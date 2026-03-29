"""
H-135: Mean Reversion Speed Factor (Cross-Sectional)

Measure how quickly each asset reverts to its moving average after deviations.
Operationalised as the lag-1 autocorrelation of daily returns:
  - Positive autocorrelation => asset is TRENDING (momentum continues)
  - Negative autocorrelation => asset is MEAN-REVERTING (fades the move)

Signal: Rank by rolling lag-1 autocorrelation over a window.
  - LONG top-N (highest autocorrelation = trending = ride the move)
  - SHORT bottom-N (lowest autocorrelation = mean-reverting = fade the move)

This is regime-adaptive: the signal changes as assets shift between trending
and mean-reverting regimes.

Key difference from H-115: parameter grid extended to include shorter lookbacks
(10 days), 90-day OOS windows in walk-forward, and explicit split-half analysis
with cross-validation in both directions.

Parameter grid (45 combos):
  Lookback windows : [10, 20, 30, 40, 60] days
  Rebalance freq   : [3, 5, 7] days
  N positions each : [3, 4, 5]

Sharpe: daily mean / daily std * sqrt(365)
Fee: 0.1% round-trip per rebalance (10 bps, Bybit taker)
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

FEE_RATE = 0.001
INITIAL_CAPITAL = 10_000.0

LOOKBACKS   = [10, 20, 30, 40, 60]
REBAL_FREQS = [3, 5, 7]
N_SIZES     = [3, 4, 5]

WF_FOLDS        = 6
WF_TEST_DAYS    = 90   # 90-day OOS windows


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


def build_close_matrix(daily: dict) -> pd.DataFrame:
    closes = {}
    for sym, df in daily.items():
        closes[sym] = df["close"]
    return pd.DataFrame(closes).dropna(how="all").ffill()


def compute_metrics(equity_series: pd.Series) -> dict:
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99, "annual_ret": 0.0, "max_dd": 1.0, "win_rate": 0.0}
    rets = eq.pct_change().dropna()
    n_pos    = (rets > 0).sum()
    n_total  = len(rets)
    sharpe   = float(rets.mean() / rets.std() * np.sqrt(365)) if rets.std() > 1e-10 else 0.0
    return {
        "sharpe":     round(sharpe, 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd":     round(max_drawdown(eq), 4),
        "win_rate":   round(n_pos / n_total, 4) if n_total > 0 else 0.0,
    }


def compute_autocorrelation_matrix(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    For each day t, compute rolling lag-1 autocorrelation of daily returns
    over the past `lookback` days.  Requires at least 10 valid observations.
    Returns a DataFrame of the same shape as `returns` filled with NaN where
    insufficient data.
    """
    n_days   = len(returns)
    n_assets = len(returns.columns)
    ac_vals  = np.full((n_days, n_assets), np.nan)
    ret_arr  = returns.values

    for i in range(lookback, n_days):
        window = ret_arr[i - lookback:i, :]
        for j in range(n_assets):
            col   = window[:, j]
            valid = col[~np.isnan(col)]
            if len(valid) < 10:
                continue
            r1 = valid[:-1]
            r2 = valid[1:]
            if np.std(r1) < 1e-12 or np.std(r2) < 1e-12:
                continue
            ac_vals[i, j] = np.corrcoef(r1, r2)[0, 1]

    return pd.DataFrame(ac_vals, index=returns.index, columns=returns.columns)


def run_mr_speed_factor(
    closes: pd.DataFrame,
    lookback: int,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    fee_rate: float = FEE_RATE,
    pre_computed: pd.DataFrame | None = None,
) -> dict:
    if n_short is None:
        n_short = n_long

    returns = closes.pct_change()

    ac_matrix = pre_computed if pre_computed is not None else \
                compute_autocorrelation_matrix(returns, lookback)

    n      = len(closes)
    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count  = 0
    warmup       = lookback + 5

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets        = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            sig   = ac_matrix.iloc[i - 1]
            valid = sig.dropna()

            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # LONG highest autocorrelation (trending), SHORT lowest (mean-reverting)
            ranked = valid.sort_values(ascending=False)
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

            port_ret      = (new_weights * log_rets).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count  += 1
            prev_weights  = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series            = pd.Series(equity, index=closes.index)
    metrics              = compute_metrics(eq_series)
    metrics["n_trades"]     = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"]       = eq_series
    return metrics


# ── Full In-Sample Scan ────────────────────────────────────────────────────────

def run_full_scan(closes: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-135: MEAN REVERSION SPEED FACTOR -- Full In-Sample Param Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per trade (Bybit taker)")
    print(f"  Signal   : lag-1 autocorrelation of daily returns")
    print(f"  Long     : high autocorr (trending) | Short: low autocorr (mean-reverting)")

    returns = closes.pct_change()

    print("\n  Pre-computing autocorrelation matrices...")
    ac_cache = {}
    for lb in LOOKBACKS:
        print(f"    Lookback {lb:2d}d ...", end=" ", flush=True)
        ac_cache[lb] = compute_autocorrelation_matrix(returns, lb)
        print("done")

    n_combos = len(LOOKBACKS) * len(REBAL_FREQS) * len(N_SIZES)
    print(f"\n  Running {n_combos} param combos...")

    results = []
    for lb, rebal, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        res = run_mr_speed_factor(closes, lb, rebal, n, pre_computed=ac_cache[lb])
        tag = f"L{lb}_R{rebal}_N{n}"
        results.append({
            "tag":        tag,
            "lookback":   lb,
            "rebal":      rebal,
            "n":          n,
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
            "win_rate":   res["win_rate"],
            "n_trades":   res["n_trades"],
        })

    df = pd.DataFrame(results)
    n_positive  = (df["sharpe"] > 0).sum()
    pct_positive = n_positive / len(df) * 100

    print(f"\n  Results: {n_positive}/{len(df)} positive Sharpe ({pct_positive:.1f}%)")
    print(f"  Mean Sharpe   : {df['sharpe'].mean():.3f}")
    print(f"  Median Sharpe : {df['sharpe'].median():.3f}")
    best_row = df.loc[df["sharpe"].idxmax()]
    print(f"  Best          : {best_row['tag']} "
          f"Sharpe={best_row['sharpe']:.3f} "
          f"Ret={best_row['annual_ret']*100:.1f}% "
          f"DD={best_row['max_dd']*100:.1f}%")

    print("\n  Top 10 param sets:")
    print(f"  {'Tag':20s}  {'Sharpe':>7}  {'Ann.Ret':>8}  {'MaxDD':>7}  {'WinRate':>8}  {'Trades':>7}")
    for _, row in df.nlargest(10, "sharpe").iterrows():
        print(f"  {row['tag']:20s}  {row['sharpe']:7.3f}  "
              f"{row['annual_ret']*100:7.1f}%  {row['max_dd']*100:6.1f}%  "
              f"{row['win_rate']*100:7.1f}%  {row['n_trades']:7d}")

    print("\n  Bottom 5 param sets:")
    for _, row in df.nsmallest(5, "sharpe").iterrows():
        print(f"  {row['tag']:20s}  {row['sharpe']:7.3f}")

    return df, results, ac_cache


# ── Walk-Forward (90-day OOS windows) ─────────────────────────────────────────

def run_mr_speed_factor_warmstart(
    train_closes: pd.DataFrame,
    test_closes: pd.DataFrame,
    lookback: int,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    fee_rate: float = FEE_RATE,
) -> dict:
    """
    Run the MR-speed factor on test_closes, but warm-start the autocorrelation
    signal using the last `lookback` rows of train_closes.  This means the
    signal is valid from day 1 of the test period.
    """
    if n_short is None:
        n_short = n_long

    # Build a combined window so we can compute AC signal for the test period
    # from day 0 (using the tail of train as warm-up data)
    warm   = train_closes.iloc[-lookback:]          # warm-up price history
    combined = pd.concat([warm, test_closes])
    returns  = combined.pct_change()

    ac_matrix_combined = compute_autocorrelation_matrix(returns, lookback)
    # Slice back to test period only (indices from len(warm) onward)
    ac_test = ac_matrix_combined.iloc[len(warm):]
    # Re-index to match test_closes
    ac_test = ac_test.set_axis(test_closes.index)

    n      = len(test_closes)
    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

    prev_weights = pd.Series(0.0, index=test_closes.columns)
    total_trades = 0
    rebal_count  = 0

    for i in range(1, n):
        price_today     = test_closes.iloc[i]
        price_yesterday = test_closes.iloc[i - 1]
        log_rets        = np.log(price_today / price_yesterday)

        # Rebalance from day 1 of test (warmup already done via train data)
        if i % rebal_freq == 0:
            sig   = ac_test.iloc[i - 1]
            valid = sig.dropna()

            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            ranked = valid.sort_values(ascending=False)
            longs  = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=test_closes.columns)
            for sym in longs:
                new_weights[sym] =  1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover       = weight_changes.sum() / 2.0
            fee_drag       = turnover * fee_rate

            port_ret      = (new_weights * log_rets).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count  += 1
            prev_weights  = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=test_closes.index)
    metrics   = compute_metrics(eq_series)
    metrics["n_trades"]     = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"]       = eq_series
    return metrics


def walk_forward(closes: pd.DataFrame, n_folds: int = WF_FOLDS):
    print(f"\n  Walk-Forward Validation ({n_folds} folds, {WF_TEST_DAYS}-day OOS windows)")
    n          = len(closes)
    test_size  = WF_TEST_DAYS
    wf_results = []

    # Each test fold needs at least lookback+rebal+5 days of warm-start from training
    # Use the last 60% of data for testing, first 40% mandatory train
    min_train  = 200   # minimum training days
    total_test_span = test_size * n_folds
    if min_train + total_test_span > n:
        test_size = max(45, (n - min_train) // n_folds)
        print(f"    (Adjusted test size to {test_size} days to fit {n} total days)")

    start_offset = max(min_train, n - test_size * n_folds)

    for fold in range(n_folds):
        test_start = start_offset + fold * test_size
        test_end   = test_start + test_size
        if test_end > n:
            break
        train_closes = closes.iloc[:test_start]
        test_closes  = closes.iloc[test_start:test_end]
        if len(train_closes) < min_train:
            continue

        # Pick best params on train set
        best_sharpe = -99
        best_p      = None
        for lb, rebal, nn in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
            if len(train_closes) < lb + 30:
                continue
            res = run_mr_speed_factor(train_closes, lb, rebal, nn)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_p      = (lb, rebal, nn)

        if best_p is None:
            continue

        lb, rebal, nn = best_p
        # Warm-start OOS: pass last `lb` rows of train as context
        test_res = run_mr_speed_factor_warmstart(
            train_closes, test_closes, lb, rebal, nn
        )
        wf_results.append({
            "fold":         fold,
            "train_sharpe": round(best_sharpe, 3),
            "test_sharpe":  round(test_res["sharpe"], 3),
            "params":       f"L{lb}_R{rebal}_N{nn}",
            "test_ret":     round(test_res["annual_ret"], 4),
            "test_dd":      round(test_res["max_dd"], 4),
            "train_n":      len(train_closes),
            "test_n":       len(test_closes),
        })
        print(f"    Fold {fold}: train={len(train_closes)}d best({best_p}) "
              f"train_S={best_sharpe:.3f} -> OOS_S={test_res['sharpe']:.3f} "
              f"OOS_ret={test_res['annual_ret']*100:.1f}%")

    if wf_results:
        wf_df   = pd.DataFrame(wf_results)
        n_pos   = (wf_df["test_sharpe"] > 0).sum()
        mean_s  = wf_df["test_sharpe"].mean()
        print(f"\n  WF Summary: {n_pos}/{len(wf_df)} folds positive OOS Sharpe, "
              f"mean OOS Sharpe = {mean_s:.3f}")
        return wf_df
    return pd.DataFrame()


# ── Split-Half Stability ───────────────────────────────────────────────────────

def split_half_test(closes: pd.DataFrame, ac_cache: dict | None = None):
    print(f"\n  Split-Half Stability Test")
    mid = len(closes) // 2
    h1  = closes.iloc[:mid]
    h2  = closes.iloc[mid:]

    print(f"    Half-1: {h1.index[0].date()} to {h1.index[-1].date()} ({len(h1)} days)")
    print(f"    Half-2: {h2.index[0].date()} to {h2.index[-1].date()} ({len(h2)} days)")

    r1, r2 = [], []
    for lb, rebal, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        res1 = run_mr_speed_factor(h1, lb, rebal, n)
        res2 = run_mr_speed_factor(h2, lb, rebal, n)
        r1.append(res1["sharpe"])
        r2.append(res2["sharpe"])

    corr  = np.corrcoef(r1, r2)[0, 1]
    print(f"    Param-rank correlation H1 vs H2 : {corr:.3f}")
    print(f"    Half-1 mean Sharpe: {np.mean(r1):.3f}  |  Half-2 mean Sharpe: {np.mean(r2):.3f}")
    print(f"    Half-1 % positive : {np.mean(np.array(r1)>0)*100:.1f}%  |  "
          f"Half-2 % positive: {np.mean(np.array(r2)>0)*100:.1f}%")
    return float(corr), float(np.mean(r1)), float(np.mean(r2))


# ── Correlation with H-012 (Momentum) ─────────────────────────────────────────

def correlation_with_h012(closes: pd.DataFrame, best_lb: int = 30,
                           best_rebal: int = 5, best_n: int = 4):
    print(f"\n  Correlation with H-012 (Cross-Sectional Momentum)")
    res    = run_mr_speed_factor(closes, best_lb, best_rebal, best_n)
    my_rets = res["equity"].pct_change().dropna()

    # Build a simple cross-sectional momentum benchmark (60-day lookback, top/bottom 4)
    roll_ret = closes.pct_change(60)
    h012_eq  = np.zeros(len(closes))
    h012_eq[0] = 10_000.0
    prev_w   = pd.Series(0.0, index=closes.columns)
    warmup   = 65
    for i in range(1, len(closes)):
        pt = closes.iloc[i]
        py = closes.iloc[i - 1]
        lr = np.log(pt / py)
        if i >= warmup and (i - warmup) % 5 == 0:
            sig = roll_ret.iloc[i - 1].dropna()
            if len(sig) >= 8:
                ranked = sig.sort_values(ascending=False)
                new_w  = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:4]:
                    new_w[s] =  1.0 / 4
                for s in ranked.index[-4:]:
                    new_w[s] = -1.0 / 4
                prev_w = new_w
        h012_eq[i] = h012_eq[i - 1] * np.exp((prev_w * lr).sum())

    h012_rets = pd.Series(h012_eq, index=closes.index).pct_change().dropna()
    common    = my_rets.index.intersection(h012_rets.index)
    corr      = np.corrcoef(my_rets.loc[common].values, h012_rets.loc[common].values)[0, 1]
    print(f"    Correlation with H-012 momentum: {corr:.3f}")
    return float(corr)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("H-135: Mean Reversion Speed Factor")
    print("Loading daily data...")
    daily  = load_daily_data()
    closes = build_close_matrix(daily)
    print(f"\nClose matrix: {closes.shape[0]} days x {closes.shape[1]} assets")
    print(f"Date range  : {closes.index[0].date()} to {closes.index[-1].date()}")

    # 1. Full in-sample scan
    df_results, results_list, ac_cache = run_full_scan(closes)

    # 2. Walk-forward OOS
    wf_df = walk_forward(closes)

    # 3. Split-half stability
    sh_corr, sh_mean1, sh_mean2 = split_half_test(closes)

    # 4. Correlation with H-012
    best = df_results.loc[df_results["sharpe"].idxmax()]
    corr_012 = correlation_with_h012(
        closes, int(best["lookback"]), int(best["rebal"]), int(best["n"])
    )

    # ── Final summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("H-135 FINAL SUMMARY")
    print("=" * 72)
    n_pos = (df_results["sharpe"] > 0).sum()
    print(f"  Total param combos   : {len(df_results)}")
    print(f"  Positive Sharpe      : {n_pos}/{len(df_results)} ({n_pos/len(df_results)*100:.1f}%)")
    print(f"  Mean IS Sharpe       : {df_results['sharpe'].mean():.3f}")
    print(f"  Best IS Sharpe       : {best['sharpe']:.3f}  ({best['tag']})")
    print(f"  Best IS Annual Ret   : {best['annual_ret']*100:.1f}%")
    print(f"  Best IS Max DD       : {best['max_dd']*100:.1f}%")
    if len(wf_df) > 0:
        n_pos_wf = (wf_df["test_sharpe"] > 0).sum()
        print(f"  WF OOS positive folds: {n_pos_wf}/{len(wf_df)}")
        print(f"  WF mean OOS Sharpe   : {wf_df['test_sharpe'].mean():.3f}")
    print(f"  Split-half corr      : {sh_corr:.3f}")
    print(f"  Corr w/ H-012 (mom)  : {corr_012:.3f}")

    # ── Save results ───────────────────────────────────────────────────────────
    output = {
        "hypothesis":           "H-135",
        "name":                 "Mean Reversion Speed Factor",
        "description":          "Rank assets by rolling lag-1 return autocorrelation. "
                                 "Long trending (high autocorr), short mean-reverting (low autocorr).",
        "date_range":           f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "n_assets":             len(closes.columns),
        "n_days":               len(closes),
        "n_params":             len(df_results),
        "pct_positive_sharpe":  round(float((df_results["sharpe"] > 0).mean() * 100), 1),
        "mean_sharpe":          round(float(df_results["sharpe"].mean()), 3),
        "median_sharpe":        round(float(df_results["sharpe"].median()), 3),
        "best_params":          str(best["tag"]),
        "best_sharpe":          round(float(best["sharpe"]), 3),
        "best_annual_ret":      round(float(best["annual_ret"]), 4),
        "best_max_dd":          round(float(best["max_dd"]), 4),
        "best_win_rate":        round(float(best["win_rate"]), 4),
        "wf_folds_total":       len(wf_df),
        "wf_folds_positive":    int((wf_df["test_sharpe"] > 0).sum()) if len(wf_df) > 0 else 0,
        "wf_mean_oos_sharpe":   round(float(wf_df["test_sharpe"].mean()), 3) if len(wf_df) > 0 else None,
        "split_half_corr":      round(sh_corr, 3),
        "split_half_mean1":     round(sh_mean1, 3),
        "split_half_mean2":     round(sh_mean2, 3),
        "corr_h012":            round(corr_012, 3),
        "all_params": [
            {k: v for k, v in r.items() if k != "equity"}
            for r in results_list
        ],
        "wf_folds": wf_df.to_dict(orient="records") if len(wf_df) > 0 else [],
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")
    print("\n" + json.dumps({k: v for k, v in output.items() if k != "all_params"}, indent=2))
