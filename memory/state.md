# Strategy State

## Active Paper Trades

### H-009: BTC Daily EMA Trend Following (VT 20%)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: LONG 0.054885 BTC @ $73,524.10
- **Leverage**: 0.40x (vol targeting: 49.6% realized → 20% target)
- **Capital**: $9,995.16 (starting $10,000)
- **Runner**: `paper_trades/h009_btc_daily_trend/runner.py`
- **Signal**: EMA(5) > EMA(40) on daily close → LONG
- **Next check**: Next daily bar close

### H-011: Leveraged Funding Rate Arb (5x)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: OUT (rolling-27 avg funding < 0)
- **Capital**: $10,000.00
- **Runner**: `paper_trades/h011_funding_rate_arb/runner.py`
- **Next check**: Next funding settlement (every 8h)

## Target Portfolio Allocation
- **30% H-009** (BTC daily trend): directional alpha, Sharpe ~0.6-0.9
- **70% H-011** (funding rate arb): carry alpha, Sharpe ~15-25
- **Combined target**: Sharpe 2.43, +34% return, 7.2% DD (full-period estimate)
- **Conservative target**: ~15-17% return, ~7% DD (recent funding rates)
- **Correlation**: 0.037 (near zero — excellent diversification)

## Active Live Strategies
(none)

## Recently Killed
(none)

## Research Pipeline
| Hypothesis | Status | Priority | Next Step |
|-----------|--------|----------|-----------|
| H-010: Multi-Strategy Portfolio | BACKTEST | Medium | Consider third strategy (options vol selling?) to further diversify |

## Rejected Strategies
| Hypothesis | Reason |
|-----------|--------|
| H-001: EMA Crossover (4h) | Superseded by H-008/H-009 (daily better than 4h) |
| H-002: BB Mean Reversion (spot) | Long-only fails in bear market. All params negative. |
| H-003: Cross-Asset Momentum | Returns too low (<4%), drawdown too high (39%). |
| H-004: Volatility Breakout (1h) | All params negative. BTC 1h breakouts lack follow-through. |
| H-005: Funding Rate Arb (1x) | Returns too low at 1x (1.7-3.1%). Superseded by H-011 (5x). |
| H-006: Adaptive Mean Reversion (1h) | All params negative even with regime filter. |
| H-007: BTC/ETH Pairs Trading | Structural BTC/ETH divergence defeats mean reversion. |

## Infrastructure Status
- Data fetcher: operational (ccxt, parquet caching)
- Metrics library: operational
- Backtest engine: operational (event-driven, spot + futures + pairs modes)
- H-008 strategy code with walk-forward validation framework
- H-010 multi-strategy research framework
- **NEW**: H-009 paper trade runner (internal simulation)
- **NEW**: H-011 paper trade runner (funding rate arb simulation)
- Cached data (1h, 2yr): BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM (14 assets)
- Cached data: BTC funding rates (2yr, 2194 records)

## Key Learnings
- 2024–2026 BTC: +1.8% total, 50% drawdown — extremely hostile for directional strategies
- Daily EMA crossover is a real signal on BTC: OOS Sharpe 0.94, parameter robust (15/15 positive)
- Multi-asset selection via past Sharpe fails walk-forward — crypto assets too regime-dependent
- Vol targeting works: controls DD proportionally (15% vol target → ~10% DD)
- **Funding rate arb at 5x leverage is viable**: OOS +25.4% annual, 0.14% DD, Sharpe 29.9
- **H-009 + H-011 are uncorrelated (r=0.037)**: perfect portfolio diversification
- **Combined portfolio can hit targets**: 30/70 split → Sharpe 2.43, +34%, 7.2% DD
- **Risk**: funding rates declining (Q1 2024: 22.7% → Q1 2026: 1.6%)
- Weekly momentum and daily mean reversion add no value beyond existing strategies
- Fee drag critical at 1h; daily timeframe (25 trades/2yr) minimizes fee impact
- Next priorities: (1) monitor paper trades, (2) explore options vol selling for third leg
