"""
Batch backtest: H-1212 to H-1219 — Volume-Return Interaction Dynamics.
How volume interacts with returns over time to predict cross-sectional performance.

H-1212: Volume-Weighted Return — sum(ret * vol) / sum(vol) over 20d. Smart money flow.
H-1213: Volume Surprise Return — return on days with vol > 2σ over 20d. Informed trading signal.
H-1214: Up-Volume Ratio — vol on up days / total vol over 20d. Buying pressure.
H-1215: Volume Trend Return — corr(cumul vol, cumul ret) over 20d. Price-volume agreement.
H-1216: Return Per Unit Volume — sum(|ret|) / sum(vol) over 20d. Price impact / sensitivity.
H-1217: Volume Concentration in Returns — std(ret * vol) / mean(|ret * vol|) over 20d.
H-1218: Positive Vol Momentum — vol on top 5 up days / vol on top 5 down days, 20d window.
H-1219: Net Volume Delta — (vol on up days - vol on down days) / total vol, 20d window.
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

    # H-1212: Volume-Weighted Return — VWAP-style return
    vw_ret = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col]
        v = volumes[col]
        rv = r * v
        vw_ret[col] = rv.rolling(20).sum() / v.rolling(20).sum().clip(lower=1)
    signals["vw_return"] = vw_ret

    # H-1213: Volume Surprise Return — avg return on high-volume days
    vs_ret = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        v = volumes[col].values
        out = np.full(len(r), np.nan)
        for i in range(20, len(r)):
            rv = r[i-20:i]
            vv = v[i-20:i]
            mask = np.isfinite(rv) & np.isfinite(vv)
            if mask.sum() < 10:
                continue
            rv_m, vv_m = rv[mask], vv[mask]
            vol_mean = np.mean(vv_m)
            vol_std = np.std(vv_m)
            if vol_std < 1e-10:
                continue
            high_vol = vv_m > vol_mean + 1.5 * vol_std
            if high_vol.sum() > 0:
                out[i] = np.mean(rv_m[high_vol])
            else:
                out[i] = 0
        vs_ret[col] = out
    signals["vol_surprise_ret"] = vs_ret

    # H-1214: Up-Volume Ratio — volume on up days / total volume
    up_vol = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col]
        v = volumes[col]
        up_v = (v * (r > 0).astype(float))
        up_vol[col] = up_v.rolling(20).sum() / v.rolling(20).sum().clip(lower=1)
    signals["up_vol_ratio"] = up_vol

    # H-1215: Volume Trend Return — corr(cumulative vol, cumulative ret) over 20d
    vt_corr = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        v = volumes[col].values
        out = np.full(len(r), np.nan)
        for i in range(20, len(r)):
            rv = r[i-20:i]
            vv = v[i-20:i]
            mask = np.isfinite(rv) & np.isfinite(vv)
            if mask.sum() < 10:
                continue
            cum_r = np.cumsum(rv[mask])
            cum_v = np.cumsum(vv[mask])
            if np.std(cum_r) > 0 and np.std(cum_v) > 0:
                out[i] = np.corrcoef(cum_r, cum_v)[0, 1]
        vt_corr[col] = out
    signals["vol_trend_ret"] = vt_corr

    # H-1216: Return Per Unit Volume — sum(|ret|) / sum(vol) normalized XS
    abs_ret_sum = returns.abs().rolling(20).sum()
    vol_sum = volumes.rolling(20).sum().clip(lower=1)
    signals["ret_per_vol"] = abs_ret_sum / vol_sum

    # H-1217: Volume Concentration in Returns — std(ret*vol)/mean(|ret*vol|)
    rv_prod = returns * volumes
    rv_std = rv_prod.rolling(20).std()
    rv_mean = rv_prod.abs().rolling(20).mean().clip(lower=1e-15)
    signals["vol_conc_ret"] = rv_std / rv_mean

    # H-1218: Positive Vol Momentum — vol on best days / vol on worst days
    pvm = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        v = volumes[col].values
        out = np.full(len(r), np.nan)
        for i in range(20, len(r)):
            rv = r[i-20:i]
            vv = v[i-20:i]
            mask = np.isfinite(rv) & np.isfinite(vv)
            if mask.sum() < 10:
                continue
            rv_m, vv_m = rv[mask], vv[mask]
            order = np.argsort(rv_m)
            top5 = order[-5:]
            bot5 = order[:5]
            vol_top = np.sum(vv_m[top5])
            vol_bot = np.sum(vv_m[bot5])
            if vol_bot > 0:
                out[i] = vol_top / vol_bot
            else:
                out[i] = 1
        pvm[col] = out
    signals["pos_vol_mom"] = pvm

    # H-1219: Net Volume Delta — (up vol - down vol) / total vol
    for col in closes.columns:
        r = returns[col]
        v = volumes[col]
    up_v_total = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    dn_v_total = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col]
        v = volumes[col]
        up_v_total[col] = (v * (r > 0).astype(float)).rolling(20).sum()
        dn_v_total[col] = (v * (r <= 0).astype(float)).rolling(20).sum()
    total_v = volumes.rolling(20).sum().clip(lower=1)
    signals["net_vol_delta"] = (up_v_total - dn_v_total) / total_v

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
        "H-1212": ("vw_return", "Volume-Weighted Return (20d VWAP-style)"),
        "H-1213": ("vol_surprise_ret", "Volume Surprise Return (high-vol day avg ret)"),
        "H-1214": ("up_vol_ratio", "Up-Volume Ratio (vol on up days / total)"),
        "H-1215": ("vol_trend_ret", "Volume Trend Return (corr cum_vol cum_ret)"),
        "H-1216": ("ret_per_vol", "Return Per Unit Volume (|ret|/vol)"),
        "H-1217": ("vol_conc_ret", "Volume Concentration in Returns (std/mean)"),
        "H-1218": ("pos_vol_mom", "Positive Vol Momentum (top day vol / bot day vol)"),
        "H-1219": ("net_vol_delta", "Net Volume Delta ((up-down)/total vol)"),
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
