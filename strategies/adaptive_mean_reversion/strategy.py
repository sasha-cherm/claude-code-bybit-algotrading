"""
H-006: Adaptive Mean Reversion (BTC Futures, Long/Short)
Entry long: close < BB_lower AND RSI < rsi_long_entry AND regime=range
Entry short: close > BB_upper AND RSI > rsi_short_entry AND regime=range
Exit: close crosses BB_middle
Stop: stop_atr_mult * ATR
Regime filter: ATR(24)/ATR(168) < regime_threshold => range-bound => trade
Mode: futures (long/short)
Timeframe: 1h
"""

import numpy as np
import pandas as pd


def compute_bollinger_bands(close: pd.Series, window: int = 20, num_std: float = 2.0):
    """Compute Bollinger Bands."""
    middle = close.rolling(window).mean()
    std = close.rolling(window).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, middle, lower


def compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Compute RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


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
    bb_window: int = 20,
    bb_std: float = 2.0,
    rsi_window: int = 14,
    rsi_long_entry: float = 35.0,
    rsi_short_entry: float = 65.0,
    atr_short_window: int = 24,
    atr_long_window: int = 168,
    regime_threshold: float = 1.0,
    stop_atr_mult: float = 2.0,
    require_reversal: bool = True,
) -> pd.Series:
    """
    Generate adaptive mean reversion signals with regime filter and reversal confirmation.

    Reversal confirmation: instead of entering on the BB touch itself, wait for the
    close to move back inside the band (confirming the reversal has started).
    This avoids entering during waterfall sell-offs / melt-ups.

    Returns: Series of 1 (long), -1 (short), 0 (flat).
    """
    close = df["close"]

    # Compute indicators
    bb_upper, bb_middle, bb_lower = compute_bollinger_bands(close, bb_window, bb_std)
    rsi = compute_rsi(close, rsi_window)
    atr_short = compute_atr(df, atr_short_window)
    atr_long = compute_atr(df, atr_long_window)

    # Regime: ratio < threshold means range-bound (favorable for mean reversion)
    regime_ratio = atr_short / atr_long

    n = len(df)
    signals = np.zeros(n)
    position = 0  # -1, 0, 1
    entry_price = 0.0
    stop_price = 0.0
    # Track "primed" state: BB touch detected, waiting for reversal confirmation
    primed_long = False
    primed_short = False
    primed_price = 0.0  # price at BB touch (worst price for stop calculation)

    warmup = max(bb_window, atr_long_window) + 1

    for i in range(warmup, n):
        c = close.iloc[i]
        prev_c = close.iloc[i - 1]
        rsi_val = rsi.iloc[i]
        bb_up = bb_upper.iloc[i]
        bb_mid = bb_middle.iloc[i]
        bb_lo = bb_lower.iloc[i]
        atr_val = atr_short.iloc[i]
        regime = regime_ratio.iloc[i]

        if np.isnan(regime) or np.isnan(rsi_val) or np.isnan(bb_lo) or np.isnan(atr_val):
            signals[i] = 0
            primed_long = False
            primed_short = False
            continue

        is_range_bound = regime < regime_threshold

        if position == 0:
            if not is_range_bound:
                signals[i] = 0
                primed_long = False
                primed_short = False
                continue

            if require_reversal:
                # Step 1: detect BB touch (prime the signal)
                if prev_c < bb_lower.iloc[i - 1] and rsi.iloc[i - 1] < rsi_long_entry:
                    primed_long = True
                    primed_price = prev_c
                if prev_c > bb_upper.iloc[i - 1] and rsi.iloc[i - 1] > rsi_short_entry:
                    primed_short = True
                    primed_price = prev_c

                # Step 2: confirm reversal (close moves back inside BB)
                if primed_long and c > bb_lo and c > prev_c:
                    position = 1
                    entry_price = c
                    stop_price = min(c, primed_price) - stop_atr_mult * atr_val
                    signals[i] = 1
                    primed_long = False
                    primed_short = False
                elif primed_short and c < bb_up and c < prev_c:
                    position = -1
                    entry_price = c
                    stop_price = max(c, primed_price) + stop_atr_mult * atr_val
                    signals[i] = -1
                    primed_long = False
                    primed_short = False
                else:
                    signals[i] = 0
                    # Reset primed if price moves too far away (3 bars stale)
                    if primed_long and c > bb_mid:
                        primed_long = False
                    if primed_short and c < bb_mid:
                        primed_short = False
            else:
                # No reversal required (original behavior)
                if c < bb_lo and rsi_val < rsi_long_entry:
                    position = 1
                    entry_price = c
                    stop_price = c - stop_atr_mult * atr_val
                    signals[i] = 1
                elif c > bb_up and rsi_val > rsi_short_entry:
                    position = -1
                    entry_price = c
                    stop_price = c + stop_atr_mult * atr_val
                    signals[i] = -1
                else:
                    signals[i] = 0
        else:
            # Exit conditions
            hit_stop = (position == 1 and c < stop_price) or (position == -1 and c > stop_price)
            # Mean reversion target: cross BB middle
            hit_target = (position == 1 and c > bb_mid) or (position == -1 and c < bb_mid)

            if hit_stop or hit_target:
                signals[i] = 0
                position = 0
                primed_long = False
                primed_short = False
            else:
                signals[i] = position

    return pd.Series(signals, index=df.index)
