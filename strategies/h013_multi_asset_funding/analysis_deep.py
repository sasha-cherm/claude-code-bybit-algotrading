"""
H-013 Deep Analysis:
1. Period-split comparison (full vs recent 180d vs recent 90d)
2. Walk-forward validation of multi-asset funding arb
3. Optimal portfolio reallocation when funding is low
4. Combined portfolio: H-009 + H-013 + H-012 (replacing H-011)
"""

import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
DATA_DIR = ROOT / "data"

ASSETS_NAMES = ["BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX", "LINK",
                "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM"]


def load_all_funding() -> pd.DataFrame:
    """Load all cached funding rate data into a combined DataFrame."""
    rates = {}
    for name in ASSETS_NAMES:
        cache = DATA_DIR / f"{name}_USDT_USDT_funding.parquet"
        if cache.exists():
            df = pd.read_parquet(cache)
            rates[name] = df["funding_rate"]
    combined = pd.DataFrame(rates).dropna(how="all").fillna(0).sort_index()
    return combined


def backtest_all_positive(
    combined: pd.DataFrame,
    leverage: float = 5.0,
    fee_rate: float = 0.001,
    initial_capital: float = 10_000.0,
    filter_lookback: int = 27,
    rebal_every: int = 1,  # rebalance every N settlements (1 = every 8h)
    start_date: str | None = None,
    end_date: str | None = None,
    label: str = "",
) -> dict:
    """
    Backtest all-positive multi-asset funding arb.
    At each settlement, collect funding from all assets whose rolling avg > 0.
    Capital equally distributed across active positions.
    """
    df = combined.copy()
    if start_date:
        df = df[df.index >= start_date]
    if end_date:
        df = df[df.index <= end_date]

    rolling = df.rolling(filter_lookback).mean().dropna()
    df = df.loc[rolling.index]

    capital = initial_capital
    equity_history = []
    total_fees = 0
    prev_assets = set()
    step = 0

    for ts in rolling.index:
        row_rolling = rolling.loc[ts]
        row_actual = df.loc[ts]

        # Determine active assets (positive rolling avg)
        active_assets = set(row_rolling[row_rolling > 0].index)

        # Only rebalance on schedule
        if step % rebal_every == 0:
            current_assets = active_assets
        else:
            current_assets = prev_assets & active_assets  # keep existing if still positive

        if not current_assets:
            # No positions — just wait
            equity_history.append({"ts": ts, "equity": capital, "n": 0})
            prev_assets = set()
            step += 1
            continue

        # Turnover fees
        if step % rebal_every == 0:
            entered = current_assets - prev_assets
            exited = prev_assets - current_assets
            turnover = len(entered) + len(exited)
            if turnover > 0:
                per_asset_notional = capital / len(current_assets) * leverage
                fee = fee_rate * per_asset_notional * turnover
                capital -= fee
                total_fees += fee

        # Collect funding from each active asset
        cap_per = capital / len(current_assets)
        for asset in current_assets:
            rate = row_actual[asset]
            pnl = cap_per * leverage * rate
            capital += pnl

        equity_history.append({"ts": ts, "equity": capital, "n": len(current_assets)})
        prev_assets = current_assets
        step += 1

    eq_df = pd.DataFrame(equity_history).set_index("ts")
    days = (eq_df.index[-1] - eq_df.index[0]).days or 1
    total_return = capital / initial_capital - 1
    ann_return = (1 + total_return) ** (365 / days) - 1

    eq_series = eq_df["equity"]
    max_dd = ((eq_series - eq_series.cummax()) / eq_series.cummax()).min()

    eq_daily = eq_series.resample("1D").last().dropna()
    daily_returns = eq_daily.pct_change().dropna()
    sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(365) if daily_returns.std() > 0 else 0

    in_market = (eq_df["n"] > 0).mean()
    avg_n = eq_df["n"].mean()

    result = {
        "label": label,
        "days": days,
        "total_return": total_return,
        "ann_return": ann_return,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "in_market": in_market,
        "avg_positions": avg_n,
        "fees": total_fees,
        "final_equity": capital,
    }

    print(f"  {label}: Ann {ann_return:+.1%}, DD {max_dd:.2%}, "
          f"Sharpe {sharpe:.2f}, InMkt {in_market:.1%}, Avg N {avg_n:.1f}, "
          f"Fees ${total_fees:,.0f}")

    return result


def backtest_btc_only(
    combined: pd.DataFrame,
    leverage: float = 5.0,
    fee_rate: float = 0.001,
    initial_capital: float = 10_000.0,
    filter_lookback: int = 27,
    start_date: str | None = None,
    end_date: str | None = None,
    label: str = "",
) -> dict:
    """BTC-only funding arb baseline."""
    df = combined[["BTC"]].copy()
    if start_date:
        df = df[df.index >= start_date]
    if end_date:
        df = df[df.index <= end_date]

    rolling = df["BTC"].rolling(filter_lookback).mean().dropna()
    df = df.loc[rolling.index]

    capital = initial_capital
    equity_history = []
    in_pos = False
    total_fees = 0

    for ts in rolling.index:
        rate = df.loc[ts, "BTC"]
        ravg = rolling.loc[ts]

        if ravg > 0:
            notional = capital * leverage
            pnl = notional * rate
            capital += pnl
            if not in_pos:
                fee = fee_rate * notional
                capital -= fee
                total_fees += fee
                in_pos = True
        else:
            if in_pos:
                fee = fee_rate * capital * leverage
                capital -= fee
                total_fees += fee
                in_pos = False

        equity_history.append({"ts": ts, "equity": capital, "in_pos": in_pos})

    eq_df = pd.DataFrame(equity_history).set_index("ts")
    days = (eq_df.index[-1] - eq_df.index[0]).days or 1
    total_return = capital / initial_capital - 1
    ann_return = (1 + total_return) ** (365 / days) - 1

    eq_series = eq_df["equity"]
    max_dd = ((eq_series - eq_series.cummax()) / eq_series.cummax()).min()

    eq_daily = eq_series.resample("1D").last().dropna()
    daily_returns = eq_daily.pct_change().dropna()
    sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(365) if daily_returns.std() > 0 else 0

    in_market = eq_df["in_pos"].mean()

    result = {
        "label": label,
        "days": days,
        "total_return": total_return,
        "ann_return": ann_return,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "in_market": in_market,
        "fees": total_fees,
        "final_equity": capital,
    }

    print(f"  {label}: Ann {ann_return:+.1%}, DD {max_dd:.2%}, "
          f"Sharpe {sharpe:.2f}, InMkt {in_market:.1%}, Fees ${total_fees:,.0f}")

    return result


def walk_forward_validation(combined: pd.DataFrame, n_folds: int = 4):
    """Rolling walk-forward: train on 360 settlements (~120d), test on 180 (~60d)."""
    print("\n=== Walk-Forward Validation ===")
    train_size = 360  # ~120 days
    test_size = 180   # ~60 days
    step = test_size

    rolling = combined.rolling(27).mean().dropna()
    timestamps = rolling.index

    oos_results_multi = []
    oos_results_btc = []
    fold = 0

    start = 0
    while start + train_size + test_size <= len(timestamps):
        train_end = timestamps[start + train_size - 1]
        test_start = timestamps[start + train_size]
        test_end_idx = min(start + train_size + test_size - 1, len(timestamps) - 1)
        test_end = timestamps[test_end_idx]

        print(f"\n  Fold {fold + 1}: Train up to {train_end.date()}, Test {test_start.date()} to {test_end.date()}")

        r_multi = backtest_all_positive(
            combined, start_date=str(test_start), end_date=str(test_end),
            label=f"  Multi F{fold+1} OOS"
        )
        r_btc = backtest_btc_only(
            combined, start_date=str(test_start), end_date=str(test_end),
            label=f"  BTC   F{fold+1} OOS"
        )

        oos_results_multi.append(r_multi)
        oos_results_btc.append(r_btc)

        start += step
        fold += 1

    # Aggregate OOS results
    print("\n  --- Walk-Forward Summary ---")
    multi_sharpes = [r["sharpe"] for r in oos_results_multi]
    btc_sharpes = [r["sharpe"] for r in oos_results_btc]
    multi_returns = [r["ann_return"] for r in oos_results_multi]
    btc_returns = [r["ann_return"] for r in oos_results_btc]

    print(f"  Multi-asset: avg Sharpe {np.mean(multi_sharpes):.2f} "
          f"(range {min(multi_sharpes):.2f} to {max(multi_sharpes):.2f}), "
          f"avg ann {np.mean(multi_returns):+.1%}")
    print(f"  BTC-only:    avg Sharpe {np.mean(btc_sharpes):.2f} "
          f"(range {min(btc_sharpes):.2f} to {max(btc_sharpes):.2f}), "
          f"avg ann {np.mean(btc_returns):+.1%}")

    return oos_results_multi, oos_results_btc


def portfolio_comparison(combined: pd.DataFrame):
    """
    Compare portfolio configurations:
    A) Current: 20% H-009 + 60% H-011 (BTC funding) + 20% H-012
    B) Proposed: 20% H-009 + 60% H-013 (multi-asset funding) + 20% H-012
    C) Alternative: 40% H-009 + 0% funding + 60% H-012
    D) Hybrid: 20% H-009 + 40% H-013 + 40% H-012

    Use funding arb equity curves + BTC trend proxy + XSMom proxy.
    """
    print("\n=== Portfolio Configuration Comparison ===")

    # Build equity curves for each strategy component
    # 1. BTC funding arb (H-011 proxy)
    btc_eq = _build_equity_curve(combined, "btc_only")
    # 2. Multi-asset funding arb (H-013 proxy)
    multi_eq = _build_equity_curve(combined, "all_positive")
    # 3. BTC trend (H-009 proxy) from daily data
    trend_eq = _build_trend_equity()
    # 4. XSMom (H-012 proxy) from daily data
    xsmom_eq = _build_xsmom_equity()

    # Align all to daily
    btc_daily = btc_eq.resample("1D").last().dropna()
    multi_daily = multi_eq.resample("1D").last().dropna()
    trend_daily = trend_eq.resample("1D").last().dropna()
    xsmom_daily = xsmom_eq.resample("1D").last().dropna()

    # Find common date range
    common_start = max(btc_daily.index.min(), multi_daily.index.min(),
                       trend_daily.index.min(), xsmom_daily.index.min())
    common_end = min(btc_daily.index.max(), multi_daily.index.max(),
                     trend_daily.index.max(), xsmom_daily.index.max())

    btc_daily = btc_daily[common_start:common_end]
    multi_daily = multi_daily[common_start:common_end]
    trend_daily = trend_daily[common_start:common_end]
    xsmom_daily = xsmom_daily[common_start:common_end]

    # Compute returns
    btc_ret = btc_daily.pct_change().dropna()
    multi_ret = multi_daily.pct_change().dropna()
    trend_ret = trend_daily.pct_change().dropna()
    xsmom_ret = xsmom_daily.pct_change().dropna()

    # Align returns
    common_idx = btc_ret.index.intersection(multi_ret.index).intersection(
        trend_ret.index).intersection(xsmom_ret.index)
    btc_ret = btc_ret.loc[common_idx]
    multi_ret = multi_ret.loc[common_idx]
    trend_ret = trend_ret.loc[common_idx]
    xsmom_ret = xsmom_ret.loc[common_idx]

    days = len(common_idx)
    print(f"  Common period: {common_idx.min().date()} to {common_idx.max().date()} ({days} days)")

    # Correlations between strategy returns
    print("\n  --- Strategy Return Correlations ---")
    corr_df = pd.DataFrame({
        "H009_Trend": trend_ret,
        "H011_BTC_Funding": btc_ret,
        "H013_Multi_Funding": multi_ret,
        "H012_XSMom": xsmom_ret,
    }).corr()
    print(corr_df.round(3).to_string())

    # Portfolio configurations
    configs = {
        "A: 20/60/20 H009+H011+H012 (current)": {"trend": 0.20, "btc_funding": 0.60, "multi_funding": 0.00, "xsmom": 0.20},
        "B: 20/60/20 H009+H013+H012 (multi-fund)": {"trend": 0.20, "btc_funding": 0.00, "multi_funding": 0.60, "xsmom": 0.20},
        "C: 40/0/60 H009+H012 (no funding)": {"trend": 0.40, "btc_funding": 0.00, "multi_funding": 0.00, "xsmom": 0.60},
        "D: 20/40/40 H009+H013+H012 (hybrid)": {"trend": 0.20, "btc_funding": 0.00, "multi_funding": 0.40, "xsmom": 0.40},
        "E: 20/30/30/20 all four": {"trend": 0.20, "btc_funding": 0.30, "multi_funding": 0.30, "xsmom": 0.20},
    }

    print(f"\n  {'Config':<45s} {'Ann':>7s} {'DD':>7s} {'Sharpe':>7s}")
    print("  " + "-" * 70)

    results = {}
    for name, weights in configs.items():
        port_ret = (
            weights["trend"] * trend_ret +
            weights["btc_funding"] * btc_ret +
            weights["multi_funding"] * multi_ret +
            weights["xsmom"] * xsmom_ret
        )

        ann = port_ret.mean() * 365
        vol = port_ret.std() * np.sqrt(365)
        sharpe = ann / vol if vol > 0 else 0

        eq = (1 + port_ret).cumprod()
        max_dd = ((eq - eq.cummax()) / eq.cummax()).min()

        print(f"  {name:<45s} {ann:>+6.1%} {max_dd:>6.2%} {sharpe:>7.2f}")
        results[name] = {"ann_return": ann, "max_dd": max_dd, "sharpe": sharpe}

    # Recent period analysis (last 180 days)
    print(f"\n  --- Recent 180 Days ---")
    recent_start = common_idx[-180] if len(common_idx) > 180 else common_idx[0]
    btc_ret_r = btc_ret[recent_start:]
    multi_ret_r = multi_ret[recent_start:]
    trend_ret_r = trend_ret[recent_start:]
    xsmom_ret_r = xsmom_ret[recent_start:]

    print(f"  {'Config':<45s} {'Ann':>7s} {'DD':>7s} {'Sharpe':>7s}")
    print("  " + "-" * 70)

    for name, weights in configs.items():
        port_ret_r = (
            weights["trend"] * trend_ret_r +
            weights["btc_funding"] * btc_ret_r +
            weights["multi_funding"] * multi_ret_r +
            weights["xsmom"] * xsmom_ret_r
        )

        ann = port_ret_r.mean() * 365
        vol = port_ret_r.std() * np.sqrt(365)
        sharpe = ann / vol if vol > 0 else 0

        eq = (1 + port_ret_r).cumprod()
        max_dd = ((eq - eq.cummax()) / eq.cummax()).min()

        print(f"  {name:<45s} {ann:>+6.1%} {max_dd:>6.2%} {sharpe:>7.2f}")

    return results


def _build_equity_curve(combined: pd.DataFrame, mode: str) -> pd.Series:
    """Build equity curve for funding arb strategy."""
    rolling = combined.rolling(27).mean().dropna()
    df = combined.loc[rolling.index]

    capital = 10_000.0
    leverage = 5.0
    fee_rate = 0.001
    equity = []
    in_pos = False
    prev_assets = set()

    for ts in rolling.index:
        if mode == "btc_only":
            ravg = rolling.loc[ts, "BTC"]
            rate = df.loc[ts, "BTC"]
            if ravg > 0:
                pnl = capital * leverage * rate
                capital += pnl
                if not in_pos:
                    capital -= fee_rate * capital * leverage
                    in_pos = True
            else:
                if in_pos:
                    capital -= fee_rate * capital * leverage
                    in_pos = False
        elif mode == "all_positive":
            row_rolling = rolling.loc[ts]
            row_actual = df.loc[ts]
            active = set(row_rolling[row_rolling > 0].index)
            if active:
                # Turnover fees
                entered = active - prev_assets
                exited = prev_assets - active
                turnover = len(entered) + len(exited)
                if turnover > 0:
                    per_asset = capital / len(active) * leverage
                    capital -= fee_rate * per_asset * turnover

                cap_per = capital / len(active)
                for asset in active:
                    capital += cap_per * leverage * row_actual[asset]
            prev_assets = active

        equity.append(capital)

    return pd.Series(equity, index=rolling.index)


def _build_trend_equity() -> pd.Series:
    """Build BTC trend following equity curve (H-009 proxy)."""
    btc_file = DATA_DIR / "BTC_USDT_1h.parquet"
    btc_df = pd.read_parquet(btc_file)
    btc_daily = btc_df["close"].resample("1D").last().dropna()

    ema5 = btc_daily.ewm(span=5).mean()
    ema40 = btc_daily.ewm(span=40).mean()
    signal = (ema5 > ema40).astype(int) * 2 - 1  # +1 long, -1 short

    returns = btc_daily.pct_change()

    # Vol targeting at 20%
    vol_30d = returns.rolling(30).std() * np.sqrt(365)
    target_lev = 0.20 / vol_30d
    target_lev = target_lev.clip(upper=2.0)

    strat_returns = signal.shift(1) * returns * target_lev.shift(1)
    strat_returns = strat_returns.dropna()

    equity = (1 + strat_returns).cumprod() * 10_000
    return equity


def _build_xsmom_equity() -> pd.Series:
    """Build cross-sectional momentum equity curve (H-012 proxy)."""
    # Load daily prices for all assets
    prices = {}
    for name in ASSETS_NAMES:
        f = DATA_DIR / f"{name}_USDT_1h.parquet"
        if f.exists():
            df = pd.read_parquet(f)
            prices[name] = df["close"].resample("1D").last()

    price_df = pd.DataFrame(prices).dropna()

    # 60-day returns for ranking
    lookback = 60
    rebal_period = 5
    n_long = 4
    n_short = 4

    returns = price_df.pct_change()
    mom = price_df.pct_change(lookback)

    equity = 10_000.0
    equity_hist = []

    for i in range(lookback + 1, len(price_df)):
        date = price_df.index[i]

        if (i - lookback - 1) % rebal_period == 0:
            # Rank assets by momentum (use t-1)
            rank_vals = mom.iloc[i - 1].dropna()
            if len(rank_vals) < n_long + n_short:
                equity_hist.append(equity)
                continue
            longs = rank_vals.nlargest(n_long).index
            shorts = rank_vals.nsmallest(n_short).index
            weights = {}
            for a in longs:
                weights[a] = 1.0 / n_long
            for a in shorts:
                weights[a] = -1.0 / n_short

        # Daily return
        port_ret = 0
        day_ret = returns.iloc[i]
        for asset, w in weights.items():
            if asset in day_ret.index and not np.isnan(day_ret[asset]):
                port_ret += w * day_ret[asset]

        equity *= (1 + port_ret)
        equity_hist.append(equity)

    idx = price_df.index[lookback + 1:lookback + 1 + len(equity_hist)]
    return pd.Series(equity_hist, index=idx)


def main():
    print("=== H-013 Deep Analysis ===\n")

    combined = load_all_funding()
    print(f"Loaded {len(combined)} funding records for {len(combined.columns)} assets")
    print(f"Period: {combined.index.min()} to {combined.index.max()}\n")

    # 1. Period-split comparison
    print("=== Period-Split Comparison ===")
    periods = [
        ("Full 2yr", None, None),
        ("Recent 365d", str(combined.index.max() - pd.Timedelta(days=365)), None),
        ("Recent 180d", str(combined.index.max() - pd.Timedelta(days=180)), None),
        ("Recent 90d", str(combined.index.max() - pd.Timedelta(days=90)), None),
    ]

    print(f"\n{'Period':<15s} {'BTC-only Ann':>14s} {'Multi Ann':>14s} {'BTC Sharpe':>12s} {'Multi Sharpe':>14s}")
    print("-" * 75)

    for label, start, end in periods:
        r_btc = backtest_btc_only(combined, start_date=start, end_date=end, label=f"BTC {label}")
        r_multi = backtest_all_positive(combined, start_date=start, end_date=end, label=f"Multi {label}")
        print(f"  {label:<15s} {r_btc['ann_return']:>+13.1%} {r_multi['ann_return']:>+13.1%} "
              f"{r_btc['sharpe']:>11.2f} {r_multi['sharpe']:>13.2f}")
        print()

    # 2. Walk-forward validation
    walk_forward_validation(combined)

    # 3. Rebalance frequency sensitivity
    print("\n=== Rebalance Frequency Sensitivity (Multi-Asset) ===")
    for rebal in [1, 3, 9, 27]:  # every 8h, 24h, 3d, 9d
        label = f"Rebal every {rebal} ({rebal*8}h)"
        backtest_all_positive(combined, rebal_every=rebal, label=label)

    # 4. Portfolio comparison
    portfolio_comparison(combined)

    print("\n=== ANALYSIS COMPLETE ===")


if __name__ == "__main__":
    main()
