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

## H-002: Bollinger Band Mean Reversion (BTC Spot)
- Status: PENDING
- Idea: Buy oversold (below lower BB) with RSI confirmation, sell at mean. Exploit the negative daily autocorrelation observed in BTC.
- Instrument: spot (BTC/USDT)
- Timeframe: 1h
- Logic: Entry: close < BB_lower(20,2) AND RSI(14) < 30. Exit: close > BB_middle(20) OR RSI > 60. Stop-loss: 3% below entry. Spot-only (no shorting) to avoid funding costs and liquidation risk.
- Result: —
- Notes: Negative lag-1 autocorrelation (-0.08) on daily supports mean reversion. BB extremes hit ~6% of time — should generate enough signals. Risk: catching falling knives in strong downtrends. RSI filter helps.
- Sessions: [2026-03-15 research]

## H-003: Cross-Asset Momentum Rotation (Multi-Asset Futures)
- Status: PENDING
- Idea: Rank BTC, ETH, SOL by recent momentum. Go long the strongest, short the weakest. Market-neutral exposure.
- Instrument: futures (BTC/USDT, ETH/USDT, SOL/USDT perps)
- Timeframe: 4h (rebalance weekly)
- Logic: Compute 7-day and 21-day momentum (rate of change) for each asset. Score = weighted rank. Long top-1 asset, short bottom-1 asset. Equal dollar exposure on each leg. Rebalance every 168 bars (1 week). Position size: 5% of equity per leg.
- Result: —
- Notes: Market-neutral means performance doesn't depend on crypto going up. BTC -0.9% annualized, ETH -44.7%, SOL -52.9% over 2yr — massive divergence means momentum rotation could capture relative value. Key risk: correlation spikes during crashes (all assets drop together).
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

## Confirmed
(none)

## Rejected
(none)

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
