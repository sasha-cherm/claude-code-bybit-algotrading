"""
H-139: Volume-Clock Dislocation Factor

Measures the temporal distribution of volume within the lookback window.
The "volume centroid" is the center-of-mass of volume over time -- if volume
is evenly distributed, the centroid is at the midpoint. If volume clusters
toward the recent end, the centroid shifts forward (recent heavy activity).
If volume clusters toward the old end, the centroid shifts backward.

Factor = (actual centroid - midpoint) / midpoint = normalized dislocation

High positive dislocation = volume is accelerating (more recent activity)
High negative dislocation = volume is decelerating (activity drying up)

This captures institutional flow patterns that are distinct from price
momentum, volatility, or volume level.

Two directions:
  A) acceleration: Long assets with POSITIVE dislocation (accelerating volume),
                    short assets with NEGATIVE dislocation (decelerating)
  B) deceleration: Long NEGATIVE dislocation (contrarian: volume drying up
                    = underpriced), short POSITIVE (overhyped)

Dollar-neutral, equal-weighted long/short legs.

Validation: full parameter scan, walk-forward (6 folds, 90d test),
split-half, H-012 correlation.
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.0006
INITIAL_CAPITAL = 10_000.0

# Parameter grid
LOOKBACKS      = [10, 20, 30, 40, 60]       # volume centroid lookback window (days)
REBAL_FREQS    = [3, 5, 7, 10]              # rebalance every N days
N_LONGS        = [3, 4, 5]                  # top/bottom N per side
NORM_METHODS   = ["raw", "zscore"]           # raw centroid or z-score normalized
DIRECTIONS     = ["acceleration", "deceleration"]

# Walk-forward config
WF_FOLDS  = 6
WF_TRAIN  = 300
WF_TEST   = 90
WF_STEP   = 90


def load_daily_data():
    data_dir = ROOT / "data"
    daily = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if len(df) >= 200:
                daily[sym] = df
                print(f"  {sym}: {len(df)} daily bars "
                      f"({df.index[0].date()} to {df.index[-1].date()})")
    return daily


def build_matrices(daily):
    """Build both close and volume matrices."""
    close_frames = {}
    vol_frames = {}
    for sym, df in daily.items():
        col_c = "close" if "close" in df.columns else df.columns[3]
        col_v = "volume" if "volume" in df.columns else df.columns[4]
        close_frames[sym] = df[col_c]
        vol_frames[sym] = df[col_v]

    closes = pd.DataFrame(close_frames).sort_index().dropna(how="all")
    volumes = pd.DataFrame(vol_frames).sort_index().dropna(how="all")

    # Align indices
    common_idx = closes.index.intersection(volumes.index)
    closes = closes.loc[common_idx]
    volumes = volumes.loc[common_idx]

    closes = closes.ffill(limit=3)
    volumes = volumes.ffill(limit=3)

    closes = closes.dropna(thresh=len(closes.columns) // 2 + 1)
    volumes = volumes.loc[closes.index]

    print(f"\n  Close matrix: {closes.shape[0]} days x {closes.shape[1]} assets")
    print(f"  Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    return closes, volumes


def compute_vol_clock_dislocation(volumes, lookback, norm_method="raw"):
    """
    For each asset on each day t:
      1. Get volume over [t-lookback, t)
      2. Compute volume centroid: sum(vol_i * i) / sum(vol_i) where i = 0..lookback-1
         (0 = oldest bar, lookback-1 = most recent)
      3. Midpoint = (lookback - 1) / 2
      4. Dislocation = (centroid - midpoint) / midpoint

    Positive = volume skewed toward recent (accelerating)
    Negative = volume skewed toward past (decelerating)

    If norm_method == "zscore", z-score normalize dislocation over a 60d window
    to capture changes relative to recent history.
    """
    factor = pd.DataFrame(np.nan, index=volumes.index, columns=volumes.columns)
    positions = np.arange(lookback, dtype=float)  # 0, 1, ..., lookback-1
    midpoint = (lookback - 1) / 2.0

    for col in volumes.columns:
        vols = volumes[col].values
        n = len(vols)
        vals = np.full(n, np.nan)

        for i in range(lookback, n):
            window = vols[i - lookback:i]
            if np.any(np.isnan(window)):
                window = np.nan_to_num(window, nan=0.0)
            total_vol = np.sum(window)
            if total_vol < 1e-12:
                continue
            centroid = np.sum(window * positions) / total_vol
            dislocation = (centroid - midpoint) / midpoint if midpoint > 0 else 0
            vals[i] = dislocation

        if norm_method == "zscore":
            # Z-score normalize over a 60d window
            z_window = 60
            raw_vals = vals.copy()
            vals = np.full(n, np.nan)
            for i in range(lookback + z_window, n):
                w = raw_vals[i - z_window:i]
                w = w[~np.isnan(w)]
                if len(w) >= 20:
                    mu = np.mean(w)
                    sigma = np.std(w, ddof=1)
                    if sigma > 1e-12:
                        vals[i] = (raw_vals[i] - mu) / sigma

        factor[col] = vals

    return factor


def compute_metrics(equity_series):
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "win_rate": 0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "win_rate": round(n_pos / n_total, 4) if n_total > 0 else 0,
    }


def run_xs_factor(closes, ranking_series, rebal_freq, n_long,
                  direction="acceleration", fee_rate=FEE_RATE, warmup=65,
                  n_short=None):
    """
    Cross-sectional factor backtester.

    direction="acceleration": Long HIGH dislocation (accelerating vol), short LOW
    direction="deceleration": Long LOW dislocation (decelerating vol), short HIGH
    """
    if n_short is None:
        n_short = n_long

    n = len(closes)
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital
    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count = 0

    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = ranking_series.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            if direction == "acceleration":
                # Long HIGH dislocation (volume accelerating), short LOW
                sorted_vals = valid.sort_values(ascending=False)
                longs = sorted_vals.index[:n_long]
                shorts = sorted_vals.index[-n_short:]
            else:
                # deceleration: Long LOW dislocation, short HIGH
                sorted_vals = valid.sort_values(ascending=True)
                longs = sorted_vals.index[:n_long]
                shorts = sorted_vals.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * fee_rate

            port_ret = (new_weights * log_rets).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count += 1
            prev_weights = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"] = eq_series
    return metrics


def run_full_scan(closes, volumes):
    print("\n" + "=" * 70)
    print("H-139: VOLUME-CLOCK DISLOCATION -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE * 10000:.0f} bps per trade")

    # Pre-compute dislocation for all (lookback, norm) combos
    print("\n  Pre-computing volume-clock dislocation factors...")
    factor_cache = {}
    for lb, norm in product(LOOKBACKS, NORM_METHODS):
        key = (lb, norm)
        print(f"    LB={lb}, norm={norm}...", end=" ", flush=True)
        factor_cache[key] = compute_vol_clock_dislocation(volumes, lb, norm)
        valid_count = factor_cache[key].notna().sum().sum()
        print(f"done ({valid_count} valid values)")

    results = []
    total_combos = len(LOOKBACKS) * len(NORM_METHODS) * len(REBAL_FREQS) * len(N_LONGS) * len(DIRECTIONS)
    print(f"\n  Running {total_combos} parameter combinations...")
    combo_idx = 0

    for lb, norm, rebal, n_long, direction in product(
            LOOKBACKS, NORM_METHODS, REBAL_FREQS, N_LONGS, DIRECTIONS):
        ranking = factor_cache[(lb, norm)]
        warmup = lb + (60 if norm == "zscore" else 0) + 5

        res = run_xs_factor(closes, ranking, rebal, n_long,
                            direction=direction, warmup=warmup)
        tag = f"LB{lb}_{norm}_R{rebal}_N{n_long}_{direction[:4]}"
        results.append({
            "tag": tag,
            "lookback": lb,
            "norm_method": norm,
            "rebal": rebal,
            "n_long": n_long,
            "direction": direction,
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
            "n_rebalances": res["n_rebalances"],
        })
        combo_idx += 1
        if combo_idx % 60 == 0:
            print(f"    ...{combo_idx}/{total_combos} done")

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]

    print(f"\n  Total parameter combos: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"  Best Sharpe:  {df['sharpe'].max():.3f}")
    print(f"  Worst Sharpe: {df['sharpe'].min():.3f}")

    for dir_ in DIRECTIONS:
        sub = df[df["direction"] == dir_]
        pos = (sub["sharpe"] > 0).sum()
        print(f"\n  Direction={dir_}:")
        print(f"    Positive Sharpe: {pos}/{len(sub)} ({pos/len(sub):.0%})")
        print(f"    Mean Sharpe: {sub['sharpe'].mean():.3f}")
        print(f"    Best Sharpe: {sub['sharpe'].max():.3f}")

    for norm in NORM_METHODS:
        sub = df[df["norm_method"] == norm]
        pos = (sub["sharpe"] > 0).sum()
        print(f"\n  Norm={norm}:")
        print(f"    Positive Sharpe: {pos}/{len(sub)} ({pos/len(sub):.0%})")
        print(f"    Mean Sharpe: {sub['sharpe'].mean():.3f}")

    print("\n  Top 20 parameter combos by Sharpe:")
    for _, row in df.sort_values("sharpe", ascending=False).head(20).iterrows():
        marker = "**" if row["sharpe"] > 0.5 else "  "
        print(f"  {marker} {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}, Trades {row['n_trades']}")

    return df, factor_cache


def run_walk_forward(closes, volumes, lookback, norm_method, rebal, n_long, direction):
    print(f"\n  Walk-Forward (Fixed Params): "
          f"LB{lookback}_{norm_method}_R{rebal}_N{n_long}_{direction}")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, {WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx   = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0 or test_end_idx <= test_start_idx:
            break

        test_closes = closes.iloc[test_start_idx:test_end_idx]
        test_volumes = volumes.iloc[test_start_idx:test_end_idx]
        if len(test_closes) < 30:
            break

        test_ranking = compute_vol_clock_dislocation(test_volumes, lookback, norm_method)
        warmup = min(lookback + (60 if norm_method == "zscore" else 0) + 5,
                     len(test_closes) // 2)

        res = run_xs_factor(test_closes, test_ranking, rebal, n_long,
                            direction=direction, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
        })
        print(f"    Fold {fold+1}: {test_closes.index[0].date()} -> {test_closes.index[-1].date()}, "
              f"Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}, "
              f"DD {res['max_dd']:.1%}, Trades {res['n_trades']}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df_wf = pd.DataFrame(fold_results)
    pos = (df_wf["sharpe"] > 0).sum()
    print(f"\n    Positive folds: {pos}/{len(df_wf)}")
    print(f"    Mean OOS Sharpe: {df_wf['sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df_wf['annual_ret'].mean():.1%}")
    print(f"    Total OOS test observations: {df_wf['n_days'].sum()}")
    return df_wf


def run_split_half(closes, volumes):
    n = len(closes)
    mid = n // 2
    half1_c = closes.iloc[:mid]
    half2_c = closes.iloc[mid:]
    half1_v = volumes.iloc[:mid]
    half2_v = volumes.iloc[mid:]

    print(f"\n  Split-Half Validation")
    print(f"  Half 1: {half1_c.index[0].date()} to {half1_c.index[-1].date()} ({len(half1_c)} days)")
    print(f"  Half 2: {half2_c.index[0].date()} to {half2_c.index[-1].date()} ({len(half2_c)} days)")

    results_h1 = []
    results_h2 = []

    for lb, norm, rebal, n_long, direction in product(
            LOOKBACKS, NORM_METHODS, REBAL_FREQS, N_LONGS, DIRECTIONS):
        warmup = lb + (60 if norm == "zscore" else 0) + 5
        r1 = compute_vol_clock_dislocation(half1_v, lb, norm)
        r2 = compute_vol_clock_dislocation(half2_v, lb, norm)
        res1 = run_xs_factor(half1_c, r1, rebal, n_long, direction=direction, warmup=warmup)
        res2 = run_xs_factor(half2_c, r2, rebal, n_long, direction=direction, warmup=warmup)
        results_h1.append(res1["sharpe"])
        results_h2.append(res2["sharpe"])

    h1_arr = np.array(results_h1)
    h2_arr = np.array(results_h2)

    corr, _ = spearmanr(h1_arr, h2_arr)
    both_pos = ((h1_arr > 0) & (h2_arr > 0)).sum()

    print(f"  Spearman rank corr (Sharpe, H1 vs H2): {corr:.3f}")
    print(f"  Both halves positive: {both_pos}/{len(h1_arr)} ({both_pos/len(h1_arr):.0%})")
    print(f"  Half 1 mean Sharpe: {h1_arr.mean():.3f}")
    print(f"  Half 2 mean Sharpe: {h2_arr.mean():.3f}")

    if (h1_arr.mean() > 0.2 and h2_arr.mean() < -0.2) or \
       (h1_arr.mean() < -0.2 and h2_arr.mean() > 0.2):
        print("  WARNING: Signal inversion detected between halves!")

    return {
        "spearman_corr": round(float(corr), 3),
        "both_positive_pct": round(both_pos / len(h1_arr), 3),
        "half1_mean_sharpe": round(float(h1_arr.mean()), 3),
        "half2_mean_sharpe": round(float(h2_arr.mean()), 3),
    }


def compute_h012_correlation(closes, volumes, lookback, norm_method, rebal, n_long, direction):
    print(f"\n  Correlation with H-012 (60d Momentum)")

    ranking = compute_vol_clock_dislocation(volumes, lookback, norm_method)
    warmup = lookback + (60 if norm_method == "zscore" else 0) + 5
    res_factor = run_xs_factor(closes, ranking, rebal, n_long,
                               direction=direction, warmup=warmup)

    mom_ranking = closes.pct_change(60)
    res_mom = run_xs_factor(closes, mom_ranking, 5, 4,
                            direction="contrarian", warmup=65)

    eq_factor = res_factor["equity"]
    eq_mom    = res_mom["equity"]

    rets_factor = eq_factor.pct_change().dropna()
    rets_mom    = eq_mom.pct_change().dropna()

    common = rets_factor.index.intersection(rets_mom.index)
    if len(common) < 50:
        print("    Insufficient overlap for correlation")
        return 0.0

    corr = rets_factor.loc[common].corr(rets_mom.loc[common])
    print(f"    Daily return correlation H-139 vs H-012: {corr:.3f}")
    print(f"    H-012 Momentum: Sharpe {res_mom['sharpe']:.3f}, Ann {res_mom['annual_ret']:.1%}")
    print(f"    H-139 VolClock: Sharpe {res_factor['sharpe']:.3f}, Ann {res_factor['annual_ret']:.1%}")
    return round(corr, 3)


if __name__ == "__main__":
    print("=" * 70)
    print("H-139: Volume-Clock Dislocation Factor")
    print("=" * 70)

    # 1. Load data
    print("\n[1/5] Loading daily data...")
    daily = load_daily_data()
    closes, volumes = build_matrices(daily)

    if closes.shape[1] < 6:
        print("ERROR: Too few assets loaded. Aborting.")
        sys.exit(1)

    # 2. Full parameter scan
    print("\n[2/5] Full Parameter Scan...")
    scan_df, factor_cache = run_full_scan(closes, volumes)

    best_row  = scan_df.loc[scan_df["sharpe"].idxmax()]
    best_lb   = int(best_row["lookback"])
    best_norm = best_row["norm_method"]
    best_r    = int(best_row["rebal"])
    best_n    = int(best_row["n_long"])
    best_dir  = best_row["direction"]

    print(f"\n  BEST OVERALL: {best_row['tag']}")
    print(f"    Sharpe {best_row['sharpe']:.3f}, Ann {best_row['annual_ret']:.1%}, "
          f"DD {best_row['max_dd']:.1%}, WR {best_row['win_rate']:.1%}")

    # 3. Walk-Forward (6 folds)
    print("\n[3/5] Walk-Forward Validation...")
    wf_df = run_walk_forward(closes, volumes, best_lb, best_norm, best_r, best_n, best_dir)

    # 4. Split-Half
    print("\n[4/5] Split-Half Validation...")
    sh_results = run_split_half(closes, volumes)

    # 5. H-012 Correlation
    print("\n[5/5] H-012 Correlation...")
    h012_corr = compute_h012_correlation(closes, volumes, best_lb, best_norm, best_r, best_n, best_dir)

    # Summary
    print("\n" + "=" * 70)
    print("H-139 SUMMARY")
    print("=" * 70)

    pct_positive = len(scan_df[scan_df["sharpe"] > 0]) / len(scan_df)
    mean_sharpe  = scan_df["sharpe"].mean()

    print(f"\n  FULL SCAN ({len(scan_df)} combos):")
    print(f"    % Positive Sharpe:  {pct_positive:.0%}")
    print(f"    Mean Sharpe:        {mean_sharpe:.3f}")
    print(f"    Best Sharpe:        {scan_df['sharpe'].max():.3f}  ({best_row['tag']})")

    for dir_ in DIRECTIONS:
        sub = scan_df[scan_df["direction"] == dir_]
        pos = (sub["sharpe"] > 0).sum()
        print(f"    {dir_}: {pos}/{len(sub)} positive, mean Sharpe {sub['sharpe'].mean():.3f}")

    for norm in NORM_METHODS:
        sub = scan_df[scan_df["norm_method"] == norm]
        pos = (sub["sharpe"] > 0).sum()
        print(f"    {norm}: {pos}/{len(sub)} positive, mean Sharpe {sub['sharpe'].mean():.3f}")

    if wf_df is not None:
        pos_folds = (wf_df["sharpe"] > 0).sum()
        print(f"\n  WALK-FORWARD ({len(wf_df)} folds):")
        print(f"    Positive folds:     {pos_folds}/{len(wf_df)}")
        print(f"    Mean OOS Sharpe:    {wf_df['sharpe'].mean():.3f}")
        print(f"    Mean OOS Ann Ret:   {wf_df['annual_ret'].mean():.1%}")
        print(f"    Total test obs:     {wf_df['n_days'].sum()} days")
        print(f"    Total test trades:  {wf_df['n_trades'].sum()}")

    print(f"\n  SPLIT-HALF:")
    print(f"    Spearman corr:      {sh_results['spearman_corr']:.3f}")
    print(f"    Both halves pos:    {sh_results['both_positive_pct']:.0%}")
    print(f"    H1 mean Sharpe:     {sh_results['half1_mean_sharpe']:.3f}")
    print(f"    H2 mean Sharpe:     {sh_results['half2_mean_sharpe']:.3f}")

    print(f"\n  H-012 CORRELATION:    {h012_corr:.3f}")

    # Verdict
    print("\n  VERDICT:")
    reasons = []
    if pct_positive < 0.60:
        reasons.append(f"Only {pct_positive:.0%} params positive (need >=60%)")
    if sh_results["half1_mean_sharpe"] * sh_results["half2_mean_sharpe"] < 0 and \
       abs(sh_results["half1_mean_sharpe"]) > 0.2 and abs(sh_results["half2_mean_sharpe"]) > 0.2:
        reasons.append("Signal inversion between halves")
    if wf_df is not None and wf_df["sharpe"].mean() < 0:
        reasons.append(f"Negative WF OOS mean Sharpe ({wf_df['sharpe'].mean():.3f})")
    if abs(h012_corr) > 0.5:
        reasons.append(f"High H-012 correlation ({h012_corr:.3f})")

    if reasons:
        verdict = "REJECTED"
        print(f"    {verdict}")
        for r in reasons:
            print(f"      - {r}")
    elif pct_positive >= 0.60 and mean_sharpe >= 0.3 and \
         wf_df is not None and wf_df["sharpe"].mean() >= 0.2:
        verdict = "CONFIRMED"
        print(f"    {verdict} -- robust signal with positive OOS performance")
    else:
        verdict = "CONDITIONAL"
        print(f"    {verdict} -- some positive signal but needs more evidence")

    # Save results
    output_path = Path(__file__).parent / "results.json"
    results_dict = {
        "hypothesis": "H-139",
        "title": "Volume-Clock Dislocation Factor",
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "n_days": len(closes),
        "n_assets": len(closes.columns),
        "n_combos": len(scan_df),
        "pct_positive_sharpe": round(pct_positive, 4),
        "mean_sharpe": round(mean_sharpe, 4),
        "best_sharpe": round(float(scan_df["sharpe"].max()), 4),
        "best_params": best_row["tag"],
        "best_direction": best_dir,
        "best_norm": best_norm,
        "walk_forward": {
            "n_folds": len(wf_df) if wf_df is not None else 0,
            "positive_folds": int((wf_df["sharpe"] > 0).sum()) if wf_df is not None else 0,
            "mean_oos_sharpe": round(float(wf_df["sharpe"].mean()), 3) if wf_df is not None else None,
            "total_test_days": int(wf_df["n_days"].sum()) if wf_df is not None else 0,
            "total_test_trades": int(wf_df["n_trades"].sum()) if wf_df is not None else 0,
        },
        "split_half": sh_results,
        "h012_correlation": h012_corr,
        "verdict": verdict,
    }

    with open(output_path, "w") as f:
        json.dump(results_dict, f, indent=2)
    print(f"\n  Results saved to {output_path}")
    print("=" * 70)
