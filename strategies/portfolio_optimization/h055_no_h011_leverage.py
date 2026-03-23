"""
H-055 Without H-011 — Leverage & Liquidation Risk Analysis

Explores the portfolio using only the 7 XS/factor strategies (no H-011),
tests leverage on the market-neutral subset, and quantifies liquidation risk
on a $1,000 account using Bybit cross-margin mechanics.

Bybit USDT perpetual margin model (VIP0):
  - Initial margin rate = 1 / leverage
  - Maintenance margin rate = 0.5% (0.005) for most perps
  - Cross-margin: all account equity serves as collateral for all positions
  - Liquidation triggered when: equity < sum(maintenance_margin per position)
  - Maintenance margin per position = notional × 0.5%
"""

import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from strategies.portfolio_optimization.h055_portfolio_optimizer import (
    load_all_daily, build_closes_and_volumes,
    gen_h009_returns, gen_h021_returns, gen_h031_returns,
    gen_h039_returns, gen_h046_returns, gen_h052_returns, gen_h053_returns,
    compute_metrics,
)

# ── H-055 weights WITHOUT H-011 (renormalized from 60% to 100%) ──
WEIGHTS_NO_H011 = {
    'H-009': 0.12 / 0.60,   # 20.0%
    'H-021': 0.07 / 0.60,   # 11.7%
    'H-031': 0.13 / 0.60,   # 21.7%
    'H-039': 0.09 / 0.60,   # 15.0%
    'H-046': 0.05 / 0.60,   #  8.3%
    'H-052': 0.08 / 0.60,   # 13.3%
    'H-053': 0.06 / 0.60,   # 10.0%
}

# Market-neutral XS strategies (balanced long/short — funding nets to ~0)
MN_STRATEGIES = {'H-021', 'H-031', 'H-046', 'H-052', 'H-053'}

# Directional strategies
DIR_STRATEGIES = {'H-009', 'H-039'}

# Bybit margin parameters
MAINT_MARGIN_RATE = 0.005    # 0.5% maintenance margin on notional
AVG_DAILY_FUNDING  = 0.0003  # ~0.03%/day average BTC funding paid by longs

ACCOUNT_SIZE = 1_000.0       # starting capital for liquidation analysis


def equity_to_returns(equity):
    return equity.pct_change().dropna()


def build_portfolio_returns(strat_returns, weights, lev_map):
    """Build daily portfolio returns with per-strategy leverage."""
    common_idx = None
    for ret in strat_returns.values():
        common_idx = ret.index if common_idx is None else common_idx.intersection(ret.index)

    port = pd.Series(0.0, index=common_idx)
    for name, ret in strat_returns.items():
        lev = lev_map.get(name, 1.0)
        port += weights[name] * ret.reindex(common_idx).fillna(0) * lev
    return port


def margin_analysis(weights, lev_map, account_size):
    """
    Compute margin requirements and liquidation threshold for $account_size.

    Cross-margin model:
      Total notional = sum(weight × lev × account_size)   for each strategy leg
      Initial margin required = sum(notional / lev) = account_size (since weights sum to 1)
      Maintenance margin required = sum(notional × MAINT_MARGIN_RATE)
      Liquidation occurs when: remaining_equity < total_maintenance_margin
    """
    total_notional = sum(weights[s] * lev_map.get(s, 1.0) * account_size
                         for s in weights)
    # For market-neutral strategies, each side (L and S) is separately margined
    # Total notional is approximately 2x per strategy leg notional
    # (long book + short book)
    mn_notional = sum(weights[s] * lev_map.get(s, 1.0) * account_size * 2
                      for s in MN_STRATEGIES if s in weights)
    dir_notional = sum(weights[s] * lev_map.get(s, 1.0) * account_size
                       for s in DIR_STRATEGIES if s in weights)
    total_gross_notional = mn_notional + dir_notional

    maintenance_margin = total_gross_notional * MAINT_MARGIN_RATE
    initial_margin = account_size  # capital fully deployed

    # Liquidation buffer: how much the portfolio can lose before margin call
    liq_buffer = initial_margin - maintenance_margin
    liq_pct = liq_buffer / initial_margin  # % of capital that can be lost

    return {
        'total_gross_notional': total_gross_notional,
        'maintenance_margin': maintenance_margin,
        'liq_buffer_$': liq_buffer,
        'liq_buffer_%': liq_pct,
        'liq_trigger_%': -liq_pct,   # loss % that triggers liquidation
    }


def monte_carlo_ruin(daily_returns, n_sims=10000, n_days=365,
                     liq_threshold=-0.90, account_size=1_000):
    """
    Monte Carlo simulation tracking path-dependent liquidation risk.

    liq_threshold: fraction of account lost that triggers liquidation
    Returns: P(ruin), P(DD>10%), P(DD>20%), P(DD>30%), median_return
    """
    np.random.seed(42)
    ret_values = daily_returns.dropna().values
    ruined = 0
    final_returns = []
    max_dds = []

    for _ in range(n_sims):
        daily = np.random.choice(ret_values, size=n_days, replace=True)
        equity = account_size * (1 + daily).cumprod()
        running_max = np.maximum.accumulate(equity)
        dd_series = equity / running_max - 1
        max_dd = dd_series.min()

        if max_dd <= liq_threshold:
            ruined += 1

        final_returns.append(equity[-1] / account_size - 1)
        max_dds.append(max_dd)

    max_dds = np.array(max_dds)
    final_returns = np.array(final_returns)

    return {
        'p_ruin': ruined / n_sims,
        'p_dd_10': (max_dds < -0.10).mean(),
        'p_dd_20': (max_dds < -0.20).mean(),
        'p_dd_30': (max_dds < -0.30).mean(),
        'median_return': np.median(final_returns),
        'p5_return': np.percentile(final_returns, 5),
        'p95_return': np.percentile(final_returns, 95),
        'p_loss': (final_returns < 0).mean(),
        'p_gt50': (final_returns > 0.50).mean(),
        'p_gt100': (final_returns > 1.00).mean(),
    }


def consecutive_loss_to_liquidate(daily_returns, liq_pct):
    """
    How many avg-bad-day consecutive losses would trigger liquidation?
    Uses the 5th percentile daily return as the 'bad day' scenario.
    """
    bad_day = np.percentile(daily_returns.dropna().values, 5)
    days = np.log(1 - liq_pct) / np.log(1 + bad_day)
    return bad_day, int(np.ceil(days))


def print_sep(title=""):
    w = 70
    if title:
        print(f"\n{'─'*3} {title} {'─'*(w-5-len(title))}")
    else:
        print("─" * w)


def main():
    print("=" * 70)
    print("H-055 WITHOUT H-011 — LEVERAGE & LIQUIDATION RISK ANALYSIS")
    print(f"Account size: ${ACCOUNT_SIZE:,.0f}")
    print("=" * 70)

    # ── Load data ──
    print("\n[1] Loading data...")
    daily = load_all_daily()
    closes, volumes = build_closes_and_volumes(daily)
    print(f"  {len(daily)} assets, {len(closes)} daily bars")

    # ── Generate returns ──
    print("\n[2] Generating strategy returns (no H-011)...")
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

    # Renormalize weights to available strategies
    avail = {k: WEIGHTS_NO_H011[k] for k in equity if k in WEIGHTS_NO_H011}
    total_w = sum(avail.values())
    avail = {k: v / total_w for k, v in avail.items()}

    print(f"\n  Weights (renormalized):")
    for k, w in sorted(avail.items(), key=lambda x: -x[1]):
        ltype = "Market-neutral" if k in MN_STRATEGIES else "Directional"
        print(f"    {k}: {w:.1%}  [{ltype}]")

    # ── Define configurations ──
    configs = {
        'No-H011 1x':        {},
        'No-H011 2x MN':     {s: 2.0 for s in MN_STRATEGIES},
        'No-H011 3x MN':     {s: 3.0 for s in MN_STRATEGIES},
        'No-H011 2x all':    {s: 2.0 for s in avail},
        'No-H011 3x all':    {s: 3.0 for s in avail},
    }

    # ── Build portfolio returns ──
    print("\n[3] Portfolio metrics:")
    port_rets = {}
    print(f"\n  {'Config':<22} {'Ann Ret':>9} {'Vol':>8} {'Sharpe':>8} {'Max DD':>9}")
    print(f"  {'─'*22} {'─'*9} {'─'*8} {'─'*8} {'─'*9}")
    for cfg_name, lev_map in configs.items():
        pr = build_portfolio_returns(strat_returns, avail, lev_map)
        port_rets[cfg_name] = pr
        m = compute_metrics(pr)
        print(f"  {cfg_name:<22} {m['annual_return']:>+9.1%} {m['annual_vol']:>8.1%} "
              f"{m['sharpe']:>8.2f} {m['max_dd']:>9.1%}")

    # ── Margin & liquidation analysis ──
    print_sep("MARGIN & LIQUIDATION RISK ($1,000 cross-margin)")
    print(f"\n  {'Config':<22} {'Gross Notional':>16} {'Maint Margin':>14} "
          f"{'Liq Buffer':>12} {'Liq Trigger':>13}")
    print(f"  {'─'*22} {'─'*16} {'─'*14} {'─'*12} {'─'*13}")
    for cfg_name, lev_map in configs.items():
        mg = margin_analysis(avail, lev_map, ACCOUNT_SIZE)
        print(f"  {cfg_name:<22} ${mg['total_gross_notional']:>13,.0f} "
              f"  ${mg['maintenance_margin']:>11,.2f} "
              f"  ${mg['liq_buffer_$']:>9,.2f} "
              f"  {mg['liq_trigger_%']:>+12.1%}")

    print(f"""
  Notes:
  • Gross notional = sum of all long + short perp positions
  • Maintenance margin = 0.5% × gross notional (Bybit standard)
  • Liquidation buffer = capital remaining before margin call
  • Liq trigger = % portfolio loss that causes forced liquidation
  • At liq trigger: Bybit closes all positions automatically
    """)

    # ── Consecutive bad days to liquidation ──
    print_sep("CONSECUTIVE BAD DAYS TO LIQUIDATION")
    print(f"\n  (Using 5th-percentile daily return as 'bad day' scenario)")
    print(f"\n  {'Config':<22} {'Bad Day (5th pct)':>18} {'Days to Liq':>13} {'Liq at $':>10}")
    print(f"  {'─'*22} {'─'*18} {'─'*13} {'─'*10}")
    for cfg_name, lev_map in configs.items():
        mg = margin_analysis(avail, lev_map, ACCOUNT_SIZE)
        pr = port_rets[cfg_name]
        bad_day, n_days = consecutive_loss_to_liquidate(pr, mg['liq_buffer_%'])
        liq_at = ACCOUNT_SIZE * (1 - mg['liq_buffer_%'])
        print(f"  {cfg_name:<22} {bad_day:>+17.2%}  {n_days:>12} days  ${liq_at:>8,.2f}")

    # ── Monte Carlo with path-dependent liquidation ──
    print_sep("MONTE CARLO — PATH-DEPENDENT LIQUIDATION (10,000 sims, 1yr)")
    print()
    for cfg_name, lev_map in configs.items():
        mg = margin_analysis(avail, lev_map, ACCOUNT_SIZE)
        liq_threshold = -(mg['liq_buffer_%'])
        mc = monte_carlo_ruin(port_rets[cfg_name], n_sims=10000, n_days=365,
                              liq_threshold=liq_threshold, account_size=ACCOUNT_SIZE)
        print(f"  {cfg_name}  (liq threshold: {liq_threshold:.1%})")
        print(f"    P(liquidation)  : {mc['p_ruin']:.2%}")
        print(f"    P(loss)         : {mc['p_loss']:.2%}")
        print(f"    P(DD > 10%)     : {mc['p_dd_10']:.1%}")
        print(f"    P(DD > 20%)     : {mc['p_dd_20']:.1%}")
        print(f"    P(DD > 30%)     : {mc['p_dd_30']:.1%}")
        print(f"    Median 1yr ret  : {mc['median_return']:+.1%}  "
              f"  [5th: {mc['p5_return']:+.1%} / 95th: {mc['p95_return']:+.1%}]")
        print(f"    P(>50% return)  : {mc['p_gt50']:.1%}")
        print(f"    P(>100% return) : {mc['p_gt100']:.1%}")
        print()

    # ── Worst day breakdown ──
    print_sep("WORST DAYS")
    for cfg_name in ['No-H011 1x', 'No-H011 2x MN', 'No-H011 3x MN']:
        pr = port_rets[cfg_name]
        worst = pr.sort_values().head(5)
        print(f"\n  {cfg_name}:")
        for dt, r in worst.items():
            print(f"    {dt.date()}  {r:+.2%}  (${r*ACCOUNT_SIZE:+.2f})")

    # ── Year-by-year ──
    print_sep("YEAR-BY-YEAR RETURNS")
    print(f"\n  {'Year':<6}", end="")
    for cn in configs:
        print(f" {cn[:18]:>19}", end="")
    print()
    for year in [2024, 2025, 2026]:
        print(f"  {year:<6}", end="")
        for cn, pr in port_rets.items():
            yr = pr[pr.index.year == year]
            if len(yr) > 20:
                ann = (1 + yr).prod() ** (365 / len(yr)) - 1
                print(f" {ann:>+18.1%}", end="")
            else:
                print(f" {'n/a':>19}", end="")
        print()

    print("\n[Done]")


if __name__ == '__main__':
    main()
