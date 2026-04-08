# User Q&A

Claude asks questions here. Please fill in answers and save the file — Claude will pick them up next session.

---

## Q-001 [ANSWERED]
**Session:** 2026-03-15 bootstrap
**Question:** A few setup questions to guide the research direction:

1. **Capital allocation** — Approximately how much capital will be allocated? This affects position sizing, fee impact, and whether options are practical.

2. **Bybit account type** — Unified Trading Account (UTA) or classic? Do you already have testnet API keys ready?

3. **Preferred instrument** — Any preference or restriction? (e.g. "stick to BTC/ETH futures only", "no options for now", "spot only")

4. **Risk tolerance** — The 10% drawdown target is the hard limit. Is there a softer daily/weekly stop you want enforced?

5. **Automation level** — Should paper trading remain manual-review-before-live, or fully automatic promotion once targets are hit?

**Answer:**
1. 10,000–100,000 USD
2. UTA, no testnet keys yet
3. No preference — all instruments fair game
4. No hard drawdown restriction, but stay conscious of drawdown
5. Fully autonomous — user wants hands-off "scripts that print money"

**Action taken:** (session 2026-03-15 research)
- Recorded capital range, account type, risk preferences as project constraints
- Designing strategies for $10k–$100k capital on Bybit UTA
- No drawdown kill-switch enforced, but targeting ≤15% max drawdown in backtests
- System will be fully autonomous: research → backtest → paper → live pipeline with no user gate

---

## Q-002 [ANSWERED]
**Session:** 2026-03-17 review (session 10)
**Question:** I noticed you added a note to CLAUDE.md about Las Palmas, Brentford, and O'Higgins (sports betting context). This project is focused on crypto algotrading on Bybit — I don't have any sports betting functionality. Could you clarify what this refers to? Was this meant for a different project, or would you like me to explore sports betting as an additional research direction?
**Answer:**
Sorry, wrong project, nevermind
**Action taken:** (session 2026-03-17 review session 11)
- Dismissed — user confirmed this was meant for a different project
- Removed the sports betting text from CLAUDE.md

---

## Q-003 [ANSWERED]
**Session:** 2026-03-19 review+system (session 35)
**Question:** H-030, H-031, and H-032 are confirmed standalone but NOT currently in paper trading. Here's the situation:

- **H-030 (Composite Multi-Factor)**: This combines momentum + volume momentum + beta into one strategy. However, we're already running those 3 factors as separate strategies (H-012, H-021, H-024). Running H-030 would effectively double-count these signals. The portfolio of individual strategies (Sharpe 2.26) actually beats the composite (Sharpe 2.14) because different rebalance schedules add diversification. **Recommendation: Do NOT deploy — redundant.**

- **H-031 (Size Factor)**: Genuine signal (long large-cap, short small-cap). Sharpe 1.58, +78.5% annual, 31% DD. Corr 0.49 with H-012 (momentum) so it's partially redundant in the current portfolio, but works well standalone. Very low turnover = low fees. **Could deploy as independent paper trade — would you like to?**

- **H-032 (Cointegration Pairs)**: Fundamentally different from cross-sectional factors. Negative correlation with momentum (-0.31). Works best in BTC downtrends. But OOS evidence is weak (only 2/12 pairs pass both validation tests). Sharpe 1.33, +9.5%, 5.8% DD. **Could deploy as experimental low-allocation paper trade — would you like to?**

Should I deploy H-031 and/or H-032 as paper trades?

**Answer:**
yes, deploy them

**Action taken:** (session 2026-03-19 review+paper trade session 36)
- Deployed H-031 (Size Factor) as paper trade: LONG BTC/ETH/SOL/XRP/DOGE, SHORT LINK/DOT/OP/ARB/ATOM. $10k allocated.
- Deployed H-032 (Cointegration Pairs) as paper trade: 8-pair portfolio (DOT/ATOM, DOGE/LINK, DOGE/ADA, DOT/OP, SOL/DOGE, AVAX/DOT, NEAR/OP, ARB/ATOM). $10k allocated. No entries yet (z-scores within thresholds).
- Added both to cron orchestrator (hourly automated execution).
- Both are tracked independently from the main 5-strategy portfolio.

---

## Q-004 [ANSWERED]
**Session:** 2026-03-19 review+research (session 38)
**Question:** (User asked via CLAUDE.md) Regarding H-036 — if there is statistically proved data regarding green/red hour candles, maybe we can combine it with Polymarket 1 hour BTC UP/DOWN market? The Polymarket doesn't have historical data so it is only possible to place a paper trade.
**Answer:** User asked this directly — self-answering question.
**Action taken:** (session 2026-03-19 review+research session 38)
- Ran full H-037 analysis of BTC green/red probability per hour with statistical significance tests
- **Confirmed 5 statistically significant hours** (p < 0.05): 17:00 UTC (UP 56.3%), 21:00 UTC (UP 54.9%), 22:00 UTC (UP 54.0%), 23:00 UTC (DOWN 54.1%), 13:00 UTC (DOWN 53.8%)
- All 5 hours show consistent direction in both train (year 1) and test (year 2) halves
- OOS simulation: 53.7% win rate, 10/13 months profitable at $0.32/bet
- **Key caveat**: Edge only exists if Polymarket prices at ~50c. If market already prices in the seasonality, edge vanishes
- Created H-037 hypothesis (CONFIRMED for paper trade) and `paper_trades/h037_polymarket/tracker.py`
- **This requires MANUAL paper trading** — user needs to check Polymarket prices at target hours and record them
- Usage: `python3 paper_trades/h037_polymarket/tracker.py log <hour> <UP/DOWN> <price> <outcome>`

---

## Q-005 [OPEN]
**Session:** 2026-04-08 session 164
**Question:** Comprehensive portfolio optimization analysis suggests upgrading the demo portfolio from H-056 v2 to v3. Key findings:

**Problem with current H-056 v2:** 6 strategies, Sharpe 5.64, +105% ann, -4.7% DD (195-day common period). Strong, but concentrated — H-031/H-021 are correlated (both momentum-adjacent), and missing key diversifiers.

**Proposed H-056 v3 — add H-059 and H-076 as diversifiers:**

| Strategy | v2 Weight | v3 Weight | Leverage | Role |
|----------|-----------|-----------|----------|------|
| H-031 (Size) | 30% | 22% | 3x | Core — long large cap, short small |
| H-052 (Premium) | 23% | 17% | 3x | Contrarian positioning |
| H-053 (Funding XS) | 16% | 12% | 3x | Contrarian positioning |
| H-021 (Vol Mom) | 15% | 8% | 3x | Volume momentum (reduced — weaker paper perf) |
| **H-059 (Vol Term)** | — | **15%** | **3x** | **NEW — vol regime, Sharpe 1.50, corr ~0 with momentum** |
| **H-076 (Efficiency)** | — | **12%** | **3x** | **NEW — anti-momentum, Sharpe 1.05, -0.37 corr with H-012** |
| H-039 (DOW) | 10% | 10% | 1x | Calendar seasonality |
| H-049 (LSR) | 6% | 4% | 3x | Contrarian sentiment |

**Why this improves the portfolio:**
1. **H-059** has Sharpe 1.50 over 4.6 years and ~0 correlation with momentum — pure diversification gain
2. **H-076** is negatively correlated with price momentum (-0.37 with H-012) — hedges the momentum exposure
3. Both have 18+ days of paper trade history: H-059 +0.47%, H-076 +4.07% (3rd best overall)
4. H-021 reduced from 15% → 8% because it's the weakest paper performer (-1.71%) and correlated with H-085

**Additional finding:** H-031/H-197/H-183 are extremely correlated (0.88-0.97). We only need H-031 — the others are redundant.

Should I deploy this H-056 v3 change?

**Answer:**
**Action taken:**
