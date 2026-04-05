# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$100,649 (+0.65%). BTC spot ~$67,239.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **H-011 status**: DROPPED from demo. Internal paper trade IN. Capital $9,871 (-1.29%).
- **Internal paper trades:** 34 runners active. Session 149. **10/34 positive**.
- **H-063 IN TRADE 2**: MTM +1.39% ($190 premium, expires Apr 10). **H-039 FLAT**: +5.79%, next LONG Wed Apr 9.
- **Top performers**: H-039(+5.79%), H-076(+4.07%), H-031(+3.93%), H-012(+2.22%), H-052(+1.92%).
- **Research**: 256 total hypotheses. H-254/H-256 REJECTED, H-255 CONFIRMED+deployed.
- **AUTOMATED:** Paper trades hourly via cron (34 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Continue research. Monitor H-021 (-3.63%) and H-009/H-160.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 139) archived to `memory/session_archive.md`._

### Session 2026-04-04 review+deploy+research (session 140)
- Goal: Review + Deploy + Research — MTM update, H-223 deployment, H-224/H-225/H-226 backtests
- Focus: Paper trade MTM (no new daily bar, still Apr 3), H-223 deployment, 3 new factor backtests
- Done: 30 runners checked (29→30 post-deploy). **Demo**: $98,827 (-1.17%). **14/30 positive**. Top: H-039(+5.79%), H-031(+3.89%), H-012(+3.87%), H-076(+3.21%), H-175(+1.91%). H-012 surged to +3.87% (was +3.21%). H-189 improving -2.94% (was -3.03%). **H-223 deployed** as paper trade #30: LONG ETH/DOGE/LINK, SHORT OP/ATOM/NEAR. Added to orchestrator. **Research**: **H-224 REJECTED** (ADX trend strength — IS dom dir 95.8% but WF 3/5, doesn't generalize OOS). **H-225 REJECTED** (VPT — IS dom dir 100%, WF 4/6, but corr 0.654 with H-012, too similar to momentum). **H-226 REJECTED** (Ease of Movement — IS 43.3%, dom dir 76.7% < 80%, weak signal in 24/7 crypto). 226 total hypotheses.
- Next: Continue research. Monitor H-189 (-2.94%) and H-160 (-2.19%).
- Questions added: none
- Self-modifications: H-223 runner created, added to orchestrator. Archived session 131. (session 140)

### Session 2026-04-04 review+research (session 141)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, still Apr 3), H-227/H-228/H-229 backtests
- Done: 30 runners checked. **Demo**: $98,650 (-1.35%). BTC $66,965. **14/30 positive**. Top: H-039(+5.79%), H-031(+3.90%), H-012(+3.21%), H-076(+3.20%), H-175(+1.82%). H-009 recovering -0.51% (SHORT gaining). H-189 worst at -3.03%. **Research**: **H-227 REJECTED** (RS vs BTC — IS dom dir 91.7% but WF 1/3 and corr **0.923** with H-012, essentially momentum). **H-228 REJECTED** (CLV persistence — IS 40%, dom dir 70% < 80%). **H-229 REJECTED** (volume autocorrelation — IS 41.7%, dom dir 52.8%, no XS predictive power). 229 total hypotheses.
- Next: Continue research. Monitor H-189 (-3.03%) and H-160 (-2.25%).
- Questions added: none
- Self-modifications: Archived session 132. (session 141)

### Session 2026-04-04 review+research (session 142)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$67,099), H-230/H-231/H-232 backtests
- Done: 30 runners checked. **Demo**: $98,745 (-1.26%, improving). BTC ~$67,099. **14/30 positive**. Top: H-039(+5.79%), H-031(+3.90%), H-012(+3.21%), H-076(+3.20%), H-175(+1.82%). **H-063 entered trade 2** — strangle active, MTM +1.06%, 5.8d remaining. **Research**: **H-230 REJECTED** (return autocorrelation — IS **16.7%**, mean Sharpe -0.889, no XS predictive power). **H-231 REJECTED** (CLR close location in range — IS 73.3%, best Sharpe 1.55 but short lookbacks all negative, parameter-sensitive). **H-232 REJECTED** (Parkinson range ratio — IS **0%**, mean Sharpe -0.647, all crypto assets have similarly high intraday noise). 232 total hypotheses.
- Next: Continue research. Monitor H-189 (-3.03%) and H-160 (-2.25%).
- Questions added: none
- Self-modifications: none (session 142)

### Session 2026-04-04 review+research (session 143)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (BTC ~$67,299 live, bar $66,933), H-233/H-234/H-235 backtests
- Done: 30 runners checked. **Demo**: $98,905 (-1.10%, improving). **14/30 positive**. Top: H-039(+5.79%), H-031(+3.90%), H-012(+3.21%), H-076(+3.20%), H-175(+1.82%). No new daily bar (still Apr 3). **Research**: **H-233 REJECTED** (relative volume — IS **0%**, 0/144, mean Sharpe -1.502, volume ratio has zero XS predictive power). **H-234 REJECTED** (consecutive return direction — IS 15%, low_long 30%, similar to H-223 but broader param space fails). **H-235 REJECTED** (funding rate change/delta — IS 38.9%, low_long 77.8% close to 80% but not passing, funding level H-053 works better than funding change). 235 total hypotheses.
- Next: Continue research. Monitor H-189 (-3.03%) and H-160 (-2.25%).
- Questions added: none
- Self-modifications: Archived session 133. (session 143)

### Session 2026-04-04 review+research (session 144)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (BTC ~$67,278, no new daily bar), H-236/H-237/H-238 backtests
- Done: 30 runners checked. **Demo**: $99,094 (-0.91%, improving). **14/30 positive**. Top: H-039(+5.79%), H-031(+3.89%), H-012(+3.87%), H-076(+3.21%), H-175(+1.91%). H-012 surged to +3.87% (was +3.21%). H-044 nearly flat at -0.08%. **Research**: **H-236 REJECTED** (co-skewness — IS 35.4%, no directional dominance, all crypto crashes together). **H-237 REJECTED** (volume concentration HHI — IS 38.5%, dom 52.1%, some strong individual params but not robust). **H-238 CONFIRMED** (downside beta — IS **100%** low_long, WF **4/6** mean 2.612, Sharpe 1.766, but corr **0.738** with regular beta, **0.512** with H-019 — not deployed due to redundancy). 238 total hypotheses.
- Next: Continue research. Monitor H-189 (-2.94%) and H-160/H-191.
- Questions added: none
- Self-modifications: Archived session 134. (session 144)

### Session 2026-04-05 review+research (session 145)
- Goal: Review + Research — MTM update with Apr 4 daily bar, 3 new factor backtests
- Focus: Paper trade MTM (BTC $67,301 Apr 4 bar), H-239/H-240/H-241 backtests
- Done: 30 runners checked. **Demo**: $99,214 (-0.79%, improving). **12/30 positive**. Top: H-039(+5.79%), H-012(+4.90%), H-076(+4.09%), H-031(+3.43%), H-062(+3.21%). H-012 surged to +4.90% (was +2.22%). H-053 dropped to -2.23% (was +1.39%). H-189 worst at -3.60%. **Research**: **H-239 REJECTED** (price impact — IS 100% low_impact, WF **5/6** mean 1.878 outstanding, but corr **0.525** with H-012 exceeds threshold). **H-240 REJECTED** (beta instability — IS dom dir 70.8% < 80%, high drawdowns 45-62%). **H-241 REJECTED** (multi-horizon disagreement — IS dom dir 90.3% but WF **1/6**, severe overfitting). 241 total hypotheses.
- Next: Continue research. Monitor H-189 (-3.60%) and H-183 (-3.54%).
- Questions added: none
- Self-modifications: Archived session 135. Updated daily data through Apr 4. (session 145)

### Session 2026-04-05 review+deploy+research (session 146)
- Goal: Review + Deploy + Research — MTM check, H-242/H-244 deployment, 3 new factor backtests
- Focus: Paper trade MTM (no new bar, BTC $67,082), H-242/H-243/H-244 backtests
- Done: 32 runners (30→32 post-deploy). No new daily bar since Apr 4. **Research**: **H-242 CONFIRMED** (intraday momentum concentration — IS **100%** high_conc_long, WF **6/6** mean **1.802** outstanding, corr 0.14 H-012, 0.24 H-031. Novel microstructure signal using hourly data). **H-243 REJECTED** (funding-premium divergence — IS 87.5% dom dir but WF **3/6**, doesn't generalize). **H-244 CONFIRMED** (intraday reversal propensity — IS **100%** neg_autocorr_long, WF **4/6** mean 0.268, corr 0.05 H-012, 0.01 H-242. Novel intraday microstructure). Both deployed as paper trades. 244 total hypotheses.
- Next: Continue research. Monitor H-189 (-3.60%) and H-183/H-191.
- Questions added: none
- Self-modifications: H-242/H-244 runners created, added to orchestrator. Archived session 136. (session 146)

### Session 2026-04-05 review+deploy+research (session 147)
- Goal: Review + Deploy + Research — MTM update, H-250 deployment, 6 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$66,870), H-245 through H-250 backtests
- Done: 33 runners (32→33 post-deploy). **Demo**: $100,490 (+0.49%, recovered to positive!). **10/33 positive**. Top: H-039(+5.79%), H-076(+4.07%), H-031(+3.93%), H-012(+2.22%), H-052(+1.92%). H-053 recovered to +1.39%. H-063 trade 2 at +1.31% (expires Apr 10). **Research**: **H-250 CONFIRMED** (US Session Momentum — IS **96.7%** high_us_long, WF **5/5** mean **1.197**, corr **0.032** H-012, **0.378** H-031, **-0.227** H-076. Novel institutional flow proxy using intraday session decomposition). **H-245 REJECTED** (VWAP deviation — 76.7% < 80%). **H-246 REJECTED** (volume HHI — 53.3%). **H-247 REJECTED** (first-hour alignment — 63.3%). **H-248 REJECTED** (intraday efficiency — 56.7%). **H-249 REJECTED** (range expansion — 36.7%). H-250 deployed as paper trade #33: LONG OP/NEAR/SOL, SHORT XRP/ATOM/ADA. 250 total hypotheses.
- Next: Continue research. Monitor H-021 (-3.63%) and H-009/H-160.
- Questions added: none
- Self-modifications: H-250 runner created, added to orchestrator. Archived session 137. (session 147)

### Session 2026-04-05 review+research (session 148)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$66,834), H-251/H-252/H-253 backtests
- Done: 33 runners checked. **Demo**: $100,509 (+0.51%). BTC $66,834. **10/33 positive**. Top: H-039(+5.79%), H-076(+4.07%), H-031(+3.93%), H-012(+2.22%), H-052(+1.92%). H-063 trade 2 at +1.36% (expires Apr 10). **Research**: **H-251 REJECTED** (Hurst exponent — IS 37.5%, best dir 50%, crypto assets have similar persistence, no XS spread). **H-252 REJECTED** (tail ratio — IS 37.5%, best dir high_tail_long 75% borderline but < 80%). **H-253 REJECTED** (return entropy — IS 36.5%, best dir 47.9%, all crypto uniformly high entropy). 253 total hypotheses.
- Next: Continue research. Monitor H-021 (-3.63%) and H-009/H-160.
- Questions added: none
- Self-modifications: Archived session 138. (session 148)

### Session 2026-04-05 review+deploy+research (session 149)
- Goal: Review + Deploy + Research — MTM update, H-255 deployment, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$67,239), H-254/H-255/H-256 backtests
- Done: 34 runners (33→34 post-deploy). **Demo**: $100,649 (+0.65%). **10/34 positive**. Top: H-039(+5.79%), H-076(+4.07%), H-031(+3.93%), H-012(+2.22%), H-052(+1.92%). No new daily bar since Apr 4. **Research**: **H-254 REJECTED** (BTC beta change direction — IS 42.6%, neither direction dominant, beta change is mean-reverting not persistent). **H-255 CONFIRMED** (risk-adjusted momentum/rolling Sharpe — IS **93.3%** high_sharpe_long, WF **5/6** mean **0.964**, split-half H1=1.963/H2=1.447, corr 0.460 H-012. Quality momentum captures risk-adjusted persistence). **H-256 REJECTED** (volume-confirmed return — IS 93.3% passes but WF **3/6** mean -0.164, doesn't generalize OOS). H-255 deployed as paper trade #34: LONG DOGE/ETH/LINK, SHORT ATOM/XRP/DOT. 256 total hypotheses.
- Next: Continue research. Monitor H-021 (-3.63%) and H-009/H-160.
- Questions added: none
- Self-modifications: H-255 runner created, added to orchestrator. Archived session 139. (session 149)
