"""
Batch backtest: H-1036 to H-1043 — Return Persistence / Memory XS Signals.

H-1036: Consecutive Return Direction — length of current win/loss streak
H-1037: Return Regime Duration — days since return regime change (bull->bear or vice versa)
H-1038: Mean Reversion Timer — days since last local max/min in price
H-1039: Return Acceleration — 2nd derivative of cumulative return (change in momentum)
H-1040: Momentum Freshness — exponentially-weighted momentum (more weight on recent)
H-1041: Trend Persistence Ratio — fraction of days with same-sign return as overall trend
H-1042: Recovery Rate — speed of recovery from recent drawdown (slope of recovery)
H-1043: Return Predictability — R-squared of linear fit to recent returns (high = smooth trend)
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

def consecutive_return_direction(closes, max_lookback=20):
    """H-1036: Length of current consecutive win/loss streak.
    Positive = streak of positive days, negative = streak of negative days."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(5, len(closes)):
        for col in closes.columns:
            streak = 0
            for j in range(min(max_lookback, i)):
                r = returns[col].iloc[i - j]
                if not np.isfinite(r):
                    break
                if j == 0:
                    direction = 1 if r > 0 else -1
                    streak = direction
                elif (r > 0 and direction > 0) or (r < 0 and direction < 0):
                    streak += direction
                else:
                    break
            signal.iloc[i, signal.columns.get_loc(col)] = streak
    return signal


def return_regime_duration(closes, regime_period=10):
    """H-1037: Days since return regime changed. Regime = sign of rolling N-day return.
    Long duration = established trend, short duration = regime just changed."""
    rolling_ret = closes.pct_change(regime_period)
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for col in closes.columns:
        current_sign = None
        duration = 0
        for i in range(regime_period + 1, len(closes)):
            val = rolling_ret[col].iloc[i]
            if not np.isfinite(val):
                continue
            new_sign = 1 if val > 0 else -1
            if current_sign is None or new_sign != current_sign:
                current_sign = new_sign
                duration = 1
            else:
                duration += 1
            # Signed duration: positive for uptrend, negative for downtrend
            signal.iloc[i, signal.columns.get_loc(col)] = duration * current_sign
    return signal


def mean_reversion_timer(closes, period=30):
    """H-1038: Days since price was at its N-day rolling max or min.
    Near max = recently strong, near min = recently weak. Distance from peak."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for col in closes.columns:
        for i in range(period, len(closes)):
            window = closes[col].iloc[i - period:i + 1].values
            if not np.all(np.isfinite(window)):
                continue
            max_idx = np.argmax(window)
            min_idx = np.argmin(window)
            # How recent is the high vs the low
            days_from_high = period - max_idx
            days_from_low = period - min_idx
            # Positive if closer to high (recently strong)
            signal.iloc[i, signal.columns.get_loc(col)] = days_from_low - days_from_high
    return signal


def return_acceleration(closes, short=5, long=20):
    """H-1039: Second derivative of price — change in momentum.
    Positive = momentum accelerating, negative = decelerating."""
    mom_short = closes.pct_change(short)
    mom_long = closes.pct_change(long) / (long / short)  # Normalize to same scale
    # Acceleration = recent momentum - longer-term momentum rate
    return mom_short - mom_long


def momentum_freshness(closes, halflife=10, period=60):
    """H-1040: Exponentially-weighted momentum. Recent returns weighted more.
    Fresher momentum (recent outperformance) should persist better than stale."""
    returns = closes.pct_change()
    weights = np.exp(-np.log(2) / halflife * np.arange(period)[::-1])
    weights = weights / weights.sum()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            rets = returns[col].iloc[i - period:i].values
            if np.sum(np.isfinite(rets)) < period * 0.8:
                continue
            rets = np.where(np.isfinite(rets), rets, 0)
            signal.iloc[i, signal.columns.get_loc(col)] = np.sum(rets * weights)
    return signal


def trend_persistence_ratio(closes, period=30):
    """H-1041: Fraction of days where daily return matches overall trend direction.
    High ratio = persistent trend (most days positive if uptrend). Quality of trend."""
    returns = closes.pct_change()
    overall_ret = closes.pct_change(period)
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            ov = overall_ret[col].iloc[i]
            if not np.isfinite(ov) or ov == 0:
                continue
            trend_dir = 1 if ov > 0 else -1
            daily_rets = returns[col].iloc[i - period:i].dropna().values
            if len(daily_rets) < 15:
                continue
            same_dir = np.sum((daily_rets > 0) == (trend_dir > 0))
            ratio = same_dir / len(daily_rets)
            # Sign it: positive ratio for uptrend, negative for downtrend
            signal.iloc[i, signal.columns.get_loc(col)] = ratio * trend_dir
    return signal


def recovery_rate(closes, period=30):
    """H-1042: Speed of recovery from recent drawdown.
    Compute current drawdown from rolling max, then measure slope of recovery.
    Fast recoverers = strong mean reversion from pullbacks."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for col in closes.columns:
        prices = closes[col].values
        for i in range(period + 10, len(closes)):
            window = prices[i - period:i + 1]
            if not np.all(np.isfinite(window)):
                continue
            running_max = np.maximum.accumulate(window)
            dd = window / running_max - 1
            # If currently in drawdown, measure recovery slope over last 5 days
            if dd[-1] < -0.01:  # At least 1% drawdown
                recent_dd = dd[-5:]
                if len(recent_dd) >= 3:
                    # Slope: positive = recovering, negative = deepening
                    slope = (recent_dd[-1] - recent_dd[0]) / len(recent_dd)
                    signal.iloc[i, signal.columns.get_loc(col)] = slope
            else:
                # Not in drawdown — near highs is positive
                signal.iloc[i, signal.columns.get_loc(col)] = -dd[-1]  # Higher = closer to high
    return signal


def return_predictability(closes, period=20):
    """H-1043: R-squared of linear fit to log prices over past N days.
    High R2 = smooth, predictable trend. Low R2 = noisy, choppy."""
    log_prices = np.log(closes.replace(0, np.nan))
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    x = np.arange(period)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            y = log_prices[col].iloc[i - period:i].values
            if np.sum(np.isfinite(y)) < period * 0.8:
                continue
            y_clean = np.nan_to_num(y, np.nanmean(y))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y_clean)
            r2 = r_value ** 2
            # Sign by direction: positive R2 for uptrend, negative for downtrend
            signal.iloc[i, signal.columns.get_loc(col)] = r2 * np.sign(slope)
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

    # H-1036: Consecutive Return Direction
    sig = consecutive_return_direction(closes)
    results["H-1036"] = run_signal("H-1036 Consecutive Return Direction", sig, closes, 25, param_configs, "high_long")

    # H-1037: Return Regime Duration
    sig = return_regime_duration(closes, 10)
    results["H-1037"] = run_signal("H-1037 Return Regime Duration", sig, closes, 15, param_configs, "high_long")

    # H-1038: Mean Reversion Timer
    sig = mean_reversion_timer(closes, 30)
    results["H-1038"] = run_signal("H-1038 Mean Reversion Timer", sig, closes, 35, param_configs, "high_long")

    # H-1039: Return Acceleration
    sig = return_acceleration(closes, 5, 20)
    results["H-1039"] = run_signal("H-1039 Return Acceleration", sig, closes, 25, param_configs, "high_long")

    # H-1040: Momentum Freshness (EW)
    sig = momentum_freshness(closes, 10, 60)
    results["H-1040"] = run_signal("H-1040 Momentum Freshness (EW)", sig, closes, 65, param_configs, "high_long")

    # H-1041: Trend Persistence Ratio
    sig = trend_persistence_ratio(closes, 30)
    results["H-1041"] = run_signal("H-1041 Trend Persistence Ratio", sig, closes, 35, param_configs, "high_long")

    # H-1042: Recovery Rate
    sig = recovery_rate(closes, 30)
    results["H-1042"] = run_signal("H-1042 Recovery Rate", sig, closes, 40, param_configs, "high_long")

    # H-1043: Return Predictability (R2)
    sig = return_predictability(closes, 20)
    results["H-1043"] = run_signal("H-1043 Return Predictability (R2)", sig, closes, 25, param_configs, "high_long")

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
