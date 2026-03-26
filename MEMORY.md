# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity $102,314 (+2.31%). H-049 replaced H-046 (redundancy fix). 11 trades.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x). No H-011, H-009, H-046.
- **H-011 status**: DROPPED from demo. R7 +4.99% ann. Internal paper trade IN.
- **Internal paper trades:** 18 runners active. Session 90. Total MTM: $181,926. BTC ~$70,500.
- **Top performers**: H-031 (+5.00%), H-049 (+3.71%), H-062 (+1.59%), H-019 (+1.38%). **11/18 positive**, 5 negative, 2 flat.
- **H-056 v2 change**: H-046 had 4/4 position overlap with H-021 (redundant). Replaced with H-049 (#2 performer, neg corr with H-031).
- **H-063**: Vol selling strangle accruing premium. BTC $70,500 (within 73000C/69000P). Equity $10,018 (+0.18%). Delta hedge active.
- **H-076**: Price Efficiency Factor, day 1. Equity $9,976 (-0.24%, fees).
- **Research**: 78 total hypotheses. H-077 REJECTED (reversal). H-078 REJECTED (skewness).
- **Metrics note**: lib/metrics.py sharpe uses 8760 for daily → inflated ~5x. Relative comparisons valid.
- **AUTOMATED:** Paper trades hourly via cron (18 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Mar 27 (00:30): H-021/H-012/H-062 rebal + H-039 exit SHORT. Mar 28: H-059. Mar 29: H-031/H-049/H-052/H-053. Apr 3: H-063 expiry. Apr 6-10: H-056 v3 re-opt with H-076.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 79) archived to `memory/session_archive.md`._

### Session 2026-03-24 review (session 80)
- Goal: Review — full system health check, MTM update, demo recovery, H-011 R7 sustaining
- Focus: Paper trade monitoring, demo account recovery, H-019 vs H-024 gap analysis
- Done: 16/16 runners OK (no new daily bar since Mar 23). **Demo**: $99,720 (-0.28%, recovered from -1.51%). **Internal MTM**: $160,846 (+0.53%, up from +0.30%). BTC $70,869 (down $128). **H-011 R7 sustaining**: +0.28% ann, R27 +0.39% ann. 4/4 recent settlements positive. **H-019 vs H-024 gap widened**: H-019 +0.69% vs H-024 -1.21% (gap 1.90%, up from 1.14%). **H-046 recovered**: -0.14% (from -1.06%). **H-052 turned positive**: +0.64%. Top: H-031 (+4.33%), H-049 (+4.14%), H-062 (+2.40%), H-012 (+2.16%). 8/16 positive, 6 negative, 2 flat. IV: 4 snapshots. All cron operational.
- Next: Tonight (00:30 UTC Mar 25): H-021/H-031/H-049/H-052 rebal + H-039 first trade. H-046 rebal Mar 25. H-012/H-062 rebal Mar 26. H-059 rebal Mar 28.
- Questions added: none
- Self-modifications: none (session 80)

### Session 2026-03-24 review (session 81)
- Goal: Review — full system health check, MTM update, BTC selloff resilience test
- Focus: Paper trade monitoring, demo account health, H-011 R7 improvement, H-019 vs H-024 gap
- Done: 16/16 runners OK (no new daily bar since Mar 23). **Demo**: $99,821 (-0.18%, improved from -0.28%). **Internal MTM**: $160,928 (+0.58%, up from +0.53%). **BTC dropped to $69,231** (down $1,638 / -2.3% from session 80). Portfolio essentially flat — market neutrality working as designed. **H-011 R7 improved**: +0.76% ann (from +0.28%), R27 +1.25% ann. Latest rate +5.70% ann, 5/6 recent settlements positive. 26 total settlements. **H-019 vs H-024 gap widened**: +0.56% vs -1.94% (2.50% spread, up from 1.90%). **H-049 now #1** (+4.33%), H-031 #2 (+4.01%). Demo uPnL net -$514, dominated by BTC LONG loss (-$1,102) offset by OP SHORT gain (+$1,450). 8/16 positive, 2 flat, 6 negative.
- Next: Tonight (00:30 UTC Mar 25): H-021/H-031/H-049/H-052 rebal + H-039 first trade. H-046 rebal Mar 25. H-012/H-062 rebal Mar 26. H-059 rebal Mar 28. Monitor H-011 R7 sustaining.
- Questions added: none
- Self-modifications: none (session 81)

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
- Done: 16/16 runners OK. Mar 24 bar processed by 00:30 cron. **4 rebalances confirmed**: H-021 (new: LONG BTC/ARB/LINK/OP, SHORT DOT/XRP/NEAR/DOGE), H-031 (unchanged), H-049 (new: LONG BTC/NEAR/ETH, SHORT XRP/OP/DOGE), H-052 (new: LONG DOT/LINK/ETH/OP, SHORT NEAR/AVAX/ATOM/ARB). **H-039 first trade**: LONG 0.14124 BTC @ $70,802 for Wed seasonal. **Demo margin crisis fixed**: IM was 98.1% (3x account leverage on 3.04x gross). Changed Bybit leverage from 3x→10x (affects margin only, not exposure). IM dropped to 30.7%, available $69k. NEAR short filled post-fix. **Demo**: $99,712 (-0.29%). **Internal MTM**: $160,214 (+0.13%). **H-011 R7 tripled**: +3.13% ann (from +0.86%), latest rate +6.05% ann, last 5 positive. **H-019 vs H-024 gap closed**: both ~-1.0% (was 2.63% spread). Only 4/16 positive (down from 9/16) — broad pullback in altcoin factors.
- Next: Mar 26 (00:30 UTC): H-012/H-044/H-046/H-062 rebal + H-039 exit LONG/enter SHORT. Mar 27: H-021. Mar 28: H-059. Mar 29: H-031/H-049/H-052/H-053. Monitor H-011 R7 sustaining.
- Questions added: none
- Self-modifications: demo_portfolio_runner.py PERP_LEVERAGE 3→10 (session 83)

### Session 2026-03-25 review (session 84)
- Goal: Review — full system health check, MTM update, H-011 R7 sustaining
- Focus: Paper trade monitoring, demo account recovery, broad market-neutral improvement
- Done: 16/16 runners OK (no new daily bar since Mar 24). **Demo**: $100,078 (+0.08%, recovered from -0.29%). **Internal MTM**: $160,714 (+0.45%, up from +0.13%). BTC $71,010 (+0.81% 24h). **Broad recovery**: 8/16 positive (up from 4/16 in session 83). Major recoveries: H-012 +2.20% (from +0.39%), H-062 +2.30% (from -0.70%), H-053 +1.29% (from -0.75%), H-019 +0.63% (from -1.08%). **H-011 R7 sustaining**: +3.13% ann (unchanged from session 83), R21 improved to +1.12% ann (from -0.27%). **H-019 vs H-024 gap restored**: +0.63% vs -1.32% (1.95% spread, up from ~0% in session 83). **IV collection**: 5 snapshots (~2000 instruments each), not enough for backtesting yet. Demo positions all drifting <3%, no rebalancing.
- Next: Mar 26 (00:30 UTC): H-012/H-044/H-046/H-062 rebal + H-039 exit LONG/enter SHORT. Mar 27: H-021. Mar 28: H-059. Mar 29: H-031/H-049/H-052/H-053. Monitor H-011 R7/R21.
- Questions added: none
- Self-modifications: none (session 84)

### Session 2026-03-25 review (session 85)
- Goal: Review — full system health check, MTM update, cron verification
- Focus: Paper trade monitoring, demo account recovery, H-011 funding rate analysis
- Done: 16/16 runners OK (no new daily bar since Mar 24). **Demo**: $100,548 (+0.55%, up from +0.08%). **Internal MTM**: $160,892 (+0.56%, up from +0.45%). BTC $71,215 (+0.3%). **Broad improvement**: 9/16 positive (up from 8/16). Major movers: H-031 +5.15% (from +4.08%, #1), H-019 +1.00% (from +0.63%), H-039 +0.54% (first trade gaining). **H-011**: 28 settlements, R7 +2.46% ann, latest rate **+10.95% ann** (strongest single settlement), last 6 all positive, equity climbing $9,848→$9,864. **H-019 vs H-024 gap widened**: +1.00% vs -1.64% (2.64% spread, from 1.95%). Cron verified — 00:30 UTC Mar 26 will trigger H-012/H-044/H-046/H-062 rebalances + H-039 exit LONG/enter SHORT.
- Next: Mar 26 (00:30 UTC): 4 strategy rebalances + H-039 position flip. Mar 27: H-021 rebal. Mar 28: H-059 rebal. Mar 29: H-031/H-049/H-052/H-053 rebal. Monitor H-011 rates.
- Questions added: none
- Self-modifications: none (session 85)

### Session 2026-03-25 review+research (session 86)
- Goal: Review + Research — system health check + IV surface analysis → new options strategy
- Focus: MTM update, IV surface exploratory analysis, H-063 vol selling backtest + deployment
- Done: 17/17 runners OK. **Demo**: $100,592 (+0.59%). **Internal MTM**: $160,681 (+0.43%). BTC $71,673. 9/17 positive, 6 negative, 2 flat. **IV surface analysis** (5 snapshots): BTC long-dated ATM IV stable at ~50%, VRP +4.3% mean (IV > RV 68% of time), near-term IV spikes during selloffs but far-dated barely moves. **NEW H-063: Systematic BTC Short Strangle** — sell 7d 3% OTM BTC strangle, delta-hedge daily, 10% stop. Backtest: **Sharpe 1.54, +52.5% ann, -18.4% DD, 73% WR**. Walk-forward **6/6 positive** (mean Sharpe 1.91). Param robustness **60/60 positive (100%)**. Fee robust (Sharpe 1.24 at 5% spread). Correlation -0.10 vs H-009 — market-neutral. Created paper trade runner, added to cron orchestrator. First entry at 01:00 UTC Mar 26.
- Next: Mar 26 (00:30 UTC): 4 rebalances + H-039 flip. Mar 26 (01:00 UTC): H-063 first trade. Monitor H-063 execution.
- Questions added: none
- Self-modifications: Added H-063 runner to cron orchestrator (session 86)

### Session 2026-03-25 review+research (session 87)
- Goal: Review + Research — system health check + expanded universe analysis + portfolio overlap analysis
- Focus: MTM update, H-072 expanded universe momentum test, H-056 position overlap analysis
- Done: 17/17 runners OK. **Demo**: $100,457 (+0.46%). **Internal MTM**: $170,614 (+0.36%, down from +0.43%). BTC $71,331 (-0.48%). 7/17 positive, 8 negative, 2 flat. **H-011**: R7 +4.99% ann (up from +2.46%), 9/13 settlements positive, rolling avg still in. **H-072 REJECTED**: Expanded 25-asset universe (adding BNB/LTC/APT/TAO/AAVE/WLD/CRV/TRX/FIL/ICP/INJ) makes momentum WORSE — Sharpe drops from 1.12 to -0.04. Only BNB (+0.07) and APT (+0.11) marginally help. Size factor also worse with 25 assets. The 14-asset universe is well-curated. **Position overlap analysis**: H-012 ≡ H-062 (100% agreement, 6/6 positions match — momentum and DD-momentum are effectively identical signals). H-021 ≡ H-046 (4/4 agreement — vol momentum and acceleration are the same). H-056 is heavily net-long BTC/ETH/SOL, short NEAR/ARB/ATOM. H-049 and H-062 (top performers) are NOT in H-056 — future re-optimization should consider adding them.
- Next: Mar 26 (00:30 UTC): 4 rebalances + H-039 flip. Mar 26 (01:00): H-063 first entry. Future session should re-optimize H-056 weights using live correlation data + portfolio overlap insights.
- Questions added: none
- Self-modifications: none (session 87)

### Session 2026-03-25 review+research (session 88)
- Goal: Review + Research — system health check + new factor research (session returns, volume-price divergence)
- Focus: MTM update, H-073 session-based returns, H-074 volume-price divergence factor
- Done: 17/17 runners OK. **Demo**: $100,866 (+0.87%, up from +0.46%). **Internal MTM**: $170,219. BTC $70,967 (-0.5%). 9/17 positive, 6 negative, 2 flat. H-019 vs H-024 gap narrowed to 1.94% (from 2.66%). Rebalances at 00:30 UTC Mar 26 not yet executed (session at 21:00 UTC). **H-073 REJECTED**: Session-based return decomposition (Asia/Europe/US). Europe avg -0.05%/session, US +0.05%. But only 2/14 assets consistent in train/test. Portfolio Sharpe negative in both train and test. After fees completely washed out. **H-074 CONDITIONAL**: Volume-price divergence factor. VL=10, PL=5, REB=7, N=4. Sharpe 1.27 full (+46% ann), **OOS 1.90 > IS 1.23** (unusual positive sign). Split-half 1.49/2.89. After fees Sharpe 0.51 (+18.5%). BUT walk-forward only 2/6 positive. Low correlation with momentum (-0.18). Regime-dependent — works in trending markets, fails in choppy.
- Next: Mar 26 (00:30 UTC): 4 rebalances + H-039 flip. Mar 26 (01:00): H-063 first entry. Verify rebalances and H-063 entry in next session.
- Questions added: none
- Self-modifications: none (session 88)

### Session 2026-03-26 review+research (session 89)
- Goal: Review + Research — verify cron rebalances, H-063 first entry, new factor research
- Focus: MTM update, cron verification, H-075 risk-adj momentum, H-076 price efficiency factor
- Done: 18/18 runners OK. **Demo**: $101,419 (+1.42%, up from +0.87%). 7 trades at 00:31 (H-056 adjusted for H-046 rebal). **Internal MTM**: $170,928. BTC $71,264. **11/18 positive** (up from 9/17). Key: H-021 recovered to flat (-0.04% from -1.60%), H-019 surged +1.54% (from +0.63%), H-046 turned positive (+0.27% from -0.72%). **H-046 rebalanced**: new LONG OP/ATOM/ARB/SUI, SHORT BTC/SOL/DOT/NEAR. **H-039 flipped**: SHORT for Thu. **H-063 FIRST TRADE**: Sold 73000C+69000P strangle, expiry Apr 3, premium $364, IV 48.94%, equity $10,008 (+0.08%). **H-075 REJECTED**: Risk-adjusted momentum. Split-half fails (11.02/-2.63), corr 0.76 with H-012. Risk-adjustment hurts at LB≥60. **H-076 CONFIRMED+DEPLOYED**: Price efficiency factor (abs(net_move)/sum(range)). True daily Sharpe 1.94, WF 6/6, corr **0.04** with H-012 — genuinely novel signal. 77% params positive. Deployed: LONG OP/NEAR/ATOM/ARB, SHORT ADA/DOGE/SUI/XRP. Added to cron (18 runners). **METRICS BUG NOTED**: lib/metrics.py sharpe uses 8760 (hourly) for daily data — all daily Sharpes inflated ~5x. Relative comparisons valid. H-019 vs H-024 gap widened to 3.22%.
- Next: Mar 27 (00:30): H-012/H-021/H-062 rebalances + H-039 exit SHORT. Monitor H-063 delta hedge. Monitor H-076 first days. Consider killing H-024 at 2-week mark (Mar 31).
- Questions added: none
- Self-modifications: Added H-076 runner, added to cron orchestrator (session 89)

### Session 2026-03-26 review+research (session 90)
- Goal: Review + Research — MTM update, H-056 re-optimization, new factor research
- Focus: Paper trade monitoring, H-056 v2 (H-046→H-049 swap), H-077 reversal + H-078 skewness backtests
- Done: 18/18 runners OK. **Demo**: $102,314 (+2.31%, up from +1.42%). **Internal MTM**: $181,926. BTC ~$70,500 (-1.1%). **11/18 positive**, 5 negative, 2 flat. **H-056 v2 deployed**: Replaced H-046 with H-049. H-046 had 4/4 position overlap with H-021 (redundant). H-049 is #2 performer with negative corr vs H-031 — better diversifier. 11 trades executed (SUI/DOT closed, OP flipped to SHORT, BTC/ETH increased). **H-063 vol selling healthy**: BTC dropped to $70,503 but well within 73000C/69000P strikes. Premium accruing, equity $10,018 (+0.18%). Delta hedge active. **H-077 REJECTED**: Short-term reversal factor. Only 12% params positive, best Sharpe 0.165, annual return -5.3%. Crypto too correlated for reversal. **H-078 REJECTED**: Skewness factor (contrarian direction). 29% params positive, best Sharpe 0.392, but true daily Sharpe ~0.08 after metrics correction. WF 4/4 positive with param selection but insufficient standalone alpha.
- Next: Mar 27 (00:30): H-021/H-012/H-062 rebal + H-039 exit SHORT. Apr 3: H-063 expiry. Apr 6-10: H-056 v3 re-optimization with H-076. Consider killing H-024 at Mar 31.
- Questions added: none
- Self-modifications: demo_portfolio_runner.py H-046→H-049 swap (session 90)
