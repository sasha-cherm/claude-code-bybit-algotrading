# MEMORY.md — Session Log & State Index

## Current State
- **Active strategies:** none (4 hypotheses PENDING)
- **Paper trading:** none
- **Last session:** 2026-03-15 research
- **Open user questions:** none (Q-001 answered and acted on)

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
