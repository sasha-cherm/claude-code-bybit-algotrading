"""
H-127: Volume-Price Divergence Factor (Cross-Sectional)

This factor measures the divergence between volume-weighted returns and
equal-weighted returns:
  div = rolling_mean(vw_ret - ew_ret, lookback)
  where vw_ret = ret * (vol / avg_vol)

When volume-weighted returns exceed equal-weighted returns, it suggests
"smart money" or large participants are buying. Cross-sectional z-scored.

Two directions tested:
  (a) div_long = long high divergence (vol-weighted > equal-weighted), short low
  (b) conv_long = contrarian — short high divergence, long low

Validation: Full grid + split-half + walk-forward + correlation check.
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

LOOKBACKS = [3, 5, 10, 20]
REBAL_FREQS = [3, 5, 7, 10]
N_LONGS = [3, 4, 5]
DIRECTIONS = ["div_long", "conv_long"]

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


def compute_signal(daily, lookback):
    """Volume-price divergence: vw_ret - ew_ret, cross-sectionally z-scored."""
    signals = {}
    for sym, df in daily.items():
        ret = df['close'].pct_change()
        vol = df['volume']
        vol_norm = vol / vol.rolling(lookback).mean()
        vw_ret = (ret * vol_norm).rolling(lookback).mean()
        ew_ret = ret.rolling(lookback).mean()
        signals[sym] = vw_ret - ew_ret

    sig_df = pd.DataFrame(signals)
    sig_z = sig_df.sub(sig_df.mean(axis=1), axis=0).div(sig_df.std(axis=1) + 1e-10, axis=0)
    return sig_z


def run_backtest(signal_df, close_df, ret_df, all_dates, rebal_freq, n_positions, direction, start_idx=None, end_idx=None):
    dates = all_dates
    if start_idx is not None:
        dates = dates[start_idx:end_idx]

    if len(dates) < rebal_freq + 1:
        return None

    capital = INITIAL_CAPITAL
    equity_curve = []
    daily_returns = []
    positions = {}
    days_since_rebal = rebal_freq

    for i, date in enumerate(dates):
        if i == 0:
            equity_curve.append(capital)
            continue

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
            prev_date = dates[i-1] if i > 0 else date
            if prev_date in signal_df.index:
                signals = signal_df.loc[prev_date].dropna()
            else:
                continue

            if len(signals) >= 2 * n_positions:
                ranked = signals.sort_values()

                if direction == "div_long":
                    longs = ranked.index[-n_positions:].tolist()
                    shorts = ranked.index[:n_positions].tolist()
                elif direction == "conv_long":
                    longs = ranked.index[:n_positions].tolist()
                    shorts = ranked.index[-n_positions:].tolist()

                new_positions = {}
                w = 1.0 / (2 * n_positions)
                for sym in longs:
                    new_positions[sym] = w
                for sym in shorts:
                    new_positions[sym] = -w

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
    }


def main():
    print("=" * 70)
    print("H-127: Volume-Price Divergence Factor Backtest")
    print("=" * 70)

    daily = load_daily_data()
    if len(daily) < 10:
        print("Not enough assets. Aborting.")
        return

    common_start = max(df.index[0] for df in daily.values())
    common_end = min(df.index[-1] for df in daily.values())
    total_days = (common_end - common_start).days
    print(f"\nCommon range: {common_start.date()} to {common_end.date()} ({total_days} days)")

    for sym in list(daily.keys()):
        daily[sym] = daily[sym].loc[common_start:common_end]

    # Build close and return DataFrames once
    syms = list(daily.keys())
    close_df = pd.DataFrame({sym: daily[sym]['close'] for sym in syms})
    ret_df = close_df.pct_change()

    # Precompute signals for all lookbacks
    print("\nPrecomputing signals...")
    signal_cache = {}
    for L in LOOKBACKS:
        signal_cache[L] = compute_signal(daily, L)
        print(f"  L={L}: {len(signal_cache[L].dropna(how='all'))} valid dates")

    # === 1. Full Parameter Grid ===
    print("\n--- Phase 1: Full Parameter Grid Scan ---")
    all_results = []
    for L, R, N, D in product(LOOKBACKS, REBAL_FREQS, N_LONGS, DIRECTIONS):
        sig = signal_cache[L]
        dates = sig.dropna(how='all').index
        res = run_backtest(sig, close_df, ret_df, dates, R, N, D)
        if res:
            all_results.append({
                'lookback': L, 'rebal': R, 'n_pos': N, 'direction': D,
                'sharpe': res['sharpe'], 'annual_return': res['annual_return'],
                'max_drawdown': res['max_drawdown'],
            })

    df_res = pd.DataFrame(all_results)
    if len(df_res) == 0:
        print("No valid results. Aborting.")
        return

    n_positive = (df_res['sharpe'] > 0).sum()
    total_params = len(df_res)
    print(f"Parameter combinations: {total_params}")
    print(f"Positive Sharpe: {n_positive}/{total_params} ({100*n_positive/total_params:.1f}%)")
    print(f"Mean Sharpe: {df_res['sharpe'].mean():.3f}")
    print(f"Median Sharpe: {df_res['sharpe'].median():.3f}")

    for d in DIRECTIONS:
        sub = df_res[df_res['direction'] == d]
        if len(sub) > 0:
            pos = (sub['sharpe'] > 0).sum()
            print(f"  {d}: {pos}/{len(sub)} positive ({100*pos/len(sub):.1f}%), "
                  f"mean Sharpe {sub['sharpe'].mean():.3f}")

    best = df_res.loc[df_res['sharpe'].idxmax()]
    print(f"\nBest: L={best['lookback']} R={best['rebal']} N={best['n_pos']} "
          f"D={best['direction']} -> Sharpe {best['sharpe']:.3f}, "
          f"Return {best['annual_return']*100:.1f}%, DD {best['max_drawdown']*100:.1f}%")

    best_L = int(best['lookback'])
    best_R = int(best['rebal'])
    best_N = int(best['n_pos'])
    best_D = best['direction']

    # === 2. Train/Test ===
    print("\n--- Phase 2: Train/Test Split (70/30) ---")
    sig = signal_cache[best_L]
    dates = sig.dropna(how='all').index
    split_idx = int(len(dates) * 0.7)

    train_res = run_backtest(sig, close_df, ret_df, dates, best_R, best_N, best_D, end_idx=split_idx)
    test_res = run_backtest(sig, close_df, ret_df, dates, best_R, best_N, best_D, start_idx=split_idx)

    if train_res and test_res:
        print(f"Train: Sharpe {train_res['sharpe']:.3f}, Return {train_res['annual_return']*100:.1f}%")
        print(f"Test:  Sharpe {test_res['sharpe']:.3f}, Return {test_res['annual_return']*100:.1f}%")

    # === 3. Split-Half ===
    print("\n--- Phase 3: Split-Half Stability ---")
    mid = len(dates) // 2
    h1_res = run_backtest(sig, close_df, ret_df, dates, best_R, best_N, best_D, end_idx=mid)
    h2_res = run_backtest(sig, close_df, ret_df, dates, best_R, best_N, best_D, start_idx=mid)

    split_half_ratio = 0
    if h1_res and h2_res:
        print(f"H1: Sharpe {h1_res['sharpe']:.3f}")
        print(f"H2: Sharpe {h2_res['sharpe']:.3f}")
        denom = max(abs(h1_res['sharpe']), abs(h2_res['sharpe']))
        split_half_ratio = min(h1_res['sharpe'], h2_res['sharpe']) / denom if denom > 0 else 0
        print(f"Split-half ratio: {split_half_ratio:.3f}")

    # === 4. Walk-Forward ===
    print("\n--- Phase 4: Walk-Forward (IS param selection) ---")
    n_dates = len(dates)

    wf_results = []
    for fold in range(WF_FOLDS):
        train_start = fold * WF_STEP
        train_end = train_start + WF_TRAIN
        test_start = train_end
        test_end = test_start + WF_TEST

        if test_end > n_dates:
            break

        best_is_sharpe = -999
        best_is_params = None
        for L, R, N, D in product(LOOKBACKS, REBAL_FREQS, N_LONGS, DIRECTIONS):
            s = signal_cache[L]
            d2 = s.dropna(how='all').index
            res = run_backtest(s, close_df, ret_df, d2, R, N, D, start_idx=train_start, end_idx=train_end)
            if res and res['sharpe'] > best_is_sharpe:
                best_is_sharpe = res['sharpe']
                best_is_params = (L, R, N, D)

        if best_is_params:
            s = signal_cache[best_is_params[0]]
            d2 = s.dropna(how='all').index
            oos_res = run_backtest(s, close_df, ret_df, d2, best_is_params[1], best_is_params[2], best_is_params[3], start_idx=test_start, end_idx=test_end)
            if oos_res:
                wf_results.append({
                    'fold': fold,
                    'is_sharpe': best_is_sharpe,
                    'oos_sharpe': oos_res['sharpe'],
                    'params': best_is_params,
                })
                print(f"  Fold {fold}: IS={best_is_sharpe:.3f} -> OOS={oos_res['sharpe']:.3f} "
                      f"(L={best_is_params[0]}, R={best_is_params[1]}, N={best_is_params[2]}, D={best_is_params[3]})")

    wf_pos = 0
    wf_mean = 0
    if wf_results:
        wf_pos = sum(1 for w in wf_results if w['oos_sharpe'] > 0)
        wf_mean = np.mean([w['oos_sharpe'] for w in wf_results])
        print(f"\nWF OOS: {wf_pos}/{len(wf_results)} positive, mean OOS Sharpe {wf_mean:.3f}")

    # === 5. Correlation ===
    print("\n--- Phase 5: Correlation with H-012 (Momentum) ---")
    mom_df = pd.DataFrame({sym: daily[sym]['close'].pct_change() for sym in syms}).rolling(60).sum()

    common_idx = sig.dropna(how='all').index.intersection(mom_df.dropna(how='all').index)
    avg_corr = 0
    if len(common_idx) > 100:
        div_ranks = sig.loc[common_idx].rank(axis=1)
        mom_ranks = mom_df.loc[common_idx].rank(axis=1)

        correlations = []
        for date in common_idx[::5]:
            dr = div_ranks.loc[date].dropna()
            mr = mom_ranks.loc[date].dropna()
            common = dr.index.intersection(mr.index)
            if len(common) >= 8:
                correlations.append(dr[common].corr(mr[common]))

        if correlations:
            avg_corr = np.nanmean(correlations)
            print(f"Average rank correlation with H-012 (momentum): {avg_corr:.3f}")

    # === Summary ===
    print("\n" + "=" * 70)
    print("H-127 SUMMARY")
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
    print(f"Corr with H-012: {avg_corr:.3f}")

    summary = {
        'hypothesis': 'H-127',
        'name': 'Volume-Price Divergence Factor',
        'is_positive_pct': 100*n_positive/total_params,
        'best_params': {'lookback': best_L, 'rebal': best_R, 'n_pos': best_N, 'direction': best_D},
        'best_sharpe': float(best['sharpe']),
        'oos_sharpe': float(test_res['sharpe']) if test_res else None,
        'split_half_h1': float(h1_res['sharpe']) if h1_res else None,
        'split_half_h2': float(h2_res['sharpe']) if h2_res else None,
        'split_half_ratio': float(split_half_ratio),
        'wf_positive': f"{wf_pos}/{len(wf_results)}" if wf_results else None,
        'wf_mean_oos': float(wf_mean),
        'corr_h012': float(avg_corr),
    }

    with open(ROOT / 'strategies/factor_research/h127_results.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print("\nResults saved to h127_results.json")


if __name__ == "__main__":
    main()
