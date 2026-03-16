"""
H-008: Multi-Asset Daily Trend Following

EMA crossover trend following on daily timeframe across a diversified
crypto futures portfolio. Long when fast EMA > slow EMA, short otherwise.
"""

import numpy as np
import pandas as pd


def resample_to_daily(df_1h: pd.DataFrame) -> pd.DataFrame:
    """Resample 1h OHLCV to daily bars."""
    daily = df_1h.resample("1D").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()
    return daily


def generate_signals(
    daily_close: pd.Series,
    ema_fast: int = 5,
    ema_slow: int = 40,
) -> pd.Series:
    """
    Generate trend following signals from daily close prices.

    Returns:
        Series of 1 (long) / -1 (short) aligned with daily_close index.
    """
    fast = daily_close.ewm(span=ema_fast, adjust=False).mean()
    slow = daily_close.ewm(span=ema_slow, adjust=False).mean()
    signal = pd.Series(np.where(fast > slow, 1, -1), index=daily_close.index)
    # No signal until slow EMA has warmed up
    signal.iloc[:ema_slow] = 0
    return signal


def backtest_single_asset(
    daily_df: pd.DataFrame,
    ema_fast: int = 5,
    ema_slow: int = 40,
    fee_rate: float = 0.001,
    slippage_bps: float = 2.0,
    initial_capital: float = 10_000.0,
) -> dict:
    """
    Backtest EMA crossover on a single asset (daily bars, futures long/short).

    Returns dict with equity_curve (Series), trades (list), and metrics.
    """
    close = daily_df["close"].values
    signals = generate_signals(daily_df["close"], ema_fast, ema_slow).values
    n = len(close)
    slippage = slippage_bps / 10_000

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
                trades.append({
                    "entry_time": str(daily_df.index[max(0, i - 1)]),
                    "exit_time": str(daily_df.index[i]),
                    "direction": position,
                    "pnl": pnl,
                })
                position = 0
                size = 0.0

            # Open
            if target != 0:
                entry_price = price * (1 + target * slippage)
                size = capital / entry_price
                capital -= fee_rate * size * entry_price
                position = target

            equity[i] = capital + (position * size * (price - entry_price) if position != 0 else 0)

    # Close open position at end
    if position != 0:
        exit_price = close[-1] * (1 - position * slippage)
        pnl = position * size * (exit_price - entry_price) - fee_rate * size * exit_price
        capital += pnl
        trades.append({
            "entry_time": str(daily_df.index[-2]) if n > 1 else str(daily_df.index[-1]),
            "exit_time": str(daily_df.index[-1]),
            "direction": position,
            "pnl": pnl,
        })
        equity[-1] = capital

    eq_series = pd.Series(equity, index=daily_df.index)
    return {
        "equity_curve": eq_series,
        "trades": trades,
        "final_capital": capital,
    }


def backtest_portfolio(
    asset_daily: dict[str, pd.DataFrame],
    assets: list[str],
    ema_fast: int = 5,
    ema_slow: int = 40,
    fee_rate: float = 0.001,
    slippage_bps: float = 2.0,
    initial_capital: float = 10_000.0,
    vol_target: float | None = None,
    vol_lookback: int = 60,
) -> dict:
    """
    Backtest equal-weight portfolio of multiple assets.

    If vol_target is set (e.g. 0.10 for 10% annual vol), position sizes are
    scaled by inverse volatility to target that portfolio vol level.

    Returns dict with portfolio equity curve, per-asset results, and metrics.
    """
    n_assets = len(assets)
    if n_assets == 0:
        raise ValueError("No assets provided")

    # Run per-asset backtests with equal capital allocation
    alloc = initial_capital / n_assets
    per_asset = {}
    for sym in assets:
        if sym not in asset_daily:
            continue
        df = asset_daily[sym]
        res = backtest_single_asset(df, ema_fast, ema_slow, fee_rate, slippage_bps, alloc)
        per_asset[sym] = res

    if not per_asset:
        raise ValueError("No valid assets")

    # Build portfolio equity curve by summing per-asset equity
    # Align all equity curves to common dates
    all_eq = pd.DataFrame({sym: r["equity_curve"] for sym, r in per_asset.items()})
    all_eq = all_eq.dropna()
    portfolio_equity = all_eq.sum(axis=1)

    # Apply vol targeting if requested
    if vol_target is not None:
        portfolio_equity = apply_vol_targeting(
            all_eq, initial_capital, vol_target, vol_lookback
        )

    from lib.metrics import summary as calc_summary, returns_from_equity

    periods_per_year = 365  # daily data
    all_trades = []
    for sym, r in per_asset.items():
        all_trades.extend(r["trades"])
    trade_pnls = pd.Series([t["pnl"] for t in all_trades]) if all_trades else pd.Series(dtype=float)

    metrics = calc_summary(portfolio_equity, trade_pnls, periods_per_year)
    metrics["n_assets"] = len(per_asset)
    metrics["assets"] = list(per_asset.keys())

    return {
        "equity_curve": portfolio_equity,
        "per_asset_equity": all_eq,
        "metrics": metrics,
        "trades": all_trades,
    }


def apply_vol_targeting(
    asset_equity: pd.DataFrame,
    initial_capital: float,
    vol_target: float,
    lookback: int = 60,
) -> pd.Series:
    """
    Apply ex-post vol targeting to portfolio equity.

    Scales daily returns so that realized portfolio volatility targets
    vol_target (annualized). Uses lookback-day rolling window of realized vol.
    """
    portfolio_eq = asset_equity.sum(axis=1)
    rets = portfolio_eq.pct_change().fillna(0)
    rolling_vol = rets.rolling(lookback, min_periods=20).std() * np.sqrt(365)

    # Scale factor: target_vol / realized_vol, capped at 2x
    scale = (vol_target / rolling_vol).clip(upper=2.0).fillna(1.0)

    scaled_rets = rets * scale
    scaled_equity = initial_capital * (1 + scaled_rets).cumprod()
    return scaled_equity
