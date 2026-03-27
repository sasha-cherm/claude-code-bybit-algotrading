"""
H-089: Funding Rate Momentum (Change in Funding Rate) — Cross-Sectional Factor

Hypothesis: Assets where funding rates are RISING (becoming more positive = more
longs piling in) will underperform, while assets where funding rates are FALLING
will outperform. This differs from H-053 (funding rate level) — this uses the
CHANGE in funding rate.

Signal: short_window_avg - long_window_avg of daily average funding rates.
Positive change = funding rising = crowded longs building up.
Contrarian direction: long assets with FALLING funding (most negative change),
short assets with RISING funding (most positive change).

Data: 8-hourly funding rates from Bybit, aggregated to daily avg, ~2yr history.
"""

import json
import os
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return, total_return

ASSETS = ['BTC', 'ETH', 'SOL', 'SUI', 'XRP', 'DOGE', 'AVAX', 'LINK',
          'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM']
DATA_DIR = ROOT / "data"
RESULTS_DIR = Path(__file__).resolve().parent

FEE_BPS = 5  # one-way fee in basis points (taker ~5bps on Bybit)


# ═══════════════════════════════════════════════════════════════════════
# Data Loading
# ═══════════════════════════════════════════════════════════════════════

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
        # Aggregate 8h rates to daily average
        daily = df['funding_rate'].resample('1D').mean()
        funding[asset] = daily

    panel = pd.DataFrame(funding).sort_index().dropna(how='all')
    print(f"Funding data: {len(panel)} days, {len(panel.columns)} assets")
    print(f"Date range: {panel.index[0].date()} to {panel.index[-1].date()}")
    return panel


def compute_funding_change(funding_panel, short_window, long_window):
    """
    Compute change in rolling average funding rate.
    Signal = short_window_avg - long_window_avg.
    Positive = funding is rising (more longs). Negative = funding is falling.
    """
    short_avg = funding_panel.rolling(short_window, min_periods=max(1, short_window // 2)).mean()
    long_avg = funding_panel.rolling(long_window, min_periods=max(1, long_window // 2)).mean()
    return short_avg - long_avg


# ═══════════════════════════════════════════════════════════════════════
# Backtest Engine
# ═══════════════════════════════════════════════════════════════════════

def backtest_xs_factor(closes, signals, rebal_days, n_long_short, fee_bps=FEE_BPS):
    """
    Backtest cross-sectional factor.
    CONTRARIAN: long assets with most NEGATIVE signal (falling funding),
                short assets with most POSITIVE signal (rising funding).
    Returns daily portfolio returns series.
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
            # Contrarian: long the LOWEST (most negative change = falling funding)
            new_longs = ranked.index[:n_long_short].tolist()
            # Short the HIGHEST (most positive change = rising funding)
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


# ═══════════════════════════════════════════════════════════════════════
# Walk-Forward Validation
# ═══════════════════════════════════════════════════════════════════════

def walk_forward_test(closes, funding, short_w, long_w, rebal_days, n_long_short,
                      n_folds=6, train_days=180, test_days=90):
    """
    Rolling walk-forward: train_days train, test_days test, rolling.
    Uses fixed signal params, just tests on OOS windows.
    """
    signals = compute_funding_change(funding, short_w, long_w)
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

        # Run on test period
        test_closes = closes.loc[test_start:test_end]
        test_signals = signals.loc[:test_end]

        rets = backtest_xs_factor(test_closes, test_signals, rebal_days, n_long_short)
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


# ═══════════════════════════════════════════════════════════════════════
# Split-Half Validation
# ═══════════════════════════════════════════════════════════════════════

def split_half_test(closes, funding, short_w, long_w, rebal_days, n_long_short):
    """Test on first half vs second half of data."""
    signals = compute_funding_change(funding, short_w, long_w)
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
        rets = backtest_xs_factor(sub_closes, sub_signals, rebal_days, n_long_short)
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


# ═══════════════════════════════════════════════════════════════════════
# Correlation with H-012 (60d momentum)
# ═══════════════════════════════════════════════════════════════════════

def compute_h012_returns(closes, lookback=60, rebal=5, n_long=4):
    """Compute H-012 XSMom returns for correlation analysis."""
    mom = closes.pct_change(lookback)
    # Long top momentum, short bottom momentum
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


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("H-089: Funding Rate Momentum (Change in Funding Rate)")
    print("Cross-Sectional Factor Backtest")
    print("=" * 70)

    # ── Load Data ─────────────────────────────────────────────────────
    print("\nLoading data...")
    closes = load_daily_closes()
    funding = load_funding_rates()

    # Align dates
    common_dates = closes.index.intersection(funding.index)
    closes = closes.loc[common_dates]
    funding = funding.loc[common_dates]
    print(f"Aligned: {len(common_dates)} days, {closes.shape[1]} assets")
    print(f"Date range: {common_dates[0].date()} to {common_dates[-1].date()}")

    # Quick data summary
    print(f"\nFunding rate summary (daily avg, annualized %):")
    ann = funding.mean() * 3 * 365 * 100
    for asset in ASSETS:
        if asset in ann.index:
            print(f"  {asset:>5}: {ann[asset]:+.2f}%")

    # Cross-sectional dispersion
    xs_std = funding.std(axis=1).mean()
    print(f"\nCross-sectional std of daily funding: {xs_std:.6f}")

    # ── Parameter Grid Search ─────────────────────────────────────────
    short_windows = [3, 5, 7]
    long_windows = [14, 21, 30]
    rebal_list = [3, 5, 7, 10]
    n_list = [3, 4, 5]

    total_combos = len(short_windows) * len(long_windows) * len(rebal_list) * len(n_list)
    print(f"\n{'='*70}")
    print(f"PARAMETER GRID SEARCH: {total_combos} combinations")
    print(f"Short windows: {short_windows}")
    print(f"Long windows: {long_windows}")
    print(f"Rebalance days: {rebal_list}")
    print(f"N long/short: {n_list}")
    print(f"{'='*70}")

    results = []
    for sw, lw, rd, n in product(short_windows, long_windows, rebal_list, n_list):
        signal = compute_funding_change(funding, sw, lw)
        rets = backtest_xs_factor(closes, signal, rd, n)

        if len(rets) < 30:
            continue

        eq = 10000 * (1 + rets).cumprod()
        sr = sharpe_ratio(rets, periods_per_year=365)
        ar = annual_return(eq, periods_per_year=365)
        dd = max_drawdown(eq)
        tr = total_return(eq)

        results.append({
            'short_w': sw, 'long_w': lw, 'rebal': rd, 'n': n,
            'sharpe': round(sr, 3),
            'annual_ret': round(ar, 4),
            'total_ret': round(tr, 4),
            'max_dd': round(dd, 4),
            'days': len(rets),
        })

    df = pd.DataFrame(results)

    # ── Parameter Robustness Summary ──────────────────────────────────
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

    # Top 15
    print(f"\nTop 15 by Sharpe:")
    top = df.nlargest(15, 'sharpe')
    for _, r in top.iterrows():
        print(f"  SW{r['short_w']:>2} LW{r['long_w']:>2} R{r['rebal']:>2} N{r['n']}: "
              f"Sharpe {r['sharpe']:+.3f}, Ann {r['annual_ret']*100:+.1f}%, "
              f"DD {r['max_dd']*100:.1f}%, Total {r['total_ret']*100:+.1f}%")

    # Bottom 5
    print(f"\nBottom 5 by Sharpe:")
    bottom = df.nsmallest(5, 'sharpe')
    for _, r in bottom.iterrows():
        print(f"  SW{r['short_w']:>2} LW{r['long_w']:>2} R{r['rebal']:>2} N{r['n']}: "
              f"Sharpe {r['sharpe']:+.3f}, Ann {r['annual_ret']*100:+.1f}%, "
              f"DD {r['max_dd']*100:.1f}%")

    # ── Best Params Full Analysis ─────────────────────────────────────
    best = df.nlargest(1, 'sharpe').iloc[0]
    best_sw = int(best['short_w'])
    best_lw = int(best['long_w'])
    best_rd = int(best['rebal'])
    best_n = int(best['n'])

    print(f"\n{'='*70}")
    print(f"BEST PARAMS: SW={best_sw} LW={best_lw} R={best_rd} N={best_n}")
    print(f"  Sharpe:     {best['sharpe']:.3f}")
    print(f"  Annual Ret: {best['annual_ret']*100:+.2f}%")
    print(f"  Max DD:     {best['max_dd']*100:.2f}%")
    print(f"  Total Ret:  {best['total_ret']*100:+.2f}%")
    print(f"  Days:       {int(best['days'])}")
    print(f"{'='*70}")

    # ── Fee Sensitivity ───────────────────────────────────────────────
    print(f"\nFee sensitivity (best params):")
    for fee_mult in [1, 2, 3, 5]:
        signal = compute_funding_change(funding, best_sw, best_lw)
        rets = backtest_xs_factor(closes, signal, best_rd, best_n,
                                  fee_bps=FEE_BPS * fee_mult)
        sr = sharpe_ratio(rets, periods_per_year=365)
        print(f"  {fee_mult}x fees ({FEE_BPS*fee_mult}bps): Sharpe {sr:.3f}")

    # ── Walk-Forward Validation ───────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"WALK-FORWARD VALIDATION (6 folds, 180d train, 90d test)")
    print(f"{'='*70}")

    wf_results = walk_forward_test(closes, funding, best_sw, best_lw,
                                    best_rd, best_n,
                                    n_folds=6, train_days=180, test_days=90)
    if wf_results:
        for fold_r in wf_results:
            print(f"  Fold {fold_r['fold']}: {fold_r['start']} to {fold_r['end']} — "
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
        print(f"  IS/OOS ratio:      {mean_oos/best['sharpe']:.2f}" if best['sharpe'] != 0 else "")
    else:
        print("  Insufficient data for walk-forward")

    # Also test top 3 param sets
    print(f"\nWalk-forward for top 3 param sets:")
    top3 = df.nlargest(3, 'sharpe')
    for idx, (_, r) in enumerate(top3.iterrows()):
        sw, lw, rd, n = int(r['short_w']), int(r['long_w']), int(r['rebal']), int(r['n'])
        wf = walk_forward_test(closes, funding, sw, lw, rd, n)
        if wf:
            wf_s = [f['sharpe'] for f in wf]
            n_pos = sum(1 for s in wf_s if s > 0)
            print(f"  #{idx+1} SW{sw} LW{lw} R{rd} N{n}: IS={r['sharpe']:.3f}, "
                  f"OOS mean={np.mean(wf_s):.3f}, {n_pos}/{len(wf)} positive folds")

    # ── Split-Half Validation ─────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"SPLIT-HALF VALIDATION (best params)")
    print(f"{'='*70}")

    split = split_half_test(closes, funding, best_sw, best_lw, best_rd, best_n)
    for label, stats in split.items():
        print(f"  {label}: Sharpe {stats['sharpe']:+.3f}, "
              f"Ann {stats['annual_ret']*100:+.1f}%, DD {stats['max_dd']*100:.1f}% "
              f"({stats['start']} to {stats['end']}, {stats['days']} days)")

    if 'first_half' in split and 'second_half' in split:
        s1 = split['first_half']['sharpe']
        s2 = split['second_half']['sharpe']
        print(f"  Sharpe difference: {abs(s1 - s2):.3f}")
        both_positive = s1 > 0 and s2 > 0
        print(f"  Both halves positive: {'YES' if both_positive else 'NO'}")

    # ── Correlation with H-012 (60d Momentum) ────────────────────────
    print(f"\n{'='*70}")
    print(f"CORRELATION WITH H-012 (60d XS Momentum)")
    print(f"{'='*70}")

    h089_signal = compute_funding_change(funding, best_sw, best_lw)
    h089_rets = backtest_xs_factor(closes, h089_signal, best_rd, best_n)
    h012_rets = compute_h012_returns(closes, lookback=60, rebal=5, n_long=4)

    common = h089_rets.index.intersection(h012_rets.index)
    # Filter to non-zero entries only for meaningful correlation
    h089_common = h089_rets.loc[common]
    h012_common = h012_rets.loc[common]
    mask = (h089_common != 0) | (h012_common != 0)
    h089_filtered = h089_common[mask]
    h012_filtered = h012_common[mask]

    if len(h089_filtered) > 30:
        corr = h089_filtered.corr(h012_filtered)
        print(f"  Daily return correlation: {corr:.3f}")
        print(f"  ({len(h089_filtered)} overlapping trading days)")

        # Rolling correlation
        rolling_corr = h089_common.rolling(60).corr(h012_common).dropna()
        if len(rolling_corr) > 0:
            print(f"  60-day rolling correlation: mean={rolling_corr.mean():.3f}, "
                  f"std={rolling_corr.std():.3f}")
    else:
        corr = None
        print("  Insufficient overlapping data for correlation")

    # Also check signal-level correlation
    mom60 = closes.pct_change(60)
    # Rank correlation between funding change and momentum across assets
    rank_corrs = []
    for date in common:
        if date in h089_signal.index and date in mom60.index:
            fc = h089_signal.loc[date].dropna()
            m = mom60.loc[date].dropna()
            common_assets = fc.index.intersection(m.index)
            if len(common_assets) >= 8:
                rc = fc[common_assets].corr(m[common_assets])
                if not np.isnan(rc):
                    rank_corrs.append(rc)
    if rank_corrs:
        print(f"\n  Signal-level correlation (funding change vs 60d momentum):")
        print(f"    Mean XS corr: {np.mean(rank_corrs):.3f}")
        print(f"    Std XS corr:  {np.std(rank_corrs):.3f}")
        print(f"    % days positive: {sum(1 for r in rank_corrs if r > 0)/len(rank_corrs)*100:.0f}%")

    # ── VERDICT ───────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"VERDICT")
    print(f"{'='*70}")

    # Determine verdict based on multiple criteria
    criteria = {
        'pct_positive': pct_positive,
        'mean_sharpe': df['sharpe'].mean(),
        'best_sharpe': best['sharpe'],
        'wf_mean_sharpe': np.mean([f['sharpe'] for f in wf_results]) if wf_results else -99,
        'wf_pct_positive': (sum(1 for f in wf_results if f['sharpe'] > 0) / len(wf_results) * 100) if wf_results else 0,
        'split_both_positive': (split.get('first_half', {}).get('sharpe', -1) > 0 and
                                split.get('second_half', {}).get('sharpe', -1) > 0),
        'corr_with_mom': corr if corr is not None else 0,
    }

    print(f"\n  Param robustness:   {pct_positive:.0f}% positive (need >60%)")
    print(f"  Mean Sharpe:        {criteria['mean_sharpe']:.3f} (need >0.3)")
    print(f"  Best IS Sharpe:     {criteria['best_sharpe']:.3f}")
    print(f"  WF mean OOS Sharpe: {criteria['wf_mean_sharpe']:.3f} (need >0.2)")
    print(f"  WF positive folds:  {criteria['wf_pct_positive']:.0f}%")
    print(f"  Split-half stable:  {'YES' if criteria['split_both_positive'] else 'NO'}")
    print(f"  Corr with H-012:    {criteria['corr_with_mom']:.3f} (want <0.3)")

    if (pct_positive >= 70 and criteria['mean_sharpe'] > 0.5 and
            criteria['wf_mean_sharpe'] > 0.3 and criteria['wf_pct_positive'] >= 50 and
            criteria['split_both_positive']):
        verdict = "CONFIRMED"
        print(f"\n  >>> CONFIRMED: Strong factor with robust OOS performance")
    elif (pct_positive >= 55 and criteria['mean_sharpe'] > 0.2 and
            criteria['wf_mean_sharpe'] > 0.0):
        verdict = "CONDITIONAL"
        reasons = []
        if criteria['wf_pct_positive'] < 50:
            reasons.append("WF consistency weak")
        if not criteria['split_both_positive']:
            reasons.append("split-half unstable")
        if abs(criteria['corr_with_mom']) > 0.3:
            reasons.append(f"correlated with H-012 ({criteria['corr_with_mom']:.2f})")
        print(f"\n  >>> CONDITIONAL: Promising but has concerns: {', '.join(reasons) if reasons else 'marginal'}")
    else:
        verdict = "REJECTED"
        reasons = []
        if pct_positive < 55:
            reasons.append(f"only {pct_positive:.0f}% positive params")
        if criteria['mean_sharpe'] <= 0.2:
            reasons.append(f"low mean Sharpe ({criteria['mean_sharpe']:.3f})")
        if criteria['wf_mean_sharpe'] <= 0:
            reasons.append(f"negative OOS Sharpe ({criteria['wf_mean_sharpe']:.3f})")
        print(f"\n  >>> REJECTED: {'; '.join(reasons)}")

    # ── Save Results ──────────────────────────────────────────────────
    results_json = {
        'hypothesis': 'H-089',
        'name': 'Funding Rate Momentum (Change in Funding Rate)',
        'verdict': verdict,
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
            'short_window': best_sw,
            'long_window': best_lw,
            'rebalance_days': best_rd,
            'n_long_short': best_n,
            'sharpe': round(float(best['sharpe']), 3),
            'annual_return': round(float(best['annual_ret']), 4),
            'max_drawdown': round(float(best['max_dd']), 4),
            'total_return': round(float(best['total_ret']), 4),
        },
        'walk_forward': {
            'n_folds': len(wf_results) if wf_results else 0,
            'folds': wf_results if wf_results else [],
            'mean_oos_sharpe': round(float(np.mean([f['sharpe'] for f in wf_results])), 3) if wf_results else None,
            'pct_positive_folds': round(criteria['wf_pct_positive'], 1),
        },
        'split_half': split,
        'correlation_with_h012': round(float(corr), 3) if corr is not None else None,
        'top_10_params': df.nlargest(10, 'sharpe').to_dict('records'),
    }

    results_path = RESULTS_DIR / "results.json"
    with open(results_path, 'w') as f:
        json.dump(results_json, f, indent=2, default=str)
    print(f"\nResults saved to {results_path}")

    return results_json


if __name__ == '__main__':
    main()
