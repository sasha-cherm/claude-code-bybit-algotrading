"""
H-014 Anti-Martingale: Walk-Forward Validation + Portfolio Correlation Analysis
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import summary, returns_from_equity, sharpe_ratio
from strategies.daily_trend_multi_asset.strategy import (
    generate_signals,
    resample_to_daily,
)
from strategies.anti_martingale.backtest import run_anti_martingale_backtest


def walk_forward_validation():
    """Rolling walk-forward: train on 12mo, test on 3mo, roll 3mo."""
    print("=== H-014 Walk-Forward Validation ===\n")

    # Load BTC daily data
    df_1h = fetch_and_cache("BTC/USDT", "1h", limit_days=730)
    daily = resample_to_daily(df_1h)
    prices = daily["close"]
    print(f"Data: {prices.index[0].date()} to {prices.index[-1].date()}, {len(prices)} bars\n")

    # Fixed-split test first (70/30)
    split_idx = int(len(prices) * 0.7)
    train_prices = prices.iloc[:split_idx]
    test_prices = prices.iloc[split_idx:]
    print(f"Fixed split: train {train_prices.index[0].date()}-{train_prices.index[-1].date()} "
          f"({len(train_prices)} bars)")
    print(f"             test  {test_prices.index[0].date()}-{test_prices.index[-1].date()} "
          f"({len(test_prices)} bars)\n")

    # Test a range of robust parameters on training set
    best_sharpe = -999
    best_params = None
    param_results = []

    for entry_lb in [10, 20, 40]:
        for add_pct in [0.03, 0.05, 0.08, 0.10]:
            for trail_pct in [0.08, 0.10, 0.15]:
                for init_alloc in [0.10, 0.15, 0.20]:
                    result = run_anti_martingale_backtest(
                        train_prices, mode="long_only",
                        entry_lookback=entry_lb, add_pct=add_pct,
                        trail_pct=trail_pct, initial_alloc=init_alloc,
                        add_alloc=init_alloc, max_adds=8,
                    )
                    m = result["metrics"]
                    param_results.append({
                        "entry_lb": entry_lb, "add_pct": add_pct,
                        "trail_pct": trail_pct, "init_alloc": init_alloc,
                        "is_sharpe": m["sharpe_ratio"],
                    })
                    if m["sharpe_ratio"] > best_sharpe:
                        best_sharpe = m["sharpe_ratio"]
                        best_params = {
                            "entry_lookback": entry_lb, "add_pct": add_pct,
                            "trail_pct": trail_pct, "initial_alloc": init_alloc,
                            "add_alloc": init_alloc, "max_adds": 8,
                        }

    print(f"Best IS params: {best_params}")
    print(f"Best IS Sharpe: {best_sharpe:.3f}\n")

    # Run OOS with best params
    oos_result = run_anti_martingale_backtest(test_prices, mode="long_only", **best_params)
    oos_m = oos_result["metrics"]
    print(f"OOS Sharpe: {oos_m['sharpe_ratio']:.3f}")
    print(f"OOS Annual: {oos_m['annual_return']:+.1%}")
    print(f"OOS MaxDD:  {oos_m['max_drawdown']:.1%}")
    print(f"OOS Trades: {oos_m.get('n_trades', 0)}")
    print(f"OOS WR:     {oos_m.get('win_rate', 0):.0%}\n")

    # Run OOS with several top params (check for robustness)
    df_params = pd.DataFrame(param_results).sort_values("is_sharpe", ascending=False)
    print("OOS performance of top 5 IS params:")
    oos_sharpes = []
    for _, row in df_params.head(5).iterrows():
        params = {
            "entry_lookback": int(row["entry_lb"]),
            "add_pct": row["add_pct"],
            "trail_pct": row["trail_pct"],
            "initial_alloc": row["init_alloc"],
            "add_alloc": row["init_alloc"],
            "max_adds": 8,
        }
        r = run_anti_martingale_backtest(test_prices, mode="long_only", **params)
        m = r["metrics"]
        oos_sharpes.append(m["sharpe_ratio"])
        print(f"  IS={row['is_sharpe']:.2f} → OOS={m['sharpe_ratio']:.2f}  "
              f"Ann={m['annual_return']:+.1%}  DD={m['max_drawdown']:.1%}")

    print(f"\nMean OOS Sharpe (top 5): {np.mean(oos_sharpes):.3f}")

    # Rolling walk-forward (12mo train, 3mo test, 3mo roll)
    print("\n" + "=" * 80)
    print("ROLLING WALK-FORWARD (12mo train, 3mo test)")
    print("=" * 80)

    train_window = 365  # days
    test_window = 90    # days
    step = 90           # roll by 90 days

    fold_results = []
    start = 0
    fold = 0

    while start + train_window + test_window <= len(prices):
        train_end = start + train_window
        test_end = min(train_end + test_window, len(prices))

        train_p = prices.iloc[start:train_end]
        test_p = prices.iloc[train_end:test_end]

        if len(test_p) < 30:
            break

        # Find best params on training set
        best_s = -999
        best_p = None
        for entry_lb in [10, 20, 40]:
            for add_pct in [0.03, 0.05, 0.08, 0.10]:
                for trail_pct in [0.08, 0.10, 0.15]:
                    r = run_anti_martingale_backtest(
                        train_p, mode="long_only",
                        entry_lookback=entry_lb, add_pct=add_pct,
                        trail_pct=trail_pct, initial_alloc=0.15,
                        add_alloc=0.15, max_adds=8,
                    )
                    if r["metrics"]["sharpe_ratio"] > best_s:
                        best_s = r["metrics"]["sharpe_ratio"]
                        best_p = {
                            "entry_lookback": entry_lb, "add_pct": add_pct,
                            "trail_pct": trail_pct, "initial_alloc": 0.15,
                            "add_alloc": 0.15, "max_adds": 8,
                        }

        # Test OOS
        oos_r = run_anti_martingale_backtest(test_p, mode="long_only", **best_p)
        oos_m = oos_r["metrics"]

        fold_results.append({
            "fold": fold,
            "train": f"{train_p.index[0].date()}-{train_p.index[-1].date()}",
            "test": f"{test_p.index[0].date()}-{test_p.index[-1].date()}",
            "is_sharpe": best_s,
            "oos_sharpe": oos_m["sharpe_ratio"],
            "oos_annual": oos_m["annual_return"],
            "oos_dd": oos_m["max_drawdown"],
            "oos_trades": oos_m.get("n_trades", 0),
        })

        print(f"  Fold {fold}: train {train_p.index[0].date()}-{train_p.index[-1].date()} | "
              f"test {test_p.index[0].date()}-{test_p.index[-1].date()} | "
              f"IS={best_s:.2f} → OOS={oos_m['sharpe_ratio']:.2f}  "
              f"Ann={oos_m['annual_return']:+.1%}  DD={oos_m['max_drawdown']:.1%}  "
              f"T={oos_m.get('n_trades', 0)}")

        start += step
        fold += 1

    if fold_results:
        oos_sharpes = [f["oos_sharpe"] for f in fold_results]
        print(f"\nRolling WF Summary:")
        print(f"  Folds: {len(fold_results)}")
        print(f"  Mean OOS Sharpe: {np.mean(oos_sharpes):.3f}")
        print(f"  Median OOS Sharpe: {np.median(oos_sharpes):.3f}")
        print(f"  Positive folds: {sum(1 for s in oos_sharpes if s > 0)}/{len(oos_sharpes)}")

    return best_params, fold_results


def correlation_analysis(best_params: dict):
    """Check correlation of H-014 returns with H-009 and H-012."""
    print("\n" + "=" * 80)
    print("CORRELATION WITH EXISTING PORTFOLIO STRATEGIES")
    print("=" * 80 + "\n")

    # Load BTC data
    df_1h = fetch_and_cache("BTC/USDT", "1h", limit_days=730)
    daily = resample_to_daily(df_1h)
    prices = daily["close"]

    # H-014 equity curve
    r014 = run_anti_martingale_backtest(prices, mode="long_only", **best_params)
    eq_014 = r014["equity"]

    # H-009 equity curve (EMA 5/40 with vol targeting)
    signals = generate_signals(prices, 5, 40)
    # Simplified H-009: just compute returns from EMA signal without vol targeting
    # For correlation purposes, we just need the direction
    h009_returns = signals.shift(1) * prices.pct_change()
    h009_returns = h009_returns.dropna()
    eq_009 = 10000 * (1 + h009_returns).cumprod()

    # H-012: Need to compute from multi-asset data
    # For now just load 14 assets and compute XSMom returns
    from lib.data_fetch import fetch_and_cache as fac
    assets = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
              "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
              "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT"]

    daily_closes = {}
    for sym in assets:
        try:
            d = fac(sym, "1h", limit_days=730)
            daily_closes[sym] = resample_to_daily(d)["close"]
        except:
            pass
    closes = pd.DataFrame(daily_closes).dropna(how="all").ffill().dropna()

    # XSMom backtest (60d lookback, 5d rebal, top/bottom 4)
    lookback = 60
    n_long = 4
    n_short = 4
    rebal_freq = 5

    xsmom_returns = pd.Series(0.0, index=closes.index)
    current_weights = {}

    for i in range(lookback + 1, len(closes)):
        # Mark-to-market
        if current_weights:
            daily_ret = 0.0
            for sym, w in current_weights.items():
                if sym in closes.columns:
                    r = (closes[sym].iloc[i] / closes[sym].iloc[i - 1]) - 1
                    daily_ret += w * r
            xsmom_returns.iloc[i] = daily_ret

        # Rebalance every N days
        if (i - lookback - 1) % rebal_freq == 0:
            # Lagged ranking
            cur = closes.iloc[i - 1]
            past = closes.iloc[i - 1 - lookback]
            rets = (cur / past - 1).dropna().sort_values(ascending=False)
            longs = rets.index[:n_long]
            shorts = rets.index[-n_short:]
            current_weights = {}
            for s in longs:
                current_weights[s] = 1.0 / n_long
            for s in shorts:
                current_weights[s] = -1.0 / n_short

    eq_012 = 10000 * (1 + xsmom_returns).cumprod()

    # Align all equity curves
    common_idx = eq_014.index.intersection(eq_009.index).intersection(eq_012.index)
    if len(common_idx) < 60:
        print("Insufficient overlapping data for correlation analysis")
        return

    ret_014 = eq_014.loc[common_idx].pct_change().dropna()
    ret_009 = eq_009.loc[common_idx].pct_change().dropna()
    ret_012 = eq_012.loc[common_idx].pct_change().dropna()

    # Align
    common = ret_014.index.intersection(ret_009.index).intersection(ret_012.index)
    ret_014 = ret_014.loc[common]
    ret_009 = ret_009.loc[common]
    ret_012 = ret_012.loc[common]

    corr_009_014 = ret_009.corr(ret_014)
    corr_012_014 = ret_012.corr(ret_014)
    corr_009_012 = ret_009.corr(ret_012)

    print(f"Correlation matrix (daily returns):")
    print(f"  H-009 vs H-014: {corr_009_014:.3f}")
    print(f"  H-012 vs H-014: {corr_012_014:.3f}")
    print(f"  H-009 vs H-012: {corr_009_012:.3f}")

    # Portfolio analysis: add H-014 to existing portfolio
    # Current: 20% H-009, 60% H-011, 20% H-012
    # Option A: 15% H-009, 55% H-011, 15% H-012, 15% H-014
    # Option B: 20% H-009, 40% H-011, 20% H-012, 20% H-014

    # H-011 is mostly flat (close to risk-free when OUT), so model as near-zero returns
    # When IN, it's ~30-40% annualized at 5x with near-zero vol
    # For portfolio analysis, use the actual funding rate data

    print(f"\n--- Individual Strategy Performance (full period) ---")
    print(f"  H-009 (BTC EMA): Sharpe={sharpe_ratio(ret_009, periods_per_year=365):.2f}  "
          f"Ann={((1+ret_009).prod() ** (365/len(ret_009)) - 1):+.1%}")
    print(f"  H-012 (XSMom):   Sharpe={sharpe_ratio(ret_012, periods_per_year=365):.2f}  "
          f"Ann={((1+ret_012).prod() ** (365/len(ret_012)) - 1):+.1%}")
    print(f"  H-014 (AntiMart): Sharpe={sharpe_ratio(ret_014, periods_per_year=365):.2f}  "
          f"Ann={((1+ret_014).prod() ** (365/len(ret_014)) - 1):+.1%}")

    # Portfolio combinations (excluding H-011 for simplicity - it's uncorrelated anyway)
    combos = {
        "Current (50/50 H009/H012)": {"H-009": 0.50, "H-012": 0.50},
        "+H014 (33/33/33)": {"H-009": 0.33, "H-012": 0.33, "H-014": 0.33},
        "+H014 (40/30/30)": {"H-009": 0.40, "H-012": 0.30, "H-014": 0.30},
        "+H014 (25/25/50)": {"H-009": 0.25, "H-012": 0.25, "H-014": 0.50},
    }

    print(f"\n--- Portfolio Combinations (ex-H-011, daily rebal) ---")
    returns_map = {"H-009": ret_009, "H-012": ret_012, "H-014": ret_014}

    for name, weights in combos.items():
        port_ret = sum(w * returns_map[s] for s, w in weights.items())
        port_eq = 10000 * (1 + port_ret).cumprod()
        port_sharpe = sharpe_ratio(port_ret, periods_per_year=365)
        port_ann = (port_eq.iloc[-1] / port_eq.iloc[0]) ** (365 / len(port_eq)) - 1
        port_dd = ((port_eq.cummax() - port_eq) / port_eq.cummax()).max()
        print(f"  {name:30s}: Sharpe={port_sharpe:.2f}  Ann={port_ann:+.1%}  DD={port_dd:.1%}")


if __name__ == "__main__":
    best_params, fold_results = walk_forward_validation()
    if best_params:
        correlation_analysis(best_params)
