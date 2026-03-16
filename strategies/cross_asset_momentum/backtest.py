"""
Backtest runner for H-003: Cross-Asset Momentum Rotation.
Custom multi-asset backtest since the base engine is single-asset.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.metrics import summary
from strategies.cross_asset_momentum.strategy import generate_rotation_signals

RESULTS_DIR = Path(__file__).resolve().parent


def run_backtest(
    fast_window: int = 168,
    slow_window: int = 504,
    rebalance_bars: int = 168,
    fast_weight: float = 0.6,
    slow_weight: float = 0.4,
    position_size_pct: float = 0.05,
    initial_capital: float = 10_000.0,
    fee_rate: float = 0.001,
    slippage_bps: float = 2.0,
):
    """Run the cross-asset momentum rotation backtest."""
    root = Path(__file__).resolve().parent.parent.parent

    # Load all three assets
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    prices = {}
    for sym in symbols:
        safe = sym.replace("/", "_")
        path = root / f"data/{safe}_1h.parquet"
        prices[sym] = pd.read_parquet(path)

    print(f"Loaded: {', '.join(f'{s}: {len(prices[s])} bars' for s in symbols)}")

    # Generate signals
    signals = generate_rotation_signals(
        prices,
        fast_window=fast_window,
        slow_window=slow_window,
        rebalance_bars=rebalance_bars,
        fast_weight=fast_weight,
        slow_weight=slow_weight,
    )

    # Align everything to common index
    common_idx = signals[symbols[0]].index
    closes = pd.DataFrame({sym: prices[sym]["close"].reindex(common_idx) for sym in symbols})

    n = len(common_idx)
    capital = initial_capital
    slippage = slippage_bps / 10_000

    # Track positions per asset: {sym: (direction, size_usd, entry_price)}
    positions = {sym: (0, 0.0, 0.0) for sym in symbols}
    equity = np.zeros(n)
    equity[0] = capital
    trades = []

    for i in range(1, n):
        # Mark-to-market
        unrealized = 0.0
        for sym in symbols:
            direction, size_usd, entry_price = positions[sym]
            if direction != 0 and entry_price > 0:
                current_price = closes[sym].iloc[i]
                pnl_pct = (current_price / entry_price - 1) * direction
                unrealized += size_usd * pnl_pct

        equity[i] = capital + unrealized

        # Check for signal changes
        for sym in symbols:
            target = int(signals[sym].iloc[i])
            current_dir = positions[sym][0]

            if target != current_dir:
                # Close existing position
                if current_dir != 0:
                    _, size_usd, entry_price = positions[sym]
                    exit_price = closes[sym].iloc[i] * (1 - current_dir * slippage)
                    pnl_pct = (exit_price / entry_price - 1) * current_dir
                    pnl = size_usd * pnl_pct - fee_rate * size_usd  # exit fee
                    capital += pnl + size_usd  # return capital + pnl
                    trades.append({
                        "symbol": sym,
                        "direction": "long" if current_dir == 1 else "short",
                        "entry_time": str(positions[sym]),  # simplified
                        "exit_time": str(common_idx[i]),
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 4),
                    })
                    positions[sym] = (0, 0.0, 0.0)

                # Open new position
                if target != 0:
                    alloc = equity[i] * position_size_pct
                    entry_price = closes[sym].iloc[i] * (1 + target * slippage)
                    capital -= alloc + fee_rate * alloc  # entry fee
                    positions[sym] = (target, alloc, entry_price)

                # Update equity after trades
                unrealized = 0.0
                for s in symbols:
                    d, sz, ep = positions[s]
                    if d != 0 and ep > 0:
                        cp = closes[s].iloc[i]
                        unrealized += sz * ((cp / ep - 1) * d)
                equity[i] = capital + unrealized

    # Close all open positions at end
    for sym in symbols:
        direction, size_usd, entry_price = positions[sym]
        if direction != 0:
            exit_price = closes[sym].iloc[-1] * (1 - direction * slippage)
            pnl_pct = (exit_price / entry_price - 1) * direction
            pnl = size_usd * pnl_pct - fee_rate * size_usd
            capital += pnl + size_usd
            trades.append({
                "symbol": sym,
                "direction": "long" if direction == 1 else "short",
                "exit_time": str(common_idx[-1]),
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 4),
            })
    equity[-1] = capital

    # Compute metrics
    equity_series = pd.Series(equity, index=common_idx)
    trade_pnls = pd.Series([t["pnl"] for t in trades]) if trades else pd.Series(dtype=float)
    results = summary(equity_series, trade_pnls, periods_per_year=8760)

    results["strategy"] = "H-003: Cross-Asset Momentum Rotation"
    results["mode"] = "futures"
    results["initial_capital"] = initial_capital
    results["final_capital"] = round(float(equity[-1]), 2)
    results["position_size_pct"] = position_size_pct
    results["params"] = {
        "fast_window": fast_window,
        "slow_window": slow_window,
        "rebalance_bars": rebalance_bars,
        "fast_weight": fast_weight,
        "slow_weight": slow_weight,
        "position_size_pct": position_size_pct,
    }

    # Per-asset breakdown
    per_asset = {}
    for sym in symbols:
        sym_trades = [t for t in trades if t["symbol"] == sym]
        sym_pnls = [t["pnl"] for t in sym_trades]
        per_asset[sym] = {
            "n_trades": len(sym_trades),
            "total_pnl": round(sum(sym_pnls), 2),
            "avg_pnl": round(np.mean(sym_pnls), 2) if sym_pnls else 0,
        }
    results["per_asset"] = per_asset

    # Save
    with open(RESULTS_DIR / "results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        trades_df.to_csv(RESULTS_DIR / "trades.csv", index=False)

    print("\n=== H-003: Cross-Asset Momentum Rotation Results ===")
    for k, v in results.items():
        if k not in ("params", "per_asset"):
            print(f"  {k}: {v}")
    print("\n  Per-asset breakdown:")
    for sym, stats in per_asset.items():
        print(f"    {sym}: {stats}")

    return results


def parameter_sweep():
    """Test different parameter combinations."""
    param_sets = [
        {"fast_window": 168, "slow_window": 504, "rebalance_bars": 168, "position_size_pct": 0.05},
        {"fast_window": 168, "slow_window": 504, "rebalance_bars": 168, "position_size_pct": 0.10},
        {"fast_window": 168, "slow_window": 504, "rebalance_bars": 168, "position_size_pct": 0.20},
        {"fast_window": 72, "slow_window": 336, "rebalance_bars": 72, "position_size_pct": 0.10},
        {"fast_window": 336, "slow_window": 720, "rebalance_bars": 336, "position_size_pct": 0.10},
        {"fast_window": 168, "slow_window": 504, "rebalance_bars": 72, "position_size_pct": 0.10},
    ]

    all_results = []
    for params in param_sets:
        print(f"\n--- Testing: {params} ---")
        results = run_backtest(**params)
        all_results.append(results)

    all_results.sort(key=lambda x: x.get("sharpe_ratio", 0), reverse=True)

    print("\n\n=== SWEEP SUMMARY (sorted by Sharpe) ===")
    for i, r in enumerate(all_results):
        print(f"  #{i+1}: Sharpe={r['sharpe_ratio']:.2f} | Annual={r['annual_return']*100:.1f}% | "
              f"MaxDD={r['max_drawdown']*100:.1f}% | Trades={r.get('n_trades', 0)} | "
              f"PosSize={r['position_size_pct']}")

    with open(RESULTS_DIR / "sweep_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    return all_results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep", action="store_true", help="Run parameter sweep")
    args = parser.parse_args()

    if args.sweep:
        parameter_sweep()
    else:
        run_backtest()
