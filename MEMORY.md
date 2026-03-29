# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity $103,060 (+3.06%). BTC $66,829.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x). No H-011, H-009, H-046.
- **H-011 status**: DROPPED from demo. Internal paper trade IN. Capital $9,865 (-1.35%). 40 settlements. 4/5 recent rates negative, R27 declining.
- **Internal paper trades:** 19 runners active. Session 109. BTC $66,829.
- **Top performers**: H-031 (+6.04%), H-039 (+4.35%), H-012 (+3.64%), H-062 (+3.27%), H-049 (+2.94%). **8/19 positive**, 11 negative.
- **H-063 status**: Vol selling strangle — BTC $66,829, put strike $69,000 — PUT ITM by $2,171. MTM $9,842 (-1.58%, improving). **$842 MTM to stop**. 4.6d to expiry. Time decay in our favor.
- **H-019 vs H-024**: +1.48% vs -0.49% — gap 1.97%. Kill H-024 at Mar 31.
- **Research**: 136 total hypotheses. H-134 REJECTED (gap reversal, split-half -0.808). H-135 REJECTED (autocorrelation, 40% IS). H-136 REJECTED (RS persistence, OOS degrades).
- **AUTOMATED:** Paper trades hourly via cron (19 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Mar 30 (00:30 UTC): H-031/H-049/H-052/H-053/H-076 rebal. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 99) archived to `memory/session_archive.md`._

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

### Session 2026-03-28 review+research (session 104)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,864 recovering), H-063 vol selling recovery, H-119/H-120/H-121 backtests
- Done: 19/19 runners OK. **Demo**: $100,526 (+0.53%, down from +1.59%). BTC $66,864 (+0.67% from last). **9/19 positive**, 1 flat, 9 negative. Top: H-031(+5.37%), H-039(+4.35%), H-012(+2.47%). **H-063 much improved**: $9,963 (-0.37%, up from -2.58%), $963 to stop, 5.6d to expiry, only $182 from breakeven. **H-019 vs H-024**: gap 2.16% (widened from 1.64%). **H-011**: IN, 38 settlements, R27 declining to 1.316e-05, two negative rates. **H-119 REJECTED** (Amihud illiquidity — 100% IS positive, Sharpe 2.10, BUT split-half **-0.622**, only 2 WF folds, corr 0.431 H-012). **H-120 REJECTED** (relative volume spike — 100% IS positive, BUT WF **0/2** OOS **-2.916**, classic overfitting). **H-121 CONDITIONAL** (VWAP deviation — 91.7% IS positive, WF **4/6** mean 0.712, split-half 0.366, corr 0.388 H-012. Decent but moderate momentum overlap).
- Next: Mar 29: H-031/H-046/H-049/H-052/H-053/H-059 rebal. Mar 30: H-076. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 104)

### Session 2026-03-28 review+research (session 105)
- Goal: Review + Rebalance + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,926 stable), H-063 vol selling analysis, H-122/H-123/H-124 backtests
- Done: 19/19 runners OK. **Demo**: $100,742 (+0.74%). BTC $66,926. **9/19 positive**, 3 flat, 7 negative. Top: H-031(+4.67%), H-039(+4.35%), H-049(+3.00%). H-009 improved dramatically (-2.10%→-0.09%, SHORT profiting). H-076 turned positive (+0.07%). **H-063**: MTM $9,832 (-1.68%), intrinsic $9,967 (-0.33%). Premium $364 > intrinsic put cost $291. $832 MTM buffer to stop. 5.4d to expiry. **H-019 vs H-024**: gap 1.64% (narrowed from 2.16%). **Research**: **H-122 REJECTED** (candle conviction — **0% IS positive**, all 60 params negative. Signal inverts: clean moves = exhaustion in crypto). **H-123 REJECTED** (vol-price elasticity — 23% IS positive, WF **1/6**, noisy). **H-124 REJECTED** (CLV — overall 46.5% IS positive, BUT momentum direction **84.7%** positive. Overlaps H-012 at corr 0.448 — just another way to capture momentum). Rebalances for H-031/H-046/H-049/H-052/H-053/H-059 due after 00:30 UTC Mar 29 via cron.
- Next: Mar 29 (auto): 6 rebalances. Mar 30: H-076 rebal. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 105)

### Session 2026-03-29 review+research (session 106)
- Goal: Review + Research — MTM update, rebalance verification, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,516, continued slide), H-063 vol selling, H-125/H-126/H-127 backtests
- Done: 19/19 runners OK. **Demo**: $101,453 (+1.45%). BTC $66,516 (-0.61% from session 105). **7/19 positive**, 3 flat, 9 negative. Top: H-031(+6.06%), H-039(+4.35%), H-012(+3.42%). H-046/H-059 rebalanced on Mar 28 bar; H-031/H-049/H-052/H-053 due Mar 29 bar (00:30 UTC Mar 30). **H-063**: MTM $9,763 (-2.37%), $763 buffer to stop, 5.3d to expiry. Premium $364 barely covers intrinsic $348. **H-011**: IN, R27=1.06e-05. **Research**: **H-125 REJECTED** (wick ratio — 50% IS positive, OOS **-1.551**, WF 4/6 mean 0.588 but direction unstable, corr 0.051 H-012). **H-126 REJECTED** (return consistency — 50% IS positive, OOS **-1.662**, WF **3/6** mean **-0.247**, corr 0.235 H-012). **H-127 REJECTED** (vol-price divergence — div_long 95.8% IS positive Sharpe 2.35 BUT WF **2/6** mean **-0.007**, direction instability, corr 0.372 H-012).
- Next: Mar 30: H-031/H-049/H-052/H-053/H-076 rebal. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 106)

### Session 2026-03-29 review+research (session 107)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,713 recovering), H-063 vol selling improvement, H-128/H-129/H-130 backtests
- Done: 19/19 runners OK. **Demo**: $101,779 (+1.78%, up from +1.45%). BTC $66,713 (+0.30% from session 106). **8/19 positive**, 2 flat, 9 negative. Top: H-031(+6.09%), H-039(+4.35%), H-012(+3.23%). **H-063 improving**: $9,814 (-1.86%, up from -2.37%), $814 buffer to stop, 5.1d to expiry, $686 time value decaying for us. **H-019 vs H-024**: gap 2.03% (stable). BTC funding rates mostly negative. **Research**: **H-128 REJECTED** (DV velocity — long_accel 97.2% IS positive, Sharpe 1.91, BUT WF **3/6** mean **-1.161**, split-half **-0.243**. Strong IS / weak OOS overfitting). **H-129 REJECTED** (intraday vol ratio — 50% IS positive, split-half **-0.817**, signal inverts. Corr H-076 only 0.091). **H-130 REJECTED** (funding momentum — 28.7% IS positive, WF **2/6**, split-half **-1.005**. Signal worked early then fully decayed. Corr H-053 0.201).
- Next: Mar 30: H-031/H-049/H-052/H-053/H-076 rebal. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 107)

### Session 2026-03-29 review+research (session 108)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,718 flat), H-063 vol selling stable, H-131/H-132/H-133 backtests
- Done: 19/19 runners OK. **Demo**: $102,245 (+2.25%, up from +1.78%). BTC $66,718 (flat). **8/19 positive**, 1 flat, 10 negative. Top: H-031(+6.14%), H-039(+4.35%), H-012(+3.26%). **H-063 stable**: $9,817 (-1.83%), $817 buffer to stop, 4.9d to expiry. **H-011 R27 declining** to 8.15e-06, 4 consecutive negative funding rates. **H-019 vs H-024**: gap 1.75% (narrowed from 2.03%). **Research**: **H-131 REJECTED** (close-to-range — 44% IS positive, split-half unstable, regime-dependent). **H-132 REJECTED** (return dispersion timing — 33% IS positive, parameter-sensitive, WF fails best params). **H-133 REJECTED** (consecutive direction — 29% IS positive, split-half both halves negative, IS/OOS ratio 0.23).
- Next: Mar 30: H-031/H-049/H-052/H-053/H-076 rebal. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 108)

### Session 2026-03-29 review+research (session 109)
- Goal: Review + Research — MTM update, H-063/H-011 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,829 +0.17%), H-063 vol selling improving, H-134/H-135/H-136 backtests
- Done: 19/19 runners OK. **Demo**: $103,060 (+3.06%, up from +2.25%). BTC $66,829. **8/19 positive**, 11 negative. Top: H-031(+6.04%), H-039(+4.35%), H-012(+3.64%). **H-063 improving**: $9,842 (-1.58%, up from -1.83%), $842 buffer to stop, 4.6d to expiry. **H-011**: 40 settlements, 4/5 recent rates negative, R27 declining. **H-019 vs H-024**: gap 1.97% (widened from 1.75%). **Research**: **H-134 REJECTED** (overnight gap reversal — 100% IS positive Sharpe 2.51, BUT split-half **-0.808**, rebal period has no effect). **H-135 REJECTED** (mean reversion speed — only 40% IS positive, mean Sharpe -0.21, WF **0/6** — autocorrelation doesn't work as XS factor). **H-136 REJECTED** (RS persistence — 100% IS positive Sharpe 1.15, BUT OOS degrades: train 1.89 → test 0.46, split-half H2 0.41, corr 0.458 with H-012 — noisier momentum).
- Next: Mar 30: H-031/H-049/H-052/H-053/H-076 rebal. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 109)
