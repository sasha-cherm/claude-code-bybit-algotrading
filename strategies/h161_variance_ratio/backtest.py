#!/usr/bin/env python3
"""
H-161: Variance Ratio Factor (Cross-Sectional, 14 Crypto Assets)

Lo-MacKinlay variance ratio VR(k) = Var(k-day returns) / (k * Var(1-day returns)).
VR > 1 → trending (positive autocorrelation), long.
VR < 1 → mean-reverting (negative autocorrelation), short.

Different from H-116 (Hurst exponent) in computation method and horizon specificity.
Different from H-115/H-135 (raw autocorrelation) — VR integrates over multiple lags.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]


def load_daily_closes():
    daily_close = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=800)
            if len(df) < 200:
                continue
            daily = resample_to_daily(df)
            daily_close[sym] = daily["close"]
        except Exception:
            pass
    return pd.DataFrame(daily_close).dropna(how="all").ffill().dropna()


def compute_variance_ratio(prices: pd.Series, lookback: int, k: int) -> float:
    """Compute VR(k) over lookback window."""
    rets_1d = prices.pct_change().dropna()
    if len(rets_1d) < lookback:
        return np.nan

    rets_window = rets_1d.iloc[-lookback:]

    # 1-day variance
    var_1 = rets_window.var()
    if var_1 < 1e-12:
        return np.nan

    # k-day returns
    rets_k = prices.pct_change(k).dropna()
    if len(rets_k) < lookback // k:
        return np.nan

    rets_k_window = rets_k.iloc[-(lookback // k):]
    var_k = rets_k_window.var()

    return var_k / (k * var_1)


def backtest_factor(closes, lookback, k, rebal_freq, n_long, n_short, direction="trend_long"):
    """
    direction: 'trend_long' = long VR>1 (trending), short VR<1
    """
    returns = closes.pct_change().dropna()
    dates = returns.index
    n_assets = len(closes.columns)
    warmup = max(lookback, k * 10) + 5

    portfolio_returns = []
    last_rebal = -rebal_freq

    weights = pd.Series(0.0, index=closes.columns)

    for i in range(warmup, len(dates)):
        # Daily portfolio return
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_returns.append({"date": dates[i], "return": day_ret})

        # Rebalance check
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                prices_window = closes[sym].iloc[:i]  # lagged (up to yesterday)
                vr = compute_variance_ratio(prices_window, lookback, k)
                if not np.isnan(vr):
                    signals[sym] = vr

            if len(signals) >= n_long + n_short:
                ranked = pd.Series(signals).sort_values(ascending=False)
                if direction == "trend_long":
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


def walk_forward(closes, lookback, k, rebal_freq, n_long, n_short, direction, n_folds=6, test_days=90):
    """Walk-forward OOS validation."""
    returns = closes.pct_change().dropna()
    dates = returns.index
    total = len(dates)
    warmup = max(lookback, k * 10) + 5

    results = []
    for fold in range(n_folds):
        test_end = total - fold * test_days
        test_start = test_end - test_days
        if test_start < warmup + 60:
            break

        # Run backtest on test period only (using all prior data for signal)
        test_closes = closes.iloc[:test_end]
        rets = backtest_factor(test_closes, lookback, k, rebal_freq, n_long, n_short, direction)
        if rets is not None and len(rets) > 0:
            test_rets = rets.iloc[-test_days:]
            if len(test_rets) > 10:
                ev = evaluate(test_rets, f"fold{fold}")
                if ev:
                    results.append(ev)

    return results


def main():
    print("Loading data...")
    closes = load_daily_closes()
    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0].date()} to {closes.index[-1].date()}")

    # Parameter grid
    lookbacks = [40, 60, 80]
    ks = [5, 10]           # VR horizon (5-day, 10-day)
    rebals = [5, 7, 10]
    ns = [3, 4]
    directions = ["trend_long"]  # long trending (VR>1), short mean-reverting

    results = []
    total = len(lookbacks) * len(ks) * len(rebals) * len(ns) * len(directions)
    print(f"\nScanning {total} parameter combinations...")

    for lb in lookbacks:
        for k in ks:
            for rf in rebals:
                for n in ns:
                    for d in directions:
                        rets = backtest_factor(closes, lb, k, rf, n, n, d)
                        ev = evaluate(rets, f"LB{lb}_K{k}_R{rf}_N{n}_{d}")
                        if ev:
                            results.append(ev)

    if not results:
        print("No valid results!")
        return

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    print(f"\n=== PARAM SCAN RESULTS ===")
    print(f"Total configs: {len(df)}")
    print(f"Positive Sharpe: {n_positive}/{len(df)} ({n_positive/len(df)*100:.1f}%)")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"Best: {df.loc[df['sharpe'].idxmax(), 'label']} Sharpe {df['sharpe'].max():.3f}")

    # Top 5
    top = df.nlargest(5, "sharpe")
    print("\nTop 5:")
    for _, r in top.iterrows():
        print(f"  {r['label']}: Sharpe {r['sharpe']:.3f}, Ann {r['annual']:.1f}%, DD {r['dd']:.1f}%, {r['days']}d")

    # Threshold check: need >= 80% positive
    if n_positive / len(df) < 0.80:
        print(f"\nFAIL: Only {n_positive/len(df)*100:.1f}% positive (need >=80%). REJECTED.")
        return

    # Walk-forward on best config
    best = df.loc[df["sharpe"].idxmax()]
    parts = best["label"].split("_")
    lb = int(parts[0][2:])
    k = int(parts[1][1:])
    rf = int(parts[2][1:])
    n = int(parts[3][1:])
    d = parts[4] + "_" + parts[5] if len(parts) > 5 else parts[4]

    print(f"\n=== WALK-FORWARD ({best['label']}) ===")
    wf = walk_forward(closes, lb, k, rf, n, n, d)
    if wf:
        for r in wf:
            print(f"  {r['label']}: Sharpe {r['sharpe']:.3f}")
        wf_sharpes = [r["sharpe"] for r in wf]
        n_pos = sum(1 for s in wf_sharpes if s > 0)
        print(f"WF positive: {n_pos}/{len(wf)}, mean OOS: {np.mean(wf_sharpes):.3f}")

    # Split-half stability
    print(f"\n=== SPLIT-HALF ===")
    half = len(closes) // 2
    h1_results = []
    h2_results = []
    for lb in lookbacks:
        for k in ks:
            for rf in rebals:
                for n in ns:
                    for d in directions:
                        r1 = backtest_factor(closes.iloc[:half], lb, k, rf, n, n, d)
                        r2 = backtest_factor(closes.iloc[half:], lb, k, rf, n, n, d)
                        e1 = evaluate(r1)
                        e2 = evaluate(r2)
                        if e1 and e2:
                            h1_results.append(e1["sharpe"])
                            h2_results.append(e2["sharpe"])

    if h1_results and h2_results:
        corr = np.corrcoef(h1_results, h2_results)[0, 1]
        h1_mean = np.mean(h1_results)
        h2_mean = np.mean(h2_results)
        both_pos = sum(1 for a, b in zip(h1_results, h2_results) if a > 0 and b > 0)
        print(f"Split-half corr: {corr:.3f}")
        print(f"H1 mean: {h1_mean:.3f}, H2 mean: {h2_mean:.3f}")
        print(f"Both positive: {both_pos}/{len(h1_results)} ({both_pos/len(h1_results)*100:.1f}%)")

    # Correlation with H-012 (momentum)
    print(f"\n=== CORRELATION WITH H-012 ===")
    mom_rets = backtest_momentum(closes)
    best_rets = backtest_factor(closes, lb, k, rf, n, n, d)
    if mom_rets is not None and best_rets is not None:
        common = mom_rets.index.intersection(best_rets.index)
        if len(common) > 30:
            corr_mom = np.corrcoef(mom_rets.loc[common], best_rets.loc[common])[0, 1]
            print(f"Correlation with H-012 momentum: {corr_mom:.3f}")


def backtest_momentum(closes, lookback=60, rebal_freq=5, n=4):
    """Simple momentum factor for correlation check."""
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


if __name__ == "__main__":
    main()
