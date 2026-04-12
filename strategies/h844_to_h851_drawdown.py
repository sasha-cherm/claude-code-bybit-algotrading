"""
Batch backtest: H-844 to H-851 — Drawdown dynamics and recovery signals.

H-844: Current Drawdown Depth — how far from rolling high (contrarian: buy deep DD)
H-845: Drawdown Duration — how many days since peak (buy long-duration DD = exhaustion)
H-846: Recovery Speed — rate of change in drawdown (improving = buy)
H-847: Drawdown-Adjusted Momentum — momentum penalized by DD depth
H-848: Max Gain Factor — max rolling gain (from trough) as strength signal
H-849: Underwater Volatility — vol during drawdown periods vs overall
H-850: Peak Distance Ratio — current price / all-time-window high
H-851: Drawdown Mean Reversion — z-score of current DD vs historical DD distribution
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
            sig_row = signal_df.iloc[i - 1].dropna()
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

def current_drawdown_signal(closes, window):
    """H-844: Current drawdown from rolling high. Contrarian: buy deep drawdowns."""
    rolling_high = closes.rolling(window).max()
    dd = (closes - rolling_high) / rolling_high.replace(0, np.nan)
    # Contrarian: long deepest drawdowns (most negative → highest signal)
    return dd  # Most negative = buy


def drawdown_duration_signal(closes, window):
    """H-845: Days since rolling high. Long assets with longest duration (exhaustion)."""
    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    rolling_high = closes.rolling(window).max()
    for col in closes.columns:
        duration = pd.Series(0, index=closes.index, dtype=float)
        count = 0
        for i in range(window, len(closes)):
            if closes[col].iloc[i] >= rolling_high[col].iloc[i] * 0.999:
                count = 0
            else:
                count += 1
            duration.iloc[i] = count
        signal[col] = duration
    return signal  # Long high duration = exhaustion reversal


def recovery_speed_signal(closes, window, short_window=5):
    """H-846: Rate of change of drawdown (improving DD = recovery signal)."""
    rolling_high = closes.rolling(window).max()
    dd = (closes - rolling_high) / rolling_high.replace(0, np.nan)
    # Recovery speed = change in drawdown over short window
    # Positive = DD improving (getting less negative)
    return dd.diff(short_window)


def dd_adjusted_momentum_signal(closes, mom_window, dd_window):
    """H-847: Momentum penalized by drawdown depth.
    High momentum + shallow DD = strongest signal."""
    mom = closes.pct_change(mom_window)
    rolling_high = closes.rolling(dd_window).max()
    dd = (closes - rolling_high) / rolling_high.replace(0, np.nan)
    # DD is negative, so (1 + dd) is < 1 for drawdown assets
    # Momentum × (1 + dd) penalizes assets in drawdown
    return mom * (1 + dd)


def max_gain_signal(closes, window):
    """H-848: Maximum gain from rolling trough within window. Strength indicator."""
    rolling_low = closes.rolling(window).min()
    max_gain = (closes - rolling_low) / rolling_low.replace(0, np.nan)
    return max_gain


def underwater_vol_signal(closes, window):
    """H-849: Volatility during drawdown vs overall. High underwater vol = risky."""
    ret = closes.pct_change()
    rolling_high = closes.rolling(window).max()
    in_dd = closes < rolling_high * 0.99  # At least 1% below peak

    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(window + 10, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i - window:i]
            dd_mask = in_dd[col].iloc[i - window:i]
            r_dd = r[dd_mask]
            r_all = r
            if len(r_dd) > 5 and r_all.std() > 0:
                signal.iloc[i, signal.columns.get_loc(col)] = r_dd.std() / r_all.std()
    return -signal  # Long = low underwater vol (calm drawdowns)


def peak_distance_signal(closes, window):
    """H-850: Current price / rolling high. Proximity to peak."""
    rolling_high = closes.rolling(window).max()
    return closes / rolling_high.replace(0, np.nan)


def dd_mean_reversion_signal(closes, window, zscore_window=60):
    """H-851: Z-score of current DD vs historical DD distribution.
    Extreme negative z-score = DD unusually deep → reversion expected."""
    rolling_high = closes.rolling(window).max()
    dd = (closes - rolling_high) / rolling_high.replace(0, np.nan)
    dd_mean = dd.rolling(zscore_window).mean()
    dd_std = dd.rolling(zscore_window).std().replace(0, np.nan)
    z = (dd - dd_mean) / dd_std
    return z  # Very negative = unusually deep DD → contrarian long


def run_batch():
    print("Loading data...")
    closes, highs, lows, opens, volumes = load_data()
    print(f"Data: {len(closes)} days, {len(closes.columns)} assets, "
          f"{closes.index[0].date()} to {closes.index[-1].date()}")

    results = {}

    hypotheses = [
        ("H-844", "Current Drawdown Depth (contrarian)",
         lambda c, w: current_drawdown_signal(c, w), [30, 60, 90], "high_long"),
        ("H-845", "Drawdown Duration (exhaustion reversal)",
         lambda c, w: drawdown_duration_signal(c, w), [30, 60, 90], "high_long"),
        ("H-846", "Recovery Speed",
         lambda c, w: recovery_speed_signal(c, w), [30, 60], "high_long"),
        ("H-847", "DD-Adjusted Momentum",
         lambda c, w: dd_adjusted_momentum_signal(c, w, w), [30, 60], "high_long"),
        ("H-848", "Max Gain Factor",
         lambda c, w: max_gain_signal(c, w), [20, 30, 60], "high_long"),
        ("H-849", "Underwater Volatility",
         lambda c, w: underwater_vol_signal(c, w), [30, 60], "high_long"),
        ("H-850", "Peak Distance Ratio",
         lambda c, w: peak_distance_signal(c, w), [30, 60, 90], "high_long"),
        ("H-851", "DD Mean Reversion",
         lambda c, w: dd_mean_reversion_signal(c, w), [30, 60], "high_long"),
    ]

    for h_id, h_name, sig_func, windows, direction in hypotheses:
        print(f"\n=== {h_id}: {h_name} ===")
        best = {"sharpe": -99}
        params_all = []
        for window in windows:
            try:
                sig = sig_func(closes, window)
            except Exception as e:
                print(f"  Signal error: {e}")
                continue
            for rebal in [3, 5, 7]:
                for n_ls in [3, 4]:
                    pnl = xs_backtest(closes, sig, window, rebal, n_ls, direction)
                    sh = compute_sharpe(pnl)
                    params_all.append(sh)
                    if sh > best["sharpe"]:
                        best = {"sharpe": sh, "window": window, "rebal": rebal,
                                "n_ls": n_ls, "pnl": pnl, "signal": sig}

        if not params_all:
            print("  No valid params")
            results[h_id] = {"status": "REJECTED_IS", "pos_pct": 0, "sharpe": 0}
            continue

        pos_pct = sum(1 for s in params_all if s > 0) / len(params_all) * 100
        print(f"  IS: {pos_pct:.0f}% positive ({sum(1 for s in params_all if s > 0)}/{len(params_all)})")
        print(f"  Best: W{best['window']}_R{best['rebal']}_N{best['n_ls']} "
              f"Sharpe {best['sharpe']:.3f}")
        m = compute_metrics(best["pnl"])
        print(f"  Metrics: {m}")

        if pos_pct >= 80 and best["sharpe"] > 0.8:
            wf = walk_forward(closes, best["signal"], best["window"],
                              best["rebal"], best["n_ls"], direction)
            sh1, sh2, p = split_half_test(best["pnl"])
            corr = h012_correlation(closes, best["signal"], best["window"],
                                    best["rebal"], best["n_ls"], direction)
            print(f"  WF: {[round(w, 3) for w in wf]} ({sum(1 for w in wf if w > 0)}/{len(wf)})")
            print(f"  SH: {sh1:.3f}/{sh2:.3f}, p={p:.4f}")
            print(f"  H-012 corr: {corr}")
            results[h_id] = {"sharpe": best["sharpe"], "pos_pct": pos_pct,
                             "wf": wf, "sh": (sh1, sh2, p), "corr": corr, "metrics": m,
                             "params": f"W{best['window']}_R{best['rebal']}_N{best['n_ls']}"}
        else:
            print(f"  REJECTED at IS — {pos_pct:.0f}% positive, Sharpe {best['sharpe']:.3f}")
            results[h_id] = {"status": "REJECTED_IS", "pos_pct": pos_pct,
                             "sharpe": best["sharpe"]}

    # Summary
    print("\n" + "=" * 60)
    print("BATCH 2 SUMMARY: Drawdown Dynamics")
    print("=" * 60)
    for h, r in results.items():
        status = r.get("status", "")
        if "REJECTED" in status:
            print(f"  {h}: REJECTED — IS {r['pos_pct']:.0f}% positive, Sharpe {r['sharpe']:.3f}")
        else:
            wf = r["wf"]
            wf_pass = sum(1 for w in wf if w > 0)
            sh1, sh2, p = r["sh"]
            sh_pass = "PASS" if p < 0.10 else "FAIL"
            print(f"  {h}: Sharpe {r['sharpe']:.3f}, WF {wf_pass}/{len(wf)}, "
                  f"SH {sh1:.3f}/{sh2:.3f} p={p:.4f} ({sh_pass}), "
                  f"H-012 corr {r['corr']}, params: {r['params']}")

    return results


if __name__ == "__main__":
    run_batch()
