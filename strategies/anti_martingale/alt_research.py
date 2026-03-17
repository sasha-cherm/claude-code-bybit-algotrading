"""
Alternative strategy research for portfolio diversification.

Since H-014 (anti-martingale) was rejected, explore:
1. RSI mean-reversion on daily BTC (long+short) — different signal than EMA
2. Bollinger Band squeeze breakout — vol expansion after compression
3. Multi-asset rotation with momentum decay filter

Focus: find something uncorrelated with H-009 (EMA trend) and H-012 (XSMom).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import summary, returns_from_equity, sharpe_ratio
from strategies.daily_trend_multi_asset.strategy import (
    generate_signals,
    resample_to_daily,
)


def test_daily_rsi_mean_reversion():
    """
    H-015: RSI-based mean reversion on daily BTC.
    Long when RSI oversold, short when overbought.
    This should be NEGATIVELY correlated with H-009 (trend following).
    """
    print("=" * 80)
    print("H-015: Daily RSI Mean Reversion (BTC)")
    print("=" * 80)

    df_1h = fetch_and_cache("BTC/USDT", "1h", limit_days=730)
    daily = resample_to_daily(df_1h)
    prices = daily["close"]

    results = []
    for rsi_period in [7, 14, 21]:
        for oversold in [25, 30, 35]:
            overbought = 100 - oversold
            for exit_level in [45, 50, 55]:
                # Compute RSI
                delta = prices.diff()
                gain = delta.where(delta > 0, 0).rolling(rsi_period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
                rs = gain / loss.replace(0, np.nan)
                rsi = 100 - (100 / (1 + rs))

                # Generate signals
                signals = pd.Series(0, index=prices.index)
                position = 0
                for i in range(rsi_period, len(prices)):
                    r = rsi.iloc[i]
                    if np.isnan(r):
                        continue
                    if position == 0:
                        if r < oversold:
                            position = 1  # long
                        elif r > overbought:
                            position = -1  # short
                    elif position == 1:
                        if r > exit_level:
                            position = 0
                        elif r > overbought:
                            position = -1
                    elif position == -1:
                        if r < (100 - exit_level):
                            position = 0
                        elif r < oversold:
                            position = 1
                    signals.iloc[i] = position

                # Compute returns
                strat_ret = signals.shift(1) * prices.pct_change()
                strat_ret = strat_ret.dropna()
                # Subtract fees for trades
                trades = (signals.diff() != 0) & (signals.diff().notna())
                n_trades = trades.sum()
                fee_drag = n_trades * 0.001 * 2  # round-trip fee
                total_ret = (1 + strat_ret).prod() - 1 - fee_drag / len(strat_ret)

                eq = 10000 * (1 + strat_ret).cumprod()
                s = sharpe_ratio(strat_ret, periods_per_year=365)
                ann = (eq.iloc[-1] / eq.iloc[0]) ** (365 / len(eq)) - 1
                dd = ((eq.cummax() - eq) / eq.cummax()).max()

                results.append({
                    "rsi_period": rsi_period, "oversold": oversold,
                    "overbought": overbought, "exit": exit_level,
                    "sharpe": s, "annual": ann, "max_dd": dd,
                    "n_trades": int(n_trades),
                })

    df = pd.DataFrame(results).sort_values("sharpe", ascending=False)
    print(f"\nTested {len(df)} parameter combinations")
    print(f"Positive Sharpe: {(df['sharpe'] > 0).sum()}/{len(df)} ({(df['sharpe'] > 0).mean():.0%})")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")

    print(f"\nTop 5:")
    for _, row in df.head(5).iterrows():
        print(f"  RSI({int(row['rsi_period'])}) OS={int(row['oversold'])} OB={int(row['overbought'])} "
              f"exit={int(row['exit'])} | Sharpe={row['sharpe']:.2f} Ann={row['annual']:+.1%} "
              f"DD={row['max_dd']:.1%} T={int(row['n_trades'])}")

    print(f"\nBottom 3:")
    for _, row in df.tail(3).iterrows():
        print(f"  RSI({int(row['rsi_period'])}) OS={int(row['oversold'])} | "
              f"Sharpe={row['sharpe']:.2f} Ann={row['annual']:+.1%}")

    # Correlation with H-009
    best = df.iloc[0]
    rsi_period = int(best["rsi_period"])
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    signals_rsi = pd.Series(0, index=prices.index)
    position = 0
    for i in range(rsi_period, len(prices)):
        r = rsi.iloc[i]
        if np.isnan(r):
            continue
        if position == 0:
            if r < int(best["oversold"]):
                position = 1
            elif r > int(best["overbought"]):
                position = -1
        elif position == 1:
            if r > int(best["exit"]):
                position = 0
            elif r > int(best["overbought"]):
                position = -1
        elif position == -1:
            if r < (100 - int(best["exit"])):
                position = 0
            elif r < int(best["oversold"]):
                position = 1
        signals_rsi.iloc[i] = position

    ret_rsi = (signals_rsi.shift(1) * prices.pct_change()).dropna()

    signals_ema = generate_signals(prices, 5, 40)
    ret_ema = (signals_ema.shift(1) * prices.pct_change()).dropna()

    common = ret_rsi.index.intersection(ret_ema.index)
    corr = ret_rsi.loc[common].corr(ret_ema.loc[common])
    print(f"\nCorrelation with H-009 (EMA trend): {corr:.3f}")

    return df


def test_bb_squeeze_breakout():
    """
    H-016: Bollinger Band squeeze → breakout strategy.
    When bands contract (squeeze), trade the breakout direction.
    """
    print("\n" + "=" * 80)
    print("H-016: BB Squeeze Breakout (BTC Daily)")
    print("=" * 80)

    df_1h = fetch_and_cache("BTC/USDT", "1h", limit_days=730)
    daily = resample_to_daily(df_1h)
    prices = daily["close"]

    results = []
    for bb_period in [14, 20, 30]:
        for bb_std in [1.5, 2.0, 2.5]:
            for squeeze_pctile in [10, 20, 30]:  # bandwidth percentile threshold
                for hold_bars in [5, 10, 20]:
                    # Compute BB
                    sma = prices.rolling(bb_period).mean()
                    std = prices.rolling(bb_period).std()
                    upper = sma + bb_std * std
                    lower = sma - bb_std * std
                    bandwidth = (upper - lower) / sma

                    # Squeeze detection: bandwidth below Nth percentile of its own history
                    bw_pctile = bandwidth.rolling(100).apply(
                        lambda x: (x.iloc[-1] <= np.percentile(x.iloc[:-1], squeeze_pctile))
                        if len(x) > 1 else 0,
                        raw=False
                    )

                    signals = pd.Series(0, index=prices.index)
                    position = 0
                    bars_held = 0

                    for i in range(bb_period + 100, len(prices)):
                        if position != 0:
                            bars_held += 1
                            if bars_held >= hold_bars:
                                position = 0
                                bars_held = 0
                            signals.iloc[i] = position
                            continue

                        # Check for squeeze (bandwidth was compressed)
                        if pd.isna(bw_pctile.iloc[i - 1]):
                            continue

                        if bw_pctile.iloc[i - 1] == 1:  # was in squeeze
                            if prices.iloc[i] > upper.iloc[i - 1]:
                                position = 1
                                bars_held = 0
                            elif prices.iloc[i] < lower.iloc[i - 1]:
                                position = -1
                                bars_held = 0
                        signals.iloc[i] = position

                    strat_ret = signals.shift(1) * prices.pct_change()
                    strat_ret = strat_ret.dropna()
                    trades = (signals.diff() != 0) & (signals.diff().notna())
                    n_trades = trades.sum()

                    eq = 10000 * (1 + strat_ret).cumprod()
                    s = sharpe_ratio(strat_ret, periods_per_year=365)
                    ann = (eq.iloc[-1] / eq.iloc[0]) ** (365 / len(eq)) - 1
                    dd = ((eq.cummax() - eq) / eq.cummax()).max()

                    results.append({
                        "bb_period": bb_period, "bb_std": bb_std,
                        "squeeze_pctile": squeeze_pctile, "hold_bars": hold_bars,
                        "sharpe": s, "annual": ann, "max_dd": dd,
                        "n_trades": int(n_trades),
                    })

    df = pd.DataFrame(results).sort_values("sharpe", ascending=False)
    print(f"\nTested {len(df)} parameter combinations")
    print(f"Positive Sharpe: {(df['sharpe'] > 0).sum()}/{len(df)} ({(df['sharpe'] > 0).mean():.0%})")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")

    print(f"\nTop 5:")
    for _, row in df.head(5).iterrows():
        print(f"  BB({int(row['bb_period'])},{row['bb_std']:.1f}) squeeze<{int(row['squeeze_pctile'])}%ile "
              f"hold={int(row['hold_bars'])} | Sharpe={row['sharpe']:.2f} Ann={row['annual']:+.1%} "
              f"DD={row['max_dd']:.1%} T={int(row['n_trades'])}")

    return df


def test_multi_timeframe_momentum():
    """
    H-017: Multi-timeframe momentum filter.
    Only trade when weekly AND daily trends agree.
    Weekly: EMA(4) > EMA(12) → bull, Daily: EMA(5) > EMA(20) → entry.
    """
    print("\n" + "=" * 80)
    print("H-017: Multi-Timeframe Momentum Filter (BTC)")
    print("=" * 80)

    df_1h = fetch_and_cache("BTC/USDT", "1h", limit_days=730)
    daily = resample_to_daily(df_1h)
    prices = daily["close"]

    # Create weekly prices
    weekly = prices.resample("W").last().dropna()

    results = []
    for w_fast, w_slow in [(4, 12), (4, 8), (3, 10), (5, 15)]:
        for d_fast, d_slow in [(5, 20), (5, 40), (10, 30), (8, 21)]:
            # Weekly trend
            w_ema_fast = weekly.ewm(span=w_fast, adjust=False).mean()
            w_ema_slow = weekly.ewm(span=w_slow, adjust=False).mean()
            weekly_bull = (w_ema_fast > w_ema_slow).astype(int)
            weekly_bear = (w_ema_fast < w_ema_slow).astype(int)

            # Upsample weekly signal to daily
            weekly_signal = pd.Series(index=prices.index, dtype=float)
            for date in prices.index:
                # Find the most recent weekly date
                w_dates = weekly.index[weekly.index <= date]
                if len(w_dates) > 0:
                    latest_w = w_dates[-1]
                    if latest_w in weekly_bull.index:
                        weekly_signal[date] = 1 if weekly_bull[latest_w] else (-1 if weekly_bear[latest_w] else 0)

            weekly_signal = weekly_signal.fillna(0)

            # Daily signal
            d_ema_fast = prices.ewm(span=d_fast, adjust=False).mean()
            d_ema_slow = prices.ewm(span=d_slow, adjust=False).mean()
            daily_signal = pd.Series(0, index=prices.index)
            daily_signal[d_ema_fast > d_ema_slow] = 1
            daily_signal[d_ema_fast < d_ema_slow] = -1

            # Combined: only trade when weekly and daily agree
            combined = pd.Series(0, index=prices.index)
            combined[(weekly_signal == 1) & (daily_signal == 1)] = 1
            combined[(weekly_signal == -1) & (daily_signal == -1)] = -1

            strat_ret = combined.shift(1) * prices.pct_change()
            strat_ret = strat_ret.dropna()

            eq = 10000 * (1 + strat_ret).cumprod()
            s = sharpe_ratio(strat_ret, periods_per_year=365)
            ann = (eq.iloc[-1] / eq.iloc[0]) ** (365 / len(eq)) - 1
            dd = ((eq.cummax() - eq) / eq.cummax()).max()

            trades = (combined.diff() != 0).sum()

            results.append({
                "w_fast": w_fast, "w_slow": w_slow,
                "d_fast": d_fast, "d_slow": d_slow,
                "sharpe": s, "annual": ann, "max_dd": dd,
                "n_trades": int(trades),
            })

    df = pd.DataFrame(results).sort_values("sharpe", ascending=False)
    print(f"\nTested {len(df)} parameter combinations")
    print(f"Positive Sharpe: {(df['sharpe'] > 0).sum()}/{len(df)} ({(df['sharpe'] > 0).mean():.0%})")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")

    print(f"\nTop 5:")
    for _, row in df.head(5).iterrows():
        print(f"  W({int(row['w_fast'])}/{int(row['w_slow'])}) D({int(row['d_fast'])}/{int(row['d_slow'])}) | "
              f"Sharpe={row['sharpe']:.2f} Ann={row['annual']:+.1%} DD={row['max_dd']:.1%} "
              f"T={int(row['n_trades'])}")

    # Correlation with H-009
    best = df.iloc[0]
    d_ema_fast = prices.ewm(span=int(best["d_fast"]), adjust=False).mean()
    d_ema_slow = prices.ewm(span=int(best["d_slow"]), adjust=False).mean()
    daily_signal = pd.Series(0, index=prices.index)
    daily_signal[d_ema_fast > d_ema_slow] = 1
    daily_signal[d_ema_fast < d_ema_slow] = -1

    ret_mtf = (daily_signal.shift(1) * prices.pct_change()).dropna()

    signals_ema = generate_signals(prices, 5, 40)
    ret_ema = (signals_ema.shift(1) * prices.pct_change()).dropna()
    common = ret_mtf.index.intersection(ret_ema.index)
    corr = ret_mtf.loc[common].corr(ret_ema.loc[common])
    print(f"\nCorrelation with H-009: {corr:.3f}")

    return df


if __name__ == "__main__":
    rsi_results = test_daily_rsi_mean_reversion()
    bb_results = test_bb_squeeze_breakout()
    mtf_results = test_multi_timeframe_momentum()

    print("\n" + "=" * 80)
    print("SUMMARY OF ALL ALTERNATIVE STRATEGIES")
    print("=" * 80)
    print(f"H-015 RSI MR:      Best Sharpe = {rsi_results['sharpe'].max():.2f}, "
          f"Mean = {rsi_results['sharpe'].mean():.3f}, "
          f"Positive = {(rsi_results['sharpe'] > 0).mean():.0%}")
    print(f"H-016 BB Squeeze:  Best Sharpe = {bb_results['sharpe'].max():.2f}, "
          f"Mean = {bb_results['sharpe'].mean():.3f}, "
          f"Positive = {(bb_results['sharpe'] > 0).mean():.0%}")
    print(f"H-017 MTF Trend:   Best Sharpe = {mtf_results['sharpe'].max():.2f}, "
          f"Mean = {mtf_results['sharpe'].mean():.3f}, "
          f"Positive = {(mtf_results['sharpe'] > 0).mean():.0%}")
