"""
H-043: Open Interest Changes as Cross-Sectional Factor
H-044: OI-Price Divergence / Confirmation Signal

Research:
- Fetch daily OI data for 14 assets from Bybit
- Compute OI change factors (1d, 5d, 10d, 20d)
- Test as cross-sectional factor: long high OI change vs short low OI change (and vice versa)
- Test OI-Price confirmation/divergence as signal
- Walk-forward validation
"""

import numpy as np
import pandas as pd
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return

import ccxt

ASSETS = ['BTC', 'ETH', 'SOL', 'SUI', 'XRP', 'DOGE', 'AVAX', 'LINK', 'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM']
OI_CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'oi')

def fetch_oi_history(symbol='BTCUSDT', interval='1d', limit=500):
    """Fetch historical open interest from Bybit V5 API."""
    exchange = ccxt.bybit()
    all_data = []
    cursor = None

    for _ in range(20):  # max 20 pages
        params = {
            'category': 'linear',
            'symbol': symbol,
            'intervalTime': interval,
            'limit': str(limit),
        }
        if cursor:
            params['cursor'] = cursor

        try:
            resp = exchange.publicGetV5MarketOpenInterest(params)
            data = resp['result']['list']
            if not data:
                break
            all_data.extend(data)

            cursor = resp['result'].get('nextPageCursor', '')
            if not cursor:
                break
            time.sleep(0.3)  # rate limit
        except Exception as e:
            print(f"  Error fetching {symbol}: {e}")
            break

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
    df['openInterest'] = df['openInterest'].astype(float)
    df = df.sort_values('timestamp').drop_duplicates('timestamp').reset_index(drop=True)
    df = df.set_index('timestamp')
    return df[['openInterest']]


def fetch_all_oi(assets=ASSETS, interval='1d'):
    """Fetch OI for all assets, with caching."""
    os.makedirs(OI_CACHE_DIR, exist_ok=True)

    oi_dict = {}
    for asset in assets:
        symbol = f"{asset}USDT"
        cache_file = os.path.join(OI_CACHE_DIR, f"{asset}_oi_{interval}.parquet")

        if os.path.exists(cache_file):
            df = pd.read_parquet(cache_file)
            print(f"  {asset}: loaded {len(df)} cached OI bars")
        else:
            print(f"  {asset}: fetching OI from Bybit...")
            df = fetch_oi_history(symbol, interval)
            if len(df) > 0:
                df.to_parquet(cache_file)
                print(f"  {asset}: fetched {len(df)} OI bars ({df.index[0]} to {df.index[-1]})")
            else:
                print(f"  {asset}: NO OI data available!")
                continue

        oi_dict[asset] = df['openInterest']
        time.sleep(0.2)

    # Combine into single DataFrame
    oi_panel = pd.DataFrame(oi_dict)
    oi_panel = oi_panel.sort_index().dropna(how='all')
    return oi_panel


def compute_oi_factors(oi_panel, windows=[1, 3, 5, 10, 20]):
    """Compute OI change factors at various windows."""
    factors = {}
    for w in windows:
        # Percentage change in OI
        oi_pct = oi_panel.pct_change(w)
        factors[f'OI_CHG_{w}d'] = oi_pct
    return factors


def compute_oi_price_divergence(oi_panel, close_panel, windows=[5, 10, 20]):
    """
    Compute OI-Price divergence factor.
    Positive divergence: price up + OI down (weak rally, potential reversal)
    Negative divergence: price down + OI up (potential squeeze)

    Signal: rank(price_change) - rank(oi_change)
    """
    factors = {}
    for w in windows:
        price_chg = close_panel.pct_change(w)
        oi_chg = oi_panel.pct_change(w)

        # Price-OI divergence: standardized price return minus standardized OI change
        # High value = price up, OI down (bearish divergence — weak rally)
        # Low value = price down, OI up (bullish divergence — squeeze setup)
        price_z = price_chg.sub(price_chg.mean(axis=1), axis=0).div(price_chg.std(axis=1) + 1e-10, axis=0)
        oi_z = oi_chg.sub(oi_chg.mean(axis=1), axis=0).div(oi_chg.std(axis=1) + 1e-10, axis=0)

        divergence = price_z - oi_z
        factors[f'OI_DIV_{w}d'] = divergence

        # Also test: OI confirmation (price and OI moving together)
        confirmation = price_z + oi_z
        factors[f'OI_CONF_{w}d'] = confirmation

    return factors


def xs_backtest(signal_df, return_df, n_long=4, n_short=4, rebal_days=5,
                start_date=None, end_date=None, fee_bps=4):
    """
    Cross-sectional backtest: long top-N signal, short bottom-N signal.
    Rebalance every rebal_days.
    """
    if start_date:
        signal_df = signal_df.loc[start_date:]
        return_df = return_df.loc[start_date:]
    if end_date:
        signal_df = signal_df.loc[:end_date]
        return_df = return_df.loc[:end_date]

    # Align dates
    common_dates = signal_df.index.intersection(return_df.index)
    signal_df = signal_df.loc[common_dates]
    return_df = return_df.loc[common_dates]

    # Drop rows with too few assets
    min_assets = n_long + n_short
    valid = signal_df.notna().sum(axis=1) >= min_assets
    signal_df = signal_df[valid]
    return_df = return_df[valid]

    if len(signal_df) < 30:
        return pd.Series(dtype=float), {}

    daily_returns = []
    prev_longs = set()
    prev_shorts = set()

    for i, date in enumerate(signal_df.index):
        if i % rebal_days == 0:
            # Rank assets by signal
            sig = signal_df.loc[date].dropna()
            if len(sig) < min_assets:
                daily_returns.append(0.0)
                continue

            ranked = sig.sort_values(ascending=False)
            new_longs = set(ranked.index[:n_long])
            new_shorts = set(ranked.index[-n_short:])

            # Fee for turnover
            turnover = len(new_longs - prev_longs) + len(new_shorts - prev_shorts)
            fee = turnover * fee_bps / 10000 * 2 / (n_long + n_short)  # proportional

            prev_longs = new_longs
            prev_shorts = new_shorts
        else:
            fee = 0.0

        # Daily return: equal weight long/short
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
        'sharpe': sharpe_ratio(equity),
        'annual_return': annual_return(equity),
        'max_dd': max_drawdown(cum),
        'win_rate': (equity > 0).mean(),
        'n_days': len(equity),
    }
    return equity, metrics


def walk_forward_test(signal_df, return_df, n_long=4, n_short=4, rebal_days=5,
                      n_folds=6, fee_bps=4):
    """Walk-forward test with expanding window."""
    dates = signal_df.index
    total_days = len(dates)
    fold_size = total_days // (n_folds + 1)  # Reserve 1 fold for initial training

    results = []
    for fold in range(n_folds):
        train_end_idx = fold_size * (fold + 2) - 1  # Expanding train window
        test_start_idx = train_end_idx + 1
        test_end_idx = min(test_start_idx + fold_size - 1, total_days - 1)

        if test_end_idx <= test_start_idx + 10:
            break

        test_start = dates[test_start_idx]
        test_end = dates[test_end_idx]

        # We use the same signal (no optimization within folds for rank-based factors)
        # Just test OOS performance in each fold
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


def main():
    print("=" * 70)
    print("H-043 / H-044: Open Interest Factor Research")
    print("=" * 70)

    # Step 1: Fetch OI data
    print("\n[1] Fetching OI data for 14 assets...")
    oi_panel = fetch_all_oi(ASSETS, '1d')
    print(f"\nOI panel: {oi_panel.shape[0]} days x {oi_panel.shape[1]} assets")
    print(f"Date range: {oi_panel.index[0]} to {oi_panel.index[-1]}")
    print(f"Assets with data: {list(oi_panel.columns)}")

    # Step 2: Load price data
    print("\n[2] Loading price data...")
    close_dict = {}
    for asset in ASSETS:
        try:
            df = fetch_and_cache(f"{asset}/USDT", '1h')
            daily = df['close'].resample('1D').last().dropna()
            close_dict[asset] = daily
        except Exception as e:
            print(f"  {asset}: {e}")

    close_panel = pd.DataFrame(close_dict)

    # Align OI and price data (fix timezone mismatch)
    oi_panel.index = oi_panel.index.tz_localize('UTC') if oi_panel.index.tz is None else oi_panel.index
    common_idx = oi_panel.index.intersection(close_panel.index)
    oi_panel = oi_panel.loc[common_idx]
    close_panel = close_panel.loc[common_idx]

    # Daily returns
    return_df = close_panel.pct_change().iloc[1:]
    oi_panel = oi_panel.loc[return_df.index]

    print(f"Aligned data: {len(return_df)} days, {len(return_df.columns)} assets")
    print(f"Date range: {return_df.index[0]} to {return_df.index[-1]}")

    # Step 3: Compute OI factors
    print("\n[3] Computing OI change factors...")
    oi_factors = compute_oi_factors(oi_panel, windows=[1, 3, 5, 10, 20])

    # Also test inverted signal (short high OI change = contrarian)
    oi_factors_inv = {}
    for name, sig in oi_factors.items():
        oi_factors_inv[f'{name}_INV'] = -sig  # Inverted: short high OI change

    all_oi_factors = {**oi_factors, **oi_factors_inv}
    print(f"Total OI change factors: {len(all_oi_factors)}")

    # Step 4: Parameter sweep for H-043 (OI change)
    print("\n[4] H-043: OI Change Factor — Parameter Sweep")
    # Lag signals by 1 day to avoid look-ahead
    lagged_factors = {}
    for name, sig in all_oi_factors.items():
        lagged_factors[name] = sig.shift(1)

    sweep_results = parameter_sweep(lagged_factors, return_df,
                                     n_values=[3, 4, 5], rebal_values=[3, 5, 10])

    if len(sweep_results) > 0:
        print(f"\nTotal param sets tested: {len(sweep_results)}")
        positive = (sweep_results['sharpe'] > 0).sum()
        print(f"Positive Sharpe: {positive}/{len(sweep_results)} ({100*positive/len(sweep_results):.1f}%)")

        print("\nTop 10 by Sharpe:")
        top10 = sweep_results.nlargest(10, 'sharpe')
        for _, row in top10.iterrows():
            print(f"  {row['factor']:20s} n={row['n']:.0f} r={row['rebal']:.0f} | "
                  f"Sharpe {row['sharpe']:+.2f}, ret {row['annual_return']*100:+.1f}%, "
                  f"DD {row['max_dd']*100:.1f}%, WR {row['win_rate']*100:.1f}%")

        print("\nBottom 5 by Sharpe:")
        bot5 = sweep_results.nsmallest(5, 'sharpe')
        for _, row in bot5.iterrows():
            print(f"  {row['factor']:20s} n={row['n']:.0f} r={row['rebal']:.0f} | "
                  f"Sharpe {row['sharpe']:+.2f}, ret {row['annual_return']*100:+.1f}%, "
                  f"DD {row['max_dd']*100:.1f}%")
    else:
        print("No valid results!")

    # Step 5: OI-Price divergence factors (H-044)
    print("\n" + "=" * 70)
    print("[5] H-044: OI-Price Divergence/Confirmation — Parameter Sweep")
    div_factors = compute_oi_price_divergence(oi_panel, close_panel, windows=[3, 5, 10, 20])

    # Also invert
    div_factors_all = {}
    for name, sig in div_factors.items():
        div_factors_all[name] = sig.shift(1)
        div_factors_all[f'{name}_INV'] = -sig.shift(1)

    sweep_div = parameter_sweep(div_factors_all, return_df,
                                 n_values=[3, 4, 5], rebal_values=[3, 5, 10])

    if len(sweep_div) > 0:
        print(f"\nTotal param sets tested: {len(sweep_div)}")
        positive = (sweep_div['sharpe'] > 0).sum()
        print(f"Positive Sharpe: {positive}/{len(sweep_div)} ({100*positive/len(sweep_div):.1f}%)")

        print("\nTop 10 by Sharpe:")
        top10 = sweep_div.nlargest(10, 'sharpe')
        for _, row in top10.iterrows():
            print(f"  {row['factor']:20s} n={row['n']:.0f} r={row['rebal']:.0f} | "
                  f"Sharpe {row['sharpe']:+.2f}, ret {row['annual_return']*100:+.1f}%, "
                  f"DD {row['max_dd']*100:.1f}%, WR {row['win_rate']*100:.1f}%")
    else:
        print("No valid results!")

    # Step 6: Walk-forward on best H-043 factor
    print("\n" + "=" * 70)
    print("[6] Walk-Forward Validation on Best H-043 Factor")

    if len(sweep_results) > 0:
        best = sweep_results.nlargest(1, 'sharpe').iloc[0]
        best_factor = best['factor']
        best_n = int(best['n'])
        best_r = int(best['rebal'])

        print(f"Best factor: {best_factor}, n={best_n}, rebal={best_r}")
        print(f"IS Sharpe: {best['sharpe']:.2f}, Return: {best['annual_return']*100:.1f}%")

        wf_results = walk_forward_test(
            lagged_factors[best_factor], return_df,
            n_long=best_n, n_short=best_n, rebal_days=best_r,
            n_folds=6, fee_bps=4
        )

        if wf_results:
            print(f"\nWalk-Forward Results ({len(wf_results)} folds):")
            positive_folds = 0
            sharpes = []
            for fold in wf_results:
                status = "+" if fold['sharpe'] > 0 else "-"
                print(f"  Fold {fold['fold']}: {fold['start']} to {fold['end']} "
                      f"({fold['days']}d) | Sharpe {fold['sharpe']:+.2f}, "
                      f"ret {fold['annual_return']*100:+.1f}%, DD {fold['max_dd']*100:.1f}% [{status}]")
                if fold['sharpe'] > 0:
                    positive_folds += 1
                sharpes.append(fold['sharpe'])

            print(f"\nWF Summary: {positive_folds}/{len(wf_results)} positive, "
                  f"mean OOS Sharpe {np.mean(sharpes):.2f}")

    # Step 7: Walk-forward on best H-044 factor
    print("\n" + "=" * 70)
    print("[7] Walk-Forward Validation on Best H-044 Factor")

    if len(sweep_div) > 0:
        best_div = sweep_div.nlargest(1, 'sharpe').iloc[0]
        best_factor_div = best_div['factor']
        best_n_div = int(best_div['n'])
        best_r_div = int(best_div['rebal'])

        print(f"Best factor: {best_factor_div}, n={best_n_div}, rebal={best_r_div}")
        print(f"IS Sharpe: {best_div['sharpe']:.2f}, Return: {best_div['annual_return']*100:.1f}%")

        wf_div = walk_forward_test(
            div_factors_all[best_factor_div], return_df,
            n_long=best_n_div, n_short=best_n_div, rebal_days=best_r_div,
            n_folds=6, fee_bps=4
        )

        if wf_div:
            print(f"\nWalk-Forward Results ({len(wf_div)} folds):")
            positive_folds = 0
            sharpes = []
            for fold in wf_div:
                status = "+" if fold['sharpe'] > 0 else "-"
                print(f"  Fold {fold['fold']}: {fold['start']} to {fold['end']} "
                      f"({fold['days']}d) | Sharpe {fold['sharpe']:+.2f}, "
                      f"ret {fold['annual_return']*100:+.1f}%, DD {fold['max_dd']*100:.1f}% [{status}]")
                if fold['sharpe'] > 0:
                    positive_folds += 1
                sharpes.append(fold['sharpe'])

            print(f"\nWF Summary: {positive_folds}/{len(wf_div)} positive, "
                  f"mean OOS Sharpe {np.mean(sharpes):.2f}")

    # Step 8: Correlation with existing strategies
    print("\n" + "=" * 70)
    print("[8] Correlation Analysis with Existing Strategies")

    if len(sweep_results) > 0:
        best = sweep_results.nlargest(1, 'sharpe').iloc[0]
        best_equity, _ = xs_backtest(
            lagged_factors[best['factor']], return_df,
            n_long=int(best['n']), n_short=int(best['n']),
            rebal_days=int(best['rebal']), fee_bps=4
        )

        # Load H-012 momentum returns for comparison
        # Build momentum factor for correlation check
        mom_60d = close_panel.pct_change(60).shift(1)
        mom_equity, _ = xs_backtest(mom_60d, return_df, n_long=4, n_short=4, rebal_days=5, fee_bps=4)

        # Volume momentum
        vol_panel = {}
        for asset in ASSETS:
            try:
                df = fetch_and_cache(f"{asset}/USDT", '1h')
                daily_vol = df['volume'].resample('1D').sum().dropna()
                vol_panel[asset] = daily_vol
            except:
                pass
        vol_df = pd.DataFrame(vol_panel).loc[return_df.index]
        vs5 = vol_df.rolling(5).mean()
        vl20 = vol_df.rolling(20).mean()
        vol_mom_sig = (vs5 / vl20).shift(1)
        volmom_equity, _ = xs_backtest(vol_mom_sig, return_df, n_long=4, n_short=4, rebal_days=3, fee_bps=4)

        # Align and compute correlations
        common = best_equity.index.intersection(mom_equity.index).intersection(volmom_equity.index)
        if len(common) > 30:
            corr_mom = best_equity.loc[common].corr(mom_equity.loc[common])
            corr_vol = best_equity.loc[common].corr(volmom_equity.loc[common])
            print(f"  OI factor vs H-012 (momentum): {corr_mom:.3f}")
            print(f"  OI factor vs H-021 (vol mom):   {corr_vol:.3f}")

    # Step 9: Fee robustness
    print("\n" + "=" * 70)
    print("[9] Fee Robustness Test (best H-043)")

    if len(sweep_results) > 0:
        best = sweep_results.nlargest(1, 'sharpe').iloc[0]
        for fee_mult in [1, 2, 3, 5]:
            fee = 4 * fee_mult
            _, metrics = xs_backtest(
                lagged_factors[best['factor']], return_df,
                n_long=int(best['n']), n_short=int(best['n']),
                rebal_days=int(best['rebal']), fee_bps=fee
            )
            if metrics:
                print(f"  Fee {fee}bps ({fee_mult}x): Sharpe {metrics['sharpe']:+.2f}, "
                      f"ret {metrics['annual_return']*100:+.1f}%")

    # Step 10: Full-period IS results for all OI factors
    print("\n" + "=" * 70)
    print("[10] Summary: IS results by factor type")

    if len(sweep_results) > 0:
        for factor in sweep_results['factor'].unique():
            subset = sweep_results[sweep_results['factor'] == factor]
            pos = (subset['sharpe'] > 0).sum()
            best_s = subset['sharpe'].max()
            mean_s = subset['sharpe'].mean()
            print(f"  {factor:20s}: {pos}/{len(subset)} positive ({100*pos/len(subset):.0f}%), "
                  f"best {best_s:+.2f}, mean {mean_s:+.2f}")

    if len(sweep_div) > 0:
        print()
        for factor in sweep_div['factor'].unique():
            subset = sweep_div[sweep_div['factor'] == factor]
            pos = (subset['sharpe'] > 0).sum()
            best_s = subset['sharpe'].max()
            mean_s = subset['sharpe'].mean()
            print(f"  {factor:20s}: {pos}/{len(subset)} positive ({100*pos/len(subset):.0f}%), "
                  f"best {best_s:+.2f}, mean {mean_s:+.2f}")

    print("\n" + "=" * 70)
    print("RESEARCH COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
