# Strategy State

## Active Paper Trades

### H-009: BTC Daily EMA Trend Following (VT 20%)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: LONG 0.054885 BTC @ $73,524.10
- **Mark equity**: $9,858 (-1.42%) — live mark @ BTC $71,017
- **Leverage**: 0.40x (vol targeting: 50.0% realized -> 20% target)
- **Runner**: `paper_trades/h009_btc_daily_trend/runner.py`
- **Signal**: EMA(5) > EMA(40) on daily close -> LONG. **Gap narrowing: +0.84%. Flip to SHORT if daily close < $70,579.**
- **Next check**: Next daily bar close — **signal at risk if BTC continues dropping**

### H-011: Leveraged Funding Rate Arb (5x)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: OUT (rolling-27 avg funding negative, since 2026-03-07)
- **Capital**: $10,000.00
- **Runner**: `paper_trades/h011_funding_rate_arb/runner.py`
- **Funding trend**: Rolling-27 at -1.6% ann. BTC selloff generating negative rates. **Projected re-entry: 2026-03-22 to 2026-03-23** (pushed back from Mar 20 due to new negative rates).
- **Next check**: Next funding settlement

### H-012: Cross-Sectional Momentum (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: BTC (-$100), NEAR (-$88), ATOM (-$105), AVAX (-$162)
  - SHORT: SOL (+$147), SUI (+$193), ARB (+$193), OP (+$137)
- **Mark equity**: $10,195 (+1.95%) — **short side dominating** (+$670 vs -$455 longs). Market drop benefits shorts.
- **Runner**: `paper_trades/h012_xsmom/runner.py`
- **Params**: 60d lookback, 5d rebalance, top/bottom 4
- **Next rebal**: 2026-03-21 (3 days)

### H-019: Low-Volatility Anomaly (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-18)
- **Position**: 6 positions (3 long, 3 short)
  - LONG (low vol): ATOM (-$223), ARB (-$221), XRP (-$141)
  - SHORT (high vol): DOGE (+$157), DOT (+$191), NEAR (+$171)
- **Mark equity**: $9,914 (-0.86%) — longs hit harder than shorts benefit from market drop
- **Runner**: `paper_trades/h019_lowvol/runner.py`
- **Params**: 20d vol window, 21d rebalance, top/bottom 3
- **Next rebal**: 2026-04-08 (21 days)

## Portfolio Summary (live mark-to-market 2026-03-18 17:00 UTC)
- **Total equity**: $40,004 (+0.01%)
- **H-009**: $9,868 (-1.32%) | **H-011**: $10,000 (0%) | **H-012**: $10,177 (+1.77%) | **H-019**: $9,957 (-0.43%)
- **Paper trade age**: H-009/H-011/H-012: 2 days / 28 required. H-019: day 0.
- **BTC at $71,194** — portfolio essentially flat despite -3.9% BTC drop.

## Target Portfolio Allocation (current 4-strat)
- **15% H-009** (BTC daily trend): directional alpha, Sharpe ~0.6-0.9
- **50% H-011** (funding rate arb): carry alpha, Sharpe ~15-25
- **15% H-012** (cross-sectional momentum): relative value alpha, Sharpe ~0.8-1.1
- **20% H-019** (low-volatility anomaly): cross-sectional factor, Sharpe ~0.7-1.2
- **Combined (4-strat, actual H-009 equity)**: Sharpe 1.75, +23.8%, 14.0% DD
- **Correlations**: H-009/H-011: -0.033, H-009/H-012: 0.001, H-011/H-012: 0.006, H-009/H-019: -0.094, H-012/H-019: 0.076

## Potential 5-Strategy Allocation (with H-021)
- **10% H-009** | **40% H-011** | **10% H-012** | **15% H-019** | **25% H-021**
- **Combined**: Sharpe 2.10, +31.6%, 12.9% DD (up from 1.75/23.8%/14.0%)
- **H-021 correlations**: H-009 -0.068, H-012 0.057, H-019 -0.032 (near-zero with all)

## Active Live Strategies
(none)

## Recently Killed
(none)

## Research Pipeline
| Hypothesis | Status | Priority | Next Step |
|-----------|--------|----------|-----------|
| H-021: Volume Momentum | CONFIRMED | **High** | Deploy paper trade runner (3-day rebal, VS5_VL20_R3_N4) |
| H-010: Multi-Strategy Portfolio | BACKTEST | Low | Superseded by 5-strat portfolio analysis |

## Risk Watch
- **BTC SELLOFF ongoing**: BTC at $71,194 (-3.9%). H-009 LONG signal fragile — watch daily close vs $70,579.
- **H-012 best performer**: +1.77% — short side (+$652) dominating. Market-neutral design proven.
- **H-019 recovering**: -0.43% (up from -0.86%). Short side benefiting from broad market drop.
- **Funding rate**: Rolling-7 at -1.4% ann. **H-011 re-entry ~Mar 22-23.**
- **Diversification working**: 3.9% BTC drop → only 0.01% portfolio change.
- **Watchlist**: H-009 signal flip risk. H-011 re-entry ~Mar 22-23. H-012 rebalance 2026-03-21. **H-021 paper trade deployment next session.**

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

## Infrastructure Status
- Data fetcher: operational (ccxt, parquet caching)
- Metrics library: operational
- Backtest engine: operational (event-driven, spot + futures + pairs modes)
- H-008 strategy code with walk-forward validation framework
- H-010 multi-strategy research framework
- H-012 research + validation framework (XSMom)
- Cross-sectional factor research framework (`strategies/new_factors_research/`)
- H-019 deep validation v2 framework (`strategies/new_factors_research/h019_deep_validation_v2.py`)
- **H-021 volume factor research** (`strategies/new_factors_research/volume_factors_research.py`)
- **H-021 deep validation** (`strategies/new_factors_research/h021_deep_validation.py`)
- H-009 paper trade runner (internal simulation)
- H-011 paper trade runner (funding rate arb simulation)
- H-012 paper trade runner (XSMom, internal simulation)
- **H-019 paper trade runner** (LowVol, internal simulation) -- NEW
- **Portfolio monitor**: `scripts/portfolio_monitor.py` — live mark-to-market across all 4 strategies
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
- **All four strategies are uncorrelated**: pairwise r near 0 -- ideal diversification
- **4-strategy portfolio**: Sharpe 1.75, +23.8%, 14.0% DD (corrected with actual H-009 equity)
- **Volume momentum is a genuine cross-sectional signal**: 90% params positive, 6/6 WF folds (mean OOS 1.83). Only works at high-frequency rebal (3-day).
- **Amihud illiquidity premium doesn't exist in crypto**: 0/48 positive. Illiquid = underperforming.
- **Price-volume confirmation = momentum in disguise**: 0.864 corr with H-012 at 60d lookback.
- **5-strategy portfolio (with H-021)**: Sharpe 2.10, +31.6%, 12.9% DD — significant improvement over 4-strat
- **23 hypotheses tested total**: H-009/H-011/H-012/H-019 in paper trade, H-021 confirmed, 18 rejected
- **Risk**: funding rates declining (Q1 2024: 22.7% -> Q1 2026: 1.6%) -- rolling-27 negative since 2026-03-07
- Fee drag critical at 1h; daily/5-day/21-day rebalance minimizes fee impact
- **All 4 strategies now in paper trade** -- monitor for >=4 weeks before live consideration
- **20 hypotheses tested total**: H-009/H-011/H-012/H-019 in paper trade, 16 rejected
