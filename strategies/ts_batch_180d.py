#!/usr/bin/env python3
"""
Session 180 Batch 4: Higher-order moments and distributional TS signals.
H-660 through H-667: Kurtosis, tail ratio, Hurst exponent, autocorrelation,
and multi-asset realized skew variations.
H-657 (realized skew) worked — explore related distributional signals.
"""
import sys, json, warnings
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import skew as skew_fn, kurtosis as kurt_fn

warnings.filterwarnings('ignore')

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

def load_daily(symbol='BTC'):
    df = pd.read_parquet(DATA_DIR / f'{symbol}_USDT_1h.parquet')
    return df.resample('1D').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna()

def load_hourly(symbol='BTC'):
    return pd.read_parquet(DATA_DIR / f'{symbol}_USDT_1h.parquet')

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
        'max_dd': round(dd, 4), 'n_trades': n_trades, 'win_rate': round(wr, 3),
        'n_bars': n, 'strat_ret': strat_ret
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
        seg = prices_df.iloc[test_start:test_end]
        if len(seg) < 30:
            continue
        sig = signal_fn(prices_df.iloc[:test_end])
        test_sig = sig.iloc[test_start:test_end] if len(sig) > test_start else pd.Series(0, index=seg.index)
        ret = seg['close'].pct_change().fillna(0)
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

def sequential_halves(prices_df, signal_fn, freq='daily'):
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

def kurtosis_signal(daily, lookback=30, long_thresh=3.0, short_thresh=3.0):
    """H-660: Realized kurtosis — excess kurtosis indicates fat tails / regime instability."""
    ret = daily['close'].pct_change()
    signal = pd.Series(0.0, index=daily.index)
    for i in range(lookback + 1, len(daily)):
        window = ret.iloc[i-lookback:i].dropna()
        if len(window) < 20:
            continue
        k = kurt_fn(window)  # excess kurtosis
        # High kurtosis = fat tails, uncertainty → trade momentum direction
        mom = daily['close'].iloc[i-1] / daily['close'].iloc[max(0,i-lookback)] - 1
        if k > long_thresh:
            signal.iloc[i] = 1 if mom > 0 else -1
        # Low kurtosis = normal distribution, calm → trend-follow
        elif k < 0:
            signal.iloc[i] = 1 if mom > 0 else -1
    return signal

def tail_ratio_signal(daily, lookback=60, percentile=5):
    """H-661: Tail ratio — ratio of right tail to left tail magnitude. Asymmetric tails are predictive."""
    ret = daily['close'].pct_change()
    signal = pd.Series(0.0, index=daily.index)
    for i in range(lookback + 1, len(daily)):
        window = ret.iloc[i-lookback:i].dropna()
        if len(window) < 30:
            continue
        right_tail = np.percentile(window, 100 - percentile)
        left_tail = abs(np.percentile(window, percentile))
        if left_tail > 0:
            ratio = right_tail / left_tail
        else:
            ratio = 1
        # ratio > 1: right tail fatter → upside bias → long
        if ratio > 1.3:
            signal.iloc[i] = 1
        elif ratio < 0.7:
            signal.iloc[i] = -1
    return signal

def hurst_signal(daily, lookback=100):
    """H-662: Hurst exponent — H>0.5 trending, H<0.5 mean-reverting."""
    close = daily['close']
    signal = pd.Series(0.0, index=daily.index)

    for i in range(lookback + 1, len(daily)):
        window = close.iloc[i-lookback:i].values
        n = len(window)
        if n < 50:
            continue
        # Compute Hurst via R/S method
        ret_w = np.diff(np.log(window))
        mean_r = np.mean(ret_w)
        dev = np.cumsum(ret_w - mean_r)
        R = max(dev) - min(dev)
        S = np.std(ret_w, ddof=1)
        if S > 0 and R > 0:
            H = np.log(R / S) / np.log(n)
        else:
            continue

        mom = close.iloc[i-1] / close.iloc[max(0, i-20)] - 1
        if H > 0.55:
            # Trending regime → momentum
            signal.iloc[i] = 1 if mom > 0 else -1
        elif H < 0.45:
            # Mean-reverting → contrarian
            signal.iloc[i] = -1 if mom > 0 else 1
    return signal

def autocorrelation_signal(daily, lookback=30, lag=1):
    """H-663: Return autocorrelation — positive AC = trend, negative = mean-revert."""
    ret = daily['close'].pct_change()
    signal = pd.Series(0.0, index=daily.index)
    for i in range(lookback + lag + 1, len(daily)):
        window = ret.iloc[i-lookback:i].dropna()
        if len(window) < 20:
            continue
        ac = window.autocorr(lag=lag)
        if pd.isna(ac):
            continue
        mom = daily['close'].iloc[i-1] / daily['close'].iloc[max(0, i-20)] - 1
        if ac > 0.1:
            # Positive autocorrelation → trend continues
            signal.iloc[i] = 1 if mom > 0 else -1
        elif ac < -0.1:
            # Negative autocorrelation → reversal expected
            signal.iloc[i] = -1 if mom > 0 else 1
    return signal

def eth_realized_skew(lookback=30):
    """H-664: Realized skew on ETH (H-657 applied to ETH)."""
    eth = load_daily('ETH')
    ret = eth['close'].pct_change()
    signal = pd.Series(0.0, index=eth.index)
    for i in range(lookback + 1, len(eth)):
        window = ret.iloc[i-lookback:i].dropna()
        if len(window) < 20:
            continue
        sk = skew_fn(window)
        if sk > 0.5:
            signal.iloc[i] = 1
        elif sk < -0.5:
            signal.iloc[i] = -1
    return eth, signal

def sol_realized_skew(lookback=30):
    """H-665: Realized skew on SOL."""
    sol = load_daily('SOL')
    ret = sol['close'].pct_change()
    signal = pd.Series(0.0, index=sol.index)
    for i in range(lookback + 1, len(sol)):
        window = ret.iloc[i-lookback:i].dropna()
        if len(window) < 20:
            continue
        sk = skew_fn(window)
        if sk > 0.5:
            signal.iloc[i] = 1
        elif sk < -0.5:
            signal.iloc[i] = -1
    return sol, signal

def multi_asset_skew_portfolio():
    """H-666: Portfolio of realized skew signals across BTC/ETH/SOL — equal weight."""
    assets_data = {}
    for sym in ['BTC', 'ETH', 'SOL']:
        daily = load_daily(sym)
        ret = daily['close'].pct_change()
        signal = pd.Series(0.0, index=daily.index)
        for i in range(31, len(daily)):
            window = ret.iloc[i-30:i].dropna()
            if len(window) < 20:
                continue
            sk = skew_fn(window)
            if sk > 0.5:
                signal.iloc[i] = 1
            elif sk < -0.5:
                signal.iloc[i] = -1
        assets_data[sym] = {'daily': daily, 'signal': signal, 'ret': daily['close'].pct_change()}

    common = assets_data['BTC']['daily'].index
    for sym in ['ETH', 'SOL']:
        common = common.intersection(assets_data[sym]['daily'].index)

    port_ret = pd.Series(0.0, index=common)
    for sym in ['BTC', 'ETH', 'SOL']:
        sig = assets_data[sym]['signal'].loc[common]
        r = assets_data[sym]['ret'].loc[common]
        port_ret += (sig.shift(1) * r).fillna(0) / 3

    sig_change = pd.Series(0.0, index=common)
    for sym in ['BTC', 'ETH', 'SOL']:
        sig = assets_data[sym]['signal'].loc[common]
        sig_change += sig.diff().abs().fillna(0) / 3
    port_ret -= sig_change * 10 / 10000

    equity = 10000 * (1 + port_ret).cumprod()
    years = len(equity) / 365
    total_ret = equity.iloc[-1] / equity.iloc[0] - 1
    ann_ret = (1 + total_ret) ** (1 / years) - 1
    sharpe = float(port_ret.mean() / port_ret.std() * np.sqrt(365)) if float(port_ret.std()) > 0 else 0
    peak = equity.cummax()
    dd = float(abs(((equity - peak) / peak).min()))
    n_trades = int(sig_change.sum())
    win = int((port_ret > 0).sum())
    loss = int((port_ret < 0).sum())
    wr = win / (win + loss) if (win + loss) > 0 else 0

    return {
        'sharpe': round(sharpe, 3), 'ann_ret': round(ann_ret, 4), 'max_dd': round(dd, 4),
        'n_trades': n_trades, 'win_rate': round(wr, 3), 'n_bars': len(equity),
        'equity': equity, 'port_ret': port_ret
    }


def skew_momentum_combined(daily, skew_lb=30, mom_lb=20):
    """H-667: Combined skew + momentum. Only trade when skew AND momentum agree."""
    ret = daily['close'].pct_change()
    mom = daily['close'].pct_change(mom_lb)
    signal = pd.Series(0.0, index=daily.index)
    for i in range(max(skew_lb, mom_lb) + 1, len(daily)):
        window = ret.iloc[i-skew_lb:i].dropna()
        if len(window) < 20:
            continue
        sk = skew_fn(window)
        m = mom.iloc[i-1]
        if pd.isna(m):
            continue
        # Both positive → strong long signal
        if sk > 0.3 and m > 0:
            signal.iloc[i] = 1
        elif sk < -0.3 and m < 0:
            signal.iloc[i] = -1
    return signal


# ============================================================
# MAIN
# ============================================================

def full_test(name, h_id, prices_df, signal, signal_fn=None, freq='daily'):
    print(f"\n{'='*60}")
    print(f"{h_id}: {name}")

    res = backtest_ts(prices_df['close'], signal, freq=freq)
    print(f"  IS: Sharpe {res['sharpe']}, Ann {res['ann_ret']*100:.1f}%, DD {res['max_dd']*100:.1f}%, Trades {res['n_trades']}")

    if res['sharpe'] < 0.5:
        print(f"  ** REJECTED (IS Sharpe < 0.5)")
        return {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', 'sharpe': res['sharpe']}

    if signal_fn:
        wf = walk_forward_ts(prices_df, signal_fn, n_folds=7, freq=freq)
        wf_pos = sum(1 for w in wf if w > 0)
        sh = sequential_halves(prices_df, signal_fn, freq=freq)

        print(f"  WF: {wf_pos}/{len(wf)} positive, folds={wf}")
        print(f"  SH: H1={sh[0]}, H2={sh[1]} {'PASS' if sh[0]>0 and sh[1]>0 else 'FAIL'}")

        # H-657 correlation
        btc = load_daily('BTC')
        btc_ret = btc['close'].pct_change()
        from scipy.stats import skew as skew_fn2
        h657_sig = pd.Series(0.0, index=btc.index)
        for i in range(31, len(btc)):
            window = btc_ret.iloc[i-30:i].dropna()
            if len(window) >= 20:
                sk = skew_fn2(window)
                if sk > 0.5: h657_sig.iloc[i] = 1
                elif sk < -0.5: h657_sig.iloc[i] = -1
        h657_ret = (h657_sig.shift(1) * btc_ret).fillna(0)

        strat_ret = res['strat_ret']
        common = h657_ret.index.intersection(strat_ret.index)
        if len(common) > 30:
            corr_657 = h657_ret.loc[common].corr(strat_ret.loc[common])
            print(f"  H-657 PnL corr: {corr_657:.3f}")
        else:
            corr_657 = float('nan')
            print(f"  H-657 PnL corr: N/A (insufficient overlap)")

        is_confirmed = sh[0] > 0 and sh[1] > 0 and wf_pos >= 3
        status = 'CONFIRMED' if is_confirmed else 'BORDERLINE'
        print(f"  ** {status}")
        return {
            'status': status, 'sharpe': res['sharpe'], 'ann_ret': res['ann_ret'],
            'max_dd': res['max_dd'], 'wf': wf, 'sh': sh, 'h657_corr': round(corr_657, 3) if not np.isnan(corr_657) else 'N/A'
        }
    else:
        return {'status': 'BORDERLINE', 'sharpe': res['sharpe'], 'ann_ret': res['ann_ret'], 'max_dd': res['max_dd']}


def run_batch():
    print("="*60)
    print("SESSION 180 BATCH 4: Distributional/Higher-Order Moment Signals")
    print("="*60)

    all_results = {}
    btc = load_daily('BTC')

    # H-660: Kurtosis Signal
    try:
        sig_fn = lambda df: kurtosis_signal(df, 30, 3.0, 3.0)
        sig = sig_fn(btc)
        all_results['H-660'] = full_test('BTC Realized Kurtosis', 'H-660', btc, sig, sig_fn)
    except Exception as e:
        print(f"  H-660 ERROR: {e}")
        all_results['H-660'] = {'status': 'ERROR', 'error': str(e)}

    # H-661: Tail Ratio Signal
    try:
        sig_fn = lambda df: tail_ratio_signal(df, 60, 5)
        sig = sig_fn(btc)
        all_results['H-661'] = full_test('BTC Tail Ratio', 'H-661', btc, sig, sig_fn)
    except Exception as e:
        print(f"  H-661 ERROR: {e}")
        all_results['H-661'] = {'status': 'ERROR', 'error': str(e)}

    # H-662: Hurst Exponent Signal
    try:
        sig_fn = lambda df: hurst_signal(df, 100)
        sig = sig_fn(btc)
        all_results['H-662'] = full_test('BTC Hurst Exponent', 'H-662', btc, sig, sig_fn)
    except Exception as e:
        print(f"  H-662 ERROR: {e}")
        all_results['H-662'] = {'status': 'ERROR', 'error': str(e)}

    # H-663: Autocorrelation Signal
    try:
        sig_fn = lambda df: autocorrelation_signal(df, 30, 1)
        sig = sig_fn(btc)
        all_results['H-663'] = full_test('BTC Return Autocorrelation', 'H-663', btc, sig, sig_fn)
    except Exception as e:
        print(f"  H-663 ERROR: {e}")
        all_results['H-663'] = {'status': 'ERROR', 'error': str(e)}

    # H-664: ETH Realized Skew
    try:
        eth, sig = eth_realized_skew(30)
        sig_fn = lambda df: eth_realized_skew(30)[1].loc[df.index.intersection(eth_realized_skew(30)[1].index)]
        # Simplified for WF
        def eth_sig_fn(df):
            ret = df['close'].pct_change()
            signal = pd.Series(0.0, index=df.index)
            for i in range(31, len(df)):
                window = ret.iloc[i-30:i].dropna()
                if len(window) >= 20:
                    sk = skew_fn(window)
                    if sk > 0.5: signal.iloc[i] = 1
                    elif sk < -0.5: signal.iloc[i] = -1
            return signal
        all_results['H-664'] = full_test('ETH Realized Skew', 'H-664', eth, sig, eth_sig_fn)
    except Exception as e:
        print(f"  H-664 ERROR: {e}")
        import traceback; traceback.print_exc()
        all_results['H-664'] = {'status': 'ERROR', 'error': str(e)}

    # H-665: SOL Realized Skew
    try:
        sol, sig = sol_realized_skew(30)
        def sol_sig_fn(df):
            ret = df['close'].pct_change()
            signal = pd.Series(0.0, index=df.index)
            for i in range(31, len(df)):
                window = ret.iloc[i-30:i].dropna()
                if len(window) >= 20:
                    sk = skew_fn(window)
                    if sk > 0.5: signal.iloc[i] = 1
                    elif sk < -0.5: signal.iloc[i] = -1
            return signal
        all_results['H-665'] = full_test('SOL Realized Skew', 'H-665', sol, sig, sol_sig_fn)
    except Exception as e:
        print(f"  H-665 ERROR: {e}")
        all_results['H-665'] = {'status': 'ERROR', 'error': str(e)}

    # H-666: Multi-Asset Skew Portfolio
    print(f"\n{'='*60}")
    print("H-666: Multi-Asset Skew Portfolio (BTC+ETH+SOL)")
    try:
        res_port = multi_asset_skew_portfolio()
        print(f"  IS: Sharpe {res_port['sharpe']}, Ann {res_port['ann_ret']*100:.1f}%, DD {res_port['max_dd']*100:.1f}%, Trades {res_port['n_trades']}")

        if res_port['sharpe'] < 0.5:
            print(f"  ** REJECTED (IS Sharpe < 0.5)")
            all_results['H-666'] = {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', 'sharpe': res_port['sharpe']}
        else:
            # SH
            port_ret = res_port['port_ret']
            mid = len(port_ret) // 2
            h1 = port_ret.iloc[:mid]
            h2 = port_ret.iloc[mid:]
            h1_sh = float(h1.mean() / h1.std() * np.sqrt(365)) if float(h1.std()) > 0 else 0
            h2_sh = float(h2.mean() / h2.std() * np.sqrt(365)) if float(h2.std()) > 0 else 0
            print(f"  SH: H1={h1_sh:.3f}, H2={h2_sh:.3f} {'PASS' if h1_sh>0 and h2_sh>0 else 'FAIL'}")

            all_results['H-666'] = {
                'status': 'CONFIRMED' if h1_sh > 0 and h2_sh > 0 else 'BORDERLINE',
                'sharpe': res_port['sharpe'], 'ann_ret': res_port['ann_ret'], 'max_dd': res_port['max_dd'],
                'sh': [round(h1_sh, 3), round(h2_sh, 3)]
            }
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback; traceback.print_exc()
        all_results['H-666'] = {'status': 'ERROR', 'error': str(e)}

    # H-667: Skew + Momentum Combined
    try:
        sig_fn = lambda df: skew_momentum_combined(df, 30, 20)
        sig = sig_fn(btc)
        all_results['H-667'] = full_test('BTC Skew+Momentum Combined', 'H-667', btc, sig, sig_fn)
    except Exception as e:
        print(f"  H-667 ERROR: {e}")
        all_results['H-667'] = {'status': 'ERROR', 'error': str(e)}

    # SUMMARY
    print(f"\n\n{'='*60}")
    print("BATCH 4 SUMMARY")
    print(f"{'='*60}")
    for h_id, r in all_results.items():
        status = r.get('status', 'UNKNOWN')
        sharpe = r.get('sharpe', 'N/A')
        extra = ''
        if 'sh' in r:
            extra = f" SH={r['sh']}"
        if 'h657_corr' in r:
            extra += f" H657_corr={r['h657_corr']}"
        print(f"  {h_id}: {status} (Sharpe={sharpe}{extra})")


if __name__ == '__main__':
    run_batch()
