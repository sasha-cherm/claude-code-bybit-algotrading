#!/usr/bin/env python3
"""
H-199: Consecutive Return Streaks Factor — Cross-Sectional Backtest
====================================================================

Idea: Count the length of the current consecutive positive (or negative) daily
return streak for each asset.  The signed streak count is +N when the last N
daily returns were all positive and -N when the last N daily returns were all
negative.  With smoothing window W > 1, take the rolling mean of the signed
streak count over W days.

Differs from:
  - H-133 (consecutive direction): H-133 counts net up-down days over a fixed
    lookback window; H-199 counts the *unbroken streak* length — it resets to
    zero after a single opposing day.
  - H-012 (momentum): pure return-based, not streak-based.
  - H-093 (trend consistency): ratio-based, not count-based.

Directions:
  - streak_long  (momentum continuation): Long assets with longest positive
    streaks, Short assets with longest negative streaks.
  - contrarian_long (reversal bet): Long assets with longest negative streaks,
    Short assets with longest positive streaks.

Parameter grid:
  Smoothing window W : [1, 3, 5, 10]   (1 = raw streak, >1 = rolling mean)
  Rebalance period R : [3, 5, 7]
  N top/bottom       : [3, 4]
  Direction           : [streak_long, contrarian_long]
  Total: 4 x 3 x 2 x 2 = 48 combos

Validation (4-stage):
  1. IS: >= 80% of combos in the better direction must have positive Sharpe
  2. Walk-Forward: 6 folds, best IS params per fold, need >= 4/6 positive OOS
  3. Split-Half: Run full grid on each half, both halves' best-combo Sharpe > 0
  4. Correlation: max |corr| < 0.50 with H-012
"""

import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS_ALL = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
    "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT", "NEAR/USDT",
    "OP/USDT", "ARB/USDT", "ATOM/USDT", "SUI/USDT",
]

# Parameter grid
SMOOTHING_WINDOWS = [1, 3, 5, 10]
REBALS            = [3, 5, 7]
NS                = [3, 4]
DIRECTIONS        = ["streak_long", "contrarian_long"]

# Transaction costs: 10bps round-trip => 5bps per side
COST_PER_SIDE = 0.0005

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
    return closes


# -- Streak computation ----------------------------------------------------

def compute_signed_streaks(returns_series):
    """
    Compute signed consecutive streak count for a single asset's daily returns.

    For each day t:
      If the last N returns were all positive, streak = +N
      If the last N returns were all negative, streak = -N
      Otherwise streak = 0 (only after a direction change)

    Returns a pd.Series aligned with input.
    """
    values = returns_series.values
    n = len(values)
    streaks = np.zeros(n, dtype=float)

    for i in range(n):
        if np.isnan(values[i]):
            streaks[i] = 0.0
            continue
        if values[i] > 0:
            if i > 0 and streaks[i - 1] > 0:
                streaks[i] = streaks[i - 1] + 1
            else:
                streaks[i] = 1.0
        elif values[i] < 0:
            if i > 0 and streaks[i - 1] < 0:
                streaks[i] = streaks[i - 1] - 1
            else:
                streaks[i] = -1.0
        else:
            # Exactly zero return: treat as no streak
            streaks[i] = 0.0

    return pd.Series(streaks, index=returns_series.index)


def compute_streak_matrix(returns_df, smoothing_window=1):
    """
    Compute signed streak scores for all assets.

    Args:
        returns_df: DataFrame of daily returns (assets in columns)
        smoothing_window: if >1, take rolling mean of raw streak over this window

    Returns:
        DataFrame of streak scores (same shape as returns_df)
    """
    streak_dict = {}
    for sym in returns_df.columns:
        raw = compute_signed_streaks(returns_df[sym])
        if smoothing_window > 1:
            streak_dict[sym] = raw.rolling(smoothing_window, min_periods=1).mean()
        else:
            streak_dict[sym] = raw
    return pd.DataFrame(streak_dict)


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

def backtest_streaks(closes, smoothing_window, rebal_freq, n, direction):
    """
    Consecutive Return Streaks Factor backtest.

    Args:
        closes:           DataFrame of daily closes
        smoothing_window: W for smoothing (1 = raw streak)
        rebal_freq:       rebalance every R days
        n:                number of longs and shorts
        direction:        "streak_long" or "contrarian_long"
    Returns:
        pd.Series of daily portfolio returns (or None)
    """
    trade_cols = list(closes.columns)
    if len(trade_cols) < 2 * n:
        return None

    returns = closes.pct_change().dropna()
    streak_scores = compute_streak_matrix(returns, smoothing_window)

    dates = returns.index
    warmup = max(smoothing_window, 5) + 5

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=trade_cols)
    prev_weights = pd.Series(0.0, index=trade_cols)

    for i in range(warmup, len(dates)):
        # Apply existing weights to get day's return
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": day_ret})

        # Rebalance check
        if i - last_rebal >= rebal_freq:
            scores = {}
            for sym in trade_cols:
                if sym not in streak_scores.columns:
                    continue
                val = streak_scores[sym].iloc[i - 1]  # use yesterday's streak
                if np.isnan(val):
                    continue
                scores[sym] = val

            if len(scores) < 2 * n:
                continue

            ranked = pd.Series(scores).sort_values(ascending=True)
            # ranked: ascending by streak score
            # Bottom = most negative streaks (longest losing streaks)
            # Top = most positive streaks (longest winning streaks)

            if direction == "streak_long":
                # Momentum: long highest streaks, short lowest streaks
                longs = ranked.index[-n:]
                shorts = ranked.index[:n]
            else:
                # Contrarian: long lowest streaks (losers), short highest (winners)
                longs = ranked.index[:n]
                shorts = ranked.index[-n:]

            new_weights = pd.Series(0.0, index=trade_cols)
            for s in longs:
                new_weights[s] = 1.0 / n
            for s in shorts:
                new_weights[s] = -1.0 / n

            # Transaction costs: proportional to turnover
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
    """H-012 cross-sectional momentum."""
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

def run_walk_forward(closes, best_direction):
    """
    6-fold walk-forward. For each fold, select best IS params from full grid
    (within the best direction) on training data, then evaluate OOS.
    """
    n_total = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        oos_end = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break

        train_closes = closes.iloc[:oos_start]
        oos_closes = closes.iloc[oos_start:oos_end]

        if len(train_closes) < WF_TRAIN_MIN or len(oos_closes) < 20:
            break

        # IS param selection on training data
        best_sharpe = -np.inf
        best_params = None
        for sw in SMOOTHING_WINDOWS:
            for rf in REBALS:
                for nn in NS:
                    r = backtest_streaks(train_closes, sw, rf, nn, best_direction)
                    ev = evaluate(r)
                    if ev and ev["sharpe"] > best_sharpe:
                        best_sharpe = ev["sharpe"]
                        best_params = (sw, rf, nn)

        if best_params is None:
            fold_results.append({
                "fold": fold + 1, "is_params": "none", "is_sharpe": 0,
                "oos_sharpe": None, "oos_start": "", "oos_end": "",
            })
            continue

        sw, rf, nn = best_params
        # OOS evaluation
        oos_r = backtest_streaks(oos_closes, sw, rf, nn, best_direction)
        oos_e = evaluate(oos_r)

        oos_start_date = closes.index[oos_start]
        oos_end_date = closes.index[min(oos_end - 1, len(closes) - 1)]

        fold_results.append({
            "fold":       fold + 1,
            "is_params":  f"W{sw}_R{rf}_N{nn}",
            "is_sharpe":  round(best_sharpe, 3),
            "oos_sharpe": oos_e["sharpe"] if oos_e else None,
            "oos_start":  str(oos_start_date)[:10],
            "oos_end":    str(oos_end_date)[:10],
        })

    return fold_results


# -- Split-half validation -------------------------------------------------

def run_split_half(closes, best_direction):
    """
    Run full grid (within best direction) on each half.
    Report best-combo Sharpe and mean Sharpe for each half.
    """
    half = len(closes) // 2
    h1_closes = closes.iloc[:half]
    h2_closes = closes.iloc[half:]

    h1_results = []
    h2_results = []

    for sw in SMOOTHING_WINDOWS:
        for rf in REBALS:
            for nn in NS:
                r1 = backtest_streaks(h1_closes, sw, rf, nn, best_direction)
                r2 = backtest_streaks(h2_closes, sw, rf, nn, best_direction)
                e1 = evaluate(r1)
                e2 = evaluate(r2)
                if e1:
                    h1_results.append(e1)
                if e2:
                    h2_results.append(e2)

    if not h1_results or not h2_results:
        return None, None, None, None

    h1_sharpes = [r["sharpe"] for r in h1_results]
    h2_sharpes = [r["sharpe"] for r in h2_results]

    return (
        round(max(h1_sharpes), 3),
        round(max(h2_sharpes), 3),
        round(np.mean(h1_sharpes), 3),
        round(np.mean(h2_sharpes), 3),
    )


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
    print("  H-199: Consecutive Return Streaks Factor")
    print("=" * 60)

    print("\nLoading daily close data...")
    closes = load_daily_data()
    n_assets = len(closes.columns)
    n_days = len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")
    print(f"Assets: {list(closes.columns)}")

    if n_assets < 6:
        print("ERROR: Too few assets. Aborting.")
        sys.exit(1)

    # ==================================================================
    # Stage 1: IS Parameter Scan
    # ==================================================================
    valid_grid = [(sw, rf, nn, d)
                  for sw in SMOOTHING_WINDOWS
                  for rf in REBALS
                  for nn in NS
                  for d in DIRECTIONS]
    total_combos = len(valid_grid)
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")

    all_results = []
    count = 0
    for sw, rf, nn, d in valid_grid:
        count += 1
        r = backtest_streaks(closes, sw, rf, nn, d)
        ev = evaluate(r, f"W{sw}_R{rf}_N{nn}_{d}")
        if ev:
            ev["sw"] = sw
            ev["rf"] = rf
            ev["n"] = nn
            ev["direction"] = d
            all_results.append(ev)
        if count % 20 == 0:
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

    # Pick direction with higher positive rate
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

    # Filter to best direction for further analysis
    df_best = df_res[df_res["direction"] == best_dir].copy()
    df_best = df_best.sort_values("sharpe", ascending=False)

    # Top 10
    print(f"\n  Top 10 combos ({best_dir}):")
    for _, row in df_best.head(10).iterrows():
        print(f"    W{int(row['sw'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    # Bottom 5
    print(f"\n  Bottom 5 combos ({best_dir}):")
    for _, row in df_best.tail(5).iterrows():
        print(f"    W{int(row['sw'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    # Best combo
    best_row = df_best.iloc[0]
    best_sw = int(best_row["sw"])
    best_rf = int(best_row["rf"])
    best_n = int(best_row["n"])

    print(f"\n  Best combo: W{best_sw}_R{best_rf}_N{best_n} ({best_dir})")
    print(f"  Sharpe: {best_row['sharpe']:.3f}, Annual: {best_row['annual']:.1f}%, "
          f"Max DD: {best_row['dd']:.1f}%, Days: {int(best_row['days'])}")

    # IS gate: 80% of combos in best direction must be positive
    is_pass = pct_positive >= 80.0
    if not is_pass:
        print(f"\n*** FAIL IS: {pct_positive:.1f}% positive in {best_dir} < 80% threshold ***")
        print("REJECTED at Stage 1. Skipping further validation.")

        # Still compute correlation for reporting
        print(f"\n--- Correlation with H-012 (for reporting) ---")
        best_rets = backtest_streaks(closes, best_sw, best_rf, best_n, best_dir)
        mom_rets = backtest_momentum(closes)
        corr_h012 = safe_corr(best_rets, mom_rets)
        print(f"  H-012 (momentum): {corr_h012}")

        result_json = {
            "hypothesis": "H-199",
            "name": "Consecutive Return Streaks Factor",
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
            "best_params": {"smoothing_window": best_sw, "rebal": best_rf, "n": best_n, "direction": best_dir},
            "best_sharpe": round(float(best_row["sharpe"]), 3),
            "best_annual_return": round(float(best_row["annual"]), 1),
            "best_max_dd": round(float(best_row["dd"]), 1),
            "correlations": {"H-012_momentum": corr_h012},
            "n_assets": n_assets,
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
    wf_results = run_walk_forward(closes, best_dir)

    wf_oos_sharpes = [r["oos_sharpe"] for r in wf_results if r["oos_sharpe"] is not None]
    wf_n_pos = sum(1 for s in wf_oos_sharpes if s > 0)

    for r in wf_results:
        oos_s = f"{r['oos_sharpe']:.3f}" if r['oos_sharpe'] is not None else "N/A"
        print(f"  Fold {r['fold']}: IS={r['is_params']} (IS Sharpe {r['is_sharpe']:.3f}), "
              f"OOS={r['oos_start']}~{r['oos_end']}, OOS Sharpe {oos_s}")

    mean_oos = np.mean(wf_oos_sharpes) if wf_oos_sharpes else float("nan")
    print(f"\n  WF summary: {wf_n_pos}/{len(wf_oos_sharpes)} positive OOS folds, "
          f"mean OOS Sharpe: {mean_oos:.3f}")

    wf_pass = wf_n_pos >= 4
    if not wf_pass:
        print(f"  *** FAIL WF: {wf_n_pos}/{len(wf_oos_sharpes)} < 4/6 threshold ***")

    # ==================================================================
    # Stage 3: Split-Half
    # ==================================================================
    print(f"\n--- Stage 3: Split-Half Stability ---")
    sh_best_h1, sh_best_h2, sh_mean_h1, sh_mean_h2 = run_split_half(closes, best_dir)

    if sh_best_h1 is not None:
        print(f"  H1 best Sharpe: {sh_best_h1:.3f}, H1 mean Sharpe: {sh_mean_h1:.3f}")
        print(f"  H2 best Sharpe: {sh_best_h2:.3f}, H2 mean Sharpe: {sh_mean_h2:.3f}")
        sh_pass = sh_best_h1 > 0 and sh_best_h2 > 0
        if not sh_pass:
            print(f"  *** FAIL Split-Half: need both best Sharpes > 0 ***")
    else:
        print("  Split-half: insufficient data")
        sh_pass = False

    # ==================================================================
    # Stage 4: Correlation with H-012
    # ==================================================================
    print(f"\n--- Stage 4: Correlation with H-012 (Momentum) ---")
    best_rets = backtest_streaks(closes, best_sw, best_rf, best_n, best_dir)

    print("  Computing H-012 momentum returns...")
    mom_rets = backtest_momentum(closes)

    corr_h012 = safe_corr(best_rets, mom_rets)
    print(f"  H-012 (momentum): {corr_h012:.3f}")

    max_abs_corr = abs(corr_h012) if not np.isnan(corr_h012) else 0
    corr_pass = max_abs_corr < 0.50
    if not corr_pass:
        print(f"  *** FAIL Correlation: |corr| = {max_abs_corr:.3f} >= 0.50 ***")
    else:
        print(f"  PASS: |corr| = {max_abs_corr:.3f} < 0.50")

    # ==================================================================
    # Final Verdict
    # ==================================================================
    print(f"\n{'='*60}")
    print("  FINAL VERDICT")
    print(f"{'='*60}")
    print(f"  IS positive rate: {pct_positive:.1f}% {'PASS' if is_pass else 'FAIL'}")
    print(f"  Walk-Forward: {wf_n_pos}/{len(wf_oos_sharpes)} positive {'PASS' if wf_pass else 'FAIL'}")
    print(f"  Split-Half: H1={sh_best_h1}, H2={sh_best_h2} {'PASS' if sh_pass else 'FAIL'}")
    print(f"  Correlation: |corr|={max_abs_corr:.3f} {'PASS' if corr_pass else 'FAIL'}")

    all_pass = is_pass and wf_pass and sh_pass and corr_pass
    status = "CONFIRMED" if all_pass else "REJECTED"
    rejection_reasons = []
    if not is_pass:
        rejection_reasons.append(f"IS positive rate {pct_positive:.1f}% < 80%")
    if not wf_pass:
        rejection_reasons.append(f"WF {wf_n_pos}/{len(wf_oos_sharpes)} < 4/6")
    if not sh_pass:
        rejection_reasons.append(f"Split-half best Sharpes: H1={sh_best_h1}, H2={sh_best_h2}")
    if not corr_pass:
        rejection_reasons.append(f"|corr| {max_abs_corr:.3f} >= 0.50")

    print(f"\n  Status: {status}")
    if rejection_reasons:
        print(f"  Reason: {'; '.join(rejection_reasons)}")

    # ==================================================================
    # Write results.json
    # ==================================================================
    result_json = {
        "hypothesis": "H-199",
        "name": "Consecutive Return Streaks Factor",
        "status": status,
        "reason": "; ".join(rejection_reasons) if rejection_reasons else "All 4 stages passed",
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
        "best_params": {"smoothing_window": best_sw, "rebal": best_rf, "n": best_n, "direction": best_dir},
        "best_sharpe": round(float(best_row["sharpe"]), 3),
        "best_annual_return": round(float(best_row["annual"]), 1),
        "best_max_dd": round(float(best_row["dd"]), 1),
        "wf_folds": [
            {"fold": r["fold"], "is_params": r["is_params"],
             "is_sharpe": r["is_sharpe"], "oos_sharpe": r["oos_sharpe"],
             "oos_start": r["oos_start"], "oos_end": r["oos_end"]}
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
            "H-012_momentum": corr_h012,
        },
        "max_abs_correlation": round(max_abs_corr, 3) if is_pass else None,
        "n_assets": n_assets,
        "n_days": n_days,
        "total_combos": total_combos,
        "valid_combos": len(df_res),
        "validation": {
            "is_pass": bool(is_pass),
            "wf_pass": bool(wf_pass) if is_pass else None,
            "sh_pass": bool(sh_pass) if is_pass else None,
            "corr_pass": bool(corr_pass) if is_pass else None,
        },
    }

    results_path = Path(__file__).parent / "results.json"
    with open(results_path, "w") as f:
        json.dump(result_json, f, indent=2)
    print(f"\nResults written to {results_path}")


if __name__ == "__main__":
    main()
