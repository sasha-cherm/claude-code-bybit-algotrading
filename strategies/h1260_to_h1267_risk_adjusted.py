"""
Batch backtest: H-1260 to H-1267 — Risk-Adjusted Performance Metrics.
Cross-sectional signals based on risk-adjusted return properties.

H-1260: Upside Potential Ratio — E[r|r>0] × P(r>0) / downside_dev, 30d.
H-1261: Omega Ratio — sum(positive rets) / abs(sum(negative rets)), 30d.
H-1262: Calmar Proxy — 30d return / max drawdown over 30d.
H-1263: Risk-Return Trend — 20d rolling Sharpe minus 40d rolling Sharpe. Improving risk-reward.
H-1264: Positive Skew Score — (mean-median)/std, 30d. Nonparametric skewness.
H-1265: CVaR Rank — mean of worst 5% of returns, 30d. Expected shortfall.
H-1266: Max Consecutive Loss — longest losing streak in 30d. Pattern persistence.
H-1267: Gain Persistence — autocorrelation of sign(return) over 30d. Streakiness.
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
    W = 30

    # H-1260: Upside Potential Ratio
    upr = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() < 15:
                continue
            rv_m = rv[mask]
            pos = rv_m[rv_m > 0]
            neg = rv_m[rv_m < 0]
            if len(pos) == 0:
                out[i] = 0
                continue
            upside = np.mean(pos) * (len(pos) / len(rv_m))
            downside_dev = np.sqrt(np.mean(neg**2)) if len(neg) > 0 else 1e-10
            out[i] = upside / (downside_dev + 1e-10)
        upr[col] = out
    signals["upside_potential"] = upr

    # H-1261: Omega Ratio
    omega = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() < 15:
                continue
            rv_m = rv[mask]
            sum_pos = np.sum(rv_m[rv_m > 0])
            sum_neg = abs(np.sum(rv_m[rv_m < 0]))
            out[i] = sum_pos / (sum_neg + 1e-10)
        omega[col] = out
    signals["omega_ratio"] = omega

    # H-1262: Calmar Proxy — 30d return / max DD 30d
    calmar = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() < 15:
                continue
            rv_m = rv[mask]
            cum = np.cumsum(rv_m)
            total_ret = cum[-1]
            running_max = np.maximum.accumulate(cum)
            max_dd = abs(np.min(cum - running_max))
            out[i] = total_ret / (max_dd + 1e-10)
        calmar[col] = out
    signals["calmar_proxy"] = calmar

    # H-1263: Risk-Return Trend — 20d Sharpe - 40d Sharpe
    def rolling_sharpe(r_series, window):
        rm = r_series.rolling(window).mean()
        rs = r_series.rolling(window).std()
        return rm / (rs + 1e-10) * np.sqrt(365)
    for col in closes.columns:
        r = returns[col]
        sh20 = rolling_sharpe(r, 20)
        sh40 = rolling_sharpe(r, 40)
        if "rr_trend" not in signals:
            signals["rr_trend"] = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
        signals["rr_trend"][col] = sh20 - sh40

    # H-1264: Positive Skew Score — (mean-median)/std, 30d
    pss = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() < 15:
                continue
            rv_m = rv[mask]
            std_val = np.std(rv_m)
            if std_val > 1e-10:
                out[i] = (np.mean(rv_m) - np.median(rv_m)) / std_val
        pss[col] = out
    signals["pos_skew_score"] = pss

    # H-1265: CVaR Rank — mean of worst 5% of returns, 30d
    cvar = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() < 15:
                continue
            rv_m = np.sort(rv[mask])
            n5 = max(1, int(len(rv_m) * 0.05))
            out[i] = np.mean(rv_m[:n5])
        cvar[col] = out
    signals["cvar_5pct"] = cvar

    # H-1266: Max Consecutive Loss — longest losing streak in 30d
    mcl = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() < 15:
                continue
            rv_m = rv[mask]
            max_streak = 0
            current = 0
            for v in rv_m:
                if v < 0:
                    current += 1
                    max_streak = max(max_streak, current)
                else:
                    current = 0
            out[i] = max_streak
        mcl[col] = out
    signals["max_consec_loss"] = mcl

    # H-1267: Gain Persistence — autocorrelation of sign(return) over 30d
    gp = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() < 15:
                continue
            rv_m = np.sign(rv[mask])
            if len(rv_m) > 2 and np.std(rv_m) > 0:
                out[i] = np.corrcoef(rv_m[:-1], rv_m[1:])[0, 1]
            else:
                out[i] = 0
        gp[col] = out
    signals["gain_persistence"] = gp

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
        "H-1260": ("upside_potential", "Upside Potential Ratio (E[r|r>0]×P(up)/downside_dev, 30d)"),
        "H-1261": ("omega_ratio", "Omega Ratio (sum pos / abs sum neg, 30d)"),
        "H-1262": ("calmar_proxy", "Calmar Proxy (30d ret / max DD 30d)"),
        "H-1263": ("rr_trend", "Risk-Return Trend (20d Sharpe - 40d Sharpe)"),
        "H-1264": ("pos_skew_score", "Positive Skew Score ((mean-median)/std, 30d)"),
        "H-1265": ("cvar_5pct", "CVaR 5% (mean worst 5% returns, 30d)"),
        "H-1266": ("max_consec_loss", "Max Consecutive Loss (longest losing streak, 30d)"),
        "H-1267": ("gain_persistence", "Gain Persistence (autocorr of sign(ret), 30d)"),
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
