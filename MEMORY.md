# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$97k. BTC spot ~$73,041.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **Internal paper trades:** 83 runners active. Session 184. **32/80 positive** (40%), avg **-0.15%**.
- **H-063**: ~$9,652 (-3.48%). Iron condor active (70K/75.5K, exp Apr 13).
- **Top performers**: H-169(+5.13%), H-049(+4.98%), H-085(+4.51%), H-193(+4.43%), H-411(+4.09%).
- **Session 184 research**: 24 new hypotheses (H-716–H-739). **3 deployed** (H-726 Max DD, H-733 DV Change, H-736 Volume Delta). **739 total hypotheses.**
- **H-736 Volume Delta**: Sharpe **1.703**, WF **6/6 (PERFECT)**, SH corrected PASS, 96% param robust, H-012 corr 0.366. Best new XS factor. Buy/sell pressure from OHLC microstructure.
- **H-726 Max DD Factor**: Sharpe 0.980, WF **6/6 (PERFECT)**, 100% param robust. Contrarian DD-based factor.
- **H-733 DV Change**: Sharpe 1.262, 97% robust, H-012 corr **0.046** (near-zero — excellent diversifier).
- **AUTOMATED:** Paper trades hourly via cron (83 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Await Q-005 answer. Monitor all paper trades (esp. H-726/H-733/H-736). Explore sentiment data, liquidation signals.
- **Open user questions:** Q-005 (H-056 v3 portfolio upgrade proposal)

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 174) archived to `memory/session_archive.md`._

### Session 2026-04-10 review+deploy+research (session 175)
- Goal: Review + Deploy + Research — MTM update, 19 new backtests, H-528 deployment
- Focus: Paper trade MTM (BTC $72,128), expanded universe testing, novel signal categories (H-513–H-531)
- Done: 67 runners (66→67). **26/66 positive** (avg -0.11%). Demo $94,608 (-5.39%). H-063 at -4.91% (trade 2 expires 08:00 UTC, expected -$574 loss). H-496 at +0.22% (day 1). **Expanded universe**: Tested 27-asset momentum (Sharpe 0.26) and size (0.77) — both worse than 14-asset. **Batch 1 (H-513–H-522)**: H-518 Regime Mom (Sharpe 1.36, WF 6/6 but corr 0.793 H-012 = redundant). **H-519 Vol Shock** (Sharpe 1.52, 100% robust, corr -0.041 H-012, but 0.704 corr H-336 = redundant). H-522 PVT Slope (Sharpe 0.98, 100% robust, corr 0.425 H-012). 7 REJECTED. **Batch 2 (H-523–H-531)**: **H-528 Range Expansion CONFIRMED+deployed** (IS 0.849, 100% param robust 96/96, WF 4/6, SH PASS, corr **-0.001** H-012 — perfect diversifier). H-530 DV Share passes all tests but corr 0.934 with H-031 = identical. 8 REJECTED. **531 total hypotheses.**
- Next: Await Q-005 answer. H-063 settles today 08:00. Monitor H-496/H-528. Explore higher-frequency or different instruments.
- Questions added: none
- Self-modifications: H-528 runner created, added to orchestrator. Archived session 165. (session 175)

### Session 2026-04-10 review+deploy+research (session 176)
- Goal: Review + Deploy + Research — MTM update, H-063 settlement check, 16 new BTC time-series backtests, 3 deployments
- Focus: Paper trade MTM (BTC $71,681), BTC time-series strategies (H-532–H-547)
- Done: 70 runners (67→70). **14/66 positive** (21%, down from 26). Avg **-0.17%**. Demo ~$94,700 (-5.30%). **H-063 trade 2 settled**: BTC $71,641 at expiry, 69kC ITM, loss -$454, total -3.76%. **Research**: Explored BTC time-series (TS) strategies — fundamentally different from all prior XS factors. **H-535 CONFIRMED** (Intra Mom, WF 6/8 mean 1.05, SH PASS). **H-539 CONFIRMED** (Keltner Breakout, WF 5/7, 83% param robust, SH PASS). **H-544 CONFIRMED** (Range Squeeze, WF 5/8, **100% param robust**, SH PASS, corr 0.109 H-009). **CRITICAL**: H-540 Multi-Asset TSMOM had look-ahead bias (Sharpe 6.17 fake → 0.57 real). 13 REJECTED. **547 total hypotheses.**
- Next: Await Q-005 answer. Monitor BTC TS paper trades. H-063 trade 3 entry tonight. Consider alternative instruments or higher-frequency.
- Questions added: none
- Self-modifications: H-535/H-539/H-544 runners created, added to orchestrator. Archived session 166. (session 176)

### Session 2026-04-10 review+deploy+research (session 177)
- Goal: Review + Deploy + Research — MTM update, 32 new backtests (ETH TS, multi-asset, classic indicators, multi-TF), 1 deployment
- Focus: Paper trade MTM (BTC $72,202), ETH/SOL time-series and classic indicator strategies (H-548–H-579)
- Done: 71 runners (70→71). **26/70 positive** (37%, up from 21%). Avg **-0.09%** (improved). Demo ~$95,900 (-4.10%, recovering). **Batch 1 (H-548–H-563, ETH TS + cross-asset)**: All 16 REJECTED. ETH intraday momentum FAILS (Sharpe -0.45), mean-reversion universally fails in crypto, BTC-ETH spread not mean-reverting, leader-follower doesn't work. Best was H-561 ATR Breakout (Sharpe 0.404, close but below threshold). **Batch 2 (H-564–H-579, multi-TF/adaptive/SOL/classic)**: **H-571 CONFIRMED** (SOL Session Momentum, IS **0.847**, WF **6/7** mean 0.848, SH PASS, **100% param robust**, BTC corr **-0.092**, deployed). H-572 BTC Multi-TF close (Sharpe 0.651, WF 6/7, SH PASS) but param robust only 69% — REJECTED. 15 REJECTED. **579 total hypotheses.**
- Next: Await Q-005 answer. Monitor TS paper trades (H-535/H-539/H-544/H-571). H-063 trade 3 tonight. Explore options strategies or non-price data.
- Questions added: none
- Self-modifications: H-571 runner created, added to orchestrator. Archived session 167. (session 177)

### Session 2026-04-10 review+deploy+research (session 178)
- Goal: Review + Deploy + Research — MTM update, 32 new backtests (4 batches of 8), 2 new deployments
- Focus: Paper trade MTM (BTC $72,892), novel XS signals: multi-period momentum, funding dynamics, candlestick patterns, volume trends (H-580–H-611)
- Done: 73 runners (71→73). **26/71 positive** (37%). Avg **-0.09%** (stable). Demo ~$96k-$97k. H-063 flat, trade 3 at 01:00 UTC. **Batch 1 (H-580–H-587)**: All 8 REJECTED. Multi-period mom, dispersion, OBV ROC, gap reversal — no edges above 0.7 Sharpe. **Batch 2 (H-588–H-595)**: H-589 Vol Ratio CONFIRMED (IS 1.213, WF 5/6, SH PASS, but factor corr 0.82+ with H-059 → NOT deployed). H-593 VW Momentum REJECTED (WF 3/6 fail). 6 more REJECTED. **Batch 3 (H-596–H-603)**: **H-599 RSI XS CONFIRMED** (IS 1.148, WF 4/6, **100% param robust**, deployed). **H-601 Vol Decline CONFIRMED** (IS 0.965, WF 4/6, **100% param robust**, corr **0.054** H-012, deployed). H-606 CLV CONFIRMED (IS 1.260, WF 5/6) but redundant with H-451 (PnL corr 0.691). 5 REJECTED. **Batch 4 (H-604–H-611)**: H-606 CLV confirmed above. 7 REJECTED. **611 total hypotheses.**
- Next: Await Q-005 answer. Monitor all 73 runners. H-063 trade 3 tonight. Continue exploring options/on-chain/alternative data.
- Questions added: none
- Self-modifications: H-599/H-601 runners created, added to orchestrator. Archived session 168. Fixed WF min-days bug (90-day folds were below 100-day threshold). (session 178)

### Session 2026-04-11 review+deploy+research (session 179)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 1 new deployment
- Focus: Paper trade MTM (BTC $73,310), 4-hour timeframe BTC time-series exploration (H-612–H-635)
- Done: 74 runners (73→74). **26/74 positive** (35%). Avg **-0.10%**. Demo ~$97k (+1.3% 24h). **Batch 1 (H-612–H-619, 4h BTC TS)**: **H-617 CONFIRMED** (4h Volume Breakout, IS 0.971, WF 6/8, 88% param robust, SH PASS, deployed). H-616 Keltner borderline (SH FAIL). 6 REJECTED (EMA/RSI/MACD/BB/adaptive = noise at 4h). **Batch 2 (H-620–H-627, multi-asset 4h + funding)**: **H-622 CONFIRMED** (Multi-Asset 4h Vol Breakout BTC+ETH+SOL, IS 1.001, 100% robust) but NOT deployed — corr 0.724 with H-617 = redundant. H-627 OI Proxy promising (IS 0.877, WF 4/5) but only 709 days data. H-624/H-625/H-626 REJECTED (funding rate timing fails). **Batch 3 (H-628–H-635, structural patterns)**: All 8 REJECTED. Weekend effect too weak. Session patterns not tradable. Vol compression, multi-TF alignment, momentum reversal, range expansion, RSI-vol divergence — no edges.
- Next: Await Q-005 answer. Monitor H-617 4h paper trade. Explore altcoin TS, on-chain data, or intra-day XS.
- Questions added: none
- Self-modifications: H-617 runner created, added to orchestrator. Archived session 169. (session 179)

### Session 2026-04-11 review+deploy+research (session 180)
- Goal: Review + Deploy + Research — MTM update, 32 new backtests (4 batches of 8), 1 new deployment
- Focus: Paper trade MTM (BTC $72,799), altcoin TS, funding rate TS, distributional/higher-order moment signals (H-636–H-667)
- Done: 75 runners (74→75). **30/74 positive** (41%, up from 35%). Avg **-0.18%**. **Batch 1 (H-636–H-643, altcoin 4h TS)**: All 8 REJECTED at IS. ETH/SOL/DOGE/XRP/AVAX/LINK/NEAR 4h TS strategies fail — BTC volume breakout pattern doesn't transfer. **Batch 2 (H-644–H-651, daily alt TS + funding + OI)**: All 8 REJECTED. ETH daily vol breakout borderline (SH fail). Funding rate TS (BTC/ETH), OI change, vol regime, intraday vol distribution, aggregate funding — no edges. **Batch 3 (H-652–H-659)**: **H-657 CONFIRMED+deployed** (BTC Realized Skew, IS **0.947**, WF 5/6, SH PASS 0.624/1.524, **98% param robust**, H-012 corr **0.052** — excellent diversifier). ETH/BTC ratio, monthly calendar, vol-of-vol, multi-TF, BTC dominance — all fail. **Batch 4 (H-660–H-667)**: **H-666 CONFIRMED** (Multi-Asset Skew Portfolio, IS 0.887, SH PASS) but NOT deployed — inferior to H-657 BTC-only. Kurtosis, tail ratio, Hurst, autocorrelation all fail. **667 total hypotheses.**
- Next: Await Q-005 answer. Monitor all 75 runners (esp. H-657). H-063 trade 3. Explore options strategies, on-chain data, or micro-structure signals.
- Questions added: none
- Self-modifications: H-657 runner created, added to orchestrator. Archived session 170. (session 180)

### Session 2026-04-11 review+deploy+research (session 181)
- Goal: Review + Deploy + Research — MTM update, 16 new backtests (2 batches of 8), 4 new deployments
- Focus: Paper trade MTM (BTC $72,751), calendar/timing effects (H-668–H-675) and multi-period/composite strategies (H-676–H-683)
- Done: 79 runners (75→79). **30/74 positive** (41%). Avg **-0.17%** (stable). H-063 trade 3 active (75000C/71000P, $196 premium, exp Apr 17). **Batch 1 (H-668–H-675, calendar/timing)**: All 8 REJECTED. Turn-of-month (Sharpe -1.46), week-of-month (data-mined), expiry effects (not significant), funding settlement (Sharpe 0.23), weekend drift (SH fail), intra-month seasonality (WF fail), quarterly expiry (N=8 insufficient), monthly momentum (SH fail). **Batch 2 (H-676–H-683, multi-period/novel)**: **H-676 CONFIRMED** (BTC 3d Contrarian, Sharpe 1.308, **WF 5/5**, param 100%, H-012 corr **-0.039**). **H-677 CONFIRMED** (BTC Crash Bounce, active Sharpe 1.610, **WF 5/5**, H-009 corr **-0.455**). **H-679 CONFIRMED** (BTC Vol Regime Switch, Sharpe 1.464, WF 4/5, param 88%, H-012 corr 0.023). **H-680 CONFIRMED** (Return-Volume Convergence XS, Sharpe 1.486, WF 4/5, param 90%, H-012 corr 0.264). 4 REJECTED (H-678 marginal, H-681 directional, H-682 below threshold, H-683 SH fail). **683 total hypotheses.**
- Next: Await Q-005 answer. Monitor 79 runners. Calendar effects exhausted in crypto. Explore options strategies (need more IV data), on-chain data.
- Questions added: none
- Self-modifications: H-676/H-677/H-679/H-680 runners created, added to orchestrator. Archived session 171. (session 181)

### Session 2026-04-11 review+research (session 182)
- Goal: Review + Research — MTM update, 16 new backtests (2 batches of 8), 0 deployments
- Focus: Paper trade MTM (BTC $72,665), gold-crypto intermarket signals (H-684–H-691) and OHLC microstructure (H-692–H-699)
- Done: 79 runners (unchanged). **30/79 positive** (38%). Avg **-0.16%**. H-063 new iron condor (70K/75.5K, exp Apr 13). **Batch 1 (H-684–H-691, gold-crypto)**: All 8 REJECTED. Fetched XAUT (gold) 1yr data. Gold-crypto correlation, gold momentum regime, gold/BTC ratio, gold return predictor, gold vol spillover, gold corr regime, gold-adjusted momentum, gold hedging demand — none work. Gold doesn't predict crypto XS. **Batch 2 (H-692–H-699, microstructure)**: All 8 REJECTED after look-ahead correction. **CRITICAL BUG FOUND**: SH test in batch scripts was broken (permutation preserves mean → always p≈1). Fixed with t-test+bootstrap. **CRITICAL FINDING**: H-698 4h Momentum had Sharpe 3.201 that dropped to 0.189 after 1-day lag (100% look-ahead bias). H-692/H-699 also artifacts. H-697 Overnight Gap borderline (1.666, SH PASS, WF 3/6). **699 total hypotheses.**
- Next: Await Q-005 answer. Monitor 79 runners. Re-evaluate prior SH FAIL rejects with corrected test. Explore on-chain data or sentiment signals.
- Questions added: none
- Self-modifications: Identified and fixed SH test bug (permutation→t-test). Archived session 172. (session 182)

### Session 2026-04-11 review+deploy+research (session 183)
- Goal: Review + Deploy + Research — MTM update, 16 new OI-based backtests (2 batches of 8), 1 deployment
- Focus: Paper trade MTM (BTC $72,665), advanced OI signals using real Bybit OI history (H-700–H-715)
- Done: 80 runners (79→80). **31/79 positive** (39%). Avg **-0.15%**. Fetched full OI history from Bybit V5 API (2000+ days BTC/ETH, 1000+ all others). **Batch 1 (H-700–H-707, OI XS + BTC TS)**: **H-703 CONFIRMED+deployed** (OI Surprise, IS 1.578, WF 5/6 mean 1.422, SH 1.41/1.33, H-012 corr -0.01 — perfect diversifier). H-700 OI Velocity (WF 1/4), H-701 OI-Volume Ratio borderline (WF 4/5, SH FAIL). H-705/H-706 BTC OI TS fail. **Batch 2 (H-708–H-715, BTC TS with OI)**: All 8 REJECTED. OI divergence, liquidation proxy, funding-OI composite, ETH/BTC OI ratio, aggregate OI, OI-vol regime, OI percentile, OI breadth — none work for BTC timing. H-715 OI Breadth borderline (Sharpe 0.78, SH FAIL). **715 total hypotheses.**
- Next: Await Q-005 answer. Monitor 80 runners (esp. H-703). OI as TS signal for BTC doesn't work; XS residual is the only viable approach. Explore liquidation data or sentiment APIs.
- Questions added: none
- Self-modifications: H-703 runner created, added to orchestrator. OI data fetcher built (V5 API pagination, 2000+ rows). Archived session 173. (session 183)

### Session 2026-04-11 review+deploy+research (session 184)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 3 new deployments
- Focus: Paper trade MTM (BTC $73,041), basis/carry signals (H-716–H-723), interaction factors (H-724–H-731), novel XS constructions (H-732–H-739)
- Done: 83 runners (80→83). **32/80 positive** (40%). Avg **-0.15%**. **Batch 1 (H-716–H-723, basis/carry)**: All 8 REJECTED. Spot-perp basis is too tight in crypto for any trading signal. Z-score, momentum, regime, XS carry, basis change, composite, basis mom, basis vol — none work. **Batch 2 (H-724–H-731, interaction factors)**: **H-726 CONFIRMED** (Max DD Factor, Sharpe 0.980, **WF 6/6 PERFECT**, 100% param robust, deployed). H-724 Vol×Mom confirmed but redundant (H-012 corr 0.908). H-727 Recovery Speed borderline. H-731 Range Asymmetry borderline. **Batch 3 (H-732–H-739, novel XS)**: **H-736 CONFIRMED** (Volume Delta, Sharpe **1.703**, **WF 6/6**, SH corrected **PASS**, 96% robust, deployed). **H-733 deployed** (DV Change, Sharpe 1.262, 97% robust, H-012 corr 0.046, borderline SH). H-738 Mom Accel borderline. **739 total hypotheses.**
- Next: Await Q-005 answer. Monitor H-726/H-733/H-736. Explore sentiment data, liquidation signals, or non-price data sources.
- Questions added: none
- Self-modifications: H-726/H-733/H-736 runners created, added to orchestrator. Archived session 174. (session 184)
