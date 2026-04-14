"""
Batch backtest: H-1116 to H-1123 — Regime-Conditional & Adaptive Signals.
XS signals that adapt based on market conditions (dispersion, vol regime, breadth).

H-1116: Dispersion-Timed Momentum — strengthen momentum in high dispersion regimes
H-1117: Vol-Regime Momentum — momentum in low vol, reversal in high vol
H-1118: BTC-Trend Conditional — momentum when BTC trending, mean-reversion when ranging
H-1119: Correlation-Adjusted Momentum — reduce momentum when avg XS correlation is high
H-1120: Dynamic Lookback Momentum — shorter lookback in high vol, longer in low vol
H-1121: Breadth-Conditional Momentum — momentum when breadth narrow, reversal when wide
H-1122: Momentum Crash Protection — reduce position when recent momentum DD is high
H-1123: Performance-Adaptive Signal — weight recent winners among factors
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


def xs_zscore(df):
    mu = df.mean(axis=1)
    sigma = df.std(axis=1).clip(lower=1e-10)
    return df.sub(mu, axis=0).div(sigma, axis=0)


def compute_signals(closes, volumes):
    returns = closes.pct_change()
    signals = {}

    mom60 = returns.rolling(60).sum()
    mom5 = returns.rolling(5).sum()
    vol20 = returns.rolling(20).std()

    # Market-level conditioning variables
    xs_disp = returns.std(axis=1).rolling(20).mean()
    xs_disp_z = (xs_disp - xs_disp.rolling(120).mean()) / xs_disp.rolling(120).std().clip(lower=1e-10)

    btc_col = [c for c in closes.columns if "BTC" in c][0]
    btc_ret = returns[btc_col]
    btc_vol = btc_ret.rolling(20).std()
    btc_vol_z = (btc_vol - btc_vol.rolling(120).mean()) / btc_vol.rolling(120).std().clip(lower=1e-10)

    btc_mom = btc_ret.rolling(60).sum()
    btc_trending = btc_mom.abs() > btc_mom.rolling(120).std()

    avg_corr = pd.Series(index=closes.index, dtype=float)
    for i in range(65, len(closes)):
        window = returns.iloc[i-60:i].dropna(axis=1)
        if window.shape[1] < 5:
            continue
        corr_mat = window.corr().values
        n = corr_mat.shape[0]
        mask = np.triu(np.ones((n, n), dtype=bool), k=1)
        avg_corr.iloc[i] = corr_mat[mask].mean()

    breadth = (returns > 0).sum(axis=1) / returns.count(axis=1)
    breadth_ma = breadth.rolling(20).mean()
    breadth_z = (breadth_ma - 0.5) / breadth_ma.rolling(120).std().clip(lower=1e-10)

    # H-1116: Dispersion-Timed Momentum
    z_mom = xs_zscore(mom60)
    disp_weight = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        disp_weight[col] = 1 + xs_disp_z.clip(-2, 2)
    signals["disp_timed_mom"] = z_mom * disp_weight

    # H-1117: Vol-Regime Momentum
    # Low vol → momentum, high vol → reversal
    z_rev = xs_zscore(-mom5)
    vol_regime_signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(65, len(closes)):
        if btc_vol_z.iloc[i] > 0.5:
            vol_regime_signal.iloc[i] = z_rev.iloc[i]
        else:
            vol_regime_signal.iloc[i] = z_mom.iloc[i]
    signals["vol_regime_mom"] = vol_regime_signal

    # H-1118: BTC-Trend Conditional
    trend_signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(65, len(closes)):
        if btc_trending.iloc[i]:
            trend_signal.iloc[i] = z_mom.iloc[i]
        else:
            trend_signal.iloc[i] = z_rev.iloc[i]
    signals["btc_trend_cond"] = trend_signal

    # H-1119: Correlation-Adjusted Momentum
    corr_adj = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    avg_corr_z = (avg_corr - avg_corr.rolling(120).mean()) / avg_corr.rolling(120).std().clip(lower=1e-10)
    for col in closes.columns:
        corr_weight = 1 - avg_corr_z.clip(-1, 1) * 0.5
        corr_adj[col] = z_mom[col] * corr_weight
    signals["corr_adj_mom"] = corr_adj

    # H-1120: Dynamic Lookback Momentum
    mom_short = returns.rolling(20).sum()
    mom_long = returns.rolling(60).sum()
    z_mom_s = xs_zscore(mom_short)
    z_mom_l = xs_zscore(mom_long)
    dyn_lb = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(65, len(closes)):
        if btc_vol_z.iloc[i] > 0:
            dyn_lb.iloc[i] = z_mom_s.iloc[i]
        else:
            dyn_lb.iloc[i] = z_mom_l.iloc[i]
    signals["dynamic_lookback"] = dyn_lb

    # H-1121: Breadth-Conditional Momentum
    breadth_signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(65, len(closes)):
        if breadth_z.iloc[i] < 0:
            breadth_signal.iloc[i] = z_mom.iloc[i]
        else:
            breadth_signal.iloc[i] = z_rev.iloc[i]
    signals["breadth_cond"] = breadth_signal

    # H-1122: Momentum Crash Protection
    mom_pnl = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        mom_pnl[col] = mom60[col].rank(axis=0, pct=True)
    mom_cumret = z_mom.cumsum()
    mom_dd = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        running_max = mom_cumret[col].cummax()
        mom_dd[col] = mom_cumret[col] - running_max
    crash_protect = z_mom.copy()
    for col in closes.columns:
        dd_z = mom_dd[col].rolling(60).mean() / mom_dd[col].rolling(60).std().clip(lower=1e-10)
        weight = (1 + dd_z.clip(-2, 0) * 0.3)
        crash_protect[col] = z_mom[col] * weight
    signals["crash_protect"] = crash_protect

    # H-1123: Performance-Adaptive Signal
    # Combine momentum, vol, and size based on recent 20d performance
    z_vol = xs_zscore(-vol20)
    z_size = xs_zscore(volumes.rolling(20).mean())
    factor_pnl = {}
    factor_sigs = {"mom": z_mom, "vol": z_vol, "size": z_size}
    for fname, fsig in factor_sigs.items():
        daily_pnl = pd.Series(0.0, index=closes.index)
        for i in range(65, len(closes)):
            sig_row = fsig.iloc[i-1].dropna()
            if len(sig_row) < 8:
                continue
            ranked = sig_row.sort_values(ascending=False)
            longs = ranked.index[:4]
            shorts = ranked.index[-4:]
            ret_day = 0.0
            for sym in longs:
                r = returns[sym].iloc[i]
                if np.isfinite(r):
                    ret_day += r / 4
            for sym in shorts:
                r = returns[sym].iloc[i]
                if np.isfinite(r):
                    ret_day -= r / 4
            daily_pnl.iloc[i] = ret_day
        factor_pnl[fname] = daily_pnl

    adaptive = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for i in range(85, len(closes)):
        recent_perf = {}
        for fname in factor_sigs:
            recent_perf[fname] = factor_pnl[fname].iloc[i-20:i].sum()
        total = sum(max(0, v) for v in recent_perf.values())
        if total <= 0:
            weights = {f: 1/3 for f in factor_sigs}
        else:
            weights = {f: max(0, v) / total for f, v in recent_perf.items()}
        for fname, w in weights.items():
            adaptive.iloc[i] += w * factor_sigs[fname].iloc[i]
    signals["adaptive"] = adaptive

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
    closes, volumes = load_daily()
    print(f"Loaded {len(closes)} bars, {len(closes.columns)} assets")
    print()

    print("Computing signals...")
    signals = compute_signals(closes, volumes)
    print(f"Got {len(signals)} signal types")
    print()

    feature_map = {
        "H-1116": ("disp_timed_mom", "Dispersion-Timed Momentum"),
        "H-1117": ("vol_regime_mom", "Vol-Regime Conditional"),
        "H-1118": ("btc_trend_cond", "BTC-Trend Conditional"),
        "H-1119": ("corr_adj_mom", "Correlation-Adjusted Momentum"),
        "H-1120": ("dynamic_lookback", "Dynamic Lookback Momentum"),
        "H-1121": ("breadth_cond", "Breadth-Conditional"),
        "H-1122": ("crash_protect", "Momentum Crash Protection"),
        "H-1123": ("adaptive", "Performance-Adaptive Signal"),
    }

    results = {}
    lookback = 60

    for hyp_id, (sig_name, desc) in feature_map.items():
        print(f"\n{hyp_id}: {desc}")
        sig_df = signals[sig_name]
        r = run_signal(hyp_id, sig_df, closes, lookback,
                       ["high_long", "low_long"], [3, 4], [5, 7])
        if r:
            results[hyp_id] = r

    print(f"\n{'='*80}")
    print(f"BATCH SUMMARY: {len(results)}/{8} signals with positive IS Sharpe")
    for name, r in sorted(results.items(), key=lambda x: -x[1]["sharpe"]):
        status = "CONFIRMED" if r["wf_pos"] >= max(2, r["wf_total"] * 0.5) and r["p_val"] < 0.1 else "BORDERLINE" if r["wf_pos"] >= 2 else "REJECTED"
        print(f"  {name}: Sharpe {r['sharpe']:.3f} | WF {r['wf_pos']}/{r['wf_total']} | p={r['p_val']:.3f} | "
              f"corr {r['h012_corr']:.3f} | SH {r['sh1']:.2f}/{r['sh2']:.2f} | {status}")


if __name__ == "__main__":
    main()
