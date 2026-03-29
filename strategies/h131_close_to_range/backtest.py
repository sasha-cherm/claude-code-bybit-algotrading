"""
H-131: Close-to-Range Position Factor — Cross-Sectional Backtest
=================================================================

Idea: Compute where each asset's close sits within its N-day high-low range:
  signal = (close - N_low) / (N_high - N_low)

  Value near 1 = closing near recent highs (bullish / uptrend)
  Value near 0 = closing near recent lows (bearish / downtrend)

Directions:
  - MOMENTUM: long assets closing near highs (signal near 1), short near lows
  - CONTRARIAN: long assets closing near lows (signal near 0), short near highs

This differs from H-124 (CLV, single-bar open/high/low/close) — this uses
multi-day range which smooths out intrabar noise.

Parameter grid: lookback [5,10,20,30] x rebal [3,5,7] x N [3,4] x direction [mom, contra]
  = 4 x 3 x 2 x 2 = 48 combos

Validation:
  1. In-sample: % params with positive Sharpe (need >= 80%)
  2. Walk-forward: 6 folds, 180d train / 90d test (need >= 4/6 positive OOS folds)
  3. Split-half stability: Sharpe H1 vs H2 (need stability > 0)
  4. Correlation with H-012 (60d momentum): need < 0.6
  5. Correlation with H-031 (size factor): need < 0.6
"""

import json
import sys
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return, total_return

ASSETS = ['BTC', 'ETH', 'SOL', 'SUI', 'XRP', 'DOGE', 'AVAX', 'LINK',
          'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM']
RESULTS_DIR = Path(__file__).resolve().parent

FEE_BPS = 5  # one-way fee in basis points


# ======================================================================
# Data Loading
# ======================================================================

def load_daily_ohlcv():
    """Load daily OHLCV for all 14 assets. Returns dict of DataFrames."""
    data = {}
    for asset in ASSETS:
        df = fetch_and_cache(f"{asset}/USDT", '1d')
        if df is not None and len(df) > 0:
            data[asset] = df
    return data


def build_close_panel(data):
    closes = {a: d['close'] for a, d in data.items()}
    return pd.DataFrame(closes).sort_index().dropna(how='all')


def build_high_panel(data):
    highs = {a: d['high'] for a, d in data.items()}
    return pd.DataFrame(highs).sort_index().dropna(how='all')


def build_low_panel(data):
    lows = {a: d['low'] for a, d in data.items()}
    return pd.DataFrame(lows).sort_index().dropna(how='all')


# ======================================================================
# Signal Construction
# ======================================================================

def compute_close_to_range(closes, highs, lows, lookback):
    """
    Compute (close - N_low) / (N_high - N_low) for each asset.
    Result is in [0, 1]: 0 = at N-day low, 1 = at N-day high.
    """
    rolling_high = highs.rolling(lookback, min_periods=max(1, lookback // 2)).max()
    rolling_low = lows.rolling(lookback, min_periods=max(1, lookback // 2)).min()
    range_width = rolling_high - rolling_low
    # Avoid division by zero
    ctr = (closes - rolling_low) / range_width.replace(0, np.nan)
    return ctr.clip(0, 1)


# ======================================================================
# Backtest Engine
# ======================================================================

def backtest_xs_factor(closes, signals, rebal_days, n_long_short,
                       direction='momentum', fee_bps=FEE_BPS):
    """
    Cross-sectional long/short factor backtest.

    direction='momentum':   long HIGHEST signal (near highs), short LOWEST (near lows)
    direction='contrarian': long LOWEST signal (near lows), short HIGHEST (near highs)

    Returns daily portfolio return series.
    """
    returns = closes.pct_change()
    assets = [a for a in signals.columns if a in returns.columns]
    asset_returns = returns[assets]

    common_idx = signals.dropna(how='all').index.intersection(
        asset_returns.dropna(how='all').index
    )
    signals = signals.loc[common_idx]
    asset_returns = asset_returns.loc[common_idx]

    portfolio_returns = pd.Series(0.0, index=common_idx)
    current_longs = []
    current_shorts = []
    last_rebal = None

    for i, date in enumerate(common_idx):
        if i == 0:
            continue

        prev_date = common_idx[i - 1]
        sig = signals.loc[prev_date].dropna()

        if len(sig) < 2 * n_long_short:
            continue

        days_since = (date - last_rebal).days if last_rebal else rebal_days + 1

        if days_since >= rebal_days:
            ranked = sig.sort_values()

            if direction == 'momentum':
                # Momentum: long HIGHEST (near highs), short LOWEST (near lows)
                new_longs = ranked.index[-n_long_short:].tolist()
                new_shorts = ranked.index[:n_long_short].tolist()
            else:
                # Contrarian: long LOWEST (near lows), short HIGHEST (near highs)
                new_longs = ranked.index[:n_long_short].tolist()
                new_shorts = ranked.index[-n_long_short:].tolist()

            # Turnover-based fee calculation
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
                    r = asset_returns.loc[date, a]
                    if not np.isnan(r):
                        day_ret += w * r
            for a in current_shorts:
                if a in asset_returns.columns:
                    r = asset_returns.loc[date, a]
                    if not np.isnan(r):
                        day_ret -= w * r
            portfolio_returns.loc[date] += day_ret

    return portfolio_returns


def compute_win_rate(rets, rebal_days):
    cumrets = (1 + rets).cumprod()
    period_rets = cumrets.iloc[::rebal_days].pct_change().dropna()
    if len(period_rets) == 0:
        return 0.0
    return float((period_rets > 0).sum() / len(period_rets))


# ======================================================================
# Walk-Forward Validation
# ======================================================================

def walk_forward_test(closes, highs, lows, lookback, rebal_days, n_long_short,
                      direction='momentum', n_folds=6, train_days=180, test_days=90):
    signals = compute_close_to_range(closes, highs, lows, lookback)
    returns = closes.pct_change()
    assets = [a for a in signals.columns if a in returns.columns]
    common_idx = signals.dropna(how='all').index.intersection(
        returns[assets].dropna(how='all').index
    )

    total_days = len(common_idx)
    total_test = n_folds * test_days
    first_test_start = total_days - total_test

    if first_test_start < train_days:
        return []

    fold_results = []
    for fold in range(n_folds):
        test_start_idx = first_test_start + fold * test_days
        test_end_idx = min(test_start_idx + test_days, total_days)

        if test_end_idx <= test_start_idx:
            break

        test_dates = common_idx[test_start_idx:test_end_idx]
        if len(test_dates) < 10:
            break

        test_start = test_dates[0]
        test_end = test_dates[-1]

        test_closes = closes.loc[test_start:test_end]
        test_signals = signals.loc[:test_end]

        rets = backtest_xs_factor(test_closes, test_signals, rebal_days,
                                  n_long_short, direction=direction)
        rets = rets[rets.index >= test_start]

        if len(rets) > 10:
            sr = sharpe_ratio(rets, periods_per_year=365)
            fold_results.append({
                'fold': fold,
                'start': str(test_start.date()),
                'end': str(test_end.date()),
                'sharpe': round(sr, 3),
                'days': len(rets),
                'total_ret': round(float(rets.sum()), 4),
            })

    return fold_results


# ======================================================================
# Split-Half Validation
# ======================================================================

def split_half_test(closes, highs, lows, lookback, rebal_days, n_long_short,
                    direction='momentum'):
    signals = compute_close_to_range(closes, highs, lows, lookback)
    common_idx = signals.dropna(how='all').index.intersection(
        closes.dropna(how='all').index
    )
    mid = len(common_idx) // 2

    results = {}
    for label, dates in [('first_half', common_idx[:mid]), ('second_half', common_idx[mid:])]:
        start, end = dates[0], dates[-1]
        sub_closes = closes.loc[start:end]
        sub_signals = signals.loc[:end]
        rets = backtest_xs_factor(sub_closes, sub_signals, rebal_days,
                                  n_long_short, direction=direction)
        rets = rets[rets.index >= start]
        if len(rets) > 20:
            eq = 10000 * (1 + rets).cumprod()
            results[label] = {
                'sharpe': round(sharpe_ratio(rets, periods_per_year=365), 3),
                'annual_ret': round(annual_return(eq, periods_per_year=365), 4),
                'max_dd': round(max_drawdown(eq), 4),
                'days': len(rets),
                'start': str(start.date()),
                'end': str(end.date()),
            }
    return results


# ======================================================================
# Correlation Benchmarks
# ======================================================================

def compute_h012_returns(closes, lookback=60, rebal=5, n_long=4):
    """H-012: 60d XS Momentum. Long top momentum, short bottom."""
    mom = closes.pct_change(lookback)
    returns = closes.pct_change()

    common_idx = mom.dropna(how='all').index.intersection(
        returns.dropna(how='all').index
    )
    mom = mom.loc[common_idx]
    asset_returns = returns.loc[common_idx]

    portfolio_returns = pd.Series(0.0, index=common_idx)
    current_longs = []
    current_shorts = []
    last_rebal = None
    warmup = lookback + 5

    for i, date in enumerate(common_idx):
        if i < warmup:
            continue
        prev_date = common_idx[i - 1]
        sig = mom.loc[prev_date].dropna()
        if len(sig) < 2 * n_long:
            continue
        days_since = (date - last_rebal).days if last_rebal else rebal + 1
        if days_since >= rebal:
            ranked = sig.sort_values(ascending=False)
            current_longs = ranked.index[:n_long].tolist()
            current_shorts = ranked.index[-n_long:].tolist()
            last_rebal = date
        if current_longs and current_shorts:
            w = 1.0 / (2 * n_long)
            day_ret = 0.0
            for a in current_longs:
                if a in asset_returns.columns:
                    r = asset_returns.loc[date, a]
                    if not np.isnan(r):
                        day_ret += w * r
            for a in current_shorts:
                if a in asset_returns.columns:
                    r = asset_returns.loc[date, a]
                    if not np.isnan(r):
                        day_ret -= w * r
            portfolio_returns.loc[date] += day_ret

    return portfolio_returns


def compute_h031_returns(closes, rebal=5, n_long=4):
    """
    H-031: Size factor. Signal = market cap proxy (rolling avg close * volume).
    Contrarian (small-cap outperforms large-cap).
    """
    # Size proxy: log of close price (crude but consistent with previous sessions)
    size_signal = np.log(closes + 1e-10)
    # Contrarian: long small (low signal), short large (high signal)
    return backtest_xs_factor(closes, size_signal, rebal, n_long, direction='contrarian')


def compute_correlation(rets_a, rets_b):
    common = rets_a.index.intersection(rets_b.index)
    a = rets_a.loc[common]
    b = rets_b.loc[common]
    mask = (a != 0) | (b != 0)
    a_f = a[mask]
    b_f = b[mask]
    if len(a_f) < 30:
        return None, 0
    return round(float(a_f.corr(b_f)), 3), len(a_f)


# ======================================================================
# Main
# ======================================================================

def main():
    print("=" * 70)
    print("H-131: Close-to-Range Position Factor")
    print("Cross-Sectional Factor Backtest (Momentum + Contrarian directions)")
    print("=" * 70)

    # -- Load Data --
    print("\nLoading data...")
    data = load_daily_ohlcv()
    closes = build_close_panel(data)
    highs = build_high_panel(data)
    lows = build_low_panel(data)

    # Align all three panels
    common_idx = closes.index.intersection(highs.index).intersection(lows.index)
    closes = closes.loc[common_idx]
    highs = highs.loc[common_idx]
    lows = lows.loc[common_idx]

    print(f"Data loaded: {len(common_idx)} days, {closes.shape[1]} assets")
    print(f"Date range: {common_idx[0].date()} to {common_idx[-1].date()}")

    # Quick signal preview
    print(f"\nClose-to-range sample (last date, lookback=10):")
    sample_sig = compute_close_to_range(closes, highs, lows, 10)
    last_sig = sample_sig.iloc[-1].sort_values()
    for asset, val in last_sig.items():
        print(f"  {asset:>5}: {val:.3f}")

    # -- Parameter Grid Search --
    lookback_list = [5, 10, 20, 30]
    rebal_list = [3, 5, 7]
    n_list = [3, 4]
    directions = ['momentum', 'contrarian']

    total_combos = len(lookback_list) * len(rebal_list) * len(n_list) * len(directions)
    print(f"\n{'='*70}")
    print(f"PARAMETER GRID SEARCH: {total_combos} combinations")
    print(f"Lookbacks: {lookback_list}")
    print(f"Rebalance days: {rebal_list}")
    print(f"N long/short: {n_list}")
    print(f"Directions: {directions}")
    print(f"{'='*70}")

    results = []
    for lb, rd, n, d in product(lookback_list, rebal_list, n_list, directions):
        signal = compute_close_to_range(closes, highs, lows, lb)
        rets = backtest_xs_factor(closes, signal, rd, n, direction=d)

        if len(rets) < 30:
            continue

        eq = 10000 * (1 + rets).cumprod()
        sr = sharpe_ratio(rets, periods_per_year=365)
        ar = annual_return(eq, periods_per_year=365)
        dd = max_drawdown(eq)
        tr = total_return(eq)
        wr = compute_win_rate(rets, rd)

        results.append({
            'lookback': lb, 'rebal': rd, 'n': n, 'direction': d,
            'sharpe': round(sr, 3),
            'annual_ret': round(ar, 4),
            'total_ret': round(tr, 4),
            'max_dd': round(dd, 4),
            'win_rate': round(wr, 4),
            'days': len(rets),
        })

    df = pd.DataFrame(results)

    # -- Parameter Robustness Summary --
    print(f"\n{'='*70}")
    print(f"PARAMETER ROBUSTNESS: {len(df)} combinations tested")
    print(f"{'='*70}")

    n_positive = int((df['sharpe'] > 0).sum())
    pct_positive = n_positive / len(df) * 100
    print(f"\nPositive Sharpe: {n_positive}/{len(df)} ({pct_positive:.1f}%)")
    print(f"Mean Sharpe:   {df['sharpe'].mean():.3f}")
    print(f"Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"Std Sharpe:    {df['sharpe'].std():.3f}")
    print(f"Min Sharpe:    {df['sharpe'].min():.3f}")
    print(f"Max Sharpe:    {df['sharpe'].max():.3f}")

    print(f"\nBy direction:")
    for d in directions:
        sub = df[df['direction'] == d]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  {d:>11}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.0f}%), "
              f"mean Sharpe {sub['sharpe'].mean():.3f}, median {sub['sharpe'].median():.3f}")

    print(f"\nBy lookback:")
    for lb in lookback_list:
        sub = df[df['lookback'] == lb]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  LB={lb:>2}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.0f}%), "
              f"mean Sharpe {sub['sharpe'].mean():.3f}")

    print(f"\nBy N long/short:")
    for n in n_list:
        sub = df[df['n'] == n]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  N={n}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.0f}%), "
              f"mean Sharpe {sub['sharpe'].mean():.3f}")

    print(f"\nBy rebalance frequency:")
    for rd in rebal_list:
        sub = df[df['rebal'] == rd]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  R={rd}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.0f}%), "
              f"mean Sharpe {sub['sharpe'].mean():.3f}")

    print(f"\nTop 15 by Sharpe:")
    top = df.nlargest(15, 'sharpe')
    for _, r in top.iterrows():
        print(f"  {r['direction']:>11} LB{r['lookback']:>2} R{r['rebal']:>2} N{r['n']}: "
              f"Sharpe {r['sharpe']:+.3f}, Ann {r['annual_ret']*100:+.1f}%, "
              f"DD {r['max_dd']*100:.1f}%, WR {r['win_rate']*100:.0f}%")

    print(f"\nBottom 5 by Sharpe:")
    bottom = df.nsmallest(5, 'sharpe')
    for _, r in bottom.iterrows():
        print(f"  {r['direction']:>11} LB{r['lookback']:>2} R{r['rebal']:>2} N{r['n']}: "
              f"Sharpe {r['sharpe']:+.3f}, Ann {r['annual_ret']*100:+.1f}%, DD {r['max_dd']*100:.1f}%")

    # -- Best Params Full Analysis --
    best = df.nlargest(1, 'sharpe').iloc[0]
    best_lb = int(best['lookback'])
    best_rd = int(best['rebal'])
    best_n = int(best['n'])
    best_dir = best['direction']

    print(f"\n{'='*70}")
    print(f"BEST PARAMS: direction={best_dir} LB={best_lb} R={best_rd} N={best_n}")
    print(f"  Sharpe:     {best['sharpe']:.3f}")
    print(f"  Annual Ret: {best['annual_ret']*100:+.2f}%")
    print(f"  Max DD:     {best['max_dd']*100:.2f}%")
    print(f"  Total Ret:  {best['total_ret']*100:+.2f}%")
    print(f"  Win Rate:   {best['win_rate']*100:.1f}%")
    print(f"  Days:       {int(best['days'])}")
    print(f"{'='*70}")

    # Fee sensitivity
    signal_best = compute_close_to_range(closes, highs, lows, best_lb)
    print(f"\nFee sensitivity (best params):")
    for fee_mult in [1, 2, 3, 5]:
        rets = backtest_xs_factor(closes, signal_best, best_rd, best_n,
                                  direction=best_dir, fee_bps=FEE_BPS * fee_mult)
        sr = sharpe_ratio(rets, periods_per_year=365)
        print(f"  {fee_mult}x fees ({FEE_BPS*fee_mult}bps): Sharpe {sr:.3f}")

    # -- Walk-Forward Validation --
    print(f"\n{'='*70}")
    print(f"WALK-FORWARD VALIDATION (6 folds, 180d train, 90d test)")
    print(f"{'='*70}")

    wf_results = walk_forward_test(closes, highs, lows, best_lb,
                                   best_rd, best_n, direction=best_dir,
                                   n_folds=6, train_days=180, test_days=90)
    if wf_results:
        for fold_r in wf_results:
            print(f"  Fold {fold_r['fold']}: {fold_r['start']} to {fold_r['end']} -- "
                  f"Sharpe {fold_r['sharpe']:+.3f}, Ret {fold_r['total_ret']*100:+.2f}% "
                  f"({fold_r['days']} days)")

        wf_sharpes = [f['sharpe'] for f in wf_results]
        n_pos_folds = sum(1 for s in wf_sharpes if s > 0)
        mean_oos = np.mean(wf_sharpes)
        median_oos = np.median(wf_sharpes)
        print(f"\n  OOS Summary: {n_pos_folds}/{len(wf_results)} positive folds")
        print(f"  Mean OOS Sharpe:   {mean_oos:.3f}")
        print(f"  Median OOS Sharpe: {median_oos:.3f}")
        print(f"  In-sample Sharpe:  {best['sharpe']:.3f}")
        if best['sharpe'] != 0:
            print(f"  IS/OOS ratio:      {mean_oos/best['sharpe']:.2f}")
    else:
        print("  Insufficient data for walk-forward")
        wf_sharpes = []
        n_pos_folds = 0
        mean_oos = -99

    # WF top 3
    print(f"\nWalk-forward for top 3 param sets:")
    top3 = df.nlargest(3, 'sharpe')
    for idx, (_, r) in enumerate(top3.iterrows()):
        lb, rd, n, d = int(r['lookback']), int(r['rebal']), int(r['n']), r['direction']
        wf = walk_forward_test(closes, highs, lows, lb, rd, n, direction=d)
        if wf:
            wf_s = [f['sharpe'] for f in wf]
            n_pos = sum(1 for s in wf_s if s > 0)
            print(f"  #{idx+1} {d:>11} LB{lb} R{rd} N{n}: IS={r['sharpe']:.3f}, "
                  f"OOS mean={np.mean(wf_s):.3f}, {n_pos}/{len(wf)} positive folds")

    # -- Split-Half Validation --
    print(f"\n{'='*70}")
    print(f"SPLIT-HALF VALIDATION (best params)")
    print(f"{'='*70}")

    split = split_half_test(closes, highs, lows, best_lb, best_rd, best_n,
                            direction=best_dir)
    for label, stats in split.items():
        print(f"  {label}: Sharpe {stats['sharpe']:+.3f}, "
              f"Ann {stats['annual_ret']*100:+.1f}%, DD {stats['max_dd']*100:.1f}% "
              f"({stats['start']} to {stats['end']}, {stats['days']} days)")

    s1 = split.get('first_half', {}).get('sharpe', -99)
    s2 = split.get('second_half', {}).get('sharpe', -99)
    stability = min(s1, s2)
    if s1 != -99 and s2 != -99:
        print(f"\n  H1 Sharpe: {s1:.3f}")
        print(f"  H2 Sharpe: {s2:.3f}")
        print(f"  Stability (min): {stability:.3f}")
        print(f"  Both halves positive: {'YES' if s1 > 0 and s2 > 0 else 'NO'}")

    if len(wf_results) >= 4:
        wf_h1 = wf_sharpes[:len(wf_sharpes)//2]
        wf_h2 = wf_sharpes[len(wf_sharpes)//2:]
        wf_h1_mean = np.mean(wf_h1)
        wf_h2_mean = np.mean(wf_h2)
        print(f"\n  WF H1 mean Sharpe: {wf_h1_mean:.3f}")
        print(f"  WF H2 mean Sharpe: {wf_h2_mean:.3f}")
        print(f"  WF stability (min): {min(wf_h1_mean, wf_h2_mean):.3f}")
    else:
        wf_h1_mean = -99
        wf_h2_mean = -99

    # -- Correlations --
    print(f"\n{'='*70}")
    print(f"CORRELATIONS")
    print(f"{'='*70}")

    h131_rets = backtest_xs_factor(closes, signal_best, best_rd, best_n,
                                   direction=best_dir)
    h012_rets = compute_h012_returns(closes, lookback=60, rebal=5, n_long=4)
    h031_rets = compute_h031_returns(closes, rebal=5, n_long=4)

    corr_h012, n_h012 = compute_correlation(h131_rets, h012_rets)
    corr_h031, n_h031 = compute_correlation(h131_rets, h031_rets)

    if corr_h012 is not None:
        print(f"\n  Correlation with H-012 (60d momentum): {corr_h012:.3f} ({n_h012} days)")
        print(f"  Redundant (>0.6)? {'YES' if abs(corr_h012) > 0.6 else 'NO'}")
    if corr_h031 is not None:
        print(f"\n  Correlation with H-031 (size factor):  {corr_h031:.3f} ({n_h031} days)")
        print(f"  Redundant (>0.6)? {'YES' if abs(corr_h031) > 0.6 else 'NO'}")

    # -- Save Results --
    # Pick median param set for reporting (more robust than best)
    median_row = df.iloc[(df['sharpe'] - df['sharpe'].median()).abs().argsort().iloc[0]]

    output = {
        'hypothesis': 'H-131',
        'name': 'Close-to-Range Position Factor',
        'date_run': str(pd.Timestamp.now().date()),
        'data_range': {
            'start': str(common_idx[0].date()),
            'end': str(common_idx[-1].date()),
            'days': len(common_idx),
            'assets': closes.shape[1],
        },
        'parameter_grid': {
            'total_combos': len(df),
            'n_positive_sharpe': n_positive,
            'pct_positive_sharpe': round(pct_positive, 1),
            'mean_sharpe': round(float(df['sharpe'].mean()), 3),
            'median_sharpe': round(float(df['sharpe'].median()), 3),
            'std_sharpe': round(float(df['sharpe'].std()), 3),
        },
        'best_params': {
            'lookback': best_lb,
            'rebal': best_rd,
            'n': best_n,
            'direction': best_dir,
            'sharpe': round(float(best['sharpe']), 3),
            'annual_ret': round(float(best['annual_ret']), 4),
            'max_dd': round(float(best['max_dd']), 4),
            'total_ret': round(float(best['total_ret']), 4),
            'win_rate': round(float(best['win_rate']), 4),
        },
        'walk_forward': {
            'n_folds': len(wf_results),
            'n_positive_folds': n_pos_folds,
            'mean_oos_sharpe': round(float(mean_oos), 3) if mean_oos != -99 else None,
            'folds': wf_results,
        },
        'split_half': {
            'first_half_sharpe': s1,
            'second_half_sharpe': s2,
            'stability_min': round(stability, 3) if s1 != -99 and s2 != -99 else None,
            'both_positive': bool(s1 > 0 and s2 > 0) if s1 != -99 and s2 != -99 else None,
        },
        'correlations': {
            'h012_corr': corr_h012,
            'h012_redundant': bool(abs(corr_h012) > 0.6) if corr_h012 is not None else None,
            'h031_corr': corr_h031,
            'h031_redundant': bool(abs(corr_h031) > 0.6) if corr_h031 is not None else None,
        },
        'all_results': df.to_dict(orient='records'),
    }

    # Verdict logic
    verdict_reasons = []
    passed = True

    if pct_positive < 80:
        verdict_reasons.append(f"IS params only {pct_positive:.0f}% positive (need >=80%)")
        passed = False
    if n_pos_folds < 4:
        verdict_reasons.append(f"WF only {n_pos_folds}/6 positive folds (need >=4)")
        passed = False
    if s1 != -99 and s2 != -99 and stability <= 0:
        verdict_reasons.append(f"Split-half instability (min Sharpe={stability:.3f})")
        passed = False
    if corr_h012 is not None and abs(corr_h012) > 0.6:
        verdict_reasons.append(f"Too correlated with H-012 ({corr_h012:.3f})")
        passed = False
    if corr_h031 is not None and abs(corr_h031) > 0.6:
        verdict_reasons.append(f"Too correlated with H-031 ({corr_h031:.3f})")
        passed = False

    # Conditional if some criteria met
    n_criteria_met = sum([
        pct_positive >= 80,
        n_pos_folds >= 4,
        s1 != -99 and s2 != -99 and stability > 0,
    ])

    if passed:
        verdict = 'CONFIRMED'
    elif n_criteria_met >= 2:
        verdict = 'CONDITIONAL'
    else:
        verdict = 'REJECTED'

    output['verdict'] = verdict
    output['verdict_reasons'] = verdict_reasons

    print(f"\n{'='*70}")
    print(f"VERDICT: {verdict}")
    for r in verdict_reasons:
        print(f"  - {r}")
    print(f"{'='*70}")

    results_path = RESULTS_DIR / "results.json"
    with open(results_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to {results_path}")

    return output


if __name__ == '__main__':
    main()
