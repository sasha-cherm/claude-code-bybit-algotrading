"""
Optimal portfolio allocation without H-011.

Finds weights for H-009, H-021, H-031, H-039, H-046, H-052, H-053 via:
  1. Max Sharpe (unconstrained & capped at 40% per strategy)
  2. Min Volatility
  3. Equal Weight
  4. Current renormalized H-055 weights (baseline)
  5. Max Sharpe with leverage (2x on MN strategies)

Also runs walk-forward validation to check if optimal weights are stable OOS.
"""

import sys, os
import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from strategies.portfolio_optimization.h055_portfolio_optimizer import (
    load_all_daily, build_closes_and_volumes,
    gen_h009_returns, gen_h021_returns, gen_h031_returns,
    gen_h039_returns, gen_h046_returns, gen_h052_returns, gen_h053_returns,
    compute_metrics,
)

MN_STRATEGIES  = {'H-021', 'H-031', 'H-046', 'H-052', 'H-053'}
DIR_STRATEGIES = {'H-009', 'H-039'}

# Renormalized H-055 weights (baseline for comparison)
BASELINE_WEIGHTS = {
    'H-009': 0.12 / 0.60,
    'H-021': 0.07 / 0.60,
    'H-031': 0.13 / 0.60,
    'H-039': 0.09 / 0.60,
    'H-046': 0.05 / 0.60,
    'H-052': 0.08 / 0.60,
    'H-053': 0.06 / 0.60,
}


def equity_to_returns(equity):
    return equity.pct_change().dropna()


def build_returns_df(strat_returns):
    """Align all strategy returns into a single DataFrame."""
    common_idx = None
    for r in strat_returns.values():
        common_idx = r.index if common_idx is None else common_idx.intersection(r.index)
    df = pd.DataFrame({k: v.reindex(common_idx) for k, v in strat_returns.items()})
    return df.dropna()


def portfolio_metrics(weights_arr, returns_df):
    """Annual return, vol, Sharpe for a weight vector."""
    port = returns_df.values @ weights_arr
    ann_ret = (1 + port.mean()) ** 365 - 1
    ann_vol = port.std() * np.sqrt(365)
    sharpe  = ann_ret / ann_vol if ann_vol > 0 else 0
    cum = (1 + port).cumprod()
    max_dd = (cum / np.maximum.accumulate(cum) - 1).min()
    return ann_ret, ann_vol, sharpe, max_dd


def optimize(returns_df, method='max_sharpe', max_weight=0.40, min_weight=0.03):
    """MVO optimization."""
    n = len(returns_df.columns)
    w0 = np.ones(n) / n

    constraints = [{'type': 'eq', 'fun': lambda w: w.sum() - 1}]
    bounds = [(min_weight, max_weight)] * n

    if method == 'max_sharpe':
        def neg_sharpe(w):
            _, _, sr, _ = portfolio_metrics(w, returns_df)
            return -sr
        res = minimize(neg_sharpe, w0, method='SLSQP',
                       bounds=bounds, constraints=constraints,
                       options={'maxiter': 1000, 'ftol': 1e-10})
    elif method == 'min_vol':
        def vol(w):
            port = returns_df.values @ w
            return port.std() * np.sqrt(365)
        res = minimize(vol, w0, method='SLSQP',
                       bounds=bounds, constraints=constraints,
                       options={'maxiter': 1000, 'ftol': 1e-10})
    elif method == 'max_sharpe_lev':
        # Apply 2x to MN strategies before optimizing
        lev_returns = returns_df.copy()
        for col in lev_returns.columns:
            if col in MN_STRATEGIES:
                lev_returns[col] = lev_returns[col] * 2.0
        def neg_sharpe_lev(w):
            _, _, sr, _ = portfolio_metrics(w, lev_returns)
            return -sr
        res = minimize(neg_sharpe_lev, w0, method='SLSQP',
                       bounds=bounds, constraints=constraints,
                       options={'maxiter': 1000, 'ftol': 1e-10})
        # Return weights that apply to the LEVERAGED returns
        return dict(zip(returns_df.columns, res.x)), res.success

    return dict(zip(returns_df.columns, res.x)), res.success


def walk_forward_stability(returns_df, n_folds=5):
    """
    Walk-forward test: train on 60% of data, test on remaining 40%.
    Measures if optimized weights from training hold up OOS.
    """
    n = len(returns_df)
    train_size = int(n * 0.60)
    step = (n - train_size) // n_folds

    results = []
    for fold in range(n_folds):
        start = fold * step
        end   = start + train_size
        if end + step > n:
            break

        train = returns_df.iloc[start:end]
        test  = returns_df.iloc[end:end + step]

        weights, ok = optimize(train, method='max_sharpe', max_weight=0.40)
        if not ok:
            continue

        w_arr = np.array([weights[c] for c in returns_df.columns])
        _, _, train_sr, train_dd = portfolio_metrics(w_arr, train)
        _, _, test_sr,  test_dd  = portfolio_metrics(w_arr, test)

        results.append({
            'fold': fold + 1,
            'train_days': len(train),
            'test_days': len(test),
            'train_sharpe': train_sr,
            'test_sharpe': test_sr,
            'train_dd': train_dd,
            'test_dd': test_dd,
        })

    return pd.DataFrame(results)


def print_weights(weights, label, returns_df=None, lev_map=None):
    """Print weights + optional metrics."""
    names = sorted(weights.keys())
    print(f"\n  {label}:")
    for n in sorted(names, key=lambda x: -weights[x]):
        tag = "(MN)" if n in MN_STRATEGIES else "(DIR)"
        print(f"    {n} {tag}: {weights[n]:.1%}")
    if returns_df is not None:
        if lev_map:
            rd = returns_df.copy()
            for col in rd.columns:
                if col in lev_map:
                    rd[col] = rd[col] * lev_map[col]
        else:
            rd = returns_df
        w_arr = np.array([weights[c] for c in rd.columns])
        ar, av, sr, dd = portfolio_metrics(w_arr, rd)
        print(f"    → Ann return: {ar:+.1%} | Vol: {av:.1%} | Sharpe: {sr:.2f} | Max DD: {dd:.1%}")


def main():
    print("=" * 65)
    print("OPTIMAL PORTFOLIO WITHOUT H-011")
    print("=" * 65)

    # ── Load data ──
    print("\n[1] Loading data...")
    daily = load_all_daily()
    closes, volumes = build_closes_and_volumes(daily)

    # ── Generate returns ──
    print("[2] Generating strategy returns...")
    equity = {
        'H-009': gen_h009_returns(daily),
        'H-021': gen_h021_returns(closes, volumes),
        'H-031': gen_h031_returns(closes, volumes),
        'H-039': gen_h039_returns(daily),
        'H-046': gen_h046_returns(closes),
        'H-052': gen_h052_returns(closes),
        'H-053': gen_h053_returns(closes),
    }
    equity = {k: v for k, v in equity.items() if v is not None}
    strat_returns = {k: equity_to_returns(v) for k, v in equity.items()}

    returns_df = build_returns_df(strat_returns)
    print(f"  {len(returns_df.columns)} strategies, {len(returns_df)} common days\n")

    # Individual strategy metrics
    print("  Individual strategy metrics:")
    print(f"  {'Strategy':<10} {'Ann Ret':>9} {'Vol':>8} {'Sharpe':>8} {'Max DD':>9}")
    print(f"  {'─'*10} {'─'*9} {'─'*8} {'─'*8} {'─'*9}")
    for col in returns_df.columns:
        r = returns_df[col].values
        ar = (1 + r.mean()) ** 365 - 1
        av = r.std() * np.sqrt(365)
        sr = ar / av if av > 0 else 0
        cum = (1 + r).cumprod()
        dd = (cum / np.maximum.accumulate(cum) - 1).min()
        tag = "(MN)" if col in MN_STRATEGIES else "(DIR)"
        print(f"  {col:<6}{tag:<5} {ar:>+9.1%} {av:>8.1%} {sr:>8.2f} {dd:>9.1%}")

    # ── Correlation matrix ──
    print("\n[3] Strategy correlations:")
    corr = returns_df.corr().round(3)
    cols = list(returns_df.columns)
    print(f"  {'':>8}", end="")
    for c in cols:
        print(f"  {c:>7}", end="")
    print()
    for r in cols:
        print(f"  {r:>8}", end="")
        for c in cols:
            v = corr.loc[r, c]
            print(f"  {v:>7.3f}", end="")
        print()

    # ── Optimization ──
    print("\n[4] Portfolio optimization:")

    # A. Baseline (renormalized H-055)
    avail_baseline = {k: BASELINE_WEIGHTS[k] for k in returns_df.columns}
    tw = sum(avail_baseline.values())
    avail_baseline = {k: v/tw for k, v in avail_baseline.items()}
    print_weights(avail_baseline, "Baseline (renorm H-055 weights)", returns_df)

    # B. Equal weight
    ew = {k: 1/len(returns_df.columns) for k in returns_df.columns}
    print_weights(ew, "Equal weight", returns_df)

    # C. Max Sharpe (cap 40%)
    ws_max, ok = optimize(returns_df, method='max_sharpe', max_weight=0.40)
    print_weights(ws_max, f"Max Sharpe (cap 40%, ok={ok})", returns_df)

    # D. Max Sharpe (cap 30%)
    ws_30, ok = optimize(returns_df, method='max_sharpe', max_weight=0.30)
    print_weights(ws_30, f"Max Sharpe (cap 30%, ok={ok})", returns_df)

    # E. Min Volatility
    ws_mv, ok = optimize(returns_df, method='min_vol', max_weight=0.40)
    print_weights(ws_mv, f"Min Volatility (cap 40%, ok={ok})", returns_df)

    # F. Max Sharpe with 2x leverage on MN strategies
    lev_map_2x = {s: 2.0 for s in MN_STRATEGIES}
    ws_lev, ok = optimize(returns_df, method='max_sharpe_lev', max_weight=0.40)
    print(f"\n  Max Sharpe with 2x MN leverage (cap 40%, ok={ok}):")
    for n in sorted(ws_lev.keys(), key=lambda x: -ws_lev[x]):
        tag = "(MN 2x)" if n in MN_STRATEGIES else "(DIR 1x)"
        print(f"    {n} {tag}: {ws_lev[n]:.1%}")
    # Compute metrics with leverage applied
    rd_lev = returns_df.copy()
    for col in rd_lev.columns:
        if col in MN_STRATEGIES:
            rd_lev[col] = rd_lev[col] * 2.0
    w_arr = np.array([ws_lev[c] for c in rd_lev.columns])
    ar, av, sr, dd = portfolio_metrics(w_arr, rd_lev)
    print(f"    → Ann return: {ar:+.1%} | Vol: {av:.1%} | Sharpe: {sr:.2f} | Max DD: {dd:.1%}")

    # ── Summary comparison table ──
    print("\n[5] Summary comparison:")
    configs = {
        'Renorm H-055':      (avail_baseline, None),
        'Equal weight':      (ew, None),
        'Max Sharpe 40%':    (ws_max, None),
        'Max Sharpe 30%':    (ws_30, None),
        'Min Vol 40%':       (ws_mv, None),
        'MaxSharpe 2x MN':   (ws_lev, lev_map_2x),
    }
    print(f"\n  {'Config':<22} {'Ann Ret':>9} {'Vol':>8} {'Sharpe':>8} {'Max DD':>9}")
    print(f"  {'─'*22} {'─'*9} {'─'*8} {'─'*8} {'─'*9}")
    for label, (w, lm) in configs.items():
        rd = returns_df.copy()
        if lm:
            for col in rd.columns:
                if col in lm:
                    rd[col] = rd[col] * lm[col]
        w_arr = np.array([w[c] for c in rd.columns])
        ar, av, sr, dd = portfolio_metrics(w_arr, rd)
        print(f"  {label:<22} {ar:>+9.1%} {av:>8.1%} {sr:>8.2f} {dd:>9.1%}")

    # ── Walk-forward stability ──
    print("\n[6] Walk-forward stability of Max Sharpe weights (5 folds):")
    wf = walk_forward_stability(returns_df, n_folds=5)
    if not wf.empty:
        print(f"\n  {'Fold':<6} {'Train Sharpe':>13} {'OOS Sharpe':>11} "
              f"{'Train DD':>10} {'OOS DD':>9}")
        print(f"  {'─'*6} {'─'*13} {'─'*11} {'─'*10} {'─'*9}")
        for _, row in wf.iterrows():
            print(f"  {int(row.fold):<6} {row.train_sharpe:>13.2f} {row.test_sharpe:>11.2f} "
                  f"{row.train_dd:>10.1%} {row.test_dd:>9.1%}")
        print(f"\n  Mean OOS Sharpe: {wf.test_sharpe.mean():.2f}  "
              f"(vs train: {wf.train_sharpe.mean():.2f})")
        print(f"  OOS positive:    {(wf.test_sharpe > 0).sum()}/{len(wf)} folds")

    # ── Year-by-year for best configs ──
    print("\n[7] Year-by-year returns (best configs):")
    best_configs = {
        'Renorm H-055':   (avail_baseline, None),
        'Max Sharpe 30%': (ws_30, None),
        'MaxSharpe 2x MN':(ws_lev, lev_map_2x),
    }
    print(f"\n  {'Year':<6}", end="")
    for cn in best_configs:
        print(f" {cn:>18}", end="")
    print()
    for year in [2024, 2025, 2026]:
        print(f"  {year:<6}", end="")
        for cn, (w, lm) in best_configs.items():
            rd = returns_df.copy()
            if lm:
                for col in rd.columns:
                    if col in lm:
                        rd[col] = rd[col] * lm[col]
            w_arr = np.array([w[c] for c in rd.columns])
            port = rd.values @ w_arr
            yr = port[rd.index.year == year]
            if len(yr) > 20:
                ann = (1 + yr).prod() ** (365 / len(yr)) - 1
                print(f" {ann:>+17.1%}", end="")
            else:
                print(f" {'n/a':>18}", end="")
        print()

    # ── Final recommendation ──
    print("\n[8] Recommended allocation (Max Sharpe 30% cap, 1x):")
    for n in sorted(ws_30.keys(), key=lambda x: -ws_30[x]):
        tag = "Market-neutral" if n in MN_STRATEGIES else "Directional"
        print(f"    {n} ({tag}): {ws_30[n]:.1%}")

    print("\n[Done]")


if __name__ == '__main__':
    main()
