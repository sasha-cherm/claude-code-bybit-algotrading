#!/usr/bin/env python3
"""
H-163: Momentum Concentration Factor (14 Crypto Assets)

Measures what fraction of total cumulative return came from the single
best day in the lookback window. High concentration = fragile momentum
(one big day). Low concentration = broad-based persistent trend.

Long low-concentration momentum (robust trends),
short high-concentration (fragile/luck-driven).
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


def compute_momentum_concentration(returns_window: pd.Series) -> float:
    """
    Concentration = max(|daily_ret|) / sum(|daily_ret|).
    High value = one day dominates returns. Low = spread out.
    Also consider directional: max_ret / total_ret for signed version.
    """
    abs_rets = returns_window.abs()
    total_abs = abs_rets.sum()
    if total_abs < 1e-10:
        return np.nan

    max_abs_ret = abs_rets.max()
    concentration = max_abs_ret / total_abs
    return concentration


def backtest_factor(closes, lookback, rebal_freq, n_long, n_short, direction="low_conc_long"):
    """
    direction: 'low_conc_long' = long low-concentration (robust), short high (fragile)
               'high_conc_long' = reverse
    """
    returns = closes.pct_change().dropna()
    dates = returns.index
    warmup = lookback + 5

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
                rets_window = returns[sym].iloc[i-lookback:i]
                if len(rets_window) < lookback:
                    continue
                conc = compute_momentum_concentration(rets_window)
                if not np.isnan(conc):
                    signals[sym] = conc

            if len(signals) >= n_long + n_short:
                ranked = pd.Series(signals).sort_values(ascending=False)
                if direction == "low_conc_long":
                    # Long low concentration (bottom = robust), short high (top = fragile)
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


def walk_forward(closes, lookback, rebal_freq, n_long, n_short, direction, n_folds=6, test_days=90):
    returns = closes.pct_change().dropna()
    dates = returns.index
    total = len(dates)
    warmup = lookback + 5

    results = []
    for fold in range(n_folds):
        test_end = total - fold * test_days
        test_start = test_end - test_days
        if test_start < warmup + 60:
            break

        test_closes = closes.iloc[:test_end]
        rets = backtest_factor(test_closes, lookback, rebal_freq, n_long, n_short, direction)
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
    lookbacks = [20, 30, 40, 60]
    rebals = [3, 5, 7]
    ns = [3, 4]
    directions = ["low_conc_long", "high_conc_long"]

    results = []
    total = len(lookbacks) * len(rebals) * len(ns) * len(directions)
    print(f"\nScanning {total} parameter combinations...")

    for lb in lookbacks:
        for rf in rebals:
            for n in ns:
                for d in directions:
                    rets = backtest_factor(closes, lb, rf, n, n, d)
                    ev = evaluate(rets, f"LB{lb}_R{rf}_N{n}_{d}")
                    if ev:
                        results.append(ev)

    if not results:
        print("No valid results!")
        return

    df = pd.DataFrame(results)

    for d in directions:
        sub = df[df["label"].str.contains(d)]
        n_pos = (sub["sharpe"] > 0).sum()
        print(f"\n=== {d.upper()} ===")
        print(f"Positive: {n_pos}/{len(sub)} ({n_pos/len(sub)*100:.1f}%)")
        print(f"Mean Sharpe: {sub['sharpe'].mean():.3f}, Best: {sub['sharpe'].max():.3f}")

    n_positive = (df["sharpe"] > 0).sum()
    print(f"\n=== OVERALL ===")
    print(f"Positive: {n_positive}/{len(df)} ({n_positive/len(df)*100:.1f}%)")

    for d in directions:
        sub = df[df["label"].str.contains(d)]
        if len(sub) > 0:
            best = sub.loc[sub["sharpe"].idxmax()]
            print(f"Best {d}: {best['label']} Sharpe {best['sharpe']:.3f}, Ann {best['annual']:.1f}%, DD {best['dd']:.1f}%")

    # Find best direction
    best_dir = None
    for d in directions:
        sub = df[df["label"].str.contains(d)]
        pct = (sub["sharpe"] > 0).sum() / len(sub)
        if pct >= 0.80:
            if best_dir is None:
                best_dir = d
            else:
                sub2 = df[df["label"].str.contains(d)]
                sub1 = df[df["label"].str.contains(best_dir)]
                if sub2["sharpe"].mean() > sub1["sharpe"].mean():
                    best_dir = d

    if best_dir is None:
        print("\nFAIL: No direction passes 80% positive threshold. REJECTED.")
        return

    sub = df[df["label"].str.contains(best_dir)]
    best = sub.loc[sub["sharpe"].idxmax()]
    parts = best["label"].split("_")
    lb = int(parts[0][2:])
    rf = int(parts[1][1:])
    n = int(parts[2][1:])

    print(f"\n=== WALK-FORWARD ({best['label']}) ===")
    wf = walk_forward(closes, lb, rf, n, n, best_dir)
    if wf:
        for r in wf:
            print(f"  {r['label']}: Sharpe {r['sharpe']:.3f}")
        wf_sharpes = [r["sharpe"] for r in wf]
        n_pos = sum(1 for s in wf_sharpes if s > 0)
        print(f"WF positive: {n_pos}/{len(wf)}, mean OOS: {np.mean(wf_sharpes):.3f}")

    # Split-half
    print(f"\n=== SPLIT-HALF ===")
    half = len(closes) // 2
    h1_res, h2_res = [], []
    for lb in lookbacks:
        for rf in rebals:
            for n in ns:
                r1 = backtest_factor(closes.iloc[:half], lb, rf, n, n, best_dir)
                r2 = backtest_factor(closes.iloc[half:], lb, rf, n, n, best_dir)
                e1 = evaluate(r1)
                e2 = evaluate(r2)
                if e1 and e2:
                    h1_res.append(e1["sharpe"])
                    h2_res.append(e2["sharpe"])

    if h1_res and h2_res:
        corr = np.corrcoef(h1_res, h2_res)[0, 1]
        print(f"Split-half corr: {corr:.3f}")
        print(f"H1 mean: {np.mean(h1_res):.3f}, H2 mean: {np.mean(h2_res):.3f}")
        both = sum(1 for a, b in zip(h1_res, h2_res) if a > 0 and b > 0)
        print(f"Both positive: {both}/{len(h1_res)} ({both/len(h1_res)*100:.1f}%)")

    # Correlation
    print(f"\n=== CORRELATION ===")
    mom_rets = backtest_momentum(closes)
    best_rets = backtest_factor(closes, lb, rf, n, n, best_dir)
    if mom_rets is not None and best_rets is not None:
        common = mom_rets.index.intersection(best_rets.index)
        if len(common) > 30:
            c = np.corrcoef(mom_rets.loc[common], best_rets.loc[common])[0, 1]
            print(f"Corr H-012 (momentum): {c:.3f}")


def backtest_momentum(closes, lookback=60, rebal_freq=5, n=4):
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
