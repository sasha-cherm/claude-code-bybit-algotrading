# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$98,736 (-1.26%). BTC bar $66,903 (Apr 2). Apr 3 bar in progress (~$66,849).
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **H-011 status**: DROPPED from demo. Internal paper trade IN. Capital $9,867 (-1.33%). 56 settlements.
- **Internal paper trades:** 28 runners active. Session 138. **13/28 positive** (up from 10/28).
- **H-063 FLAT**: First trade +0.78%. Waiting next entry. **H-039 FLAT**: +5.79%, next LONG Wed Apr 8.
- **Top performers**: H-039(+5.79%), H-031(+4.74%), H-012(+3.50%), H-019(+2.34%), H-062(+1.56%). Several new strats turned positive: H-182(+1.00%), H-175(+0.57%), H-193(+0.42%), H-169(+0.25%).
- **Research**: 220 total hypotheses. **H-219 CONFIRMED** (Up-Volume Ratio). H-218/H-220 REJECTED.
- **AUTOMATED:** Paper trades hourly via cron (28 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Deploy H-219 paper trade. Apr 4 bar close triggers rebalances. Continue research.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 128) archived to `memory/session_archive.md`._

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
- Done: 27 runners checked (26->27 post-deploy). **Demo**: $98,564 (-1.41%). BTC spot $66,954. **13/27 positive**, 14 negative. Top: H-031(+4.72%), H-039(+3.98%), H-019(+2.63%), H-012(+1.88%), H-169(+1.82%). **H-063 still profitable**: +0.24%, BTC $66,875, PUT ITM by ~$2,068 but premium covering. 11h to expiry — on track for profitable close. **H-197 deployed** as paper trade #27. **Research**: **H-200 REJECTED** (return autocorrelation). **H-201 REJECTED** (volume imbalance). **H-202 REJECTED** (intraday vol HHI — split-half fails). 202 total hypotheses.
- Self-modifications: H-197 runner created (session 132)

### Session 2026-04-03 review+research (session 133)
- Goal: Review + Research — MTM update, H-063 pre-expiry check, 3 new factor backtests
- Done: 27 runners. **Demo**: $98,604 (-1.40%). BTC $66,903. **13/27 positive**. H-063 breakeven (+$1, 7h to expiry). H-182 surged to +1.00%. **Research**: H-203/H-204/H-205 all REJECTED. 205 total hypotheses.
- Self-modifications: none (session 133)

### Session 2026-04-03 review+research (session 134)
- Goal: Review + Research — MTM update, H-063 pre-expiry, 3 new factor backtests
- Done: 27 runners. **Demo**: $97,996 (-2.00%). BTC dropping. H-063 at -0.52%, 3h to expiry. H-021 rebalanced Apr 2. **Research**: H-206 REJECTED (Hurst — split-half fails). H-207 REJECTED (OI growth). H-208 REJECTED (reversal). H-116 resolved REJECTED. 208 total hypotheses.
- Self-modifications: H-116 resolved (session 134)

### Session 2026-04-03 review+research (session 135)
- Goal: Review + Research — MTM update, H-063 settlement confirmation, 3 new factor backtests
- Focus: Paper trade MTM (BTC $66,931), H-063 expiry settlement, H-209/H-210/H-211 backtests
- Done: 27 runners checked. **Demo**: $97,730 (-2.27%). BTC $66,931. **10/27 positive**, 16 negative, 1 flat. Top: H-039(+5.79%), H-031(+4.12%), H-012(+2.22%), H-053(+1.39%), H-046(+1.26%). **H-063 SETTLED PROFITABLY**: Trade 1 expired 08:35 UTC — BTC $67,060, call OTM, put ITM $272 payoff but premium $364 → **net +$77.64 (+0.78%)**. Now FLAT. **Research**: **H-209 REJECTED** (price-volume correlation — IS 58.3% in dominant dir, no robust signal). **H-210 REJECTED** (RSI dispersion — IS 83.3% but WF **3/6** fails, signal deteriorating). **H-211 REJECTED** (market coupling R² — IS ~50%, no XS predictive power). 211 total hypotheses.
- Next: Apr 4: H-039(exit SHORT), H-049/H-052/H-076/H-012/H-021/H-197 rebalances. Continue research.
- Questions added: none
- Self-modifications: Archived sessions 125-126 (session 135)

### Session 2026-04-03 review+research (session 136)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (BTC $66,673), H-212/H-213/H-214 backtests
- Done: 27 runners checked. **Demo**: $97,833 (-2.17%). BTC $66,673. **12/27 positive** (improved from 10). Top: H-039(+5.79%), H-031(+4.74%), H-012(+3.50%), H-019(+2.34%), H-062(+1.56%). **Improving**: H-012 surged +3.50% (was +2.22%), H-062 +1.56% (was +0.88%), H-182 +1.00% (was -0.20%), H-193 turned positive +0.42%. **Worsening**: H-189 -1.47% (was -0.20%). **Research**: **H-212 REJECTED** (volume rank persistence — IS 43.3%, signal too parameter-sensitive). **H-213 REJECTED** (CLV persistence — IS 66.7%, short lookbacks noise). **H-214 REJECTED** (CVaR tail risk — IS 100% pass but corr 0.649 with H-019, too redundant with low-vol). 214 total hypotheses.
- Next: Apr 4: H-039(exit SHORT), H-049/H-052/H-076/H-012/H-021/H-197 rebalances. Continue research.
- Questions added: none
- Self-modifications: none (session 136)

### Session 2026-04-03 review+research+deploy (session 137)
- Goal: Review + Research + Deploy — MTM update, H-215 deployment, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar since Apr 2), H-215/H-216/H-217 backtests
- Done: 28 runners checked (27→28 post-deploy). No new daily bar — MTM unchanged from session 136. H-011 $9,867 (-1.33%, 56 settlements). H-039 FLAT +5.79%. **Research**: **H-215 CONFIRMED** (Dollar Volume Trend — IS **94.4%**, WF **4/6** mean 0.016, split-half H1=2.388/H2=1.565, corr **0.148** H-012. Best LB15_R3_N4 Sharpe 1.668. Novel flow-of-funds signal). **H-216 REJECTED** (Kurtosis — IS 40% < 80%, low-kurt-long 76.7% but crypto too uniformly fat-tailed). **H-217 REJECTED** (Volume/OI Ratio — IS 48.3%, high-VOI-long 96.7% but combined fails. Interesting one-directional signal). **H-215 deployed** as paper trade #28: LONG SOL/DOGE/OP/SUI, SHORT DOT/LINK/NEAR/ATOM. 217 total hypotheses.
- Next: Apr 4: H-049/H-052/H-076/H-012/H-021/H-197 rebalances. Continue research.
- Questions added: none
- Self-modifications: H-215 runner created, added to orchestrator (session 137)

### Session 2026-04-03 review+research (session 138)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (BTC bar $66,903, Apr 3 bar in progress ~$66,849), H-218/H-219/H-220 backtests
- Done: 28 runners checked. **Demo**: $98,736 (-1.26%, improved from -2.17%). **13/28 positive** (up from 10). Top: H-039(+5.79%), H-031(+4.74%), H-012(+3.50%), H-019(+2.34%), H-062(+1.56%). Improved: H-182 surged +1.00%, H-175 +0.57%, H-193 +0.42%, H-169 +0.25%. H-049 rebalanced (new: LONG ADA/AVAX, SHORT ARB). H-021 still worst -3.71%. **Research**: **H-218 REJECTED** (Rolling Beta Change — IS 53.7% in best direction < 80%, beta dynamics too noisy in 14-coin universe). **H-219 CONFIRMED** (Up-Volume Ratio — IS **80.0%** upvol_long, WF **4/6** mean 0.204, split-half H1=1.266/H2=2.097, corr **0.157** H-012. Novel volume composition signal). **H-220 REJECTED** (Short-Term Reversal — IS 37.5% reversal dir, crypto too momentum-driven even at 1-5 day horizon). 220 total hypotheses.
- Next: Deploy H-219 paper trade. Apr 4 bar close triggers multiple rebalances. Continue research.
- Questions added: none
- Self-modifications: none (session 138)
