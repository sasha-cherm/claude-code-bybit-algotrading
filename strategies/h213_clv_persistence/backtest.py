#!/usr/bin/env python3
"""
H-213: Intrabar Momentum Consistency (CLV Persistence)

Concept:
  Close Location Value (CLV) = (2*close - high - low) / (high - low)
  measures where within the day's range the close lands.
  CLV = +1  → close at the high (strong buying pressure)
  CLV = -1  → close at the low  (strong selling pressure)
  CLV =  0  → close at the midpoint

  H-186 tested raw daily CLV as a ranking signal and got IS 56.7% — REJECTED.
  This hypothesis is different: we smooth the CLV over a rolling lookback window.
  The hypothesis is that assets with persistently high rolling-mean CLV have
  systematic institutional buying pressure and subsequently outperform, while
  assets with persistently low rolling-mean CLV (sellers dominating) underperform.

  Factor = rolling_mean(CLV, lookback)

Logic:
  Each rebalance day:
    1. Compute CLV for each asset over the last `lookback` days
    2. Rank assets by their mean(CLV): highest = persistent buying, lowest = persistent selling
    3. Long top N, Short bottom N → dollar-neutral, equal weight

Transaction costs: 10bps round-trip (5bps per side × turnover).

Parameter grid:
  Lookback  : [5, 10, 15, 20, 30]
  Rebalance : [3, 5, 7]
  N         : [3, 4]
  Total: 5 × 3 × 2 = 30 combos

Validation (4-stage):
  1. IS: ≥ 80% of combos must have positive Sharpe
  2. Walk-Forward: 6 folds (270d train / 90d test), ≥ 4/6 folds positive OOS
  3. Split-Half: both halves' best-combo Sharpe > 0
  4. Correlation: max |corr| < 0.50 with H-012 (cross-sectional momentum)

CONFIRMED if all 4 stages pass, else REJECTED.
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
LOOKBACKS = [5, 10, 15, 20, 30]
REBALS    = [3, 5, 7]
NS        = [3, 4]

# Transaction cost: 10bps round-trip → 5bps per side
COST_PER_SIDE = 0.0005

# Walk-forward config
WF_FOLDS     = 6
WF_TEST_DAYS = 90
WF_TRAIN_MIN = 120


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_daily_data():
    """
    Load 1d parquet files. Returns three aligned DataFrames:
      closes, highs, lows  (DatetimeIndex, columns = asset symbols)
    """
    data_dir = ROOT / "data"
    closes_d, highs_d, lows_d = {}, {}, {}

    for sym in ASSETS_ALL:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if not path.exists():
            print(f"  WARNING: {path.name} not found — skipping {sym}")
            continue
        df = pd.read_parquet(path)
        needed = ["close", "high", "low"]
        if not all(c in df.columns for c in needed):
            print(f"  WARNING: {sym} missing columns — skipping")
            continue
        if len(df) < 200:
            print(f"  WARNING: {sym} only {len(df)} rows — skipping")
            continue
        closes_d[sym] = df["close"]
        highs_d[sym]  = df["high"]
        lows_d[sym]   = df["low"]

    closes = pd.DataFrame(closes_d)
    highs  = pd.DataFrame(highs_d)
    lows   = pd.DataFrame(lows_d)

    # Align on common trading dates
    common_idx = closes.index
    for df_ in [highs, lows]:
        common_idx = common_idx.intersection(df_.index)
    closes = closes.loc[common_idx].dropna(how="all").ffill()
    highs  = highs.loc[common_idx].dropna(how="all").ffill()
    lows   = lows.loc[common_idx].dropna(how="all").ffill()

    # Keep only columns present in all three
    cols = list(set(closes.columns) & set(highs.columns) & set(lows.columns))
    cols.sort()
    closes = closes[cols].dropna()
    highs  = highs[cols].reindex(closes.index).dropna()
    lows   = lows[cols].reindex(closes.index).dropna()

    return closes, highs, lows


# ---------------------------------------------------------------------------
# Metrics helper
# ---------------------------------------------------------------------------

def evaluate(rets, label=""):
    """Compute Sharpe, annual return, max drawdown from a daily return series."""
    if rets is None or len(rets) < 30:
        return None
    ann = rets.mean() * 365
    vol = rets.std() * np.sqrt(365)
    sharpe = ann / vol if vol > 1e-8 else 0.0
    cum = (1 + rets).cumprod()
    dd = (cum / cum.cummax() - 1).min()
    return {
        "label":  label,
        "sharpe": round(float(sharpe), 4),
        "annual": round(float(ann * 100), 2),
        "dd":     round(float(dd * 100), 2),
        "days":   len(rets),
    }


# ---------------------------------------------------------------------------
# Core backtest
# ---------------------------------------------------------------------------

def compute_clv(closes, highs, lows):
    """
    CLV = (2*close - high - low) / (high - low)
    Handle the edge case where high == low (zero range → CLV = 0).
    Returns DataFrame aligned with closes.
    """
    hl = highs - lows
    hl_safe = hl.replace(0, np.nan)
    clv = (2 * closes - highs - lows) / hl_safe
    clv = clv.fillna(0.0)
    # Clip to [-1, 1] to handle any floating-point oddities
    clv = clv.clip(-1.0, 1.0)
    return clv


def backtest_clv_persistence(closes, highs, lows, lookback, rebal_freq, n):
    """
    CLV Persistence factor backtest.

    Args:
        closes, highs, lows : aligned DataFrames
        lookback   : rolling window for mean CLV
        rebal_freq : rebalance every N days
        n          : number of longs and shorts

    Returns: pd.Series of daily portfolio returns (or None)
    """
    trade_cols = list(closes.columns)
    if len(trade_cols) < 2 * n:
        return None

    clv = compute_clv(closes, highs, lows)
    returns = closes.pct_change().dropna()

    # Align clv to returns index
    clv = clv.reindex(returns.index)

    dates = returns.index
    warmup = lookback + 5

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=trade_cols)
    prev_weights = pd.Series(0.0, index=trade_cols)

    for i in range(warmup, len(dates)):
        # Apply existing weights to get today's P&L
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": float(day_ret)})

        # Rebalance?
        if i - last_rebal >= rebal_freq:
            # Compute rolling mean CLV for each asset over [i-lookback, i)
            scores = {}
            for sym in trade_cols:
                window = clv[sym].iloc[i - lookback: i].values
                valid = window[np.isfinite(window)]
                if len(valid) < lookback // 2:
                    continue
                scores[sym] = float(np.mean(valid))

            if len(scores) < 2 * n:
                continue

            ranked = pd.Series(scores).sort_values(ascending=False)
            # High mean CLV  → persistent buyers  → long
            # Low  mean CLV  → persistent sellers → short
            longs  = ranked.index[:n]
            shorts = ranked.index[-n:]

            new_weights = pd.Series(0.0, index=trade_cols)
            for s in longs:
                new_weights[s] = 1.0 / n
            for s in shorts:
                new_weights[s] = -1.0 / n

            # Transaction costs proportional to turnover
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
# Reference factor: H-012 cross-sectional momentum (for correlation)
# ---------------------------------------------------------------------------

def backtest_momentum(closes, lookback=60, rebal_freq=5, n=4):
    """H-012 cross-sectional momentum."""
    rets = closes.pct_change().dropna()
    dates = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append(
                {"date": dates[i], "return": float((rets.iloc[i] * weights).sum())}
            )
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
# Walk-forward validation
# ---------------------------------------------------------------------------

def run_walk_forward(closes, highs, lows):
    """
    6-fold walk-forward. Each fold: select best IS params on train, evaluate OOS.
    Folds are anchored from the most recent data backwards.
    """
    n_total = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        oos_end   = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break

        tr_c = closes.iloc[:oos_start]
        tr_h = highs.iloc[:oos_start]
        tr_l = lows.iloc[:oos_start]
        oo_c = closes.iloc[oos_start:oos_end]
        oo_h = highs.iloc[oos_start:oos_end]
        oo_l = lows.iloc[oos_start:oos_end]

        if len(tr_c) < WF_TRAIN_MIN or len(oo_c) < 20:
            break

        # Select best IS params
        best_sharpe = -np.inf
        best_params = None
        for lb in LOOKBACKS:
            for rf in REBALS:
                for nn in NS:
                    r = backtest_clv_persistence(tr_c, tr_h, tr_l, lb, rf, nn)
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
        oos_r = backtest_clv_persistence(oo_c, oo_h, oo_l, lb, rf, nn)
        oos_e = evaluate(oos_r)

        oos_start_date = str(closes.index[oos_start])[:10]
        oos_end_date   = str(closes.index[min(oos_end - 1, n_total - 1)])[:10]

        fold_results.append({
            "fold":       fold + 1,
            "is_params":  f"LB{lb}_R{rf}_N{nn}",
            "is_sharpe":  round(float(best_sharpe), 3),
            "oos_sharpe": oos_e["sharpe"] if oos_e else None,
            "oos_start":  oos_start_date,
            "oos_end":    oos_end_date,
        })

    return fold_results


# ---------------------------------------------------------------------------
# Split-half validation
# ---------------------------------------------------------------------------

def run_split_half(closes, highs, lows):
    """Run full grid on each half, report best and mean Sharpe per half."""
    half = len(closes) // 2
    h1_c, h1_h, h1_l = closes.iloc[:half], highs.iloc[:half], lows.iloc[:half]
    h2_c, h2_h, h2_l = closes.iloc[half:], highs.iloc[half:], lows.iloc[half:]

    h1_res, h2_res = [], []

    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                r1 = backtest_clv_persistence(h1_c, h1_h, h1_l, lb, rf, nn)
                r2 = backtest_clv_persistence(h2_c, h2_h, h2_l, lb, rf, nn)
                e1 = evaluate(r1)
                e2 = evaluate(r2)
                if e1:
                    h1_res.append(e1)
                if e2:
                    h2_res.append(e2)

    if not h1_res or not h2_res:
        return None, None, None, None

    h1_s = [r["sharpe"] for r in h1_res]
    h2_s = [r["sharpe"] for r in h2_res]

    return (
        round(max(h1_s), 3),
        round(max(h2_s), 3),
        round(float(np.mean(h1_s)), 3),
        round(float(np.mean(h2_s)), 3),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  H-213: Intrabar Momentum Consistency (CLV Persistence)")
    print("=" * 60)

    print("\nLoading daily OHLCV data...")
    closes, highs, lows = load_daily_data()
    n_assets = len(closes.columns)
    n_days   = len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")
    print(f"Assets: {list(closes.columns)}")

    if n_assets < 6:
        print("ERROR: Too few assets — aborting.")
        sys.exit(1)

    # Quick CLV sanity check
    clv_sample = compute_clv(closes, highs, lows)
    print(f"\nCLV sanity (BTC/USDT last 5 days):\n{clv_sample['BTC/USDT'].tail(5).round(3)}")

    # ======================================================================
    # Stage 1: In-Sample Parameter Scan
    # ======================================================================
    valid_grid = [
        (lb, rf, nn)
        for lb in LOOKBACKS
        for rf in REBALS
        for nn in NS
    ]
    total_combos = len(valid_grid)
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")

    all_results = []
    for idx, (lb, rf, nn) in enumerate(valid_grid, 1):
        r = backtest_clv_persistence(closes, highs, lows, lb, rf, nn)
        ev = evaluate(r, f"LB{lb}_R{rf}_N{nn}")
        if ev:
            ev["lb"] = lb
            ev["rf"] = rf
            ev["n"]  = nn
            all_results.append(ev)
        if idx % 10 == 0:
            print(f"  {idx}/{total_combos} done...")
    print(f"  {total_combos}/{total_combos} done.")

    if not all_results:
        print("No valid results — REJECTED.")
        return

    df_res = pd.DataFrame(all_results)

    n_positive  = (df_res["sharpe"] > 0).sum()
    pct_positive = n_positive / len(df_res) * 100
    mean_sharpe  = df_res["sharpe"].mean()
    median_sharpe = df_res["sharpe"].median()

    print(f"\n  Valid combos: {len(df_res)}/{total_combos}")
    print(f"  Positive Sharpe: {n_positive}/{len(df_res)} ({pct_positive:.1f}%)")
    print(f"  Mean Sharpe:   {mean_sharpe:.3f}")
    print(f"  Median Sharpe: {median_sharpe:.3f}")

    df_sorted = df_res.sort_values("sharpe", ascending=False)

    print(f"\n  Top 10 combos:")
    for _, row in df_sorted.head(10).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    print(f"\n  Bottom 5 combos:")
    for _, row in df_sorted.tail(5).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    best_row = df_sorted.iloc[0]
    best_lb  = int(best_row["lb"])
    best_rf  = int(best_row["rf"])
    best_n   = int(best_row["n"])

    print(f"\n  Best combo: LB{best_lb}_R{best_rf}_N{best_n}")
    print(f"  Sharpe: {best_row['sharpe']:.3f}, Annual: {best_row['annual']:.1f}%, "
          f"Max DD: {best_row['dd']:.1f}%, Days: {int(best_row['days'])}")

    # IS gate
    is_pass = pct_positive >= 80.0
    if not is_pass:
        print(f"\n*** FAIL IS: {pct_positive:.1f}% positive < 80% threshold ***")
        print("REJECTED at Stage 1 — skipping further validation.")
        _write_results(
            status="REJECTED",
            reason=f"IS positive rate {pct_positive:.1f}% < 80% threshold",
            pct_positive=pct_positive,
            mean_sharpe=mean_sharpe,
            median_sharpe=float(median_sharpe),
            best_lb=best_lb, best_rf=best_rf, best_n=best_n,
            best_row=best_row,
            n_assets=n_assets, n_days=n_days,
            total_combos=total_combos, valid_combos=len(df_res),
            wf_results=[], wf_n_pos=None, mean_oos=None,
            sh_best_h1=None, sh_best_h2=None,
            sh_mean_h1=None, sh_mean_h2=None,
            corr_h012=None, max_abs_corr=None,
            validation={"is_pass": False, "wf_pass": None, "sh_pass": None, "corr_pass": None},
        )
        return

    # ======================================================================
    # Stage 2: Walk-Forward Validation
    # ======================================================================
    print(f"\n--- Stage 2: Walk-Forward ({WF_FOLDS} folds, {WF_TEST_DAYS}d OOS each) ---")
    wf_results = run_walk_forward(closes, highs, lows)

    wf_oos_sharpes = [r["oos_sharpe"] for r in wf_results if r["oos_sharpe"] is not None]
    wf_n_pos = sum(1 for s in wf_oos_sharpes if s > 0)
    mean_oos = float(np.mean(wf_oos_sharpes)) if wf_oos_sharpes else float("nan")

    for r in wf_results:
        oos_s = f"{r['oos_sharpe']:.3f}" if r["oos_sharpe"] is not None else "N/A"
        print(f"  Fold {r['fold']}: IS={r['is_params']} (IS Sharpe {r['is_sharpe']:.3f}), "
              f"OOS={r['oos_start']}~{r['oos_end']}, OOS Sharpe {oos_s}")

    print(f"\n  WF summary: {wf_n_pos}/{len(wf_oos_sharpes)} positive OOS folds, "
          f"mean OOS Sharpe: {mean_oos:.3f}")

    wf_pass = wf_n_pos >= 4
    if not wf_pass:
        print(f"  *** FAIL WF: {wf_n_pos}/{len(wf_oos_sharpes)} < 4/6 threshold ***")

    # ======================================================================
    # Stage 3: Split-Half Stability
    # ======================================================================
    print(f"\n--- Stage 3: Split-Half Stability ---")
    sh_best_h1, sh_best_h2, sh_mean_h1, sh_mean_h2 = run_split_half(closes, highs, lows)

    if sh_best_h1 is not None:
        print(f"  H1 best Sharpe: {sh_best_h1:.3f}, H1 mean Sharpe: {sh_mean_h1:.3f}")
        print(f"  H2 best Sharpe: {sh_best_h2:.3f}, H2 mean Sharpe: {sh_mean_h2:.3f}")
        sh_pass = sh_best_h1 > 0 and sh_best_h2 > 0
        if not sh_pass:
            print(f"  *** FAIL Split-Half: need both best Sharpes > 0 ***")
        else:
            print(f"  PASS: both halves positive")
    else:
        print("  Split-half: insufficient data")
        sh_pass = False

    # ======================================================================
    # Stage 4: Correlation with H-012
    # ======================================================================
    print(f"\n--- Stage 4: Correlation with H-012 (momentum) ---")
    best_rets = backtest_clv_persistence(closes, highs, lows, best_lb, best_rf, best_n)
    mom_rets  = backtest_momentum(closes)
    corr_h012 = safe_corr(best_rets, mom_rets)
    max_abs_corr = abs(corr_h012) if not np.isnan(corr_h012) else 0.0

    print(f"  H-012 (momentum): {corr_h012:.3f}")
    corr_pass = max_abs_corr < 0.50
    if not corr_pass:
        print(f"  *** FAIL Correlation: |corr| = {max_abs_corr:.3f} >= 0.50 ***")
    else:
        print(f"  PASS: |corr| = {max_abs_corr:.3f} < 0.50")

    # ======================================================================
    # Final Verdict
    # ======================================================================
    print(f"\n{'='*60}")
    print("  FINAL VERDICT")
    print(f"{'='*60}")
    print(f"  IS positive rate:  {pct_positive:.1f}%   {'PASS' if is_pass else 'FAIL'}")
    print(f"  Walk-Forward:      {wf_n_pos}/{len(wf_oos_sharpes)} positive   {'PASS' if wf_pass else 'FAIL'}")
    print(f"  Split-Half:        H1={sh_best_h1}, H2={sh_best_h2}   {'PASS' if sh_pass else 'FAIL'}")
    print(f"  Correlation:       max |corr|={max_abs_corr:.3f}   {'PASS' if corr_pass else 'FAIL'}")

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
        rejection_reasons.append(f"max |corr| {max_abs_corr:.3f} >= 0.50")

    print(f"\n  Status: {status}")
    if rejection_reasons:
        print(f"  Reason: {'; '.join(rejection_reasons)}")

    _write_results(
        status=status,
        reason="; ".join(rejection_reasons) if rejection_reasons else "All 4 stages passed",
        pct_positive=pct_positive,
        mean_sharpe=mean_sharpe,
        median_sharpe=float(median_sharpe),
        best_lb=best_lb, best_rf=best_rf, best_n=best_n,
        best_row=best_row,
        n_assets=n_assets, n_days=n_days,
        total_combos=total_combos, valid_combos=len(df_res),
        wf_results=wf_results, wf_n_pos=wf_n_pos, mean_oos=mean_oos,
        sh_best_h1=sh_best_h1, sh_best_h2=sh_best_h2,
        sh_mean_h1=sh_mean_h1, sh_mean_h2=sh_mean_h2,
        corr_h012=corr_h012, max_abs_corr=max_abs_corr,
        validation={
            "is_pass":   bool(is_pass),
            "wf_pass":   bool(wf_pass),
            "sh_pass":   bool(sh_pass),
            "corr_pass": bool(corr_pass),
        },
    )


def _write_results(**kw):
    result_json = {
        "hypothesis":      "H-213",
        "name":            "Intrabar Momentum Consistency (CLV Persistence)",
        "status":          kw["status"],
        "reason":          kw["reason"],
        "is_positive_rate": round(kw["pct_positive"], 1),
        "is_mean_sharpe":  round(float(kw["mean_sharpe"]), 3),
        "is_median_sharpe": round(kw["median_sharpe"], 3),
        "best_params": {
            "lookback": kw["best_lb"],
            "rebal":    kw["best_rf"],
            "n":        kw["best_n"],
        },
        "best_sharpe":        round(float(kw["best_row"]["sharpe"]), 3),
        "best_annual_return": round(float(kw["best_row"]["annual"]), 1),
        "best_max_dd":        round(float(kw["best_row"]["dd"]), 1),
        "wf_folds": [
            {
                "fold":       r["fold"],
                "is_params":  r["is_params"],
                "is_sharpe":  r["is_sharpe"],
                "oos_sharpe": r["oos_sharpe"],
                "oos_start":  r["oos_start"],
                "oos_end":    r["oos_end"],
            }
            for r in kw["wf_results"]
        ],
        "wf_positive_folds": kw["wf_n_pos"],
        "wf_total_folds":    len(kw["wf_results"]) if kw["wf_results"] else None,
        "wf_mean_oos_sharpe": (
            round(kw["mean_oos"], 3)
            if kw["mean_oos"] is not None and not np.isnan(kw["mean_oos"])
            else None
        ),
        "split_half": (
            {
                "h1_best_sharpe": kw["sh_best_h1"],
                "h2_best_sharpe": kw["sh_best_h2"],
                "h1_mean_sharpe": kw["sh_mean_h1"],
                "h2_mean_sharpe": kw["sh_mean_h2"],
            }
            if kw["sh_best_h1"] is not None
            else None
        ),
        "correlations": (
            {"H-012_momentum": kw["corr_h012"]}
            if kw["corr_h012"] is not None
            else None
        ),
        "max_abs_correlation": (
            round(kw["max_abs_corr"], 3)
            if kw["max_abs_corr"] is not None
            else None
        ),
        "n_assets":     kw["n_assets"],
        "n_days":       kw["n_days"],
        "total_combos": kw["total_combos"],
        "valid_combos": kw["valid_combos"],
        "validation":   kw["validation"],
    }
    results_path = Path(__file__).parent / "results.json"
    with open(results_path, "w") as f:
        json.dump(result_json, f, indent=2)
    print(f"\nResults written to {results_path}")


if __name__ == "__main__":
    main()
