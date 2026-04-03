#!/usr/bin/env python3
"""
H-214: Downside Tail Risk Factor (CVaR/Expected Shortfall)

Concept: Assets with lower downside tail risk (less negative CVaR at the 5%
level) tend to outperform those with higher downside tail risk. This is the
crypto analogue of the low-volatility anomaly but focused on the LEFT TAIL —
retail investors overweight lottery-like tail-risk assets, suppressing their
risk-adjusted returns. An asset can have moderate vol but extreme left-tail
events, or high vol but a truncated left tail; CVaR captures this asymmetry
that simple volatility (H-019) misses.

Differentiation from H-099 (earlier CVaR test):
  - H-099 used percentiles [5, 10] in its grid and a different validation
    framework (4 WF folds, no strict IS >= 80% gate, no split-half best-Sharpe
    criterion). This version uses the standardized 4-stage framework matching
    H-197 (IS >= 80% gate, 6 WF folds 270d/90d, split-half best-Sharpe > 0,
    correlation with H-012 and H-019).
  - Parameter grid anchored at 5% CVaR only (the canonical ES measure).
  - Adds H-019 low-vol correlation check as a direct differentiation test.

Logic:
  1. Compute daily log returns for each asset.
  2. Over a rolling lookback window, compute CVaR_5% = mean of returns that fall
     below the 5th percentile of that window's return distribution.
  3. Rank assets cross-sectionally by CVaR (ascending = most negative first).
  4. Two directions:
       low_tail_long:  Long lowest tail risk (least negative CVaR = safest),
                       Short highest tail risk (most negative CVaR = riskiest)
                       [lottery/overpricing hypothesis]
       high_tail_long: Long highest tail risk (most negative CVaR = riskiest),
                       Short lowest tail risk [risk-premium hypothesis]
  5. Dollar-neutral, equal-weighted within each leg.

Transaction costs: 10bps round-trip (5bps per side) on rebalance turnover.

Parameter grid:
  Lookback : [20, 30, 40, 60]   (days)
  Rebal    : [3, 5, 7]          (days)
  N        : [3, 4]             (assets per leg)
  Direction: [low_tail_long, high_tail_long]
  Total: 4 x 3 x 2 x 2 = 48 combos

Validation (4-stage, standardized):
  1. IS: >= 80% of combos in the better direction have positive Sharpe
  2. Walk-Forward: 6 folds (270d train / 90d OOS), >= 4/6 positive OOS folds,
     mean OOS Sharpe > 0
  3. Split-Half: Run full grid on each half, best-combo Sharpe > 0 in BOTH halves
  4. Correlation: max |corr| < 0.50 with H-012 (momentum) and H-019 (low-vol)

CONFIRMED if Stages 1-4 all pass, else REJECTED.
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
LOOKBACKS  = [20, 30, 40, 60]
REBALS     = [3, 5, 7]
NS         = [3, 4]
DIRECTIONS = ["low_tail_long", "high_tail_long"]

# CVaR percentile (5% = canonical Expected Shortfall)
CVAR_PCT = 5

# Transaction costs: 10bps round-trip => 5bps per side
COST_PER_SIDE = 0.0005

# Walk-forward config
WF_FOLDS     = 6
WF_TRAIN_MIN = 270  # minimum IS training days per fold
WF_TEST_DAYS = 90   # OOS days per fold


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_daily_data():
    """Load 1d parquet files for all assets. Returns DataFrame of closes."""
    data_dir = ROOT / "data"
    closes_dict = {}
    for sym in ASSETS_ALL:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if not path.exists():
            print(f"  WARNING: {path.name} not found — skipping {sym}")
            continue
        df = pd.read_parquet(path)
        if "close" not in df.columns:
            print(f"  WARNING: {path.name} has no 'close' column — skipping {sym}")
            continue
        if len(df) < 200:
            print(f"  WARNING: {path.name} only {len(df)} rows — skipping {sym}")
            continue
        closes_dict[sym] = df["close"]

    closes = pd.DataFrame(closes_dict)
    # Align on common date index, forward-fill minor gaps, drop leading NaNs
    closes = closes.dropna(how="all").ffill()
    # Drop any rows that still have all-NaN after ffill
    closes = closes.dropna(how="all")
    return closes


# ---------------------------------------------------------------------------
# Evaluation helper
# ---------------------------------------------------------------------------

def evaluate(rets, label=""):
    """Compute Sharpe, annual return, max DD from a daily return series."""
    if rets is None or len(rets) < 30:
        return None
    ann  = rets.mean() * 365
    vol  = rets.std() * np.sqrt(365)
    sharpe = ann / vol if vol > 1e-8 else 0.0
    cum  = (1 + rets).cumprod()
    dd   = (cum / cum.cummax() - 1).min()
    return {
        "label":  label,
        "sharpe": round(sharpe, 4),
        "annual": round(ann * 100, 2),
        "dd":     round(dd * 100, 2),
        "days":   len(rets),
    }


# ---------------------------------------------------------------------------
# Core backtest: CVaR cross-sectional factor
# ---------------------------------------------------------------------------

def compute_cvar(returns_window, pct):
    """
    Compute CVaR at the given percentile from a 1-D array of returns.
    Returns the mean of returns strictly below the pct-th percentile.
    If insufficient data, returns NaN.
    """
    valid = returns_window[~np.isnan(returns_window)]
    if len(valid) < max(5, pct):
        return np.nan
    threshold = np.percentile(valid, pct)
    tail = valid[valid <= threshold]
    if len(tail) == 0:
        return np.nan
    return float(np.mean(tail))


def backtest_cvar(closes, lookback, rebal_freq, n, direction):
    """
    CVaR Tail Risk Factor backtest.

    Args:
        closes:     DataFrame of daily closes (rows = dates, cols = assets)
        lookback:   Rolling window (days) for CVaR calculation
        rebal_freq: Rebalance every N calendar days
        n:          Number of longs and number of shorts
        direction:  "low_tail_long"  -> Long lowest tail risk (safest)
                    "high_tail_long" -> Long highest tail risk (riskiest)
    Returns:
        pd.Series of daily portfolio returns, or None
    """
    trade_cols = list(closes.columns)
    if len(trade_cols) < 2 * n:
        return None

    # Log returns (use pct_change as standard; log returns ≈ pct for small moves)
    returns = closes.pct_change().dropna()
    dates   = returns.index
    warmup  = lookback + 5

    portfolio_rets = []
    last_rebal     = -rebal_freq
    weights        = pd.Series(0.0, index=trade_cols)
    prev_weights   = pd.Series(0.0, index=trade_cols)

    for i in range(warmup, len(dates)):
        # Mark-to-market with current weights
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": day_ret})

        # Rebalance check
        if i - last_rebal >= rebal_freq:
            cvar_scores = {}
            for sym in trade_cols:
                if sym not in returns.columns:
                    continue
                window = returns[sym].iloc[i - lookback: i].values
                cv = compute_cvar(window, CVAR_PCT)
                if not np.isfinite(cv):
                    continue
                cvar_scores[sym] = cv

            if len(cvar_scores) < 2 * n:
                continue

            # Sort ascending: most negative CVaR first (= highest tail risk first)
            ranked = pd.Series(cvar_scores).sort_values(ascending=True)

            if direction == "low_tail_long":
                # Long least negative CVaR (tail-safe), Short most negative CVaR
                longs  = ranked.index[-n:]   # highest (least negative) CVaR
                shorts = ranked.index[:n]    # lowest (most negative) CVaR
            else:
                # high_tail_long: Long highest tail risk, Short lowest tail risk
                longs  = ranked.index[:n]    # lowest (most negative) CVaR
                shorts = ranked.index[-n:]   # highest (least negative) CVaR

            new_weights = pd.Series(0.0, index=trade_cols)
            for s in longs:
                new_weights[s] = 1.0 / n
            for s in shorts:
                new_weights[s] = -1.0 / n

            # Transaction cost proportional to turnover
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
# Reference strategy: H-012 momentum
# ---------------------------------------------------------------------------

def backtest_momentum(closes, lookback=60, rebal_freq=5, n=4):
    """Approximate H-012 cross-sectional momentum for correlation check."""
    rets   = closes.pct_change().dropna()
    dates  = rets.index
    p_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            p_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            mom     = closes.iloc[i - 1] / closes.iloc[i - 1 - lookback] - 1
            ranked  = mom.sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not p_rets:
        return None
    return pd.DataFrame(p_rets).set_index("date")["return"]


# ---------------------------------------------------------------------------
# Reference strategy: H-019 low-volatility
# ---------------------------------------------------------------------------

def backtest_lowvol(closes, lookback=30, rebal_freq=5, n=4):
    """
    Approximate H-019 low-volatility factor for correlation check.
    Long lowest-vol assets, Short highest-vol assets.
    """
    rets   = closes.pct_change().dropna()
    dates  = rets.index
    p_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    warmup  = lookback + 2
    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            p_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            vol_scores = {}
            for sym in closes.columns:
                w = rets[sym].iloc[i - lookback: i].values
                valid = w[~np.isnan(w)]
                if len(valid) < lookback // 2:
                    continue
                vol_scores[sym] = float(np.std(valid))
            if len(vol_scores) < 2 * n:
                continue
            ranked = pd.Series(vol_scores).sort_values(ascending=True)
            # low_vol_long: Long lowest vol, Short highest vol
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not p_rets:
        return None
    return pd.DataFrame(p_rets).set_index("date")["return"]


# ---------------------------------------------------------------------------
# Walk-forward validation (6 folds, 270d train / 90d OOS)
# ---------------------------------------------------------------------------

def run_walk_forward(closes, best_direction):
    """
    6-fold walk-forward. For each fold, select best IS params (from full grid
    within best_direction) on training data, then evaluate OOS.
    """
    n_total    = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        oos_end   = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break

        train_closes = closes.iloc[:oos_start]
        oos_closes   = closes.iloc[oos_start:oos_end]

        if len(train_closes) < WF_TRAIN_MIN or len(oos_closes) < 20:
            break

        # IS param selection
        best_sharpe = -np.inf
        best_params = None
        for lb in LOOKBACKS:
            for rf in REBALS:
                for nn in NS:
                    r  = backtest_cvar(train_closes, lb, rf, nn, best_direction)
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
        oos_r  = backtest_cvar(oos_closes, lb, rf, nn, best_direction)
        oos_ev = evaluate(oos_r)

        oos_start_date = closes.index[oos_start]
        oos_end_date   = closes.index[min(oos_end - 1, n_total - 1)]

        fold_results.append({
            "fold":       fold + 1,
            "is_params":  f"LB{lb}_R{rf}_N{nn}",
            "is_sharpe":  round(best_sharpe, 3),
            "oos_sharpe": oos_ev["sharpe"] if oos_ev else None,
            "oos_start":  str(oos_start_date)[:10],
            "oos_end":    str(oos_end_date)[:10],
        })

    return fold_results


# ---------------------------------------------------------------------------
# Split-half validation
# ---------------------------------------------------------------------------

def run_split_half(closes, best_direction):
    """
    Run full grid (within best_direction) on each chronological half.
    Report best-combo and mean Sharpe for each half.
    """
    half = len(closes) // 2
    h1   = closes.iloc[:half]
    h2   = closes.iloc[half:]

    h1_results, h2_results = [], []
    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                r1 = backtest_cvar(h1, lb, rf, nn, best_direction)
                r2 = backtest_cvar(h2, lb, rf, nn, best_direction)
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
        round(max(h1_sharpes),      3),
        round(max(h2_sharpes),      3),
        round(np.mean(h1_sharpes),  3),
        round(np.mean(h2_sharpes),  3),
    )


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
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  H-214: Downside Tail Risk Factor (CVaR/Expected Shortfall)")
    print("=" * 60)

    # -----------------------------------------------------------------------
    # Load data
    # -----------------------------------------------------------------------
    print("\nLoading daily OHLCV data...")
    closes   = load_daily_data()
    n_assets = len(closes.columns)
    n_days   = len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")
    print(f"Assets: {list(closes.columns)}")

    if n_assets < 6:
        print("ERROR: Too few assets loaded. Aborting.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Stage 1: IS Parameter Scan
    # -----------------------------------------------------------------------
    valid_grid = [
        (lb, rf, nn, d)
        for lb in LOOKBACKS
        for rf in REBALS
        for nn in NS
        for d  in DIRECTIONS
    ]
    total_combos = len(valid_grid)
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos, CVaR pct={CVAR_PCT}%) ---")

    all_results = []
    count = 0
    for lb, rf, nn, d in valid_grid:
        count += 1
        r  = backtest_cvar(closes, lb, rf, nn, d)
        ev = evaluate(r, f"LB{lb}_R{rf}_N{nn}_{d}")
        if ev:
            ev["lb"]        = lb
            ev["rf"]        = rf
            ev["n"]         = nn
            ev["direction"] = d
            all_results.append(ev)
        if count % 12 == 0:
            print(f"  {count}/{total_combos} done...")
    print(f"  {count}/{total_combos} done.")

    if not all_results:
        print("No valid results. REJECTED.")
        return

    df_res = pd.DataFrame(all_results)

    # Per-direction breakdown
    print("\n  Results by direction:")
    dir_stats = {}
    for d in DIRECTIONS:
        sub   = df_res[df_res["direction"] == d]
        n_pos = int((sub["sharpe"] > 0).sum())
        pct   = n_pos / len(sub) * 100 if len(sub) > 0 else 0.0
        mean_s = float(sub["sharpe"].mean()) if len(sub) > 0 else 0.0
        dir_stats[d] = {"pct_positive": pct, "mean_sharpe": mean_s, "count": len(sub)}
        print(f"    {d}: {n_pos}/{len(sub)} positive ({pct:.1f}%), mean Sharpe {mean_s:.3f}")

    # Select best direction by positive rate
    best_dir       = max(dir_stats, key=lambda d: dir_stats[d]["pct_positive"])
    pct_positive   = dir_stats[best_dir]["pct_positive"]
    mean_sharpe_bd = dir_stats[best_dir]["mean_sharpe"]

    print(f"\n  Better direction: {best_dir}")
    print(f"  Positive Sharpe: {pct_positive:.1f}%  (threshold: >= 80%)")
    print(f"  Mean Sharpe: {mean_sharpe_bd:.3f}")

    # Overall stats
    n_pos_all  = int((df_res["sharpe"] > 0).sum())
    total_val  = len(df_res)
    print(f"\n  Overall (all directions):")
    print(f"    Valid combos: {total_val}/{total_combos}")
    print(f"    Positive Sharpe: {n_pos_all}/{total_val} ({n_pos_all/total_val*100:.1f}%)")
    print(f"    Mean Sharpe: {df_res['sharpe'].mean():.3f}")
    print(f"    Median Sharpe: {df_res['sharpe'].median():.3f}")

    # Best direction subset
    df_best = df_res[df_res["direction"] == best_dir].copy().sort_values("sharpe", ascending=False)

    print(f"\n  Top 10 combos ({best_dir}):")
    for _, row in df_best.head(10).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    print(f"\n  Bottom 5 combos ({best_dir}):")
    for _, row in df_best.tail(5).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    best_row = df_best.iloc[0]
    best_lb  = int(best_row["lb"])
    best_rf  = int(best_row["rf"])
    best_n   = int(best_row["n"])

    print(f"\n  Best combo: LB{best_lb}_R{best_rf}_N{best_n} ({best_dir})")
    print(f"  Sharpe: {best_row['sharpe']:.3f}, Annual: {best_row['annual']:.1f}%, "
          f"Max DD: {best_row['dd']:.1f}%, Days: {int(best_row['days'])}")

    # IS gate
    is_pass = pct_positive >= 80.0
    if not is_pass:
        print(f"\n*** FAIL IS: {pct_positive:.1f}% positive in {best_dir} < 80% threshold ***")
        print("REJECTED at Stage 1. Skipping further validation.")

        result_json = {
            "hypothesis":      "H-214",
            "name":            "Downside Tail Risk Factor (CVaR/Expected Shortfall)",
            "status":          "REJECTED",
            "reason":          f"IS positive rate {pct_positive:.1f}% ({best_dir}) < 80% threshold",
            "cvar_pct":        CVAR_PCT,
            "best_direction":  best_dir,
            "direction_stats": {
                d: {
                    "pct_positive": round(dir_stats[d]["pct_positive"], 1),
                    "mean_sharpe":  round(dir_stats[d]["mean_sharpe"],  3),
                    "n_combos":     dir_stats[d]["count"],
                }
                for d in dir_stats
            },
            "is_positive_rate": round(pct_positive, 1),
            "is_mean_sharpe":   round(mean_sharpe_bd, 3),
            "best_params":      {"lookback": best_lb, "rebal": best_rf, "n": best_n,
                                 "direction": best_dir},
            "best_sharpe":      round(float(best_row["sharpe"]), 3),
            "best_annual_return": round(float(best_row["annual"]), 1),
            "best_max_dd":      round(float(best_row["dd"]), 1),
            "n_assets":         n_assets,
            "n_days":           n_days,
            "total_combos":     total_combos,
            "valid_combos":     total_val,
            "validation":       {"is_pass": False, "wf_pass": None,
                                 "sh_pass": None,  "corr_pass": None},
        }
        out_path = Path(__file__).parent / "results.json"
        with open(out_path, "w") as f:
            json.dump(result_json, f, indent=2)
        print(f"\nResults written to {out_path}")
        return

    # -----------------------------------------------------------------------
    # Stage 2: Walk-Forward (6 folds, 270d train / 90d OOS)
    # -----------------------------------------------------------------------
    print(f"\n--- Stage 2: Walk-Forward ({WF_FOLDS} folds, {WF_TRAIN_MIN}d train / {WF_TEST_DAYS}d OOS) ---")
    wf_results = run_walk_forward(closes, best_dir)

    wf_oos_sharpes = [r["oos_sharpe"] for r in wf_results if r["oos_sharpe"] is not None]
    wf_n_pos       = sum(1 for s in wf_oos_sharpes if s > 0)
    mean_oos       = float(np.mean(wf_oos_sharpes)) if wf_oos_sharpes else float("nan")

    for r in wf_results:
        oos_s = f"{r['oos_sharpe']:.3f}" if r["oos_sharpe"] is not None else "N/A"
        print(f"  Fold {r['fold']}: IS={r['is_params']} (IS Sharpe {r['is_sharpe']:.3f}), "
              f"OOS={r['oos_start']}~{r['oos_end']}, OOS Sharpe {oos_s}")

    print(f"\n  WF summary: {wf_n_pos}/{len(wf_oos_sharpes)} positive OOS folds, "
          f"mean OOS Sharpe: {mean_oos:.3f}")

    wf_pass = (wf_n_pos >= 4) and (not np.isnan(mean_oos)) and (mean_oos > 0)
    if not wf_pass:
        reasons = []
        if wf_n_pos < 4:
            reasons.append(f"{wf_n_pos}/{len(wf_oos_sharpes)} < 4/6 positive")
        if np.isnan(mean_oos) or mean_oos <= 0:
            reasons.append(f"mean OOS Sharpe {mean_oos:.3f} <= 0")
        print(f"  *** FAIL WF: {'; '.join(reasons)} ***")

    # -----------------------------------------------------------------------
    # Stage 3: Split-Half
    # -----------------------------------------------------------------------
    print(f"\n--- Stage 3: Split-Half Stability ---")
    sh_best_h1, sh_best_h2, sh_mean_h1, sh_mean_h2 = run_split_half(closes, best_dir)

    if sh_best_h1 is not None:
        print(f"  H1 best Sharpe: {sh_best_h1:.3f},  H1 mean Sharpe: {sh_mean_h1:.3f}")
        print(f"  H2 best Sharpe: {sh_best_h2:.3f},  H2 mean Sharpe: {sh_mean_h2:.3f}")
        sh_pass = sh_best_h1 > 0 and sh_best_h2 > 0
        if not sh_pass:
            print(f"  *** FAIL Split-Half: need both best Sharpes > 0 ***")
        else:
            print(f"  PASS: both halves have best Sharpe > 0")
    else:
        print("  Split-half: insufficient data")
        sh_pass = False

    # -----------------------------------------------------------------------
    # Stage 4: Correlation with H-012 and H-019
    # -----------------------------------------------------------------------
    print(f"\n--- Stage 4: Correlation with Reference Factors ---")
    best_rets = backtest_cvar(closes, best_lb, best_rf, best_n, best_dir)

    print("  Computing H-012 (momentum) reference returns...")
    mom_rets  = backtest_momentum(closes)
    print("  Computing H-019 (low-vol) reference returns...")
    lowv_rets = backtest_lowvol(closes)

    corr_h012 = safe_corr(best_rets, mom_rets)
    corr_h019 = safe_corr(best_rets, lowv_rets)

    print(f"  H-012 (momentum):  {corr_h012:.3f}")
    print(f"  H-019 (low-vol):   {corr_h019:.3f}")

    max_abs_corr = max(
        abs(corr_h012) if not np.isnan(corr_h012) else 0.0,
        abs(corr_h019) if not np.isnan(corr_h019) else 0.0,
    )
    corr_pass = max_abs_corr < 0.50
    if not corr_pass:
        print(f"  *** FAIL Correlation: max |corr| = {max_abs_corr:.3f} >= 0.50 ***")
    else:
        print(f"  PASS: max |corr| = {max_abs_corr:.3f} < 0.50")

    # -----------------------------------------------------------------------
    # Final Verdict
    # -----------------------------------------------------------------------
    print(f"\n{'='*60}")
    print("  FINAL VERDICT")
    print(f"{'='*60}")
    print(f"  IS positive rate ({best_dir}): {pct_positive:.1f}%  {'PASS' if is_pass else 'FAIL'}")
    print(f"  Walk-Forward: {wf_n_pos}/{len(wf_oos_sharpes)} positive, "
          f"mean OOS {mean_oos:.3f}  {'PASS' if wf_pass else 'FAIL'}")
    if sh_best_h1 is not None:
        print(f"  Split-Half: H1={sh_best_h1}, H2={sh_best_h2}  {'PASS' if sh_pass else 'FAIL'}")
    else:
        print(f"  Split-Half: insufficient data  FAIL")
    print(f"  Correlation: max |corr|={max_abs_corr:.3f}  {'PASS' if corr_pass else 'FAIL'}")

    all_pass = is_pass and wf_pass and sh_pass and corr_pass
    status   = "CONFIRMED" if all_pass else "REJECTED"

    rejection_reasons = []
    if not is_pass:
        rejection_reasons.append(f"IS positive rate {pct_positive:.1f}% < 80%")
    if not wf_pass:
        rejection_reasons.append(
            f"WF {wf_n_pos}/{len(wf_oos_sharpes)} positive, mean OOS {mean_oos:.3f}"
        )
    if not sh_pass:
        rejection_reasons.append(
            f"Split-half best Sharpes: H1={sh_best_h1}, H2={sh_best_h2}"
        )
    if not corr_pass:
        rejection_reasons.append(f"max |corr| {max_abs_corr:.3f} >= 0.50")

    print(f"\n  >>> Status: {status} <<<")
    if rejection_reasons:
        print(f"  Reason: {'; '.join(rejection_reasons)}")

    # -----------------------------------------------------------------------
    # Write results.json
    # -----------------------------------------------------------------------
    result_json = {
        "hypothesis":       "H-214",
        "name":             "Downside Tail Risk Factor (CVaR/Expected Shortfall)",
        "status":           status,
        "reason":           "; ".join(rejection_reasons) if rejection_reasons else "All 4 stages passed",
        "cvar_pct":         CVAR_PCT,
        "best_direction":   best_dir,
        "direction_stats":  {
            d: {
                "pct_positive": round(dir_stats[d]["pct_positive"], 1),
                "mean_sharpe":  round(dir_stats[d]["mean_sharpe"],  3),
                "n_combos":     dir_stats[d]["count"],
            }
            for d in dir_stats
        },
        "is_positive_rate": round(pct_positive, 1),
        "is_mean_sharpe":   round(mean_sharpe_bd, 3),
        "is_median_sharpe": round(float(df_best["sharpe"].median()), 3),
        "best_params":      {"lookback": best_lb, "rebal": best_rf, "n": best_n,
                             "direction": best_dir},
        "best_sharpe":      round(float(best_row["sharpe"]), 3),
        "best_annual_return": round(float(best_row["annual"]), 1),
        "best_max_dd":      round(float(best_row["dd"]), 1),
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
        "wf_positive_folds":  wf_n_pos      if is_pass else None,
        "wf_total_folds":     len(wf_oos_sharpes) if is_pass else None,
        "wf_mean_oos_sharpe": round(mean_oos, 3) if (is_pass and not np.isnan(mean_oos)) else None,
        "split_half": {
            "h1_best_sharpe": sh_best_h1,
            "h2_best_sharpe": sh_best_h2,
            "h1_mean_sharpe": sh_mean_h1,
            "h2_mean_sharpe": sh_mean_h2,
        } if is_pass else None,
        "correlations": {
            "H-012_momentum": corr_h012,
            "H-019_low_vol":  corr_h019,
        } if is_pass else None,
        "max_abs_correlation": round(max_abs_corr, 3) if is_pass else None,
        "n_assets":     n_assets,
        "n_days":       n_days,
        "date_start":   str(closes.index[0])[:10],
        "date_end":     str(closes.index[-1])[:10],
        "total_combos": total_combos,
        "valid_combos": total_val,
        "validation": {
            "is_pass":   bool(is_pass),
            "wf_pass":   bool(wf_pass)   if is_pass else None,
            "sh_pass":   bool(sh_pass)   if is_pass else None,
            "corr_pass": bool(corr_pass) if is_pass else None,
        },
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(result_json, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
