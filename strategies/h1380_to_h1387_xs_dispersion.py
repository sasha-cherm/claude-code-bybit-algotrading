"""
Batch backtest: H-1380 to H-1387 — Cross-Sectional Dispersion & Relative Dynamics.
Signals capturing an asset's behavior vs the cross-section.

H-1380: XS Z-Score Momentum — asset's return rank normalized by XS std (z-score of 10d return).
H-1381: Peer Deviation — asset return deviation from XS mean over 30d (mean abs dev).
H-1382: XS Rank Trend — slope of asset's XS-rank percentile over 30d.
H-1383: Outperformance Consistency — fraction of days where asset return > XS median over 30d.
H-1384: Relative Vol Spread — asset 20d vol / XS-median 20d vol.
H-1385: Cross-Section Correlation — avg correlation of asset with XS over 60d (concentration).
H-1386: Beta to XS Mean — rolling 60d regression of asset return on XS-mean return.
H-1387: XS Surprise — (asset 5d return - XS median 5d return) normalized by asset vol.
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
    closes, volumes = {}, {}
    for sym, df in frames.items():
        closes[sym] = df["close"]
        volumes[sym] = df["volume"] * df["close"]
    idx = sorted(set.intersection(*[set(df.index) for df in frames.values()]))
    closes = pd.DataFrame(closes).loc[idx]
    volumes = pd.DataFrame(volumes).loc[idx]
    return closes, volumes


def compute_signals(closes, volumes):
    returns = closes.pct_change()
    signals = {}

    # H-1380: XS Z-Score Momentum (10d return normalized by XS std each day)
    ret_10 = closes.pct_change(10)
    xs_mean = ret_10.mean(axis=1)
    xs_std = ret_10.std(axis=1).replace(0, np.nan)
    signals["xs_zscore_mom"] = ret_10.sub(xs_mean, axis=0).div(xs_std, axis=0)

    # H-1381: Peer Deviation — mean abs dev of asset vs XS mean over 30d
    xs_mean_daily = returns.mean(axis=1)
    dev = returns.sub(xs_mean_daily, axis=0).abs()
    signals["peer_deviation"] = dev.rolling(30).mean()

    # H-1382: XS Rank Trend — slope of asset's rank percentile over 30d
    rank_pct = returns.rolling(10).sum().rank(axis=1, pct=True)
    def slope_30(series):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(30, len(series)):
            chunk = series.iloc[i-30:i].values
            valid = chunk[np.isfinite(chunk)]
            if len(valid) < 20:
                continue
            x = np.arange(len(valid))
            result.iloc[i] = np.polyfit(x, valid, 1)[0]
        return result

    signals["xs_rank_trend"] = rank_pct.apply(slope_30)

    # H-1383: Outperformance Consistency — frac days asset > XS median, 30d
    xs_median_daily = returns.median(axis=1)
    outperf = returns.gt(xs_median_daily, axis=0).astype(float)
    signals["outperf_consistency"] = outperf.rolling(30).mean()

    # H-1384: Relative Vol Spread — asset 20d vol / XS-median 20d vol
    vol_20 = returns.rolling(20).std()
    xs_vol_median = vol_20.median(axis=1)
    signals["rel_vol_spread"] = vol_20.div(xs_vol_median, axis=0)

    # H-1385: Cross-Section Correlation — avg pairwise corr over 60d
    def avg_corr_with_xs(asset_col, all_cols, window=60):
        result = pd.Series(index=asset_col.index, dtype=float)
        for i in range(window, len(asset_col)):
            chunk_asset = asset_col.iloc[i-window:i].values
            if np.sum(np.isfinite(chunk_asset)) < window * 0.8:
                continue
            corrs = []
            for j, other_col in enumerate(all_cols):
                if other_col is asset_col.name:
                    continue
                chunk_other = all_cols[other_col].iloc[i-window:i].values
                mask = np.isfinite(chunk_asset) & np.isfinite(chunk_other)
                if np.sum(mask) < window * 0.7:
                    continue
                if np.std(chunk_asset[mask]) > 0 and np.std(chunk_other[mask]) > 0:
                    corrs.append(np.corrcoef(chunk_asset[mask], chunk_other[mask])[0, 1])
            if len(corrs) >= 3:
                result.iloc[i] = np.mean(corrs)
        return result

    xs_corr_sig = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=float)
    for col in returns.columns:
        xs_corr_sig[col] = avg_corr_with_xs(returns[col], returns, 60)
    signals["xs_correlation"] = xs_corr_sig

    # H-1386: Beta to XS Mean (rolling 60d)
    xs_mean_d = returns.mean(axis=1)
    def beta_to(series, xs_series, window=60):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            y = series.iloc[i-window:i].values
            x = xs_series.iloc[i-window:i].values
            mask = np.isfinite(y) & np.isfinite(x)
            if np.sum(mask) < window * 0.8:
                continue
            if np.var(x[mask]) > 0:
                result.iloc[i] = np.cov(y[mask], x[mask])[0, 1] / np.var(x[mask])
        return result

    beta_sig = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=float)
    for col in returns.columns:
        beta_sig[col] = beta_to(returns[col], xs_mean_d, 60)
    signals["beta_xs"] = beta_sig

    # H-1387: XS Surprise — (asset 5d - XS median 5d) / asset vol 20d
    ret_5 = closes.pct_change(5)
    xs_median_5 = ret_5.median(axis=1)
    diff = ret_5.sub(xs_median_5, axis=0)
    asset_vol = returns.rolling(20).std().replace(0, np.nan) * np.sqrt(5)
    signals["xs_surprise"] = diff / asset_vol

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
        "H-1380": ("xs_zscore_mom", "XS Z-Score Momentum (10d ret z-score)"),
        "H-1381": ("peer_deviation", "Peer Deviation (mean abs dev vs XS mean, 30d)"),
        "H-1382": ("xs_rank_trend", "XS Rank Trend (slope of rank percentile, 30d)"),
        "H-1383": ("outperf_consistency", "Outperformance Consistency (frac > XS median, 30d)"),
        "H-1384": ("rel_vol_spread", "Relative Vol Spread (asset vol / XS median vol)"),
        "H-1385": ("xs_correlation", "Cross-Section Correlation (avg pairwise, 60d)"),
        "H-1386": ("beta_xs", "Beta to XS Mean (rolling 60d)"),
        "H-1387": ("xs_surprise", "XS Surprise (5d deviation normalized)"),
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
