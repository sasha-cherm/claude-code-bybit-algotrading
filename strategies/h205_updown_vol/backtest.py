#!/usr/bin/env python3
"""
H-205: Up/Down Volume Ratio Factor (Cross-Sectional)

Concept: Compute the ratio of cumulative trading volume on positive-return days
to cumulative trading volume on negative-return days over a rolling lookback.
  - High ratio = more volume transacted when price rises (bullish conviction)
  - Low ratio  = more volume transacted when price falls (bearish conviction)

Different from:
  - H-188 (return-volume asymmetry: |return| conditional on volume)
  - H-201 (intraday buy/sell pressure from hourly bars)
This version uses simple daily up/down volume balance.

Logic:
  For each asset on each rebalance day:
    1. Classify each day in lookback window as up (return > 0) or down (return <= 0)
    2. up_vol_ratio = sum(volume on up days) / sum(volume on down days)
    3. Handle zero-down-volume: set ratio to 99th-percentile observed ratio
    4. Rank cross-sectionally
    5. Two directions:
       - high_ratio_long: Long high ratio (bullish conviction), Short low ratio
       - low_ratio_long:  Long low ratio (bearish conviction), Short high ratio

Transaction costs: 0.05% per side (0.10% round trip) on each rebalance.

Parameter grid:
  Lookback   : [10, 20, 30, 60]
  Rebalance  : [3, 5, 7]
  N          : [3, 4, 5]
  Direction  : [high_ratio_long, low_ratio_long]
  Total: 4 x 3 x 3 x 2 = 72 combos

Validation (4-stage):
  1. IS: >= 80% of combos in the best direction must have positive Sharpe
  2. Walk-Forward: 6 folds, best IS params per fold, need >= 4/6 positive OOS
  3. Split-Half: Run full grid on each half, both halves' best-combo Sharpe > 0
  4. Correlation: |corr| with H-012 momentum factor
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
LOOKBACKS  = [10, 20, 30, 60]
REBALS     = [3, 5, 7]
NS         = [3, 4, 5]
DIRECTIONS = ["high_ratio_long", "low_ratio_long"]

# Transaction costs: 10bps round-trip => 5bps per side
COST_PER_SIDE = 0.0005

# Walk-forward config
WF_FOLDS     = 6
WF_TEST_DAYS = 90   # ~3 months per fold
WF_TRAIN_MIN = 120  # minimum IS training days


# -- Data loading ----------------------------------------------------------

def load_daily_data():
    """Load 1d parquet files for all assets, return closes and volumes DataFrames.
    Falls back to aggregating 1h data if 1d parquet not available.
    """
    data_dir = ROOT / "data"
    closes_dict = {}
    volumes_dict = {}

    for sym in ASSETS_ALL:
        asset = sym.split("/")[0]
        path_1d = data_dir / f"{asset}_USDT_1d.parquet"
        path_1h = data_dir / f"{asset}_USDT_1h.parquet"

        df = None
        if path_1d.exists():
            df = pd.read_parquet(path_1d)
        elif path_1h.exists():
            raw = pd.read_parquet(path_1h)
            # Aggregate 1h -> daily
            raw["date"] = pd.to_datetime(raw["open_time"]).dt.date
            df = raw.groupby("date").agg(
                open=("open", "first"),
                high=("high", "max"),
                low=("low", "min"),
                close=("close", "last"),
                volume=("volume", "sum"),
            )
            df.index = pd.to_datetime(df.index)

        if df is None:
            continue

        # Normalize column names
        df.columns = [c.lower() for c in df.columns]

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        if all(c in df.columns for c in ["close", "volume"]) and len(df) >= 200:
            closes_dict[sym] = df["close"]
            volumes_dict[sym] = df["volume"]

    closes = pd.DataFrame(closes_dict)
    volumes = pd.DataFrame(volumes_dict)

    # Align and clean
    common_idx = closes.index.intersection(volumes.index)
    closes = closes.loc[common_idx].dropna(how="all").ffill().dropna()
    volumes = volumes.loc[common_idx].reindex(closes.index).ffill().dropna()

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


# -- Core backtest ---------------------------------------------------------

def backtest_updown_vol(closes, volumes, lookback, rebal_freq, n, direction):
    """
    Up/Down Volume Ratio Factor backtest.

    Args:
        closes:     DataFrame of daily closes (assets as columns)
        volumes:    DataFrame of daily volumes (aligned with closes)
        lookback:   rolling window for up/down volume calculation
        rebal_freq: rebalance every N days
        n:          number of longs and shorts per leg
        direction:  "high_ratio_long" or "low_ratio_long"
    Returns:
        pd.Series of daily portfolio returns (or None)
    """
    trade_cols = list(closes.columns)
    if len(trade_cols) < 2 * n:
        return None

    returns = closes.pct_change().dropna()
    vols = volumes.reindex(returns.index)

    dates = returns.index
    warmup = lookback + 5

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=trade_cols)
    prev_weights = pd.Series(0.0, index=trade_cols)

    # Precompute max ratio for div-by-zero handling (will update lazily)
    max_ratio_seen = 10.0  # conservative initial cap

    for i in range(warmup, len(dates)):
        # Apply existing weights to get day's return
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": day_ret})

        # Rebalance check
        if i - last_rebal >= rebal_freq:
            ratio_scores = {}
            raw_ratios = []

            for sym in trade_cols:
                if sym not in returns.columns or sym not in vols.columns:
                    continue

                # Window of returns and volumes
                ret_w = returns[sym].iloc[i - lookback:i].values
                vol_w = vols[sym].iloc[i - lookback:i].values

                if len(ret_w) < lookback // 2:
                    continue

                # Mask valid entries (no NaN)
                valid = ~(np.isnan(ret_w) | np.isnan(vol_w))
                ret_w = ret_w[valid]
                vol_w = vol_w[valid]

                if len(ret_w) < lookback // 3:
                    continue

                # Split into up/down days
                up_mask   = ret_w > 0
                down_mask = ~up_mask  # includes 0-return days

                up_vol   = vol_w[up_mask].sum()
                down_vol = vol_w[down_mask].sum()

                # Handle edge cases
                if down_vol == 0 and up_vol == 0:
                    continue
                elif down_vol == 0:
                    # All up days - will be replaced with max ratio later
                    ratio_scores[sym] = np.nan
                    raw_ratios.append(np.nan)
                    continue
                else:
                    ratio = up_vol / down_vol
                    ratio_scores[sym] = ratio
                    raw_ratios.append(ratio)

            # Update max_ratio_seen from valid ratios
            valid_ratios = [r for r in raw_ratios if not np.isnan(r)]
            if valid_ratios:
                max_ratio_seen = max(max_ratio_seen, max(valid_ratios))

            # Fill NaN ratios (no-down-days) with max observed
            for sym in list(ratio_scores.keys()):
                if np.isnan(ratio_scores[sym]):
                    ratio_scores[sym] = max_ratio_seen

            if len(ratio_scores) < 2 * n:
                continue

            ranked = pd.Series(ratio_scores).sort_values(ascending=True)
            # ranked ascending: lowest ratio at front, highest at back

            if direction == "high_ratio_long":
                # Long high ratio (bullish conviction), Short low ratio
                longs  = ranked.index[-n:]
                shorts = ranked.index[:n]
            else:
                # Long low ratio (bearish conviction), Short high ratio
                longs  = ranked.index[:n]
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

def backtest_updown_vol_oos(full_closes, full_volumes, oos_start_idx, oos_end_idx,
                            lookback, rebal_freq, n, direction):
    """
    OOS-only evaluation with context window prepended for warmup.

    Runs the backtest on full_closes[:oos_end_idx] but only collects
    portfolio returns from oos_start_idx onward. This lets the lookback
    window have proper context from the training period.
    """
    # Prepend enough context bars so warmup is covered
    context_bars = lookback + rebal_freq + 5
    context_start = max(0, oos_start_idx - context_bars)

    ext_closes  = full_closes.iloc[context_start:oos_end_idx]
    ext_volumes = full_volumes.iloc[context_start:oos_end_idx]

    # Boundary in the extended window where OOS actually starts
    oos_boundary_idx = oos_start_idx - context_start

    trade_cols = list(ext_closes.columns)
    if len(trade_cols) < 2 * n:
        return None

    returns = ext_closes.pct_change().dropna()
    vols = ext_volumes.reindex(returns.index)
    dates = returns.index
    warmup = lookback + 5

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=trade_cols)
    prev_weights = pd.Series(0.0, index=trade_cols)
    max_ratio_seen = 10.0

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            # Only collect if this day is in the OOS period
            if i >= oos_boundary_idx:
                day_ret = (returns.iloc[i] * weights).sum()
                portfolio_rets.append({"date": dates[i], "return": day_ret})

        if i - last_rebal >= rebal_freq:
            ratio_scores = {}
            raw_ratios = []
            for sym in trade_cols:
                if sym not in returns.columns or sym not in vols.columns:
                    continue
                ret_w = returns[sym].iloc[i - lookback:i].values
                vol_w = vols[sym].iloc[i - lookback:i].values
                if len(ret_w) < lookback // 2:
                    continue
                valid = ~(np.isnan(ret_w) | np.isnan(vol_w))
                ret_w = ret_w[valid]
                vol_w = vol_w[valid]
                if len(ret_w) < lookback // 3:
                    continue
                up_mask  = ret_w > 0
                up_vol   = vol_w[up_mask].sum()
                down_vol = vol_w[~up_mask].sum()
                if down_vol == 0 and up_vol == 0:
                    continue
                elif down_vol == 0:
                    ratio_scores[sym] = np.nan
                    raw_ratios.append(np.nan)
                else:
                    ratio = up_vol / down_vol
                    ratio_scores[sym] = ratio
                    raw_ratios.append(ratio)
            valid_ratios = [r for r in raw_ratios if not np.isnan(r)]
            if valid_ratios:
                max_ratio_seen = max(max_ratio_seen, max(valid_ratios))
            for sym in list(ratio_scores.keys()):
                if np.isnan(ratio_scores[sym]):
                    ratio_scores[sym] = max_ratio_seen
            if len(ratio_scores) < 2 * n:
                last_rebal = i
                continue
            ranked = pd.Series(ratio_scores).sort_values(ascending=True)
            if direction == "high_ratio_long":
                longs  = ranked.index[-n:]
                shorts = ranked.index[:n]
            else:
                longs  = ranked.index[:n]
                shorts = ranked.index[-n:]
            new_weights = pd.Series(0.0, index=trade_cols)
            for s in longs:
                new_weights[s] = 1.0 / n
            for s in shorts:
                new_weights[s] = -1.0 / n
            # TC only applied to OOS returns
            if i >= oos_boundary_idx:
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


def run_walk_forward(closes, volumes, best_direction):
    """
    6-fold walk-forward. For each fold, select best IS params from full grid
    (within the best direction) on training data, then evaluate OOS.
    Uses context-window approach to avoid warmup eating OOS period.
    """
    n_total = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        oos_end   = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break

        train_closes  = closes.iloc[:oos_start]
        train_volumes = volumes.iloc[:oos_start]

        if len(train_closes) < WF_TRAIN_MIN:
            break

        # IS param selection on training data
        best_sharpe = -np.inf
        best_params = None
        for lb in LOOKBACKS:
            for rf in REBALS:
                for nn in NS:
                    r = backtest_updown_vol(train_closes, train_volumes, lb, rf, nn, best_direction)
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
        # OOS evaluation with context window for proper warmup
        oos_r = backtest_updown_vol_oos(closes, volumes, oos_start, oos_end,
                                        lb, rf, nn, best_direction)
        oos_e = evaluate(oos_r)

        oos_start_date = closes.index[oos_start]
        oos_end_date   = closes.index[min(oos_end - 1, len(closes) - 1)]

        fold_results.append({
            "fold":       fold + 1,
            "is_params":  f"LB{lb}_R{rf}_N{nn}",
            "is_sharpe":  round(best_sharpe, 3),
            "oos_sharpe": oos_e["sharpe"] if oos_e else None,
            "oos_days":   len(oos_r) if oos_r is not None else 0,
            "oos_start":  str(oos_start_date)[:10],
            "oos_end":    str(oos_end_date)[:10],
        })

    return fold_results


# -- Split-half validation -------------------------------------------------

def run_split_half(closes, volumes, best_direction):
    """
    Run full grid (within best direction) on each half.
    Report best-combo Sharpe and mean Sharpe for each half.
    """
    half = len(closes) // 2
    h1_closes  = closes.iloc[:half]
    h1_volumes = volumes.iloc[:half]
    h2_closes  = closes.iloc[half:]
    h2_volumes = volumes.iloc[half:]

    h1_results = []
    h2_results = []

    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                r1 = backtest_updown_vol(h1_closes, h1_volumes, lb, rf, nn, best_direction)
                r2 = backtest_updown_vol(h2_closes, h2_volumes, lb, rf, nn, best_direction)
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
    print("  H-205: Up/Down Volume Ratio Factor")
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

    # ==================================================================
    # Stage 1: IS Parameter Scan
    # ==================================================================
    valid_grid = [
        (lb, rf, nn, d)
        for lb in LOOKBACKS
        for rf in REBALS
        for nn in NS
        for d in DIRECTIONS
    ]
    total_combos = len(valid_grid)
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")

    all_results = []
    count = 0
    for lb, rf, nn, d in valid_grid:
        count += 1
        r  = backtest_updown_vol(closes, volumes, lb, rf, nn, d)
        ev = evaluate(r, f"LB{lb}_R{rf}_N{nn}_{d}")
        if ev:
            ev["lb"]        = lb
            ev["rf"]        = rf
            ev["n"]         = nn
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
        pct   = n_pos / len(sub) * 100 if len(sub) > 0 else 0
        mean_s = sub["sharpe"].mean() if len(sub) > 0 else 0
        print(f"    {d}: {n_pos}/{len(sub)} positive ({pct:.1f}%), mean Sharpe {mean_s:.3f}")

    # Select the better direction
    dir_stats = {}
    for d in DIRECTIONS:
        sub = df_res[df_res["direction"] == d]
        if len(sub) > 0:
            n_pos = (sub["sharpe"] > 0).sum()
            pct   = n_pos / len(sub) * 100
            dir_stats[d] = {
                "pct_positive": pct,
                "mean_sharpe":  sub["sharpe"].mean(),
                "count":        len(sub),
            }

    best_dir       = max(dir_stats, key=lambda d: dir_stats[d]["pct_positive"])
    best_dir_stats = dir_stats[best_dir]
    pct_positive   = best_dir_stats["pct_positive"]
    mean_sharpe_best_dir = best_dir_stats["mean_sharpe"]

    print(f"\n  Better direction: {best_dir}")
    print(f"  Positive Sharpe:  {pct_positive:.1f}%")
    print(f"  Mean Sharpe:      {mean_sharpe_best_dir:.3f}")

    # Overall stats
    n_positive_all   = (df_res["sharpe"] > 0).sum()
    mean_sharpe_all  = df_res["sharpe"].mean()
    median_sharpe_all = df_res["sharpe"].median()
    print(f"\n  Overall (all directions):")
    print(f"  Valid combos:    {len(df_res)}/{total_combos}")
    print(f"  Positive Sharpe: {n_positive_all}/{len(df_res)} "
          f"({n_positive_all/len(df_res)*100:.1f}%)")
    print(f"  Mean Sharpe:     {mean_sharpe_all:.3f}")
    print(f"  Median Sharpe:   {median_sharpe_all:.3f}")

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
    best_lb  = int(best_row["lb"])
    best_rf  = int(best_row["rf"])
    best_n   = int(best_row["n"])

    print(f"\n  Best combo: LB{best_lb}_R{best_rf}_N{best_n} ({best_dir})")
    print(f"  Sharpe: {best_row['sharpe']:.3f}, Annual: {best_row['annual']:.1f}%, "
          f"Max DD: {best_row['dd']:.1f}%, Days: {int(best_row['days'])}")

    # IS gate: 80% threshold
    is_pass = pct_positive >= 80.0
    if not is_pass:
        print(f"\n*** FAIL IS: {pct_positive:.1f}% positive in {best_dir} < 80% threshold ***")
        print("REJECTED at Stage 1. Skipping further validation.")

        result_json = {
            "hypothesis": "H-205",
            "name": "Up/Down Volume Ratio Factor",
            "status": "REJECTED",
            "reason": f"IS positive rate {pct_positive:.1f}% ({best_dir}) < 80% threshold",
            "best_direction": best_dir,
            "direction_stats": {
                d: {
                    "pct_positive": round(dir_stats[d]["pct_positive"], 1),
                    "mean_sharpe":  round(dir_stats[d]["mean_sharpe"], 3),
                    "n_combos":     dir_stats[d]["count"],
                }
                for d in dir_stats
            },
            "is_positive_rate": round(pct_positive, 1),
            "is_mean_sharpe":   round(mean_sharpe_best_dir, 3),
            "best_params": {
                "lookback": best_lb, "rebal": best_rf,
                "n": best_n, "direction": best_dir,
            },
            "best_sharpe":       round(float(best_row["sharpe"]), 3),
            "best_annual_return": round(float(best_row["annual"]), 1),
            "best_max_dd":        round(float(best_row["dd"]), 1),
            "n_assets":     n_assets,
            "n_days":       n_days,
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
    wf_results = run_walk_forward(closes, volumes, best_dir)

    wf_oos_sharpes = [r["oos_sharpe"] for r in wf_results if r["oos_sharpe"] is not None]
    wf_n_pos = sum(1 for s in wf_oos_sharpes if s > 0)

    for r in wf_results:
        oos_s = f"{r['oos_sharpe']:.3f}" if r["oos_sharpe"] is not None else "N/A"
        oos_days = r.get("oos_days", "?")
        print(f"  Fold {r['fold']}: IS={r['is_params']} (IS Sharpe {r['is_sharpe']:.3f}), "
              f"OOS={r['oos_start']}~{r['oos_end']} [{oos_days}d], OOS Sharpe {oos_s}")

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
    sh_best_h1, sh_best_h2, sh_mean_h1, sh_mean_h2 = run_split_half(closes, volumes, best_dir)

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
    print(f"\n--- Stage 4: Correlation with H-012 Momentum ---")
    best_rets = backtest_updown_vol(closes, volumes, best_lb, best_rf, best_n, best_dir)
    mom_rets  = backtest_momentum(closes)

    corr_h012 = safe_corr(best_rets, mom_rets)
    print(f"  H-012 (momentum): {corr_h012:.3f}")

    corr_pass = abs(corr_h012) < 0.50 if not np.isnan(corr_h012) else True
    if not corr_pass:
        print(f"  *** FAIL Correlation: |corr| = {abs(corr_h012):.3f} >= 0.50 ***")
    else:
        print(f"  PASS: |corr| = {abs(corr_h012):.3f} < 0.50")

    # ==================================================================
    # Final Verdict
    # ==================================================================
    print(f"\n{'='*60}")
    print("  FINAL VERDICT")
    print(f"{'='*60}")
    print(f"  IS positive rate: {pct_positive:.1f}%  {'PASS' if is_pass else 'FAIL'}")
    print(f"  Walk-Forward:     {wf_n_pos}/{len(wf_oos_sharpes)} positive  {'PASS' if wf_pass else 'FAIL'}")
    if sh_best_h1 is not None:
        print(f"  Split-Half:       H1={sh_best_h1}, H2={sh_best_h2}  {'PASS' if sh_pass else 'FAIL'}")
    else:
        print(f"  Split-Half:       insufficient data  FAIL")
    print(f"  Correlation:      |corr H-012|={abs(corr_h012):.3f}  {'PASS' if corr_pass else 'FAIL'}")

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
        "hypothesis": "H-205",
        "name": "Up/Down Volume Ratio Factor",
        "status": status,
        "reason": "; ".join(rejection_reasons) if rejection_reasons else "All stages passed",
        "best_direction": best_dir,
        "direction_stats": {
            d: {
                "pct_positive": round(dir_stats[d]["pct_positive"], 1),
                "mean_sharpe":  round(dir_stats[d]["mean_sharpe"], 3),
                "n_combos":     dir_stats[d]["count"],
            }
            for d in dir_stats
        },
        "is_positive_rate":   round(pct_positive, 1),
        "is_mean_sharpe":     round(mean_sharpe_best_dir, 3),
        "is_median_sharpe":   round(float(df_best["sharpe"].median()), 3),
        "best_params": {
            "lookback": best_lb, "rebal": best_rf,
            "n": best_n, "direction": best_dir,
        },
        "best_sharpe":        round(float(best_row["sharpe"]), 3),
        "best_annual_return": round(float(best_row["annual"]), 1),
        "best_max_dd":        round(float(best_row["dd"]), 1),
        "wf_folds": [
            {
                "fold":       r["fold"],
                "is_params":  r["is_params"],
                "is_sharpe":  r["is_sharpe"],
                "oos_sharpe": r["oos_sharpe"],
                "oos_days":   r.get("oos_days"),
                "oos_start":  r["oos_start"],
                "oos_end":    r["oos_end"],
            }
            for r in wf_results
        ] if is_pass else [],
        "wf_positive_folds":   wf_n_pos if is_pass else None,
        "wf_total_folds":      len(wf_oos_sharpes) if is_pass else None,
        "wf_mean_oos_sharpe":  round(mean_oos, 3) if (is_pass and not np.isnan(mean_oos)) else None,
        "split_half": {
            "h1_best_sharpe": sh_best_h1,
            "h2_best_sharpe": sh_best_h2,
            "h1_mean_sharpe": sh_mean_h1,
            "h2_mean_sharpe": sh_mean_h2,
        } if is_pass else None,
        "correlations": {
            "H-012_momentum": corr_h012,
        } if is_pass else None,
        "n_assets":     n_assets,
        "n_days":       n_days,
        "total_combos": total_combos,
        "valid_combos": len(df_res),
        "validation": {
            "is_pass":   bool(is_pass),
            "wf_pass":   bool(wf_pass) if is_pass else None,
            "sh_pass":   bool(sh_pass) if is_pass else None,
            "corr_pass": bool(corr_pass) if is_pass else None,
        },
    }

    results_path = Path(__file__).parent / "results.json"
    with open(results_path, "w") as f:
        json.dump(result_json, f, indent=2)
    print(f"\nResults written to {results_path}")


if __name__ == "__main__":
    main()
