# Strategy State

## Active Paper Trades

### H-009: BTC Daily EMA Trend Following (VT 20%)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: LONG 0.054885 BTC @ $73,524.10
- **Mark equity**: $9,840 (-1.60%) — live mark @ BTC $70,685
- **Leverage**: 0.40x (vol targeting: 50.0% realized -> 20% target)
- **Runner**: `paper_trades/h009_btc_daily_trend/runner.py`
- **Signal**: EMA(5) < EMA(40) already on incomplete bar. **Flip to SHORT on tonight's daily close (00:00 UTC Mar 20) confirmed.**
- **Next check**: Next daily bar close (00:00 UTC 2026-03-20)

### H-011: Leveraged Funding Rate Arb (5x)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: OUT (rolling-27 avg funding negative, since 2026-03-07)
- **Capital**: $10,000.00
- **Runner**: `paper_trades/h011_funding_rate_arb/runner.py`
- **Funding trend**: Rolling-7 at -1.4% ann. **Projected re-entry: ~2026-03-22 to 2026-03-23**.
- **Next check**: Next funding settlement

### H-012: Cross-Sectional Momentum (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: BTC, NEAR, ATOM, AVAX
  - SHORT: SOL, SUI, ARB, OP
- **Mark equity**: $10,173 (+1.73%) — **short side dominating**
- **Runner**: `paper_trades/h012_xsmom/runner.py`
- **Params**: 60d lookback, 5d rebalance, top/bottom 4
- **Next rebal**: 2026-03-21 (2 days)

### H-019: Low-Volatility Anomaly (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-18)
- **Position**: 6 positions (3 long, 3 short)
  - LONG (low vol): ATOM, ARB, XRP
  - SHORT (high vol): DOGE, DOT, NEAR
- **Mark equity**: $9,970 (-0.30%)
- **Runner**: `paper_trades/h019_lowvol/runner.py`
- **Params**: 20d vol window, 21d rebalance, top/bottom 3
- **Next rebal**: 2026-04-08 (21 days)

### H-021: Volume Momentum Factor (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-18)
- **Position**: 8 positions (4 long, 4 short)
  - LONG (vol surge): DOT, LINK, XRP, DOGE
  - SHORT (vol drop): ARB, SUI, NEAR, ATOM
- **Mark equity**: $10,128 (+1.28%)
- **Runner**: `paper_trades/h021_volmom/runner.py`
- **Params**: VS5_VL20_R3_N4 (5d/20d volume ratio, 3-day rebalance, top/bottom 4)
- **Next rebal**: 2026-03-21 (2 days)

### H-024: Low-Beta Anomaly (14 Assets) — comparison
- **Status**: LIVE paper trade (started 2026-03-18) — **comparing against H-019**
- **Position**: 6 positions (3 long, 3 short)
  - LONG (low beta): ATOM, OP, BTC
  - SHORT (high beta): XRP, NEAR, SUI
- **Mark equity**: $9,922 (-0.78%)
- **Runner**: `paper_trades/h024_beta/runner.py`
- **Params**: W60_R21_N3 (60d rolling beta vs BTC, 21d rebalance, top/bottom 3)
- **Next rebal**: 2026-04-08 (21 days)
- **Note**: In backtests, H-024 dominates H-019 at every param set (12/12), WF 5/6 positive (mean 2.12). Portfolio Sharpe improves from 1.80 to 2.33 by replacing H-019. Tracking in parallel for live comparison.

### H-031: Size Factor (Dollar Volume Proxy, Long Large) — independent
- **Status**: LIVE paper trade (started 2026-03-19) — independent, not in main portfolio
- **Position**: 10 positions (5 long, 5 short)
  - LONG (large cap): BTC, ETH, SOL, XRP, DOGE
  - SHORT (small cap): LINK, DOT, OP, ARB, ATOM
- **Mark equity**: $10,034 (+0.34%)
- **Runner**: `paper_trades/h031_size/runner.py`
- **Params**: W30_R5_N5 (30-day avg dollar volume, 5-day rebalance, top/bottom 5)
- **Next rebal**: 2026-03-24 (5 days)
- **Note**: Confirmed standalone (Sharpe 1.58, +78.5% ann, 31% DD). Corr 0.49 with H-012.

### H-032: Cointegration Pairs (8-pair portfolio) — independent
- **Status**: LIVE paper trade (started 2026-03-19) — independent, experimental
- **Position**: ALL FLAT — waiting for z-score entry signals
- **Pairs**: DOT/ATOM, DOGE/LINK, DOGE/ADA, DOT/OP, SOL/DOGE, AVAX/DOT, NEAR/OP, ARB/ATOM
- **Mark equity**: $10,000 (0%)
- **Runner**: `paper_trades/h032_pairs/runner.py`
- **Note**: OOS Sharpe 1.33, DD 5.8%. Negative corr with H-012 (-0.31). Entries are infrequent — trade on z-score extremes only.

### H-037: Polymarket 1hr BTC UP/DOWN (Manual Paper Trade)
- **Status**: CONFIRMED for paper trade (started 2026-03-19) — MANUAL, Polymarket only
- **Position**: No trades yet — requires user to check Polymarket prices at target hours
- **Target hours (UTC)**: 17:00 (UP), 21:00 (UP), 22:00 (UP), 23:00 (DOWN), 13:00 (DOWN)
- **Tracker**: `paper_trades/h037_polymarket/tracker.py`
- **Note**: OOS 53.7% win rate, +$0.32/bet at 50c. Edge depends on Polymarket mispricing.

### H-039: Day-of-Week Seasonality (Long Wed / Short Thu) — NEW
- **Status**: LIVE paper trade (started 2026-03-19) — independent
- **Position**: FLAT (first trade: Tue Mar 24 close → enter LONG for Wed)
- **Capital**: $10,000.00
- **Runner**: `paper_trades/h039_dow_seasonality/runner.py`
- **Logic**: Long BTC at Tue close (captures Wed up), flip short at Wed close (captures Thu down), flat Fri-Tue
- **Backtest**: WF **6/6** positive (mean OOS Sharpe **2.46**), best WF in entire project. IS Sharpe 1.55, +44.8% ann, -32.7% DD
- **Cross-asset**: Works on ALL 14 assets. EW all-asset WF 6/6 (mean 1.99). BTC, ETH, DOGE all 6/6
- **Correlations**: 0.013 with H-009, 0.119 with H-012, 0.112 with H-019 — near-zero
- **Fees**: 4 bps/side → Sharpe 1.07 (still viable)
- **Note**: 40 hypotheses tested total. Strongest walk-forward result ever found.

### H-044: OI-Price Divergence Factor (14 Assets) — NEW, independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 10 positions (5 long, 5 short)
  - LONG (price up + OI down): SUI, OP, NEAR, SOL, ETH
  - SHORT (price down + OI up): ADA, ARB, DOT, XRP, DOGE
- **Mark equity**: $9,972 (-0.28%)
- **Runner**: `paper_trades/h044_oi_divergence/runner.py`
- **Params**: 20d OI/price window, 10d rebalance, top/bottom 5
- **Next rebal**: 2026-03-29 (10 days)
- **Backtest**: IS Sharpe 1.46, +26.3% ann, 13.9% DD. WF 4/5 positive (mean OOS 1.27). 100% params positive (9/9). Fee-robust (1.15 at 5x fees).
- **Correlations**: 0.016 with H-009, **0.565 with H-012**, 0.154 with H-019, 0.064 with H-021
- **Note**: First strategy using genuinely new data source (open interest). Partially correlated with H-012 (momentum) — not in main portfolio. Independent deployment.

## Portfolio Summary (live mark-to-market 2026-03-20 session 42)
- **Total equity**: $50,112 (+0.22%) — 5-strat portfolio only
- **H-009**: $9,840 (-1.60%) | **H-011**: $10,000 (0%) | **H-012**: $10,173 (+1.73%) | **H-019**: $9,970 (-0.30%) | **H-021**: $10,128 (+1.28%)
- **H-024 (comparison)**: $9,922 (-0.78%) — H-019 leading
- **H-031 (independent)**: $10,034 (+0.34%) | **H-032 (independent)**: $10,000 (0%)
- **H-037 (Polymarket, manual)**: $0 (no trades yet) | **H-039 (DOW, independent)**: $10,000 (flat, first trade Mar 24)
- **H-044 (OI divergence, independent)**: $9,972 (-0.28%) — NEW
- **Paper trade age**: H-009/H-011/H-012: 3 days / 28 required. H-019/H-021/H-024: 1-2 days. H-031/H-032/H-039: 0 days. H-044: 0 days.
- **BTC at ~$70,685** — H-009 flip to SHORT confirmed for tonight's daily close (00:00 UTC Mar 20).

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
- **H-009 flip TONIGHT**: EMA5 < EMA40 already. Flip to SHORT on daily close (00:00 UTC Mar 20).
- **H-012 best performer**: +1.73% — short side dominating. Market-neutral proven.
- **H-019 vs H-024**: H-019 -0.30% vs H-024 -0.78% — H-019 still leading.
- **H-021**: +1.28% (improving, now 2nd best).
- **H-031**: +0.34% — turned positive. Short side (small caps) profiting.
- **H-044 NEW**: Deployed OI-Price divergence. L SUI/OP/NEAR/SOL/ETH, S ADA/ARB/DOT/XRP/DOGE.
- **Funding rate**: Rolling-7 at -1.4% ann. **H-011 re-entry ~Mar 22-23.**
- **Portfolio stable**: BTC -3.9% since entry → +0.22% portfolio. Diversification working.
- **Research status**: 44 hypotheses tested, 35 rejected, 3 confirmed standalone (H-030, H-038, H-042-weak), 10 in paper trade + 1 comparison + 1 manual.
- **Watchlist**: H-009 flip tonight. H-011 re-entry ~Mar 22-23. H-012 + H-021 rebalance 2026-03-21. H-039 first trade Mar 24. H-044 next rebal Mar 29.
- **Open user questions**: None

## Automation
- **Paper trade orchestrator**: `scripts/run_all_paper_trades.py` — runs all 10 active runners sequentially
- **Cron schedule**: Every hour at :30 (`30 * * * *`), independent of Claude sessions
- **Logs**: `logs/paper_trades.log`
- **Claude sessions**: Every 2 hours at :00 — research, monitoring, strategy updates
- Paper trades now run independently from Claude sessions. No missed trades even if Claude session fails.

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
| H-027: Lead-Lag XS | 1% positive. BTC-altcoin lag not exploitable at hourly frequency. |
| H-028: Volume Trend Change | 6% positive. Overfitting, fails WF. OI proxy has no XS signal. |
| H-029: Hourly XS Momentum | 16% positive. 336h lookback works but corr 0.484 with H-012 — redundant. |
| H-033: Idiosyncratic Momentum | 99% IS positive but corr 0.832 with H-012. Fails WF (1/4). Redundant. |
| H-034: Funding Rate BTC Timing | 49% positive (noise). Only 5 trades in 2yr. No edge. |
| H-035: Momentum + Vol Timing | Enhancement to H-012, not independent strategy. WF 3/4, mean 0.76. |
| H-036: Intraday Seasonality | Real patterns (train/test corr 0.44) but untradeable — Sharpe 0.30 max. |
| H-040: Vol Regime Factor Timing | Marginal IS improvement (+0.12 Sharpe), negative OOS (-0.06 to -0.31). Doesn't help. |
| H-041: BTC Dominance Rotation | 100% look-ahead bias. Correctly lagged: 1/16 params positive (6.2%), WF 3/6. All lookbacks negative. |
| H-043: OI Change XS Factor | 34% IS positive. Best (1d OI change, r=3) fails WF (1/5). OI change alone not predictive. |

## Confirmed Standalone (not in portfolio — good for independent deployment)
| Hypothesis | Metrics | Why Not In Portfolio |
|-----------|---------|---------------------|
| H-030: Composite Multi-Factor | Sharpe 2.05, +101.7% ann, 25% DD, WF 5/6, 100% params positive | Portfolio of individual strategies (Sharpe 2.26) beats composite (2.14) |
| H-038: ML Factor Combo (Ridge) | Sharpe 1.43, +26.2% ann, 9.6% DD, WF 2/3, 96% params positive | Train window sensitive (only 365d works), too fragile for portfolio |
| H-042: Short-Term XSMom (20d) | Sharpe 1.17 IS, WF 4/6, mean OOS 0.55, 77% params positive, fee-robust | Corr 0.686 with H-012 (partially redundant). Weak OOS mean Sharpe. |

*H-031 and H-032 moved to independent paper trades (session 36). H-044 deployed as independent paper trade (session 42).*

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
- H-024 beta factor research + deep validation
- Lead-lag / hourly factor research (`strategies/leadlag_research/`)
- Composite multi-factor research (`strategies/new_factors_research/composite_factor_research.py`)
- **Pairwise cointegration research** (`strategies/pairs_research/`) — NEW
- H-009 paper trade runner (internal simulation)
- H-011 paper trade runner (funding rate arb simulation)
- H-012 paper trade runner (XSMom, internal simulation)
- H-019 paper trade runner (LowVol, internal simulation)
- H-021 paper trade runner (VolMom, internal simulation)
- H-024 paper trade runner (Beta, internal simulation)
- **H-031 paper trade runner** (Size Factor, internal simulation) — NEW
- **H-032 paper trade runner** (Cointegration Pairs, 8-pair portfolio) — NEW
- **H-039 paper trade runner** (DOW Seasonality, BTC long Wed / short Thu) — NEW
- **DOW seasonality research** (`strategies/dow_research/`)
- **Dominance + dispersion research** (`strategies/dominance_dispersion_research/`)
- **OI factor research** (`strategies/oi_research/`) — NEW: Open interest data as cross-sectional factor
- **H-044 paper trade runner** (OI-Price Divergence, internal simulation) — NEW
- **Portfolio monitor**: `scripts/portfolio_monitor.py` — live mark-to-market across all 10+ strategies
- **Paper trade orchestrator**: `scripts/run_all_paper_trades.py` — runs all 10 runners hourly via cron (independent of Claude sessions)
- Cached data (1h, 2yr): BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM (14 assets)
- Cached data: BTC funding rates (2yr, 2199 records)
- Cached data: 14-asset funding rates (2yr, 2190 records each)
- Cached data: 14-asset daily OI (open interest) from Bybit V5 API (2020-2026, 1000-2000 bars per asset)

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
- **Lead-lag (BTC→alt) not exploitable**: 1% IS positive at hourly frequency. Effect may exist at tick level but not at 1h bars.
- **Volume trend change no cross-sectional signal**: 6% IS positive. OI proxy via volume ratios doesn't work.
- **Hourly momentum ≈ daily momentum**: 336h lookback works (5/6 WF) but corr 0.484 with H-012. No unique intraday momentum alpha.
- **44 hypotheses tested total**: 10 in paper trade + 1 comparison (H-024) + 1 manual, 35 rejected, 3 confirmed standalone (H-030, H-038, H-042)
- **Risk**: funding rates declining (Q1 2024: 22.7% -> Q1 2026: 1.6%) -- rolling-27 negative since 2026-03-07
- Fee drag critical at 1h; daily/3-day/5-day/21-day rebalance minimizes fee impact
- **Composite multi-factor doesn't beat portfolio of individuals**: Combining 3 factors into 1 strategy (Sharpe 2.14) is worse than running them separately (Sharpe 2.26). Diversification from independent rebalance schedules adds value.
- **Size factor (long large-cap) is genuine but redundant**: 100% IS positive (long_large), WF 4/4, but corr 0.486 with momentum. Large-cap outperformance ≈ momentum.
- **Cross-sectional factor space exhausted**: Tested momentum, volume momentum, beta, volatility, reversal, skewness, drawdown, illiquidity, funding dispersion, lead-lag, size, composite. Only 3 orthogonal signals found (momentum, volume momentum, beta/vol).
- **Pairwise cointegration (H-032)**: 3/91 pairs strictly cointegrated. Multi-pair portfolio IS Sharpe 1.67, OOS 1.33 — but only 2/12 pairs pass both WF and split tests. Cointegration unstable (<30% of windows). Negative corr with H-012 (-0.31) is attractive. Confirmed standalone (weak).
- **Idiosyncratic momentum ≈ raw momentum**: Decomposing returns into beta*BTC + residual doesn't create independent signal. Corr 0.832 with H-012. Fails WF.
- **Funding rate doesn't predict BTC price**: 49% IS positive = noise. Contrarian funding signal non-existent.
- **Vol timing can enhance H-012**: VT0.3/VW10 → Sharpe 1.12→1.61, DD 30.6%→21.3%. WF 3/4. Log as potential refinement.
- **Intraday hour-of-day patterns are real but untradeable**: Train/test corr 0.44. Cross-asset corr 0.63. But absolute returns per hour too small vs fees.
- **Research exhaustion after 36 hypotheses**: All tradeable alpha in price/volume/funding data has been found. Future alpha requires options IV, on-chain data, or order book.
- **ML factor combination (H-038)**: Ridge regression on factor z-scores achieves OOS Sharpe 1.43, beats individual factors. But train window sensitive (only 365d works) — fragile. Linear model beats trees (RF, GB) — factor interaction is linear, not non-linear. Reversal (failed alone) contributes in combination. Beta most stable feature.
- **Day-of-week seasonality (H-039) is strongest signal found**: Wednesday consistently positive, Thursday consistently negative across ALL 14 crypto assets. BTC WF 6/6 (mean Sharpe 2.46), EW all-asset WF 6/6 (mean 1.99). Effect strengthening over time. Correlation near-zero with all existing strategies. Fee-robust at maker rates.
- **Vol regime factor timing (H-040) doesn't work OOS**: In-sample improvement (+0.12 Sharpe) but walk-forward degradation (-0.06 to -0.31). Base factor strategies already time vol through position sizing.
- **All 5 portfolio strategies now in paper trade + H-024 comparison + H-039** -- monitor for >=4 weeks before live consideration
- **BTC dominance rotation (H-041) is 100% look-ahead bias**: Without 1-day signal lag: Sharpe 3.96 (fake). With correct lag: 1/16 params positive (6.2%), all lookbacks negative. BTC dominance mean-reverts next day — opposite of rotation hypothesis.
- **Dispersion conditioning (H-042) does not add alpha**: Dispersion filter only improves 10.2% of param combos. Core underlying signal is short-term XSMom (20d lookback, 21d rebal) with IS Sharpe 1.17, WF 4/6. But corr 0.686 with H-012 (redundant). Not in portfolio.
- **Look-ahead bias is critical for daily strategies**: Signal must be computed on close of day t-1 (lagged) and applied to return of day t. Same-bar signal + same-bar return = look-ahead. Always verify with .shift(1) before reporting results.
- **OI change alone is NOT a cross-sectional signal (H-043)**: Only 34% IS positive. 1-day OI change has IS edge at 3-day rebal but fails WF (1/5). Long-term contrarian OI too weak (best Sharpe 0.60). OI only works combined with price (H-044).
- **OI-Price divergence (H-044) is a genuine new signal**: First strategy using open interest data. 100% IS params positive (9/9), WF 4/5 (mean OOS 1.27), Sharpe 1.46, +26.3%, 13.9% DD. Extremely fee-robust (1.15 at 5x). Signal: assets with price up + OI down (deleveraging rally) outperform those with price down + OI up (leverage buildup). Corr 0.565 with H-012 — partially captures momentum but with unique OI information.
- **New data sources can break through research exhaustion**: After 42 hypotheses using only price/volume/funding, OI data yielded a genuinely new signal (H-044). Future: options IV, on-chain data, order book depth.
