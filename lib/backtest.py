"""
Vectorized backtest engine for single-asset strategies.
Supports long-only (spot) and long/short (futures) modes.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from lib.metrics import summary, returns_from_equity


@dataclass
class BacktestConfig:
    initial_capital: float = 10_000.0
    fee_rate: float = 0.001  # 0.1% taker fee (Bybit standard)
    slippage_bps: float = 2.0  # 2 bps slippage per trade
    mode: str = "futures"  # "spot" (long-only) or "futures" (long/short)


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: int  # 1 = long, -1 = short
    entry_price: float
    exit_price: float
    size: float  # in base currency units
    pnl: float
    pnl_pct: float


class Backtest:
    """
    Event-driven backtest engine.

    Usage:
        1. Subclass and implement generate_signals(df) -> pd.Series of {-1, 0, 1}
        2. Or pass signals directly to run()
    """

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()
        self.trades: list[Trade] = []
        self.equity_curve: pd.Series | None = None

    def run(self, df: pd.DataFrame, signals: pd.Series) -> dict:
        """
        Run backtest with pre-computed signals.

        Args:
            df: OHLCV DataFrame (must have 'close' column).
            signals: Series aligned with df index.
                     Values: 1 (long), -1 (short), 0 (flat).
                     For spot mode, -1 is treated as 0.

        Returns:
            Performance summary dict.
        """
        if self.config.mode == "spot":
            signals = signals.clip(lower=0)

        close = df["close"].values
        sig = signals.values
        n = len(close)

        capital = self.config.initial_capital
        position = 0  # current direction: -1, 0, 1
        entry_price = 0.0
        entry_time = None
        size = 0.0

        equity = np.zeros(n)
        equity[0] = capital
        trades = []
        fee_rate = self.config.fee_rate
        slippage = self.config.slippage_bps / 10_000

        for i in range(1, n):
            price = close[i]
            target = int(sig[i]) if not np.isnan(sig[i]) else 0

            # Mark-to-market current position
            if position != 0:
                unrealized = position * size * (price - entry_price)
                equity[i] = capital + unrealized
            else:
                equity[i] = capital

            # Check for position change
            if target != position:
                # Close existing position
                if position != 0:
                    exit_price = price * (1 - position * slippage)  # slippage against us
                    pnl = position * size * (exit_price - entry_price) - fee_rate * size * exit_price
                    capital += pnl
                    trades.append(Trade(
                        entry_time=entry_time,
                        exit_time=df.index[i],
                        direction=position,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        size=size,
                        pnl=pnl,
                        pnl_pct=pnl / (size * entry_price) if size * entry_price > 0 else 0,
                    ))
                    position = 0
                    size = 0.0

                # Open new position
                if target != 0:
                    entry_price = price * (1 + target * slippage)  # slippage against us
                    size = capital / entry_price  # full allocation
                    entry_price_with_fee = entry_price
                    capital -= fee_rate * size * entry_price  # entry fee
                    position = target
                    entry_time = df.index[i]

                equity[i] = capital + (position * size * (price - entry_price) if position != 0 else 0)

        # Close any open position at the end
        if position != 0:
            exit_price = close[-1] * (1 - position * slippage)
            pnl = position * size * (exit_price - entry_price) - fee_rate * size * exit_price
            capital += pnl
            trades.append(Trade(
                entry_time=entry_time,
                exit_time=df.index[-1],
                direction=position,
                entry_price=entry_price,
                exit_price=exit_price,
                size=size,
                pnl=pnl,
                pnl_pct=pnl / (size * entry_price) if size * entry_price > 0 else 0,
            ))
            equity[-1] = capital

        self.equity_curve = pd.Series(equity, index=df.index)
        self.trades = trades

        # Determine periods_per_year from data frequency
        if len(df) > 1:
            freq_hours = (df.index[1] - df.index[0]).total_seconds() / 3600
            periods_per_year = 8760 / freq_hours
        else:
            periods_per_year = 8760

        trade_pnls = pd.Series([t.pnl for t in trades]) if trades else pd.Series(dtype=float)
        result = summary(self.equity_curve, trade_pnls, periods_per_year)
        result["mode"] = self.config.mode
        result["fee_rate"] = self.config.fee_rate
        result["initial_capital"] = self.config.initial_capital
        result["final_capital"] = round(float(equity[-1]), 2)
        return result

    def save_results(self, results: dict, path: str | Path):
        """Save backtest results to JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(results, f, indent=2, default=str)

    def get_trades_df(self) -> pd.DataFrame:
        """Return trades as a DataFrame."""
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([
            {
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "direction": "long" if t.direction == 1 else "short",
                "entry_price": round(t.entry_price, 2),
                "exit_price": round(t.exit_price, 2),
                "pnl": round(t.pnl, 2),
                "pnl_pct": round(t.pnl_pct, 4),
            }
            for t in self.trades
        ])
