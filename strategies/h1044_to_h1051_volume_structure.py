"""
Batch backtest: H-1044 to H-1051 — Volume Structure / Profile XS Signals.

H-1044: Volume Skewness — skewness of daily volume distribution (asymmetric interest)
H-1045: Volume Concentration — max daily volume / mean (captures institutional spikes)
H-1046: Relative Volume Duration — consecutive days with RVOL > 1 (sustained interest)
H-1047: Volume-Price Agreement — correlation between volume and |returns| (efficient pricing)
H-1048: Volume Decay Rate — how quickly do volume spikes mean-revert?
H-1049: Volume Gini — inequality of daily volumes (concentrated vs distributed activity)
H-1050: Buy Volume Ratio Trend — trend in (close > open) volume fraction (accumulation)
H-1051: Volume Momentum Spread — difference between short and long-term volume ratios
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

def volume_skewness(volumes, period=30):
    """H-1044: Skewness of daily volume distribution over past N days.
    Positive skew = occasional volume spikes (institutional interest)."""
    signal = pd.DataFrame(np.nan, index=volumes.index, columns=volumes.columns)
    for i in range(period + 5, len(volumes)):
        for col in volumes.columns:
            v = volumes[col].iloc[i - period:i].dropna().values
            if len(v) < 15:
                continue
            if np.std(v) == 0:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = stats.skew(v)
    return signal


def volume_concentration(volumes, period=30):
    """H-1045: Max daily volume / mean volume. High = concentrated activity (big player days).
    Institutional flow shows up as extreme volume concentration."""
    rolling_max = volumes.rolling(period).max()
    rolling_mean = volumes.rolling(period).mean()
    rolling_mean = rolling_mean.replace(0, np.nan)
    return rolling_max / rolling_mean


def relative_volume_duration(volumes, short=5, long=20):
    """H-1046: Count of consecutive days with short-term avg volume > long-term avg.
    Sustained high relative volume = persistent institutional interest."""
    rvol = volumes.rolling(short).mean() / volumes.rolling(long).mean()
    rvol = rvol.replace([np.inf, -np.inf], np.nan)
    signal = pd.DataFrame(np.nan, index=volumes.index, columns=volumes.columns)
    for col in volumes.columns:
        streak = 0
        for i in range(long + 5, len(volumes)):
            val = rvol[col].iloc[i]
            if not np.isfinite(val):
                streak = 0
                continue
            if val > 1.0:
                streak += 1
            else:
                streak = 0
            signal.iloc[i, signal.columns.get_loc(col)] = streak
    return signal


def volume_price_agreement(closes, volumes, period=20):
    """H-1047: Correlation between volume and absolute returns over past N days.
    High agreement = efficient market (volume validates price moves)."""
    returns = closes.pct_change().abs()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            if col not in volumes.columns:
                continue
            r = returns[col].iloc[i - period:i].dropna().values
            v = volumes[col].iloc[i - period:i].dropna().values
            mn = min(len(r), len(v))
            if mn < 10:
                continue
            corr = np.corrcoef(r[:mn], v[:mn])[0, 1]
            if np.isfinite(corr):
                signal.iloc[i, signal.columns.get_loc(col)] = corr
    return signal


def volume_decay_rate(volumes, spike_period=5, decay_period=20):
    """H-1048: How quickly volume spikes decay. Fast decay = transient interest.
    Slow decay = sustained institutional accumulation. Measured as autocorrelation of volume."""
    signal = pd.DataFrame(np.nan, index=volumes.index, columns=volumes.columns)
    for i in range(decay_period + 10, len(volumes)):
        for col in volumes.columns:
            v = volumes[col].iloc[i - decay_period:i].dropna().values
            if len(v) < 15:
                continue
            if np.std(v) == 0:
                continue
            # Autocorrelation of volume: high = persistent, low = mean-reverting
            ac = np.corrcoef(v[:-1], v[1:])[0, 1]
            if np.isfinite(ac):
                signal.iloc[i, signal.columns.get_loc(col)] = ac
    return signal


def volume_gini(volumes, period=30):
    """H-1049: Gini coefficient of daily volumes. High = concentrated activity on few days.
    Low = evenly distributed. Concentrated may indicate informed trading."""
    signal = pd.DataFrame(np.nan, index=volumes.index, columns=volumes.columns)
    for i in range(period + 5, len(volumes)):
        for col in volumes.columns:
            v = volumes[col].iloc[i - period:i].dropna().values
            if len(v) < 15:
                continue
            v_sorted = np.sort(v)
            n = len(v_sorted)
            if np.sum(v_sorted) == 0:
                continue
            cum = np.cumsum(v_sorted)
            gini = (2 * np.sum(np.arange(1, n + 1) * v_sorted) / (n * np.sum(v_sorted))) - (n + 1) / n
            signal.iloc[i, signal.columns.get_loc(col)] = gini
    return signal


def buy_volume_ratio_trend(closes, opens_df, volumes, short=5, long=20):
    """H-1050: Trend in buy-volume ratio (close > open = buy bar).
    Rising buy ratio = accumulation phase. Use short/long MA crossover."""
    buy_vol = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for col in closes.columns:
        if col in opens_df.columns and col in volumes.columns:
            is_buy = (closes[col] > opens_df[col]).astype(float)
            buy_vol[col] = is_buy
    buy_ratio_short = buy_vol.rolling(short).mean()
    buy_ratio_long = buy_vol.rolling(long).mean()
    return buy_ratio_short - buy_ratio_long


def volume_momentum_spread(volumes, short=5, mid=20, long=60):
    """H-1051: Difference between short-term and mid-term volume ratios vs long-term.
    Positive spread = accelerating volume interest across timeframes."""
    vm_short = volumes.rolling(short).mean() / volumes.rolling(long).mean()
    vm_mid = volumes.rolling(mid).mean() / volumes.rolling(long).mean()
    vm_short = vm_short.replace([np.inf, -np.inf], np.nan)
    vm_mid = vm_mid.replace([np.inf, -np.inf], np.nan)
    return vm_short - vm_mid


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

    # H-1044: Volume Skewness
    sig = volume_skewness(volumes, 30)
    results["H-1044"] = run_signal("H-1044 Volume Skewness", sig, closes, 35, param_configs, "high_long")

    # H-1045: Volume Concentration
    sig = volume_concentration(volumes, 30)
    results["H-1045"] = run_signal("H-1045 Volume Concentration", sig, closes, 35, param_configs, "high_long")

    # H-1046: Relative Volume Duration
    sig = relative_volume_duration(volumes, 5, 20)
    results["H-1046"] = run_signal("H-1046 Relative Volume Duration", sig, closes, 25, param_configs, "high_long")

    # H-1047: Volume-Price Agreement
    sig = volume_price_agreement(closes, volumes, 20)
    results["H-1047"] = run_signal("H-1047 Volume-Price Agreement", sig, closes, 25, param_configs, "high_long")

    # H-1048: Volume Decay Rate
    sig = volume_decay_rate(volumes, 5, 20)
    results["H-1048"] = run_signal("H-1048 Volume Decay Rate", sig, closes, 25, param_configs, "high_long")

    # H-1049: Volume Gini
    sig = volume_gini(volumes, 30)
    results["H-1049"] = run_signal("H-1049 Volume Gini", sig, closes, 35, param_configs, "high_long")

    # H-1050: Buy Volume Ratio Trend
    sig = buy_volume_ratio_trend(closes, opens, volumes, 5, 20)
    results["H-1050"] = run_signal("H-1050 Buy Volume Ratio Trend", sig, closes, 25, param_configs, "high_long")

    # H-1051: Volume Momentum Spread
    sig = volume_momentum_spread(volumes, 5, 20, 60)
    results["H-1051"] = run_signal("H-1051 Volume Momentum Spread", sig, closes, 65, param_configs, "high_long")

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
