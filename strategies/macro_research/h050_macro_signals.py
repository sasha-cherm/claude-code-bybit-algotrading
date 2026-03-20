#!/usr/bin/env python3
"""
H-050: Inter-Market Macro Signals for Crypto Timing

Test whether traditional macro asset returns (S&P 500, Gold, DXY, VIX)
can predict next-day crypto cross-sectional or directional returns.

Hypotheses:
  A) BTC timing: use macro signals to time BTC long/short (improve H-009)
  B) Cross-sectional: use macro signals to tilt cross-sectional factor exposure
  C) Risk-on/risk-off: use VIX/DXY to define regimes for crypto allocation

Data: S&P 500 (SPY), Gold (GLD), DXY (UUP or DX-Y.NYB), VIX (^VIX), US 10Y yield (^TNX)
"""

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return

# ─── 1. Fetch macro data ───
print("=== H-050: Inter-Market Macro Signals Research ===\n")
print("Fetching macro data from Yahoo Finance...")

macro_tickers = {
    'SPY': 'S&P 500 ETF',
    'GLD': 'Gold ETF',
    'UUP': 'USD Index ETF (DXY proxy)',
    '^VIX': 'VIX Index',
    '^TNX': 'US 10Y Yield',
}

start_date = '2024-03-01'
end_date = '2026-03-20'

macro_data = {}
for ticker, name in macro_tickers.items():
    try:
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if len(df) > 0:
            macro_data[ticker] = df['Close'].squeeze()
            print(f"  {ticker} ({name}): {len(df)} bars, {df.index[0].date()} to {df.index[-1].date()}")
        else:
            print(f"  {ticker}: NO DATA")
    except Exception as e:
        print(f"  {ticker}: Error — {e}")

# ─── 2. Fetch crypto data ───
print("\nFetching crypto data...")
ASSETS = ['BTC', 'ETH', 'SOL', 'SUI', 'XRP', 'DOGE', 'AVAX', 'LINK', 'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM']
crypto_prices = {}
for asset in ASSETS:
    df = fetch_and_cache(f'{asset}/USDT', timeframe='1d', limit_days=740)
    crypto_prices[asset] = df['close']

crypto_df = pd.DataFrame(crypto_prices)
crypto_returns = crypto_df.pct_change()
btc_returns = crypto_returns['BTC']
print(f"  Crypto data: {len(crypto_df)} bars, {crypto_df.index[0]} to {crypto_df.index[-1]}")

# ─── 3. Align macro and crypto data ───
print("\nAligning data...")
macro_df = pd.DataFrame(macro_data)
macro_df.index = pd.to_datetime(macro_df.index).tz_localize(None).normalize()

# Strip timezone from crypto data
crypto_df.index = pd.to_datetime(crypto_df.index).tz_localize(None).normalize()
crypto_returns = crypto_df.pct_change()  # recompute after tz strip
btc_returns = crypto_returns['BTC']

# Macro data is M-F only; crypto is 24/7. Forward-fill macro on weekends
all_dates = crypto_df.index
macro_aligned = macro_df.reindex(all_dates, method='ffill')
macro_returns = macro_aligned.pct_change()

# Drop NaN
valid = macro_returns.dropna().index.intersection(crypto_returns.dropna(how='all').index)
macro_ret = macro_returns.loc[valid]
crypto_ret = crypto_returns.loc[valid]
btc_ret = btc_returns.loc[valid]
print(f"  Aligned: {len(valid)} trading days")

# ─── 4. Correlation analysis ───
print("\n=== Correlation: Macro Returns → Same-Day Crypto Returns ===")
for ticker in macro_ret.columns:
    corr = macro_ret[ticker].corr(btc_ret)
    print(f"  {ticker:6s} vs BTC: {corr:+.4f}")

# Lagged correlation (macro_t → crypto_t+1)
print("\n=== Lagged Correlation: Macro_t → BTC_t+1 ===")
btc_ret_fwd = btc_ret.shift(-1)
for ticker in macro_ret.columns:
    corr = macro_ret[ticker].corr(btc_ret_fwd)
    print(f"  {ticker:6s} → BTC_t+1: {corr:+.4f}")

# Multi-day signals
print("\n=== Multi-Day Lagged Correlation: Macro(sum_Nd) → BTC(sum_next_Nd) ===")
for N in [3, 5, 10, 20]:
    print(f"\n  N={N}d:")
    macro_Nd = macro_ret.rolling(N).sum()
    btc_Nd_fwd = btc_ret.rolling(N).sum().shift(-N)
    for ticker in macro_ret.columns:
        corr = macro_Nd[ticker].corr(btc_Nd_fwd)
        print(f"    {ticker:6s} → BTC({N}d): {corr:+.4f}")

# ─── 5. Test directional BTC timing strategies ───
print("\n\n=== Strategy Tests: Macro Signal → BTC Timing ===")

results = []

for ticker in macro_ret.columns:
    for lookback in [1, 3, 5, 10, 20]:
        for direction in ['momentum', 'contrarian']:
            # Signal: sign of N-day macro return (lagged by 1 day)
            macro_signal = macro_ret[ticker].rolling(lookback).sum().shift(1)  # lag by 1 day

            if direction == 'contrarian':
                macro_signal = -macro_signal

            # Strategy: long BTC when signal > 0, short when signal < 0
            position = np.sign(macro_signal)
            strat_ret = position * btc_ret
            strat_ret = strat_ret.dropna()

            if len(strat_ret) < 100:
                continue

            sr = sharpe_ratio(strat_ret)
            ar = annual_return(strat_ret)
            dd = max_drawdown(strat_ret)

            results.append({
                'macro': ticker,
                'lookback': lookback,
                'direction': direction,
                'sharpe': sr,
                'annual_ret': ar,
                'max_dd': dd,
                'n_days': len(strat_ret)
            })

results_df = pd.DataFrame(results)
print(f"\n{len(results_df)} parameter sets tested")

# Summary stats
positive = (results_df['sharpe'] > 0).sum()
total = len(results_df)
print(f"Positive Sharpe: {positive}/{total} ({100*positive/total:.1f}%)")
print(f"Mean Sharpe: {results_df['sharpe'].mean():.3f}")
print(f"Best Sharpe: {results_df['sharpe'].max():.3f}")

# Top 10 by Sharpe
print("\n=== Top 10 Strategies ===")
top10 = results_df.nlargest(10, 'sharpe')
for _, row in top10.iterrows():
    print(f"  {row['macro']:6s} LB{row['lookback']:2d} {row['direction']:11s} — "
          f"Sharpe {row['sharpe']:+.3f}, Ann {row['annual_ret']*100:+.1f}%, DD {row['max_dd']*100:.1f}%")

# ─── 6. Test VIX level as regime filter ───
print("\n\n=== VIX Level as Regime Filter for BTC ===")
if '^VIX' in macro_aligned.columns:
    vix = macro_aligned['^VIX']

    for vix_thresh in [15, 20, 25, 30]:
        # Long BTC when VIX < threshold (risk-on), short when VIX > threshold
        vix_signal = np.where(vix.shift(1) < vix_thresh, 1, -1)
        vix_strat = pd.Series(vix_signal, index=vix.index) * btc_ret
        vix_strat = vix_strat.dropna()
        vix_strat = vix_strat.loc[valid]
        vix_strat = vix_strat.dropna()

        if len(vix_strat) > 100:
            sr = sharpe_ratio(vix_strat)
            ar = annual_return(vix_strat)
            dd = max_drawdown(vix_strat)
            frac_long = (vix.shift(1).loc[valid] < vix_thresh).mean()
            print(f"  VIX < {vix_thresh}: Sharpe {sr:+.3f}, Ann {ar*100:+.1f}%, DD {dd*100:.1f}%, "
                  f"Long {frac_long*100:.0f}% of time")

    # VIX percentile-based
    print("\n  VIX Percentile (expanding):")
    vix_pctl = vix.expanding(min_periods=30).apply(lambda x: (x.iloc[-1] - x.min()) / (x.max() - x.min()) if x.max() > x.min() else 0.5)
    for pctl in [0.3, 0.5, 0.7]:
        signal = np.where(vix_pctl.shift(1) < pctl, 1, -1)
        strat = pd.Series(signal, index=vix.index) * btc_ret
        strat = strat.loc[valid].dropna()
        if len(strat) > 100:
            sr = sharpe_ratio(strat)
            print(f"    Long when VIX pctl < {pctl:.1f}: Sharpe {sr:+.3f}")

# ─── 7. Cross-sectional macro signal: rotate within crypto ───
print("\n\n=== Cross-Sectional: Macro → Crypto Beta Tilt ===")
print("Testing: when macro signal positive, tilt to high-beta assets; when negative, tilt to low-beta")

# Compute rolling beta of each asset to BTC
window_beta = 60
betas = {}
for asset in ASSETS:
    if asset == 'BTC':
        betas[asset] = pd.Series(1.0, index=valid)
        continue
    roll_cov = crypto_ret[asset].loc[valid].rolling(window_beta).cov(btc_ret.loc[valid])
    roll_var = btc_ret.loc[valid].rolling(window_beta).var()
    betas[asset] = roll_cov / roll_var

betas_df = pd.DataFrame(betas)

# For each macro signal, test XS strategy: high-beta long when signal positive, low-beta long when negative
for ticker in ['SPY', '^VIX']:
    for lb in [5, 10, 20]:
        macro_sig = macro_ret[ticker].rolling(lb).sum().shift(1).loc[valid]

        # On each day, rank assets by beta.
        # When SPY positive: long high-beta, short low-beta (risk-on)
        # When SPY negative: long low-beta, short high-beta (risk-off)
        daily_returns = []
        for date in valid[window_beta + lb:]:
            if pd.isna(macro_sig.loc[date]):
                continue

            beta_row = betas_df.loc[date]
            if beta_row.isna().sum() > 3:
                continue

            # Rank by beta
            ranks = beta_row.rank()
            n_assets = len(ASSETS)
            N = 4  # top/bottom 4

            long_mask = ranks > (n_assets - N)
            short_mask = ranks <= N

            if ticker == '^VIX':
                # VIX up → risk-off → long low-beta, short high-beta (reverse)
                if macro_sig.loc[date] > 0:
                    long_mask, short_mask = short_mask, long_mask
            else:
                # SPY up → risk-on → long high-beta, short low-beta
                if macro_sig.loc[date] < 0:
                    long_mask, short_mask = short_mask, long_mask

            ret_row = crypto_ret.loc[date]
            port_ret = ret_row[long_mask].mean() - ret_row[short_mask].mean()
            daily_returns.append(port_ret)

        if len(daily_returns) > 100:
            daily_returns = pd.Series(daily_returns)
            sr = sharpe_ratio(daily_returns)
            ar = annual_return(daily_returns)
            dd = max_drawdown(daily_returns)
            print(f"  {ticker:6s} LB{lb:2d} → Beta Tilt — Sharpe {sr:+.3f}, Ann {ar*100:+.1f}%, DD {dd*100:.1f}%")

# ─── 8. Combined macro regime signal ───
print("\n\n=== Combined Macro Regime → BTC Timing ===")
# PCA-like: z-score each macro signal, combine
macro_z = macro_ret.rolling(20).apply(lambda x: (x.iloc[-1] - x.mean()) / max(x.std(), 1e-8))

# Risk-on composite: +SPY, +GLD, -UUP, -VIX, -TNX
weights = {'SPY': 1.0, 'GLD': 0.5, 'UUP': -1.0, '^VIX': -1.0, '^TNX': -0.5}
risk_on = sum(macro_z[t] * w for t, w in weights.items() if t in macro_z.columns)
risk_on = risk_on / len(weights)

for thresh in [0, 0.3, 0.5]:
    signal = np.where(risk_on.shift(1) > thresh, 1, np.where(risk_on.shift(1) < -thresh, -1, 0))
    strat = pd.Series(signal, index=risk_on.index) * btc_ret
    strat = strat.loc[valid].dropna()
    strat = strat[strat != 0]  # remove flat periods

    if len(strat) > 50:
        sr = sharpe_ratio(strat)
        ar = annual_return(strat)
        dd = max_drawdown(strat)
        frac = len(strat) / len(valid)
        print(f"  Thresh {thresh:.1f}: Sharpe {sr:+.3f}, Ann {ar*100:+.1f}%, DD {dd*100:.1f}%, "
              f"Active {frac*100:.0f}% of days ({len(strat)} days)")

# ─── 9. Walk-forward validation of best strategies ───
print("\n\n=== Walk-Forward Validation (Top Strategies) ===")

# Test top 3 single-macro strategies
top3 = results_df.nlargest(3, 'sharpe')
for _, row in top3.iterrows():
    ticker = row['macro']
    lb = int(row['lookback'])
    dirn = row['direction']

    macro_sig = macro_ret[ticker].rolling(lb).sum().shift(1)
    if dirn == 'contrarian':
        macro_sig = -macro_sig
    position = np.sign(macro_sig)
    strat_ret = (position * btc_ret).dropna()

    # Walk-forward: 180d train, 90d test, 4 folds
    n = len(strat_ret)
    train_days = 180
    test_days = 90
    fold_size = train_days + test_days

    n_folds = min(4, (n - train_days) // test_days)
    if n_folds < 3:
        print(f"  {ticker} LB{lb} {dirn}: Too few data for WF")
        continue

    oos_sharpes = []
    for fold in range(n_folds):
        start = fold * test_days
        train_end = start + train_days
        test_end = train_end + test_days

        if test_end > n:
            break

        train_data = strat_ret.iloc[start:train_end]
        test_data = strat_ret.iloc[train_end:test_end]

        train_sr = sharpe_ratio(train_data)
        test_sr = sharpe_ratio(test_data)
        oos_sharpes.append(test_sr)

    pos_folds = sum(1 for s in oos_sharpes if s > 0)
    mean_oos = np.mean(oos_sharpes) if oos_sharpes else 0

    print(f"  {ticker:6s} LB{lb:2d} {dirn:11s}: WF {pos_folds}/{len(oos_sharpes)} positive, "
          f"mean OOS {mean_oos:+.3f}, folds: {[f'{s:+.2f}' for s in oos_sharpes]}")

# ─── 10. Summary ───
print("\n\n=== SUMMARY ===")
print(f"Total param sets: {len(results_df)}")
print(f"Positive Sharpe: {positive}/{total} ({100*positive/total:.1f}%)")
print(f"Mean Sharpe: {results_df['sharpe'].mean():.3f}")
print(f"Best single: {top10.iloc[0]['macro']} LB{int(top10.iloc[0]['lookback'])} "
      f"{top10.iloc[0]['direction']} — Sharpe {top10.iloc[0]['sharpe']:+.3f}")
print("\nConclusion: See above. If <50% positive or WF fails → REJECT.")
