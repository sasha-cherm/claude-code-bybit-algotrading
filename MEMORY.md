# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$97,538 (-2.46%). BTC spot ~$72,385.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **Internal paper trades:** 66 runners active. Session 173. **20/66 positive**, avg **+0.01%**.
- **H-063**: $9,358 (-6.42%), trade 2 expires Apr 10 08:00 UTC. Expected ~-$662 loss on this trade.
- **Top performers**: H-049(+4.98%), H-085(+4.51%), H-193(+4.43%), H-012(+4.30%), H-076(+4.07%).
- **Session 173 research**: **H-496 ML Ensemble CONFIRMED+deployed.** Best Sharpe ever: 2.149. Equal-weight 10-factor composite. **496 total hypotheses.**
- **AUTOMATED:** Paper trades hourly via cron (66 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Await Q-005 answer on H-056 v3. H-063 settles Apr 10 08:00. Monitor H-496 paper trade performance.
- **Open user questions:** Q-005 (H-056 v3 portfolio upgrade proposal)

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 163) archived to `memory/session_archive.md`._

### Session 2026-04-08 review+optimize (session 164)
- Goal: Review + Portfolio Optimization — comprehensive analysis of 33 confirmed strategies
- Focus: Demo MTM ($96,783, -3.22%), portfolio optimization using backtest return series
- Done: 50 runners (no new bar, BTC $71,829). **Portfolio optimization**: H-056v2 Sharpe 5.64. Proposed v3 adds H-059/H-076. H-031/H-197/H-183 corr 0.88-0.97 (redundant). Q-005 opened.
- Next: Await Q-005 answer. Options strategies. Monitor H-063 (-4.56%).
- Questions added: Q-005 (H-056 v3 proposal)
- Self-modifications: Created comprehensive_optimizer.py. Archived session 154. (session 164)

### Session 2026-04-08 review+deploy+research (session 165)
- Goal: Review + Deploy + Research — MTM update, 10 new backtests (8 XS + 2 options), H-363 deployment
- Focus: Paper trade MTM (BTC $72,508), H-358 through H-367 backtests, VRP analysis, options strategies
- Done: 51 runners (50→51 post-deploy). **Demo**: $97,787 (-2.21%, improved from -3.22%). H-063 deteriorated to **-6.35%** (BTC $72.5k above $69k call). **Research**: 8 XS signals tested — **H-363 CONFIRMED** (multi-day return pattern, IS 83.3% high_long, WF **5/6** mean 0.611, split-half PASS, neighbors 88.9%, corr 0.322 H-012). H-358(76.7%), H-359(60%), H-360(100% but too slow), H-361(79.2%), H-362(50%) REJECTED at IS. H-364(WF 2/6), H-365(split-half fail) REJECTED at WF. **Options research**: Bull put spread (H-366) IS 93.1%, WF **5/5** mean 6.01, Sharpe 1.8-4.4. Strangle (H-367) WF 5/5 mean 3.86. **BTC VRP analysis**: IV overprices RV by +5-15pp (20 days of data), confirming vol-selling edge. 367 total hypotheses.
- Next: Await Q-005 answer. Monitor H-063 (-6.35%, expires Apr 10). Continue research.
- Questions added: none
- Self-modifications: H-363 runner created, added to orchestrator. Archived session 155. (session 165)

### Session 2026-04-08 review+deploy+research (session 166)
- Goal: Review + Deploy + Research — MTM update, 16 new backtests, 3 new deployments
- Focus: Paper trade MTM (BTC $71,593), H-368 through H-383 backtests (2 batches of 8)
- Done: 54 runners (51→54 post-deploy). **Demo**: $97,301 (-2.70%). H-063 improved to -2.68% (BTC retreated from $72.5k to $71.6k). **Research batch 1 (H-368–H-375)**: **H-368 CONFIRMED** (Vol Share Drift — IS **90.7%**, WF **6/6** mean **2.034**, split-half PASS, neighbors 100%, Sharpe 1.628, corr 0.206 H-012). H-369(43% IS), H-370(17%), H-371(80% borderline), H-372(28%), H-373(6%), H-374(2%), H-375(50%) REJECTED. **Research batch 2 (H-376–H-383)**: **H-382 CONFIRMED** (Return Kurtosis — IS **87.5%**, WF **6/6** mean **1.500**, corr **-0.152** H-012). **H-383 CONFIRMED** (PVT — IS **87.5%**, WF **4/6** mean **1.312**, split-half PASS). H-376(67%), H-377(63%), H-378(75%), H-379(17%), H-380(4%), H-381(78% borderline) REJECTED. **383 total hypotheses.**
- Next: Await Q-005 answer. Monitor H-063 (-2.68%, expires Apr 10). Continue research.
- Questions added: none
- Self-modifications: H-368/H-382/H-383 runners created, added to orchestrator. Archived session 156. (session 166)

### Session 2026-04-09 review+deploy+research (session 167)
- Goal: Review + Deploy + Research — MTM update, 16 new backtests, 2 new deployments
- Focus: Paper trade MTM (BTC $71,367), H-384 through H-399 backtests (2 batches of 8)
- Done: 56 runners (54→56). **Demo**: $96,481 (-3.52%). **20/54 positive** (up from 11, avg -0.02%). H-085 surged to +3.74%. H-021 recovered from -4.23% to -0.86%. H-063 at -3.06% (trade 2 expires Apr 10). **Batch 1 (H-384–H-391)**: H-385 CONFIRMED (Vol HHI, IS 83.3%, WF 4/6 but mean -0.362 — NOT deployed). **H-388 CONFIRMED** (Night-Day Diff, IS 96.7%, WF 4/6, corr 0.040, deployed). H-384/H-386/H-387/H-389/H-390/H-391 REJECTED. **Batch 2 (H-392–H-399)**: **H-394 CONFIRMED** (Variance Ratio, IS 86.7%, Sharpe **1.014**, WF 4/6, split-half **0.932/0.958** PASS, corr **0.027** H-012, deployed). H-392/H-393/H-398 no OI data. H-395/H-396/H-397/H-399 REJECTED. **399 total hypotheses.**
- Next: Await Q-005 answer. H-063 expires Apr 10. Continue research. Try to get OI data working.
- Questions added: none
- Self-modifications: H-388/H-394 runners created, added to orchestrator. Archived session 157. (session 167)

### Session 2026-04-09 review+deploy+research (session 168)
- Goal: Review + Deploy + Research — MTM update, 16 new backtests (2 batches of 8), **critical look-ahead bias discovery**, 3 new deployments
- Focus: Paper trade MTM (BTC $70,814), H-400 through H-415 backtests. Look-ahead bias investigation.
- Done: 58 runners (56→58). **23/55 positive** (avg -0.14%). H-049 surged to #1 (+4.93%). H-063 improved to -0.94% (expires tomorrow). **CRITICAL FINDING**: All 4h microstructure backtests had look-ahead bias (same-day features included in signal). Fix: `feat.index < date_i`. H-332 survives lagged (83.3%), but H-336(63.3%)/H-338(66.7%) do NOT. Daily factors H-410/H-413 also inflated by same-close bias. **Batch 1 (H-400–H-407, lagged)**: **H-404 CONFIRMED** (Session Flow, IS 80%, WF 5/6, corr **0.008**, deployed). 7 REJECTED after look-ahead fix. **Batch 2 (H-408–H-415, lagged)**: **H-411 CONFIRMED** (OBV Slope, IS 93.3%, WF 6/6 mean 0.886, deployed). **H-412 CONFIRMED** (Vol Z-Score, borderline WF 4/6, NOT deployed). **H-414 CONFIRMED** (Volume Trend, IS 96.7%, WF 5/6 mean **2.437**, corr **0.028** — session standout, deployed). H-410/H-413 REJECTED (look-ahead inflated). **415 total hypotheses.**
- Next: Await Q-005 answer. H-063 expires Apr 10. Fix 4h backtest look-ahead in existing code. Continue research.
- Questions added: none
- Self-modifications: H-404/H-411/H-414 runners created, added to orchestrator. 4h data resampled from 1h. Look-ahead bias documented. Archived session 158. (session 168)

### Session 2026-04-09 review+deploy+research (session 169)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 2 new deployments
- Focus: Paper trade MTM (BTC $70,742), H-416 through H-439 backtests. Hourly-derived signal exploration.
- Done: 61 runners (59→61). **20/57 positive** (avg **+0.12%**, improved from -0.14%). **Demo**: $97,282 (-2.72%, improving). H-012 surged to +4.30%. H-191 worst at -6.51%. **Batch 1 (H-416–H-423, daily composite)**: All 8 REJECTED at IS ~50%. **Batch 2 (H-424–H-431, daily structural)**: All 8 REJECTED at IS ~50%. **Daily XS factor space exhausted.** **Batch 3 (H-432–H-439, hourly-derived)**: **H-435 CONFIRMED** (Hourly Kurtosis, IS 95.8%, WF 4/6 mean 1.367, SH PASS, corr 0.106, deployed). **H-437 CONFIRMED** (HL Spread Proxy, IS 95.8%, WF 5/6 mean 1.049, SH PASS, corr **-0.183**, deployed). H-434 INVALIDATED (constant 1.0 — no gaps in 24/7 crypto). H-432/H-436 borderline (SH fail). **439 total hypotheses.**
- Next: Await Q-005 answer. H-063 expires Apr 10 08:00. Explore more hourly-derived signals. Consider killing worst performers.
- Questions added: none
- Self-modifications: H-435/H-437 runners created, added to orchestrator. Archived session 159. (session 169)

### Session 2026-04-09 review+deploy+research (session 170)
- Goal: Review + Deploy + Research — MTM update, 16 new backtests (2 batches of 8), 3 new deployments
- Focus: Paper trade MTM (BTC $71,171), H-440 through H-455 backtests. Hourly-derived signal exploration continued.
- Done: 64 runners (61→64). **20/61 positive** (avg +0.09%). **Demo**: $98,154 (-1.85%, improving). **Batch 1 (H-440–H-447)**: **H-445 CONFIRMED** (Max Hourly DD, IS 95.8%, WF 5/6 mean 1.500, SH PASS, corr **-0.200** — negative, deployed). **H-447 CONFIRMED** (Vol Autocorr, IS 87.5%, WF 4/6, SH PASS, corr 0.039, deployed). H-442/H-444 borderline (SH fail). 4 rejected. **Batch 2 (H-448–H-455)**: **H-451 CONFIRMED** (Close-High Ratio, IS 100%, WF 5/6 mean 1.366, SH PASS, corr 0.258, deployed). H-449/H-452/H-455 borderline (SH fail). H-455 notable: WF **6/6** mean 2.171 but H2=-0.071. 4 rejected. **455 total hypotheses.**
- Next: Await Q-005 answer. H-063 expires Apr 10 08:00. Continue hourly-derived exploration. H-455 worth revisiting.
- Questions added: none
- Self-modifications: H-445/H-447/H-451 runners created, added to orchestrator. Archived session 160. (session 170)

### Session 2026-04-09 review+deploy+research (session 171)
- Goal: Review + Deploy + Research — MTM update, 16 new backtests (2 batches of 8), 1 new deployment
- Focus: Paper trade MTM (BTC $71,245), H-456 through H-471 backtests. Hourly-derived signal exploration — final batch.
- Done: 65 runners (64→65). **20/65 positive** (avg +0.07%). **Batch 1 (H-456–H-463)**: 0 confirmed. 4 borderline (H-456 VW Ret, H-458 Up Vol, H-459 Amihud, H-461 Vol HHI — all SH FAIL). H-456/H-458 have high H-012 corr (0.6+). 4 rejected. **Batch 2 (H-464–H-471)**: **H-470 CONFIRMED** (First Hour Ret, IS 100%, WF 4/6 mean 0.365, SH **PASS** H1=1.665 H2=0.411, corr 0.267, deployed). H-467 borderline (SH FAIL, H1=-0.073). 6 rejected. **471 total hypotheses.** Hourly-derived space approaching exhaustion — SH failures dominate.
- Next: Await Q-005 answer. H-063 expires Apr 10 08:00. Explore new signal categories (multi-timeframe, cross-asset, or non-price data). 
- Questions added: none
- Self-modifications: H-470 runner created, added to orchestrator. Archived session 161. (session 171)

### Session 2026-04-09 review+research (session 172)
- Goal: Review + Research — MTM update, 24 new backtests (3 batches of 8), no deployments
- Focus: Paper trade MTM (BTC $72,405), H-472 through H-495 backtests. Cross-asset dynamics, factor interactions, calendar seasonality.
- Done: 65 runners (unchanged). **20/65 positive** (avg +0.04%). Demo $97,514 (-2.49%). H-063 heading for ~-5% loss (trade 2, BTC rallied to $72.4k vs $69k call). **Batch 1 (H-472–H-479, cross-asset)**: All 8 REJECTED at IS. Lead-lag, correlation clustering, beta dynamics, spillover, idiosyncratic momentum — no cross-asset edges. **Batch 2 (H-480–H-487, interactions)**: **H-485 CONFIRMED** (Monthly Reversal, IS 100%, WF 4/6 mean 1.042, SH PASS — NOT deployed, H-012 corr 0.591). H-486 borderline (IS 94%, WF 6/6 but H-012 corr 0.899). 6 REJECTED. **Batch 3 (H-488–H-495, novel)**: All 8 REJECTED. Factor composite, calendar seasonality, distance-from-high, autocorrelation — no edges. **495 total hypotheses.** Signal space thoroughly exhausted across daily XS, hourly-derived, cross-asset, and interaction categories.
- Next: Await Q-005 answer. H-063 expires Apr 10 08:00. Consider ML signal combination, alternative asset universes, or longer history.
- Questions added: none
- Self-modifications: Archived session 162. (session 172)

### Session 2026-04-09 review+research (session 173)
- Goal: Review + Research — MTM update, ML ensemble signal combination, H-496 deployed
- Focus: Paper trade MTM (BTC $72,385), ML ensemble backtest combining 30 confirmed XS factors
- Done: 66 runners (65→66). **20/66 positive** (avg +0.01%). Demo $97,538 (-2.46%). H-063 at -6.42% (expires tomorrow 08:00, expected -$662 loss). **ML Ensemble research**: Tested 3 methods (equal-weight, IC-weighted, ridge) on 30 factors. Equal-weight best. **Focused 10-factor subset dramatically outperforms**: Sharpe **2.149** (+98.7% ann, -23.8% DD). WF **5/6** positive (mean 2.189). SH PASS (2.555/1.655). Param robust 12/12. H-496 = best single-strategy Sharpe ever found. Key insight: simpler equal-weight beats ML weighting. Most recent fold flat (-0.049). **496 total hypotheses.**
- Next: Await Q-005 answer. H-063 settles Apr 10 08:00. Monitor H-496 paper performance. Consider H-496 for v3 portfolio.
- Questions added: none
- Self-modifications: H-496 runner created, added to orchestrator. Archived session 163. (session 173)
