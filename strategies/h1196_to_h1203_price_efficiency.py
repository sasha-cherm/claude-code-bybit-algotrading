"""
Batch backtest: H-1196 to H-1203 — Price Efficiency Signals.
How efficiently do prices process information? Variance ratios, delay measures,
autocorrelation structure, and information content proxies.

H-1196: Variance Ratio — VR(5) = var(5d ret) / (5 * var(1d ret)). Departure from random walk.
H-1197: Price Delay — R²(ret ~ lagged BTC ret) / R²(ret ~ concurrent BTC ret). Info speed.
H-1198: Absolute Autocorrelation — |autocorr(1d rets, 20d)|. Return predictability.
H-1199: Close-Open Dispersion — std(overnight rets) / std(intraday rets). Info asymmetry.
H-1200: Amihud Persistence — autocorr of Amihud illiquidity over 20d. Liquidity stability.
H-1201: Return-Volume Correlation — corr(|rets|, volume, 20d). Information content.
H-1202: Signed Volume Asymmetry — corr(rets, volume, 20d). Directional volume.
H-1203: Intraday Range Efficiency — |close-open|/(high-low) over 20d avg. Price efficiency.
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
    return closes, highs, lows, opens, volumes


def compute_signals(closes, highs, lows, opens, volumes):
    returns = closes.pct_change()
    signals = {}

    # H-1196: Variance Ratio VR(5) = var(5d ret) / (5 * var(1d ret))
    ret5 = closes.pct_change(5)
    var1 = returns.rolling(40).var()
    var5 = ret5.rolling(40).var()
    signals["variance_ratio"] = var5 / (5 * var1).clip(lower=1e-15)

    # H-1197: Price Delay — how quickly does asset respond to BTC moves?
    btc_ret = returns.get("BTC/USDT", returns.iloc[:, 0])
    delay = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        if col == "BTC/USDT":
            delay[col] = np.nan
            continue
        out = np.full(len(closes), np.nan)
        r = returns[col].values
        bm = btc_ret.values
        for i in range(42, len(r)):
            y = r[i-40:i]
            x0 = bm[i-40:i]
            x1 = bm[i-41:i-1]
            mask = np.isfinite(y) & np.isfinite(x0) & np.isfinite(x1)
            if mask.sum() < 20:
                continue
            y_m, x0_m, x1_m = y[mask], x0[mask], x1[mask]
            try:
                _, _, r0, _, _ = stats.linregress(x0_m, y_m)
                X = np.column_stack([x0_m, x1_m, np.ones(len(x0_m))])
                coef, _, _, _ = np.linalg.lstsq(X, y_m, rcond=None)
                pred = X @ coef
                ss_res = np.sum((y_m - pred)**2)
                ss_tot = np.sum((y_m - np.mean(y_m))**2)
                r2_full = 1 - ss_res / ss_tot if ss_tot > 0 else 0
                r2_concurrent = r0**2
                out[i] = 1 - r2_concurrent / max(r2_full, 1e-10) if r2_full > 0.01 else 0
            except:
                out[i] = 0
        delay[col] = out
    signals["price_delay"] = delay

    # H-1198: Absolute Autocorrelation of returns over 20d
    abs_ac = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col]
        abs_ac[col] = r.rolling(20).apply(
            lambda x: abs(x.autocorr(lag=1)) if len(x.dropna()) > 10 else 0, raw=False)
    signals["abs_autocorr"] = abs_ac

    # H-1199: Close-Open Dispersion — std(overnight) / std(intraday)
    overnight = (opens / closes.shift(1) - 1).replace([np.inf, -np.inf], np.nan)
    intraday = (closes / opens - 1).replace([np.inf, -np.inf], np.nan)
    std_on = overnight.rolling(20).std()
    std_id = intraday.rolling(20).std().clip(lower=1e-10)
    signals["co_dispersion"] = std_on / std_id

    # H-1200: Amihud Persistence — autocorr of Amihud illiquidity
    amihud = (returns.abs() / volumes.clip(lower=1)).replace([np.inf, -np.inf], np.nan)
    amihud_ac = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        a = amihud[col]
        amihud_ac[col] = a.rolling(20).apply(
            lambda x: x.autocorr(lag=1) if len(x.dropna()) > 10 else 0, raw=False)
    signals["amihud_persist"] = amihud_ac

    # H-1201: Return-Volume Correlation — corr(|rets|, volume, 20d)
    abs_ret = returns.abs()
    rv_corr = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        rv_corr[col] = abs_ret[col].rolling(20).corr(volumes[col])
    signals["ret_vol_corr"] = rv_corr

    # H-1202: Signed Volume Asymmetry — corr(rets, volume, 20d)
    sv_corr = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        sv_corr[col] = returns[col].rolling(20).corr(volumes[col])
    signals["signed_vol_asym"] = sv_corr

    # H-1203: Intraday Range Efficiency — avg(|close-open|/(high-low)) over 20d
    rng = (highs - lows).clip(lower=1e-10)
    body = (closes - opens).abs()
    eff = body / rng
    signals["range_efficiency"] = eff.rolling(20).mean()

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
        "H-1196": ("variance_ratio", "Variance Ratio VR(5)"),
        "H-1197": ("price_delay", "Price Delay (BTC response lag)"),
        "H-1198": ("abs_autocorr", "Absolute Autocorrelation (20d)"),
        "H-1199": ("co_dispersion", "Close-Open Dispersion (overnight/intraday vol)"),
        "H-1200": ("amihud_persist", "Amihud Illiquidity Persistence (20d)"),
        "H-1201": ("ret_vol_corr", "Return-Volume Correlation (20d)"),
        "H-1202": ("signed_vol_asym", "Signed Volume Asymmetry (20d)"),
        "H-1203": ("range_efficiency", "Intraday Range Efficiency (20d avg)"),
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
