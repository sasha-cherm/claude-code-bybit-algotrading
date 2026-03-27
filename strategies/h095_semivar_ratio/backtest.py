"""
H-095: Realized Semivariance Ratio Factor

Rank 14 crypto assets by the ratio of upside realized volatility to downside
realized volatility over a lookback window.
- Upside semi-variance: variance of positive returns only over lookback
- Downside semi-variance: variance of negative returns only over lookback
- Factor = sqrt(upside_semivar) / sqrt(downside_semivar)
- Long top-N (positive skew), short bottom-N (negative skew)
- Dollar-neutral: equal $ on long side and short side

Intuition: assets with favorable realized skew (more upside than downside
volatility) should outperform on a risk-adjusted basis.

Validation: walk-forward (6 folds, 300d train, 90d test), split-half,
70/30 train/test, parameter robustness, correlation with H-012 momentum.
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
LOOKBACKS = [10, 20, 30, 40, 60]       # semivariance lookback window
REBAL_FREQS = [3, 5, 7]                # rebalance every N days
N_LONGS = [3, 4, 5]                    # top/bottom N

# Walk-forward config
WF_FOLDS = 6
WF_TRAIN = 300
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


def semivariance_ratio(closes, lookback):
    """
    Compute the realized semivariance ratio factor for each asset/day.

    For each asset on each day:
      - Compute daily log returns over the lookback window
      - Upside semi-variance = variance of returns > 0
      - Downside semi-variance = variance of returns < 0
      - Factor = sqrt(upside_semivar) / sqrt(downside_semivar)

    Higher values = more upside vol relative to downside vol (positive skew).
    Returns DataFrame of factor values (same shape as closes).
    """
    log_returns = np.log(closes / closes.shift(1))

    factor = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)

    for col in closes.columns:
        rets = log_returns[col]
        for i in range(lookback, len(rets)):
            window = rets.iloc[i - lookback:i]
            up = window[window > 0]
            down = window[window < 0]

            # Need at least 3 observations on each side for meaningful variance
            if len(up) >= 3 and len(down) >= 3:
                up_var = up.var()
                down_var = down.var()
                if down_var > 0 and up_var > 0:
                    factor.iloc[i, factor.columns.get_loc(col)] = (
                        np.sqrt(up_var) / np.sqrt(down_var)
                    )

    return factor


def semivariance_ratio_vectorized(closes, lookback):
    """
    Vectorized version of the semivariance ratio computation.
    Uses rolling windows for speed.
    """
    log_returns = np.log(closes / closes.shift(1))
    factor = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)

    for col in closes.columns:
        rets = log_returns[col].values
        n = len(rets)
        ratios = np.full(n, np.nan)

        for i in range(lookback, n):
            window = rets[i - lookback:i]
            # Filter out NaN
            window = window[~np.isnan(window)]
            up = window[window > 0]
            down = window[window < 0]

            if len(up) >= 3 and len(down) >= 3:
                up_std = np.std(up, ddof=1)
                down_std = np.std(down, ddof=1)
                if down_std > 0:
                    ratios[i] = up_std / down_std

        factor[col] = ratios

    return factor


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
# Fee robustness (5bps per leg)
# =========================================================================

def run_xs_factor_with_fee(closes, ranking_series, rebal_freq, n_long,
                           fee_rate, n_short=None, warmup=65):
    """Same as run_xs_factor but with configurable fee rate."""
    if n_short is None:
        n_short = n_long

    n = len(closes)
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    prev_weights = pd.Series(0.0, index=closes.columns)

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

            ranked = valid.sort_values(ascending=False)
            longs = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * fee_rate

            port_ret = (new_weights * log_rets).sum() - fee_drag
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
    """Run all parameter combinations on the full period."""
    print("\n" + "=" * 70)
    print("H-095: REALIZED SEMIVARIANCE RATIO FACTOR -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE*10000:.0f} bps per trade")

    # Pre-compute rankings for all lookback values
    print("\n  Pre-computing semivariance ratios for all lookbacks...")
    rankings = {}
    for lb in LOOKBACKS:
        print(f"    lookback={lb}...", end=" ", flush=True)
        rankings[lb] = semivariance_ratio_vectorized(closes, lb)
        valid_count = rankings[lb].notna().sum().sum()
        print(f"done ({valid_count} valid factor values)")

    results = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking = rankings[lookback]
        warmup = lookback + 5

        res = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup)
        tag = f"L{lookback}_R{rebal}_N{n_long}"
        results.append({
            "tag": tag,
            "lookback": lookback,
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

    return df, rankings


# =========================================================================
# 70/30 Train/Test Split
# =========================================================================

def run_train_test_split(closes, split_ratio=0.7):
    """Run parameter scan on 70% train, evaluate best on 30% test."""
    n = len(closes)
    split_idx = int(n * split_ratio)
    train_closes = closes.iloc[:split_idx]
    test_closes = closes.iloc[split_idx:]

    print(f"\n  70/30 Train/Test Split")
    print(f"  Train: {train_closes.index[0].date()} to {train_closes.index[-1].date()} ({len(train_closes)} days)")
    print(f"  Test:  {test_closes.index[0].date()} to {test_closes.index[-1].date()} ({len(test_closes)} days)")

    # Find best params on train set
    best_sharpe = -999
    best_params = None
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking = semivariance_ratio_vectorized(train_closes, lookback)
        warmup = lookback + 5
        res = run_xs_factor(train_closes, ranking, rebal, n_long, warmup=warmup)
        if res["sharpe"] > best_sharpe:
            best_sharpe = res["sharpe"]
            best_params = (lookback, rebal, n_long)

    lookback, rebal, n_long = best_params
    print(f"  Train best: L{lookback}_R{rebal}_N{n_long} (Sharpe {best_sharpe:.3f})")

    # Evaluate on test set
    test_ranking = semivariance_ratio_vectorized(test_closes, lookback)
    warmup = lookback + 5
    res_test = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=warmup)
    print(f"  Test result: Sharpe {res_test['sharpe']:.3f}, "
          f"Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}")

    return {
        "train_best_params": f"L{lookback}_R{rebal}_N{n_long}",
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

def run_split_half(closes):
    """Split data into two halves, run scan on each, compare rankings."""
    n = len(closes)
    mid = n // 2
    half1_closes = closes.iloc[:mid]
    half2_closes = closes.iloc[mid:]

    print(f"\n  Split-Half Validation")
    print(f"  Half 1: {half1_closes.index[0].date()} to {half1_closes.index[-1].date()} ({len(half1_closes)} days)")
    print(f"  Half 2: {half2_closes.index[0].date()} to {half2_closes.index[-1].date()} ({len(half2_closes)} days)")

    results_h1 = []
    results_h2 = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking1 = semivariance_ratio_vectorized(half1_closes, lookback)
        warmup = lookback + 5
        res1 = run_xs_factor(half1_closes, ranking1, rebal, n_long, warmup=warmup)

        ranking2 = semivariance_ratio_vectorized(half2_closes, lookback)
        res2 = run_xs_factor(half2_closes, ranking2, rebal, n_long, warmup=warmup)

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

def run_walk_forward(closes, lookback, rebal, n_long):
    """
    Walk-forward validation with FIXED params: 6 folds, 90d test each.
    Folds go from most recent backwards.
    """
    print(f"\n  Walk-Forward (Fixed Params): L{lookback}_R{rebal}_N{n_long}")
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

        test_ranking = semivariance_ratio_vectorized(test_closes, lookback)
        warmup = min(lookback + 5, len(test_closes) // 2)

        res = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=warmup)

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


def run_walk_forward_param_selection(closes):
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
        test_closes = closes.iloc[test_start_idx:test_end_idx]

        if len(test_closes) < 30 or len(train_closes) < 100:
            break

        # Step 1: find best params on train set
        best_sharpe = -999
        best_params = None
        for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
            ranking = semivariance_ratio_vectorized(train_closes, lookback)
            warmup = lookback + 5
            if warmup >= len(train_closes) - 30:
                continue
            res = run_xs_factor(train_closes, ranking, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_params = (lookback, rebal, n_long)

        if best_params is None:
            break

        # Step 2: evaluate best params on test set
        lookback, rebal, n_long = best_params
        test_ranking = semivariance_ratio_vectorized(test_closes, lookback)
        warmup = min(lookback + 5, len(test_closes) // 2)
        res = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "train_best_params": f"L{lookback}_R{rebal}_N{n_long}",
            "train_sharpe": round(best_sharpe, 3),
            "oos_sharpe": res["sharpe"],
            "oos_annual_ret": res["annual_ret"],
            "oos_max_dd": res["max_dd"],
        })
        print(f"    Fold {fold+1}: train best=L{lookback}_R{rebal}_N{n_long} "
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
# Correlation with H-012 (Momentum)
# =========================================================================

def compute_h012_correlation(closes, lookback, rebal, n_long):
    """Compute daily return correlation between semivariance ratio factor and H-012 momentum."""
    print(f"\n  Correlation with H-012 (60d Momentum)")

    # Run semivariance ratio factor
    sv_ranking = semivariance_ratio_vectorized(closes, lookback)
    warmup_sv = lookback + 5
    res_sv = run_xs_factor(closes, sv_ranking, rebal, n_long, warmup=warmup_sv)

    # Run H-012 momentum (60d lookback, rebal 5d, N=4)
    mom_ranking = closes.pct_change(60)
    res_mom = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)

    eq_sv = res_sv["equity"]
    eq_mom = res_mom["equity"]

    rets_sv = eq_sv.pct_change().dropna()
    rets_mom = eq_mom.pct_change().dropna()

    common = rets_sv.index.intersection(rets_mom.index)
    if len(common) < 50:
        print("    Insufficient overlap for correlation")
        return 0.0

    corr = rets_sv.loc[common].corr(rets_mom.loc[common])
    print(f"    Daily return correlation: {corr:.3f}")
    print(f"    H-012 Momentum:          Sharpe {res_mom['sharpe']:.3f}, Ann {res_mom['annual_ret']:.1%}")
    print(f"    H-095 SemiVar Ratio:     Sharpe {res_sv['sharpe']:.3f}, Ann {res_sv['annual_ret']:.1%}")
    return round(corr, 3)


# =========================================================================
# Fee Robustness (5bps per leg = 10bps round-trip)
# =========================================================================

def run_fee_robustness(closes, lookback, rebal, n_long):
    """Test how performance degrades at higher fee levels."""
    print(f"\n  Fee Robustness (best params: L{lookback}_R{rebal}_N{n_long})")
    fee_levels = [0.0, 0.0003, 0.0005, 0.0006, 0.0010, 0.0015, 0.0020]
    ranking = semivariance_ratio_vectorized(closes, lookback)
    warmup = lookback + 5

    results = []
    for fee in fee_levels:
        res = run_xs_factor_with_fee(closes, ranking, rebal, n_long,
                                     fee_rate=fee, warmup=warmup)
        bps = fee * 10000
        print(f"    Fee {bps:.0f}bps: Sharpe {res['sharpe']:.3f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")
        results.append({
            "fee_bps": bps,
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        })

    # Check at 5bps per leg (10bps round-trip)
    ranking_5bps = [r for r in results if r["fee_bps"] == 5.0]
    if ranking_5bps:
        print(f"\n    At 5bps/leg: Sharpe {ranking_5bps[0]['sharpe']:.3f}")

    return results


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    print("H-095: Realized Semivariance Ratio Factor")
    print("=" * 70)

    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")

    if len(daily) < 10:
        print("ERROR: Not enough assets loaded. Aborting.")
        sys.exit(1)

    # Build closes panel
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})

    # Align: drop rows where all NaN, forward fill, then drop remaining NaN
    closes = closes.dropna(how="all").ffill().dropna()

    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")
    print(f"Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    # ===== 1. Full parameter scan =====
    scan_results, precomputed_rankings = run_full_scan(closes)

    # ===== 2. Best parameters =====
    best = scan_results.nlargest(1, "sharpe").iloc[0]
    best_lookback = int(best["lookback"])
    best_rebal = int(best["rebal"])
    best_n_long = int(best["n_long"])
    print(f"\n  Best full-period params: L{best_lookback}_R{best_rebal}_N{best_n_long}")
    print(f"  Sharpe: {best['sharpe']:.3f}, Ann Return: {best['annual_ret']:.1%}, "
          f"Max DD: {best['max_dd']:.1%}, Win Rate: {best['win_rate']:.1%}")

    # ===== 3. 70/30 Train/Test Split =====
    train_test = run_train_test_split(closes)

    # ===== 4. Split-Half Validation =====
    split_half = run_split_half(closes)

    # ===== 5. Walk-Forward (fixed params) =====
    wf_fixed = run_walk_forward(closes, best_lookback, best_rebal, best_n_long)

    # ===== 6. Walk-Forward with parameter selection =====
    wf_selected = run_walk_forward_param_selection(closes)

    # ===== 7. Correlation with H-012 =====
    h012_corr = compute_h012_correlation(closes, best_lookback, best_rebal, best_n_long)

    # ===== 8. Fee Robustness =====
    fee_results = run_fee_robustness(closes, best_lookback, best_rebal, best_n_long)

    # ===== 9. Parameter Robustness =====
    pos_pct = (scan_results["sharpe"] > 0).mean()
    mean_sharpe = scan_results["sharpe"].mean()
    median_sharpe = scan_results["sharpe"].median()

    # ===== 10. Summary =====
    print("\n" + "=" * 70)
    print("SUMMARY: H-095 Realized Semivariance Ratio Factor")
    print("=" * 70)
    print(f"  Parameter combos tested: {len(scan_results)}")
    print(f"  Positive Sharpe: {(scan_results['sharpe'] > 0).sum()}/{len(scan_results)} ({pos_pct:.0%})")
    print(f"  Mean Sharpe: {mean_sharpe:.3f}, Median: {median_sharpe:.3f}")
    print(f"  Best full-period: L{best_lookback}_R{best_rebal}_N{best_n_long}, "
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

    print(f"\n  Correlation with H-012 (momentum): {h012_corr}")

    # Fee robustness at 5bps
    fee_5bps = [r for r in fee_results if r["fee_bps"] == 5.0]
    if fee_5bps:
        print(f"  Fee robustness at 5bps/leg: Sharpe {fee_5bps[0]['sharpe']:.3f}")

    # ===== 11. Save results =====
    results_file = Path(__file__).parent / "results.json"
    results_data = {
        "hypothesis": "H-095",
        "name": "Realized Semivariance Ratio Factor",
        "description": "Cross-sectional factor: long assets with high upside/downside vol ratio (positive skew), short assets with low ratio (negative skew)",
        "fee_rate_bps": FEE_RATE * 10000,
        "universe_size": len(closes.columns),
        "n_days": len(closes),
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "full_scan": {
            "n_combos": len(scan_results),
            "pct_positive_sharpe": round(float(pos_pct), 3),
            "mean_sharpe": round(float(mean_sharpe), 3),
            "median_sharpe": round(float(median_sharpe), 3),
            "best_params": f"L{best_lookback}_R{best_rebal}_N{best_n_long}",
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
            "params": f"L{best_lookback}_R{best_rebal}_N{best_n_long}",
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
        "h012_correlation": h012_corr,
        "fee_robustness": fee_results,
        "parameter_robustness": {
            "pct_positive_sharpe": round(float(pos_pct), 3),
            "mean_sharpe": round(float(mean_sharpe), 3),
            "median_sharpe": round(float(median_sharpe), 3),
        },
    }

    with open(results_file, "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\n  Results saved to {results_file}")
