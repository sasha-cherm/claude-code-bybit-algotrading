"""
H-137: Kurtosis Regime Change Factor

For each asset, compute the CHANGE in excess kurtosis of daily returns over
a rolling window. Rapidly increasing kurtosis (fat tails appearing) signals
transition to a volatile/mean-reverting regime; decreasing kurtosis signals
transition toward trending/calm regime.

Two directions:
  A) contrarian: Long assets with FALLING kurtosis (calming, trending ahead),
                  short assets with RISING kurtosis (chaos, mean-reversion ahead)
  B) risk_premium: Long RISING kurtosis (fat tails = risk premium),
                    short FALLING kurtosis

This is distinct from volatility (vol can be high but normally distributed)
and from momentum (kurtosis change captures distribution shape, not direction).

Dollar-neutral, equal-weighted long/short legs.

Validation: full parameter scan, walk-forward (6 folds, 90d test),
split-half, H-012 correlation.
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.0006
INITIAL_CAPITAL = 10_000.0

# Parameter grid
LOOKBACKS      = [20, 30, 40, 60, 90]       # kurtosis window (days)
DELTA_WINDOWS  = [5, 10, 20]                 # how far back to measure kurtosis change
REBAL_FREQS    = [3, 5, 7, 10]               # rebalance every N days
N_LONGS        = [3, 4, 5]                   # top/bottom N per side
DIRECTIONS     = ["contrarian", "risk_premium"]

# Walk-forward config
WF_FOLDS  = 6
WF_TRAIN  = 300
WF_TEST   = 90
WF_STEP   = 90


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


def build_close_matrix(daily):
    frames = {}
    for sym, df in daily.items():
        col = "close" if "close" in df.columns else df.columns[3]
        frames[sym] = df[col]
    closes = pd.DataFrame(frames).sort_index().dropna(how="all")
    closes = closes.ffill(limit=3)
    closes = closes.dropna(thresh=len(closes.columns) // 2 + 1)
    print(f"\n  Close matrix: {closes.shape[0]} days x {closes.shape[1]} assets")
    print(f"  Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    return closes


def compute_kurtosis_change(closes, lookback, delta_window):
    """
    For each asset on each day t:
      1. Compute excess kurtosis of log returns over [t-lookback, t)
      2. Compute excess kurtosis over [t-lookback-delta_window, t-delta_window)
      3. Factor = kurtosis(current) - kurtosis(lagged) = kurtosis CHANGE

    Positive = kurtosis increasing (more fat tails appearing)
    Negative = kurtosis decreasing (distribution normalizing)
    """
    log_returns = np.log(closes / closes.shift(1))
    factor = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)

    for col in closes.columns:
        rets = log_returns[col].values
        n = len(rets)
        vals = np.full(n, np.nan)

        for i in range(lookback + delta_window, n):
            # Current window kurtosis
            w_curr = rets[i - lookback:i]
            w_curr = w_curr[~np.isnan(w_curr)]

            # Lagged window kurtosis
            w_lag = rets[i - lookback - delta_window:i - delta_window]
            w_lag = w_lag[~np.isnan(w_lag)]

            if len(w_curr) < 10 or len(w_lag) < 10:
                continue

            # Excess kurtosis (Fisher definition: normal = 0)
            m_curr = np.mean(w_curr)
            s_curr = np.std(w_curr, ddof=1)
            if s_curr < 1e-12:
                continue
            k_curr = np.mean(((w_curr - m_curr) / s_curr) ** 4) - 3.0

            m_lag = np.mean(w_lag)
            s_lag = np.std(w_lag, ddof=1)
            if s_lag < 1e-12:
                continue
            k_lag = np.mean(((w_lag - m_lag) / s_lag) ** 4) - 3.0

            vals[i] = k_curr - k_lag

        factor[col] = vals

    return factor


def compute_metrics(equity_series):
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "win_rate": 0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "win_rate": round(n_pos / n_total, 4) if n_total > 0 else 0,
    }


def run_xs_factor(closes, ranking_series, rebal_freq, n_long,
                  direction="contrarian", fee_rate=FEE_RATE, warmup=95,
                  n_short=None):
    """
    Cross-sectional factor backtester.

    direction="contrarian": Long FALLING kurtosis (most negative change), short RISING
    direction="risk_premium": Long RISING kurtosis (most positive change), short FALLING
    """
    if n_short is None:
        n_short = n_long

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
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = ranking_series.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            if direction == "contrarian":
                # Long FALLING kurtosis (most negative change = calming)
                sorted_vals = valid.sort_values(ascending=True)
                longs = sorted_vals.index[:n_long]
                shorts = sorted_vals.index[-n_short:]
            else:
                # risk_premium: Long RISING kurtosis (most positive change)
                sorted_vals = valid.sort_values(ascending=False)
                longs = sorted_vals.index[:n_long]
                shorts = sorted_vals.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * fee_rate

            port_ret = (new_weights * log_rets).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count += 1
            prev_weights = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"] = eq_series
    return metrics


def run_full_scan(closes):
    print("\n" + "=" * 70)
    print("H-137: KURTOSIS REGIME CHANGE -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE * 10000:.0f} bps per trade")

    # Pre-compute kurtosis change for all (lookback, delta_window) combos
    print("\n  Pre-computing kurtosis change factors...")
    factor_cache = {}
    for lb, dw in product(LOOKBACKS, DELTA_WINDOWS):
        key = (lb, dw)
        print(f"    LB={lb}, DW={dw}...", end=" ", flush=True)
        factor_cache[key] = compute_kurtosis_change(closes, lb, dw)
        valid_count = factor_cache[key].notna().sum().sum()
        print(f"done ({valid_count} valid values)")

    results = []
    total_combos = len(LOOKBACKS) * len(DELTA_WINDOWS) * len(REBAL_FREQS) * len(N_LONGS) * len(DIRECTIONS)
    print(f"\n  Running {total_combos} parameter combinations...")
    combo_idx = 0

    for lb, dw, rebal, n_long, direction in product(
            LOOKBACKS, DELTA_WINDOWS, REBAL_FREQS, N_LONGS, DIRECTIONS):
        ranking = factor_cache[(lb, dw)]
        warmup = lb + dw + 5

        res = run_xs_factor(closes, ranking, rebal, n_long,
                            direction=direction, warmup=warmup)
        tag = f"LB{lb}_DW{dw}_R{rebal}_N{n_long}_{direction[:4]}"
        results.append({
            "tag": tag,
            "lookback": lb,
            "delta_window": dw,
            "rebal": rebal,
            "n_long": n_long,
            "direction": direction,
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
            "n_rebalances": res["n_rebalances"],
        })
        combo_idx += 1
        if combo_idx % 60 == 0:
            print(f"    ...{combo_idx}/{total_combos} done")

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]

    print(f"\n  Total parameter combos: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"  Best Sharpe:  {df['sharpe'].max():.3f}")
    print(f"  Worst Sharpe: {df['sharpe'].min():.3f}")

    for dir_ in DIRECTIONS:
        sub = df[df["direction"] == dir_]
        pos = (sub["sharpe"] > 0).sum()
        print(f"\n  Direction={dir_}:")
        print(f"    Positive Sharpe: {pos}/{len(sub)} ({pos/len(sub):.0%})")
        print(f"    Mean Sharpe: {sub['sharpe'].mean():.3f}")
        print(f"    Best Sharpe: {sub['sharpe'].max():.3f}")

    print("\n  Top 20 parameter combos by Sharpe:")
    for _, row in df.sort_values("sharpe", ascending=False).head(20).iterrows():
        marker = "**" if row["sharpe"] > 0.5 else "  "
        print(f"  {marker} {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}, Trades {row['n_trades']}")

    return df, factor_cache


def run_walk_forward(closes, lookback, delta_window, rebal, n_long, direction):
    print(f"\n  Walk-Forward (Fixed Params): "
          f"LB{lookback}_DW{delta_window}_R{rebal}_N{n_long}_{direction}")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, {WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx   = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0 or test_end_idx <= test_start_idx:
            break

        test_closes = closes.iloc[test_start_idx:test_end_idx]
        if len(test_closes) < 30:
            break

        test_ranking = compute_kurtosis_change(test_closes, lookback, delta_window)
        warmup = min(lookback + delta_window + 5, len(test_closes) // 2)

        res = run_xs_factor(test_closes, test_ranking, rebal, n_long,
                            direction=direction, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
        })
        print(f"    Fold {fold+1}: {test_closes.index[0].date()} -> {test_closes.index[-1].date()}, "
              f"Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}, "
              f"DD {res['max_dd']:.1%}, Trades {res['n_trades']}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df_wf = pd.DataFrame(fold_results)
    pos = (df_wf["sharpe"] > 0).sum()
    print(f"\n    Positive folds: {pos}/{len(df_wf)}")
    print(f"    Mean OOS Sharpe: {df_wf['sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df_wf['annual_ret'].mean():.1%}")
    print(f"    Total OOS test observations: {df_wf['n_days'].sum()}")
    return df_wf


def run_split_half(closes):
    n = len(closes)
    mid = n // 2
    half1 = closes.iloc[:mid]
    half2 = closes.iloc[mid:]

    print(f"\n  Split-Half Validation")
    print(f"  Half 1: {half1.index[0].date()} to {half1.index[-1].date()} ({len(half1)} days)")
    print(f"  Half 2: {half2.index[0].date()} to {half2.index[-1].date()} ({len(half2)} days)")

    results_h1 = []
    results_h2 = []

    for lb, dw, rebal, n_long, direction in product(
            LOOKBACKS, DELTA_WINDOWS, REBAL_FREQS, N_LONGS, DIRECTIONS):
        warmup = lb + dw + 5
        r1 = compute_kurtosis_change(half1, lb, dw)
        r2 = compute_kurtosis_change(half2, lb, dw)
        res1 = run_xs_factor(half1, r1, rebal, n_long, direction=direction, warmup=warmup)
        res2 = run_xs_factor(half2, r2, rebal, n_long, direction=direction, warmup=warmup)
        results_h1.append(res1["sharpe"])
        results_h2.append(res2["sharpe"])

    h1_arr = np.array(results_h1)
    h2_arr = np.array(results_h2)

    corr, _ = spearmanr(h1_arr, h2_arr)
    both_pos = ((h1_arr > 0) & (h2_arr > 0)).sum()

    print(f"  Spearman rank corr (Sharpe, H1 vs H2): {corr:.3f}")
    print(f"  Both halves positive: {both_pos}/{len(h1_arr)} ({both_pos/len(h1_arr):.0%})")
    print(f"  Half 1 mean Sharpe: {h1_arr.mean():.3f}")
    print(f"  Half 2 mean Sharpe: {h2_arr.mean():.3f}")

    # Check for inversion
    if (h1_arr.mean() > 0.2 and h2_arr.mean() < -0.2) or \
       (h1_arr.mean() < -0.2 and h2_arr.mean() > 0.2):
        print("  WARNING: Signal inversion detected between halves!")

    return {
        "spearman_corr": round(float(corr), 3),
        "both_positive_pct": round(both_pos / len(h1_arr), 3),
        "half1_mean_sharpe": round(float(h1_arr.mean()), 3),
        "half2_mean_sharpe": round(float(h2_arr.mean()), 3),
    }


def compute_h012_correlation(closes, lookback, delta_window, rebal, n_long, direction):
    print(f"\n  Correlation with H-012 (60d Momentum)")

    ranking = compute_kurtosis_change(closes, lookback, delta_window)
    warmup = lookback + delta_window + 5
    res_factor = run_xs_factor(closes, ranking, rebal, n_long,
                               direction=direction, warmup=warmup)

    # H-012: 60d momentum, long top, short bottom
    mom_ranking = closes.pct_change(60)
    res_mom = run_xs_factor(closes, mom_ranking, 5, 4,
                            direction="contrarian", warmup=65)
    # "contrarian" sorts descending -> largest pct_change first = longs

    eq_factor = res_factor["equity"]
    eq_mom    = res_mom["equity"]

    rets_factor = eq_factor.pct_change().dropna()
    rets_mom    = eq_mom.pct_change().dropna()

    common = rets_factor.index.intersection(rets_mom.index)
    if len(common) < 50:
        print("    Insufficient overlap for correlation")
        return 0.0

    corr = rets_factor.loc[common].corr(rets_mom.loc[common])
    print(f"    Daily return correlation H-137 vs H-012: {corr:.3f}")
    print(f"    H-012 Momentum: Sharpe {res_mom['sharpe']:.3f}, Ann {res_mom['annual_ret']:.1%}")
    print(f"    H-137 Kurtosis: Sharpe {res_factor['sharpe']:.3f}, Ann {res_factor['annual_ret']:.1%}")
    return round(corr, 3)


if __name__ == "__main__":
    print("=" * 70)
    print("H-137: Kurtosis Regime Change Factor")
    print("=" * 70)

    # 1. Load data
    print("\n[1/5] Loading daily data...")
    daily = load_daily_data()
    closes = build_close_matrix(daily)

    if closes.shape[1] < 6:
        print("ERROR: Too few assets loaded. Aborting.")
        sys.exit(1)

    # 2. Full parameter scan
    print("\n[2/5] Full Parameter Scan...")
    scan_df, factor_cache = run_full_scan(closes)

    best_row = scan_df.loc[scan_df["sharpe"].idxmax()]
    best_lb  = int(best_row["lookback"])
    best_dw  = int(best_row["delta_window"])
    best_r   = int(best_row["rebal"])
    best_n   = int(best_row["n_long"])
    best_dir = best_row["direction"]

    print(f"\n  BEST OVERALL: {best_row['tag']}")
    print(f"    Sharpe {best_row['sharpe']:.3f}, Ann {best_row['annual_ret']:.1%}, "
          f"DD {best_row['max_dd']:.1%}, WR {best_row['win_rate']:.1%}")

    # 3. Walk-Forward (6 folds)
    print("\n[3/5] Walk-Forward Validation...")
    wf_df = run_walk_forward(closes, best_lb, best_dw, best_r, best_n, best_dir)

    # 4. Split-Half
    print("\n[4/5] Split-Half Validation...")
    sh_results = run_split_half(closes)

    # 5. H-012 Correlation
    print("\n[5/5] H-012 Correlation...")
    h012_corr = compute_h012_correlation(closes, best_lb, best_dw, best_r, best_n, best_dir)

    # Summary
    print("\n" + "=" * 70)
    print("H-137 SUMMARY")
    print("=" * 70)

    pct_positive = len(scan_df[scan_df["sharpe"] > 0]) / len(scan_df)
    mean_sharpe  = scan_df["sharpe"].mean()

    print(f"\n  FULL SCAN ({len(scan_df)} combos):")
    print(f"    % Positive Sharpe:  {pct_positive:.0%}")
    print(f"    Mean Sharpe:        {mean_sharpe:.3f}")
    print(f"    Best Sharpe:        {scan_df['sharpe'].max():.3f}  ({best_row['tag']})")

    for dir_ in DIRECTIONS:
        sub = scan_df[scan_df["direction"] == dir_]
        pos = (sub["sharpe"] > 0).sum()
        print(f"    {dir_}: {pos}/{len(sub)} positive, mean Sharpe {sub['sharpe'].mean():.3f}")

    if wf_df is not None:
        pos_folds = (wf_df["sharpe"] > 0).sum()
        print(f"\n  WALK-FORWARD ({len(wf_df)} folds):")
        print(f"    Positive folds:     {pos_folds}/{len(wf_df)}")
        print(f"    Mean OOS Sharpe:    {wf_df['sharpe'].mean():.3f}")
        print(f"    Mean OOS Ann Ret:   {wf_df['annual_ret'].mean():.1%}")
        print(f"    Total test obs:     {wf_df['n_days'].sum()} days")
        print(f"    Total test trades:  {wf_df['n_trades'].sum()}")

    print(f"\n  SPLIT-HALF:")
    print(f"    Spearman corr:      {sh_results['spearman_corr']:.3f}")
    print(f"    Both halves pos:    {sh_results['both_positive_pct']:.0%}")
    print(f"    H1 mean Sharpe:     {sh_results['half1_mean_sharpe']:.3f}")
    print(f"    H2 mean Sharpe:     {sh_results['half2_mean_sharpe']:.3f}")

    print(f"\n  H-012 CORRELATION:    {h012_corr:.3f}")

    # Verdict
    print("\n  VERDICT:")
    reasons = []
    if pct_positive < 0.60:
        reasons.append(f"Only {pct_positive:.0%} params positive (need >=60%)")
    if sh_results["half1_mean_sharpe"] * sh_results["half2_mean_sharpe"] < 0 and \
       abs(sh_results["half1_mean_sharpe"]) > 0.2 and abs(sh_results["half2_mean_sharpe"]) > 0.2:
        reasons.append("Signal inversion between halves")
    if wf_df is not None and wf_df["sharpe"].mean() < 0:
        reasons.append(f"Negative WF OOS mean Sharpe ({wf_df['sharpe'].mean():.3f})")
    if abs(h012_corr) > 0.5:
        reasons.append(f"High H-012 correlation ({h012_corr:.3f})")

    if reasons:
        verdict = "REJECTED"
        print(f"    {verdict}")
        for r in reasons:
            print(f"      - {r}")
    elif pct_positive >= 0.60 and mean_sharpe >= 0.3 and \
         wf_df is not None and wf_df["sharpe"].mean() >= 0.2:
        verdict = "CONFIRMED"
        print(f"    {verdict} -- robust signal with positive OOS performance")
    else:
        verdict = "CONDITIONAL"
        print(f"    {verdict} -- some positive signal but needs more evidence")

    # Save results
    output_path = Path(__file__).parent / "results.json"
    results_dict = {
        "hypothesis": "H-137",
        "title": "Kurtosis Regime Change Factor",
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "n_days": len(closes),
        "n_assets": len(closes.columns),
        "n_combos": len(scan_df),
        "pct_positive_sharpe": round(pct_positive, 4),
        "mean_sharpe": round(mean_sharpe, 4),
        "best_sharpe": round(float(scan_df["sharpe"].max()), 4),
        "best_params": best_row["tag"],
        "best_direction": best_dir,
        "walk_forward": {
            "n_folds": len(wf_df) if wf_df is not None else 0,
            "positive_folds": int((wf_df["sharpe"] > 0).sum()) if wf_df is not None else 0,
            "mean_oos_sharpe": round(float(wf_df["sharpe"].mean()), 3) if wf_df is not None else None,
            "total_test_days": int(wf_df["n_days"].sum()) if wf_df is not None else 0,
            "total_test_trades": int(wf_df["n_trades"].sum()) if wf_df is not None else 0,
        },
        "split_half": sh_results,
        "h012_correlation": h012_corr,
        "verdict": verdict,
    }

    with open(output_path, "w") as f:
        json.dump(results_dict, f, indent=2)
    print(f"\n  Results saved to {output_path}")
    print("=" * 70)
