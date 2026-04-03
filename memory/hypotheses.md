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

## Killed

### H-024: Low-Beta Anomaly — KILLED (2026-03-31, session 114)
- Reason: Comparison vs H-019 (low-vol) over 13 days: H-019 +7.44% vs H-024 -0.20% (7.64% gap). H-019 decisively won.

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
