"""
H-002: Bollinger Band Mean Reversion (BTC Spot)
Entry: close < BB_lower(20,2) AND RSI(14) < 30
Exit: close > BB_middle(20) OR RSI > 60
Stop-loss: 3% below entry
Mode: spot (long-only)
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


def generate_signals(
    df: pd.DataFrame,
    bb_window: int = 20,
    bb_std: float = 2.0,
    rsi_window: int = 14,
    rsi_entry: float = 30.0,
    rsi_exit: float = 60.0,
    stop_loss_pct: float = 0.03,
) -> pd.Series:
    """
    Generate long-only mean reversion signals.

    Returns: Series of 1 (long) or 0 (flat).
    """
    close = df["close"]
    bb_upper, bb_middle, bb_lower = compute_bollinger_bands(close, bb_window, bb_std)
    rsi = compute_rsi(close, rsi_window)

    n = len(df)
    signals = np.zeros(n)
    position = 0  # 0 = flat, 1 = long
    entry_price = 0.0

    for i in range(1, n):
        if position == 0:
            # Entry: close below lower BB and RSI oversold
            if close.iloc[i] < bb_lower.iloc[i] and rsi.iloc[i] < rsi_entry:
                if not np.isnan(bb_lower.iloc[i]) and not np.isnan(rsi.iloc[i]):
                    position = 1
                    entry_price = close.iloc[i]
                    signals[i] = 1
            else:
                signals[i] = 0
        else:
            # Exit conditions
            hit_stop = close.iloc[i] < entry_price * (1 - stop_loss_pct)
            hit_bb_middle = close.iloc[i] > bb_middle.iloc[i]
            hit_rsi_exit = rsi.iloc[i] > rsi_exit

            if hit_stop or hit_bb_middle or hit_rsi_exit:
                position = 0
                signals[i] = 0
            else:
                signals[i] = 1

    return pd.Series(signals, index=df.index)
