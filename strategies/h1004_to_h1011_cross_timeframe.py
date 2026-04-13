"""
Batch backtest: H-1004 to H-1011 — Cross-Timeframe XS Signals.

H-1004: Weekly Return Rank — rank by prior full-week return (cleaner than daily noise)
H-1005: 4H Momentum Consistency — pct of 4H bars with positive return over 60 4H bars
H-1006: Multi-Day Range Breakout — current close vs 20-day high/low range position
H-1007: Intraweek Recovery — how fast assets recover from weekly low (resilience)
H-1008: Close Location in Range — (close - low) / (high - low) averaged over lookback
H-1009: Consecutive Up Days — count of consecutive positive daily returns
H-1010: Weekly Volume Profile — current week's volume vs prior 4-week avg
H-1011: Close vs VWAP Position — rolling close position relative to vol-weighted avg price proxy
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

def weekly_return_rank(closes, period=7):
    """H-1004: Prior full-week return — cleaner than daily momentum noise."""
    return closes.pct_change(period)


def momentum_4h_consistency(closes, n_days=15):
    """H-1005: Fraction of daily returns that are positive over lookback.
    Proxy for 4H consistency using daily data — consistent movers vs. spiky."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(n_days + 1, len(closes)):
        for col in closes.columns:
            rets = returns[col].iloc[i - n_days:i].dropna().values
            if len(rets) < n_days // 2:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = np.mean(rets > 0)
    return signal


def multi_day_range_position(closes, period=20):
    """H-1006: Where does current close sit in the 20-day high-low range?
    Score = (close - period_low) / (period_high - period_low). High = near top."""
    high_roll = closes.rolling(period).max()
    low_roll = closes.rolling(period).min()
    rng = high_roll - low_roll
    rng = rng.replace(0, np.nan)
    return (closes - low_roll) / rng


def intraweek_recovery(closes, highs, lows, period=20):
    """H-1007: Average daily recovery from low. How much of the day's range
    does the close capture? Resilient assets close near highs."""
    daily_range = highs - lows
    daily_range = daily_range.replace(0, np.nan)
    recovery = (closes - lows) / daily_range  # 0 = close at low, 1 = close at high
    return recovery.rolling(period).mean()


def close_location_in_range(closes, highs, lows, period=10):
    """H-1008: Average (close - low)/(high - low) over lookback.
    Assets consistently closing near highs are in demand."""
    daily_range = highs - lows
    daily_range = daily_range.replace(0, np.nan)
    clv = (closes - lows) / daily_range
    return clv.rolling(period).mean()


def consecutive_up_days(closes, lookback=20):
    """H-1009: Maximum streak of consecutive positive daily returns in lookback.
    Long assets with longer winning streaks (trend persistence)."""
    returns = closes.pct_change()
    up = (returns > 0).astype(float)
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(lookback + 1, len(closes)):
        for col in closes.columns:
            streak = up[col].iloc[i - lookback:i].values
            max_streak = 0
            current = 0
            for v in streak:
                if v > 0:
                    current += 1
                    max_streak = max(max_streak, current)
                else:
                    current = 0
            signal.iloc[i, signal.columns.get_loc(col)] = max_streak
    return signal


def weekly_volume_profile(volumes, period=20):
    """H-1010: Current 5-day volume vs 20-day average volume.
    Volume surge = attention/inflow. Similar to H-085 but shorter lookback."""
    avg_short = volumes.rolling(5).mean()
    avg_long = volumes.rolling(period).mean()
    avg_long = avg_long.replace(0, np.nan)
    return avg_short / avg_long


def close_vs_vwap(closes, volumes, period=20):
    """H-1011: Close position relative to volume-weighted average price proxy.
    VWAP proxy = sum(close * volume) / sum(volume) over period.
    Close > VWAP = buying pressure. Score = (close - vwap) / vwap."""
    vwap = (closes * volumes).rolling(period).sum() / volumes.rolling(period).sum()
    vwap = vwap.replace(0, np.nan)
    return (closes - vwap) / vwap


# ============================================================
# BATCH RUNNER
# ============================================================

def run_signal(name, signal_df, closes, lookback, param_configs, direction="high_long"):
    print(f"\n=== {name} ===")
    best = {"sharpe": -99}
    all_sharpes = []

    for rebal, n_ls in param_configs:
        pnl = xs_backtest(closes, signal_df, lookback, rebal, n_ls, direction)
        m = compute_metrics(pnl)
        all_sharpes.append(m["sharpe"])
        if m["sharpe"] > best.get("sharpe", -99):
            best = {"rebal": rebal, "n_ls": n_ls, "direction": direction, **m,
                    "pnl": pnl, "lookback": lookback}

    if best["sharpe"] <= 0:
        pos_pct = sum(1 for s in all_sharpes if s > 0) / len(all_sharpes) * 100 if all_sharpes else 0
        print(f"  Best IS Sharpe: {best['sharpe']:.3f} | {pos_pct:.0f}% positive | SKIP")
        return None

    # Try reverse direction
    for rebal, n_ls in param_configs:
        pnl = xs_backtest(closes, signal_df, lookback, rebal, n_ls,
                          "low_long" if direction == "high_long" else "high_long")
        m = compute_metrics(pnl)
        all_sharpes.append(m["sharpe"])
        if m["sharpe"] > best.get("sharpe", -99):
            rev_dir = "low_long" if direction == "high_long" else "high_long"
            best = {"rebal": rebal, "n_ls": n_ls, "direction": rev_dir, **m,
                    "pnl": pnl, "lookback": lookback}

    pos_pct = sum(1 for s in all_sharpes if s > 0) / len(all_sharpes) * 100 if all_sharpes else 0
    print(f"  Best IS: Sharpe {best['sharpe']:.3f}, Ret {best['annual_ret']:.1f}%, "
          f"DD {best['max_dd']:.1f}% | {pos_pct:.0f}% positive | dir={best['direction']}")

    if best["sharpe"] < 0.8:
        print(f"  IS Sharpe {best['sharpe']:.3f} < 0.8 — SKIP")
        return None

    # Walk-forward
    wf = walk_forward(closes, signal_df, best["lookback"], best["rebal"],
                      best["n_ls"], best["direction"])
    wf_pos = sum(1 for w in wf if w > 0)
    wf_mean = np.mean(wf) if wf else 0
    print(f"  WF: {wf_pos}/{len(wf)} positive, mean {wf_mean:.3f} | folds: {[round(w,2) for w in wf]}")

    if wf_pos < len(wf) * 0.5:
        print(f"  WF {wf_pos}/{len(wf)} < 50% — FAIL")
        return None

    # Split-half test
    sh1, sh2, p_val = split_half_test(best["pnl"])
    print(f"  Split-half: {sh1:.3f} / {sh2:.3f}, SH p={p_val:.4f}")

    # H-012 correlation
    corr = h012_correlation(closes, signal_df, best["lookback"], best["rebal"],
                            best["n_ls"], best["direction"])
    print(f"  H-012 corr: {corr:.3f}")

    status = "CONFIRMED" if (wf_pos >= len(wf) * 0.5 and p_val < 0.10 and abs(corr) < 0.50) else "BORDERLINE"
    print(f"  >>> {status}")

    return {
        "name": name,
        "status": status,
        "sharpe": best["sharpe"],
        "annual_ret": best["annual_ret"],
        "max_dd": best["max_dd"],
        "rebal": best["rebal"],
        "n_ls": best["n_ls"],
        "direction": best["direction"],
        "lookback": best["lookback"],
        "wf": wf,
        "wf_pos": wf_pos,
        "wf_total": len(wf),
        "sh1": sh1,
        "sh2": sh2,
        "p_val": p_val,
        "h012_corr": corr,
        "pos_pct": pos_pct,
    }


if __name__ == "__main__":
    closes, highs, lows, opens, volumes = load_data()
    print(f"Data: {len(closes)} days, {len(closes.columns)} assets, "
          f"{closes.index[0].date()} to {closes.index[-1].date()}")

    param_configs = [(3, 4), (5, 4), (7, 4), (5, 3), (7, 3), (10, 4), (5, 5), (7, 5)]
    results = {}

    # H-1004: Weekly Return Rank
    sig = weekly_return_rank(closes, 7)
    results["H-1004"] = run_signal("H-1004 Weekly Return Rank", sig, closes, 10, param_configs, "high_long")

    # H-1005: Daily Positive Fraction (4H consistency proxy)
    sig = momentum_4h_consistency(closes, 15)
    results["H-1005"] = run_signal("H-1005 Momentum Consistency (daily pos frac)", sig, closes, 20, param_configs, "high_long")

    # H-1006: Multi-Day Range Position
    sig = multi_day_range_position(closes, 20)
    results["H-1006"] = run_signal("H-1006 Multi-Day Range Position", sig, closes, 25, param_configs, "high_long")

    # H-1007: Intraweek Recovery (close near high)
    sig = intraweek_recovery(closes, highs, lows, 20)
    results["H-1007"] = run_signal("H-1007 Intraweek Recovery", sig, closes, 25, param_configs, "high_long")

    # H-1008: Close Location in Range
    sig = close_location_in_range(closes, highs, lows, 10)
    results["H-1008"] = run_signal("H-1008 Close Location in Range (10d)", sig, closes, 15, param_configs, "high_long")

    # H-1009: Consecutive Up Days
    sig = consecutive_up_days(closes, 20)
    results["H-1009"] = run_signal("H-1009 Consecutive Up Days (20d)", sig, closes, 25, param_configs, "high_long")

    # H-1010: Weekly Volume Profile
    sig = weekly_volume_profile(volumes, 20)
    results["H-1010"] = run_signal("H-1010 Weekly Volume Profile", sig, closes, 25, param_configs, "high_long")

    # H-1011: Close vs VWAP
    sig = close_vs_vwap(closes, volumes, 20)
    results["H-1011"] = run_signal("H-1011 Close vs VWAP Proxy", sig, closes, 25, param_configs, "high_long")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    confirmed = []
    for k, v in results.items():
        if v is not None:
            tag = "✓ CONFIRMED" if v["status"] == "CONFIRMED" else "~ BORDERLINE"
            print(f"  {tag} {k}: IS {v['sharpe']:.3f}, WF {v['wf_pos']}/{v['wf_total']}, "
                  f"SH p={v['p_val']:.4f}, corr {v['h012_corr']:.3f}")
            if v["status"] == "CONFIRMED":
                confirmed.append(k)
        else:
            print(f"  ✗ REJECTED {k}")
    print(f"\nConfirmed: {len(confirmed)} — {confirmed}")
