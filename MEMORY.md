# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity $100,834 (+0.83%). Short side dominating (+$8.6k short, -$7.4k long). NEAR short biggest winner (+$3,367).
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x). No H-011, H-009, H-046.
- **H-011 status**: DROPPED from demo. Internal paper trade IN, 19 settlements, net funding +$15.23, fees $149.
- **Internal paper trades:** 19 runners active. Session 98. BTC $65,966 (-4.3% 24h, continued heavy selloff).
- **Top performers**: H-031 (+4.68%), H-039 (+4.35%), H-049 (+3.54%), H-062 (+1.25%), H-012 (+1.23%). **10/19 positive**, 3 flat, 6 negative.
- **H-063 CRITICAL**: Vol selling strangle — BTC $65,966, put strike $69,000 — **PUT ITM by $3,035**. Equity $9,637 (-3.63%). **$637 to stop**. Delta hedge 0.095 BTC. 7 days to expiry. NEW low $9,601 at BTC $65,804.
- **H-019 vs H-024**: +1.09% vs -1.29% — gap 2.38%. H-019 still winning. Kill H-024 at Mar 31.
- **Research**: 103 total hypotheses. H-101 REJECTED (kurtosis, 96% IS but split-half -0.614). H-102 REJECTED (vol stability, 27% positive). H-103 REJECTED (PV corr, OOS failure).
- **AUTOMATED:** Paper trades hourly via cron (19 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053. Mar 30: H-076. Mar 31: Kill H-024. Apr 1: H-085. Apr 3: H-063 expiry.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 91) archived to `memory/session_archive.md`._

### Session 2026-03-26 review+research (session 91)
- Goal: Review + Research — MTM update, H-063 monitoring, new factor research
- Focus: Full MTM update (18 runners), H-063 put proximity warning, 4 new factor backtests
- Done: 18/18 runners OK. **Demo**: $102,522 (+2.52%). **Internal MTM**: $180,955 (true). BTC $69,957 (-1.78%). **11/18 positive**, 1 flat, 6 negative. Top: H-031(+4.12%), H-049(+3.91%), H-062(+2.40%), H-019(+1.92%), H-053(+1.44%). **H-063 WARNING**: BTC approaching 69000P strike (1.4% away), equity still +0.12% but needs monitoring. **H-011**: R7 +3.58% ann (31 settlements, 5/7 positive). **H-019 vs H-024 gap 3.26%** (widening steadily). **Research**: H-079 REJECTED (autocorrelation, WF 2/6). H-080 REJECTED (VWAP=momentum, corr 0.647). H-081 REJECTED (Hurst, 25% positive). H-082 CONDITIONAL (risk-adj carry, WF 4/6, mean 1.09, corr -0.11 with momentum — revisit later). 6 runners not computing MTM (show $9,980 capital-only).
- Next: Mar 27 (00:30): H-012/H-021/H-044/H-062 rebal + H-039 exit SHORT. Monitor H-063 put strike proximity. Apr 3: H-063 expiry. Consider fixing runner MTM bug.
- Questions added: none
- Self-modifications: none (session 91)

### Session 2026-03-26 review+research (session 92)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests, H-085 deployment
- Focus: Full MTM update (19 runners), H-063 put proximity warning, H-083/H-084/H-085 backtests
- Done: 19/19 runners OK. **Demo**: $101,601 (+1.60%, down from +2.52%). **Internal MTM**: $181,439 (+0.80%). BTC $69,464 (-3.21% 24h). **9/19 positive**, 3 flat, 7 negative. Top: H-031(+5.11%), H-049(+4.10%), H-039(+3.36%, Thu SHORT surging). **H-063 WARNING**: BTC $69,464, put $69,000 — only 0.7% OTM. 24h low $69,189. Equity $9,990, $990 to stop. Delta hedge active. **Research**: H-083 CONDITIONAL (idio vol, 94% params positive, corr -0.01 with momentum — near zero, but asymmetric split-half: bad 2024, good 2025-2026). H-084 REJECTED (BTC correlation, only 31% params positive, reversed performance). **H-085 CONFIRMED+DEPLOYED** (turnover velocity, **100% params positive**, best Sharpe 2.08, mean 1.48, WF selected 3/4 positive). Paper trade created with L20_R7_N4: LONG BTC/ARB/OP/ATOM, SHORT ETH/XRP/DOGE/NEAR. Added to cron (19 runners). **H-019 vs H-024**: gap 3.06%.
- Next: Mar 27 (00:30): H-012/H-021/H-044/H-062 rebal + H-039 exit SHORT. Monitor H-063. Apr 1: H-085 rebal. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: Added H-085 runner + cron orchestrator entry (session 92)

### Session 2026-03-26 review+research (session 93)
- Goal: Review + Research — full MTM update, H-063 put ITM monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC selloff), H-063 vol selling under stress, H-086/H-087/H-088 backtests
- Done: 19/19 runners OK. **Demo**: $101,913 (+1.91%, up from +1.60%). BTC $68,865 (-2.85% 24h, -4.0% from session 92). **9/19 positive**, 10 negative. Top: H-031(+5.07%), H-039(+4.21%, Thu SHORT surging), H-049(+3.80%). **H-063 PUT IS ITM** by $135 — BTC $68,865 < $69,000 strike. Equity $9,988 (-0.12%), $988 to stop, delta hedge active. **Research**: H-086 REJECTED (multi-TF momentum composite — corr 0.68 with H-012, single 60d beats composite, 5d momentum is NEGATIVE). H-087 REJECTED (Amihud illiquidity — corr **0.916** with H-031, liquid=large-cap in crypto). H-088 REJECTED (TSMOM — WF param selection 2/6, 56% max DD, unreliable). **System fix**: Orchestrator MTM bug fixed (was reporting capital instead of equity_history). Added DAILY=365 constant to lib/metrics.py. **H-019 vs H-024**: gap 2.67% (narrowed from 3.06%).
- Next: Mar 27 (00:30): H-012/H-044/H-062 rebal + H-039 exit SHORT. Mar 28: H-021/H-059. Monitor H-063 closely. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: run_all_paper_trades.py MTM fix, lib/metrics.py DAILY constant (session 93)

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
- Done: 19/19 runners OK. **Demo**: $100,796 (+0.80%, down from +1.27%). BTC $68,519 (continued decline). **10/19 positive**, 2 flat, 7 negative. Top: H-031(+4.68%), H-039(+4.35%), H-049(+3.54%). **H-063 PUT ITM** by $481 — equity $9,970 (-0.30%), $970 to stop. Low point $9,918 at BTC $68,228. Delta hedge absorbing damage (BTC -$2,745 from entry, equity only -$30). **Research**: H-092 REJECTED (vol-weighted momentum, 100% params positive but corr **0.586** with H-012 — just noisier momentum, WF 0/4 fixed). H-093 CONDITIONAL (trend consistency hit rate, **100% params positive**, WF selected **4/4** mean 1.152, OOS > IS (1.914 vs 1.553), corr 0.214 with H-012 — partially independent. But split-half corr -0.118 — regime-dependent). H-094 REJECTED (volume asymmetry, OOS -0.546 failure, corr **0.633** with H-012 — captures momentum through volume lens).
- Next: Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053. Mar 31: Kill H-024. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 95)

### Session 2026-03-27 review+research (session 96)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC continued selloff to $67,843), H-063 vol selling new low, H-095/H-096/H-097 backtests
- Done: 19/19 runners OK. **Demo**: $100,181 (+0.18%, down from +0.80%). BTC $67,843 (-1.0% from session 95, -4.9% from H-063 entry). **10/19 positive**, 2 flat, 7 negative. Top: H-031(+4.68%), H-039(+4.35%), H-049(+3.54%). **H-063 NEW LOW**: equity $9,899 (-1.01%), put ITM by $1,157. $899 to stop. Delta hedge 0.063 BTC absorbing ($3,475 BTC drop → $101 equity loss). **H-011**: 34 settlements, IN, R27 avg 1.43e-05. **Research**: H-095 REJECTED (semivariance ratio, 97.8% IS positive but WF selected 1/4, split-half asymmetric 1.60/-0.26, regime-dependent). H-096 REJECTED (dispersion, only 28.9% positive, mean Sharpe -0.19, inverse of H-076 but formulation fails). H-097 REJECTED (lead-lag momentum, 37.0% positive, WF selected 1/4, daily lead-lag too fast in crypto).
- Next: Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053. Mar 31: Kill H-024. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 96)

### Session 2026-03-27 review+research (session 97)
- Goal: Review + Research — MTM update (BTC crash to $66,636), H-063 critical monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC -4.1% 24h), H-063 vol selling stress test, H-098/H-099/H-100 backtests
- Done: 19/19 runners OK. **Demo**: $100,764 (+0.76%, up from +0.18%). BTC $66,636 (-4.1% 24h, -6.5% from H-063 entry). **10/19 positive**, 3 flat, 6 negative. Top: H-031(+4.68%), H-039(+4.35%), H-049(+3.54%). **H-063 CRITICAL**: equity $9,739 (-2.61%), put ITM by $2,364, only **$739 to stop**. Delta hedge increased to 0.084 BTC — absorbing damage (BTC -$4,628 but equity only -$261). New low $9,709 at BTC $66,432. **H-011**: IN, 34 settlements, net funding +$17.33 vs $149 fees. **Research**: H-098 REJECTED (BTC-residual momentum, 100% IS positive but corr **0.698** with H-012, split-half 1.84/0.04, WF param 1/3). H-099 REJECTED (CVaR/tail risk, contrarian 100% positive, WF 4/4, BUT corr **0.749** with H-019 — low-vol by another name). H-100 REJECTED (comovement, train 2.2 → test -0.07, split-half **-0.757**).
- Next: Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053. Mar 31: Kill H-024. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 97)

### Session 2026-03-28 backtest (session 99)
- Goal: Backtest — H-105 Close Location Value (CLV) Momentum Quality Factor
- Focus: Full 36-param scan, IS/OOS, walk-forward, split-half, fee sensitivity, correlations
- Done: H-105 REJECTED. 78% params positive (pass), OOS Sharpe 2.005 (pass), WF mean 0.762 (pass), corr H-012 0.343 (pass), but **split-half correlation -0.187** (fail — regime-dependent). WF fold 4 (Oct-Dec 2025) = -1.549 reveals factor reverses in drawdown regimes. Best params LB20_R7_N5. CLV signal partially correlated with H-012 momentum (0.343). Results saved to strategies/h105_close_location/results.json.
- Next: Continue backtest research — H-106+
- Questions added: none
- Self-modifications: none (session 99)

### Session 2026-03-27 review+research (session 98)
- Goal: Review + Research — MTM update (BTC selloff to $65,966), H-063 critical monitoring, 3 new factor backtests
- Focus: Full MTM update (19 runners), H-063 vol selling stress, H-101/H-102/H-103 backtests
- Done: 19/19 runners OK. **Demo**: $100,834 (+0.83%). BTC $65,966 (-4.3% 24h). **10/19 positive**, 3 flat, 6 negative. Top: H-031(+4.68%), H-039(+4.35%), H-049(+3.54%). **H-063 WORSE**: equity $9,637 (-3.63%), put ITM by $3,035, **$637 to stop**. New low $9,601 at BTC $65,804. Delta hedge 0.095 BTC absorbing damage (BTC -$5,298 from entry, equity -$363). **H-011**: IN, 19 settlements, net funding +$15.23 vs $149 fees (still underwater on fees). **Research**: H-101 REJECTED (return kurtosis, **96% IS positive**, mean 0.514, corr **-0.009** with H-012 — genuinely novel. BUT split-half **-0.614** — extreme regime dependence. H1 mean 0.006 vs H2 mean 1.637. WF selected 1/4. Only works in late 2025+). H-102 REJECTED (volume stability CV, only 27% positive, mean -0.259, OOS -0.639, split-half -0.031). H-103 REJECTED (price-volume correlation, 75% IS but OOS -0.519, WF selected 2/4 mean -0.110, corr 0.428 with H-012).
- Next: Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053. Mar 31: Kill H-024. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 98)

### Session 2026-03-28 backtest (session 100)
- Goal: Backtest — H-106 Volume Profile Skewness Factor
- Focus: 72-combo param scan (both directions), 60/40 IS/OOS, 6-fold walk-forward, split-half, factor correlations
- Done: H-106 REJECTED. Contrarian direction dominates (97% params positive, mean Sharpe 0.935, best 1.792 full-period). But OOS Sharpe -0.122 (fail). Split-half cross-param correlation 0.014 (near zero — no persistent structure). WF mean 0.931 but fold variance extreme ([-0.36, 2.31, -0.11, 1.88]). Momentum direction barely works (8% positive). Contrarian signal is a regime artifact, not a stable factor. Corr H-012=0.068, H-031=0.150 (genuinely novel signal, just not robust). Results: strategies/h106_vol_skew/results.json.
- Next: Continue cross-sectional factor research — H-107+
- Questions added: none
- Self-modifications: none (session 100)
