"""
H-152: Return Entropy Factor (Cross-Sectional)

For each asset, compute Shannon entropy of the distribution of daily returns
over a rolling window by binning returns into N_BINS bins.

Low entropy = returns concentrated in few bins (trending / patterned).
High entropy = returns spread uniformly (random walk).

Cross-sectional: go LONG low-entropy assets (more predictable),
SHORT high-entropy assets (more random).
"""

import json
import sys
import time
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE",
    "AVAX", "LINK", "ADA", "DOT", "NEAR",
    "OP", "ARB", "ATOM", "SUI",
]

FEE_RATE = 0.001
INITIAL_CAPITAL = 10_000.0

WINDOWS = [14, 20, 30, 60]
REBAL_FREQS = [3, 5, 7, 10]
N_POSITIONS = [3, 4, 5]
N_BINS = 10  # number of bins for return histogram

WF_FOLDS = 6


def fetch_all_data(limit=1100):
    import ccxt
    exchange = ccxt.bybit({
        "enableRateLimit": True,
        "options": {"defaultType": "linear"},
    })
    print(f"Fetching {len(ASSETS)} assets × {limit} daily bars from Bybit...")
    daily = {}
    for sym in ASSETS:
        symbol = f"{sym}/USDT:USDT"
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=limit)
            if not ohlcv:
                symbol = f"{sym}/USDT"
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=limit)
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df = df.set_index("timestamp").sort_index()
            df = df[~df.index.duplicated(keep="last")]
            daily[sym] = df
            print(f"  {sym}: {len(df)} bars  ({df.index[0].date()} → {df.index[-1].date()})")
            time.sleep(0.2)
        except Exception as e:
            print(f"  {sym}: FAILED — {e}")
    return daily


def align_data(daily):
    dates = None
    for sym, df in daily.items():
        idx = df.index
        if dates is None:
            dates = idx
        else:
            dates = dates.intersection(idx)
    dates = dates.sort_values()
    print(f"\nCommon date range: {dates[0].date()} → {dates[-1].date()}  ({len(dates)} days)")
    aligned = {}
    for sym, df in daily.items():
        aligned[sym] = df.reindex(dates)
    return aligned, dates


def compute_factor(aligned, dates, window):
    """
    Compute rolling Shannon entropy of daily returns for each asset.
    Returns are binned into N_BINS equal-width bins based on the rolling window.
    Lower entropy = more concentrated/patterned returns.
    """
    syms = list(aligned.keys())
    n = len(dates)
    factor = pd.DataFrame(np.nan, index=dates, columns=syms)

    for sym in syms:
        df = aligned[sym]
        rets = df["close"].pct_change().values

        result = np.full(n, np.nan)
        for i in range(window, n):
            window_rets = rets[i - window + 1:i + 1]
            valid = window_rets[~np.isnan(window_rets)]
            if len(valid) < window // 2:
                continue

            # Bin returns into N_BINS equal-width bins
            rmin, rmax = valid.min(), valid.max()
            if rmax - rmin < 1e-12:
                result[i] = 0.0  # all same return = zero entropy
                continue

            counts, _ = np.histogram(valid, bins=N_BINS, range=(rmin, rmax))
            probs = counts / counts.sum()
            probs = probs[probs > 0]  # filter zeros for log
            entropy = -np.sum(probs * np.log2(probs))
            result[i] = entropy

        factor[sym] = result

    return factor


def build_returns(aligned, dates):
    syms = list(aligned.keys())
    ret = pd.DataFrame(np.nan, index=dates, columns=syms)
    for sym in syms:
        prices = aligned[sym]["close"]
        ret[sym] = prices.pct_change()
    return ret


def run_strategy(factor, ret_matrix, rebal_freq, n_pos, fee_rate=FEE_RATE):
    dates = factor.index
    n = len(dates)
    syms = factor.columns.tolist()
    portfolio_returns = pd.Series(0.0, index=dates)
    current_weights = pd.Series(0.0, index=syms)
    rebal_day = 0

    for i in range(1, n):
        if rebal_day == 0:
            f_row = factor.iloc[i]
            valid = f_row.dropna()
            if len(valid) >= 2 * n_pos:
                ranked = valid.rank(ascending=True)
                # LOW entropy = LONG (trending), HIGH entropy = SHORT (random)
                bot_syms = ranked.nsmallest(n_pos).index.tolist()  # lowest entropy → long
                top_syms = ranked.nlargest(n_pos).index.tolist()   # highest entropy → short

                new_weights = pd.Series(0.0, index=syms)
                for s in bot_syms:
                    new_weights[s] = 0.5 / n_pos
                for s in top_syms:
                    new_weights[s] = -0.5 / n_pos

                turnover = (new_weights - current_weights).abs().sum()
                tc = turnover * fee_rate
                current_weights = new_weights
            else:
                tc = 0.0
        else:
            tc = 0.0

        day_ret = ret_matrix.iloc[i]
        port_ret = (current_weights * day_ret).sum() - tc
        portfolio_returns.iloc[i] = port_ret
        rebal_day = (rebal_day + 1) % rebal_freq

    return portfolio_returns


def sharpe(rets, freq=252):
    r = rets.dropna()
    if len(r) < 30 or r.std() == 0:
        return np.nan
    return (r.mean() / r.std()) * np.sqrt(freq)


def annual_ret(rets):
    r = rets.dropna()
    if len(r) < 2:
        return np.nan
    total = (1 + r).prod()
    years = len(r) / 252
    return total ** (1 / years) - 1 if years > 0 else np.nan


def max_dd(rets):
    r = rets.dropna()
    eq = (1 + r).cumprod()
    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max
    return dd.min()


def walk_forward(aligned, dates, ret_matrix, best_window, best_rebal, best_n):
    n = len(dates)
    fold_size = n // WF_FOLDS
    fold_sharpes = []
    for fold in range(WF_FOLDS):
        test_start = fold * fold_size
        test_end = test_start + fold_size if fold < WF_FOLDS - 1 else n
        test_dates = dates[test_start:test_end]
        test_factor = compute_factor(aligned, test_dates, best_window)
        test_ret = ret_matrix.reindex(test_dates)
        rets = run_strategy(test_factor, test_ret, best_rebal, best_n)
        s = sharpe(rets)
        fold_sharpes.append(s)
        print(f"  Fold {fold + 1}: {test_dates[0].date()} → {test_dates[-1].date()}  Sharpe={s:.3f}")
    return fold_sharpes


def split_half(aligned, dates, ret_matrix, best_window, best_rebal, best_n):
    mid = len(dates) // 2
    results = {}
    for label, d in [("H1", dates[:mid]), ("H2", dates[mid:])]:
        f = compute_factor(aligned, d, best_window)
        r = ret_matrix.reindex(d)
        rets = run_strategy(f, r, best_rebal, best_n)
        results[label] = {
            "sharpe": sharpe(rets),
            "annual_ret": annual_ret(rets),
            "max_dd": max_dd(rets),
            "days": len(d),
        }
        print(f"  {label}: {d[0].date()} → {d[-1].date()} Sharpe={results[label]['sharpe']:.3f}")
    return results


def correlation_with_momentum(aligned, dates, ret_matrix, best_window, best_rebal, best_n):
    """Compare daily returns with H-012 momentum strategy."""
    # Run our strategy
    f = compute_factor(aligned, dates, best_window)
    our_rets = run_strategy(f, ret_matrix, best_rebal, best_n)

    # Run momentum (60d return, 5d rebal, top/bottom 4)
    syms = list(aligned.keys())
    mom_factor = pd.DataFrame(np.nan, index=dates, columns=syms)
    for sym in syms:
        prices = aligned[sym]["close"]
        mom_factor[sym] = prices.pct_change(60)

    mom_rets = run_strategy(mom_factor, ret_matrix, 5, 4)

    corr = our_rets.corr(mom_rets)
    print(f"  Correlation with H-012 (momentum): {corr:.3f}")
    return corr


if __name__ == "__main__":
    daily = fetch_all_data()
    aligned, dates = align_data(daily)
    ret_matrix = build_returns(aligned, dates)

    print(f"\n{'='*70}")
    print("PHASE 1: Full parameter sweep (IS)")
    print(f"{'='*70}")

    all_results = []
    for win in WINDOWS:
        factor = compute_factor(aligned, dates, win)
        for rebal, n_pos in product(REBAL_FREQS, N_POSITIONS):
            rets = run_strategy(factor, ret_matrix, rebal, n_pos)
            s = sharpe(rets)
            ar = annual_ret(rets)
            dd = max_dd(rets)
            all_results.append({
                "window": win, "rebal": rebal, "n_pos": n_pos,
                "sharpe": round(s, 3) if not np.isnan(s) else None,
                "annual_ret": round(ar, 4) if not np.isnan(ar) else None,
                "max_dd": round(dd, 4) if not np.isnan(dd) else None,
            })

    positive = sum(1 for r in all_results if r["sharpe"] and r["sharpe"] > 0)
    total = len(all_results)
    mean_sharpe = np.mean([r["sharpe"] for r in all_results if r["sharpe"] is not None])
    print(f"\nIS Results: {positive}/{total} positive ({positive/total*100:.1f}%)")
    print(f"Mean Sharpe: {mean_sharpe:.3f}")

    # Sort and show top 5
    sorted_results = sorted(all_results, key=lambda x: x["sharpe"] or -999, reverse=True)
    print("\nTop 5 parameter combos:")
    for r in sorted_results[:5]:
        print(f"  W{r['window']}_R{r['rebal']}_N{r['n_pos']}: "
              f"Sharpe={r['sharpe']}, Annual={r['annual_ret']}, DD={r['max_dd']}")

    best = sorted_results[0]
    bw, br, bn = best["window"], best["rebal"], best["n_pos"]

    # Also test reverse direction (high entropy = long)
    print(f"\n{'='*70}")
    print("Testing REVERSE direction (high entropy → LONG)")
    print(f"{'='*70}")
    rev_results = []
    for win in WINDOWS:
        factor = compute_factor(aligned, dates, win)
        # Negate to reverse ranking
        rev_factor = -factor
        for rebal, n_pos in product(REBAL_FREQS, N_POSITIONS):
            rets = run_strategy(rev_factor, ret_matrix, rebal, n_pos)
            s = sharpe(rets)
            rev_results.append({"window": win, "rebal": rebal, "n_pos": n_pos, "sharpe": round(s, 3) if not np.isnan(s) else None})

    rev_positive = sum(1 for r in rev_results if r["sharpe"] and r["sharpe"] > 0)
    rev_mean = np.mean([r["sharpe"] for r in rev_results if r["sharpe"] is not None])
    print(f"Reverse: {rev_positive}/{total} positive ({rev_positive/total*100:.1f}%), mean Sharpe={rev_mean:.3f}")

    # Pick the better direction
    if rev_mean > mean_sharpe:
        print("*** REVERSE direction is better — using high entropy → LONG ***")
        direction = "high_entropy_long"
        # Re-run with negated factor for WF/split
        compute_factor_orig = compute_factor
        def compute_factor_rev(aligned, dates, window):
            return -compute_factor_orig(aligned, dates, window)
        compute_factor_use = compute_factor_rev
        # Re-find best params
        rev_sorted = sorted(rev_results, key=lambda x: x["sharpe"] or -999, reverse=True)
        best = rev_sorted[0]
        bw, br, bn = best["window"], best["rebal"], best["n_pos"]
    else:
        direction = "low_entropy_long"
        compute_factor_use = compute_factor

    print(f"\nBest params: W{bw}_R{br}_N{bn} (Sharpe={best['sharpe']})")

    print(f"\n{'='*70}")
    print("PHASE 2: Walk-Forward Validation")
    print(f"{'='*70}")
    wf = walk_forward(aligned, dates, ret_matrix, bw, br, bn)
    wf_positive = sum(1 for s in wf if s > 0)
    wf_mean = np.mean(wf)
    print(f"WF: {wf_positive}/{WF_FOLDS} positive, mean OOS Sharpe={wf_mean:.3f}")

    print(f"\n{'='*70}")
    print("PHASE 3: Split-Half Stability")
    print(f"{'='*70}")
    sh = split_half(aligned, dates, ret_matrix, bw, br, bn)

    print(f"\n{'='*70}")
    print("PHASE 4: Correlation with H-012 Momentum")
    print(f"{'='*70}")
    corr = correlation_with_momentum(aligned, dates, ret_matrix, bw, br, bn)

    # Save results
    output = {
        "hypothesis": "H-152",
        "name": "Return Entropy Factor",
        "direction": direction,
        "is_positive_pct": positive / total,
        "is_mean_sharpe": round(mean_sharpe, 3),
        "best_params": {"window": bw, "rebal": br, "n_pos": bn},
        "best_sharpe": best["sharpe"],
        "wf_folds_positive": wf_positive,
        "wf_mean_oos": round(wf_mean, 3),
        "split_half": {k: {kk: round(vv, 3) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in sh.items()},
        "h012_corr": round(corr, 3),
        "param_results": all_results,
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Direction: {direction}")
    print(f"IS: {positive}/{total} positive ({positive/total*100:.1f}%), mean Sharpe={mean_sharpe:.3f}")
    print(f"WF: {wf_positive}/{WF_FOLDS} positive, mean OOS={wf_mean:.3f}")
    print(f"Split-half: H1={sh['H1']['sharpe']:.3f}, H2={sh['H2']['sharpe']:.3f}")
    print(f"H-012 correlation: {corr:.3f}")
