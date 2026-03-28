# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity $101,586 (+1.59%). BTC $66,417. Short side still dominating.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x). No H-011, H-009, H-046.
- **H-011 status**: DROPPED from demo. Internal paper trade IN, 37 settlements. Capital $9,868 (-1.32%).
- **Internal paper trades:** 19 runners active. Session 103. BTC $66,417.
- **Top performers**: H-031 (+4.67%), H-039 (+4.35%), H-049 (+3.00%), H-062 (+2.15%), H-012 (+2.04%). **8/19 positive**, 3 flat, 8 negative.
- **H-063 status**: Vol selling strangle — BTC $66,417, put strike $69,000 — PUT ITM by $2,583. Equity $9,742 (-2.58%). **$742 to stop**. 5.5 days to expiry. Gradually improving.
- **H-019 vs H-024**: +1.04% vs -0.60% — gap 1.64% (stable). Kill H-024 at Mar 31.
- **Research**: 118 total hypotheses. H-116 CONDITIONAL (Hurst exponent, WF 4/5 mean 1.72, corr 0.238). H-117 REJECTED (info ratio, H2 collapse). H-118 REJECTED (OBV trend, split-half -0.509).
- **AUTOMATED:** Paper trades hourly via cron (19 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Mar 29: H-031/H-046/H-049/H-052/H-053/H-059 rebal. Mar 30: H-076. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 93) archived to `memory/session_archive.md`._

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

### Session 2026-03-27 review+research (session 98)
- Goal: Review + Research — MTM update (BTC selloff to $65,966), H-063 critical monitoring, 3 new factor backtests
- Focus: Full MTM update (19 runners), H-063 vol selling stress, H-101/H-102/H-103 backtests
- Done: 19/19 runners OK. **Demo**: $100,834 (+0.83%). BTC $65,966 (-4.3% 24h). **10/19 positive**, 3 flat, 6 negative. Top: H-031(+4.68%), H-039(+4.35%), H-049(+3.54%). **H-063 WORSE**: equity $9,637 (-3.63%), put ITM by $3,035, **$637 to stop**. New low $9,601 at BTC $65,804. Delta hedge 0.095 BTC absorbing damage (BTC -$5,298 from entry, equity -$363). **Research**: H-101 REJECTED (kurtosis, split-half -0.614). H-102 REJECTED (vol stability, 27% positive). H-103 REJECTED (PV correlation, OOS -0.519).
- Next: Mar 28: H-021/H-059 rebal. Mar 29: H-031/H-049/H-052/H-053. Mar 31: Kill H-024. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 98)

### Session 2026-03-28 review+research (session 99)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,027), H-063 vol selling, H-104/H-105/H-106 backtests
- Done: 19/19 runners OK. **Demo**: $100,681 (+0.68%). BTC $66,027. **10/19 positive**, 3 flat, 6 negative. **H-063 improved**: $9,660 (-3.40%, up from -3.63%), $660 to stop. **H-104 REJECTED** (RSI MR, only 3% positive — crypto is momentum-driven, not mean-reverting). **H-105 REJECTED** (CLV, 78% positive, OOS 2.0, WF 0.76 — strong BUT split-half -0.19, regime-dependent). **H-106 REJECTED** (vol skew, 97% IS positive but OOS -0.12 — classic overfitting).
- Next: Mar 28 00:30: H-021 rebal. Mar 29: H-031/H-046/H-049/H-052/H-053. Mar 31: Kill H-024. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 99)

### Session 2026-03-28 review+research (session 100)
- Goal: Review + Research — MTM update, H-021 rebalance verification, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,372), H-063 vol selling recovery, H-107/H-108/H-109 backtests
- Done: 19/19 runners OK. **Demo**: $101,390 (+1.39%, up from +0.68%). BTC $66,372 (-3.5% 24h). **9/19 positive**, 1 flat, 9 negative. Top: H-031(+4.67%), H-039(+4.35%), H-049(+3.00%), H-062(+2.15%), H-012(+2.04%). **H-063 improving**: $9,716 (-2.84%, up from -3.40%), $716 to stop, 6.3d to expiry. **H-021 REBALANCED** (Mar 27 bar): LONG ARB/BTC/DOT/OP, SHORT AVAX/ETH/NEAR/XRP. **H-019 vs H-024 gap 1.64%** (narrowed from 2.38%). **H-107 REJECTED** (range compression, 1% positive). **H-108 REJECTED** (overnight gap, 100% pos but split-half -0.487). **H-109 REJECTED** (short-term reversal, 75% pos but regime-dependent).
- Next: Mar 29: H-031/H-046/H-049/H-052/H-053/H-059 rebal. Mar 30: H-076. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 100)

### Session 2026-03-28 review+research (session 101)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,224 continued decline), H-063 vol selling, H-110/H-111/H-112 backtests
- Done: 19/19 runners OK. **Demo**: $101,796 (+1.80%, up from +1.39%). BTC $66,224 (-3.3% 24h). **8/19 positive**, 2 flat, 9 negative. Top: H-031(+5.32%), H-039(+4.35%), H-049(+2.86%), H-062(+2.44%), H-053(+2.34%). **H-063**: $9,699 (-3.01%, down from -2.84%), $699 to stop, 6.1d to expiry. Low $9,643 earlier today (BTC $65,945). **H-019 vs H-024**: gap 1.83% (widened from 1.64%). **H-110 REJECTED** (skewness, only 25% IS positive, split-half -0.031 — signal reverses between regimes). **H-111 REJECTED** (vol imbalance, 92% IS positive but WF OOS -0.613, split-half 0.009 — regime-concentrated). **H-112 REJECTED** (downside beta, 100% IS positive but split-half -0.455, corr 0.662 with H-024 — redundant).
- Next: Mar 29: H-031/H-046/H-049/H-052/H-053/H-059 rebal. Mar 30: H-076. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 101)

### Session 2026-03-28 review+research (session 102)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,401 recovering), H-063 vol selling, H-113/H-114/H-115 backtests
- Done: 19/19 runners OK. **Demo**: $101,338 (+1.34%, down from +1.80%). BTC $66,401 (-2.2% 24h). **8/19 positive**, 3 flat, 8 negative. Top: H-031(+4.67%), H-039(+4.35%), H-049(+3.00%), H-062(+2.15%), H-012(+2.04%). **H-063 improving**: $9,724 (-2.76%, up from -3.01%), $724 to stop, 5.8d to expiry. **H-019 vs H-024**: gap 1.64% (narrowed from 1.83%). **H-113 REJECTED** (funding-adj momentum, 100% IS positive but corr **0.995** with H-012 — funding adjustment is negligible in crypto). **H-114 REJECTED** (G/L ratio, 90% IS positive but split-half H2 **-0.535** — regime-dependent). **H-115 REJECTED** (autocorrelation, only 63% IS positive, WF **0/5** OOS -0.591 — no signal).
- Next: Mar 29: H-031/H-046/H-049/H-052/H-053/H-059 rebal. Mar 30: H-076. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 102)

### Session 2026-03-28 review+research (session 103)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,417 stable), H-063 vol selling recovery, H-116/H-117/H-118 backtests
- Done: 19/19 runners OK. **Demo**: $101,586 (+1.59%, up from +1.34%). BTC $66,417. **8/19 positive**, 3 flat, 8 negative. Top: H-031(+4.67%), H-039(+4.35%), H-049(+3.00%). **H-063 improving**: $9,742 (-2.58%, up from -2.76%), $742 to stop, 5.5d to expiry. **H-019 vs H-024**: gap 1.64% (stable). **H-116 CONDITIONAL** (Hurst exponent — 95.8% IS positive, WF **4/5** mean OOS **1.718**, split-half 0.332, corr 0.238 with H-012. Genuinely novel signal capturing trending propensity via R/S method. Top params favor 80d lookback). **H-117 REJECTED** (info ratio — 91.7% IS positive, WF 5/5, BUT split-half H2 mean **0.029** — signal collapses in recent data. Corr 0.491 with H-012 — just noisier momentum). **H-118 REJECTED** (OBV trend — 100% IS positive, corr 0.066 with H-012, BUT split-half **-0.509** — signal inverts between halves).
- Next: Mar 29: H-031/H-046/H-049/H-052/H-053/H-059 rebal. Mar 30: H-076. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 103)
