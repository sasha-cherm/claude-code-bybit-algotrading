# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$97k. BTC spot ~$73,310.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **Internal paper trades:** 74 runners active. Session 179. **26/74 positive** (35%), avg **-0.10%**.
- **H-063**: $9,624 (-3.76%). FLAT. Awaiting trade 3 entry.
- **Top performers**: H-049(+4.98%), H-085(+4.51%), H-193(+4.43%), H-012(+4.30%), H-244(+4.04%).
- **Session 179 research**: 24 new hypotheses (H-612–H-635). **1 CONFIRMED+deployed** (H-617 BTC 4h Vol Breakout). 1 CONFIRMED not deployed (H-622 redundant H-617). 22 REJECTED. **635 total hypotheses.**
- **AUTOMATED:** Paper trades hourly via cron (74 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Await Q-005 answer. Monitor all paper trades. H-063 trade 3. Explore on-chain data, altcoin TS, or higher-freq XS.
- **Open user questions:** Q-005 (H-056 v3 portfolio upgrade proposal)

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 169) archived to `memory/session_archive.md`._

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

### Session 2026-04-10 review+research (session 174)
- Goal: Review + Research — MTM update, 16 new hypotheses (regime timing + portfolio construction)
- Focus: Paper trade MTM (BTC $71,966), H-497 through H-512 backtests
- Done: 66 runners (unchanged). **26/66 positive** (avg -0.10%). H-063 trade 2 expires today 08:00 (expected -$514 loss, call ITM). H-496 paper trade at +0.22% (1 day). **Research batch 1 (H-497–H-504, regime-adaptive)**: All 8 REJECTED. BTC trend/vol/dispersion/correlation/volume regime timing and trend-adaptive weighting all fail to beat base ensemble (Sharpe 2.137). Best was H-497 at +2.1%. **Research batch 2 (H-505–H-512, portfolio construction)**: All 8 REJECTED. Continuous weighting, vol-scaled, multi-horizon, asymmetric L/S, signal threshold, turnover penalty, dynamic N, risk-parity — none beat simple L4/S4 equal-weight 5d rebal. Best was H-511 Dynamic N at +1.0%. **512 total hypotheses.** Meta-conclusion: base ensemble is optimal — simpler is better.
- Next: Await Q-005 answer. H-063 settles today 08:00. Explore new data sources, higher frequency, or alternative asset universes.
- Questions added: none
- Self-modifications: Archived session 164. (session 174)

### Session 2026-04-10 review+deploy+research (session 175)
- Goal: Review + Deploy + Research — MTM update, 19 new backtests, H-528 deployment
- Focus: Paper trade MTM (BTC $72,128), expanded universe testing, novel signal categories (H-513–H-531)
- Done: 67 runners (66→67). **26/66 positive** (avg -0.11%). Demo $94,608 (-5.39%). H-063 at -4.91% (trade 2 expires 08:00 UTC, expected -$574 loss). H-496 at +0.22% (day 1). **Expanded universe**: Tested 27-asset momentum (Sharpe 0.26) and size (0.77) — both worse than 14-asset. **Batch 1 (H-513–H-522)**: H-518 Regime Mom (Sharpe 1.36, WF 6/6 but corr 0.793 H-012 = redundant). **H-519 Vol Shock** (Sharpe 1.52, 100% robust, corr -0.041 H-012, but 0.704 corr H-336 = redundant). H-522 PVT Slope (Sharpe 0.98, 100% robust, corr 0.425 H-012). 7 REJECTED. **Batch 2 (H-523–H-531)**: **H-528 Range Expansion CONFIRMED+deployed** (IS 0.849, 100% param robust 96/96, WF 4/6, SH PASS, corr **-0.001** H-012 — perfect diversifier). H-530 DV Share passes all tests but corr 0.934 with H-031 = identical. 8 REJECTED. **531 total hypotheses.**
- Next: Await Q-005 answer. H-063 settles today 08:00. Monitor H-496/H-528. Explore higher-frequency or different instruments.
- Questions added: none
- Self-modifications: H-528 runner created, added to orchestrator. Archived session 165. (session 175)

### Session 2026-04-10 review+deploy+research (session 176)
- Goal: Review + Deploy + Research — MTM update, H-063 settlement check, 16 new BTC time-series backtests, 3 deployments
- Focus: Paper trade MTM (BTC $71,681), BTC time-series strategies (H-532–H-547)
- Done: 70 runners (67→70). **14/66 positive** (21%, down from 26). Avg **-0.17%**. Demo ~$94,700 (-5.30%). **H-063 trade 2 settled**: BTC $71,641 at expiry, 69kC ITM, loss -$454, total -3.76%. **Research**: Explored BTC time-series (TS) strategies — fundamentally different from all prior XS factors. **H-535 CONFIRMED** (Intra Mom, WF 6/8 mean 1.05, SH PASS). **H-539 CONFIRMED** (Keltner Breakout, WF 5/7, 83% param robust, SH PASS). **H-544 CONFIRMED** (Range Squeeze, WF 5/8, **100% param robust**, SH PASS, corr 0.109 H-009). **CRITICAL**: H-540 Multi-Asset TSMOM had look-ahead bias (Sharpe 6.17 fake → 0.57 real). 13 REJECTED. **547 total hypotheses.**
- Next: Await Q-005 answer. Monitor BTC TS paper trades. H-063 trade 3 entry tonight. Consider alternative instruments or higher-frequency.
- Questions added: none
- Self-modifications: H-535/H-539/H-544 runners created, added to orchestrator. Archived session 166. (session 176)

### Session 2026-04-10 review+deploy+research (session 177)
- Goal: Review + Deploy + Research — MTM update, 32 new backtests (ETH TS, multi-asset, classic indicators, multi-TF), 1 deployment
- Focus: Paper trade MTM (BTC $72,202), ETH/SOL time-series and classic indicator strategies (H-548–H-579)
- Done: 71 runners (70→71). **26/70 positive** (37%, up from 21%). Avg **-0.09%** (improved). Demo ~$95,900 (-4.10%, recovering). **Batch 1 (H-548–H-563, ETH TS + cross-asset)**: All 16 REJECTED. ETH intraday momentum FAILS (Sharpe -0.45), mean-reversion universally fails in crypto, BTC-ETH spread not mean-reverting, leader-follower doesn't work. Best was H-561 ATR Breakout (Sharpe 0.404, close but below threshold). **Batch 2 (H-564–H-579, multi-TF/adaptive/SOL/classic)**: **H-571 CONFIRMED** (SOL Session Momentum, IS **0.847**, WF **6/7** mean 0.848, SH PASS, **100% param robust**, BTC corr **-0.092**, deployed). H-572 BTC Multi-TF close (Sharpe 0.651, WF 6/7, SH PASS) but param robust only 69% — REJECTED. 15 REJECTED. **579 total hypotheses.**
- Next: Await Q-005 answer. Monitor TS paper trades (H-535/H-539/H-544/H-571). H-063 trade 3 tonight. Explore options strategies or non-price data.
- Questions added: none
- Self-modifications: H-571 runner created, added to orchestrator. Archived session 167. (session 177)

### Session 2026-04-10 review+deploy+research (session 178)
- Goal: Review + Deploy + Research — MTM update, 32 new backtests (4 batches of 8), 2 new deployments
- Focus: Paper trade MTM (BTC $72,892), novel XS signals: multi-period momentum, funding dynamics, candlestick patterns, volume trends (H-580–H-611)
- Done: 73 runners (71→73). **26/71 positive** (37%). Avg **-0.09%** (stable). Demo ~$96k-$97k. H-063 flat, trade 3 at 01:00 UTC. **Batch 1 (H-580–H-587)**: All 8 REJECTED. Multi-period mom, dispersion, OBV ROC, gap reversal — no edges above 0.7 Sharpe. **Batch 2 (H-588–H-595)**: H-589 Vol Ratio CONFIRMED (IS 1.213, WF 5/6, SH PASS, but factor corr 0.82+ with H-059 → NOT deployed). H-593 VW Momentum REJECTED (WF 3/6 fail). 6 more REJECTED. **Batch 3 (H-596–H-603)**: **H-599 RSI XS CONFIRMED** (IS 1.148, WF 4/6, **100% param robust**, deployed). **H-601 Vol Decline CONFIRMED** (IS 0.965, WF 4/6, **100% param robust**, corr **0.054** H-012, deployed). H-606 CLV CONFIRMED (IS 1.260, WF 5/6) but redundant with H-451 (PnL corr 0.691). 5 REJECTED. **Batch 4 (H-604–H-611)**: H-606 CLV confirmed above. 7 REJECTED. **611 total hypotheses.**
- Next: Await Q-005 answer. Monitor all 73 runners. H-063 trade 3 tonight. Continue exploring options/on-chain/alternative data.
- Questions added: none
- Self-modifications: H-599/H-601 runners created, added to orchestrator. Archived session 168. Fixed WF min-days bug (90-day folds were below 100-day threshold). (session 178)

### Session 2026-04-11 review+deploy+research (session 179)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 1 new deployment
- Focus: Paper trade MTM (BTC $73,310), 4-hour timeframe BTC time-series exploration (H-612–H-635)
- Done: 74 runners (73→74). **26/74 positive** (35%). Avg **-0.10%**. Demo ~$97k (+1.3% 24h). **Batch 1 (H-612–H-619, 4h BTC TS)**: **H-617 CONFIRMED** (4h Volume Breakout, IS 0.971, WF 6/8, 88% param robust, SH PASS, deployed). H-616 Keltner borderline (SH FAIL). 6 REJECTED (EMA/RSI/MACD/BB/adaptive = noise at 4h). **Batch 2 (H-620–H-627, multi-asset 4h + funding)**: **H-622 CONFIRMED** (Multi-Asset 4h Vol Breakout BTC+ETH+SOL, IS 1.001, 100% robust) but NOT deployed — corr 0.724 with H-617 = redundant. H-627 OI Proxy promising (IS 0.877, WF 4/5) but only 709 days data. H-624/H-625/H-626 REJECTED (funding rate timing fails). **Batch 3 (H-628–H-635, structural patterns)**: All 8 REJECTED. Weekend effect too weak. Session patterns not tradable. Vol compression, multi-TF alignment, momentum reversal, range expansion, RSI-vol divergence — no edges.
- Next: Await Q-005 answer. Monitor H-617 4h paper trade. Explore altcoin TS, on-chain data, or intra-day XS.
- Questions added: none
- Self-modifications: H-617 runner created, added to orchestrator. Archived session 169. (session 179)
