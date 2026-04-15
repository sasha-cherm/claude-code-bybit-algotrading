"""
Batch backtest: H-1252 to H-1259 — Intraday OHLCV Cross-Sectional Signals.
Cross-sectional signals derived from full OHLCV bars (not just close prices).

H-1252: Relative Intraday Range — (high-low)/close, 10d vs 30d ratio. Range expansion.
H-1253: Close Position — (close-low)/(high-low) averaged 20d. Bullish close bias.
H-1254: Body-to-Shadow Ratio — abs(close-open)/(high-low) averaged 20d. Directional conviction.
H-1255: Upper Shadow Dominance — (high-max(open,close))/(high-low) averaged 20d. Selling pressure.
H-1256: Gap Frequency — abs(open-prev_close)/prev_close, mean 20d. Overnight info arrival.
H-1257: True Range Trend — 10d ATR / 30d ATR. Expanding vs contracting ranges.
H-1258: Candle Direction Consistency — fraction of days where close > open in 20d. Bullish candle freq.
H-1259: High-Low Asymmetry — (high-close)/(close-low+1e-10), log, averaged 20d. Wick imbalance.
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
    returns = closes.pct_change()
    signals = {}
    hl_range = (highs - lows) / closes

    # H-1252: Relative Intraday Range — 10d avg range / 30d avg range
    range_10 = hl_range.rolling(10).mean()
    range_30 = hl_range.rolling(30).mean()
    signals["rel_intraday_range"] = range_10 / (range_30 + 1e-10)

    # H-1253: Close Position — (close - low) / (high - low), averaged 20d
    denom = (highs - lows).replace(0, np.nan)
    close_pos = (closes - lows) / denom
    signals["close_position"] = close_pos.rolling(20).mean()

    # H-1254: Body-to-Shadow Ratio — abs(close-open) / (high-low), averaged 20d
    body = (closes - opens).abs()
    body_ratio = body / denom
    signals["body_shadow_ratio"] = body_ratio.rolling(20).mean()

    # H-1255: Upper Shadow Dominance — (high - max(open,close)) / (high-low), averaged 20d
    upper_body = pd.DataFrame(np.maximum(opens.values, closes.values),
                              index=opens.index, columns=opens.columns)
    upper_shadow = (highs - upper_body) / denom
    signals["upper_shadow_dom"] = upper_shadow.rolling(20).mean()

    # H-1256: Gap Frequency — abs(open - prev_close) / prev_close, mean 20d
    prev_close = closes.shift(1)
    gap = (opens - prev_close).abs() / (prev_close + 1e-10)
    signals["gap_freq"] = gap.rolling(20).mean()

    # H-1257: True Range Trend — 10d ATR / 30d ATR
    tr1 = highs - lows
    tr2 = (highs - closes.shift(1)).abs()
    tr3 = (lows - closes.shift(1)).abs()
    true_range = pd.DataFrame(np.maximum(tr1.values, np.maximum(tr2.values, tr3.values)),
                              index=closes.index, columns=closes.columns)
    atr_10 = true_range.rolling(10).mean()
    atr_30 = true_range.rolling(30).mean()
    signals["tr_trend"] = atr_10 / (atr_30 + 1e-10)

    # H-1258: Candle Direction Consistency — frac of close > open days in 20d
    bullish = (closes > opens).astype(float)
    signals["candle_direction"] = bullish.rolling(20).mean()

    # H-1259: High-Low Asymmetry — log((high-close)/(close-low+eps)), averaged 20d
    upper_wick = highs - closes
    lower_wick = closes - lows
    wick_ratio = np.log((upper_wick + 1e-10) / (lower_wick + 1e-10))
    signals["hl_asymmetry"] = wick_ratio.rolling(20).mean()

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
        "H-1252": ("rel_intraday_range", "Relative Intraday Range (10d/30d range ratio)"),
        "H-1253": ("close_position", "Close Position ((close-low)/(high-low), 20d avg)"),
        "H-1254": ("body_shadow_ratio", "Body-to-Shadow Ratio (body/(high-low), 20d avg)"),
        "H-1255": ("upper_shadow_dom", "Upper Shadow Dominance (upper wick fraction, 20d avg)"),
        "H-1256": ("gap_freq", "Gap Frequency (abs(open-prev_close)/close, 20d avg)"),
        "H-1257": ("tr_trend", "True Range Trend (ATR10/ATR30)"),
        "H-1258": ("candle_direction", "Candle Direction Consistency (frac bullish candles, 20d)"),
        "H-1259": ("hl_asymmetry", "High-Low Asymmetry (log upper/lower wick, 20d avg)"),
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
