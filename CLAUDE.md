# Bybit Algo Trading — Autonomous Research System

## Mission
Build a robust crypto trading algorithm validated on historical data and paper trades, targeting **≥20% annual return** on Bybit. Instruments: spot, futures, options — anything that fits the risk profile. Before I meant DD to be <=10%, actually nice if it would be <=50%, excelent if it would be <=30%.

## How This Works

Claude sessions are launched automatically every 4 hours by crontab. Each session is autonomous: research, backtest, refine, or paper-trade. You are the researcher, analyst, and engineer. You can modify this CLAUDE.md, create skills, update memory, and evolve the system.

---

## Session Protocol

**Every session must follow this protocol — do not skip steps.**

### 1. Load Context (start here)
Read these files in order — stop if missing:
- `MEMORY.md` — session log + state index
- `memory/state.md` — current strategy status, open positions
- `memory/hypotheses.md` — what has been tested, what is pending
- `questions/USER_QA.md` — check for new user answers, act on them

Limit: read only the above 4 files at session start. Do not load full backtests or data files into context.

### 2. Decide the Session Goal
Based on state, pick exactly ONE focus:
- [ ] **Research** — explore a new strategy idea, write it to `hypotheses.md` as PENDING
- [ ] **Backtest** — implement and run backtest for a PENDING hypothesis
- [ ] **Analyze** — review backtest results, mark hypothesis CONFIRMED/REJECTED
- [ ] **Paper Trade** — implement a CONFIRMED strategy in paper-trade mode
- [ ] **Review** — review paper trade performance, decide to promote/kill
- [ ] **Optimize** — tune parameters of a live paper strategy
- [ ] **System** — improve tooling, fix bugs, update this file

Log the chosen goal at the top of the session log entry.

### 3. Execute
- Keep file reads targeted — avoid loading large data files wholesale
- Write intermediate results to `results/` not to context
- If a script runs long, use background execution and check next session

### 4. Update State
Before ending the session, update:
- `memory/state.md` — current status of all strategies
- `memory/hypotheses.md` — mark hypothesis outcomes
- `MEMORY.md` — append a session log entry (≤10 lines)
- `questions/USER_QA.md` — add any questions for the user

### 5. Commit to Git
Every session must end with a git commit, even if only memory/state files changed:
```bash
git add -A
git commit -m "session YYYY-MM-DD HH:MM: <goal> — <one-line summary>"
git push origin master
```
Never commit `.env` or files matched by `.gitignore`. If `git push` fails due to remote changes, pull and rebase first: `git pull --rebase origin master`.

---

## File Structure

```
/
├── CLAUDE.md                  ← this file (self-modifiable)
├── MEMORY.md                  ← session log index + state summary
├── memory/
│   ├── state.md               ← live strategy status, paper positions
│   ├── hypotheses.md          ← all hypotheses with status + results
│   └── *.md                   ← other memory files as needed
├── questions/
│   └── USER_QA.md             ← questions to user / answers from user
├── strategies/
│   ├── <name>/
│   │   ├── strategy.py        ← strategy implementation
│   │   ├── backtest.py        ← backtest runner
│   │   └── results.json       ← latest backtest metrics
├── paper_trades/
│   └── <name>/
│       ├── runner.py          ← paper trade execution
│       └── log.json           ← trade log
├── lib/
│   ├── bybit_client.py        ← Bybit API wrapper
│   ├── data_fetch.py          ← OHLCV / orderbook fetchers
│   └── metrics.py             ← sharpe, drawdown, return calculators
├── data/                      ← cached historical data (do not load fully into context)
└── scripts/
    └── session.sh             ← crontab entry script
```

---

## Hypothesis Tracking

Format in `memory/hypotheses.md`:

```
## H-001: <title>
- Status: PENDING | BACKTEST | CONFIRMED | REJECTED | LIVE | KILLED
- Idea: <one sentence>
- Instrument: spot | futures | options
- Timeframe: <e.g. 1h>
- Logic: <brief>
- Result: <metrics when done — annual return, max drawdown, sharpe>
- Notes: <what worked, what didn't>
- Sessions: [2026-03-15 session 1], ...
```

---

## Performance Targets

| Metric | Target | Excellent | Hard Limit |
|--------|--------|-----------|------------|
| Annual return | ≥ 20% | ≥ 30% | — |
| Max drawdown | ≤ 50% | ≤ 30% | — |
| Sharpe ratio | ≥ 1.5 | ≥ 2.0 | — |
| Win rate | ≥ 45% | — | — |
| Backtest period | ≥ 2 years | — | — |

A strategy must pass backtest before paper trading. Paper trading runs ≥ 4 weeks before any live consideration.

---

## User Interaction

Questions for the user go in `questions/USER_QA.md`. Format:

```
## Q-001 [OPEN/ANSWERED]
**Session:** 2026-03-15 session 1
**Question:** ...
**Answer:** (user fills this in)
**Action taken:** (Claude fills after reading answer)
```

Check this file every session. If a question is ANSWERED and no action taken, act on it immediately.

---

## Self-Modification Rules

You may:
- Edit `CLAUDE.md` to improve protocols, add sections, fix errors
- Create new skills in `~/.claude/` if a repeated pattern warrants it
- Add utility scripts to `lib/` or `scripts/`
- Restructure `strategies/` or `memory/` layout if justified

Always note self-modifications in the session log.

---

## Context Budget

Keep total context per session under ~80k tokens:
- Session start files: ~5k
- Active strategy code: ~5k
- Backtest results summary (not raw data): ~3k
- Working code/analysis: ~20k
- Leave headroom for tool outputs

If approaching limits, summarize and write to disk before continuing.

---

## Bybit API Notes

- Use `pybit` library for Bybit V5 API
- Paper trading: use Bybit testnet (`testnet=True`) or implement internal simulation
- Rate limits: respect 120 req/min on public endpoints
- Credentials: read from `.env` file (never hardcode, never commit)

---

## Environment Setup

```bash
# Install deps
pip install pybit pandas numpy ta-lib scipy statsmodels python-dotenv ccxt

# .env file (create manually, never commit)
BYBIT_API_KEY=...
BYBIT_API_SECRET=...
BYBIT_TESTNET=true
```

---

## Session Log Format (append to MEMORY.md)

```
### Session YYYY-MM-DD HH:MM
- Goal: <one of the 7 session types>
- Focus: <strategy name or research topic>
- Done: <what was accomplished>
- Next: <what the next session should do>
- Questions added: Q-XXX (or none)
- Self-modifications: (or none)
```

