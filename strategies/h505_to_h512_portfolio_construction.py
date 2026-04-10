#!/usr/bin/env python3
"""
H-505 to H-512: Portfolio Construction Improvements

Instead of finding new signals or timing regimes, improve HOW we convert
the equal-weight ensemble signal into portfolio weights.

H-505: Continuous weighting — z-score proportional weights instead of binary top/bottom 4
H-506: Volatility-scaled — scale each asset weight by inverse recent vol
H-507: Multi-horizon ensemble — combine 3d/5d/10d rebalance frequency signals
H-508: Asymmetric long/short — long top 5, short bottom 3 (concentrated shorts)
H-509: Signal-strength threshold — only trade when composite z-score exceeds threshold
H-510: Turnover-penalized — blend old and new signals to reduce turnover
H-511: Dynamic N — vary long/short count based on signal dispersion
H-512: Risk-parity weighting — weight by inverse volatility at portfolio level
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001


def fetch_all_data():
    print("Fetching hourly data for 14 assets...")
    daily = {}
    for sym in ASSETS:
        df_1h = fetch_and_cache(sym, "1h", limit_days=900)
        if df_1h is not None and len(df_1h) > 100:
            df_d = resample_to_daily(df_1h)
            daily[sym] = df_d
    print(f"  Loaded {len(daily)} assets")

    all_dates = sorted(set.intersection(*[set(df.index) for df in daily.values()]))
    close = pd.DataFrame({s: daily[s].loc[all_dates, 'close'] for s in daily})
    volume = pd.DataFrame({s: daily[s].loc[all_dates, 'volume'] for s in daily})
    high = pd.DataFrame({s: daily[s].loc[all_dates, 'high'] for s in daily})
    low = pd.DataFrame({s: daily[s].loc[all_dates, 'low'] for s in daily})
    opn = pd.DataFrame({s: daily[s].loc[all_dates, 'open'] for s in daily})
    return close, volume, high, low, opn, all_dates


def xs_zscore(row):
    vals = row.values
    if np.all(np.isnan(vals)):
        return pd.Series(np.nan, index=row.index)
    m = np.nanmean(vals)
    s = np.nanstd(vals)
    if s < 1e-12:
        return pd.Series(0.0, index=row.index)
    return (row - m) / s


def compute_core_factors(close, volume, high, low, opn):
    rets = close.pct_change()
    dollar_vol = close * volume
    factors = {}
    mom60 = close / close.shift(60) - 1
    factors['momentum'] = mom60.apply(xs_zscore, axis=1)
    vol20 = rets.rolling(20).std()
    factors['low_vol'] = (-vol20).apply(xs_zscore, axis=1)
    dv_s = (dollar_vol).rolling(5).mean()
    dv_l = (dollar_vol).rolling(20).mean()
    factors['turnover'] = (dv_s / dv_l).apply(xs_zscore, axis=1)
    abs_ret = rets.abs()
    net_40 = (close / close.shift(40) - 1).abs()
    sum_abs_40 = abs_ret.rolling(40).sum()
    factors['efficiency'] = (net_40 / sum_abs_40).apply(xs_zscore, axis=1)
    dd_prox = close / close.rolling(60).max()
    factors['dd_momentum'] = dd_prox.apply(xs_zscore, axis=1)
    vw_ret = (rets * volume).rolling(10).sum() / volume.rolling(10).sum()
    factors['vw_pressure'] = vw_ret.apply(xs_zscore, axis=1)
    vol_surp = volume / volume.rolling(20).mean()
    factors['vol_surprise'] = vol_surp.apply(xs_zscore, axis=1)
    vwap_p = (close * volume).rolling(5).sum() / volume.rolling(5).sum()
    premium = close / vwap_p - 1
    factors['premium'] = (-premium).apply(xs_zscore, axis=1)
    dv30 = dollar_vol.rolling(30).mean()
    factors['size'] = dv30.apply(xs_zscore, axis=1)
    vol7 = rets.rolling(7).std()
    vol30 = rets.rolling(30).std()
    factors['vol_term'] = (vol7 / vol30).apply(xs_zscore, axis=1)
    return factors


def get_composite_signal(factors, date_i):
    """Equal-weight composite z-score for a given date."""
    factor_names = sorted(factors.keys())
    n_assets = len(list(factors.values())[0].columns)
    X = np.zeros(n_assets)
    for fname in factor_names:
        fvals = factors[fname].loc[date_i].values
        if not np.all(np.isnan(fvals)):
            X += np.nan_to_num(fvals.copy(), 0)
    X /= len(factor_names)
    return X


def compute_metrics(rets_series):
    if len(rets_series) < 30:
        return {'sharpe': 0, 'annual_return': 0, 'max_drawdown': 0, 'win_rate': 0, 'n_days': 0}
    ann_ret = rets_series.mean() * 365
    ann_vol = rets_series.std() * np.sqrt(365)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    cum = (1 + rets_series).cumprod()
    dd = (cum / cum.cummax() - 1)
    max_dd = dd.min()
    win_rate = (rets_series > 0).mean()
    return {
        'sharpe': round(sharpe, 3),
        'annual_return': round(ann_ret, 4),
        'max_drawdown': round(max_dd, 4),
        'win_rate': round(win_rate, 4),
        'n_days': len(rets_series),
    }


def walk_forward(rets_series, n_folds=6, fold_days=90):
    n = len(rets_series)
    results = []
    for fold in range(n_folds):
        end_idx = n - fold * fold_days
        start_idx = end_idx - fold_days
        if start_idx < 30:
            break
        fold_rets = rets_series.iloc[start_idx:end_idx]
        m = compute_metrics(fold_rets)
        m['fold'] = fold + 1
        results.append(m)
    return results


def split_half(rets_series):
    mid = len(rets_series) // 2
    h1 = compute_metrics(rets_series.iloc[:mid])
    h2 = compute_metrics(rets_series.iloc[mid:])
    return h1, h2


def evaluate(name, rets, rets_base, rets_h012=None):
    m = compute_metrics(rets)
    m_base = compute_metrics(rets_base)

    print(f"\n  --- {name} ---")
    print(f"  IS: Sharpe {m['sharpe']:.3f} (base {m_base['sharpe']:.3f}, "
          f"delta {(m['sharpe']/m_base['sharpe']-1)*100:+.1f}%)")
    print(f"  Ann: {m['annual_return']*100:+.1f}% DD: {m['max_drawdown']*100:.1f}% "
          f"WR: {m['win_rate']*100:.1f}% N={m['n_days']}")

    wf = walk_forward(rets)
    wf_pos = sum(1 for f in wf if f['sharpe'] > 0)
    wf_mean = np.mean([f['sharpe'] for f in wf]) if wf else 0
    print(f"  WF: {wf_pos}/{len(wf)} positive, mean {wf_mean:.3f}")
    for f in wf:
        print(f"    Fold {f['fold']}: Sharpe {f['sharpe']:.3f}")

    h1, h2 = split_half(rets)
    sh_pass = h1['sharpe'] > 0 and h2['sharpe'] > 0
    print(f"  SH: H1={h1['sharpe']:.3f} H2={h2['sharpe']:.3f} {'PASS' if sh_pass else 'FAIL'}")

    if rets_h012 is not None:
        common = rets.index.intersection(rets_h012.index)
        if len(common) > 30:
            corr = rets.loc[common].corr(rets_h012.loc[common])
            print(f"  Corr H-012: {corr:.3f}")

    common = rets.index.intersection(rets_base.index)
    if len(common) > 30:
        corr_base = rets.loc[common].corr(rets_base.loc[common])
        print(f"  Corr base: {corr_base:.3f}")

    imp = (m['sharpe'] / m_base['sharpe'] - 1) if m_base['sharpe'] > 0 else 0
    confirmed = (m['sharpe'] > 1.0 and wf_pos >= 4 and sh_pass and imp > 0.05)
    status = "CONFIRMED" if confirmed else "REJECTED"
    reasons = []
    if m['sharpe'] <= 1.0: reasons.append(f"Sharpe {m['sharpe']:.3f}")
    if wf_pos < 4: reasons.append(f"WF {wf_pos}/6")
    if not sh_pass: reasons.append("SH FAIL")
    if imp <= 0.05: reasons.append(f"imp {imp*100:+.1f}%")
    print(f"  ==> {status}" + (f" ({', '.join(reasons)})" if reasons else ""))
    return {'name': name, 'status': status, 'metrics': m, 'wf_pos': wf_pos,
            'wf_total': len(wf), 'wf_mean': wf_mean, 'sh_pass': sh_pass,
            'improvement': imp}


def backtest_base(close, factors, n_long=4, n_short=4, rebal_freq=5, start_idx=120):
    rets = close.pct_change()
    dates = close.index.tolist()
    n_assets = len(close.columns)
    prev_weights = np.zeros(n_assets)
    port_rets, sig_dates = [], []

    for i in range(start_idx, len(dates) - 1):
        if (i - start_idx) % rebal_freq != 0:
            dr = rets.loc[dates[i+1]].values
            if not np.any(np.isnan(dr)):
                port_rets.append(np.nansum(prev_weights * dr))
                sig_dates.append(dates[i+1])
            continue
        X = get_composite_signal(factors, dates[i])
        if np.all(X == 0): continue
        ranks = rankdata(X)
        w = np.zeros(n_assets)
        w[ranks > (n_assets - n_long)] = 1.0 / n_long
        w[ranks <= n_short] = -1.0 / n_short
        turnover = np.sum(np.abs(w - prev_weights))
        fee = turnover * FEE_RATE
        dr = rets.loc[dates[i+1]].values
        if np.any(np.isnan(dr)): continue
        port_rets.append(np.nansum(w * dr) - fee)
        sig_dates.append(dates[i+1])
        prev_weights = w.copy()
    return pd.Series(port_rets, index=sig_dates)


def backtest_continuous(close, factors, rebal_freq=5, start_idx=120):
    """H-505: Continuous z-score proportional weights (long/short balanced)."""
    rets = close.pct_change()
    dates = close.index.tolist()
    n_assets = len(close.columns)
    prev_weights = np.zeros(n_assets)
    port_rets, sig_dates = [], []

    for i in range(start_idx, len(dates) - 1):
        if (i - start_idx) % rebal_freq != 0:
            dr = rets.loc[dates[i+1]].values
            if not np.any(np.isnan(dr)):
                port_rets.append(np.nansum(prev_weights * dr))
                sig_dates.append(dates[i+1])
            continue
        X = get_composite_signal(factors, dates[i])
        if np.all(X == 0): continue
        # Demean to ensure long/short balance
        X = X - np.mean(X)
        # Normalize to sum(abs(weights)) = 2 (1 long + 1 short)
        total = np.sum(np.abs(X))
        if total < 1e-10: continue
        w = X / total * 2
        turnover = np.sum(np.abs(w - prev_weights))
        fee = turnover * FEE_RATE
        dr = rets.loc[dates[i+1]].values
        if np.any(np.isnan(dr)): continue
        port_rets.append(np.nansum(w * dr) - fee)
        sig_dates.append(dates[i+1])
        prev_weights = w.copy()
    return pd.Series(port_rets, index=sig_dates)


def backtest_vol_scaled(close, factors, rebal_freq=5, start_idx=120, n_long=4, n_short=4):
    """H-506: Scale each asset's weight by inverse recent volatility."""
    rets = close.pct_change()
    vol20 = rets.rolling(20).std()
    dates = close.index.tolist()
    n_assets = len(close.columns)
    prev_weights = np.zeros(n_assets)
    port_rets, sig_dates = [], []

    for i in range(start_idx, len(dates) - 1):
        if (i - start_idx) % rebal_freq != 0:
            dr = rets.loc[dates[i+1]].values
            if not np.any(np.isnan(dr)):
                port_rets.append(np.nansum(prev_weights * dr))
                sig_dates.append(dates[i+1])
            continue
        X = get_composite_signal(factors, dates[i])
        if np.all(X == 0): continue
        ranks = rankdata(X)
        w = np.zeros(n_assets)
        w[ranks > (n_assets - n_long)] = 1.0
        w[ranks <= n_short] = -1.0
        # Scale by inverse vol
        v = vol20.loc[dates[i]].values
        inv_vol = 1.0 / (v + 1e-10)
        w = w * inv_vol
        # Normalize long and short sides separately
        long_sum = np.sum(w[w > 0])
        short_sum = np.abs(np.sum(w[w < 0]))
        if long_sum > 0: w[w > 0] /= long_sum
        if short_sum > 0: w[w < 0] /= short_sum
        w[w < 0] *= -1; w[w < 0] *= -1  # keep negative

        turnover = np.sum(np.abs(w - prev_weights))
        fee = turnover * FEE_RATE
        dr = rets.loc[dates[i+1]].values
        if np.any(np.isnan(dr)): continue
        port_rets.append(np.nansum(w * dr) - fee)
        sig_dates.append(dates[i+1])
        prev_weights = w.copy()
    return pd.Series(port_rets, index=sig_dates)


def backtest_multi_horizon(close, factors, start_idx=120):
    """H-507: Combine signals at 3d, 5d, 10d rebalance frequencies."""
    rets = close.pct_change()
    dates = close.index.tolist()
    n_assets = len(close.columns)

    # Pre-compute signals for each frequency
    signals = {}
    for freq in [3, 5, 10]:
        sig = {}
        for i in range(start_idx, len(dates)):
            if (i - start_idx) % freq == 0:
                X = get_composite_signal(factors, dates[i])
                sig[dates[i]] = X
        signals[freq] = sig

    prev_weights = np.zeros(n_assets)
    port_rets, sig_dates = [], []
    last_signal = {3: np.zeros(n_assets), 5: np.zeros(n_assets), 10: np.zeros(n_assets)}

    for i in range(start_idx, len(dates) - 1):
        # Update signals for each horizon
        for freq in [3, 5, 10]:
            if dates[i] in signals[freq]:
                last_signal[freq] = signals[freq][dates[i]]

        if (i - start_idx) % 3 != 0:  # rebalance every 3 days (fastest freq)
            dr = rets.loc[dates[i+1]].values
            if not np.any(np.isnan(dr)):
                port_rets.append(np.nansum(prev_weights * dr))
                sig_dates.append(dates[i+1])
            continue

        # Blend signals (equal weight across horizons)
        X = (last_signal[3] + last_signal[5] + last_signal[10]) / 3
        if np.all(X == 0): continue

        ranks = rankdata(X)
        w = np.zeros(n_assets)
        w[ranks > (n_assets - 4)] = 0.25
        w[ranks <= 4] = -0.25
        turnover = np.sum(np.abs(w - prev_weights))
        fee = turnover * FEE_RATE
        dr = rets.loc[dates[i+1]].values
        if np.any(np.isnan(dr)): continue
        port_rets.append(np.nansum(w * dr) - fee)
        sig_dates.append(dates[i+1])
        prev_weights = w.copy()
    return pd.Series(port_rets, index=sig_dates)


def backtest_asymmetric(close, factors, n_long=5, n_short=3, rebal_freq=5, start_idx=120):
    """H-508: Asymmetric long/short (more longs, concentrated shorts)."""
    rets = close.pct_change()
    dates = close.index.tolist()
    n_assets = len(close.columns)
    prev_weights = np.zeros(n_assets)
    port_rets, sig_dates = [], []

    for i in range(start_idx, len(dates) - 1):
        if (i - start_idx) % rebal_freq != 0:
            dr = rets.loc[dates[i+1]].values
            if not np.any(np.isnan(dr)):
                port_rets.append(np.nansum(prev_weights * dr))
                sig_dates.append(dates[i+1])
            continue
        X = get_composite_signal(factors, dates[i])
        if np.all(X == 0): continue
        ranks = rankdata(X)
        w = np.zeros(n_assets)
        w[ranks > (n_assets - n_long)] = 1.0 / n_long
        w[ranks <= n_short] = -1.0 / n_short
        turnover = np.sum(np.abs(w - prev_weights))
        fee = turnover * FEE_RATE
        dr = rets.loc[dates[i+1]].values
        if np.any(np.isnan(dr)): continue
        port_rets.append(np.nansum(w * dr) - fee)
        sig_dates.append(dates[i+1])
        prev_weights = w.copy()
    return pd.Series(port_rets, index=sig_dates)


def backtest_threshold(close, factors, threshold=0.5, rebal_freq=5, start_idx=120):
    """H-509: Only trade assets with composite z-score above threshold."""
    rets = close.pct_change()
    dates = close.index.tolist()
    n_assets = len(close.columns)
    prev_weights = np.zeros(n_assets)
    port_rets, sig_dates = [], []

    for i in range(start_idx, len(dates) - 1):
        if (i - start_idx) % rebal_freq != 0:
            dr = rets.loc[dates[i+1]].values
            if not np.any(np.isnan(dr)):
                port_rets.append(np.nansum(prev_weights * dr))
                sig_dates.append(dates[i+1])
            continue
        X = get_composite_signal(factors, dates[i])
        if np.all(X == 0): continue
        # Only trade assets with |z-score| above threshold
        w = np.zeros(n_assets)
        long_mask = X > threshold
        short_mask = X < -threshold
        n_long = long_mask.sum()
        n_short = short_mask.sum()
        if n_long > 0: w[long_mask] = 1.0 / n_long
        if n_short > 0: w[short_mask] = -1.0 / n_short
        # If no signals pass threshold, stay flat
        if n_long == 0 and n_short == 0:
            w = prev_weights.copy()

        turnover = np.sum(np.abs(w - prev_weights))
        fee = turnover * FEE_RATE
        dr = rets.loc[dates[i+1]].values
        if np.any(np.isnan(dr)): continue
        port_rets.append(np.nansum(w * dr) - fee)
        sig_dates.append(dates[i+1])
        prev_weights = w.copy()
    return pd.Series(port_rets, index=sig_dates)


def backtest_turnover_penalized(close, factors, blend=0.5, rebal_freq=5, start_idx=120):
    """H-510: Blend old and new signals to reduce turnover."""
    rets = close.pct_change()
    dates = close.index.tolist()
    n_assets = len(close.columns)
    prev_weights = np.zeros(n_assets)
    prev_signal = np.zeros(n_assets)
    port_rets, sig_dates = [], []

    for i in range(start_idx, len(dates) - 1):
        if (i - start_idx) % rebal_freq != 0:
            dr = rets.loc[dates[i+1]].values
            if not np.any(np.isnan(dr)):
                port_rets.append(np.nansum(prev_weights * dr))
                sig_dates.append(dates[i+1])
            continue
        X_new = get_composite_signal(factors, dates[i])
        if np.all(X_new == 0): continue
        # Blend with previous signal
        X = blend * X_new + (1 - blend) * prev_signal
        prev_signal = X.copy()
        ranks = rankdata(X)
        w = np.zeros(n_assets)
        w[ranks > (n_assets - 4)] = 0.25
        w[ranks <= 4] = -0.25
        turnover = np.sum(np.abs(w - prev_weights))
        fee = turnover * FEE_RATE
        dr = rets.loc[dates[i+1]].values
        if np.any(np.isnan(dr)): continue
        port_rets.append(np.nansum(w * dr) - fee)
        sig_dates.append(dates[i+1])
        prev_weights = w.copy()
    return pd.Series(port_rets, index=sig_dates)


def backtest_dynamic_n(close, factors, rebal_freq=5, start_idx=120):
    """H-511: Vary number of positions based on signal dispersion."""
    rets = close.pct_change()
    dates = close.index.tolist()
    n_assets = len(close.columns)
    prev_weights = np.zeros(n_assets)
    port_rets, sig_dates = [], []

    for i in range(start_idx, len(dates) - 1):
        if (i - start_idx) % rebal_freq != 0:
            dr = rets.loc[dates[i+1]].values
            if not np.any(np.isnan(dr)):
                port_rets.append(np.nansum(prev_weights * dr))
                sig_dates.append(dates[i+1])
            continue
        X = get_composite_signal(factors, dates[i])
        if np.all(X == 0): continue
        # Signal dispersion determines N
        disp = np.std(X)
        # Higher dispersion = more extreme views = use fewer assets (concentrated)
        # Lower dispersion = weaker views = use more assets (diversified)
        if disp > 0.5:
            n_ls = 3
        elif disp > 0.3:
            n_ls = 4
        else:
            n_ls = 5
        ranks = rankdata(X)
        w = np.zeros(n_assets)
        w[ranks > (n_assets - n_ls)] = 1.0 / n_ls
        w[ranks <= n_ls] = -1.0 / n_ls
        turnover = np.sum(np.abs(w - prev_weights))
        fee = turnover * FEE_RATE
        dr = rets.loc[dates[i+1]].values
        if np.any(np.isnan(dr)): continue
        port_rets.append(np.nansum(w * dr) - fee)
        sig_dates.append(dates[i+1])
        prev_weights = w.copy()
    return pd.Series(port_rets, index=sig_dates)


def backtest_risk_parity(close, factors, rebal_freq=5, start_idx=120, n_long=4, n_short=4):
    """H-512: Risk-parity — equal risk contribution via inverse vol weighting."""
    rets = close.pct_change()
    vol20 = rets.rolling(20).std()
    dates = close.index.tolist()
    n_assets = len(close.columns)
    prev_weights = np.zeros(n_assets)
    port_rets, sig_dates = [], []

    for i in range(start_idx, len(dates) - 1):
        if (i - start_idx) % rebal_freq != 0:
            dr = rets.loc[dates[i+1]].values
            if not np.any(np.isnan(dr)):
                port_rets.append(np.nansum(prev_weights * dr))
                sig_dates.append(dates[i+1])
            continue
        X = get_composite_signal(factors, dates[i])
        if np.all(X == 0): continue
        ranks = rankdata(X)
        long_mask = ranks > (n_assets - n_long)
        short_mask = ranks <= n_short

        v = vol20.loc[dates[i]].values
        inv_v = 1.0 / (v + 1e-10)

        w = np.zeros(n_assets)
        # Long side: inverse-vol weighted
        if long_mask.sum() > 0:
            long_inv = inv_v[long_mask]
            w[long_mask] = long_inv / long_inv.sum()
        # Short side: inverse-vol weighted
        if short_mask.sum() > 0:
            short_inv = inv_v[short_mask]
            w[short_mask] = -(short_inv / short_inv.sum())

        turnover = np.sum(np.abs(w - prev_weights))
        fee = turnover * FEE_RATE
        dr = rets.loc[dates[i+1]].values
        if np.any(np.isnan(dr)): continue
        port_rets.append(np.nansum(w * dr) - fee)
        sig_dates.append(dates[i+1])
        prev_weights = w.copy()
    return pd.Series(port_rets, index=sig_dates)


def main():
    print("=" * 70)
    print("H-505 to H-512: PORTFOLIO CONSTRUCTION IMPROVEMENTS")
    print("=" * 70)

    close, volume, high, low, opn, all_dates = fetch_all_data()
    print(f"  Date range: {all_dates[0]} to {all_dates[-1]} ({len(all_dates)} days)")

    print("\nComputing 10 core factors...")
    factors = compute_core_factors(close, volume, high, low, opn)

    # Base ensemble
    print("\nBase ensemble (top/bottom 4, equal weight, 5d rebal)...")
    rets_base = backtest_base(close, factors)
    m_base = compute_metrics(rets_base)
    print(f"  Sharpe: {m_base['sharpe']:.3f}, Ann: {m_base['annual_return']*100:+.1f}%, "
          f"DD: {m_base['max_drawdown']*100:.1f}%")

    # H-012 for correlation
    mom_only = {'momentum': factors['momentum']}
    rets_h012 = backtest_base(close, mom_only, start_idx=60)

    results = []

    # H-505: Continuous weighting
    print("\n" + "=" * 50)
    rets_505 = backtest_continuous(close, factors)
    r = evaluate("H-505 Continuous Weighting", rets_505, rets_base, rets_h012)
    results.append(r)

    # H-506: Volatility-scaled
    print("\n" + "=" * 50)
    rets_506 = backtest_vol_scaled(close, factors)
    r = evaluate("H-506 Vol-Scaled Weights", rets_506, rets_base, rets_h012)
    results.append(r)

    # H-507: Multi-horizon
    print("\n" + "=" * 50)
    rets_507 = backtest_multi_horizon(close, factors)
    r = evaluate("H-507 Multi-Horizon (3/5/10d)", rets_507, rets_base, rets_h012)
    results.append(r)

    # H-508: Asymmetric long/short
    print("\n" + "=" * 50)
    rets_508 = backtest_asymmetric(close, factors, n_long=5, n_short=3)
    r = evaluate("H-508 Asymmetric L5/S3", rets_508, rets_base, rets_h012)
    results.append(r)

    # H-509: Signal threshold
    print("\n" + "=" * 50)
    rets_509 = backtest_threshold(close, factors, threshold=0.3)
    r = evaluate("H-509 Signal Threshold (0.3)", rets_509, rets_base, rets_h012)
    results.append(r)

    # H-510: Turnover-penalized
    print("\n" + "=" * 50)
    rets_510 = backtest_turnover_penalized(close, factors, blend=0.6)
    r = evaluate("H-510 Turnover-Penalized (0.6)", rets_510, rets_base, rets_h012)
    results.append(r)

    # H-511: Dynamic N
    print("\n" + "=" * 50)
    rets_511 = backtest_dynamic_n(close, factors)
    r = evaluate("H-511 Dynamic N", rets_511, rets_base, rets_h012)
    results.append(r)

    # H-512: Risk-parity
    print("\n" + "=" * 50)
    rets_512 = backtest_risk_parity(close, factors)
    r = evaluate("H-512 Risk-Parity", rets_512, rets_base, rets_h012)
    results.append(r)

    # Parameter sweep for promising approaches
    print("\n" + "=" * 70)
    print("PARAMETER SWEEPS")
    print("=" * 70)

    # H-508 sweep: different N_long/N_short combos
    print("\nH-508 Asymmetric sweep:")
    for nl in [3, 4, 5, 6]:
        for ns in [2, 3, 4]:
            if nl + ns > 10: continue
            rets_r = backtest_asymmetric(close, factors, n_long=nl, n_short=ns)
            m = compute_metrics(rets_r)
            print(f"  L{nl}/S{ns}: Sharpe {m['sharpe']:.3f} Ann {m['annual_return']*100:+.1f}% "
                  f"DD {m['max_drawdown']*100:.1f}%")

    # H-510 sweep: different blend ratios
    print("\nH-510 Blend sweep:")
    for blend in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        rets_r = backtest_turnover_penalized(close, factors, blend=blend)
        m = compute_metrics(rets_r)
        print(f"  blend={blend:.1f}: Sharpe {m['sharpe']:.3f} Ann {m['annual_return']*100:+.1f}%")

    # SUMMARY
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nBase: Sharpe {m_base['sharpe']:.3f}")
    for r in results:
        m = r['metrics']
        imp = r['improvement']
        wf = f"{r['wf_pos']}/{r['wf_total']}"
        sh = "PASS" if r['sh_pass'] else "FAIL"
        print(f"  {r['name']:45s} {r['status']:10s} Sharpe {m['sharpe']:.3f} "
              f"({imp*100:+.1f}%) WF {wf} SH {sh}")

    confirmed = [r for r in results if r['status'] == 'CONFIRMED']
    print(f"\n  CONFIRMED: {len(confirmed)}, REJECTED: {len(results) - len(confirmed)}")
    for r in confirmed:
        print(f"    {r['name']}: Sharpe {r['metrics']['sharpe']:.3f}")


if __name__ == "__main__":
    main()
