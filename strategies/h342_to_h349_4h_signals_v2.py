#!/usr/bin/env python3
"""
Backtest 8 novel cross-sectional factors derived from hourly/4h microstructure (batch 2).
Trade at daily frequency to keep costs low.

  H-342: Volume-Price Synchronicity — corr(hourly_volume, abs(hourly_return)) over lookback.
         High sync = volume appears when price moves (efficient market participation).
         Low sync = volume disconnected from price moves (noise/manipulation).
  H-343: Intraday Momentum Decay — (close - open) / (high - low) averaged across 4h bars.
         High = closes near highs (sustained buying). Low = gives back intraday gains.
  H-344: Volume Clustering Score — gini coefficient of hourly volumes within each day.
         High clustering = volume concentrated in few hours (institutional block trades).
         Low clustering = evenly distributed (retail flow).
  H-345: Asia-US Session Return Spread — avg(US session return - Asia session return).
         Positive = US buyers pushing up, Asia selling. Captures institutional flow timing.
  H-346: Hourly Return Kurtosis — kurtosis of hourly returns over lookback.
         High kurtosis = fat tails = event-driven. Low = smooth/mean-reverting.
  H-347: Volume-Weighted Close Location — VWAP-like intraday positioning.
         avg((close - low) / (high - low), weighted by hourly volume).
         Volume-weighted CLV captures WHERE in the range the heavy volume traded.
  H-348: Intraday Trend Strength — avg R-squared of hourly cumulative returns vs. time
         within each day. High R² = clean intraday trend. Low = random walk intraday.
  H-349: Opening Gap Fill Rate — fraction of days where the first-hour return reverses
         the overnight gap. High fill rate = mean-reverting, low = gap continuation.

Standard framework: grid search, IS robustness (>=80%), walk-forward OOS, split-half, H-012 corr.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001
SLIPPAGE_BPS = 2.0


def load_data():
    """Load hourly data, compute features, align with daily bars."""
    print("Fetching hourly data for 14 assets...")
    hourly_dict = {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df_1h) < 200:
                continue
            hourly_dict[sym] = df_1h
        except Exception as e:
            print(f"  {sym}: {e}")

    closes_dict, opens_dict, volumes_dict = {}, {}, {}
    features = {}

    for sym, df_1h in hourly_dict.items():
        daily = resample_to_daily(df_1h)
        closes_dict[sym] = daily["close"]
        opens_dict[sym] = daily["open"]
        volumes_dict[sym] = daily["volume"]

        df_1h["hour_return"] = df_1h["close"] / df_1h["open"] - 1
        df_1h["date"] = df_1h.index.date

        # Also build 4h bars
        df_4h = df_1h.resample("4h").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum"
        }).dropna()
        df_4h["bar_return"] = df_4h["close"] / df_4h["open"] - 1
        df_4h["bar_range"] = df_4h["high"] - df_4h["low"]
        df_4h["date"] = df_4h.index.date

        daily_feats = []
        for date, hourly_group in df_1h.groupby("date"):
            if len(hourly_group) < 18:
                continue

            vol = hourly_group["volume"].values
            ret = hourly_group["hour_return"].values
            total_vol = vol.sum()

            # H-342: Volume-Price Synchronicity
            abs_ret = np.abs(ret)
            if np.std(vol) > 0 and np.std(abs_ret) > 0:
                vp_sync = np.corrcoef(vol, abs_ret)[0, 1]
            else:
                vp_sync = 0.0

            # H-344: Volume Clustering (Gini coefficient of hourly volumes)
            sorted_vol = np.sort(vol)
            n = len(sorted_vol)
            cum_vol = np.cumsum(sorted_vol)
            gini = (2 * np.sum((np.arange(1, n + 1) * sorted_vol)) / (n * np.sum(sorted_vol)) - (n + 1) / n) if np.sum(sorted_vol) > 0 else 0

            # H-345: Asia (00-08) vs US (16-24) session returns
            asia = hourly_group[hourly_group.index.hour < 8]
            us = hourly_group[hourly_group.index.hour >= 16]
            asia_ret = (asia["close"].iloc[-1] / asia["open"].iloc[0] - 1) if len(asia) >= 4 else 0
            us_ret = (us["close"].iloc[-1] / us["open"].iloc[0] - 1) if len(us) >= 4 else 0
            session_spread = us_ret - asia_ret

            # H-346: Hourly Return Kurtosis
            if len(ret) >= 10 and np.std(ret) > 0:
                hour_kurt = float(stats.kurtosis(ret, fisher=True))
            else:
                hour_kurt = 0.0

            # H-347: Volume-Weighted Close Location
            # For each hour: CLV = (close - low) / (high - low), weighted by volume
            h_range = hourly_group["high"].values - hourly_group["low"].values
            h_clv = np.where(h_range > 0,
                           (hourly_group["close"].values - hourly_group["low"].values) / h_range,
                           0.5)
            if total_vol > 0:
                vw_clv = np.sum(h_clv * vol) / total_vol
            else:
                vw_clv = 0.5

            # H-348: Intraday Trend Strength (R² of cumulative return vs time)
            cum_ret = np.cumsum(ret)
            if len(cum_ret) >= 10:
                x = np.arange(len(cum_ret))
                slope, intercept, r_value, p_value, std_err = stats.linregress(x, cum_ret)
                r_squared = r_value ** 2
                # Sign it by the direction of the trend
                trend_strength = r_squared * np.sign(slope)
            else:
                trend_strength = 0.0

            # H-349: Opening Gap Fill Rate
            # "Gap" = overnight return (prev close to first hour open is implicit in first bar)
            # We approximate: first hour return direction vs. rest-of-day direction
            first_ret = ret[0] if len(ret) > 0 else 0
            rest_ret = np.sum(ret[1:]) if len(ret) > 1 else 0
            gap_filled = 1.0 if (first_ret * rest_ret < 0 and abs(rest_ret) > abs(first_ret) * 0.5) else 0.0

            daily_feats.append({
                "date": pd.Timestamp(date),
                "vp_sync": float(vp_sync) if np.isfinite(vp_sync) else 0.0,
                "vol_gini": float(gini),
                "session_spread": float(session_spread),
                "hour_kurt": float(hour_kurt) if np.isfinite(hour_kurt) else 0.0,
                "vw_clv": float(vw_clv),
                "trend_strength": float(trend_strength) if np.isfinite(trend_strength) else 0.0,
                "gap_filled": float(gap_filled),
            })

        # H-343: Intraday Momentum Decay from 4h bars
        day_groups_4h = df_4h.groupby("date")
        momentum_decay_dict = {}
        for date, g4h in day_groups_4h:
            if len(g4h) < 4:
                continue
            br = g4h["bar_range"].values
            valid = br > 0
            if valid.sum() < 3:
                continue
            # (close - open) / (high - low) for each 4h bar, averaged
            clv_4h = np.where(br > 0, (g4h["close"].values - g4h["open"].values) / br, 0)
            momentum_decay_dict[pd.Timestamp(date)] = float(np.mean(clv_4h))

        if daily_feats:
            feat_df = pd.DataFrame(daily_feats).set_index("date")
            if feat_df.index.tz is None:
                feat_df.index = feat_df.index.tz_localize("UTC")
            # Add momentum decay
            if momentum_decay_dict:
                md_series = pd.Series(momentum_decay_dict, name="momentum_decay")
                if md_series.index.tz is None:
                    md_series.index = md_series.index.tz_localize("UTC")
                feat_df = feat_df.join(md_series, how="left")
                feat_df["momentum_decay"] = feat_df["momentum_decay"].fillna(0)
            else:
                feat_df["momentum_decay"] = 0.0
            features[sym] = feat_df

    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    opens = pd.DataFrame(opens_dict).reindex(closes.index).ffill()
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill()

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars, "
          f"features for {len(features)} assets")
    return closes, opens, volumes, features


def backtest_factor(closes, factor_fn, lookbacks, rebals, ns, directions,
                    factor_name, extra_data=None):
    returns = closes.pct_change()
    slippage = SLIPPAGE_BPS / 10_000
    results = []

    for lookback in lookbacks:
        for rebal in rebals:
            for n in ns:
                for direction in directions:
                    warmup = lookback + 10
                    pnl_daily = []
                    positions = {}
                    days_since = rebal

                    for i in range(warmup, len(closes)):
                        days_since += 1
                        if days_since >= rebal:
                            scores = factor_fn(extra_data, lookback, i)
                            if scores is None or len(scores) < 2 * n:
                                continue

                            if direction.endswith("_long"):
                                high_first = direction.startswith("high")
                                ranked = scores.sort_values(ascending=not high_first)
                            else:
                                ranked = scores.sort_values(ascending=False)

                            longs = set(ranked.index[:n])
                            shorts = set(ranked.index[-n:])
                            old_syms = set(positions.keys())
                            new_syms = longs | shorts
                            changed = old_syms.symmetric_difference(new_syms)
                            fee_cost = len(changed) * FEE_RATE / (2 * n)
                            slip_cost = len(changed) * slippage / (2 * n)

                            positions = {}
                            for sym in longs:
                                positions[sym] = 1.0 / n
                            for sym in shorts:
                                positions[sym] = -1.0 / n
                            days_since = 0
                            daily_ret = -fee_cost - slip_cost
                        else:
                            daily_ret = 0.0

                        for sym, w in positions.items():
                            if sym in returns.columns:
                                r = returns[sym].iloc[i]
                                if np.isfinite(r):
                                    daily_ret += w * r
                        pnl_daily.append(daily_ret)

                    if len(pnl_daily) < 100:
                        continue

                    pnl = np.array(pnl_daily)
                    sharpe = float(np.mean(pnl) / np.std(pnl) * np.sqrt(365)) if np.std(pnl) > 0 else 0
                    ann_ret = float((1 + np.mean(pnl)) ** 365 - 1) * 100
                    cum = np.cumprod(1 + pnl)
                    dd = float((1 - cum / np.maximum.accumulate(cum)).max()) * 100

                    results.append({
                        "factor": factor_name,
                        "lookback": lookback,
                        "rebal": rebal,
                        "n": n,
                        "direction": direction,
                        "sharpe": round(sharpe, 3),
                        "ann_ret": round(ann_ret, 1),
                        "max_dd": round(dd, 1),
                        "n_days": len(pnl_daily),
                        "pnl_daily": pnl,
                    })

    return results


def walk_forward(closes, factor_fn, lookback, rebal, n, direction,
                 extra_data=None, n_folds=6):
    returns = closes.pct_change()
    slippage = SLIPPAGE_BPS / 10_000
    total_bars = len(closes)
    warmup = lookback + 10
    usable = total_bars - warmup
    fold_size = usable // n_folds

    oos_sharpes = []
    for fold in range(n_folds):
        test_start = warmup + fold * fold_size
        test_end = min(test_start + fold_size, total_bars)
        if test_end > total_bars:
            break

        positions = {}
        days_since = rebal
        pnl_daily = []

        for i in range(test_start, test_end):
            days_since += 1
            if days_since >= rebal:
                scores = factor_fn(extra_data, lookback, i)
                if scores is None or len(scores) < 2 * n:
                    continue

                if direction.endswith("_long"):
                    high_first = direction.startswith("high")
                    ranked = scores.sort_values(ascending=not high_first)
                else:
                    ranked = scores.sort_values(ascending=False)

                longs = set(ranked.index[:n])
                shorts = set(ranked.index[-n:])
                old_syms = set(positions.keys())
                new_syms = longs | shorts
                changed = old_syms.symmetric_difference(new_syms)
                fee_cost = len(changed) * FEE_RATE / (2 * n)
                slip_cost = len(changed) * slippage / (2 * n)

                positions = {}
                for sym in longs:
                    positions[sym] = 1.0 / n
                for sym in shorts:
                    positions[sym] = -1.0 / n
                days_since = 0
                daily_ret = -fee_cost - slip_cost
            else:
                daily_ret = 0.0

            for sym, w in positions.items():
                if sym in returns.columns:
                    r = returns[sym].iloc[i]
                    if np.isfinite(r):
                        daily_ret += w * r
            pnl_daily.append(daily_ret)

        if len(pnl_daily) < 30:
            continue
        pnl = np.array(pnl_daily)
        sharpe = float(np.mean(pnl) / np.std(pnl) * np.sqrt(365)) if np.std(pnl) > 0 else 0
        oos_sharpes.append(sharpe)

    return oos_sharpes


def compute_correlation_h012(closes, pnl_daily):
    returns = closes.pct_change()
    lookback, rebal, n = 60, 5, 4
    h012_pnl = []
    positions = {}
    days_since = rebal

    for i in range(70, len(closes)):
        days_since += 1
        if days_since >= rebal:
            mom = {}
            for sym in closes.columns:
                if i >= lookback:
                    r = closes[sym].iloc[i] / closes[sym].iloc[i - lookback] - 1
                    if np.isfinite(r):
                        mom[sym] = r
            if len(mom) < 2 * n:
                h012_pnl.append(0)
                continue
            ranked = pd.Series(mom).sort_values(ascending=False)
            longs = set(ranked.index[:n])
            shorts = set(ranked.index[-n:])
            old_syms = set(positions.keys())
            new_syms = longs | shorts
            changed = old_syms.symmetric_difference(new_syms)
            fee_cost = len(changed) * FEE_RATE / (2 * n)

            positions = {}
            for sym in longs:
                positions[sym] = 1.0 / n
            for sym in shorts:
                positions[sym] = -1.0 / n
            days_since = 0
            daily_ret = -fee_cost
        else:
            daily_ret = 0.0

        for sym, w in positions.items():
            if sym in returns.columns:
                r = returns[sym].iloc[i]
                if np.isfinite(r):
                    daily_ret += w * r
        h012_pnl.append(daily_ret)

    h012 = np.array(h012_pnl)
    min_len = min(len(h012), len(pnl_daily))
    if min_len < 50:
        return 0.0
    corr = np.corrcoef(h012[-min_len:], pnl_daily[-min_len:])[0, 1]
    return round(corr, 3) if np.isfinite(corr) else 0.0


def compute_correlation_h076(closes, pnl_daily):
    returns = closes.pct_change()
    lookback, rebal, n = 40, 5, 4
    h076_pnl = []
    positions = {}
    days_since = rebal

    for i in range(50, len(closes)):
        days_since += 1
        if days_since >= rebal:
            eff = {}
            for sym in closes.columns:
                c = closes[sym].iloc[max(0, i - lookback):i + 1]
                if len(c) < lookback * 0.7:
                    continue
                net_move = abs(c.iloc[-1] - c.iloc[0])
                sum_abs_moves = c.diff().abs().sum()
                if sum_abs_moves > 0:
                    eff[sym] = net_move / sum_abs_moves
            if len(eff) < 2 * n:
                h076_pnl.append(0)
                continue
            ranked = pd.Series(eff).sort_values(ascending=False)
            longs = set(ranked.index[:n])
            shorts = set(ranked.index[-n:])
            old_syms = set(positions.keys())
            new_syms = longs | shorts
            changed = old_syms.symmetric_difference(new_syms)
            fee_cost = len(changed) * FEE_RATE / (2 * n)

            positions = {}
            for sym in longs:
                positions[sym] = 1.0 / n
            for sym in shorts:
                positions[sym] = -1.0 / n
            days_since = 0
            daily_ret = -fee_cost
        else:
            daily_ret = 0.0

        for sym, w in positions.items():
            if sym in returns.columns:
                r = returns[sym].iloc[i]
                if np.isfinite(r):
                    daily_ret += w * r
        h076_pnl.append(daily_ret)

    h076 = np.array(h076_pnl)
    min_len = min(len(h076), len(pnl_daily))
    if min_len < 50:
        return 0.0
    corr = np.corrcoef(h076[-min_len:], pnl_daily[-min_len:])[0, 1]
    return round(corr, 3) if np.isfinite(corr) else 0.0


# ============ Factor Definitions ============

def vp_synchronicity_factor(data, lookback, date_idx):
    """H-342: Volume-Price Synchronicity — corr(volume, abs(return)) over lookback."""
    closes = data["closes"]
    feats = data["features"]
    dates = closes.index
    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        if "vp_sync" not in feat.columns:
            continue
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "vp_sync"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score
    return pd.Series(scores) if scores else None


def momentum_decay_factor(data, lookback, date_idx):
    """H-343: Intraday Momentum Decay — avg((close-open)/(high-low)) of 4h bars."""
    closes = data["closes"]
    feats = data["features"]
    dates = closes.index
    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        if "momentum_decay" not in feat.columns:
            continue
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "momentum_decay"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score
    return pd.Series(scores) if scores else None


def volume_clustering_factor(data, lookback, date_idx):
    """H-344: Volume Clustering — Gini of hourly volumes over lookback days."""
    closes = data["closes"]
    feats = data["features"]
    dates = closes.index
    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        if "vol_gini" not in feat.columns:
            continue
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "vol_gini"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score
    return pd.Series(scores) if scores else None


def session_spread_factor(data, lookback, date_idx):
    """H-345: Asia-US Session Return Spread — avg(US return - Asia return)."""
    closes = data["closes"]
    feats = data["features"]
    dates = closes.index
    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        if "session_spread" not in feat.columns:
            continue
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "session_spread"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score
    return pd.Series(scores) if scores else None


def hourly_kurtosis_factor(data, lookback, date_idx):
    """H-346: Hourly Return Kurtosis over lookback days."""
    closes = data["closes"]
    feats = data["features"]
    dates = closes.index
    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        if "hour_kurt" not in feat.columns:
            continue
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "hour_kurt"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score
    return pd.Series(scores) if scores else None


def vw_close_location_factor(data, lookback, date_idx):
    """H-347: Volume-Weighted Close Location over lookback days."""
    closes = data["closes"]
    feats = data["features"]
    dates = closes.index
    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        if "vw_clv" not in feat.columns:
            continue
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "vw_clv"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score
    return pd.Series(scores) if scores else None


def trend_strength_factor(data, lookback, date_idx):
    """H-348: Intraday Trend Strength (signed R² of cumulative return vs time)."""
    closes = data["closes"]
    feats = data["features"]
    dates = closes.index
    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        if "trend_strength" not in feat.columns:
            continue
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "trend_strength"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score
    return pd.Series(scores) if scores else None


def gap_fill_rate_factor(data, lookback, date_idx):
    """H-349: Opening Gap Fill Rate over lookback days."""
    closes = data["closes"]
    feats = data["features"]
    dates = closes.index
    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        if "gap_filled" not in feat.columns:
            continue
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "gap_filled"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score
    return pd.Series(scores) if scores else None


# ============ Full Validation ============

def full_validation(closes, factor_fn, results, factor_name, extra_data):
    """Run full validation: IS robustness, WF, split-half, correlations."""
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "pnl_daily"} for r in results])
    if len(df) == 0:
        print(f"\n{'='*60}")
        print(f"  {factor_name}: NO VALID RESULTS")
        return

    pos_sharpe = (df["sharpe"] > 0).sum()
    total = len(df)
    is_pct = pos_sharpe / total * 100

    print(f"\n{'='*60}")
    print(f"  {factor_name}")
    print(f"{'='*60}")
    print(f"  Grid: {total} configs tested")
    print(f"  IS robustness: {pos_sharpe}/{total} = {is_pct:.1f}% positive Sharpe")
    print(f"  Best IS Sharpe: {df['sharpe'].max():.3f}")
    print(f"  Mean IS Sharpe: {df['sharpe'].mean():.3f}")
    print(f"  Best: LB={df.loc[df['sharpe'].idxmax(), 'lookback']}, "
          f"R={df.loc[df['sharpe'].idxmax(), 'rebal']}, "
          f"N={df.loc[df['sharpe'].idxmax(), 'n']}, "
          f"Dir={df.loc[df['sharpe'].idxmax(), 'direction']}")

    for d in df["direction"].unique():
        sub = df[df["direction"] == d]
        d_pos = (sub["sharpe"] > 0).sum()
        d_total = len(sub)
        d_pct = d_pos / d_total * 100 if d_total > 0 else 0
        print(f"    {d}: {d_pos}/{d_total} = {d_pct:.1f}% positive")

    if is_pct < 50:
        print(f"  VERDICT: REJECTED — IS robustness {is_pct:.1f}% < 50%")
        return

    best = df.loc[df["sharpe"].idxmax()]
    best_result = results[df["sharpe"].idxmax()]
    best_pnl = best_result["pnl_daily"]

    wf_sharpes = walk_forward(
        closes, factor_fn,
        int(best["lookback"]), int(best["rebal"]), int(best["n"]),
        best["direction"], extra_data
    )

    if wf_sharpes:
        wf_pos = sum(1 for s in wf_sharpes if s > 0)
        wf_total = len(wf_sharpes)
        wf_mean = np.mean(wf_sharpes)
        print(f"  Walk-forward OOS: {wf_pos}/{wf_total} positive, mean Sharpe {wf_mean:.3f}")
        print(f"    Fold Sharpes: {[round(s, 3) for s in wf_sharpes]}")
    else:
        print(f"  Walk-forward: FAILED (no folds)")
        print(f"  VERDICT: REJECTED — WF failed")
        return

    # Neighboring params
    best_lb = int(best["lookback"])
    best_rb = int(best["rebal"])
    best_n = int(best["n"])
    best_dir = best["direction"]
    neighbors = df[
        (df["direction"] == best_dir) &
        (abs(df["lookback"] - best_lb) <= 10) &
        (abs(df["rebal"] - best_rb) <= 2) &
        (abs(df["n"] - best_n) <= 1)
    ]
    if len(neighbors) > 1:
        nb_pos = (neighbors["sharpe"] > 0).sum()
        nb_pct = nb_pos / len(neighbors) * 100
        print(f"  Neighboring params: {nb_pos}/{len(neighbors)} = {nb_pct:.1f}% positive")

    # Split-half
    half = len(best_pnl) // 2
    h1, h2 = best_pnl[:half], best_pnl[half:]
    s1 = float(np.mean(h1) / np.std(h1) * np.sqrt(365)) if np.std(h1) > 0 else 0
    s2 = float(np.mean(h2) / np.std(h2) * np.sqrt(365)) if np.std(h2) > 0 else 0
    split_pass = (s1 > 0 and s2 > 0)
    print(f"  Split-half: H1={s1:.3f}, H2={s2:.3f} — {'PASS' if split_pass else 'FAIL'}")

    corr_012 = compute_correlation_h012(closes, best_pnl)
    corr_076 = compute_correlation_h076(closes, best_pnl)
    print(f"  Correlation with H-012: {corr_012}")
    print(f"  Correlation with H-076: {corr_076}")

    wf_pass = wf_pos >= wf_total * 0.6 if wf_sharpes else False
    is_pass = is_pct >= 80
    corr_ok = abs(corr_012) < 0.5

    if is_pass and wf_pass and split_pass and corr_ok:
        print(f"  VERDICT: **CONFIRMED** — IS {is_pct:.1f}%, WF {wf_pos}/{wf_total}, "
              f"split OK, corr {corr_012}")
    elif is_pass and wf_pass and corr_ok:
        print(f"  VERDICT: BORDERLINE — IS {is_pct:.1f}%, WF {wf_pos}/{wf_total}, "
              f"split {'PASS' if split_pass else 'FAIL'}, corr {corr_012}")
    elif is_pct >= 70 and wf_pass:
        print(f"  VERDICT: BORDERLINE — IS {is_pct:.1f}% (marginal), WF {wf_pos}/{wf_total}")
    else:
        reasons = []
        if not is_pass:
            reasons.append(f"IS {is_pct:.1f}%")
        if not wf_pass:
            reasons.append(f"WF {wf_pos}/{len(wf_sharpes) if wf_sharpes else 0}")
        if not split_pass:
            reasons.append(f"split {s1:.2f}/{s2:.2f}")
        if not corr_ok:
            reasons.append(f"corr {corr_012}")
        print(f"  VERDICT: REJECTED — {', '.join(reasons)}")


def main():
    closes, opens, volumes, features = load_data()

    data = {
        "closes": closes,
        "opens": opens,
        "volumes": volumes,
        "returns": closes.pct_change(),
        "features": features,
    }

    lookbacks = [10, 20, 30, 60]
    rebals = [3, 5, 7]
    ns = [3, 4]

    # ===== H-342: Volume-Price Synchronicity =====
    print("\n" + "="*60)
    print("Testing H-342: Volume-Price Synchronicity")
    print("="*60)
    r342 = backtest_factor(closes, vp_synchronicity_factor,
                           lookbacks, rebals, ns,
                           ["high_long", "low_long"], "H-342 VP Synchronicity", data)
    full_validation(closes, vp_synchronicity_factor, r342, "H-342 VP Synchronicity", data)

    # ===== H-343: Intraday Momentum Decay =====
    print("\n" + "="*60)
    print("Testing H-343: Intraday Momentum Decay")
    print("="*60)
    r343 = backtest_factor(closes, momentum_decay_factor,
                           lookbacks, rebals, ns,
                           ["high_long", "low_long"], "H-343 Momentum Decay", data)
    full_validation(closes, momentum_decay_factor, r343, "H-343 Momentum Decay", data)

    # ===== H-344: Volume Clustering =====
    print("\n" + "="*60)
    print("Testing H-344: Volume Clustering")
    print("="*60)
    r344 = backtest_factor(closes, volume_clustering_factor,
                           lookbacks, rebals, ns,
                           ["high_long", "low_long"], "H-344 Volume Clustering", data)
    full_validation(closes, volume_clustering_factor, r344, "H-344 Volume Clustering", data)

    # ===== H-345: Session Spread =====
    print("\n" + "="*60)
    print("Testing H-345: Asia-US Session Spread")
    print("="*60)
    r345 = backtest_factor(closes, session_spread_factor,
                           lookbacks, rebals, ns,
                           ["high_long", "low_long"], "H-345 Session Spread", data)
    full_validation(closes, session_spread_factor, r345, "H-345 Session Spread", data)

    # ===== H-346: Hourly Kurtosis =====
    print("\n" + "="*60)
    print("Testing H-346: Hourly Return Kurtosis")
    print("="*60)
    r346 = backtest_factor(closes, hourly_kurtosis_factor,
                           lookbacks, rebals, ns,
                           ["high_long", "low_long"], "H-346 Hourly Kurtosis", data)
    full_validation(closes, hourly_kurtosis_factor, r346, "H-346 Hourly Kurtosis", data)

    # ===== H-347: VW Close Location =====
    print("\n" + "="*60)
    print("Testing H-347: Volume-Weighted Close Location")
    print("="*60)
    r347 = backtest_factor(closes, vw_close_location_factor,
                           lookbacks, rebals, ns,
                           ["high_long", "low_long"], "H-347 VW Close Location", data)
    full_validation(closes, vw_close_location_factor, r347, "H-347 VW Close Location", data)

    # ===== H-348: Intraday Trend Strength =====
    print("\n" + "="*60)
    print("Testing H-348: Intraday Trend Strength")
    print("="*60)
    r348 = backtest_factor(closes, trend_strength_factor,
                           lookbacks, rebals, ns,
                           ["high_long", "low_long"], "H-348 Trend Strength", data)
    full_validation(closes, trend_strength_factor, r348, "H-348 Trend Strength", data)

    # ===== H-349: Gap Fill Rate =====
    print("\n" + "="*60)
    print("Testing H-349: Gap Fill Rate")
    print("="*60)
    r349 = backtest_factor(closes, gap_fill_rate_factor,
                           lookbacks, rebals, ns,
                           ["high_long", "low_long"], "H-349 Gap Fill Rate", data)
    full_validation(closes, gap_fill_rate_factor, r349, "H-349 Gap Fill Rate", data)


if __name__ == "__main__":
    main()
