# Strategy State

## Bybit Demo Account (LIVE since 2026-03-20, H-056 since 2026-03-23)

**Account**: $100k USDT demo. H-056 v2 deployed via hourly cron rebalancing.
**Architecture**: `scripts/demo_portfolio_runner.py` reads all strategy state.json files, computes net H-056 weighted positions with per-strategy leverage, rebalances on Bybit demo after each `run_all_paper_trades.py` run.
**H-056 weights (v2)**: H-031(30%,3x) H-052(23%,3x) H-053(16%,3x) H-021(15%,3x) H-039(10%,1x) H-049(6%,3x)
**v2 change (session 90)**: Replaced H-046 with H-049. H-046 had 4/4 position overlap with H-021 (redundant). H-049 has better diversification (neg corr with H-031).
**Dropped**: H-011 (funding arb), H-009 (BTC trend), H-046 (redundant with H-021)
**Bybit account leverage**: 10x (changed from 3x in session 83 to fix margin — only affects IM, not exposure)
**Gross leverage**: ~3.0x actual. All perp, no spot.

### Current Demo Status (as of 2026-04-02 17:27 UTC):
Demo eq: $98,428 (-1.57%). BTC spot ~$66,895. 13 open positions. Stable from last session despite BTC spot drop (daily bar still $68,119).

---

## Active Paper Trades (Internal Simulation)

### H-009: BTC Daily EMA Trend Following (VT 20%)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: SHORT 0.053871 BTC @ $69,909.32 — flipped from LONG (session 44)
- **Mark equity**: $9,886 (-1.14%) — BTC bar $68,119. SHORT gaining.
- **Leverage**: 0.38x (vol targeting)
- **Runner**: `paper_trades/h009_btc_daily_trend/runner.py`
- **Signal**: EMA(5) < EMA(40), remains SHORT.
- **Next check**: next daily bar

### H-011: Leveraged Funding Rate Arb (5x)
- **Status**: LIVE paper trade (started 2026-03-16) — **IN** since 00:00 UTC Mar 23 (2nd entry).
- **Position**: IN — Notional ~$49k (5x). 23 log entries.
- **Capital**: $9,866 (-1.34%)
- **Funding**: Total fees $149.24. 53 settlements.
- **Runner**: `paper_trades/h011_funding_rate_arb/runner.py`
- **Demo execution**: NOT on demo (H-056 excludes H-011). Internal paper trade only.

### H-012: Cross-Sectional Momentum (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-16)
- **Position**: 8 positions (4 long, 4 short) — **REBALANCED** session 94 (Mar 26 bar)
  - LONG: BTC, AVAX, DOGE, NEAR
  - SHORT: ARB, DOT, OP, SUI
- **Mark equity**: $10,262 (+2.62%)
- **Runner**: `paper_trades/h012_xsmom/runner.py`
- **Params**: 60d lookback, 5d rebalance, top/bottom 4
- **Next rebal**: in 4 days

### H-019: Low-Volatility Anomaly (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-18)
- **Position**: 6 positions (3 long, 3 short)
  - LONG (low vol): ATOM, ARB, XRP
  - SHORT (high vol): DOGE, DOT, NEAR
- **Mark equity**: $10,258 (+2.58%)
- **Runner**: `paper_trades/h019_lowvol/runner.py`
- **Params**: 20d vol window, 21d rebalance, top/bottom 3
- **Next rebal**: in 7 days

### H-021: Volume Momentum Factor (14 Assets)
- **Status**: LIVE paper trade (started 2026-03-18)
- **Position**: 8 positions (4 long, 4 short) — **REBALANCED** session 100 (Mar 27 bar)
  - LONG (vol surge): ARB, BTC, DOT, OP
  - SHORT (vol drop): AVAX, ETH, NEAR, XRP
- **Mark equity**: $9,577 (-4.23%) — **worst performer**, sharp drop Apr 1.
- **Runner**: `paper_trades/h021_volmom/runner.py`
- **Params**: VS5_VL20_R3_N4 (5d/20d volume ratio, 3-day rebalance, top/bottom 4)
- **Next rebal**: in 1 day

### H-024: Low-Beta Anomaly (14 Assets) — KILLED
- **Status**: KILLED (session 114, 2026-03-31). H-019 won comparison decisively (+7.44% vs -0.20%).
- **Final equity**: $10,079 (+0.79%) — positions still held but runner removed from orchestrator.
- **Runner**: Removed from orchestrator (session 114/124). Comment cleaned up session 124.

### H-031: Size Factor (Dollar Volume Proxy, Long Large) — independent
- **Status**: LIVE paper trade (started 2026-03-19) — independent
- **Position**: 10 positions (5 long, 5 short) — rebalanced session 83 (positions unchanged)
  - LONG (large cap): BTC, ETH, SOL, XRP, DOGE
  - SHORT (small cap): LINK, DOT, OP, ARB, ATOM
- **Mark equity**: $10,469 (+4.69%) — **#1 overall**.
- **Runner**: `paper_trades/h031_size/runner.py`
- **Params**: W30_R5_N5 (30-day avg dollar volume, 5-day rebalance, top/bottom 5)
- **Next rebal**: Mar 29 bar

### H-032: Cointegration Pairs (8-pair portfolio) — independent
- **Status**: LIVE paper trade (started 2026-03-19) — independent, experimental
- **Position**: ALL FLAT — waiting for z-score entry signals
- **Pairs**: DOT/ATOM, DOGE/LINK, DOGE/ADA, DOT/OP, SOL/DOGE, AVAX/DOT, NEAR/OP, ARB/ATOM
- **Mark equity**: $9,991 (-0.09%) — 3 active pairs (DOT/ATOM, SOL/DOGE, AVAX/DOT).
- **Runner**: `paper_trades/h032_pairs/runner.py`
- **Note**: OOS Sharpe 1.33, DD 5.8%. First entries now active.

### H-037: Polymarket 1hr BTC UP/DOWN (Manual Paper Trade)
- **Status**: CONFIRMED for paper trade (started 2026-03-19) — MANUAL, Polymarket only
- **Position**: No trades yet
- **Target hours (UTC)**: 17:00 (UP), 21:00 (UP), 22:00 (UP), 23:00 (DOWN), 13:00 (DOWN)
- **Tracker**: `paper_trades/h037_polymarket/tracker.py`

### H-039: Day-of-Week Seasonality (Long Wed / Short Thu) — independent
- **Status**: LIVE paper trade (started 2026-03-19) — independent
- **Position**: **SHORT** 0.1527 BTC @ $68,119 (Thu short entered at 00:34 UTC Apr 2).
- **Capital**: $10,398 (+3.98%) — **#2 overall**. Wed LONG closed -$29.
- **Runner**: `paper_trades/h039_dow_seasonality/runner.py`
- **Backtest**: WF **6/6** positive (mean OOS Sharpe **2.46**)
- **Next**: Exit SHORT at Fri open (00:30 UTC Apr 4). LONG entry next Wed (00:30 UTC Apr 9).

### H-044: OI-Price Divergence Factor (14 Assets) — independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 10 positions (5 long, 5 short)
  - LONG (price up + OI down): SUI, OP, NEAR, SOL, ETH
  - SHORT (price down + OI up): ADA, ARB, DOT, XRP, DOGE
- **Mark equity**: $9,952 (-0.48%)
- **Runner**: `paper_trades/h044_oi_divergence/runner.py`
- **Next rebal**: in 8 days

### H-046: Price Acceleration Factor (14 Assets) — independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 8 positions (4 long, 4 short) — **REBALANCED** session 89 (Mar 25 bar)
  - LONG (accelerating): OP, ATOM, ARB, SUI
  - SHORT (decelerating): BTC, SOL, DOT, NEAR
- **Mark equity**: $10,017 (+0.17%)
- **Runner**: `paper_trades/h046_acceleration/runner.py`
- **Next rebal**: in 2 days

### H-049: LSR Sentiment Factor (Contrarian, 14 Assets) — independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 6 positions (3 long, 3 short) — **REBALANCED** session 83 (Mar 24 bar)
  - LONG (crowd short): BTC, NEAR, ETH
  - SHORT (crowd long): XRP, OP, DOGE
- **Mark equity**: $10,116 (+1.16%)
- **Runner**: `paper_trades/h049_lsr_sentiment/runner.py`
- **Params**: R5_N3 (5-day rebalance, top/bottom 3, contrarian direction)
- **Next rebal**: in 2 days
- **CAVEAT**: Only 200 days of backtest data. Needs extended paper trade.

### H-052: Premium Index Factor (Contrarian, 14 Assets) — independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 8 positions (4 long, 4 short) — **REBALANCED** session 83 (Mar 24 bar)
  - LONG (most discounted): DOT, LINK, ETH, OP
  - SHORT (least discounted): NEAR, AVAX, ATOM, ARB
- **Mark equity**: $10,144 (+1.44%)
- **Runner**: `paper_trades/h052_premium/runner.py`
- **Params**: W5_R5_N4 (5-day premium window, 5-day rebalance, top/bottom 4, contrarian)
- **Next rebal**: in 3 days

### H-053: Funding Rate Cross-Sectional Factor (Contrarian, 14 Assets) — independent
- **Status**: LIVE paper trade (started 2026-03-20) — independent
- **Position**: 8 positions (4 long, 4 short)
  - LONG (lowest funding): DOT, ATOM, SOL, BTC
  - SHORT (highest funding): OP, NEAR, ARB, ADA
- **Mark equity**: $9,867 (-1.33%) — dropped after rebalance.
- **Runner**: `paper_trades/h053_funding_xs/runner.py`
- **Params**: W3_R10_N4 (3-day funding avg, 10-day rebalance, top/bottom 4, contrarian)
- **Next rebal**: in 8 days

### H-059: Volatility Term Structure Factor (Expansion-Long, 14 Assets) — independent
- **Status**: LIVE paper trade (started 2026-03-22) — independent
- **Position**: 10 positions (5 long, 5 short)
  - LONG (vol expanding): OP, ARB, XRP, ATOM, ETH
  - SHORT (vol contracting): DOGE, SUI, BTC, NEAR, DOT
- **Mark equity**: $10,053 (+0.53%) — recovered to positive.
- **Runner**: `paper_trades/h059_vol_term/runner.py`
- **Params**: SW7_LW30_R7_N5 (7-day short vol, 30-day long vol, 7-day rebalance, top/bottom 5, expansion-long)
- **Next rebal**: in ~2 days

### H-062: Max Drawdown Momentum Factor (14 Assets) — independent
- **Status**: LIVE paper trade (started 2026-03-22) — independent
- **Position**: 6 positions (3 long, 3 short) — **REBALANCED** session 94 (Mar 26 bar, unchanged)
  - LONG (near 60d peak): AVAX, BTC, NEAR
  - SHORT (deep drawdown): ARB, OP, SUI
- **Mark equity**: $10,113 (+1.13%)
- **Runner**: `paper_trades/h062_dd_momentum/runner.py`
- **Params**: L60_R5_N3 (60-day lookback, 5-day rebalance, top/bottom 3, long near-peak)
- **Next rebal**: in ~2 days

### H-063: Systematic BTC Short Strangle with Delta Hedging (Vol Selling)
- **Status**: LIVE paper trade (started 2026-03-25) — first options strategy
- **Position**: FLAT — Trade 1 settled at expiry Apr 3 08:00 UTC.
  - Trade 1: Sold 73000C + 69000P, 0.1403 contracts, $364.14 premium, entry BTC $71,264.
  - Settlement: BTC $67,060. Call expired OTM (worthless). Put settled ITM ($69k-$67,060=$1,940 intrinsic, $272 payoff).
  - **Net P&L: +$77.64 (+0.78%)** — premium > put liability. First trade profitable!
- **Mark equity**: $10,078 (+0.78%)
- **Runner**: `paper_trades/h063_vol_selling/runner.py`
- **Backtest**: Sharpe 1.54, +52.5% ann, -18.4% DD, 73% WR. WF 6/6 positive. 60/60 params positive.
- **Logic**: Sell 7-day 3% OTM BTC strangle, delta-hedge daily, 10% stop
- **Next**: Waiting for next 7-day option entry (cron will handle automatically).
- **Correlation**: -0.10 vs H-009, ~0 vs BTC — truly market-neutral

### H-076: Price Efficiency Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-03-26) — genuinely novel signal
- **Position**: 8 positions (4 long, 4 short)
  - LONG (most efficient): OP, NEAR, ATOM, ARB
  - SHORT (most noisy): ADA, DOGE, SUI, XRP
- **Mark equity**: $10,065 (+0.65%)
- **Runner**: `paper_trades/h076_efficiency/runner.py`
- **Params**: LB40_R5_N4 (40-day efficiency, 5-day rebalance, top/bottom 4)
- **Next rebal**: in ~2 days
- **Backtest**: True daily Sharpe 1.94, +106% ann, -23.5% DD. WF **6/6 positive**. Corr 0.04 with H-012 (near zero).
- **Note**: Most novel signal discovered — captures trend quality, not direction. Zero correlation with all existing strategies.

### H-085: Turnover Velocity Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-03-26) — 100% param robustness
- **Position**: 8 positions (4 long, 4 short) — **REBALANCED** Apr 1 bar
  - LONG: BTC, NEAR, SOL, SUI
  - SHORT: XRP, DOGE, DOT, LINK
- **Mark equity**: $9,951 (-0.49%)
- **Runner**: `paper_trades/h085_turnover/runner.py`
- **Params**: SV5_LV20_R7_N4 (5-day short vol, 20-day long vol, 7-day rebalance, top/bottom 4)
- **Next rebal**: Apr 8 bar
- **Backtest**: 100% params positive (48/48), best Sharpe 2.08, mean 1.48. WF (selected) 3/4 positive. Corr 0.21 with H-012.

### H-160: Trend-Quality Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-03-31) — genuinely novel
- **Position**: 6 positions (3 long, 3 short)
  - LONG: ETH, DOGE, SOL
  - SHORT: BTC, OP, ATOM
- **Mark equity**: $9,944 (-0.56%) — recovering.
- **Runner**: `paper_trades/h160_trend_quality/runner.py`
- **Params**: EFF20_VOL20_R3_N3 (20-day efficiency, 20-day vol, 3-day rebal, top/bottom 3)
- **Next rebal**: Apr 2 bar
- **Backtest**: IS 87%, WF 4/6 mean 0.303. Corr 0.355 H-012, 0.117 H-076.

### H-169: Beta-Adjusted Momentum / Alpha Factor (13 Non-BTC Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-01) — 100% IS positive
- **Position**: 8 positions (4 long, 4 short)
  - LONG (positive alpha): DOGE, LINK, ETH, AVAX
  - SHORT (negative alpha): ATOM, NEAR, OP, DOT
- **Mark equity**: $10,170 (+1.70%) — **strong start, day 2**.
- **Runner**: `paper_trades/h169_alpha_momentum/runner.py`
- **Params**: LB10_R5_N4 (10-day alpha lookback, 5-day rebalance, top/bottom 4)
- **Next rebal**: Apr 5 bar
- **Backtest**: IS 100% (30/30), best Sharpe 1.550. WF 4/6, mean OOS 1.648. Corr 0.342 H-012.

### H-175: Net Money Flow Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-01) — 100% IS positive
- **Position**: 8 positions (4 long, 4 short)
  - LONG (inflow): DOGE, ARB, NEAR, ADA
  - SHORT (outflow): ETH, BTC, ATOM, OP
- **Mark equity**: $10,116 (+1.16%) — **strong start, day 2**.
- **Runner**: `paper_trades/h175_money_flow/runner.py`
- **Params**: LB30_R7_N4 (30-day flow window, 7-day rebalance, top/bottom 4)
- **Next rebal**: Apr 7 bar
- **Backtest**: IS 100% (30/30), mean Sharpe 1.005, best 1.402. WF 4/6, mean OOS 1.051. Corr 0.145 H-012, 0.299 H-160.

### H-182: High-Low Range Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-02) — 90% IS, genuinely novel
- **Position**: 6 positions (3 long, 3 short)
  - LONG (narrow range): BTC, ATOM, XRP
  - SHORT (wide range): OP, SUI, NEAR
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h182_range/runner.py`
- **Params**: LB30_R5_N3 (30-day range, 5-day rebalance, top/bottom 3, narrow_long)
- **Next rebal**: Apr 6 bar
- **Backtest**: IS 90%, WF 5/6 mean 1.506. Corr 0.200 H-012 (very low).

### H-183: Gap Factor / Overnight Sentiment (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-02) — 100% IS positive
- **Position**: 8 positions (4 long, 4 short)
  - LONG (negative gap / contrarian buy): BTC, ETH, SOL, SUI
  - SHORT (positive gap): NEAR, OP, ARB, ATOM
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h183_gap/runner.py`
- **Params**: LB10_R5_N4 (10-day gap, 5-day rebalance, top/bottom 4, neg_gap_long)
- **Next rebal**: Apr 6 bar
- **Backtest**: IS 100%, WF 5/6 mean 1.771. Corr 0.468 H-012 (borderline but passing).

### H-189: Funding Rate Dispersion Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-02) — essentially zero correlation with everything
- **Position**: 6 positions (3 long, 3 short)
  - LONG (low dispersion): BTC, ETH, LINK
  - SHORT (high dispersion): ATOM, DOT, OP
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h189_funding_dispersion/runner.py`
- **Params**: LB20_R7_N3 (20-day funding std, 7-day rebalance, top/bottom 3, low_disp_long)
- **Next rebal**: Apr 8 bar
- **Backtest**: IS 91.7%, WF 4/6 mean 1.014. Corr 0.033 (near zero with everything).

### H-191: Volume-Price Elasticity Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-02) — novel microstructure signal
- **Position**: 8 positions (4 long, 4 short)
  - LONG (deep liquidity): BTC, ETH, XRP, AVAX
  - SHORT (fragile/thin): NEAR, OP, SUI, ARB
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h191_vol_price_elasticity/runner.py`
- **Params**: LB60_R7_N4 (60-day elasticity, 7-day rebalance, top/bottom 4, low_elast_long)
- **Next rebal**: Apr 8 bar
- **Backtest**: IS 80%, WF 4/5 mean 1.728. Corr 0.353 H-012, 0.000 H-076.

### H-193: OI-Price Momentum Divergence Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-02) — uses OI data
- **Position**: 6 positions (3 long, 3 short)
  - LONG (aligned momentum): XRP, OP, ARB
  - SHORT (misaligned): AVAX, ADA, LINK
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h193_oi_price_divergence/runner.py`
- **Params**: LB20_R7_N3 (20-day momentum, 7-day rebalance, top/bottom 3, low_div_long)
- **Next rebal**: Apr 8 bar
- **Backtest**: IS 86.7%, WF 4/5 mean 1.470. Corr 0.380 H-012.

### H-197: Amihud Illiquidity Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-02) — 100% IS, flight-to-liquidity
- **Position**: 8 positions (4 long, 4 short)
  - LONG (most liquid / low Amihud): BTC, ETH, SOL, XRP
  - SHORT (most illiquid / high Amihud): LINK, OP, ARB, ATOM
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h197_amihud/runner.py`
- **Params**: LB10_R3_N4 (10-day Amihud, 3-day rebalance, top/bottom 4, low_amihud_long)
- **Next rebal**: Apr 4 bar
- **Backtest**: IS 100% (30/30), mean Sharpe 1.537, best 1.895. WF 5/6 mean 1.387. Corr 0.488 H-012, 0.000 H-076.

### H-215: Dollar Volume Trend Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-03) — novel flow-of-funds signal
- **Position**: 8 positions (4 long, 4 short)
  - LONG (increasing DV trend): SOL, DOGE, OP, SUI
  - SHORT (decreasing DV trend): DOT, LINK, NEAR, ATOM
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h215_dollar_vol_trend/runner.py`
- **Params**: LB15_R3_N4 (15-day log-DV slope, 3-day rebalance, top/bottom 4)
- **Next rebal**: Apr 5 bar
- **Backtest**: IS 94.4% (34/36), mean Sharpe 0.705, best 1.668. WF 4/6 mean 0.016. Split-half H1=2.388/H2=1.565. Corr 0.148 H-012.

### H-219: Up-Volume Ratio Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-04) — novel volume composition signal
- **Position**: 6 positions (3 long, 3 short)
  - LONG (high up-vol ratio): ETH, LINK, DOGE
  - SHORT (low up-vol ratio): DOT, NEAR, ATOM
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h219_upvol_ratio/runner.py`
- **Params**: LB10_R7_N3 (10-day up-vol ratio, 7-day rebalance, top/bottom 3, upvol_long)
- **Next rebal**: Apr 10 bar
- **Backtest**: IS 80.0%, WF 4/6 mean 0.204. Corr 0.157 H-012. Split-half H1=1.266/H2=2.097.

### H-223: Momentum Breadth / Win Rate Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-04) — captures direction consistency
- **Position**: 6 positions (3 long, 3 short)
  - LONG (high win rate): ETH, DOGE, LINK
  - SHORT (low win rate): OP, ATOM, NEAR
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h223_momentum_breadth/runner.py`
- **Params**: LB20_R5_N3 (20-day win rate, 5-day rebalance, top/bottom 3, high_long)
- **Next rebal**: Apr 8 bar
- **Backtest**: IS 83.3%, WF 5/6 mean 1.120. Corr 0.365 H-012. Split-half H1=1.416/H2=0.994.

### H-242: Intraday Momentum Concentration Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-05) — novel microstructure signal
- **Position**: 8 positions (4 long, 4 short)
  - LONG (high concentration): ETH, AVAX, SOL, DOGE
  - SHORT (low concentration): NEAR, DOT, XRP, ATOM
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h242_intraday_concentration/runner.py`
- **Params**: LB10_R5_N4 (10-day avg concentration, 5-day rebalance, top/bottom 4, high_conc_long)
- **Next rebal**: Apr 9 bar
- **Backtest**: IS 100%, WF **6/6** mean **1.802** (best in entire hypothesis set). Corr 0.14 H-012, 0.24 H-031, 0.10 H-076.

### H-244: Intraday Reversal Propensity Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-05) — novel intraday microstructure
- **Position**: 8 positions (4 long, 4 short)
  - LONG (most mean-reverting): NEAR, OP, ARB, DOT
  - SHORT (most trending): AVAX, SOL, DOGE, ATOM
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h244_intraday_reversal/runner.py`
- **Params**: LB14d_R5_N4 (14-day hourly autocorrelation, 5-day rebalance, top/bottom 4, neg_autocorr_long)
- **Next rebal**: Apr 9 bar
- **Backtest**: IS 100%, WF 4/6 mean 0.268. Corr 0.05 H-012, -0.03 H-031, 0.01 H-242.

## Portfolio Summary (mark-to-market 2026-04-05 session 146, 05:22 UTC)
- **Bybit Demo**: ~$99,214 (-0.79%). BTC spot ~$67,082. Last daily bar: Apr 4, close $67,301.
- **Total internal MTM (32 strats)**: 32 runners active (30→32 post-deploy). No new daily bar since Apr 4.
- **Positive (12/32)**: H-039(+5.79%), H-012(+4.90%), H-076(+4.09%), H-031(+3.43%), H-062(+3.21%), H-175(+2.52%), H-052(+2.07%), H-049(+1.86%), H-085(+1.68%), H-044(+0.99%), H-063(+0.78%), H-019(+0.55%)
- **Near flat (1/32)**: H-032(0.00%)
- **Negative (19/32)**: H-242(-0.24%), H-244(-0.24%), H-193(-0.13%), H-059(-0.59%), H-046(-0.71%), H-021(-0.90%), H-011(-1.28%), H-215(-1.34%), H-197(-1.73%), H-223(-1.95%), H-009(-2.10%), H-219(-2.19%), H-053(-2.23%), H-182(-2.30%), H-160(-2.39%), H-169(-2.41%), H-191(-3.14%), H-183(-3.54%), H-189(-3.60%)
- **H-063 IN TRADE 2**: Strangle active, MTM +0.78%. ~2 days remaining.
- **H-039 (DOW)**: $10,579 (+5.79%, FLAT). Next LONG entry Wed Apr 9 (00:30 UTC).
- **H-011**: $9,872 (-1.28%), still IN.
- **H-189 worst**: -3.60%. H-183(-3.54%), H-191(-3.14%) also lagging. Monitor.
- **Rebal status**: Apr 5 bar: H-169/H-215. Apr 6: H-182/H-183. Apr 7: H-175. Apr 8: H-085/H-189/H-191/H-193/H-223. Apr 9: H-242/H-244. Apr 10: H-219.
- **Research**: 244 hypotheses total. H-242/H-244 CONFIRMED+deployed. H-243 REJECTED.
- **AUTOMATED:** Paper trades hourly via cron (32 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Continue research. Monitor H-189 (-3.60%) and H-183/H-191.
- **Open user questions:** None

## Target Portfolio Allocation — OLD 5-strat (baseline)
- **10% H-009** (BTC daily trend): directional alpha, Sharpe ~0.6-0.9
- **40% H-011** (funding rate arb): carry alpha, Sharpe ~15-25
- **10% H-012** (cross-sectional momentum): relative value alpha, Sharpe ~0.8-1.1
- **15% H-019** (low-volatility anomaly): cross-sectional factor, Sharpe ~0.7-1.2
- **25% H-021** (volume momentum): cross-sectional factor, Sharpe ~1.5-1.8
- **Combined (5-strat)**: Sharpe 2.58, +35.3%, 13.9% DD

## Target Portfolio Allocation — NEW 8-strat (H-055, proposed)
- **12% H-009** (BTC daily trend): directional alpha, Sharpe ~0.3
- **40% H-011** (funding rate arb): carry alpha, Sharpe ~18
- **7% H-021** (volume momentum): cross-sectional factor, Sharpe ~1.5
- **13% H-031** (size factor): large-cap vs small-cap, Sharpe ~2.5 — **REPLACES H-012**
- **9% H-039** (DOW seasonality): calendar alpha, Sharpe ~1.2 — **NEW**
- **5% H-046** (price acceleration): XS momentum derivative, Sharpe ~0.7 — **NEW**
- **8% H-052** (premium index contrarian): XS positioning, Sharpe ~2.4 — **NEW**
- **6% H-053** (funding rate XS contrarian): XS positioning, Sharpe ~2.0 — **NEW**
- **Combined (8-strat)**: **Sharpe 5.13, +46.0%, 7.3% DD** (vs 2.58/35%/14% old)
- **DROPPED**: H-012 (redundant with H-031, corr 0.517), H-019 (inferior to H-024, corr 0.657)
- **Status**: Pending paper trade validation (need 28+ days on all strategies)

## Proposed Upgrade: Replace H-019 with H-024
- **If confirmed in paper trade**: H-024 (beta) replaces H-019 (vol) — H-055 optimization also drops H-019
- **Current status**: H-019 +1.00% vs H-024 -1.64% — H-019 leads by 2.64%. Gap widening consistently.
- **Decision point**: After 4 weeks of parallel paper trading

## Key Correlations (12-strat, full 2yr, 700 days)
- H-009/H-011: 0.044, H-009/H-012: 0.025, H-009/H-021: 0.043, H-009/H-039: 0.069
- H-012/H-031: **0.517** (moderate — both capture similar XS signals)
- H-012/H-044: **0.467** (moderate — momentum and OI overlap)
- H-019/H-024: **0.657** (high — related factors, choose one)
- H-019/H-031: **0.454** (moderate — vol and size overlap)
- H-052/H-053: **0.377** (moderate — both positioning signals)
- H-052/H-012: **-0.127** (negative — excellent diversifier)
- H-053/H-012: 0.008 (near zero — excellent)
- H-039/all: <0.11 (near zero with everything — perfect diversifier)

## Active Live Strategies
(none)

## Recently Killed
(none)

## Research Pipeline
| Hypothesis | Status | Priority | Next Step |
|-----------|--------|----------|-----------|
| H-010: Multi-Strategy Portfolio | BACKTEST | Low | Superseded by H-055 portfolio optimization |
| H-055: Portfolio Optimization | CONFIRMED | High | Implement new 8-strat allocation after paper trade validation |

## H-055 Stress Test Results (session 54, 700 days backtest)
- **Tail Risk**: 95% daily VaR -0.56%, 99% VaR -0.89%. Worst day: -3.4% (Aug 8 2024, BTC flash). Max DD: -7.25%, recovered in 33 days.
- **Distribution**: 62% positive days, skew +0.18 (slightly positive), kurtosis 7.5 (fat tails but manageable). Only 0.6% of days below -1%.
- **Correlation Stability**: Avg pairwise corr 0.044. During BTC stress: 0.041 (unchanged). Rolling 30d corr NEVER >0.30. No correlation breakdown.
- **Regime Performance**: Uptrend Sharpe 7.46, Downtrend 2.89. High vol 5.64, Low vol 5.25. Deep DD 4.71. Positive in ALL regimes.
- **Year-by-year**: 2024: Sharpe 4.74, 2025: 5.50, 2026: 5.24. Consistent.
- **Monthly**: 88% positive (21/24). Worst month -3.26%. Mean +3.11%.
- **Regime Adaptive**: Static weights are near-optimal. Momentum reweight +0.53 Sharpe but risk of overfit. Trend/vol/DD protection all slightly hurt.
- **Monte Carlo (5000 sims, 1yr)**: P(loss)=0.0%. 5th pct return: +22.3%. P(>20%): 96.5%. P(DD>10%): 0.4%. Median Sharpe 5.36.
- **Critical Strategy**: H-011 most valuable (removing it: Sharpe 5.13→3.64). H-009 slightly negative marginal (Sharpe +0.23 without it — consider replacing or reducing weight).
- **H-046 Weakness**: Only strategy with negative Sharpe in downtrend (-0.87). Acceleration signal breaks when momentum reverses.
- **Action items**: (1) Keep static weights — don't add complexity. (2) Monitor H-009 marginal value; may reduce weight if paper trade confirms. (3) H-011 re-entry is the single most important event for portfolio returns.

## Risk Watch
- **Demo account**: $99,765 (-0.24%). All drifts within threshold. No spot BTC.
- **H-056 LIVE on demo**: 6-strat portfolio. Leverage 2.79x. Stress tested: positive in ALL regimes.
- **H-011 IN POSITION**: Re-entered 00:00 UTC Mar 23 (2nd entry). R27 +1.16% ann (safe). **R7 projects positive after 08:00 UTC Mar 24** — recovery ahead of schedule. Last 3 rates positive.
- **H-009 SHORT**: Entry $69,909, BTC at $70,190 → -2.63% equity. SHORT losing in BTC rally.
- **H-046 worst XS**: -0.96%. Acceleration factor underperforming.
- **H-011 worst overall**: -1.47% ($149 fees, net +$2.07 funding from 2 entry cycles).
- **Research status**: 71 hypotheses tested, ~48 rejected. All backtestable sources exhausted.
- **IV collector**: running (7 days). **OB collector**: running.
- **Watchlist**: **Tonight 00:30 UTC Mar 25**: H-021/H-031/H-049/H-052 rebal + H-039 first trade. H-046 rebal Mar 25. H-012/H-062 rebal Mar 26. H-059 rebal Mar 28. H-053/H-044 rebal Mar 29.
- **Cron**: Claude sessions every 4 hours. Paper trades hourly.
- **Open user questions**: None

## Automation
- **Paper trade orchestrator**: `scripts/run_all_paper_trades.py` — runs all 14 active runners sequentially
- **Cron schedule**: Every hour at :30 (`30 * * * *`), independent of Claude sessions
- **Logs**: `logs/paper_trades.log`
- **Claude sessions**: Every 4 hours at :00 — research, monitoring, strategy updates

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
| H-013: Multi-Asset Funding Arb | Rates too correlated (r=0.49), fees kill rotation. |
| H-014: Anti-Martingale | Fails WF (1/4). Corr 0.42 with H-009, redundant. |
| H-015: RSI Mean Reversion | 0/4 OOS folds positive. |
| H-016: BB Squeeze Breakout | Only 18 trades in 2yr. Overfit. |
| H-017: MTF Momentum | Corr 0.89 with H-009. Redundant. |
| H-018: Short-Term Reversal | 4% positive. Momentum dominates. |
| H-020: Funding Rate Dispersion | 0% positive. Rates too correlated. |
| H-022: Amihud Illiquidity | 0% positive. No illiquidity premium in crypto. |
| H-023: Price-Volume Confirmation | Corr 0.864 with H-012. Redundant. |
| H-025: Skewness Factor | 15% positive. No edge. |
| H-026: Drawdown Distance | Corr 0.682 with H-012. Redundant. |
| H-027: Lead-Lag XS | 1% positive. Not exploitable at 1h. |
| H-028: Volume Trend Change | 6% positive. Fails WF. |
| H-029: Hourly XS Momentum | Corr 0.484 with H-012. Redundant. |
| H-033: Idiosyncratic Momentum | Corr 0.832 with H-012. Fails WF. |
| H-034: Funding Rate BTC Timing | 49% positive (noise). No edge. |
| H-035: Momentum + Vol Timing | WF 3/4, mean 0.76. Enhancement only. |
| H-036: Intraday Seasonality | Real patterns but untradeable (Sharpe 0.30 max). |
| H-040: Vol Regime Factor Timing | Negative OOS. Doesn't help. |
| H-041: BTC Dominance Rotation | 100% look-ahead bias. 1/16 params positive. |
| H-043: OI Change XS Factor | 34% IS positive. Fails WF. |
| H-047: Volatility Change Factor | 50% positive = noise. No signal in vol dynamics. |
| H-048: Correlation Change Factor | 50% positive = noise. No signal in correlation dynamics. |
| H-050: Inter-Market Macro Signals | 50% positive = noise. Lagged corr all <0.08. Info priced in same-day. |
| H-051: Monthly Calendar Seasonality | DOM train/test corr -0.13. WF 3/6. No persistence. |
| H-086: Multi-TF Momentum | Corr 0.68 with H-012. Doesn't beat single 60d. |
| H-087: Amihud Illiquidity | Corr 0.92 with H-031 (size). Redundant. |
| H-088: TSMOM Portfolio | WF 2/6 param selection. 56% DD. Unreliable. |

## Confirmed Standalone (not in portfolio)
| Hypothesis | Metrics | Why Not In Portfolio |
|-----------|---------|---------------------|
| H-030: Composite Multi-Factor | Sharpe 2.05, +101.7% ann, 25% DD, WF 5/6 | Individual strategies beat composite |
| H-038: ML Factor Combo (Ridge) | Sharpe 1.43, +26.2% ann, 9.6% DD, WF 2/3 | Train window sensitive, fragile |
| H-042: Short-Term XSMom (20d) | Sharpe 1.17 IS, WF 4/6, mean OOS 0.55 | Corr 0.686 with H-012, redundant |
| H-045: OI-Volume Confirmation | Robust variant WF 3/4, rebal-sensitive | Not deployed, weak |

## Infrastructure Status
- Data fetcher: operational (ccxt, parquet caching)
- Metrics library: operational
- Backtest engine: operational
- **Paper trade runners**: 14 active (H-009, H-011, H-012, H-019, H-021, H-024, H-031, H-032, H-039, H-044, H-046, H-049, H-052, H-053)
- **Bug fix (session 44)**: Incomplete daily bar bug in all runners. Runners now drop today's incomplete bar before processing.
- **New data sources**: Bybit LSR (`data/all_assets_lsr_daily.parquet`), premium index (`data/all_assets_premium_daily.parquet`)
- Vol dynamics research: `strategies/vol_dynamics_research/`
- Premium research: `strategies/premium_research/`
- **Options IV surface collector**: `scripts/collect_iv_surface.py` — daily cron at 01:00 UTC, data in `data/iv_snapshots/`
- **Order book depth collector**: `scripts/collect_orderbook_depth.py` — daily cron at 01:30 UTC, data in `data/orderbook_snapshots/`
- Macro research: `strategies/macro_research/`

## Key Learnings
- 2024-2026 BTC: +1.8% total, 50% drawdown -- extremely hostile for directional strategies
- Daily EMA crossover is a real signal on BTC: OOS Sharpe 0.94, parameter robust (15/15 positive)
- **Funding rate arb at 5x leverage is viable**: OOS +25.4% annual, 0.14% DD, Sharpe 29.9
- **Cross-sectional momentum is a genuine signal**: 100% params positive, rolling OOS Sharpe 0.84
- **Low-volatility anomaly works in crypto**: 89% params positive, 5/8 WF folds, fee-robust
- **Volume momentum is a genuine cross-sectional signal**: 90% params positive, 6/6 WF (mean OOS 1.83)
- **Low-beta anomaly is stronger than low-vol**: 100% IS positive, 5/6 WF (mean 2.12)
- **5-strategy portfolio**: Sharpe 2.10, +31.6%, 12.9% DD — exceeds all targets
- **Day-of-week seasonality (H-039) is strongest signal found**: WF 6/6 (mean 2.46)
- **Price acceleration (H-046) is genuinely independent**: WF 4/4, near-zero corr with everything
- **OI-Price divergence (H-044)**: True IS Sharpe 1.01 (was 1.46 before bug fix). WF 3/4.
- **Long/short ratio sentiment (H-049)**: Contrarian signal — 100% params positive, Sharpe 2.58, 7.2% DD. BUT only 200 days of data. Genuinely new data source (first non-price/volume/OI signal).
- **Volatility change (H-047) has NO signal**: 50% positive = random noise. Vol dynamics not predictive cross-sectionally.
- **Correlation change (H-048) has NO signal**: 50% positive = random noise.
- **Incomplete daily bar bug**: Critical bug found and fixed. Runners were processing intra-day incomplete bars, causing stale signals. H-009 missed SHORT flip by ~1 day.
- **Macro signals (H-050) have NO predictive power**: SPY-BTC same-day corr +0.37, but lagged corr <0.08. Info fully priced in. 50% positive = noise across all lookbacks.
- **Monthly calendar effects (H-051) don't persist**: DOM train/test corr -0.13. Only DOW effects (H-039) work — likely need 100+ observations per bucket.
- **Premium index is a powerful contrarian signal (H-052)**: 100% IS positive, WF 6/6 (mean 1.86), split-half 2.18/2.95. Corr -0.14 with momentum — excellent diversifier. Assets with deepest perp discount (shorts aggressive) outperform.
- **Funding rate XS contrarian (H-053)**: 93% IS positive, WF 6/6 (mean OOS 2.29), split-half 1.31/1.91. Assets with lowest funding rate outperform. Corr 0.36 with H-052 (moderate overlap — both measure positioning). Without ATOM still Sharpe 1.22.
- **Liquidation data not accessible**: Bybit has no public historical liquidation endpoint. Only via WebSocket real-time stream.
- **H-055 stress test (session 54)**: Portfolio is highly robust. P(1yr loss)=0% across 5000 Monte Carlo sims. Correlations DON'T break during stress (0.041 in stress vs 0.044 overall). Positive in all regimes (uptrend/downtrend/deep DD). 88% positive months. Static weights outperform all adaptive approaches tested. H-011 is the critical strategy (Sharpe drops from 5.13→3.64 without it). H-009 has slightly negative marginal value. H-046 is the only weakness (Sharpe -0.87 in downtrend).
- **53 hypotheses tested**: 14 in paper trade + 1 comparison + 1 manual, 40 rejected, 3 confirmed standalone + 1 weak.
- Fee drag critical at 1h; daily/3-day/5-day/21-day rebalance minimizes fee impact
- **Research: Bybit API rich data sources**: Premium index (exploited in H-052), options IV (collecting), order book depth (collecting), LSR (exploited in H-049).
- **Options IV surface data collection started**: BTC/ETH/SOL/XRP/DOGE daily snapshots. ATM IV levels: BTC ~46-52%, ETH ~63-75%, SOL ~70-79%, DOGE ~67-96%. After 60-90 days of collection, options-based cross-sectional signals become backtestable.
- **Order book depth collection started**: 14 assets daily snapshots. Bid/ask imbalance at 5/10/25 levels. After ~60-90 days, microstructure signals become backtestable.
