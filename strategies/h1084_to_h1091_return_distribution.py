"""
Batch backtest: H-1084 to H-1091 — Return Distribution Properties.
XS signals derived from shape/distributional characteristics of asset returns.

H-1084: Return Entropy — Shannon entropy of discretized returns
H-1085: Positive Volume Ratio — volume on up days / total volume
H-1086: DD Recovery Speed — inverse of avg time to recover from drawdowns
H-1087: Return Kurtosis — excess kurtosis of rolling returns (fat tails)
H-1088: Up-Move Efficiency — avg return on up days / avg range on up days
H-1089: Return Quantile Position — where current 5d return sits in 60d distribution
H-1090: Consecutive Extreme Frequency — frequency of back-to-back |ret| > 1.5σ days
H-1091: Overnight Return Share — portion of total return earned via close-to-open gaps
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
    closes, volumes, highs, lows, opens_ = {}, {}, {}, {}, {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_1d.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            sym = f"{ticker}/USDT"
            closes[sym] = df["close"]
            volumes[sym] = df["volume"] * df["close"]
            highs[sym] = df["high"]
            lows[sym] = df["low"]
            opens_[sym] = df["open"]
        except:
            pass
    closes = pd.DataFrame(closes).sort_index().dropna(how="all")
    volumes = pd.DataFrame(volumes).sort_index().dropna(how="all")
    highs = pd.DataFrame(highs).sort_index().dropna(how="all")
    lows = pd.DataFrame(lows).sort_index().dropna(how="all")
    opens_ = pd.DataFrame(opens_).sort_index().dropna(how="all")
    return closes, volumes, highs, lows, opens_


def compute_signals(closes, volumes, highs, lows, opens_):
    returns = closes.pct_change()
    signals = {}

    # H-1084: Return Entropy — Shannon entropy of discretized daily returns
    def rolling_entropy(series, window=30, n_bins=10):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            vals = series.iloc[i-window:i].dropna()
            if len(vals) < 15:
                continue
            counts, _ = np.histogram(vals, bins=n_bins)
            probs = counts / counts.sum()
            probs = probs[probs > 0]
            result.iloc[i] = -np.sum(probs * np.log2(probs))
        return result

    entropy = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        entropy[col] = rolling_entropy(returns[col])
    signals["return_entropy"] = entropy

    # H-1085: Positive Volume Ratio — volume on up days / total volume over 20d
    up_mask = (returns > 0).astype(float)
    pos_vol_ratio = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        up_vol = (volumes[col] * up_mask[col]).rolling(20).sum()
        total_vol = volumes[col].rolling(20).sum()
        pos_vol_ratio[col] = up_vol / total_vol.clip(lower=1)
    signals["pos_vol_ratio"] = pos_vol_ratio

    # H-1086: DD Recovery Speed
    dd_recovery = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        cum_ret = returns[col].cumsum()
        running_max = cum_ret.expanding().max()
        dd = cum_ret - running_max
        recovery_speed = pd.Series(index=closes.index, dtype=float)
        for i in range(60, len(closes)):
            dd_window = dd.iloc[i-60:i]
            trough_idx = dd_window.idxmin()
            trough_pos = list(dd_window.index).index(trough_idx)
            after_trough = dd_window.iloc[trough_pos:]
            if len(after_trough) > 1 and dd_window.min() < -0.001:
                recovery = (after_trough.iloc[-1] - after_trough.iloc[0]) / abs(dd_window.min())
                recovery_speed.iloc[i] = recovery
        dd_recovery[col] = recovery_speed
    signals["dd_recovery_speed"] = dd_recovery

    # H-1087: Return Kurtosis — rolling 30d excess kurtosis
    kurtosis = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        kurtosis[col] = returns[col].rolling(30).apply(
            lambda x: stats.kurtosis(x.dropna()) if len(x.dropna()) > 10 else np.nan, raw=False)
    signals["return_kurtosis"] = kurtosis

    # H-1088: Up-Move Efficiency — avg return on up days / avg range on up days
    daily_range = (highs - lows) / closes
    up_eff = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        up_days = returns[col] > 0
        eff = pd.Series(index=closes.index, dtype=float)
        for i in range(30, len(closes)):
            mask = up_days.iloc[i-30:i]
            if mask.sum() < 5:
                continue
            avg_ret_up = returns[col].iloc[i-30:i][mask].mean()
            avg_range_up = daily_range[col].iloc[i-30:i][mask].mean()
            if avg_range_up > 0:
                eff.iloc[i] = avg_ret_up / avg_range_up
        up_eff[col] = eff
    signals["up_move_efficiency"] = up_eff

    # H-1089: Return Quantile Position — where current 5d return sits in 60d distribution
    ret_5d = returns.rolling(5).sum()
    quantile_pos = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        qp = pd.Series(index=closes.index, dtype=float)
        for i in range(65, len(closes)):
            current = ret_5d[col].iloc[i]
            history = ret_5d[col].iloc[i-60:i].dropna()
            if len(history) < 20 or np.isnan(current):
                continue
            qp.iloc[i] = (history < current).sum() / len(history)
        quantile_pos[col] = qp
    signals["return_quantile_pos"] = quantile_pos

    # H-1090: Consecutive Extreme Frequency — back-to-back |ret| > 1.5σ days
    consec_extreme = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        vol_20d = returns[col].rolling(20).std()
        is_extreme = (returns[col].abs() > 1.5 * vol_20d).astype(float)
        consecutive = (is_extreme * is_extreme.shift(1))
        consec_extreme[col] = consecutive.rolling(30).mean()
    signals["consec_extreme_freq"] = consec_extreme

    # H-1091: Overnight Return Share — (open-to-open return - close-to-close return) pattern
    overnight_ret = opens_ / closes.shift(1) - 1
    intraday_ret = closes / opens_ - 1
    overnight_share = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        total_abs = overnight_ret[col].abs().rolling(20).sum()
        overnight_abs = overnight_ret[col].rolling(20).sum()
        overnight_share[col] = overnight_abs / total_abs.clip(lower=1e-10)
    signals["overnight_share"] = overnight_share

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
    closes, volumes, highs, lows, opens_ = load_daily()
    print(f"Loaded {len(closes)} bars, {len(closes.columns)} assets")
    print()

    print("Computing signals...")
    signals = compute_signals(closes, volumes, highs, lows, opens_)
    print(f"Got {len(signals)} signal types")
    print()

    feature_map = {
        "H-1084": ("return_entropy", "Return Entropy (Shannon)"),
        "H-1085": ("pos_vol_ratio", "Positive Volume Ratio"),
        "H-1086": ("dd_recovery_speed", "DD Recovery Speed"),
        "H-1087": ("return_kurtosis", "Return Kurtosis (excess)"),
        "H-1088": ("up_move_efficiency", "Up-Move Efficiency"),
        "H-1089": ("return_quantile_pos", "Return Quantile Position"),
        "H-1090": ("consec_extreme_freq", "Consecutive Extreme Frequency"),
        "H-1091": ("overnight_share", "Overnight Return Share"),
    }

    results = {}
    lookback = 30

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
