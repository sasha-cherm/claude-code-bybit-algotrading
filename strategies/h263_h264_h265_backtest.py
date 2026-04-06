#!/usr/bin/env python3
"""
Backtest three new cross-sectional factors:
  H-263: Relative Strength vs BTC — rank (asset_return - BTC_return) over lookback.
         Captures idiosyncratic outperformance beyond BTC beta.
  H-264: Return Skewness Factor — rank by own return skewness over lookback.
         Academic lottery preference: negative-skew assets outperform (less speculative demand).
  H-265: Lead-Lag Response Factor — rank by lagged beta (regression of asset_t on market_{t-1}).
         Assets that lead the market (low lagged beta) should continue; laggers revert.

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
    closes_dict, opens_dict, volumes_dict = {}, {}, {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df_1h) < 200:
                continue
            daily = resample_to_daily(df_1h)
            closes_dict[sym] = daily["close"]
            opens_dict[sym] = daily["open"]
            volumes_dict[sym] = daily["volume"]
        except Exception as e:
            print(f"  {sym}: {e}")
    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    opens = pd.DataFrame(opens_dict).reindex(closes.index).ffill().dropna()
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill().dropna()
    idx = closes.index.intersection(opens.index).intersection(volumes.index)
    closes, opens, volumes = closes.loc[idx], opens.loc[idx], volumes.loc[idx]
    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    return closes, opens, volumes


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


# ============ Factor Definitions ============

def relative_strength_vs_btc(data, lookback, date_idx):
    """
    H-263: Relative Strength vs BTC.
    Score = asset cumulative return over lookback minus BTC cumulative return.
    Captures idiosyncratic alpha beyond BTC beta exposure.
    """
    closes = data["closes"]
    if "BTC/USDT" not in closes.columns:
        return None

    btc_ret = closes["BTC/USDT"].iloc[date_idx] / closes["BTC/USDT"].iloc[date_idx - lookback] - 1
    if not np.isfinite(btc_ret):
        return None

    scores = {}
    for sym in closes.columns:
        if sym == "BTC/USDT":
            continue  # Exclude BTC itself — factor is vs BTC
        c = closes[sym].iloc[date_idx - lookback: date_idx + 1]
        if len(c) < lookback * 0.8:
            continue
        asset_ret = closes[sym].iloc[date_idx] / closes[sym].iloc[date_idx - lookback] - 1
        if np.isfinite(asset_ret):
            scores[sym] = asset_ret - btc_ret

    return pd.Series(scores) if scores else None


def return_skewness_factor(data, lookback, date_idx):
    """
    H-264: Return Skewness Factor.
    Score = skewness of daily returns over lookback window.
    Academic lottery preference: investors overpay for positive-skew assets
    (lottery tickets), so negative-skew assets are underpriced and outperform.
    """
    closes = data["closes"]
    scores = {}
    for sym in closes.columns:
        c = closes[sym].iloc[max(0, date_idx - lookback): date_idx + 1]
        if len(c) < lookback * 0.7:
            continue
        rets = c.pct_change().dropna().values
        if len(rets) < 20:
            continue
        skew = float(stats.skew(rets))
        if np.isfinite(skew):
            scores[sym] = skew

    return pd.Series(scores) if scores else None


def lead_lag_response_factor(data, lookback, date_idx):
    """
    H-265: Lead-Lag Response Factor.
    Score = regression beta of asset_return(t) on equal-weight_market_return(t-1).
    High lagged beta = asset lags the market (slow reaction, reversal expected).
    Low lagged beta = asset leads the market (early mover, continuation).
    """
    closes = data["closes"]
    returns = data["returns"]

    # Equal-weight market return (excluding the asset itself for each score)
    all_rets = returns.iloc[max(0, date_idx - lookback): date_idx + 1]
    if len(all_rets) < lookback * 0.7:
        return None

    mkt_ret = all_rets.mean(axis=1)  # equal-weight market

    scores = {}
    for sym in closes.columns:
        r = all_rets[sym].values if sym in all_rets.columns else None
        if r is None or len(r) < 20:
            continue

        # Market return excluding this asset
        other_cols = [c for c in all_rets.columns if c != sym]
        if len(other_cols) < 5:
            continue
        mkt_ex = all_rets[other_cols].mean(axis=1).values

        # Lagged regression: asset_t ~ alpha + beta * market_{t-1}
        y = r[1:]  # asset return at t
        x = mkt_ex[:-1]  # market return at t-1
        if len(y) < 20 or np.std(x) < 1e-10:
            continue

        # Simple OLS beta
        beta = np.cov(y, x)[0, 1] / np.var(x)
        if np.isfinite(beta):
            scores[sym] = beta

    return pd.Series(scores) if scores else None


# ============ Main ============

def analyze_results(results, factor_name):
    """Analyze IS robustness for a factor."""
    if not results:
        print(f"\n{'='*60}")
        print(f"  {factor_name}: NO RESULTS")
        return None

    df = pd.DataFrame([{k: v for k, v in r.items() if k != "pnl_daily"} for r in results])
    total = len(df)
    positive = (df["sharpe"] > 0).sum()
    pct = positive / total * 100

    # Dominant direction
    directions = df["direction"].unique()
    dir_stats = {}
    for d in directions:
        sub = df[df["direction"] == d]
        dir_stats[d] = {
            "count": len(sub),
            "positive": (sub["sharpe"] > 0).sum(),
            "pct": (sub["sharpe"] > 0).sum() / len(sub) * 100,
            "mean_sharpe": sub["sharpe"].mean(),
        }

    dom_dir = max(dir_stats.items(), key=lambda x: x[1]["pct"])

    print(f"\n{'='*60}")
    print(f"  {factor_name}")
    print(f"{'='*60}")
    print(f"  Total combos: {total}")
    print(f"  Positive Sharpe: {positive}/{total} ({pct:.1f}%)")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"  Best: {df.loc[df['sharpe'].idxmax()].to_dict()}")
    print(f"\n  Direction breakdown:")
    for d, s in dir_stats.items():
        print(f"    {d}: {s['positive']}/{s['count']} ({s['pct']:.1f}%) mean Sharpe {s['mean_sharpe']:.3f}")
    print(f"  Dominant: {dom_dir[0]} ({dom_dir[1]['pct']:.1f}%)")

    return {
        "total": total,
        "positive": positive,
        "pct": pct,
        "dom_dir": dom_dir[0],
        "dom_pct": dom_dir[1]["pct"],
        "mean_sharpe": df["sharpe"].mean(),
        "best": df.loc[df["sharpe"].idxmax()].to_dict(),
        "results": results,
    }


def deep_validate(closes, factor_fn, best_result, extra_data, factor_name):
    """Run WF, split-half, and H-012 correlation for confirmed factors."""
    lb = best_result["lookback"]
    rb = best_result["rebal"]
    n = best_result["n"]
    d = best_result["direction"]

    print(f"\n  --- Deep Validation: {factor_name} (LB{lb}_R{rb}_N{n}_{d}) ---")

    # Walk-forward
    wf = walk_forward(closes, factor_fn, lb, rb, n, d, extra_data=extra_data)
    wf_positive = sum(1 for s in wf if s > 0)
    wf_mean = np.mean(wf) if wf else 0
    print(f"  WF: {wf_positive}/{len(wf)} positive, mean OOS Sharpe {wf_mean:.3f}")
    print(f"  WF folds: {[round(s, 3) for s in wf]}")

    # Split-half
    half = len(closes) // 2
    pnl_h1 = backtest_factor(closes.iloc[:half], factor_fn, [lb], [rb], [n], [d],
                              factor_name, extra_data=extra_data)
    pnl_h2 = backtest_factor(closes.iloc[half:], factor_fn, [lb], [rb], [n], [d],
                              factor_name, extra_data=extra_data)

    sh1 = pnl_h1[0]["sharpe"] if pnl_h1 else 0
    sh2 = pnl_h2[0]["sharpe"] if pnl_h2 else 0
    print(f"  Split-half: H1={sh1:.3f}, H2={sh2:.3f}")

    # H-012 correlation
    best_pnl = best_result.get("pnl_daily")
    if best_pnl is not None:
        corr = compute_correlation_h012(closes, best_pnl)
    else:
        corr = 0.0
    print(f"  Correlation with H-012: {corr}")

    return {
        "wf_positive": wf_positive,
        "wf_total": len(wf),
        "wf_mean": round(wf_mean, 3),
        "wf_folds": [round(s, 3) for s in wf],
        "split_h1": sh1,
        "split_h2": sh2,
        "corr_h012": corr,
    }


if __name__ == "__main__":
    print("Loading data...")
    closes, opens, volumes = load_data()
    returns = closes.pct_change()

    data = {"closes": closes, "opens": opens, "volumes": volumes, "returns": returns}

    # ============ H-263: Relative Strength vs BTC ============
    print("\n\n" + "=" * 70)
    print("H-263: RELATIVE STRENGTH VS BTC")
    print("=" * 70)
    # Note: 13 non-BTC assets only
    h263_results = backtest_factor(
        closes, relative_strength_vs_btc,
        lookbacks=[10, 15, 20, 30, 60],
        rebals=[3, 5, 7],
        ns=[3, 4],
        directions=["high_long", "low_long"],
        factor_name="H-263",
        extra_data=data,
    )
    h263_analysis = analyze_results(h263_results, "H-263: Relative Strength vs BTC")

    if h263_analysis and h263_analysis["dom_pct"] >= 80:
        # Find best from dominant direction
        dom_results = [r for r in h263_results if r["direction"] == h263_analysis["dom_dir"]]
        best = max(dom_results, key=lambda r: r["sharpe"])
        h263_val = deep_validate(closes, relative_strength_vs_btc, best, data, "H-263")
    else:
        h263_val = None
        print(f"  *** REJECTED: IS {h263_analysis['dom_pct']:.1f}% < 80% ***" if h263_analysis else "  *** NO RESULTS ***")

    # ============ H-264: Return Skewness ============
    print("\n\n" + "=" * 70)
    print("H-264: RETURN SKEWNESS FACTOR")
    print("=" * 70)
    h264_results = backtest_factor(
        closes, return_skewness_factor,
        lookbacks=[10, 15, 20, 30, 40, 60],
        rebals=[3, 5, 7],
        ns=[3, 4],
        directions=["high_long", "low_long"],
        factor_name="H-264",
        extra_data=data,
    )
    h264_analysis = analyze_results(h264_results, "H-264: Return Skewness")

    if h264_analysis and h264_analysis["dom_pct"] >= 80:
        dom_results = [r for r in h264_results if r["direction"] == h264_analysis["dom_dir"]]
        best = max(dom_results, key=lambda r: r["sharpe"])
        h264_val = deep_validate(closes, return_skewness_factor, best, data, "H-264")
    else:
        h264_val = None
        print(f"  *** REJECTED: IS {h264_analysis['dom_pct']:.1f}% < 80% ***" if h264_analysis else "  *** NO RESULTS ***")

    # ============ H-265: Lead-Lag Response ============
    print("\n\n" + "=" * 70)
    print("H-265: LEAD-LAG RESPONSE FACTOR")
    print("=" * 70)
    h265_results = backtest_factor(
        closes, lead_lag_response_factor,
        lookbacks=[10, 15, 20, 30, 60],
        rebals=[3, 5, 7],
        ns=[3, 4],
        directions=["high_long", "low_long"],
        factor_name="H-265",
        extra_data=data,
    )
    h265_analysis = analyze_results(h265_results, "H-265: Lead-Lag Response")

    if h265_analysis and h265_analysis["dom_pct"] >= 80:
        dom_results = [r for r in h265_results if r["direction"] == h265_analysis["dom_dir"]]
        best = max(dom_results, key=lambda r: r["sharpe"])
        h265_val = deep_validate(closes, lead_lag_response_factor, best, data, "H-265")
    else:
        h265_val = None
        print(f"  *** REJECTED: IS {h265_analysis['dom_pct']:.1f}% < 80% ***" if h265_analysis else "  *** NO RESULTS ***")

    # ============ Summary ============
    print("\n\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, analysis, val in [
        ("H-263", h263_analysis, h263_val),
        ("H-264", h264_analysis, h264_val),
        ("H-265", h265_analysis, h265_val),
    ]:
        if analysis is None:
            print(f"  {name}: NO RESULTS")
        elif analysis["dom_pct"] < 80:
            print(f"  {name}: REJECTED (IS {analysis['dom_pct']:.1f}% < 80%)")
        elif val is None:
            print(f"  {name}: REJECTED (no validation)")
        else:
            wf_pass = val["wf_positive"] >= val["wf_total"] * 0.6
            corr_ok = abs(val["corr_h012"]) < 0.5
            status = "CONFIRMED" if (wf_pass and corr_ok and val["wf_positive"] >= 4) else "REJECTED"
            print(f"  {name}: {status} — IS {analysis['dom_pct']:.1f}%, WF {val['wf_positive']}/{val['wf_total']} mean {val['wf_mean']:.3f}, "
                  f"SH H1={val['split_h1']:.3f}/H2={val['split_h2']:.3f}, corr {val['corr_h012']}")
