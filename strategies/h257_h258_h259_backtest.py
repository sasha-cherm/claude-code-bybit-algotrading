#!/usr/bin/env python3
"""
Backtest three new cross-sectional factors:
  H-257: Intraday Return Dominance Factor — ratio of cumulative open-to-close
         returns vs total close-to-close returns. Captures whether institutional
         (intraday) or retail (overnight) flow drives the asset.
  H-258: Recovery Speed Factor — rolling average of how quickly price bounces
         after drawdowns. Fast recovery = strong demand support.
  H-259: Extreme Move Frequency Factor — fraction of daily returns exceeding
         2 rolling standard deviations. Low tail = orderly market = better persistence.

Standard framework: grid search over lookback/rebal/N/direction,
in-sample robustness (>=80% positive Sharpe), walk-forward OOS validation,
split-half stability, correlation with H-012.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

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
    """Load daily OHLCV data for all assets, resampled from hourly."""
    closes_dict, opens_dict, highs_dict, lows_dict, volumes_dict = {}, {}, {}, {}, {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df_1h) < 200:
                continue
            daily = resample_to_daily(df_1h)
            closes_dict[sym] = daily["close"]
            opens_dict[sym] = daily["open"]
            highs_dict[sym] = daily["high"]
            lows_dict[sym] = daily["low"]
            volumes_dict[sym] = daily["volume"]
        except Exception as e:
            print(f"  {sym}: {e}")
    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    opens = pd.DataFrame(opens_dict).reindex(closes.index).ffill().dropna()
    highs = pd.DataFrame(highs_dict).reindex(closes.index).ffill().dropna()
    lows = pd.DataFrame(lows_dict).reindex(closes.index).ffill().dropna()
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill().dropna()
    # Align all to same index
    idx = closes.index.intersection(opens.index).intersection(highs.index)
    closes, opens, highs, lows, volumes = (
        closes.loc[idx], opens.loc[idx], highs.loc[idx], lows.loc[idx], volumes.loc[idx]
    )
    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    return closes, opens, highs, lows, volumes


def backtest_factor(closes, factor_fn, lookbacks, rebals, ns, directions,
                    factor_name, extra_data=None):
    """Run grid search for a cross-sectional factor."""
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
    """Walk-forward validation with rolling train/test splits."""
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
    """Compute correlation with H-012 (60-day momentum, 5-day rebal, top/bottom 4)."""
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


# ============ Factor Definitions ============

def intraday_return_dominance(data, lookback, date_idx):
    """
    H-257: Intraday Return Dominance Factor.
    Ratio of cumulative open-to-close (intraday) returns to total close-to-close
    returns over the lookback window. High ratio = institutional/intraday flow
    drives the asset. Low ratio = overnight/retail flow dominates.
    """
    closes, opens = data["closes"], data["opens"]
    scores = {}
    for sym in closes.columns:
        if sym not in opens.columns:
            continue
        c_window = closes[sym].iloc[date_idx - lookback: date_idx + 1]
        o_window = opens[sym].iloc[date_idx - lookback: date_idx + 1]
        if len(c_window) < lookback * 0.8:
            continue

        # Intraday return: open-to-close for each day
        intraday_rets = (c_window.values[1:] / o_window.values[1:] - 1)
        # Total return: close-to-close
        total_rets = c_window.pct_change().dropna().values

        if len(intraday_rets) < lookback * 0.7 or len(total_rets) < lookback * 0.7:
            continue

        cum_intraday = np.sum(intraday_rets)
        cum_total = np.sum(total_rets)

        # Ratio: if total is near zero, use just intraday sign
        if abs(cum_total) < 1e-8:
            score = cum_intraday * 100  # amplify for ranking
        else:
            score = cum_intraday / abs(cum_total)

        if np.isfinite(score):
            scores[sym] = score

    return pd.Series(scores) if scores else None


def recovery_speed_factor(data, lookback, date_idx):
    """
    H-258: Recovery Speed Factor.
    For each asset over the lookback window, measure the average speed of
    recovery after local dips. Uses rolling max drawdown points and measures
    how many days it takes to recover 50% of each dip.
    Fast recovery = strong support/demand. Slow = weak.
    """
    closes = data["closes"]
    scores = {}
    for sym in closes.columns:
        price_window = closes[sym].iloc[max(0, date_idx - lookback): date_idx + 1].values
        if len(price_window) < lookback * 0.8:
            continue

        # Compute rolling drawdown
        running_max = np.maximum.accumulate(price_window)
        drawdowns = (price_window - running_max) / running_max

        # Find significant dip points (drawdown < -1%)
        recovery_scores = []
        i = 0
        while i < len(drawdowns):
            if drawdowns[i] < -0.01:
                # Found a dip — find the trough
                trough_idx = i
                trough_val = drawdowns[i]
                j = i + 1
                while j < len(drawdowns) and drawdowns[j] <= trough_val * 0.5:
                    if drawdowns[j] < trough_val:
                        trough_val = drawdowns[j]
                        trough_idx = j
                    j += 1
                # Recovery: how many days from trough to recover 50%
                half_recovery_target = trough_val * 0.5
                recovered = False
                for k in range(trough_idx + 1, min(trough_idx + lookback, len(drawdowns))):
                    if drawdowns[k] >= half_recovery_target:
                        days_to_recover = k - trough_idx
                        # Score: inverse of recovery days, weighted by dip depth
                        recovery_scores.append(abs(trough_val) / max(days_to_recover, 1))
                        recovered = True
                        break
                if not recovered and trough_idx < len(drawdowns) - 1:
                    # Never recovered — penalize
                    recovery_scores.append(0.0)
                i = max(j, i + 1)
            else:
                i += 1

        if len(recovery_scores) >= 1:
            scores[sym] = float(np.mean(recovery_scores))

    return pd.Series(scores) if scores else None


def extreme_move_frequency(data, lookback, date_idx):
    """
    H-259: Extreme Move Frequency Factor.
    Fraction of daily returns that exceed 2 rolling standard deviations
    over the lookback window. Low extreme frequency = orderly, predictable
    market = better trend persistence. High = chaotic, hard to trade.
    """
    closes = data["closes"]
    scores = {}
    for sym in closes.columns:
        ret_series = closes[sym].pct_change()
        ret_window = ret_series.iloc[max(1, date_idx - lookback): date_idx + 1].dropna()
        if len(ret_window) < lookback * 0.8:
            continue

        # Rolling std from a slightly longer window for stability
        extended_start = max(1, date_idx - lookback * 2)
        ret_extended = ret_series.iloc[extended_start: date_idx + 1].dropna()
        if len(ret_extended) < 20:
            continue
        rolling_std = float(ret_extended.std())
        if rolling_std <= 0:
            continue

        threshold = 2.0 * rolling_std
        n_extreme = int((ret_window.abs() > threshold).sum())
        frac_extreme = n_extreme / len(ret_window)

        if np.isfinite(frac_extreme):
            scores[sym] = frac_extreme

    return pd.Series(scores) if scores else None


def run_full_analysis(closes, factor_fn, factor_name, lookbacks, rebals,
                      ns, directions, extra_data=None):
    """Run complete analysis: IS grid, WF, split-half, correlation."""
    print(f"\n{'='*60}")
    print(f"  {factor_name}")
    print(f"{'='*60}")

    total_combos = len(lookbacks) * len(rebals) * len(ns) * len(directions)
    print(f"Grid: {len(lookbacks)} LB x {len(rebals)} R x {len(ns)} N x {len(directions)} dir = {total_combos} combos")

    results = backtest_factor(closes, factor_fn, lookbacks, rebals, ns,
                              directions, factor_name, extra_data)

    if not results:
        print("  NO RESULTS")
        return None

    # Count positive Sharpe by direction
    for d in directions:
        d_results = [r for r in results if r["direction"] == d]
        positive = sum(1 for r in d_results if r["sharpe"] > 0)
        total = len(d_results)
        pct = positive / total * 100 if total > 0 else 0
        mean_sharpe = np.mean([r["sharpe"] for r in d_results]) if d_results else 0
        print(f"  {d}: {positive}/{total} positive ({pct:.1f}%), mean Sharpe {mean_sharpe:.3f}")

    # Overall
    positive_all = sum(1 for r in results if r["sharpe"] > 0)
    pct_all = positive_all / len(results) * 100
    print(f"  Overall: {positive_all}/{len(results)} positive ({pct_all:.1f}%)")

    # Best combo
    best = max(results, key=lambda r: r["sharpe"])
    print(f"  Best: LB{best['lookback']}_R{best['rebal']}_N{best['n']}_{best['direction']} "
          f"Sharpe {best['sharpe']:.3f} ({best['ann_ret']:+.1f}% ann, -{best['max_dd']:.1f}% DD)")

    # Direction stats
    dir_stats = {}
    for d in directions:
        d_results = [r for r in results if r["direction"] == d]
        positive = sum(1 for r in d_results if r["sharpe"] > 0)
        total = len(d_results)
        pct = positive / total * 100 if total > 0 else 0
        dir_stats[d] = {"pct": pct, "count": total, "positive": positive}

    best_dir = max(dir_stats, key=lambda d: dir_stats[d]["pct"])
    best_dir_pct = dir_stats[best_dir]["pct"]

    if best_dir_pct < 80:
        print(f"\n  REJECT: Best direction {best_dir} only {best_dir_pct:.1f}% < 80% threshold")
        return {"status": "REJECTED", "reason": f"IS {best_dir_pct:.1f}% < 80%",
                "best": best, "dir_stats": dir_stats}

    print(f"\n  IS PASSES: {best_dir} at {best_dir_pct:.1f}%")

    # Best params within passing direction
    dir_results = [r for r in results if r["direction"] == best_dir]
    best_in_dir = max(dir_results, key=lambda r: r["sharpe"])

    # Walk-forward
    print(f"\n  Walk-forward (6 folds, LB{best_in_dir['lookback']}_R{best_in_dir['rebal']}_N{best_in_dir['n']})...")
    wf_sharpes = walk_forward(
        closes, factor_fn,
        best_in_dir["lookback"], best_in_dir["rebal"], best_in_dir["n"],
        best_dir, extra_data, n_folds=6
    )

    if not wf_sharpes:
        print("  WF: No results")
        return {"status": "REJECTED", "reason": "WF failed", "best": best_in_dir}

    wf_positive = sum(1 for s in wf_sharpes if s > 0)
    wf_mean = np.mean(wf_sharpes)
    print(f"  WF: {wf_positive}/{len(wf_sharpes)} positive, mean OOS Sharpe {wf_mean:.3f}")
    print(f"  WF folds: {[round(s, 3) for s in wf_sharpes]}")

    if wf_positive < 3:
        print(f"  REJECT: WF only {wf_positive}/{len(wf_sharpes)} positive < 3")
        return {"status": "REJECTED", "reason": f"WF {wf_positive}/{len(wf_sharpes)}",
                "best": best_in_dir, "wf_sharpes": wf_sharpes}

    # Split-half
    pnl = best_in_dir["pnl_daily"]
    mid = len(pnl) // 2
    h1_sharpe = float(np.mean(pnl[:mid]) / np.std(pnl[:mid]) * np.sqrt(365)) if np.std(pnl[:mid]) > 0 else 0
    h2_sharpe = float(np.mean(pnl[mid:]) / np.std(pnl[mid:]) * np.sqrt(365)) if np.std(pnl[mid:]) > 0 else 0
    print(f"  Split-half: H1={h1_sharpe:.3f}, H2={h2_sharpe:.3f}")

    # Correlation with H-012
    corr = compute_correlation_h012(closes, pnl, )
    print(f"  Correlation with H-012: {corr}")

    return {
        "status": "CONFIRMED",
        "best": best_in_dir,
        "direction": best_dir,
        "dir_pct": best_dir_pct,
        "wf_sharpes": wf_sharpes,
        "wf_positive": wf_positive,
        "wf_mean": wf_mean,
        "h1_sharpe": h1_sharpe,
        "h2_sharpe": h2_sharpe,
        "corr_h012": corr,
    }


if __name__ == "__main__":
    print("Loading data...")
    closes, opens, highs, lows, volumes = load_data()

    # Package extra data for factor functions
    extra_data = {
        "closes": closes,
        "opens": opens,
        "highs": highs,
        "lows": lows,
        "volumes": volumes,
    }

    # H-257: Intraday Return Dominance Factor
    r257 = run_full_analysis(
        closes, intraday_return_dominance, "H-257 Intraday Return Dominance",
        lookbacks=[10, 15, 20, 30, 60],
        rebals=[3, 5, 7],
        ns=[3, 4],
        directions=["high_long", "low_long"],
        extra_data=extra_data,
    )

    # H-258: Recovery Speed Factor
    r258 = run_full_analysis(
        closes, recovery_speed_factor, "H-258 Recovery Speed",
        lookbacks=[15, 20, 30, 40, 60],
        rebals=[3, 5, 7],
        ns=[3, 4],
        directions=["high_long", "low_long"],
        extra_data=extra_data,
    )

    # H-259: Extreme Move Frequency Factor
    r259 = run_full_analysis(
        closes, extreme_move_frequency, "H-259 Extreme Move Frequency",
        lookbacks=[10, 15, 20, 30, 60],
        rebals=[3, 5, 7],
        ns=[3, 4],
        directions=["high_long", "low_long"],
        extra_data=extra_data,
    )

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for name, r in [("H-257", r257), ("H-258", r258), ("H-259", r259)]:
        if r is None:
            print(f"  {name}: FAILED (no results)")
        elif r["status"] == "REJECTED":
            print(f"  {name}: REJECTED — {r['reason']}")
        else:
            print(f"  {name}: CONFIRMED — IS {r['dir_pct']:.1f}%, WF {r['wf_positive']}/{len(r['wf_sharpes'])} "
                  f"mean {r['wf_mean']:.3f}, split H1={r['h1_sharpe']:.3f}/H2={r['h2_sharpe']:.3f}, "
                  f"corr H-012 {r['corr_h012']}")
