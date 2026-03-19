# MEMORY.md — Session Log & State Index

## Current State
- **Paper trading (5+1+2+1+1 strategies):** H-009 (-2.35%) + H-011 (OUT, 0%) + H-012 (+2.15%) + H-019 (+0.09%) + H-021 (+0.47%) — portfolio $50,037 (+0.07%). H-024 (+0.03%) comparison. H-031 (-0.20%) + H-032 (0%) + H-039 (flat) independent. H-037 (Polymarket, manual).
- **H-024 vs H-019**: H-019 +0.09% vs H-024 +0.03% — gap narrowing.
- **5-strat portfolio**: Sharpe 2.10, +31.6%, 12.9% DD (target allocation 10/40/10/15/25)
- **BTC at ~$69,322**. H-009 flip to SHORT tonight (00:00 UTC Mar 20) confirmed.
- **42 total tested, 34 rejected.** 9 in paper trade + 1 comparison + 1 manual (Polymarket). Confirmed standalone: H-030, H-038 (weak), H-042 (weak, redundant with H-012).
- **Last session:** 2026-03-19 research (session 41) — H-041 REJECTED, H-042 CONFIRMED standalone (weak)
- **H-039 BREAKTHROUGH**: Day-of-week seasonality — **best WF in project** (6/6, mean Sharpe 2.46). Long Wed, short Thu on BTC. Deployed paper trade.
- **Funding:** Rolling-7 at -1.4% ann. H-011 re-entry ~Mar 22-23.
- **AUTOMATED:** Paper trades now run independently via cron (hourly). `scripts/run_all_paper_trades.py` (9 runners).
- **Next action:** Monitor. H-009 flip tonight. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. H-039 first trade Mar 24.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log

### Session 2026-03-15 (bootstrap)
- Goal: System — project initialization
- Focus: Create project structure, CLAUDE.md, scaffolding
- Done: CLAUDE.md, MEMORY.md, memory files, questions file, directory structure created
- Next: Research session — survey best-fit strategies for Bybit crypto (trend following, mean reversion, carry)
- Questions added: Q-001
- Self-modifications: none (initial setup)

### Session 2026-03-15 research
- Goal: Research — survey strategies, build infrastructure
- Focus: Data analysis of BTC/ETH/SOL 2yr, strategy hypothesis design
- Done: Built lib/data_fetch.py, lib/metrics.py, lib/backtest.py. Fetched 2yr 1h data for BTC/ETH/SOL. Analyzed market characteristics. Created 4 hypotheses: H-001 EMA trend, H-002 BB mean reversion, H-003 cross-asset momentum, H-004 vol breakout. Processed Q-001 user answers (capital $10k-$100k, fully autonomous).
- Next: Backtest H-002 (BB mean reversion) and H-003 (cross-asset momentum) — highest priority given bearish/choppy market
- Questions added: none
- Self-modifications: none

### Session 2026-03-16 backtest (session 1)
- Goal: Backtest — implement and run H-002 (BB mean reversion) and H-003 (cross-asset momentum)
- Focus: Strategy implementation, parameter sweep backtests on 2yr BTC/ETH/SOL 1h data
- Done: Implemented H-002 (8 param sets) and H-003 (6 param sets). H-002 REJECTED: all negative returns, best Sharpe -0.56. Long-only spot fails in bear market. H-003 REJECTED: best Sharpe 0.33, 3.9% annual, 38.9% DD. Crypto assets too correlated. Added H-005 (funding rate arb) and H-006 (adaptive mean reversion with regime filter + long/short).
- Next: Backtest H-004 (vol breakout) and H-006 (adaptive mean reversion with regime filter) — both use futures long/short which should fare better
- Questions added: none
- Self-modifications: none

### Session 2026-03-16 backtest (session 2)
- Goal: Backtest — H-004 (vol breakout), H-006 (adaptive MR), H-007 (pairs), H-005 (funding arb), daily trend following
- Focus: Exhaustive strategy testing — 5 hypotheses tested, pivoted to daily timeframe and multi-asset
- Done: **H-004 REJECTED** (all negative, best Sharpe -0.62). **H-006 REJECTED** (reversal confirmation improved WR to 60% but still negative). Created and tested **H-007** BTC/ETH pairs trading — **REJECTED** (structural ETH underperformance defeats mean reversion). Tested **H-005** funding rate arb — works perfectly (Sharpe 4.7+) but returns too low (1.7-3.1% annual) — **REJECTED**. Pivoted to daily EMA crossover: BTC EMA(5/40) Sharpe 0.70, +22.5% annual. Expanded to 14 assets — created **H-008**: top-3 portfolio (SUI, BTC, XRP) achieves **Sharpe 1.03, +53.4% annual**. Fetched 1h data for 11 additional assets.
- Next: **H-008 walk-forward validation** — split train/test, confirm not overfit. Position sizing to control DD. Consider adaptive asset selection.
- Questions added: none
- Self-modifications: none

### Session 2026-03-16 analyze (session 3)
- Goal: Analyze — H-008 walk-forward validation, vol targeting, parameter robustness
- Focus: Rigorous OOS testing of multi-asset daily trend following
- Done: Built full strategy code in `strategies/daily_trend_multi_asset/`. Ran 5 validation tests: (1) Fixed 70/30 split — BTC-only OOS Sharpe 0.94, top-3 OOS Sharpe 0.94; (2) Rolling walk-forward — **FAILS** (Sharpe -0.84, -0.59) due to altcoin regime shifts; (3) Param robustness — 15/15 positive Sharpe (0.50–0.86); (4) Vol targeting — controls DD but reduces returns proportionally; (5) BTC-only VT 20% → +11.8%, 12.9% DD. Created H-009 (BTC-only paper trade candidate) and H-010 (multi-strategy portfolio research). Math: need Sharpe ≥ 2.0 for 20% return at ≤10% DD.
- Next: **H-009 paper trade implementation** (BTC daily EMA with vol targeting). **H-010 research** — explore higher-Sharpe strategies: options vol selling, basis/carry trades, order flow microstructure.
- Questions added: none
- Self-modifications: none

### Session 2026-03-16 paper trade (session 4)
- Goal: Paper Trade + Research — deploy H-009 and research H-010
- Focus: Paper trade runners for H-009 and H-011, multi-strategy portfolio research
- Done: Built and deployed **H-009 paper trade runner** (BTC daily EMA + VT 20%). Opened LONG 0.055 BTC @ $73,524 (0.40x). Ran **H-010 multi-strategy research**: tested 5 tracks — leveraged funding arb (best: 5x → +38.2%, Sharpe 24.89), basis trade (~7% = same as funding), weekly momentum (Sharpe 0.63, too much DD), daily MR (all negative). **Key finding**: H-009 + funding arb at 5x are uncorrelated (r=0.037). Portfolio 30/70 → Sharpe 2.43, +34%, 7.2% DD. Created **H-011** (leveraged funding rate arb) and deployed paper trade runner. Walk-forward validated: OOS 5x → +25.4%, 0.14% DD.
- Next: **Monitor paper trades** (both H-009 and H-011 each session). **Research options vol selling** as potential third portfolio leg. Watch funding rate trends.
- Questions added: none
- Self-modifications: none

### Session 2026-03-16 research (session 5)
- Goal: Research — find third portfolio leg to diversify beyond H-009 + H-011
- Focus: Tested 3 tracks: cross-sectional momentum (14 assets), equal-weight all-asset trend, BTC calendar patterns
- Done: **H-012 CONFIRMED** — cross-sectional momentum (60d lookback, 5d rebalance, top/bottom 4). IS Sharpe 1.11, rolling OOS Sharpe 0.84 (+27.5%, 20.6% DD). 45/45 params positive (100%). Fee robust to 5x. Correlation with H-009: 0.015, with H-011: -0.050. 3-strategy portfolio (20/60/20): **Sharpe 2.78, +40.1%, 10.1% DD** (up from 2.43/34%/7.2%). EW all-asset trend rejected (IS Sharpe 0.43). Calendar patterns rejected (no significant effects).
- Next: **Implement H-012 paper trade runner**. Monitor H-009 and H-011 paper trades.
- Questions added: none
- Self-modifications: none

### Session 2026-03-16 paper trade (session 6)
- Goal: Paper Trade — deploy H-012 cross-sectional momentum, monitor H-009 + H-011
- Focus: Implement H-012 paper trade runner and execute initial positions
- Done: Built `paper_trades/h012_xsmom/runner.py` — market-neutral XSMom (60d lookback, 5d rebal, top/bottom 4). Initial rebalance: LONG BTC/NEAR/ATOM/AVAX, SHORT SOL/SUI/ARB/OP. Equity $9,976 after entry fees. H-009: LONG BTC +$24 (equity $10,020). H-011: OUT, no new settlements. **All 3 portfolio strategies now in paper trade.**
- Next: Monitor all 3 paper trades every session. H-012 next rebal 2026-03-21. Consider 4th strategy leg if needed.
- Questions added: none
- Self-modifications: none

### Session 2026-03-17 review (session 7)
- Goal: Review — monitor paper trades, analyze funding rate risk, build portfolio tooling
- Focus: Paper trade day 1 review + H-011 funding rate viability analysis
- Done: Ran all 3 paper trade runners (no new daily bars yet). Portfolio at $30,007 (+0.02%). Deep funding rate analysis: rolling-27 negative since 2026-03-07, Q1 2026 only 1.6% ann, tested filter windows 9-54 — no window rescues recent performance (best 180d: window 36 → +12.3% ann at 5x). Built `scripts/portfolio_monitor.py` with live mark-to-market pricing. Added Risk Watch section to state.md.
- Next: Continue monitoring. If funding stays negative past 2026-03-21, begin researching H-011 replacement (options vol selling, basis trade variants, or higher H-009/H-012 allocation). H-012 rebalances 2026-03-21.
- Questions added: none
- Self-modifications: Added portfolio_monitor.py to infrastructure

### Session 2026-03-17 research (session 8)
- Goal: Research — H-013 multi-asset funding arb + dynamic allocation to address H-011 risk
- Focus: Can we fix H-011's low-funding problem via multi-asset diversification or dynamic reallocation?
- Done: Fetched 2yr funding rates for 14 assets. **H-013 REJECTED**: all crypto funding rates correlated (r=0.49 with BTC), multi-asset diversification doesn't help in low-funding regimes, fees kill top-N rotation. Dynamic allocation also rejected: static 20/60/20 outperforms all dynamic variants (Sharpe 2.14 vs 1.42 recent 180d). Key insight: H-011 OUT = auto-derisking (60% idle reduces vol). Portfolio is self-regulating. Portfolio at $30,027 (+0.09%): H-009 $10,059 (+0.59%), H-011 $10,000 (0%), H-012 $9,968 (-0.32%).
- Next: Monitor paper trades. H-012 rebalances 2026-03-21. Research new strategy types (options, orderflow) only if portfolio Sharpe drops below 1.0.
- Questions added: none
- Self-modifications: none

### Session 2026-03-17 review (session 9)
- Goal: Review — monitor all 3 paper trades, update mark-to-market
- Focus: Run paper trade runners, check funding rate recovery
- Done: Ran all 3 runners. Portfolio $30,134 (+0.45%): H-009 $10,097 (+0.97%, BTC $75,358 LONG), H-011 $10,000 (OUT, rolling-27 -2.2% ann), H-012 $10,038 (+0.38%, longs recovered). Funding showing recovery — last settlement +10.2% ann, 3 of 5 recent positive. H-012 next rebal 2026-03-21.
- Next: Continue monitoring. Watch for H-011 re-entry as funding rates recover.
- Questions added: none
- Self-modifications: none

### Session 2026-03-17 review (session 10)
- Goal: Review — monitor all 3 paper trades, check funding recovery
- Focus: Run runners, funding rate analysis
- Done: No new daily bars or funding settlements. Portfolio $30,098 (+0.33%): H-009 $10,090 (+0.90%, BTC $75,231), H-011 $10,000 (OUT), H-012 $10,009 (+0.09%, shorts OP/ARB dragging). Funding recovery building: last 5 avg +4.0% ann. Negative Mar 12-14 rates roll out of 27-window in ~4-5 days — H-011 may re-enter ~Mar 21-22.
- Next: Continue monitoring. H-012 rebal + possible H-011 re-entry both ~2026-03-21.
- Questions added: none
- Self-modifications: none

### Session 2026-03-17 review (session 11)
- Goal: Review — monitor paper trades, handle Q-002, clean up CLAUDE.md
- Focus: Run all 3 paper trade runners, process user answer
- Done: Portfolio $30,086 (+0.29%): H-009 $10,030 (+0.30%, BTC pulled back to $74,145), H-011 $10,000 (OUT, no new settlements), H-012 $10,056 (+0.56%, shorts SUI/SOL/ARB now profitable). BTC -1.4% pullback reduced H-009 gains but H-012 benefited from short-side momentum. Q-002 resolved (sports text was wrong project). Cleaned CLAUDE.md.
- Next: Continue monitoring. H-012 rebal 2026-03-21. H-011 potential re-entry ~Mar 21-22.
- Questions added: none
- Self-modifications: Removed erroneous sports betting text from CLAUDE.md

### Session 2026-03-17 review (session 12)
- Goal: Review — monitor paper trades, funding rate re-entry projection
- Focus: Run all 3 runners, detailed funding rate analysis with settlement-by-settlement projection
- Done: Portfolio $30,080 (+0.27%): H-009 $10,029 (+0.29%, BTC $74,128 stable), H-011 $10,000 (OUT), H-012 $10,058 (+0.58%, SUI short +$63 best). Detailed funding analysis: last settlement +10.2% ann, recent 5 avg +4.0% ann (recovery continuing). Projected H-011 re-entry **2026-03-20 00:00 UTC** — earlier than previous Mar 21-22 estimate, driven by large Mar 11 negative (-0.000107) dropping out of rolling-27 window.
- Next: Monitor paper trades. Watch H-011 re-entry ~Mar 20. H-012 rebal 2026-03-21.
- Questions added: none
- Self-modifications: none

### Session 2026-03-17 review (session 13)
- Goal: Review — monitor paper trades, fetch new funding settlements
- Focus: Run all 3 runners, update funding rate data (+3 new settlements)
- Done: Portfolio $30,103 (+0.34%): H-009 $10,032 (+0.32%, BTC $74,188), H-011 $10,000 (OUT), H-012 $10,071 (+0.71%, NEAR/SUI +$64 each). Fetched 3 new funding settlements (latest +4.8% ann). Rolling-27 improved to -1.87% ann (from -2.2%). H-011 re-entry confirmed 2026-03-20 00:00 UTC.
- Next: Monitor paper trades. H-011 re-entry ~Mar 20. H-012 rebal 2026-03-21.
- Questions added: none
- Self-modifications: none

### Session 2026-03-17 research (session 14)
- Goal: Research — anti-martingale strategy (user suggestion) + alternative strategies
- Focus: H-014 anti-martingale backtest + walk-forward, H-015 RSI MR, H-016 BB squeeze, H-017 MTF momentum
- Done: Ran paper trade runners (no new bars). **H-014 REJECTED**: 88% IS positive but walk-forward fails (1/4 folds, mean OOS -1.12), corr 0.42 with H-009. **H-015 REJECTED**: 0/4 OOS folds, interesting -0.73 corr with H-009 but no edge. **H-016 REJECTED**: overfit (18 trades). **H-017 REJECTED**: 0.89 corr with H-009. Portfolio stable at +0.34%. Acted on user suggestion (anti-martingale), removed from CLAUDE.md.
- Next: Monitor paper trades. H-011 re-entry Mar 20. H-012 rebal Mar 21. Future research: sub-daily timeframes, on-chain data, or orderbook microstructure signals.
- Questions added: none
- Self-modifications: Removed user suggestion from CLAUDE.md after acting on it

### Session 2026-03-17 review (session 15)
- Goal: Review — monitor all 3 paper trades
- Focus: Run runners, funding rate analysis, mark-to-market update
- Done: Portfolio $30,049 (+0.16%): H-009 $10,007 (+0.07%, BTC $73,733 pullback), H-011 $10,000 (OUT), H-012 $10,042 (+0.42%, SUI short +$73 leading). BTC pulled back ~$450 from last session — normal fluctuation. Funding rolling-27 unchanged at -1.87% ann. H-011 re-entry still confirmed 2026-03-20 00:00 UTC. No new daily bars or funding settlements.
- Next: Continue monitoring. H-011 re-entry Mar 20. H-012 rebal Mar 21.
- Questions added: none
- Self-modifications: none

### Session 2026-03-17 review (session 16)
- Goal: Review — monitor all 3 paper trades
- Focus: Run runners, mark-to-market update
- Done: Portfolio $30,105 (+0.35%): H-009 $10,008 (+0.08%, BTC $73,742 flat), H-011 $10,000 (OUT), H-012 $10,097 (+0.97%, SUI short +$98 leading, ARB short +$32 improving). H-012 short side strong — all shorts profitable. No new daily bars or funding settlements. H-011 re-entry still projected Mar 20.
- Next: Continue monitoring. H-011 re-entry Mar 20. H-012 rebal Mar 21.
- Questions added: none
- Self-modifications: none

### Session 2026-03-17 review (session 17)
- Goal: Review — monitor all 3 paper trades
- Focus: Run runners, mark-to-market update
- Done: Portfolio $30,089 (+0.30%): H-009 $10,053 (+0.53%, BTC rallied to $74,557), H-011 $10,000 (OUT), H-012 $10,036 (+0.36%, gave back gains — OP short -$46, SOL short -$13, but SUI short +$60 still leading). BTC rally helped H-009 but hurt H-012 short-side on some positions. No new daily bars or funding settlements. Next funding at 16:00 UTC.
- Next: Continue monitoring. H-011 re-entry Mar 20. H-012 rebal Mar 21.
- Questions added: none
- Self-modifications: none

### Session 2026-03-17 review (session 18)
- Goal: Review — monitor all 3 paper trades, funding rate update
- Focus: Run runners, process new 16:00 UTC funding settlement, re-entry projection
- Done: Portfolio $30,093 (+0.31%): H-009 $10,035 (+0.35%, BTC pulled back to $74,229), H-011 $10,000 (OUT, 5 settlements), H-012 $10,058 (+0.58%, ARB short now +$11, SUI short +$65 leading). Latest funding settlement -4.2% ann (setback), rolling-27 -1.9% ann. Forward simulation confirms H-011 re-entry 2026-03-20 00:00 UTC still holds — big Mar 11 negative (-11.7%) drops out.
- Next: Continue monitoring. H-011 re-entry Mar 20. H-012 rebal Mar 21.
- Questions added: none
- Self-modifications: none

### Session 2026-03-17 review (session 19)
- Goal: Review — monitor all 3 paper trades
- Focus: Run runners, mark-to-market update
- Done: Portfolio $30,067 (+0.22%): H-009 $10,059 (+0.59%, BTC rallied to $74,682), H-011 $10,000 (OUT), H-012 $10,008 (+0.08%, short side gave back gains — SOL -$26, SUI +$42 vs +$65). BTC rally helped H-009 but hurt H-012 shorts. No new daily bars or funding settlements.
- Next: Continue monitoring. H-011 re-entry Mar 20. H-012 rebal Mar 21.
- Questions added: none
- Self-modifications: none

### Session 2026-03-18 review (session 20)
- Goal: Review — monitor all 3 paper trades
- Focus: Run runners, mark-to-market update
- Done: Portfolio $30,027 (+0.09%): H-009 $10,039 (+0.39%, BTC pulled back to $74,312), H-011 $10,000 (OUT), H-012 $9,988 (-0.12%, OP short -$70 is main drag). No new daily bars or funding settlements (next in ~1 hour). Fixed Q-002 status to ANSWERED.
- Next: Continue monitoring. H-011 re-entry Mar 20. H-012 rebal Mar 21.
- Questions added: none
- Self-modifications: none

### Session 2026-03-18 review (session 21)
- Goal: Review — monitor all 3 paper trades, funding re-entry update
- Focus: Run runners, new daily bar for H-012, funding rate analysis
- Done: Portfolio $30,037 (+0.12%): H-009 $10,012 (+0.12%, BTC $73,824 continued pullback), H-011 $10,000 (OUT, 6 settlements), H-012 $10,025 (+0.25%, recovered — SUI short +$66, new daily bar processed). Live funding rate -4.6% ann (setback). H-011 re-entry pushed to 2026-03-21 00:00 UTC (from Mar 20). Both H-011 re-entry and H-012 rebal now align on Mar 21.
- Next: Monitor paper trades. Key date: Mar 21 (H-011 re-entry + H-012 rebal).
- Questions added: none
- Self-modifications: none

### Session 2026-03-18 review (session 22)
- Goal: Review — monitor all 3 paper trades
- Focus: Run runners, mark-to-market update
- Done: Portfolio $30,097 (+0.32%): H-009 $10,041 (+0.41%, BTC recovered to $74,362), H-011 $10,000 (OUT, 6 settlements), H-012 $10,057 (+0.57%, NEAR long +$50, long side all positive). Live funding rate -2.0% ann (improved from -4.6%). No new daily bars or funding settlements. H-011 re-entry still projected Mar 21.
- Next: Monitor paper trades. Key date: Mar 21 (H-011 re-entry + H-012 rebal).
- Questions added: none
- Self-modifications: none

### Session 2026-03-18 review (session 23)
- Goal: Review — monitor all 3 paper trades, funding rate update
- Focus: Run runners, fetch new funding settlements, re-entry projection
- Done: Portfolio $30,110 (+0.37%): H-009 $10,032 (+0.32%, BTC $74,181 slight pullback), H-011 $10,000 (OUT, 8 settlements), H-012 $10,078 (+0.78%, SOL short now profitable +$8). Fetched 2 new funding settlements (Mar 17 16:00: -4.2% ann, Mar 18 00:00: +0.5% ann). Rolling-27 improved to -1.7% ann. Upcoming rate +3.2% ann. **H-011 re-entry moved up to 2026-03-20 16:00 UTC** (from Mar 21).
- Next: Monitor paper trades. H-011 re-entry ~Mar 20. H-012 rebal Mar 21.
- Questions added: none
- Self-modifications: none

### Session 2026-03-18 research (session 24)
- Goal: Research — explore new cross-sectional factor strategies
- Focus: H-018 (short-term reversal), H-019 (low-volatility anomaly), H-020 (funding rate dispersion)
- Done: Tested 3 new cross-sectional factors (262 total param sets). **H-018 REJECTED**: 4% positive, crypto momentum dominates — reversal doesn't work. **H-020 REJECTED**: 0% positive, funding rates too correlated cross-sectionally. **H-019 PROMISING**: 89% params positive (140 tested), Sharpe 1.17 IS, 5/8 WF folds, fee-robust (1.03 at 5x fees). Correlation: -0.27 with H-009 (excellent diversifier), 0.076 with H-012. 4-strat portfolio (15/50/15/20) → Sharpe 1.77, +24%, 11.5% DD. Vol targeting tested but doesn't help much. Paper trades: $30,081 (+0.27%).
- Next: Monitor paper trades. Continue H-019 validation (more OOS testing, regime analysis). H-011 re-entry ~Mar 20. H-012 rebal Mar 21.
- Questions added: none
- Self-modifications: Added cross-sectional factor research framework; saved user feedback memory about continued research

### Session 2026-03-18 research (session 25)
- Goal: Research — H-019 deep validation v2 + paper trade monitoring
- Focus: Per-fold WF analysis, alternative vol measures, regime filters, actual H-009 correlation, combined factors
- Done: Portfolio $30,120 (+0.40%): H-009 $10,025 (+0.25%), H-011 OUT, H-012 $10,092 (+0.92%). **H-019 CONFIRMED** after exhaustive validation (7 tests). KEY FINDINGS: (1) Failing WF folds = strong BTC uptrends (avg +31.8%). (2) Downside vol variant: 99% param robust, 7/8 WF — but standard vol better for portfolio (corr 0.076 vs 0.223 with H-012). (3) Actual H-009 correlation: -0.094 (corrected from -0.268 proxy). (4) No regime filter helps. (5) **CRITICAL**: 3-strat Sharpe with actual H-009 equity is 1.38 (not 2.78 from BTC proxy). Adding H-019 (15/50/15/20): Sharpe 1.75, +23.8%, 14.0% DD. (6) Adaptive WF: 4/6 positive, mean OOS 1.58.
- Next: Monitor paper trades. Prepare H-019 paper trade runner. H-011 re-entry ~Mar 20. H-012 rebal Mar 21.
- Questions added: none
- Self-modifications: Added h019_deep_validation_v2.py framework

### Session 2026-03-18 paper trade (session 26)
- Goal: Paper Trade — deploy H-019 low-volatility anomaly, monitor existing strategies
- Focus: Build H-019 paper trade runner, execute initial rebalance, update portfolio monitor
- Done: Built `paper_trades/h019_lowvol/runner.py` (V20_R21_N3). Initial rebalance: LONG ATOM/ARB/XRP (lowest 20d vol), SHORT DOGE/DOT/NEAR (highest vol). Equity $9,976 after fees. Updated portfolio monitor for 4-strat allocation (15/50/15/20). Portfolio $40,148 (+0.37%): H-009 $10,017 (+0.17%), H-011 $10,000 (OUT), H-012 $10,155 (+1.55%), H-019 $9,976 (-0.24%). **All 4 strategies now in paper trade.** H-012 performing best — ATOM +$67, SUI short +$73.
- Next: Monitor all 4 paper trades. H-011 re-entry ~Mar 20. H-012 rebal Mar 21. H-019 next rebal Apr 8.
- Questions added: none
- Self-modifications: Updated portfolio_monitor.py for 4-strategy layout

### Session 2026-03-18 review (session 27)
- Goal: Review — monitor all 4 paper trades, BTC selloff analysis
- Focus: Run runners, funding rate projection, EMA signal analysis
- Done: Portfolio $39,967 (-0.08%): H-009 $9,858 (-1.42%, BTC dropped to $71,017), H-011 $10,000 (OUT), H-012 $10,195 (+1.95%, short side dominating +$670), H-019 $9,914 (-0.86%). **BTC -3.9% but portfolio only -0.08% — diversification proven.** H-009 signal fragile: EMA gap 0.84%, flips SHORT below $70,579. H-011 re-entry pushed to Mar 22-23 (from Mar 20) due to negative funding from selloff. H-012 best performer — market-neutral shorts profiting from broad altcoin decline.
- Next: Watch H-009 signal closely (near flip). H-012 rebal Mar 21. H-011 re-entry ~Mar 22-23.
- Questions added: none
- Self-modifications: none

### Session 2026-03-18 research (session 28)
- Goal: Research — volume-based cross-sectional factors
- Focus: H-021 (volume momentum), H-022 (Amihud illiquidity), H-023 (price-volume confirmation)
- Done: Tested 3 new volume factors (324 total param sets). **H-021 CONFIRMED**: 90% positive, **6/6 WF folds** (best ever), mean OOS Sharpe 1.83. Corr near zero with all existing strategies. 5-strat portfolio Sharpe 2.10 (+31.6%, 12.9% DD). Only works at high-frequency rebal (3-day). **H-022 REJECTED**: 0% positive — no illiquidity premium in crypto. **H-023 REJECTED**: 93% positive but corr 0.864 with H-012 — just momentum in disguise. Portfolio $40,004 (+0.01%). Paper trades stable.
- Next: Deploy H-021 paper trade runner. Monitor all 4 paper trades. H-012 rebal Mar 21. H-011 re-entry ~Mar 22-23.
- Questions added: none
- Self-modifications: Added volume_factors_research.py and h021_deep_validation.py

### Session 2026-03-18 paper trade (session 29)
- Goal: Paper Trade — deploy H-021 volume momentum, monitor all strategies
- Focus: Build H-021 paper trade runner, execute initial rebalance, update portfolio to 5-strat
- Done: Built `paper_trades/h021_volmom/runner.py` (VS5_VL20_R3_N4, 3-day rebal). Initial rebalance: LONG DOT/LINK/XRP/DOGE (volume surge), SHORT ARB/SUI/NEAR/ATOM (volume drop). Equity $9,976 after fees. Updated portfolio monitor for 5-strategy allocation (10/40/10/15/25). Portfolio $49,904 (-0.19%): H-009 $9,877 (-1.23%), H-011 $10,000 (OUT), H-012 $10,131 (+1.31%), H-019 $9,915 (-0.85%), H-021 $9,980 (-0.20%). **All 5 strategies now in paper trade.** H-012 still best performer — short side dominating during market drop.
- Next: Monitor all 5 paper trades. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. H-009 flip risk. Continue research if pipeline empty.
- Questions added: none
- Self-modifications: Updated portfolio_monitor.py for 5-strategy layout

### Session 2026-03-18 review+research (session 30)
- Goal: Review + Research — monitor all paper trades, explore risk-based cross-sectional factors
- Focus: H-024 (beta), H-025 (skewness), H-026 (drawdown distance) + paper trade monitoring
- Done: Portfolio $49,883 (-0.23%): H-009 $9,875 (-1.25%), H-011 $10,000 (OUT), H-012 $10,142 (+1.42%), H-019 $9,927 (-0.73%), H-021 $9,939 (-0.61%). BTC $71,324 (-4.3% 24h). Tested 3 risk factors (156 param sets). **H-024 CONFIRMED**: 100% IS positive (48/48), WF 5/6 (mean 2.12), beats H-019 at every param set (12/12), portfolio Sharpe 1.80→2.33 as replacement. **H-025 REJECTED** (15% positive). **H-026 REJECTED** (97% positive but corr 0.682 with H-012 = redundant). Deployed H-024 paper trade: LONG ATOM/OP/BTC, SHORT XRP/NEAR/SUI. Updated portfolio monitor for 6-strategy tracking.
- Next: Monitor all 6 paper trades. Track H-024 vs H-019 head-to-head. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. H-009 flip risk.
- Questions added: none
- Self-modifications: Added risk_factors_research.py, h024_deep_validation.py, h024_beta paper trade runner. Updated portfolio_monitor.py for 6-strategy tracking.

### Session 2026-03-18 review+research (session 31)
- Goal: Review + Research — monitor paper trades, explore 1h-frequency cross-sectional factors
- Focus: H-027 (lead-lag), H-028 (volume trend/OI proxy), H-029 (hourly momentum)
- Done: Portfolio $49,927 (-0.15%): H-009 $9,863 (-1.37%), H-011 $10,000 (OUT), H-012 $10,147 (+1.47%), H-019 $9,974 (-0.26%), H-021 $9,943 (-0.57%). BTC $71,250 stable. Tested 3 hourly-frequency factors (369 param sets). **H-027 REJECTED** (1% positive, lead-lag not exploitable). **H-028 REJECTED** (6% positive, overfitting). **H-029 REJECTED** (336h lookback works but corr 0.484 with H-012 — redundant). No new daily bars during session. 29 hypotheses tested total, 23 rejected.
- Next: Monitor all 6 paper trades. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. H-009 flip risk. Explore new research directions: options, on-chain data, ML/ensemble methods.
- Questions added: none
- Self-modifications: Added leadlag_research/ framework.

### Session 2026-03-19 review+research (session 32)
- Goal: Review + Research — monitor paper trades, explore composite multi-factor and size factor
- Focus: H-030 (composite multi-factor), H-031 (size/dollar volume)
- Done: Portfolio $49,948 (-0.10%): H-009 $9,862 (-1.38%), H-011 $10,000 (OUT), H-012 $10,122 (+1.22%), H-019 $9,979 (-0.21%), H-021 $9,982 (-0.18%). Tested 2 new hypotheses (468+ param sets). **H-030 CONFIRMED standalone** (100% IS positive, WF 5/6 mean 1.71-2.01, fee-robust) but **REJECTED for portfolio** — portfolio of 3 individual strategies (Sharpe 2.26) beats single composite (Sharpe 2.14). **H-031 CONFIRMED standalone** (100% long_large positive, WF 4/4 mean 1.47-1.78, extremely fee-robust) but **REJECTED for portfolio** — corr 0.486 with H-012 (momentum), redundant. 31 hypotheses tested, 25 rejected.
- Next: Monitor all 6 paper trades. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. H-009 flip risk. Cross-sectional factor space exhausted — future research needs new data sources (options, on-chain) or fundamentally different approaches.
- Questions added: none
- Self-modifications: Added composite_factor_research.py + composite_deep_validation.py

### Session 2026-03-19 review+system (session 33)
- Goal: Review + System — handle user feedback, monitor paper trades, reclassify strategies
- Focus: User feedback on rejection policy, paper trade monitoring, test set size documentation
- Done: Portfolio $49,957 (-0.09%): H-009 $9,862 (-1.38%), H-011 $10,000 (OUT), H-012 $10,150 (+1.50%), H-019 $10,012 (+0.12%), H-021 $9,931 (-0.69%). H-024 $10,002 (+0.02%). **Handled user feedback**: reclassified H-030 and H-031 from REJECTED to CONFIRMED (standalone) — both have excellent returns (H-030: Sharpe 2.05, +101% ann; H-031: Sharpe 1.58, +78.5% ann). Added test set size info (data period, OOS days, trade counts) to all CONFIRMED/LIVE hypotheses. Saved feedback memory. H-019 now slightly ahead of H-024. H-021 worsened to -0.69%.
- Next: Monitor all 6 paper trades. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. H-009 flip risk.
- Questions added: none
- Self-modifications: Removed handled user input from CLAUDE.md. Added feedback memory. Added "Confirmed Standalone" section to state.md.

### Session 2026-03-19 review+research (session 34)
- Goal: Review + Research — monitor paper trades, explore pairwise cointegration stat arb
- Focus: Paper trade monitoring + H-032 pairwise cointegration statistical arbitrage
- Done: Portfolio $49,961 (-0.08%): H-009 $9,851 (-1.49%, BTC $70,879 ~$300 from flip), H-011 $10,000 (OUT), H-012 $10,123 (+1.23%), H-019 $10,017 (+0.17%), H-021 $9,972 (-0.28% improved). H-024 $9,960 (-0.40%, H-019 widening lead). **H-032 CONFIRMED (standalone, weak)**: 3/91 pairs cointegrated. OOS 8-pair portfolio Sharpe 1.33 (+9.5%, 5.8% DD). Only 2/12 pairs pass both WF and split. Corr with H-012: -0.31. Works best in BTC downtrends. 32 hypotheses tested.
- Next: Monitor all 6 paper trades. H-009 flip IMMINENT. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23.
- Questions added: none
- Self-modifications: Added strategies/pairs_research/ framework

### Session 2026-03-19 review+system (session 35)
- Goal: Review + System — answer user questions, automate paper trades
- Focus: Paper trade automation + H-030/H-031/H-032 status
- Done: Portfolio $50,010 (+0.02%): H-009 $9,825 (-1.75%, BTC $70,410), H-011 $10,000 (OUT), H-012 $10,133 (+1.33%), H-019 $10,026 (+0.26%), H-021 $10,026 (+0.26% recovered). H-024 $9,933 (-0.67%). **Automated paper trades**: built `scripts/run_all_paper_trades.py` orchestrator, added hourly cron job (30 * * * *) independent of Claude sessions. Answered user: H-030/H-031/H-032 are NOT in paper trading (confirmed standalone only). Added Q-003 asking about deploying H-031/H-032. Removed user input from CLAUDE.md.
- Next: Monitor. Await Q-003 answer. H-009 flip IMMINENT. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23.
- Questions added: Q-003 (deploy H-031/H-032?)
- Self-modifications: Added run_all_paper_trades.py orchestrator, added cron automation, removed user input from CLAUDE.md

### Session 2026-03-19 review+paper trade (session 36)
- Goal: Review + Paper Trade — deploy H-031 and H-032 per user request (Q-003)
- Focus: Build and deploy H-031 (size factor) and H-032 (cointegration pairs) paper trade runners
- Done: Portfolio $50,029 (+0.06%): H-009 $9,806 (-1.94%, BTC ~$70,069), H-011 $10,000 (OUT), H-012 $10,148 (+1.48%), H-019 $10,006 (+0.06%), H-021 $10,068 (+0.68%). H-024 $9,948 (-0.52%). **Deployed H-031**: Size factor (W30_R5_N5, long large-cap, short small-cap). Initial: LONG BTC/ETH/SOL/XRP/DOGE, SHORT LINK/DOT/OP/ARB/ATOM. $9,976 after fees. **Deployed H-032**: 8-pair cointegration portfolio (DOT/ATOM, DOGE/LINK, DOGE/ADA, DOT/OP, SOL/DOGE, AVAX/DOT, NEAR/OP, ARB/ATOM). All flat — waiting for z-score entry signals. Updated orchestrator and portfolio monitor to include both. Acted on Q-003 (user said "yes, deploy them").
- Next: Monitor all 8 paper trades. H-009 flip IMMINENT. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. Continue research.
- Questions added: none
- Self-modifications: Added H-031 + H-032 paper trade runners. Updated orchestrator (8 runners) and portfolio monitor.

### Session 2026-03-19 review+research (session 37)
- Goal: Review + Research — monitor paper trades, explore new alpha sources beyond exhausted factor space
- Focus: H-033 (idiosyncratic momentum), H-034 (funding timing), H-035 (momentum vol timing), H-036 (intraday seasonality)
- Done: Portfolio $50,002 (+0.00%): H-009 $9,811 (-1.89%), H-011 $10,000 (OUT), H-012 $10,122 (+1.22%), H-019 $9,974 (-0.26%), H-021 $10,095 (+0.95%). H-024 $9,864 (-1.36%, H-019 widening lead). H-031 $10,021 (+0.21%, positive). H-032 $10,000 (flat). **H-033 REJECTED**: 99% IS positive but corr 0.832 with H-012 (redundant), WF 1/4. **H-034 REJECTED**: 49% positive = noise, only 5 trades. **H-035 REJECTED** (as standalone): enhancement to H-012 (Sharpe 1.12→1.61, DD 30.6%→21.3%) but WF 3/4 weaker than base. **H-036 REJECTED**: Real hour-of-day patterns (train/test corr 0.44) but Sharpe 0.30 max — untradeable. 36 hypotheses tested total.
- Next: Monitor paper trades. H-009 flip IMMINENT. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. Research largely exhausted — future alpha needs new data sources (options, on-chain, order book).
- Questions added: none
- Self-modifications: Added h033_h034_research.py and h035_h036_research.py

### Session 2026-03-19 review+research (session 38)
- Goal: Review + Research — monitor paper trades, explore H-037 Polymarket hourly BTC direction (user suggestion)
- Focus: H-037 Polymarket 1hr BTC UP/DOWN using H-036 intraday seasonality patterns
- Done: Portfolio $49,965 (-0.07%): H-009 $9,760 (-2.40%, BTC $69,250 — flip on next close), H-011 $10,000 (OUT), H-012 $10,154 (+1.54%), H-019 $9,981 (-0.19%), H-021 $10,070 (+0.70%). H-024 $9,953 (-0.47%). H-031 $9,963 (-0.37%). H-032 $10,000 (flat). **H-037 CONFIRMED for paper trade**: analyzed BTC green/red probability per hour — 5 statistically significant hours (p<0.05): 17:00 UP (56.3%), 21:00 UP (54.9%), 22:00 UP (54.0%), 23:00 DOWN (54.1%), 13:00 DOWN (53.8%). Train/test prob corr 0.52. OOS sim: 53.7% WR, 10/13 months profitable. **Edge only exists if Polymarket misprices** — requires manual paper trade. Built tracker tool.
- Next: Monitor paper trades. H-009 flip on next daily close. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. User to start H-037 Polymarket paper trading.
- Questions added: Q-004 (self-answering — handled user CLAUDE.md question about H-036+Polymarket)
- Self-modifications: Added strategies/polymarket_research/h037_polymarket_hourly.py, paper_trades/h037_polymarket/tracker.py. Removed user question from CLAUDE.md.

### Session 2026-03-19 review+research (session 39)
- Goal: Review + Research — monitor paper trades, explore ML factor combination (H-038)
- Focus: H-038 ML (Ridge/RF/GB) combination of cross-sectional factor signals
- Done: Portfolio $50,010 (+0.02%): H-009 $9,779 (-2.21%, BTC $69,575 — flip on next close), H-011 $10,000 (OUT), H-012 $10,181 (+1.81%), H-019 $9,991 (-0.09%), H-021 $10,058 (+0.58%). H-024 $9,913 (-0.87%, H-019 widening lead). H-031 $10,004 (+0.04%). H-032 $10,000 (flat). Cron automation verified working (8/8 runners OK). **H-038 CONFIRMED standalone (weak)**: Ridge alpha=100 on 7 factor z-scores → OOS Sharpe 1.43, +26.2%, 9.6% DD, fee-robust (0.97 at 5x). 96% params positive. BUT train window sensitive: 180d=-0.10, 270d=-0.17, 365d=1.43, 450d=0.46. Only 2/3 WF folds positive. Not deploying. Key finding: beta most stable feature, reversal contributes in combination despite failing alone.
- Next: Monitor paper trades. H-009 flip on next daily close (00:00 UTC Mar 20). H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. Research approaching exhaustion — 38 hypotheses tested.
- Questions added: none
- Self-modifications: Added strategies/ml_research/ (h038_ml_factor_combo.py, h038_deep_validation.py). Installed scikit-learn.

### Session 2026-03-19 review+research (session 40)
- Goal: Review + Research — monitor paper trades, explore day-of-week seasonality + vol regime timing
- Focus: H-039 (DOW seasonality), H-040 (vol regime factor timing)
- Done: Portfolio $50,037 (+0.07%): H-009 $9,765 (-2.35%, BTC $69,322 — flip tonight confirmed), H-011 $10,000 (OUT), H-012 $10,215 (+2.15%), H-019 $10,009 (+0.09%), H-021 $10,047 (+0.47%). H-024 $10,003 (+0.03%, gap narrowing). **H-039 CONFIRMED — BEST WF IN PROJECT**: Fixed Wed long / Thu short on BTC. WF **6/6** positive (mean Sharpe **2.46**). EW 14-asset WF 6/6 (mean 1.99). ALL 14 assets positive. Corr ~0 with everything. Fee-robust at maker rates. Deployed paper trade. **H-040 REJECTED**: Vol regime timing adds nothing OOS (-0.06 to -0.31 Sharpe improvement). 40 hypotheses tested.
- Next: Monitor. H-009 flip tonight. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. H-039 first trade Mar 24 (Tue close).
- Questions added: none
- Self-modifications: Added strategies/dow_research/, paper_trades/h039_dow_seasonality/. Updated orchestrator (9 runners) and portfolio monitor.

### Session 2026-03-19 research (session 41)
- Goal: Research — H-041 BTC Dominance Rotation + H-042 Cross-Sectional Return Dispersion Trading
- Focus: Two fundamentally new signal types: market structure rotation and dispersion conditioning
- Done: **H-041 REJECTED** — BTC dominance rotation is pure look-ahead bias. Without lag: IS Sharpe 3.96, WF 6/6 (fake). With correct 1-day signal lag: 1/16 params positive (6.2%), WF 3/6, best IS Sharpe 0.24. Root cause: BTC dominance mean-reverts next day. **H-042 CONFIRMED standalone (weak)** — core signal is short-term XSMom (20d lookback, 21d rebal, N=4). IS Sharpe 1.166, 77.1% positive, WF 4/6, mean OOS 0.548, fee-robust (1.082 at 2x fees). Dispersion filter does NOT add alpha (improves only 10.2% of params, hurts H-012 overlay). Corr with H-012: 0.686 (high — partially redundant). Not adding to portfolio. 42 hypotheses tested total.
- Next: Monitor paper trades. H-009 flip tonight. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. H-039 first trade Mar 24. Research continues needed — 34 rejected, need new data sources.
- Questions added: none
- Self-modifications: Added strategies/dominance_dispersion_research/ (h041_h042_research.py, results_summary.txt).
