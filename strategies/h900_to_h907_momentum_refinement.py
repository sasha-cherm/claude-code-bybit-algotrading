"""
Batch backtest: H-900 to H-907 — Cross-Timeframe & Momentum Refinement XS Signals.

H-900: Timeframe Consistency XS — alignment of returns across 3d/7d/14d/30d
H-901: Momentum Acceleration XS — change in momentum strength
H-902: Momentum Quality Score XS — Sharpe-like measure of recent returns
H-903: Return Dispersion Ratio XS — intra-period std / abs(total return)
H-904: Direction Count XS — consecutive positive/negative day streak
H-905: Weighted Return Consistency XS — time-weighted consistency score
H-906: Momentum Gap XS — distance from cross-sectional mean momentum
H-907: Normalized Momentum XS — momentum / volatility (risk-adjusted)
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

def timeframe_consistency_signal(closes):
    """H-900: Timeframe Consistency = sign agreement across 3d/7d/14d/30d returns.
    Score = sum of signs. +4 = all up across timeframes, -4 = all down.
    High consistency = strong trend across all horizons."""
    r3 = closes.pct_change(3)
    r7 = closes.pct_change(7)
    r14 = closes.pct_change(14)
    r30 = closes.pct_change(30)
    return np.sign(r3) + np.sign(r7) + np.sign(r14) + np.sign(r30)


def momentum_acceleration_signal(closes, short=14, long=60):
    """H-901: Momentum Acceleration = short-term momentum - long-term momentum.
    Positive = momentum increasing. Captures acceleration of winners."""
    mom_short = closes.pct_change(short)
    mom_long = closes.pct_change(long)
    return mom_short - mom_long / (long / short)


def momentum_quality_signal(closes, period=30):
    """H-902: Momentum Quality = mean(daily return) / std(daily return) over period.
    Sharpe-like measure. High quality = consistent positive returns, not just large total."""
    ret = closes.pct_change()
    mean_r = ret.rolling(period).mean()
    std_r = ret.rolling(period).std().replace(0, np.nan)
    return mean_r / std_r


def return_dispersion_signal(closes, period=20):
    """H-903: Return Dispersion = std(daily returns) / abs(total period return + epsilon).
    Low dispersion = smooth directional move. High = choppy (lots of reversals)."""
    ret = closes.pct_change()
    std_r = ret.rolling(period).std()
    total_r = closes.pct_change(period).abs().replace(0, 1e-10)
    # Invert: low dispersion = smooth trend = good
    return -std_r / total_r


def direction_count_signal(closes, period=10):
    """H-904: Direction Count = net count of up days minus down days.
    Positive = more up days. Captures short-term directional persistence."""
    ret = closes.pct_change()
    up = (ret > 0).astype(float)
    down = (ret < 0).astype(float)
    net = up.rolling(period).sum() - down.rolling(period).sum()
    return net


def weighted_return_consistency_signal(closes, period=20):
    """H-905: Weighted Return Consistency = sum of returns weighted by recency.
    More recent days weighted more. Captures trending with emphasis on latest data."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    weights = np.linspace(1, 2, period)  # Recent days weighted 2x
    weights = weights / weights.sum()
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i - period:i].values
            if np.all(np.isfinite(r)):
                signal.iloc[i, signal.columns.get_loc(col)] = np.sum(r * weights)
    return signal


def momentum_gap_signal(closes, period=30):
    """H-906: Momentum Gap = asset momentum - cross-sectional mean momentum.
    Large positive gap = extreme outperformer relative to the pack.
    Could capture momentum breakaways or crowded positions."""
    mom = closes.pct_change(period)
    xs_mean = mom.mean(axis=1)
    return mom.sub(xs_mean, axis=0)


def normalized_momentum_signal(closes, period=30, vol_window=20):
    """H-907: Normalized Momentum = momentum / volatility. Risk-adjusted XS momentum.
    High norm_mom = strong return per unit risk. Filters out high-vol noise."""
    mom = closes.pct_change(period)
    vol = closes.pct_change().rolling(vol_window).std().replace(0, np.nan)
    return mom / vol


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

    # H-900: Timeframe Consistency
    sig = timeframe_consistency_signal(closes)
    r = run_signal("H-900 (TF Consistency)", sig, closes, 35, configs)
    results["H-900"] = r

    # H-901: Momentum Acceleration
    for short, long in [(7, 30), (14, 60), (10, 45)]:
        sig = momentum_acceleration_signal(closes, short, long)
        r = run_signal(f"H-901 (MomAccel {short}/{long})", sig, closes, long + 5, configs)
        if r.get("sharpe", 0) > results.get("H-901", {}).get("sharpe", -99):
            results["H-901"] = r

    # H-902: Momentum Quality
    for period in [14, 20, 30, 45]:
        sig = momentum_quality_signal(closes, period)
        r = run_signal(f"H-902 (MomQual P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-902", {}).get("sharpe", -99):
            results["H-902"] = r

    # H-903: Return Dispersion
    for period in [10, 20, 30]:
        sig = return_dispersion_signal(closes, period)
        r = run_signal(f"H-903 (RetDisp P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-903", {}).get("sharpe", -99):
            results["H-903"] = r

    # H-904: Direction Count
    for period in [5, 10, 14]:
        sig = direction_count_signal(closes, period)
        r = run_signal(f"H-904 (DirCount P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-904", {}).get("sharpe", -99):
            results["H-904"] = r

    # H-905: Weighted Return Consistency
    for period in [14, 20, 30]:
        sig = weighted_return_consistency_signal(closes, period)
        r = run_signal(f"H-905 (WtRetCons P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-905", {}).get("sharpe", -99):
            results["H-905"] = r

    # H-906: Momentum Gap
    for period in [14, 30, 60]:
        sig = momentum_gap_signal(closes, period)
        r = run_signal(f"H-906 (MomGap P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-906", {}).get("sharpe", -99):
            results["H-906"] = r

    # H-907: Normalized Momentum
    for period, vol_w in [(14, 14), (30, 20), (60, 30)]:
        sig = normalized_momentum_signal(closes, period, vol_w)
        r = run_signal(f"H-907 (NormMom {period}/{vol_w})", sig, closes, period + vol_w + 5, configs)
        if r.get("sharpe", 0) > results.get("H-907", {}).get("sharpe", -99):
            results["H-907"] = r

    # Summary
    print("\n" + "=" * 60)
    print("BATCH SUMMARY: H-900 to H-907 (Momentum Refinements)")
    print("=" * 60)
    for hid, r in sorted(results.items()):
        status = r.get("status", "CANDIDATE")
        if status == "REJECTED_IS":
            print(f"  {hid}: REJECTED (IS {r['pos_pct']:.0f}% pos, Sharpe {r['sharpe']:.3f})")
        else:
            wf_pos = sum(1 for w in r["wf"] if w > 0)
            wf_tot = len(r["wf"])
            print(f"  {hid}: Sharpe {r['sharpe']:.3f}, WF {wf_pos}/{wf_tot}, "
                  f"SH p={r['sh'][2]:.4f}, corr {r['corr']}, params {r['params']}")


if __name__ == "__main__":
    run_batch()
