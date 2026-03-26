"""
H-086: Multi-Timeframe Momentum Composite Factor (Cross-Sectional)

Instead of using a single lookback (like H-012's 60d), combine multiple timeframes
(5d, 20d, 60d returns) into a composite score. Each timeframe captures different
momentum dynamics:
  - 5d:  short-term continuation / mean-reversion boundary
  - 20d: medium-term trend
  - 60d: long-term momentum

Methodology:
  - For each day and each asset, compute returns over 5d, 20d, and 60d
  - Z-score each timeframe's returns cross-sectionally (across all 14 assets)
  - Composite = equal-weight mean of the 3 z-scores
  - Rank by composite
  - Long top N, short bottom N (dollar-neutral, equal weight)
  - Rebalance every R days

Validation: full parameter scan, 70/30 train/test, split-half, walk-forward
(6 folds, 120d train / 90d test), correlation with H-012 momentum.
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.0006          # 6 bps taker fee on Bybit perps (one-way); round-trip ~12 bps
INITIAL_CAPITAL = 10_000.0

# Lookback windows for the three timeframes
TF_WINDOWS = [5, 20, 60]

# Parameter grid
REBAL_FREQS = [3, 5, 7]    # rebalance every N days
N_LONGS = [3, 4, 5]        # top/bottom N

# Walk-forward config
WF_FOLDS = 6
WF_TRAIN = 120
WF_TEST = 90
WF_STEP = 90

WARMUP = 65                 # need at least 60d for returns + small buffer


# =========================================================================
# Data loading
# =========================================================================

def load_daily_data():
    """Load daily parquet data for all 14 assets."""
    data_dir = ROOT / "data"
    daily = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if len(df) >= 200:
                daily[sym] = df
                print(f"  {sym}: {len(df)} daily bars "
                      f"({df.index[0].date()} to {df.index[-1].date()})")
            else:
                print(f"  {sym}: only {len(df)} bars, skipping")
        else:
            print(f"  {sym}: no data found")
    return daily


# =========================================================================
# Metrics helper
# =========================================================================

def compute_metrics(equity_series):
    """Compute standard metrics from equity curve."""
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe_daily": -99, "sharpe_raw": -99, "annual_ret": 0,
                "max_dd": 1.0, "win_rate": 0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    return {
        "sharpe_daily": round(sharpe_ratio(rets, periods_per_year=365), 3),
        "sharpe_raw": round(sharpe_ratio(rets, periods_per_year=8760), 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "win_rate": round(n_pos / n_total, 4) if n_total > 0 else 0,
    }


# =========================================================================
# Multi-timeframe momentum composite signal
# =========================================================================

def compute_multitf_composite(closes):
    """
    Compute the multi-timeframe momentum composite for each asset/day.

    For each day:
      1. Compute returns over 5d, 20d, 60d for each asset
      2. Z-score each timeframe cross-sectionally
      3. Composite = mean of z-scores

    Returns a DataFrame with the same shape as closes.
    """
    composites = []
    for window in TF_WINDOWS:
        # Simple return over the lookback window
        ret = closes.pct_change(window)
        composites.append(ret)

    # Cross-sectional z-score each timeframe, then average
    n = len(closes)
    composite_score = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    count_valid = pd.DataFrame(0, index=closes.index, columns=closes.columns)

    for ret_df in composites:
        # Cross-sectional z-score: for each row, subtract mean and divide by std
        row_mean = ret_df.mean(axis=1)
        row_std = ret_df.std(axis=1)
        # Avoid division by zero
        row_std = row_std.replace(0, np.nan)
        z = ret_df.sub(row_mean, axis=0).div(row_std, axis=0)
        # Accumulate
        valid_mask = z.notna()
        composite_score = composite_score.add(z.fillna(0))
        count_valid = count_valid.add(valid_mask.astype(int))

    # Average over the number of valid timeframes
    count_valid = count_valid.replace(0, np.nan)
    composite_score = composite_score / count_valid

    return composite_score


# =========================================================================
# Generic cross-sectional factor backtester (same pattern as H-085)
# =========================================================================

def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  warmup=WARMUP):
    """
    Generic cross-sectional factor backtester using log returns.
    Higher ranking value = go long, lower = go short.
    Dollar-neutral: equal $ on long side and short side.

    Fee model: at each rebalance, compute turnover and deduct
    FEE_RATE * turnover_notional from PnL.
    """
    if n_short is None:
        n_short = n_long

    n = len(closes)
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count = 0

    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]

        # Log returns for the day
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            # Use t-1 ranking (no look-ahead)
            ranks = ranking_series.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                # Not enough valid assets, carry position
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            ranked = valid.sort_values(ascending=False)
            longs = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            # Turnover = sum of absolute weight changes / 2
            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * FEE_RATE

            # PnL for the day using log returns
            port_ret = (new_weights * log_rets).sum() - fee_drag

            total_trades += int((weight_changes > 0.001).sum())
            rebal_count += 1
            prev_weights = new_weights
        else:
            # Hold existing positions
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"] = eq_series
    return metrics


# =========================================================================
# Full parameter scan
# =========================================================================

def run_full_scan(closes):
    """Run all parameter combinations on the full period."""
    print("\n" + "=" * 70)
    print("H-086: MULTI-TIMEFRAME MOMENTUM COMPOSITE -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE * 10000:.0f} bps per trade")
    print(f"  Timeframe windows: {TF_WINDOWS}")

    composite = compute_multitf_composite(closes)

    results = []
    equities = {}
    for rebal, n_long in product(REBAL_FREQS, N_LONGS):
        res = run_xs_factor(closes, composite, rebal, n_long, warmup=WARMUP)
        tag = f"R{rebal}_N{n_long}"
        equities[tag] = res["equity"]
        results.append({
            "tag": tag,
            "rebal": rebal,
            "n_long": n_long,
            "sharpe_daily": res["sharpe_daily"],
            "sharpe_raw": res["sharpe_raw"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
            "n_rebalances": res["n_rebalances"],
        })

    df = pd.DataFrame(results)
    positive = df[df["sharpe_daily"] > 0]
    print(f"\n  Total parameter combos: {len(df)}")
    print(f"  Positive Sharpe (daily): {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe (daily): {df['sharpe_daily'].mean():.3f}")
    print(f"  Median Sharpe (daily): {df['sharpe_daily'].median():.3f}")
    print(f"  Best Sharpe (daily): {df['sharpe_daily'].max():.3f}")
    print(f"  Worst Sharpe (daily): {df['sharpe_daily'].min():.3f}")

    print("\n  All results sorted by Sharpe (daily ann.):")
    print(f"  {'Tag':<12} {'Sharpe(365)':>11} {'Sharpe(8760)':>13} {'AnnRet':>8} "
          f"{'MaxDD':>8} {'WinRate':>8} {'Trades':>7}")
    print("  " + "-" * 70)
    for _, row in df.sort_values("sharpe_daily", ascending=False).iterrows():
        marker = "**" if row["sharpe_daily"] > 0.5 else "  "
        print(f"  {marker}{row['tag']:<10} {row['sharpe_daily']:>11.3f} {row['sharpe_raw']:>13.3f} "
              f"{row['annual_ret']:>7.1%} {row['max_dd']:>7.1%} "
              f"{row['win_rate']:>7.1%} {row['n_trades']:>7}")

    return df, equities, composite


# =========================================================================
# 70/30 Train/Test Split
# =========================================================================

def run_train_test_split(closes, split_ratio=0.7):
    """Run parameter scan on 70% train, evaluate best on 30% test."""
    n = len(closes)
    split_idx = int(n * split_ratio)
    train_closes = closes.iloc[:split_idx]
    test_closes = closes.iloc[split_idx:]

    print(f"\n{'='*70}")
    print(f"70/30 Train/Test Split")
    print(f"{'='*70}")
    print(f"  Train: {train_closes.index[0].date()} to {train_closes.index[-1].date()} ({len(train_closes)} days)")
    print(f"  Test:  {test_closes.index[0].date()} to {test_closes.index[-1].date()} ({len(test_closes)} days)")

    train_composite = compute_multitf_composite(train_closes)
    test_composite = compute_multitf_composite(test_closes)

    # Find best params on train set
    best_sharpe = -999
    best_params = None
    train_results = []
    for rebal, n_long in product(REBAL_FREQS, N_LONGS):
        res = run_xs_factor(train_closes, train_composite, rebal, n_long, warmup=WARMUP)
        train_results.append({
            "rebal": rebal, "n_long": n_long,
            "sharpe_daily": res["sharpe_daily"],
        })
        if res["sharpe_daily"] > best_sharpe:
            best_sharpe = res["sharpe_daily"]
            best_params = (rebal, n_long)

    rebal, n_long = best_params
    print(f"  Train best: R{rebal}_N{n_long} (Sharpe {best_sharpe:.3f})")

    # Evaluate on test set
    res_test = run_xs_factor(test_closes, test_composite, rebal, n_long, warmup=WARMUP)
    print(f"  Test result: Sharpe(365) {res_test['sharpe_daily']:.3f}, "
          f"Sharpe(8760) {res_test['sharpe_raw']:.3f}, "
          f"Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}")

    # Also evaluate ALL params on test set for comparison
    print(f"\n  All params on test set:")
    test_results = []
    for rebal_t, n_long_t in product(REBAL_FREQS, N_LONGS):
        res_t = run_xs_factor(test_closes, test_composite, rebal_t, n_long_t, warmup=WARMUP)
        test_results.append({
            "tag": f"R{rebal_t}_N{n_long_t}",
            "sharpe_daily": res_t["sharpe_daily"],
            "annual_ret": res_t["annual_ret"],
        })
    test_df = pd.DataFrame(test_results)
    for _, row in test_df.sort_values("sharpe_daily", ascending=False).iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe_daily']:.3f}, Ann {row['annual_ret']:.1%}")

    return {
        "train_best_params": f"R{rebal}_N{n_long}",
        "train_sharpe": round(best_sharpe, 3),
        "test_sharpe_daily": res_test["sharpe_daily"],
        "test_sharpe_raw": res_test["sharpe_raw"],
        "test_annual_ret": res_test["annual_ret"],
        "test_max_dd": res_test["max_dd"],
        "test_win_rate": res_test["win_rate"],
        "test_n_days": len(test_closes),
    }


# =========================================================================
# Split-Half Validation
# =========================================================================

def run_split_half(closes):
    """Split data into two halves, run scan on each, compare rankings."""
    n = len(closes)
    mid = n // 2
    half1_closes = closes.iloc[:mid]
    half2_closes = closes.iloc[mid:]

    print(f"\n{'='*70}")
    print(f"Split-Half Validation")
    print(f"{'='*70}")
    print(f"  Half 1: {half1_closes.index[0].date()} to {half1_closes.index[-1].date()} ({len(half1_closes)} days)")
    print(f"  Half 2: {half2_closes.index[0].date()} to {half2_closes.index[-1].date()} ({len(half2_closes)} days)")

    composite1 = compute_multitf_composite(half1_closes)
    composite2 = compute_multitf_composite(half2_closes)

    results_h1 = []
    results_h2 = []
    param_labels = []
    for rebal, n_long in product(REBAL_FREQS, N_LONGS):
        res1 = run_xs_factor(half1_closes, composite1, rebal, n_long, warmup=WARMUP)
        res2 = run_xs_factor(half2_closes, composite2, rebal, n_long, warmup=WARMUP)
        results_h1.append(res1["sharpe_daily"])
        results_h2.append(res2["sharpe_daily"])
        param_labels.append(f"R{rebal}_N{n_long}")

    h1_arr = np.array(results_h1)
    h2_arr = np.array(results_h2)
    corr = np.corrcoef(h1_arr, h2_arr)[0, 1]
    both_positive = ((h1_arr > 0) & (h2_arr > 0)).sum()

    print(f"  Sharpe rank correlation between halves: {corr:.3f}")
    print(f"  Positive in both halves: {both_positive}/{len(h1_arr)} ({both_positive/len(h1_arr):.0%})")
    print(f"  Half 1 mean Sharpe: {h1_arr.mean():.3f}")
    print(f"  Half 2 mean Sharpe: {h2_arr.mean():.3f}")

    print(f"\n  Per-param breakdown:")
    for i, label in enumerate(param_labels):
        marker = "+" if h1_arr[i] > 0 and h2_arr[i] > 0 else " "
        print(f"    {marker} {label}: H1={h1_arr[i]:.3f}, H2={h2_arr[i]:.3f}")

    return {
        "sharpe_correlation": round(float(corr), 3),
        "both_positive_pct": round(both_positive / len(h1_arr), 3),
        "half1_mean_sharpe": round(float(h1_arr.mean()), 3),
        "half2_mean_sharpe": round(float(h2_arr.mean()), 3),
    }


# =========================================================================
# Walk-Forward Validation
# =========================================================================

def run_walk_forward(closes, rebal, n_long):
    """
    Walk-forward validation with FIXED params: 6 folds, 120d train / 90d test.
    Folds go from most recent backwards.
    """
    print(f"\n{'='*70}")
    print(f"Walk-Forward (Fixed Params): R{rebal}_N{n_long}")
    print(f"{'='*70}")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, {WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0:
            print(f"    Fold {fold+1}: insufficient data, skipping")
            break

        test_closes = closes.iloc[test_start_idx:test_end_idx]

        if len(test_closes) < 30:
            print(f"    Fold {fold+1}: test period too short ({len(test_closes)} days)")
            break

        test_composite = compute_multitf_composite(test_closes)
        warmup = min(WARMUP, len(test_closes) // 2)

        res = run_xs_factor(test_closes, test_composite, rebal, n_long, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "sharpe_daily": res["sharpe_daily"],
            "sharpe_raw": res["sharpe_raw"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
        })
        print(f"    Fold {fold+1}: {test_closes.index[0].date()} -> {test_closes.index[-1].date()}, "
              f"Sharpe(365) {res['sharpe_daily']:.3f}, Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["sharpe_daily"] > 0).sum()
    print(f"\n    Positive folds: {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe (daily): {df['sharpe_daily'].mean():.3f}")
    print(f"    Mean OOS Sharpe (raw):   {df['sharpe_raw'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df['annual_ret'].mean():.1%}")
    print(f"    Worst OOS DD: {df['max_dd'].max():.1%}")
    return df


def run_walk_forward_param_selection(closes):
    """
    Walk-forward with in-sample parameter selection:
    For each fold, select best params on train set, then evaluate on test set.
    """
    print(f"\n{'='*70}")
    print(f"Walk-Forward with In-Sample Parameter Selection")
    print(f"{'='*70}")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, {WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0:
            break

        train_closes = closes.iloc[train_start_idx:test_start_idx]
        test_closes = closes.iloc[test_start_idx:test_end_idx]

        if len(test_closes) < 30 or len(train_closes) < 80:
            break

        # Step 1: find best params on train set
        train_composite = compute_multitf_composite(train_closes)
        best_sharpe = -999
        best_params = None
        for rebal, n_long in product(REBAL_FREQS, N_LONGS):
            warmup = min(WARMUP, len(train_closes) // 2)
            res = run_xs_factor(train_closes, train_composite, rebal, n_long, warmup=warmup)
            if res["sharpe_daily"] > best_sharpe:
                best_sharpe = res["sharpe_daily"]
                best_params = (rebal, n_long)

        if best_params is None:
            break

        # Step 2: evaluate best params on test set
        rebal, n_long = best_params
        test_composite = compute_multitf_composite(test_closes)
        warmup = min(WARMUP, len(test_closes) // 2)
        res = run_xs_factor(test_closes, test_composite, rebal, n_long, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "train_best_params": f"R{rebal}_N{n_long}",
            "train_sharpe": round(best_sharpe, 3),
            "oos_sharpe_daily": res["sharpe_daily"],
            "oos_sharpe_raw": res["sharpe_raw"],
            "oos_annual_ret": res["annual_ret"],
            "oos_max_dd": res["max_dd"],
        })
        print(f"    Fold {fold+1}: train best=R{rebal}_N{n_long} "
              f"(IS Sharpe {best_sharpe:.3f}), "
              f"OOS Sharpe(365) {res['sharpe_daily']:.3f}, Ann {res['annual_ret']:.1%}")

    if not fold_results:
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe_daily"] > 0).sum()
    print(f"\n    Positive OOS folds: {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe (daily): {df['oos_sharpe_daily'].mean():.3f}")
    print(f"    Mean OOS Sharpe (raw):   {df['oos_sharpe_raw'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df['oos_annual_ret'].mean():.1%}")
    return df


# =========================================================================
# Correlation with H-012 (60d single-timeframe momentum)
# =========================================================================

def compute_h012_correlation(closes, composite, rebal, n_long):
    """Compute daily return correlation between multi-TF composite and H-012 momentum."""
    print(f"\n{'='*70}")
    print(f"Correlation with H-012 (60d Single-Timeframe Momentum)")
    print(f"{'='*70}")

    # Run multi-TF composite factor
    res_mtf = run_xs_factor(closes, composite, rebal, n_long, warmup=WARMUP)

    # Run H-012: pure 60d momentum (LB60_R5_N4)
    mom60 = closes.pct_change(60)
    res_mom = run_xs_factor(closes, mom60, 5, 4, warmup=65)

    # Also run single-timeframe variants for comparison
    mom5 = closes.pct_change(5)
    res_mom5 = run_xs_factor(closes, mom5, 5, 4, warmup=10)
    mom20 = closes.pct_change(20)
    res_mom20 = run_xs_factor(closes, mom20, 5, 4, warmup=25)

    eq_mtf = res_mtf["equity"]
    eq_mom = res_mom["equity"]
    eq_mom5 = res_mom5["equity"]
    eq_mom20 = res_mom20["equity"]

    rets_mtf = eq_mtf.pct_change().dropna()
    rets_mom = eq_mom.pct_change().dropna()
    rets_mom5 = eq_mom5.pct_change().dropna()
    rets_mom20 = eq_mom20.pct_change().dropna()

    common = rets_mtf.index.intersection(rets_mom.index)
    if len(common) < 50:
        print("    Insufficient overlap for correlation")
        return {}

    corr_h012 = rets_mtf.loc[common].corr(rets_mom.loc[common])

    common5 = rets_mtf.index.intersection(rets_mom5.index)
    corr_5d = rets_mtf.loc[common5].corr(rets_mom5.loc[common5]) if len(common5) > 50 else np.nan

    common20 = rets_mtf.index.intersection(rets_mom20.index)
    corr_20d = rets_mtf.loc[common20].corr(rets_mom20.loc[common20]) if len(common20) > 50 else np.nan

    print(f"  H-086 Multi-TF (R{rebal}_N{n_long}): Sharpe(365) {res_mtf['sharpe_daily']:.3f}, Ann {res_mtf['annual_ret']:.1%}")
    print(f"  H-012 Mom-60d (R5_N4):              Sharpe(365) {res_mom['sharpe_daily']:.3f}, Ann {res_mom['annual_ret']:.1%}")
    print(f"  Mom-5d  (R5_N4):                     Sharpe(365) {res_mom5['sharpe_daily']:.3f}, Ann {res_mom5['annual_ret']:.1%}")
    print(f"  Mom-20d (R5_N4):                     Sharpe(365) {res_mom20['sharpe_daily']:.3f}, Ann {res_mom20['annual_ret']:.1%}")
    print(f"\n  Daily return correlations with H-086:")
    print(f"    vs H-012 (60d momentum): {corr_h012:.3f}")
    print(f"    vs 5d momentum:          {corr_5d:.3f}")
    print(f"    vs 20d momentum:         {corr_20d:.3f}")

    return {
        "corr_h012_60d": round(float(corr_h012), 3),
        "corr_5d_mom": round(float(corr_5d), 3) if not np.isnan(corr_5d) else None,
        "corr_20d_mom": round(float(corr_20d), 3) if not np.isnan(corr_20d) else None,
        "h012_sharpe": res_mom["sharpe_daily"],
        "h012_annual_ret": res_mom["annual_ret"],
        "mom5_sharpe": res_mom5["sharpe_daily"],
        "mom5_annual_ret": res_mom5["annual_ret"],
        "mom20_sharpe": res_mom20["sharpe_daily"],
        "mom20_annual_ret": res_mom20["annual_ret"],
    }


# =========================================================================
# Individual timeframe contribution analysis
# =========================================================================

def run_timeframe_contribution(closes, rebal, n_long):
    """
    Run each individual timeframe as a standalone factor + the composite.
    Shows whether combining timeframes adds value.
    """
    print(f"\n{'='*70}")
    print(f"Timeframe Contribution Analysis (R{rebal}_N{n_long})")
    print(f"{'='*70}")

    composite = compute_multitf_composite(closes)

    print(f"\n  {'Factor':<25} {'Sharpe(365)':>11} {'Sharpe(8760)':>13} {'AnnRet':>8} {'MaxDD':>8} {'WinRate':>8}")
    print(f"  {'-'*75}")

    results = {}
    for window in TF_WINDOWS:
        ret = closes.pct_change(window)
        # z-score cross-sectionally
        row_mean = ret.mean(axis=1)
        row_std = ret.std(axis=1).replace(0, np.nan)
        z = ret.sub(row_mean, axis=0).div(row_std, axis=0)
        warmup = max(window + 5, 10)
        res = run_xs_factor(closes, z, rebal, n_long, warmup=warmup)
        label = f"Single {window}d z-scored"
        print(f"  {label:<25} {res['sharpe_daily']:>11.3f} {res['sharpe_raw']:>13.3f} "
              f"{res['annual_ret']:>7.1%} {res['max_dd']:>7.1%} {res['win_rate']:>7.1%}")
        results[f"single_{window}d"] = {
            "sharpe_daily": res["sharpe_daily"],
            "sharpe_raw": res["sharpe_raw"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        }

    # Composite
    res_comp = run_xs_factor(closes, composite, rebal, n_long, warmup=WARMUP)
    label = "Composite (5+20+60)"
    print(f"  {label:<25} {res_comp['sharpe_daily']:>11.3f} {res_comp['sharpe_raw']:>13.3f} "
          f"{res_comp['annual_ret']:>7.1%} {res_comp['max_dd']:>7.1%} {res_comp['win_rate']:>7.1%}")
    results["composite"] = {
        "sharpe_daily": res_comp["sharpe_daily"],
        "sharpe_raw": res_comp["sharpe_raw"],
        "annual_ret": res_comp["annual_ret"],
        "max_dd": res_comp["max_dd"],
    }

    # Also test pairwise combinations
    print(f"\n  Pairwise composites:")
    for i in range(len(TF_WINDOWS)):
        for j in range(i+1, len(TF_WINDOWS)):
            w1, w2 = TF_WINDOWS[i], TF_WINDOWS[j]
            rets = []
            for w in [w1, w2]:
                ret = closes.pct_change(w)
                row_mean = ret.mean(axis=1)
                row_std = ret.std(axis=1).replace(0, np.nan)
                z = ret.sub(row_mean, axis=0).div(row_std, axis=0)
                rets.append(z)
            pair_composite = (rets[0].fillna(0) + rets[1].fillna(0)) / 2
            # Properly handle NaN
            valid_count = rets[0].notna().astype(int) + rets[1].notna().astype(int)
            valid_count = valid_count.replace(0, np.nan)
            pair_composite = (rets[0].fillna(0) + rets[1].fillna(0)) / valid_count

            warmup_pair = max(w2 + 5, WARMUP)
            res_pair = run_xs_factor(closes, pair_composite, rebal, n_long, warmup=warmup_pair)
            label = f"  Pair {w1}d+{w2}d"
            print(f"  {label:<25} {res_pair['sharpe_daily']:>11.3f} {res_pair['sharpe_raw']:>13.3f} "
                  f"{res_pair['annual_ret']:>7.1%} {res_pair['max_dd']:>7.1%} {res_pair['win_rate']:>7.1%}")

    return results


# =========================================================================
# Monthly returns breakdown
# =========================================================================

def monthly_returns_table(equity_series):
    """Print a monthly returns table."""
    rets = equity_series.pct_change().dropna()
    rets.index = pd.to_datetime(rets.index)

    monthly = rets.groupby(pd.Grouper(freq="ME")).apply(lambda x: (1 + x).prod() - 1)

    print(f"\n  Monthly Returns:")
    print(f"  {'Month':<12} {'Return':>8}")
    print(f"  {'-'*22}")
    for date, ret in monthly.items():
        marker = "+" if ret > 0 else "-"
        print(f"  {date.strftime('%Y-%m'):<12} {ret:>7.1%} {marker}")

    pos_months = (monthly > 0).sum()
    total_months = len(monthly)
    print(f"\n  Positive months: {pos_months}/{total_months} ({pos_months/total_months:.0%})")
    print(f"  Best month:  {monthly.max():.1%}")
    print(f"  Worst month: {monthly.min():.1%}")
    print(f"  Mean month:  {monthly.mean():.1%}")
    print(f"  Median month: {monthly.median():.1%}")


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    print("H-086: Multi-Timeframe Momentum Composite Factor")
    print("=" * 70)
    print(f"Timeframe windows: {TF_WINDOWS}")
    print(f"Parameter grid: rebal={REBAL_FREQS}, N_long={N_LONGS}")
    print(f"Fee rate: {FEE_RATE*10000:.0f} bps per trade")
    print(f"Warmup: {WARMUP} days")

    # ===== Load data =====
    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")

    if len(daily) < 10:
        print("ERROR: Not enough assets loaded. Aborting.")
        sys.exit(1)

    # Build closes panel
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")
    print(f"Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    # ===== 1. Full parameter scan =====
    scan_results, equities, composite = run_full_scan(closes)

    # ===== 2. Best parameters =====
    best = scan_results.nlargest(1, "sharpe_daily").iloc[0]
    best_rebal = int(best["rebal"])
    best_n_long = int(best["n_long"])
    best_tag = f"R{best_rebal}_N{best_n_long}"
    print(f"\n  Best full-period params: {best_tag}")
    print(f"  Sharpe(365): {best['sharpe_daily']:.3f}, Sharpe(8760): {best['sharpe_raw']:.3f}")
    print(f"  Ann Return: {best['annual_ret']:.1%}, Max DD: {best['max_dd']:.1%}, "
          f"Win Rate: {best['win_rate']:.1%}")

    # ===== 3. Timeframe contribution analysis =====
    tf_contrib = run_timeframe_contribution(closes, best_rebal, best_n_long)

    # ===== 4. Monthly returns for best params =====
    print(f"\n{'='*70}")
    print(f"Monthly Returns for Best Params ({best_tag})")
    print(f"{'='*70}")
    monthly_returns_table(equities[best_tag])

    # ===== 5. 70/30 Train/Test Split =====
    train_test = run_train_test_split(closes)

    # ===== 6. Split-Half Validation =====
    split_half = run_split_half(closes)

    # ===== 7. Walk-Forward (fixed params) =====
    wf_fixed = run_walk_forward(closes, best_rebal, best_n_long)

    # ===== 8. Walk-Forward with parameter selection =====
    wf_selected = run_walk_forward_param_selection(closes)

    # ===== 9. Correlation with H-012 =====
    h012_corr = compute_h012_correlation(closes, composite, best_rebal, best_n_long)

    # ===== 10. Parameter Robustness =====
    pos_pct = (scan_results["sharpe_daily"] > 0).mean()
    mean_sharpe = scan_results["sharpe_daily"].mean()
    median_sharpe = scan_results["sharpe_daily"].median()

    # ===== 11. Final Summary =====
    print("\n" + "=" * 70)
    print("FINAL SUMMARY: H-086 Multi-Timeframe Momentum Composite")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()} ({len(closes)} days)")
    print(f"  Fee: {FEE_RATE*10000:.0f} bps per trade")
    print(f"  Timeframes: {TF_WINDOWS}")

    print(f"\n  --- Full Scan ---")
    print(f"  Parameter combos tested: {len(scan_results)}")
    print(f"  Positive Sharpe: {(scan_results['sharpe_daily'] > 0).sum()}/{len(scan_results)} ({pos_pct:.0%})")
    print(f"  Mean Sharpe(365): {mean_sharpe:.3f}, Median: {median_sharpe:.3f}")
    print(f"  Best full-period: {best_tag}")
    print(f"    Sharpe(365): {best['sharpe_daily']:.3f}")
    print(f"    Sharpe(8760): {best['sharpe_raw']:.3f}")
    print(f"    Annual Return: {best['annual_ret']:.1%}")
    print(f"    Max Drawdown: {best['max_dd']:.1%}")
    print(f"    Win Rate: {best['win_rate']:.1%}")
    print(f"    Trades: {int(best['n_trades'])}")

    print(f"\n  --- Timeframe Contribution ---")
    for k, v in tf_contrib.items():
        print(f"    {k}: Sharpe(365) {v['sharpe_daily']:.3f}, Ann {v['annual_ret']:.1%}, DD {v['max_dd']:.1%}")

    print(f"\n  --- 70/30 Train/Test ---")
    print(f"    Train best params: {train_test['train_best_params']} (IS Sharpe {train_test['train_sharpe']:.3f})")
    print(f"    OOS Sharpe(365): {train_test['test_sharpe_daily']:.3f}")
    print(f"    OOS Sharpe(8760): {train_test['test_sharpe_raw']:.3f}")
    print(f"    OOS Ann Return: {train_test['test_annual_ret']:.1%}")
    print(f"    OOS Max DD: {train_test['test_max_dd']:.1%}")
    print(f"    Test days: {train_test['test_n_days']}")

    print(f"\n  --- Split-Half ---")
    print(f"    Sharpe correlation: {split_half['sharpe_correlation']:.3f}")
    print(f"    Both positive: {split_half['both_positive_pct']:.0%}")
    print(f"    Half 1 mean Sharpe: {split_half['half1_mean_sharpe']:.3f}")
    print(f"    Half 2 mean Sharpe: {split_half['half2_mean_sharpe']:.3f}")

    if wf_fixed is not None:
        wf_pos = int((wf_fixed["sharpe_daily"] > 0).sum())
        print(f"\n  --- Walk-Forward (fixed params: {best_tag}) ---")
        print(f"    Positive folds: {wf_pos}/{len(wf_fixed)}")
        print(f"    Mean OOS Sharpe(365): {wf_fixed['sharpe_daily'].mean():.3f}")
        print(f"    Mean OOS Sharpe(8760): {wf_fixed['sharpe_raw'].mean():.3f}")
        print(f"    Mean OOS Ann Return: {wf_fixed['annual_ret'].mean():.1%}")
        print(f"    Worst OOS DD: {wf_fixed['max_dd'].max():.1%}")

    if wf_selected is not None:
        wf_pos2 = int((wf_selected["oos_sharpe_daily"] > 0).sum())
        print(f"\n  --- Walk-Forward (param selection) ---")
        print(f"    Positive folds: {wf_pos2}/{len(wf_selected)}")
        print(f"    Mean OOS Sharpe(365): {wf_selected['oos_sharpe_daily'].mean():.3f}")
        print(f"    Mean OOS Sharpe(8760): {wf_selected['oos_sharpe_raw'].mean():.3f}")
        print(f"    Mean OOS Ann Return: {wf_selected['oos_annual_ret'].mean():.1%}")

    print(f"\n  --- Correlation with H-012 ---")
    if h012_corr:
        print(f"    vs H-012 (60d momentum): {h012_corr.get('corr_h012_60d', 'N/A')}")
        print(f"    vs 5d momentum:          {h012_corr.get('corr_5d_mom', 'N/A')}")
        print(f"    vs 20d momentum:         {h012_corr.get('corr_20d_mom', 'N/A')}")
        print(f"    H-012 Sharpe(365):       {h012_corr.get('h012_sharpe', 'N/A')}")
        print(f"    H-012 Ann Return:        {h012_corr.get('h012_annual_ret', 'N/A')}")

    # ===== 12. Save results =====
    results_file = Path(__file__).parent / "h086_results.json"
    results_data = {
        "hypothesis": "H-086",
        "name": "Multi-Timeframe Momentum Composite",
        "description": "Cross-sectional factor: z-scored 5d+20d+60d returns composite. Long top N, short bottom N.",
        "timeframe_windows": TF_WINDOWS,
        "fee_rate_bps": FEE_RATE * 10000,
        "universe_size": len(closes.columns),
        "n_days": len(closes),
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "full_scan": {
            "n_combos": len(scan_results),
            "pct_positive_sharpe": round(float(pos_pct), 3),
            "mean_sharpe_daily": round(float(mean_sharpe), 3),
            "median_sharpe_daily": round(float(median_sharpe), 3),
            "best_params": best_tag,
            "best_sharpe_daily": round(float(best["sharpe_daily"]), 3),
            "best_sharpe_raw": round(float(best["sharpe_raw"]), 3),
            "best_annual_ret": round(float(best["annual_ret"]), 4),
            "best_max_dd": round(float(best["max_dd"]), 4),
            "best_win_rate": round(float(best["win_rate"]), 4),
            "best_n_trades": int(best["n_trades"]),
            "all_results": scan_results.to_dict("records"),
        },
        "timeframe_contribution": tf_contrib,
        "train_test_70_30": train_test,
        "split_half": split_half,
        "walk_forward_fixed": {
            "params": best_tag,
            "n_folds": len(wf_fixed) if wf_fixed is not None else 0,
            "positive_folds": int((wf_fixed["sharpe_daily"] > 0).sum()) if wf_fixed is not None else 0,
            "mean_oos_sharpe_daily": round(float(wf_fixed["sharpe_daily"].mean()), 3) if wf_fixed is not None else 0,
            "mean_oos_sharpe_raw": round(float(wf_fixed["sharpe_raw"].mean()), 3) if wf_fixed is not None else 0,
            "mean_oos_annual_ret": round(float(wf_fixed["annual_ret"].mean()), 4) if wf_fixed is not None else 0,
            "folds": wf_fixed.to_dict("records") if wf_fixed is not None else [],
        },
        "walk_forward_selected": {
            "n_folds": len(wf_selected) if wf_selected is not None else 0,
            "positive_folds": int((wf_selected["oos_sharpe_daily"] > 0).sum()) if wf_selected is not None else 0,
            "mean_oos_sharpe_daily": round(float(wf_selected["oos_sharpe_daily"].mean()), 3) if wf_selected is not None else 0,
            "mean_oos_sharpe_raw": round(float(wf_selected["oos_sharpe_raw"].mean()), 3) if wf_selected is not None else 0,
            "folds": wf_selected.to_dict("records") if wf_selected is not None else [],
        },
        "h012_correlation": h012_corr,
        "parameter_robustness": {
            "pct_positive_sharpe": round(float(pos_pct), 3),
            "mean_sharpe_daily": round(float(mean_sharpe), 3),
            "median_sharpe_daily": round(float(median_sharpe), 3),
        },
    }

    with open(results_file, "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\n  Results saved to {results_file}")
