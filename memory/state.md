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
| H-008: Multi-Asset Daily Trend Following | BACKTEST | **High** | Walk-forward validation, position sizing, out-of-sample test |
| H-001: EMA Crossover Trend (BTC 4h) | PENDING | Low | Superseded by H-008 |

## Rejected Strategies
| Hypothesis | Reason |
|-----------|--------|
| H-002: BB Mean Reversion (spot) | Long-only fails in bear market. All params negative. |
| H-003: Cross-Asset Momentum | Returns too low (<4%), drawdown too high (39%). Only 3 correlated crypto assets. |
| H-004: Volatility Breakout (1h) | All params negative. BTC 1h breakouts lack follow-through. Best Sharpe -0.62. |
| H-005: Funding Rate Arb | Strategy works (Sharpe 4.7+) but absolute returns too low (1.7-3.1% annual). Funding declining over time. |
| H-006: Adaptive Mean Reversion (1h) | All params negative even with regime filter + reversal confirmation. No edge on BTC 1h mean reversion. |
| H-007: BTC/ETH Pairs Trading | Structural BTC/ETH divergence defeats mean reversion. ETH -44.7% vs BTC +1.8% over 2 years. |

## Infrastructure Status
- Data fetcher: operational (ccxt, parquet caching)
- Metrics library: operational
- Backtest engine: operational (event-driven, spot + futures + pairs modes)
- Cached data (1h, 2yr): BTC, ETH, SOL, DOGE, AVAX, LINK, ADA, XRP, DOT, NEAR, OP, ARB, SUI, ATOM (14 assets)
- Cached data: BTC funding rates (2yr, 2194 records)

## Key Learnings
- 2024–2026 BTC: +1.8% total, 50% drawdown — extremely hostile for directional strategies
- 2024–2026 ETH: -44.7%, SOL: variable, SUI: +100%+ (strong outlier)
- Long-only spot strategies fail in bear/choppy markets
- 1h timeframe: both trend-following and mean reversion produce negative expectancy on BTC
- Daily timeframe EMA crossover produces the first positive result (Sharpe 0.70 on BTC)
- Multi-asset portfolio diversification helps (avg correlation 0.355 across strategy returns)
- Funding rate arb works but yields too low for our return targets (6.5% avg, declining)
- Fee drag is critical: 0.2% round-trip × 200 trades = 40% lost to fees
- Position sizing needed: raw DD of best strategies is 30-57%, need scaling to hit ≤10% target
- Next session priority: **H-008 walk-forward validation** — split data into train/test, validate on out-of-sample
