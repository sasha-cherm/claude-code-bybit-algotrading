"""
Performance metrics for backtesting and strategy evaluation.
Sharpe, drawdown, returns, win rate, etc.
"""

import numpy as np
import pandas as pd

# Annualization constants
HOURLY = 8760    # 24 * 365
DAILY = 365
EIGHT_HOUR = 1095  # 365 * 3 (for funding rate 8h data)


def total_return(equity_curve: pd.Series) -> float:
    """Total return as a fraction (0.20 = 20%)."""
    return (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1.0


def annual_return(equity_curve: pd.Series, periods_per_year: float = 8760) -> float:
    """
    Annualized return.
    Default periods_per_year=8760 assumes hourly data (24*365).
    """
    n = len(equity_curve)
    if n < 2:
        return 0.0
    total = total_return(equity_curve)
    years = n / periods_per_year
    if years <= 0:
        return 0.0
    return (1.0 + total) ** (1.0 / years) - 1.0


def max_drawdown(equity_curve: pd.Series) -> float:
    """Maximum drawdown as a positive fraction (0.10 = 10% drawdown)."""
    peak = equity_curve.cummax()
    dd = (equity_curve - peak) / peak
    return abs(dd.min())


def drawdown_series(equity_curve: pd.Series) -> pd.Series:
    """Drawdown at each point as a negative fraction."""
    peak = equity_curve.cummax()
    return (equity_curve - peak) / peak


def sharpe_ratio(
    returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: float = 8760
) -> float:
    """
    Annualized Sharpe ratio.
    `returns` should be period returns (not cumulative).
    """
    if returns.std() == 0:
        return 0.0
    excess = returns - risk_free_rate / periods_per_year
    return float(excess.mean() / excess.std() * np.sqrt(periods_per_year))


def sortino_ratio(
    returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: float = 8760
) -> float:
    """Annualized Sortino ratio (downside deviation only)."""
    excess = returns - risk_free_rate / periods_per_year
    downside = excess[excess < 0]
    if len(downside) == 0 or downside.std() == 0:
        return float("inf") if excess.mean() > 0 else 0.0
    return float(excess.mean() / downside.std() * np.sqrt(periods_per_year))


def win_rate(trades: pd.Series) -> float:
    """Win rate from a series of trade PnLs."""
    if len(trades) == 0:
        return 0.0
    return float((trades > 0).sum() / len(trades))


def profit_factor(trades: pd.Series) -> float:
    """Gross profit / gross loss."""
    gross_profit = trades[trades > 0].sum()
    gross_loss = abs(trades[trades < 0].sum())
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return float(gross_profit / gross_loss)


def calmar_ratio(equity_curve: pd.Series, periods_per_year: float = 8760) -> float:
    """Annualized return / max drawdown."""
    mdd = max_drawdown(equity_curve)
    if mdd == 0:
        return float("inf")
    ar = annual_return(equity_curve, periods_per_year)
    return float(ar / mdd)


def returns_from_equity(equity_curve: pd.Series) -> pd.Series:
    """Convert equity curve to period returns."""
    return equity_curve.pct_change().dropna()


def equity_from_returns(returns: pd.Series, initial_capital: float = 10000.0) -> pd.Series:
    """Convert period returns to equity curve."""
    return initial_capital * (1.0 + returns).cumprod()


def summary(
    equity_curve: pd.Series,
    trades: pd.Series | None = None,
    periods_per_year: float = 8760,
) -> dict:
    """
    Full performance summary dict.

    Args:
        equity_curve: Series of portfolio value over time.
        trades: Optional series of individual trade PnLs.
        periods_per_year: Number of periods in a year (8760 for hourly).

    Returns:
        Dict with all key metrics.
    """
    rets = returns_from_equity(equity_curve)
    result = {
        "total_return": round(total_return(equity_curve), 4),
        "annual_return": round(annual_return(equity_curve, periods_per_year), 4),
        "max_drawdown": round(max_drawdown(equity_curve), 4),
        "sharpe_ratio": round(sharpe_ratio(rets, periods_per_year=periods_per_year), 4),
        "sortino_ratio": round(sortino_ratio(rets, periods_per_year=periods_per_year), 4),
        "calmar_ratio": round(calmar_ratio(equity_curve, periods_per_year), 4),
        "n_periods": len(equity_curve),
    }
    if trades is not None and len(trades) > 0:
        result["n_trades"] = len(trades)
        result["win_rate"] = round(win_rate(trades), 4)
        result["profit_factor"] = round(profit_factor(trades), 4)
        result["avg_trade"] = round(float(trades.mean()), 4)
        result["best_trade"] = round(float(trades.max()), 4)
        result["worst_trade"] = round(float(trades.min()), 4)
    return result
