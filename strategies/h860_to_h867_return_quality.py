"""
Batch backtest: H-860 to H-867 — Return Decomposition & Quality XS Signals.

H-860: Upside Capture XS — avg return on BTC-up days (long high capture)
H-861: Downside Protection XS — avg return on BTC-down days (long least-bad)
H-862: Up-Down Capture Ratio XS — upside / downside capture ratio
H-863: Win Rate XS — fraction of positive return days
H-864: Conditional Momentum — momentum computed only on high-volume days
H-865: Return Consistency XS — consistency = mean / std of sub-period returns
H-866: Volume-Weighted Return XS — VWAP return vs simple return divergence
H-867: Max Gain Dependency XS — max single-day gain / total return (tail dependency)
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

def upside_capture_signal(closes, window=30):
    """H-860: Upside Capture — avg return on BTC-up days.
    Long assets that outperform on BTC-up days (high beta to upside)."""
    returns = closes.pct_change()
    btc_ret = returns["BTC/USDT"] if "BTC/USDT" in returns.columns else returns.iloc[:, 0]
    btc_up = btc_ret > 0
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(window + 5, len(closes)):
        mask = btc_up.iloc[i - window:i]
        for col in returns.columns:
            up_rets = returns[col].iloc[i - window:i][mask]
            if len(up_rets) > 5:
                signal.iloc[i, signal.columns.get_loc(col)] = up_rets.mean()
    return signal


def downside_protection_signal(closes, window=30):
    """H-861: Downside Protection — avg return on BTC-down days (less negative = better).
    Long assets that lose least on BTC-down days."""
    returns = closes.pct_change()
    btc_ret = returns["BTC/USDT"] if "BTC/USDT" in returns.columns else returns.iloc[:, 0]
    btc_down = btc_ret < 0
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(window + 5, len(closes)):
        mask = btc_down.iloc[i - window:i]
        for col in returns.columns:
            dn_rets = returns[col].iloc[i - window:i][mask]
            if len(dn_rets) > 5:
                signal.iloc[i, signal.columns.get_loc(col)] = dn_rets.mean()
    # Higher = less negative = better protection
    return signal


def updown_ratio_signal(closes, window=30):
    """H-862: Up-Down Capture Ratio — upside capture / abs(downside capture).
    High ratio = asset gains more in up markets relative to losses in down markets."""
    returns = closes.pct_change()
    btc_ret = returns["BTC/USDT"] if "BTC/USDT" in returns.columns else returns.iloc[:, 0]
    btc_up = btc_ret > 0
    btc_down = btc_ret < 0
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(window + 5, len(closes)):
        up_mask = btc_up.iloc[i - window:i]
        dn_mask = btc_down.iloc[i - window:i]
        for col in returns.columns:
            up_avg = returns[col].iloc[i - window:i][up_mask].mean()
            dn_avg = returns[col].iloc[i - window:i][dn_mask].mean()
            if dn_avg != 0 and np.isfinite(up_avg) and np.isfinite(dn_avg):
                signal.iloc[i, signal.columns.get_loc(col)] = up_avg / abs(dn_avg)
    return signal


def win_rate_signal(closes, window=20):
    """H-863: Win Rate — fraction of positive return days.
    Long high win-rate assets, short low win-rate assets."""
    returns = closes.pct_change()
    signal = (returns > 0).astype(float).rolling(window).mean()
    return signal


def conditional_momentum_signal(closes, volumes, window=30, vol_pctile=0.5):
    """H-864: Conditional Momentum — momentum computed only on high-volume days.
    Filters noise by only counting returns on days with above-median volume."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(window + 5, len(closes)):
        for col in returns.columns:
            if col not in volumes.columns:
                continue
            v = volumes[col].iloc[i - window:i]
            r = returns[col].iloc[i - window:i]
            median_v = v.median()
            # Only use returns on high-volume days
            high_vol_mask = v > median_v
            hv_rets = r[high_vol_mask]
            if len(hv_rets) > 5:
                signal.iloc[i, signal.columns.get_loc(col)] = hv_rets.sum()
    return signal


def return_consistency_signal(closes, window=30, sub_period=5):
    """H-865: Return Consistency — mean / std of sub-period returns.
    High consistency = steady returns, not driven by single events."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(window + 5, len(closes)):
        for col in returns.columns:
            r = returns[col].iloc[i - window:i].dropna()
            if len(r) < window // 2:
                continue
            # Split into sub-periods
            n_subs = len(r) // sub_period
            if n_subs < 3:
                continue
            sub_rets = [r.iloc[j * sub_period:(j + 1) * sub_period].sum()
                        for j in range(n_subs)]
            sub_rets = np.array(sub_rets)
            std = np.std(sub_rets)
            if std > 0:
                signal.iloc[i, signal.columns.get_loc(col)] = np.mean(sub_rets) / std
    return signal


def vw_return_divergence_signal(closes, volumes, window=20):
    """H-866: Volume-Weighted Return Divergence — VWAP return vs simple return.
    Positive divergence = smart money buying (high-vol days had positive returns)."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(window + 5, len(closes)):
        for col in returns.columns:
            if col not in volumes.columns:
                continue
            r = returns[col].iloc[i - window:i].dropna()
            v = volumes[col].iloc[i - window:i].dropna()
            idx = r.index.intersection(v.index)
            if len(idx) < 10:
                continue
            r_common = r[idx]
            v_common = v[idx]
            vw_ret = (r_common * v_common).sum() / v_common.sum() if v_common.sum() > 0 else 0
            ew_ret = r_common.mean()
            signal.iloc[i, signal.columns.get_loc(col)] = vw_ret - ew_ret
    return signal


def max_gain_dependency_signal(closes, window=30):
    """H-867: Max Gain Dependency — max single-day gain / total return.
    Short assets where most of the return came from a single day (fragile momentum)."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(window + 5, len(closes)):
        for col in returns.columns:
            r = returns[col].iloc[i - window:i].dropna()
            if len(r) < window // 2:
                continue
            total = r.sum()
            if abs(total) > 1e-8:
                max_gain = r.max()
                signal.iloc[i, signal.columns.get_loc(col)] = -(max_gain / abs(total))
            # Negative → long when max_gain/total is LOW (not tail-dependent)
    return signal


# ============================================================
# BATCH RUNNER
# ============================================================

def run_signal(name, signal_df, closes, lookback, param_configs, direction="high_long"):
    """Generic signal evaluator with param sweep, WF, SH, and H-012 corr."""
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

    # Standard param configs: rebal × n_ls
    configs = [(r, n) for r in [3, 5, 7] for n in [3, 4]]
    results = {}

    # H-860: Upside Capture
    for window in [20, 30, 40]:
        sig = upside_capture_signal(closes, window)
        r = run_signal(f"H-860 (Upside Capture W{window})", sig, closes, window, configs)
        if r.get("sharpe", 0) > results.get("H-860", {}).get("sharpe", -99):
            results["H-860"] = r

    # H-861: Downside Protection
    for window in [20, 30, 40]:
        sig = downside_protection_signal(closes, window)
        r = run_signal(f"H-861 (Downside Protect W{window})", sig, closes, window, configs)
        if r.get("sharpe", 0) > results.get("H-861", {}).get("sharpe", -99):
            results["H-861"] = r

    # H-862: Up-Down Capture Ratio
    for window in [20, 30, 40]:
        sig = updown_ratio_signal(closes, window)
        r = run_signal(f"H-862 (Up-Down Ratio W{window})", sig, closes, window, configs)
        if r.get("sharpe", 0) > results.get("H-862", {}).get("sharpe", -99):
            results["H-862"] = r

    # H-863: Win Rate
    for window in [15, 20, 30]:
        sig = win_rate_signal(closes, window)
        r = run_signal(f"H-863 (Win Rate W{window})", sig, closes, window, configs)
        if r.get("sharpe", 0) > results.get("H-863", {}).get("sharpe", -99):
            results["H-863"] = r

    # H-864: Conditional Momentum
    for window in [20, 30, 40]:
        sig = conditional_momentum_signal(closes, volumes, window)
        r = run_signal(f"H-864 (Conditional Mom W{window})", sig, closes, window, configs)
        if r.get("sharpe", 0) > results.get("H-864", {}).get("sharpe", -99):
            results["H-864"] = r

    # H-865: Return Consistency
    for window in [20, 30, 40]:
        sig = return_consistency_signal(closes, window)
        r = run_signal(f"H-865 (Ret Consistency W{window})", sig, closes, window, configs)
        if r.get("sharpe", 0) > results.get("H-865", {}).get("sharpe", -99):
            results["H-865"] = r

    # H-866: VW Return Divergence
    for window in [15, 20, 30]:
        sig = vw_return_divergence_signal(closes, volumes, window)
        r = run_signal(f"H-866 (VW Return Div W{window})", sig, closes, window, configs)
        if r.get("sharpe", 0) > results.get("H-866", {}).get("sharpe", -99):
            results["H-866"] = r

    # H-867: Max Gain Dependency
    for window in [20, 30, 40]:
        sig = max_gain_dependency_signal(closes, window)
        r = run_signal(f"H-867 (Max Gain Dep W{window})", sig, closes, window, configs)
        if r.get("sharpe", 0) > results.get("H-867", {}).get("sharpe", -99):
            results["H-867"] = r

    print("\n" + "=" * 60)
    print("BATCH 1 SUMMARY: Return Decomposition & Quality")
    print("=" * 60)
    for h, r in sorted(results.items()):
        status = r.get("status", "PASSED_IS")
        if status == "REJECTED_IS":
            print(f"  {h}: REJECTED (IS Sharpe {r['sharpe']:.3f}, {r['pos_pct']:.0f}% pos)")
        else:
            wf_pass = sum(1 for w in r["wf"] if w > 0)
            sh_p = r["sh"][2]
            print(f"  {h}: Sharpe {r['sharpe']:.3f}, WF {wf_pass}/{len(r['wf'])}, "
                  f"SH p={sh_p:.4f}, corr {r['corr']}")
            if wf_pass >= len(r["wf"]) * 0.6 and sh_p < 0.10 and abs(r["corr"]) < 0.5:
                print(f"    >>> CONFIRMED — {r['params']}")
            elif wf_pass >= len(r["wf"]) * 0.5:
                print(f"    >>> BORDERLINE — needs review")
            else:
                print(f"    >>> REJECTED (WF fail)")

    return results


if __name__ == "__main__":
    results = run_batch()
