#!/usr/bin/env python3
"""
H-202: Intraday Volatility Clustering Factor (14 Assets)

Concept: Measure the concentration/clustering of intraday volatility using
the Herfindahl-Hirschman Index (HHI) of hourly squared returns within each day.

High HHI = volatility concentrated in specific hours (institutional footprint)
Low HHI  = volatility diffuse across hours (retail/random)

For 24 uniform hours, minimum HHI = 1/24 ≈ 0.042. Maximum HHI = 1.0 (all vol
in one hour).

Direction options:
  - high_hhi_long: Long concentrated-vol assets (institutional), Short diffuse
  - low_hhi_long:  Long diffuse-vol assets, Short concentrated

Logic:
  For each asset on each rebalance day:
    1. Over lookback window, for each day compute HHI of hourly squared returns
    2. Rolling average HHI over lookback
    3. Rank cross-sectionally
    4. Dollar-neutral, equal weight within legs

Transaction costs: 0.05% per side (0.10% round trip) on each rebalance.
Slippage: 2bps per side.

Parameter grid:
  LB (lookback days): [5, 10, 20, 30]
  Rebalance          : [3, 5, 7]
  N (top/bottom)     : [3, 4, 5]
  Direction           : [high_hhi_long, low_hhi_long]
  Total: 4 x 3 x 3 x 2 = 72 combos

Validation (4-stage):
  1. IS: >= 80% of combos in the better direction must have positive Sharpe
  2. Walk-Forward: 6 folds, best IS params per fold, report fold Sharpes + mean
  3. Split-Half: Run best params on each half, both positive
  4. Correlation: with H-012 (60d momentum, 5d rebal, top/bottom 4)
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
LOOKBACKS   = [5, 10, 20, 30]
REBALS      = [3, 5, 7]
NS          = [3, 4, 5]
DIRECTIONS  = ["high_hhi_long", "low_hhi_long"]

# Transaction costs: 0.05% per side + 2bps slippage per side = 0.07% per side
COST_PER_SIDE = 0.0007

# Walk-forward config
WF_FOLDS     = 6
WF_TEST_DAYS = 90
WF_TRAIN_MIN = 120


# -- Data loading ----------------------------------------------------------

def load_daily_data():
    """Load 1d parquet files for all assets, return closes DataFrame."""
    data_dir = ROOT / "data"
    closes_dict = {}
    for sym in ASSETS_ALL:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if "close" in df.columns and len(df) >= 200:
                closes_dict[sym] = df["close"]
    closes = pd.DataFrame(closes_dict)
    closes = closes.dropna(how="all").ffill().dropna()
    if closes.index.tz is not None:
        closes.index = closes.index.tz_localize(None)
    return closes


def load_hourly_data():
    """Load 1h parquet files for all assets, return closes DataFrame."""
    data_dir = ROOT / "data"
    hourly_dict = {}
    for sym in ASSETS_ALL:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1h.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if "close" in df.columns and len(df) >= 200 * 24:
                hourly_dict[sym] = df["close"]
    hourly = pd.DataFrame(hourly_dict)
    hourly = hourly.dropna(how="all").ffill().dropna()
    if hourly.index.tz is not None:
        hourly.index = hourly.index.tz_localize(None)
    return hourly


# -- HHI computation -------------------------------------------------------

def compute_daily_hhi(hourly_closes):
    """
    For each asset and each day, compute the Herfindahl-Hirschman Index (HHI)
    of hourly squared returns.

    HHI = sum(share_i^2) where share_i = hourly_sq_return_i / daily_sum_sq_returns

    Returns a DataFrame with daily index and one column per asset.
    """
    hourly_rets = hourly_closes.pct_change().dropna()
    hourly_sq = hourly_rets ** 2

    # Group by date and compute HHI for each asset
    hhi_dict = {}
    for sym in hourly_sq.columns:
        sym_sq = hourly_sq[sym].dropna()
        dates = sym_sq.index.date
        daily_groups = sym_sq.groupby(dates)

        hhi_values = {}
        for date, group in daily_groups:
            total_sq = group.sum()
            if total_sq > 1e-20 and len(group) >= 12:  # need at least 12 hours
                shares = group / total_sq
                hhi = (shares ** 2).sum()
                hhi_values[date] = hhi

        if hhi_values:
            hhi_dict[sym] = pd.Series(hhi_values)

    hhi_df = pd.DataFrame(hhi_dict)
    hhi_df.index = pd.to_datetime(hhi_df.index)
    hhi_df = hhi_df.sort_index()
    return hhi_df


# -- Evaluation helpers ----------------------------------------------------

def evaluate(rets, label=""):
    """Compute Sharpe, annual return, max DD from daily return series."""
    if rets is None or len(rets) < 30:
        return None
    ann = rets.mean() * 365
    vol = rets.std() * np.sqrt(365)
    sharpe = ann / vol if vol > 1e-8 else 0.0
    cum = (1 + rets).cumprod()
    dd = (cum / cum.cummax() - 1).min()
    return {
        "label":  label,
        "sharpe": round(sharpe, 4),
        "annual": round(ann * 100, 2),
        "dd":     round(dd * 100, 2),
        "days":   len(rets),
    }


# -- Core backtest ---------------------------------------------------------

def backtest_vol_clustering(closes, hhi_scores, lookback, rebal_freq, n, direction):
    """
    Intraday Volatility Clustering (HHI) factor backtest.

    closes:      Daily close prices (DatetimeIndex, columns = assets)
    hhi_scores:  Daily HHI values (DatetimeIndex, columns = assets)
    lookback:    Number of days to average HHI over
    rebal_freq:  Rebalance every N days
    n:           Number of assets in each leg (long and short)
    direction:   'high_hhi_long' or 'low_hhi_long'
    """
    trade_cols = list(set(closes.columns) & set(hhi_scores.columns))
    if len(trade_cols) < 2 * n:
        return None

    closes = closes[trade_cols]
    hhi_scores = hhi_scores[trade_cols]

    returns = closes.pct_change().dropna()

    # Align indices
    common_idx = returns.index.intersection(hhi_scores.index)
    if len(common_idx) < lookback + 50:
        return None

    returns = returns.loc[common_idx]
    hhi_aligned = hhi_scores.loc[common_idx]
    dates = returns.index
    warmup = lookback + 5

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=trade_cols)
    prev_weights = pd.Series(0.0, index=trade_cols)

    for i in range(warmup, len(dates)):
        # Apply existing weights
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": day_ret})

        # Rebalance check
        if i - last_rebal >= rebal_freq:
            avg_hhi = {}
            for sym in trade_cols:
                hhi_window = hhi_aligned[sym].iloc[i - lookback:i].values
                valid = hhi_window[~np.isnan(hhi_window)]
                if len(valid) >= lookback * 0.6:  # need at least 60% of lookback filled
                    avg_hhi[sym] = np.mean(valid)

            if len(avg_hhi) < 2 * n:
                continue

            ranked = pd.Series(avg_hhi).sort_values(ascending=True)
            # Low HHI = diffuse volatility (retail)
            # High HHI = concentrated volatility (institutional)

            if direction == "high_hhi_long":
                # Long concentrated (institutional), Short diffuse (retail)
                longs = ranked.index[-n:]
                shorts = ranked.index[:n]
            else:
                # low_hhi_long: Long diffuse, Short concentrated
                longs = ranked.index[:n]
                shorts = ranked.index[-n:]

            new_weights = pd.Series(0.0, index=trade_cols)
            for s in longs:
                new_weights[s] = 1.0 / n
            for s in shorts:
                new_weights[s] = -1.0 / n

            # Transaction costs
            turnover = (new_weights - prev_weights).abs().sum()
            tc = turnover * COST_PER_SIDE
            if portfolio_rets:
                portfolio_rets[-1]["return"] -= tc

            prev_weights = weights.copy()
            weights = new_weights
            last_rebal = i

    if not portfolio_rets:
        return None
    df_out = pd.DataFrame(portfolio_rets).set_index("date")
    return df_out["return"]


# -- Reference strategy returns (for correlation) --------------------------

def backtest_momentum(closes, lookback=60, rebal_freq=5, n=4):
    """H-012 cross-sectional momentum: 60d lookback, 5d rebal, top/bottom 4."""
    rets = closes.pct_change().dropna()
    dates = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
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


# -- Walk-forward validation -----------------------------------------------

def run_walk_forward(closes, hhi_scores, best_direction):
    """6-fold walk-forward. Each fold: optimize on train, test on OOS 90d."""
    common_idx = closes.index.intersection(hhi_scores.index)
    closes_wf = closes.loc[common_idx]
    hhi_wf = hhi_scores.loc[common_idx]

    n_total = len(closes_wf)
    fold_results = []

    for fold in range(WF_FOLDS):
        oos_end = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break

        train_closes = closes_wf.iloc[:oos_start]
        train_hhi = hhi_wf.iloc[:oos_start]
        oos_closes = closes_wf.iloc[oos_start:oos_end]
        oos_hhi = hhi_wf.iloc[oos_start:oos_end]

        if len(train_closes) < WF_TRAIN_MIN or len(oos_closes) < 20:
            break

        best_sharpe = -np.inf
        best_params = None
        for lb in LOOKBACKS:
            for rf in REBALS:
                for nn in NS:
                    r = backtest_vol_clustering(train_closes, train_hhi, lb, rf, nn, best_direction)
                    ev = evaluate(r)
                    if ev and ev["sharpe"] > best_sharpe:
                        best_sharpe = ev["sharpe"]
                        best_params = (lb, rf, nn)

        if best_params is None:
            fold_results.append({
                "fold": fold + 1, "is_params": "none", "is_sharpe": 0,
                "oos_sharpe": None, "oos_start": "", "oos_end": "",
            })
            continue

        lb, rf, nn = best_params
        oos_r = backtest_vol_clustering(oos_closes, oos_hhi, lb, rf, nn, best_direction)
        oos_e = evaluate(oos_r)

        oos_start_date = closes_wf.index[oos_start]
        oos_end_date = closes_wf.index[min(oos_end - 1, len(closes_wf) - 1)]

        fold_results.append({
            "fold":       fold + 1,
            "is_params":  f"LB{lb}_R{rf}_N{nn}",
            "is_sharpe":  round(best_sharpe, 3),
            "oos_sharpe": oos_e["sharpe"] if oos_e else None,
            "oos_start":  str(oos_start_date)[:10],
            "oos_end":    str(oos_end_date)[:10],
        })

    return fold_results


# -- Split-half validation -------------------------------------------------

def run_split_half(closes, hhi_scores, best_lb, best_rf, best_n, best_direction):
    """Run best params on each half separately. Both must have positive Sharpe."""
    common_idx = closes.index.intersection(hhi_scores.index)
    closes_sh = closes.loc[common_idx]
    hhi_sh = hhi_scores.loc[common_idx]

    half = len(closes_sh) // 2
    h1_closes = closes_sh.iloc[:half]
    h1_hhi = hhi_sh.iloc[:half]
    h2_closes = closes_sh.iloc[half:]
    h2_hhi = hhi_sh.iloc[half:]

    r1 = backtest_vol_clustering(h1_closes, h1_hhi, best_lb, best_rf, best_n, best_direction)
    r2 = backtest_vol_clustering(h2_closes, h2_hhi, best_lb, best_rf, best_n, best_direction)
    e1 = evaluate(r1, "H1")
    e2 = evaluate(r2, "H2")

    return e1, e2


# -- Correlation helper ----------------------------------------------------

def safe_corr(a, b):
    if a is None or b is None:
        return float("nan")
    common = a.dropna().index.intersection(b.dropna().index)
    if len(common) < 30:
        return float("nan")
    return round(float(np.corrcoef(a.loc[common].values, b.loc[common].values)[0, 1]), 3)


# -- Main ------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  H-202: Intraday Volatility Clustering Factor (HHI)")
    print("=" * 60)

    print("\nLoading daily close data...")
    closes = load_daily_data()
    n_assets = len(closes.columns)
    n_days = len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")

    print("\nLoading hourly close data...")
    hourly = load_hourly_data()
    n_hourly_assets = len(hourly.columns)
    n_hourly_bars = len(hourly)
    print(f"Loaded {n_hourly_assets} assets, {n_hourly_bars} hourly bars")
    print(f"Hourly date range: {hourly.index[0]} -> {hourly.index[-1]}")

    print("\nComputing daily HHI of hourly squared returns...")
    hhi_scores = compute_daily_hhi(hourly)
    print(f"HHI shape: {hhi_scores.shape}")
    print(f"HHI date range: {hhi_scores.index[0]} -> {hhi_scores.index[-1]}")

    # Sample HHI values
    print(f"\nHHI sample statistics (last 30 days mean):")
    recent_hhi = hhi_scores.tail(30).mean()
    for sym in sorted(recent_hhi.index):
        print(f"  {sym}: {recent_hhi[sym]:.4f}")
    print(f"  Cross-sectional mean: {recent_hhi.mean():.4f}")
    print(f"  (Uniform = {1.0/24:.4f}, Max = 1.0)")

    # Common columns between daily closes and HHI data
    common_assets = list(set(closes.columns) & set(hhi_scores.columns))
    print(f"\nCommon assets: {len(common_assets)}: {sorted(common_assets)}")

    if len(common_assets) < 6:
        print("ERROR: Too few common assets. Aborting.")
        sys.exit(1)

    closes = closes[common_assets]

    # ==================================================================
    # Stage 1: IS Parameter Scan
    # ==================================================================
    valid_grid = [(lb, rf, nn, d)
                  for lb in LOOKBACKS
                  for rf in REBALS
                  for nn in NS
                  for d in DIRECTIONS]
    total_combos = len(valid_grid)
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")

    all_results = []
    count = 0
    for lb, rf, nn, d in valid_grid:
        count += 1
        r = backtest_vol_clustering(closes, hhi_scores, lb, rf, nn, d)
        ev = evaluate(r, f"LB{lb}_R{rf}_N{nn}_{d}")
        if ev:
            ev["lb"] = lb
            ev["rf"] = rf
            ev["n"] = nn
            ev["direction"] = d
            all_results.append(ev)
        if count % 24 == 0:
            print(f"  {count}/{total_combos} done...")

    print(f"  {count}/{total_combos} done.")

    if not all_results:
        print("No valid results! REJECTED.")
        return

    df_res = pd.DataFrame(all_results)

    # Analyze by direction
    print(f"\n  Results by direction:")
    for d in DIRECTIONS:
        sub = df_res[df_res["direction"] == d]
        n_pos = (sub["sharpe"] > 0).sum()
        pct = n_pos / len(sub) * 100 if len(sub) > 0 else 0
        mean_s = sub["sharpe"].mean() if len(sub) > 0 else 0
        print(f"    {d}: {n_pos}/{len(sub)} positive ({pct:.1f}%), mean Sharpe {mean_s:.3f}")

    # Select the better direction
    dir_stats = {}
    for d in DIRECTIONS:
        sub = df_res[df_res["direction"] == d]
        if len(sub) > 0:
            n_pos = (sub["sharpe"] > 0).sum()
            pct = n_pos / len(sub) * 100
            dir_stats[d] = {"pct_positive": pct, "mean_sharpe": sub["sharpe"].mean(), "count": len(sub)}

    best_dir = max(dir_stats, key=lambda d: dir_stats[d]["pct_positive"])
    best_dir_stats = dir_stats[best_dir]
    pct_positive = best_dir_stats["pct_positive"]
    mean_sharpe_best_dir = best_dir_stats["mean_sharpe"]

    print(f"\n  Better direction: {best_dir}")
    print(f"  Positive Sharpe: {pct_positive:.1f}%")
    print(f"  Mean Sharpe: {mean_sharpe_best_dir:.3f}")

    # Overall stats
    n_positive_all = (df_res["sharpe"] > 0).sum()
    mean_sharpe_all = df_res["sharpe"].mean()
    median_sharpe_all = df_res["sharpe"].median()
    print(f"\n  Overall (all directions):")
    print(f"  Valid combos: {len(df_res)}/{total_combos}")
    print(f"  Positive Sharpe: {n_positive_all}/{len(df_res)} ({n_positive_all/len(df_res)*100:.1f}%)")
    print(f"  Mean Sharpe: {mean_sharpe_all:.3f}")
    print(f"  Median Sharpe: {median_sharpe_all:.3f}")

    # Filter to best direction
    df_best = df_res[df_res["direction"] == best_dir].copy()
    df_best = df_best.sort_values("sharpe", ascending=False)

    # Top 10
    print(f"\n  Top 10 combos ({best_dir}):")
    for _, row in df_best.head(10).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    # Bottom 5
    print(f"\n  Bottom 5 combos ({best_dir}):")
    for _, row in df_best.tail(5).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    # Best combo
    best_row = df_best.iloc[0]
    best_lb = int(best_row["lb"])
    best_rf = int(best_row["rf"])
    best_n = int(best_row["n"])

    print(f"\n  Best combo: LB{best_lb}_R{best_rf}_N{best_n} ({best_dir})")
    print(f"  Sharpe: {best_row['sharpe']:.3f}, Annual: {best_row['annual']:.1f}%, "
          f"Max DD: {best_row['dd']:.1f}%, Days: {int(best_row['days'])}")

    # IS gate
    is_pass = pct_positive >= 80.0
    if not is_pass:
        print(f"\n*** FAIL IS: {pct_positive:.1f}% positive in {best_dir} < 80% threshold ***")
        print("REJECTED at Stage 1. Skipping further validation.")

        result_json = {
            "hypothesis": "H-202",
            "name": "Intraday Volatility Clustering Factor (HHI)",
            "status": "REJECTED",
            "reason": f"IS positive rate {pct_positive:.1f}% ({best_dir}) < 80% threshold",
            "best_direction": best_dir,
            "direction_stats": {
                d: {
                    "pct_positive": round(dir_stats[d]["pct_positive"], 1),
                    "mean_sharpe": round(dir_stats[d]["mean_sharpe"], 3),
                    "n_combos": dir_stats[d]["count"],
                }
                for d in dir_stats
            },
            "is_positive_rate": round(pct_positive, 1),
            "is_mean_sharpe": round(mean_sharpe_best_dir, 3),
            "best_params": {"lookback": best_lb, "rebal": best_rf, "n": best_n, "direction": best_dir},
            "best_sharpe": round(float(best_row["sharpe"]), 3),
            "best_annual_return": round(float(best_row["annual"]), 1),
            "best_max_dd": round(float(best_row["dd"]), 1),
            "n_assets": len(common_assets),
            "n_days": n_days,
            "total_combos": total_combos,
            "valid_combos": len(df_res),
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
    wf_results = run_walk_forward(closes, hhi_scores, best_dir)

    wf_oos_sharpes = [r["oos_sharpe"] for r in wf_results if r["oos_sharpe"] is not None]
    wf_n_pos = sum(1 for s in wf_oos_sharpes if s > 0)

    for r in wf_results:
        oos_s = f"{r['oos_sharpe']:.3f}" if r['oos_sharpe'] is not None else "N/A"
        print(f"  Fold {r['fold']}: IS={r['is_params']} (IS Sharpe {r['is_sharpe']:.3f}), "
              f"OOS={r['oos_start']}~{r['oos_end']}, OOS Sharpe {oos_s}")

    mean_oos = np.mean(wf_oos_sharpes) if wf_oos_sharpes else float("nan")
    print(f"\n  WF summary: {wf_n_pos}/{len(wf_oos_sharpes)} positive OOS folds, "
          f"mean OOS Sharpe: {mean_oos:.3f}")

    # ==================================================================
    # Stage 3: Split-Half
    # ==================================================================
    print(f"\n--- Stage 3: Split-Half Stability ---")
    e1, e2 = run_split_half(closes, hhi_scores, best_lb, best_rf, best_n, best_dir)

    if e1 is not None and e2 is not None:
        print(f"  H1: Sharpe {e1['sharpe']:.3f}, Ann {e1['annual']:.1f}%, DD {e1['dd']:.1f}%, Days {e1['days']}")
        print(f"  H2: Sharpe {e2['sharpe']:.3f}, Ann {e2['annual']:.1f}%, DD {e2['dd']:.1f}%, Days {e2['days']}")
        sh_pass = e1["sharpe"] > 0 and e2["sharpe"] > 0
        if not sh_pass:
            print(f"  *** FAIL Split-Half: need both Sharpes > 0 ***")
    else:
        print("  Split-half: insufficient data")
        sh_pass = False

    # ==================================================================
    # Stage 4: Correlation with H-012
    # ==================================================================
    print(f"\n--- Stage 4: Correlation with H-012 (60d momentum, 5d rebal, N=4) ---")
    best_rets = backtest_vol_clustering(closes, hhi_scores, best_lb, best_rf, best_n, best_dir)

    print("  Computing H-012 momentum returns...")
    mom_rets = backtest_momentum(closes, lookback=60, rebal_freq=5, n=4)

    corr_h012 = safe_corr(best_rets, mom_rets)
    print(f"  H-012 (momentum) correlation: {corr_h012:.3f}")

    # ==================================================================
    # Final Verdict
    # ==================================================================
    print(f"\n{'='*60}")
    print("  FINAL VERDICT")
    print(f"{'='*60}")
    print(f"  IS positive rate: {pct_positive:.1f}% {'PASS' if is_pass else 'FAIL'}")
    print(f"  Walk-Forward: {wf_n_pos}/{len(wf_oos_sharpes)} positive, mean OOS Sharpe {mean_oos:.3f}")
    if e1 and e2:
        print(f"  Split-Half: H1 Sharpe={e1['sharpe']:.3f}, H2 Sharpe={e2['sharpe']:.3f} {'PASS' if sh_pass else 'FAIL'}")
    else:
        print(f"  Split-Half: insufficient data FAIL")
    print(f"  H-012 Correlation: {corr_h012:.3f}")

    # Status determination
    all_pass = is_pass and sh_pass
    status = "CONFIRMED" if all_pass else "REJECTED"
    rejection_reasons = []
    if not is_pass:
        rejection_reasons.append(f"IS positive rate {pct_positive:.1f}% < 80%")
    if not sh_pass:
        if e1 and e2:
            rejection_reasons.append(f"Split-half Sharpes: H1={e1['sharpe']:.3f}, H2={e2['sharpe']:.3f}")
        else:
            rejection_reasons.append("Split-half: insufficient data")

    print(f"\n  Status: {status}")
    if rejection_reasons:
        print(f"  Reason: {'; '.join(rejection_reasons)}")

    # ==================================================================
    # Write results.json
    # ==================================================================
    result_json = {
        "hypothesis": "H-202",
        "name": "Intraday Volatility Clustering Factor (HHI)",
        "status": status,
        "reason": "; ".join(rejection_reasons) if rejection_reasons else "All stages passed",
        "best_direction": best_dir,
        "direction_stats": {
            d: {
                "pct_positive": round(dir_stats[d]["pct_positive"], 1),
                "mean_sharpe": round(dir_stats[d]["mean_sharpe"], 3),
                "n_combos": dir_stats[d]["count"],
            }
            for d in dir_stats
        },
        "is_positive_rate": round(pct_positive, 1),
        "is_mean_sharpe": round(mean_sharpe_best_dir, 3),
        "is_median_sharpe": round(float(df_best["sharpe"].median()), 3),
        "best_params": {"lookback": best_lb, "rebal": best_rf, "n": best_n, "direction": best_dir},
        "best_sharpe": round(float(best_row["sharpe"]), 3),
        "best_annual_return": round(float(best_row["annual"]), 1),
        "best_max_dd": round(float(best_row["dd"]), 1),
        "wf_folds": [
            {"fold": r["fold"], "is_params": r["is_params"],
             "is_sharpe": r["is_sharpe"], "oos_sharpe": r["oos_sharpe"],
             "oos_start": r["oos_start"], "oos_end": r["oos_end"]}
            for r in wf_results
        ],
        "wf_positive_folds": wf_n_pos,
        "wf_total_folds": len(wf_oos_sharpes),
        "wf_mean_oos_sharpe": round(mean_oos, 3) if not np.isnan(mean_oos) else None,
        "split_half": {
            "h1": {"sharpe": e1["sharpe"], "annual": e1["annual"], "dd": e1["dd"], "days": e1["days"]} if e1 else None,
            "h2": {"sharpe": e2["sharpe"], "annual": e2["annual"], "dd": e2["dd"], "days": e2["days"]} if e2 else None,
        },
        "correlation_h012": corr_h012,
        "n_assets": len(common_assets),
        "n_days": n_days,
        "total_combos": total_combos,
        "valid_combos": len(df_res),
        "validation": {
            "is_pass": bool(is_pass),
            "sh_pass": bool(sh_pass),
        },
    }

    results_path = Path(__file__).parent / "results.json"
    with open(results_path, "w") as f:
        json.dump(result_json, f, indent=2)
    print(f"\nResults written to {results_path}")


if __name__ == "__main__":
    main()
