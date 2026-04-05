#!/usr/bin/env python3
"""
H-256: Volume-Confirmed Return Factor

Idea: Weight daily returns by relative volume to create a "volume-confirmed" return signal.
Days with above-average volume contribute more; low-volume days contribute less.
Rank cross-sectionally by this volume-weighted return.

Different from:
- H-012 (Momentum): equal-weighted daily returns, ignores volume
- H-021 (Volume Momentum): ranks by volume change, not volume-weighted *returns*
- H-175 (Money Flow): uses MFI-style buy/sell volume decomposition
- H-219 (Up-Volume Ratio): counts up-volume days, this weights returns by volume
- H-215 (Dollar Volume Trend): slope of dollar volume, not volume-weighted returns

The thesis: price moves on high volume are more "real" and persistent than moves
on thin volume. Volume-confirmation should filter out noise moves.

Signal construction:
  1. For each day: vol_weight = volume / rolling_avg_volume(N)
  2. Confirmed_return(t) = sum(ret_i * vol_weight_i) for i in lookback window
  3. Rank XS: long high confirmed return, short low confirmed return.

Parameter grid:
  Lookback: [10, 14, 21, 30, 60]
  Vol avg window: [10, 20]   (for vol normalization)
  Rebal freq: [3, 5, 7]
  N: [3, 4]
  Direction: [high_vcr_long, low_vcr_long]
  Total: 5 x 2 x 3 x 2 x 2 = 120 combos
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

LOOKBACKS = [10, 14, 21, 30, 60]
VOL_WINDOWS = [10, 20]
REBALS = [3, 5, 7]
NS = [3, 4]
DIRECTIONS = ["high_vcr_long", "low_vcr_long"]

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
    volumes = pd.DataFrame(volumes).reindex(closes.index).ffill().fillna(0)
    return closes, volumes


def compute_vol_confirmed_return(closes, volumes, lookback, vol_window):
    """Compute volume-confirmed return for each asset."""
    rets = closes.pct_change().dropna()
    cols = list(rets.columns)

    # Relative volume: volume / rolling_avg
    rel_vol = volumes / volumes.rolling(vol_window, min_periods=max(vol_window // 2, 5)).mean()
    rel_vol = rel_vol.reindex(rets.index).fillna(1.0)

    # Weighted return: sum of ret * rel_vol over lookback
    vcr_arr = np.full((len(rets), len(cols)), np.nan)
    for j, col in enumerate(cols):
        r_vals = rets[col].values
        v_vals = rel_vol[col].values
        weighted = r_vals * v_vals
        for i in range(lookback, len(r_vals)):
            vcr_arr[i, j] = weighted[i - lookback:i].sum()

    return pd.DataFrame(vcr_arr, index=rets.index, columns=cols)


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
    cols = list(signal_df.columns)
    if len(cols) < 2 * n:
        return None
    returns = closes[cols].pct_change().dropna()
    signal_df = signal_df.reindex(returns.index)
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
        if direction == "high_vcr_long":
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
        tr_v = volumes.iloc[:oos_start]
        oo_c = closes.iloc[oos_start:oos_end]
        if len(tr_c) < WF_TRAIN_MIN or len(oo_c) < 20:
            break
        best_sharpe, best_params = -np.inf, None
        for lb in LOOKBACKS:
            for vw in VOL_WINDOWS:
                sig = compute_vol_confirmed_return(tr_c, tr_v, lb, vw)
                for rf in REBALS:
                    for nn in NS:
                        for d in DIRECTIONS:
                            r = backtest_factor(tr_c, sig, rf, nn, d)
                            ev = evaluate(r)
                            if ev and ev["sharpe"] > best_sharpe:
                                best_sharpe = ev["sharpe"]
                                best_params = (lb, vw, rf, nn, d)
        if best_params is None:
            fold_results.append({"fold": fold + 1, "oos_sharpe": None})
            continue
        lb, vw, rf, nn, d = best_params
        full_sig = compute_vol_confirmed_return(closes.iloc[:oos_end], volumes.iloc[:oos_end], lb, vw)
        oos_sig = full_sig.iloc[oos_start:oos_end]
        oos_r = backtest_factor(oo_c, oos_sig, rf, nn, d)
        oos_ev = evaluate(oos_r)
        fold_results.append({
            "fold": fold + 1, "is_params": f"LB{lb}_VW{vw}_R{rf}_N{nn}_{d}",
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
        for vw in VOL_WINDOWS:
            h1_sig = compute_vol_confirmed_return(h1c, h1v, lb, vw)
            h2_sig = compute_vol_confirmed_return(h2c, h2v, lb, vw)
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
    print("  H-256: Volume-Confirmed Return Factor")
    print("=" * 60)

    print("\nLoading daily data...")
    closes, volumes = load_data()
    n_assets, n_days = len(closes.columns), len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")

    total_combos = len(LOOKBACKS) * len(VOL_WINDOWS) * len(REBALS) * len(NS) * len(DIRECTIONS)

    # Pre-compute VCR for all param combos
    print("\nPre-computing volume-confirmed returns...")
    vcr_cache = {}
    for lb in LOOKBACKS:
        for vw in VOL_WINDOWS:
            key = (lb, vw)
            vcr_cache[key] = compute_vol_confirmed_return(closes, volumes, lb, vw)
            print(f"  LB={lb}, VW={vw} done")

    # Stage 1: IS Parameter Scan
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")
    all_results = []
    count = 0
    for lb in LOOKBACKS:
        for vw in VOL_WINDOWS:
            sig = vcr_cache[(lb, vw)]
            for rf in REBALS:
                for nn in NS:
                    for d in DIRECTIONS:
                        count += 1
                        r = backtest_factor(closes, sig, rf, nn, d)
                        ev = evaluate(r, f"LB{lb}_VW{vw}_R{rf}_N{nn}_{d}")
                        if ev:
                            ev["lb"], ev["vw"], ev["rf"], ev["n"], ev["dir"] = lb, vw, rf, nn, d
                            all_results.append(ev)
            if count % 24 == 0:
                print(f"  {count}/{total_combos} combos done...")

    if not all_results:
        print("No valid results! REJECTED.")
        return

    df_res = pd.DataFrame(all_results)
    n_pos = int((df_res["sharpe"] > 0).sum())
    pct_pos = n_pos / len(df_res) * 100
    mean_shp = float(df_res["sharpe"].mean())

    for d in DIRECTIONS:
        sub = df_res[df_res["dir"] == d]
        d_pos = int((sub["sharpe"] > 0).sum())
        d_pct = d_pos / len(sub) * 100 if len(sub) > 0 else 0
        d_mean = float(sub["sharpe"].mean()) if len(sub) > 0 else 0
        print(f"  {d}: {d_pos}/{len(sub)} positive ({d_pct:.1f}%), mean Sharpe {d_mean:.3f}")

    print(f"\n  Overall: {n_pos}/{len(df_res)} ({pct_pos:.1f}%), mean Sharpe {mean_shp:.3f}")

    best_dir = None
    best_dir_pct = 0
    for d in DIRECTIONS:
        sub = df_res[df_res["dir"] == d]
        d_pct = int((sub["sharpe"] > 0).sum()) / len(sub) * 100 if len(sub) > 0 else 0
        if d_pct > best_dir_pct:
            best_dir_pct = d_pct
            best_dir = d

    df_sorted = df_res.sort_values("sharpe", ascending=False)
    print(f"\n  Top 5:")
    for _, row in df_sorted.head(5).iterrows():
        print(f"    LB{int(row['lb'])}_VW{int(row['vw'])}_R{int(row['rf'])}_N{int(row['n'])}_{row['dir']}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    best_row = df_sorted.iloc[0]

    is_pass = pct_pos >= 80.0
    dom_dir_pass = best_dir_pct >= 80.0

    if not is_pass and not dom_dir_pass:
        print(f"\n*** FAIL IS: overall {pct_pos:.1f}%, best dir {best_dir} {best_dir_pct:.1f}% < 80%. REJECTED. ***")
        result = {
            "hypothesis": "H-256", "name": "Volume-Confirmed Return Factor",
            "status": "REJECTED", "reason": f"IS {pct_pos:.1f}% / dom dir {best_dir_pct:.1f}% < 80%",
            "is_positive_rate": round(pct_pos, 1), "is_mean_sharpe": round(mean_shp, 3),
            "best_dir": best_dir, "best_dir_pct": round(best_dir_pct, 1),
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

    # Stage 4: Correlation
    print("\n--- Stage 4: Correlation with H-012 ---")
    best_sig = vcr_cache[(int(best_row["lb"]), int(best_row["vw"]))]
    best_r = backtest_factor(closes, best_sig, int(best_row["rf"]),
                             int(best_row["n"]), best_row["dir"])
    mom_r = backtest_momentum(closes)
    corr_h012 = safe_corr(best_r, mom_r)
    print(f"  Corr with H-012: {corr_h012}")
    corr_pass = abs(corr_h012) < 0.50 if not np.isnan(corr_h012) else True

    all_pass = (is_pass or dom_dir_pass) and wf_pass and sh_pass and corr_pass
    status = "CONFIRMED" if all_pass else "REJECTED"
    reason_parts = []
    if not (is_pass or dom_dir_pass):
        reason_parts.append(f"IS {pct_pos:.1f}%")
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
        "hypothesis": "H-256", "name": "Volume-Confirmed Return Factor",
        "status": status, "reason": reason,
        "is_positive_rate": round(pct_pos, 1), "is_mean_sharpe": round(mean_shp, 3),
        "best_dir": best_dir, "best_dir_pct": round(best_dir_pct, 1),
        "best_params": {"lookback": int(best_row["lb"]), "vol_window": int(best_row["vw"]),
                        "rebal": int(best_row["rf"]), "n": int(best_row["n"]), "dir": best_row["dir"]},
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
