"""
Batch backtest: H-1028 to H-1035 — Calendar / Seasonal Cross-Sectional Signals.

H-1028: Turn-of-Month Effect — XS: which assets show strongest turn-of-month return pattern
H-1029: Monthly Return Persistence — does last month's XS rank persist into this month?
H-1030: Return Horizon Ratio — 7d/30d return ratio (momentum acceleration/deceleration)
H-1031: Same-Weekday Momentum — average return on same weekday over past N weeks
H-1032: Intramonth Position — performance in first vs second half of month (XS)
H-1033: Lagged Week Return — prior week's XS return as signal for current week
H-1034: Monthly Reversal — short recent monthly winners, long monthly losers (XS reversal)
H-1035: Day-of-Month Seasonality — which assets outperform at specific month phases
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

def turn_of_month(closes, lookback_months=6):
    """H-1028: Turn-of-month XS effect. Compute average return in last 3 + first 3 days
    of month vs mid-month for each asset. Rank by TOM outperformance."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(60, len(closes)):
        day_of_month = closes.index[i].day
        days_in_month = pd.Timestamp(closes.index[i]).days_in_month
        # Compute rolling average TOM return for each asset
        for col in closes.columns:
            window = returns[col].iloc[max(0, i-180):i].dropna()
            if len(window) < 60:
                continue
            # Classify each day as TOM (day <= 3 or day >= days_in_month - 2) or not
            tom_rets = []
            non_tom_rets = []
            for j in range(len(window)):
                idx = window.index[j]
                d = idx.day
                dim = pd.Timestamp(idx).days_in_month
                if d <= 3 or d >= dim - 2:
                    tom_rets.append(window.iloc[j])
                else:
                    non_tom_rets.append(window.iloc[j])
            if len(tom_rets) > 5 and len(non_tom_rets) > 5:
                tom_avg = np.mean(tom_rets)
                non_tom_avg = np.mean(non_tom_rets)
                signal.iloc[i, signal.columns.get_loc(col)] = tom_avg - non_tom_avg
    return signal


def monthly_return_persistence(closes):
    """H-1029: Last 30-day XS return rank as predictor for next period.
    Simple monthly momentum — does last month's cross-sectional winner persist?"""
    return closes.pct_change(30)


def return_horizon_ratio(closes, short=7, long=30):
    """H-1030: Ratio of short-term to long-term return. High = accelerating momentum.
    If 7d return > proportional share of 30d return, momentum is freshening."""
    short_ret = closes.pct_change(short)
    long_ret = closes.pct_change(long)
    # Avoid division by zero
    long_ret_safe = long_ret.replace(0, np.nan)
    ratio = short_ret / long_ret_safe.abs()
    # Positive long_ret and high ratio = accelerating uptrend
    # Use signed version: short_ret / |long_ret| * sign(long_ret)
    return short_ret * np.sign(long_ret)


def same_weekday_momentum(closes, n_weeks=8):
    """H-1031: Average return on same weekday over past N weeks.
    Some assets have systematic weekday patterns (e.g., always strong on Tuesday)."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(n_weeks * 7 + 5, len(closes)):
        target_weekday = closes.index[i].weekday()
        for col in closes.columns:
            # Collect returns on same weekday over past n_weeks weeks
            weekday_rets = []
            for w in range(1, n_weeks + 1):
                j = i - w * 7
                if j >= 0 and closes.index[j].weekday() == target_weekday:
                    r = returns[col].iloc[j]
                    if np.isfinite(r):
                        weekday_rets.append(r)
            if len(weekday_rets) >= 4:
                signal.iloc[i, signal.columns.get_loc(col)] = np.mean(weekday_rets)
    return signal


def intramonth_position(closes, lookback_months=3):
    """H-1032: First-half vs second-half of month relative performance.
    Track which assets consistently outperform in early vs late month."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(90, len(closes)):
        for col in closes.columns:
            window = returns[col].iloc[max(0, i-90):i].dropna()
            if len(window) < 30:
                continue
            first_half = [window.iloc[j] for j in range(len(window))
                         if window.index[j].day <= 15]
            second_half = [window.iloc[j] for j in range(len(window))
                          if window.index[j].day > 15]
            if len(first_half) > 10 and len(second_half) > 10:
                # Current day determines which signal to use
                if closes.index[i].day <= 15:
                    signal.iloc[i, signal.columns.get_loc(col)] = np.mean(first_half)
                else:
                    signal.iloc[i, signal.columns.get_loc(col)] = np.mean(second_half)
    return signal


def lagged_week_return(closes):
    """H-1033: Prior week's XS return as signal. Simple weekly momentum carry-over.
    Assets that did well last week continue to outperform this week."""
    return closes.pct_change(7).shift(1)


def monthly_reversal(closes, period=30):
    """H-1034: Short recent monthly winners, long monthly losers.
    Monthly reversal — overreaction correction at 1-month horizon."""
    return -closes.pct_change(period)  # Negative = reversal (long losers)


def day_of_month_seasonality(closes, lookback_months=6):
    """H-1035: Rolling average return by day-of-month phase (early/mid/late).
    Captures systematic within-month timing patterns per asset."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(180, len(closes)):
        day = closes.index[i].day
        # Classify: early (1-10), mid (11-20), late (21-31)
        if day <= 10:
            phase = "early"
        elif day <= 20:
            phase = "mid"
        else:
            phase = "late"
        for col in closes.columns:
            window = returns[col].iloc[max(0, i-180):i].dropna()
            if len(window) < 60:
                continue
            phase_rets = []
            for j in range(len(window)):
                d = window.index[j].day
                if phase == "early" and d <= 10:
                    phase_rets.append(window.iloc[j])
                elif phase == "mid" and 11 <= d <= 20:
                    phase_rets.append(window.iloc[j])
                elif phase == "late" and d > 20:
                    phase_rets.append(window.iloc[j])
            if len(phase_rets) > 10:
                signal.iloc[i, signal.columns.get_loc(col)] = np.mean(phase_rets)
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
        print(f"  IS Sharpe {best['sharpe']:.3f} < 0.8 -- SKIP")
        return None

    # Walk-forward
    wf = walk_forward(closes, signal_df, best["lookback"], best["rebal"],
                      best["n_ls"], best["direction"])
    wf_pos = sum(1 for w in wf if w > 0)
    wf_mean = np.mean(wf) if wf else 0
    print(f"  WF: {wf_pos}/{len(wf)} positive, mean {wf_mean:.3f} | folds: {[round(w,2) for w in wf]}")

    if wf_pos < len(wf) * 0.5:
        print(f"  WF {wf_pos}/{len(wf)} < 50% -- FAIL")
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

    # H-1028: Turn-of-Month Effect
    sig = turn_of_month(closes)
    results["H-1028"] = run_signal("H-1028 Turn-of-Month Effect", sig, closes, 65, param_configs, "high_long")

    # H-1029: Monthly Return Persistence
    sig = monthly_return_persistence(closes)
    results["H-1029"] = run_signal("H-1029 Monthly Return Persistence", sig, closes, 35, param_configs, "high_long")

    # H-1030: Return Horizon Ratio
    sig = return_horizon_ratio(closes, 7, 30)
    results["H-1030"] = run_signal("H-1030 Return Horizon Ratio (7d/30d)", sig, closes, 35, param_configs, "high_long")

    # H-1031: Same-Weekday Momentum
    sig = same_weekday_momentum(closes, 8)
    results["H-1031"] = run_signal("H-1031 Same-Weekday Momentum", sig, closes, 60, param_configs, "high_long")

    # H-1032: Intramonth Position
    sig = intramonth_position(closes)
    results["H-1032"] = run_signal("H-1032 Intramonth Position", sig, closes, 95, param_configs, "high_long")

    # H-1033: Lagged Week Return
    sig = lagged_week_return(closes)
    results["H-1033"] = run_signal("H-1033 Lagged Week Return", sig, closes, 12, param_configs, "high_long")

    # H-1034: Monthly Reversal
    sig = monthly_reversal(closes, 30)
    results["H-1034"] = run_signal("H-1034 Monthly Reversal", sig, closes, 35, param_configs, "high_long")

    # H-1035: Day-of-Month Seasonality
    sig = day_of_month_seasonality(closes)
    results["H-1035"] = run_signal("H-1035 Day-of-Month Seasonality", sig, closes, 185, param_configs, "high_long")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    confirmed = []
    for k, v in results.items():
        if v is not None:
            tag = "CONFIRMED" if v["status"] == "CONFIRMED" else "~ BORDERLINE"
            print(f"  {tag} {k}: IS {v['sharpe']:.3f}, WF {v['wf_pos']}/{v['wf_total']}, "
                  f"SH p={v['p_val']:.4f}, corr {v['h012_corr']:.3f}")
            if v["status"] == "CONFIRMED":
                confirmed.append(k)
        else:
            print(f"  REJECTED {k}")
    print(f"\nConfirmed: {len(confirmed)} -- {confirmed}")
