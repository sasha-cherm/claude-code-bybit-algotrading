#!/usr/bin/env python3
"""
Batch 5 of hourly-derived signals. All signals use LAGGED hourly data (yesterday's)
to avoid look-ahead bias. Trade on daily rebalance.

  H-464: Hourly Volume Momentum — slope of volume over hours (linear regression).
         Positive slope = volume building throughout day = accumulation.
  H-465: Price-Volume Divergence — correlation between hourly return direction
         and volume change direction. Negative = divergence (bearish if price up).
  H-466: Intraday Vol Ratio — std(returns first half) / std(returns second half).
         >1 = front-loaded volatility (news-driven). <1 = back-loaded (positioning).
  H-467: Hourly Return Dispersion — std dev of hourly returns within day.
         High = volatile intraday. Low = smooth intraday.
  H-468: VWAP Position — (VWAP - low) / (high - low) where VWAP computed from
         hourly bars. Near 1 = VWAP near highs = strong. Near 0 = weak.
  H-469: Reversal Count — number of sign changes in hourly returns / total hours.
         High = choppy. Low = trending.
  H-470: First-Hour Return — return of first hourly bar. Often sets daily direction.
  H-471: Last-Hour Return — return of last hourly bar. Reflects closing flows.

Standard framework: grid search, IS >=80%, walk-forward OOS, split-half, H-012 corr.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001
SLIPPAGE_BPS = 2.0


def load_data():
    print("Loading daily + hourly data for 14 assets...")
    closes_dict, volumes_dict = {}, {}
    hourly_dict = {}

    for sym in ASSETS:
        ticker = sym.replace("/", "_")
        fpath_d = ROOT / "data" / f"{ticker}_1d.parquet"
        if not fpath_d.exists():
            continue
        df = pd.read_parquet(fpath_d)
        if len(df) < 200:
            continue
        closes_dict[sym] = df["close"]
        volumes_dict[sym] = df["volume"]

        fpath_h = ROOT / "data" / f"{ticker}_1h.parquet"
        if fpath_h.exists():
            hdf = pd.read_parquet(fpath_h)
            hourly_dict[sym] = hdf

    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill().dropna()
    idx = closes.index.intersection(volumes.index)
    closes, volumes = closes.loc[idx], volumes.loc[idx]

    print(f"Loaded {len(closes.columns)} daily assets, {len(closes)} bars")
    print(f"Hourly data for {len(hourly_dict)} assets")
    return closes, volumes, hourly_dict


def precompute_hourly_features(closes, hourly_dict):
    print("Pre-computing hourly features batch 5 (lagged)...")
    dates = closes.index
    syms = closes.columns

    vol_momentum = pd.DataFrame(index=dates, columns=syms, dtype=float)
    pv_divergence = pd.DataFrame(index=dates, columns=syms, dtype=float)
    intraday_vol_ratio = pd.DataFrame(index=dates, columns=syms, dtype=float)
    ret_dispersion = pd.DataFrame(index=dates, columns=syms, dtype=float)
    vwap_position = pd.DataFrame(index=dates, columns=syms, dtype=float)
    reversal_count = pd.DataFrame(index=dates, columns=syms, dtype=float)
    first_hour_ret = pd.DataFrame(index=dates, columns=syms, dtype=float)
    last_hour_ret = pd.DataFrame(index=dates, columns=syms, dtype=float)

    for sym in syms:
        if sym not in hourly_dict:
            continue
        hdf = hourly_dict[sym]
        hdf = hdf.sort_index()

        for di in range(1, len(dates)):
            date_i = dates[di]
            prev_date = dates[di - 1]

            mask = (hdf.index >= prev_date) & (hdf.index < date_i)
            day_bars = hdf.loc[mask]
            if len(day_bars) < 12:
                continue

            h_vol = day_bars["volume"].values
            h_close = day_bars["close"].values
            h_open = day_bars["open"].values
            h_high = day_bars["high"].values
            h_low = day_bars["low"].values

            h_rets = np.diff(h_close) / h_close[:-1]
            h_rets = h_rets[np.isfinite(h_rets)]

            # H-464: Volume momentum (slope of volume over time)
            if len(h_vol) >= 8:
                x = np.arange(len(h_vol))
                slope, _, _, _, _ = stats.linregress(x, h_vol)
                # Normalize by mean volume
                mean_v = np.mean(h_vol)
                if mean_v > 0:
                    norm_slope = slope / mean_v
                    if np.isfinite(norm_slope):
                        vol_momentum.at[date_i, sym] = norm_slope

            # H-465: Price-volume divergence
            if len(h_rets) >= 8:
                vol_changes = np.diff(h_vol)
                vol_ch = vol_changes[:len(h_rets)]
                if len(vol_ch) >= 8:
                    # Direction alignment: sign(return) * sign(vol_change)
                    alignment = np.sign(h_rets[:len(vol_ch)]) * np.sign(vol_ch)
                    pvd = np.mean(alignment)
                    if np.isfinite(pvd):
                        pv_divergence.at[date_i, sym] = pvd

            # H-466: Intraday vol ratio (first half vs second half)
            if len(h_rets) >= 12:
                mid = len(h_rets) // 2
                std1 = np.std(h_rets[:mid])
                std2 = np.std(h_rets[mid:])
                if std2 > 0:
                    vr = std1 / std2
                    if np.isfinite(vr) and vr < 100:
                        intraday_vol_ratio.at[date_i, sym] = vr

            # H-467: Return dispersion (std of hourly returns)
            if len(h_rets) >= 8:
                rd = np.std(h_rets)
                if np.isfinite(rd):
                    ret_dispersion.at[date_i, sym] = rd

            # H-468: VWAP position
            total_v = h_vol.sum()
            day_high = np.max(h_high)
            day_low = np.min(h_low)
            day_range = day_high - day_low
            if total_v > 0 and day_range > 0:
                # Approximate VWAP using hourly close * volume
                vwap = np.sum(h_close * h_vol) / total_v
                vp = (vwap - day_low) / day_range
                if np.isfinite(vp):
                    vwap_position.at[date_i, sym] = vp

            # H-469: Reversal count
            if len(h_rets) >= 8:
                signs = np.sign(h_rets)
                sign_changes = np.sum(signs[1:] != signs[:-1])
                rc = sign_changes / len(h_rets)
                if np.isfinite(rc):
                    reversal_count.at[date_i, sym] = rc

            # H-470: First-hour return
            if len(h_close) >= 2:
                fhr = (h_close[0] - h_open[0]) / h_open[0] if h_open[0] > 0 else 0
                if np.isfinite(fhr):
                    first_hour_ret.at[date_i, sym] = fhr

            # H-471: Last-hour return
            if len(h_close) >= 2:
                lhr = (h_close[-1] - h_open[-1]) / h_open[-1] if h_open[-1] > 0 else 0
                if np.isfinite(lhr):
                    last_hour_ret.at[date_i, sym] = lhr

    features = {
        "vol_momentum": vol_momentum,
        "pv_divergence": pv_divergence,
        "intraday_vol_ratio": intraday_vol_ratio,
        "ret_dispersion": ret_dispersion,
        "vwap_position": vwap_position,
        "reversal_count": reversal_count,
        "first_hour_ret": first_hour_ret,
        "last_hour_ret": last_hour_ret,
    }
    print("Feature computation done.")
    return features


def backtest_factor(closes, factor_fn, lookbacks, rebals, ns, directions,
                    factor_name, extra_data=None):
    returns = closes.pct_change()
    slippage = SLIPPAGE_BPS / 10_000
    results = []

    for lookback in lookbacks:
        for rebal in rebals:
            for n in ns:
                for direction in directions:
                    warmup = lookback + 10
                    pnl_daily = []
                    positions = {}
                    days_since = rebal

                    for i in range(warmup, len(closes)):
                        days_since += 1
                        if days_since >= rebal:
                            scores = factor_fn(closes, extra_data, lookback, i)
                            if scores is None or len(scores) < 2 * n:
                                continue

                            if direction.endswith("_long"):
                                high_first = direction.startswith("high")
                                ranked = scores.sort_values(ascending=not high_first)
                            else:
                                ranked = scores.sort_values(ascending=False)

                            longs = set(ranked.index[:n])
                            shorts = set(ranked.index[-n:])
                            old_syms = set(positions.keys())
                            new_syms = longs | shorts
                            changed = old_syms.symmetric_difference(new_syms)
                            fee_cost = len(changed) * FEE_RATE / (2 * n)
                            slip_cost = len(changed) * slippage / (2 * n)

                            positions = {}
                            for sym in longs:
                                positions[sym] = 1.0 / n
                            for sym in shorts:
                                positions[sym] = -1.0 / n
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

                    if len(pnl_daily) < 100:
                        continue

                    pnl = np.array(pnl_daily)
                    sharpe = float(np.mean(pnl) / np.std(pnl) * np.sqrt(365)) if np.std(pnl) > 0 else 0
                    ann_ret = float((1 + np.mean(pnl)) ** 365 - 1) * 100
                    cum = np.cumprod(1 + pnl)
                    dd = float((1 - cum / np.maximum.accumulate(cum)).max()) * 100

                    results.append({
                        "factor": factor_name,
                        "lookback": lookback,
                        "rebal": rebal,
                        "n": n,
                        "direction": direction,
                        "sharpe": round(sharpe, 3),
                        "ann_ret": round(ann_ret, 1),
                        "max_dd": round(dd, 1),
                        "n_days": len(pnl_daily),
                        "pnl_daily": pnl,
                    })

    return results


def walk_forward(closes, factor_fn, lookback, rebal, n, direction,
                 extra_data=None, n_folds=6):
    returns = closes.pct_change()
    slippage = SLIPPAGE_BPS / 10_000
    total_bars = len(closes)
    warmup = lookback + 10
    usable = total_bars - warmup
    fold_size = usable // n_folds

    oos_sharpes = []
    for fold in range(n_folds):
        test_start = warmup + fold * fold_size
        test_end = min(test_start + fold_size, total_bars)
        if test_end > total_bars:
            break

        positions = {}
        days_since = rebal
        pnl_daily = []

        for i in range(test_start, test_end):
            days_since += 1
            if days_since >= rebal:
                scores = factor_fn(closes, extra_data, lookback, i)
                if scores is None or len(scores) < 2 * n:
                    continue

                if direction.endswith("_long"):
                    high_first = direction.startswith("high")
                    ranked = scores.sort_values(ascending=not high_first)
                else:
                    ranked = scores.sort_values(ascending=False)

                longs = set(ranked.index[:n])
                shorts = set(ranked.index[-n:])
                old_syms = set(positions.keys())
                new_syms = longs | shorts
                changed = old_syms.symmetric_difference(new_syms)
                fee_cost = len(changed) * FEE_RATE / (2 * n)
                slip_cost = len(changed) * slippage / (2 * n)

                positions = {}
                for sym in longs:
                    positions[sym] = 1.0 / n
                for sym in shorts:
                    positions[sym] = -1.0 / n
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

        if len(pnl_daily) < 30:
            oos_sharpes.append(0)
            continue

        pnl = np.array(pnl_daily)
        sh = float(np.mean(pnl) / np.std(pnl) * np.sqrt(365)) if np.std(pnl) > 0 else 0
        oos_sharpes.append(sh)

    return oos_sharpes


def split_half_test(closes, factor_fn, lookback, rebal, n, direction,
                    extra_data=None):
    mid = len(closes) // 2
    h1_closes = closes.iloc[:mid + lookback]
    h2_closes = closes.iloc[mid:]
    r1 = backtest_factor(h1_closes, factor_fn, [lookback], [rebal], [n],
                         [direction], "h1", extra_data)
    r2 = backtest_factor(h2_closes, factor_fn, [lookback], [rebal], [n],
                         [direction], "h2", extra_data)
    s1 = r1[0]["sharpe"] if r1 else 0
    s2 = r2[0]["sharpe"] if r2 else 0
    return s1, s2


def compute_h012_correlation(closes, factor_fn, lookback, rebal, n, direction,
                             extra_data=None):
    returns = closes.pct_change()
    slippage = SLIPPAGE_BPS / 10_000

    def run_strat(fn, ed=None):
        warmup = lookback + 10
        positions = {}
        days_since = rebal
        pnl_daily = []
        for i in range(warmup, len(closes)):
            days_since += 1
            if days_since >= rebal:
                scores = fn(closes, ed, lookback, i)
                if scores is None or len(scores) < 2 * n:
                    pnl_daily.append(0)
                    continue
                if direction.endswith("_long"):
                    high_first = direction.startswith("high")
                    ranked = scores.sort_values(ascending=not high_first)
                else:
                    ranked = scores.sort_values(ascending=False)
                longs = set(ranked.index[:n])
                shorts = set(ranked.index[-n:])
                old_syms = set(positions.keys())
                new_syms = longs | shorts
                changed = old_syms.symmetric_difference(new_syms)
                fee_cost = len(changed) * FEE_RATE / (2 * n)
                slip_cost = len(changed) * slippage / (2 * n)
                positions = {}
                for sym in longs:
                    positions[sym] = 1.0 / n
                for sym in shorts:
                    positions[sym] = -1.0 / n
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

    def h012_fn(c, _ed, lb, i):
        ret = c.iloc[i] / c.iloc[i - lb] - 1
        return ret.dropna()

    pnl_test = run_strat(factor_fn, extra_data)
    pnl_h012 = run_strat(h012_fn)
    mn = min(len(pnl_test), len(pnl_h012))
    if mn < 30:
        return 0
    corr = np.corrcoef(pnl_test[:mn], pnl_h012[:mn])[0, 1]
    return round(corr, 3) if np.isfinite(corr) else 0


def make_rolling_factor(feature_key, agg="mean"):
    def factor_fn(closes, extra_data, lookback, i):
        feat = extra_data["features"][feature_key]
        feat_slice = feat.iloc[max(0, i-lookback):i]
        if len(feat_slice) < 5:
            return None
        if agg == "mean":
            score = feat_slice.mean()
        elif agg == "median":
            score = feat_slice.median()
        else:
            score = feat_slice.mean()
        return score.dropna()
    return factor_fn


FACTORS = [
    ("H-464 Vol Momentum", "vol_momentum", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-465 PV Divergence", "pv_divergence", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-466 Intraday Vol Ratio", "intraday_vol_ratio", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-467 Ret Dispersion", "ret_dispersion", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-468 VWAP Position", "vwap_position", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-469 Reversal Count", "reversal_count", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-470 First Hour Ret", "first_hour_ret", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-471 Last Hour Ret", "last_hour_ret", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
]


def main():
    closes, volumes, hourly_dict = load_data()
    features = precompute_hourly_features(closes, hourly_dict)
    extra = {"volumes": volumes, "features": features}

    for factor_name, feat_key, agg, lookbacks, rebals, ns, directions in FACTORS:
        print(f"\n{'='*60}")
        print(f"  {factor_name}")
        print(f"{'='*60}")

        factor_fn = make_rolling_factor(feat_key, agg)
        results = backtest_factor(closes, factor_fn, lookbacks, rebals, ns,
                                  directions, factor_name, extra)

        if not results:
            print("  NO RESULTS")
            continue

        total = len(results)
        positive = sum(1 for r in results if r["sharpe"] > 0)
        pct = positive / total * 100
        best = max(results, key=lambda x: x["sharpe"])
        median_sharpe = np.median([r["sharpe"] for r in results])

        print(f"\n  IS Results: {positive}/{total} positive ({pct:.1f}%)")
        print(f"  Median Sharpe: {median_sharpe:.3f}")
        print(f"  Best: LB={best['lookback']}, R={best['rebal']}, N={best['n']}, "
              f"Dir={best['direction']}")
        print(f"    Sharpe={best['sharpe']:.3f}, Ann={best['ann_ret']:.1f}%, "
              f"DD={best['max_dd']:.1f}%, Days={best['n_days']}")

        for d in directions:
            d_results = [r for r in results if r["direction"] == d]
            d_pos = sum(1 for r in d_results if r["sharpe"] > 0)
            d_pct = d_pos / len(d_results) * 100 if d_results else 0
            print(f"    {d}: {d_pos}/{len(d_results)} positive ({d_pct:.1f}%)")

        if pct < 80:
            best_dir_pct = 0
            best_dir = None
            for d in directions:
                d_results = [r for r in results if r["direction"] == d]
                d_pos = sum(1 for r in d_results if r["sharpe"] > 0)
                d_pct = d_pos / len(d_results) * 100 if d_results else 0
                if d_pct > best_dir_pct:
                    best_dir_pct = d_pct
                    best_dir = d

            if best_dir_pct >= 80:
                print(f"\n  Direction {best_dir} passes IS at {best_dir_pct:.1f}%!")
                dir_results = [r for r in results if r["direction"] == best_dir]
                best = max(dir_results, key=lambda x: x["sharpe"])
                pct = best_dir_pct
                print(f"  Best ({best_dir}): LB={best['lookback']}, R={best['rebal']}, "
                      f"N={best['n']}")
                print(f"    Sharpe={best['sharpe']:.3f}, Ann={best['ann_ret']:.1f}%, "
                      f"DD={best['max_dd']:.1f}%")
            else:
                print(f"\n  *** REJECTED at IS stage ({pct:.1f}% overall, "
                      f"best direction {best_dir_pct:.1f}%) ***")
                continue

        # Walk-forward
        print(f"\n  Walk-Forward OOS (6-fold):")
        wf = walk_forward(closes, factor_fn, best["lookback"], best["rebal"],
                          best["n"], best["direction"], extra)
        wf_pos = sum(1 for s in wf if s > 0)
        wf_mean = np.mean(wf)
        print(f"    Fold Sharpes: {[f'{s:.3f}' for s in wf]}")
        print(f"    Positive: {wf_pos}/{len(wf)}, Mean: {wf_mean:.3f}")

        if wf_pos < 4:
            print(f"\n  *** REJECTED at WF stage ({wf_pos}/6 < 4) ***")
            continue

        # Split-half
        s1, s2 = split_half_test(closes, factor_fn, best["lookback"],
                                  best["rebal"], best["n"], best["direction"],
                                  extra)
        sh_pass = s1 > 0 and s2 > 0
        print(f"\n  Split-Half: H1={s1:.3f}, H2={s2:.3f} — {'PASS' if sh_pass else 'FAIL'}")

        # H-012 correlation
        corr = compute_h012_correlation(closes, factor_fn, best["lookback"],
                                         best["rebal"], best["n"],
                                         best["direction"], extra)
        print(f"  H-012 Correlation: {corr}")

        # Neighboring params
        param_neighbors = [r for r in results
                           if abs(r["lookback"] - best["lookback"]) <= 5
                           and abs(r["rebal"] - best["rebal"]) <= 2
                           and r["direction"] == best["direction"]]
        neighbor_pos = sum(1 for r in param_neighbors if r["sharpe"] > 0)
        neighbor_pct = neighbor_pos / len(param_neighbors) * 100 if param_neighbors else 0
        print(f"  Neighboring params: {neighbor_pos}/{len(param_neighbors)} positive "
              f"({neighbor_pct:.1f}%)")

        status = "CONFIRMED" if (wf_pos >= 4 and sh_pass) else "BORDERLINE"
        print(f"\n  *** {status} *** "
              f"IS={pct:.0f}% WF={wf_pos}/6(mean {wf_mean:.3f}) "
              f"SH={'PASS' if sh_pass else 'FAIL'} Corr={corr}")


if __name__ == "__main__":
    main()
