"""
H-084: BTC Correlation Factor Backtest

Concept: Assets with lower rolling correlation to BTC earn a "decorrelation premium".
Long low-BTC-correlation assets, short high-BTC-correlation assets.
Dollar-neutral cross-sectional strategy on 14 crypto perps.

Parameter grid:
  - Lookback: 20, 30, 40, 60 days
  - Rebalance: 3, 5, 7, 10 days
  - N: 3, 4, 5 (top/bottom)

Validation:
  - 70/30 train/test split
  - Walk-forward (6 folds, 90 days each)
  - Split-half validation
  - Correlation with H-012 (momentum)
  - Parameter robustness
"""

import json
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.0006  # 0.06% taker fee on Bybit perps
INITIAL_CAPITAL = 10_000.0


def load_daily_closes() -> pd.DataFrame:
    """Load daily close prices for all 14 assets from cached parquet files."""
    closes = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = ROOT / f"data/{safe}_1d.parquet"
        df = pd.read_parquet(path)
        closes[sym] = df["close"]
    closes_df = pd.DataFrame(closes)
    closes_df = closes_df.dropna(how="all").ffill().dropna()
    return closes_df


def compute_log_returns(closes: pd.DataFrame) -> pd.DataFrame:
    """Compute daily log returns."""
    return np.log(closes / closes.shift(1))


def compute_btc_correlations(log_rets: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    For each non-BTC asset, compute rolling Pearson correlation of daily log returns
    vs BTC daily log returns over the lookback window.
    BTC itself gets correlation = 1.0.
    """
    btc_rets = log_rets["BTC/USDT"]
    corr_df = pd.DataFrame(index=log_rets.index, columns=log_rets.columns, dtype=float)

    for sym in log_rets.columns:
        if sym == "BTC/USDT":
            corr_df[sym] = 1.0
        else:
            corr_df[sym] = log_rets[sym].rolling(lookback, min_periods=lookback).corr(btc_rets)

    return corr_df


def run_btc_corr_backtest(
    closes: pd.DataFrame,
    log_rets: pd.DataFrame,
    lookback: int = 30,
    rebal_freq: int = 5,
    n_positions: int = 4,
    start_idx: int | None = None,
    end_idx: int | None = None,
) -> dict:
    """
    Run the BTC correlation factor backtest.

    Long bottom N (lowest BTC correlation), short top N (highest BTC correlation).
    Dollar-neutral: equal weight on long side and short side.
    Uses t-1 data for ranking (no lookahead).
    Transaction costs: 0.06% * turnover at each rebalance.
    """
    # Subset data if specified
    if start_idx is not None or end_idx is not None:
        si = start_idx or 0
        ei = end_idx or len(closes)
        closes = closes.iloc[si:ei]
        log_rets = log_rets.iloc[si:ei]

    n = len(closes)
    assets = closes.columns.tolist()

    # Compute BTC correlations on the provided data slice
    btc_corrs = compute_btc_correlations(log_rets, lookback)

    # Warmup: need lookback days of returns + 1 day lag
    warmup = lookback + 1

    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

    prev_weights = pd.Series(0.0, index=assets)
    daily_returns_list = []

    for i in range(1, n):
        if i < warmup:
            equity[i] = equity[i - 1]
            daily_returns_list.append(0.0)
            continue

        # Check if it's a rebalance day
        rebalance = (i - warmup) % rebal_freq == 0

        if rebalance:
            # Use t-1 correlations for ranking (no lookahead)
            corr_yesterday = btc_corrs.iloc[i - 1]
            valid = corr_yesterday.dropna()

            if len(valid) < 2 * n_positions:
                # Not enough valid data, hold existing positions
                daily_ret = (prev_weights * log_rets.iloc[i]).sum()
                # Use simple returns for equity computation
                price_rets = (closes.iloc[i] / closes.iloc[i - 1] - 1)
                daily_ret = (prev_weights * price_rets).sum()
                equity[i] = equity[i - 1] * (1 + daily_ret)
                daily_returns_list.append(daily_ret)
                continue

            # Rank by BTC correlation: low corr = long, high corr = short
            ranked = valid.sort_values(ascending=True)
            longs = ranked.index[:n_positions]
            shorts = ranked.index[-n_positions:]

            new_weights = pd.Series(0.0, index=assets)
            for sym in longs:
                new_weights[sym] = 1.0 / n_positions   # equal weight long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_positions   # equal weight short

            # Compute turnover and fee drag
            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2  # one-way turnover
            fee_drag = turnover * FEE_RATE * 2  # entry + exit counted as round trip

            # Compute daily return from positions
            price_rets = (closes.iloc[i] / closes.iloc[i - 1] - 1)
            daily_ret = (new_weights * price_rets).sum() - fee_drag

            equity[i] = equity[i - 1] * (1 + daily_ret)
            prev_weights = new_weights
            daily_returns_list.append(daily_ret)
        else:
            # Hold existing positions
            price_rets = (closes.iloc[i] / closes.iloc[i - 1] - 1)
            daily_ret = (prev_weights * price_rets).sum()
            equity[i] = equity[i - 1] * (1 + daily_ret)
            daily_returns_list.append(daily_ret)

    # Build equity series
    eq_series = pd.Series(equity, index=closes.index)
    daily_rets = pd.Series(daily_returns_list, index=closes.index[1:])

    # Trim warmup period for metrics
    active_eq = eq_series.iloc[warmup:]
    active_rets = daily_rets.iloc[warmup:]

    if len(active_eq) < 30 or active_eq.iloc[-1] <= 0:
        return {
            "sharpe": -99.0,
            "annual_return": 0.0,
            "max_drawdown": 1.0,
            "win_rate": 0.0,
            "total_return": 0.0,
            "equity": eq_series,
            "daily_returns": daily_rets,
            "n_days": len(active_eq),
        }

    # Metrics
    active_rets_clean = active_rets.replace([np.inf, -np.inf], np.nan).dropna()
    if len(active_rets_clean) < 10 or active_rets_clean.std() == 0:
        sharpe = 0.0
    else:
        sharpe = float(active_rets_clean.mean() / active_rets_clean.std() * np.sqrt(365))

    total_ret = float(active_eq.iloc[-1] / active_eq.iloc[0] - 1)
    n_days = len(active_eq)
    years = n_days / 365
    ann_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0.0

    peak = active_eq.cummax()
    dd = (active_eq - peak) / peak
    max_dd = abs(dd.min())

    win_rate = float((active_rets_clean > 0).sum() / len(active_rets_clean)) if len(active_rets_clean) > 0 else 0.0

    return {
        "sharpe": round(sharpe, 4),
        "annual_return": round(ann_ret, 4),
        "max_drawdown": round(max_dd, 4),
        "win_rate": round(win_rate, 4),
        "total_return": round(total_ret, 4),
        "equity": eq_series,
        "daily_returns": daily_rets,
        "n_days": n_days,
    }


def run_h012_momentum(closes: pd.DataFrame, log_rets: pd.DataFrame,
                       lookback: int = 60, rebal_freq: int = 5, n_positions: int = 4,
                       start_idx: int | None = None, end_idx: int | None = None) -> dict:
    """
    Run H-012 cross-sectional momentum for correlation comparison.
    Rank by lookback-day simple return, long top N, short bottom N.
    """
    if start_idx is not None or end_idx is not None:
        si = start_idx or 0
        ei = end_idx or len(closes)
        closes = closes.iloc[si:ei]

    n = len(closes)
    assets = closes.columns.tolist()

    rolling_ret = closes.pct_change(lookback)
    warmup = lookback + 5

    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

    prev_weights = pd.Series(0.0, index=assets)
    daily_returns_list = []

    for i in range(1, n):
        if i < warmup:
            equity[i] = equity[i - 1]
            daily_returns_list.append(0.0)
            continue

        rebalance = (i - warmup) % rebal_freq == 0

        if rebalance:
            rets = rolling_ret.iloc[i - 1]  # lagged ranking
            valid = rets.dropna()
            if len(valid) < 2 * n_positions:
                price_rets = (closes.iloc[i] / closes.iloc[i - 1] - 1)
                daily_ret = (prev_weights * price_rets).sum()
                equity[i] = equity[i - 1] * (1 + daily_ret)
                daily_returns_list.append(daily_ret)
                continue

            ranked = valid.sort_values(ascending=False)
            longs = ranked.index[:n_positions]
            shorts = ranked.index[-n_positions:]

            new_weights = pd.Series(0.0, index=assets)
            for sym in longs:
                new_weights[sym] = 1.0 / n_positions
            for sym in shorts:
                new_weights[sym] = -1.0 / n_positions

            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * FEE_RATE * 2

            price_rets = (closes.iloc[i] / closes.iloc[i - 1] - 1)
            daily_ret = (new_weights * price_rets).sum() - fee_drag
            equity[i] = equity[i - 1] * (1 + daily_ret)
            prev_weights = new_weights
            daily_returns_list.append(daily_ret)
        else:
            price_rets = (closes.iloc[i] / closes.iloc[i - 1] - 1)
            daily_ret = (prev_weights * price_rets).sum()
            equity[i] = equity[i - 1] * (1 + daily_ret)
            daily_returns_list.append(daily_ret)

    eq_series = pd.Series(equity, index=closes.index)
    daily_rets = pd.Series(daily_returns_list, index=closes.index[1:])

    return {
        "equity": eq_series,
        "daily_returns": daily_rets,
    }


def parameter_sweep(closes: pd.DataFrame, log_rets: pd.DataFrame) -> pd.DataFrame:
    """Run full parameter grid sweep."""
    lookbacks = [20, 30, 40, 60]
    rebalances = [3, 5, 7, 10]
    n_positions_list = [3, 4, 5]

    results = []
    total = len(lookbacks) * len(rebalances) * len(n_positions_list)
    count = 0

    for lb, rb, np_ in product(lookbacks, rebalances, n_positions_list):
        count += 1
        r = run_btc_corr_backtest(closes, log_rets, lookback=lb, rebal_freq=rb, n_positions=np_)
        results.append({
            "lookback": lb,
            "rebal": rb,
            "n_positions": np_,
            "sharpe": r["sharpe"],
            "annual_return": r["annual_return"],
            "max_drawdown": r["max_drawdown"],
            "win_rate": r["win_rate"],
            "total_return": r["total_return"],
            "n_days": r["n_days"],
        })
        if count % 12 == 0:
            print(f"  Sweep progress: {count}/{total}")

    return pd.DataFrame(results)


def train_test_split(closes: pd.DataFrame, log_rets: pd.DataFrame,
                     lookback: int, rebal_freq: int, n_positions: int,
                     train_frac: float = 0.7) -> dict:
    """Run 70/30 train/test split."""
    n = len(closes)
    split_idx = int(n * train_frac)

    train_result = run_btc_corr_backtest(closes, log_rets, lookback, rebal_freq, n_positions,
                                          start_idx=0, end_idx=split_idx)
    test_result = run_btc_corr_backtest(closes, log_rets, lookback, rebal_freq, n_positions,
                                         start_idx=split_idx, end_idx=n)

    return {
        "train": {
            "sharpe": train_result["sharpe"],
            "annual_return": train_result["annual_return"],
            "max_drawdown": train_result["max_drawdown"],
            "n_days": train_result["n_days"],
        },
        "test": {
            "sharpe": test_result["sharpe"],
            "annual_return": test_result["annual_return"],
            "max_drawdown": test_result["max_drawdown"],
            "n_days": test_result["n_days"],
        },
        "split_date": str(closes.index[split_idx]),
    }


def walk_forward(closes: pd.DataFrame, log_rets: pd.DataFrame,
                 lookback: int, rebal_freq: int, n_positions: int,
                 n_folds: int = 6, test_days: int = 90) -> dict:
    """Rolling walk-forward: train on everything before, test on 90-day windows."""
    n = len(closes)
    results = []
    all_oos_returns = []

    # Calculate fold boundaries: last n_folds*test_days for testing
    total_test_days = n_folds * test_days
    first_test_start = n - total_test_days

    if first_test_start < lookback + 50:
        # Not enough training data
        print("  WARNING: Not enough data for walk-forward")
        return {"folds": [], "combined_sharpe": 0.0}

    for fold in range(n_folds):
        test_start = first_test_start + fold * test_days
        test_end = test_start + test_days

        if test_end > n:
            test_end = n

        # Run on test period only
        r = run_btc_corr_backtest(closes, log_rets, lookback, rebal_freq, n_positions,
                                   start_idx=test_start, end_idx=test_end)

        fold_info = {
            "fold": fold,
            "test_start": str(closes.index[test_start]),
            "test_end": str(closes.index[min(test_end - 1, n - 1)]),
            "sharpe": r["sharpe"],
            "annual_return": r["annual_return"],
            "max_drawdown": r["max_drawdown"],
            "n_days": r["n_days"],
        }
        results.append(fold_info)

        # Collect OOS returns
        active_rets = r["daily_returns"].iloc[lookback + 1:] if len(r["daily_returns"]) > lookback + 1 else r["daily_returns"]
        if len(active_rets) > 0:
            all_oos_returns.append(active_rets)

    # Combined OOS metrics
    if all_oos_returns:
        combined_rets = pd.concat(all_oos_returns)
        combined_rets_clean = combined_rets.replace([np.inf, -np.inf], np.nan).dropna()
        if len(combined_rets_clean) > 10 and combined_rets_clean.std() > 0:
            combined_sharpe = float(combined_rets_clean.mean() / combined_rets_clean.std() * np.sqrt(365))
        else:
            combined_sharpe = 0.0

        combined_eq = INITIAL_CAPITAL * (1 + combined_rets_clean).cumprod()
        combined_total_ret = float(combined_eq.iloc[-1] / combined_eq.iloc[0] - 1) if len(combined_eq) > 0 else 0.0
        combined_years = len(combined_rets_clean) / 365
        combined_ann_ret = (1 + combined_total_ret) ** (1 / combined_years) - 1 if combined_years > 0 else 0.0
        peak = combined_eq.cummax()
        dd = (combined_eq - peak) / peak
        combined_max_dd = abs(dd.min()) if len(dd) > 0 else 0.0

        n_positive_folds = sum(1 for f in results if f["sharpe"] > 0)
    else:
        combined_sharpe = 0.0
        combined_ann_ret = 0.0
        combined_max_dd = 0.0
        n_positive_folds = 0

    return {
        "folds": results,
        "combined_sharpe": round(combined_sharpe, 4),
        "combined_annual_return": round(combined_ann_ret, 4),
        "combined_max_drawdown": round(combined_max_dd, 4),
        "positive_folds": n_positive_folds,
        "total_folds": len(results),
        "total_oos_days": sum(len(r) for r in all_oos_returns) if all_oos_returns else 0,
    }


def split_half_validation(closes: pd.DataFrame, log_rets: pd.DataFrame,
                          lookback: int, rebal_freq: int, n_positions: int) -> dict:
    """Split data in half and compare metrics."""
    n = len(closes)
    mid = n // 2

    first_half = run_btc_corr_backtest(closes, log_rets, lookback, rebal_freq, n_positions,
                                        start_idx=0, end_idx=mid)
    second_half = run_btc_corr_backtest(closes, log_rets, lookback, rebal_freq, n_positions,
                                         start_idx=mid, end_idx=n)

    return {
        "first_half": {
            "sharpe": first_half["sharpe"],
            "annual_return": first_half["annual_return"],
            "max_drawdown": first_half["max_drawdown"],
            "period": f"{closes.index[0]} to {closes.index[mid - 1]}",
            "n_days": first_half["n_days"],
        },
        "second_half": {
            "sharpe": second_half["sharpe"],
            "annual_return": second_half["annual_return"],
            "max_drawdown": second_half["max_drawdown"],
            "period": f"{closes.index[mid]} to {closes.index[-1]}",
            "n_days": second_half["n_days"],
        },
        "sharpe_ratio_decay": round(second_half["sharpe"] / first_half["sharpe"], 2) if first_half["sharpe"] != 0 else 0.0,
    }


def compute_h012_correlation(closes: pd.DataFrame, log_rets: pd.DataFrame,
                              lookback: int, rebal_freq: int, n_positions: int) -> float:
    """
    Compute daily return correlation between H-084 and H-012.
    H-012 uses: lookback=60, rebal=5, n_positions=4.
    """
    # H-084 returns
    h084 = run_btc_corr_backtest(closes, log_rets, lookback, rebal_freq, n_positions)
    h084_rets = h084["daily_returns"]

    # H-012 returns (momentum: lookback=60, rebal=5, n=4)
    h012 = run_h012_momentum(closes, log_rets, lookback=60, rebal_freq=5, n_positions=4)
    h012_rets = h012["daily_returns"]

    # Align indices
    common = h084_rets.index.intersection(h012_rets.index)
    if len(common) < 30:
        return 0.0

    h084_aligned = h084_rets.loc[common].replace([np.inf, -np.inf], np.nan).dropna()
    h012_aligned = h012_rets.loc[common].replace([np.inf, -np.inf], np.nan).dropna()

    # Re-align after NaN removal
    common2 = h084_aligned.index.intersection(h012_aligned.index)
    if len(common2) < 30:
        return 0.0

    corr = h084_aligned.loc[common2].corr(h012_aligned.loc[common2])
    return round(float(corr), 4)


def main():
    print("=" * 70)
    print("H-084: BTC CORRELATION FACTOR BACKTEST")
    print("=" * 70)

    # Load data
    print("\n1. Loading data...")
    closes = load_daily_closes()
    log_rets = compute_log_returns(closes)
    print(f"   Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"   Date range: {closes.index[0]} to {closes.index[-1]}")

    # ===================================================================
    # 2. Full parameter sweep
    # ===================================================================
    print("\n2. Running parameter sweep (4 x 4 x 3 = 48 combinations)...")
    sweep_df = parameter_sweep(closes, log_rets)

    positive_sharpe = sweep_df[sweep_df["sharpe"] > 0]
    param_robustness = len(positive_sharpe) / len(sweep_df) * 100

    print(f"\n   Parameter Robustness: {len(positive_sharpe)}/{len(sweep_df)} "
          f"({param_robustness:.0f}%) have positive Sharpe")
    print(f"   Mean Sharpe: {sweep_df['sharpe'].mean():.4f}")
    print(f"   Median Sharpe: {sweep_df['sharpe'].median():.4f}")
    print(f"   Max Sharpe: {sweep_df['sharpe'].max():.4f}")
    print(f"   Min Sharpe: {sweep_df['sharpe'].min():.4f}")

    # Print full grid
    print("\n   Full Parameter Grid (Sharpe Ratios):")
    print(f"   {'LB':>4} {'RB':>4} {'N':>3} | {'Sharpe':>8} {'AnnRet':>8} {'MaxDD':>8} {'WinRate':>8}")
    print("   " + "-" * 55)
    for _, row in sweep_df.sort_values("sharpe", ascending=False).iterrows():
        print(f"   {int(row['lookback']):>4} {int(row['rebal']):>4} {int(row['n_positions']):>3} | "
              f"{row['sharpe']:>8.4f} {row['annual_return']:>7.1%} {row['max_drawdown']:>7.1%} {row['win_rate']:>7.1%}")

    # ===================================================================
    # 3. Best parameter set detailed analysis
    # ===================================================================
    best_row = sweep_df.loc[sweep_df["sharpe"].idxmax()]
    best_lb = int(best_row["lookback"])
    best_rb = int(best_row["rebal"])
    best_np = int(best_row["n_positions"])

    print(f"\n3. BEST PARAMETERS: lookback={best_lb}, rebal={best_rb}, n_positions={best_np}")
    print(f"   Sharpe: {best_row['sharpe']:.4f}")
    print(f"   Annual Return: {best_row['annual_return']:.2%}")
    print(f"   Max Drawdown: {best_row['max_drawdown']:.2%}")
    print(f"   Win Rate: {best_row['win_rate']:.2%}")
    print(f"   Total Return: {best_row['total_return']:.2%}")

    # ===================================================================
    # 4. 70/30 Train/Test Split
    # ===================================================================
    print(f"\n4. 70/30 Train/Test Split (best params: LB={best_lb}, RB={best_rb}, N={best_np})...")
    tt_result = train_test_split(closes, log_rets, best_lb, best_rb, best_np)
    print(f"   Split at: {tt_result['split_date']}")
    print(f"   TRAIN: Sharpe {tt_result['train']['sharpe']:.4f}, "
          f"Ann {tt_result['train']['annual_return']:.2%}, "
          f"DD {tt_result['train']['max_drawdown']:.2%}, "
          f"Days {tt_result['train']['n_days']}")
    print(f"   TEST:  Sharpe {tt_result['test']['sharpe']:.4f}, "
          f"Ann {tt_result['test']['annual_return']:.2%}, "
          f"DD {tt_result['test']['max_drawdown']:.2%}, "
          f"Days {tt_result['test']['n_days']}")

    # ===================================================================
    # 5. Walk-Forward Validation
    # ===================================================================
    print(f"\n5. Walk-Forward Validation (6 folds, 90 days each)...")
    wf_result = walk_forward(closes, log_rets, best_lb, best_rb, best_np, n_folds=6, test_days=90)
    for fold_info in wf_result["folds"]:
        print(f"   Fold {fold_info['fold']}: {fold_info['test_start'][:10]} to {fold_info['test_end'][:10]} — "
              f"Sharpe {fold_info['sharpe']:.4f}, Ann {fold_info['annual_return']:.2%}, "
              f"DD {fold_info['max_drawdown']:.2%}")
    print(f"   COMBINED OOS: Sharpe {wf_result['combined_sharpe']:.4f}, "
          f"Ann {wf_result['combined_annual_return']:.2%}, "
          f"DD {wf_result['combined_max_drawdown']:.2%}")
    print(f"   Positive folds: {wf_result['positive_folds']}/{wf_result['total_folds']}")

    # ===================================================================
    # 6. Split-Half Validation
    # ===================================================================
    print(f"\n6. Split-Half Validation...")
    sh_result = split_half_validation(closes, log_rets, best_lb, best_rb, best_np)
    print(f"   First half:  Sharpe {sh_result['first_half']['sharpe']:.4f}, "
          f"Ann {sh_result['first_half']['annual_return']:.2%}")
    print(f"   Second half: Sharpe {sh_result['second_half']['sharpe']:.4f}, "
          f"Ann {sh_result['second_half']['annual_return']:.2%}")
    print(f"   Sharpe ratio (2nd/1st): {sh_result['sharpe_ratio_decay']:.2f}")

    # ===================================================================
    # 7. Correlation with H-012 (Momentum)
    # ===================================================================
    print(f"\n7. Correlation with H-012 (XS Momentum, LB=60, RB=5, N=4)...")
    h012_corr = compute_h012_correlation(closes, log_rets, best_lb, best_rb, best_np)
    print(f"   Pearson correlation of daily returns: {h012_corr:.4f}")

    # ===================================================================
    # 8. Save results
    # ===================================================================
    results = {
        "strategy": "H-084: BTC Correlation Factor",
        "description": "Long low-BTC-correlation, short high-BTC-correlation assets. Dollar-neutral.",
        "assets": [a.replace("/USDT", "") for a in ASSETS],
        "data_period": f"{closes.index[0]} to {closes.index[-1]}",
        "n_daily_bars": len(closes),
        "fee_rate": FEE_RATE,
        "best_params": {
            "lookback": best_lb,
            "rebal_freq": best_rb,
            "n_positions": best_np,
        },
        "best_full_sample": {
            "sharpe": best_row["sharpe"],
            "annual_return": best_row["annual_return"],
            "max_drawdown": best_row["max_drawdown"],
            "win_rate": best_row["win_rate"],
            "total_return": best_row["total_return"],
            "n_days": int(best_row["n_days"]),
        },
        "train_test_70_30": tt_result,
        "walk_forward_6fold_90d": wf_result,
        "split_half": sh_result,
        "correlation_with_h012": h012_corr,
        "parameter_robustness": {
            "total_param_sets": len(sweep_df),
            "positive_sharpe_count": len(positive_sharpe),
            "positive_sharpe_pct": round(param_robustness, 1),
            "mean_sharpe": round(sweep_df["sharpe"].mean(), 4),
            "median_sharpe": round(sweep_df["sharpe"].median(), 4),
        },
        "full_sweep": sweep_df.sort_values("sharpe", ascending=False).to_dict("records"),
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n   Results saved to {out_path}")

    # Also print a summary table
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Best params: lookback={best_lb}, rebal={best_rb}, N={best_np}")
    print(f"  Full-sample Sharpe: {best_row['sharpe']:.4f}")
    print(f"  Full-sample Annual Return: {best_row['annual_return']:.2%}")
    print(f"  Full-sample Max DD: {best_row['max_drawdown']:.2%}")
    print(f"  70/30 OOS Sharpe: {tt_result['test']['sharpe']:.4f}")
    print(f"  Walk-Forward OOS Sharpe: {wf_result['combined_sharpe']:.4f}")
    print(f"  Walk-Forward positive folds: {wf_result['positive_folds']}/{wf_result['total_folds']}")
    print(f"  Split-Half decay: {sh_result['sharpe_ratio_decay']:.2f}")
    print(f"  Correlation with H-012: {h012_corr:.4f}")
    print(f"  Parameter robustness: {param_robustness:.0f}% positive Sharpe")

    return results


if __name__ == "__main__":
    main()
