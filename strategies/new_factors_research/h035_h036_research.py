"""
H-035: Momentum with Volatility Timing
H-036: Intraday Hour-of-Day Seasonality (BTC)

Quick research — session 2026-03-19.

H-035: Scale H-012 momentum exposure based on recent portfolio volatility.
When realized vol is high, reduce exposure (avoid momentum crashes).
When vol is low, increase exposure (lean into calm trending environments).

H-036: Test if BTC returns vary systematically by hour of day.
If so, could trade "buy the Asian session, sell the US session" or similar.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

BASE_FEE = 0.001
SLIPPAGE_BPS = 2.0
INITIAL_CAPITAL = 10_000.0


def resample_to_daily(df):
    daily = df.resample("1D").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()
    return daily


def load_all_data():
    hourly = {}
    daily = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df) < 200:
                continue
            hourly[sym] = df
            daily[sym] = resample_to_daily(df)
        except Exception as e:
            print(f"  {sym}: failed: {e}")
    return hourly, daily


def compute_metrics(equity_series):
    eq = equity_series[equity_series > 0]
    if len(eq) < 50:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0}
    rets = eq.pct_change().dropna()
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 2),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
    }


def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  fee_multiplier=1.0, warmup=65, vol_scale=None, vol_window=None):
    """
    vol_scale: if provided, scale exposure by target_vol / realized_vol.
    vol_window: lookback for realized vol computation.
    """
    if n_short is None:
        n_short = n_long

    n = len(closes)
    slippage = SLIPPAGE_BPS / 10_000
    fee_rate = BASE_FEE * fee_multiplier

    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    prev_weights = pd.Series(0.0, index=closes.columns)
    trades = 0

    # Precompute portfolio returns for vol scaling
    if vol_scale is not None and vol_window is not None:
        # First pass: get base portfolio returns for vol estimation
        base_equity = np.zeros(n)
        base_equity[0] = capital
        base_prev_w = pd.Series(0.0, index=closes.columns)
        for i in range(1, n):
            pt = closes.iloc[i]
            py = closes.iloc[i - 1]
            if i >= warmup and (i - warmup) % rebal_freq == 0:
                ranks = ranking_series.iloc[i - 1]
                valid = ranks.dropna()
                if len(valid) < n_long + n_short:
                    base_equity[i] = base_equity[i - 1]
                    continue
                ranked = valid.sort_values(ascending=False)
                nw = pd.Series(0.0, index=closes.columns)
                for sym in ranked.index[:n_long]:
                    nw[sym] = 1.0 / n_long
                for sym in ranked.index[-n_short:]:
                    nw[sym] = -1.0 / n_short
                dr = (pt / py - 1)
                base_equity[i] = base_equity[i - 1] * (1 + (nw * dr).sum())
                base_prev_w = nw
            else:
                dr = (pt / py - 1)
                base_equity[i] = base_equity[i - 1] * (1 + (base_prev_w * dr).sum())

        base_rets = pd.Series(base_equity).pct_change()

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

            # Vol scaling
            if vol_scale is not None and vol_window is not None and i >= vol_window + warmup:
                recent_vol = base_rets.iloc[i - vol_window:i].std() * np.sqrt(365)
                if recent_vol > 0.01:
                    scale = min(vol_scale / recent_vol, 2.0)  # cap at 2x
                    new_weights *= scale

            weight_changes = (new_weights - prev_weights).abs()
            trades += int((weight_changes > 0.01).sum())
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
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = trades
    metrics["equity"] = eq_series
    return metrics


# ═══════════════════════════════════════════════════════════════════════
# H-035: Momentum with Volatility Timing
# ═══════════════════════════════════════════════════════════════════════

def h035_momentum_vol_timing(daily_data):
    print("\n" + "=" * 70)
    print("H-035: MOMENTUM WITH VOLATILITY TIMING")
    print("=" * 70)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    # Base H-012 ranking (60d momentum)
    ranking = closes.pct_change(60)

    # First: run base H-012 for comparison
    base = run_xs_factor(closes, ranking, 5, 4, warmup=65)
    print(f"\n  Base H-012: Sharpe {base['sharpe']:.2f}, "
          f"Ann {base['annual_ret']:.1%}, DD {base['max_dd']:.1%}")

    results = []
    for vol_target in [0.3, 0.5, 0.7, 1.0]:
        for vol_window in [10, 20, 30, 60]:
            for rebal_freq in [3, 5, 7]:
                for n_long in [3, 4, 5]:
                    res = run_xs_factor(
                        closes, ranking, rebal_freq, n_long,
                        warmup=65, vol_scale=vol_target, vol_window=vol_window,
                    )
                    tag = f"VT{vol_target}_VW{vol_window}_R{rebal_freq}_N{n_long}"
                    results.append({
                        "tag": tag, "vol_target": vol_target,
                        "vol_window": vol_window, "rebal": rebal_freq,
                        "n_long": n_long,
                        **{k: v for k, v in res.items() if k != "equity"},
                    })
                    if res["sharpe"] > 1.2:
                        print(f"  ** {tag}: Sharpe {res['sharpe']:.2f}, "
                              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    beats_base = df[df["sharpe"] > base["sharpe"]]
    print(f"\n  Total params: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Beats base H-012 ({base['sharpe']:.2f}): {len(beats_base)}/{len(df)} "
          f"({len(beats_base)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.2f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}")

    # Walk-forward for best if it beats base
    best = df.nlargest(1, "sharpe").iloc[0]
    if best["sharpe"] > base["sharpe"]:
        print(f"\n  Walk-forward for {best['tag']}...")
        vt = best["vol_target"]
        vw = int(best["vol_window"])
        rebal = int(best["rebal"])
        nl = int(best["n_long"])

        n_folds = 6
        test_days = 80
        train_days = 360
        n = len(closes)
        fold_results = []

        for fold in range(n_folds):
            test_end = n - fold * test_days
            test_start = test_end - test_days
            if test_start - train_days < 0:
                break

            tc = closes.iloc[test_start:test_end]
            tr = ranking.iloc[test_start:test_end]
            res = run_xs_factor(tc, tr, rebal, nl, warmup=5,
                                vol_scale=vt, vol_window=vw)
            fold_results.append({"fold": fold + 1, "sharpe": res["sharpe"]})
            print(f"    Fold {fold+1}: Sharpe {res['sharpe']:.2f}")

        if fold_results:
            wf_df = pd.DataFrame(fold_results)
            pos = (wf_df["sharpe"] > 0).sum()
            print(f"    WF: {pos}/{len(wf_df)} positive, mean {wf_df['sharpe'].mean():.2f}")

    return df


# ═══════════════════════════════════════════════════════════════════════
# H-036: Intraday Hour-of-Day Seasonality
# ═══════════════════════════════════════════════════════════════════════

def h036_intraday_seasonality(hourly_data):
    print("\n" + "=" * 70)
    print("H-036: INTRADAY HOUR-OF-DAY SEASONALITY (BTC)")
    print("=" * 70)

    btc_hourly = hourly_data.get("BTC/USDT")
    if btc_hourly is None:
        print("  No BTC hourly data.")
        return None

    btc = btc_hourly.copy()
    btc["return"] = btc["close"].pct_change()
    btc["hour"] = btc.index.hour
    print(f"  BTC hourly data: {len(btc)} bars")

    # Analyze returns by hour
    print("\n  Average return by hour (UTC):")
    hourly_stats = btc.groupby("hour")["return"].agg(["mean", "std", "count"])
    hourly_stats["sharpe"] = hourly_stats["mean"] / hourly_stats["std"] * np.sqrt(365 * 24)
    hourly_stats["ann_ret"] = hourly_stats["mean"] * 365 * 24
    for h in range(24):
        if h in hourly_stats.index:
            s = hourly_stats.loc[h]
            marker = " ***" if abs(s["sharpe"]) > 0.5 else ""
            print(f"    {h:02d}:00  mean={s['mean']:.6f}  Sharpe={s['sharpe']:.2f}  "
                  f"ann={s['ann_ret']:.1%}  n={int(s['count'])}{marker}")

    # Test: split into train/test and see if patterns persist
    n = len(btc)
    split = n // 2
    train = btc.iloc[:split]
    test = btc.iloc[split:]

    train_stats = train.groupby("hour")["return"].mean()
    test_stats = test.groupby("hour")["return"].mean()

    # Correlation of hour-of-day returns between halves
    common_hours = train_stats.index.intersection(test_stats.index)
    if len(common_hours) > 10:
        corr = train_stats.loc[common_hours].corr(test_stats.loc[common_hours])
        print(f"\n  Train/Test correlation of hourly returns: {corr:.3f}")
        print(f"  (>0.3 would suggest persistent seasonality)")

    # Strategy: long during best N hours, flat during worst N hours
    print("\n  Testing hour-based strategy:")
    results = []
    for n_best in [4, 6, 8, 10, 12]:
        # Use expanding window to determine best hours (no lookahead)
        equity = np.zeros(n)
        equity[0] = INITIAL_CAPITAL
        min_history = 24 * 30  # Need at least 30 days of hourly data

        for i in range(1, n):
            if i >= min_history:
                # Compute best hours from history
                hist = btc.iloc[:i]
                hour_means = hist.groupby("hour")["return"].mean()
                best_hours = hour_means.nlargest(n_best).index.tolist()

                current_hour = btc.iloc[i]["hour"]
                if current_hour in best_hours:
                    equity[i] = equity[i - 1] * (1 + btc.iloc[i]["return"])
                else:
                    equity[i] = equity[i - 1]
            else:
                equity[i] = equity[i - 1]

        eq_s = pd.Series(equity, index=btc.index)
        metrics = compute_metrics(eq_s)
        tag = f"BEST{n_best}"
        results.append({"tag": tag, "n_best": n_best, **{k:v for k,v in metrics.items()}})
        print(f"    {tag}: Sharpe {metrics['sharpe']:.2f}, "
              f"Ann {metrics['annual_ret']:.1%}, DD {metrics['max_dd']:.1%}")

    # Also test: long during best hours, SHORT during worst hours
    for n_best in [4, 6, 8]:
        equity = np.zeros(n)
        equity[0] = INITIAL_CAPITAL
        min_history = 24 * 30

        for i in range(1, n):
            if i >= min_history:
                hist = btc.iloc[:i]
                hour_means = hist.groupby("hour")["return"].mean()
                best_hours = hour_means.nlargest(n_best).index.tolist()
                worst_hours = hour_means.nsmallest(n_best).index.tolist()

                current_hour = btc.iloc[i]["hour"]
                ret = btc.iloc[i]["return"]
                if pd.isna(ret):
                    ret = 0
                if current_hour in best_hours:
                    equity[i] = equity[i - 1] * (1 + ret)
                elif current_hour in worst_hours:
                    equity[i] = equity[i - 1] * (1 - ret)  # short
                else:
                    equity[i] = equity[i - 1]
            else:
                equity[i] = equity[i - 1]

        eq_s = pd.Series(equity, index=btc.index)
        metrics = compute_metrics(eq_s)
        tag = f"LS{n_best}"
        results.append({"tag": tag, "n_best": n_best, **{k:v for k,v in metrics.items()}})
        print(f"    {tag}: Sharpe {metrics['sharpe']:.2f}, "
              f"Ann {metrics['annual_ret']:.1%}, DD {metrics['max_dd']:.1%}")

    df = pd.DataFrame(results)
    print(f"\n  Best overall: {df.loc[df['sharpe'].idxmax(), 'tag']} "
          f"Sharpe {df['sharpe'].max():.2f}")

    # Cross-asset seasonality: do all assets share same hour patterns?
    print("\n  Cross-asset hour pattern correlation:")
    hour_patterns = {}
    for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT"]:
        if sym in hourly_data:
            h = hourly_data[sym].copy()
            h["return"] = h["close"].pct_change()
            h["hour"] = h.index.hour
            hour_patterns[sym] = h.groupby("hour")["return"].mean()

    if len(hour_patterns) >= 3:
        hp_df = pd.DataFrame(hour_patterns)
        corr_matrix = hp_df.corr()
        print(f"    Mean pairwise correlation of hourly patterns: "
              f"{corr_matrix.values[np.triu_indices_from(corr_matrix, k=1)].mean():.3f}")
        print(f"    BTC ↔ ETH: {corr_matrix.loc['BTC/USDT', 'ETH/USDT']:.3f}")

    return df


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Loading data...")
    hourly, daily = load_all_data()
    print(f"Loaded {len(daily)} assets\n")

    # H-035
    print("█" * 70)
    print("H-035: MOMENTUM WITH VOLATILITY TIMING")
    print("█" * 70)
    h035_results = h035_momentum_vol_timing(daily)

    # H-036
    print("\n" + "█" * 70)
    print("H-036: INTRADAY HOUR-OF-DAY SEASONALITY")
    print("█" * 70)
    h036_results = h036_intraday_seasonality(hourly)

    # Summary
    print("\n" + "█" * 70)
    print("SESSION SUMMARY")
    print("█" * 70)

    for name, df in [("H-035 MomVolTime", h035_results),
                     ("H-036 HourSeason", h036_results)]:
        if df is not None and len(df) > 0:
            pos_pct = (df["sharpe"] > 0).mean()
            print(f"\n  {name}:")
            print(f"    Params tested: {len(df)}")
            print(f"    Positive Sharpe: {pos_pct:.0%}")
            print(f"    Best Sharpe: {df['sharpe'].max():.2f}")
        else:
            print(f"\n  {name}: No results")

    print("\nDone.")
