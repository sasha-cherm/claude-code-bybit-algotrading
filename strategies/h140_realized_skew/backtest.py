"""
H-140: Realized Skewness Factor (Contrarian)

Theory: Assets with high positive realized skewness (fat right tail) attract
lottery-seeking traders who bid them up, causing overpricing. Negative-skew
assets are underpriced (avoided due to crash risk). Strategy:
  - SHORT the highest-skewness assets (top N)
  - LONG the lowest-skewness assets (bottom N, most negative / symmetric)
Market-neutral, equal-weight, rebalanced every R days.

Universe: 14 crypto perps (BTC, ETH, SOL, SUI, XRP, DOGE, AVAX, LINK,
          ADA, DOT, NEAR, OP, ARB, ATOM)
Data: ~2 years daily OHLCV from cached parquet files.

Parameter grid (36 combos):
  Lookback:   [20, 30, 40, 60]  (skewness window in days)
  Rebalance:  [3, 5, 7]         (days between rebalances)
  N:          [3, 4, 5]         (positions per side)

Validation:
  1. % of params with positive IS Sharpe (want >= 80%)
  2. Walk-forward: 6 folds (120d IS / 90d OOS). Want >= 4/6 positive, mean > 0.5
  3. Split-half: both halves positive Sharpe
  4. Correlation with H-012 (60d momentum) < 0.4

Fee: 0.06% per side (0.12% round-trip, Bybit taker on perps).
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_PER_SIDE = 0.0006       # 0.06% per side (6 bps)
INITIAL_CAPITAL = 10_000.0

# Parameter grid: 4 x 3 x 3 = 36 combos
LOOKBACKS   = [20, 30, 40, 60]
REBAL_FREQS = [3, 5, 7]
N_SIZES     = [3, 4, 5]

# Walk-forward config
WF_FOLDS    = 6
WF_IS_DAYS  = 120
WF_OOS_DAYS = 90


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_daily_data():
    """Load cached daily parquet files for all assets."""
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
            else:
                print(f"  {sym}: only {len(df)} bars, skipping")
        else:
            print(f"  {sym}: no data file found")
    return daily


def build_close_matrix(daily: dict) -> pd.DataFrame:
    """Build aligned close price matrix from daily data dict."""
    frames = {}
    for sym, df in daily.items():
        frames[sym] = df["close"]
    closes = pd.DataFrame(frames).sort_index()
    # Drop rows where more than 2 assets have NaN
    closes = closes.dropna(thresh=len(closes.columns) - 2)
    closes = closes.ffill()
    closes = closes.dropna()
    return closes


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(equity_series: pd.Series) -> dict:
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99.0, "annual_ret": 0.0, "max_dd": 1.0, "win_rate": 0.0}
    rets = eq.pct_change().dropna()
    n_pos = int((rets > 0).sum())
    n_total = len(rets)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(365)) if rets.std() > 1e-12 else 0.0
    return {
        "sharpe":     round(sharpe, 4),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd":     round(max_drawdown(eq), 4),
        "win_rate":   round(n_pos / n_total, 4) if n_total > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Core backtest engine
# ---------------------------------------------------------------------------

def compute_skewness_signal(closes: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    Compute rolling realized skewness of daily log returns.
    Uses scipy unbiased skewness (Fisher definition).
    """
    log_rets = np.log(closes / closes.shift(1))
    skew_signal = log_rets.rolling(lookback, min_periods=lookback).apply(
        lambda x: float(sp_stats.skew(x, bias=False)), raw=True
    )
    return skew_signal


def run_skew_factor(
    closes: pd.DataFrame,
    skew_signal: pd.DataFrame,
    rebal_freq: int,
    n_long: int,
    n_short: int = None,
    warmup: int = None,
    fee_per_side: float = FEE_PER_SIDE,
) -> dict:
    """
    Cross-sectional realized skewness factor (contrarian).

    LONG bottom N (lowest skewness = most negative / symmetric)
    SHORT top N (highest skewness = most positively skewed)

    Uses t-1 signal to avoid look-ahead bias.
    """
    if n_short is None:
        n_short = n_long
    if warmup is None:
        warmup = max(LOOKBACKS) + 5

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
        log_ret_i = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            # Use signal at t-1 (no look-ahead)
            skews = skew_signal.iloc[i - 1]
            valid = skews.dropna()

            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_ret_i).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # Sort ascending: lowest skew = LONG, highest skew = SHORT
            ranked = valid.sort_values(ascending=True)
            longs = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            # Turnover and fee
            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2.0
            # fee_per_side applies to both entry and exit of changed positions
            fee_drag = turnover * fee_per_side * 2  # both sides

            port_ret = (new_weights * log_ret_i).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count += 1
            prev_weights = new_weights
        else:
            port_ret = (prev_weights * log_ret_i).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"] = eq_series
    return metrics


# ---------------------------------------------------------------------------
# 1. Full parameter scan
# ---------------------------------------------------------------------------

def run_full_scan(closes: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-140: REALIZED SKEWNESS FACTOR -- Full Parameter Scan (In-Sample)")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_PER_SIDE * 10000:.0f} bps per side ({FEE_PER_SIDE*2*10000:.0f} bps round-trip)")
    print(f"  Direction: Contrarian (long low-skew, short high-skew)")

    # Pre-compute skewness signals for all lookbacks
    print("\n  Pre-computing skewness signals...")
    skew_cache = {}
    for lb in LOOKBACKS:
        print(f"    Lookback {lb}...", end=" ", flush=True)
        skew_cache[lb] = compute_skewness_signal(closes, lb)
        valid_count = skew_cache[lb].notna().sum().sum()
        print(f"done ({valid_count} valid values)")

    results = []
    total_combos = len(LOOKBACKS) * len(REBAL_FREQS) * len(N_SIZES)
    print(f"\n  Running {total_combos} parameter combinations...")

    for lb, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = lb + 5
        res = run_skew_factor(closes, skew_cache[lb], rebal, n_long, warmup=warmup)
        tag = f"LB{lb}_R{rebal}_N{n_long}"
        results.append({
            "tag": tag,
            "lookback": lb,
            "rebal": rebal,
            "n_long": n_long,
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
            "n_rebalances": res["n_rebalances"],
        })

    df = pd.DataFrame(results)
    pos_count = (df["sharpe"] > 0).sum()
    pos_pct = pos_count / len(df)

    print(f"\n  Results ({len(df)} combos):")
    print(f"    Positive Sharpe: {pos_count}/{len(df)} ({pos_pct:.0%})")
    print(f"    Mean Sharpe:   {df['sharpe'].mean():.3f}")
    print(f"    Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"    Best Sharpe:   {df['sharpe'].max():.3f}")
    print(f"    Worst Sharpe:  {df['sharpe'].min():.3f}")
    print(f"    Mean Ann Ret:  {df['annual_ret'].mean():.1%}")
    print(f"    Mean Max DD:   {df['max_dd'].mean():.1%}")

    print(f"\n  Top 10 params by Sharpe:")
    for _, row in df.nlargest(10, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}, Trades {row['n_trades']}")

    print(f"\n  Bottom 5 params by Sharpe:")
    for _, row in df.nsmallest(5, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    print(f"\n  By lookback:")
    for lb in LOOKBACKS:
        sub = df[df["lookback"] == lb]
        p = (sub["sharpe"] > 0).sum()
        print(f"    LB{lb}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"positive {p}/{len(sub)} ({p/len(sub):.0%})")

    print(f"\n  By rebalance freq:")
    for rb in REBAL_FREQS:
        sub = df[df["rebal"] == rb]
        p = (sub["sharpe"] > 0).sum()
        print(f"    R{rb}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"positive {p}/{len(sub)} ({p/len(sub):.0%})")

    print(f"\n  By N positions:")
    for ns in N_SIZES:
        sub = df[df["n_long"] == ns]
        p = (sub["sharpe"] > 0).sum()
        print(f"    N{ns}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"positive {p}/{len(sub)} ({p/len(sub):.0%})")

    return df, skew_cache


# ---------------------------------------------------------------------------
# 2. Walk-forward validation (6 folds, 120d IS / 90d OOS)
# ---------------------------------------------------------------------------

def run_walk_forward(closes: pd.DataFrame, skew_cache: dict):
    """
    Walk-forward with 6 folds:
    - 120 days in-sample to select best params
    - 90 days out-of-sample to test
    - Folds are rolled from the end backwards
    """
    print(f"\n" + "=" * 72)
    print("WALK-FORWARD VALIDATION")
    print("=" * 72)
    print(f"  Config: {WF_FOLDS} folds, {WF_IS_DAYS}d IS, {WF_OOS_DAYS}d OOS")

    n = len(closes)
    fold_size = WF_IS_DAYS + WF_OOS_DAYS  # 210 days per fold
    fold_results = []

    for fold in range(WF_FOLDS):
        # Fold layout: from end backwards
        oos_end_idx = n - fold * WF_OOS_DAYS
        oos_start_idx = oos_end_idx - WF_OOS_DAYS
        is_start_idx = oos_start_idx - WF_IS_DAYS

        if is_start_idx < 0 or oos_start_idx <= 0 or oos_end_idx <= oos_start_idx:
            print(f"    Fold {fold+1}: SKIPPED (insufficient data)")
            break

        is_closes = closes.iloc[is_start_idx:oos_start_idx]
        oos_closes = closes.iloc[oos_start_idx:oos_end_idx]

        if len(is_closes) < 60 or len(oos_closes) < 30:
            print(f"    Fold {fold+1}: SKIPPED (too few bars)")
            break

        # In-sample: find best params
        best_is_sharpe = -999.0
        best_params = None

        for lb, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
            warmup = lb + 5
            if warmup >= len(is_closes) - 20:
                continue
            is_skew = compute_skewness_signal(is_closes, lb)
            res = run_skew_factor(is_closes, is_skew, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_is_sharpe:
                best_is_sharpe = res["sharpe"]
                best_params = (lb, rebal, n_long)

        if best_params is None:
            print(f"    Fold {fold+1}: SKIPPED (no valid IS params)")
            break

        bp_lb, bp_rb, bp_n = best_params

        # Out-of-sample: test with IS-best params
        oos_skew = compute_skewness_signal(oos_closes, bp_lb)
        oos_warmup = min(bp_lb + 5, len(oos_closes) // 2)
        res_oos = run_skew_factor(oos_closes, oos_skew, bp_rb, bp_n, warmup=oos_warmup)

        fold_results.append({
            "fold": fold + 1,
            "oos_start": oos_closes.index[0].strftime("%Y-%m-%d"),
            "oos_end": oos_closes.index[-1].strftime("%Y-%m-%d"),
            "is_days": len(is_closes),
            "oos_days": len(oos_closes),
            "is_best_params": f"LB{bp_lb}_R{bp_rb}_N{bp_n}",
            "is_sharpe": round(best_is_sharpe, 3),
            "oos_sharpe": res_oos["sharpe"],
            "oos_ann_ret": res_oos["annual_ret"],
            "oos_max_dd": res_oos["max_dd"],
            "oos_win_rate": res_oos["win_rate"],
            "oos_trades": res_oos["n_trades"],
        })
        print(f"    Fold {fold+1}: OOS {oos_closes.index[0].date()} -> {oos_closes.index[-1].date()} "
              f"({len(oos_closes)}d) | IS best: LB{bp_lb}_R{bp_rb}_N{bp_n} "
              f"(IS Sharpe={best_is_sharpe:.3f}) | OOS: Sharpe={res_oos['sharpe']:.3f}, "
              f"Ann={res_oos['annual_ret']:.1%}, DD={res_oos['max_dd']:.1%}")

    if not fold_results:
        print("  No valid folds!")
        return None

    df_wf = pd.DataFrame(fold_results)
    pos = (df_wf["oos_sharpe"] > 0).sum()
    mean_oos = df_wf["oos_sharpe"].mean()

    print(f"\n  Walk-Forward Summary:")
    print(f"    Positive OOS folds: {pos}/{len(df_wf)} (target: >= 4/6)")
    print(f"    Mean OOS Sharpe:    {mean_oos:.3f} (target: > 0.5)")
    print(f"    Mean OOS Ann Ret:   {df_wf['oos_ann_ret'].mean():.1%}")
    print(f"    Mean OOS Max DD:    {df_wf['oos_max_dd'].mean():.1%}")
    print(f"    Total OOS days:     {df_wf['oos_days'].sum()}")

    return df_wf


# ---------------------------------------------------------------------------
# 3. Split-half validation
# ---------------------------------------------------------------------------

def run_split_half(closes: pd.DataFrame):
    print(f"\n" + "=" * 72)
    print("SPLIT-HALF VALIDATION")
    print("=" * 72)

    n = len(closes)
    mid = n // 2
    half1 = closes.iloc[:mid]
    half2 = closes.iloc[mid:]

    print(f"  Half 1: {half1.index[0].date()} to {half1.index[-1].date()} ({len(half1)} days)")
    print(f"  Half 2: {half2.index[0].date()} to {half2.index[-1].date()} ({len(half2)} days)")

    h1_sharpes = []
    h2_sharpes = []
    tags = []

    for lb, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = lb + 5
        skew1 = compute_skewness_signal(half1, lb)
        skew2 = compute_skewness_signal(half2, lb)
        r1 = run_skew_factor(half1, skew1, rebal, n_long, warmup=warmup)
        r2 = run_skew_factor(half2, skew2, rebal, n_long, warmup=warmup)
        h1_sharpes.append(r1["sharpe"])
        h2_sharpes.append(r2["sharpe"])
        tags.append(f"LB{lb}_R{rebal}_N{n_long}")

    h1 = np.array(h1_sharpes)
    h2 = np.array(h2_sharpes)

    corr = float(np.corrcoef(h1, h2)[0, 1]) if np.std(h1) > 0 and np.std(h2) > 0 else 0.0
    from scipy.stats import spearmanr
    spearman_corr, _ = spearmanr(h1, h2)
    both_pos = int(((h1 > 0) & (h2 > 0)).sum())

    print(f"\n  Results ({len(h1)} param combos):")
    print(f"    Pearson corr (Sharpe, H1 vs H2):  {corr:.3f}")
    print(f"    Spearman corr (Sharpe, H1 vs H2): {spearman_corr:.3f}")
    print(f"    Both halves positive: {both_pos}/{len(h1)} ({both_pos/len(h1):.0%})")
    print(f"    Half 1 mean Sharpe: {h1.mean():.3f}")
    print(f"    Half 2 mean Sharpe: {h2.mean():.3f}")

    # Show most consistent params
    df_sh = pd.DataFrame({"tag": tags, "h1": h1, "h2": h2})
    consistent = df_sh[(df_sh["h1"] > 0) & (df_sh["h2"] > 0)].copy()
    if len(consistent) > 0:
        consistent["min_sh"] = consistent[["h1", "h2"]].min(axis=1)
        print(f"\n  Most consistent (both positive, sorted by min Sharpe):")
        for _, row in consistent.nlargest(5, "min_sh").iterrows():
            print(f"    {row['tag']}: H1={row['h1']:.3f}, H2={row['h2']:.3f}")
    else:
        print(f"\n  No params positive in both halves.")

    # Check for signal inversion
    if (h1.mean() > 0.2 and h2.mean() < -0.2) or \
       (h1.mean() < -0.2 and h2.mean() > 0.2):
        print("  WARNING: Signal inversion between halves!")

    return {
        "pearson_corr": round(corr, 3),
        "spearman_corr": round(float(spearman_corr), 3),
        "both_positive_count": both_pos,
        "both_positive_pct": round(both_pos / len(h1), 3),
        "half1_mean_sharpe": round(float(h1.mean()), 3),
        "half2_mean_sharpe": round(float(h2.mean()), 3),
    }


# ---------------------------------------------------------------------------
# 4. Correlation with H-012 (60d momentum factor)
# ---------------------------------------------------------------------------

def compute_h012_correlation(closes: pd.DataFrame, best_lb: int, best_rb: int,
                             best_n: int):
    print(f"\n" + "=" * 72)
    print("CORRELATION WITH H-012 (60d Cross-Sectional Momentum)")
    print("=" * 72)

    # H-140: realized skewness factor with best params
    skew_sig = compute_skewness_signal(closes, best_lb)
    res_h140 = run_skew_factor(closes, skew_sig, best_rb, best_n,
                               warmup=best_lb + 5)
    eq_h140 = res_h140["equity"]

    # H-012: 60d momentum, long top 4, short bottom 4, rebalance 5d
    mom_lb = 60
    mom_rebal = 5
    mom_n = 4
    mom_warmup = 65

    mom_signal = closes.pct_change(mom_lb)
    n = len(closes)
    eq_mom = np.zeros(n)
    eq_mom[0] = INITIAL_CAPITAL
    pw = pd.Series(0.0, index=closes.columns)

    for i in range(1, n):
        log_ret_i = np.log(closes.iloc[i] / closes.iloc[i - 1])
        if i >= mom_warmup and (i - mom_warmup) % mom_rebal == 0:
            ranks = mom_signal.iloc[i - 1].dropna()
            if len(ranks) < mom_n * 2:
                eq_mom[i] = eq_mom[i - 1] * np.exp((pw * log_ret_i).sum())
                continue
            ranked = ranks.sort_values(ascending=False)
            new_w = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:mom_n]:
                new_w[s] = 1.0 / mom_n
            for s in ranked.index[-mom_n:]:
                new_w[s] = -1.0 / mom_n
            wc = (new_w - pw).abs()
            fee = wc.sum() / 2.0 * FEE_PER_SIDE * 2
            eq_mom[i] = eq_mom[i - 1] * np.exp((new_w * log_ret_i).sum() - fee)
            pw = new_w
        else:
            eq_mom[i] = eq_mom[i - 1] * np.exp((pw * log_ret_i).sum())

    eq_mom_series = pd.Series(eq_mom, index=closes.index)

    # Compute daily return correlation
    rets_h140 = eq_h140.pct_change().dropna()
    rets_h012 = eq_mom_series.pct_change().dropna()

    aligned = pd.DataFrame({"h140": rets_h140, "h012": rets_h012}).dropna()
    if len(aligned) < 50:
        print("  Insufficient overlapping data for correlation")
        return {"corr_h012": 0.0, "aligned_days": len(aligned)}

    corr = float(aligned["h140"].corr(aligned["h012"]))

    # Also compute H-012 metrics for reference
    met_mom = compute_metrics(eq_mom_series)

    print(f"  H-140 (Skew): Sharpe={res_h140['sharpe']:.3f}, Ann={res_h140['annual_ret']:.1%}")
    print(f"  H-012 (Mom):  Sharpe={met_mom['sharpe']:.3f}, Ann={met_mom['annual_ret']:.1%}")
    print(f"  Daily return correlation: {corr:.3f}")
    print(f"  Aligned days: {len(aligned)}")

    if abs(corr) < 0.2:
        print(f"  --> EXCELLENT: Very low correlation, strong diversifier")
    elif abs(corr) < 0.4:
        print(f"  --> PASS: Low enough correlation (target < 0.4)")
    else:
        print(f"  --> FAIL: Correlation too high (target < 0.4)")

    return {
        "corr_h012": round(corr, 4),
        "aligned_days": len(aligned),
        "h012_sharpe": met_mom["sharpe"],
        "h012_annual_ret": met_mom["annual_ret"],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 72)
    print("H-140: REALIZED SKEWNESS FACTOR (CONTRARIAN) BACKTEST")
    print("=" * 72)

    # 1. Load data
    print("\n[1/5] Loading daily data...")
    daily = load_daily_data()
    if len(daily) < 10:
        print(f"ERROR: Only {len(daily)} assets loaded, need at least 10. Aborting.")
        return

    closes = build_close_matrix(daily)
    n_years = len(closes) / 365.0
    print(f"\n  Close matrix: {len(closes)} days x {len(closes.columns)} assets")
    print(f"  Date range:   {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Coverage:     {n_years:.1f} years")

    if n_years < 1.5:
        print("WARNING: Less than 1.5 years of data.")

    # 2. Full parameter scan (in-sample)
    print("\n[2/5] Full Parameter Scan...")
    scan_df, skew_cache = run_full_scan(closes)

    pos_pct = float((scan_df["sharpe"] > 0).mean())
    mean_sharpe = float(scan_df["sharpe"].mean())
    best_row = scan_df.loc[scan_df["sharpe"].idxmax()]
    best_lb = int(best_row["lookback"])
    best_rb = int(best_row["rebal"])
    best_n = int(best_row["n_long"])
    best_sharpe = float(best_row["sharpe"])

    print(f"\n  Best params: LB{best_lb}_R{best_rb}_N{best_n} (Sharpe={best_sharpe:.3f})")

    # 3. Walk-forward validation
    print("\n[3/5] Walk-Forward Validation...")
    wf_df = run_walk_forward(closes, skew_cache)

    # 4. Split-half validation
    print("\n[4/5] Split-Half Validation...")
    sh_result = run_split_half(closes)

    # 5. H-012 correlation
    print("\n[5/5] H-012 Correlation...")
    corr_result = compute_h012_correlation(closes, best_lb, best_rb, best_n)

    # -----------------------------------------------------------------------
    # FINAL SUMMARY
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("H-140 FINAL SUMMARY")
    print("=" * 72)

    # Test 1: Param robustness
    print(f"\n  TEST 1 - Parameter Robustness:")
    print(f"    % positive IS Sharpe: {pos_pct:.0%} (target >= 80%)")
    print(f"    Mean IS Sharpe:       {mean_sharpe:.3f}")
    test1_pass = pos_pct >= 0.80
    print(f"    Result: {'PASS' if test1_pass else 'FAIL'}")

    # Test 2: Walk-forward
    wf_pos = 0
    wf_mean = -99.0
    if wf_df is not None and len(wf_df) > 0:
        wf_pos = int((wf_df["oos_sharpe"] > 0).sum())
        wf_mean = float(wf_df["oos_sharpe"].mean())
    print(f"\n  TEST 2 - Walk-Forward OOS:")
    print(f"    Positive OOS folds: {wf_pos}/{WF_FOLDS} (target >= 4/6)")
    print(f"    Mean OOS Sharpe:    {wf_mean:.3f} (target > 0.5)")
    test2_pass = wf_pos >= 4 and wf_mean > 0.5
    print(f"    Result: {'PASS' if test2_pass else 'FAIL'}")

    # Test 3: Split-half
    h1_pos = sh_result["half1_mean_sharpe"] > 0
    h2_pos = sh_result["half2_mean_sharpe"] > 0
    both_pos = h1_pos and h2_pos
    print(f"\n  TEST 3 - Split-Half:")
    print(f"    Half 1 mean Sharpe: {sh_result['half1_mean_sharpe']:.3f} ({'positive' if h1_pos else 'negative'})")
    print(f"    Half 2 mean Sharpe: {sh_result['half2_mean_sharpe']:.3f} ({'positive' if h2_pos else 'negative'})")
    print(f"    Both halves positive: {'YES' if both_pos else 'NO'}")
    test3_pass = both_pos
    print(f"    Result: {'PASS' if test3_pass else 'FAIL'}")

    # Test 4: H-012 correlation
    h012_corr = corr_result["corr_h012"]
    print(f"\n  TEST 4 - H-012 Correlation:")
    print(f"    Correlation: {h012_corr:.3f} (target < 0.4)")
    test4_pass = abs(h012_corr) < 0.4
    print(f"    Result: {'PASS' if test4_pass else 'FAIL'}")

    # Overall verdict
    all_pass = test1_pass and test2_pass and test3_pass and test4_pass
    tests_passed = sum([test1_pass, test2_pass, test3_pass, test4_pass])

    print(f"\n  OVERALL: {tests_passed}/4 tests passed")

    reasons = []
    if not test1_pass:
        reasons.append(f"Param robustness {pos_pct:.0%} < 80%")
    if not test2_pass:
        reasons.append(f"WF: {wf_pos}/6 positive folds, mean OOS Sharpe {wf_mean:.3f}")
    if not test3_pass:
        reasons.append(f"Split-half: H1={sh_result['half1_mean_sharpe']:.3f}, H2={sh_result['half2_mean_sharpe']:.3f}")
    if not test4_pass:
        reasons.append(f"H-012 correlation {h012_corr:.3f} >= 0.4")

    if all_pass:
        verdict = "CONFIRMED"
        print(f"\n  VERDICT: CONFIRMED -- all 4 validation tests passed")
    else:
        verdict = "REJECTED"
        print(f"\n  VERDICT: REJECTED")
        for r in reasons:
            print(f"    - {r}")

    # -----------------------------------------------------------------------
    # Save results
    # -----------------------------------------------------------------------
    out_path = Path(__file__).parent / "results.json"

    wf_summary = {}
    if wf_df is not None and len(wf_df) > 0:
        wf_summary = {
            "n_folds": len(wf_df),
            "positive_folds": wf_pos,
            "mean_oos_sharpe": round(wf_mean, 3),
            "mean_oos_ann_ret": round(float(wf_df["oos_ann_ret"].mean()), 4),
            "mean_oos_max_dd": round(float(wf_df["oos_max_dd"].mean()), 4),
            "total_oos_days": int(wf_df["oos_days"].sum()),
            "fold_details": wf_df.to_dict("records"),
        }
    else:
        wf_summary = {"n_folds": 0, "positive_folds": 0, "mean_oos_sharpe": -99.0}

    results_dict = {
        "hypothesis": "H-140",
        "title": "Realized Skewness Factor (Contrarian)",
        "verdict": verdict,
        "tests_passed": f"{tests_passed}/4",
        "date_run": str(pd.Timestamp.now().date()),
        "data_period": {
            "start": str(closes.index[0].date()),
            "end": str(closes.index[-1].date()),
            "days": len(closes),
            "years": round(n_years, 2),
            "assets": list(closes.columns),
            "n_assets": len(closes.columns),
        },
        "in_sample": {
            "n_combos": len(scan_df),
            "positive_pct": round(pos_pct, 4),
            "mean_sharpe": round(mean_sharpe, 4),
            "median_sharpe": round(float(scan_df["sharpe"].median()), 4),
            "best_sharpe": round(best_sharpe, 4),
            "best_params": f"LB{best_lb}_R{best_rb}_N{best_n}",
            "best_annual_ret": round(float(best_row["annual_ret"]), 4),
            "best_max_dd": round(float(best_row["max_dd"]), 4),
            "best_win_rate": round(float(best_row["win_rate"]), 4),
        },
        "walk_forward": wf_summary,
        "split_half": sh_result,
        "h012_correlation": corr_result,
        "validation_tests": {
            "test1_param_robustness": {
                "pass": test1_pass,
                "positive_pct": round(pos_pct, 4),
                "threshold": 0.80,
            },
            "test2_walk_forward": {
                "pass": test2_pass,
                "positive_folds": wf_pos,
                "mean_oos_sharpe": round(wf_mean, 3),
                "threshold_folds": 4,
                "threshold_sharpe": 0.5,
            },
            "test3_split_half": {
                "pass": test3_pass,
                "half1_mean_sharpe": sh_result["half1_mean_sharpe"],
                "half2_mean_sharpe": sh_result["half2_mean_sharpe"],
            },
            "test4_h012_corr": {
                "pass": test4_pass,
                "correlation": round(h012_corr, 4),
                "threshold": 0.4,
            },
        },
        "rejection_reasons": reasons,
    }

    with open(out_path, "w") as f:
        json.dump(results_dict, f, indent=2)
    print(f"\n  Results saved to {out_path}")
    print("=" * 72)

    return results_dict


if __name__ == "__main__":
    main()
