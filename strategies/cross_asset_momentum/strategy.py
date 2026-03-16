"""
H-003: Cross-Asset Momentum Rotation (Multi-Asset Futures)
Rank BTC, ETH, SOL by momentum. Long strongest, short weakest.
Market-neutral exposure. Rebalance weekly.
Instrument: futures (BTC/USDT, ETH/USDT, SOL/USDT perps)
Timeframe: 1h data, rebalance every 168 bars (1 week)
"""

import numpy as np
import pandas as pd


def compute_momentum(close: pd.Series, window: int) -> pd.Series:
    """Rate of change over window."""
    return close.pct_change(window)


def generate_rotation_signals(
    prices: dict[str, pd.DataFrame],
    fast_window: int = 168,   # 7 days in hours
    slow_window: int = 504,   # 21 days in hours
    rebalance_bars: int = 168, # rebalance weekly
    fast_weight: float = 0.6,
    slow_weight: float = 0.4,
) -> dict[str, pd.Series]:
    """
    Generate rotation signals for multiple assets.

    Args:
        prices: dict of symbol -> OHLCV DataFrame
        fast_window: fast momentum lookback
        slow_window: slow momentum lookback
        rebalance_bars: bars between rebalances
        fast_weight: weight for fast momentum score
        slow_weight: weight for slow momentum score

    Returns:
        dict of symbol -> signal Series (1=long, -1=short, 0=flat)
    """
    symbols = list(prices.keys())

    # Align all price series to common index
    closes = pd.DataFrame({sym: prices[sym]["close"] for sym in symbols})
    closes = closes.dropna()

    n = len(closes)
    signals = {sym: np.zeros(n) for sym in symbols}

    # Compute momentum scores
    fast_mom = {sym: compute_momentum(closes[sym], fast_window) for sym in symbols}
    slow_mom = {sym: compute_momentum(closes[sym], slow_window) for sym in symbols}

    # Generate signals at rebalance points
    last_long = None
    last_short = None

    for i in range(slow_window, n):
        if (i - slow_window) % rebalance_bars == 0:
            # Score each asset
            scores = {}
            for sym in symbols:
                fm = fast_mom[sym].iloc[i]
                sm = slow_mom[sym].iloc[i]
                if np.isnan(fm) or np.isnan(sm):
                    scores[sym] = 0.0
                else:
                    scores[sym] = fast_weight * fm + slow_weight * sm

            # Rank: long best, short worst
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            last_long = ranked[0][0]
            last_short = ranked[-1][0]

        # Apply signals
        if last_long is not None:
            for sym in symbols:
                if sym == last_long:
                    signals[sym][i] = 1
                elif sym == last_short:
                    signals[sym][i] = -1
                else:
                    signals[sym][i] = 0

    return {sym: pd.Series(signals[sym], index=closes.index) for sym in symbols}
