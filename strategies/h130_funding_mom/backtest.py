"""
H-130: Funding Rate Momentum Factor — Cross-Sectional Backtest
================================================================

Idea: Use the RATE OF CHANGE in funding rates as a signal, not the level.
  - funding_momentum = short_rolling_avg - long_rolling_avg of daily avg funding
  - Rising funding = increasing bullish sentiment (crowd getting more leveraged long)
  - Falling funding = decreasing sentiment

Directions:
  - CONTRARIAN: short assets with rising funding, long assets with falling funding
  - MOMENTUM: long assets with rising funding, short assets with falling funding

This differs from H-053 (funding LEVEL contrarian) and H-089 (funding change,
contrarian only). H-130 tests BOTH directions in the parameter grid.

Parameter grid: short_window [3,5,7] x long_window [14,21,30] x rebal [3,5,7]
                x N [3,4] x direction [contrarian, momentum] = 162 combos

Validation:
  1. In-sample: % params with positive Sharpe (need >= 80%)
  2. Walk-forward: 6 folds, 180d train / 90d test (need >= 4/6 positive OOS folds)
  3. Split-half stability: Sharpe H1 vs H2 (need stability > 0)
  4. Correlation with H-053 (funding level contrarian): need < 0.6
  5. Correlation with H-012 (60d momentum): need < 0.6
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
DATA_DIR = ROOT / "data"
RESULTS_DIR = Path(__file__).resolve().parent

FEE_BPS = 5  # one-way fee in basis points


# ======================================================================
# Data Loading
# ======================================================================

def load_daily_closes():
    """Load daily close prices for all 14 assets."""
    closes = {}
    for asset in ASSETS:
        df = fetch_and_cache(f"{asset}/USDT", '1d')
        if df is not None and len(df) > 0:
            closes[asset] = df['close']
    panel = pd.DataFrame(closes).sort_index().dropna(how='all')
    return panel


def load_funding_rates():
    """Load 8h funding rates and aggregate to daily average."""
    funding = {}
    for asset in ASSETS:
        fpath = DATA_DIR / f"{asset}_USDT_USDT_funding.parquet"
        if not fpath.exists():
            print(f"  WARNING: no funding data for {asset}")
            continue
        df = pd.read_parquet(fpath)
        daily = df['funding_rate'].resample('1D').mean()
        funding[asset] = daily
    panel = pd.DataFrame(funding).sort_index().dropna(how='all')
    print(f"Funding data: {len(panel)} days, {len(panel.columns)} assets")
    print(f"Date range: {panel.index[0].date()} to {panel.index[-1].date()}")
    return panel


# ======================================================================
# Signal Construction
# ======================================================================

def compute_funding_momentum(funding_panel, short_window, long_window):
    """
    funding_momentum = short_rolling_avg - long_rolling_avg of daily avg funding.
    Positive = funding trending up (crowd getting more leveraged long).
    Negative = funding trending down.
    """
    short_avg = funding_panel.rolling(short_window, min_periods=max(1, short_window // 2)).mean()
    long_avg = funding_panel.rolling(long_window, min_periods=max(1, long_window // 2)).mean()
    return short_avg - long_avg


# ======================================================================
# Backtest Engine
# ======================================================================

def backtest_xs_factor(closes, signals, rebal_days, n_long_short,
                       direction='contrarian', fee_bps=FEE_BPS):
    """
    Cross-sectional long/short factor backtest.

    direction='contrarian': long LOWEST signal (falling funding), short HIGHEST (rising funding)
    direction='momentum':   long HIGHEST signal (rising funding), short LOWEST (falling funding)

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

            if direction == 'contrarian':
                # Contrarian: long LOWEST (falling funding), short HIGHEST (rising)
                new_longs = ranked.index[:n_long_short].tolist()
                new_shorts = ranked.index[-n_long_short:].tolist()
            else:
                # Momentum: long HIGHEST (rising funding), short LOWEST (falling)
                new_longs = ranked.index[-n_long_short:].tolist()
                new_shorts = ranked.index[:n_long_short].tolist()

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
    """Compute win rate based on rebalance-period returns."""
    # Group returns into rebalance-period chunks
    cumrets = (1 + rets).cumprod()
    period_rets = cumrets.iloc[::rebal_days].pct_change().dropna()
    if len(period_rets) == 0:
        return 0.0
    return float((period_rets > 0).sum() / len(period_rets))


# ======================================================================
# Walk-Forward Validation
# ======================================================================

def walk_forward_test(closes, funding, short_w, long_w, rebal_days, n_long_short,
                      direction='contrarian', n_folds=6, train_days=180, test_days=90):
    """
    Rolling walk-forward: train_days train, test_days test.
    Uses fixed signal params, tests on OOS windows.
    """
    signals = compute_funding_momentum(funding, short_w, long_w)
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

def split_half_test(closes, funding, short_w, long_w, rebal_days, n_long_short,
                    direction='contrarian'):
    """Test on first half vs second half of data."""
    signals = compute_funding_momentum(funding, short_w, long_w)
    common_idx = signals.dropna(how='all').index.intersection(
        closes.dropna(how='all').index
    )
    mid = len(common_idx) // 2

    first_half_dates = common_idx[:mid]
    second_half_dates = common_idx[mid:]

    results = {}
    for label, dates in [('first_half', first_half_dates), ('second_half', second_half_dates)]:
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

def compute_h053_returns(closes, funding, lookback=14, rebal=5, n_long=4):
    """
    H-053: Funding rate LEVEL contrarian.
    Signal = rolling mean of funding rate level.
    Contrarian: long LOW funding (less crowded longs), short HIGH funding.
    """
    signal = funding.rolling(lookback, min_periods=max(1, lookback // 2)).mean()
    return backtest_xs_factor(closes, signal, rebal, n_long, direction='contrarian')


def compute_h012_returns(closes, lookback=60, rebal=5, n_long=4):
    """H-012: 60d XS Momentum. Long top momentum, short bottom."""
    mom = closes.pct_change(lookback)
    returns = closes.pct_change()
    assets = list(closes.columns)

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


def compute_correlation(rets_a, rets_b, label_a="A", label_b="B"):
    """Compute daily return correlation between two strategies."""
    common = rets_a.index.intersection(rets_b.index)
    a = rets_a.loc[common]
    b = rets_b.loc[common]
    mask = (a != 0) | (b != 0)
    a_filtered = a[mask]
    b_filtered = b[mask]

    if len(a_filtered) < 30:
        return None, 0

    corr = a_filtered.corr(b_filtered)
    return round(float(corr), 3), len(a_filtered)


# ======================================================================
# Main
# ======================================================================

def main():
    print("=" * 70)
    print("H-130: Funding Rate Momentum Factor")
    print("Cross-Sectional Factor Backtest (Contrarian + Momentum directions)")
    print("=" * 70)

    # -- Load Data --
    print("\nLoading data...")
    closes = load_daily_closes()
    funding = load_funding_rates()

    # Align dates
    common_dates = closes.index.intersection(funding.index)
    closes = closes.loc[common_dates]
    funding = funding.loc[common_dates]
    print(f"Aligned: {len(common_dates)} days, {closes.shape[1]} assets")
    print(f"Date range: {common_dates[0].date()} to {common_dates[-1].date()}")

    # Quick funding summary
    print(f"\nFunding rate summary (daily avg, annualized %):")
    ann = funding.mean() * 3 * 365 * 100  # 3 funding periods/day
    for asset in ASSETS:
        if asset in ann.index:
            print(f"  {asset:>5}: {ann[asset]:+.2f}%")

    xs_std = funding.std(axis=1).mean()
    print(f"\nCross-sectional std of daily funding: {xs_std:.6f}")

    # -- Parameter Grid Search --
    short_windows = [3, 5, 7]
    long_windows = [14, 21, 30]
    rebal_list = [3, 5, 7]
    n_list = [3, 4]
    directions = ['contrarian', 'momentum']

    total_combos = (len(short_windows) * len(long_windows) * len(rebal_list)
                    * len(n_list) * len(directions))
    print(f"\n{'='*70}")
    print(f"PARAMETER GRID SEARCH: {total_combos} combinations")
    print(f"Short windows: {short_windows}")
    print(f"Long windows: {long_windows}")
    print(f"Rebalance days: {rebal_list}")
    print(f"N long/short: {n_list}")
    print(f"Directions: {directions}")
    print(f"{'='*70}")

    results = []
    for sw, lw, rd, n, d in product(short_windows, long_windows, rebal_list, n_list, directions):
        signal = compute_funding_momentum(funding, sw, lw)
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
            'short_w': sw, 'long_w': lw, 'rebal': rd, 'n': n, 'direction': d,
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

    # Breakdown by direction
    print(f"\nBy direction:")
    for d in directions:
        sub = df[df['direction'] == d]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  {d:>11}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.0f}%), "
              f"mean Sharpe {sub['sharpe'].mean():.3f}, median {sub['sharpe'].median():.3f}")

    # Breakdown by short window
    print(f"\nBy short window:")
    for sw in short_windows:
        sub = df[df['short_w'] == sw]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  SW={sw}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.0f}%), "
              f"mean Sharpe {sub['sharpe'].mean():.3f}")

    # Breakdown by long window
    print(f"\nBy long window:")
    for lw in long_windows:
        sub = df[df['long_w'] == lw]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  LW={lw}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.0f}%), "
              f"mean Sharpe {sub['sharpe'].mean():.3f}")

    # Breakdown by N
    print(f"\nBy N long/short:")
    for n in n_list:
        sub = df[df['n'] == n]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  N={n}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.0f}%), "
              f"mean Sharpe {sub['sharpe'].mean():.3f}")

    # Breakdown by rebalance
    print(f"\nBy rebalance frequency:")
    for rd in rebal_list:
        sub = df[df['rebal'] == rd]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  R={rd}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.0f}%), "
              f"mean Sharpe {sub['sharpe'].mean():.3f}")

    # Top 15
    print(f"\nTop 15 by Sharpe:")
    top = df.nlargest(15, 'sharpe')
    for _, r in top.iterrows():
        print(f"  {r['direction']:>11} SW{r['short_w']:>2} LW{r['long_w']:>2} R{r['rebal']:>2} N{r['n']}: "
              f"Sharpe {r['sharpe']:+.3f}, Ann {r['annual_ret']*100:+.1f}%, "
              f"DD {r['max_dd']*100:.1f}%, WR {r['win_rate']*100:.0f}%")

    # Bottom 5
    print(f"\nBottom 5 by Sharpe:")
    bottom = df.nsmallest(5, 'sharpe')
    for _, r in bottom.iterrows():
        print(f"  {r['direction']:>11} SW{r['short_w']:>2} LW{r['long_w']:>2} R{r['rebal']:>2} N{r['n']}: "
              f"Sharpe {r['sharpe']:+.3f}, Ann {r['annual_ret']*100:+.1f}%, DD {r['max_dd']*100:.1f}%")

    # -- Best Params Full Analysis --
    best = df.nlargest(1, 'sharpe').iloc[0]
    best_sw = int(best['short_w'])
    best_lw = int(best['long_w'])
    best_rd = int(best['rebal'])
    best_n = int(best['n'])
    best_dir = best['direction']

    print(f"\n{'='*70}")
    print(f"BEST PARAMS: direction={best_dir} SW={best_sw} LW={best_lw} R={best_rd} N={best_n}")
    print(f"  Sharpe:     {best['sharpe']:.3f}")
    print(f"  Annual Ret: {best['annual_ret']*100:+.2f}%")
    print(f"  Max DD:     {best['max_dd']*100:.2f}%")
    print(f"  Total Ret:  {best['total_ret']*100:+.2f}%")
    print(f"  Win Rate:   {best['win_rate']*100:.1f}%")
    print(f"  Days:       {int(best['days'])}")
    print(f"{'='*70}")

    # -- Fee Sensitivity --
    print(f"\nFee sensitivity (best params):")
    signal_best = compute_funding_momentum(funding, best_sw, best_lw)
    for fee_mult in [1, 2, 3, 5]:
        rets = backtest_xs_factor(closes, signal_best, best_rd, best_n,
                                  direction=best_dir, fee_bps=FEE_BPS * fee_mult)
        sr = sharpe_ratio(rets, periods_per_year=365)
        print(f"  {fee_mult}x fees ({FEE_BPS*fee_mult}bps): Sharpe {sr:.3f}")

    # -- Walk-Forward Validation --
    print(f"\n{'='*70}")
    print(f"WALK-FORWARD VALIDATION (6 folds, 180d train, 90d test)")
    print(f"{'='*70}")

    wf_results = walk_forward_test(closes, funding, best_sw, best_lw,
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

    # Walk-forward for top 3 param sets
    print(f"\nWalk-forward for top 3 param sets:")
    top3 = df.nlargest(3, 'sharpe')
    for idx, (_, r) in enumerate(top3.iterrows()):
        sw, lw, rd, n, d = (int(r['short_w']), int(r['long_w']),
                             int(r['rebal']), int(r['n']), r['direction'])
        wf = walk_forward_test(closes, funding, sw, lw, rd, n, direction=d)
        if wf:
            wf_s = [f['sharpe'] for f in wf]
            n_pos = sum(1 for s in wf_s if s > 0)
            print(f"  #{idx+1} {d:>11} SW{sw} LW{lw} R{rd} N{n}: IS={r['sharpe']:.3f}, "
                  f"OOS mean={np.mean(wf_s):.3f}, {n_pos}/{len(wf)} positive folds")

    # -- Split-Half Validation --
    print(f"\n{'='*70}")
    print(f"SPLIT-HALF VALIDATION (best params)")
    print(f"{'='*70}")

    split = split_half_test(closes, funding, best_sw, best_lw, best_rd, best_n,
                            direction=best_dir)
    for label, stats in split.items():
        print(f"  {label}: Sharpe {stats['sharpe']:+.3f}, "
              f"Ann {stats['annual_ret']*100:+.1f}%, DD {stats['max_dd']*100:.1f}% "
              f"({stats['start']} to {stats['end']}, {stats['days']} days)")

    s1 = split.get('first_half', {}).get('sharpe', -99)
    s2 = split.get('second_half', {}).get('sharpe', -99)
    stability = min(s1, s2)  # stability > 0 means both halves positive
    if s1 != -99 and s2 != -99:
        print(f"\n  H1 Sharpe: {s1:.3f}")
        print(f"  H2 Sharpe: {s2:.3f}")
        print(f"  Stability (min): {stability:.3f}")
        print(f"  Both halves positive: {'YES' if s1 > 0 and s2 > 0 else 'NO'}")

    # -- Split-half on walk-forward OOS returns --
    print(f"\n  Split-half on WF OOS folds:")
    if len(wf_results) >= 4:
        wf_h1 = wf_sharpes[:len(wf_sharpes)//2]
        wf_h2 = wf_sharpes[len(wf_sharpes)//2:]
        wf_h1_mean = np.mean(wf_h1)
        wf_h2_mean = np.mean(wf_h2)
        print(f"  WF H1 mean Sharpe: {wf_h1_mean:.3f} (folds {[f['fold'] for f in wf_results[:len(wf_results)//2]]})")
        print(f"  WF H2 mean Sharpe: {wf_h2_mean:.3f} (folds {[f['fold'] for f in wf_results[len(wf_results)//2:]]})")
        print(f"  WF stability: {min(wf_h1_mean, wf_h2_mean):.3f}")
    else:
        wf_h1_mean = -99
        wf_h2_mean = -99
        print("  Insufficient WF folds for split-half")

    # -- Correlation with H-053 (Funding Level Contrarian) --
    print(f"\n{'='*70}")
    print(f"CORRELATION WITH H-053 (Funding Rate Level Contrarian)")
    print(f"{'='*70}")

    h130_rets = backtest_xs_factor(closes, signal_best, best_rd, best_n,
                                   direction=best_dir)
    h053_rets = compute_h053_returns(closes, funding, lookback=14, rebal=5, n_long=4)

    corr_h053, n_overlap_h053 = compute_correlation(h130_rets, h053_rets, "H-130", "H-053")
    if corr_h053 is not None:
        print(f"  Daily return correlation with H-053: {corr_h053:.3f} ({n_overlap_h053} days)")
        print(f"  Redundant (>0.6)? {'YES' if abs(corr_h053) > 0.6 else 'NO'}")
    else:
        print(f"  Insufficient overlap for H-053 correlation")

    # -- Correlation with H-012 (60d Momentum) --
    print(f"\n{'='*70}")
    print(f"CORRELATION WITH H-012 (60d XS Momentum)")
    print(f"{'='*70}")

    h012_rets = compute_h012_returns(closes, lookback=60, rebal=5, n_long=4)
    corr_h012, n_overlap_h012 = compute_correlation(h130_rets, h012_rets, "H-130", "H-012")
    if corr_h012 is not None:
        print(f"  Daily return correlation with H-012: {corr_h012:.3f} ({n_overlap_h012} days)")
        print(f"  Redundant (>0.6)? {'YES' if abs(corr_h012) > 0.6 else 'NO'}")
    else:
        print(f"  Insufficient overlap for H-012 correlation")

    # Signal-level correlation: funding momentum vs price momentum
    mom60 = closes.pct_change(60)
    rank_corrs = []
    for date in common_dates:
        if date in signal_best.index and date in mom60.index:
            fc = signal_best.loc[date].dropna()
            m = mom60.loc[date].dropna()
            common_assets = fc.index.intersection(m.index)
            if len(common_assets) >= 8:
                rc = fc[common_assets].corr(m[common_assets])
                if not np.isnan(rc):
                    rank_corrs.append(rc)
    if rank_corrs:
        print(f"\n  Signal-level correlation (funding momentum vs 60d price momentum):")
        print(f"    Mean XS corr: {np.mean(rank_corrs):.3f}")
        print(f"    Std XS corr:  {np.std(rank_corrs):.3f}")
        print(f"    % days positive: {sum(1 for r in rank_corrs if r > 0)/len(rank_corrs)*100:.0f}%")

    # ======================================================================
    # VERDICT
    # ======================================================================
    print(f"\n{'='*70}")
    print(f"VERDICT")
    print(f"{'='*70}")

    wf_pct_positive = (n_pos_folds / len(wf_results) * 100) if wf_results else 0

    print(f"\n  Criteria check:")
    print(f"    1. In-sample % positive Sharpe:    {pct_positive:.1f}%  (need >= 80%) {'PASS' if pct_positive >= 80 else 'FAIL'}")
    print(f"    2. Walk-forward positive folds:    {n_pos_folds}/{len(wf_results) if wf_results else 0}  (need >= 4/6)  {'PASS' if n_pos_folds >= 4 else 'FAIL'}")
    print(f"    3. WF mean OOS Sharpe:             {mean_oos:.3f}  (need > 0)    {'PASS' if mean_oos > 0 else 'FAIL'}")
    print(f"    4. Split-half stability:           {stability:.3f}  (need > 0)    {'PASS' if stability > 0 else 'FAIL'}")
    corr_h053_val = corr_h053 if corr_h053 is not None else 0
    corr_h012_val = corr_h012 if corr_h012 is not None else 0
    print(f"    5. Corr with H-053 (redundancy):   {corr_h053_val:.3f}  (need < 0.6)  {'PASS' if abs(corr_h053_val) < 0.6 else 'FAIL'}")
    print(f"    6. Corr with H-012 (redundancy):   {corr_h012_val:.3f}  (need < 0.6)  {'PASS' if abs(corr_h012_val) < 0.6 else 'FAIL'}")

    # Count passes
    passes = 0
    total_criteria = 6
    if pct_positive >= 80:
        passes += 1
    if n_pos_folds >= 4:
        passes += 1
    if mean_oos > 0:
        passes += 1
    if stability > 0:
        passes += 1
    if abs(corr_h053_val) < 0.6:
        passes += 1
    if abs(corr_h012_val) < 0.6:
        passes += 1

    print(f"\n  Passed: {passes}/{total_criteria}")

    # Determine verdict
    if passes == total_criteria:
        verdict = "CONFIRMED"
        reason = "All criteria passed"
        print(f"\n  >>> CONFIRMED: {reason}")
    elif passes >= 4 and mean_oos > 0 and pct_positive >= 60:
        verdict = "CONDITIONAL"
        fails = []
        if pct_positive < 80:
            fails.append(f"IS positive only {pct_positive:.0f}%")
        if n_pos_folds < 4:
            fails.append(f"only {n_pos_folds} positive WF folds")
        if stability <= 0:
            fails.append(f"split-half stability {stability:.3f}")
        if abs(corr_h053_val) >= 0.6:
            fails.append(f"redundant with H-053 (corr={corr_h053_val:.2f})")
        if abs(corr_h012_val) >= 0.6:
            fails.append(f"redundant with H-012 (corr={corr_h012_val:.2f})")
        reason = f"Promising but: {'; '.join(fails)}"
        print(f"\n  >>> CONDITIONAL: {reason}")
    else:
        verdict = "REJECTED"
        fails = []
        if pct_positive < 80:
            fails.append(f"IS positive only {pct_positive:.0f}%")
        if n_pos_folds < 4:
            fails.append(f"only {n_pos_folds} positive WF folds")
        if mean_oos <= 0:
            fails.append(f"negative OOS Sharpe ({mean_oos:.3f})")
        if stability <= 0:
            fails.append(f"split-half stability {stability:.3f}")
        if abs(corr_h053_val) >= 0.6:
            fails.append(f"redundant with H-053 (corr={corr_h053_val:.2f})")
        if abs(corr_h012_val) >= 0.6:
            fails.append(f"redundant with H-012 (corr={corr_h012_val:.2f})")
        reason = "; ".join(fails)
        print(f"\n  >>> REJECTED: {reason}")

    # -- Save Results --
    results_json = {
        'hypothesis': 'H-130',
        'name': 'Funding Rate Momentum Factor',
        'verdict': verdict,
        'reason': reason,
        'data_range': f"{common_dates[0].date()} to {common_dates[-1].date()}",
        'n_assets': len(ASSETS),
        'n_days': len(common_dates),
        'param_robustness': {
            'total_combinations': len(df),
            'pct_positive_sharpe': round(pct_positive, 1),
            'mean_sharpe': round(float(df['sharpe'].mean()), 3),
            'median_sharpe': round(float(df['sharpe'].median()), 3),
            'std_sharpe': round(float(df['sharpe'].std()), 3),
            'max_sharpe': round(float(df['sharpe'].max()), 3),
            'min_sharpe': round(float(df['sharpe'].min()), 3),
        },
        'best_params': {
            'direction': best_dir,
            'short_window': best_sw,
            'long_window': best_lw,
            'rebalance_days': best_rd,
            'n_long_short': best_n,
            'sharpe': round(float(best['sharpe']), 3),
            'annual_return': round(float(best['annual_ret']), 4),
            'max_drawdown': round(float(best['max_dd']), 4),
            'total_return': round(float(best['total_ret']), 4),
            'win_rate': round(float(best['win_rate']), 4),
        },
        'walk_forward': {
            'n_folds': len(wf_results) if wf_results else 0,
            'folds': wf_results if wf_results else [],
            'mean_oos_sharpe': round(float(mean_oos), 3) if mean_oos != -99 else None,
            'positive_folds': n_pos_folds,
            'pct_positive_folds': round(wf_pct_positive, 1),
        },
        'split_half': split,
        'split_half_stability': round(float(stability), 3) if stability != -99 else None,
        'wf_split_half': {
            'h1_mean': round(float(wf_h1_mean), 3) if wf_h1_mean != -99 else None,
            'h2_mean': round(float(wf_h2_mean), 3) if wf_h2_mean != -99 else None,
        },
        'correlation_with_h053': corr_h053,
        'correlation_with_h012': corr_h012,
        'direction_breakdown': {
            d: {
                'pct_positive': round(float((df[df['direction']==d]['sharpe'] > 0).mean() * 100), 1),
                'mean_sharpe': round(float(df[df['direction']==d]['sharpe'].mean()), 3),
                'median_sharpe': round(float(df[df['direction']==d]['sharpe'].median()), 3),
            }
            for d in directions
        },
        'top_10_params': df.nlargest(10, 'sharpe').to_dict('records'),
        'criteria': {
            'is_pct_positive': {'value': round(pct_positive, 1), 'threshold': 80, 'pass': pct_positive >= 80},
            'wf_positive_folds': {'value': n_pos_folds, 'threshold': 4, 'pass': n_pos_folds >= 4},
            'wf_mean_oos': {'value': round(float(mean_oos), 3) if mean_oos != -99 else None, 'threshold': 0, 'pass': mean_oos > 0},
            'split_half_stability': {'value': round(float(stability), 3) if stability != -99 else None, 'threshold': 0, 'pass': stability > 0},
            'corr_h053': {'value': corr_h053, 'threshold': 0.6, 'pass': abs(corr_h053_val) < 0.6},
            'corr_h012': {'value': corr_h012, 'threshold': 0.6, 'pass': abs(corr_h012_val) < 0.6},
        },
    }

    results_path = RESULTS_DIR / "results.json"
    with open(results_path, 'w') as f:
        json.dump(results_json, f, indent=2, default=str)
    print(f"\nResults saved to {results_path}")

    return results_json


if __name__ == '__main__':
    main()
