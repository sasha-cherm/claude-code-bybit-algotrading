"""
Batch backtest: H-868 to H-875 — Short-Term Reversal & Mean Reversion XS Signals.

H-868: 1-Day Reversal XS — contrarian on 1-day returns
H-869: 3-Day Reversal XS — contrarian on 3-day returns
H-870: 5-Day Reversal XS — contrarian on 5-day returns
H-871: 10-Day Reversal XS — contrarian on 10-day returns
H-872: RSI(14) Contrarian XS — buy oversold, sell overbought
H-873: Distance from 20-Day High XS — long close to high, short far from high
H-874: Z-Score Mean Reversion XS — price z-score vs 20d MA (contrarian)
H-875: Bollinger Band Position XS — position within bands (contrarian)
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

def reversal_signal(closes, lookback):
    """Short-term reversal: negative of recent return (contrarian)."""
    return -closes.pct_change(lookback)


def rsi_contrarian_signal(closes, period=14):
    """RSI Contrarian: negative RSI (buy oversold, sell overbought)."""
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return -rsi  # Contrarian: low RSI = buy signal


def distance_from_high_signal(closes, window=20):
    """Distance from rolling high: close / rolling_max - 1.
    Momentum: long close to high (near 0), short far from high (deeply negative)."""
    rolling_high = closes.rolling(window).max()
    return closes / rolling_high.replace(0, np.nan) - 1


def zscore_reversion_signal(closes, window=20):
    """Z-score of price relative to moving average (contrarian).
    Buy low z-score (below MA), sell high z-score (above MA)."""
    ma = closes.rolling(window).mean()
    std = closes.rolling(window).std().replace(0, np.nan)
    z = (closes - ma) / std
    return -z  # Contrarian


def bollinger_position_signal(closes, window=20, num_std=2):
    """Position within Bollinger Bands (contrarian).
    (close - lower) / (upper - lower): 0 = at lower, 1 = at upper.
    Contrarian: buy near lower band, sell near upper band."""
    ma = closes.rolling(window).mean()
    std = closes.rolling(window).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    band_width = (upper - lower).replace(0, np.nan)
    position = (closes - lower) / band_width
    return -position  # Contrarian: long near lower band


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

    # H-868: 1-Day Reversal
    sig = reversal_signal(closes, 1)
    results["H-868"] = run_signal("H-868 (1-Day Reversal)", sig, closes, 5, configs)

    # H-869: 3-Day Reversal
    sig = reversal_signal(closes, 3)
    results["H-869"] = run_signal("H-869 (3-Day Reversal)", sig, closes, 5, configs)

    # H-870: 5-Day Reversal
    sig = reversal_signal(closes, 5)
    results["H-870"] = run_signal("H-870 (5-Day Reversal)", sig, closes, 7, configs)

    # H-871: 10-Day Reversal
    sig = reversal_signal(closes, 10)
    results["H-871"] = run_signal("H-871 (10-Day Reversal)", sig, closes, 12, configs)

    # H-872: RSI(14) Contrarian
    for period in [10, 14, 21]:
        sig = rsi_contrarian_signal(closes, period)
        r = run_signal(f"H-872 (RSI Contrarian P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-872", {}).get("sharpe", -99):
            results["H-872"] = r

    # H-873: Distance from High (momentum direction — not contrarian)
    for window in [10, 20, 30]:
        sig = distance_from_high_signal(closes, window)
        r = run_signal(f"H-873 (Dist from High W{window})", sig, closes, window, configs)
        if r.get("sharpe", 0) > results.get("H-873", {}).get("sharpe", -99):
            results["H-873"] = r

    # H-874: Z-Score Mean Reversion
    for window in [10, 20, 30]:
        sig = zscore_reversion_signal(closes, window)
        r = run_signal(f"H-874 (Z-Score Revert W{window})", sig, closes, window, configs)
        if r.get("sharpe", 0) > results.get("H-874", {}).get("sharpe", -99):
            results["H-874"] = r

    # H-875: Bollinger Band Position
    for window in [15, 20, 30]:
        sig = bollinger_position_signal(closes, window)
        r = run_signal(f"H-875 (Bollinger Pos W{window})", sig, closes, window, configs)
        if r.get("sharpe", 0) > results.get("H-875", {}).get("sharpe", -99):
            results["H-875"] = r

    print("\n" + "=" * 60)
    print("BATCH 2 SUMMARY: Short-Term Reversal & Mean Reversion")
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
