# MEMORY.md — Session Log & State Index

## Current State
- **Paper trading:** H-009 (+0.53%) + H-011 (OUT, 0%) + H-012 (+0.36%) — portfolio +0.30%
- **H-012 positions:** LONG BTC/NEAR/ATOM/AVAX, SHORT SOL/SUI/ARB/OP (next rebal 2026-03-21)
- **Target portfolio:** 20% H-009 / 60% H-011 / 20% H-012 → Sharpe 2.78 (self-regulating)
- **Rejected:** H-001–H-007, H-013–H-017 (all fail walk-forward or redundant)
- **Last session:** 2026-03-17 review (session 17)
- **BTC rallying:** $74,557, up $815. H-009 LONG +0.53%. H-012 short side gave back gains (OP -$46, SOL -$13).
- **Funding recovery on track:** H-011 re-entry projected 2026-03-20 00:00 UTC. Rolling-27 -1.87% ann. Next settlement 16:00 UTC.
- **Research exhaustion on BTC daily:** 17 hypotheses tested, only H-009/H-011/H-012 survive. Future research: sub-daily, on-chain, or orderbook signals.
- **Next action:** Monitor paper trades. H-011 re-entry Mar 20. H-012 rebal Mar 21.
- **Open user questions:** none

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
