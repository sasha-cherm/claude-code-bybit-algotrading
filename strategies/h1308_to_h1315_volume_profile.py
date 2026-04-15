"""
Batch backtest: H-1308 to H-1315 — Volume Profile Signals.
Volume-derived structural features for cross-sectional ranking.

H-1308: Volume Trend Slope — slope of linear regression on log(volume) over 20d. Rising/falling interest.
H-1309: Volume Concentration — max single-day volume / sum over 20d. How concentrated/distributed volume is.
H-1310: Relative Volume Rank Stability — std of daily volume rank across assets over 20d. Consistent liquidity.
H-1311: Volume-Return Decoupling — 1 - abs(corr(ret, vol)) over 20d. Low coupling = institutional flow.
H-1312: Abnormal Volume Frequency — fraction of days with volume > 2x 60d avg in last 20d. Attention spikes.
H-1313: Volume Momentum Persistence — autocorr of volume changes over 20d. Volume trending behavior.
H-1314: High-Volume Return Sign — avg return on top-5-volume days in 20d. Directional bias of active days.
H-1315: Volume Entropy — Shannon entropy of volume distribution (discretized into 5 bins) over 20d. How evenly distributed volume is.
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

    # H-1308: Volume Trend Slope — linear regression slope on log(volume)
    log_vol = np.log(volumes + 1)
    def rolling_slope(series, window=20):
        result = pd.Series(index=series.index, dtype=float)
        x = np.arange(window)
        for i in range(window, len(series)):
            y = series.iloc[i-window:i].values
            if np.any(~np.isfinite(y)):
                result.iloc[i] = np.nan
                continue
            slope, _, _, _, _ = scipy_stats.linregress(x, y)
            result.iloc[i] = slope
        return result

    signals["vol_trend_slope"] = log_vol.apply(lambda col: rolling_slope(col, 20))

    # H-1309: Volume Concentration — max single day / sum
    def vol_concentration(series, window=20):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            chunk = series.iloc[i-window:i].values
            s = np.sum(chunk)
            if s <= 0:
                result.iloc[i] = np.nan
                continue
            result.iloc[i] = np.max(chunk) / s
        return result

    signals["vol_concentration"] = volumes.apply(lambda col: vol_concentration(col, 20))

    # H-1310: Volume Rank Stability — std of daily rank
    def rank_stability(df, window=20):
        result = pd.DataFrame(index=df.index, columns=df.columns, dtype=float)
        for i in range(window, len(df)):
            chunk = df.iloc[i-window:i]
            ranks = chunk.rank(axis=1)
            result.iloc[i] = ranks.std()
        return result

    signals["vol_rank_stability"] = rank_stability(volumes, 20)

    # H-1311: Volume-Return Decoupling
    def vol_ret_decoupling(ret_series, vol_series, window=20):
        result = pd.Series(index=ret_series.index, dtype=float)
        for i in range(window, len(ret_series)):
            r = ret_series.iloc[i-window:i].values
            v = vol_series.iloc[i-window:i].values
            if np.std(r) < 1e-15 or np.std(v) < 1e-15:
                result.iloc[i] = 1.0
                continue
            c = np.corrcoef(r, v)[0, 1]
            result.iloc[i] = 1 - abs(c)
        return result

    decoupling = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=float)
    for col in returns.columns:
        if col in volumes.columns:
            decoupling[col] = vol_ret_decoupling(returns[col], volumes[col], 20)
    signals["vol_ret_decouple"] = decoupling

    # H-1312: Abnormal Volume Frequency — fraction of days > 2x 60d avg
    vol_ma60 = volumes.rolling(60).mean()
    abnormal = (volumes > 2 * vol_ma60).astype(float)
    signals["abnormal_vol_freq"] = abnormal.rolling(20).mean()

    # H-1313: Volume Momentum Persistence — autocorr of volume changes
    vol_chg = volumes.pct_change()
    def rolling_acf1(series, window=20):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window + 1, len(series)):
            x = series.iloc[i-window:i].values
            x_lag = series.iloc[i-window-1:i-1].values
            valid = np.isfinite(x) & np.isfinite(x_lag)
            if np.sum(valid) < 10:
                result.iloc[i] = 0
                continue
            if np.std(x[valid]) < 1e-15 or np.std(x_lag[valid]) < 1e-15:
                result.iloc[i] = 0
                continue
            result.iloc[i] = np.corrcoef(x[valid], x_lag[valid])[0, 1]
        return result

    signals["vol_mom_persist"] = vol_chg.apply(lambda col: rolling_acf1(col, 20))

    # H-1314: High-Volume Return Sign — avg return on top-5-vol days in 20d
    def high_vol_return(ret_series, vol_series, window=20, top_k=5):
        result = pd.Series(index=ret_series.index, dtype=float)
        for i in range(window, len(ret_series)):
            r = ret_series.iloc[i-window:i].values
            v = vol_series.iloc[i-window:i].values
            top_idx = np.argsort(v)[-top_k:]
            result.iloc[i] = np.mean(r[top_idx])
        return result

    hv_ret = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=float)
    for col in returns.columns:
        if col in volumes.columns:
            hv_ret[col] = high_vol_return(returns[col], volumes[col], 20, 5)
    signals["high_vol_ret_sign"] = hv_ret

    # H-1315: Volume Entropy — Shannon entropy of volume distribution
    def vol_entropy(series, window=20, n_bins=5):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            chunk = series.iloc[i-window:i].values
            if np.any(~np.isfinite(chunk)) or np.max(chunk) <= np.min(chunk):
                result.iloc[i] = np.nan
                continue
            hist, _ = np.histogram(chunk, bins=n_bins)
            p = hist / np.sum(hist)
            p = p[p > 0]
            result.iloc[i] = -np.sum(p * np.log2(p))
        return result

    signals["vol_entropy"] = volumes.apply(lambda col: vol_entropy(col, 20, 5))

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
        "H-1308": ("vol_trend_slope", "Volume Trend Slope (linreg slope on log vol, 20d)"),
        "H-1309": ("vol_concentration", "Volume Concentration (max day / sum, 20d)"),
        "H-1310": ("vol_rank_stability", "Volume Rank Stability (std of daily rank, 20d)"),
        "H-1311": ("vol_ret_decouple", "Volume-Return Decoupling (1-|corr|, 20d)"),
        "H-1312": ("abnormal_vol_freq", "Abnormal Volume Frequency (>2x avg, 20d)"),
        "H-1313": ("vol_mom_persist", "Volume Momentum Persistence (autocorr vol chg, 20d)"),
        "H-1314": ("high_vol_ret_sign", "High-Volume Return Sign (avg ret on top-5-vol days)"),
        "H-1315": ("vol_entropy", "Volume Entropy (Shannon entropy, 20d, 5 bins)"),
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
