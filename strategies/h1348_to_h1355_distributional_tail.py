"""
Batch backtest: H-1348 to H-1355 — Distributional Tail Dynamics.
Signals based on how the tails and shape of the return distribution are evolving.

H-1348: Tail Weight Change — kurtosis(20d) - kurtosis(60d). Increasing tail weight = regime change.
H-1349: Left Tail Shrinkage — 5th percentile change: percentile5(recent 20d) - percentile5(prior 20d). Less negative = left tail shrinking.
H-1350: Right Tail Growth — 95th percentile change: percentile95(recent 20d) - percentile95(prior 20d). More positive = right tail expanding.
H-1351: Tail Asymmetry Change — (p95/|p5| recent 20d) - (p95/|p5| prior 20d). Increasing = becoming more right-skewed.
H-1352: Extreme Day Ratio — (days >2 sigma) / total days in 30d. More extremes = breakout regime.
H-1353: VaR Breach Rate — fraction of days where loss > historical VaR(5%) in rolling 30d. Frequent breaches = regime shift.
H-1354: Expected Shortfall Trend — avg loss on worst 5 days in 30d, compare recent vs prior window.
H-1355: Distribution Width Change — IQR(recent 20d) - IQR(prior 20d). Widening = expanding regime.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats as scipy_stats

DATA_DIR = Path("data")
FEE_RATE = 0.00055
SLIPPAGE_BPS = 2

ASSETS = ["BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX", "LINK",
          "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM"]


def load_daily_ohlcv():
    frames = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_1d.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            frames[f"{ticker}/USDT"] = df
        except:
            pass
    opens, highs, lows, closes, volumes = {}, {}, {}, {}, {}
    for sym, df in frames.items():
        opens[sym] = df["open"]
        highs[sym] = df["high"]
        lows[sym] = df["low"]
        closes[sym] = df["close"]
        volumes[sym] = df["volume"] * df["close"]
    idx = sorted(set.intersection(*[set(df.index) for df in frames.values()]))
    opens = pd.DataFrame(opens).loc[idx]
    highs = pd.DataFrame(highs).loc[idx]
    lows = pd.DataFrame(lows).loc[idx]
    closes = pd.DataFrame(closes).loc[idx]
    volumes = pd.DataFrame(volumes).loc[idx]
    return opens, highs, lows, closes, volumes


def compute_signals(opens, highs, lows, closes, volumes):
    returns = closes.pct_change()
    signals = {}

    # H-1348: Tail Weight Change (kurtosis delta)
    kurt_20 = returns.rolling(20).apply(lambda x: scipy_stats.kurtosis(x, fisher=True), raw=True)
    kurt_60 = returns.rolling(60).apply(lambda x: scipy_stats.kurtosis(x, fisher=True), raw=True)
    signals["tail_weight_change"] = kurt_20 - kurt_60

    # H-1349: Left Tail Shrinkage
    p5_recent = returns.rolling(20).quantile(0.05)
    p5_prior = returns.shift(20).rolling(20).quantile(0.05)
    signals["left_tail_shrink"] = p5_recent - p5_prior

    # H-1350: Right Tail Growth
    p95_recent = returns.rolling(20).quantile(0.95)
    p95_prior = returns.shift(20).rolling(20).quantile(0.95)
    signals["right_tail_growth"] = p95_recent - p95_prior

    # H-1351: Tail Asymmetry Change
    def tail_asym(series, window=20):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            chunk = series.iloc[i-window:i].values
            valid = chunk[np.isfinite(chunk)]
            if len(valid) < 10:
                continue
            p95 = np.percentile(valid, 95)
            p5 = np.percentile(valid, 5)
            if abs(p5) < 1e-15:
                continue
            result.iloc[i] = p95 / abs(p5)
        return result

    asym_recent = returns.apply(lambda col: tail_asym(col, 20))
    asym_prior = returns.shift(20).apply(lambda col: tail_asym(col, 20))
    signals["tail_asym_change"] = asym_recent - asym_prior

    # H-1352: Extreme Day Ratio
    vol_30 = returns.rolling(30).std()
    extreme_up = (returns > 2 * vol_30).astype(float)
    extreme_down = (returns < -2 * vol_30).astype(float)
    signals["extreme_day_ratio"] = (extreme_up + extreme_down).rolling(30).mean()

    # H-1353: VaR Breach Rate
    hist_var = returns.rolling(60).quantile(0.05)
    breach = (returns < hist_var).astype(float)
    signals["var_breach_rate"] = breach.rolling(30).mean()

    # H-1354: Expected Shortfall Trend
    def es_rolling(series, window=30, n_worst=5):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            chunk = series.iloc[i-window:i].values
            valid = chunk[np.isfinite(chunk)]
            if len(valid) < n_worst:
                continue
            sorted_rets = np.sort(valid)
            result.iloc[i] = np.mean(sorted_rets[:n_worst])
        return result

    es_recent = returns.apply(lambda col: es_rolling(col, 20, 3))
    es_prior = returns.shift(20).apply(lambda col: es_rolling(col, 20, 3))
    signals["es_trend"] = es_recent - es_prior

    # H-1355: Distribution Width Change (IQR delta)
    iqr_recent = returns.rolling(20).quantile(0.75) - returns.rolling(20).quantile(0.25)
    iqr_prior = returns.shift(20).rolling(20).quantile(0.75) - returns.shift(20).rolling(20).quantile(0.25)
    signals["width_change"] = iqr_recent - iqr_prior

    return signals, closes


def xs_backtest(closes, signal_df, lookback, rebal_days, n_ls, direction="high_long"):
    returns = closes.pct_change()
    slippage = SLIPPAGE_BPS / 10_000
    warmup = lookback + 5
    positions = {}
    days_since = rebal_days
    pnl_daily = []
    for i in range(warmup, len(closes)):
        days_since += 1
        if days_since >= rebal_days:
            sig_row = signal_df.iloc[i - 1].dropna()
            if len(sig_row) < 2 * n_ls:
                pnl_daily.append(0)
                continue
            if direction == "high_long":
                ranked = sig_row.sort_values(ascending=False)
            else:
                ranked = sig_row.sort_values(ascending=True)
            longs = set(ranked.index[:n_ls])
            shorts = set(ranked.index[-n_ls:])
            old_syms = set(positions.keys())
            new_syms = longs | shorts
            changed = old_syms.symmetric_difference(new_syms)
            fee_cost = len(changed) * FEE_RATE / (2 * n_ls)
            slip_cost = len(changed) * slippage / (2 * n_ls)
            positions = {}
            for sym in longs:
                positions[sym] = 1.0 / n_ls
            for sym in shorts:
                positions[sym] = -1.0 / n_ls
            days_since = 0
            daily_ret = -fee_cost - slip_cost
        else:
            daily_ret = 0.0
        for sym, w in positions.items():
            if sym in returns.columns:
                r = returns[sym].iloc[i]
                if np.isfinite(r):
                    daily_ret += w * r
        pnl_daily.append(daily_ret)
    return np.array(pnl_daily)


def compute_sharpe(pnl, ann_factor=365):
    if len(pnl) < 30 or np.std(pnl) == 0:
        return 0
    return np.mean(pnl) / np.std(pnl) * np.sqrt(ann_factor)


def compute_metrics(pnl):
    if len(pnl) < 30:
        return {"sharpe": 0, "annual_ret": 0, "max_dd": 0}
    sharpe = compute_sharpe(pnl)
    cum = np.cumsum(pnl)
    annual_ret = np.mean(pnl) * 365
    running_max = np.maximum.accumulate(cum)
    dd = cum - running_max
    max_dd = np.min(dd) if len(dd) > 0 else 0
    return {"sharpe": round(sharpe, 3), "annual_ret": round(annual_ret * 100, 1),
            "max_dd": round(max_dd * 100, 1)}


def walk_forward(closes, signal_df, lookback, rebal, n_ls, direction,
                 n_folds=5, test_days=120):
    results = []
    for fold in range(n_folds):
        test_end = len(closes) - fold * test_days
        test_start = test_end - test_days
        if test_start < 200 + lookback + 5:
            break
        c_test = closes.iloc[test_start - lookback - 5:test_end]
        s_test = signal_df.iloc[test_start - lookback - 5:test_end]
        pnl = xs_backtest(c_test, s_test, lookback, rebal, n_ls, direction)
        sh = compute_sharpe(pnl)
        results.append(sh)
    return results


def split_half_test(pnl):
    if len(pnl) < 60:
        return 0, 0, 1.0
    t_stat, p_val = scipy_stats.ttest_1samp(pnl, 0)
    mid = len(pnl) // 2
    return compute_sharpe(pnl[:mid]), compute_sharpe(pnl[mid:]), p_val


def h012_correlation(closes, signal_df, lookback, rebal, n_ls, direction):
    pnl_test = xs_backtest(closes, signal_df, lookback, rebal, n_ls, direction)
    ret60 = closes.pct_change(60)
    pnl_h012 = xs_backtest(closes, ret60, 60, 5, 4, "high_long")
    mn = min(len(pnl_test), len(pnl_h012))
    if mn < 30:
        return 0
    return round(np.corrcoef(pnl_test[:mn], pnl_h012[:mn])[0, 1], 3)


def check_degenerate(signal_df, name):
    last_row = signal_df.dropna(how='all').iloc[-1].dropna()
    if len(last_row) < 8:
        return False
    nunique = last_row.nunique()
    if nunique <= 3:
        print(f"  {name}: DEGENERATE — only {nunique} unique values in last row")
        return True
    val_counts = last_row.value_counts()
    if val_counts.iloc[0] >= len(last_row) * 0.5:
        print(f"  {name}: DEGENERATE — {val_counts.iloc[0]}/{len(last_row)} assets have same value")
        return True
    return False


def run_signal(name, signal_df, closes, lookback, directions, n_ls_list=[4],
               rebal_list=[5, 7]):
    common_idx = closes.index.intersection(signal_df.index)
    common_cols = [c for c in closes.columns if c in signal_df.columns]
    if len(common_cols) < 8 or len(common_idx) < 200:
        print(f"  {name}: Insufficient data — SKIP")
        return None
    closes_c = closes[common_cols].loc[common_idx]
    signal_c = signal_df[common_cols].loc[common_idx]
    if check_degenerate(signal_c, name):
        return None
    best = {"sharpe": -999}
    all_positive = 0
    all_total = 0
    for direction in directions:
        for n_ls in n_ls_list:
            for rebal in rebal_list:
                pnl = xs_backtest(closes_c, signal_c, lookback, rebal, n_ls, direction)
                m = compute_metrics(pnl)
                all_total += 1
                if m["sharpe"] > 0:
                    all_positive += 1
                if m["sharpe"] > best.get("sharpe", -999):
                    best = {**m, "direction": direction, "n_ls": n_ls, "rebal": rebal,
                            "pnl": pnl, "closes_c": closes_c, "signal_c": signal_c}
    is_pct = f"{100*all_positive//all_total}%" if all_total > 0 else "N/A"
    if best["sharpe"] <= 0:
        print(f"  {name}: IS {is_pct} ({all_positive}/{all_total} positive) — SKIP")
        return None
    pnl = best["pnl"]
    wf = walk_forward(best["closes_c"], best["signal_c"], lookback, best["rebal"],
                      best["n_ls"], best["direction"])
    sh1, sh2, p_val = split_half_test(pnl)
    corr = h012_correlation(best["closes_c"], best["signal_c"], lookback, best["rebal"],
                            best["n_ls"], best["direction"])
    wf_pos = sum(1 for x in wf if x > 0)
    print(f"  {name}: IS Sharpe {best['sharpe']:.3f} | Ann {best['annual_ret']:.1f}% | DD {best['max_dd']:.1f}% | "
          f"Dir={best['direction']} | IS {is_pct} ({all_positive}/{all_total}) | "
          f"WF {wf_pos}/{len(wf)} {[round(x,2) for x in wf]} | SH {sh1:.3f}/{sh2:.3f} p={p_val:.3f} | "
          f"H012 corr {corr:.3f} | N={len(pnl)}")
    return {
        "sharpe": best["sharpe"], "annual_ret": best["annual_ret"],
        "max_dd": best["max_dd"], "direction": best["direction"],
        "n_ls": best["n_ls"], "rebal": best["rebal"],
        "wf": wf, "wf_pos": wf_pos, "wf_total": len(wf),
        "sh1": sh1, "sh2": sh2, "p_val": round(p_val, 4),
        "h012_corr": corr, "n_bars": len(pnl),
        "is_positive_pct": is_pct
    }


def main():
    print("Loading OHLCV data...")
    opens, highs, lows, closes, volumes = load_daily_ohlcv()
    print(f"Loaded {len(closes)} bars, {len(closes.columns)} assets")
    print()

    print("Computing signals...")
    signals, closes = compute_signals(opens, highs, lows, closes, volumes)
    print(f"Got {len(signals)} signal types")
    print()

    feature_map = {
        "H-1348": ("tail_weight_change", "Tail Weight Change (kurtosis 20d - kurtosis 60d)"),
        "H-1349": ("left_tail_shrink", "Left Tail Shrinkage (p5 change between windows)"),
        "H-1350": ("right_tail_growth", "Right Tail Growth (p95 change between windows)"),
        "H-1351": ("tail_asym_change", "Tail Asymmetry Change (p95/|p5| delta)"),
        "H-1352": ("extreme_day_ratio", "Extreme Day Ratio (days >2sigma in 30d)"),
        "H-1353": ("var_breach_rate", "VaR Breach Rate (historical VaR breach freq, 30d)"),
        "H-1354": ("es_trend", "Expected Shortfall Trend (worst-day avg delta)"),
        "H-1355": ("width_change", "Distribution Width Change (IQR delta)"),
    }

    results = {}
    lookback = 30

    for hyp_id, (sig_name, desc) in feature_map.items():
        print(f"\n{hyp_id}: {desc}")
        sig_df = signals[sig_name]
        r = run_signal(hyp_id, sig_df, closes, lookback,
                       ["high_long", "low_long"], [3, 4], [3, 5, 7])
        if r:
            results[hyp_id] = r

    print(f"\n{'='*80}")
    print(f"BATCH SUMMARY: {len(results)}/{8} signals with positive IS Sharpe")
    for name, r in sorted(results.items(), key=lambda x: -x[1]["sharpe"]):
        status = "CONFIRMED" if r["wf_pos"] >= max(2, r["wf_total"] * 0.5) and r["p_val"] < 0.15 else "BORDERLINE" if r["wf_pos"] >= 2 else "REJECTED"
        print(f"  {name}: Sharpe {r['sharpe']:.3f} | WF {r['wf_pos']}/{r['wf_total']} | p={r['p_val']:.3f} | "
              f"corr {r['h012_corr']:.3f} | SH {r['sh1']:.2f}/{r['sh2']:.2f} | {status}")


if __name__ == "__main__":
    main()
