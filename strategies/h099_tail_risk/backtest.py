"""
H-099: Tail Risk Factor (CVaR)

For each asset, compute Conditional Value at Risk (CVaR) — the average of the
worst X% of daily log returns over a lookback window.

Two directions tested:
  A) risk_premium: Long WORST tail risk (most negative CVaR), short BEST.
     Hypothesis: high tail risk = higher expected return as compensation.
  B) contrarian:  Long BEST tail risk (least negative CVaR), short WORST.
     Hypothesis: lottery-seeking investors overprice tail-risk assets.

Dollar-neutral, equal-weighted long/short legs.

Validation: full parameter scan (300 combos), walk-forward (4 folds),
walk-forward with param selection, split-half, H-012 correlation, fee sensitivity.
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

FEE_RATE = 0.0006        # 6 bps taker fee (baseline)
INITIAL_CAPITAL = 10_000.0

# ---- Parameter grid (300 combinations) ----
LOOKBACKS     = [20, 30, 40, 60, 90]        # CVaR lookback window (days)
REBAL_FREQS   = [3, 5, 7, 10, 14]           # rebalance every N days
N_LONGS       = [3, 4, 5]                   # top/bottom N per side
PERCENTILES   = [5, 10]                     # worst X% of returns for CVaR
DIRECTIONS    = ["risk_premium", "contrarian"]

# Walk-forward config
WF_FOLDS = 4
WF_TRAIN  = 300   # training days per fold
WF_TEST   = 90    # out-of-sample days per fold
WF_STEP   = 90    # how much to slide forward per fold


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


def build_close_matrix(daily):
    """Align all assets to a common date index using close prices."""
    frames = {}
    for sym, df in daily.items():
        col = "close" if "close" in df.columns else df.columns[3]
        frames[sym] = df[col]
    closes = pd.DataFrame(frames)
    closes = closes.sort_index()
    closes = closes.dropna(how="all")
    # Forward-fill short gaps (max 3 days)
    closes = closes.ffill(limit=3)
    # Drop any remaining rows with too few valid assets
    closes = closes.dropna(thresh=len(closes.columns) // 2 + 1)
    print(f"\n  Close matrix: {closes.shape[0]} days × {closes.shape[1]} assets")
    print(f"  Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    return closes


# =========================================================================
# CVaR factor computation
# =========================================================================

def compute_cvar_factor(closes, lookback, percentile):
    """
    Compute CVaR factor for all assets on all dates.

    For each asset on each day t:
      1. Get log returns over [t-lookback, t)
      2. Sort ascending
      3. CVaR = mean of bottom `percentile`% of those returns

    Returns DataFrame with same index/columns as closes.
    CVaR values are negative (worse = more negative).
    """
    log_returns = np.log(closes / closes.shift(1))
    factor = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)

    k = max(2, int(np.floor(lookback * percentile / 100.0)))  # number of tail obs

    for col in closes.columns:
        rets = log_returns[col].values
        n = len(rets)
        vals = np.full(n, np.nan)

        for i in range(lookback, n):
            window = rets[i - lookback:i]
            window = window[~np.isnan(window)]
            if len(window) < k + 1:
                continue
            sorted_w = np.sort(window)
            cvar = sorted_w[:k].mean()   # mean of worst k returns (negative)
            vals[i] = cvar

        factor[col] = vals

    return factor


# =========================================================================
# Cross-sectional factor backtester
# =========================================================================

def compute_metrics(equity_series):
    """Compute standard metrics from equity curve."""
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "win_rate": 0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "win_rate": round(n_pos / n_total, 4) if n_total > 0 else 0,
    }


def run_xs_factor(closes, ranking_series, rebal_freq, n_long,
                  direction="risk_premium", fee_rate=FEE_RATE, warmup=65,
                  n_short=None):
    """
    Generic cross-sectional factor backtester.

    direction="risk_premium": Long bottom (most negative CVaR), short top.
    direction="contrarian":   Long top (least negative CVaR), short bottom.

    ranking_series contains raw CVaR values (negative numbers).
    For risk_premium: sort ascending → longs are index[:n_long] (most negative).
    For contrarian:   sort descending → longs are index[:n_long] (least negative).
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
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = ranking_series.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            if direction == "risk_premium":
                # Sort ascending: most negative CVaR first → those go long
                sorted_asc = valid.sort_values(ascending=True)
                longs = sorted_asc.index[:n_long]
                shorts = sorted_asc.index[-n_short:]
            else:
                # contrarian: sort descending → least negative (best) CVaR first → long
                sorted_desc = valid.sort_values(ascending=False)
                longs = sorted_desc.index[:n_long]
                shorts = sorted_desc.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * fee_rate

            port_ret = (new_weights * log_rets).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count += 1
            prev_weights = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"] = eq_series
    return metrics


def run_xs_factor_with_fee(closes, ranking_series, rebal_freq, n_long,
                            fee_rate, direction="risk_premium",
                            warmup=65, n_short=None):
    """Same as run_xs_factor but with configurable fee rate (no equity stored)."""
    if n_short is None:
        n_short = n_long

    n = len(closes)
    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL
    prev_weights = pd.Series(0.0, index=closes.columns)

    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = ranking_series.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                equity[i] = equity[i - 1] * np.exp((prev_weights * log_rets).sum())
                continue

            if direction == "risk_premium":
                sorted_asc = valid.sort_values(ascending=True)
                longs = sorted_asc.index[:n_long]
                shorts = sorted_asc.index[-n_short:]
            else:
                sorted_desc = valid.sort_values(ascending=False)
                longs = sorted_desc.index[:n_long]
                shorts = sorted_desc.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            turnover = (new_weights - prev_weights).abs().sum() / 2
            port_ret = (new_weights * log_rets).sum() - turnover * fee_rate
            prev_weights = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["equity"] = eq_series
    return metrics


# =========================================================================
# Full parameter scan
# =========================================================================

def run_full_scan(closes):
    """
    Sweep all 300 parameter combinations (5 LB × 5 R × 3 N × 2 pct × 2 dir).
    """
    print("\n" + "=" * 70)
    print("H-099: TAIL RISK FACTOR (CVaR) -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE * 10000:.0f} bps per trade")

    # Pre-compute CVaR rankings for all (lookback, percentile) combinations
    print("\n  Pre-computing CVaR factors for all (lookback, percentile) combos...")
    cvar_cache = {}
    for lb, pct in product(LOOKBACKS, PERCENTILES):
        key = (lb, pct)
        print(f"    LB={lb}, pct={pct}%...", end=" ", flush=True)
        cvar_cache[key] = compute_cvar_factor(closes, lb, pct)
        valid_count = cvar_cache[key].notna().sum().sum()
        print(f"done ({valid_count} valid values)")

    results = []
    total_combos = len(LOOKBACKS) * len(REBAL_FREQS) * len(N_LONGS) * len(PERCENTILES) * len(DIRECTIONS)
    print(f"\n  Running {total_combos} parameter combinations...")
    combo_idx = 0

    for lb, rebal, n_long, pct, direction in product(
            LOOKBACKS, REBAL_FREQS, N_LONGS, PERCENTILES, DIRECTIONS):
        ranking = cvar_cache[(lb, pct)]
        warmup = lb + 5

        res = run_xs_factor(closes, ranking, rebal, n_long,
                            direction=direction, warmup=warmup)
        tag = f"LB{lb}_R{rebal}_N{n_long}_P{pct}_{direction[:4]}"
        results.append({
            "tag": tag,
            "lookback": lb,
            "rebal": rebal,
            "n_long": n_long,
            "percentile": pct,
            "direction": direction,
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
            "n_rebalances": res["n_rebalances"],
        })
        combo_idx += 1
        if combo_idx % 50 == 0:
            print(f"    ...{combo_idx}/{total_combos} done")

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]

    print(f"\n  Total parameter combos: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"  Best Sharpe:  {df['sharpe'].max():.3f}")
    print(f"  Worst Sharpe: {df['sharpe'].min():.3f}")

    # Direction breakdown
    for dir_ in DIRECTIONS:
        sub = df[df["direction"] == dir_]
        pos = (sub["sharpe"] > 0).sum()
        print(f"\n  Direction={dir_}:")
        print(f"    Positive Sharpe: {pos}/{len(sub)} ({pos/len(sub):.0%})")
        print(f"    Mean Sharpe: {sub['sharpe'].mean():.3f}")
        print(f"    Best Sharpe: {sub['sharpe'].max():.3f}")

    # Percentile breakdown
    for pct in PERCENTILES:
        sub = df[df["percentile"] == pct]
        pos = (sub["sharpe"] > 0).sum()
        print(f"\n  Percentile={pct}%:")
        print(f"    Positive Sharpe: {pos}/{len(sub)} ({pos/len(sub):.0%})")
        print(f"    Mean Sharpe: {sub['sharpe'].mean():.3f}")

    # Top 20 results
    print("\n  Top 20 parameter combos by Sharpe:")
    for _, row in df.sort_values("sharpe", ascending=False).head(20).iterrows():
        marker = "**" if row["sharpe"] > 0.5 else "  "
        print(f"  {marker} {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}, Trades {row['n_trades']}")

    return df, cvar_cache


# =========================================================================
# Walk-Forward Validation (fixed best params, 4 folds)
# =========================================================================

def run_walk_forward(closes, lookback, rebal, n_long, percentile, direction):
    """
    Walk-forward with fixed params: 4 folds, 300d train, 90d test.
    """
    print(f"\n  Walk-Forward (Fixed Params): "
          f"LB{lookback}_R{rebal}_N{n_long}_P{percentile}_{direction}")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, {WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx   = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0 or test_end_idx <= test_start_idx:
            print(f"    Fold {fold+1}: insufficient data, skipping")
            break

        test_closes = closes.iloc[test_start_idx:test_end_idx]
        if len(test_closes) < 30:
            print(f"    Fold {fold+1}: test too short ({len(test_closes)} days), skipping")
            break

        test_ranking = compute_cvar_factor(test_closes, lookback, percentile)
        warmup = min(lookback + 5, len(test_closes) // 2)

        res = run_xs_factor(test_closes, test_ranking, rebal, n_long,
                            direction=direction, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
        })
        print(f"    Fold {fold+1}: {test_closes.index[0].date()} → {test_closes.index[-1].date()}, "
              f"Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df_wf = pd.DataFrame(fold_results)
    pos = (df_wf["sharpe"] > 0).sum()
    print(f"\n    Positive folds: {pos}/{len(df_wf)}")
    print(f"    Mean OOS Sharpe: {df_wf['sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df_wf['annual_ret'].mean():.1%}")
    print(f"    Worst OOS DD: {df_wf['max_dd'].max():.1%}")
    return df_wf


# =========================================================================
# Walk-Forward with Parameter Selection
# =========================================================================

def run_walk_forward_param_selection(closes):
    """
    Walk-forward with in-sample parameter selection.
    For each fold, select best (lookback, rebal, n_long, percentile, direction)
    on train set, then evaluate on test set.
    """
    print(f"\n  Walk-Forward with In-Sample Parameter Selection")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, {WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx    = n - fold * WF_STEP
        test_start_idx  = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0:
            break

        train_closes = closes.iloc[train_start_idx:test_start_idx]
        test_closes  = closes.iloc[test_start_idx:test_end_idx]

        if len(test_closes) < 30 or len(train_closes) < 100:
            break

        # Find best params on train set
        best_sharpe = -999
        best_params = None
        for lb, rebal, n_long, pct, direction in product(
                LOOKBACKS, REBAL_FREQS, N_LONGS, PERCENTILES, DIRECTIONS):
            warmup = lb + 5
            if warmup >= len(train_closes) - 20:
                continue
            ranking = compute_cvar_factor(train_closes, lb, pct)
            res = run_xs_factor(train_closes, ranking, rebal, n_long,
                                direction=direction, warmup=warmup)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_params = (lb, rebal, n_long, pct, direction)

        if best_params is None:
            break

        lb, rebal, n_long, pct, direction = best_params
        test_ranking = compute_cvar_factor(test_closes, lb, pct)
        warmup = min(lb + 5, len(test_closes) // 2)
        res = run_xs_factor(test_closes, test_ranking, rebal, n_long,
                            direction=direction, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "train_best_params": f"LB{lb}_R{rebal}_N{n_long}_P{pct}_{direction[:4]}",
            "train_sharpe": round(best_sharpe, 3),
            "oos_sharpe": res["sharpe"],
            "oos_annual_ret": res["annual_ret"],
            "oos_max_dd": res["max_dd"],
        })
        print(f"    Fold {fold+1}: train best=LB{lb}_R{rebal}_N{n_long}_P{pct}_{direction[:4]} "
              f"(IS Sharpe {best_sharpe:.3f}), "
              f"OOS Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}")

    if not fold_results:
        return None

    df_wfps = pd.DataFrame(fold_results)
    pos = (df_wfps["oos_sharpe"] > 0).sum()
    print(f"\n    Positive OOS folds: {pos}/{len(df_wfps)}")
    print(f"    Mean OOS Sharpe: {df_wfps['oos_sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df_wfps['oos_annual_ret'].mean():.1%}")
    return df_wfps


# =========================================================================
# Split-Half Validation
# =========================================================================

def run_split_half(closes):
    """Split into two halves, run full param scan on each, compare Sharpes."""
    n = len(closes)
    mid = n // 2
    half1 = closes.iloc[:mid]
    half2 = closes.iloc[mid:]

    print(f"\n  Split-Half Validation")
    print(f"  Half 1: {half1.index[0].date()} to {half1.index[-1].date()} ({len(half1)} days)")
    print(f"  Half 2: {half2.index[0].date()} to {half2.index[-1].date()} ({len(half2)} days)")

    results_h1 = []
    results_h2 = []

    for lb, rebal, n_long, pct, direction in product(
            LOOKBACKS, REBAL_FREQS, N_LONGS, PERCENTILES, DIRECTIONS):
        warmup = lb + 5
        r1 = compute_cvar_factor(half1, lb, pct)
        r2 = compute_cvar_factor(half2, lb, pct)
        res1 = run_xs_factor(half1, r1, rebal, n_long, direction=direction, warmup=warmup)
        res2 = run_xs_factor(half2, r2, rebal, n_long, direction=direction, warmup=warmup)
        results_h1.append(res1["sharpe"])
        results_h2.append(res2["sharpe"])

    h1_arr = np.array(results_h1)
    h2_arr = np.array(results_h2)

    # Rank correlation
    from scipy.stats import spearmanr
    corr, _ = spearmanr(h1_arr, h2_arr)
    both_pos = ((h1_arr > 0) & (h2_arr > 0)).sum()

    print(f"  Spearman rank corr (Sharpe, H1 vs H2): {corr:.3f}")
    print(f"  Both halves positive: {both_pos}/{len(h1_arr)} ({both_pos/len(h1_arr):.0%})")
    print(f"  Half 1 mean Sharpe: {h1_arr.mean():.3f}")
    print(f"  Half 2 mean Sharpe: {h2_arr.mean():.3f}")

    return {
        "spearman_corr": round(float(corr), 3),
        "both_positive_pct": round(both_pos / len(h1_arr), 3),
        "half1_mean_sharpe": round(float(h1_arr.mean()), 3),
        "half2_mean_sharpe": round(float(h2_arr.mean()), 3),
    }


# =========================================================================
# Correlation with H-012 Momentum (LB60, R5, N4)
# =========================================================================

def compute_h012_correlation(closes, lookback, rebal, n_long, percentile, direction):
    """Compute daily return correlation between CVaR factor and H-012 momentum."""
    print(f"\n  Correlation with H-012 (60d Momentum)")

    # Run CVaR factor with best params
    cvar_ranking = compute_cvar_factor(closes, lookback, percentile)
    warmup_cvar = lookback + 5
    res_cvar = run_xs_factor(closes, cvar_ranking, rebal, n_long,
                             direction=direction, warmup=warmup_cvar)

    # Run H-012 momentum (60d lookback, rebal 5d, N=4), direction: long winners
    mom_ranking = closes.pct_change(60)
    # H-012: long top momentum (most positive), short bottom
    res_mom = run_xs_factor(closes, mom_ranking, 5, 4,
                            direction="contrarian", warmup=65)
    # Note: for momentum, "contrarian" with pct_change gives long top returners
    # because contrarian sorts descending → largest pct_change first = longs

    eq_cvar = res_cvar["equity"]
    eq_mom  = res_mom["equity"]

    rets_cvar = eq_cvar.pct_change().dropna()
    rets_mom  = eq_mom.pct_change().dropna()

    common = rets_cvar.index.intersection(rets_mom.index)
    if len(common) < 50:
        print("    Insufficient overlap for correlation")
        return 0.0

    corr = rets_cvar.loc[common].corr(rets_mom.loc[common])
    print(f"    Daily return correlation H-099 vs H-012: {corr:.3f}")
    print(f"    H-012 Momentum: Sharpe {res_mom['sharpe']:.3f}, Ann {res_mom['annual_ret']:.1%}")
    print(f"    H-099 CVaR:     Sharpe {res_cvar['sharpe']:.3f}, Ann {res_cvar['annual_ret']:.1%}")
    return round(corr, 3)


# =========================================================================
# Fee Robustness (5bps per leg = 10bps round-trip)
# =========================================================================

def run_fee_robustness(closes, lookback, rebal, n_long, percentile, direction):
    """Test performance across different fee levels."""
    print(f"\n  Fee Robustness (best: LB{lookback}_R{rebal}_N{n_long}_P{percentile}_{direction})")
    fee_levels = [0.0, 0.0003, 0.0005, 0.0006, 0.0010, 0.0015, 0.0020]

    ranking = compute_cvar_factor(closes, lookback, percentile)
    warmup = lookback + 5

    results = []
    for fee in fee_levels:
        res = run_xs_factor_with_fee(closes, ranking, rebal, n_long,
                                     fee_rate=fee, direction=direction, warmup=warmup)
        bps = fee * 10000
        print(f"    Fee {bps:.0f}bps: Sharpe {res['sharpe']:.3f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")
        results.append({
            "fee_bps": bps,
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        })

    # Specifically call out 5bps per leg
    r5 = [r for r in results if r["fee_bps"] == 5.0]
    if r5:
        print(f"\n    At 5bps/leg (task requirement): Sharpe {r5[0]['sharpe']:.3f}, "
              f"Ann {r5[0]['annual_ret']:.1%}")

    return results


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("H-099: Tail Risk Factor (CVaR)")
    print("=" * 70)

    # 1. Load data
    print("\n[1/7] Loading daily data...")
    daily = load_daily_data()
    closes = build_close_matrix(daily)

    if closes.shape[1] < 6:
        print("ERROR: Too few assets loaded. Aborting.")
        sys.exit(1)

    # 2. Full parameter scan (300 combos)
    print("\n[2/7] Full Parameter Scan...")
    scan_df, cvar_cache = run_full_scan(closes)

    # Identify best parameters overall
    best_row = scan_df.loc[scan_df["sharpe"].idxmax()]
    best_lb   = int(best_row["lookback"])
    best_r    = int(best_row["rebal"])
    best_n    = int(best_row["n_long"])
    best_pct  = int(best_row["percentile"])
    best_dir  = best_row["direction"]

    print(f"\n  BEST OVERALL: {best_row['tag']}")
    print(f"    Sharpe {best_row['sharpe']:.3f}, Ann {best_row['annual_ret']:.1%}, "
          f"DD {best_row['max_dd']:.1%}, WR {best_row['win_rate']:.1%}")

    # Best per direction
    for dir_ in DIRECTIONS:
        sub = scan_df[scan_df["direction"] == dir_]
        best_d = sub.loc[sub["sharpe"].idxmax()]
        print(f"\n  Best {dir_}: {best_d['tag']}")
        print(f"    Sharpe {best_d['sharpe']:.3f}, Ann {best_d['annual_ret']:.1%}, "
              f"DD {best_d['max_dd']:.1%}")

    # 3. Walk-Forward (fixed best params, 4 folds)
    print("\n[3/7] Walk-Forward Validation (Fixed Params)...")
    wf_df = run_walk_forward(closes, best_lb, best_r, best_n, best_pct, best_dir)

    # 4. Walk-Forward with Parameter Selection
    print("\n[4/7] Walk-Forward with Parameter Selection...")
    wfps_df = run_walk_forward_param_selection(closes)

    # 5. Split-Half Validation
    print("\n[5/7] Split-Half Validation...")
    sh_results = run_split_half(closes)

    # 6. Correlation with H-012
    print("\n[6/7] H-012 Momentum Correlation...")
    h012_corr = compute_h012_correlation(closes, best_lb, best_r, best_n, best_pct, best_dir)

    # 7. Fee Robustness
    print("\n[7/7] Fee Robustness...")
    fee_results = run_fee_robustness(closes, best_lb, best_r, best_n, best_pct, best_dir)

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("H-099 SUMMARY")
    print("=" * 70)

    pct_positive = len(scan_df[scan_df["sharpe"] > 0]) / len(scan_df)
    mean_sharpe  = scan_df["sharpe"].mean()

    print(f"\n  FULL SCAN ({len(scan_df)} combos):")
    print(f"    % Positive Sharpe:  {pct_positive:.0%}")
    print(f"    Mean Sharpe:        {mean_sharpe:.3f}")
    print(f"    Best Sharpe:        {scan_df['sharpe'].max():.3f}  ({best_row['tag']})")

    for dir_ in DIRECTIONS:
        sub = scan_df[scan_df["direction"] == dir_]
        pos = (sub["sharpe"] > 0).sum()
        print(f"    {dir_}: {pos}/{len(sub)} positive, mean Sharpe {sub['sharpe'].mean():.3f}")

    if wf_df is not None:
        pos_folds = (wf_df["sharpe"] > 0).sum()
        print(f"\n  WALK-FORWARD (Fixed Best Params):")
        print(f"    Positive folds:     {pos_folds}/{len(wf_df)}")
        print(f"    Mean OOS Sharpe:    {wf_df['sharpe'].mean():.3f}")
        print(f"    Mean OOS Ann Ret:   {wf_df['annual_ret'].mean():.1%}")

    if wfps_df is not None:
        pos_folds_ps = (wfps_df["oos_sharpe"] > 0).sum()
        print(f"\n  WALK-FORWARD (Param Selection):")
        print(f"    Positive folds:     {pos_folds_ps}/{len(wfps_df)}")
        print(f"    Mean OOS Sharpe:    {wfps_df['oos_sharpe'].mean():.3f}")
        print(f"    Mean OOS Ann Ret:   {wfps_df['oos_annual_ret'].mean():.1%}")

    print(f"\n  SPLIT-HALF:")
    print(f"    Spearman corr:      {sh_results['spearman_corr']:.3f}")
    print(f"    Both halves pos:    {sh_results['both_positive_pct']:.0%}")
    print(f"    H1 mean Sharpe:     {sh_results['half1_mean_sharpe']:.3f}")
    print(f"    H2 mean Sharpe:     {sh_results['half2_mean_sharpe']:.3f}")

    print(f"\n  H-012 CORRELATION:    {h012_corr:.3f}")

    fee_dict = {r["fee_bps"]: r for r in fee_results}
    if 5.0 in fee_dict:
        print(f"\n  FEE SENSITIVITY (5bps/leg):")
        print(f"    Sharpe at 0bps:  {fee_dict.get(0.0, {}).get('sharpe', float('nan')):.3f}")
        print(f"    Sharpe at 5bps:  {fee_dict[5.0]['sharpe']:.3f}")
        print(f"    Sharpe at 6bps:  {fee_dict.get(6.0, fee_dict.get(5.0, {})).get('sharpe', float('nan')):.3f}")

    # =========================================================================
    # Verdict
    # =========================================================================
    print("\n  VERDICT:")
    if pct_positive >= 0.55 and mean_sharpe >= 0.3 and wf_df is not None and wf_df["sharpe"].mean() >= 0.2:
        verdict = "PROMISING — candidate for further validation"
    elif pct_positive >= 0.4 and mean_sharpe >= 0.1:
        verdict = "WEAK SIGNAL — possible but not robust enough alone"
    else:
        verdict = "REJECTED — insufficient evidence of alpha"
    print(f"    {verdict}")
    print(f"    Best direction: {best_dir}")

    # =========================================================================
    # Save results
    # =========================================================================
    output_path = Path(__file__).parent / "results.json"
    results_dict = {
        "hypothesis": "H-099",
        "title": "Tail Risk Factor (CVaR)",
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "n_days": len(closes),
        "n_assets": len(closes.columns),
        "n_combos": len(scan_df),
        "pct_positive_sharpe": round(pct_positive, 4),
        "mean_sharpe": round(mean_sharpe, 4),
        "best_sharpe": round(float(scan_df["sharpe"].max()), 4),
        "best_params": best_row["tag"],
        "best_direction": best_dir,
        "direction_breakdown": {
            dir_: {
                "pct_positive": round((scan_df[scan_df["direction"] == dir_]["sharpe"] > 0).mean(), 4),
                "mean_sharpe": round(float(scan_df[scan_df["direction"] == dir_]["sharpe"].mean()), 4),
                "best_sharpe": round(float(scan_df[scan_df["direction"] == dir_]["sharpe"].max()), 4),
            }
            for dir_ in DIRECTIONS
        },
        "walk_forward_fixed": {
            "n_folds": len(wf_df) if wf_df is not None else 0,
            "positive_folds": int((wf_df["sharpe"] > 0).sum()) if wf_df is not None else 0,
            "mean_oos_sharpe": round(float(wf_df["sharpe"].mean()), 3) if wf_df is not None else None,
            "mean_oos_annual_ret": round(float(wf_df["annual_ret"].mean()), 4) if wf_df is not None else None,
        },
        "walk_forward_param_selection": {
            "n_folds": len(wfps_df) if wfps_df is not None else 0,
            "positive_folds": int((wfps_df["oos_sharpe"] > 0).sum()) if wfps_df is not None else 0,
            "mean_oos_sharpe": round(float(wfps_df["oos_sharpe"].mean()), 3) if wfps_df is not None else None,
        },
        "split_half": sh_results,
        "h012_correlation": h012_corr,
        "fee_sensitivity": fee_results,
        "verdict": verdict,
    }

    with open(output_path, "w") as f:
        json.dump(results_dict, f, indent=2)
    print(f"\n  Results saved to {output_path}")
    print("=" * 70)
