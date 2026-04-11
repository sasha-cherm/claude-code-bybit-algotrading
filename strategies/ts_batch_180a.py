#!/usr/bin/env python3
"""
Session 180 Batch 1: Altcoin 4h Time-Series Strategies
H-636 through H-643: 8 hypotheses testing individual altcoin TS patterns at 4h.
Core idea: H-617 (BTC 4h vol breakout) works — do similar patterns work on ETH/SOL/DOGE/XRP/AVAX/LINK?
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

def backtest_ts(prices, signal, fee_bps=10, freq='4h'):
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

def walk_forward_ts(prices, signal_fn, n_folds=8, freq='4h'):
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

        ret = test_prices.pct_change().fillna(0)
        strat_ret = test_sig.shift(1) * ret
        strat_ret = strat_ret.fillna(0)
        sig_change = test_sig.diff().abs().fillna(0)
        strat_ret = strat_ret - sig_change * 10 / 10000

        sh = strat_ret.mean() / strat_ret.std() * np.sqrt(ppy) if strat_ret.std() > 0 else 0
        results.append(round(sh, 3))

    return results

def param_robustness_ts(prices_df, base_signal_fn, param_grid, freq='4h'):
    positive = 0
    total = 0
    for params in param_grid:
        try:
            sig_fn = base_signal_fn(params)
            sig = sig_fn(prices_df)
            res = backtest_ts(prices_df['close'], sig, freq=freq)
            if res['sharpe'] > 0:
                positive += 1
            total += 1
        except:
            pass
    return positive, total

def sequential_halves_test(prices_df, signal_fn, freq='4h'):
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
        strat_ret = sig.shift(1) * ret
        strat_ret = strat_ret.fillna(0)
        sig_change = sig.diff().abs().fillna(0)
        strat_ret = strat_ret - sig_change * 10 / 10000
        sh = strat_ret.mean() / strat_ret.std() * np.sqrt(ppy) if strat_ret.std() > 0 else 0
        results.append(round(sh, 3))

    return results  # [H1, H2]


# ============================================================
# SIGNAL GENERATORS
# ============================================================

def vol_breakout_signal(df_4h, mom_period=12, vol_mult=1.5):
    """Volume breakout: when volume surges + positive momentum → long, vice versa."""
    close = df_4h['close']
    volume = df_4h['volume']
    ret = close.pct_change(mom_period)
    vol_ma = volume.rolling(mom_period * 4).mean()

    signal = pd.Series(0, index=close.index, dtype=float)
    prev = 0
    for i in range(1, len(close)):
        v = volume.iloc[i-1]
        vma = vol_ma.iloc[i-1]
        r = ret.iloc[i-1]
        if pd.isna(vma) or pd.isna(r):
            signal.iloc[i] = prev
            continue
        if v > vol_mult * vma:
            if r > 0:
                prev = 1
            elif r < 0:
                prev = -1
        signal.iloc[i] = prev
    return signal


def keltner_breakout_signal(df_4h, period=20, atr_mult=2.0):
    """Keltner channel breakout — long above upper, short below lower."""
    close = df_4h['close']
    high = df_4h['high']
    low = df_4h['low']

    mid = close.ewm(span=period).mean()
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    upper = mid + atr_mult * atr
    lower = mid - atr_mult * atr

    signal = pd.Series(0, index=close.index, dtype=float)
    prev = 0
    for i in range(1, len(close)):
        c = close.iloc[i-1]
        u = upper.iloc[i-1]
        l = lower.iloc[i-1]
        if pd.isna(u):
            signal.iloc[i] = prev
            continue
        if c > u:
            prev = 1
        elif c < l:
            prev = -1
        signal.iloc[i] = prev
    return signal


def momentum_4h_signal(df_4h, lookback=48):
    """Simple 4h momentum — sign of N-bar return."""
    close = df_4h['close']
    ret = close.pct_change(lookback)
    signal = pd.Series(0, index=close.index, dtype=float)
    for i in range(1, len(close)):
        r = ret.iloc[i-1]
        if pd.isna(r):
            continue
        signal.iloc[i] = 1 if r > 0 else -1
    return signal


def range_squeeze_signal(df_4h, bb_period=20, bb_std=2.0, kc_mult=1.5, mom_period=12):
    """Squeeze: when BB inside KC, pressure builds → trade the breakout direction."""
    close = df_4h['close']
    high = df_4h['high']
    low = df_4h['low']

    sma = close.rolling(bb_period).mean()
    bb_std_val = close.rolling(bb_period).std()
    bb_upper = sma + bb_std * bb_std_val
    bb_lower = sma - bb_std * bb_std_val

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(bb_period).mean()
    kc_upper = sma + kc_mult * atr
    kc_lower = sma - kc_mult * atr

    squeeze = (bb_upper < kc_upper) & (bb_lower > kc_lower)
    mom = close - close.shift(mom_period)

    signal = pd.Series(0, index=close.index, dtype=float)
    in_squeeze = False
    prev = 0
    for i in range(1, len(close)):
        if pd.isna(kc_upper.iloc[i-1]) or pd.isna(mom.iloc[i-1]):
            signal.iloc[i] = prev
            continue
        if squeeze.iloc[i-1]:
            in_squeeze = True
        elif in_squeeze:
            in_squeeze = False
            m = mom.iloc[i-1]
            prev = 1 if m > 0 else -1
        signal.iloc[i] = prev
    return signal


def atr_trend_signal(df_4h, atr_period=14, trail_mult=3.0):
    """ATR trailing stop trend following. Classic chandelier exit."""
    close = df_4h['close']
    high = df_4h['high']
    low = df_4h['low']

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()

    signal = pd.Series(0, index=close.index, dtype=float)
    pos = 0
    trail_stop = 0
    for i in range(1, len(close)):
        if pd.isna(atr.iloc[i-1]):
            continue
        c = close.iloc[i-1]
        a = atr.iloc[i-1]
        if pos == 1:
            trail_stop = max(trail_stop, c - trail_mult * a)
            if c < trail_stop:
                pos = -1
                trail_stop = c + trail_mult * a
        elif pos == -1:
            trail_stop = min(trail_stop, c + trail_mult * a)
            if c > trail_stop:
                pos = 1
                trail_stop = c - trail_mult * a
        else:
            pos = 1
            trail_stop = c - trail_mult * a
        signal.iloc[i] = pos
    return signal


# ============================================================
# MAIN
# ============================================================

ASSETS = ['ETH', 'SOL', 'DOGE', 'XRP', 'AVAX', 'LINK', 'ADA', 'NEAR']

HYPOTHESES = {
    'H-636': {'name': 'ETH 4h Volume Breakout', 'asset': 'ETH',
              'signal_fn': lambda df: vol_breakout_signal(df, 12, 1.5),
              'desc': 'H-617 pattern applied to ETH — volume surge + momentum direction'},
    'H-637': {'name': 'SOL 4h Volume Breakout', 'asset': 'SOL',
              'signal_fn': lambda df: vol_breakout_signal(df, 12, 1.5),
              'desc': 'H-617 pattern applied to SOL'},
    'H-638': {'name': 'ETH 4h Keltner Breakout', 'asset': 'ETH',
              'signal_fn': lambda df: keltner_breakout_signal(df, 20, 2.0),
              'desc': 'Keltner channel breakout on ETH 4h (like H-539 BTC variant)'},
    'H-639': {'name': 'DOGE 4h Momentum', 'asset': 'DOGE',
              'signal_fn': lambda df: momentum_4h_signal(df, 48),
              'desc': '48-bar momentum signal on DOGE 4h — high-beta asset'},
    'H-640': {'name': 'XRP 4h Range Squeeze', 'asset': 'XRP',
              'signal_fn': lambda df: range_squeeze_signal(df, 20, 2.0, 1.5, 12),
              'desc': 'BB/KC squeeze breakout on XRP 4h — tests compression breakout'},
    'H-641': {'name': 'AVAX 4h ATR Trailing Trend', 'asset': 'AVAX',
              'signal_fn': lambda df: atr_trend_signal(df, 14, 3.0),
              'desc': 'ATR trailing stop trend following on AVAX 4h'},
    'H-642': {'name': 'LINK 4h Volume Breakout', 'asset': 'LINK',
              'signal_fn': lambda df: vol_breakout_signal(df, 12, 1.5),
              'desc': 'H-617 pattern applied to LINK — mid-cap DeFi'},
    'H-643': {'name': 'NEAR 4h Keltner Breakout', 'asset': 'NEAR',
              'signal_fn': lambda df: keltner_breakout_signal(df, 20, 2.0),
              'desc': 'Keltner channel breakout on NEAR 4h'},
}


def run_batch():
    results = {}

    # Pre-load all data
    data_cache = {}
    for h_id, h in HYPOTHESES.items():
        asset = h['asset']
        if asset not in data_cache:
            try:
                df_1h = load_hourly(asset)
                df_4h = resample_4h(df_1h)
                data_cache[asset] = df_4h
                print(f"  Loaded {asset}: {len(df_4h)} 4h bars")
            except Exception as e:
                print(f"  FAILED loading {asset}: {e}")

    for h_id, h in HYPOTHESES.items():
        asset = h['asset']
        print(f"\n{'='*60}")
        print(f"{h_id}: {h['name']}")
        print(f"  Asset: {asset}")
        print(f"  Logic: {h['desc']}")

        if asset not in data_cache:
            print(f"  SKIP — no data")
            results[h_id] = {'status': 'SKIP'}
            continue

        df_4h = data_cache[asset]
        signal_fn = h['signal_fn']

        try:
            # Full IS backtest
            sig = signal_fn(df_4h)
            res = backtest_ts(df_4h['close'], sig, freq='4h')

            print(f"  IS: Sharpe {res['sharpe']}, Ann {res['ann_ret']*100:.1f}%, DD {res['max_dd']*100:.1f}%, Trades {res['n_trades']}, WR {res['win_rate']*100:.0f}%")
            print(f"  Bars: {res['n_bars']}")

            if res['sharpe'] < 0.5:
                print(f"  ** REJECTED at IS (Sharpe < 0.5)")
                results[h_id] = {'status': 'REJECTED', 'reason': 'IS Sharpe < 0.5', **{k:v for k,v in res.items() if k != 'equity'}}
                continue

            # Walk-forward
            def make_sig_fn(fn):
                def _fn(prices_subset):
                    return fn(prices_subset)
                return _fn

            wf = walk_forward_ts(df_4h, make_sig_fn(signal_fn), n_folds=8, freq='4h')
            wf_pos = sum(1 for w in wf if w > 0)
            wf_mean = np.mean(wf) if wf else 0

            print(f"  WF: {wf_pos}/{len(wf)} positive, mean {wf_mean:.3f}")
            print(f"  WF folds: {wf}")

            if wf_pos < 4 or len(wf) < 5:
                print(f"  ** REJECTED at WF (<4 positive folds or too few folds)")
                results[h_id] = {'status': 'REJECTED', 'reason': 'WF fail', 'wf': wf, **{k:v for k,v in res.items() if k != 'equity'}}
                continue

            # Sequential halves
            sh = sequential_halves_test(df_4h, signal_fn, freq='4h')
            sh_pass = sh[0] > 0 and sh[1] > 0

            print(f"  SH: H1={sh[0]}, H2={sh[1]} {'PASS' if sh_pass else 'FAIL'}")

            # Param robustness
            if 'vol_breakout' in str(signal_fn):
                param_grid = [{'mom': m, 'vol': v} for m in [8, 10, 12, 16, 20] for v in [1.2, 1.5, 1.8, 2.0]]
                def make_param_fn(params):
                    def fn(df): return vol_breakout_signal(df, params['mom'], params['vol'])
                    return fn
            elif 'keltner' in str(signal_fn):
                param_grid = [{'period': p, 'mult': m} for p in [15, 20, 25, 30] for m in [1.5, 2.0, 2.5, 3.0]]
                def make_param_fn(params):
                    def fn(df): return keltner_breakout_signal(df, params['period'], params['mult'])
                    return fn
            elif 'momentum_4h' in str(signal_fn):
                param_grid = [{'lookback': lb} for lb in [24, 36, 48, 60, 72, 96]]
                def make_param_fn(params):
                    def fn(df): return momentum_4h_signal(df, params['lookback'])
                    return fn
            elif 'range_squeeze' in str(signal_fn):
                param_grid = [{'bb_p': p, 'kc_m': m} for p in [15, 20, 25, 30] for m in [1.0, 1.5, 2.0]]
                def make_param_fn(params):
                    def fn(df): return range_squeeze_signal(df, params['bb_p'], 2.0, params['kc_m'], 12)
                    return fn
            elif 'atr_trend' in str(signal_fn):
                param_grid = [{'atr_p': p, 'trail': t} for p in [10, 14, 20] for t in [2.0, 2.5, 3.0, 3.5, 4.0]]
                def make_param_fn(params):
                    def fn(df): return atr_trend_signal(df, params['atr_p'], params['trail'])
                    return fn
            else:
                param_grid = []
                make_param_fn = None

            pr_pos, pr_total = 0, 0
            if param_grid and make_param_fn:
                pr_pos, pr_total = param_robustness_ts(df_4h, make_param_fn, param_grid, freq='4h')
                print(f"  Param robust: {pr_pos}/{pr_total} ({100*pr_pos/pr_total:.0f}%)")

            # Correlation with BTC (H-009 proxy)
            btc_1h = load_hourly('BTC')
            btc_4h = resample_4h(btc_1h)
            btc_ret = btc_4h['close'].pct_change()
            asset_sig = signal_fn(df_4h)
            asset_ret = df_4h['close'].pct_change()
            strat_ret = asset_sig.shift(1) * asset_ret
            common = btc_ret.index.intersection(strat_ret.index)
            btc_corr = btc_ret.loc[common].corr(strat_ret.loc[common])

            print(f"  BTC corr: {btc_corr:.3f}")

            result = {
                'status': 'CONFIRMED' if sh_pass else 'BORDERLINE',
                'sharpe': res['sharpe'],
                'ann_ret': res['ann_ret'],
                'max_dd': res['max_dd'],
                'n_trades': res['n_trades'],
                'win_rate': res['win_rate'],
                'n_bars': res['n_bars'],
                'wf': wf,
                'wf_pos': wf_pos,
                'wf_mean': round(wf_mean, 3),
                'sh': sh,
                'sh_pass': sh_pass,
                'param_robust': f"{pr_pos}/{pr_total}" if pr_total > 0 else 'N/A',
                'btc_corr': round(btc_corr, 3),
            }

            if sh_pass:
                print(f"  ** CONFIRMED — all tests pass")
            else:
                print(f"  ** BORDERLINE — SH fails")

            results[h_id] = result

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            results[h_id] = {'status': 'ERROR', 'error': str(e)}

    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for h_id, r in results.items():
        name = HYPOTHESES[h_id]['name']
        status = r.get('status', 'UNKNOWN')
        if status in ('CONFIRMED', 'BORDERLINE'):
            print(f"  {h_id} {name}: {status} Sharpe={r['sharpe']} WF={r['wf_pos']}/{len(r['wf'])} SH={'PASS' if r.get('sh_pass') else 'FAIL'} BTC_corr={r.get('btc_corr', 'N/A')}")
        else:
            print(f"  {h_id} {name}: {status} ({r.get('reason', r.get('error', ''))})")


if __name__ == '__main__':
    run_batch()
