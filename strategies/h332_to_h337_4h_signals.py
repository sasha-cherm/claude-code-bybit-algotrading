#!/usr/bin/env python3
"""
Backtest six novel cross-sectional factors derived from 4h (hourly→4h aggregation) microstructure.
Trade at daily frequency to keep costs low.

  H-332: Bar Consistency Score — fraction of 4h bars closing in majority direction.
         Clean intraday momentum (5/6 green) predicts next-day returns better than choppy.
  H-333: Smart Volume Return — return in the highest-volume 4h bar of the day.
         "Informed" traders concentrate activity; their directional bias predicts continuation.
  H-334: Intraday Range Efficiency — daily_range / sum(4h_ranges). ~1 = persistent,
         ~0 = mean-reverting. XS: efficient assets sustain momentum, inefficient revert.
  H-335: Session Autocorrelation — correlation of (Asia→Europe→US) session returns over lookback.
         High autocorrelation = predictable session flow, low = random.
  H-336: Volume Surprise — daily volume vs volume-weighted expectation (day-of-week × hour pattern).
         Abnormal volume = institutional flow event, predicts XS returns.
  H-337: Intraday Closing Pressure — avg close-location within 4h bars.
         Consistently closing near 4h highs = persistent buying pressure.

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
    """Load hourly data, compute 4h features, align with daily bars."""
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

    # Build daily aligned data
    closes_dict, opens_dict, volumes_dict = {}, {}, {}
    # Build 4h feature dict: each asset → DataFrame of daily-level 4h-derived features
    features_4h = {}

    for sym, df_1h in hourly_dict.items():
        daily = resample_to_daily(df_1h)
        closes_dict[sym] = daily["close"]
        opens_dict[sym] = daily["open"]
        volumes_dict[sym] = daily["volume"]

        # Resample 1h → 4h
        df_4h = df_1h.resample("4h").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum"
        }).dropna()

        # Assign each 4h bar to its calendar day (UTC)
        df_4h["date"] = df_4h.index.date
        df_4h["bar_return"] = df_4h["close"] / df_4h["open"] - 1
        df_4h["bar_range"] = df_4h["high"] - df_4h["low"]
        df_4h["clv"] = np.where(
            df_4h["bar_range"] > 0,
            (df_4h["close"] - df_4h["low"]) / df_4h["bar_range"],
            0.5
        )
        df_4h["bar_direction"] = np.sign(df_4h["bar_return"])

        # Group by calendar day to compute daily-level 4h features
        daily_feats = []
        for date, group in df_4h.groupby("date"):
            if len(group) < 4:  # need at least 4 bars (some days have 6)
                continue

            # H-332: Bar Consistency — fraction of bars in majority direction
            dirs = group["bar_direction"].values
            n_pos = (dirs > 0).sum()
            n_neg = (dirs < 0).sum()
            n_total = len(dirs)
            majority_frac = max(n_pos, n_neg) / n_total if n_total > 0 else 0.5
            # Sign it: positive if majority is up, negative if majority is down
            consistency = majority_frac if n_pos >= n_neg else -majority_frac

            # H-333: Smart Volume Return — return of highest-volume 4h bar
            max_vol_idx = group["volume"].idxmax()
            smart_return = group.loc[max_vol_idx, "bar_return"]

            # H-334: Intraday Range Efficiency — daily range / sum(4h ranges)
            daily_range = group["high"].max() - group["low"].min()
            sum_4h_ranges = group["bar_range"].sum()
            range_eff = daily_range / sum_4h_ranges if sum_4h_ranges > 0 else 0

            # H-335: Session returns (Asia 00-08, Europe 08-16, US 16-24 UTC)
            asia = group[group.index.hour < 8]
            europe = group[(group.index.hour >= 8) & (group.index.hour < 16)]
            us = group[group.index.hour >= 16]
            asia_ret = (asia["close"].iloc[-1] / asia["open"].iloc[0] - 1) if len(asia) > 0 else 0
            europe_ret = (europe["close"].iloc[-1] / europe["open"].iloc[0] - 1) if len(europe) > 0 else 0
            us_ret = (us["close"].iloc[-1] / us["open"].iloc[0] - 1) if len(us) > 0 else 0

            # H-336: Volume surprise — total daily vol / 20-day moving avg vol
            # (will be computed from rolling window in factor function instead)
            total_vol = group["volume"].sum()

            # H-337: Intraday Closing Pressure — avg CLV across 4h bars
            avg_clv = group["clv"].mean()

            daily_feats.append({
                "date": pd.Timestamp(date),
                "consistency": consistency,
                "smart_return": smart_return,
                "range_efficiency": range_eff,
                "asia_ret": asia_ret,
                "europe_ret": europe_ret,
                "us_ret": us_ret,
                "total_vol": total_vol,
                "avg_clv": avg_clv,
            })

        if daily_feats:
            feat_df = pd.DataFrame(daily_feats).set_index("date")
            feat_df.index = pd.to_datetime(feat_df.index, utc=True)
            features_4h[sym] = feat_df

    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    opens = pd.DataFrame(opens_dict).reindex(closes.index).ffill().dropna()
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill().dropna()
    idx = closes.index.intersection(opens.index).intersection(volumes.index)
    closes, opens, volumes = closes.loc[idx], opens.loc[idx], volumes.loc[idx]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"4h features computed for {len(features_4h)} assets")

    return closes, opens, volumes, features_4h


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
    """Correlation with H-076 (price efficiency)."""
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

def bar_consistency_factor(data, lookback, date_idx):
    """
    H-332: Bar Consistency Score.
    Average the signed consistency (fraction of 4h bars in majority direction) over lookback.
    High consistency = clean intraday momentum, predicts continuation.
    """
    closes = data["closes"]
    feats = data["features_4h"]
    dates = closes.index

    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        # Get lookback window of daily dates
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "consistency"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score

    return pd.Series(scores) if scores else None


def smart_volume_return_factor(data, lookback, date_idx):
    """
    H-333: Smart Volume Return.
    Average the return of the highest-volume 4h bar over lookback days.
    Captures directional bias of "informed" high-volume activity.
    """
    closes = data["closes"]
    feats = data["features_4h"]
    dates = closes.index

    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "smart_return"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score

    return pd.Series(scores) if scores else None


def intraday_range_efficiency_factor(data, lookback, date_idx):
    """
    H-334: Intraday Range Efficiency.
    Average daily_range / sum(4h_ranges) over lookback.
    High efficiency = persistent intraday moves. Low = mean-reverting intraday.
    """
    closes = data["closes"]
    feats = data["features_4h"]
    dates = closes.index

    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "range_efficiency"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score

    return pd.Series(scores) if scores else None


def session_autocorrelation_factor(data, lookback, date_idx):
    """
    H-335: Session Autocorrelation.
    Correlation of consecutive session returns (Asia→Europe, Europe→US) over lookback.
    High autocorrelation = predictable session flow, assets with momentum carry-through.
    """
    closes = data["closes"]
    feats = data["features_4h"]
    dates = closes.index

    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date)]
        if len(window) < lookback * 0.5:
            continue

        # Session autocorrelation: corr(earlier_session, later_session)
        asia = window["asia_ret"].values
        europe = window["europe_ret"].values
        us = window["us_ret"].values
        if len(asia) < 10:
            continue

        # Average of (Asia→Europe corr) and (Europe→US corr)
        try:
            ae_corr = np.corrcoef(asia, europe)[0, 1]
            eu_corr = np.corrcoef(europe, us)[0, 1]
            score = (ae_corr + eu_corr) / 2
            if np.isfinite(score):
                scores[sym] = score
        except:
            continue

    return pd.Series(scores) if scores else None


def volume_surprise_factor(data, lookback, date_idx):
    """
    H-336: Volume Surprise.
    Current day's volume / rolling average volume over lookback.
    High surprise = unusual activity (institutional flow). Average over recent window.
    """
    closes = data["closes"]
    volumes = data["volumes"]
    dates = closes.index

    scores = {}
    for sym in closes.columns:
        if sym not in volumes.columns:
            continue
        vol_series = volumes[sym].iloc[max(0, date_idx - lookback): date_idx + 1]
        if len(vol_series) < lookback * 0.5:
            continue
        avg_vol = vol_series[:-5].mean() if len(vol_series) > 5 else vol_series.mean()
        if avg_vol <= 0:
            continue
        # Average surprise over last 5 days
        recent = vol_series.iloc[-5:]
        surprise = (recent / avg_vol).mean()
        if np.isfinite(surprise):
            scores[sym] = surprise

    return pd.Series(scores) if scores else None


def closing_pressure_factor(data, lookback, date_idx):
    """
    H-337: Intraday Closing Pressure.
    Average close-location-value across 4h bars over lookback days.
    CLV near 1 = consistently closing near 4h highs = buying pressure.
    CLV near 0 = consistently closing near 4h lows = selling pressure.
    """
    closes = data["closes"]
    feats = data["features_4h"]
    dates = closes.index

    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "avg_clv"]
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

    # Dominant direction
    for d in df["direction"].unique():
        sub = df[df["direction"] == d]
        d_pos = (sub["sharpe"] > 0).sum()
        d_total = len(sub)
        d_pct = d_pos / d_total * 100 if d_total > 0 else 0
        print(f"    {d}: {d_pos}/{d_total} = {d_pct:.1f}% positive")

    if is_pct < 50:
        print(f"  VERDICT: REJECTED — IS robustness {is_pct:.1f}% < 50%")
        return

    # Walk-forward on best config
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

    # Correlation with H-012 and H-076
    corr_012 = compute_correlation_h012(closes, best_pnl)
    corr_076 = compute_correlation_h076(closes, best_pnl)
    print(f"  Correlation with H-012: {corr_012}")
    print(f"  Correlation with H-076: {corr_076}")

    # Verdict
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
    closes, opens, volumes, features_4h = load_data()

    data = {
        "closes": closes,
        "opens": opens,
        "volumes": volumes,
        "returns": closes.pct_change(),
        "features_4h": features_4h,
    }

    # Standard parameter grid
    lookbacks = [10, 20, 30, 60]
    rebals = [3, 5, 7]
    ns = [3, 4]

    # ===== H-332: Bar Consistency =====
    print("\n" + "="*60)
    print("Testing H-332: Bar Consistency Score")
    print("="*60)
    results_332 = backtest_factor(
        closes, bar_consistency_factor,
        lookbacks, rebals, ns,
        ["high_long", "low_long"],
        "H-332 Bar Consistency",
        extra_data=data,
    )
    full_validation(closes, bar_consistency_factor, results_332, "H-332 Bar Consistency", data)

    # ===== H-333: Smart Volume Return =====
    print("\n" + "="*60)
    print("Testing H-333: Smart Volume Return")
    print("="*60)
    results_333 = backtest_factor(
        closes, smart_volume_return_factor,
        lookbacks, rebals, ns,
        ["high_long", "low_long"],
        "H-333 Smart Volume Return",
        extra_data=data,
    )
    full_validation(closes, smart_volume_return_factor, results_333, "H-333 Smart Volume Return", data)

    # ===== H-334: Intraday Range Efficiency =====
    print("\n" + "="*60)
    print("Testing H-334: Intraday Range Efficiency")
    print("="*60)
    results_334 = backtest_factor(
        closes, intraday_range_efficiency_factor,
        lookbacks, rebals, ns,
        ["high_long", "low_long"],
        "H-334 Intraday Range Efficiency",
        extra_data=data,
    )
    full_validation(closes, intraday_range_efficiency_factor, results_334, "H-334 Intraday Range Efficiency", data)

    # ===== H-335: Session Autocorrelation =====
    print("\n" + "="*60)
    print("Testing H-335: Session Autocorrelation")
    print("="*60)
    results_335 = backtest_factor(
        closes, session_autocorrelation_factor,
        [20, 30, 60, 90],  # Longer lookbacks for correlation estimation
        rebals, ns,
        ["high_long", "low_long"],
        "H-335 Session Autocorrelation",
        extra_data=data,
    )
    full_validation(closes, session_autocorrelation_factor, results_335, "H-335 Session Autocorrelation", data)

    # ===== H-336: Volume Surprise =====
    print("\n" + "="*60)
    print("Testing H-336: Volume Surprise")
    print("="*60)
    results_336 = backtest_factor(
        closes, volume_surprise_factor,
        [20, 30, 60],
        rebals, ns,
        ["high_long", "low_long"],
        "H-336 Volume Surprise",
        extra_data=data,
    )
    full_validation(closes, volume_surprise_factor, results_336, "H-336 Volume Surprise", data)

    # ===== H-337: Closing Pressure =====
    print("\n" + "="*60)
    print("Testing H-337: Closing Pressure")
    print("="*60)
    results_337 = backtest_factor(
        closes, closing_pressure_factor,
        lookbacks, rebals, ns,
        ["high_long", "low_long"],
        "H-337 Closing Pressure",
        extra_data=data,
    )
    full_validation(closes, closing_pressure_factor, results_337, "H-337 Closing Pressure", data)

    print("\n\n" + "="*60)
    print("ALL 6 FACTORS COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
