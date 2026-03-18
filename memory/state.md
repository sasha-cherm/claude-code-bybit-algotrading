# Strategy State

## Active Paper Trades

### H-009: BTC Daily EMA Trend Following (VT 20%)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: LONG 0.054885 BTC @ $73,524.10
- **Mark equity**: $9,875 (-1.25%) — live mark @ BTC $71,324
- **Leverage**: 0.40x (vol targeting: 50.0% realized -> 20% target)
- **Runner**: `paper_trades/h009_btc_daily_trend/runner.py`
- **Signal**: EMA(5) > EMA(40) on daily close -> LONG. **Gap still narrowing. Flip to SHORT if daily close < ~$70,579.**
- **Next check**: Next daily bar close

### H-011: Leveraged Funding Rate Arb (5x)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: OUT (rolling-27 avg funding negative, since 2026-03-07)
- **Capital**: $10,000.00
- **Runner**: `paper_trades/h011_funding_rate_arb/runner.py`
- **Funding trend**: Rolling-7 at -1.4% ann. **Projected re-entry: 2026-03-22 to 2026-03-23**.
- **Next check**: Next funding settlement

### H-012: Cross-Sectional Momentum (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: BTC (-$94), NEAR (-$58), ATOM (-$98), AVAX (-$133)
  - SHORT: SOL (+$118), SUI (+$177), ARB (+$147), OP (+$112)
- **Mark equity**: $10,142 (+1.42%) — **short side dominating** (+$554 vs -$383 longs)
- **Runner**: `paper_trades/h012_xsmom/runner.py`
- **Params**: 60d lookback, 5d rebalance, top/bottom 4
- **Next rebal**: 2026-03-21 (3 days)

### H-019: Low-Volatility Anomaly (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-18)
- **Position**: 6 positions (3 long, 3 short)
  - LONG (low vol): ATOM (-$215), ARB (-$159), XRP (-$113)
  - SHORT (high vol): DOGE (+$134), DOT (+$146), NEAR (+$132)
- **Mark equity**: $9,927 (-0.73%)
- **Runner**: `paper_trades/h019_lowvol/runner.py`
- **Params**: 20d vol window, 21d rebalance, top/bottom 3
- **Next rebal**: 2026-04-08 (21 days)

### H-021: Volume Momentum Factor (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-18)
- **Position**: 8 positions (4 long, 4 short)
  - LONG (vol surge): DOT (-$1), LINK (+$5), XRP (+$4), DOGE (+$5)
  - SHORT (vol drop): ARB (-$5), SUI (-$4), NEAR (-$17), ATOM (-$6)
- **Mark equity**: $9,939 (-0.61%)
- **Runner**: `paper_trades/h021_volmom/runner.py`
- **Params**: VS5_VL20_R3_N4 (5d/20d volume ratio, 3-day rebalance, top/bottom 4)
- **Next rebal**: 2026-03-21 (3 days)

### H-024: Low-Beta Anomaly (14 Assets) — NEW, comparison
- **Status**: LIVE paper trade (started 2026-03-18) — **comparing against H-019**
- **Position**: 6 positions (3 long, 3 short)
  - LONG (low beta): ATOM (-$1), OP (-$1), BTC (-$1)
  - SHORT (high beta): XRP (-$1), NEAR (-$1), SUI (-$1)
- **Mark equity**: $9,975 (-0.25%) — just deployed, fee drag only
- **Runner**: `paper_trades/h024_beta/runner.py`
- **Params**: W60_R21_N3 (60d rolling beta vs BTC, 21d rebalance, top/bottom 3)
- **Next rebal**: 2026-04-08 (21 days)
- **Note**: In backtests, H-024 dominates H-019 at every param set (12/12), WF 5/6 positive (mean 2.12). Portfolio Sharpe improves from 1.80 to 2.33 by replacing H-019. Tracking in parallel for live comparison.

## Portfolio Summary (live mark-to-market 2026-03-18 21:10 UTC)
- **Total equity**: $49,883 (-0.23%) — 5-strat portfolio only
- **H-009**: $9,875 (-1.25%) | **H-011**: $10,000 (0%) | **H-012**: $10,142 (+1.42%) | **H-019**: $9,927 (-0.73%) | **H-021**: $9,939 (-0.61%)
- **H-024 (comparison)**: $9,975 (-0.25%)
- **Paper trade age**: H-009/H-011/H-012: 2 days / 28 required. H-019/H-021/H-024: day 0.
- **BTC at $71,324** — portfolio essentially flat despite -4.3% BTC 24h drop.

## Target Portfolio Allocation (5-strat)
- **10% H-009** (BTC daily trend): directional alpha, Sharpe ~0.6-0.9
- **40% H-011** (funding rate arb): carry alpha, Sharpe ~15-25
- **10% H-012** (cross-sectional momentum): relative value alpha, Sharpe ~0.8-1.1
- **15% H-019** (low-volatility anomaly): cross-sectional factor, Sharpe ~0.7-1.2
- **25% H-021** (volume momentum): cross-sectional factor, Sharpe ~1.5-1.8
- **Combined (5-strat)**: Sharpe 2.10, +31.6%, 12.9% DD

## Proposed Upgrade: Replace H-019 with H-024
- **If confirmed in paper trade**: H-024 (beta) replaces H-019 (vol) at same 15% allocation
- **Projected upgrade**: Portfolio Sharpe 2.10 → 2.33, return +31.6% → higher
- **Rationale**: Beta beats vol 12/12 at matched params. WF 5/6 vs 5/8. Fee-robust (1.48 at 5x).
- **Decision point**: After 4 weeks of parallel paper trading

## Key Correlations
- All pairwise near zero — ideal diversification
  - H-009/H-011: -0.033, H-009/H-012: 0.001, H-009/H-019: -0.094, H-009/H-021: -0.068
  - H-012/H-019: 0.076, H-012/H-021: 0.057, H-019/H-021: -0.032
  - **H-024/H-019: 0.660** (high — these are related factors, beta vs total vol)
  - H-024/H-012: 0.319, H-024/H-009: -0.027, H-024/H-021: 0.069

## Active Live Strategies
(none)

## Recently Killed
(none)

## Research Pipeline
| Hypothesis | Status | Priority | Next Step |
|-----------|--------|----------|-----------|
| H-010: Multi-Strategy Portfolio | BACKTEST | Low | Superseded by 5-strat portfolio analysis |

## Risk Watch
- **BTC selloff continuing**: BTC at $71,324 (-4.3% 24h), touched $70,495. H-009 LONG signal fragile — watch daily close vs ~$70,579.
- **H-012 best performer**: +1.42% — short side (+$554) dominating. Market-neutral design proven.
- **H-019 vs H-024**: Both just deployed. Tracking in parallel. Backtest says H-024 >> H-019.
- **H-021 slightly negative**: -0.61%, first rebal in 3 days.
- **Funding rate**: Rolling-7 at -1.4% ann. **H-011 re-entry ~Mar 22-23.**
- **Diversification working**: 4.3% BTC drop → only 0.23% portfolio loss across 5 strategies.
- **Watchlist**: H-009 signal flip risk. H-011 re-entry ~Mar 22-23. H-012 + H-021 rebalance 2026-03-21.

## Rejected Strategies
| Hypothesis | Reason |
|-----------|--------|
| H-001: EMA Crossover (4h) | Superseded by H-008/H-009 (daily better than 4h) |
| H-002: BB Mean Reversion (spot) | Long-only fails in bear market. All params negative. |
| H-003: Cross-Asset Momentum | Returns too low (<4%), drawdown too high (39%). |
| H-004: Volatility Breakout (1h) | All params negative. BTC 1h breakouts lack follow-through. |
| H-005: Funding Rate Arb (1x) | Returns too low at 1x (1.7-3.1%). Superseded by H-011 (5x). |
| H-006: Adaptive Mean Reversion (1h) | All params negative even with regime filter. |
| H-007: BTC/ETH Pairs Trading | Structural BTC/ETH divergence defeats mean reversion. |
| H-013: Multi-Asset Funding Arb | Rates too correlated (r=0.49), fees kill multi-asset rotation. |
| H-014: Anti-Martingale | Fails walk-forward (1/4 folds). Corr 0.42 with H-009, redundant. |
| H-015: RSI Mean Reversion | 0/4 OOS folds positive. Interesting -0.73 corr with H-009 but no edge. |
| H-016: BB Squeeze Breakout | Only 18 trades in 2yr. 36% params positive. Overfit. |
| H-017: MTF Momentum | Corr 0.89 with H-009. 44-51% DD. Redundant. |
| H-018: Short-Term Reversal | 4% positive. Crypto momentum dominates, reversal doesn't work. |
| H-020: Funding Rate Dispersion | 0% positive. Cross-sectional carry doesn't work (rates too correlated). |
| H-022: Amihud Illiquidity | 0% positive. Illiquidity premium doesn't exist in crypto. |
| H-023: Price-Volume Confirmation | 93% positive, but corr 0.864 with H-012 — redundant with momentum. |
| H-025: Skewness Factor | 15% positive. No edge in crypto. |
| H-026: Drawdown Distance | 97% positive but corr 0.682 with H-012 — redundant with momentum. |

## Infrastructure Status
- Data fetcher: operational (ccxt, parquet caching)
- Metrics library: operational
- Backtest engine: operational (event-driven, spot + futures + pairs modes)
- H-008 strategy code with walk-forward validation framework
- H-010 multi-strategy research framework
- H-012 research + validation framework (XSMom)
- Cross-sectional factor research framework (`strategies/new_factors_research/`)
- H-019 deep validation v2 framework
- H-021 volume factor research + deep validation
- **H-024 beta factor research + deep validation** — NEW
- H-009 paper trade runner (internal simulation)
- H-011 paper trade runner (funding rate arb simulation)
- H-012 paper trade runner (XSMom, internal simulation)
- H-019 paper trade runner (LowVol, internal simulation)
- H-021 paper trade runner (VolMom, internal simulation)
- **H-024 paper trade runner** (Beta, internal simulation) — NEW
- **Portfolio monitor**: `scripts/portfolio_monitor.py` — live mark-to-market across all 6 strategies (5 portfolio + 1 comparison)
- Cached data (1h, 2yr): BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM (14 assets)
- Cached data: BTC funding rates (2yr, 2199 records)
- Cached data: 14-asset funding rates (2yr, 2190 records each)

## Key Learnings
- 2024-2026 BTC: +1.8% total, 50% drawdown -- extremely hostile for directional strategies
- Daily EMA crossover is a real signal on BTC: OOS Sharpe 0.94, parameter robust (15/15 positive)
- Multi-asset selection via past Sharpe fails walk-forward -- crypto assets too regime-dependent
- Vol targeting works: controls DD proportionally (15% vol target -> ~10% DD)
- **Funding rate arb at 5x leverage is viable**: OOS +25.4% annual, 0.14% DD, Sharpe 29.9
- **Cross-sectional momentum is a genuine signal**: 100% params positive, rolling OOS Sharpe 0.84
- **Low-volatility anomaly works in crypto**: 89% params positive, 5/8 WF folds, fee-robust
- **Volume momentum is a genuine cross-sectional signal**: 90% params positive, **6/6 WF folds** (mean OOS 1.83). Only works at high-frequency rebal (3-day).
- **Low-beta anomaly is stronger than low-vol**: 100% IS positive, 5/6 WF (mean 2.12). Beats vol at all 12 matched param sets. Portfolio Sharpe 1.80→2.33.
- **Skewness doesn't work in crypto**: only 15% IS positive. Lottery premium absent.
- **Drawdown distance ≈ momentum**: 97% IS positive but r=0.682 with H-012. Redundant.
- **All active strategies are uncorrelated**: pairwise r near 0 — ideal diversification
- **5-strategy portfolio**: Sharpe 2.10, +31.6%, 12.9% DD — exceeds all targets
- **26 hypotheses tested total**: 5 in paper trade + 1 comparison (H-024), 20 rejected
- **Risk**: funding rates declining (Q1 2024: 22.7% -> Q1 2026: 1.6%) -- rolling-27 negative since 2026-03-07
- Fee drag critical at 1h; daily/3-day/5-day/21-day rebalance minimizes fee impact
- **All 5 portfolio strategies now in paper trade + H-024 comparison** -- monitor for >=4 weeks before live consideration
