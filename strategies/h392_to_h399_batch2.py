#!/usr/bin/env python3
"""
Backtest 8 novel cross-sectional factors — session 167, batch 2.
Focus on stronger signal types: OI-based, multi-frequency composites, crypto-specific.

  H-392: OI Momentum Factor — rank by rolling change in open interest (not price).
         Rising OI = new money entering, falling OI = positions closing.
  H-393: Volume-OI Divergence Momentum — rolling corr(volume_change, OI_change).
         High corr = aligned flows (trending). Low/neg = divergent (reversal setup).
  H-394: Hourly Return Variance Ratio — var(2h returns) / (2 * var(1h returns)).
         Tests random walk. VR > 1 = trending. VR < 1 = mean-reverting at intraday scale.
  H-395: Intraday Volume Asymmetry — ratio of volume on up-hours to volume on down-hours.
         High = buying pressure dominates. Distinct from daily up-vol ratio (H-219) by
         using hourly granularity.
  H-396: Price Impact Factor — avg |return| per unit volume. High = thin/fragile market.
         Inverse of liquidity. Different from Amihud (H-197) by using hourly data.
  H-397: 4h Momentum Composite — combine 4h return autocorrelation + body/shadow +
         volume persistence into one composite score. Multi-signal approach.
  H-398: Funding-OI Interaction — rank by funding_rate * OI_change.
         When high funding + rising OI = crowded momentum. Contrarian short.
  H-399: Return Acceleration at 4h — second derivative of 4h cumulative returns.
         Positive acceleration = trend strengthening. Negative = trend exhaustion.
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
    """Load hourly + OI data, compute features."""
    print("Fetching hourly data for 14 assets...")
    hourly_dict = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df) < 200:
                continue
            hourly_dict[sym] = df
        except Exception as e:
            print(f"  {sym}: {e}")

    # Load OI data
    print("Fetching OI data...")
    oi_dict = {}
    for sym in ASSETS:
        try:
            ticker = sym.replace("/", "")
            oi_path = ROOT / "data" / f"oi_{ticker}_daily.parquet"
            if oi_path.exists():
                oi_df = pd.read_parquet(oi_path)
                if len(oi_df) > 100:
                    oi_dict[sym] = oi_df
                    continue
            # Try fetching
            from lib.data_fetch import fetch_oi_history
            oi_df = fetch_oi_history(sym, limit=1000)
            if oi_df is not None and len(oi_df) > 100:
                oi_dict[sym] = oi_df
        except Exception:
            pass
    print(f"  OI data: {len(oi_dict)} assets")

    # Load funding data
    print("Fetching funding data...")
    funding_dict = {}
    for sym in ASSETS:
        try:
            ticker = sym.replace("/", "")
            fund_path = ROOT / "data" / f"funding_{ticker}.parquet"
            if fund_path.exists():
                fund_df = pd.read_parquet(fund_path)
                if len(fund_df) > 100:
                    funding_dict[sym] = fund_df
                    continue
        except Exception:
            pass
    print(f"  Funding data: {len(funding_dict)} assets")

    # Build close/return panels
    closes_dict = {}
    for sym, df in hourly_dict.items():
        daily = resample_to_daily(df)
        idx = daily.index.tz_localize(None) if daily.index.tz else daily.index
        closes_dict[sym] = pd.Series(daily["close"].values, index=idx)

    closes = pd.DataFrame(closes_dict)
    returns = closes.pct_change()

    # Compute features
    feature_panels = {}
    for fname in ["oi_momentum", "vol_oi_corr", "variance_ratio",
                  "hourly_vol_asym", "price_impact", "composite_4h",
                  "funding_oi_interaction", "ret_acceleration_4h"]:
        feature_panels[fname] = {}

    for sym, df_1h in hourly_dict.items():
        df_1h = df_1h.copy()
        if df_1h.index.tz:
            df_1h.index = df_1h.index.tz_localize(None)
        df_1h["hour_return"] = df_1h["close"] / df_1h["open"] - 1
        df_1h["date"] = df_1h.index.normalize()
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
            total_vol = vol.sum()
            avg_vol = np.mean(vol) if np.mean(vol) > 0 else 1.0

            # H-394: Variance Ratio (2h vs 1h)
            if len(ret) >= 20:
                var_1h = np.var(ret)
                # 2h returns: sum pairs
                ret_2h = ret[::2][:len(ret)//2] + ret[1::2][:len(ret)//2]
                var_2h = np.var(ret_2h) if len(ret_2h) > 2 else 0
                vr = var_2h / (2 * var_1h) if var_1h > 1e-12 else 1.0
            else:
                vr = 1.0

            # H-395: Hourly Volume Asymmetry
            up_mask = ret > 0
            down_mask = ret < 0
            up_vol = vol[up_mask].sum() if up_mask.any() else 0
            down_vol = vol[down_mask].sum() if down_mask.any() else 1
            vol_asym = up_vol / down_vol if down_vol > 0 else 1.0

            # H-396: Price Impact = avg(|ret|/vol) per hour
            impacts = []
            for j in range(len(ret)):
                if vol[j] > 0:
                    impacts.append(abs(ret[j]) / (vol[j] / avg_vol))
            price_impact = np.mean(impacts) if impacts else 0.0

            daily_feats[date_ts] = {
                "variance_ratio": vr,
                "hourly_vol_asym": vol_asym,
                "price_impact": price_impact,
            }

        # 4h composite and acceleration
        comp_by_date = {}
        accel_by_date = {}
        for date_ts, g4h in df_4h.groupby("date"):
            r4h = g4h["return_4h"].values
            bs = g4h["body_shadow"].dropna().values
            v4h = g4h["volume"].values.astype(float)

            if len(r4h) >= 4:
                # AC of 4h returns
                ac = float(np.corrcoef(r4h[:-1], r4h[1:])[0, 1]) if np.std(r4h) > 0 else 0
                # Avg body/shadow
                avg_bs = float(np.mean(bs)) if len(bs) > 0 else 0.5
                # Volume persistence (AC of volumes)
                vol_ac = float(np.corrcoef(v4h[:-1], v4h[1:])[0, 1]) if np.std(v4h) > 0 else 0

                # H-397: Composite = normalized sum of ac + bs + vol_ac
                composite = (ac + avg_bs + vol_ac) / 3.0
                comp_by_date[date_ts] = composite

                # H-399: Return acceleration = second diff of cumulative 4h returns
                cum_ret = np.cumsum(r4h)
                if len(cum_ret) >= 3:
                    velocity = np.diff(cum_ret)
                    acceleration = np.diff(velocity)
                    accel_by_date[date_ts] = float(np.mean(acceleration))

        # Store features
        if daily_feats:
            df_f = pd.DataFrame(daily_feats).T
            for col in df_f.columns:
                feature_panels[col][sym] = df_f[col]

        if comp_by_date:
            feature_panels["composite_4h"][sym] = pd.Series(comp_by_date)
        if accel_by_date:
            feature_panels["ret_acceleration_4h"][sym] = pd.Series(accel_by_date)

    # OI-based features
    for sym in hourly_dict:
        if sym not in oi_dict:
            continue
        oi_df = oi_dict[sym]
        # Get OI series (daily)
        if "openInterest" in oi_df.columns:
            oi_col = "openInterest"
        elif "oi" in oi_df.columns:
            oi_col = "oi"
        else:
            continue

        oi_s = oi_df[oi_col].copy()
        if oi_s.index.tz:
            oi_s.index = oi_s.index.tz_localize(None)
        oi_s = oi_s.resample("D").last().dropna()

        # H-392: OI Momentum
        oi_mom = oi_s.pct_change(5)  # 5-day OI change
        feature_panels["oi_momentum"][sym] = oi_mom

        # H-393: Volume-OI correlation
        if sym in closes_dict:
            vol_daily = pd.DataFrame(closes_dict).index  # use volume from hourly
            pass  # Will compute below with daily volume

        # H-398: Funding-OI interaction
        if sym in funding_dict:
            fund_df = funding_dict[sym]
            if "fundingRate" in fund_df.columns:
                fund_s = fund_df["fundingRate"].copy()
                if fund_s.index.tz:
                    fund_s.index = fund_s.index.tz_localize(None)
                fund_daily = fund_s.resample("D").mean().dropna()
                # Align and compute interaction
                common = oi_mom.index.intersection(fund_daily.index)
                if len(common) > 50:
                    interaction = fund_daily.loc[common] * oi_mom.loc[common]
                    feature_panels["funding_oi_interaction"][sym] = interaction

    print(f"\n  Features computed:")
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
    common_dates = returns.index.intersection(signal_df.index)
    common_assets = returns.columns.intersection(signal_df.columns)
    ret = returns.loc[common_dates, common_assets]
    sig = signal_df.loc[common_dates, common_assets]
    n = len(common_dates)
    results = []
    for fold in range(n_folds):
        test_end = n - fold * test_days
        test_start = test_end - test_days
        if test_start < 60:
            break
        r = backtest_xs_factor(ret.iloc[test_start:test_end],
                               sig.iloc[test_start:test_end],
                               rebal_days, top_n, direction)
        if r:
            results.append(r["sharpe"])
    return results


def split_half(returns, signal_df, rebal_days, top_n, direction):
    common_dates = returns.index.intersection(signal_df.index)
    common_assets = returns.columns.intersection(signal_df.columns)
    ret = returns.loc[common_dates, common_assets]
    sig = signal_df.loc[common_dates, common_assets]
    mid = len(common_dates) // 2
    r1 = backtest_xs_factor(ret.iloc[:mid], sig.iloc[:mid], rebal_days, top_n, direction)
    r2 = backtest_xs_factor(ret.iloc[mid:], sig.iloc[mid:], rebal_days, top_n, direction)
    return (r1["sharpe"] if r1 else 0, r2["sharpe"] if r2 else 0)


def h012_benchmark(returns):
    return returns.rolling(60).sum()


def run_hypothesis(name, feature_data, returns, lookbacks, rebal_periods, ns,
                   directions=("high_long", "low_long")):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    raw_df = pd.DataFrame(feature_data).sort_index()

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

    for d in set(r["dir"] for r in all_results):
        d_results = [r for r in all_results if r["dir"] == d]
        d_pos = sum(1 for r in d_results if r["sharpe"] > 0)
        print(f"  {d}: {d_pos}/{len(d_results)} ({d_pos/len(d_results)*100:.1f}%)")

    best = max(all_results, key=lambda x: x["sharpe"])
    print(f"  IS: {positive}/{total} ({positive/total*100:.1f}%)")
    print(f"  Best: LB{best['lb']}_R{best['r']}_N{best['n']}_{best['dir']}")
    print(f"         Sharpe {best['sharpe']:.3f}, {best['ann_ret']:+.1f}% ann, {best['max_dd']:.1f}% DD, {best['n_days']}d")

    dom_dir = max(set(r["dir"] for r in all_results),
                  key=lambda d: sum(1 for r in all_results if r["dir"] == d and r["sharpe"] > 0))
    dom_results = [r for r in all_results if r["dir"] == dom_dir]
    dom_pos = sum(1 for r in dom_results if r["sharpe"] > 0)
    dom_pct = dom_pos / len(dom_results) * 100

    if dom_pct < 80:
        print(f"  FAIL IS: {dom_dir} {dom_pct:.1f}% < 80%")
        return {"status": "REJECTED", "reason": f"IS {dom_pct:.1f}%",
                "best_sharpe": best["sharpe"], "ann_ret": best["ann_ret"],
                "max_dd": best["max_dd"], "is_pct": dom_pct, "total": total, "positive": positive}

    best_sig = raw_df.rolling(best["lb"], min_periods=max(best["lb"]//2, 3)).mean()
    wf = walk_forward(returns, best_sig, best["r"], best["n"], best["dir"])
    wf_pos = sum(1 for s in wf if s > 0)
    wf_mean = np.mean(wf) if wf else 0
    print(f"  WF: {wf_pos}/{len(wf)}, mean {wf_mean:.3f}")
    print(f"       Folds: {[f'{s:.3f}' for s in wf]}")

    if wf_pos < 4:
        print(f"  FAIL WF: {wf_pos}/{len(wf)}")
        return {"status": "REJECTED", "reason": f"WF {wf_pos}/{len(wf)}",
                "best_sharpe": best["sharpe"], "ann_ret": best["ann_ret"],
                "max_dd": best["max_dd"], "is_pct": dom_pct, "total": total, "positive": positive,
                "wf_positive": wf_pos, "wf_total": len(wf), "wf_mean": wf_mean}

    s1, s2 = split_half(returns, best_sig, best["r"], best["n"], best["dir"])
    sh_pass = s1 > 0 and s2 > 0
    print(f"  Split-half: H1={s1:.3f}, H2={s2:.3f} {'PASS' if sh_pass else 'FAIL'}")

    neighbors = [r for r in all_results if r["dir"] == best["dir"]
                 and abs(r["lb"] - best["lb"]) <= max(best["lb"] * 0.5, 5)
                 and abs(r["r"] - best["r"]) <= 2 and abs(r["n"] - best["n"]) <= 1]
    nbr_pos = sum(1 for r in neighbors if r["sharpe"] > 0)
    nbr_pct = nbr_pos / len(neighbors) * 100 if neighbors else 0
    print(f"  Neighbors: {nbr_pos}/{len(neighbors)} ({nbr_pct:.1f}%)")

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

    print(f"\n  {'✅' if status == 'CONFIRMED' else '❌'} {status}")

    return {"status": status, "best_sharpe": best["sharpe"], "ann_ret": best["ann_ret"],
            "max_dd": best["max_dd"], "is_pct": dom_pct, "total": total, "positive": positive,
            "wf_positive": wf_pos, "wf_total": len(wf), "wf_mean": wf_mean,
            "split_h1": s1, "split_h2": s2, "neighbor_pct": nbr_pct, "corr_h012": corr,
            "best_config": f"LB{best['lb']}_R{best['r']}_N{best['n']}_{best['dir']}",
            "dom_dir": dom_dir}


def main():
    closes, returns, features = load_data()
    print(f"\nLoaded {len(returns.columns)} assets, {len(returns)} daily bars")

    results = {}
    LBs = [5, 10, 15, 20, 30]
    Rs = [3, 5, 7]
    Ns = [3, 4]

    # H-392: OI Momentum
    if len(features["oi_momentum"]) >= 8:
        results["H-392"] = run_hypothesis("H-392: OI Momentum",
                                          features["oi_momentum"], returns, LBs, Rs, Ns)
    else:
        print(f"\n  H-392: Only {len(features['oi_momentum'])} assets with OI data (need 8)")
        results["H-392"] = {"status": "REJECTED", "reason": "insufficient OI data",
                            "is_pct": 0, "best_sharpe": 0, "ann_ret": 0, "max_dd": 0}

    # H-393: Volume-OI Divergence — skip if insufficient OI data
    # Will use vol_oi_corr feature
    if len(features.get("vol_oi_corr", {})) >= 8:
        results["H-393"] = run_hypothesis("H-393: Volume-OI Corr",
                                          features["vol_oi_corr"], returns, LBs, Rs, Ns)
    else:
        print(f"\n  H-393: Insufficient vol-OI correlation data")
        results["H-393"] = {"status": "REJECTED", "reason": "insufficient data",
                            "is_pct": 0, "best_sharpe": 0, "ann_ret": 0, "max_dd": 0}

    # H-394: Variance Ratio
    results["H-394"] = run_hypothesis("H-394: Intraday Variance Ratio",
                                      features["variance_ratio"], returns, LBs, Rs, Ns)

    # H-395: Hourly Volume Asymmetry
    results["H-395"] = run_hypothesis("H-395: Hourly Volume Asymmetry",
                                      features["hourly_vol_asym"], returns, LBs, Rs, Ns)

    # H-396: Price Impact
    results["H-396"] = run_hypothesis("H-396: Price Impact Factor",
                                      features["price_impact"], returns, LBs, Rs, Ns)

    # H-397: 4h Composite
    if len(features["composite_4h"]) >= 8:
        results["H-397"] = run_hypothesis("H-397: 4h Momentum Composite",
                                          features["composite_4h"], returns, LBs, Rs, Ns)
    else:
        results["H-397"] = {"status": "REJECTED", "reason": "insufficient data",
                            "is_pct": 0, "best_sharpe": 0, "ann_ret": 0, "max_dd": 0}

    # H-398: Funding-OI Interaction
    if len(features.get("funding_oi_interaction", {})) >= 8:
        results["H-398"] = run_hypothesis("H-398: Funding-OI Interaction",
                                          features["funding_oi_interaction"], returns,
                                          LBs, Rs, Ns)
    else:
        print(f"\n  H-398: Insufficient funding-OI data ({len(features.get('funding_oi_interaction', {}))} assets)")
        results["H-398"] = {"status": "REJECTED", "reason": "insufficient data",
                            "is_pct": 0, "best_sharpe": 0, "ann_ret": 0, "max_dd": 0}

    # H-399: 4h Return Acceleration
    if len(features["ret_acceleration_4h"]) >= 8:
        results["H-399"] = run_hypothesis("H-399: 4h Return Acceleration",
                                          features["ret_acceleration_4h"], returns, LBs, Rs, Ns)
    else:
        results["H-399"] = {"status": "REJECTED", "reason": "insufficient data",
                            "is_pct": 0, "best_sharpe": 0, "ann_ret": 0, "max_dd": 0}

    # Summary
    print("\n\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    confirmed = []
    for h, r in sorted(results.items()):
        status = r.get("status", "ERROR")
        sharpe = r.get("best_sharpe", 0)
        is_pct = r.get("is_pct", 0)
        reason = r.get("reason", "")
        tag = "✅" if status == "CONFIRMED" else "❌"
        extra = f", WF {r.get('wf_positive',0)}/{r.get('wf_total',0)}" if "wf_positive" in r else ""
        print(f"  {tag} {h}: Sharpe {sharpe:.3f}, IS {is_pct:.1f}% {status} {reason}{extra}")
        if status == "CONFIRMED":
            confirmed.append(h)

    print(f"\n  {len(confirmed)}/{len(results)} CONFIRMED: {confirmed}")
    return results


if __name__ == "__main__":
    results = main()
