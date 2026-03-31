#!/usr/bin/env python3
"""
H-164: Co-Momentum Factor (Peer-Weighted Momentum, 14 Crypto Assets)

For each asset i, compute co_momentum_i = sum_j(corr(i,j) * momentum_j) for j != i.
This measures how much an asset's correlated peers are also trending.
Long assets with high co-momentum (trend confirmed by peers), short those with low.

Different from raw momentum (H-012): co-momentum captures "consensus" signal.
Different from lead-lag (H-097, H-146): not about leading/lagging but about confirmation.
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


def compute_co_momentum(closes, i_idx, corr_lb, mom_lb):
    """Compute co-momentum for asset at column i_idx."""
    returns = closes.pct_change().dropna()
    if len(returns) < max(corr_lb, mom_lb) + 5:
        return np.nan

    # Rolling correlation matrix over corr_lb window
    ret_window = returns.iloc[-corr_lb:]
    corr_matrix = ret_window.corr()

    # Momentum for all assets
    mom = closes.iloc[-1] / closes.iloc[-1 - mom_lb] - 1

    asset = closes.columns[i_idx]
    co_mom = 0.0
    count = 0
    for j, other in enumerate(closes.columns):
        if j == i_idx:
            continue
        c = corr_matrix.iloc[i_idx, j]
        if not np.isnan(c):
            co_mom += c * mom.iloc[j]
            count += 1

    return co_mom / count if count > 0 else np.nan


def backtest_factor(closes, corr_lb, mom_lb, rebal_freq, n_long, n_short):
    returns = closes.pct_change().dropna()
    dates = returns.index
    warmup = max(corr_lb, mom_lb) + 10

    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_returns.append({"date": dates[i], "return": day_ret})

        if i - last_rebal >= rebal_freq:
            hist = closes.iloc[:i]
            ret_window = hist.pct_change().dropna().iloc[-corr_lb:]
            if len(ret_window) < corr_lb - 5:
                continue

            corr_matrix = ret_window.corr()
            mom = hist.iloc[-1] / hist.iloc[-1 - mom_lb] - 1

            signals = {}
            for j, sym in enumerate(closes.columns):
                co_mom = 0.0
                count = 0
                for k, other in enumerate(closes.columns):
                    if k == j:
                        continue
                    c = corr_matrix.iloc[j, k]
                    if not np.isnan(c):
                        co_mom += c * mom.iloc[k]
                        count += 1
                if count > 0:
                    signals[sym] = co_mom / count

            if len(signals) >= n_long + n_short:
                ranked = pd.Series(signals).sort_values(ascending=False)
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


def main():
    print("Loading data...")
    closes = load_daily_closes()
    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0].date()} to {closes.index[-1].date()}")

    # Parameter grid
    corr_lbs = [30, 60, 90]      # correlation lookback
    mom_lbs = [20, 40, 60]       # momentum lookback
    rebals = [3, 5, 7]
    ns = [3, 4]

    results = []
    total = len(corr_lbs) * len(mom_lbs) * len(rebals) * len(ns)
    print(f"\nScanning {total} parameter combinations...")

    for cl in corr_lbs:
        for ml in mom_lbs:
            for rf in rebals:
                for n in ns:
                    rets = backtest_factor(closes, cl, ml, rf, n, n)
                    ev = evaluate(rets, f"CL{cl}_ML{ml}_R{rf}_N{n}")
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

    top = df.nlargest(5, "sharpe")
    print("\nTop 5:")
    for _, r in top.iterrows():
        print(f"  {r['label']}: Sharpe {r['sharpe']:.3f}, Ann {r['annual']:.1f}%, DD {r['dd']:.1f}%, {r['days']}d")

    if n_positive / len(df) < 0.80:
        print(f"\nFAIL: Only {n_positive/len(df)*100:.1f}% positive (need >=80%). REJECTED.")
        return

    # Walk-forward on best config
    best = df.loc[df["sharpe"].idxmax()]
    parts = best["label"].split("_")
    cl = int(parts[0][2:])
    ml = int(parts[1][2:])
    rf = int(parts[2][1:])
    n = int(parts[3][1:])

    print(f"\n=== WALK-FORWARD ({best['label']}) ===")
    returns_all = closes.pct_change().dropna()
    total_days = len(returns_all)
    test_days = 90
    n_folds = 6
    wf_results = []
    for fold in range(n_folds):
        test_end = total_days - fold * test_days
        test_start = test_end - test_days
        warmup = max(cl, ml) + 10
        if test_start < warmup + 60:
            break
        test_closes = closes.iloc[:test_end]
        rets = backtest_factor(test_closes, cl, ml, rf, n, n)
        if rets is not None and len(rets) > 0:
            test_rets = rets.iloc[-test_days:]
            if len(test_rets) > 10:
                ev = evaluate(test_rets, f"fold{fold}")
                if ev:
                    wf_results.append(ev)

    if wf_results:
        for r in wf_results:
            print(f"  {r['label']}: Sharpe {r['sharpe']:.3f}")
        wf_sharpes = [r["sharpe"] for r in wf_results]
        n_pos = sum(1 for s in wf_sharpes if s > 0)
        print(f"WF positive: {n_pos}/{len(wf_results)}, mean OOS: {np.mean(wf_sharpes):.3f}")

    # Split-half
    print(f"\n=== SPLIT-HALF ===")
    half = len(closes) // 2
    h1_results = []
    h2_results = []
    for cl_ in corr_lbs:
        for ml_ in mom_lbs:
            for rf_ in rebals:
                for n_ in ns:
                    r1 = backtest_factor(closes.iloc[:half], cl_, ml_, rf_, n_, n_)
                    r2 = backtest_factor(closes.iloc[half:], cl_, ml_, rf_, n_, n_)
                    e1 = evaluate(r1)
                    e2 = evaluate(r2)
                    if e1 and e2:
                        h1_results.append(e1["sharpe"])
                        h2_results.append(e2["sharpe"])

    if h1_results and h2_results:
        corr = np.corrcoef(h1_results, h2_results)[0, 1] if len(h1_results) > 1 else 0
        h1_mean = np.mean(h1_results)
        h2_mean = np.mean(h2_results)
        print(f"Split-half corr: {corr:.3f}")
        print(f"H1 mean: {h1_mean:.3f}, H2 mean: {h2_mean:.3f}")

    # Correlation with H-012 and H-076
    print(f"\n=== CORRELATIONS ===")
    mom_rets = backtest_momentum(closes)
    best_rets = backtest_factor(closes, cl, ml, rf, n, n)
    if mom_rets is not None and best_rets is not None:
        common = mom_rets.index.intersection(best_rets.index)
        if len(common) > 30:
            corr_mom = np.corrcoef(mom_rets.loc[common], best_rets.loc[common])[0, 1]
            print(f"Corr with H-012 momentum: {corr_mom:.3f}")


if __name__ == "__main__":
    main()
