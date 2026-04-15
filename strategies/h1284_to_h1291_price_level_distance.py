"""
Batch backtest: H-1284 to H-1291 — Price Level & Distance Signals.
How far price is from key reference levels as cross-sectional signals.

H-1284: Distance from N-day High — (close - high_60d) / high_60d. Proximity to recent peak.
H-1285: Distance from N-day Low — (close - low_60d) / low_60d. Bounce from recent trough.
H-1286: High-Low Range Relative — (high_20d - low_20d) / close. Recent price range width.
H-1287: Days Since High — count of days since 60d highest close. Momentum recency.
H-1288: Price vs VWAP — (close - vwap_20d) / vwap_20d. Price vs volume-weighted fair value.
H-1289: Consecutive Higher Closes — max streak of close > prev_close in last 20d. Trend quality.
H-1290: Mean Distance — abs(close - mean_20d) / std_20d. How far from equilibrium.
H-1291: Trend Consistency Score — R² of linear regression fit on log(close) over 20d.
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

    # H-1284: Distance from 60d High
    high_60 = closes.rolling(60).max()
    signals["dist_from_high"] = (closes - high_60) / (high_60 + 1e-10)

    # H-1285: Distance from 60d Low
    low_60 = closes.rolling(60).min()
    signals["dist_from_low"] = (closes - low_60) / (low_60 + 1e-10)

    # H-1286: High-Low Range Relative — (high_20d - low_20d) / close
    high_20 = closes.rolling(20).max()
    low_20 = closes.rolling(20).min()
    signals["hl_range_rel"] = (high_20 - low_20) / (closes + 1e-10)

    # H-1287: Days Since High — how many days since the 60d max close
    def days_since_max(series, window=60):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            window_data = series.iloc[i-window+1:i+1]
            idx_max = window_data.values.argmax()
            result.iloc[i] = window - 1 - idx_max
        return result

    days_since = closes.apply(lambda col: days_since_max(col, 60))
    signals["days_since_high"] = days_since

    # H-1288: Price vs VWAP — 20d VWAP
    dollar_vol = closes * volumes  # already dollar vol in volumes
    cum_dv_20 = dollar_vol.rolling(20).sum()
    cum_v_20 = volumes.rolling(20).sum()
    vwap_20 = cum_dv_20 / (cum_v_20 + 1e-10)
    signals["price_vs_vwap"] = (closes - vwap_20) / (vwap_20 + 1e-10)

    # H-1289: Consecutive Higher Closes — max streak in 20d
    def max_up_streak(series, window=20):
        result = pd.Series(index=series.index, dtype=float)
        up = (series > series.shift(1)).astype(int)
        for i in range(window, len(series)):
            window_data = up.iloc[i-window+1:i+1].values
            max_streak = 0
            current = 0
            for v in window_data:
                if v == 1:
                    current += 1
                    max_streak = max(max_streak, current)
                else:
                    current = 0
            result.iloc[i] = max_streak
        return result

    signals["consec_higher"] = closes.apply(lambda col: max_up_streak(col, 20))

    # H-1290: Mean Distance — abs(close - mean) / std
    mean_20 = closes.rolling(20).mean()
    std_20 = closes.rolling(20).std()
    signals["mean_distance"] = (closes - mean_20).abs() / (std_20 + 1e-10)

    # H-1291: Trend Consistency Score — R² of linear regression on log(close) over 20d
    def rolling_r2(series, window=20):
        result = pd.Series(index=series.index, dtype=float)
        log_s = np.log(series + 1e-10)
        x = np.arange(window)
        for i in range(window, len(series)):
            y = log_s.iloc[i-window+1:i+1].values
            if np.any(~np.isfinite(y)):
                result.iloc[i] = np.nan
                continue
            slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, y)
            result.iloc[i] = r_value ** 2
        return result

    signals["trend_r2"] = closes.apply(lambda col: rolling_r2(col, 20))

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
        "H-1284": ("dist_from_high", "Distance from 60d High ((close-high60)/high60)"),
        "H-1285": ("dist_from_low", "Distance from 60d Low ((close-low60)/low60)"),
        "H-1286": ("hl_range_rel", "High-Low Range Relative ((high20-low20)/close)"),
        "H-1287": ("days_since_high", "Days Since 60d High (count of days since max)"),
        "H-1288": ("price_vs_vwap", "Price vs VWAP 20d ((close-vwap)/vwap)"),
        "H-1289": ("consec_higher", "Consecutive Higher Closes (max streak in 20d)"),
        "H-1290": ("mean_distance", "Mean Distance (abs(close-mean)/std, 20d)"),
        "H-1291": ("trend_r2", "Trend Consistency R² (linreg R² on log close, 20d)"),
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
