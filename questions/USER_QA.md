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
