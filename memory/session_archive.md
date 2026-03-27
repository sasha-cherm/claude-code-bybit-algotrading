# Session Archive (Sessions bootstrap through 86)
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

### Session 2026-03-19 review+research (session 41)
- Goal: Review + Research — monitor paper trades, explore BTC dominance rotation + dispersion trading
- Focus: H-041 (BTC dominance rotation), H-042 (cross-sectional return dispersion)
- Done: Portfolio $50,065 (+0.13%): H-009 $9,798 (-2.02%, BTC $69,920), H-011 $10,000 (OUT), H-012 $10,198 (+1.98%), H-019 $9,978 (-0.22%), H-021 $10,091 (+0.91%). H-024 $9,948 (-0.52%, H-019 leading). **H-041 REJECTED**: BTC dominance rotation is pure look-ahead bias. Correctly lagged: 1/16 params positive (6.2%), WF 3/6. Dominance mean-reverts next day. **H-042 CONFIRMED standalone (weak)**: short-term XSMom (20d). IS Sharpe 1.17, WF 4/6. Dispersion filter does NOT add alpha. Corr 0.686 with H-012 — redundant for portfolio. 42 hypotheses tested.
- Next: Monitor. H-009 flip tonight. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. H-039 first trade Mar 24.
- Questions added: none
- Self-modifications: Added strategies/dominance_dispersion_research/ (h041_h042_research.py, results_summary.txt).

### Session 2026-03-20 review+research (session 42)
- Goal: Review + Research — monitor paper trades, explore open interest as new data source
- Focus: H-043 (OI change as XS factor), H-044 (OI-Price divergence)
- Done: Portfolio $50,112 (+0.22%): H-009 $9,840 (-1.60%, BTC $70,685), H-011 $10,000 (OUT), H-012 $10,173 (+1.73%), H-019 $9,970 (-0.30%), H-021 $10,128 (+1.28%). H-024 $9,922 (-0.78%, H-019 leading). H-031 $10,034 (+0.34%, turned positive). Fetched 2yr daily OI for all 14 assets from Bybit V5 API. **H-043 REJECTED**: OI change alone is NOT a cross-sectional signal (34% IS positive, WF 1/5). **H-044 CONFIRMED and DEPLOYED**: OI-Price divergence (20d) — 100% IS positive (9/9), WF 4/5 (mean OOS 1.27), Sharpe 1.46, +26.3%, 13.9% DD. Fee-robust (1.15 at 5x). First strategy using genuinely new data (open interest). Corr 0.565 with H-012 — independent deployment. Initial: L SUI/OP/NEAR/SOL/ETH, S ADA/ARB/DOT/XRP/DOGE. 44 hypotheses tested.
- Next: Monitor. H-009 flip tonight. H-012 + H-021 rebal Mar 21. H-011 re-entry ~Mar 22-23. H-039 first trade Mar 24. H-044 next rebal Mar 29.
- Questions added: none
- Self-modifications: Added strategies/oi_research/, paper_trades/h044_oi_divergence/. Updated orchestrator (10 runners) and portfolio monitor. Fetched and cached OI data for 14 assets.

### Session 2026-03-20 review+research (session 43)
- Goal: Review + Research — monitor paper trades, explore OI-Volume combinations + price acceleration
- Focus: H-045 (OI-Volume confirmation/divergence), H-046 (price acceleration — second derivative of momentum)
- Done: Portfolio $49,999 (-0.00%): H-009 $9,815 (-1.85%, BTC $70,228), H-011 $10,000 (OUT), H-012 $10,091 (+0.91%), H-019 $9,937 (-0.63%), H-021 $10,157 (+1.57%). H-024 $9,872 (-1.28%, H-019 leading by wider margin). **CRITICAL BUG FOUND**: H-043/H-044 research script used periods_per_year=8760 (hourly) for daily data, inflating all Sharpe ratios by 4.9x. H-044 true IS Sharpe is 1.01 (not 1.46). Corrected. H-044 still viable (100% params positive, WF 3/4 mean OOS 1.22). **H-045 CONFIRMED standalone (weak)**: OI-Volume signals had zero-signal artifact inflating results. Robust no-clip variant W20 n=4 r=10 has IS 1.76, WF 3/4, but rebal-sensitive. Not deploying. **H-046 CONFIRMED and DEPLOYED**: Price acceleration (change in 20d momentum over 20d) — IS Sharpe 1.19, +25.1%, 17.6% DD. **WF 4/4** (mean OOS 1.13). 100% params positive (9/9). **Near-zero corr with ALL existing strategies** (max 0.179). Fee-robust (0.56 at 5x). Deployed paper trade: LONG OP/ARB/NEAR/SUI, SHORT DOGE/LINK/ADA/DOT. 46 hypotheses tested.
- Next: Monitor. H-009 flip tonight (00:30 UTC cron). H-012 + H-021 rebal Mar 21. H-046 rebal Mar 22. H-011 re-entry ~Mar 22-23. H-039 first trade Mar 24. H-044 next rebal Mar 29.
- Questions added: none
- Self-modifications: Added strategies/oi_research/h045_oi_volume_research.py, paper_trades/h046_acceleration/. Updated orchestrator (11 runners) and portfolio monitor. Fixed metrics bug in h043_oi_factor_research.py. Corrected H-044 metrics in state/hypotheses files.

### Session 2026-03-20 review+research (session 44)
- Goal: Review + Research — monitor paper trades, fix critical bug, explore new data sources (Bybit LSR, options, vol dynamics)
- Focus: H-009 flip bug fix, H-047 (vol change), H-048 (correlation change), H-049 (LSR sentiment)
- Done: Portfolio $49,947 (-0.11%): H-009 $9,789 (-2.11%, **now SHORT** at $69,909), H-011 $10,000 (OUT), H-012 $10,098 (+0.98%), H-019 $9,938 (-0.62%), H-021 $10,136 (+1.36%). H-024 $9,885 (-1.16%, H-019 leading). **CRITICAL BUG FOUND AND FIXED**: All 10 paper trade runners had incomplete daily bar bug — processing intra-day bars as complete daily closes. H-009 missed SHORT flip by ~1 day. Fixed by dropping today's incomplete bar in all runners. **H-009 manually corrected and flipped to SHORT** at Mar 19 close ($69,923). **H-047 REJECTED**: Vol change factor — 50% positive = pure noise. **H-048 REJECTED**: Correlation change factor — 50% positive = pure noise. **H-049 CONFIRMED and DEPLOYED**: LSR sentiment contrarian — Bybit long/short ratio. IS Sharpe **2.58**, 100% params positive (12/12), split-half 2.01/3.75, fee-robust (1.58 at 5x fees). 7.2% DD. **BUT only 200 days of data** (6.5 months). Corr -0.091 with H-012, **0.581 with H-046**. First non-price/volume/OI signal. Deployed: LONG BTC/ETH/LINK, SHORT ARB/SUI/OP. Also explored Bybit API: 2200 options markets (Greeks/IV available), liquidation data (not yet via ccxt). 49 hypotheses tested.
- Next: Monitor. H-012 + H-021 rebal Mar 21. H-046 rebal Mar 22. H-039 first trade Mar 24. H-049 + H-031 rebal Mar 24. H-011 re-entry ~Mar 25-26. H-044 next rebal Mar 29.
- Questions added: none
- Self-modifications: Fixed incomplete daily bar bug in all 10 runners. Added strategies/vol_dynamics_research/. Added paper_trades/h049_lsr_sentiment/. Updated orchestrator (12 runners). Cached LSR data. Explored Bybit options API.

### Session 2026-03-20 review+research (session 45)
- Goal: Review + Research — monitor paper trades, test macro signals and calendar seasonality, set up IV collector
- Focus: H-050 (inter-market macro signals), H-051 (monthly calendar seasonality), options IV data infrastructure
- Done: Portfolio $49,961 (-0.08%): unchanged from session 44 (no new daily bar). BTC $70,477. **H-050 REJECTED**: Macro signals (SPY/GLD/VIX/DXY/TNX) have zero lagged predictive power for crypto. 50 param sets tested, exactly 50% positive = random noise. Same-day SPY-BTC correlation (+0.37) is real but info priced in by close. VIX regime filters also useless. **H-051 REJECTED**: Monthly/DOM calendar seasonality — train/test DOM correlation -0.13 (negative = no persistence). WF 3/6, mean OOS -0.97. Only DOW effects (H-039) survive. **IV collector deployed**: Daily cron (01:00 UTC) captures Bybit options IV surface for BTC/ETH/SOL/XRP/DOGE (2400 records/day). First snapshot captured. After ~60-90 days of collection, options-based signals become backtestable. 51 hypotheses tested, 40 rejected.
- Next: Monitor. H-012 + H-021 rebal Mar 21. H-046 rebal Mar 22. H-039 first trade Mar 24. H-049 + H-031 rebal Mar 24. H-011 re-entry ~Mar 25-26. H-044 next rebal Mar 29. Research: explore liquidation data, order book microstructure, or alternative data APIs (CoinGlass, Glassnode).
- Questions added: none
- Self-modifications: Added strategies/macro_research/h050_macro_signals.py. Added scripts/collect_iv_surface.py + daily cron. Installed yfinance.

### Session 2026-03-20 review+research (session 46)
- Goal: Review + Research — monitor paper trades, explore premium index and order book depth as new data sources
- Focus: H-052 (premium index cross-sectional factor), order book depth collection infrastructure
- Done: Portfolio $49,961 (-0.08%): unchanged (no new daily bar since Mar 19). BTC $70,477. **H-052 CONFIRMED and DEPLOYED**: Premium index contrarian — rank assets by perp-vs-spot premium, long most discounted (shorts aggressive), short least discounted. IS: **100% params positive** (30/30), best Sharpe 2.25. WF: **6/6 positive** for W5_R5_N4 (mean OOS 1.86), 23/24 majority positive overall (mean 1.35). Split-half: 2.18/2.95 (strong in both halves). Correlations: **-0.142 H-012** (negative!), 0.097 H-021, 0.167 H-046. Deployed paper trade: LONG ARB/ATOM/ETH/LINK, SHORT OP/DOGE/NEAR/SOL. **Order book depth collector deployed**: Daily cron at 01:30 UTC captures bid/ask imbalance at 5/10/25 levels for 14 assets. Building history for future microstructure research. 52 hypotheses tested, 40 rejected.
- Next: Monitor. H-012 + H-021 rebal Mar 21. H-046 rebal Mar 22. H-039 first trade Mar 24. H-049 + H-031 + H-052 rebal Mar 24. H-011 re-entry ~Mar 25-26. H-044 next rebal Mar 29. Research: all immediately backtestable signals explored — future alpha depends on IV surface + OB depth data collection (60-90 days).
- Questions added: none
- Self-modifications: Added strategies/premium_research/, paper_trades/h052_premium/. Added scripts/collect_orderbook_depth.py + daily cron. Updated orchestrator (13 runners). Cached premium index data.

### Session 2026-03-20 review+research (session 47)
- Goal: Review + Research — monitor paper trades, explore funding rate XS factor and liquidation data
- Focus: H-053 (funding rate cross-sectional factor), liquidation data availability
- Done: Portfolio $49,863 (-0.27%): BTC $70,302. **H-024 overtook H-019** (-0.53% vs -0.61%, gap reversed). All 14 runners OK via cron. **H-053 CONFIRMED and DEPLOYED**: Funding rate XS contrarian — rank assets by rolling 3-day avg funding rate, long lowest (shorts paying longs), short highest (crowded longs). IS 93% positive (42/45). Best W3 R10 N4: Sharpe 1.52, +32.9% ann, 22.2% DD. **WF 6/6 positive (mean OOS 2.29)** — tied for strongest WF in project. Split-half 1.31/1.91. Fee-robust (0.92 at 5x). Corr 0.004 H-012 (near zero!), 0.360 H-052 (moderate), 0.480 H-049. Deployed: LONG DOT/ATOM/SOL/BTC, SHORT OP/NEAR/ARB/ADA. **Liquidation data NOT available**: Bybit has no public historical liquidation endpoint (ccxt fetchLiquidations unsupported). Would need WebSocket collector. 53 hypotheses tested, 40 rejected.
- Next: Monitor. H-012 + H-021 rebal Mar 21. H-046 rebal Mar 22. H-039 first trade Mar 24. H-049 + H-031 + H-052 rebal Mar 24. H-011 re-entry ~Mar 25-26. H-053 + H-044 rebal Mar 29. All immediately backtestable Bybit data sources now exhausted.
- Questions added: none
- Self-modifications: Added strategies/funding_xs_research/, paper_trades/h053_funding_xs/. Updated orchestrator (14 runners).

### Session 2026-03-20 research (session 48)
- Goal: Research — Multi-asset Polymarket candle direction analysis (user request)
- Focus: H-054: Analyze green/red candle probability per 1h and 4h slot for BTC, ETH, SOL, XRP, DOGE, HYPE, BNB
- Done: **H-054 CONFIRMED**. 210 total tests, **38 significant** (3.62x expected by chance). Strongest 1h patterns: **23:00 UTC RED** (7/7 assets agree, avg 44.7% green, 5 individually sig, XRP p=0.0001 survives Bonferroni), **17:00 UTC GREEN** (7/7 agree, 54.6% avg, 4 sig, BTC p=0.0006 survives Bonferroni), **21:00 GREEN** (6/7, 53.9%, 5 sig), **22:00 GREEN** (7/7, 54.0%, 3 sig). Strongest 4h: **12-16 RED** (7/7, 45.8%, 5 sig), **00-04 GREEN** (7/7, 54.0%, 4 sig). Cross-asset patterns highly correlated — bets on different assets same hour NOT independent. HYPE only 8 months data (low confidence). Results saved to strategies/polymarket_research/h054_results.json.
- Next: Paper trade H-054 manually on Polymarket (requires manual tracking like H-037). Monitor existing 14 runners.
- Questions added: none
- Self-modifications: Added strategies/polymarket_research/h054_multi_asset_hourly.py

### Session 2026-03-20 research (session 49)
- Goal: Research — Re-run H-054 per user request: independent per-asset hourly report (not cross-asset consensus)
- Focus: H-054 per-asset independent report
- Done: Created `strategies/polymarket_research/h054_per_asset_report.py`. **39 significant results** (p<0.05 + consistent train/test), **8 Bonferroni survivors**. Per-asset breakdown: BTC 4 sig hours (17:00 UP***), ETH 3 (23:00 DOWN***), SOL 5 (23:00 DOWN***), XRP 4 (23:00 DOWN***), DOGE 2, HYPE 1, BNB 5 (21:00 UP***, 22:00 UP***). 4H: SOL 12-16 DOWN***, XRP 20-24 DOWN***. Removed user input from CLAUDE.md.
- Next: Monitor existing 14 runners. H-012 + H-021 rebal Mar 21.
- Questions added: none
- Self-modifications: Added strategies/polymarket_research/h054_per_asset_report.py. Removed user input from CLAUDE.md.

### Session 2026-03-20 review+research (session 50)
- Goal: Review + Research — monitor paper trades, comprehensive portfolio optimization across all strategies
- Focus: H-055 portfolio optimization with mean-variance, risk parity, exhaustive N-strategy subsets
- Done: Portfolio $49,778 (-0.44%): H-009 $9,754 (-2.46%), H-011 $10,000 (OUT), H-012 $9,999 (-0.01%), H-019 $9,908 (-0.93%), H-021 $10,118 (+1.18%). H-024 $9,921 (-0.79%, leads H-019). H-031 $10,026 (+0.26%). H-044 $10,024 (+0.24%). **H-055 CONFIRMED**: Built full portfolio optimizer (12 strategies, 700 days). Full correlation matrix computed. Current 5-strat Sharpe 2.58 → **optimal 8-strat Sharpe 5.13** (+46.0%, 7.3% DD). Best allocation: H-009(12%)/H-011(40%)/H-021(7%)/H-031(13%)/H-039(9%)/H-046(5%)/H-052(8%)/H-053(6%). Key findings: H-012 dropped (replaced by H-031, corr 0.517, higher Sharpe), H-019 dropped (replaced by positioning signals + H-024). H-039 DOW seasonality is an excellent diversifier (corr <0.11 with everything). 55 hypotheses tested.
- Next: Monitor paper trades. H-012 + H-021 rebal Mar 21. H-046 rebal Mar 22. H-039 first trade Mar 24. Continue paper trade validation (28 days min before implementing H-055 allocation).
- Questions added: none
- Self-modifications: Added strategies/portfolio_optimization/h055_portfolio_optimizer.py.

### Session 2026-03-20 system (session 51)
- Goal: System — migrate paper trades to Bybit demo trading
- Focus: Build Bybit demo execution layer for H-055 portfolio
- Done: Built `lib/bybit_demo_client.py` (DemoTrader class, full CRUD for positions/orders/prices). Built `scripts/demo_portfolio_runner.py` (reads 7 strategy state.json files, nets positions by H-055 weights, rebalances on Bybit demo). Updated `scripts/run_all_paper_trades.py` to call demo runner after individual runners. **Placed initial 13 positions on Bybit demo**: SHORT ADA/ARB/ATOM/BTC/DOT/LINK/NEAR/OP/SUI, LONG DOGE/ETH/SOL/XRP. Account: $99,973 equity. H-011 stays cash buffer until funding signal fires.
- Next: Monitor hourly execution. Next rebal triggers as strategies update signals.
- Questions added: none
- Self-modifications: New files: lib/bybit_demo_client.py, scripts/demo_portfolio_runner.py.

### Session 2026-03-20 review (session 52)
- Goal: Review — monitor paper trades, demo account, data collection
- Focus: Full system health check and mark-to-market update
- Done: Ran all 14 paper trade runners (all OK, no new daily bar). **Demo account**: $99,956 (-0.04%), 0.29x leverage, 13 positions healthy. **Internal MTM**: H-012 -13.56%, H-019 -13.85% (momentum crash — longs entered at $74k BTC, now $70.4k). Newer positioning strats all positive: H-049 +1.94%, H-046 +1.49%, H-053 +1.37%, H-052 +1.25%, H-044 +1.18%. H-012/H-019 drawdown is within backtest expectations (OOS DD was 20.6%) and irrelevant to demo (both dropped from H-055). IV/OB depth collectors: day 1, running correctly (2,400 IV records, 14 OB snapshots).
- Next: H-012 + H-021 rebal Mar 21. H-046 rebal Mar 22. H-039 first trade Mar 24. H-011 re-entry ~Mar 25-26.
- Questions added: none
- Self-modifications: none

### Session 2026-03-20 review (session 53)
- Goal: Review — monitor paper trades, demo account health, system verification
- Focus: Full system health check, live MTM update, cron verification
- Done: Ran all 14 paper trade runners (all OK, no new daily bar since Mar 19). **Demo account**: $100,086 (+0.09%), 13 positions, short side profitable (OP +$89, NEAR +$36, ARB +$32). BTC dropped to $69,634 (-1.05% from session 52). **Live MTM**: H-021 best XS strat (+1.34%), H-049 worst (-1.01%, contrarian longs losing in selloff). H-024 still leads H-019 (-0.44% vs -0.71%). H-009 SHORT profiting ($+15 unrealized). Cron jobs verified: 81 successful hourly runs, all 14/14 OK. IV + OB depth data files confirmed (day 1).
- Next: H-012 + H-021 rebal Mar 21. H-046 rebal Mar 22. H-039 first trade Mar 24. H-011 re-entry ~Mar 25-26.
- Questions added: none
- Self-modifications: none

### Session 2026-03-20 optimize (session 54)
- Goal: Optimize — stress test H-055 portfolio, regime analysis, adaptive allocation
- Focus: Tail risk, correlation breakdown, regime performance, regime-adaptive weights, Monte Carlo, strategy contribution
- Done: Demo $100,029 (+0.03%), all 14 runners OK (no new daily bar). Built `h055_stress_test.py`. **Key findings**: (1) 95% VaR -0.56%/day, max DD -7.25% (recovered 33 days). (2) Correlations DON'T break during stress (0.041 vs 0.044 full). Rolling 30d corr NEVER >0.30. (3) Positive ALL regimes: uptrend Sharpe 7.46, downtrend 2.89, deep DD 4.71. (4) 88% months positive. (5) Static weights near-optimal — adaptive adds no value. (6) Monte Carlo: P(loss)=0%, P(>20%)=96.5%, P(DD>10%)=0.4%. (7) H-011 most critical; H-009 slightly negative marginal. H-046 only weakness in downtrend.
- Next: H-012 + H-021 rebal Mar 21. H-046 rebal Mar 22. H-039 first trade Mar 24. H-011 re-entry ~Mar 25-26.
- Questions added: none
- Self-modifications: Added h055_stress_test.py. Updated state.md with stress test findings.

### Session 2026-03-20 review (session 55)
- Goal: Review — monitor paper trades, demo account, funding rate check
- Focus: System health check, H-011 funding rate re-entry timeline
- Done: All 14/14 runners OK (no new daily bar since Mar 19). **Demo**: $100,082 (+0.08%), 13 positions, short side profitable (OP +$79, NEAR +$55, ADA +$41). Internal: $139,705 (-0.21%). BTC $69,779. Cron verified (hourly runs OK). IV+OB collectors day 1. **KEY FINDING: H-011 re-entry IMMINENT** — R27 at -0.007% (was -2.75% ann last check). Last 5 funding settlements all positive (0.0014%-0.0053%). Estimated re-entry ~Mar 21 11:00 UTC (~16h). Previous estimate was Mar 25-26. This is the most important event for portfolio returns (40% weight, Sharpe ~18 backtest).
- Next: **H-011 re-entry ~Mar 21 (watch closely)**. H-012 + H-021 rebal Mar 21. H-046 rebal Mar 22. H-039 first trade Mar 24.
- Questions added: none
- Self-modifications: none

### Session 2026-03-20 review (session 56)
- Goal: Review — pre-bar-close check, H-011 funding rate confirmation
- Focus: All paper trades + demo health, funding rate R27 deep dive
- Done: All 14/14 runners OK. **Demo**: $100,137 (+0.14%), 13 positions. Short side best: OP +$86, NEAR +$52, ADA +$44. BTC $69,980. H-009 SHORT -2.14%. XS strats all at -0.20% (fee drag only, no rebal yet). **H-011 R27 refined to -0.0003%** (was -0.007% last session). Current funding rate +0.003%. Next settlement (00:00 UTC) drops oldest -0.011% rate — **R27 will flip positive, triggering re-entry**. Cron at 00:30 UTC Mar 21 will auto-execute H-011 entry + H-012/H-021 rebalances. IV/OB collectors day 2.
- Next: **Verify H-011 entry + rebalances executed** (session 57 at ~02:00 UTC or later). H-046 rebal Mar 22. H-039 first trade Mar 24.
- Questions added: none
- Self-modifications: none

### Session 2026-03-20 review (session 57)
- Goal: Review — pre-bar-close final verification, H-011 entry confirmation, rebalance timing correction
- Focus: System readiness for H-011 re-entry, EMA signal verification, rebalance date audit
- Done: All 14/14 runners OK. **Demo**: $100,124 (+0.12%), 13 positions. BTC $70,742 (+1.09%). H-009 SHORT -2.55% (BTC rallied against position). **H-011 entry CONFIRMED**: R27 at -0.0003%, indicated rate +0.0046%, projected post-settlement R27 ~+0.00013% → entry triggers at 00:30 UTC cron. **TIMING CORRECTION**: H-012/H-021 rebal is Mar 21 bar (processed 00:30 UTC Mar 22), NOT Mar 20 bar as previously stated. Days since rebal: H-012=4/5, H-021=2/3 after Mar 20 bar. H-009 EMA verified: gap widens to ~-$277 with Mar 20 close, remains SHORT. IV/OB collectors operational (day 2).
- Next: **Verify H-011 entry executed** (session 58). H-012/H-021 rebal at 00:30 UTC Mar 22. H-046 rebal Mar 22 bar. H-039 first trade Mar 24.
- Questions added: none
- Self-modifications: Corrected rebalance timing in state.md (H-012/H-021 off by 1 day).

### Session 2026-03-21 review (session 58)
- Goal: Review — verify H-011 entry, process Mar 20 bar, full system health check
- Focus: H-011 entry verification, all strategy MTM update, IV data collection
- Done: **H-011 ENTERED** at 00:00 UTC Mar 21 — $49.8k notional (5x), fee $50, first funding $2.51 collected (rate 0.005%, annualized ~+27.5%). R27 flipped to +0.000145%. 14/14 runners OK, Mar 20 bar processed. **Demo**: $100,131 (+0.13%). **Internal**: $139,837 (-0.12%). H-021 best +1.32%, H-009 worst -2.54% (SHORT, BTC $70,510). H-024 leads H-019 (+0.16% vs 0.00%). IV snapshot Mar 21 collected (2 days total). All systems operational.
- Next: **H-012 + H-021 rebal at 00:30 UTC Mar 22**. H-046 rebal Mar 23. H-039 first trade Mar 24.
- Questions added: none
- Self-modifications: none

### Session 2026-03-21 review (session 59)
- Goal: Review — full system health check, MTM update, data collector verification
- Focus: All 14 paper trades + demo account + IV/OB collectors
- Done: 14/14 runners OK (no new daily bar since Mar 20). **Demo**: $100,163 (+0.16%), all drifts within threshold. **Internal MTM**: ~$139,913 (-0.06%). H-021 best XS +0.96%, H-049 worst -0.71% (contrarian OP short losing). **H-019 overtook H-024** (+0.54% vs +0.31%, comparison reversed). H-052 recovered -0.26%→-0.06%. IV collector: 2 snapshots OK. OB collector: 1 snapshot OK. H-011 still in position, $2.51 funding collected, next settlement 08:00 UTC.
- Next: **H-012 + H-021 rebal at 00:30 UTC Mar 22**. H-046 rebal Mar 23. H-039 first trade Mar 24.
- Questions added: none
- Self-modifications: none

### Session 2026-03-21 system+review (session 60)
- Goal: System + Review — address user cron question, fix uncommitted leverage issue, MTM update
- Focus: Cron schedule change, H-011 leverage revert, demo runner H-011 spot+perp management, full MTM
- Done: **Cron changed from 2h → 4h** (user requested; research exhausted, paper trades hourly). **Reverted H-011 leverage 10x → 5x** (undocumented change from interrupted session; all backtests/metrics at 5x). Kept structural demo_portfolio_runner.py improvements (H-011 spot+perp leg management, spot_market_order in bybit_demo_client). 14/14 runners OK. **Demo**: $100,131 (+0.13%). **Internal**: ~$140,036 (+0.03%). H-021 best +1.23%, H-053 jumped +0.66% (second-best). **H-046 turned negative** (-0.17%, was +0.39%). H-049 recovering (-0.27%, was -0.71%). H-019/H-024 virtually tied (+0.23%/+0.28%). H-011 funding rate 0.0068% (37.4% ann at 5x). BTC $70,650.
- Next: **H-012 + H-021 rebal at 00:30 UTC Mar 22**. H-046 rebal Mar 23. H-039 first trade Mar 24.
- Questions added: none
- Self-modifications: Cron 2h→4h. Reverted H-011 runner leverage 10→5. Fixed demo_portfolio_runner comments. Removed user input from CLAUDE.md.

### Session 2026-03-21 review (session 61)
- Goal: Review — full system health check, MTM update, funding rate verification
- Focus: All 14 paper trades + demo account + H-011 funding + data collectors
- Done: 14/14 runners OK (no new daily bar since Mar 20). **Demo**: $100,073 (+0.07%), 13 positions + 0.514 BTC spot, total unrealized PnL +$163. **Internal MTM**: ~$140,199 (+0.14%, up from $140,036). H-021 best XS +0.84%, H-012 recovered +0.76%. **H-011**: 2 settlements collected ($4.43), current rate 0.0027% (15% ann at 5x). **H-046 recovered** from -0.17% to +0.19%. **H-052 improved** -0.04%→+0.41%. H-019 (+0.61%) vs H-024 (+0.65%) virtually tied still. 12/14 strats positive or flat, only H-049 (-0.21%) and H-009 (-2.10%) negative. IV collector: 2 snapshots OK. OB collector: 1 snapshot (minor naming issue).
- Next: **H-012 + H-021 rebal at 00:30 UTC Mar 22**. H-046 rebal Mar 23. H-039 first trade Mar 24.
- Questions added: none
- Self-modifications: none

### Session 2026-03-21 review (session 62)
- Goal: Review — full system health check, MTM update, H-011 funding deep-dive
- Focus: All 14 paper trades + demo account + H-011 R27 analysis + data collectors
- Done: 14/14 runners OK (no new daily bar since Mar 20). **Demo**: $100,234 (+0.23%, up from +0.07%). **Internal MTM**: ~$139,915 (-0.06%). H-021 best XS +0.96%, H-046 +0.39%. **H-049 worst** at -0.71% (contrarian LSR losing). **H-011 R27 deep-dive**: R27 = +0.000509% (positive, position holds). Indicated rate for 16:00 UTC is -0.0027% — H-011 will pay ~$1.34 but R27 stays positive after oldest negative rate drops from window. H-019 (+0.54%) leads H-024 (+0.31%) again. 10/14 positive or flat. IV: 2 snapshots. OB: 1 snapshot. All cron jobs operational.
- Next: **H-012 + H-021 rebal at 00:30 UTC Mar 22**. H-046 rebal Mar 23. H-039 first trade Mar 24.
- Questions added: none
- Self-modifications: none

### Session 2026-03-21 review (session 63)
- Goal: Review — full system health check, MTM update, pre-rebalance analysis
- Focus: All 14 paper trades + demo account + H-011 R27 projection + tonight's rebalance preview
- Done: 14/14 runners OK. **Demo**: $100,093 (+0.09%). **Internal MTM**: ~$140,069 (+0.05%). BTC dropped $70,725→$70,230. **H-012/H-021 tied best** (+0.67%). **H-044 biggest mover**: -0.16%→+0.57% (BTC decline helping). H-052 turned positive (+0.15%). H-049 recovering (-0.45%). **H-019 vs H-024**: virtually tied (0.41% vs 0.42%), H-024 micro-leading for first time. **H-011 R27**: +0.000559%, projected +0.000403% after midnight (holds). 11/14 positive. **Rebalance preview**: H-012 minor (DOT↔AVAX swap), H-021 major (6/8 positions change). IV: 2 snapshots. OB: 1 snapshot. All cron operational.
- Next: **H-012 + H-021 rebal at 00:30 UTC Mar 22**. H-046 rebal Mar 23. H-039 first trade Mar 24.
- Questions added: none
- Self-modifications: none

### Session 2026-03-21 review (session 64)
- Goal: Review — full system health check, MTM update, H-011 R27 projection, pre-rebalance check
- Focus: All 14 paper trades + demo account + H-011 funding rate deep-dive
- Done: 14/14 runners OK (no new daily bar since Mar 20). **Demo**: $100,108 (+0.11%). **Internal MTM**: ~$139,914 (-0.06%). BTC $70,446 (up from $70,230). H-021 best XS (+0.96%). H-049 worst (-0.71%). **H-044 reversed** from +0.57% to -0.16% (BTC rally hurt OI divergence). **H-019 leads H-024** again (+0.54% vs +0.31%). H-011 R27 +0.000559%, projected +0.000425% post-midnight (holds but slowly declining). Indicated rate -0.0079%, will pay ~$3.93. 9/14 positive or flat. IV: 2 snapshots. OB: 1 snapshot. All cron operational. H-012/H-021 rebalances in ~3h.
- Next: **Verify H-012 + H-021 rebalances executed** (session 65). H-046 rebal Mar 23. H-039 first trade Mar 24.
- Questions added: none
- Self-modifications: none

### Session 2026-03-22 review (session 65)
- Goal: Review — verify H-012/H-021 rebalances, full system health check, H-011 R27 analysis
- Focus: Post-rebalance verification, H-011 exit projection, full MTM update
- Done: 14/14 runners OK. Mar 21 bar processed. **H-012 REBALANCED**: SOL→ETH swap in shorts, longs unchanged (BTC/NEAR/ATOM/AVAX). **H-021 REBALANCED**: major reshuffle, BTC→longs, SOL/AVAX/DOGE→shorts (6/8 changed). Demo rebalanced with 7 trades, equity $100,270 (+0.27%). **H-011 EXIT IMMINENT**: R27 +0.000362% (razor-thin), indicated rate -0.0152%, projected R27 -0.000387% after 08:00 UTC → exit. Net funding -$1.50 this entry (collected $4.43, paid $5.93). BTC dropped to $68,973 (-2.1%). Internal MTM: $140,236 (+0.17%). H-021 best +1.64%. H-049 strong recovery -0.71%→+0.55%. 10/14 positive or flat.
- Next: **H-011 likely exits ~08:00 UTC Mar 22** (cron will auto-execute). H-046 rebal Mar 23. H-039 first trade Mar 24.
- Questions added: none
- Self-modifications: none

### Session 2026-03-22 review+research (session 66)
- Goal: Review + Research — monitor paper trades, research new cross-sectional factors
- Focus: H-011 exit confirmation, 4 new hypotheses tested, H-059 deployed
- Done: 15/15 runners OK. Demo $100,296 (+0.30%). Internal $149,692 (+0.35%, 15 strats). BTC $69,281 (recovered from $68,973). **H-011 EXIT CONFIRMED for 08:00 UTC** — R27 +0.00036%, indicated -0.0084%, projected -0.00013% post-settlement. **RESEARCH (4 hypotheses)**: H-056 (short-term reversal) REJECTED — WF fails, OOS Sharpe -1.61, edge decayed. H-057 (BTC→alt lead-lag) REJECTED — too unstable, WF mean -0.35. H-058 (residual momentum) CONDITIONAL — 100% param positive but 0.672 corr with H-012. **H-059 (vol term structure) CONFIRMED** — IS Sharpe 2.57, OOS 2.48, WF 4/6 positive (mean 1.23), 90% params positive, 0.034 corr H-019. **Deployed H-059 paper trade**: LONG OP/ARB/XRP/ATOM/ETH (vol expanding), SHORT DOGE/SUI/BTC/NEAR/DOT (vol contracting).
- Next: **H-011 exits 08:00 UTC Mar 22.** H-046 rebal Mar 23. H-039 first trade Mar 24. H-059 rebal Mar 28. Consider adding H-059 to H-055 portfolio optimization.
- Questions added: none
- Self-modifications: Added H-059 runner to cron orchestrator

### Session 2026-03-22 review (session 67)
- Goal: Review — verify H-011 exit, fix demo spot sell bug, full MTM update
- Focus: H-011 exit verification, demo portfolio cleanup, all 15 runners
- Done: 15/15 runners OK. **H-011 EXITED at 08:00 UTC** (rolling_avg_negative). Capital $9,899 (-1.01%). Net funding -$1.50, fees $99.74. 32h hold, net loss. **Fixed demo spot sell bug**: `round(btc, 5)` rounded UP past available balance → `math.floor(btc*100000)/100000` (floor-rounding). BTC spot (0.514) successfully sold. Demo equity $100,306 (+0.31%). BTC perp flipped from SHORT 0.465 → LONG 0.018 (non-H-011 strategies). **Internal MTM**: $150,159 (+0.11%). BTC $68,774 (-0.7%). H-012 leads +1.65%. H-024 overtakes H-019 again (-0.53% vs -0.73%). 8/15 positive, 3 flat, 4 negative.
- Next: H-046 rebal Mar 23. H-039 first trade Mar 24. H-021/H-049/H-031/H-052 rebal Mar 24. H-059 rebal Mar 28. Monitor H-011 R27 for re-entry.
- Questions added: none
- Self-modifications: Fixed floor-rounding bug in demo_portfolio_runner.py handle_h011_spot()

### Session 2026-03-22 review+research (session 68)
- Goal: Review + Research — full MTM update, H-011 R27 check, H-055 re-optimization with H-059
- Focus: Paper trade monitoring, portfolio optimization research
- Done: 15/15 runners OK. Demo $100,392 (+0.39%). Internal MTM $150,419 (+0.28%). BTC $68,784 (stable). **Top**: H-049 (+2.04%), H-031 (+2.00%), H-012 (+1.94%), H-053 (+1.77%). **Worst**: H-046 (-1.05%), H-059 (-0.71%, day 1). H-011 R27 at -0.1% ann — razor-thin negative, last 3 rates strongly negative (-2.5%, -10.5%, -6.6% ann), re-entry unlikely without BTC stabilization. **H-055 re-optimized with H-059**: H-059 appears in ALL optimal allocations at 10-14% weight. Best 8-strat: H-011/H-021/H-024/H-039/H-044/H-049/H-053/H-059 → Sharpe 8.02, +58.6%, 1.1% DD (195-day common period). H-059 has uniquely low/negative correlations with portfolio core (-0.109 H-011, -0.107 H-044, -0.148 H-049).
- Next: H-046 rebal Mar 23. H-039 first trade Mar 24. H-021/H-049/H-031/H-052 rebal Mar 24. H-059 rebal Mar 28. Monitor H-011 R27.
- Questions added: none
- Self-modifications: Added H-059 to H-055 portfolio optimizer (gen_h059_returns function)

### Session 2026-03-22 review+research (session 69)
- Goal: Review + Research — MTM update, H-011 R27 check, 4 new factor hypotheses
- Focus: Paper trade monitoring, new cross-sectional factor research
- Done: 16/16 runners OK. Demo $100,445 (+0.45%). Internal MTM $150,595 (+0.40%). BTC $68,752 (stable). H-011 R27 -0.11% ann (still OUT), indicated rate +5.1% (turning positive). **H-024 overtakes H-019** (-0.01% vs -0.56%). **RESEARCH (4 hypotheses)**: H-060 (return skewness) REJECTED — OOS decays, 0.609 corr with H-012. H-061 (idiosyncratic vol) CONDITIONAL — strong OOS but only works in second half, 0.563 corr with H-019. **H-062 (DD momentum) CONFIRMED** — WF 6/6 (mean 2.23), split-half stable (1.59/1.79), 92% params positive, Sharpe 1.67. Deployed paper trade: LONG NEAR/BTC/AVAX, SHORT SUI/ARB/OP. H-063 (autocorrelation) REJECTED — weak signal.
- Next: H-046 rebal Mar 23. H-039 first trade Mar 24. H-021/H-049/H-031/H-052 rebal Mar 24. H-062 rebal Mar 26. H-059 rebal Mar 28. Monitor H-011 R27 (may re-enter soon).
- Questions added: none
- Self-modifications: Added H-062 runner to cron orchestrator

### Session 2026-03-22 review+research (session 70)
- Goal: Review + Research — full MTM update, H-011 R27 analysis, 8 novel factor hypotheses
- Focus: Paper trade monitoring, H-011 re-entry projection, exhaustive novel factor research
- Done: 16/16 runners OK. Demo $100,521 (+0.52%). Internal MTM $160,984 (+0.62%). BTC $68,084 (down $668). **H-011 R27 deep projection**: Re-entry likely Mar 23 08:00-16:00 UTC — big negative rates from Mar 14 (-3.8%, -6.7%, -9.6% ann) dropping from R27 window. Rate at 08:00 only needs to be > -3.2% ann. **H-062 surging** +1.70% in day 1. **H-019/H-024 virtual tie** (-0.03% vs +0.06%). **RESEARCH (8 hypotheses, all REJECTED)**: H-064 (weekend effect) — no day-of-week signal in crypto. H-065 (sector rotation) — 0.611 corr H-012, 0.515 corr H-031 (redundant). H-066 (intraday range) — 50% positive = noise. H-067 (Amihud illiquidity) — 0.910 corr H-031 (identical to size factor). H-068 (open-close gap) — artifact in 24/7 markets. H-069 (extreme move freq) — WF 6/6 but OOS 0.24, fee-fragile. H-070 (vol-of-vol) — 50% noise. H-071 (return-volume corr) — 50% noise. All price/vol/OI/funding/premium/LSR data sources now fully explored. 71 hypotheses tested, ~48 rejected.
- Next: Verify H-046 rebal tonight (00:30 UTC). H-011 re-entry Mar 23. H-039 first trade Mar 24. H-021/H-049/H-031/H-052 rebal Mar 24. Future alpha requires IV surface + OB depth data (collecting, need 60-90 days).
- Questions added: none
- Self-modifications: none

### Session 2026-03-23 review (session 71)
- Goal: Review — verify H-046 rebal, H-011 re-entry, full MTM update
- Focus: Paper trade monitoring, system health check
- Done: 16/16 runners OK. Demo $100,320 (+0.32%). Internal MTM $160,780 (+0.49%). BTC $67,862 (down $222). **H-011 RE-ENTERED** at 00:00 UTC Mar 23 — R27 flipped to +8e-08 (razor-thin). Capital $9,848 (-1.52%). Whipsawed: $149 fees, -$3 net funding over 2 entry cycles. Demo re-bought BTC spot (0.489), perp SHORT 0.454. **H-046 REBALANCED** on Mar 22 bar: LONG OP/ETH/SUI/BTC, SHORT AVAX/NEAR/ADA/DOT. Top: H-012 (+2.57%), H-049 (+2.26%), H-031 (+1.94%). H-024 micro-leads H-019 (-0.05% vs -0.11%). 9/16 positive or flat.
- Next: H-039 first trade Mar 24. H-021/H-049/H-031/H-052 rebal Mar 24 bar. H-046 rebal Mar 25. H-012/H-062 rebal Mar 26. Monitor H-011 R27 (whipsaw risk).
- Questions added: none
- Self-modifications: none

### Session 2026-03-23 review (session 72)
- Goal: Review — full system health check, MTM update, H-011 R27 recovery analysis
- Focus: Paper trade monitoring, H-011 funding rate projection
- Done: 16/16 runners OK. Demo $100,238 (+0.24%). Internal MTM $160,802 (+0.50%). BTC $68,669 (up $807). **H-011 R27 RECOVERING**: +0.01% ann but projected to +0.5% as Mar 14 negative cluster exits window. Indicated rate +2.8% ann (positive). Whipsaw risk diminishing. Top: H-012 (+2.58%), H-049 (+2.17%), H-031 (+1.88%). H-024 leads H-019 (+0.04% vs -0.02%). 10/16 positive or flat. IV: 3 snapshots. OB: 3 snapshots. All systems operational.
- Next: H-039 first trade Mar 24. H-021/H-049/H-031/H-052 rebal Mar 24 bar. H-046 rebal Mar 25. H-012/H-062 rebal Mar 26. H-059 rebal Mar 28. Monitor H-011 R27.
- Questions added: none
- Self-modifications: none

### Session 2026-03-23 review (session 73)
- Goal: Review — full system health check, MTM update, H-011 R27 status
- Focus: Paper trade monitoring, demo account health, H-011 funding recovery
- Done: 16/16 runners OK. Demo $100,505 (+0.50%). Internal MTM $161,077 (+0.67%). BTC $68,210 (down $459). **H-011 R27 improving**: +0.19% ann (up from +0.01%). Latest rate +5.5% ann. 22 settlements, net funding -$2.55. Whipsaw risk diminishing. **Top**: H-012 (+3.18%), H-049 (+3.04%), H-053 (+2.52%), H-062 (+2.26%), H-031 (+2.16%). **H-024 clearly leads H-019** (+0.68% vs -0.16%). H-052 turned positive (+0.02%). 11/16 positive or flat. IV collector: 3 snapshots (Mar 20-22). All systems operational.
- Next: H-039 first trade Mar 24. H-021/H-049/H-031/H-052 rebal Mar 24 bar. H-046 rebal Mar 25. H-012/H-062 rebal Mar 26. H-059 rebal Mar 28. Monitor H-011 R27.
- Questions added: none
- Self-modifications: none (session 73)

### Session 2026-03-23 review (session 74)
- Goal: Review — full system health check, MTM update, H-011 R27 status
- Focus: Paper trade monitoring, demo account health, BTC rally impact analysis
- Done: 16/16 runners OK. Demo $100,385 (+0.38%). Internal MTM $161,045 (+0.65%). **BTC rallied to $70,660** (up $2,450 from $68,210 session 73, +3.6%). Portfolio resilient — market-neutral strategies unaffected. H-009 worst (-2.10%, SHORT into rally). **Top**: H-049 (+3.28%), H-053 (+3.01%), H-012 (+2.91%), H-031 (+2.62%), H-062 (+2.24%). **H-019 vs H-024 gap compressed** (-0.15% vs -0.10%, both near breakeven). **H-011 R27 stable** at +0.19% ann, latest rate +1.1% ann. Mar 14 negatives exit R27 in next 2 settlements → ~+0.7%. 11/16 positive or flat. All systems operational.
- Next: H-039 first trade Mar 24. H-021/H-049/H-031/H-052 rebal Mar 24 bar. H-046 rebal Mar 25. H-012/H-062 rebal Mar 26. H-059 rebal Mar 28. Monitor H-011 R27.
- Questions added: none
- Self-modifications: none (session 74)

### Session 2026-03-23 review (session 75)
- Goal: Review — full system health check, MTM update, H-011 R7 status
- Focus: Paper trade monitoring, H-019 vs H-024 reversal, H-011 funding recovery
- Done: 16/16 runners OK. Demo $100,458 (+0.46%). Internal MTM $160,681 (+0.43%). BTC $70,586. **H-031 now #1** (+4.24%), H-049 #2 (+3.77%). **H-019 vs H-024 reversed**: H-019 leads (-0.73% vs -2.13%). H-021 turned negative (-0.24%), H-052 turned negative (-0.43%). **H-011**: 7 settlements since re-entry, R7 +0.07% ann (barely positive), latest rate +6.1% ann (strong). Net funding +$0.21. 6/16 positive, 2 flat, 8 negative.
- Next: H-039 first trade Mar 24. H-021/H-049/H-031/H-052 rebal Mar 24 bar. H-046 rebal Mar 25. H-012/H-062 rebal Mar 26. H-059 rebal Mar 28. Monitor H-011 R7.
- Questions added: none
- Self-modifications: none (session 75)

### Session 2026-03-23 review (session 76)
- Goal: Review — full system health check, MTM update, H-056 deployment verification, H-011 R7
- Focus: Paper trade monitoring, demo account verification, funding rate analysis
- Done: 16/16 runners OK (no new daily bar since Mar 22). **Demo**: $99,561 (-0.44%), 14 perps, no spot BTC, leverage 2.79x. H-056 positions already aligned via hourly cron — **no --reset needed**. **Internal MTM**: $160,613 (+0.38%). BTC $70,911 (+$325). **H-011 R7 improved**: +0.80% ann (from +0.07%), indicated +4.0%. Negative Mar 21-22 cluster exiting window. **H-019 leads H-024 by 1.94%** (-0.65% vs -2.59%, gap widening). Top: H-031 (+4.61%), H-049 (+3.85%), H-062 (+2.91%), H-012 (+2.58%). 8/16 positive, 2 flat, 6 negative.
- Next: Tonight (00:30 UTC): H-021/H-031/H-049/H-052 rebalance + H-039 first trade on Mar 24 bar. H-046 rebal Mar 25. H-012/H-062 rebal Mar 26. H-059 rebal Mar 28. Monitor H-011 R7.
- Questions added: none
- Self-modifications: none (session 76)

### Session 2026-03-24 review (session 77)
- Goal: Review — full system health check, MTM update, H-011 funding analysis
- Focus: Paper trade monitoring, demo account health, H-011 R7/R27 analysis
- Done: 16/16 runners OK (no new daily bar since Mar 23 — rebalances fire tomorrow). **Demo**: $99,882 (-0.12%, improved from -0.44%). **Internal MTM**: $160,779 (+0.49%). BTC $70,615 (down $296). **H-052 turned positive** (+0.52% from -0.42%). **H-019 improved** to +0.48% (from -0.65%). **H-019 vs H-024 gap widened** to 2.63% (+0.48% vs -2.15%). **H-011**: R27 +1.16% ann (positive, no exit risk), R7 -1.54% ann (Mar 22 negatives exit in 2 days). Indicated +2.93% ann. 24 settlements. Top: H-031 (+4.31%), H-049 (+3.69%), H-062 (+2.81%), H-012 (+2.68%). 8/16 positive, 2 flat, 6 negative.
- Next: Tomorrow (00:30 UTC Mar 25): H-021/H-031/H-049/H-052 rebalance + H-039 first trade on Mar 24 bar. H-046 rebal Mar 25. H-012/H-062 rebal Mar 26. H-059 rebal Mar 28. Monitor H-011 R7.
- Questions added: none
- Self-modifications: none (session 77)

### Session 2026-03-24 review (session 78)
- Goal: Review — full system health check, MTM update, H-011 R7 recovery analysis
- Focus: Paper trade monitoring, demo account health, H-011 funding rate R7 projection
- Done: 16/16 runners OK (no new daily bar since Mar 23). **Demo**: $99,765 (-0.24%, down from -0.12%). **Internal MTM**: $160,779 (+0.49%, unchanged). BTC $70,190 (down $425). **H-011 R7 recovery ahead of schedule**: -1.52% ann currently, but projects positive after 08:00 UTC Mar 24 as -10.5% Mar 22 rate exits window. Last 3 settlements positive (+1.1%, +6.1%, +4.1%). R27 +1.16% (safe). Demo: OP short best (+$693), XRP long worst (-$588). No strategy changes. 8/16 positive, 2 flat, 6 negative.
- Next: Tonight (00:30 UTC Mar 25): H-021/H-031/H-049/H-052 rebal + H-039 first trade. H-046 rebal Mar 25. H-012/H-062 rebal Mar 26. H-059 rebal Mar 28. Verify H-011 R7 flip.
- Questions added: none
- Self-modifications: none (session 78)

### Session 2026-03-24 review (session 79)
- Goal: Review — full system health check, MTM update, H-011 R7 flip verification
- Focus: Paper trade monitoring, demo account health, H-011 funding rate R7 confirmation
- Done: 16/16 runners OK (no new daily bar since Mar 23). **Demo**: $98,486 (-1.51%, down from -0.24% — short-side losing on broad rally). **Internal MTM**: $160,485 (+0.30%, down from +0.49%). BTC $70,997 (up $807). **H-011 R7 FLIPPED POSITIVE: +0.28% ann** — confirmed projection, -10.5% Mar 22 00:00 rate exited R7 window. R27 +1.22% (solid). 25 settlements. **H-019 vs H-024**: H-019 -0.47% vs H-024 -1.61%, gap narrowed to 1.14% (from 2.63%). H-052 slipped to -0.05% (from +0.52%). Top: H-031 (+3.91%), H-049 (+3.65%), H-062 (+2.60%), H-012 (+2.45%). 6/16 positive, 3 flat, 7 negative.
- Next: Tonight (00:30 UTC Mar 25): H-021/H-031/H-049/H-052 rebal + H-039 first trade. H-046 rebal Mar 25. H-012/H-062 rebal Mar 26. H-059 rebal Mar 28. Monitor H-011 R7 sustaining.
- Questions added: none
- Self-modifications: none (session 79)


### Session 2026-03-24 review (session 80)
- Goal: Review — full system health check, MTM update, demo recovery, H-011 R7 sustaining
- Focus: Paper trade monitoring, demo account recovery, H-019 vs H-024 gap analysis
- Done: 16/16 runners OK. Demo: $99,720 (-0.28%). Internal MTM: $160,846 (+0.53%). BTC $70,869. H-011 R7 +0.28% ann. H-019 vs H-024 gap 1.90%. 8/16 positive.
- Next: Mar 25 rebalances. Questions: none. Self-modifications: none.

### Session 2026-03-24 review (session 81)
- Goal: Review — full system health check, MTM update, BTC selloff resilience test
- Focus: Paper trade monitoring, demo account health, BTC drop resilience
- Done: 16/16 runners OK. Demo: $99,821 (-0.18%). Internal MTM: $160,928 (+0.58%). BTC dropped to $69,231 (-2.3%). Portfolio flat — market neutrality working. H-011 R7 +0.76% ann. H-019 vs H-024 gap 2.50%. 8/16 positive.
- Next: Mar 25 rebalances. Questions: none. Self-modifications: none.

### Session 2026-03-25 review (session 82)
- Goal: Review — full system health check, MTM update, BTC recovery impact
- Focus: Paper trade monitoring, demo account health, H-011 R7/R27 analysis
- Done: 16/16 runners OK (no new daily bar since Mar 23). **Demo**: $99,031 (-0.97%, down from -0.18% — short-side losing on broad recovery). **Internal MTM**: $160,782 (+0.49%, down from +0.58%). **BTC recovered to $70,899** (up +2.4% from $69,231). Portfolio flat despite BTC rally — market neutrality holding. **H-011**: R7 +0.86% ann (sustaining positive, 15/21 positive), R27 -0.27% ann (older positives rolling off, will recover as Mar 22 negatives exit in ~5 days). **H-019 vs H-024 gap widened**: +0.48% vs -2.15% (2.63% spread, from 2.50%). **H-031 now #1** (+4.31%), H-049 #2 (+3.69%). 9/16 positive, 5 negative, 2 flat.
- Next: Tonight (00:30 UTC Mar 25): H-021/H-031/H-049/H-052 rebal + H-039 first trade on Mar 24 bar. H-046/H-012/H-062 rebal Mar 26. H-059 rebal Mar 28. Monitor H-011 R27 recovery.
- Questions added: none
- Self-modifications: none (session 82)

### Session 2026-03-25 review (session 83)
- Goal: Review — rebalance verification, margin fix, full MTM update
- Focus: Verify 4 strategy rebalances (H-021/H-031/H-049/H-052) + H-039 first trade. Fix demo margin issue.
- Done: 16/16 runners OK. 4 rebalances confirmed. H-039 first trade. Demo margin crisis fixed (3x→10x leverage, IM 98%→31%). Demo $99,712 (-0.29%). Internal $160,214.
- Self-modifications: demo_portfolio_runner.py PERP_LEVERAGE 3→10

### Session 2026-03-25 review (session 84)
- Goal: Review — full system health check, MTM update, H-011 R7 sustaining
- Focus: Paper trade monitoring, demo account recovery, broad market-neutral improvement
- Done: 16/16 runners OK. Demo $100,078 (+0.08%). Internal $160,714. 8/16 positive. H-011 R7 +3.13% ann. H-019 vs H-024 gap 1.95%. IV collection ongoing.
- Self-modifications: none

### Session 2026-03-25 review (session 85)
- Goal: Review — full system health check, MTM update, cron verification
- Focus: Paper trade monitoring, demo account recovery, H-011 funding rate analysis
- Done: 16/16 runners OK. Demo $100,548 (+0.55%). Internal $160,892 (+0.56%). BTC $71,215. 9/16 positive. H-031 +5.15% (#1). H-011 R7 +2.46% ann, latest +10.95% ann. H-019 vs H-024 gap 2.64%. Cron verified for Mar 26.
- Self-modifications: none

### Session 2026-03-25 review+research (session 86)
- Goal: Review + Research — system health check + IV surface analysis → new options strategy
- Focus: MTM update, IV surface exploratory analysis, H-063 vol selling backtest + deployment
- Done: 17/17 runners OK. Demo $100,592 (+0.59%). Internal $160,681 (+0.43%). BTC $71,673. 9/17 positive. NEW H-063 short strangle deployed. Backtest: Sharpe 1.54, +52.5% ann, -18.4% DD, WF 6/6, 60/60 params. Corr -0.10 vs H-009.
- Self-modifications: Added H-063 runner to cron orchestrator (session 86)

### Session 2026-03-25 review+research (session 87)
- Goal: Review + Research — system health check + expanded universe analysis + portfolio overlap analysis
- Focus: MTM update, H-072 expanded universe momentum test, H-056 position overlap analysis
- Done: 17/17 runners OK. Demo $100,457 (+0.46%). Internal $170,614 (+0.36%). BTC $71,331. 7/17 positive. H-072 REJECTED (expanded 25-asset universe). Position overlap: H-012≡H-062, H-021≡H-046.
- Self-modifications: none (session 87)

### Session 2026-03-25 review+research (session 88)
- Goal: Review + Research — system health check + new factor research (session returns, volume-price divergence)
- Focus: MTM update, H-073 session-based returns, H-074 volume-price divergence factor
- Done: 17/17 runners OK. Demo $100,866 (+0.87%). Internal $170,219. BTC $70,967. 9/17 positive. H-073 REJECTED (session returns). H-074 CONDITIONAL (volume-price divergence, OOS>IS but WF 2/6).
- Self-modifications: none (session 88)

### Session 2026-03-26 review+research (session 89)
- Goal: Review + Research — verify cron rebalances, H-063 first entry, new factor research
- Focus: MTM update, cron verification, H-075 risk-adj momentum, H-076 price efficiency factor
- Done: 18/18 runners OK. Demo $101,419 (+1.42%). BTC $71,264. 11/18 positive. H-063 first trade (73000C+69000P strangle). H-075 REJECTED. H-076 CONFIRMED+DEPLOYED (efficiency, Sharpe 1.94, corr 0.04 with H-012). Metrics bug noted.
- Self-modifications: Added H-076 runner + cron (session 89)

### Session 2026-03-26 review+research (session 90)
- Goal: Review + Research — MTM update, H-056 re-optimization, new factor research
- Focus: Paper trade monitoring, H-056 v2 (H-046→H-049 swap), H-077 reversal + H-078 skewness backtests
- Done: 18/18 runners OK. Demo $102,314 (+2.31%). BTC ~$70,500. 11/18 positive. H-056 v2 deployed (H-046→H-049). H-077 REJECTED (12% positive, reversal). H-078 REJECTED (29% positive, skewness).
- Self-modifications: demo_portfolio_runner.py H-046→H-049 swap (session 90)

### Session 2026-03-26 review+research (session 91)
- Goal: Review + Research — MTM update, H-063 monitoring, 4 new factor backtests
- Focus: Full MTM update (18 runners), H-063 put proximity warning, H-079/H-080/H-081/H-082 backtests
- Done: 18/18 runners OK. Demo $102,522 (+2.52%). BTC $69,957. 11/18 positive. H-063 put approaching. H-079 REJECTED (autocorrelation). H-080 REJECTED (VWAP=momentum, corr 0.647). H-081 REJECTED (Hurst, 25% positive). H-082 CONDITIONAL (risk-adj carry, WF 4/6, corr -0.11).
- Self-modifications: none (session 91)
