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
| H-009: BTC Daily EMA Trend + Vol Targeting | PENDING | **High** | Implement paper trade runner, deploy on testnet |
| H-010: Multi-Strategy Portfolio Research | PENDING | **High** | Research higher-Sharpe strategies: options vol selling, basis trade, microstructure |
| H-008: Multi-Asset Daily Trend Following | ANALYZED | Medium | Asset selection problem unsolved; BTC-only variant extracted as H-009 |

## Rejected Strategies
| Hypothesis | Reason |
|-----------|--------|
| H-001: EMA Crossover (4h) | Superseded by H-008/H-009 (daily better than 4h) |
| H-002: BB Mean Reversion (spot) | Long-only fails in bear market. All params negative. |
| H-003: Cross-Asset Momentum | Returns too low (<4%), drawdown too high (39%). |
| H-004: Volatility Breakout (1h) | All params negative. BTC 1h breakouts lack follow-through. |
| H-005: Funding Rate Arb | Works (Sharpe 4.7+) but absolute returns too low (1.7-3.1% annual). |
| H-006: Adaptive Mean Reversion (1h) | All params negative even with regime filter. |
| H-007: BTC/ETH Pairs Trading | Structural BTC/ETH divergence defeats mean reversion. |

## Infrastructure Status
- Data fetcher: operational (ccxt, parquet caching)
- Metrics library: operational
- Backtest engine: operational (event-driven, spot + futures + pairs modes)
- **NEW**: H-008 strategy code with walk-forward validation framework
- **NEW**: Position-level vol targeting implementation
- Cached data (1h, 2yr): BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM (14 assets)
- Cached data: BTC funding rates (2yr, 2194 records)

## Key Learnings
- 2024–2026 BTC: +1.8% total, 50% drawdown — extremely hostile for directional strategies
- Daily EMA crossover is a real signal on BTC: OOS Sharpe 0.94, parameter robust (15/15 positive)
- Multi-asset selection via past Sharpe fails walk-forward — crypto assets too regime-dependent
- Vol targeting works: controls DD proportionally (15% vol target → ~10% DD)
- **Math ceiling**: single strategy Sharpe ~0.65 → max ~15% return at 10% DD
- **Need Sharpe ≥ 2.0** for 20% return at ≤10% DD → requires multi-strategy portfolio or higher-alpha strategies
- Fee drag critical at 1h; daily timeframe (25 trades/2yr) minimizes fee impact
- Next priority: (1) deploy H-009 to paper trading, (2) research higher-Sharpe strategies for H-010
