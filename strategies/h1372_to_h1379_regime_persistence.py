"""
Batch backtest: H-1372 to H-1379 — Regime Persistence & Transition Signals.
Signals capturing whether an asset's current regime is likely to continue or flip.

H-1372: Mean Persistence — |mean(recent 20d) - mean(prior 20d)| / std. Small = stable regime.
H-1373: Sign Persistence — fraction of 30d where daily sign matches rolling mean sign.
H-1374: Trend Stability — std of daily slope estimates across rolling 10d windows in 60d.
H-1375: Volatility Persistence — std of rolling 10d vol across 60d (low = stable vol regime).
H-1376: Regime Flip Count — count of sign changes in rolling mean over 60d.
H-1377: Price Stability Index — std of price / mean price (60d CV, inverted).
H-1378: Return Stability — IQR(30d) / range(30d). High = stable.
H-1379: Momentum Lifecycle — days since last 20d-mean sign flipped.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats as scipy_stats

DATA_DIR = Path("data")
FEE_RATE = 0.00055
SLIPPAGE_BPS = 2

ASSETS = ["BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX", "LINK",
          "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM"]


def load_daily_ohlcv():
    frames = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_1d.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            frames[f"{ticker}/USDT"] = df
        except:
            pass
    closes, volumes = {}, {}
    for sym, df in frames.items():
        closes[sym] = df["close"]
        volumes[sym] = df["volume"] * df["close"]
    idx = sorted(set.intersection(*[set(df.index) for df in frames.values()]))
    closes = pd.DataFrame(closes).loc[idx]
    volumes = pd.DataFrame(volumes).loc[idx]
    return closes, volumes


def compute_signals(closes, volumes):
    returns = closes.pct_change()
    signals = {}

    # H-1372: Mean Persistence (|delta mean| / std) — low = stable regime
    mean_recent = returns.rolling(20).mean()
    mean_prior = returns.shift(20).rolling(20).mean()
    std_60 = returns.rolling(60).std()
    signals["mean_persistence"] = (mean_recent - mean_prior).abs() / std_60.replace(0, np.nan)

    # H-1373: Sign Persistence — frac of days matching rolling mean sign in 30d
    def sign_persist(series, window=30):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            chunk = series.iloc[i-window:i].values
            valid = chunk[np.isfinite(chunk)]
            if len(valid) < 10:
                continue
            mu = np.mean(valid)
            if mu == 0:
                continue
            match = np.sign(valid) == np.sign(mu)
            result.iloc[i] = np.mean(match)
        return result

    signals["sign_persist"] = returns.apply(lambda col: sign_persist(col, 30))

    # H-1374: Trend Stability — std of 10d slopes across 60d
    def slope_stability(series, short=10, long=60):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(long, len(series)):
            chunk = series.iloc[i-long:i].values
            valid = chunk[np.isfinite(chunk)]
            if len(valid) < long:
                continue
            slopes = []
            for j in range(short, long + 1):
                sub = valid[j-short:j]
                x = np.arange(short)
                if np.std(sub) > 0:
                    slope = np.polyfit(x, sub, 1)[0]
                    slopes.append(slope)
            if len(slopes) > 5:
                result.iloc[i] = np.std(slopes)
        return result

    signals["trend_stability"] = returns.apply(lambda col: slope_stability(col, 10, 60))

    # H-1375: Vol Persistence — std of rolling 10d vol across 60d
    vol_10 = returns.rolling(10).std()
    signals["vol_persistence"] = vol_10.rolling(60).std()

    # H-1376: Regime Flip Count — count of sign changes in 20d rolling mean across 60d
    mean_20 = returns.rolling(20).mean()
    sign_diff = (np.sign(mean_20) != np.sign(mean_20.shift(1))).astype(float)
    signals["regime_flip_count"] = sign_diff.rolling(60).sum()

    # H-1377: Price Stability Index — 60d CV (std / mean) of close
    price_mean = closes.rolling(60).mean()
    price_std = closes.rolling(60).std()
    signals["price_cv"] = price_std / price_mean.replace(0, np.nan)

    # H-1378: Return Stability — IQR / range in 30d
    iqr = returns.rolling(30).quantile(0.75) - returns.rolling(30).quantile(0.25)
    rng = returns.rolling(30).max() - returns.rolling(30).min()
    signals["return_stability"] = iqr / rng.replace(0, np.nan)

    # H-1379: Momentum Lifecycle — days since last sign flip of 20d mean
    def days_since_flip(series, window=20, max_look=60):
        result = pd.Series(index=series.index, dtype=float)
        mean = series.rolling(window).mean()
        for i in range(window + 1, len(series)):
            cur_sign = np.sign(mean.iloc[i])
            days = 0
            for j in range(i-1, max(i - max_look, window), -1):
                if np.sign(mean.iloc[j]) != cur_sign:
                    break
                days += 1
            result.iloc[i] = days
        return result

    signals["mom_lifecycle"] = returns.apply(lambda col: days_since_flip(col, 20, 60))

    return signals, closes


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
            sig_row = signal_df.iloc[i - 1].dropna()
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
    t_stat, p_val = scipy_stats.ttest_1samp(pnl, 0)
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


def check_degenerate(signal_df, name):
    last_row = signal_df.dropna(how='all').iloc[-1].dropna()
    if len(last_row) < 8:
        return False
    nunique = last_row.nunique()
    if nunique <= 3:
        print(f"  {name}: DEGENERATE — only {nunique} unique values in last row")
        return True
    val_counts = last_row.value_counts()
    if val_counts.iloc[0] >= len(last_row) * 0.5:
        print(f"  {name}: DEGENERATE — {val_counts.iloc[0]}/{len(last_row)} assets have same value")
        return True
    return False


def run_signal(name, signal_df, closes, lookback, directions, n_ls_list=[4],
               rebal_list=[5, 7]):
    common_idx = closes.index.intersection(signal_df.index)
    common_cols = [c for c in closes.columns if c in signal_df.columns]
    if len(common_cols) < 8 or len(common_idx) < 200:
        print(f"  {name}: Insufficient data — SKIP")
        return None
    closes_c = closes[common_cols].loc[common_idx]
    signal_c = signal_df[common_cols].loc[common_idx]
    if check_degenerate(signal_c, name):
        return None
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
    print("Loading OHLCV data...")
    closes, volumes = load_daily_ohlcv()
    print(f"Loaded {len(closes)} bars, {len(closes.columns)} assets")
    print()

    print("Computing signals...")
    signals, closes = compute_signals(closes, volumes)
    print(f"Got {len(signals)} signal types")
    print()

    feature_map = {
        "H-1372": ("mean_persistence", "Mean Persistence (|delta mean|/std)"),
        "H-1373": ("sign_persist", "Sign Persistence (frac matching mean sign)"),
        "H-1374": ("trend_stability", "Trend Stability (std of 10d slopes in 60d)"),
        "H-1375": ("vol_persistence", "Vol Persistence (std of 10d vol in 60d)"),
        "H-1376": ("regime_flip_count", "Regime Flip Count (sign changes in 60d)"),
        "H-1377": ("price_cv", "Price CV 60d (std/mean close)"),
        "H-1378": ("return_stability", "Return Stability (IQR/range in 30d)"),
        "H-1379": ("mom_lifecycle", "Momentum Lifecycle (days since sign flip)"),
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
