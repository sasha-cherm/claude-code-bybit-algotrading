"""
Batch backtest: H-964 to H-971 — Conditional / Structural Momentum XS Signals.

H-964: Momentum Conviction — momentum penalized by path roughness (DD/abs_return)
H-965: Relative Drawdown Depth — current_dd / max_historic_dd — shallow = recovery potential
H-966: Price Level Factor — log(close) — test if nominal price predicts XS returns
H-967: Funding × Momentum — funding_rate * momentum direction — aligned signals
H-968: Volume Spike Recency — days since most recent volume spike (>2 std)
H-969: Post-Spike Return — cumulative return after highest-volume day in lookback
H-970: Higher Lows Count — count of days where low > prior low — trend structure quality
H-971: Overnight Gap Trend — slope of overnight gaps (open_t - close_{t-1})
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


def load_funding():
    """Load funding rate data for supported assets."""
    funding = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_funding.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            # Resample to daily (sum of 3 funding settlements)
            daily_fr = df["fundingRate"].resample("1D").sum()
            funding[f"{ticker}/USDT"] = daily_fr
        except:
            pass
    if funding:
        return pd.DataFrame(funding).sort_index().dropna(how="all")
    return None


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

def momentum_conviction(closes, mom_period=30, dd_period=30):
    """H-964: Momentum * (1 - max_dd/abs_return). Penalizes rough momentum paths."""
    ret = closes.pct_change()
    cum_ret = ret.rolling(mom_period).sum()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(max(mom_period, dd_period) + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-dd_period:i].values
            if not np.all(np.isfinite(r)):
                continue
            cr = cum_ret[col].iloc[i]
            if not np.isfinite(cr) or abs(cr) < 1e-10:
                continue
            # Max drawdown over the period
            cum = np.cumsum(r)
            peak = np.maximum.accumulate(cum)
            dd = cum - peak
            max_dd = abs(np.min(dd)) if len(dd) > 0 else 0
            # Conviction: momentum * (1 - roughness)
            roughness = max_dd / (abs(cr) + 1e-10)
            roughness = min(roughness, 2.0)  # cap
            conviction = cr * max(0, 1 - roughness)
            signal.iloc[i, signal.columns.get_loc(col)] = conviction
    return signal


def relative_drawdown_depth(closes, period=60):
    """H-965: current_dd / max_historic_dd. Shallow DD relative to history = recovery potential.
    Long assets with shallow relative DD (near 0), short deep relative DD (near 1)."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 30, len(closes)):
        for col in closes.columns:
            prices = closes[col].iloc[:i+1].values
            if not np.all(np.isfinite(prices[-period:])):
                continue
            # Current DD
            peak = np.max(prices[-period:])
            current_dd = (peak - prices[-1]) / peak if peak > 0 else 0
            # Historic max DD
            all_peak = np.maximum.accumulate(prices)
            all_dd = (all_peak - prices) / np.where(all_peak > 0, all_peak, 1)
            max_hist_dd = np.max(all_dd)
            if max_hist_dd < 0.01:
                continue
            ratio = current_dd / max_hist_dd
            signal.iloc[i, signal.columns.get_loc(col)] = -ratio  # negative: shallow = long
    return signal


def price_level_factor(closes):
    """H-966: log(close). Test if high-price vs low-price assets have systematic XS return differences."""
    return np.log(closes)


def funding_momentum_interaction(closes, funding_df, mom_period=30, fund_period=14):
    """H-967: funding_rate_avg * sign(momentum). Aligned funding and momentum."""
    if funding_df is None:
        return pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    ret = closes.pct_change()
    mom = ret.rolling(mom_period).sum()
    # Align funding to close index
    fund_aligned = funding_df.reindex(closes.index, method="ffill")
    fund_avg = fund_aligned.rolling(fund_period).mean()
    # Only use columns present in both
    common = [c for c in closes.columns if c in fund_avg.columns]
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for col in common:
        s = fund_avg[col] * np.sign(mom[col])
        signal[col] = s
    return signal


def volume_spike_recency(volumes, period=30, spike_threshold=2.0):
    """H-968: Days since most recent volume spike (>2 std above mean).
    Recent spike = attention/catalyst. Long recent spike, short no recent spike."""
    signal = pd.DataFrame(np.nan, index=volumes.index, columns=volumes.columns)
    for i in range(period + 5, len(volumes)):
        for col in volumes.columns:
            v = volumes[col].iloc[i-period:i].values
            if not np.all(np.isfinite(v)):
                continue
            mean_v = np.mean(v)
            std_v = np.std(v)
            if std_v < 1e-10:
                continue
            threshold = mean_v + spike_threshold * std_v
            # Find days since last spike
            spike_days = np.where(v > threshold)[0]
            if len(spike_days) > 0:
                days_since = period - 1 - spike_days[-1]
            else:
                days_since = period
            signal.iloc[i, signal.columns.get_loc(col)] = -days_since  # negative: recent spike = long
    return signal


def post_spike_return(closes, volumes, period=30, spike_threshold=2.0):
    """H-969: Cumulative return after the highest-volume day in lookback window.
    Positive post-spike return = momentum continuation after catalyst."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            if col not in volumes.columns:
                continue
            v = volumes[col].iloc[i-period:i].values
            r = ret[col].iloc[i-period:i].values
            if not (np.all(np.isfinite(v)) and np.all(np.isfinite(r))):
                continue
            # Find highest volume day
            max_vol_idx = np.argmax(v)
            # Return after that day
            if max_vol_idx < period - 1:
                post_ret = np.sum(r[max_vol_idx+1:])
                signal.iloc[i, signal.columns.get_loc(col)] = post_ret
    return signal


def higher_lows_count(lows, period=20):
    """H-970: Count of days where low > prior day's low. More higher lows = stronger uptrend structure."""
    signal = pd.DataFrame(np.nan, index=lows.index, columns=lows.columns)
    for i in range(period + 5, len(lows)):
        for col in lows.columns:
            lo = lows[col].iloc[i-period:i].values
            if not np.all(np.isfinite(lo)):
                continue
            count = np.sum(lo[1:] > lo[:-1])
            signal.iloc[i, signal.columns.get_loc(col)] = count
    return signal


def overnight_gap_trend(closes, opens, period=20):
    """H-971: Slope of overnight gaps (open_t - close_{t-1}) / close_{t-1}.
    Positive gap trend = increasing overnight buying pressure."""
    gaps = (opens - closes.shift(1)) / closes.shift(1)
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            g = gaps[col].iloc[i-period:i].values
            if not np.all(np.isfinite(g)):
                continue
            x = np.arange(period)
            slope, _, _, _, _ = stats.linregress(x, g)
            if np.isfinite(slope):
                signal.iloc[i, signal.columns.get_loc(col)] = slope
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
    funding_df = load_funding()
    print(f"Data: {len(closes)} days, {len(closes.columns)} assets, "
          f"{closes.index[0].date()} to {closes.index[-1].date()}")
    if funding_df is not None:
        print(f"Funding: {len(funding_df)} days, {len(funding_df.columns)} assets")

    configs = [(r, n) for r in [3, 5, 7] for n in [3, 4]]
    results = {}

    # H-964: Momentum Conviction
    for mp, dp in [(14, 14), (30, 30), (60, 60)]:
        sig = momentum_conviction(closes, mp, dp)
        r = run_signal(f"H-964 (MomConvict M{mp}D{dp})", sig, closes, max(mp, dp) + 5, configs)
        if r.get("sharpe", 0) > results.get("H-964", {}).get("sharpe", -99):
            results["H-964"] = r

    # H-965: Relative Drawdown Depth
    for period in [30, 60, 90]:
        sig = relative_drawdown_depth(closes, period)
        r = run_signal(f"H-965 (RelDD P{period})", sig, closes, period + 30, configs)
        if r.get("sharpe", 0) > results.get("H-965", {}).get("sharpe", -99):
            results["H-965"] = r

    # H-966: Price Level Factor
    sig = price_level_factor(closes)
    r = run_signal("H-966 (PriceLevel)", sig, closes, 5, configs)
    results["H-966"] = r
    # Also test reverse direction
    r2 = run_signal("H-966 (PriceLevel Low)", sig, closes, 5, configs, direction="low_long")
    if r2.get("sharpe", 0) > results.get("H-966", {}).get("sharpe", -99):
        results["H-966"] = r2

    # H-967: Funding × Momentum
    for mp, fp in [(14, 7), (30, 14), (60, 30)]:
        sig = funding_momentum_interaction(closes, funding_df, mp, fp)
        r = run_signal(f"H-967 (FundMom M{mp}F{fp})", sig, closes, max(mp, fp) + 5, configs)
        if r.get("sharpe", 0) > results.get("H-967", {}).get("sharpe", -99):
            results["H-967"] = r

    # H-968: Volume Spike Recency
    for period in [14, 20, 30]:
        sig = volume_spike_recency(volumes, period)
        r = run_signal(f"H-968 (VolSpike P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-968", {}).get("sharpe", -99):
            results["H-968"] = r

    # H-969: Post-Spike Return
    for period in [14, 20, 30]:
        sig = post_spike_return(closes, volumes, period)
        r = run_signal(f"H-969 (PostSpike P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-969", {}).get("sharpe", -99):
            results["H-969"] = r

    # H-970: Higher Lows Count
    for period in [10, 14, 20, 30]:
        sig = higher_lows_count(lows, period)
        r = run_signal(f"H-970 (HigherLows P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-970", {}).get("sharpe", -99):
            results["H-970"] = r

    # H-971: Overnight Gap Trend
    for period in [10, 14, 20, 30]:
        sig = overnight_gap_trend(closes, opens, period)
        r = run_signal(f"H-971 (OvernGap P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-971", {}).get("sharpe", -99):
            results["H-971"] = r

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "="*70)
    print("BATCH 2 SUMMARY (H-964 to H-971 — Conditional / Structural)")
    print("="*70)
    for hid in ["H-964", "H-965", "H-966", "H-967", "H-968", "H-969", "H-970", "H-971"]:
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
    run_batch()
