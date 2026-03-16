# Hypotheses

## Pending

## H-001: EMA Crossover Trend Following (BTC Futures)
- Status: PENDING
- Idea: Classic dual-EMA crossover on BTC/USDT perpetual futures with volatility-scaled position sizing
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Logic: Long when EMA(20) > EMA(50), short when EMA(20) < EMA(50). Position size = target_risk / ATR(14). Stop-loss at 2×ATR. Take-profit at 3×ATR or trail.
- Result: —
- Notes: Likely to struggle in the 2024–2026 sideways/down market, but should capture any strong trends. Baseline strategy to compare others against. Low trade frequency (~2-4 trades/month).
- Sessions: [2026-03-15 research]

## H-004: Volatility Breakout (BTC Futures)
- Status: PENDING
- Idea: Enter on volatility expansion beyond recent range, using ATR channel breakout. Exploit the fat tails (kurtosis 3.66).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1h
- Logic: Compute ATR(24) and 24-bar high/low channel. Entry long: close > channel_high + 0.5×ATR. Entry short: close < channel_low - 0.5×ATR. Exit: trail stop at 1.5×ATR or mean reversion to 24-bar midpoint. Max holding period: 48 bars.
- Result: —
- Notes: High kurtosis (3.66) and 70% vol at 90th percentile suggest profitable breakout opportunities. Quick entries and exits — higher trade count than trend following. Risk: false breakouts in low-vol regimes. Filter: only trade when ATR(24) > ATR(168) (expanding vol).
- Sessions: [2026-03-15 research]

## H-005: Funding Rate Arbitrage (BTC Futures)
- Status: PENDING
- Idea: Exploit persistent funding rate imbalances on BTC perpetual futures. When funding is highly positive (longs pay shorts), go short perp + long spot. When highly negative, go long perp + short spot (or just long perp).
- Instrument: futures + spot (BTC/USDT)
- Timeframe: 8h (funding settlement intervals)
- Logic: Monitor funding rate. When |funding_rate| > threshold (e.g. 0.03%), take opposing position to collect funding. Size based on annualized funding yield vs execution costs. Delta-neutral when paired with spot hedge.
- Result: —
- Notes: Funding rates on Bybit perps are a consistent source of alpha. Market-neutral when hedged. Requires spot + futures positions simultaneously. Low drawdown by design. Need to fetch historical funding rate data. Key risk: sudden funding rate reversal during position entry.
- Sessions: [2026-03-16 backtest]

## H-006: Adaptive Mean Reversion (BTC Futures, Long/Short)
- Status: PENDING
- Idea: Improved mean reversion using futures (long/short) instead of spot-only. Add regime filter: only trade mean reversion when volatility is contracting (avoid trending markets). Addresses H-002's failure mode.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1h
- Logic: BB(20,2) + RSI(14) mean reversion but with: (1) long AND short signals, (2) regime filter using ATR ratio (ATR_24/ATR_168 < 1.0 = range-bound = trade), (3) adaptive BB width based on recent vol. Entry long: close < BB_lower AND RSI < 35 AND regime=range. Entry short: close > BB_upper AND RSI > 65 AND regime=range. Exit at BB_middle. Stop: 2×ATR.
- Result: —
- Notes: H-002 failed because it was long-only in a bear market and lacked regime awareness. This version adds shorting capability and filters out trending periods where mean reversion fails. Should have fewer but higher-quality trades.
- Sessions: [2026-03-16 backtest]

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
