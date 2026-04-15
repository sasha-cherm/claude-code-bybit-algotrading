"""
Batch backtest: H-1300 to H-1307 — Return Autocorrelation Dynamics.
How serial dependence in returns varies cross-sectionally.

H-1300: Return Autocorrelation (lag 1) — corr(ret_t, ret_{t-1}) over 20d. Momentum/MR tendency.
H-1301: Absolute Return Persistence — corr(|ret_t|, |ret_{t-1}|) over 20d. Vol clustering strength.
H-1302: Sign Persistence — fraction of consecutive same-sign returns in 20d. Trend streakiness.
H-1303: Partial Autocorrelation (lag 2) — PACF at lag 2 removing lag 1. Second-order structure.
H-1304: Return Predictability Ratio — R² of AR(1) on returns over 40d. How predictable returns are.
H-1305: Mean Reversion Speed — half-life of AR(1) in log prices over 60d. How fast prices revert.
H-1306: Runs Test Z-score — z-score from Wald-Wolfowitz runs test on return signs, 40d. Tests randomness.
H-1307: Cross-autocorrelation — corr(ret_t, market_ret_{t-1}) over 20d. Lead-lag with market.
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
    opens, highs, lows, closes, volumes = {}, {}, {}, {}, {}
    for sym, df in frames.items():
        opens[sym] = df["open"]
        highs[sym] = df["high"]
        lows[sym] = df["low"]
        closes[sym] = df["close"]
        volumes[sym] = df["volume"] * df["close"]
    idx = sorted(set.intersection(*[set(df.index) for df in frames.values()]))
    opens = pd.DataFrame(opens).loc[idx]
    highs = pd.DataFrame(highs).loc[idx]
    lows = pd.DataFrame(lows).loc[idx]
    closes = pd.DataFrame(closes).loc[idx]
    volumes = pd.DataFrame(volumes).loc[idx]
    return opens, highs, lows, closes, volumes


def compute_signals(opens, highs, lows, closes, volumes):
    returns = closes.pct_change()
    mkt_ret = returns.mean(axis=1)
    signals = {}

    # H-1300: Return Autocorrelation (lag 1) over 20d
    def rolling_acf1(series, window=20):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window + 1, len(series)):
            x = series.iloc[i-window:i].values
            x_lag = series.iloc[i-window-1:i-1].values
            if np.std(x) < 1e-15 or np.std(x_lag) < 1e-15:
                result.iloc[i] = 0
                continue
            result.iloc[i] = np.corrcoef(x, x_lag)[0, 1]
        return result

    signals["ret_acf1"] = returns.apply(lambda col: rolling_acf1(col, 20))

    # H-1301: Absolute Return Persistence
    abs_ret = returns.abs()
    signals["abs_ret_persist"] = abs_ret.apply(lambda col: rolling_acf1(col, 20))

    # H-1302: Sign Persistence — fraction of same-sign consecutive pairs
    def sign_persistence(series, window=20):
        result = pd.Series(index=series.index, dtype=float)
        signs = np.sign(series)
        for i in range(window + 1, len(series)):
            s = signs.iloc[i-window:i].values
            s_lag = signs.iloc[i-window-1:i-1].values
            same = np.sum(s == s_lag)
            result.iloc[i] = same / window
        return result

    signals["sign_persist"] = returns.apply(lambda col: sign_persistence(col, 20))

    # H-1303: Partial Autocorrelation at lag 2
    def rolling_pacf2(series, window=40):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            chunk = series.iloc[i-window:i].values
            if np.std(chunk) < 1e-15:
                result.iloc[i] = 0
                continue
            try:
                x = chunk[2:]
                x1 = chunk[1:-1]
                x2 = chunk[:-2]
                A = np.column_stack([x1, x2, np.ones(len(x))])
                coeffs = np.linalg.lstsq(A, x, rcond=None)[0]
                result.iloc[i] = coeffs[1]
            except:
                result.iloc[i] = 0
        return result

    signals["pacf_lag2"] = returns.apply(lambda col: rolling_pacf2(col, 40))

    # H-1304: Return Predictability Ratio — R² of AR(1)
    def rolling_ar1_r2(series, window=40):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window + 1, len(series)):
            y = series.iloc[i-window:i].values
            x = series.iloc[i-window-1:i-1].values
            if np.std(x) < 1e-15:
                result.iloc[i] = 0
                continue
            slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, y)
            result.iloc[i] = r_value ** 2
        return result

    signals["ret_predictability"] = returns.apply(lambda col: rolling_ar1_r2(col, 40))

    # H-1305: Mean Reversion Speed — AR(1) coefficient on log prices
    log_prices = np.log(closes)
    def rolling_ar1_coeff(series, window=60):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            y = series.iloc[i-window+1:i+1].values
            x = series.iloc[i-window:i].values
            if np.std(x) < 1e-15:
                result.iloc[i] = 1.0
                continue
            slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, y)
            result.iloc[i] = slope
        return result

    signals["mr_speed"] = log_prices.apply(lambda col: rolling_ar1_coeff(col, 60))

    # H-1306: Runs Test Z-score — tests departure from randomness
    def runs_test_z(series, window=40):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window, len(series)):
            chunk = series.iloc[i-window:i].values
            signs = (chunk > 0).astype(int)
            n_pos = np.sum(signs)
            n_neg = window - n_pos
            if n_pos < 2 or n_neg < 2:
                result.iloc[i] = 0
                continue
            runs = 1
            for j in range(1, len(signs)):
                if signs[j] != signs[j-1]:
                    runs += 1
            expected = 1 + 2 * n_pos * n_neg / window
            var = 2 * n_pos * n_neg * (2 * n_pos * n_neg - window) / (window ** 2 * (window - 1))
            if var <= 0:
                result.iloc[i] = 0
                continue
            result.iloc[i] = (runs - expected) / np.sqrt(var)
        return result

    signals["runs_z"] = returns.apply(lambda col: runs_test_z(col, 40))

    # H-1307: Cross-autocorrelation with market return
    def rolling_cross_acf(series, mkt, window=20):
        result = pd.Series(index=series.index, dtype=float)
        for i in range(window + 1, len(series)):
            x = series.iloc[i-window:i].values
            m_lag = mkt.iloc[i-window-1:i-1].values
            if np.std(x) < 1e-15 or np.std(m_lag) < 1e-15:
                result.iloc[i] = 0
                continue
            result.iloc[i] = np.corrcoef(x, m_lag)[0, 1]
        return result

    signals["cross_acf"] = returns.apply(lambda col: rolling_cross_acf(col, mkt_ret, 20))

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
    print("Loading OHLCV data...")
    opens, highs, lows, closes, volumes = load_daily_ohlcv()
    print(f"Loaded {len(closes)} bars, {len(closes.columns)} assets")
    print()

    print("Computing signals...")
    signals, closes = compute_signals(opens, highs, lows, closes, volumes)
    print(f"Got {len(signals)} signal types")
    print()

    feature_map = {
        "H-1300": ("ret_acf1", "Return Autocorrelation lag 1 (20d)"),
        "H-1301": ("abs_ret_persist", "Absolute Return Persistence (autocorr |ret|, 20d)"),
        "H-1302": ("sign_persist", "Sign Persistence (same-sign fraction, 20d)"),
        "H-1303": ("pacf_lag2", "Partial Autocorrelation lag 2 (40d)"),
        "H-1304": ("ret_predictability", "Return Predictability R² (AR(1) R², 40d)"),
        "H-1305": ("mr_speed", "Mean Reversion Speed (AR(1) coeff on log price, 60d)"),
        "H-1306": ("runs_z", "Runs Test Z-score (randomness test, 40d)"),
        "H-1307": ("cross_acf", "Cross-autocorrelation with Market (20d)"),
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
