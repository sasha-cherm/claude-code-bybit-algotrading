"""
Batch backtest: H-908 to H-915 — Return Shape & Distribution XS Signals.

H-908: Positive Return Ratio XS — fraction of positive daily returns over lookback
H-909: Return Asymmetry XS — mean(positive returns) / mean(abs(negative returns))
H-910: Tail Ratio XS — 95th percentile / abs(5th percentile) of returns
H-911: Gain-Loss Ratio XS — avg gain / avg loss (win-loss asymmetry)
H-912: Consecutive Gain Streak XS — current streak of consecutive positive closes
H-913: Up Capture Ratio XS — mean return on market-up days / mean market return on up days
H-914: Return Smoothness XS — R-squared of cumulative returns vs linear trend
H-915: Sortino-like XS — mean return / downside deviation
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

def positive_return_ratio_signal(closes, period=20):
    """H-908: Positive Return Ratio = fraction of positive daily returns.
    High ratio = asset trending up consistently. Simple but robust."""
    ret = closes.pct_change()
    return ret.rolling(period).apply(lambda x: (x > 0).sum() / len(x), raw=True)


def return_asymmetry_signal(closes, period=20):
    """H-909: Return Asymmetry = mean(positive rets) / mean(abs(negative rets)).
    > 1 means gains are larger than losses. Captures upside skew."""
    ret = closes.pct_change()
    def asym(x):
        pos = x[x > 0]
        neg = x[x < 0]
        if len(pos) == 0 or len(neg) == 0:
            return np.nan
        return np.mean(pos) / np.mean(np.abs(neg))
    return ret.rolling(period).apply(asym, raw=True)


def tail_ratio_signal(closes, period=30):
    """H-910: Tail Ratio = 95th percentile / abs(5th percentile) of returns.
    High = right tail bigger than left tail (favorable distribution)."""
    ret = closes.pct_change()
    def tail_r(x):
        p95 = np.percentile(x, 95)
        p5 = np.percentile(x, 5)
        if p5 == 0:
            return np.nan
        return p95 / abs(p5)
    return ret.rolling(period).apply(tail_r, raw=True)


def gain_loss_ratio_signal(closes, period=20):
    """H-911: Gain-Loss Ratio = avg gain / avg loss.
    Captures win/loss size asymmetry. High = wins are bigger than losses."""
    ret = closes.pct_change()
    def glr(x):
        gains = x[x > 0]
        losses = x[x < 0]
        if len(gains) == 0 or len(losses) == 0:
            return np.nan
        return np.mean(gains) / np.mean(np.abs(losses))
    return ret.rolling(period).apply(glr, raw=True)


def consecutive_gain_streak_signal(closes):
    """H-912: Consecutive Gain Streak = current streak of consecutive green days.
    Positive for up-streak, negative for down-streak. Captures short-term persistence."""
    ret = closes.pct_change()
    signal = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for col in closes.columns:
        streak = 0
        for i in range(1, len(closes)):
            r = ret[col].iloc[i]
            if np.isnan(r):
                streak = 0
            elif r > 0:
                if streak > 0:
                    streak += 1
                else:
                    streak = 1
            elif r < 0:
                if streak < 0:
                    streak -= 1
                else:
                    streak = -1
            else:
                streak = 0
            signal.iloc[i, signal.columns.get_loc(col)] = streak
    return signal


def up_capture_ratio_signal(closes, period=30):
    """H-913: Up Capture Ratio = asset's mean return on market-up days / market's mean return on up days.
    Market = equal-weight cross-section. High capture = outperforms when market is up."""
    ret = closes.pct_change()
    mkt = ret.mean(axis=1)
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        mkt_window = mkt.iloc[i-period:i]
        up_mask = mkt_window > 0
        if up_mask.sum() < 5:
            continue
        mkt_up_mean = mkt_window[up_mask].mean()
        if mkt_up_mean == 0:
            continue
        for col in closes.columns:
            asset_ret = ret[col].iloc[i-period:i]
            asset_up = asset_ret[up_mask].mean()
            signal.iloc[i, signal.columns.get_loc(col)] = asset_up / mkt_up_mean
    return signal


def return_smoothness_signal(closes, period=20):
    """H-914: Return Smoothness = R-squared of cumulative returns vs linear trend.
    High R2 = smooth, consistent trend. Low = choppy, noisy. Smoothness predicts persistence."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    x = np.arange(period)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            cum_r = np.cumsum(r)
            if np.std(cum_r) == 0:
                continue
            slope, intercept, r_val, p_val, std_err = stats.linregress(x, cum_r)
            # Signed R2: positive if trending up, negative if trending down
            r2 = r_val ** 2
            direction = np.sign(slope)
            signal.iloc[i, signal.columns.get_loc(col)] = r2 * direction
    return signal


def sortino_like_signal(closes, period=20):
    """H-915: Sortino-like = mean return / downside deviation.
    Downside dev = std of negative returns only. Penalizes downside risk not upside vol."""
    ret = closes.pct_change()
    def sortino(x):
        mean_r = np.mean(x)
        neg = x[x < 0]
        if len(neg) < 3:
            return np.nan
        downside_std = np.std(neg)
        if downside_std == 0:
            return np.nan
        return mean_r / downside_std
    return ret.rolling(period).apply(sortino, raw=True)


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

    # H-908: Positive Return Ratio
    for period in [10, 14, 20, 30]:
        sig = positive_return_ratio_signal(closes, period)
        r = run_signal(f"H-908 (PosRetRatio P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-908", {}).get("sharpe", -99):
            results["H-908"] = r

    # H-909: Return Asymmetry
    for period in [14, 20, 30]:
        sig = return_asymmetry_signal(closes, period)
        r = run_signal(f"H-909 (RetAsym P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-909", {}).get("sharpe", -99):
            results["H-909"] = r

    # H-910: Tail Ratio
    for period in [20, 30, 45]:
        sig = tail_ratio_signal(closes, period)
        r = run_signal(f"H-910 (TailRatio P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-910", {}).get("sharpe", -99):
            results["H-910"] = r

    # H-911: Gain-Loss Ratio
    for period in [14, 20, 30]:
        sig = gain_loss_ratio_signal(closes, period)
        r = run_signal(f"H-911 (GLRatio P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-911", {}).get("sharpe", -99):
            results["H-911"] = r

    # H-912: Consecutive Gain Streak
    sig = consecutive_gain_streak_signal(closes)
    r = run_signal("H-912 (GainStreak)", sig, closes, 10, configs)
    results["H-912"] = r

    # H-913: Up Capture Ratio
    for period in [20, 30, 45]:
        sig = up_capture_ratio_signal(closes, period)
        r = run_signal(f"H-913 (UpCapture P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-913", {}).get("sharpe", -99):
            results["H-913"] = r

    # H-914: Return Smoothness
    for period in [14, 20, 30]:
        sig = return_smoothness_signal(closes, period)
        r = run_signal(f"H-914 (RetSmooth P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-914", {}).get("sharpe", -99):
            results["H-914"] = r

    # H-915: Sortino-like
    for period in [14, 20, 30]:
        sig = sortino_like_signal(closes, period)
        r = run_signal(f"H-915 (Sortino P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-915", {}).get("sharpe", -99):
            results["H-915"] = r

    # Summary
    print("\n" + "=" * 70)
    print("BATCH 1 SUMMARY (H-908 to H-915)")
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
