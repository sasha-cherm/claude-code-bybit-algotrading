# Strategy State

## Bybit Demo Account (LIVE since 2026-03-20)

**Account**: $100k USDT demo. Equity ~$100,137 (session 56, +0.14%).
**Architecture**: `scripts/demo_portfolio_runner.py` reads all strategy state.json files, computes net H-055 weighted positions, rebalances on Bybit demo after each `run_all_paper_trades.py` run.
**H-055 weights**: H-009(12%) H-011(40%,cash) H-021(7%) H-031(13%) H-039(9%) H-046(5%) H-052(8%) H-053(6%)
**Gross leverage**: 0.29x (low — H-011 40% in cash). Net exposure: short bias (BTC $69,980).

### Current Demo Positions (as of 2026-03-20 21:03 UTC):
| Symbol | Side | Size | Entry | Notional | PnL |
|--------|------|------|-------|----------|-----|
| ADAUSDT | SHORT | 10,269 | $0.2678 | $-2,750 | $+44 |
| ARBUSDT | SHORT | 25,889 | $0.1004 | $-2,600 | $+35 |
| ATOMUSDT | SHORT | 470.8 | $1.8054 | $-850 | $-2 |
| BTCUSDT | SHORT | 0.007 | $70,402 | $-493 | $+3 |
| DOGEUSDT | LONG | 11,717 | $0.0939 | $+1,100 | $-4 |
| DOTUSDT | SHORT | 392.5 | $1.5284 | $-600 | $+9 |
| ETHUSDT | LONG | 2.15 | $2,141.55 | $+4,604 | $-23 |
| LINKUSDT | SHORT | 11.0 | $9.0850 | $-100 | $+1 |
| NEARUSDT | SHORT | 2,996.7 | $1.3352 | $-4,000 | $+52 |
| OPUSDT | SHORT | 38,759.7 | $0.1251 | $-4,850 | $+86 |
| SOLUSDT | LONG | 23.5 | $89.19 | $+2,096 | $-7 |
| SUIUSDT | SHORT | 510 | $0.9676 | $-493 | $+5 |
| XRPUSDT | LONG | 3,004 | $1.4480 | $+4,350 | $-39 |

---

## Active Paper Trades (Internal Simulation)

### H-009: BTC Daily EMA Trend Following (VT 20%)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: SHORT 0.053871 BTC @ $69,909.32 — **FLIPPED from LONG** (session 44)
- **Mark equity**: $9,786 (-2.14%) — closed LONG at loss ($-202), now SHORT (slightly underwater $-4)
- **Leverage**: 0.38x (vol targeting: 52% realized -> 20% target)
- **Runner**: `paper_trades/h009_btc_daily_trend/runner.py`
- **Signal**: EMA(5) < EMA(40) confirmed on Mar 19 close ($69,882). BTC at $69,980 — SHORT slightly underwater.
- **Next check**: Next daily bar close (00:00 UTC 2026-03-21, ~3h)

### H-011: Leveraged Funding Rate Arb (5x)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: OUT (rolling-27 avg funding negative, since 2026-03-07)
- **Capital**: $10,000.00
- **Runner**: `paper_trades/h011_funding_rate_arb/runner.py`
- **Funding trend**: R27 at -0.0003% (nearly zero!). **Re-entry IMMINENT — likely at 00:00 UTC Mar 21** (~3h). Next settlement drops oldest rate (-0.011%) and adds ~+0.003%, flipping R27 positive. Last 8 of 10 settlements positive.
- **Next check**: 00:00 UTC 2026-03-21 funding settlement — cron at 00:30 will execute entry

### H-012: Cross-Sectional Momentum (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: BTC, NEAR, ATOM, AVAX
  - SHORT: SOL, SUI, ARB, OP
- **Mark equity**: $9,980 (-0.20%) — fee drag only, no rebalance yet. Live MTM tracked via demo.
- **Runner**: `paper_trades/h012_xsmom/runner.py`
- **Params**: 60d lookback, 5d rebalance, top/bottom 4
- **Next rebal**: 2026-03-21 00:00 UTC bar close (~3h) — cron at 00:30 processes

### H-019: Low-Volatility Anomaly (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-18)
- **Position**: 6 positions (3 long, 3 short)
  - LONG (low vol): ATOM, ARB, XRP
  - SHORT (high vol): DOGE, DOT, NEAR
- **Mark equity**: $9,980 (-0.20%) — fee drag only
- **Runner**: `paper_trades/h019_lowvol/runner.py`
- **Params**: 20d vol window, 21d rebalance, top/bottom 3
- **Next rebal**: 2026-04-08 (19 days)

### H-021: Volume Momentum Factor (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-18)
- **Position**: 8 positions (4 long, 4 short)
  - LONG (vol surge): DOT, LINK, XRP, DOGE
  - SHORT (vol drop): ARB, SUI, NEAR, ATOM
- **Mark equity**: $9,980 (-0.20%) — fee drag only, no rebalance yet. Live MTM tracked via demo.
- **Runner**: `paper_trades/h021_volmom/runner.py`
- **Params**: VS5_VL20_R3_N4 (5d/20d volume ratio, 3-day rebalance, top/bottom 4)
- **Next rebal**: 2026-03-21 00:00 UTC bar close (~3h) — cron at 00:30 processes

### H-024: Low-Beta Anomaly (14 Assets) — comparison
- **Status**: LIVE paper trade (started 2026-03-18) — **comparing against H-019**
- **Position**: 6 positions (3 long, 3 short)
  - LONG (low beta): ATOM, OP, BTC
  - SHORT (high beta): XRP, NEAR, SUI
- **Mark equity**: $9,956 (-0.44%)
- **Runner**: `paper_trades/h024_beta/runner.py`
- **Params**: W60_R21_N3 (60d rolling beta vs BTC, 21d rebalance, top/bottom 3)
- **Next rebal**: 2026-04-08 (19 days)
- **Note**: Both at -0.20% (fee drag only). Comparison still early — both entered recently.

### H-031: Size Factor (Dollar Volume Proxy, Long Large) — independent
- **Status**: LIVE paper trade (started 2026-03-19) — independent
- **Position**: 10 positions (5 long, 5 short)
  - LONG (large cap): BTC, ETH, SOL, XRP, DOGE
  - SHORT (small cap): LINK, DOT, OP, ARB, ATOM
- **Mark equity**: $9,980 (-0.20%) — fee drag only
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
- **Mark equity**: $9,980 (-0.20%) — fee drag only
- **Runner**: `paper_trades/h044_oi_divergence/runner.py`
- **Next rebal**: 2026-03-29 (10 days)

### H-046: Price Acceleration Factor (14 Assets) — independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 8 positions (4 long, 4 short)
  - LONG (accelerating): OP, ARB, NEAR, SUI
  - SHORT (decelerating): DOGE, LINK, ADA, DOT
- **Mark equity**: $9,980 (-0.20%) — fee drag only
- **Runner**: `paper_trades/h046_acceleration/runner.py`
- **Next rebal**: 2026-03-22 (2 days)

### H-049: LSR Sentiment Factor (Contrarian, 14 Assets) — NEW, independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 6 positions (3 long, 3 short)
  - LONG (crowd short): BTC, ETH, LINK
  - SHORT (crowd long): ARB, SUI, OP
- **Mark equity**: $9,980 (-0.20%) — fee drag only
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
- **Mark equity**: $9,980 (-0.20%) — fee drag only
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
- **Mark equity**: $9,980 (-0.20%) — fee drag only
- **Runner**: `paper_trades/h053_funding_xs/runner.py`
- **Params**: W3_R10_N4 (3-day funding avg, 10-day rebalance, top/bottom 4, contrarian)
- **Next rebal**: 2026-03-29 (10 days)
- **Backtest (full 2yr)**: IS 93% positive (42/45). Best Sharpe 1.52, +32.9% ann, 22.2% DD. **WF 6/6 positive (mean OOS 2.29)**. Split-half: 1.31/1.91. Fee-robust (0.92 at 5x fees).
- **Correlations**: 0.004 H-012, 0.109 H-046, **0.360 H-052** (moderate — related contrarian signals), **0.480 H-049** (high)
- **Data source**: Bybit funding rates (8h, aggregated to daily avg) — same underlying market positioning as H-052 (premium).

## Portfolio Summary (live mark-to-market 2026-03-20 session 56, 21:03 UTC)
- **Bybit Demo**: $100,137 (+0.14%) — H-055 allocation, 13 positions, 0.29x leverage. Short bias profitable (OP +$86, NEAR +$52, ADA +$44, ARB +$35).
- **Total internal equity (14 strats)**: $139,590 (-0.29%) — mostly fee drag, XS strats don't track live MTM between rebalances.
- **H-009**: $9,786 (-2.14%, SHORT) | **H-011**: $10,000 (0%, OUT — re-entry ~3h) | **H-012**: $9,980 (-0.20%) | **H-019**: $9,980 (-0.20%) | **H-021**: $9,980 (-0.20%)
- **H-024 (comparison)**: $9,980 (-0.20%)
- **H-031 (independent)**: $9,980 (-0.20%) | **H-032 (independent)**: $10,000 (0%, flat)
- **H-037 (Polymarket, manual)**: $0 (no trades yet) | **H-039 (DOW, independent)**: $10,000 (flat, first trade Mar 24)
- **H-044 (OI divergence)**: $9,980 (-0.20%) | **H-046 (Acceleration)**: $9,980 (-0.20%)
- **H-049 (LSR sentiment)**: $9,980 (-0.20%) | **H-052 (Premium)**: $9,980 (-0.20%)
- **H-053 (Funding XS)**: $9,980 (-0.20%)
- **Paper trade age**: H-009/H-011/H-012: 5 days / 28 required. H-019/H-021/H-024: 3 days. H-031/H-032/H-039: 2 days. H-044/H-046/H-049/H-052/H-053: 1 day.
- **BTC at ~$69,980** — H-009 SHORT, slightly underwater (-$4).
- **Mar 20 daily bar closes in ~3h** (00:00 UTC Mar 21) — triggers H-012+H-021 rebal + H-011 likely re-entry.

## Target Portfolio Allocation — OLD 5-strat (baseline)
- **10% H-009** (BTC daily trend): directional alpha, Sharpe ~0.6-0.9
- **40% H-011** (funding rate arb): carry alpha, Sharpe ~15-25
- **10% H-012** (cross-sectional momentum): relative value alpha, Sharpe ~0.8-1.1
- **15% H-019** (low-volatility anomaly): cross-sectional factor, Sharpe ~0.7-1.2
- **25% H-021** (volume momentum): cross-sectional factor, Sharpe ~1.5-1.8
- **Combined (5-strat)**: Sharpe 2.58, +35.3%, 13.9% DD

## Target Portfolio Allocation — NEW 8-strat (H-055, proposed)
- **12% H-009** (BTC daily trend): directional alpha, Sharpe ~0.3
- **40% H-011** (funding rate arb): carry alpha, Sharpe ~18
- **7% H-021** (volume momentum): cross-sectional factor, Sharpe ~1.5
- **13% H-031** (size factor): large-cap vs small-cap, Sharpe ~2.5 — **REPLACES H-012**
- **9% H-039** (DOW seasonality): calendar alpha, Sharpe ~1.2 — **NEW**
- **5% H-046** (price acceleration): XS momentum derivative, Sharpe ~0.7 — **NEW**
- **8% H-052** (premium index contrarian): XS positioning, Sharpe ~2.4 — **NEW**
- **6% H-053** (funding rate XS contrarian): XS positioning, Sharpe ~2.0 — **NEW**
- **Combined (8-strat)**: **Sharpe 5.13, +46.0%, 7.3% DD** (vs 2.58/35%/14% old)
- **DROPPED**: H-012 (redundant with H-031, corr 0.517), H-019 (inferior to H-024, corr 0.657)
- **Status**: Pending paper trade validation (need 28+ days on all strategies)

## Proposed Upgrade: Replace H-019 with H-024
- **If confirmed in paper trade**: H-024 (beta) replaces H-019 (vol) — H-055 optimization also drops H-019
- **Current status**: H-024 -4.70% vs H-019 -13.85% — both in drawdown from BTC crash. Note: H-019 entered 2 days earlier at higher prices.
- **Decision point**: After 4 weeks of parallel paper trading

## Key Correlations (12-strat, full 2yr, 700 days)
- H-009/H-011: 0.044, H-009/H-012: 0.025, H-009/H-021: 0.043, H-009/H-039: 0.069
- H-012/H-031: **0.517** (moderate — both capture similar XS signals)
- H-012/H-044: **0.467** (moderate — momentum and OI overlap)
- H-019/H-024: **0.657** (high — related factors, choose one)
- H-019/H-031: **0.454** (moderate — vol and size overlap)
- H-052/H-053: **0.377** (moderate — both positioning signals)
- H-052/H-012: **-0.127** (negative — excellent diversifier)
- H-053/H-012: 0.008 (near zero — excellent)
- H-039/all: <0.11 (near zero with everything — perfect diversifier)

## Active Live Strategies
(none)

## Recently Killed
(none)

## Research Pipeline
| Hypothesis | Status | Priority | Next Step |
|-----------|--------|----------|-----------|
| H-010: Multi-Strategy Portfolio | BACKTEST | Low | Superseded by H-055 portfolio optimization |
| H-055: Portfolio Optimization | CONFIRMED | High | Implement new 8-strat allocation after paper trade validation |

## H-055 Stress Test Results (session 54, 700 days backtest)
- **Tail Risk**: 95% daily VaR -0.56%, 99% VaR -0.89%. Worst day: -3.4% (Aug 8 2024, BTC flash). Max DD: -7.25%, recovered in 33 days.
- **Distribution**: 62% positive days, skew +0.18 (slightly positive), kurtosis 7.5 (fat tails but manageable). Only 0.6% of days below -1%.
- **Correlation Stability**: Avg pairwise corr 0.044. During BTC stress: 0.041 (unchanged). Rolling 30d corr NEVER >0.30. No correlation breakdown.
- **Regime Performance**: Uptrend Sharpe 7.46, Downtrend 2.89. High vol 5.64, Low vol 5.25. Deep DD 4.71. Positive in ALL regimes.
- **Year-by-year**: 2024: Sharpe 4.74, 2025: 5.50, 2026: 5.24. Consistent.
- **Monthly**: 88% positive (21/24). Worst month -3.26%. Mean +3.11%.
- **Regime Adaptive**: Static weights are near-optimal. Momentum reweight +0.53 Sharpe but risk of overfit. Trend/vol/DD protection all slightly hurt.
- **Monte Carlo (5000 sims, 1yr)**: P(loss)=0.0%. 5th pct return: +22.3%. P(>20%): 96.5%. P(DD>10%): 0.4%. Median Sharpe 5.36.
- **Critical Strategy**: H-011 most valuable (removing it: Sharpe 5.13→3.64). H-009 slightly negative marginal (Sharpe +0.23 without it — consider replacing or reducing weight).
- **H-046 Weakness**: Only strategy with negative Sharpe in downtrend (-0.87). Acceleration signal breaks when momentum reverses.
- **Action items**: (1) Keep static weights — don't add complexity. (2) Monitor H-009 marginal value; may reduce weight if paper trade confirms. (3) H-011 re-entry is the single most important event for portfolio returns.

## Risk Watch
- **Demo account healthy**: $100,137 (+0.14%), 0.29x leverage. Low exposure because H-011 (40% weight) is cash.
- **H-055 CONFIRMED**: 8-strat portfolio LIVE on demo. Sharpe 5.13 backtest. Stress tested: positive in ALL regimes.
- **Funding rate**: R27 at -0.0003% — **re-entry at next settlement (00:00 UTC Mar 21, ~3h)**. Oldest rate in window (-0.011%) drops off, replaced by ~+0.003% current rate. R27 will flip positive. **Most important near-term event** (40% of portfolio weight). Last 8/10 settlements positive.
- **Research status**: 55 hypotheses tested, 40 rejected, 5 confirmed standalone, 14 in paper trade + 1 comparison + 1 manual.
- **All backtestable sources exhausted**: Future alpha from IV surface + OB depth data (60-90 day collection underway).
- **IV collector**: Daily cron at 01:00 UTC. Day 2 of collection.
- **OB depth collector**: Daily cron at 01:30 UTC. Day 2 of collection.
- **Watchlist**: **H-011 re-entry 00:00 UTC Mar 21 (IMMINENT, ~3h)**. H-012 + H-021 rebal Mar 21 bar close. H-046 rebal Mar 22. H-039 first trade Mar 24. H-049 + H-031 + H-052 rebal Mar 24. H-053 + H-044 rebal Mar 29.
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
- **H-055 stress test (session 54)**: Portfolio is highly robust. P(1yr loss)=0% across 5000 Monte Carlo sims. Correlations DON'T break during stress (0.041 in stress vs 0.044 overall). Positive in all regimes (uptrend/downtrend/deep DD). 88% positive months. Static weights outperform all adaptive approaches tested. H-011 is the critical strategy (Sharpe drops from 5.13→3.64 without it). H-009 has slightly negative marginal value. H-046 is the only weakness (Sharpe -0.87 in downtrend).
- **53 hypotheses tested**: 14 in paper trade + 1 comparison + 1 manual, 40 rejected, 3 confirmed standalone + 1 weak.
- Fee drag critical at 1h; daily/3-day/5-day/21-day rebalance minimizes fee impact
- **Research: Bybit API rich data sources**: Premium index (exploited in H-052), options IV (collecting), order book depth (collecting), LSR (exploited in H-049).
- **Options IV surface data collection started**: BTC/ETH/SOL/XRP/DOGE daily snapshots. ATM IV levels: BTC ~46-52%, ETH ~63-75%, SOL ~70-79%, DOGE ~67-96%. After 60-90 days of collection, options-based cross-sectional signals become backtestable.
- **Order book depth collection started**: 14 assets daily snapshots. Bid/ask imbalance at 5/10/25 levels. After ~60-90 days, microstructure signals become backtestable.
