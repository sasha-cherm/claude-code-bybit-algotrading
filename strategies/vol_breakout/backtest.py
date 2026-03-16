"""
Backtest runner for H-004: Volatility Breakout (BTC Futures).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.backtest import Backtest, BacktestConfig
from strategies.vol_breakout.strategy import generate_signals

RESULTS_DIR = Path(__file__).resolve().parent


def parameter_sweep():
    """Run a parameter sweep across multiple configurations."""
    root = Path(__file__).resolve().parent.parent.parent
    df = __import__("pandas").read_parquet(root / "data/BTC_USDT_1h.parquet")

    print(f"Data: {len(df)} candles from {df.index[0]} to {df.index[-1]}")

    param_sets = [
        # Baseline
        {"channel_window": 24, "atr_window": 24, "breakout_mult": 0.5, "trail_atr_mult": 1.5, "max_hold": 48, "vol_filter": True},
        # Wider channel
        {"channel_window": 48, "atr_window": 24, "breakout_mult": 0.5, "trail_atr_mult": 1.5, "max_hold": 48, "vol_filter": True},
        # Tighter breakout threshold
        {"channel_window": 24, "atr_window": 24, "breakout_mult": 0.3, "trail_atr_mult": 1.5, "max_hold": 48, "vol_filter": True},
        # Wider breakout threshold
        {"channel_window": 24, "atr_window": 24, "breakout_mult": 1.0, "trail_atr_mult": 1.5, "max_hold": 48, "vol_filter": True},
        # Tighter trailing stop
        {"channel_window": 24, "atr_window": 24, "breakout_mult": 0.5, "trail_atr_mult": 1.0, "max_hold": 48, "vol_filter": True},
        # Wider trailing stop
        {"channel_window": 24, "atr_window": 24, "breakout_mult": 0.5, "trail_atr_mult": 2.0, "max_hold": 48, "vol_filter": True},
        # Longer hold
        {"channel_window": 24, "atr_window": 24, "breakout_mult": 0.5, "trail_atr_mult": 1.5, "max_hold": 96, "vol_filter": True},
        # No vol filter
        {"channel_window": 24, "atr_window": 24, "breakout_mult": 0.5, "trail_atr_mult": 1.5, "max_hold": 48, "vol_filter": False},
        # Wider channel + wider breakout
        {"channel_window": 48, "atr_window": 24, "breakout_mult": 1.0, "trail_atr_mult": 2.0, "max_hold": 72, "vol_filter": True},
        # Short channel, tight stop
        {"channel_window": 12, "atr_window": 24, "breakout_mult": 0.3, "trail_atr_mult": 1.0, "max_hold": 24, "vol_filter": True},
    ]

    all_results = []
    config = BacktestConfig(initial_capital=10_000.0, fee_rate=0.001, slippage_bps=2.0, mode="futures")

    for i, params in enumerate(param_sets):
        signals = generate_signals(df, **params)
        bt = Backtest(config)
        results = bt.run(df, signals)
        results["params"] = params
        all_results.append(results)
        n_long = int((signals == 1).sum())
        n_short = int((signals == -1).sum())
        print(f"  Set #{i+1}: signals long={n_long} short={n_short} trades={results.get('n_trades', 0)}")

    # Sort by Sharpe
    all_results.sort(key=lambda x: x.get("sharpe_ratio", 0), reverse=True)

    print("\n=== H-004: Volatility Breakout — Parameter Sweep (sorted by Sharpe) ===")
    for i, r in enumerate(all_results):
        print(f"\n  #{i+1}: Sharpe={r['sharpe_ratio']:.2f} | Annual={r['annual_return']*100:.1f}% | "
              f"MaxDD={r['max_drawdown']*100:.1f}% | Trades={r.get('n_trades', 0)} | "
              f"WinRate={r.get('win_rate', 0)*100:.0f}%")
        p = r['params']
        print(f"       ch={p['channel_window']} brk={p['breakout_mult']} trail={p['trail_atr_mult']} "
              f"hold={p['max_hold']} vf={p['vol_filter']}")

    # Save results
    with open(RESULTS_DIR / "sweep_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    # Save best result separately
    best = all_results[0]
    with open(RESULTS_DIR / "results.json", "w") as f:
        json.dump(best, f, indent=2, default=str)

    return all_results


if __name__ == "__main__":
    parameter_sweep()
