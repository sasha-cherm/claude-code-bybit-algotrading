# Strategy State

## Active Paper Trades
(none)

## Active Live Strategies
(none)

## Recently Killed
(none)

## Research Pipeline
| Hypothesis | Status | Priority | Next Step |
|-----------|--------|----------|-----------|
| H-001: EMA Crossover Trend (BTC futures) | PENDING | Medium | Backtest on 4h |
| H-002: BB Mean Reversion (BTC spot) | PENDING | High | Backtest on 1h |
| H-003: Cross-Asset Momentum (multi futures) | PENDING | High | Backtest on 4h |
| H-004: Volatility Breakout (BTC futures) | PENDING | Medium | Backtest on 1h |

## Infrastructure Status
- Data fetcher: operational (ccxt, parquet caching)
- Metrics library: operational
- Backtest engine: operational (event-driven, spot + futures modes)
- Cached data: BTC/USDT 1h (17,520 candles), ETH/USDT 1h, SOL/USDT 1h — all 2yr

## Notes
- 2024–2026 BTC: +1.8% total, 50% drawdown, very choppy — buy-and-hold is weak
- ETH -44.7%, SOL -52.9% over same period — bear market for alts
- Negative daily autocorrelation in BTC (-0.08) favors mean reversion
- High kurtosis (3.66) favors breakout strategies
- Next session should backtest H-002 (mean reversion) and H-003 (cross-asset momentum) — highest priority
