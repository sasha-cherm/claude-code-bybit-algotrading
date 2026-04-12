"""
Batch backtest: H-892 to H-899 — Volume Dynamics XS Signals.

H-892: Volume Acceleration XS — second derivative of volume
H-893: Volume Volatility XS — std of volume changes
H-894: Volume-Price Correlation XS — rolling corr between returns and volume
H-895: Dollar Volume Rank Change XS — drift in volume ranking
H-896: Relative Volume XS — current vs historical average volume
H-897: Volume Concentration XS — Herfindahl index of daily volume
H-898: Cumulative Volume Divergence XS — cum vol diff from moving average
H-899: Volume Trend Persistence XS — consecutive days above/below avg volume
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

def volume_acceleration_signal(volumes, short=5, long=20):
    """H-892: Volume Acceleration = change in volume momentum.
    vol_mom = vol_sma(short) / vol_sma(long). Acceleration = change in vol_mom.
    High accel = volume surge accelerating = buying pressure building."""
    vol_mom = volumes.rolling(short).mean() / volumes.rolling(long).mean().replace(0, np.nan)
    return vol_mom.diff(short)


def volume_volatility_signal(volumes, period=20):
    """H-893: Volume Volatility = coefficient of variation of volume.
    High vol-vol = unstable activity patterns. Low = stable/institutional."""
    vol_cv = volumes.rolling(period).std() / volumes.rolling(period).mean().replace(0, np.nan)
    return vol_cv


def vol_price_corr_signal(closes, volumes, period=20):
    """H-894: Volume-Price Correlation = rolling correlation between returns and volume.
    Positive = volume confirms price moves. Negative = divergence."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i - period:i].values
            v = volumes[col].iloc[i - period:i].values
            if np.all(np.isfinite(r)) and np.all(np.isfinite(v)) and np.std(r) > 0 and np.std(v) > 0:
                signal.iloc[i, signal.columns.get_loc(col)] = np.corrcoef(r, v)[0, 1]
    return signal


def dvol_rank_change_signal(volumes, short=5, long=30):
    """H-895: Dollar Volume Rank Change. Rank volume cross-sectionally now vs N days ago.
    If rank increased (from rank 10 to rank 3), volume is growing in importance."""
    vol_short = volumes.rolling(short).mean()
    vol_long = volumes.rolling(long).mean()
    # Rank each
    rank_short = vol_short.rank(axis=1, pct=True)
    rank_long = vol_long.rank(axis=1, pct=True)
    return rank_short - rank_long


def relative_volume_signal(volumes, short=5, long=60):
    """H-896: Relative Volume = short-term avg volume / long-term avg volume.
    High RVOL = unusual activity = potential catalyst."""
    return volumes.rolling(short).mean() / volumes.rolling(long).mean().replace(0, np.nan)


def volume_concentration_signal(volumes, period=20):
    """H-897: Volume Concentration = Herfindahl index of daily volume share.
    For each asset, compute daily vol share of total, then HHI of shares over period.
    Concentrated volume = fewer big-volume days = event-driven. Dispersed = steady flow."""
    total_vol = volumes.sum(axis=1)
    vol_share = volumes.div(total_vol.replace(0, np.nan), axis=0)
    # For each asset, compute variability of its volume share over period
    signal = vol_share.rolling(period).std() / vol_share.rolling(period).mean().replace(0, np.nan)
    return signal


def cum_vol_divergence_signal(volumes, short=5, long=30):
    """H-898: Cumulative Volume Divergence = cumulative sum of (vol - sma(vol)) / sma(vol).
    Positive divergence = sustained above-average volume = accumulation."""
    sma = volumes.rolling(long).mean()
    deviation = (volumes - sma) / sma.replace(0, np.nan)
    return deviation.rolling(short).sum()


def vol_trend_persistence_signal(volumes, period=20):
    """H-899: Volume Trend Persistence = count of consecutive days above avg volume,
    minus count below. Positive = sustained high volume = institutional interest."""
    sma = volumes.rolling(period).mean()
    above = (volumes > sma).astype(float)
    # Rolling sum of above-average days
    return above.rolling(period).sum() / period


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

    # H-892: Volume Acceleration
    for short, long in [(3, 14), (5, 20), (7, 30)]:
        sig = volume_acceleration_signal(volumes, short, long)
        r = run_signal(f"H-892 (VolAccel {short}/{long})", sig, closes, long + 5, configs)
        if r.get("sharpe", 0) > results.get("H-892", {}).get("sharpe", -99):
            results["H-892"] = r

    # H-893: Volume Volatility
    for period in [14, 20, 30]:
        sig = volume_volatility_signal(volumes, period)
        r = run_signal(f"H-893 (VolVol P{period})", sig, closes, period + 5, configs, direction="low_long")
        if r.get("sharpe", 0) > results.get("H-893", {}).get("sharpe", -99):
            results["H-893"] = r

    # H-894: Vol-Price Correlation
    for period in [14, 20, 30]:
        sig = vol_price_corr_signal(closes, volumes, period)
        r = run_signal(f"H-894 (VP Corr P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-894", {}).get("sharpe", -99):
            results["H-894"] = r

    # H-895: Dollar Volume Rank Change
    for short, long in [(5, 20), (5, 30), (7, 30)]:
        sig = dvol_rank_change_signal(volumes, short, long)
        r = run_signal(f"H-895 (DVolRank {short}/{long})", sig, closes, long + 5, configs)
        if r.get("sharpe", 0) > results.get("H-895", {}).get("sharpe", -99):
            results["H-895"] = r

    # H-896: Relative Volume
    for short, long in [(3, 30), (5, 60), (7, 60)]:
        sig = relative_volume_signal(volumes, short, long)
        r = run_signal(f"H-896 (RVOL {short}/{long})", sig, closes, long + 5, configs)
        if r.get("sharpe", 0) > results.get("H-896", {}).get("sharpe", -99):
            results["H-896"] = r

    # H-897: Volume Concentration
    for period in [14, 20, 30]:
        sig = volume_concentration_signal(volumes, period)
        r = run_signal(f"H-897 (VolConc P{period})", sig, closes, period + 5, configs, direction="low_long")
        if r.get("sharpe", 0) > results.get("H-897", {}).get("sharpe", -99):
            results["H-897"] = r

    # H-898: Cumulative Volume Divergence
    for short, long in [(3, 20), (5, 30), (7, 30)]:
        sig = cum_vol_divergence_signal(volumes, short, long)
        r = run_signal(f"H-898 (CumVolDiv {short}/{long})", sig, closes, long + 5, configs)
        if r.get("sharpe", 0) > results.get("H-898", {}).get("sharpe", -99):
            results["H-898"] = r

    # H-899: Volume Trend Persistence
    for period in [14, 20, 30]:
        sig = vol_trend_persistence_signal(volumes, period)
        r = run_signal(f"H-899 (VolPersist P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-899", {}).get("sharpe", -99):
            results["H-899"] = r

    # Summary
    print("\n" + "=" * 60)
    print("BATCH SUMMARY: H-892 to H-899 (Volume Dynamics)")
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
