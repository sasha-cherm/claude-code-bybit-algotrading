#!/usr/bin/env python3
"""
Session 177 Batch 2: Multi-timeframe, adaptive, and SOL TS strategies.
H-564 through H-579: 16 hypotheses.
Focus: BTC 4h patterns, adaptive trend, SOL TS, multi-timeframe.
"""
import sys, json, warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings('ignore')

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

def load_hourly(symbol='BTC'):
    f = DATA_DIR / f'{symbol}_USDT_1h.parquet'
    return pd.read_parquet(f)

def resample_4h(df_1h):
    return df_1h.resample('4h').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna()

def compute_daily(df_1h):
    return df_1h.resample('1D').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna()

def backtest_ts(prices, signal, fee_bps=10, freq='daily'):
    """Backtest a TS signal. freq: 'daily' or 'hourly' or '4h'."""
    common = prices.index.intersection(signal.index)
    prices = prices.loc[common]
    signal = signal.loc[common]

    ret = prices.pct_change().fillna(0)
    strat_ret = signal.shift(1) * ret
    strat_ret = strat_ret.fillna(0)

    signal_change = signal.diff().abs().fillna(0)
    strat_ret = strat_ret - signal_change * fee_bps / 10000

    equity = 10000 * (1 + strat_ret).cumprod()

    ppy = {'daily': 365, 'hourly': 8760, '4h': 2190}[freq]
    n = len(equity)
    years = n / ppy
    total_ret = equity.iloc[-1] / equity.iloc[0] - 1
    ann_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
    sharpe = strat_ret.mean() / strat_ret.std() * np.sqrt(ppy) if strat_ret.std() > 0 else 0
    peak = equity.cummax()
    dd = abs(((equity - peak) / peak).min())
    n_trades = int(signal_change.sum())
    win = (strat_ret > 0).sum()
    loss = (strat_ret < 0).sum()
    wr = win / (win + loss) if (win + loss) > 0 else 0

    return {
        'equity': equity,
        'sharpe': round(sharpe, 3),
        'ann_ret': round(ann_ret, 4),
        'max_dd': round(dd, 4),
        'n_trades': n_trades,
        'win_rate': round(wr, 3),
        'n_bars': n
    }

def walk_forward_ts(prices, signal_fn, n_folds=8, freq='daily'):
    """Walk-forward for TS strategy. Returns list of fold Sharpes."""
    ppy = {'daily': 365, 'hourly': 8760, '4h': 2190}[freq]
    n = len(prices)
    fold_size = n // n_folds
    results = []

    for i in range(n_folds):
        test_start = i * fold_size
        test_end = min((i + 1) * fold_size, n)
        if test_start < fold_size:
            continue  # skip first fold (no training)

        test_prices = prices.iloc[test_start:test_end]
        if len(test_prices) < 30:
            continue

        # Generate signal using data up to test period
        full_sig = signal_fn(prices.iloc[:test_end])
        test_sig = full_sig.iloc[test_start:test_end]

        ret = test_prices.pct_change().fillna(0)
        strat_ret = test_sig.shift(1) * ret
        strat_ret = strat_ret.fillna(0)
        sig_change = test_sig.diff().abs().fillna(0)
        strat_ret = strat_ret - sig_change * 10 / 10000

        sh = strat_ret.mean() / strat_ret.std() * np.sqrt(ppy) if strat_ret.std() > 0 else 0
        results.append(round(sh, 3))

    return results


# ============================================================
# SIGNAL GENERATORS — BATCH 2
# ============================================================

def adaptive_ema_signal(prices_daily, fast_range=(5, 15), slow_range=(20, 60), vol_lookback=20):
    """H-564: Adaptive EMA trend — shorter EMAs in low vol, longer in high vol."""
    close = prices_daily['close']
    ret = close.pct_change()
    vol = ret.rolling(vol_lookback).std()
    vol_rank = vol.rolling(365).rank(pct=True)

    signal = pd.Series(0, index=close.index)
    for i in range(max(slow_range[1], 365) + 1, len(close)):
        vr = vol_rank.iloc[i-1]
        if np.isnan(vr):
            continue
        # Low vol → shorter EMAs (more responsive)
        fast_p = int(fast_range[0] + (fast_range[1] - fast_range[0]) * vr)
        slow_p = int(slow_range[0] + (slow_range[1] - slow_range[0]) * vr)

        ema_fast = close.iloc[max(0,i-slow_p*3):i].ewm(span=fast_p).mean().iloc[-1]
        ema_slow = close.iloc[max(0,i-slow_p*3):i].ewm(span=slow_p).mean().iloc[-1]

        signal.iloc[i] = 1 if ema_fast > ema_slow else -1

    return signal


def btc_4h_ema_trend(prices_4h, fast=5, slow=20):
    """H-565: BTC 4h EMA crossover trend following."""
    close = prices_4h['close']
    ema_f = close.ewm(span=fast).mean()
    ema_s = close.ewm(span=slow).mean()

    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        signal.iloc[i] = 1 if ema_f.iloc[i-1] > ema_s.iloc[i-1] else -1

    return signal


def btc_4h_rsi_momentum(prices_4h, period=14, threshold=50):
    """H-566: BTC 4h RSI momentum — long when RSI > threshold, short below."""
    close = prices_4h['close']
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        if not np.isnan(rsi.iloc[i-1]):
            signal.iloc[i] = 1 if rsi.iloc[i-1] > threshold else -1

    return signal


def btc_4h_vwap_reversion(prices_4h, lookback=30, z_entry=1.5):
    """H-567: BTC 4h VWAP deviation mean-reversion."""
    close = prices_4h['close']
    volume = prices_4h['volume']

    vwap = (close * volume).rolling(lookback).sum() / volume.rolling(lookback).sum()
    std = close.rolling(lookback).std()
    z = (close - vwap) / std.replace(0, np.nan)

    signal = pd.Series(0, index=close.index)
    pos = 0
    for i in range(1, len(close)):
        if np.isnan(z.iloc[i-1]):
            continue
        if z.iloc[i-1] < -z_entry:
            pos = 1
        elif z.iloc[i-1] > z_entry:
            pos = -1
        elif pos == 1 and z.iloc[i-1] > 0:
            pos = 0
        elif pos == -1 and z.iloc[i-1] < 0:
            pos = 0
        signal.iloc[i] = pos

    return signal


def btc_4h_momentum_filter(prices_4h, mom_lookback=48, vol_lookback=48):
    """H-568: BTC 4h momentum + vol filter — only trade when vol is expanding."""
    close = prices_4h['close']
    ret = close.pct_change()
    mom = close.pct_change(mom_lookback)
    vol = ret.rolling(vol_lookback).std()
    vol_ma = vol.rolling(vol_lookback * 2).mean()

    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        if np.isnan(mom.iloc[i-1]) or np.isnan(vol_ma.iloc[i-1]):
            continue
        if vol.iloc[i-1] > vol_ma.iloc[i-1]:
            signal.iloc[i] = 1 if mom.iloc[i-1] > 0 else -1
        # else: flat (no signal in low vol)

    return signal


def sol_ema_trend(sol_daily, fast=10, slow=30):
    """H-569: SOL daily EMA trend following."""
    close = sol_daily['close']
    ema_f = close.ewm(span=fast).mean()
    ema_s = close.ewm(span=slow).mean()

    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        signal.iloc[i] = 1 if ema_f.iloc[i-1] > ema_s.iloc[i-1] else -1

    return signal


def sol_keltner_breakout(sol_daily, period=20, atr_mult=1.5):
    """H-570: SOL Keltner channel breakout."""
    close = sol_daily['close']
    high = sol_daily['high']
    low = sol_daily['low']

    ema = close.ewm(span=period).mean()
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()

    upper = ema + atr_mult * atr
    lower = ema - atr_mult * atr

    signal = pd.Series(0, index=close.index)
    pos = 0
    for i in range(1, len(close)):
        if close.iloc[i-1] > upper.iloc[i-1]:
            pos = 1
        elif close.iloc[i-1] < lower.iloc[i-1]:
            pos = -1
        signal.iloc[i] = pos

    return signal


def sol_intraday_momentum(sol_1h, threshold=0.0):
    """H-571: SOL first 6h session momentum."""
    df = sol_1h.copy()
    df['date'] = df.index.date
    df['hour'] = df.index.hour

    daily_signals = {}
    for date, group in df.groupby('date'):
        first_6h = group[group['hour'] < 6]
        if len(first_6h) >= 4:
            ret_6h = first_6h['close'].iloc[-1] / first_6h['open'].iloc[0] - 1
            daily_signals[date] = 1 if ret_6h > threshold else (-1 if ret_6h < -threshold else 0)

    sig = pd.Series(daily_signals)
    sig.index = pd.to_datetime(sig.index, utc=True)
    return sig


def multi_tf_btc_signal(btc_1h, daily_lookback=20, hourly_lookback=24):
    """H-572: Multi-timeframe BTC — daily trend filter + hourly momentum entry."""
    daily = btc_1h.resample('1D').agg({'close': 'last'}).dropna()
    daily_ema = daily['close'].ewm(span=daily_lookback).mean()
    daily_trend = (daily['close'] > daily_ema).astype(int).replace(0, -1)

    # Map daily trend to hourly
    btc_close = btc_1h['close']
    daily_trend_hourly = daily_trend.reindex(btc_close.index, method='ffill')

    # Hourly momentum
    hourly_mom = btc_close.pct_change(hourly_lookback)
    hourly_dir = hourly_mom.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))

    # Only trade when hourly and daily agree
    signal = pd.Series(0, index=btc_close.index)
    for i in range(1, len(btc_close)):
        d = daily_trend_hourly.iloc[i-1] if not np.isnan(daily_trend_hourly.iloc[i-1]) else 0
        h = hourly_dir.iloc[i-1] if not np.isnan(hourly_dir.iloc[i-1]) else 0
        if d == h and d != 0:
            signal.iloc[i] = int(d)
        # else: flat (disagreement → no trade)

    return signal


def btc_daily_trend_vol_target(btc_daily, ema_fast=10, ema_slow=40, target_vol=0.15):
    """H-573: BTC daily trend + vol targeting (like H-009 with different params)."""
    close = btc_daily['close']
    ema_f = close.ewm(span=ema_fast).mean()
    ema_s = close.ewm(span=ema_slow).mean()

    ret = close.pct_change()
    vol = ret.rolling(30).std() * np.sqrt(365)

    signal = pd.Series(0.0, index=close.index)
    for i in range(1, len(close)):
        direction = 1 if ema_f.iloc[i-1] > ema_s.iloc[i-1] else -1
        if not np.isnan(vol.iloc[i-1]) and vol.iloc[i-1] > 0:
            sizing = min(target_vol / vol.iloc[i-1], 2.0)
        else:
            sizing = 1.0
        signal.iloc[i] = direction * sizing

    # Discretize to -2, -1, 0, 1, 2 for simplicity
    signal = signal.round().clip(-2, 2)
    return signal


def btc_adx_trend(btc_daily, period=14, adx_threshold=25):
    """H-574: BTC ADX trend strength — only trade in strong trends (ADX > 25)."""
    close = btc_daily['close']
    high = btc_daily['high']
    low = btc_daily['low']

    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(span=period).mean()

    # +DM / -DM
    up = high - high.shift(1)
    dn = low.shift(1) - low
    plus_dm = ((up > dn) & (up > 0)).astype(float) * up
    minus_dm = ((dn > up) & (dn > 0)).astype(float) * dn

    plus_di = 100 * plus_dm.ewm(span=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(span=period).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(span=period).mean()

    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        if np.isnan(adx.iloc[i-1]):
            continue
        if adx.iloc[i-1] > adx_threshold:
            signal.iloc[i] = 1 if plus_di.iloc[i-1] > minus_di.iloc[i-1] else -1

    return signal


def btc_volume_trend(btc_daily, price_lookback=20, vol_lookback=20):
    """H-575: BTC price momentum confirmed by volume trend."""
    close = btc_daily['close']
    volume = btc_daily['volume']

    price_mom = close.pct_change(price_lookback)
    vol_trend = volume.rolling(vol_lookback).mean() / volume.rolling(vol_lookback * 2).mean() - 1

    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        if np.isnan(price_mom.iloc[i-1]) or np.isnan(vol_trend.iloc[i-1]):
            continue
        pm = price_mom.iloc[i-1]
        vt = vol_trend.iloc[i-1]

        if pm > 0 and vt > 0:
            signal.iloc[i] = 1  # price up + volume expanding → strong long
        elif pm < 0 and vt > 0:
            signal.iloc[i] = -1  # price down + volume expanding → strong short
        # Price move on declining volume → ignore (likely weak)

    return signal


def btc_supertrend(btc_daily, period=10, mult=3.0):
    """H-576: BTC SuperTrend indicator."""
    close = btc_daily['close']
    high = btc_daily['high']
    low = btc_daily['low']

    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()

    hl2 = (high + low) / 2
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr

    supertrend = pd.Series(0.0, index=close.index)
    direction = pd.Series(1, index=close.index)

    for i in range(1, len(close)):
        if np.isnan(upper.iloc[i]) or np.isnan(lower.iloc[i]):
            supertrend.iloc[i] = supertrend.iloc[i-1]
            direction.iloc[i] = direction.iloc[i-1]
            continue

        # Adjust bands
        if lower.iloc[i] > lower.iloc[i-1] or close.iloc[i-1] < lower.iloc[i-1]:
            pass
        else:
            lower.iloc[i] = lower.iloc[i-1]

        if upper.iloc[i] < upper.iloc[i-1] or close.iloc[i-1] > upper.iloc[i-1]:
            pass
        else:
            upper.iloc[i] = upper.iloc[i-1]

        if direction.iloc[i-1] == 1:
            if close.iloc[i] < lower.iloc[i]:
                direction.iloc[i] = -1
                supertrend.iloc[i] = upper.iloc[i]
            else:
                direction.iloc[i] = 1
                supertrend.iloc[i] = lower.iloc[i]
        else:
            if close.iloc[i] > upper.iloc[i]:
                direction.iloc[i] = 1
                supertrend.iloc[i] = lower.iloc[i]
            else:
                direction.iloc[i] = -1
                supertrend.iloc[i] = upper.iloc[i]

    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        signal.iloc[i] = int(direction.iloc[i-1])

    return signal


def btc_heikin_ashi_trend(btc_daily, n_confirm=3):
    """H-577: BTC Heikin-Ashi candle trend confirmation."""
    o = btc_daily['open']
    h = btc_daily['high']
    l = btc_daily['low']
    c = btc_daily['close']

    ha_close = (o + h + l + c) / 4
    ha_open = pd.Series(0.0, index=o.index)
    ha_open.iloc[0] = (o.iloc[0] + c.iloc[0]) / 2
    for i in range(1, len(o)):
        ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2

    ha_high = pd.concat([h, ha_open, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([l, ha_open, ha_close], axis=1).min(axis=1)

    ha_bullish = (ha_close > ha_open).astype(int)

    # Count consecutive bullish/bearish candles
    signal = pd.Series(0, index=c.index)
    for i in range(n_confirm, len(c)):
        bull_count = sum(ha_bullish.iloc[i-n_confirm:i])
        if bull_count == n_confirm:
            signal.iloc[i] = 1
        elif bull_count == 0:
            signal.iloc[i] = -1

    return signal


def btc_ichimoku_signal(btc_daily, tenkan=9, kijun=26, senkou_b=52):
    """H-578: BTC Ichimoku Cloud signal."""
    close = btc_daily['close']
    high = btc_daily['high']
    low = btc_daily['low']

    tenkan_sen = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
    kijun_sen = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2
    senkou_a = (tenkan_sen + kijun_sen) / 2
    senkou_b_line = (high.rolling(senkou_b).max() + low.rolling(senkou_b).min()) / 2

    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        above_cloud = close.iloc[i-1] > max(senkou_a.iloc[i-1], senkou_b_line.iloc[i-1]) if not (np.isnan(senkou_a.iloc[i-1]) or np.isnan(senkou_b_line.iloc[i-1])) else False
        below_cloud = close.iloc[i-1] < min(senkou_a.iloc[i-1], senkou_b_line.iloc[i-1]) if not (np.isnan(senkou_a.iloc[i-1]) or np.isnan(senkou_b_line.iloc[i-1])) else False
        tk_cross = tenkan_sen.iloc[i-1] > kijun_sen.iloc[i-1] if not (np.isnan(tenkan_sen.iloc[i-1]) or np.isnan(kijun_sen.iloc[i-1])) else False

        if above_cloud and tk_cross:
            signal.iloc[i] = 1
        elif below_cloud and not tk_cross:
            signal.iloc[i] = -1

    return signal


def btc_mean_reversion_daily(btc_daily, lookback=10, z_entry=2.0):
    """H-579: BTC daily mean-reversion (z-score of close vs MA)."""
    close = btc_daily['close']
    ma = close.rolling(lookback).mean()
    std = close.rolling(lookback).std()
    z = (close - ma) / std.replace(0, np.nan)

    signal = pd.Series(0, index=close.index)
    pos = 0
    for i in range(1, len(close)):
        if np.isnan(z.iloc[i-1]):
            continue
        if z.iloc[i-1] < -z_entry:
            pos = 1
        elif z.iloc[i-1] > z_entry:
            pos = -1
        elif pos == 1 and z.iloc[i-1] > 0:
            pos = 0
        elif pos == -1 and z.iloc[i-1] < 0:
            pos = 0
        signal.iloc[i] = pos

    return signal


# ============================================================
# MAIN
# ============================================================

def run_batch():
    print("=" * 80)
    print("SESSION 177 BATCH 2: Multi-TF, Adaptive, SOL TS Strategies")
    print("=" * 80)

    btc_1h = load_hourly('BTC')
    eth_1h = load_hourly('ETH')
    sol_1h = load_hourly('SOL')

    btc_daily = compute_daily(btc_1h)
    eth_daily = compute_daily(eth_1h)
    sol_daily = compute_daily(sol_1h)
    btc_4h = resample_4h(btc_1h)

    print(f"BTC daily: {len(btc_daily)}, 4h: {len(btc_4h)}")
    print(f"SOL daily: {len(sol_daily)}")

    results = {}

    strategies = [
        ('H-564', 'BTC Adaptive EMA', lambda: adaptive_ema_signal(btc_daily),
         btc_daily['close'], 'daily',
         [((5,10),(20,40),lb) for lb in [15,20,30]] + [((5,15),(20,60),lb) for lb in [15,20,30]]),

        ('H-565', 'BTC 4h EMA Trend', lambda: btc_4h_ema_trend(btc_4h),
         btc_4h['close'], '4h',
         [(f, s) for f in [3,5,8,10] for s in [15,20,25,30,40] if f < s]),

        ('H-566', 'BTC 4h RSI Momentum', lambda: btc_4h_rsi_momentum(btc_4h),
         btc_4h['close'], '4h',
         [(p, t) for p in [7,10,14,21] for t in [45,50,55]]),

        ('H-567', 'BTC 4h VWAP Reversion', lambda: btc_4h_vwap_reversion(btc_4h),
         btc_4h['close'], '4h',
         [(lb, ze) for lb in [15,20,30,50] for ze in [1.0,1.5,2.0,2.5]]),

        ('H-568', 'BTC 4h Mom+Vol Filter', lambda: btc_4h_momentum_filter(btc_4h),
         btc_4h['close'], '4h',
         [(m, v) for m in [24,48,72,96] for v in [24,48,72]]),

        ('H-569', 'SOL Daily EMA Trend', lambda: sol_ema_trend(sol_daily),
         sol_daily['close'], 'daily',
         [(f, s) for f in [5,10,15,20] for s in [20,30,40,50,60] if f < s]),

        ('H-570', 'SOL Keltner Breakout', lambda: sol_keltner_breakout(sol_daily),
         sol_daily['close'], 'daily',
         [(p, m) for p in [10,15,20,25,30] for m in [1.0,1.5,2.0,2.5]]),

        ('H-571', 'SOL Session Momentum', lambda: sol_intraday_momentum(sol_1h),
         sol_daily['close'], 'daily',
         [(t,) for t in [0, 0.002, 0.005, 0.008, 0.01, 0.015, 0.02, 0.025]]),

        ('H-573', 'BTC Trend+VolTarget', lambda: btc_daily_trend_vol_target(btc_daily),
         btc_daily['close'], 'daily',
         [(f, s) for f in [5,10,15] for s in [20,30,40,50] if f < s]),

        ('H-574', 'BTC ADX Trend', lambda: btc_adx_trend(btc_daily),
         btc_daily['close'], 'daily',
         [(p, t) for p in [7,10,14,21] for t in [20,25,30,35]]),

        ('H-575', 'BTC Vol-Confirmed Mom', lambda: btc_volume_trend(btc_daily),
         btc_daily['close'], 'daily',
         [(pl, vl) for pl in [10,15,20,30] for vl in [10,15,20,30]]),

        ('H-576', 'BTC SuperTrend', lambda: btc_supertrend(btc_daily),
         btc_daily['close'], 'daily',
         [(p, m) for p in [7,10,14,20] for m in [2.0,2.5,3.0,3.5]]),

        ('H-577', 'BTC Heikin-Ashi', lambda: btc_heikin_ashi_trend(btc_daily),
         btc_daily['close'], 'daily',
         [(n,) for n in [2,3,4,5,6,7]]),

        ('H-578', 'BTC Ichimoku', lambda: btc_ichimoku_signal(btc_daily),
         btc_daily['close'], 'daily',
         [(t, k, s) for t in [7,9,12] for k in [20,26,33] for s in [40,52,65] if t < k < s]),

        ('H-579', 'BTC Daily Mean Rev', lambda: btc_mean_reversion_daily(btc_daily),
         btc_daily['close'], 'daily',
         [(lb, ze) for lb in [5,10,15,20,30] for ze in [1.5,2.0,2.5,3.0]]),
    ]

    # H-572 needs special handling (hourly)
    print("\n--- H-572: BTC Multi-Timeframe ---")
    sig = multi_tf_btc_signal(btc_1h)
    btc_1h_close = btc_1h['close']
    bt = backtest_ts(btc_1h_close, sig, freq='hourly')
    results['H-572'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}")

    pos = 0
    total = 0
    for dl in [10, 15, 20, 30]:
        for hl in [12, 24, 48]:
            s = multi_tf_btc_signal(btc_1h, daily_lookback=dl, hourly_lookback=hl)
            b = backtest_ts(btc_1h_close, s, freq='hourly')
            if b['sharpe'] > 0: pos += 1
            total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-572']['param_robust'] = f"{pos}/{total}"

    for hyp_id, name, default_sig_fn, prices, freq, param_grid in strategies:
        print(f"\n--- {hyp_id}: {name} ---")

        sig = default_sig_fn()
        bt = backtest_ts(prices, sig, freq=freq)
        results[hyp_id] = bt
        print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

        # Param robustness
        pos = 0
        total = 0
        for params in param_grid:
            if not isinstance(params, tuple):
                params = (params,)
            try:
                # Reconstruct signal with different params
                if hyp_id == 'H-564':
                    s = adaptive_ema_signal(btc_daily, fast_range=params[0], slow_range=params[1], vol_lookback=params[2])
                elif hyp_id == 'H-565':
                    s = btc_4h_ema_trend(btc_4h, fast=params[0], slow=params[1])
                elif hyp_id == 'H-566':
                    s = btc_4h_rsi_momentum(btc_4h, period=params[0], threshold=params[1])
                elif hyp_id == 'H-567':
                    s = btc_4h_vwap_reversion(btc_4h, lookback=params[0], z_entry=params[1])
                elif hyp_id == 'H-568':
                    s = btc_4h_momentum_filter(btc_4h, mom_lookback=params[0], vol_lookback=params[1])
                elif hyp_id == 'H-569':
                    s = sol_ema_trend(sol_daily, fast=params[0], slow=params[1])
                elif hyp_id == 'H-570':
                    s = sol_keltner_breakout(sol_daily, period=params[0], atr_mult=params[1])
                elif hyp_id == 'H-571':
                    s = sol_intraday_momentum(sol_1h, threshold=params[0])
                elif hyp_id == 'H-573':
                    s = btc_daily_trend_vol_target(btc_daily, ema_fast=params[0], ema_slow=params[1])
                elif hyp_id == 'H-574':
                    s = btc_adx_trend(btc_daily, period=params[0], adx_threshold=params[1])
                elif hyp_id == 'H-575':
                    s = btc_volume_trend(btc_daily, price_lookback=params[0], vol_lookback=params[1])
                elif hyp_id == 'H-576':
                    s = btc_supertrend(btc_daily, period=params[0], mult=params[1])
                elif hyp_id == 'H-577':
                    s = btc_heikin_ashi_trend(btc_daily, n_confirm=params[0])
                elif hyp_id == 'H-578':
                    s = btc_ichimoku_signal(btc_daily, tenkan=params[0], kijun=params[1], senkou_b=params[2])
                elif hyp_id == 'H-579':
                    s = btc_mean_reversion_daily(btc_daily, lookback=params[0], z_entry=params[1])
                else:
                    continue

                b = backtest_ts(prices, s, freq=freq)
                if b['sharpe'] > 0: pos += 1
                total += 1
            except:
                total += 1

        if total > 0:
            print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
            results[hyp_id]['param_robust'] = f"{pos}/{total}"

    # Walk-forward for promising ones (Sharpe > 0.3)
    promising = {h: r for h, r in results.items() if r.get('sharpe', 0) > 0.3}
    if promising:
        print(f"\n{'='*80}")
        print(f"WALK-FORWARD for {len(promising)} promising strategies")
        print(f"{'='*80}")
        for hyp_id in sorted(promising.keys()):
            # Build signal function for WF
            if hyp_id == 'H-565':
                sig_fn = lambda p: btc_4h_ema_trend(btc_4h.loc[:p.index[-1]])
                prices = btc_4h['close']
                freq = '4h'
            elif hyp_id == 'H-566':
                sig_fn = lambda p: btc_4h_rsi_momentum(btc_4h.loc[:p.index[-1]])
                prices = btc_4h['close']
                freq = '4h'
            elif hyp_id == 'H-576':
                sig_fn = lambda p: btc_supertrend(btc_daily.loc[:p.index[-1]])
                prices = btc_daily['close']
                freq = 'daily'
            elif hyp_id == 'H-574':
                sig_fn = lambda p: btc_adx_trend(btc_daily.loc[:p.index[-1]])
                prices = btc_daily['close']
                freq = 'daily'
            elif hyp_id == 'H-569':
                sig_fn = lambda p: sol_ema_trend(sol_daily.loc[:p.index[-1]])
                prices = sol_daily['close']
                freq = 'daily'
            elif hyp_id == 'H-570':
                sig_fn = lambda p: sol_keltner_breakout(sol_daily.loc[:p.index[-1]])
                prices = sol_daily['close']
                freq = 'daily'
            elif hyp_id == 'H-573':
                sig_fn = lambda p: btc_daily_trend_vol_target(btc_daily.loc[:p.index[-1]])
                prices = btc_daily['close']
                freq = 'daily'
            elif hyp_id == 'H-577':
                sig_fn = lambda p: btc_heikin_ashi_trend(btc_daily.loc[:p.index[-1]])
                prices = btc_daily['close']
                freq = 'daily'
            elif hyp_id == 'H-578':
                sig_fn = lambda p: btc_ichimoku_signal(btc_daily.loc[:p.index[-1]])
                prices = btc_daily['close']
                freq = 'daily'
            else:
                continue

            wf = walk_forward_ts(prices, sig_fn, n_folds=8, freq=freq)
            pos_folds = sum(1 for s in wf if s > 0)
            mean_sh = np.mean(wf) if wf else 0
            print(f"  {hyp_id}: WF {pos_folds}/{len(wf)} positive, mean Sharpe {mean_sh:.3f}, folds: {wf}")
            results[hyp_id]['wf_folds'] = wf
            results[hyp_id]['wf_positive'] = f"{pos_folds}/{len(wf)}"

    # Summary
    print(f"\n{'='*100}")
    print("SUMMARY TABLE — BATCH 2")
    print(f"{'='*100}")
    print(f"{'Hyp':6s} {'Name':25s} {'Sharpe':>8s} {'AnnRet':>8s} {'MaxDD':>8s} {'Trades':>7s} {'WR':>6s} {'ParamRob':>10s} {'WF':>8s}")
    print("-" * 100)

    for h in sorted(results.keys()):
        r = results[h]
        sharpe = r.get('sharpe', 0)
        ann = r.get('ann_ret', 0)
        dd = r.get('max_dd', 0)
        trades = r.get('n_trades', 0)
        wr = r.get('win_rate', 0)
        pr = r.get('param_robust', 'N/A')
        wf = r.get('wf_positive', '-')

        # Find name
        name = ''
        for s in strategies:
            if s[0] == h:
                name = s[1][:25]
                break
        if h == 'H-572':
            name = 'BTC Multi-Timeframe'

        print(f"{h:6s} {name:25s} {sharpe:8.3f} {ann:8.1%} {dd:8.1%} {trades:7d} {wr:6.1%} {pr:>10s} {wf:>8s}")

    # Save
    save_results = {}
    for h, r in results.items():
        save_results[h] = {k: v for k, v in r.items() if k != 'equity'}
    with open('strategies/ts_batch_177b_results.json', 'w') as f:
        json.dump(save_results, f, indent=2)
    print("\nResults saved to strategies/ts_batch_177b_results.json")


if __name__ == '__main__':
    run_batch()
