"""
H-087: Amihud Illiquidity Factor (Cross-Sectional)

The Amihud illiquidity ratio measures price impact per unit of dollar volume:
  ILLIQ = mean( |daily_return| / dollar_volume )  over L-day lookback

In equities, illiquid assets earn a premium (Amihud 2002). In crypto, the
relationship may reverse: liquid assets attract institutional flow and may
outperform. We test BOTH directions:
  (a) liquid_long  = long most-liquid (LOW Amihud), short least-liquid
  (b) illiquid_long = long least-liquid (HIGH Amihud), short most-liquid

Validation:
  - Full parameter grid scan (L x R x N x Direction)
  - 70/30 train/test split
  - Split-half stability
  - Walk-forward: 6 folds, 120d train / 90d test (per spec)
  - Walk-forward with in-sample parameter selection
  - Correlation with H-012 (momentum) and H-031 (size factor)
  - Sharpe computed at BOTH 8760 and 365 annualization
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

# =========================================================================
# Configuration
# =========================================================================

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.0006       # 6 bps taker fee on Bybit perps (round-trip ~12 bps)
INITIAL_CAPITAL = 10_000.0

# Parameter grid
LOOKBACKS = [10, 20, 30]            # Amihud lookback window (days)
REBAL_FREQS = [3, 5, 7]            # rebalance every N days
N_LONGS = [3, 4, 5]                # top/bottom N
DIRECTIONS = ["liquid_long", "illiquid_long"]

# Walk-forward config (per spec: 120d train / 90d test, 6 folds)
WF_FOLDS = 6
WF_TRAIN = 120
WF_TEST = 90
WF_STEP = 90


# =========================================================================
# Data Loading
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
# Amihud Illiquidity Ratio
# =========================================================================

def compute_amihud(closes, volumes, lookback):
    """
    Compute Amihud illiquidity ratio for each asset/day.

    ILLIQ_t = mean( |r_i| / DV_i ) for i in [t-L+1, t]

    where r_i = daily return (close-to-close), DV_i = close_i * volume_i.

    Higher value = more illiquid (larger price impact per dollar traded).
    Lower value  = more liquid.
    """
    # Daily absolute returns
    abs_returns = closes.pct_change().abs()

    # Dollar volume
    dollar_volume = closes * volumes

    # Replace zero dollar volume with NaN to avoid division by zero
    dollar_volume = dollar_volume.replace(0, np.nan)

    # Ratio: |return| / dollar_volume
    illiq_daily = abs_returns / dollar_volume

    # Replace inf with NaN
    illiq_daily = illiq_daily.replace([np.inf, -np.inf], np.nan)

    # Rolling mean over lookback window
    amihud = illiq_daily.rolling(lookback, min_periods=lookback).mean()

    return amihud


# =========================================================================
# Metrics
# =========================================================================

def compute_metrics(equity_series, periods_per_year=365):
    """Compute standard metrics from equity curve."""
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe_365": -99, "sharpe_8760": -99, "annual_ret": 0,
                "max_dd": 1.0, "win_rate": 0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    return {
        "sharpe_365": round(sharpe_ratio(rets, periods_per_year=365), 3),
        "sharpe_8760": round(sharpe_ratio(rets, periods_per_year=8760), 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "win_rate": round(n_pos / n_total, 4) if n_total > 0 else 0,
    }


# =========================================================================
# Cross-Sectional Factor Backtester
# =========================================================================

def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  warmup=65):
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
# Full Parameter Scan
# =========================================================================

def run_full_scan(closes, volumes):
    """Run all parameter combinations on the full period, both directions."""
    print("\n" + "=" * 70)
    print("H-087: AMIHUD ILLIQUIDITY FACTOR -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE*10000:.0f} bps per trade")
    print(f"  Directions: liquid_long (long low-Amihud), illiquid_long (long high-Amihud)")

    results = []
    for lookback, rebal, n_long, direction in product(LOOKBACKS, REBAL_FREQS,
                                                       N_LONGS, DIRECTIONS):
        amihud = compute_amihud(closes, volumes, lookback)
        warmup = lookback + 5

        if direction == "liquid_long":
            # Long MOST LIQUID (low Amihud) = rank by NEGATIVE Amihud
            # so highest rank = lowest Amihud = most liquid
            ranking = -amihud
        else:
            # Long LEAST LIQUID (high Amihud) = rank by Amihud directly
            ranking = amihud

        res = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup)
        tag = f"{direction}_L{lookback}_R{rebal}_N{n_long}"
        results.append({
            "tag": tag,
            "direction": direction,
            "lookback": lookback,
            "rebal": rebal,
            "n_long": n_long,
            "sharpe_365": res["sharpe_365"],
            "sharpe_8760": res["sharpe_8760"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
            "n_rebalances": res["n_rebalances"],
        })

    df = pd.DataFrame(results)
    positive = df[df["sharpe_365"] > 0]
    print(f"\n  Total parameter combos: {len(df)}")
    print(f"  Positive Sharpe (365): {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe (365): {df['sharpe_365'].mean():.3f}")
    print(f"  Median Sharpe (365): {df['sharpe_365'].median():.3f}")
    print(f"  Best Sharpe (365): {df['sharpe_365'].max():.3f}")
    print(f"  Worst Sharpe (365): {df['sharpe_365'].min():.3f}")

    # Per-direction breakdown
    for d in DIRECTIONS:
        sub = df[df["direction"] == d]
        pos = (sub["sharpe_365"] > 0).sum()
        print(f"\n  --- {d} ---")
        print(f"  Positive: {pos}/{len(sub)} ({pos/len(sub):.0%})")
        print(f"  Mean Sharpe (365): {sub['sharpe_365'].mean():.3f}")
        print(f"  Mean Sharpe (8760): {sub['sharpe_8760'].mean():.3f}")
        print(f"  Best: {sub.loc[sub['sharpe_365'].idxmax(), 'tag']} "
              f"Sharpe(365)={sub['sharpe_365'].max():.3f}, "
              f"Ann {sub.loc[sub['sharpe_365'].idxmax(), 'annual_ret']:.1%}, "
              f"DD {sub.loc[sub['sharpe_365'].idxmax(), 'max_dd']:.1%}")

    print("\n  All results sorted by Sharpe (365):")
    for _, row in df.sort_values("sharpe_365", ascending=False).iterrows():
        marker = "**" if row["sharpe_365"] > 0.5 else "  "
        print(f"  {marker} {row['tag']}: Sharpe(365) {row['sharpe_365']:.3f}, "
              f"Sharpe(8760) {row['sharpe_8760']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}, Trades {row['n_trades']}")

    return df


# =========================================================================
# 70/30 Train/Test Split
# =========================================================================

def run_train_test_split(closes, volumes, split_ratio=0.7):
    """Run parameter scan on 70% train, evaluate best on 30% test."""
    n = len(closes)
    split_idx = int(n * split_ratio)
    train_closes = closes.iloc[:split_idx]
    train_volumes = volumes.iloc[:split_idx]
    test_closes = closes.iloc[split_idx:]
    test_volumes = volumes.iloc[split_idx:]

    print(f"\n{'='*70}")
    print("70/30 Train/Test Split")
    print(f"{'='*70}")
    print(f"  Train: {train_closes.index[0].date()} to {train_closes.index[-1].date()} ({len(train_closes)} days)")
    print(f"  Test:  {test_closes.index[0].date()} to {test_closes.index[-1].date()} ({len(test_closes)} days)")

    # Find best params on train set (both directions)
    best_sharpe = -999
    best_params = None
    for lookback, rebal, n_long, direction in product(LOOKBACKS, REBAL_FREQS,
                                                       N_LONGS, DIRECTIONS):
        amihud = compute_amihud(train_closes, train_volumes, lookback)
        warmup = lookback + 5
        ranking = -amihud if direction == "liquid_long" else amihud
        res = run_xs_factor(train_closes, ranking, rebal, n_long, warmup=warmup)
        if res["sharpe_365"] > best_sharpe:
            best_sharpe = res["sharpe_365"]
            best_params = (lookback, rebal, n_long, direction)

    lookback, rebal, n_long, direction = best_params
    tag = f"{direction}_L{lookback}_R{rebal}_N{n_long}"
    print(f"  Train best: {tag} (Sharpe(365) {best_sharpe:.3f})")

    # Evaluate on test set
    test_amihud = compute_amihud(test_closes, test_volumes, lookback)
    test_ranking = -test_amihud if direction == "liquid_long" else test_amihud
    warmup = lookback + 5
    res_test = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=warmup)
    print(f"  Test result: Sharpe(365) {res_test['sharpe_365']:.3f}, "
          f"Sharpe(8760) {res_test['sharpe_8760']:.3f}, "
          f"Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}")

    return {
        "train_best_params": tag,
        "train_sharpe_365": round(best_sharpe, 3),
        "test_sharpe_365": res_test["sharpe_365"],
        "test_sharpe_8760": res_test["sharpe_8760"],
        "test_annual_ret": res_test["annual_ret"],
        "test_max_dd": res_test["max_dd"],
        "test_win_rate": res_test["win_rate"],
        "test_n_days": len(test_closes),
    }


# =========================================================================
# Split-Half Validation
# =========================================================================

def run_split_half(closes, volumes):
    """Split data into two halves, run scan on each, compare stability."""
    n = len(closes)
    mid = n // 2
    half1_closes = closes.iloc[:mid]
    half1_volumes = volumes.iloc[:mid]
    half2_closes = closes.iloc[mid:]
    half2_volumes = volumes.iloc[mid:]

    print(f"\n{'='*70}")
    print("Split-Half Validation")
    print(f"{'='*70}")
    print(f"  Half 1: {half1_closes.index[0].date()} to {half1_closes.index[-1].date()} ({len(half1_closes)} days)")
    print(f"  Half 2: {half2_closes.index[0].date()} to {half2_closes.index[-1].date()} ({len(half2_closes)} days)")

    results_h1 = []
    results_h2 = []
    tags = []
    for lookback, rebal, n_long, direction in product(LOOKBACKS, REBAL_FREQS,
                                                       N_LONGS, DIRECTIONS):
        amihud1 = compute_amihud(half1_closes, half1_volumes, lookback)
        ranking1 = -amihud1 if direction == "liquid_long" else amihud1
        warmup = lookback + 5
        res1 = run_xs_factor(half1_closes, ranking1, rebal, n_long, warmup=warmup)

        amihud2 = compute_amihud(half2_closes, half2_volumes, lookback)
        ranking2 = -amihud2 if direction == "liquid_long" else amihud2
        res2 = run_xs_factor(half2_closes, ranking2, rebal, n_long, warmup=warmup)

        results_h1.append(res1["sharpe_365"])
        results_h2.append(res2["sharpe_365"])
        tags.append(f"{direction}_L{lookback}_R{rebal}_N{n_long}")

    h1_arr = np.array(results_h1)
    h2_arr = np.array(results_h2)
    corr = np.corrcoef(h1_arr, h2_arr)[0, 1]
    both_positive = ((h1_arr > 0) & (h2_arr > 0)).sum()

    print(f"  Sharpe rank correlation between halves: {corr:.3f}")
    print(f"  Positive in both halves: {both_positive}/{len(h1_arr)} ({both_positive/len(h1_arr):.0%})")
    print(f"  Half 1 mean Sharpe(365): {h1_arr.mean():.3f}")
    print(f"  Half 2 mean Sharpe(365): {h2_arr.mean():.3f}")

    # Per-direction breakdown
    for d in DIRECTIONS:
        mask = [d in t for t in tags]
        h1_sub = h1_arr[mask]
        h2_sub = h2_arr[mask]
        both = ((h1_sub > 0) & (h2_sub > 0)).sum()
        print(f"  {d}: Half1 mean {h1_sub.mean():.3f}, Half2 mean {h2_sub.mean():.3f}, "
              f"both positive {both}/{len(h1_sub)}")

    return {
        "sharpe_correlation": round(float(corr), 3),
        "both_positive_pct": round(both_positive / len(h1_arr), 3),
        "half1_mean_sharpe": round(float(h1_arr.mean()), 3),
        "half2_mean_sharpe": round(float(h2_arr.mean()), 3),
    }


# =========================================================================
# Walk-Forward with Fixed Params
# =========================================================================

def run_walk_forward_fixed(closes, volumes, lookback, rebal, n_long, direction):
    """
    Walk-forward validation with FIXED params: 6 folds, 120d train / 90d test.
    Folds go from most recent backwards.
    """
    tag = f"{direction}_L{lookback}_R{rebal}_N{n_long}"
    print(f"\n  Walk-Forward (Fixed Params): {tag}")
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
        test_volumes = volumes.iloc[test_start_idx:test_end_idx]

        if len(test_closes) < 30:
            print(f"    Fold {fold+1}: test period too short ({len(test_closes)} days)")
            break

        test_amihud = compute_amihud(test_closes, test_volumes, lookback)
        test_ranking = -test_amihud if direction == "liquid_long" else test_amihud
        warmup = min(lookback + 5, len(test_closes) // 2)

        res = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "sharpe_365": res["sharpe_365"],
            "sharpe_8760": res["sharpe_8760"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
        })
        print(f"    Fold {fold+1}: {test_closes.index[0].date()} -> {test_closes.index[-1].date()}, "
              f"Sharpe(365) {res['sharpe_365']:.3f}, Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["sharpe_365"] > 0).sum()
    print(f"\n    Positive folds: {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe(365): {df['sharpe_365'].mean():.3f}")
    print(f"    Mean OOS Sharpe(8760): {df['sharpe_8760'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df['annual_ret'].mean():.1%}")
    print(f"    Worst OOS DD: {df['max_dd'].max():.1%}")
    return df


# =========================================================================
# Walk-Forward with In-Sample Parameter Selection
# =========================================================================

def run_walk_forward_param_selection(closes, volumes):
    """
    Walk-forward with in-sample parameter selection:
    For each fold, select best params on train set, then evaluate on test set.
    Tests BOTH directions within each fold.
    """
    print(f"\n{'='*70}")
    print("Walk-Forward with In-Sample Parameter Selection")
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
        train_volumes = volumes.iloc[train_start_idx:test_start_idx]
        test_closes = closes.iloc[test_start_idx:test_end_idx]
        test_volumes = volumes.iloc[test_start_idx:test_end_idx]

        if len(test_closes) < 30 or len(train_closes) < 60:
            break

        # Step 1: find best params on train set (both directions)
        best_sharpe = -999
        best_params = None
        for lookback, rebal, n_long, direction in product(LOOKBACKS, REBAL_FREQS,
                                                           N_LONGS, DIRECTIONS):
            amihud = compute_amihud(train_closes, train_volumes, lookback)
            ranking = -amihud if direction == "liquid_long" else amihud
            warmup = lookback + 5
            if warmup >= len(train_closes) - 30:
                continue
            res = run_xs_factor(train_closes, ranking, rebal, n_long, warmup=warmup)
            if res["sharpe_365"] > best_sharpe:
                best_sharpe = res["sharpe_365"]
                best_params = (lookback, rebal, n_long, direction)

        if best_params is None:
            break

        # Step 2: evaluate best params on test set
        lookback, rebal, n_long, direction = best_params
        test_amihud = compute_amihud(test_closes, test_volumes, lookback)
        test_ranking = -test_amihud if direction == "liquid_long" else test_amihud
        warmup = min(lookback + 5, len(test_closes) // 2)
        res = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=warmup)

        tag = f"{direction}_L{lookback}_R{rebal}_N{n_long}"
        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "train_best_params": tag,
            "train_sharpe_365": round(best_sharpe, 3),
            "oos_sharpe_365": res["sharpe_365"],
            "oos_sharpe_8760": res["sharpe_8760"],
            "oos_annual_ret": res["annual_ret"],
            "oos_max_dd": res["max_dd"],
        })
        print(f"    Fold {fold+1}: train best={tag} "
              f"(IS Sharpe(365) {best_sharpe:.3f}), "
              f"OOS Sharpe(365) {res['sharpe_365']:.3f}, Ann {res['annual_ret']:.1%}")

    if not fold_results:
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe_365"] > 0).sum()
    print(f"\n    Positive OOS folds: {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe(365): {df['oos_sharpe_365'].mean():.3f}")
    print(f"    Mean OOS Sharpe(8760): {df['oos_sharpe_8760'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df['oos_annual_ret'].mean():.1%}")
    return df


# =========================================================================
# Correlation with H-012 (Momentum) and H-031 (Size)
# =========================================================================

def compute_correlations(closes, volumes, lookback, rebal, n_long, direction):
    """
    Compute daily return correlation between Amihud factor and:
    - H-012: 60-day momentum (rebal 5d, N=4)
    - H-031: Size factor = 30-day avg dollar volume (long large, rebal 5d, N=5)
    """
    print(f"\n{'='*70}")
    print("Correlation Analysis")
    print(f"{'='*70}")
    tag = f"{direction}_L{lookback}_R{rebal}_N{n_long}"
    print(f"  Amihud params: {tag}")

    # Run Amihud factor
    amihud = compute_amihud(closes, volumes, lookback)
    ranking = -amihud if direction == "liquid_long" else amihud
    warmup = lookback + 5
    res_amihud = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup)

    # H-012: Momentum (60d lookback, rebal 5d, N=4)
    mom_ranking = closes.pct_change(60)
    res_mom = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)

    # H-031: Size factor (30d avg dollar volume, long large, rebal 5d, N=5)
    dollar_volume = closes * volumes
    size_ranking = dollar_volume.rolling(30, min_periods=30).mean()
    res_size = run_xs_factor(closes, size_ranking, 5, 5, warmup=65)

    eq_amihud = res_amihud["equity"]
    eq_mom = res_mom["equity"]
    eq_size = res_size["equity"]

    rets_amihud = eq_amihud.pct_change().dropna()
    rets_mom = eq_mom.pct_change().dropna()
    rets_size = eq_size.pct_change().dropna()

    # Correlation with momentum
    common_mom = rets_amihud.index.intersection(rets_mom.index)
    if len(common_mom) >= 50:
        corr_mom = rets_amihud.loc[common_mom].corr(rets_mom.loc[common_mom])
    else:
        corr_mom = np.nan
        print("    Insufficient overlap for momentum correlation")

    # Correlation with size
    common_size = rets_amihud.index.intersection(rets_size.index)
    if len(common_size) >= 50:
        corr_size = rets_amihud.loc[common_size].corr(rets_size.loc[common_size])
    else:
        corr_size = np.nan
        print("    Insufficient overlap for size correlation")

    print(f"\n  H-087 Amihud ({tag}):  Sharpe(365) {res_amihud['sharpe_365']:.3f}, "
          f"Ann {res_amihud['annual_ret']:.1%}")
    print(f"  H-012 Momentum:        Sharpe(365) {res_mom['sharpe_365']:.3f}, "
          f"Ann {res_mom['annual_ret']:.1%}")
    print(f"  H-031 Size:            Sharpe(365) {res_size['sharpe_365']:.3f}, "
          f"Ann {res_size['annual_ret']:.1%}")
    print(f"\n  Correlation H-087 vs H-012 (momentum): {corr_mom:.3f}")
    print(f"  Correlation H-087 vs H-031 (size):     {corr_size:.3f}")

    # Also check correlation between Amihud and size at signal level
    # (since Amihud uses dollar volume, it may be mechanically related to size)
    amihud_vals = compute_amihud(closes, volumes, lookback)
    size_vals = dollar_volume.rolling(30, min_periods=30).mean()
    # Cross-sectional correlation at each time step
    xs_corrs = []
    for idx in amihud_vals.index:
        a = amihud_vals.loc[idx].dropna()
        s = size_vals.loc[idx].dropna()
        common = a.index.intersection(s.index)
        if len(common) >= 5:
            xs_corrs.append(a[common].corr(s[common]))
    if xs_corrs:
        mean_xs_corr = np.nanmean(xs_corrs)
        print(f"\n  Signal-level cross-sectional correlation (Amihud vs Size): {mean_xs_corr:.3f}")
        print(f"  (Expected: strongly negative, since Amihud ~ 1/dollar_volume ~ 1/size)")

    return {
        "h012_momentum_corr": round(float(corr_mom), 3) if not np.isnan(corr_mom) else None,
        "h031_size_corr": round(float(corr_size), 3) if not np.isnan(corr_size) else None,
        "signal_xs_corr_amihud_size": round(float(mean_xs_corr), 3) if xs_corrs else None,
    }


# =========================================================================
# Amihud Factor Decile Analysis
# =========================================================================

def run_decile_analysis(closes, volumes, lookback=20):
    """
    Analyze average returns by Amihud quintile to understand the shape
    of the illiquidity-return relationship.
    """
    print(f"\n{'='*70}")
    print(f"Amihud Quintile Return Analysis (lookback={lookback})")
    print(f"{'='*70}")

    amihud = compute_amihud(closes, volumes, lookback)
    daily_rets = closes.pct_change()

    # For each day, rank assets into quintiles by Amihud, compute next-day return
    quintile_rets = {q: [] for q in range(1, 6)}

    for i in range(lookback + 1, len(closes) - 1):
        a = amihud.iloc[i].dropna()
        r_next = daily_rets.iloc[i + 1]
        if len(a) < 10:
            continue

        # Quintile assignment
        try:
            quintiles = pd.qcut(a, 5, labels=[1, 2, 3, 4, 5])
        except ValueError:
            continue  # ties prevent clean binning

        for q in range(1, 6):
            assets_in_q = quintiles[quintiles == q].index
            if len(assets_in_q) > 0:
                mean_ret = r_next[assets_in_q].mean()
                if not np.isnan(mean_ret):
                    quintile_rets[q].append(mean_ret)

    print(f"  Quintile 1 = MOST LIQUID (lowest Amihud)")
    print(f"  Quintile 5 = LEAST LIQUID (highest Amihud)")
    print()

    for q in range(1, 6):
        rets = np.array(quintile_rets[q])
        if len(rets) > 0:
            mean_r = np.mean(rets) * 365 * 100  # annualized in pct
            std_r = np.std(rets) * np.sqrt(365) * 100
            sharpe = (np.mean(rets) / np.std(rets) * np.sqrt(365)) if np.std(rets) > 0 else 0
            print(f"  Q{q}: mean daily ret {np.mean(rets)*100:.4f}%, "
                  f"ann ~{mean_r:.1f}%, ann vol ~{std_r:.1f}%, "
                  f"Sharpe(365) ~{sharpe:.2f}, n={len(rets)}")

    # Long Q1 short Q5 spread (liquid premium)
    if quintile_rets[1] and quintile_rets[5]:
        q1 = np.array(quintile_rets[1])
        q5 = np.array(quintile_rets[5])
        min_len = min(len(q1), len(q5))
        spread = q1[:min_len] - q5[:min_len]
        spread_mean = np.mean(spread) * 365 * 100
        spread_sharpe = (np.mean(spread) / np.std(spread) * np.sqrt(365)) if np.std(spread) > 0 else 0
        print(f"\n  Q1-Q5 spread (liquid premium): {spread_mean:.1f}% ann, Sharpe ~{spread_sharpe:.2f}")

    # Long Q5 short Q1 spread (illiquidity premium)
    if quintile_rets[1] and quintile_rets[5]:
        spread2 = q5[:min_len] - q1[:min_len]
        spread2_mean = np.mean(spread2) * 365 * 100
        spread2_sharpe = (np.mean(spread2) / np.std(spread2) * np.sqrt(365)) if np.std(spread2) > 0 else 0
        print(f"  Q5-Q1 spread (illiquidity premium): {spread2_mean:.1f}% ann, Sharpe ~{spread2_sharpe:.2f}")


# =========================================================================
# Current Positions
# =========================================================================

def show_current_positions(closes, volumes, lookback, rebal, n_long, direction):
    """Show what positions would be held today."""
    print(f"\n{'='*70}")
    print("Current Positions (Most Recent Signal)")
    print(f"{'='*70}")

    amihud = compute_amihud(closes, volumes, lookback)
    latest = amihud.iloc[-1].dropna().sort_values()

    print(f"  Amihud values (last bar, lookback={lookback}):")
    print(f"  {'Asset':<12} {'Amihud':>15} {'Rank':>6}")
    for rank, (sym, val) in enumerate(latest.items(), 1):
        marker = ""
        if direction == "liquid_long":
            if rank <= n_long:
                marker = " <-- LONG (most liquid)"
            elif rank > len(latest) - n_long:
                marker = " <-- SHORT (least liquid)"
        else:
            if rank <= n_long:
                marker = " <-- SHORT (most liquid)"
            elif rank > len(latest) - n_long:
                marker = " <-- LONG (least liquid)"
        print(f"  {sym:<12} {val:>15.2e} {rank:>6}{marker}")


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    print("H-087: Amihud Illiquidity Factor")
    print("=" * 70)

    # ===== Load Data =====
    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")

    if len(daily) < 10:
        print("ERROR: Not enough assets loaded. Run data fetch first:")
        print("  python -c \"from lib.data_fetch import fetch_multiple; "
              "fetch_multiple([...], '1d', limit_days=730)\"")
        sys.exit(1)

    # Build closes and volumes panels
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily.items()})

    # Align: drop rows where all NaN, forward fill, then drop remaining NaN
    closes = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().fillna(0)

    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")
    print(f"Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    # ===== 0. Quintile Analysis =====
    run_decile_analysis(closes, volumes, lookback=20)

    # ===== 1. Full Parameter Scan =====
    scan_results = run_full_scan(closes, volumes)

    # ===== 2. Best parameters (each direction) =====
    best_overall = scan_results.nlargest(1, "sharpe_365").iloc[0]
    best_lookback = int(best_overall["lookback"])
    best_rebal = int(best_overall["rebal"])
    best_n_long = int(best_overall["n_long"])
    best_direction = best_overall["direction"]
    best_tag = f"{best_direction}_L{best_lookback}_R{best_rebal}_N{best_n_long}"

    print(f"\n  OVERALL BEST: {best_tag}")
    print(f"  Sharpe(365): {best_overall['sharpe_365']:.3f}, "
          f"Sharpe(8760): {best_overall['sharpe_8760']:.3f}")
    print(f"  Ann Return: {best_overall['annual_ret']:.1%}, "
          f"Max DD: {best_overall['max_dd']:.1%}, "
          f"Win Rate: {best_overall['win_rate']:.1%}")

    # Best per direction
    for d in DIRECTIONS:
        sub = scan_results[scan_results["direction"] == d]
        b = sub.nlargest(1, "sharpe_365").iloc[0]
        print(f"\n  Best {d}: L{int(b['lookback'])}_R{int(b['rebal'])}_N{int(b['n_long'])}")
        print(f"    Sharpe(365) {b['sharpe_365']:.3f}, Ann {b['annual_ret']:.1%}, DD {b['max_dd']:.1%}")

    # ===== 3. 70/30 Train/Test Split =====
    train_test = run_train_test_split(closes, volumes)

    # ===== 4. Split-Half Validation =====
    split_half = run_split_half(closes, volumes)

    # ===== 5. Walk-Forward (fixed params for best overall) =====
    print(f"\n{'='*70}")
    print("Walk-Forward Validation (Fixed Params)")
    print(f"{'='*70}")
    wf_fixed = run_walk_forward_fixed(closes, volumes, best_lookback, best_rebal,
                                       best_n_long, best_direction)

    # Also run WF for the other direction's best
    other_direction = "illiquid_long" if best_direction == "liquid_long" else "liquid_long"
    sub_other = scan_results[scan_results["direction"] == other_direction]
    best_other = sub_other.nlargest(1, "sharpe_365").iloc[0]
    wf_fixed_other = run_walk_forward_fixed(
        closes, volumes,
        int(best_other["lookback"]), int(best_other["rebal"]),
        int(best_other["n_long"]), other_direction
    )

    # ===== 6. Walk-Forward with Parameter Selection =====
    wf_selected = run_walk_forward_param_selection(closes, volumes)

    # ===== 7. Correlations with H-012 and H-031 =====
    correlations = compute_correlations(closes, volumes, best_lookback, best_rebal,
                                        best_n_long, best_direction)

    # ===== 8. Current Positions =====
    show_current_positions(closes, volumes, best_lookback, best_rebal,
                           best_n_long, best_direction)

    # ===== 9. Parameter Robustness =====
    pos_pct = (scan_results["sharpe_365"] > 0).mean()
    mean_sharpe = scan_results["sharpe_365"].mean()
    median_sharpe = scan_results["sharpe_365"].median()

    # Per-direction robustness
    robustness = {}
    for d in DIRECTIONS:
        sub = scan_results[scan_results["direction"] == d]
        robustness[d] = {
            "n_combos": len(sub),
            "pct_positive": round(float((sub["sharpe_365"] > 0).mean()), 3),
            "mean_sharpe_365": round(float(sub["sharpe_365"].mean()), 3),
            "median_sharpe_365": round(float(sub["sharpe_365"].median()), 3),
        }

    # ===== 10. Summary =====
    print("\n" + "=" * 70)
    print("COMPREHENSIVE SUMMARY: H-087 Amihud Illiquidity Factor")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Parameter combos tested: {len(scan_results)} "
          f"({len(scan_results)//2} per direction)")
    print(f"  Overall positive Sharpe(365): "
          f"{(scan_results['sharpe_365'] > 0).sum()}/{len(scan_results)} ({pos_pct:.0%})")

    for d in DIRECTIONS:
        r = robustness[d]
        print(f"\n  {d}:")
        print(f"    Positive: {r['pct_positive']:.0%}, "
              f"Mean Sharpe(365): {r['mean_sharpe_365']:.3f}, "
              f"Median: {r['median_sharpe_365']:.3f}")

    print(f"\n  OVERALL BEST: {best_tag}")
    print(f"    Sharpe(365): {best_overall['sharpe_365']:.3f}, "
          f"Sharpe(8760): {best_overall['sharpe_8760']:.3f}")
    print(f"    Ann Return: {best_overall['annual_ret']:.1%}, "
          f"Max DD: {best_overall['max_dd']:.1%}, "
          f"Win Rate: {best_overall['win_rate']:.1%}")

    print(f"\n  70/30 Train/Test:")
    print(f"    Train best: {train_test['train_best_params']} "
          f"(IS Sharpe(365) {train_test['train_sharpe_365']:.3f})")
    print(f"    OOS Sharpe(365): {train_test['test_sharpe_365']:.3f}, "
          f"Ann: {train_test['test_annual_ret']:.1%}, DD: {train_test['test_max_dd']:.1%}")

    print(f"\n  Split-Half:")
    print(f"    Sharpe correlation: {split_half['sharpe_correlation']:.3f}")
    print(f"    Both positive: {split_half['both_positive_pct']:.0%}")

    if wf_fixed is not None:
        wf_pos = (wf_fixed["sharpe_365"] > 0).sum()
        print(f"\n  Walk-Forward BEST ({best_tag}, fixed):")
        print(f"    {wf_pos}/{len(wf_fixed)} positive, "
              f"mean OOS Sharpe(365) {wf_fixed['sharpe_365'].mean():.3f}")

    if wf_fixed_other is not None:
        wf_pos_o = (wf_fixed_other["sharpe_365"] > 0).sum()
        other_tag = f"{other_direction}_L{int(best_other['lookback'])}_R{int(best_other['rebal'])}_N{int(best_other['n_long'])}"
        print(f"  Walk-Forward OTHER ({other_tag}, fixed):")
        print(f"    {wf_pos_o}/{len(wf_fixed_other)} positive, "
              f"mean OOS Sharpe(365) {wf_fixed_other['sharpe_365'].mean():.3f}")

    if wf_selected is not None:
        wf_pos2 = (wf_selected["oos_sharpe_365"] > 0).sum()
        print(f"  Walk-Forward (param selection): {wf_pos2}/{len(wf_selected)} positive, "
              f"mean OOS Sharpe(365) {wf_selected['oos_sharpe_365'].mean():.3f}")

    print(f"\n  Correlations:")
    if correlations["h012_momentum_corr"] is not None:
        print(f"    vs H-012 (momentum): {correlations['h012_momentum_corr']:.3f}")
    if correlations["h031_size_corr"] is not None:
        print(f"    vs H-031 (size):     {correlations['h031_size_corr']:.3f}")
    if correlations.get("signal_xs_corr_amihud_size") is not None:
        print(f"    Signal-level XS corr (Amihud vs Size): "
              f"{correlations['signal_xs_corr_amihud_size']:.3f}")

    # ===== 11. Decision =====
    # Auto-assess based on criteria
    assessment_lines = []
    if pos_pct >= 0.7:
        assessment_lines.append(f"  [PASS] Param robustness: {pos_pct:.0%} positive (threshold 70%)")
    else:
        assessment_lines.append(f"  [FAIL] Param robustness: {pos_pct:.0%} positive (threshold 70%)")

    if train_test["test_sharpe_365"] > 0:
        assessment_lines.append(f"  [PASS] OOS Sharpe(365): {train_test['test_sharpe_365']:.3f} > 0")
    else:
        assessment_lines.append(f"  [FAIL] OOS Sharpe(365): {train_test['test_sharpe_365']:.3f} <= 0")

    if split_half["sharpe_correlation"] > 0.3:
        assessment_lines.append(f"  [PASS] Split-half correlation: {split_half['sharpe_correlation']:.3f} > 0.3")
    else:
        assessment_lines.append(f"  [WARN] Split-half correlation: {split_half['sharpe_correlation']:.3f} <= 0.3")

    if wf_selected is not None:
        wf_pos_ratio = (wf_selected["oos_sharpe_365"] > 0).sum() / len(wf_selected)
        if wf_pos_ratio >= 0.5:
            assessment_lines.append(f"  [PASS] WF param selection: {wf_pos_ratio:.0%} positive folds")
        else:
            assessment_lines.append(f"  [FAIL] WF param selection: {wf_pos_ratio:.0%} positive folds")

    print(f"\n  ASSESSMENT:")
    for line in assessment_lines:
        print(line)

    n_pass = sum(1 for l in assessment_lines if "[PASS]" in l)
    n_total_checks = len(assessment_lines)
    if n_pass >= 3:
        verdict = "CONFIRMED"
    elif n_pass >= 2:
        verdict = "CONDITIONAL"
    else:
        verdict = "REJECTED"
    print(f"\n  VERDICT: {verdict} ({n_pass}/{n_total_checks} checks passed)")

    # ===== 12. Save Results =====
    results_file = Path(__file__).parent / "h087_results.json"
    results_data = {
        "hypothesis": "H-087",
        "name": "Amihud Illiquidity Factor",
        "description": "Cross-sectional factor: test both long-liquid and long-illiquid directions",
        "fee_rate_bps": FEE_RATE * 10000,
        "universe_size": len(closes.columns),
        "n_days": len(closes),
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "verdict": verdict,
        "full_scan": {
            "n_combos": len(scan_results),
            "pct_positive_sharpe": round(float(pos_pct), 3),
            "mean_sharpe_365": round(float(mean_sharpe), 3),
            "median_sharpe_365": round(float(median_sharpe), 3),
            "best_params": best_tag,
            "best_sharpe_365": round(float(best_overall["sharpe_365"]), 3),
            "best_sharpe_8760": round(float(best_overall["sharpe_8760"]), 3),
            "best_annual_ret": round(float(best_overall["annual_ret"]), 4),
            "best_max_dd": round(float(best_overall["max_dd"]), 4),
            "best_win_rate": round(float(best_overall["win_rate"]), 4),
            "per_direction": robustness,
        },
        "train_test_70_30": train_test,
        "split_half": split_half,
        "walk_forward_fixed_best": {
            "params": best_tag,
            "n_folds": len(wf_fixed) if wf_fixed is not None else 0,
            "positive_folds": int((wf_fixed["sharpe_365"] > 0).sum()) if wf_fixed is not None else 0,
            "mean_oos_sharpe_365": round(float(wf_fixed["sharpe_365"].mean()), 3) if wf_fixed is not None else 0,
            "mean_oos_sharpe_8760": round(float(wf_fixed["sharpe_8760"].mean()), 3) if wf_fixed is not None else 0,
            "folds": wf_fixed.to_dict("records") if wf_fixed is not None else [],
        },
        "walk_forward_fixed_other": {
            "params": f"{other_direction}_L{int(best_other['lookback'])}_R{int(best_other['rebal'])}_N{int(best_other['n_long'])}",
            "n_folds": len(wf_fixed_other) if wf_fixed_other is not None else 0,
            "positive_folds": int((wf_fixed_other["sharpe_365"] > 0).sum()) if wf_fixed_other is not None else 0,
            "mean_oos_sharpe_365": round(float(wf_fixed_other["sharpe_365"].mean()), 3) if wf_fixed_other is not None else 0,
            "folds": wf_fixed_other.to_dict("records") if wf_fixed_other is not None else [],
        },
        "walk_forward_selected": {
            "n_folds": len(wf_selected) if wf_selected is not None else 0,
            "positive_folds": int((wf_selected["oos_sharpe_365"] > 0).sum()) if wf_selected is not None else 0,
            "mean_oos_sharpe_365": round(float(wf_selected["oos_sharpe_365"].mean()), 3) if wf_selected is not None else 0,
            "folds": wf_selected.to_dict("records") if wf_selected is not None else [],
        },
        "correlations": correlations,
        "parameter_robustness": {
            "overall_pct_positive": round(float(pos_pct), 3),
            "overall_mean_sharpe": round(float(mean_sharpe), 3),
            "per_direction": robustness,
        },
        "assessment": assessment_lines,
    }

    with open(results_file, "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\n  Results saved to {results_file}")
