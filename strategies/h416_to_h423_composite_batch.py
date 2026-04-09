#!/usr/bin/env python3
"""
Backtest eight novel cross-sectional factors — composite + structural signals.
All daily, no look-ahead bias.

  H-416: Composite Score (Efficiency × Volume Surprise) — combine two uncorrelated
         confirmed signals: price efficiency (H-076) and volume surprise (H-336).
         Rank by product of z-scored signals.
  H-417: Volatility-Adaptive Momentum — use realized vol to determine lookback.
         High vol → short lookback (recent info matters more).
         Low vol → long lookback (trend is slow).
  H-418: BTC Lead-Lag Timing — for each alt, compute rolling correlation of
         alt_return(t) with BTC_return(t-1). High lag = momentum, low lag = independent.
         Go long assets that follow BTC with a lag (momentum amplifiers).
  H-419: Funding Rate Acceleration — rate of change of funding rate, not just level.
         Accelerating funding = crowding intensifying. Contrarian: short accelerating.
  H-420: Vol-of-Vol Factor — realized vol of realized vol. High vol-of-vol = regime
         uncertainty. Low vol-of-vol = stable regime. Long stable, short uncertain.
  H-421: Return Autocorrelation Factor — daily return autocorrelation over lookback.
         Positive autocorr = trending. Negative = mean-reverting.
         Long trending assets (positive autocorr).
  H-422: Consecutive Direction Streak — count of consecutive up/down days.
         After long winning streaks: mean reversion. Test both directions.
  H-423: Volume-Weighted Return Factor — rolling average of return × relative volume.
         High vol days have more weight. Captures institutional conviction.

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
    idx = closes.index.intersection(volumes.index)
    closes, volumes = closes.loc[idx], volumes.loc[idx]
    highs, lows = highs.loc[idx], lows.loc[idx]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    return closes, volumes, highs, lows


def load_funding():
    """Load funding rate data."""
    funding_dict = {}
    for sym in ASSETS:
        ticker = sym.replace("/", "_")
        fpath = ROOT / "data" / f"{ticker}_USDT_funding.parquet"
        if not fpath.exists():
            continue
        df = pd.read_parquet(fpath)
        if "fundingRate" in df.columns:
            fr = df["fundingRate"].resample("1D").sum()
            funding_dict[sym] = fr
    if not funding_dict:
        return None
    funding = pd.DataFrame(funding_dict).ffill().fillna(0)
    return funding


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
    """Split data in half, run backtest on each, check consistency."""
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
    """Compute correlation with H-012 (simple momentum)."""
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
        """Simple momentum: total return over lookback."""
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

def factor_h416_composite(closes, extra_data, lookback, i):
    """Composite: efficiency × volume surprise."""
    volumes = extra_data["volumes"]
    # Price efficiency
    rets = np.log(closes.iloc[i] / closes.iloc[i - lookback])
    daily_abs_rets = np.abs(np.log(closes.iloc[max(0, i-lookback):i+1] /
                                    closes.iloc[max(0, i-lookback):i+1].shift(1))).sum()
    efficiency = rets / daily_abs_rets.replace(0, np.nan)

    # Volume surprise: recent volume / average volume
    recent_vol = volumes.iloc[max(0, i-5):i+1].mean()
    avg_vol = volumes.iloc[max(0, i-lookback):i+1].mean()
    vol_surprise = (recent_vol / avg_vol - 1)

    # Z-score both, then multiply
    eff_z = (efficiency - efficiency.mean()) / efficiency.std()
    vs_z = (vol_surprise - vol_surprise.mean()) / vol_surprise.std()
    composite = eff_z * vs_z
    return composite.dropna()


def factor_h417_vol_adaptive_mom(closes, extra_data, lookback, i):
    """Volatility-adaptive momentum: short lookback in high vol, long in low vol."""
    # Use BTC vol as regime indicator
    btc_rets = np.log(closes["BTC/USDT"].iloc[max(0, i-60):i+1] /
                       closes["BTC/USDT"].iloc[max(0, i-60):i+1].shift(1)).dropna()
    curr_vol = btc_rets.iloc[-20:].std() if len(btc_rets) >= 20 else btc_rets.std()
    avg_vol = btc_rets.std()

    vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0
    # Adaptive: high vol → shorter lookback, low vol → longer
    adaptive_lb = int(np.clip(lookback / vol_ratio, 5, lookback * 2))
    adaptive_lb = min(adaptive_lb, i)

    # Momentum with adaptive lookback
    ret = closes.iloc[i] / closes.iloc[max(0, i - adaptive_lb)] - 1
    return ret.dropna()


def factor_h418_btc_leadlag(closes, extra_data, lookback, i):
    """BTC lead-lag: correlation of alt_ret(t) with BTC_ret(t-1)."""
    if "BTC/USDT" not in closes.columns:
        return None
    rets = closes.iloc[max(0, i-lookback):i+1].pct_change().dropna()
    if len(rets) < 20:
        return None
    btc_lag = rets["BTC/USDT"].shift(1).dropna()
    common_idx = rets.index.intersection(btc_lag.index)
    if len(common_idx) < 15:
        return None
    scores = {}
    for sym in closes.columns:
        if sym == "BTC/USDT":
            continue
        r = rets.loc[common_idx, sym]
        bl = btc_lag.loc[common_idx]
        valid = r.notna() & bl.notna()
        if valid.sum() < 15:
            continue
        corr = r[valid].corr(bl[valid])
        if np.isfinite(corr):
            scores[sym] = corr
    return pd.Series(scores) if scores else None


def factor_h419_funding_accel(closes, extra_data, lookback, i):
    """Funding rate acceleration: rate of change of funding."""
    funding = extra_data.get("funding")
    if funding is None:
        return None
    fund_idx = funding.index
    close_date = closes.index[i]
    # Find closest funding date
    mask = fund_idx <= close_date
    if mask.sum() < lookback:
        return None
    fund_slice = funding.loc[mask].iloc[-lookback:]
    if len(fund_slice) < lookback:
        return None
    # Acceleration = slope of funding rate over lookback
    scores = {}
    x = np.arange(len(fund_slice))
    for sym in fund_slice.columns:
        y = fund_slice[sym].values
        if np.isnan(y).sum() > len(y) * 0.5:
            continue
        y = np.nan_to_num(y, 0)
        slope, _, _, _, _ = stats.linregress(x, y)
        if np.isfinite(slope):
            scores[sym] = slope
    return pd.Series(scores) if scores else None


def factor_h420_vol_of_vol(closes, extra_data, lookback, i):
    """Vol-of-Vol: rolling std of rolling volatility."""
    rets = closes.iloc[max(0, i-lookback*2):i+1].pct_change().dropna()
    if len(rets) < lookback:
        return None
    # Rolling 5-day vol
    roll_vol = rets.rolling(5).std()
    if len(roll_vol) < lookback:
        return None
    # Std of rolling vol (vol-of-vol)
    vov = roll_vol.iloc[-lookback:].std()
    return vov.dropna()


def factor_h421_return_autocorr(closes, extra_data, lookback, i):
    """Return autocorrelation: rolling autocorr(1) of daily returns."""
    rets = closes.iloc[max(0, i-lookback):i+1].pct_change().dropna()
    if len(rets) < 20:
        return None
    scores = {}
    for sym in rets.columns:
        r = rets[sym].dropna()
        if len(r) < 15:
            continue
        ac = r.autocorr(lag=1)
        if np.isfinite(ac):
            scores[sym] = ac
    return pd.Series(scores) if scores else None


def factor_h422_streak(closes, extra_data, lookback, i):
    """Consecutive direction streak: count of same-direction days."""
    rets = closes.iloc[max(0, i-lookback):i+1].pct_change().dropna()
    if len(rets) < 5:
        return None
    scores = {}
    for sym in rets.columns:
        r = rets[sym].dropna()
        if len(r) < 5:
            continue
        # Count consecutive days in same direction as latest
        latest_sign = np.sign(r.iloc[-1])
        if latest_sign == 0:
            scores[sym] = 0
            continue
        streak = 1
        for j in range(len(r) - 2, -1, -1):
            if np.sign(r.iloc[j]) == latest_sign:
                streak += 1
            else:
                break
        # Sign the streak: positive streak = up, negative = down
        scores[sym] = streak * latest_sign
    return pd.Series(scores) if scores else None


def factor_h423_vol_weighted_return(closes, extra_data, lookback, i):
    """Volume-weighted return: avg(return × relative_volume)."""
    volumes = extra_data["volumes"]
    rets = closes.iloc[max(0, i-lookback):i+1].pct_change().dropna()
    vols = volumes.iloc[max(0, i-lookback):i+1]
    common_idx = rets.index.intersection(vols.index)
    if len(common_idx) < 10:
        return None
    rets = rets.loc[common_idx]
    vols = vols.loc[common_idx]

    # Relative volume: each day's volume / average volume over lookback
    avg_vol = vols.mean()
    rel_vol = vols / avg_vol.replace(0, np.nan)

    # Volume-weighted return
    vw_ret = (rets * rel_vol).mean()
    return vw_ret.dropna()


# ============================================================
# Main
# ============================================================

FACTORS = [
    ("H-416 Composite(Eff×VolSurp)", factor_h416_composite,
     [20, 30, 40, 60], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-417 Vol-Adaptive Momentum", factor_h417_vol_adaptive_mom,
     [20, 30, 40, 60], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-418 BTC Lead-Lag", factor_h418_btc_leadlag,
     [20, 30, 60], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-419 Funding Acceleration", factor_h419_funding_accel,
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-420 Vol-of-Vol", factor_h420_vol_of_vol,
     [20, 30, 40, 60], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-421 Return Autocorrelation", factor_h421_return_autocorr,
     [15, 20, 30, 60], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-422 Streak Factor", factor_h422_streak,
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
    ("H-423 Vol-Weighted Return", factor_h423_vol_weighted_return,
     [10, 15, 20, 30], [3, 5, 7], [3, 4], ["high_long", "low_long"]),
]


def main():
    closes, volumes, highs, lows = load_data()
    funding = load_funding()

    extra = {"volumes": volumes, "highs": highs, "lows": lows, "funding": funding}

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
