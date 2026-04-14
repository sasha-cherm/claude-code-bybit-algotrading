"""
Batch backtest: H-1060 to H-1067 — Open Interest Structure XS Signals.

H-1060: OI Velocity — rate of change of OI (positioning momentum)
H-1061: OI-Price Divergence Speed — divergence rate between OI change and price change
H-1062: OI Concentration Change — change in how concentrated OI is across assets
H-1063: OI Momentum — cumulative OI change (trend in positioning)
H-1064: OI-Volume Ratio — OI normalized by volume (leverage intensity)
H-1065: OI Rank Stability — how stable is OI ranking? (persistent vs transient)
H-1066: OI Surge Detection — sudden OI spikes relative to baseline
H-1067: OI Mean Reversion — extreme OI levels predict reversal
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
    closes, volumes = {}, {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_1d.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            closes[f"{ticker}/USDT"] = df["close"]
            volumes[f"{ticker}/USDT"] = df["volume"] * df["close"]
        except:
            pass
    closes = pd.DataFrame(closes).sort_index().dropna(how="all")
    volumes = pd.DataFrame(volumes).sort_index().dropna(how="all")
    return closes, volumes


def load_oi():
    oi = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_oi_daily.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            oi[f"{ticker}/USDT"] = df["openInterest"]
        except:
            pass
    return pd.DataFrame(oi).sort_index().dropna(how="all")


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

def oi_velocity(oi, short=5, long=20):
    """H-1060: Rate of change of OI — short-term OI change vs long-term.
    Rising OI = growing positioning (momentum), falling = delevering."""
    short_chg = oi.pct_change(short)
    long_chg = oi.pct_change(long)
    return short_chg - long_chg


def oi_price_divergence(oi, closes, period=14):
    """H-1061: OI change - price change divergence.
    OI rising while price falling = shorts building (bearish OI).
    OI falling while price rising = short covering (bullish momentum)."""
    common_cols = [c for c in oi.columns if c in closes.columns]
    if not common_cols:
        return pd.DataFrame()
    oi_chg = oi[common_cols].pct_change(period).rank(axis=1, pct=True)
    price_chg = closes[common_cols].pct_change(period).rank(axis=1, pct=True)
    common_idx = oi_chg.index.intersection(price_chg.index)
    return price_chg.loc[common_idx] - oi_chg.loc[common_idx]


def oi_concentration_change(oi, period=14):
    """H-1062: Change in OI Herfindahl index across assets.
    Increasing concentration = flow into fewer assets → momentum.
    We compute per-asset's share of total OI and its change."""
    total_oi = oi.sum(axis=1)
    shares = oi.div(total_oi, axis=0)
    share_chg = shares.diff(period)
    return share_chg


def oi_momentum(oi, period=20):
    """H-1063: Cumulative OI change as pct. More OI growth → more conviction."""
    return oi.pct_change(period)


def oi_volume_ratio(oi, volumes, period=14):
    """H-1064: OI / Volume ratio — leverage intensity.
    High ratio = lots of open positions relative to daily volume = crowded."""
    common_cols = [c for c in oi.columns if c in volumes.columns]
    if not common_cols:
        return pd.DataFrame()
    oi_avg = oi[common_cols].rolling(period).mean()
    vol_avg = volumes[common_cols].rolling(period).mean()
    vol_avg = vol_avg.replace(0, np.nan)
    common_idx = oi_avg.index.intersection(vol_avg.index)
    return oi_avg.loc[common_idx] / vol_avg.loc[common_idx]


def oi_rank_stability(oi, short=7, long=30):
    """H-1065: Correlation between short-term and long-term OI rankings.
    Stable ranking = persistent positioning, unstable = regime change."""
    short_rank = oi.rolling(short).mean().rank(axis=1, pct=True)
    long_rank = oi.rolling(long).mean().rank(axis=1, pct=True)
    return short_rank - long_rank


def oi_surge(oi, short=3, long=20, threshold=1.5):
    """H-1066: OI surge detection — short-term OI jump vs baseline.
    Sudden OI surge = new position building (institutional entry)."""
    short_avg = oi.rolling(short).mean()
    long_avg = oi.rolling(long).mean()
    long_avg = long_avg.replace(0, np.nan)
    ratio = short_avg / long_avg
    return ratio


def oi_mean_reversion(oi, short=5, long=30):
    """H-1067: Z-score of OI from rolling mean.
    Extreme high OI → overleveraged, expect correction (contrarian short).
    Extreme low OI → capitulation, expect bounce (contrarian long)."""
    rolling_mean = oi.rolling(long).mean()
    rolling_std = oi.rolling(long).std()
    rolling_std = rolling_std.replace(0, np.nan)
    zscore = (oi.rolling(short).mean() - rolling_mean) / rolling_std
    return -zscore


def run_signal(name, signal_df, closes, lookback, directions, n_ls_list=[4],
               rebal_list=[5, 7]):
    best = {"sharpe": -999}
    for direction in directions:
        for n_ls in n_ls_list:
            for rebal in rebal_list:
                pnl = xs_backtest(closes, signal_df, lookback, rebal, n_ls, direction)
                m = compute_metrics(pnl)
                if m["sharpe"] > best.get("sharpe", -999):
                    best = {**m, "direction": direction, "n_ls": n_ls, "rebal": rebal,
                            "pnl": pnl}
    if best["sharpe"] <= 0:
        print(f"  {name}: IS Sharpe {best.get('sharpe', 0):.3f} — SKIP (no positive)")
        return None
    pnl = best["pnl"]
    wf = walk_forward(closes, signal_df, lookback, best["rebal"], best["n_ls"],
                      best["direction"])
    sh1, sh2, p_val = split_half_test(pnl)
    corr = h012_correlation(closes, signal_df, lookback, best["rebal"], best["n_ls"],
                            best["direction"])
    wf_pos = sum(1 for x in wf if x > 0)
    print(f"  {name}: IS Sharpe {best['sharpe']:.3f} | Ann {best['annual_ret']:.1f}% | DD {best['max_dd']:.1f}% | "
          f"Dir={best['direction']} | WF {wf_pos}/{len(wf)} {wf} | SH {sh1:.3f}/{sh2:.3f} p={p_val:.3f} | "
          f"H012 corr {corr:.3f} | N={len(pnl)}")
    return {
        "sharpe": best["sharpe"], "annual_ret": best["annual_ret"],
        "max_dd": best["max_dd"], "direction": best["direction"],
        "n_ls": best["n_ls"], "rebal": best["rebal"],
        "wf": wf, "wf_pos": wf_pos, "wf_total": len(wf),
        "sh1": sh1, "sh2": sh2, "p_val": round(p_val, 4),
        "h012_corr": corr, "n_bars": len(pnl)
    }


def main():
    print("Loading data...")
    closes, volumes = load_data()
    oi = load_oi()

    common_idx = closes.index.intersection(oi.index)
    common_cols = [c for c in closes.columns if c in oi.columns]
    closes_o = closes[common_cols].loc[common_idx]
    oi_o = oi[common_cols].loc[common_idx]
    volumes_o = volumes[[c for c in common_cols if c in volumes.columns]].loc[
        common_idx.intersection(volumes.index)]

    print(f"Closes: {closes.shape}, OI: {oi.shape}, Common: {closes_o.shape}")
    print()

    results = {}

    # H-1060: OI Velocity
    print("H-1060: OI Velocity")
    sig = oi_velocity(oi_o)
    r = run_signal("H-1060", sig, closes_o, 20, ["high_long", "low_long"])
    if r: results["H-1060"] = r

    # H-1061: OI-Price Divergence
    print("H-1061: OI-Price Divergence Speed")
    sig = oi_price_divergence(oi_o, closes_o)
    if len(sig) > 0:
        r = run_signal("H-1061", sig, closes_o, 14, ["high_long", "low_long"])
        if r: results["H-1061"] = r
    else:
        print("  H-1061: No data — SKIP")

    # H-1062: OI Concentration Change
    print("H-1062: OI Concentration Change")
    sig = oi_concentration_change(oi_o)
    r = run_signal("H-1062", sig, closes_o, 14, ["high_long", "low_long"])
    if r: results["H-1062"] = r

    # H-1063: OI Momentum
    print("H-1063: OI Momentum")
    sig = oi_momentum(oi_o)
    r = run_signal("H-1063", sig, closes_o, 20, ["high_long", "low_long"])
    if r: results["H-1063"] = r

    # H-1064: OI-Volume Ratio
    print("H-1064: OI-Volume Ratio")
    sig = oi_volume_ratio(oi_o, volumes_o)
    if len(sig) > 0:
        common_idx3 = closes_o.index.intersection(sig.index)
        common_cols3 = [c for c in closes_o.columns if c in sig.columns]
        r = run_signal("H-1064", sig[common_cols3].loc[common_idx3],
                        closes_o[common_cols3].loc[common_idx3], 14,
                        ["high_long", "low_long"])
        if r: results["H-1064"] = r
    else:
        print("  H-1064: No data — SKIP")

    # H-1065: OI Rank Stability
    print("H-1065: OI Rank Stability")
    sig = oi_rank_stability(oi_o)
    r = run_signal("H-1065", sig, closes_o, 30, ["high_long", "low_long"])
    if r: results["H-1065"] = r

    # H-1066: OI Surge
    print("H-1066: OI Surge Detection")
    sig = oi_surge(oi_o)
    r = run_signal("H-1066", sig, closes_o, 20, ["high_long", "low_long"])
    if r: results["H-1066"] = r

    # H-1067: OI Mean Reversion
    print("H-1067: OI Mean Reversion")
    sig = oi_mean_reversion(oi_o)
    r = run_signal("H-1067", sig, closes_o, 30, ["high_long", "low_long"])
    if r: results["H-1067"] = r

    print(f"\n{'='*80}")
    print(f"BATCH SUMMARY: {len(results)}/{8} signals with positive IS Sharpe")
    for name, r in sorted(results.items(), key=lambda x: -x[1]["sharpe"]):
        status = "CONFIRMED" if r["wf_pos"] >= max(2, r["wf_total"] * 0.5) and r["p_val"] < 0.1 else "BORDERLINE" if r["wf_pos"] >= 2 else "REJECTED"
        print(f"  {name}: Sharpe {r['sharpe']:.3f} | WF {r['wf_pos']}/{r['wf_total']} | p={r['p_val']:.3f} | corr {r['h012_corr']:.3f} | {status}")


if __name__ == "__main__":
    main()
