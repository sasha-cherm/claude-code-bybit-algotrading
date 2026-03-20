# Strategy State

## Active Paper Trades

### H-009: BTC Daily EMA Trend Following (VT 20%)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: SHORT 0.053871 BTC @ $69,909.32 — **FLIPPED from LONG** (session 44)
- **Mark equity**: $9,789 (-2.11%) — closed LONG at loss ($-202), now SHORT
- **Leverage**: 0.38x (vol targeting: 52% realized -> 20% target)
- **Runner**: `paper_trades/h009_btc_daily_trend/runner.py`
- **Signal**: EMA(5) < EMA(40) confirmed on Mar 19 close ($69,923). Gap widening (-0.55%).
- **Bug fixed**: Incomplete daily bar bug — runner was processing intra-day bars as complete. Fixed in all 10 runners.
- **Next check**: Next daily bar close (00:00 UTC 2026-03-21)

### H-011: Leveraged Funding Rate Arb (5x)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: OUT (rolling-27 avg funding negative, since 2026-03-07)
- **Capital**: $10,000.00
- **Runner**: `paper_trades/h011_funding_rate_arb/runner.py`
- **Funding trend**: R27 at -2.75% ann. **Re-entry pushed to ~2026-03-25 to 2026-03-26** (5.3 days).
- **Next check**: Next funding settlement

### H-012: Cross-Sectional Momentum (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: BTC, NEAR, ATOM, AVAX
  - SHORT: SOL, SUI, ARB, OP
- **Mark equity**: $10,098 (+0.98%) — short side dominating in selloff
- **Runner**: `paper_trades/h012_xsmom/runner.py`
- **Params**: 60d lookback, 5d rebalance, top/bottom 4
- **Next rebal**: 2026-03-21 (1 day)

### H-019: Low-Volatility Anomaly (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-18)
- **Position**: 6 positions (3 long, 3 short)
  - LONG (low vol): ATOM, ARB, XRP
  - SHORT (high vol): DOGE, DOT, NEAR
- **Mark equity**: $9,938 (-0.62%)
- **Runner**: `paper_trades/h019_lowvol/runner.py`
- **Params**: 20d vol window, 21d rebalance, top/bottom 3
- **Next rebal**: 2026-04-08 (19 days)

### H-021: Volume Momentum Factor (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-18)
- **Position**: 8 positions (4 long, 4 short)
  - LONG (vol surge): DOT, LINK, XRP, DOGE
  - SHORT (vol drop): ARB, SUI, NEAR, ATOM
- **Mark equity**: $10,136 (+1.36%) — best performer
- **Runner**: `paper_trades/h021_volmom/runner.py`
- **Params**: VS5_VL20_R3_N4 (5d/20d volume ratio, 3-day rebalance, top/bottom 4)
- **Next rebal**: 2026-03-21 (1 day)

### H-024: Low-Beta Anomaly (14 Assets) — comparison
- **Status**: LIVE paper trade (started 2026-03-18) — **comparing against H-019**
- **Position**: 6 positions (3 long, 3 short)
  - LONG (low beta): ATOM, OP, BTC
  - SHORT (high beta): XRP, NEAR, SUI
- **Mark equity**: $9,885 (-1.16%)
- **Runner**: `paper_trades/h024_beta/runner.py`
- **Params**: W60_R21_N3 (60d rolling beta vs BTC, 21d rebalance, top/bottom 3)
- **Next rebal**: 2026-04-08 (19 days)
- **Note**: H-019 still leading (-0.62% vs -1.16%). Gap widened.

### H-031: Size Factor (Dollar Volume Proxy, Long Large) — independent
- **Status**: LIVE paper trade (started 2026-03-19) — independent
- **Position**: 10 positions (5 long, 5 short)
  - LONG (large cap): BTC, ETH, SOL, XRP, DOGE
  - SHORT (small cap): LINK, DOT, OP, ARB, ATOM
- **Mark equity**: $10,026 (+0.26%)
- **Runner**: `paper_trades/h031_size/runner.py`
- **Params**: W30_R5_N5 (30-day avg dollar volume, 5-day rebalance, top/bottom 5)
- **Next rebal**: 2026-03-24 (4 days)

### H-032: Cointegration Pairs (8-pair portfolio) — independent
- **Status**: LIVE paper trade (started 2026-03-19) — independent, experimental
- **Position**: ALL FLAT — waiting for z-score entry signals
- **Pairs**: DOT/ATOM, DOGE/LINK, DOGE/ADA, DOT/OP, SOL/DOGE, AVAX/DOT, NEAR/OP, ARB/ATOM
- **Mark equity**: $10,000 (0%)
- **Runner**: `paper_trades/h032_pairs/runner.py`
- **Note**: OOS Sharpe 1.33, DD 5.8%. Entries are infrequent.

### H-037: Polymarket 1hr BTC UP/DOWN (Manual Paper Trade)
- **Status**: CONFIRMED for paper trade (started 2026-03-19) — MANUAL, Polymarket only
- **Position**: No trades yet
- **Target hours (UTC)**: 17:00 (UP), 21:00 (UP), 22:00 (UP), 23:00 (DOWN), 13:00 (DOWN)
- **Tracker**: `paper_trades/h037_polymarket/tracker.py`

### H-039: Day-of-Week Seasonality (Long Wed / Short Thu) — independent
- **Status**: LIVE paper trade (started 2026-03-19) — independent
- **Position**: FLAT (first trade: Tue Mar 24 close → enter LONG for Wed)
- **Capital**: $10,000.00
- **Runner**: `paper_trades/h039_dow_seasonality/runner.py`
- **Backtest**: WF **6/6** positive (mean OOS Sharpe **2.46**)

### H-044: OI-Price Divergence Factor (14 Assets) — independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 10 positions (5 long, 5 short)
  - LONG (price up + OI down): SUI, OP, NEAR, SOL, ETH
  - SHORT (price down + OI up): ADA, ARB, DOT, XRP, DOGE
- **Mark equity**: $9,984 (-0.16%)
- **Runner**: `paper_trades/h044_oi_divergence/runner.py`
- **Next rebal**: 2026-03-29 (9 days)

### H-046: Price Acceleration Factor (14 Assets) — independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 8 positions (4 long, 4 short)
  - LONG (accelerating): OP, ARB, NEAR, SUI
  - SHORT (decelerating): DOGE, LINK, ADA, DOT
- **Mark equity**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h046_acceleration/runner.py`
- **Next rebal**: 2026-03-22 (2 days)

### H-049: LSR Sentiment Factor (Contrarian, 14 Assets) — NEW, independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 6 positions (3 long, 3 short)
  - LONG (crowd short): BTC, ETH, LINK
  - SHORT (crowd long): ARB, SUI, OP
- **Mark equity**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h049_lsr_sentiment/runner.py`
- **Params**: R5_N3 (5-day rebalance, top/bottom 3, contrarian direction)
- **Next rebal**: 2026-03-24 (5 days)
- **Backtest (200 days only)**: IS Sharpe 2.58, +59.1% ann, 7.2% DD. 100% params positive (12/12). Split-half: 2.01 / 3.75. Fee-robust (1.58 at 5x fees).
- **Correlations**: -0.091 H-012, -0.127 H-019, 0.231 H-021, **0.581 H-046** (high)
- **CAVEAT**: Only 200 days of backtest data (~6.5 months) vs 2-year standard. Needs extended paper trade to build confidence.
- **Data source**: Bybit long/short ratio — genuinely new data source (first non-price/volume/OI signal).

### H-052: Premium Index Factor (Contrarian, 14 Assets) — NEW, independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 8 positions (4 long, 4 short)
  - LONG (most discounted): ARB, ATOM, ETH, LINK
  - SHORT (least discounted): OP, DOGE, NEAR, SOL
- **Mark equity**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h052_premium/runner.py`
- **Params**: W5_R5_N4 (5-day premium window, 5-day rebalance, top/bottom 4, contrarian)
- **Next rebal**: 2026-03-24 (5 days)
- **Backtest (full 2yr)**: IS 100% positive (30/30). Best Sharpe 2.25. WF 6/6 positive (mean 1.86). Split-half: 2.18/2.95.
- **Correlations**: -0.142 H-012, 0.097 H-021, 0.167 H-046 (low/negative — great diversifier)
- **Data source**: Bybit premium index (perp-vs-spot premium/discount) — genuinely new data source.

### H-053: Funding Rate Cross-Sectional Factor (Contrarian, 14 Assets) — NEW, independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 8 positions (4 long, 4 short)
  - LONG (lowest funding): DOT, ATOM, SOL, BTC
  - SHORT (highest funding): OP, NEAR, ARB, ADA
- **Mark equity**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h053_funding_xs/runner.py`
- **Params**: W3_R10_N4 (3-day funding avg, 10-day rebalance, top/bottom 4, contrarian)
- **Next rebal**: 2026-03-29 (10 days)
- **Backtest (full 2yr)**: IS 93% positive (42/45). Best Sharpe 1.52, +32.9% ann, 22.2% DD. **WF 6/6 positive (mean OOS 2.29)**. Split-half: 1.31/1.91. Fee-robust (0.92 at 5x fees).
- **Correlations**: 0.004 H-012, 0.109 H-046, **0.360 H-052** (moderate — related contrarian signals), **0.480 H-049** (high)
- **Data source**: Bybit funding rates (8h, aggregated to daily avg) — same underlying market positioning as H-052 (premium).

## Portfolio Summary (live mark-to-market 2026-03-20 session 47)
- **Total equity**: $49,863 (-0.27%) — 5-strat portfolio only
- **H-009**: $9,769 (-2.31%, SHORT) | **H-011**: $10,000 (0%) | **H-012**: $10,077 (+0.77%) | **H-019**: $9,939 (-0.61%) | **H-021**: $10,078 (+0.78%)
- **H-024 (comparison)**: $9,947 (-0.53%) — **H-024 now leads H-019** (-0.53% vs -0.61%)
- **H-031 (independent)**: ~$9,980 (-0.20%) | **H-032 (independent)**: $10,000 (0%)
- **H-037 (Polymarket, manual)**: $0 (no trades yet) | **H-039 (DOW, independent)**: $10,000 (flat, first trade Mar 24)
- **H-044 (OI divergence)**: $9,980 (-0.20%) | **H-046 (Acceleration)**: $9,980 (-0.20%)
- **H-049 (LSR sentiment)**: $9,980 (-0.20%) | **H-052 (Premium)**: $9,980 (-0.20%)
- **H-053 (Funding XS, NEW)**: $9,976 (-0.24%)
- **Paper trade age**: H-009/H-011/H-012: 4 days / 28 required. H-019/H-021/H-024: 2 days. H-031/H-032/H-039: 1 day. H-044/H-046/H-049/H-052/H-053: 0 days.
- **BTC at ~$70,302** — H-009 SHORT.

## Target Portfolio Allocation (5-strat)
- **10% H-009** (BTC daily trend): directional alpha, Sharpe ~0.6-0.9
- **40% H-011** (funding rate arb): carry alpha, Sharpe ~15-25
- **10% H-012** (cross-sectional momentum): relative value alpha, Sharpe ~0.8-1.1
- **15% H-019** (low-volatility anomaly): cross-sectional factor, Sharpe ~0.7-1.2
- **25% H-021** (volume momentum): cross-sectional factor, Sharpe ~1.5-1.8
- **Combined (5-strat)**: Sharpe 2.10, +31.6%, 12.9% DD

## Proposed Upgrade: Replace H-019 with H-024
- **If confirmed in paper trade**: H-024 (beta) replaces H-019 (vol) at same 15% allocation
- **Current status**: H-024 -0.53% vs H-019 -0.61% — **H-024 now leading** (gap reversed session 47)
- **Decision point**: After 4 weeks of parallel paper trading

## Key Correlations
- All pairwise near zero — ideal diversification
  - H-009/H-011: -0.033, H-009/H-012: 0.001, H-009/H-019: -0.094, H-009/H-021: -0.068
  - H-012/H-019: 0.076, H-012/H-021: 0.057, H-019/H-021: -0.032
  - **H-024/H-019: 0.660** (high — these are related factors)
  - **H-049/H-046: 0.581** (high — sentiment and acceleration correlated)
  - H-049/H-012: -0.091 (near zero)
  - **H-052/H-012: -0.142** (negative — excellent diversifier!)
  - H-052/H-021: 0.097, H-052/H-046: 0.167 (low)
  - **H-053/H-012: 0.004** (near zero — excellent!)
  - H-053/H-046: 0.109 (low), **H-053/H-052: 0.360** (moderate — related signals)
  - **H-053/H-049: 0.480** (high — both contrarian positioning)

## Active Live Strategies
(none)

## Recently Killed
(none)

## Research Pipeline
| Hypothesis | Status | Priority | Next Step |
|-----------|--------|----------|-----------|
| H-010: Multi-Strategy Portfolio | BACKTEST | Low | Superseded by 5-strat portfolio analysis |

## Risk Watch
- **H-009 SHORT**: EMA gap widening. PnL: -2.31%.
- **H-024 overtook H-019**: -0.53% vs -0.61%. First time H-024 leads. Still too early to decide (2 days vs 28 required).
- **H-021 best performer**: +0.78%. H-012 at +0.77%.
- **H-053 CONFIRMED + DEPLOYED**: Funding rate XS contrarian — WF 6/6 (mean OOS 2.29). Corr 0.36 with H-052, 0.48 with H-049 (moderate overlap). LONG DOT/ATOM/SOL/BTC, SHORT OP/NEAR/ARB/ADA.
- **Funding rate**: R27 negative. H-011 re-entry pushed to ~Mar 25-26.
- **Portfolio dipping**: -0.27% (was -0.08%). BTC at $70,302 (down from $70,477).
- **Research status**: 53 hypotheses tested, 40 rejected, 3 confirmed standalone, 14 in paper trade + 1 comparison + 1 manual.
- **Liquidation data NOT available**: Bybit API has no historical liquidation endpoint. Would need WebSocket collector (60-90 day build).
- **IV collector**: Daily cron at 01:00 UTC. Building history.
- **OB depth collector**: Daily cron at 01:30 UTC. Building history.
- **Watchlist**: H-012 + H-021 rebal Mar 21. H-046 rebal Mar 22. H-039 first trade Mar 24. H-049 + H-031 + H-052 rebal Mar 24. H-011 re-entry ~Mar 25-26. H-053 + H-044 rebal Mar 29.
- **Open user questions**: None

## Automation
- **Paper trade orchestrator**: `scripts/run_all_paper_trades.py` — runs all 14 active runners sequentially
- **Cron schedule**: Every hour at :30 (`30 * * * *`), independent of Claude sessions
- **Logs**: `logs/paper_trades.log`
- **Claude sessions**: Every 2 hours at :00 — research, monitoring, strategy updates

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
| H-013: Multi-Asset Funding Arb | Rates too correlated (r=0.49), fees kill rotation. |
| H-014: Anti-Martingale | Fails WF (1/4). Corr 0.42 with H-009, redundant. |
| H-015: RSI Mean Reversion | 0/4 OOS folds positive. |
| H-016: BB Squeeze Breakout | Only 18 trades in 2yr. Overfit. |
| H-017: MTF Momentum | Corr 0.89 with H-009. Redundant. |
| H-018: Short-Term Reversal | 4% positive. Momentum dominates. |
| H-020: Funding Rate Dispersion | 0% positive. Rates too correlated. |
| H-022: Amihud Illiquidity | 0% positive. No illiquidity premium in crypto. |
| H-023: Price-Volume Confirmation | Corr 0.864 with H-012. Redundant. |
| H-025: Skewness Factor | 15% positive. No edge. |
| H-026: Drawdown Distance | Corr 0.682 with H-012. Redundant. |
| H-027: Lead-Lag XS | 1% positive. Not exploitable at 1h. |
| H-028: Volume Trend Change | 6% positive. Fails WF. |
| H-029: Hourly XS Momentum | Corr 0.484 with H-012. Redundant. |
| H-033: Idiosyncratic Momentum | Corr 0.832 with H-012. Fails WF. |
| H-034: Funding Rate BTC Timing | 49% positive (noise). No edge. |
| H-035: Momentum + Vol Timing | WF 3/4, mean 0.76. Enhancement only. |
| H-036: Intraday Seasonality | Real patterns but untradeable (Sharpe 0.30 max). |
| H-040: Vol Regime Factor Timing | Negative OOS. Doesn't help. |
| H-041: BTC Dominance Rotation | 100% look-ahead bias. 1/16 params positive. |
| H-043: OI Change XS Factor | 34% IS positive. Fails WF. |
| H-047: Volatility Change Factor | 50% positive = noise. No signal in vol dynamics. |
| H-048: Correlation Change Factor | 50% positive = noise. No signal in correlation dynamics. |
| H-050: Inter-Market Macro Signals | 50% positive = noise. Lagged corr all <0.08. Info priced in same-day. |
| H-051: Monthly Calendar Seasonality | DOM train/test corr -0.13. WF 3/6. No persistence. |

## Confirmed Standalone (not in portfolio)
| Hypothesis | Metrics | Why Not In Portfolio |
|-----------|---------|---------------------|
| H-030: Composite Multi-Factor | Sharpe 2.05, +101.7% ann, 25% DD, WF 5/6 | Individual strategies beat composite |
| H-038: ML Factor Combo (Ridge) | Sharpe 1.43, +26.2% ann, 9.6% DD, WF 2/3 | Train window sensitive, fragile |
| H-042: Short-Term XSMom (20d) | Sharpe 1.17 IS, WF 4/6, mean OOS 0.55 | Corr 0.686 with H-012, redundant |
| H-045: OI-Volume Confirmation | Robust variant WF 3/4, rebal-sensitive | Not deployed, weak |

## Infrastructure Status
- Data fetcher: operational (ccxt, parquet caching)
- Metrics library: operational
- Backtest engine: operational
- **Paper trade runners**: 14 active (H-009, H-011, H-012, H-019, H-021, H-024, H-031, H-032, H-039, H-044, H-046, H-049, H-052, H-053)
- **Bug fix (session 44)**: Incomplete daily bar bug in all runners. Runners now drop today's incomplete bar before processing.
- **New data sources**: Bybit LSR (`data/all_assets_lsr_daily.parquet`), premium index (`data/all_assets_premium_daily.parquet`)
- Vol dynamics research: `strategies/vol_dynamics_research/`
- Premium research: `strategies/premium_research/`
- **Options IV surface collector**: `scripts/collect_iv_surface.py` — daily cron at 01:00 UTC, data in `data/iv_snapshots/`
- **Order book depth collector**: `scripts/collect_orderbook_depth.py` — daily cron at 01:30 UTC, data in `data/orderbook_snapshots/`
- Macro research: `strategies/macro_research/`

## Key Learnings
- 2024-2026 BTC: +1.8% total, 50% drawdown -- extremely hostile for directional strategies
- Daily EMA crossover is a real signal on BTC: OOS Sharpe 0.94, parameter robust (15/15 positive)
- **Funding rate arb at 5x leverage is viable**: OOS +25.4% annual, 0.14% DD, Sharpe 29.9
- **Cross-sectional momentum is a genuine signal**: 100% params positive, rolling OOS Sharpe 0.84
- **Low-volatility anomaly works in crypto**: 89% params positive, 5/8 WF folds, fee-robust
- **Volume momentum is a genuine cross-sectional signal**: 90% params positive, 6/6 WF (mean OOS 1.83)
- **Low-beta anomaly is stronger than low-vol**: 100% IS positive, 5/6 WF (mean 2.12)
- **5-strategy portfolio**: Sharpe 2.10, +31.6%, 12.9% DD — exceeds all targets
- **Day-of-week seasonality (H-039) is strongest signal found**: WF 6/6 (mean 2.46)
- **Price acceleration (H-046) is genuinely independent**: WF 4/4, near-zero corr with everything
- **OI-Price divergence (H-044)**: True IS Sharpe 1.01 (was 1.46 before bug fix). WF 3/4.
- **Long/short ratio sentiment (H-049)**: Contrarian signal — 100% params positive, Sharpe 2.58, 7.2% DD. BUT only 200 days of data. Genuinely new data source (first non-price/volume/OI signal).
- **Volatility change (H-047) has NO signal**: 50% positive = random noise. Vol dynamics not predictive cross-sectionally.
- **Correlation change (H-048) has NO signal**: 50% positive = random noise.
- **Incomplete daily bar bug**: Critical bug found and fixed. Runners were processing intra-day incomplete bars, causing stale signals. H-009 missed SHORT flip by ~1 day.
- **Macro signals (H-050) have NO predictive power**: SPY-BTC same-day corr +0.37, but lagged corr <0.08. Info fully priced in. 50% positive = noise across all lookbacks.
- **Monthly calendar effects (H-051) don't persist**: DOM train/test corr -0.13. Only DOW effects (H-039) work — likely need 100+ observations per bucket.
- **Premium index is a powerful contrarian signal (H-052)**: 100% IS positive, WF 6/6 (mean 1.86), split-half 2.18/2.95. Corr -0.14 with momentum — excellent diversifier. Assets with deepest perp discount (shorts aggressive) outperform.
- **Funding rate XS contrarian (H-053)**: 93% IS positive, WF 6/6 (mean OOS 2.29), split-half 1.31/1.91. Assets with lowest funding rate outperform. Corr 0.36 with H-052 (moderate overlap — both measure positioning). Without ATOM still Sharpe 1.22.
- **Liquidation data not accessible**: Bybit has no public historical liquidation endpoint. Only via WebSocket real-time stream.
- **53 hypotheses tested**: 14 in paper trade + 1 comparison + 1 manual, 40 rejected, 3 confirmed standalone + 1 weak.
- Fee drag critical at 1h; daily/3-day/5-day/21-day rebalance minimizes fee impact
- **Research: Bybit API rich data sources**: Premium index (exploited in H-052), options IV (collecting), order book depth (collecting), LSR (exploited in H-049).
- **Options IV surface data collection started**: BTC/ETH/SOL/XRP/DOGE daily snapshots. ATM IV levels: BTC ~46-52%, ETH ~63-75%, SOL ~70-79%, DOGE ~67-96%. After 60-90 days of collection, options-based cross-sectional signals become backtestable.
- **Order book depth collection started**: 14 assets daily snapshots. Bid/ask imbalance at 5/10/25 levels. After ~60-90 days, microstructure signals become backtestable.
