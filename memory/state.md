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
| H-001: EMA Crossover Trend (BTC futures) | PENDING | Low | Backtest on 4h — likely weak in choppy market |
| H-004: Volatility Breakout (BTC futures) | PENDING | High | Backtest on 1h — fat tails support this |
| H-005: Funding Rate Arbitrage (BTC) | PENDING | High | Fetch funding rate data, build backtest |
| H-006: Adaptive Mean Reversion (BTC futures) | PENDING | High | Backtest on 1h — fixes H-002's failures |

## Rejected Strategies
| Hypothesis | Reason |
|-----------|--------|
| H-002: BB Mean Reversion (spot) | All params negative. Long-only fails in bear market. |
| H-003: Cross-Asset Momentum | Returns too low (<4%), drawdown too high (39%). Crypto too correlated. |

## Infrastructure Status
- Data fetcher: operational (ccxt, parquet caching)
- Metrics library: operational
- Backtest engine: operational (event-driven, spot + futures modes)
- Cached data: BTC/USDT 1h (17,520 candles), ETH/USDT 1h, SOL/USDT 1h — all 2yr

## Key Learnings
- 2024–2026 BTC: +1.8% total, 50% drawdown, very choppy — buy-and-hold is weak
- Long-only spot strategies fail in bear/choppy markets — need futures (long/short)
- Simple cross-asset momentum fails with only 3 correlated crypto assets
- Regime awareness is critical — mean reversion works in ranges, fails in trends
- Next session priority: H-004 (vol breakout) and H-006 (adaptive mean reversion)
