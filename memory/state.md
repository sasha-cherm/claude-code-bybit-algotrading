# Strategy State

## Bybit Demo Account (LIVE since 2026-03-20, H-056 since 2026-03-23)

**Account**: $100k USDT demo. H-056 v2 deployed via hourly cron rebalancing.
**Architecture**: `scripts/demo_portfolio_runner.py` reads all strategy state.json files, computes net H-056 weighted positions with per-strategy leverage, rebalances on Bybit demo after each `run_all_paper_trades.py` run.
**H-056 weights (v2)**: H-031(30%,3x) H-052(23%,3x) H-053(16%,3x) H-021(15%,3x) H-039(10%,1x) H-049(6%,3x)
**v2 change (session 90)**: Replaced H-046 with H-049. H-046 had 4/4 position overlap with H-021 (redundant). H-049 has better diversification (neg corr with H-031).
**Dropped**: H-011 (funding arb), H-009 (BTC trend), H-046 (redundant with H-021)
**Bybit account leverage**: 10x (changed from 3x in session 83 to fix margin — only affects IM, not exposure)
**Gross leverage**: ~3.0x actual. All perp, no spot.

### Current Demo Status (as of 2026-04-15 session 207):
Demo eq: ~$98,190 (-1.81%). BTC spot ~$74,271. 13 open positions.

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
- **Position**: IN TRADE — Trade 2 expires Apr 10 08:00 UTC (~7h away).
  - Trade 1: Sold 73000C + 69000P, 0.1403 contracts. Net P&L: +$77.64 (+0.78%).
  - Trade 2: Sold 69000C + 65000P, 0.1496 contracts, $189.93 premium, entry BTC $66,866.
    - BTC at $71,966: Call ITM ($435 liability), hedge PnL -$236, fees $33. **Expected loss ~-$514.**
- **Mark equity**: ~$9,563 (-4.37%) — trade 2 underwater due to BTC rally through call strike.
- **Runner**: `paper_trades/h063_vol_selling/runner.py`
- **Backtest**: Sharpe 1.54, +52.5% ann, -18.4% DD, 73% WR. WF 6/6 positive. 60/60 params positive.
- **Logic**: Sell 7-day 3% OTM BTC strangle, delta-hedge daily, 10% stop
- **Next**: Trade 2 settles Apr 10 08:00 UTC. Expected loss ~$514 on this trade. Cron will enter trade 3 after settlement.
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

### H-250: US Session Momentum Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-05) — novel institutional flow signal
- **Position**: 6 positions (3 long, 3 short)
  - LONG (high US share): OP, NEAR, SOL
  - SHORT (low US share): XRP, ATOM, ADA
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h250_session_momentum/runner.py`
- **Params**: LB20_R7_N3 (20-day avg US session share, 7-day rebalance, top/bottom 3, high_us_long)
- **Next rebal**: Apr 11 bar
- **Backtest**: IS 96.7% (29/30), best Sharpe 1.057. WF 5/5 mean 1.197. Corr 0.032 H-012, 0.378 H-031, -0.227 H-076.

### H-255: Risk-Adjusted Momentum / Rolling Sharpe Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-05) — quality momentum signal
- **Position**: 6 positions (3 long, 3 short)
  - LONG (high Sharpe): DOGE, ETH, LINK
  - SHORT (low Sharpe): ATOM, XRP, DOT
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h255_sharpe_momentum/runner.py`
- **Params**: LB14_R7_N3 (14-day rolling Sharpe, 7-day rebalance, top/bottom 3, high_sharpe_long)
- **Next rebal**: Apr 11 bar
- **Backtest**: IS 93.3% (28/30), best Sharpe 1.552. WF 5/6 mean 0.964. Corr 0.460 H-012.

### H-259: Extreme Move Frequency Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-06) — novel tail risk signal
- **Position**: 8 positions (4 long, 4 short)
  - LONG (high extreme freq): OP, ATOM, ARB, DOT
  - SHORT (low extreme freq): ADA, LINK, AVAX, NEAR
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h259_extreme_moves/runner.py`
- **Params**: LB20_R7_N4 (20-day extreme freq, 7-day rebalance, top/bottom 4, high_long)
- **Next rebal**: Apr 11 bar
- **Backtest**: IS 100% (30/30), best Sharpe 2.648. WF 5/6 mean 1.320. Corr 0.272 H-012.

### H-263: Relative Strength vs BTC Factor (13 Non-BTC Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-06) — best WF ever (6/6, mean 4.058)
- **Position**: 6 positions (3 long, 3 short)
  - LONG (BTC outperformers): NEAR, OP, AVAX
  - SHORT (BTC underperformers): DOT, SOL, SUI
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h263_relative_strength/runner.py`
- **Params**: LB10_R3_N3 (10-day relative return vs BTC, 3-day rebalance, top/bottom 3, high_long)
- **Next rebal**: Apr 7 bar
- **Backtest**: IS 100% (30/30), best Sharpe 4.087. WF 6/6 mean 4.058. Corr 0.338 H-012.

### H-264: Return Skewness Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-06) — crypto-specific skewness signal
- **Position**: 6 positions (3 long, 3 short)
  - LONG (high positive skew): DOT, ADA, NEAR
  - SHORT (low skew): OP, ARB, BTC
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h264_skewness/runner.py`
- **Params**: LB60_R3_N3 (60-day return skewness, 3-day rebalance, top/bottom 3, high_long)
- **Next rebal**: Apr 7 bar
- **Backtest**: IS 91.7% (22/24), best Sharpe 1.879. WF 6/6 mean 1.532. Corr 0.400 H-012.

### H-277: VWAP Deviation Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-06) — volume-weighted momentum variant
- **Position**: 6 positions (3 long, 3 short)
  - LONG (above VWAP / demand pressure): BTC, ETH, ARB
  - SHORT (below VWAP / supply pressure): XRP, SUI, DOT
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h277_vwap_deviation/runner.py`
- **Params**: LB20_R7_N3 (20-day VWAP, 7-day rebalance, top/bottom 3, above_vwap_long)
- **Next rebal**: Apr 12 bar
- **Backtest**: IS 80.0% (24/30), best Sharpe 1.384. WF 5/6 mean 1.256. Neighboring 87.5%. Corr 0.464 H-012, 0.112 H-076.

### H-324: ADX-Filtered Multi-Asset TSMOM (Vol-Scaled) — NEW
- **Status**: LIVE paper trade (started 2026-04-07) — first multi-asset TS strategy
- **Position**: FLAT — BTC ADX < 30, waiting for trending market
- **Mark equity**: $10,000 (0.00%)
- **Runner**: `paper_trades/h324_adx_tsmom/runner.py`
- **Params**: LB60_ADX30_R7 (60-day momentum, ADX threshold 30, 7-day rebalance, 15% target vol)
- **Logic**: Per-asset TS momentum (long if 60d ret > 0, short if < 0), vol-scaled, only active when BTC ADX > 30
- **Next rebal**: When ADX crosses above 30 on next daily bar
- **Backtest**: IS 65.6% (full grid), best Sharpe 1.206, +12.7% ann, -8.0% DD, 60% exposure. WF 4/5 (mean 0.557). Split-half 2.107/0.834. Neighbors 77.5% positive. Corr 0.216 H-012, 0.414 H-009, 0.023 H-076.

### H-332: Bar Consistency Score (4h Microstructure) — NEW
- **Status**: LIVE paper trade (started 2026-04-07) — novel 4h signal
- **Position**: 6 positions (3 long, 3 short)
  - LONG: ARB, ETH, XRP
  - SHORT: AVAX, SOL, SUI
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h332_bar_consistency/runner.py`
- **Params**: LB10_R3_N3 (10-day avg consistency, 3-day rebalance, top/bottom 3, high_long)
- **Backtest**: IS 100% high_long (24/24), best Sharpe 2.437. WF 6/6 mean 1.961. Corr 0.147 H-012, 0.111 H-076.

### H-336: Volume Surprise Factor — NEW
- **Status**: LIVE paper trade (started 2026-04-07) — best diversifier ever found
- **Position**: 8 positions (4 long, 4 short)
  - LONG: ADA, ARB, AVAX, LINK
  - SHORT: BTC, DOGE, DOT, NEAR
- **Mark equity**: $9,976 (-0.24%) — day 0, fees only.
- **Runner**: `paper_trades/h336_volume_surprise/runner.py`
- **Params**: LB30_R3_N4 (30-day avg vol, 3-day rebalance, top/bottom 4, high_long)
- **Backtest**: IS 100% high_long (18/18), best Sharpe 2.766. WF 6/6 mean 2.684. Corr 0.003 H-012, 0.038 H-076. **Near-zero correlation with all existing strategies.**

### H-333: Smart Volume Return (4h Microstructure) — NEW
- **Status**: LIVE paper trade (started 2026-04-08) — informed-flow signal
- **Position**: LONG ADA/AVAX/BTC, SHORT DOT/LINK/NEAR
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h333_smart_vol_return/runner.py`
- **Params**: LB10_R3_N3_high_long. WF 6/6 mean 2.467. Corr 0.428 H-012.

### H-338: VW Directional Pressure (Hourly) — NEW
- **Status**: LIVE paper trade (started 2026-04-08)
- **Position**: LONG ARB/BTC/ETH/SUI, SHORT ATOM/DOT/LINK/NEAR
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h338_vw_pressure/runner.py`
- **Params**: LB10_R3_N4_high_long. WF 6/6 mean 2.390. Corr 0.289 H-012.

### H-342: Volume-Price Synchronicity (Hourly) — NEW
- **Status**: LIVE paper trade (started 2026-04-08) — excellent diversifier
- **Position**: LONG BTC/ETH/LINK/SOL, SHORT ATOM/NEAR/SUI/XRP
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h342_vp_sync/runner.py`
- **Params**: LB10_R5_N4_high_long. WF 5/6 mean 1.175. Corr 0.273 H-012, **0.004 H-076**.

### H-343: Intraday Momentum Decay (4h) — NEW
- **Status**: LIVE paper trade (started 2026-04-08) — best WF ever
- **Position**: LONG ETH/NEAR/OP, SHORT ADA/AVAX/DOT
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h343_momentum_decay/runner.py`
- **Params**: LB10_R3_N3_high_long. WF **6/6 mean 4.163** (best ever). Corr 0.225 H-012.

### H-351: Volume Profile Skewness (Hourly) — NEW
- **Status**: LIVE paper trade (started 2026-04-08) — novel microstructure signal
- **Position**: LONG BTC/OP/XRP, SHORT AVAX/LINK/SUI
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h351_vol_skew/runner.py`
- **Params**: LB30_R5_N3_low_long. WF 5/6 mean 1.339. Corr 0.179 H-012, -0.063 H-076.

### H-353: Volume Persistence (Hourly) — NEW
- **Status**: LIVE paper trade (started 2026-04-08) — outstanding WF
- **Position**: LONG AVAX/BTC/NEAR/XRP, SHORT ADA/LINK/OP/SUI
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h353_vol_persistence/runner.py`
- **Params**: LB5_R3_N4_high_long. WF 5/6 mean **2.526**. Corr 0.196 H-012, -0.030 H-076.

### H-355: Hourly Return Entropy — NEW
- **Status**: LIVE paper trade (started 2026-04-08) — near-zero correlation
- **Position**: LONG ADA/AVAX/ETH, SHORT BTC/NEAR/XRP
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h355_entropy/runner.py`
- **Params**: LB14_R3_N3_low_long. WF 5/6 mean 1.684. Corr **0.079** H-012, **-0.020** H-076.

### H-363: Multi-Day Return Pattern Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-08) — novel direction persistence signal
- **Position**: 6 positions (3 long, 3 short)
  - LONG: AVAX, ETH, LINK
  - SHORT: DOT, NEAR, OP
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h363_multiday_pattern/runner.py`
- **Params**: LB30_R3_N3_high_long. WF 5/6 mean 0.611. Corr 0.322 H-012, 0.138 H-076.

### H-388: Night-Day Return Differential (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-09) — marginal confirmation
- **Position**: 6 positions (3 long, 3 short)
  - LONG: DOT, NEAR, OP
  - SHORT: DOGE, ETH, SOL
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h388_night_day_diff/runner.py`
- **Params**: LB30_R5_N3_high_long. WF 4/6 mean 0.358. Corr 0.040 H-012.

### H-394: Intraday Variance Ratio (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-09) — strongest session 167 signal
- **Position**: 8 positions (4 long, 4 short)
  - LONG: ATOM, BTC, OP, SUI
  - SHORT: ADA, AVAX, NEAR, XRP
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h394_variance_ratio/runner.py`
- **Params**: LB10_R3_N4_high_long. WF 4/6 mean 0.351. Split-half 0.932/0.958 PASS. Corr **0.027** H-012.

### H-404: Session Flow Imbalance (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-09) — look-ahead-free, near-zero H-012 corr
- **Position**: 8 positions (4 long, 4 short)
  - LONG: XRP, BTC, ETH, ADA
  - SHORT: OP, DOT, ATOM, NEAR
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h404_session_flow/runner.py`
- **Params**: LB20_R3_N4_low_session_imbalance_long. WF 5/6 mean 0.658. Corr **0.008** H-012.

### H-411: OBV Slope (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-09) — lagged, no look-ahead
- **Position**: 6 positions (3 long, 3 short)
  - LONG: ARB, LINK, AVAX
  - SHORT: OP, SOL, XRP
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h411_obv_slope/runner.py`
- **Params**: LB15_R7_N3_high_obv_long. WF 6/6 mean 0.886. Corr **0.267** H-012.

### H-414: Volume Trend (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-09) — lagged, no look-ahead. **Session standout.**
- **Position**: 8 positions (4 long, 4 short)
  - LONG: ARB, LINK, AVAX, ADA
  - SHORT: DOGE, OP, DOT, SOL
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h414_vol_trend/runner.py`
- **Params**: LB15_R3_N4_high_voltrd_long. WF 5/6 mean **2.437**. Corr **0.028** H-012 — excellent diversifier.

### H-435: Hourly Return Kurtosis (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-09) — hourly-derived signal
- **Position**: 8 positions (4 long, 4 short)
  - LONG: ETH, AVAX, LINK, SOL
  - SHORT: OP, NEAR, DOT, ATOM
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h435_hourly_kurtosis/runner.py`
- **Params**: LB20_R3_N4_high_long. WF 4/6 mean 1.367. Corr 0.106 H-012.

### H-437: HL Spread Proxy (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-09) — negative H-012 corr
- **Position**: 8 positions (4 long, 4 short)
  - LONG: BTC, ATOM, XRP, LINK
  - SHORT: ARB, SUI, OP, NEAR
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h437_hl_spread/runner.py`
- **Params**: LB30_R5_N4_low_long. WF 5/6 mean 1.049. Corr **-0.183** H-012 — negative, excellent diversifier.

### H-445: Max Hourly Drawdown Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-09) — negative H-012 corr!
- **Position**: 6 positions (3 long, 3 short)
  - LONG (resilient, low DD): BTC, XRP, ATOM
  - SHORT (fragile, high DD): AVAX, OP, SUI
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h445_max_hourly_dd/runner.py`
- **Params**: LB30_R5_N3_low_long. WF 5/6 mean 1.500. Corr **-0.200** H-012 — NEGATIVE, excellent diversifier.

### H-447: Volume Autocorrelation Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-09) — near-zero H-012 corr
- **Position**: 6 positions (3 long, 3 short)
  - LONG (institutional patterns): BTC, NEAR, XRP
  - SHORT (erratic volume): DOT, ADA, SUI
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h447_vol_autocorr/runner.py`
- **Params**: LB15_R3_N3_high_long. WF 4/6 mean 0.859. Corr **0.039** H-012.

### H-451: Close-to-High Ratio Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-09) — buying pressure signal
- **Position**: 6 positions (3 long, 3 short)
  - LONG (closes near highs): NEAR, ETH, OP
  - SHORT (closes near lows): ATOM, ADA, XRP
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h451_close_high_ratio/runner.py`
- **Params**: LB30_R5_N3_high_long. WF 5/6 mean 1.366. Corr 0.258 H-012.

### H-470: First-Hour Return Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-09) — opening hour predicts
- **Position**: 8 positions (4 long, 4 short)
  - LONG (strong openers): AVAX, ADA, DOT, NEAR
  - SHORT (weak openers): DOGE, SOL, ATOM, XRP
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h470_first_hour_ret/runner.py`
- **Params**: LB20_R7_N4_high_long. WF 4/6 mean 0.365. SH PASS (1.665/0.411). Corr 0.267 H-012.

### H-496: ML Ensemble (Focused Equal-Weight 10-Factor Composite) — NEW
- **Status**: LIVE paper trade (started 2026-04-09) — **best backtest Sharpe ever found**
- **Position**: 8 positions (4 long, 4 short)
  - LONG: NEAR, BTC, ETH, LINK
  - SHORT: DOT, DOGE, SOL, OP
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h496_ml_ensemble/runner.py`
- **Params**: 10 factors, equal-weight z-score, R5_N4. WF 5/6 mean **2.189**. SH PASS (2.555/1.655).
- **Logic**: Average z-scores from momentum, low_vol, size, premium, vol_term, dd_momentum, efficiency, turnover, vol_surprise, vw_pressure. Rank composite. Long top 4, short bottom 4.
- **Backtest**: Sharpe **2.149**, +98.7% annual, -23.8% DD. Param robustness 12/12 positive. Corr 0.547 H-012.
- **Note**: Equal weight beats ML methods (ridge, IC-weighted). Most recent WF fold (Jan-Apr 2026) essentially flat (-0.049).

### H-528: Range Expansion Momentum Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-10) — 100% param robust, zero H-012 corr
- **Position**: 8 positions (4 long, 4 short)
  - LONG: AVAX, ARB, SUI, DOT
  - SHORT: ETH, OP, XRP, DOGE
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h528_range_expansion/runner.py`
- **Params**: SW5_LW30_R5_N4 (5-day short range, 30-day long range, 5-day rebalance, top/bottom 4, high_range_expansion_long)
- **Backtest**: IS Sharpe 0.849, +36.8% ann, -37.5% DD. WF 4/6. SH PASS (1.502/0.164). **100% param robust (96/96)**. Best config (3,30,3,3) Sharpe 2.021.
- **Correlation**: **-0.001** H-012, -0.052 H-031, 0.029 H-076, 0.069 H-182. Perfect diversifier.
- **Note**: Captures breakout dynamics — coins with expanding daily range tend to continue trending.

### H-535: BTC Intraday Session Momentum — NEW
- **Status**: LIVE paper trade (started 2026-04-10) — first validated BTC TS strategy
- **Position**: SHORT 0.070 BTC @ $71,787 (yesterday's first 6h was -0.12%)
- **Mark equity**: $9,998 (-0.02%) — day 0.
- **Runner**: `paper_trades/h535_intraday_momentum/runner.py`
- **Params**: 6h lookback, 50% capital, daily rebalance.
- **Backtest**: IS Sharpe 0.735, +39.3% ann, -54.8% DD. WF **6/8** mean **1.051**. SH PASS (0.985/1.245).
- **Correlation**: **0.111** H-009 — low despite both trading BTC. 0.195 H-539.
- **Note**: 100% exposure. First BTC time-series strategy with genuine OOS validation.

### H-539: BTC Keltner Channel Breakout — NEW
- **Status**: LIVE paper trade (started 2026-04-10) — selective trend breakout
- **Position**: FLAT — BTC inside Keltner Channel (EMA30 ± 2.5*ATR30).
- **Mark equity**: $10,000 (+0.00%) — day 0.
- **Runner**: `paper_trades/h539_keltner_breakout/runner.py`
- **Params**: EMA30, ATR30, mult 2.5. Only trades breakouts (~15% exposure).
- **Backtest**: IS Sharpe 0.832, +20.2% ann, -26.2% DD. WF **5/7** mean **0.751**. SH PASS (0.691/0.959). Param robust 83%.
- **Correlation**: 0.453 H-009, 0.124 H-544.
- **Note**: Selective — only active during strong breakouts. Currently flat (price inside channel).

### H-544: BTC Range Squeeze Breakout — NEW
- **Status**: LIVE paper trade (started 2026-04-10) — 100% param robust, near-zero correlation
- **Position**: LONG 0.070 BTC @ $71,765 — ATR in 8.3rd percentile (SQUEEZE detected).
- **Mark equity**: $9,998 (-0.02%) — day 0.
- **Runner**: `paper_trades/h544_range_squeeze/runner.py`
- **Params**: ATR(20), 60d percentile window, squeeze < 10th percentile.
- **Backtest**: IS Sharpe 0.986, +23.0% ann, -23.2% DD. WF **5/8** mean **0.470**. SH PASS (1.235/0.427). Param robust **100%** (36/36).
- **Correlation**: **0.109** H-009, **0.124** H-539 — near-zero with everything.
- **Note**: Entered LONG immediately — current market IS in a squeeze. 100% param robustness.

### H-571: SOL Intraday Session Momentum — NEW
- **Status**: LIVE paper trade (started 2026-04-10) — first SOL TS strategy
- **Position**: SHORT 59.5 SOL @ $84.03 (yesterday's first 6h was -0.52%)
- **Mark equity**: $9,998 (-0.02%) — day 0.
- **Runner**: `paper_trades/h571_sol_session_momentum/runner.py`
- **Params**: 6h lookback, 50% capital, daily rebalance.
- **Backtest**: IS Sharpe **0.847**, Ann +42.8%, DD 77.5%. WF **6/7** mean **0.848**. SH PASS (0.679/1.060). Param robust **12/12 (100%)**.
- **Correlation**: **-0.092** BTC — excellent diversifier. Same intraday momentum pattern as BTC H-535 but works even better on SOL.
- **Note**: First non-BTC time-series strategy. Negative BTC correlation provides genuine diversification.

### H-599: RSI Cross-Sectional Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-10) — 100% param robust
- **Position**: 8 positions (4 long, 4 short)
  - LONG (high RSI): NEAR, ARB, ATOM, ETH
  - SHORT (low RSI): ADA, XRP, DOT, SOL
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h599_rsi_xs/runner.py`
- **Params**: RSI(14), R5_N4. IS Sharpe 1.148. WF 4/6 mean 0.977. SH PASS (1.621/0.544).
- **Param robust**: **60/60 (100%)**, best 2.306.
- **Correlation**: 0.455 H-012 (borderline but passing), 0.175 H-059, -0.019 H-076.

### H-601: Volume Decline Rate Factor (14 Assets) — NEW
- **Status**: LIVE paper trade (started 2026-04-10) — 100% param robust, near-zero H-012 corr
- **Position**: 8 positions (4 long, 4 short)
  - LONG (rising volume): ARB, LINK, AVAX, ADA
  - SHORT (falling volume): DOGE, OP, SOL, DOT
- **Mark equity**: $9,976 (-0.24%) — day 0.
- **Runner**: `paper_trades/h601_vol_decline/runner.py`
- **Params**: LB20_R5_N4. IS Sharpe 0.965. WF 4/6 mean 1.482. SH PASS (0.731/1.321).
- **Param robust**: **60/60 (100%)**, best 1.843.
- **Correlation**: **0.054** H-012 (near-zero), 0.254 H-059, **-0.212** H-076 (negative — excellent diversifier).

### H-617: BTC 4h Volume Breakout — NEW
- **Status**: LIVE paper trade (started 2026-04-11) — first 4h timeframe strategy
- **Position**: FLAT (no volume surge signal yet at entry)
- **Mark equity**: $10,000 (+0.00%) — just deployed.
- **Runner**: `paper_trades/h617_4h_vol_breakout/runner.py`
- **Params**: mom_period=12 (48h), vol_mult=1.5. IS Sharpe 0.971, Ann +43.6%, DD 53.4%. WF 6/8 mean 0.425. SH PASS (0.425/0.575).
- **Param robust**: **14/16 (88%)**.
- **Correlation**: 0.292 H-009 (moderate), -0.190 BTC buy&hold (negative — good diversifier).

### H-657: BTC Realized Skew — NEW
- **Status**: LIVE paper trade (started 2026-04-11) — distributional signal strategy
- **Position**: FLAT (skew 0.110, between thresholds ±0.5)
- **Mark equity**: $10,000 (+0.00%) — just deployed.
- **Runner**: `paper_trades/h657_realized_skew/runner.py`
- **Params**: lookback=30, long_thresh=0.5, short_thresh=-0.5. IS Sharpe **0.947**, Ann +32.5%, DD 48.1%. WF **5/6** mean 1.46. SH PASS (0.624/1.524).
- **Param robust**: **98%** (48/49 positive).
- **Correlation**: **0.052** H-012 (near-zero), 0.404 H-009 (moderate), 0.120 BTC direction.
- **Logic**: Trades based on 30-day return distribution shape — positive skew (>0.5) → long, negative skew (<-0.5) → short. Long 30%, Short 15%, Flat 55%.

### H-676: BTC Consecutive Day Contrarian — NEW
- **Status**: LIVE paper trade (started 2026-04-11) — mean reversion, negative H-012 corr
- **Position**: FLAT (last 3 days: -1.19%, +1.01%, +1.62% = MIXED)
- **Mark equity**: $10,000 (+0.00%) — just deployed.
- **Runner**: `paper_trades/h676_consecutive_contrarian/runner.py`
- **Params**: 3 consecutive days, 50% capital. IS Sharpe 1.308, WF **5/5**, SH 0.674/2.219.
- **Param robust**: **4/4 (100%)** — 2d (0.74), 3d (1.31), 4d (0.61), 5d (0.65).
- **Correlation**: H-012=**-0.039**, H-009=**-0.154** — negative with both momentum and trend.
- **Logic**: After 3+ consecutive up days → short. After 3+ consecutive down days → long. Exposure ~24%.

### H-677: BTC Crash Bounce — NEW
- **Status**: LIVE paper trade (started 2026-04-11) — excellent diversifier
- **Position**: FLAT (no crash detected, yesterday +1.62%)
- **Mark equity**: $10,000 (+0.00%) — just deployed.
- **Runner**: `paper_trades/h677_crash_bounce/runner.py`
- **Params**: threshold -3%, hold 2 days, 50% capital. Active Sharpe 1.610, WF **5/5**, SH 0.731/0.582.
- **Param robust**: **16/20 (80%)**.
- **Correlation**: H-012=**-0.166**, H-009=**-0.455** — strongly negative with trend, excellent diversifier.
- **Logic**: Buy BTC after >3% daily drop, hold 2 days. Exposure ~17%.

### H-679: BTC Vol Regime Switch — NEW
- **Status**: LIVE paper trade (started 2026-04-11) — strongest BTC TS strategy
- **Position**: LONG 0.069 BTC @ $72,800 (vol expanding + uptrend → momentum)
- **Mark equity**: $9,998 (-0.02%) — just deployed.
- **Runner**: `paper_trades/h679_vol_regime_switch/runner.py`
- **Params**: short_vol=5d, long_vol=30d, trend=5d. IS Sharpe **1.464**, WF 4/5, SH **1.825/1.042**.
- **Param robust**: **21/24 (88%)**.
- **Correlation**: H-012=**0.023**, H-009=**0.241**, H-676=0.101.
- **Logic**: Vol expanding → follow trend. Vol contracting → fade trend. Always in position. Ann 68.8%, DD -30.1%.

### H-680: Return-Volume Convergence XS — NEW
- **Status**: LIVE paper trade (started 2026-04-11) — volume-confirmed momentum
- **Position**: 8 positions (4 long, 4 short)
  - LONG: BTC, ETH, DOGE, ARB
  - SHORT: SOL, DOT, OP, ATOM
- **Mark equity**: $9,995 (-0.05%) — just deployed.
- **Runner**: `paper_trades/h680_vol_convergence/runner.py`
- **Params**: LB20_N4_R3. IS Sharpe **1.486**, WF 4/5, SH 1.835/1.039.
- **Param robust**: **27/30 (90%)**.
- **Correlation**: H-012=**0.264** — moderate but acceptable, captures volume-confirmed subset of momentum.
- **Logic**: Z-score(price_mom + volume_mom). L4/S4, 3-day rebalance. Long where price AND volume both rising.

### H-703: OI Surprise (Residual) XS — NEW
- **Status**: LIVE paper trade (started 2026-04-11) — OI-based residual signal
- **Position**: 6 positions (3 long, 3 short)
  - LONG: AVAX, ARB, SUI
  - SHORT: OP, NEAR, DOT
- **Mark equity**: $9,976 (-0.24%) — just deployed.
- **Runner**: `paper_trades/h703_oi_surprise/runner.py`
- **Params**: LB15_N3_R7. IS Sharpe **1.578**, WF 5/6 (mean 1.422), SH 1.409/1.332.
- **Param robust**: **25/30 (83%)**, all 6 R×N neighbors positive.
- **Correlation**: H-012=**-0.010** — near-zero (perfect diversifier).
- **Logic**: OI_pct_change(15) - Volume_pct_change(15). Low surprise (OI grows less than volume) outperforms. L3/S3, 7-day rebalance.

### H-726: Maximum Drawdown Factor XS — NEW
- **Status**: LIVE paper trade (started 2026-04-11)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: OP, DOT, NEAR, SUI (most beaten-down)
  - SHORT: ETH, LINK, XRP, DOGE (least beaten-down)
- **Mark equity**: $9,976 (-0.24%) — just deployed.
- **Runner**: `paper_trades/h726_max_dd_factor/runner.py`
- **Params**: W30_R5_N4. IS Sharpe **0.980**, WF **6/6 (PERFECT)**, SH 0.570/1.379.
- **Param robust**: **100%** (60/60). Median Sharpe 0.895.
- **Correlation**: H-012=0.332 (moderate).

### H-733: Dollar Volume Change XS — NEW
- **Status**: LIVE paper trade (started 2026-04-11)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: ARB, LINK, AVAX, ADA
  - SHORT: DOGE, SOL, OP, DOT
- **Mark equity**: $9,976 (-0.24%) — just deployed.
- **Runner**: `paper_trades/h733_dv_change/runner.py`
- **Params**: LB10_R5_N4. IS Sharpe **1.262**, WF 5/6, SH BORDERLINE.
- **Param robust**: **97%** (70/72).
- **Correlation**: H-012=**0.046** (near zero — excellent diversifier). H-021=0.540.

### H-736: Cumulative Volume Delta XS — NEW
- **Status**: LIVE paper trade (started 2026-04-11)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: ARB, NEAR, BTC, SUI (highest buy pressure)
  - SHORT: OP, XRP, SOL, DOGE (highest sell pressure)
- **Mark equity**: $9,976 (-0.24%) — just deployed.
- **Runner**: `paper_trades/h736_volume_delta/runner.py`
- **Params**: LB10_R5_N4. IS Sharpe **1.703**, WF **6/6 (PERFECT)**, SH corrected **PASS**.
- **Param robust**: **96%** (69/72).
- **Correlation**: H-012=0.366 (moderate).
- **Logic**: Buy fraction = (close-open)/(high-low). Cumulative signed volume / total volume.

### H-754: Lead-Lag Signal XS — NEW
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 6 positions (3 long, 3 short)
  - LONG: NEAR, OP, ATOM (lead BTC by 1 day)
  - SHORT: DOT, LINK, ADA (lag BTC)
- **Mark equity**: $9,976 (-0.24%) — just deployed.
- **Runner**: `paper_trades/h754_lead_lag/runner.py`
- **Params**: CW30_R3_N3. IS Sharpe 1.232, WF **4/4**, SH p=0.089. H-012 corr **-0.014**.

### H-759: ADX Trend Strength XS — NEW
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 6 positions (3 long, 3 short)
  - LONG: DOT, OP, ARB (strongest trends)
  - SHORT: ETH, LINK, DOGE (weakest trends)
- **Mark equity**: $9,976 (-0.24%) — just deployed.
- **Runner**: `paper_trades/h759_adx_trend/runner.py`
- **Params**: ADX14_R3_N3. IS Sharpe **1.723**, WF **5/5**, SH p=0.016. H-012 corr 0.064.

### H-761: Gap Signal XS — NEW
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: BTC, ETH, SOL, SUI (positive overnight gaps)
  - SHORT: NEAR, OP, ARB, ATOM (negative gaps)
- **Mark equity**: $9,976 (-0.24%) — just deployed.
- **Runner**: `paper_trades/h761_gap_signal/runner.py`
- **Params**: GW5_R1_N4. IS Sharpe **1.673**, WF **5/5**, SH p=0.019. H-012 corr 0.054.

### H-763: Momentum-Vol Ratio XS — NEW
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4 long, 4 short)
  - LONG: ARB, ETH, BTC, NEAR (highest SNR)
  - SHORT: OP, SOL, XRP, DOT (lowest SNR)
- **Mark equity**: $9,976 (-0.24%) — just deployed.
- **Runner**: `paper_trades/h763_mom_vol_ratio/runner.py`
- **Params**: M20_V20_R5_N4. IS Sharpe 1.239, WF 3/5, SH p=0.085. H-012 corr 0.027.

## Portfolio Summary (mark-to-market 2026-04-14 session 201)
- **Bybit Demo**: ~$98,190 (-1.81%, BTC $74,748).
- **Total internal MTM (179 runners)**: 179 runners (176+3 new). **94/176 positive** (53%). Avg PnL **+0.40%**.
- **Top performers**: H-049(+7.98%), H-277(+7.17%), H-353(+7.07%), H-754(+6.41%), H-332(+5.60%), H-169(+5.13%), H-496(+4.92%), H-085(+4.51%), H-193(+4.43%), H-435(+4.34%)
- **H-063**: ~$9,730 (-2.70%). Iron condor trade 3 (75K/71K, exp Apr 17) — BTC at $74,748.
- **Worst performers**: H-191(-6.51%), H-183(-6.16%), H-759(-6.11%), H-053(-5.38%), H-182(-5.01%)
- **Research (session 201)**: 24 new hypotheses (H-1124–H-1147). **3 deployed** (H-1127/H-1135/H-1137). **1147 total hypotheses.**
- **Key findings**: (1) Correlation structure signals FAIL in crypto XS — BTC corr, pairwise corr, downside corr all have massive SH collapse. (2) Lead-lag signals DON'T WORK — information propagates same-day. (3) Short-term extreme reversal IS a genuine factor (H-1135 star, Sharpe 1.836, WF 4/4, zero mom corr). (4) RSI is an independent momentum measure uncorrelated with 60d return momentum.
- **Meta-conclusions**: Crypto XS alpha comes from: momentum, size, volume dynamics, volatility structure, reversal extremes, RSI, and liquidity. Correlation-based and lead-lag signals fail. 1147 hypotheses tested, ~85 deployed as runners.
- **AUTOMATED:** Paper trades hourly via cron (179 runners). Claude sessions every 4h. IV collector running.
- **Next action:** Await Q-005 answer. Monitor 179 runners (esp. H-1135/H-1137/H-1127 new deploys). Explore on-chain data, sentiment APIs, ML ensembles.
- **Open user questions:** Q-005 (H-056 v3 portfolio upgrade proposal)

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

### H-768: Sequential Pattern Score XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 6 positions (3L/3S). LONG: ARB, BTC, NEAR. SHORT: XRP, SUI, OP.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h768_sequential_pattern/runner.py`
- **Params**: pattern_window=10, rebal=3, n_ls=3

### H-769: Multi-Horizon Divergence XS (Contrarian)
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: ARB, OP, ETH, LINK. SHORT: AVAX, XRP, SOL, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h769_multi_horizon_div/runner.py`
- **Params**: short=5d, long=20d, rebal=3, n_ls=4

### H-773: OI-Confirmed Momentum XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 6 positions (3L/3S). LONG: ETH, ARB, BTC. SHORT: ADA, DOT, OP.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h773_oi_confirmed_mom/runner.py`
- **Params**: mom=40d, oi=5d, rebal=3, n_ls=3

### H-777: Price-Volume Trend XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 6 positions (3L/3S). LONG: ETH, BTC, XRP. SHORT: OP, ATOM, SOL.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h777_pvt/runner.py`
- **Params**: pvt_window=30, rebal=3, n_ls=3

### H-778: Close Location Value XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: BTC, ARB, ETH, XRP. SHORT: LINK, ADA, NEAR, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h778_clv/runner.py`
- **Params**: clv_window=20, rebal=3, n_ls=4

### H-781: Signal Agreement XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 6 positions (3L/3S). LONG: NEAR, BTC, AVAX. SHORT: ADA, OP, ATOM.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h781_signal_agreement/runner.py`
- **Params**: 4 factor consensus, rebal=3, n_ls=3

### H-786: Volume-Confirmed Strength XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 6 positions (3L/3S). LONG: ARB, ETH, LINK. SHORT: XRP, ATOM, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h786_vol_confirmed/runner.py`
- **Params**: window=20, rebal=5, n_ls=3

### H-792: OI-Price Coherence XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 6 positions (3L/3S). LONG: SUI, AVAX, XRP. SHORT: DOGE, BTC, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h792_oi_price_coherence/runner.py`
- **Params**: corr_lb=7, rebal=7, n_ls=3

### H-810: Volume Trend Strength (Vol-ADX) XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: ARB, AVAX, DOGE, LINK. SHORT: BTC, OP, ATOM, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h810_vol_trend_strength/runner.py`
- **Params**: adx_lb=20, rebal=7, n_ls=4

### H-814: Rank Velocity XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: ETH, ARB, SOL, SUI. SHORT: BTC, ADA, DOT, ATOM.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h814_rank_velocity/runner.py`
- **Params**: lb=60, rebal=10, n_ls=4

### H-817: Cross-Asset Vol Spillover XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 10 positions (5L/5S). LONG: DOT, NEAR, OP, SUI, DOGE. SHORT: ETH, LINK, ATOM, XRP, BTC.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h817_vol_spillover/runner.py`
- **Params**: lb=60, rebal=7, n_ls=5

### H-824: Min Daily Return (Resilience) XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: BTC, XRP, NEAR, ARB. SHORT: ADA, LINK, AVAX, OP.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h824_min_return/runner.py`
- **Params**: lb=30, rebal=3, n_ls=4

### H-828: Top-5 Signal Ensemble XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: BTC, NEAR, DOGE, ARB. SHORT: SUI, OP, SOL, ATOM.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h828_signal_ensemble/runner.py`
- **Params**: lb=40, rebal=3, n_ls=4

### H-831: Volume-Confirmed Breakout XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: ARB, BTC, ETH, NEAR. SHORT: ATOM, XRP, ADA, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h831_vol_breakout/runner.py`
- **Params**: lb=30, rebal=3, n_ls=4

### H-837: Volume Turnover Rate XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 6 positions (3L/3S). LONG: ARB, NEAR, LINK. SHORT: ETH, XRP, SOL.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h837_vol_turnover/runner.py`
- **Params**: W=10, rebal=3, n_ls=3. IS Sharpe 1.958, WF 5/5. Novel turnover signal.

### H-843: Intraday Range-Vol Ratio XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: BTC, ETH, SOL, ARB. SHORT: SUI, XRP, NEAR, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h843_range_vol/runner.py`
- **Params**: W=30, rebal=7, n_ls=4. IS Sharpe 2.038, WF 5/5. Session 189 best signal.

### H-849: Underwater Volatility XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: NEAR, XRP, ETH, DOGE. SHORT: DOT, ADA, OP, ATOM.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h849_underwater_vol/runner.py`
- **Params**: W=30, rebal=5, n_ls=4. IS Sharpe 1.463, WF 4/5. H-012 corr 0.001 — perfect diversifier.

### H-851: Drawdown Mean Reversion XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 6 positions (3L/3S). LONG: ATOM, DOT, ADA. SHORT: ETH, BTC, ARB.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h851_dd_mean_reversion/runner.py`
- **Params**: W=60, rebal=3, n_ls=3. IS Sharpe 1.637, WF 3/4. Contrarian DD signal.

### H-854: Close Location Value XS
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: ARB, BTC, OP, ETH. SHORT: SOL, NEAR, ADA, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h854_clv/runner.py`
- **Params**: W=20, rebal=7, n_ls=4. IS Sharpe 1.267, WF 4/5. CLV as novel XS ranking signal.

### H-861: Downside Protection XS (session 190)
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 6 positions (3L/3S). LONG: XRP, DOT, ATOM. SHORT: OP, ADA, SUI.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h861_downside_protect/runner.py`
- **Params**: W=40, R=3, N=3. IS Sharpe 1.255, WF 3/4, SH p=0.085. H-012 corr -0.021.

### H-863: Win Rate XS (session 190)
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 6 positions (3L/3S). LONG: ETH, ARB, AVAX. SHORT: DOT, XRP, OP.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h863_win_rate/runner.py`
- **Params**: W=20, R=7, N=3. IS Sharpe 1.207, WF 4/5, SH p=0.093. H-012 corr -0.022.

### H-864: Conditional Momentum XS (session 190)
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: ARB, NEAR, ADA, AVAX. SHORT: ATOM, SOL, XRP, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h864_conditional_mom/runner.py`
- **Params**: W=20, R=5, N=4. IS Sharpe **1.608**, WF 4/5, SH p=0.025. H-012 corr **0.000** — zero! Session best novel signal.

### H-866: VW Return Divergence XS (session 190)
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: ARB, SUI, LINK, AVAX. SHORT: DOGE, ATOM, DOT, SOL.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h866_vw_return_div/runner.py`
- **Params**: W=20, R=3, N=4. IS Sharpe 1.591, WF 3/5, SH p=0.027. H-012 corr 0.005. Smart money signal.

### H-867: Max Gain Dependency XS (session 190)
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: ETH, ARB, ADA, BTC. SHORT: SUI, XRP, DOGE, SOL.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h867_max_gain_dep/runner.py`
- **Params**: W=40, R=7, N=4. IS Sharpe **1.766**, WF 3/4, SH p=0.015. H-012 corr 0.046. Highest Sharpe of batch.

### H-873: Distance from 20-Day High XS (session 190)
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: BTC, NEAR, ATOM, ETH. SHORT: OP, SOL, ADA, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h873_dist_from_high/runner.py`
- **Params**: W=20, R=7, N=4. IS Sharpe 1.391, WF 4/5, SH p=0.053. H-012 corr 0.023.

### H-878: Stochastic %K XS (session 190)
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: NEAR, ARB, BTC, ETH. SHORT: OP, DOGE, DOT, ADA.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h878_stochastic/runner.py`
- **Params**: P=14, R=7, N=4. IS Sharpe 1.406, WF 3/5, SH p=0.050. H-012 corr 0.005. Near-zero corr.

### H-882: Ease of Movement XS (session 190)
- **Status**: LIVE paper trade (started 2026-04-12)
- **Position**: 8 positions (4L/4S). LONG: BTC, ETH, SOL, NEAR. SHORT: OP, DOGE, ADA, AVAX.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h882_emv/runner.py`
- **Params**: P=10, R=7, N=4. IS Sharpe 1.383, WF 3/5, SH p=0.053. H-012 corr -0.009. Microstructure signal.

### H-891: Up/Down Day Ratio XS (session 191)
- **Status**: LIVE paper trade (started 2026-04-13)
- **Position**: 6 positions (3L/3S). LONG: ETH, ARB, AVAX. SHORT: DOT, XRP, OP.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h891_up_down_ratio/runner.py`
- **Params**: P=20, R=5, N=3. IS Sharpe 1.233, WF 4/5, SH p=0.087. H-012 corr 0.015.

### H-892: Volume Acceleration XS (session 191)
- **Status**: LIVE paper trade (started 2026-04-13)
- **Position**: 6 positions (3L/3S). LONG: ARB, DOGE, AVAX. SHORT: ADA, OP, SOL.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h892_vol_acceleration/runner.py`
- **Params**: S7/L30, R=7, N=3. IS Sharpe 1.455, WF 3/4, SH p=0.045. H-012 corr -0.026.

### H-894: Volume-Price Correlation XS (session 191)
- **Status**: LIVE paper trade (started 2026-04-13)
- **Position**: 6 positions (3L/3S). LONG: SUI, OP, AVAX. SHORT: ARB, SOL, DOGE.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h894_vol_price_corr/runner.py`
- **Params**: P=14, R=5, N=3. IS Sharpe 1.314, WF 4/5, SH p=0.067. H-012 corr 0.048.

### H-898: Cumulative Volume Divergence XS (session 191)
- **Status**: LIVE paper trade (started 2026-04-13)
- **Position**: 6 positions (3L/3S). LONG: ARB, DOGE, OP. SHORT: AVAX, ATOM, SOL.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h898_cum_vol_div/runner.py`
- **Params**: S3/L20, R=3, N=3. IS Sharpe 1.713, WF 4/5, SH p=0.018. H-012 corr -0.008. Strong accumulation signal.

### H-899: Volume Trend Persistence XS (session 191) — SESSION BEST
- **Status**: LIVE paper trade (started 2026-04-13)
- **Position**: 8 positions (4L/4S). LONG: BTC, ARB, DOGE, ETH. SHORT: ATOM, XRP, OP, NEAR.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h899_vol_trend_persist/runner.py`
- **Params**: P=20, R=7, N=4. IS Sharpe 1.560, WF **5/5 PERFECT**, SH p=0.030. H-012 corr -0.048.

### H-900: Timeframe Consistency XS (session 191)
- **Status**: LIVE paper trade (started 2026-04-13)
- **Position**: 8 positions (4L/4S). LONG: ETH, ARB, NEAR, BTC. SHORT: LINK, OP, DOT, ADA.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h900_tf_consistency/runner.py`
- **Params**: R=7, N=4. IS Sharpe 1.460, WF 3/4, SH p=0.044. H-012 corr -0.004. Multi-timeframe confirmation.

### H-902: Momentum Quality XS (session 191)
- **Status**: LIVE paper trade (started 2026-04-13)
- **Position**: 6 positions (3L/3S). LONG: ARB, NEAR, BTC. SHORT: XRP, ADA, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h902_momentum_quality/runner.py`
- **Params**: P=14, R=7, N=3. IS Sharpe 1.598, WF 3/5, SH p=0.026. H-012 corr -0.017. Risk-adjusted momentum.

### H-1077: Rank Change Momentum XS (session 199)
- **Status**: LIVE paper trade (started 2026-04-14)
- **Position**: 8 positions (4L/4S). LONG: OP, ADA, ATOM, ARB. SHORT: ETH, XRP, BTC, SOL.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h1077_rank_change_mom/runner.py`
- **Params**: R=5, N=4. IS Sharpe 1.390, WF 3/4, SH p=0.053. H-012 corr -0.031. Rising XS rank = improving.

### H-1078: Outperformance Consistency XS (session 199)
- **Status**: LIVE paper trade (started 2026-04-14)
- **Position**: 6 positions (3L/3S). LONG: ETH, BTC, ARB. SHORT: AVAX, DOT, OP.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h1078_outperf_consistency/runner.py`
- **Params**: R=7, N=3. IS Sharpe 1.239, WF 3/4, SH p=0.084. H-012 corr -0.014. Very stable SH (1.27/1.22).

### H-1081: Relative Volume Surprise XS (session 199) — SESSION BEST
- **Status**: LIVE paper trade (started 2026-04-14)
- **Position**: 8 positions (4L/4S). LONG: ARB, DOT, BTC, OP. SHORT: ADA, AVAX, ATOM, SOL.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h1081_rel_vol_surprise/runner.py`
- **Params**: R=7, N=4. IS Sharpe **1.923**, WF **4/4 PERFECT**, SH p=**0.007**. H-012 corr 0.043. SH 1.97/1.90 (remarkable stability). Volume surge relative to XS peers.

### H-1087: Return Kurtosis XS (session 199)
- **Status**: LIVE paper trade (started 2026-04-14)
- **Position**: 8 positions (4L/4S). LONG: AVAX, LINK, BTC, ADA. SHORT: SUI, NEAR, ATOM, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h1087_return_kurtosis/runner.py`
- **Params**: R=7, N=4, low_long. IS Sharpe 1.198, WF 3/4, SH p=0.097. H-012 corr 0.019. Thin-tailed returns outperform.

### H-1090: Consecutive Extreme Frequency XS (session 199)
- **Status**: LIVE paper trade (started 2026-04-14)
- **Position**: 6 positions (3L/3S). LONG: BTC, OP, NEAR. SHORT: AVAX, ARB, ATOM.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h1090_consec_extreme/runner.py`
- **Params**: R=7, N=3. IS Sharpe **2.397**, IS 100%, WF 3/4, SH p=**0.001**. H-012 corr -0.023. Vol clustering → trending.

### H-1091: Overnight Return Share XS (session 199)
- **Status**: LIVE paper trade (started 2026-04-14)
- **Position**: 8 positions (4L/4S). LONG: BTC, ETH, SOL, SUI. SHORT: NEAR, OP, ARB, ATOM.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h1091_overnight_share/runner.py`
- **Params**: R=7, N=4. IS Sharpe **1.905**, IS 100%, WF **4/4 PERFECT**, SH p=**0.008**. H-012 corr -0.016. Overnight accumulation signal.

### H-1100: Amihud Illiquidity XS (session 200)
- **Status**: LIVE paper trade (started 2026-04-14)
- **Position**: 8 positions (4L/4S). Initial entry.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h1100_amihud_illiq/runner.py`
- **Params**: R=5, N=4, dir=low_long. IS Sharpe **1.609**, WF **3/3**, SH 1.41/1.83 p=**0.030**. H-012 corr 0.471. Liquidity premium.

### H-1102: Kyle Lambda XS (session 200)
- **Status**: LIVE paper trade (started 2026-04-14)
- **Position**: 8 positions (4L/4S). Initial entry.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h1102_kyle_lambda/runner.py`
- **Params**: R=5, N=4, dir=low_long. IS Sharpe 1.218, WF **3/3**, SH 0.39/2.08 p=0.099. H-012 corr 0.295. Market depth proxy.

### H-1116: Dispersion-Timed Momentum XS (session 200)
- **Status**: LIVE paper trade (started 2026-04-14)
- **Position**: 8 positions (4L/4S). Initial entry.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h1116_disp_timed_mom/runner.py`
- **Params**: R=7, N=4, dir=high_long. IS Sharpe 1.293, WF 2/3, p=0.080. H-012 corr 0.635. Marginal.

### H-1127: Beta Stability XS (session 201)
- **Status**: LIVE paper trade (started 2026-04-14)
- **Position**: 8 positions (4L/4S). LONG: BTC, ETH, ATOM, SUI. SHORT: OP, ARB, NEAR, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h1127_beta_stability/runner.py`
- **Params**: R=5, N=4, dir=low_long. IS Sharpe 1.151, WF **3/3 PERFECT**, SH 0.71/1.60 p=0.119. H-012 corr **0.089**. Stable beta = lower risk.

### H-1135: Extreme Return Reversal XS (session 201) — SESSION BEST
- **Status**: LIVE paper trade (started 2026-04-14)
- **Position**: 6 positions (3L/3S). LONG: BTC, ETH, SOL. SHORT: OP, ARB, ATOM.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h1135_extreme_return/runner.py`
- **Params**: R=3, N=3, dir=low_long. IS Sharpe **1.836**, IS **100%**, WF **4/4 PERFECT**, SH **2.08/1.59** p=**0.011**. H-012 corr **-0.002**. Contrarian extreme reversal.

### H-1137: RSI Cross-Sectional XS (session 201)
- **Status**: LIVE paper trade (started 2026-04-14)
- **Position**: 6 positions (3L/3S). LONG: NEAR, ARB, BTC. SHORT: SOL, ADA, DOT.
- **Capital**: $9,976 (-0.24%)
- **Runner**: `paper_trades/h1137_rsi_xs/runner.py`
- **Params**: R=3, N=3, dir=high_long. IS Sharpe **1.552**, WF **3/4**, SH **1.59/1.54** p=**0.032**. H-012 corr 0.021. Independent momentum via RSI.
