# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity $99,178 (-0.82%). BTC ~$68,720.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x). No H-011, H-009, H-046.
- **H-011 status**: DROPPED from demo. Internal paper trade IN. Capital $9,871 (-1.29%).
- **Internal paper trades:** 21 runners active. Session 123. BTC ~$68,720.
- **Top performers**: H-031 (+5.01%), H-039 (+4.31%), H-063 (+2.76%), H-019 (+2.56%), H-012 (+2.30%). **12/19 positive** (pre-deploy), 7 negative. +2 new (H-169, H-175).
- **H-063 status**: Vol selling strangle — **+2.76%** (improving). PUT ITM by only ~$280. $1,276 buffer to stop. 1.9d to expiry.
- **H-169 deployed**: Beta-adjusted momentum (alpha factor). Day 0. LONG DOGE/LINK/ETH/AVAX, SHORT ATOM/NEAR/OP/DOT.
- **H-175 CONFIRMED + deployed**: Net money flow factor — IS 100% (30/30), WF 4/6, mean 1.051. Day 0. LONG DOGE/ARB/NEAR/ADA, SHORT ETH/BTC/ATOM/OP.
- **Research**: 175 total hypotheses. H-173 REJECTED (GK vol ratio, 53% IS), H-174 REJECTED (downside beta, 60% IS), **H-175 CONFIRMED** (money flow, 100% IS).
- **AUTOMATED:** Paper trades hourly via cron (21 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Apr 1 bar (00:30 UTC Apr 2): H-085. Apr 2: H-160. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076. Apr 5: H-169. Apr 7: H-175.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 113) archived to `memory/session_archive.md`._

### Session 2026-03-31 review+research+system (session 114)
- Goal: Review + Research + System — MTM update, kill H-024, system hardening, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,644 -0.95%), H-024 kill, position-count guards, H-146/H-147/H-148 backtests
- Done: 18/19 runners OK (H-024 killed). **Demo**: $100,814 (+0.81%). BTC $66,644. **9/18 positive**, 1 flat, 8 negative. **H-019 surged to +7.44%** (low-vol shorts profiting from BTC decline). **H-024 KILLED**: H-019 won decisively +7.44% vs -0.20% (7.64% gap). **H-052 alert**: dropped to -3.74% (was +0.94%). **H-063**: $9,973 (-0.27%), $973 buffer, 3.4d to expiry — manageable. **H-053 positions empty** since session 110 repair — will re-enter on Mar 30 bar. **H-031 rebal state fixed** (positions unchanged but date tracking was wrong). **System**: Position-count guard added to ALL 13 multi-asset runners (prevents corrupted rebalances). Double-write log bug fixed in orchestrator. **Research**: **H-146 REJECTED** (lead-lag spillover — 0/18 positive, crypto has no daily lead-lag). **H-147 REJECTED** (volume skewness — 83% IS, WF 4/6, IS/OOS 1.03, but noisy+0.33 corr momentum+33% DD). **H-148 REJECTED** (DD speed — 58% = noise).
- Next: Mar 30 bar (00:30 UTC Mar 31): H-021/H-031/H-053/H-076 rebal. Mar 31 bar: H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: position-count guard in 13 runners, orchestrator log fix, H-031 state fix (session 114)

### Session 2026-03-31 review+research+system (session 115)
- Goal: Review + Research + System — MTM update, rebalance verification, demo fix, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $67,127, +0.72%), demo ATOM fix, H-149/H-150/H-151 backtests
- Done: 18/18 runners OK. **Demo**: $100,211 (+0.21%). BTC $67,127. **12/18 positive** (best ratio yet), 6 negative. Top: H-031(+5.34%), H-039(+4.35%), H-012(+2.74%). **H-019 dropped** from +7.44% to +2.26% as BTC rally hurt high-vol shorts. **H-052 recovered** from -3.74% to +0.54% after Mar 30 rebalance. **Demo fix**: ATOMUSDT max order qty (22k) added to runner; order split into 2 chunks, executed. **H-063**: $9,968 (-0.32%), $968 buffer to stop, 3.3d to expiry. **Mar 30 bar rebalances verified**: H-021, H-053 (re-entered), H-076 all rebalanced. **Research**: **H-149 REJECTED** (vol concentration — 100% IS but bull-market artifact, WF 1/6, corr 0.45 with momentum). **H-150 REJECTED** (OI-funding interaction — novel low-corr signal but H1/H2 regime split, WF 3/6). **H-151 REJECTED** (conditional momentum — strong WF 5/6 mean 1.54, but only +0.01 over static, split-half fails).
- Next: Mar 31 bar: H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: ATOMUSDT max order qty added to demo runner (session 115)

### Session 2026-03-31 review+research (session 116)
- Goal: Review + Research — MTM update, H-063 monitoring, demo update, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $67,477, +0.52%), H-063 approaching expiry, H-152/H-153/H-154 backtests
- Done: 18/18 runners OK. **Demo**: $100,035 (+0.04%). BTC $67,477. **13/18 positive** (new best ratio), 5 negative. Top: H-031(+5.29%), H-039(+4.35%), H-012(+2.71%). **H-063 crossed into profit!** $10,043 (+0.43%), $1,043 buffer to stop, 3.1d to expiry — theta decay winning. **H-011 continuing slow decline**: net funding $12.62 vs fees $149.24. **Research**: **H-152 REJECTED** (return entropy — 54% IS positive = noise, H2 -0.408, signal too weak). **H-153 REJECTED** (volume surprise — 100% IS, WF 2/6, classic overfitting, H2 -0.788). **H-154 REJECTED** (corr centrality — 91.7% IS, WF 3/6, excellent -0.216 H-012 corr but folds 5&6 negative, signal dying).
- Next: Mar 31 bar (00:30 UTC Apr 1): H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry + H-031 rebal. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 116)

### Session 2026-03-31 review+research (session 117)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,761, -1.06%), H-063 vol selling back negative, H-155/H-156/H-157 backtests
- Done: 18/18 runners OK. **Demo**: $99,936 (-0.06%). BTC $66,761. **12/18 positive**, 6 negative. Top: H-031(+5.34%), H-039(+4.35%), H-012(+2.74%). **H-063 back negative**: $9,909 (-0.91%), PUT ITM by $2,239, $909 buffer to stop, 3.0d to expiry — BTC drop hurt, needs stability. **Research**: **H-155 REJECTED** (Amihud illiquidity — liquid_long IS 100%, WF 6/6 mean 1.25, BUT **corr 0.799 with H-031** = same signal, split-half H1=-0.123). **H-156 REJECTED** (funding rate vol — stable_long IS 89.6%, WF 4/6 mean 0.476, BUT split-half **H1=1.712/H2=-0.075** = signal died. Excellent corr 0.013/−0.013 — novel but decayed). **H-157 REJECTED** (range ratio — noisy_long IS 91.7% but WF **3/6** mean **-0.289**, split-half both halves negative).
- Next: Mar 31 bar (00:30 UTC Apr 1): H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 117)

### Session 2026-03-31 review+research (session 118)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,674, -0.13%), demo declining, H-158/H-159/H-160 backtests
- Done: 18/18 runners OK. **Demo**: $98,020 (-1.98%, down from -0.06%). BTC $66,674. SOL long dragging demo (-$2,546). **12/18 positive**, 6 negative (unchanged). Top: H-031(+5.34%), H-039(+4.35%), H-012(+2.74%). **H-063 slightly improved**: $9,923 (-0.77%, was -0.91%), $923 buffer to stop, 2.8d to expiry — theta helping. **Research**: **H-158 REJECTED** (dual momentum TS+XS — IS 96%, WF 4/6, split-half both positive, BUT **corr 1.000 with H-012** — mathematically identical signal). **H-159 REJECTED** (vol-adjusted return — IS 98%, WF **6/6**, split-half both positive, BUT **corr 0.948 with H-012** — near duplicate). **H-160 CONFIRMED** (trend-quality efficiency×invvol — IS 87%, WF 4/6 mean 0.303, split-half H1=1.174/H2=1.764, **corr 0.355 with H-012, 0.117 with H-076** — all 4/4 criteria pass, genuinely novel).
- Next: Mar 31 bar (00:30 UTC Apr 1): H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 118)

### Session 2026-03-31 review+research+deploy (session 119)
- Goal: Review + Research + Paper Trade — MTM update, H-160 deployment, 3 new factor backtests
- Focus: Paper trade monitoring (BTC ~$67,805, +1.7%), H-063 flipped positive, H-160 deployment, H-161/H-162/H-163 backtests
- Done: 18/18 runners OK (pre-deployment). **13/18 positive** (new best ratio, was 12). BTC rallied +1.7%. **H-063 flipped positive**: $10,110 (+1.10%, was -0.77%) — BTC rally + theta decay winning, 2.6d to expiry. **H-160 deployed** as paper trade #19: LONG ETH/DOGE/SOL, SHORT BTC/OP/ATOM. Added to cron orchestrator. **Research**: **H-161 REJECTED** (variance ratio — 52.8% IS positive = noise, VR has no XS signal in crypto). **H-162 REJECTED** (MAX effect — short_max 33.3%, long_max 66.7%, lottery premium doesn't transfer to crypto). **H-163 REJECTED** (momentum concentration — low_conc_long 79.2%, close but fails 80% threshold).
- Next: Mar 31 bar (00:30 UTC Apr 1): H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG + H-160. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: H-160 runner created, added to orchestrator (session 119)

### Session 2026-03-31 review+research (session 120)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC ~$68,179, +0.6%), demo recovering, H-164/H-165/H-166 backtests
- Done: 19/19 runners OK. **Demo**: $99,124 (-0.88%, improved from -1.98%). BTC $68,179. **13/19 positive**, 6 negative. Top: H-031(+5.34%), H-039(+4.35%), H-012(+2.74%), H-019(+2.26%), H-063(+1.81%). **H-063 improving**: $10,181 (+1.81%, was +1.10%), PUT ITM by only $952 (shrinking), $1,181 buffer to stop, 2.5d to expiry — on track for profitable first trade. **Research**: **H-164 REJECTED** (co-momentum — 14.8% IS positive, peer-weighted momentum has no signal in crypto). **H-165 REJECTED** (funding-premium interaction — 25.0% IS positive, joint crowding signal too noisy). **H-166 REJECTED** (return persistence — 90% IS, WF **6/6** mean 2.263, excellent standalone BUT **corr 0.503 with H-160** — redundant with trend-quality factor).
- Next: Mar 31 bar (00:30 UTC Apr 1): H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG + H-160. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 120)

### Session 2026-04-01 review+research (session 121)
- Goal: Review + Research — MTM update, rebalance verification, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $68,293, +0.17%), H-063 approaching expiry, H-167/H-168/H-169 backtests
- Done: 19/19 runners OK. **Demo**: $99,552 (-0.45%, improved from -0.88%). BTC $68,293. **12/19 positive** (H-059 flipped negative), 7 negative. Top: H-031(+5.01%), H-039(+4.31%), H-063(+3.36%), H-019(+2.56%). **H-063 best yet**: $10,336 (+3.36%), PUT ITM by only $708, $1,336 buffer, 2.3d to expiry. **Mar 31 rebalances confirmed**: H-012 (LONG NEAR/AVAX/BTC/ATOM, SHORT SOL/SUI/ARB/OP), H-046 (LONG OP/ATOM/ARB/DOGE, SHORT SUI/AVAX/DOT/NEAR), H-062 (unchanged). **Research**: **H-167 CONFIRMED** (vol-price confirmation — 90% IS, WF 5/6 mean 1.145, split-half both positive, max corr 0.251. Caveat: H2=0.088 weak). **H-168 REJECTED** (return autocorrelation — 25% IS positive, no XS signal). **H-169 CONFIRMED** (beta-adjusted momentum/alpha — 100% IS, WF 4/6 mean 1.648, corr 0.342 with H-012. Strongest new factor).
- Next: Apr 1 bar (00:30 UTC Apr 2): H-085 rebal. Apr 2: H-039 LONG + H-160. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 121)

### Session 2026-04-01 review+research (session 122)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $68,217, -0.11%), H-063 pulled back, H-170/H-171/H-172 backtests
- Done: 19/19 runners OK. **Demo**: $99,330 (-0.67%, down from -0.45%). BTC $68,217. **12/19 positive**, 7 negative (unchanged). Top: H-031(+5.01%), H-039(+4.31%), H-019(+2.56%), H-012(+2.30%), H-063(+2.22%). **H-063 pulled back**: $10,222 (+2.22%, was +3.36%), PUT ITM by ~$783, $1,222 buffer to stop, 2.1d to expiry — theta still working, on track. **Research**: **H-170 REJECTED** (return kurtosis — IS 93.3% excellent, best Sharpe 1.32, BUT WF **2/6** positive, mean -0.46. Split-half H1=0.16/H2=1.49 = severe recency bias. Low corr to all factors (-0.09 to -0.21) confirms novelty but signal not stable). **H-171 REJECTED** (funding rate momentum — contrarian 68.8% IS (below 80%), WF 5/6 but split-half fails. Corr **0.405** with H-053 = redundant with funding level. Reconfirms H-130 rejection). **H-172 REJECTED** (Hurst exponent R/S — trending_long 43.3% IS, meanrev_long 33.3%. No XS signal. Joins autocorrelation + variance ratio as third persistence measure to fail in crypto).
- Next: Apr 1 bar (00:30 UTC Apr 2): H-085 rebal. Apr 2: H-039 LONG + H-160. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 122)

### Session 2026-04-01 review+research+deploy (session 123)
- Goal: Review + Research + Deploy — MTM update, H-169 deploy, H-175 confirm+deploy, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $68,720, +0.74%), H-063 improving, H-169/H-175 deployment, H-173/H-174/H-175 backtests
- Done: 19/19 runners OK (pre-deploy). **Demo**: $99,178 (-0.82%). BTC $68,720. **12/19 positive**, 7 negative. **H-063 improving**: $10,276 (+2.76%, was +2.22%), PUT ITM by only ~$280 (shrinking), 1.9d to expiry. **H-169 deployed** as paper trade #20: LONG DOGE/LINK/ETH/AVAX, SHORT ATOM/NEAR/OP/DOT. **Research**: **H-173 REJECTED** (GK vol ratio — 53.3% IS = noise. Intraday vol structure doesn't discriminate XS). **H-174 REJECTED** (downside beta — 60.0% IS. Asymmetric beta not stable). **H-175 CONFIRMED** (net money flow — **100% IS** (30/30), mean Sharpe **1.005**, WF **4/6** mean 1.051, split-half H1=1.618/H2=0.226, max corr 0.299 with H-160). **H-175 deployed** as paper trade #21: LONG DOGE/ARB/NEAR/ADA, SHORT ETH/BTC/ATOM/OP.
- Next: Apr 1 bar (00:30 UTC Apr 2): H-085. Apr 2: H-160. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076. Apr 5: H-169. Apr 7: H-175.
- Questions added: none
- Self-modifications: H-169 runner created, H-175 runner created, both added to orchestrator (session 123)
