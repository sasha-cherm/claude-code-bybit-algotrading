"""
Batch backtest: H-956 to H-963 — Return Distributional Dynamics XS Signals.

H-956: Kurtosis Change — delta(rolling kurtosis) — normalizing tails = cleaner trend
H-957: IQR Expansion — IQR(recent) / IQR(long) — distribution widening = regime shift
H-958: Median-Mean Gap — (median - mean) / std — consistent vs outlier-driven returns
H-959: Down Day Frequency — fraction of negative return days (inverse = bullish)
H-960: Longest Win Streak — max consecutive positive return days in lookback
H-961: Tail Improvement — change in 5th percentile return — improving downside protection
H-962: Win-Loss Size Ratio — avg(positive returns) / avg(|negative returns|)
H-963: Return Concentration — max daily return / abs cumulative return — fragile vs distributed
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

def kurtosis_change(closes, period=30, delta=10):
    """H-956: Change in rolling kurtosis. Decreasing kurtosis = tails normalizing = cleaner trend."""
    ret = closes.pct_change()
    kurt = ret.rolling(period).apply(lambda x: stats.kurtosis(x, fisher=True), raw=True)
    return -kurt.diff(delta)  # negative: decreasing kurtosis = good


def iqr_expansion(closes, short_period=7, long_period=30):
    """H-957: IQR(short) / IQR(long). Expanding distribution = regime shift."""
    ret = closes.pct_change()
    q75_short = ret.rolling(short_period).quantile(0.75)
    q25_short = ret.rolling(short_period).quantile(0.25)
    q75_long = ret.rolling(long_period).quantile(0.75)
    q25_long = ret.rolling(long_period).quantile(0.25)
    iqr_short = q75_short - q25_short
    iqr_long = (q75_long - q25_long).replace(0, np.nan)
    return iqr_short / iqr_long


def median_mean_gap(closes, period=30):
    """H-958: (median - mean) / std. Positive = consistent gains (median > mean means fewer outlier losses)."""
    ret = closes.pct_change()
    rolling_mean = ret.rolling(period).mean()
    rolling_median = ret.rolling(period).median()
    rolling_std = ret.rolling(period).std().replace(0, np.nan)
    return (rolling_median - rolling_mean) / rolling_std


def down_day_frequency(closes, period=30):
    """H-959: Fraction of negative return days. Inverse signal: fewer down days = bullish."""
    ret = closes.pct_change()
    neg_count = ret.rolling(period).apply(lambda x: np.sum(x < 0), raw=True)
    return -(neg_count / period)  # negative: fewer down days = higher signal


def longest_win_streak(closes, period=30):
    """H-960: Max consecutive positive return days in lookback window."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            max_streak = 0
            current = 0
            for v in r:
                if v > 0:
                    current += 1
                    max_streak = max(max_streak, current)
                else:
                    current = 0
            signal.iloc[i, signal.columns.get_loc(col)] = max_streak
    return signal


def tail_improvement(closes, period=30, delta=10):
    """H-961: Change in 5th percentile daily return. Improving (less negative) = better downside protection."""
    ret = closes.pct_change()
    p5 = ret.rolling(period).quantile(0.05)
    return p5.diff(delta)  # positive change = improving tail


def win_loss_size_ratio(closes, period=30):
    """H-962: avg(positive returns) / avg(|negative returns|). Quality of wins vs losses."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            pos = r[r > 0]
            neg = r[r < 0]
            if len(pos) < 3 or len(neg) < 3:
                continue
            avg_win = np.mean(pos)
            avg_loss = np.mean(np.abs(neg))
            if avg_loss < 1e-10:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = avg_win / avg_loss
    return signal


def return_concentration(closes, period=30):
    """H-963: max(daily_return) / sum(abs(daily_return)). High = concentrated (fragile). Low = distributed (sustainable).
    Long distributed returns (low concentration), short concentrated."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            total_abs = np.sum(np.abs(r))
            if total_abs < 1e-10:
                continue
            max_abs = np.max(np.abs(r))
            signal.iloc[i, signal.columns.get_loc(col)] = -(max_abs / total_abs)  # negative: low concentration = long
    return signal


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

    # H-956: Kurtosis Change
    for period, delta in [(20, 5), (30, 10), (60, 20)]:
        sig = kurtosis_change(closes, period, delta)
        r = run_signal(f"H-956 (KurtChange P{period}D{delta})", sig, closes, period + delta + 5, configs)
        if r.get("sharpe", 0) > results.get("H-956", {}).get("sharpe", -99):
            results["H-956"] = r

    # H-957: IQR Expansion
    for sp, lp in [(5, 20), (7, 30), (10, 40)]:
        sig = iqr_expansion(closes, sp, lp)
        r = run_signal(f"H-957 (IQRExp S{sp}L{lp})", sig, closes, lp + 5, configs)
        if r.get("sharpe", 0) > results.get("H-957", {}).get("sharpe", -99):
            results["H-957"] = r

    # H-958: Median-Mean Gap
    for period in [14, 20, 30, 60]:
        sig = median_mean_gap(closes, period)
        r = run_signal(f"H-958 (MedMean P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-958", {}).get("sharpe", -99):
            results["H-958"] = r

    # H-959: Down Day Frequency
    for period in [10, 14, 20, 30]:
        sig = down_day_frequency(closes, period)
        r = run_signal(f"H-959 (DownFreq P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-959", {}).get("sharpe", -99):
            results["H-959"] = r

    # H-960: Longest Win Streak
    for period in [14, 20, 30]:
        sig = longest_win_streak(closes, period)
        r = run_signal(f"H-960 (WinStreak P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-960", {}).get("sharpe", -99):
            results["H-960"] = r

    # H-961: Tail Improvement
    for period, delta in [(20, 5), (30, 10), (60, 20)]:
        sig = tail_improvement(closes, period, delta)
        r = run_signal(f"H-961 (TailImp P{period}D{delta})", sig, closes, period + delta + 5, configs)
        if r.get("sharpe", 0) > results.get("H-961", {}).get("sharpe", -99):
            results["H-961"] = r

    # H-962: Win-Loss Size Ratio
    for period in [14, 20, 30, 60]:
        sig = win_loss_size_ratio(closes, period)
        r = run_signal(f"H-962 (WinLoss P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-962", {}).get("sharpe", -99):
            results["H-962"] = r

    # H-963: Return Concentration
    for period in [14, 20, 30, 60]:
        sig = return_concentration(closes, period)
        r = run_signal(f"H-963 (RetConc P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-963", {}).get("sharpe", -99):
            results["H-963"] = r

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "="*70)
    print("BATCH 1 SUMMARY (H-956 to H-963 — Distributional Dynamics)")
    print("="*70)
    for hid in ["H-956", "H-957", "H-958", "H-959", "H-960", "H-961", "H-962", "H-963"]:
        r = results.get(hid, {})
        status = r.get("status", "")
        if status == "REJECTED_IS":
            print(f"  {hid}: REJECTED — {r.get('pos_pct',0):.0f}% positive, Sharpe {r.get('sharpe',0):.3f}")
        elif "wf" in r:
            wf_pos = sum(1 for w in r["wf"] if w > 0)
            wf_tot = len(r["wf"])
            sh1, sh2, p = r["sh"]
            corr = r["corr"]
            m = r["metrics"]
            pass_wf = wf_pos >= wf_tot * 0.5
            pass_sh = p < 0.10
            pass_corr = abs(corr) < 0.50
            status = "CONFIRMED" if (pass_wf and pass_sh and pass_corr) else "BORDERLINE"
            if not pass_wf:
                status = "REJECTED_WF"
            print(f"  {hid}: {status} — Sharpe {r['sharpe']:.3f}, WF {wf_pos}/{wf_tot}, "
                  f"SH p={p:.3f}, corr {corr}, {m}")
        else:
            print(f"  {hid}: {r}")

    return results


if __name__ == "__main__":
    run_batch()
