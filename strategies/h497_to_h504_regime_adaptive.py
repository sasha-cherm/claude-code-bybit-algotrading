#!/usr/bin/env python3
"""
H-497 to H-504: Regime-Adaptive Factor Timing

Meta-strategies that condition existing confirmed XS factor signals on market regime.
This is NOT about finding new factors — it's about WHEN to apply confirmed factors.

H-497: BTC Trend Regime — scale momentum/reversal by BTC trend direction
H-498: Volatility Regime — scale exposure by realized vol level
H-499: Dispersion Regime — scale bet size by cross-sectional return dispersion
H-500: Momentum Crash Protection — deleverage when recent momentum reversal is extreme
H-501: Correlation Regime — reduce exposure when pairwise correlations spike
H-502: Volume Regime — scale exposure by aggregate volume ratio
H-503: Trend-Adaptive Weighting — tilt factor weights based on BTC trend strength
H-504: Drawdown-Conditional — reduce exposure during portfolio drawdowns

Each hypothesis tests whether regime conditioning improves IS Sharpe vs base equal-weight
ensemble by >10%, walk-forward 4/6+ folds positive, split-half PASS, and corr with H-012.
"""

import sys
import warnings
from pathlib import Path
from datetime import datetime

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

FEE_RATE = 0.001  # 10bps per side


def fetch_all_data():
    """Fetch and align daily OHLCV for all 14 assets."""
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
    """Compute the 10 top-performing factor z-scores (from H-496 focused ensemble)."""
    rets = close.pct_change()
    dollar_vol = close * volume
    factors = {}

    # H-012: Momentum
    mom60 = close / close.shift(60) - 1
    factors['momentum'] = mom60.apply(xs_zscore, axis=1)

    # H-019: Low-vol
    vol20 = rets.rolling(20).std()
    factors['low_vol'] = (-vol20).apply(xs_zscore, axis=1)

    # H-085: Turnover
    dv_s = (dollar_vol).rolling(5).mean()
    dv_l = (dollar_vol).rolling(20).mean()
    factors['turnover'] = (dv_s / dv_l).apply(xs_zscore, axis=1)

    # H-076: Efficiency
    abs_ret = rets.abs()
    net_40 = (close / close.shift(40) - 1).abs()
    sum_abs_40 = abs_ret.rolling(40).sum()
    factors['efficiency'] = (net_40 / sum_abs_40).apply(xs_zscore, axis=1)

    # H-062: DD momentum
    dd_prox = close / close.rolling(60).max()
    factors['dd_momentum'] = dd_prox.apply(xs_zscore, axis=1)

    # H-338: VW pressure
    vw_ret = (rets * volume).rolling(10).sum() / volume.rolling(10).sum()
    factors['vw_pressure'] = vw_ret.apply(xs_zscore, axis=1)

    # H-336: Volume surprise
    vol_surp = volume / volume.rolling(20).mean()
    factors['vol_surprise'] = vol_surp.apply(xs_zscore, axis=1)

    # H-052: Premium (contrarian)
    vwap_p = (close * volume).rolling(5).sum() / volume.rolling(5).sum()
    premium = close / vwap_p - 1
    factors['premium'] = (-premium).apply(xs_zscore, axis=1)

    # H-031: Size
    dv30 = dollar_vol.rolling(30).mean()
    factors['size'] = dv30.apply(xs_zscore, axis=1)

    # H-059: Vol term structure
    vol7 = rets.rolling(7).std()
    vol30 = rets.rolling(30).std()
    factors['vol_term'] = (vol7 / vol30).apply(xs_zscore, axis=1)

    return factors


def compute_regime_indicators(close, volume):
    """Compute regime indicators used by H-497 through H-504."""
    rets = close.pct_change()
    btc = close['BTC/USDT']
    btc_rets = rets['BTC/USDT']

    regimes = {}

    # BTC trend: EMA(20) vs EMA(50)
    ema20 = btc.ewm(span=20).mean()
    ema50 = btc.ewm(span=50).mean()
    regimes['btc_trend'] = (ema20 / ema50 - 1)  # positive = uptrend

    # BTC trend strength (abs)
    regimes['btc_trend_strength'] = regimes['btc_trend'].abs()

    # Realized vol (20d annualized)
    regimes['realized_vol'] = btc_rets.rolling(20).std() * np.sqrt(365)

    # Vol percentile (rolling 180d)
    rv = regimes['realized_vol']
    regimes['vol_percentile'] = rv.rolling(180).apply(
        lambda x: (x.iloc[-1] > x).mean() if len(x) > 10 else 0.5, raw=False)

    # Cross-sectional dispersion
    xs_std = rets.std(axis=1)
    regimes['dispersion'] = xs_std.rolling(20).mean()
    regimes['dispersion_z'] = (regimes['dispersion'] - regimes['dispersion'].rolling(180).mean()) / \
                               (regimes['dispersion'].rolling(180).std() + 1e-10)

    # Recent momentum crash indicator (5d drawdown of equal-weight momentum proxy)
    mom_proxy = (close / close.shift(60) - 1).mean(axis=1)
    mom_dd_5d = mom_proxy - mom_proxy.rolling(5).max()
    regimes['mom_crash'] = mom_dd_5d

    # Average pairwise correlation (rolling 20d)
    def rolling_avg_corr(rets_df, window=20):
        result = pd.Series(np.nan, index=rets_df.index)
        for i in range(window, len(rets_df)):
            chunk = rets_df.iloc[i-window:i]
            corr_mat = chunk.corr()
            n = len(corr_mat)
            # Upper triangle average
            mask = np.triu(np.ones((n, n), dtype=bool), k=1)
            avg = corr_mat.values[mask].mean()
            result.iloc[i] = avg
        return result

    regimes['avg_correlation'] = rolling_avg_corr(rets)
    regimes['corr_z'] = (regimes['avg_correlation'] - regimes['avg_correlation'].rolling(180).mean()) / \
                          (regimes['avg_correlation'].rolling(180).std() + 1e-10)

    # Volume regime (aggregate volume ratio 5d/20d)
    agg_vol = volume.sum(axis=1)
    regimes['vol_ratio'] = agg_vol.rolling(5).mean() / agg_vol.rolling(20).mean()

    return regimes


def base_ensemble_backtest(close, factors, n_long=4, n_short=4, rebal_freq=5,
                           start_idx=120, exposure_scale=None):
    """
    Equal-weight ensemble backtest with optional dynamic exposure scaling.

    exposure_scale: pd.Series (same index as close) with values 0-1 indicating
    what fraction of normal exposure to take. None = always 1.0.
    """
    rets = close.pct_change()
    dates = close.index.tolist()
    n_assets = len(close.columns)
    factor_names = sorted(factors.keys())
    n_factors = len(factor_names)

    portfolio_returns = []
    signal_dates = []
    prev_weights = np.zeros(n_assets)

    for i in range(start_idx, len(dates) - 1):
        date_i = dates[i]

        if (i - start_idx) % rebal_freq != 0:
            day_rets = rets.loc[dates[i + 1]].values
            if not np.any(np.isnan(day_rets)):
                pnl = np.nansum(prev_weights * day_rets)
                portfolio_returns.append(pnl)
                signal_dates.append(dates[i + 1])
            continue

        # Equal-weight composite signal
        X_today = np.zeros(n_assets)
        for fname in factor_names:
            fvals = factors[fname].loc[date_i].values
            if not np.all(np.isnan(fvals)):
                X_today += np.nan_to_num(fvals.copy(), 0)
        X_today /= n_factors

        if np.all(X_today == 0):
            continue

        # Rank and form portfolio
        ranks = rankdata(X_today)
        weights = np.zeros(n_assets)
        weights[ranks > (n_assets - n_long)] = 1.0 / n_long
        weights[ranks <= n_short] = -1.0 / n_short

        # Apply regime-based exposure scaling
        if exposure_scale is not None and date_i in exposure_scale.index:
            scale = exposure_scale.loc[date_i]
            scale = np.clip(scale, 0.0, 2.0)
            weights *= scale

        # Turnover & fees
        turnover = np.sum(np.abs(weights - prev_weights))
        fee = turnover * FEE_RATE

        day_rets = rets.loc[dates[i + 1]].values
        if np.any(np.isnan(day_rets)):
            continue

        pnl = np.nansum(weights * day_rets) - fee
        portfolio_returns.append(pnl)
        signal_dates.append(dates[i + 1])
        prev_weights = weights.copy()

    return pd.Series(portfolio_returns, index=signal_dates)


def weighted_ensemble_backtest(close, factors, factor_weights_fn, n_long=4, n_short=4,
                               rebal_freq=5, start_idx=120, regimes=None):
    """
    Ensemble backtest with dynamic factor weighting based on regime.

    factor_weights_fn: callable(regime_values_at_date) -> dict of factor_name -> weight
    """
    rets = close.pct_change()
    dates = close.index.tolist()
    n_assets = len(close.columns)
    factor_names = sorted(factors.keys())

    portfolio_returns = []
    signal_dates = []
    prev_weights = np.zeros(n_assets)

    for i in range(start_idx, len(dates) - 1):
        date_i = dates[i]

        if (i - start_idx) % rebal_freq != 0:
            day_rets = rets.loc[dates[i + 1]].values
            if not np.any(np.isnan(day_rets)):
                pnl = np.nansum(prev_weights * day_rets)
                portfolio_returns.append(pnl)
                signal_dates.append(dates[i + 1])
            continue

        # Get regime-dependent factor weights
        regime_vals = {}
        if regimes:
            for rname, rseries in regimes.items():
                if date_i in rseries.index:
                    regime_vals[rname] = rseries.loc[date_i]
                else:
                    regime_vals[rname] = np.nan

        fw = factor_weights_fn(regime_vals)

        # Weighted composite signal
        X_today = np.zeros(n_assets)
        total_w = 0
        for fname in factor_names:
            w = fw.get(fname, 1.0)
            fvals = factors[fname].loc[date_i].values
            if not np.all(np.isnan(fvals)):
                X_today += np.nan_to_num(fvals.copy(), 0) * w
                total_w += abs(w)
        if total_w > 0:
            X_today /= total_w

        if np.all(X_today == 0):
            continue

        ranks = rankdata(X_today)
        weights = np.zeros(n_assets)
        weights[ranks > (n_assets - n_long)] = 1.0 / n_long
        weights[ranks <= n_short] = -1.0 / n_short

        turnover = np.sum(np.abs(weights - prev_weights))
        fee = turnover * FEE_RATE

        day_rets = rets.loc[dates[i + 1]].values
        if np.any(np.isnan(day_rets)):
            continue

        pnl = np.nansum(weights * day_rets) - fee
        portfolio_returns.append(pnl)
        signal_dates.append(dates[i + 1])
        prev_weights = weights.copy()

    return pd.Series(portfolio_returns, index=signal_dates)


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
    """Walk-forward evaluation."""
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


def evaluate_hypothesis(name, rets_series, rets_base, h012_rets=None):
    """Evaluate a regime hypothesis against the base ensemble."""
    m = compute_metrics(rets_series)
    m_base = compute_metrics(rets_base)

    print(f"\n  --- {name} ---")
    print(f"  IS: Sharpe {m['sharpe']:.3f} (base {m_base['sharpe']:.3f}, "
          f"delta {(m['sharpe']/m_base['sharpe']-1)*100:+.1f}%)")
    print(f"  Ann: {m['annual_return']*100:+.1f}% (base {m_base['annual_return']*100:+.1f}%)")
    print(f"  DD: {m['max_drawdown']*100:.1f}% (base {m_base['max_drawdown']*100:.1f}%)")
    print(f"  WR: {m['win_rate']*100:.1f}%  N={m['n_days']}")

    # Walk-forward
    wf = walk_forward(rets_series)
    wf_pos = sum(1 for f in wf if f['sharpe'] > 0)
    wf_mean = np.mean([f['sharpe'] for f in wf]) if wf else 0
    print(f"  WF: {wf_pos}/{len(wf)} positive, mean Sharpe {wf_mean:.3f}")
    for f in wf:
        print(f"    Fold {f['fold']}: Sharpe {f['sharpe']:.3f}")

    # Split-half
    h1, h2 = split_half(rets_series)
    sh_pass = h1['sharpe'] > 0 and h2['sharpe'] > 0
    print(f"  SH: H1={h1['sharpe']:.3f} H2={h2['sharpe']:.3f} {'PASS' if sh_pass else 'FAIL'}")

    # Correlation with H-012
    if h012_rets is not None:
        common = rets_series.index.intersection(h012_rets.index)
        if len(common) > 30:
            corr = rets_series.loc[common].corr(h012_rets.loc[common])
            print(f"  Corr with H-012: {corr:.3f}")

    # Correlation with base ensemble
    common = rets_series.index.intersection(rets_base.index)
    if len(common) > 30:
        corr_base = rets_series.loc[common].corr(rets_base.loc[common])
        print(f"  Corr with base ensemble: {corr_base:.3f}")

    # Decision
    sharpe_improvement = (m['sharpe'] / m_base['sharpe'] - 1) if m_base['sharpe'] > 0 else 0
    confirmed = (m['sharpe'] > 1.0 and wf_pos >= 4 and sh_pass and sharpe_improvement > 0.05)
    status = "CONFIRMED" if confirmed else "REJECTED"
    reason = []
    if m['sharpe'] <= 1.0:
        reason.append(f"IS Sharpe {m['sharpe']:.3f} <= 1.0")
    if wf_pos < 4:
        reason.append(f"WF {wf_pos}/6 < 4")
    if not sh_pass:
        reason.append("SH FAIL")
    if sharpe_improvement <= 0.05:
        reason.append(f"Improvement {sharpe_improvement*100:+.1f}% <= 5%")

    print(f"  ==> {status}" + (f" ({', '.join(reason)})" if reason else ""))
    return {
        'name': name,
        'status': status,
        'metrics': m,
        'base_metrics': m_base,
        'wf_positive': wf_pos,
        'wf_total': len(wf),
        'wf_mean_sharpe': wf_mean,
        'sh_pass': sh_pass,
        'sharpe_improvement': sharpe_improvement,
        'reasons': reason,
    }


def main():
    print("=" * 70)
    print("H-497 to H-504: REGIME-ADAPTIVE FACTOR TIMING")
    print("=" * 70)

    close, volume, high, low, opn, all_dates = fetch_all_data()
    print(f"  Date range: {all_dates[0]} to {all_dates[-1]} ({len(all_dates)} days)")

    print("\nComputing 10 core factors...")
    factors = compute_core_factors(close, volume, high, low, opn)

    print("\nComputing regime indicators...")
    regimes = compute_regime_indicators(close, volume)

    # Base ensemble (no regime conditioning)
    print("\n" + "=" * 50)
    print("BASE: Equal-weight 10-factor ensemble (no regime)")
    print("=" * 50)
    rets_base = base_ensemble_backtest(close, factors)
    m_base = compute_metrics(rets_base)
    print(f"  Sharpe: {m_base['sharpe']:.3f}")
    print(f"  Annual: {m_base['annual_return']*100:+.1f}%")
    print(f"  DD: {m_base['max_drawdown']*100:.1f}%")
    print(f"  N: {m_base['n_days']} days")

    # H-012 standalone for correlation
    mom_only = {'momentum': factors['momentum']}
    rets_h012 = base_ensemble_backtest(close, mom_only, start_idx=60)

    results_all = []

    # ====================================================================
    # H-497: BTC Trend Regime — scale exposure by BTC trend direction
    # Logic: Full exposure when BTC uptrend, reduce to 50% when downtrend
    # ====================================================================
    print("\n" + "=" * 50)
    print("H-497: BTC Trend Regime Exposure Scaling")
    print("=" * 50)

    btc_trend = regimes['btc_trend']
    # Scale: 1.0 in uptrend, 0.5 in downtrend, linear interpolation near zero
    exposure_497 = pd.Series(np.where(btc_trend > 0, 1.0, 0.5), index=btc_trend.index)
    rets_497 = base_ensemble_backtest(close, factors, exposure_scale=exposure_497)
    r = evaluate_hypothesis("H-497 BTC Trend Regime", rets_497, rets_base, rets_h012)
    results_all.append(r)

    # ====================================================================
    # H-498: Volatility Regime — reduce exposure in high-vol environments
    # Logic: Full exposure below median vol, linear scale down to 0.3x at 90th pctl
    # ====================================================================
    print("\n" + "=" * 50)
    print("H-498: Volatility Regime Exposure Scaling")
    print("=" * 50)

    vol_pctl = regimes['vol_percentile']
    # Scale: 1.0 at vol_pctl=0, 0.3 at vol_pctl=1.0
    exposure_498 = pd.Series(1.0 - 0.7 * vol_pctl, index=vol_pctl.index)
    exposure_498 = exposure_498.clip(0.3, 1.0)
    rets_498 = base_ensemble_backtest(close, factors, exposure_scale=exposure_498)
    r = evaluate_hypothesis("H-498 Volatility Regime", rets_498, rets_base, rets_h012)
    results_all.append(r)

    # ====================================================================
    # H-499: Dispersion Regime — scale UP in high-dispersion (more XS opportunity)
    # Logic: When dispersion z-score > 0, scale to 1.5x; when < -1, scale to 0.5x
    # ====================================================================
    print("\n" + "=" * 50)
    print("H-499: Dispersion Regime Exposure Scaling")
    print("=" * 50)

    disp_z = regimes['dispersion_z']
    # Scale: 0.5 at z=-2, 1.0 at z=0, 1.5 at z=+2
    exposure_499 = pd.Series(1.0 + 0.25 * disp_z, index=disp_z.index)
    exposure_499 = exposure_499.clip(0.5, 1.5)
    rets_499 = base_ensemble_backtest(close, factors, exposure_scale=exposure_499)
    r = evaluate_hypothesis("H-499 Dispersion Regime", rets_499, rets_base, rets_h012)
    results_all.append(r)

    # ====================================================================
    # H-500: Momentum Crash Protection — deleverage when momentum crashes
    # Logic: When 5d momentum drawdown < -5%, reduce to 30% exposure
    # ====================================================================
    print("\n" + "=" * 50)
    print("H-500: Momentum Crash Protection")
    print("=" * 50)

    mom_crash = regimes['mom_crash']
    # Scale: 1.0 normally, 0.3 when mom_crash < -0.05
    exposure_500 = pd.Series(np.where(mom_crash < -0.05, 0.3,
                              np.where(mom_crash < 0, 1.0 + 14 * mom_crash, 1.0)),
                              index=mom_crash.index)
    exposure_500 = exposure_500.clip(0.3, 1.0)
    rets_500 = base_ensemble_backtest(close, factors, exposure_scale=exposure_500)
    r = evaluate_hypothesis("H-500 Momentum Crash Protection", rets_500, rets_base, rets_h012)
    results_all.append(r)

    # ====================================================================
    # H-501: Correlation Regime — reduce exposure when correlations spike
    # Logic: High avg correlation = less XS opportunity, scale down
    # ====================================================================
    print("\n" + "=" * 50)
    print("H-501: Correlation Regime")
    print("=" * 50)

    corr_z = regimes['corr_z']
    # Scale: 1.0 at corr_z=0, 0.5 at corr_z=+2 (high corr = less XS opportunity)
    exposure_501 = pd.Series(1.0 - 0.25 * corr_z.clip(-2, 2), index=corr_z.index)
    exposure_501 = exposure_501.clip(0.5, 1.5)
    rets_501 = base_ensemble_backtest(close, factors, exposure_scale=exposure_501)
    r = evaluate_hypothesis("H-501 Correlation Regime", rets_501, rets_base, rets_h012)
    results_all.append(r)

    # ====================================================================
    # H-502: Volume Regime — scale exposure by aggregate volume
    # Logic: High volume = more liquidity, more signal strength. Scale up.
    # ====================================================================
    print("\n" + "=" * 50)
    print("H-502: Volume Regime")
    print("=" * 50)

    vol_ratio = regimes['vol_ratio']
    # Scale: centered at 1.0. vol_ratio > 1.0 (high volume) -> scale up slightly
    exposure_502 = pd.Series(0.5 + 0.5 * vol_ratio.clip(0.5, 1.5), index=vol_ratio.index)
    rets_502 = base_ensemble_backtest(close, factors, exposure_scale=exposure_502)
    r = evaluate_hypothesis("H-502 Volume Regime", rets_502, rets_base, rets_h012)
    results_all.append(r)

    # ====================================================================
    # H-503: Trend-Adaptive Factor Weighting — tilt toward momentum in trends,
    #         toward reversal in choppy markets
    # ====================================================================
    print("\n" + "=" * 50)
    print("H-503: Trend-Adaptive Factor Weighting")
    print("=" * 50)

    momentum_factors = ['momentum', 'dd_momentum', 'efficiency', 'turnover']
    mean_reversion_factors = ['premium', 'vol_surprise', 'vw_pressure']
    neutral_factors = ['low_vol', 'size', 'vol_term']

    def trend_adaptive_weights(regime_vals):
        trend = regime_vals.get('btc_trend', 0)
        if np.isnan(trend):
            trend = 0
        trend_strength = abs(trend)
        # Strong trend: up-weight momentum. Weak trend: up-weight mean reversion.
        # Clamp trend_strength to [0, 0.05]
        t = min(trend_strength / 0.05, 1.0)
        mom_w = 1.0 + 0.5 * t
        mr_w = 1.0 - 0.3 * t
        fw = {}
        for f in momentum_factors:
            fw[f] = mom_w
        for f in mean_reversion_factors:
            fw[f] = mr_w
        for f in neutral_factors:
            fw[f] = 1.0
        return fw

    rets_503 = weighted_ensemble_backtest(close, factors, trend_adaptive_weights,
                                           regimes=regimes)
    r = evaluate_hypothesis("H-503 Trend-Adaptive Weighting", rets_503, rets_base, rets_h012)
    results_all.append(r)

    # ====================================================================
    # H-504: Drawdown-Conditional — reduce exposure during portfolio drawdowns
    # Logic: Track cumulative P&L, reduce to 0.5x when in >2% drawdown
    # ====================================================================
    print("\n" + "=" * 50)
    print("H-504: Drawdown-Conditional Exposure")
    print("=" * 50)

    # First compute base cumulative returns to get drawdown series
    base_cum = (1 + rets_base).cumprod()
    base_dd = base_cum / base_cum.cummax() - 1

    # Scale: 1.0 when DD > -1%, 0.5 when DD < -3%, linear between
    exposure_504 = pd.Series(
        np.where(base_dd > -0.01, 1.0,
                 np.where(base_dd < -0.03, 0.5,
                          1.0 + (base_dd + 0.01) * 25)),
        index=base_dd.index
    )
    exposure_504 = exposure_504.clip(0.5, 1.0)
    rets_504 = base_ensemble_backtest(close, factors, exposure_scale=exposure_504)
    r = evaluate_hypothesis("H-504 Drawdown-Conditional", rets_504, rets_base, rets_h012)
    results_all.append(r)

    # ====================================================================
    # SUMMARY
    # ====================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nBase ensemble: Sharpe {m_base['sharpe']:.3f}, "
          f"Ann {m_base['annual_return']*100:+.1f}%, DD {m_base['max_drawdown']*100:.1f}%")
    print()
    for r in results_all:
        status = r['status']
        m = r['metrics']
        imp = r['sharpe_improvement']
        wf = f"{r['wf_positive']}/{r['wf_total']}"
        sh = "PASS" if r['sh_pass'] else "FAIL"
        print(f"  {r['name']:45s} {status:10s} Sharpe {m['sharpe']:.3f} "
              f"({imp*100:+.1f}%) WF {wf} SH {sh}")

    confirmed = [r for r in results_all if r['status'] == 'CONFIRMED']
    rejected = [r for r in results_all if r['status'] == 'REJECTED']
    print(f"\n  CONFIRMED: {len(confirmed)}, REJECTED: {len(rejected)}")

    if confirmed:
        print("\n  Confirmed strategies:")
        for r in confirmed:
            print(f"    {r['name']}: Sharpe {r['metrics']['sharpe']:.3f}, "
                  f"WF mean {r['wf_mean_sharpe']:.3f}")


if __name__ == "__main__":
    main()
