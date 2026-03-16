# Hypotheses

## Pending

## H-009: BTC Daily EMA Trend Following with Vol Targeting (Paper Trade Candidate)
- Status: PENDING
- Idea: BTC-only daily EMA(5/40) crossover with position-level vol targeting. Most defensible variant of H-008 — no asset selection needed, OOS-validated.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D (daily)
- Logic: Long when EMA(5) > EMA(40), short when EMA(5) < EMA(40). Position size scaled by target_vol / realized_vol (30-day lookback). Cap at 2x notional.
- Result: —
- Notes: Derived from H-008 analysis. BTC-only OOS Sharpe 0.94, VT 20% gives +11.8% annual at 12.9% DD. Modest returns but robust signal. Could be component of multi-strategy portfolio.
- Sessions: [2026-03-16 analyze]

## H-010: Multi-Strategy Portfolio Research
- Status: PENDING
- Idea: Research and combine multiple uncorrelated strategies to achieve Sharpe ≥ 2.0 via diversification. Single strategies max at Sharpe ~0.7; need portfolio approach for 20% return at 10% DD.
- Instrument: mixed
- Timeframe: mixed
- Logic: Identify 3-5 strategies with low correlation. Candidates: (a) BTC daily trend (H-009, Sharpe 0.65), (b) funding rate arb with leverage (H-005 derivative), (c) cross-exchange arb/basis trade, (d) options vol selling, (e) order flow / microstructure.
- Result: —
- Notes: Math requires Sharpe ≥ 2.0 for 20% return at ≤10% DD. With 3 uncorrelated strategies at Sharpe ~0.7, combined Sharpe ≈ 1.2. Need higher individual Sharpes or more strategies.
- Sessions: [2026-03-16 analyze]

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
- Status: REJECTED
- Idea: Exploit persistent funding rate imbalances on BTC perpetual futures. Short perp + long spot when funding positive. Delta-neutral.
- Instrument: futures + spot (BTC/USDT)
- Timeframe: 8h (funding settlement intervals)
- Logic: Monitor funding rate. When rolling avg funding > threshold, hold short perp + long spot to collect funding payments.
- Result: 2-year avg funding rate: 0.0059%/8h = 6.5% annualized. Best backtest: Sharpe 4.71, annual +1.7%, max DD 0.44% (rolling-27 filter). With simple threshold: Sharpe 15.96, annual +3.1%, max DD 0.20%. Funding declining: Q1 2024 22.7% → Q1 2026 1.6%.
- Notes: Strategy works perfectly (excellent Sharpe, near-zero drawdown) but **absolute returns far too low** (1.7-3.1% annual). Would need 5-10x leverage to approach 20% target, breaking delta-neutral property. Funding rates declining over time, making this even less attractive. Not viable for our return targets.
- Sessions: [2026-03-16 backtest]

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

## Live (Paper Trading)
(none)

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
