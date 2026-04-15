"""
Batch backtest: H-1236 to H-1243 — Asymmetric Behavior Signals.
Cross-sectional signals based on asymmetric return/volume characteristics.

H-1236: Gain-Loss Ratio — avg gain on up days / avg loss on down days over 20d.
H-1237: Up-Down Volume Asymmetry — mean vol on up days / mean vol on down days.
H-1238: Post-Drop Recovery — avg return day after drop / avg return day after gain.
H-1239: Conditional Volatility Asymmetry — vol after drops / vol after gains (leverage effect).
H-1240: Positive Return Concentration — max single-day gain / total sum of gains.
H-1241: Upside Capture Ratio — beta to market on up days only.
H-1242: Downside Beta Asymmetry — downside beta / upside beta.
H-1243: Tail Asymmetry Ratio — 95th pctl return / abs(5th pctl return).
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
    mkt_ret = returns.mean(axis=1)
    signals = {}
    W = 20

    # H-1236: Gain-Loss Ratio
    gl_ratio = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() < 10:
                continue
            rv_m = rv[mask]
            gains = rv_m[rv_m > 0]
            losses = rv_m[rv_m < 0]
            avg_gain = np.mean(gains) if len(gains) > 0 else 0
            avg_loss = abs(np.mean(losses)) if len(losses) > 0 else 1e-10
            out[i] = avg_gain / (avg_loss + 1e-10)
        gl_ratio[col] = out
    signals["gain_loss_ratio"] = gl_ratio

    # H-1237: Up-Down Volume Asymmetry
    ud_vol = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        v = volumes[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            vv = v[i-W:i]
            mask = np.isfinite(rv) & np.isfinite(vv)
            if mask.sum() < 10:
                continue
            rv_m, vv_m = rv[mask], vv[mask]
            up_mask = rv_m > 0
            dn_mask = rv_m < 0
            up_vol = np.mean(vv_m[up_mask]) if up_mask.sum() > 0 else 0
            dn_vol = np.mean(vv_m[dn_mask]) if dn_mask.sum() > 0 else 1e-10
            out[i] = up_vol / (dn_vol + 1e-10)
        ud_vol[col] = out
    signals["ud_vol_asym"] = ud_vol

    # H-1238: Post-Drop Recovery — avg return day after drop vs day after gain
    pdr = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W + 1, len(r)):
            rv = r[i-W-1:i]
            mask = np.isfinite(rv)
            if mask.sum() < 10:
                continue
            rv_m = rv[mask]
            after_drop = []
            after_gain = []
            for j in range(len(rv_m) - 1):
                if rv_m[j] < 0:
                    after_drop.append(rv_m[j + 1])
                elif rv_m[j] > 0:
                    after_gain.append(rv_m[j + 1])
            mean_ad = np.mean(after_drop) if after_drop else 0
            mean_ag = np.mean(after_gain) if after_gain else 0
            out[i] = mean_ad - mean_ag
        pdr[col] = out
    signals["post_drop_recovery"] = pdr

    # H-1239: Conditional Volatility Asymmetry — vol after drops / vol after gains
    cva = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W + 1, len(r)):
            rv = r[i-W-1:i]
            mask = np.isfinite(rv)
            if mask.sum() < 10:
                continue
            rv_m = rv[mask]
            after_drop_sq = []
            after_gain_sq = []
            for j in range(len(rv_m) - 1):
                if rv_m[j] < 0:
                    after_drop_sq.append(rv_m[j + 1] ** 2)
                elif rv_m[j] > 0:
                    after_gain_sq.append(rv_m[j + 1] ** 2)
            vol_ad = np.sqrt(np.mean(after_drop_sq)) if after_drop_sq else 0
            vol_ag = np.sqrt(np.mean(after_gain_sq)) if after_gain_sq else 1e-10
            out[i] = vol_ad / (vol_ag + 1e-10)
        cva[col] = out
    signals["cond_vol_asym"] = cva

    # H-1240: Positive Return Concentration — max single gain / total gains
    prc = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() < 10:
                continue
            rv_m = rv[mask]
            gains = rv_m[rv_m > 0]
            if len(gains) > 0 and np.sum(gains) > 0:
                out[i] = np.max(gains) / np.sum(gains)
            else:
                out[i] = 1.0
        prc[col] = out
    signals["pos_ret_concentration"] = prc

    # H-1241: Upside Capture Ratio — beta to market on up-market days
    uc = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        m = mkt_ret.values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mv = m[i-W:i]
            mask = np.isfinite(rv) & np.isfinite(mv)
            if mask.sum() < 8:
                continue
            rv_m, mv_m = rv[mask], mv[mask]
            up = mv_m > 0
            if up.sum() >= 3:
                mean_r = np.mean(rv_m[up])
                mean_m = np.mean(mv_m[up])
                out[i] = mean_r / (mean_m + 1e-10)
        uc[col] = out
    signals["upside_capture"] = uc

    # H-1242: Downside Beta Asymmetry — downside beta / upside beta
    dba = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        m_arr = mkt_ret.values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mv = m_arr[i-W:i]
            mask = np.isfinite(rv) & np.isfinite(mv)
            if mask.sum() < 10:
                continue
            rv_m, mv_m = rv[mask], mv[mask]
            up = mv_m > 0
            dn = mv_m < 0
            if up.sum() >= 3 and dn.sum() >= 3:
                var_up = np.var(mv_m[up])
                var_dn = np.var(mv_m[dn])
                beta_up = np.cov(rv_m[up], mv_m[up])[0, 1] / (var_up + 1e-15)
                beta_dn = np.cov(rv_m[dn], mv_m[dn])[0, 1] / (var_dn + 1e-15)
                out[i] = beta_dn / (beta_up + 1e-10) if abs(beta_up) > 1e-10 else 1
        dba[col] = out
    signals["ds_beta_asym"] = dba

    # H-1243: Tail Asymmetry Ratio — 95th percentile / abs(5th percentile)
    tar = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() < 10:
                continue
            rv_m = rv[mask]
            p95 = np.percentile(rv_m, 95)
            p5 = np.percentile(rv_m, 5)
            out[i] = p95 / (abs(p5) + 1e-10)
        tar[col] = out
    signals["tail_asym_ratio"] = tar

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
        "H-1236": ("gain_loss_ratio", "Gain-Loss Ratio (avg gain / avg loss)"),
        "H-1237": ("ud_vol_asym", "Up-Down Volume Asymmetry (vol up / vol down)"),
        "H-1238": ("post_drop_recovery", "Post-Drop Recovery (ret after drop - ret after gain)"),
        "H-1239": ("cond_vol_asym", "Conditional Vol Asymmetry (vol after drop / vol after gain)"),
        "H-1240": ("pos_ret_concentration", "Positive Return Concentration (max gain / total gains)"),
        "H-1241": ("upside_capture", "Upside Capture Ratio (beta on up-market days)"),
        "H-1242": ("ds_beta_asym", "Downside Beta Asymmetry (down beta / up beta)"),
        "H-1243": ("tail_asym_ratio", "Tail Asymmetry Ratio (95th pctl / abs 5th pctl)"),
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
