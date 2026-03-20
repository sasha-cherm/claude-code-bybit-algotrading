"""
H-047: Volatility Change Factor (Cross-Sectional, 14 Assets)
H-048: Realized Correlation Change Factor (Cross-Sectional, 14 Assets)

H-047: Rank assets by change in realized volatility (short window vs long window).
       Long assets whose vol is decreasing, short assets whose vol is increasing.
       Or the reverse — vol momentum (rising vol = opportunity).

H-048: Rank assets by change in correlation with BTC.
       Assets becoming less correlated with BTC may offer diversification alpha.

Uses same 14-asset daily framework as other cross-sectional factors.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from itertools import product

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return


ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]


def load_daily_closes():
    """Load 14-asset daily close prices."""
    frames = {}
    for sym in ASSETS:
        df = fetch_and_cache(sym, "1h", limit_days=800)
        daily = df['close'].resample('1D').last().dropna()
        frames[sym.replace('/USDT', '')] = daily
    closes = pd.DataFrame(frames).dropna()
    print(f"Loaded {len(closes)} daily bars, {len(closes.columns)} assets")
    return closes


def compute_vol_change_signal(closes, short_window, long_window):
    """
    Compute volatility change signal: ratio of short-window vol to long-window vol.
    High ratio = vol increasing. Low ratio = vol decreasing.

    Returns DataFrame of z-scored signals (cross-sectional, daily).
    """
    returns = closes.pct_change()

    # Compute rolling vol (annualized std)
    vol_short = returns.rolling(short_window).std() * np.sqrt(365)
    vol_long = returns.rolling(long_window).std() * np.sqrt(365)

    # Vol change ratio (short/long - 1). Positive = vol increasing.
    vol_change = (vol_short / vol_long) - 1

    # Cross-sectional z-score
    mean = vol_change.mean(axis=1)
    std = vol_change.std(axis=1)
    z_scored = vol_change.sub(mean, axis=0).div(std, axis=0)

    return z_scored


def compute_corr_change_signal(closes, window, delta_window):
    """
    Compute correlation change signal.
    For each asset, compute rolling correlation with BTC.
    Then rank by change in correlation (recent - past).

    Long assets becoming LESS correlated (diversifiers).
    Short assets becoming MORE correlated.
    """
    returns = closes.pct_change()
    btc_returns = returns['BTC']

    corr_signals = pd.DataFrame(index=returns.index, columns=[c for c in returns.columns if c != 'BTC'])

    for col in corr_signals.columns:
        rolling_corr = returns[col].rolling(window).corr(btc_returns)
        # Change in correlation
        corr_change = rolling_corr - rolling_corr.shift(delta_window)
        corr_signals[col] = corr_change

    # Cross-sectional z-score (across non-BTC assets)
    mean = corr_signals.mean(axis=1)
    std = corr_signals.std(axis=1)
    z_scored = corr_signals.sub(mean, axis=0).div(std, axis=0)

    return z_scored


def backtest_xs_factor(closes, signals, rebal_days, n_long_short, direction="long_low"):
    """
    Backtest cross-sectional factor.
    direction: "long_low" = long lowest signal, short highest (vol decreasing = good)
               "long_high" = long highest signal, short lowest (vol increasing = good)

    Returns daily portfolio returns series.
    """
    returns = closes.pct_change()
    assets = signals.columns.tolist()
    asset_returns = returns[assets] if all(a in returns.columns for a in assets) else returns[[a for a in assets if a in returns.columns]]

    # Align
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

        # Use lagged signal (t-1)
        prev_date = common_idx[i-1]
        sig = signals.loc[prev_date].dropna()

        if len(sig) < 2 * n_long_short:
            continue

        # Check if rebalance day
        days_since = (date - last_rebal).days if last_rebal else rebal_days + 1

        if days_since >= rebal_days:
            ranked = sig.sort_values()
            if direction == "long_low":
                current_longs = ranked.index[:n_long_short].tolist()
                current_shorts = ranked.index[-n_long_short:].tolist()
            else:  # long_high
                current_longs = ranked.index[-n_long_short:].tolist()
                current_shorts = ranked.index[:n_long_short].tolist()
            last_rebal = date

        if current_longs and current_shorts:
            w = 1.0 / (2 * n_long_short)
            day_ret = 0.0
            for a in current_longs:
                if a in asset_returns.columns:
                    day_ret += w * asset_returns.loc[date, a]
            for a in current_shorts:
                if a in asset_returns.columns:
                    day_ret -= w * asset_returns.loc[date, a]
            portfolio_returns.loc[date] = day_ret

    return portfolio_returns


def run_h047_research():
    """Test volatility change as cross-sectional factor."""
    print("=" * 60)
    print("H-047: Volatility Change Factor Research")
    print("=" * 60)

    closes = load_daily_closes()

    # Parameter grid
    short_windows = [5, 10, 20]
    long_windows = [30, 60, 90]
    rebal_days_list = [3, 5, 10, 21]
    n_list = [3, 4, 5]
    directions = ["long_low", "long_high"]  # long_low = short rising vol, long_high = long rising vol

    results = []

    for sw, lw, rd, n, direction in product(short_windows, long_windows, rebal_days_list, n_list, directions):
        if sw >= lw:
            continue

        signals = compute_vol_change_signal(closes, sw, lw)
        port_ret = backtest_xs_factor(closes, signals, rd, n, direction)

        # Filter non-zero returns
        active = port_ret[port_ret != 0]
        if len(active) < 100:
            continue

        sr = sharpe_ratio(port_ret)
        ar = annual_return(port_ret)
        md = max_drawdown(port_ret)

        results.append({
            'short_w': sw, 'long_w': lw, 'rebal': rd, 'n': n,
            'direction': direction,
            'sharpe': sr, 'ann_ret': ar, 'max_dd': md,
            'n_days': len(active),
        })

    df = pd.DataFrame(results)
    print(f"\nTotal parameter sets: {len(df)}")

    positive = df[df['sharpe'] > 0]
    print(f"Positive Sharpe: {len(positive)}/{len(df)} ({100*len(positive)/len(df):.0f}%)")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"Median Sharpe: {df['sharpe'].median():.3f}")

    # By direction
    for d in directions:
        sub = df[df['direction'] == d]
        pos = sub[sub['sharpe'] > 0]
        print(f"\n  Direction={d}: {len(pos)}/{len(sub)} positive ({100*len(pos)/len(sub):.0f}%), mean Sharpe {sub['sharpe'].mean():.3f}")

    # Top 10
    print(f"\nTop 10 by Sharpe:")
    top = df.nlargest(10, 'sharpe')
    for _, r in top.iterrows():
        print(f"  SW{r['short_w']}_LW{r['long_w']}_R{r['rebal']}_N{r['n']}_{r['direction']}: "
              f"Sharpe {r['sharpe']:.2f}, ret {r['ann_ret']:.1%}, DD {r['max_dd']:.1%}")

    # Walk-forward on best params
    if len(positive) > 0:
        best = df.nlargest(1, 'sharpe').iloc[0]
        print(f"\n--- Walk-Forward Validation (best: SW{best['short_w']}_LW{best['long_w']}_R{best['rebal']}_N{best['n']}_{best['direction']}) ---")

        signals = compute_vol_change_signal(closes, int(best['short_w']), int(best['long_w']))
        port_ret = backtest_xs_factor(closes, signals, int(best['rebal']), int(best['n']), best['direction'])

        # 4-fold WF
        active_idx = port_ret[port_ret != 0].index
        if len(active_idx) > 200:
            fold_size = len(active_idx) // 4
            print(f"  Fold size: {fold_size} days")
            for fold in range(4):
                start = fold * fold_size
                end = min((fold + 1) * fold_size, len(active_idx))
                fold_ret = port_ret.loc[active_idx[start:end]]
                sr = sharpe_ratio(fold_ret)
                ar = annual_return(fold_ret)
                print(f"  Fold {fold+1}: Sharpe {sr:.2f}, ret {ar:.1%}")

    return df


def run_h048_research():
    """Test correlation change as cross-sectional factor."""
    print("\n" + "=" * 60)
    print("H-048: Correlation Change Factor Research")
    print("=" * 60)

    closes = load_daily_closes()

    # Parameter grid
    corr_windows = [30, 60, 90]
    delta_windows = [10, 20, 30]
    rebal_days_list = [5, 10, 21]
    n_list = [3, 4, 5]
    directions = ["long_low", "long_high"]  # long_low = long assets becoming LESS correlated

    results = []

    for cw, dw, rd, n, direction in product(corr_windows, delta_windows, rebal_days_list, n_list, directions):
        if dw >= cw:
            continue

        signals = compute_corr_change_signal(closes, cw, dw)
        # Note: signals don't include BTC, so backtest on non-BTC assets
        asset_closes = closes.drop(columns=['BTC'])
        port_ret = backtest_xs_factor(asset_closes, signals, rd, n, direction)

        active = port_ret[port_ret != 0]
        if len(active) < 100:
            continue

        sr = sharpe_ratio(port_ret)
        ar = annual_return(port_ret)
        md = max_drawdown(port_ret)

        results.append({
            'corr_w': cw, 'delta_w': dw, 'rebal': rd, 'n': n,
            'direction': direction,
            'sharpe': sr, 'ann_ret': ar, 'max_dd': md,
            'n_days': len(active),
        })

    df = pd.DataFrame(results)
    print(f"\nTotal parameter sets: {len(df)}")

    positive = df[df['sharpe'] > 0]
    print(f"Positive Sharpe: {len(positive)}/{len(df)} ({100*len(positive)/len(df):.0f}%)")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"Median Sharpe: {df['sharpe'].median():.3f}")

    # By direction
    for d in directions:
        sub = df[df['direction'] == d]
        if len(sub) > 0:
            pos = sub[sub['sharpe'] > 0]
            print(f"\n  Direction={d}: {len(pos)}/{len(sub)} positive ({100*len(pos)/len(sub):.0f}%), mean Sharpe {sub['sharpe'].mean():.3f}")

    # Top 10
    print(f"\nTop 10 by Sharpe:")
    top = df.nlargest(10, 'sharpe')
    for _, r in top.iterrows():
        print(f"  CW{r['corr_w']}_DW{r['delta_w']}_R{r['rebal']}_N{r['n']}_{r['direction']}: "
              f"Sharpe {r['sharpe']:.2f}, ret {r['ann_ret']:.1%}, DD {r['max_dd']:.1%}")

    # Walk-forward on best
    if len(positive) > 0:
        best = df.nlargest(1, 'sharpe').iloc[0]
        print(f"\n--- Walk-Forward (best: CW{best['corr_w']}_DW{best['delta_w']}_R{best['rebal']}_N{best['n']}_{best['direction']}) ---")

        signals = compute_corr_change_signal(closes, int(best['corr_w']), int(best['delta_w']))
        asset_closes = closes.drop(columns=['BTC'])
        port_ret = backtest_xs_factor(asset_closes, signals, int(best['rebal']), int(best['n']), best['direction'])

        active_idx = port_ret[port_ret != 0].index
        if len(active_idx) > 200:
            fold_size = len(active_idx) // 4
            print(f"  Fold size: {fold_size} days")
            for fold in range(4):
                start = fold * fold_size
                end = min((fold + 1) * fold_size, len(active_idx))
                fold_ret = port_ret.loc[active_idx[start:end]]
                sr = sharpe_ratio(fold_ret)
                ar = annual_return(fold_ret)
                print(f"  Fold {fold+1}: Sharpe {sr:.2f}, ret {ar:.1%}")

    return df


def compute_correlations(closes, best_params_47=None, best_params_48=None):
    """Compute correlations with existing strategies."""
    print("\n" + "=" * 60)
    print("Correlation Analysis with Existing Strategies")
    print("=" * 60)

    # Load existing strategy returns from paper trade equity histories
    import json

    strats = {}

    # H-012 XSMom
    signals_mom = compute_momentum_signal(closes, 60)
    strats['H-012'] = backtest_xs_factor(closes, signals_mom, 5, 4, "long_high")

    # H-019 LowVol
    returns = closes.pct_change()
    vol20 = returns.rolling(20).std() * np.sqrt(365)
    vol_z = vol20.sub(vol20.mean(axis=1), axis=0).div(vol20.std(axis=1), axis=0)
    strats['H-019'] = backtest_xs_factor(closes, vol_z, 21, 3, "long_low")

    # H-021 VolMom
    volumes = load_daily_volumes()
    vol_ratio = volumes.rolling(5).mean() / volumes.rolling(20).mean()
    vol_ratio_z = vol_ratio.sub(vol_ratio.mean(axis=1), axis=0).div(vol_ratio.std(axis=1), axis=0)
    strats['H-021'] = backtest_xs_factor(closes, vol_ratio_z, 3, 4, "long_high")

    # H-046 Acceleration
    mom = closes.pct_change(20)
    accel = mom - mom.shift(20)
    accel_z = accel.sub(accel.mean(axis=1), axis=0).div(accel.std(axis=1), axis=0)
    strats['H-046'] = backtest_xs_factor(closes, accel_z, 3, 4, "long_high")

    # H-047 (if params provided)
    if best_params_47:
        sw, lw, rd, n, d = best_params_47
        signals = compute_vol_change_signal(closes, sw, lw)
        strats['H-047'] = backtest_xs_factor(closes, signals, rd, n, d)

    # H-048 (if params provided)
    if best_params_48:
        cw, dw, rd, n, d = best_params_48
        signals = compute_corr_change_signal(closes, cw, dw)
        asset_closes = closes.drop(columns=['BTC'])
        strats['H-048'] = backtest_xs_factor(asset_closes, signals, rd, n, d)

    # Compute correlations
    df = pd.DataFrame(strats)
    corr = df.corr()

    print("\nCorrelation matrix:")
    print(corr.to_string(float_format='{:.3f}'.format))


def compute_momentum_signal(closes, lookback):
    """Simple momentum signal for correlation comparison."""
    mom = closes.pct_change(lookback)
    z = mom.sub(mom.mean(axis=1), axis=0).div(mom.std(axis=1), axis=0)
    return z


def load_daily_volumes():
    """Load daily volumes for all assets."""
    frames = {}
    for sym in ASSETS:
        df = fetch_and_cache(sym, "1h", limit_days=800)
        daily_vol = df['volume'].resample('1D').sum().dropna()
        frames[sym.replace('/USDT', '')] = daily_vol
    return pd.DataFrame(frames).dropna()


if __name__ == "__main__":
    df47 = run_h047_research()
    df48 = run_h048_research()

    # If either has promising results, compute correlations
    best47 = None
    best48 = None

    if len(df47[df47['sharpe'] > 0]) > 0:
        b = df47.nlargest(1, 'sharpe').iloc[0]
        best47 = (int(b['short_w']), int(b['long_w']), int(b['rebal']), int(b['n']), b['direction'])

    if len(df48[df48['sharpe'] > 0]) > 0:
        b = df48.nlargest(1, 'sharpe').iloc[0]
        best48 = (int(b['corr_w']), int(b['delta_w']), int(b['rebal']), int(b['n']), b['direction'])

    if best47 or best48:
        closes = load_daily_closes()
        compute_correlations(closes, best47, best48)
