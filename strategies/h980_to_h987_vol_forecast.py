"""
Batch backtest: H-980 to H-987 — Volatility Forecasting / Vol Regime XS Signals.

H-980: Vol Surprise — realized vol vs EWM predicted vol — long assets where vol is lower than expected
H-981: Vol Mean Reversion Speed — how fast vol reverts to long-run mean — long fast reverters
H-982: Vol Clustering Intensity — GARCH-like vol persistence (autocorr of squared returns)
H-983: Realized-Implied Vol Spread (RV proxy) — short/long vol ratio as implied vol proxy
H-984: Vol Regime Duration — days since last vol regime change (high→low or vice versa)
H-985: Vol Asymmetry — up-vol vs down-vol ratio — long assets with higher upside vol
H-986: Vol Breakout Frequency — count of days vol exceeds 2-sigma in lookback
H-987: Vol Compression Score — ratio of recent range to historical range — compressed = ready to break
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

DATA_DIR = Path("data")
FEE_RATE = 0.00055
SLIPPAGE_BPS = 2

ASSETS = ["BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX", "LINK",
          "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM"]


def load_data():
    closes, highs, lows, opens, volumes = {}, {}, {}, {}, {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_1d.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            closes[f"{ticker}/USDT"] = df["close"]
            highs[f"{ticker}/USDT"] = df["high"]
            lows[f"{ticker}/USDT"] = df["low"]
            opens[f"{ticker}/USDT"] = df["open"]
            volumes[f"{ticker}/USDT"] = df["volume"] * df["close"]
        except:
            pass
    closes = pd.DataFrame(closes).sort_index().dropna(how="all")
    highs = pd.DataFrame(highs).sort_index().dropna(how="all")
    lows = pd.DataFrame(lows).sort_index().dropna(how="all")
    opens = pd.DataFrame(opens).sort_index().dropna(how="all")
    volumes = pd.DataFrame(volumes).sort_index().dropna(how="all")
    return closes, highs, lows, opens, volumes


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
            sig_row = signal_df.iloc[i - 1]
            sig_row = sig_row.dropna()
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
                 n_folds=6, test_days=100):
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
    t_stat, p_val = stats.ttest_1samp(pnl, 0)
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


# ============================================================
# SIGNAL GENERATORS
# ============================================================

def vol_surprise(closes, short_period=10, long_period=60):
    """H-980: Realized vol vs EWM predicted vol. Negative surprise = vol lower than expected = stability.
    Long assets with negative vol surprise (calmer than predicted), short positive surprise."""
    returns = closes.pct_change()
    realized = returns.rolling(short_period).std() * np.sqrt(365)
    predicted = returns.ewm(span=long_period).std() * np.sqrt(365)
    predicted = predicted.replace(0, np.nan)
    surprise = (realized - predicted) / predicted
    return -surprise  # negative: lower vol than expected = long


def vol_mean_reversion_speed(closes, vol_window=20, lookback=60):
    """H-981: How fast vol reverts to long-run mean. Measure as correlation between vol level
    and subsequent vol change. Fast reverters are more stable/predictable."""
    returns = closes.pct_change()
    vol = returns.rolling(vol_window).std()
    vol_mean = vol.rolling(lookback).mean()
    vol_dev = vol - vol_mean  # deviation from mean
    vol_change = vol.diff(5)  # subsequent 5-day vol change
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(lookback + vol_window + 10, len(closes)):
        for col in closes.columns:
            dev = vol_dev[col].iloc[i-lookback:i].values
            chg = vol_change[col].iloc[i-lookback:i].values
            mask = np.isfinite(dev) & np.isfinite(chg)
            if mask.sum() < 20:
                continue
            corr = np.corrcoef(dev[mask], chg[mask])[0, 1]
            if np.isfinite(corr):
                signal.iloc[i, signal.columns.get_loc(col)] = -corr  # negative corr = mean reverting
    return signal


def vol_clustering(closes, period=30):
    """H-982: Autocorrelation of squared returns (GARCH-like persistence). High clustering = predictable
    vol patterns. Long high clustering (predictable), short low clustering."""
    sq_ret = closes.pct_change() ** 2
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            sr = sq_ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(sr)) or len(sr) < 10:
                continue
            ac = np.corrcoef(sr[:-1], sr[1:])[0, 1]
            if np.isfinite(ac):
                signal.iloc[i, signal.columns.get_loc(col)] = ac
    return signal


def rv_spread(closes, short_window=7, long_window=30):
    """H-983: Short/long realized vol ratio as proxy for vol term structure.
    Similar to H-059 but using returns-based vol instead of raw std.
    Ratio > 1 = expanding vol = emerging trend. Long expanding, short contracting."""
    returns = closes.pct_change()
    vol_short = returns.rolling(short_window).std()
    vol_long = returns.rolling(long_window).std().replace(0, np.nan)
    return vol_short / vol_long


def vol_regime_duration(closes, vol_window=20, threshold_pctile=50):
    """H-984: Days since last vol regime change. Long duration = stable regime.
    Short duration = recently changed (unstable). Long stable, short unstable."""
    returns = closes.pct_change()
    vol = returns.rolling(vol_window).std()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for col in closes.columns:
        v = vol[col].values
        median_vol = pd.Series(v).rolling(120, min_periods=60).median().values
        regime = np.where(v > median_vol, 1, 0)
        duration = np.zeros(len(v))
        count = 0
        for i in range(1, len(v)):
            if not np.isfinite(v[i]) or not np.isfinite(median_vol[i] if i < len(median_vol) else np.nan):
                duration[i] = np.nan
                continue
            if regime[i] == regime[i-1]:
                count += 1
            else:
                count = 0
            duration[i] = count
        signal[col] = duration
    return signal


def vol_asymmetry(closes, period=30):
    """H-985: Up-vol vs down-vol. Compute std of positive returns / std of negative returns.
    High ratio = more upside volatility = bullish distribution. Long high, short low."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = returns[col].iloc[i-period:i].values
            r = r[np.isfinite(r)]
            up = r[r > 0]
            down = r[r < 0]
            if len(up) < 5 or len(down) < 5:
                continue
            up_std = np.std(up)
            down_std = np.std(down)
            if down_std > 0:
                signal.iloc[i, signal.columns.get_loc(col)] = up_std / down_std
    return signal


def vol_breakout_freq(closes, period=60, threshold_sigma=2.0):
    """H-986: Count of days where absolute return exceeds threshold-sigma in lookback.
    More breakouts = more dynamic/active asset. Long active, short dormant."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = returns[col].iloc[i-period:i].values
            r = r[np.isfinite(r)]
            if len(r) < 20:
                continue
            mu, sigma = np.mean(r), np.std(r)
            if sigma == 0:
                continue
            count = np.sum(np.abs(r - mu) > threshold_sigma * sigma)
            signal.iloc[i, signal.columns.get_loc(col)] = count
    return signal


def vol_compression(highs, lows, short_period=5, long_period=30):
    """H-987: Recent range / historical range. Compression (ratio < 1) signals coiled spring.
    Long compressed (about to break out), short expanded (already moved).
    Direction: low_long — buy compressed, sell expanded."""
    daily_range = (highs - lows) / ((highs + lows) / 2)
    recent = daily_range.rolling(short_period).mean()
    historical = daily_range.rolling(long_period).mean().replace(0, np.nan)
    return recent / historical  # low = compressed


# ============================================================
# BATCH RUNNER
# ============================================================

def run_signal(name, signal_df, closes, lookback, param_configs, direction="high_long"):
    print(f"\n=== {name} ===")
    best = {"sharpe": -99}
    all_sharpes = []
    for rebal, n_ls in param_configs:
        pnl = xs_backtest(closes, signal_df, lookback, rebal, n_ls, direction)
        sh = compute_sharpe(pnl)
        all_sharpes.append(sh)
        if sh > best["sharpe"]:
            best = {"sharpe": sh, "rebal": rebal, "n_ls": n_ls, "pnl": pnl}

    pos_pct = sum(1 for s in all_sharpes if s > 0) / len(all_sharpes) * 100
    print(f"  IS: {pos_pct:.0f}% positive ({sum(1 for s in all_sharpes if s > 0)}/{len(all_sharpes)})")
    print(f"  Best: R{best['rebal']}_N{best['n_ls']} Sharpe {best['sharpe']:.3f}")
    m = compute_metrics(best["pnl"])
    print(f"  Metrics: {m}")

    if pos_pct >= 70 and best["sharpe"] > 0.8:
        wf = walk_forward(closes, signal_df, lookback, best["rebal"], best["n_ls"], direction)
        sh1, sh2, p = split_half_test(best["pnl"])
        corr = h012_correlation(closes, signal_df, lookback, best["rebal"], best["n_ls"], direction)
        print(f"  WF: {[round(w, 3) for w in wf]} ({sum(1 for w in wf if w > 0)}/{len(wf)})")
        print(f"  SH: {sh1:.3f}/{sh2:.3f}, p={p:.4f}")
        print(f"  H-012 corr: {corr}")
        return {"name": name, "sharpe": best["sharpe"], "pos_pct": pos_pct,
                "wf": wf, "sh": (sh1, sh2, p), "corr": corr, "metrics": m,
                "params": f"R{best['rebal']}_N{best['n_ls']}", "pnl": best["pnl"]}
    else:
        print(f"  REJECTED at IS — {pos_pct:.0f}% positive, Sharpe {best['sharpe']:.3f}")
        return {"name": name, "status": "REJECTED_IS", "pos_pct": pos_pct,
                "sharpe": best["sharpe"]}


def run_batch():
    print("Loading data...")
    closes, highs, lows, opens, volumes = load_data()
    print(f"Data: {len(closes)} days, {len(closes.columns)} assets, "
          f"{closes.index[0].date()} to {closes.index[-1].date()}")

    configs = [(r, n) for r in [3, 5, 7] for n in [3, 4]]
    results = {}

    # H-980: Vol Surprise
    for sp, lp in [(5, 30), (10, 60), (10, 90), (20, 60)]:
        sig = vol_surprise(closes, sp, lp)
        r = run_signal(f"H-980 (VolSurprise S{sp}L{lp})", sig, closes, lp + 5, configs)
        if r.get("sharpe", 0) > results.get("H-980", {}).get("sharpe", -99):
            results["H-980"] = r

    # H-981: Vol Mean Reversion Speed
    for vw, lb in [(10, 40), (20, 60), (20, 90), (30, 90)]:
        sig = vol_mean_reversion_speed(closes, vw, lb)
        r = run_signal(f"H-981 (VolMR VW{vw}LB{lb})", sig, closes, lb + vw + 10, configs)
        if r.get("sharpe", 0) > results.get("H-981", {}).get("sharpe", -99):
            results["H-981"] = r

    # H-982: Vol Clustering
    for period in [14, 20, 30, 60]:
        sig = vol_clustering(closes, period)
        r = run_signal(f"H-982 (VolCluster P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-982", {}).get("sharpe", -99):
            results["H-982"] = r

    # H-983: RV Spread (vol term structure proxy)
    for sw, lw in [(5, 20), (7, 30), (10, 30), (7, 60)]:
        sig = rv_spread(closes, sw, lw)
        r = run_signal(f"H-983 (RVSpread S{sw}L{lw})", sig, closes, lw + 5, configs)
        if r.get("sharpe", 0) > results.get("H-983", {}).get("sharpe", -99):
            results["H-983"] = r

    # H-984: Vol Regime Duration
    for vw in [10, 20, 30]:
        sig = vol_regime_duration(closes, vw)
        r = run_signal(f"H-984 (VolRegDur VW{vw})", sig, closes, max(vw, 20) + 5, configs)
        if r.get("sharpe", 0) > results.get("H-984", {}).get("sharpe", -99):
            results["H-984"] = r

    # H-985: Vol Asymmetry
    for period in [14, 20, 30, 60]:
        sig = vol_asymmetry(closes, period)
        r = run_signal(f"H-985 (VolAsym P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-985", {}).get("sharpe", -99):
            results["H-985"] = r

    # H-986: Vol Breakout Frequency
    for period, thr in [(30, 1.5), (30, 2.0), (60, 1.5), (60, 2.0)]:
        sig = vol_breakout_freq(closes, period, thr)
        r = run_signal(f"H-986 (VolBrkFreq P{period}T{thr})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-986", {}).get("sharpe", -99):
            results["H-986"] = r

    # H-987: Vol Compression
    for sp, lp in [(3, 20), (5, 30), (5, 60), (7, 30)]:
        sig = vol_compression(highs, lows, sp, lp)
        r = run_signal(f"H-987 (VolCompress S{sp}L{lp})", sig, closes, lp + 5, configs, direction="low_long")
        if r.get("sharpe", 0) > results.get("H-987", {}).get("sharpe", -99):
            results["H-987"] = r

    print("\n" + "=" * 60)
    print("BATCH SUMMARY — H-980 to H-987 (Vol Forecast / Vol Regime)")
    print("=" * 60)
    for key in sorted(results.keys()):
        r = results[key]
        if "status" in r and r["status"] == "REJECTED_IS":
            print(f"  {key}: REJECTED — {r['pos_pct']:.0f}% positive, Sharpe {r['sharpe']:.3f}")
        else:
            wf_pos = sum(1 for w in r["wf"] if w > 0)
            wf_tot = len(r["wf"])
            print(f"  {key}: Sharpe {r['sharpe']:.3f}, WF {wf_pos}/{wf_tot}, "
                  f"SH p={r['sh'][2]:.4f}, corr {r['corr']}, {r['params']}")


if __name__ == "__main__":
    run_batch()
