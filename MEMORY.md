# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$99,558 (-0.44%). BTC spot ~$68,200.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **H-011 status**: DROPPED from demo. Internal paper trade IN. Capital $9,872 (-1.28%).
- **Internal paper trades:** 41 runners active. Session 160. **16/41 positive**. H-324 deployed (starts FLAT, ADX < 30).
- **H-063**: $10,207 (+2.07%), trade 2 in progress (expires Apr 10). **H-039**: +5.79%, next LONG Wed Apr 9.
- **Top performers**: H-039(+5.79%), H-012(+4.46%), H-076(+4.36%), H-031(+3.97%), H-049(+3.46%).
- **Research**: 331 total hypotheses. Session 160: 24 time-series strategy backtests (H-308 to H-331). H-324 CONFIRMED (ADX-filtered TSMOM), 23 REJECTED. Key findings: (1) TS momentum in crypto is regime-dependent — pure TSMOM fails WF. (2) ADX filtering removes whipsaw, enabling WF 4/5. (3) Hourly MR/momentum signals exist but don't survive fees.
- **AUTOMATED:** Paper trades hourly via cron (41 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Continue: options strategies beyond strangles, portfolio optimization, alternative assets. Monitor H-021 (-2.47% worst) and H-183 (-2.43%).
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 150) archived to `memory/session_archive.md`._

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

### Session 2026-04-07 review+research (session 158)
- Goal: Review + Research — MTM update, 8 multi-factor interaction backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$68,935), H-292 through H-299 backtests
- Done: 40 runners checked. **Demo**: $99,799 (-0.20%, dipped from +0.05%). **16/40 positive**. Top: H-039(+5.79%), H-012(+4.15%), H-076(+4.14%), H-031(+3.86%), H-049(+3.25%). Worst: H-021(-2.65%), H-183(-2.46%). **Research**: All 8 REJECTED — H-292(mom×efficiency IS 93.5% but corr H-012 0.749), H-293(regime conditional IS 20.4%), H-294(mom×funding IS 94.4% but corr 0.522), H-295(BTC beta timing IS 24.1%), H-296(funding-premium spread IS 0%), H-297(MTF momentum IS 98.6%, WF 6/6, but corr 0.649), H-298(informed momentum IS 94.4% but corr 0.506), H-299(decorrelation IS 1.9%). **Key insight**: Multi-factor interactions of known factors produce great IS/WF (93-99%) but are too correlated (0.50-0.75) with components to add novel value. 299 total hypotheses.
- Next: Explore non-momentum-based signals, alternative constructions, or frequency domain approaches. Monitor H-021 (-2.65%) and H-183 (-2.46%).
- Questions added: none
- Self-modifications: Archived session 148. Fixed metrics bug (PPY passed as risk_free_rate). (session 158)

### Session 2026-04-07 review+research (session 159)
- Goal: Review + Research — MTM update, 8 non-momentum signal backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$68,888), H-300 through H-307 backtests
- Done: 40 runners checked. **Demo**: $99,584 (-0.42%, dipped from -0.20%). **15/40 positive** (was 16). Top: H-039(+5.79%), H-012(+4.15%), H-076(+4.14%), H-031(+3.86%), H-049(+3.25%). BTC dipped to $68,200 intraday. **Research**: All 8 REJECTED — H-300(short-term reversal IS 56.2%, WF 5/6 but split-half fail), H-301(corr centrality IS 91.7% but split-half fail), H-302(direction streak IS 0%), H-303(asymmetric vol IS 37.5%, LB20 only), H-304(EWM momentum IS 76.7%, corr H-012 0.631), H-305(beta change IS 44.4%), H-306(vol-price divergence IS 38.9% **but** corr H-012 **-0.447**, WF 5/6, split-half pass — best anti-momentum diversifier found), H-307(return entropy IS 12.5%, reverse 87.5% but too weak). 307 total hypotheses.
- Next: Single-factor XS signals largely exhausted after 307 hypotheses. Shift focus to: portfolio optimization, alternative assets, time-series strategies, or options strategies.
- Questions added: none
- Self-modifications: Archived session 149. (session 159)

### Session 2026-04-07 review+deploy+research (session 160)
- Goal: Review + Deploy + Research — MTM update, 24 time-series strategy backtests, H-324 deployment
- Focus: Paper trade MTM (no new daily bar, BTC ~$68,200), H-308 through H-331 backtests (24 TS strategies)
- Done: 41 runners (40→41 post-deploy). **Demo**: $99,558 (-0.44%). **16/41 positive**. Top: H-039(+5.79%), H-012(+4.46%), H-076(+4.36%), H-031(+3.97%), H-049(+3.46%). H-063 improved +2.07%. **Research**: Pivoted to time-series strategies (only 3 TS vs 35+ XS). Tested: pure TSMOM (H-308, 70.8% IS but -50% DD), vol-scaled TSMOM (H-309, WF 3/5), ensemble TSMOM (H-313, 96.7% IS but WF 2/5), EMA crossover (H-310, high DD), Donchian (H-311, 42% IS), TS carry (H-312/H-320, 100% IS but WF marginal), mean reversion (H-314-316, too parameter-sensitive), calendar effects (H-317-318, no signal), vol regime (H-319, 65% IS), BTC vol target (H-321, doesn't beat BH), hourly MR (H-322, Sharpe 2.4 pre-fees but **-0.2 post-fees**), hourly momentum (H-323, 65% IS), **ADX-filtered TSMOM (H-324, CONFIRMED, WF 4/5 mean 0.557)**, BTC-cond alts (H-325, 8% IS), vol breakout (H-326, 31% IS), return persistence (H-327, 50%), market timing (H-328, 23%), BTC lead-lag hourly (H-329, Sharpe 1.66 pre-fees but killed by 0.02% fee), range compression (H-330, 41% IS), ATR trend (H-331, 78% IS but Sharpe 0.05). **Key insights**: (1) TS momentum in crypto is regime-dependent; ADX filter is the key to making it work. (2) Hourly signals exist but don't survive trading costs. (3) H-324 is first multi-asset TS strategy to pass WF. 331 total hypotheses.
- Next: Continue research: options strategies beyond strangles, portfolio-level optimization. Monitor H-021 (-2.47%) and H-183 (-2.43%).
- Questions added: none
- Self-modifications: H-324 runner created, added to orchestrator. Archived session 150. (session 160)
