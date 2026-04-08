"""
Comprehensive Portfolio Optimization — All Confirmed Strategies

Extends H-055 optimizer with all confirmed strategies (H-009 through H-355).
Generates daily return series for each, computes full correlation matrix,
and finds optimal portfolio weights via MVO.

Strategies are grouped by signal source:
  - Daily OHLCV (most strategies)
  - Funding/LSR/Premium data (H-049, H-052, H-053, H-189)
  - OI data (H-044, H-193)
  - Hourly data (H-242, H-244, H-250, H-332, H-333, H-336, H-338, H-342, H-343, H-351, H-353, H-355)

Note: Hourly-derived strategies are included via a separate hourly signal pass.
"""

import sys, os
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from itertools import combinations

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from strategies.portfolio_optimization.h055_portfolio_optimizer import (
    load_all_daily, build_closes_and_volumes, run_xs_factor,
    gen_h009_returns, gen_h011_returns, gen_h012_returns, gen_h019_returns,
    gen_h021_returns, gen_h031_returns, gen_h039_returns,
    gen_h044_returns, gen_h046_returns, gen_h049_returns,
    gen_h052_returns, gen_h053_returns, gen_h059_returns,
    compute_metrics, optimize_portfolio,
    ASSETS_FULL, ASSETS_SHORT, BASE_FEE, SLIPPAGE_BPS, INITIAL_CAPITAL, DATA_DIR,
)


# ═══════════════════════════════════════════════════════════════
# NEW Strategy Return Generators (daily-only signals)
# ═══════════════════════════════════════════════════════════════

def gen_h062_returns(closes):
    """H-062: Max Drawdown Momentum — long near peak, short deep drawdown."""
    lookback = 60
    rolling_max = closes.rolling(lookback).max()
    dd_from_peak = closes / rolling_max  # 1.0 = at peak, <1 = in drawdown
    return run_xs_factor(closes, dd_from_peak, rebal_freq=5, n_long=3, warmup=lookback+5)


def gen_h076_returns(closes):
    """H-076: Price Efficiency — net move / total path length.
    High efficiency = trending cleanly. Long efficient, short noisy."""
    lookback = 40
    daily_rets = closes.pct_change()
    # Net move over lookback
    net_move = closes.pct_change(lookback).abs()
    # Total path = sum of absolute daily returns
    total_path = daily_rets.abs().rolling(lookback).sum()
    efficiency = net_move / total_path.replace(0, np.nan)
    return run_xs_factor(closes, efficiency, rebal_freq=5, n_long=4, warmup=lookback+5)


def gen_h085_returns(closes, volumes):
    """H-085: Turnover Velocity — short-term/long-term volume ratio.
    Captures volume momentum / participation shifts."""
    sv = volumes.rolling(5).mean()
    lv = volumes.rolling(20).mean()
    turnover = sv / lv
    return run_xs_factor(closes, turnover, rebal_freq=7, n_long=4, warmup=25)


def gen_h160_returns(closes):
    """H-160: Trend Quality — efficiency × volatility interaction.
    High efficiency + low vol = smooth trend. Signal = efficiency / vol."""
    daily_rets = closes.pct_change()
    lookback = 20
    net_move = closes.pct_change(lookback).abs()
    total_path = daily_rets.abs().rolling(lookback).sum()
    efficiency = net_move / total_path.replace(0, np.nan)
    vol = daily_rets.rolling(lookback).std()
    # Rank by efficiency (high) and low vol → efficiency / vol
    trend_quality = efficiency / vol.replace(0, np.nan)
    return run_xs_factor(closes, trend_quality, rebal_freq=3, n_long=3, warmup=lookback+5)


def gen_h169_returns(closes):
    """H-169: Alpha Momentum — BTC-beta-adjusted return.
    Residual = actual return - beta * BTC return. Long positive alpha."""
    lookback = 10
    rets = closes.pct_change()
    btc_rets = rets['BTC/USDT']
    # Non-BTC assets only
    non_btc = [c for c in closes.columns if c != 'BTC/USDT']
    alpha = pd.DataFrame(index=closes.index, columns=non_btc)
    for col in non_btc:
        rolling_cov = rets[col].rolling(lookback).cov(btc_rets)
        rolling_var = btc_rets.rolling(lookback).var()
        beta = rolling_cov / rolling_var.replace(0, np.nan)
        # Alpha = actual cumulative return - beta * BTC cumulative return
        cum_ret = closes[col].pct_change(lookback)
        btc_cum_ret = closes['BTC/USDT'].pct_change(lookback)
        alpha[col] = cum_ret - beta * btc_cum_ret
    alpha = alpha.astype(float)
    closes_sub = closes[non_btc]
    return run_xs_factor(closes_sub, alpha, rebal_freq=5, n_long=4, warmup=lookback+5)


def gen_h175_returns(closes, volumes):
    """H-175: Net Money Flow — sum of volume-weighted returns.
    Positive = net buying pressure. Long high inflow."""
    lookback = 30
    daily_rets = closes.pct_change()
    flow = daily_rets * volumes  # signed volume
    net_flow = flow.rolling(lookback).sum()
    return run_xs_factor(closes, net_flow, rebal_freq=7, n_long=4, warmup=lookback+5)


def gen_h182_returns(closes):
    """H-182: High-Low Range Factor — long narrow range (calm), short wide (volatile)."""
    daily_data_dict = {}
    for col in closes.columns:
        asset_short = col.replace('/USDT', '')
        fpath = os.path.join(DATA_DIR, f"{asset_short}_USDT_1d.parquet")
        if os.path.exists(fpath):
            df = pd.read_parquet(fpath)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            daily_data_dict[col] = df

    if len(daily_data_dict) < 8:
        return None

    lookback = 30
    range_signal = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        if col in daily_data_dict:
            df = daily_data_dict[col]
            common = closes.index.intersection(df.index)
            hl_range = (df.loc[common, 'high'] - df.loc[common, 'low']) / df.loc[common, 'close']
            avg_range = hl_range.rolling(lookback).mean()
            range_signal.loc[common, col] = -avg_range.values  # negative so narrow=high

    range_signal = range_signal.astype(float)
    return run_xs_factor(closes, range_signal, rebal_freq=5, n_long=3, warmup=lookback+5)


def gen_h183_returns(closes):
    """H-183: Gap / Overnight Sentiment — contrarian on open-close gaps."""
    daily_data_dict = {}
    for col in closes.columns:
        asset_short = col.replace('/USDT', '')
        fpath = os.path.join(DATA_DIR, f"{asset_short}_USDT_1d.parquet")
        if os.path.exists(fpath):
            df = pd.read_parquet(fpath)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            daily_data_dict[col] = df

    if len(daily_data_dict) < 8:
        return None

    lookback = 10
    gap_signal = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        if col in daily_data_dict:
            df = daily_data_dict[col]
            common = closes.index.intersection(df.index)
            # Gap = open today vs close yesterday
            gap = df.loc[common, 'open'] / df.loc[common, 'close'].shift(1) - 1
            avg_gap = gap.rolling(lookback).mean()
            gap_signal.loc[common, col] = -avg_gap.values  # contrarian: long negative gaps

    gap_signal = gap_signal.astype(float)
    return run_xs_factor(closes, gap_signal, rebal_freq=5, n_long=4, warmup=lookback+5)


def gen_h197_returns(closes, volumes):
    """H-197: Amihud Illiquidity — |return|/volume. Long liquid (low), short illiquid."""
    lookback = 10
    daily_rets = closes.pct_change().abs()
    # Dollar volume
    dollar_vol = closes * volumes
    amihud = daily_rets / dollar_vol.replace(0, np.nan)
    avg_amihud = amihud.rolling(lookback).mean()
    ranking = -avg_amihud  # negative so low Amihud (liquid) ranks high
    return run_xs_factor(closes, ranking, rebal_freq=3, n_long=4, warmup=lookback+5)


def gen_h215_returns(closes, volumes):
    """H-215: Dollar Volume Trend — slope of log dollar volume.
    Long increasing activity, short decreasing."""
    lookback = 15
    dv = np.log(closes * volumes + 1)
    # Linear regression slope of log-DV over lookback
    slopes = pd.DataFrame(index=closes.index, columns=closes.columns)
    x = np.arange(lookback, dtype=float)
    x_demean = x - x.mean()
    x_var = (x_demean ** 2).sum()
    for i in range(lookback, len(closes)):
        for col in closes.columns:
            y = dv.iloc[i-lookback:i][col].values
            if np.any(np.isnan(y)):
                continue
            y_demean = y - y.mean()
            slopes.iloc[i][col] = (x_demean * y_demean).sum() / x_var
    slopes = slopes.astype(float)
    return run_xs_factor(closes, slopes, rebal_freq=3, n_long=4, warmup=lookback+5)


def gen_h219_returns(closes):
    """H-219: Up-Volume Ratio — fraction of up days' volume vs total."""
    daily_data_dict = {}
    for col in closes.columns:
        asset_short = col.replace('/USDT', '')
        fpath = os.path.join(DATA_DIR, f"{asset_short}_USDT_1d.parquet")
        if os.path.exists(fpath):
            df = pd.read_parquet(fpath)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            daily_data_dict[col] = df

    if len(daily_data_dict) < 8:
        return None

    lookback = 10
    upvol_signal = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        if col in daily_data_dict:
            df = daily_data_dict[col]
            common = closes.index.intersection(df.index)
            daily_ret = df.loc[common, 'close'].pct_change()
            vol = df.loc[common, 'volume']
            up_vol = (vol * (daily_ret > 0)).rolling(lookback).sum()
            total_vol = vol.rolling(lookback).sum()
            upvol_ratio = up_vol / total_vol.replace(0, np.nan)
            upvol_signal.loc[common, col] = upvol_ratio.values

    upvol_signal = upvol_signal.astype(float)
    return run_xs_factor(closes, upvol_signal, rebal_freq=7, n_long=3, warmup=lookback+5)


def gen_h223_returns(closes):
    """H-223: Momentum Breadth / Win Rate — % of positive return days."""
    lookback = 20
    daily_rets = closes.pct_change()
    win_rate = (daily_rets > 0).astype(float).rolling(lookback).mean()
    return run_xs_factor(closes, win_rate, rebal_freq=5, n_long=3, warmup=lookback+5)


def gen_h255_returns(closes):
    """H-255: Risk-Adjusted Momentum / Rolling Sharpe."""
    lookback = 14
    daily_rets = closes.pct_change()
    rolling_mean = daily_rets.rolling(lookback).mean()
    rolling_std = daily_rets.rolling(lookback).std()
    rolling_sharpe = rolling_mean / rolling_std.replace(0, np.nan)
    return run_xs_factor(closes, rolling_sharpe, rebal_freq=7, n_long=3, warmup=lookback+5)


def gen_h259_returns(closes):
    """H-259: Extreme Move Frequency — % of days with >2σ moves."""
    lookback = 20
    daily_rets = closes.pct_change()
    vol = daily_rets.rolling(60).std()  # longer window for stable vol estimate
    extreme = (daily_rets.abs() > 2 * vol).astype(float)
    freq = extreme.rolling(lookback).mean()
    return run_xs_factor(closes, freq, rebal_freq=7, n_long=4, warmup=65)


def gen_h263_returns(closes):
    """H-263: Relative Strength vs BTC — non-BTC assets ranked by return vs BTC."""
    lookback = 10
    rets_over_lb = closes.pct_change(lookback)
    btc_ret = rets_over_lb['BTC/USDT']
    non_btc = [c for c in closes.columns if c != 'BTC/USDT']
    relative = pd.DataFrame(index=closes.index, columns=non_btc)
    for col in non_btc:
        relative[col] = rets_over_lb[col] - btc_ret
    relative = relative.astype(float)
    closes_sub = closes[non_btc]
    return run_xs_factor(closes_sub, relative, rebal_freq=3, n_long=3, warmup=lookback+5)


def gen_h264_returns(closes):
    """H-264: Return Skewness — long positively skewed, short negatively skewed."""
    lookback = 60
    daily_rets = closes.pct_change()
    skew = daily_rets.rolling(lookback).skew()
    return run_xs_factor(closes, skew, rebal_freq=3, n_long=3, warmup=lookback+5)


def gen_h277_returns(closes, volumes):
    """H-277: VWAP Deviation — close relative to volume-weighted average price."""
    lookback = 20
    # Approximate VWAP: cumulative (price * volume) / cumulative volume over lookback
    pv = closes * volumes
    vwap = pv.rolling(lookback).sum() / volumes.rolling(lookback).sum().replace(0, np.nan)
    deviation = closes / vwap - 1  # positive = trading above VWAP (demand pressure)
    return run_xs_factor(closes, deviation, rebal_freq=7, n_long=3, warmup=lookback+5)


# ═══════════════════════════════════════════════════════════════
# Hourly-derived signal generators
# ═══════════════════════════════════════════════════════════════

def load_hourly_data():
    """Load hourly OHLCV for all assets that have it."""
    hourly = {}
    for asset in ASSETS_SHORT:
        fpath = os.path.join(DATA_DIR, f"{asset}_USDT_1h.parquet")
        if os.path.exists(fpath):
            df = pd.read_parquet(fpath)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            hourly[f"{asset}/USDT"] = df
    return hourly


def gen_h242_returns(closes, hourly_data):
    """H-242: Intraday Momentum Concentration — fraction of daily move in biggest hourly bar."""
    lookback = 10
    conc_signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)

    for asset in closes.columns:
        if asset not in hourly_data:
            continue
        h = hourly_data[asset]
        # For each day, compute: max(|hourly_ret|) / sum(|hourly_ret|)
        h_ret = h['close'].pct_change().abs()
        daily_max = h_ret.resample('1D').max()
        daily_sum = h_ret.resample('1D').sum()
        concentration = daily_max / daily_sum.replace(0, np.nan)
        avg_conc = concentration.rolling(lookback).mean()
        common = closes.index.intersection(avg_conc.dropna().index)
        conc_signal.loc[common, asset] = avg_conc.loc[common].values

    return run_xs_factor(closes, conc_signal, rebal_freq=5, n_long=4, warmup=lookback+5)


def gen_h332_returns(closes, hourly_data):
    """H-332: Bar Consistency Score — fraction of 4h bars aligned with daily direction."""
    lookback = 10
    consistency = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)

    for asset in closes.columns:
        if asset not in hourly_data:
            continue
        h = hourly_data[asset]
        # Resample to 4h
        h4 = h['close'].resample('4h').last().dropna()
        h4_ret = h4.pct_change()
        # Daily return direction
        daily_ret = h['close'].resample('1D').last().pct_change()
        daily_sign = np.sign(daily_ret)

        # For each day, count 4h bars aligned with daily direction
        bar_alignment = pd.Series(dtype=float, index=daily_ret.index)
        for date in daily_ret.dropna().index:
            day_start = date.normalize()
            day_end = day_start + pd.Timedelta(days=1)
            bars = h4_ret.loc[day_start:day_end]
            if len(bars) == 0:
                continue
            d_sign = daily_sign.get(date, 0)
            if d_sign == 0:
                continue
            aligned = (np.sign(bars) == d_sign).sum()
            bar_alignment[date] = aligned / len(bars)

        avg = bar_alignment.rolling(lookback).mean()
        common = closes.index.intersection(avg.dropna().index)
        consistency.loc[common, asset] = avg.loc[common].values

    return run_xs_factor(closes, consistency, rebal_freq=3, n_long=3, warmup=lookback+5)


def gen_h336_returns(closes, hourly_data):
    """H-336: Volume Surprise — ratio of recent volume to longer-term average.
    Long high surprise (unusual activity), short low surprise."""
    lookback = 30
    vol_surprise = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)

    for asset in closes.columns:
        if asset not in hourly_data:
            continue
        h = hourly_data[asset]
        daily_vol = h['volume'].resample('1D').sum()
        short_avg = daily_vol.rolling(3).mean()
        long_avg = daily_vol.rolling(lookback).mean()
        surprise = short_avg / long_avg.replace(0, np.nan)
        avg_surprise = surprise.rolling(5).mean()
        common = closes.index.intersection(avg_surprise.dropna().index)
        vol_surprise.loc[common, asset] = avg_surprise.loc[common].values

    return run_xs_factor(closes, vol_surprise, rebal_freq=3, n_long=4, warmup=lookback+5)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("COMPREHENSIVE PORTFOLIO OPTIMIZATION — ALL CONFIRMED STRATEGIES")
    print("=" * 70)

    # 1. Load data
    print("\n1. Loading data...")
    daily_data = load_all_daily()
    closes, volumes = build_closes_and_volumes(daily_data)
    print(f"   {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"   {closes.index[0].date()} to {closes.index[-1].date()}")

    # Load hourly data for intraday-derived signals
    print("   Loading hourly data...")
    hourly_data = load_hourly_data()
    print(f"   {len(hourly_data)} assets have hourly data")

    # 2. Generate return series for ALL confirmed strategies
    print("\n2. Generating strategy return series...")
    strategies = {
        # Original 14 strategies
        'H-009': lambda: gen_h009_returns(daily_data),
        'H-011': lambda: gen_h011_returns(daily_data),
        'H-012': lambda: gen_h012_returns(closes),
        'H-019': lambda: gen_h019_returns(closes),
        'H-021': lambda: gen_h021_returns(closes, volumes),
        'H-031': lambda: gen_h031_returns(closes, volumes),
        'H-039': lambda: gen_h039_returns(daily_data),
        'H-044': lambda: gen_h044_returns(closes),
        'H-046': lambda: gen_h046_returns(closes),
        'H-049': lambda: gen_h049_returns(closes),
        'H-052': lambda: gen_h052_returns(closes),
        'H-053': lambda: gen_h053_returns(closes),
        'H-059': lambda: gen_h059_returns(closes),
        # New daily-signal strategies
        'H-062': lambda: gen_h062_returns(closes),
        'H-076': lambda: gen_h076_returns(closes),
        'H-085': lambda: gen_h085_returns(closes, volumes),
        'H-160': lambda: gen_h160_returns(closes),
        'H-169': lambda: gen_h169_returns(closes),
        'H-175': lambda: gen_h175_returns(closes, volumes),
        'H-182': lambda: gen_h182_returns(closes),
        'H-183': lambda: gen_h183_returns(closes),
        'H-197': lambda: gen_h197_returns(closes, volumes),
        'H-215': lambda: gen_h215_returns(closes, volumes),
        'H-219': lambda: gen_h219_returns(closes),
        'H-223': lambda: gen_h223_returns(closes),
        'H-255': lambda: gen_h255_returns(closes),
        'H-259': lambda: gen_h259_returns(closes),
        'H-263': lambda: gen_h263_returns(closes),
        'H-264': lambda: gen_h264_returns(closes),
        'H-277': lambda: gen_h277_returns(closes, volumes),
        # Hourly-derived signals
        'H-242': lambda: gen_h242_returns(closes, hourly_data),
        'H-332': lambda: gen_h332_returns(closes, hourly_data),
        'H-336': lambda: gen_h336_returns(closes, hourly_data),
    }

    equity_curves = {}
    for name, gen_func in strategies.items():
        try:
            eq = gen_func()
            if eq is not None and len(eq) > 50:
                equity_curves[name] = eq
                rets = eq.pct_change().dropna()
                m = compute_metrics(rets)
                print(f"   {name}: Sharpe {m['sharpe']:>6.2f}, "
                      f"Ret {m['annual_return']*100:>+7.1f}%, "
                      f"DD {m['max_dd']*100:>6.1f}%, "
                      f"Days {m['n_days']:>4}")
            else:
                print(f"   {name}: SKIPPED (insufficient data)")
        except Exception as e:
            print(f"   {name}: ERROR — {e}")

    # 3. Build aligned daily returns matrix
    print(f"\n3. Aligned returns matrix ({len(equity_curves)} strategies)...")
    returns_dict = {}
    for name, eq in equity_curves.items():
        rets = eq.pct_change().dropna()
        if rets.index.tz is not None:
            rets.index = rets.index.tz_localize(None)
        rets.index = pd.DatetimeIndex(rets.index.date)
        returns_dict[name] = rets

    returns_df = pd.DataFrame(returns_dict).dropna()
    print(f"   {returns_df.index[0]} to {returns_df.index[-1]}")
    print(f"   {len(returns_df)} common days, {len(returns_df.columns)} strategies")

    # 4. Correlation matrix
    print("\n4. CORRELATION MATRIX")
    print("=" * 70)
    corr = returns_df.corr()
    strats = sorted(corr.columns, key=lambda x: int(x.split('-')[1]))

    # Print compact — only show correlations > 0.3
    print("\n   High-correlation pairs (>0.3):")
    pairs = []
    for i, s1 in enumerate(strats):
        for j, s2 in enumerate(strats):
            if j > i:
                c = corr.loc[s1, s2]
                if abs(c) > 0.3:
                    pairs.append((s1, s2, c))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    for s1, s2, c in pairs:
        print(f"     {s1:>5} / {s2:<5}: {c:+.3f}")

    # 5. Individual metrics
    print("\n5. INDIVIDUAL STRATEGY METRICS")
    print("=" * 70)
    print(f"  {'Strat':>6} {'Sharpe':>7} {'Return':>8} {'Vol':>7} {'MaxDD':>7} {'Days':>5}")
    metrics = {}
    for name in strats:
        if name in returns_df.columns:
            rets = returns_df[name]
            m = compute_metrics(rets)
            metrics[name] = m
            print(f"  {name:>6} {m['sharpe']:>7.2f} {m['annual_return']*100:>+7.1f}% "
                  f"{m['annual_vol']*100:>6.1f}% {m['max_dd']*100:>6.1f}% {m['n_days']:>5}")

    # 6. Portfolio optimization
    print("\n6. PORTFOLIO OPTIMIZATION")
    print("=" * 70)

    # 6a. Current H-056 v2 portfolio (baseline)
    print("\n  --- Current H-056 v2 (baseline) ---")
    h056_weights = {
        'H-031': 0.30, 'H-052': 0.23, 'H-053': 0.16,
        'H-021': 0.15, 'H-039': 0.10, 'H-049': 0.06,
    }
    h056_strats = [s for s in h056_weights if s in returns_df.columns]
    if len(h056_strats) == len(h056_weights):
        w = np.array([h056_weights[s] for s in h056_strats])
        port = returns_df[h056_strats].values @ w
        m = compute_metrics(pd.Series(port, index=returns_df.index))
        print(f"  Sharpe {m['sharpe']:.2f}, Ret {m['annual_return']*100:+.1f}%, DD {m['max_dd']*100:.1f}%")
        for s in h056_strats:
            print(f"    {s}: {h056_weights[s]*100:.0f}%")

    # 6b. Equal weight across all
    print("\n  --- Equal weight (all strategies) ---")
    ew = returns_df.mean(axis=1)
    m_ew = compute_metrics(ew)
    print(f"  Sharpe {m_ew['sharpe']:.2f}, Ret {m_ew['annual_return']*100:+.1f}%, DD {m_ew['max_dd']*100:.1f}%")

    # 6c. Max Sharpe optimization (all strategies)
    for max_w in [0.15, 0.20, 0.30]:
        print(f"\n  --- Max Sharpe (max_weight={max_w*100:.0f}%, all {len(strats)} strategies) ---")
        try:
            weights, opt_sharpe = optimize_portfolio(returns_df[strats], 'max_sharpe',
                                                      min_weight=0.0, max_weight=max_w)
            port = returns_df[strats].values @ weights
            m = compute_metrics(pd.Series(port, index=returns_df.index))
            print(f"  Sharpe {m['sharpe']:.2f}, Ret {m['annual_return']*100:+.1f}%, DD {m['max_dd']*100:.1f}%")
            selected = [(strats[i], weights[i]) for i in range(len(strats)) if weights[i] > 0.005]
            selected.sort(key=lambda x: x[1], reverse=True)
            for s, w in selected:
                print(f"    {s}: {w*100:.1f}%")
            print(f"  Active strategies: {len(selected)}")
        except Exception as e:
            print(f"  FAILED: {e}")

    # 6d. Risk parity
    print(f"\n  --- Risk Parity ---")
    try:
        weights_rp, _ = optimize_portfolio(returns_df[strats], 'risk_parity', max_weight=0.15)
        port = returns_df[strats].values @ weights_rp
        m = compute_metrics(pd.Series(port, index=returns_df.index))
        print(f"  Sharpe {m['sharpe']:.2f}, Ret {m['annual_return']*100:+.1f}%, DD {m['max_dd']*100:.1f}%")
        selected = [(strats[i], weights_rp[i]) for i in range(len(strats)) if weights_rp[i] > 0.005]
        selected.sort(key=lambda x: x[1], reverse=True)
        for s, w in selected:
            print(f"    {s}: {w*100:.1f}%")
    except Exception as e:
        print(f"  FAILED: {e}")

    # 6e. Best subset selection — try 6, 8, 10-strategy portfolios
    print("\n  --- Best N-Strategy Subsets (max_weight=30%) ---")
    # For large N, exhaustive search is too slow. Use greedy forward selection.
    available = [s for s in strats if s in returns_df.columns]

    for target_n in [6, 8, 10, 12]:
        print(f"\n  Best-{target_n} (greedy forward selection):")
        selected = []
        remaining = list(available)

        for step in range(target_n):
            best_sharpe = -999
            best_strat = None
            for candidate in remaining:
                trial = selected + [candidate]
                sub_ret = returns_df[trial]
                try:
                    max_w = max(0.10, 1.0 / len(trial))
                    w, _ = optimize_portfolio(sub_ret, 'max_sharpe',
                                               min_weight=0.0, max_weight=0.30)
                    port = sub_ret.values @ w
                    m = compute_metrics(pd.Series(port, index=sub_ret.index))
                    if m['sharpe'] > best_sharpe:
                        best_sharpe = m['sharpe']
                        best_strat = candidate
                        best_w = w
                except:
                    continue
            if best_strat:
                selected.append(best_strat)
                remaining.remove(best_strat)

        # Final optimization on selected set
        if len(selected) == target_n:
            sub_ret = returns_df[selected]
            w, _ = optimize_portfolio(sub_ret, 'max_sharpe', min_weight=0.02, max_weight=0.30)
            port = sub_ret.values @ w
            m = compute_metrics(pd.Series(port, index=sub_ret.index))
            print(f"  Sharpe {m['sharpe']:.2f}, Ret {m['annual_return']*100:+.1f}%, DD {m['max_dd']*100:.1f}%")
            for i, s in enumerate(selected):
                if w[i] > 0.005:
                    print(f"    {s}: {w[i]*100:.1f}%")

    # 7. Save results
    import json
    results = {
        'n_strategies': len(equity_curves),
        'n_common_days': len(returns_df),
        'date_range': f"{returns_df.index[0]} to {returns_df.index[-1]}",
        'individual_metrics': {k: {kk: float(vv) if isinstance(vv, (float, np.floating)) else vv
                                    for kk, vv in v.items()} for k, v in metrics.items()},
        'correlation_pairs_gt_03': [(s1, s2, float(c)) for s1, s2, c in pairs],
    }
    out = os.path.join(os.path.dirname(__file__), 'comprehensive_results.json')
    with open(out, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to {out}")


if __name__ == '__main__':
    main()
