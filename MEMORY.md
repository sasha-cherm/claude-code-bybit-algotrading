# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$98,190 (-1.81%). BTC spot ~$74,354.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **Internal paper trades:** 173 runners active. Session 199. **94/167 positive** (56%), avg **+0.44%**.
- **H-063**: ~$9,624 (-3.76%). Iron condor trade 3 (75K/71K, exp Apr 17) — BTC at $74,354, approaching call strike.
- **Top performers**: H-049(+7.98%), H-277(+7.17%), H-353(+7.07%), H-754(+6.41%), H-332(+5.60%).
- **Session 199 research**: 24 new hypotheses (H-1076–H-1099). **7 CONFIRMED** (6 deployed: H-1077/H-1078/H-1081/H-1087/H-1090/H-1091). **1099 total hypotheses.**
- **H-1081 Relative Volume Surprise**: IS Sharpe **1.923**, WF **4/4 PERFECT**, SH p=**0.007**, SH **1.97/1.90**, corr **0.043**. **SESSION BEST** — volume surge relative to XS peers captures capital flow.
- **H-1090 Consecutive Extreme Frequency**: IS Sharpe **2.397**, IS **100%**, WF 3/4, SH p=**0.001**, corr **-0.023**. Vol clustering → trending.
- **H-1091 Overnight Return Share**: IS Sharpe **1.905**, IS **100%**, WF **4/4 PERFECT**, SH p=**0.008**, corr **-0.016**. Institutional accumulation signal.
- **Key findings**: Relative performance dynamics — rank change momentum and outperformance consistency are independent XS signals (corr ~0 with H-012). Return distribution — consecutive extreme frequency and overnight return share are novel strong signals. Multi-horizon composites — ALL 8 are momentum variants (corr 0.57-0.88 with H-012). Term structure, weighted momentum, sign agreement add ZERO independent info beyond 60d momentum.
- **AUTOMATED:** Paper trades hourly via cron (173 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Await Q-005 answer. Monitor 173 runners (esp. H-1081/H-1090/H-1091 new stars). Explore on-chain data, sentiment APIs, ML ensembles.
- **Open user questions:** Q-005 (H-056 v3 portfolio upgrade proposal)

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 189) archived to `memory/session_archive.md`._

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

### Session 2026-04-13 review+deploy+research (session 195)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 6 new deployments
- Focus: Paper trade MTM (BTC $71,115), vol forecasting/regime (H-980–H-987), spread/relative value (H-988–H-995), adaptive/conditional (H-996–H-1003)
- Done: 149 runners (143→149). **67/143 positive** (47%, up from 42%). Avg **+0.22%**. Demo ~$98,126 (-1.87%). **Batch 1 (H-980–H-987, vol forecast)**: **H-986 CONFIRMED+deployed** (Vol Breakout Freq, **2.874**, WF 3/4, p=**0.0001**, corr -0.04 — **SESSION BEST**). H-983 (RV Spread) strong but duplicate H-059. H-985 Vol Asymmetry WF unstable. H-980/H-982/H-984/H-987 all fail IS. Vol compression 0% positive (anti-signal). **Batch 2 (H-988–H-995, relative value)**: **H-992 CONFIRMED+deployed** (XS Skew Position, 1.236, WF **4/5**, p=0.084, corr 0.021). **H-994 CONFIRMED+deployed** (Vol Rank Change, **1.618**, WF 3/5, p=0.025, corr -0.017). H-993 = H-992 duplicate. Rank persistence/beta momentum fail. Relative DD interesting (WF 4/4) but SH fail. **Batch 3 (H-996–H-1003, adaptive)**: **H-1001 CONFIRMED+deployed** (Momentum Breadth, **1.798**, WF **4/4 PERFECT**, p=**0.013**, corr **0.012** — **star**). **H-997 CONFIRMED+deployed** (Mom-Vol Interaction, 1.576, WF 3/5, p=0.029, corr 0.04). **H-1003 CONFIRMED+deployed** (ATR-Norm Return, 1.406, WF 3/5, p=0.051, corr 0.012). Vol climax reversal 0% — contrarian volume fails. PV divergence fails. **1003 total hypotheses.**
- Next: Await Q-005 answer. Monitor 149 runners (esp. H-986/H-1001/H-997 new stars). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 6 runners created (H-986/H-992/H-994/H-997/H-1001/H-1003), added to orchestrator. Archived session 185. (session 195)

### Session 2026-04-13 review+deploy+research (session 196)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 7 new deployments
- Focus: Paper trade MTM (BTC $72,175), cross-timeframe (H-1004–H-1011), relative dynamics (H-1012–H-1019), nonlinear/threshold (H-1020–H-1027)
- Done: 155 runners (148→155). **62/155 positive** (40%). Avg **+0.20%**. Demo ~$98,190 (-1.81%). **Batch 1 (H-1004–H-1011, cross-TF)**: **H-1007 CONFIRMED+deployed** (Intraweek Recovery, IS 1.448, WF **5/5**, p=0.045, corr **0.002**). **H-1009 CONFIRMED+deployed** (Consecutive Up Days, IS 1.490, WF 4/5, p=0.039, corr 0.042). **H-1010 CONFIRMED+deployed** (Weekly Vol Profile, IS **1.939**, WF 3/5, p=**0.007**, corr -0.033 — **SESSION BEST**). Weekly return rank too noisy (IS 0.17). VWAP too weak. 5 REJECTED/BORDERLINE. **Batch 2 (H-1012–H-1019, relative dynamics)**: **H-1013 CONFIRMED+deployed** (DD Recovery, IS 1.394, WF **4/4**, p=0.055, corr -0.062). **H-1016 CONFIRMED+deployed** (Vol Rank Persistence, IS 1.417, WF **4/4**, p=0.051, corr 0.045). **H-1018 CONFIRMED+deployed** (Price Compression, IS 1.432, WF 4/5, p=0.047, corr **-0.017**). Momentum × dispersion fails. Skew trend 0% positive. 5 REJECTED/BORDERLINE. **Batch 3 (H-1020–H-1027, nonlinear)**: **H-1020 CONFIRMED** (Extreme Return Asymmetry, 1.378, WF 2/4, p=0.058 — NOT deployed, weak WF + split-half collapse). **H-1023 CONFIRMED+deployed** (Return Stability, 1.296, WF **4/4**, p=0.074, corr -0.051). Mom regime switch/vol acceleration/reversal all fail. **1027 total hypotheses.**
- Next: Await Q-005 answer. Monitor 155 runners (esp. H-1010/H-1009/H-1018 new stars). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 7 runners created (H-1007/H-1009/H-1010/H-1013/H-1016/H-1018/H-1023), added to orchestrator. Archived session 186. (session 196)

### Session 2026-04-14 review+deploy+research (session 197)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 8 new deployments
- Focus: Paper trade MTM (BTC $73,134), calendar/seasonal (H-1028–H-1035), return persistence/memory (H-1036–H-1043), volume structure/profile (H-1044–H-1051)
- Done: 164 runners (156→164). **63/156 positive** (40%). Avg **+0.21%**. Demo ~$98,190 (-1.81%). **Batch 1 (H-1028–H-1035, calendar/seasonal)**: **H-1028 CONFIRMED+deployed** (TOM Effect, IS **1.979**, WF 3/4, p=0.008, corr -0.031). **H-1033 CONFIRMED+deployed** (Lagged Week Return, IS **1.400**, WF **4/5**, p=0.050, corr -0.023 — very stable SH 1.34/1.55). H-1030 CONFIRMED not deployed (SH collapse 2.99/-0.11). Monthly persistence too slow, reversal anti-signal. 5 REJECTED. **Batch 2 (H-1036–H-1043, return persistence)**: **H-1036 CONFIRMED+deployed** (Consec Return Dir, IS **1.808**, WF **4/5**, p=0.012, corr -0.036 — contrarian low_long). **H-1041 CONFIRMED+deployed** (Trend Persistence Ratio, IS 1.304, WF 3/4, p=0.072, corr 0.006). **H-1043 CONFIRMED+deployed** (Return Predictability R², IS 1.313, WF **5/5 PERFECT**, p=0.068, corr 0.008 — **STAR**, SH 1.34/1.32). H-1037 CONFIRMED not deployed (SH collapse). Acceleration/freshness/recovery all fail. **Batch 3 (H-1044–H-1051, volume structure)**: **H-1046 CONFIRMED+deployed** (Rel Vol Duration, IS **2.000**, WF **5/5 PERFECT**, p=**0.006**, corr 0.015 — **SESSION BEST**). **H-1047 CONFIRMED+deployed** (Vol-Price Agreement, IS **1.914**, WF 3/5, p=0.008, corr -0.018). **H-1051 CONFIRMED+deployed** (Vol Mom Spread, IS 1.581, WF 3/4, p=0.033, corr 0.070). Vol skewness/concentration/Gini/buy-ratio all fail. **1051 total hypotheses.**
- Next: Await Q-005 answer. Monitor 164 runners (esp. H-1046/H-1043/H-1036 new stars). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 8 runners created (H-1028/H-1033/H-1036/H-1041/H-1043/H-1046/H-1047/H-1051), added to orchestrator. Archived session 187. (session 197)

### Session 2026-04-14 review+deploy+research (session 198)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 3 new deployments
- Focus: Paper trade MTM (BTC $74,089), funding rate dynamics (H-1052–H-1059), OI structure (H-1060–H-1067), hourly microstructure (H-1068–H-1075)
- Done: 167 runners (164→167). **94/164 positive** (57%, up from 40%). Avg **+0.47%** (up from +0.21%). Demo ~$98,190 (-1.81%). H-063 trade 3 active ($9,624, BTC approaching 75K call). **Batch 1 (H-1052–H-1059, funding dynamics)**: **ALL 8 REJECTED**. Funding rates have NO reliable XS signal — velocity, dispersion, mean reversion, OI interaction, rank momentum, neg freq, vol, z-score all fail. Best was H-1055 (Sharpe 1.033 IS but WF 1/4 + SH collapse). **Batch 2 (H-1060–H-1067, OI structure)**: **H-1065 CONFIRMED+deployed** (OI Rank Stability, IS **1.753**, WF **5/5 PERFECT**, p=**0.016**, corr **-0.037** — **SESSION BEST**). Anti-crowding signal: assets losing OI rank = less crowded → outperform. H-1061 (OI-Price Divergence) borderline (WF 5/5 but p=0.175). OI momentum/surge/velocity/concentration all fail. **Batch 3 (H-1068–H-1075, hourly microstructure)**: **H-1068 CONFIRMED+deployed** (Day/Night Vol Ratio, IS **1.330**, WF **4/5**, p=**0.063**, corr **0.006**, SH 1.32/1.36 — remarkably stable). **H-1071 CONFIRMED+deployed** (Range Expansion, IS **1.365**, WF **4/5**, p=**0.056**, corr **0.020**, SH 1.83/0.82). H-1069 (Autocorr) strong IS but WF 1/5 overfit. Session momentum/MR speed/vol clock/CLV all fail. **1075 total hypotheses.**
- Next: Await Q-005 answer. Monitor 167 runners (esp. H-1065/H-1068/H-1071 new stars). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 3 runners created (H-1065/H-1068/H-1071), added to orchestrator. Archived session 188. (session 198)

### Session 2026-04-14 review+deploy+research (session 199)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 6 new deployments
- Focus: Paper trade MTM (BTC $74,354), relative performance dynamics (H-1076–H-1083), return distribution properties (H-1084–H-1091), multi-horizon composites (H-1092–H-1099)
- Done: 173 runners (167→173). **94/167 positive** (56%). Avg **+0.44%**. Demo ~$98,190 (-1.81%). **Batch 1 (H-1076–H-1083, relative performance)**: **H-1081 CONFIRMED+deployed** (Rel Vol Surprise, IS **1.923**, WF **4/4 PERFECT**, p=**0.007**, SH 1.97/1.90 — **SESSION BEST**, corr 0.043). **H-1077 CONFIRMED+deployed** (Rank Change Mom, 1.390, WF 3/4, p=0.053, corr -0.031). **H-1078 CONFIRMED+deployed** (Outperf Consistency, 1.239, WF 3/4, p=0.084, corr -0.014). **H-1080 CONFIRMED not deployed** (Catch-Up, 1.412, WF 2/4, p=0.049 — weak WF). 4 REJECTED. **Batch 2 (H-1084–H-1091, return distribution)**: **H-1090 CONFIRMED+deployed** (Consec Extreme Freq, IS **2.397**, IS 100%, WF 3/4, p=**0.001**, corr -0.023 — vol clustering). **H-1091 CONFIRMED+deployed** (Overnight Return Share, IS **1.905**, IS 100%, WF **4/4 PERFECT**, p=**0.008**, corr -0.016 — institutional accumulation). **H-1087 CONFIRMED+deployed** (Return Kurtosis, 1.198, WF 3/4, p=0.097, corr 0.019 — thin tails outperform). 5 REJECTED/BORDERLINE. **Batch 3 (H-1092–H-1099, multi-horizon)**: **ALL 8 REJECTED** — every multi-horizon composite is a momentum proxy (corr 0.57-0.88 with H-012). Term structure slope, weighted momentum, sign agreement, multi-horizon Sharpe all add zero independent information. **1099 total hypotheses.**
- Next: Await Q-005 answer. Monitor 173 runners (esp. H-1081/H-1090/H-1091 new stars). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 6 runners created (H-1077/H-1078/H-1081/H-1087/H-1090/H-1091), added to orchestrator. Archived session 189. (session 199)
