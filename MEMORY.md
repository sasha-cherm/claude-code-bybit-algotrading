# MEMORY.md — Session Log & State Index

## Current State
- **Active strategies:** H-009 (BTC daily EMA + vol targeting) PENDING paper trade, H-010 (multi-strategy research) PENDING
- **Paper trading:** none
- **Analyzed:** H-008 (multi-asset daily trend) — BTC signal validated OOS, asset selection fails walk-forward
- **Rejected:** H-001–H-007 (7 hypotheses rejected)
- **Last session:** 2026-03-16 analyze (session 3)
- **Key insight:** Sharpe ~0.65 single strategy → max ~15% return at 10% DD. Need multi-strategy for 20%/10% target.
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
