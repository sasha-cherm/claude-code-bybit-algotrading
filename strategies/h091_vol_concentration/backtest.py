"""
H-091: Volume Concentration (Herfindahl) Factor (Cross-Sectional)

Measure how concentrated trading volume is across days within a rolling window.
The Herfindahl index H = sum((v_i / sum(v))^2) ranges from 1/W (perfectly
uniform) to 1.0 (all volume on a single day).

Hypothesis: Assets with evenly-distributed volume (low Herfindahl = organic,
stable interest) outperform. Assets with concentrated volume spikes (high
Herfindahl = episodic attention) underperform.

Strategy: rank assets cross-sectionally by Herfindahl index.
  - LONG bottom N (lowest Herfindahl = most uniform volume)
  - SHORT top N (highest Herfindahl = most concentrated volume)
  - Dollar-neutral, equal-weight, rebalance every R days.

Validation: full parameter scan, 70/30 train/test, split-half,
walk-forward (6 folds, 180d train, 90d test), correlation with
H-012 (momentum) and H-031 (size).
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

FEE_RATE = 0.0006       # 6 bps taker fee on Bybit perps
INITIAL_CAPITAL = 10_000.0

# Parameter grid
WINDOWS = [10, 20, 30, 40]        # Herfindahl rolling window (W)
REBAL_FREQS = [3, 5, 7, 10]      # rebalance every R days
N_LONGS = [3, 4, 5]              # top/bottom N

# Walk-forward config
WF_FOLDS = 6
WF_TRAIN = 180
WF_TEST = 90
WF_STEP = 90


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


def herfindahl_index(volumes, window):
    """
    Compute rolling Herfindahl index of daily volume for each asset.

    H = sum((v_i / sum(v))^2) over the rolling window.
    Low H -> uniform volume (organic interest).
    High H -> concentrated volume (episodic spikes).

    Returns DataFrame same shape as volumes with Herfindahl values.
    """
    def _herf_rolling(series, w):
        """Compute rolling Herfindahl for a single asset series."""
        n = len(series)
        result = np.full(n, np.nan)
        vals = series.values.astype(float)
        for i in range(w - 1, n):
            window_vals = vals[i - w + 1: i + 1]
            total = window_vals.sum()
            if total <= 0:
                result[i] = np.nan
                continue
            shares = window_vals / total
            result[i] = (shares ** 2).sum()
        return pd.Series(result, index=series.index)

    herf = pd.DataFrame(index=volumes.index, columns=volumes.columns, dtype=float)
    for col in volumes.columns:
        herf[col] = _herf_rolling(volumes[col], window)
    return herf


def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  warmup=65, long_low=True):
    """
    Generic cross-sectional factor backtester using log returns.

    If long_low=True: LONG the lowest-ranked assets, SHORT the highest.
    If long_low=False: LONG the highest-ranked assets, SHORT the lowest.

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

            if long_low:
                # Long the lowest-ranked (most uniform volume), short the highest
                ranked = valid.sort_values(ascending=True)
                longs = ranked.index[:n_long]
                shorts = ranked.index[-n_short:]
            else:
                # Long the highest-ranked, short the lowest
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

def run_full_scan(closes, volumes):
    """Run all parameter combinations on the full period."""
    print("\n" + "=" * 70)
    print("H-091: VOLUME CONCENTRATION (HERFINDAHL) FACTOR -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE*10000:.0f} bps per trade")

    results = []
    for window, rebal, n_long in product(WINDOWS, REBAL_FREQS, N_LONGS):
        ranking = herfindahl_index(volumes, window)
        warmup = window + 5

        # Long LOW Herfindahl (uniform volume), short HIGH (concentrated)
        res = run_xs_factor(closes, ranking, rebal, n_long,
                            warmup=warmup, long_low=True)
        tag = f"W{window}_R{rebal}_N{n_long}"
        results.append({
            "tag": tag,
            "window": window,
            "rebal": rebal,
            "n_long": n_long,
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
            "n_rebalances": res["n_rebalances"],
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

    print(f"\n  70/30 Train/Test Split")
    print(f"  Train: {train_closes.index[0].date()} to {train_closes.index[-1].date()} ({len(train_closes)} days)")
    print(f"  Test:  {test_closes.index[0].date()} to {test_closes.index[-1].date()} ({len(test_closes)} days)")

    # Find best params on train set
    best_sharpe = -999
    best_params = None
    for window, rebal, n_long in product(WINDOWS, REBAL_FREQS, N_LONGS):
        ranking = herfindahl_index(train_volumes, window)
        warmup = window + 5
        res = run_xs_factor(train_closes, ranking, rebal, n_long,
                            warmup=warmup, long_low=True)
        if res["sharpe"] > best_sharpe:
            best_sharpe = res["sharpe"]
            best_params = (window, rebal, n_long)

    window, rebal, n_long = best_params
    print(f"  Train best: W{window}_R{rebal}_N{n_long} (Sharpe {best_sharpe:.3f})")

    # Evaluate on test set
    test_ranking = herfindahl_index(test_volumes, window)
    warmup = window + 5
    res_test = run_xs_factor(test_closes, test_ranking, rebal, n_long,
                             warmup=warmup, long_low=True)
    print(f"  Test result: Sharpe {res_test['sharpe']:.3f}, "
          f"Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}")

    return {
        "train_best_params": f"W{window}_R{rebal}_N{n_long}",
        "train_sharpe": best_sharpe,
        "test_sharpe": res_test["sharpe"],
        "test_annual_ret": res_test["annual_ret"],
        "test_max_dd": res_test["max_dd"],
        "test_win_rate": res_test["win_rate"],
        "test_n_days": len(test_closes),
    }


# =========================================================================
# Split-Half Validation
# =========================================================================

def run_split_half(closes, volumes):
    """Split data into two halves, run scan on each, compare rankings."""
    n = len(closes)
    mid = n // 2
    half1_closes = closes.iloc[:mid]
    half1_volumes = volumes.iloc[:mid]
    half2_closes = closes.iloc[mid:]
    half2_volumes = volumes.iloc[mid:]

    print(f"\n  Split-Half Validation")
    print(f"  Half 1: {half1_closes.index[0].date()} to {half1_closes.index[-1].date()} ({len(half1_closes)} days)")
    print(f"  Half 2: {half2_closes.index[0].date()} to {half2_closes.index[-1].date()} ({len(half2_closes)} days)")

    results_h1 = []
    results_h2 = []
    for window, rebal, n_long in product(WINDOWS, REBAL_FREQS, N_LONGS):
        ranking1 = herfindahl_index(half1_volumes, window)
        warmup = window + 5
        res1 = run_xs_factor(half1_closes, ranking1, rebal, n_long,
                             warmup=warmup, long_low=True)

        ranking2 = herfindahl_index(half2_volumes, window)
        res2 = run_xs_factor(half2_closes, ranking2, rebal, n_long,
                             warmup=warmup, long_low=True)

        results_h1.append(res1["sharpe"])
        results_h2.append(res2["sharpe"])

    h1_arr = np.array(results_h1)
    h2_arr = np.array(results_h2)
    corr = np.corrcoef(h1_arr, h2_arr)[0, 1]
    both_positive = ((h1_arr > 0) & (h2_arr > 0)).sum()

    print(f"  Sharpe rank correlation between halves: {corr:.3f}")
    print(f"  Positive in both halves: {both_positive}/{len(h1_arr)} ({both_positive/len(h1_arr):.0%})")
    print(f"  Half 1 mean Sharpe: {h1_arr.mean():.3f}")
    print(f"  Half 2 mean Sharpe: {h2_arr.mean():.3f}")

    return {
        "sharpe_correlation": round(float(corr), 3),
        "both_positive_pct": round(both_positive / len(h1_arr), 3),
        "half1_mean_sharpe": round(float(h1_arr.mean()), 3),
        "half2_mean_sharpe": round(float(h2_arr.mean()), 3),
    }


# =========================================================================
# Walk-Forward Validation
# =========================================================================

def run_walk_forward(closes, volumes, window, rebal, n_long):
    """
    Walk-forward validation with FIXED params: 6 folds, 180d train, 90d test.
    Folds go from most recent backwards.
    """
    print(f"\n  Walk-Forward (Fixed Params): W{window}_R{rebal}_N{n_long}")
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

        test_ranking = herfindahl_index(test_volumes, window)
        warmup = min(window + 5, len(test_closes) // 2)

        res = run_xs_factor(test_closes, test_ranking, rebal, n_long,
                            warmup=warmup, long_low=True)

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


def run_walk_forward_param_selection(closes, volumes):
    """
    Walk-forward with in-sample parameter selection:
    For each fold, select best params on train set, then evaluate on test set.
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

        train_closes = closes.iloc[train_start_idx:test_start_idx]
        train_volumes = volumes.iloc[train_start_idx:test_start_idx]
        test_closes = closes.iloc[test_start_idx:test_end_idx]
        test_volumes = volumes.iloc[test_start_idx:test_end_idx]

        if len(test_closes) < 30 or len(train_closes) < 60:
            break

        # Step 1: find best params on train set
        best_sharpe = -999
        best_params = None
        for window, rebal, n_long in product(WINDOWS, REBAL_FREQS, N_LONGS):
            ranking = herfindahl_index(train_volumes, window)
            warmup = window + 5
            if warmup >= len(train_closes) - 30:
                continue
            res = run_xs_factor(train_closes, ranking, rebal, n_long,
                                warmup=warmup, long_low=True)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_params = (window, rebal, n_long)

        if best_params is None:
            break

        # Step 2: evaluate best params on test set
        window, rebal, n_long = best_params
        test_ranking = herfindahl_index(test_volumes, window)
        warmup = min(window + 5, len(test_closes) // 2)
        res = run_xs_factor(test_closes, test_ranking, rebal, n_long,
                            warmup=warmup, long_low=True)

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
        })
        print(f"    Fold {fold+1}: train best=W{window}_R{rebal}_N{n_long} "
              f"(IS Sharpe {best_sharpe:.3f}), "
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
# Correlation with H-012 (Momentum) and H-031 (Size)
# =========================================================================

def compute_correlations(closes, volumes, window, rebal, n_long):
    """
    Compute daily return correlation between vol-concentration factor
    and H-012 (60d momentum) + H-031 (market cap / size proxy via dollar volume).
    """
    print(f"\n  Correlations with Other Factors")

    # Run H-091 volume concentration factor
    herf_ranking = herfindahl_index(volumes, window)
    warmup_herf = window + 5
    res_herf = run_xs_factor(closes, herf_ranking, rebal, n_long,
                              warmup=warmup_herf, long_low=True)

    # Run H-012 momentum: 60d returns, long highest, short lowest
    mom_ranking = closes.pct_change(60)
    res_mom = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65, long_low=False)

    # Run H-031 size proxy: use rolling 30d avg dollar volume as size
    # Long small (low dollar volume), short large (high dollar volume) --
    # classic small-cap premium analogue
    dollar_vol = closes * volumes
    size_ranking = dollar_vol.rolling(30, min_periods=20).mean()
    res_size = run_xs_factor(closes, size_ranking, 5, 4, warmup=35, long_low=True)

    eq_herf = res_herf["equity"]
    eq_mom = res_mom["equity"]
    eq_size = res_size["equity"]

    rets_herf = eq_herf.pct_change().dropna()
    rets_mom = eq_mom.pct_change().dropna()
    rets_size = eq_size.pct_change().dropna()

    common_mom = rets_herf.index.intersection(rets_mom.index)
    common_size = rets_herf.index.intersection(rets_size.index)

    corr_mom = 0.0
    corr_size = 0.0

    if len(common_mom) >= 50:
        corr_mom = rets_herf.loc[common_mom].corr(rets_mom.loc[common_mom])
        print(f"  Correlation with H-012 (60d Momentum): {corr_mom:.3f}")
        print(f"    H-012 Momentum:     Sharpe {res_mom['sharpe']:.3f}, Ann {res_mom['annual_ret']:.1%}")
    else:
        print(f"  Insufficient overlap for H-012 correlation")

    if len(common_size) >= 50:
        corr_size = rets_herf.loc[common_size].corr(rets_size.loc[common_size])
        print(f"  Correlation with H-031 (Size proxy):   {corr_size:.3f}")
        print(f"    H-031 Size proxy:   Sharpe {res_size['sharpe']:.3f}, Ann {res_size['annual_ret']:.1%}")
    else:
        print(f"  Insufficient overlap for H-031 correlation")

    print(f"    H-091 Vol Conc:     Sharpe {res_herf['sharpe']:.3f}, Ann {res_herf['annual_ret']:.1%}")

    return {
        "h012_momentum_corr": round(float(corr_mom), 3),
        "h031_size_corr": round(float(corr_size), 3),
    }


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    print("H-091: Volume Concentration (Herfindahl) Factor")
    print("=" * 70)

    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")

    if len(daily) < 10:
        print("ERROR: Not enough assets loaded. Aborting.")
        sys.exit(1)

    # Build closes and volumes panels
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily.items()})

    # Align: drop rows where all NaN, forward fill, then drop remaining NaN
    closes = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().fillna(0)

    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")
    print(f"Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    # Sanity check: show Herfindahl distribution for one window
    print("\n--- Herfindahl Sanity Check (W=20) ---")
    herf_check = herfindahl_index(volumes, 20)
    last_day = herf_check.iloc[-1].dropna()
    print(f"  Last day Herfindahl values (W=20, theoretical min={1/20:.3f}):")
    for sym in last_day.sort_values().index:
        print(f"    {sym}: {last_day[sym]:.4f}")

    # ===== 1. Full parameter scan =====
    scan_results = run_full_scan(closes, volumes)

    # ===== 2. Best parameters =====
    best = scan_results.nlargest(1, "sharpe").iloc[0]
    best_window = int(best["window"])
    best_rebal = int(best["rebal"])
    best_n_long = int(best["n_long"])
    print(f"\n  Best full-period params: W{best_window}_R{best_rebal}_N{best_n_long}")
    print(f"  Sharpe: {best['sharpe']:.3f}, Ann Return: {best['annual_ret']:.1%}, "
          f"Max DD: {best['max_dd']:.1%}, Win Rate: {best['win_rate']:.1%}")

    # ===== 3. 70/30 Train/Test Split =====
    train_test = run_train_test_split(closes, volumes)

    # ===== 4. Split-Half Validation =====
    split_half = run_split_half(closes, volumes)

    # ===== 5. Walk-Forward (fixed params) =====
    wf_fixed = run_walk_forward(closes, volumes, best_window, best_rebal, best_n_long)

    # ===== 6. Walk-Forward with parameter selection =====
    wf_selected = run_walk_forward_param_selection(closes, volumes)

    # ===== 7. Correlations with H-012 and H-031 =====
    correlations = compute_correlations(closes, volumes, best_window, best_rebal, best_n_long)

    # ===== 8. Parameter Robustness =====
    pos_pct = (scan_results["sharpe"] > 0).mean()
    mean_sharpe = scan_results["sharpe"].mean()
    median_sharpe = scan_results["sharpe"].median()

    # Robustness by parameter dimension
    print("\n  Parameter Robustness by Dimension:")
    for param, col in [("Window", "window"), ("Rebalance", "rebal"), ("N_longs", "n_long")]:
        grp = scan_results.groupby(col)["sharpe"].agg(["mean", "median", "std"])
        print(f"    {param}:")
        for val, row in grp.iterrows():
            print(f"      {val}: mean={row['mean']:.3f}, median={row['median']:.3f}, std={row['std']:.3f}")

    # ===== 9. VERDICT =====
    print("\n" + "=" * 70)
    print("SUMMARY: H-091 Volume Concentration (Herfindahl) Factor")
    print("=" * 70)
    print(f"  Parameter combos tested: {len(scan_results)}")
    print(f"  Positive Sharpe: {(scan_results['sharpe'] > 0).sum()}/{len(scan_results)} ({pos_pct:.0%})")
    print(f"  Mean Sharpe: {mean_sharpe:.3f}, Median: {median_sharpe:.3f}")
    print(f"  Best full-period: W{best_window}_R{best_rebal}_N{best_n_long}, "
          f"Sharpe {best['sharpe']:.3f}, Ann {best['annual_ret']:.1%}, DD {best['max_dd']:.1%}")

    print(f"\n  70/30 Train/Test:")
    print(f"    Train best params: {train_test['train_best_params']} (IS Sharpe {train_test['train_sharpe']:.3f})")
    print(f"    OOS Sharpe: {train_test['test_sharpe']:.3f}, "
          f"Ann: {train_test['test_annual_ret']:.1%}, DD: {train_test['test_max_dd']:.1%}")

    print(f"\n  Split-Half:")
    print(f"    Sharpe correlation: {split_half['sharpe_correlation']:.3f}")
    print(f"    Both positive: {split_half['both_positive_pct']:.0%}")

    if wf_fixed is not None:
        wf_pos = (wf_fixed["sharpe"] > 0).sum()
        print(f"\n  Walk-Forward (fixed params): {wf_pos}/{len(wf_fixed)} positive, "
              f"mean OOS Sharpe {wf_fixed['sharpe'].mean():.3f}")
    if wf_selected is not None:
        wf_pos2 = (wf_selected["oos_sharpe"] > 0).sum()
        print(f"  Walk-Forward (param selection): {wf_pos2}/{len(wf_selected)} positive, "
              f"mean OOS Sharpe {wf_selected['oos_sharpe'].mean():.3f}")

    print(f"\n  Correlations:")
    print(f"    with H-012 (momentum): {correlations['h012_momentum_corr']}")
    print(f"    with H-031 (size):     {correlations['h031_size_corr']}")

    # Determine verdict
    verdict_criteria = {
        "positive_sharpe_pct": pos_pct >= 0.5,
        "mean_sharpe_positive": mean_sharpe > 0,
        "oos_sharpe_positive": train_test["test_sharpe"] > 0,
        "split_half_consistent": split_half["sharpe_correlation"] > 0,
        "wf_majority_positive": (wf_fixed is not None and
                                  (wf_fixed["sharpe"] > 0).sum() >= len(wf_fixed) / 2),
    }
    n_pass = sum(verdict_criteria.values())
    n_total = len(verdict_criteria)

    print(f"\n  Verdict Criteria ({n_pass}/{n_total} passed):")
    for name, passed in verdict_criteria.items():
        status = "PASS" if passed else "FAIL"
        print(f"    [{status}] {name}")

    if n_pass >= 4:
        verdict = "CONFIRMED"
        print(f"\n  >>> VERDICT: CONFIRMED -- Strong evidence for volume concentration factor.")
    elif n_pass >= 3:
        verdict = "CONDITIONAL"
        print(f"\n  >>> VERDICT: CONDITIONAL -- Some evidence, needs more validation.")
    else:
        verdict = "REJECTED"
        print(f"\n  >>> VERDICT: REJECTED -- Insufficient evidence.")

    # ===== 10. Save results =====
    results_file = Path(__file__).parent / "results.json"
    results_data = {
        "hypothesis": "H-091",
        "name": "Volume Concentration (Herfindahl) Factor",
        "description": (
            "Cross-sectional factor: long low-Herfindahl (uniform volume) assets, "
            "short high-Herfindahl (concentrated volume) assets"
        ),
        "fee_rate_bps": FEE_RATE * 10000,
        "universe_size": len(closes.columns),
        "n_days": len(closes),
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "verdict": verdict,
        "full_scan": {
            "n_combos": len(scan_results),
            "pct_positive_sharpe": round(float(pos_pct), 3),
            "mean_sharpe": round(float(mean_sharpe), 3),
            "median_sharpe": round(float(median_sharpe), 3),
            "best_params": f"W{best_window}_R{best_rebal}_N{best_n_long}",
            "best_sharpe": round(float(best["sharpe"]), 3),
            "best_annual_ret": round(float(best["annual_ret"]), 4),
            "best_max_dd": round(float(best["max_dd"]), 4),
            "best_win_rate": round(float(best["win_rate"]), 4),
            "best_n_trades": int(best["n_trades"]),
            "all_results": scan_results.to_dict("records"),
        },
        "train_test_70_30": train_test,
        "split_half": split_half,
        "walk_forward_fixed": {
            "params": f"W{best_window}_R{best_rebal}_N{best_n_long}",
            "n_folds": len(wf_fixed) if wf_fixed is not None else 0,
            "positive_folds": int((wf_fixed["sharpe"] > 0).sum()) if wf_fixed is not None else 0,
            "mean_oos_sharpe": round(float(wf_fixed["sharpe"].mean()), 3) if wf_fixed is not None else 0,
            "mean_oos_annual_ret": round(float(wf_fixed["annual_ret"].mean()), 4) if wf_fixed is not None else 0,
            "folds": wf_fixed.to_dict("records") if wf_fixed is not None else [],
        },
        "walk_forward_selected": {
            "n_folds": len(wf_selected) if wf_selected is not None else 0,
            "positive_folds": int((wf_selected["oos_sharpe"] > 0).sum()) if wf_selected is not None else 0,
            "mean_oos_sharpe": round(float(wf_selected["oos_sharpe"].mean()), 3) if wf_selected is not None else 0,
            "folds": wf_selected.to_dict("records") if wf_selected is not None else [],
        },
        "correlations": correlations,
        "parameter_robustness": {
            "pct_positive_sharpe": round(float(pos_pct), 3),
            "mean_sharpe": round(float(mean_sharpe), 3),
            "median_sharpe": round(float(median_sharpe), 3),
        },
        "verdict_criteria": {k: bool(v) for k, v in verdict_criteria.items()},
    }

    with open(results_file, "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\n  Results saved to {results_file}")
