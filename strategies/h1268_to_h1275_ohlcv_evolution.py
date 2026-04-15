"""
Batch backtest: H-1268 to H-1275 — OHLCV Pattern Evolution Signals.
Deeper mining of OHLCV patterns, building on session 206's best-ever batch.

H-1268: Close Position Change — change in (close-low)/(high-low) avg: 10d vs 20d. Improving close position.
H-1269: Gap Direction Persistence — signed gap (open-prev_close)/prev_close avg 20d. Directional gap bias.
H-1270: Range Contraction Streak — count of days range < prev range in 20d. Compression = breakout pending.
H-1271: Open-to-Close Drift — (close-open)/open avg 20d. Intraday directional drift.
H-1272: Lower Shadow Recovery — (close-low)/(high-low) on red candles only, 20d avg. Buying dip strength.
H-1273: Wick Ratio Trend — 10d avg wick ratio / 20d avg wick ratio. Changing indecision.
H-1274: Intraday Reversal Frequency — count of days where open>close but close>prev_close or vice versa in 20d.
H-1275: Range Position — (close - low_20d) / (high_20d - low_20d). Price position in recent range.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

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
    signals = {}
    denom = (highs - lows).replace(0, np.nan)

    # H-1268: Close Position Change — 10d avg minus 20d avg of (close-low)/(high-low)
    close_pos = (closes - lows) / denom
    cp_10 = close_pos.rolling(10).mean()
    cp_20 = close_pos.rolling(20).mean()
    signals["close_pos_change"] = cp_10 - cp_20

    # H-1269: Gap Direction Persistence — signed gap avg over 20d
    prev_close = closes.shift(1)
    signed_gap = (opens - prev_close) / (prev_close + 1e-10)
    signals["gap_dir_persist"] = signed_gap.rolling(20).mean()

    # H-1270: Range Contraction Streak — fraction of days where range < prev range in 20d
    daily_range = highs - lows
    contracting = (daily_range < daily_range.shift(1)).astype(float)
    signals["range_contraction"] = contracting.rolling(20).mean()

    # H-1271: Open-to-Close Drift — (close-open)/open avg 20d
    oc_drift = (closes - opens) / (opens + 1e-10)
    signals["oc_drift"] = oc_drift.rolling(20).mean()

    # H-1272: Lower Shadow Recovery — (close-low)/(high-low) on red candles only, 20d avg
    is_red = (closes < opens).astype(float)
    red_close_pos = close_pos * is_red
    red_count = is_red.rolling(20).sum().replace(0, np.nan)
    signals["lower_shadow_recovery"] = red_close_pos.rolling(20).sum() / red_count

    # H-1273: Wick Ratio Trend — 10d avg wick ratio / 20d avg wick ratio
    upper_wick = highs - pd.DataFrame(np.maximum(opens.values, closes.values),
                                       index=opens.index, columns=opens.columns)
    lower_wick = pd.DataFrame(np.minimum(opens.values, closes.values),
                               index=opens.index, columns=opens.columns) - lows
    total_wick = upper_wick + lower_wick
    body = (closes - opens).abs()
    wick_ratio = total_wick / (body + 1e-10)
    wr_10 = wick_ratio.rolling(10).mean()
    wr_20 = wick_ratio.rolling(20).mean()
    signals["wick_ratio_trend"] = wr_10 / (wr_20 + 1e-10)

    # H-1274: Intraday Reversal Frequency — days with intraday reversal (open>close but close>prev_close or vice versa) in 20d
    prev_c = closes.shift(1)
    reversal = ((opens > closes) & (closes > prev_c)) | ((opens < closes) & (closes < prev_c))
    signals["intraday_reversal_freq"] = reversal.astype(float).rolling(20).mean()

    # H-1275: Range Position — (close - rolling_low_20) / (rolling_high_20 - rolling_low_20)
    rolling_high = closes.rolling(20).max()
    rolling_low = closes.rolling(20).min()
    range_denom = (rolling_high - rolling_low).replace(0, np.nan)
    signals["range_position"] = (closes - rolling_low) / range_denom

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
            sig_row = signal_df.iloc[i - 1]
            sig_row = sig_row.dropna()
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
    t_stat, p_val = stats.ttest_1samp(pnl, 0)
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
        "H-1268": ("close_pos_change", "Close Position Change (10d vs 20d close position diff)"),
        "H-1269": ("gap_dir_persist", "Gap Direction Persistence (signed gap avg 20d)"),
        "H-1270": ("range_contraction", "Range Contraction Streak (frac days range < prev, 20d)"),
        "H-1271": ("oc_drift", "Open-to-Close Drift ((close-open)/open avg 20d)"),
        "H-1272": ("lower_shadow_recovery", "Lower Shadow Recovery (close pos on red candles, 20d)"),
        "H-1273": ("wick_ratio_trend", "Wick Ratio Trend (10d/20d wick ratio change)"),
        "H-1274": ("intraday_reversal_freq", "Intraday Reversal Frequency (reversal days/20d)"),
        "H-1275": ("range_position", "Range Position ((close-low20)/(high20-low20))"),
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
