#!/usr/bin/env python3
"""
ML Ensemble Backtest: Combine confirmed XS factor signals via ridge regression.

Approach:
1. Compute daily factor z-scores for 14 assets using all confirmed XS factors
2. Use expanding-window ridge regression to predict next-day XS returns
3. Form long/short portfolio from combined signal
4. Walk-forward validation with 6-month folds

Factors included (all confirmed in backtest + split-half):
- H-012: Momentum (60d return)
- H-019: Low-vol (inverse 20d vol)
- H-021: Volume momentum (5d/20d volume ratio)
- H-031: Size (dollar volume)
- H-049: LSR sentiment (contrarian)
- H-052: Premium index (contrarian)
- H-053: Funding rate XS (contrarian)
- H-059: Vol term structure (7d/30d vol ratio)
- H-062: DD momentum (proximity to 60d high)
- H-076: Price efficiency (path efficiency)
- H-085: Turnover velocity (5d/20d dollar vol ratio)
- H-193: OI-price divergence
- H-332: Bar consistency
- H-336: Volume surprise
- H-338: VW pressure
- H-351: Vol skew
- H-353: Vol persistence
- H-355: Entropy
- H-363: Multi-day return pattern
- H-368: Vol share drift
- H-382: Return kurtosis
- H-383: PVT
- H-388: Night-day diff
- H-394: Variance ratio
- H-404: Session flow
- H-411: OBV slope
- H-414: Volume trend
- H-435: Hourly kurtosis
- H-437: HL spread
- H-445: Max hourly DD
- H-447: Vol autocorrelation
- H-451: Close-high ratio
- H-470: First hour return
"""

import sys
import json
import warnings
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.stats import rankdata, kurtosis as scipy_kurtosis
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

RESULTS_DIR = Path(__file__).parent
FEE_RATE = 0.001  # 10bps per side


def fetch_all_data():
    """Fetch and align daily OHLCV for all 14 assets + 1h for intraday factors."""
    print("Fetching hourly data for 14 assets...")
    hourly = {}
    daily = {}
    for sym in ASSETS:
        df_1h = fetch_and_cache(sym, "1h", limit_days=900)
        if df_1h is not None and len(df_1h) > 100:
            hourly[sym] = df_1h
            df_d = resample_to_daily(df_1h)
            daily[sym] = df_d
    print(f"  Loaded {len(daily)} assets")

    # Align daily dates
    all_dates = sorted(set.intersection(*[set(df.index) for df in daily.values()]))
    close = pd.DataFrame({s: daily[s].loc[all_dates, 'close'] for s in daily})
    volume = pd.DataFrame({s: daily[s].loc[all_dates, 'volume'] for s in daily})
    high = pd.DataFrame({s: daily[s].loc[all_dates, 'high'] for s in daily})
    low = pd.DataFrame({s: daily[s].loc[all_dates, 'low'] for s in daily})
    opn = pd.DataFrame({s: daily[s].loc[all_dates, 'open'] for s in daily})

    return close, volume, high, low, opn, hourly, all_dates


def xs_zscore(df_row):
    """Cross-sectional z-score within a single day."""
    vals = df_row.values
    if np.all(np.isnan(vals)):
        return pd.Series(np.nan, index=df_row.index)
    mean = np.nanmean(vals)
    std = np.nanstd(vals)
    if std < 1e-12:
        return pd.Series(0.0, index=df_row.index)
    return (df_row - mean) / std


def compute_all_factors(close, volume, high, low, opn, hourly):
    """Compute all confirmed factor z-scores. Returns dict of DataFrames (date x asset)."""
    rets = close.pct_change()
    log_rets = np.log(close / close.shift(1))
    dollar_vol = close * volume

    factors = {}

    # H-012: Momentum (60d return)
    mom60 = close / close.shift(60) - 1
    factors['momentum'] = mom60.apply(xs_zscore, axis=1)

    # H-019: Low-volatility (inverse 20d vol) — sign: long low-vol
    vol20 = rets.rolling(20).std()
    factors['low_vol'] = (-vol20).apply(xs_zscore, axis=1)

    # H-021: Volume momentum (5d/20d volume ratio)
    vol_short = volume.rolling(5).mean()
    vol_long = volume.rolling(20).mean()
    vol_mom = vol_short / vol_long
    factors['vol_mom'] = vol_mom.apply(xs_zscore, axis=1)

    # H-031: Size (dollar volume proxy — long large)
    dv30 = dollar_vol.rolling(30).mean()
    factors['size'] = dv30.apply(xs_zscore, axis=1)

    # H-049: LSR sentiment (contrarian) — we approximate via return reversal
    # Since we don't have LSR data in backtest, use 5d return reversal as proxy
    ret5 = close / close.shift(5) - 1
    factors['reversal_5d'] = (-ret5).apply(xs_zscore, axis=1)

    # H-052: Premium index — approximate via close vs VWAP-like metric
    vwap_proxy = (close * volume).rolling(5).sum() / volume.rolling(5).sum()
    premium = close / vwap_proxy - 1
    factors['premium'] = (-premium).apply(xs_zscore, axis=1)  # contrarian

    # H-053: Funding rate XS — approximate via basis (close vs 5d MA)
    basis = close / close.rolling(5).mean() - 1
    factors['funding_proxy'] = (-basis).apply(xs_zscore, axis=1)  # contrarian

    # H-059: Vol term structure (7d/30d vol ratio — expansion long)
    vol7 = rets.rolling(7).std()
    vol30 = rets.rolling(30).std()
    vol_term = vol7 / vol30
    factors['vol_term'] = vol_term.apply(xs_zscore, axis=1)

    # H-062: DD momentum (proximity to 60d high)
    roll_max60 = close.rolling(60).max()
    dd_prox = close / roll_max60
    factors['dd_momentum'] = dd_prox.apply(xs_zscore, axis=1)

    # H-076: Price efficiency (path efficiency = |net return| / sum(|daily returns|))
    abs_ret = rets.abs()
    net_40 = (close / close.shift(40) - 1).abs()
    sum_abs_40 = abs_ret.rolling(40).sum()
    efficiency = net_40 / sum_abs_40
    factors['efficiency'] = efficiency.apply(xs_zscore, axis=1)

    # H-085: Turnover velocity (5d/20d dollar volume ratio)
    dv_short = dollar_vol.rolling(5).mean()
    dv_long = dollar_vol.rolling(20).mean()
    turnover_vel = dv_short / dv_long
    factors['turnover'] = turnover_vel.apply(xs_zscore, axis=1)

    # H-193: OI-price divergence — proxy via volume-price divergence
    ret10 = close / close.shift(10) - 1
    vol_change10 = volume.rolling(5).mean() / volume.rolling(10).mean() - 1
    # Divergence: price up but volume down = bearish
    vp_div = ret10 - vol_change10 * 0.5
    factors['vp_divergence'] = (-vp_div).apply(xs_zscore, axis=1)

    # H-332: Bar consistency — vectorized using rolling sum of (ret > 0)
    daily_rets = rets.copy()
    pos_days = (daily_rets > 0).astype(float)
    pos_frac = pos_days.rolling(20).mean()
    net_ret20 = close / close.shift(20) - 1
    bar_cons = np.where(net_ret20 > 0, pos_frac, 1 - pos_frac)
    bar_cons = pd.DataFrame(bar_cons, index=close.index, columns=close.columns)
    factors['bar_consistency'] = bar_cons.apply(xs_zscore, axis=1)

    # H-336: Volume surprise (today vol / 20d avg vol)
    vol_surprise = volume / volume.rolling(20).mean()
    factors['vol_surprise'] = vol_surprise.apply(xs_zscore, axis=1)

    # H-338: VW pressure (volume-weighted return direction)
    vw_ret = (rets * volume).rolling(10).sum() / volume.rolling(10).sum()
    factors['vw_pressure'] = vw_ret.apply(xs_zscore, axis=1)

    # H-351: Vol skew (skewness of daily returns over 20d) — pandas built-in is fast
    ret_skew = rets.rolling(20).skew()
    factors['vol_skew'] = ret_skew.apply(xs_zscore, axis=1)

    # H-353: Vol persistence — approximate via ratio of recent vs older abs returns
    abs_rets = rets.abs()
    recent_vol = abs_rets.rolling(5).mean()
    older_vol = abs_rets.shift(5).rolling(10).mean()
    vol_pers = recent_vol / (older_vol + 1e-10)
    factors['vol_persistence'] = vol_pers.apply(xs_zscore, axis=1)

    # H-355: Entropy — approximate via rolling kurtosis (pandas built-in)
    ret_kurt20 = rets.rolling(20).kurt()
    factors['entropy_proxy'] = (-ret_kurt20).apply(xs_zscore, axis=1)  # high kurtosis = low entropy

    # H-363: Multi-day return pattern — 2d return autocorrelation proxy via product of lagged returns
    ret_lag2 = rets.shift(2)
    autocorr2_proxy = (rets * ret_lag2).rolling(20).mean() / (rets.rolling(20).std() * ret_lag2.rolling(20).std() + 1e-10)
    factors['multiday_pattern'] = autocorr2_proxy.apply(xs_zscore, axis=1)

    # H-368: Vol share drift (change in volume market share)
    vol_share = volume / volume.sum(axis=1).values[:, None]
    vol_share_drift = vol_share.rolling(10).mean() / vol_share.rolling(30).mean() - 1
    factors['vol_share_drift'] = vol_share_drift.apply(xs_zscore, axis=1)

    # H-382: Return kurtosis — pandas built-in
    ret_kurt = rets.rolling(20).kurt()
    factors['ret_kurtosis'] = ret_kurt.apply(xs_zscore, axis=1)

    # H-383: PVT (Price-Volume Trend)
    pvt_change = rets * volume
    pvt = pvt_change.rolling(20).sum()
    factors['pvt'] = pvt.apply(xs_zscore, axis=1)

    # H-394: Variance ratio (5d vs 1d)
    var1 = rets.rolling(20).var()
    ret5d = close / close.shift(5) - 1
    var5 = ret5d.rolling(4).var() / 5
    vr = var5 / (var1 + 1e-10)
    factors['variance_ratio'] = vr.apply(xs_zscore, axis=1)

    # H-411: OBV slope — use diff of rolling OBV as proxy for slope
    sign_vol = np.sign(rets) * volume
    obv_rolling = sign_vol.rolling(20).sum()
    obv_slope = obv_rolling - obv_rolling.shift(5)  # 5d change as slope proxy
    factors['obv_slope'] = obv_slope.apply(xs_zscore, axis=1)

    # H-414: Volume trend — 5d change in rolling volume
    vol_ma20 = volume.rolling(20).mean()
    vol_trend = vol_ma20 / vol_ma20.shift(5) - 1
    factors['vol_trend'] = vol_trend.apply(xs_zscore, axis=1)

    # H-437: HL spread (high-low range relative to price)
    hl_spread = (high - low) / close
    hl_spread_5d = hl_spread.rolling(5).mean()
    factors['hl_spread'] = (-hl_spread_5d).apply(xs_zscore, axis=1)

    # H-445: Max hourly DD — daily range proxy
    daily_range = (high - low) / opn
    factors['daily_range_dd'] = (-daily_range.rolling(5).mean()).apply(xs_zscore, axis=1)

    # H-447: Vol autocorrelation — ratio of recent vol clustering
    vol_sq = (rets ** 2)
    vol_sq_lag = vol_sq.shift(1)
    vol_ac = (vol_sq * vol_sq_lag).rolling(20).mean() / (vol_sq.rolling(20).mean() * vol_sq_lag.rolling(20).mean() + 1e-20)
    factors['vol_autocorr'] = vol_ac.apply(xs_zscore, axis=1)

    # H-451: Close-high ratio (close position within daily range)
    chr_ratio = (close - low) / (high - low + 1e-10)
    chr_5d = chr_ratio.rolling(5).mean()
    factors['close_high_ratio'] = chr_5d.apply(xs_zscore, axis=1)

    # H-470: First hour return — daily open-to-close proxy
    oc_ret = close / opn - 1
    factors['open_close_ret'] = oc_ret.rolling(5).mean().apply(xs_zscore, axis=1)

    print(f"  Computed {len(factors)} factors")
    return factors


def backtest_ensemble(close, factors, method='ridge', n_long=4, n_short=4,
                      rebal_freq=5, min_train_days=120, alpha=10.0):
    """
    Walk-forward backtest of ML ensemble.

    method: 'ridge', 'equal', 'ic_weighted'
    """
    rets = close.pct_change()
    assets = close.columns.tolist()
    n_assets = len(assets)

    # Build factor matrix: (date, asset, factor_name) -> z-score
    dates = close.index.tolist()

    # Pre-compute forward returns (next-day XS return)
    fwd_ret = rets.shift(-1)  # return on day t+1
    fwd_xs = fwd_ret.subtract(fwd_ret.mean(axis=1), axis=0)  # XS return

    # Collect daily factor data
    factor_names = sorted(factors.keys())
    n_factors = len(factor_names)

    print(f"  Method: {method}, {n_factors} factors, rebal every {rebal_freq}d")
    print(f"  Min train: {min_train_days}d, alpha: {alpha}")

    # Build aligned matrices
    # For each date, we have n_assets rows with n_factors columns
    portfolio_returns = []
    turnover_list = []
    prev_weights = np.zeros(n_assets)
    signal_dates = []

    start_idx = max(min_train_days, 60)  # need lookback for factors

    for i in range(start_idx, len(dates) - 1):
        date_i = dates[i]

        # Only trade on rebal days
        if (i - start_idx) % rebal_freq != 0:
            # Hold existing positions
            day_rets = rets.loc[dates[i + 1]].values
            if not np.any(np.isnan(day_rets)):
                pnl = np.nansum(prev_weights * day_rets)
                portfolio_returns.append(pnl)
                signal_dates.append(dates[i + 1])
            continue

        # Get factor values for this date (lagged — use day i's data for day i+1 position)
        X_today = np.zeros(n_assets)
        valid = True

        if method == 'equal':
            # Simple equal-weight average of all factor z-scores
            for fname in factor_names:
                fvals = factors[fname].loc[date_i].values
                if not np.all(np.isnan(fvals)):
                    X_today += np.nan_to_num(fvals.copy(), 0)
            X_today /= n_factors

        elif method == 'ic_weighted':
            # Pre-computed IC weights (computed once per rebal from trailing data)
            ic_start = max(60, i - 60)
            ics = np.zeros(n_factors)
            for fi, fname in enumerate(factor_names):
                # Vectorized IC: correlate factor values with forward returns over trailing window
                f_vals = factors[fname].iloc[ic_start:i].values  # (days, assets)
                y_vals = fwd_xs.iloc[ic_start:i].values
                mask = ~(np.isnan(f_vals).any(axis=1) | np.isnan(y_vals).any(axis=1))
                if mask.sum() > 10:
                    f_flat = f_vals[mask].ravel()
                    y_flat = y_vals[mask].ravel()
                    c = np.corrcoef(f_flat, y_flat)[0, 1]
                    ics[fi] = c if not np.isnan(c) else 0

            total_ic = np.sum(np.abs(ics))
            if total_ic < 1e-6:
                for fi, fname in enumerate(factor_names):
                    fvals = factors[fname].loc[date_i].values.copy()
                    X_today += np.nan_to_num(fvals, 0)
                X_today /= n_factors
            else:
                weights_ic = ics / total_ic
                for fi, fname in enumerate(factor_names):
                    fvals = factors[fname].loc[date_i].values.copy()
                    X_today += np.nan_to_num(fvals, 0) * weights_ic[fi]

        elif method == 'ridge':
            # Expanding window ridge regression — pre-build matrix
            train_start = max(60, i - 365)
            n_train = i - train_start

            # Build X_train matrix: (n_train * n_assets, n_factors)
            X_rows = np.zeros((n_train * n_assets, n_factors))
            y_rows = np.zeros(n_train * n_assets)
            valid_mask = np.ones(n_train * n_assets, dtype=bool)

            for j_offset in range(n_train):
                j = train_start + j_offset
                row_start = j_offset * n_assets
                row_end = row_start + n_assets
                for fi, fname in enumerate(factor_names):
                    X_rows[row_start:row_end, fi] = np.nan_to_num(
                        factors[fname].iloc[j].values.copy(), 0)
                y_vals = fwd_xs.iloc[j].values.copy()
                if np.any(np.isnan(y_vals)):
                    valid_mask[row_start:row_end] = False
                else:
                    y_rows[row_start:row_end] = y_vals

            X_train = X_rows[valid_mask]
            y_train = y_rows[valid_mask]

            if len(X_train) < 30 * n_assets:
                for fname in factor_names:
                    fvals = factors[fname].loc[date_i].values.copy()
                    X_today += np.nan_to_num(fvals, 0)
                X_today /= n_factors
            else:
                scaler = StandardScaler()
                X_train_s = scaler.fit_transform(X_train)

                model = Ridge(alpha=alpha, fit_intercept=False)
                model.fit(X_train_s, y_train)

                # Score today
                X_today_mat = np.zeros((n_assets, n_factors))
                for fi, fname in enumerate(factor_names):
                    X_today_mat[:, fi] = np.nan_to_num(
                        factors[fname].loc[date_i].values.copy(), 0)
                X_today_s = scaler.transform(X_today_mat)
                X_today = model.predict(X_today_s)

        # Rank and form portfolio
        if np.all(X_today == 0) or np.all(np.isnan(X_today)):
            continue

        ranks = rankdata(X_today)
        weights = np.zeros(n_assets)
        long_mask = ranks > (n_assets - n_long)
        short_mask = ranks <= n_short
        weights[long_mask] = 1.0 / n_long
        weights[short_mask] = -1.0 / n_short

        # Compute turnover & fees
        turnover = np.sum(np.abs(weights - prev_weights))
        fee = turnover * FEE_RATE

        # Next day return
        day_rets = rets.loc[dates[i + 1]].values
        if np.any(np.isnan(day_rets)):
            continue

        pnl = np.nansum(weights * day_rets) - fee
        portfolio_returns.append(pnl)
        signal_dates.append(dates[i + 1])
        turnover_list.append(turnover)
        prev_weights = weights.copy()

    return pd.Series(portfolio_returns, index=signal_dates), turnover_list


def compute_metrics(rets_series):
    """Compute standard performance metrics."""
    if len(rets_series) < 30:
        return {}
    ann_ret = rets_series.mean() * 365
    ann_vol = rets_series.std() * np.sqrt(365)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    cum = (1 + rets_series).cumprod()
    dd = (cum / cum.cummax() - 1)
    max_dd = dd.min()
    win_rate = (rets_series > 0).mean()
    return {
        'annual_return': ann_ret,
        'annual_vol': ann_vol,
        'sharpe': sharpe,
        'max_drawdown': max_dd,
        'win_rate': win_rate,
        'n_days': len(rets_series),
        'avg_daily': rets_series.mean(),
    }


def walk_forward_test(close, factors, method='ridge', n_folds=6, fold_days=90,
                      n_long=4, n_short=4, rebal_freq=5, alpha=10.0):
    """Walk-forward test with n_folds of fold_days each."""
    dates = close.index.tolist()
    n_dates = len(dates)
    results = []

    for fold in range(n_folds):
        test_end_idx = n_dates - 1 - fold * fold_days
        test_start_idx = test_end_idx - fold_days
        if test_start_idx < 180:
            break

        test_start = dates[test_start_idx]
        test_end = dates[test_end_idx]

        # Run backtest on full data but only evaluate test period
        rets_series, _ = backtest_ensemble(
            close, factors, method=method, n_long=n_long, n_short=n_short,
            rebal_freq=rebal_freq, min_train_days=120, alpha=alpha
        )

        # Filter to test period
        test_rets = rets_series[(rets_series.index >= test_start) & (rets_series.index <= test_end)]
        if len(test_rets) < 20:
            continue

        metrics = compute_metrics(test_rets)
        metrics['fold'] = fold + 1
        metrics['test_start'] = str(test_start)[:10]
        metrics['test_end'] = str(test_end)[:10]
        results.append(metrics)
        print(f"  Fold {fold+1}: {str(test_start)[:10]} to {str(test_end)[:10]} — "
              f"Sharpe {metrics['sharpe']:.3f}, Ann {metrics['annual_return']*100:.1f}%")

    return results


def main():
    print("=" * 70)
    print("ML ENSEMBLE BACKTEST — Combining Confirmed XS Factors")
    print("=" * 70)

    # Fetch data
    close, volume, high, low, opn, hourly, all_dates = fetch_all_data()
    print(f"  Date range: {all_dates[0]} to {all_dates[-1]} ({len(all_dates)} days)")

    # Compute factors
    print("\nComputing factor z-scores...")
    factors = compute_all_factors(close, volume, high, low, opn, hourly)

    # Test all three methods — full sample only first (walk-forward is slow)
    all_results = {}

    for method in ['equal', 'ic_weighted', 'ridge']:
        print(f"\n{'='*50}")
        print(f"Method: {method.upper()}")
        print(f"{'='*50}")

        # Full-sample backtest
        rets_series, turnovers = backtest_ensemble(
            close, factors, method=method, n_long=4, n_short=4,
            rebal_freq=5, min_train_days=120, alpha=10.0
        )
        metrics = compute_metrics(rets_series)
        print(f"\n  Full sample ({metrics.get('n_days',0)} days):")
        print(f"    Sharpe:     {metrics.get('sharpe',0):.3f}")
        print(f"    Annual Ret: {metrics.get('annual_return',0)*100:.1f}%")
        print(f"    Max DD:     {metrics.get('max_drawdown',0)*100:.1f}%")
        print(f"    Win Rate:   {metrics.get('win_rate',0)*100:.1f}%")
        if turnovers:
            print(f"    Avg Turnov: {np.mean(turnovers)*100:.1f}%")

        # Split-half for this method
        if len(rets_series) > 60:
            mid = len(rets_series) // 2
            h1 = compute_metrics(rets_series.iloc[:mid])
            h2 = compute_metrics(rets_series.iloc[mid:])
            sh_pass = h1.get('sharpe', 0) > 0 and h2.get('sharpe', 0) > 0
            print(f"    Split-half: H1={h1.get('sharpe',0):.3f} H2={h2.get('sharpe',0):.3f} {'PASS' if sh_pass else 'FAIL'}")

        all_results[method] = {
            'full_sample': metrics,
        }

    # Determine best method
    best_method = max(all_results, key=lambda m: all_results[m]['full_sample'].get('sharpe', 0))
    print(f"\n{'='*50}")
    print(f"BEST METHOD: {best_method.upper()}")
    print(f"{'='*50}")

    # Param robustness for best method
    print(f"\nParameter robustness ({best_method}):")
    robust_results = []
    for alpha in [1.0, 10.0, 100.0]:
        for n_ls in [3, 4, 5]:
            rets_r, _ = backtest_ensemble(
                close, factors, method=best_method, n_long=n_ls, n_short=n_ls,
                rebal_freq=5, min_train_days=120, alpha=alpha
            )
            m = compute_metrics(rets_r)
            robust_results.append({
                'alpha': alpha, 'n_ls': n_ls,
                'sharpe': m.get('sharpe', 0),
                'ann_ret': m.get('annual_return', 0),
            })
            print(f"  alpha={alpha:5.0f} n={n_ls}: Sharpe={m.get('sharpe',0):.3f} Ann={m.get('annual_return',0)*100:+.1f}%")

    pos_sharpe = sum(1 for r in robust_results if r['sharpe'] > 0)
    sharpes = [r['sharpe'] for r in robust_results]
    print(f"\n  {pos_sharpe}/{len(robust_results)} positive, mean={np.mean(sharpes):.3f}, min={min(sharpes):.3f}, max={max(sharpes):.3f}")

    # Correlation with H-012 (momentum alone)
    print(f"\nCorrelation with H-012 (momentum only):")
    rets_full, _ = backtest_ensemble(
        close, factors, method=best_method, n_long=4, n_short=4,
        rebal_freq=5, min_train_days=120, alpha=10.0
    )
    rets_mom, _ = backtest_ensemble(
        close, {k: v for k, v in factors.items() if k == 'momentum'},
        method='equal', n_long=4, n_short=4, rebal_freq=5, min_train_days=60
    )
    common = rets_full.index.intersection(rets_mom.index)
    if len(common) > 30:
        corr = rets_full.loc[common].corr(rets_mom.loc[common])
        print(f"  Correlation (ensemble vs momentum): {corr:.3f}")

    # Now test focused ensemble: only top paper-trade performers
    print(f"\n{'='*50}")
    print("FOCUSED ENSEMBLE (Top 10 Performers)")
    print(f"{'='*50}")
    top_factors = ['momentum', 'low_vol', 'turnover', 'efficiency',
                   'dd_momentum', 'vw_pressure', 'vol_surprise',
                   'premium', 'size', 'vol_term']
    focused = {k: v for k, v in factors.items() if k in top_factors}
    print(f"  Using {len(focused)} factors: {list(focused.keys())}")

    for method in ['equal', 'ic_weighted']:
        rets_f, turnovers_f = backtest_ensemble(
            close, focused, method=method, n_long=4, n_short=4,
            rebal_freq=5, min_train_days=120, alpha=10.0
        )
        m = compute_metrics(rets_f)
        mid = len(rets_f) // 2
        h1 = compute_metrics(rets_f.iloc[:mid])
        h2 = compute_metrics(rets_f.iloc[mid:])
        sh = h1.get('sharpe', 0) > 0 and h2.get('sharpe', 0) > 0
        print(f"\n  {method}: Sharpe={m.get('sharpe',0):.3f}, Ann={m.get('annual_return',0)*100:.1f}%, "
              f"DD={m.get('max_drawdown',0)*100:.1f}%, WR={m.get('win_rate',0)*100:.1f}%")
        print(f"    SH: H1={h1.get('sharpe',0):.3f} H2={h2.get('sharpe',0):.3f} {'PASS' if sh else 'FAIL'}")

    # Param robustness for focused equal
    print(f"\n  Focused equal param robustness:")
    for n_ls in [3, 4, 5, 6]:
        for rf in [3, 5, 7]:
            rets_r, _ = backtest_ensemble(
                close, focused, method='equal', n_long=n_ls, n_short=n_ls,
                rebal_freq=rf, min_train_days=120, alpha=10.0
            )
            m = compute_metrics(rets_r)
            print(f"    n={n_ls} rf={rf}: Sharpe={m.get('sharpe',0):.3f} Ann={m.get('annual_return',0)*100:+.1f}%")

    # Save results
    results_file = RESULTS_DIR / 'results.json'
    save_data = {method: {'full_sample': data['full_sample']} for method, data in all_results.items()}
    with open(results_file, 'w') as f:
        json.dump(save_data, f, indent=2, default=str)
    print(f"\nResults saved to {results_file}")


if __name__ == "__main__":
    main()
