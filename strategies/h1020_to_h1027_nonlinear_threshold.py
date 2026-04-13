"""
Batch backtest: H-1020 to H-1027 — Non-Linear / Threshold XS Signals.

H-1020: Extreme Return Asymmetry — ratio of positive extreme returns to negative extreme returns
H-1021: Momentum Regime Switch — binary: is current momentum above or below its own median?
H-1022: Volume Acceleration — second derivative of volume (volume momentum of momentum)
H-1023: Relative Return Stability — coefficient of variation of weekly returns (low = stable)
H-1024: Price Gap from Round Numbers — distance from nearest "psychological" level (captures anchoring)
H-1025: Volatility Mean Reversion Speed — how fast does vol return to mean after a spike?
H-1026: Return Autocorrelation XS — rolling 5-day return autocorrelation. High = trending, low = mean-reverting
H-1027: Momentum Reversal Signal — assets that reversed (were down, now up) in last N days
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

def extreme_return_asymmetry(closes, period=30, threshold=1.5):
    """H-1020: Ratio of positive extreme returns (>1.5 sigma) count to negative.
    Assets with more positive extremes = positive skew momentum. Long asymmetric upside."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            rets = returns[col].iloc[i - period:i].dropna().values
            if len(rets) < 15:
                continue
            std = np.std(rets)
            if std == 0:
                continue
            z = rets / std
            pos_extreme = np.sum(z > threshold)
            neg_extreme = np.sum(z < -threshold)
            total_extreme = pos_extreme + neg_extreme
            if total_extreme == 0:
                signal.iloc[i, signal.columns.get_loc(col)] = 0
            else:
                signal.iloc[i, signal.columns.get_loc(col)] = (pos_extreme - neg_extreme) / total_extreme
    return signal


def momentum_regime_switch(closes, short_period=10, long_period=60):
    """H-1021: Is short-term momentum above or below its own long-term median?
    Binary signal: momentum acceleration vs deceleration regime."""
    short_mom = closes.pct_change(short_period)
    long_median = short_mom.rolling(long_period).median()
    return short_mom - long_median


def volume_acceleration(volumes, short_period=5, long_period=20):
    """H-1022: Second derivative of volume — volume momentum of momentum.
    Volume surge acceleration = building institutional interest."""
    vol_mom = volumes.rolling(short_period).mean() / volumes.rolling(long_period).mean()
    vol_mom = vol_mom.replace([np.inf, -np.inf], np.nan)
    # Acceleration = change in volume momentum
    return vol_mom.diff(short_period)


def relative_return_stability(closes, period=30):
    """H-1023: Coefficient of variation of weekly returns.
    Low CV = stable returner (consistent trend). Long stable, short erratic."""
    returns = closes.pct_change(5)  # weekly returns
    mean_ret = returns.rolling(period // 5).mean()
    std_ret = returns.rolling(period // 5).std()
    std_ret = std_ret.replace(0, np.nan)
    cv = std_ret / mean_ret.abs().replace(0, np.nan)
    # Invert: low CV = stable = better
    return -cv


def price_gap_round_numbers(closes):
    """H-1024: Distance from nearest round number level (captures psychological anchoring).
    Assets near round numbers may attract more attention/orders."""
    import math
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(10, len(closes)):
        for col in closes.columns:
            price = closes[col].iloc[i]
            if not np.isfinite(price) or price <= 0:
                continue
            # Find order of magnitude
            magnitude = 10 ** math.floor(math.log10(price))
            # Distance to nearest round number (in units of magnitude)
            nearest_round = round(price / magnitude) * magnitude
            dist = abs(price - nearest_round) / price
            signal.iloc[i, signal.columns.get_loc(col)] = dist
    return signal


def vol_mean_reversion_speed(closes, vol_period=20, lookback=60):
    """H-1025: How fast does realized vol revert to its mean after a spike?
    Measured by negative autocorrelation of vol changes. Fast reverters are more stable."""
    returns = closes.pct_change()
    vol = returns.rolling(vol_period).std()
    vol_change = vol.diff()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(vol_period + lookback + 5, len(closes)):
        for col in closes.columns:
            vc = vol_change[col].iloc[i - lookback:i].dropna().values
            if len(vc) < 20:
                continue
            # Autocorrelation of vol changes — negative = mean reverting
            if len(vc) > 5:
                ac = np.corrcoef(vc[:-1], vc[1:])[0, 1]
                if np.isfinite(ac):
                    signal.iloc[i, signal.columns.get_loc(col)] = -ac  # Higher = faster reversion
    return signal


def return_autocorrelation_xs(closes, period=20):
    """H-1026: Rolling return autocorrelation. High = trending (positive AC), low = mean-reverting.
    Long trending assets, short mean-reverting (in crypto, trending wins)."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            rets = returns[col].iloc[i - period:i].dropna().values
            if len(rets) < 10:
                continue
            ac = np.corrcoef(rets[:-1], rets[1:])[0, 1]
            if np.isfinite(ac):
                signal.iloc[i, signal.columns.get_loc(col)] = ac
    return signal


def momentum_reversal(closes, short_period=5, long_period=30):
    """H-1027: Assets that reversed recently — were down over long period but up over short.
    Long recent reversals (turnaround plays), short continued decliners."""
    short_ret = closes.pct_change(short_period)
    long_ret = closes.pct_change(long_period)
    # Reversal score: positive if short > 0 and long < 0 (turnaround)
    # Or more generally: short_ret - long_ret (outperforming recent vs past)
    return short_ret - long_ret


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

    # H-1020: Extreme Return Asymmetry
    sig = extreme_return_asymmetry(closes, 30, 1.5)
    results["H-1020"] = run_signal("H-1020 Extreme Return Asymmetry", sig, closes, 35, param_configs, "high_long")

    # H-1021: Momentum Regime Switch
    sig = momentum_regime_switch(closes, 10, 60)
    results["H-1021"] = run_signal("H-1021 Momentum Regime Switch", sig, closes, 65, param_configs, "high_long")

    # H-1022: Volume Acceleration
    sig = volume_acceleration(volumes, 5, 20)
    results["H-1022"] = run_signal("H-1022 Volume Acceleration", sig, closes, 25, param_configs, "high_long")

    # H-1023: Relative Return Stability
    sig = relative_return_stability(closes, 30)
    results["H-1023"] = run_signal("H-1023 Return Stability (inv CV)", sig, closes, 35, param_configs, "high_long")

    # H-1024: Price Gap from Round Numbers
    sig = price_gap_round_numbers(closes)
    results["H-1024"] = run_signal("H-1024 Round Number Distance", sig, closes, 15, param_configs, "high_long")

    # H-1025: Vol Mean Reversion Speed
    sig = vol_mean_reversion_speed(closes, 20, 60)
    results["H-1025"] = run_signal("H-1025 Vol Mean Reversion Speed", sig, closes, 65, param_configs, "high_long")

    # H-1026: Return Autocorrelation XS
    sig = return_autocorrelation_xs(closes, 20)
    results["H-1026"] = run_signal("H-1026 Return Autocorrelation XS", sig, closes, 25, param_configs, "high_long")

    # H-1027: Momentum Reversal
    sig = momentum_reversal(closes, 5, 30)
    results["H-1027"] = run_signal("H-1027 Momentum Reversal", sig, closes, 35, param_configs, "high_long")

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
