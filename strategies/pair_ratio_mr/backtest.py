"""
Backtest runner for H-007: BTC/ETH Ratio Mean Reversion (Pairs Trading).
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from strategies.pair_ratio_mr.strategy import compute_spread_and_signals, backtest_pairs

RESULTS_DIR = Path(__file__).resolve().parent


def parameter_sweep():
    """Run a parameter sweep across multiple configurations."""
    root = Path(__file__).resolve().parent.parent.parent
    btc = pd.read_parquet(root / "data/BTC_USDT_1h.parquet")
    eth = pd.read_parquet(root / "data/ETH_USDT_1h.parquet")

    # Align on common index
    common = btc.index.intersection(eth.index)
    btc = btc.loc[common]
    eth = eth.loc[common]
    print(f"Data: {len(common)} candles from {common[0]} to {common[-1]}")

    param_sets = [
        # Baseline
        {"lookback": 168, "entry_z": 2.0, "exit_z": 0.5, "stop_z": 4.0},
        # Faster lookback (3 days)
        {"lookback": 72, "entry_z": 2.0, "exit_z": 0.5, "stop_z": 4.0},
        # Slower lookback (14 days)
        {"lookback": 336, "entry_z": 2.0, "exit_z": 0.5, "stop_z": 4.0},
        # Lower entry threshold (more trades)
        {"lookback": 168, "entry_z": 1.5, "exit_z": 0.3, "stop_z": 3.5},
        # Higher entry threshold (fewer, higher-quality trades)
        {"lookback": 168, "entry_z": 2.5, "exit_z": 0.5, "stop_z": 5.0},
        # Exit closer to zero
        {"lookback": 168, "entry_z": 2.0, "exit_z": 0.0, "stop_z": 4.0},
        # Wider exit
        {"lookback": 168, "entry_z": 2.0, "exit_z": 1.0, "stop_z": 4.0},
        # Tight stop
        {"lookback": 168, "entry_z": 2.0, "exit_z": 0.5, "stop_z": 3.0},
        # No stop
        {"lookback": 168, "entry_z": 2.0, "exit_z": 0.5, "stop_z": 100.0},
        # Fast lookback + lower entry
        {"lookback": 72, "entry_z": 1.5, "exit_z": 0.3, "stop_z": 3.5},
        # Fast lookback + higher entry
        {"lookback": 72, "entry_z": 2.5, "exit_z": 0.5, "stop_z": 4.0},
        # Slow lookback + lower entry
        {"lookback": 336, "entry_z": 1.5, "exit_z": 0.3, "stop_z": 4.0},
    ]

    all_results = []

    for i, params in enumerate(param_sets):
        z_score, signals = compute_spread_and_signals(btc, eth, **params)
        result = backtest_pairs(btc, eth, signals)
        result["params"] = params
        all_results.append(result)
        n_long = int((signals == 1).sum())
        n_short = int((signals == -1).sum())
        print(f"  Set #{i+1}: long_ratio={n_long} short_ratio={n_short} trades={result.get('n_trades', 0)}")

    # Sort by Sharpe
    all_results.sort(key=lambda x: x.get("sharpe_ratio", 0), reverse=True)

    print("\n=== H-007: BTC/ETH Ratio Mean Reversion — Parameter Sweep (sorted by Sharpe) ===")
    for i, r in enumerate(all_results):
        print(f"\n  #{i+1}: Sharpe={r['sharpe_ratio']:.2f} | Annual={r['annual_return']*100:.1f}% | "
              f"MaxDD={r['max_drawdown']*100:.1f}% | Trades={r.get('n_trades', 0)} | "
              f"WinRate={r.get('win_rate', 0)*100:.0f}%")
        p = r['params']
        print(f"       lb={p['lookback']} entry_z={p['entry_z']} exit_z={p['exit_z']} stop_z={p['stop_z']}")
        print(f"       Final capital: ${r['final_capital']:,.2f}")

    # Save results
    with open(RESULTS_DIR / "sweep_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    # Save best result
    best = all_results[0]
    with open(RESULTS_DIR / "results.json", "w") as f:
        json.dump(best, f, indent=2, default=str)

    return all_results


if __name__ == "__main__":
    parameter_sweep()
