"""
H-055 Portfolio Stress Test & Regime Analysis

Tests:
1. Tail risk: worst drawdown periods, VaR/CVaR, worst week/month
2. Correlation breakdown: rolling correlations during stress periods
3. Regime analysis: performance in bull/bear/sideways markets
4. Regime-adaptive allocation: dynamic weights based on BTC trend/vol regime
5. Monte Carlo: bootstrap simulation for confidence intervals
"""

import sys, os
import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import the equity generators from the optimizer
from strategies.portfolio_optimization.h055_portfolio_optimizer import (
    load_all_daily, build_closes_and_volumes, compute_metrics,
    gen_h009_returns, gen_h011_returns, gen_h012_returns,
    gen_h019_returns, gen_h021_returns, gen_h024_returns,
    gen_h031_returns, gen_h039_returns, gen_h044_returns,
    gen_h046_returns, gen_h049_returns, gen_h052_returns,
    gen_h053_returns,
)

# H-055 allocation
H055_STRATS = ['H-009', 'H-011', 'H-021', 'H-031', 'H-039', 'H-046', 'H-052', 'H-053']
H055_WEIGHTS = {
    'H-009': 0.12, 'H-011': 0.40, 'H-021': 0.07,
    'H-031': 0.13, 'H-039': 0.09, 'H-046': 0.05,
    'H-052': 0.08, 'H-053': 0.06,
}


def generate_all_equity(daily_data, closes, volumes):
    """Generate equity curves for all strategies."""
    generators = {
        'H-009': lambda: gen_h009_returns(daily_data),
        'H-011': lambda: gen_h011_returns(daily_data),
        'H-021': lambda: gen_h021_returns(closes, volumes),
        'H-031': lambda: gen_h031_returns(closes, volumes),
        'H-039': lambda: gen_h039_returns(daily_data),
        'H-046': lambda: gen_h046_returns(closes),
        'H-052': lambda: gen_h052_returns(closes),
        'H-053': lambda: gen_h053_returns(closes),
    }
    equity = {}
    for name, func in generators.items():
        try:
            eq = func()
            if eq is not None and len(eq) > 50:
                equity[name] = eq
        except Exception as e:
            print(f"  WARNING: {name} failed: {e}")
    return equity


def build_returns_df(equity_curves):
    """Build aligned daily returns DataFrame."""
    returns_dict = {}
    for name, eq in equity_curves.items():
        rets = eq.pct_change().dropna()
        if rets.index.tz is not None:
            rets.index = rets.index.tz_localize(None)
        rets.index = pd.DatetimeIndex(rets.index.date)
        returns_dict[name] = rets
    df = pd.DataFrame(returns_dict).dropna()
    return df


def portfolio_returns(returns_df, weights_dict):
    """Compute portfolio daily returns from strategy returns and weight dict."""
    cols = [c for c in weights_dict if c in returns_df.columns]
    w = np.array([weights_dict[c] for c in cols])
    w = w / w.sum()
    return returns_df[cols] @ w


# ═══════════════════════════════════════════════════════════════
# 1. TAIL RISK ANALYSIS
# ═══════════════════════════════════════════════════════════════

def tail_risk_analysis(port_rets, btc_rets):
    """Compute VaR, CVaR, worst periods."""
    print("\n" + "=" * 70)
    print("1. TAIL RISK ANALYSIS")
    print("=" * 70)

    # VaR and CVaR at various confidence levels
    for conf in [0.95, 0.99]:
        var = np.percentile(port_rets, (1 - conf) * 100)
        cvar = port_rets[port_rets <= var].mean()
        print(f"\n  {conf*100:.0f}% VaR (daily):  {var*100:.3f}%")
        print(f"  {conf*100:.0f}% CVaR (daily): {cvar*100:.3f}%")
        # Annualized
        var_ann = var * np.sqrt(365)
        cvar_ann = cvar * np.sqrt(365)
        print(f"  {conf*100:.0f}% VaR (annual):  {var_ann*100:.1f}%")
        print(f"  {conf*100:.0f}% CVaR (annual): {cvar_ann*100:.1f}%")

    # Worst N days
    print("\n  WORST 10 DAYS (portfolio):")
    worst_days = port_rets.nsmallest(10)
    for date, ret in worst_days.items():
        btc_ret = btc_rets.get(date, float('nan'))
        print(f"    {date}: portfolio {ret*100:+.3f}%, BTC {btc_ret*100:+.2f}%")

    # Best N days
    print("\n  BEST 10 DAYS (portfolio):")
    best_days = port_rets.nlargest(10)
    for date, ret in best_days.items():
        btc_ret = btc_rets.get(date, float('nan'))
        print(f"    {date}: portfolio {ret*100:+.3f}%, BTC {btc_ret*100:+.2f}%")

    # Worst weeks and months
    weekly = port_rets.resample('W').sum()
    monthly = port_rets.resample('ME').sum()

    print("\n  WORST 5 WEEKS:")
    for date, ret in weekly.nsmallest(5).items():
        print(f"    Week of {date}: {ret*100:+.2f}%")

    print("\n  WORST 5 MONTHS:")
    for date, ret in monthly.nsmallest(5).items():
        print(f"    {date.strftime('%Y-%m')}: {ret*100:+.2f}%")

    # Max drawdown analysis
    cum = (1 + port_rets).cumprod()
    running_max = cum.cummax()
    dd = cum / running_max - 1
    max_dd = dd.min()
    max_dd_end = dd.idxmin()

    # Find drawdown start
    peak_date = cum[:max_dd_end].idxmax()
    # Find recovery date
    recovery_dates = cum.index[cum.index > max_dd_end]
    peak_val = cum[peak_date]
    recovered = cum.loc[recovery_dates][cum.loc[recovery_dates] >= peak_val]
    if len(recovered) > 0:
        recovery_date = recovered.index[0]
        recovery_days = (recovery_date - max_dd_end).days
    else:
        recovery_date = "not recovered"
        recovery_days = (cum.index[-1] - max_dd_end).days

    print(f"\n  MAX DRAWDOWN: {max_dd*100:.2f}%")
    print(f"    Peak: {peak_date}")
    print(f"    Trough: {max_dd_end}")
    print(f"    Recovery: {recovery_date} ({recovery_days} days)")

    # Distribution stats
    print(f"\n  DISTRIBUTION STATS:")
    print(f"    Mean daily return: {port_rets.mean()*100:.4f}%")
    print(f"    Std daily return: {port_rets.std()*100:.4f}%")
    print(f"    Skewness: {port_rets.skew():.3f}")
    print(f"    Kurtosis: {port_rets.kurtosis():.3f}")
    print(f"    % positive days: {(port_rets > 0).mean()*100:.1f}%")
    print(f"    % days > +1%: {(port_rets > 0.01).mean()*100:.1f}%")
    print(f"    % days < -1%: {(port_rets < -0.01).mean()*100:.1f}%")

    return max_dd


# ═══════════════════════════════════════════════════════════════
# 2. CORRELATION BREAKDOWN
# ═══════════════════════════════════════════════════════════════

def correlation_breakdown(returns_df, btc_rets, weights_dict):
    """Analyze how strategy correlations change during stress."""
    print("\n" + "=" * 70)
    print("2. CORRELATION BREAKDOWN ANALYSIS")
    print("=" * 70)

    cols = [c for c in weights_dict if c in returns_df.columns]

    # Full-sample correlation
    full_corr = returns_df[cols].corr()
    avg_corr = full_corr.values[np.triu_indices_from(full_corr.values, k=1)].mean()
    print(f"\n  Full-sample average pairwise correlation: {avg_corr:.4f}")

    # Split by BTC regime
    btc_aligned = btc_rets.reindex(returns_df.index).dropna()
    common_idx = returns_df.index.intersection(btc_aligned.index)

    # Stress days: worst 10% of BTC days
    btc_p10 = np.percentile(btc_aligned, 10)
    btc_p90 = np.percentile(btc_aligned, 90)

    stress_idx = common_idx[btc_aligned.loc[common_idx] <= btc_p10]
    rally_idx = common_idx[btc_aligned.loc[common_idx] >= btc_p90]
    normal_idx = common_idx[(btc_aligned.loc[common_idx] > btc_p10) &
                            (btc_aligned.loc[common_idx] < btc_p90)]

    for label, idx in [("STRESS (worst 10% BTC days)", stress_idx),
                       ("RALLY (best 10% BTC days)", rally_idx),
                       ("NORMAL (middle 80%)", normal_idx)]:
        if len(idx) < 10:
            print(f"\n  {label}: insufficient data ({len(idx)} days)")
            continue
        sub_corr = returns_df.loc[idx, cols].corr()
        sub_avg = sub_corr.values[np.triu_indices_from(sub_corr.values, k=1)].mean()
        sub_port = portfolio_returns(returns_df.loc[idx], weights_dict)
        print(f"\n  {label} ({len(idx)} days):")
        print(f"    Avg pairwise correlation: {sub_avg:.4f}")
        print(f"    Portfolio mean daily return: {sub_port.mean()*100:.4f}%")
        print(f"    Portfolio worst day: {sub_port.min()*100:.3f}%")
        print(f"    Portfolio best day: {sub_port.max()*100:.3f}%")

    # Rolling 30-day correlation average
    print("\n  ROLLING 30D AVERAGE CORRELATION:")
    rolling_corrs = []
    window = 30
    for i in range(window, len(returns_df)):
        sub = returns_df.iloc[i-window:i][cols]
        c = sub.corr()
        avg = c.values[np.triu_indices_from(c.values, k=1)].mean()
        rolling_corrs.append((returns_df.index[i], avg))

    rc = pd.Series({d: v for d, v in rolling_corrs})
    print(f"    Min rolling avg corr: {rc.min():.4f} on {rc.idxmin()}")
    print(f"    Max rolling avg corr: {rc.max():.4f} on {rc.idxmax()}")
    print(f"    Mean: {rc.mean():.4f}, Std: {rc.std():.4f}")
    print(f"    % of time corr > 0.3: {(rc > 0.3).mean()*100:.1f}%")
    print(f"    % of time corr > 0.5: {(rc > 0.5).mean()*100:.1f}%")


# ═══════════════════════════════════════════════════════════════
# 3. REGIME ANALYSIS
# ═══════════════════════════════════════════════════════════════

def regime_analysis(returns_df, btc_daily, weights_dict):
    """Performance across market regimes."""
    print("\n" + "=" * 70)
    print("3. REGIME ANALYSIS")
    print("=" * 70)

    btc_close = btc_daily['close']
    if btc_close.index.tz is not None:
        btc_close.index = btc_close.index.tz_localize(None)
    btc_close.index = pd.DatetimeIndex(btc_close.index.date)

    common_idx = returns_df.index.intersection(btc_close.index)
    btc_close = btc_close.loc[common_idx]
    ret_sub = returns_df.loc[common_idx]

    # Regime 1: BTC trend (EMA20 vs EMA50)
    ema20 = btc_close.ewm(span=20, adjust=False).mean()
    ema50 = btc_close.ewm(span=50, adjust=False).mean()
    uptrend = ema20 > ema50
    downtrend = ema20 < ema50

    print("\n  REGIME 1: BTC TREND (EMA20 vs EMA50)")
    for label, mask in [("UPTREND", uptrend), ("DOWNTREND", downtrend)]:
        idx = mask[mask].index.intersection(ret_sub.index)
        if len(idx) < 30:
            continue
        port = portfolio_returns(ret_sub.loc[idx], weights_dict)
        m = compute_metrics(port)
        print(f"    {label} ({len(idx)} days, {len(idx)/len(ret_sub)*100:.0f}%):")
        print(f"      Sharpe: {m['sharpe']:.2f}, Return: {m['annual_return']*100:+.1f}%, DD: {m['max_dd']*100:.1f}%")
        # Per-strategy breakdown
        for s in weights_dict:
            if s in ret_sub.columns:
                sm = compute_metrics(ret_sub.loc[idx, s])
                print(f"        {s}: Sharpe {sm['sharpe']:.2f}, Return {sm['annual_return']*100:+.1f}%")

    # Regime 2: Volatility regime (30d realized vol)
    btc_ret = btc_close.pct_change()
    vol_30d = btc_ret.rolling(30).std() * np.sqrt(365)
    vol_median = vol_30d.median()

    print(f"\n  REGIME 2: BTC VOLATILITY (30d realized, median={vol_median*100:.1f}%)")
    high_vol = vol_30d > vol_median
    low_vol = vol_30d <= vol_median

    for label, mask in [("HIGH VOL", high_vol), ("LOW VOL", low_vol)]:
        idx = mask[mask].index.intersection(ret_sub.index)
        if len(idx) < 30:
            continue
        port = portfolio_returns(ret_sub.loc[idx], weights_dict)
        m = compute_metrics(port)
        print(f"    {label} ({len(idx)} days):")
        print(f"      Sharpe: {m['sharpe']:.2f}, Return: {m['annual_return']*100:+.1f}%, DD: {m['max_dd']*100:.1f}%")

    # Regime 3: BTC drawdown depth
    cum_btc = btc_close / btc_close.cummax()
    deep_dd = cum_btc < 0.85  # >15% from peak
    shallow = cum_btc >= 0.95  # within 5% of peak
    mid_dd = (~deep_dd) & (~shallow)

    print("\n  REGIME 3: BTC DRAWDOWN DEPTH")
    for label, mask in [("NEAR PEAK (<5% from ATH)", shallow),
                        ("MODERATE DD (5-15%)", mid_dd),
                        ("DEEP DD (>15%)", deep_dd)]:
        idx = mask[mask].index.intersection(ret_sub.index)
        if len(idx) < 20:
            print(f"    {label}: insufficient data ({len(idx)} days)")
            continue
        port = portfolio_returns(ret_sub.loc[idx], weights_dict)
        m = compute_metrics(port)
        print(f"    {label} ({len(idx)} days, {len(idx)/len(ret_sub)*100:.0f}%):")
        print(f"      Sharpe: {m['sharpe']:.2f}, Return: {m['annual_return']*100:+.1f}%, DD: {m['max_dd']*100:.1f}%")

    # Regime 4: Year-by-year
    print("\n  REGIME 4: YEAR-BY-YEAR PERFORMANCE")
    port_all = portfolio_returns(ret_sub, weights_dict)
    for year in sorted(ret_sub.index.year.unique()):
        yr_idx = ret_sub.index[ret_sub.index.year == year]
        if len(yr_idx) < 30:
            continue
        port_yr = portfolio_returns(ret_sub.loc[yr_idx], weights_dict)
        m = compute_metrics(port_yr)
        print(f"    {year}: Sharpe {m['sharpe']:.2f}, Return {m['annual_return']*100:+.1f}%, DD {m['max_dd']*100:.1f}%")

    # Regime 5: Monthly returns heatmap
    print("\n  REGIME 5: MONTHLY RETURNS")
    monthly = port_all.resample('ME').apply(lambda x: (1+x).prod() - 1)
    n_positive = (monthly > 0).sum()
    n_total = len(monthly)
    print(f"    Positive months: {n_positive}/{n_total} ({n_positive/n_total*100:.0f}%)")
    print(f"    Best month: {monthly.max()*100:+.2f}%")
    print(f"    Worst month: {monthly.min()*100:+.2f}%")
    print(f"    Mean month: {monthly.mean()*100:+.2f}%")
    print(f"    Median month: {monthly.median()*100:+.2f}%")

    return vol_30d, uptrend


# ═══════════════════════════════════════════════════════════════
# 4. REGIME-ADAPTIVE ALLOCATION
# ═══════════════════════════════════════════════════════════════

def regime_adaptive_allocation(returns_df, btc_daily, weights_dict):
    """Test dynamic weight adjustment based on regime."""
    print("\n" + "=" * 70)
    print("4. REGIME-ADAPTIVE ALLOCATION")
    print("=" * 70)

    btc_close = btc_daily['close']
    if btc_close.index.tz is not None:
        btc_close.index = btc_close.index.tz_localize(None)
    btc_close.index = pd.DatetimeIndex(btc_close.index.date)
    common_idx = returns_df.index.intersection(btc_close.index)
    btc_close = btc_close.loc[common_idx]
    ret_sub = returns_df.loc[common_idx]

    cols = [c for c in weights_dict if c in ret_sub.columns]

    # Static baseline
    static_port = portfolio_returns(ret_sub, weights_dict)
    static_m = compute_metrics(static_port)
    print(f"\n  STATIC H-055 (baseline):")
    print(f"    Sharpe: {static_m['sharpe']:.2f}, Return: {static_m['annual_return']*100:+.1f}%, DD: {static_m['max_dd']*100:.1f}%")

    # Strategy A: Trend-based allocation
    # In downtrend: increase H-009 (trend follower benefits from sustained moves)
    # In uptrend: increase H-011 (funding rates tend to be more positive)
    ema20 = btc_close.ewm(span=20, adjust=False).mean()
    ema50 = btc_close.ewm(span=50, adjust=False).mean()
    uptrend = (ema20 > ema50).shift(1).fillna(True)

    # Build dynamic returns
    uptrend_weights = dict(weights_dict)
    downtrend_weights = dict(weights_dict)

    # Shift weight from H-011 to H-009 in downtrend
    if 'H-009' in uptrend_weights and 'H-011' in uptrend_weights:
        uptrend_weights['H-009'] = 0.08
        uptrend_weights['H-011'] = 0.44
        downtrend_weights['H-009'] = 0.20
        downtrend_weights['H-011'] = 0.32

    adaptive_rets = pd.Series(0.0, index=ret_sub.index)
    for date in ret_sub.index:
        if date in uptrend.index and uptrend.get(date, True):
            w = uptrend_weights
        else:
            w = downtrend_weights
        w_arr = np.array([w.get(c, 0) for c in cols])
        w_arr = w_arr / w_arr.sum()
        adaptive_rets.loc[date] = (ret_sub.loc[date, cols].values * w_arr).sum()

    adaptive_m = compute_metrics(adaptive_rets)
    print(f"\n  STRATEGY A: TREND-BASED (shift H-011→H-009 in downtrend)")
    print(f"    Sharpe: {adaptive_m['sharpe']:.2f}, Return: {adaptive_m['annual_return']*100:+.1f}%, DD: {adaptive_m['max_dd']*100:.1f}%")
    print(f"    vs static: Sharpe {adaptive_m['sharpe'] - static_m['sharpe']:+.2f}")

    # Strategy B: Vol-based allocation
    # In high vol: reduce overall exposure (scale to 50%)
    # In low vol: full exposure
    btc_ret = btc_close.pct_change()
    vol_30d = btc_ret.rolling(30).std() * np.sqrt(365)
    vol_median = vol_30d.median()
    high_vol = (vol_30d > vol_median * 1.5).shift(1).fillna(False)

    vol_adaptive_rets = static_port.copy()
    for date in ret_sub.index:
        if date in high_vol.index and high_vol.get(date, False):
            vol_adaptive_rets.loc[date] *= 0.5

    vol_m = compute_metrics(vol_adaptive_rets)
    print(f"\n  STRATEGY B: VOL-BASED (50% exposure in high vol)")
    print(f"    Sharpe: {vol_m['sharpe']:.2f}, Return: {vol_m['annual_return']*100:+.1f}%, DD: {vol_m['max_dd']*100:.1f}%")
    print(f"    vs static: Sharpe {vol_m['sharpe'] - static_m['sharpe']:+.2f}")

    # Strategy C: Momentum-based reweighting
    # Every 30 days, overweight strategies that performed well in last 60 days
    print(f"\n  STRATEGY C: MOMENTUM REWEIGHT (60d lookback, 30d rebal)")
    mom_rets = pd.Series(0.0, index=ret_sub.index)
    rebal_freq = 30
    lookback = 60
    current_w = np.array([weights_dict.get(c, 0) for c in cols])
    current_w = current_w / current_w.sum()

    for i in range(lookback, len(ret_sub)):
        if (i - lookback) % rebal_freq == 0 and i > lookback:
            # Compute trailing Sharpe for each strategy
            trailing = ret_sub.iloc[i-lookback:i][cols]
            trailing_sharpes = trailing.mean() / trailing.std()
            trailing_sharpes = trailing_sharpes.clip(lower=0)  # no negative weights

            if trailing_sharpes.sum() > 0:
                # Blend: 50% static + 50% momentum-weighted
                static_w = np.array([weights_dict.get(c, 0) for c in cols])
                static_w = static_w / static_w.sum()
                mom_w = trailing_sharpes.values / trailing_sharpes.sum()
                current_w = 0.5 * static_w + 0.5 * mom_w
                current_w = current_w / current_w.sum()
                # Cap at 50% per strategy
                current_w = np.minimum(current_w, 0.50)
                current_w = current_w / current_w.sum()

        mom_rets.iloc[i] = (ret_sub.iloc[i][cols].values * current_w).sum()

    mom_rets = mom_rets.iloc[lookback:]
    mom_m = compute_metrics(mom_rets)
    print(f"    Sharpe: {mom_m['sharpe']:.2f}, Return: {mom_m['annual_return']*100:+.1f}%, DD: {mom_m['max_dd']*100:.1f}%")
    print(f"    vs static: Sharpe {mom_m['sharpe'] - static_m['sharpe']:+.2f}")

    # Strategy D: Drawdown protection
    # When portfolio drawdown > 5%, reduce exposure to 50%
    # When drawdown > 10%, reduce to 25%
    print(f"\n  STRATEGY D: DRAWDOWN PROTECTION (reduce exposure in DD)")
    dd_rets = static_port.copy()
    cum = (1 + dd_rets).cumprod()
    for i in range(1, len(cum)):
        running_max = cum.iloc[:i].max()
        dd_pct = cum.iloc[i-1] / running_max - 1
        if dd_pct < -0.10:
            dd_rets.iloc[i] *= 0.25
        elif dd_pct < -0.05:
            dd_rets.iloc[i] *= 0.50
        # Recompute cumulative
        cum.iloc[i] = cum.iloc[i-1] * (1 + dd_rets.iloc[i])

    dd_m = compute_metrics(dd_rets)
    print(f"    Sharpe: {dd_m['sharpe']:.2f}, Return: {dd_m['annual_return']*100:+.1f}%, DD: {dd_m['max_dd']*100:.1f}%")
    print(f"    vs static: Sharpe {dd_m['sharpe'] - static_m['sharpe']:+.2f}")

    return static_m


# ═══════════════════════════════════════════════════════════════
# 5. MONTE CARLO BOOTSTRAP
# ═══════════════════════════════════════════════════════════════

def monte_carlo_analysis(port_rets, n_simulations=5000, horizon_days=365):
    """Bootstrap simulation for confidence intervals."""
    print("\n" + "=" * 70)
    print("5. MONTE CARLO BOOTSTRAP SIMULATION")
    print("=" * 70)

    daily_rets = port_rets.values
    n_days = len(daily_rets)

    # Block bootstrap (30-day blocks to preserve autocorrelation)
    block_size = 30
    n_blocks = horizon_days // block_size + 1

    sim_returns = np.zeros(n_simulations)
    sim_dds = np.zeros(n_simulations)
    sim_sharpes = np.zeros(n_simulations)

    np.random.seed(42)
    for sim in range(n_simulations):
        # Sample blocks with replacement
        path = []
        for _ in range(n_blocks):
            start = np.random.randint(0, max(1, n_days - block_size))
            block = daily_rets[start:start + block_size]
            path.extend(block)
        path = np.array(path[:horizon_days])

        cum = np.cumprod(1 + path)
        sim_returns[sim] = cum[-1] - 1
        sim_dds[sim] = (cum / np.maximum.accumulate(cum) - 1).min()
        ann_ret = (1 + np.mean(path)) ** 365 - 1
        ann_vol = np.std(path) * np.sqrt(365)
        sim_sharpes[sim] = ann_ret / ann_vol if ann_vol > 0 else 0

    # Results
    print(f"\n  Horizon: {horizon_days} days ({horizon_days/365:.1f} years)")
    print(f"  Simulations: {n_simulations}")
    print(f"  Block size: {block_size} days")

    print(f"\n  ANNUAL RETURN DISTRIBUTION:")
    for p in [5, 10, 25, 50, 75, 90, 95]:
        print(f"    {p}th percentile: {np.percentile(sim_returns, p)*100:+.1f}%")
    print(f"    Mean: {sim_returns.mean()*100:+.1f}%")
    print(f"    P(loss): {(sim_returns < 0).mean()*100:.1f}%")
    print(f"    P(>20% return): {(sim_returns > 0.20).mean()*100:.1f}%")
    print(f"    P(>30% return): {(sim_returns > 0.30).mean()*100:.1f}%")

    print(f"\n  MAX DRAWDOWN DISTRIBUTION:")
    for p in [5, 10, 25, 50, 75, 90, 95]:
        print(f"    {p}th percentile: {np.percentile(sim_dds, p)*100:.1f}%")
    print(f"    Mean: {sim_dds.mean()*100:.1f}%")
    print(f"    P(DD > 10%): {(sim_dds < -0.10).mean()*100:.1f}%")
    print(f"    P(DD > 20%): {(sim_dds < -0.20).mean()*100:.1f}%")
    print(f"    P(DD > 30%): {(sim_dds < -0.30).mean()*100:.1f}%")

    print(f"\n  SHARPE RATIO DISTRIBUTION:")
    for p in [5, 10, 25, 50, 75, 90, 95]:
        print(f"    {p}th percentile: {np.percentile(sim_sharpes, p):.2f}")
    print(f"    P(Sharpe < 1.0): {(sim_sharpes < 1.0).mean()*100:.1f}%")
    print(f"    P(Sharpe < 1.5): {(sim_sharpes < 1.5).mean()*100:.1f}%")
    print(f"    P(Sharpe > 3.0): {(sim_sharpes > 3.0).mean()*100:.1f}%")


# ═══════════════════════════════════════════════════════════════
# 6. STRATEGY CONTRIBUTION & MARGINAL VALUE
# ═══════════════════════════════════════════════════════════════

def strategy_contribution_analysis(returns_df, weights_dict):
    """Analyze each strategy's contribution to portfolio."""
    print("\n" + "=" * 70)
    print("6. STRATEGY CONTRIBUTION ANALYSIS")
    print("=" * 70)

    cols = [c for c in weights_dict if c in returns_df.columns]
    full_port = portfolio_returns(returns_df, weights_dict)
    full_m = compute_metrics(full_port)

    print(f"\n  FULL PORTFOLIO: Sharpe {full_m['sharpe']:.2f}, Return {full_m['annual_return']*100:+.1f}%, DD {full_m['max_dd']*100:.1f}%")

    # Leave-one-out analysis
    print(f"\n  LEAVE-ONE-OUT ANALYSIS (removing each strategy):")
    for remove_strat in cols:
        remaining = {k: v for k, v in weights_dict.items() if k != remove_strat and k in cols}
        if len(remaining) < 2:
            continue
        loo_port = portfolio_returns(returns_df, remaining)
        loo_m = compute_metrics(loo_port)
        delta_sharpe = loo_m['sharpe'] - full_m['sharpe']
        delta_dd = loo_m['max_dd'] - full_m['max_dd']
        print(f"    Without {remove_strat}: Sharpe {loo_m['sharpe']:.2f} ({delta_sharpe:+.2f}), "
              f"DD {loo_m['max_dd']*100:.1f}% ({delta_dd*100:+.1f}pp)")

    # Return attribution
    print(f"\n  RETURN ATTRIBUTION (weight × strategy return):")
    for s in cols:
        w = weights_dict[s]
        s_ret = returns_df[s].mean() * 365
        contrib = w * s_ret
        print(f"    {s} ({w*100:.0f}%): strategy ann return {s_ret*100:+.1f}%, "
              f"contribution {contrib*100:+.1f}pp")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("H-055 PORTFOLIO STRESS TEST & REGIME ANALYSIS")
    print("=" * 70)

    # Load data
    print("\nLoading data...")
    daily_data = load_all_daily()
    closes, volumes = build_closes_and_volumes(daily_data)
    print(f"  {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"  Range: {closes.index[0].date()} to {closes.index[-1].date()}")

    # Generate equity curves
    print("\nGenerating equity curves...")
    equity_curves = generate_all_equity(daily_data, closes, volumes)
    print(f"  Generated {len(equity_curves)} strategy equity curves")
    for name, eq in equity_curves.items():
        print(f"    {name}: {len(eq)} bars, final equity ${eq.iloc[-1]:,.0f}")

    # Build returns
    returns_df = build_returns_df(equity_curves)
    print(f"\n  Aligned returns: {len(returns_df)} days, {len(returns_df.columns)} strategies")
    print(f"  Period: {returns_df.index[0]} to {returns_df.index[-1]}")

    # BTC returns for reference
    btc = daily_data['BTC/USDT'].copy()
    if btc.index.tz is not None:
        btc.index = btc.index.tz_localize(None)
    btc_rets = btc['close'].pct_change().dropna()
    btc_rets.index = pd.DatetimeIndex(btc_rets.index.date)

    # Portfolio returns
    port_rets = portfolio_returns(returns_df, H055_WEIGHTS)

    # Run all analyses
    tail_risk_analysis(port_rets, btc_rets)
    correlation_breakdown(returns_df, btc_rets, H055_WEIGHTS)
    regime_analysis(returns_df, daily_data['BTC/USDT'], H055_WEIGHTS)
    regime_adaptive_allocation(returns_df, daily_data['BTC/USDT'], H055_WEIGHTS)
    monte_carlo_analysis(port_rets)
    strategy_contribution_analysis(returns_df, H055_WEIGHTS)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    port_m = compute_metrics(port_rets)
    print(f"  H-055 Portfolio: Sharpe {port_m['sharpe']:.2f}, Return {port_m['annual_return']*100:+.1f}%, DD {port_m['max_dd']*100:.1f}%")
    print(f"  Days analyzed: {len(port_rets)}")
    print(f"  % positive days: {(port_rets > 0).mean()*100:.1f}%")

    # Save results
    import json
    results = {
        'portfolio_metrics': {k: float(v) if isinstance(v, (np.floating, float)) else v
                              for k, v in port_m.items()},
        'n_strategies': len(equity_curves),
        'n_days': len(port_rets),
        'date_range': f"{returns_df.index[0]} to {returns_df.index[-1]}",
    }
    results_path = os.path.join(os.path.dirname(__file__), 'h055_stress_results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to {results_path}")


if __name__ == '__main__':
    main()
