#!/usr/bin/env python3
"""
Backtest eight novel XS factors using HOURLY data for signal construction,
but trading on daily rebalance (to keep fees manageable).
All signals use data strictly BEFORE the trading day (no look-ahead).

  H-432: Hourly Volume Herfindahl — how concentrated is trading volume within
         each day? High concentration = one big session dominates = institutional.
         Compute HHI of hourly volume shares within each day. Use LAGGED (yesterday's).
  H-433: Asian/US Session Return Spread — difference between Asian session return
         (00-08 UTC) and US session return (14-22 UTC). Captures institutional flow
         rotation. High spread = Asia leads = different flow dynamics.
  H-434: Overnight Gap Fill Rate — what fraction of overnight gaps (close→open) get
         filled during the next session? High fill rate = mean-reverting asset.
  H-435: Hourly Return Kurtosis — excess kurtosis of hourly returns. High kurtosis
         = fat tails = jump risk. Long low-kurtosis (calm), short high (jumpy).
  H-436: Volume-Weighted Momentum (hourly) — momentum where each hourly bar's return
         is weighted by its relative volume. High-volume hours count more.
  H-437: Bid-Ask Proxy (High-Low-Close) — intraday (high-low)/close as a proxy for
         bid-ask spread. Rolling average. Low spread = liquid = long.
  H-438: Intraday Momentum Share — what fraction of the daily return comes from
         the largest single hourly move? High = one-shot momentum = fragile.
  H-439: Hourly Volume Trend (intraday) — is volume increasing or decreasing
         throughout the day? Slope of hourly volume within each day. Up = accumulation,
         down = distribution.

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
    """Load daily + hourly data."""
    print("Loading daily + hourly data for 14 assets...")
    closes_dict, volumes_dict = {}, {}
    hourly_dict = {}

    for sym in ASSETS:
        ticker = sym.replace("/", "_")
        # Daily
        fpath_d = ROOT / "data" / f"{ticker}_1d.parquet"
        if not fpath_d.exists():
            continue
        df = pd.read_parquet(fpath_d)
        if len(df) < 200:
            continue
        closes_dict[sym] = df["close"]
        volumes_dict[sym] = df["volume"]

        # Hourly
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
    """Pre-compute daily features from hourly data (LAGGED — use yesterday's hourly)."""
    print("Pre-computing hourly features (lagged)...")
    dates = closes.index
    syms = closes.columns

    # Features indexed by date (using PREVIOUS day's hourly data)
    vol_hhi = pd.DataFrame(index=dates, columns=syms, dtype=float)
    asia_us_spread = pd.DataFrame(index=dates, columns=syms, dtype=float)
    gap_fill_rate = pd.DataFrame(index=dates, columns=syms, dtype=float)
    hourly_kurtosis = pd.DataFrame(index=dates, columns=syms, dtype=float)
    vw_momentum = pd.DataFrame(index=dates, columns=syms, dtype=float)
    hl_spread = pd.DataFrame(index=dates, columns=syms, dtype=float)
    mom_share = pd.DataFrame(index=dates, columns=syms, dtype=float)
    vol_trend_intraday = pd.DataFrame(index=dates, columns=syms, dtype=float)

    for sym in syms:
        if sym not in hourly_dict:
            continue
        hdf = hourly_dict[sym]
        hdf = hdf.sort_index()

        for di in range(1, len(dates)):
            date_i = dates[di]
            prev_date = dates[di - 1]

            # Get PREVIOUS day's hourly bars
            mask = (hdf.index >= prev_date) & (hdf.index < date_i)
            day_bars = hdf.loc[mask]
            if len(day_bars) < 12:
                continue

            h_vol = day_bars["volume"].values
            h_close = day_bars["close"].values
            h_high = day_bars["high"].values
            h_low = day_bars["low"].values
            h_open = day_bars["open"].values if "open" in day_bars else h_close

            # H-432: Volume Herfindahl
            total_v = h_vol.sum()
            if total_v > 0:
                shares = h_vol / total_v
                hhi = np.sum(shares ** 2)
                vol_hhi.at[date_i, sym] = hhi

            # H-433: Asian/US session return spread
            hours = day_bars.index.hour if hasattr(day_bars.index, 'hour') else pd.Series(day_bars.index).dt.hour.values
            asia_mask = (hours >= 0) & (hours < 8)
            us_mask = (hours >= 14) & (hours < 22)
            if asia_mask.sum() >= 4 and us_mask.sum() >= 4:
                asia_ret = h_close[asia_mask][-1] / h_close[asia_mask][0] - 1 if h_close[asia_mask][0] != 0 else 0
                us_ret = h_close[us_mask][-1] / h_close[us_mask][0] - 1 if h_close[us_mask][0] != 0 else 0
                asia_us_spread.at[date_i, sym] = asia_ret - us_ret

            # H-434: Gap fill rate (simplified: did price return to previous close?)
            if di >= 2 and len(h_close) > 1:
                prev_prev = dates[di - 2] if di >= 2 else dates[0]
                prev_mask = (hdf.index >= prev_prev) & (hdf.index < prev_date)
                prev_bars = hdf.loc[prev_mask]
                if len(prev_bars) > 0:
                    prev_close = prev_bars["close"].iloc[-1]
                    day_open = h_close[0]
                    gap = day_open - prev_close
                    if abs(gap) > 0:
                        # How much of the gap was filled?
                        if gap > 0:
                            min_price = min(h_low)
                            fill = max(0, gap - (min_price - prev_close)) / gap
                        else:
                            max_price = max(h_high)
                            fill = max(0, abs(gap) - (prev_close - max_price)) / abs(gap)
                        gap_fill_rate.at[date_i, sym] = min(fill, 1.0)

            # H-435: Hourly return kurtosis
            h_rets = np.diff(h_close) / h_close[:-1]
            h_rets = h_rets[np.isfinite(h_rets)]
            if len(h_rets) >= 8:
                kurt = stats.kurtosis(h_rets, fisher=True)
                if np.isfinite(kurt):
                    hourly_kurtosis.at[date_i, sym] = kurt

            # H-436: Volume-weighted momentum
            if total_v > 0 and len(h_rets) > 0:
                # Align returns with volume (rets has len-1)
                vw = np.sum(h_rets * h_vol[1:] / total_v)
                if np.isfinite(vw):
                    vw_momentum.at[date_i, sym] = vw

            # H-437: H-L spread proxy
            avg_hl = np.mean((h_high - h_low) / np.where(h_close > 0, h_close, 1))
            if np.isfinite(avg_hl):
                hl_spread.at[date_i, sym] = avg_hl

            # H-438: Momentum share (largest hourly move / total daily move)
            if len(h_rets) > 0:
                daily_ret = h_close[-1] / h_close[0] - 1 if h_close[0] != 0 else 0
                if abs(daily_ret) > 1e-6:
                    max_hourly = np.max(np.abs(h_rets))
                    mom_share.at[date_i, sym] = max_hourly / abs(daily_ret)

            # H-439: Volume trend intraday
            if len(h_vol) >= 6:
                x = np.arange(len(h_vol))
                slope, _, _, _, _ = stats.linregress(x, np.log1p(h_vol))
                if np.isfinite(slope):
                    vol_trend_intraday.at[date_i, sym] = slope

    features = {
        "vol_hhi": vol_hhi,
        "asia_us_spread": asia_us_spread,
        "gap_fill_rate": gap_fill_rate,
        "hourly_kurtosis": hourly_kurtosis,
        "vw_momentum": vw_momentum,
        "hl_spread": hl_spread,
        "mom_share": mom_share,
        "vol_trend_intraday": vol_trend_intraday,
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


# ============================================================
# Factor definitions (using pre-computed hourly features)
# ============================================================

def make_rolling_factor(feature_key, agg="mean"):
    """Create a factor that uses rolling average of a precomputed daily feature."""
    def factor_fn(closes, extra_data, lookback, i):
        feat = extra_data["features"][feature_key]
        feat_slice = feat.iloc[max(0, i-lookback):i]  # STRICTLY < i (lagged)
        if len(feat_slice) < 5:
            return None
        if agg == "mean":
            score = feat_slice.mean()
        elif agg == "median":
            score = feat_slice.median()
        elif agg == "slope":
            scores = {}
            x = np.arange(len(feat_slice))
            for sym in feat_slice.columns:
                y = feat_slice[sym].dropna()
                if len(y) < 5:
                    continue
                sl, _, _, _, _ = stats.linregress(np.arange(len(y)), y.values)
                if np.isfinite(sl):
                    scores[sym] = sl
            return pd.Series(scores) if scores else None
        else:
            score = feat_slice.mean()
        return score.dropna()
    return factor_fn


# ============================================================
# Main
# ============================================================

FACTORS = [
    ("H-432 Volume HHI", "vol_hhi", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-433 Asia-US Spread", "asia_us_spread", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-434 Gap Fill Rate", "gap_fill_rate", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-435 Hourly Kurtosis", "hourly_kurtosis", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-436 VW Momentum", "vw_momentum", "mean",
     [5, 10, 15, 20], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-437 HL Spread Proxy", "hl_spread", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-438 Momentum Share", "mom_share", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-439 Vol Trend Intraday", "vol_trend_intraday", "mean",
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
]


def main():
    closes, volumes, hourly_dict = load_data()

    # Pre-compute hourly features
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

        # Also check per-direction
        for d in directions:
            d_results = [r for r in results if r["direction"] == d]
            d_pos = sum(1 for r in d_results if r["sharpe"] > 0)
            d_pct = d_pos / len(d_results) * 100 if d_results else 0
            print(f"    {d}: {d_pos}/{len(d_results)} positive ({d_pct:.1f}%)")

        if pct < 80:
            # Check if one direction alone passes
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
                # Recompute best for winning direction
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
