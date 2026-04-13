"""
Batch backtest: H-948 to H-955 — Information / Efficiency XS Signals.

H-948: Price Discovery Speed — first-order autocorrelation (slow discovery = predictable)
H-949: Noise Ratio — variance ratio at different frequencies (random walk deviation)
H-950: Signal-to-Noise Ratio — trend component / noise component of returns
H-951: Information Share — explained variance by market factor (R²) as XS signal
H-952: Price Efficiency Index — abs(close-to-close return) / (high-low range)
H-953: Intrabar Reversal — (close-open)/(high-low) as rejection wick signal
H-954: Drift-to-Volatility — abs(mean return) / std(returns) (directional strength)
H-955: Momentum Predictability — autocorrelation of momentum rankings
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

def price_discovery_speed(closes, period=30):
    """H-948: First-order return autocorrelation over rolling window.
    Negative autocorrelation = fast price discovery (overreaction-correction).
    Positive = slow discovery (trending). Long slow discovery (momentum-like)."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            if len(r) < 10:
                continue
            ac = np.corrcoef(r[:-1], r[1:])[0, 1]
            if np.isfinite(ac):
                signal.iloc[i, signal.columns.get_loc(col)] = ac
    return signal


def noise_ratio(closes, short_period=5, long_period=30):
    """H-949: Variance ratio = var(long-period returns) / (long/short * var(short returns)).
    VR > 1 = trending. VR < 1 = mean-reverting. Rank by VR (long trending assets)."""
    ret = closes.pct_change()
    long_ret = closes.pct_change(long_period)
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    ratio = long_period // short_period
    for i in range(long_period + 30, len(closes)):
        for col in closes.columns:
            lr = long_ret[col].iloc[i-30:i].values
            sr = ret[col].iloc[i-30:i].values
            if not (np.all(np.isfinite(lr)) and np.all(np.isfinite(sr))):
                continue
            var_long = np.var(lr)
            var_short = np.var(sr)
            if var_short < 1e-12:
                continue
            vr = var_long / (ratio * var_short)
            if np.isfinite(vr):
                signal.iloc[i, signal.columns.get_loc(col)] = vr
    return signal


def signal_to_noise_ratio(closes, period=30):
    """H-950: |Trend component| / noise component.
    Trend = linear regression slope * period. Noise = residual std.
    High S/N = clean directional moves. Long high S/N."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            x = np.arange(period)
            slope, intercept, _, _, _ = stats.linregress(x, r)
            predicted = slope * x + intercept
            residuals = r - predicted
            noise = np.std(residuals)
            if noise < 1e-8:
                continue
            trend_mag = abs(slope) * period
            # Sign by direction
            snr = trend_mag / noise * np.sign(slope)
            signal.iloc[i, signal.columns.get_loc(col)] = snr
    return signal


def information_share(closes, period=60):
    """H-951: R² of asset vs BTC (market factor).
    Low R² = more idiosyncratic. High R² = pure beta.
    Long low R² (more alpha potential), short high R² (pure beta)."""
    ret = closes.pct_change()
    btc_col = [c for c in closes.columns if "BTC" in c]
    if not btc_col:
        return pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    btc_ret = ret[btc_col[0]]
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        br = btc_ret.iloc[i-period:i].values
        if not np.all(np.isfinite(br)):
            continue
        for col in closes.columns:
            if col == btc_col[0]:
                continue
            ar = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(ar)):
                continue
            corr = np.corrcoef(ar, br)[0, 1]
            if np.isfinite(corr):
                signal.iloc[i, signal.columns.get_loc(col)] = -(corr ** 2)  # negative: low R² = long
    return signal


def price_efficiency_index(closes, highs, lows, period=20):
    """H-952: abs(close-to-close return) / mean(high-low range).
    Efficient = price moves are captured in close-to-close. Inefficient = lots of intraday noise.
    Long efficient (clean moves), short inefficient."""
    abs_ret = closes.pct_change().abs()
    daily_range = (highs - lows) / closes
    # Rolling ratio
    avg_ret = abs_ret.rolling(period).mean()
    avg_range = daily_range.rolling(period).mean().replace(0, np.nan)
    return avg_ret / avg_range


def intrabar_reversal(closes, opens, highs, lows, period=20):
    """H-953: Rolling mean of (close-open)/(high-low).
    Positive = closes near high (bullish bars). Negative = closes near low (bearish bars).
    Captures bar quality / conviction."""
    rng = (highs - lows).replace(0, np.nan)
    bar_quality = (closes - opens) / rng
    return bar_quality.rolling(period).mean()


def drift_to_volatility(closes, period=30):
    """H-954: abs(mean daily return) / std(daily returns).
    High = strong directional drift relative to noise. Captures momentum quality."""
    ret = closes.pct_change()
    mean_ret = ret.rolling(period).mean()
    std_ret = ret.rolling(period).std().replace(0, np.nan)
    # Signed by direction
    return mean_ret / std_ret


def momentum_predictability(closes, period=30, rank_period=20):
    """H-955: Autocorrelation of cross-sectional momentum rankings.
    If rankings are persistent, momentum is more predictable.
    Rank by how stable each asset's rank has been."""
    ret = closes.pct_change(period)
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + rank_period + 5, len(closes)):
        ranks = []
        for j in range(rank_period):
            row = ret.iloc[i - j]
            valid = row.dropna()
            if len(valid) < 8:
                break
            r = valid.rank()
            ranks.append(r)
        if len(ranks) < rank_period:
            continue
        # For each asset, compute variance of its rank over the window
        for col in closes.columns:
            rank_series = [r.get(col, np.nan) for r in ranks]
            rank_series = [x for x in rank_series if np.isfinite(x)]
            if len(rank_series) < rank_period // 2:
                continue
            # Low rank variance = stable ranking (predictable)
            rank_var = np.var(rank_series)
            # Also get current momentum for direction
            current_mom = ret[col].iloc[i]
            if not np.isfinite(current_mom):
                continue
            # Signal: momentum * (1 / rank_variance) — amplify momentum for stable assets
            if rank_var < 0.1:
                rank_var = 0.1
            signal.iloc[i, signal.columns.get_loc(col)] = current_mom / np.sqrt(rank_var)
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
    closes, highs, lows, opens, volumes = load_data()
    print(f"Data: {len(closes)} days, {len(closes.columns)} assets, "
          f"{closes.index[0].date()} to {closes.index[-1].date()}")

    configs = [(r, n) for r in [3, 5, 7] for n in [3, 4]]
    results = {}

    # H-948: Price Discovery Speed (autocorrelation)
    for period in [14, 20, 30, 60]:
        sig = price_discovery_speed(closes, period)
        r = run_signal(f"H-948 (PriceDisc P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-948", {}).get("sharpe", -99):
            results["H-948"] = r

    # H-949: Noise Ratio (variance ratio)
    for short_p, long_p in [(1, 5), (1, 10), (5, 30)]:
        sig = noise_ratio(closes, short_p, long_p)
        r = run_signal(f"H-949 (NoiseRatio S{short_p}L{long_p})", sig, closes, long_p + 35, configs)
        if r.get("sharpe", 0) > results.get("H-949", {}).get("sharpe", -99):
            results["H-949"] = r

    # H-950: Signal-to-Noise Ratio
    for period in [14, 20, 30]:
        sig = signal_to_noise_ratio(closes, period)
        r = run_signal(f"H-950 (SNR P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-950", {}).get("sharpe", -99):
            results["H-950"] = r

    # H-951: Information Share (R² vs BTC)
    for period in [30, 60, 90]:
        sig = information_share(closes, period)
        r = run_signal(f"H-951 (InfoShare P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-951", {}).get("sharpe", -99):
            results["H-951"] = r

    # H-952: Price Efficiency Index
    for period in [10, 14, 20, 30]:
        sig = price_efficiency_index(closes, highs, lows, period)
        r = run_signal(f"H-952 (PriceEff P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-952", {}).get("sharpe", -99):
            results["H-952"] = r

    # H-953: Intrabar Reversal
    for period in [10, 14, 20, 30]:
        sig = intrabar_reversal(closes, opens, highs, lows, period)
        r = run_signal(f"H-953 (IntrabarRev P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-953", {}).get("sharpe", -99):
            results["H-953"] = r

    # H-954: Drift-to-Volatility
    for period in [14, 20, 30, 60]:
        sig = drift_to_volatility(closes, period)
        r = run_signal(f"H-954 (DriftVol P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-954", {}).get("sharpe", -99):
            results["H-954"] = r

    # H-955: Momentum Predictability
    for mp, rp in [(14, 14), (30, 20), (60, 20)]:
        sig = momentum_predictability(closes, mp, rp)
        r = run_signal(f"H-955 (MomPredict M{mp}R{rp})", sig, closes, mp + rp + 5, configs)
        if r.get("sharpe", 0) > results.get("H-955", {}).get("sharpe", -99):
            results["H-955"] = r

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "="*70)
    print("BATCH 3 SUMMARY (H-948 to H-955)")
    print("="*70)
    for hid in ["H-948", "H-949", "H-950", "H-951", "H-952", "H-953", "H-954", "H-955"]:
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
