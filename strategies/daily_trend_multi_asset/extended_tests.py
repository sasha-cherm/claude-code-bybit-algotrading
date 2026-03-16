"""
Extended tests for H-008 to address walk-forward failures.

Tests:
1. BTC-only out-of-sample
2. Sharpe-filtered asset selection (only Sharpe > 0 in training)
3. Proper position-level vol targeting (scale each asset's position by inverse vol)
4. Longer rolling walk-forward with top-3
5. Full-sample with proper vol targeting
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.metrics import summary as calc_summary, sharpe_ratio, returns_from_equity
from strategies.daily_trend_multi_asset.strategy import (
    resample_to_daily,
    generate_signals,
    backtest_single_asset,
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
    asset_daily = {}
    for sym in ALL_ASSETS:
        path = DATA_DIR / f"{sym}_USDT_1h.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        asset_daily[sym] = resample_to_daily(df)
    return asset_daily


def backtest_vol_targeted(
    daily_df: pd.DataFrame,
    ema_fast: int = 5,
    ema_slow: int = 40,
    vol_target_annual: float = 0.15,
    vol_lookback: int = 30,
    fee_rate: float = 0.001,
    slippage_bps: float = 2.0,
    initial_capital: float = 10_000.0,
) -> dict:
    """
    Backtest with proper position-level vol targeting.

    Each day, position size = (target_daily_vol / realized_daily_vol) * capital.
    This is computed at trade entry and adjusted at each signal change.
    """
    close = daily_df["close"].values
    signals = generate_signals(daily_df["close"], ema_fast, ema_slow).values
    n = len(close)
    slippage = slippage_bps / 10_000

    # Pre-compute daily returns and rolling vol
    daily_rets = pd.Series(close).pct_change().fillna(0).values
    target_daily_vol = vol_target_annual / np.sqrt(365)

    # Rolling realized vol
    realized_vol = np.full(n, np.nan)
    for i in range(vol_lookback, n):
        realized_vol[i] = np.std(daily_rets[i - vol_lookback:i])

    capital = initial_capital
    position = 0
    entry_price = 0.0
    size = 0.0
    equity = np.zeros(n)
    equity[0] = capital
    trades = []

    for i in range(1, n):
        price = close[i]
        target = int(signals[i])

        if position != 0:
            equity[i] = capital + position * size * (price - entry_price)
        else:
            equity[i] = capital

        if target != position:
            # Close
            if position != 0:
                exit_price = price * (1 - position * slippage)
                pnl = position * size * (exit_price - entry_price) - fee_rate * size * exit_price
                capital += pnl
                trades.append(pnl)
                position = 0
                size = 0.0

            # Open with vol-targeted sizing
            if target != 0:
                entry_price = price * (1 + target * slippage)

                # Vol-targeted position sizing
                rv = realized_vol[i] if not np.isnan(realized_vol[i]) else target_daily_vol
                if rv > 0:
                    vol_scale = min(target_daily_vol / rv, 2.0)  # cap at 2x
                else:
                    vol_scale = 1.0

                notional = capital * vol_scale
                size = notional / entry_price
                capital -= fee_rate * size * entry_price
                position = target

            equity[i] = capital + (position * size * (price - entry_price) if position != 0 else 0)

    # Close open position
    if position != 0:
        exit_price = close[-1] * (1 - position * slippage)
        pnl = position * size * (exit_price - entry_price) - fee_rate * size * exit_price
        capital += pnl
        trades.append(pnl)
        equity[-1] = capital

    eq_series = pd.Series(equity, index=daily_df.index)
    return {
        "equity_curve": eq_series,
        "trades": trades,
    }


def portfolio_vol_targeted(
    asset_daily: dict[str, pd.DataFrame],
    assets: list[str],
    portfolio_vol_target: float = 0.10,
    vol_lookback: int = 30,
) -> dict:
    """
    Multi-asset portfolio with per-asset vol targeting.

    Each asset gets capital/n_assets allocation, with vol targeting applied
    at the individual asset level. Portfolio vol target is divided by sqrt(n)
    assuming imperfect correlation.
    """
    n_assets = len(assets)
    if n_assets == 0:
        raise ValueError("No assets")

    # Per-asset vol target: portfolio_target / sqrt(n) * correlation_adjust
    # Conservative: assume correlation ~0.4, so diversification benefit = sqrt(1/n + (n-1)/n * 0.4)
    if n_assets > 1:
        avg_corr = 0.4
        div_factor = np.sqrt((1 + (n_assets - 1) * avg_corr) / n_assets)
    else:
        div_factor = 1.0

    per_asset_vol = portfolio_vol_target / div_factor
    alloc = INITIAL_CAPITAL / n_assets

    all_eq = {}
    all_trades = []

    for sym in assets:
        if sym not in asset_daily:
            continue
        res = backtest_vol_targeted(
            asset_daily[sym],
            EMA_FAST, EMA_SLOW,
            vol_target_annual=per_asset_vol,
            vol_lookback=vol_lookback,
            fee_rate=FEE_RATE,
            slippage_bps=SLIPPAGE_BPS,
            initial_capital=alloc,
        )
        all_eq[sym] = res["equity_curve"]
        all_trades.extend(res["trades"])

    eq_df = pd.DataFrame(all_eq).dropna()
    portfolio_eq = eq_df.sum(axis=1)

    trade_pnls = pd.Series(all_trades) if all_trades else pd.Series(dtype=float)
    metrics = calc_summary(portfolio_eq, trade_pnls, 365)
    metrics["assets"] = list(all_eq.keys())
    metrics["n_assets"] = len(all_eq)

    return {"equity_curve": portfolio_eq, "metrics": metrics}


def rank_assets(asset_daily, start=None, end=None):
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


def test_btc_only_oos(asset_daily):
    """Test 1: BTC-only out-of-sample."""
    print("\n" + "=" * 70)
    print("TEST A: BTC-ONLY OUT-OF-SAMPLE")
    print("=" * 70)

    btc = asset_daily["BTC"]
    n = len(btc)
    split_idx = int(n * 0.7)
    split_date = btc.index[split_idx]

    train = btc[btc.index < split_date]
    test = btc[btc.index >= split_date]

    print(f"  Train: {train.index[0].date()} to {train.index[-1].date()} ({len(train)} days)")
    print(f"  Test:  {test.index[0].date()} to {test.index[-1].date()} ({len(test)} days)")

    # In-sample
    res_is = backtest_single_asset(train, EMA_FAST, EMA_SLOW, FEE_RATE, SLIPPAGE_BPS)
    eq_is = res_is["equity_curve"]
    rets_is = eq_is.pct_change().dropna()
    from lib.metrics import annual_return, max_drawdown
    print(f"\n  In-sample:  Annual {annual_return(eq_is, 365):+.1%}, "
          f"DD {max_drawdown(eq_is):.1%}, Sharpe {sharpe_ratio(rets_is, periods_per_year=365):.2f}")

    # Out-of-sample raw
    res_oos = backtest_single_asset(test, EMA_FAST, EMA_SLOW, FEE_RATE, SLIPPAGE_BPS)
    eq_oos = res_oos["equity_curve"]
    rets_oos = eq_oos.pct_change().dropna()
    print(f"  OOS (raw):  Annual {annual_return(eq_oos, 365):+.1%}, "
          f"DD {max_drawdown(eq_oos):.1%}, Sharpe {sharpe_ratio(rets_oos, periods_per_year=365):.2f}, "
          f"Trades {len(res_oos['trades'])}")

    # OOS with vol targeting
    res_vt = backtest_vol_targeted(test, EMA_FAST, EMA_SLOW, vol_target_annual=0.15, initial_capital=INITIAL_CAPITAL)
    eq_vt = res_vt["equity_curve"]
    rets_vt = eq_vt.pct_change().dropna()
    print(f"  OOS (VT 15%): Annual {annual_return(eq_vt, 365):+.1%}, "
          f"DD {max_drawdown(eq_vt):.1%}, Sharpe {sharpe_ratio(rets_vt, periods_per_year=365):.2f}")

    res_vt2 = backtest_vol_targeted(test, EMA_FAST, EMA_SLOW, vol_target_annual=0.20, initial_capital=INITIAL_CAPITAL)
    eq_vt2 = res_vt2["equity_curve"]
    rets_vt2 = eq_vt2.pct_change().dropna()
    print(f"  OOS (VT 20%): Annual {annual_return(eq_vt2, 365):+.1%}, "
          f"DD {max_drawdown(eq_vt2):.1%}, Sharpe {sharpe_ratio(rets_vt2, periods_per_year=365):.2f}")

    return {
        "oos_raw_sharpe": round(sharpe_ratio(rets_oos, periods_per_year=365), 4),
        "oos_raw_annual": round(annual_return(eq_oos, 365), 4),
        "oos_raw_dd": round(max_drawdown(eq_oos), 4),
        "oos_vt15_annual": round(annual_return(eq_vt, 365), 4),
        "oos_vt15_dd": round(max_drawdown(eq_vt), 4),
    }


def test_sharpe_filtered_oos(asset_daily):
    """Test 2: Only include assets with Sharpe > 0 in training."""
    print("\n" + "=" * 70)
    print("TEST B: SHARPE-FILTERED PORTFOLIO OOS")
    print("=" * 70)

    all_starts = [df.index[0] for df in asset_daily.values()]
    all_ends = [df.index[-1] for df in asset_daily.values()]
    common_start = max(all_starts)
    common_end = min(all_ends)
    total_days = (common_end - common_start).days
    split_date = common_start + pd.Timedelta(days=int(total_days * 0.7))

    rankings = rank_assets(asset_daily, common_start, split_date)
    positive_sharpe = [sym for sym, sr in rankings if sr > 0]
    print(f"  Assets with positive in-sample Sharpe: {positive_sharpe}")
    print(f"  Rankings: {[(s, sr) for s, sr in rankings]}")

    for min_sharpe in [0.0, 0.3, 0.5]:
        selected = [sym for sym, sr in rankings if sr > min_sharpe]
        if not selected:
            continue

        test_data = {sym: df[df.index >= split_date] for sym, df in asset_daily.items() if sym in selected}
        test_data = {sym: df for sym, df in test_data.items() if len(df) > EMA_SLOW + 10}

        if not test_data:
            continue

        # Raw portfolio
        n_a = len(test_data)
        alloc = INITIAL_CAPITAL / n_a
        all_eq = {}
        all_trades = []
        for sym, df in test_data.items():
            res = backtest_single_asset(df, EMA_FAST, EMA_SLOW, FEE_RATE, SLIPPAGE_BPS, alloc)
            all_eq[sym] = res["equity_curve"]
            all_trades.extend(res["trades"])

        eq_df = pd.DataFrame(all_eq).dropna()
        port_eq = eq_df.sum(axis=1)
        from lib.metrics import annual_return, max_drawdown
        rets = port_eq.pct_change().dropna()
        sr = sharpe_ratio(rets, periods_per_year=365)
        ar = annual_return(port_eq, 365)
        dd = max_drawdown(port_eq)
        print(f"\n  Sharpe > {min_sharpe} ({list(test_data.keys())})")
        print(f"    Raw: Annual {ar:+.1%}, DD {dd:.1%}, Sharpe {sr:.2f}")

        # Vol-targeted portfolio
        vt_res = portfolio_vol_targeted(test_data, list(test_data.keys()),
                                        portfolio_vol_target=0.12)
        m = vt_res["metrics"]
        print(f"    VT 12%: Annual {m['annual_return']:+.1%}, DD {m['max_drawdown']:.1%}, "
              f"Sharpe {m['sharpe_ratio']:.2f}")


def test_rolling_top3(asset_daily):
    """Test 3: Rolling walk-forward with top-3 (less dilution)."""
    print("\n" + "=" * 70)
    print("TEST C: ROLLING WALK-FORWARD TOP-3")
    print("=" * 70)

    all_starts = [df.index[0] for df in asset_daily.values()]
    all_ends = [df.index[-1] for df in asset_daily.values()]
    common_start = max(all_starts)
    common_end = min(all_ends)

    # Rebalance every 3 months after 1 year of training
    first_rebal = common_start + pd.Timedelta(days=365)
    rebal_dates = pd.date_range(first_rebal, common_end, freq="3MS")
    print(f"  Rebalance dates: {[str(d.date()) for d in rebal_dates]}")

    oos_segments = []
    for i, rd in enumerate(rebal_dates):
        test_end = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else common_end
        if (test_end - rd).days < 20:
            continue

        rankings = rank_assets(asset_daily, common_start, rd)
        top3 = [sym for sym, sr in rankings[:3]]

        # Backtest on test segment with warmup
        segment_data = {}
        for sym in top3:
            if sym in asset_daily:
                warmup_start = rd - pd.Timedelta(days=EMA_SLOW + 10)
                seg = asset_daily[sym][(asset_daily[sym].index >= warmup_start) &
                                       (asset_daily[sym].index <= test_end)]
                if len(seg) > EMA_SLOW + 10:
                    segment_data[sym] = seg

        if not segment_data:
            continue

        n_a = len(segment_data)
        alloc = INITIAL_CAPITAL / n_a
        all_eq = {}
        for sym, df in segment_data.items():
            res = backtest_single_asset(df, EMA_FAST, EMA_SLOW, FEE_RATE, SLIPPAGE_BPS, alloc)
            all_eq[sym] = res["equity_curve"]

        eq_df = pd.DataFrame(all_eq).dropna()
        port_eq = eq_df.sum(axis=1)
        oos_eq = port_eq[port_eq.index >= rd]

        if len(oos_eq) > 0:
            seg_ret = (oos_eq.iloc[-1] / oos_eq.iloc[0]) - 1
            oos_segments.append(oos_eq)
            print(f"  {rd.date()} → {test_end.date()}: {list(segment_data.keys())} → {seg_ret:+.1%}")

    if not oos_segments:
        print("  No valid OOS segments")
        return {}

    # Chain
    chained = []
    cap = INITIAL_CAPITAL
    for seg in oos_segments:
        scale = cap / seg.iloc[0]
        scaled = seg * scale
        chained.append(scaled)
        cap = scaled.iloc[-1]

    chained_eq = pd.concat(chained)
    from lib.metrics import annual_return, max_drawdown
    rets = chained_eq.pct_change().dropna()
    sr = sharpe_ratio(rets, periods_per_year=365)
    ar = annual_return(chained_eq, 365)
    dd = max_drawdown(chained_eq)
    print(f"\n  Chained OOS: Annual {ar:+.1%}, DD {dd:.1%}, Sharpe {sr:.2f}")

    # Vol targeted version
    vol = rets.std() * np.sqrt(365)
    if vol > 0:
        scale = min(0.12 / vol, 2.0)
        vt_rets = rets * scale
        vt_eq = INITIAL_CAPITAL * (1 + vt_rets).cumprod()
        vt_metrics = calc_summary(vt_eq, pd.Series(dtype=float), 365)
        print(f"  VT 12%: Annual {vt_metrics['annual_return']:+.1%}, DD {vt_metrics['max_drawdown']:.1%}, "
              f"Sharpe {vt_metrics['sharpe_ratio']:.2f}")


def test_full_sample_vol_targeted(asset_daily):
    """Test 4: Full sample with proper vol targeting at various levels."""
    print("\n" + "=" * 70)
    print("TEST D: FULL-SAMPLE VOL-TARGETED PORTFOLIOS")
    print("=" * 70)

    rankings = rank_assets(asset_daily)
    print(f"  Full-sample rankings: {[(s, sr) for s, sr in rankings[:7]]}")

    for top_n in [1, 3, 5]:
        selected = [sym for sym, _ in rankings[:top_n]]
        print(f"\n  --- Top-{top_n}: {selected} ---")

        for vt in [0.08, 0.10, 0.12, 0.15, 0.20]:
            res = portfolio_vol_targeted(asset_daily, selected, portfolio_vol_target=vt)
            m = res["metrics"]
            print(f"    VT {vt*100:.0f}%: Annual {m['annual_return']:+.1%}, "
                  f"DD {m['max_drawdown']:.1%}, Sharpe {m['sharpe_ratio']:.2f}")


def test_btc_only_full_vol_targeted(asset_daily):
    """Test 5: BTC-only full sample with vol targeting — our baseline."""
    print("\n" + "=" * 70)
    print("TEST E: BTC-ONLY FULL SAMPLE VOL-TARGETED")
    print("=" * 70)

    btc = asset_daily["BTC"]
    from lib.metrics import annual_return, max_drawdown

    for vt in [0.08, 0.10, 0.12, 0.15, 0.20, 0.25]:
        res = backtest_vol_targeted(btc, EMA_FAST, EMA_SLOW,
                                    vol_target_annual=vt, initial_capital=INITIAL_CAPITAL)
        eq = res["equity_curve"]
        rets = eq.pct_change().dropna()
        sr = sharpe_ratio(rets, periods_per_year=365)
        ar = annual_return(eq, 365)
        dd = max_drawdown(eq)
        n_trades = len(res["trades"])
        print(f"  VT {vt*100:4.0f}%: Annual {ar:+.1%}, DD {dd:.1%}, "
              f"Sharpe {sr:.2f}, Trades {n_trades}")


def run_all():
    print("Loading data...")
    asset_daily = load_daily_data()
    print(f"Loaded {len(asset_daily)} assets\n")

    btc_results = test_btc_only_oos(asset_daily)
    test_sharpe_filtered_oos(asset_daily)
    test_rolling_top3(asset_daily)
    test_full_sample_vol_targeted(asset_daily)
    test_btc_only_full_vol_targeted(asset_daily)

    print("\n" + "=" * 70)
    print("SUMMARY & RECOMMENDATION")
    print("=" * 70)


if __name__ == "__main__":
    run_all()
