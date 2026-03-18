"""
H-021 Volume Momentum — Deep Validation (Session 2026-03-18, session 28)

H-021 passed initial screen with:
- 90% params positive, best Sharpe 1.81
- Walk-forward: 5/6 positive, mean OOS Sharpe 1.77
- Corr with H-012: -0.061, H-019: 0.002

Concerns to address:
1. Best params have 3-day rebal (high turnover / 1341 trades)
2. Most recent WF fold is weak (Sharpe 0.19)
3. Need H-009 correlation check
4. Need to test multiple param sets in WF (not just the best)
5. Portfolio improvement analysis
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from strategies.new_factors_research.research import (
    load_all_data, run_xs_factor, compute_metrics,
    ASSETS, BASE_FEE, SLIPPAGE_BPS, INITIAL_CAPITAL,
)
from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return


def compute_vol_momentum_ranking(closes, volumes, short_window, long_window):
    """Compute volume momentum ranking."""
    vol_short = volumes.rolling(short_window).mean()
    vol_long = volumes.rolling(long_window).mean()
    return vol_short / vol_long


def run_walk_forward(closes, volumes, short_window, long_window, rebal, n_long,
                     n_folds=8, train_days=180, test_days=80):
    """Run walk-forward for a specific param set."""
    n = len(closes)
    fold_results = []

    for fold in range(n_folds):
        test_end = n - fold * test_days
        test_start = test_end - test_days
        train_start = test_start - train_days

        if train_start < 0 or test_start < 0:
            break

        test_closes = closes.iloc[test_start:test_end]
        ranking = compute_vol_momentum_ranking(
            closes.iloc[:test_end], volumes.iloc[:test_end],
            short_window, long_window
        )
        test_ranking = ranking.iloc[test_start:test_end]

        res = run_xs_factor(test_closes, test_ranking, rebal, n_long,
                            warmup=5, fee_multiplier=1.0)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        })

    return pd.DataFrame(fold_results)


if __name__ == "__main__":
    print("Loading data...")
    hourly, daily = load_all_data()
    print(f"\nLoaded {len(daily)} assets")

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().dropna()
    common = closes.columns.intersection(volumes.columns)
    closes = closes[common]
    volumes = volumes[common]

    # ═══════════════════════════════════════════════════════════════════
    # 1. Test Multiple Param Sets in Walk-Forward
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "█" * 70)
    print("1. MULTI-PARAM WALK-FORWARD")
    print("█" * 70)

    # Test a range of param sets across different turnover levels
    param_sets = [
        # High turnover (3-day rebal)
        {"sw": 7, "lw": 20, "rebal": 3, "n_long": 4, "tag": "VS7_VL20_R3_N4 (best)"},
        {"sw": 5, "lw": 20, "rebal": 3, "n_long": 4, "tag": "VS5_VL20_R3_N4"},
        # Medium turnover (5-7 day rebal)
        {"sw": 5, "lw": 30, "rebal": 5, "n_long": 5, "tag": "VS5_VL30_R5_N5"},
        {"sw": 7, "lw": 30, "rebal": 7, "n_long": 4, "tag": "VS7_VL30_R7_N4"},
        {"sw": 7, "lw": 30, "rebal": 7, "n_long": 5, "tag": "VS7_VL30_R7_N5"},
        {"sw": 5, "lw": 30, "rebal": 7, "n_long": 4, "tag": "VS5_VL30_R7_N4"},
        # Low turnover (14-21 day rebal)
        {"sw": 5, "lw": 30, "rebal": 14, "n_long": 5, "tag": "VS5_VL30_R14_N5"},
        {"sw": 5, "lw": 30, "rebal": 14, "n_long": 4, "tag": "VS5_VL30_R14_N4"},
        {"sw": 3, "lw": 30, "rebal": 14, "n_long": 3, "tag": "VS3_VL30_R14_N3"},
        {"sw": 3, "lw": 30, "rebal": 21, "n_long": 3, "tag": "VS3_VL30_R21_N3"},
        {"sw": 7, "lw": 30, "rebal": 14, "n_long": 5, "tag": "VS7_VL30_R14_N5"},
        {"sw": 7, "lw": 30, "rebal": 21, "n_long": 3, "tag": "VS7_VL30_R21_N3"},
    ]

    wf_summary = []
    for ps in param_sets:
        wf = run_walk_forward(
            closes, volumes,
            ps["sw"], ps["lw"], ps["rebal"], ps["n_long"],
        )
        if len(wf) == 0:
            continue

        pos = (wf["sharpe"] > 0).sum()
        total = len(wf)
        mean_oos = wf["sharpe"].mean()
        median_oos = wf["sharpe"].median()

        # Also get IS metrics
        ranking = compute_vol_momentum_ranking(closes, volumes, ps["sw"], ps["lw"])
        is_res = run_xs_factor(closes, ranking, ps["rebal"], ps["n_long"],
                               warmup=ps["lw"] + 10)

        print(f"\n  {ps['tag']}:")
        print(f"    IS: Sharpe {is_res['sharpe']:.2f}, Ann {is_res['annual_ret']:.1%}, "
              f"DD {is_res['max_dd']:.1%}, Trades {is_res['n_trades']}")
        print(f"    WF: {pos}/{total} positive, mean OOS Sharpe {mean_oos:.2f}, "
              f"median {median_oos:.2f}")
        for _, row in wf.iterrows():
            print(f"      Fold {row['fold']}: {row['start']} → {row['end']}, "
                  f"Sharpe {row['sharpe']:.2f}")

        wf_summary.append({
            "tag": ps["tag"],
            "sw": ps["sw"], "lw": ps["lw"],
            "rebal": ps["rebal"], "n_long": ps["n_long"],
            "is_sharpe": is_res["sharpe"],
            "is_annual": is_res["annual_ret"],
            "is_dd": is_res["max_dd"],
            "is_trades": is_res["n_trades"],
            "wf_positive": pos,
            "wf_total": total,
            "wf_mean": mean_oos,
            "wf_median": median_oos,
        })

    wf_df = pd.DataFrame(wf_summary)
    print("\n  Summary (sorted by WF mean Sharpe):")
    wf_df_sorted = wf_df.sort_values("wf_mean", ascending=False)
    for _, row in wf_df_sorted.iterrows():
        print(f"    {row['tag']}: IS {row['is_sharpe']:.2f}, "
              f"WF {row['wf_positive']}/{row['wf_total']} (mean {row['wf_mean']:.2f}), "
              f"Trades {row['is_trades']}")

    # ═══════════════════════════════════════════════════════════════════
    # 2. Correlation with H-009 (BTC Daily EMA Trend)
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "█" * 70)
    print("2. CORRELATION WITH H-009 (BTC Daily EMA)")
    print("█" * 70)

    # Run H-009 simulation
    btc_close = closes["BTC/USDT"].dropna()
    ema5 = btc_close.ewm(span=5, adjust=False).mean()
    ema40 = btc_close.ewm(span=40, adjust=False).mean()
    h009_signal = pd.Series(0.0, index=btc_close.index)
    h009_signal[ema5 > ema40] = 1.0
    h009_signal[ema5 <= ema40] = -1.0

    # Simple equity curve for H-009
    btc_rets = btc_close.pct_change().fillna(0)
    h009_rets = h009_signal.shift(1) * btc_rets
    h009_equity = (1 + h009_rets).cumprod() * 10000

    # Run best H-021 params and compute correlation
    best_candidates = [
        {"sw": 7, "lw": 20, "rebal": 3, "n_long": 4, "tag": "VS7_VL20_R3_N4 (best)"},
        {"sw": 5, "lw": 30, "rebal": 14, "n_long": 5, "tag": "VS5_VL30_R14_N5 (low turnover)"},
        {"sw": 7, "lw": 30, "rebal": 7, "n_long": 4, "tag": "VS7_VL30_R7_N4 (mid turnover)"},
    ]

    for ps in best_candidates:
        ranking = compute_vol_momentum_ranking(closes, volumes, ps["sw"], ps["lw"])
        res = run_xs_factor(closes, ranking, ps["rebal"], ps["n_long"],
                            warmup=ps["lw"] + 10)

        h021_rets = res["equity"].pct_change().dropna()
        h009_rets_aligned = h009_equity.pct_change().dropna()

        common_idx = h021_rets.index.intersection(h009_rets_aligned.index)
        if len(common_idx) > 50:
            corr = round(h021_rets.loc[common_idx].corr(h009_rets_aligned.loc[common_idx]), 3)
        else:
            corr = 0.0
        print(f"  {ps['tag']}: corr with H-009 = {corr}")

    # ═══════════════════════════════════════════════════════════════════
    # 3. Portfolio Analysis: Add H-021 as 5th Strategy
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "█" * 70)
    print("3. PORTFOLIO IMPROVEMENT ANALYSIS")
    print("█" * 70)

    # Build equity curves for all strategies
    # H-009
    h009_eq = h009_equity

    # H-011 (funding rate arb) — use cached data
    funding_path = ROOT / "data" / "funding_BTC_USDT.parquet"
    if funding_path.exists():
        fr_data = pd.read_parquet(funding_path)
        if "funding_rate" in fr_data.columns:
            fr = fr_data["funding_rate"]
        else:
            fr = fr_data["fundingRate"]
        # Simple simulation: collect funding when rolling avg > 0, at 5x
        fr_daily = fr.resample("1D").sum()
        rolling_avg = fr_daily.rolling(27).mean()
        h011_signal = (rolling_avg > 0).astype(float)
        h011_daily_ret = h011_signal.shift(1) * fr_daily * 5
        h011_equity = (1 + h011_daily_ret.fillna(0)).cumprod() * 10000
    else:
        print("  WARNING: No funding data found, skipping H-011")
        h011_equity = pd.Series(10000.0, index=closes.index)

    # H-012 (XSMom)
    mom_ranking = closes.pct_change(60)
    h012_res = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)
    h012_equity = h012_res["equity"]

    # H-019 (LowVol)
    vol_ranking = -closes.pct_change().rolling(20).std()
    h019_res = run_xs_factor(closes, vol_ranking, 21, 3, warmup=30)
    h019_equity = h019_res["equity"]

    # H-021 — use a mid-turnover param set
    # Try VS5_VL30_R14_N5 (low turnover, IS Sharpe ~1.65)
    h021_ranking = compute_vol_momentum_ranking(closes, volumes, 5, 30)
    h021_res = run_xs_factor(closes, h021_ranking, 14, 5, warmup=40)
    h021_equity = h021_res["equity"]

    # Align all equity curves
    all_eq = pd.DataFrame({
        "H-009": h009_eq,
        "H-011": h011_equity,
        "H-012": h012_equity,
        "H-019": h019_equity,
        "H-021": h021_equity,
    }).dropna()

    all_rets = all_eq.pct_change().dropna()

    # Correlation matrix
    print("\n  Return correlation matrix:")
    corr_matrix = all_rets.corr()
    print(corr_matrix.round(3).to_string())

    # Portfolio combinations
    allocations = {
        "4-strat (current: 15/50/15/20)": {"H-009": 0.15, "H-011": 0.50, "H-012": 0.15, "H-019": 0.20},
        "5-strat (12/45/12/16/15)": {"H-009": 0.12, "H-011": 0.45, "H-012": 0.12, "H-019": 0.16, "H-021": 0.15},
        "5-strat (10/40/10/15/25)": {"H-009": 0.10, "H-011": 0.40, "H-012": 0.10, "H-019": 0.15, "H-021": 0.25},
        "5-strat (10/45/10/15/20)": {"H-009": 0.10, "H-011": 0.45, "H-012": 0.10, "H-019": 0.15, "H-021": 0.20},
    }

    print("\n  Portfolio comparisons:")
    for name, alloc in allocations.items():
        weights = pd.Series(alloc)
        port_rets = (all_rets[weights.index] * weights).sum(axis=1)
        port_eq = (1 + port_rets).cumprod() * 10000

        metrics = compute_metrics(port_eq)
        print(f"\n  {name}:")
        print(f"    Sharpe: {metrics['sharpe']:.2f}")
        print(f"    Annual return: {metrics['annual_ret']:.1%}")
        print(f"    Max drawdown: {metrics['max_dd']:.1%}")

    # ═══════════════════════════════════════════════════════════════════
    # 4. Regime Analysis — When Does H-021 Fail?
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "█" * 70)
    print("4. REGIME ANALYSIS")
    print("█" * 70)

    # Check if H-021 fails in specific BTC regimes
    btc_60d_ret = btc_close.pct_change(60)
    h021_daily_rets = h021_equity.pct_change().dropna()

    # Split into BTC up vs down regimes
    common_idx = btc_60d_ret.index.intersection(h021_daily_rets.index)
    btc_60d_aligned = btc_60d_ret.loc[common_idx]
    h021_aligned = h021_daily_rets.loc[common_idx]

    up_mask = btc_60d_aligned > 0.10  # BTC up >10% over 60d
    down_mask = btc_60d_aligned < -0.10
    flat_mask = ~up_mask & ~down_mask

    for regime, mask, label in [
        ("BTC UP (>10%)", up_mask, "up"),
        ("BTC DOWN (<-10%)", down_mask, "down"),
        ("BTC FLAT", flat_mask, "flat"),
    ]:
        regime_rets = h021_aligned[mask]
        if len(regime_rets) > 30:
            ann_ret = regime_rets.mean() * 365
            ann_vol = regime_rets.std() * np.sqrt(365)
            regime_sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
            print(f"  {regime}: {len(regime_rets)} days, "
                  f"Sharpe {regime_sharpe:.2f}, Ann ret {ann_ret:.1%}")
        else:
            print(f"  {regime}: {len(regime_rets)} days (too few)")

    # ═══════════════════════════════════════════════════════════════════
    # 5. Robustness: Volume Data Quality Check
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "█" * 70)
    print("5. VOLUME DATA QUALITY")
    print("█" * 70)

    # Check for volume anomalies (zeros, spikes, etc.)
    for sym in list(volumes.columns)[:5]:
        vol = volumes[sym]
        zero_pct = (vol == 0).mean()
        vol_ratio = vol.max() / vol.median()
        print(f"  {sym}: zeros={zero_pct:.1%}, max/median={vol_ratio:.0f}x, "
              f"mean={vol.mean():.0f}, std={vol.std():.0f}")

    # Check if volume data has time-of-day patterns that affect daily aggregation
    print("\n  Volume consistency (rolling 30d CV):")
    vol_cv = volumes.rolling(30).std() / volumes.rolling(30).mean()
    print(f"    Mean CV across assets: {vol_cv.mean().mean():.2f}")
    print(f"    Min CV: {vol_cv.mean().min():.2f} ({vol_cv.mean().idxmin()})")
    print(f"    Max CV: {vol_cv.mean().max():.2f} ({vol_cv.mean().idxmax()})")

    # ═══════════════════════════════════════════════════════════════════
    # 6. Alternative Volume Measures
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "█" * 70)
    print("6. ALTERNATIVE VOLUME MEASURES")
    print("█" * 70)

    # Test dollar volume instead of raw volume
    dollar_volumes = closes * volumes

    # Also test log-volume change
    log_vol_change = np.log(volumes).diff()

    alt_measures = {
        "Dollar volume ratio": lambda sw, lw: dollar_volumes.rolling(sw).mean() / dollar_volumes.rolling(lw).mean(),
        "Log volume change": lambda sw, lw: log_vol_change.rolling(sw).mean(),
        "Volume z-score": lambda sw, lw: (volumes.rolling(sw).mean() - volumes.rolling(lw).mean()) / volumes.rolling(lw).std(),
    }

    # Test best-performing param (VS5_VL30_R14_N5) with alternative measures
    for measure_name, measure_fn in alt_measures.items():
        ranking = measure_fn(5, 30)
        res = run_xs_factor(closes, ranking, 14, 5, warmup=40)
        print(f"  {measure_name}: Sharpe {res['sharpe']:.2f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

        # Quick WF for promising alternatives
        if res["sharpe"] > 1.0:
            print(f"    Running WF...")
            n = len(closes)
            fold_sharpes = []
            for fold in range(6):
                test_end = n - fold * 80
                test_start = test_end - 80
                if test_start < 40:
                    break
                test_c = closes.iloc[test_start:test_end]
                test_v = volumes.iloc[test_start:test_end]
                test_dv = dollar_volumes.iloc[test_start:test_end]
                test_lv = log_vol_change.iloc[test_start:test_end]

                if "Dollar" in measure_name:
                    test_r = dollar_volumes.iloc[:test_end].rolling(5).mean() / dollar_volumes.iloc[:test_end].rolling(30).mean()
                elif "Log" in measure_name:
                    test_r = log_vol_change.iloc[:test_end].rolling(5).mean()
                else:
                    test_r = (volumes.iloc[:test_end].rolling(5).mean() - volumes.iloc[:test_end].rolling(30).mean()) / volumes.iloc[:test_end].rolling(30).std()

                test_r = test_r.iloc[test_start:test_end]
                r = run_xs_factor(test_c, test_r, 14, 5, warmup=5)
                fold_sharpes.append(r["sharpe"])
            pos = sum(1 for s in fold_sharpes if s > 0)
            mean_s = np.mean(fold_sharpes)
            print(f"    WF: {pos}/{len(fold_sharpes)} positive, mean Sharpe {mean_s:.2f}")

    # ═══════════════════════════════════════════════════════════════════
    # FINAL RECOMMENDATION
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "█" * 70)
    print("FINAL RECOMMENDATION")
    print("█" * 70)

    # Summarize best param set for paper trade consideration
    # Choose the param set with best WF that also has reasonable turnover
    print("\n  Best candidates for paper trade:")
    for _, row in wf_df_sorted.head(5).iterrows():
        turnover_level = "HIGH" if row["rebal"] <= 5 else ("MED" if row["rebal"] <= 10 else "LOW")
        print(f"    {row['tag']}: IS={row['is_sharpe']:.2f}, "
              f"WF mean={row['wf_mean']:.2f} ({row['wf_positive']}/{row['wf_total']}), "
              f"Trades={row['is_trades']}, Turnover={turnover_level}")

    print("\nDone.")
