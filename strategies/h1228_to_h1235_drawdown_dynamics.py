"""
Batch backtest: H-1228 to H-1235 — Drawdown Dynamics.
Cross-sectional signals based on drawdown characteristics and recovery patterns.

H-1228: Current Drawdown Depth — distance from 60d rolling high.
H-1229: Drawdown Duration — days since last 60d high.
H-1230: Recovery Speed — avg daily gain after drawdown troughs / drawdown depth.
H-1231: Underwater Ratio — fraction of last 60d spent below prior peak.
H-1232: Max DD Change — change in rolling 30d max drawdown vs 60d.
H-1233: Drawdown Frequency — number of >2% drawdown episodes in 60d.
H-1234: Mean Recovery Time — avg days to recover from >1% drops.
H-1235: Pain Ratio — mean drawdown depth / abs(mean return), drag per gain.
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


def compute_signals(closes, volumes):
    returns = closes.pct_change()
    signals = {}
    W = 60

    # H-1228: Current Drawdown Depth — pct below rolling high
    rolling_high = closes.rolling(W).max()
    dd_depth = (closes - rolling_high) / rolling_high
    signals["dd_depth"] = dd_depth

    # H-1229: Drawdown Duration — days since rolling high
    dd_dur = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        p = closes[col].values
        rh = rolling_high[col].values
        out = np.full(len(p), np.nan)
        for i in range(W, len(p)):
            if np.isnan(rh[i]):
                continue
            days = 0
            for j in range(i, max(i - W, -1), -1):
                if p[j] >= rh[i] * 0.999:
                    break
                days += 1
            out[i] = days
        dd_dur[col] = out
    signals["dd_duration"] = dd_dur

    # H-1230: Recovery Speed — avg return in 5 days after trough vs depth
    rec_speed = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        p = closes[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            window = r[i-W:i]
            mask = np.isfinite(window)
            if mask.sum() < 20:
                continue
            cum = np.cumsum(window[mask])
            running_max = np.maximum.accumulate(cum)
            dd = cum - running_max
            if np.min(dd) >= -0.005:
                out[i] = 0
                continue
            trough_idx = np.argmin(dd)
            if trough_idx < len(cum) - 3:
                recovery = cum[min(trough_idx + 5, len(cum) - 1)] - cum[trough_idx]
                depth = abs(dd[trough_idx])
                out[i] = recovery / (depth + 1e-10)
        rec_speed[col] = out
    signals["recovery_speed"] = rec_speed

    # H-1231: Underwater Ratio — fraction of lookback below prior peak
    uw_ratio = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        p = closes[col].values
        out = np.full(len(p), np.nan)
        for i in range(W, len(p)):
            window = p[i-W:i+1]
            if np.any(np.isnan(window)):
                continue
            rm = np.maximum.accumulate(window)
            underwater = np.sum(window < rm * 0.999) / len(window)
            out[i] = underwater
        uw_ratio[col] = out
    signals["underwater_ratio"] = uw_ratio

    # H-1232: Max DD Change — 30d max DD minus 60d max DD (improvement = positive)
    dd_change = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            w60 = r[i-60:i] if i >= 60 else r[:i]
            w30 = r[i-30:i]
            mask60 = np.isfinite(w60)
            mask30 = np.isfinite(w30)
            if mask60.sum() < 20 or mask30.sum() < 15:
                continue

            def max_dd(rets):
                cum = np.cumsum(rets)
                rm = np.maximum.accumulate(cum)
                return np.min(cum - rm)
            dd60 = max_dd(w60[mask60])
            dd30 = max_dd(w30[mask30])
            out[i] = dd30 - dd60
        dd_change[col] = out
    signals["dd_change"] = dd_change

    # H-1233: Drawdown Frequency — number of >2% drawdown episodes in 60d
    dd_freq = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            window = r[i-W:i]
            mask = np.isfinite(window)
            if mask.sum() < 20:
                continue
            rets = window[mask]
            cum = np.cumsum(rets)
            rm = np.maximum.accumulate(cum)
            dd = cum - rm
            in_dd = False
            count = 0
            for d in dd:
                if d < -0.02 and not in_dd:
                    count += 1
                    in_dd = True
                elif d >= -0.005:
                    in_dd = False
            out[i] = count
        dd_freq[col] = out
    signals["dd_frequency"] = dd_freq

    # H-1234: Mean Recovery Time — avg days to recover from >1% drawdowns
    mrt = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            window = r[i-W:i]
            mask = np.isfinite(window)
            if mask.sum() < 20:
                continue
            rets = window[mask]
            cum = np.cumsum(rets)
            rm = np.maximum.accumulate(cum)
            dd = cum - rm
            rec_times = []
            dd_start = None
            for j, d in enumerate(dd):
                if d < -0.01 and dd_start is None:
                    dd_start = j
                elif d >= 0 and dd_start is not None:
                    rec_times.append(j - dd_start)
                    dd_start = None
            out[i] = np.mean(rec_times) if rec_times else W
        mrt[col] = out
    signals["mean_recovery_time"] = mrt

    # H-1235: Pain Ratio — mean DD depth / mean abs return
    pain = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            window = r[i-W:i]
            mask = np.isfinite(window)
            if mask.sum() < 20:
                continue
            rets = window[mask]
            cum = np.cumsum(rets)
            rm = np.maximum.accumulate(cum)
            dd = cum - rm
            mean_dd = np.mean(np.abs(dd))
            mean_ret = np.mean(np.abs(rets))
            out[i] = mean_dd / (mean_ret + 1e-10)
        pain[col] = out
    signals["pain_ratio"] = pain

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
        print(f"  {name}: Insufficient data — SKIP")
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
    closes, volumes = load_daily()
    print(f"Loaded {len(closes)} bars, {len(closes.columns)} assets")
    print()

    print("Computing signals...")
    signals = compute_signals(closes, volumes)
    print(f"Got {len(signals)} signal types")
    print()

    feature_map = {
        "H-1228": ("dd_depth", "Current Drawdown Depth (pct below 60d high)"),
        "H-1229": ("dd_duration", "Drawdown Duration (days since 60d high)"),
        "H-1230": ("recovery_speed", "Recovery Speed (gain after trough / depth)"),
        "H-1231": ("underwater_ratio", "Underwater Ratio (frac of 60d below peak)"),
        "H-1232": ("dd_change", "Max DD Change (30d DD - 60d DD)"),
        "H-1233": ("dd_frequency", "Drawdown Frequency (>2% DD episodes in 60d)"),
        "H-1234": ("mean_recovery_time", "Mean Recovery Time (avg days to recover)"),
        "H-1235": ("pain_ratio", "Pain Ratio (mean DD depth / mean |ret|)"),
    }

    results = {}
    lookback = 65

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
