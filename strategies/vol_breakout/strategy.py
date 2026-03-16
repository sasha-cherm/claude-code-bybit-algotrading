"""
H-004: Volatility Breakout (BTC Futures)
Entry long: close > channel_high + multiplier * ATR
Entry short: close < channel_low - multiplier * ATR
Exit: trailing stop at trail_atr * ATR or mean reversion to channel midpoint
Max holding period: max_hold bars
Filter: only trade when ATR(24) > ATR(168) (expanding vol)
Mode: futures (long/short)
Timeframe: 1h
"""

import numpy as np
import pandas as pd


def compute_atr(df: pd.DataFrame, window: int = 24) -> pd.Series:
    """Compute Average True Range."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window).mean()


def generate_signals(
    df: pd.DataFrame,
    channel_window: int = 24,
    atr_window: int = 24,
    atr_long_window: int = 168,
    breakout_mult: float = 0.5,
    trail_atr_mult: float = 1.5,
    max_hold: int = 48,
    vol_filter: bool = True,
) -> pd.Series:
    """
    Generate volatility breakout signals.

    Returns: Series of 1 (long), -1 (short), 0 (flat).
    """
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # Compute indicators
    atr_short = compute_atr(df, atr_window)
    atr_long = compute_atr(df, atr_long_window)
    # Shift by 1 so channel is based on PRIOR bars (excluding current)
    channel_high = high.rolling(channel_window).max().shift(1)
    channel_low = low.rolling(channel_window).min().shift(1)
    channel_mid = (channel_high + channel_low) / 2

    n = len(df)
    signals = np.zeros(n)
    position = 0  # -1, 0, 1
    entry_price = 0.0
    trail_stop = 0.0
    bars_held = 0

    warmup = max(channel_window, atr_long_window) + 1

    for i in range(warmup, n):
        c = close.iloc[i]
        atr_val = atr_short.iloc[i]
        ch_high = channel_high.iloc[i]
        ch_low = channel_low.iloc[i]
        ch_mid = channel_mid.iloc[i]

        if np.isnan(atr_val) or np.isnan(ch_high):
            signals[i] = 0
            continue

        # Vol filter: only trade when short-term vol > long-term vol (expanding)
        expanding_vol = True
        if vol_filter:
            atr_l = atr_long.iloc[i]
            if np.isnan(atr_l) or atr_l == 0:
                expanding_vol = False
            else:
                expanding_vol = (atr_val / atr_l) > 1.0

        if position == 0:
            if not expanding_vol:
                signals[i] = 0
                continue

            # Long breakout
            if c > ch_high + breakout_mult * atr_val:
                position = 1
                entry_price = c
                trail_stop = c - trail_atr_mult * atr_val
                bars_held = 0
                signals[i] = 1
            # Short breakout
            elif c < ch_low - breakout_mult * atr_val:
                position = -1
                entry_price = c
                trail_stop = c + trail_atr_mult * atr_val
                bars_held = 0
                signals[i] = -1
            else:
                signals[i] = 0
        else:
            bars_held += 1

            # Update trailing stop
            if position == 1:
                new_stop = c - trail_atr_mult * atr_val
                trail_stop = max(trail_stop, new_stop)
            else:
                new_stop = c + trail_atr_mult * atr_val
                trail_stop = min(trail_stop, new_stop)

            # Exit conditions
            hit_trail = (position == 1 and c < trail_stop) or (position == -1 and c > trail_stop)
            hit_mean = (position == 1 and c < ch_mid) or (position == -1 and c > ch_mid)
            hit_max_hold = bars_held >= max_hold

            if hit_trail or hit_mean or hit_max_hold:
                signals[i] = 0
                position = 0
                bars_held = 0
            else:
                signals[i] = position

    return pd.Series(signals, index=df.index)
