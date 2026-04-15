"""
Batch backtest: H-1332 to H-1339 — Price & Momentum Quality Signals.
Deeper decomposition of price action quality and consistency for XS ranking.

H-1332: Trend Strength — abs(close - close[20]) / sum(abs(daily returns)) over 20d. Efficiency of price movement (similar to fractal efficiency).
H-1333: Positive Return Concentration — Gini coefficient of positive daily returns in 20d. Concentrated vs distributed gains.
H-1334: Drawdown Recovery Speed — avg bars to recover from intraperiod dips in 30d. Fast recovery = strong buying pressure.
H-1335: Consecutive Candle Momentum — max consecutive green candles in 20d. Strong bullish persistence.
H-1336: Return Smoothness Ratio — std of rolling 5d returns / std of daily returns. Smooth trends vs choppy.
H-1337: Close vs VWAP — daily close / VWAP proxy (dollar vol weighted avg price). Consistently above = buying pressure.
H-1338: Tail Ratio — 95th percentile / abs(5th percentile) of returns in 30d. Upside vs downside extremes.
H-1339: Intraday Reversal Frequency — fraction of days where (close-open) has opposite sign to (open-prev_close) in 20d. Gap reversal tendency.
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

    # H-1332: Trend Strength (Fractal Efficiency)
    net_move = (closes - closes.shift(20)).abs()
    abs_daily = returns.abs().rolling(20).sum()
    signals["trend_strength"] = net_move / (abs_daily * closes.shift(20)).replace(0, np.nan)

    # H-1333: Positive Return Concentration (Gini of positive returns)
    def gini_positive(series, window=20):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            chunk = series.iloc[i-window:i].values
            pos = chunk[chunk > 0]
            if len(pos) < 2:
                result.iloc[i] = 0
                continue
            pos = np.sort(pos)
            n = len(pos)
            idx_arr = np.arange(1, n + 1)
            result.iloc[i] = (2 * np.sum(idx_arr * pos) / (n * np.sum(pos))) - (n + 1) / n
        return result

    signals["pos_ret_gini"] = returns.apply(lambda col: gini_positive(col, 20))

    # H-1334: Drawdown Recovery Speed
    def dd_recovery_speed(series, window=30):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            chunk = series.iloc[i-window:i].values
            cum = np.cumsum(chunk)
            running_max = np.maximum.accumulate(cum)
            dd = cum - running_max
            in_dd = dd < -0.001
            if not np.any(in_dd):
                result.iloc[i] = window
                continue
            recovery_times = []
            start = None
            for j in range(len(dd)):
                if dd[j] < -0.001 and start is None:
                    start = j
                elif dd[j] >= -0.001 and start is not None:
                    recovery_times.append(j - start)
                    start = None
            if start is not None:
                recovery_times.append(len(dd) - start)
            result.iloc[i] = np.mean(recovery_times) if recovery_times else window
        return result

    signals["dd_recovery_speed"] = returns.apply(lambda col: dd_recovery_speed(col, 30))

    # H-1335: Consecutive Candle Momentum — max consec green
    def max_consec_green(series, window=20):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            chunk = series.iloc[i-window:i].values
            green = (chunk > 0).astype(int)
            max_run = 0
            current = 0
            for g in green:
                if g:
                    current += 1
                    max_run = max(max_run, current)
                else:
                    current = 0
            result.iloc[i] = max_run
        return result

    signals["consec_green"] = returns.apply(lambda col: max_consec_green(col, 20))

    # H-1336: Return Smoothness Ratio
    roll5_ret = closes.pct_change(5)
    roll5_std = roll5_ret.rolling(20).std()
    daily_std = returns.rolling(20).std()
    signals["return_smoothness"] = roll5_std / (daily_std * np.sqrt(5)).replace(0, np.nan)

    # H-1337: Close vs VWAP proxy
    vwap_proxy = (closes * volumes).rolling(20).sum() / volumes.rolling(20).sum().replace(0, np.nan)
    signals["close_vs_vwap"] = closes / vwap_proxy

    # H-1338: Tail Ratio
    def tail_ratio(series, window=30):
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

    signals["tail_ratio"] = returns.apply(lambda col: tail_ratio(col, 30))

    # H-1339: Intraday Reversal Frequency
    gap = opens - closes.shift(1)
    body = closes - opens
    gap_sign = np.sign(gap)
    body_sign = np.sign(body)
    reversal = ((gap_sign != 0) & (gap_sign == -body_sign)).astype(float)
    signals["intraday_reversal_freq"] = reversal.rolling(20).mean()

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


def run_signal(name, signal_df, closes, lookback, directions, n_ls_list=[4],
               rebal_list=[5, 7]):
    common_idx = closes.index.intersection(signal_df.index)
    common_cols = [c for c in closes.columns if c in signal_df.columns]
    if len(common_cols) < 8 or len(common_idx) < 200:
        print(f"  {name}: Insufficient data — SKIP")
        return None
    closes_c = closes[common_cols].loc[common_idx]
    signal_c = signal_df[common_cols].loc[common_idx]
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
        "H-1332": ("trend_strength", "Trend Strength (net move / path length, 20d)"),
        "H-1333": ("pos_ret_gini", "Positive Return Concentration (Gini of positive rets, 20d)"),
        "H-1334": ("dd_recovery_speed", "Drawdown Recovery Speed (avg recovery bars, 30d)"),
        "H-1335": ("consec_green", "Consecutive Candle Momentum (max consec green, 20d)"),
        "H-1336": ("return_smoothness", "Return Smoothness Ratio (5d std / sqrt5*1d std, 20d)"),
        "H-1337": ("close_vs_vwap", "Close vs VWAP (close / 20d VWAP proxy)"),
        "H-1338": ("tail_ratio", "Tail Ratio (p95 / |p5| of returns, 30d)"),
        "H-1339": ("intraday_reversal_freq", "Intraday Reversal Frequency (gap-reversal rate, 20d)"),
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
