#!/usr/bin/env python3
"""
H-201: Volume Imbalance Factor (Buy/Sell Pressure Proxy, 14 Assets)

Concept: Approximate buy/sell pressure using intraday 1h volume and price
movement direction. For each day, compute the fraction of hourly bars where
close > open (up bars). Volume imbalance = sum of volume on up-bars / total
daily volume. High imbalance = buying pressure dominates.

Different from:
  - H-111 (Directional Volume Imbalance -- used daily bars for up-day detection)
  - H-094 (Volume Asymmetry -- used volume ratio between up and down bars,
            different factor definition)

  This version uses 1h intrabar data to construct a daily buying-pressure
  metric, then ranks cross-sectionally.

Logic:
  For each asset on each rebalance day:
    1. From 1h OHLCV, flag each hour as up (close > open) or down
    2. Daily buying pressure = sum(volume on up hours) / sum(total volume)
    3. Average buying pressure over a rolling lookback window
    4. Rank assets cross-sectionally
    5. Two directions:
       - high_buy_long: Long assets with highest buying pressure, short lowest
       - low_buy_long:  Long assets with lowest buying pressure, short highest
    6. Dollar-neutral, equal weight within legs

Transaction costs: 0.1% per side (0.05% fee + 0.02% slippage each way rounded up).

Parameter grid:
  Lookback (days):      [5, 10, 20, 30]
  Rebalance frequency:  [3, 5, 7]
  N positions each side: [3, 4, 5]
  Direction:            [high_buy_long, low_buy_long]
  Total: 4 x 3 x 3 x 2 = 72 combos

Validation (4-stage):
  1. IS: >= 80% of combos in the better direction must have positive Sharpe
  2. Walk-Forward: 6 folds, best IS params per fold, need >= 4/6 positive OOS
  3. Split-Half: Run full grid on each half, both halves' best-combo Sharpe > 0
  4. Correlation: daily return correlation with H-012 momentum
"""

import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

# Parameter grid
LOOKBACKS  = [5, 10, 20, 30]
REBALS     = [3, 5, 7]
NS         = [3, 4, 5]
DIRECTIONS = ["high_buy_long", "low_buy_long"]

# Transaction costs: 10bps per side (fee 5bps + slippage ~5bps, conservative)
COST_PER_SIDE = 0.0010

# Walk-forward config
WF_FOLDS     = 6
WF_TEST_DAYS = 90   # ~3 months per fold
WF_TRAIN_MIN = 60   # minimum IS training days


# -- Data loading ----------------------------------------------------------

def load_data():
    """
    Load 1h parquet files for all assets.
    Compute daily buying pressure from 1h bars.
    Return: closes (daily), buying_pressure (daily), both as DataFrames.
    """
    from strategies.daily_trend_multi_asset.strategy import resample_to_daily

    data_dir = ROOT / "data"
    closes_dict = {}
    bp_dict = {}  # buying pressure

    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path_1h = data_dir / f"{safe}_1h.parquet"
        if not path_1h.exists():
            print(f"  WARNING: {path_1h} not found, skipping {sym}")
            continue

        df_1h = pd.read_parquet(path_1h)
        if len(df_1h) < 500:
            print(f"  WARNING: {sym} has only {len(df_1h)} 1h bars, skipping")
            continue

        # Compute buying pressure from 1h bars
        df_1h['up'] = (df_1h['close'] > df_1h['open']).astype(float)
        df_1h['up_vol'] = df_1h['up'] * df_1h['volume']

        daily_up_vol = df_1h['up_vol'].resample('D').sum()
        daily_total_vol = df_1h['volume'].resample('D').sum()

        # buying pressure = fraction of volume on up-hours
        buying_pressure = daily_up_vol / daily_total_vol
        # Replace inf/nan with 0.5 (neutral)
        buying_pressure = buying_pressure.replace([np.inf, -np.inf], np.nan).fillna(0.5)

        # Get daily close for returns
        daily = resample_to_daily(df_1h)
        if len(daily) < 200:
            print(f"  WARNING: {sym} has only {len(daily)} daily bars, skipping")
            continue

        closes_dict[sym] = daily["close"]
        bp_dict[sym] = buying_pressure

    closes = pd.DataFrame(closes_dict)
    bp = pd.DataFrame(bp_dict)

    # Align indices
    common_idx = closes.index.intersection(bp.index)
    closes = closes.loc[common_idx].dropna(how="all").ffill().dropna()
    bp = bp.loc[common_idx].reindex(closes.index).ffill().dropna()

    # Make sure both have exactly the same index
    common_idx = closes.index.intersection(bp.index)
    closes = closes.loc[common_idx]
    bp = bp.loc[common_idx]

    return closes, bp


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

def backtest_vol_imbalance(closes, buying_pressure, lookback, rebal_freq, n, direction):
    """
    Volume Imbalance Factor backtest.

    Args:
        closes:           DataFrame of daily closes
        buying_pressure:  DataFrame of daily buying pressure (aligned with closes)
        lookback:         rolling window for averaging buying pressure
        rebal_freq:       rebalance every N days
        n:                number of longs and shorts
        direction:        "high_buy_long" or "low_buy_long"
    Returns:
        pd.Series of daily portfolio returns (or None)
    """
    trade_cols = list(closes.columns)
    if len(trade_cols) < 2 * n:
        return None

    returns = closes.pct_change().dropna()

    dates = returns.index
    warmup = lookback + 5

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
            # Compute rolling mean buying pressure for each asset
            bp_scores = {}
            for sym in trade_cols:
                if sym not in buying_pressure.columns:
                    continue
                # Use iloc indexing for the rolling window
                start_idx = max(0, i - lookback)
                window = buying_pressure[sym].iloc[start_idx:i].values
                valid_vals = window[~np.isnan(window)]
                if len(valid_vals) < lookback // 2:
                    continue
                avg_bp = np.mean(valid_vals)
                if not np.isfinite(avg_bp):
                    continue
                bp_scores[sym] = avg_bp

            if len(bp_scores) < 2 * n:
                continue

            ranked = pd.Series(bp_scores).sort_values(ascending=True)
            # ranked: ascending by buying pressure
            # Bottom = lowest buying pressure (selling pressure dominates)
            # Top = highest buying pressure (buying pressure dominates)

            if direction == "high_buy_long":
                # Long assets with highest buying pressure, Short lowest
                longs = ranked.index[-n:]
                shorts = ranked.index[:n]
            else:
                # low_buy_long: Long assets with lowest buying pressure, Short highest
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
    """H-012 cross-sectional momentum: 60d return ranking, 5d rebal, top/bottom 4."""
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

def run_walk_forward(closes, bp, best_direction):
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
        train_bp = bp.iloc[:oos_start]
        oos_closes = closes.iloc[oos_start:oos_end]
        oos_bp = bp.iloc[oos_start:oos_end]

        if len(train_closes) < WF_TRAIN_MIN or len(oos_closes) < 20:
            break

        # IS param selection on training data
        best_sharpe = -np.inf
        best_params = None
        for lb in LOOKBACKS:
            for rf in REBALS:
                for nn in NS:
                    r = backtest_vol_imbalance(train_closes, train_bp, lb, rf, nn, best_direction)
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
        # OOS evaluation
        oos_r = backtest_vol_imbalance(oos_closes, oos_bp, lb, rf, nn, best_direction)
        oos_e = evaluate(oos_r)

        oos_start_date = closes.index[oos_start]
        oos_end_date = closes.index[min(oos_end - 1, len(closes) - 1)]

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

def run_split_half(closes, bp, best_direction):
    """
    Run full grid (within best direction) on each half.
    Report best-combo Sharpe and mean Sharpe for each half.
    """
    half = len(closes) // 2
    h1_closes = closes.iloc[:half]
    h1_bp = bp.iloc[:half]
    h2_closes = closes.iloc[half:]
    h2_bp = bp.iloc[half:]

    h1_results = []
    h2_results = []

    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                r1 = backtest_vol_imbalance(h1_closes, h1_bp, lb, rf, nn, best_direction)
                r2 = backtest_vol_imbalance(h2_closes, h2_bp, lb, rf, nn, best_direction)
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
    print("=" * 65)
    print("  H-201: Volume Imbalance Factor (Buy/Sell Pressure Proxy)")
    print("=" * 65)

    print("\nLoading 1h OHLCV data and computing daily buying pressure...")
    closes, bp = load_data()
    n_assets = len(closes.columns)
    n_days = len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")
    print(f"Assets: {list(closes.columns)}")

    if n_assets < 6:
        print("ERROR: Too few assets. Aborting.")
        sys.exit(1)

    # Quick sanity check on buying pressure
    print(f"\nBuying pressure stats (most recent 30d avg):")
    recent_bp = bp.tail(30).mean()
    for sym in sorted(recent_bp.index, key=lambda s: recent_bp[s], reverse=True):
        print(f"  {sym:12s}: {recent_bp[sym]:.3f}")

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
        r = backtest_vol_imbalance(closes, bp, lb, rf, nn, d)
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
        best_s = sub["sharpe"].max() if len(sub) > 0 else 0
        print(f"    {d}: {n_pos}/{len(sub)} positive ({pct:.1f}%), "
              f"mean Sharpe {mean_s:.3f}, best Sharpe {best_s:.3f}")

    # Select the better direction
    dir_stats = {}
    for d in DIRECTIONS:
        sub = df_res[df_res["direction"] == d]
        if len(sub) > 0:
            n_pos = (sub["sharpe"] > 0).sum()
            pct = n_pos / len(sub) * 100
            dir_stats[d] = {
                "pct_positive": pct,
                "mean_sharpe": sub["sharpe"].mean(),
                "count": len(sub),
            }

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

    # IS gate: 80% of combos in best direction must be positive
    is_pass = pct_positive >= 80.0
    if not is_pass:
        print(f"\n*** FAIL IS: {pct_positive:.1f}% positive in {best_dir} < 80% threshold ***")
        print("REJECTED at Stage 1. Skipping further validation.")

        result_json = {
            "hypothesis": "H-201",
            "name": "Volume Imbalance Factor (Buy/Sell Pressure Proxy)",
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
    wf_results = run_walk_forward(closes, bp, best_dir)

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
    sh_best_h1, sh_best_h2, sh_mean_h1, sh_mean_h2 = run_split_half(closes, bp, best_dir)

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
    # Stage 4: Correlation with H-012 (momentum)
    # ==================================================================
    print(f"\n--- Stage 4: Correlation with H-012 (Momentum) ---")
    best_rets = backtest_vol_imbalance(closes, bp, best_lb, best_rf, best_n, best_dir)

    print("  Computing H-012 momentum returns (60d lookback, 5d rebal, N=4)...")
    mom_rets = backtest_momentum(closes, lookback=60, rebal_freq=5, n=4)

    corr_h012 = safe_corr(best_rets, mom_rets)
    print(f"  Correlation with H-012: {corr_h012:.3f}")

    corr_pass = abs(corr_h012) < 0.50 if not np.isnan(corr_h012) else True
    if not corr_pass:
        print(f"  *** FAIL Correlation: |corr| = {abs(corr_h012):.3f} >= 0.50 ***")
    else:
        print(f"  PASS: |corr| = {abs(corr_h012):.3f} < 0.50")

    # ==================================================================
    # Final Verdict
    # ==================================================================
    print(f"\n{'='*65}")
    print("  FINAL VERDICT")
    print(f"{'='*65}")
    print(f"  IS positive rate: {pct_positive:.1f}% {'PASS' if is_pass else 'FAIL'}")
    print(f"  Walk-Forward: {wf_n_pos}/{len(wf_oos_sharpes)} positive {'PASS' if wf_pass else 'FAIL'}")
    print(f"  Split-Half: H1={sh_best_h1}, H2={sh_best_h2} {'PASS' if sh_pass else 'FAIL'}")
    print(f"  Correlation H-012: {corr_h012:.3f} {'PASS' if corr_pass else 'FAIL'}")

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
        rejection_reasons.append(f"|corr H-012| {abs(corr_h012):.3f} >= 0.50")

    print(f"\n  Status: {status}")
    if rejection_reasons:
        print(f"  Reason: {'; '.join(rejection_reasons)}")

    # ==================================================================
    # Write results.json
    # ==================================================================
    result_json = {
        "hypothesis": "H-201",
        "name": "Volume Imbalance Factor (Buy/Sell Pressure Proxy)",
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
        "best_params": {"lookback": best_lb, "rebal": best_rf, "n": best_n, "direction": best_dir},
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
        "correlation_h012": corr_h012 if is_pass else None,
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
