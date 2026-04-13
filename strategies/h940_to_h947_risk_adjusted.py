"""
Batch backtest: H-940 to H-947 — Risk-Adjusted Return XS Signals.

H-940: Gain-to-Pain Ratio — sum of returns / |sum of negative returns|
H-941: Omega Ratio XS — probability-weighted gains/losses above zero threshold
H-942: Calmar Ratio XS — cumulative return / max drawdown depth
H-943: Tail Ratio XS — 95th pctile return / |5th pctile return|
H-944: Pain Index XS — inverse of average drawdown depth (lower pain = long)
H-945: Sterling Ratio XS — cumulative return / mean of worst drawdowns
H-946: Kappa Ratio XS — mean return / lower partial moment^(1/2)
H-947: Burke Ratio XS — cumulative return / sqrt(sum of squared drawdowns)
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
    closes, volumes = {}, {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_1d.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            closes[f"{ticker}/USDT"] = df["close"]
            volumes[f"{ticker}/USDT"] = df["volume"] * df["close"]
        except:
            pass
    closes = pd.DataFrame(closes).sort_index().dropna(how="all")
    volumes = pd.DataFrame(volumes).sort_index().dropna(how="all")
    return closes, volumes


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

def gain_to_pain_ratio(closes, period=30):
    """H-940: Sum of all returns / |sum of negative returns|.
    Higher = more gains per unit of pain experienced."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            neg_sum = abs(r[r < 0].sum())
            if neg_sum == 0:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = r.sum() / neg_sum
    return signal


def omega_ratio(closes, period=30, threshold=0):
    """H-941: Omega ratio = sum of gains above threshold / sum of losses below threshold.
    Captures full return distribution, not just mean/var."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            gains = np.sum(np.maximum(r - threshold, 0))
            losses = np.sum(np.maximum(threshold - r, 0))
            if losses == 0:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = gains / losses
    return signal


def calmar_ratio(closes, period=60):
    """H-942: Cumulative return / max drawdown depth.
    Reward-to-risk from a drawdown perspective."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            cum = np.cumsum(r)
            total_ret = cum[-1]
            running_max = np.maximum.accumulate(cum)
            dd = cum - running_max
            max_dd = abs(np.min(dd))
            if max_dd < 0.001:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = total_ret / max_dd
    return signal


def tail_ratio(closes, period=60):
    """H-943: 95th percentile abs return / |5th percentile return|.
    High = more upside tail than downside tail."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            p95 = np.percentile(r, 95)
            p5 = abs(np.percentile(r, 5))
            if p5 < 1e-6:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = p95 / p5
    return signal


def pain_index(closes, period=60):
    """H-944: Inverse of average drawdown depth.
    Lower average drawdown = better risk profile = long signal."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            cum = np.cumsum(r)
            running_max = np.maximum.accumulate(cum)
            dd = running_max - cum  # positive = in drawdown
            avg_dd = np.mean(dd)
            if avg_dd < 1e-6:
                avg_dd = 1e-6
            # Inverse: lower pain = higher signal (long the resilient ones)
            signal.iloc[i, signal.columns.get_loc(col)] = -avg_dd
    return signal


def sterling_ratio(closes, period=60, n_worst=3):
    """H-945: Cumulative return / mean of worst N drawdowns.
    Like Calmar but averages multiple worst drawdowns (more robust)."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            cum = np.cumsum(r)
            total_ret = cum[-1]
            running_max = np.maximum.accumulate(cum)
            dd = cum - running_max
            # Find worst N drawdown troughs
            sorted_dd = np.sort(dd)[:n_worst]
            mean_worst = abs(np.mean(sorted_dd))
            if mean_worst < 0.001:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = total_ret / mean_worst
    return signal


def kappa_ratio(closes, period=30):
    """H-946: Mean return / sqrt(lower partial moment).
    LPM = mean of squared negative returns. Penalizes downside only."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            mean_r = np.mean(r)
            neg = r[r < 0]
            if len(neg) < 3:
                continue
            lpm = np.mean(neg ** 2)
            sqrt_lpm = np.sqrt(lpm)
            if sqrt_lpm < 1e-8:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = mean_r / sqrt_lpm
    return signal


def burke_ratio(closes, period=60):
    """H-947: Cumulative return / sqrt(sum of squared drawdowns).
    More sensitive to multiple drawdowns than Calmar (penalizes frequency)."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            cum = np.cumsum(r)
            total_ret = cum[-1]
            running_max = np.maximum.accumulate(cum)
            dd = cum - running_max
            # Sum of squared drawdown values
            ss_dd = np.sum(dd ** 2)
            sqrt_ss = np.sqrt(ss_dd)
            if sqrt_ss < 0.001:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = total_ret / sqrt_ss
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
    closes, volumes = load_data()
    print(f"Data: {len(closes)} days, {len(closes.columns)} assets, "
          f"{closes.index[0].date()} to {closes.index[-1].date()}")

    configs = [(r, n) for r in [3, 5, 7] for n in [3, 4]]
    results = {}

    # H-940: Gain-to-Pain Ratio
    for period in [14, 20, 30, 60]:
        sig = gain_to_pain_ratio(closes, period)
        r = run_signal(f"H-940 (GainPain P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-940", {}).get("sharpe", -99):
            results["H-940"] = r

    # H-941: Omega Ratio
    for period in [14, 20, 30, 60]:
        sig = omega_ratio(closes, period)
        r = run_signal(f"H-941 (Omega P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-941", {}).get("sharpe", -99):
            results["H-941"] = r

    # H-942: Calmar Ratio
    for period in [30, 60, 90]:
        sig = calmar_ratio(closes, period)
        r = run_signal(f"H-942 (Calmar P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-942", {}).get("sharpe", -99):
            results["H-942"] = r

    # H-943: Tail Ratio
    for period in [30, 60, 90]:
        sig = tail_ratio(closes, period)
        r = run_signal(f"H-943 (TailRatio P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-943", {}).get("sharpe", -99):
            results["H-943"] = r

    # H-944: Pain Index (inverse)
    for period in [30, 60, 90]:
        sig = pain_index(closes, period)
        r = run_signal(f"H-944 (PainIdx P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-944", {}).get("sharpe", -99):
            results["H-944"] = r

    # H-945: Sterling Ratio
    for period in [30, 60, 90]:
        sig = sterling_ratio(closes, period)
        r = run_signal(f"H-945 (Sterling P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-945", {}).get("sharpe", -99):
            results["H-945"] = r

    # H-946: Kappa Ratio
    for period in [14, 20, 30, 60]:
        sig = kappa_ratio(closes, period)
        r = run_signal(f"H-946 (Kappa P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-946", {}).get("sharpe", -99):
            results["H-946"] = r

    # H-947: Burke Ratio
    for period in [30, 60, 90]:
        sig = burke_ratio(closes, period)
        r = run_signal(f"H-947 (Burke P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-947", {}).get("sharpe", -99):
            results["H-947"] = r

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "="*70)
    print("BATCH 2 SUMMARY (H-940 to H-947)")
    print("="*70)
    for hid in ["H-940", "H-941", "H-942", "H-943", "H-944", "H-945", "H-946", "H-947"]:
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
    results = run_batch()
