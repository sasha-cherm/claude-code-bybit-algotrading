#!/usr/bin/env python3
"""
H-215: Dollar Volume Trend Factor

Idea: Compute the slope of log(dollar_volume) over a lookback window for each
asset. Assets with increasing dollar volume have growing interest/institutional
participation; those with declining dollar volume are losing interest.
Long increasing, short decreasing.

Differs from H-021 (volume momentum = ratio of short/long volume) and H-031
(size = level of dollar volume). This captures the *trend direction* of dollar
volume using linear regression slope.

Signal construction (per asset, per rebalance day):
  1. Compute daily dollar volume = close * volume for all 14 assets.
  2. Over a lookback window L, fit OLS slope to log(dollar_volume).
  3. Rank assets by slope. Long top-N (steepest increase), short bottom-N.
  4. Dollar-neutral, equal-weight within each leg.

Parameter grid:
  Lookback  : [10, 15, 20, 30, 40, 60]
  Rebal freq: [3, 5, 7]
  N         : [3, 4]
  Total: 6 x 3 x 2 = 36 combos

Transaction costs: 10 bps round-trip (5 bps per side) on turnover.
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
REBALS    = [3, 5, 7]
NS        = [3, 4]

COST_PER_SIDE = 0.0005

WF_FOLDS     = 6
WF_TEST_DAYS = 90
WF_TRAIN_MIN = 120


def load_daily_data():
    data_dir = ROOT / "data"
    closes_d, volumes_d = {}, {}
    for sym in ASSETS_ALL:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if not all(c in df.columns for c in ["close", "volume"]):
            continue
        if len(df) < 200:
            continue
        closes_d[sym] = df["close"]
        volumes_d[sym] = df["volume"]
    closes = pd.DataFrame(closes_d)
    volumes = pd.DataFrame(volumes_d)
    common = closes.index.intersection(volumes.index)
    closes = closes.loc[common].dropna(how="all").ffill().dropna()
    volumes = volumes.loc[common].reindex(closes.index).ffill().dropna()
    closes.index = closes.index.tz_localize(None) if closes.index.tzinfo is not None else closes.index
    volumes.index = volumes.index.tz_localize(None) if volumes.index.tzinfo is not None else volumes.index
    return closes, volumes


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


def _log_dv_slope(dv_window):
    """Compute OLS slope of log(dollar_volume) for each asset. Returns Series."""
    log_dv = np.log(dv_window.clip(lower=1))
    n = len(log_dv)
    x = np.arange(n, dtype=float)
    x_dm = x - x.mean()
    denom = (x_dm ** 2).sum()
    if denom < 1e-12:
        return pd.Series(np.nan, index=dv_window.columns)
    slopes = {}
    for sym in dv_window.columns:
        y = log_dv[sym].values
        if np.isnan(y).any():
            slopes[sym] = np.nan
            continue
        y_dm = y - y.mean()
        slopes[sym] = float(np.dot(x_dm, y_dm) / denom)
    return pd.Series(slopes)


def backtest_dvol_trend(closes, volumes, lookback, rebal_freq, n):
    cols = list(closes.columns)
    if len(cols) < 2 * n:
        return None
    returns = closes.pct_change().dropna()
    dv = (closes * volumes).reindex(returns.index).ffill()
    dates = returns.index
    warmup = lookback + 5
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=cols)
    prev_weights = pd.Series(0.0, index=cols)

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": float(day_ret)})
        if i - last_rebal < rebal_freq:
            continue
        dv_window = dv.iloc[i - lookback: i]
        if len(dv_window) < lookback:
            continue
        slopes = _log_dv_slope(dv_window)
        valid = slopes.dropna()
        if len(valid) < 2 * n:
            continue
        ranked = valid.sort_values(ascending=False)
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
        tr_c, tr_v = closes.iloc[:oos_start], volumes.iloc[:oos_start]
        oo_c, oo_v = closes.iloc[oos_start:oos_end], volumes.iloc[oos_start:oos_end]
        if len(tr_c) < WF_TRAIN_MIN or len(oo_c) < 20:
            break
        best_sharpe, best_params = -np.inf, None
        for lb in LOOKBACKS:
            for rf in REBALS:
                for nn in NS:
                    r = backtest_dvol_trend(tr_c, tr_v, lb, rf, nn)
                    ev = evaluate(r)
                    if ev and ev["sharpe"] > best_sharpe:
                        best_sharpe = ev["sharpe"]
                        best_params = (lb, rf, nn)
        if best_params is None:
            fold_results.append({"fold": fold + 1, "oos_sharpe": None})
            continue
        lb, rf, nn = best_params
        oos_r = backtest_dvol_trend(oo_c, oo_v, lb, rf, nn)
        oos_ev = evaluate(oos_r)
        fold_results.append({
            "fold": fold + 1, "is_params": f"LB{lb}_R{rf}_N{nn}",
            "is_sharpe": round(best_sharpe, 3),
            "oos_sharpe": oos_ev["sharpe"] if oos_ev else None,
        })
    return fold_results


def run_split_half(closes, volumes):
    half = len(closes) // 2
    h1c, h1v = closes.iloc[:half], volumes.iloc[:half]
    h2c, h2v = closes.iloc[half:], volumes.iloc[half:]
    h1_sharpes, h2_sharpes = [], []
    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                e1 = evaluate(backtest_dvol_trend(h1c, h1v, lb, rf, nn))
                e2 = evaluate(backtest_dvol_trend(h2c, h2v, lb, rf, nn))
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
    print("  H-215: Dollar Volume Trend Factor")
    print("=" * 60)

    print("\nLoading daily OHLCV data...")
    closes, volumes = load_daily_data()
    n_assets, n_days = len(closes.columns), len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")

    total_combos = len(LOOKBACKS) * len(REBALS) * len(NS)

    # Stage 1: IS Parameter Scan
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")
    all_results = []
    count = 0
    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                count += 1
                r = backtest_dvol_trend(closes, volumes, lb, rf, nn)
                ev = evaluate(r, f"LB{lb}_R{rf}_N{nn}")
                if ev:
                    ev["lb"], ev["rf"], ev["n"] = lb, rf, nn
                    all_results.append(ev)
        print(f"  {count}/{total_combos} combos done...")

    if not all_results:
        print("No valid results! REJECTED.")
        return

    df_res = pd.DataFrame(all_results)
    n_pos = int((df_res["sharpe"] > 0).sum())
    pct_pos = n_pos / len(df_res) * 100
    mean_shp = float(df_res["sharpe"].mean())

    print(f"\n  Valid combos: {len(df_res)}/{total_combos}")
    print(f"  Positive Sharpe: {n_pos}/{len(df_res)} ({pct_pos:.1f}%)")
    print(f"  Mean Sharpe: {mean_shp:.3f}")

    df_sorted = df_res.sort_values("sharpe", ascending=False)
    print(f"\n  Top 5:")
    for _, row in df_sorted.head(5).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    best_row = df_sorted.iloc[0]
    best_lb, best_rf, best_n = int(best_row["lb"]), int(best_row["rf"]), int(best_row["n"])

    is_pass = pct_pos >= 80.0
    if not is_pass:
        print(f"\n*** FAIL IS: {pct_pos:.1f}% positive < 80% threshold. REJECTED. ***")
        result = {
            "hypothesis": "H-215", "name": "Dollar Volume Trend",
            "status": "REJECTED", "reason": f"IS {pct_pos:.1f}% < 80%",
            "is_positive_rate": round(pct_pos, 1), "is_mean_sharpe": round(mean_shp, 3),
            "best_params": {"lookback": best_lb, "rebal": best_rf, "n": best_n},
            "best_sharpe": round(float(best_row["sharpe"]), 3),
            "n_assets": n_assets, "n_days": n_days,
        }
        with open(Path(__file__).parent / "results.json", "w") as f:
            json.dump(result, f, indent=2)
        return

    # Stage 2: Walk-Forward
    print(f"\n--- Stage 2: Walk-Forward ({WF_FOLDS} folds, {WF_TEST_DAYS}d OOS) ---")
    wf = run_walk_forward(closes, volumes)
    wf_sharpes = [r["oos_sharpe"] for r in wf if r["oos_sharpe"] is not None]
    wf_n_pos = sum(1 for s in wf_sharpes if s > 0)
    wf_mean = float(np.mean(wf_sharpes)) if wf_sharpes else 0
    for r in wf:
        print(f"  Fold {r['fold']}: OOS Sharpe = {r.get('oos_sharpe', 'N/A')}")
    print(f"  WF positive: {wf_n_pos}/{len(wf_sharpes)}, mean OOS: {wf_mean:.3f}")
    wf_pass = wf_n_pos >= 4 and wf_mean > 0

    # Stage 3: Split-Half
    print("\n--- Stage 3: Split-Half ---")
    h1_best, h2_best, h1_mean, h2_mean = run_split_half(closes, volumes)
    print(f"  H1 best={h1_best}, H2 best={h2_best}")
    print(f"  H1 mean={h1_mean}, H2 mean={h2_mean}")
    sh_pass = h1_best is not None and h2_best is not None and h1_best > 0 and h2_best > 0

    # Stage 4: Correlation with H-012
    print("\n--- Stage 4: Correlation with H-012 ---")
    best_r = backtest_dvol_trend(closes, volumes, best_lb, best_rf, best_n)
    mom_r = backtest_momentum(closes)
    corr_h012 = safe_corr(best_r, mom_r)
    print(f"  Corr with H-012: {corr_h012}")
    corr_pass = abs(corr_h012) < 0.50 if not np.isnan(corr_h012) else True

    # Final verdict
    all_pass = is_pass and wf_pass and sh_pass and corr_pass
    status = "CONFIRMED" if all_pass else "REJECTED"
    reason_parts = []
    if not wf_pass:
        reason_parts.append(f"WF {wf_n_pos}/{len(wf_sharpes)}")
    if not sh_pass:
        reason_parts.append("split-half fails")
    if not corr_pass:
        reason_parts.append(f"corr {corr_h012}")
    reason = "; ".join(reason_parts) if reason_parts else "all stages passed"

    print(f"\n{'='*60}")
    print(f"  RESULT: {status} — {reason}")
    print(f"{'='*60}")

    result = {
        "hypothesis": "H-215", "name": "Dollar Volume Trend",
        "status": status, "reason": reason,
        "is_positive_rate": round(pct_pos, 1), "is_mean_sharpe": round(mean_shp, 3),
        "best_params": {"lookback": best_lb, "rebal": best_rf, "n": best_n},
        "best_sharpe": round(float(best_row["sharpe"]), 3),
        "best_annual": round(float(best_row["annual"]), 1),
        "best_dd": round(float(best_row["dd"]), 1),
        "wf_folds": wf, "wf_positive": wf_n_pos, "wf_total": len(wf_sharpes), "wf_mean": round(wf_mean, 3),
        "split_half": {"h1_best": h1_best, "h2_best": h2_best, "h1_mean": h1_mean, "h2_mean": h2_mean},
        "corr_h012": corr_h012, "n_assets": n_assets, "n_days": n_days,
    }
    with open(Path(__file__).parent / "results.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nResults written to results.json")


if __name__ == "__main__":
    main()
