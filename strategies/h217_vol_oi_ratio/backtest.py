#!/usr/bin/env python3
"""
H-217: Volume/OI Ratio (Speculative Activity Factor)

Idea: Volume relative to open interest measures speculative activity.
High volume/OI = short-term speculative churning (day traders).
Low volume/OI = sticky positioning (longer-term holders).

Hypothesis: Long low-V/OI assets (sticky, less noise), short high-V/OI
(speculative, noisy). Alternatively, high V/OI could signal incoming
directional conviction.

This is distinct from:
- H-044 (OI-price divergence — direction of OI vs price)
- H-085 (turnover velocity — volume relative to own history)
- H-193 (OI-price momentum divergence — momentum alignment)
- H-197 (Amihud illiquidity — price impact per dollar volume)
Volume/OI is a pure positioning characteristic, not a price signal.

Parameter grid:
  Lookback (avg V/OI): [5, 10, 15, 20, 30]
  Rebal freq: [3, 5, 7]
  N         : [3, 4]
  Direction : [low_voi_long, high_voi_long]
  Total: 5 x 3 x 2 x 2 = 60 combos

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

LOOKBACKS  = [5, 10, 15, 20, 30]
REBALS     = [3, 5, 7]
NS         = [3, 4]
DIRECTIONS = ["low_voi_long", "high_voi_long"]

COST_PER_SIDE = 0.0005

WF_FOLDS     = 6
WF_TEST_DAYS = 90
WF_TRAIN_MIN = 120


def load_daily_data():
    """Load closes, volumes, and OI data."""
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

    # Load OI data from per-asset parquet files
    oi_dir = data_dir / "oi"
    oi_dict = {}
    if oi_dir.exists():
        for sym in ASSETS_ALL:
            base = sym.split("/")[0]
            oi_path = oi_dir / f"{base}_oi_1d.parquet"
            if oi_path.exists():
                df_oi = pd.read_parquet(oi_path)
                if "openInterest" in df_oi.columns and len(df_oi) > 100:
                    oi_dict[sym] = df_oi["openInterest"]
    oi_df = None
    if oi_dict:
        oi_df = pd.DataFrame(oi_dict)
        oi_df.index = oi_df.index.tz_localize(None) if oi_df.index.tzinfo is not None else oi_df.index
        oi_df = oi_df.sort_index().ffill()

    return closes, volumes, oi_df


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


def backtest_vol_oi(closes, volumes, oi_df, lookback, rebal_freq, n, direction):
    cols = list(closes.columns)
    if oi_df is None or len(cols) < 2 * n:
        return None
    returns = closes.pct_change().dropna()
    dates = returns.index
    warmup = lookback + 5
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=cols)
    prev_weights = pd.Series(0.0, index=cols)

    # Align OI to returns dates
    oi_aligned = oi_df.reindex(dates).ffill()

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": float(day_ret)})
        if i - last_rebal < rebal_freq:
            continue

        # Compute avg V/OI ratio over lookback
        vol_window = volumes.reindex(dates).iloc[i - lookback: i]
        oi_window = oi_aligned.iloc[i - lookback: i]

        if len(vol_window) < lookback or len(oi_window) < lookback:
            continue

        voi_scores = {}
        for sym in cols:
            if sym not in oi_aligned.columns:
                continue
            v = vol_window[sym].values if sym in vol_window.columns else None
            o = oi_window[sym].values if sym in oi_window.columns else None
            if v is None or o is None:
                continue
            # Compute dollar volume / OI
            # Use close price to convert to dollar terms (already in dollar volume for volume)
            valid = (o > 0) & np.isfinite(v) & np.isfinite(o)
            if valid.sum() < lookback // 2:
                continue
            ratio = np.mean(v[valid] / o[valid])
            if not np.isfinite(ratio):
                continue
            voi_scores[sym] = ratio

        if len(voi_scores) < 2 * n:
            continue

        ranked = pd.Series(voi_scores).sort_values(ascending=True)  # low V/OI first

        if direction == "low_voi_long":
            longs = ranked.index[:n]
            shorts = ranked.index[-n:]
        else:
            longs = ranked.index[-n:]
            shorts = ranked.index[:n]

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


def run_walk_forward(closes, volumes, oi_df):
    n_total = len(closes)
    fold_results = []
    for fold in range(WF_FOLDS):
        oos_end = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break
        tr_c, tr_v = closes.iloc[:oos_start], volumes.iloc[:oos_start]
        oo_c, oo_v = closes.iloc[oos_start:oos_end], volumes.iloc[oos_start:oos_end]
        # OI uses the same full df (ffill handles alignment)
        if len(tr_c) < WF_TRAIN_MIN or len(oo_c) < 20:
            break
        best_sharpe, best_params = -np.inf, None
        for lb in LOOKBACKS:
            for rf in REBALS:
                for nn in NS:
                    for d in DIRECTIONS:
                        r = backtest_vol_oi(tr_c, tr_v, oi_df, lb, rf, nn, d)
                        ev = evaluate(r)
                        if ev and ev["sharpe"] > best_sharpe:
                            best_sharpe = ev["sharpe"]
                            best_params = (lb, rf, nn, d)
        if best_params is None:
            fold_results.append({"fold": fold + 1, "oos_sharpe": None})
            continue
        lb, rf, nn, d = best_params
        oos_r = backtest_vol_oi(oo_c, oo_v, oi_df, lb, rf, nn, d)
        oos_ev = evaluate(oos_r)
        fold_results.append({
            "fold": fold + 1, "is_params": f"LB{lb}_R{rf}_N{nn}_{d}",
            "is_sharpe": round(best_sharpe, 3),
            "oos_sharpe": oos_ev["sharpe"] if oos_ev else None,
        })
    return fold_results


def run_split_half(closes, volumes, oi_df):
    half = len(closes) // 2
    h1c, h1v = closes.iloc[:half], volumes.iloc[:half]
    h2c, h2v = closes.iloc[half:], volumes.iloc[half:]
    h1_sharpes, h2_sharpes = [], []
    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                for d in DIRECTIONS:
                    e1 = evaluate(backtest_vol_oi(h1c, h1v, oi_df, lb, rf, nn, d))
                    e2 = evaluate(backtest_vol_oi(h2c, h2v, oi_df, lb, rf, nn, d))
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
    print("  H-217: Volume/OI Ratio (Speculative Activity Factor)")
    print("=" * 60)

    print("\nLoading daily data...")
    closes, volumes, oi_df = load_daily_data()
    n_assets, n_days = len(closes.columns), len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")

    if oi_df is None or len(oi_df) < 100:
        print("ERROR: Insufficient OI data. Cannot run this backtest.")
        result = {
            "hypothesis": "H-217", "name": "Volume/OI Ratio",
            "status": "REJECTED", "reason": "Insufficient OI data",
        }
        with open(Path(__file__).parent / "results.json", "w") as f:
            json.dump(result, f, indent=2)
        return

    oi_assets = [c for c in oi_df.columns if c in closes.columns]
    print(f"OI data: {len(oi_df)} rows, {len(oi_assets)} matching assets")
    print(f"OI assets: {oi_assets}")

    total_combos = len(LOOKBACKS) * len(REBALS) * len(NS) * len(DIRECTIONS)

    # Stage 1: IS Parameter Scan
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")
    all_results = []
    count = 0
    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                for d in DIRECTIONS:
                    count += 1
                    r = backtest_vol_oi(closes, volumes, oi_df, lb, rf, nn, d)
                    ev = evaluate(r, f"LB{lb}_R{rf}_N{nn}_{d}")
                    if ev:
                        ev["lb"], ev["rf"], ev["n"], ev["dir"] = lb, rf, nn, d
                        all_results.append(ev)
        print(f"  {count}/{total_combos} combos done...")

    if not all_results:
        print("No valid results! REJECTED.")
        result = {
            "hypothesis": "H-217", "name": "Volume/OI Ratio",
            "status": "REJECTED", "reason": "No valid backtest results",
        }
        with open(Path(__file__).parent / "results.json", "w") as f:
            json.dump(result, f, indent=2)
        return

    df_res = pd.DataFrame(all_results)
    n_pos = int((df_res["sharpe"] > 0).sum())
    pct_pos = n_pos / len(df_res) * 100
    mean_shp = float(df_res["sharpe"].mean())

    print(f"\n  Valid combos: {len(df_res)}/{total_combos}")
    print(f"  Positive Sharpe: {n_pos}/{len(df_res)} ({pct_pos:.1f}%)")
    print(f"  Mean Sharpe: {mean_shp:.3f}")

    for d in DIRECTIONS:
        mask = df_res["dir"] == d
        sub = df_res[mask]
        n_p = int((sub["sharpe"] > 0).sum())
        print(f"  {d}: {n_p}/{len(sub)} positive ({n_p/len(sub)*100:.1f}%), mean {sub['sharpe'].mean():.3f}")

    df_sorted = df_res.sort_values("sharpe", ascending=False)
    print(f"\n  Top 5:")
    for _, row in df_sorted.head(5).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}_{row['dir']}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    best_row = df_sorted.iloc[0]
    best_lb, best_rf, best_n = int(best_row["lb"]), int(best_row["rf"]), int(best_row["n"])
    best_dir = best_row["dir"]

    is_pass = pct_pos >= 80.0
    if not is_pass:
        # Check dominant direction
        for d in DIRECTIONS:
            mask = df_res["dir"] == d
            sub = df_res[mask]
            p = int((sub["sharpe"] > 0).sum())
            pct = p / len(sub) * 100 if len(sub) > 0 else 0
            if pct >= 80:
                print(f"\n  Note: {d} alone passes IS with {pct:.1f}%")

        print(f"\n*** FAIL IS: {pct_pos:.1f}% positive < 80% threshold. REJECTED. ***")
        result = {
            "hypothesis": "H-217", "name": "Volume/OI Ratio",
            "status": "REJECTED", "reason": f"IS {pct_pos:.1f}% < 80%",
            "is_positive_rate": round(pct_pos, 1), "is_mean_sharpe": round(mean_shp, 3),
            "best_params": {"lookback": best_lb, "rebal": best_rf, "n": best_n, "direction": best_dir},
            "best_sharpe": round(float(best_row["sharpe"]), 3),
            "n_assets": n_assets, "n_days": n_days,
            "oi_rows": len(oi_df), "oi_assets": len(oi_assets),
        }
        with open(Path(__file__).parent / "results.json", "w") as f:
            json.dump(result, f, indent=2)
        return

    # Stage 2: Walk-Forward
    print(f"\n--- Stage 2: Walk-Forward ({WF_FOLDS} folds, {WF_TEST_DAYS}d OOS) ---")
    wf = run_walk_forward(closes, volumes, oi_df)
    wf_sharpes = [r["oos_sharpe"] for r in wf if r["oos_sharpe"] is not None]
    wf_n_pos = sum(1 for s in wf_sharpes if s > 0)
    wf_mean = float(np.mean(wf_sharpes)) if wf_sharpes else 0
    for r in wf:
        print(f"  Fold {r['fold']}: OOS Sharpe = {r.get('oos_sharpe', 'N/A')}")
    print(f"  WF positive: {wf_n_pos}/{len(wf_sharpes)}, mean OOS: {wf_mean:.3f}")
    wf_pass = wf_n_pos >= 4 and wf_mean > 0

    # Stage 3: Split-Half
    print("\n--- Stage 3: Split-Half ---")
    h1_best, h2_best, h1_mean, h2_mean = run_split_half(closes, volumes, oi_df)
    print(f"  H1 best={h1_best}, H2 best={h2_best}")
    print(f"  H1 mean={h1_mean}, H2 mean={h2_mean}")
    sh_pass = h1_best is not None and h2_best is not None and h1_best > 0 and h2_best > 0

    # Stage 4: Correlation
    print("\n--- Stage 4: Correlation ---")
    best_r = backtest_vol_oi(closes, volumes, oi_df, best_lb, best_rf, best_n, best_dir)
    mom_r = backtest_momentum(closes)
    corr_h012 = safe_corr(best_r, mom_r)
    print(f"  Corr with H-012 (momentum): {corr_h012}")
    corr_pass = abs(corr_h012) < 0.50 if not np.isnan(corr_h012) else True

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
        "hypothesis": "H-217", "name": "Volume/OI Ratio",
        "status": status, "reason": reason,
        "is_positive_rate": round(pct_pos, 1), "is_mean_sharpe": round(mean_shp, 3),
        "best_params": {"lookback": best_lb, "rebal": best_rf, "n": best_n, "direction": best_dir},
        "best_sharpe": round(float(best_row["sharpe"]), 3),
        "best_annual": round(float(best_row["annual"]), 1),
        "best_dd": round(float(best_row["dd"]), 1),
        "wf_folds": wf, "wf_positive": wf_n_pos, "wf_total": len(wf_sharpes), "wf_mean": round(wf_mean, 3),
        "split_half": {"h1_best": h1_best, "h2_best": h2_best, "h1_mean": h1_mean, "h2_mean": h2_mean},
        "corr_h012": corr_h012, "n_assets": n_assets, "n_days": n_days,
        "oi_rows": len(oi_df), "oi_assets": len(oi_assets),
    }
    with open(Path(__file__).parent / "results.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nResults written to results.json")


if __name__ == "__main__":
    main()
