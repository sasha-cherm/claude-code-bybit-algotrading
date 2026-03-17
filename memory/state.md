# Strategy State

## Active Paper Trades

### H-009: BTC Daily EMA Trend Following (VT 20%)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: LONG 0.054885 BTC @ $73,524.10
- **Mark equity**: $10,030.02 (+0.30%) — live mark @ BTC $74,144.50
- **Leverage**: 0.40x (vol targeting: 50.0% realized → 20% target)
- **Runner**: `paper_trades/h009_btc_daily_trend/runner.py`
- **Signal**: EMA(5) > EMA(40) on daily close → LONG
- **Next check**: Next daily bar close

### H-011: Leveraged Funding Rate Arb (5x)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: OUT (rolling-27 avg funding negative since 2026-03-07)
- **Capital**: $10,000.00
- **Runner**: `paper_trades/h011_funding_rate_arb/runner.py`
- **Funding trend**: Still OUT. No new settlements processed since 00:00 UTC. Next settlement at 08:00 UTC. Recovery expected as Mar 12-14 negatives roll out of 27-window by ~Mar 21-22.
- **Next check**: Next funding settlement (every 8h)

### H-012: Cross-Sectional Momentum (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: BTC (+$6), NEAR (+$15), ATOM (-$44), AVAX (+$17)
  - SHORT: SOL (+$18), SUI (+$60), ARB (+$27), OP (-$23)
- **Mark equity**: $10,055.73 (+0.56%) — shorts outperforming, SUI short best position
- **Runner**: `paper_trades/h012_xsmom/runner.py`
- **Params**: 60d lookback, 5d rebalance, top/bottom 4
- **Next rebal**: 2026-03-21 (4 days)

## Portfolio Summary (live mark-to-market 2026-03-17 05:00 UTC)
- **Total equity**: $30,085.75 (+0.29%)
- **H-009**: $10,030.02 (+0.30%) | **H-011**: $10,000.00 (0%) | **H-012**: $10,055.73 (+0.56%)
- **Paper trade age**: 1-2 days / 28 required

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
- **BTC pullback**: BTC dropped from $75,231 to $74,144 (-1.4%) since last session. H-009 still positive but reduced from +0.90% to +0.30%.
- **H-012 short-side recovery**: SUI short (+$60) and ARB short (+$27) now profitable. OP short still slightly against (-$23). ATOM long dragging (-$44). Net: H-012 up from +0.09% to +0.56%.
- **Funding rate regime**: H-011 still OUT. No new settlements to process. Mar 12-14 negatives rolling out of window by ~Mar 21-22 — potential re-entry.
- **Decision**: No action needed. All strategies operating within expectations.
- **Watchlist**: H-012 rebalance on 2026-03-21. H-011 potential re-entry ~Mar 21-22.

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
- **Portfolio monitor**: `scripts/portfolio_monitor.py` — live mark-to-market across all strategies
- Cached data (1h, 2yr): BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM (14 assets)
- Cached data: BTC funding rates (2yr, 2194 records)
- Cached data: 14-asset funding rates (2yr, 2190 records each)

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
- **Dynamic allocation not needed**: H-011 OUT = 60% idle = auto-derisking. Static 20/60/20 has best Sharpe in all periods.
- **Current portfolio is self-regulating**: accept H-011 cyclicality, maintain allocation
