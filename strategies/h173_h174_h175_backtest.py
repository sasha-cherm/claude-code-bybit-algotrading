#!/usr/bin/env python3
"""
H-173: Garman-Klass Volatility Ratio Factor
H-174: Downside Beta Factor
H-175: Net Money Flow Factor

Three new cross-sectional factor backtests using standard 4/4 validation.
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


def load_daily_ohlcv():
    """Load daily OHLCV for all assets."""
    daily_data = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=800)
            if len(df) < 200:
                continue
            daily = resample_to_daily(df)
            daily_data[sym] = daily
        except Exception:
            pass
    # Build aligned close, open, high, low, volume DataFrames
    closes = pd.DataFrame({s: d["close"] for s, d in daily_data.items()}).dropna(how="all").ffill().dropna()
    opens = pd.DataFrame({s: d["open"] for s, d in daily_data.items()}).reindex(closes.index).ffill().dropna()
    highs = pd.DataFrame({s: d["high"] for s, d in daily_data.items()}).reindex(closes.index).ffill().dropna()
    lows = pd.DataFrame({s: d["low"] for s, d in daily_data.items()}).reindex(closes.index).ffill().dropna()
    volumes = pd.DataFrame({s: d["volume"] for s, d in daily_data.items()}).reindex(closes.index).ffill().dropna()
    common = closes.index
    for df in [opens, highs, lows, volumes]:
        common = common.intersection(df.index)
    return closes.loc[common], opens.loc[common], highs.loc[common], lows.loc[common], volumes.loc[common]


def evaluate(rets, label=""):
    if rets is None or len(rets) < 30:
        return None
    ann = rets.mean() * 365
    vol = rets.std() * np.sqrt(365)
    sharpe = ann / vol if vol > 1e-8 else 0
    cum = (1 + rets).cumprod()
    dd = (cum / cum.cummax() - 1).min()
    return {"label": label, "sharpe": round(sharpe, 3), "annual": round(ann * 100, 1),
            "dd": round(dd * 100, 1), "days": len(rets)}


def backtest_momentum(closes, lookback=60, rebal_freq=5, n=4):
    """Reference H-012 momentum for correlation."""
    returns = closes.pct_change().dropna()
    dates = returns.index
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_returns.append({"date": dates[i], "return": day_ret})
        if i - last_rebal >= rebal_freq:
            mom = closes.iloc[i-1] / closes.iloc[i-1-lookback] - 1
            ranked = mom.sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_returns:
        return None
    df = pd.DataFrame(portfolio_returns).set_index("date")
    return df["return"]


def backtest_h076(closes, lookback=40, rebal_freq=5, n=4):
    """Reference H-076 efficiency for correlation."""
    returns = closes.pct_change().dropna()
    dates = returns.index
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_returns.append({"date": dates[i], "return": day_ret})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                window = closes[sym].iloc[i-lookback:i]
                r = window.pct_change().dropna()
                if len(r) < lookback - 2:
                    continue
                net = window.iloc[-1] / window.iloc[0] - 1
                path = r.abs().sum()
                if path < 1e-8:
                    continue
                signals[sym] = abs(net) / path
            if len(signals) >= 2 * n:
                ranked = pd.Series(signals).sort_values(ascending=False)
                weights = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:n]:
                    weights[s] = 1.0 / n
                for s in ranked.index[-n:]:
                    weights[s] = -1.0 / n
                last_rebal = i
    if not portfolio_returns:
        return None
    df = pd.DataFrame(portfolio_returns).set_index("date")
    return df["return"]


def backtest_h160(closes, eff_lb=20, vol_lb=20, rebal_freq=3, n=3):
    """Reference H-160 trend quality for correlation."""
    returns = closes.pct_change().dropna()
    dates = returns.index
    warmup = max(eff_lb, vol_lb) + 2
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_returns.append({"date": dates[i], "return": day_ret})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                eff_w = closes[sym].iloc[i-eff_lb:i]
                vol_w = closes[sym].iloc[i-vol_lb:i]
                daily_r = eff_w.pct_change().dropna()
                if len(daily_r) == 0:
                    continue
                net_r = eff_w.iloc[-1] / eff_w.iloc[0] - 1
                sum_abs = daily_r.abs().sum()
                if sum_abs < 1e-8:
                    continue
                eff = abs(net_r) / sum_abs
                vol_r = vol_w.pct_change().dropna()
                rvol = vol_r.std()
                if rvol < 1e-8:
                    continue
                direction = 1.0 if net_r > 0 else -1.0
                signals[sym] = eff * (1.0 / rvol) * direction
            if len(signals) >= 2 * n:
                ranked = pd.Series(signals).sort_values(ascending=False)
                weights = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:n]:
                    weights[s] = 1.0 / n
                for s in ranked.index[-n:]:
                    weights[s] = -1.0 / n
                last_rebal = i
    if not portfolio_returns:
        return None
    df = pd.DataFrame(portfolio_returns).set_index("date")
    return df["return"]


# ── H-173: Garman-Klass Volatility Ratio Factor ──
# Garman-Klass vol uses OHLC data: GK = 0.5*ln(H/L)^2 - (2ln2-1)*ln(C/O)^2
# Compare GK vol to close-to-close vol. High ratio = intraday noise dominates.
# Long assets with low ratio (clean trends), short assets with high ratio (noisy).
# Different from H-019 (vol level) because this measures vol *structure*, not level.

def backtest_h173(closes, opens, highs, lows, lookback, rebal_freq, n_long, n_short, direction="low_ratio_long"):
    returns = closes.pct_change().dropna()
    dates = returns.index
    warmup = lookback + 10
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_returns.append({"date": dates[i], "return": day_ret})

        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                c = closes[sym].iloc[i-lookback:i]
                o = opens[sym].iloc[i-lookback:i]
                h = highs[sym].iloc[i-lookback:i]
                l = lows[sym].iloc[i-lookback:i]

                if len(c) < lookback:
                    continue

                # Close-to-close vol
                cc_rets = c.pct_change().dropna()
                cc_vol = cc_rets.std()
                if cc_vol < 1e-8:
                    continue

                # Garman-Klass vol
                hl = np.log(h.values / l.values)
                co = np.log(c.values / o.values)
                gk_var = (0.5 * hl**2 - (2 * np.log(2) - 1) * co**2).mean()
                if gk_var <= 0:
                    continue
                gk_vol = np.sqrt(gk_var)

                # Ratio: GK / CC — high = intraday noise dominates
                ratio = gk_vol / cc_vol
                signals[sym] = ratio

            if len(signals) >= n_long + n_short:
                ranked = pd.Series(signals).sort_values(ascending=False)
                if direction == "low_ratio_long":
                    # Long low ratio (clean), short high ratio (noisy)
                    longs = ranked.index[-n_long:]
                    shorts = ranked.index[:n_short]
                else:
                    longs = ranked.index[:n_long]
                    shorts = ranked.index[-n_short:]

                weights = pd.Series(0.0, index=closes.columns)
                for s in longs:
                    weights[s] = 1.0 / n_long
                for s in shorts:
                    weights[s] = -1.0 / n_short
                last_rebal = i

    if not portfolio_returns:
        return None
    df = pd.DataFrame(portfolio_returns).set_index("date")
    return df["return"]


# ── H-174: Downside Beta Factor ──
# Compute beta using only BTC-down days. Assets with low downside beta are
# "defensive" — they don't drop as much when BTC drops. Long defensive, short fragile.
# Different from H-024 (full beta, KILLED) because full beta blends upside+downside.
# Downside beta captures asymmetric risk that matters for drawdown protection.

def backtest_h174(closes, lookback, rebal_freq, n_long, n_short, direction="low_dbeta_long"):
    if "BTC/USDT" not in closes.columns:
        return None
    btc = closes["BTC/USDT"]
    non_btc = [c for c in closes.columns if c != "BTC/USDT"]

    returns = closes.pct_change().dropna()
    btc_rets = btc.pct_change().dropna()
    dates = returns.index
    warmup = lookback + 10
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_returns.append({"date": dates[i], "return": day_ret})

        if i - last_rebal >= rebal_freq:
            signals = {}
            btc_window = btc_rets.iloc[i-lookback:i]
            down_mask = btc_window < 0  # BTC-down days only
            n_down = down_mask.sum()

            if n_down < lookback // 4:  # need enough down days
                last_rebal = i
                continue

            for sym in non_btc:
                asset_window = returns[sym].iloc[i-lookback:i]
                a_down = asset_window[down_mask].values
                b_down = btc_window[down_mask].values

                if len(a_down) < 5:
                    continue

                var_b = np.var(b_down)
                if var_b < 1e-12:
                    continue

                dbeta = np.cov(a_down, b_down)[0, 1] / var_b
                signals[sym] = dbeta

            if len(signals) >= n_long + n_short:
                ranked = pd.Series(signals).sort_values(ascending=False)
                if direction == "low_dbeta_long":
                    # Long low downside beta (defensive), short high (fragile)
                    longs = ranked.index[-n_long:]
                    shorts = ranked.index[:n_short]
                else:
                    longs = ranked.index[:n_long]
                    shorts = ranked.index[-n_short:]

                weights = pd.Series(0.0, index=closes.columns)
                for s in longs:
                    weights[s] = 1.0 / n_long
                for s in shorts:
                    weights[s] = -1.0 / n_short
                last_rebal = i

    if not portfolio_returns:
        return None
    df = pd.DataFrame(portfolio_returns).set_index("date")
    return df["return"]


# ── H-175: Net Money Flow Factor ──
# Net flow = (close - open) × volume. Positive = buying pressure, negative = selling.
# Rank by rolling average of net flow / average dollar volume (normalized).
# Long assets with net buying pressure, short assets with net selling.
# Different from H-012 (price only), H-021 (volume only), H-118 (OBV accumulates
# all up-days, this uses open-close range which is more granular).

def backtest_h175(closes, opens, volumes, lookback, rebal_freq, n_long, n_short, direction="inflow_long"):
    returns = closes.pct_change().dropna()
    dates = returns.index
    warmup = lookback + 10
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_returns.append({"date": dates[i], "return": day_ret})

        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                c = closes[sym].iloc[i-lookback:i]
                o = opens[sym].iloc[i-lookback:i]
                v = volumes[sym].iloc[i-lookback:i]

                if len(c) < lookback:
                    continue

                # Net flow = (close - open) * volume
                net_flow = ((c.values - o.values) / o.values) * v.values
                avg_dollar_vol = (c.values * v.values).mean()

                if avg_dollar_vol < 1e-8:
                    continue

                # Normalized net flow
                signals[sym] = net_flow.sum() / avg_dollar_vol

            if len(signals) >= n_long + n_short:
                ranked = pd.Series(signals).sort_values(ascending=False)
                if direction == "inflow_long":
                    longs = ranked.index[:n_long]
                    shorts = ranked.index[-n_short:]
                else:
                    longs = ranked.index[-n_long:]
                    shorts = ranked.index[:n_short]

                weights = pd.Series(0.0, index=closes.columns)
                for s in longs:
                    weights[s] = 1.0 / n_long
                for s in shorts:
                    weights[s] = -1.0 / n_short
                last_rebal = i

    if not portfolio_returns:
        return None
    df = pd.DataFrame(portfolio_returns).set_index("date")
    return df["return"]


def walk_forward(backtest_fn, data_args, best_params, n_folds=6, fold_days=90):
    """Walk-forward validation on the best parameter set."""
    closes = data_args[0]
    returns = closes.pct_change().dropna()
    total_days = len(returns)
    train_days = total_days - n_folds * fold_days

    if train_days < 120:
        print(f"  Not enough data for WF ({total_days} days, need {120 + n_folds * fold_days})")
        return []

    fold_results = []
    for fold in range(n_folds):
        test_start = train_days + fold * fold_days
        test_end = test_start + fold_days

        # Use all data up to test_end for this backtest, but only measure test period
        test_closes = data_args[0].iloc[:test_end]
        test_args = (test_closes,) + tuple(d.iloc[:test_end] if isinstance(d, pd.DataFrame) else d for d in data_args[1:])

        rets = backtest_fn(*test_args, **best_params)
        if rets is None:
            fold_results.append(0)
            continue

        # Only measure the test period
        test_dates = returns.index[test_start:test_end]
        oos_rets = rets.reindex(test_dates).dropna()
        ev = evaluate(oos_rets, f"fold_{fold}")
        if ev:
            fold_results.append(ev["sharpe"])
            print(f"  Fold {fold+1}: Sharpe {ev['sharpe']:.3f}, {ev['annual']:.1f}% ann, {ev['dd']:.1f}% DD ({ev['days']} days)")
        else:
            fold_results.append(0)
            print(f"  Fold {fold+1}: insufficient data")

    return fold_results


def full_validation(name, backtest_fn, data_args, extra_kwargs=None):
    """Run full 4/4 validation: IS param scan, WF, split-half, correlation."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    lookbacks = [10, 20, 30, 40, 60]
    rebals = [3, 5, 7]
    ns = [3, 4]

    if extra_kwargs and "directions" in extra_kwargs:
        directions = extra_kwargs.pop("directions")
    else:
        directions = [None]

    results = []
    total = len(lookbacks) * len(rebals) * len(ns) * len(directions)
    print(f"Scanning {total} parameter combinations...")

    for direction in directions:
        for lb in lookbacks:
            for rf in rebals:
                for n in ns:
                    kwargs = {"lookback": lb, "rebal_freq": rf, "n_long": n, "n_short": n}
                    if direction is not None:
                        kwargs["direction"] = direction
                    rets = backtest_fn(*data_args, **kwargs)
                    ev = evaluate(rets, f"{'D' + direction[:3] + '_' if direction else ''}LB{lb}_R{rf}_N{n}")
                    if ev:
                        ev["params"] = kwargs.copy()
                        results.append(ev)

    if not results:
        print("No valid results!")
        return None

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    pct_pos = n_positive / len(df) * 100
    print(f"\n--- IS Param Scan ---")
    print(f"Positive Sharpe: {n_positive}/{len(df)} ({pct_pos:.1f}%)")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"Best: {df.loc[df['sharpe'].idxmax(), 'label']} — Sharpe {df['sharpe'].max():.3f}, "
          f"{df.loc[df['sharpe'].idxmax(), 'annual']:.1f}% ann, {df.loc[df['sharpe'].idxmax(), 'dd']:.1f}% DD")

    if pct_pos < 80:
        print(f"\n*** FAIL IS: {pct_pos:.1f}% < 80% threshold ***")

    # Best param for WF
    best_idx = df["sharpe"].idxmax()
    best = df.loc[best_idx]
    best_params = results[best_idx]["params"]
    print(f"\nBest params for WF: {best_params}")

    # Walk-forward
    print(f"\n--- Walk-Forward OOS ---")
    wf_sharpes = walk_forward(backtest_fn, data_args, best_params)
    if wf_sharpes:
        n_pos = sum(1 for s in wf_sharpes if s > 0)
        mean_oos = np.mean(wf_sharpes)
        print(f"WF: {n_pos}/{len(wf_sharpes)} positive, mean OOS Sharpe: {mean_oos:.3f}")

    # Split-half
    print(f"\n--- Split-Half ---")
    closes = data_args[0]
    mid = len(closes) // 2
    h1_args = (closes.iloc[:mid],) + tuple(d.iloc[:mid] if isinstance(d, pd.DataFrame) else d for d in data_args[1:])
    h2_args = (closes.iloc[mid:],) + tuple(d.iloc[mid:] if isinstance(d, pd.DataFrame) else d for d in data_args[1:])

    h1_rets = backtest_fn(*h1_args, **best_params)
    h2_rets = backtest_fn(*h2_args, **best_params)
    h1_ev = evaluate(h1_rets, "H1")
    h2_ev = evaluate(h2_rets, "H2")
    if h1_ev and h2_ev:
        print(f"H1 Sharpe: {h1_ev['sharpe']:.3f}, H2 Sharpe: {h2_ev['sharpe']:.3f}")
    else:
        print("Split-half: insufficient data")

    # Correlation with existing strategies
    print(f"\n--- Correlation with Existing ---")
    best_rets = backtest_fn(*data_args, **best_params)
    if best_rets is not None:
        mom_rets = backtest_momentum(closes)
        eff_rets = backtest_h076(closes)
        tq_rets = backtest_h160(closes)

        for ref_name, ref_rets in [("H-012 (momentum)", mom_rets), ("H-076 (efficiency)", eff_rets), ("H-160 (trend-quality)", tq_rets)]:
            if ref_rets is not None:
                common = best_rets.index.intersection(ref_rets.index)
                if len(common) > 30:
                    corr = best_rets.loc[common].corr(ref_rets.loc[common])
                    print(f"  {ref_name}: {corr:.3f}")

    return {
        "is_pct_positive": pct_pos,
        "best_sharpe": float(df["sharpe"].max()),
        "best_params": best_params,
        "wf_sharpes": wf_sharpes if wf_sharpes else [],
        "h1_sharpe": h1_ev["sharpe"] if h1_ev else None,
        "h2_sharpe": h2_ev["sharpe"] if h2_ev else None,
    }


if __name__ == "__main__":
    print("Loading OHLCV data...")
    closes, opens, highs, lows, volumes = load_daily_ohlcv()
    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0]} to {closes.index[-1]}")

    # H-173: Garman-Klass Volatility Ratio
    r173 = full_validation(
        "H-173: Garman-Klass Volatility Ratio",
        backtest_h173,
        (closes, opens, highs, lows),
        extra_kwargs={"directions": ["low_ratio_long", "high_ratio_long"]},
    )

    # H-174: Downside Beta
    r174 = full_validation(
        "H-174: Downside Beta Factor",
        backtest_h174,
        (closes,),
        extra_kwargs={"directions": ["low_dbeta_long", "high_dbeta_long"]},
    )

    # H-175: Net Money Flow
    r175 = full_validation(
        "H-175: Net Money Flow Factor",
        backtest_h175,
        (closes, opens, volumes),
        extra_kwargs={"directions": ["inflow_long", "outflow_long"]},
    )

    print("\n\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, r in [("H-173 GK Vol Ratio", r173), ("H-174 Downside Beta", r174), ("H-175 Net Money Flow", r175)]:
        if r is None:
            print(f"{name}: NO RESULTS")
            continue
        wf_pos = sum(1 for s in r["wf_sharpes"] if s > 0) if r["wf_sharpes"] else 0
        wf_n = len(r["wf_sharpes"]) if r["wf_sharpes"] else 0
        print(f"{name}: IS {r['is_pct_positive']:.1f}% | Best Sharpe {r['best_sharpe']:.3f} | "
              f"WF {wf_pos}/{wf_n} | H1={r['h1_sharpe']} H2={r['h2_sharpe']}")
