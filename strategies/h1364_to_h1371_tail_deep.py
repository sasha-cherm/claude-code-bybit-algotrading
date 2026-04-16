"""
Batch backtest: H-1364 to H-1371 — Deep Distributional Tail Variations.
Extending the rich vein from session 210 (4/6 confirmed in H-1348–H-1355).

H-1364: Upper Tail Shrink — p95(recent 20d) - p95(prior 20d) with low_long (contrarian upside compression).
H-1365: Left Tail Grow — p5(recent 20d) - p5(prior 20d) with low_long (more negative = capitulation).
H-1366: Left CVaR Trend — mean bottom 3 of recent 20d minus prior 20d bottom 3.
H-1367: Right CVaR Trend — mean top 3 of recent 20d minus prior 20d top 3.
H-1368: Skewness Change — skew(20d) - skew(60d). Regime shift in asymmetry.
H-1369: Tail Range Asymmetry — (p95-p50 recent) / (p50-p5 recent). Right vs left tail width.
H-1370: Downside Semi-Std Change — std of negative returns, recent 20d vs prior 20d.
H-1371: Upside Semi-Std Change — std of positive returns, recent 20d vs prior 20d.
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
    closes = pd.DataFrame(closes).loc[idx]
    volumes = pd.DataFrame(volumes).loc[idx]
    return closes, volumes


def compute_signals(closes, volumes):
    returns = closes.pct_change()
    signals = {}

    # H-1364: Upper Tail Shrink
    p95_recent = returns.rolling(20).quantile(0.95)
    p95_prior = returns.shift(20).rolling(20).quantile(0.95)
    signals["upper_tail_shrink"] = p95_recent - p95_prior

    # H-1365: Left Tail Grow (more negative)
    p5_recent = returns.rolling(20).quantile(0.05)
    p5_prior = returns.shift(20).rolling(20).quantile(0.05)
    signals["left_tail_grow"] = p5_recent - p5_prior

    # H-1366/H-1367: CVaR trends (mean of extreme k returns in window)
    def cvar_rolling(series, window=20, n_k=3, tail="left"):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            chunk = series.iloc[i-window:i].values
            valid = chunk[np.isfinite(chunk)]
            if len(valid) < n_k:
                continue
            sorted_rets = np.sort(valid)
            if tail == "left":
                result.iloc[i] = np.mean(sorted_rets[:n_k])
            else:
                result.iloc[i] = np.mean(sorted_rets[-n_k:])
        return result

    left_cvar_r = returns.apply(lambda col: cvar_rolling(col, 20, 3, "left"))
    left_cvar_p = returns.shift(20).apply(lambda col: cvar_rolling(col, 20, 3, "left"))
    signals["left_cvar_trend"] = left_cvar_r - left_cvar_p

    right_cvar_r = returns.apply(lambda col: cvar_rolling(col, 20, 3, "right"))
    right_cvar_p = returns.shift(20).apply(lambda col: cvar_rolling(col, 20, 3, "right"))
    signals["right_cvar_trend"] = right_cvar_r - right_cvar_p

    # H-1368: Skewness Change (20d skew - 60d skew)
    skew_20 = returns.rolling(20).apply(lambda x: scipy_stats.skew(x), raw=True)
    skew_60 = returns.rolling(60).apply(lambda x: scipy_stats.skew(x), raw=True)
    signals["skew_change"] = skew_20 - skew_60

    # H-1369: Tail Range Asymmetry — (p95 - p50) / (p50 - p5)
    p50_r = returns.rolling(30).quantile(0.50)
    p95_r = returns.rolling(30).quantile(0.95)
    p5_r = returns.rolling(30).quantile(0.05)
    upper_range = p95_r - p50_r
    lower_range = p50_r - p5_r
    signals["tail_range_asym"] = upper_range / lower_range.replace(0, np.nan).abs()

    # H-1370: Downside Semi-Std Change
    def semi_std(series, window, side="down"):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            chunk = series.iloc[i-window:i].values
            valid = chunk[np.isfinite(chunk)]
            if side == "down":
                filt = valid[valid < 0]
            else:
                filt = valid[valid > 0]
            if len(filt) < 3:
                continue
            result.iloc[i] = np.std(filt)
        return result

    d_recent = returns.apply(lambda col: semi_std(col, 20, "down"))
    d_prior = returns.shift(20).apply(lambda col: semi_std(col, 20, "down"))
    signals["downside_std_change"] = d_recent - d_prior

    # H-1371: Upside Semi-Std Change
    u_recent = returns.apply(lambda col: semi_std(col, 20, "up"))
    u_prior = returns.shift(20).apply(lambda col: semi_std(col, 20, "up"))
    signals["upside_std_change"] = u_recent - u_prior

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
    closes, volumes = load_daily_ohlcv()
    print(f"Loaded {len(closes)} bars, {len(closes.columns)} assets")
    print()

    print("Computing signals...")
    signals, closes = compute_signals(closes, volumes)
    print(f"Got {len(signals)} signal types")
    print()

    feature_map = {
        "H-1364": ("upper_tail_shrink", "Upper Tail Shrink (p95 delta)"),
        "H-1365": ("left_tail_grow", "Left Tail Grow (p5 delta)"),
        "H-1366": ("left_cvar_trend", "Left CVaR Trend (bottom3 delta)"),
        "H-1367": ("right_cvar_trend", "Right CVaR Trend (top3 delta)"),
        "H-1368": ("skew_change", "Skewness Change (skew20 - skew60)"),
        "H-1369": ("tail_range_asym", "Tail Range Asymmetry (p95-p50)/(p50-p5)"),
        "H-1370": ("downside_std_change", "Downside Semi-Std Change"),
        "H-1371": ("upside_std_change", "Upside Semi-Std Change"),
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
