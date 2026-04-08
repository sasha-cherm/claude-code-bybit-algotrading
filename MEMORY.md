# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity ~$97,301 (-2.70%). BTC spot ~$71,593.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x).
- **H-011 status**: DROPPED from demo. Internal paper trade IN. Capital $9,880 (-1.20%).
- **Internal paper trades:** 54 runners active. Session 166. **11/54 positive**, avg +0.11%.
- **H-063**: $9,732 (-2.68%), trade 2 in progress (expires Apr 10, BTC above $69k call).
- **Top performers**: H-039(+5.75%), H-012(+4.30%), H-076(+4.07%), H-031(+3.93%), H-062(+3.10%).
- **Session 166 research**: 16 new hypotheses (H-368 to H-383). **3 CONFIRMED**: H-368 (Vol Share Drift, WF 6/6 mean 2.034), H-382 (Return Kurtosis, WF 6/6 mean 1.500, corr -0.152 H-012), H-383 (PVT, WF 4/6 mean 1.312). All 3 deployed.
- **AUTOMATED:** Paper trades hourly via cron (54 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Await Q-005 answer on H-056 v3. Monitor H-063 (-2.68%, expires Apr 10). Continue research.
- **Open user questions:** Q-005 (H-056 v3 portfolio upgrade proposal)

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 155) archived to `memory/session_archive.md`._

### Session 2026-04-07 review+research (session 157)
- Goal: Review + Research — MTM update with Apr 6 bar, 12 new factor backtests
- Focus: Paper trade MTM (Apr 6 bar $68,846, BTC now $68,763), H-280 through H-291 backtests
- Done: 40 runners checked. **Demo**: $100,050 (+0.05%, recovered from -0.83% to near breakeven!). **16/38 positive** (was 9/40). All 12 REJECTED. 291 total hypotheses.
- Next: Explore fundamentally different signal types. Monitor H-021 (-2.47%) and H-183 (-2.43%).
- Questions added: none
- Self-modifications: Archived session 147. (session 157)

### Session 2026-04-07 review+research (session 158)
- Goal: Review + Research — MTM update, 8 multi-factor interaction backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$68,935), H-292 through H-299 backtests
- Done: 40 runners checked. **Demo**: $99,799 (-0.20%). All 8 REJECTED. **Key insight**: Multi-factor interactions (93-99% IS) are too correlated (0.50-0.75) with components. 299 total hypotheses.
- Next: Explore non-momentum-based signals. Monitor H-021 (-2.65%) and H-183 (-2.46%).
- Questions added: none
- Self-modifications: Archived session 148. Fixed metrics bug. (session 158)

### Session 2026-04-07 review+research (session 159)
- Goal: Review + Research — MTM update, 8 non-momentum signal backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$68,888), H-300 through H-307 backtests
- Done: 40 runners checked. **Demo**: $99,584 (-0.42%). All 8 REJECTED. Single-factor XS signals largely exhausted after 307 hypotheses.
- Next: Shift focus to: portfolio optimization, alternative assets, time-series strategies, or options strategies.
- Questions added: none
- Self-modifications: Archived session 149. (session 159)

### Session 2026-04-07 review+deploy+research (session 160)
- Goal: Review + Deploy + Research — MTM update, 24 time-series strategy backtests, H-324 deployment
- Focus: Paper trade MTM (no new daily bar, BTC ~$68,200), H-308 through H-331 backtests (24 TS strategies)
- Done: 41 runners (40→41). **H-324 CONFIRMED** (ADX-filtered TSMOM, WF 4/5 mean 0.557). 23 REJECTED. Key: TS momentum is regime-dependent; ADX filter is the key. Hourly signals don't survive fees. 331 total hypotheses.
- Next: Options strategies beyond strangles. Monitor H-021 (-2.47%) and H-183 (-2.43%).
- Questions added: none
- Self-modifications: H-324 runner created. Archived session 150. (session 160)

### Session 2026-04-07 review+deploy+research (session 161)
- Goal: Review + Deploy + Research — MTM update, 10 novel 4h-microstructure backtests, H-332/H-336 deployment
- Focus: Paper trade MTM (no new daily bar, BTC ~$69,833), H-332 through H-341 backtests
- Done: 43 runners (41→43). **4/10 CONFIRMED** (best hit rate!): H-332 Bar Consistency (WF 6/6), H-333 Smart Vol Return (WF 6/6), H-336 Volume Surprise (WF 6/6, corr 0.003), H-338 VW Pressure (WF 6/6). 4h microstructure is a rich signal source. 341 total hypotheses.
- Next: Options strategies. Portfolio optimization. Monitor H-021/H-183.
- Questions added: none
- Self-modifications: H-332/H-336 deployed. Archived session 151. (session 161)

### Session 2026-04-08 review+deploy+research (session 162)
- Goal: Review + Deploy + Research — H-333/H-338 deployment, 8 hourly-microstructure backtests, H-342/H-343 deployment
- Focus: Paper trade MTM (BTC $71,704), H-342 through H-349 backtests
- Done: 47 runners (43→47). **H-342 CONFIRMED** (VP synchronicity, WF 5/6, corr 0.004 H-076). **H-343 CONFIRMED** (momentum decay, WF 6/6 mean **4.163** — best ever). 349 total hypotheses.
- Next: Options strategies. Portfolio optimization. Monitor H-063 (-3.81%).
- Questions added: none
- Self-modifications: H-333/H-338/H-342/H-343 deployed. Archived session 152. (session 162)

### Session 2026-04-08 review+deploy+research (session 163)
- Goal: Review + Deploy + Research — fixed partial Apr 7 bar, 8 microstructure backtests, H-351/H-353/H-355 deployment
- Focus: Paper trade MTM (BTC $71,590), H-350 through H-357 backtests
- Done: 50 runners (47→50). **3/8 CONFIRMED**: H-351 Vol Skew (WF 5/6), H-353 Vol Persistence (WF 5/6 mean 2.526), H-355 Entropy (corr 0.079). All mutually low-corr. 357 total hypotheses.
- Next: Options strategies. Monitor H-063 (-4.65%, expires Apr 10).
- Questions added: none
- Self-modifications: H-351/H-353/H-355 deployed. Archived session 153. (session 163)

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
