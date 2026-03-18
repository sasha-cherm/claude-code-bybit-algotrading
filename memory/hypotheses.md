# Hypotheses

## Live (Paper Trading)

## H-009: BTC Daily EMA Trend Following with Vol Targeting
- Status: LIVE (paper trade since 2026-03-16)
- Idea: BTC-only daily EMA(5/40) crossover with position-level vol targeting. Most defensible variant of H-008 — no asset selection needed, OOS-validated.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D (daily)
- Logic: Long when EMA(5) > EMA(40), short when EMA(5) < EMA(40). Position size scaled by target_vol / realized_vol (30-day lookback). Cap at 2x notional.
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
(none — H-012/H-019 promoted to LIVE)

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
- Status: CONFIRMED
- Idea: Long assets with highest short-term volume growth relative to long-term average, short lowest. Volume expansion precedes price moves.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3 days)
- Logic: Compute ratio of 5-day avg volume to 20-day avg volume for each asset. Rank. Long top 4 (highest volume surge), short bottom 4. Rebalance every 3 days using lagged ranking.
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
- Notes: **Best WF performance of any strategy tested** (6/6, mean 1.83). Key caveat: ONLY works at high-frequency rebalance (3-day). Low-frequency versions (14-21 day) FAIL WF badly (2/6). This means high turnover (1409 trades) — fee management critical. Must use maker orders. Alternative: VS7_VL20_R3_N4 (IS 1.81, WF 5/6 mean 1.77) also strong. Volume z-score variant (IS 1.91) fails WF. Volume data quality is clean (no zeros, CV 0.43-0.65). Ready for paper trade — design runner with careful fee tracking.
- Sessions: [2026-03-18 research session 28]

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
