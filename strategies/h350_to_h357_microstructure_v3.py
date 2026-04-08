#!/usr/bin/env python3
"""
Backtest 8 novel cross-sectional factors derived from hourly/4h microstructure (batch 3).
Trade at daily frequency to keep costs low.

  H-350: Opening Drive Ratio — first 4h bar's absolute return / full day's range.
         High = opening session dominates the day (institutional overnight flow sets direction).
         Low = opening is noise, real action comes later.
  H-351: Volume Profile Skewness — skewness of hourly volume distribution within each day.
         Positive skew = volume back-loaded (late-day conviction). Negative = front-loaded.
  H-352: Intraday R-squared — R² of hourly cumulative returns regressed on time.
         High R² = clean intraday trend (informed flow). Low = choppy/random.
  H-353: Volume Persistence — autocorrelation of hourly volumes within a day.
         High = sustained engagement (trending). Low = sporadic bursts.
  H-354: Session Momentum Ratio — US session return / (Asia + Europe session return).
         Captures institutional vs retail flow imbalance.
  H-355: Hourly Return Entropy — Shannon entropy of discretized hourly returns.
         High entropy = unpredictable (random walk). Low = structured/trending.
  H-356: Volume-at-Extremes — fraction of daily volume occurring at hours with price
         near daily high or low. High = volume concentrates at extremes (breakout behavior).
  H-357: Intraday Mean Reversion Speed — avg absolute first-hour return minus avg absolute
         full-day return, normalized. High = first move reverses. Low = first move extends.

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

        # Build 4h bars
        df_4h = df_1h.resample("4h").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum"
        }).dropna()
        df_4h["date"] = df_4h.index.date

        daily_feats = []
        for date, hg in df_1h.groupby("date"):
            if len(hg) < 18:
                continue

            vol = hg["volume"].values
            ret = hg["hour_return"].values
            total_vol = vol.sum()
            h_open = hg["open"].values
            h_close = hg["close"].values
            h_high = hg["high"].values
            h_low = hg["low"].values

            day_high = h_high.max()
            day_low = h_low.min()
            day_range = day_high - day_low

            # H-350: Opening Drive Ratio
            # First 4 hourly bars (first ~4h) absolute return / full day range
            first4_ret = abs(h_close[3] - h_open[0]) if len(ret) >= 4 else 0
            opening_drive = first4_ret / day_range if day_range > 0 else 0

            # H-351: Volume Profile Skewness
            if len(vol) >= 10 and np.std(vol) > 0:
                vol_skew = float(stats.skew(vol))
            else:
                vol_skew = 0.0

            # H-352: Intraday R-squared
            cum_ret = np.cumsum(ret)
            if len(cum_ret) >= 10:
                x = np.arange(len(cum_ret))
                slope, intercept, r_value, p_value, std_err = stats.linregress(x, cum_ret)
                intraday_r2 = r_value ** 2
            else:
                intraday_r2 = 0.0

            # H-353: Volume Persistence (autocorrelation of hourly volumes)
            if len(vol) >= 10 and np.std(vol) > 0:
                vol_ac = np.corrcoef(vol[:-1], vol[1:])[0, 1]
                vol_persistence = float(vol_ac) if np.isfinite(vol_ac) else 0.0
            else:
                vol_persistence = 0.0

            # H-354: Session Momentum Ratio
            # Asia: 00-08, Europe: 08-16, US: 16-24
            asia = hg[hg.index.hour < 8]
            europe = hg[(hg.index.hour >= 8) & (hg.index.hour < 16)]
            us = hg[hg.index.hour >= 16]
            asia_ret = (asia["close"].iloc[-1] / asia["open"].iloc[0] - 1) if len(asia) >= 4 else 0
            europe_ret = (europe["close"].iloc[-1] / europe["open"].iloc[0] - 1) if len(europe) >= 4 else 0
            us_ret = (us["close"].iloc[-1] / us["open"].iloc[0] - 1) if len(us) >= 4 else 0
            ae_ret = asia_ret + europe_ret
            session_ratio = us_ret / ae_ret if abs(ae_ret) > 1e-6 else 0.0
            # Clip extreme values
            session_ratio = np.clip(session_ratio, -10, 10)

            # H-355: Hourly Return Entropy
            # Discretize returns into bins and compute Shannon entropy
            if len(ret) >= 10 and np.std(ret) > 0:
                # 5 bins: very negative, negative, flat, positive, very positive
                std = np.std(ret)
                bins = [-np.inf, -std, -std/3, std/3, std, np.inf]
                counts = np.histogram(ret, bins=bins)[0]
                probs = counts / counts.sum()
                probs = probs[probs > 0]
                entropy = -np.sum(probs * np.log2(probs))
            else:
                entropy = 0.0

            # H-356: Volume-at-Extremes
            # Fraction of volume at hours where price is near daily high or low
            if day_range > 0 and total_vol > 0:
                threshold = 0.2  # within 20% of extreme
                near_high = h_high >= day_low + day_range * 0.8
                near_low = h_low <= day_low + day_range * 0.2
                extreme_mask = near_high | near_low
                vol_at_extremes = vol[extreme_mask].sum() / total_vol
            else:
                vol_at_extremes = 0.5

            # H-357: Intraday Mean Reversion Speed
            # |first hour return| vs |full day return|, captures if first move reverses
            first_abs = abs(ret[0]) if len(ret) > 0 else 0
            full_day_ret = abs(np.sum(ret)) if len(ret) > 0 else 0
            mr_speed = first_abs - full_day_ret if first_abs > 0 else 0.0

            daily_feats.append({
                "date": pd.Timestamp(date),
                "opening_drive": float(opening_drive) if np.isfinite(opening_drive) else 0.0,
                "vol_skew": float(vol_skew) if np.isfinite(vol_skew) else 0.0,
                "intraday_r2": float(intraday_r2) if np.isfinite(intraday_r2) else 0.0,
                "vol_persistence": float(vol_persistence) if np.isfinite(vol_persistence) else 0.0,
                "session_ratio": float(session_ratio) if np.isfinite(session_ratio) else 0.0,
                "entropy": float(entropy) if np.isfinite(entropy) else 0.0,
                "vol_at_extremes": float(vol_at_extremes) if np.isfinite(vol_at_extremes) else 0.0,
                "mr_speed": float(mr_speed) if np.isfinite(mr_speed) else 0.0,
            })

        if daily_feats:
            feat_df = pd.DataFrame(daily_feats).set_index("date")
            if feat_df.index.tz is None:
                feat_df.index = feat_df.index.tz_localize("UTC")
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


def main():
    closes, opens, volumes, features = load_data()

    # Align features: for each asset, get rolling averages of microstructure metrics
    # features[sym] has daily rows with columns: opening_drive, vol_skew, etc.

    lookbacks = [5, 10, 14, 20, 30]
    rebals = [3, 5, 7]
    ns = [3, 4]
    directions_standard = ["high_long", "low_long"]

    # Helper: build rolling average factor scores for a given feature column
    def make_factor_fn(feature_col):
        def factor_fn(extra_data, lookback, i):
            date_idx = closes.index[i]
            scores = {}
            for sym in closes.columns:
                if sym not in features:
                    continue
                feat = features[sym]
                # Get feature values up to date_idx
                mask = feat.index <= date_idx
                vals = feat.loc[mask, feature_col]
                if len(vals) < lookback:
                    continue
                avg = vals.iloc[-lookback:].mean()
                if np.isfinite(avg):
                    scores[sym] = avg
            if len(scores) < 6:
                return None
            return pd.Series(scores)
        return factor_fn

    # Hypotheses to test
    hypothesis_configs = [
        ("H-350", "opening_drive", "Opening Drive Ratio"),
        ("H-351", "vol_skew", "Volume Profile Skewness"),
        ("H-352", "intraday_r2", "Intraday R-squared"),
        ("H-353", "vol_persistence", "Volume Persistence"),
        ("H-354", "session_ratio", "Session Momentum Ratio"),
        ("H-355", "entropy", "Hourly Return Entropy"),
        ("H-356", "vol_at_extremes", "Volume-at-Extremes"),
        ("H-357", "mr_speed", "Intraday Mean Reversion Speed"),
    ]

    all_summaries = []

    for h_id, feat_col, name in hypothesis_configs:
        print(f"\n{'='*60}")
        print(f"{h_id}: {name}")
        print(f"{'='*60}")

        factor_fn = make_factor_fn(feat_col)

        results = backtest_factor(
            closes, factor_fn, lookbacks, rebals, ns, directions_standard,
            h_id, extra_data=None,
        )

        if not results:
            print(f"  No valid results")
            all_summaries.append({
                "id": h_id, "name": name, "status": "FAILED",
                "reason": "no valid results"
            })
            continue

        # Evaluate IS robustness
        positive = [r for r in results if r["sharpe"] > 0]
        is_pct = len(positive) / len(results) * 100

        # Find dominant direction
        dir_stats = {}
        for d in directions_standard:
            d_results = [r for r in results if r["direction"] == d]
            d_pos = len([r for r in d_results if r["sharpe"] > 0])
            d_total = len(d_results)
            dir_stats[d] = (d_pos / d_total * 100) if d_total > 0 else 0

        best_dir = max(dir_stats, key=dir_stats.get)
        best_dir_pct = dir_stats[best_dir]

        # Best params (in dominant direction)
        best_dir_results = [r for r in results if r["direction"] == best_dir]
        best = max(best_dir_results, key=lambda r: r["sharpe"])

        print(f"  IS robustness: {is_pct:.1f}% ({len(positive)}/{len(results)}) total")
        print(f"  Dominant direction: {best_dir} ({best_dir_pct:.1f}%)")
        print(f"  Best: LB{best['lookback']}_R{best['rebal']}_N{best['n']} "
              f"Sharpe={best['sharpe']:.3f} Ann={best['ann_ret']:.1f}% DD={best['max_dd']:.1f}%")

        # Check if IS passes threshold
        if best_dir_pct < 80:
            print(f"  REJECTED — dominant direction IS {best_dir_pct:.1f}% < 80%")
            all_summaries.append({
                "id": h_id, "name": name, "status": "REJECTED",
                "reason": f"IS {best_dir_pct:.1f}%",
                "best_sharpe": best["sharpe"],
            })
            continue

        # Walk-forward OOS
        wf_sharpes = walk_forward(
            closes, factor_fn,
            best["lookback"], best["rebal"], best["n"], best["direction"],
        )
        wf_pos = sum(1 for s in wf_sharpes if s > 0)
        wf_mean = np.mean(wf_sharpes) if wf_sharpes else 0

        print(f"  WF OOS: {wf_pos}/{len(wf_sharpes)} positive, mean Sharpe {wf_mean:.3f}")
        print(f"  WF Sharpes: {[round(s, 3) for s in wf_sharpes]}")

        if wf_pos < len(wf_sharpes) * 0.6:
            print(f"  REJECTED — WF {wf_pos}/{len(wf_sharpes)} < 60%")
            all_summaries.append({
                "id": h_id, "name": name, "status": "REJECTED",
                "reason": f"WF {wf_pos}/{len(wf_sharpes)}",
                "is_pct": best_dir_pct,
                "best_sharpe": best["sharpe"],
            })
            continue

        # Split-half stability
        dom_results = [r for r in results if r["direction"] == best_dir and len(r["pnl_daily"]) > 100]
        if dom_results:
            half = len(dom_results[0]["pnl_daily"]) // 2
            h1_sharpes = []
            h2_sharpes = []
            for r in dom_results:
                pnl = r["pnl_daily"]
                if len(pnl) < 100:
                    continue
                h1 = pnl[:half]
                h2 = pnl[half:]
                s1 = np.mean(h1) / np.std(h1) * np.sqrt(365) if np.std(h1) > 0 else 0
                s2 = np.mean(h2) / np.std(h2) * np.sqrt(365) if np.std(h2) > 0 else 0
                h1_sharpes.append(s1)
                h2_sharpes.append(s2)
            avg_h1 = np.mean(h1_sharpes) if h1_sharpes else 0
            avg_h2 = np.mean(h2_sharpes) if h2_sharpes else 0
            print(f"  Split-half: H1={avg_h1:.3f} H2={avg_h2:.3f}")
            split_pass = (avg_h1 > 0 and avg_h2 > 0)
        else:
            split_pass = False
            avg_h1, avg_h2 = 0, 0

        # Correlation with H-012 and H-076
        corr_012 = compute_correlation_h012(closes, best["pnl_daily"])
        corr_076 = compute_correlation_h076(closes, best["pnl_daily"])
        print(f"  Corr H-012: {corr_012:.3f}, H-076: {corr_076:.3f}")

        # Neighbor robustness
        neighbors = [r for r in dom_results
                     if abs(r["lookback"] - best["lookback"]) <= 5
                     and abs(r["rebal"] - best["rebal"]) <= 2
                     and abs(r["n"] - best["n"]) <= 1]
        neighbor_pos = sum(1 for r in neighbors if r["sharpe"] > 0)
        neighbor_pct = neighbor_pos / len(neighbors) * 100 if neighbors else 0
        print(f"  Neighbor robustness: {neighbor_pos}/{len(neighbors)} ({neighbor_pct:.0f}%)")

        status = "CONFIRMED" if (split_pass and neighbor_pct >= 50) else "REJECTED"
        reason = ""
        if not split_pass:
            reason = f"split-half fail (H1={avg_h1:.3f} H2={avg_h2:.3f})"
            status = "REJECTED"
        if neighbor_pct < 50:
            reason += f" neighbor {neighbor_pct:.0f}%"
            status = "REJECTED"

        if status == "CONFIRMED":
            print(f"  *** CONFIRMED *** WF {wf_pos}/{len(wf_sharpes)} mean {wf_mean:.3f}")
        else:
            print(f"  REJECTED — {reason}")

        all_summaries.append({
            "id": h_id, "name": name, "status": status,
            "is_pct": best_dir_pct,
            "best_dir": best_dir,
            "best_sharpe": best["sharpe"],
            "best_ann_ret": best["ann_ret"],
            "best_dd": best["max_dd"],
            "best_params": f"LB{best['lookback']}_R{best['rebal']}_N{best['n']}",
            "wf_pos": wf_pos, "wf_total": len(wf_sharpes),
            "wf_mean": round(wf_mean, 3),
            "wf_sharpes": [round(s, 3) for s in wf_sharpes],
            "split_h1": round(avg_h1, 3), "split_h2": round(avg_h2, 3),
            "corr_012": corr_012, "corr_076": corr_076,
            "neighbor_pct": neighbor_pct,
            "reason": reason,
        })

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    confirmed = [s for s in all_summaries if s["status"] == "CONFIRMED"]
    rejected = [s for s in all_summaries if s["status"] == "REJECTED"]
    failed = [s for s in all_summaries if s["status"] == "FAILED"]

    print(f"\nCONFIRMED: {len(confirmed)}")
    for s in confirmed:
        print(f"  {s['id']}: {s['name']} — {s['best_dir']} IS {s['is_pct']:.0f}%, "
              f"WF {s['wf_pos']}/{s['wf_total']} mean {s['wf_mean']:.3f}, "
              f"Sharpe {s['best_sharpe']:.3f}, corr H-012 {s['corr_012']:.3f}")

    print(f"\nREJECTED: {len(rejected)}")
    for s in rejected:
        r = s.get("reason", s.get("is_pct", "?"))
        print(f"  {s['id']}: {s['name']} — {r}")

    if failed:
        print(f"\nFAILED: {len(failed)}")
        for s in failed:
            print(f"  {s['id']}: {s['name']} — {s['reason']}")


if __name__ == "__main__":
    main()
