#!/usr/bin/env python3
"""
Session 180 Batch 2: Daily altcoin TS + Funding Rate TS + OI-based TS
H-644 through H-651: 8 hypotheses testing different TS signal categories.
"""
import sys, json, warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings('ignore')

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

def load_daily(symbol='BTC'):
    f = DATA_DIR / f'{symbol}_USDT_1h.parquet'
    df = pd.read_parquet(f)
    daily = df.resample('1D').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna()
    return daily

def load_hourly(symbol='BTC'):
    f = DATA_DIR / f'{symbol}_USDT_1h.parquet'
    return pd.read_parquet(f)

def load_funding(symbol='BTC'):
    f = DATA_DIR / f'funding_{symbol}USDT.parquet'
    return pd.read_parquet(f)

def load_oi_daily(symbol='BTC'):
    f = DATA_DIR / f'oi/{symbol}_oi_1d.parquet'
    return pd.read_parquet(f)

def backtest_ts(prices, signal, fee_bps=10, freq='daily'):
    common = prices.index.intersection(signal.index)
    prices = prices.loc[common]
    signal = signal.loc[common]

    ret = prices.pct_change().fillna(0)
    strat_ret = (signal.shift(1) * ret).fillna(0)
    signal_change = signal.diff().abs().fillna(0)
    strat_ret = strat_ret - signal_change * fee_bps / 10000

    equity = 10000 * (1 + strat_ret).cumprod()

    ppy = {'daily': 365, 'hourly': 8760, '4h': 2190}[freq]
    n = len(equity)
    years = n / ppy
    total_ret = equity.iloc[-1] / equity.iloc[0] - 1
    ann_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
    sharpe = float(strat_ret.mean() / strat_ret.std() * np.sqrt(ppy)) if float(strat_ret.std()) > 0 else 0
    peak = equity.cummax()
    dd = float(abs(((equity - peak) / peak).min()))
    n_trades = int(signal_change.sum())
    win = int((strat_ret > 0).sum())
    loss = int((strat_ret < 0).sum())
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
    ppy = {'daily': 365, 'hourly': 8760, '4h': 2190}[freq]
    n = len(prices)
    fold_size = n // n_folds
    results = []

    for i in range(n_folds):
        test_start = i * fold_size
        test_end = min((i + 1) * fold_size, n)
        if test_start < fold_size:
            continue

        test_prices = prices.iloc[test_start:test_end]
        if len(test_prices) < 30:
            continue

        full_sig = signal_fn(prices.iloc[:test_end])
        test_sig = full_sig.iloc[test_start:test_end]

        ret = test_prices['close'].pct_change().fillna(0)
        common = ret.index.intersection(test_sig.index)
        ret = ret.loc[common]
        test_sig = test_sig.loc[common]
        strat_ret = (test_sig.shift(1) * ret).fillna(0)
        sig_change = test_sig.diff().abs().fillna(0)
        strat_ret = strat_ret - sig_change * 10 / 10000

        std = float(strat_ret.std())
        sh = float(strat_ret.mean()) / std * np.sqrt(ppy) if std > 0 else 0
        results.append(round(sh, 3))

    return results

def sequential_halves_test(prices_df, signal_fn, freq='daily'):
    ppy = {'daily': 365, 'hourly': 8760, '4h': 2190}[freq]
    n = len(prices_df)
    mid = n // 2

    results = []
    for start, end in [(0, mid), (mid, n)]:
        seg = prices_df.iloc[start:end]
        sig = signal_fn(seg)
        ret = seg['close'].pct_change().fillna(0)
        common = ret.index.intersection(sig.index)
        ret = ret.loc[common]
        sig = sig.loc[common]
        strat_ret = (sig.shift(1) * ret).fillna(0)
        sig_change = sig.diff().abs().fillna(0)
        strat_ret = strat_ret - sig_change * 10 / 10000
        std = float(strat_ret.std())
        sh = float(strat_ret.mean()) / std * np.sqrt(ppy) if std > 0 else 0
        results.append(round(sh, 3))

    return results


# ============================================================
# SIGNAL GENERATORS
# ============================================================

def eth_daily_vol_breakout(df_daily, mom_period=10, vol_mult=1.5):
    """ETH daily volume breakout — same logic as H-617 at daily."""
    close = df_daily['close']
    volume = df_daily['volume']
    ret = close.pct_change(mom_period)
    vol_ma = volume.rolling(mom_period * 3).mean()

    signal = pd.Series(0.0, index=close.index)
    prev = 0
    for i in range(1, len(close)):
        v = volume.iloc[i-1]
        vma = vol_ma.iloc[i-1]
        r = ret.iloc[i-1]
        if pd.isna(vma) or pd.isna(r):
            signal.iloc[i] = prev
            continue
        if v > vol_mult * vma:
            prev = 1 if r > 0 else -1
        signal.iloc[i] = prev
    return signal


def multi_asset_daily_momentum(assets=['ETH', 'SOL', 'BTC'], lookback=20):
    """Equal-weight momentum across multiple assets daily."""
    daily_data = {}
    for a in assets:
        daily_data[a] = load_daily(a)

    common_idx = daily_data[assets[0]].index
    for a in assets[1:]:
        common_idx = common_idx.intersection(daily_data[a].index)

    all_signals = {}
    for a in assets:
        close = daily_data[a].loc[common_idx, 'close']
        mom = close.pct_change(lookback)
        sig = mom.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        all_signals[a] = sig

    combined = pd.DataFrame(all_signals).mean(axis=1)
    combined = combined.apply(lambda x: 1 if x > 0.3 else (-1 if x < -0.3 else 0))

    return common_idx, combined, daily_data


def funding_rate_ts(symbol='BTC', ma_fast=9, ma_slow=27):
    """TS strategy on individual coin funding rate — momentum of funding."""
    funding = load_funding(symbol)
    daily_price = load_daily(symbol)

    fr = funding['funding_rate'].resample('1D').sum()
    fr_fast = fr.rolling(ma_fast).mean()
    fr_slow = fr.rolling(ma_slow).mean()

    signal = pd.Series(0.0, index=fr.index)
    for i in range(1, len(fr)):
        if pd.isna(fr_fast.iloc[i-1]) or pd.isna(fr_slow.iloc[i-1]):
            continue
        if fr_fast.iloc[i-1] > fr_slow.iloc[i-1] and fr_fast.iloc[i-1] > 0:
            signal.iloc[i] = -1  # High funding = short (contrarian)
        elif fr_fast.iloc[i-1] < fr_slow.iloc[i-1] and fr_fast.iloc[i-1] < 0:
            signal.iloc[i] = 1  # Low/negative funding = long (contrarian)

    common = daily_price.index.intersection(signal.index)
    return daily_price.loc[common], signal.loc[common]


def oi_change_ts(symbol='BTC', lookback=5, threshold=0.1):
    """Trade based on OI changes — rising OI + price = trend continuation."""
    oi = load_oi_daily(symbol)
    price = load_daily(symbol)

    common = price.index.intersection(oi.index)
    price = price.loc[common]
    oi = oi.loc[common]

    oi_col = oi.columns[0] if len(oi.columns) > 0 else None
    if oi_col is None:
        return price, pd.Series(0, index=price.index)

    oi_vals = oi[oi_col]
    oi_change = oi_vals.pct_change(lookback)
    price_change = price['close'].pct_change(lookback)

    signal = pd.Series(0.0, index=price.index)
    for i in range(1, len(price)):
        oi_c = oi_change.iloc[i-1] if i-1 < len(oi_change) else np.nan
        p_c = price_change.iloc[i-1] if i-1 < len(price_change) else np.nan
        if pd.isna(oi_c) or pd.isna(p_c):
            continue
        if oi_c > threshold and p_c > 0:
            signal.iloc[i] = 1
        elif oi_c > threshold and p_c < 0:
            signal.iloc[i] = -1
        elif oi_c < -threshold:
            signal.iloc[i] = 0

    return price, signal


def eth_sol_momentum_switch(lookback=20, vol_lookback=20):
    """Trade ETH or SOL based on which has stronger momentum, with vol filter."""
    eth = load_daily('ETH')
    sol = load_daily('SOL')

    common = eth.index.intersection(sol.index)
    eth = eth.loc[common]
    sol = sol.loc[common]

    eth_mom = eth['close'].pct_change(lookback)
    sol_mom = sol['close'].pct_change(lookback)
    eth_vol = eth['close'].pct_change().rolling(vol_lookback).std()
    sol_vol = sol['close'].pct_change().rolling(vol_lookback).std()

    eth_sharpe = eth_mom / eth_vol.replace(0, np.nan)
    sol_sharpe = sol_mom / sol_vol.replace(0, np.nan)

    signal_eth = pd.Series(0.0, index=common)
    signal_sol = pd.Series(0.0, index=common)

    for i in range(1, len(common)):
        es = eth_sharpe.iloc[i-1]
        ss = sol_sharpe.iloc[i-1]
        if pd.isna(es) or pd.isna(ss):
            continue
        if es > ss and es > 0:
            signal_eth.iloc[i] = 1
        elif ss > es and ss > 0:
            signal_sol.iloc[i] = 1
        elif es < ss and es < 0:
            signal_eth.iloc[i] = -1
        elif ss < es and ss < 0:
            signal_sol.iloc[i] = -1

    eth_ret = eth['close'].pct_change().fillna(0)
    sol_ret = sol['close'].pct_change().fillna(0)
    combined_ret = (signal_eth.shift(1) * eth_ret + signal_sol.shift(1) * sol_ret) / 2
    combined_ret = combined_ret.fillna(0)

    equity = 10000 * (1 + combined_ret).cumprod()
    return equity, combined_ret, signal_eth, signal_sol, common, eth, sol


def btc_vol_regime_trade(vol_lookback=30, vol_threshold=0.5):
    """Trade BTC differently in high vs low vol regimes. Low vol: buy dips. High vol: momentum."""
    btc = load_daily('BTC')
    close = btc['close']
    ret = close.pct_change()
    vol = ret.rolling(vol_lookback).std()
    vol_pct = vol.rolling(365).rank(pct=True)

    mom_20 = close.pct_change(20)

    signal = pd.Series(0.0, index=close.index)
    for i in range(1, len(close)):
        vp = vol_pct.iloc[i-1]
        m = mom_20.iloc[i-1]
        if pd.isna(vp) or pd.isna(m):
            continue
        if vp < vol_threshold:
            # Low vol regime: mean-reversion / buy dips
            ret_5d = close.pct_change(5).iloc[i-1]
            if pd.isna(ret_5d):
                continue
            signal.iloc[i] = 1 if ret_5d < -0.02 else (0 if ret_5d > 0.02 else signal.iloc[i-1])
        else:
            # High vol regime: momentum
            signal.iloc[i] = 1 if m > 0 else -1

    return btc, signal


def intraday_vol_pattern(symbol='BTC', lookback=20):
    """Trade based on intraday volume distribution pattern — rising volume into close is bullish."""
    df_1h = load_hourly(symbol)

    # Compute daily: ratio of volume in last 8 hours vs first 16 hours
    daily = df_1h.resample('1D').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna()

    # Split volume by session
    df_1h['hour'] = df_1h.index.hour
    late_vol = df_1h[df_1h['hour'] >= 16]['volume'].resample('1D').sum()
    early_vol = df_1h[df_1h['hour'] < 16]['volume'].resample('1D').sum()

    common = daily.index.intersection(late_vol.index).intersection(early_vol.index)
    daily = daily.loc[common]
    vol_ratio = (late_vol.loc[common] / early_vol.loc[common].replace(0, np.nan)).fillna(1)
    vol_ratio_ma = vol_ratio.rolling(lookback).mean()

    signal = pd.Series(0.0, index=common)
    for i in range(1, len(common)):
        vr = vol_ratio.iloc[i-1]
        vrma = vol_ratio_ma.iloc[i-1]
        if pd.isna(vrma):
            continue
        if vr > vrma * 1.2:
            signal.iloc[i] = 1  # Rising late-session volume = bullish
        elif vr < vrma * 0.8:
            signal.iloc[i] = -1  # Declining late-session volume = bearish

    return daily, signal


def multi_coin_funding_contrarian():
    """Contrarian on aggregate funding across top coins."""
    coins = ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP']
    all_fr = {}
    for c in coins:
        try:
            fr = load_funding(c)
            all_fr[c] = fr['funding_rate'].resample('1D').sum()
        except:
            pass

    fr_df = pd.DataFrame(all_fr).dropna()
    avg_fr = fr_df.mean(axis=1)
    avg_fr_ma = avg_fr.rolling(14).mean()

    btc = load_daily('BTC')
    common = btc.index.intersection(avg_fr.index)
    btc = btc.loc[common]
    avg_fr = avg_fr.loc[common]
    avg_fr_ma = avg_fr_ma.loc[common]

    signal = pd.Series(0.0, index=common)
    for i in range(1, len(common)):
        fr_val = avg_fr.iloc[i-1]
        fr_ma = avg_fr_ma.iloc[i-1]
        if pd.isna(fr_ma):
            continue
        # Contrarian: high aggregate funding = short, low = long
        if fr_val > fr_ma and fr_val > 0.0003:
            signal.iloc[i] = -1
        elif fr_val < fr_ma and fr_val < -0.0001:
            signal.iloc[i] = 1

    return btc, signal


# ============================================================
# MAIN
# ============================================================

def run_batch():
    print("="*60)
    print("SESSION 180 BATCH 2: Daily TS + Funding + OI Strategies")
    print("="*60)

    all_results = {}

    # H-644: ETH Daily Volume Breakout
    print(f"\n{'='*60}")
    print("H-644: ETH Daily Volume Breakout")
    try:
        eth = load_daily('ETH')
        sig_fn = lambda df: eth_daily_vol_breakout(df, 10, 1.5)
        sig = sig_fn(eth)
        res = backtest_ts(eth['close'], sig, freq='daily')
        print(f"  IS: Sharpe {res['sharpe']}, Ann {res['ann_ret']*100:.1f}%, DD {res['max_dd']*100:.1f}%")
        if res['sharpe'] < 0.5:
            print(f"  ** REJECTED (IS Sharpe < 0.5)")
            all_results['H-644'] = {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', 'sharpe': res['sharpe']}
        else:
            wf = walk_forward_ts(eth, sig_fn, n_folds=7, freq='daily')
            wf_pos = sum(1 for w in wf if w > 0)
            sh = sequential_halves_test(eth, sig_fn, freq='daily')
            print(f"  WF: {wf_pos}/{len(wf)} positive, folds={wf}")
            print(f"  SH: H1={sh[0]}, H2={sh[1]} {'PASS' if sh[0]>0 and sh[1]>0 else 'FAIL'}")
            all_results['H-644'] = {'status': 'CONFIRMED' if sh[0]>0 and sh[1]>0 and wf_pos>=3 else 'BORDERLINE',
                                     'sharpe': res['sharpe'], 'wf': wf, 'sh': sh, 'ann_ret': res['ann_ret'], 'max_dd': res['max_dd']}
    except Exception as e:
        print(f"  ERROR: {e}")
        all_results['H-644'] = {'status': 'ERROR', 'error': str(e)}

    # H-645: SOL Daily Volume Breakout
    print(f"\n{'='*60}")
    print("H-645: SOL Daily Volume Breakout")
    try:
        sol = load_daily('SOL')
        sig_fn = lambda df: eth_daily_vol_breakout(df, 10, 1.5)
        sig = sig_fn(sol)
        res = backtest_ts(sol['close'], sig, freq='daily')
        print(f"  IS: Sharpe {res['sharpe']}, Ann {res['ann_ret']*100:.1f}%, DD {res['max_dd']*100:.1f}%")
        if res['sharpe'] < 0.5:
            print(f"  ** REJECTED (IS Sharpe < 0.5)")
            all_results['H-645'] = {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', 'sharpe': res['sharpe']}
        else:
            wf = walk_forward_ts(sol, sig_fn, n_folds=7, freq='daily')
            wf_pos = sum(1 for w in wf if w > 0)
            sh = sequential_halves_test(sol, sig_fn, freq='daily')
            print(f"  WF: {wf_pos}/{len(wf)} positive, folds={wf}")
            print(f"  SH: H1={sh[0]}, H2={sh[1]} {'PASS' if sh[0]>0 and sh[1]>0 else 'FAIL'}")
            all_results['H-645'] = {'status': 'CONFIRMED' if sh[0]>0 and sh[1]>0 and wf_pos>=3 else 'BORDERLINE',
                                     'sharpe': res['sharpe'], 'wf': wf, 'sh': sh, 'ann_ret': res['ann_ret'], 'max_dd': res['max_dd']}
    except Exception as e:
        print(f"  ERROR: {e}")
        all_results['H-645'] = {'status': 'ERROR', 'error': str(e)}

    # H-646: BTC Funding Rate TS (Contrarian)
    print(f"\n{'='*60}")
    print("H-646: BTC Funding Rate TS (Contrarian)")
    try:
        btc_prices, fr_sig = funding_rate_ts('BTC', 9, 27)
        res = backtest_ts(btc_prices['close'], fr_sig, freq='daily')
        print(f"  IS: Sharpe {res['sharpe']}, Ann {res['ann_ret']*100:.1f}%, DD {res['max_dd']*100:.1f}%, Bars {res['n_bars']}")
        if res['sharpe'] < 0.5:
            print(f"  ** REJECTED (IS Sharpe < 0.5)")
            all_results['H-646'] = {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', 'sharpe': res['sharpe']}
        else:
            def fr_sig_fn(df):
                _, sig = funding_rate_ts('BTC', 9, 27)
                common = df.index.intersection(sig.index)
                return sig.loc[common]
            wf = walk_forward_ts(btc_prices, fr_sig_fn, n_folds=6, freq='daily')
            wf_pos = sum(1 for w in wf if w > 0)
            sh = sequential_halves_test(btc_prices, fr_sig_fn, freq='daily')
            print(f"  WF: {wf_pos}/{len(wf)} positive, folds={wf}")
            print(f"  SH: H1={sh[0]}, H2={sh[1]} {'PASS' if sh[0]>0 and sh[1]>0 else 'FAIL'}")
            all_results['H-646'] = {'status': 'CONFIRMED' if sh[0]>0 and sh[1]>0 and wf_pos>=3 else 'BORDERLINE',
                                     'sharpe': res['sharpe'], 'wf': wf, 'sh': sh, 'ann_ret': res['ann_ret'], 'max_dd': res['max_dd']}
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback; traceback.print_exc()
        all_results['H-646'] = {'status': 'ERROR', 'error': str(e)}

    # H-647: ETH Funding Rate TS (Contrarian)
    print(f"\n{'='*60}")
    print("H-647: ETH Funding Rate TS (Contrarian)")
    try:
        eth_prices, fr_sig = funding_rate_ts('ETH', 9, 27)
        res = backtest_ts(eth_prices['close'], fr_sig, freq='daily')
        print(f"  IS: Sharpe {res['sharpe']}, Ann {res['ann_ret']*100:.1f}%, DD {res['max_dd']*100:.1f}%, Bars {res['n_bars']}")
        if res['sharpe'] < 0.5:
            print(f"  ** REJECTED (IS Sharpe < 0.5)")
            all_results['H-647'] = {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', 'sharpe': res['sharpe']}
        else:
            print(f"  ** Passes IS threshold, further testing needed")
            all_results['H-647'] = {'status': 'BORDERLINE', 'sharpe': res['sharpe'], 'ann_ret': res['ann_ret'], 'max_dd': res['max_dd']}
    except Exception as e:
        print(f"  ERROR: {e}")
        all_results['H-647'] = {'status': 'ERROR', 'error': str(e)}

    # H-648: BTC OI Change TS
    print(f"\n{'='*60}")
    print("H-648: BTC OI Change TS")
    try:
        btc_prices, oi_sig = oi_change_ts('BTC', 5, 0.1)
        res = backtest_ts(btc_prices['close'], oi_sig, freq='daily')
        print(f"  IS: Sharpe {res['sharpe']}, Ann {res['ann_ret']*100:.1f}%, DD {res['max_dd']*100:.1f}%, Bars {res['n_bars']}")
        if res['sharpe'] < 0.5:
            print(f"  ** REJECTED (IS Sharpe < 0.5)")
            all_results['H-648'] = {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', 'sharpe': res['sharpe']}
        else:
            print(f"  ** Passes IS threshold, further testing needed")
            all_results['H-648'] = {'status': 'BORDERLINE', 'sharpe': res['sharpe'], 'ann_ret': res['ann_ret'], 'max_dd': res['max_dd']}
    except Exception as e:
        print(f"  ERROR: {e}")
        all_results['H-648'] = {'status': 'ERROR', 'error': str(e)}

    # H-649: BTC Vol Regime Switch
    print(f"\n{'='*60}")
    print("H-649: BTC Vol Regime Switch")
    try:
        btc_prices, vol_sig = btc_vol_regime_trade(30, 0.5)
        res = backtest_ts(btc_prices['close'], vol_sig, freq='daily')
        print(f"  IS: Sharpe {res['sharpe']}, Ann {res['ann_ret']*100:.1f}%, DD {res['max_dd']*100:.1f}%, Bars {res['n_bars']}")
        if res['sharpe'] < 0.5:
            print(f"  ** REJECTED (IS Sharpe < 0.5)")
            all_results['H-649'] = {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', 'sharpe': res['sharpe']}
        else:
            def vol_sig_fn(df):
                _, sig = btc_vol_regime_trade(30, 0.5)
                common = df.index.intersection(sig.index)
                return sig.loc[common]
            wf = walk_forward_ts(btc_prices, vol_sig_fn, n_folds=7, freq='daily')
            wf_pos = sum(1 for w in wf if w > 0)
            sh = sequential_halves_test(btc_prices, vol_sig_fn, freq='daily')
            print(f"  WF: {wf_pos}/{len(wf)} positive, folds={wf}")
            print(f"  SH: H1={sh[0]}, H2={sh[1]} {'PASS' if sh[0]>0 and sh[1]>0 else 'FAIL'}")
            all_results['H-649'] = {'status': 'CONFIRMED' if sh[0]>0 and sh[1]>0 and wf_pos>=3 else 'BORDERLINE',
                                     'sharpe': res['sharpe'], 'wf': wf, 'sh': sh, 'ann_ret': res['ann_ret'], 'max_dd': res['max_dd']}
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback; traceback.print_exc()
        all_results['H-649'] = {'status': 'ERROR', 'error': str(e)}

    # H-650: Intraday Volume Pattern (BTC)
    print(f"\n{'='*60}")
    print("H-650: BTC Intraday Volume Distribution Pattern")
    try:
        btc_prices, iv_sig = intraday_vol_pattern('BTC', 20)
        res = backtest_ts(btc_prices['close'], iv_sig, freq='daily')
        print(f"  IS: Sharpe {res['sharpe']}, Ann {res['ann_ret']*100:.1f}%, DD {res['max_dd']*100:.1f}%, Bars {res['n_bars']}")
        if res['sharpe'] < 0.5:
            print(f"  ** REJECTED (IS Sharpe < 0.5)")
            all_results['H-650'] = {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', 'sharpe': res['sharpe']}
        else:
            print(f"  ** Passes IS threshold")
            all_results['H-650'] = {'status': 'BORDERLINE', 'sharpe': res['sharpe'], 'ann_ret': res['ann_ret'], 'max_dd': res['max_dd']}
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback; traceback.print_exc()
        all_results['H-650'] = {'status': 'ERROR', 'error': str(e)}

    # H-651: Multi-Coin Aggregate Funding Contrarian
    print(f"\n{'='*60}")
    print("H-651: Multi-Coin Aggregate Funding Contrarian")
    try:
        btc_prices, mc_sig = multi_coin_funding_contrarian()
        res = backtest_ts(btc_prices['close'], mc_sig, freq='daily')
        print(f"  IS: Sharpe {res['sharpe']}, Ann {res['ann_ret']*100:.1f}%, DD {res['max_dd']*100:.1f}%, Bars {res['n_bars']}")
        if res['sharpe'] < 0.5:
            print(f"  ** REJECTED (IS Sharpe < 0.5)")
            all_results['H-651'] = {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', 'sharpe': res['sharpe']}
        else:
            def mc_sig_fn(df):
                _, sig = multi_coin_funding_contrarian()
                common = df.index.intersection(sig.index)
                return sig.loc[common]
            wf = walk_forward_ts(btc_prices, mc_sig_fn, n_folds=6, freq='daily')
            wf_pos = sum(1 for w in wf if w > 0)
            sh = sequential_halves_test(btc_prices, mc_sig_fn, freq='daily')
            print(f"  WF: {wf_pos}/{len(wf)} positive, folds={wf}")
            print(f"  SH: H1={sh[0]}, H2={sh[1]} {'PASS' if sh[0]>0 and sh[1]>0 else 'FAIL'}")
            all_results['H-651'] = {'status': 'CONFIRMED' if sh[0]>0 and sh[1]>0 and wf_pos>=3 else 'BORDERLINE',
                                     'sharpe': res['sharpe'], 'wf': wf, 'sh': sh, 'ann_ret': res['ann_ret'], 'max_dd': res['max_dd']}
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback; traceback.print_exc()
        all_results['H-651'] = {'status': 'ERROR', 'error': str(e)}

    # SUMMARY
    print(f"\n\n{'='*60}")
    print("BATCH 2 SUMMARY")
    print(f"{'='*60}")
    for h_id, r in all_results.items():
        status = r.get('status', 'UNKNOWN')
        sharpe = r.get('sharpe', 'N/A')
        print(f"  {h_id}: {status} (Sharpe={sharpe})")

if __name__ == '__main__':
    run_batch()
