"""
Batch backtest: H-932 to H-939 — Multi-Timeframe / Consensus XS Signals.

H-932: Multi-TF Momentum Consensus — average z-score of momentum across 7d/14d/30d/60d
H-933: Return Acceleration XS — second derivative of price (momentum change rate)
H-934: Momentum Decay Rate — ratio of short-term to long-term momentum
H-935: Trend Strength Consensus — R² of returns regression + momentum magnitude
H-936: Lookback-Adaptive Momentum — use lookback with highest recent autocorrelation
H-937: Momentum Z-Score — momentum normalized by its own trailing volatility
H-938: Range-Adjusted Momentum — momentum / (high-low range) to normalize by activity
H-939: Volume-Confirmed Trend — momentum * (volume trend indicator)
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

def multi_tf_momentum_consensus(closes, periods=(7, 14, 30, 60)):
    """H-932: Average z-score of momentum across multiple timeframes.
    Assets with consistently positive momentum across all TFs rank highest."""
    z_scores = []
    for p in periods:
        mom = closes.pct_change(p)
        mu = mom.mean(axis=1)
        sigma = mom.std(axis=1).replace(0, np.nan)
        z = mom.sub(mu, axis=0).div(sigma, axis=0)
        z_scores.append(z)
    return sum(z_scores) / len(z_scores)


def return_acceleration(closes, short=7, long=30):
    """H-933: Second derivative of price — momentum of momentum.
    Measures whether momentum is accelerating or decelerating."""
    mom_short = closes.pct_change(short)
    mom_long = closes.pct_change(long)
    # Acceleration = short momentum - (short/long)*long momentum
    # Simplify: rate of change of momentum
    mom_prev = closes.shift(short).pct_change(short)
    return mom_short - mom_prev


def momentum_decay_rate(closes, short=14, long=60):
    """H-934: Ratio of short-term to long-term momentum.
    High ratio = momentum persisting/accelerating. Low = decaying."""
    mom_short = closes.pct_change(short)
    mom_long = closes.pct_change(long)
    # Normalize to avoid scale issues
    abs_long = mom_long.abs().replace(0, np.nan)
    return mom_short / abs_long


def trend_strength_consensus(closes, period=30):
    """H-935: Combine R² of returns regression + normalized momentum.
    High R² + positive momentum = strong, clean trend."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            x = np.arange(period)
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, r)
            r_sq = r_value ** 2
            # Signed R²: positive if slope is positive, else negative
            signed_r2 = r_sq * np.sign(slope)
            signal.iloc[i, signal.columns.get_loc(col)] = signed_r2
    return signal


def lookback_adaptive_momentum(closes, lookbacks=(7, 14, 30, 60)):
    """H-936: Use the lookback period with highest recent autocorrelation.
    Adapts to whether short or long momentum is more persistent."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    ret = closes.pct_change()
    eval_window = 60

    for i in range(max(lookbacks) + eval_window + 5, len(closes)):
        for col in closes.columns:
            best_lb = lookbacks[0]
            best_ac = -2
            for lb in lookbacks:
                mom = closes[col].pct_change(lb)
                m = mom.iloc[i-eval_window:i].values
                if not np.all(np.isfinite(m)):
                    continue
                if len(m) < 10:
                    continue
                ac = np.corrcoef(m[:-1], m[1:])[0, 1]
                if np.isfinite(ac) and ac > best_ac:
                    best_ac = ac
                    best_lb = lb
            signal.iloc[i, signal.columns.get_loc(col)] = closes[col].pct_change(best_lb).iloc[i]
    return signal


def momentum_zscore(closes, mom_period=30, vol_period=60):
    """H-937: Momentum normalized by its own trailing volatility.
    High z-score = momentum is strong relative to historical variation."""
    mom = closes.pct_change(mom_period)
    mom_mean = mom.rolling(vol_period).mean()
    mom_std = mom.rolling(vol_period).std().replace(0, np.nan)
    return (mom - mom_mean) / mom_std


def range_adjusted_momentum(closes, highs, lows, period=20):
    """H-938: Momentum / average daily range. Normalizes by activity level.
    High = large momentum relative to daily volatility."""
    mom = closes.pct_change(period)
    avg_range = ((highs - lows) / closes).rolling(period).mean().replace(0, np.nan)
    return mom / avg_range


def volume_confirmed_trend(closes, volumes, mom_period=20, vol_period=10):
    """H-939: Momentum * volume trend indicator.
    Amplifies momentum when volume is rising, dampens when volume is falling."""
    mom = closes.pct_change(mom_period)
    # Volume trend: ratio of recent vs longer-term volume
    vol_ratio = volumes.rolling(vol_period).mean() / volumes.rolling(mom_period).mean().replace(0, np.nan)
    # Interaction: momentum * (1 + vol_ratio - 1) = momentum * vol_ratio
    return mom * vol_ratio


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

    # H-932: Multi-TF Momentum Consensus
    sig = multi_tf_momentum_consensus(closes)
    results["H-932"] = run_signal("H-932 (Multi-TF Mom Consensus)", sig, closes, 65, configs)

    # H-933: Return Acceleration
    for short in [5, 7, 14]:
        sig = return_acceleration(closes, short=short, long=short*3)
        r = run_signal(f"H-933 (RetAccel S{short})", sig, closes, short*3 + 5, configs)
        if r.get("sharpe", 0) > results.get("H-933", {}).get("sharpe", -99):
            results["H-933"] = r

    # H-934: Momentum Decay Rate
    for short, long in [(7, 30), (14, 60), (7, 60)]:
        sig = momentum_decay_rate(closes, short, long)
        r = run_signal(f"H-934 (MomDecay S{short}L{long})", sig, closes, long + 5, configs)
        if r.get("sharpe", 0) > results.get("H-934", {}).get("sharpe", -99):
            results["H-934"] = r

    # H-935: Trend Strength Consensus (R² signed)
    for period in [14, 20, 30]:
        sig = trend_strength_consensus(closes, period)
        r = run_signal(f"H-935 (TrendStr P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-935", {}).get("sharpe", -99):
            results["H-935"] = r

    # H-936: Lookback-Adaptive Momentum
    sig = lookback_adaptive_momentum(closes)
    results["H-936"] = run_signal("H-936 (AdaptiveMom)", sig, closes, 70, configs)

    # H-937: Momentum Z-Score
    for mp, vp in [(14, 60), (30, 90), (20, 60)]:
        sig = momentum_zscore(closes, mp, vp)
        r = run_signal(f"H-937 (MomZ M{mp}V{vp})", sig, closes, vp + 5, configs)
        if r.get("sharpe", 0) > results.get("H-937", {}).get("sharpe", -99):
            results["H-937"] = r

    # H-938: Range-Adjusted Momentum
    for period in [10, 14, 20, 30]:
        sig = range_adjusted_momentum(closes, highs, lows, period)
        r = run_signal(f"H-938 (RangeAdjMom P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-938", {}).get("sharpe", -99):
            results["H-938"] = r

    # H-939: Volume-Confirmed Trend
    for mp, vp in [(14, 7), (20, 10), (30, 14)]:
        sig = volume_confirmed_trend(closes, volumes, mp, vp)
        r = run_signal(f"H-939 (VolConfTrend M{mp}V{vp})", sig, closes, mp + 5, configs)
        if r.get("sharpe", 0) > results.get("H-939", {}).get("sharpe", -99):
            results["H-939"] = r

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "="*70)
    print("BATCH 1 SUMMARY (H-932 to H-939)")
    print("="*70)
    for hid in ["H-932", "H-933", "H-934", "H-935", "H-936", "H-937", "H-938", "H-939"]:
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
