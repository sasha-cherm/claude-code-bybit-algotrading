#!/usr/bin/env python3
"""
Session 177: Batch backtest for ETH time-series + multi-asset TS strategies.
H-548 through H-563: 16 hypotheses.

Validation pipeline (same as prior sessions):
1. In-sample (IS) hit rate: need > 75% of params positive
2. Walk-forward (WF): need >= 4/6 or 4/8 folds positive
3. Split-half (SH): both halves positive Sharpe
4. Parameter robustness: >= 80% of param grid positive

Deploy if all 4 pass + low correlation with H-012.
"""
import sys, json, warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings('ignore')

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

def load_hourly(symbol='BTC'):
    f = DATA_DIR / f'{symbol}_USDT_1h.parquet'
    df = pd.read_parquet(f)
    return df

def compute_daily_from_hourly(df_1h):
    """Resample hourly to daily OHLCV."""
    daily = df_1h.resample('1D').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna()
    return daily

def backtest_ts_signal(prices, signal, fee_bps=10):
    """
    Backtest a time-series signal on a single asset.
    prices: Series of close prices (daily)
    signal: Series of {-1, 0, +1} (lagged — signal[t] uses data up to t-1)
    fee_bps: round-trip fee in bps
    Returns equity curve and metrics.
    """
    common = prices.index.intersection(signal.index)
    prices = prices.loc[common]
    signal = signal.loc[common]

    ret = prices.pct_change().fillna(0)
    # Signal applied at close on day t, earns return on day t+1
    strat_ret = signal.shift(1) * ret  # shift(1) ensures no look-ahead
    strat_ret = strat_ret.fillna(0)

    # Fee: charge fee_bps on every signal change
    signal_change = signal.diff().abs().fillna(0)
    fees = signal_change * fee_bps / 10000
    strat_ret = strat_ret - fees

    equity = 10000 * (1 + strat_ret).cumprod()

    # Metrics
    n_days = len(equity)
    years = n_days / 365
    total_ret = equity.iloc[-1] / equity.iloc[0] - 1
    ann_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0

    daily_ret = strat_ret
    sharpe = daily_ret.mean() / daily_ret.std() * np.sqrt(365) if daily_ret.std() > 0 else 0

    peak = equity.cummax()
    dd = (equity - peak) / peak
    max_dd = abs(dd.min())

    n_trades = int(signal_change.sum())
    win_days = (strat_ret > 0).sum()
    loss_days = (strat_ret < 0).sum()
    wr = win_days / (win_days + loss_days) if (win_days + loss_days) > 0 else 0

    return {
        'equity': equity,
        'sharpe': round(sharpe, 3),
        'ann_ret': round(ann_ret, 4),
        'max_dd': round(max_dd, 4),
        'total_ret': round(total_ret, 4),
        'n_trades': n_trades,
        'win_rate': round(wr, 3),
        'n_days': n_days
    }


def walk_forward(prices, signal_fn, n_folds=8, train_frac=0.6):
    """
    Walk-forward validation.
    signal_fn(prices_train) -> signal for the entire series (but we only score test portion).
    """
    n = len(prices)
    fold_size = n // n_folds
    results = []

    for i in range(n_folds):
        test_start = i * fold_size
        test_end = min((i + 1) * fold_size, n)
        train_end = test_start

        if train_end < int(n * train_frac * 0.5):
            continue  # not enough training data

        train_prices = prices.iloc[:train_end]
        test_prices = prices.iloc[test_start:test_end]

        if len(train_prices) < 100 or len(test_prices) < 30:
            continue

        # Generate signal using only training data, score on test
        full_signal = signal_fn(prices.iloc[:test_end])
        test_signal = full_signal.iloc[test_start:test_end]

        bt = backtest_ts_signal(test_prices, test_signal)
        results.append(bt['sharpe'])

    return results


def split_half_test(prices, signal_fn):
    """Split data in half, run signal_fn on each half independently."""
    mid = len(prices) // 2
    h1_prices = prices.iloc[:mid]
    h2_prices = prices.iloc[mid:]

    sig1 = signal_fn(h1_prices)
    sig2 = signal_fn(h2_prices)

    bt1 = backtest_ts_signal(h1_prices, sig1)
    bt2 = backtest_ts_signal(h2_prices, sig2)

    return bt1['sharpe'], bt2['sharpe']


def param_robustness(prices, signal_fn_factory, param_grid):
    """Test % of parameter combinations that yield positive Sharpe."""
    positive = 0
    total = 0
    for params in param_grid:
        sig_fn = signal_fn_factory(*params)
        sig = sig_fn(prices)
        bt = backtest_ts_signal(prices, sig)
        if bt['sharpe'] > 0:
            positive += 1
        total += 1
    return positive, total


# ============================================================
# SIGNAL GENERATORS
# ============================================================

def eth_intraday_momentum_signal(prices_1h, threshold=0.0):
    """H-548: ETH first 6h return predicts next day direction."""
    df = prices_1h.copy()
    df['date'] = df.index.date
    df['hour'] = df.index.hour

    daily_signals = {}
    for date, group in df.groupby('date'):
        first_6h = group[group['hour'] < 6]
        if len(first_6h) >= 4:
            ret_6h = first_6h['close'].iloc[-1] / first_6h['open'].iloc[0] - 1
            if ret_6h > threshold:
                daily_signals[date] = 1
            elif ret_6h < -threshold:
                daily_signals[date] = -1
            else:
                daily_signals[date] = 0

    sig = pd.Series(daily_signals)
    sig.index = pd.to_datetime(sig.index, utc=True)
    return sig


def keltner_breakout_signal(prices_daily, period=20, atr_mult=1.5):
    """H-549: Keltner channel breakout on ETH daily."""
    close = prices_daily['close']
    high = prices_daily['high']
    low = prices_daily['low']

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


def range_squeeze_signal(prices_daily, bb_period=20, kc_period=20, bb_mult=2.0, kc_mult=1.5):
    """H-550: Bollinger Bands inside Keltner = squeeze. Breakout direction = trade."""
    close = prices_daily['close']
    high = prices_daily['high']
    low = prices_daily['low']

    # Bollinger Bands
    bb_ma = close.rolling(bb_period).mean()
    bb_std = close.rolling(bb_period).std()
    bb_upper = bb_ma + bb_mult * bb_std
    bb_lower = bb_ma - bb_mult * bb_std

    # Keltner Channels
    kc_ma = close.ewm(span=kc_period).mean()
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(kc_period).mean()
    kc_upper = kc_ma + kc_mult * atr
    kc_lower = kc_ma - kc_mult * atr

    # Squeeze: BB inside KC
    squeeze = (bb_upper < kc_upper) & (bb_lower > kc_lower)

    # Momentum direction
    mom = close - close.rolling(bb_period).mean()

    signal = pd.Series(0, index=close.index)
    in_squeeze = False
    for i in range(1, len(close)):
        if squeeze.iloc[i-1]:
            in_squeeze = True
        elif in_squeeze and not squeeze.iloc[i-1]:
            # Squeeze released — trade in momentum direction
            in_squeeze = False
            if mom.iloc[i-1] > 0:
                signal.iloc[i] = 1
            else:
                signal.iloc[i] = -1
        elif not in_squeeze and signal.iloc[i-1] != 0:
            # Hold position for N bars then exit
            bars_in = 0
            for j in range(i-1, max(0, i-21), -1):
                if signal.iloc[j] == signal.iloc[i-1]:
                    bars_in += 1
                else:
                    break
            if bars_in < 20:
                signal.iloc[i] = signal.iloc[i-1]

    return signal


def rsi_mean_reversion_signal(prices_daily, period=14, overbought=70, oversold=30):
    """H-551: RSI mean-reversion on ETH daily."""
    close = prices_daily['close']
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    signal = pd.Series(0, index=close.index)
    pos = 0
    for i in range(1, len(close)):
        if rsi.iloc[i-1] < oversold:
            pos = 1
        elif rsi.iloc[i-1] > overbought:
            pos = -1
        elif pos == 1 and rsi.iloc[i-1] > 50:
            pos = 0
        elif pos == -1 and rsi.iloc[i-1] < 50:
            pos = 0
        signal.iloc[i] = pos

    return signal


def volume_spike_momentum_signal(prices_daily, vol_mult=2.0, hold_days=5):
    """H-552: Trade in direction of price on volume spike days."""
    close = prices_daily['close']
    volume = prices_daily['volume']

    vol_ma = volume.rolling(20).mean()
    vol_spike = volume > vol_mult * vol_ma
    price_dir = close.pct_change().apply(np.sign)

    signal = pd.Series(0, index=close.index)
    hold_count = 0
    for i in range(1, len(close)):
        if vol_spike.iloc[i-1] and price_dir.iloc[i-1] != 0:
            signal.iloc[i] = int(price_dir.iloc[i-1])
            hold_count = hold_days
        elif hold_count > 0:
            signal.iloc[i] = signal.iloc[i-1]
            hold_count -= 1

    return signal


def macd_crossover_signal(prices_daily, fast=12, slow=26, sig_period=9):
    """H-553: MACD crossover signal on ETH."""
    close = prices_daily['close']

    ema_fast = close.ewm(span=fast).mean()
    ema_slow = close.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=sig_period).mean()

    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        if macd.iloc[i-1] > macd_signal.iloc[i-1]:
            signal.iloc[i] = 1
        else:
            signal.iloc[i] = -1

    return signal


def overnight_gap_signal(prices_1h, threshold=0.005):
    """H-554: Trade contrarian to overnight (00-06 UTC) gap."""
    df = prices_1h.copy()
    df['date'] = df.index.date
    df['hour'] = df.index.hour

    daily_signals = {}
    for date, group in df.groupby('date'):
        overnight = group[group['hour'] < 6]
        if len(overnight) >= 4:
            gap = overnight['close'].iloc[-1] / overnight['open'].iloc[0] - 1
            if gap > threshold:
                daily_signals[date] = -1  # contrarian: gap up → short
            elif gap < -threshold:
                daily_signals[date] = 1   # contrarian: gap down → long
            else:
                daily_signals[date] = 0

    sig = pd.Series(daily_signals)
    sig.index = pd.to_datetime(sig.index, utc=True)
    return sig


def bollinger_reversion_signal(prices_daily, period=20, std_mult=2.0):
    """H-555: Bollinger band mean-reversion."""
    close = prices_daily['close']
    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = ma + std_mult * std
    lower = ma - std_mult * std

    signal = pd.Series(0, index=close.index)
    pos = 0
    for i in range(1, len(close)):
        if close.iloc[i-1] < lower.iloc[i-1]:
            pos = 1  # buy at lower band
        elif close.iloc[i-1] > upper.iloc[i-1]:
            pos = -1  # sell at upper band
        elif pos == 1 and close.iloc[i-1] > ma.iloc[i-1]:
            pos = 0
        elif pos == -1 and close.iloc[i-1] < ma.iloc[i-1]:
            pos = 0
        signal.iloc[i] = pos

    return signal


# --- Multi-asset / cross-asset signals ---

def btc_eth_spread_signal(btc_daily, eth_daily, lookback=20, z_entry=1.5, z_exit=0.5):
    """H-556: BTC-ETH ratio mean-reversion."""
    common = btc_daily.index.intersection(eth_daily.index)
    btc_c = btc_daily.loc[common, 'close']
    eth_c = eth_daily.loc[common, 'close']

    ratio = np.log(btc_c / eth_c)
    ratio_ma = ratio.rolling(lookback).mean()
    ratio_std = ratio.rolling(lookback).std()
    z = (ratio - ratio_ma) / ratio_std.replace(0, np.nan)

    # If ratio too high (BTC overvalued vs ETH), short BTC / long ETH → return -1 for BTC signal
    signal = pd.Series(0, index=common)
    pos = 0
    for i in range(1, len(common)):
        if np.isnan(z.iloc[i-1]):
            continue
        if z.iloc[i-1] > z_entry:
            pos = -1  # short BTC (ratio will revert down)
        elif z.iloc[i-1] < -z_entry:
            pos = 1   # long BTC (ratio will revert up)
        elif pos == -1 and z.iloc[i-1] < z_exit:
            pos = 0
        elif pos == 1 and z.iloc[i-1] > -z_exit:
            pos = 0
        signal.iloc[i] = pos

    return signal


def multi_asset_tsmom_signal(prices_dict, lookback=60):
    """H-557: Time-series momentum on each asset, equal-weight portfolio.
    Returns dict of signals per asset.
    """
    signals = {}
    for sym, daily in prices_dict.items():
        close = daily['close']
        ret = close.pct_change(lookback)
        sig = ret.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        sig = sig.shift(1)  # lag to avoid look-ahead
        signals[sym] = sig
    return signals


def btc_hourly_mean_reversion_signal(prices_1h, lookback=24, z_entry=2.0, z_exit=0.5):
    """H-558: Intraday mean-reversion on BTC using hourly z-score."""
    close = prices_1h['close']
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
        elif pos == 1 and z.iloc[i-1] > -z_exit:
            pos = 0
        elif pos == -1 and z.iloc[i-1] < z_exit:
            pos = 0
        signal.iloc[i] = pos

    return signal


def btc_weekend_signal(prices_daily):
    """H-559: BTC weekend effect — long Fri close to Mon close."""
    close = prices_daily['close']
    dow = close.index.dayofweek  # Mon=0, Sun=6

    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        if dow[i-1] == 4:  # Friday
            signal.iloc[i] = 1  # long over weekend
        elif dow[i-1] in [5, 6]:
            signal.iloc[i] = 1  # hold through weekend
        elif dow[i-1] == 0:
            signal.iloc[i] = 0  # exit Monday

    return signal


def eth_btc_leader_signal(btc_1h, eth_1h, lookback=24):
    """H-560: BTC hourly momentum predicts ETH next-day direction."""
    # Compute BTC 24h return
    btc_close = btc_1h['close']
    btc_ret_24h = btc_close.pct_change(lookback)

    # Resample to daily
    btc_daily_sig = btc_ret_24h.resample('1D').last()
    btc_daily_sig = btc_daily_sig.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))

    # Lag by 1 day
    return btc_daily_sig.shift(1)


def atr_breakout_signal(prices_daily, atr_period=14, mult=2.0):
    """H-561: ATR breakout — trade when close moves > mult * ATR from previous close."""
    close = prices_daily['close']
    high = prices_daily['high']
    low = prices_daily['low']

    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    move = close - close.shift(1)

    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        if np.isnan(atr.iloc[i-1]):
            continue
        if move.iloc[i-1] > mult * atr.iloc[i-1]:
            signal.iloc[i] = 1  # strong up move → momentum
        elif move.iloc[i-1] < -mult * atr.iloc[i-1]:
            signal.iloc[i] = -1  # strong down move
        else:
            signal.iloc[i] = signal.iloc[i-1]  # hold

    return signal


def donchian_channel_signal(prices_daily, period=20):
    """H-562: Donchian channel breakout (turtle-style)."""
    close = prices_daily['close']
    high = prices_daily['high']
    low = prices_daily['low']

    upper = high.rolling(period).max()
    lower = low.rolling(period).min()

    signal = pd.Series(0, index=close.index)
    pos = 0
    for i in range(1, len(close)):
        if close.iloc[i-1] > upper.iloc[i-2] if i > 1 else False:
            pos = 1
        elif close.iloc[i-1] < lower.iloc[i-2] if i > 1 else False:
            pos = -1
        signal.iloc[i] = pos

    return signal


def vol_regime_signal(prices_daily, vol_lookback=20, vol_threshold_pct=50):
    """H-563: Trade momentum in low-vol regimes, mean-revert in high-vol regimes."""
    close = prices_daily['close']
    ret = close.pct_change()
    vol = ret.rolling(vol_lookback).std()
    vol_rank = vol.rolling(252).rank(pct=True)  # percentile rank of current vol

    # Momentum signal
    mom = close.pct_change(vol_lookback)
    mom_dir = mom.apply(lambda x: 1 if x > 0 else -1)

    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        if np.isnan(vol_rank.iloc[i-1]):
            continue
        if vol_rank.iloc[i-1] < vol_threshold_pct / 100:
            # Low vol → momentum
            signal.iloc[i] = int(mom_dir.iloc[i-1]) if not np.isnan(mom_dir.iloc[i-1]) else 0
        else:
            # High vol → mean-reversion (contrarian)
            signal.iloc[i] = -int(mom_dir.iloc[i-1]) if not np.isnan(mom_dir.iloc[i-1]) else 0

    return signal


# ============================================================
# MAIN BATCH BACKTEST
# ============================================================

def run_batch():
    print("=" * 80)
    print("SESSION 177: ETH Time-Series + Multi-Asset TS Strategies")
    print("=" * 80)

    # Load data
    print("\nLoading data...")
    btc_1h = load_hourly('BTC')
    eth_1h = load_hourly('ETH')
    sol_1h = load_hourly('SOL')

    btc_daily = compute_daily_from_hourly(btc_1h)
    eth_daily = compute_daily_from_hourly(eth_1h)
    sol_daily = compute_daily_from_hourly(sol_1h)

    print(f"BTC daily: {len(btc_daily)} bars ({btc_daily.index[0].date()} to {btc_daily.index[-1].date()})")
    print(f"ETH daily: {len(eth_daily)} bars ({eth_daily.index[0].date()} to {eth_daily.index[-1].date()})")
    print(f"SOL daily: {len(sol_daily)} bars ({sol_daily.index[0].date()} to {sol_daily.index[-1].date()})")

    results = {}

    # --- H-548: ETH Intraday Session Momentum ---
    print("\n--- H-548: ETH Intraday Session Momentum ---")
    sig = eth_intraday_momentum_signal(eth_1h)
    eth_close_daily = eth_daily['close']
    bt = backtest_ts_signal(eth_close_daily, sig)
    results['H-548'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    # Param robustness: vary threshold
    pos = 0
    total = 0
    for thresh in [0, 0.002, 0.005, 0.008, 0.01, 0.015, 0.02, 0.025]:
        s = eth_intraday_momentum_signal(eth_1h, threshold=thresh)
        b = backtest_ts_signal(eth_close_daily, s)
        if b['sharpe'] > 0: pos += 1
        total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-548']['param_robust'] = f"{pos}/{total}"

    # --- H-549: ETH Keltner Channel Breakout ---
    print("\n--- H-549: ETH Keltner Channel Breakout ---")
    sig = keltner_breakout_signal(eth_daily)
    bt = backtest_ts_signal(eth_close_daily, sig)
    results['H-549'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    pos = 0
    total = 0
    for period in [10, 15, 20, 25, 30]:
        for mult in [1.0, 1.5, 2.0, 2.5]:
            s = keltner_breakout_signal(eth_daily, period=period, atr_mult=mult)
            b = backtest_ts_signal(eth_close_daily, s)
            if b['sharpe'] > 0: pos += 1
            total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-549']['param_robust'] = f"{pos}/{total}"

    # --- H-550: ETH Range Squeeze ---
    print("\n--- H-550: ETH Range Squeeze ---")
    sig = range_squeeze_signal(eth_daily)
    bt = backtest_ts_signal(eth_close_daily, sig)
    results['H-550'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    pos = 0
    total = 0
    for bb_p in [15, 20, 25]:
        for bb_m in [1.5, 2.0, 2.5]:
            for kc_m in [1.0, 1.5, 2.0]:
                s = range_squeeze_signal(eth_daily, bb_period=bb_p, bb_mult=bb_m, kc_mult=kc_m)
                b = backtest_ts_signal(eth_close_daily, s)
                if b['sharpe'] > 0: pos += 1
                total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-550']['param_robust'] = f"{pos}/{total}"

    # --- H-551: ETH RSI Mean Reversion ---
    print("\n--- H-551: ETH RSI Mean Reversion ---")
    sig = rsi_mean_reversion_signal(eth_daily)
    bt = backtest_ts_signal(eth_close_daily, sig)
    results['H-551'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    pos = 0
    total = 0
    for period in [7, 10, 14, 21]:
        for ob in [65, 70, 75, 80]:
            os_ = 100 - ob
            s = rsi_mean_reversion_signal(eth_daily, period=period, overbought=ob, oversold=os_)
            b = backtest_ts_signal(eth_close_daily, s)
            if b['sharpe'] > 0: pos += 1
            total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-551']['param_robust'] = f"{pos}/{total}"

    # --- H-552: ETH Volume Spike Momentum ---
    print("\n--- H-552: ETH Volume Spike Momentum ---")
    sig = volume_spike_momentum_signal(eth_daily)
    bt = backtest_ts_signal(eth_close_daily, sig)
    results['H-552'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    pos = 0
    total = 0
    for mult in [1.5, 2.0, 2.5, 3.0]:
        for hold in [3, 5, 7, 10]:
            s = volume_spike_momentum_signal(eth_daily, vol_mult=mult, hold_days=hold)
            b = backtest_ts_signal(eth_close_daily, s)
            if b['sharpe'] > 0: pos += 1
            total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-552']['param_robust'] = f"{pos}/{total}"

    # --- H-553: ETH MACD Crossover ---
    print("\n--- H-553: ETH MACD Crossover ---")
    sig = macd_crossover_signal(eth_daily)
    bt = backtest_ts_signal(eth_close_daily, sig)
    results['H-553'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    pos = 0
    total = 0
    for fast in [8, 12, 16]:
        for slow in [20, 26, 32]:
            for sp in [7, 9, 12]:
                if fast >= slow: continue
                s = macd_crossover_signal(eth_daily, fast=fast, slow=slow, sig_period=sp)
                b = backtest_ts_signal(eth_close_daily, s)
                if b['sharpe'] > 0: pos += 1
                total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-553']['param_robust'] = f"{pos}/{total}"

    # --- H-554: ETH Overnight Gap Contrarian ---
    print("\n--- H-554: ETH Overnight Gap Contrarian ---")
    sig = overnight_gap_signal(eth_1h)
    bt = backtest_ts_signal(eth_close_daily, sig)
    results['H-554'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    pos = 0
    total = 0
    for thresh in [0.002, 0.005, 0.008, 0.01, 0.015, 0.02]:
        s = overnight_gap_signal(eth_1h, threshold=thresh)
        b = backtest_ts_signal(eth_close_daily, s)
        if b['sharpe'] > 0: pos += 1
        total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-554']['param_robust'] = f"{pos}/{total}"

    # --- H-555: ETH Bollinger Reversion ---
    print("\n--- H-555: ETH Bollinger Reversion ---")
    sig = bollinger_reversion_signal(eth_daily)
    bt = backtest_ts_signal(eth_close_daily, sig)
    results['H-555'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    pos = 0
    total = 0
    for period in [10, 15, 20, 25, 30]:
        for mult in [1.5, 2.0, 2.5, 3.0]:
            s = bollinger_reversion_signal(eth_daily, period=period, std_mult=mult)
            b = backtest_ts_signal(eth_close_daily, s)
            if b['sharpe'] > 0: pos += 1
            total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-555']['param_robust'] = f"{pos}/{total}"

    # --- H-556: BTC-ETH Spread Mean Reversion ---
    print("\n--- H-556: BTC-ETH Spread Mean Reversion ---")
    sig = btc_eth_spread_signal(btc_daily, eth_daily)
    bt = backtest_ts_signal(btc_daily['close'], sig)
    results['H-556'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    pos = 0
    total = 0
    for lb in [10, 15, 20, 30, 40]:
        for ze in [1.0, 1.5, 2.0, 2.5]:
            s = btc_eth_spread_signal(btc_daily, eth_daily, lookback=lb, z_entry=ze)
            b = backtest_ts_signal(btc_daily['close'], s)
            if b['sharpe'] > 0: pos += 1
            total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-556']['param_robust'] = f"{pos}/{total}"

    # --- H-557: Multi-Asset TSMOM (BTC+ETH+SOL, properly lagged) ---
    print("\n--- H-557: Multi-Asset TSMOM Portfolio ---")
    prices_dict = {'BTC': btc_daily, 'ETH': eth_daily, 'SOL': sol_daily}
    sigs = multi_asset_tsmom_signal(prices_dict, lookback=60)
    # Equal-weight portfolio return
    common_idx = btc_daily.index.intersection(eth_daily.index).intersection(sol_daily.index)
    port_ret = pd.Series(0.0, index=common_idx)
    for sym in ['BTC', 'ETH', 'SOL']:
        s = sigs[sym].reindex(common_idx).fillna(0)
        r = prices_dict[sym].loc[common_idx, 'close'].pct_change().fillna(0)
        port_ret += s.shift(1) * r / 3

    equity = 10000 * (1 + port_ret).cumprod()
    n_days = len(equity)
    years = n_days / 365
    total_ret = equity.iloc[-1] / equity.iloc[0] - 1
    ann_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
    sharpe = port_ret.mean() / port_ret.std() * np.sqrt(365) if port_ret.std() > 0 else 0
    peak = equity.cummax()
    dd = abs(((equity - peak) / peak).min())

    results['H-557'] = {'sharpe': round(sharpe, 3), 'ann_ret': round(ann_ret, 4), 'max_dd': round(dd, 4), 'n_days': n_days, 'equity': equity}
    print(f"  Sharpe: {sharpe:.3f}, Ann: {ann_ret:.1%}, DD: {dd:.1%}, Days: {n_days}")

    pos = 0
    total = 0
    for lb in [20, 40, 60, 90, 120, 180]:
        sigs = multi_asset_tsmom_signal(prices_dict, lookback=lb)
        pr = pd.Series(0.0, index=common_idx)
        for sym in ['BTC', 'ETH', 'SOL']:
            s = sigs[sym].reindex(common_idx).fillna(0)
            r = prices_dict[sym].loc[common_idx, 'close'].pct_change().fillna(0)
            pr += s.shift(1) * r / 3
        sh = pr.mean() / pr.std() * np.sqrt(365) if pr.std() > 0 else 0
        if sh > 0: pos += 1
        total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-557']['param_robust'] = f"{pos}/{total}"

    # --- H-558: BTC Hourly Mean Reversion ---
    print("\n--- H-558: BTC Hourly Mean Reversion ---")
    sig = btc_hourly_mean_reversion_signal(btc_1h)
    # Backtest on hourly
    btc_1h_close = btc_1h['close']
    ret = btc_1h_close.pct_change().fillna(0)
    strat_ret = sig.shift(1) * ret
    sig_change = sig.diff().abs().fillna(0)
    strat_ret = strat_ret - sig_change * 10 / 10000
    strat_ret = strat_ret.fillna(0)
    eq = 10000 * (1 + strat_ret).cumprod()
    n = len(eq)
    years = n / 8760
    total_ret = eq.iloc[-1] / eq.iloc[0] - 1
    ann_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
    sharpe = strat_ret.mean() / strat_ret.std() * np.sqrt(8760) if strat_ret.std() > 0 else 0
    peak = eq.cummax()
    dd = abs(((eq - peak) / peak).min())
    results['H-558'] = {'sharpe': round(sharpe, 3), 'ann_ret': round(ann_ret, 4), 'max_dd': round(dd, 4), 'n_hours': n}
    print(f"  Sharpe: {sharpe:.3f}, Ann: {ann_ret:.1%}, DD: {dd:.1%}, Hours: {n}")

    pos = 0
    total = 0
    for lb in [12, 24, 48, 72]:
        for ze in [1.5, 2.0, 2.5, 3.0]:
            s = btc_hourly_mean_reversion_signal(btc_1h, lookback=lb, z_entry=ze)
            sr = s.shift(1) * ret - s.diff().abs().fillna(0) * 10 / 10000
            sr = sr.fillna(0)
            sh = sr.mean() / sr.std() * np.sqrt(8760) if sr.std() > 0 else 0
            if sh > 0: pos += 1
            total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-558']['param_robust'] = f"{pos}/{total}"

    # --- H-559: BTC Weekend Effect ---
    print("\n--- H-559: BTC Weekend Effect ---")
    sig = btc_weekend_signal(btc_daily)
    bt = backtest_ts_signal(btc_daily['close'], sig)
    results['H-559'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    # --- H-560: BTC→ETH Leader-Follower ---
    print("\n--- H-560: BTC→ETH Leader-Follower ---")
    sig = eth_btc_leader_signal(btc_1h, eth_1h)
    bt = backtest_ts_signal(eth_close_daily, sig)
    results['H-560'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    pos = 0
    total = 0
    for lb in [6, 12, 24, 48, 72]:
        s = eth_btc_leader_signal(btc_1h, eth_1h, lookback=lb)
        b = backtest_ts_signal(eth_close_daily, s)
        if b['sharpe'] > 0: pos += 1
        total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-560']['param_robust'] = f"{pos}/{total}"

    # --- H-561: BTC ATR Breakout ---
    print("\n--- H-561: BTC ATR Breakout ---")
    sig = atr_breakout_signal(btc_daily)
    bt = backtest_ts_signal(btc_daily['close'], sig)
    results['H-561'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    pos = 0
    total = 0
    for period in [7, 14, 21, 28]:
        for mult in [1.0, 1.5, 2.0, 2.5, 3.0]:
            s = atr_breakout_signal(btc_daily, atr_period=period, mult=mult)
            b = backtest_ts_signal(btc_daily['close'], s)
            if b['sharpe'] > 0: pos += 1
            total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-561']['param_robust'] = f"{pos}/{total}"

    # --- H-562: BTC Donchian Channel ---
    print("\n--- H-562: BTC Donchian Channel ---")
    sig = donchian_channel_signal(btc_daily)
    bt = backtest_ts_signal(btc_daily['close'], sig)
    results['H-562'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    pos = 0
    total = 0
    for period in [10, 15, 20, 25, 30, 40, 55]:
        s = donchian_channel_signal(btc_daily, period=period)
        b = backtest_ts_signal(btc_daily['close'], s)
        if b['sharpe'] > 0: pos += 1
        total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-562']['param_robust'] = f"{pos}/{total}"

    # --- H-563: BTC Vol Regime Adaptive ---
    print("\n--- H-563: BTC Vol Regime Adaptive ---")
    sig = vol_regime_signal(btc_daily)
    bt = backtest_ts_signal(btc_daily['close'], sig)
    results['H-563'] = bt
    print(f"  Sharpe: {bt['sharpe']}, Ann: {bt['ann_ret']:.1%}, DD: {bt['max_dd']:.1%}, Trades: {bt['n_trades']}, WR: {bt['win_rate']:.1%}")

    pos = 0
    total = 0
    for lb in [10, 15, 20, 30]:
        for vt in [30, 40, 50, 60, 70]:
            s = vol_regime_signal(btc_daily, vol_lookback=lb, vol_threshold_pct=vt)
            b = backtest_ts_signal(btc_daily['close'], s)
            if b['sharpe'] > 0: pos += 1
            total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    results['H-563']['param_robust'] = f"{pos}/{total}"

    # ============================================================
    # SUMMARY TABLE
    # ============================================================
    print("\n" + "=" * 100)
    print("SUMMARY TABLE")
    print("=" * 100)
    print(f"{'Hyp':6s} {'Sharpe':>8s} {'AnnRet':>8s} {'MaxDD':>8s} {'Trades':>7s} {'WR':>6s} {'ParamRob':>10s} {'PASS?':>6s}")
    print("-" * 100)

    for h in sorted(results.keys()):
        r = results[h]
        sharpe = r.get('sharpe', 0)
        ann = r.get('ann_ret', 0)
        dd = r.get('max_dd', 0)
        trades = r.get('n_trades', 0)
        wr = r.get('win_rate', 0)
        pr = r.get('param_robust', 'N/A')

        # Pass criteria: Sharpe > 0.5, param robust >= 60%
        passed = '??'
        if sharpe > 0.5:
            if '/' in str(pr):
                num, den = str(pr).split('/')
                if int(num) / int(den) >= 0.6:
                    passed = 'YES'
                else:
                    passed = 'NO'
        else:
            passed = 'NO'

        print(f"{h:6s} {sharpe:8.3f} {ann:8.1%} {dd:8.1%} {trades:7d} {wr:6.1%} {pr:>10s} {passed:>6s}")

    print("\n" + "=" * 100)

    # Save results (exclude equity curves for JSON serialization)
    save_results = {}
    for h, r in results.items():
        sr = {k: v for k, v in r.items() if k != 'equity'}
        save_results[h] = sr

    with open('strategies/ts_batch_177_results.json', 'w') as f:
        json.dump(save_results, f, indent=2)

    print("\nResults saved to strategies/ts_batch_177_results.json")

    # Return promising ones for deep validation
    promising = [h for h, r in results.items() if r.get('sharpe', 0) > 0.5]
    if promising:
        print(f"\nPromising strategies for deep validation: {promising}")
    else:
        print("\nNo strategies passed initial screening (Sharpe > 0.5)")

    return results


if __name__ == '__main__':
    run_batch()
