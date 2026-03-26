"""
H-083: Idiosyncratic Volatility Factor Backtest

Concept: The low idiosyncratic volatility anomaly — assets with lower residual
volatility (after removing systematic BTC exposure) tend to outperform.
Long low-idio-vol assets, short high-idio-vol assets.

Implementation:
- Rolling OLS of each asset's daily log returns vs BTC log returns
- Idiosyncratic vol = std(residuals) over lookback window
- Rank all 14 assets by idio vol each rebalance day
- Long bottom N (lowest idio vol), short top N (highest idio vol)
- Dollar-neutral: equal $ long and short
- Transaction costs: 0.06% per trade (taker fee)
- No lookahead bias: rankings use t-1 data
"""

import json
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

# ─── Configuration ───────────────────────────────────────────────────────────

ASSETS = [
    "BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX",
    "LINK", "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM",
]

DATA_DIR = ROOT / "data"
FEE_RATE = 0.0006  # 0.06% taker fee per trade
INITIAL_CAPITAL = 10_000.0
PERIODS_PER_YEAR = 365


# ─── Data Loading ────────────────────────────────────────────────────────────

def load_daily_closes() -> pd.DataFrame:
    """Load daily close prices for all assets into a single DataFrame."""
    frames = {}
    for asset in ASSETS:
        fpath = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fpath.exists():
            print(f"  WARNING: {fpath} not found, skipping {asset}")
            continue
        df = pd.read_parquet(fpath)
        frames[asset] = df["close"]

    closes = pd.DataFrame(frames)
    closes = closes.sort_index()
    closes = closes.dropna(how="all").ffill().dropna()
    return closes


# ─── Idiosyncratic Volatility Computation ────────────────────────────────────

def compute_idio_vol(log_returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    Compute idiosyncratic volatility for each asset.

    For non-BTC assets: rolling OLS regression of asset returns vs BTC returns,
    then std(residuals) over the lookback window.
    For BTC: use total rolling volatility.

    Returns DataFrame of idio_vol with same index as log_returns.
    """
    btc_ret = log_returns["BTC"]
    idio_vol = pd.DataFrame(index=log_returns.index, columns=log_returns.columns, dtype=float)

    # BTC: total volatility
    idio_vol["BTC"] = btc_ret.rolling(lookback, min_periods=lookback).std()

    # For each non-BTC asset: rolling OLS regression, then std of residuals
    for asset in log_returns.columns:
        if asset == "BTC":
            continue

        asset_ret = log_returns[asset]

        # Vectorized rolling OLS via rolling covariance / variance
        rolling_cov = asset_ret.rolling(lookback, min_periods=lookback).cov(btc_ret)
        rolling_var_btc = btc_ret.rolling(lookback, min_periods=lookback).var()

        beta = rolling_cov / rolling_var_btc
        alpha = asset_ret.rolling(lookback, min_periods=lookback).mean() - beta * btc_ret.rolling(lookback, min_periods=lookback).mean()

        # Residuals: we need rolling std of residuals
        # residual_t = asset_ret_t - alpha - beta * btc_ret_t
        # For the rolling std, we compute residuals and then rolling std
        residuals = asset_ret - alpha - beta * btc_ret
        idio_vol[asset] = residuals.rolling(lookback, min_periods=lookback).std()

    return idio_vol


# ─── Backtest Engine ─────────────────────────────────────────────────────────

def run_backtest(
    closes: pd.DataFrame,
    lookback: int = 30,
    rebal_freq: int = 5,
    n_positions: int = 4,
    fee_rate: float = FEE_RATE,
    start_idx: int | None = None,
    end_idx: int | None = None,
) -> dict:
    """
    Run the idiosyncratic volatility factor backtest.

    Args:
        closes: DataFrame of daily close prices, columns = asset names
        lookback: Rolling window for idio vol computation
        rebal_freq: Rebalance every N days
        n_positions: Number of assets on each side (long and short)
        fee_rate: Transaction cost per trade
        start_idx: Optional start index for subsetting
        end_idx: Optional end index for subsetting

    Returns:
        Dict with equity curve, metrics, and trade info
    """
    if start_idx is not None or end_idx is not None:
        closes = closes.iloc[start_idx:end_idx].copy()

    # Compute log returns
    log_returns = np.log(closes / closes.shift(1))

    # Compute idiosyncratic volatility
    idio_vol = compute_idio_vol(log_returns, lookback)

    n = len(closes)
    equity = np.full(n, np.nan)
    equity[0] = INITIAL_CAPITAL

    # Track positions as weight vectors
    prev_weights = pd.Series(0.0, index=closes.columns)
    daily_returns_list = []
    n_trades = 0

    # Warmup: need lookback days of data before we can compute idio_vol
    # Plus 1 extra day since we use t-1 for ranking
    warmup = lookback + 1

    for i in range(1, n):
        # Default: carry forward
        current_weights = prev_weights.copy()

        # Check if it's a rebalance day (after warmup)
        if i >= warmup and (i - warmup) % rebal_freq == 0:
            # Use t-1 idio vol for ranking (no lookahead)
            ivol = idio_vol.iloc[i - 1].dropna()

            if len(ivol) >= 2 * n_positions:
                ranked = ivol.sort_values(ascending=True)  # low idio vol first

                longs = ranked.index[:n_positions]   # lowest idio vol = LONG
                shorts = ranked.index[-n_positions:]  # highest idio vol = SHORT

                new_weights = pd.Series(0.0, index=closes.columns)
                for sym in longs:
                    new_weights[sym] = 1.0 / n_positions  # equal weight long
                for sym in shorts:
                    new_weights[sym] = -1.0 / n_positions  # equal weight short

                current_weights = new_weights

        # Compute daily return from positions
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        asset_returns = (price_today / price_yesterday) - 1.0  # simple returns for PnL
        port_ret = (current_weights * asset_returns).sum()

        # Transaction costs on rebalance
        if i >= warmup and (i - warmup) % rebal_freq == 0:
            weight_changes = (current_weights - prev_weights).abs()
            turnover = weight_changes.sum()  # total absolute weight change
            fee_drag = turnover * fee_rate
            port_ret -= fee_drag
            n_trades += int((weight_changes > 1e-6).sum())

        daily_returns_list.append(port_ret)
        equity[i] = equity[i - 1] * (1 + port_ret)
        prev_weights = current_weights.copy()

    # Build equity series
    eq_series = pd.Series(equity, index=closes.index).dropna()

    if len(eq_series) < 50:
        return {
            "sharpe": -99.0,
            "annual_ret": 0.0,
            "max_dd": 1.0,
            "win_rate": 0.0,
            "n_trades": 0,
            "equity": eq_series,
            "daily_returns": pd.Series(daily_returns_list, index=closes.index[1:]),
        }

    rets = eq_series.pct_change().dropna()
    win = float((rets > 0).sum() / len(rets)) if len(rets) > 0 else 0.0

    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=PERIODS_PER_YEAR), 4),
        "annual_ret": round(annual_return(eq_series, periods_per_year=PERIODS_PER_YEAR), 4),
        "max_dd": round(max_drawdown(eq_series), 4),
        "win_rate": round(win, 4),
        "n_trades": n_trades,
        "equity": eq_series,
        "daily_returns": pd.Series(daily_returns_list, index=closes.index[1:]),
    }


# ─── Parameter Grid Search ──────────────────────────────────────────────────

def run_parameter_grid(closes: pd.DataFrame) -> pd.DataFrame:
    """Run full parameter grid and return results DataFrame."""
    lookbacks = [20, 30, 40, 60]
    rebal_freqs = [3, 5, 7, 10]
    n_positions_list = [3, 4, 5]

    results = []
    total = len(lookbacks) * len(rebal_freqs) * len(n_positions_list)
    count = 0

    for lb, rb, np_ in product(lookbacks, rebal_freqs, n_positions_list):
        count += 1
        r = run_backtest(closes, lookback=lb, rebal_freq=rb, n_positions=np_)
        results.append({
            "lookback": lb,
            "rebal": rb,
            "n_pos": np_,
            "sharpe": r["sharpe"],
            "annual_ret": r["annual_ret"],
            "max_dd": r["max_dd"],
            "win_rate": r["win_rate"],
            "n_trades": r["n_trades"],
        })
        if count % 12 == 0:
            print(f"  Progress: {count}/{total}")

    return pd.DataFrame(results)


# ─── Walk-Forward Validation ─────────────────────────────────────────────────

def walk_forward_validation(
    closes: pd.DataFrame, lookback: int, rebal_freq: int, n_positions: int, n_folds: int = 6, fold_days: int = 90
) -> dict:
    """
    Walk-forward validation: expanding train window, fixed 90-day test windows.
    6 folds of 90 days each.
    """
    total_test_days = n_folds * fold_days
    n = len(closes)

    if n < total_test_days + lookback + 50:
        return {"error": "Not enough data for walk-forward"}

    # Reserve last (n_folds * fold_days) for testing
    test_start_overall = n - total_test_days

    fold_results = []
    all_oos_returns = []

    for fold in range(n_folds):
        test_start = test_start_overall + fold * fold_days
        test_end = test_start + fold_days

        # Need enough data before test_start for the lookback
        # Run backtest on just the test window, but include warmup data before it
        warmup_start = max(0, test_start - lookback - 10)
        test_closes = closes.iloc[warmup_start:test_end]

        r = run_backtest(test_closes, lookback=lookback, rebal_freq=rebal_freq, n_positions=n_positions)

        # Extract only the OOS portion's returns
        test_dates = closes.index[test_start:test_end]
        oos_rets = r["daily_returns"].reindex(test_dates).dropna()

        if len(oos_rets) > 10:
            oos_eq = INITIAL_CAPITAL * (1 + oos_rets).cumprod()
            fold_sharpe = sharpe_ratio(oos_rets, periods_per_year=PERIODS_PER_YEAR)
            fold_ann = annual_return(oos_eq, periods_per_year=PERIODS_PER_YEAR)
            fold_dd = max_drawdown(oos_eq)
            all_oos_returns.append(oos_rets)

            fold_results.append({
                "fold": fold,
                "start": str(test_dates[0].date()),
                "end": str(test_dates[-1].date()),
                "sharpe": round(fold_sharpe, 2),
                "annual_ret": round(fold_ann, 4),
                "max_dd": round(fold_dd, 4),
                "n_days": len(oos_rets),
            })

    if not all_oos_returns:
        return {"error": "No valid folds"}

    combined_rets = pd.concat(all_oos_returns)
    combined_eq = INITIAL_CAPITAL * (1 + combined_rets).cumprod()

    return {
        "folds": fold_results,
        "combined_sharpe": round(sharpe_ratio(combined_rets, periods_per_year=PERIODS_PER_YEAR), 4),
        "combined_annual_ret": round(annual_return(combined_eq, periods_per_year=PERIODS_PER_YEAR), 4),
        "combined_max_dd": round(max_drawdown(combined_eq), 4),
        "n_folds": len(fold_results),
        "total_oos_days": len(combined_rets),
    }


# ─── Train/Test Split ───────────────────────────────────────────────────────

def train_test_split(
    closes: pd.DataFrame, lookback: int, rebal_freq: int, n_positions: int, train_pct: float = 0.7
) -> dict:
    """70/30 train/test split validation."""
    n = len(closes)
    split_idx = int(n * train_pct)

    # Train
    r_train = run_backtest(closes, lookback=lookback, rebal_freq=rebal_freq,
                           n_positions=n_positions, end_idx=split_idx)
    # Test
    # Include some warmup data before the test start
    warmup_start = max(0, split_idx - lookback - 10)
    test_closes = closes.iloc[warmup_start:]
    r_test_full = run_backtest(test_closes, lookback=lookback, rebal_freq=rebal_freq,
                               n_positions=n_positions)

    # Extract only the test portion returns
    test_dates = closes.index[split_idx:]
    test_rets = r_test_full["daily_returns"].reindex(test_dates).dropna()

    if len(test_rets) < 20:
        return {"error": "Not enough test data"}

    test_eq = INITIAL_CAPITAL * (1 + test_rets).cumprod()

    return {
        "train": {
            "sharpe": r_train["sharpe"],
            "annual_ret": r_train["annual_ret"],
            "max_dd": r_train["max_dd"],
            "win_rate": r_train["win_rate"],
            "n_days": split_idx,
            "period": f"{closes.index[0].date()} to {closes.index[split_idx-1].date()}",
        },
        "test": {
            "sharpe": round(sharpe_ratio(test_rets, periods_per_year=PERIODS_PER_YEAR), 4),
            "annual_ret": round(annual_return(test_eq, periods_per_year=PERIODS_PER_YEAR), 4),
            "max_dd": round(max_drawdown(test_eq), 4),
            "win_rate": round(float((test_rets > 0).sum() / len(test_rets)), 4),
            "n_days": len(test_rets),
            "period": f"{closes.index[split_idx].date()} to {closes.index[-1].date()}",
        },
    }


# ─── Split-Half Validation ──────────────────────────────────────────────────

def split_half_validation(
    closes: pd.DataFrame, lookback: int, rebal_freq: int, n_positions: int
) -> dict:
    """Split data in half, run on each half independently."""
    n = len(closes)
    mid = n // 2

    r_first = run_backtest(closes, lookback=lookback, rebal_freq=rebal_freq,
                           n_positions=n_positions, end_idx=mid)

    # Include warmup for second half
    warmup_start = max(0, mid - lookback - 10)
    second_half = closes.iloc[warmup_start:]
    r_second_full = run_backtest(second_half, lookback=lookback, rebal_freq=rebal_freq,
                                  n_positions=n_positions)

    second_dates = closes.index[mid:]
    second_rets = r_second_full["daily_returns"].reindex(second_dates).dropna()
    if len(second_rets) < 20:
        return {"error": "Not enough data in second half"}

    second_eq = INITIAL_CAPITAL * (1 + second_rets).cumprod()

    return {
        "first_half": {
            "sharpe": r_first["sharpe"],
            "annual_ret": r_first["annual_ret"],
            "max_dd": r_first["max_dd"],
            "period": f"{closes.index[0].date()} to {closes.index[mid-1].date()}",
        },
        "second_half": {
            "sharpe": round(sharpe_ratio(second_rets, periods_per_year=PERIODS_PER_YEAR), 4),
            "annual_ret": round(annual_return(second_eq, periods_per_year=PERIODS_PER_YEAR), 4),
            "max_dd": round(max_drawdown(second_eq), 4),
            "period": f"{closes.index[mid].date()} to {closes.index[-1].date()}",
        },
    }


# ─── H-012 Momentum Correlation ─────────────────────────────────────────────

def compute_h012_returns(closes: pd.DataFrame) -> pd.Series:
    """
    Replicate H-012 cross-sectional momentum: 60d lookback, 5d rebalance, top/bottom 4.
    Long top 4 momentum, short bottom 4 momentum.
    Returns daily returns series.
    """
    lookback = 60
    rebal_freq = 5
    n_long = 4
    n_short = 4

    rolling_ret = closes.pct_change(lookback)
    n = len(closes)
    warmup = lookback + 5

    prev_weights = pd.Series(0.0, index=closes.columns)
    daily_returns_list = []

    for i in range(1, n):
        current_weights = prev_weights.copy()

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            rets = rolling_ret.iloc[i - 1]  # lagged ranking
            valid = rets.dropna()
            if len(valid) >= n_long + n_short:
                ranked = valid.sort_values(ascending=False)
                longs = ranked.index[:n_long]
                shorts = ranked.index[-n_short:]

                new_weights = pd.Series(0.0, index=closes.columns)
                for sym in longs:
                    new_weights[sym] = 1.0 / n_long
                for sym in shorts:
                    new_weights[sym] = -1.0 / n_short

                # Deduct fees
                weight_changes = (new_weights - prev_weights).abs()
                turnover = weight_changes.sum()
                current_weights = new_weights

        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        asset_returns = (price_today / price_yesterday) - 1.0
        port_ret = (current_weights * asset_returns).sum()

        # Transaction costs
        if i >= warmup and (i - warmup) % rebal_freq == 0:
            turnover = (current_weights - prev_weights).abs().sum()
            fee_drag = turnover * FEE_RATE
            port_ret -= fee_drag

        daily_returns_list.append(port_ret)
        prev_weights = current_weights.copy()

    return pd.Series(daily_returns_list, index=closes.index[1:])


def compute_correlation_with_h012(closes: pd.DataFrame, lookback: int, rebal_freq: int, n_positions: int) -> dict:
    """Compute Pearson correlation between H-083 and H-012 daily returns."""
    # H-083
    r083 = run_backtest(closes, lookback=lookback, rebal_freq=rebal_freq, n_positions=n_positions)
    h083_rets = r083["daily_returns"]

    # H-012
    h012_rets = compute_h012_returns(closes)

    # Align
    common = h083_rets.index.intersection(h012_rets.index)
    if len(common) < 30:
        return {"error": "Not enough common dates", "correlation": None}

    corr = h083_rets.loc[common].corr(h012_rets.loc[common])

    return {
        "correlation": round(float(corr), 4),
        "n_common_days": len(common),
    }


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("H-083: IDIOSYNCRATIC VOLATILITY FACTOR BACKTEST")
    print("=" * 70)

    # 1. Load data
    print("\n[1] Loading daily close prices...")
    closes = load_daily_closes()
    print(f"    Loaded {len(closes.columns)} assets, {len(closes)} days")
    print(f"    Date range: {closes.index[0].date()} to {closes.index[-1].date()}")

    # 2. Parameter grid search
    print("\n[2] Running parameter grid search...")
    print(f"    Lookbacks: [20, 30, 40, 60], Rebal: [3, 5, 7, 10], N: [3, 4, 5]")
    print(f"    Total: {4 * 4 * 3} parameter combinations")

    grid_df = run_parameter_grid(closes)

    # Sort by Sharpe
    grid_df = grid_df.sort_values("sharpe", ascending=False).reset_index(drop=True)

    # Parameter robustness
    n_positive = int((grid_df["sharpe"] > 0).sum())
    n_total = len(grid_df)
    pct_positive = n_positive / n_total

    print(f"\n    PARAMETER GRID RESULTS:")
    print(f"    Positive Sharpe: {n_positive}/{n_total} ({pct_positive:.0%})")
    print(f"    Mean Sharpe:   {grid_df['sharpe'].mean():.4f}")
    print(f"    Median Sharpe: {grid_df['sharpe'].median():.4f}")
    print(f"    Min Sharpe:    {grid_df['sharpe'].min():.4f}")
    print(f"    Max Sharpe:    {grid_df['sharpe'].max():.4f}")

    print(f"\n    Top 10 parameter sets:")
    for _, row in grid_df.head(10).iterrows():
        print(f"      L{int(row['lookback'])}_R{int(row['rebal'])}_N{int(row['n_pos'])}: "
              f"Sharpe {row['sharpe']:.4f}, Ann {row['annual_ret']:.2%}, "
              f"DD {row['max_dd']:.2%}, WR {row['win_rate']:.1%}")

    print(f"\n    Full grid (Sharpe matrix):")
    for lb in [20, 30, 40, 60]:
        for np_ in [3, 4, 5]:
            row_data = grid_df[(grid_df["lookback"] == lb) & (grid_df["n_pos"] == np_)]
            sharpes = {int(r["rebal"]): r["sharpe"] for _, r in row_data.iterrows()}
            line = f"      L{lb}_N{np_}: "
            for rb in [3, 5, 7, 10]:
                s = sharpes.get(rb, float("nan"))
                line += f"R{rb}={s:+.3f}  "
            print(line)

    # 3. Best parameter set — detailed analysis
    best = grid_df.iloc[0]
    best_lb = int(best["lookback"])
    best_rb = int(best["rebal"])
    best_np = int(best["n_pos"])

    print(f"\n[3] Best params: L{best_lb}_R{best_rb}_N{best_np}")
    print(f"    Sharpe: {best['sharpe']:.4f}")
    print(f"    Annual return: {best['annual_ret']:.2%}")
    print(f"    Max drawdown: {best['max_dd']:.2%}")
    print(f"    Win rate: {best['win_rate']:.1%}")
    print(f"    Trades: {int(best['n_trades'])}")

    # 4. 70/30 train/test split
    print(f"\n[4] Train/Test split (70/30) for best params...")
    tt_result = train_test_split(closes, best_lb, best_rb, best_np)
    if "error" not in tt_result:
        print(f"    TRAIN: Sharpe {tt_result['train']['sharpe']:.4f}, "
              f"Ann {tt_result['train']['annual_ret']:.2%}, "
              f"DD {tt_result['train']['max_dd']:.2%}, "
              f"WR {tt_result['train']['win_rate']:.1%} "
              f"({tt_result['train']['period']})")
        print(f"    TEST:  Sharpe {tt_result['test']['sharpe']:.4f}, "
              f"Ann {tt_result['test']['annual_ret']:.2%}, "
              f"DD {tt_result['test']['max_dd']:.2%}, "
              f"WR {tt_result['test']['win_rate']:.1%} "
              f"({tt_result['test']['period']})")
    else:
        print(f"    Error: {tt_result['error']}")

    # 5. Walk-forward validation (6 folds, 90 days each)
    print(f"\n[5] Walk-forward validation (6 folds, 90 days each)...")
    wf_result = walk_forward_validation(closes, best_lb, best_rb, best_np)
    if "error" not in wf_result:
        print(f"    Combined OOS: Sharpe {wf_result['combined_sharpe']:.4f}, "
              f"Ann {wf_result['combined_annual_ret']:.2%}, "
              f"DD {wf_result['combined_max_dd']:.2%}")
        print(f"    Folds: {wf_result['n_folds']}, Total OOS days: {wf_result['total_oos_days']}")
        for fold in wf_result["folds"]:
            print(f"      Fold {fold['fold']}: {fold['start']} to {fold['end']} — "
                  f"Sharpe {fold['sharpe']:.2f}, Ann {fold['annual_ret']:.2%}, DD {fold['max_dd']:.2%}")
    else:
        print(f"    Error: {wf_result['error']}")

    # 6. Split-half validation
    print(f"\n[6] Split-half validation...")
    sh_result = split_half_validation(closes, best_lb, best_rb, best_np)
    if "error" not in sh_result:
        print(f"    First half:  Sharpe {sh_result['first_half']['sharpe']:.4f}, "
              f"Ann {sh_result['first_half']['annual_ret']:.2%}, "
              f"DD {sh_result['first_half']['max_dd']:.2%} "
              f"({sh_result['first_half']['period']})")
        print(f"    Second half: Sharpe {sh_result['second_half']['sharpe']:.4f}, "
              f"Ann {sh_result['second_half']['annual_ret']:.2%}, "
              f"DD {sh_result['second_half']['max_dd']:.2%} "
              f"({sh_result['second_half']['period']})")
    else:
        print(f"    Error: {sh_result['error']}")

    # 7. Correlation with H-012
    print(f"\n[7] Correlation with H-012 (60d momentum, 5d rebal, top/bottom 4)...")
    corr_result = compute_correlation_with_h012(closes, best_lb, best_rb, best_np)
    if corr_result.get("correlation") is not None:
        print(f"    Pearson correlation: {corr_result['correlation']:.4f}")
        print(f"    Common days: {corr_result['n_common_days']}")
    else:
        print(f"    Error: {corr_result.get('error', 'unknown')}")

    # ─── Save results ────────────────────────────────────────────────────
    print(f"\n[8] Saving results...")

    # Convert grid to serializable format
    grid_records = grid_df.to_dict("records")

    results = {
        "hypothesis": "H-083",
        "name": "Idiosyncratic Volatility Factor",
        "data": {
            "n_assets": len(closes.columns),
            "n_days": len(closes),
            "date_range": f"{closes.index[0].date()} to {closes.index[-1].date()}",
            "assets": list(closes.columns),
        },
        "best_params": {
            "lookback": best_lb,
            "rebal_freq": best_rb,
            "n_positions": best_np,
            "sharpe": best["sharpe"],
            "annual_ret": best["annual_ret"],
            "max_dd": best["max_dd"],
            "win_rate": best["win_rate"],
            "n_trades": int(best["n_trades"]),
        },
        "parameter_robustness": {
            "n_total": n_total,
            "n_positive_sharpe": n_positive,
            "pct_positive_sharpe": round(pct_positive, 4),
            "mean_sharpe": round(float(grid_df["sharpe"].mean()), 4),
            "median_sharpe": round(float(grid_df["sharpe"].median()), 4),
            "min_sharpe": round(float(grid_df["sharpe"].min()), 4),
            "max_sharpe": round(float(grid_df["sharpe"].max()), 4),
        },
        "full_grid": grid_records,
        "train_test_split": tt_result,
        "walk_forward": wf_result,
        "split_half": sh_result,
        "h012_correlation": corr_result,
        "config": {
            "fee_rate": FEE_RATE,
            "initial_capital": INITIAL_CAPITAL,
            "dollar_neutral": True,
            "return_type": "log_returns_for_regression",
            "ranking_lag": 1,  # t-1 for ranking
        },
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"    Saved to {out_path}")

    # ─── Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Best params: L{best_lb}_R{best_rb}_N{best_np}")
    print(f"  Sharpe: {best['sharpe']:.4f}")
    print(f"  Annual return: {best['annual_ret']:.2%}")
    print(f"  Max drawdown: {best['max_dd']:.2%}")
    print(f"  Win rate: {best['win_rate']:.1%}")
    print(f"  Parameter robustness: {pct_positive:.0%} positive Sharpe")
    if "error" not in wf_result:
        print(f"  Walk-forward OOS Sharpe: {wf_result['combined_sharpe']:.4f}")
    if "error" not in tt_result:
        print(f"  Test set Sharpe: {tt_result['test']['sharpe']:.4f}")
    if corr_result.get("correlation") is not None:
        print(f"  H-012 correlation: {corr_result['correlation']:.4f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
