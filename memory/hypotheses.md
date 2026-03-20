# Hypotheses

## Live (Paper Trading)

## H-009: BTC Daily EMA Trend Following with Vol Targeting
- Status: LIVE (paper trade since 2026-03-16)
- Idea: BTC-only daily EMA(5/40) crossover with position-level vol targeting. Most defensible variant of H-008 — no asset selection needed, OOS-validated.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D (daily)
- Logic: Long when EMA(5) > EMA(40), short when EMA(5) < EMA(40). Position size scaled by target_vol / realized_vol (30-day lookback). Cap at 2x notional.
- Data: BTC only, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). OOS: 30% fixed split (~220 days).
- Result: Backtest OOS Sharpe 0.94, VT 20% gives +11.8% annual at 12.9% DD. 15/15 params positive. Paper trade started 2026-03-16: LONG 0.054885 BTC @ $73,524 (0.40x leverage).
- Notes: Part of multi-strategy portfolio (H-010). Contributes ~30% of target allocation. Uncorrelated with H-011 (r=0.037).
- Sessions: [2026-03-16 analyze, 2026-03-16 paper trade]

## H-011: Leveraged Funding Rate Arbitrage (5x)
- Status: LIVE (paper trade since 2026-03-16)
- Idea: Delta-neutral funding rate collection at 5x leverage. Long BTC spot + short BTC perp, collecting positive funding rates with rolling-27 filter.
- Instrument: futures + spot (BTC/USDT)
- Timeframe: 8h (funding settlement)
- Logic: Hold delta-neutral position (short perp + long spot) when 27-period rolling avg funding rate > 0. At 5x leverage, funding income scales linearly. Enter/exit based on rolling filter.
- Result:
  - **Full-period (2yr) at 5x**: +38.2% annual, 0.4% DD, Sharpe 24.89
  - **Walk-forward OOS (40%) at 5x**: +25.4% annual, 0.14% DD, Sharpe 29.9
  - **Conservative (last 6mo) at 5x**: +16.7% annual, 0.15% DD
  - **Correlation with H-009**: 0.037 (near zero — excellent diversifier)
  - **Portfolio 30% H-009 / 70% H-011 at 5x**: Sharpe 2.43, +34% return, 7.2% DD
- Notes: Derived from H-005 (rejected at 1x for low returns). Leverage scales returns linearly for delta-neutral strategy. Key risk: funding rates declining (22.7% → 1.6% recent). Max consecutive loss at 5x: 0.36% (vs 20% liquidation threshold — very safe). Paper trade started 2026-03-16, currently OUT of position (rolling avg filter).
- Sessions: [2026-03-16 paper trade]

## H-012: Cross-Sectional Momentum (14 Crypto Assets, Daily)
- Status: LIVE (paper trade since 2026-03-16)
- Idea: Rank 14 crypto assets by 60-day return, long top 4, short bottom 4. Market-neutral cross-sectional momentum.
- Instrument: futures (14 perps: BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM)
- Timeframe: 1D (rebalance every 5 days)
- Logic: Compute 60-day return for each asset. Rank. Long top 4 (25% each), short bottom 4 (25% each). Rebalance every 5 days using lagged (t-1) ranking.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). ~389 IS trades over 1.8yr. WF: 6 folds x 90d test = 540 total OOS days.
- Result:
  - **In-sample (full)**: Sharpe 1.11, +49.7% annual, 30.6% DD
  - **Rolling walk-forward OOS (6 folds, 90d each)**: Sharpe 0.84, +27.5% annual, 20.6% DD
  - **Param robustness**: 45/45 positive Sharpe (100%), mean 0.54, median 0.57
  - **Fee sensitivity**: Sharpe 0.88 even at 5x fees (very robust)
  - **Correlation with H-009**: 0.015 (near zero)
  - **Correlation with H-011**: -0.050 (slightly negative — excellent)
  - **3-strategy portfolio (20/60/20)**: Sharpe 2.78, +40.1% annual, 10.1% DD
- Notes: Captures cross-sectional momentum premium in crypto (winners keep winning, losers keep losing). Market-neutral so no directional exposure. 5/6 walk-forward folds positive. Rolling OOS 20.6% DD is the main concern — manageable with vol targeting or position sizing. Calendar and equal-weight trend alternatives were also tested and rejected. Paper trade deployed 2026-03-16: LONG BTC/NEAR/ATOM/AVAX, SHORT SOL/SUI/ARB/OP.
- Sessions: [2026-03-16 research session 5, 2026-03-16 paper trade session 6]

## Confirmed
(none — H-012/H-019/H-021/H-024 promoted to LIVE)

## Pending

## H-010: Multi-Strategy Portfolio Research
- Status: BACKTEST — expanded to 3-strategy portfolio
- Idea: Research and combine multiple uncorrelated strategies to achieve Sharpe ≥ 2.0 via diversification.
- Instrument: mixed
- Timeframe: mixed
- Logic: Identify 3-5 strategies with low correlation. Portfolio allocation based on Sharpe contribution.
- Result:
  - **Leveraged funding rate arb**: Best candidate → promoted to H-011. At 5x: +38.2% annual, Sharpe 24.89
  - **Cross-sectional momentum**: Promoted to H-012. OOS Sharpe 0.84, 100% params positive
  - **Weekly momentum**: Best Sharpe 0.63 (4w lookback), +19.2% return but 35.9% DD — not viable
  - **Basis/carry trade**: Essentially same as funding arb (7.3% annual) — no incremental value
  - **Daily mean reversion**: All negative — BTC doesn't mean-revert despite lag-1 autocorrelation -0.08
  - **Portfolio combo (H-009 + H-011)**: 30/70 at 5x → Sharpe 2.43, +34%, 7.2% DD
  - **Conservative combo**: 10/90 at 5x → Sharpe 3.40, +15.4%, 6.8% DD
- Notes: Three-strategy portfolio (H-009 + H-011 + H-012) with 20/60/20 allocation achieves Sharpe 2.78, +40.1%, 10.1% DD. All pairwise correlations near zero. Conservative estimate with declining funding rates still achieves ~20%+ return. Could explore fourth strategy (options vol selling?) for further boost.
- Sessions: [2026-03-16 analyze, 2026-03-16 paper trade, 2026-03-16 research]

## H-001: EMA Crossover Trend Following (BTC Futures)
- Status: REJECTED
- Idea: Classic dual-EMA crossover on BTC/USDT perpetual futures with volatility-scaled position sizing
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Logic: Long when EMA(20) > EMA(50), short when EMA(20) < EMA(50). Position size = target_risk / ATR(14). Stop-loss at 2×ATR. Take-profit at 3×ATR or trail.
- Result: Superseded by H-008/H-009 (daily timeframe works better than 4h).
- Notes: 4h timeframe inferior to daily. H-008 tested daily EMA crossover comprehensively.
- Sessions: [2026-03-15 research, 2026-03-16 analyze]

## Analyzed (Walk-Forward Validated)

## H-008: Multi-Asset Daily Trend Following (Futures Portfolio)
- Status: ANALYZED — partially validated
- Idea: EMA crossover trend following on daily timeframe across a diversified crypto futures portfolio. Equal-weight allocation across top-performing assets selected by in-sample Sharpe.
- Instrument: futures (BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM — 14 assets tested)
- Timeframe: 1D (daily)
- Logic: Long when EMA(5) > EMA(40), short when EMA(5) < EMA(40). Full allocation per asset, equal weight across portfolio assets.
- Result:
  - **In-sample (full)**: Top-3 Sharpe 1.03, +53.4%, 57.3% DD | BTC-only Sharpe 0.70, +22.5%
  - **Fixed-split OOS (30%)**: Top-3 Sharpe 0.94, +34.2%, 19.5% DD | BTC-only Sharpe 0.94, +30.2%, 16.5% DD
  - **Rolling walk-forward (top-5, 6mo rebal)**: Sharpe -0.84, -43.4% — **FAILS**
  - **Rolling walk-forward (top-3, 3mo rebal)**: Sharpe -0.59, -37.1% — **FAILS**
  - **BTC-only OOS VT 20%**: Sharpe 0.59, +11.8%, 12.9% DD
  - **Top-3 OOS VT 12%**: Sharpe 0.76, +9.7%, 7.2% DD
  - **Param robustness**: 15/15 param sets positive Sharpe (0.50–0.86), mean 0.69
- Notes:
  - **Signal is real**: BTC daily EMA crossover OOS Sharpe 0.94 (higher than IS 0.59), 15/15 params positive
  - **Asset selection is fragile**: rolling walk-forward fails because past Sharpe doesn't predict future for altcoins
  - **Vol targeting works**: controls DD to target level at cost of proportional return reduction
  - **Math ceiling**: Sharpe ~0.65 means max ~15% return at 10% DD. Cannot hit 20%/10% with single strategy
  - **Recommendation**: BTC-only variant (H-009) is paper-trade ready. Multi-asset needs better selection method.
- Sessions: [2026-03-16 backtest, 2026-03-16 analyze]

## Confirmed
(none)

## Rejected

## H-002: Bollinger Band Mean Reversion (BTC Spot)
- Status: REJECTED
- Idea: Buy oversold (below lower BB) with RSI confirmation, sell at mean. Exploit the negative daily autocorrelation observed in BTC.
- Instrument: spot (BTC/USDT)
- Timeframe: 1h
- Logic: Entry: close < BB_lower(20,2) AND RSI(14) < 30. Exit: close > BB_middle(20) OR RSI > 60. Stop-loss: 3% below entry. Spot-only (no shorting).
- Result: Best params: Sharpe -0.56, annual -9.6%, max DD 28.7%, 86 trades, 52% win rate. All 8 parameter sets negative.
- Notes: Long-only spot catches falling knives in 2024-2026 bear/choppy market. Win rate >50% but losses from stop-outs during downtrends dominate. Need long/short capability and regime filter. Superseded by H-006.
- Sessions: [2026-03-15 research, 2026-03-16 backtest]

## H-003: Cross-Asset Momentum Rotation (Multi-Asset Futures)
- Status: REJECTED
- Idea: Rank BTC, ETH, SOL by recent momentum. Go long the strongest, short the weakest. Market-neutral exposure.
- Instrument: futures (BTC/USDT, ETH/USDT, SOL/USDT perps)
- Timeframe: 1h (rebalance weekly)
- Logic: Compute 7-day and 21-day momentum. Long top-1, short bottom-1. Equal dollar exposure.
- Result: Best params (20% size): Sharpe 0.33, annual 3.9%, max DD 38.9%. Conservative (5% size): Sharpe 0.13, annual 0.8%, max DD 12.4%. 6 parameter sets tested.
- Notes: Returns far too low for the drawdown. Only 3 crypto assets are too correlated for meaningful momentum rotation. SOL was the only consistent profit source (from shorting). Would need 10+ uncorrelated assets to work. Not worth pursuing in crypto with limited asset universe.
- Sessions: [2026-03-15 research, 2026-03-16 backtest]

## H-004: Volatility Breakout (BTC Futures)
- Status: REJECTED
- Idea: Enter on volatility expansion beyond recent range, using ATR channel breakout. Exploit the fat tails (kurtosis 3.66).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1h
- Logic: Compute ATR(24) and 24-bar high/low channel (shifted to prior bars). Entry long: close > channel_high + 0.5×ATR. Entry short: close < channel_low - 0.5×ATR. Exit: trail stop at 1.5×ATR or mean reversion to 24-bar midpoint. Max holding period: 48 bars. Vol filter: ATR(24)/ATR(168) > 1.0.
- Result: Best params: Sharpe -0.62, annual -12.2%, max DD 31.7%, 119 trades, 40% win rate. 10 parameter sets tested, all negative.
- Notes: BTC 1h breakouts don't have enough follow-through in 2024-2026 choppy market. Win rate 33-41% with insufficient profit factor. False breakouts dominate. Tried with and without vol filter, various channel widths and trailing stops.
- Sessions: [2026-03-15 research, 2026-03-16 backtest]

## H-005: Funding Rate Arbitrage (BTC Futures)
- Status: REJECTED → superseded by H-011 (leveraged version)
- Idea: Exploit persistent funding rate imbalances on BTC perpetual futures. Short perp + long spot when funding positive. Delta-neutral.
- Instrument: futures + spot (BTC/USDT)
- Timeframe: 8h (funding settlement intervals)
- Logic: Monitor funding rate. When rolling avg funding > threshold, hold short perp + long spot to collect funding payments.
- Result: 2-year avg funding rate: 0.0059%/8h = 6.5% annualized. Best backtest: Sharpe 4.71, annual +1.7%, max DD 0.44% (rolling-27 filter). With simple threshold: Sharpe 15.96, annual +3.1%, max DD 0.20%. Funding declining: Q1 2024 22.7% → Q1 2026 1.6%.
- Notes: Strategy works perfectly (excellent Sharpe, near-zero drawdown) but **absolute returns far too low** (1.7-3.1% annual). H-010 research showed that leveraging to 5x makes this viable: +38.2% annual, 0.4% DD. Promoted to H-011.
- Sessions: [2026-03-16 backtest, 2026-03-16 paper trade]

## H-006: Adaptive Mean Reversion (BTC Futures, Long/Short)
- Status: REJECTED
- Idea: Improved mean reversion using futures (long/short) with regime filter and reversal confirmation.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1h
- Logic: BB(20,2) + RSI(14) with: (1) long AND short signals, (2) regime filter (ATR_24/ATR_168 < threshold = range-bound = trade), (3) reversal confirmation (wait for price to re-enter BB after touching). Exit at BB_middle. Stop: ATR-based.
- Result: Without reversal: best Sharpe -1.44, annual -25.2%, 56% WR. With reversal confirmation: best Sharpe -1.03, annual -13.9%, max DD 35.0%, 167 trades, 60% win rate. 12 parameter sets tested, all negative.
- Notes: Reversal confirmation improved win rate from ~50% to ~60% but still net negative. The mean reversion signal has no real edge on BTC 1h — ~49% of signals actually hit BB_middle within 48 bars. 2x ATR stop distance (1.4% of price) is too tight. Fee drag (0.2% round-trip × 167 trades) compounds the losses.
- Sessions: [2026-03-16 backtest]

## H-007: BTC/ETH Ratio Mean Reversion (Pairs Trading)
- Status: REJECTED
- Idea: Trade the BTC/ETH log ratio z-score as a market-neutral pairs strategy.
- Instrument: futures (BTC/USDT + ETH/USDT perps)
- Timeframe: 1h
- Logic: Compute rolling z-score of log(BTC/ETH). Short ratio (short BTC, long ETH) when z > entry. Long ratio when z < -entry. Exit when z reverts to ±exit_z. Stop at ±stop_z. Each leg 50% of capital (delta-neutral).
- Result: Best params: Sharpe -1.05, annual -15.0%, max DD 35.6%, 105 trades, 62% win rate. 12 parameter sets tested, all negative.
- Notes: Half-life of ratio z-score was 36.9 bars (~1.5 days), suggesting fast reversion. But the ratio has massive structural drift: ETH -44.7% vs BTC +1.8% over 2 years (ratio nearly doubled from ~18 to ~34). Even 7-day adaptive window can't handle this structural divergence. The strategy consistently bets on ratio reversion that doesn't happen because of the fundamental ETH underperformance trend.
- Sessions: [2026-03-16 backtest]

## H-013: Multi-Asset Funding Rate Arbitrage + Dynamic Allocation
- Status: REJECTED
- Idea: Diversify funding rate collection across 14 crypto assets to reduce time-out-of-market when BTC funding is negative. Also tested dynamic portfolio reallocation (shift H-011 capital to H-009/H-012 when OUT).
- Instrument: futures (14 perps: BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM)
- Timeframe: 8h (funding settlement)
- Logic: Track 1: At each settlement, collect funding from all assets with positive rolling-27 avg. Track 2: When H-011 OUT, reallocate 60% to H-009/H-012 (50/0/50 or variants).
- Result:
  - **Multi-asset (all positive, 5x)**: Full period +25.6% ann, Sharpe 6.86 (vs BTC-only +31.6%, Sharpe 10.32)
  - **Multi-asset recent 180d**: -15.8% ann, Sharpe -4.05 (vs BTC-only +7.0%, Sharpe 3.54)
  - **Top-N rotation**: All negative due to fee drag ($4k+ fees vs $1.3k for BTC-only)
  - **Walk-forward**: Multi avg Sharpe 8.76 vs BTC-only 17.06 — BTC-only dominates
  - **Dynamic alloc (50/0/50 when OUT)**: Full Sharpe 2.65 vs static 20/60/20 Sharpe 2.77
  - **Dynamic alloc recent 180d**: Sharpe 1.42 vs static 2.14
  - **Key correlation**: All crypto funding rates correlated r=0.49 with BTC. ETH/ARB 100% positive when BTC negative but rates are low.
  - **Critical insight**: H-011 OUT acts as automatic de-risking (60% idle reduces vol). Reallocating INCREASES drawdown more than returns.
- Notes: Current 20/60/20 static allocation is self-regulating and optimal across all periods tested. Accept H-011 cyclicality. Multi-asset funding rates decline together — no diversification benefit. 14-asset funding rate data cached for future reference.
- Sessions: [2026-03-17 research session 8]

## H-014: Anti-Martingale Pyramiding (BTC Daily)
- Status: REJECTED
- Idea: Buy on N-day high breakout, add to position every N% rise (pyramid), sell all on trailing stop X% from peak. User-suggested strategy.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D (daily)
- Logic: Entry on 20-day high breakout with 10-20% capital. Add 10-20% more every 3-10% rise. Trail stop at 8-15% from peak. Exit everything on stop. Cooldown 5 bars. Long-only or long+short.
- Result:
  - **In-sample**: 88% params positive Sharpe (144 tested). Best Sharpe 0.69, +16.4% ann, 23.1% DD.
  - **Fixed-split OOS (30%)**: All top 5 params negative. Best OOS Sharpe -1.31. Mean -1.85.
  - **Rolling walk-forward (12mo/3mo)**: 1/4 folds positive. Mean OOS Sharpe -1.12.
  - **Long+short mode**: Worse than long-only (shorts hurt in crypto).
  - **Multi-asset**: Very inconsistent. XRP +101% (overfit), SOL -12%, ETH -8.6%.
  - **Correlation with H-009**: 0.424 — moderately correlated (both BTC trend followers).
- Notes: Fundamentally just another trend-following strategy with fancy position sizing. Doesn't survive walk-forward validation — works in strong trending periods but loses in chop. Too correlated with H-009 to provide diversification. Rejected.
- Sessions: [2026-03-17 research session 14]

## H-015: Daily RSI Mean Reversion (BTC Futures)
- Status: REJECTED
- Idea: Long when RSI oversold, short when overbought. Contra-trend strategy to diversify against H-009.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D (daily)
- Logic: RSI(7-21). Long when RSI < 20-40, short when RSI > 60-80. Exit at RSI 40-55. Full allocation.
- Result:
  - **In-sample**: 67% positive Sharpe (120 tested). Best Sharpe 0.97.
  - **Fixed-split OOS**: All top 10 negative except one. Mean OOS Sharpe -0.43.
  - **Rolling walk-forward**: 0/4 folds positive. Mean OOS Sharpe -0.65.
  - **Correlation with H-009**: -0.569 IS, -0.732 OOS — strongly negatively correlated.
  - **Portfolio (H-009+H-015)**: Sharpe improves 0.28→0.34 but negative alpha drags returns.
- Notes: Excellent negative correlation with H-009, but the signal itself has no edge OOS. Combining it reduces DD (19.9%→6.9%) but barely improves Sharpe. Mean reversion on daily BTC doesn't work — confirmed again after H-002/H-006.
- Sessions: [2026-03-17 research session 14]

## H-016: BB Squeeze Breakout (BTC Daily)
- Status: REJECTED
- Idea: Trade Bollinger Band breakouts only after a vol squeeze (bandwidth below 10-30th percentile).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Logic: Detect squeeze (BB bandwidth < N-th percentile of 100-bar history). Trade breakout above/below band. Hold for fixed N bars.
- Result: Only 36% params positive (81 tested). Best Sharpe 1.45 but only 18 trades in 2 years — clear overfit. Mean Sharpe -0.28.
- Notes: Too few signal events on daily timeframe. The high-Sharpe results are artifacts of tiny sample size. Not worth pursuing.
- Sessions: [2026-03-17 research session 14]

## H-017: Multi-Timeframe Momentum Filter (BTC)
- Status: REJECTED
- Idea: Only trade when weekly and daily EMA trends agree. Weekly filters out noise.
- Instrument: futures (BTC/USDT perp)
- Timeframe: Weekly + Daily
- Logic: Weekly EMA(4/12) for trend direction, daily EMA(5-10/20-40) for entry. Only trade when both agree.
- Result: Best Sharpe 0.29, terrible DD (44-51%). Correlation with H-009: 0.892 — essentially redundant.
- Notes: Adding a weekly filter just makes H-009 worse by delaying entries. The weekly EMA signal is too slow for crypto. Redundant with existing strategy.
- Sessions: [2026-03-17 research session 14]

## H-018: Short-Term Reversal (Cross-Sectional, 14 Assets)
- Status: REJECTED
- Idea: Buy recent losers, sell recent winners (1-10 day lookback). Opposite of momentum. Academic short-term reversal factor.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 1-5 days)
- Logic: Rank assets by NEGATIVE of past N-day returns (losers ranked high). Long top quartile, short bottom quartile.
- Result:
  - **72 param sets tested** (lookback 1-10d, rebal 1-5d, N 3-5)
  - **Only 4% positive Sharpe** (3/72)
  - **Best Sharpe: 0.06** — essentially zero edge
  - **Mean Sharpe: -0.71**
- Notes: Crypto momentum dominates at ALL timeframes. Short-term reversal (buying losers) is a losing strategy. Losers keep losing, winners keep winning. This confirms H-012 (momentum) is the right cross-sectional signal. Reversal only works in equities due to institutional rebalancing — absent in crypto.
- Sessions: [2026-03-18 research session 24]

## H-019: Low-Volatility Anomaly (Cross-Sectional, 14 Assets)
- Status: LIVE (paper trade since 2026-03-18)
- Idea: Long low-vol assets, short high-vol assets. Classic cross-sectional factor (low-vol earns risk-adjusted excess returns).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 21 days)
- Logic: Rank assets by NEGATIVE of realized volatility (20d window, low vol ranks high). Long top 3, short bottom 3. Rebalance every 21 days using lagged ranking.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). WF: 8 folds x 80d test = 640 total OOS days.
- Result:
  - **In-sample (full, standard vol V20_R21_N3)**: Sharpe 1.17, +57.8% annual, 47.9% DD
  - **Parameter robustness (standard vol)**: 89% positive (124/140). Mean Sharpe 0.52.
  - **Parameter robustness (downside vol)**: 99% positive (138/140). Mean Sharpe 0.92.
  - **Fee sensitivity**: Sharpe 0.75 at 5x fees (very robust, low turnover).
  - **Walk-forward (8 folds, 80d, standard vol)**: 5/8 positive, mean OOS Sharpe 0.76, median 0.60
  - **Walk-forward (8 folds, 80d, downside vol)**: 7/8 positive, mean OOS Sharpe ~2.24
  - **Adaptive WF (param opt per fold)**: 4/6 positive, mean OOS Sharpe 1.58
  - **Actual H-009 correlation**: -0.094 (slightly negative — corrected from -0.268 BTC proxy)
  - **H-012 correlation**: 0.076 (standard vol), 0.223 (downside vol)
  - **Failing WF folds**: Strong BTC uptrends (avg BTC +31.8% in fails vs -10.1% in passes)
  - **Regime filter**: None improves WF over baseline
  - **Combined factor (LV+Mom)**: 30/70 blend WF mean 1.57 but overlaps with H-012
  - **4-strategy portfolio (15/50/15/20, actual H-009)**: Sharpe 1.75, +23.8%, 14.0% DD (vs 3-strat 1.38)
- Notes: Standard vol variant preferred over downside vol for portfolio use — lower correlation with H-012 (0.076 vs 0.223) and more negative correlation with H-009 (-0.094 vs -0.020), giving better portfolio improvement (Sharpe +0.37 vs +0.01). Main risk: underperforms during strong BTC uptrends. The 48% standalone DD is acceptable in a diversified portfolio (portfolio DD 14%). Critical correction: previous 3-strat Sharpe was 2.78 using BTC proxy for H-009; actual H-009 equity gives 1.38. H-019 brings it to 1.75 — meeting the ≥1.5 target. Paper trade deployed 2026-03-18: LONG ATOM/ARB/XRP (low vol), SHORT DOGE/DOT/NEAR (high vol). Next rebal 2026-04-08.
- Sessions: [2026-03-18 research session 24, 2026-03-18 research session 25, 2026-03-18 paper trade session 26]

## H-020: Funding Rate Dispersion (Cross-Sectional Carry)
- Status: REJECTED
- Idea: Cross-sectional carry trade — long assets with highest funding rates, short lowest. Exploit positioning imbalances.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 1-14 days)
- Logic: Rank assets by rolling average funding rate (7-60 day window). Long top quartile (highest funding), short bottom quartile.
- Result:
  - **50 param sets tested**
  - **0% positive Sharpe** (0/50)
  - **Best Sharpe: -0.06** — no edge whatsoever
  - **Mean Sharpe: -0.63**
- Notes: Complete failure. Crypto funding rates are too correlated across assets (r=0.49 with BTC, confirmed by H-013 analysis). High-funding assets don't outperform relative to low-funding. Cross-sectional carry doesn't work because all assets enter positive/negative funding regimes together. This also confirms H-013's finding that multi-asset funding diversification is futile.
- Sessions: [2026-03-18 research session 24]

## H-021: Volume Momentum Factor (Cross-Sectional, 14 Assets)
- Status: LIVE (paper trade since 2026-03-18)
- Idea: Long assets with highest short-term volume growth relative to long-term average, short lowest. Volume expansion precedes price moves.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3 days)
- Logic: Compute ratio of 5-day avg volume to 20-day avg volume for each asset. Rank. Long top 4 (highest volume surge), short bottom 4. Rebalance every 3 days using lagged ranking.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). 1409 IS trades over 2.0yr. WF: 6 folds x 80d test = 480 total OOS days (180d train).
- Result:
  - **In-sample (VS5_VL20_R3_N4)**: Sharpe 1.52, +63.3% annual, 24.7% DD, 1409 trades
  - **Parameter robustness**: 90% positive (162/180). Mean Sharpe 0.73.
  - **Walk-forward (6 folds, 180d/80d)**: **6/6 positive** (perfect!), mean OOS Sharpe **1.83**, median 1.55
  - **WF folds**: 0.45, 3.26, 3.01, 1.24, 1.86, 1.17 — all positive
  - **Fee sensitivity**: Sharpe 1.63→1.41→1.19→0.76 at 1x→2x→3x→5x fees
  - **Correlation with H-009**: -0.068 (near zero)
  - **Correlation with H-012**: 0.057 (near zero)
  - **Correlation with H-019**: -0.032 (near zero)
  - **Regime analysis**: BTC UP Sharpe 3.67, FLAT 0.92, DOWN 0.18 — works in all regimes
  - **5-strat portfolio (10/40/10/15/25)**: Sharpe 2.10, +31.6%, 12.9% DD
- Notes: **Best WF performance of any strategy tested** (6/6, mean 1.83). Key caveat: ONLY works at high-frequency rebalance (3-day). Low-frequency versions (14-21 day) FAIL WF badly (2/6). This means high turnover (1409 trades) — fee management critical. Must use maker orders. Alternative: VS7_VL20_R3_N4 (IS 1.81, WF 5/6 mean 1.77) also strong. Volume z-score variant (IS 1.91) fails WF. Volume data quality is clean (no zeros, CV 0.43-0.65). Paper trade deployed 2026-03-18: LONG DOT/LINK/XRP/DOGE (vol surge), SHORT ARB/SUI/NEAR/ATOM (vol drop). Next rebal 2026-03-21.
- Sessions: [2026-03-18 research session 28, 2026-03-18 paper trade session 29]

## H-022: Amihud Illiquidity Premium (Cross-Sectional, 14 Assets)
- Status: REJECTED
- Idea: Long illiquid assets (high |return|/volume ratio), short liquid assets. Academic illiquidity premium.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5-21 days)
- Logic: Compute Amihud illiquidity measure: avg(|daily return| / dollar volume) over 10-60 day window. Rank. Long top quartile (illiquid), short bottom quartile.
- Result:
  - **48 param sets tested**
  - **0% positive Sharpe** (0/48)
  - **Best Sharpe: -1.15** — no edge whatsoever
  - **Mean Sharpe: -1.40**
- Notes: Complete failure. Illiquidity premium doesn't exist in crypto. Illiquid assets (small-cap alts) consistently underperform liquid ones. The academic illiquidity premium relies on institutional constraints absent in crypto markets. Longing illiquid crypto = catching falling knives.
- Sessions: [2026-03-18 research session 28]

## H-023: Price-Volume Confirmation (Cross-Sectional, 14 Assets)
- Status: REJECTED
- Idea: Long assets with momentum + volume confirmation (both positive), short assets with momentum but declining volume (exhaustion). Smart money signal.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5-21 days)
- Logic: Ranking = momentum(N-day) * volume_change(M-day). Both dimensions must agree for strong signal.
- Result:
  - **96 param sets tested**
  - **93% positive Sharpe** (89/96). Mean 0.62, best 1.53.
  - **Walk-forward (M60_V20_R5_N3)**: 5/6 positive, mean OOS Sharpe 1.00
  - **Fee sensitivity**: Sharpe 1.27 at 5x fees (excellent)
  - **BUT: Correlation with H-012 = 0.864** — essentially redundant with momentum
- Notes: Strong factor on its own, but is just momentum with a volume multiplier. At 60d momentum lookback, it's nearly identical to H-012 (r=0.864). No portfolio diversification value. Would only be useful as a REPLACEMENT for H-012, not an addition. H-012 is simpler and already deployed — no reason to switch.
- Sessions: [2026-03-18 research session 28]

## H-024: Low-Beta Anomaly (Cross-Sectional, 14 Assets)
- Status: LIVE (paper trade since 2026-03-18) — **comparing against H-019**
- Idea: Long low-beta assets (less sensitive to BTC), short high-beta assets. Rolling 60-day beta vs BTC as market proxy.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 21 days)
- Logic: Compute rolling 60-day beta of each asset vs BTC returns. Rank. Long top 3 lowest-beta, short bottom 3 highest-beta. Rebalance every 21 days using lagged ranking.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). 105 IS trades over ~1.8yr. WF: 6 folds x 80d test = 480 total OOS days (360d train).
- Result:
  - **In-sample (W60_R21_N3)**: Sharpe 1.56, +90.1% annual, 49.2% DD, 105 trades
  - **Parameter robustness**: 100% positive (48/48). Mean Sharpe 1.08.
  - **Walk-forward (6 folds, 360d/80d)**: **5/6 positive**, mean OOS Sharpe **2.12**, median 1.36
  - **WF folds**: 4.78, 1.47, -0.60, 1.25, 0.86, 4.95
  - **Fee sensitivity**: Sharpe 1.56→1.54→1.52→1.48 at 1x→2x→3x→5x fees (extremely robust — only 105 trades)
  - **Head-to-head vs H-019 (vol)**: Beta wins 12/12 at matched params (100%)
  - **Correlation with H-009**: -0.027 (near zero)
  - **Correlation with H-012**: 0.319 (moderate)
  - **Correlation with H-019**: 0.660 (high — related factors)
  - **Correlation with H-021**: 0.069 (near zero)
  - **Portfolio (replacing H-019)**: Sharpe 1.80 → **2.33** (+0.53 improvement)
  - **6-strat (both H-019 + H-024)**: Sharpe 1.96 (worse than replacement — correlated)
  - **Multiple WF configs**: W60_R14_N4 (5/6, mean 1.72), W30_R14_N3 (5/6, mean 1.70)
  - **Idiosyncratic vol variant**: Only 67% positive, corr 0.808 with H-019, not useful
- Notes: **Strongest factor discovery since H-021.** Beta captures systematic risk (sensitivity to BTC), while H-019 captures total risk (including idiosyncratic). Beta is strictly better: higher IS Sharpe, better WF, more fee-robust, and bigger portfolio improvement. Should replace H-019 after parallel paper trade validation. Deployed 2026-03-18: LONG ATOM/OP/BTC (low beta), SHORT XRP/NEAR/SUI (high beta).
- Sessions: [2026-03-18 research session 30]

## H-025: Skewness Factor (Cross-Sectional, 14 Assets)
- Status: REJECTED
- Idea: Long negative-skew assets (underpriced risk), short positive-skew assets (overpriced lottery tickets).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5-21 days)
- Logic: Compute rolling skewness of returns (20-90 day window). Rank by NEGATIVE skewness. Long top quartile, short bottom quartile.
- Result:
  - **48 param sets tested**
  - **Only 15% positive Sharpe** (7/48)
  - **Best Sharpe: 0.49** — weak edge
  - **Mean Sharpe: -0.51**
- Notes: The skewness premium (buying assets with negatively skewed returns, avoiding lottery-like payoffs) doesn't exist in crypto. Crypto asset return distributions are too similar across the universe for cross-sectional differentiation. Only 30d window showed any signal (7 positive), and even those were marginal. The academic skewness premium relies on retail investor preferences absent in crypto.
- Sessions: [2026-03-18 research session 30]

## H-026: Drawdown Distance Factor (Cross-Sectional, 14 Assets)
- Status: REJECTED
- Idea: Long assets near their rolling highs, short assets deep in drawdown. Continuation signal.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5-21 days)
- Logic: Compute close/rolling_max(N-day) for each asset. Rank (closer to peak = higher rank). Long top quartile, short bottom quartile.
- Result:
  - **60 param sets tested**
  - **97% positive Sharpe** (58/60). Mean 0.79, best 1.54.
  - **Walk-forward (W90_R5_N5)**: 3/6 positive, mean OOS Sharpe 1.40, median 0.90
  - **BUT: Correlation with H-012 = 0.682** — essentially momentum in disguise
  - **Correlation with H-019**: 0.353 (moderate)
- Notes: Very strong standalone factor (97% positive) but is fundamentally just another way to measure momentum. Assets near their rolling highs = recent winners = exactly what H-012 captures. The 0.682 correlation confirms this. Walk-forward only 3/6 positive vs H-012's 5/6 — so it's also a weaker version of momentum. No portfolio value.
- Sessions: [2026-03-18 research session 30]

## H-027: Lead-Lag Cross-Sectional Factor (14 Assets, 1h)
- Status: REJECTED
- Idea: BTC moves first, altcoins follow. Long altcoins that haven't responded to BTC's recent move, short over-responders.
- Instrument: futures (14 perps)
- Timeframe: 1h (rebalance every 1-5 days)
- Logic: Compute BTC return over past N hours (4-24h). For each altcoin, compute lag score = BTC_return - altcoin_return. Rank. Long top N, short bottom N.
- Result:
  - **75 param sets tested** (lookback 4-24h, rebal 1-5d, N 3-5)
  - **Only 1% positive Sharpe** (1/75)
  - **Best Sharpe: 0.014** — essentially zero edge
  - **Mean Sharpe: -2.605**
  - **Walk-forward**: Best 3/6 positive, mean OOS 0.378. FAIL.
- Notes: The BTC-altcoin lead-lag effect either doesn't exist at hourly timescales or is already arbitraged away. Short lookbacks (4h, 8h) catastrophic — pure fee drag into noise. The relationship may exist at minute-level but not capturable with hourly bars.
- Sessions: [2026-03-18 review+research session 31]

## H-028: Volume Trend Change Factor (OI Proxy, 14 Assets, 1h)
- Status: REJECTED
- Idea: Assets with accelerating volume (short MA / long MA ratio) attract capital → continuation signal.
- Instrument: futures (14 perps)
- Timeframe: 1h (rebalance every 24-72h)
- Logic: Compute ratio of short-window avg volume to long-window avg volume. Rank. Long top N (volume accelerating), short bottom N.
- Result:
  - **204 param sets tested**
  - **Only 6% positive Sharpe** (12/204)
  - **Best Sharpe: 0.774** (VS6_VL48_R72_N5, 22.1% ann, 24.3% DD) — but narrow params
  - **Mean Sharpe: -1.143**
  - **Walk-forward**: All tested sets FAIL. Best 3/6, mean -0.195.
  - **Fee sensitivity**: Negative at 3x fees.
- Notes: Volume trend as OI proxy has no reliable cross-sectional signal. The few IS-positive results are narrow parameter overfitting. Actual OI data might behave differently but wasn't available in cache.
- Sessions: [2026-03-18 review+research session 31]

## H-029: Hourly Cross-Sectional Momentum (14 Assets, 1h)
- Status: REJECTED
- Idea: Higher-frequency cross-sectional momentum using 1h bars. Potentially different alpha from daily H-012.
- Instrument: futures (14 perps)
- Timeframe: 1h (rebalance every 4-48h)
- Logic: Rank assets by past 24h-336h returns using 1h bars. Long top N, short bottom N.
- Result:
  - **90 param sets tested** (lookback 24-336h, rebal 4-48h, N 3-5)
  - **16% positive Sharpe** (14/90)
  - **336h (14-day) lookback ONLY works**: 93% sub-params positive. All shorter lookbacks 0%.
  - **Walk-forward (336h)**: LB336_R48_N3: **5/6 positive, mean OOS 1.001** — PASS
  - **Fee sensitivity**: Sharpe 0.807 at 3x fees — PASS
  - **BUT: Correlation with H-012 = 0.484** — FAIL (threshold <0.4)
  - **Cross-sectional rank corr with H-012**: 0.415
- Notes: The 336h lookback that works is essentially 14-day momentum — a noisier, shorter version of H-012's 60-day momentum. Not an independent alpha source. Shorter hourly lookbacks (24-168h) that would be truly differentiated all fail. No unique hourly momentum alpha exists.
- Sessions: [2026-03-18 review+research session 31]

## H-030: Composite Multi-Factor (Momentum + Volume Momentum + Beta)
- Status: CONFIRMED (standalone) — not added to portfolio (individual strategies combined are better)
- Idea: Combine confirmed cross-sectional factors (momentum, volume momentum, beta) into a single composite z-score ranking. Test 2/3/4-factor blends.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3 days)
- Logic: Z-score normalize each factor cross-sectionally, then weighted average. Best: Mom=0.33/Vol=0.33/Beta=0.34, R3_N5.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr)
- Result:
  - **In-sample (3-factor best)**: Sharpe 2.05, +101.7% annual, 24.9% DD
  - **In-sample (4-factor best)**: Sharpe 2.14, +106.6% annual, 25.1% DD
  - **Parameter robustness**: 135/135 positive (3-factor), 243/243 positive (4-factor) — 100%
  - **Walk-forward (3-factor, 6 folds, 360d train / 80d test)**: 5/6 positive, mean OOS Sharpe 1.71 (480 total OOS days)
  - **Walk-forward (4-factor, 6 folds)**: 5/6 positive, mean OOS Sharpe 2.01
  - **Fee sensitivity**: Sharpe 1.52-1.55 at 5x fees (robust)
  - **Param neighborhood**: 36/36 positive (100%), min 1.09
  - **Portfolio note**: Portfolio of 3 individual strategies (Sharpe 2.26) > single composite (Sharpe 2.14)
  - **Correlations**: 0.61 with H-012, 0.44 with H-021, 0.57 with H-024
- Notes: Excellent standalone strategy (Sharpe 2.05, 100%+ annual, 25% DD, passes WF 5/6). Not added to current portfolio because running individual factors separately preserves diversification from different rebalance schedules (3d/5d/21d). Could be deployed as a simpler alternative to running 3 separate cross-sectional strategies. High-frequency rebal (3-day) means higher turnover — use maker orders.
- Sessions: [2026-03-19 review+research session 32, 2026-03-19 review+system session 33]

## H-031: Size Factor (Dollar Volume Proxy, Long Large)
- Status: LIVE (paper trade since 2026-03-19) — independent, not in main portfolio (corr 0.49 with momentum)
- Idea: Long assets with highest average dollar volume (large-cap proxy), short lowest. Size effect in crypto.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5 days)
- Logic: Compute 30-day rolling average dollar volume (close * volume). Rank. Long top 5 (largest), short bottom 5.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). ~94 IS trades over 1.9yr.
- Result:
  - **In-sample (W30_R5_N5)**: Sharpe 1.58, +78.5% annual, 31.3% DD, ~94 trades
  - **Parameter robustness (long_large)**: 48/48 positive (100%)
  - **Parameter robustness (long_small)**: 0/48 positive (0%)
  - **Walk-forward (W30_R5_N5, 4 folds, 360d train / 80d test)**: 4/4 positive, mean OOS Sharpe 1.47 (320 total OOS days)
  - **Walk-forward (W30_R5_N4)**: 4/4 positive, mean OOS Sharpe 1.78
  - **Fee sensitivity**: Sharpe 1.54 at 5x fees (extremely robust — low turnover)
  - **Typical positions**: LONG BTC/ETH/SOL/XRP/DOGE, SHORT NEAR/DOT/OP/ARB/ATOM
  - **Portfolio note**: Corr with H-012 (momentum) = 0.486, with H-019 (low-vol) = 0.461
  - **Adding to 4-factor composite DECREASES Sharpe**: 2.14 → 1.82-1.97
- Notes: Genuine size effect in crypto — large-cap consistently outperforms small-cap (100% positive, 4/4 WF, extremely fee-robust). Correlated with momentum/low-vol so doesn't diversify the current portfolio, but excellent standalone: +78.5% annual, 31.3% DD, Sharpe 1.58. Very low turnover makes this practical. Could be deployed independently or as a replacement for momentum if H-012 underperforms in paper trade.
- Sessions: [2026-03-19 review+research session 32, 2026-03-19 review+system session 33]

## H-032: Pairwise Cointegration Statistical Arbitrage
- Status: LIVE (paper trade since 2026-03-19) — independent, experimental (OOS evidence mixed)
- Idea: Test all 91 crypto pairs for cointegration, trade mean-reverting spreads using z-score entry/exit. Fundamentally different from cross-sectional factor approaches.
- Instrument: futures (14 perps, pairwise)
- Timeframe: 1D (daily, trades last 20-40 days)
- Logic: Engle-Granger cointegration test on log prices. Compute log-spread = log(A) - HR*log(B) where HR = OLS hedge ratio. Rolling z-score of spread. Long spread when z < -entry_z, short when z > +entry_z. Exit at +-exit_z. Stop at +-stop_z.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). 91 pairs tested. 2160 param sets across 12 candidate pairs.
- Result:
  - **Cointegration**: Only 3/91 pairs strictly cointegrated (p<0.05): DOT/ATOM (p=0.031), DOGE/LINK (p=0.027), LINK/ADA (p=0.045). 12 pairs at relaxed p<0.20.
  - **Cointegration stability**: Poor — most pairs significant in <30% of rolling 180d windows. DOT/ATOM 26%, NEAR/OP 37%, SOL/DOGE 32%.
  - **In-sample (best params)**: DOT/ATOM Sharpe 1.30 (+29.4%, 21.1% DD, 35 trades). SOL/DOGE 1.23. AVAX/DOT 0.96. 50% of 2160 param sets positive.
  - **Fee robustness (3x)**: 10/12 pairs pass. DOT/ATOM 1.30->0.67. SOL/DOGE 1.23->0.68.
  - **Walk-forward (5 folds x 120d)**: 5/12 pairs pass (>=3/4 positive). DOGE/LINK 4/4 (mean 1.49). DOT/OP 3/4 (mean 1.69). DOGE/ADA 3/4 (mean 0.70).
  - **50/50 train/test split**: 5/12 pass. DOGE/LINK test Sharpe 0.75. DOGE/ADA 0.61. DOT/ATOM 0.36.
  - **Both OOS tests passed**: Only 2 pairs (DOGE/LINK, DOGE/ADA).
  - **Multi-pair portfolio (8 pairs, IS)**: Sharpe 1.30, Ann +12.7%, DD 7.4%.
  - **Multi-pair portfolio (8 pairs, OOS)**: Sharpe 1.33, Ann +9.5%, DD 5.8%.
  - **Non-overlapping 3-pair portfolio (OOS)**: Sharpe 0.62, Ann +7.2%, DD 13.0%.
  - **Correlation with H-012**: -0.31 (NEGATIVE — excellent diversifier)
  - **Regime analysis**: BTC UP Sharpe 1.20, FLAT 1.84, DOWN 2.36 — performs best in downtrends
- Notes: Fundamentally different alpha source from cross-sectional factors. Negative correlation with momentum (-0.31) makes it an excellent diversifier. However, OOS evidence is mixed: only 2/12 pairs pass both walk-forward AND train/test split. The core issue is cointegration instability — crypto pairs drift in and out of cointegrated relationships over months. With half-lives of 20-40d and entry thresholds of 1-2.5 sigma, each pair generates only 8-35 trades over 2 years, making OOS validation statistically weak. The 8-pair portfolio OOS Sharpe of 1.33 is promising but relies on diversification across many marginal signals. Could be deployed as a low-allocation diversifier (~5-10% of portfolio) but not as a core strategy. Key advantage: works in all BTC regimes and is negatively correlated with everything else.
- Sessions: [2026-03-19 research session 34]

## H-033: Idiosyncratic Momentum (Alpha Momentum)
- Status: REJECTED
- Idea: Decompose each asset's return into market component (beta * BTC_return) + idiosyncratic residual. Rank on cumulative residual momentum. Assets with positive alpha continue outperforming.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3-14 days)
- Logic: For each asset, compute rolling beta vs BTC (30-90d). Residual return = actual - beta*BTC_return. Rank on sum of residual returns over past 10-60 days. Long top N, short bottom N.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). 144 param sets tested.
- Result:
  - **In-sample**: 99% positive (142/144). Mean Sharpe 0.77. Best B90_M60_R5_N3: Sharpe 1.56, +90.6% ann, 26.4% DD.
  - **Walk-forward (4 folds, 360d/80d)**: 1/4 positive. Mean OOS Sharpe -0.16. **FAILS.**
  - **Correlation with H-012**: 0.832 — essentially redundant with raw momentum.
  - **Correlation with H-009**: 0.000 (orthogonal).
  - **Fee sensitivity**: Robust (1.32 at 5x fees).
- Notes: Stripping out the market (BTC) component doesn't create an independent signal. The residual momentum is still capturing the same cross-sectional patterns as raw momentum because altcoin relative performance is what drives both. Walk-forward failure confirms overfitting. The high IS positive rate (99%) is misleading.
- Sessions: [2026-03-19 research session 37]

## H-034: Funding Rate as BTC Timing Signal
- Status: REJECTED
- Idea: Use extreme funding rate levels as a contrarian predictor of BTC returns. High funding = crowded longs = short. Low funding = oversold = long.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Logic: Compute rolling avg funding rate (3-45 day window). Long BTC when funding below expanding N-th percentile (oversold). Short when above P-th percentile (crowded). Hysteresis (stay in position).
- Data: BTC, 730 daily bars + 2190 funding rate records. 100 param sets tested.
- Result:
  - **In-sample**: 49% positive (49/100) — essentially random.
  - **Best**: F45_L10_S80: Sharpe 0.54, +14.8% ann, 39.9% DD — but only 5 trades.
  - **Walk-forward**: 2/6 positive, mean 0.33.
  - **Correlation with H-009**: -0.175.
- Notes: No edge. 49% positive = noise. The few positive results have tiny sample sizes (5 trades). Funding rate level does not predict BTC price direction reliably. This confirms that funding rates reflect positioning but don't have predictive power for directional moves.
- Sessions: [2026-03-19 research session 37]

## H-035: Momentum with Volatility Timing
- Status: REJECTED (as standalone — logged as potential H-012 enhancement)
- Idea: Scale H-012 momentum exposure based on recent portfolio volatility. When realized vol is high, reduce exposure. When low, increase.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Standard H-012 momentum ranking (60d). Multiply weights by min(vol_target / realized_vol_N_day, 2.0). Vol targets 0.3-1.0, windows 10-60d.
- Data: 14 assets, 734 daily bars. 144 param sets tested.
- Result:
  - **In-sample**: 100% positive (144/144). 21% beat base H-012 (Sharpe 1.12).
  - **Best**: VT0.3_VW10_R5_N4: Sharpe 1.61, +68.3% ann, 21.3% DD (vs base 30.6% DD).
  - **Walk-forward**: 3/4 positive, mean 0.76 (weaker than base H-012's 5/6).
- Notes: Not a new strategy — just an enhancement that reduces drawdown by scaling down during high-vol periods. Walk-forward weaker than base H-012 (3/4 vs 5/6). Could be applied as a refinement to H-012 if drawdown is a concern, but not worth deploying as a separate paper trade.
- Sessions: [2026-03-19 research session 37]

## H-036: Intraday Hour-of-Day Seasonality (BTC)
- Status: REJECTED
- Idea: Test if BTC returns vary systematically by hour of day. If persistent, trade best/worst hours.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1h
- Logic: Compute average return per hour of day using expanding window. Long during best N hours, flat (or short) during worst N hours.
- Data: BTC, 17,610 hourly bars (~2yr).
- Result:
  - **Patterns are real**: Train/test correlation of hourly returns = 0.439. Cross-asset corr = 0.625.
  - **Best hours**: 22:00 (Sharpe 9.75), 21:00 (8.85), 09:00 (5.39).
  - **Worst hours**: 23:00 (-9.74), 19:00 (-4.90), 13:00 (-3.20).
  - **Strategy performance**: Best Sharpe 0.30 (BEST4), +1.1% ann, 17.4% DD. Long/short: Sharpe 0.17.
- Notes: Persistent intraday patterns exist in crypto but the absolute return per hour is tiny (~0.05% per best hour). Transaction costs make any hourly trading unprofitable. The patterns are likely driven by timezone-based trading activity (Asian session 21-02 UTC shows accumulation, European/US session shows distribution). Interesting for understanding market microstructure but not actionable.
- Sessions: [2026-03-19 research session 37]

## H-037: Polymarket 1hr BTC UP/DOWN + Intraday Seasonality
- Status: CONFIRMED (paper trade — Polymarket only, no Bybit)
- Idea: Combine H-036's statistically proven hour-of-day BTC direction bias with Polymarket's 1hr BTC UP/DOWN binary markets. The patterns failed on Bybit (fees kill tiny returns) but Polymarket has a different cost structure (prediction market spread, not exchange fees).
- Instrument: Polymarket binary prediction markets (NOT Bybit)
- Timeframe: 1h
- Logic: Bet on the direction of BTC's next 1-hour candle during hours with statistically significant (p < 0.05) directional bias. Top 5 hours: 17:00 UTC (UP, 56.3%), 21:00 UTC (UP, 54.9%), 22:00 UTC (UP, 54.0%), 23:00 UTC (DOWN, 54.1%), 13:00 UTC (DOWN, 53.8%).
- Data: BTC, 17,611 hourly bars (~2yr). Train/test green probability correlation: 0.522. All 5 target hours show consistent direction in both train and test halves.
- Result:
  - **Green/red probability per hour**: Statistically significant bias at 5 hours (p < 0.05). 17:00 UTC strongest at 56.3% green.
  - **Train/test consistency**: All 5 target hours consistent across halves.
  - **Rolling stability (6mo window)**: Green hours (17/21/22) always > 50% (min 52.0%). Red hours (23/13/00) always < 50%.
  - **OOS simulation (top 5 hours)**: 1,835 bets, 53.7% win rate, 10/13 months profitable, +$586 on $10 bets. ~$0.32/bet.
  - **EV at 50c**: +$0.032-$0.058 per $1 bet depending on hour.
  - **EV at 52c**: Most hours still +EV at 52c entry price, but edge halved.
  - **CRITICAL CAVEAT**: Edge only exists if Polymarket prices at ~50c. If market already prices in seasonality (e.g., 17:00 UP at 55c), edge vanishes.
- Notes: This is a creative cross-platform arbitrage idea from the user. No historical Polymarket data exists to verify pricing inefficiency — must paper trade to find out. The statistical patterns are robust (0.52 train/test corr, consistent across rolling windows). Key unknown: does Polymarket market price in the hour-of-day bias? Paper trade involves monitoring actual Polymarket prices at target hours and comparing to historical probabilities.
- Sessions: [2026-03-19 review+research session 38]

## H-038: ML Factor Combination (Ridge Regression)
- Status: CONFIRMED (standalone, weak) — **NOT for portfolio deployment**
- Idea: Use ML (Ridge regression) to learn optimal non-linear combination of cross-sectional factor signals (momentum, volume momentum, beta, volatility, size, reversal) for predicting next-period returns.
- Instrument: futures (14-asset universe)
- Timeframe: daily (5d rebalance)
- Logic: Compute 7 factor z-scores per asset per day. Train Ridge regression on cross-sectional demeaned forward 5d returns. Walk-forward (365d train, 90d test). Long top-5, short bottom-5 by predicted score.
- Data: 14 assets, 734 daily bars (~2yr). 659 usable dates after warmup. 9,226 observation-rows.
- Result:
  - **Best config**: Ridge alpha=100, zscore features, R5, N5
  - **OOS (walk-forward)**: Sharpe 1.43, +26.2% annual, 9.6% DD
  - **Folds**: 2/3 positive (67%) — fold 0 negative at -0.41
  - **Fee robust**: 1.43 → 0.97 at 5x fees
  - **Param robustness (Ridge)**: 96% positive Sharpe (104/108 configs)
  - **RF/GB**: 100% and 97% positive, but lower best Sharpe (1.14, 1.19) — linear combo sufficient
  - **Correlation**: H-012 0.295, H-021 0.197, H-019 0.232, H-024 0.274
  - **Portfolio impact**: 3-strat XS Sharpe 1.54 → 1.68 (+9%) when added
  - **Train window sensitivity**: CRITICAL — 180d: -0.10, 270d: -0.17, **365d: 1.43**, 450d: 0.46
- Notes:
  - Train window sensitivity is a major red flag — model only works with ~365d window.
  - Feature importance: beta (most stable, 8.34 stability), reversal (11.12), momentum, volume momentum. Reversal contributes in combination despite failing standalone (H-018).
  - Linear model (Ridge) beats tree-based (RF, GB) — factor combination is approximately linear.
  - With only 3 OOS folds (limited by 2yr data), statistical confidence is low.
  - Revisit when more data accumulates (4+ folds for better validation).
  - 38 hypotheses tested total.
- Sessions: [2026-03-19 review+research session 39]

## H-039: Day-of-Week Seasonality (Long Wednesday / Short Thursday)
- Status: LIVE (paper trade since 2026-03-19) — independent
- Idea: Fixed calendar seasonality — crypto markets systematically go up on Wednesdays and down on Thursdays. Long BTC at Tue close, flip short at Wed close, close at Thu close, flat rest of week.
- Instrument: futures (BTC/USDT perp, also works on all 14 assets)
- Timeframe: 1D (daily close, trades 2 days/week)
- Logic: Position based on day of week only. No parameters to optimize. Long Wednesday return, short Thursday return.
- Data: 14 assets, 734 daily bars (~2yr). 105 observations per DOW per asset. BTC alone: 105 Wed, 105 Thu.
- Result:
  - **BTC full period**: Sharpe 1.55, +44.8% annual, -32.7% DD
  - **BTC Walk-Forward (fixed Wed/Thu, 6 folds)**: **6/6 positive** (mean OOS Sharpe **2.46**)
    - Fold 1: 1.92, Fold 2: 1.64, Fold 3: 1.78, Fold 4: 2.78, Fold 5: 3.87, Fold 6: 2.79
  - **EW All-Asset (14)**: Sharpe 1.44, +60.1% annual, -24.2% DD. WF **6/6** (mean 1.99)
  - **Per-asset**: ALL 14 positive IS Sharpe (0.85–1.78). BTC/ETH/DOGE WF 6/6
  - **Quarterly consistency**: Wed > Thu in 7/9 quarters (78%). Rolling 6-month: 89%
  - **ANOVA**: F=12.4 (p<0.0001). Wed mean +0.50%, Thu mean -0.65% (all assets)
  - **Fee robust**: Sharpe 1.07 at 5 bps/side (maker). Dies at 20 bps
  - **Correlation**: H-009 0.013, H-012 0.119, H-019 0.112 — near-zero with everything
  - **Train/Test**: Train Sharpe 0.36, Test Sharpe 3.20 (effect strengthening)
  - **Adaptive WF (select best/worst day)**: Only 4/6 — fixed Wed/Thu is MORE robust than adaptive
- Notes:
  - **Strongest walk-forward result in the entire project** (6/6, mean 2.46, all folds > 1.6)
  - No parameters = zero overfitting risk (beyond the Wed/Thu selection itself)
  - Effect is strengthening over time — recent folds have higher Sharpe
  - Cross-asset consistency (all 14 positive) suggests structural cause, not random
  - Possible causes: institutional rebalancing, options expiry flow (Deribit Fri), market maker inventory
  - BTC-specific DOW effects individually not significant (p>0.1) due to small sample — but the pattern holds in walk-forward
  - 40 hypotheses tested total
- Sessions: [2026-03-19 review+research session 40]

## H-040: Volatility Regime Factor Timing
- Status: REJECTED
- Idea: Scale cross-sectional factor strategy exposure inversely with realized BTC volatility. High vol → reduce exposure, low vol → increase.
- Instrument: futures (14-asset universe)
- Timeframe: daily
- Logic: Compute BTC realized vol over rolling window (10/20/30/60d). Scale H-012 exposure by target_vol / realized_vol. Also test binary regime (above/below expanding median).
- Data: H-012 daily returns + BTC realized vol, 734 daily bars.
- Result:
  - **In-sample**: Marginal improvement. Best: 20d binary regime Sharpe 2.18 (base 2.01). Invvol Sharpe 2.13-2.16.
  - **Walk-forward**: **NEGATIVE improvement**. Invvol: OOS mean 1.66 vs base 1.72 (-0.06). Binary: 1.41 vs 1.72 (-0.31).
  - **Combined DOW+Vol**: Sharpe 2.01 → 2.15 (marginal, likely overfitting).
- Notes: Base factor strategies already implicitly time volatility through portfolio turnover and equal-weight normalization. Explicit vol timing adds complexity without OOS benefit. REJECTED.
- Sessions: [2026-03-19 review+research session 40]

## H-041: BTC Dominance Rotation
- Status: REJECTED
- Idea: Use BTC's share of total normalised price (14-asset proxy for market cap dominance). When BTC dominance rising → long BTC / short alts. When falling → long alts / short BTC.
- Instrument: futures (BTC vs 13 alts)
- Timeframe: daily
- Logic: Compute dom_roc = diff(btc_dom, lookback). Signal = sign(dom_roc). Long BTC+short alts when rising, vice versa. Rebalance daily on signal flip.
- Data: 14 assets, 735 daily bars (2024-03-15 to 2026-03-19, ~2yr).
- Result:
  - **Without look-ahead**: IS Sharpe 3.96, WF 6/6 — FAKE, look-ahead biased
  - **Correctly lagged (signal@t-1, return@t)**: IS Sharpe 0.24 best (LB60_volume), WF 3/6, 1/16 params positive (6.2%). Best IS annual 3.0%, 22% DD.
  - **Root cause**: Dominance signal mean-reverts next day. When BTC outperformed alts today (dom_roc>0), alts tend to catch up tomorrow. Signal is anti-momentum at 1-day horizon across all lookbacks.
- Notes: The 100% positive IS results (without lag) were entirely look-ahead bias — using today's close to compute the signal AND the return. All 16 lookbacks (1–60d) negative with correct lag. Fails all three criteria: IS positive 6.2%, WF 3/6, not fee-robust.
- Sessions: [2026-03-19 research session 41]

## H-042: Cross-Sectional Return Dispersion / Short-Term XSMom
- Status: CONFIRMED (standalone, not yet in portfolio)
- Idea: When cross-sectional return dispersion is high, enable momentum positions (long winners, short losers). When dispersion is low, go flat. Tested as both standalone and H-012 overlay.
- Instrument: futures (14-asset universe)
- Timeframe: daily (with multi-day rebalancing)
- Logic: Compute rolling cross-sectional std of returns across 14 assets. When dispersion > Nth percentile → long top-N / short bottom-N by 20d (or 60d) momentum. Otherwise flat.
- Data: 14 assets, 735 daily bars (2024-03-15 to 2026-03-19, ~2yr). ~33-36 OOS observations per WF fold.
- Result:
  - **IS (full, correctly lagged)**: Sharpe 1.166, +27.4% annual, 12.1% DD (best params: M20_R21_N4). 77.1% of 48 param sets positive.
  - **Walk-forward (6 folds, 60d OOS each)**: **4/6 folds positive**, mean OOS Sharpe 0.548. Fold results: -3.32, +1.66, +2.01, +1.41, -1.07, +2.61.
  - **Fee robustness (2x)**: Sharpe 1.082 — fee-robust.
  - **Correlation with H-009**: -0.057 (near-zero)
  - **Correlation with H-012**: 0.686 (moderate-high — partially overlapping with existing momentum)
  - **Dispersion filter**: Does NOT add alpha. Only 10.2% of dispersion param combos improve over base. Core signal is short-term XSMom (20d lookback, 21d rebal).
  - **As H-012 overlay**: Hurts Sharpe (0.739 → 0.395). Dispersion is not a good gating condition.
- Notes: The hypothesis as posed (dispersion conditioning) does not work — dispersion filter hurts more than it helps. The genuine signal here is a short-term (20d) XSMom, distinct from H-012 (60d). Corr with H-012 is 0.686 — moderately high. This is NOT added to the portfolio because it is partially redundant with H-012 and the WF mean OOS Sharpe (0.548) is weak. Confirmed standalone (meets all 3 criteria) but portfolio impact marginal due to H-012 overlap.
- Sessions: [2026-03-19 research session 41]

## H-043: Open Interest Changes as Cross-Sectional Factor
- Status: REJECTED
- Idea: Rank assets by OI change (pct change in open interest over various windows). Long high OI change (momentum into leveraged positions) or short high OI change (contrarian).
- Instrument: futures (14-asset universe)
- Timeframe: daily (various rebalancing: 3, 5, 10 days)
- Logic: Compute N-day pct change in open interest for each asset. Rank cross-sectionally. Long top-N / short bottom-N. Tested both momentum (long high OI change) and contrarian (short high OI change) at windows 1, 3, 5, 10, 20 days.
- Data: 14 assets, 734 daily OI bars from Bybit (2024-03-16 to 2026-03-19), aligned with price data. OI data fetched from Bybit V5 historical API (up to 2053 bars per asset).
- Result:
  - **IS overall**: Only 34.4% of 90 param sets positive — weak.
  - **OI_CHG_1d (best)**: IS Sharpe 1.41 at n=5 r=3. But only works at 3-day rebal — fails at 5d and 10d. Walk-forward **1/5 folds positive**, mean OOS -0.90. FAILS.
  - **OI_CHG_20d_INV (contrarian, all positive)**: 100% IS positive (9/9) but best Sharpe only 0.60, mean 0.35. Very weak absolute edge.
  - **Fee robustness (OI_CHG_1d)**: Sharpe -0.60 at 5x fees. Not fee-robust.
- Notes: OI change alone is NOT a robust cross-sectional signal. Short-term (1d) OI change captures some mean-reversion in positioning but fails walk-forward. Long-term (20d) contrarian OI signal is too weak. The signal only works when combined with price (see H-044).
- Sessions: [2026-03-20 review+research session 42]

## H-044: OI-Price Divergence Factor
- Status: LIVE (paper trade since 2026-03-20, independent)
- Idea: Rank assets by divergence between price momentum and OI change. "Price up + OI down" = sustainable rally (shorts closing, not new leverage). "Price down + OI up" = leverage buildup (potential further decline).
- Instrument: futures (14-asset universe)
- Timeframe: daily (10-day rebalancing)
- Logic: Compute 20-day price change z-score and 20-day OI change z-score cross-sectionally. Signal = price_z - oi_z (lagged 1 day). Long top 5, short bottom 5.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19), OI from Bybit V5 API. ~101 OOS observations per WF fold.
- Result:
  - **IS (full, CORRECTED)**: Sharpe 1.01, +17.3% annual, 17.3% DD, 52.2% WR (n=5, r=10). **100% params positive (9/9)**. *Original Sharpe 1.46 was inflated ~4.9x by metrics bug (periods_per_year=8760 instead of 365). Corrected session 43.*
  - **Walk-forward (4 folds, ~122d OOS each, CORRECTED)**: **3/4 folds positive** (mean OOS Sharpe 1.22). Fold detail: +1.73, +1.40, +1.86, -0.13.
  - **Fee robustness**: Sharpe still positive at 5x fees — fee-robust.
  - **Correlation with H-009**: 0.016 (near zero)
  - **Correlation with H-012**: 0.565 (moderate — partially captures momentum)
  - **Correlation with H-019**: 0.154 (low)
  - **Correlation with H-021**: 0.064 (near zero)
  - **Correlation with H-024**: 0.249 (moderate)
- Notes: First strategy using genuinely new data (open interest). The OI divergence signal captures information beyond price momentum — assets where rallies are driven by deleveraging (OI down) tend to continue, while assets with increasing leverage during declines tend to fall further. Confirmed standalone with strong metrics. NOT in main portfolio due to 0.565 corr with H-012 (momentum), but deployed as independent paper trade. Initial rebalance: LONG SUI/OP/NEAR/SOL/ETH, SHORT ADA/ARB/DOT/XRP/DOGE.
- Sessions: [2026-03-20 review+research session 42]

## H-045: OI-Volume Confirmation/Divergence Factor
- Status: CONFIRMED standalone (weak) — NOT deployed
- Idea: Combine OI changes with volume changes as cross-sectional signal. Volume surge + OI increase = new positions (momentum). Volume surge + OI decrease = unwinding (reversal).
- Instrument: futures (14-asset universe)
- Timeframe: daily (10-day rebalancing)
- Logic: Compute cross-sectional z-scores of volume change and OI change. Test 6 signal variants (confirmation, divergence, new money, squeeze, triple, directed). Best robust variant: price_z * oi_z (no clip), 20d window.
- Data: 14 assets, 734 daily bars. OI data from Bybit V5.
- Result:
  - **Initial results inflated by zero-signal artifact**: Original NEW_MONEY_10d Sharpe 1.73 was 35% driven by tie-breaking of zero-signal assets (54% of signals clipped to zero).
  - **Robust no-clip variant (W20 n=4 r=10)**: IS Sharpe 1.76, +33.6%, 16.7% DD. WF 3/4 (mean OOS 1.28). But ONLY works at r=10 — sensitive to rebalance frequency.
  - **Correlations**: 0.109 with H-012, 0.144 with H-044, 0.067 with H-046 — low but strategy is fragile.
  - **49% of all param sets positive** — not robust across variants.
- Notes: The multiplicative signal (price * OI) concentrates information on assets with high-conviction OI movements, but creates many zero signals that corrupt ranking. The additive variants (confirmation, triple) are much weaker. Not deploying due to rebal sensitivity and partial redundancy with H-044.
- Sessions: [2026-03-20 review+research session 43]

## H-046: Price Acceleration Factor (Second Derivative of Momentum)
- Status: LIVE (paper trade since 2026-03-20, independent)
- Idea: Rank assets by change in 20-day momentum over the last 20 days (second derivative). Assets with accelerating momentum outperform those with decelerating momentum.
- Instrument: futures (14-asset universe)
- Timeframe: daily (3-day rebalancing)
- Logic: Compute 20-day return for each asset. Acceleration = return(t-20,t) - return(t-40,t-20). Cross-sectional z-score, lagged 1 day. Long top 4, short bottom 4.
- Data: 14 assets, 694 daily bars (after warmup). No OI data needed — price only.
- Result:
  - **IS (full)**: Sharpe 1.19, +25.1% annual, 17.6% DD, 50.1% WR (n=4, r=3). **100% params positive (9/9)**.
  - **Walk-forward (4 folds, ~122d OOS each)**: **4/4 folds positive** (mean OOS Sharpe **1.13**). Fold detail: +1.44, +0.29, +2.25, +0.54.
  - **Fee robustness**: 1.03 at 2x fees, 0.87 at 3x, 0.56 at 5x fees (decent).
  - **Correlations**: 0.007 with H-009, 0.099 with H-012, -0.123 with H-019, 0.179 with H-021 — **near-zero with everything**.
  - **Portfolio benefit**: H-012 + H-046 50/50 → Sharpe 1.71 (vs 1.37 standalone). Significant diversification.
- Notes: Captures a genuinely different aspect of price dynamics from momentum (H-012). Momentum measures the LEVEL of recent returns; acceleration measures the CHANGE in momentum. An asset just starting to move (low momentum, high acceleration) ranks differently from one with sustained high momentum. Perfect 4/4 WF and near-zero correlations make this one of the strongest discoveries since H-039 (DOW seasonality). Deployed as independent paper trade. Initial: LONG OP/ARB/NEAR/SUI, SHORT DOGE/LINK/ADA/DOT.
- Sessions: [2026-03-20 review+research session 43]

## H-047: Volatility Change Factor (Cross-Sectional, 14 Assets)
- Status: REJECTED
- Idea: Rank assets by change in realized volatility (short-window vol / long-window vol). Long assets with decreasing vol (stable), short assets with increasing vol. Or reverse.
- Instrument: futures (14 perps)
- Timeframe: 1D (various rebalancing: 3, 5, 10, 21 days)
- Logic: Compute rolling short-window (5/10/20d) and long-window (30/60/90d) realized vol. Ratio = short/long. Cross-sectional z-score. Test both long_low (decreasing vol) and long_high (increasing vol). 216 param sets.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr).
- Result:
  - **Overall**: 108/216 positive (50%) — exactly random
  - **long_low direction**: 30% positive, mean Sharpe -1.46
  - **long_high direction**: 70% positive, mean Sharpe +1.46
  - **Metrics severely broken**: Top Sharpe values (9+) are artifacts from sparse R21 rebalancing. Returns showing inf, DD >300%.
- Notes: 50% positive rate is the clearest signal of NO systematic edge. The asymmetry between directions (30% vs 70%) is due to the mirroring property of long/short portfolios. Vol dynamics (rising vs falling volatility) do not predict cross-sectional returns. Different from H-019 (vol LEVEL) which works.
- Sessions: [2026-03-20 review+research session 44]

## H-048: Realized Correlation Change Factor (Cross-Sectional, 13 non-BTC Assets)
- Status: REJECTED
- Idea: Rank assets by change in rolling correlation with BTC. Long assets becoming LESS correlated (diversifiers), short assets becoming MORE correlated.
- Instrument: futures (13 non-BTC perps)
- Timeframe: 1D (various rebalancing: 5, 10, 21 days)
- Logic: Compute rolling N-day (30/60/90) correlation of each alt with BTC. Delta = corr(t) - corr(t-M) where M=10/20/30. Cross-sectional z-score. 144 param sets.
- Data: 14 assets, 734 daily bars.
- Result:
  - **Overall**: 72/144 positive (50%) — exactly random
  - **Both directions 50/50** — no preference
  - **Top Sharpe values (6+) are artifacts** — metrics broken (inf returns)
- Notes: Correlation dynamics have no cross-sectional predictive power. Assets whose correlation with BTC is changing (up or down) don't systematically outperform. This is unsurprising — correlation is a slow-moving, noisy statistic with weak signal-to-noise at daily frequency.
- Sessions: [2026-03-20 review+research session 44]

## H-049: Long/Short Ratio Sentiment Factor (Contrarian, 14 Assets) — NEW
- Status: LIVE (paper trade since 2026-03-20, independent)
- Idea: Rank assets by Bybit long/short ratio (crowd positioning). Contrarian: long assets where crowd is MOST SHORT (lowest LSR), short assets where crowd is MOST LONG (highest LSR).
- Instrument: futures (14-asset universe)
- Timeframe: daily (5-day rebalancing)
- Logic: Fetch daily long/short ratio from Bybit API for all 14 assets. Cross-sectional z-score. Contrarian direction: long bottom 3, short top 3. Lagged 1 day.
- Data: 14 assets, **200 daily bars only** (2025-09-02 to 2026-03-20, ~6.5 months). **CAVEAT: well below 2-year standard.**
- Result:
  - **IS (full, R5_N3)**: Sharpe **2.58**, +59.1% annual, 7.2% DD, 55.3% WR. **100% params positive (12/12)** across all contrarian variants.
  - **All param range**: Sharpe 1.49 (R10_N5) to 2.80 (R1_N3) — ALL strongly positive
  - **Split-half**: First half Sharpe 2.01, second half **3.75** — both positive, effect STRENGTHENING
  - **Fee sensitivity (R5_N3)**: Zero-fee 2.58 → 4bps 2.38 → 8bps 2.18 → 12bps 1.98 → **20bps 1.58** (still positive at 5x fees!)
  - **Turnover**: 1.09 / 6 positions change per day (18%) — relatively stable
  - **Correlations**: H-012 -0.091, H-019 -0.127, H-021 0.231, **H-046 0.581** (high)
  - **Portfolio benefit**: 4 existing + H-049 → Sharpe 4.60 (from 4.29 without). H-012 + H-049 50/50 → 2.84 (vs 1.36 alone).
  - **Momentum direction**: 0/12 positive — purely contrarian edge, not momentum
- Notes: The strongest IS result ever found in this project (Sharpe 2.58, 100% params, 7% DD). However, the **200-day backtest limitation** is a serious caveat. Walk-forward validation is not possible with proper fold sizes. The signal captures genuine retail crowd positioning errors — when most traders are long an asset relative to peers, it tends to underperform. BTC and ETH are frequently in the contrarian LONG basket (crowd relatively less long / more short on these). High correlation with H-046 (acceleration, 0.581) suggests both capture "smart money vs. crowd" dynamics. Deployed as independent paper trade with extended monitoring period. Data source: Bybit `fetchLongShortRatioHistory` API, cached in `data/all_assets_lsr_daily.parquet`.
- Sessions: [2026-03-20 review+research session 44]

## H-050: Inter-Market Macro Signals for Crypto Timing
- Status: REJECTED
- Idea: Use traditional macro asset returns (S&P 500, Gold, DXY, VIX, 10Y yield) to predict next-day BTC/crypto returns. Test both directional BTC timing and cross-sectional beta tilting.
- Instrument: futures (BTC/USDT perp, 14-asset universe)
- Timeframe: 1D
- Logic: Compute N-day (1-20d) rolling macro asset return. Use sign as BTC timing signal (lagged 1 day). Also test VIX level regimes and combined risk-on composite. Also test macro-driven beta tilt in crypto universe.
- Data: SPY, GLD, UUP, ^VIX, ^TNX from Yahoo Finance (514 bars), aligned with 739 daily crypto bars (2024-03 to 2026-03).
- Result:
  - **Same-day correlations**: SPY-BTC +0.374 (significant), VIX-BTC -0.354. Crypto co-moves with equities.
  - **Lagged correlations**: ALL near zero (max |0.079|). No predictive power.
  - **BTC timing strategies**: 50 param sets tested. **Exactly 50% positive** = random noise. Mean Sharpe 0.000.
  - **VIX regime filter**: No edge. VIX < 20 Sharpe -0.25, VIX percentile < 0.5 Sharpe +0.13.
  - **Cross-sectional beta tilt**: All negative Sharpe.
  - **Combined macro composite**: All negative Sharpe.
- Notes: Crypto co-moves with equities same-day (SPY-BTC r=0.37) but the information is fully priced in by day's end. No lagged predictive power exists. This confirms efficient cross-market pricing — macro signals are absorbed intra-day. 50% positive rate across all lookbacks and directions proves there is zero edge.
- Sessions: [2026-03-20 review+research session 45]

## H-051: Monthly/Calendar Seasonality (Day-of-Month, Week-of-Month)
- Status: REJECTED
- Idea: Test if BTC returns vary systematically by day of month (turn-of-month effect, week-of-month pattern). If persistent, trade the best/worst days.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Logic: Compute mean return per day of month (1-31), week of month (1-5), month of year (Jan-Dec). Train/test split and walk-forward validation.
- Data: BTC, 739 daily bars (2024-03 to 2026-03). ~24 observations per day-of-month.
- Result:
  - **Day of month**: No statistically significant days (all |t| < 1.96). Week 5 (days 29-31) t=-2.40 borderline.
  - **Month of year**: No significant months (best Feb t=-1.32).
  - **Turn of month**: Negative (-0.21%) vs mid-month (+0.09%) — not significant.
  - **Train/test DOM correlation**: -0.133 (NEGATIVE — no persistence whatsoever)
  - **Walk-forward (6 folds, 180d train / 60d test)**: 3/6 positive, mean OOS -0.97. FAILS.
  - **Cross-asset**: BTC/ETH/SOL all show month-end weakness but not significant.
- Notes: The day-of-week effect (H-039: Wed+/Thu-) remains the ONLY calendar seasonality that works. Day-of-month patterns don't persist across periods (train/test corr -0.13). Walk-forward fails 3/6. The difference: day-of-week has 105+ observations per day (2yr), while day-of-month has only ~24 — insufficient for robust estimation. Monthly patterns (Jan-Dec) also too few observations. Calendar effects require high-frequency recurrence to be exploitable.
- Sessions: [2026-03-20 review+research session 45]

## H-052: Premium Index Cross-Sectional Factor (Contrarian)
- Status: LIVE (paper trade since 2026-03-20)
- Idea: Rank 14 crypto assets by average perpetual-to-spot premium/discount. Contrarian: long most discounted (shorts aggressive), short least discounted. Premium index is a genuinely different data source from price, volume, OI, or funding rate.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5 days)
- Logic: Compute avg premium index (close) over 5 days per asset. Rank cross-sectionally. Long bottom 4 (most discounted), short top 4 (least discounted). Market-neutral.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). Bybit V5 premium-index-price-kline endpoint.
- Result:
  - **In-sample (full)**: 100% params positive (30/30). Best W5 R3 N4: Sharpe 2.25, +40.4%, DD -11.8%
  - **Walk-forward (6 folds, 120d train / 90d test)**: 23/24 majority positive, 3/24 ALL folds positive. Mean OOS Sharpe 1.35.
    - Best WF: W10 R3 N4 mean 2.01 (5/6). W5 R5 N4 mean 1.86 (6/6 ALL positive).
  - **Split-half**: First half Sharpe 2.18, Second half Sharpe 2.95 — BOTH strong.
  - **Fee sensitivity**: 1x fees Sharpe 1.88, 2x fees 1.50, 5x fees 0.39
  - **Correlations**: -0.142 H-012 (XSMom), 0.097 H-021 (VolMom), 0.167 H-046 (Accel)
- Notes: One of the strongest signals found. Negative correlation with momentum (excellent diversifier). Premium captures directional sentiment pressure — assets with extreme negative premium (shorts aggressive) tend to revert. Level_momentum (0% positive) and basis change (43%) fail, confirming it's a contrarian mean-reversion effect. Deployed with W5 R5 N4 (6/6 WF).
- Sessions: [2026-03-20 review+research session 46]

## H-053: Funding Rate Cross-Sectional Factor (Contrarian)
- Status: LIVE (paper trade since 2026-03-20)
- Idea: Rank 14 crypto assets by rolling 3-day average funding rate. Contrarian: long lowest funding (shorts paying longs, weak sentiment), short highest funding (crowded longs). Funding rate is mechanically related to premium index (H-052) but captures different time dynamics (8h discrete settlements vs continuous premium).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 10 days)
- Logic: Compute 3-day rolling avg of daily mean funding rate per asset. Rank cross-sectionally. Long bottom 4 (lowest funding), short top 4 (highest funding). Market-neutral.
- Data: 14 assets, 730 daily bars (2024-03-17 to 2026-03-16, ~2yr). 8h Bybit funding rates aggregated to daily avg. Cross-sectional mean correlation 0.694 (high — rates move together, but rank differences still predictive).
- Result:
  - **In-sample (full, contrarian only)**: 93% params positive (42/45). Best W3 R10 N4: Sharpe 1.52, +32.9% ann, 22.2% DD
  - **Momentum direction**: 0% positive (0/45) — crowded longs continue to underperform
  - **Walk-forward (6 folds, 90d test)**: **6/6 positive** for W3 R10 N4 (mean OOS **2.29**, folds: 4.91, 0.94, 2.84, 0.06, 1.60, 3.42)
  - **Split-half**: First half 1.31, Second half 1.91
  - **Fee sensitivity**: 1x Sharpe 1.52, 2x 1.37, 5x 0.92, 10x 0.17
  - **Correlations**: 0.004 H-012 (XSMom), 0.109 H-046 (Accel), **0.360 H-052 (Premium)**, **0.480 H-049 (LSR)**
  - **Without ATOM**: Still Sharpe 1.22 (ATOM has anomalous -1.32% ann funding, in bottom 3 49% of days)
- Notes: Strongest WF result in project (tied with H-039 at 6/6). Moderate correlation with H-052 (0.36) expected since funding ≈ f(premium). High correlation with H-049 (0.48) since both are contrarian positioning signals. Near-zero correlation with momentum factors. The 0% positive for long_high direction strongly confirms contrarian mechanism: crowded longs (high funding) reliably underperform.
- Sessions: [2026-03-20 review+research session 47]

## Killed
(none)

---

<!-- Template:
## H-NNN: <title>
- Status: PENDING
- Idea:
- Instrument:
- Timeframe:
- Logic:
- Result: —
- Notes:
- Sessions: []
-->
