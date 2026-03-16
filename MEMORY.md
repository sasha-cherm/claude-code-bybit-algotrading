# MEMORY.md — Session Log & State Index

## Current State
- **Paper trading:** H-009 (+0.31%) + H-011 (OUT, 0%) + H-012 (-0.25%) — portfolio +0.02%
- **H-012 positions:** LONG BTC/NEAR/ATOM/AVAX, SHORT SOL/SUI/ARB/OP (next rebal 2026-03-21)
- **Target portfolio:** 20% H-009 / 60% H-011 / 20% H-012 → Sharpe 2.78, +40.1%, 10.1% DD
- **Rejected:** H-001–H-007 (7 hypotheses), calendar patterns, EW trend
- **Last session:** 2026-03-17 review (session 7)
- **Risk watch:** Funding rates NEGATIVE since 2026-03-07 (8 days). Q1 2026 only 1.6% ann. H-011 (60% of portfolio) earning nothing. No filter window rescues performance.
- **Action needed:** If funding stays negative >2 weeks, research H-011 replacement or reallocate
- **New tool:** `scripts/portfolio_monitor.py` — live mark-to-market portfolio dashboard
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
