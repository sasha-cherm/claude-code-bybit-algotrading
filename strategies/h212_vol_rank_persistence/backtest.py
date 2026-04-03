#!/usr/bin/env python3
"""
H-212: Relative Volume Rank Persistence

Idea: Assets whose daily dollar-volume rank (within the cross-section) is
autocorrelated over a lookback window tend to outperform those with erratic
volume rankings.  High rank-autocorrelation => stable institutional interest;
low rank-autocorrelation => speculative / event-driven flows.

Signal construction (per asset, per rebalance day):
  1. Compute daily dollar volume = close * volume for all 14 assets.
  2. Cross-sectionally rank by dollar volume each day (rank 1 = lowest).
  3. Over a lookback window L, compute the lag-1 autocorrelation of each
     asset's rank series.
  4. Rank by this persistence score.  Long top-N, short bottom-N.
  5. Dollar-neutral, equal-weight within each leg.

Parameter grid:
  Lookback  : [10, 15, 20, 30, 40]
  Rebal freq: [3, 5, 7]
  N         : [3, 4]
  Total: 5 x 3 x 2 = 30 combos

Transaction costs: 10 bps round-trip (5 bps per side) on turnover.

Validation (4-stage):
  1. IS  : >= 80% of combos must have positive Sharpe
  2. WF  : 6 folds (270d train / 90d test), >= 4/6 positive OOS, mean OOS > 0
  3. SH  : Split-half — best Sharpe > 0 in both halves
  4. Corr: |corr| with H-012 (momentum) reported; threshold < 0.50
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

# Parameter grid
LOOKBACKS = [10, 15, 20, 30, 40]
REBALS    = [3, 5, 7]
NS        = [3, 4]

# Transaction cost: 5 bps per side (10 bps round-trip)
COST_PER_SIDE = 0.0005

# Walk-forward config
WF_FOLDS     = 6
WF_TEST_DAYS = 90
WF_TRAIN_MIN = 120


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_daily_data():
    """Load 1d parquet files; return (closes, volumes) DataFrames."""
    data_dir = ROOT / "data"
    closes_d = {}
    volumes_d = {}
    for sym in ASSETS_ALL:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if not path.exists():
            print(f"  WARNING: {path.name} not found — skipping {sym}")
            continue
        df = pd.read_parquet(path)
        if not all(c in df.columns for c in ["close", "volume"]):
            print(f"  WARNING: {sym} missing close/volume columns — skipping")
            continue
        if len(df) < 200:
            print(f"  WARNING: {sym} has only {len(df)} rows — skipping")
            continue
        closes_d[sym]  = df["close"]
        volumes_d[sym] = df["volume"]

    closes  = pd.DataFrame(closes_d)
    volumes = pd.DataFrame(volumes_d)

    # Align on common dates
    common = closes.index.intersection(volumes.index)
    closes  = closes.loc[common].dropna(how="all").ffill().dropna()
    volumes = volumes.loc[common].reindex(closes.index).ffill().dropna()

    # Remove timezone info for clean display
    closes.index  = closes.index.tz_localize(None) if closes.index.tzinfo is not None else closes.index
    volumes.index = volumes.index.tz_localize(None) if volumes.index.tzinfo is not None else volumes.index

    return closes, volumes


# ---------------------------------------------------------------------------
# Evaluation helper
# ---------------------------------------------------------------------------

def evaluate(rets, label=""):
    if rets is None or len(rets) < 30:
        return None
    ann  = rets.mean() * 365
    vol  = rets.std() * np.sqrt(365)
    shp  = ann / vol if vol > 1e-8 else 0.0
    cum  = (1 + rets).cumprod()
    mdd  = (cum / cum.cummax() - 1).min()
    return {
        "label":  label,
        "sharpe": round(float(shp), 4),
        "annual": round(float(ann * 100), 2),
        "dd":     round(float(mdd * 100), 2),
        "days":   len(rets),
    }


# ---------------------------------------------------------------------------
# Core backtest: Volume Rank Persistence
# ---------------------------------------------------------------------------

def _lag1_autocorr(arr):
    """Lag-1 autocorrelation of a 1-D array.  Returns nan if degenerate."""
    if len(arr) < 4:
        return np.nan
    a = arr[:-1]
    b = arr[1:]
    # Demean
    a = a - a.mean()
    b = b - b.mean()
    denom = np.sqrt((a**2).sum() * (b**2).sum())
    if denom < 1e-12:
        return np.nan
    return float(np.dot(a, b) / denom)


def backtest_vol_rank_persistence(closes, volumes, lookback, rebal_freq, n):
    """
    Volume Rank Persistence factor backtest.

    Returns a pd.Series of daily portfolio returns (may be None).
    """
    cols = list(closes.columns)
    if len(cols) < 2 * n:
        return None

    returns = closes.pct_change().dropna()

    # Dollar volume matrix (aligned to returns dates)
    dv = (closes * volumes).reindex(returns.index).ffill()

    dates   = returns.index
    warmup  = lookback + 5

    portfolio_rets = []
    last_rebal     = -rebal_freq
    weights        = pd.Series(0.0, index=cols)
    prev_weights   = pd.Series(0.0, index=cols)

    for i in range(warmup, len(dates)):
        # Apply existing weights to today's return
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": float(day_ret)})

        # Rebalance?
        if i - last_rebal < rebal_freq:
            continue

        # ---- Build cross-sectional rank time-series over lookback window ----
        # dv_window: shape (lookback, n_assets)
        dv_window = dv.iloc[i - lookback: i]
        if len(dv_window) < lookback:
            continue

        # Rank within each day (1 = smallest DV)
        # pct=False gives integer ranks 1..n_assets
        rank_window = dv_window.rank(axis=1, method="average")  # (lookback, n_assets)

        # Lag-1 autocorrelation of the rank series for each asset
        persistence = {}
        for sym in cols:
            if sym not in rank_window.columns:
                continue
            r_series = rank_window[sym].values
            if np.isnan(r_series).any():
                # Fill NaN ranks with cross-sectional median before autocorr
                r_series = np.where(np.isnan(r_series),
                                    np.nanmedian(r_series), r_series)
            ac = _lag1_autocorr(r_series)
            if not np.isnan(ac):
                persistence[sym] = ac

        if len(persistence) < 2 * n:
            continue

        ranked = pd.Series(persistence).sort_values(ascending=False)
        longs  = ranked.index[:n]    # highest persistence
        shorts = ranked.index[-n:]   # lowest persistence

        new_weights = pd.Series(0.0, index=cols)
        for s in longs:
            new_weights[s] =  1.0 / n
        for s in shorts:
            new_weights[s] = -1.0 / n

        # Transaction costs proportional to turnover
        turnover = (new_weights - prev_weights).abs().sum()
        tc = turnover * COST_PER_SIDE
        if portfolio_rets:
            portfolio_rets[-1]["return"] -= tc

        prev_weights = weights.copy()
        weights      = new_weights
        last_rebal   = i

    if not portfolio_rets:
        return None
    df_out = pd.DataFrame(portfolio_rets).set_index("date")
    return df_out["return"]


# ---------------------------------------------------------------------------
# Reference strategy returns (H-012 momentum)
# ---------------------------------------------------------------------------

def backtest_momentum(closes, lookback=60, rebal_freq=5, n=4):
    """H-012 cross-sectional momentum (reference only)."""
    rets = closes.pct_change().dropna()
    dates = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append(
                {"date": dates[i], "return": float((rets.iloc[i] * weights).sum())}
            )
        if i - last_rebal >= rebal_freq:
            mom = closes.iloc[i - 1] / closes.iloc[i - 1 - lookback] - 1
            ranked = mom.sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] =  1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


# ---------------------------------------------------------------------------
# Correlation helper
# ---------------------------------------------------------------------------

def safe_corr(a, b):
    if a is None or b is None:
        return float("nan")
    common = a.dropna().index.intersection(b.dropna().index)
    if len(common) < 30:
        return float("nan")
    return round(float(np.corrcoef(a.loc[common].values, b.loc[common].values)[0, 1]), 3)


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------

def run_walk_forward(closes, volumes):
    n_total = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        oos_end   = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break

        tr_c = closes.iloc[:oos_start]
        tr_v = volumes.iloc[:oos_start]
        oo_c = closes.iloc[oos_start:oos_end]
        oo_v = volumes.iloc[oos_start:oos_end]

        if len(tr_c) < WF_TRAIN_MIN or len(oo_c) < 20:
            break

        # Select best IS params on training data
        best_sharpe = -np.inf
        best_params = None
        for lb in LOOKBACKS:
            for rf in REBALS:
                for nn in NS:
                    r  = backtest_vol_rank_persistence(tr_c, tr_v, lb, rf, nn)
                    ev = evaluate(r)
                    if ev and ev["sharpe"] > best_sharpe:
                        best_sharpe = ev["sharpe"]
                        best_params = (lb, rf, nn)

        if best_params is None:
            fold_results.append({
                "fold": fold + 1, "is_params": "none", "is_sharpe": 0.0,
                "oos_sharpe": None, "oos_start": "", "oos_end": "",
            })
            continue

        lb, rf, nn = best_params
        oos_r  = backtest_vol_rank_persistence(oo_c, oo_v, lb, rf, nn)
        oos_ev = evaluate(oos_r)

        oos_s_date = str(closes.index[oos_start])[:10]
        oos_e_date = str(closes.index[min(oos_end - 1, len(closes) - 1)])[:10]

        fold_results.append({
            "fold":       fold + 1,
            "is_params":  f"LB{lb}_R{rf}_N{nn}",
            "is_sharpe":  round(best_sharpe, 3),
            "oos_sharpe": oos_ev["sharpe"] if oos_ev else None,
            "oos_start":  oos_s_date,
            "oos_end":    oos_e_date,
        })

    return fold_results


# ---------------------------------------------------------------------------
# Split-half validation
# ---------------------------------------------------------------------------

def run_split_half(closes, volumes):
    half = len(closes) // 2
    h1c, h1v = closes.iloc[:half], volumes.iloc[:half]
    h2c, h2v = closes.iloc[half:], volumes.iloc[half:]

    h1_sharpes, h2_sharpes = [], []
    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                e1 = evaluate(backtest_vol_rank_persistence(h1c, h1v, lb, rf, nn))
                e2 = evaluate(backtest_vol_rank_persistence(h2c, h2v, lb, rf, nn))
                if e1:
                    h1_sharpes.append(e1["sharpe"])
                if e2:
                    h2_sharpes.append(e2["sharpe"])

    if not h1_sharpes or not h2_sharpes:
        return None, None, None, None

    return (
        round(max(h1_sharpes), 3),
        round(max(h2_sharpes), 3),
        round(float(np.mean(h1_sharpes)), 3),
        round(float(np.mean(h2_sharpes)), 3),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  H-212: Relative Volume Rank Persistence")
    print("=" * 60)

    print("\nLoading daily OHLCV data...")
    closes, volumes = load_daily_data()
    n_assets = len(closes.columns)
    n_days   = len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")
    print(f"Assets: {list(closes.columns)}")

    if n_assets < 6:
        print("ERROR: Too few assets. Aborting.")
        sys.exit(1)

    total_combos = len(LOOKBACKS) * len(REBALS) * len(NS)

    # ==================================================================
    # Stage 1: IS Parameter Scan
    # ==================================================================
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")

    all_results = []
    count = 0
    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                count += 1
                r  = backtest_vol_rank_persistence(closes, volumes, lb, rf, nn)
                ev = evaluate(r, f"LB{lb}_R{rf}_N{nn}")
                if ev:
                    ev["lb"] = lb
                    ev["rf"] = rf
                    ev["n"]  = nn
                    all_results.append(ev)
        print(f"  {count}/{total_combos} combos done...")

    if not all_results:
        print("No valid results! REJECTED.")
        return

    df_res = pd.DataFrame(all_results)
    n_pos  = int((df_res["sharpe"] > 0).sum())
    pct_pos = n_pos / len(df_res) * 100
    mean_shp = float(df_res["sharpe"].mean())
    med_shp  = float(df_res["sharpe"].median())

    print(f"\n  Valid combos : {len(df_res)}/{total_combos}")
    print(f"  Positive Sharpe: {n_pos}/{len(df_res)} ({pct_pos:.1f}%)")
    print(f"  Mean Sharpe  : {mean_shp:.3f}")
    print(f"  Median Sharpe: {med_shp:.3f}")

    df_sorted = df_res.sort_values("sharpe", ascending=False)
    print(f"\n  Top 10 combos:")
    for _, row in df_sorted.head(10).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    print(f"\n  Bottom 5 combos:")
    for _, row in df_sorted.tail(5).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    best_row = df_sorted.iloc[0]
    best_lb  = int(best_row["lb"])
    best_rf  = int(best_row["rf"])
    best_n   = int(best_row["n"])

    print(f"\n  Best combo: LB{best_lb}_R{best_rf}_N{best_n}")
    print(f"  Sharpe: {best_row['sharpe']:.3f}, Annual: {best_row['annual']:.1f}%, "
          f"Max DD: {best_row['dd']:.1f}%, Days: {int(best_row['days'])}")

    # IS gate
    is_pass = pct_pos >= 80.0
    if not is_pass:
        print(f"\n*** FAIL IS: {pct_pos:.1f}% positive < 80% threshold ***")
        print("REJECTED at Stage 1. Skipping further validation.")
        result_json = {
            "hypothesis": "H-212",
            "name": "Relative Volume Rank Persistence",
            "status": "REJECTED",
            "reason": f"IS positive rate {pct_pos:.1f}% < 80% threshold",
            "is_positive_rate": round(pct_pos, 1),
            "is_mean_sharpe": round(mean_shp, 3),
            "is_median_sharpe": round(med_shp, 3),
            "best_params": {"lookback": best_lb, "rebal": best_rf, "n": best_n},
            "best_sharpe": round(float(best_row["sharpe"]), 3),
            "best_annual_return": round(float(best_row["annual"]), 1),
            "best_max_dd": round(float(best_row["dd"]), 1),
            "n_assets": n_assets,
            "n_days": n_days,
            "total_combos": total_combos,
            "valid_combos": len(df_res),
            "validation": {"is_pass": False, "wf_pass": None, "sh_pass": None, "corr_pass": None},
        }
        results_path = Path(__file__).parent / "results.json"
        with open(results_path, "w") as f:
            json.dump(result_json, f, indent=2)
        print(f"\nResults written to {results_path}")
        return

    # ==================================================================
    # Stage 2: Walk-Forward Validation
    # ==================================================================
    print(f"\n--- Stage 2: Walk-Forward ({WF_FOLDS} folds, {WF_TEST_DAYS}d OOS each) ---")
    wf_results = run_walk_forward(closes, volumes)

    wf_oos_sharpes = [r["oos_sharpe"] for r in wf_results if r["oos_sharpe"] is not None]
    wf_n_pos = sum(1 for s in wf_oos_sharpes if s > 0)
    mean_oos = float(np.mean(wf_oos_sharpes)) if wf_oos_sharpes else float("nan")

    for r in wf_results:
        oos_str = f"{r['oos_sharpe']:.3f}" if r["oos_sharpe"] is not None else "N/A"
        print(f"  Fold {r['fold']}: IS={r['is_params']} (IS Sharpe {r['is_sharpe']:.3f}), "
              f"OOS {r['oos_start']}~{r['oos_end']}, OOS Sharpe {oos_str}")

    print(f"\n  WF summary: {wf_n_pos}/{len(wf_oos_sharpes)} positive OOS folds, "
          f"mean OOS Sharpe: {mean_oos:.3f}")

    wf_pass = wf_n_pos >= 4 and (not np.isnan(mean_oos)) and mean_oos > 0
    if not wf_pass:
        fails = []
        if wf_n_pos < 4:
            fails.append(f"{wf_n_pos}/{len(wf_oos_sharpes)} positive < 4/6")
        if np.isnan(mean_oos) or mean_oos <= 0:
            fails.append(f"mean OOS Sharpe {mean_oos:.3f} <= 0")
        print(f"  *** FAIL WF: {'; '.join(fails)} ***")

    # ==================================================================
    # Stage 3: Split-Half
    # ==================================================================
    print(f"\n--- Stage 3: Split-Half Stability ---")
    sh_best_h1, sh_best_h2, sh_mean_h1, sh_mean_h2 = run_split_half(closes, volumes)

    if sh_best_h1 is not None:
        print(f"  H1 best Sharpe: {sh_best_h1:.3f}, H1 mean Sharpe: {sh_mean_h1:.3f}")
        print(f"  H2 best Sharpe: {sh_best_h2:.3f}, H2 mean Sharpe: {sh_mean_h2:.3f}")
        sh_pass = sh_best_h1 > 0 and sh_best_h2 > 0
        if not sh_pass:
            print("  *** FAIL Split-Half: need both best Sharpes > 0 ***")
    else:
        print("  Split-half: insufficient data")
        sh_pass = False

    # ==================================================================
    # Stage 4: Correlation with H-012 (momentum)
    # ==================================================================
    print(f"\n--- Stage 4: Correlation with H-012 (Momentum) ---")
    best_rets = backtest_vol_rank_persistence(closes, volumes, best_lb, best_rf, best_n)
    mom_rets  = backtest_momentum(closes)

    corr_h012 = safe_corr(best_rets, mom_rets)
    print(f"  H-012 (momentum): {corr_h012:.3f}")

    corr_pass = (not np.isnan(corr_h012)) and abs(corr_h012) < 0.50
    if not corr_pass:
        print(f"  *** {'FAIL Correlation' if not np.isnan(corr_h012) else 'WARN: corr NaN'}: "
              f"|corr| = {corr_h012:.3f} >= 0.50 ***")
    else:
        print(f"  PASS: |corr| = {corr_h012:.3f} < 0.50")

    # ==================================================================
    # Final Verdict
    # ==================================================================
    print(f"\n{'='*60}")
    print("  FINAL VERDICT")
    print(f"{'='*60}")
    print(f"  IS positive rate : {pct_pos:.1f}%  {'PASS' if is_pass else 'FAIL'}")
    print(f"  Walk-Forward     : {wf_n_pos}/{len(wf_oos_sharpes)} pos, mean OOS {mean_oos:.3f}  "
          f"{'PASS' if wf_pass else 'FAIL'}")
    print(f"  Split-Half       : H1={sh_best_h1}, H2={sh_best_h2}  {'PASS' if sh_pass else 'FAIL'}")
    print(f"  Correlation H-012: {corr_h012:.3f}  {'PASS' if corr_pass else 'FAIL'}")

    all_pass = is_pass and wf_pass and sh_pass and corr_pass
    status   = "CONFIRMED" if all_pass else "REJECTED"

    rejection_reasons = []
    if not is_pass:
        rejection_reasons.append(f"IS positive rate {pct_pos:.1f}% < 80%")
    if not wf_pass:
        rejection_reasons.append(
            f"WF {wf_n_pos}/{len(wf_oos_sharpes)} positive, mean OOS {mean_oos:.3f}")
    if not sh_pass:
        rejection_reasons.append(
            f"Split-half best Sharpes H1={sh_best_h1}, H2={sh_best_h2}")
    if not corr_pass:
        rejection_reasons.append(f"|corr H-012| = {corr_h012:.3f} >= 0.50")

    print(f"\n  Status: {status}")
    if rejection_reasons:
        print(f"  Reason: {'; '.join(rejection_reasons)}")

    # ==================================================================
    # Write results.json
    # ==================================================================
    result_json = {
        "hypothesis": "H-212",
        "name": "Relative Volume Rank Persistence",
        "status": status,
        "reason": "; ".join(rejection_reasons) if rejection_reasons else "All 4 stages passed",
        "is_positive_rate": round(pct_pos, 1),
        "is_mean_sharpe": round(mean_shp, 3),
        "is_median_sharpe": round(med_shp, 3),
        "best_params": {"lookback": best_lb, "rebal": best_rf, "n": best_n},
        "best_sharpe": round(float(best_row["sharpe"]), 3),
        "best_annual_return": round(float(best_row["annual"]), 1),
        "best_max_dd": round(float(best_row["dd"]), 1),
        "wf_folds": [
            {
                "fold":       r["fold"],
                "is_params":  r["is_params"],
                "is_sharpe":  r["is_sharpe"],
                "oos_sharpe": r["oos_sharpe"],
                "oos_start":  r["oos_start"],
                "oos_end":    r["oos_end"],
            }
            for r in wf_results
        ] if is_pass else [],
        "wf_positive_folds": wf_n_pos if is_pass else None,
        "wf_total_folds": len(wf_oos_sharpes) if is_pass else None,
        "wf_mean_oos_sharpe": round(mean_oos, 3) if (is_pass and not np.isnan(mean_oos)) else None,
        "split_half": {
            "h1_best_sharpe": sh_best_h1,
            "h2_best_sharpe": sh_best_h2,
            "h1_mean_sharpe": sh_mean_h1,
            "h2_mean_sharpe": sh_mean_h2,
        } if is_pass else None,
        "correlations": {
            "H-012_momentum": corr_h012 if not np.isnan(corr_h012) else None,
        } if is_pass else None,
        "max_abs_correlation": round(abs(corr_h012), 3) if (is_pass and not np.isnan(corr_h012)) else None,
        "n_assets": n_assets,
        "n_days": n_days,
        "total_combos": total_combos,
        "valid_combos": len(df_res),
        "all_combo_results": [
            {
                "lb": int(r["lb"]), "rf": int(r["rf"]), "n": int(r["n"]),
                "sharpe": r["sharpe"], "annual": r["annual"], "dd": r["dd"],
            }
            for r in all_results
        ],
        "validation": {
            "is_pass":   bool(is_pass),
            "wf_pass":   bool(wf_pass)  if is_pass else None,
            "sh_pass":   bool(sh_pass)  if is_pass else None,
            "corr_pass": bool(corr_pass) if is_pass else None,
        },
    }

    results_path = Path(__file__).parent / "results.json"
    with open(results_path, "w") as f:
        json.dump(result_json, f, indent=2)
    print(f"\nResults written to {results_path}")


if __name__ == "__main__":
    main()
