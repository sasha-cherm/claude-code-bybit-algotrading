"""
Batch backtest: H-1188 to H-1195 — Structural / Regime Signals.
Detecting structural properties of price processes as XS ranking signals.

H-1188: Breakout Distance — (close - 40d high) / 40d range. Proximity to breakout.
H-1189: Support Strength — # bounces near 20d low over 20d. Anti-fragility.
H-1190: Hurst Exponent (approx) — R/S analysis over 40d. >0.5 = trending.
H-1191: Return Autocorrelation — autocorr of 5d returns over 60d. Regime persistence.
H-1192: Volatility of Volatility — std of 5d vol computed over 20d window.
H-1193: Gap Fill Ratio — % of overnight gaps filled same day over 20d.
H-1194: Trend Linearity — R² of linear regression on log-closes over 20d.
H-1195: Mean Reversion Speed — half-life from OU process estimated from 40d.
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


def load_daily():
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
    common = closes.index
    return closes.loc[common], highs.loc[common], lows.loc[common], opens.loc[common], volumes.loc[common]


def compute_signals(closes, highs, lows, opens, volumes):
    returns = closes.pct_change()
    signals = {}

    # H-1188: Breakout Distance — (close - 40d high) / 40d range
    high40 = closes.rolling(40).max()
    low40 = closes.rolling(40).min()
    rng40 = (high40 - low40).clip(lower=1e-10)
    signals["breakout_distance"] = (closes - high40) / rng40

    # H-1189: Support Strength — # of times close near 20d low / total days
    sup = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        low20 = closes[col].rolling(20).min()
        rng20 = (closes[col].rolling(20).max() - low20).clip(lower=1e-10)
        near_low = ((closes[col] - low20) / rng20 < 0.1).astype(float)
        sup[col] = near_low.rolling(20).sum()
    signals["support_strength"] = sup

    # H-1190: Hurst Exponent (approximate R/S method) over 40d
    hurst = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(40, len(r)):
            window = r[i-40:i]
            window = window[np.isfinite(window)]
            if len(window) < 20:
                continue
            mean_r = np.mean(window)
            deviate = np.cumsum(window - mean_r)
            R = np.max(deviate) - np.min(deviate)
            S = np.std(window, ddof=1)
            if S > 1e-10 and R > 0:
                out[i] = np.log(R / S) / np.log(len(window))
            else:
                out[i] = 0.5
        hurst[col] = out
    signals["hurst"] = hurst

    # H-1191: Return Autocorrelation — autocorr of 5d returns over 60d
    ret5 = closes.pct_change(5)
    acorr = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r5 = ret5[col]
        acorr[col] = r5.rolling(60).apply(lambda x: x.autocorr(lag=1) if len(x.dropna()) > 10 else 0, raw=False)
    signals["return_autocorr"] = acorr

    # H-1192: Volatility of Volatility — std of 5d rolling vol, over 20d
    vol5 = returns.rolling(5).std()
    signals["vol_of_vol"] = vol5.rolling(20).std()

    # H-1193: Gap Fill Ratio — % of overnight gaps filled same day, 20d
    gfr = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        gap = opens[col] - closes[col].shift(1)
        gap_up = gap > 0
        gap_dn = gap < 0
        filled_up = gap_up & (lows[col] <= closes[col].shift(1))
        filled_dn = gap_dn & (highs[col] >= closes[col].shift(1))
        has_gap = (gap.abs() > 1e-10).astype(float)
        filled = (filled_up | filled_dn).astype(float)
        gap_count = has_gap.rolling(20).sum().clip(lower=1)
        fill_count = filled.rolling(20).sum()
        gfr[col] = fill_count / gap_count
    signals["gap_fill_ratio"] = gfr

    # H-1194: Trend Linearity — R² of log-close regression over 20d
    tl = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    log_c = np.log(closes.clip(lower=1e-10))
    for col in closes.columns:
        lc = log_c[col].values
        out = np.full(len(lc), np.nan)
        x = np.arange(20)
        for i in range(20, len(lc)):
            y = lc[i-20:i]
            if np.any(~np.isfinite(y)):
                continue
            slope, intercept, r_value, _, _ = stats.linregress(x, y)
            out[i] = r_value ** 2 * np.sign(slope)
        tl[col] = out
    signals["trend_linearity"] = tl

    # H-1195: Mean Reversion Speed — OU half-life from 40d window
    mrs = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        lc = np.log(closes[col].clip(lower=1e-10)).values
        out = np.full(len(lc), np.nan)
        for i in range(40, len(lc)):
            y = lc[i-40:i]
            if np.any(~np.isfinite(y)):
                continue
            dy = np.diff(y)
            y_lag = y[:-1]
            if np.std(y_lag) < 1e-10:
                continue
            slope, _, _, _, _ = stats.linregress(y_lag, dy)
            if slope < 0:
                hl = -np.log(2) / slope
                out[i] = min(hl, 100)
            else:
                out[i] = 100
        mrs[col] = out
    signals["mr_speed"] = mrs

    return signals


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
                 n_folds=5, test_days=120):
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


def run_signal(name, signal_df, closes, lookback, directions, n_ls_list=[4],
               rebal_list=[5, 7]):
    common_idx = closes.index.intersection(signal_df.index)
    common_cols = [c for c in closes.columns if c in signal_df.columns]
    if len(common_cols) < 8 or len(common_idx) < 200:
        print(f"  {name}: Insufficient data ({len(common_cols)} assets, {len(common_idx)} days) — SKIP")
        return None
    closes_c = closes[common_cols].loc[common_idx]
    signal_c = signal_df[common_cols].loc[common_idx]

    best = {"sharpe": -999}
    all_positive = 0
    all_total = 0
    for direction in directions:
        for n_ls in n_ls_list:
            for rebal in rebal_list:
                pnl = xs_backtest(closes_c, signal_c, lookback, rebal, n_ls, direction)
                m = compute_metrics(pnl)
                all_total += 1
                if m["sharpe"] > 0:
                    all_positive += 1
                if m["sharpe"] > best.get("sharpe", -999):
                    best = {**m, "direction": direction, "n_ls": n_ls, "rebal": rebal,
                            "pnl": pnl, "closes_c": closes_c, "signal_c": signal_c}
    is_pct = f"{100*all_positive//all_total}%" if all_total > 0 else "N/A"
    if best["sharpe"] <= 0:
        print(f"  {name}: IS {is_pct} ({all_positive}/{all_total} positive) — SKIP")
        return None
    pnl = best["pnl"]
    wf = walk_forward(best["closes_c"], best["signal_c"], lookback, best["rebal"],
                      best["n_ls"], best["direction"])
    sh1, sh2, p_val = split_half_test(pnl)
    corr = h012_correlation(best["closes_c"], best["signal_c"], lookback, best["rebal"],
                            best["n_ls"], best["direction"])
    wf_pos = sum(1 for x in wf if x > 0)
    print(f"  {name}: IS Sharpe {best['sharpe']:.3f} | Ann {best['annual_ret']:.1f}% | DD {best['max_dd']:.1f}% | "
          f"Dir={best['direction']} | IS {is_pct} ({all_positive}/{all_total}) | "
          f"WF {wf_pos}/{len(wf)} {[round(x,2) for x in wf]} | SH {sh1:.3f}/{sh2:.3f} p={p_val:.3f} | "
          f"H012 corr {corr:.3f} | N={len(pnl)}")
    return {
        "sharpe": best["sharpe"], "annual_ret": best["annual_ret"],
        "max_dd": best["max_dd"], "direction": best["direction"],
        "n_ls": best["n_ls"], "rebal": best["rebal"],
        "wf": wf, "wf_pos": wf_pos, "wf_total": len(wf),
        "sh1": sh1, "sh2": sh2, "p_val": round(p_val, 4),
        "h012_corr": corr, "n_bars": len(pnl),
        "is_positive_pct": is_pct
    }


def main():
    print("Loading data...")
    closes, highs, lows, opens, volumes = load_daily()
    print(f"Loaded {len(closes)} bars, {len(closes.columns)} assets")
    print()

    print("Computing signals...")
    signals = compute_signals(closes, highs, lows, opens, volumes)
    print(f"Got {len(signals)} signal types")
    print()

    feature_map = {
        "H-1188": ("breakout_distance", "Breakout Distance (close vs 40d high)"),
        "H-1189": ("support_strength", "Support Strength (bounces near 20d low)"),
        "H-1190": ("hurst", "Hurst Exponent (R/S 40d)"),
        "H-1191": ("return_autocorr", "Return Autocorrelation (5d rets, 60d)"),
        "H-1192": ("vol_of_vol", "Volatility of Volatility (5d/20d)"),
        "H-1193": ("gap_fill_ratio", "Gap Fill Ratio (20d)"),
        "H-1194": ("trend_linearity", "Trend Linearity (R² 20d)"),
        "H-1195": ("mr_speed", "Mean Reversion Speed (OU half-life 40d)"),
    }

    results = {}
    lookback = 30

    for hyp_id, (sig_name, desc) in feature_map.items():
        print(f"\n{hyp_id}: {desc}")
        sig_df = signals[sig_name]
        r = run_signal(hyp_id, sig_df, closes, lookback,
                       ["high_long", "low_long"], [3, 4], [3, 5, 7])
        if r:
            results[hyp_id] = r

    print(f"\n{'='*80}")
    print(f"BATCH SUMMARY: {len(results)}/{8} signals with positive IS Sharpe")
    for name, r in sorted(results.items(), key=lambda x: -x[1]["sharpe"]):
        status = "CONFIRMED" if r["wf_pos"] >= max(2, r["wf_total"] * 0.5) and r["p_val"] < 0.15 else "BORDERLINE" if r["wf_pos"] >= 2 else "REJECTED"
        print(f"  {name}: Sharpe {r['sharpe']:.3f} | WF {r['wf_pos']}/{r['wf_total']} | p={r['p_val']:.3f} | "
              f"corr {r['h012_corr']:.3f} | SH {r['sh1']:.2f}/{r['sh2']:.2f} | {status}")


if __name__ == "__main__":
    main()
