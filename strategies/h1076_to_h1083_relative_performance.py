"""
Batch backtest: H-1076 to H-1083 — Relative Performance Dynamics.
XS signals derived from how assets perform relative to peers over time.

H-1076: Rank Persistence — autocorrelation of asset's XS return rank over trailing windows
H-1077: Rank Change Momentum — change in XS return rank (improving vs deteriorating)
H-1078: Outperformance Consistency — fraction of trailing days where asset beat XS median
H-1079: Pairwise Dominance Count — number of other assets beaten over trailing window
H-1080: Catch-Up Factor — ratio of recent 5d return rank to 30d return rank
H-1081: Relative Volume Surprise — asset's volume change vs XS volume change
H-1082: Rank Volatility — std dev of asset's XS rank over trailing period
H-1083: XS Distance from Median — avg daily distance from XS median return
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
    """Compute all 8 signals from daily close/volume data."""
    returns = closes.pct_change()
    n_assets = len(closes.columns)

    # Compute daily XS ranks (1 = best return, N = worst)
    daily_ranks = returns.rank(axis=1, ascending=False)

    signals = {}

    # H-1076: Rank Persistence — autocorrelation of daily rank over 20d windows
    rank_persist = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        rank_persist[col] = daily_ranks[col].rolling(20).apply(
            lambda x: x.autocorr() if len(x.dropna()) > 10 else np.nan, raw=False)
    signals["rank_persistence"] = rank_persist

    # H-1077: Rank Change Momentum — rank(t-1d avg over 5d) - rank(t-10d avg over 5d)
    rank_5d = daily_ranks.rolling(5).mean()
    rank_change = rank_5d - rank_5d.shift(10)
    signals["rank_change_mom"] = rank_change

    # H-1078: Outperformance Consistency — fraction of trailing 20d where ret > XS median
    xs_median = returns.median(axis=1)
    outperf = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        above_median = (returns[col] > xs_median).astype(float)
        outperf[col] = above_median.rolling(20).mean()
    signals["outperf_consistency"] = outperf

    # H-1079: Pairwise Dominance — fraction of other assets beaten over trailing 20d return
    ret_20d = returns.rolling(20).sum()
    dominance = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i, date in enumerate(closes.index):
        if i < 25:
            continue
        row = ret_20d.iloc[i].dropna()
        if len(row) < 6:
            continue
        for col in row.index:
            dominance.loc[date, col] = (row < row[col]).sum() / (len(row) - 1)
    signals["pairwise_dominance"] = dominance

    # H-1080: Catch-Up Factor — 5d return rank / 30d return rank
    ret_5d = returns.rolling(5).sum()
    ret_30d = returns.rolling(30).sum()
    rank_5d_ret = ret_5d.rank(axis=1, ascending=False)
    rank_30d_ret = ret_30d.rank(axis=1, ascending=False)
    catch_up = rank_30d_ret / rank_5d_ret.clip(lower=0.5)
    signals["catch_up"] = catch_up

    # H-1081: Relative Volume Surprise — asset's 5d/20d volume ratio minus XS mean of same
    vol_ratio = volumes.rolling(5).mean() / volumes.rolling(20).mean()
    xs_vol_mean = vol_ratio.mean(axis=1)
    rel_vol_surprise = vol_ratio.sub(xs_vol_mean, axis=0)
    signals["rel_vol_surprise"] = rel_vol_surprise

    # H-1082: Rank Volatility — std dev of daily XS rank over trailing 20d
    rank_vol = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        rank_vol[col] = daily_ranks[col].rolling(20).std()
    signals["rank_volatility"] = rank_vol

    # H-1083: XS Distance from Median — avg |ret - XS median| with sign preserved
    dist_from_median = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        signed_dist = returns[col] - xs_median
        dist_from_median[col] = signed_dist.rolling(20).mean()
    signals["xs_dist_median"] = dist_from_median

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
        "H-1076": ("rank_persistence", "Rank Persistence (XS rank autocorrelation)"),
        "H-1077": ("rank_change_mom", "Rank Change Momentum"),
        "H-1078": ("outperf_consistency", "Outperformance Consistency"),
        "H-1079": ("pairwise_dominance", "Pairwise Dominance Count"),
        "H-1080": ("catch_up", "Catch-Up Factor (5d vs 30d rank)"),
        "H-1081": ("rel_vol_surprise", "Relative Volume Surprise"),
        "H-1082": ("rank_volatility", "Rank Volatility"),
        "H-1083": ("xs_dist_median", "XS Distance from Median"),
    }

    results = {}
    lookback = 20

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
