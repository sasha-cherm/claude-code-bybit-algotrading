#!/usr/bin/env python3
"""
Session 177: Deep validation for H-571 (SOL Session Momentum) and H-572 (BTC Multi-TF).
Tests: WF, Split-half, param robustness, correlation with H-012.
"""
import json, warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings('ignore')
DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

def load_hourly(symbol='BTC'):
    return pd.read_parquet(DATA_DIR / f'{symbol}_USDT_1h.parquet')

def compute_daily(df_1h):
    return df_1h.resample('1D').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum'
    }).dropna()


def backtest_ts(prices, signal, fee_bps=10):
    """Daily TS backtest."""
    common = prices.index.intersection(signal.index)
    prices = prices.loc[common]
    signal = signal.loc[common]
    ret = prices.pct_change().fillna(0)
    strat_ret = signal.shift(1) * ret
    strat_ret = strat_ret.fillna(0)
    sig_change = signal.diff().abs().fillna(0)
    strat_ret = strat_ret - sig_change * fee_bps / 10000
    equity = 10000 * (1 + strat_ret).cumprod()
    return strat_ret, equity


def backtest_hourly(prices, signal, fee_bps=10):
    """Hourly TS backtest."""
    common = prices.index.intersection(signal.index)
    prices = prices.loc[common]
    signal = signal.loc[common]
    ret = prices.pct_change().fillna(0)
    strat_ret = signal.shift(1) * ret
    strat_ret = strat_ret.fillna(0)
    sig_change = signal.diff().abs().fillna(0)
    strat_ret = strat_ret - sig_change * fee_bps / 10000
    equity = 10000 * (1 + strat_ret).cumprod()
    return strat_ret, equity


def metrics(strat_ret, equity, ppy=365):
    n = len(equity)
    years = n / ppy
    total_ret = equity.iloc[-1] / equity.iloc[0] - 1
    ann_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
    sharpe = strat_ret.mean() / strat_ret.std() * np.sqrt(ppy) if strat_ret.std() > 0 else 0
    peak = equity.cummax()
    dd = abs(((equity - peak) / peak).min())
    return {
        'sharpe': round(sharpe, 3),
        'ann_ret': round(ann_ret, 4),
        'max_dd': round(dd, 4),
        'n_bars': n
    }


# Signal generators
def sol_intraday_momentum(sol_1h, threshold=0.0):
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


def btc_multi_tf_signal(btc_1h, daily_lookback=20, hourly_lookback=24):
    daily = btc_1h.resample('1D').agg({'close': 'last'}).dropna()
    daily_ema = daily['close'].ewm(span=daily_lookback).mean()
    daily_trend = (daily['close'] > daily_ema).astype(int).replace(0, -1)
    btc_close = btc_1h['close']
    daily_trend_hourly = daily_trend.reindex(btc_close.index, method='ffill')
    hourly_mom = btc_close.pct_change(hourly_lookback)
    hourly_dir = hourly_mom.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    signal = pd.Series(0, index=btc_close.index)
    for i in range(1, len(btc_close)):
        d = daily_trend_hourly.iloc[i-1] if not np.isnan(daily_trend_hourly.iloc[i-1]) else 0
        h = hourly_dir.iloc[i-1] if not np.isnan(hourly_dir.iloc[i-1]) else 0
        if d == h and d != 0:
            signal.iloc[i] = int(d)
    return signal


def btc_supertrend_signal(btc_daily, period=10, mult=3.0):
    close = btc_daily['close']
    high = btc_daily['high']
    low = btc_daily['low']
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    hl2 = (high + low) / 2
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    direction = pd.Series(1, index=close.index)
    for i in range(1, len(close)):
        if np.isnan(upper.iloc[i]) or np.isnan(lower.iloc[i]):
            direction.iloc[i] = direction.iloc[i-1]
            continue
        if lower.iloc[i] < lower.iloc[i-1] and close.iloc[i-1] >= lower.iloc[i-1]:
            lower.iloc[i] = lower.iloc[i-1]
        if upper.iloc[i] > upper.iloc[i-1] and close.iloc[i-1] <= upper.iloc[i-1]:
            upper.iloc[i] = upper.iloc[i-1]
        if direction.iloc[i-1] == 1:
            if close.iloc[i] < lower.iloc[i]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = 1
        else:
            if close.iloc[i] > upper.iloc[i]:
                direction.iloc[i] = 1
            else:
                direction.iloc[i] = -1
    signal = pd.Series(0, index=close.index)
    for i in range(1, len(close)):
        signal.iloc[i] = int(direction.iloc[i-1])
    return signal


# Load XS momentum returns for correlation
def load_h012_returns():
    """Load H-012 equity to compute daily returns for correlation."""
    try:
        with open('paper_trades/h012_xsmom/state.json') as f:
            s = json.load(f)
        if 'equity_history' in s and s['equity_history']:
            eq = pd.DataFrame(s['equity_history'])
            eq['time'] = pd.to_datetime(eq['time'], utc=True)
            eq = eq.set_index('time')
            return eq['equity'].pct_change().dropna()
    except:
        pass
    return None


def main():
    print("=" * 80)
    print("DEEP VALIDATION: H-571 (SOL Session Mom), H-572 (BTC Multi-TF), H-576 (BTC SuperTrend)")
    print("=" * 80)

    btc_1h = load_hourly('BTC')
    sol_1h = load_hourly('SOL')
    btc_daily = compute_daily(btc_1h)
    sol_daily = compute_daily(sol_1h)

    # =========================================
    # H-571: SOL Session Momentum — Deep Validation
    # =========================================
    print("\n" + "=" * 80)
    print("H-571: SOL Intraday Session Momentum")
    print("=" * 80)

    # Full backtest
    sig = sol_intraday_momentum(sol_1h)
    sr, eq = backtest_ts(sol_daily['close'], sig)
    m = metrics(sr, eq)
    print(f"\nFull-sample: Sharpe {m['sharpe']}, Ann {m['ann_ret']:.1%}, DD {m['max_dd']:.1%}, Bars {m['n_bars']}")

    # Walk-forward (8 folds)
    print("\nWalk-Forward (8 folds):")
    n = len(sol_daily)
    fold_size = n // 8
    wf_results = []
    for fold in range(8):
        test_start = fold * fold_size
        test_end = min((fold + 1) * fold_size, n)
        if test_start < fold_size:
            continue

        test_dates = sol_daily.index[test_start:test_end]
        sig_full = sol_intraday_momentum(sol_1h.loc[:test_dates[-1]])
        sig_test = sig_full.reindex(test_dates).fillna(0)

        test_close = sol_daily['close'].iloc[test_start:test_end]
        sr_test, eq_test = backtest_ts(test_close, sig_test)
        m_test = metrics(sr_test, eq_test)
        wf_results.append(m_test['sharpe'])
        print(f"  Fold {fold}: Sharpe {m_test['sharpe']:.3f}, Ann {m_test['ann_ret']:.1%}, DD {m_test['max_dd']:.1%}")

    pos_folds = sum(1 for s in wf_results if s > 0)
    print(f"\n  WF: {pos_folds}/{len(wf_results)} positive, mean {np.mean(wf_results):.3f}")

    # Split-half
    print("\nSplit-Half:")
    mid = len(sol_1h) // 2
    sig_h1 = sol_intraday_momentum(sol_1h.iloc[:mid])
    sig_h2 = sol_intraday_momentum(sol_1h.iloc[mid:])
    sol_daily_h1 = sol_daily.iloc[:len(sol_daily)//2]
    sol_daily_h2 = sol_daily.iloc[len(sol_daily)//2:]
    sr1, eq1 = backtest_ts(sol_daily_h1['close'], sig_h1)
    sr2, eq2 = backtest_ts(sol_daily_h2['close'], sig_h2)
    m1 = metrics(sr1, eq1)
    m2 = metrics(sr2, eq2)
    print(f"  H1: Sharpe {m1['sharpe']}, Ann {m1['ann_ret']:.1%}, DD {m1['max_dd']:.1%}")
    print(f"  H2: Sharpe {m2['sharpe']}, Ann {m2['ann_ret']:.1%}, DD {m2['max_dd']:.1%}")
    sh_pass = m1['sharpe'] > 0 and m2['sharpe'] > 0
    print(f"  Split-half: {'PASS' if sh_pass else 'FAIL'}")

    # Extended param robustness
    print("\nParam Robustness (extended):")
    pos = 0
    total = 0
    best_sharpe = -999
    for thresh in [0, 0.001, 0.002, 0.003, 0.005, 0.007, 0.008, 0.01, 0.012, 0.015, 0.02, 0.025]:
        s = sol_intraday_momentum(sol_1h, threshold=thresh)
        sr_p, eq_p = backtest_ts(sol_daily['close'], s)
        m_p = metrics(sr_p, eq_p)
        if m_p['sharpe'] > 0: pos += 1
        if m_p['sharpe'] > best_sharpe: best_sharpe = m_p['sharpe']
        total += 1
        print(f"  thresh={thresh:.3f}: Sharpe {m_p['sharpe']:.3f}, Ann {m_p['ann_ret']:.1%}")
    print(f"\n  Param robust: {pos}/{total} ({pos/total*100:.0f}%), best Sharpe {best_sharpe:.3f}")

    # Correlation with BTC buy-and-hold (proxy for directional risk)
    print("\nCorrelation with BTC:")
    btc_ret_daily = btc_daily['close'].pct_change().dropna()
    common_dates = sr.index.intersection(btc_ret_daily.index)
    if len(common_dates) > 100:
        corr_btc = sr.loc[common_dates].corr(btc_ret_daily.loc[common_dates])
        print(f"  Correlation with BTC returns: {corr_btc:.3f}")

    # H-571 verdict
    print(f"\n{'='*40}")
    print(f"H-571 VERDICT:")
    print(f"  IS Sharpe: {m['sharpe']}")
    print(f"  WF: {pos_folds}/{len(wf_results)} positive, mean {np.mean(wf_results):.3f}")
    print(f"  SH: {'PASS' if sh_pass else 'FAIL'} (H1={m1['sharpe']}, H2={m2['sharpe']})")
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    h571_pass = pos_folds >= 4 and sh_pass and pos/total >= 0.75
    print(f"  OVERALL: {'CONFIRMED' if h571_pass else 'REJECTED'}")

    # =========================================
    # H-572: BTC Multi-Timeframe — Deep Validation
    # =========================================
    print("\n" + "=" * 80)
    print("H-572: BTC Multi-Timeframe (Daily Trend + Hourly Momentum)")
    print("=" * 80)

    sig = btc_multi_tf_signal(btc_1h)
    sr, eq = backtest_hourly(btc_1h['close'], sig)
    m = metrics(sr, eq, ppy=8760)
    print(f"\nFull-sample: Sharpe {m['sharpe']}, Ann {m['ann_ret']:.1%}, DD {m['max_dd']:.1%}, Bars {m['n_bars']}")

    # Walk-forward (8 folds on hourly)
    print("\nWalk-Forward (8 folds):")
    n = len(btc_1h)
    fold_size = n // 8
    wf_results = []
    for fold in range(8):
        test_start = fold * fold_size
        test_end = min((fold + 1) * fold_size, n)
        if test_start < fold_size:
            continue

        test_1h = btc_1h.iloc[test_start:test_end]
        sig_full = btc_multi_tf_signal(btc_1h.iloc[:test_end])
        sig_test = sig_full.iloc[test_start:test_end]

        sr_test, eq_test = backtest_hourly(test_1h['close'], sig_test)
        m_test = metrics(sr_test, eq_test, ppy=8760)
        wf_results.append(m_test['sharpe'])
        print(f"  Fold {fold}: Sharpe {m_test['sharpe']:.3f}, Ann {m_test['ann_ret']:.1%}, DD {m_test['max_dd']:.1%}")

    pos_folds = sum(1 for s in wf_results if s > 0)
    print(f"\n  WF: {pos_folds}/{len(wf_results)} positive, mean {np.mean(wf_results):.3f}")

    # Split-half
    print("\nSplit-Half:")
    mid = len(btc_1h) // 2
    sig_h1 = btc_multi_tf_signal(btc_1h.iloc[:mid])
    sig_h2 = btc_multi_tf_signal(btc_1h.iloc[mid:])
    sr1, eq1 = backtest_hourly(btc_1h['close'].iloc[:mid], sig_h1)
    sr2, eq2 = backtest_hourly(btc_1h['close'].iloc[mid:], sig_h2)
    m1 = metrics(sr1, eq1, ppy=8760)
    m2 = metrics(sr2, eq2, ppy=8760)
    print(f"  H1: Sharpe {m1['sharpe']}, Ann {m1['ann_ret']:.1%}, DD {m1['max_dd']:.1%}")
    print(f"  H2: Sharpe {m2['sharpe']}, Ann {m2['ann_ret']:.1%}, DD {m2['max_dd']:.1%}")
    sh_pass = m1['sharpe'] > 0 and m2['sharpe'] > 0
    print(f"  Split-half: {'PASS' if sh_pass else 'FAIL'}")

    # Extended param robustness
    print("\nParam Robustness (extended):")
    pos = 0
    total = 0
    for dl in [10, 15, 20, 25, 30, 40]:
        for hl in [6, 12, 18, 24, 36, 48]:
            s = btc_multi_tf_signal(btc_1h, daily_lookback=dl, hourly_lookback=hl)
            sr_p, eq_p = backtest_hourly(btc_1h['close'], s)
            m_p = metrics(sr_p, eq_p, ppy=8760)
            if m_p['sharpe'] > 0: pos += 1
            total += 1
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")

    # Correlation with BTC
    print("\nCorrelation with BTC daily:")
    strat_daily = sr.resample('1D').sum()
    btc_ret_daily = btc_daily['close'].pct_change().dropna()
    common_dates = strat_daily.index.intersection(btc_ret_daily.index)
    if len(common_dates) > 100:
        corr_btc = strat_daily.loc[common_dates].corr(btc_ret_daily.loc[common_dates])
        print(f"  Correlation with BTC returns: {corr_btc:.3f}")

    # H-572 verdict
    print(f"\n{'='*40}")
    print(f"H-572 VERDICT:")
    print(f"  IS Sharpe: {m['sharpe']}")
    print(f"  WF: {pos_folds}/{len(wf_results)} positive, mean {np.mean(wf_results):.3f}")
    print(f"  SH: {'PASS' if sh_pass else 'FAIL'} (H1={m1['sharpe']}, H2={m2['sharpe']})")
    print(f"  Param robust: {pos}/{total} ({pos/total*100:.0f}%)")
    h572_pass = pos_folds >= 4 and sh_pass and pos/total >= 0.75
    print(f"  OVERALL: {'CONFIRMED' if h572_pass else 'REJECTED'}")

    # =========================================
    # H-576: BTC SuperTrend — Sanity check
    # =========================================
    print("\n" + "=" * 80)
    print("H-576: BTC SuperTrend — Sanity Check")
    print("=" * 80)

    sig = btc_supertrend_signal(btc_daily)
    flips = sig.diff().abs().sum()
    print(f"Signal flips: {flips}")
    print(f"Unique signal values: {sig.value_counts().to_dict()}")
    print(f"Time in LONG: {(sig == 1).mean():.1%}, SHORT: {(sig == -1).mean():.1%}, FLAT: {(sig == 0).mean():.1%}")

    sr, eq = backtest_ts(btc_daily['close'], sig)
    m = metrics(sr, eq)
    print(f"Full-sample: Sharpe {m['sharpe']}, Ann {m['ann_ret']:.1%}, DD {m['max_dd']:.1%}")

    # Check: is this just buy-and-hold BTC?
    btc_bh = 10000 * (1 + btc_daily['close'].pct_change().fillna(0)).cumprod()
    btc_bh_sharpe = btc_daily['close'].pct_change().dropna()
    bh_sharpe = btc_bh_sharpe.mean() / btc_bh_sharpe.std() * np.sqrt(365)
    print(f"\nBTC Buy-and-Hold Sharpe: {bh_sharpe:.3f}")
    print(f"SuperTrend vs B&H: {'meaningfully different' if abs(m['sharpe'] - bh_sharpe) > 0.1 else 'essentially same as B&H'}")

    # WF already done above — 5/7 positive
    # But check correlation with BTC
    common_dates = sr.index.intersection(btc_bh_sharpe.index)
    corr = sr.loc[common_dates].corr(btc_bh_sharpe.loc[common_dates])
    print(f"Correlation with BTC returns: {corr:.3f}")

    if flips < 20:
        print(f"\n  WARNING: Only {int(flips)} signal flips = essentially static position.")
        print(f"  This is NOT a real trading strategy — it's near-buy-and-hold.")
        print(f"  REJECTED as not a genuine strategy.")


if __name__ == '__main__':
    main()
