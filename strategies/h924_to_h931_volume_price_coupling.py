"""
Batch backtest: H-924 to H-931 — Volume-Price Coupling XS Signals.

H-924: Volume Conviction XS — volume on up-days vs down-days ratio
H-925: Price-Volume Trend XS — correlation of price and volume changes
H-926: Volume Breakout XS — current volume / max volume in lookback
H-927: Accumulation Index XS — sum of (close-open)/(high-low) * volume, normalized
H-928: Volume Momentum Divergence XS — sign(price mom) != sign(volume mom)
H-929: Volume-Weighted Momentum XS — price returns weighted by relative volume
H-930: Money Flow Strength XS — net money flow / total volume
H-931: Volume Regime Change XS — abrupt volume level shift detection
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

def volume_conviction_signal(closes, volumes, period=20):
    """H-924: Volume Conviction = avg volume on up days / avg volume on down days.
    High ratio = more volume confirms upward moves. Volume supports trend."""
    ret = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            v = volumes[col].iloc[i-period:i].values
            if not (np.all(np.isfinite(r)) and np.all(np.isfinite(v))):
                continue
            up_mask = r > 0
            down_mask = r < 0
            if up_mask.sum() < 3 or down_mask.sum() < 3:
                continue
            up_vol = v[up_mask].mean()
            down_vol = v[down_mask].mean()
            if down_vol == 0:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = up_vol / down_vol
    return signal


def price_volume_trend_signal(closes, volumes, period=20):
    """H-925: Price-Volume Trend = correlation of price changes and volume changes.
    Positive corr = volume rises with price (healthy trend). Negative = divergence."""
    ret = closes.pct_change()
    vol_chg = volumes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i-period:i].values
            vc = vol_chg[col].iloc[i-period:i].values
            mask = np.isfinite(r) & np.isfinite(vc)
            if mask.sum() < 10:
                continue
            corr = np.corrcoef(r[mask], vc[mask])[0, 1]
            if np.isfinite(corr):
                signal.iloc[i, signal.columns.get_loc(col)] = corr
    return signal


def volume_breakout_signal(volumes, period=20):
    """H-926: Volume Breakout = current volume / max volume in lookback.
    Near 1.0 = volume at period high (breakout). Near 0 = quiet."""
    roll_max = volumes.rolling(period).max().replace(0, np.nan)
    return volumes / roll_max


def accumulation_index_signal(closes, opens, highs, lows, volumes, period=20):
    """H-927: Accumulation Index = rolling sum of CLV * volume, normalized.
    CLV = (close-open)/(high-low). Measures buying vs selling pressure weighted by volume."""
    rng = (highs - lows).replace(0, np.nan)
    clv = (closes - opens) / rng
    ad = clv * volumes
    return ad.rolling(period).sum() / volumes.rolling(period).sum().replace(0, np.nan)


def volume_momentum_divergence_signal(closes, volumes, price_period=14, vol_period=14):
    """H-928: Volume Momentum Divergence = cases where price momentum and volume momentum disagree.
    Price up + volume down = weakening (short). Price down + volume up = accumulation (long).
    Signal = vol_mom - price_mom (divergence measure)."""
    price_mom = closes.pct_change(price_period)
    vol_mom = volumes.pct_change(vol_period)
    # Normalize both to z-scores cross-sectionally
    pm_z = price_mom.sub(price_mom.mean(axis=1), axis=0).div(price_mom.std(axis=1) + 1e-10, axis=0)
    vm_z = vol_mom.sub(vol_mom.mean(axis=1), axis=0).div(vol_mom.std(axis=1) + 1e-10, axis=0)
    # Divergence: volume momentum > price momentum = accumulation signal
    return vm_z - pm_z


def volume_weighted_momentum_signal(closes, volumes, period=20):
    """H-929: Volume-Weighted Momentum = sum of (return_i * rel_vol_i) over period.
    Weighs returns by relative volume — high-volume moves count more."""
    ret = closes.pct_change()
    rel_vol = volumes / volumes.rolling(20).mean().replace(0, np.nan)
    vw_ret = ret * rel_vol
    return vw_ret.rolling(period).sum()


def money_flow_strength_signal(closes, highs, lows, volumes, period=20):
    """H-930: Money Flow Strength = net money flow / total volume flow.
    MF = typical_price * volume. Up if close > prev_close, down otherwise.
    MF Strength = (up_flow - down_flow) / (up_flow + down_flow)."""
    tp = (closes + highs + lows) / 3
    mf = tp * volumes
    ret = closes.pct_change()
    up_mf = mf.where(ret > 0, 0)
    down_mf = mf.where(ret <= 0, 0)
    sum_up = up_mf.rolling(period).sum()
    sum_down = down_mf.rolling(period).sum()
    total = (sum_up + sum_down).replace(0, np.nan)
    return (sum_up - sum_down) / total


def volume_regime_change_signal(volumes, short=5, long=30):
    """H-931: Volume Regime Change = short-term avg volume / long-term avg volume.
    High = volume spike (regime change). Captures sudden interest shifts."""
    short_avg = volumes.rolling(short).mean()
    long_avg = volumes.rolling(long).mean().replace(0, np.nan)
    return short_avg / long_avg


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

    # H-924: Volume Conviction
    for period in [10, 14, 20, 30]:
        sig = volume_conviction_signal(closes, volumes, period)
        r = run_signal(f"H-924 (VolConviction P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-924", {}).get("sharpe", -99):
            results["H-924"] = r

    # H-925: Price-Volume Trend
    for period in [14, 20, 30]:
        sig = price_volume_trend_signal(closes, volumes, period)
        r = run_signal(f"H-925 (PVTrend P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-925", {}).get("sharpe", -99):
            results["H-925"] = r

    # H-926: Volume Breakout
    for period in [10, 14, 20, 30]:
        sig = volume_breakout_signal(volumes, period)
        r = run_signal(f"H-926 (VolBreakout P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-926", {}).get("sharpe", -99):
            results["H-926"] = r

    # H-927: Accumulation Index
    for period in [10, 14, 20, 30]:
        sig = accumulation_index_signal(closes, opens, highs, lows, volumes, period)
        r = run_signal(f"H-927 (AccumIdx P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-927", {}).get("sharpe", -99):
            results["H-927"] = r

    # H-928: Volume-Momentum Divergence
    for period in [7, 14, 20]:
        sig = volume_momentum_divergence_signal(closes, volumes, period, period)
        r = run_signal(f"H-928 (VMDiv P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-928", {}).get("sharpe", -99):
            results["H-928"] = r

    # H-929: Volume-Weighted Momentum
    for period in [10, 14, 20, 30]:
        sig = volume_weighted_momentum_signal(closes, volumes, period)
        r = run_signal(f"H-929 (VWMom P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-929", {}).get("sharpe", -99):
            results["H-929"] = r

    # H-930: Money Flow Strength
    for period in [10, 14, 20, 30]:
        sig = money_flow_strength_signal(closes, highs, lows, volumes, period)
        r = run_signal(f"H-930 (MFStrength P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-930", {}).get("sharpe", -99):
            results["H-930"] = r

    # H-931: Volume Regime Change
    for short, long in [(3, 20), (5, 30), (7, 30)]:
        sig = volume_regime_change_signal(volumes, short, long)
        r = run_signal(f"H-931 (VolRegime {short}/{long})", sig, closes, long + 5, configs)
        if r.get("sharpe", 0) > results.get("H-931", {}).get("sharpe", -99):
            results["H-931"] = r

    # Summary
    print("\n" + "=" * 70)
    print("BATCH 3 SUMMARY (H-924 to H-931)")
    print("=" * 70)
    for hid in sorted(results.keys()):
        r = results[hid]
        status = r.get("status", "")
        if status == "REJECTED_IS":
            print(f"  {hid}: REJECTED — IS {r.get('pos_pct', 0):.0f}% positive, Sharpe {r.get('sharpe', 0):.3f}")
        else:
            wf = r.get("wf", [])
            wf_pass = sum(1 for w in wf if w > 0)
            sh1, sh2, p = r.get("sh", (0, 0, 1))
            corr = r.get("corr", 0)
            sh_pass = "PASS" if p < 0.1 else "FAIL"
            params = r.get("params", "?")
            print(f"  {hid}: Sharpe {r['sharpe']:.3f}, WF {wf_pass}/{len(wf)}, "
                  f"SH p={p:.3f} {sh_pass}, corr {corr}, {params}")

    return results


if __name__ == "__main__":
    run_batch()
