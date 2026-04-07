# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$100,050 (+0.05%, near breakeven!). BTC spot ~$68,763.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **H-011 status**: DROPPED from demo. Internal paper trade IN. Capital $9,873 (-1.27%).
- **Internal paper trades:** 40 runners active. Session 157. **16/38 positive** (Apr 6 bar processed, big improvement from 9/40).
- **H-063**: $10,150 (+1.50%), between trades. **H-039**: +5.79%, next LONG Wed Apr 9.
- **Top performers**: H-039(+5.79%), H-012(+4.46%), H-076(+4.36%), H-031(+3.97%), H-049(+3.46%).
- **Key shift**: Demo recovered -0.83% → +0.05%. H-049 surged +3.46%, H-085/H-175/H-063/H-019 all flipped positive.
- **Research**: 291 total hypotheses. H-280 through H-291 all REJECTED (12 new factors, no confirmations).
- **AUTOMATED:** Paper trades hourly via cron (40 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Continue research. Monitor H-021 (-2.47% worst) and H-183 (-2.43%).
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 147) archived to `memory/session_archive.md`._

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

### Session 2026-04-06 review+deploy+research (session 150)
- Goal: Review + Deploy + Research — MTM update, H-259 deployment, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$67,575), H-257/H-258/H-259 backtests
- Done: 35 runners (34→35 post-deploy). **Demo**: $100,877 (+0.88%). **12/35 positive**. Top: H-039(+5.79%), H-012(+4.67%), H-076(+3.92%), H-031(+3.49%), H-062(+2.92%). H-012 surged +2.22%→+4.67%. H-021 improved -3.63%→-1.00%. H-175 flipped positive (+2.45%). Daily data updated through Apr 5 bar ($67,631 close). **Research**: **H-257 REJECTED** (intraday return dominance — IS 100%, WF **6/6** mean 2.780 best-ever, but in 24/7 crypto open≈prev_close so factor reduces to short-term momentum, corr 0.538 H-012). **H-258 REJECTED** (recovery speed — IS only 50%, no XS predictive power). **H-259 CONFIRMED** (extreme move frequency — IS **100%** high_long, WF **5/6** mean **1.320**, corr **0.272** H-012, novel tail-risk signal). H-259 deployed as paper trade #35: LONG OP/ATOM/ARB/DOT, SHORT ADA/LINK/AVAX/NEAR. 259 total hypotheses.
- Next: Continue research. Monitor H-189 (-3.56%) and H-183 (-3.40%).
- Questions added: none
- Self-modifications: H-259 runner created, added to orchestrator. Archived session 140. (session 150)

### Session 2026-04-06 review+research (session 151)
- Goal: Review + Research — MTM update with final Apr 5 bar, 3 new factor backtests
- Focus: Paper trade MTM (BTC Apr 5 final $69,035, Apr 6 in progress $68,939), H-260/H-261/H-262 backtests
- Done: 35 runners checked. **Demo**: $98,869 (-1.13%). **16/35 positive** (was 12/35). Top: H-039(+5.79%), H-031(+4.74%), H-012(+4.08%), H-076(+3.66%), H-062(+2.82%). H-085 flipped +1.82% (was -0.49%). H-049 surged +2.49% (was +1.16%). H-242 positive +1.27%. H-053 worst at -2.12%. Daily data refreshed with final Apr 5 bar ($69,035 close, +2.6% day). **Research**: **H-260 REJECTED** (BTC correlation regime — IS 86.7% high_long but 70/30 OOS -1.376, split-half H2=-2.047, WF 2/6, severe regime-dependence). **H-261 REJECTED** (volume spike frequency — IS 47.9%, no XS power). **H-262 REJECTED** (return consistency median/mean — IS 61.1%, no dominant direction). 262 total hypotheses.
- Next: Continue research. Monitor H-053 (-2.12%) and H-183 (-1.88%).
- Questions added: none
- Self-modifications: Archived session 141. Updated daily data with final Apr 5 bar. (session 151)

### Session 2026-04-06 review+deploy+research (session 152)
- Goal: Review + Deploy + Research — MTM update, H-263/H-264 deployment, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$69,130), H-263/H-264/H-265 backtests
- Done: 37 runners (35→37 post-deploy). **Demo**: $98,188 (-1.81%). **10/37 positive**. Top: H-039(+5.79%), H-012(+4.30%), H-076(+4.07%), H-031(+3.93%), H-062(+3.10%). No new daily bar since Apr 5. **Research**: **H-263 CONFIRMED** (relative strength vs BTC — IS **100%** high_long, WF **6/6** mean **4.058** best-ever, Sharpe 4.087, corr 0.338 H-012. Captures idiosyncratic altcoin outperformance vs BTC). **H-264 CONFIRMED** (return skewness — IS **91.7%** high_long, WF **6/6** mean **1.532**, Sharpe 1.879, corr 0.400 H-012. Counterintuitive: high skew=breakout phase in crypto). **H-265 REJECTED** (lead-lag response — IS 55.6%, no robust XS signal, crypto lacks equity-like lead-lag structure). Both H-263/H-264 deployed as paper trades #36-37. 265 total hypotheses.
- Next: Continue research. Monitor H-009 (-2.10%) and H-021 (-1.71%).
- Questions added: none
- Self-modifications: H-263/H-264 runners created, added to orchestrator. Archived session 142. (session 152)

### Session 2026-04-06 review+research (session 153)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$69,200), H-266/H-267/H-268 backtests
- Done: 37 runners checked. **Demo**: $98,176 (-1.82%). **10/37 positive**. Top: H-039(+5.79%), H-012(+4.30%), H-076(+4.07%), H-031(+3.93%), H-062(+3.10%). No new daily bar since Apr 5. H-063 trade 2 eq $10,024 (+0.24%). **Research**: **H-266 REJECTED** (conditional beta asymmetry — IS **35.4%**, mean Sharpe -0.135, up/down beta decomposition too noisy in crypto). **H-267 REJECTED** (variance ratio — IS **41.7%**, strong directional signal 88.9% high_vr_long but insufficient IS robustness, same issue as Hurst/autocorrelation). **H-268 REJECTED** (OI growth rate — IS **35.0%**, pure OI momentum has no XS power, OI only useful relative to price). 268 total hypotheses.
- Next: Continue research. Monitor H-009 (-2.10%) and H-021 (-1.71%).
- Questions added: none
- Self-modifications: Archived session 143. (session 153)

### Session 2026-04-06 review+research (session 154)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$69,348), H-269/H-270/H-271 backtests
- Done: 37 runners checked. **Demo**: $97,400 (-2.60%, down from -1.82%). **16/37 positive** (was 10/37 — big improvement as recent runners entered positions). Top: H-039(+5.79%), H-031(+4.67%), H-012(+4.26%), H-076(+3.63%), H-062(+3.06%). Key shifts: H-049 surged +2.63%, H-175 flipped +2.18%, H-085 flipped +1.72%. H-053 crashed -2.06% (was +1.39%). H-063 trade 2 at +0.10% (BTC above $69k call strike, pressure building). **Research**: **H-269 REJECTED** (momentum breadth/% positive days — IS **31.7%**, discards magnitude info which hurts). **H-270 REJECTED** (DV acceleration — IS **42.1%**, best Sharpe 2.05 but second derivative amplifies noise). **H-271 REJECTED** (price efficiency ratio — IS **41.7%**, 100% high_eff_long but not enough XS spread). 271 total hypotheses.
- Next: Continue research. Monitor H-053 (-2.06%) and H-183 (-1.75%).
- Questions added: none
- Self-modifications: Archived session 144. (session 154)

### Session 2026-04-06 review+research (session 155)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$69,750), H-272/H-273/H-274 backtests
- Done: 37 runners checked. **Demo**: $98,557 (-1.44%, improved from -2.60%). BTC $69,750. No new daily bar since Apr 5. H-063 trade 2: call now ITM ($69,750 > $69,000 strike), eq ~$9,967 (-0.33%), expires Apr 10. **Research**: **H-272 REJECTED** (idiosyncratic vol — IS **35.0%**, low_idiovol_long 85.7% dom, crypto assets all have high idio-vol, insufficient XS spread). **H-273 REJECTED** (funding rate momentum/change — IS **41.7%**, falling_fund_long 100% dom, change signal noisier than level). **H-274 REJECTED** (return-volume correlation — IS **48.6%**, high_corr_long 100% dom, PV relationship unstable in crypto). 274 total hypotheses.
- Next: Continue research. Monitor H-063 (call ITM, pressure building) and H-053 (-2.06% MTM).
- Questions added: none
- Self-modifications: Archived session 145. (session 155)

### Session 2026-04-06 review+deploy+research (session 156)
- Goal: Review + Deploy + Research — MTM update, H-277 deployment, 5 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$69,819), H-275/H-276/H-277/H-278/H-279 backtests
- Done: 40 runners (39→40 post-deploy). **Demo**: $99,165 (-0.83%, improved from -1.44%). **9/40 positive**. Top: H-039(+5.79%), H-012(+4.30%), H-076(+4.07%), H-031(+3.93%), H-062(+3.10%). No new daily bar since Apr 5. H-063 between trades ($9,928, -0.71%). **Research**: **H-277 CONFIRMED** (VWAP deviation — IS **80%** above_vwap_long, WF **5/6** mean **1.256**, neighboring params **87.5%** positive, split-half H1=1.795/H2=0.867, corr 0.464 H-012, 0.112 H-076. Volume-weighted momentum variant). **H-275 REJECTED** (CLV — 63.3% IS). **H-276 REJECTED** (autocorrelation — 58.3% IS). **H-278 REJECTED** (kurtosis — IS 83.3% but WF mean Sharpe -0.119). **H-279 REJECTED** (volume CV — 75% IS). H-277 deployed as paper trade #40: LONG BTC/ETH/ARB, SHORT XRP/SUI/DOT. 279 total hypotheses.
- Next: Continue research. Monitor H-009 (-2.10% worst) and H-021 (-1.71%).
- Questions added: none
- Self-modifications: H-277 runner created, added to orchestrator. Archived session 146. (session 156)

### Session 2026-04-07 review+research (session 157)
- Goal: Review + Research — MTM update with Apr 6 bar, 12 new factor backtests
- Focus: Paper trade MTM (Apr 6 bar $68,846, BTC now $68,763), H-280 through H-291 backtests
- Done: 40 runners checked. **Demo**: $100,050 (+0.05%, recovered from -0.83% to near breakeven!). **16/38 positive** (was 9/40). Top: H-039(+5.79%), H-012(+4.46%), H-076(+4.36%), H-031(+3.97%), H-049(+3.46%). Key movers: H-049 surged +0.56%→+3.46%, H-085 flipped +1.92%, H-175 flipped +1.30%, H-063 flipped +1.50%, H-019 flipped +1.71%. H-183 crashed -2.43%. H-021 worst at -2.47%. **Research**: All 12 REJECTED — H-280(wick ratio 40.3%), H-281(vol-weight persistence 45.8%), H-282(close-to-high 43.1%), H-283(dispersion 38.9%), H-284(volume surprise 50%), H-285(direction persistence 36.1%), H-286(return/volume 50%), H-287(gap 0%), H-288(Sharpe change 44.4%), H-289(residual mom FAILED), H-290(DD recovery 38.9%), H-291(ATR ratio 44.4%). 291 total hypotheses.
- Next: Continue research. Explore fundamentally different signal types (funding, OI combinations, multi-asset). Monitor H-021 (-2.47%) and H-183 (-2.43%).
- Questions added: none
- Self-modifications: Archived session 147. (session 157)
