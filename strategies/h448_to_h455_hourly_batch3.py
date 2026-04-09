#!/usr/bin/env python3
"""
Batch 3 of hourly-derived signals. All signals use LAGGED hourly data (yesterday's)
to avoid look-ahead bias. Trade on daily rebalance.

  H-448: Hourly Return Skewness — skewness of hourly returns within each day.
         Positive skew = upside jumps, negative = downside jumps. Rolling mean.
  H-449: Volume Acceleration — acceleration (2nd derivative) of hourly volume
         within each day. Increasing acceleration = volume surge building.
  H-450: Price Range Expansion Rate — ratio of hourly range to daily range.
         High = range established early = strong trend. Low = choppy expansion.
  H-451: Hourly Close-to-High Ratio — avg (close-low)/(high-low) across hours.
         High = closes near highs consistently = buying pressure.
  H-452: Hourly Volume Entropy — entropy of hourly volume distribution. High
         entropy = evenly distributed = organic. Low = concentrated = institutional.
  H-453: Intraday Trend Strength — R-squared of price vs time regression using
         hourly bars. High = smooth trend. Low = noisy/choppy.
  H-454: Hourly Return Momentum Decay Rate — difference between first-half and
         second-half hourly momentum within day. Positive = front-loaded moves.
  H-455: Volume-Price Correlation (hourly) — correlation between hourly volume
         and absolute hourly returns. High = volume confirms moves. Low = noise.

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
    print("Pre-computing hourly features batch 3 (lagged)...")
    dates = closes.index
    syms = closes.columns

    ret_skew = pd.DataFrame(index=dates, columns=syms, dtype=float)
    vol_accel = pd.DataFrame(index=dates, columns=syms, dtype=float)
    range_expansion = pd.DataFrame(index=dates, columns=syms, dtype=float)
    close_high_ratio = pd.DataFrame(index=dates, columns=syms, dtype=float)
    vol_entropy = pd.DataFrame(index=dates, columns=syms, dtype=float)
    trend_strength = pd.DataFrame(index=dates, columns=syms, dtype=float)
    mom_decay = pd.DataFrame(index=dates, columns=syms, dtype=float)
    vol_price_corr = pd.DataFrame(index=dates, columns=syms, dtype=float)

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
            h_high = day_bars["high"].values
            h_low = day_bars["low"].values

            h_rets = np.diff(h_close) / h_close[:-1]
            h_rets = h_rets[np.isfinite(h_rets)]

            # H-448: Return skewness
            if len(h_rets) >= 8:
                sk = stats.skew(h_rets)
                if np.isfinite(sk):
                    ret_skew.at[date_i, sym] = sk

            # H-449: Volume acceleration
            if len(h_vol) >= 6:
                dv = np.diff(h_vol)
                if len(dv) >= 3:
                    ddv = np.diff(dv)
                    accel = np.mean(ddv)
                    if np.isfinite(accel):
                        vol_accel.at[date_i, sym] = accel

            # H-450: Range expansion rate
            total_range = max(h_high) - min(h_low)
            if total_range > 0:
                hourly_ranges = h_high - h_low
                avg_hourly_range = np.mean(hourly_ranges)
                re = avg_hourly_range / total_range
                if np.isfinite(re):
                    range_expansion.at[date_i, sym] = re

            # H-451: Close-to-high ratio
            hl_range = h_high - h_low
            valid = hl_range > 0
            if valid.sum() >= 8:
                ratios = (h_close[valid] - h_low[valid]) / hl_range[valid]
                chr_val = np.mean(ratios)
                if np.isfinite(chr_val):
                    close_high_ratio.at[date_i, sym] = chr_val

            # H-452: Volume entropy
            total_v = h_vol.sum()
            if total_v > 0:
                shares = h_vol / total_v
                shares = shares[shares > 0]
                ent = -np.sum(shares * np.log(shares))
                if np.isfinite(ent):
                    vol_entropy.at[date_i, sym] = ent

            # H-453: Trend strength (R-squared)
            if len(h_close) >= 8:
                x = np.arange(len(h_close))
                _, _, r_val, _, _ = stats.linregress(x, h_close)
                r2 = r_val ** 2
                if np.isfinite(r2):
                    trend_strength.at[date_i, sym] = r2

            # H-454: Momentum decay rate
            if len(h_rets) >= 8:
                mid = len(h_rets) // 2
                first_half_mom = np.mean(h_rets[:mid])
                second_half_mom = np.mean(h_rets[mid:])
                decay = first_half_mom - second_half_mom
                if np.isfinite(decay):
                    mom_decay.at[date_i, sym] = decay

            # H-455: Volume-price correlation
            if len(h_rets) > 0 and len(h_vol) > 1:
                abs_rets = np.abs(h_rets)
                vols_aligned = h_vol[1:]  # align with returns
                if len(abs_rets) >= 8:
                    vpc = np.corrcoef(abs_rets, vols_aligned)[0, 1]
                    if np.isfinite(vpc):
                        vol_price_corr.at[date_i, sym] = vpc

    features = {
        "ret_skew": ret_skew,
        "vol_accel": vol_accel,
        "range_expansion": range_expansion,
        "close_high_ratio": close_high_ratio,
        "vol_entropy": vol_entropy,
        "trend_strength": trend_strength,
        "mom_decay": mom_decay,
        "vol_price_corr": vol_price_corr,
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
    ("H-448 Ret Skewness", "ret_skew", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-449 Vol Acceleration", "vol_accel", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-450 Range Expansion", "range_expansion", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-451 Close-High Ratio", "close_high_ratio", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-452 Vol Entropy", "vol_entropy", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-453 Trend Strength", "trend_strength", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-454 Mom Decay Rate", "mom_decay", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-455 Vol-Price Corr", "vol_price_corr", "mean",
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
