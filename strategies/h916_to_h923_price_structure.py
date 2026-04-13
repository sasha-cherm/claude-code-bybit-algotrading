"""
Batch backtest: H-916 to H-923 — Price Structure & Trend Anatomy XS Signals.

H-916: Trend Linearity XS — R-squared of price vs time regression
H-917: Price Efficiency Ratio XS — net price change / sum of absolute daily changes (fractal efficiency)
H-918: Hurst Deviation XS — simplified Hurst exponent deviation from 0.5 (mean-reverting vs trending)
H-919: Swing Count XS — number of direction changes in lookback (choppy vs smooth)
H-920: Higher-Low Ratio XS — count of higher-lows / count of lower-lows
H-921: Price Position XS — where current price sits in lookback range (0=low, 1=high)
H-922: Mean Reversion Speed XS — autocorrelation of returns (negative = mean-reverting)
H-923: Fractal Dimension XS — Higuchi fractal dimension proxy (complexity of price path)
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

def trend_linearity_signal(closes, period=20):
    """H-916: Trend Linearity = R-squared of close prices vs time.
    High R2 = strong linear trend. Signed by slope direction."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    x = np.arange(period)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            p = closes[col].iloc[i-period:i].values
            if not np.all(np.isfinite(p)):
                continue
            slope, intercept, r_val, p_val, std_err = stats.linregress(x, p)
            r2 = r_val ** 2
            direction = np.sign(slope)
            signal.iloc[i, signal.columns.get_loc(col)] = r2 * direction
    return signal


def price_efficiency_signal(closes, period=20):
    """H-917: Price Efficiency Ratio = net price change / sum(abs(daily changes)).
    1.0 = perfectly straight move. Near 0 = choppy. Signed by direction."""
    ret = closes.pct_change()
    net = closes.pct_change(period)
    abs_sum = ret.abs().rolling(period).sum().replace(0, np.nan)
    return net / abs_sum


def hurst_deviation_signal(closes, period=30):
    """H-918: Simplified Hurst proxy: std(returns) scaling.
    H > 0.5 = trending, H < 0.5 = mean-reverting.
    Compute as RS/sqrt(n) ratio across sub-periods."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            # Rescaled range
            cum = np.cumsum(r - np.mean(r))
            R = np.max(cum) - np.min(cum)
            S = np.std(r)
            if S == 0:
                continue
            rs = R / S
            # H estimate: RS ~ n^H, so H ~ log(RS)/log(n)
            H = np.log(rs + 1e-10) / np.log(period)
            signal.iloc[i, signal.columns.get_loc(col)] = H - 0.5  # deviation from random walk
    return signal


def swing_count_signal(closes, period=20):
    """H-919: Swing Count = number of direction reversals in lookback.
    Low count = smooth trend. High count = choppy. INVERT: low is better for momentum."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            signs = np.sign(r)
            changes = np.sum(np.abs(np.diff(signs[signs != 0])) > 0)
            signal.iloc[i, signal.columns.get_loc(col)] = -changes  # negate: fewer swings = better
    return signal


def higher_low_ratio_signal(closes, period=20):
    """H-920: Higher-Low Ratio = count of higher-lows / total.
    Captures trend structure: uptrend = series of higher lows."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            p = closes[col].iloc[i-period:i].values
            if not np.all(np.isfinite(p)):
                continue
            higher_lows = 0
            total_checks = 0
            for j in range(2, len(p)):
                # Compare local mins
                if p[j] > p[j-2]:  # higher low structure
                    higher_lows += 1
                total_checks += 1
            if total_checks == 0:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = higher_lows / total_checks
    return signal


def price_position_signal(closes, period=20):
    """H-921: Price Position = (close - min) / (max - min) over lookback.
    1.0 = at period high. 0.0 = at period low. High position = momentum."""
    roll_min = closes.rolling(period).min()
    roll_max = closes.rolling(period).max()
    rng = (roll_max - roll_min).replace(0, np.nan)
    return (closes - roll_min) / rng


def mean_reversion_speed_signal(closes, period=20):
    """H-922: Autocorrelation of returns. Negative = mean-reverting (short it).
    Positive = trending (long it). Captures persistence structure."""
    ret = closes.pct_change()
    def autocorr(x):
        if len(x) < 5:
            return np.nan
        return pd.Series(x).autocorr(lag=1)
    return ret.rolling(period).apply(autocorr, raw=True)


def fractal_dimension_signal(closes, period=20):
    """H-923: Fractal Dimension proxy = log(total path length / net displacement) / log(period).
    High FD = complex/choppy. Low FD = smooth trend. INVERT: low is better."""
    ret = closes.pct_change()
    path_len = ret.abs().rolling(period).sum().replace(0, np.nan)
    net_disp = closes.pct_change(period).abs().replace(0, 1e-10)
    ratio = path_len / net_disp
    # FD ~ 1 + log(ratio) / log(period), negate so low complexity = high signal
    return -np.log(ratio + 1e-10) / np.log(period)


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

    # H-916: Trend Linearity
    for period in [14, 20, 30]:
        sig = trend_linearity_signal(closes, period)
        r = run_signal(f"H-916 (TrendLin P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-916", {}).get("sharpe", -99):
            results["H-916"] = r

    # H-917: Price Efficiency
    for period in [10, 14, 20, 30]:
        sig = price_efficiency_signal(closes, period)
        r = run_signal(f"H-917 (PriceEff P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-917", {}).get("sharpe", -99):
            results["H-917"] = r

    # H-918: Hurst Deviation
    for period in [20, 30, 45]:
        sig = hurst_deviation_signal(closes, period)
        r = run_signal(f"H-918 (Hurst P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-918", {}).get("sharpe", -99):
            results["H-918"] = r

    # H-919: Swing Count
    for period in [10, 14, 20]:
        sig = swing_count_signal(closes, period)
        r = run_signal(f"H-919 (SwingCnt P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-919", {}).get("sharpe", -99):
            results["H-919"] = r

    # H-920: Higher-Low Ratio
    for period in [14, 20, 30]:
        sig = higher_low_ratio_signal(closes, period)
        r = run_signal(f"H-920 (HigherLow P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-920", {}).get("sharpe", -99):
            results["H-920"] = r

    # H-921: Price Position
    for period in [10, 14, 20, 30]:
        sig = price_position_signal(closes, period)
        r = run_signal(f"H-921 (PricePos P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-921", {}).get("sharpe", -99):
            results["H-921"] = r

    # H-922: Mean Reversion Speed
    for period in [14, 20, 30]:
        sig = mean_reversion_speed_signal(closes, period)
        r = run_signal(f"H-922 (MRSpeed P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-922", {}).get("sharpe", -99):
            results["H-922"] = r

    # H-923: Fractal Dimension
    for period in [14, 20, 30]:
        sig = fractal_dimension_signal(closes, period)
        r = run_signal(f"H-923 (FracDim P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-923", {}).get("sharpe", -99):
            results["H-923"] = r

    # Summary
    print("\n" + "=" * 70)
    print("BATCH 2 SUMMARY (H-916 to H-923)")
    print("=" * 70)
    for hid in sorted(results.keys()):
        r = results[hid]
        status = r.get("status", "")
        if status == "REJECTED_IS":
            print(f"  {hid}: REJECTED — IS {r.get('pos_pct', 0):.0f}% positive, Sharpe {r.get('sharpe', 0):.3f}")
        else:
            wf = r.get("wf", [])
            wf_pass = sum(1 for w in wf if w > 0)
            sh1, sh2, p = r.get("sh", (0, 0, 1))
            corr = r.get("corr", 0)
            sh_pass = "PASS" if p < 0.1 else "FAIL"
            params = r.get("params", "?")
            print(f"  {hid}: Sharpe {r['sharpe']:.3f}, WF {wf_pass}/{len(wf)}, "
                  f"SH p={p:.3f} {sh_pass}, corr {corr}, {params}")

    return results


if __name__ == "__main__":
    run_batch()
