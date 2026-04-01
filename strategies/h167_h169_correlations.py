#!/usr/bin/env python3
"""Check correlations of H-167 and H-169 against all existing strategies."""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from strategies.h167_h168_h169_backtest import (
    load_daily, backtest_h167, backtest_h169, backtest_momentum, evaluate
)

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]


# ── Reference strategies ──

def backtest_lowvol(closes, lookback=20, rebal_freq=21, n=3):
    """H-019: Low vol long."""
    returns = closes.pct_change().dropna()
    dates = returns.index
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_returns.append({"date": dates[i], "return": (returns.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            vol = returns.iloc[i-lookback:i].std()
            ranked = vol.sort_values(ascending=True)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_returns:
        return None
    return pd.DataFrame(portfolio_returns).set_index("date")["return"]


def backtest_size(closes, lookback=30, rebal_freq=5, n=5):
    """H-031: Size factor (large-cap long)."""
    # Use close * volume as proxy for dollar volume (size)
    returns = closes.pct_change().dropna()
    dates = returns.index
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_returns.append({"date": dates[i], "return": (returns.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            # Use price level as size proxy (highly correlated with market cap in crypto)
            price = closes.iloc[i-1]
            ranked = price.sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_returns:
        return None
    return pd.DataFrame(portfolio_returns).set_index("date")["return"]


def backtest_efficiency(closes, lookback=40, rebal_freq=5, n=4):
    """H-076: Price efficiency factor."""
    returns = closes.pct_change().dropna()
    dates = returns.index
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_returns.append({"date": dates[i], "return": (returns.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                p = closes[sym].iloc[i-lookback:i]
                net_move = abs(p.iloc[-1] / p.iloc[0] - 1)
                daily_moves = abs(p.pct_change().dropna()).sum()
                eff = net_move / daily_moves if daily_moves > 0 else 0
                signals[sym] = eff
            ranked = pd.Series(signals).sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_returns:
        return None
    return pd.DataFrame(portfolio_returns).set_index("date")["return"]


def backtest_trend_quality(closes, lookback=60, rebal_freq=5, n=3):
    """H-160: Trend quality (efficiency * inv_vol)."""
    returns = closes.pct_change().dropna()
    dates = returns.index
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_returns.append({"date": dates[i], "return": (returns.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                p = closes[sym].iloc[i-lookback:i]
                net_move = abs(p.iloc[-1] / p.iloc[0] - 1)
                daily_moves = abs(p.pct_change().dropna()).sum()
                eff = net_move / daily_moves if daily_moves > 0 else 0
                vol = returns[sym].iloc[max(0,i-lookback):i].std()
                inv_vol = 1.0 / vol if vol > 1e-8 else 0
                signals[sym] = eff * inv_vol
            ranked = pd.Series(signals).sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_returns:
        return None
    return pd.DataFrame(portfolio_returns).set_index("date")["return"]


def main():
    print("Loading data...")
    closes, volumes = load_daily()
    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    # Generate all strategy returns
    print("Computing strategy returns...")
    strategies = {}
    strategies["H-012 Momentum"] = backtest_momentum(closes)
    strategies["H-019 LowVol"] = backtest_lowvol(closes)
    strategies["H-031 Size"] = backtest_size(closes)
    strategies["H-076 Efficiency"] = backtest_efficiency(closes)
    strategies["H-160 TrendQuality"] = backtest_trend_quality(closes)
    strategies["H-167 VolPriceConf"] = backtest_h167(closes, volumes, lookback=10, rebal_freq=7, n_long=4, n_short=4)
    strategies["H-169 Alpha"] = backtest_h169(closes, lookback=10, rebal_freq=5, n_long=4, n_short=4)

    # Build correlation matrix
    all_rets = pd.DataFrame({k: v for k, v in strategies.items() if v is not None})
    all_rets = all_rets.dropna()

    print(f"\nCorrelation matrix ({len(all_rets)} common days):")
    corr = all_rets.corr()
    print(corr.round(3).to_string())

    # Specific correlations for H-167 and H-169
    print("\n--- H-167 correlations ---")
    for name in corr.columns:
        if name != "H-167 VolPriceConf":
            print(f"  vs {name}: {corr.loc['H-167 VolPriceConf', name]:.3f}")

    print("\n--- H-169 correlations ---")
    for name in corr.columns:
        if name != "H-169 Alpha":
            print(f"  vs {name}: {corr.loc['H-169 Alpha', name]:.3f}")

    # Check H-167 vs H-169 mutual correlation
    print(f"\nH-167 vs H-169: {corr.loc['H-167 VolPriceConf', 'H-169 Alpha']:.3f}")


if __name__ == "__main__":
    main()
