# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity $100,181 (+0.18%). Short side dominating (+$5.5k net). SOL long biggest loser (-$1,982).
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x). No H-011, H-009, H-046.
- **H-011 status**: DROPPED from demo. Internal paper trade IN, 34 settlements, R27 avg 1.43e-05 (positive).
- **Internal paper trades:** 19 runners active. Session 96. BTC $67,843 (continued selloff from $68,519).
- **Top performers**: H-031 (+4.68%), H-039 (+4.35%), H-049 (+3.54%), H-062 (+1.25%), H-012 (+1.23%). **10/19 positive**, 2 flat, 7 negative.
- **H-063 WARNING**: Vol selling strangle — BTC $67,843, put strike $69,000 — **PUT ITM by $1,157**. Equity $9,899 (-1.01%). $899 to stop. Delta hedge 0.063 BTC. 7 days to expiry. NEW low $9,899 at BTC $67,789.
- **H-019 vs H-024**: +1.09% vs -1.29% — gap 2.38%. H-019 still winning. Kill H-024 at Mar 31.
- **Research**: 97 total hypotheses. H-095 REJECTED (semivariance ratio, WF 1/4). H-096 REJECTED (dispersion, 29% positive). H-097 REJECTED (lead-lag, 37% positive).
- **AUTOMATED:** Paper trades hourly via cron (19 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053. Mar 30: H-076. Mar 31: Kill H-024. Apr 1: H-085. Apr 3: H-063 expiry.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 86) archived to `memory/session_archive.md`._

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

### Session 2026-03-27 backtest (session 97 — H-098)
- Goal: Backtest — H-098 BTC-Residual Momentum (cross-sectional alpha after removing BTC beta)
- Focus: H-098 full 90-combo param scan + walk-forward + split-half + H-012 correlation + fee sensitivity
- Done: **H-098 REJECTED**. Signal: residual return = cumret_i - beta_i * cumret_btc. 100% params positive IS (mean Sharpe 1.138), best LB120_R14_N3 (1.765). But: split-half half1=1.844 vs half2=0.035 — factor collapses in 2025+. WF fixed 3/4 (mean 0.644), WF selected 1/3 (mean -0.239 — severe param overfit). **Correlation with H-012: 0.698** — captures same momentum signal. Factor adds no diversification and degrades OOS. Strategy file: `strategies/h098_residual_mom/backtest.py`. Bug fixed: pandas alignment issue in rolling beta computation (needed numpy arrays to avoid DataFrame outer-product on DatetimeIndex columns).
- Next: Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053. Mar 31: Kill H-024. Apr 3: H-063 expiry. Continue researching new factors.
- Questions added: none
- Self-modifications: none (session 97)
