#!/usr/bin/env python3
"""
H-274: Return-Volume Correlation Factor (14 Assets)

Idea: Compute rolling correlation between daily returns and daily volume.
  High positive corr = volume confirms price moves (informed trading, smart money).
  Low/negative corr = volume opposes price (noise, liquidations, panic).
  Long assets with high return-volume correlation (informed trading), short low.

Different from:
- H-021 (Volume Momentum): uses volume level change, not return-volume relationship
- H-094 (Volume Asymmetry): compares up-day vs down-day volumes, not correlation
- H-103 (PV Correlation, prior): was rejected in earlier attempt with different grid
- H-219 (Up-Volume Ratio): fraction of volume on up days, not correlation metric
- H-175 (Money Flow): uses price-weighted volume, not correlation
- H-191 (Vol-Price Elasticity): regression-based, different measure

Key insight: The correlation between returns and volume captures the information
content of trading. When large moves come with high volume, it suggests
institutional/informed participation. When volume is disconnected from price,
it suggests noise or manipulation.

Signal construction:
  1. For each asset, compute rolling correlation(daily_return, daily_volume) over lookback
  2. Rank XS: long high corr (informed), short low corr (noise)

Parameter grid:
  Lookback: [10, 15, 20, 30, 40, 60]
  Rebal freq: [3, 5, 7]
  N: [3, 4]
  Direction: [high_corr_long, low_corr_long]
  Total: 6 x 3 x 2 x 2 = 72 combos
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS_ALL = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

LOOKBACKS = [10, 15, 20, 30, 40, 60]
REBALS = [3, 5, 7]
NS = [3, 4]
DIRECTIONS = ["high_corr_long", "low_corr_long"]

COST_PER_SIDE = 0.0005

WF_FOLDS = 6
WF_TEST_DAYS = 90
WF_TRAIN_MIN = 120


def load_data():
    data_dir = ROOT / "data"
    closes = {}
    volumes = {}
    for sym in ASSETS_ALL:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if "close" not in df.columns or "volume" not in df.columns or len(df) < 200:
            continue
        dc = df["close"].copy()
        dv = df["volume"].copy()
        if dc.index.tzinfo is not None:
            dc.index = dc.index.tz_localize(None)
            dv.index = dv.index.tz_localize(None)
        closes[sym] = dc
        volumes[sym] = dv
    closes = pd.DataFrame(closes).dropna(how="all").ffill().dropna()
    volumes = pd.DataFrame(volumes).dropna(how="all").ffill().dropna()
    # Align
    common_idx = closes.index.intersection(volumes.index)
    closes = closes.loc[common_idx]
    volumes = volumes.loc[common_idx]
    return closes, volumes


def compute_return_volume_corr(closes, volumes, lookback):
    """Rolling correlation between daily returns and daily volume."""
    rets = closes.pct_change()
    # Use log volume to reduce skewness
    log_vol = np.log1p(volumes)

    corr_df = pd.DataFrame(index=rets.index, columns=rets.columns, dtype=float)
    for asset in rets.columns:
        r = rets[asset]
        v = log_vol[asset]
        corr_df[asset] = r.rolling(lookback, min_periods=lookback).corr(v)
    return corr_df


def evaluate(rets, label=""):
    if rets is None or len(rets) < 30:
        return None
    ann = rets.mean() * 365
    vol = rets.std() * np.sqrt(365)
    shp = ann / vol if vol > 1e-8 else 0.0
    cum = (1 + rets).cumprod()
    mdd = (cum / cum.cummax() - 1).min()
    return {
        "label": label, "sharpe": round(float(shp), 4),
        "annual": round(float(ann * 100), 2), "dd": round(float(mdd * 100), 2),
        "days": len(rets),
    }


def backtest_factor(closes, signal_df, rebal_freq, n, direction):
    cols = list(set(signal_df.columns) & set(closes.columns))
    if len(cols) < 2 * n:
        return None
    returns = closes[cols].pct_change().dropna()
    signal_df = signal_df[cols].reindex(returns.index)
    dates = returns.index

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=cols)
    prev_weights = pd.Series(0.0, index=cols)

    for i in range(1, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": float(day_ret)})
        if i - last_rebal < rebal_freq:
            continue
        cv = signal_df.iloc[i]
        valid = cv.dropna()
        if len(valid) < 2 * n:
            continue
        if direction == "high_corr_long":
            ranked = valid.sort_values(ascending=False)
        else:
            ranked = valid.sort_values(ascending=True)
        longs = ranked.index[:n]
        shorts = ranked.index[-n:]
        new_weights = pd.Series(0.0, index=cols)
        for s in longs:
            new_weights[s] = 1.0 / n
        for s in shorts:
            new_weights[s] = -1.0 / n
        turnover = (new_weights - prev_weights).abs().sum()
        tc = turnover * COST_PER_SIDE
        if portfolio_rets:
            portfolio_rets[-1]["return"] -= tc
        prev_weights = weights.copy()
        weights = new_weights
        last_rebal = i

    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def backtest_momentum(closes, lookback=60, rebal_freq=5, n=4):
    rets = closes.pct_change().dropna()
    dates = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": float((rets.iloc[i] * weights).sum())})
        if i - last_rebal >= rebal_freq:
            mom = closes.iloc[i - 1] / closes.iloc[i - 1 - lookback] - 1
            ranked = mom.sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def safe_corr(a, b):
    if a is None or b is None:
        return float("nan")
    common = a.dropna().index.intersection(b.dropna().index)
    if len(common) < 30:
        return float("nan")
    return round(float(np.corrcoef(a.loc[common].values, b.loc[common].values)[0, 1]), 3)


def run_walk_forward(closes, volumes):
    n_total = len(closes)
    fold_results = []
    for fold in range(WF_FOLDS):
        oos_end = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break
        tr_c = closes.iloc[:oos_start]
        oo_c = closes.iloc[oos_start:oos_end]
        tr_v = volumes.iloc[:oos_start]
        if len(tr_c) < WF_TRAIN_MIN or len(oo_c) < 20:
            break
        best_sharpe, best_params = -np.inf, None
        for lb in LOOKBACKS:
            sig = compute_return_volume_corr(tr_c, tr_v, lb)
            for rf in REBALS:
                for nn in NS:
                    for d in DIRECTIONS:
                        r = backtest_factor(tr_c, sig, rf, nn, d)
                        ev = evaluate(r)
                        if ev and ev["sharpe"] > best_sharpe:
                            best_sharpe = ev["sharpe"]
                            best_params = (lb, rf, nn, d)
        if best_params is None:
            fold_results.append({"fold": fold + 1, "oos_sharpe": None})
            continue
        lb, rf, nn, d = best_params
        full_sig = compute_return_volume_corr(closes.iloc[:oos_end], volumes.iloc[:oos_end], lb)
        oos_sig = full_sig.iloc[oos_start:oos_end]
        oos_r = backtest_factor(oo_c, oos_sig, rf, nn, d)
        oos_ev = evaluate(oos_r)
        fold_results.append({
            "fold": fold + 1, "is_params": f"LB{lb}_R{rf}_N{nn}_{d}",
            "is_sharpe": round(best_sharpe, 3),
            "oos_sharpe": oos_ev["sharpe"] if oos_ev else None,
        })
    return fold_results


def run_split_half(closes, volumes):
    half = len(closes) // 2
    h1c, h2c = closes.iloc[:half], closes.iloc[half:]
    h1v, h2v = volumes.iloc[:half], volumes.iloc[half:]
    h1_sharpes, h2_sharpes = [], []
    for lb in LOOKBACKS:
        h1_sig = compute_return_volume_corr(h1c, h1v, lb)
        h2_sig = compute_return_volume_corr(h2c, h2v, lb)
        for rf in REBALS:
            for nn in NS:
                for d in DIRECTIONS:
                    e1 = evaluate(backtest_factor(h1c, h1_sig, rf, nn, d))
                    e2 = evaluate(backtest_factor(h2c, h2_sig, rf, nn, d))
                    if e1:
                        h1_sharpes.append(e1["sharpe"])
                    if e2:
                        h2_sharpes.append(e2["sharpe"])
    if not h1_sharpes or not h2_sharpes:
        return None, None, None, None
    return (round(max(h1_sharpes), 3), round(max(h2_sharpes), 3),
            round(float(np.mean(h1_sharpes)), 3), round(float(np.mean(h2_sharpes)), 3))


def main():
    print("=" * 60)
    print("  H-274: Return-Volume Correlation Factor")
    print("=" * 60)

    print("\nLoading daily data...")
    closes, volumes = load_data()
    n_assets = len(closes.columns)
    n_days = len(closes)
    print(f"Loaded {n_assets} assets, {n_days} days")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")

    total_combos = len(LOOKBACKS) * len(REBALS) * len(NS) * len(DIRECTIONS)

    # Pre-compute signals
    print("\nPre-computing return-volume correlation signals...")
    sig_cache = {}
    for lb in LOOKBACKS:
        sig_cache[lb] = compute_return_volume_corr(closes, volumes, lb)
        print(f"  LB={lb} done")

    # Stage 1: IS Parameter Scan
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")
    all_results = []
    count = 0
    for lb in LOOKBACKS:
        sig = sig_cache[lb]
        for rf in REBALS:
            for nn in NS:
                for d in DIRECTIONS:
                    count += 1
                    r = backtest_factor(closes, sig, rf, nn, d)
                    ev = evaluate(r, f"LB{lb}_R{rf}_N{nn}_{d}")
                    if ev:
                        all_results.append(ev)
    print(f"Evaluated {count} combos, {len(all_results)} valid")

    if not all_results:
        print("No valid results!")
        return

    positive = [r for r in all_results if r["sharpe"] > 0]
    is_pct = len(positive) / len(all_results) * 100
    sharpes = [r["sharpe"] for r in all_results]
    print(f"IS positive: {len(positive)}/{len(all_results)} ({is_pct:.1f}%)")
    print(f"IS Sharpe: mean={np.mean(sharpes):.3f}, median={np.median(sharpes):.3f}, best={max(sharpes):.3f}")

    # Dominant direction
    dir_counts = {d: 0 for d in DIRECTIONS}
    for r in positive:
        for d in DIRECTIONS:
            if d in r["label"]:
                dir_counts[d] += 1
    dom_dir = max(dir_counts, key=dir_counts.get)
    dom_pct = dir_counts[dom_dir] / len(positive) * 100 if positive else 0
    print(f"Dominant direction: {dom_dir} ({dom_pct:.1f}%)")

    best = max(all_results, key=lambda x: x["sharpe"])
    print(f"Best combo: {best['label']} -- Sharpe {best['sharpe']}, Ann {best['annual']}%, DD {best['dd']}%")

    # DECISION GATE
    if is_pct < 80:
        print(f"\n*** REJECTED at Stage 1: IS {is_pct:.1f}% < 80% threshold ***")
        save_results(all_results, is_pct, dom_dir, dom_pct, best, None, None, None)
        return

    # Stage 2: Walk-forward
    print(f"\n--- Stage 2: Walk-Forward ({WF_FOLDS} folds x {WF_TEST_DAYS}d) ---")
    wf = run_walk_forward(closes, volumes)
    for f in wf:
        print(f"  Fold {f['fold']}: IS={f.get('is_sharpe','N/A')}, OOS={f.get('oos_sharpe','N/A')} | {f.get('is_params','N/A')}")
    oos_sharpes = [f["oos_sharpe"] for f in wf if f.get("oos_sharpe") is not None]
    wf_positive = sum(1 for s in oos_sharpes if s > 0)
    wf_mean = np.mean(oos_sharpes) if oos_sharpes else 0
    print(f"WF positive: {wf_positive}/{len(oos_sharpes)}, mean OOS Sharpe: {wf_mean:.3f}")

    # Stage 3: Split-half
    print("\n--- Stage 3: Split-Half ---")
    h1_best, h2_best, h1_mean, h2_mean = run_split_half(closes, volumes)
    print(f"H1 best={h1_best}, H2 best={h2_best}")
    print(f"H1 mean={h1_mean}, H2 mean={h2_mean}")

    # Stage 4: Correlation
    print("\n--- Stage 4: Correlation with H-012 (Momentum) ---")
    mom_rets = backtest_momentum(closes)
    parts = best["label"].split("_")
    lb = int(parts[0][2:])
    rf = int(parts[1][1:])
    nn = int(parts[2][1:])
    d = "high_corr_long" if "high_corr_long" in best["label"] else "low_corr_long"
    sig = sig_cache[lb]
    best_rets = backtest_factor(closes, sig, rf, nn, d)
    corr_h012 = safe_corr(best_rets, mom_rets)
    print(f"Correlation with H-012: {corr_h012}")

    save_results(all_results, is_pct, dom_dir, dom_pct, best, wf, (h1_best, h2_best, h1_mean, h2_mean), corr_h012)


def save_results(all_results, is_pct, dom_dir, dom_pct, best, wf, split_half, corr_h012):
    out = {
        "hypothesis": "H-274",
        "name": "Return-Volume Correlation Factor",
        "is_positive_pct": round(is_pct, 1),
        "is_total": len(all_results),
        "dom_direction": dom_dir,
        "dom_pct": round(dom_pct, 1),
        "best": best,
        "mean_sharpe": round(float(np.mean([r["sharpe"] for r in all_results])), 3),
        "walk_forward": wf,
        "split_half": split_half,
        "corr_h012": corr_h012,
    }
    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
