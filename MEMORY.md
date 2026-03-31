# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity $100,814 (+0.81%). BTC $66,644.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x). No H-011, H-009, H-046.
- **H-011 status**: DROPPED from demo. Internal paper trade IN. Capital $9,865 (-1.35%). Funding neg.
- **Internal paper trades:** 18 runners active (H-024 killed). Session 114. BTC $66,644.
- **Top performers**: H-019 (+7.44%), H-031 (+4.52%), H-039 (+4.35%), H-012 (+2.42%), H-044 (+1.79%). **9/18 positive**, 1 flat, 8 negative.
- **H-063 status**: Vol selling strangle — BTC $66,806, put strike $69,000 — PUT ITM by $2,194. MTM $9,973 (-0.27%). **$973 buffer to stop**. 3.4d to expiry.
- **H-024 KILLED**: H-019 won comparison +7.44% vs -0.20% (7.64% gap over 13 days).
- **H-052 alert**: Dropped to -3.74% (was +0.94%). Premium contrarian struggling in BTC decline.
- **Research**: 149 total hypotheses. H-146/H-147/H-148/H-149 all REJECTED.
- **System fixes**: Position-count guard added to ALL 13 multi-asset runners. Double-write log bug fixed. H-031 rebal state fixed.
- **AUTOMATED:** Paper trades hourly via cron (18 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Mar 30 bar (00:30 UTC Mar 31): H-021/H-031/H-053/H-076 rebal. Mar 31 bar: H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 104) archived to `memory/session_archive.md`._

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

### Session 2026-03-30 review+research+bugfix (session 110)
- Goal: Review + Research + System — MTM update, H-053 repair, min-asset guard for all runners, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $67,486 +0.98%), H-063 approaching breakeven, H-053 broken rebalance fix, H-137/H-138/H-139 backtests
- Done: 19/19 runners OK. **Demo**: $100,365 (+0.37%, down from +3.06%). BTC $67,486 rally hurt short side. **11/19 positive** (was 8), 8 negative. Top: H-031(+5.65%), H-039(+4.35%), H-012(+3.26%). **H-063 near breakeven**: $10,018 (+0.18%, up from -1.58%!), $1,018 buffer, 4.0d to expiry. **BUG FOUND**: H-053 broken rebalance Mar 29 — API failure loaded 2/14 assets, silently dropped $676 in gains. **FIXED**: Capital restored $9,549→$10,159. **Added min-asset guard (>=7/14) to all 14 multi-asset runners** to prevent recurrence. **H-049** rebalanced to 3 positions (LSR data partial). **Research**: **H-137 REJECTED** (kurtosis regime — 51% IS, OOS -1.136, overfitting). **H-138 REJECTED** (correlation fragility — borderline: fragility dir 90% positive, WF OOS 1.022 but split-half 0.022, only 53% overall). **H-139 REJECTED** (volume-clock — 52% IS, OOS -0.198, split-half -0.363).
- Next: Mar 30 bar: H-053/H-076/H-021 rebal. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: min-asset guard added to 14 runners, H-053 state repaired

### Session 2026-03-30 review+research (session 111)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $67,847 +0.54%), H-063 vol selling profitable, H-140/H-141/H-142 backtests
- Done: 19/19 runners OK. **Demo**: $100,872 (+0.87%, up from +0.37%). BTC $67,847. **13/19 positive** (best session yet!), 5 negative, 1 flat. Top: H-031(+5.16%), H-039(+4.35%), H-012(+2.51%). **H-063 profitable**: $10,073 (+0.73%, up from +0.18%), $1,073 buffer, 3.8d to expiry — time decay winning. **H-019 vs H-024**: gap 1.39% (narrowed from 1.67%). **H-011**: still losing ($15 funding vs $149 fees). **Research**: **H-140 REJECTED** (realized skewness — 11% IS positive, WF 2/6, split-half H1 -1.27). **H-141 REJECTED** (gap reversion — outstanding stats but corr 0.44>0.40 threshold + degenerate signal in 24/7 crypto where gap=0). **H-142 REJECTED** (range compression — 0% IS positive, complete failure).
- Next: Mar 30 bar: H-021/H-031/H-053/H-076 rebal. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 111)

### Session 2026-03-30 review+research (session 112)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $67,285 -0.83%), H-063 vol selling pullback, H-143/H-144/H-145 backtests
- Done: 19/19 runners OK. **Demo**: $101,297 (+1.30%, up from +0.87%). BTC $67,285. **8/19 positive**, 2 flat, 9 negative (BTC drop hurt). Top: H-031(+6.25%), H-039(+4.35%), H-012(+3.64%), H-062(+3.48%). **H-063 pulled back**: $9,967 (-0.34%, was +0.73%), PUT ITM by $1,804, $967 buffer to stop, 3.6d to expiry. **H-019 vs H-024**: gap 1.32% (narrowed). **Research**: **H-143 REJECTED** (short-term reversal — 22% IS positive, WF 3/6 OOS -0.724, split-half -0.077. Reversal anomaly doesn't transfer to crypto). **H-144 CONFIRMED** (idiosyncratic vol — 92% IS positive, WF **6/6** OOS 1.99, H-012 corr 0.010. BUT H-019 corr **0.72** — near-substitute for total vol, regime-dependent). **H-145 REJECTED** (DV stability — stable_long 29% IS. Erratic_long 89% positive but H1/H2 regime split).
- Next: Mar 30 bar: H-021/H-031/H-053/H-076 rebal. Mar 31: Kill H-024, H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 112)

### Session 2026-03-30 backtest (session 113)
- Goal: Backtest — H-144 idiosyncratic vol factor full validation
- Focus: Confirming H-144 with 4/4 criteria (IS 92%, WF 6/6 OOS 1.99, split-half stable, low corr H-012 0.01)
- Done: H-144 CONFIRMED. But H-019 corr 0.72 — near-substitute for total vol. Not deploying as paper trade due to redundancy.
- Next: Session 114 review + research
- Questions added: none
- Self-modifications: none (session 113)

### Session 2026-03-31 review+research+system (session 114)
- Goal: Review + Research + System — MTM update, kill H-024, system hardening, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,644 -0.95%), H-024 kill, position-count guards, H-146/H-147/H-148 backtests
- Done: 18/19 runners OK (H-024 killed). **Demo**: $100,814 (+0.81%). BTC $66,644. **9/18 positive**, 1 flat, 8 negative. **H-019 surged to +7.44%** (low-vol shorts profiting from BTC decline). **H-024 KILLED**: H-019 won decisively +7.44% vs -0.20% (7.64% gap). **H-052 alert**: dropped to -3.74% (was +0.94%). **H-063**: $9,973 (-0.27%), $973 buffer, 3.4d to expiry — manageable. **H-053 positions empty** since session 110 repair — will re-enter on Mar 30 bar. **H-031 rebal state fixed** (positions unchanged but date tracking was wrong). **System**: Position-count guard added to ALL 13 multi-asset runners (prevents corrupted rebalances). Double-write log bug fixed in orchestrator. **Research**: **H-146 REJECTED** (lead-lag spillover — 0/18 positive, crypto has no daily lead-lag). **H-147 REJECTED** (volume skewness — 83% IS, WF 4/6, IS/OOS 1.03, but noisy+0.33 corr momentum+33% DD). **H-148 REJECTED** (DD speed — 58% = noise).
- Next: Mar 30 bar (00:30 UTC Mar 31): H-021/H-031/H-053/H-076 rebal. Mar 31 bar: H-012/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: position-count guard in 13 runners, orchestrator log fix, H-031 state fix (session 114)

### Session 2026-03-31 backtest (session 115)
- Goal: Backtest — H-149 Volume Concentration Factor (up-day volume %)
- Focus: Cross-sectional factor: % of volume on close>open days over rolling window. Long highest buying pressure, short lowest.
- Done: **H-149 REJECTED** (1/4 criteria). IS 100% positive (48/48, mean Sharpe 1.479) — but pure overfitting to early bull regime. WF **1/6** positive folds, mean OOS **-0.144** (only fold 1 = 2023 bull run). Split-half H1=3.124, H2=-1.346 (regime collapse). Corr with momentum 0.446 (above 0.40 threshold). Factor captures buying pressure but it IS momentum in disguise — completely regime-dependent and non-additive.
- Next: Continue research (H-150+). Apr 1: H-085 rebal. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 115)

### Session 2026-03-31 backtest (session 116)
- Goal: Backtest — H-151 Conditional Momentum (BTC Regime Switch)
- Focus: BTC SMA regime (up/downtrend) switching between momentum and contrarian cross-sectional positions on 14 altcoins. 96 param combos + static momentum baseline.
- Done: **H-151 REJECTED** (3/5 criteria). IS 86.5% positive, WF **5/6** positive folds mean OOS Sharpe **1.535** — surprisingly strong OOS. But split-half H2 **-0.334** (regime change in 2H 2025). **Key finding**: regime switch adds only +0.011 Sharpe over static momentum IS (need +0.30). WF shows it helps when static momentum fails (folds 2,3,5 static goes negative but conditional stays positive), but IS sweep doesn't confirm it adds value on average. Correlation with static momentum: 0.225 (low — strategy IS different, just not reliably better). Uptrend leg Sharpe 2.37 >> Downtrend leg 1.13 — momentum works much better than contrarian in regime context.
- Next: Continue research. Apr 1: H-085 rebal. Apr 2: H-039 LONG. Apr 3: H-063 expiry.
- Questions added: none
- Self-modifications: none (session 116)
