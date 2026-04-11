#!/usr/bin/env python3
"""
Session 180 Batch 3: Creative TS approaches
H-652 through H-659: ETH/BTC ratio, monthly seasonality, vol-of-vol,
multi-TF confirmation, realized skew, 4h XS momentum.
"""
import sys, json, warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings('ignore')

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

def load_hourly(symbol='BTC'):
    return pd.read_parquet(DATA_DIR / f'{symbol}_USDT_1h.parquet')

def load_daily(symbol='BTC'):
    df = load_hourly(symbol)
    return df.resample('1D').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna()

def resample_4h(df_1h):
    return df_1h.resample('4h').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna()

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
        'equity': equity, 'sharpe': round(sharpe, 3), 'ann_ret': round(ann_ret, 4),
        'max_dd': round(dd, 4), 'n_trades': n_trades, 'win_rate': round(wr, 3), 'n_bars': n
    }

def walk_forward_ts(prices_df, signal_fn, n_folds=7, freq='daily'):
    ppy = {'daily': 365, 'hourly': 8760, '4h': 2190}[freq]
    n = len(prices_df)
    fold_size = n // n_folds
    results = []
    for i in range(n_folds):
        test_start = i * fold_size
        test_end = min((i + 1) * fold_size, n)
        if test_start < fold_size:
            continue
        test_prices = prices_df.iloc[test_start:test_end]
        if len(test_prices) < 30:
            continue
        full_sig = signal_fn(prices_df.iloc[:test_end])
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

def eth_btc_ratio_momentum(lookback=20):
    """H-652: Trade BTC based on ETH/BTC ratio trend. Rising ETH/BTC = risk-on = long BTC."""
    btc = load_daily('BTC')
    eth = load_daily('ETH')
    common = btc.index.intersection(eth.index)
    btc = btc.loc[common]
    eth = eth.loc[common]

    ratio = eth['close'] / btc['close']
    ratio_mom = ratio.pct_change(lookback)

    signal = pd.Series(0.0, index=common)
    for i in range(1, len(common)):
        r = ratio_mom.iloc[i-1]
        if pd.isna(r):
            continue
        signal.iloc[i] = 1 if r > 0 else -1

    return btc, signal


def eth_btc_ratio_mean_reversion(lookback=60, z_threshold=1.5):
    """H-653: Mean-revert on ETH/BTC ratio — extreme deviation signals reversal."""
    btc = load_daily('BTC')
    eth = load_daily('ETH')
    common = btc.index.intersection(eth.index)
    btc = btc.loc[common]
    eth = eth.loc[common]

    ratio = eth['close'] / btc['close']
    ratio_ma = ratio.rolling(lookback).mean()
    ratio_std = ratio.rolling(lookback).std()
    z_score = (ratio - ratio_ma) / ratio_std.replace(0, np.nan)

    signal = pd.Series(0.0, index=common)
    pos = 0
    for i in range(1, len(common)):
        z = z_score.iloc[i-1]
        if pd.isna(z):
            signal.iloc[i] = pos
            continue
        if z > z_threshold:
            pos = -1  # ETH overvalued vs BTC → short ETH (or long BTC)
        elif z < -z_threshold:
            pos = 1  # ETH undervalued vs BTC → long ETH (or short BTC relative)
        elif abs(z) < 0.5:
            pos = 0  # Revert to flat near mean
        signal.iloc[i] = pos

    # Trade BTC in direction: signal=1 means BTC strong (short BTC? No: if ETH undervalued, BTC overvalued → short BTC)
    # Actually: z > threshold means ETH high vs BTC → BTC should catch up → long BTC
    # Let's trade BTC: long when ratio high (BTC underperforming, reversion trade = long BTC)
    return btc, signal


def monthly_calendar_effect(symbol='BTC'):
    """H-654: Day-of-month effects. Test for month-start and month-end patterns."""
    daily = load_daily(symbol)
    close = daily['close']

    signal = pd.Series(0.0, index=close.index)
    for i in range(1, len(close)):
        dom = close.index[i-1].day
        # Month-end (last 3 days) and month-start (first 3 days) tend bullish in crypto
        if dom <= 3 or dom >= 28:
            signal.iloc[i] = 1
        elif 14 <= dom <= 16:
            signal.iloc[i] = -1  # Mid-month weakness
        else:
            signal.iloc[i] = 0

    return daily, signal


def vol_of_vol_signal(symbol='BTC', vol_lb=20, vov_lb=20):
    """H-655: Volatility-of-volatility. Low VoV = stable trends, high VoV = choppy."""
    daily = load_daily(symbol)
    close = daily['close']
    ret = close.pct_change()
    vol = ret.rolling(vol_lb).std()
    vov = vol.rolling(vov_lb).std()
    vov_pct = vov.rolling(252).rank(pct=True)

    mom_20 = close.pct_change(20)

    signal = pd.Series(0.0, index=close.index)
    for i in range(1, len(close)):
        vp = vov_pct.iloc[i-1]
        m = mom_20.iloc[i-1]
        if pd.isna(vp) or pd.isna(m):
            continue
        if vp < 0.4:
            # Low VoV = stable regime → trend-follow
            signal.iloc[i] = 1 if m > 0 else -1
        else:
            # High VoV = choppy → stay flat
            signal.iloc[i] = 0

    return daily, signal


def multi_tf_btc_confirmation(daily_lookback=20, h4_lookback=12):
    """H-656: Multi-TF BTC — long only when daily AND 4h both bullish. Refined from H-572."""
    btc_1h = load_hourly('BTC')
    btc_4h = resample_4h(btc_1h)
    btc_daily = load_daily('BTC')

    # Daily trend
    daily_mom = btc_daily['close'].pct_change(daily_lookback)
    daily_signal = daily_mom.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0) if not pd.isna(x) else 0)

    # 4h volume breakout (proven in H-617)
    close_4h = btc_4h['close']
    vol_4h = btc_4h['volume']
    ret_4h = close_4h.pct_change(h4_lookback)
    vol_ma_4h = vol_4h.rolling(h4_lookback * 4).mean()

    h4_signal = pd.Series(0.0, index=close_4h.index)
    prev = 0
    for i in range(1, len(close_4h)):
        v = vol_4h.iloc[i-1]
        vma = vol_ma_4h.iloc[i-1]
        r = ret_4h.iloc[i-1]
        if pd.isna(vma) or pd.isna(r):
            h4_signal.iloc[i] = prev
            continue
        if v > 1.5 * vma:
            prev = 1 if r > 0 else -1
        h4_signal.iloc[i] = prev

    # Resample 4h signal to daily (take last signal of day)
    h4_daily = h4_signal.resample('1D').last().ffill()

    # Combine: only trade when both agree
    common = btc_daily.index.intersection(h4_daily.index).intersection(daily_signal.index)
    btc_daily = btc_daily.loc[common]
    d_sig = daily_signal.loc[common]
    h4_d_sig = h4_daily.loc[common]

    combined = pd.Series(0.0, index=common)
    for i in range(1, len(common)):
        ds = d_sig.iloc[i-1]
        hs = h4_d_sig.iloc[i-1]
        if ds == hs:
            combined.iloc[i] = ds
        else:
            combined.iloc[i] = 0  # Disagree → flat

    return btc_daily, combined


def realized_skew_signal(symbol='BTC', lookback=30):
    """H-657: Realized skew — positive skew = upside risk, negative = downside risk."""
    daily = load_daily(symbol)
    ret = daily['close'].pct_change()

    from scipy.stats import skew as skew_fn

    signal = pd.Series(0.0, index=daily.index)
    for i in range(lookback + 1, len(daily)):
        window = ret.iloc[i-lookback:i].dropna()
        if len(window) < 20:
            continue
        sk = skew_fn(window)
        # Negative skew = crash risk → go short. Positive skew = upside → long.
        if sk > 0.5:
            signal.iloc[i] = 1
        elif sk < -0.5:
            signal.iloc[i] = -1

    return daily, signal


def xs_momentum_4h(assets=['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'AVAX', 'LINK', 'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM', 'SUI'],
                    lookback=48, n_top=4, rebal_period=6):
    """H-658: Cross-sectional momentum at 4h frequency. Faster version of daily XS (H-012)."""
    data_4h = {}
    for a in assets:
        try:
            df = resample_4h(load_hourly(a))
            data_4h[a] = df
        except:
            pass

    common_idx = data_4h[assets[0]].index
    for a in list(data_4h.keys())[1:]:
        common_idx = common_idx.intersection(data_4h[a].index)

    closes = pd.DataFrame({a: data_4h[a].loc[common_idx, 'close'] for a in data_4h})
    rets = closes.pct_change(lookback)

    n = len(common_idx)
    all_positions = pd.DataFrame(0.0, index=common_idx, columns=list(data_4h.keys()))

    rebal_counter = 0
    current_longs = []
    current_shorts = []

    for i in range(lookback + 1, n):
        rebal_counter += 1
        if rebal_counter >= rebal_period or not current_longs:
            row = rets.iloc[i-1].dropna()
            if len(row) < 2 * n_top:
                if current_longs:
                    for a in current_longs:
                        all_positions.iloc[i][a] = 1.0 / n_top
                    for a in current_shorts:
                        all_positions.iloc[i][a] = -1.0 / n_top
                continue

            ranked = row.sort_values()
            current_shorts = ranked.index[:n_top].tolist()
            current_longs = ranked.index[-n_top:].tolist()
            rebal_counter = 0

        for a in current_longs:
            all_positions.iloc[i][a] = 1.0 / n_top
        for a in current_shorts:
            all_positions.iloc[i][a] = -1.0 / n_top

    # Compute portfolio return
    asset_rets = closes.pct_change().fillna(0)
    port_ret = (all_positions.shift(1) * asset_rets).sum(axis=1)
    # Fee: count position changes
    pos_changes = all_positions.diff().abs().sum(axis=1)
    port_ret = port_ret - pos_changes * 10 / 10000

    equity = 10000 * (1 + port_ret).cumprod()

    ppy = 2190
    years = n / ppy
    total_ret = equity.iloc[-1] / equity.iloc[0] - 1
    ann_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
    sharpe = float(port_ret.mean() / port_ret.std() * np.sqrt(ppy)) if float(port_ret.std()) > 0 else 0
    peak = equity.cummax()
    dd = float(abs(((equity - peak) / peak).min()))
    n_trades = int(pos_changes.sum())
    win = int((port_ret > 0).sum())
    loss = int((port_ret < 0).sum())
    wr = win / (win + loss) if (win + loss) > 0 else 0

    return {
        'sharpe': round(sharpe, 3), 'ann_ret': round(ann_ret, 4),
        'max_dd': round(dd, 4), 'n_trades': n_trades, 'win_rate': round(wr, 3),
        'n_bars': n, 'equity': equity, 'port_ret': port_ret
    }


def btc_dominance_proxy_signal(lookback=20):
    """H-659: BTC dominance proxy — when BTC outperforms alts, stay long BTC."""
    btc = load_daily('BTC')
    eth = load_daily('ETH')
    sol = load_daily('SOL')

    common = btc.index.intersection(eth.index).intersection(sol.index)
    btc = btc.loc[common]
    eth = eth.loc[common]
    sol = sol.loc[common]

    btc_ret = btc['close'].pct_change(lookback)
    alt_ret = (eth['close'].pct_change(lookback) + sol['close'].pct_change(lookback)) / 2
    dominance_change = btc_ret - alt_ret  # positive = BTC outperforming

    signal = pd.Series(0.0, index=common)
    for i in range(1, len(common)):
        dc = dominance_change.iloc[i-1]
        if pd.isna(dc):
            continue
        # When BTC is outperforming alts: long BTC (trend continuation)
        if dc > 0.05:
            signal.iloc[i] = 1
        elif dc < -0.05:
            signal.iloc[i] = -1

    return btc, signal


# ============================================================
# MAIN
# ============================================================

def full_test(name, h_id, prices_df, signal, signal_fn=None, freq='daily'):
    """Run full test suite for a TS signal."""
    print(f"\n{'='*60}")
    print(f"{h_id}: {name}")

    res = backtest_ts(prices_df['close'], signal, freq=freq)
    print(f"  IS: Sharpe {res['sharpe']}, Ann {res['ann_ret']*100:.1f}%, DD {res['max_dd']*100:.1f}%, Trades {res['n_trades']}, Bars {res['n_bars']}")

    if res['sharpe'] < 0.5:
        print(f"  ** REJECTED (IS Sharpe < 0.5)")
        return {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', 'sharpe': res['sharpe']}

    if signal_fn:
        wf = walk_forward_ts(prices_df, signal_fn, n_folds=7, freq=freq)
        wf_pos = sum(1 for w in wf if w > 0)
        sh = sequential_halves_test(prices_df, signal_fn, freq=freq)

        print(f"  WF: {wf_pos}/{len(wf)} positive, folds={wf}")
        print(f"  SH: H1={sh[0]}, H2={sh[1]} {'PASS' if sh[0]>0 and sh[1]>0 else 'FAIL'}")

        # BTC correlation
        btc = load_daily('BTC')
        btc_ret = btc['close'].pct_change()
        strat_ret = (signal.shift(1) * prices_df['close'].pct_change()).fillna(0)
        common_idx = btc_ret.index.intersection(strat_ret.index)
        btc_corr = btc_ret.loc[common_idx].corr(strat_ret.loc[common_idx])
        print(f"  BTC corr: {btc_corr:.3f}")

        is_confirmed = sh[0] > 0 and sh[1] > 0 and wf_pos >= 3
        status = 'CONFIRMED' if is_confirmed else 'BORDERLINE'
        print(f"  ** {status}")

        return {
            'status': status, 'sharpe': res['sharpe'], 'ann_ret': res['ann_ret'],
            'max_dd': res['max_dd'], 'wf': wf, 'wf_pos': wf_pos,
            'sh': sh, 'btc_corr': round(btc_corr, 3), 'n_bars': res['n_bars']
        }
    else:
        return {'status': 'BORDERLINE', 'sharpe': res['sharpe'], 'ann_ret': res['ann_ret'], 'max_dd': res['max_dd']}


def run_batch():
    print("="*60)
    print("SESSION 180 BATCH 3: Creative TS Approaches")
    print("="*60)

    all_results = {}

    # H-652: ETH/BTC Ratio Momentum
    try:
        prices, signal = eth_btc_ratio_momentum(20)
        def sig_fn(df):
            _, s = eth_btc_ratio_momentum(20)
            common = df.index.intersection(s.index)
            return s.loc[common]
        all_results['H-652'] = full_test('ETH/BTC Ratio Momentum', 'H-652', prices, signal, sig_fn)
    except Exception as e:
        print(f"  H-652 ERROR: {e}")
        all_results['H-652'] = {'status': 'ERROR', 'error': str(e)}

    # H-653: ETH/BTC Ratio Mean-Reversion
    try:
        prices, signal = eth_btc_ratio_mean_reversion(60, 1.5)
        def sig_fn(df):
            _, s = eth_btc_ratio_mean_reversion(60, 1.5)
            common = df.index.intersection(s.index)
            return s.loc[common]
        all_results['H-653'] = full_test('ETH/BTC Ratio Mean-Reversion', 'H-653', prices, signal, sig_fn)
    except Exception as e:
        print(f"  H-653 ERROR: {e}")
        all_results['H-653'] = {'status': 'ERROR', 'error': str(e)}

    # H-654: Monthly Calendar Effect
    try:
        prices, signal = monthly_calendar_effect('BTC')
        def sig_fn(df):
            signal = pd.Series(0.0, index=df.index)
            for i in range(1, len(df)):
                dom = df.index[i-1].day
                if dom <= 3 or dom >= 28:
                    signal.iloc[i] = 1
                elif 14 <= dom <= 16:
                    signal.iloc[i] = -1
            return signal
        all_results['H-654'] = full_test('BTC Monthly Calendar Effect', 'H-654', prices, signal, sig_fn)
    except Exception as e:
        print(f"  H-654 ERROR: {e}")
        all_results['H-654'] = {'status': 'ERROR', 'error': str(e)}

    # H-655: Vol-of-Vol Signal
    try:
        prices, signal = vol_of_vol_signal('BTC', 20, 20)
        def sig_fn(df):
            _, s = vol_of_vol_signal('BTC', 20, 20)
            common = df.index.intersection(s.index)
            return s.loc[common]
        all_results['H-655'] = full_test('BTC Vol-of-Vol Signal', 'H-655', prices, signal, sig_fn)
    except Exception as e:
        print(f"  H-655 ERROR: {e}")
        all_results['H-655'] = {'status': 'ERROR', 'error': str(e)}

    # H-656: Multi-TF BTC Confirmation (Daily + 4h)
    try:
        prices, signal = multi_tf_btc_confirmation(20, 12)
        def sig_fn(df):
            _, s = multi_tf_btc_confirmation(20, 12)
            common = df.index.intersection(s.index)
            return s.loc[common]
        all_results['H-656'] = full_test('Multi-TF BTC Confirmation', 'H-656', prices, signal, sig_fn)
    except Exception as e:
        print(f"  H-656 ERROR: {e}")
        import traceback; traceback.print_exc()
        all_results['H-656'] = {'status': 'ERROR', 'error': str(e)}

    # H-657: Realized Skew Signal
    try:
        prices, signal = realized_skew_signal('BTC', 30)
        def sig_fn(df):
            _, s = realized_skew_signal('BTC', 30)
            common = df.index.intersection(s.index)
            return s.loc[common]
        all_results['H-657'] = full_test('BTC Realized Skew', 'H-657', prices, signal, sig_fn)
    except Exception as e:
        print(f"  H-657 ERROR: {e}")
        all_results['H-657'] = {'status': 'ERROR', 'error': str(e)}

    # H-658: XS Momentum at 4h Frequency
    print(f"\n{'='*60}")
    print("H-658: Cross-Sectional Momentum at 4h")
    try:
        res_4h = xs_momentum_4h(lookback=48, n_top=4, rebal_period=6)
        print(f"  IS: Sharpe {res_4h['sharpe']}, Ann {res_4h['ann_ret']*100:.1f}%, DD {res_4h['max_dd']*100:.1f}%, Trades {res_4h['n_trades']}, Bars {res_4h['n_bars']}")

        if res_4h['sharpe'] < 0.5:
            print(f"  ** REJECTED (IS Sharpe < 0.5)")
            all_results['H-658'] = {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', 'sharpe': res_4h['sharpe']}
        else:
            # WF for XS: test sequential halves on the portfolio return
            port_ret = res_4h['port_ret']
            mid = len(port_ret) // 2
            h1_ret = port_ret.iloc[:mid]
            h2_ret = port_ret.iloc[mid:]
            h1_sh = float(h1_ret.mean() / h1_ret.std() * np.sqrt(2190)) if float(h1_ret.std()) > 0 else 0
            h2_sh = float(h2_ret.mean() / h2_ret.std() * np.sqrt(2190)) if float(h2_ret.std()) > 0 else 0
            print(f"  SH: H1={h1_sh:.3f}, H2={h2_sh:.3f} {'PASS' if h1_sh>0 and h2_sh>0 else 'FAIL'}")

            # H-012 correlation
            h012_prices = load_daily('BTC')
            btc_ret_daily = h012_prices['close'].pct_change()
            port_daily = port_ret.resample('1D').sum()
            common_idx = btc_ret_daily.index.intersection(port_daily.index)
            corr_btc = btc_ret_daily.loc[common_idx].corr(port_daily.loc[common_idx])
            print(f"  BTC corr: {corr_btc:.3f}")

            all_results['H-658'] = {
                'status': 'CONFIRMED' if h1_sh > 0 and h2_sh > 0 else 'BORDERLINE',
                'sharpe': res_4h['sharpe'], 'ann_ret': res_4h['ann_ret'], 'max_dd': res_4h['max_dd'],
                'sh': [round(h1_sh, 3), round(h2_sh, 3)], 'btc_corr': round(corr_btc, 3),
            }
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback; traceback.print_exc()
        all_results['H-658'] = {'status': 'ERROR', 'error': str(e)}

    # H-659: BTC Dominance Proxy
    try:
        prices, signal = btc_dominance_proxy_signal(20)
        def sig_fn(df):
            _, s = btc_dominance_proxy_signal(20)
            common = df.index.intersection(s.index)
            return s.loc[common]
        all_results['H-659'] = full_test('BTC Dominance Proxy', 'H-659', prices, signal, sig_fn)
    except Exception as e:
        print(f"  H-659 ERROR: {e}")
        all_results['H-659'] = {'status': 'ERROR', 'error': str(e)}

    # SUMMARY
    print(f"\n\n{'='*60}")
    print("BATCH 3 SUMMARY")
    print(f"{'='*60}")
    for h_id, r in all_results.items():
        status = r.get('status', 'UNKNOWN')
        sharpe = r.get('sharpe', 'N/A')
        extra = ''
        if 'sh' in r:
            extra = f" SH={r['sh']}"
        if 'btc_corr' in r:
            extra += f" BTC_corr={r['btc_corr']}"
        print(f"  {h_id}: {status} (Sharpe={sharpe}{extra})")


if __name__ == '__main__':
    run_batch()
