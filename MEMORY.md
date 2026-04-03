# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity $97,730 (-2.27%). BTC spot ~$66,931.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x). No H-011, H-009, H-046.
- **H-011 status**: DROPPED from demo. Internal paper trade IN. Capital $9,866 (-1.34%).
- **Internal paper trades:** 27 runners active. Session 135. BTC last bar $66,903 (Apr 2), spot ~$66,931.
- **H-063 SETTLED**: First vol selling trade **profitable** — +$77.64 (+0.78%). Now FLAT, waiting next entry.
- **Top performers**: H-039 (+5.79%), H-031 (+4.12%), H-012 (+2.22%), H-053 (+1.39%), H-046 (+1.26%). **10/27 positive**, 16 negative, 1 flat.
- **Research**: 211 total hypotheses. H-209/H-210/H-211 all REJECTED. No new confirms.
- **AUTOMATED:** Paper trades hourly via cron (27 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Apr 4: H-039(exit SHORT), multiple rebalances. Continue research.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 126) archived to `memory/session_archive.md`._

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
