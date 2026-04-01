#!/usr/bin/env python3
"""
H-167: Volume-Price Confirmation Factor
H-168: Return Autocorrelation Factor
H-169: Beta-Adjusted Momentum (Alpha Factor)

Three new cross-sectional factor backtests using the standard 4/4 validation framework.
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


def load_daily():
    daily_close = {}
    daily_volume = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=800)
            if len(df) < 200:
                continue
            daily = resample_to_daily(df)
            daily_close[sym] = daily["close"]
            daily_volume[sym] = daily["volume"]
        except Exception:
            pass
    closes = pd.DataFrame(daily_close).dropna(how="all").ffill().dropna()
    volumes = pd.DataFrame(daily_volume).reindex(closes.index).ffill().dropna()
    common = closes.index.intersection(volumes.index)
    return closes.loc[common], volumes.loc[common]


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
    """Reference H-012 momentum for correlation comparison."""
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


# ── H-167: Volume-Price Confirmation Factor ──
# Measure rolling correlation between price changes and volume changes.
# High correlation = volume confirms trend. Low/negative = volume diverges.
# Long confirmed (volume supporting price), short diverging.
# Different from H-021 (volume momentum, just volume level) and H-153 (volume surprise).

def compute_vol_price_corr(prices, volumes, lookback):
    """Rolling correlation between daily returns and volume changes."""
    if len(prices) < lookback + 2:
        return np.nan
    price_rets = prices.pct_change().iloc[-lookback:]
    vol_rets = volumes.pct_change().iloc[-lookback:]
    # Drop NaN
    mask = price_rets.notna() & vol_rets.notna()
    if mask.sum() < lookback // 2:
        return np.nan
    corr = np.corrcoef(price_rets[mask].values, vol_rets[mask].values)[0, 1]
    if np.isnan(corr):
        return 0.0
    return corr


def backtest_h167(closes, volumes, lookback, rebal_freq, n_long, n_short, direction="confirm_long"):
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
                p = closes[sym].iloc[:i]
                v = volumes[sym].iloc[:i]
                val = compute_vol_price_corr(p, v, lookback)
                if not np.isnan(val):
                    signals[sym] = val

            if len(signals) >= n_long + n_short:
                ranked = pd.Series(signals).sort_values(ascending=False)
                if direction == "confirm_long":
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


# ── H-168: Return Autocorrelation Factor ──
# Measure rolling first-order autocorrelation of daily returns.
# High positive autocorrelation = trending. Negative = mean-reverting.
# Long high-autocorrelation (trending assets), short low (mean-reverting).
# Different from H-160 (trend-quality uses efficiency ratio) and H-166 (persistence).

def compute_autocorrelation(prices, lookback):
    """Rolling first-order autocorrelation of daily returns."""
    if len(prices) < lookback + 3:
        return np.nan
    rets = prices.pct_change().dropna().iloc[-lookback:]
    if len(rets) < lookback - 1:
        return np.nan
    r1 = rets.iloc[:-1].values
    r2 = rets.iloc[1:].values
    if len(r1) < 10:
        return np.nan
    corr = np.corrcoef(r1, r2)[0, 1]
    return corr if not np.isnan(corr) else 0.0


def backtest_h168(closes, lookback, rebal_freq, n_long, n_short, direction="autocorr_long"):
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
                p = closes[sym].iloc[:i]
                val = compute_autocorrelation(p, lookback)
                if not np.isnan(val):
                    signals[sym] = val

            if len(signals) >= n_long + n_short:
                ranked = pd.Series(signals).sort_values(ascending=False)
                if direction == "autocorr_long":
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


# ── H-169: Beta-Adjusted Momentum (Alpha Factor) ──
# Instead of raw return, rank assets by alpha vs BTC (return - beta * BTC_return).
# This captures genuine outperformance, not just high-beta rides.
# Long positive alpha, short negative alpha.
# Different from H-012 (raw momentum) and H-019 (low volatility).

def compute_alpha(prices, btc_prices, lookback):
    """Rolling alpha: asset return minus beta * BTC return."""
    if len(prices) < lookback + 2 or len(btc_prices) < lookback + 2:
        return np.nan
    asset_rets = prices.pct_change().dropna().iloc[-lookback:]
    btc_rets = btc_prices.pct_change().dropna().iloc[-lookback:]
    common = asset_rets.index.intersection(btc_rets.index)
    if len(common) < lookback // 2:
        return np.nan
    a = asset_rets.loc[common].values
    b = btc_rets.loc[common].values
    # OLS beta
    var_b = np.var(b)
    if var_b < 1e-12:
        return np.nan
    beta = np.cov(a, b)[0, 1] / var_b
    # Alpha = cumulative excess return
    alpha = a.sum() - beta * b.sum()
    return alpha


def backtest_h169(closes, lookback, rebal_freq, n_long, n_short, direction="alpha_long"):
    if "BTC/USDT" not in closes.columns:
        return None
    btc = closes["BTC/USDT"]
    # Only rank non-BTC assets
    non_btc = [c for c in closes.columns if c != "BTC/USDT"]

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
            for sym in non_btc:
                p = closes[sym].iloc[:i]
                b = btc.iloc[:i]
                val = compute_alpha(p, b, lookback)
                if not np.isnan(val):
                    signals[sym] = val

            if len(signals) >= n_long + n_short:
                ranked = pd.Series(signals).sort_values(ascending=False)
                if direction == "alpha_long":
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


def full_validation(name, backtest_fn, closes, volumes=None, extra_kwargs=None):
    """Run full 4/4 validation: IS param scan, WF, split-half, correlation."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    lookbacks = [10, 20, 30, 40, 60]
    rebals = [3, 5, 7]
    ns = [3, 4]

    results = []
    total = len(lookbacks) * len(rebals) * len(ns)
    print(f"Scanning {total} parameter combinations...")

    for lb in lookbacks:
        for rf in rebals:
            for n in ns:
                kwargs = {"lookback": lb, "rebal_freq": rf, "n_long": n, "n_short": n}
                if volumes is not None:
                    kwargs["volumes"] = volumes
                if extra_kwargs:
                    kwargs.update(extra_kwargs)
                rets = backtest_fn(closes, **kwargs)
                ev = evaluate(rets, f"LB{lb}_R{rf}_N{n}")
                if ev:
                    results.append(ev)

    if not results:
        print("No valid results!")
        return

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    pct_pos = n_positive / len(df) * 100
    print(f"\n--- IS Param Scan ---")
    print(f"Positive Sharpe: {n_positive}/{len(df)} ({pct_pos:.1f}%)")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"Best: {df.loc[df['sharpe'].idxmax(), 'label']} Sharpe {df['sharpe'].max():.3f}")

    top = df.nlargest(3, "sharpe")
    for _, r in top.iterrows():
        print(f"  {r['label']}: Sharpe {r['sharpe']:.3f}, Ann {r['annual']:.1f}%, DD {r['dd']:.1f}%, {r['days']}d")

    if pct_pos < 80:
        print(f"\n** FAIL criterion 1: {pct_pos:.1f}% positive (need >=80%). REJECTED. **")
        return

    # Walk-forward (best params)
    best = df.loc[df["sharpe"].idxmax()]
    parts = best["label"].split("_")
    lb_best = int(parts[0][2:])
    rf_best = int(parts[1][1:])
    n_best = int(parts[2][1:])

    print(f"\n--- Walk-Forward ({best['label']}) ---")
    total_days = len(closes)
    test_days = 90
    n_folds = 6
    wf_results = []
    for fold in range(n_folds):
        test_end = total_days - fold * test_days
        test_start = test_end - test_days
        if test_start < lb_best + 60:
            break
        test_closes = closes.iloc[:test_end]
        test_volumes = volumes.iloc[:test_end] if volumes is not None else None

        kwargs = {"lookback": lb_best, "rebal_freq": rf_best, "n_long": n_best, "n_short": n_best}
        if test_volumes is not None:
            kwargs["volumes"] = test_volumes
        if extra_kwargs:
            kwargs.update(extra_kwargs)

        rets = backtest_fn(test_closes, **kwargs)
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
        n_pos_wf = sum(1 for s in wf_sharpes if s > 0)
        mean_wf = np.mean(wf_sharpes)
        print(f"WF positive: {n_pos_wf}/{len(wf_results)}, mean OOS: {mean_wf:.3f}")
    else:
        n_pos_wf = 0
        mean_wf = 0
        print("WF: no valid folds")

    # Split-half
    print(f"\n--- Split-Half ---")
    half = len(closes) // 2
    h1_res, h2_res = [], []
    for lb_ in lookbacks:
        for rf_ in rebals:
            for n_ in ns:
                kwargs1 = {"lookback": lb_, "rebal_freq": rf_, "n_long": n_, "n_short": n_}
                kwargs2 = dict(kwargs1)
                if volumes is not None:
                    kwargs1["volumes"] = volumes.iloc[:half]
                    kwargs2["volumes"] = volumes.iloc[half:]
                if extra_kwargs:
                    kwargs1.update(extra_kwargs)
                    kwargs2.update(extra_kwargs)

                r1 = backtest_fn(closes.iloc[:half], **kwargs1)
                r2 = backtest_fn(closes.iloc[half:], **kwargs2)
                e1 = evaluate(r1)
                e2 = evaluate(r2)
                if e1 and e2:
                    h1_res.append(e1["sharpe"])
                    h2_res.append(e2["sharpe"])

    if h1_res and h2_res:
        h1_mean = np.mean(h1_res)
        h2_mean = np.mean(h2_res)
        sh_corr = np.corrcoef(h1_res, h2_res)[0, 1] if len(h1_res) > 1 else 0
        print(f"H1 mean: {h1_mean:.3f}, H2 mean: {h2_mean:.3f}, corr: {sh_corr:.3f}")
    else:
        h1_mean = h2_mean = sh_corr = 0
        print("Split-half: insufficient data")

    # Correlation with H-012 momentum
    print(f"\n--- Correlations ---")
    mom_rets = backtest_momentum(closes)
    kwargs_best = {"lookback": lb_best, "rebal_freq": rf_best, "n_long": n_best, "n_short": n_best}
    if volumes is not None:
        kwargs_best["volumes"] = volumes
    if extra_kwargs:
        kwargs_best.update(extra_kwargs)
    best_rets = backtest_fn(closes, **kwargs_best)

    corr_mom = 0
    if mom_rets is not None and best_rets is not None:
        common = mom_rets.index.intersection(best_rets.index)
        if len(common) > 30:
            corr_mom = np.corrcoef(mom_rets.loc[common], best_rets.loc[common])[0, 1]
            print(f"Corr with H-012 momentum: {corr_mom:.3f}")

    # Summary
    print(f"\n--- SUMMARY ---")
    print(f"1. IS positive: {pct_pos:.1f}% {'PASS' if pct_pos >= 80 else 'FAIL'}")
    print(f"2. WF: {n_pos_wf}/{len(wf_results) if wf_results else 0} positive, mean {mean_wf:.3f} {'PASS' if wf_results and n_pos_wf >= 4 else 'FAIL'}")
    sh_pass = h1_mean > 0 and h2_mean > 0
    print(f"3. Split-half: H1={h1_mean:.3f} H2={h2_mean:.3f} {'PASS' if sh_pass else 'FAIL'}")
    corr_pass = abs(corr_mom) < 0.40
    print(f"4. Correlation: {corr_mom:.3f} {'PASS' if corr_pass else 'FAIL (>0.40)'}")

    passed = sum([pct_pos >= 80, wf_results and n_pos_wf >= 4, sh_pass, corr_pass])
    print(f"\nScore: {passed}/4")
    if passed == 4:
        print("** CONFIRMED — all 4 criteria pass **")
    else:
        print("** REJECTED **")


def main():
    print("Loading data...")
    closes, volumes = load_daily()
    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0].date()} to {closes.index[-1].date()}")

    # H-167: Volume-Price Confirmation
    full_validation("H-167: Volume-Price Confirmation Factor", backtest_h167, closes, volumes)

    # H-168: Return Autocorrelation
    full_validation("H-168: Return Autocorrelation Factor", backtest_h168, closes)

    # H-169: Beta-Adjusted Momentum (Alpha)
    full_validation("H-169: Beta-Adjusted Momentum (Alpha Factor)", backtest_h169, closes)


if __name__ == "__main__":
    main()
