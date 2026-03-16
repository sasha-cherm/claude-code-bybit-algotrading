"""
H-007: BTC/ETH Ratio Mean Reversion (Pairs Trading)
Market-neutral strategy: trade the BTC/ETH log ratio z-score.

When z-score > entry: ratio is high (BTC overpriced vs ETH) → short BTC, long ETH
When z-score < -entry: ratio is low (ETH overpriced vs BTC) → long BTC, short ETH
Exit: z-score crosses back to exit_z (near zero)
Stop: z-score exceeds stop_z (spread diverges further)

Each leg is 50% of capital → ~delta-neutral.
Mode: futures (both legs can be shorted)
Timeframe: 1h
"""

import numpy as np
import pandas as pd


def compute_spread_and_signals(
    btc: pd.DataFrame,
    eth: pd.DataFrame,
    lookback: int = 168,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    stop_z: float = 4.0,
) -> tuple[pd.Series, pd.Series]:
    """
    Compute the log ratio z-score and generate trading signals.

    Returns:
        (z_score, signals) where signals are:
         1 = long ratio (long BTC, short ETH) — z < -entry
        -1 = short ratio (short BTC, long ETH) — z > entry
         0 = flat
    """
    log_ratio = np.log(btc["close"] / eth["close"])
    lr_mean = log_ratio.rolling(lookback).mean()
    lr_std = log_ratio.rolling(lookback).std()
    z_score = (log_ratio - lr_mean) / lr_std

    n = len(z_score)
    signals = np.zeros(n)
    position = 0  # 1 = long ratio, -1 = short ratio, 0 = flat

    for i in range(lookback + 1, n):
        z = z_score.iloc[i]

        if np.isnan(z):
            signals[i] = 0
            continue

        if position == 0:
            # Entry: z deviated enough
            if z > entry_z:
                position = -1  # short ratio: short BTC, long ETH
                signals[i] = -1
            elif z < -entry_z:
                position = 1  # long ratio: long BTC, short ETH
                signals[i] = 1
            else:
                signals[i] = 0
        else:
            # Exit: z reverted toward zero
            if position == 1 and z > -exit_z:
                position = 0
                signals[i] = 0
            elif position == -1 and z < exit_z:
                position = 0
                signals[i] = 0
            # Stop: z diverged further
            elif abs(z) > stop_z:
                position = 0
                signals[i] = 0
            else:
                signals[i] = position

    return z_score, pd.Series(signals, index=btc.index)


def backtest_pairs(
    btc: pd.DataFrame,
    eth: pd.DataFrame,
    signals: pd.Series,
    initial_capital: float = 10_000.0,
    fee_rate: float = 0.001,
    slippage_bps: float = 2.0,
) -> dict:
    """
    Backtest the pairs strategy.

    When signal = 1 (long ratio): 50% long BTC, 50% short ETH
    When signal = -1 (short ratio): 50% short BTC, 50% long ETH
    When signal = 0: flat both

    Returns performance dict.
    """
    btc_close = btc["close"].values
    eth_close = eth["close"].values
    sig = signals.values
    n = len(btc_close)
    slippage = slippage_bps / 10_000

    capital = initial_capital
    position = 0
    btc_size = 0.0  # positive = long, negative = short
    eth_size = 0.0
    btc_entry = 0.0
    eth_entry = 0.0

    equity = np.zeros(n)
    equity[0] = capital
    trades = []

    for i in range(1, n):
        bp = btc_close[i]
        ep = eth_close[i]
        target = int(sig[i]) if not np.isnan(sig[i]) else 0

        # Mark-to-market
        if position != 0:
            btc_pnl = btc_size * (bp - btc_entry)
            eth_pnl = eth_size * (ep - eth_entry)
            equity[i] = capital + btc_pnl + eth_pnl
        else:
            equity[i] = capital

        if target != position:
            # Close existing positions
            if position != 0:
                # Close BTC leg
                btc_exit = bp * (1 - np.sign(btc_size) * slippage)
                btc_pnl = btc_size * (btc_exit - btc_entry) - fee_rate * abs(btc_size) * btc_exit
                # Close ETH leg
                eth_exit = ep * (1 - np.sign(eth_size) * slippage)
                eth_pnl = eth_size * (eth_exit - eth_entry) - fee_rate * abs(eth_size) * eth_exit
                total_pnl = btc_pnl + eth_pnl
                capital += total_pnl
                trades.append(total_pnl)
                btc_size = 0.0
                eth_size = 0.0
                position = 0

            # Open new positions
            if target != 0:
                half_cap = capital / 2
                if target == 1:
                    # Long ratio: long BTC, short ETH
                    btc_entry = bp * (1 + slippage)
                    eth_entry = ep * (1 - slippage)
                    btc_size = half_cap / btc_entry  # long
                    eth_size = -(half_cap / eth_entry)  # short
                else:
                    # Short ratio: short BTC, long ETH
                    btc_entry = bp * (1 - slippage)
                    eth_entry = ep * (1 + slippage)
                    btc_size = -(half_cap / btc_entry)  # short
                    eth_size = half_cap / eth_entry  # long

                # Entry fees (both legs)
                capital -= fee_rate * abs(btc_size) * abs(btc_entry)
                capital -= fee_rate * abs(eth_size) * abs(eth_entry)
                position = target

            btc_pnl = btc_size * (bp - btc_entry) if position != 0 else 0
            eth_pnl = eth_size * (ep - eth_entry) if position != 0 else 0
            equity[i] = capital + btc_pnl + eth_pnl

    # Close any open position at end
    if position != 0:
        bp = btc_close[-1]
        ep = eth_close[-1]
        btc_exit = bp * (1 - np.sign(btc_size) * slippage)
        btc_pnl = btc_size * (btc_exit - btc_entry) - fee_rate * abs(btc_size) * btc_exit
        eth_exit = ep * (1 - np.sign(eth_size) * slippage)
        eth_pnl = eth_size * (eth_exit - eth_entry) - fee_rate * abs(eth_size) * eth_exit
        total_pnl = btc_pnl + eth_pnl
        capital += total_pnl
        trades.append(total_pnl)
        equity[-1] = capital

    equity_series = pd.Series(equity, index=btc.index)

    # Compute metrics
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent.parent))
    from lib.metrics import summary
    trade_pnls = pd.Series(trades) if trades else pd.Series(dtype=float)

    # periods_per_year for 1h data
    if len(btc) > 1:
        freq_hours = (btc.index[1] - btc.index[0]).total_seconds() / 3600
        periods_per_year = 8760 / freq_hours
    else:
        periods_per_year = 8760

    result = summary(equity_series, trade_pnls, periods_per_year)
    result["initial_capital"] = initial_capital
    result["final_capital"] = round(float(equity[-1]), 2)
    result["fee_rate"] = fee_rate
    result["mode"] = "pairs"
    return result
