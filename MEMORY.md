# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$98,126 (-1.87%). BTC spot ~$70,842.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **Internal paper trades:** 142 runners active. Session 194. **61/142 positive** (42%), avg **+0.22%**.
- **H-063**: ~$9,632 (-3.68%). Iron condor trade 3 (75K/71K, exp Apr 17) — BTC at $70,842.
- **Top performers**: H-277(+7.17%), H-353(+7.07%), H-332(+5.60%), H-169(+5.13%), H-049(+4.98%).
- **Session 194 research**: 24 new hypotheses (H-956–H-979). **9 CONFIRMED** (9 deployed: H-959/H-960/H-961/H-963/H-964/H-970/H-971/H-974/H-979). **979 total hypotheses.**
- **H-970 Higher Lows Count**: IS Sharpe **2.464**, WF **5/5 PERFECT**, SH p=**0.001**, H-012 corr **-0.008**. **SESSION BEST** — textbook uptrend structure as XS factor. Strongest WF ever (all folds >0.95).
- **H-964 Momentum Conviction**: IS Sharpe **2.074**, WF **4/4 PERFECT**, SH p=**0.005**, corr **-0.006**. Path-adjusted momentum — penalizes volatile zigzag gains.
- **H-979 Consecutive Range Expansion**: IS Sharpe **2.204**, WF **5/5 PERFECT**, SH p=**0.002**, corr **0.004**. Increasing activity signal.
- **Key findings**: Distributional dynamics — kurtosis change, median-mean gap, win-loss ratio all fail. Down day frequency and win streak work (simple trend health metrics). Structural signals — higher lows count (Sharpe 2.46!) and overnight gap trend are strong. Microstructure — body ratio and upper shadow useless, but ATR expansion and consecutive range expansion work. Price level = size factor in disguise. Funding × momentum = no signal.
- **AUTOMATED:** Paper trades hourly via cron (142 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Await Q-005 answer. Monitor 142 runners (esp. H-970/H-964/H-979 new stars). Explore on-chain data, sentiment APIs, ML ensembles.
- **Open user questions:** Q-005 (H-056 v3 portfolio upgrade proposal)

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 184) archived to `memory/session_archive.md`._

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

### Session 2026-04-13 review+deploy+research (session 191)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 7 new deployments
- Focus: Paper trade MTM (BTC $71,393), time-series statistics (H-884–H-891), volume dynamics (H-892–H-899), momentum refinements (H-900–H-907)
- Done: 120 runners (113→120). **46/113 positive** (41%). Avg **+0.32%**. Demo ~$98,017 (-1.96%). **Batch 1 (H-884–H-891, TS stats)**: **1 CONFIRMED+deployed**: H-891 Up/Down Ratio (1.233, WF 4/5, corr 0.015). 7 REJECTED. Hurst/AR1/VoV/MAE/Parkinson/CVaR all fail — time-series statistics have no XS predictive power. **Batch 2 (H-892–H-899, volume dynamics)**: **4 CONFIRMED+deployed**: H-899 Vol Trend Persistence (**1.560**, WF **5/5 PERFECT**, p=0.030, corr -0.048 — **session best**), H-898 CumVolDiv (1.713, WF 4/5, p=0.018, corr -0.008), H-892 Vol Acceleration (1.455, WF 3/4, p=0.045, corr -0.026), H-894 Vol-Price Corr (1.314, WF 4/5, p=0.067, corr 0.048). RVOL IS 1.798 but WF 0/4. 4 REJECTED. **Batch 3 (H-900–H-907, momentum refinements)**: **2 CONFIRMED+deployed**: H-902 Momentum Quality (1.598, WF 3/5, p=0.026, corr -0.017), H-900 TF Consistency (1.460, WF 3/4, p=0.044, corr -0.004). H-904 Direction Count CONFIRMED not deployed (redundant H-891). H-903 RetDisp IS 2.108 but WF 1/4. 5 REJECTED. **907 total hypotheses.**
- Next: Await Q-005 answer. Monitor 120 runners (esp. H-899/H-898/H-902 new stars). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 7 runners created (H-891/H-892/H-894/H-898/H-899/H-900/H-902), added to orchestrator. Archived session 181. (session 191)

### Session 2026-04-13 review+deploy+research (session 192)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 7 new deployments
- Focus: Paper trade MTM (BTC $71,204), return shape/distribution (H-908–H-915), price structure/trend anatomy (H-916–H-923), volume-price coupling (H-924–H-931)
- Done: 127 runners (120→127). **62/127 positive** (49%). Avg **+0.28%**. Demo ~$98,126 (-1.87%). **Batch 1 (H-908–H-915, return shape)**: **4 CONFIRMED**: H-914 Return Smoothness (**1.471**, WF 4/5, p=0.040, corr -0.019, deployed), H-915 Sortino-like (**1.549**, WF 3/5, p=0.032, corr 0.044, deployed), H-908 Pos Return Ratio (1.233, WF 4/5, not deployed), H-912 Gain Streak (1.226, WF 4/5, not deployed). H-909=H-911 identical (same signal!). H-913 Up Capture IS fail (17%). **Batch 2 (H-916–H-923, price structure)**: **3 CONFIRMED**: H-916 Trend Linearity (**1.521**, WF 4/5, p=0.034, corr -0.030, deployed), H-917 Price Efficiency (**1.594**, WF 3/5, p=0.026, corr -0.012, deployed), H-920 Higher-Low Ratio (1.483, WF 3/5, not deployed). Hurst/autocorrelation/fractal dim all fail (confirms TS stats useless). **Batch 3 (H-924–H-931, vol-price coupling)**: **3 CONFIRMED**: H-929 VW Momentum (**1.753**, WF 4/5, p=0.015, corr 0.006 — **session best**, deployed), H-931 Vol Regime Change (**1.796**, WF 3/4, p=0.013, corr 0.000, deployed), H-927 Accumulation Index (1.557, WF 4/5, p=0.031, deployed). Vol conviction/PV trend/MFI/breakout/divergence all fail. **931 total hypotheses.**
- Next: Await Q-005 answer. Monitor 127 runners (esp. H-929/H-931/H-927). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 7 runners created (H-914/H-915/H-916/H-917/H-927/H-929/H-931), added to orchestrator. Archived session 182. (session 192)

### Session 2026-04-13 review+deploy+research (session 193)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 6 new deployments
- Focus: Paper trade MTM (BTC $70,896), multi-TF/consensus signals (H-932–H-939), risk-adjusted return factors (H-940–H-947), information/efficiency signals (H-948–H-955)
- Done: 133 runners (127→133). **61/133 positive** (46%). Avg **+0.25%**. Demo ~$98,126 (-1.87%). **Batch 1 (H-932–H-939, multi-TF)**: **H-935 CONFIRMED+deployed** (Trend Strength R², 1.243, WF 3/4, corr -0.043). **H-938 CONFIRMED+deployed** (Range-Adj Mom, **1.585**, WF 3/5, p=0.027, corr 0.018). **H-939 CONFIRMED+deployed** (Vol-Confirmed Trend, 1.182, WF **4/5**, corr **0.001**). H-937 Momentum Z-Score IS 1.854 but WF 2/4. 5 REJECTED. **Batch 2 (H-940–H-947, risk-adjusted)**: **H-940 CONFIRMED+deployed** (Gain-to-Pain, **1.356**, WF **4/5**, p=0.060). **H-946 CONFIRMED+deployed** (Kappa Ratio, 1.251, WF **4/5**, p=0.082). H-941 = H-940 (Omega≡Gain-to-Pain, identical rankings). H-943 Tail Ratio IS 1.589 but WF 1/4. 6 REJECTED. **Batch 3 (H-948–H-955, info/efficiency)**: **H-954 CONFIRMED+deployed** (Drift-to-Volatility, **1.598**, WF 3/5, p=**0.026** — **session best**). H-950 = H-935 (SNR≡signed R², duplicate). Autocorrelation, variance ratio, R² vs BTC, price efficiency all fail. **955 total hypotheses.**
- Next: Await Q-005 answer. Monitor 133 runners (esp. H-954/H-938/H-940). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 6 runners created (H-935/H-938/H-939/H-940/H-946/H-954), added to orchestrator. Archived session 183. (session 193)

### Session 2026-04-13 review+deploy+research (session 194)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 9 new deployments
- Focus: Paper trade MTM (BTC $70,842), distributional dynamics (H-956–H-963), conditional/structural momentum (H-964–H-971), microstructure/candle signals (H-972–H-979)
- Done: 142 runners (133→142). **61/142 positive** (42%). Avg **+0.22%**. Demo ~$98,126 (-1.87%). **Batch 1 (H-956–H-963, distributional)**: **H-959 CONFIRMED+deployed** (Down Day Freq, 1.289, WF **5/5**, corr 0.030). **H-960 CONFIRMED+deployed** (Win Streak, **1.453**, WF 4/5, p=0.043, corr -0.020). **H-961 CONFIRMED+deployed** (Tail Improvement, 1.244, WF 3/4, corr 0.018). **H-963 CONFIRMED+deployed** (Return Concentration, **1.506**, WF 3/5, p=0.037, corr **0.004**). H-957 CONFIRMED but not deployed (WF 2/4 borderline). H-958 Median-Mean Gap 0% positive. 4 REJECTED. **Batch 2 (H-964–H-971, conditional/structural)**: **H-964 CONFIRMED+deployed** (Momentum Conviction, **2.074**, WF **4/4 PERFECT**, p=**0.005**, corr -0.006 — **star**). **H-970 CONFIRMED+deployed** (Higher Lows, **2.464**, WF **5/5 PERFECT**, p=**0.001**, corr -0.008 — **SESSION BEST**). **H-971 CONFIRMED+deployed** (Overnight Gap, **1.890**, WF **5/5**, p=0.009, corr 0.034). H-966 Price Level = size factor. H-967 Funding×Mom = 0%. 5 REJECTED. **Batch 3 (H-972–H-979, microstructure)**: **H-974 CONFIRMED+deployed** (ATR Expansion, **1.763**, WF **4/4 PERFECT**, p=0.015, corr -0.006). **H-979 CONFIRMED+deployed** (ConsRangeExp, **2.204**, WF **5/5 PERFECT**, p=0.002, corr 0.004). H-972 Body Ratio 0% positive. H-973 Vol Autocorr borderline (SH fail). 6 REJECTED. **979 total hypotheses.**
- Next: Await Q-005 answer. Monitor 142 runners (esp. H-970/H-964/H-979 new stars). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 9 runners created (H-959/H-960/H-961/H-963/H-964/H-970/H-971/H-974/H-979), added to orchestrator. Archived session 184. (session 194)
