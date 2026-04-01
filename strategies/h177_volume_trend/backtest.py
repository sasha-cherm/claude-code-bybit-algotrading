#!/usr/bin/env python3
"""
H-177: Volume Trend (Slope) Factor

Concept: Volume itself has trends. Rank assets by the trend in their trading
volume -- rising volume signals growing interest/accumulation, declining volume
signals waning interest/distribution.

Logic:
  For each of 14 crypto assets, on each rebalance day:
    1. Take log(volume) over the lookback window
    2. Compute OLS slope of log(volume) vs time index, normalized by std of
       log(volume) for cross-sectional comparability
    3. Rank assets cross-sectionally by this normalized slope
    4. Direction:
       - rising_long:   Long top-N (fastest rising volume), Short bottom-N
       - declining_long: Long bottom-N (fastest declining volume), Short top-N

Dollar-neutral: $1 long, $1 short. Equal weight within each leg.
Transaction costs: 0.06% per side (0.12% round trip) on each rebalance.

Parameter grid:
  Lookback (LB)   : [10, 20, 30, 40, 60]
  Rebalance (R)    : [3, 5, 7]
  N (top/bottom)   : [3, 4]
  Direction        : [rising_long, declining_long]
  Total: 5 x 3 x 2 x 2 = 60 combos

Validation (4-stage):
  1. IS: >= 80% of combos in the better direction must have positive Sharpe
  2. Walk-Forward: 6 folds, best IS params per fold, need >= 4/6 positive OOS
  3. Split-Half: Both halves' best-combo Sharpe > 0
  4. Correlation: max |corr| < 0.40 with H-012, H-076, H-160, H-169
"""

import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
    "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT", "NEAR/USDT",
    "OP/USDT", "ARB/USDT", "ATOM/USDT", "SUI/USDT",
]

# Parameter grid
LOOKBACKS = [10, 20, 30, 40, 60]
REBALS    = [3, 5, 7]
NS        = [3, 4]
DIRECTIONS = ["rising_long", "declining_long"]

# Transaction costs
COST_PER_SIDE = 0.0006  # 0.06% per side

# Walk-forward config
WF_FOLDS     = 6
WF_TEST_DAYS = 90   # ~3 months per fold
WF_TRAIN_MIN = 120  # minimum IS training days


# -- Data loading ----------------------------------------------------------

def load_daily_data():
    """Load 1d parquet files for all assets, return closes and volumes DataFrames."""
    data_dir = ROOT / "data"
    closes_dict = {}
    volumes_dict = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if "close" in df.columns and "volume" in df.columns and len(df) >= 200:
                closes_dict[sym] = df["close"]
                volumes_dict[sym] = df["volume"]
    closes = pd.DataFrame(closes_dict)
    volumes = pd.DataFrame(volumes_dict)
    # Align indices
    common_idx = closes.index.intersection(volumes.index)
    closes = closes.loc[common_idx].dropna(how="all").ffill().dropna()
    volumes = volumes.loc[common_idx].dropna(how="all").ffill().dropna()
    # Ensure same index
    common = closes.index.intersection(volumes.index)
    closes = closes.loc[common]
    volumes = volumes.loc[common]
    return closes, volumes


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


def compute_volume_slope(vol_window):
    """
    Compute OLS slope of log(volume) vs time index, normalized by std.

    Args:
        vol_window: 1D array of volume values over the lookback window

    Returns:
        Normalized slope (slope / std of log_vol), or NaN if invalid
    """
    # Filter out zeros/negatives
    v = np.array(vol_window, dtype=float)
    if np.any(v <= 0) or len(v) < 5:
        return np.nan

    log_v = np.log(v)
    std_log_v = np.std(log_v)
    if std_log_v < 1e-10:
        return 0.0

    # OLS slope: cov(x, y) / var(x) where x = time index
    n = len(log_v)
    x = np.arange(n, dtype=float)
    x_mean = x.mean()
    y_mean = log_v.mean()

    slope = np.sum((x - x_mean) * (log_v - y_mean)) / np.sum((x - x_mean) ** 2)

    # Normalize by std for cross-sectional comparability
    normalized_slope = slope / std_log_v
    return normalized_slope


# -- Core backtest ---------------------------------------------------------

def backtest_volume_trend(closes, volumes, lb, rebal_freq, n, direction):
    """
    Volume Trend (Slope) Factor backtest.

    Args:
        closes: DataFrame of daily closes (assets as columns)
        volumes: DataFrame of daily volumes (assets as columns)
        lb: lookback window for volume slope
        rebal_freq: rebalance every N days
        n: number of longs and shorts
        direction: 'rising_long' or 'declining_long'
    Returns:
        pd.Series of daily portfolio returns (or None)
    """
    returns = closes.pct_change().dropna()
    dates = returns.index
    warmup = lb + 5  # need enough data for lookback

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    prev_weights = pd.Series(0.0, index=closes.columns)

    for i in range(warmup, len(dates)):
        # Apply existing weights to get day's return
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": day_ret})

        # Rebalance check
        if i - last_rebal >= rebal_freq:
            # Compute volume slope for each asset
            signals = {}
            for sym in closes.columns:
                vol_window = volumes[sym].iloc[max(0, i - lb):i].values
                if len(vol_window) < lb:
                    continue
                slope = compute_volume_slope(vol_window)
                if not np.isnan(slope):
                    signals[sym] = slope

            if len(signals) < 2 * n:
                continue

            signal_series = pd.Series(signals)

            if direction == "rising_long":
                # Long top-N (fastest rising volume), Short bottom-N
                ranked = signal_series.sort_values(ascending=False)
                longs = ranked.index[:n]
                shorts = ranked.index[-n:]
            else:  # declining_long
                # Long bottom-N (fastest declining volume), Short top-N
                ranked = signal_series.sort_values(ascending=True)
                longs = ranked.index[:n]
                shorts = ranked.index[-n:]

            new_weights = pd.Series(0.0, index=closes.columns)
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


def backtest_efficiency(closes, lookback=40, rebal_freq=5, n=4):
    """H-076 price efficiency factor."""
    rets = closes.pct_change().dropna()
    dates = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                p = closes[sym].iloc[i - lookback: i]
                net_move = abs(p.iloc[-1] / p.iloc[0] - 1)
                daily_moves = abs(p.pct_change().dropna()).sum()
                signals[sym] = net_move / daily_moves if daily_moves > 0 else 0.0
            ranked = pd.Series(signals).sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def backtest_trend_quality(closes, lookback=60, rebal_freq=5, n=3):
    """H-160 trend quality (efficiency x inv_vol)."""
    rets = closes.pct_change().dropna()
    dates = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                p = closes[sym].iloc[i - lookback: i]
                net_move = abs(p.iloc[-1] / p.iloc[0] - 1)
                daily_moves = abs(p.pct_change().dropna()).sum()
                eff = net_move / daily_moves if daily_moves > 0 else 0.0
                vol = rets[sym].iloc[max(0, i - lookback): i].std()
                inv_vol = 1.0 / vol if vol > 1e-8 else 0.0
                signals[sym] = eff * inv_vol
            ranked = pd.Series(signals).sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def backtest_h169(closes, lookback=10, rebal_freq=5, n=4):
    """H-169 beta-adjusted momentum (alpha vs BTC)."""
    if "BTC/USDT" not in closes.columns:
        return None
    btc = closes["BTC/USDT"]
    non_btc = [c for c in closes.columns if c != "BTC/USDT"]
    rets = closes.pct_change().dropna()
    dates = rets.index
    warmup = lookback + 10
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in non_btc:
                asset_r = closes[sym].pct_change().dropna().iloc[max(0, i - lookback): i]
                btc_r = btc.pct_change().dropna().iloc[max(0, i - lookback): i]
                common = asset_r.index.intersection(btc_r.index)
                if len(common) < lookback // 2:
                    continue
                a = asset_r.loc[common].values
                b = btc_r.loc[common].values
                var_b = np.var(b)
                if var_b < 1e-12:
                    continue
                beta = np.cov(a, b)[0, 1] / var_b
                alpha = a.sum() - beta * b.sum()
                signals[sym] = alpha
            if len(signals) >= n * 2:
                ranked = pd.Series(signals).sort_values(ascending=False)
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

def run_walk_forward(closes, volumes, best_direction):
    """
    6-fold walk-forward. For each fold, select best IS params from full grid
    on training data (within the best direction), then evaluate OOS.
    """
    n_total = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        oos_end = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break

        train_closes = closes.iloc[:oos_start]
        train_volumes = volumes.iloc[:oos_start]
        oos_closes = closes.iloc[oos_start:oos_end]
        oos_volumes = volumes.iloc[oos_start:oos_end]

        if len(train_closes) < WF_TRAIN_MIN or len(oos_closes) < 20:
            break

        # IS param selection on training data (within best direction)
        best_sharpe = -np.inf
        best_params = None
        for lb in LOOKBACKS:
            for rf in REBALS:
                for n in NS:
                    r = backtest_volume_trend(train_closes, train_volumes, lb, rf, n, best_direction)
                    ev = evaluate(r)
                    if ev and ev["sharpe"] > best_sharpe:
                        best_sharpe = ev["sharpe"]
                        best_params = (lb, rf, n)

        if best_params is None:
            fold_results.append({
                "fold": fold + 1, "is_params": "none", "is_sharpe": 0,
                "oos_sharpe": None, "oos_start": "", "oos_end": "",
            })
            continue

        lb, rf, n = best_params
        # OOS evaluation
        oos_r = backtest_volume_trend(oos_closes, oos_volumes, lb, rf, n, best_direction)
        oos_e = evaluate(oos_r)

        oos_start_date = closes.index[oos_start]
        oos_end_date = closes.index[min(oos_end - 1, len(closes) - 1)]

        fold_results.append({
            "fold":       fold + 1,
            "is_params":  f"LB{lb}_R{rf}_N{n}",
            "is_sharpe":  round(best_sharpe, 3),
            "oos_sharpe": oos_e["sharpe"] if oos_e else None,
            "oos_start":  str(oos_start_date)[:10],
            "oos_end":    str(oos_end_date)[:10],
        })

    return fold_results


# -- Split-half validation -------------------------------------------------

def run_split_half(closes, volumes, best_direction):
    """
    Run full grid on each half (within best direction).
    Report best-combo Sharpe for each half.
    """
    half = len(closes) // 2
    h1_closes = closes.iloc[:half]
    h1_volumes = volumes.iloc[:half]
    h2_closes = closes.iloc[half:]
    h2_volumes = volumes.iloc[half:]

    h1_results = []
    h2_results = []

    for lb in LOOKBACKS:
        for rf in REBALS:
            for n in NS:
                r1 = backtest_volume_trend(h1_closes, h1_volumes, lb, rf, n, best_direction)
                r2 = backtest_volume_trend(h2_closes, h2_volumes, lb, rf, n, best_direction)
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
        round(max(h1_sharpes), 3),      # best H1
        round(max(h2_sharpes), 3),      # best H2
        round(np.mean(h1_sharpes), 3),  # mean H1
        round(np.mean(h2_sharpes), 3),  # mean H2
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
    print("  H-177: Volume Trend (Slope) Factor")
    print("=" * 60)

    print("\nLoading daily data (closes + volumes)...")
    closes, volumes = load_daily_data()
    n_assets = len(closes.columns)
    n_days = len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")

    if n_assets < 8:
        print("ERROR: Too few assets. Aborting.")
        sys.exit(1)

    # ==================================================================
    # Stage 1: IS Parameter Scan (both directions)
    # ==================================================================
    combos_per_dir = len(LOOKBACKS) * len(REBALS) * len(NS)
    total_combos = combos_per_dir * len(DIRECTIONS)
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos total, {combos_per_dir} per direction) ---")

    all_results = []
    count = 0
    for direction in DIRECTIONS:
        for lb in LOOKBACKS:
            for rf in REBALS:
                for n in NS:
                    count += 1
                    r = backtest_volume_trend(closes, volumes, lb, rf, n, direction)
                    ev = evaluate(r, f"LB{lb}_R{rf}_N{n}_{direction}")
                    if ev:
                        ev["lb"] = lb
                        ev["rf"] = rf
                        ev["n"] = n
                        ev["direction"] = direction
                        all_results.append(ev)
                    if count % 10 == 0:
                        print(f"  {count}/{total_combos} done...")

    if not all_results:
        print("No valid results! REJECTED.")
        return

    df_res = pd.DataFrame(all_results)

    # Analyze by direction
    print(f"\n  IS Results by Direction:")
    dir_stats = {}
    for direction in DIRECTIONS:
        mask = df_res["direction"] == direction
        sub = df_res[mask]
        if len(sub) == 0:
            continue
        n_pos = (sub["sharpe"] > 0).sum()
        n_tot = len(sub)
        pct_pos = n_pos / n_tot * 100
        mean_s = sub["sharpe"].mean()
        median_s = sub["sharpe"].median()
        dir_stats[direction] = {
            "n_positive": int(n_pos),
            "n_total": int(n_tot),
            "pct_positive": round(pct_pos, 1),
            "mean_sharpe": round(mean_s, 3),
            "median_sharpe": round(median_s, 3),
        }
        print(f"    {direction}: {n_pos}/{n_tot} positive ({pct_pos:.1f}%), "
              f"mean Sharpe {mean_s:.3f}, median {median_s:.3f}")

    # Determine better direction
    better_dir = max(dir_stats.keys(), key=lambda d: dir_stats[d]["mean_sharpe"])
    worse_dir = [d for d in dir_stats.keys() if d != better_dir][0]
    print(f"\n  Better direction: {better_dir}")

    better_pct_pos = dir_stats[better_dir]["pct_positive"]
    better_mean_sharpe = dir_stats[better_dir]["mean_sharpe"]

    # Overall stats
    n_positive_all = (df_res["sharpe"] > 0).sum()
    n_total_all = len(df_res)
    pct_positive_all = n_positive_all / n_total_all * 100
    mean_sharpe_all = df_res["sharpe"].mean()

    # Top 10 overall
    print(f"\n  Top 10 combos (all directions):")
    for _, row in df_res.nlargest(10, "sharpe").iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}_{row['direction']}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    # Bottom 5
    print(f"\n  Bottom 5 combos:")
    for _, row in df_res.nsmallest(5, "sharpe").iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}_{row['direction']}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    # Best combo overall
    best_idx = df_res["sharpe"].idxmax()
    best = df_res.loc[best_idx]
    best_lb = int(best["lb"])
    best_rf = int(best["rf"])
    best_n = int(best["n"])
    best_dir = best["direction"]

    print(f"\n  Best combo: LB{best_lb}_R{best_rf}_N{best_n}_{best_dir}")
    print(f"  Sharpe: {best['sharpe']:.3f}, Annual: {best['annual']:.1f}%, Max DD: {best['dd']:.1f}%, Days: {int(best['days'])}")

    # IS gate: check the better direction's positive rate
    is_pass = better_pct_pos >= 80.0
    if not is_pass:
        print(f"\n*** FAIL IS: {better_dir} has {better_pct_pos:.1f}% positive < 80% threshold ***")
        print("REJECTED at Stage 1. Skipping further validation.")

        result_json = {
            "hypothesis": "H-177",
            "name": "Volume Trend (Slope) Factor",
            "status": "REJECTED",
            "reason": f"IS positive rate {better_pct_pos:.1f}% (better dir: {better_dir}) < 80% threshold",
            "is_positive_rate_better_dir": round(better_pct_pos, 1),
            "is_mean_sharpe_better_dir": round(better_mean_sharpe, 3),
            "is_positive_rate_all": round(pct_positive_all, 1),
            "is_mean_sharpe_all": round(mean_sharpe_all, 3),
            "better_direction": better_dir,
            "direction_stats": dir_stats,
            "best_params": {"lb": best_lb, "rebal": best_rf, "n": best_n, "direction": best_dir},
            "best_sharpe": round(float(best["sharpe"]), 3),
            "best_annual_return": round(float(best["annual"]), 1),
            "best_max_dd": round(float(best["dd"]), 1),
            "n_assets": n_assets,
            "n_days": n_days,
            "total_combos": total_combos,
            "valid_combos": n_total_all,
        }
        results_path = Path(__file__).parent / "results.json"
        with open(results_path, "w") as f:
            json.dump(result_json, f, indent=2)
        print(f"\nResults written to {results_path}")
        return

    print(f"\n  PASS IS: {better_dir} has {better_pct_pos:.1f}% positive (>= 80%)")

    # ==================================================================
    # Stage 2: Walk-Forward Validation (using better direction)
    # ==================================================================
    print(f"\n--- Stage 2: Walk-Forward ({WF_FOLDS} folds, {WF_TEST_DAYS}d OOS each) ---")
    print(f"  Using direction: {better_dir}")
    wf_results = run_walk_forward(closes, volumes, better_dir)

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
    print(f"  Using direction: {better_dir}")
    sh_best_h1, sh_best_h2, sh_mean_h1, sh_mean_h2 = run_split_half(closes, volumes, better_dir)

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
    # Stage 4: Correlation with Existing Factors
    # ==================================================================
    print(f"\n--- Stage 4: Correlation with Existing Factors ---")
    best_rets = backtest_volume_trend(closes, volumes, best_lb, best_rf, best_n, best_dir)

    print("  Computing reference strategy returns...")
    mom_rets = backtest_momentum(closes)
    eff_rets = backtest_efficiency(closes)
    tq_rets = backtest_trend_quality(closes)
    h169_rets = backtest_h169(closes)

    corr_h012 = safe_corr(best_rets, mom_rets)
    corr_h076 = safe_corr(best_rets, eff_rets)
    corr_h160 = safe_corr(best_rets, tq_rets)
    corr_h169 = safe_corr(best_rets, h169_rets)

    print(f"  H-012 (momentum):      {corr_h012:.3f}")
    print(f"  H-076 (efficiency):    {corr_h076:.3f}")
    print(f"  H-160 (trend quality): {corr_h160:.3f}")
    print(f"  H-169 (alpha mom):     {corr_h169:.3f}")

    max_abs_corr = max(
        abs(corr_h012) if not np.isnan(corr_h012) else 0,
        abs(corr_h076) if not np.isnan(corr_h076) else 0,
        abs(corr_h160) if not np.isnan(corr_h160) else 0,
        abs(corr_h169) if not np.isnan(corr_h169) else 0,
    )
    corr_pass = max_abs_corr < 0.40
    if not corr_pass:
        print(f"  *** FAIL Correlation: max |corr| = {max_abs_corr:.3f} >= 0.40 ***")
    else:
        print(f"  PASS: max |corr| = {max_abs_corr:.3f} < 0.40")

    # ==================================================================
    # Final Verdict
    # ==================================================================
    print(f"\n{'='*60}")
    print("  FINAL VERDICT")
    print(f"{'='*60}")
    print(f"  IS positive rate ({better_dir}): {better_pct_pos:.1f}% {'PASS' if is_pass else 'FAIL'}")
    print(f"  Walk-Forward: {wf_n_pos}/{len(wf_oos_sharpes)} positive {'PASS' if wf_pass else 'FAIL'}")
    print(f"  Split-Half: H1={sh_best_h1}, H2={sh_best_h2} {'PASS' if sh_pass else 'FAIL'}")
    print(f"  Correlation: max |corr|={max_abs_corr:.3f} {'PASS' if corr_pass else 'FAIL'}")

    all_pass = is_pass and wf_pass and sh_pass and corr_pass
    status = "CONFIRMED" if all_pass else "REJECTED"
    rejection_reasons = []
    if not is_pass:
        rejection_reasons.append(f"IS positive rate {better_pct_pos:.1f}% < 80%")
    if not wf_pass:
        rejection_reasons.append(f"WF {wf_n_pos}/{len(wf_oos_sharpes)} < 4/6")
    if not sh_pass:
        rejection_reasons.append(f"Split-half best Sharpes: H1={sh_best_h1}, H2={sh_best_h2}")
    if not corr_pass:
        rejection_reasons.append(f"max |corr| {max_abs_corr:.3f} >= 0.40")

    print(f"\n  Status: {status}")
    if rejection_reasons:
        print(f"  Reason: {'; '.join(rejection_reasons)}")
    else:
        print(f"  All 4 stages passed!")

    # ==================================================================
    # Write results.json
    # ==================================================================
    result_json = {
        "hypothesis": "H-177",
        "name": "Volume Trend (Slope) Factor",
        "status": status,
        "reason": "; ".join(rejection_reasons) if rejection_reasons else "All 4 stages passed",
        "is_positive_rate_better_dir": round(better_pct_pos, 1),
        "is_mean_sharpe_better_dir": round(better_mean_sharpe, 3),
        "is_positive_rate_all": round(pct_positive_all, 1),
        "is_mean_sharpe_all": round(mean_sharpe_all, 3),
        "better_direction": better_dir,
        "direction_stats": dir_stats,
        "best_params": {"lb": best_lb, "rebal": best_rf, "n": best_n, "direction": best_dir},
        "best_sharpe": round(float(best["sharpe"]), 3),
        "best_annual_return": round(float(best["annual"]), 1),
        "best_max_dd": round(float(best["dd"]), 1),
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
            "h1_best_sharpe": sh_best_h1,
            "h2_best_sharpe": sh_best_h2,
            "h1_mean_sharpe": sh_mean_h1,
            "h2_mean_sharpe": sh_mean_h2,
        },
        "correlations": {
            "H-012_momentum": corr_h012,
            "H-076_efficiency": corr_h076,
            "H-160_trend_quality": corr_h160,
            "H-169_alpha_momentum": corr_h169,
        },
        "max_abs_correlation": round(max_abs_corr, 3),
        "n_assets": n_assets,
        "n_days": n_days,
        "total_combos": total_combos,
        "valid_combos": n_total_all,
        "validation": {
            "is_pass": is_pass,
            "wf_pass": wf_pass,
            "sh_pass": sh_pass,
            "corr_pass": corr_pass,
        },
    }

    results_path = Path(__file__).parent / "results.json"
    with open(results_path, "w") as f:
        json.dump(result_json, f, indent=2)
    print(f"\nResults written to {results_path}")


if __name__ == "__main__":
    main()
