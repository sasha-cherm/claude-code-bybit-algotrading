# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity $97,996 (-2.00%). BTC spot ~$66,523.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x). No H-011, H-009, H-046.
- **H-011 status**: DROPPED from demo. Internal paper trade IN. Capital $9,867 (-1.33%).
- **Internal paper trades:** 27 runners active. Session 134. BTC last bar $66,903 (Apr 2), spot ~$66,523.
- **Top performers**: H-039 (+5.79%), H-031 (+4.68%), H-019 (+2.33%), H-012 (+2.18%), H-062 (+1.54%). **13/27 positive**, 14 negative.
- **H-063 status**: Vol selling strangle — $9,948 (-0.52%), 3h to expiry (Apr 3 08:00). PUT deep ITM ~$2,400. First trade = small loss.
- **Research**: 208 total hypotheses. H-206/H-207/H-208 all REJECTED. H-116 resolved to REJECTED.
- **AUTOMATED:** Paper trades hourly via cron (27 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Apr 3 08:00: H-063 expiry settlement (auto). Continue research.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 124) archived to `memory/session_archive.md`._

### Session 2026-04-01 review+research (session 125)
- Goal: Review + Research — MTM update, demo check, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $69,164, +1.26% from last session), demo nearly breakeven, H-179/H-180/H-181 backtests
- Done: 21 runners checked. **Demo**: $99,896 (-0.10%, recovered from -1.80%). BTC $69,164. **14/21 positive**, 5 negative, 2 flat. Top: H-031(+5.17%), H-039(+4.31%), H-063(~+3.69%), H-019(+2.10%), H-049(+1.67%). **H-063 both options OTM!** BTC $69,164 > put $69,000. ~$1,369 buffer, 1.5d to expiry — strong position. **H-169 strong day 1**: +1.53%. **H-175 day 1**: +0.81%. **H-059 recovered**: +1.02% (was -1.05%). **H-160 recovered**: +0.53% (was -1.23%). **Research**: **H-179 REJECTED** (OI share change — shrinking_long 63.3% IS, contrarian OI signal exists but too parameter-sensitive). **H-180 REJECTED** (multi-TF agreement — IS 100% but WF 1/4 and corr 0.69 with H-012, just a momentum proxy). **H-181 REJECTED** (volume CV — erratic_long 66.7% IS, counterintuitive direction but not robust). 181 total hypotheses.
- Next: Apr 1 bar (00:30 UTC Apr 2): H-085. Apr 2: H-039 LONG + H-160. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076. Apr 5: H-169. Apr 7: H-175.
- Questions added: none
- Self-modifications: none (session 125)

### Session 2026-04-01 review+research (session 126)
- Goal: Review + Research — MTM update, H-063 pre-expiry monitoring, demo check, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $68,340, -1.2% from last session), demo down, H-182/H-183/H-184 backtests
- Done: 21 runners checked. **Demo**: $98,471 (-1.53%, down from -0.10%). BTC $68,340. **12/21 positive**, 9 negative. Top: H-031(+5.01%), H-039(+4.31%), H-063(+2.87%), H-019(+2.56%), H-012(+2.30%). **H-063 pre-expiry**: +2.87%, PUT ITM by $660 but liability only $172 (theta decay), $1,287 buffer, 1.4d to expiry — on track. **Notable moves**: H-046 recovered +1.23% (from -0.47%), H-076 +1.07% (from -0.46%). H-049 dropped to +0.02% (from +1.67%). H-059 flipped to -1.05%. **Research**: **H-182 CONFIRMED** (High-Low Range — narrow_long 90% IS, WF **5/6** mean 1.506, split-half both positive, corr **0.200** with H-012. Genuinely novel). **H-183 CONFIRMED** (Gap/Overnight Sentiment — neg_gap_long **100% IS**, WF **5/6** mean 1.771, split-half both strong, corr 0.468 with H-012. Borderline but passes). **H-184 REJECTED** (VW momentum — 83% IS passes but WF **3/6** fails. Signal emerged recently, recency bias). 184 total hypotheses. Two confirms ready for deployment.
- Next: Apr 1 bar (00:30 UTC Apr 2): H-085 rebal, H-039 LONG. Apr 2: H-160. Apr 3: H-063 expiry + H-031. Deploy H-182/H-183 paper trades.
- Questions added: none
- Self-modifications: none (session 126)

### Session 2026-04-02 review+research+deploy (session 127)
- Goal: Review + Research + Deploy — MTM update, H-182/H-183 deployment, 3 new factor backtests
- Focus: Paper trade monitoring (BTC ~$68,170, -0.25%), H-063 pre-expiry, H-182/H-183 deployment, H-185/H-186/H-187 backtests
- Done: 23 runners checked (21 pre-deploy). **Demo**: $98,182 (-1.82%). BTC $68,170. **13/21 positive** (improved from 12). Top: H-031(+4.37%), H-039(+3.98%), H-019(+2.81%), H-012(+2.47%), H-063(+2.25%). **H-063**: +2.25%, PUT ITM by ~$830, liability ~$200, 1.3d to expiry — on track. **H-169 surged**: +1.27% (from -0.24%). **H-175**: +0.98% (from -0.24%). **H-053 dropped**: -1.48% (from +0.78%). **H-085 rebalanced**: LONG BTC/NEAR/SOL/SUI, SHORT XRP/DOGE/DOT/LINK. **H-039**: Wed LONG -$29, now SHORT Thu @ $68,119. **H-182 deployed** as paper trade #22: LONG BTC/ATOM/XRP, SHORT OP/SUI/NEAR. **H-183 deployed** as paper trade #23: LONG BTC/ETH/SOL/SUI, SHORT NEAR/OP/ARB/ATOM. Both added to orchestrator (23 total). **Research**: **H-185 REJECTED** (skewness — IS 66.7% < 80%, opposite of equity lottery effect). **H-186 REJECTED** (CLV — IS 56.7%, no intraday positioning signal). **H-187 REJECTED** (rolling Sharpe — IS 93.3% but WF 3/5, unstable risk-adjusted momentum). 187 total hypotheses.
- Next: Apr 2: H-160 rebal. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076. Continue research.
- Questions added: none
- Self-modifications: H-182/H-183 runners created, added to orchestrator (session 127)

### Session 2026-04-02 review+research (session 128)
- Goal: Review + Research — MTM update, H-063 pre-expiry monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC ~$66,350, -2.7% from last session), H-063 crashed, H-188/H-189/H-190 backtests
- Done: 23 runners checked. **Demo**: $98,434 (-1.57%, improved from -1.82% despite BTC drop). BTC $66,350. **12/23 positive**, 11 negative. Top: H-031(+4.69%), H-039(+3.98%), H-012(+2.62%), H-019(+2.58%), H-169(+1.70%). **H-063 crashed**: -1.31% (was +2.25%) — BTC fell to $66,349, PUT deep ITM by $2,651, $869 buffer above stop, 1.1d to expiry. First trade likely a loss. **H-009 recovering**: -1.14% (from -2.10%), SHORT gaining on BTC drop. **H-032 first trades**: 3 active pairs. **H-169/H-175 day 3**: +1.70%/+1.16%, both strengthening. **Research**: **H-188 REJECTED** (return-volume asymmetry — IS 83.3% but WF 0/3, complete OOS failure). **H-189 CONFIRMED** (funding rate dispersion — IS 91.7%, WF 4/6 mean 1.014, split-half H1=2.124/H2=1.568, **corr 0.033** — essentially uncorrelated with everything. Genuinely novel signal). **H-190 REJECTED** (range position — IS 86.7% but WF 2/3, insufficient valid folds). 190 total hypotheses.
- Next: Apr 3: H-063 expiry settlement + H-031 rebal. Consider deploying H-189 paper trade. Continue research.
- Questions added: none
- Self-modifications: none (session 128)

### Session 2026-04-02 review+research+deploy (session 129)
- Goal: Review + Research + Deploy — MTM update, H-189 deployment, 3 new factor backtests
- Focus: Paper trade monitoring (BTC ~$68,119, no new bar), H-189 deployment, H-191/H-192/H-193 backtests
- Done: 24 runners checked (23 pre-deploy). No new daily bar = MTM unchanged from session 128. **H-189 deployed** as paper trade #24: LONG BTC/ETH/LINK, SHORT ATOM/DOT/OP. Added to orchestrator (24 total). **Research**: **H-191 CONFIRMED** (volume-price elasticity — IS 80%, WF **4/5** mean **1.728**, split-half H1=1.650/H2=2.404, corr 0.353 H-012. Novel microstructure signal). **H-192 REJECTED** (intraday dispersion — IS 86.7% but WF **2/6** mean -1.328. Overfit short lookback). **H-193 CONFIRMED** (OI-price momentum divergence — IS 86.7%, WF **4/5** mean **1.470**, split-half H1=2.196/H2=2.001, corr 0.380 H-012. Captures positioning quality). 193 total hypotheses.
- Next: Apr 3: H-063 expiry + H-031 rebal. Deploy H-191/H-193 paper trades. Continue research.
- Questions added: none
- Self-modifications: H-189 runner created, added to orchestrator (session 129)

### Session 2026-04-02 review+research+deploy (session 130)
- Goal: Review + Research + Deploy — MTM update, H-191/H-193 deployment, 3 new factor backtests
- Focus: Paper trade monitoring (BTC spot ~$66,100, last bar $68,119), H-063 worsening, H-191/H-193 deployment, H-194/H-195/H-196 backtests
- Done: 26 runners checked (24 pre-deploy). **Demo**: $98,577 (-1.42%, improved from -1.57%). BTC spot dropped to ~$66,100 but no new daily bar yet. **H-063 worsened**: $9,774 (-2.26%, was -1.28%), PUT deep ITM by ~$3,000, 0.8d to expiry, $774 buffer to stop — first trade will be a loss. **H-191 deployed** as paper trade #25: LONG BTC/ETH/XRP/AVAX, SHORT NEAR/OP/SUI/ARB. **H-193 deployed** as paper trade #26: LONG XRP/OP/ARB, SHORT AVAX/ADA/LINK. Both added to orchestrator (26 total). **Research**: **H-194 REJECTED** (realized vol ratio — IS 94% but WF **0/6** positive, mean -1.168. Complete OOS failure). **H-195 REJECTED** (funding rate reversal — IS 38% = noise. Third funding momentum variant to fail). **H-196 REJECTED** (dollar vol acceleration — IS 85% but WF 2/4, corr **0.763** with H-021. Redundant with volume momentum). 196 total hypotheses.
- Next: Apr 3: H-063 expiry settlement + H-031 rebal. Apr 4: H-021/H-049/H-052/H-076. Continue research.
- Questions added: none
- Self-modifications: H-191/H-193 runners created, added to orchestrator (session 130)

### Session 2026-04-02 review+research (session 131)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC spot ~$66,895, last bar $68,119), H-063 recovery, H-197/H-198/H-199 backtests
- Done: 26 runners checked. **Demo**: $98,428 (-1.57%). BTC spot $66,895, no new daily bar. **13/26 positive**, 8 negative, 5 flat (day 0). Top: H-031(+4.69%), H-039(+3.98%), H-012(+2.62%), H-019(+2.58%), H-169(+1.70%). **H-063 RECOVERED**: +1.20% (was -2.26%), BTC bounced to $67,265, 0.6d to expiry, liability only $253, buffer $1,120 — could close in profit. **H-021 worst**: -4.23% (sharp Apr 1 drop). **H-169/H-175 strong**: +1.70%/+1.16% (day 2). **Research**: **H-197 CONFIRMED** (Amihud illiquidity — **100% IS** (30/30), mean Sharpe 1.537, best LB10_R3_N4 Sharpe 1.895. WF **5/6** mean **1.387**. Split-half H1=1.911/H2=2.290. Corr 0.488 H-012. Long liquid, short illiquid — flight-to-liquidity factor). **H-198 REJECTED** (price-MA distance — mean reversion 10% IS, momentum 66.7% IS < 80%. Mean reversion decisively wrong in crypto). **H-199 REJECTED** (consecutive streaks — 50% IS, raw streaks marginally work but smoothing destroys signal, too parameter-sensitive). 199 total hypotheses.
- Next: Apr 3: H-063 expiry settlement + H-031 rebal. Deploy H-197 paper trade. Continue research.
- Questions added: none
- Self-modifications: Archived sessions 121-122 (session 131)

### Session 2026-04-03 review+deploy+research (session 132)
- Goal: Review + Deploy + Research — MTM update, H-197 deploy, 3 new factor backtests
- Focus: Paper trade monitoring (BTC spot ~$66,954, last bar $68,119), H-063 pre-expiry, H-197 deployment, H-200/H-201/H-202 backtests
- Done: 27 runners checked (26→27 post-deploy). **Demo**: $98,564 (-1.41%). BTC spot $66,954. **13/27 positive**, 14 negative. Top: H-031(+4.72%), H-039(+3.98%), H-019(+2.63%), H-012(+1.88%), H-169(+1.82%). **H-063 still profitable**: +0.24%, BTC $66,875, PUT ITM by ~$2,068 but premium covering. 11h to expiry — on track for profitable close. **H-197 deployed** as paper trade #27: LONG BTC/ETH/SOL/XRP, SHORT LINK/OP/ARB/ATOM. Added to orchestrator (27 total). **Research**: **H-200 REJECTED** (return autocorrelation — IS 27.8% < 80%. Only works at LB=60, too parameter-sensitive). **H-201 REJECTED** (volume imbalance / buy-sell pressure — IS 44.4% < 80%. Weak XS differentiation). **H-202 REJECTED** (intraday vol clustering HHI — IS 100%, WF 5/6, but split-half FAILS: H1=3.53/H2=-0.19. Signal temporally unstable). 202 total hypotheses.
- Next: Apr 3 08:00 UTC: H-063 expiry settlement (auto). Continue research.
- Questions added: none
- Self-modifications: H-197 runner created, added to orchestrator (session 132)

### Session 2026-04-03 review+research (session 133)
- Goal: Review + Research — MTM update, H-063 pre-expiry check, 3 new factor backtests
- Focus: Paper trade monitoring (BTC spot ~$66,903, last bar $68,119), H-203/H-204/H-205 backtests
- Done: 27 runners checked. **Demo**: $98,604 (-1.40%). BTC $66,903. **13/27 positive**, 14 negative. Top: H-039(+5.79%), H-031(+4.68%), H-019(+2.33%), H-012(+2.18%), H-062(+1.54%). **H-063 breakeven** (+$1, 7h to expiry). **H-182 surged** from -0.24% to +1.00% (range factor working). **H-169 dropped** from +1.82% to +0.28%. **Research**: **H-203 REJECTED** (kurtosis — IS 69.4% < 80%, signal exists at medium lookbacks but too noisy at LB10). **H-204 REJECTED** (idiosyncratic vol — IS 61.1% < 80%, low-ivol outperformance too lookback-dependent). **H-205 REJECTED** (up/down volume ratio — IS 83.3%, WF 5/6, split-half passes, but **corr 0.583** with H-012 momentum — too redundant). 205 total hypotheses.
- Next: Apr 3 08:00: H-063 expiry settlement (auto). Apr 4: H-021/H-049/H-052/H-076/H-039(exit SHORT). Continue research.
- Questions added: none
- Self-modifications: none (session 133)

### Session 2026-04-03 review+research (session 134)
- Goal: Review + Research — MTM update, H-063 pre-expiry, 3 new factor backtests
- Focus: Paper trade monitoring (BTC spot ~$66,523, Apr 2 bar $66,903), H-206/H-207/H-208 backtests
- Done: 27 runners checked. **Demo**: $97,996 (-2.00%, down from -1.40%). BTC dropping. **13/27 positive**, 14 negative. Top: H-039(+5.79%), H-031(+4.68%), H-019(+2.33%), H-012(+2.18%), H-062(+1.54%). **H-063 at -0.52%**: PUT deep ITM ~$2,400, equity $9,948, 3h to expiry — first trade will be small loss. **H-021 rebalanced** Apr 2 to LONG SUI/NEAR/OP/SOL, SHORT XRP/ETH/ATOM/DOT. **H-160 rebalanced** Apr 2. **Research**: **H-206 REJECTED** (Hurst R/S — implementation bug: LB≤40 defaults all values to 0.5 creating disguised size factor. At LB=60 where real Hurst is computed: 6/6 IS combos positive, WF 5/6, but split-half FAILS H2=-0.324. Signal too unstable). **H-207 REJECTED** (OI growth rate — 50% IS = noise, confirms H-043). **H-208 REJECTED** (short-term reversal — 26.6% IS, confirms H-109). H-116 resolved from CONDITIONAL to REJECTED. 208 total hypotheses.
- Next: Apr 3 08:00: H-063 expiry settlement (auto). Apr 4: H-039 exit SHORT, H-012/H-049/H-052/H-076 rebal. Continue research.
- Questions added: none
- Self-modifications: H-116 status resolved to REJECTED (session 134)
