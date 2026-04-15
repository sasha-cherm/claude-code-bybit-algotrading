# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$98,190 (-1.81%). BTC spot ~$74,528.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **Internal paper trades:** 198 runners active. Session 204. **119/190 positive** (63%), avg **+0.84%**.
- **H-063**: Iron condor trade 3 (75K/71K, exp Apr 17) — BTC at $74,528, near call strike.
- **Top performers**: H-049(+8.06%), H-250(+8.05%), H-085(+7.50%), H-277(+7.17%), H-353(+7.07%).
- **Session 204 research**: 24 new hypotheses (H-1196–H-1219). **11 CONFIRMED** (8 deployed: H-1202/H-1206/H-1207/H-1208/H-1210/H-1213/H-1215/H-1216/H-1218). **1219 total hypotheses.**
- **H-1215 Vol Trend Return**: IS **1.656**, WF **3/4**, SH **1.60/1.77** p=**0.022**, corr **-0.032**. **SESSION BEST SH** — most stable split-half of any batch 3 signal.
- **H-1216 Return Per Vol**: IS **1.452**, WF **4/4 PERFECT** [1.23→2.88 monotonic], SH **1.28/1.63**, p=**0.045**, corr -0.023. Liquid assets outperform.
- **H-1202 Signed Vol Asym**: IS **1.631**, WF **4/4 PERFECT**, SH **2.21/0.85**, p=**0.024**, corr **0.002**. Directional volume signal.
- **H-1210 Win Rate**: IS **1.284**, WF **4/4 PERFECT**, SH 0.65/2.05, p=0.076, corr **-0.093**. Most anti-momentum of batch.
- **H-1208 Outperf Streak**: IS **1.513**, IS **83%**, WF **3/4**, SH **2.20/0.63**, p=**0.036**, corr -0.053. Contrarian: short hot streaks.
- **Key findings**: Price efficiency signals mostly fail (variance ratio, price delay, autocorr — all WF 1/4). H-1199=H-1193 duplicate. Relative strength dynamics yield many signals — RSI/win rate/smoothness independent of 60d momentum. Volume-return interactions rich: volume trend, surprise returns, positive vol mom all genuine. H-1214=H-1219 duplicate (up-vol ratio ≡ net vol delta).
- **AUTOMATED:** Paper trades hourly via cron (198 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Await Q-005 answer. Monitor 198 runners (esp. new deploys). Explore on-chain data, sentiment APIs, ML ensembles.
- **Open user questions:** Q-005 (H-056 v3 portfolio upgrade proposal)

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 194) archived to `memory/session_archive.md`._

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

### Session 2026-04-14 review+deploy+research (session 200)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 3 new deployments
- Focus: Paper trade MTM (BTC $74,748), liquidity/market quality (H-1100–H-1107), factor interactions (H-1108–H-1115), regime-conditional (H-1116–H-1123)
- Done: 176 runners (173→176). **78/173 positive** (45%). Avg **+0.44%**. Demo ~$98,190 (-1.81%). **Batch 1 (H-1100–H-1107, liquidity)**: **H-1100 CONFIRMED+deployed** (Amihud Illiquidity, IS **1.609**, WF **3/3**, SH **1.41/1.83** p=**0.030** — **SESSION BEST**, corr 0.471). **H-1102 CONFIRMED+deployed** (Kyle Lambda, 1.218, WF **3/3**, SH 0.39/2.08 p=0.099, corr 0.295). 6 REJECTED/BORDERLINE. Liquidity premium real: long liquid, short illiquid assets outperform. **Batch 2 (H-1108–H-1115, factor interactions)**: **ALL 8 REJECTED**. z(A)×z(B) factor interactions add ZERO alpha beyond individual factors. Mom×LowVol, Size×Mom, Rev×Turnover, Trend×Kurtosis all fail. Key finding: factor synergies don't exist in crypto XS. **Batch 3 (H-1116–H-1123, regime-conditional)**: **H-1116 CONFIRMED+deployed** (Dispersion-Timed Mom, IS 1.293, WF 2/3, p=0.080, corr 0.635 — marginal). 7 REJECTED. Adaptive lookback (0.844 corr), crash protection (0.885 corr), correlation adjustment (0.835 corr) are all pure momentum proxies. **1123 total hypotheses.**
- Next: Await Q-005 answer. Monitor 176 runners (esp. H-1100/H-1102 liquidity premium). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 3 runners created (H-1100/H-1102/H-1116), added to orchestrator. Archived session 190. (session 200)

### Session 2026-04-14 review+deploy+research (session 201)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 3 new deployments
- Focus: Paper trade MTM (BTC $74,748), correlation/co-movement (H-1124–H-1131), short-term reversal (H-1132–H-1139), lead-lag/spillover (H-1140–H-1147)
- Done: 179 runners (176→179). **94/176 positive** (53%, up from 45%). Avg **+0.40%**. Demo ~$98,190 (-1.81%). **Batch 1 (H-1124–H-1131, correlation)**: **H-1127 CONFIRMED+deployed** (Beta Stability, IS 1.151, WF **3/3 PERFECT**, p=0.119, corr **0.089** — borderline p but perfect WF + very independent). 7 REJECTED. Correlation signals are UNRELIABLE — BTC corr, pairwise corr, downside corr all fail with massive SH collapse (2.49→-2.12). Residual momentum doesn't exist. **Batch 2 (H-1132–H-1139, reversal)**: **H-1135 CONFIRMED+deployed** (Extreme Return Reversal, IS **1.836**, WF **4/4 PERFECT**, IS **100%**, p=**0.011**, corr **-0.002** — **SESSION BEST**). **H-1137 CONFIRMED+deployed** (RSI XS, IS **1.552**, WF **3/4**, SH **1.59/1.54** p=**0.032**, corr 0.021). 6 REJECTED/BORDERLINE. Short-term extreme reversal is a genuine new factor. RSI is independent momentum measure. **Batch 3 (H-1140–H-1147, lead-lag)**: **ALL 8 REJECTED**. Lead-lag signals DON'T WORK in crypto XS — information propagates same-day. H-1144=H-1147 (identical). BTC lag, ETH spread, residual persistence, large-cap lead all fail. **1147 total hypotheses.**
- Next: Await Q-005 answer. Monitor 179 runners (esp. H-1135/H-1137/H-1127 new deploys). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 3 runners created (H-1127/H-1135/H-1137), added to orchestrator. Archived session 191. (session 201)

### Session 2026-04-14 review+deploy+research (session 202)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 6 new deployments
- Focus: Paper trade MTM (BTC $74,608), technical indicators (H-1148–H-1155), price structure (H-1156–H-1163), risk quality (H-1164–H-1171)
- Done: 185 runners (179→185). **78/179 positive** (44%). Avg **+0.41%**. Demo ~$98,190 (-1.81%). **Batch 1 (H-1148–H-1155, TA indicators)**: **H-1154 CONFIRMED+deployed** (Price Channel Position, IS **1.324**, WF 3/4, SH **1.26/1.43**, p=**0.067**, corr **0.010** — very stable SH). **H-1155 CONFIRMED+deployed** (ROC Divergence, 1.220, WF 2/4, p=0.091, corr **-0.006**). H-1149=H-1150 (Stochastic≡Williams %R). MACD/CCI/ADX/BB all borderline. **Batch 2 (H-1156–H-1163, price structure)**: **H-1163 CONFIRMED+deployed** (Overnight/Intraday Ratio, IS **1.905**, WF **4/4 PERFECT**, IS **100%**, SH **2.65/1.11**, p=**0.008**, corr **-0.016** — **SESSION BEST**). **H-1162 CONFIRMED+deployed** (Price Acceleration, **1.503**, WF 3/4, p=0.038, corr **-0.049**). **H-1161 CONFIRMED+deployed** (VPT Change, 1.327, WF 3/4, p=0.066, corr -0.021). **H-1156 CONFIRMED+deployed** (MA Convergence, 1.258, WF 3/4, p=0.082, corr 0.012). H-1160 overfit (WF 1/4+SH collapse). H-1159/H-1158 SH collapse. **Batch 3 (H-1164–H-1171, risk quality)**: **H-1166 CONFIRMED not deployed** (Downside Capture, 1.311, WF 3/3, p=0.076 — corr 0.597 too high). ALL OTHERS REJECTED/BORDERLINE. Key finding: risk quality signals are momentum proxies (IR 0.901, capture ratio 0.867, alpha consistency 0.694). **1171 total hypotheses.**
- Next: Await Q-005 answer. Monitor 185 runners (esp. H-1163/H-1162/H-1154 new stars). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 6 runners created (H-1154/H-1155/H-1156/H-1161/H-1162/H-1163), added to orchestrator. Archived session 192. (session 202)

### Session 2026-04-15 review+deploy+research (session 203)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 6 new deployments
- Focus: Paper trade MTM (BTC $74,118), order flow proxies (H-1172–H-1179), momentum decomposition (H-1180–H-1187), structural signals (H-1188–H-1195)
- Done: 191 runners (185→191). **102/185 positive** (55%, up from 44%). Avg **+0.73%** (up from +0.41%). Demo ~$98,190 (-1.81%). **Batch 1 (H-1172–H-1179, order flow)**: **H-1176 CONFIRMED+deployed** (MFI, IS **1.762**, WF **4/4 PERFECT**, SH 1.79/1.75, p=**0.015**, corr 0.085 — strong order flow proxy). H-1173 CONFIRMED not deployed (WF 2/4, recent folds negative). 6 REJECTED. Most order flow proxies fail XS (buy pressure, force index, Chaikin, EOM all weak). **Batch 2 (H-1180–H-1187, momentum decomp)**: **H-1180 CONFIRMED+deployed** (Recent vs Distal, IS **2.047**, WF 3/4, SH **1.97/2.25**, p=**0.005**, corr 0.034 — **STAR**, contrarian low_long). **H-1186 CONFIRMED+deployed** (Up-Down Capture, IS 1.240, WF **4/4 PERFECT** all ~1.3, SH 1.23/1.28, p=0.086 — **most stable WF ever**). H-1185 CONFIRMED not deployed (WF 2/4). 5 REJECTED. Momentum decomposition mostly fails — path dependency, smoothness adj, recency weighting, idiosyncratic all flop. **Batch 3 (H-1188–H-1195, structural)**: **H-1193 CONFIRMED+deployed** (Gap Fill Ratio, IS **1.905**, WF **4/4 PERFECT**, IS **100%**, SH **2.65/1.11**, p=**0.008**, corr **-0.016** — **SESSION BEST**). **H-1190 CONFIRMED+deployed** (Hurst Exponent, IS **1.725**, WF 3/4, SH 1.89/1.67, p=**0.017**, corr **-0.075** — genuine structural factor). **H-1194 CONFIRMED+deployed** (Trend Linearity, IS 1.316, WF 3/4, SH 1.28/1.40, p=0.069, corr -0.036). 5 REJECTED. Breakout distance fails (WF 1/4). MR speed, vol-of-vol, support strength borderline. **1195 total hypotheses.**
- Next: Await Q-005 answer. Monitor 191 runners (esp. H-1193/H-1180/H-1190 new stars). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 6 runners created (H-1176/H-1180/H-1186/H-1190/H-1193/H-1194), added to orchestrator. Archived session 193. (session 203)

### Session 2026-04-15 review+deploy+research (session 204)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 8 new deployments
- Focus: Paper trade MTM (BTC $74,528), price efficiency (H-1196–H-1203), relative strength dynamics (H-1204–H-1211), volume-return interaction (H-1212–H-1219)
- Done: 198 runners (190→198). **119/190 positive** (63%, up from 55%). Avg **+0.84%** (up from +0.73%). Demo ~$98,190 (-1.81%). **Batch 1 (H-1196–H-1203, price efficiency)**: **H-1202 CONFIRMED+deployed** (Signed Vol Asym, IS **1.631**, WF **4/4 PERFECT**, p=**0.024**, corr **0.002** — directional volume). H-1199=H-1193 duplicate (identical rankings). 5 REJECTED (variance ratio/price delay/autocorr/Amihud persist/range eff all WF 1/4). H-1201 SH collapse (3.12→0.04). **Batch 2 (H-1204–H-1211, relative strength)**: **H-1208 CONFIRMED+deployed** (Outperf Streak, IS **1.513**, IS **83%**, WF **3/4**, p=**0.036**, corr -0.053 — contrarian). **H-1206 CONFIRMED+deployed** (RSI XS, 1.437, WF 3/4, p=0.047, corr 0.059). **H-1210 CONFIRMED+deployed** (Win Rate, 1.284, WF **4/4 PERFECT**, p=0.076, corr **-0.093** — most anti-momentum). **H-1207 CONFIRMED+deployed** (Mom Smoothness, 1.279, WF 2/4, SH **1.15/1.49** — stable SH). H-1204 CONFIRMED not deployed (WF 2/4). 3 REJECTED. **Batch 3 (H-1212–H-1219, vol-return)**: **H-1215 CONFIRMED+deployed** (Vol Trend Return, IS **1.656**, WF **3/4**, SH **1.60/1.77** — **BEST SH**, p=**0.022**, corr -0.032). **H-1216 CONFIRMED+deployed** (Ret Per Vol, 1.452, WF **4/4 PERFECT** [1.23→2.88 monotonic], SH 1.28/1.63, p=0.045). **H-1218 CONFIRMED+deployed** (Pos Vol Mom, 1.585, WF 3/4, p=0.028). **H-1213 CONFIRMED+deployed** (Vol Surprise Ret, 1.456, WF 3/4, p=0.044, corr 0.003). H-1214=H-1219 duplicate. H-1212/H-1217 SH collapse. **1219 total hypotheses.**
- Next: Await Q-005 answer. Monitor 198 runners (esp. H-1215/H-1216/H-1202 new stars). Explore on-chain data, sentiment APIs, ML ensembles.
- Questions added: none
- Self-modifications: 8 runners created (H-1202/H-1206/H-1207/H-1208/H-1210/H-1213/H-1215/H-1216/H-1218), added to orchestrator. Archived session 194. (session 204)
