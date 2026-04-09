#!/usr/bin/env python3
"""
Backtest eight cross-sectional factors using daily data.
No 4h look-ahead risk — all signals computed from daily bars.

  H-408: Weekday Seasonality XS — for each asset, compute avg return on today's
         weekday over rolling window. Rank by expected weekday-specific return.
  H-409: Lead-Lag Score — rolling correlation of each asset's return(t) with
         BTC's return(t-1). High = lags BTC. Low = leads/independent.
  H-410: Drawdown Depth XS — current drawdown from rolling peak. Long shallow DD,
         short deep DD (quality/momentum persistence).
  H-411: Volume Trend (OBV Slope) — slope of On-Balance Volume over rolling window.
         Rising OBV = accumulation, falling = distribution.
  H-412: Realized-Implied Volatility Ratio — realized vol / funding-implied vol.
         Not possible without IV data, so use realized vol relative to XS median instead.
         Actually: Relative Volatility Position — rolling z-score of vol change.
  H-413: Price-MA Distance — distance from rolling MA (e.g., 20d SMA).
         Far above = extended, far below = oversold. Test both directions.
  H-414: Volume Profile Trend — is volume increasing or decreasing over time?
         Linear regression slope of log-volume over lookback.
  H-415: Cross-Asset Dispersion Beta — rolling beta of each asset's daily return to
         cross-sectional return dispersion. Captures which assets move more when
         the market is volatile.

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
    closes_dict, volumes_dict = {}, {}

    for sym in ASSETS:
        ticker = sym.replace("/", "_")
        fpath = ROOT / "data" / f"{ticker}_1d.parquet"
        if not fpath.exists():
            print(f"  {sym}: no daily data")
            continue
        df = pd.read_parquet(fpath)
        if len(df) < 200:
            print(f"  {sym}: only {len(df)} bars")
            continue
        closes_dict[sym] = df["close"]
        volumes_dict[sym] = df["volume"]

    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill().dropna()
    idx = closes.index.intersection(volumes.index)
    closes, volumes = closes.loc[idx], volumes.loc[idx]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    return closes, volumes


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
            continue
        pnl = np.array(pnl_daily)
        sharpe = float(np.mean(pnl) / np.std(pnl) * np.sqrt(365)) if np.std(pnl) > 0 else 0
        oos_sharpes.append(sharpe)

    return oos_sharpes


def compute_correlation_h012(closes, pnl_daily):
    returns = closes.pct_change()
    lookback, rebal, n = 60, 5, 4

    h012_pnl = []
    positions = {}
    days_since = rebal

    for i in range(70, len(closes)):
        days_since += 1
        if days_since >= rebal:
            mom = {}
            for sym in closes.columns:
                if i >= lookback:
                    r = closes[sym].iloc[i] / closes[sym].iloc[i - lookback] - 1
                    if np.isfinite(r):
                        mom[sym] = r
            if len(mom) < 2 * n:
                h012_pnl.append(0)
                continue
            ranked = pd.Series(mom).sort_values(ascending=False)
            longs = set(ranked.index[:n])
            shorts = set(ranked.index[-n:])
            old = set(positions.keys())
            new = longs | shorts
            changed = old.symmetric_difference(new)
            fee_cost = len(changed) * FEE_RATE / (2 * n)
            positions = {s: (1.0/n if s in longs else -1.0/n) for s in longs | shorts}
            days_since = 0
            daily_ret = -fee_cost
        else:
            daily_ret = 0.0

        for sym, w in positions.items():
            if sym in returns.columns:
                r = returns[sym].iloc[i]
                if np.isfinite(r):
                    daily_ret += w * r
        h012_pnl.append(daily_ret)

    min_len = min(len(h012_pnl), len(pnl_daily))
    if min_len < 30:
        return 0.0
    return float(np.corrcoef(h012_pnl[-min_len:], pnl_daily[-min_len:])[0, 1])


# ============ Factor Definitions ============

def weekday_seasonality_factor(closes, extra_data, lookback, i):
    """H-408: Rank by expected return for today's weekday."""
    returns = closes.pct_change()
    today_weekday = closes.index[i].weekday()
    scores = {}
    for sym in closes.columns:
        # Get returns up to yesterday (i-1) to avoid look-ahead
        rets = returns[sym].iloc[max(0, i-lookback*7):i]
        weekday_rets = rets[rets.index.weekday == today_weekday]
        if len(weekday_rets) < 3:
            continue
        scores[sym] = float(weekday_rets.mean())
    if len(scores) < 6:
        return None
    return pd.Series(scores)


def lead_lag_factor(closes, extra_data, lookback, i):
    """H-409: Rolling correlation of asset return(t) with BTC return(t-1)."""
    returns = closes.pct_change()
    if "BTC/USDT" not in returns.columns:
        return None
    btc_ret_lag = returns["BTC/USDT"].shift(1)
    scores = {}
    for sym in closes.columns:
        if sym == "BTC/USDT":
            continue
        window_ret = returns[sym].iloc[max(0, i-lookback):i]
        window_btc = btc_ret_lag.iloc[max(0, i-lookback):i]
        valid = window_ret.notna() & window_btc.notna()
        if valid.sum() < lookback * 0.5:
            continue
        corr = window_ret[valid].corr(window_btc[valid])
        if np.isfinite(corr):
            scores[sym] = corr
    if len(scores) < 6:
        return None
    return pd.Series(scores)


def drawdown_depth_factor(closes, extra_data, lookback, i):
    """H-410: Current drawdown from rolling peak. Shallow DD = quality."""
    scores = {}
    for sym in closes.columns:
        window = closes[sym].iloc[max(0, i-lookback):i+1]
        if len(window) < lookback * 0.5:
            continue
        peak = window.max()
        current = window.iloc[-1]
        dd = (current - peak) / peak if peak > 0 else 0
        scores[sym] = dd  # Closer to 0 = shallow DD
    if len(scores) < 6:
        return None
    return pd.Series(scores)


def obv_slope_factor(closes, extra_data, lookback, i):
    """H-411: Slope of On-Balance Volume over rolling window."""
    volumes = extra_data["volumes"]
    returns = closes.pct_change()
    scores = {}
    for sym in closes.columns:
        if sym not in volumes.columns:
            continue
        rets = returns[sym].iloc[max(0, i-lookback):i+1]
        vols = volumes[sym].iloc[max(0, i-lookback):i+1]
        if len(rets) < lookback * 0.5:
            continue
        # OBV: cumulative sum of signed volume
        signed_vol = vols * np.sign(rets)
        obv = signed_vol.cumsum()
        if len(obv) < 5:
            continue
        # Linear regression slope
        x = np.arange(len(obv))
        y = obv.values
        valid = np.isfinite(y)
        if valid.sum() < 5:
            continue
        slope, _, _, _, _ = stats.linregress(x[valid], y[valid])
        # Normalize by mean volume for cross-asset comparability
        mean_vol = vols.mean()
        if mean_vol > 0:
            scores[sym] = slope / mean_vol
    if len(scores) < 6:
        return None
    return pd.Series(scores)


def relative_vol_zscore_factor(closes, extra_data, lookback, i):
    """H-412: Z-score of recent vol change relative to longer history."""
    returns = closes.pct_change()
    scores = {}
    for sym in closes.columns:
        long_window = returns[sym].iloc[max(0, i-lookback*3):i]
        short_window = returns[sym].iloc[max(0, i-lookback//3):i]
        if len(long_window) < lookback or len(short_window) < 3:
            continue
        long_vol = long_window.std()
        short_vol = short_window.std()
        if long_vol > 0:
            scores[sym] = (short_vol - long_vol) / long_vol
    if len(scores) < 6:
        return None
    return pd.Series(scores)


def price_ma_distance_factor(closes, extra_data, lookback, i):
    """H-413: Distance from rolling MA. Far above = extended."""
    scores = {}
    for sym in closes.columns:
        window = closes[sym].iloc[max(0, i-lookback):i+1]
        if len(window) < lookback * 0.5:
            continue
        ma = window.mean()
        current = window.iloc[-1]
        if ma > 0:
            scores[sym] = (current - ma) / ma
    if len(scores) < 6:
        return None
    return pd.Series(scores)


def volume_trend_factor(closes, extra_data, lookback, i):
    """H-414: Linear regression slope of log-volume over lookback."""
    volumes = extra_data["volumes"]
    scores = {}
    for sym in closes.columns:
        if sym not in volumes.columns:
            continue
        vols = volumes[sym].iloc[max(0, i-lookback):i+1]
        if len(vols) < lookback * 0.5:
            continue
        log_vol = np.log1p(vols.values)
        valid = np.isfinite(log_vol)
        if valid.sum() < 5:
            continue
        x = np.arange(len(log_vol))
        slope, _, _, _, _ = stats.linregress(x[valid], log_vol[valid])
        scores[sym] = slope
    if len(scores) < 6:
        return None
    return pd.Series(scores)


def dispersion_beta_factor(closes, extra_data, lookback, i):
    """H-415: Beta to cross-sectional return dispersion."""
    returns = closes.pct_change()
    window = returns.iloc[max(0, i-lookback):i]
    if len(window) < lookback * 0.5:
        return None
    # Cross-sectional dispersion per day
    disp = window.std(axis=1)
    scores = {}
    for sym in closes.columns:
        asset_ret = window[sym]
        valid = asset_ret.notna() & disp.notna()
        if valid.sum() < lookback * 0.3:
            continue
        corr = asset_ret[valid].corr(disp[valid])
        if np.isfinite(corr):
            scores[sym] = corr
    if len(scores) < 6:
        return None
    return pd.Series(scores)


def evaluate_hypothesis(closes, hyp_name, factor_fn, directions, extra_data=None):
    print(f"\n{'='*60}")
    print(f"  {hyp_name}")
    print(f"{'='*60}")

    lookbacks = [10, 15, 20, 30, 60]
    rebals = [3, 5, 7]
    ns = [3, 4]

    results = backtest_factor(closes, factor_fn, lookbacks, rebals, ns,
                              directions, hyp_name, extra_data=extra_data)

    if not results:
        print("  No valid results!")
        return None

    df = pd.DataFrame([{k: v for k, v in r.items() if k != "pnl_daily"} for r in results])
    mean_sharpe = df["sharpe"].mean()

    best_dir = None
    best_pct = 0
    for d in directions:
        sub = df[df["direction"] == d]
        d_pos = (sub["sharpe"] > 0).sum()
        d_total = len(sub)
        d_pct = d_pos / d_total * 100 if d_total > 0 else 0
        print(f"  IS {d}: {d_pos}/{d_total} positive ({d_pct:.1f}%)")
        if d_pct > best_pct:
            best_pct = d_pct
            best_dir = d

    best = df.loc[df["sharpe"].idxmax()]
    print(f"  Best: LB{best['lookback']}_R{best['rebal']}_N{best['n']}_{best['direction']}")
    print(f"    Sharpe {best['sharpe']:.3f}, Ann {best['ann_ret']:.1f}%, DD {best['max_dd']:.1f}%")
    print(f"  Mean Sharpe: {mean_sharpe:.3f}")

    if best_pct < 80:
        print(f"  REJECTED at IS — best direction {best_dir} only {best_pct:.1f}% positive")
        return {"status": "REJECTED", "reason": "IS", "best_pct": best_pct, "best_dir": best_dir,
                "best_sharpe": float(best["sharpe"]), "mean_sharpe": mean_sharpe}

    print(f"  IS PASSED — {best_dir} {best_pct:.1f}% positive")

    best_result = results[df["sharpe"].idxmax()]
    wf_sharpes = walk_forward(
        closes, factor_fn, int(best["lookback"]), int(best["rebal"]),
        int(best["n"]), best["direction"], extra_data=extra_data
    )

    n_pos_wf = sum(1 for s in wf_sharpes if s > 0)
    mean_wf = np.mean(wf_sharpes) if wf_sharpes else 0
    print(f"  WF: {n_pos_wf}/{len(wf_sharpes)} positive, mean Sharpe {mean_wf:.3f}")
    print(f"    Fold Sharpes: {[round(s, 3) for s in wf_sharpes]}")

    if n_pos_wf < 4 or mean_wf < 0:
        print(f"  REJECTED at WF — {n_pos_wf}/{len(wf_sharpes)} positive, mean {mean_wf:.3f}")
        return {"status": "REJECTED", "reason": "WF", "best_pct": best_pct, "best_dir": best_dir,
                "best_sharpe": float(best["sharpe"]), "wf_pos": n_pos_wf, "wf_total": len(wf_sharpes),
                "wf_mean": mean_wf, "mean_sharpe": mean_sharpe}

    pnl = best_result["pnl_daily"]
    half = len(pnl) // 2
    h1_sharpe = float(np.mean(pnl[:half]) / np.std(pnl[:half]) * np.sqrt(365)) if np.std(pnl[:half]) > 0 else 0
    h2_sharpe = float(np.mean(pnl[half:]) / np.std(pnl[half:]) * np.sqrt(365)) if np.std(pnl[half:]) > 0 else 0
    split_pass = h1_sharpe > 0 and h2_sharpe > 0
    print(f"  Split-half: H1={h1_sharpe:.3f}, H2={h2_sharpe:.3f} {'PASS' if split_pass else 'FAIL'}")

    best_lb = int(best["lookback"])
    best_r = int(best["rebal"])
    best_n = int(best["n"])
    neighbors = df[
        (df["direction"] == best["direction"]) &
        (abs(df["lookback"] - best_lb) <= 10) &
        (abs(df["rebal"] - best_r) <= 2) &
        (abs(df["n"] - best_n) <= 1)
    ]
    n_pos_nb = (neighbors["sharpe"] > 0).sum()
    nb_total = len(neighbors)
    nb_pct = n_pos_nb / nb_total * 100 if nb_total > 0 else 0
    print(f"  Neighbors: {n_pos_nb}/{nb_total} positive ({nb_pct:.1f}%)")

    corr_h012 = compute_correlation_h012(closes, pnl)
    print(f"  H-012 correlation: {corr_h012:.3f}")

    if not split_pass:
        print(f"  REJECTED at split-half")
        return {"status": "REJECTED", "reason": "split-half", "best_pct": best_pct, "best_dir": best_dir,
                "best_sharpe": float(best["sharpe"]), "wf_pos": n_pos_wf, "wf_total": len(wf_sharpes),
                "wf_mean": mean_wf, "h1": h1_sharpe, "h2": h2_sharpe, "corr_h012": corr_h012,
                "mean_sharpe": mean_sharpe}

    print(f"  *** CONFIRMED ***")
    return {
        "status": "CONFIRMED",
        "best_dir": best_dir, "best_pct": best_pct,
        "best_sharpe": float(best["sharpe"]),
        "best_config": f"LB{best_lb}_R{best_r}_N{best_n}_{best['direction']}",
        "ann_ret": float(best["ann_ret"]),
        "max_dd": float(best["max_dd"]),
        "wf_pos": n_pos_wf, "wf_total": len(wf_sharpes),
        "wf_mean": mean_wf,
        "h1": h1_sharpe, "h2": h2_sharpe,
        "nb_pct": nb_pct,
        "corr_h012": corr_h012,
        "mean_sharpe": mean_sharpe,
        "n_days": int(best["n_days"]),
        "lookback": best_lb, "rebal": best_r, "n": best_n,
        "direction": str(best["direction"]),
    }


def main():
    closes, volumes = load_data()
    extra_data = {"volumes": volumes}

    hypotheses = [
        ("H-408: Weekday Seasonality", weekday_seasonality_factor,
         ["high_weekday_long", "low_weekday_long"], None),
        ("H-409: Lead-Lag Score", lead_lag_factor,
         ["high_leadlag_long", "low_leadlag_long"], None),
        ("H-410: Drawdown Depth", drawdown_depth_factor,
         ["high_dd_long", "low_dd_long"], None),
        ("H-411: OBV Slope", obv_slope_factor,
         ["high_obv_long", "low_obv_long"], extra_data),
        ("H-412: Relative Vol Z-Score", relative_vol_zscore_factor,
         ["high_volz_long", "low_volz_long"], None),
        ("H-413: Price-MA Distance", price_ma_distance_factor,
         ["high_mad_long", "low_mad_long"], None),
        ("H-414: Volume Trend", volume_trend_factor,
         ["high_voltrd_long", "low_voltrd_long"], extra_data),
        ("H-415: Dispersion Beta", dispersion_beta_factor,
         ["high_dispbeta_long", "low_dispbeta_long"], None),
    ]

    all_results = {}
    for hyp_name, factor_fn, directions, ed in hypotheses:
        result = evaluate_hypothesis(closes, hyp_name, factor_fn, directions, extra_data=ed)
        all_results[hyp_name] = result

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for hyp_name, result in all_results.items():
        if result is None:
            print(f"  {hyp_name}: NO RESULTS")
        elif result["status"] == "CONFIRMED":
            print(f"  {hyp_name}: CONFIRMED — Sharpe {result['best_sharpe']:.3f}, "
                  f"WF {result['wf_pos']}/{result['wf_total']}, corr H-012 {result['corr_h012']:.3f}")
        else:
            reason = result.get("reason", "unknown")
            print(f"  {hyp_name}: REJECTED ({reason}) — best dir {result.get('best_dir', '?')} "
                  f"{result.get('best_pct', 0):.1f}%, Sharpe {result.get('best_sharpe', 0):.3f}")


if __name__ == "__main__":
    main()
