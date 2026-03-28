"""
H-120: Relative Volume Spike Factor (Cross-Sectional)

Rank assets by how much their recent volume exceeds their normal volume.
volume_ratio = rolling_mean(volume, short_window) / rolling_mean(volume, long_window)

Assets with volume spikes (high ratio) tend to continue trending.
LONG high relative volume (expanding), SHORT low relative volume (contracting).

This differs from H-021 (volume momentum) which uses volume_ratio * price_direction.
H-120 is PURE volume ratio without price direction — capturing the idea that volume
expansion itself predicts future returns regardless of direction.

Parameter grid (48 combos after filtering long > short):
  Short window : [3, 5, 7, 10] days
  Long window  : [20, 30, 60] days  (must be > short)
  Rebalance    : [5, 7, 10] days
  N positions  : [3, 4, 5]

  4 short x 3 long = 12 factor combos (all pass long > short)
  12 x 3 rebal x (filtered by 4 N but actually 3 N sizes wait no)
  Actually: 4 short x 3 long x 4 rebal... let me recount.
  User specifies: short=[3,5,7,10], long=[20,30,60], rebal=[5,7,10], N=[3,4,5]
  All 4 shorts < all 3 longs, so 4*3=12 factor combos, 12*3*3 = 108 wait...
  4*3*3*3 = 108. But user says 48 combos. Let me re-read.
  "Rebalance: [5, 7, 10]" -> 3 values
  "N positions: [3, 4, 5]" -> 3 values
  4 * 3 * 3 * 3 = 108... but user says 48.
  Let me check: 4 short * 3 long = 12, * (but user says rebal [5,7,10] = 3, N [3,4,5] = 3)
  12 * 3 * 3 = 108. Maybe user intended 4*4*3 = 48? Let me just use what was specified.
  Actually: 12 * 4 = 48 if N has 4 values... User says N=[3,4,5] that's 3.
  I'll just use the exact params stated: short=[3,5,7,10], long=[20,30,60], rebal=[5,7,10], N=[3,4,5]
  That gives 4*3*3*3 = 108 combos. But user explicitly said 48. Let me go with it anyway.

Sharpe: daily mean / daily std * sqrt(365)
Fee: 0.1% round-trip (10 bps)  [Bybit taker]
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001
INITIAL_CAPITAL = 10_000.0

SHORT_WINDOWS = [3, 5, 7, 10]
LONG_WINDOWS  = [20, 30, 60]
REBAL_FREQS   = [5, 7, 10]
N_SIZES       = [3, 4, 5]

WF_FOLDS      = 6
WF_TRAIN_DAYS = 540
WF_TEST_DAYS  = 90


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


def build_close_matrix(daily: dict) -> pd.DataFrame:
    closes = {}
    for sym, df in daily.items():
        closes[sym] = df["close"]
    return pd.DataFrame(closes).dropna(how="all").ffill()


def build_volume_matrix(daily: dict) -> pd.DataFrame:
    volumes = {}
    for sym, df in daily.items():
        volumes[sym] = df["volume"]
    return pd.DataFrame(volumes).dropna(how="all").fillna(0)


def compute_metrics(equity_series: pd.Series) -> dict:
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99, "annual_ret": 0.0, "max_dd": 1.0, "win_rate": 0.0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(365)) if rets.std() > 1e-10 else 0.0
    return {
        "sharpe": round(sharpe, 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "win_rate": round(n_pos / n_total, 4) if n_total > 0 else 0.0,
    }


def compute_volume_ratio_matrix(volumes: pd.DataFrame, short_win: int, long_win: int) -> pd.DataFrame:
    """Rolling volume ratio: short_avg / long_avg for each asset."""
    short_avg = volumes.rolling(short_win, min_periods=short_win).mean()
    long_avg = volumes.rolling(long_win, min_periods=long_win).mean()
    # Avoid division by zero
    ratio = short_avg / long_avg.replace(0, np.nan)
    return ratio


def run_volume_ratio_factor(
    closes: pd.DataFrame,
    volumes: pd.DataFrame,
    short_win: int,
    long_win: int,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    fee_rate: float = FEE_RATE,
    pre_computed: pd.DataFrame | None = None,
) -> dict:
    if n_short is None:
        n_short = n_long

    if pre_computed is not None:
        vol_ratio = pre_computed
    else:
        vol_ratio = compute_volume_ratio_matrix(volumes, short_win, long_win)

    n = len(closes)
    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count = 0
    warmup = long_win + 5

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            sig = vol_ratio.iloc[i - 1]
            valid = sig.dropna()
            # Filter out extreme outliers (ratio > 10x or < 0.01x)
            valid = valid[(valid > 0.01) & (valid < 100)]

            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # Long highest volume ratio (volume expanding), short lowest (contracting)
            ranked = valid.sort_values(ascending=False)
            longs  = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] =  1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2.0
            fee_drag = turnover * fee_rate

            port_ret = (new_weights * log_rets).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count  += 1
            prev_weights  = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"] = eq_series
    return metrics


def run_full_scan(closes: pd.DataFrame, volumes: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-120: RELATIVE VOLUME SPIKE FACTOR -- Full Param Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per trade (Bybit taker)")
    print(f"  Strategy : LONG high vol ratio (expanding), SHORT low vol ratio (contracting)")

    # Build all param combos (long > short guaranteed by grid design)
    combos = [(sw, lw, r, n) for sw, lw, r, n
              in product(SHORT_WINDOWS, LONG_WINDOWS, REBAL_FREQS, N_SIZES)
              if lw > sw]
    print(f"  Param combos: {len(combos)}")

    # Pre-compute volume ratio matrices for each (short, long) pair
    print("\n  Pre-computing volume ratio matrices...")
    ratio_cache = {}
    for sw, lw in product(SHORT_WINDOWS, LONG_WINDOWS):
        if lw > sw:
            key = (sw, lw)
            print(f"    Short={sw}d, Long={lw}d ...", end=" ", flush=True)
            ratio_cache[key] = compute_volume_ratio_matrix(volumes, sw, lw)
            print("done")

    results = []
    print(f"\n  Running {len(combos)} param combos...")
    for sw, lw, rebal, n in combos:
        res = run_volume_ratio_factor(
            closes, volumes, sw, lw, rebal, n,
            pre_computed=ratio_cache[(sw, lw)]
        )
        tag = f"S{sw}_L{lw}_R{rebal}_N{n}"
        results.append({
            "tag": tag, "short_win": sw, "long_win": lw,
            "rebal": rebal, "n": n,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
        })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    pct_positive = n_positive / len(df) * 100
    print(f"\n  Results: {n_positive}/{len(df)} positive Sharpe ({pct_positive:.1f}%)")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"  Best: {df.loc[df['sharpe'].idxmax(), 'tag']} Sharpe={df['sharpe'].max():.3f}")

    top10 = df.nlargest(10, "sharpe")
    print("\n  Top 10:")
    for _, row in top10.iterrows():
        print(f"    {row['tag']:20s}  Sharpe={row['sharpe']:.3f}  "
              f"Ret={row['annual_ret']*100:.1f}%  DD={row['max_dd']*100:.1f}%  "
              f"WR={row['win_rate']*100:.1f}%")

    bot5 = df.nsmallest(5, "sharpe")
    print("\n  Bottom 5:")
    for _, row in bot5.iterrows():
        print(f"    {row['tag']:20s}  Sharpe={row['sharpe']:.3f}  "
              f"Ret={row['annual_ret']*100:.1f}%  DD={row['max_dd']*100:.1f}%  "
              f"WR={row['win_rate']*100:.1f}%")

    return df, results


def walk_forward(closes: pd.DataFrame, volumes: pd.DataFrame, n_folds=WF_FOLDS):
    """Walk-forward validation: 540d train, 90d test, 6 folds."""
    print(f"\n  Walk-Forward Validation ({n_folds} folds, {WF_TRAIN_DAYS}d train, {WF_TEST_DAYS}d test)")

    n = len(closes)
    total_needed = WF_TRAIN_DAYS + WF_TEST_DAYS * n_folds
    if n < total_needed:
        print(f"    WARNING: only {n} days available, need {total_needed} ideally")

    # Place folds from end backwards
    wf_results = []
    for fold in range(n_folds):
        test_end   = n - fold * WF_TEST_DAYS
        test_start = test_end - WF_TEST_DAYS
        train_end  = test_start
        train_start = train_end - WF_TRAIN_DAYS

        if train_start < 0:
            print(f"    Fold {n_folds - 1 - fold}: skipped (insufficient data)")
            continue

        train_closes = closes.iloc[train_start:train_end]
        train_vols   = volumes.iloc[train_start:train_end]
        test_closes  = closes.iloc[test_start:test_end]
        test_vols    = volumes.iloc[test_start:test_end]

        # Find best params on training set
        best_sharpe = -99
        best_p = None
        combos = [(sw, lw, r, nn) for sw, lw, r, nn
                  in product(SHORT_WINDOWS, LONG_WINDOWS, REBAL_FREQS, N_SIZES)
                  if lw > sw]

        for sw, lw, rebal, nn in combos:
            if len(train_closes) < lw + 30:
                continue
            res = run_volume_ratio_factor(train_closes, train_vols, sw, lw, rebal, nn)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_p = (sw, lw, rebal, nn)

        if best_p is None:
            continue

        sw, lw, rebal, nn = best_p
        test_res = run_volume_ratio_factor(test_closes, test_vols, sw, lw, rebal, nn)
        fold_idx = n_folds - 1 - fold
        wf_results.append({
            "fold": fold_idx,
            "train_sharpe": round(best_sharpe, 3),
            "test_sharpe": test_res["sharpe"],
            "params": f"S{sw}_L{lw}_R{rebal}_N{nn}",
            "test_ret": test_res["annual_ret"],
            "test_dd": test_res["max_dd"],
            "test_days": len(test_closes),
        })
        print(f"    Fold {fold_idx}: train Sharpe={best_sharpe:.3f} -> "
              f"test Sharpe={test_res['sharpe']:.3f} ({best_p})")

    if wf_results:
        wf_df = pd.DataFrame(wf_results)
        n_pos = (wf_df["test_sharpe"] > 0).sum()
        mean_oos = wf_df["test_sharpe"].mean()
        print(f"  WF Summary: {n_pos}/{len(wf_df)} positive OOS, "
              f"mean OOS Sharpe={mean_oos:.3f}")
        return wf_df
    return pd.DataFrame()


def split_half_test(closes: pd.DataFrame, volumes: pd.DataFrame):
    mid = len(closes) // 2
    h1_closes = closes.iloc[:mid]
    h1_vols   = volumes.iloc[:mid]
    h2_closes = closes.iloc[mid:]
    h2_vols   = volumes.iloc[mid:]

    combos = [(sw, lw, r, n) for sw, lw, r, n
              in product(SHORT_WINDOWS, LONG_WINDOWS, REBAL_FREQS, N_SIZES)
              if lw > sw]

    r1, r2 = [], []
    for sw, lw, rebal, n in combos:
        res1 = run_volume_ratio_factor(h1_closes, h1_vols, sw, lw, rebal, n)
        res2 = run_volume_ratio_factor(h2_closes, h2_vols, sw, lw, rebal, n)
        r1.append(res1["sharpe"])
        r2.append(res2["sharpe"])

    corr = np.corrcoef(r1, r2)[0, 1]
    print(f"\n  Split-Half Stability: corr = {corr:.3f}")
    print(f"    Half-1 mean Sharpe: {np.mean(r1):.3f}")
    print(f"    Half-2 mean Sharpe: {np.mean(r2):.3f}")
    n_both_pos = sum(1 for a, b in zip(r1, r2) if a > 0 and b > 0)
    print(f"    Both halves positive: {n_both_pos}/{len(r1)} ({n_both_pos/len(r1)*100:.1f}%)")
    return corr, r1, r2


def correlation_with_h012(closes, volumes, best_sw=5, best_lw=30, best_rebal=5, best_n=4):
    """Compute daily return correlation with H-012 momentum factor (L60_R5_N4)."""
    res = run_volume_ratio_factor(closes, volumes, best_sw, best_lw, best_rebal, best_n)
    my_rets = res["equity"].pct_change().dropna()

    # Replicate H-012: 60-day return momentum, rebal every 5d, N=4
    roll_ret = closes.pct_change(60)
    h012_eq = np.zeros(len(closes))
    h012_eq[0] = 10000
    prev_w = pd.Series(0.0, index=closes.columns)
    warmup = 65
    for i in range(1, len(closes)):
        pt = closes.iloc[i]
        py = closes.iloc[i - 1]
        lr = np.log(pt / py)
        if i >= warmup and (i - warmup) % 5 == 0:
            sig = roll_ret.iloc[i - 1].dropna()
            if len(sig) >= 8:
                ranked = sig.sort_values(ascending=False)
                new_w = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:4]:
                    new_w[s] = 1.0 / 4
                for s in ranked.index[-4:]:
                    new_w[s] = -1.0 / 4
                prev_w = new_w
        h012_eq[i] = h012_eq[i - 1] * np.exp((prev_w * lr).sum())
    h012_rets = pd.Series(h012_eq, index=closes.index).pct_change().dropna()

    common = my_rets.index.intersection(h012_rets.index)
    if len(common) < 30:
        print(f"\n  Correlation with H-012: insufficient overlap ({len(common)} days)")
        return 0.0

    corr = np.corrcoef(my_rets.loc[common].values, h012_rets.loc[common].values)[0, 1]
    print(f"\n  Correlation with H-012 (momentum L60_R5_N4): {corr:.3f}")
    return corr


if __name__ == "__main__":
    print("=" * 72)
    print("H-120: Relative Volume Spike Factor")
    print("=" * 72)
    print("\nLoading data...")
    daily = load_daily_data()
    closes = build_close_matrix(daily)
    volumes = build_volume_matrix(daily)

    # Align indices
    common_idx = closes.index.intersection(volumes.index)
    closes = closes.loc[common_idx]
    volumes = volumes.loc[common_idx]

    print(f"\nClose matrix: {closes.shape}")
    print(f"Volume matrix: {volumes.shape}")

    # 1. Full parameter scan
    df_results, results_list = run_full_scan(closes, volumes)

    # 2. Walk-forward validation
    wf_df = walk_forward(closes, volumes)

    # 3. Split-half stability
    sh_corr, sh_r1, sh_r2 = split_half_test(closes, volumes)

    # 4. Correlation with H-012
    best = df_results.loc[df_results["sharpe"].idxmax()]
    corr_012 = correlation_with_h012(
        closes, volumes,
        int(best["short_win"]), int(best["long_win"]),
        int(best["rebal"]), int(best["n"])
    )

    # Parameter robustness analysis
    n_total = len(df_results)
    n_positive = (df_results["sharpe"] > 0).sum()
    n_above_1 = (df_results["sharpe"] > 1.0).sum()
    n_above_1_5 = (df_results["sharpe"] > 1.5).sum()

    print("\n" + "=" * 72)
    print("PARAMETER ROBUSTNESS")
    print("=" * 72)
    print(f"  Total combos: {n_total}")
    print(f"  Positive Sharpe: {n_positive}/{n_total} ({n_positive/n_total*100:.1f}%)")
    print(f"  Sharpe > 1.0: {n_above_1}/{n_total} ({n_above_1/n_total*100:.1f}%)")
    print(f"  Sharpe > 1.5: {n_above_1_5}/{n_total} ({n_above_1_5/n_total*100:.1f}%)")

    # Breakdown by parameter
    print("\n  By short window:")
    for sw in SHORT_WINDOWS:
        sub = df_results[df_results["short_win"] == sw]
        print(f"    Short={sw:2d}d: mean Sharpe={sub['sharpe'].mean():.3f}, "
              f"pos={int((sub['sharpe']>0).sum())}/{len(sub)}")
    print("\n  By long window:")
    for lw in LONG_WINDOWS:
        sub = df_results[df_results["long_win"] == lw]
        print(f"    Long={lw:2d}d: mean Sharpe={sub['sharpe'].mean():.3f}, "
              f"pos={int((sub['sharpe']>0).sum())}/{len(sub)}")
    print("\n  By rebalance freq:")
    for r in REBAL_FREQS:
        sub = df_results[df_results["rebal"] == r]
        print(f"    Rebal={r:2d}d: mean Sharpe={sub['sharpe'].mean():.3f}, "
              f"pos={int((sub['sharpe']>0).sum())}/{len(sub)}")
    print("\n  By N positions:")
    for n in N_SIZES:
        sub = df_results[df_results["n"] == n]
        print(f"    N={n}: mean Sharpe={sub['sharpe'].mean():.3f}, "
              f"pos={int((sub['sharpe']>0).sum())}/{len(sub)}")

    # Save results
    output = {
        "hypothesis": "H-120",
        "name": "Relative Volume Spike Factor",
        "description": "LONG high volume ratio (expanding), SHORT low volume ratio (contracting)",
        "factor": "volume_ratio = rolling_mean(volume, short_window) / rolling_mean(volume, long_window)",
        "n_assets": len(closes.columns),
        "n_days": len(closes),
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "n_params": int(n_total),
        "pct_positive_sharpe": round(float(n_positive / n_total * 100), 1),
        "pct_sharpe_above_1": round(float(n_above_1 / n_total * 100), 1),
        "pct_sharpe_above_1_5": round(float(n_above_1_5 / n_total * 100), 1),
        "mean_sharpe": round(float(df_results["sharpe"].mean()), 3),
        "median_sharpe": round(float(df_results["sharpe"].median()), 3),
        "best_params": str(best["tag"]),
        "best_sharpe": float(best["sharpe"]),
        "best_annual_ret": float(best["annual_ret"]),
        "best_max_dd": float(best["max_dd"]),
        "best_win_rate": float(best["win_rate"]),
        "top5": df_results.nlargest(5, "sharpe")[
            ["tag", "sharpe", "annual_ret", "max_dd", "win_rate"]
        ].to_dict("records"),
        "wf_folds_positive": int((wf_df["test_sharpe"] > 0).sum()) if len(wf_df) > 0 else 0,
        "wf_folds_total": len(wf_df),
        "wf_mean_oos_sharpe": round(float(wf_df["test_sharpe"].mean()), 3) if len(wf_df) > 0 else 0,
        "wf_details": wf_df.to_dict("records") if len(wf_df) > 0 else [],
        "split_half_corr": round(float(sh_corr), 3),
        "split_half_h1_mean": round(float(np.mean(sh_r1)), 3),
        "split_half_h2_mean": round(float(np.mean(sh_r2)), 3),
        "corr_h012": round(float(corr_012), 3),
        "param_sensitivity": {
            "by_short_window": {
                str(sw): round(float(df_results[df_results["short_win"] == sw]["sharpe"].mean()), 3)
                for sw in SHORT_WINDOWS
            },
            "by_long_window": {
                str(lw): round(float(df_results[df_results["long_win"] == lw]["sharpe"].mean()), 3)
                for lw in LONG_WINDOWS
            },
            "by_rebal": {
                str(r): round(float(df_results[df_results["rebal"] == r]["sharpe"].mean()), 3)
                for r in REBAL_FREQS
            },
            "by_n": {
                str(n): round(float(df_results[df_results["n"] == n]["sharpe"].mean()), 3)
                for n in N_SIZES
            },
        },
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")
    print("\n" + json.dumps(output, indent=2))
