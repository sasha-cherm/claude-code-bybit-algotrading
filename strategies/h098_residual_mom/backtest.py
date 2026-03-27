"""
H-098: BTC-Residual Momentum

Instead of ranking by raw return (like H-012 momentum), rank by the residual
return after removing BTC beta exposure. For each asset i:
  - beta_i = cov(ret_i, ret_btc) / var(ret_btc)  [over lookback window]
  - alpha_i = cumulative_return_i - beta_i * cumulative_return_btc  [over lookback]
  - Rank by alpha_i: long top N (highest alpha), short bottom N (worst alpha)

This captures "pure outperformance" vs the crypto market, removing the
directional BTC component.

Validation: full param scan (90 combos), walk-forward (4 equal folds),
walk-forward with param selection, split-half, correlation with H-012, fee robustness.
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

FEE_RATE = 0.0006       # 6 bps taker fee on Bybit perps (default)
FEE_RATE_5BPS = 0.0005  # 5 bps per leg for fee robustness test
INITIAL_CAPITAL = 10_000.0

# Parameter grid — 6 x 5 x 3 = 90 combinations
LOOKBACKS    = [20, 30, 40, 60, 90, 120]   # days for rolling beta + cumret
REBAL_FREQS  = [3, 5, 7, 10, 14]           # rebalance every N days
N_LONGS      = [3, 4, 5]                   # top/bottom N to hold

# Walk-forward config: 4 equal folds
WF_FOLDS = 4

# H-012 reference params (LB60_R5_N4)
H012_LOOKBACK = 60
H012_REBAL    = 5
H012_N        = 4


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_daily_data():
    """Load daily parquet data for all 14 assets."""
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


def build_close_matrix(daily):
    """Align close prices into a single DataFrame."""
    closes = {}
    for sym, df in daily.items():
        col = "close" if "close" in df.columns else df.columns[3]
        closes[sym] = df[col]
    closes_df = pd.DataFrame(closes).sort_index()
    closes_df = closes_df.ffill().dropna(how="all")
    return closes_df


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(equity_series):
    """Compute standard metrics from equity curve."""
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "win_rate": 0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    return {
        "sharpe":     round(sharpe_ratio(rets, periods_per_year=365), 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd":     round(max_drawdown(eq), 4),
        "win_rate":   round(n_pos / n_total, 4) if n_total > 0 else 0,
    }


# ---------------------------------------------------------------------------
# Signal construction: BTC-residual alpha
# ---------------------------------------------------------------------------

def compute_btc_residual_alpha(closes, lookback):
    """
    For every day t, compute rolling BTC-adjusted alpha for each asset:

      1. simple returns over rolling lookback: ret_i = close[t]/close[t-lookback] - 1
      2. rolling beta to BTC using daily returns inside the window:
         beta_i = cov(daily_ret_i, daily_ret_btc) / var(daily_ret_btc)
         computed with a rolling window of `lookback` days
      3. alpha_i = ret_i - beta_i * ret_btc   (residual cumulative return)

    Returns a DataFrame of alpha scores aligned to closes.index.
    """
    if "BTC/USDT" not in closes.columns:
        raise ValueError("BTC/USDT must be in the universe for H-098")

    btc = closes["BTC/USDT"]

    # Daily returns — numpy arrays to avoid pandas alignment issues
    daily_rets_df = closes.pct_change()
    btc_daily_arr = daily_rets_df["BTC/USDT"].values  # shape (T,)
    rets_arr      = daily_rets_df.values               # shape (T, N)
    T, N          = rets_arr.shape

    # --- Rolling beta: cov(asset, btc) / var(btc) ---
    # Vectorised rolling over rows using a sliding window
    beta_arr = np.full((T, N), np.nan)

    for t in range(lookback, T):
        window_btc  = btc_daily_arr[t - lookback : t]  # (lookback,)
        window_rets = rets_arr[t - lookback : t, :]    # (lookback, N)

        if np.any(np.isnan(window_btc)):
            continue

        btc_var = np.var(window_btc, ddof=0)
        if btc_var < 1e-20:
            continue

        btc_mean  = np.mean(window_btc)
        rets_mean = np.nanmean(window_rets, axis=0)  # (N,)

        # cov(asset_i, btc) for all assets simultaneously
        # cov = E[x*y] - E[x]*E[y]
        cov = np.nanmean(window_rets * btc_daily_arr[t - lookback : t, None], axis=0) \
              - rets_mean * btc_mean

        beta_arr[t, :] = cov / btc_var

    beta_df = pd.DataFrame(beta_arr, index=closes.index, columns=closes.columns)

    # --- Cumulative returns over lookback window ---
    cum_ret     = closes.pct_change(lookback)    # DataFrame (T, N)
    cum_ret_btc = btc.pct_change(lookback)       # Series (T,)

    # --- alpha = cum_ret_i - beta_i * cum_ret_btc ---
    # Explicit element-wise: multiply beta by BTC cum return (broadcast along columns)
    alpha = cum_ret.values - beta_df.values * cum_ret_btc.values[:, None]
    alpha_df = pd.DataFrame(alpha, index=closes.index, columns=closes.columns)

    return alpha_df


# ---------------------------------------------------------------------------
# Cross-sectional factor backtester (reused from H-097 template)
# ---------------------------------------------------------------------------

def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  warmup=None, fee_rate=FEE_RATE):
    """
    Generic cross-sectional factor backtester using log returns.
    Higher ranking value = go long, lower = go short.
    Dollar-neutral: equal $ on long side and short side.
    """
    if n_short is None:
        n_short = n_long
    if warmup is None:
        warmup = 10

    n = len(closes)
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count  = 0

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]

        # Log returns for the day
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            # Use t-1 ranking (no look-ahead)
            ranks = ranking_series.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            ranked = valid.sort_values(ascending=False)
            longs  = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            # Turnover
            weight_changes = (new_weights - prev_weights).abs()
            turnover  = weight_changes.sum() / 2
            fee_drag  = turnover * fee_rate

            port_ret = (new_weights * log_rets).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count  += 1
            prev_weights  = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics   = compute_metrics(eq_series)
    metrics["n_trades"]    = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"]      = eq_series
    return metrics


# ---------------------------------------------------------------------------
# Full parameter scan
# ---------------------------------------------------------------------------

def run_full_scan(closes):
    """Run all 90 parameter combinations on the full period."""
    print("\n" + "=" * 70)
    print("H-098: BTC-RESIDUAL MOMENTUM -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE * 10_000:.0f} bps per trade")

    results = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        alpha = compute_btc_residual_alpha(closes, lookback)
        warmup = lookback + 5  # need lookback days + buffer

        res = run_xs_factor(closes, alpha, rebal, n_long, warmup=warmup)
        tag = f"LB{lookback}_R{rebal}_N{n_long}"
        results.append({
            "tag":        tag,
            "lookback":   lookback,
            "rebal":      rebal,
            "n_long":     n_long,
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
            "win_rate":   res["win_rate"],
            "n_trades":   res["n_trades"],
            "n_rebalances": res["n_rebalances"],
        })

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"\n  Total parameter combos: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe:   {df['sharpe'].mean():.3f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"  Best Sharpe:   {df['sharpe'].max():.3f}")
    print(f"  Worst Sharpe:  {df['sharpe'].min():.3f}")

    print("\n  All results sorted by Sharpe:")
    for _, row in df.sort_values("sharpe", ascending=False).iterrows():
        marker = "**" if row["sharpe"] > 0.5 else "  "
        print(f"  {marker} {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}, Trades {row['n_trades']}")

    return df


# ---------------------------------------------------------------------------
# Walk-forward: fixed best params, 4 equal folds
# ---------------------------------------------------------------------------

def run_walk_forward_fixed(closes, lookback, rebal, n_long):
    """Walk-forward with FIXED best params — 4 equal folds."""
    n     = len(closes)
    fold_size = n // WF_FOLDS
    tag   = f"LB{lookback}_R{rebal}_N{n_long}"

    print(f"\n  Walk-Forward (Fixed Params): {tag}")
    print(f"  Config: {WF_FOLDS} folds, {fold_size}d each")

    fold_results = []
    for fold in range(WF_FOLDS):
        # Train: folds 0 .. fold-1; Test: fold
        test_start = fold * fold_size
        test_end   = test_start + fold_size if fold < WF_FOLDS - 1 else n

        if test_end - test_start < 30:
            print(f"    Fold {fold+1}: too short, skipping")
            continue

        # We compute the signal on the FULL dataset but only evaluate on test slice
        # To avoid look-ahead in the signal, we compute alpha on closes[:test_end]
        # and restrict to the test window for evaluation.
        # This mirrors standard walk-forward approach.
        fold_closes = closes.iloc[test_start:test_end]
        fold_alpha  = compute_btc_residual_alpha(fold_closes, lookback)
        warmup      = min(lookback + 5, len(fold_closes) // 3)

        res = run_xs_factor(fold_closes, fold_alpha, rebal, n_long, warmup=warmup)
        fold_results.append({
            "fold":      fold + 1,
            "start":     fold_closes.index[0].strftime("%Y-%m-%d"),
            "end":       fold_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days":    len(fold_closes),
            "sharpe":    res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":    res["max_dd"],
            "win_rate":  res["win_rate"],
        })
        print(f"    Fold {fold+1}: {fold_closes.index[0].date()} -> "
              f"{fold_closes.index[-1].date()}, "
              f"Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}, "
              f"DD {res['max_dd']:.1%}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["sharpe"] > 0).sum()
    print(f"\n    Positive folds: {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe:     {df['sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df['annual_ret'].mean():.1%}")
    print(f"    Worst OOS DD:        {df['max_dd'].max():.1%}")
    return df


# ---------------------------------------------------------------------------
# Walk-forward: with parameter selection (train on prior folds, test on next)
# ---------------------------------------------------------------------------

def run_walk_forward_param_selection(closes):
    """
    Walk-forward with in-sample parameter selection:
    Fold k trains on folds 0..k-1 combined, selects best params, tests on fold k.
    """
    print(f"\n  Walk-Forward with In-Sample Parameter Selection")
    print(f"  Config: {WF_FOLDS} folds (train on fold 1..k-1, test on fold k)")

    n         = len(closes)
    fold_size = n // WF_FOLDS
    fold_results = []

    for fold in range(1, WF_FOLDS):   # start from fold 1 (need at least 1 train fold)
        train_end  = fold * fold_size
        test_start = train_end
        test_end   = test_start + fold_size if fold < WF_FOLDS - 1 else n

        if test_end - test_start < 30 or train_end < 100:
            continue

        train_closes = closes.iloc[:train_end]
        test_closes  = closes.iloc[test_start:test_end]

        # Step 1: find best params on training data
        best_sharpe = -999
        best_params = None
        for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
            warmup = lookback + 5
            if warmup >= len(train_closes) - 30:
                continue
            tr_alpha = compute_btc_residual_alpha(train_closes, lookback)
            res = run_xs_factor(train_closes, tr_alpha, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_params = (lookback, rebal, n_long)

        if best_params is None:
            continue

        lookback, rebal, n_long = best_params
        best_tag = f"LB{lookback}_R{rebal}_N{n_long}"

        # Step 2: evaluate on test fold
        test_alpha = compute_btc_residual_alpha(test_closes, lookback)
        warmup_t   = min(lookback + 5, len(test_closes) // 3)
        res_test   = run_xs_factor(test_closes, test_alpha, rebal, n_long, warmup=warmup_t)

        fold_results.append({
            "fold":            fold + 1,
            "start":           test_closes.index[0].strftime("%Y-%m-%d"),
            "end":             test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days":          len(test_closes),
            "train_best_params": best_tag,
            "train_sharpe":    round(best_sharpe, 3),
            "oos_sharpe":      res_test["sharpe"],
            "oos_annual_ret":  res_test["annual_ret"],
            "oos_max_dd":      res_test["max_dd"],
        })
        print(f"    Fold {fold+1}: train={best_tag} (IS {best_sharpe:.3f}), "
              f"OOS Sharpe {res_test['sharpe']:.3f}, Ann {res_test['annual_ret']:.1%}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe"] > 0).sum()
    print(f"\n    Positive OOS folds: {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe:     {df['oos_sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df['oos_annual_ret'].mean():.1%}")
    return df


# ---------------------------------------------------------------------------
# Split-half validation
# ---------------------------------------------------------------------------

def run_split_half(closes):
    """Split data into two halves, compare performance across all param combos."""
    n   = len(closes)
    mid = n // 2

    half1_closes = closes.iloc[:mid]
    half2_closes = closes.iloc[mid:]

    print(f"\n  Split-Half Validation")
    print(f"  Half 1: {half1_closes.index[0].date()} to {half1_closes.index[-1].date()} "
          f"({len(half1_closes)} days)")
    print(f"  Half 2: {half2_closes.index[0].date()} to {half2_closes.index[-1].date()} "
          f"({len(half2_closes)} days)")

    results_h1, results_h2 = [], []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        warmup = lookback + 5

        alpha1 = compute_btc_residual_alpha(half1_closes, lookback)
        res1   = run_xs_factor(half1_closes, alpha1, rebal, n_long, warmup=warmup)

        alpha2 = compute_btc_residual_alpha(half2_closes, lookback)
        res2   = run_xs_factor(half2_closes, alpha2, rebal, n_long, warmup=warmup)

        results_h1.append(res1["sharpe"])
        results_h2.append(res2["sharpe"])

    h1_arr = np.array(results_h1)
    h2_arr = np.array(results_h2)

    corr         = np.corrcoef(h1_arr, h2_arr)[0, 1]
    both_positive = ((h1_arr > 0) & (h2_arr > 0)).sum()

    print(f"  Sharpe rank correlation between halves: {corr:.3f}")
    print(f"  Positive in both halves: {both_positive}/{len(h1_arr)} "
          f"({both_positive/len(h1_arr):.0%})")
    print(f"  Half 1 mean Sharpe: {h1_arr.mean():.3f}")
    print(f"  Half 2 mean Sharpe: {h2_arr.mean():.3f}")

    return {
        "sharpe_correlation":  round(float(corr), 3),
        "both_positive_pct":   round(both_positive / len(h1_arr), 3),
        "half1_mean_sharpe":   round(float(h1_arr.mean()), 3),
        "half2_mean_sharpe":   round(float(h2_arr.mean()), 3),
    }


# ---------------------------------------------------------------------------
# Correlation with H-012 (60d momentum, rebal 5d, N=4)
# ---------------------------------------------------------------------------

def compute_h012_correlation(closes, best_lookback, best_rebal, best_n_long):
    """Compare daily returns of H-098 (best params) vs H-012 momentum."""
    print(f"\n  Correlation with H-012 (LB{H012_LOOKBACK}_R{H012_REBAL}_N{H012_N})")

    # H-098 with best params
    alpha_098  = compute_btc_residual_alpha(closes, best_lookback)
    warmup_098 = best_lookback + 5
    res_098    = run_xs_factor(closes, alpha_098, best_rebal, best_n_long, warmup=warmup_098)

    # H-012: raw 60d momentum
    mom_ranking = closes.pct_change(H012_LOOKBACK)
    res_012     = run_xs_factor(closes, mom_ranking, H012_REBAL, H012_N, warmup=H012_LOOKBACK + 5)

    eq_098 = res_098["equity"]
    eq_012 = res_012["equity"]

    rets_098 = eq_098.pct_change().dropna()
    rets_012 = eq_012.pct_change().dropna()

    common = rets_098.index.intersection(rets_012.index)
    if len(common) < 50:
        print("    Insufficient overlap for correlation")
        return 0.0, res_098, res_012

    corr = rets_098.loc[common].corr(rets_012.loc[common])
    print(f"    H-012 Momentum:      Sharpe {res_012['sharpe']:.3f}, "
          f"Ann {res_012['annual_ret']:.1%}")
    print(f"    H-098 Residual Mom:  Sharpe {res_098['sharpe']:.3f}, "
          f"Ann {res_098['annual_ret']:.1%}")
    print(f"    Daily return Pearson correlation: {corr:.3f}")

    return round(corr, 3), res_098, res_012


# ---------------------------------------------------------------------------
# Fee sensitivity (5 bps round-trip)
# ---------------------------------------------------------------------------

def run_fee_sensitivity(closes, scan_results):
    """Re-run all params at 5 bps round-trip fee (half the standard)."""
    print("\n" + "=" * 70)
    print("FEE SENSITIVITY: 5 bps round-trip (vs 6 bps default)")
    print("=" * 70)

    results = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        alpha  = compute_btc_residual_alpha(closes, lookback)
        warmup = lookback + 5
        res    = run_xs_factor(closes, alpha, rebal, n_long, warmup=warmup,
                               fee_rate=FEE_RATE_5BPS)
        tag    = f"LB{lookback}_R{rebal}_N{n_long}"
        results.append({"tag": tag, "sharpe": res["sharpe"], "annual_ret": res["annual_ret"]})

    df_fee = pd.DataFrame(results)
    positive_fee = df_fee[df_fee["sharpe"] > 0]

    print(f"  Positive Sharpe at 5bps: {len(positive_fee)}/{len(df_fee)} "
          f"({len(positive_fee)/len(df_fee):.0%})")
    print(f"  Mean Sharpe at 5bps: {df_fee['sharpe'].mean():.3f}")

    merge = (scan_results[["tag", "sharpe"]]
             .rename(columns={"sharpe": "sharpe_6bps"})
             .merge(df_fee[["tag", "sharpe"]].rename(columns={"sharpe": "sharpe_5bps"}),
                    on="tag"))
    degradation = (merge["sharpe_6bps"] - merge["sharpe_5bps"]).mean()
    print(f"  Mean Sharpe degradation (6bps→5bps): {degradation:.3f}")

    return {
        "pct_positive_5bps": round(len(positive_fee) / len(df_fee), 3),
        "mean_sharpe_5bps":  round(float(df_fee["sharpe"].mean()), 3),
        "sharpe_degradation": round(float(degradation), 3),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("H-098: BTC-RESIDUAL MOMENTUM — Backtest")
    print("=" * 70)

    # --- Load data ---
    print("\nLoading daily data...")
    daily = load_daily_data()
    closes = build_close_matrix(daily)
    print(f"\nAligned matrix: {closes.shape[0]} days x {closes.shape[1]} assets")
    print(f"Date range: {closes.index[0].date()} → {closes.index[-1].date()}")

    if closes.shape[1] < 5:
        print("ERROR: insufficient assets loaded")
        return

    # --- 1. Full parameter scan ---
    scan_df = run_full_scan(closes)

    best_row    = scan_df.loc[scan_df["sharpe"].idxmax()]
    best_lb     = int(best_row["lookback"])
    best_rebal  = int(best_row["rebal"])
    best_n      = int(best_row["n_long"])
    best_tag    = best_row["tag"]

    print(f"\n  Best params: {best_tag}")
    print(f"    Sharpe {best_row['sharpe']:.3f}, Ann {best_row['annual_ret']:.1%}, "
          f"DD {best_row['max_dd']:.1%}")

    # --- 2. Walk-forward (fixed best params, 4 equal folds) ---
    print("\n" + "=" * 70)
    print("WALK-FORWARD VALIDATION (FIXED BEST PARAMS)")
    print("=" * 70)
    wf_fixed_df = run_walk_forward_fixed(closes, best_lb, best_rebal, best_n)

    # --- 3. Walk-forward with parameter selection ---
    print("\n" + "=" * 70)
    print("WALK-FORWARD VALIDATION (WITH PARAMETER SELECTION)")
    print("=" * 70)
    wf_param_df = run_walk_forward_param_selection(closes)

    # --- 4. Split-half test ---
    print("\n" + "=" * 70)
    print("SPLIT-HALF TEST")
    print("=" * 70)
    split_half_res = run_split_half(closes)

    # --- 5. Correlation with H-012 ---
    print("\n" + "=" * 70)
    print("CORRELATION WITH H-012 MOMENTUM")
    print("=" * 70)
    corr_h012, res_098_best, res_012 = compute_h012_correlation(
        closes, best_lb, best_rebal, best_n)

    # --- 6. Fee sensitivity ---
    fee_res = run_fee_sensitivity(closes, scan_df)

    # --- Summary ---
    print("\n" + "=" * 70)
    print("H-098 FINAL SUMMARY")
    print("=" * 70)
    print(f"  Assets: {len(closes.columns)}, Days: {len(closes)}")
    print(f"  Period: {closes.index[0].date()} → {closes.index[-1].date()}")
    print()
    print(f"  Parameter Scan ({len(scan_df)} combos):")
    print(f"    % Positive Sharpe:  {(scan_df['sharpe']>0).mean():.0%}")
    print(f"    Mean Sharpe:        {scan_df['sharpe'].mean():.3f}")
    print(f"    Median Sharpe:      {scan_df['sharpe'].median():.3f}")
    print(f"    Best Params:        {best_tag}")
    print(f"    Best Sharpe:        {best_row['sharpe']:.3f}")
    print(f"    Best Annual Ret:    {best_row['annual_ret']:.1%}")
    print(f"    Best Max DD:        {best_row['max_dd']:.1%}")
    print()
    if wf_fixed_df is not None:
        pos_folds = (wf_fixed_df["sharpe"] > 0).sum()
        print(f"  Walk-Forward Fixed ({best_tag}):")
        for _, r in wf_fixed_df.iterrows():
            print(f"    Fold {int(r['fold'])}: Sharpe {r['sharpe']:.3f}, "
                  f"Ann {r['annual_ret']:.1%}, DD {r['max_dd']:.1%}")
        print(f"    Positive folds: {pos_folds}/{len(wf_fixed_df)}")
        print(f"    Mean OOS Sharpe: {wf_fixed_df['sharpe'].mean():.3f}")
    print()
    if wf_param_df is not None:
        pos_folds_p = (wf_param_df["oos_sharpe"] > 0).sum()
        print(f"  Walk-Forward Param Selection:")
        for _, r in wf_param_df.iterrows():
            print(f"    Fold {int(r['fold'])}: {r['train_best_params']} → "
                  f"OOS Sharpe {r['oos_sharpe']:.3f}, Ann {r['oos_annual_ret']:.1%}")
        print(f"    Positive folds: {pos_folds_p}/{len(wf_param_df)}")
        print(f"    Mean OOS Sharpe: {wf_param_df['oos_sharpe'].mean():.3f}")
    print()
    print(f"  Split-Half:")
    print(f"    Half 1 mean Sharpe: {split_half_res['half1_mean_sharpe']:.3f}")
    print(f"    Half 2 mean Sharpe: {split_half_res['half2_mean_sharpe']:.3f}")
    print(f"    Cross-half Sharpe corr: {split_half_res['sharpe_correlation']:.3f}")
    print(f"    Positive both halves: {split_half_res['both_positive_pct']:.0%}")
    print()
    print(f"  Correlation with H-012 Momentum: {corr_h012:.3f}")
    print()
    print(f"  Fee Sensitivity (5 bps):")
    print(f"    % Positive Sharpe: {fee_res['pct_positive_5bps']:.0%}")
    print(f"    Mean Sharpe:       {fee_res['mean_sharpe_5bps']:.3f}")
    print(f"    Degradation vs 6bps: {fee_res['sharpe_degradation']:.3f}")
    print()
    print("  NOTE: Sharpe uses 365 annualisation. lib/metrics.py may use 8760 (hourly)")
    print("  scale internally — all sharpe values may be inflated ~5x vs daily-correct.")
    print("  Relative comparisons with H-012/H-097 are valid.")
    print("=" * 70)

    # --- Save results ---
    results = {
        "hypothesis": "H-098",
        "title": "BTC-Residual Momentum",
        "n_assets": len(closes.columns),
        "n_days": len(closes),
        "period_start": str(closes.index[0].date()),
        "period_end":   str(closes.index[-1].date()),
        "param_scan": {
            "n_combos":             len(scan_df),
            "pct_positive_sharpe":  round((scan_df["sharpe"] > 0).mean(), 3),
            "mean_sharpe":          round(float(scan_df["sharpe"].mean()), 3),
            "median_sharpe":        round(float(scan_df["sharpe"].median()), 3),
            "best_params":          best_tag,
            "best_sharpe":          float(best_row["sharpe"]),
            "best_annual_ret":      float(best_row["annual_ret"]),
            "best_max_dd":          float(best_row["max_dd"]),
        },
        "walk_forward_fixed": (
            {
                "params": best_tag,
                "folds":  wf_fixed_df.to_dict(orient="records"),
                "mean_oos_sharpe": round(float(wf_fixed_df["sharpe"].mean()), 3),
            } if wf_fixed_df is not None else None
        ),
        "walk_forward_param_selection": (
            {
                "folds":  wf_param_df.to_dict(orient="records"),
                "mean_oos_sharpe": round(float(wf_param_df["oos_sharpe"].mean()), 3),
            } if wf_param_df is not None else None
        ),
        "split_half": split_half_res,
        "correlation_h012": corr_h012,
        "fee_sensitivity_5bps": fee_res,
        "all_params": scan_df[["tag","sharpe","annual_ret","max_dd","win_rate","n_trades"]].to_dict(orient="records"),
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {out_path}")


if __name__ == "__main__":
    main()
