# Strategy State

## Active Paper Trades

### H-009: BTC Daily EMA Trend Following (VT 20%)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: LONG 0.054885 BTC @ $73,524.10
- **Mark equity**: $10,025 (+0.25%) — live mark @ BTC $74,061
- **Leverage**: 0.40x (vol targeting: 50.0% realized → 20% target)
- **Runner**: `paper_trades/h009_btc_daily_trend/runner.py`
- **Signal**: EMA(5) > EMA(40) on daily close → LONG
- **Next check**: Next daily bar close

### H-011: Leveraged Funding Rate Arb (5x)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: OUT (rolling-27 avg funding negative, since 2026-03-07)
- **Capital**: $10,000.00
- **Runner**: `paper_trades/h011_funding_rate_arb/runner.py`
- **Funding trend**: Still OUT. 7d avg -1.4% ann. **Projected re-entry: 2026-03-20 16:00 UTC**.
- **Next check**: Next funding settlement

### H-012: Cross-Sectional Momentum (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: BTC (+$3), NEAR (+$13), ATOM (+$38), AVAX (+$9)
  - SHORT: SOL (+$9), SUI (+$65), ARB (+$23), OP (-$48)
- **Mark equity**: $10,092 (+0.92%) — SUI short +$65 leading
- **Runner**: `paper_trades/h012_xsmom/runner.py`
- **Params**: 60d lookback, 5d rebalance, top/bottom 4
- **Next rebal**: 2026-03-21 (3 days)

## Portfolio Summary (live mark-to-market 2026-03-18)
- **Total equity**: $30,120 (+0.40%)
- **H-009**: $10,025 (+0.25%) | **H-011**: $10,000 (0%) | **H-012**: $10,092 (+0.92%)
- **Paper trade age**: 2 days / 28 required

## Target Portfolio Allocation
- **20% H-009** (BTC daily trend): directional alpha, Sharpe ~0.6-0.9
- **60% H-011** (funding rate arb): carry alpha, Sharpe ~15-25
- **20% H-012** (cross-sectional momentum): relative value alpha, Sharpe ~0.8-1.1
- **Combined (actual H-009 equity)**: Sharpe 1.38, +14.4%, 8.2% DD
- **With H-019 (15/50/15/20)**: Sharpe 1.75, +23.8%, 14.0% DD
- **Correlations**: H-009/H-011: -0.033, H-009/H-012: 0.001, H-011/H-012: 0.006, H-009/H-019: -0.094, H-012/H-019: 0.076

## Active Live Strategies
(none)

## Recently Killed
(none)

## Research Pipeline
| Hypothesis | Status | Priority | Next Step |
|-----------|--------|----------|-----------|
| H-019: Low-Volatility Anomaly | **CONFIRMED** | High | Ready for paper trade. V20_R21_N3, 5/8 WF, portfolio Sharpe 1.38→1.75 |
| H-010: Multi-Strategy Portfolio | BACKTEST | Low | Superseded by 4-strat portfolio analysis |
| H-018: Short-Term Reversal | REJECTED | — | 4% positive, crypto doesn't reverse cross-sectionally |
| H-020: Funding Rate Dispersion | REJECTED | — | 0% positive, funding rates too correlated |

## Risk Watch
- **BTC recovering**: BTC at $74,061, up from $73,949 last session. H-009 LONG +0.25%.
- **H-012 strongest**: +0.92% (was +0.62%). SUI short +$65, ATOM long +$38 leading. OP short (-$48) only drag.
- **Funding rate**: H-011 re-entry projected **2026-03-20 16:00 UTC**.
- **H-019 CONFIRMED**: Deep validation complete. Downside vol variant has 7/8 WF but standard vol (5/8 WF) is better portfolio component (lower corr with H-012).
- **Portfolio correction**: 3-strat Sharpe with actual H-009 equity is 1.38 (not 2.78 from BTC proxy). Adding H-019 brings it to 1.75.
- **Watchlist**: H-011 re-entry ~Mar 20. H-012 rebalance 2026-03-21. Prepare H-019 paper trade runner.

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
| H-014: Anti-Martingale | Fails walk-forward (1/4 folds). Corr 0.42 with H-009, redundant. |
| H-015: RSI Mean Reversion | 0/4 OOS folds positive. Interesting -0.73 corr with H-009 but no edge. |
| H-016: BB Squeeze Breakout | Only 18 trades in 2yr. 36% params positive. Overfit. |
| H-017: MTF Momentum | Corr 0.89 with H-009. 44-51% DD. Redundant. |
| H-018: Short-Term Reversal | 4% positive. Crypto momentum dominates, reversal doesn't work. |
| H-020: Funding Rate Dispersion | 0% positive. Cross-sectional carry doesn't work (rates too correlated). |

## Infrastructure Status
- Data fetcher: operational (ccxt, parquet caching)
- Metrics library: operational
- Backtest engine: operational (event-driven, spot + futures + pairs modes)
- H-008 strategy code with walk-forward validation framework
- H-010 multi-strategy research framework
- H-012 research + validation framework (XSMom)
- Cross-sectional factor research framework (`strategies/new_factors_research/`)
- **New**: H-019 deep validation v2 framework (`strategies/new_factors_research/h019_deep_validation_v2.py`)
- H-009 paper trade runner (internal simulation)
- H-011 paper trade runner (funding rate arb simulation)
- H-012 paper trade runner (XSMom, internal simulation)
- **Portfolio monitor**: `scripts/portfolio_monitor.py` — live mark-to-market across all strategies
- Cached data (1h, 2yr): BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM (14 assets)
- Cached data: BTC funding rates (2yr, 2199 records)
- Cached data: 14-asset funding rates (2yr, 2190 records each)

## Key Learnings
- 2024–2026 BTC: +1.8% total, 50% drawdown — extremely hostile for directional strategies
- Daily EMA crossover is a real signal on BTC: OOS Sharpe 0.94, parameter robust (15/15 positive)
- Multi-asset selection via past Sharpe fails walk-forward — crypto assets too regime-dependent
- Vol targeting works: controls DD proportionally (15% vol target → ~10% DD)
- **Funding rate arb at 5x leverage is viable**: OOS +25.4% annual, 0.14% DD, Sharpe 29.9
- **Cross-sectional momentum is a genuine signal**: 100% params positive, rolling OOS Sharpe 0.84
- **All three strategies are uncorrelated**: r ≈ 0 pairwise — ideal diversification
- **3-strategy portfolio with actual H-009**: Sharpe 1.38, +14.4%, 8.2% DD (corrected from 2.78 proxy estimate)
- **4-strategy portfolio with H-019**: Sharpe 1.75, +23.8%, 14.0% DD — meaningful improvement
- **Risk**: funding rates declining (Q1 2024: 22.7% → Q1 2026: 1.6%) — rolling-27 negative since 2026-03-07
- **Filter sensitivity**: No lookback window rescues H-011 in low-funding regime
- Fee drag critical at 1h; daily/5-day rebalance minimizes fee impact
- **All 3 strategies now in paper trade** — monitor for ≥4 weeks before live consideration
- **Multi-asset funding arb doesn't help**: all crypto funding rates correlated (r=0.49)
- **Dynamic allocation not needed**: H-011 OUT = 60% idle = auto-derisking. Static allocation optimal.
- **Short-term reversal doesn't work in crypto**: 4% positive (72 params). Momentum dominates.
- **H-019 low-vol CONFIRMED**: 89% params positive (standard), 99% (downside). WF: 5/8 standard, 7/8 downside. Standard vol better for portfolio (corr -0.094 with H-009 vs -0.020 for downside). Fails during strong BTC uptrends (+22-74%).
- **Downside vol variant interesting but redundant**: 7/8 WF but corr 0.223 with H-012 reduces portfolio benefit.
- **Cross-sectional carry (funding dispersion) doesn't work**: 0% positive (50 params).
- **CRITICAL: Previous 3-strat Sharpe 2.78 was overstated** — used BTC buy-and-hold as H-009 proxy. Actual H-009 EMA+VT gives 1.38. Always use actual strategy equity for portfolio estimates.
- **20 hypotheses tested total**: H-009/H-011/H-012 in paper trade. H-019 confirmed, awaiting deployment.
