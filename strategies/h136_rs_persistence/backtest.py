"""
H-136: Relative Strength Persistence Factor (Cross-Sectional)

Instead of measuring total return (momentum), we measure the *fraction of days*
each asset beat the cross-sectional average return over a rolling window.

  win_rate = count(asset_ret > xs_avg_ret) / lookback_days

An asset with an 80% win-rate vs peers is more consistently strong than one
with a spike-driven 60% win-rate — this captures "quality of momentum".

Ranks assets by persistence metric:
  - Long top-N (most consistently outperforming the cross-sectional average)
  - Short bottom-N (most consistently underperforming)

Validation:
  - Full parameter grid scan (windows x rebal x n_positions)
  - 70/30 train/test split
  - Split-half stability
  - Walk-forward OOS: 6 folds, 90-day test windows
  - Correlation with H-012 (momentum)
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.0006
INITIAL_CAPITAL = 10_000.0

LOOKBACKS = [10, 20, 30, 40, 60]
REBAL_FREQS = [3, 5, 7]
N_LONGS = [3, 4, 5]

WF_FOLDS = 6
WF_TRAIN = 120
WF_TEST = 90
WF_STEP = 90


def load_daily_data():
    data_dir = ROOT / "data"
    daily = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if len(df) >= 200:
                daily[sym] = df
                print(f"  {sym}: {len(df)} daily bars "
                      f"({df.index[0].date()} to {df.index[-1].date()})")
        else:
            print(f"  {sym}: missing cache file, fetching...")
            try:
                from lib.data_fetch import fetch_and_cache
                df = fetch_and_cache(sym, "1d", limit_days=730)
                if len(df) >= 200:
                    daily[sym] = df
                    print(f"    => {len(df)} bars fetched")
                else:
                    print(f"    => only {len(df)} bars, skipping")
            except Exception as e:
                print(f"    => fetch failed: {e}")
    return daily


def compute_rs_persistence(daily, lookback):
    """
    For each asset and each day, compute the fraction of the past `lookback` days
    where that asset's return exceeded the cross-sectional average return.

    This is the "win-rate vs peers" metric.
    """
    syms = list(daily.keys())
    # Build aligned daily return DataFrame
    rets = pd.DataFrame({sym: daily[sym]['close'].pct_change() for sym in syms})

    # Cross-sectional average return each day
    xs_avg = rets.mean(axis=1)

    # Beat indicator: did asset beat the cross-sectional average?
    beat = rets.sub(xs_avg, axis=0) > 0
    beat = beat.astype(float)

    # Rolling win-rate
    persistence = beat.rolling(lookback).mean()
    return persistence


def compute_momentum_signal(daily, lookback=60):
    """H-012 momentum: rolling sum of daily returns over lookback."""
    syms = list(daily.keys())
    rets = pd.DataFrame({sym: daily[sym]['close'].pct_change() for sym in syms})
    return rets.rolling(lookback).sum()


def run_backtest(daily, lookback, rebal_freq, n_positions, start_idx=None, end_idx=None):
    syms = list(daily.keys())
    signal_df = compute_rs_persistence(daily, lookback)

    all_dates = signal_df.dropna(how='all').index

    if start_idx is not None:
        all_dates = all_dates[start_idx:end_idx]

    if len(all_dates) < rebal_freq + 1:
        return None

    close_df = pd.DataFrame({sym: daily[sym]['close'] for sym in syms})
    close_df = close_df.reindex(all_dates)
    ret_df = close_df.pct_change()

    capital = INITIAL_CAPITAL
    equity_curve = []
    daily_returns = []
    positions = {}
    days_since_rebal = rebal_freq  # trigger rebalance on first available day

    for i, date in enumerate(all_dates):
        if i == 0:
            equity_curve.append(capital)
            continue

        # Mark-to-market current positions
        port_ret = 0.0
        if positions:
            for sym, weight in positions.items():
                r = ret_df.loc[date, sym] if sym in ret_df.columns and pd.notna(ret_df.loc[date, sym]) else 0.0
                port_ret += weight * r

        capital *= (1 + port_ret)
        daily_returns.append(port_ret)
        equity_curve.append(capital)

        days_since_rebal += 1

        if days_since_rebal >= rebal_freq:
            prev_date = all_dates[i - 1] if i > 0 else date
            signals = signal_df.loc[prev_date].dropna()

            if len(signals) >= 2 * n_positions:
                ranked = signals.sort_values()  # low persistence first

                # Long most persistent (high win-rate vs peers)
                longs = ranked.index[-n_positions:].tolist()
                # Short least persistent (low win-rate vs peers)
                shorts = ranked.index[:n_positions].tolist()

                w = 1.0 / (2 * n_positions)
                new_positions = {}
                for sym in longs:
                    new_positions[sym] = w
                for sym in shorts:
                    new_positions[sym] = -w

                # Compute turnover for fee calculation
                old_syms = set(positions.keys())
                new_syms = set(new_positions.keys())
                changed = old_syms.symmetric_difference(new_syms)
                for sym in old_syms.intersection(new_syms):
                    if abs(positions.get(sym, 0) - new_positions.get(sym, 0)) > 1e-6:
                        changed.add(sym)

                fee_cost = len(changed) * 2 * FEE_RATE * w
                capital *= (1 - fee_cost)

                positions = new_positions
                days_since_rebal = 0

    if len(daily_returns) < 30:
        return None

    daily_returns = np.array(daily_returns)
    equity_curve = np.array(equity_curve)

    sharpe_val = np.mean(daily_returns) / (np.std(daily_returns) + 1e-10) * np.sqrt(365)
    ann_ret = (equity_curve[-1] / equity_curve[0]) ** (365 / len(daily_returns)) - 1
    mdd = max_drawdown(pd.Series(equity_curve))

    return {
        'sharpe': sharpe_val,
        'annual_return': ann_ret,
        'max_drawdown': mdd,
        'total_return': equity_curve[-1] / equity_curve[0] - 1,
        'n_days': len(daily_returns),
        'daily_returns': daily_returns,
        'equity_curve': equity_curve,
    }


def main():
    print("=" * 70)
    print("H-136: Relative Strength Persistence Factor Backtest")
    print("=" * 70)

    print("\nLoading daily data...")
    daily = load_daily_data()
    if len(daily) < 10:
        print(f"ERROR: Only {len(daily)} assets loaded (need >=10). Aborting.")
        return

    print(f"\nAssets loaded: {len(daily)}")

    # Align to common date range
    common_start = max(df.index[0] for df in daily.values())
    common_end = min(df.index[-1] for df in daily.values())
    total_days = (common_end - common_start).days
    print(f"Common range: {common_start.date()} to {common_end.date()} ({total_days} days / {total_days/365:.1f} years)")

    for sym in list(daily.keys()):
        daily[sym] = daily[sym].loc[common_start:common_end]

    # Quick signal preview
    print("\n--- Signal Preview (last 5 days, 30-day window) ---")
    pers_preview = compute_rs_persistence(daily, 30)
    print(pers_preview.dropna(how='all').tail(5).round(3).to_string())

    # =========================================================
    # Phase 1: Full Parameter Grid Scan
    # =========================================================
    print("\n--- Phase 1: Full Parameter Grid Scan ---")
    print(f"Grid: {len(LOOKBACKS)} lookbacks x {len(REBAL_FREQS)} rebals x {len(N_LONGS)} n_pos = "
          f"{len(LOOKBACKS)*len(REBAL_FREQS)*len(N_LONGS)} combinations")

    all_results = []
    for L, R, N in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        res = run_backtest(daily, L, R, N)
        if res:
            all_results.append({
                'lookback': L, 'rebal': R, 'n_pos': N,
                'sharpe': res['sharpe'],
                'annual_return': res['annual_return'],
                'max_drawdown': res['max_drawdown'],
                'total_return': res['total_return'],
                'n_days': res['n_days'],
            })

    df_res = pd.DataFrame(all_results)
    n_positive = (df_res['sharpe'] > 0).sum()
    total_params = len(df_res)
    pct_positive = 100 * n_positive / total_params

    print(f"\nParameter combinations evaluated: {total_params}")
    print(f"Positive Sharpe: {n_positive}/{total_params} ({pct_positive:.1f}%)")
    print(f"Mean Sharpe: {df_res['sharpe'].mean():.3f}")
    print(f"Median Sharpe: {df_res['sharpe'].median():.3f}")
    print(f"Sharpe std: {df_res['sharpe'].std():.3f}")
    print(f"Best Sharpe: {df_res['sharpe'].max():.3f}")
    print(f"Worst Sharpe: {df_res['sharpe'].min():.3f}")

    print("\n--- Breakdown by lookback ---")
    for L in LOOKBACKS:
        sub = df_res[df_res['lookback'] == L]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  L={L:3d}: {pos}/{len(sub)} positive, mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"mean return {sub['annual_return'].mean()*100:.1f}%")

    print("\n--- Breakdown by rebal freq ---")
    for R in REBAL_FREQS:
        sub = df_res[df_res['rebal'] == R]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  R={R}: {pos}/{len(sub)} positive, mean Sharpe {sub['sharpe'].mean():.3f}")

    print("\n--- Breakdown by n_positions ---")
    for N in N_LONGS:
        sub = df_res[df_res['n_pos'] == N]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  N={N}: {pos}/{len(sub)} positive, mean Sharpe {sub['sharpe'].mean():.3f}")

    print("\n--- Top 10 parameter sets ---")
    top10 = df_res.nlargest(10, 'sharpe')
    for _, row in top10.iterrows():
        print(f"  L={int(row['lookback']):3d} R={int(row['rebal'])} N={int(row['n_pos'])} "
              f"Sharpe={row['sharpe']:.3f} Return={row['annual_return']*100:.1f}% DD={row['max_drawdown']*100:.1f}%")

    best = df_res.loc[df_res['sharpe'].idxmax()]
    best_L = int(best['lookback'])
    best_R = int(best['rebal'])
    best_N = int(best['n_pos'])

    print(f"\nBest params: L={best_L}, R={best_R}, N={best_N} → "
          f"Sharpe {best['sharpe']:.3f}, Return {best['annual_return']*100:.1f}%, DD {best['max_drawdown']*100:.1f}%")

    # =========================================================
    # Phase 2: Train/Test Split (70/30)
    # =========================================================
    print("\n--- Phase 2: Train/Test Split (70/30) ---")
    signal_full = compute_rs_persistence(daily, best_L)
    valid_dates = signal_full.dropna(how='all').index
    n_valid = len(valid_dates)
    split_idx = int(n_valid * 0.7)

    train_res = run_backtest(daily, best_L, best_R, best_N, end_idx=split_idx)
    test_res = run_backtest(daily, best_L, best_R, best_N, start_idx=split_idx)

    if train_res:
        print(f"Train (first 70%): Sharpe {train_res['sharpe']:.3f}, "
              f"Return {train_res['annual_return']*100:.1f}%, DD {train_res['max_drawdown']*100:.1f}%")
    if test_res:
        print(f"Test  (last  30%): Sharpe {test_res['sharpe']:.3f}, "
              f"Return {test_res['annual_return']*100:.1f}%, DD {test_res['max_drawdown']*100:.1f}%")

    # =========================================================
    # Phase 3: Split-Half Stability
    # =========================================================
    print("\n--- Phase 3: Split-Half Stability ---")
    mid_idx = n_valid // 2
    h1_res = run_backtest(daily, best_L, best_R, best_N, end_idx=mid_idx)
    h2_res = run_backtest(daily, best_L, best_R, best_N, start_idx=mid_idx)

    split_half_ratio = 0.0
    if h1_res and h2_res:
        print(f"First half:  Sharpe {h1_res['sharpe']:.3f}, Return {h1_res['annual_return']*100:.1f}%")
        print(f"Second half: Sharpe {h2_res['sharpe']:.3f}, Return {h2_res['annual_return']*100:.1f}%")
        denom = max(abs(h1_res['sharpe']), abs(h2_res['sharpe']))
        split_half_ratio = min(h1_res['sharpe'], h2_res['sharpe']) / denom if denom > 0 else 0
        print(f"Split-half ratio (min/max): {split_half_ratio:.3f}")

    # =========================================================
    # Phase 4: Walk-Forward OOS (6 folds, IS param selection)
    # =========================================================
    print("\n--- Phase 4: Walk-Forward OOS (6 folds, 90-day test) ---")
    wf_results = []
    for fold in range(WF_FOLDS):
        train_start = fold * WF_STEP
        train_end = train_start + WF_TRAIN
        test_start = train_end
        test_end = test_start + WF_TEST

        if test_end > n_valid:
            print(f"  Fold {fold}: not enough data, stopping")
            break

        best_is_sharpe = -999
        best_is_params = None
        for L, R, N in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
            res = run_backtest(daily, L, R, N, start_idx=train_start, end_idx=train_end)
            if res and res['sharpe'] > best_is_sharpe:
                best_is_sharpe = res['sharpe']
                best_is_params = (L, R, N)

        if best_is_params:
            oos_res = run_backtest(daily, *best_is_params, start_idx=test_start, end_idx=test_end)
            if oos_res:
                wf_results.append({
                    'fold': fold,
                    'is_sharpe': float(best_is_sharpe),
                    'oos_sharpe': float(oos_res['sharpe']),
                    'oos_return': float(oos_res['annual_return']),
                    'params': {'L': best_is_params[0], 'R': best_is_params[1], 'N': best_is_params[2]},
                })
                print(f"  Fold {fold}: IS={best_is_sharpe:.3f} → OOS={oos_res['sharpe']:.3f} "
                      f"(ret={oos_res['annual_return']*100:.1f}%) "
                      f"[L={best_is_params[0]}, R={best_is_params[1]}, N={best_is_params[2]}]")

    wf_pos = 0
    wf_mean_oos = 0.0
    if wf_results:
        wf_pos = sum(1 for w in wf_results if w['oos_sharpe'] > 0)
        wf_mean_oos = float(np.mean([w['oos_sharpe'] for w in wf_results]))
        print(f"\nWF summary: {wf_pos}/{len(wf_results)} positive OOS folds, mean OOS Sharpe {wf_mean_oos:.3f}")

    # =========================================================
    # Phase 5: Correlation with H-012 (Momentum)
    # =========================================================
    print("\n--- Phase 5: Correlation with H-012 (Momentum, 60d) ---")
    mom_signal = compute_momentum_signal(daily, 60)
    pers_signal = compute_rs_persistence(daily, best_L)

    common_idx = pers_signal.dropna(how='all').index.intersection(
        mom_signal.dropna(how='all').index
    )

    avg_corr = 0.0
    if len(common_idx) > 100:
        pers_ranks = pers_signal.loc[common_idx].rank(axis=1)
        mom_ranks = mom_signal.loc[common_idx].rank(axis=1)

        correlations = []
        for date in common_idx[::5]:
            pr = pers_ranks.loc[date].dropna()
            mr = mom_ranks.loc[date].dropna()
            common_cols = pr.index.intersection(mr.index)
            if len(common_cols) >= 8:
                correlations.append(pr[common_cols].corr(mr[common_cols]))

        if correlations:
            avg_corr = float(np.nanmean(correlations))
            corr_std = float(np.nanstd(correlations))
            print(f"Average rank correlation with H-012 (momentum): {avg_corr:.3f} ± {corr_std:.3f}")
            print(f"  (based on {len(correlations)} cross-sections, sampled every 5 days)")
        else:
            print("Could not compute cross-sectional correlation.")
    else:
        print(f"Not enough common dates ({len(common_idx)}) for correlation.")

    # =========================================================
    # Phase 6: Median-param robustness (avoid cherry-picking best)
    # =========================================================
    print("\n--- Phase 6: Median-Param Robustness ---")
    median_sharpe_row = df_res.iloc[(df_res['sharpe'] - df_res['sharpe'].median()).abs().argsort()[:1]]
    m_row = median_sharpe_row.iloc[0]
    print(f"Median param set: L={int(m_row['lookback'])}, R={int(m_row['rebal'])}, N={int(m_row['n_pos'])} "
          f"→ Sharpe {m_row['sharpe']:.3f}, Return {m_row['annual_return']*100:.1f}%")

    # =========================================================
    # Summary
    # =========================================================
    print("\n" + "=" * 70)
    print("H-136 FINAL SUMMARY")
    print("=" * 70)
    print(f"Assets:         {len(daily)}")
    print(f"Data range:     {common_start.date()} to {common_end.date()} ({total_days} days)")
    print(f"IS params (best): L={best_L}, R={best_R}, N={best_N}")
    print(f"IS Sharpe:      {best['sharpe']:.3f}")
    print(f"IS Return:      {best['annual_return']*100:.1f}%")
    print(f"IS MaxDD:       {best['max_drawdown']*100:.1f}%")
    print(f"% params positive Sharpe: {pct_positive:.1f}%")
    if test_res:
        print(f"OOS Sharpe (30%): {test_res['sharpe']:.3f}")
        print(f"OOS Return:       {test_res['annual_return']*100:.1f}%")
    if h1_res and h2_res:
        print(f"Split-half:     H1={h1_res['sharpe']:.3f}, H2={h2_res['sharpe']:.3f}, ratio={split_half_ratio:.3f}")
    if wf_results:
        print(f"Walk-forward:   {wf_pos}/{len(wf_results)} positive, mean OOS Sharpe {wf_mean_oos:.3f}")
    print(f"Corr with H-012: {avg_corr:.3f}")

    # =========================================================
    # Save Results
    # =========================================================
    results = {
        'hypothesis': 'H-136',
        'name': 'Relative Strength Persistence Factor',
        'description': 'Win-rate of asset vs cross-sectional average over rolling window',
        'assets': list(daily.keys()),
        'n_assets': len(daily),
        'data_start': str(common_start.date()),
        'data_end': str(common_end.date()),
        'total_days': total_days,
        'params_grid': {
            'lookbacks': LOOKBACKS,
            'rebal_freqs': REBAL_FREQS,
            'n_positions': N_LONGS,
        },
        'is_stats': {
            'total_combinations': total_params,
            'positive_sharpe_pct': round(pct_positive, 2),
            'mean_sharpe': round(float(df_res['sharpe'].mean()), 4),
            'median_sharpe': round(float(df_res['sharpe'].median()), 4),
            'best_sharpe': round(float(df_res['sharpe'].max()), 4),
            'worst_sharpe': round(float(df_res['sharpe'].min()), 4),
        },
        'best_params': {'lookback': best_L, 'rebal': best_R, 'n_pos': best_N},
        'best_is': {
            'sharpe': round(float(best['sharpe']), 4),
            'annual_return': round(float(best['annual_return']), 4),
            'max_drawdown': round(float(best['max_drawdown']), 4),
        },
        'train_test_70_30': {
            'train_sharpe': round(float(train_res['sharpe']), 4) if train_res else None,
            'test_sharpe': round(float(test_res['sharpe']), 4) if test_res else None,
            'train_return': round(float(train_res['annual_return']), 4) if train_res else None,
            'test_return': round(float(test_res['annual_return']), 4) if test_res else None,
        },
        'split_half': {
            'h1_sharpe': round(float(h1_res['sharpe']), 4) if h1_res else None,
            'h2_sharpe': round(float(h2_res['sharpe']), 4) if h2_res else None,
            'ratio': round(float(split_half_ratio), 4),
        },
        'walk_forward': {
            'n_folds': len(wf_results),
            'positive_folds': wf_pos,
            'mean_oos_sharpe': round(float(wf_mean_oos), 4),
            'folds': wf_results,
        },
        'corr_h012_momentum': round(float(avg_corr), 4),
        'median_param_set': {
            'lookback': int(m_row['lookback']),
            'rebal': int(m_row['rebal']),
            'n_pos': int(m_row['n_pos']),
            'sharpe': round(float(m_row['sharpe']), 4),
            'annual_return': round(float(m_row['annual_return']), 4),
        },
        'all_results': [
            {
                'lookback': int(r['lookback']), 'rebal': int(r['rebal']),
                'n_pos': int(r['n_pos']), 'sharpe': round(float(r['sharpe']), 4),
                'annual_return': round(float(r['annual_return']), 4),
                'max_drawdown': round(float(r['max_drawdown']), 4),
            }
            for _, r in df_res.iterrows()
        ],
    }

    out_dir = ROOT / 'strategies' / 'h136_rs_persistence'
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / 'results.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
