"""
Batch backtest: H-1156 to H-1163 — Price Structure / Pattern Signals.
Converting price structure and technical pattern features into XS ranking signals.

H-1156: MA Convergence — (EMA20 - EMA50) / EMA50. Trend momentum via MA separation.
H-1157: New High Frequency — # of 20d highs in last 40 days. Persistent strength.
H-1158: Price Efficiency Ratio — net move / sum(|daily moves|) over 20d. Kaufman-style.
H-1159: Candle Body Ratio (5d avg) — |close - open| / (high - low). Conviction indicator.
H-1160: Upper Shadow Ratio (5d avg) — (high - max(open,close)) / (high - low). Selling pressure.
H-1161: Volume-Price Trend (VPT) — cumulative volume × pct change, ranked by 20d change.
H-1162: Acceleration — 5d ROC minus lagged 5d ROC. Second derivative of price.
H-1163: Overnight vs Intraday Ratio — (open_t - close_{t-1}) / (close_t - open_t). Session gap vs day move.
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

    # H-1156: MA Convergence — (EMA20 - EMA50) / EMA50
    ma_conv = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        ema20 = closes[col].ewm(span=20, adjust=False).mean()
        ema50 = closes[col].ewm(span=50, adjust=False).mean()
        ma_conv[col] = (ema20 - ema50) / ema50.clip(lower=1e-10)
    signals["ma_convergence"] = ma_conv

    # H-1157: New High Frequency — count of 20d highs in last 40 days
    nhf_df = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        rolling_max = closes[col].rolling(20).max()
        is_new_high = (closes[col] >= rolling_max).astype(float)
        nhf_df[col] = is_new_high.rolling(40).sum()
    signals["new_high_freq"] = nhf_df

    # H-1158: Price Efficiency Ratio — net / gross move over 20d
    eff_df = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        net_move = closes[col].diff(20).abs()
        daily_abs = closes[col].diff().abs()
        gross_move = daily_abs.rolling(20).sum()
        eff_df[col] = net_move / gross_move.clip(lower=1e-10)
    signals["price_efficiency"] = eff_df

    # H-1159: Candle Body Ratio (5d avg) — |close - open| / (high - low)
    body_ratio = (closes - opens).abs() / (highs - lows).clip(lower=1e-10)
    signals["body_ratio_5d"] = body_ratio.rolling(5).mean()

    # H-1160: Upper Shadow Ratio (5d avg) — selling pressure
    upper_shadow = highs - pd.concat([opens, closes], axis=1).max(level=0) if False else pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        max_oc = pd.concat([opens[col], closes[col]], axis=1).max(axis=1)
        us = (highs[col] - max_oc) / (highs[col] - lows[col]).clip(lower=1e-10)
        upper_shadow[col] = us
    signals["upper_shadow_5d"] = upper_shadow.rolling(5).mean()

    # H-1161: Volume-Price Trend (VPT) — 20d change in cumulative VPT
    vpt_df = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        pct = closes[col].pct_change()
        vpt_cum = (pct * volumes[col]).cumsum()
        vpt_df[col] = vpt_cum.diff(20)
    # Normalize by avg volume
    vol_20 = volumes.rolling(20).mean().clip(lower=1)
    signals["vpt_change"] = vpt_df / vol_20

    # H-1162: Acceleration — 5d ROC minus lagged 5d ROC (second derivative)
    roc5 = closes.pct_change(5)
    roc5_lag = roc5.shift(5)
    signals["acceleration"] = roc5 - roc5_lag

    # H-1163: Overnight vs Intraday Ratio
    on_df = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        overnight = (opens[col] - closes[col].shift(1)).abs()
        intraday = (closes[col] - opens[col]).abs()
        ratio = overnight / intraday.clip(lower=1e-10)
        on_df[col] = ratio.rolling(5).mean()
    signals["on_intra_ratio"] = on_df

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
        "H-1156": ("ma_convergence", "MA Convergence (EMA20/EMA50)"),
        "H-1157": ("new_high_freq", "New High Frequency (40d)"),
        "H-1158": ("price_efficiency", "Price Efficiency Ratio (20d)"),
        "H-1159": ("body_ratio_5d", "Candle Body Ratio (5d avg)"),
        "H-1160": ("upper_shadow_5d", "Upper Shadow Ratio (5d avg)"),
        "H-1161": ("vpt_change", "Volume-Price Trend Change (20d)"),
        "H-1162": ("acceleration", "Price Acceleration (5d-5d)"),
        "H-1163": ("on_intra_ratio", "Overnight/Intraday Ratio (5d avg)"),
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
