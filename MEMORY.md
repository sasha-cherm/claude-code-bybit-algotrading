# MEMORY.md — Session Log & State Index

## Current State
- **BYBIT DEMO H-056 v2** (deployed 2026-03-23, v2 2026-03-26): Equity $99,936 (-0.06%). BTC $66,761.
- **H-056 v2 allocation**: H-031(30%,3x)/H-052(23%,3x)/H-053(16%,3x)/H-021(15%,3x)/H-039(10%,1x)/H-049(6%,3x). No H-011, H-009, H-046.
- **H-011 status**: DROPPED from demo. Internal paper trade IN. Capital $9,865 (-1.35%). Net funding $12.62 vs fees $149.24.
- **Internal paper trades:** 18 runners active. Session 117. BTC $66,761.
- **Top performers**: H-031 (+5.34%), H-039 (+4.35%), H-012 (+2.74%), H-019 (+2.26%), H-062 (+1.72%). **12/18 positive**, 6 negative.
- **H-063 status**: Vol selling strangle — **back in negative** as BTC dropped. BTC $66,761, put strike $69,000 — PUT ITM by $2,239. MTM $9,909 (-0.91%). **$909 buffer to stop**. 3.0d to expiry.
- **H-019 stable**: +2.26%. BTC decline helping low-vol shorts.
- **Research**: 157 total hypotheses. H-155/H-156/H-157 all REJECTED.
- **AUTOMATED:** Paper trades hourly via cron (18 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Mar 31 bar (00:30 UTC Apr 1): H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry + H-031 rebal.
- **Open user questions:** None

## Memory Files
| File | Purpose |
|------|---------|
| `memory/state.md` | Live strategy status and paper positions |
| `memory/hypotheses.md` | All hypotheses with outcomes |

## Session Log


_Older sessions (bootstrap through 107) archived to `memory/session_archive.md`._

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

### Session 2026-03-31 review+research+system (session 115)
- Goal: Review + Research + System — MTM update, rebalance verification, demo fix, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $67,127, +0.72%), demo ATOM fix, H-149/H-150/H-151 backtests
- Done: 18/18 runners OK. **Demo**: $100,211 (+0.21%). BTC $67,127. **12/18 positive** (best ratio yet), 6 negative. Top: H-031(+5.34%), H-039(+4.35%), H-012(+2.74%). **H-019 dropped** from +7.44% to +2.26% as BTC rally hurt high-vol shorts. **H-052 recovered** from -3.74% to +0.54% after Mar 30 rebalance. **Demo fix**: ATOMUSDT max order qty (22k) added to runner; order split into 2 chunks, executed. **H-063**: $9,968 (-0.32%), $968 buffer to stop, 3.3d to expiry. **Mar 30 bar rebalances verified**: H-021, H-053 (re-entered), H-076 all rebalanced. **Research**: **H-149 REJECTED** (vol concentration — 100% IS but bull-market artifact, WF 1/6, corr 0.45 with momentum). **H-150 REJECTED** (OI-funding interaction — novel low-corr signal but H1/H2 regime split, WF 3/6). **H-151 REJECTED** (conditional momentum — strong WF 5/6 mean 1.54, but only +0.01 over static, split-half fails).
- Next: Mar 31 bar: H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: ATOMUSDT max order qty added to demo runner (session 115)

### Session 2026-03-31 review+research (session 116)
- Goal: Review + Research — MTM update, H-063 monitoring, demo update, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $67,477, +0.52%), H-063 approaching expiry, H-152/H-153/H-154 backtests
- Done: 18/18 runners OK. **Demo**: $100,035 (+0.04%). BTC $67,477. **13/18 positive** (new best ratio), 5 negative. Top: H-031(+5.29%), H-039(+4.35%), H-012(+2.71%). **H-063 crossed into profit!** $10,043 (+0.43%), $1,043 buffer to stop, 3.1d to expiry — theta decay winning. **H-011 continuing slow decline**: net funding $12.62 vs fees $149.24. **Research**: **H-152 REJECTED** (return entropy — 54% IS positive = noise, H2 -0.408, signal too weak). **H-153 REJECTED** (volume surprise — 100% IS, WF 2/6, classic overfitting, H2 -0.788). **H-154 REJECTED** (corr centrality — 91.7% IS, WF 3/6, excellent -0.216 H-012 corr but folds 5&6 negative, signal dying).
- Next: Mar 31 bar (00:30 UTC Apr 1): H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry + H-031 rebal. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 116)

### Session 2026-03-31 review+research (session 117)
- Goal: Review + Research — MTM update, H-063 monitoring, 3 new factor backtests
- Focus: Paper trade monitoring (BTC $66,761, -1.06%), H-063 vol selling back negative, H-155/H-156/H-157 backtests
- Done: 18/18 runners OK. **Demo**: $99,936 (-0.06%). BTC $66,761. **12/18 positive**, 6 negative. Top: H-031(+5.34%), H-039(+4.35%), H-012(+2.74%). **H-063 back negative**: $9,909 (-0.91%), PUT ITM by $2,239, $909 buffer to stop, 3.0d to expiry — BTC drop hurt, needs stability. **Research**: **H-155 REJECTED** (Amihud illiquidity — liquid_long IS 100%, WF 6/6 mean 1.25, BUT **corr 0.799 with H-031** = same signal, split-half H1=-0.123). **H-156 REJECTED** (funding rate vol — stable_long IS 89.6%, WF 4/6 mean 0.476, BUT split-half **H1=1.712/H2=-0.075** = signal died. Excellent corr 0.013/−0.013 — novel but decayed). **H-157 REJECTED** (range ratio — noisy_long IS 91.7% but WF **3/6** mean **-0.289**, split-half both halves negative).
- Next: Mar 31 bar (00:30 UTC Apr 1): H-012/H-046/H-062 rebal. Apr 1: H-085. Apr 2: H-039 LONG. Apr 3: H-063 expiry + H-031. Apr 4: H-021/H-049/H-052/H-076.
- Questions added: none
- Self-modifications: none (session 117)
