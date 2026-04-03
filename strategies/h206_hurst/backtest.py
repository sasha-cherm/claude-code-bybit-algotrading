"""
H-206: Hurst Exponent Factor Strategy Backtest
Cross-sectional ranking on Hurst exponent (R/S method).
Long highest-H (trending) vs short lowest-H (mean-reverting), or vice versa.
"""

import json
import sys
import time
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RESULTS_PATH = Path(__file__).parent / "results.json"

ASSETS = [
    "BTC", "ETH", "SOL", "SUI", "XRP", "DOGE",
    "AVAX", "LINK", "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM",
]

# ---------------------------------------------------------------------------
# Hurst exponent via R/S method
# ---------------------------------------------------------------------------

def hurst_rs(series: np.ndarray) -> float:
    """Compute Hurst exponent using R/S analysis on a numpy array of log-returns."""
    n = len(series)
    if n < 20:
        return 0.5
    max_k = min(n // 2, n)
    # Use log-spaced subset sizes
    sizes = []
    s = 10
    while s <= max_k:
        sizes.append(s)
        s = int(s * 1.5)
    if len(sizes) < 3:
        return 0.5
    rs_values = []
    for size in sizes:
        rs_list = []
        for start in range(0, n - size + 1, max(1, size // 2)):
            subset = series[start : start + size]
            mean_sub = subset.mean()
            deviate = (subset - mean_sub).cumsum()
            R = deviate.max() - deviate.min()
            S = subset.std(ddof=1)
            if S > 0:
                rs_list.append(R / S)
        if rs_list:
            rs_values.append((np.log(size), np.log(np.mean(rs_list))))
    if len(rs_values) < 3:
        return 0.5
    x = np.array([v[0] for v in rs_values])
    y = np.array([v[1] for v in rs_values])
    slope, _ = np.polyfit(x, y, 1)
    return float(slope)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_returns() -> pd.DataFrame:
    """Load close prices for all assets, compute log-returns, align on common index."""
    prices = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        df = pd.read_parquet(fp)
        prices[asset] = df["close"]
    price_df = pd.DataFrame(prices)
    # forward-fill minor gaps, drop rows with >50% missing
    price_df = price_df.ffill().dropna(thresh=len(ASSETS) // 2)
    log_ret = np.log(price_df / price_df.shift(1))
    return log_ret  # DatetimeIndex, columns = asset names


# ---------------------------------------------------------------------------
# Hurst matrix computation
# ---------------------------------------------------------------------------

def compute_hurst_matrix(log_ret: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    For each date t (with ≥ lookback prior observations), compute Hurst
    for each asset using the log-return window [t-lookback, t-1].
    Returns DataFrame with same index as log_ret, columns = assets.
    """
    dates = log_ret.index
    n_dates = len(dates)
    hurst_vals = np.full((n_dates, len(ASSETS)), np.nan)

    for i in range(lookback, n_dates):
        window = log_ret.iloc[i - lookback : i].values  # shape (lookback, n_assets)
        for j in range(len(ASSETS)):
            col = window[:, j]
            # skip if too many NaNs
            valid = col[~np.isnan(col)]
            if len(valid) >= 20:
                hurst_vals[i, j] = hurst_rs(valid)
            else:
                hurst_vals[i, j] = 0.5

    return pd.DataFrame(hurst_vals, index=dates, columns=ASSETS)


# ---------------------------------------------------------------------------
# Backtest engine
# ---------------------------------------------------------------------------

def run_backtest(
    log_ret: pd.DataFrame,
    hurst_df: pd.DataFrame,
    lookback: int,
    rebal_period: int,
    n_top: int,
    direction: str,  # "high_hurst_long" | "low_hurst_long"
) -> pd.Series:
    """
    Simulate a market-neutral long-short portfolio.
    Rebalance every `rebal_period` days using t-1 Hurst rankings.
    Returns a daily P&L series (portfolio returns).
    """
    dates = log_ret.index
    portfolio_rets = []
    port_dates = []

    # current positions: dict asset -> weight
    current_weights = {}
    last_rebal = -999

    for i in range(lookback + 1, len(dates)):
        t = dates[i]
        days_since_rebal = i - last_rebal

        if days_since_rebal >= rebal_period:
            # Use t-1 Hurst (already computed at i-1)
            hurst_row = hurst_df.iloc[i - 1]
            valid = hurst_row.dropna()
            if len(valid) < 2 * n_top:
                # not enough valid assets to form portfolio
                current_weights = {}
            else:
                ranked = valid.sort_values(ascending=False)
                top_assets = ranked.index[:n_top].tolist()
                bot_assets = ranked.index[-n_top:].tolist()

                if direction == "high_hurst_long":
                    long_assets = top_assets
                    short_assets = bot_assets
                else:  # low_hurst_long
                    long_assets = bot_assets
                    short_assets = top_assets

                w = 1.0 / n_top
                current_weights = {}
                for a in long_assets:
                    current_weights[a] = w
                for a in short_assets:
                    current_weights[a] = -w

            last_rebal = i

        # Compute portfolio return for day t
        day_ret = 0.0
        day_ret_count = 0
        for asset, weight in current_weights.items():
            r = log_ret.loc[t, asset]
            if not np.isnan(r):
                day_ret += weight * r
                day_ret_count += 1

        if day_ret_count > 0:
            portfolio_rets.append(day_ret)
            port_dates.append(t)

    return pd.Series(portfolio_rets, index=port_dates)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def sharpe(returns: pd.Series, annualize: float = 365.0) -> float:
    if len(returns) < 10:
        return 0.0
    mu = returns.mean()
    sigma = returns.std(ddof=1)
    if sigma == 0:
        return 0.0
    return float(mu / sigma * np.sqrt(annualize))


def max_drawdown(returns: pd.Series) -> float:
    cum = (1 + returns).cumprod()
    roll_max = cum.cummax()
    dd = (cum - roll_max) / roll_max
    return float(dd.min())


def annual_return(returns: pd.Series) -> float:
    if len(returns) < 2:
        return 0.0
    cum = (1 + returns).prod()
    n_years = len(returns) / 365.0
    return float(cum ** (1 / n_years) - 1)


# ---------------------------------------------------------------------------
# Parameter grid
# ---------------------------------------------------------------------------

LOOKBACKS = [10, 20, 30, 40, 60]
REBAL_PERIODS = [3, 5, 7]
N_TOPS = [3, 4]
DIRECTIONS = ["high_hurst_long", "low_hurst_long"]


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------

def walk_forward(
    log_ret: pd.DataFrame,
    lookback: int,
    rebal_period: int,
    n_top: int,
    direction: str,
    n_folds: int = 6,
    fold_days: int = 90,
) -> list:
    """
    Walk-forward: for each of n_folds test windows (fold_days each),
    train on all data prior to the test window, evaluate OOS Sharpe.
    Returns list of OOS Sharpe per fold.
    """
    dates = log_ret.index
    total_days = len(dates)
    test_total = n_folds * fold_days

    if total_days < lookback + test_total + fold_days:
        return []

    fold_sharpes = []
    for fold in range(n_folds):
        # test window: last n_folds windows
        test_end_idx = total_days - fold * fold_days
        test_start_idx = test_end_idx - fold_days
        if test_start_idx <= lookback:
            break

        test_ret = log_ret.iloc[test_start_idx:test_end_idx]
        train_ret = log_ret.iloc[:test_start_idx]

        # Compute Hurst on train data
        hurst_train = compute_hurst_matrix(train_ret, lookback)

        # We need Hurst values for days just before the test window to initialize
        # positions, plus we carry positions into the test window.
        # Approach: compute Hurst on full slice up to test_start_idx
        hurst_full = compute_hurst_matrix(log_ret.iloc[:test_end_idx], lookback)

        # Run backtest on test slice only (but use hurst from full up to that point)
        test_log_full = log_ret.iloc[:test_end_idx]
        rets = run_backtest_slice(
            test_log_full, hurst_full, lookback, rebal_period, n_top, direction,
            start_idx=test_start_idx,
        )
        fold_sharpes.append(sharpe(rets))

    return fold_sharpes


def run_backtest_slice(
    log_ret: pd.DataFrame,
    hurst_df: pd.DataFrame,
    lookback: int,
    rebal_period: int,
    n_top: int,
    direction: str,
    start_idx: int,
) -> pd.Series:
    """Like run_backtest but only generates returns from start_idx onwards."""
    dates = log_ret.index
    portfolio_rets = []
    port_dates = []

    current_weights = {}
    last_rebal = -999

    # Scan from lookback+1 to build up position state before start_idx
    for i in range(lookback + 1, len(dates)):
        t = dates[i]
        days_since_rebal = i - last_rebal

        if days_since_rebal >= rebal_period:
            hurst_row = hurst_df.iloc[i - 1]
            valid = hurst_row.dropna()
            if len(valid) < 2 * n_top:
                current_weights = {}
            else:
                ranked = valid.sort_values(ascending=False)
                top_assets = ranked.index[:n_top].tolist()
                bot_assets = ranked.index[-n_top:].tolist()

                if direction == "high_hurst_long":
                    long_assets = top_assets
                    short_assets = bot_assets
                else:
                    long_assets = bot_assets
                    short_assets = top_assets

                w = 1.0 / n_top
                current_weights = {}
                for a in long_assets:
                    current_weights[a] = w
                for a in short_assets:
                    current_weights[a] = -w

            last_rebal = i

        if i >= start_idx:
            day_ret = 0.0
            day_ret_count = 0
            for asset, weight in current_weights.items():
                r = log_ret.loc[t, asset]
                if not np.isnan(r):
                    day_ret += weight * r
                    day_ret_count += 1

            if day_ret_count > 0:
                portfolio_rets.append(day_ret)
                port_dates.append(t)

    return pd.Series(portfolio_rets, index=port_dates)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    print("=" * 60)
    print("H-206: Hurst Exponent Factor Backtest")
    print("=" * 60)

    print("\nLoading data...")
    log_ret = load_returns()
    print(f"  Date range: {log_ret.index[0].date()} to {log_ret.index[-1].date()}")
    print(f"  Total days: {len(log_ret)}, Assets: {len(ASSETS)}")

    # Pre-compute Hurst matrices for each lookback (avoid recomputing per combo)
    print("\nPre-computing Hurst matrices for each lookback window...")
    hurst_matrices = {}
    for lb in LOOKBACKS:
        print(f"  Lookback={lb}...", end=" ", flush=True)
        t1 = time.time()
        hurst_matrices[lb] = compute_hurst_matrix(log_ret, lb)
        print(f"done ({time.time()-t1:.1f}s)")

    # Parameter grid sweep
    print("\nRunning parameter grid sweep...")
    combos = list(product(LOOKBACKS, REBAL_PERIODS, N_TOPS, DIRECTIONS))
    print(f"  Total combinations: {len(combos)}")

    results = []
    for idx, (lb, rp, nt, dr) in enumerate(combos):
        if idx % 20 == 0:
            print(f"  [{idx+1}/{len(combos)}] lb={lb} rp={rp} N={nt} dir={dr[:4]}")
        rets = run_backtest(log_ret, hurst_matrices[lb], lb, rp, nt, dr)
        sp = sharpe(rets)
        mdd = max_drawdown(rets)
        ar = annual_return(rets)
        results.append({
            "lookback": lb,
            "rebal_period": rp,
            "n_top": nt,
            "direction": dr,
            "sharpe": round(sp, 4),
            "annual_return": round(ar, 4),
            "max_drawdown": round(mdd, 4),
            "n_days": len(rets),
        })

    # Analyse IS results
    sharpes = [r["sharpe"] for r in results]
    positive = [s > 0 for s in sharpes]
    hit_rate = sum(positive) / len(positive)

    best = max(results, key=lambda x: x["sharpe"])
    mean_sharpe = float(np.mean(sharpes))

    dir_high = [r["sharpe"] for r in results if r["direction"] == "high_hurst_long"]
    dir_low  = [r["sharpe"] for r in results if r["direction"] == "low_hurst_long"]
    mean_high = float(np.mean(dir_high))
    mean_low  = float(np.mean(dir_low))
    dom_direction = "high_hurst_long" if mean_high >= mean_low else "low_hurst_long"

    print("\n" + "=" * 60)
    print("IN-SAMPLE RESULTS")
    print("=" * 60)
    print(f"  Hit rate (Sharpe > 0): {hit_rate:.1%}  ({sum(positive)}/{len(positive)} combos)")
    print(f"  Mean Sharpe:           {mean_sharpe:.4f}")
    print(f"  Best Sharpe:           {best['sharpe']:.4f}")
    print(f"  Best params:           lb={best['lookback']} rp={best['rebal_period']} N={best['n_top']} {best['direction']}")
    print(f"  Best annual return:    {best['annual_return']:.2%}")
    print(f"  Best max drawdown:     {best['max_drawdown']:.2%}")
    print(f"  Mean Sharpe high_H_L:  {mean_high:.4f}")
    print(f"  Mean Sharpe low_H_L:   {mean_low:.4f}")
    print(f"  Dominant direction:    {dom_direction}")

    # Sort and show top 10 combos
    top10 = sorted(results, key=lambda x: x["sharpe"], reverse=True)[:10]
    print("\n  Top-10 parameter combos:")
    print(f"  {'lb':>4} {'rp':>4} {'N':>3} {'dir':>18} {'sharpe':>8} {'ann_ret':>8} {'mdd':>8}")
    for r in top10:
        print(f"  {r['lookback']:>4} {r['rebal_period']:>4} {r['n_top']:>3} {r['direction']:>18} {r['sharpe']:>8.4f} {r['annual_return']:>8.2%} {r['max_drawdown']:>8.2%}")

    # Walk-forward validation
    wf_result = None
    wf_needed = hit_rate >= 0.80

    if wf_needed:
        print(f"\n  IS hit rate {hit_rate:.1%} >= 80% — running walk-forward validation...")
        # Use best params
        lb_best = best["lookback"]
        rp_best = best["rebal_period"]
        nt_best = best["n_top"]
        dr_best = best["direction"]

        fold_sharpes = walk_forward(
            log_ret, lb_best, rp_best, nt_best, dr_best,
            n_folds=6, fold_days=90,
        )

        if len(fold_sharpes) == 0:
            print("  Walk-forward: not enough data for 6 folds.")
            wf_pass = False
        else:
            wf_positive = sum(s > 0 for s in fold_sharpes)
            wf_pass = wf_positive >= 4
            wf_mean = float(np.mean(fold_sharpes))
            print("\n  Walk-Forward Results:")
            print(f"  {'Fold':>5} {'OOS Sharpe':>12}")
            for fi, fs in enumerate(fold_sharpes):
                flag = "+" if fs > 0 else "-"
                print(f"  {fi+1:>5}  {fs:>10.4f}  {flag}")
            print(f"\n  Folds positive: {wf_positive}/{len(fold_sharpes)}")
            print(f"  Mean OOS Sharpe: {wf_mean:.4f}")
            print(f"  WF PASS: {wf_pass} (need >= 4/6 positive)")

        wf_result = {
            "fold_sharpes": [round(s, 4) for s in fold_sharpes],
            "folds_positive": sum(s > 0 for s in fold_sharpes),
            "folds_total": len(fold_sharpes),
            "wf_pass": wf_pass,
            "mean_oos_sharpe": round(float(np.mean(fold_sharpes)) if fold_sharpes else 0.0, 4),
        }
    else:
        print(f"\n  IS hit rate {hit_rate:.1%} < 80% — walk-forward NOT run.")
        wf_pass = False

    # Split-half stability (only if WF passes)
    split_half = None
    if wf_result and wf_result.get("wf_pass"):
        print("\n  Running split-half stability test...")
        mid = len(log_ret) // 2
        h1_ret = log_ret.iloc[:mid]
        h2_ret = log_ret.iloc[mid:]

        lb_best = best["lookback"]
        rp_best = best["rebal_period"]
        nt_best = best["n_top"]
        dr_best = best["direction"]

        hm1 = compute_hurst_matrix(h1_ret, lb_best)
        hm2 = compute_hurst_matrix(h2_ret, lb_best)

        rets_h1 = run_backtest(h1_ret, hm1, lb_best, rp_best, nt_best, dr_best)
        rets_h2 = run_backtest(h2_ret, hm2, lb_best, rp_best, nt_best, dr_best)

        sh1 = sharpe(rets_h1)
        sh2 = sharpe(rets_h2)
        print(f"  First half Sharpe:  {sh1:.4f}")
        print(f"  Second half Sharpe: {sh2:.4f}")
        stability_pass = sh1 > 0 and sh2 > 0

        # Correlation with H-012 momentum signals (if available)
        h012_corr = None
        h012_path = ROOT / "strategies" / "h012_xsmom" / "results.json"
        if h012_path.exists():
            try:
                with open(h012_path) as f:
                    h012_data = json.load(f)
                print(f"  H-012 result file found: {h012_path}")
            except Exception:
                pass

        split_half = {
            "h1_sharpe": round(sh1, 4),
            "h2_sharpe": round(sh2, 4),
            "stability_pass": stability_pass,
            "h012_correlation": h012_corr,
        }

    # Summary verdict
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)
    if hit_rate >= 0.80 and wf_result and wf_result.get("wf_pass"):
        verdict = "CONFIRMED"
        print(f"  CONFIRMED — IS hit rate {hit_rate:.1%}, WF passes {wf_result['folds_positive']}/{wf_result['folds_total']}")
    elif hit_rate >= 0.80 and not wf_needed:
        verdict = "MARGINAL"
        print(f"  WF not triggered (hit rate {hit_rate:.1%})")
    elif hit_rate >= 0.60:
        verdict = "WEAK"
        print(f"  WEAK — IS hit rate {hit_rate:.1%}, not robust enough")
    else:
        verdict = "REJECTED"
        print(f"  REJECTED — IS hit rate {hit_rate:.1%} < 60%")

    print(f"\nTotal backtest time: {time.time()-t0:.1f}s")

    # Save results
    output = {
        "hypothesis": "H-206",
        "title": "Hurst Exponent Factor",
        "in_sample": {
            "hit_rate": round(hit_rate, 4),
            "mean_sharpe": round(mean_sharpe, 4),
            "n_combos": len(results),
            "best": best,
            "mean_high_hurst_long": round(mean_high, 4),
            "mean_low_hurst_long": round(mean_low, 4),
            "dominant_direction": dom_direction,
            "top10": top10,
        },
        "walk_forward": wf_result,
        "split_half": split_half,
        "verdict": verdict,
        "runtime_seconds": round(time.time() - t0, 1),
    }

    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to: {RESULTS_PATH}")
    return output


if __name__ == "__main__":
    main()
