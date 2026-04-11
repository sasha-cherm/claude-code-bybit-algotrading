# Hypotheses

## Live (Paper Trading)

## H-009: BTC Daily EMA Trend Following with Vol Targeting
- Status: LIVE (paper trade since 2026-03-16)
- Idea: BTC-only daily EMA(5/40) crossover with position-level vol targeting. Most defensible variant of H-008 — no asset selection needed, OOS-validated.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D (daily)
- Logic: Long when EMA(5) > EMA(40), short when EMA(5) < EMA(40). Position size scaled by target_vol / realized_vol (30-day lookback). Cap at 2x notional.
- Data: BTC only, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). OOS: 30% fixed split (~220 days).
- Result: Backtest OOS Sharpe 0.94, VT 20% gives +11.8% annual at 12.9% DD. 15/15 params positive. Paper trade started 2026-03-16: LONG 0.054885 BTC @ $73,524 (0.40x leverage).
- Notes: Part of multi-strategy portfolio (H-010). Contributes ~30% of target allocation. Uncorrelated with H-011 (r=0.037).
- Sessions: [2026-03-16 analyze, 2026-03-16 paper trade]

## H-011: Leveraged Funding Rate Arbitrage (5x)
- Status: LIVE (paper trade since 2026-03-16)
- Idea: Delta-neutral funding rate collection at 5x leverage. Long BTC spot + short BTC perp, collecting positive funding rates with rolling-27 filter.
- Instrument: futures + spot (BTC/USDT)
- Timeframe: 8h (funding settlement)
- Logic: Hold delta-neutral position (short perp + long spot) when 27-period rolling avg funding rate > 0. At 5x leverage, funding income scales linearly. Enter/exit based on rolling filter.
- Result:
  - **Full-period (2yr) at 5x**: +38.2% annual, 0.4% DD, Sharpe 24.89
  - **Walk-forward OOS (40%) at 5x**: +25.4% annual, 0.14% DD, Sharpe 29.9
  - **Conservative (last 6mo) at 5x**: +16.7% annual, 0.15% DD
  - **Correlation with H-009**: 0.037 (near zero — excellent diversifier)
  - **Portfolio 30% H-009 / 70% H-011 at 5x**: Sharpe 2.43, +34% return, 7.2% DD
- Notes: Derived from H-005 (rejected at 1x for low returns). Leverage scales returns linearly for delta-neutral strategy. Key risk: funding rates declining (22.7% → 1.6% recent). Max consecutive loss at 5x: 0.36% (vs 20% liquidation threshold — very safe). Paper trade started 2026-03-16. First full entry-exit cycle (Mar 21 00:00 → Mar 22 08:00, 32h): -1.01% due to fees + negative net funding. Currently OUT.
- Sessions: [2026-03-16 paper trade, 2026-03-22 review session 67]

## H-012: Cross-Sectional Momentum (14 Crypto Assets, Daily)
- Status: LIVE (paper trade since 2026-03-16)
- Idea: Rank 14 crypto assets by 60-day return, long top 4, short bottom 4. Market-neutral cross-sectional momentum.
- Instrument: futures (14 perps: BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM)
- Timeframe: 1D (rebalance every 5 days)
- Logic: Compute 60-day return for each asset. Rank. Long top 4 (25% each), short bottom 4 (25% each). Rebalance every 5 days using lagged (t-1) ranking.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). ~389 IS trades over 1.8yr. WF: 6 folds x 90d test = 540 total OOS days.
- Result:
  - **In-sample (full)**: Sharpe 1.11, +49.7% annual, 30.6% DD
  - **Rolling walk-forward OOS (6 folds, 90d each)**: Sharpe 0.84, +27.5% annual, 20.6% DD
  - **Param robustness**: 45/45 positive Sharpe (100%), mean 0.54, median 0.57
  - **Fee sensitivity**: Sharpe 0.88 even at 5x fees (very robust)
  - **Correlation with H-009**: 0.015 (near zero)
  - **Correlation with H-011**: -0.050 (slightly negative — excellent)
  - **3-strategy portfolio (20/60/20)**: Sharpe 2.78, +40.1% annual, 10.1% DD
- Notes: Captures cross-sectional momentum premium in crypto (winners keep winning, losers keep losing). Market-neutral so no directional exposure. 5/6 walk-forward folds positive. Rolling OOS 20.6% DD is the main concern — manageable with vol targeting or position sizing. Calendar and equal-weight trend alternatives were also tested and rejected. Paper trade deployed 2026-03-16: LONG BTC/NEAR/ATOM/AVAX, SHORT SOL/SUI/ARB/OP.
- Sessions: [2026-03-16 research session 5, 2026-03-16 paper trade session 6]

## Confirmed
(none — H-012/H-019/H-021/H-024 promoted to LIVE)

## H-054: Multi-Asset Polymarket Hourly + 4H Candle Direction (7 Assets)
- Status: CONFIRMED (research complete, extends H-037)
- Idea: Analyze green/red candle probability at each 1h and 4h time slot for all Polymarket crypto assets (BTC, ETH, SOL, XRP, DOGE, HYPE, BNB). Find statistically significant time-of-day biases.
- Instrument: Polymarket binary options (1h UP/DOWN, 4h UP/DOWN)
- Timeframe: 1h and 4h
- Logic: Binomial test (H0: P(green)=50%) per slot per asset. Train/test split validation. Cross-asset consensus scoring.
- Data: ~17,600 hourly bars (2yr) per asset for BTC/ETH/SOL/XRP/DOGE/BNB; ~6,000 bars (8mo) for HYPE. 210 total statistical tests.
- Result:
  - **39 significant results** (p<0.05, consistent train/test) across 7 assets, 8 survive Bonferroni
  - **Per-asset 1H significant hours**:
    - BTC: 17:00 56.4% UP (p=0.0006***), 21:00 54.8% UP, 23:00 54.1% DOWN, 22:00 53.9% UP
    - ETH: 23:00 56.5% DOWN (p=0.0005***), 21:00 55.1% UP, 17:00 54.4% UP
    - SOL: 23:00 55.8% DOWN (p=0.0019***), 22:00 55.5% UP, 17:00 55.2% UP, 21:00 54.7% UP, 01:00 53.7% UP
    - XRP: 23:00 57.2% DOWN (p=0.0001***), 20:00 54.9% DOWN, 00:00 53.8% DOWN, 07:00 53.8% UP
    - DOGE: 21:00 55.2% UP, 17:00 54.9% UP
    - HYPE: 12:00 58.7% DOWN (only 8mo data)
    - BNB: 21:00 56.8% UP (p=0.0002***), 22:00 56.0% UP (p=0.0013***), 03:00 55.1% UP, 23:00 54.5% DOWN, 19:00 53.7% UP
  - **Per-asset 4H significant hours**:
    - ETH: 20-24 54.5% UP, 12-16 54.4% DOWN
    - SOL: 12-16 56.0% DOWN (p=0.0013***), 00-04 54.8% UP
    - XRP: 20-24 56.0% DOWN (p=0.0013***), 08-12 54.3% UP, 00-04 54.1% UP
    - DOGE: 00-04 54.5% UP, 12-16 54.0% DOWN, 20-24 53.8% UP
    - HYPE: 12-16 57.9% DOWN
    - BNB: 00-04 54.4% UP, 12-16 54.2% DOWN, 20-24 54.2% UP, 16-20 53.8% UP
  - **Bonferroni survivors (8)**: XRP 23:00 DOWN, BNB 21:00 UP, ETH 23:00 DOWN, BTC 17:00 UP, BNB 22:00 UP, SOL 4h 12-16 DOWN, XRP 4h 20-24 DOWN, SOL 23:00 DOWN
  - **Universal themes**: 23:00 RED (5 assets), 17:00/21:00 GREEN (4-5 assets), 12-16 4H RED (5 assets)
- Notes: Re-analyzed per user request to report each asset independently (not just cross-asset consensus). Report script: `strategies/polymarket_research/h054_per_asset_report.py`. Edge ~4-7% above 50% — only viable if Polymarket prices at ~50c.
- Sessions: [2026-03-20 research], [2026-03-20 research — per-asset independent report]

## H-055: Comprehensive Portfolio Optimization (14 Strategies)
- Status: CONFIRMED
- Idea: Full mean-variance portfolio optimization across all 14 deployable strategies. Find optimal allocations using max Sharpe, risk parity, and exhaustive N-strategy subset search.
- Instrument: portfolio of all instruments
- Timeframe: daily (portfolio-level)
- Logic: Generate daily return series for each strategy on 2yr data. Build full correlation matrix. Optimize using scipy constrained optimization. Test N-strategy subsets exhaustively.
- Data: 14 strategies, 195 overlapping daily bars (2025-09-03 to 2026-03-16, limited by H-049 data).
- Result:
  - **Current 5-strat portfolio**: Sharpe 4.32, +55.6%, 4.7% DD
  - **H-024 replacing H-019**: Sharpe 4.76, +61.8%, 4.0% DD
  - **Optimal 14 (40% cap)**: Sharpe 7.74, +64.4%, 1.2% DD — H-011(40%)/H-039(12%)/H-059(12%)/H-053(9%)/H-044(9%)/H-021(5%)/H-049(5%)
  - **Best 5-strat (no H-011)**: H-021/H-024/H-039/H-049/H-053 → **Sharpe 7.88, +146.9%, 3.6% DD**
  - **Best 7-strat**: H-011(50%)/H-021/H-024/H-039/H-044/H-053/H-059 → **Sharpe 7.96, +58.2%, 1.1% DD**
  - **Best 8-strat**: H-011(50%)/H-021(4%)/H-024(4%)/H-039(11%)/H-044(10%)/H-049(3%)/H-053(8%)/H-059(11%) → **Sharpe 8.02, +58.6%, 1.1% DD**
  - **Equal weight 14**: Sharpe 5.96, +88.2%, 4.0% DD
  - **Risk parity 14**: Sharpe 6.04, +72.4%, 3.2% DD
  - **H-059 appears in ALL optimal allocations** at 10-14% weight — uniquely low correlations with core
  - **H-059 key correlations**: -0.109 H-011, -0.107 H-044, -0.148 H-049, 0.003 H-046, 0.036 H-039
  - **H-044 (OI divergence) gains importance**: appears in best 7-strat and 8-strat
  - **H-012 and H-019 still drop** from optimal — replaced by H-024, H-031, H-059
- Notes: Updated session 68 to include H-059 (vol term structure). The 195-day common period (limited by H-049) may inflate Sharpe numbers vs the full 700-day optimization. H-059 is a strong diversifier — its vol-expansion signal captures something fundamentally different from positioning/momentum factors. Still need 4+ weeks of paper trading before implementing any allocation changes.
- Sessions: [2026-03-20 research session 50, 2026-03-22 research session 68]

## H-059: Volatility Term Structure Factor (Expansion-Long, 14 Assets)
- Status: LIVE (paper trade since 2026-03-22)
- Idea: Compare short-term (7d) vs long-term (30d) realized volatility. Long assets with expanding vol (short/long ratio > 1), short assets with contracting vol. Vol expansion signals emerging trends and capital inflows.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 7 days)
- Logic: For each asset, compute ratio = std(returns, 7d) / std(returns, 30d). Rank. Long top 5 (most expanding vol), short bottom 5 (most contracting).
- Data: 14 assets, 740 daily bars (~2yr).
- Result:
  - **IS (full)**: Sharpe 2.57, +149.9% ann, 24.5% DD
  - **OOS (70/30)**: Sharpe **2.48**, +96.4% ann, 8.7% DD — OOS matches IS
  - **Walk-forward (6 folds, 90d)**: **4/6 positive**, mean Sharpe 1.23. Recent folds strongest (2.93, 2.38)
  - **Split-half**: 2.75 / 1.53 — both halves strong
  - **Param robustness**: **130/144 positive** (90%), mean Sharpe 0.64
  - **Fee sensitivity**: 2.10 at 5x fees (very robust)
  - **Correlation**: 0.312 H-012, **0.034 H-019** (near zero)
- Notes: Counterintuitive direction — expanding vol (not contracting) predicts positive returns. In crypto, vol expansion signals money flowing into an asset (attention, volume, institutional interest). Contracting vol signals being ignored. Paper trade deployed 2026-03-22: LONG OP/ARB/XRP/ATOM/ETH, SHORT DOGE/SUI/BTC/NEAR/DOT.
- Sessions: [2026-03-22 research+paper trade session 66]

## H-063: Systematic BTC Short Strangle with Delta Hedging (Vol Selling)
- Status: LIVE (paper trade since 2026-03-25)
- Idea: Sell weekly 3% OTM BTC strangles, delta-hedge daily with BTCUSDT perp. Captures the volatility risk premium (IV consistently exceeds realized vol ~68% of the time). 10% stop-loss to limit tail risk.
- Instrument: options (BTC-USDT strangles) + futures (BTCUSDT perp for delta hedge)
- Timeframe: 7 days (weekly trade cycle)
- Logic: Every 7 days, sell 1 ATM-3% OTM call + 1 ATM-3% OTM put on the nearest weekly expiry. Delta-hedge daily using BTCUSDT perp. If running PnL < -10% of notional, close at market (stop-loss). At expiry, settle and repeat.
- Data: BTC daily, 740 bars (~2yr). IV surface: 5 snapshots (2026-03-20 to 2026-03-24).
- Result:
  - **Full-period (3% OTM, 7d, 10% stop)**: Sharpe **1.54**, +52.5% ann, -18.4% DD, 73% WR, 101 trades
  - **Walk-forward (6 folds, 90d)**: **6/6 positive**, mean Sharpe **1.91**
  - **Split-half**: 0.74 / 1.53 — both halves positive, second half stronger
  - **70/30 split**: IS 1.37, OOS 0.54 — OOS positive
  - **Param robustness**: **60/60 positive** (100%) — strongest of any strategy tested
  - **Fee sensitivity**: Sharpe 1.24 even at **5% option spread** (extremely robust)
  - **Correlation**: -0.104 vs H-009 (BTC trend), 0.006 vs BTC returns — truly market-neutral
  - **VRP stats**: Mean VRP +4.3%, IV > RV 68% of time. Long-dated BTC ATM IV stable at ~50%.
  - **Liquidity**: BTC weekly options on Bybit: OI 7-8k, vol 1-2k/day, near-ATM spreads 1-5%
  - **Variant comparison (all 7d, 10% stop)**:
    - ATM straddle: Sharpe 1.81, +60.8%, -17.7% DD
    - 3% OTM strangle: Sharpe 1.54, +52.5%, -18.4% DD
    - 5% OTM strangle: Sharpe 1.87, +44.8%, -15.3% DD, 78% WR — best risk-adjusted
    - 7% OTM: Sharpe 1.62, +27.5%, -10.1% DD, 86% WR — lowest risk
- Notes: First options strategy in the system. Edge comes from: (1) theta decay fastest in final week, (2) BTC IV ~50% consistently exceeds average RV ~46%, (3) delta hedging isolates vol premium from directional risk. Key risk: tail events (worst trade -13.4% with stop). Real execution uses Bybit option bids for selling, actual mark prices for MTM. Paper trade runner queries live Bybit options quotes. Entry at 01:00 UTC daily.
- Sessions: [2026-03-25 research+paper trade session 86]

## H-085: Turnover Velocity Factor (14 Crypto Assets)
- Status: LIVE (paper trade since 2026-03-26)
- Idea: Rank 14 crypto assets by turnover velocity (5-day avg dollar volume / 20-day avg dollar volume). Long top 4 (highest volume surge = growing institutional attention), short bottom 4 (declining interest). Market-neutral.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 7 days)
- Logic: For each asset, compute ratio = mean(dollar_vol, 5d) / mean(dollar_vol, 20d). Rank. Long top 4, short bottom 4.
- Data: 14 assets, 746 daily bars (~2yr).
- Result:
  - **Full-period (best)**: Sharpe **2.08** (L30_R10_N4), +109% ann, -23% DD, 50% WR
  - **Parameter robustness**: **48/48 positive** (100%) — strongest ever tested, mean Sharpe 1.48
  - **Walk-forward (param-selected, 4 folds)**: **3/4 positive**, mean Sharpe **2.37**
  - **Walk-forward (fixed params, 4 folds)**: 2/4 positive, mean Sharpe 0.15 — param-dependent
  - **Split-half**: 93.8% of params positive in both halves. Half means: 2.05 / 0.84
  - **70/30 split**: Train 2.27, Test 0.23 — OOS weaker with fixed params
  - **Correlation with H-012**: **0.21** (moderate)
  - **Fee sensitivity**: Sharpe 1.48 median even with fees included
- Notes: 100% param robustness is exceptional. The signal captures attention/interest shifts — volume surging means capital inflow. Fixed-param OOS is weaker (signal is real but optimal params shift over time). Deployed with L20_R7_N4 (recent WF best). Paper trade: LONG BTC/ARB/OP/ATOM, SHORT ETH/XRP/DOGE/NEAR.
- Sessions: [2026-03-26 review+research session 92]

## Pending

## H-058: Residual Momentum Factor (14 Assets)
- Status: CONDITIONAL — promising but too correlated with H-012
- Idea: Cross-sectional momentum after stripping out BTC beta. Rank assets by cumulative residual returns (after OLS regression vs BTC). Long top residual momentum, short bottom.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: For each alt, compute daily residuals = alt_return - beta * BTC_return over lookback window. Rank by cumulative residual. Long top N, short bottom N.
- Data: 14 assets, 740 daily bars (~2yr).
- Result:
  - **IS (full)**: Best Sharpe 1.31 (LB=30, REB=7, N=3), +66.1% ann, 31.7% DD
  - **Param robustness**: **48/48 positive** (100%) — exceptionally strong
  - **Walk-forward**: 4/6 positive, mean Sharpe 0.87
  - **70/30 split**: IS 1.75, OOS -0.30 (fails)
  - **Correlation with H-012**: **0.672** (too high — limited diversification value)
  - **Fee sensitivity**: 1.00 at 5x fees
- Notes: Would only deploy if replacing H-012 from portfolio. Signal is fundamentally momentum with BTC beta stripped out — not different enough.
- Sessions: [2026-03-22 research session 66]

## H-010: Multi-Strategy Portfolio Research
- Status: BACKTEST — expanded to 3-strategy portfolio
- Idea: Research and combine multiple uncorrelated strategies to achieve Sharpe ≥ 2.0 via diversification.
- Instrument: mixed
- Timeframe: mixed
- Logic: Identify 3-5 strategies with low correlation. Portfolio allocation based on Sharpe contribution.
- Result:
  - **Leveraged funding rate arb**: Best candidate → promoted to H-011. At 5x: +38.2% annual, Sharpe 24.89
  - **Cross-sectional momentum**: Promoted to H-012. OOS Sharpe 0.84, 100% params positive
  - **Weekly momentum**: Best Sharpe 0.63 (4w lookback), +19.2% return but 35.9% DD — not viable
  - **Basis/carry trade**: Essentially same as funding arb (7.3% annual) — no incremental value
  - **Daily mean reversion**: All negative — BTC doesn't mean-revert despite lag-1 autocorrelation -0.08
  - **Portfolio combo (H-009 + H-011)**: 30/70 at 5x → Sharpe 2.43, +34%, 7.2% DD
  - **Conservative combo**: 10/90 at 5x → Sharpe 3.40, +15.4%, 6.8% DD
- Notes: Three-strategy portfolio (H-009 + H-011 + H-012) with 20/60/20 allocation achieves Sharpe 2.78, +40.1%, 10.1% DD. All pairwise correlations near zero. Conservative estimate with declining funding rates still achieves ~20%+ return. Could explore fourth strategy (options vol selling?) for further boost.
- Sessions: [2026-03-16 analyze, 2026-03-16 paper trade, 2026-03-16 research]

## H-001: EMA Crossover Trend Following (BTC Futures)
- Status: REJECTED
- Idea: Classic dual-EMA crossover on BTC/USDT perpetual futures with volatility-scaled position sizing
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Logic: Long when EMA(20) > EMA(50), short when EMA(20) < EMA(50). Position size = target_risk / ATR(14). Stop-loss at 2×ATR. Take-profit at 3×ATR or trail.
- Result: Superseded by H-008/H-009 (daily timeframe works better than 4h).
- Notes: 4h timeframe inferior to daily. H-008 tested daily EMA crossover comprehensively.
- Sessions: [2026-03-15 research, 2026-03-16 analyze]

## Analyzed (Walk-Forward Validated)

## H-008: Multi-Asset Daily Trend Following (Futures Portfolio)
- Status: ANALYZED — partially validated
- Idea: EMA crossover trend following on daily timeframe across a diversified crypto futures portfolio. Equal-weight allocation across top-performing assets selected by in-sample Sharpe.
- Instrument: futures (BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM — 14 assets tested)
- Timeframe: 1D (daily)
- Logic: Long when EMA(5) > EMA(40), short when EMA(5) < EMA(40). Full allocation per asset, equal weight across portfolio assets.
- Result:
  - **In-sample (full)**: Top-3 Sharpe 1.03, +53.4%, 57.3% DD | BTC-only Sharpe 0.70, +22.5%
  - **Fixed-split OOS (30%)**: Top-3 Sharpe 0.94, +34.2%, 19.5% DD | BTC-only Sharpe 0.94, +30.2%, 16.5% DD
  - **Rolling walk-forward (top-5, 6mo rebal)**: Sharpe -0.84, -43.4% — **FAILS**
  - **Rolling walk-forward (top-3, 3mo rebal)**: Sharpe -0.59, -37.1% — **FAILS**
  - **BTC-only OOS VT 20%**: Sharpe 0.59, +11.8%, 12.9% DD
  - **Top-3 OOS VT 12%**: Sharpe 0.76, +9.7%, 7.2% DD
  - **Param robustness**: 15/15 param sets positive Sharpe (0.50–0.86), mean 0.69
- Notes:
  - **Signal is real**: BTC daily EMA crossover OOS Sharpe 0.94 (higher than IS 0.59), 15/15 params positive
  - **Asset selection is fragile**: rolling walk-forward fails because past Sharpe doesn't predict future for altcoins
  - **Vol targeting works**: controls DD to target level at cost of proportional return reduction
  - **Math ceiling**: Sharpe ~0.65 means max ~15% return at 10% DD. Cannot hit 20%/10% with single strategy
  - **Recommendation**: BTC-only variant (H-009) is paper-trade ready. Multi-asset needs better selection method.
- Sessions: [2026-03-16 backtest, 2026-03-16 analyze]

## H-062: Max Drawdown Momentum Factor (14 Assets)
- Status: LIVE (paper trade since 2026-03-22)
- Idea: Rank assets by distance from 60-day peak. Long top 3 (nearest peak = momentum winners), short bottom 3 (deepest drawdown = losers). Momentum variant using peak distance rather than raw returns.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5 days)
- Logic: For each asset, compute price / 60-day-high - 1. Rank. Long top 3 (nearest peak), short bottom 3 (farthest from peak). Lagged (t-1).
- Data: 14 assets, 740 daily bars (~2yr).
- Result:
  - **IS (full)**: Sharpe 1.67, +44.9% ann, 21.2% DD
  - **Param robustness**: **33/36 positive (92%)** — exceptionally strong
  - **Walk-forward**: **6/6 positive**, mean OOS Sharpe **2.23**, min 0.15, max 4.04
  - **Split-half**: 1.59 / 1.79 — **stable across both halves**
  - **70/30 split**: IS 1.15, OOS 3.41 — OOS outperforms IS
  - **Fee sensitivity**: 1.36 at 5x fees (very robust)
  - **Correlation with H-012**: **0.600** (high — momentum variant)
  - **Correlation with H-019**: 0.424, H-021: -0.044
  - **Portfolio contribution**: Adding to 3-factor base improves Sharpe 1.15 → 1.49, gets 58% weight
- Notes: Strongest validation of any new factor. Essentially captures momentum from a different angle (distance from peak vs cumulative return). High correlation with H-012 but better standalone metrics (6/6 WF vs 5/6). Deployed as independent paper trade for comparison.
- Sessions: [2026-03-22 research session 69]

## H-061: Idiosyncratic Volatility Factor (14 Assets)
- Status: CONDITIONAL — strong OOS but regime-dependent
- Idea: Regress each alt's returns on BTC (market factor). Rank by residual volatility. Long low-IVOL (stable alphas), short high-IVOL (lottery-ticket alts).
- Instrument: futures (13 perps, excludes BTC)
- Timeframe: 1D
- Logic: For each alt, OLS regress daily returns on BTC returns over lookback. Compute std(residuals) = idiosyncratic vol. Rank. Long lowest 5, short highest 5.
- Data: 14 assets, 740 daily bars (~2yr).
- Result:
  - **IS (full)**: Best Sharpe 1.10, +18.8% ann, 19.9% DD (L20_R10_N5)
  - **Param robustness**: **27/36 positive (75%)**
  - **Walk-forward**: 5/6 positive, mean OOS Sharpe 1.76
  - **Split-half**: H1 0.08 / H2 2.49 — **only works in second half (regime-dependent)**
  - **70/30 split**: IS 0.29, OOS 3.82 — OOS massively better (suspicious)
  - **Fee sensitivity**: 1.00 at 5x fees (very robust — low turnover R10)
  - **Correlation with H-019**: **0.563** (related to low-vol factor)
  - **Correlation with H-012**: -0.167 (negative — good diversifier from momentum)
  - **Portfolio contribution**: Adding replaces H-019 entirely, improves Sharpe 1.15 → 1.46
- Notes: Low-IVOL puzzle exists in crypto. However, the signal only works in the second half of the sample (2025+). Could be a regime shift or could be a spurious result. Need to observe before deploying. Would replace H-019 in portfolio if confirmed.
- Sessions: [2026-03-22 research session 69]

## Confirmed
(none)

## Rejected

## H-060: Return Skewness Factor (14 Assets)
- Status: REJECTED — OOS decay, redundant with momentum
- Idea: Rank assets by return skewness. Long positive-skew (upside potential), short negative-skew.
- Result: 72% params positive, best Sharpe 1.52. But OOS: IS 2.10 → OOS 0.02 (decays). Split-half: 2.84/0.14 (unstable). Corr 0.609 with H-012 (essentially momentum). Rejected.
- Sessions: [2026-03-22 research session 69]

## H-063: Return Autocorrelation Factor (14 Assets)
- Status: REJECTED — weak, no clear direction
- Idea: Rank by lag-1 return autocorrelation. Neither direction worked reliably. Best: 42% positive, Sharpe 1.08 but inconsistent.
- Sessions: [2026-03-22 research session 69]

## H-064: Weekend Effect Cross-Sectional Factor (14 Assets)
- Status: REJECTED — no signal
- Idea: Test if crypto assets behave differently on weekends vs weekdays. XS weekend momentum/reversal.
- Result: No asset shows significant weekend vs weekday return difference (all p>0.2). Monday returns also non-significant (best: XRP p=0.123). No exploitable day-of-week effect beyond H-039 (already captured).
- Sessions: [2026-03-22 review+research session 70]

## H-065: Crypto Sector Rotation Factor
- Status: REJECTED — redundant with momentum/size
- Idea: Group 14 assets into sectors (L1/L2/Payment/DeFi), rotate based on sector momentum.
- Result: IS Sharpe 1.77, OOS 0.98 for best setting (LB=30 REB=10). WF 3/4. 90% params positive. BUT: corr 0.611 with H-012, 0.515 with H-031, 0.655 with static Payment/L2 bet. Only 4 sectors with 0.78-0.90 correlations — essentially a coarser version of existing momentum/size.
- Sessions: [2026-03-22 review+research session 70]

## H-066: Intraday Range Factor (14 Assets)
- Status: REJECTED — no signal
- Idea: Rank assets by (high-low)/close ratio. Test narrow-range (accumulation) vs wide-range (breakout) directions.
- Result: 50% params positive (24/48) — exactly random. Mirror image pattern: narrow_long and wide_long are perfect inverses. No edge.
- Sessions: [2026-03-22 review+research session 70]

## H-067: Amihud Illiquidity Factor (14 Assets)
- Status: REJECTED — redundant with size factor
- Idea: Rank by |return|/volume (Amihud illiquidity ratio). Test illiquidity premium vs liquidity preference.
- Result: Liquid_long direction has 100% positive params, best Sharpe 1.90, WF 3/4. BUT: corr **0.910** with H-031 (size). Always LONG BTC/ETH/SOL/XRP (liquid=large), SHORT DOT/OP/ARB/ATOM (illiquid=small). Identical to size factor.
- Sessions: [2026-03-22 review+research session 70]

## H-068: Open-Close Gap Factor (14 Assets)
- Status: REJECTED — no signal (artifact)
- Idea: Rank by average open-close gap. Gap momentum or reversal.
- Result: 100% params positive (48/48) BUT both directions identical — gap_up_long and gap_down_long produce same results. In 24/7 crypto markets, open ≈ previous close, so gap is ~0 and rankings are arbitrary. Artifact, not signal.
- Sessions: [2026-03-22 review+research session 70]

## H-069: Extreme Move Frequency Factor (14 Assets)
- Status: REJECTED — OOS degrades, fee fragile
- Idea: Count days with |return| > 2*rolling_std in recent window. Long assets with more extreme moves (attention/regime signal).
- Result: 78% params positive, best Sharpe 2.63, WF **6/6** positive (mean 3.09). BUT: split-half 4.11→0.20 (collapses), 70/30 OOS 0.24, fee-fragile (2x fees Sharpe 0.10). Corr 0.40 H-012, 0.43 H-062.
- Sessions: [2026-03-22 review+research session 70]

## H-070: Volatility-of-Volatility Factor (14 Assets)
- Status: REJECTED — no signal
- Idea: Rank by std of rolling volatility (vol-of-vol). Test if stable-vol or unstable-vol assets outperform.
- Result: 50% params positive (24/48) — noise. Both directions roughly mirrored.
- Sessions: [2026-03-22 review+research session 70]

## H-071: Return-Volume Correlation Factor (14 Assets)
- Status: REJECTED — no signal
- Idea: Rank by rolling correlation between returns and volume. Positive corr = healthy trend.
- Result: 50% params positive (12/24) — noise. Best individual Sharpe 1.57 but no consistency.
- Sessions: [2026-03-22 review+research session 70]

## H-072: Expanded Universe Cross-Sectional Momentum (25 Assets)
- Status: REJECTED — worse than 14-asset universe
- Idea: Expand momentum universe from 14 to 25 assets (adding BNB, LTC, APT, TAO, AAVE, WLD, CRV, TRX, FIL, ICP, INJ) to increase cross-sectional dispersion and improve factor performance.
- Instrument: futures (25 USDT perps)
- Timeframe: 1D
- Logic: Same as H-012 (XS momentum) but on expanded universe. Tested LB=14/30/60d, Rebal=3/5d, N=4-10.
- Data: 741 daily bars (2024-03-15 to 2026-03-25) for all 25 assets. Also tested 37 assets for data availability.
- Result:
  - **14-asset (H-012 baseline)**: Sharpe **1.12**, +26.9% ann, -16.3% DD (LB=60, R=5, N=4)
  - **25-asset (same params)**: Sharpe **-0.04**, -5.6% ann, -34.4% DD — dramatically worse
  - **25-asset optimal N=7**: Sharpe 0.24 — still far worse than 14-asset
  - **Individual additions**: Only BNB (+0.07 Sharpe) and APT (+0.11 Sharpe) marginally help. CRV (-0.40), ICP (-0.57), FIL (-0.28), LTC (-0.25), TRX (-0.26) all hurt badly.
  - **Size factor also worse**: 14-asset Sharpe 0.16 vs 25-asset Sharpe -0.13
- Notes: The original 14-asset universe was well-curated. New assets have poor momentum characteristics: LTC/TRX are low-vol stableish, ICP/FIL/WLD have persistent downtrends, CRV is choppy. Adding noise assets dilutes the cross-sectional signal. The 14-asset universe captures the right mix of liquid + volatile + trending assets.
- **Key finding**: Also discovered that H-012 (momentum) and H-062 (DD momentum) have **100% position agreement** — effectively the same signal. H-021 (vol mom) and H-046 (acceleration) also align 4/4. This matters for H-056 portfolio construction.
- Sessions: [2026-03-25 review+research session 87]

## H-073: Session-Based Crypto Return Decomposition (14 Assets)
- Status: REJECTED — no stable session bias across time periods
- Idea: Trade session-specific return biases. Short during Europe (08-16 UTC, negative avg return), long during US (16-00 UTC, positive avg return). Cross-asset equal-weight portfolio.
- Instrument: futures (14 perps)
- Timeframe: 8h (session-level)
- Logic: Decompose daily returns into Asia/Europe/US sessions. Europe has avg -0.05%/session across 12/14 assets; US has +0.05% across 10/14. Strategy: Short Europe + Long US.
- Data: 14 assets, ~1,725 days of 1h data (~4.7yr for BTC, shorter for some alts).
- Result:
  - **Per-asset train/test**: Only **2/14 consistent** (DOGE, NEAR). Mean train Sharpe +0.79, mean test -0.17.
  - **Equal-weight portfolio**: Train Sharpe -0.08, Test Sharpe -0.19. Both periods negative.
  - **Walk-forward (6 folds, 90d)**: Only 2/6 positive (mean Sharpe 2.02 skewed by Fold 4 outlier +11.95).
  - **Significant individual sessions**: XRP US (p=0.003), SUI US (p=0.028) — but not tradeable standalone.
  - **ANOVA significant**: XRP (p=0.007), DOGE (p=0.042) — but session effects flip between periods.
  - **After fees**: Completely washed out (4 trades/day × 0.055% = 80% annual fee drag).
- Notes: The session bias exists in aggregate (Europe underperforms, US outperforms) but is not stable across time periods. The effect flips between bullish and bearish regimes. With 4 trades per day, fees destroy any residual edge. Not viable.
- Sessions: [2026-03-25 review+research session 88]

## H-074: Volume-Price Divergence Factor (14 Assets)
- Status: CONDITIONAL — real signal but inconsistent walk-forward
- Idea: Cross-sectional factor based on volume-price divergence. Long assets where volume is rising faster than price (accumulation signal), short assets where volume is falling relative to price (distribution signal).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 7 days)
- Logic: For each asset, compute divergence_score = (volume_change_10d - price_change_5d). Rank. Long top 4 (high divergence = accumulation), short bottom 4 (low divergence = distribution).
- Data: 14 assets, 740 daily bars (~2yr).
- Result:
  - **Full period (VL=10, PL=5, REB=7, N=4)**: Sharpe **1.27**, +46.1% ann, -36.2% DD, 54% WR
  - **After fees**: Sharpe **0.51**, +18.5% ann (1.37 trades/day, 27.6% fee drag)
  - **IS (70%)**: Sharpe 1.23 | **OOS (30%)**: Sharpe **1.90** — OOS outperforms IS (unusual and positive)
  - **Split-half**: 1.49 / 2.89 — **both halves strong**, second half better
  - **Walk-forward (6 folds, 90d)**: Only **2/6 positive** (mean 0.71, inflated by outlier fold)
  - **Param robustness (neighbors)**: **49/81 positive (60%)**
  - **Param robustness (full sweep)**: **56/81 positive (69%)**
  - **Correlation**: -0.18 vs H-012 (momentum), +0.34 vs H-021 (vol mom), -0.06 vs H-031 (size), +0.01 vs BTC
  - **Best fee-robust params (VL=30, PL=5, REB=10, N=4)**: Sharpe 3.21 full but OOS -1.33 — fails
  - **Regime note**: Momentum direction (reversed) works in OOS for long-lookback params — signal may flip between contrarian and momentum modes
- Notes: Signal is real — the OOS outperforming IS is strong evidence. Low correlation with existing factors makes this a good diversifier. However, walk-forward failure (2/6) indicates the signal is regime-dependent. The factor seems to work well in trending markets (2025-H2) and poorly in choppy markets (2024-Q4). Would need an adaptive component or longer observation before deployment. Could be combined with existing momentum signals as a secondary filter.
- Sessions: [2026-03-25 review+research session 88]

## H-075: Risk-Adjusted Momentum Factor (14 Assets)
- Status: REJECTED — no improvement over raw momentum + high correlation
- Idea: Rank assets by return/volatility (asset-level Sharpe ratio) instead of raw return. Long high risk-adjusted momentum, short low.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result:
  - **Param robustness**: 92% positive (133/144) — but raw momentum is 94%
  - **Head-to-head**: Inconsistent vs raw — helps at LB=40, hurts at LB=60/90
  - **Best (LB=40, VW=60, REB=10, N=3)**: WF 4/6, mean Sharpe 2.31
  - **Split-half**: 11.02 / -2.63 — **catastrophic second half**
  - **Correlation with H-012**: 0.76 (too high)
- Notes: Risk-adjustment doesn't consistently improve over raw momentum in crypto. Second-half failure = only works in trending markets. Redundant with H-012.
- Sessions: [2026-03-26 review+research session 89]

## H-076: Price Efficiency Factor (14 Assets)
- Status: LIVE (paper trade since 2026-03-26)
- Idea: Rank assets by price efficiency = abs(net_close_change) / sum(daily_high_low_range) over lookback. High efficiency = clean directional move, low = noisy/choppy. Long most efficient, short most noisy.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5 days)
- Logic: For each asset over 40 days (lagged t-1): efficiency = |close_end/close_start - 1| / sum(high_i/low_i - 1). Rank. Long top 4, short bottom 4.
- Data: 14 assets, 745 daily bars (~2yr).
- Result:
  - **True daily Sharpe**: 1.94, +106.3% ann, -23.5% DD, 54.1% WR
  - **70/30 split**: OOS matches IS (both ~1.4+ daily Sharpe)
  - **Walk-forward**: **6/6 positive** (best of any factor tested)
  - **Split-half**: both halves strongly positive
  - **Param robustness**: 77% positive (46/60)
  - **Fee sensitivity**: positive to 5x fees
  - **Correlation with H-012 (momentum)**: **0.038** — genuinely different signal
  - **Correlation with H-059/H-019**: <0.10 — near zero with all
  - **Direction clarity**: Long efficient 79% positive, long noisy **0% positive**
  - **Signal nature**: -0.13 rank correlation with momentum — NOT momentum in disguise
- Notes: Most novel signal. Efficiency captures "trend quality" not direction. All existing strategies have <0.1 correlation. Note: lib/metrics.py Sharpe uses 8760 periods/yr (hourly default) for daily data — inflates by ~5x. True daily Sharpe is ~1.94. Deployed: LONG OP/NEAR/ATOM/ARB, SHORT ADA/DOGE/SUI/XRP.
- Sessions: [2026-03-26 review+research session 89]

## H-056: Short-Term Reversal Factor (1-5 Day, 14 Assets)
- Status: REJECTED
- Idea: Cross-sectional reversal — long recent losers (1-5d), short winners. Anti-correlated with momentum.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: Best IS Sharpe 1.26 (LB=2, REB=3, N=4), but **70/30 OOS Sharpe -1.61** (complete failure). WF 3/5 positive but mean -0.26. Only 35% of params positive. Edge decayed — last WF fold Sharpe -3.03.
- Notes: Short-term reversal was viable historically but has completely decayed in crypto. Classic alpha decay.
- Sessions: [2026-03-22 research session 66]

## H-057: Cross-Asset Lead-Lag Factor (BTC/ETH→Alts)
- Status: REJECTED
- Idea: Exploit information diffusion from BTC/ETH to altcoins. Score alts by residual vs leader return (lagging alts expected to catch up).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: Best IS Sharpe 1.68 (BTC, LB=2, REB=7, N=5). WF 3/5 positive but extreme variation (-3.39 to +1.52), mean -0.35. 70/30 OOS Sharpe 0.65 (marginal). Only 31% of params positive.
- Notes: Signal too unstable across folds. Information diffusion in crypto is too fast for daily frequency — alts catch up within hours, not days.
- Sessions: [2026-03-22 research session 66]

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

## H-004: Volatility Breakout (BTC Futures)
- Status: REJECTED
- Idea: Enter on volatility expansion beyond recent range, using ATR channel breakout. Exploit the fat tails (kurtosis 3.66).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1h
- Logic: Compute ATR(24) and 24-bar high/low channel (shifted to prior bars). Entry long: close > channel_high + 0.5×ATR. Entry short: close < channel_low - 0.5×ATR. Exit: trail stop at 1.5×ATR or mean reversion to 24-bar midpoint. Max holding period: 48 bars. Vol filter: ATR(24)/ATR(168) > 1.0.
- Result: Best params: Sharpe -0.62, annual -12.2%, max DD 31.7%, 119 trades, 40% win rate. 10 parameter sets tested, all negative.
- Notes: BTC 1h breakouts don't have enough follow-through in 2024-2026 choppy market. Win rate 33-41% with insufficient profit factor. False breakouts dominate. Tried with and without vol filter, various channel widths and trailing stops.
- Sessions: [2026-03-15 research, 2026-03-16 backtest]

## H-005: Funding Rate Arbitrage (BTC Futures)
- Status: REJECTED → superseded by H-011 (leveraged version)
- Idea: Exploit persistent funding rate imbalances on BTC perpetual futures. Short perp + long spot when funding positive. Delta-neutral.
- Instrument: futures + spot (BTC/USDT)
- Timeframe: 8h (funding settlement intervals)
- Logic: Monitor funding rate. When rolling avg funding > threshold, hold short perp + long spot to collect funding payments.
- Result: 2-year avg funding rate: 0.0059%/8h = 6.5% annualized. Best backtest: Sharpe 4.71, annual +1.7%, max DD 0.44% (rolling-27 filter). With simple threshold: Sharpe 15.96, annual +3.1%, max DD 0.20%. Funding declining: Q1 2024 22.7% → Q1 2026 1.6%.
- Notes: Strategy works perfectly (excellent Sharpe, near-zero drawdown) but **absolute returns far too low** (1.7-3.1% annual). H-010 research showed that leveraging to 5x makes this viable: +38.2% annual, 0.4% DD. Promoted to H-011.
- Sessions: [2026-03-16 backtest, 2026-03-16 paper trade]

## H-006: Adaptive Mean Reversion (BTC Futures, Long/Short)
- Status: REJECTED
- Idea: Improved mean reversion using futures (long/short) with regime filter and reversal confirmation.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1h
- Logic: BB(20,2) + RSI(14) with: (1) long AND short signals, (2) regime filter (ATR_24/ATR_168 < threshold = range-bound = trade), (3) reversal confirmation (wait for price to re-enter BB after touching). Exit at BB_middle. Stop: ATR-based.
- Result: Without reversal: best Sharpe -1.44, annual -25.2%, 56% WR. With reversal confirmation: best Sharpe -1.03, annual -13.9%, max DD 35.0%, 167 trades, 60% win rate. 12 parameter sets tested, all negative.
- Notes: Reversal confirmation improved win rate from ~50% to ~60% but still net negative. The mean reversion signal has no real edge on BTC 1h — ~49% of signals actually hit BB_middle within 48 bars. 2x ATR stop distance (1.4% of price) is too tight. Fee drag (0.2% round-trip × 167 trades) compounds the losses.
- Sessions: [2026-03-16 backtest]

## H-007: BTC/ETH Ratio Mean Reversion (Pairs Trading)
- Status: REJECTED
- Idea: Trade the BTC/ETH log ratio z-score as a market-neutral pairs strategy.
- Instrument: futures (BTC/USDT + ETH/USDT perps)
- Timeframe: 1h
- Logic: Compute rolling z-score of log(BTC/ETH). Short ratio (short BTC, long ETH) when z > entry. Long ratio when z < -entry. Exit when z reverts to ±exit_z. Stop at ±stop_z. Each leg 50% of capital (delta-neutral).
- Result: Best params: Sharpe -1.05, annual -15.0%, max DD 35.6%, 105 trades, 62% win rate. 12 parameter sets tested, all negative.
- Notes: Half-life of ratio z-score was 36.9 bars (~1.5 days), suggesting fast reversion. But the ratio has massive structural drift: ETH -44.7% vs BTC +1.8% over 2 years (ratio nearly doubled from ~18 to ~34). Even 7-day adaptive window can't handle this structural divergence. The strategy consistently bets on ratio reversion that doesn't happen because of the fundamental ETH underperformance trend.
- Sessions: [2026-03-16 backtest]

## H-013: Multi-Asset Funding Rate Arbitrage + Dynamic Allocation
- Status: REJECTED
- Idea: Diversify funding rate collection across 14 crypto assets to reduce time-out-of-market when BTC funding is negative. Also tested dynamic portfolio reallocation (shift H-011 capital to H-009/H-012 when OUT).
- Instrument: futures (14 perps: BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK, ADA, DOT, NEAR, OP, ARB, ATOM)
- Timeframe: 8h (funding settlement)
- Logic: Track 1: At each settlement, collect funding from all assets with positive rolling-27 avg. Track 2: When H-011 OUT, reallocate 60% to H-009/H-012 (50/0/50 or variants).
- Result:
  - **Multi-asset (all positive, 5x)**: Full period +25.6% ann, Sharpe 6.86 (vs BTC-only +31.6%, Sharpe 10.32)
  - **Multi-asset recent 180d**: -15.8% ann, Sharpe -4.05 (vs BTC-only +7.0%, Sharpe 3.54)
  - **Top-N rotation**: All negative due to fee drag ($4k+ fees vs $1.3k for BTC-only)
  - **Walk-forward**: Multi avg Sharpe 8.76 vs BTC-only 17.06 — BTC-only dominates
  - **Dynamic alloc (50/0/50 when OUT)**: Full Sharpe 2.65 vs static 20/60/20 Sharpe 2.77
  - **Dynamic alloc recent 180d**: Sharpe 1.42 vs static 2.14
  - **Key correlation**: All crypto funding rates correlated r=0.49 with BTC. ETH/ARB 100% positive when BTC negative but rates are low.
  - **Critical insight**: H-011 OUT acts as automatic de-risking (60% idle reduces vol). Reallocating INCREASES drawdown more than returns.
- Notes: Current 20/60/20 static allocation is self-regulating and optimal across all periods tested. Accept H-011 cyclicality. Multi-asset funding rates decline together — no diversification benefit. 14-asset funding rate data cached for future reference.
- Sessions: [2026-03-17 research session 8]

## H-014: Anti-Martingale Pyramiding (BTC Daily)
- Status: REJECTED
- Idea: Buy on N-day high breakout, add to position every N% rise (pyramid), sell all on trailing stop X% from peak. User-suggested strategy.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D (daily)
- Logic: Entry on 20-day high breakout with 10-20% capital. Add 10-20% more every 3-10% rise. Trail stop at 8-15% from peak. Exit everything on stop. Cooldown 5 bars. Long-only or long+short.
- Result:
  - **In-sample**: 88% params positive Sharpe (144 tested). Best Sharpe 0.69, +16.4% ann, 23.1% DD.
  - **Fixed-split OOS (30%)**: All top 5 params negative. Best OOS Sharpe -1.31. Mean -1.85.
  - **Rolling walk-forward (12mo/3mo)**: 1/4 folds positive. Mean OOS Sharpe -1.12.
  - **Long+short mode**: Worse than long-only (shorts hurt in crypto).
  - **Multi-asset**: Very inconsistent. XRP +101% (overfit), SOL -12%, ETH -8.6%.
  - **Correlation with H-009**: 0.424 — moderately correlated (both BTC trend followers).
- Notes: Fundamentally just another trend-following strategy with fancy position sizing. Doesn't survive walk-forward validation — works in strong trending periods but loses in chop. Too correlated with H-009 to provide diversification. Rejected.
- Sessions: [2026-03-17 research session 14]

## H-015: Daily RSI Mean Reversion (BTC Futures)
- Status: REJECTED
- Idea: Long when RSI oversold, short when overbought. Contra-trend strategy to diversify against H-009.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D (daily)
- Logic: RSI(7-21). Long when RSI < 20-40, short when RSI > 60-80. Exit at RSI 40-55. Full allocation.
- Result:
  - **In-sample**: 67% positive Sharpe (120 tested). Best Sharpe 0.97.
  - **Fixed-split OOS**: All top 10 negative except one. Mean OOS Sharpe -0.43.
  - **Rolling walk-forward**: 0/4 folds positive. Mean OOS Sharpe -0.65.
  - **Correlation with H-009**: -0.569 IS, -0.732 OOS — strongly negatively correlated.
  - **Portfolio (H-009+H-015)**: Sharpe improves 0.28→0.34 but negative alpha drags returns.
- Notes: Excellent negative correlation with H-009, but the signal itself has no edge OOS. Combining it reduces DD (19.9%→6.9%) but barely improves Sharpe. Mean reversion on daily BTC doesn't work — confirmed again after H-002/H-006.
- Sessions: [2026-03-17 research session 14]

## H-016: BB Squeeze Breakout (BTC Daily)
- Status: REJECTED
- Idea: Trade Bollinger Band breakouts only after a vol squeeze (bandwidth below 10-30th percentile).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Logic: Detect squeeze (BB bandwidth < N-th percentile of 100-bar history). Trade breakout above/below band. Hold for fixed N bars.
- Result: Only 36% params positive (81 tested). Best Sharpe 1.45 but only 18 trades in 2 years — clear overfit. Mean Sharpe -0.28.
- Notes: Too few signal events on daily timeframe. The high-Sharpe results are artifacts of tiny sample size. Not worth pursuing.
- Sessions: [2026-03-17 research session 14]

## H-017: Multi-Timeframe Momentum Filter (BTC)
- Status: REJECTED
- Idea: Only trade when weekly and daily EMA trends agree. Weekly filters out noise.
- Instrument: futures (BTC/USDT perp)
- Timeframe: Weekly + Daily
- Logic: Weekly EMA(4/12) for trend direction, daily EMA(5-10/20-40) for entry. Only trade when both agree.
- Result: Best Sharpe 0.29, terrible DD (44-51%). Correlation with H-009: 0.892 — essentially redundant.
- Notes: Adding a weekly filter just makes H-009 worse by delaying entries. The weekly EMA signal is too slow for crypto. Redundant with existing strategy.
- Sessions: [2026-03-17 research session 14]

## H-018: Short-Term Reversal (Cross-Sectional, 14 Assets)
- Status: REJECTED
- Idea: Buy recent losers, sell recent winners (1-10 day lookback). Opposite of momentum. Academic short-term reversal factor.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 1-5 days)
- Logic: Rank assets by NEGATIVE of past N-day returns (losers ranked high). Long top quartile, short bottom quartile.
- Result:
  - **72 param sets tested** (lookback 1-10d, rebal 1-5d, N 3-5)
  - **Only 4% positive Sharpe** (3/72)
  - **Best Sharpe: 0.06** — essentially zero edge
  - **Mean Sharpe: -0.71**
- Notes: Crypto momentum dominates at ALL timeframes. Short-term reversal (buying losers) is a losing strategy. Losers keep losing, winners keep winning. This confirms H-012 (momentum) is the right cross-sectional signal. Reversal only works in equities due to institutional rebalancing — absent in crypto.
- Sessions: [2026-03-18 research session 24]

## H-019: Low-Volatility Anomaly (Cross-Sectional, 14 Assets)
- Status: LIVE (paper trade since 2026-03-18)
- Idea: Long low-vol assets, short high-vol assets. Classic cross-sectional factor (low-vol earns risk-adjusted excess returns).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 21 days)
- Logic: Rank assets by NEGATIVE of realized volatility (20d window, low vol ranks high). Long top 3, short bottom 3. Rebalance every 21 days using lagged ranking.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). WF: 8 folds x 80d test = 640 total OOS days.
- Result:
  - **In-sample (full, standard vol V20_R21_N3)**: Sharpe 1.17, +57.8% annual, 47.9% DD
  - **Parameter robustness (standard vol)**: 89% positive (124/140). Mean Sharpe 0.52.
  - **Parameter robustness (downside vol)**: 99% positive (138/140). Mean Sharpe 0.92.
  - **Fee sensitivity**: Sharpe 0.75 at 5x fees (very robust, low turnover).
  - **Walk-forward (8 folds, 80d, standard vol)**: 5/8 positive, mean OOS Sharpe 0.76, median 0.60
  - **Walk-forward (8 folds, 80d, downside vol)**: 7/8 positive, mean OOS Sharpe ~2.24
  - **Adaptive WF (param opt per fold)**: 4/6 positive, mean OOS Sharpe 1.58
  - **Actual H-009 correlation**: -0.094 (slightly negative — corrected from -0.268 BTC proxy)
  - **H-012 correlation**: 0.076 (standard vol), 0.223 (downside vol)
  - **Failing WF folds**: Strong BTC uptrends (avg BTC +31.8% in fails vs -10.1% in passes)
  - **Regime filter**: None improves WF over baseline
  - **Combined factor (LV+Mom)**: 30/70 blend WF mean 1.57 but overlaps with H-012
  - **4-strategy portfolio (15/50/15/20, actual H-009)**: Sharpe 1.75, +23.8%, 14.0% DD (vs 3-strat 1.38)
- Notes: Standard vol variant preferred over downside vol for portfolio use — lower correlation with H-012 (0.076 vs 0.223) and more negative correlation with H-009 (-0.094 vs -0.020), giving better portfolio improvement (Sharpe +0.37 vs +0.01). Main risk: underperforms during strong BTC uptrends. The 48% standalone DD is acceptable in a diversified portfolio (portfolio DD 14%). Critical correction: previous 3-strat Sharpe was 2.78 using BTC proxy for H-009; actual H-009 equity gives 1.38. H-019 brings it to 1.75 — meeting the ≥1.5 target. Paper trade deployed 2026-03-18: LONG ATOM/ARB/XRP (low vol), SHORT DOGE/DOT/NEAR (high vol). Next rebal 2026-04-08.
- Sessions: [2026-03-18 research session 24, 2026-03-18 research session 25, 2026-03-18 paper trade session 26]

## H-020: Funding Rate Dispersion (Cross-Sectional Carry)
- Status: REJECTED
- Idea: Cross-sectional carry trade — long assets with highest funding rates, short lowest. Exploit positioning imbalances.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 1-14 days)
- Logic: Rank assets by rolling average funding rate (7-60 day window). Long top quartile (highest funding), short bottom quartile.
- Result:
  - **50 param sets tested**
  - **0% positive Sharpe** (0/50)
  - **Best Sharpe: -0.06** — no edge whatsoever
  - **Mean Sharpe: -0.63**
- Notes: Complete failure. Crypto funding rates are too correlated across assets (r=0.49 with BTC, confirmed by H-013 analysis). High-funding assets don't outperform relative to low-funding. Cross-sectional carry doesn't work because all assets enter positive/negative funding regimes together. This also confirms H-013's finding that multi-asset funding diversification is futile.
- Sessions: [2026-03-18 research session 24]

## H-021: Volume Momentum Factor (Cross-Sectional, 14 Assets)
- Status: LIVE (paper trade since 2026-03-18)
- Idea: Long assets with highest short-term volume growth relative to long-term average, short lowest. Volume expansion precedes price moves.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3 days)
- Logic: Compute ratio of 5-day avg volume to 20-day avg volume for each asset. Rank. Long top 4 (highest volume surge), short bottom 4. Rebalance every 3 days using lagged ranking.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). 1409 IS trades over 2.0yr. WF: 6 folds x 80d test = 480 total OOS days (180d train).
- Result:
  - **In-sample (VS5_VL20_R3_N4)**: Sharpe 1.52, +63.3% annual, 24.7% DD, 1409 trades
  - **Parameter robustness**: 90% positive (162/180). Mean Sharpe 0.73.
  - **Walk-forward (6 folds, 180d/80d)**: **6/6 positive** (perfect!), mean OOS Sharpe **1.83**, median 1.55
  - **WF folds**: 0.45, 3.26, 3.01, 1.24, 1.86, 1.17 — all positive
  - **Fee sensitivity**: Sharpe 1.63→1.41→1.19→0.76 at 1x→2x→3x→5x fees
  - **Correlation with H-009**: -0.068 (near zero)
  - **Correlation with H-012**: 0.057 (near zero)
  - **Correlation with H-019**: -0.032 (near zero)
  - **Regime analysis**: BTC UP Sharpe 3.67, FLAT 0.92, DOWN 0.18 — works in all regimes
  - **5-strat portfolio (10/40/10/15/25)**: Sharpe 2.10, +31.6%, 12.9% DD
- Notes: **Best WF performance of any strategy tested** (6/6, mean 1.83). Key caveat: ONLY works at high-frequency rebalance (3-day). Low-frequency versions (14-21 day) FAIL WF badly (2/6). This means high turnover (1409 trades) — fee management critical. Must use maker orders. Alternative: VS7_VL20_R3_N4 (IS 1.81, WF 5/6 mean 1.77) also strong. Volume z-score variant (IS 1.91) fails WF. Volume data quality is clean (no zeros, CV 0.43-0.65). Paper trade deployed 2026-03-18: LONG DOT/LINK/XRP/DOGE (vol surge), SHORT ARB/SUI/NEAR/ATOM (vol drop). Next rebal 2026-03-21.
- Sessions: [2026-03-18 research session 28, 2026-03-18 paper trade session 29]

## H-022: Amihud Illiquidity Premium (Cross-Sectional, 14 Assets)
- Status: REJECTED
- Idea: Long illiquid assets (high |return|/volume ratio), short liquid assets. Academic illiquidity premium.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5-21 days)
- Logic: Compute Amihud illiquidity measure: avg(|daily return| / dollar volume) over 10-60 day window. Rank. Long top quartile (illiquid), short bottom quartile.
- Result:
  - **48 param sets tested**
  - **0% positive Sharpe** (0/48)
  - **Best Sharpe: -1.15** — no edge whatsoever
  - **Mean Sharpe: -1.40**
- Notes: Complete failure. Illiquidity premium doesn't exist in crypto. Illiquid assets (small-cap alts) consistently underperform liquid ones. The academic illiquidity premium relies on institutional constraints absent in crypto markets. Longing illiquid crypto = catching falling knives.
- Sessions: [2026-03-18 research session 28]

## H-023: Price-Volume Confirmation (Cross-Sectional, 14 Assets)
- Status: REJECTED
- Idea: Long assets with momentum + volume confirmation (both positive), short assets with momentum but declining volume (exhaustion). Smart money signal.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5-21 days)
- Logic: Ranking = momentum(N-day) * volume_change(M-day). Both dimensions must agree for strong signal.
- Result:
  - **96 param sets tested**
  - **93% positive Sharpe** (89/96). Mean 0.62, best 1.53.
  - **Walk-forward (M60_V20_R5_N3)**: 5/6 positive, mean OOS Sharpe 1.00
  - **Fee sensitivity**: Sharpe 1.27 at 5x fees (excellent)
  - **BUT: Correlation with H-012 = 0.864** — essentially redundant with momentum
- Notes: Strong factor on its own, but is just momentum with a volume multiplier. At 60d momentum lookback, it's nearly identical to H-012 (r=0.864). No portfolio diversification value. Would only be useful as a REPLACEMENT for H-012, not an addition. H-012 is simpler and already deployed — no reason to switch.
- Sessions: [2026-03-18 research session 28]

## H-024: Low-Beta Anomaly (Cross-Sectional, 14 Assets)
- Status: KILLED (2026-03-31, session 114) — H-019 won comparison +7.44% vs -0.20% (7.64% gap over 13 days)
- Idea: Long low-beta assets (less sensitive to BTC), short high-beta assets. Rolling 60-day beta vs BTC as market proxy.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 21 days)
- Logic: Compute rolling 60-day beta of each asset vs BTC returns. Rank. Long top 3 lowest-beta, short bottom 3 highest-beta. Rebalance every 21 days using lagged ranking.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). 105 IS trades over ~1.8yr. WF: 6 folds x 80d test = 480 total OOS days (360d train).
- Result:
  - **In-sample (W60_R21_N3)**: Sharpe 1.56, +90.1% annual, 49.2% DD, 105 trades
  - **Parameter robustness**: 100% positive (48/48). Mean Sharpe 1.08.
  - **Walk-forward (6 folds, 360d/80d)**: **5/6 positive**, mean OOS Sharpe **2.12**, median 1.36
  - **WF folds**: 4.78, 1.47, -0.60, 1.25, 0.86, 4.95
  - **Fee sensitivity**: Sharpe 1.56→1.54→1.52→1.48 at 1x→2x→3x→5x fees (extremely robust — only 105 trades)
  - **Head-to-head vs H-019 (vol)**: Beta wins 12/12 at matched params (100%)
  - **Correlation with H-009**: -0.027 (near zero)
  - **Correlation with H-012**: 0.319 (moderate)
  - **Correlation with H-019**: 0.660 (high — related factors)
  - **Correlation with H-021**: 0.069 (near zero)
  - **Portfolio (replacing H-019)**: Sharpe 1.80 → **2.33** (+0.53 improvement)
  - **6-strat (both H-019 + H-024)**: Sharpe 1.96 (worse than replacement — correlated)
  - **Multiple WF configs**: W60_R14_N4 (5/6, mean 1.72), W30_R14_N3 (5/6, mean 1.70)
  - **Idiosyncratic vol variant**: Only 67% positive, corr 0.808 with H-019, not useful
- Notes: **Strongest factor discovery since H-021.** Beta captures systematic risk (sensitivity to BTC), while H-019 captures total risk (including idiosyncratic). Beta is strictly better: higher IS Sharpe, better WF, more fee-robust, and bigger portfolio improvement. Should replace H-019 after parallel paper trade validation. Deployed 2026-03-18: LONG ATOM/OP/BTC (low beta), SHORT XRP/NEAR/SUI (high beta).
- Sessions: [2026-03-18 research session 30]

## H-025: Skewness Factor (Cross-Sectional, 14 Assets)
- Status: REJECTED
- Idea: Long negative-skew assets (underpriced risk), short positive-skew assets (overpriced lottery tickets).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5-21 days)
- Logic: Compute rolling skewness of returns (20-90 day window). Rank by NEGATIVE skewness. Long top quartile, short bottom quartile.
- Result:
  - **48 param sets tested**
  - **Only 15% positive Sharpe** (7/48)
  - **Best Sharpe: 0.49** — weak edge
  - **Mean Sharpe: -0.51**
- Notes: The skewness premium (buying assets with negatively skewed returns, avoiding lottery-like payoffs) doesn't exist in crypto. Crypto asset return distributions are too similar across the universe for cross-sectional differentiation. Only 30d window showed any signal (7 positive), and even those were marginal. The academic skewness premium relies on retail investor preferences absent in crypto.
- Sessions: [2026-03-18 research session 30]

## H-026: Drawdown Distance Factor (Cross-Sectional, 14 Assets)
- Status: REJECTED
- Idea: Long assets near their rolling highs, short assets deep in drawdown. Continuation signal.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5-21 days)
- Logic: Compute close/rolling_max(N-day) for each asset. Rank (closer to peak = higher rank). Long top quartile, short bottom quartile.
- Result:
  - **60 param sets tested**
  - **97% positive Sharpe** (58/60). Mean 0.79, best 1.54.
  - **Walk-forward (W90_R5_N5)**: 3/6 positive, mean OOS Sharpe 1.40, median 0.90
  - **BUT: Correlation with H-012 = 0.682** — essentially momentum in disguise
  - **Correlation with H-019**: 0.353 (moderate)
- Notes: Very strong standalone factor (97% positive) but is fundamentally just another way to measure momentum. Assets near their rolling highs = recent winners = exactly what H-012 captures. The 0.682 correlation confirms this. Walk-forward only 3/6 positive vs H-012's 5/6 — so it's also a weaker version of momentum. No portfolio value.
- Sessions: [2026-03-18 research session 30]

## H-027: Lead-Lag Cross-Sectional Factor (14 Assets, 1h)
- Status: REJECTED
- Idea: BTC moves first, altcoins follow. Long altcoins that haven't responded to BTC's recent move, short over-responders.
- Instrument: futures (14 perps)
- Timeframe: 1h (rebalance every 1-5 days)
- Logic: Compute BTC return over past N hours (4-24h). For each altcoin, compute lag score = BTC_return - altcoin_return. Rank. Long top N, short bottom N.
- Result:
  - **75 param sets tested** (lookback 4-24h, rebal 1-5d, N 3-5)
  - **Only 1% positive Sharpe** (1/75)
  - **Best Sharpe: 0.014** — essentially zero edge
  - **Mean Sharpe: -2.605**
  - **Walk-forward**: Best 3/6 positive, mean OOS 0.378. FAIL.
- Notes: The BTC-altcoin lead-lag effect either doesn't exist at hourly timescales or is already arbitraged away. Short lookbacks (4h, 8h) catastrophic — pure fee drag into noise. The relationship may exist at minute-level but not capturable with hourly bars.
- Sessions: [2026-03-18 review+research session 31]

## H-028: Volume Trend Change Factor (OI Proxy, 14 Assets, 1h)
- Status: REJECTED
- Idea: Assets with accelerating volume (short MA / long MA ratio) attract capital → continuation signal.
- Instrument: futures (14 perps)
- Timeframe: 1h (rebalance every 24-72h)
- Logic: Compute ratio of short-window avg volume to long-window avg volume. Rank. Long top N (volume accelerating), short bottom N.
- Result:
  - **204 param sets tested**
  - **Only 6% positive Sharpe** (12/204)
  - **Best Sharpe: 0.774** (VS6_VL48_R72_N5, 22.1% ann, 24.3% DD) — but narrow params
  - **Mean Sharpe: -1.143**
  - **Walk-forward**: All tested sets FAIL. Best 3/6, mean -0.195.
  - **Fee sensitivity**: Negative at 3x fees.
- Notes: Volume trend as OI proxy has no reliable cross-sectional signal. The few IS-positive results are narrow parameter overfitting. Actual OI data might behave differently but wasn't available in cache.
- Sessions: [2026-03-18 review+research session 31]

## H-029: Hourly Cross-Sectional Momentum (14 Assets, 1h)
- Status: REJECTED
- Idea: Higher-frequency cross-sectional momentum using 1h bars. Potentially different alpha from daily H-012.
- Instrument: futures (14 perps)
- Timeframe: 1h (rebalance every 4-48h)
- Logic: Rank assets by past 24h-336h returns using 1h bars. Long top N, short bottom N.
- Result:
  - **90 param sets tested** (lookback 24-336h, rebal 4-48h, N 3-5)
  - **16% positive Sharpe** (14/90)
  - **336h (14-day) lookback ONLY works**: 93% sub-params positive. All shorter lookbacks 0%.
  - **Walk-forward (336h)**: LB336_R48_N3: **5/6 positive, mean OOS 1.001** — PASS
  - **Fee sensitivity**: Sharpe 0.807 at 3x fees — PASS
  - **BUT: Correlation with H-012 = 0.484** — FAIL (threshold <0.4)
  - **Cross-sectional rank corr with H-012**: 0.415
- Notes: The 336h lookback that works is essentially 14-day momentum — a noisier, shorter version of H-012's 60-day momentum. Not an independent alpha source. Shorter hourly lookbacks (24-168h) that would be truly differentiated all fail. No unique hourly momentum alpha exists.
- Sessions: [2026-03-18 review+research session 31]

## H-030: Composite Multi-Factor (Momentum + Volume Momentum + Beta)
- Status: CONFIRMED (standalone) — not added to portfolio (individual strategies combined are better)
- Idea: Combine confirmed cross-sectional factors (momentum, volume momentum, beta) into a single composite z-score ranking. Test 2/3/4-factor blends.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3 days)
- Logic: Z-score normalize each factor cross-sectionally, then weighted average. Best: Mom=0.33/Vol=0.33/Beta=0.34, R3_N5.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr)
- Result:
  - **In-sample (3-factor best)**: Sharpe 2.05, +101.7% annual, 24.9% DD
  - **In-sample (4-factor best)**: Sharpe 2.14, +106.6% annual, 25.1% DD
  - **Parameter robustness**: 135/135 positive (3-factor), 243/243 positive (4-factor) — 100%
  - **Walk-forward (3-factor, 6 folds, 360d train / 80d test)**: 5/6 positive, mean OOS Sharpe 1.71 (480 total OOS days)
  - **Walk-forward (4-factor, 6 folds)**: 5/6 positive, mean OOS Sharpe 2.01
  - **Fee sensitivity**: Sharpe 1.52-1.55 at 5x fees (robust)
  - **Param neighborhood**: 36/36 positive (100%), min 1.09
  - **Portfolio note**: Portfolio of 3 individual strategies (Sharpe 2.26) > single composite (Sharpe 2.14)
  - **Correlations**: 0.61 with H-012, 0.44 with H-021, 0.57 with H-024
- Notes: Excellent standalone strategy (Sharpe 2.05, 100%+ annual, 25% DD, passes WF 5/6). Not added to current portfolio because running individual factors separately preserves diversification from different rebalance schedules (3d/5d/21d). Could be deployed as a simpler alternative to running 3 separate cross-sectional strategies. High-frequency rebal (3-day) means higher turnover — use maker orders.
- Sessions: [2026-03-19 review+research session 32, 2026-03-19 review+system session 33]

## H-031: Size Factor (Dollar Volume Proxy, Long Large)
- Status: LIVE (paper trade since 2026-03-19) — independent, not in main portfolio (corr 0.49 with momentum)
- Idea: Long assets with highest average dollar volume (large-cap proxy), short lowest. Size effect in crypto.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5 days)
- Logic: Compute 30-day rolling average dollar volume (close * volume). Rank. Long top 5 (largest), short bottom 5.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). ~94 IS trades over 1.9yr.
- Result:
  - **In-sample (W30_R5_N5)**: Sharpe 1.58, +78.5% annual, 31.3% DD, ~94 trades
  - **Parameter robustness (long_large)**: 48/48 positive (100%)
  - **Parameter robustness (long_small)**: 0/48 positive (0%)
  - **Walk-forward (W30_R5_N5, 4 folds, 360d train / 80d test)**: 4/4 positive, mean OOS Sharpe 1.47 (320 total OOS days)
  - **Walk-forward (W30_R5_N4)**: 4/4 positive, mean OOS Sharpe 1.78
  - **Fee sensitivity**: Sharpe 1.54 at 5x fees (extremely robust — low turnover)
  - **Typical positions**: LONG BTC/ETH/SOL/XRP/DOGE, SHORT NEAR/DOT/OP/ARB/ATOM
  - **Portfolio note**: Corr with H-012 (momentum) = 0.486, with H-019 (low-vol) = 0.461
  - **Adding to 4-factor composite DECREASES Sharpe**: 2.14 → 1.82-1.97
- Notes: Genuine size effect in crypto — large-cap consistently outperforms small-cap (100% positive, 4/4 WF, extremely fee-robust). Correlated with momentum/low-vol so doesn't diversify the current portfolio, but excellent standalone: +78.5% annual, 31.3% DD, Sharpe 1.58. Very low turnover makes this practical. Could be deployed independently or as a replacement for momentum if H-012 underperforms in paper trade.
- Sessions: [2026-03-19 review+research session 32, 2026-03-19 review+system session 33]

## H-032: Pairwise Cointegration Statistical Arbitrage
- Status: LIVE (paper trade since 2026-03-19) — independent, experimental (OOS evidence mixed)
- Idea: Test all 91 crypto pairs for cointegration, trade mean-reverting spreads using z-score entry/exit. Fundamentally different from cross-sectional factor approaches.
- Instrument: futures (14 perps, pairwise)
- Timeframe: 1D (daily, trades last 20-40 days)
- Logic: Engle-Granger cointegration test on log prices. Compute log-spread = log(A) - HR*log(B) where HR = OLS hedge ratio. Rolling z-score of spread. Long spread when z < -entry_z, short when z > +entry_z. Exit at +-exit_z. Stop at +-stop_z.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). 91 pairs tested. 2160 param sets across 12 candidate pairs.
- Result:
  - **Cointegration**: Only 3/91 pairs strictly cointegrated (p<0.05): DOT/ATOM (p=0.031), DOGE/LINK (p=0.027), LINK/ADA (p=0.045). 12 pairs at relaxed p<0.20.
  - **Cointegration stability**: Poor — most pairs significant in <30% of rolling 180d windows. DOT/ATOM 26%, NEAR/OP 37%, SOL/DOGE 32%.
  - **In-sample (best params)**: DOT/ATOM Sharpe 1.30 (+29.4%, 21.1% DD, 35 trades). SOL/DOGE 1.23. AVAX/DOT 0.96. 50% of 2160 param sets positive.
  - **Fee robustness (3x)**: 10/12 pairs pass. DOT/ATOM 1.30->0.67. SOL/DOGE 1.23->0.68.
  - **Walk-forward (5 folds x 120d)**: 5/12 pairs pass (>=3/4 positive). DOGE/LINK 4/4 (mean 1.49). DOT/OP 3/4 (mean 1.69). DOGE/ADA 3/4 (mean 0.70).
  - **50/50 train/test split**: 5/12 pass. DOGE/LINK test Sharpe 0.75. DOGE/ADA 0.61. DOT/ATOM 0.36.
  - **Both OOS tests passed**: Only 2 pairs (DOGE/LINK, DOGE/ADA).
  - **Multi-pair portfolio (8 pairs, IS)**: Sharpe 1.30, Ann +12.7%, DD 7.4%.
  - **Multi-pair portfolio (8 pairs, OOS)**: Sharpe 1.33, Ann +9.5%, DD 5.8%.
  - **Non-overlapping 3-pair portfolio (OOS)**: Sharpe 0.62, Ann +7.2%, DD 13.0%.
  - **Correlation with H-012**: -0.31 (NEGATIVE — excellent diversifier)
  - **Regime analysis**: BTC UP Sharpe 1.20, FLAT 1.84, DOWN 2.36 — performs best in downtrends
- Notes: Fundamentally different alpha source from cross-sectional factors. Negative correlation with momentum (-0.31) makes it an excellent diversifier. However, OOS evidence is mixed: only 2/12 pairs pass both walk-forward AND train/test split. The core issue is cointegration instability — crypto pairs drift in and out of cointegrated relationships over months. With half-lives of 20-40d and entry thresholds of 1-2.5 sigma, each pair generates only 8-35 trades over 2 years, making OOS validation statistically weak. The 8-pair portfolio OOS Sharpe of 1.33 is promising but relies on diversification across many marginal signals. Could be deployed as a low-allocation diversifier (~5-10% of portfolio) but not as a core strategy. Key advantage: works in all BTC regimes and is negatively correlated with everything else.
- Sessions: [2026-03-19 research session 34]

## H-033: Idiosyncratic Momentum (Alpha Momentum)
- Status: REJECTED
- Idea: Decompose each asset's return into market component (beta * BTC_return) + idiosyncratic residual. Rank on cumulative residual momentum. Assets with positive alpha continue outperforming.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3-14 days)
- Logic: For each asset, compute rolling beta vs BTC (30-90d). Residual return = actual - beta*BTC_return. Rank on sum of residual returns over past 10-60 days. Long top N, short bottom N.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). 144 param sets tested.
- Result:
  - **In-sample**: 99% positive (142/144). Mean Sharpe 0.77. Best B90_M60_R5_N3: Sharpe 1.56, +90.6% ann, 26.4% DD.
  - **Walk-forward (4 folds, 360d/80d)**: 1/4 positive. Mean OOS Sharpe -0.16. **FAILS.**
  - **Correlation with H-012**: 0.832 — essentially redundant with raw momentum.
  - **Correlation with H-009**: 0.000 (orthogonal).
  - **Fee sensitivity**: Robust (1.32 at 5x fees).
- Notes: Stripping out the market (BTC) component doesn't create an independent signal. The residual momentum is still capturing the same cross-sectional patterns as raw momentum because altcoin relative performance is what drives both. Walk-forward failure confirms overfitting. The high IS positive rate (99%) is misleading.
- Sessions: [2026-03-19 research session 37]

## H-034: Funding Rate as BTC Timing Signal
- Status: REJECTED
- Idea: Use extreme funding rate levels as a contrarian predictor of BTC returns. High funding = crowded longs = short. Low funding = oversold = long.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Logic: Compute rolling avg funding rate (3-45 day window). Long BTC when funding below expanding N-th percentile (oversold). Short when above P-th percentile (crowded). Hysteresis (stay in position).
- Data: BTC, 730 daily bars + 2190 funding rate records. 100 param sets tested.
- Result:
  - **In-sample**: 49% positive (49/100) — essentially random.
  - **Best**: F45_L10_S80: Sharpe 0.54, +14.8% ann, 39.9% DD — but only 5 trades.
  - **Walk-forward**: 2/6 positive, mean 0.33.
  - **Correlation with H-009**: -0.175.
- Notes: No edge. 49% positive = noise. The few positive results have tiny sample sizes (5 trades). Funding rate level does not predict BTC price direction reliably. This confirms that funding rates reflect positioning but don't have predictive power for directional moves.
- Sessions: [2026-03-19 research session 37]

## H-035: Momentum with Volatility Timing
- Status: REJECTED (as standalone — logged as potential H-012 enhancement)
- Idea: Scale H-012 momentum exposure based on recent portfolio volatility. When realized vol is high, reduce exposure. When low, increase.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Standard H-012 momentum ranking (60d). Multiply weights by min(vol_target / realized_vol_N_day, 2.0). Vol targets 0.3-1.0, windows 10-60d.
- Data: 14 assets, 734 daily bars. 144 param sets tested.
- Result:
  - **In-sample**: 100% positive (144/144). 21% beat base H-012 (Sharpe 1.12).
  - **Best**: VT0.3_VW10_R5_N4: Sharpe 1.61, +68.3% ann, 21.3% DD (vs base 30.6% DD).
  - **Walk-forward**: 3/4 positive, mean 0.76 (weaker than base H-012's 5/6).
- Notes: Not a new strategy — just an enhancement that reduces drawdown by scaling down during high-vol periods. Walk-forward weaker than base H-012 (3/4 vs 5/6). Could be applied as a refinement to H-012 if drawdown is a concern, but not worth deploying as a separate paper trade.
- Sessions: [2026-03-19 research session 37]

## H-036: Intraday Hour-of-Day Seasonality (BTC)
- Status: REJECTED
- Idea: Test if BTC returns vary systematically by hour of day. If persistent, trade best/worst hours.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1h
- Logic: Compute average return per hour of day using expanding window. Long during best N hours, flat (or short) during worst N hours.
- Data: BTC, 17,610 hourly bars (~2yr).
- Result:
  - **Patterns are real**: Train/test correlation of hourly returns = 0.439. Cross-asset corr = 0.625.
  - **Best hours**: 22:00 (Sharpe 9.75), 21:00 (8.85), 09:00 (5.39).
  - **Worst hours**: 23:00 (-9.74), 19:00 (-4.90), 13:00 (-3.20).
  - **Strategy performance**: Best Sharpe 0.30 (BEST4), +1.1% ann, 17.4% DD. Long/short: Sharpe 0.17.
- Notes: Persistent intraday patterns exist in crypto but the absolute return per hour is tiny (~0.05% per best hour). Transaction costs make any hourly trading unprofitable. The patterns are likely driven by timezone-based trading activity (Asian session 21-02 UTC shows accumulation, European/US session shows distribution). Interesting for understanding market microstructure but not actionable.
- Sessions: [2026-03-19 research session 37]

## H-037: Polymarket 1hr BTC UP/DOWN + Intraday Seasonality
- Status: CONFIRMED (paper trade — Polymarket only, no Bybit)
- Idea: Combine H-036's statistically proven hour-of-day BTC direction bias with Polymarket's 1hr BTC UP/DOWN binary markets. The patterns failed on Bybit (fees kill tiny returns) but Polymarket has a different cost structure (prediction market spread, not exchange fees).
- Instrument: Polymarket binary prediction markets (NOT Bybit)
- Timeframe: 1h
- Logic: Bet on the direction of BTC's next 1-hour candle during hours with statistically significant (p < 0.05) directional bias. Top 5 hours: 17:00 UTC (UP, 56.3%), 21:00 UTC (UP, 54.9%), 22:00 UTC (UP, 54.0%), 23:00 UTC (DOWN, 54.1%), 13:00 UTC (DOWN, 53.8%).
- Data: BTC, 17,611 hourly bars (~2yr). Train/test green probability correlation: 0.522. All 5 target hours show consistent direction in both train and test halves.
- Result:
  - **Green/red probability per hour**: Statistically significant bias at 5 hours (p < 0.05). 17:00 UTC strongest at 56.3% green.
  - **Train/test consistency**: All 5 target hours consistent across halves.
  - **Rolling stability (6mo window)**: Green hours (17/21/22) always > 50% (min 52.0%). Red hours (23/13/00) always < 50%.
  - **OOS simulation (top 5 hours)**: 1,835 bets, 53.7% win rate, 10/13 months profitable, +$586 on $10 bets. ~$0.32/bet.
  - **EV at 50c**: +$0.032-$0.058 per $1 bet depending on hour.
  - **EV at 52c**: Most hours still +EV at 52c entry price, but edge halved.
  - **CRITICAL CAVEAT**: Edge only exists if Polymarket prices at ~50c. If market already prices in seasonality (e.g., 17:00 UP at 55c), edge vanishes.
- Notes: This is a creative cross-platform arbitrage idea from the user. No historical Polymarket data exists to verify pricing inefficiency — must paper trade to find out. The statistical patterns are robust (0.52 train/test corr, consistent across rolling windows). Key unknown: does Polymarket market price in the hour-of-day bias? Paper trade involves monitoring actual Polymarket prices at target hours and comparing to historical probabilities.
- Sessions: [2026-03-19 review+research session 38]

## H-038: ML Factor Combination (Ridge Regression)
- Status: CONFIRMED (standalone, weak) — **NOT for portfolio deployment**
- Idea: Use ML (Ridge regression) to learn optimal non-linear combination of cross-sectional factor signals (momentum, volume momentum, beta, volatility, size, reversal) for predicting next-period returns.
- Instrument: futures (14-asset universe)
- Timeframe: daily (5d rebalance)
- Logic: Compute 7 factor z-scores per asset per day. Train Ridge regression on cross-sectional demeaned forward 5d returns. Walk-forward (365d train, 90d test). Long top-5, short bottom-5 by predicted score.
- Data: 14 assets, 734 daily bars (~2yr). 659 usable dates after warmup. 9,226 observation-rows.
- Result:
  - **Best config**: Ridge alpha=100, zscore features, R5, N5
  - **OOS (walk-forward)**: Sharpe 1.43, +26.2% annual, 9.6% DD
  - **Folds**: 2/3 positive (67%) — fold 0 negative at -0.41
  - **Fee robust**: 1.43 → 0.97 at 5x fees
  - **Param robustness (Ridge)**: 96% positive Sharpe (104/108 configs)
  - **RF/GB**: 100% and 97% positive, but lower best Sharpe (1.14, 1.19) — linear combo sufficient
  - **Correlation**: H-012 0.295, H-021 0.197, H-019 0.232, H-024 0.274
  - **Portfolio impact**: 3-strat XS Sharpe 1.54 → 1.68 (+9%) when added
  - **Train window sensitivity**: CRITICAL — 180d: -0.10, 270d: -0.17, **365d: 1.43**, 450d: 0.46
- Notes:
  - Train window sensitivity is a major red flag — model only works with ~365d window.
  - Feature importance: beta (most stable, 8.34 stability), reversal (11.12), momentum, volume momentum. Reversal contributes in combination despite failing standalone (H-018).
  - Linear model (Ridge) beats tree-based (RF, GB) — factor combination is approximately linear.
  - With only 3 OOS folds (limited by 2yr data), statistical confidence is low.
  - Revisit when more data accumulates (4+ folds for better validation).
  - 38 hypotheses tested total.
- Sessions: [2026-03-19 review+research session 39]

## H-039: Day-of-Week Seasonality (Long Wednesday / Short Thursday)
- Status: LIVE (paper trade since 2026-03-19) — independent
- Idea: Fixed calendar seasonality — crypto markets systematically go up on Wednesdays and down on Thursdays. Long BTC at Tue close, flip short at Wed close, close at Thu close, flat rest of week.
- Instrument: futures (BTC/USDT perp, also works on all 14 assets)
- Timeframe: 1D (daily close, trades 2 days/week)
- Logic: Position based on day of week only. No parameters to optimize. Long Wednesday return, short Thursday return.
- Data: 14 assets, 734 daily bars (~2yr). 105 observations per DOW per asset. BTC alone: 105 Wed, 105 Thu.
- Result:
  - **BTC full period**: Sharpe 1.55, +44.8% annual, -32.7% DD
  - **BTC Walk-Forward (fixed Wed/Thu, 6 folds)**: **6/6 positive** (mean OOS Sharpe **2.46**)
    - Fold 1: 1.92, Fold 2: 1.64, Fold 3: 1.78, Fold 4: 2.78, Fold 5: 3.87, Fold 6: 2.79
  - **EW All-Asset (14)**: Sharpe 1.44, +60.1% annual, -24.2% DD. WF **6/6** (mean 1.99)
  - **Per-asset**: ALL 14 positive IS Sharpe (0.85–1.78). BTC/ETH/DOGE WF 6/6
  - **Quarterly consistency**: Wed > Thu in 7/9 quarters (78%). Rolling 6-month: 89%
  - **ANOVA**: F=12.4 (p<0.0001). Wed mean +0.50%, Thu mean -0.65% (all assets)
  - **Fee robust**: Sharpe 1.07 at 5 bps/side (maker). Dies at 20 bps
  - **Correlation**: H-009 0.013, H-012 0.119, H-019 0.112 — near-zero with everything
  - **Train/Test**: Train Sharpe 0.36, Test Sharpe 3.20 (effect strengthening)
  - **Adaptive WF (select best/worst day)**: Only 4/6 — fixed Wed/Thu is MORE robust than adaptive
- Notes:
  - **Strongest walk-forward result in the entire project** (6/6, mean 2.46, all folds > 1.6)
  - No parameters = zero overfitting risk (beyond the Wed/Thu selection itself)
  - Effect is strengthening over time — recent folds have higher Sharpe
  - Cross-asset consistency (all 14 positive) suggests structural cause, not random
  - Possible causes: institutional rebalancing, options expiry flow (Deribit Fri), market maker inventory
  - BTC-specific DOW effects individually not significant (p>0.1) due to small sample — but the pattern holds in walk-forward
  - 40 hypotheses tested total
- Sessions: [2026-03-19 review+research session 40]

## H-040: Volatility Regime Factor Timing
- Status: REJECTED
- Idea: Scale cross-sectional factor strategy exposure inversely with realized BTC volatility. High vol → reduce exposure, low vol → increase.
- Instrument: futures (14-asset universe)
- Timeframe: daily
- Logic: Compute BTC realized vol over rolling window (10/20/30/60d). Scale H-012 exposure by target_vol / realized_vol. Also test binary regime (above/below expanding median).
- Data: H-012 daily returns + BTC realized vol, 734 daily bars.
- Result:
  - **In-sample**: Marginal improvement. Best: 20d binary regime Sharpe 2.18 (base 2.01). Invvol Sharpe 2.13-2.16.
  - **Walk-forward**: **NEGATIVE improvement**. Invvol: OOS mean 1.66 vs base 1.72 (-0.06). Binary: 1.41 vs 1.72 (-0.31).
  - **Combined DOW+Vol**: Sharpe 2.01 → 2.15 (marginal, likely overfitting).
- Notes: Base factor strategies already implicitly time volatility through portfolio turnover and equal-weight normalization. Explicit vol timing adds complexity without OOS benefit. REJECTED.
- Sessions: [2026-03-19 review+research session 40]

## H-041: BTC Dominance Rotation
- Status: REJECTED
- Idea: Use BTC's share of total normalised price (14-asset proxy for market cap dominance). When BTC dominance rising → long BTC / short alts. When falling → long alts / short BTC.
- Instrument: futures (BTC vs 13 alts)
- Timeframe: daily
- Logic: Compute dom_roc = diff(btc_dom, lookback). Signal = sign(dom_roc). Long BTC+short alts when rising, vice versa. Rebalance daily on signal flip.
- Data: 14 assets, 735 daily bars (2024-03-15 to 2026-03-19, ~2yr).
- Result:
  - **Without look-ahead**: IS Sharpe 3.96, WF 6/6 — FAKE, look-ahead biased
  - **Correctly lagged (signal@t-1, return@t)**: IS Sharpe 0.24 best (LB60_volume), WF 3/6, 1/16 params positive (6.2%). Best IS annual 3.0%, 22% DD.
  - **Root cause**: Dominance signal mean-reverts next day. When BTC outperformed alts today (dom_roc>0), alts tend to catch up tomorrow. Signal is anti-momentum at 1-day horizon across all lookbacks.
- Notes: The 100% positive IS results (without lag) were entirely look-ahead bias — using today's close to compute the signal AND the return. All 16 lookbacks (1–60d) negative with correct lag. Fails all three criteria: IS positive 6.2%, WF 3/6, not fee-robust.
- Sessions: [2026-03-19 research session 41]

## H-042: Cross-Sectional Return Dispersion / Short-Term XSMom
- Status: CONFIRMED (standalone, not yet in portfolio)
- Idea: When cross-sectional return dispersion is high, enable momentum positions (long winners, short losers). When dispersion is low, go flat. Tested as both standalone and H-012 overlay.
- Instrument: futures (14-asset universe)
- Timeframe: daily (with multi-day rebalancing)
- Logic: Compute rolling cross-sectional std of returns across 14 assets. When dispersion > Nth percentile → long top-N / short bottom-N by 20d (or 60d) momentum. Otherwise flat.
- Data: 14 assets, 735 daily bars (2024-03-15 to 2026-03-19, ~2yr). ~33-36 OOS observations per WF fold.
- Result:
  - **IS (full, correctly lagged)**: Sharpe 1.166, +27.4% annual, 12.1% DD (best params: M20_R21_N4). 77.1% of 48 param sets positive.
  - **Walk-forward (6 folds, 60d OOS each)**: **4/6 folds positive**, mean OOS Sharpe 0.548. Fold results: -3.32, +1.66, +2.01, +1.41, -1.07, +2.61.
  - **Fee robustness (2x)**: Sharpe 1.082 — fee-robust.
  - **Correlation with H-009**: -0.057 (near-zero)
  - **Correlation with H-012**: 0.686 (moderate-high — partially overlapping with existing momentum)
  - **Dispersion filter**: Does NOT add alpha. Only 10.2% of dispersion param combos improve over base. Core signal is short-term XSMom (20d lookback, 21d rebal).
  - **As H-012 overlay**: Hurts Sharpe (0.739 → 0.395). Dispersion is not a good gating condition.
- Notes: The hypothesis as posed (dispersion conditioning) does not work — dispersion filter hurts more than it helps. The genuine signal here is a short-term (20d) XSMom, distinct from H-012 (60d). Corr with H-012 is 0.686 — moderately high. This is NOT added to the portfolio because it is partially redundant with H-012 and the WF mean OOS Sharpe (0.548) is weak. Confirmed standalone (meets all 3 criteria) but portfolio impact marginal due to H-012 overlap.
- Sessions: [2026-03-19 research session 41]

## H-043: Open Interest Changes as Cross-Sectional Factor
- Status: REJECTED
- Idea: Rank assets by OI change (pct change in open interest over various windows). Long high OI change (momentum into leveraged positions) or short high OI change (contrarian).
- Instrument: futures (14-asset universe)
- Timeframe: daily (various rebalancing: 3, 5, 10 days)
- Logic: Compute N-day pct change in open interest for each asset. Rank cross-sectionally. Long top-N / short bottom-N. Tested both momentum (long high OI change) and contrarian (short high OI change) at windows 1, 3, 5, 10, 20 days.
- Data: 14 assets, 734 daily OI bars from Bybit (2024-03-16 to 2026-03-19), aligned with price data. OI data fetched from Bybit V5 historical API (up to 2053 bars per asset).
- Result:
  - **IS overall**: Only 34.4% of 90 param sets positive — weak.
  - **OI_CHG_1d (best)**: IS Sharpe 1.41 at n=5 r=3. But only works at 3-day rebal — fails at 5d and 10d. Walk-forward **1/5 folds positive**, mean OOS -0.90. FAILS.
  - **OI_CHG_20d_INV (contrarian, all positive)**: 100% IS positive (9/9) but best Sharpe only 0.60, mean 0.35. Very weak absolute edge.
  - **Fee robustness (OI_CHG_1d)**: Sharpe -0.60 at 5x fees. Not fee-robust.
- Notes: OI change alone is NOT a robust cross-sectional signal. Short-term (1d) OI change captures some mean-reversion in positioning but fails walk-forward. Long-term (20d) contrarian OI signal is too weak. The signal only works when combined with price (see H-044).
- Sessions: [2026-03-20 review+research session 42]

## H-044: OI-Price Divergence Factor
- Status: LIVE (paper trade since 2026-03-20, independent)
- Idea: Rank assets by divergence between price momentum and OI change. "Price up + OI down" = sustainable rally (shorts closing, not new leverage). "Price down + OI up" = leverage buildup (potential further decline).
- Instrument: futures (14-asset universe)
- Timeframe: daily (10-day rebalancing)
- Logic: Compute 20-day price change z-score and 20-day OI change z-score cross-sectionally. Signal = price_z - oi_z (lagged 1 day). Long top 5, short bottom 5.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19), OI from Bybit V5 API. ~101 OOS observations per WF fold.
- Result:
  - **IS (full, CORRECTED)**: Sharpe 1.01, +17.3% annual, 17.3% DD, 52.2% WR (n=5, r=10). **100% params positive (9/9)**. *Original Sharpe 1.46 was inflated ~4.9x by metrics bug (periods_per_year=8760 instead of 365). Corrected session 43.*
  - **Walk-forward (4 folds, ~122d OOS each, CORRECTED)**: **3/4 folds positive** (mean OOS Sharpe 1.22). Fold detail: +1.73, +1.40, +1.86, -0.13.
  - **Fee robustness**: Sharpe still positive at 5x fees — fee-robust.
  - **Correlation with H-009**: 0.016 (near zero)
  - **Correlation with H-012**: 0.565 (moderate — partially captures momentum)
  - **Correlation with H-019**: 0.154 (low)
  - **Correlation with H-021**: 0.064 (near zero)
  - **Correlation with H-024**: 0.249 (moderate)
- Notes: First strategy using genuinely new data (open interest). The OI divergence signal captures information beyond price momentum — assets where rallies are driven by deleveraging (OI down) tend to continue, while assets with increasing leverage during declines tend to fall further. Confirmed standalone with strong metrics. NOT in main portfolio due to 0.565 corr with H-012 (momentum), but deployed as independent paper trade. Initial rebalance: LONG SUI/OP/NEAR/SOL/ETH, SHORT ADA/ARB/DOT/XRP/DOGE.
- Sessions: [2026-03-20 review+research session 42]

## H-045: OI-Volume Confirmation/Divergence Factor
- Status: CONFIRMED standalone (weak) — NOT deployed
- Idea: Combine OI changes with volume changes as cross-sectional signal. Volume surge + OI increase = new positions (momentum). Volume surge + OI decrease = unwinding (reversal).
- Instrument: futures (14-asset universe)
- Timeframe: daily (10-day rebalancing)
- Logic: Compute cross-sectional z-scores of volume change and OI change. Test 6 signal variants (confirmation, divergence, new money, squeeze, triple, directed). Best robust variant: price_z * oi_z (no clip), 20d window.
- Data: 14 assets, 734 daily bars. OI data from Bybit V5.
- Result:
  - **Initial results inflated by zero-signal artifact**: Original NEW_MONEY_10d Sharpe 1.73 was 35% driven by tie-breaking of zero-signal assets (54% of signals clipped to zero).
  - **Robust no-clip variant (W20 n=4 r=10)**: IS Sharpe 1.76, +33.6%, 16.7% DD. WF 3/4 (mean OOS 1.28). But ONLY works at r=10 — sensitive to rebalance frequency.
  - **Correlations**: 0.109 with H-012, 0.144 with H-044, 0.067 with H-046 — low but strategy is fragile.
  - **49% of all param sets positive** — not robust across variants.
- Notes: The multiplicative signal (price * OI) concentrates information on assets with high-conviction OI movements, but creates many zero signals that corrupt ranking. The additive variants (confirmation, triple) are much weaker. Not deploying due to rebal sensitivity and partial redundancy with H-044.
- Sessions: [2026-03-20 review+research session 43]

## H-046: Price Acceleration Factor (Second Derivative of Momentum)
- Status: LIVE (paper trade since 2026-03-20, independent)
- Idea: Rank assets by change in 20-day momentum over the last 20 days (second derivative). Assets with accelerating momentum outperform those with decelerating momentum.
- Instrument: futures (14-asset universe)
- Timeframe: daily (3-day rebalancing)
- Logic: Compute 20-day return for each asset. Acceleration = return(t-20,t) - return(t-40,t-20). Cross-sectional z-score, lagged 1 day. Long top 4, short bottom 4.
- Data: 14 assets, 694 daily bars (after warmup). No OI data needed — price only.
- Result:
  - **IS (full)**: Sharpe 1.19, +25.1% annual, 17.6% DD, 50.1% WR (n=4, r=3). **100% params positive (9/9)**.
  - **Walk-forward (4 folds, ~122d OOS each)**: **4/4 folds positive** (mean OOS Sharpe **1.13**). Fold detail: +1.44, +0.29, +2.25, +0.54.
  - **Fee robustness**: 1.03 at 2x fees, 0.87 at 3x, 0.56 at 5x fees (decent).
  - **Correlations**: 0.007 with H-009, 0.099 with H-012, -0.123 with H-019, 0.179 with H-021 — **near-zero with everything**.
  - **Portfolio benefit**: H-012 + H-046 50/50 → Sharpe 1.71 (vs 1.37 standalone). Significant diversification.
- Notes: Captures a genuinely different aspect of price dynamics from momentum (H-012). Momentum measures the LEVEL of recent returns; acceleration measures the CHANGE in momentum. An asset just starting to move (low momentum, high acceleration) ranks differently from one with sustained high momentum. Perfect 4/4 WF and near-zero correlations make this one of the strongest discoveries since H-039 (DOW seasonality). Deployed as independent paper trade. Initial: LONG OP/ARB/NEAR/SUI, SHORT DOGE/LINK/ADA/DOT.
- Sessions: [2026-03-20 review+research session 43]

## H-047: Volatility Change Factor (Cross-Sectional, 14 Assets)
- Status: REJECTED
- Idea: Rank assets by change in realized volatility (short-window vol / long-window vol). Long assets with decreasing vol (stable), short assets with increasing vol. Or reverse.
- Instrument: futures (14 perps)
- Timeframe: 1D (various rebalancing: 3, 5, 10, 21 days)
- Logic: Compute rolling short-window (5/10/20d) and long-window (30/60/90d) realized vol. Ratio = short/long. Cross-sectional z-score. Test both long_low (decreasing vol) and long_high (increasing vol). 216 param sets.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr).
- Result:
  - **Overall**: 108/216 positive (50%) — exactly random
  - **long_low direction**: 30% positive, mean Sharpe -1.46
  - **long_high direction**: 70% positive, mean Sharpe +1.46
  - **Metrics severely broken**: Top Sharpe values (9+) are artifacts from sparse R21 rebalancing. Returns showing inf, DD >300%.
- Notes: 50% positive rate is the clearest signal of NO systematic edge. The asymmetry between directions (30% vs 70%) is due to the mirroring property of long/short portfolios. Vol dynamics (rising vs falling volatility) do not predict cross-sectional returns. Different from H-019 (vol LEVEL) which works.
- Sessions: [2026-03-20 review+research session 44]

## H-048: Realized Correlation Change Factor (Cross-Sectional, 13 non-BTC Assets)
- Status: REJECTED
- Idea: Rank assets by change in rolling correlation with BTC. Long assets becoming LESS correlated (diversifiers), short assets becoming MORE correlated.
- Instrument: futures (13 non-BTC perps)
- Timeframe: 1D (various rebalancing: 5, 10, 21 days)
- Logic: Compute rolling N-day (30/60/90) correlation of each alt with BTC. Delta = corr(t) - corr(t-M) where M=10/20/30. Cross-sectional z-score. 144 param sets.
- Data: 14 assets, 734 daily bars.
- Result:
  - **Overall**: 72/144 positive (50%) — exactly random
  - **Both directions 50/50** — no preference
  - **Top Sharpe values (6+) are artifacts** — metrics broken (inf returns)
- Notes: Correlation dynamics have no cross-sectional predictive power. Assets whose correlation with BTC is changing (up or down) don't systematically outperform. This is unsurprising — correlation is a slow-moving, noisy statistic with weak signal-to-noise at daily frequency.
- Sessions: [2026-03-20 review+research session 44]

## H-049: Long/Short Ratio Sentiment Factor (Contrarian, 14 Assets) — NEW
- Status: LIVE (paper trade since 2026-03-20, independent)
- Idea: Rank assets by Bybit long/short ratio (crowd positioning). Contrarian: long assets where crowd is MOST SHORT (lowest LSR), short assets where crowd is MOST LONG (highest LSR).
- Instrument: futures (14-asset universe)
- Timeframe: daily (5-day rebalancing)
- Logic: Fetch daily long/short ratio from Bybit API for all 14 assets. Cross-sectional z-score. Contrarian direction: long bottom 3, short top 3. Lagged 1 day.
- Data: 14 assets, **200 daily bars only** (2025-09-02 to 2026-03-20, ~6.5 months). **CAVEAT: well below 2-year standard.**
- Result:
  - **IS (full, R5_N3)**: Sharpe **2.58**, +59.1% annual, 7.2% DD, 55.3% WR. **100% params positive (12/12)** across all contrarian variants.
  - **All param range**: Sharpe 1.49 (R10_N5) to 2.80 (R1_N3) — ALL strongly positive
  - **Split-half**: First half Sharpe 2.01, second half **3.75** — both positive, effect STRENGTHENING
  - **Fee sensitivity (R5_N3)**: Zero-fee 2.58 → 4bps 2.38 → 8bps 2.18 → 12bps 1.98 → **20bps 1.58** (still positive at 5x fees!)
  - **Turnover**: 1.09 / 6 positions change per day (18%) — relatively stable
  - **Correlations**: H-012 -0.091, H-019 -0.127, H-021 0.231, **H-046 0.581** (high)
  - **Portfolio benefit**: 4 existing + H-049 → Sharpe 4.60 (from 4.29 without). H-012 + H-049 50/50 → 2.84 (vs 1.36 alone).
  - **Momentum direction**: 0/12 positive — purely contrarian edge, not momentum
- Notes: The strongest IS result ever found in this project (Sharpe 2.58, 100% params, 7% DD). However, the **200-day backtest limitation** is a serious caveat. Walk-forward validation is not possible with proper fold sizes. The signal captures genuine retail crowd positioning errors — when most traders are long an asset relative to peers, it tends to underperform. BTC and ETH are frequently in the contrarian LONG basket (crowd relatively less long / more short on these). High correlation with H-046 (acceleration, 0.581) suggests both capture "smart money vs. crowd" dynamics. Deployed as independent paper trade with extended monitoring period. Data source: Bybit `fetchLongShortRatioHistory` API, cached in `data/all_assets_lsr_daily.parquet`.
- Sessions: [2026-03-20 review+research session 44]

## H-050: Inter-Market Macro Signals for Crypto Timing
- Status: REJECTED
- Idea: Use traditional macro asset returns (S&P 500, Gold, DXY, VIX, 10Y yield) to predict next-day BTC/crypto returns. Test both directional BTC timing and cross-sectional beta tilting.
- Instrument: futures (BTC/USDT perp, 14-asset universe)
- Timeframe: 1D
- Logic: Compute N-day (1-20d) rolling macro asset return. Use sign as BTC timing signal (lagged 1 day). Also test VIX level regimes and combined risk-on composite. Also test macro-driven beta tilt in crypto universe.
- Data: SPY, GLD, UUP, ^VIX, ^TNX from Yahoo Finance (514 bars), aligned with 739 daily crypto bars (2024-03 to 2026-03).
- Result:
  - **Same-day correlations**: SPY-BTC +0.374 (significant), VIX-BTC -0.354. Crypto co-moves with equities.
  - **Lagged correlations**: ALL near zero (max |0.079|). No predictive power.
  - **BTC timing strategies**: 50 param sets tested. **Exactly 50% positive** = random noise. Mean Sharpe 0.000.
  - **VIX regime filter**: No edge. VIX < 20 Sharpe -0.25, VIX percentile < 0.5 Sharpe +0.13.
  - **Cross-sectional beta tilt**: All negative Sharpe.
  - **Combined macro composite**: All negative Sharpe.
- Notes: Crypto co-moves with equities same-day (SPY-BTC r=0.37) but the information is fully priced in by day's end. No lagged predictive power exists. This confirms efficient cross-market pricing — macro signals are absorbed intra-day. 50% positive rate across all lookbacks and directions proves there is zero edge.
- Sessions: [2026-03-20 review+research session 45]

## H-051: Monthly/Calendar Seasonality (Day-of-Month, Week-of-Month)
- Status: REJECTED
- Idea: Test if BTC returns vary systematically by day of month (turn-of-month effect, week-of-month pattern). If persistent, trade the best/worst days.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Logic: Compute mean return per day of month (1-31), week of month (1-5), month of year (Jan-Dec). Train/test split and walk-forward validation.
- Data: BTC, 739 daily bars (2024-03 to 2026-03). ~24 observations per day-of-month.
- Result:
  - **Day of month**: No statistically significant days (all |t| < 1.96). Week 5 (days 29-31) t=-2.40 borderline.
  - **Month of year**: No significant months (best Feb t=-1.32).
  - **Turn of month**: Negative (-0.21%) vs mid-month (+0.09%) — not significant.
  - **Train/test DOM correlation**: -0.133 (NEGATIVE — no persistence whatsoever)
  - **Walk-forward (6 folds, 180d train / 60d test)**: 3/6 positive, mean OOS -0.97. FAILS.
  - **Cross-asset**: BTC/ETH/SOL all show month-end weakness but not significant.
- Notes: The day-of-week effect (H-039: Wed+/Thu-) remains the ONLY calendar seasonality that works. Day-of-month patterns don't persist across periods (train/test corr -0.13). Walk-forward fails 3/6. The difference: day-of-week has 105+ observations per day (2yr), while day-of-month has only ~24 — insufficient for robust estimation. Monthly patterns (Jan-Dec) also too few observations. Calendar effects require high-frequency recurrence to be exploitable.
- Sessions: [2026-03-20 review+research session 45]

## H-052: Premium Index Cross-Sectional Factor (Contrarian)
- Status: LIVE (paper trade since 2026-03-20)
- Idea: Rank 14 crypto assets by average perpetual-to-spot premium/discount. Contrarian: long most discounted (shorts aggressive), short least discounted. Premium index is a genuinely different data source from price, volume, OI, or funding rate.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5 days)
- Logic: Compute avg premium index (close) over 5 days per asset. Rank cross-sectionally. Long bottom 4 (most discounted), short top 4 (least discounted). Market-neutral.
- Data: 14 assets, 734 daily bars (2024-03-16 to 2026-03-19, ~2yr). Bybit V5 premium-index-price-kline endpoint.
- Result:
  - **In-sample (full)**: 100% params positive (30/30). Best W5 R3 N4: Sharpe 2.25, +40.4%, DD -11.8%
  - **Walk-forward (6 folds, 120d train / 90d test)**: 23/24 majority positive, 3/24 ALL folds positive. Mean OOS Sharpe 1.35.
    - Best WF: W10 R3 N4 mean 2.01 (5/6). W5 R5 N4 mean 1.86 (6/6 ALL positive).
  - **Split-half**: First half Sharpe 2.18, Second half Sharpe 2.95 — BOTH strong.
  - **Fee sensitivity**: 1x fees Sharpe 1.88, 2x fees 1.50, 5x fees 0.39
  - **Correlations**: -0.142 H-012 (XSMom), 0.097 H-021 (VolMom), 0.167 H-046 (Accel)
- Notes: One of the strongest signals found. Negative correlation with momentum (excellent diversifier). Premium captures directional sentiment pressure — assets with extreme negative premium (shorts aggressive) tend to revert. Level_momentum (0% positive) and basis change (43%) fail, confirming it's a contrarian mean-reversion effect. Deployed with W5 R5 N4 (6/6 WF).
- Sessions: [2026-03-20 review+research session 46]

## H-053: Funding Rate Cross-Sectional Factor (Contrarian)
- Status: LIVE (paper trade since 2026-03-20)
- Idea: Rank 14 crypto assets by rolling 3-day average funding rate. Contrarian: long lowest funding (shorts paying longs, weak sentiment), short highest funding (crowded longs). Funding rate is mechanically related to premium index (H-052) but captures different time dynamics (8h discrete settlements vs continuous premium).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 10 days)
- Logic: Compute 3-day rolling avg of daily mean funding rate per asset. Rank cross-sectionally. Long bottom 4 (lowest funding), short top 4 (highest funding). Market-neutral.
- Data: 14 assets, 730 daily bars (2024-03-17 to 2026-03-16, ~2yr). 8h Bybit funding rates aggregated to daily avg. Cross-sectional mean correlation 0.694 (high — rates move together, but rank differences still predictive).
- Result:
  - **In-sample (full, contrarian only)**: 93% params positive (42/45). Best W3 R10 N4: Sharpe 1.52, +32.9% ann, 22.2% DD
  - **Momentum direction**: 0% positive (0/45) — crowded longs continue to underperform
  - **Walk-forward (6 folds, 90d test)**: **6/6 positive** for W3 R10 N4 (mean OOS **2.29**, folds: 4.91, 0.94, 2.84, 0.06, 1.60, 3.42)
  - **Split-half**: First half 1.31, Second half 1.91
  - **Fee sensitivity**: 1x Sharpe 1.52, 2x 1.37, 5x 0.92, 10x 0.17
  - **Correlations**: 0.004 H-012 (XSMom), 0.109 H-046 (Accel), **0.360 H-052 (Premium)**, **0.480 H-049 (LSR)**
  - **Without ATOM**: Still Sharpe 1.22 (ATOM has anomalous -1.32% ann funding, in bottom 3 49% of days)
- Notes: Strongest WF result in project (tied with H-039 at 6/6). Moderate correlation with H-052 (0.36) expected since funding ≈ f(premium). High correlation with H-049 (0.48) since both are contrarian positioning signals. Near-zero correlation with momentum factors. The 0% positive for long_high direction strongly confirms contrarian mechanism: crowded longs (high funding) reliably underperform.
- Sessions: [2026-03-20 review+research session 47]

## H-077: Short-Term Reversal Factor (14 Assets)
- Status: REJECTED — no edge in crypto, fee-sensitive
- Idea: Rank assets by 5-day return, LONG most oversold (bottom N), SHORT most overbought (top N). Classic contrarian reversal.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 1-5 days)
- Logic: Compute N-day return, rank, long bottom N, short top N. Tests: lookback 3/5/7/10, rebal 1/3/5, N 3/4.
- Result: **Only 12% params positive** (3/24). Best Sharpe 0.165 (L3_R3_N3), annual return -5.3%, max DD 49.8%. WF 3/4 positive but inflated by single outlier fold. Very fee-sensitive — negative at 2x fees. H-012 correlation -0.130.
- Notes: Short-term reversal does not work in crypto. Assets too correlated — short leg destroyed in trending markets. Would need regime filter but not worth pursuing.
- Sessions: [2026-03-26 review+research session 90]

## H-078: Return Skewness Factor — Contrarian Direction (14 Assets)
- Status: REJECTED — full-period Sharpe too weak despite interesting OOS
- Idea: Rank assets by rolling return skewness. LONG negative-skew assets (crash risk premium), SHORT positive-skew (lottery overpricing). Opposite direction from H-060.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 5-21 days)
- Logic: Compute rolling skewness (20-60d window), rank, long most negative skew (bottom N), short most positive (top N). Tests: window 20/30/40/60, rebal 5/10/21, N 3/4.
- Result: 29% params positive (7/24). Best Sharpe 0.392 (W40_R21_N4), annual return +8.1%, max DD 50.3%. WF 4/4 positive with param selection (mean OOS Sharpe 1.681). Fee resilient (low turnover). **H-012 correlation -0.345** (good diversifier).
- Notes: Opposite direction from H-060 (which was 72% positive but OOS decayed). This version has better OOS but weaker full-period. True daily Sharpe ~0.08 after metrics correction — too weak to deploy. The -0.345 momentum correlation is valuable but insufficient standalone alpha.
- Sessions: [2026-03-26 review+research session 90]

## H-079: Return Autocorrelation Factor (14 Assets)
- Status: REJECTED — fragile, walk-forward fails
- Idea: Rank assets by rolling lag-1 return autocorrelation. Long trending (positive AC), short mean-reverting (negative AC). Tests both directions.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Result: 42% params positive (51/120). Best Sharpe 1.181 (LB=20, REB=3, N=5, long_negative). WF **2/6 positive** (mean -0.57). Split-half 1.78→0.32 (degrades). Momentum correlation -0.236.
- Notes: Autocorrelation is too noisy at the daily frequency for cross-sectional ranking. Best direction was "long mean-reverting" which is counterintuitive. Signal not robust.
- Sessions: [2026-03-26 review+research session 91]

## H-080: VWAP Trend Factor (14 Assets)
- Status: REJECTED — too correlated with momentum
- Idea: Compare current close to rolling VWAP (volume-weighted average price). Long assets above VWAP, short below.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Result: 43% params positive (62/144). Best Sharpe 1.228 (LB=60, REB=7, N=3, long_positive). WF 4/6 positive (mean 0.78). Split-half 1.95→0.33. **Correlation 0.647 with momentum** — essentially same signal via different mechanism.
- Notes: VWAP trend is momentum in disguise. Above-VWAP = trending up = momentum. No diversification value.
- Sessions: [2026-03-26 review+research session 91]

## H-081: Hurst Exponent Factor (14 Assets)
- Status: REJECTED — weak signal, computationally expensive
- Idea: Rank assets by rolling Hurst exponent (R/S analysis). Long persistent (H>0.5), short mean-reverting (H<0.5).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Result: 25% params positive (9/36). Best Sharpe 0.787 (LB=60, REB=7, N=4, long_negative). WF **3/6 positive** (mean -0.98). Split-half 0.31→-1.09 (second half negative). Momentum correlation 0.215.
- Notes: Hurst exponent is too noisy at the crypto daily frequency. R/S analysis needs longer time series for stable estimates. 90-day Hurst only marginally better than shorter windows.
- Sessions: [2026-03-26 review+research session 91]

## H-082: Risk-Adjusted Carry Factor (14 Assets)
- Status: CONDITIONAL — interesting signal but parameter-sensitive
- Idea: Rank by funding_rate / realized_volatility (per-asset funding "Sharpe"). Long highest risk-adjusted carry, short lowest.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Result: 44% params positive (84/192). Best Sharpe 1.239 (VW=20, FW=21, REB=7, N=3, long_positive). WF **4/6 positive** (mean **1.087** — strongest recent WF). Split-half 1.27→0.38 (second half weak). **Correlation -0.114 with momentum** (excellent diversifier).
- Notes: Risk-adjusting the carry signal by volatility is theoretically sound. The negative correlation with momentum makes this highly attractive for portfolio diversification. However, only 44% params positive and significant split-half degradation indicate overfitting risk. Best params all use FW=21 (3-week funding window) with VW=20 (3-week vol) — requires extended lookback. Could be revisited if H-053 (raw funding XS) shows sustained success.
- Sessions: [2026-03-26 review+research session 91]

## H-083: Idiosyncratic Volatility Factor (14 Assets)
- Status: CONDITIONAL — strong recent performance but asymmetric historical behavior
- Idea: Low idiosyncratic volatility anomaly. After removing BTC beta via OLS regression, rank assets by residual vol. Long lowest idio vol (quality), short highest idio vol.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Result: Best Sharpe 0.89 (LB=40, REB=5, N=3), +35.5% ann, -60.3% DD. **94% params positive** (45/48). **Correlation -0.011 with H-012** — near zero, excellent diversifier. WF **5/6 positive** (fold 0 was -3.30, rest 1.01-3.43). Split-half **-0.83 / +1.91** — bad first half, great second. 70/30: IS 0.15, OOS 2.53.
- Notes: The signal clearly exists in recent data (2025-2026) but was terrible in 2024. This regime shift is concerning — the idio vol anomaly may be a newer phenomenon in crypto. The near-zero momentum correlation makes it an excellent diversifier IF it persists. Max DD 60% is too high for standalone. Revisit if the signal remains stable for another 6 months.
- Sessions: [2026-03-26 review+research session 92]

## H-084: BTC Correlation Factor (14 Assets)
- Status: REJECTED — no consistent edge
- Idea: Long assets with low BTC correlation (decorrelation premium), short high BTC correlation.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Result: Best Sharpe **0.42** (LB=20, REB=10, N=3). Only **31% params positive** (15/48). WF 3/6 positive — recent folds terrible (fold 5: -5.62). Split-half +1.98 / -1.82 — complete reversal. 70/30: IS 1.37, OOS -2.14. Corr 0.09 with H-012.
- Notes: The BTC correlation factor worked in early data (2024) but completely reversed in 2025-2026. Crypto assets became more correlated over time, making the low-correlation premium disappear. Fundamental regime change killed the signal.
- Sessions: [2026-03-26 review+research session 92]

## H-086: Multi-Timeframe Momentum Composite (14 Assets)
- Status: REJECTED — doesn't beat single 60d, high corr with H-012
- Idea: Combine z-scored 5d, 20d, and 60d returns into a composite score. Long top N, short bottom N.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Result: Best Sharpe **1.25** (R3_N3), +59.9% ann, 34.7% DD. 100% params positive (9/9). WF 5/6 positive (mean 0.72). 70/30: train-best OOS Sharpe only 0.21. Split-half: both halves positive (mean 1.14/1.08). **Corr 0.68 with H-012.** Single 60d momentum: Sharpe 1.41 — beats the composite. 5d timeframe has NEGATIVE Sharpe (-0.97) and drags the composite down.
- Notes: Adding short-term momentum to 60d signal hurts. Crypto short-term (5d) momentum is strongly mean-reverting, which offsets the longer-term trend. No added value over existing H-012.
- Sessions: [2026-03-26 review+research session 93]

## H-087: Amihud Illiquidity Factor (14 Assets)
- Status: REJECTED — redundant with H-031 (size)
- Idea: Amihud illiquidity ratio = |return|/dollar_volume. Test both directions: long liquid vs long illiquid.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Result: Long-liquid works, long-illiquid doesn't. Best Sharpe **2.37** (liquid_long_L20_R7_N4), +177.6% ann, 25.5% DD. WF fixed: **6/6 positive** (mean 1.82). WF selected: 5/6 positive (mean 1.40). 70/30 OOS Sharpe 2.02. Split-half corr **0.97**. BUT: **corr 0.916 with H-031 (size factor)**. Corr 0.435 with H-012.
- Notes: In crypto, Amihud illiquidity is a near-perfect proxy for market cap/size — BTC and ETH are the most liquid, small alts are illiquid. "Long liquid, short illiquid" ≈ H-031 size factor. Despite excellent standalone metrics, adding this would double-count the size premium.
- Sessions: [2026-03-26 review+research session 93]

## H-088: Time-Series Momentum (TSMOM) Portfolio (14 Assets)
- Status: REJECTED — WF fails, excessive DD
- Idea: Trade each of 14 assets based on own L-day return sign (long if positive, short if negative). Net directional — can be fully long or short the entire market.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Result: Best Sharpe **1.03** (L60_R1, equal weight), +56.6% ann, **55.7% DD**. WF param selection: **2/6 positive** (mean -1.06). WF fixed: 4/6 positive (mean 0.22). 70/30 OOS Sharpe 0.91. Corr -0.37 with BTC (negative — would be diversifier). Corr 0.30 with H-012. Vol-scaled variant nearly identical (corr 0.997).
- Notes: Interesting concept — negative BTC correlation is rare. But unreliable: WF param selection fails catastrophically (2/6), max DD 55.7% is unacceptable. The negative BTC correlation comes from going short during crypto downturns (=trend following), which H-009 already captures. Net directional risk too high for standalone deployment.
- Sessions: [2026-03-26 review+research session 93]

## H-089: Funding Rate Momentum (Change in Funding Rate, Contrarian)
- Status: CONDITIONAL — fragile param selection, but second-best params promising
- Idea: Rank assets by change in rolling-average funding rate (short window vs long window). Contrarian: long assets where funding is falling (shorts increasing), short assets where funding is rising (longs piling in).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Compute short_window avg funding rate minus long_window avg funding rate. Rank cross-sectionally. Contrarian: long bottom N (falling funding), short top N (rising funding). Rebalance every R days.
- Result: 63% params positive (108 tested), mean Sharpe 0.17. Best IS (SW5/LW21/R7/N5): Sharpe 1.43, +25.1% ann, -19.8% DD — but WF 2/6, split-half decays (0.85→-1.79). **Second-best** (SW3/LW21/R10/N5): Sharpe 1.20, WF **4/6 positive (mean 0.94)**, split-half 0.45/0.15 (both positive). Corr **-0.25** with H-012 (negative — good diversifier).
- Notes: Param selection is fragile — best IS params overfit completely. But robust params exist with decent WF performance. Negative momentum correlation makes it an interesting diversifier. May revisit if portfolio needs more diversification.
- Sessions: [2026-03-27 review+research session 94]

## H-090: BTC Correlation Breakaway Factor (13 Assets ex-BTC)
- Status: REJECTED — split-half collapses, OOS negative
- Idea: Rank assets by change in rolling correlation with BTC. Long assets decoupling from BTC, short assets increasingly correlated.
- Instrument: futures (13 USDT perps, ex-BTC)
- Timeframe: 1D
- Result: 43.8% params positive (48 tested), mean Sharpe -0.13. Best (W20/R10/N3): Sharpe 1.10, +50.5% ann, -40.7% DD. But 70/30 OOS: Sharpe **-2.30**. Split-half: **2.28→-1.17** (massive decay). WF 3/5 positive, combined annual return -0.001. Low corr with momentum (0.10) and beta (0.08).
- Notes: Signal worked in early period (2024) but completely reversed in 2025-2026. Likely spurious — correlation dynamics in crypto shift too fast for a static strategy. Not deployable.
- Sessions: [2026-03-27 review+research session 94]

## H-091: Volume Concentration (Herfindahl) Factor
- Status: REJECTED — weak params, anti-correlated split-half
- Idea: Measure how concentrated volume is across days using Herfindahl index. Long assets with uniform volume (organic interest), short assets with volume spikes (episodic attention).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Result: 33.3% params positive (48 tested), mean Sharpe -0.11. Best (W10/R3/N5): Sharpe 0.74, +19.7% ann, -37.4% DD. Split-half anti-correlated (-0.23), only 4.2% both positive. WF fixed 4/6, but WF selected **2/6** (mean -1.22). Corr -0.07 with momentum, -0.03 with size.
- Notes: Volume concentration doesn't predict returns cross-sectionally in crypto. The 14-asset universe likely too small for this factor — all assets have similar volume patterns. Second half performance reverses first half. Dead end.
- Sessions: [2026-03-27 review+research session 94]

## H-092: Volume-Weighted Momentum Factor (14 Assets)
- Status: REJECTED — too correlated with plain momentum, poor walk-forward
- Idea: Weight each day's return by relative volume (volume / avg volume over lookback). High-volume moves matter more. Rank cross-sectionally, long top N, short bottom N.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: vol_weighted_momentum = sum(daily_log_return * relative_volume) over lookback. Rank. Long top N, short bottom N. Dollar-neutral.
- Result: **100% params positive** (48/48), mean Sharpe 1.167, median 1.22, best L90_R7_N5 Sharpe 1.807 (+63.9% ann, -15.0% DD). 70/30: train 2.183, OOS 0.414 (decay). Split-half corr 0.172 (poor), half1 1.43 / half2 0.47. WF fixed **0/4 positive** (all zeros). WF selected **2/4** (mean 1.22: folds 3.19, -0.04, 2.31, -0.59). **Corr 0.586 with H-012** — highly correlated with plain momentum. Short lookback (20d) works better than long (40-90d) but becomes noisy.
- Notes: Volume weighting doesn't add novel information beyond raw momentum in crypto. The 0.586 correlation with H-012 means this is largely the same signal with extra noise. Walk-forward inconsistency confirms it's not a robust independent factor. L20 params show better split-half but still degraded OOS. Dead end.
- Sessions: [2026-03-27 review+research session 95]

## H-093: Trend Consistency (Hit Rate) Factor (14 Assets)
- Status: CONDITIONAL — strong walk-forward but split-half asymmetry
- Idea: Fraction of positive daily returns over lookback period. High hit rate = consistent uptrend. Different from momentum (total return) and efficiency (path quality). Rank cross-sectionally, long top N, short bottom N.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: hit_rate = count(daily_return > 0) / lookback_days. Rank. Long top N (most consistently positive), short bottom N (most consistently negative). Dollar-neutral.
- Result: **100% params positive** (60/60), mean Sharpe 0.753, median 0.685, best L10_R3_N3 Sharpe 1.784 (+109.1% ann, -36.5% DD). 70/30: train 1.553, **OOS 1.914** (OOS > IS — rare positive sign). Split-half corr **-0.118** (negative — concerning), 75% both positive, half1 0.49 / half2 1.30. WF fixed (L10_R3_N3): **3/4 positive** (mean 0.966: 1.71, 3.17, -1.33, 0.31). WF selected: **4/4 positive** (mean 1.152: 2.23, 0.71, 0.86, 0.81). **Corr 0.214 with H-012** — partially independent. Short lookback (10-20d) with N=3 works best.
- Notes: The 4/4 walk-forward with param selection is strong, and OOS beating IS is unusual. But the negative split-half correlation signals a regime shift — this factor works much better in 2025-2026 than 2024. Short 10-day lookback captures recent price consistency effectively. The 0.214 momentum correlation means it captures some independent information. Revisit if H-076 (price efficiency, corr 0.04) shows it captures a similar signal. Best candidates for deployment: L10_R3_N3, L20_R5_N3, L20_R10_N3.
- Sessions: [2026-03-27 review+research session 95]

## H-094: Volume Asymmetry Factor (Buy vs Sell Volume, 14 Assets)
- Status: REJECTED — OOS failure, highly correlated with momentum
- Idea: Compare volume on up-days vs down-days. volume_asymmetry = (up_volume - down_volume) / (up_volume + down_volume). Long assets with buy-volume dominance, short assets with sell-volume dominance.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Over lookback window, compute up_volume (vol on close > prev_close days) and down_volume (close < prev_close days). volume_asymmetry ratio. Rank. Long highest, short lowest. Dollar-neutral.
- Result: 96.7% params positive (58/60), mean Sharpe 0.605, median 0.601, best L60_R7_N5 Sharpe 1.435 (+48.1% ann, -20.7% DD). 70/30: train 1.591, **OOS -0.546** (fails). Split-half corr **-0.285** (negative), 66.7% both positive, half1 0.35 / half2 1.12. WF fixed (L60_R7_N5): **2/4 positive** (mean 1.107: 2.26, -0.47, -0.37, 3.00 — highly erratic). WF selected: **2/4** (mean 0.376: 2.10, -0.94, 2.22, -1.87). **Corr 0.633 with H-012** — essentially capturing momentum through volume lens.
- Notes: The high momentum correlation (0.633) confirms this is not a novel signal — assets going up naturally have more volume on up-days. OOS failure is definitive. The negative split-half correlation and erratic walk-forward (alternating strong positive and negative folds) suggest the factor is regime-dependent rather than robust. Dead end.
- Sessions: [2026-03-27 review+research session 95]

## H-095: Realized Semivariance Ratio Factor (14 Assets)
- Status: REJECTED — WF selected 1/4 positive, regime-dependent signal
- Idea: Rank assets by upside/downside realized volatility ratio. Long positive-skew assets, short negative-skew assets.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: For each asset over lookback, compute sqrt(upside_semivariance) / sqrt(downside_semivariance). High ratio = favorable skew. Rank. Long top-N, short bottom-N. Dollar-neutral.
- Result: 97.8% params positive (44/45), mean Sharpe 0.757, best L10_R3_N3 Sharpe 1.789 (+88.9% ann, -28.6% DD). 70/30: train 2.162, test 0.727 (decays). Split-half: half1 1.602, **half2 -0.262** (asymmetric, corr -0.037). WF fixed (L10_R3_N3): **2/4** positive (mean 0.182). WF selected: **1/4** positive (mean -1.223 — severe failure). Corr 0.226 with H-012 (moderate).
- Notes: High IS robustness (97.8%) is misleading — the signal is heavily regime-dependent. Works in recent period (fold 1 Sharpe 2.45) but fails badly in mid-2025 (fold 2: -4.22, fold 3: -1.58). The split-half confirms asymmetry — first half of data strong, second half negative. Not deployable.
- Sessions: [2026-03-27 review+research session 96]

## H-096: Intraday Return Dispersion Factor (14 Assets)
- Status: REJECTED — only 28.9% params positive, mean Sharpe negative
- Idea: Rank assets by ratio of mean intraday range to mean absolute close-to-close return (dispersion). Long efficient movers (low dispersion), short noisy ones (high dispersion).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: For each asset, dispersion = mean(high-low)/close / mean(abs(close-prev_close)/prev_close) over lookback. Low dispersion = trending efficiently. Rank. Long bottom-N (efficient), short top-N (noisy). Dollar-neutral.
- Result: 28.9% params positive (13/45), mean Sharpe -0.187, best L10_R5_N4 Sharpe 0.539 (+13.9% ann, -35.7% DD). 70/30: train 0.280, test 1.949 (suspicious test > train). Split-half: half1 -0.466, half2 0.174 (corr 0.044). WF fixed: 1/4 positive (mean 0.174). WF selected: 2/4 positive (mean 0.286 — weak). Note: this is essentially the inverse of H-076 (price efficiency) but the specific formulation fails.
- Notes: Despite being conceptually related to H-076 (which works well), this inverted ratio formulation doesn't capture the signal. The directional asymmetry matters — H-076 ranks by efficiency directly, while this ranks by noise, and the noise metric isn't as clean. Only 29% positive is a clear failure.
- Sessions: [2026-03-27 review+research session 96]

## H-097: Cross-Asset Lead-Lag Momentum Diffusion (14 Assets)
- Status: REJECTED — 37% params positive, WF selected 1/4, unstable
- Idea: Exploit information diffusion — some crypto assets lag behind cross-sectional average returns. Estimate lead-lag betas, then trade expected momentum spillover.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: For each asset, regress return(t) on equal-weight market return(t-lag) over lookback. lead_lag_beta captures responsiveness. Signal = beta * recent_market_return. High signal = laggard expected to catch up. Rank. Long top-N, short bottom-N.
- Result: 37.0% params positive (20/54), mean Sharpe -0.323, best L60_LAG2_R3_N3 Sharpe 0.986 (+40.4% ann, -50.3% DD). 70/30: train 0.663, test 2.148 (suspicious test > train). Split-half: half1 -0.763, half2 0.142 (corr 0.167). WF fixed: 2/4 positive (mean 0.737). WF selected: **1/4** positive (mean -1.178). Corr -0.127 with H-012.
- Notes: Information diffusion in crypto is too fast for daily-frequency exploitation. The lead-lag structure is noisy and unstable across periods. Best params have 50% DD — unacceptable. The negative correlation with momentum (-0.127) is interesting but the signal itself doesn't hold. Previously tested H-057 (BTC/ETH→Alts lead-lag) also failed — confirming daily lead-lag is not viable in crypto.
- Sessions: [2026-03-27 review+research session 96]

## H-098: BTC-Residual Momentum (14 Assets, Daily)
- Status: REJECTED — strong IS but severe half2 collapse, high H-012 correlation
- Idea: Cross-sectional momentum after removing BTC beta — rank by alpha_i = cumret_i - beta_i * cumret_btc. Should isolate "pure outperformers" vs the market.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Rolling OLS beta to BTC over lookback window. Residual cumulative return = total return minus beta*BTC return. Rank. Long top N, short bottom N. Rebalance every R days.
- Result:
  - **Param scan (90 combos)**: 100% positive, mean Sharpe 1.138, median 1.131, best LB120_R14_N3 (Sharpe 1.765, +115% ann, 24% DD)
  - **WF fixed best params (4 folds)**: 3/4 positive, mean OOS Sharpe 0.644 — fold 3 negative (-0.309)
  - **WF with param selection (3 folds)**: 1/3 positive, mean OOS Sharpe -0.239 — severe overfitting in IS param selection
  - **Split-half**: Half 1 mean 1.844, Half 2 mean 0.035, cross-half Sharpe corr -0.493 — strategy nearly dead in second half
  - **Fee sensitivity (5 bps)**: 100% positive, mean 1.145, negligible degradation
  - **Correlation with H-012**: 0.698 — high; mostly captures same momentum signal
- Notes: Factor is essentially a beta-hedged version of H-012 momentum. The signal collapses in half 2 (2025-03-19 onwards), suggesting the alpha vs BTC was concentrated in the 2024 bull period when some alts ran independently. In 2025+, the whole market moved together and the residual signal lost content. High correlation with H-012 means no diversification benefit. The param selection WF (mean -0.239) confirms the IS performance is not stable OOS.
- Sessions: [2026-03-27 backtest]

## H-099: Tail Risk Factor / CVaR (14 Assets, Contrarian)
- Status: REJECTED — strong standalone but 0.749 corr with H-019 (low-vol by another name)
- Idea: Rank assets by Conditional Value at Risk (average of worst 10% of returns). Long low tail risk (least negative CVaR), short high tail risk. Tests both risk-premium and contrarian directions.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Compute CVaR = mean of bottom P% of daily returns over lookback window. Rank. Contrarian: long high CVaR (low tail risk), short low CVaR (high tail risk).
- Result:
  - **Param scan (300 combos)**: 50% overall positive. **Contrarian direction: 100% positive** (150/150), mean Sharpe 1.839. Risk-premium: 0% positive (all negative).
  - **Best params**: LB30_R14_N3_P10_contrarian, Sharpe 2.352, +177% ann, 28% DD
  - **WF fixed (4 folds)**: **4/4 positive**, mean OOS Sharpe 2.183 — very strong
  - **WF param selection (4 folds)**: **4/4 positive**, mean OOS Sharpe 2.736 — exceptional
  - **Split-half**: Spearman 0.761 (very stable), both-positive 50%, H1 0.193 / H2 0.175 — consistent
  - **Correlation with H-012**: 0.438 (moderate)
  - **Correlation with H-019 (low-vol)**: **0.749** (very high — same signal)
  - **Fee sensitivity**: Robust — Sharpe 2.30 even at 20bps
- Notes: Strongest OOS results of any factor tested recently (WF 4/4 fixed AND param selection). The concept "buy safe assets, sell dangerous ones" is fundamentally the low-volatility anomaly — CVaR and realized vol are highly correlated cross-sectionally. Since H-019 already captures this signal, deploying H-099 would be redundant. Could replace H-019 if performance diverges in paper trading, but not worth a new deployment.
- Sessions: [2026-03-27 backtest session 97]

## H-100: Average Pairwise Correlation / Comovement Factor (14 Assets)
- Status: REJECTED — OOS failure, extreme split-half instability
- Idea: For each asset, compute average correlation with all other 13 assets over rolling window. Test long low-comovement (independent movers) vs long high-comovement (crowd leaders).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Rolling correlation matrix over window. Average each asset's pairwise correlations. Rank. Direction A: long low-corr, short high-corr. Direction B: vice versa.
- Result:
  - **Param scan (150 combos)**: 62% positive (93/150). Low-corr-long mean Sharpe 0.673 (clearly better). High-corr-long mean -0.316.
  - **Best params**: CW60_R3_N3_low_corr_long, Sharpe 1.556, +78% ann, 29% DD
  - **WF fixed (4 folds)**: 3/4 positive but last fold **-0.740** (recent period fails)
  - **WF param selection (3 folds)**: Mixed — 2.144, -2.384, 0.849. Direction instability (fold 1 selects high_corr_long, opposite of others)
  - **Split-half**: Spearman **-0.757** (extremely unstable — what works H1 fails H2), both-positive **3.3%**
  - **Train/test**: Train Sharpe 2.2 → Test Sharpe **-0.071** (complete OOS failure)
  - **Correlation with H-012**: 0.371, with H-031: -0.015
  - **Fee sensitivity**: Robust (minimal degradation)
- Notes: The factor captures something real (independent movers outperform) but it's extremely regime-dependent. The -0.757 split-half correlation and train/test failure (2.2 → -0.07) mean the signal flips direction between periods. The direction instability in WF (folds selecting opposite directions) confirms the factor is not stable enough to trade. Correlation patterns change over time in crypto as narrative/sector rotation shifts which assets co-move.
- Sessions: [2026-03-27 backtest session 97]

## H-101: Return Kurtosis Factor (14 Assets)
- Status: REJECTED — regime-dependent, split-half reversal
- Idea: Rank assets by rolling excess kurtosis. Long lowest kurtosis (thin tails), short highest kurtosis (fat tails). Hypothesis: low-kurtosis assets deliver better risk-adjusted returns.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Rolling excess kurtosis of daily returns (20-60d window). Negate to long thin-tailed, short fat-tailed. Dollar-neutral.
- Result:
  - **Param scan (48 combos)**: **96% positive** (46/48). Mean Sharpe 0.514. Best LB30_R5_N5 Sharpe 1.288, +45.5% ann, 27.4% DD.
  - **Train/test (70/30)**: IS 1.406 → OOS **0.119** (near-zero alpha OOS)
  - **Split-half**: Correlation **-0.614** (extreme reversal!). H1 mean 0.006, H2 mean 1.637. Factor only works in 2025+.
  - **WF fixed (4 folds)**: 3/4 positive, mean 0.762 (includes strong H2 period)
  - **WF selected (4 folds)**: **1/4 positive**, mean 0.106 (severe param overfit)
  - **Correlation with H-012**: **-0.009** (zero — genuinely novel signal)
- Notes: Extremely interesting from a diversification standpoint (zero H-012 correlation) but the signal is regime-dependent. Only works in H2 (late 2025-2026), essentially zero alpha in H1 (2024-mid 2025). The -0.614 split-half correlation means what works in one period reverses in the next. Strategy file: `strategies/h101_kurtosis/backtest.py`.
- Sessions: [2026-03-27 backtest session 98]

## H-102: Volume Stability Factor (14 Assets)
- Status: REJECTED — poor parameter robustness, OOS failure
- Idea: Rank assets by coefficient of variation (CV) of daily dollar volume. Long most stable volume (low CV = institutional interest), short most bursty (high CV = retail hype).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Rolling CV = std/mean of dollar volume over lookback window. Negate to long stable, short bursty. Dollar-neutral.
- Result:
  - **Param scan (48 combos)**: Only **27% positive** (13/48). Mean Sharpe **-0.259**. Best only 0.337.
  - **Train/test**: IS 0.019 → OOS **-0.639** (complete OOS failure)
  - **Split-half**: Correlation **-0.031** (zero persistence). H1 mean -1.094, H2 mean 0.917. Extreme asymmetry.
  - **WF selected (4 folds)**: 3/4 positive, mean 1.492 (but IS data selects long lookback=60 which captures size, not stability)
  - **Corr with H-012**: -0.270. **Corr with H-031 (size)**: 0.073.
- Notes: Factor fundamentally doesn't work. Volume stability in crypto is mostly a proxy for size/maturity, and the pure CV measure is too noisy. The WF param selection results are misleading — the folds select LB=60 consistently which captures long-term volume patterns (basically size). Strategy file: `strategies/h102_vol_stability/backtest.py`.
- Sessions: [2026-03-27 backtest session 98]

## H-103: Price-Volume Correlation Factor (14 Assets)
- Status: REJECTED — IS overfitting, OOS failure
- Idea: Rank assets by rolling correlation between daily returns and daily volume changes. Long highest corr (conviction buying = price up + volume up), short lowest corr (weak moves).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Rolling Pearson correlation between returns and volume changes (20-60d window). Conviction direction: long high corr, short low. Also tested contrarian direction.
- Result:
  - **Param scan (48 combos)**: **75% positive** (36/48). Mean Sharpe 0.297. Best 1.025.
  - **Direction test**: Conviction (75% positive, mean 0.297) beats Contrarian (40% positive, mean -0.057).
  - **Train/test**: IS 1.410 → OOS **-0.519** (severe OOS failure — classic overfit)
  - **Split-half**: Correlation 0.408 (moderate). H1 0.209, H2 0.243. Consistent but low.
  - **WF selected (4 folds)**: **2/4 positive**, mean **-0.110** (negative OOS)
  - **Corr with H-012**: 0.428 (moderate — partially captures momentum via conviction). **Corr with H-021**: 0.155.
- Notes: The conviction direction has some IS alpha but it doesn't persist OOS. Correlation 0.428 with H-012 suggests it partially captures momentum (strong conviction moves are trending moves). Not genuinely independent. Strategy file: `strategies/h103_pv_correlation/backtest.py`.
- Sessions: [2026-03-27 backtest session 98]

## H-104: RSI Cross-Sectional Mean Reversion (14 Assets)
- Status: REJECTED — only 3% params positive, mean Sharpe -0.66
- Idea: Rank 14 assets by RSI. Go long most oversold (lowest RSI), short most overbought (highest RSI). Cross-sectional mean reversion.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Compute RSI over lookback, rank cross-sectionally. Long bottom-N (oversold), short top-N (overbought). Equal-weight, dollar-neutral. Tested 36 combos: RSI lookback [7,14,21], rebal [3,5,7,10]d, N [3,4,5].
- Result:
  - **Param scan (36 combos)**: **3% positive** (1/36). Mean Sharpe -0.656. Best RSI7_R10_N3 Sharpe 0.181.
  - **IS/OOS (60/40)**: Best IS Sharpe 0.778 → OOS Sharpe **-0.398**, mean OOS Sharpe -1.010.
  - **Walk-forward (4 folds)**: Mean OOS Sharpe **-2.017**. All folds negative: [-3.10, -0.98, -2.04, -1.95].
  - **Split-half**: Mean H1 -0.794, Mean H2 -0.727. Corr **-0.291** (negative — inconsistent even in failure).
  - **Fee sensitivity**: Best Sharpe 0.181 at 1x fees → -0.061 at 5x fees.
  - **Corr H-012**: -0.393 (anti-correlated with momentum — expected since RSI MR is inverse of momentum)
  - **Corr H-019**: -0.087 (low)
- Notes: Cross-sectional mean reversion conclusively doesn't work in crypto. Crypto is momentum-driven — assets that are "overbought" continue rising, "oversold" continue falling. The -0.393 correlation with H-012 confirms RSI MR is simply the wrong side of momentum. Only 1/36 params positive. Dead end — do not revisit.
- Sessions: [2026-03-28 backtest session 99]

## H-105: Close Location Value (CLV) Momentum Quality Factor (14 Assets)
- Status: REJECTED — regime-dependent (split-half correlation negative)
- Idea: CLV = (close - low) / (high - low) measures where close falls within daily range. Assets consistently closing near highs have strong buying pressure. Cross-sectional: long highest avg-CLV, short lowest.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Compute daily CLV, roll over N days, rank cross-sectionally. Long top-N, short bottom-N. Equal-weight. Dollar-neutral. Tested 36 combos: CLV lookback [5,10,20,30], rebal [3,5,7]d, N [3,4,5].
- Result:
  - **Param scan (36 combos)**: **78% positive** (28/36). Mean Sharpe 0.385, Median 0.569. Best LB20_R5_N5 Sharpe 1.428, +71.1% ann, 36.5% DD. Strong cluster around LB=20.
  - **IS/OOS (60/40)**: IS Sharpe 1.148 → OOS Sharpe **2.005**, OOS Ann 97.3%, OOS DD 19.0%. Unusually strong OOS (suspect regime).
  - **Walk-forward (4 folds)**: 3/4 positive, mean 0.762. Fold Sharpes: [0.685, 2.159, 1.755, **-1.549**]. Fold 4 (Oct-Dec 2025) severely negative.
  - **Split-half OOS**: H1 (Jun-Oct 2025) Sharpe 2.556 vs H2 (Nov 2025-Mar 2026) Sharpe 1.385 with best params. Cross-param correlation **-0.187** — regime-dependent, strategy works differently in different halves.
  - **Fee sensitivity**: Sharpe 1.356 at 1x fees → 1.126 at 5x fees. Robust to fees.
  - **Corr H-012 (60d momentum)**: **0.343** (moderate — CLV captures some momentum premium)
  - **Corr H-019 (20d vol)**: 0.175 (low)
- Notes: Interesting factor with clear directional logic. Short lookback (LB=5) completely fails (worst Sharpe -2.07) — likely noise. LB=20 is the sweet spot. The OOS number (2.0) looks great but is inflated by a very strong H1 2025 regime. WF fold 4 (Oct-Dec 2025) severely negative (-1.549) and split-half correlation is negative — the factor changes sign between regimes. The signal likely captures "momentum quality" in trending markets and reverses when momentum reverses (Oct-Dec 2025 was a drawdown period). Corr 0.343 with H-012 means it is partially redundant. Strategy file: `strategies/h105_close_location/backtest.py`.
- Sessions: [2026-03-28 backtest session 99]

## H-106: Volume Profile Skewness Factor (14 Assets)
- Status: REJECTED — OOS Sharpe negative (-0.122), split-half correlation near zero (0.014)
- Idea: Rank assets by rolling skewness of daily trading volume. High positive skew = occasional large volume spikes (institutional/event-driven). Cross-sectional: test both momentum (long high skew) and contrarian (long low skew) directions.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Rolling scipy skewness of daily volume over [10,20,30,60]d windows. Rebal every [5,7,10]d. Long/short top/bottom [3,4,5] by skew rank. Equal-weight, dollar-neutral. 36 combos per direction, 72 total.
- Result:
  - **Direction**: CONTRARIAN strongly dominates (97% positive Sharpe vs only 8% for momentum direction). Momentum direction fails comprehensively — volume spikes signal exhaustion, not smart money.
  - **Param scan (contrarian, 36 combos)**: **97% positive** (35/36). Mean Sharpe 0.935, Best LB10_R7_N4 Sharpe 1.792, +70.6% ann, 32.8% DD on full period.
  - **IS/OOS (60/40 split)**: IS Sharpe 1.523 → OOS Sharpe **-0.122**, OOS Ann -7.3%, OOS DD 19.4%. Severe in-sample/out-of-sample degradation.
  - **OOS split-half**: H1 (Jun-Oct 2025) Sharpe -0.203, H2 (Nov 2025-Mar 2026) Sharpe 1.139. Very inconsistent.
  - **Split-half cross-param correlation**: **0.014** (essentially zero — no consistency across halves).
  - **Walk-forward (4 folds, IS param selection)**: 2/4 positive, mean OOS 0.931 — misleading because fold variation is extreme ([-0.360, 2.309, -0.106, 1.883]).
  - **Corr H-012 (XS momentum)**: 0.068 (low — independent signal)
  - **Corr H-031 (size)**: 0.150 (low)
- Notes: Contrarian direction (short high-skew, long low-skew) has very strong full-period performance but completely fails OOS validation. The strategy appears to capture a regime-specific effect — likely worked extremely well in late 2024/early 2025 but the relationship breaks down in 2025-2026. Split-half correlation of 0.014 is the smoking gun: the param ranking in H1 and H2 are essentially uncorrelated, meaning there is no persistent structure. Volume skewness is not a stable cross-sectional factor. The contrarian intuition (volume spikes = exhaustion) has merit but is too regime-dependent to be reliably exploitable. Strategy file: `strategies/h106_vol_skew/backtest.py`.
- Sessions: [2026-03-28 backtest session 99]

## H-107: Range Compression Factor (14 Assets)
- Status: REJECTED — only 1% params positive, mean Sharpe -0.844
- Idea: Rank assets by ATR ratio (short ATR / long ATR). Low ratio = compressed range (coiling for breakout). Cross-sectional: long compressed, short expanded.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: ATR_short / ATR_long ratio. Short windows [5,7,10], long windows [20,30,40,60], rebal [3,5,7], N [3,4]. 72 combos.
- Result:
  - **Param scan**: 1/72 positive (1.4%). Mean Sharpe **-0.844**. Best S10_L30_R7_N3 Sharpe 0.094.
  - **OOS**: Sharpe -0.230, Ann -16.6%, DD 38.0%.
  - **Walk-forward**: 2/4 positive, mean OOS -0.506.
  - **Split-half**: corr 0.243. H1 mean -1.885, H2 mean 0.648.
  - **Corr H-012**: -0.377. **Corr H-019**: 0.044.
- Notes: Comprehensive failure. Compressed ranges do NOT predict cross-sectional outperformance. The reverse direction (long expanded) would have mean Sharpe ~+0.8 but with terrible split-half consistency, suggesting this is noise. Range dynamics don't generate a stable cross-sectional signal in crypto.
- Sessions: [2026-03-28 backtest session 100]

## H-108: Overnight Gap Factor (14 Assets)
- Status: REJECTED — split-half corr -0.487, |corr H-019| = 0.515
- Idea: Rank assets by average overnight gap (Open_t / Close_{t-1} - 1). Positive gaps = overnight demand. Cross-sectional: long positive gaps, short negative gaps.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Rolling mean of daily gap over [5,10,20,30]d. Rebal [3,5,7]. N [3,4]. 24 combos.
- Result:
  - **Param scan**: **100% positive** (24/24). Mean Sharpe **2.367**. Best L10_R3_N4 Sharpe 2.464.
  - **OOS (IS-selected)**: Sharpe **1.698**, Ann +86.7%, DD 22.7%. Very strong.
  - **Walk-forward**: **4/4 positive**, mean OOS **2.272**. Excellent.
  - **Split-half**: corr **-0.487** (FAIL). H1 mean 1.933, H2 mean 2.701 — both positive but param ranking inverts.
  - **Fee sensitivity**: Nearly zero impact (Sharpe 2.464 → 2.461 at 5x fees).
  - **Corr H-012**: 0.421. **Corr H-019**: **-0.515** (FAIL, >0.5).
- Notes: Extremely strong metrics — 100% positive, WF 4/4, OOS 1.698 — but REJECTED on two criteria: (1) split-half param correlation -0.487 means the best params in one half are worst in the other (regime-dependent), (2) corr -0.515 with H-019 means it captures the inverse of the low-vol signal (anti-low-vol factor). The signal is real but parameter-unstable and partially redundant. Consider revisiting if a fixed-param version (no selection) performs well.
- Sessions: [2026-03-28 backtest session 100]

## H-109: Short-Term Reversal Factor (14 Assets)
- Status: REJECTED — split-half corr -0.443, OOS Sharpe -0.199
- Idea: Rank assets by very short-term (1-5 day) return. Go LONG biggest losers, SHORT biggest winners. Tests whether short-term reversal exists in crypto at very short horizons.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Simple return over [1,2,3,5]d. Reversal direction (long losers). Rebal [1,2,3,5]d. N [3,4,5]. 48 combos.
- Result:
  - **Param scan**: **75% positive** (36/48). Mean Sharpe 0.353. Best L5_R3_N4 Sharpe 1.171.
  - **OOS (IS-selected)**: Sharpe **-0.199**, Ann -11.2%, DD 21.0%. IS params don't transfer.
  - **Walk-forward**: 3/4 positive, mean OOS 0.617 — decent but IS-selected fails.
  - **Split-half**: corr **-0.443** (FAIL). H1 mean 0.245, H2 mean 0.247 — both positive but param ranking inverts.
  - **Fee sensitivity**: Sharpe 0.961 → 0.341 at 5x fees (high turnover).
  - **Corr H-012**: **-0.086** (near zero, slightly negative = genuine reversal signal). **Corr H-019**: 0.003 (independent).
- Notes: Short-term reversal EXISTS weakly in crypto (75% positive, WF 3/4, slightly negative corr with momentum). This is a genuine reversal effect, not disguised momentum. But it's parameter-unstable (split-half -0.443) — the optimal lookback/rebalance combo shifts between regimes. Also fee-sensitive due to high turnover. The signal is too fragile to deploy. If a no-selection fixed-param approach (e.g., always L3_R3_N4) showed consistent performance, might be worth revisiting.
- Sessions: [2026-03-28 backtest session 100]

## H-110: Return Skewness Factor (14 Assets)
- Status: REJECTED — param robustness 25%, split-half corr -0.031, WF mean OOS Sharpe -0.515
- Idea: Cross-sectional skewness factor. Positively-skewed assets are overpriced (lottery preference); negatively-skewed are underpriced. Long most neg-skew, short most pos-skew.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Rolling return skewness (scipy stats.skew) over [20,30,40,60]d. Sort ascending → long lowest (most negative), short highest (most positive). Rebal [3,5,7,10]d. N [3,4,5]. 48 combos.
- Result:
  - **Param scan**: Only **25% positive** (12/48). Mean Sharpe -0.369. Best S30_R5_N3 Sharpe 0.319.
  - **Walk-forward (6-fold)**: 3/5 positive, mean OOS Sharpe **-0.515**. Folds 4 and 5 catastrophic (-1.586, -3.089) — strategy reversed in mid-2024 to mid-2025.
  - **Split-half**: corr **-0.031** (FAIL). H1 mean -1.115, H2 mean +0.763 — signal works in 2025-2026 but fails badly in 2024-2025. Complete regime flip.
  - **Fee sensitivity (1x=0.1% taker)**: Best-param Sharpe 0.319 (below 0.5 threshold).
  - **Corr H-012**: **-0.341** (negative — anti-correlated with momentum, independent).
  - Fee degradation: 0.423→0.319 at 1x→ negative at 5x. Fee-sensitive.
- Notes: Skewness factor is **strongly regime-dependent** in crypto. In 2025-2026 (BTC recovery/consolidation) the anti-lottery effect worked. In 2024-2025 (bull run / altcoin mania) the opposite was true — lottery assets outperformed. The signal completely reverses depending on market phase. Academic finance result does not transfer robustly to crypto cross-section over 2-year horizon. S60 (long-window) was 0% positive, confirming skewness as a noisy signal in crypto. The split-half regime flip is the decisive rejection criterion.
- Sessions: [2026-03-28 backtest session 101]

## H-111: Directional Volume Imbalance Factor
- Status: REJECTED — split-half corr 0.009, OOS Sharpe -0.613
- Idea: Cross-sectional factor: rolling up-volume ratio (vol on up-days / total vol). Long accumulators, short distributors.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Up-day = close > open (or close > prev_close — both identical in this dataset). Rolling up-vol ratio over [10,20,30,40]d. Rebal [3,5,7,10]d. N [3,4,5]. 48 combos.
- Result:
  - **Param scan**: **92% positive** (44/48). Mean Sharpe **0.489**. Best L40_R7_N3 Sharpe **1.457**, Ann +64.8%, DD 23.4%.
  - **Walk-forward OOS** (6-fold rolling 60/40): **2/5 positive**, mean OOS Sharpe **-0.613** (FAIL). IS 2.257 → OOS -0.613 — severe IS→OOS degradation.
  - **Split-half**: corr **0.009** (FAIL, near zero). H1 mean 0.106, H2 mean 1.100 — factor essentially non-existent in first half (2024), strong in second (2025). Pure regime concentration.
  - **Fee sensitivity**: Very robust (Sharpe 1.535 → 1.147 at 50 bps). Fee is not the issue.
  - **Corr H-012**: 0.455 (OK, independent). **Corr H-021**: -0.019 (OK, independent).
- Notes: Strong IS metrics (92% positive, best Sharpe 1.457) but collapses on both OOS tests. The factor only worked in 2025 bull/accumulation regime — essentially H1 Sharpe 0.106 vs H2 1.100. The up-volume ratio captures accumulation/distribution signal that existed during the 2025 crypto rally but was absent in the more volatile 2024 period. Not stable enough to deploy. Both up-day definitions (close>open vs close>prev_close) yielded identical results — they're effectively the same signal in this dataset.
- Sessions: [2026-03-28 backtest session 101]

## H-112: Downside Beta Factor (14 Assets)
- Status: REJECTED — split-half corr -0.455, WF OOS mean 0.418, redundant with H-024 (corr 0.662)
- Idea: Asymmetric beta using only BTC down days. Long low downside-beta (defensive assets that don't crash with BTC), short high downside-beta (fragile).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Rolling downside beta = cov(asset_ret, btc_ret | btc_ret<0) / var(btc_ret | btc_ret<0) over lookback. Rank cross-sectionally. Long bottom-N, short top-N. Equal-weight, market-neutral.
- Result:
  - **Param scan**: **100% positive** (48/48). Mean Sharpe **1.127**, Median **1.106**. Best L90_R14_N3 Sharpe **1.950**, Ann 114%, DD 32.6%.
  - **Walk-forward OOS** (6-fold rolling 60/40): **4/6 positive**, mean OOS Sharpe **0.418** (borderline FAIL). Unstable: fold 1 -2.539, fold 3 +2.453. High IS→OOS variance.
  - **Split-half**: corr **-0.455** (FAIL). Both halves positive (H1 mean 1.360, H2 mean 1.233) but ranking across params is reversed — the params that work in H1 fail in H2.
  - **Fee sensitivity**: Very robust — Sharpe 1.974 (0 fee) to 1.852 (5x fee). Low turnover (47 rebals over 2yr at best params).
  - **Corr H-019 (low-vol)**: **0.459** (borderline, just under 0.5 — nearly redundant). **Corr H-024 (regular beta)**: **0.662** — REDUNDANT. Downside beta is just noisier regular beta.
  - **Checks passed**: 4/7. REJECTED.
- Notes: Conceptually appealing (downside beta is theoretically superior risk measure) but in practice it is a noisier version of regular beta (H-024, corr 0.662). BTC has ~50% down days, so downside beta windows overlap heavily with full beta. The signal degrades in WF because: (a) short-term windows have too few down-days for stable estimation, (b) the cross-sectional ranking is regime-dependent. Not distinct enough from H-024 to justify.
- Sessions: [2026-03-28 backtest session 101]

## H-113: Funding-Adjusted Momentum (14 Assets)
- Status: REJECTED — corr 0.995 with H-012 (identical to raw momentum), split-half 0.156, WF 2/5 positive
- Idea: Rank by N-day price return minus cumulative N-day funding cost. Penalises momentum driven by crowded trades with high funding costs.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Signal = pct_change(lookback) - rolling_sum(daily_funding, lookback). Long top-N (best carry-adjusted mom), short bottom-N. Equal-weight, market-neutral.
- Result:
  - **Param scan**: **100% positive** (48/48). Mean Sharpe **0.898**, Best L90_R7_N4 Sharpe **1.502**, Ann 68.8%, DD 20.1%.
  - **Walk-forward OOS**: **2/5 positive**, mean OOS Sharpe **0.109** (FAIL).
  - **Split-half**: corr **0.156** (FAIL). H1 mean 1.346, H2 mean 0.281 — massive decay.
  - **Corr H-012 (momentum)**: **0.995** — IDENTICAL. Funding adjustment is negligible.
  - **Corr H-053 (funding XS)**: -0.060 (independent from funding, but identical to momentum).
  - **Checks passed**: 1/5. REJECTED.
- Notes: Funding rates are tiny relative to price returns (bps vs %). The carry adjustment barely changes the ranking. In traditional finance, carry matters because rates are comparable to returns. In crypto, funding is noise. Waste of complexity.
- Sessions: [2026-03-28 backtest session 102]

## H-114: Gain/Loss Ratio Factor (14 Assets)
- Status: REJECTED — split-half -0.535 in H2, regime-dependent signal
- Idea: Rank by avg(positive returns) / avg(|negative returns|) over N days. Assets with asymmetric upside go long.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: G/L ratio = mean(gains) / mean(|losses|) over rolling lookback. Long top-N (high G/L), short bottom-N. Equal-weight, market-neutral.
- Result:
  - **Param scan**: **89.6% positive** (43/48). Mean Sharpe **0.452**, Best L60_R10_N3 Sharpe **1.071**, Ann 43.2%, DD 31.3%.
  - **Walk-forward OOS**: **3/5 positive**, mean OOS Sharpe **0.636** (borderline OK).
  - **Split-half**: corr **0.290** (FAIL). H1 mean 0.904, H2 mean **-0.535** — signal reverses in second half.
  - **Corr H-012 (momentum)**: **0.491** (moderate — partially independent but captures similar directional information).
  - **Checks passed**: 2/5. REJECTED.
- Notes: G/L ratio is capturing a noisy version of momentum through a different lens (asymmetric returns tend to come from trending assets). The regime-dependence (signal reverses H2) means it's unreliable for production. Different from skewness (H-110) but shares the same failure mode: the cross-sectional ranking of G/L ratios is unstable across time.
- Sessions: [2026-03-28 backtest session 102]

## H-115: Autocorrelation Factor (14 Assets)
- Status: REJECTED — WF 0/5 positive (OOS -0.591), split-half 0.015, only 62.5% IS positive
- Idea: Rank by lag-1 autocorrelation of daily returns. Long trending assets (positive AC), short mean-reverting (negative AC).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Rolling lag-1 autocorrelation of daily returns over lookback window. Long top-N (highest AC, trending), short bottom-N. Equal-weight, market-neutral.
- Result:
  - **Param scan**: **62.5% positive** (30/48). Mean Sharpe **0.123** (very weak), Best L30_R14_N4 Sharpe **0.813**, Ann 26.2%, DD 25.1%.
  - **Walk-forward OOS**: **0/5 positive** (FAIL), mean OOS Sharpe **-0.591**. Every fold negative.
  - **Split-half**: corr **0.015** (FAIL — random). H1 mean 0.160, H2 mean 0.357 — both weak.
  - **Corr H-012 (momentum)**: **0.244** (low — genuinely different signal, but a useless one).
  - **Checks passed**: 0/5. REJECTED.
- Notes: Lag-1 autocorrelation in crypto daily returns is essentially noise. Crypto markets are efficient enough at the daily level that serial correlation doesn't provide cross-sectional predictive power. The concept is theoretically appealing ("trendability") but fails in practice because autocorrelation estimates from 20-60 days of daily data are extremely noisy (each estimate uses <60 data points for a correlation coefficient).
- Sessions: [2026-03-28 backtest session 102]

## H-116: Hurst Exponent Factor (14 Assets)
- Status: REJECTED (resolved session 134) — was CONDITIONAL but H-172 and H-206 bug analysis showed signal is implementation-dependent and split-half unstable at LB=60
- Idea: Rank by rolling Hurst exponent (R/S method). Long trending assets (H > 0.5), short mean-reverting (H < 0.5). Captures intrinsic trending tendency independent of return magnitude.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Estimate Hurst exponent via rescaled range (R/S) method over rolling lookback. Long top-N (highest Hurst, strongest trending propensity), short bottom-N. Equal-weight, market-neutral.
- Result:
  - **Param scan**: **95.8% positive** (46/48). Mean Sharpe **0.735**, Best L80_R10_N4 Sharpe **1.863**, Ann 84.3%, DD 23.0%.
  - **Walk-forward OOS**: **4/5 positive**, mean OOS Sharpe **1.718** (excellent). Fold 2 barely negative (-0.043), rest strong (1.257, 2.918, 1.630, 2.829).
  - **Split-half**: corr **0.332** (moderate). H1 mean 0.858, H2 mean 0.546 — some degradation but both halves solidly positive.
  - **Corr H-012 (momentum)**: **0.238** — low overlap, genuinely different signal.
  - **Top params**: All favor 80d lookback (longer windows give more stable Hurst estimates). R10 rebalance, N3-N4.
  - **Checks passed**: 4/5.
- Notes: Hurst exponent measures multi-scale persistence — conceptually richer than lag-1 autocorrelation (H-115, rejected). The R/S method uses multiple block sizes to estimate trending propensity. Low H-012 correlation (0.238) confirms this captures trend *quality* not trend *direction*. Split-half 0.332 is moderate — not failing but not excellent. H2 degradation (0.858→0.546) suggests some signal decay but still meaningful. Top params strongly favor 80d lookback (shorter lookbacks give noisier Hurst estimates). 746 days of data = ~9 Hurst windows at 80d. Strategy file: `strategies/h116_hurst/backtest.py`.
- Sessions: [2026-03-28 backtest session 103]

## H-117: Information Ratio Factor (14 Assets)
- Status: REJECTED — split-half H2 mean 0.029 (collapses in recent data), corr 0.491 with H-012
- Idea: Rank by rolling information ratio (mean return / std return). Long best risk-adjusted performers, short worst. Composite of momentum + low-vol.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Rolling mean(daily return) / std(daily return) over lookback. Long top-N (highest IR), short bottom-N. Equal-weight, market-neutral.
- Result:
  - **Param scan**: **91.7% positive** (44/48). Mean Sharpe **0.629**, Best L20_R5_N3 Sharpe **1.590**, Ann 87.1%, DD 24.0%.
  - **Walk-forward OOS**: **5/5 positive**, mean OOS Sharpe **1.322**. Folds: 3.030, 0.633, 1.095, 1.362, 0.492.
  - **Split-half**: corr **0.160** (FAIL). H1 mean **0.986**, H2 mean **0.029** — signal collapses in second half.
  - **Corr H-012 (momentum)**: **0.491** — moderate overlap (captures similar directional signal through vol-adjusted lens).
  - **Checks passed**: 2/5. REJECTED.
- Notes: Information ratio = return/vol is a composite signal. The WF 5/5 looks excellent but is misleading — the signal is front-loaded to the first half of data (H1 mean 0.986 vs H2 mean 0.029). The composite doesn't add value beyond raw momentum (corr 0.49) and in fact degrades faster. In crypto where vol is high everywhere, normalizing by vol just adds noise. Strategy file: `strategies/h117_info_ratio/backtest.py`.
- Sessions: [2026-03-28 backtest session 103]

## H-118: Volume-Price Confirmation (OBV Trend) Factor (14 Assets)
- Status: REJECTED — split-half corr -0.509 (signal inverts), WF 3/5 positive
- Idea: Rank by rolling correlation between OBV (on-balance volume) and price. High corr = volume confirms price trend (long), low corr = divergence (short).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Compute OBV (cumulative signed volume), then rolling correlation(OBV, price) over lookback window. Long top-N (highest vol-price confirmation), short bottom-N. Equal-weight, market-neutral.
- Result:
  - **Param scan**: **100% positive** (48/48). Mean Sharpe **0.913**, Best L20_R5_N4 Sharpe **1.539**, Ann 55.8%, DD 30.5%.
  - **Walk-forward OOS**: **3/5 positive**, mean OOS Sharpe **0.716**. Very inconsistent: folds 2.444, 0.157, -0.549, -1.396, 2.925.
  - **Split-half**: corr **-0.509** (FAIL). H1 mean 0.424, H2 mean 1.472 — signal exists in both halves but params that work in one INVERT in the other.
  - **Corr H-012 (momentum)**: **0.066** — near zero, excellent diversification potential.
  - **Checks passed**: 2/5. REJECTED.
- Notes: OBV-price correlation is a genuinely novel signal with near-zero H-012 correlation (0.066). 100% IS positive and the raw signal clearly exists. But the parameter instability (split-half -0.509) kills it — you can't pick stable params. The OBV-price relationship likely shifts with regime: in trending markets, all assets show high OBV-price corr (long everything works), in choppy markets the relationship breaks. This is more of a regime indicator than a cross-sectional factor. Strategy file: `strategies/h118_obv_trend/backtest.py`.
- Sessions: [2026-03-28 backtest session 103]

## H-119: Amihud Illiquidity Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by Amihud illiquidity ratio (|return| / dollar_volume). LONG low illiquidity (most liquid), SHORT high illiquidity.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Rolling mean of |daily_return| / dollar_volume over lookback window. Cross-sectional ranking. Liquidity premium in crypto.
- Data: 14 assets, ~746 daily bars (2yr). 48 param combos (lookback [10,20,30,60] x rebal [5,7,10,14] x N [3,4,5]).
- Result:
  - **IS**: 100% positive (48/48), mean Sharpe **2.099**, best L20_R14_N4 Sharpe 2.375, +175.5% ann, 25.1% DD
  - **Walk-forward**: Only **2/2** folds evaluated (data limitation), both positive, mean OOS **1.368**
  - **Split-half**: corr **-0.622** — parameter ranking inverts between halves
  - **Correlation with H-012**: 0.431 — moderate overlap with momentum
- Notes: Extremely strong IS results with 100% positive and mean Sharpe >2. But split-half -0.622 is a dealbreaker — the best params in half 1 are the worst in half 2, making forward param selection unreliable. Only 2 WF folds (insufficient). Corr 0.431 with momentum means partial redundancy. The Amihud ratio likely captures size/liquidity effect (similar to H-031) through a different lens. Strategy file: `strategies/h119_amihud/backtest.py`.
- Sessions: [2026-03-28 backtest session 104]

## H-120: Relative Volume Spike Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by volume expansion ratio (short_avg_volume / long_avg_volume). LONG high ratio (volume expanding), SHORT low ratio (contracting). Pure volume signal without price direction.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: volume_ratio = rolling_mean(volume, short_window) / rolling_mean(volume, long_window). Cross-sectional ranking. Different from H-021 (vol momentum) which includes price direction.
- Data: 14 assets, 746 daily bars (2yr). 108 param combos.
- Result:
  - **IS**: 100% positive (108/108), mean Sharpe **1.171**, best S5_L30_R10_N5 Sharpe 2.029
  - **Walk-forward**: **0/2** positive, mean OOS **-2.916** — catastrophic OOS failure
  - **Split-half**: corr **-0.307** — parameter instability
  - **Correlation with H-012**: 0.101 — nearly independent (good)
- Notes: Classic overfitting case. 100% IS positive but WF OOS is catastrophically negative (-2.916). The volume expansion signal is too noisy cross-sectionally — volume spikes are often idiosyncratic (news, listings, etc.) and don't predict cross-sectional returns. Low H-012 correlation is the only positive. Strategy file: `strategies/h120_rel_volume/backtest.py`.
- Sessions: [2026-03-28 backtest session 104]

## H-121: Distance from VWAP Factor (14 Assets)
- Status: CONDITIONAL
- Idea: Rank assets by deviation from rolling VWAP. LONG assets above VWAP (strong demand), SHORT below VWAP (weak demand).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: vwap_deviation = (close - rolling_vwap) / rolling_vwap. Cross-sectional ranking. Captures momentum through volume-weighted fair value lens.
- Data: 14 assets, ~746 daily bars (2yr). 48 param combos (VWAP lookback [10,20,30,60] x rebal [5,7,10,14] x N [3,4,5]).
- Result:
  - **IS**: 91.7% positive (44/48), mean Sharpe **0.846**, best L10_R14_N3 Sharpe 1.766
  - **Walk-forward**: **4/6** positive, mean OOS **0.712** — decent
  - **Split-half**: corr **0.366** — moderate stability (positive)
  - **Correlation with H-012**: 0.388 — moderate overlap with momentum
- Notes: Decent WF (4/6 positive, mean 0.712) and positive split-half (0.366) make this the best of the three. But 91.7% IS positive is not as strong as 100%, and corr 0.388 with H-012 means partial momentum redundancy. Best params favor short lookback (10d) and long rebal (14d), suggesting it captures short-term deviation from fair value. Max DD 39.8% is high. Could be useful in a portfolio context but not compelling enough for immediate paper trading. Strategy file: `strategies/h121_vwap_dev/backtest.py`.
- Sessions: [2026-03-28 backtest session 104]

## H-122: Candle Conviction Factor (14 Assets)
- Status: REJECTED
- Idea: Cross-sectional ranking by average candle body ratio |close-open|/(high-low). Long high conviction (clean moves), short low conviction (wicky candles).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-10 days)
- Logic: Rolling mean body ratio over 10-60d lookback. Rank cross-sectionally, long top N, short bottom N.
- Result: IS **0% positive** (all 60 params negative!). Mean Sharpe -1.189. WF **1/6** positive. Split-half 0.046. Corr H-012 -0.152.
- Notes: Signal works in REVERSE — low conviction candles lead to outperformance, high conviction candles mean-revert. Crypto "clean moves" are exhaustion signals. Data: 746 days, 14 assets.
- Sessions: [2026-03-28 session 105]

## H-123: Volume-Price Elasticity Factor (14 Assets)
- Status: REJECTED
- Idea: Regression slope of |return| on log(volume) measures price-volume responsiveness. Cross-sectional: long high elasticity, short low.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-10 days)
- Logic: Rolling OLS of |log_return| on log(volume) over 15-60d. Take beta as elasticity, rank cross-sectionally.
- Result: IS 23.3% positive (14/60). Best Sharpe 0.385 (W15_R10_N4). WF **1/6** positive (mean OOS -1.354). Split-half 0.137. Corr H-012 0.052.
- Notes: Very noisy signal, strong training performance collapses OOS. Volume-price relationship is too unstable for cross-sectional factor. Data: 746 days, 14 assets, 60 param combos.
- Sessions: [2026-03-28 session 105]

## H-124: Close Location Value Factor (14 Assets, Revisited)
- Status: REJECTED
- Idea: CLV = (close-low)/(high-low). Average over lookback, rank cross-sectionally. Tested both momentum (long high CLV) and contrarian (long low CLV) directions.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-10 days)
- Logic: Rolling mean CLV. Momentum: long top N (closes near high), short bottom N. Contrarian: reverse.
- Result: Overall IS 46.5% positive (67/144). **Momentum: 84.7% positive** (61/72). Contrarian: 8.3% positive (6/72). Split-half 0.621. Corr H-012 **0.448** (moderate overlap).
- Notes: CLV momentum is real but overlaps with price momentum (H-012). Closes near high → continued rise is just another way to capture momentum. Confirms H-105 finding (split-half now 0.621 vs -0.19, but added momentum overlap wasn't tested before). Data: 746 days, 14 assets, 144 param combos (72 per direction).
- Sessions: [2026-03-28 session 105]

## H-125: Wick Ratio Factor (14 Assets)
- Status: REJECTED
- Idea: Wick ratio = 1 - |close-open|/(high-low). Measures candle indecision vs conviction. Rank cross-sectionally, tested both conviction_long and indecision_long.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Rolling mean wick ratio over lookback. conviction_long: long low-wick (decisive), short high-wick. indecision_long: reverse.
- Result: IS **50.0%** positive (36/72). Indecision_long 77.8% positive (28/36). Best L=5,R=5,N=5 indecision_long Sharpe 1.039. **OOS Sharpe -1.551** (fails). Split-half **0.898** (good). WF **4/6** positive mean 0.588. Corr H-012 **0.051** (novel).
- Notes: The indecision_long direction is counterintuitive — coins with more wicks outperform. WF is decent but OOS on best params fails badly. Direction unstable (fold 5 picks conviction_long). Only 50% IS positive is barely random. Data: 746 days, 14 assets, 72 param combos.
- Sessions: [2026-03-29 session 106]

## H-126: Return Consistency Factor (14 Assets)
- Status: REJECTED
- Idea: Fraction of positive return days over lookback period. Rank cross-sectionally. consistent_long: long most-consistent winners.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Rolling fraction of positive-return days. consistent_long: long high consistency, short low. inconsistent_long: reverse.
- Result: IS **50.0%** positive (36/72). consistent_long 61.1% (22/36). Best L=30,R=7,N=3 consistent_long Sharpe 1.189. **OOS Sharpe -1.662** (fails). Split-half 0.754. WF **3/6** positive mean **-0.247** (negative). Corr H-012 0.235 (moderate overlap).
- Notes: Just a noisier version of momentum. Positive return days over 30-day lookback correlates 0.235 with 60-day momentum. WF direction instability (3 folds pick consistent, 2 pick inconsistent, 1 consistent). No edge. Data: 746 days, 14 assets, 72 param combos.
- Sessions: [2026-03-29 session 106]

## H-127: Volume-Price Divergence Factor (14 Assets)
- Status: REJECTED
- Idea: Divergence between volume-weighted returns and equal-weighted returns. When vol-weighted > equal-weighted, large-volume moves are positive ("smart money buying").
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-10 days)
- Logic: div = rolling_mean(vw_ret - ew_ret, L). Cross-sectionally z-scored. div_long: long high divergence, short low.
- Result: IS 50% overall but **div_long 95.8%** positive (46/48), conv_long 4.2%. Best L=20,R=7,N=4 div_long Sharpe **2.354**, +45.2%, 10.0% DD (strong IS). OOS Sharpe **0.682** (positive but degraded). Split-half 0.704. WF **2/6** positive mean **-0.007** (fails). Corr H-012 **0.372** (moderate overlap).
- Notes: Very strong IS for div_long direction, but WF completely fails (only 2/6 positive). Direction instability: WF picks conv_long in 2 folds. This is regime-dependent overfitting — the vol-weighted signal captures momentum-like behavior (corr 0.372) but without stability across time. Data: 746 days, 14 assets, 96 param combos.
- Sessions: [2026-03-29 session 106]

## H-128: Dollar Volume Velocity Factor (Rate of Change in DV)
- Status: REJECTED
- Idea: Rank 14 crypto assets by rate of change in dollar volume (price*volume). Assets with accelerating DV flow → long. Captures momentum in market participation.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-10 days)
- Logic: dv_velocity = short_mean(close*vol) / long_mean(close*vol) - 1. Cross-sectional rank, long top N, short bottom N.
- Result: IS 48.6% overall positive (**long_accel 97.2%**, long_decel 0%). Best S5_L30_R10_N4 long_accel Sharpe **1.908**, +110% ann, 23.3% DD. WF **3/6** positive, mean OOS **-1.161**. Split-half **-0.243**. Corr H-012 **0.21**, H-031 N/A.
- Notes: Strong IS for long_accel direction but fails OOS validation badly. WF fold 0 selected decel direction (-7.05 OOS), fold 1 NaN. Classic overfitting: strong in-sample, collapses out-of-sample. Data: 746 days, 14 assets, 144 param combos.
- Sessions: [2026-03-29 session 107]

## H-129: Intraday Volatility Ratio Factor (Parkinson/CC Vol Ratio)
- Status: REJECTED
- Idea: Ratio of Parkinson (high-low range) vol to close-close vol captures information content of price bars. High ratio = noise, low ratio = clean trend.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: parkinson_vol / cc_vol over lookback window. Cross-sectional rank. Test both long_low_ratio and long_high_ratio.
- Result: IS **50%** positive (need ≥80%). Best L20_R7_N3_LH Sharpe **1.424**, +75.6% ann, 28.7% DD. OOS Sharpe **-0.289**. WF **4/6** positive but mean OOS **0.057** (noise). Split-half **-0.817** (signal inverts). Corr H-076 **0.091**, H-012 **0.31**.
- Notes: Signal direction is fundamentally unstable — inverts between time periods. Not redundant with H-076 (different math, same intuition) but neither works reliably. Both directions roughly equally likely to be positive. Data: 746 days, 14 assets, 60 param combos.
- Sessions: [2026-03-29 session 107]

## H-130: Funding Rate Momentum Factor (Rate of Change in Funding)
- Status: REJECTED
- Idea: Rate of change in funding rates as cross-sectional signal. Rising funding = increasing bullish sentiment → contrarian short. Captures momentum of sentiment, not level (unlike H-053).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: funding_momentum = short_avg(funding) - long_avg(funding). Cross-sectional rank. Contrarian: short rising, long falling.
- Result: IS **28.7%** positive. Contrarian 51.9%, momentum 5.6%. Best S5_L21_R7_N3 contrarian Sharpe **1.198**, +26.6% ann, 26.3% DD. WF **2/6** positive, mean OOS **0.216**. Split-half **-1.005** — signal completely inverts (H1 +1.23, H2 -1.01). Corr H-053 **0.201**, H-012 **-0.104**.
- Notes: Funding momentum was a strong signal early (fold 0: Sharpe 4.08) but has fully decayed in recent data. The funding rate regime has changed — rates have become more volatile and mean-reverting, breaking the momentum signal. Not redundant with H-053 (corr 0.20). Data: 730 days, 14 assets, 108 param combos.
- Sessions: [2026-03-29 session 107]

## H-131: Close-to-Range Position Factor
- Status: REJECTED
- Idea: Signal = (close - N-day low) / (N-day high - N-day low). Where is close within multi-day range? Near high = bullish (momentum), near low = bearish.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Rolling high/low range, position of close in range. Momentum: long assets near highs. Contrarian: long assets near lows.
- Result: IS **44%** positive overall. Momentum direction **79%** positive (mean Sharpe 0.281). Best: momentum LB20 R7 N4 Sharpe **0.759**, +15.6% ann, 18.2% DD. WF **4/6** positive, mean OOS **0.901**. Split-half **-0.015** (H1 -0.015, H2 +0.997) — second half only. Corr H-012 **0.263**, H-031 **-0.279**.
- Notes: Strong momentum direction in second half of data only — split-half instability kills it. WF OK (4/6) but IS fails (whole grid 44%, need 80%). Momentum direction is essentially re-capturing the same momentum signal as H-012 (price near highs = strong momentum). Data: 749 days, 14 assets, 48 combos.
- Sessions: [2026-03-29 session 108]

## H-132: Return Dispersion Timing Factor
- Status: REJECTED
- Idea: Use cross-sectional dispersion of returns to switch between momentum (high dispersion) and reversal (low dispersion) regimes.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 5-10 days)
- Logic: Compute std of N-day returns across assets. If dispersion > rolling median → HIGH regime (use momentum ranks). If below → LOW regime (use reversal = inverse ranks). Composite = momentum_rank * regime_sign.
- Result: IS **33%** positive. MW=20 best at **83%** positive (mean 0.250). Best overall: MW40 DW10 R7 N3 Sharpe **0.841**, +20.7% ann, 19.2% DD. WF **0/6** positive folds (best params insufficient data). Split-half **-0.147** (H1 +0.102, H2 -0.147). Corr H-012 **0.146**, H-031 **0.209**.
- Notes: Very parameter-sensitive — only MW=20 works (83% IS positive); longer windows all negative. The regime-conditioning adds complexity without improving OOS. Best params failed walk-forward (too short history with MW=40). Low-dispersion reversal is likely spurious on 2yr window. Data: 749 days, 14 assets, 54 combos.
- Sessions: [2026-03-29 session 108]

## H-133: Consecutive Direction Factor
- Status: REJECTED
- Idea: Count net up-days (sign of daily return, rolling sum) as cross-sectional signal. Assets with more consecutive up days = stronger trend propensity.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: net_up = rolling sum of sign(daily_ret). Momentum: long highest net-up (most up days). Contrarian: long lowest (most down days).
- Result: IS **29%** positive overall. Momentum direction **42%** positive. Best: momentum LB30 R7 N3 Sharpe **1.069**, +22.7% ann, 17.5% DD. WF **5/6** positive folds, mean OOS **0.245**. Split-half **-0.240** (H1 -0.006, H2 -0.240) — both halves negative. Corr H-012 **0.335**, H-031 **-0.017**.
- Notes: Interesting WF result (5/6 positive) but split-half both negative — contradictory. The best IS params (LB30 R7 N3) have strong IS Sharpe but OOS decays severely (IS/OOS 0.23). Signal is too discretized (integer net-up-days) to provide robust cross-sectional ranking. The contrarian LB7 had strong WF OOS (5/6, mean 1.144) but IS only 0.954. No direction consistently dominates. Data: 749 days, 14 assets, 48 combos.
- Sessions: [2026-03-29 session 108]

## H-134: Overnight Gap Reversal Factor
- Status: REJECTED
- Idea: Rank assets by overnight gap (open vs prior close). Long assets that gapped down (expected reversal up), short those that gapped up.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily rebalance)
- Logic: gap = (open - prev_close) / prev_close, averaged over lookback [1,3,5,10]. Long bottom N (gapped down), short top N.
- Result: IS **100%** positive (36/36), mean Sharpe **2.51**. Best L10_R1_N5 Sharpe **2.71**, +194% ann, 24.6% DD. WF **4/4** positive, mean OOS **2.66**. BUT split-half correlation **-0.808** — parameter rankings completely invert. Rebalance period has no effect (R1=R3=R5 identical — daily rebal regardless). Corr H-012 **0.457**, H-019 **0.519**.
- Notes: Suspiciously high returns and Sharpe. Rebalance parameter has zero impact suggesting implementation is daily-only. The -0.808 split-half means what works in first half is worst in second half — classic regime-dependent signal. Despite strong WF, parameter instability makes this unreliable. Data: 749 days, 14 assets, 36 combos.
- Sessions: [2026-03-29 session 109]

## H-135: Mean Reversion Speed Factor
- Status: REJECTED
- Idea: Rank assets by rolling lag-1 return autocorrelation. Long trending (high autocorr), short mean-reverting (low autocorr).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute rolling autocorrelation(lag=1) over window [10,20,30,40,60]. Long top N (positive autocorr = trending), short bottom N.
- Result: IS only **40%** positive, mean Sharpe **-0.211**, median **-0.087**. Best L60_R3_N5 Sharpe **0.97**. WF **0/6** positive (all OOS zero). Split-half corr **-0.087**. Corr H-012 **0.168**.
- Notes: Autocorrelation-based regime detection does not work as cross-sectional factor in crypto. Most params give negative returns, especially short lookbacks (L10 all negative). The concept that "trending vs mean-reverting" regime can be captured by simple autocorrelation fails here — crypto returns are too noisy at daily frequency. Data: 749 days, 14 assets, 45 combos.
- Sessions: [2026-03-29 session 109]

## H-136: Relative Strength Persistence Factor
- Status: REJECTED
- Idea: Measure fraction of days an asset outperforms the cross-sectional average over rolling window ("win rate vs peers").
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute rolling fraction of days with return > cross-sectional average. Long top N (most consistently outperforming), short bottom N.
- Result: IS **100%** positive (45/45), mean Sharpe **1.15**. Best L30_R7_N3 Sharpe **1.89**, +45.1% ann, 10.4% DD. OOS degrades: train 1.89 → test **0.46**. Split-half H1 **1.89**, H2 **0.41** — signal decays dramatically. WF **5/6** positive, mean OOS **0.56**. Corr H-012 **0.458**.
- Notes: Good IS performance but OOS degrades too much (split-half ratio 0.22). Signal is essentially a smoothed version of momentum (corr 0.458 with H-012) — the "persistence" metric just captures recent trend with extra noise reduction. The 0.56 mean WF OOS is borderline but not novel enough to justify deployment given overlap with existing momentum strategies. Data: 748 days, 14 assets, 45 combos.
- Sessions: [2026-03-29 session 109]

## H-137: Kurtosis Regime Change Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by change in excess kurtosis between current and lagged windows. Long assets with calming distributions (falling kurtosis = entering trend), short rising kurtosis.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-14 days)
- Logic: Compute rolling excess kurtosis over lookback window and a delta window. Rank by kurtosis change. Long/short top/bottom N.
- Result: IS 51% positive (below 60% threshold). Mean Sharpe 0.063. Best Sharpe 2.240. Contrarian direction 94% positive (mean 0.867). WF **1/4** positive, mean OOS **-1.136**. Split-half Spearman 0.389. Corr H-012 0.060. Data: 749 days, 360 param combos, 162 OOS trades.
- Notes: Classic overfitting — strong IS signal collapses OOS. Contrarian direction (short falling kurtosis) is the profitable one, suggesting high-kurtosis = trend, not mean-reversion. Genuinely uncorrelated with momentum but signal not robust.
- Sessions: [2026-03-30 session 110]

## H-138: Correlation Fragility Factor (14 Assets)
- Status: REJECTED (borderline — closest to passing)
- Idea: Measure instability of each asset's cross-correlations. Fragility = rolling std of mean absolute pairwise correlation. Long fragile-correlation assets (regime transition = opportunity), short stable.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-14 days)
- Logic: Compute rolling correlation of each asset with all others, then measure rolling std of that correlation. Rank by fragility. Long top N, short bottom N.
- Result: IS 53% positive (below 60%). Fragility direction alone: **90% positive**, mean Sharpe **0.652**. WF **3/4** positive, mean OOS **1.022**, +30.3% ann. Split-half Spearman **0.022** (weak). Corr H-012 **0.375**. Data: 749 days, 384 param combos, 119 OOS trades.
- Notes: Best WF OOS of the batch. If evaluated on fragility direction alone, it passes IS filter (90%) and has strong OOS. But split-half stability is very weak (0.022). Moderate H-012 correlation (0.375). Could revisit with longer data history.
- Sessions: [2026-03-30 session 110]

## H-139: Volume-Clock Dislocation Factor (14 Assets)
- Status: REJECTED
- Idea: Measure where volume clusters within a lookback window (volume centroid). Assets with accelerating volume (centroid shifted recent) may be experiencing institutional attention.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-14 days)
- Logic: Compute weighted centroid of volume within lookback window. Rank by centroid position. Long accelerating-volume, short decelerating.
- Result: IS 52% positive. Acceleration direction 98% positive (mean 0.882). WF **1/4** positive, mean OOS **-0.198**. Split-half Spearman **-0.363** (signal inverts). Corr H-012 **-0.074**. Data: 749 days, 240 param combos, 175 OOS trades.
- Notes: Genuinely uncorrelated with momentum (-0.074). Strong IS acceleration signal but parameter landscape is unstable (negative split-half). Signal structure changes between time periods.
- Sessions: [2026-03-30 session 110]

## H-140: Realized Skewness Factor (Contrarian, 14 Assets)
- Status: REJECTED
- Idea: Assets with high positive realized skewness attract lottery-seeking traders and underperform. Short high-skew, long low-skew (contrarian).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute realized skewness of daily returns over lookback window. Rank. Long bottom N (lowest skew), short top N (highest skew).
- Result: IS **11%** positive (far below 80%). Best Sharpe 0.31, mean -0.48. WF **2/6** positive, mean OOS 0.313. Split-half: H1 **-1.273**, H2 0.865 (unstable). Corr H-012 **-0.34** (good). Data: 749 days, 36 param combos.
- Notes: Realized skewness as a cross-sectional factor simply doesn't work in crypto. First half is strongly negative. Only redeeming quality is negative correlation with H-012.
- Sessions: [2026-03-30 session 111]

## H-141: Overnight Gap Reversion Factor (14 Assets)
- Status: REJECTED
- Idea: Assets that gap between previous close and current open tend to revert. Long assets with negative gaps, short assets with positive gaps.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute rolling average signed gap ratio = (open_t - close_{t-1}) / ATR. Rank. Long bottom N (biggest neg gaps), short top N (biggest pos gaps).
- Result: IS **100%** positive (best Sharpe 1.92, mean 1.81). WF **6/6** positive, mean OOS **1.872**. Split-half: H1=2.16, H2=1.60 (both strong). Corr H-012 **0.44** (FAILS >0.40 threshold). Data: 749 days, 48 param combos.
- Notes: Outstanding IS/OOS performance, BUT: (1) H-012 corr 0.44 marginally fails threshold, (2) in 24/7 crypto, daily bars have open==prev_close so "gap" is zero — signal may be degenerate/capturing momentum, explaining the correlation. All params have identical max_dd (0.39) regardless of rebal period, confirming signal degeneracy.
- Sessions: [2026-03-30 session 111]

## H-142: Intraday Range Compression Factor (14 Assets)
- Status: REJECTED
- Idea: Assets whose intraday range (H-L)/C is compressing relative to history are "coiling" for a breakout. Long compressed, short expanded.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute ratio of short-term avg range / long-term avg range. Rank. Long bottom N (most compressed), short top N (most expanded).
- Result: IS **0%** positive (mean Sharpe -0.81, best -0.02). WF **3/6** positive, mean OOS **-0.235**. Split-half: only 1.4% of params positive in both halves. Corr H-012 **-0.04** (excellent). Data: 749 days, 72 param combos.
- Notes: Complete failure. Range compression as a cross-sectional factor actively loses money. The "coiled spring" breakout intuition doesn't translate to cross-sectional alpha in crypto. Low H-012 correlation (near zero) confirms it's a genuinely different signal — just a bad one.
- Sessions: [2026-03-30 session 111]

## H-143: Short-Term Reversal Factor (Cross-Sectional)
- Status: REJECTED
- Idea: At short horizons (1-5 days), crypto assets may exhibit cross-sectional mean-reversion. Long worst performers of past L days, short best performers. Classic "short-term reversal" anomaly from equities.
- Instrument: futures (14 perps: BTC/ETH/SOL/XRP/DOGE/ADA/AVAX/DOT/LINK/ATOM/NEAR/OP/ARB/SUI)
- Timeframe: 1D (rebalance 1-5 days)
- Logic: Compute L-day return. Reversal: rank descending by negative return (long losers, short winners). Momentum comparison also run. Equal-weight top/bottom N.
- Result: **IS 22% positive** (mean Sharpe -0.46, best L3_R3_N4 Sharpe 1.35 @ 62.6% ann, 23.8% DD). **WF 3/6 folds positive**, mean OOS Sharpe **-0.724** (badly negative). **Split-half rank corr -0.077** (negative — no stability). H-012 corr **-0.047** (decorrelated). Data: 749 days (2024-03-11 to 2026-03-29), 72 reversal + 72 momentum combos.
- Notes: Failed all criteria except H-012 correlation. Only 22% of reversal params positive IS (need ≥80%). WF strongly negative (folds 4-6 all deeply negative: -1.99, -0.57, -4.04 Sharpe). Split-half corr negative — signal is not stable across time periods. Fee sensitivity poor: profitable only at 1x fees, breaks at 2x. Best IS param (L3_R3_N4 Sharpe 1.35) is cherry-picked — the regime breaks badly in 2025 H2. The short-term reversal anomaly that works in equities does not robustly transfer to crypto in this 2yr window. Momentum direction also failed WF with 3/6 folds positive. Supersedes H-077 (narrower grid, similar conclusion).
- Sessions: [2026-03-30 session 112]

## H-144: Idiosyncratic Volatility Factor (BTC-Residual, 14 Assets)
- Status: CONFIRMED
- Idea: Rank assets by residual volatility after removing BTC systematic exposure. Long low idio-vol (institutional quality), short high idio-vol (speculative). Distinct from H-019 (total vol) by controlling for BTC beta.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-14 days)
- Logic: Rolling OLS of each asset vs BTC returns → compute std(residuals) → cross-sectional rank. Long bottom-N (lowest idio-vol), short top-N (highest idio-vol). Dollar-neutral.
- Result: IS **92%** positive (55/60 params, mean 0.46, median 0.54). Best L20_R14_N4: Sharpe **1.15**, Ann **+45%**, DD **52%**. WF **6/6 folds positive**, combined Sharpe **1.99**, combined Ann **+68%**, DD **12.6%**. Split-half corr **+0.015** (passes). H-012 corr **0.010** (near zero — excellent diversifier). H-019 corr **0.72** (highly correlated with total vol factor). Data: 14 assets, 749 days (2024-03-11 to 2026-03-29). Criteria: 4/4 PASS.
- Notes: Strong signal — all 6 WF folds positive. Key concern: r=0.72 with H-019 means it overlaps with total-vol factor substantially. First half underperforms (mean Sharpe -0.84 for first half vs +1.66 second half) — possible regime shift in 2025 when idio-vol differentiation became more relevant. Best params: short lookback L20 and infrequent rebal R14. Should not be deployed alongside H-019 without portfolio-level analysis — they are nearly substitutes. Candidate to replace H-019 if it shows better OOS in paper trading.
- Sessions: [2026-03-30 backtest]

## H-145: Dollar-Volume Stability Factor (Cross-Sectional)
- Status: REJECTED
- Idea: Rank crypto assets by coefficient of variation (CV = std/mean) of daily dollar volume over a rolling window. Low CV = stable institutional volume. Long low-CV (stable), short high-CV (erratic) — "stable_long" direction.
- Instrument: futures (14 perps: BTC/ETH/SOL/XRP/DOGE/ADA/AVAX/DOT/LINK/ATOM/NEAR/OP/ARB/SUI)
- Timeframe: 1D (rebalance 3-14 days)
- Logic: Compute daily dollar volume = close * volume. Rolling CV over lookback L. Long bottom-N (lowest CV = stable), short top-N (highest CV = erratic). Parameter grid: L∈[10,20,30,40,60], R∈[3,5,7,10,14], N∈[3,4,5]. Both directions tested.
- Result:
  - **stable_long IS**: Only **29%** positive (22/75) — FAILS ≥80% criterion. Mean Sharpe -0.238. Best: L10_R5_N3 Sharpe 0.931, +34.1% ann, 55.5% DD.
  - **erratic_long IS**: **89%** positive (67/75). Mean Sharpe 0.481. Best: L20_R7_N4 Sharpe 1.549, +66.3% ann, 33.4% DD.
  - **Walk-forward (stable_long best params)**: **6/6** folds positive. Mean OOS Sharpe **1.571**, Mean OOS Ann +67.9%.
  - **Split-half (stable_long)**: Sharpe rank correlation **0.176** (positive, passes). H1 mean -1.082, H2 mean +0.847 — severe regime split.
  - **Correlations**: H-012 **-0.038** (excellent), H-031 **-0.190** (excellent).
  - Data: 749 days (2024-03-11 to 2026-03-29), 150 total combos. Criteria: 3/4 pass (FAILS IS 80%).
- Notes: The stable_long direction (the original hypothesis) fails IS criterion badly — only 29% of params show edge. The erratic_long direction (opposite) is the actual winner at 89% positive IS with Sharpe 1.549, suggesting that in crypto, HIGH volume variability assets outperform, not low-variability ones. The WF 6/6 for stable_long is impressive but the severe H1/H2 regime split (H1 mean -1.08, H2 mean +0.85) indicates the signal flipped direction mid-period. The erratic_long direction merits its own hypothesis (H-146) with a focused backtest to confirm robustness.
- Sessions: [2026-03-30 session 112]

## H-146: Lagged Cross-Asset Return Spillover Factor
- Status: REJECTED
- Idea: Some assets lead others. Use cross-asset lagged return correlations to predict which assets will outperform/underperform. Long predicted winners, short predicted losers.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-10 days)
- Logic: For each asset, compute correlation of its return with the lagged equal-weighted market return (excluding self) over a lookback window. Use this "response beta" * yesterday's market return to predict today's relative performance. Parameter grid: LB∈[20,40,60], RF∈[3,5,10], N∈[3,4].
- Result:
  - **IS**: **0%** positive (0/18) — complete failure. Mean Sharpe **-0.842**. All params negative.
  - Best: LB=20, RF=10, N=3: Sharpe -0.066. Worst: LB=40, RF=3, N=4: Sharpe -1.753.
  - Data: 999 days, 14 assets.
- Notes: Lead-lag effects at daily frequency in crypto are non-existent. All assets move together (high same-day correlation) with no usable lag structure. H-027 (lead-lag at 1h) was also rejected (1% positive). Lead-lag is not an exploitable signal in crypto at any timeframe.
- Sessions: [2026-03-31 session 114]

## H-147: Volume Profile Skewness (Up-Day vs Down-Day Volume Ratio)
- Status: REJECTED
- Idea: Compute ratio of average volume on up-days vs down-days. High ratio = buying pressure (accumulation). Long accumulated assets, short distributed.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-10 days)
- Logic: For each asset, compute avg(volume on up-days) / avg(volume on down-days) over lookback. Rank cross-sectionally. Long top-N (highest up/down volume ratio), short bottom-N. Parameter grid: LB∈[10,20,30,60], RF∈[3,5,10], N∈[3,4].
- Result:
  - **IS**: **83%** positive (20/24). Mean Sharpe 0.295. Best: LB=20, RF=5, N=3: Sharpe 0.964, +40.3% ann, 33.1% DD.
  - **Walk-forward (best params)**: **4/6** positive, mean OOS Sharpe **0.604**. But fold 2 extreme (-4.253). High variance.
  - **Split-half**: H1 Sharpe 1.612, H2 0.956 (consistent).
  - **IS/OOS**: IS 1.013 → OOS 1.047 (ratio 1.03 — no overfitting).
  - **Correlations**: H-012 (momentum) **0.330**, H-019 (low-vol) **-0.227**.
  - Data: 1000 days, 14 assets, 24 combos.
- Notes: Signal is real (IS/OOS ratio 1.03 is excellent) but noisy (WF fold 2 outlier at -4.25, high drawdown 33%). Moderate correlation with momentum (0.33) suggests it partially captures momentum through volume asymmetry. The consistent split-half and IS/OOS stability are notable. REJECTED due to noise, moderate momentum overlap, and high DD — doesn't add enough to portfolio.
- Sessions: [2026-03-31 session 114]

## H-148: Relative Drawdown Speed Factor
- Status: REJECTED
- Idea: Measure how quickly assets draw down vs recover. "Resilient" assets (fast recovery, slow drawdown) go long. "Fragile" assets go short. Behavioral factor.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-10 days)
- Logic: For each asset over lookback window, compute ratio of recovery speed (avg daily DD improvement on recovery days) to drawdown speed (avg daily DD worsening on drawdown days). Higher ratio = more resilient. Long top-N, short bottom-N. Parameter grid: LB∈[20,40,60,90], RF∈[3,5,10], N∈[3,4].
- Result:
  - **IS**: **58%** positive (14/24) — near random (50%). Mean Sharpe **0.082**.
  - Best: LB=90, RF=5, N=4: Sharpe 1.028. Worst: LB=40, RF=5, N=3: Sharpe -0.959.
  - Massive drawdowns across all params (40-79%).
  - Data: 1000 days, 14 assets, 24 combos.
- Notes: Resilience/fragility as measured by drawdown speed ratio has no cross-sectional signal. The 58% positive rate is essentially noise. Only LB=90 shows marginal edge (all 4 LB=90 combos are positive), suggesting a weak relationship between long-term resilience and future returns, but too weak and unstable to trade.
- Sessions: [2026-03-31 session 114]

## H-149: Volume Concentration Factor (Up-Day Volume %)
- Status: REJECTED
- Idea: Rolling % of volume occurring on up days (close > open). High % = buying pressure. Long top-N (most buying pressure), short bottom-N.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-10 days)
- Logic: Factor = sum(vol on up days) / sum(all vol) over rolling window. Rank cross-sectionally. Long top-N, short bottom-N. Equal weight, 50% per leg. Parameter grid: W∈[10,14,20,30], RF∈[3,5,7,10], N∈[3,4,5] (48 combos).
- Result:
  - **IS**: **100%** positive (48/48). Mean Sharpe **1.479**. Best: W=10, RF=3, N=4: Sharpe **2.506**, +51.0% ann, 11.1% DD.
  - **Walk-forward (6 folds, best params W=10,RF=3,N=4)**: **1/6** positive. Fold 1 Sharpe 3.172, Folds 2-6: -1.082, -1.853, -0.786, -0.146, -0.170. Mean OOS **-0.144**.
  - **Split-half**: H1 Sharpe **3.124**, H2 Sharpe **-1.346** (strong regime change mid-period).
  - **Correlation with momentum (H-012 proxy)**: **0.446** (above 0.40 threshold).
  - Data: 1000 days (2023-07-06 → 2026-03-31), 14 assets.
- Notes: Classic regime-dependent factor. Worked exceptionally well in H1 (bull run 2023-mid 2024) but completely failed in H2. The IS 100% positive rate is misleading — driven entirely by the first regime. Walk-forward shows the effect vanished after ~Dec 2023. Correlated with momentum (0.45), which explains the regime-dependency. Factor essentially captures a variant of trend/momentum signal. Similar to H-147 (up/down volume ratio, REJECTED) but even more regime-sensitive. The pure % volume concentration adds no signal beyond what momentum already captures.
- Sessions: [2026-03-31]

## H-151: Conditional Momentum (BTC Regime Switch)
- Status: REJECTED
- Idea: Use BTC SMA regime (uptrend/downtrend) to switch between momentum and contrarian cross-sectional strategies on 14 altcoins.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute N-day return for each asset. In BTC UPTREND (close > SMA), long top-M, short bottom-M (momentum). In BTC DOWNTREND, long bottom-M, short top-M (contrarian/reversal). Parameter grid: regime_window∈[20,30,50,60], momentum_lookback∈[14,21,30,60], rebalance_period∈[3,5,7], n_positions∈[3,4] (96 combos).
- Result:
  - **IS**: **86.5%** positive (83/96). Mean Sharpe **0.707**. Best params: rw=60, ml=21, rp=5, N=3: Sharpe 1.817, +125% ann, 29.9% DD.
  - **Static momentum baseline IS**: 93.8% positive, mean Sharpe 0.696.
  - **Improvement from regime switch**: +0.011 Sharpe (need >=+0.30) — FAIL.
  - **Walk-forward OOS (6 folds × 90 days)**: 5/6 positive, mean OOS Sharpe **1.535**. One bad fold (fold 6: -1.626). Conditional clearly better than static in OOS (folds 2,3,5 all negative for static but conditional positive).
  - **Split-half**: H1 Sharpe 2.577 (great), H2 Sharpe **-0.334** (fails).
  - **Correlations**: cond vs static = **0.225** (low, PASS), cond vs H-019 low-vol = -0.268.
  - **Regime breakdown**: 46% uptrend days, 54% downtrend days. Sharpe in uptrend 2.37, in downtrend 1.13.
  - Data: 749 daily bars, 14 assets.
- Notes: The regime switch does help OOS (WF looks strong), but the IS improvement is negligible (+0.01 Sharpe). The split-half failure reveals temporal instability — the strategy worked in H1 but broke down in H2. The conditional idea is directionally interesting (WF folds 2/3/5 show static momentum failing while conditional succeeds), but the second half of 2025/early 2026 is where the strategy falls apart. The mean Sharpe is inflated by regime coincidence in IS. The fundamental limitation: with only ~2 years of data, there are too few full BTC regime cycles to validate the hypothesis robustly. The C5 correlation check passed (0.225) — the strategy is meaningfully different from H-012, but that difference worked against it in the second half.
- Sessions: [2026-03-31 backtest]

## H-150: OI-Funding Interaction Factor
- Status: REJECTED
- Idea: Combine OI change and funding rate into a cross-sectional interaction signal. Rising OI + positive funding = frothy longs → SHORT (contrarian). Rising OI + negative funding → LONG (squeeze potential). Signal = sign(OI_change) * rolling_avg_funding.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 5-10 days)
- Logic: signal = sign(OI_pct_change_N) × rolling_M_avg_funding. Rank cross-sectionally. Long bottom-N, short top-N. Sign-based variant selected (68.1% IS positive vs 30.6% raw). OI_win∈[5,10,14,20], f_win∈[3,5,7], rebal∈[5,7,10], N∈[3,4] = 72 combos per variant.
- Result:
  - **IS (sign)**: **68.1%** positive (49/72). Best: OI_win=10, f_win=3, rebal=5, N=3: Sharpe **1.206**, +50.4% ann, 39.7% DD.
  - **Walk-forward (6 folds × 90d)**: **3/6** positive. Folds: -2.624, +1.120, -5.992, +3.136, +0.313, -2.345. Mean OOS Sharpe **-1.066**. FAIL (need ≥4/6 and mean > 0.5).
  - **Split-half**: H1 Sharpe **+1.729**, H2 Sharpe **-2.433**. FAIL (need both positive).
  - **Correlation**: H-012 **+0.082**, H-044 **+0.056**, H-053 **+0.176** — all well below 0.40. PASS.
  - Data: 14 assets, 2024-03-17 → 2026-03-16 (730 days).
- Notes: Novel factor (low corr with all references) passes IS at 68.1% and correlation criterion, but fails WF and split-half. Strong H1/H2 regime asymmetry. Raw interaction (OI_pct × funding) is even worse at 30.6% IS positive. 2/4 criteria passed.
- Sessions: [2026-03-31 session 115]

## H-152: Return Entropy Factor (14 Assets)
- Status: REJECTED
- Idea: Shannon entropy of daily return distribution over rolling window. Low entropy = concentrated/patterned (trending), high entropy = uniformly distributed (random). Long low-entropy, short high-entropy.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-10 days)
- Logic: Bin daily returns into 10 equal-width bins over rolling window. Compute Shannon entropy = -sum(p*log2(p)). Rank cross-sectionally. Low entropy → long (more predictable), high entropy → short (random). Grid: window∈[14,20,30,60], rebal∈[3,5,7,10], N∈[3,4,5] = 48 combos.
- Result:
  - **IS**: 54.2% positive (26/48). Mean Sharpe **0.026** — noise level.
  - **Walk-forward**: **3/6** positive, mean OOS **0.408** — decent OOS but weak IS.
  - **Split-half**: H1=1.420, H2=**-0.408** — collapses in recent data.
  - **Correlation with H-012**: -0.019 (uncorrelated — nice but signal is too weak).
  - Reverse direction (high_entropy_long) tested: worse.
  - Data: 1000 daily bars, 14 assets.
- Notes: Only 54% IS positive is noise level — the factor barely distinguishes assets cross-sectionally. The entropy of daily returns over 14-60 days is too similar across crypto assets (all similarly volatile). H1 captures a period where some assets had more concentrated returns, but this doesn't persist. 1/4 criteria met.
- Sessions: [2026-03-31 session 116]

## H-153: Volume Surprise Factor (14 Assets)
- Status: REJECTED
- Idea: Ratio of short-term average volume to long-term EMA volume. High surprise = unusual volume spike (information). Low surprise = quiet period.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-10 days)
- Logic: volume_surprise = rolling_mean(vol, short_win) / ema(vol, long_win). Rank cross-sectionally. Surprise_long: long high surprise (activity = information), short low surprise. Grid: short∈[3,5,7], long∈[20,30,60], rebal∈[3,5,7,10], N∈[3,4,5] = 108 combos.
- Result:
  - **IS**: **100%** positive (108/108). Mean Sharpe **1.159** — very strong.
  - **Walk-forward**: **2/6** positive, mean OOS **-0.809** — terrible OOS.
  - **Split-half**: H1=2.481, H2=**-0.788** — classic overfitting, signal inverts.
  - **Correlation with H-012**: -0.035 (uncorrelated).
  - Reverse direction (quiet_long) tested: worse.
  - Data: 1000 daily bars, 14 assets.
- Notes: Classic overfitting pattern — 100% IS positive but complete OOS failure. Volume surprise worked strongly in H1 (2023-2024) but inverted in H2 (2025-2026). Likely the relationship between volume spikes and forward returns changed as market structure evolved. Different from H-021 (volume momentum = level change) and H-085 (turnover velocity = ratio). 1/4 criteria met.
- Sessions: [2026-03-31 session 116]

## H-154: Cross-Asset Correlation Centrality Factor (14 Assets)
- Status: REJECTED
- Idea: Average pairwise correlation of each asset with all others over rolling window. Low centrality (peripheral) assets may earn diversification premium.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 5-14 days)
- Logic: For each asset, compute avg(corr(asset_i, asset_j)) for all j≠i over rolling window. Rank cross-sectionally. Peripheral_long: long low-centrality, short high-centrality. Grid: window∈[20,30,60,90], rebal∈[5,7,10,14], N∈[3,4,5] = 48 combos.
- Result:
  - **IS**: 91.7% positive (44/48). Mean Sharpe **0.434**.
  - **Walk-forward**: **3/6** positive, mean OOS **0.431**. Folds 5,6 negative (-0.105, -0.395).
  - **Split-half**: H1=1.468, H2=**0.212** — H2 positive but weak, significant degradation.
  - **Correlation with H-012**: **-0.216** (negative! excellent diversifier).
  - **Correlation with H-019**: **0.146** (low).
  - Central_long direction tested: worse.
  - Data: 1000 daily bars, 14 assets.
- Notes: Most promising of the three — 91.7% IS, excellent negative correlation with momentum (-0.216), and H2 still positive (0.212). But WF only 3/6 (need 4/6) and folds 5&6 are negative, suggesting signal is dying in recent data. The correlation centrality captures something real — peripheral assets outperform central ones — but the effect is weakening as crypto markets mature and correlations become more homogeneous. Close to CONDITIONAL but recent negative folds disqualify. 2/4 criteria met.
- Sessions: [2026-03-31 session 116]

## H-155: Amihud Illiquidity Factor (Cross-Sectional)
- Status: REJECTED
- Idea: Rank assets by Amihud illiquidity (mean |return| / dollar_volume). Classic equity factor — illiquidity premium.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily)
- Logic: Compute rolling Amihud illiquidity. Best direction: liquid_long (long most liquid, short illiquid).
- Data: 14 assets, ~1063 daily bars (~2.9yr). 48 param configs (4 windows × 4 rebal × 3 N).
- Result: IS 48/48 positive (100%), mean Sharpe 0.823. WF **6/6** positive, mean OOS 1.250. BUT split-half H1=-0.123, H2=1.603 (regime-dependent). **Corr 0.799 with H-031** (size factor) — near-duplicate signal. H-019 corr 0.477.
- Notes: Amihud illiquidity in crypto ≈ inverse of dollar volume ≈ size factor. Strong OOS but essentially redundant with H-031 which already captures this. Split-half failure confirms recent-regime dependence.
- Sessions: [2026-03-31 session 117]

## H-156: Funding Rate Volatility Factor (Cross-Sectional)
- Status: REJECTED
- Idea: Rank assets by rolling std of daily mean funding rates. Stable funding → predictable carry. Volatile funding → speculative churn.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily)
- Logic: Compute rolling std of funding rates. Best direction: stable_long (long stable-funding, short volatile-funding).
- Data: 14 assets, ~1064 daily bars, ~3190 funding records per asset. 48 param configs.
- Result: IS 43/48 positive (89.6%), mean Sharpe 0.658. WF 4/6 positive, mean OOS 0.476. Split-half **H1=1.712, H2=-0.075** — signal died in recent half. Excellent corr: H-012 0.013, H-053 -0.013 (genuinely novel signal source).
- Notes: Signal worked beautifully in H1 (Jul 2023 – Nov 2024) but died in H2. Regime-dependent. If the signal revives, this could be valuable (unique, zero corr with everything). Worth revisiting in 6 months.
- Sessions: [2026-03-31 session 117]

## H-157: Intraday Range Ratio Factor (Cross-Sectional)
- Status: REJECTED
- Idea: Rank assets by ratio of intraday range (high-low) to net movement (|close-open|). High ratio = noisy/reversal-prone. Low ratio = clean directional moves.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily)
- Logic: Compute rolling mean of (high-low) / |close-open|. Best direction: noisy_long (long noisy, short clean). Also tested clean_long (0/48 positive).
- Data: 14 assets, ~1063 daily bars. 48 param configs.
- Result: noisy_long IS 44/48 positive (91.7%), mean Sharpe 0.269. WF **3/6** positive, mean OOS **-0.289**. Split-half H1=-0.086, H2=-0.109 — both halves negative. Excellent corr: H-012 -0.006, H-076 -0.028 (genuinely uncorrelated).
- Notes: IS signal exists but completely fails OOS. Both split halves negative confirms signal is noise/overfitting. Low correlation is irrelevant if there's no actual signal.
- Sessions: [2026-03-31 session 117]

## H-158: Dual Momentum Factor (TS + XS Filter, 14 Assets)
- Status: REJECTED
- Idea: Combine time-series (absolute return sign) and cross-sectional momentum filters. Signal = return × |return| (squared return preserving sign). Only long when return > 0 AND in top-N, short when return < 0 AND in bottom-N.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily)
- Logic: Compute lookback-period return, multiply by absolute value to create sign-preserving squared signal. Rank cross-sectionally. Long top-N, short bottom-N.
- Data: 14 assets, 749 daily bars. 45 param configs (5 lookbacks × 3 N × 3 rebal).
- Result: IS 43/45 positive (96%), mean Sharpe 0.445, best 1.116. WF 4/6 positive, mean OOS 0.249. Split-half H1=1.374 H2=0.337 (both positive). BUT **corr 1.000 with H-012** — mathematically identical signal. Squaring returns preserves cross-sectional ranking.
- Notes: The TS filter adds nothing in cross-sectional context — ranking by return × |return| gives identical ranking to ranking by return. Redundant with H-012.
- Sessions: [2026-03-31 session 118]

## H-159: Volume-Adjusted Return Factor (14 Assets)
- Status: REJECTED
- Idea: Weight momentum by inverse square-root of realized volatility. Penalizes noisy momentum, rewards smooth trends.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily)
- Logic: Signal = return(mom_lookback) / sqrt(vol(vol_lookback)). Rank cross-sectionally, long top-N, short bottom-N.
- Data: 14 assets, 749 daily bars. 81 param configs (3 mom_lb × 3 vol_lb × 3 N × 3 rebal).
- Result: IS 79/81 positive (98%), mean Sharpe 0.478, best 1.166. WF **6/6** positive, mean OOS 0.546. Split-half H1=1.493 H2=0.674 (both positive). BUT **corr 0.948 with H-012** — near-duplicate. Dividing by sqrt(vol) barely changes the ranking.
- Notes: Despite excellent stats (WF 6/6), this is essentially H-012 momentum with cosmetic vol adjustment. Not worth deploying as separate strategy.
- Sessions: [2026-03-31 session 118]

## H-160: Trend-Quality Factor (Efficiency × Inverse Volatility, 14 Assets)
- Status: LIVE (paper trade since 2026-03-31)
- Idea: Multiplicative interaction of price efficiency ratio (trend smoothness) and inverse realized volatility, with directional momentum sign. Captures "quality of trend" — smooth, low-vol directional moves.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily)
- Logic: efficiency = |net_return(eff_lb)| / sum(|daily_rets|, eff_lb). signal = efficiency × (1/vol(vol_lb)) × sign(momentum). Rank XS, long top-N (smooth low-vol uptrends), short bottom-N.
- Data: 14 assets, 749 daily bars. 108 param configs (4 eff_lb × 3 vol_lb × 3 N × 3 rebal).
- Result:
  - IS: 94/108 positive (87%), mean Sharpe 0.493, best 1.175 (eff_lb=20, vol_lb=20, N=3, R=3)
  - WF: **4/6** positive, mean OOS **0.303** (train→test: 3.87→0.11, 2.50→-0.56, 1.40→1.17, 1.26→1.13, 2.32→-0.31, 2.28→0.28)
  - Split-half: H1=1.174, H2=**1.764** (both positive, H2 stronger = no decay)
  - Correlation: H-012 **0.355**, H-019 -0.140, H-031 0.071, H-076 **0.117** — all below 0.40
  - **ALL 4/4 criteria pass**
- Notes: Genuinely novel factor that combines trend quality with volatility preference. Only 0.117 corr with H-076 (pure efficiency) despite sharing efficiency ratio component — the inverse vol interaction creates a distinct signal. Deployed as paper trade session 119.
- Sessions: [2026-03-31 session 118, 2026-03-31 session 119 — deployed]

## H-161: Variance Ratio Factor (Lo-MacKinlay VR, 14 Assets)
- Status: REJECTED
- Idea: Cross-sectional ranking by Lo-MacKinlay variance ratio VR(k) = Var(k-day returns) / (k × Var(1-day returns)). VR > 1 = trending (long), VR < 1 = mean-reverting (short). Different from Hurst exponent (H-116) in computation method.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily)
- Logic: Compute rolling VR at horizon k (5d, 10d) over lookback (40-80d). Rank cross-sectionally. Long top-N (trending), short bottom-N (mean-reverting).
- Data: 14 assets, 1064 daily bars. 36 param configs (3 LB × 2 K × 3 R × 2 N).
- Result: IS **19/36 positive (52.8%)** = noise. Mean Sharpe -0.056. Best LB60_K10_R7_N3 Sharpe 0.661 (+35.3% ann, -46.9% DD).
- Notes: Variance ratio has no cross-sectional signal in crypto. 52.8% positive is essentially random. The trending/mean-reverting distinction doesn't differentiate future returns across assets. K=10 slightly better than K=5 but still insufficient.
- Sessions: [2026-03-31 session 119]

## H-162: MAX Effect (Maximum Daily Return Factor, 14 Assets)
- Status: REJECTED
- Idea: Based on Bali, Cakici, Whitelaw (2011) — assets with highest maximum single-day return in past lookback underperform (overpriced lottery tickets). Short high-MAX, long low-MAX.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily)
- Logic: Compute max(daily_return) over lookback window. Short high-MAX (lottery), long low-MAX (steady). Also tested reverse direction.
- Data: 14 assets, 1064 daily bars. 48 param configs (4 LB × 3 R × 2 N × 2 directions).
- Result: short_max **8/24 positive (33.3%)**. long_max **16/24 positive (66.7%)**. Neither direction passes 80%. Best short_max Sharpe 0.247. Best long_max Sharpe 0.626 (+33.0% ann, -55.2% DD).
- Notes: MAX effect doesn't exist in crypto. The lottery premium documented in equities (retail investors overpaying for high-MAX stocks) doesn't transfer — possibly because crypto itself is a "lottery" asset class, or because the cross-section of 14 assets is too narrow. long_max direction shows momentum-like signal but too weak and noisy.
- Sessions: [2026-03-31 session 119]

## H-163: Momentum Concentration Factor (14 Assets)
- Status: REJECTED
- Idea: Measure what fraction of total absolute returns came from the single best day (concentration = max(|ret|) / sum(|ret|)). High = fragile momentum (one big day). Low = broad-based persistent trend. Long low-concentration, short high-concentration.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily)
- Logic: Rolling concentration metric over lookback. Rank cross-sectionally. Long low-concentration (robust trends), short high-concentration (fragile).
- Data: 14 assets, 1064 daily bars. 48 param configs (4 LB × 3 R × 2 N × 2 directions).
- Result: low_conc_long **19/24 positive (79.2%)** — close but below 80% threshold. Mean Sharpe 0.254. Best LB40_R5_N4 Sharpe 0.826 (+34.4% ann, -56.5% DD). high_conc_long only 20.8% positive.
- Notes: The low-concentration direction came very close (79.2% vs 80% threshold) but fails param robustness. High drawdown (-56.5%) and marginal hit rate suggest this is a fragile signal. The concept is sound but the 14-asset universe may be too small to reliably differentiate momentum quality by concentration alone.
- Sessions: [2026-03-31 session 119]

## H-164: Co-Momentum Factor (Peer-Weighted Momentum, 14 Assets)
- Status: REJECTED
- Idea: For each asset, compute co-momentum = mean(corr(i,j) × momentum(j)) over all peers j. High co-momentum = trend confirmed by correlated peers. Long high co-momentum, short low.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily)
- Logic: Rolling cross-asset correlation matrix × peer momentum signals. Captures "consensus momentum" vs "isolated momentum."
- Data: 14 assets, 1064 daily bars. 54 param configs (3 corr_lb × 3 mom_lb × 3 R × 2 N).
- Result: IS **8/54 positive (14.8%)** = noise. Mean Sharpe -0.476. Best CL30_ML20_R7_N3 Sharpe 0.217 (+11.7% ann, -55.6% DD).
- Notes: Peer-weighted momentum has zero cross-sectional signal in crypto. With 14 highly correlated assets (all correlated to BTC), co-momentum just captures the market factor — every asset's peers are trending the same way. The cross-sectional variation in co-momentum is too small to differentiate.
- Sessions: [2026-04-01 session 120]

## H-165: Funding-Premium Interaction Factor (14 Assets)
- Status: REJECTED
- Idea: Multiply z-scored funding rate × z-scored premium index. Joint extreme = maximum crowding → go contrarian. Short high interaction (bullish crowding), long low.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily)
- Logic: For each asset, compute rolling z-score of funding rate and premium index. Signal = z_funding × z_premium. Go contrarian: short when both signals are extremely positive, long when both extremely negative.
- Data: 14 assets, ~700 daily bars (funding + premium overlap). 96 param configs (4 fund_lb × 4 prem_lb × 3 R × 2 N).
- Result: IS **24/96 positive (25.0%)** = noise. Mean Sharpe -0.369. Best FL20_PL20_R3_N3 Sharpe 1.154 (+47.7% ann, -31.8% DD).
- Notes: The funding-premium interaction doesn't produce a robust cross-sectional signal. The two positioning indicators (funding rate and premium index) don't meaningfully combine — their product z-score is too noisy to rank assets reliably. Individual signals (H-052, H-053) work better alone than multiplied.
- Sessions: [2026-04-01 session 120]

## H-166: Return Persistence Factor (14 Assets)
- Status: REJECTED
- Idea: Fraction of recent days where daily return matches sign of lookback momentum × momentum direction. High = smooth, persistent trend. Long smooth uptrends, short smooth downtrends.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily)
- Logic: Compute persistence = (days with same sign as momentum / total days) × sign(momentum) over lookback. Rank cross-sectionally. Long top-N, short bottom-N.
- Data: 14 assets, 1064 daily bars. 30 param configs (5 LB × 3 R × 2 N).
- Result: IS **27/30 positive (90.0%)**, mean Sharpe 0.610, best LB10_R3_N3 Sharpe 1.894 (+89.4% ann, -28.7% DD). WF **6/6** positive, mean OOS **2.263**. Split-half H1=0.562, H2=0.395 (both positive, corr 0.199). H-012 corr **0.249**. BUT **H-160 corr 0.503** (above 0.40 threshold). H-076 corr 0.344.
- Notes: Excellent standalone metrics — passes 3/4 criteria convincingly. The 10-day return persistence signal captures "smooth short-term momentum," which is conceptually and empirically very close to H-160 (trend-quality = efficiency × inverse vol × momentum sign). The 0.503 correlation with H-160 confirms redundancy. Not worth deploying separately. If H-160 ever gets killed, H-166 would be the natural replacement.
- Sessions: [2026-04-01 session 120]

## H-167: Volume-Price Confirmation Factor (14 Assets)
- Status: CONFIRMED
- Idea: Rolling correlation between daily returns and volume changes. High correlation = volume confirms price trend. Low/negative = volume diverges from price. Long confirmed, short diverging.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute rolling Pearson correlation between daily price returns and daily volume changes over lookback window. Rank cross-sectionally. Long top-N (volume-confirmed), short bottom-N (volume-diverging). Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4] = 30 combos.
- Data: 14 assets, 1065 daily bars (2023-05-03 to 2026-04-01).
- Result: IS **27/30 positive (90.0%)**, mean Sharpe 0.444, best LB10_R7_N4 Sharpe 1.227 (+46.3% ann, -34.6% DD). WF **5/6** positive, mean OOS **1.145**. Split-half H1=0.781, H2=0.088 (both positive but H2 marginal). H-012 corr **0.251**, H-076 corr 0.092, H-160 corr 0.121. Max corr with existing: 0.251.
- Notes: Passes all 4/4 criteria. Novel signal — volume-price confirmation is conceptually different from volume momentum (H-021) or volume surprise (H-153). Caveat: H2 split-half is only 0.088, suggesting signal weakened in recent period. Short lookback (10d) optimal may capture noise. Not deploying yet given 19 active runners.
- Sessions: [2026-04-01 session 121]

## H-168: Return Autocorrelation Factor (14 Assets)
- Status: REJECTED
- Idea: Rolling first-order autocorrelation of daily returns. High positive autocorrelation = trending asset. Negative = mean-reverting. Long trending, short mean-reverting.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute Pearson correlation between r(t) and r(t-1) over rolling window. Rank cross-sectionally. Long high-autocorrelation, short low. Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4] = 30 combos.
- Data: 14 assets, 1065 daily bars.
- Result: IS **6/24 positive (25.0%)** — noise level. Best LB20_R7_N3 Sharpe 0.299 (+14.6% ann, -52.3% DD). Massive drawdowns across all params.
- Notes: Autocorrelation has no cross-sectional signal in crypto. Daily returns are too noisy for first-order autocorrelation to discriminate between assets. Different from H-115/H-135 (autocorrelation tested previously) — confirms that autocorrelation is not a viable XS factor in crypto at any lookback.
- Sessions: [2026-04-01 session 121]

## H-169: Beta-Adjusted Momentum (Alpha Factor, 14 Assets)
- Status: CONFIRMED
- Idea: Rank altcoins by alpha vs BTC (return minus beta × BTC return). Captures genuine outperformance, not just high-beta rides. Long positive alpha, short negative alpha.
- Instrument: futures (13 perps, excluding BTC)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each non-BTC asset, compute rolling OLS beta vs BTC, then alpha = cumulative(return - beta × BTC_return) over lookback. Rank cross-sectionally. Long top-N alpha, short bottom-N. Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4] = 30 combos.
- Data: 14 assets (13 ranked), 1065 daily bars.
- Result: IS **30/30 positive (100%)**, mean Sharpe **1.118**, best LB10_R5_N4 Sharpe **1.550** (+67.9% ann, -35.2% DD). WF **4/6** positive, mean OOS **1.648** (folds 3&4 negative: -1.798, -1.540). Split-half H1=1.335, H2=0.422 (both positive). H-012 corr **0.342**, H-076 corr 0.161, H-160 corr 0.133, H-167 corr 0.371. Max corr with existing: 0.342.
- Notes: Strongest new factor — 100% IS positive rate is exceptional. Beta-adjusted momentum is theoretically grounded (alpha capture). The 0.342 correlation with H-012 is borderline but passing (<0.40). Caveat: WF folds 3&4 deeply negative suggests regime-dependent behavior (BTC flat periods may confuse the signal). H-167 mutual corr 0.371 — deploying both would add some redundancy. Not deploying yet given 19 active runners.
- Sessions: [2026-04-01 session 121]

## H-170: Return Kurtosis Factor (14 Assets)
- Status: REJECTED
- Idea: Rolling excess kurtosis of daily returns as cross-sectional factor. High kurtosis = fat tails = dangerous/unpredictable. Long low-kurtosis (predictable), short high-kurtosis (risky).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute scipy.stats.kurtosis(returns[-LB:]) for each asset daily. Rank cross-sectionally. low_kurt_long: long bottom-N (thinnest tails), short top-N (fattest tails). Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], direction∈[low_kurt_long, high_kurt_long] = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result:
  - IS: low_kurt_long **28/30 positive (93.3%)**, mean Sharpe 0.629, best LB30_R7_N4 Sharpe **1.319** (+48.8% ann, -26.3% DD). high_kurt_long only 2/30 (6.7%). **PASS IS**
  - WF: **2/6** positive, mean OOS **-0.463** (fold sharpes: -2.78, 7.00, -2.64, -4.21, -2.59, 2.43). **FAIL**
  - Split-half: H1=0.156, H2=1.487 — massive asymmetry, factor concentrated in recent period
  - Correlations: H-012 **-0.091**, H-076 **-0.133**, H-160 **-0.137**, H-167 **-0.208**, H-169 **-0.043** — all negative, genuinely novel
  - Score: **1/4** criteria (IS pass, WF fail, split-half unstable)
- Notes: IS looks excellent (93.3%) and correlations are ideal (all negative vs existing factors — true diversifier). However, WF exposes severe recency bias — factor appears concentrated in Q4-2025/Q1-2026 (H2=1.487 vs H1=0.156). The kurtosis signal may be capturing a temporary regime where low-tail-risk assets outperformed. Not stable enough for deployment. Novel concept worth revisiting if crypto enters sustained low-vol regime.
- Sessions: [2026-04-01 session 122]

## H-171: Funding Rate Momentum Factor (Retest)
- Status: REJECTED
- Idea: CHANGE in funding rates as cross-sectional signal. Rising funding = growing bullish crowding → contrarian short. Captures acceleration of positioning sentiment, not level (H-053).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: funding_momentum = mean(funding[-SW:]) - mean(funding[-LW:]). Positive = funding rising (crowding increasing). Contrarian: long bottom-N (falling funding), short top-N (rising funding). Grid: SW∈[3,5,10], LW∈[10,20,30], R∈[3,5,7], N∈[3,4], direction∈[contrarian,momentum] — 96 combos. SW < LW constraint.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01), 730-day funding panel. Retest of H-130 with newer data.
- Result:
  - IS: **38/96 positive (39.6%)**, mean Sharpe -0.350. **FAIL** (need ≥80%)
  - Direction split: contrarian **33/48 (68.8%)** mean 0.145; momentum **5/48 (10.4%)** — clear directional asymmetry
  - Best: SW10_LW30_R5_N4_contrarian Sharpe **1.275**, +22.7% ann, -20.6% DD
  - WF: **5/6** positive, mean OOS **1.625** (fold sharpes: 1.45, 1.55, -0.75, 0.90, 1.46, 5.14) — **PASS**
  - Split-half (all params): H1=-0.300, H2=-0.427 — **FAIL**
  - Split-half (best contrarian params only): H1=1.833, H2=0.533 — both positive
  - Correlations: H-012 **-0.121**, H-053 **0.405** (slightly above 0.40 threshold), H-076 **-0.077**, H-160 **-0.122**
  - Score: **1/3** criteria
- Notes: Reconfirms H-130 rejection. IS failure is driven entirely by the momentum direction (10% positive) which is simply the wrong direction. Contrarian-only would be 68.8% positive — still below 80% threshold. The strong WF (5/6, mean 1.625) is encouraging but the split-half shows no regime consistency across the full parameter space. The 0.405 correlation with H-053 (funding level) confirms the two strategies are related — choosing contrarian vs long_low in H-053 is equivalent. Funding momentum adds no independent alpha beyond funding level.
- Sessions: [2026-04-01 session 122 (this session)]

## H-172: Hurst Exponent Factor (R/S Method, 14 Assets)
- Status: REJECTED
- Idea: Rank 14 assets by rolling Hurst exponent (R/S rescaled-range method). H > 0.5 = trending (long), H < 0.5 = mean-reverting (short). Or reverse direction.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute Hurst exponent via R/S on rolling log-returns using sub-period sizes [n//8, n//4, n//2, n]; OLS slope of log(R/S) on log(n) = H. Rank cross-sectionally. trending_long: long top-N (high H), short bottom-N. meanrev_long: opposite. Grid: LB∈[20,30,40,60,80], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 1065 daily bars (2023-05-03 to 2026-04-01). Best: LB80_R5_N4_trending_long Sharpe 1.407 (+57.5% ann, -30.3% DD).
- Result: IS **trending_long 13/30 positive (43.3%)**, mean Sharpe -0.126. **meanrev_long 10/30 positive (33.3%)**, mean Sharpe -0.213. Both directions fail 80% IS threshold — deep validation not run.
- Notes: Hurst exponent has no consistent XS signal in crypto at any lookback from 20-80 days. Mirrors H-116 (prior Hurst backtest, different sub-period splits) and H-168 (autocorrelation — also no XS signal). All three serial-dependence measures fail, confirming that persistence structure is not a viable cross-sectional factor in crypto. The few positive combos cluster at LB=80, suggesting very long-horizon Hurst may contain a weak signal, but not robust enough. Matches H-116 conclusion.
- Sessions: [2026-04-01 (this session, h172_hurst/backtest.py)]

## H-173: Garman-Klass Volatility Ratio Factor (14 Assets)
- Status: REJECTED
- Idea: Compare Garman-Klass OHLC-based volatility to close-to-close volatility. High ratio = intraday noise dominates. Long low-ratio (clean trends), short high-ratio (noisy). Captures vol *structure*, not level.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: GK_var = mean(0.5*ln(H/L)^2 - (2ln2-1)*ln(C/O)^2). Ratio = GK_vol / CC_vol. Rank cross-sectionally. Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 1065 daily bars (2023-05-03 to 2026-04-01).
- Result: IS low_ratio_long **16/30 positive (53.3%)**, mean Sharpe 0.099. **FAIL** IS < 80%. Best LB10_R5_N4 Sharpe 0.922. WF 3/6, mean 0.922. Split-half H1=1.150, H2=-0.285. Correlations: H-012 -0.006, H-076 0.126, H-160 0.077.
- Notes: GK-to-CC ratio does not produce a reliable cross-sectional signal. The intraday vol structure is too similar across crypto assets to discriminate. Different from H-019 (vol level) but lacks stable edge.
- Sessions: [2026-04-01 session 123]

## H-174: Downside Beta Factor (13 Non-BTC Assets)
- Status: REJECTED
- Idea: Compute beta using only BTC-down days (asymmetric risk). Long defensive assets (low downside beta), short fragile (high downside beta). Different from H-024 (full beta) because it isolates loss-day sensitivity.
- Instrument: futures (13 perps, excl BTC)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each non-BTC asset, compute OLS beta using only days where BTC return < 0. Rank cross-sectionally. Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 1065 daily bars.
- Result: IS high_dbeta_long **18/30 positive (60.0%)**, mean Sharpe 0.034. **FAIL** IS < 80%. Best LB20_R5_N3 Sharpe 0.675 (+33.5% ann, -58.0% DD). WF 4/6, mean 0.165. Split-half H1=1.007, H2=-0.404.
- Notes: Downside-specific beta does not produce a stable XS signal. Surprising that high_dbeta_long slightly outperforms, suggesting high-beta assets that drop most in BTC downturns also rally most on recoveries. But signal too weak and inconsistent. Corr H-012 -0.039, H-076 0.073, H-160 -0.123 — novel but not useful.
- Sessions: [2026-04-01 session 123]

## H-175: Net Money Flow Factor (14 Assets)
- Status: CONFIRMED → LIVE (paper trade since 2026-04-01)
- Idea: Net flow = (close - open) / open × volume, summed over lookback, normalized by avg dollar volume. Captures directional buying/selling pressure. Long inflow assets, short outflow.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance every 7 days)
- Logic: For each asset, compute rolling sum of net_flow = ((close - open)/open) × volume over lookback window. Normalize by mean(close × volume). Rank cross-sectionally. Long top-N (strongest inflow), short bottom-N (strongest outflow). Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4] = 30 combos.
- Data: 14 assets, 1065 daily bars (2023-05-03 to 2026-04-01).
- Result: IS inflow_long **30/30 positive (100.0%)**, mean Sharpe **1.005**, best LB30_R7_N4 Sharpe **1.402** (+59.7% ann, -35.1% DD). WF **4/6** positive, mean OOS **1.051** (fold Sharpes: 5.017, 0.079, -0.196, -0.717, 1.178, 0.944). Split-half H1=**1.618**, H2=**0.226** (both positive). H-012 corr **0.145**, H-076 corr **-0.062**, H-160 corr **0.299**. Max corr with existing: 0.299.
- Notes: Exceptional 100% IS positive rate (third factor to achieve this alongside H-012 and H-169). Passes all 4/4 criteria. Net money flow is conceptually different from momentum (price only), volume momentum (volume level only), and OBV (H-118, which accumulates all up-days). This uses open-close range × volume — more granular directional flow. Deployed as paper trade #21.
- Sessions: [2026-04-01 session 123]

## H-176: Momentum-Reversal Timing Factor (14 Assets)
- Status: REJECTED
- Idea: Combine long-term momentum rank with short-term reversal. "Buy the dip" in uptrending assets, "short the dead cat bounce" in downtrending assets. Score = long_term_mom_rank - short_term_ret_rank.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute long-term return (LLB lookback) and short-term return (SLB lookback). Score = percentile_rank(LT_ret) - percentile_rank(ST_ret). Long top-N (strong trend + dip), short bottom-N (weak trend + bounce). Grid: LLB∈[30,40,60], SLB∈[3,5,7], R∈[3,5,7], N∈[3,4] = 54 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS **18/54 positive (33.3%)**, mean Sharpe -0.120. **FAIL** IS < 80%. Best: LLB60_SLB3_R3_N4 Sharpe 0.859 (+37.2% ann, -35.8% DD). Signal only works in narrow parameter corner (LLB=60, SLB=3, R=3) — highly fragile.
- Notes: The dip-buying/dead-cat concept doesn't produce robust cross-sectional signal in crypto. The best combo looks decent individually but 67% of parameter space is negative. The signal is too sensitive to exact lookback choices — classic overfitting signature. Short-term reversals in crypto are too noisy to combine reliably with momentum.
- Sessions: [2026-04-01 session 124]

## H-177: Volume Trend (Slope) Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by OLS slope of log(volume) over rolling window. Rising volume = accumulation/growing interest. Long rising-volume assets, short declining-volume.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute OLS slope of log(volume) vs time index, normalized by std for cross-sectional comparability. Rank. rising_long: long top-N, short bottom-N. Also test declining_long. Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS rising_long **21/30 positive (70.0%)**, mean Sharpe 0.281. declining_long 1/30 (3.3%). **FAIL** IS < 80%. Best: LB40_R3_N4_rising_long Sharpe 1.239 (+44.5% ann, -35.6% DD). Direction is clear (rising > declining) but not robust across parameter space.
- Notes: Close to threshold (70% vs 80%) — most promising rejected factor in recent sessions. Signal works at medium lookbacks (30-40d) but fails at short lookbacks (10-20d) and with infrequent rebalancing. Volume trends in crypto are legitimate (accumulation thesis) but the signal is too noisy at the daily frequency. Possibly viable at weekly frequency but not tested.
- Sessions: [2026-04-01 session 124]

## H-178: Correlation Regime Change Factor (13 Non-BTC Assets)
- Status: REJECTED
- Idea: Track how each asset's rolling correlation with BTC changes over time. Short herding assets (increasing corr), long decorrelating assets (decreasing corr). Based on crowding/herding theory.
- Instrument: futures (13 USDT perps, excl BTC)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each non-BTC asset, compute rolling corr with BTC over short window (SW) and long window (LW). Corr_change = short_corr - long_corr. Positive = herding, negative = decorrelating. Rank. decorr_long: long bottom-N, short top-N. herd_long: opposite. Grid: SW∈[10,20,30], LW∈[40,60,90], R∈[3,5,7], N∈[3,4], dir∈2 = 108 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS decorr_long **25/54 positive (46.3%)**, mean Sharpe -0.078. herd_long 12/54 (22.2%), mean -0.421. **FAIL** IS < 80%. Best: SW20_LW90_R5_N3 Sharpe 0.808 (+36.4% ann, -48.5% DD). Highly parameter-sensitive — SW=20 combos dominate top, SW=10 dominate bottom.
- Notes: Correlation regime changes don't produce reliable XS signals in crypto. The herding/decorrelation dynamic may exist but is too noisy to trade profitably. Neither direction shows systematic edge. Best individual combo has high DD (48.5%) suggesting fragile signal. Crypto assets move in and out of BTC correlation too rapidly for this to be a stable factor.
- Sessions: [2026-04-01 session 124]

## H-179: OI Share Change Factor (14 Assets)
- Status: REJECTED
- Idea: Track each asset's share of total universe OI over time. Long assets whose OI share is growing (attracting speculative attention), short those with declining share. Measures RELATIVE OI allocation, not absolute OI change (H-044).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute OI_share = asset_OI / sum(all_OI). Compute share_change = OI_share(today) - OI_share(today - lookback). Rank cross-sectionally. Grid: LB∈[5,10,20,30,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS shrinking_long **19/30 positive (63.3%)**, mean Sharpe 0.236. growing_long 2/30 (6.7%), mean -0.702. **FAIL** IS < 80%. Best LB60_R7_N4 Sharpe 1.966 (+74.9% ann, -23.7% DD). Direction is clear (shrinking > growing) but not robust.
- Notes: Counterintuitively, assets losing OI share outperform those gaining share. This suggests crowding — assets attracting new OI become overexposed and underperform. The contrarian signal has promise (best combo Sharpe 1.97) but is too parameter-sensitive (only 63.3% positive). OI share changes may be too noisy at the daily frequency to be a reliable cross-sectional signal.
- Sessions: [2026-04-01 session 125]

## H-180: Multi-Timeframe Momentum Agreement Factor (14 Assets)
- Status: REJECTED
- Idea: Count how many lookback windows (5d, 10d, 20d, 40d, 60d) agree on positive returns. Assets with full multi-TF agreement go long, those with full downtrend agreement go short. Uses BINARY agreement, not return magnitude.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute returns over [5,10,20,40,60] day lookbacks. Count positives → agreement_score ∈ {0..5}. Rank cross-sectionally. Tiebreak by avg_return or sum_return. Grid: R∈[3,5,7], N∈[3,4], dir∈2, tiebreak∈2 = 24 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS agreement_long **12/12 positive (100%)**, mean Sharpe 0.635. Best R7_N4 Sharpe 1.045 (+45.9% ann, -28.6% DD). **PASS IS.** WF **1/4** positive, mean OOS 0.036. **FAIL WF.** Split-half H1=2.069, H2=0.842 (PASS). Corr H-012 **0.690**, H-169 **0.560**. **FAIL Correlation.**
- Notes: Despite excellent IS (100% positive), the factor is just a momentum proxy in disguise. 0.69 correlation with H-012 (momentum) proves the binary agreement approach doesn't differentiate enough. WF fails badly (only most recent fold positive). Tiebreak method made zero difference — binary agreement dominates with only 14 assets. Not novel enough.
- Sessions: [2026-04-01 session 125]

## H-181: Volume Stability Factor (Volume CV, 14 Assets)
- Status: REJECTED
- Idea: Measure volume consistency via coefficient of variation (CV = std/mean) of daily volume. Low CV = stable institutional volume. High CV = erratic retail/news-driven volume. Captures volume QUALITY, not level or direction.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute rolling CV = std(volume) / mean(volume) over lookback window. Rank cross-sectionally. stable_long: long low-CV, short high-CV. erratic_long: opposite. Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS erratic_long **20/30 positive (66.7%)**, mean Sharpe 0.202. stable_long 1/30 (3.3%), mean -0.589. **FAIL** IS < 80%. Best LB20_R7_N3 Sharpe 1.048 (+43.6% ann, -35.4% DD).
- Notes: Counterintuitive result: erratic volume assets outperform stable ones. This may reflect that high-CV assets are those experiencing volume surges (attention events) which drive returns. However, the signal is not robust (66.7% vs 80% threshold). Volume stability alone doesn't discriminate reliably in the cross-section. The institutional/retail quality hypothesis doesn't hold in crypto — all assets have similar volume patterns driven by BTC correlation.
- Sessions: [2026-04-01 session 125]

## H-182: High-Low Range Factor (14 Assets)
- Status: CONFIRMED → LIVE (paper trade since 2026-04-02)
- Idea: Use normalized intraday range (High - Low) / Close as a cross-sectional signal. Assets with narrow ranges are in quiet accumulation; wide ranges indicate panic/volatility. Different from H-019 (close-close vol) because it uses intraday extremes.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: For each asset, compute rolling mean of (high - low) / close over lookback window. Rank cross-sectionally. narrow_long: long lowest range (bottom-N), short highest range (top-N). Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS narrow_long **27/30 positive (90.0%)**, mean Sharpe **0.503**, best LB30_R5_N3 Sharpe **0.912** (+47.2% ann, -62.1% DD). WF **5/6** positive, mean OOS **1.506** (fold Sharpes: 5.557, 2.201, 1.167, 1.573, 2.811, -4.274). Split-half H1=**0.416**, H2=**2.397** (both positive). H-012 corr **0.200**, H-076 corr **-0.154**, H-160 corr **0.101**. Max corr 0.200.
- Notes: Genuinely novel signal — captures "quiet accumulation" vs "panic volatility" via intraday range. Very low correlation with all existing factors (max 0.200). 90% IS robust. WF very strong (5/6, mean 1.506). Only concern: best IS combo has -62.1% DD, but WF stabilizes. Different from close-close volatility (H-019) and price efficiency (H-076). Ready for paper trade deployment.
- Sessions: [2026-04-01 session 126]

## H-183: Gap Factor — Overnight Sentiment (14 Assets)
- Status: CONFIRMED → LIVE (paper trade since 2026-04-02)
- Idea: Compute overnight gap = (open - prev_close) / prev_close. Rolling average gap captures persistent overnight sentiment. Contrarian direction (neg_gap_long) outperforms — assets gapping down overnight tend to bounce.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: For each asset, compute daily gap = (open_t - close_{t-1}) / close_{t-1}. Rolling mean over lookback. Rank cross-sectionally. neg_gap_long: long assets with most negative overnight gaps, short those with positive gaps. Grid: LB∈[5,10,20,30,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS neg_gap_long **30/30 positive (100.0%)**, mean Sharpe **1.276**, best LB10_R5_N4 Sharpe **1.778** (+85.3% ann, -38.0% DD). WF **5/6** positive, mean OOS **1.771** (fold Sharpes: 4.794, 1.333, 1.454, 1.639, 1.497, -0.089). Split-half H1=**1.826**, H2=**2.040** (both strong). H-012 corr **0.468**, H-076 corr **-0.050**, H-160 corr **0.190**. Max corr 0.468.
- Notes: Fourth factor to achieve 100% IS positive (alongside H-012, H-169, H-175). Exceptional WF performance (mean OOS 1.771, best of any factor tested). Contrarian interpretation: overnight optimism (positive gaps) is crowded; gaps down reflect genuine selling pressure that reverses intraday. Borderline H-012 correlation (0.468) — passes threshold but partially captures momentum. The overnight decomposition adds genuine alpha beyond plain momentum. Ready for paper trade deployment.
- Sessions: [2026-04-01 session 126]

## H-184: Volume-Weighted Return Momentum (14 Assets)
- Status: REJECTED
- Idea: Weight daily returns by relative volume (vol_t / avg_vol_20d) to emphasize "high conviction" moves. Cumulative volume-weighted return over lookback as momentum signal.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: For each asset, compute daily return × (volume / rolling_mean(volume, 20)). Rolling sum over lookback. Rank cross-sectionally. vwmom_long: long top-N, short bottom-N. Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS vwmom_long **25/30 positive (83.3%)**, mean Sharpe 0.644, best LB10_R5_N4 Sharpe **1.860** (+73.9% ann, -29.2% DD). WF **3/6** positive (3.925, 1.892, 2.022, -3.270, -3.417, -2.823), mean OOS -0.279. **FAIL WF.** Split-half H1=2.197/H2=1.689 (best) but H2 mean=-0.090. Corr H-012 0.284, H-076 0.026, H-160 0.157.
- Notes: Volume-weighted momentum concept has merit (IS passes at 83.3%, near standard momentum). Recent 3 folds very strong (1.9-3.9 Sharpe) but older folds deeply negative — classic recency bias. The signal emerged recently (post-2025) and didn't exist before. Volume weighting doesn't add enough temporal stability over plain momentum. Corr 0.284 with H-012 confirms partial overlap. Interesting that it works at short lookbacks (LB10) but fails at longer ones (LB40) — volume-confirmation is short-lived.
- Sessions: [2026-04-01 session 126]

## H-185: Return Skewness Factor (14 Assets)
- Status: REJECTED
- Idea: Rolling skewness of daily returns as cross-sectional signal. Positive skew = "lottery" (explosive upside but usually grind down). Negative skew = "steady" (gradual gains). Test whether skewness preference transfers from equities to crypto.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute scipy.stats.skew(returns[-LB:]) for each asset. Rank cross-sectionally. pos_skew_long: long highest skew, short lowest. neg_skew_long: opposite. Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS pos_skew_long **20/30 positive (66.7%)**, mean Sharpe 0.239. neg_skew_long only 6/30 (20.0%). **FAIL** IS < 80%. Best LB10_R5_N4 Sharpe 1.054 (+40.4% ann, -36.5% DD).
- Notes: Opposite of equity "lottery effect" — in crypto, positive-skew assets outperform (not underperform). This makes sense: crypto is momentum-driven, and positive-skew assets are those having breakout moves. But the signal is too weak and parameter-sensitive (66.7%) to be reliable. Skewness is not a viable XS factor in crypto.
- Sessions: [2026-04-02 session 127]

## H-186: Close Location Value (CLV) Factor (14 Assets)
- Status: REJECTED
- Idea: CLV = (2×close - high - low) / (high - low) measures where close sits within day's range. +1 = close at high (buyers won), -1 = close at low (sellers won). Rolling mean CLV captures persistent buying/selling pressure. Different from H-175 (money flow, uses open-close×volume) and H-183 (gap, overnight only).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute CLV per day, rolling mean over lookback. Rank cross-sectionally. high_clv_long: long top-N (persistent buying pressure), short bottom-N. Grid: LB∈[5,10,20,30,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS high_clv_long **17/30 positive (56.7%)**, mean Sharpe 0.121. low_clv_long 8/30 (26.7%). **FAIL** IS < 80%. Best LB20_R5_N4 Sharpe 1.315 (+50.1% ann, -20.3% DD).
- Notes: Intraday close position has very weak discriminatory power in crypto. Where the close sits within the HL range doesn't predict future cross-sectional returns. Likely because crypto is 24/7 — there's no "closing auction" effect that creates CLV patterns like in equities. The signal is near noise level (56.7%).
- Sessions: [2026-04-02 session 127]

## H-187: Rolling Sharpe Ratio as Cross-Sectional Factor (14 Assets)
- Status: REJECTED
- Idea: Use rolling Sharpe ratio (mean_ret/std_ret over lookback) as XS signal. Captures risk-adjusted momentum — combines return and vol into a single ratio. Different from H-012 (return only) and H-019 (vol only).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute rolling Sharpe = mean(ret[-LB:]) / std(ret[-LB:]). Rank cross-sectionally. high_sharpe_long: long top-N, short bottom-N. Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS high_sharpe_long **28/30 positive (93.3%)**, mean Sharpe 0.632, best LB10_R7_N4 Sharpe **1.627** (+66.8% ann, -33.0% DD). **PASS IS.** WF **3/5** positive (3.928, -5.320, 1.185, 3.965, -3.471), mean OOS 0.057. **FAIL WF.** Split-half H1=2.333, H2=1.292 (both positive, but H2 mean -0.097). Corr H-012 **0.373**, H-076 0.197, H-160 0.168.
- Notes: IS excellent (93.3%) and correlation with H-012 at 0.373 (below 0.50 = passing). However, WF exposes deep instability — two folds deeply negative (-5.32, -3.47). The risk-adjustment helps IS metrics but doesn't stabilize OOS performance. The Sharpe ratio is still fundamentally driven by returns (corr 0.373 with momentum). H2 mean sharpe negative suggests signal weakened in recent data. Not reliable enough.
- Sessions: [2026-04-02 session 127]

## H-188: Return-Volume Asymmetry Factor (14 Assets)
- Status: REJECTED
- Idea: Ratio of average volume on UP days to average volume on DOWN days over a rolling window. High ratio = bullish conviction (volume confirms up moves). Different from H-021 (total volume change) and H-167 (continuous vol-price correlation).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute avg_vol(up_days) / avg_vol(down_days) over lookback. Rank XS. up_vol_long: long high ratio (bullish conviction), short low ratio. Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS up_vol_long **25/30 positive (83.3%)**, mean Sharpe 0.249, best LB40_R7_N3 Sharpe **0.830** (+37.7% ann, -40.3% DD). **PASS IS.** WF **0/3** positive (3 folds N/A), mean OOS -1.616. **FAIL WF.** Split-half H1=1.106, H2=0.748 (both positive). Corr H-012 0.482 (borderline).
- Notes: IS passes but WF is a complete failure — 0/3 valid folds positive. Signal looks good historically but doesn't carry forward at all, classic overfitting pattern. The volume asymmetry between up/down days is too noisy to be a reliable XS discriminator. Short lookback combos (LB=10) performed terribly even in-sample.
- Sessions: [2026-04-02 session 128]

## H-189: Funding Rate Dispersion Factor (14 Assets)
- Status: CONFIRMED → LIVE (paper trade since 2026-04-02)
- Idea: Rolling standard deviation of 8-hourly funding rates as XS signal. Low dispersion = stable/consensus positioning. High dispersion = volatile/uncertain positioning. Long low-dispersion (stable consensus carries information), short high-dispersion.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute rolling std dev of funding rates over LB×3 periods (3 settlements/day). Rank XS. low_disp_long: long bottom-N (most stable), short top-N (most volatile). Grid: LB∈[5,10,20,30], R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos.
- Data: 14 assets, 752 daily bars + 2190 funding rate rows.
- Result: IS low_disp_long **22/24 positive (91.7%)**, mean Sharpe **0.583**, best LB20_R7_N3 Sharpe **1.489** (+63.9% ann, -34.1% DD). WF **4/6** positive, mean OOS **1.014** (folds: -1.95, 1.29, 2.28, 2.19, -2.50, 4.78). Split-half H1=2.124/H2=1.568 (both strong, mean 0.573/0.544). Corr H-012 **-0.033**, H-076 **-0.015**, H-160 **0.029**. Max corr **0.033**.
- Notes: Passes all 4/4 criteria convincingly. **Essentially zero correlation with all reference factors** — genuinely novel signal. Stable funding = informed consensus that carries directional edge. Volatile funding = confused/whipsawing positioning that underperforms. Two negative WF folds (Q1 2025, Q1 2026) may correspond to market regime shifts. Caveat: should check correlation with H-053 (funding level) before deploying. Best params LB20_R7_N3 stable across IS optimization.
- Sessions: [2026-04-02 session 128]

## H-190: Relative Range Position Factor (14 Assets)
- Status: REJECTED
- Idea: Position of current close within N-day high-low range: (close - low_N) / (high_N - low_N). Near 1 = near range top (breakout). Near 0 = near bottom (breakdown/oversold). Different from H-012 (raw returns), H-062 (distance from peak only), H-182 (range WIDTH).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute range_pos from rolling close min/max. Rank XS. high_pos_long: long near-top, short near-bottom. Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS high_pos_long **26/30 positive (86.7%)**, mean Sharpe 0.501, best LB30_R7_N3 Sharpe **1.609** (+75.9% ann, -25.9% DD). **PASS IS.** WF **2/3** positive (3 folds N/A due to LB60 warmup consuming OOS window), mean OOS 1.364. **FAIL WF** (2/3 < 4/6 threshold). Split-half H1=3.510, H2=1.190 (both positive). Corr H-012 0.231, H-076 -0.090, H-160 -0.006.
- Notes: Strong IS metrics and low correlations, but WF validation failed because the optimizer selected long lookback params (LB60) whose warmup period consumed the 90-day OOS windows, leaving only 3 evaluable folds. The 2 positive folds had strong Sharpes (2.60, 2.46) suggesting the signal may be real but can't be validated with current data length. Worth retesting when more data available.
- Sessions: [2026-04-02 session 128]

## H-191: Volume-Price Elasticity Factor (14 Assets)
- Status: CONFIRMED → LIVE (paper trade since 2026-04-02)
- Idea: Elasticity = |return| / normalized_volume. Measures how much price moves per unit of dollar volume. Low elasticity = institutional absorption / deep liquidity. High elasticity = thin/retail orderbooks.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance every 5-7 days)
- Logic: For each asset, compute daily elasticity = |close_ret| / (volume * close / avg_dollar_vol). Rolling mean over lookback. Rank XS. low_elast_long: long bottom-N (deep liquidity), short top-N (fragile). Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS low_elast_long **24/30 positive (80.0%)**, mean Sharpe **0.696**, best LB60_R7_N4 Sharpe **1.552** (+68.3% ann, -39.1% DD). WF **4/5** positive, mean OOS **1.728** (folds: 5.201, 1.695, N/A, 3.140, 2.202, -3.597). Split-half H1=**1.650**, H2=**2.404** (both strong). Corr H-012 **0.353**, H-076 **0.000**, H-160 **0.154**. Max corr 0.353.
- Notes: Novel microstructure signal. Assets with low price impact per volume unit (institutional depth) outperform fragile/thin assets. WF very strong with one negative fold (oldest data). Zero correlation with H-076 is notable — captures different aspect of market quality. Ready for paper trade deployment.
- Sessions: [2026-04-02 session 129]

## H-192: Intraday Return Dispersion Factor (14 Assets)
- Status: REJECTED
- Idea: Uses hourly data to compute std dev of hourly returns within each day, then averages ratio of intraday vol to daily vol over lookback. Captures microstructure noise level.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: For each asset, compute daily intraday_disp = std(hourly_returns). Rolling mean over lookback. Rank XS. high_disp_long: long noisiest, short quietest. Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS high_disp_long **26/30 positive (86.7%)**, mean Sharpe 0.431, best LB30_R7_N4 Sharpe **1.041** (+44.2% ann, -34.2% DD). **PASS IS.** WF **2/6** positive (0.166, -2.611, -4.846, -2.369, 2.460, -0.769), mean OOS **-1.328**. **FAIL WF.** Split-half H1=1.897, H2=2.349 (both positive). Corr H-012 0.100, H-076 0.032, H-160 -0.159. Max corr 0.159.
- Notes: WF is a catastrophe — consistently selected short lookback (LB10_R3_N3) in-sample which overfit badly OOS. The microstructure noise signal is interesting but extremely parameter-sensitive and unstable across time. Low correlations are a silver lining but not enough to overcome WF failure.
- Sessions: [2026-04-02 session 129]

## H-193: OI-Price Momentum Divergence Factor (14 Assets)
- Status: CONFIRMED → LIVE (paper trade since 2026-04-02)
- Idea: Compare OI momentum rank vs price momentum rank cross-sectionally. When price outpaces OI (divergence low) = healthy trend with de-leveraging. When OI outpaces price (divergence high) = crowded positioning without price follow-through.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance every 5-7 days)
- Logic: For each asset, compute OI_momentum = OI_pct_change(LB) and price_momentum = price_pct_change(LB). Rank each XS. Divergence = abs(OI_rank - price_rank). low_div_long: long lowest divergence (aligned momentum), short highest (misaligned). Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars + OI data (2024-03-11 to 2026-04-01).
- Result: IS low_div_long **26/30 positive (86.7%)**, mean Sharpe **0.694**, best LB20_R7_N3 Sharpe **1.774** (+75.6% ann, -28.9% DD). WF **4/5** positive, mean OOS **1.470** (folds: -0.415, 0.631, 1.066, 2.674, 3.393, N/A). Split-half H1=**2.196**, H2=**2.001** (both strong). Corr H-012 **0.380**, H-076 **0.056**, H-160 **0.262**. Max corr 0.380.
- Notes: Captures positioning quality — when OI and price momentum agree, the trend is healthy. When they diverge (OI building without price follow-through), positioning is crowded and vulnerable. Different from H-044 (OI-price divergence uses level changes, this uses momentum rank divergence). Uses OI data which adds a genuine new data source dimension. Ready for paper trade deployment.
- Sessions: [2026-04-02 session 129]

## H-194: Realized Vol Ratio Factor (14 Assets)
- Status: REJECTED
- Idea: Ratio of short-term realized volatility to long-term realized volatility as XS signal. Low ratio = vol compression (potential breakout). High ratio = vol expansion (mean reversion expected).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute vol_ratio = std(ret[-short:]) / std(ret[-long:]). Rank XS. Grid: SW∈[5,10,20], LW∈[30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 108 combos.
- Data: 14 assets, 1065 daily bars (2023-05-04 to 2026-04-02).
- Result: IS high_ratio_long **51/54 positive (94%)**, mean Sharpe 0.548, best SW5_LW60_R7_N4 Sharpe **1.379** (+62.9% ann, -30.2% DD). **PASS IS.** WF **0/6** positive, mean OOS **-1.168** (folds: -3.24, -0.65, -1.74, -0.12, -0.21, -1.04). **FAIL WF.** Corr H-012 -0.043, H-076 -0.005, H-160 0.014. Max corr 0.043.
- Notes: IS looked promising but WF is a complete disaster — 0/6 folds positive. Classic in-sample overfitting to regime-specific patterns that reverse OOS. Interesting finding: high_ratio_long won (opposite of original hypothesis — vol expansion assets outperform, not compressed ones). But this just exploits transient momentum in volatile assets, not robust. Very low correlation means genuine novelty, but orthogonal-and-unprofitable is not useful.
- Sessions: [2026-04-02 session 130]

## H-195: Funding Rate Reversal Factor (14 Assets)
- Status: REJECTED
- Idea: Short-term change in average funding rate as contrarian signal. Funding rate spike = crowd just piled in long → fade. Funding rate drop = crowd exiting → buy the dip. Different from H-053 (level) and H-171 (raw momentum) by using delta of averages.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute funding_change = mean(funding[-W*3:]) - mean(funding[-2W*3:-W*3]). Rank XS. drop_long: long bottom-N (biggest funding drop), short top-N (biggest spike). Grid: W∈[3,5,10,20], R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos.
- Data: 14 assets, funding rate data (8-hourly settlements).
- Result: IS drop_long **9/24 positive (38%)**, mean Sharpe **-0.531**. rise_long 2/24 (8%). **FAIL IS** (38% < 80%). Best drop_long W20_R3_N4 Sharpe 0.489 (+9.4% ann, -18.8% DD). Corr H-012 0.018, H-053 -0.009.
- Notes: Third funding momentum variant to fail (after H-130, H-171). Short-term changes in funding rate simply do not predict XS returns. Both directions deeply negative mean Sharpe. Novel (corr ~0 with H-053) but powerless. Funding rates in crypto are too noisy at short frequencies for momentum/reversal signals.
- Sessions: [2026-04-02 session 130]

## H-196: Dollar Volume Acceleration Factor (14 Assets)
- Status: REJECTED
- Idea: Second derivative of dollar volume — acceleration of volume growth. Assets with accelerating volume = accumulation/institutional interest building. Decelerating = fading interest.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: For each asset, compute vol_accel = (short_avg/med_avg) - (med_avg/long_avg) using 3 rolling windows. Rank XS. accel_long: long top-N, short bottom-N. Grid: SW∈[5,10], MW∈[20,30], LW∈[40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 96 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS accel_long **41/48 positive (85.4%)**, mean Sharpe 0.603, best S5_M30_L40_R5_N3 Sharpe **1.645** (+69.4% ann, -33.2% DD). **PASS IS.** WF **2/4** positive (1.97, -0.34, 3.30, -1.20), mean OOS 0.934. **FAIL WF.** Split-half H1=2.235/H2=2.630 (both strong). Corr H-012 0.091, H-021 **0.763**, H-076 0.107. Max corr **0.763**.
- Notes: Double failure: WF 2/4 (below 4/6) AND correlation 0.763 with H-021 (volume momentum). The second derivative of dollar volume is just a noisier version of the first derivative. Three-window structure doesn't extract a meaningfully different signal. Confirms that volume acceleration ≈ volume momentum in crypto.
- Sessions: [2026-04-02 session 130]

## H-197: Amihud Illiquidity Factor (14 Assets)
- Status: LIVE (paper trade since 2026-04-02)
- Idea: Amihud (2002) illiquidity measure = mean(|return| / dollar_volume) over lookback. Long the most liquid assets (low Amihud), short the most illiquid. "Flight to liquidity" factor in crypto.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute Amihud ratio per asset, rank XS. low_amihud_long: long most liquid N, short most illiquid N. Grid: LB∈[10,20,30,60], R∈[5,7,10,14], N∈[3,4,5], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS low_amihud_long **100% positive (30/30)**, mean Sharpe **1.537**, best LB10_R3_N4 Sharpe **1.895** (+89.8% ann, -29.7% DD). high_amihud_long 0% (0/30). **WF 5/6** positive (3.02, 0.47, 1.39, 2.86, 1.22, -0.65), mean OOS **1.387**. Split-half H1=1.911/H2=2.290 (both strong, H2 even better). Corr H-012 **0.488**, H-076 0.000, H-160 0.235. Max corr 0.488.
- Notes: Exceptionally robust — 100% IS positive is rare. Captures liquidity premium: liquid assets (large-cap BTC/ETH/etc) outperform illiquid ones. Borderline momentum correlation (0.488) makes economic sense — liquid = trending. But distinct signal (efficiency corr = 0.000). Paper trade deployed session 132: LONG BTC/ETH/SOL/XRP, SHORT LINK/OP/ARB/ATOM.
- Sessions: [2026-04-02 session 131, 2026-04-03 session 132 deploy]

## H-198: Price-MA Distance Factor (Mean Reversion, 14 Assets)
- Status: REJECTED
- Idea: Distance of price from its moving average (close/SMA - 1) as XS signal. Mean reversion: long oversold (below MA), short overbought (above MA). Or momentum: long above MA.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Factor = close / SMA(window) - 1. Rank XS. Grid: MA∈[5,10,20,30,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS below_ma_long (mean reversion) **3/30 positive (10%)**. above_ma_long (momentum) **20/30 positive (66.7%)**. Best: MA60_R7_N3 Sharpe 1.041 (+57.6% ann, -34.8% DD). **FAIL IS** (66.7% < 80%).
- Notes: Mean reversion is decisively wrong in crypto — buying below MA fails 90% of the time. Momentum direction works with long windows but not robust (short MA windows lose money). Likely redundant with H-012 momentum. Third mean-reversion variant to fail in crypto.
- Sessions: [2026-04-02 session 131]

## H-199: Consecutive Return Streaks Factor (14 Assets)
- Status: REJECTED
- Idea: Count consecutive positive/negative daily returns per asset. Cross-sectional: long assets with streaks (momentum continuation) or against streaks (mean reversion).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Signed streak count (+N for N up days, -N for N down days). Optional smoothing W∈[1,3,5,10]. Rank XS. Grid: W∈[1,3,5,10], R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS streak_long 7/24 positive (29.2%). contrarian_long 12/24 positive (50.0%). Best: W1_R7_N4 (contrarian) Sharpe 0.904 (+37.1% ann, -34.1% DD). **FAIL IS** (50% < 80%). Corr H-012 0.271 (low).
- Notes: Only raw streaks (W=1) produce any positive results — smoothing destroys signal. Even best direction is coin-flip robustness (50%). Too noisy and parameter-sensitive. Streak counting doesn't capture durable XS signal in crypto.
- Sessions: [2026-04-02 session 131]

## H-200: Return Autocorrelation Factor (14 Assets)
- Status: REJECTED
- Idea: Rolling lag-1 autocorrelation of daily returns as XS signal. Long trending assets (high positive autocorrelation), short mean-reverting/choppy assets (low/negative autocorrelation).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute rolling autocorrelation(lag=1) of daily returns. Rank XS. Grid: LB∈[10,20,30,60], R∈[3,5,7], N∈[3,4,5], dir∈2 = 72 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS high_autocorr_long **10/36 positive (27.8%)**, mean Sharpe -0.572. low_autocorr_long 8/36 (22.2%), mean Sharpe -0.348. Best: L60_R3_N5 Sharpe 0.822 (+28.7% ann, -25.8% DD). **FAIL IS** (27.8% < 80%). Corr H-012 0.209 (low).
- Notes: Only works at LB=60 (effectively slow momentum proxy). Short lookbacks (10, 20) produce deeply negative results (Sharpe as low as -2.4). Too parameter-sensitive. Autocorrelation is an unreliable XS discriminator in crypto.
- Sessions: [2026-04-03 session 132]

## H-201: Volume Imbalance Factor (Buy/Sell Pressure Proxy, 14 Assets)
- Status: REJECTED
- Idea: Approximate buy/sell pressure using fraction of hourly up-bars' volume to total daily volume. Long assets with highest buying pressure, short assets with lowest.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Buying pressure = sum(vol on close>open hours) / total daily vol. Rolling average. Rank XS. Grid: LB∈[5,10,20,30], R∈[3,5,7], N∈[3,4,5], dir∈2 = 72 combos.
- Data: 14 assets, 1066 daily bars (2023-05-03 to 2026-04-02).
- Result: IS high_buy_long **16/36 positive (44.4%)**, mean Sharpe -0.145. low_buy_long 0/36 (0%). Best: LB10_R5_N3 Sharpe 0.578 (+26.8% ann, -41.7% DD). **FAIL IS** (44.4% < 80%).
- Notes: Buying pressure metric clusters tightly (0.42-0.50) across assets — weak cross-sectional differentiation. Reverse direction (contrarian) produces zero positive combos. Short lookbacks noisy, transaction costs eat returns. Volume bar direction doesn't carry durable XS signal.
- Sessions: [2026-04-03 session 132]

## H-202: Intraday Volatility Clustering Factor (HHI, 14 Assets)
- Status: REJECTED
- Idea: Herfindahl index of hourly squared returns within each day. High HHI = concentrated volatility (institutional). Low HHI = diffuse (retail). Long concentrated, short diffuse.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: HHI = sum(share_i^2) where share_i = hourly_sq_ret / daily_sum_sq_ret. Rolling avg. Rank XS. Grid: LB∈[5,10,20,30], R∈[3,5,7], N∈[3,4,5], dir∈2 = 72 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS high_hhi_long **100% positive (36/36)**, mean Sharpe 0.935. low_hhi_long 0% (0/36). Best: LB5_R7_N5 Sharpe 2.149 (+68.6% ann, -16.9% DD). **PASS IS.** WF **5/6** positive (4.09, 2.15, 0.53, 0.44, -1.23, 1.56), mean OOS 1.256. **PASS WF.** Split-half H1=3.529 / **H2=-0.187. FAIL split-half.** Corr H-012 0.004 (essentially zero).
- Notes: Exceptional IS (100%) and WF (5/6, mean 1.256), essentially zero momentum correlation. But split-half reveals temporal instability: H1 Sharpe 3.53, H2 Sharpe -0.19. The factor worked brilliantly early but decayed. May reflect changing market microstructure. Could revisit if recent WF performance sustains.
- Sessions: [2026-04-03 session 132]

## H-203: Kurtosis / Excess Tail Risk Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by rolling kurtosis of daily returns. Long low-kurtosis (thin tails, well-behaved), short high-kurtosis (fat tails, crash-prone).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute rolling kurtosis over lookback window. Rank XS. Grid: LB∈[10,20,30,60], R∈[3,5,7], N∈[3,4,5], dir∈2 = 72 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS low_kurt_long **25/36 positive (69.4%)**, mean Sharpe 0.241. high_kurt_long 1/36 (2.8%), mean -0.615. Best: LB20_R7_N5 Sharpe 0.976 (+34.1% ann, -26.3% DD). **FAIL IS** (69.4% < 80%).
- Notes: Clear directional signal (low kurtosis outperforms) but too noisy at short lookbacks (LB10 consistently bad). Top combos cluster at LB20/LB30. Tail risk concept has merit but needs longer, more stable estimation windows than the crypto daily frequency allows.
- Sessions: [2026-04-03 session 133]

## H-204: Idiosyncratic Volatility Factor (14 Assets)
- Status: REJECTED
- Idea: After regressing each asset's returns on BTC (market factor), compute residual volatility. Long low-idio-vol (stable alpha generators), short high-idio-vol (noisy). Classic "idiosyncratic volatility puzzle" from equities.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Rolling OLS of asset returns on BTC returns. Idio-vol = std(residuals). Rank XS. Grid: LB∈[10,20,30,60], R∈[3,5,7], N∈[3,4,5], dir∈2 = 72 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS low_ivol_long **22/36 positive (61.1%)**, mean Sharpe 0.065. high_ivol_long 9/36 (25%), mean -0.296. Best: LB30_R7_N5 Sharpe 0.838 (+30.8% ann, -50.6% DD). **FAIL IS** (61.1% < 80%).
- Notes: Low-idio-vol outperformance exists in crypto but is highly lookback-dependent. Short windows (LB10/20) strongly negative, only LB30+ works. Consistent with equities literature where effect is regime-sensitive. Different from total vol (H-019) but not robust enough for XS factor.
- Sessions: [2026-04-03 session 133]

## H-205: Up/Down Volume Ratio Factor (14 Assets)
- Status: REJECTED
- Idea: Ratio of volume on up-days to volume on down-days over rolling window. High ratio = bullish conviction. Long high ratio, short low ratio.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: up_vol = sum(vol on days with ret>0), down_vol = sum(vol on days with ret<=0). Ratio = up_vol/down_vol. Rank XS. Grid: LB∈[10,20,30,60], R∈[3,5,7], N∈[3,4,5], dir∈2 = 72 combos.
- Data: 14 assets, 752 daily bars (2024-03-11 to 2026-04-01).
- Result: IS high_ratio_long **30/36 positive (83.3%)**, mean Sharpe 0.378. low_ratio_long 1/36 (2.8%), mean -0.740. Best: LB30_R7_N3 Sharpe 1.276 (+57.1% ann, -33.3% DD). **PASS IS.** WF **5/6** positive, mean OOS 0.403. **PASS WF.** Split-half H1=1.701/H2=1.786. **PASS split-half.** Corr H-012 **0.583** > 0.50. **FAIL correlation** — too redundant with momentum.
- Notes: Genuinely strong factor (passed IS, WF, and split-half). But high correlation with H-012 momentum (0.583) reveals it's largely a momentum proxy: assets going up naturally have more volume on up-days. Could serve as momentum confirmation signal but not standalone.
- Sessions: [2026-04-03 session 133]

## H-206: Hurst Exponent Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets cross-sectionally by Hurst exponent (R/S method). Assets with H > 0.5 are trending (persistent); H < 0.5 are mean-reverting. Long highest-H (most trending), short lowest-H (most mean-reverting).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Rolling R/S Hurst over lookback window. Rank XS. Long top-N, short bottom-N (high_hurst_long). Grid: LB∈[10,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 730 daily bars (2024-04-04 to 2026-04-03).
- Result: **IMPLEMENTATION BUG**: R/S method requires ≥3 sub-period sizes, but for LB≤40, max_k=LB//2≤20, log-spaced sizes only [10,15] → all Hurst values default to 0.5. This makes LB≤40 combos a disguised **size factor** (fixed alphabetical positions: LONG BTC/ETH/SOL/SUI, SHORT NEAR/OP/ARB/ATOM). The apparent WF 6/6 and Sharpe 2.26 were artifacts. **At LB=60 where real Hurst is computed**: 6/6 combos positive (IS Sharpe 0.79-1.25), WF **5/6** positive but mean OOS only **0.587**. **Split-half FAILS**: H1=2.569, H2=**-0.324**. Corr H-012: 0.157 (good). Fold 4 = -4.87 (catastrophic).
- Notes: Fourth test of Hurst/persistence XS factor (after H-116, H-168, H-172). At LB=60, there's a weak trending-long signal (all combos positive IS), but it fails split-half stability (recent period negative). The R/S computation is very sensitive to implementation details. Also confirms H-116's "CONDITIONAL" status should be resolved as REJECTED — signal too unstable.
- Sessions: [2026-04-03 session 134]

## H-208: Short-Term Reversal Factor (14 Assets)
- Status: REJECTED
- Idea: Classic equity anomaly — rank assets by 1-5 day returns, long biggest losers, short biggest winners (contrarian). Also tests momentum direction.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D
- Logic: Grid: LB∈[1,2,3,5], R∈[1,2,3,5], N∈[3,4], dir∈[reversal,momentum] = 64 combos. 5bps fee per trade (one-way).
- Data: 14 assets, 730 daily bars (2024-04-04 to 2026-04-03).
- Result: IS hit rate **26.6%** (17/64 combos positive). Mean Sharpe -0.470. Reversal mean -0.074 (44% positive), momentum mean -0.865 (9% positive). Best single combo: LB3_R3_N4_REV Sharpe 1.505 (+74% ann, -23.4% DD) — but highly cherry-picked. **FAIL IS < 80%.** Signal is extremely parameter-sensitive; only the LB=2-3, R=3-5, N=3-4 reversal window shows any life. Prior H-109 also rejected with similar findings (IS 75%, OOS -0.199).
- Notes: Short-term reversal does not robustly work across this asset universe and parameter space. The single standout combo (LB3_R3_N4_REV) is likely data-mined. Both this test and H-109 confirm crypto short-term reversal is not a stable cross-sectional anomaly with this universe/timeframe.
- Sessions: [2026-04-03 session 134]

## H-209: Price-Volume Correlation Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by rolling correlation between daily returns and daily volume changes. High correlation = price-volume coupling; low = decoupled dynamics.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Rolling Pearson correlation of log-returns vs log-volume-changes over lookback. Rank XS. Grid: LB∈[10,20,30,60], R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos.
- Data: 14 assets, 730 daily bars (2024-04-04 to 2026-04-03).
- Result: IS 58.3% in dominant direction (pos_corr_long), mean Sharpe 0.178. Best single: LB10_R7_N4 Sharpe 0.916 (+29.5% ann, -37.1% DD). LB=10 and LB=60 show some signal (5-6/6 positive), LB=20-30 weak (1-2/6). **FAIL IS < 80%.** Direction inconsistency across lookbacks — short lookback and very long lookback give opposite results from mid-range.
- Notes: Price-volume coupling is not a robust XS factor. The signal at LB=10 (recent coupling) and LB=60 (long-term coupling) work but mid-range lookbacks fail, suggesting no true underlying effect.
- Sessions: [2026-04-03 session 135]

## H-210: RSI Dispersion Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by standard deviation of daily RSI(14) over a lookback window. Low RSI dispersion = consistent trend; high = choppy/oscillating.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Rolling std of RSI(14) values over lookback. Rank XS. Grid: LB∈[10,20,30,60], R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos.
- Data: 14 assets, 730 daily bars (2024-04-04 to 2026-04-03).
- Result: IS 83.3% in dominant direction (high_disp_long, 20/24 combos positive), mean Sharpe 0.387. Best: LB60_R3_N3 Sharpe 1.281 (+64.0% ann, -41.1% DD). **WF 3/6 FAILS** (need ≥4). Fold sharpes: [-0.16, 1.82, -0.13, 0.16, -0.62, 3.35]. Recent folds negative = signal deteriorating. Counterintuitively, high RSI dispersion (choppy assets) outperform — likely a volatility proxy at LB=60.
- Notes: IS passes marginally (83.3%) but OOS stability fails. The high_disp direction is counterintuitive and likely captures size/vol effects rather than genuine RSI consistency signal. Third factor related to trend consistency to fail (after H-160 CONDITIONAL, H-076 confirmed with different construction).
- Sessions: [2026-04-03 session 135]

## H-211: Market Coupling / R² Factor (13 Non-BTC Assets)
- Status: REJECTED
- Idea: Rank non-BTC assets by rolling R² of their returns vs BTC returns. High R² = tightly coupled to BTC (market co-mover); low R² = independent mover.
- Instrument: futures (13 USDT perps, BTC excluded from ranking)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Rolling R² (correlation²) of asset vs BTC returns. Rank XS. Grid: LB∈[20,30,60], R∈[3,5,7], N∈[3,4], dir∈2 = 36 combos.
- Data: 14 assets (13 ranked), 730 daily bars (2024-04-04 to 2026-04-03).
- Result: IS 50.0% in dominant direction (low_r2_long), mean Sharpe 0.003 — essentially zero. Best single: LB30_R7_N4_high_r2 Sharpe 0.415 (+9.0% ann, -57.6% DD). **FAIL IS << 80%.** Neither direction produces meaningful cross-sectional differentiation. R² with BTC has no predictive power.
- Notes: BTC coupling is essentially constant across most altcoins (all highly correlated with BTC). The cross-sectional spread in R² is too small to generate a tradeable signal. Related to but distinct from beta (H-024, magnitude not R²) — both fail.
- Sessions: [2026-04-03 session 135]

## H-212: Relative Volume Rank Persistence (14 Assets)
- Status: REJECTED
- Idea: Assets whose daily dollar-volume rank (relative to the 14-asset cross-section) is persistent over time (high lag-1 autocorrelation of rank series) outperform those with erratic volume rankings. Persistent volume ranking suggests stable institutional interest.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Each day, rank assets by dollar volume. Compute lag-1 autocorrelation of volume rank over lookback window. Long top N (most persistent), short bottom N. Grid: LB∈[10,15,20,30,40], R∈[3,5,7], N∈[3,4] = 30 combos.
- Data: 14 assets, 730 daily bars (2024-04-04 to 2026-04-03).
- Result: IS 13/30 positive (43.3%) — **FAIL IS << 80%**. Mean Sharpe -0.169. Best single: LB15_R7_N4 Sharpe 0.878 (+28.3% ann, -25.9% DD). LB=10 strongly negative (Sharpe -0.9 to -1.3). Signal is highly parameter-sensitive — performance swings from -1.28 to +0.88 depending on lookback.
- Notes: The rank autocorrelation at short windows captures transient rank shuffling (noise) rather than structural persistence. Only LB=15 shows consistent positive signal but it's a single cherry-picked point, not robust.
- Sessions: [2026-04-03 session 136]

## H-213: Intrabar Momentum Consistency (CLV Persistence)
- Status: REJECTED
- Idea: Rolling mean of Close Location Value (CLV = (2*close - high - low)/(high-low)) as a cross-sectional persistence signal. Assets persistently closing near their daily high (high mean CLV) have sustained buying pressure and outperform.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute daily CLV per asset, take rolling mean over lookback. Rank XS: long top N (high mean CLV), short bottom N. Dollar-neutral equal weight. Grid: LB∈[5,10,15,20,30], R∈[3,5,7], N∈[3,4] = 30 combos.
- Data: 14 assets, 730 daily bars (2024-04-04 to 2026-04-03).
- Result: IS 20/30 combos positive (66.7%) — **FAIL IS < 80%**. Mean Sharpe 0.345, median 0.344. Best single: LB15_R7_N3 Sharpe 1.444 (+65.8% ann, -34.0% DD). Short-LB combos (LB5/10) mostly negative (7/12 negative), dragging overall pass rate below threshold. Smoothing helps but only at medium lookbacks (15-20d). Related: H-186 (raw CLV, 56.7% IS, REJECTED) — this approach improves on raw CLV but still insufficient.
- Notes: The signal polarizes sharply with lookback: short windows (5-10d) flip negative while longer windows (15-30d) are consistently positive (all 12 LB15-20 combos positive). The all-or-nothing IS criterion masks a real medium-lookback effect. Could be revisited with LB∈[15,20,30] only (12/12 positive in that sub-grid), but that would be curve-fitting the parameter selection.
- Sessions: [2026-04-03 session 136]

## H-214: Downside Tail Risk Factor / CVaR (14 Assets)
- Status: REJECTED
- Idea: Assets with lower downside tail risk (5% CVaR / Expected Shortfall) outperform those with extreme left-tail risk. Crypto analogue of low-vol anomaly focused on tail behavior — investors overcompensate for tail risk.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute rolling 5% CVaR (mean of returns below 5th percentile). Rank XS: long top N (lowest tail risk = least negative CVaR), short bottom N. Grid: LB∈[20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos.
- Data: 14 assets, 730 daily bars (2024-04-04 to 2026-04-03).
- Result: IS **100%** positive in low_tail_long direction (24/24), mean Sharpe 1.028. Best: LB20_R7_N4 Sharpe 1.611 (+69.5% ann, -25.8% DD). Split-half consistent (H1 2.474, H2 2.543). **BUT**: WF only 3/4 folds positive (data-length limits to 4 folds, not 6). **AND**: Corr with H-019 (low-vol) = **0.649** — too redundant. Corr with H-012 = 0.354.
- Notes: Strong standalone signal that IS passes beautifully, but fundamentally captures the same low-vol anomaly as H-019 through a different lens. In this 14-coin universe, CVaR and simple volatility co-move heavily (r=0.65). A larger universe might reduce overlap but we don't have it. Redundant with existing H-019.
- Sessions: [2026-04-03 session 136]

## H-215: Dollar Volume Trend Factor (14 Assets)
- Status: CONFIRMED → LIVE (paper trade deployed 2026-04-03)
- Idea: Rank assets by OLS slope of log(dollar_volume) over a lookback window. Steepest increasing trend (growing interest) → long, steepest decreasing (fading) → short. Captures flow-of-funds direction, distinct from H-021 (volume ratio) and H-031 (size level).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance every 3 days)
- Logic: Compute daily dollar_volume = close * volume. Fit OLS slope to log(DV) over lookback window. Rank XS. Long top-N, short bottom-N. Grid: LB∈[10,15,20,30,40,60], R∈[3,5,7], N∈[3,4] = 36 combos.
- Data: 14 assets, 730 daily bars (2024-04-04 to 2026-04-03).
- Result: IS **94.4%** positive (34/36), mean Sharpe 0.705. Best: LB15_R3_N4 Sharpe **1.668** (+65.2% ann, -21.8% DD). WF **4/6** positive, mean OOS **0.016** (marginal but positive). Split-half H1=**2.388**, H2=**1.565** (strong both halves). Corr H-012 **0.148** (very low — genuinely novel signal).
- Notes: Very strong IS and split-half. WF mean barely positive (0.016) — recent fold volatility means some parameter instability. But corr 0.148 with momentum is excellent novelty. Deployed as paper trade #28, LB15_R3_N4 params.
- Sessions: [2026-04-03 session 137]

## H-216: Kurtosis Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by excess kurtosis of daily returns. Long low-kurtosis (thin tails, more Gaussian), short high-kurtosis (fat tails, crash-prone). Shape-of-distribution factor distinct from vol level.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute rolling Fisher excess kurtosis. Rank XS. Grid: LB∈[15,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 730 daily bars (2024-04-04 to 2026-04-03).
- Result: IS **40.0%** < 80% threshold. Low-kurtosis-long: 76.7% positive (23/30), mean 0.313. High-kurtosis-long: 3.3% positive (1/30), mean -0.647. Best: LB30_R5_N4_low_kurt_long Sharpe 1.088.
- Notes: Low-kurtosis-long direction shows signal (76.7%) but fails IS threshold. In 14-asset crypto universe, kurtosis doesn't vary enough XS to create reliable ranking — all crypto is fat-tailed. Signal too weak and unstable.
- Sessions: [2026-04-03 session 137]

## H-217: Volume/OI Ratio — Speculative Activity Factor (14 Assets)
- Status: REJECTED
- Idea: Volume/OI ratio measures speculative churning vs sticky positioning. High V/OI = speculative daytrading. Low V/OI = longer-term holders.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute rolling avg(volume/OI). Rank XS. Grid: LB∈[5,10,15,20,30], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 730 daily bars + 1000 OI rows, all 14 assets.
- Result: IS **48.3%** < 80% threshold. Low-VOI-long: 0% (0/30) — completely wrong direction. High-VOI-long: **96.7%** (29/30), mean 0.780, best LB5_R5_N4 Sharpe 1.607. Clear one-directional signal but fails combined IS gate.
- Notes: Strong signal in high-V/OI-long direction (96.7%, best Sharpe 1.607). In crypto, high speculative activity = momentum confirmation, not noise. Interesting finding but combined IS fails protocol threshold. Could revisit as direction-fixed factor.
- Sessions: [2026-04-03 session 137]

## H-218: Rolling Beta Change Factor (13 Non-BTC Assets)
- Status: REJECTED
- Idea: Rank by change in rolling beta to BTC (short window minus long window). Assets decorrelating from BTC may have idiosyncratic alpha. Differs from static beta (H-024) and alpha momentum (H-169).
- Instrument: futures (14 USDT perps, ranking 13 non-BTC)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute rolling beta to BTC over short (10-20d) and long (30-60d) windows. Beta change = short_beta - long_beta. Rank XS: two directions tested (dec_long, inc_long). Grid: SW∈[10,15,20], LW∈[30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 108 combos.
- Data: 14 assets, 730 daily bars (2024-04-04 to 2026-04-03).
- Result: IS **40.7%** < 80%. dec_long: 27.8% (15/54), inc_long: 53.7% (29/54). Best: SW10_LW40_R5_N3_inc_long Sharpe 1.087 (+50.2% ann, -48.9% DD). Neither direction passes IS threshold.
- Notes: Interestingly, increasing beta (more coupled to BTC) slightly outperforms decreasing beta — opposite of the initial hypothesis. But 53.7% pass rate is insufficient. Beta dynamics in this 14-coin universe are too noisy for reliable XS ranking. Crypto coins are all highly correlated to BTC (beta near 1) so changes are small and noisy.
- Sessions: [2026-04-03 session 138]

## H-219: Up-Volume Ratio Factor (14 Assets)
- Status: CONFIRMED
- Idea: Ratio of volume on positive-return days to total volume over lookback. Assets with dominant buying volume (high up-vol ratio) outperform. Distinct from H-021 (volume change), H-175 (price-weighted money flow), H-012 (price momentum).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Classify each day as up (return > 0) or down. Compute rolling up-vol ratio = sum(vol on up days)/sum(total vol). Rank XS. Grid: LB∈[10,15,20,30,40], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 730 daily bars (2024-04-04 to 2026-04-03).
- Result: IS **80.0%** in upvol_long (24/30). downvol_long 0% (0/30) — clear directional signal. Best: LB10_R7_N3 Sharpe **1.177** (+53.1% ann, -43.5% DD). WF **4/6** mean OOS **0.204**. Split-half H1=**1.266**, H2=**2.097**. Corr H-012 **0.157** (very low — genuinely novel signal).
- Notes: Very clean one-directional signal. Upvol_long passes IS threshold exactly at 80% while downvol_long is completely wrong (0%). WF mean positive at 0.204 with fold 2 being the outlier at -5.1. Split-half robust in both halves. The 0.157 correlation with momentum confirms this captures something distinct — volume *composition* rather than volume level or price direction. Worth deploying.
- Sessions: [2026-04-03 session 138]

## H-220: Short-Term Reversal Factor (14 Assets)
- Status: REJECTED
- Idea: Classic market microstructure reversal — long recent (1-5 day) losers, short recent winners. Overreaction/mean-reversion at short horizons. Well-documented in equities; testing in crypto.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 1-5 days)
- Logic: Compute trailing return over lookback (1-5d). Rank XS: reversal = long losers/short winners, momentum = long winners/short losers. Grid: LB∈[1,2,3,5], R∈[1,2,3,5], N∈[3,4], dir∈2 = 64 combos.
- Data: 14 assets, 730 daily bars (2024-04-04 to 2026-04-03).
- Result: IS **25.0%** overall. Reversal: 37.5% (12/32), mean -0.172. Momentum: 12.5% (4/32), mean -0.912. Best: LB3_R3_N4_reversal Sharpe 0.987 (+45.0%, -41.2% DD). Both directions fail IS.
- Notes: Reversal slightly better than short-term momentum (37.5% vs 12.5%), confirming mild mean-reversion exists at 2-3 day horizon. But 37.5% is far below 80% threshold. Transaction costs destroy much of the edge (daily rebalancing at 10bps round-trip). Crypto markets are too momentum-driven even at short horizons — equities-style reversal doesn't translate. The LB3_R3 sweet spot suggests 3-day windows have the most reversal but it's too parameter-specific.
- Sessions: [2026-04-03 session 138]

## H-221: Return Skewness Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by trailing return skewness. Positive skew (occasional big up moves) should signal different risk profiles. Well-documented factor in equities.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute scipy.stats.skew of daily returns over lookback window. Rank XS. Grid: LB∈[10,15,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 72 combos.
- Data: 14 assets, 1068 daily bars (2023-05-03 to 2026-04-04).
- Result: IS **61.1%** in high_long direction (positive skew long) < 80%. low_long 22.2%. Best: LB10_R5_N3_high_long Sharpe 1.665 (+107.4%, -27.7% DD). Overall 41.7%.
- Notes: Positive skew → long shows some signal (61.1%) but too parameter-sensitive. Short lookbacks work better (LB10 best) suggesting skew is a fast-decaying signal. Low_long (negative skew long) completely fails — confirms positive skew is the right direction but the effect isn't robust enough in crypto. The best single param set looks great (Sharpe 1.67) but it's a cherry-pick.
- Sessions: [2026-04-04 session 139]

## H-222: Volume Volatility Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by coefficient of variation (CV) of daily volume. High CV means erratic trading interest (fragile), low CV means stable volume (robust). Could capture stability premium.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: CV = std(volume) / mean(volume) over lookback. Rank XS. Grid: LB∈[10,15,20,30,40], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 1068 daily bars (2023-05-03 to 2026-04-04).
- Result: IS **60.0%** in high_long (high CV long) < 80%. low_long 23.3%. Best: LB30_R7_N4_high_long Sharpe 0.476 (+21.9%, -43.0% DD). Overall 41.7%.
- Notes: High volume volatility → long marginally works (60%) suggesting erratic-volume coins have momentum-like behavior, but effect is not robust. The absolute best Sharpe is only 0.476 — even cherry-picked results are weak. Volume CV doesn't discriminate well across a 14-coin universe; most cryptos have similarly erratic volume patterns.
- Sessions: [2026-04-04 session 139]

## H-223: Momentum Breadth / Win Rate Factor (14 Assets)
- Status: CONFIRMED
- Idea: Rank assets by fraction of positive-return days over lookback window (win rate). High win rate (consistent upward drift) → long. Low win rate (consistent downward drift) → short. Different from momentum (total return) — captures *consistency* of direction.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 5 days)
- Logic: Win_rate = count(daily_return > 0) / lookback. Rank XS: high win rate → long, low → short. Grid: LB∈[10,15,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 72 combos.
- Data: 14 assets, 1068 daily bars (2023-05-03 to 2026-04-04).
- Result: IS **83.3%** high_long (30/36). low_long 19.4% (decisively wrong). Best: LB20_R5_N3_high_long Sharpe **1.218** (+79.7% ann, -44.1% DD). WF **5/6** mean OOS **1.120**. Split-half H1=**1.416**, H2=**0.994**. Corr H-012 **0.365** (moderate — some overlap with momentum but distinct signal).
- Notes: Win rate captures *consistency* of positive returns, distinct from total return magnitude (momentum). An asset can have high momentum from one big jump but low win rate, or steady small gains with high win rate. The 0.365 correlation with H-012 is expected (both capture bullish tendencies) but low enough to add value. WF is strong at 5/6 with mean 1.120 — only fold 4 negative (-0.359). Split-half robust in both halves. Direction is unambiguous: high_long 83.3% vs low_long 19.4%.
- Sessions: [2026-04-04 session 139]

## H-224: ADX / Trend Strength Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by Average Directional Index (ADX), which measures trend strength regardless of direction. High ADX = strong trend -> long (trend followers win). Low ADX = choppy -> short.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute Wilder's ADX per asset over rolling window. Rank XS: high_adx_long vs low_adx_long. Grid: ADX_period∈[7,14,20,30], R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS dom dir **95.8%** high_adx_long (23/24). IS overall 47.9%. Best ADX7_R7_N4 Sharpe 1.324 (+49.3% ann, -20.7% DD). WF **3/5** (fails ≥4). Split-half H1=2.045, H2=2.074. Corr H-012 0.190.
- Notes: Strong directional signal (95.8% high_adx_long) — trending assets DO continue trending in crypto. However WF inconsistent at 3/5 — fold 1 has -4.35 OOS, fold 4 has -0.74. Signal has right intuition but doesn't generalize OOS consistently. ADX computation is noisy in 24/7 crypto markets (no session-based structure). Interesting that low_adx_long is 0% positive — decisively wrong direction.
- Sessions: [2026-04-04 session 140]

## H-225: Volume-Price Trend (VPT) Factor (14 Assets)
- Status: REJECTED
- Idea: VPT = cumulative(volume * pct_change). Rank by rolling VPT slope (linear regression). High VPT slope = sustained buying pressure -> long. Different from OBV (binary up/down volume) and money flow (OHLC-weighted).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Compute VPT, then rolling linear regression slope over lookback. Normalize by mean volume. Rank XS. Grid: LB∈[10,15,20,30,40], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS dom dir **100.0%** high_vpt_long (30/30). IS overall 50.0%. Best LB20_R7_N3 Sharpe 1.384 (+70.2% ann, -28.6% DD). WF **4/6** mean 0.673. Split-half H1=2.224, H2=1.296. Corr H-012 **0.654** (too high, FAIL).
- Notes: VPT slope is essentially volume-weighted momentum — the correlation with H-012 (0.654) confirms it's not a novel signal. It captures the same "winners keep winning" effect, just weighted by volume intensity. Despite passing IS (100%!), WF (4/6), and split-half, the high correlation means it adds no diversification value. Would be redundant in any portfolio already containing H-012.
- Sessions: [2026-04-04 session 140]

## H-226: Ease of Movement (EMV) Factor (14 Assets)
- Status: REJECTED
- Idea: EMV = midpoint_displacement / (volume / HL_range). Measures how easily price moves — high EMV = trending smoothly with little volume resistance. Cross-sectional ranking.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: EMV = (mid - prev_mid) * HL_range / volume. Rolling mean over lookback. Rank XS. Grid: LB∈[10,15,20,30,40], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS overall 43.3%, dom dir high_emv_long **76.7%** < 80%. Best LB30_R5_N3 Sharpe 1.010 (+43.4% ann, -50.2% DD).
- Notes: EMV fails IS threshold — 76.7% is close but not enough. The signal is weakly directional (high EMV assets do slightly better) but the effect is too noisy in crypto's 24/7 markets. In equities, EMV works because of opening/closing auction microstructure — crypto lacks this. Additionally, the drawdowns are severe (50%+) even for the best params.
- Sessions: [2026-04-04 session 140]

## H-227: Relative Strength vs BTC Factor (13 Non-BTC Assets)
- Status: REJECTED
- Idea: Rank altcoins by rolling return relative to BTC over a lookback window. Long outperformers, short underperformers. Captures "alpha" vs the dominant crypto asset.
- Instrument: futures (13 non-BTC USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: RS = alt_return(LB) - BTC_return(LB). Rank XS. Grid: LB∈[10,15,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 72 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS overall 47.2%, dom dir high_rs_long **91.7%**. Best LB60_R5_N3 Sharpe 1.038 (+57.6% ann, -31.1% DD). **WF 1/3** (only 3 folds produced results, only 1 positive). Corr with H-012: **0.923** — nearly identical to momentum.
- Notes: Relative strength vs BTC is essentially momentum in disguise. The 0.923 correlation with H-012 confirms that ranking by altcoin returns relative to BTC produces nearly the same portfolio as ranking by absolute returns. This makes sense: BTC's return is the same for all alts, so subtracting it preserves the relative ranking. The WF also failed badly (1/3). Not a useful independent signal.
- Sessions: [2026-04-04 session 141]

## H-228: Close Location Value (CLV) Persistence Factor (14 Assets)
- Status: REJECTED
- Idea: Rolling average CLV = (close - low) / (high - low) over lookback window. Assets consistently closing near highs have sustained buying pressure. Smoothed version of earlier H-124 CLV attempt.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: CLV = (close - low) / (high - low). Rolling mean over lookback. Rank XS. Grid: LB∈[5,10,15,20,30], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS overall 40.0%, dom dir high_clv_long **70.0%** < 80%. Best LB15_R7_N3 Sharpe 1.450 (+68.3% ann, -31.7% DD).
- Notes: CLV fails IS threshold at both levels (40% overall, 70% dominant direction). The signal has some promise in the best param combos but is too parameter-sensitive. 30% of high_clv_long combos are negative. In crypto's continuous 24/7 market, close location may be less meaningful than in equities with opening/closing sessions. Second attempt (after H-124) — signal consistently fails.
- Sessions: [2026-04-04 session 141]

## H-229: Volume Autocorrelation Factor (14 Assets)
- Status: REJECTED
- Idea: Rolling first-order autocorrelation of daily volume over a lookback window. High volume autocorrelation = persistent/institutional flows. Cross-sectional ranking.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: AC1 = corr(vol[t-1:t-LB], vol[t:t-LB+1]) over rolling window. Rank XS. Grid: LB∈[10,15,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 72 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS overall 41.7%, dom dir high_autocorr_long **52.8%** < 80%. Best LB15_R5_N3_low_autocorr Sharpe 0.887 (+39.7% ann, -34.1% DD).
- Notes: Volume autocorrelation has essentially no cross-sectional predictive power. Neither direction dominates (52.8% vs 30.6%). All crypto assets likely have similar volume autocorrelation structures (driven by 24h cycles), so cross-sectional dispersion is minimal. The weak signal that exists is noisy and not robust. Dead end for this universe.
- Sessions: [2026-04-04 session 141]

## H-230: Return Autocorrelation Factor (14 Assets)
- Status: REJECTED
- Idea: Rolling first-order autocorrelation of daily returns over a lookback window. High autocorrelation = trending behavior. Cross-sectional ranking: long trending, short mean-reverting.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: AC1 = corr(ret[t-1:t-LB], ret[t:t-LB+1]) over rolling window. Rank XS. Grid: LB∈[10,15,20,30], R∈[3,5,7], N∈[3,4] = 24 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS overall **16.7%** (4/24 positive). Mean Sharpe **-0.889**. Best LB20_R7_N3 Sharpe 0.097 (+2.3% ann). Dominant direction: high_autocorr_long only 4/24 positive. Strongly negative at short lookbacks (LB10 worst: Sharpe -2.3).
- Notes: Return autocorrelation has essentially no cross-sectional predictive power. Crypto returns are noisy and daily autocorrelation is near zero for all assets, so cross-sectional dispersion is minimal. Short lookbacks amplify noise. Dead end.
- Sessions: [2026-04-04 session 142]

## H-231: Close Location in Range Factor (14 Assets)
- Status: REJECTED
- Idea: Average (Close - Low)/(High - Low) over N days. Long assets consistently closing near daily high (accumulation). Short assets closing near daily low (distribution).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: CLR = (C-L)/(H-L) averaged over lookback. Rank XS. Grid: LB∈[5,10,15,20,30], R∈[3,5,7], N∈[3,4] = 30 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS overall **73.3%** (22/30 positive). Mean Sharpe 0.301. Best LB15_R7_N4 Sharpe **1.553** (+32.7% ann, -20.5% DD). Dominant direction: high_clr_long Sharpe 1.55 vs low_clr_long -1.99. BUT short lookbacks (5-10d) all negative — signal is parameter-sensitive, fails <80%.
- Notes: Close to passing but too parameter-sensitive. Short-lookback CLR (5-10d) is pure noise. Only moderate-to-long lookbacks (15-30d) work, which already overlap with momentum signals. The signal captures buying pressure but is not robust enough across the parameter space.
- Sessions: [2026-04-04 session 142]

## H-232: Parkinson Range Ratio Factor (14 Assets)
- Status: REJECTED
- Idea: Compare Parkinson (range-based) volatility to close-to-close volatility. Low ratio = efficient clean trends. High ratio = noisy intraday reversals. Long efficient, short noisy.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Ratio = sqrt(ParkVar / CCVar) over lookback. Rank XS. Grid: LB∈[10,15,20,30,40], R∈[3,5,7], N∈[3,4] = 30 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS overall **0.0%** (0/30 positive). Mean Sharpe **-0.647**. Best LB10_R7_N3 Sharpe -0.223. Neither direction works (low_ratio_long -0.223, high_ratio_long -0.402).
- Notes: Complete failure. In 24/7 crypto markets, all assets have similarly high Parkinson-to-CC ratios due to continuous trading. Cross-sectional dispersion in this ratio is minimal and has no predictive power for future returns. The microstructure efficiency concept doesn't differentiate assets in this universe.
- Sessions: [2026-04-04 session 142]

## H-233: Relative Volume (Abnormal Volume) Factor (14 Assets)
- Status: REJECTED
- Idea: Ratio of short-term average volume (N days) to long-term average volume (M days). High relative volume = interest surge, information event. Cross-sectional ranking: long high relative volume, short low relative volume.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: RelVol = SMA(vol, SW) / SMA(vol, LW). Rank XS. Grid: SW∈[3,5,7,10], LW∈[20,30,40], R∈[3,5,7], N∈[3,4], directions = 144 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS overall **0.0%** (0/144 positive). Mean Sharpe **-1.502**. Best SW10_LW40_R7_N3_high_long Sharpe -0.495 (-11.8% ann, -39.9% DD). Neither direction works: high_long 0/72, low_long 0/72.
- Notes: Complete failure. Relative volume has zero cross-sectional predictive power in crypto. All assets show similar volume dynamics (correlated with BTC-driven market-wide activity), so the cross-sectional dispersion carries no alpha.
- Sessions: [2026-04-04 session 143]

## H-234: Consecutive Return Direction / Win Rate Factor (14 Assets)
- Status: REJECTED
- Idea: Count of positive daily returns over N-day rolling window (win rate). Long assets with high win rate (consistent upward momentum), short assets with low win rate. Also tested contrarian.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: WinRate = count(ret > 0) / lookback over rolling window. Rank XS. Grid: LB∈[5,7,10,15,20], R∈[3,5,7], N∈[3,4], directions = 60 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS overall **15.0%** (9/60 positive). Mean Sharpe **-0.547**. Best LB7_R3_N4_low_long Sharpe 1.233 (+22.2% ann, -14.4% DD). high_long 0/30, low_long 9/30 (30%).
- Notes: Fails IS. Conceptually similar to H-223 (momentum breadth) which already passed at LB20. Short lookbacks (5-7d) show some contrarian edge but not robust. The daily win-rate signal doesn't capture enough cross-sectional dispersion to be tradeable. H-223's specific parameter choice (LB20_R5_N3) works but the broader parameter space doesn't — confirming H-223 was at the edge of viability.
- Sessions: [2026-04-04 session 143]

## H-235: Funding Rate Change / Delta Factor (14 Assets)
- Status: REJECTED
- Idea: Change in average funding rate (short-window avg minus long-window avg). Long assets where funding is decreasing (crowd de-leveraging = contrarian buy), short assets where funding is increasing (crowd getting more leveraged).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 5-7 days)
- Logic: FundDelta = SMA(funding, SW) - SMA(funding, LW). Rank XS. Contrarian: low_long. Grid: SW∈[3,5,7], LW∈[14,21,30], R∈[5,7], N∈[3,4], directions = 72 combos.
- Data: 14 assets, 730 daily bars. Funding rate data from Bybit API.
- Result: IS overall **38.9%** (28/72 positive). Mean Sharpe **-0.248**. Best SW3_LW30_R7_N4_low_long Sharpe 1.016 (+16.6% ann, -14.4% DD). high_long 0/36, **low_long 28/36 (77.8%)** — close to 80% but not passing.
- Notes: Contrarian direction (low_long) at 77.8% is the closest near-miss. The signal captures crowd de-leveraging dynamics, but funding rates in crypto are noisy and the short-term vs long-term delta doesn't consistently predict returns cross-sectionally. Funding level (H-053) works better than funding change.
- Sessions: [2026-04-04 session 143]

## H-236: Return Co-Skewness Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by co-skewness with the equal-weight market portfolio. Assets with negative co-skewness (crash with market) should command higher returns as tail-risk compensation. From Harvey-Siddique (2000).
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: CoSkew = E[r_i * r_m^2] / (std(r_i) * std(r_m)^2). Rolling over lookback. Rank XS. Grid: LB∈[20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos.
- Data: 14 assets, 729 daily returns.
- Result: IS overall **35.4%** (17/48 positive). Mean Sharpe **-0.160**. Best LB60_R5_N4_high_long Sharpe 0.759 (+15.1% ann, -13.0% DD). No directional dominance: low_long 8/24, high_long 9/24.
- Notes: Co-skewness has no cross-sectional predictive power in crypto. All crypto assets have similar co-skewness profiles (highly correlated crash behavior), so cross-sectional dispersion is minimal. The academic tail-risk premium doesn't materialize in this universe where everything crashes together.
- Sessions: [2026-04-04 session 144]

## H-237: Volume Concentration (Herfindahl) Factor (14 Assets)
- Status: REJECTED
- Idea: Compute Herfindahl index of volume distribution over sub-periods within a rolling window. High HHI = volume concentrated in few periods (institutional/event-driven). Low HHI = evenly distributed (retail). Cross-sectional ranking.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Split lookback into N buckets, compute volume share in each, HHI = sum(share^2). Rank XS. Grid: LB∈[10,15,20,30], B∈[3,5], R∈[3,5,7], N∈[3,4], dir∈2 = 96 combos.
- Data: 14 assets, 729 daily bars.
- Result: IS overall **38.5%** (37/96 positive). Mean Sharpe **-0.168**. Best LB20_B5_R3_N4_high_long Sharpe **1.794** (+34.2% ann, -12.0% DD). Dominant: high_long 25/48 (52.1%), mean 0.145.
- Notes: Some strong individual results (Sharpe 1.79) but not robust across parameter space. Only 52.1% of high_long combos positive. The top results cluster at LB20-30 with 3-5 buckets, suggesting a real but fragile signal. Volume concentration in crypto may capture event-driven flows but the effect is too noisy for reliable cross-sectional ranking.
- Sessions: [2026-04-04 session 144]

## H-238: Downside Beta Factor (14 Assets)
- Status: CONFIRMED (not deployed — redundant with H-019/H-024)
- Idea: Measure each asset's beta only on market down-days. Long low downside beta (defensive), short high downside beta (crash-prone). Refinement of killed H-024.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: beta_down = cov(r_i, r_m | r_m < 0) / var(r_m | r_m < 0). Rolling over lookback. Rank XS. Grid: LB∈[20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos.
- Data: 14 assets, 729 daily returns.
- Result: IS dom dir **100%** (24/24 low_long positive), overall 50%. Best LB60_R3_N3_low_long Sharpe **1.766** (+42.7% ann, -16.4% DD). **WF 4/6** positive, mean OOS **2.612**. Split-half H1=2.460/H2=1.125. Corr 0.413 H-012, **0.512 H-019**, **0.738 H-024** (regular beta).
- Notes: Strong standalone signal — 100% IS in low_long, WF 4/6, excellent Sharpe. But 0.738 correlation with regular beta (H-024 killed) and 0.512 with H-019 (low-vol in portfolio). Essentially a refined low-beta/low-vol anomaly. Not deploying to paper trade: 30 runners already active, H-019 captures most of this signal. If H-019 underperforms in future, H-238 could be a replacement.
- Sessions: [2026-04-04 session 144]

## H-239: Price Impact Factor (Return-to-Dollar-Volume, 14 Assets)
- Status: REJECTED
- Idea: Rank assets by rolling average of |daily_return| / dollar_volume. Low price impact = deep, resilient market that attracts institutional flow. Amihud-like but dollar-volume-normalized.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: price_impact = rolling_mean(|ret| / (close * volume)). Rank XS. Grid: LB∈[10,15,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 72 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS dom dir **100%** (36/36 low_impact_long positive), overall 50%. Mean Sharpe 1.439. Best LB40_R7_N4 Sharpe **1.763** (+84.9% ann, -28.6% DD). **WF 5/6** positive, mean OOS **1.878**. Split-half H1=1.776/H2=2.256. Corr H-012 **0.525** (FAILS <0.50).
- Notes: Excellent signal — 100% IS, WF 5/6 with mean OOS 1.878 (outstanding). But 0.525 correlation with momentum exceeds threshold. The low-impact assets are essentially large-cap momentum winners (BTC, ETH, SOL), so the signal is partially capturing size/momentum. Related to H-197 (Amihud) which is already deployed. Very strong but redundant.
- Sessions: [2026-04-05 session 145]

## H-240: Beta Instability Factor (14 Assets)
- Status: REJECTED
- Idea: Measure rolling std of each asset's beta to BTC. Low instability = stable, resolved relationship. Long stable, short unstable.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: Rolling beta(asset, BTC) over BW window, then rolling std over OW window. Rank XS. Grid: BW∈[10,20,30], OW∈[10,20,30,40], R∈[3,5,7], N∈[3,4], dir∈2 = 144 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS overall **43.1%**, dom dir low_instab_long **70.8%** < 80%. Best BW30_OW10_R3_N4 Sharpe **1.138** (+45.4% ann, -45.2% DD). High drawdowns across all params.
- Notes: Beta instability doesn't differentiate crypto assets enough for cross-sectional ranking. All alts have unstable BTC betas due to idiosyncratic moves. Drawdowns are very high (45-62%) across top params, making the signal impractical even if IS had passed.
- Sessions: [2026-04-05 session 145]

## H-241: Multi-Horizon Return Disagreement Factor (14 Assets)
- Status: REJECTED
- Idea: Compare short-term (3-7d) vs medium-term (15-40d) return direction. Coherent = both agree (strong trend). Long coherent-positive, short divergent/negative.
- Instrument: futures (14 USDT perps)
- Timeframe: 1D (rebalance 3-7 days)
- Logic: coherence = sign(ret_short) * sign(ret_long) * sqrt(|ret_short| * |ret_long|). Rank XS. Grid: SH∈[3,5,7], LH∈[15,20,30,40], R∈[3,5,7], N∈[3,4], dir∈2 = 144 combos.
- Data: 14 assets, 730 daily bars.
- Result: IS dom dir coherent_long **90.3%** (65/72 positive), overall 45.8%. Mean Sharpe 0.670. Best SH7_LH30_R3_N4 Sharpe **1.668** (+77.2% ann, -18.8% DD). **WF 1/6** positive (FAILS), mean OOS **-0.330**. Split-half H1=2.296/H2=1.974. Corr H-012 **0.144**.
- Notes: Interesting signal with 90.3% IS and very low H-012 correlation (0.144), but WF catastrophically fails (1/6). The IS-selected params don't generalize OOS at all — classic overfitting. The coherence metric essentially captures momentum when both horizons agree, explaining the IS performance, but the optimal horizons shift across time periods.
- Sessions: [2026-04-05 session 145]

### H-242: Intraday Momentum Concentration Factor — CONFIRMED
- Status: LIVE (paper trade since 2026-04-05)
- Idea: Rank assets by fraction of daily absolute return from the single highest-return hour. High concentration (spike-driven) outperforms low concentration (distributed).
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1H bars)
- Logic: For each asset/day, compute max(|hourly_ret|) / sum(|hourly_ret|). Rolling avg over lookback. Rank XS. Long high concentration, short low. Grid: LB∈[10,15,20,30], R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS dom dir high_conc_long **100%** (24/24 positive), overall 50.0%. Mean Sharpe (high_conc) 1.100. Best LB10_R5_N4 Sharpe **2.014** (+73.2% ann, -28.6% DD). **WF 6/6** positive, mean OOS **1.802** (outstanding). Split-half H1=2.112/H2=2.298. Corr H-012 **0.14**, H-031 **0.24**, H-076 **0.10**.
- Notes: Genuinely novel microstructure signal using intraday data. WF 6/6 is the best walk-forward result in the entire hypothesis set. BTC and ETH have highest concentration (likely institutional-driven moves), while small-caps have more distributed returns. Captures something distinct from size/momentum/efficiency.
- Sessions: [2026-04-05 session 146]

### H-243: Funding-Premium Divergence Factor — REJECTED
- Status: REJECTED
- Idea: Compare XS rank of funding rate vs premium index. Disagreement between these two positioning signals creates distinct signal.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Divergence = funding_XS_rank - premium_XS_rank. Long assets where funding rank >> premium rank (bullish leverage but discounted spot). Grid: LB∈[5,10,15,20], R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS dom dir fund_high_prem_low_long **87.5%** (21/24 positive). Best LB5_R3_N4 Sharpe 1.554. **WF 3/6** (FAILS). Mean OOS 0.910 but too inconsistent.
- Notes: Clear directional signal in-sample but OOS walk-forward fails 3/6. When it works it works well (folds 2,4,5 > 2.0 Sharpe) but folds 1,3,6 negative. The optimal params shift too much across time.
- Sessions: [2026-04-05 session 146]

### H-244: Intraday Reversal Propensity Factor — CONFIRMED
- Status: LIVE (paper trade since 2026-04-05)
- Idea: Rank assets by hourly return lag-1 autocorrelation. Assets with negative autocorrelation (mean-reverting intraday) outperform those with positive autocorrelation (trending intraday).
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1H bars)
- Logic: Compute rolling lag-1 autocorrelation of hourly returns over lookback*24 hours. Rank XS. Long most negative (mean-reverting), short most positive. Grid: LB∈[7,14,21,30]d, R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS dom dir neg_autocorr_long **100%** (24/24 positive), overall 50.0%. Mean Sharpe (neg_autocorr) 1.118. Best LB14d_R5_N4 Sharpe **2.074** (+72.6% ann, -18.4% DD). **WF 4/6** positive, mean OOS **0.268**. Split-half H1=2.988/H2=2.090. Corr H-012 **0.05**, H-031 **-0.03**, H-242 **0.01**.
- Notes: Genuinely novel intraday microstructure signal. XRP, SOL, BTC most mean-reverting; OP, ARB most trending. Mean-reverting assets (where market makers are active) outperform. Essentially zero correlation with everything — excellent diversifier. WF mean is modest (0.268) but 4/6 positive.
- Sessions: [2026-04-05 session 146]

## H-245: Close-to-VWAP Deviation Factor — REJECTED
- Status: REJECTED
- Idea: Using hourly bars, compute daily VWAP. Signal = rolling avg of (close - VWAP) / VWAP. Assets closing above VWAP have net buying pressure. Rank XS.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1H bars)
- Logic: VWAP from hourly typical price * volume. Rolling avg over lookback. Rank XS. Grid: LB∈[5,10,15,20,30], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS dom dir above_vwap_long **76.7%** (23/30) < 80%. Best LB15_R7_N4 Sharpe 1.391 (+29.9% ann, -14.2% DD). Clear directional signal but not robust across params.
- Notes: VWAP deviation captures buying/selling pressure but crypto's 24/7 market dilutes the signal. Higher lookbacks weaken it — noise washes out the pressure signal quickly.
- Sessions: [2026-04-05 session 147]

## H-246: Volume Clock / Hourly Volume HHI Factor — REJECTED
- Status: REJECTED
- Idea: Measure Herfindahl index of hourly volume shares within each day. High HHI = concentrated trading, low = distributed. Rank XS.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1H bars)
- Logic: HHI = sum(hourly_vol_share^2). Rolling avg. Grid: LB∈[5,10,15,20,30], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS dom dir high_hhi_long **53.3%** (16/30), overall 43.3%. Best LB10_R7_N3 Sharpe 0.809. Essentially random.
- Notes: Volume concentration (HHI) does not differentiate crypto XS returns. All crypto assets show similarly distributed volume patterns with occasional spikes.
- Sessions: [2026-04-05 session 147]

## H-247: First-Hour Momentum Alignment Factor — REJECTED
- Status: REJECTED
- Idea: For each asset/day, compare first hour return direction with full day return. Rolling fraction of aligned days. Long predictable (high alignment) assets.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1H bars)
- Logic: Alignment = 1 if sign(first_hour_ret) == sign(full_day_ret). Rolling avg. Grid: LB∈[10,15,20,30,40], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS dom dir high_align_long **63.3%** (19/30) < 80%. Best LB40_R3_N3 Sharpe 1.551. Mean alignment ~55% across assets (only slightly above random).
- Notes: First-hour-to-day alignment is too noisy as a XS signal. The best param requires 40d lookback which smooths out too much. 24/7 crypto markets have no "opening bell" effect.
- Sessions: [2026-04-05 session 147]

## H-248: Intraday Trend Strength / Efficiency Factor — REJECTED
- Status: REJECTED
- Idea: Using hourly bars, compute |sum(hourly_ret)| / sum(|hourly_ret|) per day — within-day efficiency ratio. Low intraday efficiency = noisy. Rank XS.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1H bars)
- Logic: Efficiency = |net_hourly_ret| / sum(|hourly_ret|). Rolling avg. Grid: LB∈[5,10,15,20,30], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS dom dir low_eff_long **56.7%** (17/30) < 80%. Best LB5_R7_N3 Sharpe 0.794. Weak, no robust edge.
- Notes: Intraday efficiency (within-day trend quality) is different from H-076 (multi-day efficiency) but doesn't predict XS returns. All crypto assets have similarly low intraday efficiency (~0.21).
- Sessions: [2026-04-05 session 147]

## H-249: Intraday Range Expansion Factor — REJECTED
- Status: REJECTED
- Idea: Ratio of daily range (H-L) to first-hour range. High expansion = breakout day. Rolling avg. Rank XS.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1H bars)
- Logic: Expansion = day_range / first_hour_range. Rolling avg. Grid: LB∈[5,10,15,20,30], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS overall **36.7%**, no dominant direction (both 36.7%). Best LB30_R3_N4 Sharpe 0.768. No signal.
- Notes: Range expansion ratio is approximately the same across all crypto assets (~6x) with insufficient XS dispersion to generate trading signals.
- Sessions: [2026-04-05 session 147]

### H-250: US Session Momentum Factor — CONFIRMED
- Status: LIVE (paper trade since 2026-04-05)
- Idea: Rank assets by fraction of daily absolute return occurring during US trading hours (13:00-21:00 UTC). High US share = institutional flow. Long institutional, short non-institutional.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1H bars)
- Logic: US_share = sum(|hourly_ret| during 13-21 UTC) / sum(|hourly_ret| all day). Rolling avg over lookback. Rank XS. Long high US share. Grid: LB∈[5,10,15,20,30], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS dom dir high_us_long **96.7%** (29/30 positive), overall 48.3%. Mean Sharpe 0.678. Best LB20_R7_N3 Sharpe **1.057** (+25.5% ann, -29.4% DD). **WF 5/5** positive (240/90 window), mean OOS **1.197**. WF 3/3 (360/120) mean **2.089**. Split-half H1=0.245/H2=2.557. Corr H-012 **0.032**, H-031 **0.378**, H-076 **-0.227**, H-242 **0.214**.
- Notes: Novel institutional flow proxy. BTC/ETH/SOL have highest US share (~39-41%); smaller alts have lower (~37-38%). US session captures institutional trading activity. Near-zero momentum correlation (0.032) makes it an excellent diversifier. Negative correlation with efficiency (-0.227) is interesting — institutional-driven assets may be efficient in different ways.
- Sessions: [2026-04-05 session 147]

## H-251: Hurst Exponent Factor (14 Assets)
- Status: REJECTED — weak IS, no dominant direction
- Idea: Estimate Hurst exponent (R/S method) for each asset over rolling window. Long trending (H>0.5), short mean-reverting (H<0.5) assets.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Rolling Hurst via simplified R/S analysis. Rank XS by Hurst value.
- Data: 14 assets, 731 daily bars.
- Result: IS **37.5%** (18/48), best dir high_h_long **50.0%** < 80%. Mean Sharpe -0.217. Best LB90_R7_N3 Sharpe 1.487 (+67.6%, -34.5% DD), but overall signal too noisy.
- Notes: Hurst captures fractal scaling/persistence but crypto assets have similar persistence characteristics — the XS spread is too narrow. Different from momentum (direction) and efficiency (path linearity), but Hurst doesn't generate robust XS rankings in crypto. LB=90 works best (more data for R/S estimation) but still only 50% positive.
- Sessions: [2026-04-05 session 148]

## H-252: Tail Ratio Factor (14 Assets)
- Status: REJECTED — IS dom dir 75% < 80%, borderline
- Idea: Ratio of 95th to 5th percentile absolute returns over rolling window. Captures extreme return asymmetry.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: tail_ratio = |P95 return| / |P5 return|. Long high_tail (positive extreme asymmetry), short low_tail.
- Data: 14 assets, 731 daily bars.
- Result: IS **37.5%** (18/48), best dir high_tail_long **75.0%** < 80%. Mean Sharpe -0.174. Best LB60_R3_N3 Sharpe 1.294 (+57.4%, -26.1% DD).
- Notes: Borderline signal — 75% in dominant direction is close to threshold. Different from skewness (full distribution) because it focuses only on extreme percentiles. High_tail_long works because assets with bigger upside tails tend to continue. But 25% of params fail, indicating parameter sensitivity. Longer lookbacks (60d) better than shorter ones.
- Sessions: [2026-04-05 session 148]

## H-253: Return Entropy Factor (14 Assets)
- Status: REJECTED — weak IS, no directional edge
- Idea: Shannon entropy of discretized daily return distribution. Low entropy = concentrated/predictable returns.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Discretize N-day returns into K bins, compute normalized Shannon entropy. Rank XS: long low-entropy (predictable), short high-entropy (random).
- Data: 14 assets, 731 daily bars.
- Result: IS **36.5%** (35/96), best dir high_entropy_long **47.9%** < 80%. Mean Sharpe -0.177. Best LB40_B8_R7_N4 Sharpe 0.524 (+19.6%, -44.7% DD).
- Notes: Entropy fails as a XS factor — all crypto assets have similarly high return entropy due to 24/7 trading and correlation with BTC. The XS dispersion in entropy values is too narrow. Even the best parameter set has mediocre Sharpe (0.524) with high drawdown (-44.7%). Neither direction dominates. Entropy captures a real property of returns but it doesn't differentiate meaningfully across crypto assets.
- Sessions: [2026-04-05 session 148]

## H-254: BTC Beta Change Direction Factor (13 Non-BTC Assets)
- Status: REJECTED — weak IS, no dominant direction
- Idea: Rank non-BTC assets by the direction of change in their rolling BTC beta. Assets decorrelating from BTC (decreasing beta) may have independent alpha.
- Instrument: futures (13 perps, non-BTC)
- Timeframe: 1D
- Logic: Rolling beta vs BTC over window, then compute beta_now - beta_N_days_ago. Rank XS: long decreasing beta (decorrelating), short increasing beta (becoming more BTC-like). Grid: BW∈[20,40,60], CL∈[5,10,20], R∈[3,5,7], N∈[3,4], dir∈2 = 108 combos.
- Data: 13 non-BTC assets, 731 daily bars.
- Result: IS **42.6%** (46/108), best dir incr_beta_long **59.3%** < 80%. Mean Sharpe -0.231. Best BW40_CL20_R7_N4 Sharpe 0.782 (+33.1%, -28.9% DD). Neither direction dominant.
- Notes: BTC beta change direction doesn't predict XS returns. Crypto assets move in and out of BTC correlation randomly — the direction of beta change is mean-reverting rather than persistent. Different from beta level (H-024, killed) and beta instability/magnitude (H-240, rejected).
- Sessions: [2026-04-05 session 149]

### H-255: Risk-Adjusted Momentum / Rolling Sharpe Factor — CONFIRMED
- Status: LIVE (paper trade since 2026-04-05)
- Idea: Rank 14 crypto assets by rolling Sharpe ratio (return/vol). Long high-Sharpe (quality momentum), short low-Sharpe. Risk-adjusted momentum should be more persistent than raw return.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: For each asset, compute rolling daily Sharpe (mean/std of returns) over lookback window. Rank XS: long high Sharpe (quality momentum), short low Sharpe. Grid: LB∈[14,21,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS dom dir high_sharpe_long **93.3%** (28/30 positive), overall 46.7%. Mean Sharpe 0.558. Best LB14_R7_N3 Sharpe **1.552** (+75.2% ann, -26.3% DD). **WF 5/6** positive, mean OOS **0.964**. Split-half H1=1.963/H2=1.447. Corr H-012 **0.460** (below 0.50 threshold but borderline — captures overlapping but distinct signal).
- Notes: Risk-adjusted momentum is related to raw momentum (H-012, corr 0.46) but the volatility normalization adds a distinct dimension. High-Sharpe assets have better risk-adjusted persistence than high-return assets. Short lookback (14d) works best — recent risk-adjusted quality matters more than long-term. XRP/BTC have highest avg rolling Sharpe; OP/ARB lowest.
- Sessions: [2026-04-05 session 149]

## H-256: Volume-Confirmed Return Factor (14 Assets)
- Status: REJECTED — passes IS but fails WF
- Idea: Weight daily returns by relative volume (vol/avg_vol) to create volume-confirmed returns. High-volume moves are more "real" and persistent.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: vol_weight = volume / rolling_avg(N). Confirmed_return = sum(ret * vol_weight) over lookback. Rank XS: long high VCR, short low VCR. Grid: LB∈[10,14,21,30,60], VW∈[10,20], R∈[3,5,7], N∈[3,4], dir∈2 = 120 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS dom dir high_vcr_long **93.3%** (56/60 positive), overall 46.7%. Mean Sharpe 0.615. Best LB10_VW20_R7_N4 Sharpe **1.522** (+63.7% ann, -39.2% DD). **WF 3/6** mean OOS **-0.164** (FAILS). Split-half H1=2.267/H2=1.071. Corr H-012 0.463.
- Notes: Volume-weighted returns have strong IS signal (93.3%) but don't generalize OOS — WF shows inconsistency with 3 of 6 folds negative. The volume-weighting essentially amplifies momentum on high-volume days, which is regime-dependent. Short lookbacks (10-14d) work better IS but are more parameter-sensitive OOS. Conceptually similar to momentum (H-012) with volume emphasis — the 0.463 correlation confirms overlap.
- Sessions: [2026-04-05 session 149]

## H-257: Intraday Return Dominance Factor (14 Assets)
- Status: REJECTED — redundant with momentum in 24/7 market
- Idea: Decompose daily returns into intraday (open-to-close) and overnight (close-to-open) components. Rank by ratio of cumulative intraday returns to total returns. High ratio = institutional flow drives asset.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: intraday_ret = close/open - 1 for each day. total_ret = close/prev_close - 1. Score = sum(intraday_ret) / abs(sum(total_ret)) over lookback. Grid: LB∈[10,15,20,30,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 1069 daily bars.
- Result: IS dom dir high_long **100%** (30/30 positive), mean Sharpe 1.816. Best LB10_R7_N4 Sharpe **2.682** (+234.2% ann, -29.7% DD). **WF 6/6** mean OOS **2.780** (best WF in entire hypothesis set!). Split-half H1=3.687/H2=1.820. Corr H-012 **0.538**.
- Notes: Despite extraordinary WF performance (6/6, mean 2.780 — best ever), this factor is **REJECTED** because in 24/7 crypto markets open[i] ≈ close[i-1], making overnight returns ≈ 0. The intraday return exactly equals the total return, so the factor reduces to short-term momentum (10-day). The 0.538 correlation with H-012 confirms this redundancy. The strong performance comes from the short lookback (LB10) and wider rebal (R7), which is just a different parameterization of momentum, not a novel signal.
- Sessions: [2026-04-06 session 150]

## H-258: Recovery Speed Factor (14 Assets)
- Status: REJECTED — IS fails 80% threshold
- Idea: Measure average speed of price recovery after local dips over lookback window. Fast recovery = strong support/demand. Rank XS: long fast-recovery, short slow-recovery.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Find dip points (drawdown < -1%), measure days to recover 50% of dip, weighted by dip depth. Score = mean(depth/recovery_days). Grid: LB∈[15,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 1069 daily bars.
- Result: IS best dir high_long **50.0%** (15/30 positive), overall **38.3%** (23/60). Best LB15_R5_N4_high_long Sharpe 1.016 (+52.5% ann, -56.1% DD).
- Notes: Recovery speed has no robust cross-sectional predictive power in crypto. Only 50% IS positive — barely better than random. Crypto assets tend to crash and recover together, so XS differentiation is weak. The best individual combo (Sharpe 1.016) has extreme 56% drawdown, indicating unreliability.
- Sessions: [2026-04-06 session 150]

## H-259: Extreme Move Frequency Factor (14 Assets)
- Status: LIVE (paper trade since 2026-04-06)
- Idea: Rank assets by fraction of daily returns exceeding 2 rolling standard deviations. High extreme frequency = breakout potential. Long active/volatile breakout assets, short quiet/ranging.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: For each asset, compute fraction of |return| > 2σ_rolling over lookback window. σ computed from 2x lookback for stability. Rank XS: long high extreme freq, short low. Grid: LB∈[10,15,20,30,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 1069 daily bars.
- Result: IS dom dir high_long **100%** (30/30 positive), overall 58.3%. Mean Sharpe 1.331. Best LB20_R7_N4 Sharpe **2.648** (+197.3% ann, -17.7% DD). **WF 5/6** mean OOS **1.320**. Split-half H1=2.315/H2=2.990. Corr H-012 **0.272** (low).
- Notes: Counterintuitive direction — high extreme move frequency predicts outperformance, not underperformance. In crypto, assets making outsized moves are in breakout/momentum phase, capturing "momentum burst" potential. Very low H-012 correlation (0.272) confirms this is distinct from simple momentum. Excellent split-half stability (both halves Sharpe > 2). Deployed as paper trade #35: LONG OP/ATOM/ARB/DOT, SHORT ADA/LINK/AVAX/NEAR.
- Sessions: [2026-04-06 session 150]

## H-260: BTC Correlation Regime Factor (13 Non-BTC Assets)
- Status: REJECTED — passes IS but severe OOS collapse
- Idea: Rank non-BTC assets by rolling correlation with BTC. Long high-corr (beta plays riding BTC trend) or low-corr (decoupled alpha).
- Instrument: futures (13 perps, excl BTC)
- Timeframe: 1D
- Logic: rolling_corr(asset, BTC, lookback). Rank XS: test both directions. Grid: LB∈[15,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 729 daily bars.
- Result: IS dom dir high_long **86.7%** (26/30 positive), overall 50.0%. Best LB20_R5_N3_high_long Sharpe 0.829 (+33.4% ann, -60.3% DD). **70/30 split: IS 1.836, OOS -1.376** (FAILS). Split-half H1=3.037, H2=**-2.047** (catastrophic). **WF 2/6** mean 0.313.
- Notes: High BTC correlation predicts outperformance IS — intuitively, high-beta alts ride BTC trends up. But the signal is regime-dependent: works in trending BTC markets (H1), completely fails in choppy/down (H2). Severe overfitting to one regime. 60% drawdown is also unacceptable.
- Sessions: [2026-04-06 session 151]

## H-261: Volume Spike Frequency Factor (14 Assets)
- Status: REJECTED — IS fails 80% threshold
- Idea: Count days with dollar volume > K× rolling average over lookback. Frequent spikes = attention surges. Rank XS: long high-spike or low-spike.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: spike = (vol > K * rolling_avg(20d)). Score = rolling_mean(spike, lookback). Grid: LB∈[10,15,20,30], K∈[2,3], R∈[3,5,7], N∈[3,4], dir∈2 = 96 combos.
- Data: 14 assets, 729 daily bars.
- Result: IS best dir low_long **47.9%** (23/48), overall 37.5%. Best LB10_S2.0_R3_N3_low_long Sharpe 0.816 (+32.7% ann, -49.7% DD).
- Notes: Volume spike frequency has no robust XS predictive power. Only 37.5% overall positive — barely better than random. Volume spikes don't differentiate future returns cross-sectionally. Related to turnover (H-085) which works better by measuring volume ratios continuously rather than counting discrete spikes.
- Sessions: [2026-04-06 session 151]

## H-262: Return Consistency Factor (14 Assets)
- Status: REJECTED — IS fails 80% threshold
- Idea: Ratio of median daily return to mean daily return over lookback. High consistency (median ≈ mean) = stable normal trend. Low consistency = fat-tailed jump-driven.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: score = median(ret, LB) / mean(ret, LB). Grid: LB∈[10,15,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 72 combos.
- Data: 14 assets, 729 daily bars.
- Result: IS both directions tied at **61.1%** (22/36 each), overall 61.1%. Best LB30_R7_N3_low_long Sharpe 1.609 (+78.6% ann, -45.5% DD).
- Notes: Median/mean return ratio has no dominant direction — both sides equally weak. The ratio is noisy because mean returns over short lookbacks are close to zero, causing the ratio to swing wildly. Does not capture any distinct cross-sectional structure.
- Sessions: [2026-04-06 session 151]

## H-263: Relative Strength vs BTC Factor (13 Non-BTC Assets)
- Status: LIVE (paper trade since 2026-04-06)
- Idea: Rank non-BTC assets by cumulative return minus BTC cumulative return over lookback. Captures idiosyncratic outperformance beyond BTC beta exposure.
- Instrument: futures (13 perps, excl BTC)
- Timeframe: 1D
- Logic: For each non-BTC asset, score = (asset_return_LB - BTC_return_LB). Rank XS: long top relative strength, short bottom. Grid: LB∈[10,15,20,30,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 1070 daily bars.
- Result: IS dom dir high_long **100%** (30/30 positive), overall 50.0%. Mean Sharpe 2.530. Best LB10_R3_N3_high_long Sharpe **4.087** (+1014% ann, -20.6% DD). **WF 6/6** mean OOS **4.058** (best ever). Split-half H1=3.831/H2=0.820. Corr H-012 **0.338** (low).
- Notes: Exceptionally strong factor. All 6 WF folds Sharpe > 2.7 — robust across all market regimes. High_long direction captures that altcoins outperforming BTC have idiosyncratic momentum that persists. 10-day lookback with 3-day rebal is aggressive but 100% IS robustness confirms signal across all parameter combos. The low H-012 correlation (0.338) confirms this captures a distinct signal from raw momentum — the BTC-relative component adds genuine information. Deployed as paper trade #36: LONG NEAR/OP/AVAX (currently no BTC in universe), SHORT DOT/SOL/SUI.
- Sessions: [2026-04-06 session 152]

## H-264: Return Skewness Factor (14 Assets)
- Status: LIVE (paper trade since 2026-04-06)
- Idea: Rank assets by return skewness over lookback window. High positive skew indicates breakout/momentum phase. In crypto (unlike equities), positive skew predicts continuation not reversal.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: For each asset, compute scipy.stats.skew(daily_returns, LB). Rank XS: long high skew, short low skew. Grid: LB∈[10,15,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 48 combos (24 per direction).
- Data: 14 assets, 1070 daily bars.
- Result: IS dom dir high_long **91.7%** (22/24 positive), low_long 8.3%. Mean Sharpe 0.772 (high_long). Best LB60_R3_N3_high_long Sharpe **1.879** (+153.8% ann, -28.4% DD). **WF 6/6** mean OOS **1.532**. Split-half H1=2.398/H2=0.872. Corr H-012 **0.400** (moderate, below 0.5 threshold).
- Notes: Counterintuitive direction for crypto — academic literature predicts negative-skew outperformance (lottery preference), but in crypto HIGH skew outperforms. Assets exhibiting positive skew are in breakout/momentum phases, and the skew itself signals continuation potential. 60-day lookback captures stable skewness regime. All 6 WF folds positive. The 0.400 correlation with H-012 shows moderate overlap with momentum but enough independence to add value. Deployed as paper trade #37: LONG DOT/ADA/NEAR (currently high skew), SHORT OP/ARB/BTC.
- Sessions: [2026-04-06 session 152]

## H-265: Lead-Lag Response Factor (14 Assets)
- Status: REJECTED — IS fails 80% threshold
- Idea: Rank assets by regression beta of asset_return(t) on equal-weight_market_return(t-1). Low lagged beta = asset leads the market. High lagged beta = asset lags.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: For each asset, regress its return on lagged (t-1) equal-weight market return (excl self). Beta = lagged response coefficient. Grid: LB∈[10,15,20,30,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos (reduced to 36 due to min data requirements).
- Data: 14 assets, 1070 daily bars.
- Result: IS best dir low_long **55.6%** (10/18 positive), high_long 33.3%. Overall 44.4% (16/36). Best LB30_R7_N4_low_long Sharpe 1.537 (+89.6% ann, -28.9% DD).
- Notes: Lead-lag relationships in crypto are weak and unstable. The lagged beta has no robust XS predictive power — only 55.6% positive in best direction. Crypto assets tend to move simultaneously rather than in sequence, so the lead-lag structure that exists in equities (large→small, liquid→illiquid) is largely absent in the 14-asset crypto universe. Market microstructure in crypto (24/7 trading, high retail participation) eliminates most informational lag.
- Sessions: [2026-04-06 session 152]

## Killed

### H-024: Low-Beta Anomaly — KILLED (2026-03-31, session 114)
- Reason: Comparison vs H-019 (low-vol) over 13 days: H-019 +7.44% vs H-024 -0.20% (7.64% gap). H-019 decisively won.

---

## Rejected

## H-266: Conditional Beta Asymmetry Factor (13 Non-BTC Assets)
- Status: REJECTED
- Idea: Compute beta to BTC separately on BTC-up and BTC-down days. Ratio (up_beta/down_beta) captures asymmetric market participation. Long assets with high upside/downside beta ratio.
- Instrument: futures (13 non-BTC perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: Split lookback into BTC-up/down days, compute conditional betas, rank by ratio or difference.
- Result: IS **35.4%** positive (34/96). Mean Sharpe -0.135. Best: LB20_ratio_R7_N3 Sharpe 0.570. No dominant direction (high_asym 61.8%). **REJECTED** — conditional betas too noisy in crypto; up/down days don't create stable XS spread.
- Notes: Similar to H-236 (co-skewness, also rejected). Conditional beta decomposition doesn't produce robust XS signals because crypto assets crash together regardless of their individual beta asymmetry.
- Sessions: [2026-04-06 session 153]

## H-267: Variance Ratio Factor (14 Assets)
- Status: REJECTED
- Idea: Lo-MacKinlay variance ratio VR(q) = Var(q-day returns) / (q * Var(1-day returns)). VR>1 means trending, VR<1 means reverting. Rank cross-sectionally.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: Compute rolling VR with window W and aggregation period q. Rank by VR.
- Result: IS **41.7%** positive (45/108). Mean Sharpe -0.131. Best: W90_Q5_R5_N3_high_vr_long Sharpe 1.245. Dominant direction high_vr_long (88.9%) but < 80% IS threshold. **REJECTED** — variance ratio does not produce robust XS spread in crypto. All assets have similar VR properties.
- Notes: Strong directional signal (88.9% high_vr_long) but not enough combos are positive. VR measures return persistence which is related to Hurst (H-251, also rejected) and autocorrelation (H-200/H-230, also rejected). Crypto assets have universally weak VR signals — insufficient XS dispersion.
- Sessions: [2026-04-06 session 153]

## H-268: OI Growth Rate Factor (14 Assets)
- Status: REJECTED
- Idea: Rank assets by rate of change of open interest. Pure OI momentum — does absolute OI growth predict XS returns?
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: Compute OI growth = OI(t)/OI(t-lookback) - 1. Rank cross-sectionally.
- Result: IS **35.0%** positive (21/60). Mean Sharpe -0.260. Best: LB14_R7_N4_low_oi_long Sharpe 1.119. No dominant direction (52.4% low_oi_long). **REJECTED** — OI growth rate alone has no robust XS predictive power.
- Notes: Pure OI momentum fails despite OI being useful in composite signals (H-044, H-193). OI growth alone is too noisy — it reflects market-wide speculation shifts that affect all assets similarly. The useful OI signals are relative to price (divergence/alignment).
- Sessions: [2026-04-06 session 153]

## H-269: Momentum Breadth Factor (% Positive Days, 14 Assets)
- Status: REJECTED
- Idea: Rank assets by fraction of positive-return days over lookback window. More robust momentum signal than total return — resistant to single-day outlier moves.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: Compute breadth = count(positive return days) / lookback days. Rank XS.
- Result: IS **31.7%** positive (19/60). Mean Sharpe -0.312. Best: LB15_R5_N3_high_breadth_long Sharpe 1.116 (+52.7% ann, -35.2% DD). Dominant direction high_breadth_long (94.7%). **REJECTED** — breadth doesn't produce robust XS spread.
- Notes: Strong directional signal (94.7% high_breadth_long) but only 31.7% of parameter combos are positive. The fraction-of-positive-days measure is a weaker version of total momentum — it loses the magnitude information (how big each day's return was) without gaining sufficient robustness. In crypto, a single big up day can dominate performance, so throwing away magnitude actually discards useful information.
- Sessions: [2026-04-06 session 154]

## H-270: Dollar Volume Acceleration Factor (14 Assets)
- Status: REJECTED
- Idea: Second derivative of dollar volume: rate of change of DV momentum. Assets with accelerating volume attract increasing attention and capital.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: Compute DV = close * volume, DV_mom = DV_MA(short)/DV_MA(long)-1, DV_accel = DV_mom(t) - DV_mom(t-lag). Rank XS.
- Result: IS **42.1%** positive (91/216). Mean Sharpe -0.320. Best: S5_L30_AL15_R5_N4_high_accel_long Sharpe **2.052** (+77.7% ann, -26.1% DD). Dominant direction high_accel_long (92.3%). **REJECTED** — strong best combo but most parameter combos negative.
- Notes: Best single combo has outstanding Sharpe 2.05 but not robust — only 42.1% positive. DV acceleration is inherently noisy (second derivative amplifies noise). The signal works in the best parameterization but doesn't generalize across the parameter grid. Volume momentum (H-021) captures the first derivative more stably.
- Sessions: [2026-04-06 session 154]

## H-271: Price Efficiency Ratio Factor (14 Assets)
- Status: REJECTED
- Idea: Compute |net movement| / gross movement over lookback. Values near 1 = trending (directional), near 0 = choppy (back-and-forth). Long trending assets, short choppy ones.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: For each asset: efficiency = |close(t)/close(t-LB) - 1| / sum(|daily_returns|). Rank XS.
- Result: IS **41.7%** positive (25/60). Mean Sharpe -0.225. Best: LB15_R5_N3_high_eff_long Sharpe 1.077 (+50.7% ann, -37.4% DD). Dominant direction high_eff_long (**100%**). **REJECTED** — all positive combos are trending-long but overall IS too low.
- Notes: Perfect directional dominance (100% high_eff_long = trending is good) but insufficient XS predictive power — only 41.7% positive. The efficiency ratio captures something real (trending assets do better) but the cross-sectional spread between trending and choppy assets in crypto is not wide or stable enough to generate consistent returns. Related to H-093 (trend consistency) and H-248 (intraday efficiency), both also rejected. Trend quality measures consistently fail in the 14-asset crypto universe.
- Sessions: [2026-04-06 session 154]

## H-272: Idiosyncratic Volatility Factor (13 Non-BTC Assets)
- Status: REJECTED
- Idea: Residual volatility after removing BTC market factor via rolling regression. Low idio-vol = cleaner BTC proxy, high idio-vol = unpredictable idiosyncratic moves. Tests if equity-like idio-vol puzzle holds in crypto.
- Instrument: futures (13 non-BTC perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: Regress each non-BTC asset return on BTC return over rolling window, compute std(residuals). Rank XS. Grid: LB∈[15,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 60 combos.
- Data: 14 assets, 729 daily bars.
- Result: IS **35.0%** positive (21/60). Mean Sharpe -0.102. Best: LB40_R3_N3_low_idiovol_long Sharpe 0.588 (+27.7% ann, -66.8% DD). Dominant direction low_idiovol_long (**85.7%**). **REJECTED** — idio-vol factor too weak in crypto.
- Notes: Directional signal is correct (85.7% low_idiovol_long, matching equity anomaly) but insufficient XS spread. Crypto assets all have high idiosyncratic vol relative to BTC, and the cross-sectional dispersion in residual vol is not wide enough to generate persistent returns. Prior attempts (H-083, H-144) also rejected. The idio-vol puzzle doesn't translate from equities to crypto — crypto markets lack the institutional structure that drives the anomaly in stocks.
- Sessions: [2026-04-06 session 155]

## H-273: Funding Rate Momentum Factor (14 Assets)
- Status: REJECTED
- Idea: Rank by change in funding rate (short MA - long MA). Rising funding = increasing crowd positioning → contrarian short. Falling = contrarian long. Captures DIRECTION of crowding, not level.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: Compute FR_momentum = FR_MA(short) - FR_MA(long). Rank XS. Grid: SW∈[3,5,7], LW∈[14,21,30] (SW<LW only), R∈[3,5,7], N∈[3,4], dir∈2 = 108 combos.
- Data: 14 assets, 709 aligned days (funding data shorter than price data).
- Result: IS **41.7%** positive (45/108). Mean Sharpe -0.305. Best: S5_L21_R7_N3_falling_fund_long Sharpe 1.324 (+57.2% ann, -45.7% DD). Dominant direction falling_fund_long (**100%**). **REJECTED** — funding rate change is too noisy for XS signals.
- Notes: Strong directional signal (100% falling_fund_long = contrarian works) but only 41.7% IS positive. Funding rate momentum (rate of change) is even noisier than funding level (H-053). Prior attempts (H-089, H-130, H-171) also rejected with different metrics. Funding rate works cross-sectionally only as a LEVEL signal (H-053 confirmed), not as a momentum/change signal — the change amplifies noise without adding information.
- Sessions: [2026-04-06 session 155]

## H-274: Return-Volume Correlation Factor (14 Assets)
- Status: REJECTED
- Idea: Rolling correlation between daily returns and daily log-volume. High positive correlation = volume confirms price moves (informed trading). Low/negative = noise trading. Long high-corr (informed), short low-corr (noisy).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: Compute rolling corr(daily_return, log_volume) over lookback. Rank XS. Grid: LB∈[10,15,20,30,40,60], R∈[3,5,7], N∈[3,4], dir∈2 = 72 combos.
- Data: 14 assets, 729 daily bars.
- Result: IS **48.6%** positive (35/72). Mean Sharpe -0.183. Best: LB40_R7_N4_high_corr_long Sharpe 1.520 (+54.5% ann, -24.2% DD). Dominant direction high_corr_long (**100%**). **REJECTED** — return-volume correlation lacks robust XS spread.
- Notes: Clear directional signal (100% high_corr_long) but only 48.6% IS positive — insufficient for robustness. Prior PV correlation attempt (H-103) also rejected. In crypto, the return-volume relationship is unstable: high volume can accompany both informed buying and panic liquidations. The correlation metric can't distinguish these regimes, making the XS signal unreliable. The best combo has decent Sharpe 1.52 but not robust across parameters.
- Sessions: [2026-04-06 session 155]

---

## H-275: Close Location Value (CLV) Factor
- Status: REJECTED
- Idea: Rank 14 crypto assets by rolling avg CLV = (close - low) / (high - low). High CLV = accumulation (closing near highs). Long high CLV, short low CLV.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Compute CLV per bar, average over lookback. Rank cross-sectionally. Market-neutral long/short.
- Result: IS **50.0%** overall, best direction high_clv_long **63.3%** (19/30). Below 80% threshold. Best config LB20_R3_N4 Sharpe 1.653 but insufficient robustness.
- Notes: CLV captures where price closes within daily range (accumulation vs distribution), but insufficient cross-sectional spread in crypto — all assets have similar CLV distributions. Different from H-182 (range width) but equally noisy.
- Sessions: [2026-04-06 session 156]

## H-276: Return Autocorrelation Factor
- Status: REJECTED
- Idea: Rank 14 crypto assets by rolling AR(1) coefficient. Positive autocorrelation = trending, negative = mean-reverting. Long trending, short mean-reverting.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Rolling autocorrelation of daily returns over lookback. Rank and construct L/S portfolio.
- Result: IS **50.0%** overall, best direction pos_autocorr_long **58.3%** (14/24). Below 80% threshold. Best config LB60_R3_N3 Sharpe 0.912.
- Notes: Similar problem as H-251 (Hurst exponent) — autocorrelation properties don't vary enough cross-sectionally in crypto assets. Short-range AR(1) not better than long-range Hurst.
- Sessions: [2026-04-06 session 156]

## H-277: VWAP Deviation Factor
- Status: LIVE (paper trade since 2026-04-06)
- Idea: Rank 14 crypto assets by (close - VWAP) / VWAP where VWAP is rolling volume-weighted average price. Above VWAP = demand pressure. Long above, short below.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 7 days)
- Logic: Compute rolling VWAP = sum(typical_price * volume) / sum(volume) over lookback. Rank deviation. Long top 3, short bottom 3.
- Data: 14 assets, 729 daily bars (~2yr). IS: 60 configs. WF: 6 folds x 90d test.
- Result:
  - **IS**: 80.0% above_vwap_long (24/30 positive), mean Sharpe 0.394
  - **Best config**: LB20_R7_N3, Sharpe **1.384**, +33.9% ann, -18.7% DD
  - **WF**: **5/6** positive, mean Sharpe **1.256**
  - **Split-half**: H1=1.795, H2=0.867 (both positive, H2 decay but stable)
  - **Neighboring params**: 21/24 positive (**87.5%** — excellent robustness)
  - **Correlation**: H-012 **0.464**, H-031 0.279, H-076 **0.112**
- Notes: Volume-weighted momentum variant. Captures demand/supply pressure through VWAP deviation. Higher correlation with H-012 (0.464) but very low with H-076 efficiency (0.112). Neighboring param robustness (87.5%) stronger than headline IS (80%). Paper trade deployed: LONG BTC/ETH/ARB, SHORT XRP/SUI/DOT.
- Sessions: [2026-04-06 session 156]

## H-278: Return Kurtosis Factor
- Status: REJECTED
- Idea: Rank 14 crypto assets by rolling excess kurtosis of daily returns. Long low-kurtosis (normal tails), short high-kurtosis (fat tails).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Rolling kurtosis over lookback. Low_kurt_long: assets with thinner tails are more predictable/stable.
- Result: IS low_kurt_long **83.3%** (passes), best Sharpe 0.856 (LB20_R7_N4). But WF: 4/6 positive, mean Sharpe **-0.119**. Folds 4-5 deeply negative (-1.920, -1.882). Signal regime-dependent.
- Notes: IS passes at 83.3% but WF mean Sharpe is negative — classic overfitting pattern. Kurtosis is inherently unstable in crypto, shifting dramatically across regimes. Near-zero correlation with H-012 (0.033) was a plus but signal doesn't generalize.
- Sessions: [2026-04-06 session 156]

## H-279: Volume Consistency (CV) Factor
- Status: REJECTED
- Idea: Rank 14 crypto assets by coefficient of variation of daily volume. Low CV = steady institutional interest. High CV = episodic/retail. Long consistent, short episodic.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Rolling std(volume) / mean(volume) over lookback. Rank cross-sectionally.
- Result: IS **50.0%** overall, best direction high_cv_long **75.0%** (18/24). Below 80% threshold. Best config LB20_R7_N4 Sharpe 1.083.
- Notes: Counterintuitive — high CV (episodic) assets outperform steady-volume assets. Captures attention/narrative-driven flows. But insufficient robustness. Volume CV doesn't provide enough cross-sectional spread.
- Sessions: [2026-04-06 session 156]

## H-280: Wick Ratio Factor (Intraday Reversal Intensity)
- Status: REJECTED
- Idea: Rank 14 crypto assets by average wick-to-body ratio (high-low / |close-open|). High wick = noisy intraday reversals.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Rolling mean of (high-low) / |close-open| over lookback. Rank cross-sectionally.
- Result: IS **40.3%** overall. Best direction high_long 80.6%. Below 80% threshold. Best Sharpe 1.765 (LB5_R5_N4).
- Notes: Strong directional signal in one direction but overall IS robustness too low. Wick ratio captures noise but doesn't differentiate enough cross-sectionally.
- Sessions: [2026-04-07 session 157]

## H-281: Volume-Weighted Return Persistence Factor
- Status: REJECTED
- Idea: Rank by rolling sum of return × normalized volume. Captures whether high-volume days push in same direction persistently.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: ret × (vol/vol_60d_avg), rolling sum over lookback.
- Result: IS **45.8%** overall. Best direction high_long 75.0%. Below 80% threshold. Best Sharpe 1.508 (LB20_R3_N4).
- Notes: Volume-weighted persistence doesn't add enough beyond raw momentum.
- Sessions: [2026-04-07 session 157]

## H-282: Close-to-High Distance Factor (Buying Pressure)
- Status: REJECTED
- Idea: Rank by where close falls in daily range (close-low)/(high-low). Near high = bullish.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Rolling mean of (close-low)/(high-low) over lookback.
- Result: IS **43.1%** overall. Best direction high_long 58.3%. Below 80% threshold. Best Sharpe 1.442 (LB14_R7_N4).
- Notes: Buying pressure proxy has insufficient cross-sectional spread. All crypto assets close similarly relative to their ranges.
- Sessions: [2026-04-07 session 157]

## H-283: Return Dispersion Factor (XS Deviation)
- Status: REJECTED
- Idea: Rank by average absolute deviation of asset return from cross-sectional mean. High dispersion = independent mover.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Rolling mean of |ret_i - mean(ret_all)| over lookback.
- Result: IS **38.9%** overall. Best direction high_long 75.0%. Below 80% threshold. Best Sharpe 1.503 (LB5_R5_N3).
- Notes: Dispersion captures independence from market but doesn't predict direction cross-sectionally.
- Sessions: [2026-04-07 session 157]

## H-284: Relative Volume Surprise Factor
- Status: REJECTED
- Idea: Rank by ratio of short-term to long-term volume. High ratio = volume surge/increased attention.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: vol_5d_avg / vol_LBd_avg, ranked cross-sectionally.
- Result: IS **50.0%** overall. Best direction low_long **100%** (36/36). Below 80% threshold. Best Sharpe 1.934 (LB20_R5_N3).
- Notes: Strong directional signal in low_long but overall IS robustness fails. Similar to H-021 (volume momentum) in reverse — low volume surprise outperforms. Redundant concept.
- Sessions: [2026-04-07 session 157]

## H-285: Return Direction Persistence Factor (Rolling Sign Mean)
- Status: REJECTED
- Idea: Rank by rolling mean of daily return sign (+1/-1). Captures consistency of direction.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Rolling mean of sign(ret) over lookback.
- Result: IS **36.1%** overall. Best direction high_long 61.1%. Below 80% threshold. Best Sharpe 1.069 (LB10_R5_N4).
- Notes: Discards magnitude (same as H-269 momentum breadth). Consistently weak signal — magnitude matters for cross-sectional ranking.
- Sessions: [2026-04-07 session 157]

## H-286: Return-to-Volume Ratio (Dollar-Volume Adjusted Return)
- Status: REJECTED
- Idea: Rank by |return| / dollar_volume — Amihud-like price impact measure.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Rolling mean of |ret| / (close × vol) over lookback.
- Result: IS **50.0%** overall. Best direction low_long **100%** (36/36). Below 80% threshold. Best Sharpe 1.572 (LB60_R7_N4).
- Notes: Similar to H-197 (Amihud) but different construction. Low price impact = liquid assets outperform. Consistent direction but not robust across all params.
- Sessions: [2026-04-07 session 157]

## H-287: Open-to-Previous-Close Gap Factor
- Status: REJECTED
- Idea: Rank by average gap between open and previous close. Captures overnight sentiment shift.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Rolling mean of (open - prev_close) / prev_close.
- Result: IS **0.0%** (0/72 positive). Completely dead signal. Best Sharpe -7.794.
- Notes: In 24/7 crypto markets, open ≈ previous close (no real "overnight gap"). Gap is just noise from bar boundary timing. Completely non-informative.
- Sessions: [2026-04-07 session 157]

## H-288: Rolling Sharpe Change (Quality Acceleration)
- Status: REJECTED
- Idea: Rank by difference between short-window and long-window rolling Sharpe. Captures improving risk-adjusted quality.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Sharpe(LB) - Sharpe(3×LB), where Sharpe = mean(ret) / std(ret) over window.
- Result: IS **44.4%** overall. Best direction high_long 52.8%. Below 80% threshold. Best Sharpe 1.835 (LB5_R3_N3).
- Notes: Similar concept to H-255 (rolling Sharpe level) which passed. The *change* is noisier than the *level*. Second derivative signals amplify noise.
- Sessions: [2026-04-07 session 157]

## H-289: Residual Momentum (Orthogonalized to Size & Vol)
- Status: REJECTED
- Idea: Cross-sectional regression of momentum on size & volatility per day. Extract residual as pure idiosyncratic momentum.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Daily XS regression: mom_i = β₁×size_i + β₂×vol_i + α_i. Factor = residual α.
- Result: **FAILED** — no valid results. Cross-sectional regression with only 14 assets is too noisy; OLS with 14 observations and 3 parameters lacks degrees of freedom.
- Notes: Would need 50+ assets for reliable XS regression. With 14 crypto assets, residuals are dominated by estimation error.
- Sessions: [2026-04-07 session 157]

## H-290: Volume-Adjusted Drawdown Recovery Speed
- Status: REJECTED
- Idea: How quickly does an asset recover from drawdowns, weighted by volume? Strong recovery with high volume = buying interest.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Rolling mean of (positive_ret × in_drawdown) × normalized_vol.
- Result: IS **38.9%** overall. Best direction high_long 47.2%. Below 80% threshold. Best Sharpe 1.252 (LB60_R3_N4).
- Notes: Recovery speed concept doesn't differentiate cross-sectionally. All crypto assets have similar drawdown/recovery dynamics due to high correlation.
- Sessions: [2026-04-07 session 157]

## H-291: ATR Expansion/Contraction Ratio
- Status: REJECTED
- Idea: Ratio of short-term ATR to long-term ATR. Expanding = breakout/vol expansion. Contracting = consolidation.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: ATR(LB) / ATR(3×LB).
- Result: IS **44.4%** overall. Best direction high_long **86.1%**. Below 80% threshold. Best Sharpe 1.264 (LB5_R3_N4).
- Notes: Strong directional signal (expanding ATR = long) but overall robustness fails. Similar to H-059 (vol term structure) which passed by using a different vol decomposition. ATR ratio is too raw.
- Sessions: [2026-04-07 session 157]

---

## H-292: Momentum × Efficiency Interaction Factor
- Status: REJECTED
- Idea: Combine cross-sectional momentum (rank) with price efficiency (rank) into a composite signal. Assets with strong + clean momentum should outperform.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3-7 days)
- Logic: composite = rank(N-day return) × rank(efficiency). Long top composite, short bottom. Grid: MOM_LB∈[20,40,60] × EFF_LB∈[20,40,60] × R∈[3,5,7] × N∈[3,4] × mode∈[add,mult] = 108 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **93.5%** positive (101/108). Best: MOM60_EFF40_R5_N3_mult Sharpe **2.178**, +92.2% ann, -21.0% DD. WF **5/6** mean **2.052**. Split-half 2.462/0.212. Neighbors 91.7%. **BUT** corr H-012 **0.749**, H-076 **0.578** — too correlated with both components.
- Notes: Excellent IS/WF but the interaction is just a linear combination of known factors. Correlation > 0.50 with both H-012 and H-076 means no novel signal captured. Multi-factor interactions inherit component correlations.
- Sessions: [2026-04-07 session 158]

## H-293: BTC-Regime Conditional Factor Switching
- Status: REJECTED
- Idea: Use BTC volatility regime to switch between momentum (trending) and mean-reversion (range-bound) for altcoins.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: If BTC short-term vol > long-term vol → trending → use momentum. Else → contrarian. Grid: MOM_LB∈[20,40,60] × VS∈[10,20,30] × VL∈[60,90,120] × R∈[3,5,7] × N∈[3,4] = 162 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **20.4%** positive (33/162). Best: MOM60_VS10_VL90_R5_N3 Sharpe 1.048, +42.3% ann, -67.2% DD. WF **4/6** mean 1.691. Split-half 0.346/1.036. Low corr H-012 **-0.042**. **REJECTED** — IS too low, regime switching doesn't generalize across parameters.
- Notes: Regime switching sounds appealing but the BTC vol regime indicator doesn't robustly classify regimes. Most parameter combos lose money. Recent WF folds are stronger (folds 4-5) suggesting possible emerging signal, but insufficient historical evidence.
- Sessions: [2026-04-07 session 158]

## H-294: Momentum × Funding Rate Interaction Factor
- Status: REJECTED
- Idea: Combine momentum with funding rate contrarian: long high-momentum + low-funding assets (under-crowded momentum), short low-momentum + high-funding (crowded losers).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = rank(mom) × (1 - rank(funding_avg)). Grid: MOM_LB∈[20,40,60] × FUND_W∈[3,5,7,10] × R∈[3,5,7] × N∈[3,4] = 72 combos.
- Data: 14 assets, 731 daily bars (funding: 730 bars).
- Result: IS **94.4%** positive (68/72). Best: MOM60_FW5_R5_N4 Sharpe **1.532**, +68.3% ann, -28.1% DD. Split-half 2.337/0.164. Neighbors 97.2%. **BUT** corr H-012 **0.522**, H-053 **0.498** — too correlated with components.
- Notes: Combining H-012 and H-053 produces a strong signal (94.4% IS, neighbors 97.2%) but it inherits correlations from both. The interaction doesn't capture enough novel information beyond what the two individual factors already provide separately.
- Sessions: [2026-04-07 session 158]

## H-295: BTC Beta Timing Factor
- Status: REJECTED
- Idea: Use BTC return direction to select altcoin beta exposure. When BTC rising, long high-beta alts; when BTC falling, long low-beta alts.
- Instrument: futures (13 alt perps, BTC excluded from trading)
- Timeframe: 1D
- Logic: signal = rolling_beta_to_BTC × sign(BTC_momentum). Grid: beta_LB∈[20,30,60] × btc_mom∈[5,10,20] × R∈[3,5,7] × N∈[3,4] = 54 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **24.1%** positive (13/54). Best: BETA30_BTCM5_R7_N4 Sharpe 0.711, +22.3% ann, -41.1% DD. WF **4/6** mean 1.226. Corr H-012 **0.212** (low, novel). **REJECTED** — IS too low. Timing beta exposure by BTC direction doesn't generalize.
- Notes: Low correlation with H-012 (0.212) is appealing — genuinely different signal. But only recent WF folds positive (4-5: Sharpe 3.6, 4.9). May be worth revisiting if crypto market structure changes. The idea is sound but data period too short/noisy.
- Sessions: [2026-04-07 session 158]

## H-296: Funding-Premium Spread Factor
- Status: REJECTED
- Idea: Combine funding rate and premium index into a spread: rank(premium) - rank(funding). High premium + low funding = genuine demand → LONG.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = rank(premium_avg) - rank(funding_avg). Grid: FUND_W∈[3,5,7] × PREM_W∈[3,5,7] × R∈[3,5,7] × N∈[3,4] = 54 combos.
- Data: 14 assets, 731 daily bars. Premium: 734 bars.
- Result: IS **0.0%** positive (0/54). Best Sharpe **-0.017**. Mean Sharpe -0.930. **REJECTED** — funding-premium spread has no cross-sectional predictive power at all.
- Notes: The spread between two positioning signals (funding rate level vs futures basis) doesn't generate XS returns. The two signals may capture the same underlying positioning but from different angles, so their spread is noise.
- Sessions: [2026-04-07 session 158]

## H-297: Multi-Timeframe Momentum Agreement Factor
- Status: REJECTED
- Idea: Combine short-term (10-20d) and long-term (40-60d) momentum into a concordance signal. Assets where both timeframes agree should have stronger trends.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = rank(short_mom) × rank(long_mom) or rank(sum) when signs agree. Grid: S∈[10,14,20] × L∈[40,60] × R∈[3,5,7] × N∈[3,4] × mode∈[product,agreement] = 72 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **98.6%** positive (71/72). Best: S10_L40_R3_N4_product Sharpe **1.775**, +119.3% ann, -31.3% DD. WF **6/6** mean **1.803**. Split-half 2.429/0.042. Neighbors **100%**. **BUT** corr H-012 **0.649** — too correlated with standard momentum.
- Notes: Outstanding metrics: 98.6% IS, 6/6 WF, 100% neighbors. Best multi-factor result in entire hypothesis set. But it's fundamentally just a better momentum signal (0.649 corr with H-012). Could be a candidate to REPLACE H-012 rather than complement it — but deployment redundant with existing momentum.
- Sessions: [2026-04-07 session 158]

## H-298: Informed Momentum Factor (High-Volume Filtered Returns)
- Status: REJECTED
- Idea: Compute momentum using only high-volume days (above rolling median). Filters out "noise" days, retaining only "informed" trading signals.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: informed_ret = daily_return × (volume > rolling_quantile). signal = rolling_sum(informed_ret). Grid: MOM_LB∈[20,40,60] × VT∈[0.5,0.7] × R∈[3,5,7] × N∈[3,4] = 36 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **94.4%** positive (34/36). Best: MOM20_VT0.7_R5_N3 Sharpe **1.173**, +55.4% ann, -37.9% DD. WF **5/6** mean **1.444**. Split-half 1.044/1.082. **BUT** corr H-012 **0.506** — just above 0.50 threshold.
- Notes: Volume-filtered momentum doesn't differentiate enough from raw momentum. High-volume days in crypto are ubiquitous enough that filtering has minimal effect on rankings. Correlation 0.506 is borderline but reflects fundamental similarity. Split-half stability (1.044/1.082) is excellent.
- Sessions: [2026-04-07 session 158]

## H-299: Decorrelation Signal Factor
- Status: REJECTED
- Idea: Assets whose correlation with the market is decreasing (decorrelating, "breaking away") are establishing idiosyncratic trends.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = long_window_corr_with_market - short_window_corr_with_market. High = decorrelating → LONG. Grid: SC∈[5,10,15] × LC∈[30,40,60] × R∈[3,5,7] × N∈[3,4] = 54 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **1.9%** positive in decorrelation direction (1/54). **HOWEVER**, reverse direction (recorrelation_long) **98.1%** positive — but best Sharpe only 0.116. Corr H-012 **-0.012** (near zero, genuinely novel). **REJECTED** — signal magnitude too weak in both directions.
- Notes: Interesting finding: assets RE-JOINING the herd outperform (98.1% in reverse), while decorrelating assets underperform. This makes sense — crypto is herding/beta-driven, so convergence = momentum confirmation. But the magnitude is too weak (best Sharpe 0.116) to be tradeable. Near-zero H-012 correlation shows this captures something genuinely different, just not strong enough.
- Sessions: [2026-04-07 session 158]

## H-300: Short-Term Reversal Factor (1-5 Day Contrarian)
- Status: REJECTED
- Idea: Buy recent losers, sell recent winners over 1-5 day horizons. Opposite of momentum — mean-reversion at short time scales.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = -pct_change(lookback). Grid: LB∈[1,2,3,5] × R∈[1,2,3,5] × N∈[3,4] = 32 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **56.2%** positive (18/32). Best: LB2_R3_N4 Sharpe **1.436**, +69.9% ann, -27.7% DD. WF **5/6** mean **1.366**. Split-half 1.597/**-0.800**. Corr H-012 **-0.122** (negative = diversifier). **REJECTED** — IS too low, split-half fails.
- Notes: Short-term reversal exists in crypto (WF 5/6, mean 1.366 is excellent) but is parameter-sensitive: LB2 works (Sharpe 0.435 mean), LB1 and LB5 don't. Negative correlation with H-012 means this is a genuine anti-momentum signal. H2 failure suggests reversal effect may be weakening over time.
- Sessions: [2026-04-07 session 159]

## H-301: Correlation Centrality Factor
- Status: REJECTED
- Idea: Rank assets by average pairwise rolling correlation (centrality in correlation network). Long peripheral, short central assets.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = -mean(rolling_corr with all others). Grid: CW∈[20,30,40,60] × R∈[3,5,7] × N∈[3,4] = 24 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **91.7%** positive (22/24). Best: CW60_R7_N3 Sharpe **1.514**, +75.9% ann, -25.4% DD. WF **4/6** mean **0.622**. Split-half 2.796/**-0.420**. Corr H-012 **0.414**. **REJECTED** — split-half fails (H2 negative).
- Notes: Strong IS robustness (91.7%) with clear signal: peripheral assets outperform central ones. CW60 dominates (mean Sharpe 1.194, 6/6 positive). But the signal degraded in the second half (H2=-0.420), suggesting the peripheral-alpha may have been arbitraged away or correlation structure changed. Modestly correlated with momentum (0.414).
- Sessions: [2026-04-07 session 159]

## H-302: Consecutive Direction Streak Factor
- Status: REJECTED
- Idea: Count consecutive positive/negative daily return streaks as non-linear momentum encoding. Test both continuation (long winning streaks) and reversal (long losing streaks).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = streak_count (capped at max_lb). Grid: ML∈[10,14,20,30] × R∈[3,5,7] × N∈[3,4] × dir∈[continuation,reversal] = 48 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **0.0%** positive (0/48). Best: ML10_R5_N3_reversal Sharpe **-0.452**. Mean Sharpe **-1.192**. Neither direction works. **REJECTED** — zero IS positive.
- Notes: Pure direction count (ignoring magnitude) has absolutely no cross-sectional predictive power in crypto. Both continuation and reversal are equally useless (mean Sharpe -1.198 vs -1.186). Magnitude matters; direction alone is noise.
- Sessions: [2026-04-07 session 159]

## H-303: Asymmetric Volatility Factor (Upside/Downside Vol Ratio)
- Status: REJECTED
- Idea: Ratio of upside to downside realized volatility. High ratio = bullish vol structure → LONG.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = std(positive_returns) / std(negative_returns). Grid: LB∈[10,20,30,40] × R∈[3,5,7] × N∈[3,4] = 24 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **37.5%** positive (9/24). Best: LB20_R5_N3 Sharpe **1.102**, +45.4% ann, -31.9% DD. WF **5/6** mean **0.970**. Split-half 0.733/1.408 (PASS!). Corr H-012 **0.407**. **REJECTED** — IS too low (only LB20 works, 6/6; all other lookbacks fail).
- Notes: The up/down vol asymmetry signal is real but extremely lookback-sensitive: LB20 gives 6/6 positive (mean 0.902) while LB10(-0.684), LB30(-0.649), LB40(-0.126) all negative. WF and split-half both pass. This is a genuine signal (crypto assets with bigger up moves than down moves continue to outperform) but too fragile to deploy.
- Sessions: [2026-04-07 session 159]

## H-304: Exponentially-Weighted Momentum Factor
- Status: REJECTED
- Idea: EWM of daily returns (recent days weighted more) instead of simple N-day return momentum.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = ewm(daily_returns, span). Grid: SPAN∈[5,10,20,30,40] × R∈[3,5,7] × N∈[3,4] = 30 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **76.7%** positive (23/30). Best: SPAN30_R7_N4 Sharpe **0.938**, +36.7% ann, -33.6% DD. WF **4/6** mean **0.625**. Split-half 1.767/0.317 (pass). Corr H-012 **0.631**. **REJECTED** — IS borderline 76.7% (below 80%), corr 0.631 too high.
- Notes: EWM momentum is just momentum with a recency decay — as span increases, correlation with H-012 increases monotonically (SPAN5: 0.230, SPAN40: 0.658). SPAN10 is interesting (corr 0.267, 6/6 positive) but IS doesn't reach 80%. Confirms that any momentum variant ends up correlated with standard momentum.
- Sessions: [2026-04-07 session 159]

## H-305: Beta Change Factor (Rolling Beta Acceleration)
- Status: REJECTED
- Idea: Rank 13 non-BTC assets by change in rolling beta to BTC (short_beta - long_beta). Test both increasing-beta-long and decreasing-beta-long.
- Instrument: futures (13 alt perps, BTC excluded)
- Timeframe: 1D
- Logic: signal = short_beta - long_beta (or negated). Grid: SB∈[10,20] × LB∈[30,40,60] × R∈[3,5,7] × N∈[3,4] × dir∈[increasing,decreasing] = 72 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **44.4%** positive (32/72). Best: SB10_LB30_R7_N4_increasing_long Sharpe **0.974**, +33.8% ann, -45.0% DD. WF **4/6** mean **1.686**. Split-half -0.123/0.810. Corr H-012 **0.174** (low, novel). **REJECTED** — IS too low, split-half H1 negative.
- Notes: Increasing-beta-long slightly better (47.2%) than decreasing (41.7%) — assets becoming more BTC-correlated tend to outperform. Low H-012 correlation (0.174) means this IS genuinely novel. But beta dynamics in crypto are too noisy (45% DD). WF high (1.686) but concentrated in recent folds (3-5: Sharpe 4.2, 3.6, 2.3). May be worth revisiting.
- Sessions: [2026-04-07 session 159]

## H-306: Volume-Price Divergence Factor
- Status: REJECTED
- Idea: Cross-sectional divergence between volume rank and price rank. Assets where volume is growing more than price are experiencing accumulation.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = rank(volume_pct_change) - rank(price_pct_change). Grid: PLB∈[10,20,30] × VLB∈[10,20,30] × R∈[3,5,7] × N∈[3,4] = 54 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **38.9%** positive (21/54). Best: P30_V10_R7_N3 Sharpe **1.383**, +59.7% ann, -36.1% DD. WF **5/6** mean **1.747**. Split-half 0.726/0.610 (PASS!). Corr H-012 **-0.447** (strongly negative, excellent diversifier). **REJECTED** — IS too low.
- Notes: **Most interesting rejection this session.** Corr -0.447 with H-012 makes this the strongest anti-momentum diversifier found in 307 hypotheses. WF 5/6 (mean 1.747) and split-half both pass. The accumulation signal (volume growing faster than price = buying pressure without price confirmation) is a genuine contrarian signal. But IS robustness is only 38.9% — the signal is too sensitive to lookback mismatches (price 30d + volume 10d works, but most other combos don't). The exhaust direction would be 61.1% positive.
- Sessions: [2026-04-07 session 159]

## H-307: Return Distribution Entropy Factor
- Status: REJECTED
- Idea: Shannon entropy of binned daily return distribution. Long low-entropy (predictable) assets, short high-entropy (random) assets.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = -entropy(histogram(returns, n_bins)). Grid: LB∈[10,20,30,40] × B∈[3,5,7] × R∈[3,5,7] × N∈[3,4] = 72 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **12.5%** positive low-entropy-long (9/72). **REVERSE**: high-entropy-long **87.5%** positive (63/72). Best: LB10_B3_R7_N3 Sharpe **0.613**, +18.0% ann, -28.9% DD. Corr H-012 **-0.105**. **REJECTED** — IS too low in intended direction, reverse direction too weak.
- Notes: Counterintuitive finding: high-entropy (random/unpredictable) assets outperform predictable ones 87.5% of the time. This might be because "predictable" in crypto means "stuck in a range" while "unpredictable" means "making large moves in both directions" = higher expected absolute returns. But the magnitude is too weak (mean Sharpe -0.518 even in the intended direction). Near-zero H-012 correlation (-0.105) confirms this is a genuinely novel signal type.
- Sessions: [2026-04-07 session 159]

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

## H-308: Time-Series Momentum (TSMOM) Multi-Asset
- Status: REJECTED
- Idea: Classic TSMOM across 14 crypto assets. Each asset independently long/short based on own past N-day return.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = sign(past_return). Grid: LB∈[5,10,14,20,30,60] × R∈[1,3,5,7] = 24 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **70.8%** positive (17/24). Best: LB60_R7 Sharpe **1.074**, +69.2% ann, **-50.3%** DD. Mean Sharpe 0.255. **REJECTED** — excessive drawdowns (34-75%).
- Notes: TSMOM signal exists in crypto but is heavily regime-dependent. Works in trending markets, gets whipsawed in ranges. Max DD 50%+ is unacceptable.
- Sessions: [2026-04-07 session 160]

## H-309: Vol-Scaled TSMOM Multi-Asset
- Status: REJECTED
- Idea: TSMOM with per-asset inverse-vol sizing (risk parity). Target 15% ann vol per asset, cap 3x leverage.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = sign(past_ret) × min(target_vol/realized_vol, 3). Grid: LB∈[10-60] × VW∈[10,20,30] × R∈[3,5,7] = 60 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **60.0%** positive. Best: LB60_VW10_R7 Sharpe **1.176**, +15.1% ann, **-10.6%** DD. Vol scaling dramatically improves DD. But WF **3/5** (mean OOS -0.216). Split-half PASS (2.48/0.62). Neighbors 63.3%. **REJECTED** — WF fails, regime-dependent.
- Notes: Vol scaling fixes the DD problem but the strategy still gets whipsawed in ranging markets. Recent folds (2025-2026) show negative OOS Sharpe. Corr 0.312 H-012, 0.519 H-009.
- Sessions: [2026-04-07 session 160]

## H-310: EMA Crossover Multi-Asset Trend Following
- Status: REJECTED
- Idea: EMA(fast) vs EMA(slow) crossover signal applied to all 14 assets independently.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = sign(EMA_fast - EMA_slow). Grid: F∈[5,10,20] × S∈[20,40,60,100] × R∈[1,3,5] = 33 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **84.8%** positive (28/33). Best: F20_S40_R5 Sharpe **0.670**, +42.3% ann, **-56.1%** DD. Mean 0.272. **REJECTED** — high IS% but Sharpes too low and DDs 50-60%.
- Sessions: [2026-04-07 session 160]

## H-311: Donchian Channel Breakout Multi-Asset
- Status: REJECTED
- Idea: Buy on N-day high breakout, sell on N-day low breakout. Applied to all 14 assets.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **41.7%** positive (5/12). **REJECTED** — coin flip.
- Sessions: [2026-04-07 session 160]

## H-312: Time-Series Carry (Funding Rate)
- Status: REJECTED
- Idea: TS version of carry: each asset independently long when funding < 0 (earn funding), short when > 0. Not XS ranking.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = -sign(avg_funding_rate). Grid: LB∈[3-20] × R∈[1,3,5,7] = 24 combos.
- Data: 14 assets with funding, 661 daily bars.
- Result: IS **91.7%** positive (22/24). Best: LB5_R5 Sharpe **0.708**, +43.3% ann, **-65.1%** DD. Mean 0.215. **REJECTED** — 100% IS positive on vol-weighted version (40/40, mean 0.347) but DDs 60%+ and WF 3/5 (mean 0.033).
- Notes: Corr -0.605 vs BTC (strategy tends to be short BTC since BTC usually has positive funding). This creates built-in negative beta. Corr 0.034 vs H-012 (great). But WF is too unstable.
- Sessions: [2026-04-07 session 160]

## H-313: Multi-Timeframe TSMOM Ensemble (Vol-Scaled)
- Status: REJECTED
- Idea: Ensemble of TSMOM signals from multiple lookbacks (short/medium/long), vol-scaled. Reduces whipsaw.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = mean(sign(ret_5d), sign(ret_20d), sign(ret_60d)) × vol_sizing. Grid: 5 LB combos × 2 VW × 3 R = 30 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **96.7%** positive (29/30)! Best: LBs=(5,20,60)_VW20_R7 Sharpe **0.940**, +9.0% ann, **-5.5%** DD. But WF **2/5** (mean OOS -0.311). Split-half PASS (1.64/0.32). **REJECTED** — outstanding IS robustness but WF fails on recent periods.
- Notes: The ensemble smooths whipsaw beautifully (96.7% IS, only -5.5% DD) but is still regime-dependent. Corr 0.198 H-012, 0.562 H-009.
- Sessions: [2026-04-07 session 160]

## H-314: Time-Series Mean Reversion (Z-Score)
- Status: REJECTED
- Idea: Per-asset z-score of rolling returns. Buy oversold (z < -thresh), sell overbought (z > +thresh).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: z = rolling_mean(ret) / rolling_std(ret). Grid: LB∈[5,10,14,20] × Z∈[0.5,1.0,1.5,2.0] × H∈[1,3,5] = 48 combos.
- Data: 14 assets, 731 daily bars.
- Result: IS **45.8%** positive (22/48). Best: LB5_Z2.0_H3 Sharpe **1.392**, +7.6% ann, -4.8% DD. **REJECTED** — only 45.8% IS, too parameter-sensitive.
- Sessions: [2026-04-07 session 160]

## H-315: RSI Mean Reversion (TS)
- Status: REJECTED
- Idea: Buy when RSI < 30, sell when RSI > 70 across 14 assets independently.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **50.0%** positive (54/108). **REJECTED** — coin flip.
- Sessions: [2026-04-07 session 160]

## H-316: Bollinger Band Mean Reversion (TS)
- Status: REJECTED
- Idea: Buy below lower band, sell above upper band across 14 assets.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **50.0%** positive (24/48). **REJECTED** — coin flip.
- Sessions: [2026-04-07 session 160]

## H-317: Turn-of-Month Effect (Multi-Asset)
- Status: REJECTED
- Idea: Go long all assets on last/first N days of month (academic TOM effect).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **0.0%** positive (0/9). All negative. **REJECTED** — TOM effect does not exist in 24/7 crypto.
- Sessions: [2026-04-07 session 160]

## H-318: Options Expiry Day Effect (BTC)
- Status: REJECTED
- Idea: Exploit BTC price patterns around weekly options expiry (Fridays).
- Instrument: futures (BTC)
- Timeframe: 1D
- Result: Shorting around expiry: Sharpe 0.573. **REJECTED** — too weak and small sample.
- Sessions: [2026-04-07 session 160]

## H-319: Vol-Regime Adaptive Strategy (BTC)
- Status: REJECTED
- Idea: Switch between trend-following (high vol) and mean-reversion (low vol) based on vol percentile regime.
- Instrument: futures (BTC)
- Timeframe: 1D
- Result: IS **65.4%** positive (53/81). Best: VW14_VP70_MOM30_MR10 Sharpe **1.202**, +54.8% ann, -23.0% DD. **REJECTED** — BTC-only, 65% IS, not robust enough.
- Sessions: [2026-04-07 session 160]

## H-320: Vol-Weighted TS Carry (Funding)
- Status: REJECTED
- Idea: TS funding carry with vol-scaling. Per-asset independent signal + risk parity sizing.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **100%** positive (40/40). Best: LB3_VW10_R7 Sharpe **0.789**, +9.5% ann, -13.0% DD. But WF **3/5** (mean OOS 0.033). Split-half PASS (0.91/0.52). Corr 0.034 H-012, -0.605 BTC. **REJECTED** — 100% IS but WF marginal.
- Sessions: [2026-04-07 session 160]

## H-321: BTC Volatility Targeting
- Status: REJECTED
- Idea: Always long BTC, adjust leverage by inverse realized vol (classic vol-targeting).
- Instrument: futures (BTC)
- Timeframe: 1D
- Result: IS **100%** positive (20/20) but only **20%** beat buy-and-hold. Best: VW7 Sharpe 0.353 vs BH 0.286. **REJECTED** — doesn't materially improve on holding BTC.
- Sessions: [2026-04-07 session 160]

## H-322: Hourly Mean-Reversion (Multi-Asset)
- Status: REJECTED
- Idea: Short-term (2-6h) z-score mean reversion on hourly crypto data across 14 assets.
- Instrument: futures (14 perps)
- Timeframe: 1H
- Data: 14 assets, 25,686 hourly bars (3 years).
- Result: IS **88.9%** positive (48/54). Best: LB3_Z1.0_H1 Sharpe **2.386**, +45.2% ann. **BUT** at 0.02% taker fee: Sharpe **-0.196**. **REJECTED** — signal exists but doesn't survive trading costs.
- Notes: Key finding: hourly mean-reversion alpha in crypto is real but captured entirely by fees. At 0.01% (maker): Sharpe 1.10. At 0.02% (taker): negative. Trades ~12.6×/day. WF with fees: 2/5.
- Sessions: [2026-04-07 session 160]

## H-323: Hourly Momentum (Multi-Asset)
- Status: REJECTED
- Idea: Trend-following on hourly data across 14 assets.
- Instrument: futures (14 perps)
- Timeframe: 1H
- Result: IS **65.0%** positive (13/20). Best: LB12h_R8h Sharpe **1.274**, +75.3% ann. **REJECTED** — 65% IS, would also suffer from fees. Not tested with fees as IS already borderline.
- Sessions: [2026-04-07 session 160]

## H-324: ADX-Filtered Multi-Asset TSMOM (Vol-Scaled)
- Status: CONFIRMED
- Idea: Time-series momentum across 14 assets, filtered by BTC ADX > 30 (only trade when market is trending). Vol-scaled per asset.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: signal = sign(60d_return) × min(target_vol/realized_vol, 3x). Filter: BTC ADX(14) > 30. Rebalance every 7d. Flat when ADX below threshold.
- Data: 14 assets, 731 daily bars.
- Result: IS **65.6%** positive (42/64, full grid). **Best: LB60_ADX30_R7** Sharpe **1.206**, +12.7% ann, **-8.0%** DD, 60% exposure. WF **4/5** positive (mean OOS **0.557**). Split-half **PASS** (2.107/0.834). Neighbors **77.5%** positive (62/80). Corr 0.216 H-012, 0.414 H-009, 0.023 H-076.
- Notes: ADX filter is the key innovation — removes whipsaw periods that destroy pure TSMOM. When BTC ADX < 30, strategy goes flat instead of getting chopped up. 60% exposure means capital-efficient when active. First TS strategy to pass WF validation this session (4/5 vs 2-3/5 for all others). Paper trade deployed as #41.
- Sessions: [2026-04-07 session 160]

## H-325: BTC-Conditioned Altcoin Direction
- Status: REJECTED
- Idea: Use BTC trend direction to select high-beta altcoins in same direction.
- Instrument: futures (13 alts)
- Timeframe: 1D
- Result: IS **8.3%** positive (3/36). **REJECTED** — BTC signal doesn't help pick altcoin direction.
- Sessions: [2026-04-07 session 160]

## H-326: Volatility Breakout (Multi-Asset)
- Status: REJECTED
- Idea: Enter when daily range exceeds N-day avg by X std, trade in direction of the breakout.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **31.2%** positive (15/48). **REJECTED** — not robust.
- Sessions: [2026-04-07 session 160]

## H-327: Return Persistence / Autocorrelation (TS)
- Status: REJECTED
- Idea: Trade based on short-term return autocorrelation (momentum vs reversal at 1-5d).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **50.0%** positive (12/24). **REJECTED** — coin flip between momentum and reversal.
- Sessions: [2026-04-07 session 160]

## H-328: Market Timing (EW Long / Flat)
- Status: REJECTED
- Idea: Long equal-weight all assets when momentum positive, flat when negative. Simple risk-on/off.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **23.3%** positive (7/30). **REJECTED** — simple market timing doesn't work in crypto.
- Sessions: [2026-04-07 session 160]

## H-329: BTC Lead-Lag Hourly (Cross-Asset)
- Status: REJECTED
- Idea: Use BTC 1h return to predict next-hour altcoin returns (lead-lag effect).
- Instrument: futures (13 alts, 1H)
- Timeframe: 1H
- Data: 25,686 hourly bars.
- Result: **Reversal** (contrarian) Sharpe **1.658** pre-fees. At 0.02% fee: Sharpe **-0.737**. Signal changes 52.6% of hours (~12.6 trades/day). **REJECTED** — doesn't survive fees.
- Notes: Strong hourly reversal pattern: when BTC moves up, altcoins tend to reverse next hour. But trading costs kill it. Even at maker fees (0.01%), only Sharpe 0.46.
- Sessions: [2026-04-07 session 160]

## H-330: Range Compression Breakout
- Status: REJECTED
- Idea: Enter when range contracts below N-percentile (compression), trade in direction of first breakout.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **40.7%** positive (11/27). Best: W14_P30%_H1 Sharpe **1.702** but only 40.7% IS. **REJECTED** — very parameter-sensitive.
- Sessions: [2026-04-07 session 160]

## H-331: ATR Trailing Stop Trend Following
- Status: REJECTED
- Idea: Multi-asset stop-and-reverse trend following using ATR trailing stops, vol-scaled.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **77.8%** positive (21/27) but mean Sharpe **0.047**. Best: AP14_AM2.5 Sharpe **0.132**. **REJECTED** — survives but doesn't make money.
- Sessions: [2026-04-07 session 160]

## H-332: Bar Consistency Score (4h Microstructure)
- Status: LIVE (paper trade since 2026-04-07)
- Idea: Rank assets by intraday bar consistency — fraction of 4h bars closing in the majority direction, averaged over lookback. Clean intraday momentum across all sessions predicts continuation.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 4h, trade daily)
- Logic: Compute per-day consistency (max(n_green, n_red)/n_total, signed by majority direction). Average over lookback. Long top N (highest consistency), short bottom N.
- Result: IS **100%** high_long (24/24). Best LB10_R3_N3 Sharpe **2.437**. WF **6/6** mean **1.961** (1.09, 1.90, 2.72, 3.58, 1.23, 1.26). Split-half H1=2.337, H2=2.587. Neighbors 8/8=100%. Corr H-012 **0.147**, H-076 **0.111**. Novel 4h microstructure signal.
- Notes: IS overall 50% because opposite direction (low_long) always fails — expected for directional factor. Signal exploits broad-based buying across all sessions (Asia+Europe+US).
- Sessions: [2026-04-07 session 161]

## H-333: Smart Volume Return (4h Microstructure)
- Status: CONFIRMED (not deployed, corr 0.428 with H-012)
- Idea: Rank assets by the return of the highest-volume 4h bar, averaged over lookback. Captures directional bias of informed high-volume activity.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 4h, trade daily)
- Result: IS **100%** high_long (24/24). Best LB10_R3_N3 Sharpe **2.447**. WF **6/6** mean **2.467**. Split-half H1=2.145, H2=2.924. Corr H-012 **0.428** (borderline). Novel but partially overlaps momentum.
- Sessions: [2026-04-07 session 161]

## H-334: Intraday Range Efficiency (4h)
- Status: REJECTED
- Idea: Daily range / sum(4h ranges) — measures persistence of intraday moves.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **45.8%** positive. No dominant direction. High_long 37.5%, low_long 54.2%. **REJECTED** — no clear XS signal from intraday range efficiency.
- Sessions: [2026-04-07 session 161]

## H-335: Session Autocorrelation (4h)
- Status: REJECTED
- Idea: Correlation of consecutive session returns (Asia→Europe, Europe→US) over lookback. High autocorrelation = predictable session flow.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **43.8%** positive. High_long 87.5% but too few configs overall. Best Sharpe 1.107. **REJECTED** — signal too weak across parameter space.
- Sessions: [2026-04-07 session 161]

## H-336: Volume Surprise Factor
- Status: LIVE (paper trade since 2026-04-07)
- Idea: Rank assets by volume surprise — recent volume vs rolling average. High surprise = unusual institutional activity, predicts XS continuation.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Compute 5-day avg volume / lookback avg volume for each asset. Long top N (highest surprise), short bottom N (quietest).
- Result: IS **100%** high_long (18/18). Best LB30_R3_N4 Sharpe **2.766**. WF **6/6** mean **2.684** (0.35, 4.99, 3.64, 3.14, 1.76, 2.23). Split-half H1=3.084, H2=2.445. Corr H-012 **0.003**, H-076 **0.038**. **Near-zero correlation with ALL existing strategies — best diversifier found in 337 hypotheses.**
- Notes: IS overall 50% (opposite direction always fails). Pure volume signal uncorrelated with price momentum — genuinely novel alpha source.
- Sessions: [2026-04-07 session 161]

## H-337: Intraday Closing Pressure (4h)
- Status: REJECTED
- Idea: Average close-location-value across 4h bars over lookback. High CLV = buying pressure.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **45.8%** positive. High_long 83.3% but overall grid too mixed. **REJECTED** — CLV at 4h level doesn't distinguish assets well enough in XS.
- Sessions: [2026-04-07 session 161]

## H-338: Volume-Weighted Directional Pressure (4h)
- Status: CONFIRMED (not deployed, overlaps H-332/H-336 signal family)
- Idea: Sum of (volume × sign(return)) normalized by total volume over lookback. Captures net buying/selling pressure weighted by activity.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from hourly, trade daily)
- Result: IS **100%** high_long (24/24). Best LB10_R3_N4 Sharpe **2.136**. WF **6/6** mean **2.390**. Split-half H1=1.842, H2=2.428. Corr H-012 **0.289**. Not deployed to avoid overlap with H-332/H-336.
- Sessions: [2026-04-07 session 161]

## H-339: Intraday Momentum Propagation (4h)
- Status: REJECTED
- Idea: Correlation between first 4h bar return and rest-of-day return. High propagation = predictable session flow.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **50%** overall. Low_long 75% (below 80% threshold). WF 4/6 positive (marginal). Best Sharpe 1.031. **REJECTED** — signal exists in low_long direction but insufficient robustness.
- Sessions: [2026-04-07 session 161]

## H-340: 4h Price Path Convexity
- Status: REJECTED
- Idea: Measure second-half vs first-half 4h momentum — acceleration vs deceleration.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **41.7%** positive. High_long 83.3% but overall weak. Best Sharpe 1.634. **REJECTED** — intraday acceleration not robust enough as XS signal.
- Sessions: [2026-04-07 session 161]

## H-341: Return Concentration in High-Volume Hours
- Status: REJECTED
- Idea: Fraction of daily return from top-2 volume hours. High concentration = institutional-driven.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **39.6%** positive. High_long 66.7%. Best Sharpe 0.729. **REJECTED** — return concentration has no reliable XS predictive power.
- Sessions: [2026-04-07 session 161]

## H-342: Volume-Price Synchronicity (Hourly Microstructure)
- Status: CONFIRMED (deployed session 162)
- Idea: Rank assets by corr(hourly volume, |hourly return|) over lookback. High sync = volume appears when price moves (efficient market participation).
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from hourly, trade daily)
- Result: IS **100%** high_long (24/24, overall 50% because low_long 0% — directional signal). Best LB10_R5_N4 Sharpe **1.095**. WF **5/6** mean **1.175**. Split-half H1=0.600, H2=1.584. Corr H-012 **0.273**, H-076 **0.004** (excellent diversifier). Neighbors 12/12 = 100%.
- Notes: Framework refinement — for directional signals where one direction is 100% positive and the other 0%, evaluate IS on dominant direction only. VP sync captures a fundamentally different aspect of market microstructure from momentum or trend quality.
- Sessions: [2026-04-08 session 162]

## H-343: Intraday Momentum Decay (4h Microstructure)
- Status: CONFIRMED (deployed session 162)
- Idea: Rank assets by avg (close-open)/(high-low) of 4h bars over lookback. High = bars closing near highs (sustained buying). Low = intraday gains given back.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 4h, trade daily)
- Result: IS **100%** high_long (24/24, overall 50% — directional). Best LB10_R3_N3 Sharpe **4.051**. WF **6/6** mean **4.163** (best WF ever!). Split-half H1=3.789, H2=4.342. Corr H-012 **0.225**, H-076 **0.101**. Neighbors 8/8 = 100%. Cross-corr with H-342: 0.072, H-348: 0.717.
- Notes: Extraordinary signal — sustained intraday buying pressure predicts XS continuation. Corr 0.717 with H-348 (trend strength R²) so they measure related but different aspects of intraday quality; keep H-343 (higher Sharpe).
- Sessions: [2026-04-08 session 162]

## H-344: Volume Clustering (Hourly Gini)
- Status: REJECTED
- Idea: Gini coefficient of hourly volumes within each day. High clustering = institutional block trades.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **39.6%** positive. Low_long 62.5%, high_long 16.7%. Best Sharpe 0.590. **REJECTED** — volume clustering pattern has no reliable XS signal.
- Sessions: [2026-04-08 session 162]

## H-345: Asia-US Session Return Spread
- Status: REJECTED
- Idea: Avg (US session return - Asia session return) over lookback. Captures institutional flow timing.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **41.7%** positive. High_long 75.0%, low_long 8.3%. Best Sharpe 1.183. **REJECTED** — session-level return spread too noisy for reliable XS ranking.
- Sessions: [2026-04-08 session 162]

## H-346: Hourly Return Kurtosis
- Status: REJECTED
- Idea: Kurtosis of hourly returns over lookback. High = fat tails (event-driven). Low = smooth/mean-reverting.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **50%** overall (high_long 95.8%, low_long 4.2%). Best Sharpe 0.945. WF 3/6 (fail). **REJECTED** — direction clear but WF inconsistent.
- Sessions: [2026-04-08 session 162]

## H-347: Volume-Weighted Close Location (Hourly)
- Status: REJECTED
- Idea: VWAP-like intraday positioning — avg CLV weighted by hourly volume. Captures where in range heavy volume traded.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **47.9%** positive. High_long 83.3%, low_long 12.5%. Best Sharpe 1.527. **REJECTED** — insufficient overall IS robustness.
- Sessions: [2026-04-08 session 162]

## H-348: Intraday Trend Strength (Hourly R²)
- Status: REJECTED (redundant with H-343, corr 0.717)
- Idea: R² of cumulative hourly returns vs time within each day. High R² = clean intraday trend.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **100%** high_long (24/24, overall 50%). Best LB10_R3_N3 Sharpe **2.983**. WF **6/6** mean **3.035**. Split-half H1=2.887, H2=3.093. Corr H-012 **0.231**, H-076 **0.211**. **Strong signal but corr 0.717 with H-343** — rejected as redundant (H-343 has higher Sharpe 4.05 vs 2.98).
- Sessions: [2026-04-08 session 162]

## H-349: Opening Gap Fill Rate
- Status: REJECTED
- Idea: Fraction of days where first-hour return reverses into rest-of-day. High fill = mean-reverting.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **45.8%** positive. Low_long 58.3%, high_long 33.3%. Best Sharpe 0.834. **REJECTED** — gap fill behavior too weak and inconsistent as XS signal.
- Sessions: [2026-04-08 session 162]

## H-350: Opening Drive Ratio
- Status: REJECTED
- Idea: First 4h bar's absolute return / full day's range. High = opening session dominates the day.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **53.3%** dominant direction (high_long). Best LB30_R3_N3 Sharpe 0.810. **REJECTED** — IS 53.3% < 80%.
- Sessions: [2026-04-08 session 163]

## H-351: Volume Profile Skewness
- Status: LIVE (paper trade since 2026-04-08)
- Idea: Skewness of hourly volume distribution within each day. Low skew = front-loaded volume (institutional conviction). High skew = back-loaded (retail chase).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5 days)
- Logic: Rank by rolling 30-day avg vol skewness. Long low-skew (front-loaded), short high-skew.
- Data: 14 assets, 1072 daily bars (~2.9yr). WF: 6 folds.
- Result: IS **100%** low_long (30/30). Best LB30_R5_N3 Sharpe **1.438**, +95.7% ann, -44.7% DD. WF **5/6** mean **1.339**. Split-half H1=1.109, H2=0.588. Neighbor 100%. Corr H-012 **0.179**, H-076 **-0.063**. Cross-corr: 0.286 H-353, -0.180 H-355.
- Sessions: [2026-04-08 session 163]

## H-352: Intraday R-squared (Hourly)
- Status: REJECTED
- Idea: R² of hourly cumulative returns vs time. High = clean intraday trend. Low = choppy.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **76.7%** dominant direction (high_long). Best LB14_R7_N4 Sharpe 0.615. **REJECTED** — IS 76.7% < 80%.
- Sessions: [2026-04-08 session 163]

## H-353: Volume Persistence
- Status: LIVE (paper trade since 2026-04-08)
- Idea: Autocorrelation of hourly volumes within a day. High persistence = sustained institutional engagement. Low = sporadic bursts.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3 days)
- Logic: Rank by rolling 5-day avg hourly volume autocorrelation. Long high-persistence, short low.
- Data: 14 assets, 1072 daily bars (~2.9yr). WF: 6 folds.
- Result: IS **100%** high_long (30/30). Best LB5_R3_N4 Sharpe **2.501**, +146.2% ann, -19.5% DD. WF **5/6** mean **2.526** (excellent). Split-half H1=1.592, H2=1.035. Neighbor 100%. Corr H-012 **0.196**, H-076 **-0.030**. Cross-corr: 0.286 H-351, 0.057 H-355.
- Sessions: [2026-04-08 session 163]

## H-354: Session Momentum Ratio
- Status: REJECTED
- Idea: US session return / (Asia + Europe session return). Captures institutional vs retail flow imbalance.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **43.3%** dominant direction (low_long). Best LB20_R7_N3 Sharpe 0.623. **REJECTED** — IS 43.3% < 80%.
- Sessions: [2026-04-08 session 163]

## H-355: Hourly Return Entropy
- Status: LIVE (paper trade since 2026-04-08)
- Idea: Shannon entropy of discretized hourly returns. Low entropy = structured/trending intraday price action. High entropy = random walk.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3 days)
- Logic: Rank by rolling 14-day avg return entropy. Long low-entropy (structured), short high.
- Data: 14 assets, 1072 daily bars (~2.9yr). WF: 6 folds.
- Result: IS **100%** low_long (30/30). Best LB14_R3_N3 Sharpe **1.657**, +101.9% ann, -37.0% DD. WF **5/6** mean **1.684**. Split-half H1=0.353, H2=1.059. Neighbor 100%. Corr H-012 **0.079**, H-076 **-0.020**. Cross-corr: -0.180 H-351, 0.057 H-353. Near-zero correlation with everything.
- Sessions: [2026-04-08 session 163]

## H-356: Volume-at-Extremes
- Status: REJECTED
- Idea: Fraction of daily volume occurring at hours with price near daily high or low. High = breakout behavior.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **46.7%** dominant direction (high_long). Best LB14_R7_N4 Sharpe 0.933. **REJECTED** — IS 46.7% < 80%.
- Sessions: [2026-04-08 session 163]

## H-357: Intraday Mean Reversion Speed
- Status: REJECTED
- Idea: |first hour return| - |full day return|. High = first move reverses. Low = extends.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **100%** low_long (30/30). Best LB5_R3_N3 Sharpe 1.641. WF **5/6** mean 1.441. **Split-half fail** (H1=1.893, H2=-0.073). Neighbor 100%. **REJECTED** — signal degrades in second half.
- Sessions: [2026-04-08 session 163]

## H-358: Cross-Asset Hourly Synchronicity with BTC
- Status: REJECTED
- Idea: Fraction of hours where an asset moves in same direction as BTC, averaged over lookback. High sync = institutional, low = retail.
- Instrument: futures (14 perps, hourly signal → daily trade)
- Timeframe: 1D
- Result: IS **76.7%** high_long (23/30). Best LB20_R5_N3 Sharpe 1.129, +48.8%, -44.8% DD. **REJECTED** — IS 76.7% < 80%.
- Sessions: [2026-04-08 session 165]

## H-359: Volume-Weighted Return Asymmetry
- Status: REJECTED
- Idea: Ratio of volume on up-hours to down-hours, averaged over lookback. High ratio = buying pressure dominates.
- Instrument: futures (14 perps, hourly signal → daily trade)
- Timeframe: 1D
- Result: IS **60.0%** high_long (18/30). Best LB7_R7_N4 Sharpe 0.668. **REJECTED** — IS 60% < 80%.
- Sessions: [2026-04-08 session 165]

## H-360: Autocorrelation Decay Speed
- Status: REJECTED
- Idea: Difference between lag-1 and lag-4 hourly return autocorrelation. Slow decay (persistent AC) = predictable = long.
- Instrument: futures (14 perps, hourly signal → daily trade)
- Timeframe: 1D
- Result: IS **100%** low_long (18/18). Best LB10_R5_N4 Sharpe 1.456, +55.3%, -26.9% DD. **REJECTED** — too computationally expensive for WF validation; 3 lookback values only (18 combos).
- Sessions: [2026-04-08 session 165]

## H-361: Session Continuation Score
- Status: REJECTED
- Idea: Fraction of days where Asia session (0-8 UTC) direction matches US session (13-21 UTC). High continuation = trending intraday.
- Instrument: futures (14 perps, hourly signal → daily trade)
- Timeframe: 1D
- Result: IS **79.2%** low_long (19/24). Best LB14_R7_N4 Sharpe 1.036. **REJECTED** — IS 79.2% < 80% (close but below).
- Sessions: [2026-04-08 session 165]

## H-362: Volume-Weighted Intraday Beta
- Status: REJECTED
- Idea: Beta computed from hourly returns weighted by volume. High VW-beta = more responsive intraday.
- Instrument: futures (14 perps, hourly signal → daily trade)
- Timeframe: 1D
- Result: IS **50.0%** high_long (12/24). **REJECTED** — coin flip.
- Sessions: [2026-04-08 session 165]

## H-363: Multi-Day Return Pattern Factor
- Status: LIVE (paper trade since 2026-04-08)
- Idea: Rolling average of 2-day return streak indicators (up-up = +1, down-down = -1). High score = asset in consecutive-up patterns → long. Captures direction persistence at micro level.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 3 days)
- Logic: For each asset, compute streak_signal = I(2-day up-streak) - I(2-day down-streak). Average over 30-day lookback. Long top 3, short bottom 3.
- Data: 14 assets, 732 daily bars (~2yr). WF: 6 folds × 90d.
- Result: IS **83.3%** high_long (20/24). Best LB30_R3_N3 Sharpe **1.011**, +44.6% ann, -29.3% DD. WF **5/6** positive (mean OOS **0.611**, folds: 0.454/1.447/0.256/1.565/-1.078/1.020). Split-half H1=0.865, H2=0.536 — **PASS**. Neighbors **88.9%** positive (32/36). Corr H-012 **0.322**, H-076 **0.138**.
- Notes: Novel signal capturing direction persistence at 2-day micro level. Unlike momentum (60-day total return), this measures *consistency* of up-days. Low corr with all existing strategies. Deployed as paper trade #51.
- Sessions: [2026-04-08 session 165]

## H-364: Momentum Dispersion-Normalized Factor
- Status: REJECTED
- Idea: Each asset's momentum normalized by cross-sectional momentum dispersion. Risk-adjusted momentum signal.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **100%** high_long (30/30). Best LB10_R7_N3 Sharpe 1.257. WF **2/6** positive (mean 0.659). Split-half PASS (H1=1.543, H2=0.205). Neighbors **100%** (45/45). **REJECTED** — outstanding IS/neighbors but WF fails (only 2/6 folds positive).
- Notes: Likely regime-dependent; works in trending markets but fails in range-bound periods.
- Sessions: [2026-04-08 session 165]

## H-365: Volume-Price Trend (VPT) Factor
- Status: REJECTED
- Idea: Cumulative (return × volume) over lookback, ranked cross-sectionally. Classic VPT as XS signal.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **93.3%** high_long (28/30). Best LB60_R3_N3 Sharpe 1.325. WF **3/6** positive (mean 0.582). Split-half **FAIL** (H1=2.818, H2=-0.498). Neighbors 84.4%. **REJECTED** — signal degrades in second half (split-half fail) and WF only 3/6.
- Notes: VPT is essentially volume-weighted momentum — partially redundant with H-012/H-021 (corr 0.392 H-012). First half performance inflated by strong trending period.
- Sessions: [2026-04-08 session 165]

## H-366: Systematic BTC Bull Put Spread (Synthetic Backtest)
- Status: CONFIRMED (not deployable — no options paper trade infrastructure yet)
- Idea: Sell weekly 10% OTM BTC put, buy 20% OTM BTC put. Collect spread premium. Defined risk.
- Instrument: options (BTC)
- Timeframe: weekly (7-day expiry)
- Logic: Using synthetic BS pricing with IV = RV_30d + VRP_spread. Position size = 20% of equity at risk. Spread width = 10% of spot.
- Data: BTC daily bars, 732 days (~2yr). 92-100 weekly trades.
- Result: IS **93.1%** positive (134/144 param combos). Best: 10%OTM/+10%spread/7d/RV30/VRP0.15 Sharpe **4.39**, +50.1% ann, **-6.7%** DD, **95% WR**, 92 trades. WF **5/5** positive (mean **6.01**, folds: 10.74/2.27/8.42/7.56/1.05). At lower VRP assumption (0.10): Sharpe 1.81, +53.3%, -10.5% DD.
- Notes: **Strong synthetic backtest but CRITICAL CAVEATS**: (1) Uses assumed VRP of 10-15pp — actual VRP varies. Our 20-day IV data shows VRP ranges from -3pp to +18pp. (2) Assumes BS fair-value execution — real execution has wider spreads on Bybit options. (3) Defined risk is the major advantage over naked strangle (H-063). (4) BTC options liquidity on Bybit is improving but still thin for alts. **Recommendation**: Needs real-market paper trade validation once options execution is automated.
- Sessions: [2026-04-08 session 165]

## H-367: Systematic BTC Short Strangle (Synthetic Backtest Comparison)
- Status: CONFIRMED (synthetic — comparison with H-063)
- Idea: Sell weekly 5% OTM call + 5% OTM put. Pocket premium. Same as H-063 but synthetic backtest for comparison.
- Instrument: options (BTC)
- Timeframe: weekly (7-day expiry)
- Result: IS strong. 5%C/5%P: Sharpe **2.40**, +17.8% ann, **-3.0%** DD, 78% WR. WF **5/5** positive (mean 3.86). 3%C/5%P: Sharpe 2.27, +18.8%, -3.3% DD.
- Notes: Validates H-063's strangle approach. Synthetic Sharpe ~2.4 vs H-063 paper trade currently at -6.35% (BTC rallied 8% above call strike — a tail event). The synthetic backtest doesn't capture tail risk well since it settles at expiry only. H-063's real-time delta hedging adds cost but reduces tail risk.
- Sessions: [2026-04-08 session 165]

## H-368: Volume Market Share Drift Factor
- Status: LIVE (paper trade since 2026-04-08)
- Idea: Rank assets by change in their share of total market volume. Increasing volume share = growing institutional interest before price adjusts.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5 days)
- Logic: Compute each asset's dollar volume as fraction of total 14-asset volume. Rolling 30-day mean of share, then 5-day change (drift). Long top 3 (gaining share), short bottom 3 (losing share).
- Data: 14 assets, 732 daily bars (~2yr). IS: 54 param combos.
- Result: IS **90.7%** positive (49/54). Best LB30_DW5_R5_N3 Sharpe **1.628**, +85.5% ann, -23.8% DD. WF **6/6** positive (mean **2.034**, folds: 2.370/0.566/3.225/0.962/3.740/1.342). Split-half H1=1.290, H2=0.382 PASS. Neighbors 100% positive. Corr H-012 0.206, H-076 0.115.
- Notes: Genuinely novel signal — volume share captures institutional reallocation across crypto assets. Low correlation with all existing strategies. Very strong WF performance with all 6 folds positive.
- Sessions: [2026-04-08 session 166]

## H-369: Cross-Sectional Rank Momentum Factor
- Status: REJECTED (IS 43.1%)
- Idea: Rank assets by improvement in their cross-sectional return rank over time. Assets climbing in rank = momentum pickup.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 72 param combos.
- Result: IS 43.1% positive (31/72). Best Sharpe 1.154, +45.4% ann, -29.6% DD. Corr H-012 -0.103.
- Notes: Signal too noisy — rank changes don't provide consistent edge. Rank momentum is fundamentally noisier than return momentum.
- Sessions: [2026-04-08 session 166]

## H-370: Consecutive Direction Intensity Factor
- Status: REJECTED (IS 16.7%)
- Idea: Measure streak length × average return per streak day. Captures not just trending but intensity of trends.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 24 param combos.
- Result: IS 16.7% positive (4/24). Best Sharpe 0.308, +4.0% ann, -52.6% DD. Corr H-012 -0.156.
- Notes: Strong negative result — 83% negative. Signal direction is inverse (high intensity = bad). Even inverted, too noisy to be useful.
- Sessions: [2026-04-08 session 166]

## H-371: Volume Impulse Factor
- Status: REJECTED (IS 79.6% — borderline)
- Idea: First difference of smoothed log(volume). Captures sudden volume shifts. Volume impulse may precede price moves.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 54 param combos.
- Result: IS 79.6% positive (43/54) — just under 80% threshold. Best Sharpe 1.509, +74.5% ann, -24.5% DD. Corr H-012 0.022, H-076 0.033 — near-zero correlation.
- Notes: Very close to passing. Near-zero correlation with all benchmarks makes it interesting. But 79.6% IS is borderline — could be noise. Best config has high Sharpe but may be overfit.
- Sessions: [2026-04-08 session 166]

## H-372: Return-Range Ratio Trend Factor
- Status: REJECTED (IS 27.8%)
- Idea: Slope of |return|/range over lookback. Trending up = becoming more directional.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 36 param combos.
- Result: IS 27.8% positive (10/36). Best Sharpe 0.562, +15.0% ann, -37.8% DD. Corr H-012 0.094.
- Notes: Directionality trend is not a reliable cross-sectional signal. The concept is sound but noise dominates.
- Sessions: [2026-04-08 session 166]

## H-373: Dispersion-Filtered Momentum Factor
- Status: REJECTED (IS 5.6%)
- Idea: Only trade momentum when cross-sectional return dispersion is high (above median). High dispersion = factor opportunities.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 54 param combos.
- Result: IS 5.6% positive (3/54). Best Sharpe 0.115, -6.6% ann, -53.8% DD. Corr H-012 0.019.
- Notes: Dispersion filtering actually hurts momentum performance. The filter removes too many valid trading days, leaving insufficient signal. XS momentum in crypto doesn't depend on dispersion regimes like in equities.
- Sessions: [2026-04-08 session 166]

## H-374: Relative Volatility Rank Change Factor
- Status: REJECTED (IS 1.9%)
- Idea: Rank assets by how much their volatility rank has changed vs peers. Decreasing relative vol = entering trending phase.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 54 param combos.
- Result: IS 1.9% positive (1/54). Best Sharpe 0.185, -0.2% ann, -38.5% DD. Corr H-012 -0.011.
- Notes: Strongest rejection — 98% negative. Vol rank changes don't predict returns. The concept that decreasing relative vol predicts trending is not supported in crypto.
- Sessions: [2026-04-08 session 166]

## H-375: Volume-Weighted Distance from Mean Factor
- Status: REJECTED (IS 50%)
- Idea: Volume-weighted mean absolute deviation of returns. Low = quiet accumulation phase. High = volatile on heavy volume.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 24 param combos.
- Result: IS 50.0% positive (12/24). Best Sharpe 0.530, +14.8% ann, -67.4% DD. Corr H-012 0.027.
- Notes: Coin-flip results. The concept of quiet accumulation doesn't provide XS edge in crypto. Very high drawdown.
- Sessions: [2026-04-08 session 166]

## H-376: Dollar Volume Acceleration Factor
- Status: REJECTED (IS 66.7%)
- Idea: Second derivative of dollar volume (change in volume growth rate). Accelerating volume precedes price moves.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 54 param combos.
- Result: IS 66.7% positive (36/54). Best Sharpe 1.881, +88.3% ann, -38.6% DD. Corr H-012 0.117.
- Notes: High best Sharpe but inconsistent across params (only 67% positive). Second derivative is too noisy for daily frequency.
- Sessions: [2026-04-08 session 166]

## H-377: Return-Volume Concordance Factor
- Status: REJECTED (IS 62.5%)
- Idea: Rolling correlation between daily returns and volume changes. High correlation = volume confirms price.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 24 param combos.
- Result: IS 62.5% positive (15/24). Best Sharpe 0.831, +27.0% ann, -26.1% DD. Corr H-012 0.269.
- Notes: Moderate result. Volume-return concordance provides some signal but not robust enough. Similar concept to H-167 (return-volume correlation) which was confirmed at different params.
- Sessions: [2026-04-08 session 166]

## H-378: Relative Close Position (Stochastic-like) Factor
- Status: REJECTED (IS 75%)
- Idea: Where today's close sits relative to N-day high-low range: (close - N_low) / (N_high - N_low).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 24 param combos.
- Result: IS 75.0% positive (18/24). Best Sharpe 1.716, +100.6% ann, -30.7% DD. Corr H-012 0.163.
- Notes: Close to passing (75% vs 80% threshold). Stochastic-like positioning captures some momentum but not robust. Similar to H-190 (range position) which was tested before.
- Sessions: [2026-04-08 session 166]

## H-379: Candle Body Ratio Factor
- Status: REJECTED (IS 16.7%)
- Idea: Average |close-open|/(high-low) over lookback. High body ratio = conviction candles.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 24 param combos.
- Result: IS 16.7% positive (4/24). Best Sharpe 0.878, +32.7% ann, -44.7% DD. Corr H-012 -0.020.
- Notes: 83% negative — signal direction is opposite to expected. This is similar to H-343 (momentum decay at 4h) which was CONFIRMED — suggesting body ratio works at 4h but not daily timeframe.
- Sessions: [2026-04-08 session 166]

## H-380: Volume Profile Skewness Factor
- Status: REJECTED (IS 4.2%)
- Idea: Skewness of daily volume distribution over lookback. Captures asymmetry in volume profile.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 24 param combos.
- Result: IS 4.2% positive (1/24). Best Sharpe 0.173, -1.3% ann, -69.4% DD. Corr H-012 0.050.
- Notes: Very strong rejection. Volume distribution shape is not a useful XS signal at daily frequency.
- Sessions: [2026-04-08 session 166]

## H-381: Momentum Decay Rate Factor
- Status: REJECTED (IS 77.8% — borderline)
- Idea: Ratio of short-term momentum to long-term momentum. High ratio = momentum persisting, low = decaying.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 18 param combos.
- Result: IS 77.8% positive (14/18). Best Sharpe 2.081, +133.3% ann, -23.4% DD. Corr H-012 0.147.
- Notes: Another borderline case (78% vs 80%). Very high best Sharpe (2.081) and excellent annual return. The concept is related to momentum quality — assets where momentum persists outperform. Could be revisited with a finer parameter grid.
- Sessions: [2026-04-08 session 166]

## H-382: Return Kurtosis Factor
- Status: LIVE (paper trade since 2026-04-08)
- Idea: Rank assets by rolling excess kurtosis of daily returns. Low kurtosis (thin tails, more predictable) → long. High kurtosis (fat tails, crash-prone) → short.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5 days)
- Logic: Compute rolling 30-day excess kurtosis. Negate signal (low kurtosis = high rank). Long top 4, short bottom 4.
- Data: 14 assets, 732 daily bars. IS: 24 param combos.
- Result: IS **87.5%** positive (21/24). Best LB30_R5_N4 Sharpe **1.124**, +40.1% ann, -27.0% DD. WF **6/6** positive (mean **1.500**, folds: 2.089/0.082/0.201/0.620/5.309/0.698). Split-half H1=0.551, H2=1.850 PASS. Neighbors 100% positive. Corr H-012 **-0.152**.
- Notes: Negative correlation with momentum (-0.152) is excellent for portfolio diversification. Prior kurtosis attempts (H-101, H-170) were rejected — this version uses negated kurtosis at LB30 which captures the right signal. Low kurtosis = asset has thin-tailed predictable returns = trending/stable behavior.
- Sessions: [2026-04-08 session 166]

## H-383: Price-Volume Trend Factor
- Status: LIVE (paper trade since 2026-04-08)
- Idea: Normalized OBV-like signal: sum of volume × sign(return) over lookback, divided by total volume. Captures buying vs selling pressure.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 7 days)
- Logic: Compute PVT = Σ(vol × sign(ret)) / Σ(vol) over 30-day window. Long top 4 (buying pressure), short bottom 4 (selling pressure).
- Data: 14 assets, 732 daily bars. IS: 24 param combos.
- Result: IS **87.5%** positive (21/24). Best LB30_R7_N4 Sharpe **1.347**, +52.7% ann, -31.4% DD. WF **4/6** positive (mean **1.312**, folds: 1.341/1.516/-0.162/3.866/-0.958/2.270). Split-half H1=1.441, H2=2.226 PASS. Neighbors 100% positive. Corr H-012 0.435.
- Notes: Moderate correlation with H-012 (0.435) — both capture price direction but PVT incorporates volume conviction. Prior OBV attempts (H-118) failed at different params. This normalized version works because cross-sectional comparison requires normalization by total volume.
- Sessions: [2026-04-08 session 166]

## H-384: Day-of-Month Sensitivity Factor
- Status: REJECTED (WF 2/6)
- Idea: Rank assets by rolling avg excess return on month-edge days (1-5, 26-31) minus mid-month.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 1737 daily bars. IS: 48 param combos.
- Result: IS 100% high_long (24/24). Best LB20_R7_N3 Sharpe 0.643, +31.1% ann, -70.4% DD. WF **2/6** (FAIL). Folds: -0.251/-1.637/1.282/-3.783/2.772/-1.918.
- Notes: Strong IS (100% high_long) but terrible OOS. Edge-of-month effect is real in-sample but doesn't persist out-of-sample. Calendar anomalies may be arbitraged away quickly.
- Sessions: [2026-04-09 session 167]

## H-385: Volume Herfindahl Index Factor
- Status: CONFIRMED (not deployed — negative WF mean)
- Idea: Rank assets by HHI of hourly volume distribution. High HHI (concentrated volume) → long.
- Instrument: futures (14 perps)
- Timeframe: 1D (hourly data aggregated)
- Data: 14 assets, 1737 daily bars. IS: 60 param combos.
- Result: IS **83.3%** high_long (25/30). Best LB20_R7_N4 Sharpe 0.686, +27.7% ann, -69.7% DD. WF **4/6** mean **-0.362** (2.183/0.251/1.713/-2.971/0.059/-3.404). Split-half H1=0.511, H2=0.832 PASS. Neighbors 87.5%. Corr H-012 **0.023**.
- Notes: Technically passes WF fold count (4/6) but WF mean is NEGATIVE (-0.362) — recent folds heavily negative. Near-zero H-012 corr is excellent. Not deployed due to weak OOS performance. May revisit if signal improves.
- Sessions: [2026-04-09 session 167]

## H-386: 4h Return Autocorrelation Factor
- Status: REJECTED (IS 56.7%)
- Idea: Rank assets by lag-1 autocorrelation of 4h returns. High AC = trending intraday.
- Instrument: futures (14 perps)
- Timeframe: 1D (4h data aggregated)
- Data: 14 assets, 1738 daily bars. IS: 60 param combos.
- Result: IS 56.7% high_long < 80%. Best LB5_R7_N4_low_long Sharpe 0.599. Dominant direction unclear.
- Notes: 4h return autocorrelation doesn't provide robust cross-sectional signal. Crypto intraday returns are close to white noise — AC is too noisy for ranking.
- Sessions: [2026-04-09 session 167]

## H-387: Volume-Weighted Return Dispersion Factor
- Status: REJECTED (WF 2/6)
- Idea: Rank assets by std of volume-weighted hourly returns. Low dispersion (calm) → long.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 1737 daily bars. IS: 60 param combos.
- Result: IS **96.7%** low_long (29/30). Best LB5_R7_N4 Sharpe 0.560, +25.2% ann, -75.0% DD. WF **2/6** (FAIL). Mean -0.747.
- Notes: Strong IS in low_dispersion_long direction but completely fails OOS. The low-vw-dispersion anomaly is similar to low-volatility (H-019) but doesn't persist. Massive drawdowns.
- Sessions: [2026-04-09 session 167]

## H-388: Night-Day Return Differential Factor
- Status: LIVE (paper trade since 2026-04-09)
- Idea: Rank by rolling avg of (Asian session return minus US session return). High differential → long.
- Instrument: futures (14 perps)
- Timeframe: 1D (hourly data aggregated)
- Data: 14 assets, 1737 daily bars. IS: 60 param combos.
- Result: IS **96.7%** high_long (29/30). Best LB30_R5_N3 Sharpe 0.688, +32.2% ann, -81.7% DD. WF **4/6** mean 0.358 (1.561/-2.432/-2.078/1.345/0.113/3.640). Split-half H1=0.916, H2=-0.271 (marginal). Neighbors 94.4%. Corr H-012 **0.040**.
- Notes: Near-zero H-012 correlation is excellent. IS extremely robust. Split-half failed H2 but WF strength justified confirmation. Marginal signal — may need to watch closely. Captures persistent Asian/retail accumulation patterns. Deployed as paper trade #56.
- Sessions: [2026-04-09 session 167]

## H-389: Intraday High Timing Factor
- Status: REJECTED (IS 70%)
- Idea: Rank by avg hour when daily high occurs. Early highs (Asian) vs late highs (US institutional).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 1737 daily bars. IS: 60 param combos.
- Result: IS 70% low_long < 80%. Best LB15_R7_N4 Sharpe 0.855. Interesting signal but not robust enough.
- Notes: The signal that late highs are bad (low_long dominant) suggests US-session selling is more informative than US-session buying. But 70% IS is insufficient.
- Sessions: [2026-04-09 session 167]

## H-390: 4h Body/Shadow Ratio Factor
- Status: REJECTED (IS 76.7%)
- Idea: Rank by avg 4h candle body/shadow ratio. High = conviction bars → long.
- Instrument: futures (14 perps)
- Timeframe: 1D (4h aggregated)
- Data: 14 assets, 1737 daily bars. IS: 60 param combos.
- Result: IS 76.7% high_long < 80%. Best LB20_R7_N4 Sharpe 0.882. Close to threshold but not robust.
- Notes: Similar concept to H-343 (momentum decay at 4h, which was CONFIRMED). Daily aggregation loses the intrabar detail that makes 4h signals work.
- Sessions: [2026-04-09 session 167]

## H-391: Hourly Volume Trend Slope Factor
- Status: REJECTED (IS 46.7%)
- Idea: Rank by OLS slope of hourly volume within each day. Positive slope = building interest.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 1737 daily bars. IS: 60 param combos.
- Result: IS 46.7% high_long. Best LB30_R3_N3 Sharpe 0.644. Coin-flip results.
- Notes: Intraday volume slope is too noisy for cross-sectional ranking. All crypto assets have similar U-shaped volume patterns (high at open/close, low mid-day), making XS differentiation minimal.
- Sessions: [2026-04-09 session 167]

## H-392: OI Momentum Factor
- Status: REJECTED (no OI data in parquet files)
- Idea: Rank by rolling change in open interest. Rising OI = new money, falling OI = closing.
- Instrument: futures (14 perps)
- Notes: Could not test — OI parquet files not available. Similar concept to H-044 which uses OI divergence.
- Sessions: [2026-04-09 session 167]

## H-393: Volume-OI Divergence Momentum
- Status: REJECTED (no OI data)
- Idea: Rolling correlation of volume changes with OI changes.
- Instrument: futures (14 perps)
- Notes: Could not test — OI data unavailable.
- Sessions: [2026-04-09 session 167]

## H-394: Intraday Variance Ratio Factor
- Status: LIVE (paper trade since 2026-04-09)
- Idea: Rank assets by variance ratio (var(2h returns) / (2 * var(1h returns))). VR > 1 = trending intraday → long. VR < 1 = mean-reverting → short.
- Instrument: futures (14 perps)
- Timeframe: 1D (hourly data aggregated)
- Data: 14 assets, 1737 daily bars. IS: 60 param combos.
- Result: IS **86.7%** high_long (26/30). Best LB10_R3_N4 Sharpe **1.014**, +39.5% ann, -54.4% DD. WF **4/6** mean **0.351** (-0.989/1.489/0.962/1.911/0.679/-1.944). Split-half H1=0.932, H2=0.958 **PASS**. Neighbors 83.3%. Corr H-012 **0.027**.
- Notes: Strongest signal of the session. Sharpe > 1, near-zero H-012 corr, split-half robust in both halves. The variance ratio tests the random walk hypothesis — assets deviating from random walk (VR > 1, trending) systematically outperform. This is a well-documented microstructure phenomenon. Deployed as paper trade #55.
- Sessions: [2026-04-09 session 167]

## H-395: Hourly Volume Asymmetry Factor
- Status: REJECTED (IS 33.3%)
- Idea: Rank by ratio of up-hour volume to down-hour volume. High = buying pressure.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 1737 daily bars. IS: 60 param combos.
- Result: IS 33.3% low_long. Best LB30_R7_N3 Sharpe 0.414. Very weak.
- Notes: Hourly volume asymmetry doesn't provide cross-sectional edge. Similar concept to H-219 (up-vol ratio at daily freq, CONFIRMED) but hourly granularity adds noise, not signal.
- Sessions: [2026-04-09 session 167]

## H-396: Price Impact Factor
- Status: REJECTED (IS 60%)
- Idea: Rank by avg |return|/volume per hour. High impact = thin/fragile market.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 1737 daily bars. IS: 60 param combos.
- Result: IS 60% high_long < 80%. Best LB5_R5_N3_low_long Sharpe 0.481. Massive DD (-94%).
- Notes: Price impact at hourly level is too noisy. Direction unclear (high_long dominant but only 60%). Different from Amihud (H-197) which uses daily data — daily aggregation works better for this concept.
- Sessions: [2026-04-09 session 167]

## H-397: 4h Momentum Composite Factor
- Status: REJECTED (IS 56.7%)
- Idea: Composite of 4h return AC + body/shadow + volume persistence. Multi-signal approach.
- Instrument: futures (14 perps)
- Timeframe: 1D (4h aggregated)
- Data: 14 assets, 1737 daily bars. IS: 60 param combos.
- Result: IS 56.7% high_long < 80%. Best LB30_R5_N4 Sharpe 0.916. Close to decent but IS fails.
- Notes: Simple averaging of 3 weak signals doesn't produce a strong composite. Each component individually is borderline — combining them doesn't add enough signal. Would need more sophisticated combination (e.g., PCA, regression weighting).
- Sessions: [2026-04-09 session 167]

## H-398: Funding-OI Interaction Factor
- Status: REJECTED (no OI data for interaction)
- Idea: Rank by funding_rate * OI_change. High = crowded momentum → contrarian short.
- Instrument: futures (14 perps)
- Notes: Could not test — OI data unavailable for interaction calculation.
- Sessions: [2026-04-09 session 167]

## H-399: 4h Return Acceleration Factor
- Status: REJECTED (IS 36.7%)
- Idea: Second derivative of 4h cumulative returns. Positive acceleration = strengthening trend.
- Instrument: futures (14 perps)
- Timeframe: 1D (4h aggregated)
- Data: 14 assets, 1737 daily bars. IS: 60 param combos.
- Result: IS 36.7% high_long. Best Sharpe 0.182. Massive DD (-103%).
- Notes: Return acceleration at 4h is pure noise. Second derivatives amplify noise quadratically. The concept of trend acceleration doesn't translate to a reliable cross-sectional ranking signal in crypto.
- Sessions: [2026-04-09 session 167]

---

## H-400: Volume Profile Asymmetry (4h, lagged)
- Status: REJECTED (WF 2/6)
- Idea: Ratio of volume in up-4h-bars to total volume. High = buying dominance.
- Instrument: futures (14 perps)
- Timeframe: 1D (4h features, LAGGED — no look-ahead)
- Data: 14 assets, 1073 daily bars. IS: 60 combos.
- Result: IS high_vol_asymmetry_long **90.0%** (passes). WF only **2/6** positive, mean 0.377.
- Notes: Strong IS signal but fails WF — buying volume dominance doesn't predict next-day returns reliably. **Critical finding this session: ALL 4h features had massive look-ahead bias when using same-day data (<=). Fixed to use strictly lagged (<) data.**
- Sessions: [2026-04-09 session 168]

## H-401: Intraday Range Expansion (4h, lagged)
- Status: REJECTED (IS 70.0%)
- Idea: Average 4h bar range (normalized by close) over rolling window.
- Instrument: futures (14 perps)
- Timeframe: 1D (4h features, lagged)
- Data: 14 assets, 1073 daily bars. IS: 60 combos.
- Result: IS high_avg_range_long **70.0%**. Below 80% threshold.
- Notes: Range expansion doesn't predict cross-sectional returns at daily frequency.
- Sessions: [2026-04-09 session 168]

## H-402: Body-to-Range Ratio (4h, lagged)
- Status: REJECTED (WF 3/6)
- Idea: Rolling mean of |close-open|/(high-low) at 4h bars.
- Instrument: futures (14 perps)
- Timeframe: 1D (4h features, lagged)
- Data: 14 assets, 1073 daily bars. IS: 60 combos.
- Result: IS low_body_range_long **80.0%** (borderline passes). WF **3/6** positive, mean 0.470.
- Notes: Low body-to-range (wicky bars) → long. Signal exists but unstable across WF folds.
- Sessions: [2026-04-09 session 168]

## H-403: Return Acceleration (4h, lagged)
- Status: REJECTED (IS 53.3%)
- Idea: Acceleration of 4h-aggregate momentum (recent half vs older half of lookback).
- Instrument: futures (14 perps)
- Timeframe: 1D (4h features, lagged)
- Data: 14 assets, 1073 daily bars. IS: 60 combos.
- Result: IS low_agg_mom_long only **53.3%**. Best Sharpe 1.299.
- Notes: Without look-ahead, 4h momentum acceleration is noisy. Confirms acceleration signals are fragile.
- Sessions: [2026-04-09 session 168]

## H-404: Session Flow Imbalance
- Status: LIVE (paper trade since 2026-04-09)
- Idea: Rank by rolling mean of (Asian session return - US session return). LOW imbalance (US outperforms Asia) → long.
- Instrument: futures (14 perps)
- Timeframe: 1D (1h session features, LAGGED)
- Logic: session_imbalance = asia_ret - us_ret per day, rolling 20d mean. Low → long (ascending sort).
- Data: 14 assets, 1073 daily bars. IS: 60 combos. WF: 6 folds.
- Result:
  - **IS**: low_session_imbalance_long **80.0%** (24/30 positive)
  - **Best config**: LB20_R3_N4, Sharpe **0.748**, +36.3% ann, -36.0% DD
  - **WF**: **5/6** positive, mean Sharpe **0.658**
  - **Split-half**: H1=0.296, H2=1.313 (both positive, improving in second half)
  - **Neighbors**: 14/16 positive (**87.5%**)
  - **Correlation**: H-012 **0.008** — near-zero, genuine diversifier
- Notes: Captures geographic flow divergence. When US sessions push price more than Asian sessions, next-day continuation. Look-ahead-free by construction. Paper trade deployed: LONG XRP/BTC/ETH/ADA, SHORT OP/DOT/ATOM/NEAR.
- Sessions: [2026-04-09 session 168]

## H-405: Consecutive Direction Streak (4h, lagged)
- Status: REJECTED (IS 56.7%)
- Idea: Rolling avg of longest same-direction streak in 4h bars.
- Instrument: futures (14 perps)
- Timeframe: 1D (4h features, lagged)
- Data: 14 assets, 1073 daily bars. IS: 60 combos.
- Result: IS high_signed_streak_long only **56.7%**.
- Notes: Without look-ahead, streak length doesn't predict next-day returns.
- Sessions: [2026-04-09 session 168]

## H-406: Volume-Price Trend Coherence (4h, lagged)
- Status: REJECTED (IS 50.0%)
- Idea: Rolling correlation of 4h returns and 4h volume changes.
- Instrument: futures (14 perps)
- Timeframe: 1D (4h features, lagged)
- Data: 14 assets, 1073 daily bars. IS: 60 combos.
- Result: IS high_vp_corr_long only **50.0%**.
- Notes: Volume-return coherence at 4h doesn't predict next-day cross-sectional returns.
- Sessions: [2026-04-09 session 168]

## H-407: Intrabar Momentum Quality (4h, lagged)
- Status: REJECTED (IS 33.3%)
- Idea: Rolling Sharpe ratio of individual 4h bar returns.
- Instrument: futures (14 perps)
- Timeframe: 1D (4h features, lagged)
- Data: 14 assets, 1073 daily bars. IS: 60 combos.
- Result: IS high_intrabar_sharpe_long only **33.3%**. Dead signal with lag.
- Notes: **Key finding**: This had Sharpe 4.83 WITH look-ahead, -0.05 WITHOUT. Confirms 4h microstructure at daily lag is mostly noise. The "signal" was the day's own return reflected in the features.
- Sessions: [2026-04-09 session 168]

## H-408: Weekday Seasonality XS
- Status: REJECTED (IS 56.7%)
- Idea: For each asset, compute avg return on today's weekday over lookback. Rank by expected weekday-specific return.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 60 combos.
- Result: IS low_weekday_long **56.7%**. Best Sharpe 1.247.
- Notes: Weekday seasonality doesn't differentiate cross-sectionally — all crypto assets have similar weekday patterns.
- Sessions: [2026-04-09 session 168]

## H-409: Lead-Lag Score
- Status: REJECTED (IS 36.7%)
- Idea: Rolling correlation of each asset's return(t) with BTC return(t-1). High = lags BTC.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 60 combos.
- Result: IS high_leadlag_long **36.7%**. Best Sharpe 0.467.
- Notes: Lead-lag relationships in crypto are too unstable for cross-sectional ranking. All altcoins lag BTC similarly.
- Sessions: [2026-04-09 session 168]

## H-410: Drawdown Depth XS
- Status: REJECTED (look-ahead inflated, lagged IS 66.7%)
- Idea: Current drawdown from rolling peak. Shallow DD = quality/momentum.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 60 combos (lagged).
- Result: **Original**: IS 100%, Sharpe 5.315, WF 6/6. **LAGGED**: IS 66.7%, Sharpe 1.352. **Massive look-ahead bias** — today's close determines both DD and return.
- Notes: Today's close being high → shallow DD AND positive return → spurious positive. The factor is measuring the return itself. Classic same-day look-ahead.
- Sessions: [2026-04-09 session 168]

## H-411: OBV Slope Factor
- Status: LIVE (paper trade since 2026-04-09)
- Idea: Slope of On-Balance Volume (signed volume cumulative sum) over rolling window. Rising OBV = accumulation.
- Instrument: futures (14 perps)
- Timeframe: 1D (lagged — signal uses data up to yesterday)
- Logic: For each asset: compute OBV = cumsum(vol × sign(ret)) over LB days. Linear regression slope, normalized by mean volume. High slope → long (accumulation).
- Data: 14 assets, 732 daily bars. IS: 60 combos.
- Result:
  - **IS (lagged)**: high_obv_long **93.3%** (28/30 positive)
  - **Best config**: LB15_R7_N3, Sharpe **1.547**, +114.2% ann, -30.6% DD
  - **WF (lagged)**: **6/6** positive, mean Sharpe **0.886**
  - **Split-half**: H1=1.968, H2=1.063 (both positive)
  - **Neighbors**: 12/12 positive (**100%**)
  - **Correlation**: H-012 **0.267**
- Notes: OBV captures net buying/selling pressure through volume flow. The lagged version survives because OBV slope changes slowly — yesterday's accumulation pattern predicts today's continuation. Higher H-012 correlation (0.267) than ideal but still adds value. Paper trade deployed: LONG ARB/LINK/AVAX, SHORT OP/SOL/XRP.
- Sessions: [2026-04-09 session 168]

## H-412: Relative Volatility Z-Score
- Status: CONFIRMED (borderline WF)
- Idea: Z-score of short-term vol change relative to longer history. Rising vol = regime shift.
- Instrument: futures (14 perps)
- Timeframe: 1D (lagged)
- Data: 14 assets, 732 daily bars. IS: 60 combos.
- Result:
  - **IS (lagged)**: high_volz_long **86.7%** (26/30)
  - **Best config**: LB10_R7_N4, Sharpe **2.577**
  - **WF (lagged)**: **4/6** positive, mean Sharpe **0.172** (borderline — folds 3-4 deeply negative)
  - **Split-half**: H1=2.608, H2=2.579 (both positive)
  - **Neighbors**: 10/12 (83.3%)
  - **Correlation**: H-012 **-0.010** (near-zero, excellent diversifier)
- Notes: Excellent IS and split-half but WF is regime-dependent with high variance. NOT deployed due to borderline WF. The negative H-012 corr is attractive but reliability is questionable.
- Sessions: [2026-04-09 session 168]

## H-413: Price-MA Distance XS
- Status: REJECTED (look-ahead inflated, lagged IS 66.7%)
- Idea: Distance from rolling MA. Far above = extended.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 60 combos (lagged).
- Result: **Original**: IS 100%, Sharpe 5.649, WF 6/6. **LAGGED**: IS 66.7%, Sharpe 0.868. Same look-ahead pattern as H-410.
- Notes: Price-MA distance uses today's close in both signal and return. Without look-ahead, the signal largely vanishes. Similar to pure momentum but shorter-term.
- Sessions: [2026-04-09 session 168]

## H-414: Volume Trend Factor
- Status: LIVE (paper trade since 2026-04-09)
- Idea: Linear regression slope of log-volume over rolling window. Rising volume = increasing interest/accumulation.
- Instrument: futures (14 perps)
- Timeframe: 1D (lagged — signal uses data up to yesterday)
- Logic: For each asset: linregress(x, log1p(volume)) over LB days. High slope → long.
- Data: 14 assets, 732 daily bars. IS: 60 combos.
- Result:
  - **IS (lagged)**: high_voltrd_long **96.7%** (29/30 positive) — strongest IS of the batch
  - **Best config**: LB15_R3_N4, Sharpe **2.520**, +189.9% ann, -15.4% DD
  - **WF (lagged)**: **5/6** positive, mean Sharpe **2.437** — excellent
  - **Split-half**: H1=2.369, H2=2.762 (both positive, improving in H2)
  - **Neighbors**: 12/12 positive (**100%**)
  - **Correlation**: H-012 **0.028** — near-zero, excellent diversifier
- Notes: **Standout of this session**. Volume trend is purely volume-based (no price in signal), making it immune to price look-ahead. Volume trends are persistent — an asset with accelerating volume yesterday continues to attract attention today. Near-zero H-012 corr makes it an excellent portfolio diversifier. Paper trade deployed: LONG ARB/LINK/AVAX/ADA, SHORT DOGE/OP/DOT/SOL.
- Sessions: [2026-04-09 session 168]

## H-415: Dispersion Beta Factor
- Status: REJECTED (WF 2/6)
- Idea: Beta of each asset's daily return to cross-sectional return dispersion.
- Instrument: futures (14 perps)
- Timeframe: 1D (lagged)
- Data: 14 assets, 732 daily bars. IS: 60 combos.
- Result: IS high_dispbeta_long **90.0%** (lagged). WF only **2/6** positive, mean 0.348.
- Notes: IS passes but WF fails — dispersion sensitivity is regime-dependent.
- Sessions: [2026-04-09 session 168]

## H-416: Composite Score (Efficiency × Volume Surprise)
- Status: REJECTED (IS 41.7%)
- Idea: Combine two uncorrelated confirmed signals (price efficiency + volume surprise) via z-scored product.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **41.7%** — composite does not maintain individual signal quality in cross-section.
- Notes: Combining signals by multiplication destroys the signal — factor interactions aren't additive.
- Sessions: [2026-04-09 session 169]

## H-417: Volatility-Adaptive Momentum
- Status: REJECTED (IS 50.0%)
- Idea: Use BTC realized vol to adaptively shorten momentum lookback in high-vol regimes.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **50.0%** — adaptive lookback doesn't improve over fixed.
- Notes: Vol-adaptive approach is theoretically appealing but doesn't capture XS signal.
- Sessions: [2026-04-09 session 169]

## H-418: BTC Lead-Lag Timing
- Status: REJECTED (IS 30.6%)
- Idea: Rolling correlation of alt_return(t) with BTC_return(t-1). High = lags BTC.
- Instrument: futures (13 non-BTC perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 36 combos.
- Result: IS **30.6%** — lead-lag relationship is not persistent cross-sectionally.
- Sessions: [2026-04-09 session 169]

## H-419: Funding Rate Acceleration
- Status: REJECTED (no data)
- Idea: Rate of change of funding rate as contrarian signal.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: Funding data files not in expected format.
- Result: NO RESULTS — data loading failed.
- Sessions: [2026-04-09 session 169]

## H-420: Vol-of-Vol Factor
- Status: REJECTED (IS 45.8%)
- Idea: Realized vol of realized vol. Low vol-of-vol = stable regime.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **45.8%** — vol-of-vol doesn't predict XS returns.
- Sessions: [2026-04-09 session 169]

## H-421: Return Autocorrelation Factor
- Status: REJECTED (IS 36.1%)
- Idea: Rolling daily return autocorrelation. High = trending, low = mean-reverting.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 36 combos.
- Result: IS **36.1%** — autocorrelation not a reliable XS predictor.
- Sessions: [2026-04-09 session 169]

## H-422: Consecutive Direction Streak Factor
- Status: REJECTED (IS 50.0%)
- Idea: Count consecutive up/down days as momentum/reversal signal.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **50.0%** — streak patterns don't predict next-day XS returns.
- Sessions: [2026-04-09 session 169]

## H-423: Volume-Weighted Return Factor
- Status: REJECTED (IS 50.0%)
- Idea: Return weighted by relative volume — captures institutional conviction.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **50.0%** — volume-weighting doesn't add alpha over raw returns.
- Sessions: [2026-04-09 session 169]

## H-424: Rank Momentum Factor
- Status: REJECTED (IS 50.0%)
- Idea: Change in cross-sectional momentum rank over time.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **50.0%** — rank changes are noisy and don't persist.
- Sessions: [2026-04-09 session 169]

## H-425: Closing Location Value (CLV) Factor
- Status: REJECTED (IS 50.0%)
- Idea: Where the close falls in the day's range (buying/selling pressure).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **50.0%** — CLV has no persistent XS predictive power.
- Sessions: [2026-04-09 session 169]

## H-426: True Range Ratio Factor
- Status: REJECTED (IS 50.0%)
- Idea: True range / close as volatility proxy. Long calm, short volatile.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **50.0%** — true range variant of low-vol doesn't add over simpler measures.
- Sessions: [2026-04-09 session 169]

## H-427: Co-Movement Score Factor
- Status: REJECTED (IS 50.0%)
- Idea: Average pairwise correlation with all other assets.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **50.0%** — co-movement doesn't predict returns cross-sectionally.
- Sessions: [2026-04-09 session 169]

## H-428: Dispersion Beta Factor (v2)
- Status: REJECTED (IS 47.9%)
- Idea: Beta of asset return to cross-sectional return dispersion.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **47.9%** — dispersion sensitivity not a useful XS signal.
- Sessions: [2026-04-09 session 169]

## H-429: Price Position (Donchian) Factor
- Status: REJECTED (IS 50.0%)
- Idea: Current price position in N-day high-low range.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **50.0%** — Donchian position has no persistent XS alpha.
- Sessions: [2026-04-09 session 169]

## H-430: Volume-Price Correlation Factor
- Status: REJECTED (IS 45.8%)
- Idea: Rolling correlation between volume and abs(return).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **45.8%** — vol-price alignment doesn't predict XS returns.
- Sessions: [2026-04-09 session 169]

## H-431: Momentum Quality Factor
- Status: REJECTED (IS 50.0%)
- Idea: Momentum adjusted for max drawdown during lookback.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS **50.0%** — quality-adjusting momentum doesn't improve the signal.
- Sessions: [2026-04-09 session 169]

## H-432: Volume HHI (Hourly Concentration) Factor
- Status: BORDERLINE (SH FAIL)
- Idea: Herfindahl index of hourly volume shares within each day. Lagged.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars. IS: 48 combos (high_long 87.5%).
- Result: IS high_long **87.5%** (21/24). WF **4/6** mean 0.790. SH FAIL (H1=1.517, H2=-0.930). Corr H-012 **-0.101**.
- Notes: Passes IS and WF but split-half failure suggests instability. Not deployed.
- Sessions: [2026-04-09 session 169]

## H-433: Asia-US Session Return Spread Factor
- Status: REJECTED (IS 70.8% best direction)
- Idea: Difference between Asian session return and US session return.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars. IS: 48 combos.
- Result: IS best direction only **70.8%** — insufficient robustness.
- Sessions: [2026-04-09 session 169]

## H-434: Gap Fill Rate Factor
- Status: REJECTED (data artifact)
- Idea: What fraction of overnight gaps get filled during the session.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: **INVALIDATED** — all values are 1.0 (crypto has no real gaps; 24/7 trading means all tiny gaps are immediately filled). No cross-sectional variation.
- Notes: The 100% IS and 6/6 WF were artifacts of a constant factor producing random but identical portfolios. A useful cautionary tale about checking factor variation.
- Sessions: [2026-04-09 session 169]

## H-435: Hourly Return Kurtosis Factor
- Status: CONFIRMED (deployed)
- Idea: Rolling average of hourly return kurtosis. High kurtosis = fat tails = jump premium.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars. IS: 24 combos (high_long direction).
- Result:
  - **IS**: high_long **95.8%** (23/24 positive)
  - **Best config**: LB20_R3_N4, Sharpe **1.520**, +70.1% ann, -26.6% DD
  - **WF**: **4/6** positive, mean Sharpe **1.367**
  - **Split-half**: H1=1.824, H2=1.038 — PASS (both positive)
  - **Neighbors**: 8/8 positive (100%)
  - **Correlation**: H-012 **0.106** — low, good diversifier
- Notes: High-kurtosis assets have more frequent extreme moves, which in crypto tends to be rewarded. Opposite direction (low_long) has 0/24 positive, confirming this is a genuine directional signal. Paper trade deployed: LONG ETH/AVAX/LINK/SOL, SHORT OP/NEAR/DOT/ATOM.
- Sessions: [2026-04-09 session 169]

## H-436: Volume-Weighted Momentum (Hourly) Factor
- Status: BORDERLINE (SH FAIL, high corr)
- Idea: Momentum weighted by relative volume per hourly bar.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars. IS: 24 combos (high_long 91.7%).
- Result: IS high_long **91.7%**. WF **4/6** mean 0.299. SH FAIL (H1=1.237, H2=-2.026). Corr H-012 **0.466** (too high).
- Notes: Not deployed — split-half failure and high momentum correlation make this redundant.
- Sessions: [2026-04-09 session 169]

## H-437: HL Spread Proxy (Bid-Ask Proxy) Factor
- Status: CONFIRMED (deployed)
- Idea: Rolling average hourly (high-low)/close as bid-ask spread proxy. Low spread = liquid = quality.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars. IS: 24 combos (low_long direction).
- Result:
  - **IS**: low_long **95.8%** (23/24 positive)
  - **Best config**: LB30_R5_N4, Sharpe **0.870**, +49.5% ann, -55.4% DD
  - **WF**: **5/6** positive, mean Sharpe **1.049**
  - **Split-half**: H1=0.068, H2=1.461 — PASS (both positive)
  - **Neighbors**: 6/6 positive (100%)
  - **Correlation**: H-012 **-0.183** — NEGATIVE, excellent diversifier
- Notes: Tight hourly spreads indicate liquid, efficiently-priced assets. These tend to outperform in crypto because liquidity attracts institutional flow. The negative H-012 correlation makes this particularly valuable for portfolio diversification. Paper trade deployed: LONG BTC/ATOM/XRP/LINK, SHORT ARB/SUI/OP/NEAR.
- Sessions: [2026-04-09 session 169]

## H-438: Intraday Momentum Share Factor
- Status: REJECTED (IS 54.2% best direction)
- Idea: Fraction of daily return from largest single hourly move.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS best direction **54.2%** — insufficient robustness.
- Sessions: [2026-04-09 session 169]

## H-439: Intraday Volume Trend Factor
- Status: REJECTED (IS 50.0% best direction)
- Idea: Slope of hourly volume within each day (accumulation vs distribution).
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS best direction **50.0%** — no predictive signal.
- Sessions: [2026-04-09 session 169]

## H-440: Hourly Return Autocorrelation Factor
- Status: REJECTED (IS 58.3% best direction)
- Idea: 1st-order autocorrelation of hourly returns within each day. Positive = trending, negative = reverting.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS best direction (low_long) **58.3%** — insufficient robustness.
- Sessions: [2026-04-09 session 170]

## H-441: Volume Clock Clustering Factor
- Status: REJECTED (IS 50.0% best direction)
- Idea: Volume-weighted center-of-mass hour. When does smart money trade?
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS best direction (low_long) **50.0%** — no signal.
- Sessions: [2026-04-09 session 170]

## H-442: Hourly Return Dispersion Factor
- Status: BORDERLINE (IS 95.8%, WF 5/6, SH FAIL)
- Idea: Std of hourly returns. Low dispersion = calm intraday = resilient.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 95.8% positive (low_long direction), best LB30_R5_N3, Sharpe 0.883
  - **WF**: **5/6** positive, mean Sharpe **1.069**
  - **Split-half**: H1=-0.073, H2=1.425 — **FAIL** (H1 negative)
  - **Correlation**: H-012 **-0.094** — near-zero
- Notes: Good WF but first-half performance absent. Not deployed.
- Sessions: [2026-04-09 session 170]

## H-443: Reversal Ratio Factor
- Status: REJECTED (IS 45.8% best direction)
- Idea: Fraction of hourly sign flips (choppy vs smooth price action).
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS best direction (low_long) **45.8%** — no signal.
- Sessions: [2026-04-09 session 170]

## H-444: Up-Volume Concentration Factor
- Status: BORDERLINE (IS 100%, WF 5/6, SH FAIL, corr 0.598)
- Idea: Fraction of volume during positive-return hours. High = aligned buying pressure.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 100% positive (high_long direction), best LB30_R5_N4, Sharpe 1.530
  - **WF**: **5/6** positive, mean Sharpe **1.444**
  - **Split-half**: H1=1.957, H2=-0.555 — **FAIL**
  - **Correlation**: H-012 **0.598** — too high, redundant with momentum
- Notes: Strong IS/WF but SH fails and very correlated with H-012. Not deployed.
- Sessions: [2026-04-09 session 170]

## H-445: Max Hourly Drawdown Factor
- Status: CONFIRMED → LIVE (paper trade started 2026-04-09)
- Idea: Max intraday drawdown from hourly bars. Low DD → long (resilient).
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged), rebalance every 5 days
- Logic: Rolling 30-day avg max hourly DD. LOW → long (resilient), HIGH → short (fragile). Top/bottom 3.
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 95.8% positive (low_long direction), best LB30_R5_N3, Sharpe 1.343, +104.8% ann, -60.4% DD
  - **WF**: **5/6** positive, mean Sharpe **1.500**
  - **Split-half**: H1=0.900, H2=1.626 — **PASS**
  - **Neighbors**: 6/6 positive (100%)
  - **Correlation**: H-012 **-0.200** — NEGATIVE, excellent diversifier
- Notes: Negative correlation with H-012 is very valuable — captures "flight to quality" within crypto. Resilient assets outperform. Paper trade deployed: LONG BTC/XRP/ATOM, SHORT AVAX/OP/SUI.
- Sessions: [2026-04-09 session 170]

## H-446: Hourly VWAP Deviation Factor
- Status: REJECTED (IS 66.7% best direction)
- Idea: Closing price deviation from hourly VWAP.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS best direction (high_long) **66.7%** — insufficient robustness.
- Sessions: [2026-04-09 session 170]

## H-447: Hourly Volume Autocorrelation Factor
- Status: CONFIRMED → LIVE (paper trade started 2026-04-09)
- Idea: 1st-order autocorrelation of hourly volume. High = predictable = institutional.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged), rebalance every 3 days
- Logic: Rolling 15-day avg vol autocorrelation. HIGH → long (institutional), LOW → short (erratic). Top/bottom 3.
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 87.5% positive (high_long direction), best LB15_R3_N3, Sharpe 0.741, +38.9% ann, -48.8% DD
  - **WF**: **4/6** positive, mean Sharpe **0.859**
  - **Split-half**: H1=0.754, H2=1.391 — **PASS**
  - **Neighbors**: 12/12 positive (100%)
  - **Correlation**: H-012 **0.039** — near-zero, excellent diversifier
- Notes: Predictable volume patterns indicate institutional presence. These assets tend to have better price discovery. Paper trade deployed: LONG BTC/NEAR/XRP, SHORT DOT/ADA/SUI.
- Sessions: [2026-04-09 session 170]

## H-448: Hourly Return Skewness Factor
- Status: REJECTED (IS 29.2% best direction)
- Idea: Skewness of hourly returns within each day.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS best direction (high_long) **29.2%** — no signal.
- Sessions: [2026-04-09 session 170]

## H-449: Volume Acceleration Factor
- Status: BORDERLINE (IS 91.7%, WF 5/6, SH FAIL)
- Idea: 2nd derivative of hourly volume. Increasing acceleration = volume surge building.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 91.7% positive (high_long), best LB15_R3_N4, Sharpe 1.288
  - **WF**: **5/6** positive, mean Sharpe **1.009**
  - **Split-half**: H1=2.491, H2=-0.608 — **FAIL**
  - **Correlation**: H-012 **-0.011** — near-zero
- Notes: Strong first-half but poor second-half performance. Not deployed.
- Sessions: [2026-04-09 session 170]

## H-450: Price Range Expansion Rate Factor
- Status: REJECTED (IS 45.8% best direction)
- Idea: Ratio of hourly range to daily range.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS best direction (low_long) **45.8%** — no signal.
- Sessions: [2026-04-09 session 170]

## H-451: Close-to-High Ratio Factor
- Status: CONFIRMED → LIVE (paper trade started 2026-04-09)
- Idea: Avg (close-low)/(high-low) across hourly bars. High = consistent buying pressure.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged), rebalance every 5 days
- Logic: Rolling 30-day avg close-to-high ratio. HIGH → long (buying pressure). Top/bottom 3.
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 100% positive (high_long direction), best LB30_R5_N3, Sharpe 1.325, +87.4% ann, -50.0% DD
  - **WF**: **5/6** positive, mean Sharpe **1.366**
  - **Split-half**: H1=0.867, H2=0.510 — **PASS**
  - **Neighbors**: 6/6 positive (100%)
  - **Correlation**: H-012 **0.258** — moderate but acceptable
- Notes: Assets that consistently close near their hourly highs have sustained buying pressure. Paper trade deployed: LONG NEAR/ETH/OP, SHORT ATOM/ADA/XRP.
- Sessions: [2026-04-09 session 170]

## H-452: Volume Entropy Factor
- Status: BORDERLINE (IS 95.8%, WF 4/6, SH FAIL)
- Idea: Entropy of hourly volume distribution. Low entropy = concentrated = institutional.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 95.8% positive (low_long), best LB10_R5_N4, Sharpe 0.908
  - **WF**: **4/6** positive, mean Sharpe **0.620**
  - **Split-half**: H1=1.699, H2=-0.834 — **FAIL**
  - **Correlation**: H-012 **0.090** — near-zero
- Notes: Signal degrades in second half of data. Not deployed.
- Sessions: [2026-04-09 session 170]

## H-453: Intraday Trend Strength Factor
- Status: REJECTED (IS 45.8% best direction)
- Idea: R-squared of hourly price regression (smooth trend vs choppy).
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS best direction (high_long) **45.8%** — no signal.
- Sessions: [2026-04-09 session 170]

## H-454: Momentum Decay Rate Factor
- Status: REJECTED (IS 70.8% best direction)
- Idea: Difference between first-half and second-half hourly momentum.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS best direction (low_long) **70.8%** — below 80% threshold.
- Sessions: [2026-04-09 session 170]

## H-455: Volume-Price Correlation Factor
- Status: BORDERLINE (IS 100%, WF 6/6, SH near-FAIL)
- Idea: Correlation between hourly volume and absolute returns. High = volume confirms moves.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 100% positive (high_long), best LB20_R7_N3, Sharpe **2.288**, +171.9% ann
  - **WF**: **6/6** positive, mean Sharpe **2.171** — outstanding
  - **Split-half**: H1=1.945, H2=-0.071 — **FAIL** (H2 barely negative)
  - **Neighbors**: 8/8 positive (100%)
  - **Correlation**: H-012 **0.207** — moderate
- Notes: Exceptional WF performance but narrowly fails SH. Very close to confirmation — worth monitoring. Not deployed yet.
- Sessions: [2026-04-09 session 170]

## H-456: Volume-Weighted Return Factor
- Status: BORDERLINE (IS 100%, WF 4/6, SH FAIL)
- Idea: Average hourly return weighted by volume. High VW return = volume confirms direction.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 100% positive (high_long), best LB20_R3_N4, Sharpe 1.339, +66.8% ann
  - **WF**: 4/6 positive, mean 1.196
  - **Split-half**: H1=1.283, H2=-1.839 — **FAIL**
  - **Correlation**: H-012 **0.625** — very high
- Notes: High momentum correlation makes this mostly redundant. SH failure in H2 suggests regime-dependent.
- Sessions: [2026-04-09 session 171]

## H-457: Intraday Autocorrelation Factor
- Status: REJECTED (IS 45.8%)
- Idea: Lag-1 autocorrelation of hourly returns. Mean reversion vs trending intraday.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS 45.8% overall, best direction 58.3% — below 80% threshold.
- Sessions: [2026-04-09 session 171]

## H-458: Up Volume Ratio Factor
- Status: BORDERLINE (IS 100%, WF 5/6, SH FAIL)
- Idea: Volume on green hours / total volume. High = buying pressure dominant.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 100% positive (high_long), best LB30_R5_N4, Sharpe 1.530, +83.9% ann
  - **WF**: **5/6** positive, mean 1.444
  - **Split-half**: H1=1.957, H2=-0.555 — **FAIL**
  - **Correlation**: H-012 **0.598** — very high
- Notes: Strong WF but fails SH. Very high momentum correlation — effectively a momentum proxy.
- Sessions: [2026-04-09 session 171]

## H-459: Hourly Amihud Illiquidity Factor
- Status: BORDERLINE (IS 100%, WF 4/6, SH FAIL)
- Idea: Mean |return|/volume across hourly bars. Long liquid, short illiquid.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 100% positive (low_long), best LB20_R7_N3, Sharpe 1.175, +65.2% ann
  - **WF**: 4/6 positive, mean 0.836
  - **Split-half**: H1=2.185, H2=-1.156 — **FAIL**
  - **Correlation**: H-012 **-0.165** — good (negative, diversifying)
- Notes: Good negative correlation but fails SH decisively. Interesting diversifier concept but unstable across halves.
- Sessions: [2026-04-09 session 171]

## H-460: Intraday Close Position Factor
- Status: REJECTED (WF 3/6)
- Idea: (close-open)/(high-low) for the day from hourly bars. High = closes near daily high.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS 95.8% (high_long), best LB15_R7_N3, Sharpe 1.317. WF 3/6 — rejected.
- Sessions: [2026-04-09 session 171]

## H-461: Volume HHI Factor
- Status: BORDERLINE (IS 88%, WF 4/6, SH FAIL)
- Idea: Herfindahl index of hourly volume distribution. High = concentrated in few hours.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 87.5% positive (high_long), best LB10_R5_N4, Sharpe 0.669, +28.5% ann
  - **WF**: 4/6 positive, mean 0.790
  - **Split-half**: H1=1.517, H2=-0.930 — **FAIL**
  - **Correlation**: H-012 **-0.101** — low (good)
- Notes: Low Sharpe and SH fail. Low correlation is appealing but signal too weak.
- Sessions: [2026-04-09 session 171]

## H-462: Breakout Persistence Factor
- Status: REJECTED (IS 31.2%)
- Idea: Max consecutive same-sign hourly returns / total. High = strong intraday trend.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS 31.2% overall, best direction 41.7% — below 80% threshold.
- Sessions: [2026-04-09 session 171]

## H-463: Return Asymmetry Factor
- Status: REJECTED (IS 41.7%)
- Idea: Ratio of max positive hourly return to abs(max negative). >1 = larger upside moves.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS 41.7% overall, best direction 54.2% — below 80% threshold.
- Sessions: [2026-04-09 session 171]

## H-464: Volume Momentum Factor (hourly)
- Status: REJECTED (IS 35.4%)
- Idea: Slope of hourly volume over the day (linear regression, normalized). Increasing = accumulation.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS 35.4% overall, best direction 50.0% — below 80% threshold.
- Sessions: [2026-04-09 session 171]

## H-465: Price-Volume Divergence Factor
- Status: REJECTED (IS 41.7%)
- Idea: Mean of sign(return)*sign(vol_change) across hours. Negative = divergence.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS 41.7% overall, best direction (low_long) 79.2% — very close but below 80%.
- Sessions: [2026-04-09 session 171]

## H-466: Intraday Volatility Ratio Factor
- Status: REJECTED (WF 3/6)
- Idea: std(hourly returns first half) / std(second half). Front vs back-loaded volatility.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS 95.8% (low_long), best LB10_R7_N4, Sharpe 1.117. WF 3/6 — rejected.
- Sessions: [2026-04-09 session 171]

## H-467: Return Dispersion Factor (hourly)
- Status: BORDERLINE (IS 96%, WF 5/6, SH FAIL)
- Idea: Std dev of hourly returns within day. Long low-dispersion, short high-dispersion.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 95.8% positive (low_long), best LB30_R5_N3, Sharpe 0.883, +58.0% ann
  - **WF**: **5/6** positive, mean 1.069
  - **Split-half**: H1=-0.073, H2=1.425 — **FAIL** (H1 barely negative)
  - **Correlation**: H-012 **-0.094** — low (good diversifier)
- Notes: Close to pass — H1 barely negative. Good negative momentum correlation. Similar concept to low-vol anomaly.
- Sessions: [2026-04-09 session 171]

## H-468: VWAP Position Factor
- Status: REJECTED (IS 29.2%)
- Idea: Position of VWAP relative to daily high/low from hourly bars.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS 29.2% overall, best direction 50.0% — below 80% threshold.
- Sessions: [2026-04-09 session 171]

## H-469: Reversal Count Factor
- Status: REJECTED (IS 41.7%)
- Idea: Number of sign changes in hourly returns / total hours. High = choppy.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS 41.7% overall, best direction 58.3% — below 80% threshold.
- Sessions: [2026-04-09 session 171]

## H-470: First-Hour Return Factor
- Status: LIVE (paper trade since 2026-04-09)
- Idea: Rank assets by rolling avg first-hour return. Long strongest openers, short weakest.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Logic: Compute first-hour return (close/open - 1) for each asset's first hourly bar. Rolling 20-day average. Long top 4, short bottom 4. 7-day rebalance. Lagged (t-1).
- Data: 14 assets, 732 daily bars.
- Result:
  - **IS**: 100% positive (high_long, 24/24), best LB20_R7_N4, Sharpe **1.564**, +88.0% ann, -24.5% DD
  - **WF**: **4/6** positive, mean 0.365
  - **Split-half**: H1=1.665, H2=0.411 — **PASS**
  - **Neighbors**: 8/8 positive (100%)
  - **Correlation**: H-012 **0.267** — moderate
- Notes: First-hour return sets the tone — assets with consistently strong opening hours tend to continue. Moderate momentum correlation but SH passes in both halves.
- Sessions: [2026-04-09 session 171]

## H-471: Last-Hour Return Factor
- Status: REJECTED (IS 35.4%)
- Idea: Rank assets by rolling avg last-hour return. Long strongest closers.
- Instrument: futures (14 perps)
- Timeframe: 1D (signal from 1h bars, lagged)
- Data: 14 assets, 732 daily bars.
- Result: IS 35.4% overall, best direction 54.2% — below 80% threshold.
- Sessions: [2026-04-09 session 171]

## H-472: BTC Lead-Lag Factor
- Status: REJECTED (IS 33%)
- Idea: Rolling correlation of BTC return(t-1) with asset return(t). Cross-asset lead-lag.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars.
- Result: IS 33% (4/12 positive). No reliable cross-asset lead-lag edge.
- Sessions: [2026-04-09 session 172]

## H-473: Correlation Clustering Factor
- Status: REJECTED (IS 50%)
- Idea: Average pairwise correlation with all other assets. Low corr = independent.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 50% (6/12 positive). Unstable across params.
- Sessions: [2026-04-09 session 172]

## H-474: Beta Change Factor
- Status: REJECTED (IS 42%)
- Idea: Rolling change in BTC beta (beta_10d - beta_30d). Falling beta = safer.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 42% (5/12 positive). Beta dynamics not predictive.
- Sessions: [2026-04-09 session 172]

## H-475: Relative Funding Spread
- Status: REJECTED (IS 0%)
- Idea: Asset funding rate minus cross-sectional median. Contrarian.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 0% (0/6 positive). Zero signal.
- Sessions: [2026-04-09 session 172]

## H-476: Momentum Spillover Factor
- Status: REJECTED (IS 38%)
- Idea: Weighted sum of lagged returns from correlated peers.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 38% (3/8 positive). Peer spillover not predictive.
- Sessions: [2026-04-09 session 172]

## H-477: Idiosyncratic Momentum
- Status: REJECTED (IS 50%)
- Idea: Residual return after removing BTC component. Pure alpha signal.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 50% (6/12 positive). Market-neutral residuals not predictive.
- Sessions: [2026-04-09 session 172]

## H-478: Dispersion-Conditional Momentum
- Status: REJECTED (IS 0%)
- Idea: XS momentum only when cross-sectional return dispersion is high.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 0% (0/18 positive). Conditioning destroys signal.
- Sessions: [2026-04-09 session 172]

## H-479: Correlation Regime Switch
- Status: REJECTED (IS 0%)
- Idea: Momentum only when overall crypto correlation is falling.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 0% (0/18 positive). Correlation regime filtering fails.
- Sessions: [2026-04-09 session 172]

## H-480: Momentum × Volume Interaction
- Status: REJECTED (IS 0%)
- Idea: Momentum weighted by relative volume.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 0% (0/6 positive). Volume weighting destroys momentum.
- Sessions: [2026-04-09 session 172]

## H-481: Momentum × Efficiency Interaction
- Status: REJECTED (IS 0%)
- Idea: Momentum weighted by price efficiency.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 0% (0/6 positive).
- Sessions: [2026-04-09 session 172]

## H-482: Reversal × Volatility Interaction
- Status: REJECTED (IS 25%)
- Idea: Short-term reversal weighted by realized vol.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 25% (1/4 positive).
- Sessions: [2026-04-09 session 172]

## H-483: Size × Momentum Interaction
- Status: REJECTED (IS 0%)
- Idea: Dollar volume × 60d momentum.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 0% (0/6 positive).
- Sessions: [2026-04-09 session 172]

## H-484: Weekly Momentum
- Status: REJECTED (IS 50%)
- Idea: 5-day return as XS factor.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 50% (6/12 positive). Unstable.
- Sessions: [2026-04-09 session 172]

## H-485: Monthly Reversal
- Status: CONFIRMED (not deployed — H-012 corr 0.591)
- Idea: Short recent 20d winners, long recent 20d losers. Short-horizon reversal.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 732 daily bars.
- Result: IS **100%** (6/6), best Sharpe 1.082 (+57.1%, -44.9% DD). WF **4/6** mean **1.042**. SH **PASS** (1.324/0.600). H-012 corr **0.591**.
- Notes: Confirmed but too correlated with H-012 to add portfolio value. Not deploying.
- Sessions: [2026-04-09 session 172]

## H-486: BTC-Regime Conditional Factor
- Status: REJECTED (H-012 corr 0.899 — momentum proxy)
- Idea: Momentum when trending (ADX>25), reversal when ranging.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS **94%**, WF **6/6** mean **1.279**. But H-012 corr **0.899** — just momentum.
- Sessions: [2026-04-09 session 172]

## H-487: Dual Momentum
- Status: REJECTED (WF 2/6, SH fail)
- Idea: Long when TS>0 AND XS top; short when TS<0 AND XS bottom.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 100%, WF 2/6, SH FAIL (-1.621/-0.605).
- Sessions: [2026-04-09 session 172]

## H-488: Factor Composite Score
- Status: REJECTED (IS 0%)
- Idea: Equal-weight z-score of top 5 confirmed factors.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 0% (0/6 positive). Averaging z-scores cancels signals.
- Notes: Factors work independently but not as linear combination — conflicting directions.
- Sessions: [2026-04-09 session 172]

## H-489: Momentum-Volume Agreement
- Status: REJECTED (IS 33%)
- Idea: Only trade momentum when volume trend agrees.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 33% (2/6 positive).
- Sessions: [2026-04-09 session 172]

## H-490: Day-of-Month Seasonality
- Status: REJECTED (no significant days)
- Idea: BTC returns vary by day of month.
- Instrument: BTC/USDT
- Timeframe: 1D
- Result: No statistically significant days (all p > 0.05). 2yr insufficient for calendar effects.
- Sessions: [2026-04-09 session 172]

## H-491: Monthly Seasonality
- Status: REJECTED (no significant months)
- Idea: BTC returns vary by calendar month.
- Instrument: BTC/USDT
- Timeframe: 1D
- Result: No significant months. Feb weakest, May strongest, all p > 0.1. Need longer history.
- Sessions: [2026-04-09 session 172]

## H-492: Distance from 60-Day High
- Status: REJECTED (IS 50%)
- Idea: Assets near 60d high tend to break out; near lows tend to bounce.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 50% (6/12 positive). Unstable.
- Sessions: [2026-04-09 session 172]

## H-493: Consecutive Direction
- Status: REJECTED (IS 0%)
- Idea: Number of consecutive up/down days as overbought/oversold signal.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 0% (0/8 positive). No predictive power.
- Sessions: [2026-04-09 session 172]

## H-494: Range Expansion Rate
- Status: REJECTED (IS 50%)
- Idea: Today's range vs 20d avg range. Expanding range = breakout.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 50% (6/12 positive). Unstable.
- Sessions: [2026-04-09 session 172]

## H-495: Return Autocorrelation
- Status: REJECTED (IS 33%)
- Idea: 20-day return autocorrelation as trending/reverting classifier.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 33% (4/12 positive). Not stable enough.
- Sessions: [2026-04-09 session 172]

## H-496: ML Ensemble (Focused Equal-Weight 10-Factor Composite)
- Status: CONFIRMED (deployed to paper trade)
- Idea: Combine 10 confirmed XS factor z-scores via equal-weight averaging into single composite signal. Long top 4, short bottom 4.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 5d)
- Logic: Compute 10 factor z-scores (momentum, low_vol, size, premium, vol_term, dd_momentum, efficiency, turnover, vol_surprise, vw_pressure). Average z-scores cross-sectionally. Rank composite. Long top 4, short bottom 4.
- Data: 14 assets, 1073 daily bars (~2.9 years). 952-day evaluation period.
- Result:
  - **Full sample**: Sharpe **2.149**, +98.7% annual, -23.8% DD, 56.3% WR
  - **Walk-forward (6 folds x 90d)**: **5/6 positive**, mean Sharpe **2.189**, min -0.049
  - **Split-half**: H1=2.555, H2=1.655 — **PASS**
  - **Param robustness**: **12/12 positive** (n_long=[3,4,5,6] x rf=[3,5,7]), mean 1.35, min 0.86
  - **Correlation with H-012**: 0.547 (moderate — shares momentum component)
  - **Factor importance (leave-one-out delta)**: vol_term(-0.711), premium(-0.580), efficiency(-0.556), momentum(-0.519), dd_momentum(-0.440), vw_pressure(-0.330), turnover(-0.226), vol_surprise(-0.170), low_vol(+0.061), size(+0.022)
  - **30-factor full set**: Sharpe 0.662 (diluted by weak factors). IC-weighted: 0.571 (overfit). Ridge: -0.298 (overfit).
- Notes: Best single-strategy Sharpe found. Equal-weight outperforms ML weighting (ridge/IC) — simpler is better. Most recent WF fold (Jan-Apr 2026) essentially flat (-0.049). The premium and vol_term factors contribute most beyond momentum. low_vol and size can be dropped with no loss. Correlation with H-012 at 0.547 means some momentum overlap but substantial diversification from the other 8 factors.
- Sessions: [2026-04-09 session 173]

## H-497: BTC Trend Regime Exposure Scaling
- Status: REJECTED
- Idea: Scale ensemble exposure by BTC EMA(20)/EMA(50) trend direction. Full exposure in uptrend, 50% in downtrend.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Regime overlay on H-496 base ensemble. When BTC trend positive, full exposure; negative, halve exposure.
- Result: IS Sharpe 2.182 (+2.1% vs base 2.137), WF 5/6, SH PASS (2.672/1.552). Improvement insufficient (<5%).
- Notes: Regime timing adds marginal value. DD improved to -19.6% from -23.8% but annual return dropped to 88.9%.
- Sessions: [2026-04-10 session 174]

## H-498: Volatility Regime Exposure Scaling
- Status: REJECTED
- Idea: Reduce exposure in high-vol environments. Scale from 1.0x (low vol) to 0.3x (high vol) based on rolling vol percentile.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 2.179 (+2.0%), WF 5/6, SH PASS (3.277/1.059). Improvement insufficient.
- Notes: DD improved to -17.8% but annual dropped to 60%. Vol scaling reduces both risk and return proportionally.
- Sessions: [2026-04-10 session 174]

## H-499: Dispersion Regime Exposure Scaling
- Status: REJECTED
- Idea: Scale exposure UP when XS return dispersion is high (more opportunity). Down when low.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 2.112 (-1.2%), WF 5/6, SH PASS (2.485/1.701). No improvement.
- Notes: Dispersion-based scaling doesn't add value — XS opportunities exist regardless of dispersion level.
- Sessions: [2026-04-10 session 174]

## H-500: Momentum Crash Protection
- Status: REJECTED
- Idea: Deleverage to 30% when 5d momentum drawdown exceeds -5%.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.824 (-14.6%), WF 5/6, SH PASS (2.511/0.970). Significantly worse.
- Notes: Crash protection hurts — drawdown periods are actually recovery opportunities for the ensemble.
- Sessions: [2026-04-10 session 174]

## H-501: Correlation Regime Exposure Scaling
- Status: REJECTED
- Idea: Reduce exposure when average pairwise asset correlations spike (less XS opportunity).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 2.078 (-2.8%), WF 5/6, SH PASS (2.653/1.326). No improvement.
- Sessions: [2026-04-10 session 174]

## H-502: Volume Regime Exposure Scaling
- Status: REJECTED
- Idea: Scale exposure by aggregate volume ratio (high volume = more signal strength).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 2.091 (-2.2%), WF 5/6, SH PASS (2.438/1.675). No improvement.
- Sessions: [2026-04-10 session 174]

## H-503: Trend-Adaptive Factor Weighting
- Status: REJECTED
- Idea: Tilt factor weights toward momentum in strong BTC trends, toward mean-reversion in choppy markets.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.985 (-7.1%), WF 5/6, SH PASS (2.353/1.539). Worse than equal weight.
- Notes: Dynamic factor weighting underperforms static equal-weight. Confirms H-496 finding: simpler is better.
- Sessions: [2026-04-10 session 174]

## H-504: Drawdown-Conditional Exposure
- Status: REJECTED
- Idea: Reduce exposure to 50% during portfolio drawdowns >3%.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.736 (-18.8%), WF 4/6, SH PASS (2.212/1.139). Worst of batch.
- Notes: Drawdown-based deleveraging is costly — the ensemble recovers quickly, so reducing exposure during DD cuts recovery.
- Sessions: [2026-04-10 session 174]

## H-505: Continuous Z-Score Proportional Weighting
- Status: REJECTED
- Idea: Instead of binary top/bottom 4, weight all assets proportional to their composite z-score.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.624 (-24.0%), WF 5/6, SH PASS (2.097/1.030). Significantly worse.
- Notes: Continuous weighting dilutes the signal by including low-conviction assets.
- Sessions: [2026-04-10 session 174]

## H-506: Volatility-Scaled Asset Weights
- Status: REJECTED
- Idea: Scale each selected asset's weight by inverse recent volatility.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.290 (-86.4%), WF 2/6, SH FAIL. Catastrophic failure.
- Notes: Implementation issue — vol scaling inverts the natural factor exposure and creates extreme weights.
- Sessions: [2026-04-10 session 174]

## H-507: Multi-Horizon Ensemble (3d/5d/10d)
- Status: REJECTED
- Idea: Blend signals from 3-day, 5-day, and 10-day rebalance frequencies.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.346 (-37.0%), WF 6/6, SH PASS (1.407/1.291). Worse despite robust WF.
- Notes: Blending frequencies dilutes the 5d signal which is already optimal.
- Sessions: [2026-04-10 session 174]

## H-508: Asymmetric Long/Short (L5/S3)
- Status: REJECTED
- Idea: More longs (5) with concentrated shorts (3) instead of balanced L4/S4.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.652 (-22.7%), WF 5/6, SH PASS (1.631/1.710). Param sweep confirms L4/S4 optimal.
- Notes: Asymmetry hurts. L4/S4 = 2.137, all other N combos worse. Short side contributes significantly.
- Sessions: [2026-04-10 session 174]

## H-509: Signal-Strength Threshold (z>0.3)
- Status: REJECTED
- Idea: Only trade assets with composite z-score exceeding 0.3 threshold.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.251 (-41.5%), WF 4/6, SH PASS (1.647/0.726). Much worse.
- Notes: Thresholding creates variable position count and reduces time-in-market.
- Sessions: [2026-04-10 session 174]

## H-510: Turnover-Penalized Signal Blending
- Status: REJECTED
- Idea: Blend new signal with previous signal (60/40) to reduce turnover.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.581 (-26.0%), WF 5/6, SH PASS (1.772/1.364). Worse. Sweep shows blend=1.0 (no blending) is optimal.
- Notes: Turnover penalty hurts more than it saves in fees. The 5d rebalance is already infrequent enough.
- Sessions: [2026-04-10 session 174]

## H-511: Dynamic N (Signal Dispersion Adaptive)
- Status: REJECTED
- Idea: Vary number of long/short positions (3-5) based on composite signal dispersion.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 2.159 (+1.0%), WF 6/6, SH PASS (2.546/1.694). Closest to base but improvement <5%.
- Notes: Marginal improvement — dynamic N concentrates when signals are strong. 0.990 correlation with base.
- Sessions: [2026-04-10 session 174]

## H-512: Risk-Parity Weighting (Inverse Vol)
- Status: REJECTED
- Idea: Weight selected assets by inverse volatility (equal risk contribution) instead of equal weight.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 2.037 (-4.7%), WF 6/6, SH PASS (2.421/1.596). Slightly worse.
- Notes: Risk-parity is robust (6/6 WF) but doesn't beat equal-weight. The XS ranking already accounts for vol differences.
- Sessions: [2026-04-10 session 174]

## H-513: Expanded Universe XS Momentum (27 coins)
- Status: REJECTED
- Idea: Run cross-sectional momentum on 27 assets instead of 14. More coins = more diversification.
- Instrument: futures (27 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.258, Ann +12.4%, DD -57.3%. WF 3/6 (mean 0.238). SH PASS (0.219/0.314). 14-asset: Sharpe 0.782.
- Notes: Expanding universe dilutes the signal. More noise, less edge. 14-asset universe is optimal.
- Sessions: [2026-04-10 session 175]

## H-514: Expanded Universe Size Factor (27 coins)
- Status: REJECTED
- Idea: Run size factor on 27 assets. More coins = bigger size spread.
- Instrument: futures (27 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.769, Ann +33.8%, DD -39.3%. WF 6/6 (mean 0.898). SH PASS. Corr 0.661 with 14-asset H-031.
- Notes: WF 6/6 but inferior to 14-asset H-031 (Sharpe ~2.5) and corr 0.661 = redundant. No gain from expansion.
- Sessions: [2026-04-10 session 175]

## H-515: Sector Momentum Rotation (L1 vs L2/Infra)
- Status: REJECTED
- Idea: Rotate between L1 coins (BTC,ETH,SOL...) and L2/infra (LINK,OP,ARB) based on sector momentum.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.137, Ann +5.5%, DD -51.7%. WF 3/6. SH FAIL (H1=-0.642). Corr 0.181 H-012.
- Notes: Crypto sectors are too small and correlated for sector rotation. Not enough independent sectors.
- Sessions: [2026-04-10 session 175]

## H-516: Long-Horizon Reversal (120d lookback, contrarian)
- Status: REJECTED
- Idea: Contrarian 120-day reversal — long worst performers, short best.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -1.099, Ann -52.2%, DD -85.0%. WF 0/6. SH FAIL.
- Notes: Crypto has strong momentum, not reversal. Going against trend is disastrous.
- Sessions: [2026-04-10 session 175]

## H-517: Volatility Mean Reversion
- Status: REJECTED
- Idea: Long coins whose volatility recently dropped (normalizing), short those still elevated.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.432, Ann -19.0%, DD -69.3%. WF 3/6. SH FAIL.
- Notes: Vol mean reversion doesn't work as a cross-sectional factor. Vol isn't mean-reverting fast enough to predict returns.
- Sessions: [2026-04-10 session 175]

## H-518: BTC Regime-Conditional Momentum
- Status: CONFIRMED (not deployed)
- Idea: Only take XS momentum positions when BTC in uptrend (20d SMA > 60d SMA). Zero positions in downtrend.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.360, Ann +65.9%, DD -46.7%. WF 6/6 (mean 1.441). SH PASS (1.230/1.556). Corr 0.793 H-012.
- Notes: Strong but essentially just momentum with a filter. Corr 0.793 with H-012 = redundant. Not adding independent information.
- Sessions: [2026-04-10 session 175]

## H-519: Relative Volume Shock
- Status: CONFIRMED (not deployed)
- Idea: Long coins with sudden volume increase (3d vs 30d volume ratio). Volume shock as breakout signal.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.516, Ann +64.6%, DD -38.8%. WF 5/6 (mean 1.562). SH PASS (1.956/0.996). Corr -0.041 H-012. **100% param robust (96/96).**
- Notes: Excellent standalone signal with near-zero H-012 corr. BUT corr 0.704 with H-336 (Volume Surprise) — same signal family. H-336 already deployed. Not adding.
- Sessions: [2026-04-10 session 175]

## H-520: Return Acceleration (momentum of momentum)
- Status: REJECTED
- Idea: Second derivative of price — long accelerating coins, short decelerating.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.479, Ann -21.0%, DD -65.2%. WF 2/6. SH FAIL. Corr -0.089 H-012.
- Notes: Acceleration doesn't work — crypto momentum is linear, not accelerating.
- Sessions: [2026-04-10 session 175]

## H-521: Realized Vol Expansion (vol breakout, high direction)
- Status: REJECTED
- Idea: Long coins with expanding realized vol (5d/60d vol ratio high). Vol breakout signals trending.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.632, Ann +26.0%, DD -59.4%. WF 4/6. SH FAIL (H1=1.718, H2=-0.594). Corr -0.035 H-012.
- Notes: Passes IS and WF but second half of sample is negative. Signal decayed over time.
- Sessions: [2026-04-10 session 175]

## H-522: PVT Slope (cumulative price-volume trend)
- Status: CONFIRMED (not deployed)
- Idea: Slope of cumulative PVT (daily_return * volume) over 20 days. High slope = volume-confirmed trend.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.978, Ann +39.8%, DD -40.6%. WF 4/6 (mean 0.779). SH PASS (1.704/0.114). Corr 0.425 H-012. **100% param robust (30/30).**
- Notes: Passes all tests, 100% robust. But moderate H-012 corr (0.425) and weak H2 (0.114). Corr 0.330 with H-383 PVT Level. Not independent enough to deploy.
- Sessions: [2026-04-10 session 175]

## H-523: Weekend Relative Performance
- Status: REJECTED
- Idea: Rank coins by weekend vs weekday return differential. Long weekend outperformers.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.892, Ann -38.9%, DD -81.2%. WF 2/6. SH FAIL.
- Notes: Weekend/weekday return patterns not stable enough for cross-sectional ranking.
- Sessions: [2026-04-10 session 175]

## H-524: Beta Stability (low beta change vs BTC)
- Status: REJECTED
- Idea: Long coins with stable beta to BTC, short coins with unstable beta.
- Instrument: futures (13 non-BTC perps)
- Timeframe: 1D
- Result: IS Sharpe 0.393, Ann +15.1%, DD -58.4%. WF 5/6. SH FAIL (H1=-0.308).
- Notes: WF 5/6 but SH failure and low Sharpe. Beta stability has weak predictive power.
- Sessions: [2026-04-10 session 175]

## H-525: Cumulative Volume Delta (buy vs sell pressure)
- Status: REJECTED (borderline)
- Idea: Approximate buy/sell pressure from candle direction. Long high CVD, short low CVD.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.030, Ann +40.5%, DD -35.5%. WF 4/6. SH FAIL (H1=1.857, H2=-0.028). Corr 0.398 H-012.
- Notes: Strong H1 but essentially zero H2. Momentum-correlated. Signal degraded in second half.
- Sessions: [2026-04-10 session 175]

## H-526: Volume Decay Rate
- Status: REJECTED
- Idea: Ratio of short-to-medium vs short-to-long volume ratios. Captures volume concentration pattern.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.988, Ann -43.2%, DD -84.7%. WF 2/6. SH FAIL.
- Notes: Volume decay rate has no predictive power. Complex ratio just adds noise.
- Sessions: [2026-04-10 session 175]

## H-527: Body-to-Shadow Ratio (candle structure)
- Status: REJECTED
- Idea: Rank coins by average body-to-shadow ratio. High body = directional conviction.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.139, Ann +5.7%, DD -62.6%. WF 4/6. SH FAIL.
- Notes: Candle body vs wick ratio has minimal cross-sectional predictive power.
- Sessions: [2026-04-10 session 175]

## H-528: Range Expansion Momentum
- Status: CONFIRMED — **DEPLOYED**
- Idea: Long coins with expanding daily range (5d/30d high-low range ratio), short contracting. Breakout signal.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.849, Ann +36.8%, DD -37.5%. WF 4/6. SH PASS (1.502/0.164). **100% param robust (96/96).** Corr **-0.001** H-012. Near-zero with H-031 (-0.052), H-076 (0.029), H-182 (0.069).
- Notes: Near-perfect diversifier — zero correlation with momentum, size, and efficiency. 100% robust across all parameter combinations. Deployed to paper trade. Best (3,30,3,3) Sharpe 2.021.
- Sessions: [2026-04-10 session 175]

## H-529: Return Streak Persistence (contrarian)
- Status: REJECTED
- Idea: Contrarian on consecutive up/down day streaks. Long losing streaks, short winning.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.553, Ann +22.2%, DD -57.0%. WF 4/6. SH FAIL (H1=-0.638). Corr 0.056 H-012.
- Notes: Passes IS+WF but first half negative. Streak reversal not reliable.
- Sessions: [2026-04-10 session 175]

## H-530: Dollar Volume Share (market attention proxy)
- Status: REJECTED (redundant)
- Idea: Rank coins by share of total universe dollar volume. Long high share, short low.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.129, Ann +55.8%, DD -50.5%. WF 5/6. SH PASS (0.533/1.713). Corr 0.543 H-012, **0.934 H-031**.
- Notes: Passes all tests but corr 0.934 with H-031 (Size Factor) = identical signal. Dollar volume share IS size. Redundant.
- Sessions: [2026-04-10 session 175]

## H-531: Range Contraction (inverse of H-528)
- Status: REJECTED
- Idea: Inverse of H-528 — long contracting range, short expanding.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.849, Ann -36.8%, DD -83.3%. WF 2/6. SH FAIL.
- Notes: Exact mirror of H-528 — confirms H-528's direction (high range expansion is bullish).
- Sessions: [2026-04-10 session 175]

## H-532: BTC Funding Rate Contrarian (Time-Series)
- Status: REJECTED
- Idea: Fade the crowd — short BTC when funding rate is high, long when low.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Logic: Average 8h funding rate over N days. Contrarian position based on threshold.
- Result: Best config W10_T5e-05: Sharpe -0.042, Ann -0.9%, DD -48.6%. Win rate 49.6%, 19% exposure, 36 trades.
- Notes: No edge in funding rate contrarian on BTC TS. Funding is too noisy and mean-reverting for directional signals. XS version (H-053) works because relative ranking is more stable.
- Sessions: [2026-04-10 session 176]

## H-533: BTC Volatility Breakout (Bollinger Band)
- Status: REJECTED
- Idea: Trade BTC breakouts from Bollinger Bands.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Logic: Long when close > upper BB, short when close < lower BB.
- Result: Best config LB10_M1.5: Sharpe 0.374, Ann +10.9%, DD -33.5%. Win rate 32.4%, 22% exposure.
- Notes: Weak Sharpe, low win rate. Trend following captures the same signal better (H-539 Keltner).
- Sessions: [2026-04-10 session 176]

## H-534: BTC RSI Mean Reversion
- Status: REJECTED
- Idea: Short BTC when RSI overbought, long when oversold.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Logic: RSI(N) > overbought -> short. RSI(N) < oversold -> long.
- Result: Best config LB7_OB75: Sharpe 0.135, Ann +4.7%, DD -61.0%. Win rate 41.6%.
- Notes: Mean reversion doesn't work in crypto — momentum dominates. High DD confirms.
- Sessions: [2026-04-10 session 176]

## H-535: BTC Intraday Session Momentum
- Status: CONFIRMED (deployed)
- Idea: First 6h return of the day predicts next-day BTC direction.
- Instrument: BTC/USDT perp
- Timeframe: 1D (signal from hourly)
- Logic: If first 6h return > 0, go LONG next day. If < 0, SHORT.
- Result: IS Sharpe 0.735, Ann +39.3%, DD -54.8%. 100% exposure, 50% win rate.
- WF: **6/8 positive**, mean **1.051**. SH: **PASS** (H1=0.985, H2=1.245). Corr 0.111 H-009, 0.195 H-539.
- Notes: Strong OOS evidence. 100% exposure means always in market. DD -54.8% borderline but WF 6/8 with mean >1 is very strong. Low correlation with H-009 (different signal despite both trading BTC). First BTC TS strategy with genuine validation.
- Sessions: [2026-04-10 session 176]

## H-536: BTC Funding-Price Divergence
- Status: REJECTED
- Idea: Trade BTC when funding and price direction diverge.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Best config FW3_PW7: Sharpe 0.574, Ann +6.4%, DD -12.6%. Only 6% exposure, 106 trades in 730 days.
- Notes: Low exposure means very few signals. Good DD but insufficient trade count for statistical significance.
- Sessions: [2026-04-10 session 176]

## H-537: BTC Volume Shock Reversal
- Status: REJECTED
- Idea: After extreme volume days, expect mean reversion.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Best config LB30_Z2.0: Sharpe 0.362, Ann +6.9%, DD -29.5%. 6% exposure.
- Notes: Weak Sharpe. Volume shocks don't reliably predict reversals in BTC.
- Sessions: [2026-04-10 session 176]

## H-538: BTC Month-of-Year Seasonality
- Status: REJECTED
- Idea: Trade BTC based on historical monthly patterns (long in positive months, short in negative).
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: IS Sharpe 1.108, Ann +59.1%, DD -63.6%. But WF: **2/5 positive** (mean -0.154). SH: FAIL (H1=1.88, H2=-0.12).
- Notes: Monthly patterns are unstable — only ~4 observations per month in 4.7 years. Pattern shifts across cycles. Look-ahead bias inflated IS.
- Sessions: [2026-04-10 session 176]

## H-539: BTC Keltner Channel Breakout
- Status: CONFIRMED (deployed)
- Idea: Trade BTC breakouts from Keltner Channel (EMA + ATR bands).
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Logic: Long when close > EMA(30) + 2.5*ATR(30). Short when close < EMA(30) - 2.5*ATR(30). Flat inside.
- Result: IS Sharpe 0.832, Ann +20.2%, DD -26.2%. 15% exposure, 106 trades.
- WF: **5/7 positive** (mean **0.751**). SH: **PASS** (H1=0.691, H2=0.959). Param robust **83%** (25/30 positive).
- Corr: 0.453 H-009, 0.195 H-535, 0.124 H-544.
- Notes: Selective trend following — only trades during strong breakouts. Low exposure (15%) = excellent diversifier. H-009 correlation (0.453) because when active, it aligns with the trend H-009 is tracking. But only 15% of the time.
- Sessions: [2026-04-10 session 176]

## H-540: Multi-Asset TSMOM (14 perps)
- Status: REJECTED
- Idea: Per-asset TS momentum: long if 10d return > 0, short if < 0. Equal weight all 14 assets.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: **CRITICAL: Initial IS Sharpe 6.17 was due to LOOK-AHEAD BIAS** (positions not shifted by 1 day). After fix: Sharpe 0.571, Ann +34.5%, DD -64.3%. WF: 4/8 positive (mean 0.658). SH: 0.89/0.26.
- Notes: Bug caught and documented. Without look-ahead, strategy has mediocre Sharpe with terrible DD. Multi-asset TSMOM doesn't add enough over BTC-only strategies. Daily sign-based positions are too noisy.
- Sessions: [2026-04-10 session 176]

## H-541: Multi-Asset Carry (Funding Rate)
- Status: REJECTED
- Idea: Long-short based on funding rate level — either pro-carry (long high funding) or anti-carry (contrarian).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: Pro-carry Sharpe -0.703 (wrong direction). Anti-carry best: Sharpe 0.773, Ann +17.3%, DD -27.3%.
- Notes: Anti-carry = same as H-053 (Funding XS Contrarian). Redundant. Pro-carry loses money — in crypto, high funding predicts reversals, not continuation.
- Sessions: [2026-04-10 session 176]

## H-542: BTC Vol-Adjusted Momentum
- Status: REJECTED
- Idea: BTC momentum signal scaled by inverse volatility (risk parity).
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Best config M30_V30: Sharpe 0.629, Ann +10.6%, DD -23.4%.
- Notes: Marginal improvement over basic momentum (H-009). Not novel enough to deploy.
- Sessions: [2026-04-10 session 176]

## H-543: BTC Absolute Momentum (Cash Filter)
- Status: REJECTED
- Idea: Long BTC only when beating cash (5% annual). Short when significantly negative.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Best config LB40: Sharpe 0.459, Ann +24.0%, DD -61.6%.
- Notes: Weak Sharpe with high DD. Cash filter doesn't add enough value in crypto.
- Sessions: [2026-04-10 session 176]

## H-544: BTC Range Squeeze Breakout
- Status: CONFIRMED (deployed)
- Idea: After periods of range contraction (low ATR), trade breakout direction.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Logic: When ATR(20) is in bottom 10th percentile (60d window), signal = direction of last daily move. Flat when not in squeeze.
- Result: IS Sharpe 0.986, Ann +23.0%, DD -23.2%. ~14-21% exposure.
- WF: **5/8 positive** (mean **0.470**). SH: **PASS** (H1=1.235, H2=0.427). Param robust **100%** (36/36 positive).
- Corr: **0.109** H-009, **0.124** H-539 — near-zero with all existing strategies.
- Notes: 100% parameter robustness is strongest validation signal. Near-zero correlation with everything. Currently in squeeze (ATR 8.3rd percentile) — entered LONG at deployment. Selective strategy ~14-21% exposure.
- Sessions: [2026-04-10 session 176]

## H-545: Multi-Asset Short-Term Reversal
- Status: REJECTED
- Idea: Cross-sectional reversal: short recent winners, long recent losers (1-5 day returns).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: Best config LB5_H3: Sharpe -3.744, Ann -91.9%, DD -85.2%.
- Notes: Short-term reversal is catastrophically wrong in crypto — momentum dominates at all frequencies. Anti-momentum = guaranteed loss.
- Sessions: [2026-04-10 session 176]

## H-546: BTC Full Week Seasonality
- Status: REJECTED
- Idea: Trade BTC based on full 7-day DOW pattern (not just Wed/Thu like H-039).
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.737, Ann -39.4%, DD -93.8%.
- Notes: Full-week DOW pattern is unstable. H-039's Wed-long/Thu-short is the only robust DOW signal. Adding more days dilutes the edge.
- Sessions: [2026-04-10 session 176]

## H-547: BTC Consecutive Returns Signal
- Status: REJECTED
- Idea: After 5+ consecutive up/down days, bet on continuation (momentum).
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Best config momentum_N5: Sharpe 0.721, Ann +11.0%, DD -14.4%. Only 5% exposure.
- Notes: Interesting Sharpe and low DD, but only 5% exposure = too few trades for statistical significance. Good IS but can't validate OOS with so few events.
- Sessions: [2026-04-10 session 176]

## H-548: ETH Intraday Session Momentum
- Status: REJECTED
- Idea: ETH first 6h return predicts next-day direction (same as H-535 but for ETH).
- Instrument: ETH/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.447, Ann -44.2%, DD 97.8%. Param robust 3/8 (38%).
- Notes: ETH does not exhibit the intraday session momentum pattern. Sharp contrast with BTC/SOL.
- Sessions: [2026-04-10 session 177]

## H-549: ETH Keltner Channel Breakout
- Status: REJECTED
- Idea: Keltner channel breakout on ETH daily.
- Instrument: ETH/USDT perp
- Timeframe: 1D
- Result: Sharpe 0.152, Ann -13.5%, DD 81.6%. Param robust 16/20 (80%) but Sharpe too low.
- Notes: Param robust but base Sharpe well below 0.5 threshold.
- Sessions: [2026-04-10 session 177]

## H-550: ETH Range Squeeze
- Status: REJECTED
- Idea: Bollinger Bands inside Keltner channel = squeeze. Breakout direction = trade.
- Instrument: ETH/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.135, Ann -11.3%, DD 70.0%. Param robust 11/27 (41%).
- Notes: Squeeze signals are too noisy on ETH. Failed IS and param robustness.
- Sessions: [2026-04-10 session 177]

## H-551: ETH RSI Mean Reversion
- Status: REJECTED
- Idea: RSI mean-reversion on ETH daily (buy oversold, sell overbought).
- Instrument: ETH/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.322, Ann -24.4%, DD 81.1%. Param robust 0/16 (0%).
- Notes: Mean-reversion universally fails in crypto. 0% param robustness confirms no edge.
- Sessions: [2026-04-10 session 177]

## H-552: ETH Volume Spike Momentum
- Status: REJECTED
- Idea: Trade in direction of price on volume spike days.
- Instrument: ETH/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.179, Ann -13.4%, DD 70.0%. Param robust 8/16 (50%).
- Notes: Volume spikes on ETH are not predictive of continuation.
- Sessions: [2026-04-10 session 177]

## H-553: ETH MACD Crossover
- Status: REJECTED
- Idea: Classic MACD crossover on ETH daily.
- Instrument: ETH/USDT perp
- Timeframe: 1D
- Result: Sharpe 0.071, Ann -18.5%, DD 81.5%. Param robust 12/27 (44%).
- Notes: MACD generates too many whipsaw trades in crypto. Sharpe near zero.
- Sessions: [2026-04-10 session 177]

## H-554: ETH Overnight Gap Contrarian
- Status: REJECTED
- Idea: Trade contrarian to overnight (00-06 UTC) gap on ETH.
- Instrument: ETH/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.915, Ann -51.2%, DD 98.5%. Param robust 0/6 (0%).
- Notes: Contrarian gap trading is catastrophically wrong — crypto overnight moves continue into the day, not reverse.
- Sessions: [2026-04-10 session 177]

## H-555: ETH Bollinger Band Reversion
- Status: REJECTED
- Idea: Bollinger band mean-reversion on ETH daily (buy lower band, sell upper).
- Instrument: ETH/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.265, Ann -25.3%, DD 81.7%. Param robust 5/20 (25%).
- Notes: Another mean-reversion failure. Crypto trends dominate.
- Sessions: [2026-04-10 session 177]

## H-556: BTC-ETH Spread Mean Reversion
- Status: REJECTED
- Idea: Log BTC/ETH price ratio z-score mean-reversion.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.326, Ann -19.6%, DD 76.5%. Param robust 1/20 (5%).
- Notes: BTC/ETH ratio is not mean-reverting over these timeframes. The ratio has structural trends.
- Sessions: [2026-04-10 session 177]

## H-557: Multi-Asset TSMOM Portfolio (BTC+ETH+SOL)
- Status: REJECTED
- Idea: Time-series momentum on BTC, ETH, SOL individually, equal-weight portfolio.
- Instrument: futures (BTC/ETH/SOL perps)
- Timeframe: 1D
- Result: Sharpe 0.303, Ann NaN (calculation issue), DD 67.4%. Param robust 6/6 (100%).
- Notes: 100% param robust but Sharpe too low (0.303 < 0.5 threshold). Not enough edge.
- Sessions: [2026-04-10 session 177]

## H-558: BTC Hourly Mean Reversion
- Status: REJECTED
- Idea: Intraday mean-reversion on BTC using hourly z-score.
- Instrument: BTC/USDT perp
- Timeframe: 1h
- Result: Sharpe -2.116, Ann -57.4%, DD 98.4%. Param robust 0/16 (0%).
- Notes: BTC does NOT mean-revert at hourly frequency. Strongest rejection in this batch.
- Sessions: [2026-04-10 session 177]

## H-559: BTC Weekend Effect
- Status: REJECTED
- Idea: BTC long from Friday close to Monday close (weekend effect).
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe 0.279, Ann 3.6%, DD 50.9%.
- Notes: Very weak edge (Sharpe 0.279). Weekend effect exists but too small to trade profitably after fees.
- Sessions: [2026-04-10 session 177]

## H-560: BTC->ETH Leader-Follower
- Status: REJECTED
- Idea: BTC hourly momentum predicts ETH next-day direction.
- Instrument: ETH/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.256, Ann -35.4%, DD 89.5%. Param robust 2/5 (40%).
- Notes: BTC does not lead ETH at daily frequency. Both move together.
- Sessions: [2026-04-10 session 177]

## H-561: BTC ATR Breakout
- Status: REJECTED
- Idea: Trade when BTC daily close moves > mult*ATR from previous close.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe 0.404, Ann 7.7%, DD 71.2%. Param robust 17/20 (85%).
- Notes: Close to passing (Sharpe 0.404, 85% param robust) but below 0.5 threshold.
- Sessions: [2026-04-10 session 177]

## H-562: BTC Donchian Channel
- Status: REJECTED
- Idea: Donchian channel (turtle-style) breakout on BTC daily.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.021, Ann -14.1%, DD 82.3%. Param robust 2/7 (29%).
- Notes: Classic turtle system doesn't work in crypto. Too many false breakouts.
- Sessions: [2026-04-10 session 177]

## H-563: BTC Vol Regime Adaptive
- Status: REJECTED
- Idea: Momentum in low-vol regimes, mean-reversion in high-vol regimes.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe 0.034, Ann -8.9%, DD 74.2%. Param robust 3/20 (15%).
- Notes: Regime switching doesn't add value. Both momentum and mean-reversion components cancel out.
- Sessions: [2026-04-10 session 177]

## H-564: BTC Adaptive EMA
- Status: REJECTED
- Idea: Adaptive EMA crossover — shorter EMAs in low vol, longer in high vol.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe 0.125, Ann -3.8%, DD 58.6%. Param robust 6/6 (100%) but Sharpe too low.
- Notes: Adaptive parameters don't improve over fixed EMA. Overfitting risk.
- Sessions: [2026-04-10 session 177]

## H-565: BTC 4h EMA Trend
- Status: REJECTED
- Idea: BTC 4h EMA crossover trend following.
- Instrument: BTC/USDT perp
- Timeframe: 4h
- Result: Sharpe -0.052, Ann -15.1%, DD 74.6%. Param robust 2/20 (10%).
- Notes: 4h EMA crossover generates excessive whipsaw. 10% param robustness.
- Sessions: [2026-04-10 session 177]

## H-566: BTC 4h RSI Momentum
- Status: REJECTED
- Idea: BTC 4h RSI momentum — long when RSI > 50, short below.
- Instrument: BTC/USDT perp
- Timeframe: 4h
- Result: Sharpe -0.843, Ann -43.9%, DD 95.2%. Param robust 0/12 (0%).
- Notes: RSI as a directional signal fails completely on 4h BTC.
- Sessions: [2026-04-10 session 177]

## H-567: BTC 4h VWAP Reversion
- Status: REJECTED
- Idea: BTC 4h VWAP deviation mean-reversion.
- Instrument: BTC/USDT perp
- Timeframe: 4h
- Result: Sharpe -0.601, Ann -30.3%, DD 90.2%. Param robust 0/16 (0%).
- Notes: Mean-reversion fails at 4h too. Crypto trends dominate all frequencies.
- Sessions: [2026-04-10 session 177]

## H-568: BTC 4h Momentum+Vol Filter
- Status: REJECTED
- Idea: BTC 4h momentum only in expanding volatility regimes.
- Instrument: BTC/USDT perp
- Timeframe: 4h
- Result: Sharpe 0.166, Ann -1.0%, DD 49.8%. Param robust 7/12 (58%).
- Notes: Vol filter helps (lower DD than pure momentum) but Sharpe still too low.
- Sessions: [2026-04-10 session 177]

## H-569: SOL Daily EMA Trend
- Status: REJECTED
- Idea: SOL daily EMA crossover trend following.
- Instrument: SOL/USDT perp
- Timeframe: 1D
- Result: Sharpe 0.383, Ann -9.8%, DD 90.0%. Param robust 18/19 (95%). WF 3/7 (FAIL).
- Notes: High param robustness but Sharpe below threshold and WF fails.
- Sessions: [2026-04-10 session 177]

## H-570: SOL Keltner Breakout
- Status: REJECTED
- Idea: SOL Keltner channel breakout.
- Instrument: SOL/USDT perp
- Timeframe: 1D
- Result: Sharpe 0.286, Ann -17.3%, DD 94.4%. Param robust 16/20 (80%).
- Notes: Keltner breakout on SOL doesn't generate sufficient edge.
- Sessions: [2026-04-10 session 177]

## H-571: SOL Intraday Session Momentum
- Status: LIVE (paper trade since 2026-04-10)
- Idea: SOL first 6h return of the day predicts next-day SOL direction. Long if > 0, short if < 0. First SOL time-series strategy.
- Instrument: SOL/USDT perp
- Timeframe: 1D (signal from hourly bars)
- Logic: Compute first 6 hours return. If positive, go long SOL next day. If negative, short. 50% capital allocation.
- Result: IS Sharpe 0.847, Ann +42.8%, DD 77.5%. WF **6/7** positive (mean 0.848). SH PASS (H1=0.679, H2=1.06). Param robust **12/12 (100%)**. BTC corr **-0.092**.
- Notes: Same pattern as BTC H-535 but works even better on SOL. Negative BTC correlation means excellent diversifier. High DD (77.5%) is due to SOL's extreme volatility, not strategy weakness. Deployed 2026-04-10.
- Sessions: [2026-04-10 session 177]

## H-572: BTC Multi-Timeframe (Daily+Hourly)
- Status: REJECTED
- Idea: Daily EMA trend filter + hourly momentum confirmation. Only trade when both timeframes agree.
- Instrument: BTC/USDT perp
- Timeframe: 1h (with daily filter)
- Result: IS Sharpe 0.651, Ann +20.5%, DD 33.9%. WF **6/7** positive (mean 0.482). SH PASS (H1=0.663, H2=0.758). Param robust **25/36 (69%)** — below 75% threshold.
- Notes: Strong WF and SH results but param robustness at 69% fails the 75% cutoff. Close but REJECTED. Could revisit with refined parameter space.
- Sessions: [2026-04-10 session 177]

## H-573: BTC Trend + Vol Targeting
- Status: REJECTED
- Idea: BTC daily EMA trend with volatility targeting (similar to H-009 with different params).
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.071, Ann -1.9%, DD 29.0%. Param robust 3/12 (25%).
- Notes: Already have H-009 doing this. Different params don't improve. Low DD is only merit.
- Sessions: [2026-04-10 session 177]

## H-574: BTC ADX Trend
- Status: REJECTED
- Idea: BTC ADX trend strength — only trade in strong trends (ADX > threshold).
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.232, Ann -20.6%, DD 81.9%. Param robust 5/16 (31%).
- Notes: ADX filtering doesn't work for crypto. Trends start/end too abruptly for ADX to capture.
- Sessions: [2026-04-10 session 177]

## H-575: BTC Volume-Confirmed Momentum
- Status: REJECTED
- Idea: BTC price momentum confirmed by expanding volume trend.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.141, Ann -12.8%, DD 69.0%. Param robust 8/16 (50%).
- Notes: Volume confirmation doesn't improve momentum in crypto. Volume patterns are noisy.
- Sessions: [2026-04-10 session 177]

## H-576: BTC SuperTrend
- Status: REJECTED
- Idea: BTC SuperTrend indicator signal.
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Deep validation: Sharpe -0.07, Ann -16.5%, DD 83.3%. Initial screening inflated by low trade count.
- Notes: Initial screening showed Sharpe 0.56 with 100% param robust, but deep validation revealed the signal has 103 flips over 4.7 years (reasonable) yet Sharpe is actually negative. WF 5/7 was also misleading. BTC buy-and-hold Sharpe 0.566 is better.
- Sessions: [2026-04-10 session 177]

## H-577: BTC Heikin-Ashi Trend
- Status: REJECTED
- Idea: BTC Heikin-Ashi candle trend confirmation (N consecutive bullish/bearish candles).
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe -0.349, Ann -20.9%, DD 74.0%. Param robust 0/6 (0%).
- Notes: Heikin-Ashi smoothing doesn't add signal beyond raw price. 0% param robustness.
- Sessions: [2026-04-10 session 177]

## H-578: BTC Ichimoku Cloud
- Status: REJECTED
- Idea: BTC Ichimoku cloud signal (above cloud + TK cross = long).
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe 0.195, Ann -1.0%, DD 50.2%. Param robust 17/27 (63%).
- Notes: Ichimoku is too lagging for crypto. By the time signals confirm, the move is over.
- Sessions: [2026-04-10 session 177]

## H-579: BTC Daily Mean Reversion
- Status: REJECTED
- Idea: BTC daily z-score mean-reversion (buy below MA, sell above).
- Instrument: BTC/USDT perp
- Timeframe: 1D
- Result: Sharpe 0.474, Ann 11.0%, DD 33.7%. Param robust 5/20 (25%).
- Notes: Best mean-reversion result we've seen (Sharpe 0.474, low DD 33.7%) but still below 0.5 threshold and only 25% param robust.
- Sessions: [2026-04-10 session 177]

## H-580: Multi-Period Momentum Combo
- Status: REJECTED
- Idea: Average z-scored 5d/20d/60d momentum for XS ranking.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.587, Ann +23.0%, DD 34.5%. Corr 0.607 H-012 (redundant).
- Notes: Below IS threshold. High H-012 correlation — captures same momentum signal. SH 1.13/-0.15 unstable.
- Sessions: [2026-04-10 session 178]

## H-581: Return Dispersion Factor
- Status: REJECTED
- Idea: XS ranking by own-vol z-score relative to cross-section. Low dispersion = long.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.040, Ann +1.7%, DD 60.7%. No edge.
- Notes: Cross-sectional return dispersion has no predictive power in crypto.
- Sessions: [2026-04-10 session 178]

## H-582: Momentum Acceleration
- Status: REJECTED
- Idea: Change in 5-day momentum (current - lagged) as XS signal.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe -1.185, Ann -49.5%, DD 75.5%. Strong negative = mean-reversion bias.
- Notes: Acceleration captures the wrong signal in crypto — buying accelerating assets is a loss.
- Sessions: [2026-04-10 session 178]

## H-583: OBV Rate of Change
- Status: REJECTED
- Idea: On-Balance Volume 20-day percent change as XS factor.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe -0.936, Ann -32.6%, DD 62.1%.
- Notes: OBV ROC has strong negative Sharpe — OBV momentum actually reverses in crypto.
- Sessions: [2026-04-10 session 178]

## H-584: Price-EMA Distance Factor
- Status: REJECTED
- Idea: Distance from 21-EMA as XS momentum proxy.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.091, Ann +4.1%, DD 46.9%. Corr 0.305 H-012.
- Notes: Weak edge. Mostly captures same signal as raw momentum. SH -0.21/0.53 fail.
- Sessions: [2026-04-10 session 178]

## H-585: Direction Streak Factor
- Status: REJECTED
- Idea: Count up days minus down days over 20d period as XS factor.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.666, Ann +25.2%, DD 32.4%. Corr 0.229 H-012. Close but below threshold.
- Notes: SH 0.36/1.01 borderline. Just below 0.7 Sharpe threshold.
- Sessions: [2026-04-10 session 178]

## H-586: Relative Volume Surge Factor
- Status: REJECTED
- Idea: Today's dollar volume / 20d avg dollar volume as XS factor.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.544, Ann +21.5%, DD 39.5%. Corr -0.030 H-012.
- Notes: Near-zero H-012 corr but IS too weak. SH -0.49/1.82 very unstable.
- Sessions: [2026-04-10 session 178]

## H-587: Close-Open Gap Reversal
- Status: REJECTED
- Idea: Contrarian signal based on average open-to-close gap over 10d.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe -0.284, Ann -19.5%, DD 81.5%.
- Notes: Gaps don't exist meaningfully in 24/7 crypto. No edge.
- Sessions: [2026-04-10 session 178]

## H-588: Funding Rate Momentum
- Status: REJECTED
- Idea: Change in cumulative funding rate over 7d period (contrarian) as XS signal.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.601, Ann +22.1%, DD 33.2%. Corr -0.105 H-012. Close but below threshold.
- Notes: Funding momentum captures different signal than pure price momentum but insufficient IS Sharpe. SH 1.02/-0.01 borderline.
- Sessions: [2026-04-10 session 178]

## H-589: Volatility Ratio (Short/Long Realized)
- Status: CONFIRMED (not deployed — factor-level redundancy with H-059)
- Idea: Rank by 5d/30d realized vol ratio. High ratio = expanding vol = long.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 1.213, Ann +47.1%, DD 42.5%. WF **5/6** (mean varies by fold). SH 0.474/2.304 PASS. Param 77%. Corr **-0.144** H-012.
- Notes: Strong IS and WF. But factor-level corr with H-059 is **0.82+** per asset — same signal (short vol / long vol ratio). PnL corr 0.43 is lower due to different N/rebal, but deploying both double-counts the signal. CONFIRMED standalone quality, NOT deployed.
- Sessions: [2026-04-10 session 178]

## H-590: Price-Volume Correlation Factor
- Status: REJECTED
- Idea: Rolling 20d correlation between price returns and volume returns.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.421, Ann +15.1%, DD 29.8%. Corr 0.408 H-012.
- Notes: Moderate H-012 overlap, insufficient IS Sharpe.
- Sessions: [2026-04-10 session 178]

## H-591: Body-to-Range Ratio
- Status: REJECTED
- Idea: Avg candlestick body/range ratio over 15d. High body = clean trend.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe -0.623, Ann -23.8%, DD 64.6%. Negative edge.
- Notes: Candlestick body/range has negative predictive power in crypto.
- Sessions: [2026-04-10 session 178]

## H-592: Upper Shadow Ratio
- Status: REJECTED
- Idea: Average upper shadow proportion of daily candle over 15d (low shadow = bullish).
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.107, Ann +3.8%, DD 53.8%. SH -1.24/1.65 very unstable.
- Notes: No edge in cross-section. Upper shadow doesn't predict future returns.
- Sessions: [2026-04-10 session 178]

## H-593: Volume-Weighted Return Momentum
- Status: REJECTED
- Idea: 20d volume-weighted cumulative return as XS factor.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.837, Ann +32.8%, DD 27.3%. WF 3/6 (FAIL). Corr 0.560 H-012. Param 94%.
- Notes: Passes IS and param robustness, but WF 3/6 FAIL. High H-012 correlation — mostly captures momentum.
- Sessions: [2026-04-10 session 178]

## H-594: Tail Asymmetry Factor
- Status: REJECTED
- Idea: Ratio of 90th percentile positive returns to 10th percentile negative returns over 30d.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.510, Ann +18.7%, DD 35.3%. Below threshold.
- Notes: Tail risk asymmetry has moderate but insufficient edge. SH 0.85/0.09 borderline.
- Sessions: [2026-04-10 session 178]

## H-595: Large Move Persistence Factor
- Status: REJECTED
- Idea: Count of >2% daily moves (up minus down) over 20d period.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.242, Ann +9.0%, DD 35.8%. No meaningful edge.
- Notes: Counting large moves is too noisy. SH -0.04/0.62 unstable.
- Sessions: [2026-04-10 session 178]

## H-596: Wicking Factor
- Status: REJECTED
- Idea: Avg wick-to-body ratio over 15d. Low wick = clean trend = long.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe -0.206, Ann -6.6%, DD 37.3%.
- Notes: Wick/body ratio has no predictive power. Similar to H-591 (body/range) failure.
- Sessions: [2026-04-10 session 178]

## H-597: Overnight Return Momentum
- Status: REJECTED
- Idea: 20d cumulative overnight (open - prev close) returns as XS signal.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe -0.253, Ann -17.3%, DD 81.5%.
- Notes: No meaningful overnight in 24/7 crypto. Same result as H-587.
- Sessions: [2026-04-10 session 178]

## H-598: Return Autocorrelation Factor
- Status: REJECTED
- Idea: Rolling 20d lag-1 autocorrelation as XS ranking factor.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe -0.272, Ann -10.4%, DD 54.9%.
- Notes: Serial correlation doesn't predict XS returns.
- Sessions: [2026-04-10 session 178]

## H-599: RSI Cross-Sectional Factor
- Status: LIVE (paper trade since 2026-04-10)
- Idea: Rank 14 assets by 14-period RSI. Long highest RSI, short lowest.
- Instrument: 14 crypto perps
- Timeframe: 1D (rebalance every 5 days)
- Result: IS Sharpe **1.148**, Ann +47.7%, DD 29.4%. WF **4/6** (mean 0.977). SH **1.621/0.544 PASS**. Param robust **60/60 (100%)**, best 2.306. Corr 0.455 H-012.
- Notes: RSI captures momentum direction + strength. 100% param robust across 5 periods x 12 configs. Borderline H-012 corr but passes threshold. Deployed.
- Sessions: [2026-04-10 session 178]

## H-600: Intraday Range Expansion Rate
- Status: REJECTED
- Idea: Ratio of recent 20d avg range to previous 20d avg range as XS signal.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 1.130, Ann +45.1%, DD 37.2%. WF 3/6 (FAIL). SH 2.49/-0.44.
- Notes: Strong IS but WF 3/6 and SH H2 negative = time-varying edge. Not robust enough.
- Sessions: [2026-04-10 session 178]

## H-601: Volume Decline Rate Factor
- Status: LIVE (paper trade since 2026-04-10)
- Idea: Rank by recent vs longer-term dollar volume (10d/20d avg). Rising volume = long.
- Instrument: 14 crypto perps
- Timeframe: 1D (rebalance every 5 days)
- Result: IS Sharpe **0.965**, Ann +39.3%, DD 32.1%. WF **4/6** (mean 1.482). SH **0.731/1.321 PASS**. Param robust **60/60 (100%)**, best 1.843. Corr **0.054** H-012 — near-zero.
- Notes: Captures volume trend / flow-of-funds signal. 100% param robust. Near-zero H-012 correlation = excellent diversifier. Corr H-076 -0.212 (negative = anti-correlated). One of the best diversifiers found.
- Sessions: [2026-04-10 session 178]

## H-602: Momentum Quality Factor
- Status: REJECTED
- Idea: Rolling 30d return / volatility (risk-adjusted momentum) as XS signal.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.723, Ann +29.0%, DD 39.1%. WF 4/6 but mean -0.218 (FAIL). Corr 0.614 H-012.
- Notes: Passes IS but WF mean is negative (last folds strongly negative). SH 1.50/-0.23 fail. High H-012 corr.
- Sessions: [2026-04-10 session 178]

## H-603: BTC Beta Change Factor
- Status: REJECTED
- Idea: Change in rolling beta vs BTC over 30d. Rising beta = increasing market sensitivity.
- Instrument: 13 non-BTC crypto perps
- Timeframe: 1D
- Result: IS Sharpe -0.225, Ann -10.8%, DD 66.0%.
- Notes: Beta dynamics have no XS predictive power. Direction of beta change doesn't predict returns.
- Sessions: [2026-04-10 session 178]

## H-604: 4h Momentum Persistence
- Status: REJECTED
- Idea: % of 4h bars matching daily direction over 10d as XS ranking.
- Instrument: 14 crypto perps
- Timeframe: 4h → 1D
- Result: IS Sharpe -0.796, Ann -27.6%, DD 67.7%.
- Notes: Intraday-to-daily consistency has negative predictive power. Coins with consistent 4h direction underperform.
- Sessions: [2026-04-10 session 178]

## H-605: Hourly Volume Clustering (HHI)
- Status: REJECTED
- Idea: Herfindahl index of hourly dollar volume within each day, averaged over 14d.
- Instrument: 14 crypto perps
- Timeframe: 1h → 1D
- Result: IS Sharpe 0.597, Ann +22.5%, DD 37.2%. Corr -0.067 H-012. Below threshold.
- Notes: Volume concentration captures some institutional flow but insufficient edge. Near-zero H-012 corr is interesting.
- Sessions: [2026-04-10 session 178]

## H-606: Close Location Value (CLV)
- Status: CONFIRMED (not deployed — redundant with H-451)
- Idea: Average (close-low)/(high-low) - 0.5 over 15d as XS factor. High = closes near highs.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe **1.260**, Ann +53.4%, DD 32.6%. WF **5/6** (mean 1.854). SH 1.260/1.294 PASS. Param 75%. Corr 0.327 H-012.
- Notes: Strong signal — essentially identical to H-451 (Close-to-High Ratio). PnL corr 0.691 with H-451 (already deployed), factor corr ~0.68 per asset. CONFIRMED standalone but NOT deployed. Redundant.
- Sessions: [2026-04-10 session 178]

## H-607: Intraday Trend Score
- Status: REJECTED
- Idea: Signed R² of hourly price regression within each day, averaged over 10d.
- Instrument: 14 crypto perps
- Timeframe: 1h → 1D
- Result: IS Sharpe 0.195, Ann +7.5%, DD 46.5%.
- Notes: Intraday trend quality (R²) doesn't predict next-day XS returns.
- Sessions: [2026-04-10 session 178]

## H-608: Late-Day Volume Share
- Status: REJECTED
- Idea: Share of dollar volume after 18:00 UTC averaged over 14d.
- Instrument: 14 crypto perps
- Timeframe: 1h → 1D
- Result: IS Sharpe 0.678, Ann +25.2%, DD 35.2%. Corr 0.258 H-012. Close but below threshold.
- Notes: Late-day volume concentration captures some institutional signal but insufficient edge. SH 0.71/0.67 passes.
- Sessions: [2026-04-10 session 178]

## H-609: Price Smoothness Factor
- Status: REJECTED
- Idea: Ratio of net price change to gross path length over 30d.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.633, Ann +24.4%, DD 28.8%. Corr 0.261 H-012. Below threshold.
- Notes: Similar concept to H-076 (efficiency) but different lookback. Near-zero H-076 corr would need to be checked. IS below threshold.
- Sessions: [2026-04-10 session 178]

## H-610: Dollar Volume Acceleration
- Status: REJECTED
- Idea: Change in short/long volume ratio over time.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.398, Ann +15.0%, DD 45.4%. Corr -0.147 H-012.
- Notes: Second-order volume dynamics have insufficient predictive power. SH -0.41/1.46 unstable.
- Sessions: [2026-04-10 session 178]

## H-611: Signed Volume Momentum
- Status: REJECTED
- Idea: Net buy pressure (CLV-weighted volume) accumulated over 20d as XS signal.
- Instrument: 14 crypto perps
- Timeframe: 1D
- Result: IS Sharpe 0.274, Ann +10.6%, DD 33.7%. Corr 0.455 H-012.
- Notes: Buy/sell volume decomposition based on close-location has weak edge. Too correlated with momentum.
- Sessions: [2026-04-10 session 178]

## H-612: BTC 4h EMA Crossover
- Status: REJECTED
- Idea: EMA(12/48) crossover on 4-hour BTC bars.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.073, Ann -8.7%, DD 55.2%.
- Notes: 4h EMA crossover is pure noise. Daily version (H-009) marginally better.
- Sessions: [2026-04-11 session 179]

## H-613: BTC 4h RSI Trend
- Status: REJECTED
- Idea: RSI(14) above/below 55/45 thresholds on 4h bars as trend signal.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.200, Ann -1.3%, DD 48.8%.
- Notes: RSI thresholds on 4h have no predictive power for BTC. Too many false signals.
- Sessions: [2026-04-11 session 179]

## H-614: BTC 4h Donchian Breakout
- Status: REJECTED
- Idea: Buy/sell on breakout above/below 48-bar (8-day) Donchian channel.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.621, Ann +20.4%, DD 50.6%. WF 6/8, SH PASS (0.661/0.728). Param robust only 4/6 (67%).
- Notes: Close to threshold but param robustness too low. Borderline signal.
- Sessions: [2026-04-11 session 179]

## H-615: BTC 4h MACD Trend
- Status: REJECTED
- Idea: Classic MACD(12,26,9) signal crossover on 4h bars.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.003, Ann -11.8%, DD 64.7%.
- Notes: MACD on 4h crypto is pure noise. Indicator was designed for daily equities.
- Sessions: [2026-04-11 session 179]

## H-616: BTC 4h Keltner Breakout
- Status: REJECTED
- Idea: Keltner Channel (EMA20 +/- 2.0*ATR) breakout on 4h bars.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.708, Ann +25.8%, DD 61.0%. Param robust 15/16 (94%). WF 4/8, SH FAIL (-0.106/0.004).
- Notes: Borderline — strong IS and param robustness but SH test fails. Most recent folds are negative.
- Sessions: [2026-04-11 session 179]

## H-617: BTC 4h Volume Breakout
- Status: LIVE (paper trade since 2026-04-11)
- Idea: Long when 12-bar (48h) momentum positive AND volume surges >1.5x its 48-bar MA. Short on reverse. Holds until opposite signal.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Logic: Price momentum + volume confirmation. Volume surge filters out weak momentum signals. Position held via forward-fill until next vol surge in opposite direction.
- Result: IS Sharpe 0.971, Ann +43.6%, DD 53.4%. WF 6/8 positive (mean 0.425). SH PASS (H1=0.425, H2=0.575). Param robust 14/16 (88%). Corr 0.292 with H-009 (moderate).
- Notes: First confirmed 4h timeframe strategy. Volume confirmation is key — without it, momentum is noise at 4h. Negative corr with BTC buy-hold (-0.190).
- Sessions: [2026-04-11 session 179]

## H-618: BTC 4h Bollinger Band Mean Reversion
- Status: REJECTED
- Idea: Buy at lower BB, sell at upper BB on 4h bars.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe -0.400, Ann -27.9%, DD 90.7%.
- Notes: Mean reversion universally fails in crypto at all timeframes. Confirmed again at 4h.
- Sessions: [2026-04-11 session 179]

## H-619: BTC 4h Adaptive Momentum
- Status: REJECTED
- Idea: Momentum signal with dynamic lookback scaled by inverse vol ratio. Flat in high vol.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe -0.141, Ann -15.0%, DD 71.7%.
- Notes: Vol-adaptive momentum doesn't work — the high-vol periods that get filtered out are exactly when momentum signals are strongest.
- Sessions: [2026-04-11 session 179]

## H-620: ETH 4h Volume Breakout
- Status: REJECTED
- Idea: H-617 volume breakout signal applied to ETH instead of BTC.
- Instrument: futures (ETH/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.619, Ann +21.0%, DD 68.0%. WF 6/8, SH PASS (0.839/1.092).
- Notes: Below IS threshold (0.7). The signal works better on BTC — ETH has more noise at 4h.
- Sessions: [2026-04-11 session 179]

## H-621: SOL 4h Volume Breakout
- Status: REJECTED
- Idea: H-617 volume breakout signal applied to SOL.
- Instrument: futures (SOL/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.778, Ann +33.1%, DD 69.3%. WF only 3/8. SH FAIL (0.050/-0.139).
- Notes: SOL's 4h volume breakout is too unstable — recent folds deeply negative. Asset too volatile for this signal.
- Sessions: [2026-04-11 session 179]

## H-622: Multi-Asset 4h Volume Breakout (BTC+ETH+SOL)
- Status: CONFIRMED (NOT deployed — redundant with H-617)
- Idea: Equal-weight portfolio of H-617 applied to BTC, ETH, SOL simultaneously.
- Instrument: futures (BTC/ETH/SOL perps)
- Timeframe: 4h
- Result: IS Sharpe 1.001, Ann +49.1%, DD 42.3%. WF 5/8, SH PASS (0.481/0.471). Param robust 16/16 (100%). Corr 0.724 with H-617.
- Notes: Best IS Sharpe of the batch and 100% param robust. But 0.724 correlation with H-617 (BTC only) means most signal is shared — adding ETH/SOL provides marginal diversification.
- Sessions: [2026-04-11 session 179]

## H-623: BTC 4h Donchian + Volume Filter
- Status: REJECTED
- Idea: Donchian breakout filtered by volume surge (only enter when volume confirms).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.563, Ann +16.9%, DD 47.8%. WF 6/8, SH PASS (0.444/0.493).
- Notes: Volume filter improves Donchian but not enough. IS below 0.7 threshold.
- Sessions: [2026-04-11 session 179]

## H-624: BTC Funding Rate Reversal
- Status: REJECTED
- Idea: Short BTC when funding rate z-score > 1.5 (crowded longs), long when < -1.5.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -1.062, Ann -15.9%, DD 33.5%. Only 709 days of data.
- Notes: Contrarian funding rate timing is a losing strategy — high funding coincides with uptrends.
- Sessions: [2026-04-11 session 179]

## H-625: BTC Funding Momentum
- Status: REJECTED
- Idea: Trend-follow funding rate direction (rising funding = bullish).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.320, Ann +4.1%, DD 69.9%. Only 709 days of data.
- Notes: Funding rate momentum has weak predictive power for price. Too noisy.
- Sessions: [2026-04-11 session 179]

## H-626: BTC Funding-Price Divergence
- Status: REJECTED
- Idea: Trade divergence between price trend (20d return) and funding rate change.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.081, Ann -13.2%, DD 56.7%. Only 709 days of data.
- Notes: Funding-price divergence has no edge. Funding follows price, not the other way around.
- Sessions: [2026-04-11 session 179]

## H-627: BTC OI Proxy Momentum
- Status: REJECTED
- Idea: Trend-follow BTC when OI proxy (abs funding rate * volume) is expanding above its 20d MA.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.877, Ann +26.3%, DD 24.9%. WF 4/5, SH PASS (1.433/1.475). But only 709 days of data.
- Notes: Promising results but only 2 years of funding data — insufficient for confidence. OI proxy is imperfect. Would need actual OI data and longer history. Worth revisiting with better data.
- Sessions: [2026-04-11 session 179]

## H-628: BTC Weekend Effect (4h)
- Status: REJECTED
- Idea: Long BTC on weekdays, short on weekends.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.608, Ann +19.6%, DD 55.4%.
- Notes: Borderline — weekend effect exists but too weak to trade profitably after costs. IS below threshold.
- Sessions: [2026-04-11 session 179]

## H-629: BTC 4h Session Pattern
- Status: REJECTED
- Idea: Long at best-performing 4h session (20:00 UTC), short at worst (16:00 UTC).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe -0.396, Ann -27.8%, DD 78.8%.
- Notes: Session-specific 4h signals are not tradable — too much noise within sessions. The mean differences (0.06% best vs -0.03% worst) are dwarfed by within-session variance.
- Sessions: [2026-04-11 session 179]

## H-630: BTC 4h Vol Compression Breakout
- Status: REJECTED
- Idea: Enter when BB width drops below 20th percentile (compression), use momentum for direction.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe -0.977, Ann -44.3%, DD 94.2%.
- Notes: Vol compression at 4h doesn't predict breakout direction. Signal enters at exactly the wrong time.
- Sessions: [2026-04-11 session 179]

## H-631: BTC Multi-TF Trend Alignment
- Status: REJECTED
- Idea: Trade only when 4h EMA trend agrees with 20-day price trend (above/below MA).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.419, Ann +9.0%, DD 41.7%.
- Notes: Multi-TF alignment adds filtering but doesn't improve Sharpe enough. The aligned periods miss too many profitable moves.
- Sessions: [2026-04-11 session 179]

## H-632: BTC 4h Momentum Reversal
- Status: REJECTED
- Idea: Fade overextended 4h moves (z-score > 2.0) by trading the reversal.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe -0.627, Ann -12.1%, DD 60.7%.
- Notes: Mean reversion / reversal does not work in crypto at any timeframe. Momentum persists through overextension.
- Sessions: [2026-04-11 session 179]

## H-633: BTC 4h ATR Trailing Stop
- Status: REJECTED
- Idea: Trend-follow with ATR-based trailing stop (3.0x ATR, 24-bar period).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.484, Ann +12.4%, DD 41.1%.
- Notes: Close to threshold but falls short. ATR trailing stop whipsaws too much on 4h — would need wider stops that defeat the purpose of 4h granularity.
- Sessions: [2026-04-11 session 179]

## H-634: BTC 4h Range Expansion Trend
- Status: REJECTED
- Idea: Trade when 4h bar range expands >1.5x its 48-bar avg, in the direction of the bar (close vs open).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe -0.121, Ann -17.2%, DD 77.6%.
- Notes: Range expansion at 4h is noise — expanded bars are followed by mean-reverting contractions, not continuation.
- Sessions: [2026-04-11 session 179]

## H-635: BTC 4h RSI-Volume Divergence
- Status: REJECTED
- Idea: Buy when RSI falling but volume rising (accumulation divergence), sell when RSI rising but volume falling.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.050, Ann -9.5%, DD 65.4%.
- Notes: RSI-volume divergence at 4h is not predictive. Volume dynamics don't reliably signal reversals at this frequency.
- Sessions: [2026-04-11 session 179]

## H-636: ETH 4h Volume Breakout
- Status: REJECTED
- Idea: H-617 (BTC 4h volume breakout) pattern applied to ETH.
- Instrument: futures (ETH/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe -0.006, Ann -21.5%, DD 85.9%.
- Notes: Volume breakout pattern is BTC-specific. ETH lacks the clean trend structure that BTC has at 4h.
- Sessions: [2026-04-11 session 180]

## H-637: SOL 4h Volume Breakout
- Status: REJECTED
- Idea: H-617 pattern applied to SOL.
- Instrument: futures (SOL/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.526 but DD 88.6% — risk-adjusted terrible.
- Notes: Marginal IS Sharpe but 88.6% DD makes it untradeable. SOL too volatile for 4h trend-following.
- Sessions: [2026-04-11 session 180]

## H-638: ETH 4h Keltner Breakout
- Status: REJECTED
- Idea: Keltner channel breakout on ETH 4h (like H-539 BTC variant).
- Instrument: futures (ETH/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.29, Ann -3.7%, DD 82.3%.
- Notes: ETH 4h has no channel breakout edge. Whipsaws dominate.
- Sessions: [2026-04-11 session 180]

## H-639: DOGE 4h Momentum
- Status: REJECTED
- Idea: 48-bar momentum signal on DOGE 4h.
- Instrument: futures (DOGE/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.012, Ann -36.8%, DD 94.7%.
- Notes: DOGE 4h momentum is pure noise. High-beta meme coin has no short-term trend persistence.
- Sessions: [2026-04-11 session 180]

## H-640: XRP 4h Range Squeeze
- Status: REJECTED
- Idea: BB/KC squeeze breakout on XRP 4h.
- Instrument: futures (XRP/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe -0.377, Ann -48.1%, DD 99.4%.
- Notes: XRP squeeze breakouts fail catastrophically. Compression leads to random direction, not predictable breakout.
- Sessions: [2026-04-11 session 180]

## H-641: AVAX 4h ATR Trailing Trend
- Status: REJECTED
- Idea: ATR trailing stop trend following on AVAX 4h.
- Instrument: futures (AVAX/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.285, Ann -18.1%, DD 83.6%.
- Notes: ATR trailing stop doesn't work for AVAX at 4h. Alt 4h TS confirmed as dead-end across the board.
- Sessions: [2026-04-11 session 180]

## H-642: LINK 4h Volume Breakout
- Status: REJECTED
- Idea: H-617 pattern applied to LINK — mid-cap DeFi.
- Instrument: futures (LINK/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe -0.619, Ann -62.0%, DD 99.0%.
- Notes: Strongly negative — LINK volume patterns are contrarian to momentum at 4h.
- Sessions: [2026-04-11 session 180]

## H-643: NEAR 4h Keltner Breakout
- Status: REJECTED
- Idea: Keltner channel breakout on NEAR 4h.
- Instrument: futures (NEAR/USDT perp)
- Timeframe: 4h
- Result: IS Sharpe 0.598, Ann 8.8%, DD 92.0%. WF errored (borderline regardless with 92% DD).
- Notes: Marginal Sharpe with extreme DD. 4h Keltner works for BTC only.
- Sessions: [2026-04-11 session 180]

## H-644: ETH Daily Volume Breakout
- Status: REJECTED (BORDERLINE)
- Idea: Volume breakout on ETH daily (mom_period=10, vol_mult=1.5).
- Instrument: futures (ETH/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.569, WF 4/6, SH FAIL (H1=-0.098, H2=1.279).
- Notes: Daily volume breakout passes IS but fails SH first half — recent pattern only. Not robust across full sample.
- Sessions: [2026-04-11 session 180]

## H-645: SOL Daily Volume Breakout
- Status: REJECTED
- Idea: Volume breakout on SOL daily.
- Instrument: futures (SOL/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.17, Ann -25.1%, DD 90.1%.
- Notes: SOL daily volume breakout fails. Volume patterns on SOL are noise.
- Sessions: [2026-04-11 session 180]

## H-646: BTC Funding Rate TS (Contrarian)
- Status: REJECTED
- Idea: Trade BTC based on its own funding rate momentum (9/27 MA crossover, contrarian).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D (signal from 8h funding)
- Result: IS Sharpe -0.664, Ann -23.1%, DD 55.2%. Only 667 bars (~2yr).
- Notes: Individual coin funding rate contrarian doesn't work. Funding rates are not mean-reverting enough.
- Sessions: [2026-04-11 session 180]

## H-647: ETH Funding Rate TS (Contrarian)
- Status: REJECTED
- Idea: Trade ETH based on its own funding rate momentum (contrarian).
- Instrument: futures (ETH/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.002, Ann -14.3%, DD 61.6%.
- Notes: ETH funding rate TS also fails. No individual coin funding rate edge.
- Sessions: [2026-04-11 session 180]

## H-648: BTC OI Change TS
- Status: REJECTED (ERROR)
- Idea: Trade based on OI changes — rising OI + price trend = continuation.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: Error — OI data format issue. Would have tested OI/price confirmation.
- Notes: OI data needs index alignment fix. Concept tested in XS as H-044/H-193.
- Sessions: [2026-04-11 session 180]

## H-649: BTC Vol Regime Switch
- Status: REJECTED
- Idea: Trade BTC differently in high vs low vol regimes. Low vol: buy dips. High vol: momentum.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.43, Ann 9.5%, DD 47.8%.
- Notes: Close to threshold but regime identification doesn't add value over pure momentum. Tested in H-497–H-504 range previously.
- Sessions: [2026-04-11 session 180]

## H-650: BTC Intraday Volume Distribution Pattern
- Status: REJECTED
- Idea: Trade based on late vs early session volume ratio (rising late-session volume = bullish).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.836, Ann -36.1%, DD 90.1%.
- Notes: Intraday volume distribution is not predictive of next-day direction. Strongly negative.
- Sessions: [2026-04-11 session 180]

## H-651: Multi-Coin Aggregate Funding Contrarian
- Status: REJECTED
- Idea: Contrarian on aggregate funding across BTC/ETH/SOL/DOGE/XRP. Trade BTC when aggregate funding extreme.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.046, Ann -1.6%, DD 33.6%.
- Notes: Aggregate funding provides no edge. Already tested as XS in H-053 (which works). TS version fails.
- Sessions: [2026-04-11 session 180]

## H-652: ETH/BTC Ratio Momentum
- Status: REJECTED
- Idea: Trade BTC based on ETH/BTC ratio trend (rising ratio = risk-on = long BTC).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.183, Ann -21.2%, DD 83.9%.
- Notes: ETH/BTC ratio momentum provides no edge for trading BTC directionally.
- Sessions: [2026-04-11 session 180]

## H-653: ETH/BTC Ratio Mean-Reversion
- Status: REJECTED
- Idea: Mean-revert on ETH/BTC ratio — extreme deviation signals BTC reversal.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.484, Ann 12.0%, DD 45.7%.
- Notes: Close to threshold (0.484 vs 0.5). The ratio does weakly mean-revert but not enough for a standalone strategy.
- Sessions: [2026-04-11 session 180]

## H-654: BTC Monthly Calendar Effect
- Status: REJECTED
- Idea: Day-of-month effects — long month-start/end, short mid-month.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.022, Ann -4.6%, DD 54.8%.
- Notes: No monthly calendar effect in BTC. Already tested DOW effect (H-039 works); monthly is different and doesn't exist.
- Sessions: [2026-04-11 session 180]

## H-655: BTC Vol-of-Vol Signal
- Status: REJECTED
- Idea: Low vol-of-vol = stable trend regime (trade momentum), high VoV = choppy (stay flat).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.491, Ann -17.0%, DD 70.1%.
- Notes: Vol-of-vol doesn't predict tradeable regimes. The regime identification adds noise rather than filtering.
- Sessions: [2026-04-11 session 180]

## H-656: Multi-TF BTC Confirmation (Daily + 4h)
- Status: REJECTED
- Idea: Long only when daily AND 4h signals agree (daily momentum + 4h volume breakout).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D+4h
- Result: IS Sharpe 0.281, Ann 2.8%, DD 50.1%.
- Notes: Multi-TF confirmation reduces signal quality rather than improving it. Disagreement periods (which are filtered out) contain edge. Revisited from H-572 (similar finding). Multi-TF is a dead end.
- Sessions: [2026-04-11 session 180]

## H-657: BTC Realized Skew
- Status: LIVE (paper trade since 2026-04-11)
- Idea: Trade BTC based on 30-day realized skew of returns. Positive skew (>0.5) → long, negative (<-0.5) → short.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Logic: Compute scipy skew of 30-day return window. Positive skew = upside bias = long. Negative skew = crash risk = short. Between thresholds = flat.
- Data: BTC daily, 1742 bars (~4.8 years).
- Result:
  - **IS**: Sharpe **0.947**, Ann +32.5%, DD 48.1%, 122 trades.
  - **WF**: 5/6 positive (mean ~1.46). Folds: [0.0, 1.224, 2.768, 1.190, 2.224, 1.365].
  - **SH**: PASS (H1=0.624, H2=1.524).
  - **Param robust**: **98%** (48/49 positive, lookback 15-60, threshold 0.3-1.0).
  - **H-012 PnL corr**: **0.052** (near zero — excellent diversifier for XS strategies).
  - **H-009 PnL corr**: 0.404 (moderate overlap with BTC trend).
  - **BTC direction corr**: 0.120 (low).
  - **Signal**: Long 30%, Short 15%, Flat 55% (long bias).
- Notes: Captures return distribution shape — different from momentum or vol signals. Best new single-asset TS strategy found since H-617. Deployed 2026-04-11.
- Sessions: [2026-04-11 session 180]

## H-658: Cross-Sectional Momentum at 4h
- Status: REJECTED (BORDERLINE)
- Idea: H-012 XS momentum at 4h frequency (48-bar lookback, rebal every 6 bars).
- Instrument: futures (14 perps)
- Timeframe: 4h
- Result: IS Sharpe 0.697, Ann 22.7%, DD 51.6%. SH PASS (0.612/1.075). WF 5/7. H-012 corr 0.306.
- Notes: Higher-frequency version of H-012. Works but adds noise and complexity. Much higher turnover = more fees. Not worth deploying separately when H-012 daily version is superior and already running.
- Sessions: [2026-04-11 session 180]

## H-659: BTC Dominance Proxy
- Status: REJECTED
- Idea: Trade BTC based on relative performance vs ETH+SOL (dominance proxy).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.353, Ann -19.4%, DD 82.0%.
- Notes: BTC dominance changes are not predictive of BTC direction. Relative performance is noise at daily frequency.
- Sessions: [2026-04-11 session 180]

## H-660: BTC Realized Kurtosis
- Status: REJECTED
- Idea: Trade direction based on realized kurtosis (fat tails indicator).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.143, Ann -0.5%, DD 49.6%.
- Notes: Kurtosis doesn't predict direction. Fat tails indicate regime uncertainty but not tradeable bias.
- Sessions: [2026-04-11 session 180]

## H-661: BTC Tail Ratio
- Status: REJECTED
- Idea: Ratio of right vs left tail magnitude (5th/95th percentile) as directional signal.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.234, Ann 2.0%, DD 59.1%.
- Notes: Tail ratio has weak directional content. Right tail dominance is weakly bullish but not enough for standalone edge.
- Sessions: [2026-04-11 session 180]

## H-662: BTC Hurst Exponent
- Status: REJECTED
- Idea: Hurst exponent to classify trending vs mean-reverting regimes.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.942, Ann -26.0%, DD 79.5%.
- Notes: Strongly negative. R/S Hurst estimation is too noisy at 100-day lookback. Regime classification based on Hurst fails decisively.
- Sessions: [2026-04-11 session 180]

## H-663: BTC Return Autocorrelation
- Status: REJECTED
- Idea: Positive autocorrelation = trend (follow), negative = mean-revert (contrarian).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.315, Ann 4.7%, DD 61.1%.
- Notes: Autocorrelation-based regime switching marginally positive but well below threshold. BTC autocorrelation is too unstable for reliable regime identification.
- Sessions: [2026-04-11 session 180]

## H-664: ETH Realized Skew
- Status: REJECTED
- Idea: H-657 realized skew signal applied to ETH.
- Instrument: futures (ETH/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.189, Ann -1.8%, DD 72.8%.
- Notes: Realized skew is BTC-specific. ETH return distribution shape is not predictive of future direction. Key finding: skew edge exists in BTC's unique market microstructure (institutional flow, miner dynamics).
- Sessions: [2026-04-11 session 180]

## H-665: SOL Realized Skew
- Status: REJECTED (BORDERLINE)
- Idea: H-657 realized skew signal applied to SOL.
- Instrument: futures (SOL/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.796, Ann 35.3%, DD 65.4%. WF 4/6. SH FAIL (H1=1.489, H2=-0.158). H-657 corr 0.364.
- Notes: SOL skew has some signal in first half but fails in second half. Not robust. Slightly correlated with BTC skew.
- Sessions: [2026-04-11 session 180]

## H-666: Multi-Asset Skew Portfolio (BTC+ETH+SOL)
- Status: CONFIRMED (NOT deployed — inferior to H-657)
- Idea: Equal-weight portfolio of realized skew signals across BTC, ETH, and SOL.
- Instrument: futures (BTC, ETH, SOL perps)
- Timeframe: 1D
- Result: IS Sharpe 0.887, Ann 30.0%, DD 43.1%. SH PASS (1.130/0.584).
- Notes: Portfolio Sharpe (0.887) is lower than BTC-only (0.947). Adding ETH (0.189) and SOL (borderline) dilutes the BTC signal. Better to run H-657 alone. Lower DD (43.1% vs 48.1%) is the only advantage but not enough to justify complexity.
- Sessions: [2026-04-11 session 180]

## H-667: BTC Skew + Momentum Combined
- Status: REJECTED
- Idea: Trade only when skew AND momentum agree (both positive → long, both negative → short).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.492, Ann 12.2%, DD 53.7%.
- Notes: Requiring momentum confirmation reduces the skew signal quality. The additional filter removes good trades (when skew and momentum disagree but skew is right).
- Sessions: [2026-04-11 session 180]

## H-668: BTC Turn-of-Month Momentum
- Status: REJECTED
- Idea: Buy BTC on day 28-2 of month (turn-of-month effect). Calendar timing strategy.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe **-1.464**. All param variants negative (d27-d3: -1.53, d28-d2: -1.46, d29-d1: -0.98, d26-d4: -1.95).
- Notes: Turn-of-month effect does NOT exist in BTC. Strongly negative — anti-pattern.
- Sessions: [2026-04-11 session 181]

## H-669: Week-of-Month XS Momentum
- Status: REJECTED
- Idea: Run cross-sectional momentum only during the "best" week of each month.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: Week 1 Sharpe 2.73, Week 2: -0.10, Week 3: 0.53, Week 4: -1.07, Week 5: 7.39. Highly variable — data-mined selection.
- Notes: Week 5 has very few data points (inflated Sharpe). Selecting specific weeks is overfitting.
- Sessions: [2026-04-11 session 181]

## H-670: BTC Options Expiry Week Effect
- Status: REJECTED
- Idea: Short BTC on Friday (expiry pinning), long on weekend (post-expiry expansion).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: No statistically significant day-of-week effects. Thu most negative (mean -0.42%, p=0.126) but not significant. Already captured by H-039 DOW.
- Notes: Options expiry doesn't create a tradable pattern at daily level.
- Sessions: [2026-04-11 session 181]

## H-671: BTC Funding Settlement Alpha
- Status: REJECTED
- Idea: Trade BTC around 8h funding settlement times (00:00/08:00/16:00 UTC). Trade significant hours.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1h
- Result: Sharpe 0.230. WF 3/6. SH 0.156/0.330. Only Hour 22 significant (p=0.003). Strategy too weak.
- Notes: Hour 22 (0.04%/hr) is significant but hourly alpha is too small to trade profitably. Already known from H-037 analysis.
- Sessions: [2026-04-11 session 181]

## H-672: BTC Weekend Drift
- Status: REJECTED
- Idea: Long weekend, short weekday (or vice versa). Weekend vs weekday differential.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: Sharpe 0.406. WF 3/5. SH -0.455/1.408 (FAIL — first half negative).
- Notes: Weekend mean -0.01%, weekday +0.05%, diff not significant (p=0.756). Split-half failure.
- Sessions: [2026-04-11 session 181]

## H-673: Intra-Month Seasonality XS
- Status: REJECTED
- Idea: Rank assets by historical seasonal return pattern for current part of month (early/mid/late).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: Sharpe 0.518. WF 1/3. SH -0.115/1.536 (FAIL — first half negative).
- Notes: Walk-forward failure. Intra-month seasonal patterns are not stable enough for cross-sectional ranking.
- Sessions: [2026-04-11 session 181]

## H-674: BTC Quarterly Options Expiry Effect
- Status: REJECTED
- Idea: Long BTC for 3 days after quarterly options expiry (last Friday of Mar/Jun/Sep/Dec).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: 3-day post-expiry mean +0.15%, t=0.15, p=0.885. N=8 (insufficient data).
- Notes: Only 8 quarterly expiries in 2 years. No effect. Insufficient sample size.
- Sessions: [2026-04-11 session 181]

## H-675: BTC Monthly Momentum
- Status: REJECTED
- Idea: Long BTC if prior N months positive, short if negative. Monthly time-series momentum.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D (monthly signal)
- Result: Best 6mo lookback: Sharpe 0.680. WF 2/3. SH 1.774/-0.454 (FAIL — second half negative).
- Notes: All lookbacks (1mo: 0.32, 2mo: 0.30, 3mo: 0.50, 6mo: 0.68) below threshold. Split-half failure on best.
- Sessions: [2026-04-11 session 181]

## H-676: BTC Consecutive Day Contrarian
- Status: CONFIRMED (deployed session 181)
- Idea: After 3+ consecutive up days, short BTC. After 3+ consecutive down days, long BTC. Mean reversion.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Logic: Count consecutive up/down days. Signal triggers when streak >= 3. Contrarian direction.
- Result:
  - **Full Sharpe: 1.308**, Active Sharpe: 2.708
  - **Ann return: 30.3%**, Max DD: -17.0%
  - **Walk-forward: 5/5 positive** (0.754, 2.493, 4.245, 0.004, 3.079) — PERFECT
  - **Split-half: 0.674/2.219** — PASS
  - **Param robustness: 4/4 (100%)** — 2d (0.739), 3d (1.308), 4d (0.606), 5d (0.651)
  - **Exposure: 23.6%** (flat ~76% of the time)
  - **Correlation: H-012=-0.039, H-009=-0.154** — excellent diversifier
- Notes: Pure mean-reversion BTC signal. Negative correlation with both momentum and trend strategies. Low exposure makes it a good overlay. 173 active trade days in 2 years.
- Sessions: [2026-04-11 session 181]

## H-677: BTC Crash Bounce
- Status: CONFIRMED (deployed session 181)
- Idea: Buy BTC after a >3% daily drop, hold for 2 days. Post-crash mean reversion.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Logic: If yesterday's return < -3%, go long for 2 days. Otherwise flat.
- Result:
  - **Active Sharpe: 1.610**, Full Sharpe: 0.657
  - **Walk-forward: 5/5 positive** (1.526, 0.573, 3.433, 2.961, 0.443) — PERFECT
  - **Split-half: 0.731/0.582** — PASS
  - **Param robustness: 16/20 (80%)**
  - **Exposure: 16.6%** (only active after crashes)
  - **Correlation: H-012=-0.166, H-009=-0.455** — strongly negative with trend
- Notes: Excellent diversifier due to strong negative correlation with H-009 trend. Works because crypto crashes tend to overshoot and mean-revert within 2 days. 122 active trade days in 2 years.
- Sessions: [2026-04-11 session 181]

## H-678: Multi-Lookback Momentum XS
- Status: REJECTED
- Idea: Combine 5d+60d momentum z-scores as composite XS factor.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: Best (5,60) Sharpe 1.246. Just a variant of H-012 with mixed lookbacks. Not sufficiently different.
- Notes: Composite of (5,60) beats (20,60) and (5,20,60). But Sharpe improvement over H-012 (1.11) is marginal and likely due to parameter mining.
- Sessions: [2026-04-11 session 181]

## H-679: BTC Vol Regime Switch
- Status: CONFIRMED (deployed session 181)
- Idea: Follow BTC 5d trend when vol expanding (5d/30d ratio > 1). Fade trend when contracting.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Logic: Short vol (5d) / long vol (30d) ratio determines regime. Momentum in high vol, contrarian in low vol.
- Result:
  - **Sharpe: 1.464**, Ann: 68.8%, Max DD: -30.1%
  - **Walk-forward: 4/5 positive** (4.531, 1.340, 0.959, 1.904, -0.162)
  - **Split-half: 1.825/1.042** — STRONG PASS
  - **Param robustness: 21/24 (88%)**
  - **Correlation: H-012=0.023, H-009=0.241, H-676=0.101**
- Notes: Strongest BTC TS strategy found yet. Always in position. Near-zero H-012 correlation. Moderate H-009 correlation (0.241) but fundamentally different signal (vol regime vs trend). Key insight: momentum works in vol expansions, contrarian works in vol contractions.
- Sessions: [2026-04-11 session 181]

## H-680: Return-Volume Convergence XS
- Status: CONFIRMED (deployed session 181)
- Idea: Long assets where price AND volume move together (confirmed momentum). Short where both decline.
- Instrument: futures (14 perps)
- Timeframe: 1D, 3-day rebalance
- Logic: Z-score price momentum + volume momentum. Rank composite. L4/S4.
- Result:
  - **Sharpe: 1.486** (LB20_N4_R3)
  - **Walk-forward: 4/5 positive**
  - **Split-half: 1.835/1.039** — PASS
  - **Param robustness: 27/30 (90%)**
  - **Correlation: H-012=0.264** — moderate but acceptable
- Notes: Volume-confirmed momentum is a genuine signal improvement over pure price momentum. The volume confirmation reduces false signals. 3-day rebalance is more frequent than H-012 (5d). H-012 corr 0.264 shows they capture different aspects of momentum.
- Sessions: [2026-04-11 session 181]

## H-681: Rolling Correlation Alpha XS
- Status: REJECTED
- Idea: Trade assets decorrelating/recorrelating with BTC.
- Instrument: futures (13 non-BTC perps)
- Timeframe: 1D
- Result: LB20 decorrelating Sharpe 1.957 but recorrelating has -1.957 (perfect mirror). Only 2/6 param combos have consistent direction. Not robust.
- Notes: The signal is purely directional — same signal with opposite sign produces exactly opposite results. This means it's capturing market direction, not a real factor.
- Sessions: [2026-04-11 session 181]

## H-682: PCA Residual Momentum XS
- Status: REJECTED
- Idea: Market-factor-neutral momentum using PCA residuals.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: Max Sharpe 0.774 (LB60). All n_components give identical results (suspicious). Below 0.8 threshold.
- Notes: PCA doesn't add value — the market factor in crypto is so dominant that residual momentum is noise.
- Sessions: [2026-04-11 session 181]

## H-683: BTC Gap-and-Follow TS
- Status: REJECTED
- Idea: If first 4h candle is positive, hold long for rest of day (intraday momentum continuation).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 4h/1D
- Result: Best 4h_follow Sharpe 0.287. WF 4/6. SH 0.619/-0.098 (FAIL — second half negative).
- Notes: Intraday continuation signal is weak at 4h level. Already captured better by H-535 (6h intraday session momentum).
- Sessions: [2026-04-11 session 181]

## H-684: Gold-Crypto Correlation XS
- Status: REJECTED
- Idea: Rank crypto by rolling correlation with gold (XAUT). Long low-corr (risk-on), short high-corr.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.061, Ann -0.4%, DD -17.0%. WF 0/4. Params 2/8 (25%). H-012 corr 0.107.
- Notes: Gold-crypto correlation has no cross-sectional predictive power. Only 365 days common data (XAUT listed Apr 2025).
- Sessions: [2026-04-11 session 182]

## H-685: Gold Momentum Regime Filter XS
- Status: REJECTED
- Idea: When gold trending up (risk-off), favor low-vol crypto. When down, favor high-vol.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.021, Ann -2.4%, DD -22.7%. WF 4/4 (but IS is noise). Params 7/9 (78%).
- Notes: Gold momentum doesn't differentiate crypto cross-section. Regime switching is noise.
- Sessions: [2026-04-11 session 182]

## H-686: Gold/BTC Ratio Momentum XS
- Status: REJECTED
- Idea: Use gold/BTC ratio momentum to select high/low beta crypto positions.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -1.593, Ann -28.0%, DD -29.2%. WF 0/3. Params 2/6 (33%).
- Notes: Strongly negative Sharpe — gold/BTC ratio is counterproductive as XS signal.
- Sessions: [2026-04-11 session 182]

## H-687: Gold Return Predicts Crypto XS
- Status: REJECTED
- Idea: Gold returns today predict crypto cross-section tomorrow (via asset sensitivity to gold).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.900, Ann -16.3%, DD -18.4%. WF 1/3. Params 4/6 (67%).
- Notes: Gold returns have zero predictive power for next-day crypto cross-section.
- Sessions: [2026-04-11 session 182]

## H-688: Gold Vol Spillover XS
- Status: REJECTED
- Idea: Gold vol spikes predict crypto vol — position for it by ranking assets by volatility.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.121 (marginal), Ann 26.6%, DD -14.6%. WF 1/3. SH FAIL (corrected t-test). Params 7/9 (78%).
- Notes: Promising IS but fails WF badly. Gold vol spillover to crypto is inconsistent.
- Sessions: [2026-04-11 session 182]

## H-689: Gold-Crypto Correlation Regime Switch XS
- Status: REJECTED
- Idea: Switch between momentum and mean-reversion XS based on gold-crypto correlation regime.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -1.419, Ann -21.5%, DD -26.4%. WF 1/3. Params 0/9 (0%).
- Notes: Gold-crypto correlation is not a useful regime indicator. Zero param robustness.
- Sessions: [2026-04-11 session 182]

## H-690: Gold-Adjusted Momentum XS
- Status: REJECTED
- Idea: Residual momentum after hedging out gold beta (pure crypto alpha momentum).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.485. Params 12/12 (100%). BUT H-012 signal corr 0.949 — identical to plain momentum.
- Notes: Gold beta in crypto is negligible. Hedging it out doesn't change the signal. Redundant with H-012.
- Sessions: [2026-04-11 session 182]

## H-691: Gold Hedging Demand Proxy XS
- Status: REJECTED
- Idea: Strong gold returns = flight to safety → short high-BTC-beta crypto, long low-beta.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.148, Ann 22.4%, DD -10.0%. WF 4/4 (mean 1.634). Params 12/12 (100%). SH FAIL (corrected). H-012 corr -0.114.
- Notes: Promising WF and params but SH FAIL with corrected test. Only 336 days data limits statistical power. Worth revisiting when XAUT has 2+ years of data.
- Sessions: [2026-04-11 session 182]

## H-692: Taker Volume Proxy XS
- Status: REJECTED
- Idea: Approximate buy/sell pressure from OHLCV ((close-low)/(high-low) * volume). Rank by rolling buy pressure.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.924 (raw) → -0.252 (lagged). LOOK-AHEAD BIAS. WF 3/6 (lagged). Params 5/7 (71% lagged).
- Notes: CRITICAL: IS Sharpe was 1.924 using same-day data. Drops to -0.252 when signal lagged by 1 day. Entire signal was look-ahead bias. Same-day OHLCV → same-day return prediction is a classic pitfall.
- Sessions: [2026-04-11 session 182]

## H-693: Range Compression XS
- Status: REJECTED
- Idea: Assets with narrowing daily ranges (compression) tend to break out.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -2.350, Ann -43.1%, DD -65.2%. WF 0/6. Params 0/9 (0%).
- Notes: Range compression is ANTI-predictive in crypto. Compressed assets actually underperform. Worst performer of this batch.
- Sessions: [2026-04-11 session 182]

## H-694: Volume-Adjusted Return XS
- Status: REJECTED
- Idea: Return per unit of dollar volume — measures price efficiency/conviction.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.218, Ann 2.4%, DD -22.1%. WF 2/6. Params 7/7 (100%).
- Notes: Weak signal. Return/volume has no cross-sectional predictive power despite 100% params. H-012 corr 0.427 (moderate momentum content).
- Sessions: [2026-04-11 session 182]

## H-695: Range Momentum XS
- Status: REJECTED (borderline)
- Idea: Rank by expanding range × return direction (range expansion + positive return = bullish).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 2.590 (raw) → 1.278 (lagged). SH PASS (t-test), FAIL (bootstrap). WF 2/6 (lagged). Params 9/9 (100%).
- Notes: Significant IS even after lag correction. But WF 2/6 kills it. Signal is partially look-ahead contaminated (short_w=5, today is 1/5 of signal). Low H-012 corr (0.222) = good diversifier. May revisit with stronger lag.
- Sessions: [2026-04-11 session 182]

## H-696: Return Efficiency XS
- Status: REJECTED
- Idea: Rank by |close-close_prev|/(high-low) × direction — efficient movers (high conviction) outperform.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.434. WF 3/6. SH FAIL (corrected). Params 5/6 (83%). H-012 corr 0.270.
- Notes: Fails both SH and WF. Direction-weighted efficiency has some signal but insufficient statistical significance.
- Sessions: [2026-04-11 session 182]

## H-697: Overnight Gap XS
- Status: REJECTED (borderline)
- Idea: Rank by cumulative overnight gap (open vs prev close). Assets with persistent gaps continue.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.666 (lagged). SH PASS (both t-test and bootstrap). WF 3/6 (mean 1.547). Params 7/7 (100%).
- Notes: Survives look-ahead correction (signal uses open-to-close, properly lagged). SH passes both tests. WF only 3/6 kills deployment. Mean WF Sharpe strong (1.547) — positive folds very strong, negative folds mild. PnL corr 0.411 with momentum (moderate). Revisit if more data or different WF structure.
- Sessions: [2026-04-11 session 182]

## H-698: 4h Momentum XS
- Status: REJECTED
- Idea: 4h cumulative momentum resampled to daily ranking for faster signal.
- Instrument: futures (14 perps)
- Timeframe: 4h → 1D
- Result: IS Sharpe 3.201 (raw) → 0.189 (lagged). MASSIVE LOOK-AHEAD BIAS.
- Notes: CRITICAL: Sharpe 3.201 was 100% look-ahead bias — last 4h bar includes most of same-day's return. After 1-day lag: Sharpe 0.189, WF 2/6, params 57%. Complete artifact. This is why 4h→daily resampling needs careful lag handling.
- Sessions: [2026-04-11 session 182]

## H-699: Multi-TF Momentum Composite XS
- Status: REJECTED
- Idea: Combine daily 60d momentum + 4h 30-bar momentum as composite XS signal.
- Instrument: futures (14 perps)
- Timeframe: 4h + 1D
- Result: IS Sharpe 2.107 (raw) → -0.265 (lagged). Look-ahead + redundant (H-012 corr 0.808).
- Notes: Both look-ahead (4h component) and redundant (0.808 corr with plain momentum). After lag: complete failure. The 4h component was the sole source of apparent alpha, and it was all look-ahead.
- Sessions: [2026-04-11 session 182]

## H-700: OI Velocity (2nd Derivative) XS
- Status: REJECTED
- Idea: Acceleration of OI change — rate of change of OI growth rate. Assets with accelerating OI may see continuation.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Data: 14 assets, 734 days (common OHLCV + OI period).
- Result: IS 100% (high_long, LB30), best LB30_R7_N4 Sharpe 0.871, Ann +29.4%, DD -30.0%. Params 6/6 (100%). **WF 1/4** — poor OOS. SH PASS (1.0/0.1). H-012 corr -0.033.
- Notes: Good IS but WF kills it. OI acceleration has no persistent XS predictive power despite near-zero H-012 corr.
- Sessions: [2026-04-11 session 183]

## H-701: OI-Volume Ratio (Positioning Density) XS
- Status: BORDERLINE (SH FAIL)
- Idea: Rank by OI / rolling average volume. High ratio = many positions held relative to activity = crowded.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 83% (low_long), best LB10_R5_N3 Sharpe 0.477, Ann +23.0%, DD -85.5%. Params 5/6 (83%). **WF 4/5** (mean 1.236). SH FAIL (H1=-0.519, H2=1.470). H-012 corr -0.003 (excellent diversifier).
- Notes: Outstanding WF but SH failure and low IS Sharpe. Interesting diversifier concept but unstable in first half of data. Not deployed.
- Sessions: [2026-04-11 session 183]

## H-702: OI-Funding Interaction (Crowding) XS
- Status: REJECTED
- Idea: OI growth × funding rate as composite crowding signal. High crowding = contrarian trade.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 83% (high_long, LB10), best LB10_R7_N3 Sharpe 1.077. WF 2/5. SH FAIL (H1=1.433, H2=-0.211). H-012 corr 0.091.
- Notes: WF fails. Crowding signal (OI × funding) doesn't predict XS returns. LB20 and LB30 also fail IS.
- Sessions: [2026-04-11 session 183]

## H-703: OI Surprise (Residual) XS
- Status: CONFIRMED → LIVE (paper trade since 2026-04-11)
- Idea: OI change minus volume change. Assets where OI grows LESS than volume (low positioning density relative to activity) outperform.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebalance every 7 days)
- Logic: Compute OI_pct_change(15) - Volume_pct_change(15). Rank XS. Long bottom 3 (lowest surprise), short top 3.
- Data: 14 assets, 734 daily bars + real OI history from Bybit V5 API.
- Result:
  - **IS**: 83% positive (25/30 expanded grid), best **LB15_R7_N3** Sharpe **1.578**, +66.5% ann, -38.2% DD
  - **WF**: **5/6** positive (83%), mean **1.422** — outstanding
  - **Split-half**: H1=**1.409**, H2=**1.332** — PASS (both strong)
  - **Param robustness**: All 6 R×N neighbors positive (100%), range 1.225-1.578
  - **Correlation**: H-012 **-0.010** — near-zero (excellent diversifier)
  - **Yearly consistency**: 2024 Sharpe 1.59, 2025 Sharpe 1.57, 2026 Sharpe 1.85
- Notes: First strategy using real OI data from Bybit. Signal captures informed directional trading (high volume without proportional position-building). LB15 is optimal; LB10 has much worse DD (-84.6%). Deployed: LONG AVAX/ARB/SUI, SHORT OP/NEAR/DOT.
- Sessions: [2026-04-11 session 183]

## H-704: OI Mean Reversion (Percentile Rank) XS
- Status: BORDERLINE (SH FAIL)
- Idea: OI percentile rank over rolling window. Assets at extreme OI levels revert.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS 100% (low_long, LB120), best LB120_R3_N3 Sharpe 0.374. Params 6/6 (100%). WF 3/4. SH FAIL (H1=-0.625, H2=0.743). H-012 corr -0.007.
- Notes: Low IS Sharpe (0.374) despite 100% params. OI percentile rank is too slow to be useful. Not deployed.
- Sessions: [2026-04-11 session 183]

## H-705: BTC OI Breakout TS
- Status: REJECTED
- Idea: Long BTC when OI > OI_MA and Price > Price_MA. Combined conviction signal.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.295, Ann +10.9%, DD -43.6%. Too low for further testing.
- Notes: Simple OI + price MA crossover doesn't work for BTC timing. Signal too noisy.
- Sessions: [2026-04-11 session 183]

## H-706: BTC OI-Price Regime TS
- Status: REJECTED
- Idea: 4-quadrant model: (OI up/down) × (Price up/down) → different positions. Confirmed breakout, capitulation buying, etc.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.073, Ann -3.1%, DD -46.5%. Negative Sharpe.
- Notes: OI-Price quadrant model is noise for BTC timing. Regime classification doesn't predict next-day returns.
- Sessions: [2026-04-11 session 183]

## H-707: Multi-Asset OI Momentum TS
- Status: BORDERLINE (50% param robust)
- Idea: Average OI growth across top-N assets as macro timing signal for BTC.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.956, Ann +44.3%, DD -80.6%. Params 5/10 (50%). WF 4/5 (mean 1.291). SH PASS (0.099/1.989).
- Notes: Interesting WF performance but only 50% param robust. Huge DD (-80.6%). SH passes but H1 barely positive (0.099). Not deployed.
- Sessions: [2026-04-11 session 183]

## H-708: BTC OI Divergence TS
- Status: REJECTED
- Idea: Trade divergences between price new highs/lows and OI new highs/lows. Classic technical divergence.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.338, Ann -10.0%, DD -40.6%. Negative Sharpe.
- Notes: Price-OI divergence is not predictive for BTC timing. Classic TA divergence fails.
- Sessions: [2026-04-11 session 183]

## H-709: BTC Liquidation Proxy TS
- Status: REJECTED
- Idea: Detect rapid OI drop + price drop (liquidation cascade), buy the bounce. Hold for N days.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.628, Ann +16.3%, DD -26.8%. Params 15/27 (56%). WF 2/5. SH PASS (1.0/0.07). H-009 corr -0.358.
- Notes: Liquidation bounces exist (interesting negative H-009 correlation) but too infrequent and inconsistent for reliable strategy. WF 2/5 kills it.
- Sessions: [2026-04-11 session 183]

## H-710: BTC Funding-OI Composite TS
- Status: BORDERLINE (low Sharpe, SH FAIL)
- Idea: Z-score composite of OI growth + funding rate + price momentum. Contrarian at extremes.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.303, Ann +10.9%, DD -33.5%. Params 3/8 (38%). WF 3/5. SH FAIL (0.465/-0.310). H-009 corr -0.430.
- Notes: Excellent negative trend correlation (-0.43) but signal too weak. Funding-OI composite doesn't add enough value over individual signals.
- Sessions: [2026-04-11 session 183]

## H-711: ETH/BTC OI Ratio TS
- Status: REJECTED
- Idea: ETH OI / BTC OI ratio change as altcoin rotation signal. Rising ratio = altcoin season.
- Instrument: futures (ETH/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.265, Ann +12.0%, DD -63.9%. Too low.
- Notes: ETH/BTC OI ratio doesn't predict ETH performance. Altcoin rotation via OI ratio fails.
- Sessions: [2026-04-11 session 183]

## H-712: Aggregate OI Expansion TS
- Status: REJECTED
- Idea: Total OI in USD across all 14 assets as macro timing signal. Expanding OI = bullish.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.261, Ann +8.7%, DD -33.8%. Too low.
- Notes: Aggregate OI growth is too noisy for BTC timing. Total positioning doesn't predict returns.
- Sessions: [2026-04-11 session 183]

## H-713: OI-Volatility Regime TS
- Status: REJECTED
- Idea: Trade BTC based on OI-vol regimes. High OI + low vol = squeeze → breakout. High OI + high vol = crowded → revert.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.115, Ann -1.8%, DD -26.3%. Negative.
- Notes: OI-vol regime classification is noise. Squeeze detection via OI + vol percentiles doesn't work.
- Sessions: [2026-04-11 session 183]

## H-714: BTC OI Percentile Timing TS
- Status: REJECTED
- Idea: Contrarian trade at OI extremes. Sell when OI is at 90th percentile (crowded), buy at 10th (uncrowded).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.299, Ann +7.9%, DD -26.3%. Too low.
- Notes: OI percentile timing is too slow and unreliable. Extreme OI doesn't consistently predict BTC returns.
- Sessions: [2026-04-11 session 183]

## H-715: OI Breadth TS
- Status: BORDERLINE (SH FAIL)
- Idea: Fraction of assets with rising OI (breadth) as macro signal. High breadth = broad participation = bullish.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 0.780, Ann +17.3%, DD -16.5%. Params 10/12 (83%). WF 3/5. SH FAIL (1.350/-0.475). H-009 corr 0.205.
- Notes: Decent IS and params but SH fails. OI breadth signal works in second half only (H2=-0.475). Moderate trend correlation. Not deployed.
- Sessions: [2026-04-11 session 183]

## H-716: BTC Basis Z-Score Mean Reversion
- Status: REJECTED (SH FAIL)
- Idea: Trade BTC based on z-score of spot-perp basis. High z → short (overheated), low z → long.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe 1.055, Ann +33.1%, DD -32.0%, Exposure 33%. WF 3/6. SH 2.169/-0.078 (FAIL). 100% param robust (24/24).
- Notes: Strong IS but basis degrades over time. Basis too small and tight in crypto due to funding rate mechanism.
- Sessions: [2026-04-11 session 184]

## H-717: BTC Basis Momentum
- Status: REJECTED
- Idea: BTC long when short-term basis MA > long-term (rising basis = bullish).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.183, Ann -9.8%, DD -87.6%.
- Notes: Basis direction doesn't predict price direction.
- Sessions: [2026-04-11 session 184]

## H-718: BTC Basis Level Regime
- Status: REJECTED
- Idea: Trade BTC based on basis percentile rank (high = bullish, low = bearish).
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.905, Ann -29.9%, DD -87.1%. Strongly negative.
- Sessions: [2026-04-11 session 184]

## H-719: XS Basis (Carry Factor)
- Status: REJECTED (WEAK)
- Idea: Rank 14 assets by rolling average spot-perp basis. Long highest basis, short lowest.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.603, WF 5/6, SH PASS. H-012 corr 0.314. Below 0.7 threshold.
- Notes: Traditional carry factor is weak in crypto where basis is tight.
- Sessions: [2026-04-11 session 184]

## H-720: Basis Change XS
- Status: REJECTED
- Idea: Rank assets by 5-day change in basis. Rising basis → long.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.261. Basis changes are noise.
- Sessions: [2026-04-11 session 184]

## H-721: BTC Funding-Basis Composite
- Status: REJECTED (DATA UNAVAILABLE)
- Idea: Combine funding rate z-score and basis z-score into composite mean-reversion signal.
- Result: Could not test — funding data format issue. Basis signals weak regardless.
- Sessions: [2026-04-11 session 184]

## H-722: Multi-Asset Basis Momentum XS
- Status: REJECTED
- Idea: Rank assets by change in rolling average basis.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.128. Basis momentum in cross-section is noise.
- Sessions: [2026-04-11 session 184]

## H-723: BTC Basis Volatility
- Status: REJECTED
- Idea: Basis vol as VIX proxy. High basis vol → buy. Low → sell.
- Instrument: futures (BTC/USDT perp)
- Timeframe: 1D
- Result: IS Sharpe -0.099. Basis volatility doesn't predict price direction.
- Sessions: [2026-04-11 session 184]

## H-724: Volume x Momentum Interaction XS
- Status: CONFIRMED (NOT deployed — redundant)
- Idea: Rank by momentum × volume ratio. Momentum amplified by volume confirmation.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.434, WF 4/6, SH PASS, 100% param robust. H-012 corr **0.908** — essentially identical to momentum.
- Sessions: [2026-04-11 session 184]

## H-725: Price-Volume Divergence XS
- Status: REJECTED
- Idea: Volume change rank minus price momentum rank as accumulation signal.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.027. SH FAIL.
- Sessions: [2026-04-11 session 184]

## H-726: Maximum Drawdown Factor XS
- Status: LIVE (paper trade since 2026-04-11)
- Idea: Rank by rolling 30-day max drawdown. Long most beaten-down, short least.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Compute max DD of each asset over 30d rolling window. Long deepest DD (contrarian), short shallowest.
- Result:
  - **IS**: Sharpe **0.980**, Ann +44.6%, DD -35.5%.
  - **WF**: **6/6 (PERFECT)**.
  - **SH**: 0.570/1.379 (both positive, corrected p=0.498/0.101).
  - **Param robust**: **100%** (60/60). Median Sharpe 0.895.
  - **H-012 corr**: 0.332.
- Notes: Perfect WF is strongest possible evidence. Novel contrarian factor. SH borderline on corrected test (power issue in first half).
- Sessions: [2026-04-11 session 184]

## H-727: Recovery Speed Factor XS
- Status: BORDERLINE (not deployed)
- Idea: Rank by how close to 30-day high each asset is. Fast recovery → long.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.205, WF 5/6, SH corrected FAIL. 100% param robust. H-012 corr 0.351. H-726 corr 0.350.
- Notes: Related to H-726 conceptually. Not deployed to avoid redundancy.
- Sessions: [2026-04-11 session 184]

## H-728: Vol-Adjusted Momentum XS
- Status: REJECTED (redundant)
- Idea: Rank by momentum / volatility (Sharpe-like).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.524. H-012 corr 0.798. Below threshold and highly redundant.
- Sessions: [2026-04-11 session 184]

## H-729: Consecutive Return Days XS
- Status: REJECTED
- Idea: XS contrarian on consecutive up/down days.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -1.239. Strongly negative — momentum dominates cross-sectionally.
- Sessions: [2026-04-11 session 184]

## H-730: Range Compression XS
- Status: REJECTED
- Idea: Long most range-compressed assets (breakout anticipation).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -1.268. Strongly negative.
- Sessions: [2026-04-11 session 184]

## H-731: Intraday Range Asymmetry XS
- Status: BORDERLINE (not deployed)
- Idea: Rank by (close-open)/(high-low) averaged over 10 days.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.013, WF 4/6, SH corrected FAIL. 85% param robust. H-012 corr 0.263.
- Sessions: [2026-04-11 session 184]

## H-732: RSI Momentum XS
- Status: REJECTED (WEAK)
- Idea: Rank by 5-day RSI change (momentum of RSI).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.644, WF 5/6, SH PASS. H-012 corr 0.052. Below 0.7 threshold.
- Sessions: [2026-04-11 session 184]

## H-733: Dollar Volume Change XS
- Status: LIVE (paper trade since 2026-04-11)
- Idea: Rank by 10-day change in dollar volume (price × volume). Long increasing, short decreasing.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Dollar volume = close × volume. 10-day pct change. Long top 4, short bottom 4.
- Result:
  - **IS**: Sharpe **1.262**, Ann +51.2%.
  - **WF**: **5/6**.
  - **SH**: BORDERLINE (H1=0.254 p=0.760, H2=2.242 p=0.007).
  - **Param robust**: **97%** (70/72).
  - **H-012 corr**: **0.046** (near zero — excellent diversifier).
  - **H-021 corr**: 0.540 (moderate overlap with volume momentum).
- Notes: SH first half weak. Deployed given 97% param robustness and near-zero momentum correlation.
- Sessions: [2026-04-11 session 184]

## H-734: H-L Range Trend XS
- Status: REJECTED
- Idea: Contrarian on range expansion (short expanding, long contracting).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -1.127. Strongly negative.
- Sessions: [2026-04-11 session 184]

## H-735: Close-to-High Ratio XS
- Status: REJECTED (SH FAIL)
- Idea: Rank by (close-low)/(high-low) over 10 days.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.696, WF 3/6, SH 1.434/-0.093 (FAIL).
- Sessions: [2026-04-11 session 184]

## H-736: Cumulative Volume Delta XS
- Status: LIVE (paper trade since 2026-04-11)
- Idea: Approximate buy/sell pressure from OHLC candle structure. (close-open)/(high-low) × volume.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Logic: Buy fraction = (close-open)/(high-low). Sum(buy_frac × vol) / sum(vol) over 10 days. Long top 4, short bottom 4.
- Result:
  - **IS**: Sharpe **1.703**, Ann +70.8%.
  - **WF**: **6/6 (PERFECT)** on 11 assets, 4/6 on 14.
  - **SH corrected**: **PASS** (H1 p=0.061, H2 p=0.026).
  - **Param robust**: **96%** (69/72).
  - **H-012 corr**: 0.366 (moderate).
- Notes: Best new factor this session. More refined than OBV — uses candle body position, not just return sign. All validation criteria pass cleanly.
- Sessions: [2026-04-11 session 184]

## H-737: Relative Volume Surprise XS
- Status: REJECTED
- Idea: Signed volume surprise (vol/avg × sign(ret)) averaged over 5 days.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.393, SH FAIL. Volume surprise too noisy.
- Sessions: [2026-04-11 session 184]

## H-738: Momentum Acceleration XS
- Status: BORDERLINE (not deployed)
- Idea: Second derivative of momentum (10-day change in 20-day mean return).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.820-0.971, WF 4/6, SH corrected FAIL. 82% param robust. H-012 corr 0.064.
- Notes: Low momentum correlation is interesting. Captures where momentum is building vs fading.
- Sessions: [2026-04-11 session 184]

## H-739: Upside Participation Ratio XS
- Status: BORDERLINE (not deployed)
- Idea: Rank by average return on BTC-up days over 20-day window.
- Instrument: futures (14 perps excl BTC)
- Timeframe: 1D
- Result: IS Sharpe 1.037, WF 4/6, SH 1.426/0.645 (PASS basic). H-012 corr 0.295.
- Notes: Novel but depends on BTC being in universe. Not validated with corrected SH.
- Sessions: [2026-04-11 session 184]

## H-740: Idiosyncratic Volatility XS
- Status: REJECTED
- Idea: Short high-idiosyncratic-vol assets (residual vol after removing market beta).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.336. No edge.
- Notes: Low-vol anomaly doesn't extend to residual vol in crypto.
- Sessions: [2026-04-12 session 185]

## H-741: Residual Momentum XS
- Status: REJECTED
- Idea: Cumulative residual return after beta-adjusting for market.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.568, WF 1/4 (fail). 100% param robust but no OOS edge.
- Notes: Market factor too dominant in crypto — residuals are noise.
- Sessions: [2026-04-12 session 185]

## H-742: Idiosyncratic Skewness XS
- Status: REJECTED
- Idea: Short positive-skew (lottery ticket) assets, long negative-skew.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.063. No edge.
- Notes: Lottery preference anomaly doesn't exist in crypto cross-section.
- Sessions: [2026-04-12 session 185]

## H-743: Beta Deviation XS
- Status: REJECTED
- Idea: Short assets whose short-term beta exceeds long-term beta (mean revert).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.277. Below threshold.
- Sessions: [2026-04-12 session 185]

## H-744: Tracking Error XS
- Status: REJECTED
- Idea: Long assets with high tracking error vs market (independent movers).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.398. Below threshold.
- Sessions: [2026-04-12 session 185]

## H-745: Information Ratio XS
- Status: REJECTED
- Idea: Rank by mean residual return / residual volatility.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.983, 100% param robust, WF 1/4 (fail).
- Notes: Good IS but completely unstable OOS. Overfitting to in-sample residual patterns.
- Sessions: [2026-04-12 session 185]

## H-746: Residual Reversal XS
- Status: REJECTED
- Idea: Short-term reversal in idiosyncratic (beta-adjusted) returns.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.368. Below threshold.
- Notes: Mean-reversion in residuals doesn't work in crypto.
- Sessions: [2026-04-12 session 185]

## H-747: Systematic Risk Share XS
- Status: REJECTED
- Idea: Long low-R² assets (idiosyncratic movers). R² of asset vs market.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0. Signal had computation issues (pandas chained assignment).
- Sessions: [2026-04-12 session 185]

## H-748: Correlation Breakaway XS
- Status: REJECTED
- Idea: Change in rolling correlation with BTC — decorrelating assets have momentum.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.079. No edge.
- Sessions: [2026-04-12 session 185]

## H-749: Pairwise Correlation Change XS
- Status: REJECTED
- Idea: Average correlation change with all other assets.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe -0.366. Negative edge.
- Sessions: [2026-04-12 session 185]

## H-750: Relative Strength RSI XS
- Status: REJECTED
- Idea: RSI of price relative to BTC (relative strength momentum/contrarian).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.918, 100% robust, WF 3/5, but SH p=0.200 (fail).
- Notes: Good IS but statistically insignificant. Both momentum and contrarian tested.
- Sessions: [2026-04-12 session 185]

## H-751: Mean Distance XS
- Status: REJECTED
- Idea: Z-score of price vs rolling mean (contrarian).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.009. No edge at all.
- Notes: Cross-sectional mean-reversion doesn't work in crypto (again confirmed).
- Sessions: [2026-04-12 session 185]

## H-752: Sector Rotation XS
- Status: REJECTED
- Idea: Return relative to sector average (L1 vs L2 vs meme rotation).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.156. Below threshold.
- Notes: Crypto sectors too correlated for meaningful rotation signals.
- Sessions: [2026-04-12 session 185]

## H-753: Correlation Concentration XS
- Status: REJECTED
- Idea: Average absolute correlation with all other assets. Long decorrelated.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.827, 100% robust, WF 1/4 (fail).
- Sessions: [2026-04-12 session 185]

## H-754: Lead-Lag Signal XS
- Status: CONFIRMED → LIVE (paper trade since 2026-04-12)
- Idea: Rank by lagged correlation with BTC — corr(asset_ret(t-1), BTC_ret(t)). Long assets that lead BTC.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebal every 3 days)
- Logic: 30-day rolling correlation of each asset's t-1 return with BTC's t return. Long top 3, short bottom 3.
- Result: IS Sharpe 1.232, Ann +61.7%, DD -34.7%. WF **4/4** mean 1.766. SH p=0.089 (PASS). 100% param robust.
- H-012 corr: **-0.014** (near-zero — excellent diversifier).
- Notes: Classic microstructure signal. Assets leading BTC by 1 day. Very strong WF performance.
- Sessions: [2026-04-12 session 185]

## H-755: Cross-Correlation Momentum XS
- Status: REJECTED
- Idea: Momentum of correlation with BTC (rising vs falling correlation).
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.467. Below threshold.
- Sessions: [2026-04-12 session 185]

## H-756: Asymmetric Beta XS
- Status: REJECTED
- Idea: Downside beta minus upside beta. Short high downside beta.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.303. Below threshold.
- Sessions: [2026-04-12 session 185]

## H-757: Return Consistency XS
- Status: REJECTED
- Idea: Fraction of positive return days. Long consistent winners.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.171, 100% robust, WF 4/5, but SH p=0.103 (borderline fail).
- Notes: Very close to passing all tests. Essentially a short-term momentum proxy.
- Sessions: [2026-04-12 session 185]

## H-758: Momentum Persistence XS
- Status: REJECTED
- Idea: Streak length of consecutive gains/losses.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.293, but param robust only 33% (fail).
- Notes: Extremely parameter-sensitive — only works with specific rebal frequency.
- Sessions: [2026-04-12 session 185]

## H-759: ADX Trend Strength XS
- Status: CONFIRMED → LIVE (paper trade since 2026-04-12)
- Idea: Long strong-trending assets (high ADX), short weak-trending.
- Instrument: futures (14 perps)
- Timeframe: 1D (rebal every 3 days)
- Logic: ADX(14) for each asset. Long top 3 (strongest trends), short bottom 3 (weakest).
- Result: IS Sharpe **1.723**, Ann +75.6%, DD -28.4%. WF **5/5** mean 1.454. SH p=0.016 (PASS). 100% param robust.
- H-012 corr: **0.064** (near-zero — excellent diversifier).
- Notes: ADX captures trend strength regardless of direction. Best IS Sharpe in batch. All WF folds positive.
- Sessions: [2026-04-12 session 185]

## H-760: Volume Surprise XS
- Status: REJECTED
- Idea: Volume z-score — current volume vs rolling average.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 1.122, 67% robust, WF 2/5 (fail).
- Sessions: [2026-04-12 session 185]

## H-761: Gap Signal XS
- Status: CONFIRMED → LIVE (paper trade since 2026-04-12)
- Idea: Open-to-previous-close gap. 5-day average gap as ranking signal.
- Instrument: futures (14 perps)
- Timeframe: 1D (daily rebal)
- Logic: Gap = (open - prev_close) / prev_close. 5-day rolling average. Long top 4 gaps, short bottom 4.
- Result: IS Sharpe **1.673**, Ann +76.9%, DD -46.8%. WF **5/5** mean 1.512. SH p=0.019 (PASS). 100% param robust.
- H-012 corr: **0.054** (near-zero — excellent diversifier).
- Notes: Overnight/gap effect captures momentum alignment. Daily rebal is high turnover but backtested with fees.
- Sessions: [2026-04-12 session 185]

## H-762: Range Position XS
- Status: REJECTED
- Idea: Where in recent high-low range the price sits.
- Instrument: futures (14 perps)
- Timeframe: 1D
- Result: IS Sharpe 0.823, 83% robust, WF 3/5, SH p=0.252 (fail).
- Sessions: [2026-04-12 session 185]

## H-763: Momentum-Vol Ratio XS
- Status: CONFIRMED → LIVE (paper trade since 2026-04-12)
- Idea: Momentum normalized by volatility (signal-to-noise ratio).
- Instrument: futures (14 perps)
- Timeframe: 1D (rebal every 5 days)
- Logic: 20-day return / 20-day volatility. Long top 4 (highest SNR), short bottom 4.
- Result: IS Sharpe 1.239, Ann +52.0%, DD -24.2%. WF 3/5 mean 0.701. SH p=0.085 (PASS). 100% param robust.
- H-012 corr: **0.027** (near-zero — excellent diversifier).
- Notes: Essentially a risk-adjusted momentum signal. Captures momentum quality not just magnitude.
- Sessions: [2026-04-12 session 185]
