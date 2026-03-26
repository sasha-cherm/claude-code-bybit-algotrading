"""
H-078: Return Skewness Factor (Cross-Sectional)

Compute rolling skewness of daily returns:
- LONG assets with negative skewness (crash risk premium -- compensated for downside tail risk)
- SHORT assets with positive skewness (lottery preference -- overpriced upside)

This is an established risk factor in equities. Negative skew assets are
avoided by retail (fear of crashes), creating a risk premium.

Walk-forward validation: 6 folds, 300d train, 90d test, 90d step.
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

BASE_FEE = 0.001       # 10 bps taker fee
SLIPPAGE_BPS = 2.0     # 2 bps slippage
INITIAL_CAPITAL = 10_000.0

# Parameter grid
SKEW_WINDOWS = [20, 30, 40, 60]
REBAL_FREQS = [5, 10, 21]
N_LONGS = [3, 4]

# Walk-forward config
WF_FOLDS = 6
WF_TRAIN = 300
WF_TEST = 90
WF_STEP = 90


def load_daily_data():
    """Load daily parquet data directly (no API calls)."""
    data_dir = ROOT / "data"
    daily = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if len(df) >= 200:
                daily[sym] = df
                print(f"  {sym}: {len(df)} daily bars ({df.index[0].date()} to {df.index[-1].date()})")
            else:
                print(f"  {sym}: only {len(df)} bars, skipping")
        else:
            # Fall back to hourly data resampled to daily
            h_path = data_dir / f"{safe}_1h.parquet"
            if h_path.exists():
                hdf = pd.read_parquet(h_path)
                df = hdf.resample("1D").agg({
                    "open": "first", "high": "max", "low": "min",
                    "close": "last", "volume": "sum",
                }).dropna()
                if len(df) >= 200:
                    daily[sym] = df
                    print(f"  {sym}: {len(df)} daily bars (from hourly)")
                else:
                    print(f"  {sym}: only {len(df)} bars, skipping")
            else:
                print(f"  {sym}: no data found")
    return daily


def compute_metrics(equity_series):
    """Compute standard metrics from equity curve."""
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0}
    rets = eq.pct_change().dropna()
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
    }


def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  fee_multiplier=1.0, warmup=65):
    """
    Generic cross-sectional factor backtester.
    Higher ranking value = go long, lower = go short.
    """
    if n_short is None:
        n_short = n_long

    n = len(closes)
    slippage = SLIPPAGE_BPS / 10_000
    fee_rate = BASE_FEE * fee_multiplier

    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    prev_weights = pd.Series(0.0, index=closes.columns)
    trades = 0

    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = ranking_series.iloc[i - 1]  # lagged (no look-ahead)
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                equity[i] = equity[i - 1]
                continue

            ranked = valid.sort_values(ascending=False)
            longs = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            trades += int((weight_changes > 0.01).sum())

            turnover = weight_changes.sum() / 2
            fee_drag = turnover * (fee_rate + slippage)

            daily_rets = (price_today / price_yesterday - 1)
            port_ret = (new_weights * daily_rets).sum() - fee_drag

            prev_weights = new_weights
        else:
            daily_rets = (price_today / price_yesterday - 1)
            port_ret = (prev_weights * daily_rets).sum()

        equity[i] = equity[i - 1] * (1 + port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = trades
    metrics["equity"] = eq_series
    return metrics


def skewness_ranking(closes, window):
    """
    Return skewness factor ranking.
    NEGATIVE skewness = higher ranking (long these -- crash risk premium).
    We negate skewness so that most negative skew ranks highest.
    """
    daily_rets = closes.pct_change()

    # Rolling skewness using scipy for accuracy
    def rolling_skew(series, w):
        result = series.rolling(w).apply(
            lambda x: stats.skew(x, nan_policy='omit') if x.notna().sum() >= w * 0.7 else np.nan,
            raw=False
        )
        return result

    skew_df = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        skew_df[col] = rolling_skew(daily_rets[col], window)

    # Negate: most negative skewness ranks highest (these are our longs)
    return -skew_df


def skewness_ranking_fast(closes, window):
    """
    Faster rolling skewness using pandas built-in .skew().
    NEGATIVE skewness = higher ranking (long these -- crash risk premium).
    """
    daily_rets = closes.pct_change()
    skew_df = daily_rets.rolling(window, min_periods=int(window * 0.7)).skew()
    # Negate: most negative skewness ranks highest
    return -skew_df


# =========================================================================
# Full parameter scan
# =========================================================================

def run_full_scan(closes):
    """Run all parameter combinations on the full period."""
    print("\n" + "=" * 70)
    print("H-078: RETURN SKEWNESS -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    results = []
    for window, rebal, n_long in product(SKEW_WINDOWS, REBAL_FREQS, N_LONGS):
        ranking = skewness_ranking_fast(closes, window)
        warmup = window + 10

        res = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup)
        tag = f"W{window}_R{rebal}_N{n_long}"
        results.append({
            "tag": tag,
            "window": window,
            "rebal": rebal,
            "n_long": n_long,
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "n_trades": res["n_trades"],
        })

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"\n  Total parameter combos: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.3f}")
    print(f"  Worst Sharpe: {df['sharpe'].min():.3f}")

    print("\n  All results sorted by Sharpe:")
    for _, row in df.sort_values("sharpe", ascending=False).iterrows():
        marker = "**" if row["sharpe"] > 0.5 else "  "
        print(f"  {marker} {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}")

    return df


# =========================================================================
# Walk-Forward Validation
# =========================================================================

def run_walk_forward(closes, window, rebal, n_long):
    """Walk-forward with fixed params across folds."""
    print(f"\n  Walk-Forward Validation: W{window}_R{rebal}_N{n_long}")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, {WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0:
            break

        test_closes = closes.iloc[test_start_idx:test_end_idx]
        if len(test_closes) < 30:
            break

        # Need enough history before test period for rolling skewness
        # Use data from train_start onward to compute skewness, then slice to test
        full_closes = closes.iloc[train_start_idx:test_end_idx]
        full_ranking = skewness_ranking_fast(full_closes, window)

        # Slice ranking to test period only
        test_ranking = full_ranking.iloc[WF_TRAIN:]
        warmup = 5  # skewness already computed from full history

        res = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "n_trades": res["n_trades"],
        })
        print(f"    Fold {fold+1}: {test_closes.index[0].date()} -> {test_closes.index[-1].date()}, "
              f"Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["sharpe"] > 0).sum()
    print(f"\n    Positive folds: {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe: {df['sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df['annual_ret'].mean():.1%}")
    print(f"    Worst OOS DD: {df['max_dd'].max():.1%}")
    return df


def run_walk_forward_param_selection(closes):
    """
    Proper walk-forward: for each fold, select best params on train set,
    then evaluate on test set.
    """
    print(f"\n  Walk-Forward with In-Sample Parameter Selection")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, {WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0:
            break

        # Need extra history for skewness warmup
        warmup_extra = max(SKEW_WINDOWS) + 10
        data_start_idx = max(0, train_start_idx - warmup_extra)

        train_closes = closes.iloc[data_start_idx:test_start_idx]
        test_full_closes = closes.iloc[data_start_idx:test_end_idx]
        test_closes = closes.iloc[test_start_idx:test_end_idx]

        if len(test_closes) < 30 or len(train_closes) < 100:
            break

        # Step 1: find best params on train set
        best_sharpe = -999
        best_params = None
        train_slice = closes.iloc[train_start_idx:test_start_idx]
        for window, rebal, n_long in product(SKEW_WINDOWS, REBAL_FREQS, N_LONGS):
            ranking = skewness_ranking_fast(train_closes, window)
            # Slice to actual train period
            ranking_train = ranking.iloc[-(len(train_slice)):]
            warmup = window + 5
            res = run_xs_factor(train_slice, ranking_train, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_params = (window, rebal, n_long)

        # Step 2: evaluate best params on test set
        window, rebal, n_long = best_params
        full_ranking = skewness_ranking_fast(test_full_closes, window)
        test_ranking = full_ranking.iloc[-(len(test_closes)):]
        warmup = 5
        res = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "train_best_params": f"W{window}_R{rebal}_N{n_long}",
            "train_sharpe": round(best_sharpe, 3),
            "oos_sharpe": res["sharpe"],
            "oos_annual_ret": res["annual_ret"],
            "oos_max_dd": res["max_dd"],
            "oos_n_trades": res["n_trades"],
        })
        print(f"    Fold {fold+1}: train best=W{window}_R{rebal}_N{n_long} (Sharpe {best_sharpe:.3f}), "
              f"OOS Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}")

    if not fold_results:
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe"] > 0).sum()
    print(f"\n    Positive OOS folds: {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe: {df['oos_sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df['oos_annual_ret'].mean():.1%}")
    return df


# =========================================================================
# Correlation with H-012 (Momentum)
# =========================================================================

def compute_h012_correlation(closes, window, rebal, n_long):
    """Compute return correlation between skewness and H-012 (60d momentum)."""
    print(f"\n  Correlation with H-012 (60d Momentum)")

    # Run skewness
    skew_ranking = skewness_ranking_fast(closes, window)
    warmup_skew = window + 10
    res_skew = run_xs_factor(closes, skew_ranking, rebal, n_long, warmup=warmup_skew)

    # Run H-012 momentum
    mom_ranking = closes.pct_change(60)
    res_mom = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)

    eq_skew = res_skew["equity"]
    eq_mom = res_mom["equity"]

    rets_skew = eq_skew.pct_change().dropna()
    rets_mom = eq_mom.pct_change().dropna()

    common = rets_skew.index.intersection(rets_mom.index)
    if len(common) < 50:
        print("    Insufficient overlap for correlation")
        return 0.0

    corr = rets_skew.loc[common].corr(rets_mom.loc[common])
    print(f"    Daily return correlation: {corr:.3f}")
    print(f"    H-012 Momentum: Sharpe {res_mom['sharpe']:.3f}, Ann {res_mom['annual_ret']:.1%}")
    return round(corr, 3)


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    print("H-078: Return Skewness Factor")
    print("=" * 70)

    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")

    # Build closes panel
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")
    print(f"Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    # 1. Full parameter scan
    scan_results = run_full_scan(closes)

    # 2. Walk-forward with best parameters
    best = scan_results.nlargest(1, "sharpe").iloc[0]
    best_window = int(best["window"])
    best_rebal = int(best["rebal"])
    best_n_long = int(best["n_long"])
    print(f"\n  Best full-period params: W{best_window}_R{best_rebal}_N{best_n_long}")

    wf_fixed = run_walk_forward(closes, best_window, best_rebal, best_n_long)

    # 3. Walk-forward with in-sample parameter selection (more rigorous)
    wf_selected = run_walk_forward_param_selection(closes)

    # 4. Correlation with H-012
    h012_corr = compute_h012_correlation(closes, best_window, best_rebal, best_n_long)

    # 5. Fee sensitivity
    print(f"\n  Fee Sensitivity (best params: W{best_window}_R{best_rebal}_N{best_n_long})")
    skew_ranking = skewness_ranking_fast(closes, best_window)
    warmup = best_window + 10
    for fee_mult in [1.0, 2.0, 3.0, 5.0]:
        res = run_xs_factor(closes, skew_ranking, best_rebal, best_n_long,
                            warmup=warmup, fee_multiplier=fee_mult)
        print(f"    Fee x{fee_mult:.0f}: Sharpe {res['sharpe']:.3f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    # 6. Summary
    print("\n" + "=" * 70)
    print("SUMMARY: H-078 Return Skewness")
    print("=" * 70)

    pos_pct = (scan_results["sharpe"] > 0).mean()
    print(f"  Parameter combos tested: {len(scan_results)}")
    print(f"  Positive Sharpe: {(scan_results['sharpe'] > 0).sum()}/{len(scan_results)} ({pos_pct:.0%})")
    print(f"  Best full-period: W{best_window}_R{best_rebal}_N{best_n_long}, "
          f"Sharpe {best['sharpe']:.3f}, Ann {best['annual_ret']:.1%}, DD {best['max_dd']:.1%}")

    if wf_fixed is not None:
        wf_pos = (wf_fixed["sharpe"] > 0).sum()
        print(f"  Walk-forward (fixed params): {wf_pos}/{len(wf_fixed)} positive, "
              f"mean OOS Sharpe {wf_fixed['sharpe'].mean():.3f}")

    if wf_selected is not None:
        wf_pos2 = (wf_selected["oos_sharpe"] > 0).sum()
        print(f"  Walk-forward (param selection): {wf_pos2}/{len(wf_selected)} positive, "
              f"mean OOS Sharpe {wf_selected['oos_sharpe'].mean():.3f}")

    print(f"  Correlation with H-012 (momentum): {h012_corr}")

    # Save results
    results_file = Path(__file__).parent / "results.json"
    results_data = {
        "hypothesis": "H-078",
        "name": "Return Skewness",
        "full_scan": {
            "n_combos": len(scan_results),
            "pct_positive": round(pos_pct, 3),
            "mean_sharpe": round(scan_results["sharpe"].mean(), 3),
            "median_sharpe": round(scan_results["sharpe"].median(), 3),
            "best_params": f"W{best_window}_R{best_rebal}_N{best_n_long}",
            "best_sharpe": round(float(best["sharpe"]), 3),
            "best_annual_ret": round(float(best["annual_ret"]), 4),
            "best_max_dd": round(float(best["max_dd"]), 4),
        },
        "walk_forward_fixed": {
            "n_folds": len(wf_fixed) if wf_fixed is not None else 0,
            "positive_folds": int((wf_fixed["sharpe"] > 0).sum()) if wf_fixed is not None else 0,
            "mean_oos_sharpe": round(float(wf_fixed["sharpe"].mean()), 3) if wf_fixed is not None else 0,
        },
        "walk_forward_selected": {
            "n_folds": len(wf_selected) if wf_selected is not None else 0,
            "positive_folds": int((wf_selected["oos_sharpe"] > 0).sum()) if wf_selected is not None else 0,
            "mean_oos_sharpe": round(float(wf_selected["oos_sharpe"].mean()), 3) if wf_selected is not None else 0,
        },
        "h012_correlation": h012_corr,
        "all_results": scan_results.to_dict("records"),
    }
    with open(results_file, "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\n  Results saved to {results_file}")
