"""
H-055: Comprehensive Portfolio Optimization

Generate daily return series for all 14 deployable strategies,
compute the full correlation matrix, and find optimal allocations
using mean-variance optimization with various constraints.

Strategies:
  H-009: BTC Daily EMA Trend (vol targeted 20%)
  H-011: Funding Rate Arb (5x leverage)
  H-012: Cross-Sectional Momentum (60d, 5d rebal, top/bot 4)
  H-019: Low-Vol Anomaly (20d vol, 21d rebal, top/bot 3)
  H-021: Volume Momentum (VS5/VL20, 3d rebal, top/bot 4)
  H-024: Low-Beta Anomaly (60d beta, 21d rebal, top/bot 3)
  H-031: Size Factor (30d DV, 5d rebal, top/bot 5)
  H-039: DOW Seasonality (Wed long / Thu short BTC)
  H-044: OI-Price Divergence (20d, 10d rebal, top/bot 5)
  H-046: Price Acceleration (20d mom, 20d accel, 3d rebal, top/bot 4)
  H-049: LSR Sentiment Contrarian (5d rebal, top/bot 3) [only 200 days]
  H-052: Premium Index Contrarian (5d window, 5d rebal, top/bot 4)
  H-053: Funding Rate XS Contrarian (3d window, 10d rebal, top/bot 4)
  H-059: Volatility Term Structure (7d/30d vol ratio, 7d rebal, top/bot 5)
"""

import sys, os
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from itertools import combinations

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS_FULL = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'SUI/USDT', 'XRP/USDT',
               'DOGE/USDT', 'AVAX/USDT', 'LINK/USDT', 'ADA/USDT', 'DOT/USDT',
               'NEAR/USDT', 'OP/USDT', 'ARB/USDT', 'ATOM/USDT']
ASSETS_SHORT = [a.replace('/USDT', '') for a in ASSETS_FULL]

BASE_FEE = 0.001
SLIPPAGE_BPS = 2.0
INITIAL_CAPITAL = 10_000.0
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')


def resample_to_daily(df):
    daily = df.resample("1D").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()
    return daily


def load_all_daily():
    """Load daily OHLCV for all 14 assets."""
    daily = {}
    for sym in ASSETS_FULL:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df) >= 200:
                daily[sym] = resample_to_daily(df)
        except Exception as e:
            print(f"  Warning: failed to load {sym}: {e}")
    return daily


def build_closes_and_volumes(daily_data):
    """Build aligned closes and volumes DataFrames."""
    closes = pd.DataFrame({sym: daily_data[sym]['close'] for sym in daily_data})
    volumes = pd.DataFrame({sym: daily_data[sym]['volume'] for sym in daily_data})
    # Normalize to tz-naive for compatibility with other data sources
    if closes.index.tz is not None:
        closes.index = closes.index.tz_localize(None)
    if volumes.index.tz is not None:
        volumes.index = volumes.index.tz_localize(None)
    closes = closes.sort_index().dropna(how='all')
    volumes = volumes.sort_index().dropna(how='all')
    return closes, volumes


# ═══════════════════════════════════════════════════════════════
# Strategy return generators
# ═══════════════════════════════════════════════════════════════

def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  fee_multiplier=1.0, warmup=65):
    """Shared cross-sectional factor backtest."""
    if n_short is None:
        n_short = n_long
    n = len(closes)
    slippage = SLIPPAGE_BPS / 10_000
    fee_rate = BASE_FEE * fee_multiplier
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital
    prev_weights = pd.Series(0.0, index=closes.columns)

    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = ranking_series.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                equity[i] = equity[i - 1]
                continue
            ranked = valid.sort_values(ascending=False)
            longs = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]
            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short
            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * (fee_rate + slippage)
            daily_rets = (price_today / price_yesterday - 1)
            port_ret = (new_weights * daily_rets).sum() - fee_drag
            prev_weights = new_weights
        else:
            daily_rets = (price_today / price_yesterday - 1)
            port_ret = (prev_weights * daily_rets).sum()

        equity[i] = equity[i - 1] * (1 + port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    return eq_series


def backtest_xs_factor_alt(closes, signals, rebal_days, n_long_short,
                           direction="long_high", fee_bps=5):
    """Alternative XS factor backtest (used by H-052, H-053)."""
    returns = closes.pct_change()
    assets = [a for a in signals.columns if a in returns.columns]
    asset_returns = returns[assets]

    common_idx = signals.dropna(how='all').index.intersection(asset_returns.dropna(how='all').index)
    signals = signals.loc[common_idx]
    asset_returns = asset_returns.loc[common_idx]

    portfolio_returns = pd.Series(0.0, index=common_idx)
    current_longs = []
    current_shorts = []
    last_rebal = None

    for i, date in enumerate(common_idx):
        if i == 0:
            continue
        prev_date = common_idx[i-1]
        sig = signals.loc[prev_date].dropna()
        if len(sig) < 2 * n_long_short:
            continue
        days_since = (date - last_rebal).days if last_rebal else rebal_days + 1
        if days_since >= rebal_days:
            ranked = sig.sort_values()
            if direction == "long_low":
                new_longs = ranked.index[:n_long_short].tolist()
                new_shorts = ranked.index[-n_long_short:].tolist()
            else:
                new_longs = ranked.index[-n_long_short:].tolist()
                new_shorts = ranked.index[:n_long_short].tolist()
            if current_longs or current_shorts:
                old_set = set(current_longs + current_shorts)
                new_set = set(new_longs + new_shorts)
                turnover = len(old_set.symmetric_difference(new_set))
                fee_cost = turnover * (1.0 / (2 * n_long_short)) * fee_bps * 2 / 10000
            else:
                fee_cost = 2 * fee_bps / 10000
            current_longs = new_longs
            current_shorts = new_shorts
            last_rebal = date
            portfolio_returns.loc[date] -= fee_cost

        if current_longs and current_shorts:
            w = 1.0 / n_long_short
            for sym in current_longs:
                if sym in asset_returns.columns:
                    portfolio_returns.loc[date] += w * asset_returns.loc[date, sym]
            for sym in current_shorts:
                if sym in asset_returns.columns:
                    portfolio_returns.loc[date] -= w * asset_returns.loc[date, sym]

    # Convert to equity
    equity = INITIAL_CAPITAL * (1 + portfolio_returns).cumprod()
    return equity


# ── H-009: BTC Daily EMA Trend with Vol Targeting ──

def gen_h009_returns(daily_data):
    """Generate H-009 daily return series."""
    btc = daily_data['BTC/USDT'].copy()
    if btc.index.tz is not None:
        btc.index = btc.index.tz_localize(None)
    close = btc['close']
    ema5 = close.ewm(span=5, adjust=False).mean()
    ema40 = close.ewm(span=40, adjust=False).mean()
    signal = (ema5 > ema40).astype(float) * 2 - 1  # +1 long, -1 short

    daily_ret = close.pct_change()
    strat_ret = signal.shift(1) * daily_ret

    # Vol targeting 20%
    realized_vol = daily_ret.rolling(30).std() * np.sqrt(365)
    target_vol = 0.20
    leverage = (target_vol / realized_vol).clip(0.1, 2.0)
    vt_ret = strat_ret * leverage.shift(1)

    # Apply fees on signal changes
    fee_rate = BASE_FEE + SLIPPAGE_BPS / 10000
    signal_change = signal.diff().abs()
    fee_drag = signal_change.shift(1) * fee_rate
    vt_ret = vt_ret - fee_drag

    equity = INITIAL_CAPITAL * (1 + vt_ret.dropna()).cumprod()
    return equity


# ── H-011: Funding Rate Arb (5x) ──

def gen_h011_returns(daily_data):
    """Generate H-011 daily return series."""
    funding_path = os.path.join(DATA_DIR, 'BTC_USDT_funding_rates.parquet')
    if not os.path.exists(funding_path):
        print("  WARNING: No funding rate data for H-011")
        return None
    df_funding = pd.read_parquet(funding_path)
    rate_col = 'fundingRate' if 'fundingRate' in df_funding.columns else 'funding_rate'
    if 'timestamp' in df_funding.columns:
        df_funding['timestamp'] = pd.to_datetime(df_funding['timestamp'])
        df_funding = df_funding.set_index('timestamp')
    elif 'datetime' in df_funding.columns:
        df_funding['datetime'] = pd.to_datetime(df_funding['datetime'])
        df_funding = df_funding.set_index('datetime')
    df_funding = df_funding.sort_index()
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)

    leverage = 5.0
    daily_funding = df_funding[rate_col].resample('1D').sum()
    rolling_avg = df_funding[rate_col].resample('1D').mean().rolling(27, min_periods=5).mean()

    common_idx = daily_funding.index.intersection(rolling_avg.dropna().index)
    daily_funding = daily_funding.loc[common_idx]
    rolling_avg = rolling_avg.loc[common_idx]

    daily_returns = pd.Series(0.0, index=common_idx)
    for date in common_idx:
        if rolling_avg.loc[date] > 0:
            daily_returns.loc[date] = leverage * daily_funding.loc[date]

    equity = INITIAL_CAPITAL * (1 + daily_returns).cumprod()
    return equity


# ── H-012: Cross-Sectional Momentum ──

def gen_h012_returns(closes):
    """Generate H-012 daily return series."""
    lookback = 60
    rolling_ret = closes.pct_change(lookback)
    return run_xs_factor(closes, rolling_ret, rebal_freq=5, n_long=4, warmup=lookback+5)


# ── H-019: Low-Vol Anomaly ──

def gen_h019_returns(closes):
    """Generate H-019 daily return series."""
    daily_rets = closes.pct_change()
    ranking = -daily_rets.rolling(20).std()  # negative so low vol ranks high
    return run_xs_factor(closes, ranking, rebal_freq=21, n_long=3, warmup=65)


# ── H-021: Volume Momentum ──

def gen_h021_returns(closes, volumes):
    """Generate H-021 daily return series."""
    vol_short = volumes.rolling(5).mean()
    vol_long = volumes.rolling(20).mean()
    ranking = vol_short / vol_long
    return run_xs_factor(closes, ranking, rebal_freq=3, n_long=4, warmup=65)


# ── H-024: Low-Beta Anomaly ──

def gen_h024_returns(closes):
    """Generate H-024 daily return series."""
    rets = closes.pct_change()
    btc_rets = rets['BTC/USDT']
    beta_ranking = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        rolling_cov = rets[col].rolling(60).cov(btc_rets)
        rolling_var = btc_rets.rolling(60).var()
        beta = rolling_cov / rolling_var
        beta_ranking[col] = -beta  # negative so low beta ranks high
    return run_xs_factor(closes, beta_ranking, rebal_freq=21, n_long=3, warmup=65)


# ── H-031: Size Factor (Dollar Volume) ──

def gen_h031_returns(closes, volumes):
    """Generate H-031 daily return series."""
    dollar_volume = closes * volumes
    ranking = dollar_volume.rolling(30).mean()  # long large cap (high DV)
    return run_xs_factor(closes, ranking, rebal_freq=5, n_long=5, warmup=65)


# ── H-039: Day-of-Week Seasonality ──

def gen_h039_returns(daily_data):
    """Generate H-039 daily return series."""
    btc = daily_data['BTC/USDT'].copy()
    if btc.index.tz is not None:
        btc.index = btc.index.tz_localize(None)
    close = btc['close']
    daily_ret = close.pct_change()
    dow = close.index.dayofweek

    strat_ret = pd.Series(0.0, index=close.index)
    fee = 0.0004 * 2  # maker fee entry + exit per trade
    for i in range(len(close)):
        if dow[i] == 2:  # Wednesday: long
            strat_ret.iloc[i] = daily_ret.iloc[i] - fee
        elif dow[i] == 3:  # Thursday: short
            strat_ret.iloc[i] = -daily_ret.iloc[i] - fee

    equity = INITIAL_CAPITAL * (1 + strat_ret.dropna()).cumprod()
    return equity


# ── H-044: OI-Price Divergence ──

def gen_h044_returns(closes):
    """Generate H-044 daily return series using OI data."""
    oi_data = {}
    for asset in ASSETS_SHORT:
        fpath = os.path.join(DATA_DIR, 'oi', f"{asset}_oi_1d.parquet")
        if os.path.exists(fpath):
            df = pd.read_parquet(fpath)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            if 'openInterest' in df.columns:
                oi_data[f"{asset}/USDT"] = df['openInterest']
            elif 'open_interest' in df.columns:
                oi_data[f"{asset}/USDT"] = df['open_interest']
    if len(oi_data) < 8:
        print(f"  WARNING: only {len(oi_data)} assets have OI data for H-044")
        return None

    oi_panel = pd.DataFrame(oi_data).sort_index()
    common_assets = [a for a in closes.columns if a in oi_panel.columns]
    closes_sub = closes[common_assets]
    oi_sub = oi_panel[common_assets]

    # Align indices
    common_idx = closes_sub.index.intersection(oi_sub.index)
    closes_sub = closes_sub.loc[common_idx]
    oi_sub = oi_sub.loc[common_idx]

    window = 20
    price_chg = closes_sub.pct_change(window)
    oi_chg = oi_sub.pct_change(window)

    # Z-score cross-sectionally
    price_z = price_chg.subtract(price_chg.mean(axis=1), axis=0).divide(price_chg.std(axis=1), axis=0)
    oi_z = oi_chg.subtract(oi_chg.mean(axis=1), axis=0).divide(oi_chg.std(axis=1), axis=0)
    divergence = price_z - oi_z  # high = price up + OI down

    return run_xs_factor(closes_sub, divergence, rebal_freq=10, n_long=5, warmup=window+5)


# ── H-046: Price Acceleration ──

def gen_h046_returns(closes):
    """Generate H-046 daily return series."""
    mom_window = 20
    momentum_now = closes.pct_change(mom_window)
    momentum_past = closes.shift(mom_window).pct_change(mom_window)
    acceleration = momentum_now - momentum_past
    return run_xs_factor(closes, acceleration, rebal_freq=3, n_long=4, warmup=2*mom_window+5)


# ── H-049: LSR Sentiment Contrarian ──

def gen_h049_returns(closes):
    """Generate H-049 daily return series using LSR data."""
    lsr_path = os.path.join(DATA_DIR, 'all_assets_lsr_daily.parquet')
    if not os.path.exists(lsr_path):
        print("  WARNING: No LSR data for H-049")
        return None
    lsr = pd.read_parquet(lsr_path)
    if lsr.index.tz is not None:
        lsr.index = lsr.index.tz_localize(None)

    # Map short names to full names
    lsr_mapped = pd.DataFrame(index=lsr.index)
    for col in lsr.columns:
        sym = f"{col}/USDT" if '/USDT' not in col else col
        if sym in closes.columns:
            lsr_mapped[sym] = lsr[col].values

    if len(lsr_mapped.columns) < 6:
        print(f"  WARNING: only {len(lsr_mapped.columns)} assets have LSR data")
        return None

    common_assets = [a for a in closes.columns if a in lsr_mapped.columns]
    closes_sub = closes[common_assets].copy()
    lsr_sub = lsr_mapped[common_assets].copy()

    common_idx = closes_sub.index.intersection(lsr_sub.dropna(how='all').index)
    if len(common_idx) < 50:
        print(f"  WARNING: only {len(common_idx)} common days for H-049")
        return None
    closes_sub = closes_sub.loc[common_idx]
    lsr_sub = lsr_sub.loc[common_idx]

    # Contrarian: long lowest LSR, short highest
    ranking = -lsr_sub  # negative so low LSR ranks high
    return run_xs_factor(closes_sub, ranking, rebal_freq=5, n_long=3, warmup=10)


# ── H-052: Premium Index Contrarian ──

def gen_h052_returns(closes):
    """Generate H-052 daily return series using premium index data."""
    premium_path = os.path.join(DATA_DIR, 'all_assets_premium_daily.parquet')
    if not os.path.exists(premium_path):
        print("  WARNING: No premium data for H-052")
        return None
    df_raw = pd.read_parquet(premium_path)

    # Premium data is in long format: timestamp, open, high, low, close, asset
    # Pivot to wide format: date x asset
    df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'])
    premium_wide = df_raw.pivot_table(index='timestamp', columns='asset', values='close')
    if premium_wide.index.tz is not None:
        premium_wide.index = premium_wide.index.tz_localize(None)

    # Map short names to full names
    premium_mapped = pd.DataFrame(index=premium_wide.index)
    for col in premium_wide.columns:
        sym = f"{col}/USDT" if '/USDT' not in col else col
        if sym in closes.columns:
            premium_mapped[sym] = premium_wide[col].values

    if len(premium_mapped.columns) < 6:
        print(f"  WARNING: only {len(premium_mapped.columns)} assets have premium data")
        return None

    common_assets = [a for a in closes.columns if a in premium_mapped.columns]
    closes_sub = closes[common_assets].copy()
    premium_sub = premium_mapped[common_assets].copy()

    common_idx = closes_sub.index.intersection(premium_sub.dropna(how='all').index)
    if len(common_idx) < 50:
        print(f"  WARNING: only {len(common_idx)} common days for H-052")
        return None
    closes_sub = closes_sub.loc[common_idx]
    premium_sub = premium_sub.loc[common_idx]

    # 5-day rolling average, contrarian: long most discounted (low premium)
    premium_avg = premium_sub.rolling(5, min_periods=3).mean()
    ranking = -premium_avg  # negative so low premium ranks high
    return run_xs_factor(closes_sub, ranking, rebal_freq=5, n_long=4, warmup=10)


# ── H-053: Funding Rate XS Contrarian ──

def gen_h053_returns(closes):
    """Generate H-053 daily return series using funding rate data."""
    funding_data = {}
    for asset in ASSETS_SHORT:
        fpath = os.path.join(DATA_DIR, f"{asset}_USDT_USDT_funding.parquet")
        if not os.path.exists(fpath):
            continue
        df = pd.read_parquet(fpath)
        rate_col = 'fundingRate' if 'fundingRate' in df.columns else 'funding_rate'
        if rate_col not in df.columns:
            continue
        # Set timestamp as index
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
        elif 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        daily = df[rate_col].resample('1D').mean()
        funding_data[f"{asset}/USDT"] = daily

    if len(funding_data) < 8:
        print(f"  WARNING: only {len(funding_data)} assets have funding data for H-053")
        return None

    funding_panel = pd.DataFrame(funding_data).sort_index()
    common_assets = [a for a in closes.columns if a in funding_panel.columns]
    closes_sub = closes[common_assets]
    funding_sub = funding_panel[common_assets]

    common_idx = closes_sub.index.intersection(funding_sub.dropna(how='all').index)
    closes_sub = closes_sub.loc[common_idx]
    funding_sub = funding_sub.loc[common_idx]

    # 3-day rolling average, contrarian: long lowest funding
    funding_avg = funding_sub.rolling(3, min_periods=2).mean()
    ranking = -funding_avg  # negative so lowest funding ranks high
    return run_xs_factor(closes_sub, ranking, rebal_freq=10, n_long=4, warmup=10)


# ── H-059: Volatility Term Structure Factor ──

def gen_h059_returns(closes):
    """Generate H-059 daily return series.
    Long assets with expanding vol (short/long ratio > 1),
    short assets with contracting vol."""
    daily_rets = closes.pct_change()
    short_vol = daily_rets.rolling(7).std()
    long_vol = daily_rets.rolling(30).std()
    vol_ratio = short_vol / long_vol  # > 1 means expanding vol
    return run_xs_factor(closes, vol_ratio, rebal_freq=7, n_long=5, warmup=35)


# ═══════════════════════════════════════════════════════════════
# Portfolio Optimization
# ═══════════════════════════════════════════════════════════════

def compute_metrics(returns):
    """Compute key portfolio metrics from daily returns."""
    if len(returns) < 30:
        return {}
    ann_ret = (1 + returns.mean()) ** 365 - 1
    ann_vol = returns.std() * np.sqrt(365)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    cum_ret = (1 + returns).cumprod()
    max_dd = (cum_ret / cum_ret.cummax() - 1).min()
    return {
        'annual_return': ann_ret,
        'annual_vol': ann_vol,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'n_days': len(returns),
    }


def optimize_portfolio(returns_df, method='max_sharpe', min_weight=0.0, max_weight=0.5):
    """Mean-variance portfolio optimization."""
    mu = returns_df.mean() * 365
    cov = returns_df.cov() * 365
    n = len(returns_df.columns)

    if method == 'max_sharpe':
        def neg_sharpe(w):
            port_ret = w @ mu
            port_vol = np.sqrt(w @ cov @ w)
            return -port_ret / port_vol if port_vol > 0 else 0

        constraints = [{'type': 'eq', 'fun': lambda w: w.sum() - 1}]
        bounds = [(min_weight, max_weight)] * n
        w0 = np.ones(n) / n
        result = minimize(neg_sharpe, w0, method='SLSQP',
                         bounds=bounds, constraints=constraints)
        return result.x, -result.fun

    elif method == 'min_vol':
        def portfolio_vol(w):
            return np.sqrt(w @ cov @ w)

        constraints = [
            {'type': 'eq', 'fun': lambda w: w.sum() - 1},
            {'type': 'ineq', 'fun': lambda w: w @ mu - 0.20},  # min 20% return
        ]
        bounds = [(min_weight, max_weight)] * n
        w0 = np.ones(n) / n
        result = minimize(portfolio_vol, w0, method='SLSQP',
                         bounds=bounds, constraints=constraints)
        return result.x, None

    elif method == 'risk_parity':
        def risk_parity_obj(w):
            port_vol = np.sqrt(w @ cov @ w)
            marginal = cov @ w
            risk_contrib = w * marginal / port_vol
            target = port_vol / n
            return np.sum((risk_contrib - target) ** 2)

        constraints = [{'type': 'eq', 'fun': lambda w: w.sum() - 1}]
        bounds = [(0.01, max_weight)] * n
        w0 = np.ones(n) / n
        result = minimize(risk_parity_obj, w0, method='SLSQP',
                         bounds=bounds, constraints=constraints)
        return result.x, None

    elif method == 'equal_weight':
        return np.ones(n) / n, None


def main():
    print("=" * 70)
    print("H-055: COMPREHENSIVE PORTFOLIO OPTIMIZATION")
    print("=" * 70)

    # 1. Load data
    print("\n1. Loading data...")
    daily_data = load_all_daily()
    closes, volumes = build_closes_and_volumes(daily_data)
    print(f"   Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"   Date range: {closes.index[0].date()} to {closes.index[-1].date()}")

    # 2. Generate all strategy return series
    print("\n2. Generating strategy return series...")
    equity_curves = {}

    strategies = {
        'H-009': lambda: gen_h009_returns(daily_data),
        'H-011': lambda: gen_h011_returns(daily_data),
        'H-012': lambda: gen_h012_returns(closes),
        'H-019': lambda: gen_h019_returns(closes),
        'H-021': lambda: gen_h021_returns(closes, volumes),
        'H-024': lambda: gen_h024_returns(closes),
        'H-031': lambda: gen_h031_returns(closes, volumes),
        'H-039': lambda: gen_h039_returns(daily_data),
        'H-044': lambda: gen_h044_returns(closes),
        'H-046': lambda: gen_h046_returns(closes),
        'H-049': lambda: gen_h049_returns(closes),
        'H-052': lambda: gen_h052_returns(closes),
        'H-053': lambda: gen_h053_returns(closes),
        'H-059': lambda: gen_h059_returns(closes),
    }

    for name, gen_func in strategies.items():
        try:
            eq = gen_func()
            if eq is not None and len(eq) > 50:
                equity_curves[name] = eq
                rets = eq.pct_change().dropna()
                m = compute_metrics(rets)
                print(f"   {name}: Sharpe {m['sharpe']:.2f}, "
                      f"Return {m['annual_return']*100:+.1f}%, "
                      f"DD {m['max_dd']*100:.1f}%, "
                      f"Days {m['n_days']}")
            else:
                print(f"   {name}: SKIPPED (insufficient data)")
        except Exception as e:
            print(f"   {name}: ERROR — {e}")

    # 3. Build daily returns matrix (aligned)
    print(f"\n3. Building aligned returns matrix ({len(equity_curves)} strategies)...")
    returns_dict = {}
    for name, eq in equity_curves.items():
        rets = eq.pct_change().dropna()
        # Normalize timezone
        if rets.index.tz is not None:
            rets.index = rets.index.tz_localize(None)
        # Normalize to date-only index for alignment
        rets.index = pd.DatetimeIndex(rets.index.date)
        returns_dict[name] = rets

    returns_df = pd.DataFrame(returns_dict)
    returns_df = returns_df.dropna()
    print(f"   Common period: {returns_df.index[0].date()} to {returns_df.index[-1].date()}")
    print(f"   {len(returns_df)} overlapping days, {len(returns_df.columns)} strategies")

    # For strategies with shorter data (H-049), also build a wider matrix
    all_returns = pd.DataFrame(returns_dict)
    full_cols = [c for c in all_returns.columns if all_returns[c].notna().sum() > 500]
    short_cols = [c for c in all_returns.columns if c not in full_cols]
    print(f"   Full-period strategies: {full_cols}")
    if short_cols:
        print(f"   Short-period strategies: {short_cols}")

    # 4. Correlation matrix
    print("\n4. FULL CORRELATION MATRIX")
    print("=" * 70)
    corr = returns_df.corr()
    # Print in compact format
    strats = list(corr.columns)
    header = "         " + "  ".join([f"{s:>6}" for s in strats])
    print(header)
    for s1 in strats:
        row = f"{s1:>8} "
        for s2 in strats:
            v = corr.loc[s1, s2]
            if s1 == s2:
                row += f"{'  1.00':>8}"
            else:
                row += f"{v:>8.3f}"
        print(row)

    # 5. Individual strategy metrics
    print("\n5. INDIVIDUAL STRATEGY METRICS (full sample)")
    print("=" * 70)
    print(f"{'Strategy':>8} {'Sharpe':>8} {'Return':>8} {'Vol':>8} {'MaxDD':>8} {'Days':>6}")
    individual_metrics = {}
    for name in returns_df.columns:
        rets = returns_df[name]
        m = compute_metrics(rets)
        individual_metrics[name] = m
        print(f"{name:>8} {m['sharpe']:>8.2f} {m['annual_return']*100:>7.1f}% "
              f"{m['annual_vol']*100:>7.1f}% {m['max_dd']*100:>7.1f}% {m['n_days']:>6}")

    # 6. Portfolio optimization — multiple approaches
    print("\n6. PORTFOLIO OPTIMIZATION")
    print("=" * 70)

    # 6a. Current 5-strategy portfolio (for comparison)
    current_5 = ['H-009', 'H-012', 'H-019', 'H-021']
    current_5_in_data = [s for s in current_5 if s in returns_df.columns]
    if 'H-011' in returns_df.columns:
        current_5_in_data.append('H-011')
    current_weights = {'H-009': 0.10, 'H-011': 0.40, 'H-012': 0.10, 'H-019': 0.15, 'H-021': 0.25}

    print("\n  6a. CURRENT 5-STRATEGY PORTFOLIO (baseline)")
    avail = [s for s in current_weights if s in returns_df.columns]
    w_current = np.array([current_weights[s] for s in avail])
    w_current = w_current / w_current.sum()  # renormalize
    port_ret_current = returns_df[avail] @ w_current
    m = compute_metrics(port_ret_current)
    print(f"      Sharpe: {m['sharpe']:.2f}, Return: {m['annual_return']*100:+.1f}%, "
          f"DD: {m['max_dd']*100:.1f}%")
    for i, s in enumerate(avail):
        print(f"      {s}: {w_current[i]*100:.0f}%")

    # 6b. Current 5-strat with H-024 replacing H-019
    print("\n  6b. 5-STRATEGY WITH H-024 REPLACING H-019")
    replaced_weights = {'H-009': 0.10, 'H-011': 0.40, 'H-012': 0.10, 'H-024': 0.15, 'H-021': 0.25}
    avail2 = [s for s in replaced_weights if s in returns_df.columns]
    if len(avail2) == len(replaced_weights):
        w_replaced = np.array([replaced_weights[s] for s in avail2])
        port_ret_replaced = returns_df[avail2] @ w_replaced
        m2 = compute_metrics(port_ret_replaced)
        print(f"      Sharpe: {m2['sharpe']:.2f}, Return: {m2['annual_return']*100:+.1f}%, "
              f"DD: {m2['max_dd']*100:.1f}%")

    # 6c. Optimize over all available strategies
    print("\n  6c. OPTIMAL PORTFOLIO (all strategies, max Sharpe)")
    strat_list = list(returns_df.columns)
    for max_w in [0.30, 0.40, 0.50]:
        try:
            weights, opt_sharpe = optimize_portfolio(returns_df, method='max_sharpe',
                                                     min_weight=0.0, max_weight=max_w)
            port_ret = returns_df.values @ weights
            port_ret_series = pd.Series(port_ret, index=returns_df.index)
            m = compute_metrics(port_ret_series)
            print(f"\n      Max weight={max_w*100:.0f}%: Sharpe {m['sharpe']:.2f}, "
                  f"Return {m['annual_return']*100:+.1f}%, DD {m['max_dd']*100:.1f}%")
            for i, s in enumerate(strat_list):
                if weights[i] > 0.005:
                    print(f"        {s}: {weights[i]*100:.1f}%")
        except Exception as e:
            print(f"      max_weight={max_w}: optimization failed — {e}")

    # 6d. Equal weight across all strategies
    print("\n  6d. EQUAL WEIGHT (all strategies)")
    ew_ret = returns_df.mean(axis=1)
    m_ew = compute_metrics(ew_ret)
    print(f"      Sharpe: {m_ew['sharpe']:.2f}, Return: {m_ew['annual_return']*100:+.1f}%, "
          f"DD: {m_ew['max_dd']*100:.1f}%")

    # 6e. Risk parity
    print("\n  6e. RISK PARITY")
    try:
        weights_rp, _ = optimize_portfolio(returns_df, method='risk_parity', max_weight=0.40)
        port_ret_rp = returns_df.values @ weights_rp
        m_rp = compute_metrics(pd.Series(port_ret_rp, index=returns_df.index))
        print(f"      Sharpe: {m_rp['sharpe']:.2f}, Return: {m_rp['annual_return']*100:+.1f}%, "
              f"DD: {m_rp['max_dd']*100:.1f}%")
        for i, s in enumerate(strat_list):
            if weights_rp[i] > 0.005:
                print(f"        {s}: {weights_rp[i]*100:.1f}%")
    except Exception as e:
        print(f"      Risk parity failed — {e}")

    # 6f. Best N-strategy subsets (exhaustive for small N)
    print("\n  6f. BEST N-STRATEGY SUBSETS")
    for n_strats in [5, 6, 7, 8]:
        if n_strats > len(strat_list):
            continue
        best_sharpe = -999
        best_combo = None
        for combo in combinations(strat_list, n_strats):
            sub_ret = returns_df[list(combo)]
            try:
                w, _ = optimize_portfolio(sub_ret, method='max_sharpe',
                                          min_weight=0.0, max_weight=0.50)
                port = sub_ret.values @ w
                m = compute_metrics(pd.Series(port, index=sub_ret.index))
                if m['sharpe'] > best_sharpe:
                    best_sharpe = m['sharpe']
                    best_combo = combo
                    best_weights = w
                    best_metrics = m
            except:
                continue

        if best_combo:
            print(f"\n      Best {n_strats}-strategy: Sharpe {best_metrics['sharpe']:.2f}, "
                  f"Return {best_metrics['annual_return']*100:+.1f}%, "
                  f"DD {best_metrics['max_dd']*100:.1f}%")
            for i, s in enumerate(best_combo):
                if best_weights[i] > 0.005:
                    print(f"        {s}: {best_weights[i]*100:.1f}%")

    # 7. Recommended portfolio
    print("\n" + "=" * 70)
    print("7. RECOMMENDATIONS")
    print("=" * 70)

    # Identify high-correlation pairs to avoid
    print("\n  High-correlation pairs (>0.4):")
    for i, s1 in enumerate(strats):
        for j, s2 in enumerate(strats):
            if j > i and corr.loc[s1, s2] > 0.4:
                print(f"    {s1} / {s2}: {corr.loc[s1, s2]:.3f}")

    print("\n  Strategy categories:")
    print("    Directional: H-009 (BTC trend), H-039 (DOW)")
    print("    Carry/Arb: H-011 (funding)")
    print("    XS Momentum: H-012 (price mom), H-021 (vol mom), H-046 (acceleration)")
    print("    XS Value/Anomaly: H-019 (low vol), H-024 (low beta), H-031 (size)")
    print("    XS Positioning: H-049 (LSR), H-052 (premium), H-053 (funding XS)")
    print("    XS Fundamental: H-044 (OI divergence)")
    print("    XS Volatility: H-059 (vol term structure)")

    # Save results
    results = {
        'correlation_matrix': corr.to_dict(),
        'individual_metrics': individual_metrics,
        'n_strategies': len(returns_df.columns),
        'n_common_days': len(returns_df),
        'date_range': f"{returns_df.index[0].date()} to {returns_df.index[-1].date()}",
    }

    import json
    output_path = os.path.join(os.path.dirname(__file__), 'h055_results.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to {output_path}")


if __name__ == '__main__':
    main()
