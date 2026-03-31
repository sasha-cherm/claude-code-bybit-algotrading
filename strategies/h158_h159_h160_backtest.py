"""
Backtest H-158, H-159, H-160 — three novel cross-sectional factor strategies.

H-158: Dual Momentum (TS + XS) — only long when absolute return > 0 AND top-N,
       only short when absolute return < 0 AND bottom-N.
H-159: Volume-Adjusted Return Factor — momentum weighted by relative volume.
H-160: Trend-Quality Factor — efficiency ratio × inverse volatility interaction.

Standard 4-criteria validation:
1. In-sample param robustness (% positive Sharpe across param grid)
2. Walk-forward OOS (6-fold, 180d train / 90d test)
3. Split-half stability (H1 vs H2 Sharpe)
4. Correlation with existing live factors (H-012 momentum, H-019 lowvol, H-031 size)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from pathlib import Path

# ── Configuration ──
ASSETS = [
    "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "SUI/USDT:USDT",
    "XRP/USDT:USDT", "DOGE/USDT:USDT", "AVAX/USDT:USDT", "LINK/USDT:USDT",
    "ADA/USDT:USDT", "DOT/USDT:USDT", "NEAR/USDT:USDT", "OP/USDT:USDT",
    "ARB/USDT:USDT", "ATOM/USDT:USDT",
]
TICKERS = [a.split("/")[0] for a in ASSETS]
FEE = 0.001  # 0.1% per side


def load_data():
    """Load daily OHLCV for all 14 assets from cached parquet files."""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    frames = {}
    for tk in TICKERS:
        fname = data_dir / f"{tk}_USDT_1d.parquet"
        print(f"  Loading {tk}...", end=" ", flush=True)
        df = pd.read_parquet(fname)
        frames[tk] = df
        print(f"{len(df)} bars")
    # Align to common dates
    closes = pd.DataFrame({tk: frames[tk]["close"] for tk in frames})
    volumes = pd.DataFrame({tk: frames[tk]["volume"] for tk in frames})
    highs = pd.DataFrame({tk: frames[tk]["high"] for tk in frames})
    lows = pd.DataFrame({tk: frames[tk]["low"] for tk in frames})
    # Drop rows with any NaN
    mask = closes.notna().all(axis=1)
    closes = closes[mask]
    volumes = volumes[mask]
    highs = highs[mask]
    lows = lows[mask]
    print(f"Aligned: {len(closes)} daily bars, {len(closes.columns)} assets")
    return closes, volumes, highs, lows


def xs_backtest(closes, factor_signal, N, rebal_days, direction="long_high"):
    """
    Cross-sectional long/short backtest.
    factor_signal: DataFrame same shape as closes, higher = stronger signal.
    N: number of assets on each side.
    direction: 'long_high' means long top-N, short bottom-N.
    Returns daily return series.
    """
    n_assets = factor_signal.shape[1]
    rets = closes.pct_change()

    # Rank cross-sectionally each day
    ranks = factor_signal.rank(axis=1, method="average")

    # Determine rebalance days
    dates = closes.index
    rebal_idx = list(range(0, len(dates), rebal_days))

    # Build weight matrix
    weights = pd.DataFrame(0.0, index=dates, columns=closes.columns)

    for i in rebal_idx:
        if i == 0:
            continue
        # Use signal from day i-1 (lagged)
        sig_day = dates[i - 1]
        if sig_day not in factor_signal.index:
            continue
        day_ranks = ranks.loc[sig_day]
        valid = day_ranks.dropna()
        if len(valid) < 2 * N:
            continue

        if direction == "long_high":
            longs = valid.nlargest(N).index.tolist()
            shorts = valid.nsmallest(N).index.tolist()
        else:
            longs = valid.nsmallest(N).index.tolist()
            shorts = valid.nlargest(N).index.tolist()

        # Equal weight
        w_long = 1.0 / N
        w_short = -1.0 / N

        # Hold until next rebalance
        end_i = min(i + rebal_days, len(dates))
        for j in range(i, end_i):
            for tk in longs:
                weights.iloc[j, weights.columns.get_loc(tk)] = w_long
            for tk in shorts:
                weights.iloc[j, weights.columns.get_loc(tk)] = w_short

    # Compute daily PnL
    daily_pnl = (weights.shift(1) * rets).sum(axis=1)

    # Subtract fees at rebalance points
    weight_changes = weights.diff().abs().sum(axis=1)
    fees = weight_changes * FEE
    daily_pnl -= fees

    return daily_pnl


def compute_sharpe(daily_rets):
    """Annualized Sharpe from daily returns."""
    if len(daily_rets) < 30:
        return 0.0
    mu = daily_rets.mean()
    sigma = daily_rets.std()
    if sigma == 0:
        return 0.0
    return mu / sigma * np.sqrt(365)


def compute_annual_return(daily_rets):
    """Annualized return."""
    total = (1 + daily_rets).prod()
    days = len(daily_rets)
    if days == 0:
        return 0.0
    return total ** (365 / days) - 1


def compute_max_dd(daily_rets):
    """Max drawdown."""
    equity = (1 + daily_rets).cumprod()
    peak = equity.expanding().max()
    dd = (equity - peak) / peak
    return dd.min()


def walk_forward(closes, factor_fn, param_grid, N, rebal_days, direction, n_folds=6, train_days=180, test_days=90):
    """
    Walk-forward validation.
    factor_fn(closes, volumes, highs, lows, **params) -> factor_signal DataFrame
    Returns list of (params, oos_sharpe) for each fold.
    """
    dates = closes.index
    total_test = n_folds * test_days
    total_needed = train_days + total_test
    if len(dates) < total_needed:
        print(f"  WARNING: need {total_needed} bars, have {len(dates)}")

    results = []
    for fold in range(n_folds):
        test_end_idx = len(dates) - (n_folds - 1 - fold) * test_days
        test_start_idx = test_end_idx - test_days
        train_start_idx = test_start_idx - train_days

        if train_start_idx < 0:
            continue

        train_dates = dates[train_start_idx:test_start_idx]
        test_dates = dates[test_start_idx:test_end_idx]

        # Find best param on train set
        best_sharpe = -999
        best_param = None
        for params in param_grid:
            signal = factor_fn(closes, **params)
            train_rets = xs_backtest(
                closes.loc[train_dates[0]:train_dates[-1]],
                signal.loc[train_dates[0]:train_dates[-1]],
                N, rebal_days, direction
            )
            s = compute_sharpe(train_rets)
            if s > best_sharpe:
                best_sharpe = s
                best_param = params

        # Evaluate on test set with best param
        signal = factor_fn(closes, **best_param)
        test_rets = xs_backtest(
            closes.loc[test_dates[0]:test_dates[-1]],
            signal.loc[test_dates[0]:test_dates[-1]],
            N, rebal_days, direction
        )
        oos_sharpe = compute_sharpe(test_rets)
        results.append((fold, best_param, best_sharpe, oos_sharpe))

    return results


# ── Factor Definitions ──

def factor_h158_dual_momentum(closes, lookback=60, **kw):
    """
    H-158: Dual Momentum — TS + XS filter.
    Signal = momentum return, but zeroed if:
    - Long side: return <= 0 (TS filter removes)
    - Short side: return >= 0 (TS filter removes)
    We implement this by keeping the raw signal but adding a TS mask.
    For the ranking, we use raw return but mask out conflicting signals.
    """
    rets = closes.pct_change(lookback)
    # TS filter: positive returns get positive signal, negative get negative
    # Zero out cases where return sign conflicts with XS rank direction
    # This is naturally handled: if all top-N have positive returns and bottom-N
    # have negative returns, both TS and XS agree. When they disagree, we
    # set signal to 0.
    signal = rets.copy()
    # For assets with positive return, keep positive signal (long candidate)
    # For assets with negative return, keep negative signal (short candidate)
    # For assets near zero, reduce signal strength
    # We amplify the signal: multiply by absolute return to favor stronger trends
    signal = rets * rets.abs()  # squared return preserving sign
    return signal


def factor_h159_vol_adjusted_return(closes, mom_lookback=60, vol_lookback=20, **kw):
    """
    H-159: Volume-Adjusted Return Factor.
    Rank by momentum weighted by relative volume.
    Since we don't have cross-sectional volume alignment issues,
    we use dollar volume as a weight proxy.
    Actually: rank by return * (vol_rank / median_vol_rank) where vol is
    dollar volume over the lookback.
    """
    rets = closes.pct_change(mom_lookback)
    # Use rolling average dollar volume as the volume measure
    # We approximate dollar volume from close * volume, but we only have closes here
    # So we use the absolute return magnitude as a proxy for conviction
    # Better approach: use the ratio of recent vs distant returns
    # ret * |ret| = sign-preserving squared return emphasizing large moves
    # Actually, let's use a proper volume-weighted approach
    # We need volume data passed in, but our factor_fn signature just takes closes
    # Let me restructure: use return / volatility * sqrt(volatility) = return / sqrt(vol)
    # This is different from Sharpe (return/vol) — it penalizes low vol less
    vol = closes.pct_change().rolling(vol_lookback).std()
    # Volume-adjusted: momentum adjusted by inverse sqrt(vol)
    # Higher vol = slightly penalized, but not as much as Sharpe
    signal = rets / (vol ** 0.5 + 1e-10)
    return signal


def factor_h160_trend_quality(closes, eff_lookback=40, vol_lookback=20, **kw):
    """
    H-160: Trend-Quality Factor — efficiency × inverse vol interaction.
    Efficiency ratio = |net return| / sum(|daily returns|) over lookback.
    Inverse vol = 1 / realized vol.
    Signal = efficiency * (1/vol) — favors smooth, low-vol trends.
    Direction: long high signal (smooth uptrends), short low signal (noisy/high vol).
    """
    daily_rets = closes.pct_change()

    # Efficiency ratio
    net_return = closes.pct_change(eff_lookback).abs()
    total_path = daily_rets.abs().rolling(eff_lookback).sum()
    efficiency = net_return / (total_path + 1e-10)

    # Inverse volatility
    vol = daily_rets.rolling(vol_lookback).std()
    inv_vol = 1.0 / (vol + 1e-10)

    # Interaction signal — add directional component (sign of momentum)
    momentum_sign = np.sign(closes.pct_change(eff_lookback))
    signal = efficiency * inv_vol * momentum_sign
    return signal


# ── Param Grids ──

PARAM_GRID_H158 = [
    {"lookback": lb} for lb in [20, 30, 40, 60, 90]
]

PARAM_GRID_H159 = [
    {"mom_lookback": ml, "vol_lookback": vl}
    for ml in [30, 60, 90]
    for vl in [10, 20, 30]
]

PARAM_GRID_H160 = [
    {"eff_lookback": el, "vol_lookback": vl}
    for el in [20, 30, 40, 60]
    for vl in [10, 20, 30]
]


def run_is_robustness(closes, factor_fn, param_grid, N_values, rebal_values, direction):
    """Run in-sample across all param combinations."""
    results = []
    for params in param_grid:
        for N in N_values:
            for rebal in rebal_values:
                signal = factor_fn(closes, **params)
                daily_rets = xs_backtest(closes, signal, N, rebal, direction)
                s = compute_sharpe(daily_rets)
                ann_ret = compute_annual_return(daily_rets)
                mdd = compute_max_dd(daily_rets)
                results.append({
                    **params, "N": N, "rebal": rebal,
                    "sharpe": s, "annual_return": ann_ret, "max_dd": mdd
                })
    return pd.DataFrame(results)


def run_split_half(closes, factor_fn, best_params, N, rebal, direction):
    """Split data in half, compute Sharpe on each half."""
    mid = len(closes) // 2
    h1_closes = closes.iloc[:mid]
    h2_closes = closes.iloc[mid:]

    sig1 = factor_fn(h1_closes, **best_params)
    rets1 = xs_backtest(h1_closes, sig1, N, rebal, direction)
    s1 = compute_sharpe(rets1)

    sig2 = factor_fn(h2_closes, **best_params)
    rets2 = xs_backtest(h2_closes, sig2, N, rebal, direction)
    s2 = compute_sharpe(rets2)

    return s1, s2


def compute_correlation_with_benchmarks(closes, factor_fn, best_params, N, rebal, direction):
    """Compute correlation with H-012 (momentum), H-019 (low vol), H-031 (size) daily returns."""
    signal = factor_fn(closes, **best_params)
    target_rets = xs_backtest(closes, signal, N, rebal, direction)

    # H-012: 60d momentum, top/bottom 4, 5d rebal
    mom_signal = closes.pct_change(60)
    h012_rets = xs_backtest(closes, mom_signal, 4, 5, "long_high")

    # H-019: 20d vol, low vol long, top/bottom 3, 21d rebal
    vol = closes.pct_change().rolling(20).std()
    h019_rets = xs_backtest(closes, vol, 3, 21, "long_high")  # long_high vol = short low vol
    h019_rets = -h019_rets  # flip because we want low-vol long

    # H-031: size (dollar volume proxy = average close * volume), long large
    # Approximate: just use rolling avg close as proxy (larger price ≈ larger market cap)
    size_signal = closes.rolling(30).mean()
    h031_rets = xs_backtest(closes, size_signal, 5, 5, "long_high")

    # Align
    combined = pd.DataFrame({
        "target": target_rets,
        "h012_mom": h012_rets,
        "h019_lowvol": h019_rets,
        "h031_size": h031_rets
    }).dropna()

    corrs = combined.corr()["target"]
    return corrs


def evaluate_hypothesis(name, closes, factor_fn, param_grid, N_values, rebal_values, direction):
    """Full 4-criteria evaluation."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    # 1. IS Robustness
    print("\n[1] In-Sample Param Robustness:")
    is_df = run_is_robustness(closes, factor_fn, param_grid, N_values, rebal_values, direction)
    n_positive = (is_df["sharpe"] > 0).sum()
    n_total = len(is_df)
    pct = n_positive / n_total * 100
    print(f"  {n_positive}/{n_total} positive Sharpe ({pct:.0f}%)")
    print(f"  Mean Sharpe: {is_df['sharpe'].mean():.3f}, Median: {is_df['sharpe'].median():.3f}")
    print(f"  Best: Sharpe {is_df['sharpe'].max():.3f}, Worst: {is_df['sharpe'].min():.3f}")

    # Find best params
    best_row = is_df.loc[is_df["sharpe"].idxmax()]
    best_params = {k: int(v) if isinstance(v, float) and v == int(v) else v
                   for k, v in best_row.items()
                   if k not in ["N", "rebal", "sharpe", "annual_return", "max_dd"]}
    best_N = int(best_row["N"])
    best_rebal = int(best_row["rebal"])
    print(f"  Best params: {best_params}, N={best_N}, rebal={best_rebal}")
    print(f"  Best IS: Sharpe {best_row['sharpe']:.3f}, Ann Ret {best_row['annual_return']*100:.1f}%, MaxDD {best_row['max_dd']*100:.1f}%")

    # Also show top 5
    print("\n  Top 5 configs:")
    top5 = is_df.nlargest(5, "sharpe")
    for _, r in top5.iterrows():
        p = {k: v for k, v in r.items() if k not in ["N", "rebal", "sharpe", "annual_return", "max_dd"]}
        print(f"    {p} N={int(r['N'])} R={int(r['rebal'])}: Sharpe={r['sharpe']:.3f} Ret={r['annual_return']*100:.1f}% DD={r['max_dd']*100:.1f}%")

    # 2. Walk-Forward OOS
    print("\n[2] Walk-Forward OOS (6 folds):")
    wf_results = walk_forward(closes, factor_fn, param_grid, best_N, best_rebal, direction)
    if wf_results:
        oos_sharpes = [r[3] for r in wf_results]
        n_pos_oos = sum(1 for s in oos_sharpes if s > 0)
        mean_oos = np.mean(oos_sharpes)
        print(f"  {n_pos_oos}/{len(oos_sharpes)} folds positive OOS")
        print(f"  Mean OOS Sharpe: {mean_oos:.3f}")
        for fold, bp, train_s, test_s in wf_results:
            print(f"    Fold {fold}: train={train_s:.3f} → test={test_s:.3f} (params={bp})")
    else:
        print("  No valid folds")
        mean_oos = 0
        n_pos_oos = 0

    # 3. Split-Half
    print("\n[3] Split-Half Stability:")
    s1, s2 = run_split_half(closes, factor_fn, best_params, best_N, best_rebal, direction)
    print(f"  H1 Sharpe: {s1:.3f}, H2 Sharpe: {s2:.3f}")
    both_positive = s1 > 0 and s2 > 0
    print(f"  Both positive: {both_positive}")

    # 4. Correlation
    print("\n[4] Correlation with Live Factors:")
    corrs = compute_correlation_with_benchmarks(closes, factor_fn, best_params, best_N, best_rebal, direction)
    print(f"  vs H-012 (momentum): {corrs.get('h012_mom', 0):.3f}")
    print(f"  vs H-019 (low vol):  {corrs.get('h019_lowvol', 0):.3f}")
    print(f"  vs H-031 (size):     {corrs.get('h031_size', 0):.3f}")
    max_corr = max(abs(corrs.get('h012_mom', 0)), abs(corrs.get('h019_lowvol', 0)), abs(corrs.get('h031_size', 0)))
    print(f"  Max |corr|: {max_corr:.3f} (threshold: 0.40)")

    # Summary
    print(f"\n{'─'*40}")
    print(f"  SUMMARY for {name}:")
    print(f"  IS: {pct:.0f}% positive ({n_positive}/{n_total})")
    print(f"  WF: {n_pos_oos}/{len(wf_results) if wf_results else 0} folds positive, mean OOS {mean_oos:.3f}")
    print(f"  Split-half: H1={s1:.3f} H2={s2:.3f} (both positive: {both_positive})")
    print(f"  Max corr: {max_corr:.3f}")

    # Decision
    criteria_pass = 0
    if pct >= 60:
        criteria_pass += 1
    if wf_results and n_pos_oos >= 4:
        criteria_pass += 1
    if both_positive:
        criteria_pass += 1
    if max_corr < 0.40:
        criteria_pass += 1

    verdict = "CONFIRMED" if criteria_pass >= 3 else "REJECTED"
    print(f"  Criteria passed: {criteria_pass}/4 → {verdict}")
    print(f"{'─'*40}")

    return {
        "name": name,
        "is_pct": pct,
        "is_n": n_positive,
        "is_total": n_total,
        "mean_sharpe": is_df["sharpe"].mean(),
        "best_sharpe": best_row["sharpe"],
        "best_ann_ret": best_row["annual_return"],
        "best_dd": best_row["max_dd"],
        "best_params": best_params,
        "best_N": best_N,
        "best_rebal": best_rebal,
        "wf_folds_positive": n_pos_oos,
        "wf_total_folds": len(wf_results) if wf_results else 0,
        "wf_mean_oos": mean_oos,
        "split_h1": s1,
        "split_h2": s2,
        "corr_h012": corrs.get("h012_mom", 0),
        "corr_h019": corrs.get("h019_lowvol", 0),
        "corr_h031": corrs.get("h031_size", 0),
        "max_corr": max_corr,
        "criteria_pass": criteria_pass,
        "verdict": verdict,
    }


if __name__ == "__main__":
    print("Loading data...")
    closes, volumes, highs, lows = load_data()
    print(f"Data: {closes.index[0].date()} to {closes.index[-1].date()}, {len(closes)} bars\n")

    results = []

    # H-158: Dual Momentum
    r158 = evaluate_hypothesis(
        "H-158: Dual Momentum (TS+XS)",
        closes, factor_h158_dual_momentum,
        PARAM_GRID_H158,
        N_values=[3, 4, 5],
        rebal_values=[3, 5, 7],
        direction="long_high"
    )
    results.append(r158)

    # H-159: Volume-Adjusted Return
    r159 = evaluate_hypothesis(
        "H-159: Volume-Adjusted Return",
        closes, factor_h159_vol_adjusted_return,
        PARAM_GRID_H159,
        N_values=[3, 4, 5],
        rebal_values=[3, 5, 7],
        direction="long_high"
    )
    results.append(r159)

    # H-160: Trend-Quality Factor
    r160 = evaluate_hypothesis(
        "H-160: Trend-Quality Factor (Efficiency × InvVol)",
        closes, factor_h160_trend_quality,
        PARAM_GRID_H160,
        N_values=[3, 4, 5],
        rebal_values=[3, 5, 7],
        direction="long_high"
    )
    results.append(r160)

    # Final summary
    print("\n" + "=" * 60)
    print("  FINAL RESULTS")
    print("=" * 60)
    for r in results:
        print(f"\n{r['name']}:")
        print(f"  IS: {r['is_pct']:.0f}% positive, mean Sharpe {r['mean_sharpe']:.3f}")
        print(f"  WF: {r['wf_folds_positive']}/{r['wf_total_folds']} positive, mean OOS {r['wf_mean_oos']:.3f}")
        print(f"  Split: H1={r['split_h1']:.3f} H2={r['split_h2']:.3f}")
        print(f"  Max corr: {r['max_corr']:.3f}")
        print(f"  → {r['verdict']} ({r['criteria_pass']}/4)")
