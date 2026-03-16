"""
H-008 Walk-Forward Validation

Tests:
1. Fixed split: 70% train / 30% test — select top-N assets on train, evaluate on test
2. Rolling walk-forward: expanding window, re-select assets every 6 months
3. Vol-targeted position sizing to control drawdown
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.metrics import summary as calc_summary, returns_from_equity, sharpe_ratio
from strategies.daily_trend_multi_asset.strategy import (
    resample_to_daily,
    generate_signals,
    backtest_single_asset,
    backtest_portfolio,
    apply_vol_targeting,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent

ALL_ASSETS = [
    "BTC", "ETH", "SOL", "SUI", "XRP", "DOGE",
    "AVAX", "LINK", "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM",
]

EMA_FAST = 5
EMA_SLOW = 40
FEE_RATE = 0.001
SLIPPAGE_BPS = 2.0
INITIAL_CAPITAL = 10_000.0


def load_daily_data() -> dict[str, pd.DataFrame]:
    """Load all assets, resample 1h to daily."""
    asset_daily = {}
    for sym in ALL_ASSETS:
        path = DATA_DIR / f"{sym}_USDT_1h.parquet"
        if not path.exists():
            print(f"  Skipping {sym} — no data file")
            continue
        df = pd.read_parquet(path)
        daily = resample_to_daily(df)
        asset_daily[sym] = daily
        print(f"  {sym}: {len(daily)} daily bars, {daily.index[0].date()} to {daily.index[-1].date()}")
    return asset_daily


def rank_assets_by_sharpe(
    asset_daily: dict[str, pd.DataFrame],
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> list[tuple[str, float]]:
    """
    Rank assets by in-sample Sharpe ratio of EMA crossover strategy.

    Returns list of (symbol, sharpe) sorted descending.
    """
    results = []
    for sym, df in asset_daily.items():
        subset = df
        if start is not None:
            subset = subset[subset.index >= start]
        if end is not None:
            subset = subset[subset.index <= end]
        if len(subset) < EMA_SLOW + 20:
            continue

        res = backtest_single_asset(subset, EMA_FAST, EMA_SLOW, FEE_RATE, SLIPPAGE_BPS)
        eq = res["equity_curve"]
        rets = eq.pct_change().dropna()
        sr = sharpe_ratio(rets, periods_per_year=365)
        results.append((sym, round(sr, 4)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def test_fixed_split(asset_daily: dict[str, pd.DataFrame], train_frac: float = 0.7):
    """
    Test 1: Fixed train/test split.

    Select top-N assets on training period, evaluate on test period.
    """
    print("\n" + "=" * 70)
    print("TEST 1: FIXED SPLIT WALK-FORWARD VALIDATION")
    print("=" * 70)

    # Find common date range
    all_starts = [df.index[0] for df in asset_daily.values()]
    all_ends = [df.index[-1] for df in asset_daily.values()]
    common_start = max(all_starts)
    common_end = min(all_ends)
    total_days = (common_end - common_start).days

    split_date = common_start + pd.Timedelta(days=int(total_days * train_frac))
    print(f"\n  Date range: {common_start.date()} to {common_end.date()} ({total_days} days)")
    print(f"  Train: {common_start.date()} to {split_date.date()}")
    print(f"  Test:  {split_date.date()} to {common_end.date()}")

    # Rank on training data
    print("\n  --- In-Sample Asset Ranking (Train Period) ---")
    rankings = rank_assets_by_sharpe(asset_daily, common_start, split_date)
    for sym, sr in rankings:
        print(f"    {sym:6s} Sharpe: {sr:+.4f}")

    results = {}
    for top_n in [3, 5, 7, 10, 14]:
        selected = [sym for sym, sr in rankings[:top_n] if sr > -0.5]
        if len(selected) < min(top_n, 3):
            continue

        # Backtest on TEST period only
        test_data = {sym: df[df.index >= split_date] for sym, df in asset_daily.items() if sym in selected}
        # Filter out assets with insufficient test data
        test_data = {sym: df for sym, df in test_data.items() if len(df) > EMA_SLOW + 10}

        if not test_data:
            continue

        # Equal weight, no vol targeting
        port = backtest_portfolio(test_data, list(test_data.keys()), EMA_FAST, EMA_SLOW,
                                  FEE_RATE, SLIPPAGE_BPS, INITIAL_CAPITAL)
        m = port["metrics"]

        # With vol targeting (10% annual vol)
        port_vt = backtest_portfolio(test_data, list(test_data.keys()), EMA_FAST, EMA_SLOW,
                                     FEE_RATE, SLIPPAGE_BPS, INITIAL_CAPITAL,
                                     vol_target=0.10, vol_lookback=60)
        m_vt = port_vt["metrics"]

        results[f"top_{top_n}"] = {
            "assets": list(test_data.keys()),
            "raw": {k: m[k] for k in ["annual_return", "max_drawdown", "sharpe_ratio", "sortino_ratio",
                                        "n_trades", "win_rate", "profit_factor"]},
            "vol_targeted_10pct": {k: m_vt[k] for k in ["annual_return", "max_drawdown", "sharpe_ratio",
                                                          "sortino_ratio"]},
        }

        print(f"\n  --- Top-{top_n} OOS Results ({', '.join(test_data.keys())}) ---")
        print(f"    Raw:         Annual {m['annual_return']:+.1%}, DD {m['max_drawdown']:.1%}, "
              f"Sharpe {m['sharpe_ratio']:.2f}, Trades {m.get('n_trades', 0)}")
        print(f"    Vol-tgt 10%: Annual {m_vt['annual_return']:+.1%}, DD {m_vt['max_drawdown']:.1%}, "
              f"Sharpe {m_vt['sharpe_ratio']:.2f}")

    return results


def test_rolling_walk_forward(
    asset_daily: dict[str, pd.DataFrame],
    rebalance_months: int = 6,
    min_train_days: int = 365,
    top_n: int = 5,
):
    """
    Test 2: Rolling walk-forward with expanding training window.

    Every rebalance_months, re-rank assets using all available history,
    then trade the selected portfolio for the next period.
    """
    print("\n" + "=" * 70)
    print(f"TEST 2: ROLLING WALK-FORWARD (rebal every {rebalance_months}mo, top-{top_n})")
    print("=" * 70)

    all_starts = [df.index[0] for df in asset_daily.values()]
    all_ends = [df.index[-1] for df in asset_daily.values()]
    common_start = max(all_starts)
    common_end = min(all_ends)

    # First rebalance after min_train_days
    first_rebal = common_start + pd.Timedelta(days=min_train_days)
    rebal_dates = pd.date_range(first_rebal, common_end, freq=f"{rebalance_months}MS")
    if len(rebal_dates) == 0:
        print("  Not enough data for rolling walk-forward")
        return {}

    print(f"  Rebalance dates: {[str(d.date()) for d in rebal_dates]}")

    # Collect OOS equity segments
    oos_segments = []
    segment_info = []

    for i, rebal_date in enumerate(rebal_dates):
        train_end = rebal_date
        test_start = rebal_date
        test_end = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else common_end

        if (test_end - test_start).days < 30:
            continue

        # Rank on expanding training window
        rankings = rank_assets_by_sharpe(asset_daily, common_start, train_end)
        selected = [sym for sym, sr in rankings[:top_n]]

        # Backtest on test segment
        test_data = {}
        for sym in selected:
            if sym in asset_daily:
                seg = asset_daily[sym][(asset_daily[sym].index >= test_start) &
                                       (asset_daily[sym].index <= test_end)]
                if len(seg) > EMA_SLOW + 10:
                    test_data[sym] = seg

        # For short segments, we need enough warmup — use data from before test_start for EMA
        # but only count equity from test_start onwards
        test_data_with_warmup = {}
        for sym in selected:
            if sym in asset_daily:
                warmup_start = test_start - pd.Timedelta(days=EMA_SLOW + 10)
                seg = asset_daily[sym][(asset_daily[sym].index >= warmup_start) &
                                       (asset_daily[sym].index <= test_end)]
                if len(seg) > EMA_SLOW + 10:
                    test_data_with_warmup[sym] = seg

        if not test_data_with_warmup:
            continue

        port = backtest_portfolio(test_data_with_warmup, list(test_data_with_warmup.keys()),
                                  EMA_FAST, EMA_SLOW, FEE_RATE, SLIPPAGE_BPS, INITIAL_CAPITAL)

        # Trim equity to OOS period only
        eq = port["equity_curve"]
        oos_eq = eq[eq.index >= test_start]

        if len(oos_eq) > 0:
            oos_segments.append(oos_eq)
            seg_return = (oos_eq.iloc[-1] / oos_eq.iloc[0]) - 1
            info = {
                "period": f"{test_start.date()} to {test_end.date()}",
                "assets": list(test_data_with_warmup.keys()),
                "segment_return": round(float(seg_return), 4),
            }
            segment_info.append(info)
            print(f"\n  Segment {test_start.date()} → {test_end.date()}: "
                  f"assets={list(test_data_with_warmup.keys())}, return={seg_return:+.1%}")

    if not oos_segments:
        print("  No valid OOS segments")
        return {}

    # Chain OOS segments into continuous equity curve
    chained_equity = chain_equity_segments(oos_segments, INITIAL_CAPITAL)
    rets = chained_equity.pct_change().dropna()
    metrics = calc_summary(chained_equity, pd.Series(dtype=float), 365)

    print(f"\n  --- Chained OOS Results ---")
    print(f"    Annual Return: {metrics['annual_return']:+.1%}")
    print(f"    Max Drawdown:  {metrics['max_drawdown']:.1%}")
    print(f"    Sharpe Ratio:  {metrics['sharpe_ratio']:.2f}")
    print(f"    Sortino Ratio: {metrics['sortino_ratio']:.2f}")

    # Also with vol targeting
    scale_factor = 0.10 / (rets.std() * np.sqrt(365)) if rets.std() > 0 else 1.0
    scale_factor = min(scale_factor, 2.0)
    scaled_rets = rets * scale_factor
    scaled_eq = INITIAL_CAPITAL * (1 + scaled_rets).cumprod()
    vt_metrics = calc_summary(scaled_eq, pd.Series(dtype=float), 365)

    print(f"\n  --- Vol-Targeted (10% annual) OOS ---")
    print(f"    Annual Return: {vt_metrics['annual_return']:+.1%}")
    print(f"    Max Drawdown:  {vt_metrics['max_drawdown']:.1%}")
    print(f"    Sharpe Ratio:  {vt_metrics['sharpe_ratio']:.2f}")

    return {
        "segments": segment_info,
        "chained_oos": {k: metrics[k] for k in ["annual_return", "max_drawdown", "sharpe_ratio", "sortino_ratio"]},
        "vol_targeted_10pct": {k: vt_metrics[k] for k in ["annual_return", "max_drawdown", "sharpe_ratio"]},
    }


def test_param_robustness(asset_daily: dict[str, pd.DataFrame]):
    """
    Test 3: Parameter sensitivity — test nearby EMA params to check robustness.
    """
    print("\n" + "=" * 70)
    print("TEST 3: PARAMETER ROBUSTNESS (full-sample, top-5)")
    print("=" * 70)

    # First rank with default params to get top-5
    rankings = rank_assets_by_sharpe(asset_daily)
    top5 = [sym for sym, _ in rankings[:5]]
    print(f"  Top-5 assets (default params): {top5}")

    param_sets = [
        (3, 30), (3, 40), (3, 50),
        (5, 30), (5, 40), (5, 50), (5, 60),
        (7, 30), (7, 40), (7, 50), (7, 60),
        (10, 30), (10, 40), (10, 50), (10, 60),
    ]

    results = []
    for fast, slow in param_sets:
        port = backtest_portfolio(asset_daily, top5, fast, slow,
                                  FEE_RATE, SLIPPAGE_BPS, INITIAL_CAPITAL)
        m = port["metrics"]
        results.append({
            "ema_fast": fast,
            "ema_slow": slow,
            "annual_return": m["annual_return"],
            "max_drawdown": m["max_drawdown"],
            "sharpe": m["sharpe_ratio"],
            "n_trades": m.get("n_trades", 0),
        })
        print(f"  EMA({fast:2d}/{slow:2d}): Annual {m['annual_return']:+.1%}, "
              f"DD {m['max_drawdown']:.1%}, Sharpe {m['sharpe_ratio']:.2f}, "
              f"Trades {m.get('n_trades', 0)}")

    # Summary
    sharpes = [r["sharpe"] for r in results]
    positive = sum(1 for s in sharpes if s > 0)
    print(f"\n  Positive Sharpe: {positive}/{len(results)} param sets")
    print(f"  Sharpe range: {min(sharpes):.2f} to {max(sharpes):.2f}")
    print(f"  Mean Sharpe: {np.mean(sharpes):.2f}, Median: {np.median(sharpes):.2f}")

    return results


def chain_equity_segments(segments: list[pd.Series], initial_capital: float) -> pd.Series:
    """Chain multiple equity curve segments into one continuous curve."""
    if not segments:
        return pd.Series(dtype=float)

    chained_parts = []
    current_capital = initial_capital

    for seg in segments:
        if len(seg) == 0:
            continue
        # Scale segment so it starts at current_capital
        scale = current_capital / seg.iloc[0]
        scaled = seg * scale
        chained_parts.append(scaled)
        current_capital = scaled.iloc[-1]

    if not chained_parts:
        return pd.Series(dtype=float)

    return pd.concat(chained_parts)


def run_all():
    """Run all walk-forward validation tests."""
    print("=" * 70)
    print("H-008: MULTI-ASSET DAILY TREND FOLLOWING — WALK-FORWARD VALIDATION")
    print(f"Params: EMA({EMA_FAST}/{EMA_SLOW}), Fee {FEE_RATE*100:.1f}%, Slippage {SLIPPAGE_BPS} bps")
    print("=" * 70)

    print("\nLoading data...")
    asset_daily = load_daily_data()
    print(f"Loaded {len(asset_daily)} assets")

    # Test 1: Fixed split
    fixed_results = test_fixed_split(asset_daily, train_frac=0.7)

    # Test 2: Rolling walk-forward
    rolling_results = test_rolling_walk_forward(asset_daily, rebalance_months=6, top_n=5)

    # Test 3: Parameter robustness
    param_results = test_param_robustness(asset_daily)

    # Save all results
    all_results = {
        "params": {"ema_fast": EMA_FAST, "ema_slow": EMA_SLOW, "fee_rate": FEE_RATE},
        "fixed_split": fixed_results,
        "rolling_walk_forward": rolling_results,
        "param_robustness": param_results,
    }

    results_path = RESULTS_DIR / "walkforward_results.json"
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {results_path}")

    return all_results


if __name__ == "__main__":
    run_all()
