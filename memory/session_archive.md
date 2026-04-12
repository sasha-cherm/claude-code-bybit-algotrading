# Session Archive (Sessions bootstrap through 162)

### Session 2026-03-28 review+research (session 103)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: H-116/H-117/H-118 backtests. H-116 CONDITIONAL (Hurst exponent). H-117 REJECTED (info ratio). H-118 REJECTED (OBV trend).

### Session 2026-03-28 review+research (session 104)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: H-119/H-120/H-121 backtests. H-119 REJECTED (Amihud). H-120 REJECTED (relative volume spike). H-121 CONDITIONAL (VWAP deviation).

# Session Archive (Sessions bootstrap through 92)

### Session 2026-03-26 review+research (session 92)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests, H-085 deployment
- Focus: Full MTM update (19 runners), H-063 put proximity warning, H-083/H-084/H-085 backtests
- Done: 19/19 runners OK. **Demo**: $101,601 (+1.60%). BTC $69,464. H-085 CONFIRMED+DEPLOYED (turnover velocity, 100% params positive, best Sharpe 2.08). H-083 CONDITIONAL (idio vol, regime-dependent). H-084 REJECTED (BTC correlation).
- Self-modifications: Added H-085 runner + cron orchestrator entry
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

### Session 2026-03-26 review+research (session 91)
- Goal: Review + Research — MTM update, H-063 monitoring, new factor research
- Focus: Full MTM update (18 runners), H-063 put proximity warning, 4 new factor backtests
- Done: 18/18 runners OK. Demo: $102,522 (+2.52%). BTC $69,957. 11/18 positive. H-063 WARNING: BTC approaching 69000P strike. Research: H-079/H-080/H-081 REJECTED, H-082 CONDITIONAL.
- Next: Mar 27: rebalances. Monitor H-063.

### Session 2026-03-26 review+research (session 93)
- Goal: Review + Research — full MTM update, H-063 put ITM monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC selloff), H-063 vol selling under stress, H-086/H-087/H-088 backtests
- Done: 19/19 runners OK. Demo: $101,913 (+1.91%). BTC $68,865. H-063 PUT ITM by $135. Research: H-086/H-087/H-088 REJECTED. System fix: Orchestrator MTM bug, lib/metrics.py DAILY constant.
- Next: Mar 27 rebalances. Monitor H-063.

### Session 2026-03-27 review+research (session 94)
- Goal: Review + Research — verify cron rebalances, full MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (continued BTC selloff), rebalance verification, H-089/H-090/H-091 backtests
- Done: 19/19 runners OK. **Demo**: $101,275 (+1.27%, down from +1.91%). BTC $68,823 (-3.48% 24h). **10/19 positive**, 2 flat, 7 negative. Top: H-031(+4.68%), H-039(+4.35%, exited Thu SHORT), H-049(+3.54%). **Rebalances verified**: H-012 rebalanced (LONG BTC/AVAX/DOGE/NEAR, SHORT ARB/DOT/OP/SUI). H-062 rebalanced (unchanged). H-039 exited SHORT, now FLAT at $10,435 (+4.35%). **H-044 FIXED**: OI data staleness check was >2 days (should be >=1). Fixed, data refreshed, Mar 26 bar processed. **H-063 PUT ITM** by $281 — equity $9,982, $982 to stop, delta hedge 0.043 BTC. **H-011**: IN, R27 avg 1.43e-05, latest rate +6.28e-05 (strong). **Research**: H-089 CONDITIONAL (funding rate change, 63% params positive, robust params WF 4/6 mean 0.94, corr -0.25 with H-012 — good diversifier but fragile param selection). H-090 REJECTED (BTC corr breakaway, 43.8% positive, split-half collapses). H-091 REJECTED (vol concentration Herfindahl, 33.3% positive).
- Next: Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053. Mar 31: Kill H-024. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: h044_oi_divergence/runner.py OI staleness fix (session 94)

### Session 2026-03-27 review+research (session 95)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC continued decline), H-063 vol selling stress, H-092/H-093/H-094 backtests
- Done: 19/19 runners OK. Demo: $100,796 (+0.80%). BTC $68,519. H-063 PUT ITM by $481 — equity $9,970 (-0.30%). Research: H-092 REJECTED, H-093 CONDITIONAL, H-094 REJECTED.
- Next: Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053.
- Questions added: none
- Self-modifications: none (session 95)

### Session 2026-03-27 review+research (session 96)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC continued selloff to $67,843), H-063 vol selling new low, H-095/H-096/H-097 backtests
- Done: 19/19 runners OK. Demo: $100,181 (+0.18%). BTC $67,843. H-063 NEW LOW equity $9,899 (-1.01%). Research: H-095/H-096/H-097 all REJECTED.
- Next: Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053.
- Questions added: none
- Self-modifications: none (session 96)

### Session 2026-03-27 review+research (session 97)
- Goal: Review + Research — MTM update (BTC crash to $66,636), H-063 critical monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC -4.1% 24h), H-063 vol selling stress test, H-098/H-099/H-100 backtests
- Done: 19/19 runners OK. Demo: $100,764 (+0.76%). BTC $66,636. H-063 CRITICAL equity $9,739 (-2.61%), $739 to stop. Research: H-098/H-099/H-100 all REJECTED.
- Next: Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053.
- Questions added: none
- Self-modifications: none (session 97)

### Session 2026-03-27 review+research (session 98)
- Goal: Review + Research — MTM update (BTC selloff to $65,966), H-063 critical monitoring, 3 new factor backtests
- Focus: Full MTM update (19 runners), H-063 vol selling stress, H-101/H-102/H-103 backtests
- Done: 19/19 runners OK. **Demo**: $100,834 (+0.83%). BTC $65,966 (-4.3% 24h). **10/19 positive**, 3 flat, 6 negative. Top: H-031(+4.68%), H-039(+4.35%), H-049(+3.54%). **H-063 WORSE**: equity $9,637 (-3.63%), put ITM by $3,035, **$637 to stop**. New low $9,601 at BTC $65,804. Delta hedge 0.095 BTC absorbing damage (BTC -$5,298 from entry, equity -$363). **Research**: H-101 REJECTED (kurtosis, split-half -0.614). H-102 REJECTED (vol stability, 27% positive). H-103 REJECTED (PV correlation, OOS -0.519).
- Next: Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053. Mar 31: Kill H-024. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 98)

### Session 2026-03-28 review+research (session 99)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,027), H-063 vol selling, H-104/H-105/H-106 backtests
- Done: 19/19 runners OK. **Demo**: $100,681 (+0.68%). BTC $66,027. **10/19 positive**, 3 flat, 6 negative. **H-063 improved**: $9,660 (-3.40%, up from -3.63%), $660 to stop. **H-104 REJECTED** (RSI MR, only 3% positive — crypto is momentum-driven, not mean-reverting). **H-105 REJECTED** (CLV, 78% positive, OOS 2.0, WF 0.76 — strong BUT split-half -0.19, regime-dependent). **H-106 REJECTED** (vol skew, 97% IS positive but OOS -0.12 — classic overfitting).
- Next: Mar 28 00:30: H-021 rebal. Mar 29: H-031/H-046/H-049/H-052/H-053. Mar 31: Kill H-024. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 99)

### Session 2026-03-28 review+research (session 100)
- Goal: Review + Research — MTM update, H-021 rebalance verification, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,372), H-063 vol selling recovery, H-107/H-108/H-109 backtests
- Done: 19/19 runners OK. Demo: $101,390 (+1.39%). BTC $66,372. 9/19 positive. H-063 $9,716 (-2.84%). H-107/H-108/H-109 all REJECTED.
- Next: Mar 29 rebalances. Mar 31: Kill H-024.
- Self-modifications: none (session 100)

### Session 2026-03-28 review+research (session 101)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,224), H-063 vol selling, H-110/H-111/H-112 backtests
- Done: 19/19 runners OK. Demo: $101,796 (+1.80%). 8/19 positive. H-063 $9,699 (-3.01%). H-110/H-111/H-112 all REJECTED.
- Next: Mar 29 rebalances. Mar 31: Kill H-024.
- Self-modifications: none (session 101)

### Session 2026-03-28 review+research (session 102)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,401 recovering), H-063 vol selling, H-113/H-114/H-115 backtests
- Done: 19/19 runners OK. **Demo**: $101,338 (+1.34%, down from +1.80%). BTC $66,401 (-2.2% 24h). **8/19 positive**, 3 flat, 8 negative. Top: H-031(+4.67%), H-039(+4.35%), H-049(+3.00%), H-062(+2.15%), H-012(+2.04%). **H-063 improving**: $9,724 (-2.76%, up from -3.01%), $724 to stop, 5.8d to expiry. **H-019 vs H-024**: gap 1.64% (narrowed from 1.83%). **H-113 REJECTED** (funding-adj momentum, 100% IS positive but corr **0.995** with H-012 — funding adjustment is negligible in crypto). **H-114 REJECTED** (G/L ratio, 90% IS positive but split-half H2 **-0.535** — regime-dependent). **H-115 REJECTED** (autocorrelation, only 63% IS positive, WF **0/5** OOS -0.591 — no signal).
- Next: Mar 29: H-031/H-046/H-049/H-052/H-053/H-059 rebal. Mar 30: H-076. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 102)

### Session 2026-03-28 review+research (session 103)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,417 stable), H-063 vol selling recovery, H-116/H-117/H-118 backtests
- Done: 19/19 runners OK. Demo: $101,586 (+1.59%). BTC $66,417. 8/19 positive. H-063 $9,742 (-2.58%). H-116 CONDITIONAL (Hurst exponent, WF 4/5, corr 0.238). H-117 REJECTED (info ratio, corr 0.491 with H-012). H-118 REJECTED (OBV trend, split-half -0.509).
- Questions added: none
- Self-modifications: none (session 103)

### Session 2026-03-28 review+research (session 105)
- Goal: Review + Rebalance + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,926 stable), H-063 vol selling analysis, H-122/H-123/H-124 backtests
- Done: 19/19 runners OK. Demo: $100,742 (+0.74%). BTC $66,926. 9/19 positive. H-063: $9,832 (-1.68%), $832 buffer, 5.4d to expiry. H-122 REJECTED (candle conviction — 0% IS positive). H-123 REJECTED (vol-price elasticity — 23% IS, WF 1/6). H-124 REJECTED (CLV — 84.7% momentum direction, corr 0.448 H-012 — just momentum).
- Questions added: none
- Self-modifications: none (session 105)

### Session 2026-03-28 review+research (session 105)
- Goal: Review + Rebalance + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,926 stable), H-063 vol selling analysis, H-122/H-123/H-124 backtests
- Done: 19/19 runners OK. Demo: $100,742 (+0.74%). BTC $66,926. 9/19 positive, 3 flat, 7 negative. Top: H-031(+4.67%), H-039(+4.35%), H-049(+3.00%). H-063: MTM $9,832 (-1.68%), $832 buffer, 5.4d to expiry. H-019 vs H-024: gap 1.64%. Research: H-122 REJECTED (candle conviction), H-123 REJECTED (vol-price elasticity), H-124 REJECTED (CLV).
- Next: Mar 29 rebalances. Mar 31: Kill H-024. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 105)

### Session 2026-03-29 review+research (session 106)
- Goal: Review + Research — MTM update, rebalance verification, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,516, continued slide), H-063 vol selling, H-125/H-126/H-127 backtests
- Done: 19/19 runners OK. Demo: $101,453 (+1.45%). BTC $66,516. 7/19 positive. H-125/H-126/H-127 all REJECTED.
- Next: Mar 30: rebalances. Mar 31: Kill H-024. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 106)

### Session 2026-03-29 review+research (session 107)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,713 recovering), H-063 vol selling improvement, H-128/H-129/H-130 backtests
- Done: 19/19 runners OK. Demo: $101,779 (+1.78%). BTC $66,713. H-128/H-129/H-130 all REJECTED.
- Next: Mar 30: rebalances. Mar 31: Kill H-024. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 107)

### Session 2026-03-29 review+research (session 108)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,718 flat), H-063 vol selling stable, H-131/H-132/H-133 backtests
- Done: 19/19 runners OK. Demo: $102,245 (+2.25%). BTC $66,718. H-131/H-132/H-133 all REJECTED.
- Next: Mar 30: rebalances. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 108)

### Session 2026-03-29 review+research (session 109)
- Goal: Review + Research — MTM update, H-063/H-011 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,829 +0.17%), H-063 vol selling improving, H-134/H-135/H-136 backtests
- Done: 19/19 runners OK. Demo: $103,060 (+3.06%). H-063 improving: $9,842 (-1.58%). Research: H-134/H-135/H-136 all REJECTED.
- Next: Mar 30 rebalances. Mar 31: Kill H-024.
- Questions added: none
- Self-modifications: none (session 109)

### Session 2026-03-30 review+research+bugfix (session 110)
- Goal: Review + Research + System — MTM update, H-053 repair, min-asset guard for all runners, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $67,486 +0.98%), H-063 approaching breakeven, H-053 broken rebalance fix, H-137/H-138/H-139 backtests
- Done: 19/19 runners OK. Demo: $100,365 (+0.37%). H-063 near breakeven: $10,018 (+0.18%). H-053 repaired. Min-asset guard added to 14 runners. Research: H-137/H-138/H-139 all REJECTED.
- Next: Mar 30 bar rebalances. Mar 31: Kill H-024.
- Questions added: none
- Self-modifications: min-asset guard in 14 runners, H-053 state repaired (session 110)

### Session 2026-03-30 review+research (session 111)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $67,847 +0.54%), H-063 vol selling profitable, H-140/H-141/H-142 backtests
- Done: 19/19 runners OK. Demo: $100,872 (+0.87%). H-063 profitable: $10,073 (+0.73%). Research: H-140/H-141/H-142 all REJECTED.
- Next: Mar 30 bar rebalances. Mar 31: Kill H-024.
- Questions added: none
- Self-modifications: none (session 111)

### Session 2026-03-30 review+research (session 112)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $67,285 -0.83%), H-063 vol selling pullback, H-143/H-144/H-145 backtests
- Done: 19/19 runners OK. Demo: $101,297 (+1.30%). H-063 pulled back to -0.34%. H-143 REJECTED, H-144 CONFIRMED (idiosyncratic vol), H-145 REJECTED.
- Next: Mar 30 bar rebalances. Kill H-024 Mar 31.

### Session 2026-03-30 backtest (session 113)
- Goal: Backtest — H-144 idiosyncratic vol factor full validation
- Focus: Confirming H-144 with 4/4 criteria (IS 92%, WF 6/6 OOS 1.99, split-half stable, low corr H-012 0.01)
- Done: H-144 CONFIRMED. But H-019 corr 0.72 — near-substitute for total vol. Not deploying as paper trade due to redundancy.
- Next: Session 114 review + research
- Questions added: none
- Self-modifications: none (session 113)

### Session 2026-03-31 review+research+system (session 114)
- Goal: Review + Research + System — MTM update, kill H-024, system hardening, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,644 -0.95%), H-024 kill, position-count guards, H-146/H-147/H-148 backtests
- Done: 18/19 runners OK (H-024 killed). Demo: $100,814 (+0.81%). 9/18 positive. H-019 surged to +7.44%. H-024 KILLED (H-019 won 7.64% gap). H-052 dropped to -3.74%. H-063: $9,973 (-0.27%). Position-count guard added to ALL 13 multi-asset runners. H-146 REJECTED (lead-lag spillover). H-147 REJECTED (volume skewness). H-148 REJECTED (DD speed).
- Next: Rebalances, research
- Questions added: none
- Self-modifications: position-count guard in 13 runners, orchestrator log fix, H-031 state fix (session 114)

### Session 2026-03-31 review+research+system (session 115)
- Goal: Review + Research + System — MTM update, rebalance verification, demo fix, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $67,127, +0.72%), demo ATOM fix, H-149/H-150/H-151 backtests
- Done: 18/18 runners OK. Demo: $100,211 (+0.21%). 12/18 positive. H-149/H-150/H-151 all REJECTED. Demo ATOM fix.
- Next: Mar 31 bar rebalances. Apr 1: H-085.
- Self-modifications: ATOMUSDT max order qty added to demo runner

### Session 2026-03-31 review+research (session 116)
- Goal: Review + Research — MTM update, H-063 monitoring, demo update, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $67,477, +0.52%), H-063 approaching expiry, H-152/H-153/H-154 backtests
- Done: 18/18 runners OK. Demo: $100,035 (+0.04%). 13/18 positive. H-063 crossed into profit! H-152 REJECTED (return entropy). H-153 REJECTED (volume surprise). H-154 REJECTED (corr centrality).
- Next: Mar 31 bar: H-012/H-046/H-062. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry + H-031.
- Questions added: none
- Self-modifications: none (session 116)


### Session 2026-03-31 review+research (session 117)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,761, -1.06%), H-063 vol selling back negative, H-155/H-156/H-157 backtests
- Done: 18/18 runners OK. **Demo**: $99,936 (-0.06%). BTC $66,761. **12/18 positive**, 6 negative. Top: H-031(+5.34%), H-039(+4.35%), H-012(+2.74%). **H-063 back negative**: $9,909 (-0.91%), PUT ITM by $2,239, $909 buffer to stop, 3.0d to expiry — BTC drop hurt, needs stability. **Research**: **H-155 REJECTED** (Amihud illiquidity — liquid_long IS 100%, WF 6/6 mean 1.25, BUT **corr 0.799 with H-031** = same signal, split-half H1=-0.123). **H-156 REJECTED** (funding rate vol — stable_long IS 89.6%, WF 4/6 mean 0.476, BUT split-half **H1=1.712/H2=-0.075** = signal died. Excellent corr 0.013/−0.013 — novel but decayed). **H-157 REJECTED** (range ratio — noisy_long IS 91.7% but WF **3/6** mean **-0.289**, split-half both halves negative).
- Next: Mar 31 bar (00:30 UTC Apr 1): H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 117)
### Session 2026-03-31 review+research (session 118)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,674, -0.13%), demo declining, H-158/H-159/H-160 backtests
- Done: 18/18 runners OK. **Demo**: $98,020 (-1.98%, down from -0.06%). BTC $66,674. SOL long dragging demo (-$2,546). **12/18 positive**, 6 negative (unchanged). Top: H-031(+5.34%), H-039(+4.35%), H-012(+2.74%). **H-063 slightly improved**: $9,923 (-0.77%, was -0.91%), $923 buffer to stop, 2.8d to expiry — theta helping. **Research**: **H-158 REJECTED** (dual momentum TS+XS — IS 96%, WF 4/6, split-half both positive, BUT **corr 1.000 with H-012** — mathematically identical signal). **H-159 REJECTED** (vol-adjusted return — IS 98%, WF **6/6**, split-half both positive, BUT **corr 0.948 with H-012** — near duplicate). **H-160 CONFIRMED** (trend-quality efficiency×invvol — IS 87%, WF 4/6 mean 0.303, split-half H1=1.174/H2=1.764, **corr 0.355 with H-012, 0.117 with H-076** — all 4/4 criteria pass, genuinely novel).
- Next: Mar 31 bar (00:30 UTC Apr 1): H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 118)

### Session 2026-03-31 review+research+deploy (session 119)
- Goal: Review + Research + Paper Trade — MTM update, H-160 deployment, 3 new factor backtests
- Focus: Paper trade monitoring (BTC ~$67,805, +1.7%), H-063 flipped positive, H-160 deployment, H-161/H-162/H-163 backtests
- Done: 18/18 runners OK (pre-deployment). **13/18 positive** (new best ratio, was 12). BTC rallied +1.7%. **H-063 flipped positive**: $10,110 (+1.10%, was -0.77%) — BTC rally + theta decay winning, 2.6d to expiry. **H-160 deployed** as paper trade #19: LONG ETH/DOGE/SOL, SHORT BTC/OP/ATOM. Added to cron orchestrator. **Research**: **H-161 REJECTED** (variance ratio — 52.8% IS positive = noise, VR has no XS signal in crypto). **H-162 REJECTED** (MAX effect — short_max 33.3%, long_max 66.7%, lottery premium doesn't transfer to crypto). **H-163 REJECTED** (momentum concentration — low_conc_long 79.2%, close but fails 80% threshold).
- Next: Mar 31 bar (00:30 UTC Apr 1): H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG + H-160. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: H-160 runner created, added to orchestrator (session 119)


### Session 2026-03-31 review+research (session 120)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC ~$68,179, +0.6%), demo recovering, H-164/H-165/H-166 backtests
- Done: 19/19 runners OK. **Demo**: $99,124 (-0.88%, improved from -1.98%). BTC $68,179. **13/19 positive**, 6 negative. Top: H-031(+5.34%), H-039(+4.35%), H-012(+2.74%), H-019(+2.26%), H-063(+1.81%). **H-063 improving**: $10,181 (+1.81%, was +1.10%), PUT ITM by only $952 (shrinking), $1,181 buffer to stop, 2.5d to expiry — on track for profitable first trade. **Research**: **H-164 REJECTED** (co-momentum — 14.8% IS positive, peer-weighted momentum has no signal in crypto). **H-165 REJECTED** (funding-premium interaction — 25.0% IS positive, joint crowding signal too noisy). **H-166 REJECTED** (return persistence — 90% IS, WF **6/6** mean 2.263, excellent standalone BUT **corr 0.503 with H-160** — redundant with trend-quality factor).
- Next: Mar 31 bar (00:30 UTC Apr 1): H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG + H-160. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 120)

### Session 2026-04-01 review+research (session 121)
- Goal: Review + Research — MTM update, rebalance verification, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $68,293, +0.17%), H-063 approaching expiry, H-167/H-168/H-169 backtests
- Done: 19/19 runners OK. **Demo**: $99,552 (-0.45%, improved from -0.88%). BTC $68,293. **12/19 positive** (H-059 flipped negative), 7 negative. Top: H-031(+5.01%), H-039(+4.31%), H-063(+3.36%), H-019(+2.56%). **H-063 best yet**: $10,336 (+3.36%), PUT ITM by only $708, $1,336 buffer, 2.3d to expiry. **Mar 31 rebalances confirmed**: H-012 (LONG NEAR/AVAX/BTC/ATOM, SHORT SOL/SUI/ARB/OP), H-046 (LONG OP/ATOM/ARB/DOGE, SHORT SUI/AVAX/DOT/NEAR), H-062 (unchanged). **Research**: **H-167 CONFIRMED** (vol-price confirmation — 90% IS, WF 5/6 mean 1.145, split-half both positive, max corr 0.251. Caveat: H2=0.088 weak). **H-168 REJECTED** (return autocorrelation — 25% IS positive, no XS signal). **H-169 CONFIRMED** (beta-adjusted momentum/alpha — 100% IS, WF 4/6 mean 1.648, corr 0.342 with H-012. Strongest new factor).
- Next: Apr 1 bar (00:30 UTC Apr 2): H-085 rebal. Apr 2: H-039 LONG + H-160. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 121)

### Session 2026-04-01 review+research (session 122)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $68,217, -0.11%), H-063 pulled back, H-170/H-171/H-172 backtests
- Done: 19/19 runners OK. **Demo**: $99,330 (-0.67%, down from -0.45%). BTC $68,217. **12/19 positive**, 7 negative (unchanged). Top: H-031(+5.01%), H-039(+4.31%), H-019(+2.56%), H-012(+2.30%), H-063(+2.22%). **H-063 pulled back**: $10,222 (+2.22%, was +3.36%), PUT ITM by ~$783, $1,222 buffer to stop, 2.1d to expiry — theta still working, on track. **Research**: **H-170 REJECTED** (return kurtosis — IS 93.3% excellent, best Sharpe 1.32, BUT WF **2/6** positive, mean -0.46. Split-half H1=0.16/H2=1.49 = severe recency bias. Low corr to all factors (-0.09 to -0.21) confirms novelty but signal not stable). **H-171 REJECTED** (funding rate momentum — contrarian 68.8% IS (below 80%), WF 5/6 but split-half fails. Corr **0.405** with H-053 = redundant with funding level. Reconfirms H-130 rejection). **H-172 REJECTED** (Hurst exponent R/S — trending_long 43.3% IS, meanrev_long 33.3%. No XS signal. Joins autocorrelation + variance ratio as third persistence measure to fail in crypto).
- Next: Apr 1 bar (00:30 UTC Apr 2): H-085 rebal. Apr 2: H-039 LONG + H-160. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 122)

### Session 2026-04-01 review+research+deploy (session 123)
- Goal: Review + Research + Deploy — MTM update, H-169 deploy, H-175 confirm+deploy, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $68,720, +0.74%), H-063 improving, H-169/H-175 deployment, H-173/H-174/H-175 backtests
- Done: 19/19 runners OK (pre-deploy). Demo: $99,178 (-0.82%). BTC $68,720. 12/19 positive, 7 negative. H-063 improving: $10,276 (+2.76%). H-169 deployed as paper trade #20. H-175 CONFIRMED and deployed as #21. H-173 REJECTED (GK vol ratio). H-174 REJECTED (downside beta).
- Next: Apr 1 bar: H-085. Apr 2: H-160. Apr 3: H-063 expiry + H-031.

### Session 2026-04-01 review+research (session 124)
- Goal: Review + Research — MTM update, H-024 orchestrator cleanup, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $68,306, -0.61% from last session), H-176/H-177/H-178 backtests
- Done: 21 runners checked. Demo $98,201 (-1.80%). H-176/H-177/H-178 REJECTED. 178 total hypotheses.
- Next: Apr 1 bar: H-085. Apr 2: H-039/H-160. Apr 3: H-063 expiry.

### Session 2026-04-01 review+research (session 125)
- Goal: Review + Research — MTM update, demo check, H-063 monitoring, 3 new factor backtests
- Done: 21 runners. Demo $99,896 (-0.10%). BTC $69,164. 14/21 positive. H-063 both OTM. H-179/H-180/H-181 REJECTED. 181 hypotheses.

### Session 2026-04-01 review+research (session 126)
- Goal: Review + Research — MTM update, H-063 pre-expiry, 3 new backtests
- Done: 21 runners. Demo $98,471 (-1.53%). BTC $68,340. H-182 CONFIRMED (Range), H-183 CONFIRMED (Gap). H-184 REJECTED. 184 hypotheses.

### Session 2026-04-02 review+research+deploy (session 127)
- Goal: Review + Research + Deploy — MTM update, H-182/H-183 deployment, 3 new factor backtests
- Done: 23 runners (21->23). Demo $98,182 (-1.82%). BTC $68,170. 13/21 positive. H-182/H-183 deployed. H-185/H-186/H-187 REJECTED. 187 hypotheses.

### Session 2026-04-02 review+research (session 128)
- Goal: Review + Research — MTM update, H-063 pre-expiry monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC ~$66,350), H-063 crashed, H-188/H-189/H-190 backtests
- Done: 23 runners. Demo $98,434 (-1.57%). H-063 crashed -1.31%. H-188 REJECTED, H-189 CONFIRMED, H-190 REJECTED. 190 total.
- Next: H-063 expiry + H-031 rebal. Deploy H-189.
- Self-modifications: none (session 128)

### Session 2026-04-02 review+research+deploy (session 129)
- Goal: Review + Research + Deploy — MTM update, H-189 deployment, 3 new factor backtests
- Done: H-189 deployed as #24. H-191 CONFIRMED (vol-price elasticity). H-192 REJECTED. H-193 CONFIRMED (OI-price divergence). 193 total.

### Session 2026-04-02 review+research+deploy (session 130)
- Goal: Review + Research + Deploy — MTM update, H-191/H-193 deployment, 3 new factor backtests
- Done: Demo $98,577 (-1.42%). H-191 deployed #25, H-193 deployed #26. H-194 REJECTED (realized vol ratio). H-195 REJECTED (funding reversal). H-196 REJECTED (dollar vol accel, redundant H-021). 196 total.

### Session 2026-04-02 review+research (session 131)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Done: 26 runners. Demo $98,428 (-1.57%). 13/26 positive. H-063 recovered to +1.20%. H-197 CONFIRMED (Amihud illiquidity). H-198/H-199 REJECTED. 199 total.
- Self-modifications: Archived sessions 121-122

### Session 2026-04-03 review+deploy+research (session 132)
- Goal: Review + Deploy + Research — MTM update, H-197 deploy, 3 new factor backtests
- Done: 27 runners (26→27 post-deploy). Demo $98,564 (-1.41%). 13/27 positive. H-063 +0.24%, 11h to expiry. H-197 deployed #27. H-200/H-201/H-202 all REJECTED. 202 total.
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
- Done: 27 runners checked. Demo: $97,730 (-2.27%). BTC $66,931. 10/27 positive, 16 negative, 1 flat. H-063 SETTLED PROFITABLY: Trade 1 net +$77.64 (+0.78%). H-209/H-210/H-211 REJECTED.
- Next: Apr 4: H-039(exit SHORT), rebalances. Continue research.
- Self-modifications: Archived sessions 125-126 (session 135)

### Session 2026-04-03 review+research (session 136)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (BTC $66,673), H-212/H-213/H-214 backtests
- Done: 27 runners. Demo: $97,833 (-2.17%). 12/27 positive. H-212/H-213/H-214 REJECTED.
- Next: Apr 4: H-039(exit SHORT), rebalances. Continue research.
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
- Done: 28 runners. Demo $98,736 (-1.26%). 13/28 positive. H-219 CONFIRMED (up-volume ratio IS 80%, WF 4/6). H-218/H-220 REJECTED. 220 total.
- Self-modifications: none (session 138)

### Session 2026-04-04 review+deploy+research (session 139)
- Goal: Review + Deploy + Research — MTM update, H-219 deployment, H-221/H-222/H-223 backtests
- Focus: Paper trade MTM (BTC Apr 3 bar $66,965), H-219 deployment, 3 new factor backtests
- Done: 29 runners checked (28→29 post-deploy). Demo: $98,931 (-1.07%, improving). 14/29 positive. Top: H-039(+5.79%), H-031(+3.90%), H-012(+3.21%), H-076(+3.20%), H-175(+1.82%). H-219 deployed. H-221 REJECTED, H-222 REJECTED, H-223 CONFIRMED. 223 total hypotheses.
- Next: Deploy H-223 paper trade. Continue research.

### Session 2026-04-04 review+deploy+research (session 140)
- Goal: Review + Deploy + Research — MTM update, H-223 deployment, H-224/H-225/H-226 backtests
- Focus: Paper trade MTM (no new daily bar, still Apr 3), H-223 deployment, 3 new factor backtests
- Done: 30 runners checked (29→30 post-deploy). Demo: $98,827 (-1.17%). 14/30 positive. H-223 deployed. H-224 REJECTED, H-225 REJECTED, H-226 REJECTED. 226 total hypotheses.
- Next: Continue research. Monitor H-189 (-2.94%) and H-160 (-2.19%).

### Session 2026-04-04 review+research (session 141)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, still Apr 3), H-227/H-228/H-229 backtests
- Done: 30 runners checked. Demo: $98,650 (-1.35%). 14/30 positive. H-227 REJECTED, H-228 REJECTED, H-229 REJECTED. 229 total hypotheses.
- Next: Continue research. Monitor H-189 (-3.03%) and H-160 (-2.25%).

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
- Done: 33 runners (32→33 post-deploy). Demo: $100,490 (+0.49%). H-250 CONFIRMED+deployed. H-245/H-246/H-247/H-248/H-249 REJECTED.
- Next: Continue research. Monitor H-021 (-3.63%) and H-009/H-160.
- Questions added: none
- Self-modifications: H-250 runner created, added to orchestrator. Archived session 137. (session 147)

### Session 2026-04-05 review+research (session 148)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$66,834), H-251/H-252/H-253 backtests
- Done: 33 runners checked. Demo: $100,509 (+0.51%). 10/33 positive. Research: H-251/H-252/H-253 all REJECTED. 253 total hypotheses.
- Next: Continue research. Monitor H-021 (-3.63%) and H-009/H-160.

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
- Done: 35 runners (34→35 post-deploy). Demo: $100,877 (+0.88%). 12/35 positive. H-259 CONFIRMED, deployed. H-257/H-258 REJECTED. 259 total hypotheses.
- Next: Continue research. Monitor H-189 (-3.56%) and H-183 (-3.40%).

### Session 2026-04-06 review+research (session 151)
- Goal: Review + Research — MTM update with final Apr 5 bar, 3 new factor backtests
- Focus: Paper trade MTM (BTC Apr 5 final $69,035, Apr 6 in progress $68,939), H-260/H-261/H-262 backtests
- Done: 35 runners checked. Demo: $98,869 (-1.13%). 16/35 positive. H-260/H-261/H-262 all REJECTED. 262 total hypotheses.
- Next: Continue research. Monitor H-053 (-2.12%) and H-183 (-1.88%).

### Session 2026-04-06 review+deploy+research (session 152)
- Goal: Review + Deploy + Research — MTM update, H-263/H-264 deployment, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$69,130), H-263/H-264/H-265 backtests
- Done: 37 runners (35→37 post-deploy). Demo: $98,188 (-1.81%). 10/37 positive. H-263 CONFIRMED (relative strength vs BTC, WF 6/6 mean 4.058). H-264 CONFIRMED (return skewness, WF 6/6 mean 1.532). H-265 REJECTED. Both deployed. 265 total hypotheses.
- Next: Continue research. Monitor H-009 (-2.10%) and H-021 (-1.71%).

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
- Done: 37 runners checked. Demo $97,400 (-2.60%). 16/37 positive. H-269/H-270/H-271 all REJECTED. 271 total hypotheses.
- Next: Continue research. Monitor H-053 (-2.06%) and H-183 (-1.75%).
- Self-modifications: Archived session 144. (session 154)

### Session 2026-04-06 review+research (session 155)
- Goal: Review + Research — MTM update, 3 new factor backtests
- Focus: Paper trade MTM (no new daily bar, BTC ~$69,750), H-272/H-273/H-274 backtests
- Done: 37 runners checked. Demo: $98,557 (-1.44%). H-272/H-273/H-274 all REJECTED. 274 total hypotheses.
- Next: Continue research. Monitor H-063 and H-053.


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
- Done: 47 runners (43→47). H-342 CONFIRMED (VP synchronicity, WF 5/6, corr 0.004 H-076). H-343 CONFIRMED (momentum decay, WF 6/6 mean 4.163 — best ever). 349 total hypotheses.
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
- Done: 51 runners (50→51 post-deploy). Demo: $97,787 (-2.21%). H-363 CONFIRMED+deployed. 367 total hypotheses.
- Next: Await Q-005 answer. Monitor H-063 (-6.35%, expires Apr 10). Continue research.
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
- Done: 56 runners (54→56). Demo: $96,481 (-3.52%). 20/54 positive. H-388 CONFIRMED (Night-Day Diff, deployed). H-394 CONFIRMED (Variance Ratio, deployed). 399 total hypotheses.
- Next: Await Q-005 answer. H-063 expires Apr 10. Continue research.
- Self-modifications: H-388/H-394 runners created.

### Session 2026-04-09 review+deploy+research (session 168)
- Goal: Review + Deploy + Research — MTM update, 16 new backtests (2 batches of 8), critical look-ahead bias discovery, 3 new deployments
- Focus: Paper trade MTM (BTC $70,814), H-400 through H-415 backtests. Look-ahead bias investigation.
- Done: 58 runners (56→58). 23/55 positive (avg -0.14%). CRITICAL: Look-ahead bias found in 4h backtests. H-404/H-411/H-414 CONFIRMED+deployed. 415 total hypotheses.

### Session 2026-04-09 review+deploy+research (session 169)
- Goal: Review + Deploy + Research — MTM update, 24 new backtests (3 batches of 8), 2 new deployments
- Focus: Paper trade MTM (BTC $70,742), H-416 through H-439 backtests. Hourly-derived signal exploration.
- Done: 61 runners. 20/57 positive (avg +0.12%). H-435 Hourly Kurtosis and H-437 HL Spread CONFIRMED+deployed. Daily XS exhausted. 439 total hypotheses.

### Session 2026-04-09 review+deploy+research (session 170)
- Goal: Review + Deploy + Research — MTM update, 16 new backtests, 3 new deployments
- Focus: Paper trade MTM (BTC $71,171), H-440 through H-455 backtests. Hourly-derived signals.
- Done: 64 runners (61→64). 20/61 positive. H-445/H-447/H-451 CONFIRMED+deployed. 455 total hypotheses.

### Session 2026-04-09 review+deploy+research (session 171)
- Goal: Review + Deploy + Research — MTM update, 16 new backtests (2 batches of 8), 1 new deployment
- Focus: Paper trade MTM (BTC $71,245), H-456 through H-471 backtests. Hourly-derived signal exploration — final batch.
- Done: 65 runners (64→65). 20/65 positive (avg +0.07%). H-470 CONFIRMED+deployed. 471 total hypotheses.
- Next: Await Q-005 answer. H-063 expires Apr 10 08:00.
- Questions added: none
- Self-modifications: H-470 runner created, added to orchestrator. Archived session 161. (session 171)

### Session 2026-04-09 review+research (session 172)
- Goal: Review + Research — MTM update, 24 new backtests (3 batches of 8), no deployments
- Focus: Paper trade MTM (BTC $72,405), H-472 through H-495 backtests. Cross-asset dynamics, factor interactions, calendar seasonality.
- Done: 65 runners (unchanged). 20/65 positive (avg +0.04%). Demo $97,514 (-2.49%). Batch 1-3: 24 tested, 1 confirmed (H-485 Monthly Reversal, not deployed). 495 total hypotheses.
- Next: Await Q-005 answer. H-063 expires Apr 10 08:00.

### Session 2026-04-09 review+research (session 173)
- Goal: Review + Research — MTM update, ML ensemble signal combination, H-496 deployed
- Focus: Paper trade MTM (BTC $72,385), ML ensemble backtest combining 30 confirmed XS factors
- Done: 66 runners (65→66). 20/66 positive (avg +0.01%). H-496 deployed (ML ensemble, best Sharpe ever: 2.149). 496 total hypotheses.
- Next: Await Q-005 answer. H-063 settles Apr 10 08:00.

### Session 2026-04-10 review+research (session 174)
- Goal: Review + Research — MTM update, 16 new hypotheses (regime timing + portfolio construction)
- Focus: Paper trade MTM (BTC $71,966), H-497 through H-512 backtests
- Done: 66 runners (unchanged). 26/66 positive (avg -0.10%). Research batch 1 (H-497-H-504): All 8 REJECTED. Research batch 2 (H-505-H-512): All 8 REJECTED. 512 total hypotheses.
- Next: Await Q-005 answer. Explore new data sources.
- Self-modifications: Archived session 164. (session 174)

### Session 2026-04-10 review+deploy+research (session 175)
- Goal: Review + Deploy + Research — MTM update, 19 new backtests, H-528 deployment
- Focus: Paper trade MTM (BTC $72,128), expanded universe testing, novel signal categories (H-513–H-531)
- Done: 67 runners (66→67). 26/66 positive (avg -0.11%). Demo $94,608 (-5.39%). H-528 Range Expansion CONFIRMED+deployed. 531 total hypotheses.
- Next: Await Q-005 answer. H-063 settles today 08:00. Monitor H-496/H-528.

### Session 2026-04-10 review+deploy+research (session 176)
- Goal: Review + Deploy + Research — MTM update, H-063 settlement check, 16 new BTC time-series backtests, 3 deployments
- Focus: Paper trade MTM (BTC $71,681), BTC time-series strategies (H-532–H-547)
- Done: 70 runners (67→70). 14/66 positive (21%). Avg -0.17%. 3 confirmed (H-535/H-539/H-544). H-063 trade 2 settled. 13 REJECTED. 547 total hypotheses.

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

