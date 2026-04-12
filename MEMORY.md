# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$97,767 (-2.23%, recovering). BTC spot ~$71,452.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **Internal paper trades:** 95 runners active. Session 187. **43/93 positive** (46%), avg **+0.31%**.
- **H-063**: ~$9,624 (-3.76%). Iron condor trade 3 (75K/71K, exp Apr 17) — BTC at $71,452, approaching 71K put.
- **Top performers**: H-277(+7.44%), H-353(+7.37%), H-332(+5.99%), H-169(+5.13%), H-049(+4.98%).
- **Session 187 research**: 24 new hypotheses (H-788–H-811). **2 CONFIRMED+deployed** (H-792/H-810). **811 total hypotheses.**
- **H-792 OI-Price Coherence**: IS Sharpe **1.839**, WF **5/6**, SH p=**0.005**, H-012 corr **-0.097**. Session best.
- **H-810 Volume Trend Strength (Vol-ADX)**: IS Sharpe **1.573**, WF **6/6 PERFECT**, SH p=**0.013**, corr **-0.063**. Novel signal.
- **Key findings**: Intraday structure signals (overnight gaps, VWAP, entropy) fail for XS. OI-based signals continue strong. Momentum-correlated signals (H-796, H-806, H-811) pass IS but fail independence check.
- **AUTOMATED:** Paper trades hourly via cron (95 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Await Q-005 answer. Monitor 95 runners. Explore on-chain data, sentiment APIs, or ML ensemble approaches.
- **Open user questions:** Q-005 (H-056 v3 portfolio upgrade proposal)

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 176) archived to `memory/session_archive.md`._

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

### Session 2026-04-12 review+deploy+research (session 185)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 4 new deployments
- Focus: Paper trade MTM (BTC $73,335), residual/idiosyncratic signals (H-740–H-747), correlation dynamics (H-748–H-755), novel constructions (H-756–H-763)
- Done: 87 runners (83→87). **32/83 positive** (39%). Avg **-0.15%**. Demo ~$95,490 (-4.51%). **Batch 1 (H-740–H-747, residual/idio)**: All 8 REJECTED. Idiosyncratic vol, residual momentum, skewness, beta deviation, tracking error, info ratio, residual reversal, systematic risk share — crypto market factor too dominant, residuals are noise. H-745 Info Ratio decent IS (0.983) but WF 1/4. **Batch 2 (H-748–H-755, correlation dynamics)**: **H-754 CONFIRMED+deployed** (Lead-Lag, IS 1.232, WF **4/4**, SH p=0.089, H-012 corr **-0.014**). H-750 Relative RSI (Sharpe 0.918, SH fail). H-753 Corr Concentration (WF 1/4). 6 REJECTED. **Batch 3 (H-756–H-763, novel constructions)**: **H-759 CONFIRMED+deployed** (ADX Trend Strength, IS **1.723**, WF **5/5**, SH p=0.016, corr 0.064). **H-761 CONFIRMED+deployed** (Gap Signal, IS **1.673**, WF **5/5**, SH p=0.019, corr 0.054). **H-763 CONFIRMED+deployed** (Mom-Vol Ratio, IS 1.239, WF 3/5, SH p=0.085, corr 0.027). H-757 Return Consistency borderline (SH p=0.103). H-758 Momentum Persistence param-fragile. **763 total hypotheses.**
- Next: Await Q-005 answer. Monitor 87 runners (esp. H-754/H-759/H-761/H-763). H-063 expires tomorrow. Explore multi-TF combinations, sentiment APIs.
- Questions added: none
- Self-modifications: H-754/H-759/H-761/H-763 runners created, added to orchestrator. Archived session 175. (session 185)

### Session 2026-04-12 review+deploy+research (session 186)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 7 new deployments
- Focus: Paper trade MTM (BTC $73,082), sequential patterns (H-764–H-771), interaction signals (H-772–H-779), composite signals (H-780–H-787)
- Done: 94 runners (87→94). **45/87 positive** (52%, up from 39%). Avg **+0.49%** (recovered from -0.15%). Demo ~$95,490 (-4.51%). **Batch 1 (H-764–H-771, sequential/pattern)**: **H-768 CONFIRMED+deployed** (Sequential Pattern, IS 1.667, WF 3/4, SH p=0.022, corr -0.018). **H-769 CONFIRMED+deployed** (Multi-Horizon Divergence contrarian, IS 1.544, WF 4/5, SH p=0.032, corr 0.015). H-766 Vol-Weighted Return had IS 1.47 but WF 2/4 fail. 6 REJECTED. **Batch 2 (H-772–H-779, interaction/conditional)**: **H-773 CONFIRMED+deployed** (OI-Confirmed Momentum, IS **1.698**, WF **4/4 PERFECT**, SH p=0.020, corr **-0.001** — session best). **H-777 CONFIRMED+deployed** (PVT, IS 1.679, WF 3/5, SH p=0.020, corr -0.024). **H-778 CONFIRMED+deployed** (CLV, IS 1.506, WF **4/4 PERFECT**, SH p=0.039, corr -0.034). H-772/H-774/H-775 all borderline SH fail. 5 REJECTED. **Batch 3 (H-780–H-787, composite)**: **H-781 CONFIRMED+deployed** (Signal Agreement, IS 1.293, WF 4/5, SH p=0.072, corr -0.008). **H-786 CONFIRMED+deployed** (Vol-Confirmed Strength, IS 1.213, WF 3/4, SH p=0.096, corr -0.016). H-783/H-784/H-785 had IS Sharpe 1.85-1.93 but ALL WF 2/4 — proves high IS ≠ real signal. 6 REJECTED. **787 total hypotheses.**
- Next: Await Q-005 answer. Monitor 94 runners (esp. H-773/H-778 with perfect WF). Explore sentiment APIs, on-chain data.
- Questions added: none
- Self-modifications: 7 runners created (H-768/H-769/H-773/H-777/H-778/H-781/H-786), added to orchestrator. Archived session 176. (session 186)

### Session 2026-04-12 review+deploy+research (session 187)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 2 new deployments
- Focus: Paper trade MTM (BTC $71,452), liquidation proxy/tail-risk/OI signals (H-788–H-795), intraday structure/volume clock (H-796–H-803), information-theoretic/regime signals (H-804–H-811)
- Done: 95 runners (93→95). **43/93 positive** (46%). Avg **+0.31%**. Demo ~$97,767 (-2.23%, recovering). H-063 trade 3 active (BTC near 71K put strike). **Batch 1 (H-788–H-795, liquidation/tail/OI)**: **H-792 CONFIRMED+deployed** (OI-Price Coherence, IS **1.839**, WF **5/6**, SH p=**0.005**, corr **-0.097** — session best). 7 REJECTED. Liquidation proxy, tail asymmetry, recovery speed, funding velocity — all fail. **Batch 2 (H-796–H-803, intraday structure)**: All 8 REJECTED. Volume clock momentum corr 0.594 with H-012 + split-half fail. Overnight gaps, VWAP, entropy, intraday reversal, range compression — no XS edges from intraday structure. **Batch 3 (H-804–H-811, info-theoretic/regime)**: **H-810 CONFIRMED+deployed** (Vol Trend Strength Vol-ADX, IS **1.573**, WF **6/6 PERFECT**, SH p=**0.013**, corr **-0.063**). H-806 Conditional Vol Ratio strong IS but split-half fail + corr 0.666. H-811 Multi-Period Consistency passes all tests except corr 0.601 (redundant with momentum). **811 total hypotheses.**
- Next: Await Q-005 answer. Monitor 95 runners (esp. H-792/H-810). H-063 iron condor — BTC near 71K put strike, watch closely. Explore on-chain data, sentiment APIs.
- Questions added: none
- Self-modifications: H-792/H-810 runners created, added to orchestrator. Archived session 177. (session 187)
