"""
H-045: OI-Volume Confirmation/Divergence Factor
H-046: Price Acceleration Factor (second derivative of momentum)

Research:
- OI change + Volume change combination as cross-sectional signal
- Volume surge + OI increase = new positions being built (momentum confirmation)
- Volume surge + OI decrease = positions being unwound (reversal signal)
- Also test price acceleration (second derivative) as separate factor
- Walk-forward validation, parameter sweep, correlation with existing strategies
"""

import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = ['BTC', 'ETH', 'SOL', 'SUI', 'XRP', 'DOGE', 'AVAX', 'LINK', 'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM']
OI_CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'oi')


def load_oi_panel():
    """Load cached OI data for all assets."""
    oi_dict = {}
    for asset in ASSETS:
        cache_file = os.path.join(OI_CACHE_DIR, f"{asset}_oi_1d.parquet")
        if os.path.exists(cache_file):
            df = pd.read_parquet(cache_file)
            oi_dict[asset] = df['openInterest']
    oi_panel = pd.DataFrame(oi_dict)
    oi_panel = oi_panel.sort_index().dropna(how='all')
    return oi_panel


def load_price_volume_data():
    """Load daily close and volume for all assets."""
    close_dict = {}
    vol_dict = {}
    for asset in ASSETS:
        try:
            df = fetch_and_cache(f"{asset}/USDT", '1h')
            daily_close = df['close'].resample('1D').last().dropna()
            daily_vol = df['volume'].resample('1D').sum().dropna()
            close_dict[asset] = daily_close
            vol_dict[asset] = daily_vol
        except Exception as e:
            print(f"  {asset}: {e}")
    return pd.DataFrame(close_dict), pd.DataFrame(vol_dict)


def compute_oi_volume_factors(oi_panel, vol_panel, close_panel, windows=[5, 10, 20]):
    """
    Compute OI-Volume combination factors.

    Signals:
    1. OI_VOL_CONF: z(vol_change) + z(oi_change) — confirmation (both surging)
    2. OI_VOL_DIV: z(vol_change) - z(oi_change) — divergence (volume up, OI down = unwinding)
    3. OI_VOL_RATIO: oi_change / (vol_change + eps) — OI efficiency per unit volume
    4. NEW_MONEY: rank assets by oi_change * sign(vol_change above median)
    """
    factors = {}

    for w in windows:
        vol_chg = vol_panel.pct_change(w)
        oi_chg = oi_panel.pct_change(w)
        price_chg = close_panel.pct_change(w)

        # Cross-sectional z-scores
        vol_z = vol_chg.sub(vol_chg.mean(axis=1), axis=0).div(vol_chg.std(axis=1) + 1e-10, axis=0)
        oi_z = oi_chg.sub(oi_chg.mean(axis=1), axis=0).div(oi_chg.std(axis=1) + 1e-10, axis=0)
        price_z = price_chg.sub(price_chg.mean(axis=1), axis=0).div(price_chg.std(axis=1) + 1e-10, axis=0)

        # 1. OI-Volume Confirmation: both increasing = momentum confirmation
        # Long assets where both volume and OI are surging
        factors[f'OI_VOL_CONF_{w}d'] = vol_z + oi_z

        # 2. OI-Volume Divergence: high volume + low OI = unwinding/reversal
        # Long assets with volume up, OI down (position closing)
        factors[f'OI_VOL_DIV_{w}d'] = vol_z - oi_z

        # 3. New Money Score: price direction * OI change sign
        # Assets with price up + OI up = new money entering (momentum)
        # Assets with price down + OI up = shorts piling on (further downside)
        # Signal: long "new money bullish" (price up, OI up), short "new money bearish" (price down, OI up)
        new_money = price_z * oi_z.clip(lower=0)  # Only positive OI changes amplify price
        factors[f'NEW_MONEY_{w}d'] = new_money

        # 4. Squeeze Score: opposite — assets with big OI but low volume (illiquid buildup)
        # High OI change but low volume = potentially fragile positions
        factors[f'SQUEEZE_{w}d'] = oi_z - vol_z  # High OI, low volume

        # 5. Triple combination: price + OI + volume all aligned
        factors[f'TRIPLE_{w}d'] = price_z + oi_z + vol_z

        # 6. OI-Volume confirmation with price direction filter
        # Only count OI+Vol confirmation when price is moving in same direction
        confirmation_bullish = (vol_z + oi_z) * np.sign(price_z)
        factors[f'DIRECTED_CONF_{w}d'] = confirmation_bullish

    return factors


def compute_price_acceleration(close_panel, mom_windows=[20, 40, 60], accel_windows=[5, 10, 20]):
    """
    H-046: Price acceleration factor (second derivative of momentum).
    Momentum = price change over window.
    Acceleration = change in momentum = momentum(t) - momentum(t-accel_window).

    High acceleration = momentum is INCREASING (good for trend followers).
    """
    factors = {}

    for mw in mom_windows:
        momentum = close_panel.pct_change(mw)
        for aw in accel_windows:
            accel = momentum - momentum.shift(aw)

            # Cross-sectional z-score
            accel_z = accel.sub(accel.mean(axis=1), axis=0).div(accel.std(axis=1) + 1e-10, axis=0)
            factors[f'ACCEL_M{mw}_A{aw}'] = accel_z

    return factors


def xs_backtest(signal_df, return_df, n_long=4, n_short=4, rebal_days=5,
                start_date=None, end_date=None, fee_bps=4):
    """Cross-sectional backtest: long top-N signal, short bottom-N signal."""
    if start_date:
        signal_df = signal_df.loc[start_date:]
        return_df = return_df.loc[start_date:]
    if end_date:
        signal_df = signal_df.loc[:end_date]
        return_df = return_df.loc[:end_date]

    common_dates = signal_df.index.intersection(return_df.index)
    signal_df = signal_df.loc[common_dates]
    return_df = return_df.loc[common_dates]

    min_assets = n_long + n_short
    valid = signal_df.notna().sum(axis=1) >= min_assets
    signal_df = signal_df[valid]
    return_df = return_df[valid]

    if len(signal_df) < 30:
        return pd.Series(dtype=float), {}

    # Use LAGGED signal (t-1) to avoid look-ahead bias
    signal_lagged = signal_df.shift(1)

    daily_returns = []
    prev_longs = set()
    prev_shorts = set()

    for i, date in enumerate(signal_df.index):
        if i == 0:
            daily_returns.append(0.0)
            continue

        if i % rebal_days == 0:
            sig = signal_lagged.loc[date].dropna()
            if len(sig) < min_assets:
                daily_returns.append(0.0)
                continue

            ranked = sig.sort_values(ascending=False)
            new_longs = set(ranked.index[:n_long])
            new_shorts = set(ranked.index[-n_short:])

            turnover = len(new_longs - prev_longs) + len(new_shorts - prev_shorts)
            fee = turnover * fee_bps / 10000 * 2 / (n_long + n_short)

            prev_longs = new_longs
            prev_shorts = new_shorts
        else:
            fee = 0.0

        day_ret = return_df.loc[date]
        long_ret = day_ret[list(prev_longs)].mean() if prev_longs else 0.0
        short_ret = -day_ret[list(prev_shorts)].mean() if prev_shorts else 0.0

        port_ret = (long_ret + short_ret) / 2 - fee
        daily_returns.append(port_ret)

    equity = pd.Series(daily_returns, index=signal_df.index)

    if len(equity) < 30:
        return equity, {}

    cum = (1 + equity).cumprod()
    metrics = {
        'sharpe': sharpe_ratio(equity, periods_per_year=365),
        'annual_return': annual_return(cum, periods_per_year=365),
        'max_dd': max_drawdown(cum),
        'win_rate': (equity > 0).mean(),
        'n_days': len(equity),
    }
    return equity, metrics


def walk_forward_test(signal_df, return_df, n_long=4, n_short=4, rebal_days=5,
                      n_folds=5, fee_bps=4):
    """Walk-forward test with expanding window."""
    dates = signal_df.index
    total_days = len(dates)
    fold_size = total_days // (n_folds + 1)

    results = []
    for fold in range(n_folds):
        train_end_idx = fold_size * (fold + 2) - 1
        test_start_idx = train_end_idx + 1
        test_end_idx = min(test_start_idx + fold_size - 1, total_days - 1)

        if test_end_idx <= test_start_idx + 10:
            break

        test_start = dates[test_start_idx]
        test_end = dates[test_end_idx]

        equity, metrics = xs_backtest(
            signal_df, return_df, n_long, n_short, rebal_days,
            start_date=test_start, end_date=test_end, fee_bps=fee_bps
        )

        if metrics:
            results.append({
                'fold': fold + 1,
                'start': str(test_start.date()),
                'end': str(test_end.date()),
                'days': metrics['n_days'],
                'sharpe': metrics['sharpe'],
                'annual_return': metrics['annual_return'],
                'max_dd': metrics['max_dd'],
            })

    return results


def parameter_sweep(factor_dict, return_df, n_values=[3, 4, 5],
                    rebal_values=[3, 5, 10], fee_bps=4):
    """Sweep across factor variants and parameters."""
    results = []

    for factor_name, signal_df in factor_dict.items():
        for n in n_values:
            for r in rebal_values:
                equity, metrics = xs_backtest(
                    signal_df, return_df, n_long=n, n_short=n,
                    rebal_days=r, fee_bps=fee_bps
                )
                if metrics and metrics['n_days'] > 60:
                    results.append({
                        'factor': factor_name,
                        'n': n,
                        'rebal': r,
                        'sharpe': metrics['sharpe'],
                        'annual_return': metrics['annual_return'],
                        'max_dd': metrics['max_dd'],
                        'win_rate': metrics['win_rate'],
                        'n_days': metrics['n_days'],
                    })

    return pd.DataFrame(results)


def compute_correlation_with_existing(equity_new, close_panel, oi_panel, return_df):
    """Compute return correlation with H-012 (momentum), H-021 (volume momentum), H-044 (OI-price div)."""
    correlations = {}

    # H-012: 60d momentum, top/bottom 4, 5d rebal
    mom60 = close_panel.pct_change(60)
    mom60_z = mom60.sub(mom60.mean(axis=1), axis=0).div(mom60.std(axis=1) + 1e-10, axis=0)
    eq_h012, _ = xs_backtest(mom60_z, return_df, n_long=4, n_short=4, rebal_days=5)
    if len(eq_h012) > 0:
        common = equity_new.index.intersection(eq_h012.index)
        if len(common) > 30:
            correlations['H-012 (momentum)'] = equity_new.loc[common].corr(eq_h012.loc[common])

    # H-021: volume momentum (5d/20d ratio), top/bottom 4, 3d rebal
    # Simplified: 5d volume / 20d volume
    vol_panel = load_price_volume_data()[1]
    vol_panel = vol_panel.loc[return_df.index]
    vol5 = vol_panel.rolling(5).mean()
    vol20 = vol_panel.rolling(20).mean()
    vol_ratio = vol5 / (vol20 + 1e-10)
    vol_z = vol_ratio.sub(vol_ratio.mean(axis=1), axis=0).div(vol_ratio.std(axis=1) + 1e-10, axis=0)
    eq_h021, _ = xs_backtest(vol_z, return_df, n_long=4, n_short=4, rebal_days=3)
    if len(eq_h021) > 0:
        common = equity_new.index.intersection(eq_h021.index)
        if len(common) > 30:
            correlations['H-021 (vol mom)'] = equity_new.loc[common].corr(eq_h021.loc[common])

    # H-044: OI-Price divergence (20d), top/bottom 5, 10d rebal
    price_chg = close_panel.pct_change(20)
    oi_chg = oi_panel.pct_change(20)
    p_z = price_chg.sub(price_chg.mean(axis=1), axis=0).div(price_chg.std(axis=1) + 1e-10, axis=0)
    o_z = oi_chg.sub(oi_chg.mean(axis=1), axis=0).div(oi_chg.std(axis=1) + 1e-10, axis=0)
    oi_div = p_z - o_z
    eq_h044, _ = xs_backtest(oi_div, return_df, n_long=5, n_short=5, rebal_days=10)
    if len(eq_h044) > 0:
        common = equity_new.index.intersection(eq_h044.index)
        if len(common) > 30:
            correlations['H-044 (OI-price div)'] = equity_new.loc[common].corr(eq_h044.loc[common])

    return correlations


def main():
    print("=" * 70)
    print("H-045 / H-046: OI-Volume & Price Acceleration Research")
    print("=" * 70)

    # Step 1: Load data
    print("\n[1] Loading data...")
    oi_panel = load_oi_panel()
    close_panel, vol_panel = load_price_volume_data()

    # Align
    oi_panel.index = oi_panel.index.tz_localize('UTC') if oi_panel.index.tz is None else oi_panel.index
    common_idx = oi_panel.index.intersection(close_panel.index).intersection(vol_panel.index)
    oi_panel = oi_panel.loc[common_idx]
    close_panel = close_panel.loc[common_idx]
    vol_panel = vol_panel.loc[common_idx]

    return_df = close_panel.pct_change().iloc[1:]
    oi_panel = oi_panel.loc[return_df.index]
    vol_panel = vol_panel.loc[return_df.index]
    close_panel_aligned = close_panel.loc[return_df.index]

    print(f"Data: {len(return_df)} days x {len(return_df.columns)} assets")
    print(f"Range: {return_df.index[0].date()} to {return_df.index[-1].date()}")

    # Step 2: Compute H-045 factors (OI-Volume combinations)
    print("\n[2] Computing H-045: OI-Volume factors...")
    oi_vol_factors = compute_oi_volume_factors(oi_panel, vol_panel, close_panel_aligned)
    print(f"  Created {len(oi_vol_factors)} OI-Volume factor variants")

    # Step 3: Compute H-046 factors (Price Acceleration)
    print("\n[3] Computing H-046: Price Acceleration factors...")
    accel_factors = compute_price_acceleration(close_panel_aligned)
    print(f"  Created {len(accel_factors)} Price Acceleration factor variants")

    # Step 4: Parameter sweep for H-045
    print("\n[4] H-045 Parameter sweep (OI-Volume factors)...")
    print("  Testing all factor variants x [n=3,4,5] x [rebal=3,5,10]...")
    h045_results = parameter_sweep(oi_vol_factors, return_df)

    if len(h045_results) > 0:
        positive = h045_results[h045_results['sharpe'] > 0]
        print(f"\n  H-045 Results: {len(positive)}/{len(h045_results)} positive Sharpe ({100*len(positive)/len(h045_results):.0f}%)")

        # Best by factor type
        print("\n  Best by factor type:")
        for ftype in h045_results['factor'].unique():
            subset = h045_results[h045_results['factor'] == ftype]
            best = subset.loc[subset['sharpe'].idxmax()]
            pos_pct = 100 * (subset['sharpe'] > 0).mean()
            print(f"    {ftype:25s}: Sharpe {best['sharpe']:+.2f}, ret {best['annual_return']*100:+.1f}%, "
                  f"DD {best['max_dd']*100:.1f}%, n={int(best['n'])}, r={int(best['rebal'])} "
                  f"| {pos_pct:.0f}% positive")

        # Top 10 overall
        print("\n  Top 10 param sets:")
        top10 = h045_results.nlargest(10, 'sharpe')
        for _, row in top10.iterrows():
            print(f"    {row['factor']:25s} n={int(row['n'])} r={int(row['rebal'])}: "
                  f"Sharpe {row['sharpe']:+.2f}, ret {row['annual_return']*100:+.1f}%, "
                  f"DD {row['max_dd']*100:.1f}%, WR {row['win_rate']*100:.0f}%")
    else:
        print("  No results generated!")
        return

    # Step 5: Parameter sweep for H-046
    print("\n\n[5] H-046 Parameter sweep (Price Acceleration)...")
    h046_results = parameter_sweep(accel_factors, return_df)

    if len(h046_results) > 0:
        positive = h046_results[h046_results['sharpe'] > 0]
        print(f"\n  H-046 Results: {len(positive)}/{len(h046_results)} positive Sharpe ({100*len(positive)/len(h046_results):.0f}%)")

        print("\n  Best by factor type:")
        for ftype in h046_results['factor'].unique():
            subset = h046_results[h046_results['factor'] == ftype]
            best = subset.loc[subset['sharpe'].idxmax()]
            pos_pct = 100 * (subset['sharpe'] > 0).mean()
            print(f"    {ftype:25s}: Sharpe {best['sharpe']:+.2f}, ret {best['annual_return']*100:+.1f}%, "
                  f"DD {best['max_dd']*100:.1f}%, n={int(best['n'])}, r={int(best['rebal'])} "
                  f"| {pos_pct:.0f}% positive")

        # Top 5
        print("\n  Top 5 param sets:")
        top5 = h046_results.nlargest(5, 'sharpe')
        for _, row in top5.iterrows():
            print(f"    {row['factor']:25s} n={int(row['n'])} r={int(row['rebal'])}: "
                  f"Sharpe {row['sharpe']:+.2f}, ret {row['annual_return']*100:+.1f}%, "
                  f"DD {row['max_dd']*100:.1f}%, WR {row['win_rate']*100:.0f}%")

    # Step 6: Walk-forward on best H-045 candidates (top 3 factor types with >60% positive)
    print("\n\n[6] Walk-forward validation on best H-045 candidates...")

    # Find factor types with highest % positive
    factor_scores = []
    for ftype in h045_results['factor'].unique():
        subset = h045_results[h045_results['factor'] == ftype]
        pos_pct = (subset['sharpe'] > 0).mean()
        best_sharpe = subset['sharpe'].max()
        factor_scores.append((ftype, pos_pct, best_sharpe))

    factor_scores.sort(key=lambda x: (-x[1], -x[2]))

    for ftype, pos_pct, best_sharpe in factor_scores[:4]:
        if pos_pct < 0.30:
            print(f"\n  Skipping {ftype} ({pos_pct*100:.0f}% positive — too weak)")
            continue

        print(f"\n  WF test: {ftype} (IS {pos_pct*100:.0f}% positive, best Sharpe {best_sharpe:.2f})")

        # Find best params for this factor
        subset = h045_results[h045_results['factor'] == ftype]
        best_row = subset.loc[subset['sharpe'].idxmax()]
        n = int(best_row['n'])
        r = int(best_row['rebal'])

        signal_df = oi_vol_factors[ftype]
        wf_results = walk_forward_test(signal_df, return_df, n_long=n, n_short=n,
                                        rebal_days=r, n_folds=5)

        if wf_results:
            wf_df = pd.DataFrame(wf_results)
            pos_folds = (wf_df['sharpe'] > 0).sum()
            mean_oos = wf_df['sharpe'].mean()
            print(f"    Params: n={n}, r={r}")
            print(f"    WF: {pos_folds}/{len(wf_df)} positive (mean OOS Sharpe {mean_oos:.2f})")
            for _, row in wf_df.iterrows():
                print(f"      Fold {int(row['fold'])}: {row['start']} to {row['end']} "
                      f"({int(row['days'])}d) Sharpe {row['sharpe']:+.2f}, "
                      f"ret {row['annual_return']*100:+.1f}%, DD {row['max_dd']*100:.1f}%")

            # Fee robustness (test at 5x fees = 20bps)
            _, metrics_5x = xs_backtest(signal_df, return_df, n, n, r, fee_bps=20)
            if metrics_5x:
                print(f"    Fee robustness (5x = 20bps): Sharpe {metrics_5x['sharpe']:.2f}")

    # Step 7: Walk-forward on best H-046 candidates
    if len(h046_results) > 0:
        print("\n\n[7] Walk-forward validation on best H-046 candidates...")

        factor_scores_046 = []
        for ftype in h046_results['factor'].unique():
            subset = h046_results[h046_results['factor'] == ftype]
            pos_pct = (subset['sharpe'] > 0).mean()
            best_sharpe = subset['sharpe'].max()
            factor_scores_046.append((ftype, pos_pct, best_sharpe))

        factor_scores_046.sort(key=lambda x: (-x[1], -x[2]))

        for ftype, pos_pct, best_sharpe in factor_scores_046[:3]:
            if pos_pct < 0.40:
                print(f"\n  Skipping {ftype} ({pos_pct*100:.0f}% positive — too weak)")
                continue

            print(f"\n  WF test: {ftype} (IS {pos_pct*100:.0f}% positive, best Sharpe {best_sharpe:.2f})")

            subset = h046_results[h046_results['factor'] == ftype]
            best_row = subset.loc[subset['sharpe'].idxmax()]
            n = int(best_row['n'])
            r = int(best_row['rebal'])

            signal_df = accel_factors[ftype]
            wf_results = walk_forward_test(signal_df, return_df, n_long=n, n_short=n,
                                            rebal_days=r, n_folds=5)

            if wf_results:
                wf_df = pd.DataFrame(wf_results)
                pos_folds = (wf_df['sharpe'] > 0).sum()
                mean_oos = wf_df['sharpe'].mean()
                print(f"    Params: n={n}, r={r}")
                print(f"    WF: {pos_folds}/{len(wf_df)} positive (mean OOS Sharpe {mean_oos:.2f})")
                for _, row in wf_df.iterrows():
                    print(f"      Fold {int(row['fold'])}: {row['start']} to {row['end']} "
                          f"({int(row['days'])}d) Sharpe {row['sharpe']:+.2f}, "
                          f"ret {row['annual_return']*100:+.1f}%, DD {row['max_dd']*100:.1f}%")

    # Step 8: Correlation analysis for best H-045 candidate
    print("\n\n[8] Correlation with existing strategies...")

    # Find the best overall H-045 candidate (highest IS Sharpe with >60% positive)
    best_factor = None
    best_sharpe = -999
    for ftype, pos_pct, bs in factor_scores:
        if pos_pct >= 0.50 and bs > best_sharpe:
            best_factor = ftype
            best_sharpe = bs

    if best_factor:
        subset = h045_results[h045_results['factor'] == best_factor]
        best_row = subset.loc[subset['sharpe'].idxmax()]
        n = int(best_row['n'])
        r = int(best_row['rebal'])

        print(f"\n  Best H-045 candidate: {best_factor} (n={n}, r={r}, IS Sharpe {best_sharpe:.2f})")

        signal_df = oi_vol_factors[best_factor]
        equity_best, _ = xs_backtest(signal_df, return_df, n, n, r)

        correlations = compute_correlation_with_existing(equity_best, close_panel_aligned, oi_panel, return_df)
        print("  Correlations with existing strategies:")
        for name, corr in correlations.items():
            print(f"    {name}: {corr:.3f}")
    else:
        print("  No viable H-045 candidate found for correlation analysis.")

    print("\n" + "=" * 70)
    print("RESEARCH COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
