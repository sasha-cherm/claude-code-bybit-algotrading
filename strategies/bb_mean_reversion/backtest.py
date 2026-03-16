"""
Backtest runner for H-002: BB Mean Reversion (BTC Spot).
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.backtest import Backtest, BacktestConfig
from strategies.bb_mean_reversion.strategy import generate_signals

RESULTS_DIR = Path(__file__).resolve().parent


def run_backtest(
    data_path: str = "data/BTC_USDT_1h.parquet",
    bb_window: int = 20,
    bb_std: float = 2.0,
    rsi_window: int = 14,
    rsi_entry: float = 30.0,
    rsi_exit: float = 60.0,
    stop_loss_pct: float = 0.03,
):
    """Run the BB mean reversion backtest."""
    root = Path(__file__).resolve().parent.parent.parent
    df = pd.read_parquet(root / data_path)

    print(f"Data: {len(df)} candles from {df.index[0]} to {df.index[-1]}")

    signals = generate_signals(
        df,
        bb_window=bb_window,
        bb_std=bb_std,
        rsi_window=rsi_window,
        rsi_entry=rsi_entry,
        rsi_exit=rsi_exit,
        stop_loss_pct=stop_loss_pct,
    )

    print(f"Signal counts: long={int((signals == 1).sum())}, flat={int((signals == 0).sum())}")

    config = BacktestConfig(
        initial_capital=10_000.0,
        fee_rate=0.001,
        slippage_bps=2.0,
        mode="spot",
    )

    bt = Backtest(config)
    results = bt.run(df, signals)

    # Add strategy params to results
    results["strategy"] = "H-002: BB Mean Reversion"
    results["params"] = {
        "bb_window": bb_window,
        "bb_std": bb_std,
        "rsi_window": rsi_window,
        "rsi_entry": rsi_entry,
        "rsi_exit": rsi_exit,
        "stop_loss_pct": stop_loss_pct,
    }

    bt.save_results(results, RESULTS_DIR / "results.json")

    trades_df = bt.get_trades_df()
    if not trades_df.empty:
        trades_df.to_csv(RESULTS_DIR / "trades.csv", index=False)

    print("\n=== H-002: BB Mean Reversion Results ===")
    for k, v in results.items():
        if k != "params":
            print(f"  {k}: {v}")

    return results


def parameter_sweep():
    """Run a parameter sweep to find optimal settings."""
    root = Path(__file__).resolve().parent.parent.parent
    df = pd.read_parquet(root / "data/BTC_USDT_1h.parquet")

    param_sets = [
        {"bb_window": 20, "bb_std": 2.0, "rsi_entry": 30, "rsi_exit": 60, "stop_loss_pct": 0.03},
        {"bb_window": 20, "bb_std": 2.0, "rsi_entry": 35, "rsi_exit": 55, "stop_loss_pct": 0.03},
        {"bb_window": 20, "bb_std": 2.5, "rsi_entry": 25, "rsi_exit": 60, "stop_loss_pct": 0.03},
        {"bb_window": 30, "bb_std": 2.0, "rsi_entry": 30, "rsi_exit": 60, "stop_loss_pct": 0.03},
        {"bb_window": 20, "bb_std": 1.5, "rsi_entry": 35, "rsi_exit": 55, "stop_loss_pct": 0.04},
        {"bb_window": 20, "bb_std": 2.0, "rsi_entry": 30, "rsi_exit": 65, "stop_loss_pct": 0.05},
        {"bb_window": 14, "bb_std": 2.0, "rsi_entry": 30, "rsi_exit": 60, "stop_loss_pct": 0.03},
        {"bb_window": 20, "bb_std": 2.0, "rsi_entry": 25, "rsi_exit": 70, "stop_loss_pct": 0.02},
    ]

    all_results = []
    config = BacktestConfig(initial_capital=10_000.0, fee_rate=0.001, slippage_bps=2.0, mode="spot")

    for params in param_sets:
        signals = generate_signals(df, rsi_window=14, **params)
        bt = Backtest(config)
        results = bt.run(df, signals)
        results["params"] = params
        all_results.append(results)

    # Sort by Sharpe
    all_results.sort(key=lambda x: x.get("sharpe_ratio", 0), reverse=True)

    print("\n=== Parameter Sweep Results (sorted by Sharpe) ===")
    for i, r in enumerate(all_results):
        print(f"\n  #{i+1}: Sharpe={r['sharpe_ratio']:.2f} | Annual={r['annual_return']*100:.1f}% | "
              f"MaxDD={r['max_drawdown']*100:.1f}% | Trades={r.get('n_trades', 0)} | "
              f"WinRate={r.get('win_rate', 0)*100:.0f}%")
        print(f"       Params: {r['params']}")

    # Save sweep results
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
