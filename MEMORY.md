# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$98,017 (-1.96%). BTC spot ~$70,949.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **Internal paper trades:** 114 runners active. Session 190. **43/106 positive** (40%), avg **+0.24%**.
- **H-063**: ~$9,591 (-4.09%). Iron condor trade 3 (75K/71K, exp Apr 17) — BTC at $70,949.
- **Top performers**: H-277(+7.44%), H-353(+7.37%), H-332(+5.99%), H-169(+5.13%), H-049(+4.98%).
- **Session 190 research**: 24 new hypotheses (H-860–H-883). **8 CONFIRMED+deployed** (H-861/H-863/H-864/H-866/H-867/H-873/H-878/H-882). **883 total hypotheses.**
- **H-864 Conditional Momentum**: IS Sharpe **1.608**, WF **4/5**, SH p=**0.025**, H-012 corr **0.000** (zero!). Volume-filtered momentum is entirely different signal. Session best novel finding.
- **H-867 Max Gain Dependency**: IS Sharpe **1.766** (highest), WF **3/4**, SH p=**0.015**, corr **0.046**. Penalizing tail-dependent returns is novel and powerful.
- **H-866 VW Return Divergence**: IS Sharpe **1.591**, WF **3/5**, SH p=**0.027**, corr **0.005**. Smart money buying signal.
- **Key findings**: Return decomposition is rich signal space — downside protection, win rate, conditional momentum, VW divergence, max gain dependency all work as XS signals. Mean reversion/contrarian FAILS in crypto XS (RSI, z-score, Bollinger all 0% positive). Technical indicators mixed — Stochastic and EMV work as XS signals, MACD/CCI/CMF/Force Index borderline. OBV Slope had WF 5/5 PERFECT but SH borderline.
- **AUTOMATED:** Paper trades hourly via cron (114 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Await Q-005 answer. Monitor 114 runners (esp. H-864/H-867/H-866 new stars). Explore on-chain data, sentiment APIs, ML ensembles, or OBV Slope re-test with more data.
- **Open user questions:** Q-005 (H-056 v3 portfolio upgrade proposal)

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 180) archived to `memory/session_archive.md`._

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

### Session 2026-04-12 review+deploy+research (session 188)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 5 new deployments
- Focus: Paper trade MTM (BTC $71,606), cross-asset information flow (H-812–H-819), higher-order/non-linear stats (H-820–H-827), composite/ensemble signals (H-828–H-835)
- Done: 100 runners (95→100). **43/95 positive** (45%). Avg **+0.30%**. Demo ~$98,361 (-1.64%, recovering). H-063 trade 3 active ($9,651). **Batch 1 (H-812–H-819, cross-asset info)**: **H-814 CONFIRMED+deployed** (Rank Velocity, IS **1.886**, WF 3/4, SH p=0.011, corr 0.062). **H-817 CONFIRMED+deployed** (Vol Spillover, IS **1.423**, WF 3/4, SH p=0.054, corr 0.011). BTC propagation fails (-0.475). Breadth mom, comovement, synchronicity, idiosyncratic mom — all fail OOS. **Batch 2 (H-820–H-827, higher-order)**: **H-824 CONFIRMED+deployed** (Min Daily Return/Resilience, IS **2.094**, WF **5/5 PERFECT**, SH p=**0.004**, corr **-0.052** — **session best**). Coskewness, downside beta, entropy, Herfindahl, Sortino — all fail. H-822 Low Quantile Spread borderline (WF 5/5 but SH fail). **Batch 3 (H-828–H-835, composite/ensemble)**: **H-828 CONFIRMED+deployed** (Top-5 Ensemble, IS **1.693**, WF 3/4, SH p=0.020, corr **-0.001**). **H-831 CONFIRMED+deployed** (Vol-Confirmed Breakout, IS **1.274**, WF 4/5, SH p=0.078, corr 0.006). PCA residual borderline (SH fail). Regime-conditional, funding-OI composite, variance ratio — fail. **835 total hypotheses.**
- Next: Await Q-005 answer. Monitor 100 runners (esp. H-824 with Sharpe 2.094). H-063 iron condor near 71K put. Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 5 runners created (H-814/H-817/H-824/H-828/H-831), added to orchestrator. Archived session 178. (session 188)

### Session 2026-04-12 review+deploy+research (session 189)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 5 new deployments
- Focus: Paper trade MTM (BTC $71,017), liquidity/illiquidity signals (H-836–H-843), drawdown dynamics (H-844–H-851), price patterns (H-852–H-859)
- Done: 106 runners (101→106). **27/101 positive** (27%, BTC -2.5% pullback). Avg **+0.37%**. Demo ~$98,017 (-1.96%). **Batch 1 (H-836–H-843, liquidity)**: **H-837 CONFIRMED+deployed** (Volume Turnover, IS **1.958**, WF **5/5**, SH p=**0.006**, corr 0.058). **H-843 CONFIRMED+deployed** (Range-Vol Ratio, IS **2.038**, WF **5/5**, SH p=**0.005**, corr **-0.015** — **session best**). H-836 Amihud CONFIRMED but NOT deployed (0.696 corr H-843). H-840 Price Impact CONFIRMED but NOT deployed (redundant). 4 REJECTED. **Batch 2 (H-844–H-851, drawdown)**: **H-849 CONFIRMED+deployed** (Underwater Vol, IS **1.463**, WF 4/5, SH p=0.043, corr **0.001** — perfect diversifier). **H-851 CONFIRMED+deployed** (DD Mean Reversion, IS **1.637**, WF 3/4, SH p=0.027, corr -0.012). H-844 DD Depth CONFIRMED but borderline. H-847 DD-Adj Mom REJECTED (0.884 corr H-012). 4 REJECTED. **Batch 3 (H-852–H-859, patterns)**: **H-854 CONFIRMED+deployed** (CLV, IS **1.267**, WF 4/5, SH p=0.078, corr 0.005). H-858 Weighted Mom REJECTED (0.939 corr H-012). 6 REJECTED. **859 total hypotheses.**
- Next: Await Q-005 answer. Monitor 106 runners (esp. H-843/H-837/H-849). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 5 runners created (H-837/H-843/H-849/H-851/H-854), added to orchestrator. Archived session 179. (session 189)

### Session 2026-04-12 review+deploy+research (session 190)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 8 new deployments
- Focus: Paper trade MTM (BTC $70,949), return decomposition/quality (H-860–H-867), short-term reversal (H-868–H-875), technical indicator XS (H-876–H-883)
- Done: 114 runners (106→114). **43/106 positive** (40%). Avg **+0.24%**. Demo ~$98,017 (-1.96%). **Batch 1 (H-860–H-867, return quality)**: **5 CONFIRMED+deployed**: H-864 Conditional Momentum (Sharpe **1.608**, WF 4/5, SH p=0.025, **corr 0.000** — zero!), H-867 Max Gain Dep (**1.766**, WF 3/4, p=0.015), H-866 VW Return Div (**1.591**, WF 3/5, p=0.027, corr 0.005), H-873 Dist High (1.391, WF 4/5), H-861 Downside Protect (1.255, WF 3/4). H-863 Win Rate (1.207, WF 4/5). H-860/H-862/H-865 REJECTED. **Batch 2 (H-868–H-875, reversal)**: **1 CONFIRMED** H-873 Dist from High (1.391, WF 4/5, SH p=0.053). Mean reversion FAILS in crypto XS (RSI, z-score, Bollinger all 0% positive). 3-day reversal Sharpe 1.841 but WF 2/5 fail. **Batch 3 (H-876–H-883, technical)**: **2 CONFIRMED**: H-878 Stochastic (1.406, WF 3/5, corr 0.005), H-882 EMV (1.383, WF 3/5, corr -0.009). H-881 OBV Slope notable (WF 5/5 PERFECT but SH p=0.122). MACD/CCI borderline, Williams/Force fail. **883 total hypotheses.**
- Next: Await Q-005 answer. Monitor 114 runners (esp. H-864/H-867/H-866 new stars). Explore on-chain data, sentiment APIs, ML ensembles, OBV Slope re-test.
- Questions added: none
- Self-modifications: 8 runners created (H-861/H-863/H-864/H-866/H-867/H-873/H-878/H-882), added to orchestrator. Archived session 180. (session 190)
