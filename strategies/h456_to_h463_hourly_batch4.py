#!/usr/bin/env python3
"""
Batch 4 of hourly-derived signals. All signals use LAGGED hourly data (yesterday's)
to avoid look-ahead bias. Trade on daily rebalance.

  H-456: Volume-Weighted Return — avg return weighted by volume across hours.
         High = volume confirms direction = informed buying/selling.
  H-457: Intraday Autocorrelation — lag-1 autocorrelation of hourly returns.
         Negative = mean-reverting intraday. Positive = trending.
  H-458: Up Volume Ratio — volume on green hours / total volume.
         High = buying pressure dominant. Low = selling pressure.
  H-459: Hourly Amihud Illiquidity — mean |return|/volume across hours.
         High = illiquid (big moves on little volume). Low = liquid.
  H-460: Intraday Close Position — (close - open) / (high - low) for the day
         using first/last hourly bar open/close and overall high/low.
  H-461: Volume Herfindahl (HHI) — HHI of hourly volume distribution.
         High = concentrated in few hours = institutional. Low = distributed.
  H-462: Breakout Persistence — max consecutive same-sign hourly returns / total.
         High = strong intraday trend. Low = choppy.
  H-463: Return Asymmetry — max(hourly ret) / abs(min(hourly ret)).
         >1 = upside moves larger. <1 = downside moves larger.

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
    print("Pre-computing hourly features batch 4 (lagged)...")
    dates = closes.index
    syms = closes.columns

    vw_return = pd.DataFrame(index=dates, columns=syms, dtype=float)
    intraday_ac = pd.DataFrame(index=dates, columns=syms, dtype=float)
    up_vol_ratio = pd.DataFrame(index=dates, columns=syms, dtype=float)
    amihud_illiq = pd.DataFrame(index=dates, columns=syms, dtype=float)
    close_position = pd.DataFrame(index=dates, columns=syms, dtype=float)
    vol_hhi = pd.DataFrame(index=dates, columns=syms, dtype=float)
    breakout_persist = pd.DataFrame(index=dates, columns=syms, dtype=float)
    ret_asymmetry = pd.DataFrame(index=dates, columns=syms, dtype=float)

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

            # H-456: Volume-weighted return
            if len(h_rets) > 0:
                vol_aligned = h_vol[1:]  # align with returns
                total_v = vol_aligned.sum()
                if total_v > 0:
                    vwr = np.sum(h_rets * vol_aligned) / total_v
                    if np.isfinite(vwr):
                        vw_return.at[date_i, sym] = vwr

            # H-457: Intraday autocorrelation (lag-1)
            if len(h_rets) >= 10:
                ac = np.corrcoef(h_rets[:-1], h_rets[1:])[0, 1]
                if np.isfinite(ac):
                    intraday_ac.at[date_i, sym] = ac

            # H-458: Up volume ratio
            total_v = h_vol.sum()
            if total_v > 0 and len(h_rets) > 0:
                up_mask = h_rets > 0
                up_v = h_vol[1:][up_mask].sum()  # volume on positive-return hours
                uvr = up_v / total_v
                if np.isfinite(uvr):
                    up_vol_ratio.at[date_i, sym] = uvr

            # H-459: Hourly Amihud illiquidity
            if len(h_rets) > 0:
                vol_aligned = h_vol[1:]
                valid_mask = vol_aligned > 0
                if valid_mask.sum() >= 8:
                    illiq_vals = np.abs(h_rets[valid_mask]) / vol_aligned[valid_mask]
                    ai = np.mean(illiq_vals)
                    if np.isfinite(ai) and ai < 1e10:  # sanity check
                        amihud_illiq.at[date_i, sym] = ai

            # H-460: Close position index
            day_high = np.max(h_high)
            day_low = np.min(h_low)
            day_open = h_open[0]
            day_close = h_close[-1]
            day_range = day_high - day_low
            if day_range > 0:
                cpi = (day_close - day_open) / day_range
                if np.isfinite(cpi):
                    close_position.at[date_i, sym] = cpi

            # H-461: Volume HHI
            total_v = h_vol.sum()
            if total_v > 0:
                shares = h_vol / total_v
                hhi = np.sum(shares ** 2)
                if np.isfinite(hhi):
                    vol_hhi.at[date_i, sym] = hhi

            # H-462: Breakout persistence
            if len(h_rets) >= 8:
                signs = np.sign(h_rets)
                max_streak = 1
                current_streak = 1
                for j in range(1, len(signs)):
                    if signs[j] == signs[j-1] and signs[j] != 0:
                        current_streak += 1
                        max_streak = max(max_streak, current_streak)
                    else:
                        current_streak = 1
                bp = max_streak / len(h_rets)
                if np.isfinite(bp):
                    breakout_persist.at[date_i, sym] = bp

            # H-463: Return asymmetry
            if len(h_rets) >= 8:
                max_ret = np.max(h_rets)
                min_ret = np.min(h_rets)
                if min_ret < 0 and max_ret > 0:
                    asym = max_ret / abs(min_ret)
                    if np.isfinite(asym) and asym < 100:
                        ret_asymmetry.at[date_i, sym] = asym

    features = {
        "vw_return": vw_return,
        "intraday_ac": intraday_ac,
        "up_vol_ratio": up_vol_ratio,
        "amihud_illiq": amihud_illiq,
        "close_position": close_position,
        "vol_hhi": vol_hhi,
        "breakout_persist": breakout_persist,
        "ret_asymmetry": ret_asymmetry,
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
    ("H-456 VW Return", "vw_return", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-457 Intraday Autocorr", "intraday_ac", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-458 Up Vol Ratio", "up_vol_ratio", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-459 Amihud Illiquidity", "amihud_illiq", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-460 Close Position", "close_position", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-461 Vol HHI", "vol_hhi", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-462 Breakout Persist", "breakout_persist", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-463 Ret Asymmetry", "ret_asymmetry", "mean",
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
