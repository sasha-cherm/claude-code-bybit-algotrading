"""
Batch backtest: H-1092 to H-1099 — Multi-Horizon Composite Signals.
XS signals built by comparing/combining information across multiple lookback windows.

H-1092: Momentum Term Structure Slope — slope of momentum across 5/10/20/40/60d lookbacks
H-1093: Vol Term Structure Curvature — second derivative of vol across lookback windows
H-1094: Multi-Horizon Sign Agreement — fraction of lookback windows where return is positive
H-1095: Lookback-Weighted Momentum — decaying weighted average of standardized momentum
H-1096: Acceleration Term Structure — slope of momentum changes across lookbacks
H-1097: Multi-Horizon Sharpe — compound (return/vol) across multiple lookbacks
H-1098: Return Rank Stability — mean abs rank change across all lookback windows
H-1099: Momentum Quality Score — sign agreement × return smoothness product
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

LOOKBACKS = [5, 10, 20, 40, 60]


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

    # Pre-compute returns and vols at each lookback
    mom = {}
    vols = {}
    for lb in LOOKBACKS:
        mom[lb] = returns.rolling(lb).sum()
        vols[lb] = returns.rolling(lb).std()

    # H-1092: Momentum Term Structure Slope
    # For each asset/day, regress momentum values on log(lookback)
    mom_ts_slope = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    log_lbs = np.log(LOOKBACKS)
    for i in range(65, len(closes)):
        for col in closes.columns:
            vals = [mom[lb][col].iloc[i] for lb in LOOKBACKS]
            if any(np.isnan(v) for v in vals):
                continue
            slope, _, _, _, _ = stats.linregress(log_lbs, vals)
            mom_ts_slope.loc[closes.index[i], col] = slope
    signals["mom_ts_slope"] = mom_ts_slope

    # H-1093: Vol Term Structure Curvature
    # Second derivative: vol(short) - 2*vol(mid) + vol(long)
    vol_curv = vols[5] - 2 * vols[20] + vols[60]
    signals["vol_ts_curvature"] = vol_curv

    # H-1094: Multi-Horizon Sign Agreement
    # Fraction of lookback windows where return is positive
    sign_agree = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for lb in LOOKBACKS:
        sign_agree += (mom[lb] > 0).astype(float)
    sign_agree = sign_agree / len(LOOKBACKS)
    signals["sign_agreement"] = sign_agree

    # H-1095: Lookback-Weighted Momentum — exponentially decaying weights favoring short-term
    weights = np.array([0.35, 0.25, 0.20, 0.12, 0.08])
    weighted_mom = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for lb, w in zip(LOOKBACKS, weights):
        # Standardize momentum by lookback vol
        std_mom = mom[lb] / vols[lb].clip(lower=1e-10)
        weighted_mom += w * std_mom
    signals["weighted_momentum"] = weighted_mom

    # H-1096: Acceleration Term Structure — slope of momentum changes
    accel_slope = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(70, len(closes)):
        for col in closes.columns:
            accels = []
            for lb in LOOKBACKS:
                current = mom[lb][col].iloc[i]
                prev = mom[lb][col].iloc[i-5] if i >= 5 else np.nan
                if np.isfinite(current) and np.isfinite(prev):
                    accels.append(current - prev)
                else:
                    accels.append(np.nan)
            valid = [(l, a) for l, a in zip(log_lbs, accels) if np.isfinite(a)]
            if len(valid) >= 3:
                x, y = zip(*valid)
                slope, _, _, _, _ = stats.linregress(x, y)
                accel_slope.loc[closes.index[i], col] = slope
    signals["accel_ts_slope"] = accel_slope

    # H-1097: Multi-Horizon Sharpe — average of (return/vol) across lookbacks
    multi_sharpe = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for lb in LOOKBACKS:
        multi_sharpe += mom[lb] / vols[lb].clip(lower=1e-10)
    multi_sharpe = multi_sharpe / len(LOOKBACKS)
    signals["multi_horizon_sharpe"] = multi_sharpe

    # H-1098: Return Rank Stability — mean abs rank change across lookback windows
    ranks = {}
    for lb in LOOKBACKS:
        ranks[lb] = mom[lb].rank(axis=1, ascending=False)

    rank_stability = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    n_pairs = 0
    for i_idx in range(len(LOOKBACKS)):
        for j_idx in range(i_idx + 1, len(LOOKBACKS)):
            lb_i, lb_j = LOOKBACKS[i_idx], LOOKBACKS[j_idx]
            rank_stability += (ranks[lb_i] - ranks[lb_j]).abs()
            n_pairs += 1
    rank_stability = rank_stability / max(n_pairs, 1)
    signals["rank_stability"] = rank_stability

    # H-1099: Momentum Quality Score — sign agreement × return smoothness
    # Smoothness = fraction of sub-periods with same return sign as total
    smoothness = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        sm = pd.Series(index=closes.index, dtype=float)
        for i in range(65, len(closes)):
            total_ret = mom[60][col].iloc[i]
            if np.isnan(total_ret):
                continue
            total_sign = 1 if total_ret > 0 else -1
            sub_rets = [mom[lb][col].iloc[i] for lb in [5, 10, 20]]
            if any(np.isnan(r) for r in sub_rets):
                continue
            agree_count = sum(1 for r in sub_rets if (1 if r > 0 else -1) == total_sign)
            sm.iloc[i] = agree_count / len(sub_rets)
        smoothness[col] = sm

    quality = sign_agree * smoothness
    signals["momentum_quality"] = quality

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
        "H-1092": ("mom_ts_slope", "Momentum Term Structure Slope"),
        "H-1093": ("vol_ts_curvature", "Vol Term Structure Curvature"),
        "H-1094": ("sign_agreement", "Multi-Horizon Sign Agreement"),
        "H-1095": ("weighted_momentum", "Lookback-Weighted Momentum"),
        "H-1096": ("accel_ts_slope", "Acceleration Term Structure"),
        "H-1097": ("multi_horizon_sharpe", "Multi-Horizon Sharpe"),
        "H-1098": ("rank_stability", "Return Rank Stability"),
        "H-1099": ("momentum_quality", "Momentum Quality Score"),
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
