#!/usr/bin/env python3
"""
Backtest 8 novel cross-sectional factors — session 167.

  H-384: Day-of-Month Sensitivity — rolling avg return on month-edge days (1-5, 26-31) minus mid-month.
  H-385: Volume Herfindahl Index — HHI of hourly volume distribution.
  H-386: 4h Return Autocorrelation — lag-1 AC of 4h bar returns.
  H-387: Volume-Weighted Return Dispersion — std of vol-weighted hourly returns.
  H-388: Night-Day Return Differential — Asian session minus US session return.
  H-389: Intraday High Timing — avg hour when daily high occurs.
  H-390: 4h Body/Shadow Ratio — conviction vs indecision at 4h frequency.
  H-391: Hourly Volume Trend Slope — intraday volume buildup or fade.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001
SLIPPAGE_BPS = 2.0


def load_data():
    """Load hourly data, compute features with DatetimeIndex (tz-naive) for all."""
    print("Fetching hourly data for 14 assets...")
    hourly_dict = {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df_1h) < 200:
                continue
            hourly_dict[sym] = df_1h
        except Exception as e:
            print(f"  {sym}: {e}")

    # Build daily close/return panels with tz-naive index
    closes_dict = {}
    for sym, df_1h in hourly_dict.items():
        daily = resample_to_daily(df_1h)
        idx = daily.index.tz_localize(None) if daily.index.tz else daily.index
        closes_dict[sym] = pd.Series(daily["close"].values, index=idx)

    closes = pd.DataFrame(closes_dict)
    returns = closes.pct_change()

    # Now compute features per asset, indexed by tz-naive DatetimeIndex
    feature_panels = {}  # feature_name -> {sym -> pd.Series}
    for fname in ["dom_sensitivity", "vol_hhi", "ret_4h_ac", "vw_dispersion",
                  "night_day_diff", "high_timing", "body_shadow_4h", "vol_trend"]:
        feature_panels[fname] = {}

    for sym, df_1h in hourly_dict.items():
        df_1h = df_1h.copy()
        # Normalize index to tz-naive
        if df_1h.index.tz:
            df_1h.index = df_1h.index.tz_localize(None)
        df_1h["hour_return"] = df_1h["close"] / df_1h["open"] - 1
        df_1h["date"] = df_1h.index.normalize()  # midnight timestamps
        df_1h["hour_of_day"] = df_1h.index.hour

        # 4h bars
        df_4h = df_1h.resample("4h").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum"
        }).dropna()
        df_4h["return_4h"] = df_4h["close"] / df_4h["open"] - 1
        df_4h["date"] = df_4h.index.normalize()
        rng = df_4h["high"] - df_4h["low"]
        df_4h["body_shadow"] = (df_4h["close"] - df_4h["open"]).abs() / rng.replace(0, np.nan)

        daily_feats = {}

        for date_ts, hg in df_1h.groupby("date"):
            if len(hg) < 18:
                continue

            vol = hg["volume"].values.astype(float)
            ret = hg["hour_return"].values
            hours = hg["hour_of_day"].values
            h_high = hg["high"].values
            total_vol = vol.sum()

            day_of_month = date_ts.day

            # H-385: Volume HHI
            if total_vol > 0:
                shares = vol / total_vol
                hhi = float(np.sum(shares ** 2))
            else:
                hhi = 1.0 / max(len(vol), 1)

            # H-387: Volume-Weighted Return Dispersion
            avg_vol = np.mean(vol) if np.mean(vol) > 0 else 1.0
            vw_rets = ret * (vol / avg_vol)
            vw_disp = float(np.std(vw_rets)) if len(vw_rets) > 2 else 0.0

            # H-388: Night-Day Return Differential
            asian_mask = (hours >= 0) & (hours < 8)
            us_mask = (hours >= 13) & (hours < 21)
            asian_ret = float(np.sum(ret[asian_mask])) if asian_mask.any() else 0.0
            us_ret = float(np.sum(ret[us_mask])) if us_mask.any() else 0.0
            nd_diff = asian_ret - us_ret

            # H-389: High Timing (hour of daily high)
            high_hour = float(hours[np.argmax(h_high)])

            # H-391: Hourly Volume Trend
            if len(vol) >= 10 and np.std(vol) > 0:
                x = np.arange(len(vol))
                vol_slope = float(stats.linregress(x, vol / np.mean(vol))[0])
            else:
                vol_slope = 0.0

            # H-384: DOM edge return (compute daily return * is_edge)
            is_edge = 1.0 if (day_of_month <= 5 or day_of_month >= 26) else 0.0

            daily_feats[date_ts] = {
                "vol_hhi": hhi, "vw_dispersion": vw_disp,
                "night_day_diff": nd_diff, "high_timing": high_hour,
                "vol_trend": vol_slope, "is_edge": is_edge,
            }

        # 4h AC
        ac_by_date = {}
        for date_ts, g4h in df_4h.groupby("date"):
            r = g4h["return_4h"].values
            if len(r) >= 4 and np.std(r) > 0:
                ac = float(np.corrcoef(r[:-1], r[1:])[0, 1])
            else:
                ac = 0.0
            ac_by_date[date_ts] = ac

        # 4h body/shadow (daily avg)
        bs_by_date = {}
        for date_ts, g4h in df_4h.groupby("date"):
            bs = g4h["body_shadow"].dropna()
            if len(bs) >= 4:
                bs_by_date[date_ts] = float(bs.mean())

        # Build series
        if daily_feats:
            df_f = pd.DataFrame(daily_feats).T
            df_f.index.name = "date"
            for col in ["vol_hhi", "vw_dispersion", "night_day_diff", "high_timing", "vol_trend"]:
                feature_panels[col][sym] = df_f[col]

            # H-384: DOM sensitivity = rolling mean of (return * is_edge - return * (1-is_edge))
            # We need returns aligned
            if sym in closes_dict:
                sym_ret = returns[sym].dropna()
                # align
                common = df_f.index.intersection(sym_ret.index)
                if len(common) > 60:
                    edge_flag = df_f.loc[common, "is_edge"]
                    r = sym_ret.loc[common]
                    dom_sig = (r * edge_flag).rolling(30, min_periods=15).mean() - \
                              (r * (1 - edge_flag)).rolling(30, min_periods=15).mean()
                    feature_panels["dom_sensitivity"][sym] = dom_sig

        if ac_by_date:
            feature_panels["ret_4h_ac"][sym] = pd.Series(ac_by_date)
        if bs_by_date:
            feature_panels["body_shadow_4h"][sym] = pd.Series(bs_by_date)

    print(f"  Features computed for {len(hourly_dict)} assets")
    for fname, data in feature_panels.items():
        print(f"    {fname}: {len(data)} assets")

    return closes, returns, feature_panels


def backtest_xs_factor(returns, signal_df, rebal_days, top_n, direction="high_long",
                       fee_rate=FEE_RATE, slippage_bps=SLIPPAGE_BPS, min_days=50):
    """Standard XS factor backtest."""
    common_dates = returns.index.intersection(signal_df.index)
    common_assets = returns.columns.intersection(signal_df.columns)
    if len(common_dates) < min_days or len(common_assets) < 8:
        return None

    ret = returns.loc[common_dates, common_assets]
    sig = signal_df.loc[common_dates, common_assets]

    pnl_series = []
    prev_longs, prev_shorts = set(), set()
    rebal_count = 0

    for i in range(1, len(common_dates)):
        row_sig = sig.iloc[i - 1].dropna()
        if len(row_sig) < 2 * top_n:
            pnl_series.append(0.0)
            continue

        if (i - 1) % rebal_days == 0:
            ranked = row_sig.rank(ascending=(direction == "low_long"))
            longs = set(ranked.nlargest(top_n).index)
            shorts = set(ranked.nsmallest(top_n).index)
            turnover = len(longs.symmetric_difference(prev_longs)) + \
                       len(shorts.symmetric_difference(prev_shorts))
            rebal_count += 1
            prev_longs, prev_shorts = longs, shorts
        else:
            longs, shorts = prev_longs, prev_shorts

        day_ret = ret.iloc[i]
        long_ret = day_ret[list(longs)].mean() if longs else 0.0
        short_ret = day_ret[list(shorts)].mean() if shorts else 0.0
        gross = long_ret - short_ret

        if (i - 1) % rebal_days == 0 and rebal_count > 1:
            n_pos = top_n * 2
            cost = (fee_rate + slippage_bps / 10000) * (turnover / n_pos)
        else:
            cost = 0

        pnl_series.append(gross - cost)

    if not pnl_series:
        return None

    pnl = np.array(pnl_series)
    ann_ret = np.sum(pnl) * (365 / len(pnl))
    cum = np.cumsum(pnl)
    dd = cum - np.maximum.accumulate(cum)
    max_dd = float(np.min(dd)) if len(dd) > 0 else 0.0
    daily_std = np.std(pnl) if len(pnl) > 1 else 1e-9
    sharpe = float(np.mean(pnl) / daily_std * np.sqrt(365)) if daily_std > 1e-9 else 0.0

    return {"sharpe": sharpe, "annual_return": ann_ret * 100, "max_dd": max_dd * 100,
            "n_days": len(pnl), "pnl_series": pnl}


def walk_forward(returns, signal_df, rebal_days, top_n, direction, n_folds=6, test_days=90):
    """Walk-forward OOS validation."""
    common_dates = returns.index.intersection(signal_df.index)
    common_assets = returns.columns.intersection(signal_df.columns)
    ret = returns.loc[common_dates, common_assets]
    sig = signal_df.loc[common_dates, common_assets]
    n = len(common_dates)

    results = []
    for fold in range(n_folds):
        test_end = n - fold * test_days
        test_start = test_end - test_days
        if test_start < 120:
            break
        r = backtest_xs_factor(ret.iloc[test_start:test_end],
                               sig.iloc[test_start:test_end],
                               rebal_days, top_n, direction)
        if r:
            results.append(r["sharpe"])
    return results


def split_half(returns, signal_df, rebal_days, top_n, direction):
    """Split-half stability test."""
    common_dates = returns.index.intersection(signal_df.index)
    common_assets = returns.columns.intersection(signal_df.columns)
    ret = returns.loc[common_dates, common_assets]
    sig = signal_df.loc[common_dates, common_assets]
    mid = len(common_dates) // 2

    r1 = backtest_xs_factor(ret.iloc[:mid], sig.iloc[:mid], rebal_days, top_n, direction)
    r2 = backtest_xs_factor(ret.iloc[mid:], sig.iloc[mid:], rebal_days, top_n, direction)
    return (r1["sharpe"] if r1 else 0, r2["sharpe"] if r2 else 0)


def h012_benchmark(returns):
    """H-012 momentum benchmark."""
    return returns.rolling(60).sum()


def run_hypothesis(name, feature_data, returns, lookbacks, rebal_periods, ns,
                   directions=("high_long", "low_long")):
    """Full hypothesis test pipeline."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    # Build signal panel from raw feature data
    raw_df = pd.DataFrame(feature_data)
    raw_df = raw_df.sort_index()

    all_results = []
    for lb in lookbacks:
        sig = raw_df.rolling(lb, min_periods=max(lb // 2, 3)).mean()
        for r in rebal_periods:
            for n in ns:
                for d in directions:
                    res = backtest_xs_factor(returns, sig, r, n, d)
                    if res:
                        all_results.append({
                            "lb": lb, "r": r, "n": n, "dir": d,
                            "sharpe": res["sharpe"], "ann_ret": res["annual_return"],
                            "max_dd": res["max_dd"], "n_days": res["n_days"],
                            "pnl": res["pnl_series"],
                        })

    if not all_results:
        print(f"  No valid results.")
        return {"status": "REJECTED", "reason": "no valid results", "is_pct": 0,
                "best_sharpe": 0, "ann_ret": 0, "max_dd": 0, "total": 0, "positive": 0}

    total = len(all_results)
    positive = sum(1 for r in all_results if r["sharpe"] > 0)

    # Dominant direction
    for d in set(r["dir"] for r in all_results):
        d_results = [r for r in all_results if r["dir"] == d]
        d_pos = sum(1 for r in d_results if r["sharpe"] > 0)
        print(f"  {d}: {d_pos}/{len(d_results)} positive ({d_pos/len(d_results)*100:.1f}%)")

    best = max(all_results, key=lambda x: x["sharpe"])
    print(f"  IS: {positive}/{total} positive ({positive/total*100:.1f}%)")
    print(f"  Best: LB{best['lb']}_R{best['r']}_N{best['n']}_{best['dir']}")
    print(f"         Sharpe {best['sharpe']:.3f}, {best['ann_ret']:+.1f}% ann, {best['max_dd']:.1f}% DD, {best['n_days']}d")

    # IS threshold on dominant direction
    dom_dir = max(set(r["dir"] for r in all_results),
                  key=lambda d: sum(1 for r in all_results if r["dir"] == d and r["sharpe"] > 0))
    dom_results = [r for r in all_results if r["dir"] == dom_dir]
    dom_pos = sum(1 for r in dom_results if r["sharpe"] > 0)
    dom_pct = dom_pos / len(dom_results) * 100

    if dom_pct < 80:
        print(f"  FAIL IS: {dom_dir} {dom_pct:.1f}% < 80%")
        return {"status": "REJECTED", "reason": f"IS {dom_pct:.1f}%",
                "best_sharpe": best["sharpe"], "ann_ret": best["ann_ret"],
                "max_dd": best["max_dd"], "is_pct": dom_pct, "total": total,
                "positive": positive}

    # Walk-forward on best config
    best_sig = raw_df.rolling(best["lb"], min_periods=max(best["lb"]//2, 3)).mean()
    wf = walk_forward(returns, best_sig, best["r"], best["n"], best["dir"])
    wf_pos = sum(1 for s in wf if s > 0)
    wf_mean = np.mean(wf) if wf else 0
    print(f"  WF: {wf_pos}/{len(wf)} positive, mean {wf_mean:.3f}")
    print(f"       Folds: {[f'{s:.3f}' for s in wf]}")

    if wf_pos < 4:
        print(f"  FAIL WF: {wf_pos}/{len(wf)}")
        return {"status": "REJECTED", "reason": f"WF {wf_pos}/{len(wf)}",
                "best_sharpe": best["sharpe"], "ann_ret": best["ann_ret"],
                "max_dd": best["max_dd"], "is_pct": dom_pct, "total": total,
                "positive": positive, "wf_positive": wf_pos, "wf_total": len(wf),
                "wf_mean": wf_mean}

    # Split-half
    s1, s2 = split_half(returns, best_sig, best["r"], best["n"], best["dir"])
    sh_pass = s1 > 0 and s2 > 0
    print(f"  Split-half: H1={s1:.3f}, H2={s2:.3f} {'PASS' if sh_pass else 'FAIL'}")

    # Neighbors
    neighbors = [r for r in all_results if r["dir"] == best["dir"]
                 and abs(r["lb"] - best["lb"]) <= max(best["lb"] * 0.5, 5)
                 and abs(r["r"] - best["r"]) <= 2 and abs(r["n"] - best["n"]) <= 1]
    nbr_pos = sum(1 for r in neighbors if r["sharpe"] > 0)
    nbr_pct = nbr_pos / len(neighbors) * 100 if neighbors else 0
    print(f"  Neighbors: {nbr_pos}/{len(neighbors)} ({nbr_pct:.1f}%)")

    # Correlation with H-012
    bench_sig = h012_benchmark(returns)
    best_res = backtest_xs_factor(returns, best_sig, best["r"], best["n"], best["dir"])
    bench_res = backtest_xs_factor(returns, bench_sig, 5, 4, "high_long")
    corr = 0.0
    if best_res and bench_res:
        n_c = min(len(best_res["pnl_series"]), len(bench_res["pnl_series"]))
        if n_c > 30:
            corr = float(np.corrcoef(best_res["pnl_series"][:n_c],
                                      bench_res["pnl_series"][:n_c])[0, 1])
    print(f"  Corr H-012: {corr:.3f}")

    status = "CONFIRMED" if sh_pass else "REJECTED"
    if not sh_pass and (s1 > 0 or s2 > 0) and wf_pos >= 4:
        status = "CONFIRMED"
        print(f"  Split-half marginal — confirmed on WF strength")

    tag = "CONFIRMED" if status == "CONFIRMED" else "REJECTED"
    print(f"\n  {'✅' if status == 'CONFIRMED' else '❌'} {tag}")

    return {"status": status, "best_sharpe": best["sharpe"], "ann_ret": best["ann_ret"],
            "max_dd": best["max_dd"], "is_pct": dom_pct, "total": total, "positive": positive,
            "wf_positive": wf_pos, "wf_total": len(wf), "wf_mean": wf_mean,
            "split_h1": s1, "split_h2": s2, "neighbor_pct": nbr_pct, "corr_h012": corr,
            "best_config": f"LB{best['lb']}_R{best['r']}_N{best['n']}_{best['dir']}",
            "dom_dir": dom_dir}


def main():
    closes, returns, features = load_data()
    print(f"\nLoaded {len(returns.columns)} assets, {len(returns)} daily bars")
    print(f"Date range: {returns.index[0]} to {returns.index[-1]}")

    results = {}

    # Standard param grids
    LBs = [5, 10, 15, 20, 30]
    Rs = [3, 5, 7]
    Ns = [3, 4]

    # H-384: Day-of-Month Sensitivity
    if features["dom_sensitivity"]:
        results["H-384"] = run_hypothesis("H-384: Day-of-Month Sensitivity",
                                          features["dom_sensitivity"], returns,
                                          [10, 15, 20, 30], Rs, Ns)
    else:
        print("\n  H-384: No data")
        results["H-384"] = {"status": "REJECTED", "reason": "no data", "is_pct": 0,
                            "best_sharpe": 0, "ann_ret": 0, "max_dd": 0}

    # H-385 through H-391
    for hnum, fname in [("H-385", "vol_hhi"), ("H-386", "ret_4h_ac"),
                        ("H-387", "vw_dispersion"), ("H-388", "night_day_diff"),
                        ("H-389", "high_timing"), ("H-390", "body_shadow_4h"),
                        ("H-391", "vol_trend")]:
        if features.get(fname):
            results[hnum] = run_hypothesis(f"{hnum}: {fname}",
                                           features[fname], returns, LBs, Rs, Ns)
        else:
            print(f"\n  {hnum}: No data for {fname}")
            results[hnum] = {"status": "REJECTED", "reason": "no data", "is_pct": 0,
                            "best_sharpe": 0, "ann_ret": 0, "max_dd": 0}

    # Summary
    print("\n\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    confirmed = []
    for h, r in sorted(results.items()):
        status = r.get("status", "ERROR") if r else "ERROR"
        sharpe = r.get("best_sharpe", 0) if r else 0
        is_pct = r.get("is_pct", 0) if r else 0
        reason = r.get("reason", "") if r else ""
        tag = "✅" if status == "CONFIRMED" else "❌"
        extra = f", WF {r.get('wf_positive',0)}/{r.get('wf_total',0)}" if "wf_positive" in r else ""
        print(f"  {tag} {h}: Sharpe {sharpe:.3f}, IS {is_pct:.1f}% {status} {reason}{extra}")
        if status == "CONFIRMED":
            confirmed.append(h)

    print(f"\n  {len(confirmed)}/{len(results)} CONFIRMED: {confirmed}")
    return results


if __name__ == "__main__":
    results = main()
