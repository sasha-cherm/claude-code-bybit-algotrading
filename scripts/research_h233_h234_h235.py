"""
Research backtests for H-233, H-234, H-235.

H-233: Relative Volume Factor — ratio of short-term avg volume to long-term avg volume.
       Long high relative volume (interest surge), short low relative volume (neglected).

H-234: Consecutive Return Direction Factor — count of consecutive positive daily returns.
       Long assets with longest positive streaks (momentum), short longest negative streaks.

H-235: Funding Rate Change (Delta) Factor — change in avg funding rate (short - long window).
       Long assets with decreasing funding (de-crowding), short increasing (crowding).

Standard framework: 14 assets, ~730 daily bars (2yr), parameter grid, IS pass rate,
walk-forward validation, split-half stability, correlation with H-012.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001
SLIPPAGE_BPS = 2.0
TOTAL_COST = FEE_RATE + SLIPPAGE_BPS / 10_000


def fetch_all_daily():
    """Fetch and align daily data for all 14 assets."""
    closes = {}
    volumes = {}
    highs = {}
    lows = {}
    for sym in ASSETS:
        df = fetch_and_cache(sym, "1h")
        daily = resample_to_daily(df)
        name = sym.replace("/USDT", "")
        closes[name] = daily["close"]
        volumes[name] = daily["volume"]
        highs[name] = daily["high"]
        lows[name] = daily["low"]
    close_df = pd.DataFrame(closes).dropna()
    vol_df = pd.DataFrame(volumes).reindex(close_df.index).fillna(0)
    high_df = pd.DataFrame(highs).reindex(close_df.index)
    low_df = pd.DataFrame(lows).reindex(close_df.index)
    # Use last 730 bars (~2 years)
    close_df = close_df.iloc[-730:]
    vol_df = vol_df.iloc[-730:]
    high_df = high_df.reindex(close_df.index)
    low_df = low_df.reindex(close_df.index)
    return close_df, vol_df, high_df, low_df


def compute_returns(close_df):
    return close_df.pct_change().iloc[1:]


def run_xs_backtest(signal_df, returns_df, rebal_freq, n_long, n_short, direction="high_long"):
    """
    Generic cross-sectional backtest.
    signal_df: daily signal for each asset (higher = more of the factor)
    direction: 'high_long' = long highest signal, short lowest
               'low_long' = long lowest signal, short highest
    """
    dates = signal_df.index.intersection(returns_df.index)
    dates = sorted(dates)

    port_returns = []
    prev_longs = set()
    prev_shorts = set()
    rebal_counter = 0

    for i, dt in enumerate(dates):
        sig = signal_df.loc[dt].dropna()
        ret = returns_df.loc[dt].dropna()
        common = sig.index.intersection(ret.index)
        if len(common) < n_long + n_short:
            port_returns.append(0.0)
            continue

        sig_day = sig[common].sort_values(ascending=(direction == "low_long"))

        if rebal_counter == 0:
            # Rebalance
            longs = set(sig_day.index[:n_long])
            shorts = set(sig_day.index[-n_short:]) if direction == "high_long" else set(sig_day.index[-n_short:])

            if direction == "high_long":
                longs = set(sig_day.index[-n_long:])  # highest signal
                shorts = set(sig_day.index[:n_short])  # lowest signal
            else:
                longs = set(sig_day.index[:n_long])    # lowest signal
                shorts = set(sig_day.index[-n_short:])  # highest signal

            # Turnover cost
            new_trades = len(longs - prev_longs) + len(shorts - prev_shorts)
            turnover_cost = new_trades * TOTAL_COST / (n_long + n_short)
            prev_longs = longs
            prev_shorts = shorts
            rebal_counter = rebal_freq
        else:
            turnover_cost = 0.0

        rebal_counter -= 1

        # Equal-weight portfolio return
        long_ret = ret[list(prev_longs)].mean() if prev_longs else 0
        short_ret = ret[list(prev_shorts)].mean() if prev_shorts else 0
        day_ret = (long_ret - short_ret) / 2.0 - turnover_cost
        port_returns.append(day_ret)

    return pd.Series(port_returns, index=dates[:len(port_returns)])


def calc_metrics(returns_series):
    """Calculate Sharpe, annual return, max drawdown."""
    if len(returns_series) < 30:
        return {"sharpe": 0, "annual_return": 0, "max_dd": 0}
    mean_r = returns_series.mean()
    std_r = returns_series.std()
    sharpe = (mean_r / std_r) * np.sqrt(365) if std_r > 0 else 0
    annual_return = mean_r * 365
    cumulative = (1 + returns_series).cumprod()
    peak = cumulative.cummax()
    dd = (cumulative - peak) / peak
    max_dd = dd.min()
    return {"sharpe": round(sharpe, 3), "annual_return": round(annual_return * 100, 1),
            "max_dd": round(max_dd * 100, 1)}


def walk_forward(signal_func, returns_df, close_df, vol_df, params, n_folds=6, test_days=90):
    """Walk-forward validation."""
    total_days = len(returns_df)
    train_start = 0
    results = []

    for fold in range(n_folds):
        test_end = total_days - (n_folds - fold - 1) * test_days
        test_start = test_end - test_days
        if test_start < 100:
            continue

        # Train on everything before test
        train_ret = returns_df.iloc[:test_start]
        test_ret = returns_df.iloc[test_start:test_end]

        # Compute signal over full period (signal uses lookback from history)
        sig = signal_func(close_df, vol_df, **{k: v for k, v in params.items() if k not in ['rebal_freq', 'n_long', 'n_short', 'direction']})

        test_sig = sig.reindex(test_ret.index).dropna(how='all')
        if len(test_sig) < 30:
            continue

        test_returns = run_xs_backtest(
            test_sig, test_ret,
            params['rebal_freq'], params['n_long'], params['n_short'],
            params.get('direction', 'high_long')
        )

        if len(test_returns) > 0:
            m = calc_metrics(test_returns)
            results.append(m['sharpe'])

    return results


def compute_h012_returns(close_df, returns_df):
    """H-012 baseline: 60-day momentum, 5-day rebal, top/bottom 4."""
    mom = close_df.pct_change(60)
    sig = mom.shift(1)  # lagged
    return run_xs_backtest(sig, returns_df, 5, 4, 4, direction="high_long")


# =============================================================================
# H-233: Relative Volume Factor
# =============================================================================
def h233_signal(close_df, vol_df, short_window=5, long_window=30):
    """Relative volume = short-term avg volume / long-term avg volume."""
    short_avg = vol_df.rolling(short_window).mean()
    long_avg = vol_df.rolling(long_window).mean()
    rel_vol = short_avg / long_avg.replace(0, np.nan)
    return rel_vol


def test_h233(close_df, vol_df, returns_df):
    print("\n" + "=" * 70)
    print("H-233: Relative Volume (Abnormal Volume) Factor")
    print("=" * 70)

    # Parameter grid
    short_windows = [3, 5, 7, 10]
    long_windows = [20, 30, 40]
    rebal_freqs = [3, 5, 7]
    n_values = [3, 4]
    directions = ["high_long", "low_long"]

    results = []
    for sw in short_windows:
        for lw in long_windows:
            if sw >= lw:
                continue
            for r in rebal_freqs:
                for n in n_values:
                    for d in directions:
                        sig = h233_signal(close_df, vol_df, sw, lw)
                        sig = sig.shift(1)  # lag to avoid lookahead
                        ret = run_xs_backtest(sig, returns_df, r, n, n, direction=d)
                        m = calc_metrics(ret)
                        results.append({
                            "params": f"SW{sw}_LW{lw}_R{r}_N{n}_{d}",
                            "sharpe": m["sharpe"],
                            "annual_return": m["annual_return"],
                            "max_dd": m["max_dd"],
                            "direction": d,
                        })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    n_total = len(df)
    pct = n_positive / n_total * 100

    print(f"\nIS Results: {n_positive}/{n_total} positive ({pct:.1f}%)")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"Best: {df.loc[df['sharpe'].idxmax(), 'params']} Sharpe {df['sharpe'].max():.3f} "
          f"({df.loc[df['sharpe'].idxmax(), 'annual_return']:+.1f}% ann, {df.loc[df['sharpe'].idxmax(), 'max_dd']:.1f}% DD)")

    # Check dominant direction
    for d in directions:
        sub = df[df["direction"] == d]
        pos = (sub["sharpe"] > 0).sum()
        print(f"  {d}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.1f}%), mean Sharpe {sub['sharpe'].mean():.3f}")

    # If IS pass rate >= 80%, do walk-forward
    if pct >= 80:
        print("\n--- Walk-Forward Validation ---")
        best = df.loc[df["sharpe"].idxmax()]
        # Parse best params
        parts = best["params"].split("_")
        sw = int(parts[0][2:])
        lw = int(parts[1][2:])
        r = int(parts[2][1:])
        n = int(parts[3][1:])
        d = best["direction"]

        wf_results = walk_forward(
            lambda c, v, short_window, long_window: h233_signal(c, v, short_window, long_window).shift(1),
            returns_df, close_df, vol_df,
            {"short_window": sw, "long_window": lw, "rebal_freq": r, "n_long": n, "n_short": n, "direction": d}
        )

        wf_pos = sum(1 for s in wf_results if s > 0)
        print(f"WF: {wf_pos}/{len(wf_results)} folds positive, mean OOS Sharpe {np.mean(wf_results):.3f}")

        # Split-half
        half = len(returns_df) // 2
        h1_ret = run_xs_backtest(
            h233_signal(close_df, vol_df, sw, lw).shift(1),
            returns_df.iloc[:half], r, n, n, d)
        h2_ret = run_xs_backtest(
            h233_signal(close_df, vol_df, sw, lw).shift(1),
            returns_df.iloc[half:], r, n, n, d)
        h1_m = calc_metrics(h1_ret)
        h2_m = calc_metrics(h2_ret)
        print(f"Split-half: H1 Sharpe {h1_m['sharpe']:.3f}, H2 Sharpe {h2_m['sharpe']:.3f}")

        # Correlation with H-012
        h012_ret = compute_h012_returns(close_df, returns_df)
        best_ret = run_xs_backtest(
            h233_signal(close_df, vol_df, sw, lw).shift(1),
            returns_df, r, n, n, d)
        common = h012_ret.index.intersection(best_ret.index)
        corr = h012_ret[common].corr(best_ret[common])
        print(f"Correlation with H-012: {corr:.3f}")
    else:
        # Check dominant direction pass rate
        for d in directions:
            sub = df[df["direction"] == d]
            pos_pct = (sub["sharpe"] > 0).sum() / len(sub) * 100
            if pos_pct >= 80:
                print(f"\n--- {d} passes 80% threshold, running WF ---")
                best = sub.loc[sub["sharpe"].idxmax()]
                parts = best["params"].split("_")
                sw = int(parts[0][2:])
                lw = int(parts[1][2:])
                r = int(parts[2][1:])
                n = int(parts[3][1:])

                wf_results = walk_forward(
                    lambda c, v, short_window, long_window: h233_signal(c, v, short_window, long_window).shift(1),
                    returns_df, close_df, vol_df,
                    {"short_window": sw, "long_window": lw, "rebal_freq": r, "n_long": n, "n_short": n, "direction": d}
                )
                wf_pos = sum(1 for s in wf_results if s > 0)
                print(f"WF: {wf_pos}/{len(wf_results)} folds positive, mean OOS Sharpe {np.mean(wf_results):.3f}")

                h012_ret = compute_h012_returns(close_df, returns_df)
                best_ret = run_xs_backtest(
                    h233_signal(close_df, vol_df, sw, lw).shift(1),
                    returns_df, r, n, n, d)
                common = h012_ret.index.intersection(best_ret.index)
                corr = h012_ret[common].corr(best_ret[common])
                print(f"Correlation with H-012: {corr:.3f}")

    return df


# =============================================================================
# H-234: Consecutive Return Direction Factor
# =============================================================================
def h234_signal(close_df, vol_df, lookback=10):
    """
    Count net positive days over lookback window.
    Positive value = more up days than down days.
    """
    rets = close_df.pct_change()
    # Count positive days in rolling window
    pos_days = (rets > 0).astype(float).rolling(lookback).sum()
    # Net direction: pos_days / lookback gives win rate
    win_rate = pos_days / lookback
    return win_rate


def test_h234(close_df, vol_df, returns_df):
    print("\n" + "=" * 70)
    print("H-234: Consecutive Return Direction / Win Rate Factor")
    print("=" * 70)

    lookbacks = [5, 7, 10, 15, 20]
    rebal_freqs = [3, 5, 7]
    n_values = [3, 4]
    directions = ["high_long", "low_long"]

    results = []
    for lb in lookbacks:
        for r in rebal_freqs:
            for n in n_values:
                for d in directions:
                    sig = h234_signal(close_df, vol_df, lb)
                    sig = sig.shift(1)
                    ret = run_xs_backtest(sig, returns_df, r, n, n, direction=d)
                    m = calc_metrics(ret)
                    results.append({
                        "params": f"LB{lb}_R{r}_N{n}_{d}",
                        "sharpe": m["sharpe"],
                        "annual_return": m["annual_return"],
                        "max_dd": m["max_dd"],
                        "direction": d,
                    })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    n_total = len(df)
    pct = n_positive / n_total * 100

    print(f"\nIS Results: {n_positive}/{n_total} positive ({pct:.1f}%)")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"Best: {df.loc[df['sharpe'].idxmax(), 'params']} Sharpe {df['sharpe'].max():.3f} "
          f"({df.loc[df['sharpe'].idxmax(), 'annual_return']:+.1f}% ann, {df.loc[df['sharpe'].idxmax(), 'max_dd']:.1f}% DD)")

    for d in directions:
        sub = df[df["direction"] == d]
        pos = (sub["sharpe"] > 0).sum()
        print(f"  {d}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.1f}%), mean Sharpe {sub['sharpe'].mean():.3f}")

    # Note: H-234 is very similar to H-223 (momentum breadth / win rate)
    # Check how different it is
    print("\n  Note: H-234 (win rate over lookback) is conceptually similar to H-223 (momentum breadth).")
    print("  If both pass, check correlation carefully.")

    if pct >= 80:
        print("\n--- Walk-Forward Validation ---")
        best = df.loc[df["sharpe"].idxmax()]
        parts = best["params"].split("_")
        lb = int(parts[0][2:])
        r = int(parts[1][1:])
        n = int(parts[2][1:])
        d = best["direction"]

        wf_results = walk_forward(
            lambda c, v, lookback: h234_signal(c, v, lookback).shift(1),
            returns_df, close_df, vol_df,
            {"lookback": lb, "rebal_freq": r, "n_long": n, "n_short": n, "direction": d}
        )
        wf_pos = sum(1 for s in wf_results if s > 0)
        print(f"WF: {wf_pos}/{len(wf_results)} folds positive, mean OOS Sharpe {np.mean(wf_results):.3f}")

        half = len(returns_df) // 2
        h1_ret = run_xs_backtest(
            h234_signal(close_df, vol_df, lb).shift(1),
            returns_df.iloc[:half], r, n, n, d)
        h2_ret = run_xs_backtest(
            h234_signal(close_df, vol_df, lb).shift(1),
            returns_df.iloc[half:], r, n, n, d)
        h1_m = calc_metrics(h1_ret)
        h2_m = calc_metrics(h2_ret)
        print(f"Split-half: H1 Sharpe {h1_m['sharpe']:.3f}, H2 Sharpe {h2_m['sharpe']:.3f}")

        h012_ret = compute_h012_returns(close_df, returns_df)
        best_ret = run_xs_backtest(
            h234_signal(close_df, vol_df, lb).shift(1),
            returns_df, r, n, n, d)
        common = h012_ret.index.intersection(best_ret.index)
        corr = h012_ret[common].corr(best_ret[common])
        print(f"Correlation with H-012: {corr:.3f}")

        # Also check correlation with H-223 (win rate factor)
        h223_sig = h234_signal(close_df, vol_df, 20).shift(1)  # H-223 uses LB20
        h223_ret = run_xs_backtest(h223_sig, returns_df, 5, 3, 3, "high_long")
        common2 = best_ret.index.intersection(h223_ret.index)
        corr_h223 = best_ret[common2].corr(h223_ret[common2])
        print(f"Correlation with H-223: {corr_h223:.3f}")
    else:
        for d in directions:
            sub = df[df["direction"] == d]
            pos_pct = (sub["sharpe"] > 0).sum() / len(sub) * 100
            if pos_pct >= 80:
                print(f"\n--- {d} passes 80% threshold, running WF ---")
                best = sub.loc[sub["sharpe"].idxmax()]
                parts = best["params"].split("_")
                lb = int(parts[0][2:])
                r = int(parts[1][1:])
                n = int(parts[2][1:])

                wf_results = walk_forward(
                    lambda c, v, lookback: h234_signal(c, v, lookback).shift(1),
                    returns_df, close_df, vol_df,
                    {"lookback": lb, "rebal_freq": r, "n_long": n, "n_short": n, "direction": d}
                )
                wf_pos = sum(1 for s in wf_results if s > 0)
                print(f"WF: {wf_pos}/{len(wf_results)} folds positive, mean OOS Sharpe {np.mean(wf_results):.3f}")

                h012_ret = compute_h012_returns(close_df, returns_df)
                best_ret = run_xs_backtest(
                    h234_signal(close_df, vol_df, lb).shift(1),
                    returns_df, r, n, n, d)
                common = h012_ret.index.intersection(best_ret.index)
                corr = h012_ret[common].corr(best_ret[common])
                print(f"Correlation with H-012: {corr:.3f}")

    return df


# =============================================================================
# H-235: Funding Rate Change / Delta Factor
# =============================================================================
def fetch_funding_data():
    """Fetch funding rate data for all assets."""
    funding_dfs = {}
    for sym in ASSETS:
        name = sym.replace("/USDT", "")
        bybit_sym = sym.replace("/", "")
        try:
            # Try to load cached funding data
            cache_path = ROOT / "data" / f"funding_{bybit_sym}.parquet"
            if cache_path.exists():
                df = pd.read_parquet(cache_path)
                if len(df) > 100:
                    funding_dfs[name] = df
                    continue

            # Fetch from Bybit API
            from pybit.unified_trading import HTTP
            from dotenv import load_dotenv
            import os
            load_dotenv()

            session = HTTP(testnet=False)
            all_data = []
            end_time = None

            for _ in range(10):  # Up to 10 pages
                params = {"category": "linear", "symbol": bybit_sym, "limit": 200}
                if end_time:
                    params["endTime"] = end_time
                r = session.get_funding_rate_history(**params)
                rows = r["result"]["list"]
                if not rows:
                    break
                for row in rows:
                    all_data.append({
                        "timestamp": pd.Timestamp(int(row["fundingRateTimestamp"]), unit="ms", tz="UTC"),
                        "funding_rate": float(row["fundingRate"]),
                    })
                end_time = int(rows[-1]["fundingRateTimestamp"]) - 1

            if all_data:
                df = pd.DataFrame(all_data).sort_values("timestamp").set_index("timestamp")
                df.to_parquet(cache_path)
                funding_dfs[name] = df
        except Exception as e:
            print(f"  Warning: could not load funding for {name}: {e}")

    return funding_dfs


def h235_signal_from_funding(funding_dfs, close_df, short_window=3, long_window=14):
    """
    Funding rate change = short-window avg funding - long-window avg funding.
    Positive delta = funding increasing (more crowded longs) → short signal.
    Negative delta = funding decreasing (de-crowding) → long signal (contrarian).
    """
    # Resample funding to daily (sum of 3x daily settlements)
    daily_funding = {}
    for name, fdf in funding_dfs.items():
        daily = fdf["funding_rate"].resample("1D").sum()
        daily_funding[name] = daily

    funding_df = pd.DataFrame(daily_funding).reindex(close_df.index).ffill()

    short_avg = funding_df.rolling(short_window).mean()
    long_avg = funding_df.rolling(long_window).mean()
    delta = short_avg - long_avg  # positive = funding increasing

    return delta


def test_h235(close_df, vol_df, returns_df):
    print("\n" + "=" * 70)
    print("H-235: Funding Rate Change / Delta Factor")
    print("=" * 70)

    print("Fetching funding rate data...")
    funding_dfs = fetch_funding_data()
    print(f"Loaded funding data for {len(funding_dfs)} assets")

    if len(funding_dfs) < 10:
        print("SKIP: insufficient funding data")
        return None

    short_windows = [3, 5, 7]
    long_windows = [14, 21, 30]
    rebal_freqs = [5, 7]
    n_values = [3, 4]
    # Contrarian: long where funding is DECREASING (negative delta)
    # i.e., low_long on the delta signal
    directions = ["high_long", "low_long"]

    results = []
    for sw in short_windows:
        for lw in long_windows:
            if sw >= lw:
                continue
            for r in rebal_freqs:
                for n in n_values:
                    for d in directions:
                        sig = h235_signal_from_funding(funding_dfs, close_df, sw, lw)
                        sig = sig.shift(1)
                        # Align with returns
                        common_idx = sig.index.intersection(returns_df.index)
                        sig_aligned = sig.loc[common_idx]
                        ret_aligned = returns_df.loc[common_idx]

                        ret = run_xs_backtest(sig_aligned, ret_aligned, r, n, n, direction=d)
                        m = calc_metrics(ret)
                        results.append({
                            "params": f"SW{sw}_LW{lw}_R{r}_N{n}_{d}",
                            "sharpe": m["sharpe"],
                            "annual_return": m["annual_return"],
                            "max_dd": m["max_dd"],
                            "direction": d,
                        })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    n_total = len(df)
    pct = n_positive / n_total * 100

    print(f"\nIS Results: {n_positive}/{n_total} positive ({pct:.1f}%)")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")
    if len(df) > 0:
        print(f"Best: {df.loc[df['sharpe'].idxmax(), 'params']} Sharpe {df['sharpe'].max():.3f} "
              f"({df.loc[df['sharpe'].idxmax(), 'annual_return']:+.1f}% ann, {df.loc[df['sharpe'].idxmax(), 'max_dd']:.1f}% DD)")

    for d in directions:
        sub = df[df["direction"] == d]
        pos = (sub["sharpe"] > 0).sum()
        print(f"  {d}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.1f}%), mean Sharpe {sub['sharpe'].mean():.3f}")

    if pct >= 80:
        print("\n--- Walk-Forward Validation ---")
        best = df.loc[df["sharpe"].idxmax()]
        parts = best["params"].split("_")
        sw = int(parts[0][2:])
        lw = int(parts[1][2:])
        r = int(parts[2][1:])
        n = int(parts[3][1:])
        d = best["direction"]

        sig = h235_signal_from_funding(funding_dfs, close_df, sw, lw).shift(1)

        # Walk-forward manually
        total_days = len(returns_df)
        wf_results = []
        n_folds = 6
        test_days = 90
        for fold in range(n_folds):
            test_end = total_days - (n_folds - fold - 1) * test_days
            test_start = test_end - test_days
            if test_start < 100:
                continue
            test_ret = returns_df.iloc[test_start:test_end]
            test_sig = sig.reindex(test_ret.index).dropna(how='all')
            if len(test_sig) < 30:
                continue
            fold_ret = run_xs_backtest(test_sig, test_ret, r, n, n, d)
            if len(fold_ret) > 0:
                m = calc_metrics(fold_ret)
                wf_results.append(m['sharpe'])

        wf_pos = sum(1 for s in wf_results if s > 0)
        print(f"WF: {wf_pos}/{len(wf_results)} folds positive, mean OOS Sharpe {np.mean(wf_results):.3f}")

        half = len(returns_df) // 2
        h1_ret = run_xs_backtest(sig, returns_df.iloc[:half], r, n, n, d)
        h2_ret = run_xs_backtest(sig, returns_df.iloc[half:], r, n, n, d)
        h1_m = calc_metrics(h1_ret)
        h2_m = calc_metrics(h2_ret)
        print(f"Split-half: H1 Sharpe {h1_m['sharpe']:.3f}, H2 Sharpe {h2_m['sharpe']:.3f}")

        h012_ret = compute_h012_returns(close_df, returns_df)
        best_ret = run_xs_backtest(sig, returns_df, r, n, n, d)
        common = h012_ret.index.intersection(best_ret.index)
        corr = h012_ret[common].corr(best_ret[common])
        print(f"Correlation with H-012: {corr:.3f}")
    else:
        for d in directions:
            sub = df[df["direction"] == d]
            pos_pct = (sub["sharpe"] > 0).sum() / len(sub) * 100
            if pos_pct >= 80:
                print(f"\n--- {d} passes 80% threshold, running WF ---")
                best = sub.loc[sub["sharpe"].idxmax()]
                parts = best["params"].split("_")
                sw = int(parts[0][2:])
                lw = int(parts[1][2:])
                r = int(parts[2][1:])
                n = int(parts[3][1:])

                sig = h235_signal_from_funding(funding_dfs, close_df, sw, lw).shift(1)

                total_days = len(returns_df)
                wf_results = []
                n_folds = 6
                test_days = 90
                for fold in range(n_folds):
                    test_end = total_days - (n_folds - fold - 1) * test_days
                    test_start = test_end - test_days
                    if test_start < 100:
                        continue
                    test_ret = returns_df.iloc[test_start:test_end]
                    test_sig = sig.reindex(test_ret.index).dropna(how='all')
                    if len(test_sig) < 30:
                        continue
                    fold_ret = run_xs_backtest(test_sig, test_ret, r, n, n, d)
                    if len(fold_ret) > 0:
                        m = calc_metrics(fold_ret)
                        wf_results.append(m['sharpe'])

                wf_pos = sum(1 for s in wf_results if s > 0)
                print(f"WF: {wf_pos}/{len(wf_results)} folds positive, mean OOS Sharpe {np.mean(wf_results):.3f}")

                h012_ret = compute_h012_returns(close_df, returns_df)
                best_ret = run_xs_backtest(sig, returns_df, r, n, n, d)
                common = h012_ret.index.intersection(best_ret.index)
                corr = h012_ret[common].corr(best_ret[common])
                print(f"Correlation with H-012: {corr:.3f}")

    return df


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    print("Fetching daily data for 14 assets...")
    close_df, vol_df, high_df, low_df = fetch_all_daily()
    returns_df = compute_returns(close_df)
    print(f"Data: {len(close_df)} days, {len(close_df.columns)} assets")
    print(f"Period: {close_df.index[0].date()} to {close_df.index[-1].date()}")

    r233 = test_h233(close_df, vol_df, returns_df)
    r234 = test_h234(close_df, vol_df, returns_df)
    r235 = test_h235(close_df, vol_df, returns_df)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, df in [("H-233", r233), ("H-234", r234), ("H-235", r235)]:
        if df is None:
            print(f"{name}: SKIPPED (insufficient data)")
            continue
        n_pos = (df["sharpe"] > 0).sum()
        n_tot = len(df)
        pct = n_pos / n_tot * 100
        print(f"{name}: {n_pos}/{n_tot} positive ({pct:.1f}%), "
              f"mean Sharpe {df['sharpe'].mean():.3f}, "
              f"best Sharpe {df['sharpe'].max():.3f}")
