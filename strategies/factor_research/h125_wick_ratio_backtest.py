"""
H-125: Wick Ratio Factor (Cross-Sectional)

The wick ratio measures the proportion of a candle's range that is wicks
(shadows) vs body:
  wick_ratio = 1 - |close - open| / (high - low)

High wick ratio = indecision (long shadows relative to body)
Low wick ratio = conviction (body dominates the range)

Hypothesis: Coins showing high conviction (low wick ratio) over a lookback
period tend to continue their trends, while indecisive coins underperform.

Two directions tested:
  (a) conviction_long = long low-wick (conviction), short high-wick (indecision)
  (b) indecision_long = long high-wick, short low-wick

Validation:
  - Full parameter grid scan (L x R x N x Direction)
  - 70/30 train/test split
  - Split-half stability
  - Walk-forward: 6 folds, 120d train / 90d test
  - Walk-forward with in-sample parameter selection
  - Correlation with H-012 (momentum)
  - Sharpe computed at BOTH 8760 and 365 annualization
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

LOOKBACKS = [5, 10, 20, 30]
REBAL_FREQS = [3, 5, 7]
N_LONGS = [3, 4, 5]
DIRECTIONS = ["conviction_long", "indecision_long"]

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
    return daily


def compute_wick_ratio(daily, lookback):
    """Compute rolling average wick ratio for each asset."""
    wick_ratios = {}
    for sym, df in daily.items():
        candle_range = df['high'] - df['low']
        body = (df['close'] - df['open']).abs()
        # Avoid division by zero
        wr = 1 - body / candle_range.replace(0, np.nan)
        wr = wr.rolling(lookback).mean()
        wick_ratios[sym] = wr
    return pd.DataFrame(wick_ratios)


def compute_momentum_signal(daily, lookback=60):
    """Compute momentum signal for correlation analysis."""
    rets = {}
    for sym, df in daily.items():
        rets[sym] = df['close'].pct_change()
    ret_df = pd.DataFrame(rets)
    return ret_df.rolling(lookback).sum()


def run_backtest(daily, lookback, rebal_freq, n_positions, direction, start_idx=None, end_idx=None):
    """Run factor backtest with given parameters."""
    wick_df = compute_wick_ratio(daily, lookback)

    # Get common dates
    syms = list(daily.keys())
    all_dates = wick_df.dropna(how='all').index

    if start_idx is not None:
        all_dates = all_dates[start_idx:end_idx]

    if len(all_dates) < rebal_freq + 1:
        return None

    # Build close price df
    close_df = pd.DataFrame({sym: daily[sym]['close'] for sym in syms})
    close_df = close_df.reindex(all_dates)

    # Daily returns
    ret_df = close_df.pct_change()

    capital = INITIAL_CAPITAL
    equity_curve = []
    daily_returns = []
    positions = {}
    days_since_rebal = rebal_freq  # Force rebal on first day

    for i, date in enumerate(all_dates):
        if i == 0:
            equity_curve.append(capital)
            continue

        # Mark-to-market
        port_ret = 0.0
        if positions:
            for sym, weight in positions.items():
                r = ret_df.loc[date, sym] if sym in ret_df.columns and pd.notna(ret_df.loc[date, sym]) else 0.0
                port_ret += weight * r

        capital *= (1 + port_ret)
        daily_returns.append(port_ret)
        equity_curve.append(capital)

        days_since_rebal += 1

        # Rebalance
        if days_since_rebal >= rebal_freq:
            # Use t-1 signal (previous day's wick ratio)
            prev_date = all_dates[i-1] if i > 0 else date
            signals = wick_df.loc[prev_date].dropna()

            if len(signals) >= 2 * n_positions:
                ranked = signals.sort_values()

                if direction == "conviction_long":
                    # Low wick = conviction → long; High wick = indecision → short
                    longs = ranked.index[:n_positions].tolist()
                    shorts = ranked.index[-n_positions:].tolist()
                elif direction == "indecision_long":
                    longs = ranked.index[-n_positions:].tolist()
                    shorts = ranked.index[:n_positions].tolist()

                new_positions = {}
                w = 1.0 / (2 * n_positions)
                for sym in longs:
                    new_positions[sym] = w
                for sym in shorts:
                    new_positions[sym] = -w

                # Fee for turnover
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

    sharpe_daily = np.mean(daily_returns) / (np.std(daily_returns) + 1e-10) * np.sqrt(365)
    ann_ret = (equity_curve[-1] / equity_curve[0]) ** (365 / len(daily_returns)) - 1
    mdd = max_drawdown(pd.Series(equity_curve))

    return {
        'sharpe': sharpe_daily,
        'annual_return': ann_ret,
        'max_drawdown': mdd,
        'total_return': equity_curve[-1] / equity_curve[0] - 1,
        'n_days': len(daily_returns),
        'daily_returns': daily_returns,
        'equity_curve': equity_curve,
    }


def main():
    print("=" * 70)
    print("H-125: Wick Ratio Factor Backtest")
    print("=" * 70)

    daily = load_daily_data()
    if len(daily) < 10:
        print("Not enough assets. Aborting.")
        return

    # Common date range
    common_start = max(df.index[0] for df in daily.values())
    common_end = min(df.index[-1] for df in daily.values())
    total_days = (common_end - common_start).days
    print(f"\nCommon range: {common_start.date()} to {common_end.date()} ({total_days} days)")

    # Trim all data
    for sym in list(daily.keys()):
        daily[sym] = daily[sym].loc[common_start:common_end]

    # === 1. Full Parameter Grid ===
    print("\n--- Phase 1: Full Parameter Grid Scan ---")
    all_results = []
    for L, R, N, D in product(LOOKBACKS, REBAL_FREQS, N_LONGS, DIRECTIONS):
        res = run_backtest(daily, L, R, N, D)
        if res:
            all_results.append({
                'lookback': L, 'rebal': R, 'n_pos': N, 'direction': D,
                'sharpe': res['sharpe'], 'annual_return': res['annual_return'],
                'max_drawdown': res['max_drawdown'],
            })

    df_res = pd.DataFrame(all_results)
    n_positive = (df_res['sharpe'] > 0).sum()
    total_params = len(df_res)
    print(f"Parameter combinations: {total_params}")
    print(f"Positive Sharpe: {n_positive}/{total_params} ({100*n_positive/total_params:.1f}%)")
    print(f"Mean Sharpe: {df_res['sharpe'].mean():.3f}")
    print(f"Median Sharpe: {df_res['sharpe'].median():.3f}")

    # Best by direction
    for d in DIRECTIONS:
        sub = df_res[df_res['direction'] == d]
        pos = (sub['sharpe'] > 0).sum()
        print(f"  {d}: {pos}/{len(sub)} positive ({100*pos/len(sub):.1f}%), "
              f"mean Sharpe {sub['sharpe'].mean():.3f}")

    best = df_res.loc[df_res['sharpe'].idxmax()]
    print(f"\nBest: L={best['lookback']} R={best['rebal']} N={best['n_pos']} "
          f"D={best['direction']} → Sharpe {best['sharpe']:.3f}, "
          f"Return {best['annual_return']*100:.1f}%, DD {best['max_drawdown']*100:.1f}%")

    best_L = int(best['lookback'])
    best_R = int(best['rebal'])
    best_N = int(best['n_pos'])
    best_D = best['direction']

    # === 2. Train/Test Split (70/30) ===
    print("\n--- Phase 2: Train/Test Split (70/30) ---")
    split_idx = int(total_days * 0.7)

    train_res = run_backtest(daily, best_L, best_R, best_N, best_D, end_idx=split_idx)
    test_res = run_backtest(daily, best_L, best_R, best_N, best_D, start_idx=split_idx)

    if train_res and test_res:
        print(f"Train: Sharpe {train_res['sharpe']:.3f}, Return {train_res['annual_return']*100:.1f}%")
        print(f"Test:  Sharpe {test_res['sharpe']:.3f}, Return {test_res['annual_return']*100:.1f}%")

    # === 3. Split-Half Stability ===
    print("\n--- Phase 3: Split-Half Stability ---")
    mid = total_days // 2
    h1_res = run_backtest(daily, best_L, best_R, best_N, best_D, end_idx=mid)
    h2_res = run_backtest(daily, best_L, best_R, best_N, best_D, start_idx=mid)

    if h1_res and h2_res:
        print(f"H1: Sharpe {h1_res['sharpe']:.3f}")
        print(f"H2: Sharpe {h2_res['sharpe']:.3f}")
        split_half_ratio = min(h1_res['sharpe'], h2_res['sharpe']) / max(abs(h1_res['sharpe']), abs(h2_res['sharpe'])) if max(abs(h1_res['sharpe']), abs(h2_res['sharpe'])) > 0 else 0
        print(f"Split-half ratio: {split_half_ratio:.3f}")

    # === 4. Walk-Forward ===
    print("\n--- Phase 4: Walk-Forward (IS param selection) ---")
    wick_df = compute_wick_ratio(daily, best_L)
    all_dates = wick_df.dropna(how='all').index
    n_dates = len(all_dates)

    wf_results = []
    for fold in range(WF_FOLDS):
        train_start = fold * WF_STEP
        train_end = train_start + WF_TRAIN
        test_start = train_end
        test_end = test_start + WF_TEST

        if test_end > n_dates:
            break

        # Find best IS params
        best_is_sharpe = -999
        best_is_params = None
        for L, R, N, D in product(LOOKBACKS, REBAL_FREQS, N_LONGS, DIRECTIONS):
            res = run_backtest(daily, L, R, N, D, start_idx=train_start, end_idx=train_end)
            if res and res['sharpe'] > best_is_sharpe:
                best_is_sharpe = res['sharpe']
                best_is_params = (L, R, N, D)

        if best_is_params:
            oos_res = run_backtest(daily, *best_is_params, start_idx=test_start, end_idx=test_end)
            if oos_res:
                wf_results.append({
                    'fold': fold,
                    'is_sharpe': best_is_sharpe,
                    'oos_sharpe': oos_res['sharpe'],
                    'params': best_is_params,
                })
                print(f"  Fold {fold}: IS={best_is_sharpe:.3f} → OOS={oos_res['sharpe']:.3f} "
                      f"(L={best_is_params[0]}, R={best_is_params[1]}, N={best_is_params[2]}, D={best_is_params[3]})")

    if wf_results:
        wf_pos = sum(1 for w in wf_results if w['oos_sharpe'] > 0)
        wf_mean = np.mean([w['oos_sharpe'] for w in wf_results])
        print(f"\nWF OOS: {wf_pos}/{len(wf_results)} positive, mean OOS Sharpe {wf_mean:.3f}")

    # === 5. Correlation with H-012 ===
    print("\n--- Phase 5: Correlation with H-012 (Momentum) ---")
    full_res = run_backtest(daily, best_L, best_R, best_N, best_D)
    mom_signal = compute_momentum_signal(daily, 60)

    if full_res:
        wick_signal = compute_wick_ratio(daily, best_L)
        # Compute rank correlation between wick ratio ranks and momentum ranks
        common_idx = wick_signal.dropna(how='all').index.intersection(mom_signal.dropna(how='all').index)
        if len(common_idx) > 100:
            wick_ranks = wick_signal.loc[common_idx].rank(axis=1)
            mom_ranks = mom_signal.loc[common_idx].rank(axis=1)

            correlations = []
            for date in common_idx[::5]:  # Sample every 5 days
                wr = wick_ranks.loc[date].dropna()
                mr = mom_ranks.loc[date].dropna()
                common = wr.index.intersection(mr.index)
                if len(common) >= 8:
                    correlations.append(wr[common].corr(mr[common]))

            if correlations:
                avg_corr = np.nanmean(correlations)
                print(f"Average rank correlation with H-012: {avg_corr:.3f}")

    # === Summary ===
    print("\n" + "=" * 70)
    print("H-125 SUMMARY")
    print("=" * 70)
    print(f"IS positive: {n_positive}/{total_params} ({100*n_positive/total_params:.1f}%)")
    print(f"Best params: L={best_L}, R={best_R}, N={best_N}, D={best_D}")
    print(f"Best IS Sharpe: {best['sharpe']:.3f}")
    if train_res and test_res:
        print(f"OOS Sharpe: {test_res['sharpe']:.3f}")
    if h1_res and h2_res:
        print(f"Split-half: H1={h1_res['sharpe']:.3f}, H2={h2_res['sharpe']:.3f}, ratio={split_half_ratio:.3f}")
    if wf_results:
        print(f"WF: {wf_pos}/{len(wf_results)} positive, mean OOS {wf_mean:.3f}")

    # Save results
    summary = {
        'hypothesis': 'H-125',
        'name': 'Wick Ratio Factor',
        'is_positive_pct': 100*n_positive/total_params,
        'best_params': {'lookback': best_L, 'rebal': best_R, 'n_pos': best_N, 'direction': best_D},
        'best_sharpe': float(best['sharpe']),
        'oos_sharpe': float(test_res['sharpe']) if test_res else None,
        'split_half_h1': float(h1_res['sharpe']) if h1_res else None,
        'split_half_h2': float(h2_res['sharpe']) if h2_res else None,
        'split_half_ratio': float(split_half_ratio) if h1_res and h2_res else None,
        'wf_positive': f"{wf_pos}/{len(wf_results)}" if wf_results else None,
        'wf_mean_oos': float(wf_mean) if wf_results else None,
    }

    with open(ROOT / 'strategies/factor_research/h125_results.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print("\nResults saved to h125_results.json")


if __name__ == "__main__":
    main()
