"""
Batch backtest: H-884 to H-891 — Statistical Time-Series Properties as XS Factors.

H-884: Hurst Exponent XS — trending vs mean-reverting behavior
H-885: AR(1) Coefficient XS — autocorrelation as XS signal
H-886: Volatility of Volatility XS — vol-of-vol uncertainty
H-887: Maximum Adverse Excursion XS — worst intra-period drawdown
H-888: Parkinson Vol Ratio XS — range-based vs close-close vol
H-889: Return Autocorrelation Profile XS — sum of lag-1 to lag-5 autocorrelation
H-890: Conditional Tail Expectation XS — expected shortfall / CVaR
H-891: Up/Down Day Ratio XS — proportion of up days
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

def hurst_signal(closes, period=60):
    """H-884: Hurst exponent via R/S analysis. H>0.5 = trending, H<0.5 = mean-reverting.
    Long trending assets (high H), short mean-reverting (low H)."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    ret = closes.pct_change()
    for i in range(period + 10, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i - period:i].values
            if not np.all(np.isfinite(r)):
                continue
            # Simplified R/S Hurst
            n = len(r)
            mean_r = np.mean(r)
            dev = np.cumsum(r - mean_r)
            R = np.max(dev) - np.min(dev)
            S = np.std(r, ddof=1) if np.std(r, ddof=1) > 0 else 1e-10
            rs = R / S
            H = np.log(rs) / np.log(n) if rs > 0 else 0.5
            signal.iloc[i, signal.columns.get_loc(col)] = H
    return signal


def ar1_signal(closes, period=30):
    """H-885: AR(1) coefficient = lag-1 autocorrelation of returns.
    High AR(1) = momentum persistence, low = mean-reversion tendency."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    ret = closes.pct_change()
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i - period:i].values
            if len(r) < period or not np.all(np.isfinite(r)):
                continue
            if np.std(r) > 0:
                ac = np.corrcoef(r[:-1], r[1:])[0, 1]
                signal.iloc[i, signal.columns.get_loc(col)] = ac
    return signal


def vol_of_vol_signal(closes, outer=60, inner=10):
    """H-886: Volatility of Volatility. Compute rolling inner-period vol, then take
    std of that series over outer period. High vol-of-vol = uncertain regime."""
    ret = closes.pct_change()
    inner_vol = ret.rolling(inner).std()
    vov = inner_vol.rolling(outer).std() / inner_vol.rolling(outer).mean().replace(0, np.nan)
    return vov


def max_adverse_excursion_signal(closes, period=20):
    """H-887: Maximum Adverse Excursion = worst peak-to-trough drawdown within period.
    Small MAE = resilient asset (long), large MAE = fragile (short)."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            prices = closes[col].iloc[i - period:i].values
            if not np.all(np.isfinite(prices)) or prices[0] == 0:
                continue
            # Compute max drawdown within the window
            cummax = np.maximum.accumulate(prices)
            dd = (prices - cummax) / cummax
            mae = np.min(dd)  # Most negative = worst
            signal.iloc[i, signal.columns.get_loc(col)] = -mae  # Flip: higher = more resilient
    return signal


def parkinson_vol_ratio_signal(closes, highs, lows, period=20):
    """H-888: Parkinson Volatility Ratio = Parkinson (range-based) vol / Close-Close vol.
    Ratio > 1 means intraday moves exceed close-close — hidden volatility.
    Long assets with low ratio (clean trends), short high ratio (choppy)."""
    ret = closes.pct_change()
    cc_vol = ret.rolling(period).std()
    # Parkinson vol
    log_hl = np.log(highs / lows.replace(0, np.nan))
    parkinson = np.sqrt(log_hl.pow(2).rolling(period).mean() / (4 * np.log(2)))
    ratio = parkinson / cc_vol.replace(0, np.nan)
    return ratio


def autocorr_profile_signal(closes, period=30, max_lag=5):
    """H-889: Sum of lag-1 through lag-5 autocorrelation of returns.
    Positive sum = persistent momentum structure. Negative = reversal tendency."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    ret = closes.pct_change()
    for i in range(period + max_lag + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i - period - max_lag:i].values
            if not np.all(np.isfinite(r)):
                continue
            r_main = r[max_lag:]
            ac_sum = 0
            for lag in range(1, max_lag + 1):
                r_lag = r[max_lag - lag:-lag]
                if len(r_main) == len(r_lag) and np.std(r_main) > 0 and np.std(r_lag) > 0:
                    ac_sum += np.corrcoef(r_main, r_lag)[0, 1]
            signal.iloc[i, signal.columns.get_loc(col)] = ac_sum
    return signal


def cvar_signal(closes, period=30, alpha=0.05):
    """H-890: Conditional Tail Expectation (CVaR / Expected Shortfall).
    Average of worst alpha% returns. More negative = more tail risk.
    Long assets with low tail risk (high CVaR), short high tail risk."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i - period:i].values
            if not np.all(np.isfinite(r)):
                continue
            cutoff = int(np.ceil(alpha * len(r)))
            if cutoff < 1:
                cutoff = 1
            sorted_r = np.sort(r)
            cvar = np.mean(sorted_r[:cutoff])
            signal.iloc[i, signal.columns.get_loc(col)] = -cvar  # Flip: higher = less tail risk
    return signal


def up_down_ratio_signal(closes, period=20):
    """H-891: Up/Down Day Ratio = proportion of positive return days.
    High ratio = consistent upward sentiment. Momentum-like but captures consistency."""
    ret = closes.pct_change()
    up_ratio = ret.rolling(period).apply(lambda x: np.sum(x > 0) / len(x), raw=True)
    return up_ratio


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

    # H-884: Hurst Exponent
    for period in [30, 60]:
        sig = hurst_signal(closes, period)
        r = run_signal(f"H-884 (Hurst P{period})", sig, closes, period + 10, configs)
        if r.get("sharpe", 0) > results.get("H-884", {}).get("sharpe", -99):
            results["H-884"] = r

    # H-885: AR(1) Coefficient
    for period in [20, 30, 45]:
        sig = ar1_signal(closes, period)
        r = run_signal(f"H-885 (AR1 P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-885", {}).get("sharpe", -99):
            results["H-885"] = r

    # H-886: Volatility of Volatility
    for outer in [40, 60]:
        sig = vol_of_vol_signal(closes, outer, 10)
        r = run_signal(f"H-886 (VoV O{outer})", sig, closes, outer + 10, configs, direction="low_long")
        if r.get("sharpe", 0) > results.get("H-886", {}).get("sharpe", -99):
            results["H-886"] = r

    # H-887: Maximum Adverse Excursion
    for period in [14, 20, 30]:
        sig = max_adverse_excursion_signal(closes, period)
        r = run_signal(f"H-887 (MAE P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-887", {}).get("sharpe", -99):
            results["H-887"] = r

    # H-888: Parkinson Vol Ratio
    for period in [14, 20, 30]:
        sig = parkinson_vol_ratio_signal(closes, highs, lows, period)
        r = run_signal(f"H-888 (Park Ratio P{period})", sig, closes, period + 5, configs, direction="low_long")
        if r.get("sharpe", 0) > results.get("H-888", {}).get("sharpe", -99):
            results["H-888"] = r

    # H-889: Autocorrelation Profile
    for period in [20, 30]:
        sig = autocorr_profile_signal(closes, period, 5)
        r = run_signal(f"H-889 (ACorr P{period})", sig, closes, period + 10, configs)
        if r.get("sharpe", 0) > results.get("H-889", {}).get("sharpe", -99):
            results["H-889"] = r

    # H-890: CVaR / Expected Shortfall
    for period in [20, 30, 45]:
        sig = cvar_signal(closes, period)
        r = run_signal(f"H-890 (CVaR P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-890", {}).get("sharpe", -99):
            results["H-890"] = r

    # H-891: Up/Down Day Ratio
    for period in [14, 20, 30]:
        sig = up_down_ratio_signal(closes, period)
        r = run_signal(f"H-891 (UpDown P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-891", {}).get("sharpe", -99):
            results["H-891"] = r

    # Summary
    print("\n" + "=" * 60)
    print("BATCH SUMMARY: H-884 to H-891 (Time-Series Statistics)")
    print("=" * 60)
    for hid, r in sorted(results.items()):
        status = r.get("status", "CANDIDATE")
        if status == "REJECTED_IS":
            print(f"  {hid}: REJECTED (IS {r['pos_pct']:.0f}% pos, Sharpe {r['sharpe']:.3f})")
        else:
            wf_pos = sum(1 for w in r["wf"] if w > 0)
            wf_tot = len(r["wf"])
            print(f"  {hid}: Sharpe {r['sharpe']:.3f}, WF {wf_pos}/{wf_tot}, "
                  f"SH p={r['sh'][2]:.4f}, corr {r['corr']}, params {r['params']}")


if __name__ == "__main__":
    run_batch()
