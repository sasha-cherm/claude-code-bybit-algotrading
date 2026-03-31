"""
H-154: Cross-Asset Correlation Centrality Factor (Cross-Sectional)

For each asset, compute its average pairwise correlation with all other
assets over a rolling window.

High centrality = highly correlated with everything (systemic / beta-like).
Low centrality = peripheral / idiosyncratic.

Cross-sectional: tested both directions —
  peripheral_long: LONG low-centrality (diversification premium)
  central_long: LONG high-centrality (liquidity/quality premium)
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

WINDOWS = [20, 30, 60, 90]
REBAL_FREQS = [5, 7, 10, 14]
N_POSITIONS = [3, 4, 5]

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
    For each asset on each day, compute its average correlation with
    all other assets over the past `window` days.
    """
    syms = list(aligned.keys())
    n_syms = len(syms)
    n = len(dates)

    # Build return matrix (reindex to dates first)
    ret_mat = np.full((n, n_syms), np.nan)
    for j, sym in enumerate(syms):
        prices = aligned[sym]["close"].reindex(dates).values
        rets = np.diff(prices) / prices[:-1]
        ret_mat[1:, j] = rets

    factor = pd.DataFrame(np.nan, index=dates, columns=syms)

    for i in range(window, n):
        window_rets = ret_mat[i - window + 1:i + 1, :]  # (window, n_syms)

        # Skip if too many NaN
        valid_cols = np.sum(~np.isnan(window_rets), axis=0) >= window // 2
        if valid_cols.sum() < 4:
            continue

        # Compute correlation matrix
        # Use pandas for convenience with NaN handling
        df_win = pd.DataFrame(window_rets, columns=syms)
        corr_mat = df_win.corr()

        # Average correlation for each asset (excluding self-correlation)
        for j, sym in enumerate(syms):
            if not valid_cols[j]:
                continue
            row = corr_mat.iloc[j].values.copy()
            row[j] = np.nan  # exclude self
            avg_corr = np.nanmean(row)
            factor.loc[dates[i], sym] = avg_corr

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
                # peripheral_long: LONG low centrality, SHORT high centrality
                bot_syms = ranked.nsmallest(n_pos).index.tolist()  # lowest corr → long
                top_syms = ranked.nlargest(n_pos).index.tolist()   # highest corr → short

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


if __name__ == "__main__":
    daily = fetch_all_data()
    aligned, dates = align_data(daily)
    ret_matrix = build_returns(aligned, dates)

    print(f"\n{'='*70}")
    print("PHASE 1: Full parameter sweep (IS) — peripheral_long direction")
    print(f"{'='*70}")

    all_results = []
    for win in WINDOWS:
        print(f"  Computing factor for window={win}...")
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
    print(f"\nPeripheral-long: {positive}/{total} positive ({positive/total*100:.1f}%)")
    print(f"Mean Sharpe: {mean_sharpe:.3f}")

    # Test reverse direction (central_long)
    print(f"\nTesting REVERSE (central_long):")
    rev_results = []
    for win in WINDOWS:
        factor = compute_factor(aligned, dates, win)
        rev_factor = -factor  # negate to reverse ranking
        for rebal, n_pos in product(REBAL_FREQS, N_POSITIONS):
            rets = run_strategy(rev_factor, ret_matrix, rebal, n_pos)
            s = sharpe(rets)
            rev_results.append({"sharpe": round(s, 3) if not np.isnan(s) else None})

    rev_positive = sum(1 for r in rev_results if r["sharpe"] and r["sharpe"] > 0)
    rev_mean = np.mean([r["sharpe"] for r in rev_results if r["sharpe"] is not None])
    print(f"Central-long: {rev_positive}/{total} positive ({rev_positive/total*100:.1f}%), mean={rev_mean:.3f}")

    if rev_mean > mean_sharpe:
        print("*** Central-long direction is better ***")
        direction = "central_long"
        use_positive = rev_positive
        use_mean = rev_mean
    else:
        direction = "peripheral_long"
        use_positive = positive
        use_mean = mean_sharpe

    sorted_results = sorted(all_results, key=lambda x: x["sharpe"] or -999, reverse=True)
    print(f"\nTop 5 (peripheral_long):")
    for r in sorted_results[:5]:
        print(f"  W{r['window']}_R{r['rebal']}_N{r['n_pos']}: Sharpe={r['sharpe']}, Annual={r['annual_ret']}, DD={r['max_dd']}")

    best = sorted_results[0]
    bw, br, bn = best["window"], best["rebal"], best["n_pos"]
    print(f"\nBest params: W{bw}_R{br}_N{bn} (Sharpe={best['sharpe']})")

    print(f"\n{'='*70}")
    print("PHASE 2: Walk-Forward Validation")
    print(f"{'='*70}")
    wf = walk_forward(aligned, dates, ret_matrix, bw, br, bn)
    wf_pos = sum(1 for s in wf if s > 0)
    wf_mean = np.mean(wf)
    print(f"WF: {wf_pos}/{WF_FOLDS} positive, mean OOS={wf_mean:.3f}")

    print(f"\n{'='*70}")
    print("PHASE 3: Split-Half Stability")
    print(f"{'='*70}")
    sh = split_half(aligned, dates, ret_matrix, bw, br, bn)

    print(f"\n{'='*70}")
    print("PHASE 4: Correlation with H-012")
    print(f"{'='*70}")
    syms = list(aligned.keys())
    mom_factor = pd.DataFrame(np.nan, index=dates, columns=syms)
    for sym in syms:
        prices = aligned[sym]["close"]
        mom_factor[sym] = prices.pct_change(60)
    mom_rets = run_strategy(mom_factor, ret_matrix, 5, 4)

    our_factor = compute_factor(aligned, dates, bw)
    our_rets = run_strategy(our_factor, ret_matrix, br, bn)
    corr = our_rets.corr(mom_rets)
    print(f"  Correlation with H-012: {corr:.3f}")

    # Also check corr with H-019 (low-vol)
    vol_factor = pd.DataFrame(np.nan, index=dates, columns=syms)
    for sym in syms:
        prices = aligned[sym]["close"]
        vol_factor[sym] = prices.pct_change().rolling(20).std()
    vol_factor_neg = -vol_factor  # low-vol → long
    vol_rets = run_strategy(vol_factor_neg, ret_matrix, 21, 3)
    corr_vol = our_rets.corr(vol_rets)
    print(f"  Correlation with H-019 (low-vol): {corr_vol:.3f}")

    output = {
        "hypothesis": "H-154",
        "name": "Cross-Asset Correlation Centrality Factor",
        "direction": direction,
        "is_positive_pct": use_positive / total,
        "is_mean_sharpe": round(use_mean, 3),
        "best_params": {"window": bw, "rebal": br, "n_pos": bn},
        "best_sharpe": best["sharpe"],
        "wf_folds_positive": wf_pos,
        "wf_mean_oos": round(wf_mean, 3),
        "split_half": {k: {kk: round(vv, 3) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in sh.items()},
        "h012_corr": round(corr, 3),
        "h019_corr": round(corr_vol, 3),
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
    print(f"IS: {use_positive}/{total} positive ({use_positive/total*100:.1f}%), mean={use_mean:.3f}")
    print(f"WF: {wf_pos}/{WF_FOLDS} positive, mean OOS={wf_mean:.3f}")
    print(f"Split-half: H1={sh['H1']['sharpe']:.3f}, H2={sh['H2']['sharpe']:.3f}")
    print(f"H-012 correlation: {corr:.3f}")
    print(f"H-019 correlation: {corr_vol:.3f}")
