#!/usr/bin/env python3
"""
H-204: Idiosyncratic Volatility Factor (Cross-Sectional)

Concept: After regressing each asset's daily returns on BTC returns (market
factor), compute the residual / idiosyncratic volatility over a rolling
lookback window.  This is different from total volatility (H-019 already
does that).

"Idiosyncratic volatility puzzle" — in equities, low-idio-vol stocks tend
to outperform (Ang et al., 2006). We test both directions in crypto.

Logic:
  For each non-BTC asset on each rebalance day:
    1. Rolling OLS: r_asset = alpha + beta * r_BTC + epsilon
       over the lookback window
    2. idio_vol = std(epsilon) * sqrt(365)   (annualised)
  For BTC itself: use its own total vol (it has no market regressor to strip).
  Rank assets cross-sectionally by idio_vol.
  Two directions tested:
    - low_ivol_long  : Long low idio-vol (stable alpha generators),
                       Short high idio-vol (noisy)
    - high_ivol_long : Long high idio-vol, Short low idio-vol
  Dollar-neutral, equal weight within legs.

Transaction costs: 0.05% per side (0.10% round trip) on each rebalance.

Parameter grid:
  LB (lookback)   : [10, 20, 30, 60]
  Rebalance        : [3, 5, 7]
  N (top/bottom)   : [3, 4, 5]
  Direction         : [low_ivol_long, high_ivol_long]
  Total: 4 x 3 x 3 x 2 = 72 combos

Validation (4-stage):
  1. IS  : >= 80% of combos in the better direction must have positive Sharpe
  2. WF  : 6 folds, best IS params per fold, need >= 4/6 positive OOS folds
  3. SH  : Split-half — best-combo Sharpe > 0 in both halves
  4. Corr: max |corr| < 0.50 with H-012 momentum
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# ----- Assets ---------------------------------------------------------------

ASSETS_ALL = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]
BTC_SYM = "BTC/USDT"

# ----- Parameter grid -------------------------------------------------------

LOOKBACKS  = [10, 20, 30, 60]
REBALS     = [3, 5, 7]
NS         = [3, 4, 5]
DIRECTIONS = ["low_ivol_long", "high_ivol_long"]

COST_PER_SIDE = 0.0005   # 5 bps per side

# ----- Walk-forward config --------------------------------------------------

WF_FOLDS     = 6
WF_TEST_DAYS = 90
WF_TRAIN_MIN = 120


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_daily_data():
    """Load 1d parquet files for all assets (or aggregate from 1h)."""
    data_dir = ROOT / "data"
    closes_dict = {}

    for sym in ASSETS_ALL:
        safe = sym.replace("/", "_")
        # Prefer 1d parquet; fall back to aggregating from 1h
        path_1d = data_dir / f"{safe}_1d.parquet"
        path_1h = data_dir / f"{safe}_1h.parquet"

        if path_1d.exists():
            df = pd.read_parquet(path_1d)
            if "close" in df.columns and len(df) >= 200:
                closes_dict[sym] = df["close"]
                continue

        if path_1h.exists():
            df = pd.read_parquet(path_1h)
            # Handle open_time column (various naming)
            time_col = None
            for c in ("open_time", "timestamp", "date", "time"):
                if c in df.columns:
                    time_col = c
                    break
            if time_col is None:
                df["_ts"] = df.index
                time_col = "_ts"
            df["date"] = pd.to_datetime(df[time_col]).dt.date
            daily = df.groupby("date").agg({"close": "last"})
            daily.index = pd.to_datetime(daily.index)
            if len(daily) >= 200:
                closes_dict[sym] = daily["close"]

    if not closes_dict:
        return None

    closes = pd.DataFrame(closes_dict)
    closes = closes.dropna(how="all").ffill().dropna()
    return closes


# ---------------------------------------------------------------------------
# Idiosyncratic volatility computation
# ---------------------------------------------------------------------------

def compute_idio_vol_rolling(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    For each non-BTC asset, compute rolling idio_vol via OLS on BTC returns.
    For BTC itself, use its own rolling total vol.

    Returns a DataFrame of idio_vol values with the same index as `returns`.
    Result is annualised (std * sqrt(365)).
    """
    assets = list(returns.columns)
    btc_col = BTC_SYM
    if btc_col not in assets:
        raise ValueError(f"BTC column '{btc_col}' not found in returns DataFrame")

    btc_rets = returns[btc_col].values
    n = len(returns)

    idio_vol = np.full((n, len(assets)), np.nan, dtype=float)

    for j, sym in enumerate(assets):
        asset_rets = returns[sym].values
        if sym == btc_col:
            # BTC: use total vol
            for i in range(lookback - 1, n):
                window = asset_rets[i - lookback + 1: i + 1]
                if np.sum(np.isfinite(window)) >= lookback // 2:
                    idio_vol[i, j] = np.nanstd(window) * np.sqrt(365)
        else:
            # Non-BTC: OLS residuals
            for i in range(lookback - 1, n):
                y = asset_rets[i - lookback + 1: i + 1]
                x = btc_rets[i - lookback + 1: i + 1]
                mask = np.isfinite(x) & np.isfinite(y)
                if mask.sum() < lookback // 2:
                    continue
                xm = x[mask]
                ym = y[mask]
                # OLS: y = alpha + beta * x
                xb = np.column_stack([np.ones_like(xm), xm])
                try:
                    coeffs, _, _, _ = np.linalg.lstsq(xb, ym, rcond=None)
                    residuals = ym - xb @ coeffs
                    idio_vol[i, j] = np.std(residuals) * np.sqrt(365)
                except Exception:
                    continue

    return pd.DataFrame(idio_vol, index=returns.index, columns=assets)


# ---------------------------------------------------------------------------
# Evaluation helper
# ---------------------------------------------------------------------------

def evaluate(rets, label=""):
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


# ---------------------------------------------------------------------------
# Core backtest
# ---------------------------------------------------------------------------

def backtest_idio_vol(closes: pd.DataFrame, lookback: int,
                      rebal_freq: int, n: int, direction: str,
                      idio_vol_cache: pd.DataFrame = None):
    """
    Idiosyncratic Volatility Factor backtest.

    Args:
        closes       : DataFrame of daily closes
        lookback     : rolling OLS window
        rebal_freq   : rebalance every N days
        n            : number of longs and shorts
        direction    : "low_ivol_long" or "high_ivol_long"
        idio_vol_cache: pre-computed idio_vol DataFrame (to avoid recomputing)
    Returns:
        pd.Series of daily portfolio returns (or None)
    """
    assets = list(closes.columns)
    if len(assets) < 2 * n:
        return None

    returns = closes.pct_change().dropna()

    # Use cached idio_vol aligned to returns, or compute fresh
    if idio_vol_cache is not None:
        # Reindex to match returns index; recompute only lookback window matters
        iv = idio_vol_cache.reindex(returns.index)
    else:
        iv = compute_idio_vol_rolling(returns, lookback)

    dates = returns.index
    warmup = lookback + 5

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=assets)
    prev_weights = pd.Series(0.0, index=assets)

    for i in range(warmup, len(dates)):
        # Apply existing weights
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": day_ret})

        # Rebalance check
        if i - last_rebal >= rebal_freq:
            iv_row = iv.iloc[i]
            valid = iv_row.dropna()
            if len(valid) < 2 * n:
                continue

            if direction == "low_ivol_long":
                ranked = valid.sort_values(ascending=True)
                longs  = ranked.index[:n]
                shorts = ranked.index[-n:]
            else:
                ranked = valid.sort_values(ascending=False)
                longs  = ranked.index[:n]
                shorts = ranked.index[-n:]

            new_weights = pd.Series(0.0, index=assets)
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


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------

def run_walk_forward(closes: pd.DataFrame, best_direction: str):
    n_total = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        oos_end   = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break

        train_c = closes.iloc[:oos_start]
        oos_c   = closes.iloc[oos_start:oos_end]

        if len(train_c) < WF_TRAIN_MIN or len(oos_c) < 20:
            break

        # Pre-compute idio_vol for training set per lookback
        best_sharpe = -np.inf
        best_params = None
        for lb in LOOKBACKS:
            train_rets = train_c.pct_change().dropna()
            iv_train = compute_idio_vol_rolling(train_rets, lb)
            for rf in REBALS:
                for nn in NS:
                    r = backtest_idio_vol(train_c, lb, rf, nn, best_direction,
                                          idio_vol_cache=iv_train)
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
        oos_rets = oos_c.pct_change().dropna()
        iv_oos   = compute_idio_vol_rolling(oos_rets, lb)
        oos_r    = backtest_idio_vol(oos_c, lb, rf, nn, best_direction,
                                     idio_vol_cache=iv_oos)
        oos_e    = evaluate(oos_r)

        oos_start_date = closes.index[oos_start]
        oos_end_date   = closes.index[min(oos_end - 1, len(closes) - 1)]

        fold_results.append({
            "fold":       fold + 1,
            "is_params":  f"LB{lb}_R{rf}_N{nn}",
            "is_sharpe":  round(best_sharpe, 3),
            "oos_sharpe": oos_e["sharpe"] if oos_e else None,
            "oos_start":  str(oos_start_date)[:10],
            "oos_end":    str(oos_end_date)[:10],
        })

    return fold_results


# ---------------------------------------------------------------------------
# Split-half validation
# ---------------------------------------------------------------------------

def run_split_half(closes: pd.DataFrame, best_direction: str):
    half   = len(closes) // 2
    h1_c   = closes.iloc[:half]
    h2_c   = closes.iloc[half:]

    h1_results, h2_results = [], []
    for lb in LOOKBACKS:
        h1_rets = h1_c.pct_change().dropna()
        iv_h1   = compute_idio_vol_rolling(h1_rets, lb)
        h2_rets = h2_c.pct_change().dropna()
        iv_h2   = compute_idio_vol_rolling(h2_rets, lb)

        for rf in REBALS:
            for nn in NS:
                r1 = backtest_idio_vol(h1_c, lb, rf, nn, best_direction, iv_h1)
                r2 = backtest_idio_vol(h2_c, lb, rf, nn, best_direction, iv_h2)
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


# ---------------------------------------------------------------------------
# Reference momentum (H-012) for correlation
# ---------------------------------------------------------------------------

def backtest_momentum(closes: pd.DataFrame, lookback=60, rebal_freq=5, n=4):
    rets   = closes.pct_change().dropna()
    dates  = rets.index
    prets  = []
    last_r = -rebal_freq
    wts    = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if wts.abs().sum() > 0:
            prets.append({"date": dates[i], "return": (rets.iloc[i] * wts).sum()})
        if i - last_r >= rebal_freq:
            mom    = closes.iloc[i - 1] / closes.iloc[i - 1 - lookback] - 1
            ranked = mom.sort_values(ascending=False)
            wts    = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                wts[s] = 1.0 / n
            for s in ranked.index[-n:]:
                wts[s] = -1.0 / n
            last_r = i
    if not prets:
        return None
    return pd.DataFrame(prets).set_index("date")["return"]


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
    print("  H-204: Idiosyncratic Volatility Factor")
    print("=" * 60)

    print("\nLoading daily close data...")
    closes = load_daily_data()
    if closes is None or closes.empty:
        print("ERROR: No data loaded. Aborting.")
        sys.exit(1)

    n_assets = len(closes.columns)
    n_days   = len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0].date()} -> {closes.index[-1].date()}")
    print(f"Assets: {list(closes.columns)}")

    if n_assets < 6:
        print("ERROR: Too few assets. Aborting.")
        sys.exit(1)

    # Make sure BTC is present (needed as regressor)
    if BTC_SYM not in closes.columns:
        print(f"ERROR: {BTC_SYM} not found in closes. Aborting.")
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

    # Pre-compute idio_vol per lookback to avoid recomputing for each (rf, n) combo
    print("  Pre-computing idiosyncratic volatility per lookback window...")
    returns = closes.pct_change().dropna()
    iv_cache = {}
    for lb in LOOKBACKS:
        print(f"    lookback={lb} ...", end=" ", flush=True)
        iv_cache[lb] = compute_idio_vol_rolling(returns, lb)
        print("done")

    all_results = []
    count = 0
    for lb, rf, nn, d in valid_grid:
        count += 1
        r  = backtest_idio_vol(closes, lb, rf, nn, d, idio_vol_cache=iv_cache[lb])
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

    # Analyse by direction
    print(f"\n  Results by direction:")
    dir_stats = {}
    for d in DIRECTIONS:
        sub   = df_res[df_res["direction"] == d]
        n_pos = (sub["sharpe"] > 0).sum()
        pct   = n_pos / len(sub) * 100 if len(sub) > 0 else 0
        mean_s = sub["sharpe"].mean() if len(sub) > 0 else 0
        dir_stats[d] = {
            "pct_positive": pct,
            "mean_sharpe":  mean_s,
            "count":        len(sub),
        }
        print(f"    {d}: {n_pos}/{len(sub)} positive ({pct:.1f}%), mean Sharpe {mean_s:.3f}")

    best_dir       = max(dir_stats, key=lambda d: dir_stats[d]["pct_positive"])
    best_dir_stats = dir_stats[best_dir]
    pct_positive   = best_dir_stats["pct_positive"]
    mean_sharpe_bd = best_dir_stats["mean_sharpe"]

    print(f"\n  Better direction: {best_dir}")
    print(f"  Positive Sharpe : {pct_positive:.1f}%")
    print(f"  Mean Sharpe     : {mean_sharpe_bd:.3f}")

    n_positive_all   = (df_res["sharpe"] > 0).sum()
    mean_sharpe_all  = df_res["sharpe"].mean()
    median_sharpe_all = df_res["sharpe"].median()
    print(f"\n  Overall (all directions):")
    print(f"  Valid combos: {len(df_res)}/{total_combos}")
    print(f"  Positive Sharpe: {n_positive_all}/{len(df_res)} ({n_positive_all/len(df_res)*100:.1f}%)")
    print(f"  Mean Sharpe: {mean_sharpe_all:.3f}")
    print(f"  Median Sharpe: {median_sharpe_all:.3f}")

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
            "hypothesis": "H-204",
            "name": "Idiosyncratic Volatility Factor",
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
            "is_mean_sharpe": round(mean_sharpe_bd, 3),
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
    wf_results = run_walk_forward(closes, best_dir)

    wf_oos_sharpes = [r["oos_sharpe"] for r in wf_results if r["oos_sharpe"] is not None]
    wf_n_pos       = sum(1 for s in wf_oos_sharpes if s > 0)

    for r in wf_results:
        oos_s = f"{r['oos_sharpe']:.3f}" if r["oos_sharpe"] is not None else "N/A"
        print(f"  Fold {r['fold']}: IS={r['is_params']} (IS Sharpe {r['is_sharpe']:.3f}), "
              f"OOS={r['oos_start']}~{r['oos_end']}, OOS Sharpe {oos_s}")

    mean_oos = np.mean(wf_oos_sharpes) if wf_oos_sharpes else float("nan")
    print(f"\n  WF summary: {wf_n_pos}/{len(wf_oos_sharpes)} positive OOS folds, "
          f"mean OOS Sharpe: {mean_oos:.3f}")

    wf_pass = wf_n_pos >= 4
    if not wf_pass:
        print(f"  *** FAIL WF: {wf_n_pos}/{len(wf_oos_sharpes)} < 4/6 threshold ***")

    # ==================================================================
    # Stage 3: Split-Half Stability
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
    print(f"\n--- Stage 4: Correlation with H-012 ---")
    best_rets = backtest_idio_vol(closes, best_lb, best_rf, best_n, best_dir,
                                   idio_vol_cache=iv_cache[best_lb])
    print("  Computing H-012 momentum returns...")
    mom_rets  = backtest_momentum(closes)

    corr_h012     = safe_corr(best_rets, mom_rets)
    max_abs_corr  = abs(corr_h012) if not np.isnan(corr_h012) else 0.0
    corr_pass     = max_abs_corr < 0.50

    print(f"  H-012 (momentum): {corr_h012:.3f}")
    if not corr_pass:
        print(f"  *** FAIL Correlation: max |corr| = {max_abs_corr:.3f} >= 0.50 ***")
    else:
        print(f"  PASS: max |corr| = {max_abs_corr:.3f} < 0.50")

    # ==================================================================
    # Final Verdict
    # ==================================================================
    print(f"\n{'='*60}")
    print("  FINAL VERDICT")
    print(f"{'='*60}")
    print(f"  IS positive rate: {pct_positive:.1f}% {'PASS' if is_pass else 'FAIL'}")
    print(f"  Walk-Forward: {wf_n_pos}/{len(wf_oos_sharpes)} positive {'PASS' if wf_pass else 'FAIL'}")
    if sh_best_h1 is not None:
        print(f"  Split-Half: H1={sh_best_h1}, H2={sh_best_h2} {'PASS' if sh_pass else 'FAIL'}")
    else:
        print(f"  Split-Half: insufficient data FAIL")
    print(f"  Correlation: max |corr|={max_abs_corr:.3f} {'PASS' if corr_pass else 'FAIL'}")

    all_pass  = is_pass and wf_pass and sh_pass and corr_pass
    status    = "CONFIRMED" if all_pass else "REJECTED"
    rejection_reasons = []
    if not is_pass:
        rejection_reasons.append(f"IS positive rate {pct_positive:.1f}% < 80%")
    if not wf_pass:
        rejection_reasons.append(f"WF {wf_n_pos}/{len(wf_oos_sharpes)} < 4/6")
    if not sh_pass:
        rejection_reasons.append(f"Split-half best Sharpes: H1={sh_best_h1}, H2={sh_best_h2}")
    if not corr_pass:
        rejection_reasons.append(f"max |corr| {max_abs_corr:.3f} >= 0.50")

    print(f"\n  Status: {status}")
    if rejection_reasons:
        print(f"  Reason: {'; '.join(rejection_reasons)}")

    # ==================================================================
    # Write results.json
    # ==================================================================
    result_json = {
        "hypothesis": "H-204",
        "name": "Idiosyncratic Volatility Factor",
        "status": status,
        "reason": "; ".join(rejection_reasons) if rejection_reasons else "All 4 stages passed",
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
        "is_mean_sharpe": round(mean_sharpe_bd, 3),
        "is_median_sharpe": round(float(df_best["sharpe"].median()), 3),
        "best_params": {
            "lookback": best_lb, "rebal": best_rf, "n": best_n, "direction": best_dir
        },
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
            "H-012_momentum": corr_h012,
        } if is_pass else None,
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
