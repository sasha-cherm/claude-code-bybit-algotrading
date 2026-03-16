"""
Backtest runner for H-006: Adaptive Mean Reversion (BTC Futures, Long/Short).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.backtest import Backtest, BacktestConfig
from strategies.adaptive_mean_reversion.strategy import generate_signals

RESULTS_DIR = Path(__file__).resolve().parent


def parameter_sweep():
    """Run a parameter sweep across multiple configurations."""
    root = Path(__file__).resolve().parent.parent.parent
    df = __import__("pandas").read_parquet(root / "data/BTC_USDT_1h.parquet")

    print(f"Data: {len(df)} candles from {df.index[0]} to {df.index[-1]}")

    param_sets = [
        # === With reversal confirmation (new approach) ===
        # Baseline with reversal
        {"bb_window": 20, "bb_std": 2.0, "rsi_long_entry": 35, "rsi_short_entry": 65, "regime_threshold": 1.0, "stop_atr_mult": 2.0, "require_reversal": True},
        # Wider stop with reversal
        {"bb_window": 20, "bb_std": 2.0, "rsi_long_entry": 35, "rsi_short_entry": 65, "regime_threshold": 1.0, "stop_atr_mult": 3.0, "require_reversal": True},
        # Very wide stop with reversal
        {"bb_window": 20, "bb_std": 2.0, "rsi_long_entry": 35, "rsi_short_entry": 65, "regime_threshold": 1.0, "stop_atr_mult": 4.0, "require_reversal": True},
        # Wider BB with reversal
        {"bb_window": 20, "bb_std": 2.5, "rsi_long_entry": 35, "rsi_short_entry": 65, "regime_threshold": 1.0, "stop_atr_mult": 3.0, "require_reversal": True},
        # Tight RSI with reversal
        {"bb_window": 20, "bb_std": 2.0, "rsi_long_entry": 30, "rsi_short_entry": 70, "regime_threshold": 1.0, "stop_atr_mult": 3.0, "require_reversal": True},
        # Strict regime with reversal
        {"bb_window": 20, "bb_std": 2.0, "rsi_long_entry": 35, "rsi_short_entry": 65, "regime_threshold": 0.8, "stop_atr_mult": 3.0, "require_reversal": True},
        # Loose regime + reversal
        {"bb_window": 20, "bb_std": 2.0, "rsi_long_entry": 35, "rsi_short_entry": 65, "regime_threshold": 1.2, "stop_atr_mult": 3.0, "require_reversal": True},
        # Longer BB + reversal
        {"bb_window": 30, "bb_std": 2.0, "rsi_long_entry": 35, "rsi_short_entry": 65, "regime_threshold": 1.0, "stop_atr_mult": 3.0, "require_reversal": True},
        # === Without reversal (original, as comparison) ===
        # Original baseline
        {"bb_window": 20, "bb_std": 2.0, "rsi_long_entry": 35, "rsi_short_entry": 65, "regime_threshold": 1.0, "stop_atr_mult": 2.0, "require_reversal": False},
        # Original wider stop
        {"bb_window": 20, "bb_std": 2.0, "rsi_long_entry": 35, "rsi_short_entry": 65, "regime_threshold": 1.0, "stop_atr_mult": 3.0, "require_reversal": False},
        # Original wider BB
        {"bb_window": 20, "bb_std": 2.5, "rsi_long_entry": 35, "rsi_short_entry": 65, "regime_threshold": 1.0, "stop_atr_mult": 3.0, "require_reversal": False},
        # Conservative: wide BB + strict regime + tight RSI + no reversal
        {"bb_window": 30, "bb_std": 2.5, "rsi_long_entry": 25, "rsi_short_entry": 75, "regime_threshold": 0.8, "stop_atr_mult": 3.0, "require_reversal": False},
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

    print("\n=== H-006: Adaptive Mean Reversion — Parameter Sweep (sorted by Sharpe) ===")
    for i, r in enumerate(all_results):
        print(f"\n  #{i+1}: Sharpe={r['sharpe_ratio']:.2f} | Annual={r['annual_return']*100:.1f}% | "
              f"MaxDD={r['max_drawdown']*100:.1f}% | Trades={r.get('n_trades', 0)} | "
              f"WinRate={r.get('win_rate', 0)*100:.0f}%")
        p = r['params']
        print(f"       bb={p['bb_window']}/{p['bb_std']} rsi={p['rsi_long_entry']}/{p['rsi_short_entry']} "
              f"regime={p['regime_threshold']} stop={p['stop_atr_mult']} rev={p.get('require_reversal', False)}")

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
