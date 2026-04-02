# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity $98,577 (-1.42%). BTC spot ~$66,100.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x). No H-011, H-009, H-046.
- **H-011 status**: DROPPED from demo. Internal paper trade IN. Capital $9,869 (-1.31%).
- **Internal paper trades:** 26 runners active. Session 130. BTC last bar $68,119 (no new bar since Apr 1), spot ~$66,100.
- **Top performers**: H-031 (+4.69%), H-039 (+3.98%), H-012 (+2.62%), H-019 (+2.58%), H-169 (+1.70%). **12/26 positive**, 14 negative.
- **H-063 status**: Vol selling strangle — **-2.26%**. PUT deep ITM by ~$3,000. 0.8d to expiry (Apr 3 08:00 UTC). $774 buffer above stop. First trade loss.
- **H-191/H-193 DEPLOYED**: Vol-price elasticity + OI-price divergence. Paper trades #25-26.
- **Research**: 196 total hypotheses. H-194/H-195/H-196 all REJECTED this session.
- **AUTOMATED:** Paper trades hourly via cron (26 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Apr 3: H-063 expiry settlement + H-031 rebal. Continue research.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 120) archived to `memory/session_archive.md`._

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

### Session 2026-04-01 review+research (session 124)
- Goal: Review + Research — MTM update, H-024 orchestrator cleanup, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $68,306, -0.61% from last session), H-176/H-177/H-178 backtests
- Done: 21 runners checked. **Demo**: $98,201 (-1.80%, down from -0.82%). BTC $68,306. **12/21 positive** (excl flat). Top: H-039(+4.31%), H-031(+3.89%), H-019(+2.23%), H-012(+2.08%), H-076(+1.73%). **H-063**: +2.74%, PUT ITM ~$280, 1.7d to expiry — approaching Apr 3 expiry. **H-175 strong start**: +1.34% day 0. **H-169**: +0.22% day 0. **H-024 orchestrator cleanup**: comment residue removed (was already commented out session 114). **Research**: **H-176 REJECTED** (momentum-reversal timing — 33.3% IS, dip-buying signal too fragile). **H-177 REJECTED** (volume trend slope — 70.0% IS, close but below 80%, volume trends too noisy at daily freq). **H-178 REJECTED** (correlation regime change — 46.3% IS, herding/decorrelation signal too parameter-sensitive). 178 total hypotheses.
- Next: Apr 1 bar (00:30 UTC Apr 2): H-085. Apr 2: H-039 LONG + H-160. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076. Apr 5: H-169. Apr 7: H-175.
- Questions added: none
- Self-modifications: H-024 comment cleaned from orchestrator (session 124)

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
