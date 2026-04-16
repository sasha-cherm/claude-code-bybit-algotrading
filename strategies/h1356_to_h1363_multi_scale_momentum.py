"""
Batch backtest: H-1356 to H-1363 — Multi-Scale Momentum.
Signals that combine price/volume behavior across multiple timeframes to create richer signals.

H-1356: Short-Long Momentum Gap — (5d return / 5d std) - (20d return / 20d std). Normalized momentum divergence across scales.
H-1357: Momentum Decay Profile — 5d ret / 20d ret. >1 = recent acceleration, <1 = fading momentum.
H-1358: Multi-Horizon Rank Consistency — avg rank(5d ret) + rank(10d ret) + rank(20d ret). Consistent high-ranker = strong.
H-1359: Horizon-Weighted Momentum — 0.5 * z(5d) + 0.3 * z(10d) + 0.2 * z(20d). Recency-weighted z-score combo.
H-1360: Trend Agreement — sign(5d ret) + sign(10d ret) + sign(20d ret). All positive = strong trend.
H-1361: Fast-Slow Volume Divergence — (5d avg vol / 20d avg vol) - (5d ret / 20d ret). Volume expanding faster than price.
H-1362: Multi-Scale Reversal Score — sum of (close - MA_k) / MA_k for k in [5,10,20]. Distance from multiple MAs.
H-1363: Lookback Stability — std of [5d ret, 10d ret, 15d ret, 20d ret]. Low = consistent across horizons.
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
    signals = {}

    ret5 = closes.pct_change(5)
    ret10 = closes.pct_change(10)
    ret20 = closes.pct_change(20)
    std5 = returns.rolling(5).std().replace(0, np.nan)
    std20 = returns.rolling(20).std().replace(0, np.nan)

    # H-1356: Short-Long Momentum Gap (risk-adjusted)
    sharpe5 = ret5 / (std5 * np.sqrt(5)).replace(0, np.nan)
    sharpe20 = ret20 / (std20 * np.sqrt(20)).replace(0, np.nan)
    signals["sl_mom_gap"] = sharpe5 - sharpe20

    # H-1357: Momentum Decay Profile
    safe_ret20 = ret20.replace(0, np.nan)
    signals["mom_decay"] = ret5 / safe_ret20

    # H-1358: Multi-Horizon Rank Consistency
    def xs_rank(df):
        return df.rank(axis=1, pct=True)
    rank5 = xs_rank(ret5)
    rank10 = xs_rank(ret10)
    rank20 = xs_rank(ret20)
    signals["rank_consistency"] = (rank5 + rank10 + rank20) / 3

    # H-1359: Horizon-Weighted Momentum (z-score combo)
    def xs_zscore(df):
        mu = df.mean(axis=1)
        sigma = df.std(axis=1).replace(0, np.nan)
        return df.sub(mu, axis=0).div(sigma, axis=0)
    z5 = xs_zscore(ret5)
    z10 = xs_zscore(ret10)
    z20 = xs_zscore(ret20)
    signals["hz_weighted_mom"] = 0.5 * z5 + 0.3 * z10 + 0.2 * z20

    # H-1360: Trend Agreement
    sign5 = np.sign(ret5)
    sign10 = np.sign(ret10)
    sign20 = np.sign(ret20)
    signals["trend_agreement"] = sign5 + sign10 + sign20

    # H-1361: Fast-Slow Volume Divergence
    avg_vol5 = volumes.rolling(5).mean()
    avg_vol20 = volumes.rolling(20).mean().replace(0, np.nan)
    vol_ratio = avg_vol5 / avg_vol20
    safe_ret20_for_div = ret20.replace(0, np.nan)
    ret_ratio = ret5 / safe_ret20_for_div
    signals["fast_slow_vol_div"] = vol_ratio - ret_ratio

    # H-1362: Multi-Scale Reversal Score
    ma5 = closes.rolling(5).mean()
    ma10 = closes.rolling(10).mean()
    ma20 = closes.rolling(20).mean()
    dist5 = (closes - ma5) / ma5.replace(0, np.nan)
    dist10 = (closes - ma10) / ma10.replace(0, np.nan)
    dist20 = (closes - ma20) / ma20.replace(0, np.nan)
    signals["multi_scale_reversal"] = dist5 + dist10 + dist20

    # H-1363: Lookback Stability
    ret15 = closes.pct_change(15)
    lb_stab = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        stacked = pd.concat([ret5[col], ret10[col], ret15[col], ret20[col]], axis=1)
        lb_stab[col] = stacked.std(axis=1)
    signals["lookback_stability"] = lb_stab

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
    non_null = signal_df.dropna(how='all')
    if len(non_null) == 0:
        print(f"  {name}: DEGENERATE — no valid rows")
        return True
    last_row = non_null.iloc[-1].dropna()
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
    opens, highs, lows, closes, volumes = load_daily_ohlcv()
    print(f"Loaded {len(closes)} bars, {len(closes.columns)} assets")
    print()

    print("Computing signals...")
    signals, closes = compute_signals(opens, highs, lows, closes, volumes)
    print(f"Got {len(signals)} signal types")
    print()

    feature_map = {
        "H-1356": ("sl_mom_gap", "Short-Long Momentum Gap (risk-adj 5d minus 20d)"),
        "H-1357": ("mom_decay", "Momentum Decay Profile (5d ret / 20d ret ratio)"),
        "H-1358": ("rank_consistency", "Multi-Horizon Rank Consistency (avg rank across 5/10/20d)"),
        "H-1359": ("hz_weighted_mom", "Horizon-Weighted Momentum (0.5*z5 + 0.3*z10 + 0.2*z20)"),
        "H-1360": ("trend_agreement", "Trend Agreement (sign sum across 5/10/20d)"),
        "H-1361": ("fast_slow_vol_div", "Fast-Slow Volume Divergence (vol ratio minus ret ratio)"),
        "H-1362": ("multi_scale_reversal", "Multi-Scale Reversal Score (sum dist from MA5/10/20)"),
        "H-1363": ("lookback_stability", "Lookback Stability (std of returns across 5/10/15/20d)"),
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
