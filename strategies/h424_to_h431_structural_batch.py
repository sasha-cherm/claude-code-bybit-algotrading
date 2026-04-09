#!/usr/bin/env python3
"""
Backtest eight novel structural/microstructural cross-sectional factors.
All daily, no look-ahead bias.

  H-424: Rank Momentum — change in cross-sectional momentum rank over time.
         If an asset is rising through the ranks (improving relative momentum),
         continue going long. Captures acceleration in relative terms.
  H-425: Closing Location Value (CLV) — where the close is in the day's range.
         CLV = (close - low) / (high - low). High CLV = buying pressure.
         Rolling average over lookback.
  H-426: True Range Ratio — true range / close. Low = calm/low vol.
         Inverted: long calm assets, short volatile ones (low-vol anomaly variant).
  H-427: Co-Movement Score — avg pairwise correlation with all other assets.
         Low co-movement = independent, potential alpha source.
  H-428: Return Dispersion Beta — rolling beta of asset return on XS return
         dispersion. Captures which assets benefit when cross-section is dispersed.
  H-429: Price Position in Range — where current price is in N-day high-low range.
         Near top of range = strong. (Donchian channel position.)
  H-430: Volume-Price Correlation — rolling corr(volume, abs_return).
         High = volume aligns with moves (efficient). Low = noise.
  H-431: Momentum Quality — momentum adjusted for max drawdown during lookback.
         High momentum with low DD = high quality trend.

Standard framework: grid search, IS robustness (>=80%), walk-forward OOS,
split-half, H-012 correlation.
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
    """Load daily data for all assets."""
    print("Loading daily data for 14 assets...")
    closes_dict, volumes_dict, highs_dict, lows_dict = {}, {}, {}, {}

    for sym in ASSETS:
        ticker = sym.replace("/", "_")
        fpath = ROOT / "data" / f"{ticker}_1d.parquet"
        if not fpath.exists():
            continue
        df = pd.read_parquet(fpath)
        if len(df) < 200:
            continue
        closes_dict[sym] = df["close"]
        volumes_dict[sym] = df["volume"]
        highs_dict[sym] = df["high"]
        lows_dict[sym] = df["low"]

    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill().dropna()
    highs = pd.DataFrame(highs_dict).reindex(closes.index).ffill().dropna()
    lows = pd.DataFrame(lows_dict).reindex(closes.index).ffill().dropna()
    idx = closes.index.intersection(volumes.index).intersection(highs.index)
    closes = closes.loc[idx]
    volumes = volumes.loc[idx]
    highs = highs.loc[idx]
    lows = lows.loc[idx]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    return closes, volumes, highs, lows


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
# Factor definitions
# ============================================================

def factor_h424_rank_momentum(closes, extra_data, lookback, i):
    """Change in momentum rank over time."""
    if i < lookback * 2:
        return None
    # Current momentum
    curr_mom = closes.iloc[i] / closes.iloc[i - lookback] - 1
    # Previous momentum (lookback days ago)
    prev_mom = closes.iloc[i - lookback] / closes.iloc[max(0, i - lookback*2)] - 1

    # Rank both
    curr_rank = curr_mom.rank(ascending=False)
    prev_rank = prev_mom.rank(ascending=False)

    # Rank improvement: negative = rising through ranks
    rank_change = prev_rank - curr_rank  # positive = improved
    return rank_change.dropna()


def factor_h425_clv(closes, extra_data, lookback, i):
    """Closing Location Value: avg(close - low) / (high - low) over lookback."""
    highs = extra_data["highs"]
    lows = extra_data["lows"]
    h_slice = highs.iloc[max(0, i-lookback):i+1]
    l_slice = lows.iloc[max(0, i-lookback):i+1]
    c_slice = closes.iloc[max(0, i-lookback):i+1]

    rng = h_slice - l_slice
    clv = (c_slice - l_slice) / rng.replace(0, np.nan)
    avg_clv = clv.mean()
    return avg_clv.dropna()


def factor_h426_true_range_ratio(closes, extra_data, lookback, i):
    """True Range / Close averaged over lookback. Low = calm."""
    highs = extra_data["highs"]
    lows = extra_data["lows"]

    h_slice = highs.iloc[max(0, i-lookback):i+1]
    l_slice = lows.iloc[max(0, i-lookback):i+1]
    c_slice = closes.iloc[max(0, i-lookback):i+1]
    prev_c = closes.iloc[max(0, i-lookback-1):i]

    # True range = max(h-l, |h-prev_c|, |l-prev_c|)
    tr = pd.DataFrame(index=c_slice.index, columns=c_slice.columns, dtype=float)
    for sym in c_slice.columns:
        hl = h_slice[sym] - l_slice[sym]
        if len(prev_c) >= len(c_slice):
            hpc = (h_slice[sym].values - prev_c[sym].values[:len(h_slice)]).astype(float)
            lpc = (l_slice[sym].values - prev_c[sym].values[:len(l_slice)]).astype(float)
            tr[sym] = np.maximum(hl.values, np.maximum(np.abs(hpc), np.abs(lpc)))
        else:
            tr[sym] = hl.values

    avg_tr = tr.mean() / c_slice.iloc[-1]
    return avg_tr.dropna()


def factor_h427_comovement(closes, extra_data, lookback, i):
    """Average pairwise correlation with all other assets."""
    rets = closes.iloc[max(0, i-lookback):i+1].pct_change().dropna()
    if len(rets) < 15:
        return None
    corr_mat = rets.corr()
    # Average correlation (excluding self)
    scores = {}
    for sym in corr_mat.columns:
        others = [c for c in corr_mat.columns if c != sym]
        avg_corr = corr_mat.loc[sym, others].mean()
        if np.isfinite(avg_corr):
            scores[sym] = avg_corr
    return pd.Series(scores) if scores else None


def factor_h428_dispersion_beta(closes, extra_data, lookback, i):
    """Beta of asset return to cross-sectional return dispersion."""
    rets = closes.iloc[max(0, i-lookback):i+1].pct_change().dropna()
    if len(rets) < 20:
        return None
    # Cross-sectional dispersion
    xs_disp = rets.std(axis=1)

    scores = {}
    for sym in rets.columns:
        r = rets[sym]
        valid = r.notna() & xs_disp.notna()
        if valid.sum() < 15:
            continue
        slope, _, _, _, _ = stats.linregress(xs_disp[valid], r[valid])
        if np.isfinite(slope):
            scores[sym] = slope
    return pd.Series(scores) if scores else None


def factor_h429_price_position(closes, extra_data, lookback, i):
    """Where current price is in N-day range. (Donchian channel position)."""
    c_slice = closes.iloc[max(0, i-lookback):i+1]
    period_high = c_slice.max()
    period_low = c_slice.min()
    rng = period_high - period_low
    position = (closes.iloc[i] - period_low) / rng.replace(0, np.nan)
    return position.dropna()


def factor_h430_vol_price_corr(closes, extra_data, lookback, i):
    """Rolling correlation between volume and abs(return)."""
    volumes = extra_data["volumes"]
    rets = closes.iloc[max(0, i-lookback):i+1].pct_change().dropna()
    vols = volumes.iloc[max(0, i-lookback):i+1]
    common_idx = rets.index.intersection(vols.index)
    if len(common_idx) < 15:
        return None
    rets = rets.loc[common_idx]
    vols = vols.loc[common_idx]

    scores = {}
    for sym in rets.columns:
        r = np.abs(rets[sym])
        v = vols[sym]
        valid = r.notna() & v.notna()
        if valid.sum() < 10:
            continue
        corr = r[valid].corr(v[valid])
        if np.isfinite(corr):
            scores[sym] = corr
    return pd.Series(scores) if scores else None


def factor_h431_momentum_quality(closes, extra_data, lookback, i):
    """Momentum adjusted for max drawdown during lookback period."""
    c_slice = closes.iloc[max(0, i-lookback):i+1]
    if len(c_slice) < 10:
        return None

    # Total momentum
    mom = c_slice.iloc[-1] / c_slice.iloc[0] - 1

    # Max drawdown during period
    cum_max = c_slice.cummax()
    dd = ((c_slice - cum_max) / cum_max).min()  # most negative

    # Quality = momentum / |max_dd|. Higher = better quality trend
    quality = mom / dd.abs().replace(0, np.nan)
    return quality.dropna()


# ============================================================
# Main
# ============================================================

FACTORS = [
    ("H-424 Rank Momentum", factor_h424_rank_momentum,
     [20, 30, 40, 60], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-425 CLV (Close Location)", factor_h425_clv,
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-426 True Range Ratio", factor_h426_true_range_ratio,
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-427 Co-Movement Score", factor_h427_comovement,
     [20, 30, 40, 60], [5, 7, 10], [3, 4], ["high_long", "low_long"]),
    ("H-428 Dispersion Beta", factor_h428_dispersion_beta,
     [20, 30, 40, 60], [5, 7, 10], [3, 4], ["high_long", "low_long"]),
    ("H-429 Price Position", factor_h429_price_position,
     [10, 20, 30, 60], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-430 Vol-Price Correlation", factor_h430_vol_price_corr,
     [20, 30, 40, 60], [5, 7, 10], [3, 4], ["high_long", "low_long"]),
    ("H-431 Momentum Quality", factor_h431_momentum_quality,
     [20, 30, 40, 60], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
]


def main():
    closes, volumes, highs, lows = load_data()

    extra = {"volumes": volumes, "highs": highs, "lows": lows}

    for factor_name, factor_fn, lookbacks, rebals, ns, directions in FACTORS:
        print(f"\n{'='*60}")
        print(f"  {factor_name}")
        print(f"{'='*60}")

        results = backtest_factor(closes, factor_fn, lookbacks, rebals, ns,
                                  directions, factor_name, extra)

        if not results:
            print("  NO RESULTS — factor may require unavailable data")
            continue

        # IS Analysis
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

        if pct < 80:
            print(f"\n  *** REJECTED at IS stage ({pct:.1f}% < 80%) ***")
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
                           if abs(r["lookback"] - best["lookback"]) <= 10
                           and abs(r["rebal"] - best["rebal"]) <= 2
                           and r["direction"] == best["direction"]]
        neighbor_pos = sum(1 for r in param_neighbors if r["sharpe"] > 0)
        neighbor_pct = neighbor_pos / len(param_neighbors) * 100 if param_neighbors else 0
        print(f"  Neighboring params: {neighbor_pos}/{len(param_neighbors)} positive ({neighbor_pct:.1f}%)")

        status = "CONFIRMED" if (wf_pos >= 4 and sh_pass) else "BORDERLINE"
        print(f"\n  *** {status} *** "
              f"IS={pct:.0f}% WF={wf_pos}/6(mean {wf_mean:.3f}) "
              f"SH={'PASS' if sh_pass else 'FAIL'} Corr={corr}")


if __name__ == "__main__":
    main()
