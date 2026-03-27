"""
H-100: Average Pairwise Correlation (Comovement Factor)

For each asset, compute its average pairwise correlation with all other 13 assets
over a rolling window. Rank by average correlation.

Directions tested:
  A (low_corr_long)  - Long low-corr assets (idiosyncratic / harder to hedge)
  B (high_corr_long) - Long high-corr assets (systematic / momentum leaders)

Dollar-neutral: equal-weight long side vs equal-weight short side.

Validation: full parameter scan, walk-forward (4 equal folds), walk-forward with
parameter selection, split-half, 70/30 train/test, correlation with H-012 momentum
(LB60_R5_N4) and H-031 size (W30_R5_N5), fee sensitivity at 5 bps round-trip.
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

FEE_RATE = 0.00025     # 2.5 bps per leg = 5 bps round-trip
INITIAL_CAPITAL = 10_000.0

# Parameter grid — 5 * 5 * 3 * 2 = 150 combinations
CORR_WINDOWS  = [20, 30, 40, 60, 90]
REBAL_FREQS   = [3, 5, 7, 10, 14]
N_POSITIONS   = [3, 4, 5]
DIRECTIONS    = ["low_corr_long", "high_corr_long"]

# Walk-forward config — 4 equal folds
WF_FOLDS = 4
WF_TRAIN = 270       # ~9 months
WF_TEST  = 135       # ~4.5 months
WF_STEP  = 135


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
# Metrics helpers
# =========================================================================

def compute_metrics(equity_series):
    """Compute standard metrics from equity curve."""
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "win_rate": 0}
    rets = eq.pct_change().dropna()
    n_pos   = (rets > 0).sum()
    n_total = len(rets)
    return {
        "sharpe":     round(sharpe_ratio(rets, periods_per_year=365), 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd":     round(max_drawdown(eq), 4),
        "win_rate":   round(n_pos / n_total, 4) if n_total > 0 else 0,
    }


# =========================================================================
# Comovement factor
# =========================================================================

def comovement_factor(closes, corr_window, direction):
    """
    For each asset on each day, compute its average pairwise Pearson correlation
    with all other assets over a rolling `corr_window`-day window.

    direction == "low_corr_long"  → return NEGATIVE avg_corr (low corr → high rank → long)
    direction == "high_corr_long" → return POSITIVE avg_corr (high corr → high rank → long)
    """
    returns = closes.pct_change()
    n_assets = len(closes.columns)
    n_days   = len(closes)

    # We will build the ranking DataFrame row by row.
    # To avoid huge memory usage, compute rolling corr matrix only on valid windows.
    avg_corr = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)

    for t in range(corr_window, n_days):
        window_rets = returns.iloc[t - corr_window : t]
        # Drop columns that have NaNs in this window
        valid_cols = window_rets.dropna(axis=1).columns
        if len(valid_cols) < 4:
            continue
        corr_mat = window_rets[valid_cols].corr()
        # For each asset, average correlation with *all other* assets
        for col in valid_cols:
            others = [c for c in valid_cols if c != col]
            avg_corr.loc[closes.index[t], col] = corr_mat.loc[col, others].mean()

    if direction == "low_corr_long":
        return -avg_corr      # negate: lower avg_corr → higher signal → go long
    else:
        return avg_corr       # direct: higher avg_corr → higher signal → go long


def comovement_factor_fast(closes, corr_window, direction):
    """
    Faster vectorised implementation using pandas rolling correlation.
    Builds the full rolling correlation matrix via pairwise rolling corr.
    """
    returns = closes.pct_change()
    assets  = closes.columns.tolist()
    n       = len(assets)
    n_days  = len(closes)

    # Pre-allocate
    avg_corr_vals = np.full((n_days, n), np.nan)

    # Build pairwise rolling corr for all unique pairs, store in a 3D array
    # Shape: (n_days, n, n)
    corr_cube = np.full((n_days, n, n), np.nan)
    np.fill_diagonal_strides = None  # not a function, handled below

    for i in range(n):
        for j in range(i + 1, n):
            pair_corr = returns.iloc[:, i].rolling(corr_window, min_periods=corr_window).corr(
                returns.iloc[:, j]
            ).values
            corr_cube[:, i, j] = pair_corr
            corr_cube[:, j, i] = pair_corr

    # Fill diagonal with 1 (self-correlation)
    for k in range(n):
        corr_cube[:, k, k] = 1.0

    # Average off-diagonal
    for k in range(n):
        mask = np.ones(n, dtype=bool)
        mask[k] = False
        avg_corr_vals[:, k] = np.nanmean(corr_cube[:, k, :][:, mask], axis=1)

    avg_corr = pd.DataFrame(avg_corr_vals, index=closes.index, columns=assets)

    # Set first corr_window rows to NaN (incomplete windows)
    avg_corr.iloc[:corr_window] = np.nan

    if direction == "low_corr_long":
        return -avg_corr
    else:
        return avg_corr


# =========================================================================
# Generic cross-sectional backtester
# =========================================================================

def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  warmup=95):
    """
    Generic cross-sectional factor backtester.
    Higher ranking value → long, lower → short.
    Dollar-neutral: equal $ on long side and short side.
    Returns include equity curve for further analysis.
    """
    if n_short is None:
        n_short = n_long

    n          = len(closes)
    equity     = np.zeros(n)
    equity[0]  = INITIAL_CAPITAL
    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count  = 0

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets        = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = ranking_series.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            ranked = valid.sort_values(ascending=False)
            longs  = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover       = weight_changes.sum() / 2
            fee_drag       = turnover * FEE_RATE

            port_ret = (new_weights * log_rets).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count  += 1
            prev_weights  = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics   = compute_metrics(eq_series)
    metrics["n_trades"]    = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"]      = eq_series
    return metrics


# =========================================================================
# Full parameter scan
# =========================================================================

def run_full_scan(closes):
    """Run all 150 parameter combinations on the full period."""
    print("\n" + "=" * 70)
    print("H-100: AVERAGE PAIRWISE CORRELATION FACTOR -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE * 20000:.0f} bps round-trip")
    print(f"  Param combos: {len(CORR_WINDOWS)*len(REBAL_FREQS)*len(N_POSITIONS)*len(DIRECTIONS)}")

    results = []
    combo_count = 0
    total = len(CORR_WINDOWS) * len(REBAL_FREQS) * len(N_POSITIONS) * len(DIRECTIONS)

    # Pre-compute correlation rankings for each (window, direction) to avoid redundant work
    print("\n  Pre-computing correlation signals...")
    signal_cache = {}
    for cw in CORR_WINDOWS:
        for direction in DIRECTIONS:
            key = (cw, direction)
            print(f"    Computing {direction}, window={cw}...", flush=True)
            signal_cache[key] = comovement_factor_fast(closes, cw, direction)

    print(f"  Running {total} backtests...")
    for cw, rebal, n_pos, direction in product(CORR_WINDOWS, REBAL_FREQS, N_POSITIONS, DIRECTIONS):
        ranking = signal_cache[(cw, direction)]
        warmup  = cw + 5

        res = run_xs_factor(closes, ranking, rebal, n_pos, warmup=warmup)
        tag = f"CW{cw}_R{rebal}_N{n_pos}_{direction[:3].upper()}"
        results.append({
            "tag":        tag,
            "corr_window": cw,
            "rebal":      rebal,
            "n_pos":      n_pos,
            "direction":  direction,
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
            "win_rate":   res["win_rate"],
            "n_trades":   res["n_trades"],
            "n_rebalances": res["n_rebalances"],
        })
        combo_count += 1
        if combo_count % 30 == 0:
            print(f"    ... {combo_count}/{total} done")

    df = pd.DataFrame(results)

    # Overall stats
    positive     = df[df["sharpe"] > 0]
    pos_low_dir  = df[(df["direction"] == "low_corr_long")  & (df["sharpe"] > 0)]
    pos_high_dir = df[(df["direction"] == "high_corr_long") & (df["sharpe"] > 0)]
    df_low       = df[df["direction"] == "low_corr_long"]
    df_high      = df[df["direction"] == "high_corr_long"]

    print(f"\n  Total parameter combos: {len(df)}")
    print(f"  Positive Sharpe (all):  {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  --- Direction A (low_corr_long):")
    print(f"      Positive Sharpe:    {len(pos_low_dir)}/{len(df_low)} ({len(pos_low_dir)/len(df_low):.0%})")
    print(f"      Mean Sharpe:        {df_low['sharpe'].mean():.3f}")
    print(f"      Median Sharpe:      {df_low['sharpe'].median():.3f}")
    print(f"      Best Sharpe:        {df_low['sharpe'].max():.3f}")
    print(f"  --- Direction B (high_corr_long):")
    print(f"      Positive Sharpe:    {len(pos_high_dir)}/{len(df_high)} ({len(pos_high_dir)/len(df_high):.0%})")
    print(f"      Mean Sharpe:        {df_high['sharpe'].mean():.3f}")
    print(f"      Median Sharpe:      {df_high['sharpe'].median():.3f}")
    print(f"      Best Sharpe:        {df_high['sharpe'].max():.3f}")

    print(f"\n  Top 10 by Sharpe (all directions):")
    for _, row in df.nlargest(10, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}, Trades {row['n_trades']}")

    print(f"\n  Top 5 by Sharpe — Direction A (low_corr_long):")
    for _, row in df_low.nlargest(5, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}")

    print(f"\n  Top 5 by Sharpe — Direction B (high_corr_long):")
    for _, row in df_high.nlargest(5, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}")

    print(f"\n  Bottom 5 by Sharpe (all):")
    for _, row in df.nsmallest(5, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    return df, signal_cache


# =========================================================================
# 4-fold walk-forward (equal folds, fixed best params)
# =========================================================================

def run_walk_forward_fixed(closes, signal_cache, corr_window, rebal, n_pos, direction):
    """Walk-forward with FIXED params: 4 equal folds."""
    n = len(closes)
    fold_size = n // WF_FOLDS

    print(f"\n  Walk-Forward (Fixed Params): CW{corr_window}_R{rebal}_N{n_pos}_{direction}")
    print(f"  Config: {WF_FOLDS} equal folds of ~{fold_size} days each")

    fold_results = []
    for fold in range(WF_FOLDS):
        start_idx = fold * fold_size
        end_idx   = (fold + 1) * fold_size if fold < WF_FOLDS - 1 else n
        fold_closes = closes.iloc[start_idx:end_idx]

        if len(fold_closes) < 60:
            print(f"    Fold {fold+1}: too short ({len(fold_closes)} days), skipping")
            continue

        fold_ranking = comovement_factor_fast(fold_closes, corr_window, direction)
        warmup       = corr_window + 5

        res = run_xs_factor(fold_closes, fold_ranking, rebal, n_pos, warmup=warmup)

        fold_results.append({
            "fold":       fold + 1,
            "start":      fold_closes.index[0].strftime("%Y-%m-%d"),
            "end":        fold_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days":     len(fold_closes),
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
            "win_rate":   res["win_rate"],
        })
        print(f"    Fold {fold+1}: {fold_closes.index[0].date()} → {fold_closes.index[-1].date()}, "
              f"Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["sharpe"] > 0).sum()
    print(f"\n    Positive folds:      {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe:     {df['sharpe'].mean():.3f}")
    print(f"    Median OOS Sharpe:   {df['sharpe'].median():.3f}")
    print(f"    Mean OOS Ann Return: {df['annual_ret'].mean():.1%}")
    print(f"    Worst OOS DD:        {df['max_dd'].max():.1%}")
    return df


# =========================================================================
# Walk-forward with parameter selection
# =========================================================================

def run_walk_forward_param_selection(closes):
    """Walk-forward with in-sample parameter selection per fold."""
    print(f"\n  Walk-Forward with In-Sample Parameter Selection")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, {WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx   = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0:
            break

        train_c = closes.iloc[train_start_idx:test_start_idx]
        test_c  = closes.iloc[test_start_idx:test_end_idx]

        if len(test_c) < 40 or len(train_c) < 100:
            break

        # Find best params on train set
        best_sharpe = -999
        best_params = None

        # Cache signals for train set
        train_cache = {}
        for cw in CORR_WINDOWS:
            for d in DIRECTIONS:
                train_cache[(cw, d)] = comovement_factor_fast(train_c, cw, d)

        for cw, rebal, n_pos, direction in product(CORR_WINDOWS, REBAL_FREQS, N_POSITIONS, DIRECTIONS):
            ranking = train_cache[(cw, direction)]
            warmup  = cw + 5
            if warmup >= len(train_c) - 20:
                continue
            res = run_xs_factor(train_c, ranking, rebal, n_pos, warmup=warmup)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_params = (cw, rebal, n_pos, direction)

        if best_params is None:
            break

        cw, rebal, n_pos, direction = best_params
        test_ranking = comovement_factor_fast(test_c, cw, direction)
        warmup       = min(cw + 5, len(test_c) // 2)
        res          = run_xs_factor(test_c, test_ranking, rebal, n_pos, warmup=warmup)

        fold_results.append({
            "fold":             fold + 1,
            "start":            test_c.index[0].strftime("%Y-%m-%d"),
            "end":              test_c.index[-1].strftime("%Y-%m-%d"),
            "n_days":           len(test_c),
            "train_best_params": f"CW{cw}_R{rebal}_N{n_pos}_{direction}",
            "train_sharpe":     round(best_sharpe, 3),
            "oos_sharpe":       res["sharpe"],
            "oos_annual_ret":   res["annual_ret"],
            "oos_max_dd":       res["max_dd"],
        })
        print(f"    Fold {fold+1}: train best=CW{cw}_R{rebal}_N{n_pos}_{direction} "
              f"(IS Sharpe {best_sharpe:.3f}), "
              f"OOS Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe"] > 0).sum()
    print(f"\n    Positive OOS folds:      {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe:         {df['oos_sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return:     {df['oos_annual_ret'].mean():.1%}")
    return df


# =========================================================================
# Split-Half Validation
# =========================================================================

def run_split_half(closes):
    """Split data into two halves, run scan on each, compare Sharpe ranking."""
    n   = len(closes)
    mid = n // 2
    h1  = closes.iloc[:mid]
    h2  = closes.iloc[mid:]

    print(f"\n  Split-Half Validation")
    print(f"  Half 1: {h1.index[0].date()} to {h1.index[-1].date()} ({len(h1)} days)")
    print(f"  Half 2: {h2.index[0].date()} to {h2.index[-1].date()} ({len(h2)} days)")

    results_h1 = []
    results_h2 = []

    h1_cache = {}
    h2_cache = {}
    for cw in CORR_WINDOWS:
        for d in DIRECTIONS:
            h1_cache[(cw, d)] = comovement_factor_fast(h1, cw, d)
            h2_cache[(cw, d)] = comovement_factor_fast(h2, cw, d)

    for cw, rebal, n_pos, direction in product(CORR_WINDOWS, REBAL_FREQS, N_POSITIONS, DIRECTIONS):
        warmup = cw + 5
        r1 = run_xs_factor(h1, h1_cache[(cw, direction)], rebal, n_pos, warmup=warmup)
        r2 = run_xs_factor(h2, h2_cache[(cw, direction)], rebal, n_pos, warmup=warmup)
        results_h1.append(r1["sharpe"])
        results_h2.append(r2["sharpe"])

    h1_arr = np.array(results_h1)
    h2_arr = np.array(results_h2)
    corr   = np.corrcoef(h1_arr, h2_arr)[0, 1]
    both_pos = ((h1_arr > 0) & (h2_arr > 0)).sum()

    print(f"  Sharpe rank correlation between halves: {corr:.3f}")
    print(f"  Positive in both halves: {both_pos}/{len(h1_arr)} ({both_pos/len(h1_arr):.0%})")
    print(f"  Half 1 mean Sharpe: {h1_arr.mean():.3f}")
    print(f"  Half 2 mean Sharpe: {h2_arr.mean():.3f}")

    return {
        "sharpe_correlation":  round(float(corr), 3),
        "both_positive_pct":   round(both_pos / len(h1_arr), 3),
        "half1_mean_sharpe":   round(float(h1_arr.mean()), 3),
        "half2_mean_sharpe":   round(float(h2_arr.mean()), 3),
    }


# =========================================================================
# Correlation with H-012 (momentum) and H-031 (size)
# =========================================================================

def h012_momentum_ranking(closes):
    """H-012 momentum: 60-day return, long top 4, short bottom 4, rebal 5d."""
    return closes.pct_change(60)


def h031_size_ranking(closes):
    """
    H-031 size factor: rolling 30d mean dollar volume as a proxy for market cap.
    Long large-cap (highest dollar vol), short small-cap.
    We use close as price proxy (no separate volume data needed beyond closes).
    Actually H-031 uses just close price ranking (price-based size proxy) with
    a 30-day rolling mean price. We replicate: rank by 30d rolling mean close.
    """
    return closes.rolling(30, min_periods=30).mean()


def compute_factor_correlations(closes, corr_window, rebal, n_pos, direction):
    """Compute daily return correlations with H-012 momentum and H-031 size."""
    print(f"\n  Factor Correlations (vs H-012 momentum, vs H-031 size)")

    # H-100 comovement
    ranking_h100 = comovement_factor_fast(closes, corr_window, direction)
    warmup_h100  = corr_window + 5
    res_h100     = run_xs_factor(closes, ranking_h100, rebal, n_pos, warmup=warmup_h100)

    # H-012 momentum (60d, rebal 5d, N=4)
    ranking_h012 = h012_momentum_ranking(closes)
    res_h012     = run_xs_factor(closes, ranking_h012, 5, 4, warmup=65)

    # H-031 size (30d mean price, rebal 5d, N=5, long large)
    ranking_h031 = h031_size_ranking(closes)
    res_h031     = run_xs_factor(closes, ranking_h031, 5, 5, warmup=35)

    rets_h100 = res_h100["equity"].pct_change().dropna()
    rets_h012 = res_h012["equity"].pct_change().dropna()
    rets_h031 = res_h031["equity"].pct_change().dropna()

    # H-100 vs H-012
    common_12 = rets_h100.index.intersection(rets_h012.index)
    if len(common_12) >= 50:
        corr_h012 = rets_h100.loc[common_12].corr(rets_h012.loc[common_12])
        print(f"    H-100 vs H-012 (Momentum) daily return corr: {corr_h012:.3f}")
        print(f"    H-012 Momentum: Sharpe {res_h012['sharpe']:.3f}, Ann {res_h012['annual_ret']:.1%}")
    else:
        corr_h012 = np.nan
        print("    Insufficient overlap for H-012 correlation")

    # H-100 vs H-031
    common_31 = rets_h100.index.intersection(rets_h031.index)
    if len(common_31) >= 50:
        corr_h031 = rets_h100.loc[common_31].corr(rets_h031.loc[common_31])
        print(f"    H-100 vs H-031 (Size) daily return corr: {corr_h031:.3f}")
        print(f"    H-031 Size:     Sharpe {res_h031['sharpe']:.3f}, Ann {res_h031['annual_ret']:.1%}")
    else:
        corr_h031 = np.nan
        print("    Insufficient overlap for H-031 correlation")

    print(f"    H-100 Comovement: Sharpe {res_h100['sharpe']:.3f}, Ann {res_h100['annual_ret']:.1%}")

    return {
        "h012_return_corr": round(float(corr_h012), 3) if not np.isnan(corr_h012) else None,
        "h031_return_corr": round(float(corr_h031), 3) if not np.isnan(corr_h031) else None,
        "h012_sharpe":      res_h012["sharpe"],
        "h031_sharpe":      res_h031["sharpe"],
        "h100_sharpe":      res_h100["sharpe"],
    }


# =========================================================================
# Fee sensitivity
# =========================================================================

def run_fee_sensitivity(closes, corr_window, rebal, n_pos, direction):
    """Test at 0, 2.5, 5, 10, 15, 25 bps round-trip."""
    global FEE_RATE
    original = FEE_RATE
    print(f"\n  Fee Sensitivity")

    ranking = comovement_factor_fast(closes, corr_window, direction)
    warmup  = corr_window + 5

    fee_results = []
    for rt_bps in [0, 5, 10, 20, 30, 50]:
        FEE_RATE = rt_bps / 20000.0   # split across two legs
        res = run_xs_factor(closes, ranking, rebal, n_pos, warmup=warmup)
        fee_results.append({
            "rt_bps":     rt_bps,
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
        })
        print(f"    {rt_bps:3d} bps RT: Sharpe {res['sharpe']:.3f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    FEE_RATE = original
    return fee_results


# =========================================================================
# 70/30 Train/Test Split
# =========================================================================

def run_train_test_split(closes, split_ratio=0.7):
    """Run scan on 70% train, evaluate best on 30% test."""
    n         = len(closes)
    split_idx = int(n * split_ratio)
    train_c   = closes.iloc[:split_idx]
    test_c    = closes.iloc[split_idx:]

    print(f"\n  70/30 Train/Test Split")
    print(f"  Train: {train_c.index[0].date()} to {train_c.index[-1].date()} ({len(train_c)} days)")
    print(f"  Test:  {test_c.index[0].date()} to {test_c.index[-1].date()} ({len(test_c)} days)")

    # Train scan
    best_sharpe = -999
    best_params = None

    train_cache = {}
    for cw in CORR_WINDOWS:
        for d in DIRECTIONS:
            train_cache[(cw, d)] = comovement_factor_fast(train_c, cw, d)

    for cw, rebal, n_pos, direction in product(CORR_WINDOWS, REBAL_FREQS, N_POSITIONS, DIRECTIONS):
        warmup = cw + 5
        if warmup >= len(train_c) - 20:
            continue
        res = run_xs_factor(train_c, train_cache[(cw, direction)], rebal, n_pos, warmup=warmup)
        if res["sharpe"] > best_sharpe:
            best_sharpe = res["sharpe"]
            best_params = (cw, rebal, n_pos, direction)

    cw, rebal, n_pos, direction = best_params
    print(f"  Train best: CW{cw}_R{rebal}_N{n_pos}_{direction} (Sharpe {best_sharpe:.3f})")

    test_ranking = comovement_factor_fast(test_c, cw, direction)
    warmup       = min(cw + 5, len(test_c) // 2)
    res_test     = run_xs_factor(test_c, test_ranking, rebal, n_pos, warmup=warmup)
    print(f"  Test result: Sharpe {res_test['sharpe']:.3f}, "
          f"Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}, "
          f"WR {res_test['win_rate']:.1%}")

    return {
        "train_best_params": f"CW{cw}_R{rebal}_N{n_pos}_{direction}",
        "train_sharpe":      best_sharpe,
        "test_sharpe":       res_test["sharpe"],
        "test_annual_ret":   res_test["annual_ret"],
        "test_max_dd":       res_test["max_dd"],
        "test_win_rate":     res_test["win_rate"],
        "test_n_days":       len(test_c),
    }


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    print("H-100: Average Pairwise Correlation (Comovement Factor)")
    print("=" * 70)

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
    print("\n[1] Running full parameter scan (150 combos)...")
    scan_df, full_signal_cache = run_full_scan(closes)

    # ===== 2. Best parameters =====
    best_row   = scan_df.nlargest(1, "sharpe").iloc[0]
    best_cw    = int(best_row["corr_window"])
    best_rebal = int(best_row["rebal"])
    best_n     = int(best_row["n_pos"])
    best_dir   = best_row["direction"]

    # Best per direction
    best_low  = scan_df[scan_df["direction"] == "low_corr_long"].nlargest(1, "sharpe").iloc[0]
    best_high = scan_df[scan_df["direction"] == "high_corr_long"].nlargest(1, "sharpe").iloc[0]

    print(f"\n[2] Best params overall:          CW{best_cw}_R{best_rebal}_N{best_n}_{best_dir}")
    print(f"    Sharpe: {best_row['sharpe']:.3f}, Ann: {best_row['annual_ret']:.1%}, "
          f"DD: {best_row['max_dd']:.1%}, WR: {best_row['win_rate']:.1%}")
    print(f"    Best low_corr_long:  CW{int(best_low['corr_window'])}_R{int(best_low['rebal'])}_"
          f"N{int(best_low['n_pos'])} — Sharpe {best_low['sharpe']:.3f}")
    print(f"    Best high_corr_long: CW{int(best_high['corr_window'])}_R{int(best_high['rebal'])}_"
          f"N{int(best_high['n_pos'])} — Sharpe {best_high['sharpe']:.3f}")

    # ===== 3. Walk-forward — 4 equal folds (best params) =====
    print(f"\n[3] Walk-Forward Fixed Params...")
    wf_fixed = run_walk_forward_fixed(closes, full_signal_cache,
                                      best_cw, best_rebal, best_n, best_dir)

    # ===== 4. Walk-forward with parameter selection =====
    print(f"\n[4] Walk-Forward with Parameter Selection...")
    wf_selected = run_walk_forward_param_selection(closes)

    # ===== 5. Split-half test =====
    print(f"\n[5] Split-Half Test...")
    split_half = run_split_half(closes)

    # ===== 6. 70/30 Train/Test =====
    print(f"\n[6] 70/30 Train/Test Split...")
    train_test = run_train_test_split(closes)

    # ===== 7. Factor correlations (H-012, H-031) =====
    print(f"\n[7] Factor Correlations...")
    correlations = compute_factor_correlations(closes, best_cw, best_rebal, best_n, best_dir)

    # ===== 8. Fee sensitivity =====
    print(f"\n[8] Fee Sensitivity...")
    fee_results = run_fee_sensitivity(closes, best_cw, best_rebal, best_n, best_dir)

    # ===== 9. Final Summary =====
    pos_all  = (scan_df["sharpe"] > 0).sum()
    n_all    = len(scan_df)
    pos_pct  = pos_all / n_all
    mean_sh  = scan_df["sharpe"].mean()
    med_sh   = scan_df["sharpe"].median()

    print("\n" + "=" * 70)
    print("FINAL SUMMARY: H-100 Average Pairwise Correlation (Comovement Factor)")
    print("=" * 70)
    print(f"  Data: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"\n  -- PARAMETER SCAN --")
    print(f"  Total combos:             {n_all}")
    print(f"  Positive Sharpe:          {pos_all}/{n_all} ({pos_pct:.0%})")
    print(f"  Mean Sharpe:              {mean_sh:.3f}")
    print(f"  Median Sharpe:            {med_sh:.3f}")
    df_low  = scan_df[scan_df["direction"] == "low_corr_long"]
    df_high = scan_df[scan_df["direction"] == "high_corr_long"]
    print(f"  Direction A (low→long):   pos {(df_low['sharpe']>0).sum()}/{len(df_low)}, "
          f"mean Sharpe {df_low['sharpe'].mean():.3f}")
    print(f"  Direction B (high→long):  pos {(df_high['sharpe']>0).sum()}/{len(df_high)}, "
          f"mean Sharpe {df_high['sharpe'].mean():.3f}")
    print(f"\n  -- BEST PARAMS --")
    print(f"  Overall best:             CW{best_cw}_R{best_rebal}_N{best_n}_{best_dir}")
    print(f"  Sharpe: {best_row['sharpe']:.3f}, Ann: {best_row['annual_ret']:.1%}, "
          f"DD: {best_row['max_dd']:.1%}")

    print(f"\n  -- WALK-FORWARD (4 equal folds, fixed params) --")
    if wf_fixed is not None:
        print(f"  Positive folds:           {(wf_fixed['sharpe']>0).sum()}/{len(wf_fixed)}")
        print(f"  Mean OOS Sharpe:          {wf_fixed['sharpe'].mean():.3f}")
        print(f"  Mean OOS Ann Return:      {wf_fixed['annual_ret'].mean():.1%}")
    else:
        print("  Walk-forward did not complete.")

    print(f"\n  -- WALK-FORWARD (param selection per fold) --")
    if wf_selected is not None:
        print(f"  Positive OOS folds:       {(wf_selected['oos_sharpe']>0).sum()}/{len(wf_selected)}")
        print(f"  Mean OOS Sharpe:          {wf_selected['oos_sharpe'].mean():.3f}")
        print(f"  Mean OOS Ann Return:      {wf_selected['oos_annual_ret'].mean():.1%}")
    else:
        print("  Walk-forward (param selection) did not complete.")

    print(f"\n  -- SPLIT-HALF --")
    print(f"  Sharpe rank corr (H1 vs H2): {split_half['sharpe_correlation']:.3f}")
    print(f"  Both halves positive:         {split_half['both_positive_pct']:.0%}")
    print(f"  Half-1 mean Sharpe: {split_half['half1_mean_sharpe']:.3f}")
    print(f"  Half-2 mean Sharpe: {split_half['half2_mean_sharpe']:.3f}")

    print(f"\n  -- 70/30 TRAIN/TEST --")
    print(f"  Train best:  {train_test['train_best_params']} (IS Sharpe {train_test['train_sharpe']:.3f})")
    print(f"  OOS Sharpe:  {train_test['test_sharpe']:.3f}, "
          f"Ann: {train_test['test_annual_ret']:.1%}, DD: {train_test['test_max_dd']:.1%} "
          f"({train_test['test_n_days']} days OOS)")

    print(f"\n  -- FACTOR CORRELATIONS --")
    print(f"  H-100 vs H-012 (momentum): {correlations['h012_return_corr']}")
    print(f"  H-100 vs H-031 (size):     {correlations['h031_return_corr']}")

    print(f"\n  -- FEE SENSITIVITY (5 bps baseline RT) --")
    for fr in fee_results:
        print(f"    {fr['rt_bps']:3d} bps RT: Sharpe {fr['sharpe']:.3f}, "
              f"Ann {fr['annual_ret']:.1%}")

    # ===== Save results =====
    results_path = Path(__file__).resolve().parent / "results.json"
    output = {
        "hypothesis": "H-100",
        "title": "Average Pairwise Correlation (Comovement Factor)",
        "assets": list(closes.columns),
        "n_days": len(closes),
        "period_start": str(closes.index[0].date()),
        "period_end":   str(closes.index[-1].date()),
        "fee_bps_rt":   5,
        "param_scan": {
            "total_combos":         n_all,
            "positive_sharpe":      int(pos_all),
            "positive_pct":         round(float(pos_pct), 3),
            "mean_sharpe":          round(float(mean_sh), 3),
            "median_sharpe":        round(float(med_sh), 3),
            "dir_A_mean_sharpe":    round(float(df_low["sharpe"].mean()), 3),
            "dir_B_mean_sharpe":    round(float(df_high["sharpe"].mean()), 3),
        },
        "best_params": {
            "tag":       f"CW{best_cw}_R{best_rebal}_N{best_n}_{best_dir}",
            "corr_window": best_cw,
            "rebal":      best_rebal,
            "n_pos":      best_n,
            "direction":  best_dir,
            "sharpe":     float(best_row["sharpe"]),
            "annual_ret": float(best_row["annual_ret"]),
            "max_dd":     float(best_row["max_dd"]),
            "win_rate":   float(best_row["win_rate"]),
        },
        "walk_forward_fixed": wf_fixed.to_dict("records") if wf_fixed is not None else None,
        "walk_forward_selected": wf_selected.to_dict("records") if wf_selected is not None else None,
        "split_half": split_half,
        "train_test": train_test,
        "correlations": correlations,
        "fee_sensitivity": fee_results,
    }

    with open(results_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Results saved to {results_path}")
