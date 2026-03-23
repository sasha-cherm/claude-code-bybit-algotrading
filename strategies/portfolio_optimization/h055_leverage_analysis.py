"""
H-055 Leverage Analysis

Tests impact of applying leverage to specific strategies within the H-055 portfolio.

Configurations tested:
  - Baseline: current H-055 (1x all except H-011 which is already 5x internally)
  - Lev-A: 2x on market-neutral XS strategies (H-021, H-031, H-052, H-053)
  - Lev-B: 3x on market-neutral XS strategies (H-021, H-031, H-052, H-053)
  - Lev-C: 2x on ALL non-H-011 strategies (including H-009, H-039, H-046)
  - Lev-D: 3x on ALL non-H-011 strategies
  - Lev-E: 2x on best 4 XS (H-031, H-052, H-053, H-021) + keep H-009/H-039/H-046 at 1x

Funding cost model:
  - Market-neutral (balanced L/S) strategies: funding nets to ~0, no extra cost for leverage
  - Directional strategies (H-009, H-039): incremental leverage adds real funding exposure
    → Cost = (leverage - 1) × avg_daily_funding × position_direction
    → Using historical avg BTC funding: ~0.01% per 8h = ~0.03%/day (paid by longs)

H-055 weights: H-009(12%) H-011(40%) H-021(7%) H-031(13%) H-039(9%) H-046(5%) H-052(8%) H-053(6%)
"""

import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import all strategy generators from the main optimizer
from strategies.portfolio_optimization.h055_portfolio_optimizer import (
    load_all_daily, build_closes_and_volumes,
    gen_h009_returns, gen_h011_returns,
    gen_h021_returns, gen_h031_returns, gen_h039_returns,
    gen_h046_returns, gen_h052_returns, gen_h053_returns,
    compute_metrics,
)

# ── H-055 final weights ──
H055_WEIGHTS = {
    'H-009': 0.12,
    'H-011': 0.40,
    'H-021': 0.07,
    'H-031': 0.13,
    'H-039': 0.09,
    'H-046': 0.05,
    'H-052': 0.08,
    'H-053': 0.06,
}

# Average BTC funding rate per day (3 settlements × ~0.01% = 0.03%/day)
# Based on 2yr historical mean; paid by LONG side
AVG_DAILY_FUNDING = 0.0003


def equity_to_returns(equity):
    """Convert equity series to daily returns."""
    return equity.pct_change().dropna()


def apply_leverage(returns, leverage, is_directional=False, direction_series=None):
    """
    Apply leverage to a return series.

    For market-neutral strategies: leveraged_return = leverage × return
    For directional strategies: add funding cost on incremental notional
      funding_cost = (leverage - 1) × AVG_DAILY_FUNDING × sign(position)
      (longs pay, shorts receive)
    """
    lev_returns = returns * leverage

    if is_directional and leverage > 1.0 and direction_series is not None:
        # Align direction series with returns index
        dir_aligned = direction_series.reindex(returns.index).fillna(0)
        # Incremental funding on (leverage - 1) portion
        # Long: pays funding (negative return impact)
        # Short: receives funding (positive return impact)
        funding_adj = -(leverage - 1) * AVG_DAILY_FUNDING * dir_aligned
        lev_returns = lev_returns + funding_adj

    return lev_returns


def build_portfolio(strategy_returns, weights, leverage_map=None):
    """
    Combine strategy returns into a portfolio.

    leverage_map: dict {strategy_name: leverage_factor}
    """
    if leverage_map is None:
        leverage_map = {}

    # Align all return series to common dates
    common_idx = None
    for name, ret in strategy_returns.items():
        if common_idx is None:
            common_idx = ret.index
        else:
            common_idx = common_idx.intersection(ret.index)

    port_returns = pd.Series(0.0, index=common_idx)
    for name, ret in strategy_returns.items():
        lev = leverage_map.get(name, 1.0)
        w = weights[name]
        aligned = ret.reindex(common_idx).fillna(0)
        port_returns += w * aligned * lev

    return port_returns


def print_metrics(label, returns, indent="  "):
    m = compute_metrics(returns)
    if not m:
        print(f"{indent}{label}: insufficient data")
        return m
    print(f"{indent}{label}:")
    print(f"{indent}  Annual return : {m['annual_return']:+.1%}")
    print(f"{indent}  Annual vol    : {m['annual_vol']:.1%}")
    print(f"{indent}  Sharpe        : {m['sharpe']:.2f}")
    print(f"{indent}  Max DD        : {m['max_dd']:.1%}")
    print(f"{indent}  Days          : {m['n_days']}")
    return m


def worst_day_analysis(returns, label):
    """Show worst days distribution."""
    sorted_days = returns.sort_values()
    print(f"\n  {label} — worst days:")
    for i, (dt, r) in enumerate(sorted_days.head(5).items()):
        print(f"    {dt.date()}  {r:+.2%}")


def stress_test_leverage(returns_by_config):
    """Compare metrics across all configurations in a table."""
    print("\n" + "="*78)
    print(f"{'Config':<20} {'Ann Ret':>9} {'Ann Vol':>9} {'Sharpe':>8} {'Max DD':>9} {'Days':>6}")
    print("="*78)
    for label, returns in returns_by_config.items():
        m = compute_metrics(returns)
        if m:
            print(f"{label:<20} {m['annual_return']:>+9.1%} {m['annual_vol']:>9.1%} "
                  f"{m['sharpe']:>8.2f} {m['max_dd']:>9.1%} {m['n_days']:>6}")
    print("="*78)


def main():
    print("=" * 60)
    print("H-055 LEVERAGE ANALYSIS")
    print("=" * 60)

    # ── 1. Load data ──
    print("\n[1] Loading data...")
    daily = load_all_daily()
    closes, volumes = build_closes_and_volumes(daily)
    print(f"  Loaded {len(daily)} assets, {len(closes)} daily bars")

    # ── 2. Generate strategy returns ──
    print("\n[2] Generating strategy returns...")
    equity = {}
    equity['H-009'] = gen_h009_returns(daily)
    equity['H-011'] = gen_h011_returns(daily)
    equity['H-021'] = gen_h021_returns(closes, volumes)
    equity['H-031'] = gen_h031_returns(closes, volumes)
    equity['H-039'] = gen_h039_returns(daily)
    equity['H-046'] = gen_h046_returns(closes)
    equity['H-052'] = gen_h052_returns(closes)
    equity['H-053'] = gen_h053_returns(closes)

    # Check for failures
    for name, eq in list(equity.items()):
        if eq is None:
            print(f"  WARNING: {name} failed to generate — dropping")
            del equity[name]
        else:
            ret = equity_to_returns(eq)
            print(f"  {name}: {len(ret)} days, "
                  f"ann_ret={((1+ret.mean())**365-1):+.1%}, "
                  f"sharpe={((1+ret.mean())**365-1)/(ret.std()*np.sqrt(365)):.2f}")

    # ── 3. Build raw return series ──
    print("\n[3] Building return series...")
    strat_returns = {name: equity_to_returns(eq) for name, eq in equity.items()}

    # Direction series for H-009 (for funding cost modeling)
    # Reconstruct from the EMA signal
    btc = daily['BTC/USDT']
    close = btc['close']
    ema5 = close.ewm(span=5, adjust=False).mean()
    ema40 = close.ewm(span=40, adjust=False).mean()
    h009_direction = ((ema5 > ema40).astype(float) * 2 - 1).shift(1)  # +1 long, -1 short
    if h009_direction.index.tz is not None:
        h009_direction.index = h009_direction.index.tz_localize(None)

    # H-039 direction: +1 on Wednesday, -1 on Thursday, 0 otherwise
    btc_daily_idx = close.index
    h039_direction = pd.Series(0.0, index=btc_daily_idx)
    h039_direction[btc_daily_idx.dayofweek == 2] = 1.0   # Wed: long
    h039_direction[btc_daily_idx.dayofweek == 3] = -1.0  # Thu: short
    h039_direction = h039_direction.shift(1)

    # ── 4. Define leverage configurations ──
    # Baseline: all 1x (H-011 internal 5x already baked into its returns)
    configs = {}

    # Baseline
    configs['Baseline (1x)'] = {}

    # Lev-A: 2x on 4 best market-neutral XS
    configs['Lev-A: 2x MN-XS'] = {
        'H-021': 2.0, 'H-031': 2.0, 'H-052': 2.0, 'H-053': 2.0
    }

    # Lev-B: 3x on 4 best market-neutral XS
    configs['Lev-B: 3x MN-XS'] = {
        'H-021': 3.0, 'H-031': 3.0, 'H-052': 3.0, 'H-053': 3.0
    }

    # Lev-C: 2x on ALL non-H-011 (including directional)
    configs['Lev-C: 2x all'] = {
        'H-009': 2.0, 'H-021': 2.0, 'H-031': 2.0,
        'H-039': 2.0, 'H-046': 2.0, 'H-052': 2.0, 'H-053': 2.0
    }

    # Lev-D: 3x on ALL non-H-011
    configs['Lev-D: 3x all'] = {
        'H-009': 3.0, 'H-021': 3.0, 'H-031': 3.0,
        'H-039': 3.0, 'H-046': 3.0, 'H-052': 3.0, 'H-053': 3.0
    }

    # Lev-E: 2x on top-3 only (H-031, H-052, H-053 — highest individual Sharpe)
    configs['Lev-E: 2x top-3'] = {
        'H-031': 2.0, 'H-052': 2.0, 'H-053': 2.0
    }

    # ── 5. Build portfolio returns for each config ──
    print("\n[4] Computing portfolio metrics per leverage configuration...")

    results_by_config = {}
    active_weights = {k: v for k, v in H055_WEIGHTS.items() if k in strat_returns}
    # Renormalize weights to active strategies
    total_w = sum(active_weights.values())
    active_weights = {k: v / total_w for k, v in active_weights.items()}

    for config_name, lev_map in configs.items():
        # Build leveraged return series for each strategy
        lev_strat_returns = {}
        for name, ret in strat_returns.items():
            lev = lev_map.get(name, 1.0)
            if lev == 1.0:
                lev_strat_returns[name] = ret
            else:
                # Determine if directional (needs funding cost)
                is_dir = name in ('H-009', 'H-039')
                dir_series = h009_direction if name == 'H-009' else h039_direction
                lev_strat_returns[name] = apply_leverage(
                    ret, lev,
                    is_directional=is_dir,
                    direction_series=dir_series if is_dir else None
                )

        port_ret = build_portfolio(lev_strat_returns, active_weights)
        results_by_config[config_name] = port_ret

    # ── 6. Summary table ──
    print()
    stress_test_leverage(results_by_config)

    # ── 7. Detailed per-config breakdown ──
    print("\n[5] Detailed breakdown:")
    for config_name, port_ret in results_by_config.items():
        print_metrics(config_name, port_ret)

    # ── 8. Worst day analysis for key configs ──
    print("\n[6] Worst day analysis:")
    for label in ['Baseline (1x)', 'Lev-A: 2x MN-XS', 'Lev-B: 3x MN-XS', 'Lev-C: 2x all']:
        worst_day_analysis(results_by_config[label], label)

    # ── 9. Year-by-year breakdown ──
    print("\n[7] Year-by-year returns:")
    header = f"{'Year':<6}"
    for cn in configs:
        header += f" {cn[:14]:>15}"
    print(header)
    for year in [2024, 2025, 2026]:
        row = f"{year:<6}"
        for cn, ret in results_by_config.items():
            year_ret = ret[ret.index.year == year]
            if len(year_ret) > 30:
                ann = (1 + year_ret).prod() ** (365 / len(year_ret)) - 1
                row += f" {ann:>+14.1%}"
            else:
                row += f" {'n/a':>15}"
        print(row)

    # ── 10. Monte Carlo for best config ──
    print("\n[8] Monte Carlo simulation (5000 runs, 1yr) for Lev-A vs Baseline:")
    np.random.seed(42)
    for label in ['Baseline (1x)', 'Lev-A: 2x MN-XS', 'Lev-B: 3x MN-XS']:
        ret = results_by_config[label].dropna().values
        sims = np.random.choice(ret, size=(5000, 365), replace=True)
        ann_rets = (1 + sims).prod(axis=1) - 1
        max_dds = []
        for sim in sims:
            eq = (1 + sim).cumprod()
            dd = (eq / np.maximum.accumulate(eq) - 1).min()
            max_dds.append(dd)
        max_dds = np.array(max_dds)
        p_loss = (ann_rets < 0).mean()
        p_gt20 = (ann_rets > 0.20).mean()
        p_gt50 = (ann_rets > 0.50).mean()
        p_dd10 = (max_dds < -0.10).mean()
        p_dd20 = (max_dds < -0.20).mean()
        print(f"\n  {label}:")
        print(f"    Median 1yr return : {np.median(ann_rets):+.1%}")
        print(f"    5th pct return    : {np.percentile(ann_rets, 5):+.1%}")
        print(f"    95th pct return   : {np.percentile(ann_rets, 95):+.1%}")
        print(f"    P(loss)           : {p_loss:.1%}")
        print(f"    P(>20% return)    : {p_gt20:.1%}")
        print(f"    P(>50% return)    : {p_gt50:.1%}")
        print(f"    P(DD > 10%)       : {p_dd10:.1%}")
        print(f"    P(DD > 20%)       : {p_dd20:.1%}")

    print("\n[Done]")


if __name__ == '__main__':
    main()
