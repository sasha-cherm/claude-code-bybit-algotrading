# Strategy State

## Active Paper Trades

### H-009: BTC Daily EMA Trend Following (VT 20%)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: LONG 0.054885 BTC @ $73,524.10
- **Mark equity**: $10,058.85 (+0.59%) — live mark @ BTC $74,670
- **Leverage**: 0.40x (vol targeting: 49.6% realized → 20% target)
- **Runner**: `paper_trades/h009_btc_daily_trend/runner.py`
- **Signal**: EMA(5) > EMA(40) on daily close → LONG
- **Next check**: Next daily bar close

### H-011: Leveraged Funding Rate Arb (5x)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: OUT (rolling-27 avg funding < 0, negative since 2026-03-07)
- **Capital**: $10,000.00
- **Runner**: `paper_trades/h011_funding_rate_arb/runner.py`
- **Risk flag**: Funding rates in downtrend. 7d avg -2.6% ann. Q1 2026 avg only 1.6% ann (worst quarter). Even best filter window achieves only ~12% ann in recent 180d at 5x.
- **Next check**: Next funding settlement (every 8h)

### H-012: Cross-Sectional Momentum (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: BTC (+$23), NEAR (+$125), ATOM (+$15), AVAX (+$63)
  - SHORT: SOL (-$48), SUI (-$49), ARB (-$47), OP (-$95)
- **Mark equity**: $9,968.06 (-0.32%) — shorts losing in broad rally (NEAR strong +$125)
- **Runner**: `paper_trades/h012_xsmom/runner.py`
- **Params**: 60d lookback, 5d rebalance, top/bottom 4
- **Next rebal**: 2026-03-21

## Portfolio Summary (live mark-to-market 2026-03-17)
- **Total equity**: $30,026.91 (+0.09%)
- **H-009**: $10,058.85 (+0.59%) | **H-011**: $10,000.00 (0%) | **H-012**: $9,968.06 (-0.32%)
- **Paper trade age**: 1 day / 28 required

## Target Portfolio Allocation
- **20% H-009** (BTC daily trend): directional alpha, Sharpe ~0.6-0.9
- **60% H-011** (funding rate arb): carry alpha, Sharpe ~15-25
- **20% H-012** (cross-sectional momentum): relative value alpha, Sharpe ~0.8-1.1
- **Combined target**: Sharpe 2.78, +40.1% return, 10.1% DD (full-period estimate)
- **Correlations**: H-009/H-011: 0.035, H-009/H-012: 0.015, H-011/H-012: -0.050

## Active Live Strategies
(none)

## Recently Killed
(none)

## Research Pipeline
| Hypothesis | Status | Priority | Next Step |
|-----------|--------|----------|-----------|
| H-010: Multi-Strategy Portfolio | BACKTEST | Low | All 3 strategies now in paper trade |
| H-013: Multi-Asset Funding Arb | REJECTED | — | Fees kill returns, all rates correlated |

## Risk Watch
- **Funding rate regime**: Rolling-27 negative since 2026-03-07 (10 days). H-011 OUT = 60% idle.
- **H-013 research conclusion**: Multi-asset funding arb REJECTED. Dynamic reallocation REJECTED. Current 20/60/20 is self-regulating — H-011 OUT acts as automatic de-risking, improving Sharpe. Even in recent 180d: +19.0% ann, Sharpe 2.14.
- **Decision**: Accept H-011 cyclicality. Portfolio remains robust. No allocation change needed.
- **Watchlist**: If funding stays negative >4 weeks AND portfolio Sharpe drops below 1.0, revisit. Otherwise maintain current allocation.

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
| H-013: Multi-Asset Funding Arb | Rates too correlated (r=0.49), fees kill multi-asset rotation. |

## Infrastructure Status
- Data fetcher: operational (ccxt, parquet caching)
- Metrics library: operational
- Backtest engine: operational (event-driven, spot + futures + pairs modes)
- H-008 strategy code with walk-forward validation framework
- H-010 multi-strategy research framework
- H-012 research + validation framework (XSMom)
- H-009 paper trade runner (internal simulation)
- H-011 paper trade runner (funding rate arb simulation)
- H-012 paper trade runner (XSMom, internal simulation)
- **Portfolio monitor**: `scripts/portfolio_monitor.py` — live mark-to-market across all strategies — NEW
- Cached data (1h, 2yr): BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM (14 assets)
- Cached data: BTC funding rates (2yr, 2194 records)
- Cached data: 14-asset funding rates (2yr, 2190 records each) — NEW
- H-013 multi-asset funding research + dynamic allocation analysis — NEW

## Key Learnings
- 2024–2026 BTC: +1.8% total, 50% drawdown — extremely hostile for directional strategies
- Daily EMA crossover is a real signal on BTC: OOS Sharpe 0.94, parameter robust (15/15 positive)
- Multi-asset selection via past Sharpe fails walk-forward — crypto assets too regime-dependent
- Vol targeting works: controls DD proportionally (15% vol target → ~10% DD)
- **Funding rate arb at 5x leverage is viable**: OOS +25.4% annual, 0.14% DD, Sharpe 29.9
- **Cross-sectional momentum is a genuine signal**: 100% params positive, rolling OOS Sharpe 0.84
- **All three strategies are uncorrelated**: r ≈ 0 pairwise — ideal diversification
- **3-strategy portfolio (20/60/20) hits targets**: Sharpe 2.78, +40.1%, 10.1% DD
- **Risk**: funding rates declining (Q1 2024: 22.7% → Q1 2026: 1.6%) — rolling-27 negative since 2026-03-07
- **Filter sensitivity**: No lookback window rescues H-011 in low-funding regime. Best recent 180d: window 36 → +12.3% ann (5x)
- Calendar/seasonality patterns in BTC: not exploitable (low t-stats, unstable across halves)
- Equal-weight all-asset trend: weak IS Sharpe (0.43), suspicious OOS (likely period-specific)
- Fee drag critical at 1h; daily/5-day rebalance minimizes fee impact
- **All 3 strategies now in paper trade** — monitor for ≥4 weeks before live consideration
- **Multi-asset funding arb doesn't help**: all crypto funding rates correlated (r=0.49). Fees from rotation kill returns.
- **Dynamic allocation not needed**: H-011 OUT = 60% idle = auto-derisking. Reallocating to H-009/H-012 increases DD more than returns. Static 20/60/20 has best Sharpe in all periods.
- **Current portfolio is self-regulating**: accept H-011 cyclicality, maintain allocation
- Next priorities: (1) monitor all 3 paper trades, (2) research genuinely new strategy type (options, orderflow) only if portfolio Sharpe drops below 1.0
