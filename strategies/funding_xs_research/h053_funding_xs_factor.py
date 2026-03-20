"""
H-053: Funding Rate Cross-Sectional Factor

Hypothesis: Rank 14 crypto assets by their rolling average funding rate.
Test both directions:
- "long_high": Long highest funding (momentum/carry) - assets with bullish sentiment continue
- "long_low": Long lowest funding (contrarian) - crowded longs reverse

This is mechanically related to H-052 (premium index) since funding ≈ f(premium).
We explicitly check correlation with H-052 to assess redundancy.

Data: 8-hourly funding rates from Bybit, aggregated to daily avg, 2yr history.
"""

import numpy as np
import pandas as pd
import sys, os
from itertools import product
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = ['BTC', 'ETH', 'SOL', 'SUI', 'XRP', 'DOGE', 'AVAX', 'LINK', 'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM']
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')


def load_daily_closes():
    """Load daily closes for all 14 assets."""
    closes = {}
    for asset in ASSETS:
        df = fetch_and_cache(f"{asset}/USDT", '1d')
        closes[asset] = df['close']
    panel = pd.DataFrame(closes)
    panel = panel.sort_index().dropna(how='all')
    return panel


def load_funding_rates():
    """Load 8h funding rates and aggregate to daily average."""
    funding = {}
    for asset in ASSETS:
        fpath = os.path.join(DATA_DIR, f"{asset}_USDT_USDT_funding.parquet")
        if not os.path.exists(fpath):
            print(f"  WARNING: no funding data for {asset}")
            continue
        df = pd.read_parquet(fpath)
        # Aggregate 8h rates to daily average
        daily = df['funding_rate'].resample('1D').mean()
        funding[asset] = daily

    panel = pd.DataFrame(funding)
    panel = panel.sort_index().dropna(how='all')
    print(f"Funding data: {len(panel)} days, {len(panel.columns)} assets")
    print(f"Date range: {panel.index[0]} to {panel.index[-1]}")
    return panel


def compute_rolling_funding(funding_panel, window):
    """Compute rolling average funding rate."""
    return funding_panel.rolling(window, min_periods=max(1, window//2)).mean()


def backtest_xs_factor(closes, signals, rebal_days, n_long_short, direction="long_high",
                       fee_bps=5):
    """
    Backtest cross-sectional factor.
    direction: "long_high" = long highest signal, short lowest
               "long_low" = long lowest signal, short highest
    fee_bps: one-way fee in basis points (applied on rebalance)
    Returns daily portfolio returns series.
    """
    returns = closes.pct_change()
    assets = [a for a in signals.columns if a in returns.columns]
    asset_returns = returns[assets]

    common_idx = signals.dropna(how='all').index.intersection(asset_returns.dropna(how='all').index)
    signals = signals.loc[common_idx]
    asset_returns = asset_returns.loc[common_idx]

    portfolio_returns = pd.Series(0.0, index=common_idx)
    current_longs = []
    current_shorts = []
    last_rebal = None

    for i, date in enumerate(common_idx):
        if i == 0:
            continue

        prev_date = common_idx[i-1]
        sig = signals.loc[prev_date].dropna()

        if len(sig) < 2 * n_long_short:
            continue

        days_since = (date - last_rebal).days if last_rebal else rebal_days + 1

        if days_since >= rebal_days:
            ranked = sig.sort_values()
            if direction == "long_low":
                new_longs = ranked.index[:n_long_short].tolist()
                new_shorts = ranked.index[-n_long_short:].tolist()
            else:  # long_high
                new_longs = ranked.index[-n_long_short:].tolist()
                new_shorts = ranked.index[:n_long_short].tolist()

            # Count turnover for fee calculation
            if current_longs or current_shorts:
                old_set = set(current_longs + current_shorts)
                new_set = set(new_longs + new_shorts)
                turnover = len(old_set.symmetric_difference(new_set))
                fee_cost = turnover * (1.0 / (2 * n_long_short)) * fee_bps * 2 / 10000
            else:
                fee_cost = 2 * fee_bps / 10000  # initial entry

            current_longs = new_longs
            current_shorts = new_shorts
            last_rebal = date
            portfolio_returns.loc[date] -= fee_cost

        if current_longs and current_shorts:
            w = 1.0 / (2 * n_long_short)
            day_ret = 0.0
            for a in current_longs:
                if a in asset_returns.columns:
                    day_ret += w * asset_returns.loc[date, a]
            for a in current_shorts:
                if a in asset_returns.columns:
                    day_ret -= w * asset_returns.loc[date, a]
            portfolio_returns.loc[date] += day_ret

    return portfolio_returns


def walk_forward_test(closes, signals, rebal_days, n_long_short, direction,
                      n_folds=6, test_days=90, fee_bps=5):
    """Rolling walk-forward with n_folds x test_days OOS."""
    returns = closes.pct_change()
    assets = [a for a in signals.columns if a in returns.columns]
    common_idx = signals.dropna(how='all').index.intersection(returns[assets].dropna(how='all').index)

    total_days = len(common_idx)
    total_test = n_folds * test_days
    train_size = total_days - total_test

    if train_size < 90:
        return []

    fold_results = []
    for fold in range(n_folds):
        test_start_idx = train_size + fold * test_days
        test_end_idx = min(test_start_idx + test_days, total_days)

        if test_end_idx <= test_start_idx:
            break

        test_dates = common_idx[test_start_idx:test_end_idx]
        test_start = test_dates[0]
        test_end = test_dates[-1]

        # Run backtest on test period only
        test_closes = closes.loc[test_start:test_end]
        test_signals = signals.loc[:test_end]  # use all history for signal computation

        rets = backtest_xs_factor(test_closes, test_signals, rebal_days, n_long_short,
                                   direction, fee_bps)
        rets = rets[rets.index >= test_start]

        if len(rets) > 10:
            sr = sharpe_ratio(rets)
            fold_results.append(sr)

    return fold_results


def main():
    print("=" * 70)
    print("H-053: Funding Rate Cross-Sectional Factor Research")
    print("=" * 70)

    # Load data
    closes = load_daily_closes()
    funding = load_funding_rates()

    # Align dates
    common_dates = closes.index.intersection(funding.index)
    closes = closes.loc[common_dates]
    funding = funding.loc[common_dates]
    print(f"\nAligned: {len(common_dates)} days, {len(ASSETS)} assets")

    # Summary statistics
    print(f"\nFunding rate summary (daily avg, annualized %):")
    ann = funding.mean() * 3 * 365 * 100  # 3 settlements/day * 365 days
    for asset in ASSETS:
        if asset in ann.index:
            print(f"  {asset:>5}: {ann[asset]:+.2f}%")

    # Cross-sectional dispersion check
    print(f"\nCross-sectional std of daily funding: {funding.std(axis=1).mean():.6f}")
    print(f"Cross-sectional mean correlation: {funding.corr().values[np.triu_indices(14, 1)].mean():.3f}")

    # Parameter grid
    windows = [3, 5, 7, 14, 27]  # rolling avg window in days
    rebal_list = [3, 5, 10]
    n_list = [3, 4, 5]
    directions = ["long_high", "long_low"]

    results = []
    total = len(windows) * len(rebal_list) * len(n_list) * len(directions)
    print(f"\nTesting {total} parameter combinations...")

    for i, (w, rd, n, direction) in enumerate(product(windows, rebal_list, n_list, directions)):
        signal = compute_rolling_funding(funding, w)
        rets = backtest_xs_factor(closes, signal, rd, n, direction)

        if len(rets) < 30:
            continue

        sr = sharpe_ratio(rets)
        ar = annual_return(rets) * 100
        dd = max_drawdown(rets) * 100

        results.append({
            'window': w, 'rebal': rd, 'n': n, 'direction': direction,
            'sharpe': sr, 'annual_ret': ar, 'max_dd': dd,
            'days': len(rets)
        })

    df = pd.DataFrame(results)

    # Summary
    print(f"\n{'='*70}")
    print(f"RESULTS: {len(df)} parameter combinations tested")
    print(f"{'='*70}")

    n_positive = (df['sharpe'] > 0).sum()
    pct_positive = n_positive / len(df) * 100
    print(f"\nPositive Sharpe: {n_positive}/{len(df)} ({pct_positive:.0f}%)")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"Median Sharpe: {df['sharpe'].median():.3f}")

    # By direction
    for d in directions:
        sub = df[df['direction'] == d]
        n_pos = (sub['sharpe'] > 0).sum()
        print(f"\n  {d}: {n_pos}/{len(sub)} positive ({n_pos/len(sub)*100:.0f}%), mean Sharpe {sub['sharpe'].mean():.3f}")

    # Top 10
    print(f"\nTop 10 by Sharpe:")
    top = df.nlargest(10, 'sharpe')
    for _, r in top.iterrows():
        print(f"  W{r['window']:>2} R{r['rebal']:>2} N{r['n']} {r['direction']:>10}: "
              f"Sharpe {r['sharpe']:.3f}, {r['annual_ret']:+.1f}%, DD {r['max_dd']:.1f}%")

    # If > 50% positive, do walk-forward validation on best params
    if pct_positive > 50:
        print(f"\n{'='*70}")
        print(f"WALK-FORWARD VALIDATION (>50% positive)")
        print(f"{'='*70}")

        # Test top params from each direction
        for direction in directions:
            sub = df[df['direction'] == direction].nlargest(5, 'sharpe')
            for _, r in sub.iterrows():
                signal = compute_rolling_funding(funding, int(r['window']))
                wf = walk_forward_test(closes, signal, int(r['rebal']), int(r['n']),
                                       r['direction'])
                if wf:
                    n_pos = sum(1 for s in wf if s > 0)
                    print(f"  W{int(r['window']):>2} R{int(r['rebal']):>2} N{int(r['n'])} {r['direction']:>10}: "
                          f"WF {n_pos}/{len(wf)} positive, mean OOS {np.mean(wf):.2f} "
                          f"(IS {r['sharpe']:.2f})")

        # Fee sensitivity on best
        best = df.nlargest(1, 'sharpe').iloc[0]
        print(f"\nFee sensitivity (best: W{int(best['window'])} R{int(best['rebal'])} N{int(best['n'])} {best['direction']}):")
        for fee_mult in [1, 2, 5]:
            signal = compute_rolling_funding(funding, int(best['window']))
            rets = backtest_xs_factor(closes, signal, int(best['rebal']),
                                      int(best['n']), best['direction'],
                                      fee_bps=5*fee_mult)
            sr = sharpe_ratio(rets)
            print(f"  {fee_mult}x fees ({5*fee_mult}bps): Sharpe {sr:.3f}")

    # Correlation with existing strategies
    print(f"\n{'='*70}")
    print(f"CORRELATION WITH EXISTING STRATEGIES")
    print(f"{'='*70}")

    if pct_positive > 30:
        best = df.nlargest(1, 'sharpe').iloc[0]
        signal = compute_rolling_funding(funding, int(best['window']))
        best_rets = backtest_xs_factor(closes, signal, int(best['rebal']),
                                        int(best['n']), best['direction'])

        # Compare with H-012 (XSMom), H-021 (VolMom), H-046 (Acceleration), H-049 (LSR), H-052 (Premium)
        # Simulate H-012 (60d momentum, 5d rebal, top/bottom 4)
        mom60 = closes.pct_change(60)
        h012_rets = backtest_xs_factor(closes, mom60, 5, 4, "long_high", fee_bps=5)

        # H-021 (5d/20d volume ratio) - need volume data, skip if not available
        # H-046 (price acceleration - 20d change in 20d momentum)
        mom20 = closes.pct_change(20)
        accel = mom20.diff(20)
        h046_rets = backtest_xs_factor(closes, accel, 3, 4, "long_high", fee_bps=5)

        # H-052 (premium index) - need premium data
        premium_file = os.path.join(DATA_DIR, 'all_assets_premium_daily.parquet')
        h052_rets = None
        if os.path.exists(premium_file):
            prem = pd.read_parquet(premium_file)
            prem_signal = prem.rolling(5, min_periods=3).mean()
            h052_rets = backtest_xs_factor(closes, prem_signal, 5, 4, "long_low", fee_bps=5)

        # H-049 (LSR contrarian) - need LSR data
        lsr_file = os.path.join(DATA_DIR, 'all_assets_lsr_daily.parquet')
        h049_rets = None
        if os.path.exists(lsr_file):
            lsr = pd.read_parquet(lsr_file)
            h049_rets = backtest_xs_factor(closes, lsr, 5, 3, "long_low", fee_bps=5)

        # Compute correlations
        common = best_rets.index
        pairs = [('H-012 XSMom', h012_rets), ('H-046 Accel', h046_rets)]
        if h052_rets is not None:
            pairs.append(('H-052 Premium', h052_rets))
        if h049_rets is not None:
            pairs.append(('H-049 LSR', h049_rets))

        for name, other_rets in pairs:
            common2 = common.intersection(other_rets.index)
            if len(common2) > 30:
                corr = best_rets.loc[common2].corr(other_rets.loc[common2])
                print(f"  H-053 vs {name}: {corr:.3f}")

    # Final verdict
    print(f"\n{'='*70}")
    print(f"VERDICT")
    print(f"{'='*70}")
    if pct_positive < 50:
        print(f"REJECTED: Only {pct_positive:.0f}% positive = noise")
    elif pct_positive >= 50:
        print(f"Potentially viable: {pct_positive:.0f}% positive")
        print(f"Check WF results and correlations above for final decision")


if __name__ == '__main__':
    main()
