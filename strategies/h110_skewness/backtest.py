"""
H-110: Return Skewness Factor (Cross-Sectional)

Academic finance: positively-skewed assets are overpriced (lottery preference)
and negatively-skewed assets are underpriced. Strategy:
  - Long the most negatively-skewed assets (lowest rolling skewness)
  - Short the most positively-skewed assets (highest rolling skewness)
Market-neutral, equal-weight, rebalanced periodically.

Parameter grid (48 combos):
  Skewness lookback: [20, 30, 40, 60]
  Rebalance frequency: [3, 5, 7, 10] days
  N long/short: [3, 4, 5]

Validation:
  1. In-sample: full period Sharpe for all 48 combos
  2. Parameter robustness: % positive Sharpe (target >80%)
  3. Walk-forward OOS: 6-fold rolling WF (60% train / 40% test, rolling)
  4. Split-half stability: Sharpe correlation between halves
  5. Correlation with H-012 momentum (60d, 5d rebal, top/bottom 4)
  6. Fee sensitivity: 0.1% round-trip (Bybit taker)

Fee: 0.10% round-trip (10 bps) — Bybit taker
Sharpe: daily mean / daily std * sqrt(365)
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE       = 0.001       # 0.10% round-trip (Bybit taker)
INITIAL_CAPITAL = 10_000.0

# Parameter grid
SKEW_LOOKBACKS = [20, 30, 40, 60]   # rolling skewness window (days)
REBAL_FREQS    = [3, 5, 7, 10]      # rebalance every N days
N_SIZES        = [3, 4, 5]          # top/bottom N
# 4 x 4 x 3 = 48 combos

# Walk-forward (6 folds, rolling 60/40 split)
WF_FOLDS = 6


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

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
            else:
                print(f"  {sym}: only {len(df)} bars, skipping")
        else:
            print(f"  {sym}: no data found")
    return daily


def build_closes_matrix(daily: dict) -> pd.DataFrame:
    frames = {}
    for sym, df in daily.items():
        frames[sym] = df["close"]
    closes = pd.DataFrame(frames)
    closes = closes.sort_index()
    # Drop rows where more than 2 assets have NaN
    closes = closes.dropna(thresh=len(closes.columns) - 2)
    # Forward-fill remaining NaNs (assets with shorter history)
    closes = closes.ffill()
    closes = closes.dropna()
    return closes


# ---------------------------------------------------------------------------
# Metrics helper
# ---------------------------------------------------------------------------

def compute_metrics(equity_series: pd.Series) -> dict:
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99.0, "annual_ret": 0.0, "max_dd": 1.0, "win_rate": 0.0}
    rets = eq.pct_change().dropna()
    n_pos   = int((rets > 0).sum())
    n_total = len(rets)
    sharpe  = float(rets.mean() / rets.std() * np.sqrt(365)) if rets.std() > 1e-12 else 0.0
    return {
        "sharpe":     round(sharpe, 4),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd":     round(max_drawdown(eq), 4),
        "win_rate":   round(n_pos / n_total, 4) if n_total > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Core back-test engine — skewness factor
# ---------------------------------------------------------------------------

def run_skewness_factor(
    closes: pd.DataFrame,
    skew_lookback: int,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    warmup: int | None = None,
    fee_rate: float = FEE_RATE,
) -> dict:
    """
    Cross-sectional skewness strategy.

    Factor = rolling skewness of daily returns over skew_lookback days.
    Sorting ascending: lowest skewness (most negative) = LONG.
    Highest skewness (most positive) = SHORT.

    Theory: negatively-skewed assets are underpriced (no lottery appeal),
    positively-skewed assets are overpriced (lottery demand).
    """
    if n_short is None:
        n_short = n_long
    if warmup is None:
        warmup = skew_lookback + 5

    # Daily log returns
    log_rets = np.log(closes / closes.shift(1))
    # Rolling skewness (scipy stats.skew applied rolling)
    # Use pandas rolling with apply (min_periods = skew_lookback)
    skew_signal = log_rets.rolling(skew_lookback, min_periods=skew_lookback).apply(
        lambda x: float(stats.skew(x, bias=False)), raw=True
    )

    n          = len(closes)
    capital    = INITIAL_CAPITAL
    equity     = np.zeros(n)
    equity[0]  = capital

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count  = 0

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        lret_i = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            # Use signal at i-1 to avoid look-ahead
            skews = skew_signal.iloc[i - 1]
            valid = skews.dropna()
            if len(valid) < n_long + n_short:
                port_ret      = (prev_weights * lret_i).sum()
                equity[i]     = equity[i - 1] * np.exp(port_ret)
                continue

            # Sort ascending: lowest skewness = most negative = LONG
            ranked = valid.sort_values(ascending=True)
            longs  = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] =  1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover       = weight_changes.sum() / 2.0
            fee_drag       = turnover * fee_rate

            port_ret = (new_weights * lret_i).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count  += 1
            prev_weights  = new_weights
        else:
            port_ret = (prev_weights * lret_i).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"]     = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"]       = eq_series
    return metrics


# ---------------------------------------------------------------------------
# Full parameter scan (in-sample)
# ---------------------------------------------------------------------------

def run_full_scan(closes: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-110: RETURN SKEWNESS FACTOR -- Full Param Scan (In-Sample)")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per rebalance")
    print(f"  Direction: SKEWNESS (long neg-skew, short pos-skew)")

    results = []

    for skew_lb, rebal, n in product(SKEW_LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = skew_lb + 5
        res    = run_skewness_factor(closes, skew_lb, rebal, n, warmup=warmup)
        tag    = f"S{skew_lb}_R{rebal}_N{n}"
        results.append({
            "tag": tag, "skew_lookback": skew_lb, "rebal": rebal, "n": n,
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
            "win_rate":   res["win_rate"],
            "n_trades":   res["n_trades"],
            "n_rebalances": res["n_rebalances"],
        })

    df_r = pd.DataFrame(results)
    pos_pct = (df_r["sharpe"] > 0).mean()
    print(f"\n  Combos: {len(df_r)}, Positive Sharpe: {(df_r['sharpe']>0).sum()}/{len(df_r)} ({pos_pct:.0%})")
    print(f"  Mean Sharpe: {df_r['sharpe'].mean():.3f}, Median: {df_r['sharpe'].median():.3f}")
    print(f"  Best Sharpe: {df_r['sharpe'].max():.3f}, Worst: {df_r['sharpe'].min():.3f}")
    print(f"  Mean Ann Ret: {df_r['annual_ret'].mean():.1%}, Mean DD: {df_r['max_dd'].mean():.1%}")

    print(f"\n  Top 10 parameter combos:")
    for _, row in df_r.nlargest(10, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}, Rebals {row['n_rebalances']}")

    print(f"\n  By skewness lookback:")
    for lb in SKEW_LOOKBACKS:
        sub = df_r[df_r["skew_lookback"] == lb]
        print(f"    S{lb}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"positive {(sub['sharpe']>0).sum()}/{len(sub)} ({(sub['sharpe']>0).mean():.0%})")

    print(f"\n  By rebalance frequency:")
    for rb in REBAL_FREQS:
        sub = df_r[df_r["rebal"] == rb]
        print(f"    R{rb}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"positive {(sub['sharpe']>0).sum()}/{len(sub)} ({(sub['sharpe']>0).mean():.0%})")

    print(f"\n  By N positions:")
    for n_s in N_SIZES:
        sub = df_r[df_r["n"] == n_s]
        print(f"    N{n_s}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"positive {(sub['sharpe']>0).sum()}/{len(sub)} ({(sub['sharpe']>0).mean():.0%})")

    return df_r


# ---------------------------------------------------------------------------
# Walk-forward OOS: 6-fold rolling, 60% train / 40% test
# ---------------------------------------------------------------------------

def run_walk_forward(closes: pd.DataFrame):
    n      = len(closes)
    # Rolling 6-fold: fold 0 uses earliest window, fold 5 uses latest
    # test_size = 40% of fold_window, train_size = 60%
    # total data split into 6 equal windows of size n//6, but overlap
    # Implementation: rolling advance by test_size, 6 folds
    total_window = n
    # fold window: use all data. Train = 60%, test = 40%
    # Roll forward: step = test_size each fold
    train_frac = 0.60
    # We need 6 non-overlapping test windows that tile the data
    # Strategy: split data into 6 equal segments, use cumulative train
    fold_size = total_window // WF_FOLDS  # each fold test segment
    train_min = max(SKEW_LOOKBACKS) + 20  # minimum training data

    print(f"\n  Walk-Forward ({WF_FOLDS}-fold rolling, ~{int(train_frac*100)}% train / {int((1-train_frac)*100)}% test)")
    print(f"    Total days: {n}, Fold test size: ~{fold_size} days")

    fold_results = []

    for fold in range(WF_FOLDS):
        # Test window: the (fold+1)-th segment from the end (fold 0 = last)
        test_end   = n - fold * fold_size
        test_start = test_end - fold_size
        # Train: all data before test_start, but use at most 60%/40% fraction
        # Rolling walk-forward: train ends at test_start-1
        # Determine train_start to maintain 60/40 ratio within each fold window
        fold_window = test_end  # total data available up to test_end
        train_size  = int(fold_window * train_frac)
        train_start = test_start - train_size
        if train_start < 0:
            train_start = 0

        if test_start < 0 or test_end <= test_start:
            break
        if (test_start - train_start) < train_min:
            break

        train_c = closes.iloc[train_start:test_start]
        test_c  = closes.iloc[test_start:test_end]

        if len(test_c) < 20 or len(train_c) < train_min:
            break

        # Select best params on train
        best_s = -999.0
        best_p = None
        for skew_lb, rebal, n_long in product(SKEW_LOOKBACKS, REBAL_FREQS, N_SIZES):
            warmup = skew_lb + 5
            if warmup >= len(train_c) - 20:
                continue
            res = run_skewness_factor(train_c, skew_lb, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_s:
                best_s = res["sharpe"]
                best_p = (skew_lb, rebal, n_long)

        if best_p is None:
            break
        slb, rb, nl = best_p
        res_oos = run_skewness_factor(
            test_c, slb, rb, nl,
            warmup=min(slb + 5, len(test_c) // 2)
        )

        fold_results.append({
            "fold":        fold + 1,
            "test_start":  test_c.index[0].strftime("%Y-%m-%d"),
            "test_end":    test_c.index[-1].strftime("%Y-%m-%d"),
            "train_days":  len(train_c),
            "test_days":   len(test_c),
            "train_params": f"S{slb}_R{rb}_N{nl}",
            "train_sharpe": round(best_s, 3),
            "oos_sharpe":   res_oos["sharpe"],
            "oos_ann_ret":  res_oos["annual_ret"],
            "oos_max_dd":   res_oos["max_dd"],
        })
        print(f"    Fold {fold+1}: {test_c.index[0].date()} -> {test_c.index[-1].date()} "
              f"({len(test_c)}d) | IS best S{slb}_R{rb}_N{nl} (IS={best_s:.3f}) "
              f"| OOS Sharpe={res_oos['sharpe']:.3f}, Ann={res_oos['annual_ret']:.1%}")

    if not fold_results:
        print("  [WARNING] No valid folds computed!")
        return None

    df_wf = pd.DataFrame(fold_results)
    pos    = (df_wf["oos_sharpe"] > 0).sum()
    mean_oos = df_wf["oos_sharpe"].mean()
    print(f"\n    Summary: {pos}/{len(df_wf)} positive OOS folds, "
          f"Mean OOS Sharpe={mean_oos:.3f}, "
          f"Mean OOS Ann={df_wf['oos_ann_ret'].mean():.1%}")
    return df_wf


# ---------------------------------------------------------------------------
# Split-half stability
# ---------------------------------------------------------------------------

def run_split_half(closes: pd.DataFrame):
    n   = len(closes)
    mid = n // 2
    c1, c2 = closes.iloc[:mid], closes.iloc[mid:]

    print(f"\n  Split-Half Consistency")
    print(f"    Half1: {c1.index[0].date()} to {c1.index[-1].date()} ({len(c1)} days)")
    print(f"    Half2: {c2.index[0].date()} to {c2.index[-1].date()} ({len(c2)} days)")

    h1_sharpes, h2_sharpes, tags = [], [], []
    for skew_lb, rebal, n_long in product(SKEW_LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = skew_lb + 5
        r1 = run_skewness_factor(c1, skew_lb, rebal, n_long, warmup=warmup)
        r2 = run_skewness_factor(c2, skew_lb, rebal, n_long, warmup=warmup)
        h1_sharpes.append(r1["sharpe"])
        h2_sharpes.append(r2["sharpe"])
        tags.append(f"S{skew_lb}_R{rebal}_N{n_long}")

    h1 = np.array(h1_sharpes)
    h2 = np.array(h2_sharpes)
    corr      = float(np.corrcoef(h1, h2)[0, 1])
    both_pos  = int(((h1 > 0) & (h2 > 0)).sum())

    print(f"    Sharpe correlation between halves: {corr:.3f}")
    print(f"    Positive in both halves: {both_pos}/{len(h1)} ({both_pos/len(h1):.0%})")
    print(f"    Half1 mean Sharpe: {h1.mean():.3f}, Half2 mean Sharpe: {h2.mean():.3f}")

    df_sh = pd.DataFrame({"tag": tags, "h1": h1, "h2": h2})
    consistent = df_sh[(df_sh["h1"] > 0) & (df_sh["h2"] > 0)].copy()
    if len(consistent) > 0:
        consistent["min_sh"] = consistent[["h1", "h2"]].min(axis=1)
        print(f"    Most consistent params (both positive):")
        for _, row in consistent.nlargest(5, "min_sh").iterrows():
            print(f"      {row['tag']}: H1={row['h1']:.3f}, H2={row['h2']:.3f}")
    else:
        print(f"    No params positive in both halves.")

    return {
        "sharpe_correlation":  round(corr, 3),
        "both_positive_pct":   round(both_pos / len(h1), 3),
        "half1_mean_sharpe":   round(float(h1.mean()), 3),
        "half2_mean_sharpe":   round(float(h2.mean()), 3),
    }


# ---------------------------------------------------------------------------
# Fee sensitivity
# ---------------------------------------------------------------------------

def run_fee_sensitivity(closes: pd.DataFrame, best_slb: int, best_rb: int,
                        best_n: int):
    print(f"\n  Fee Sensitivity (best params: S{best_slb}_R{best_rb}_N{best_n})")
    fee_levels = [
        ("0x",    0.0),
        ("0.5x",  FEE_RATE * 0.5),
        ("1x",    FEE_RATE),            # 0.10% — Bybit taker
        ("2x",    FEE_RATE * 2.0),
        ("3x",    FEE_RATE * 3.0),
        ("5x",    FEE_RATE * 5.0),
    ]
    fee_results = {}
    for label, fee in fee_levels:
        res = run_skewness_factor(closes, best_slb, best_rb, best_n,
                                  warmup=best_slb + 5, fee_rate=fee)
        fee_results[label] = {"sharpe": res["sharpe"], "annual_ret": res["annual_ret"]}
        print(f"    Fee {label} ({fee*10000:.0f} bps): Sharpe {res['sharpe']:.3f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    return fee_results


# ---------------------------------------------------------------------------
# Correlation with H-012 momentum
# ---------------------------------------------------------------------------

def compute_factor_correlation(closes: pd.DataFrame,
                                best_slb: int, best_rb: int, best_n: int):
    print(f"\n  Factor Correlation with H-012 (60d momentum, R5, N4)")

    # H-110 returns
    res_h110  = run_skewness_factor(closes, best_slb, best_rb, best_n,
                                     warmup=best_slb + 5)
    eq_h110   = res_h110["equity"]
    rets_h110 = eq_h110.pct_change().dropna()

    # H-012: 60-day cross-sectional momentum, rebalance 5d, top/bottom 4
    def run_momentum(c_inner, mom_lb=60, rebal_f=5, n_l=4, wup=65):
        mom   = c_inner.pct_change(mom_lb)
        n_i   = len(c_inner)
        eq    = np.zeros(n_i)
        eq[0] = INITIAL_CAPITAL
        pw    = pd.Series(0.0, index=c_inner.columns)
        for i in range(1, n_i):
            lret_i = np.log(c_inner.iloc[i] / c_inner.iloc[i - 1])
            if i >= wup and (i - wup) % rebal_f == 0:
                ranks = mom.iloc[i - 1].dropna()
                if len(ranks) < n_l * 2:
                    eq[i] = eq[i - 1] * np.exp((pw * lret_i).sum())
                    continue
                ranked = ranks.sort_values(ascending=False)
                new_w  = pd.Series(0.0, index=c_inner.columns)
                for s in ranked.index[:n_l]:
                    new_w[s] =  1.0 / n_l
                for s in ranked.index[-n_l:]:
                    new_w[s] = -1.0 / n_l
                wc   = (new_w - pw).abs()
                fee  = wc.sum() / 2.0 * 0.0006    # H-012 uses 6bps
                eq[i] = eq[i - 1] * np.exp((new_w * lret_i).sum() - fee)
                pw = new_w
            else:
                eq[i] = eq[i - 1] * np.exp((pw * lret_i).sum())
        return pd.Series(eq, index=c_inner.index).pct_change().dropna()

    rets_h012 = run_momentum(closes)

    # Align and correlate
    aligned = pd.DataFrame({"h110": rets_h110, "h012": rets_h012}).dropna()
    corr_h012 = float(aligned["h110"].corr(aligned["h012"]))

    print(f"    H-110 vs H-012: correlation = {corr_h012:.3f}")
    if abs(corr_h012) > 0.5:
        print(f"    [REDUNDANT] |corr| > 0.5 — H-110 is redundant with H-012")
    else:
        print(f"    [INDEPENDENT] |corr| <= 0.5 — H-110 is independent of H-012")

    return {
        "corr_h012": round(corr_h012, 4),
        "aligned_days": len(aligned),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 72)
    print("H-110: RETURN SKEWNESS FACTOR BACKTEST")
    print("=" * 72)

    # 1. Load data
    print("\n[1] Loading data...")
    daily = load_daily_data()
    if len(daily) < 10:
        print(f"ERROR: Only {len(daily)} assets loaded, need at least 10. Aborting.")
        return

    closes = build_closes_matrix(daily)
    print(f"\n  Matrix: {len(closes)} days x {len(closes.columns)} assets")
    print(f"  Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    n_years = len(closes) / 365.0
    print(f"  Coverage: {n_years:.1f} years")

    if n_years < 1.5:
        print("WARNING: Less than 1.5 years of data. Backtest may be unreliable.")

    # 2. Full in-sample param scan
    print("\n[2] Full in-sample parameter scan...")
    df_scan = run_full_scan(closes)

    pos_pct      = float((df_scan["sharpe"] > 0).mean())
    mean_sharpe  = float(df_scan["sharpe"].mean())
    best_row     = df_scan.loc[df_scan["sharpe"].idxmax()]
    best_slb     = int(best_row["skew_lookback"])
    best_rb      = int(best_row["rebal"])
    best_n       = int(best_row["n"])
    best_sharpe  = float(best_row["sharpe"])

    print(f"\n  Selected best params: S{best_slb}_R{best_rb}_N{best_n} (IS Sharpe={best_sharpe:.3f})")

    # 3. Walk-forward OOS
    print("\n[3] Walk-forward OOS (6-fold rolling, 60/40)...")
    df_wf = run_walk_forward(closes)

    wf_summary = {}
    if df_wf is not None and len(df_wf) > 0:
        wf_summary = {
            "folds":            len(df_wf),
            "positive_folds":   int((df_wf["oos_sharpe"] > 0).sum()),
            "mean_oos_sharpe":  round(float(df_wf["oos_sharpe"].mean()), 3),
            "mean_oos_ann_ret": round(float(df_wf["oos_ann_ret"].mean()), 4),
            "fold_sharpes":     df_wf["oos_sharpe"].tolist(),
        }
    else:
        wf_summary = {"folds": 0, "positive_folds": 0, "mean_oos_sharpe": -99.0}

    # 4. Split-half stability
    print("\n[4] Split-half stability...")
    sh_result = run_split_half(closes)

    # 5. Factor correlation with H-012
    print("\n[5] Factor correlation analysis...")
    corr_result = compute_factor_correlation(closes, best_slb, best_rb, best_n)

    # 6. Fee sensitivity
    print("\n[6] Fee sensitivity analysis...")
    fee_result = run_fee_sensitivity(closes, best_slb, best_rb, best_n)

    # 7. Full-period best-param run for final metrics
    print(f"\n[7] Full-period best-param run: S{best_slb}_R{best_rb}_N{best_n}")
    res_best = run_skewness_factor(closes, best_slb, best_rb, best_n,
                                    warmup=best_slb + 5)
    print(f"    Sharpe={res_best['sharpe']:.3f}, Ann={res_best['annual_ret']:.1%}, "
          f"DD={res_best['max_dd']:.1%}, WinRate={res_best['win_rate']:.1%}, "
          f"Trades={res_best['n_trades']}, Rebals={res_best['n_rebalances']}")

    # Also run with 0.1% taker fee explicitly
    print(f"\n[8] Fee sensitivity at 0.1% round-trip (Bybit taker):")
    res_taker = run_skewness_factor(closes, best_slb, best_rb, best_n,
                                     warmup=best_slb + 5, fee_rate=0.001)
    print(f"    0.1% fee: Sharpe={res_taker['sharpe']:.3f}, "
          f"Ann={res_taker['annual_ret']:.1%}, DD={res_taker['max_dd']:.1%}")

    # ---------------------------------------------------------------------------
    # Verdict
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("VERDICT SUMMARY")
    print("=" * 72)
    print(f"  In-sample: {(df_scan['sharpe']>0).sum()}/{len(df_scan)} params positive ({pos_pct:.0%})")
    print(f"  IS mean Sharpe: {mean_sharpe:.3f}, IS best Sharpe: {best_sharpe:.3f}")
    print(f"  Walk-forward: {wf_summary.get('positive_folds',0)}/{wf_summary.get('folds',0)} folds positive, "
          f"mean OOS Sharpe={wf_summary.get('mean_oos_sharpe',-99):.3f}")
    print(f"  Split-half corr: {sh_result['sharpe_correlation']:.3f}, "
          f"both positive: {sh_result['both_positive_pct']:.0%}")
    print(f"  Corr with H-012 momentum: {corr_result['corr_h012']:.3f}")
    print(f"  Fee sensitivity (1x=0.1% taker): Sharpe={res_taker['sharpe']:.3f}, "
          f"Ann={res_taker['annual_ret']:.1%}")

    # Decision logic
    reasons_reject = []
    if pos_pct < 0.80:
        reasons_reject.append(f"Param robustness {pos_pct:.0%} < 80%")
    if sh_result["sharpe_correlation"] < 0.0:
        reasons_reject.append(f"Split-half corr {sh_result['sharpe_correlation']:.3f} < 0")
    if wf_summary.get("mean_oos_sharpe", -99) < 0.3:
        reasons_reject.append(f"WF mean OOS Sharpe {wf_summary.get('mean_oos_sharpe',-99):.3f} < 0.3")
    if abs(corr_result["corr_h012"]) > 0.5:
        reasons_reject.append(f"Corr with H-012 = {corr_result['corr_h012']:.3f} > 0.5 (redundant)")
    if res_taker["sharpe"] < 0.5:
        reasons_reject.append(f"Taker-fee Sharpe {res_taker['sharpe']:.3f} < 0.5")

    if reasons_reject:
        verdict = "REJECTED"
        print(f"\n  VERDICT: REJECTED")
        for r in reasons_reject:
            print(f"    - {r}")
    else:
        verdict = "CONFIRMED"
        print(f"\n  VERDICT: CONFIRMED — all criteria passed")

    # ---------------------------------------------------------------------------
    # Save results
    # ---------------------------------------------------------------------------
    out_dir = Path(__file__).parent
    results = {
        "hypothesis":    "H-110",
        "name":          "Return Skewness Factor",
        "verdict":       verdict,
        "date_run":      str(pd.Timestamp.now().date()),
        "data_period": {
            "start": str(closes.index[0].date()),
            "end":   str(closes.index[-1].date()),
            "days":  len(closes),
            "years": round(n_years, 2),
            "assets": list(closes.columns),
        },
        "in_sample": {
            "n_combos":           len(df_scan),
            "positive_pct":       round(pos_pct, 4),
            "mean_sharpe":        round(mean_sharpe, 4),
            "median_sharpe":      round(float(df_scan["sharpe"].median()), 4),
            "best_sharpe":        round(best_sharpe, 4),
            "best_params":        f"S{best_slb}_R{best_rb}_N{best_n}",
            "best_annual_ret":    round(float(best_row["annual_ret"]), 4),
            "best_max_dd":        round(float(best_row["max_dd"]), 4),
        },
        "walk_forward": wf_summary,
        "split_half":   sh_result,
        "factor_correlation": corr_result,
        "fee_sensitivity": {
            k: {"sharpe": v["sharpe"], "annual_ret": v["annual_ret"]}
            for k, v in fee_result.items()
        },
        "taker_fee_run": {
            "fee_rate":   0.001,
            "sharpe":     res_taker["sharpe"],
            "annual_ret": res_taker["annual_ret"],
            "max_dd":     res_taker["max_dd"],
        },
        "best_param_full_run": {
            "params":     f"S{best_slb}_R{best_rb}_N{best_n}",
            "sharpe":     res_best["sharpe"],
            "annual_ret": res_best["annual_ret"],
            "max_dd":     res_best["max_dd"],
            "win_rate":   res_best["win_rate"],
            "n_trades":   res_best["n_trades"],
            "n_rebalances": res_best["n_rebalances"],
        },
        "rejection_reasons": reasons_reject,
    }

    out_path = out_dir / "results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {out_path}")

    return results


if __name__ == "__main__":
    main()
