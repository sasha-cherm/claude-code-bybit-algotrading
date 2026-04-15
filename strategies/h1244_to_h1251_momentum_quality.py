"""
Batch backtest: H-1244 to H-1251 — Momentum Quality & Path Shape Signals.
Cross-sectional signals based on how momentum is structured (quality, breadth, shape).

H-1244: Momentum IR — 60d return / std(daily returns over 60d). Quality-adjusted momentum.
H-1245: Win Ratio — fraction of positive-return days in 60d. Up-day breadth.
H-1246: Trend Monotonicity — Spearman corr between day-index and cumulative return over 30d.
H-1247: Info Discreteness — fraction of days where sign(ret) matches sign(cumulative 60d ret).
H-1248: Max Excursion Asymmetry — max drawup / max drawdown over 30d. Upside vs downside path.
H-1249: Momentum Divergence — rank(30d ret) - rank(60d ret). Cross-timeframe disagreement.
H-1250: Avg Positive Return — mean of only positive daily returns in 30d. Up-day quality.
H-1251: Crash Frequency — number of >3% decline days in 60d. Tail risk frequency.
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

    # H-1244: Momentum IR — 60d return / std(daily returns, 60d)
    ret60 = closes.pct_change(60)
    roll_std = returns.rolling(60).std()
    signals["mom_ir"] = ret60 / (roll_std + 1e-10)

    # H-1245: Win Ratio — fraction of positive days in 60d
    pos_days = (returns > 0).astype(float).rolling(60).mean()
    signals["win_ratio"] = pos_days

    # H-1246: Trend Monotonicity — Spearman corr(index, cum_ret) over 30d
    mono = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        idx_arr = np.arange(30)
        for i in range(30, len(r)):
            rv = r[i-30:i]
            if np.sum(np.isfinite(rv)) < 20:
                continue
            cum = np.nancumsum(rv)
            mask = np.isfinite(cum)
            if mask.sum() < 20:
                continue
            corr, _ = stats.spearmanr(idx_arr[mask], cum[mask])
            out[i] = corr
        mono[col] = out
    signals["trend_mono"] = mono

    # H-1247: Info Discreteness — frac days where sign(ret) = sign(cum 60d ret)
    disc = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        r60 = ret60[col].values if col in ret60.columns else np.full(len(r), np.nan)
        out = np.full(len(r), np.nan)
        for i in range(60, len(r)):
            cum_sign = np.sign(r60[i]) if np.isfinite(r60[i]) else 0
            if cum_sign == 0:
                continue
            rv = r[i-60:i]
            mask = np.isfinite(rv) & (rv != 0)
            if mask.sum() < 30:
                continue
            same_sign = np.sum(np.sign(rv[mask]) == cum_sign)
            out[i] = same_sign / mask.sum()
        disc[col] = out
    signals["info_discrete"] = disc

    # H-1248: Max Excursion Asymmetry — max drawup / max drawdown over 30d
    mea = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(30, len(r)):
            rv = r[i-30:i]
            if np.sum(np.isfinite(rv)) < 20:
                continue
            cum = np.nancumsum(rv)
            running_min = np.minimum.accumulate(cum)
            running_max = np.maximum.accumulate(cum)
            max_drawup = np.max(cum - running_min)
            max_drawdown = abs(np.min(cum - running_max))
            out[i] = max_drawup / (max_drawdown + 1e-10)
        mea[col] = out
    signals["max_excursion_asym"] = mea

    # H-1249: Momentum Divergence — rank(30d ret) - rank(60d ret)
    ret30 = closes.pct_change(30)
    rank30 = ret30.rank(axis=1, pct=True)
    rank60 = ret60.rank(axis=1, pct=True)
    signals["mom_divergence"] = rank30 - rank60

    # H-1250: Avg Positive Return — mean of positive daily returns over 30d
    apr = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(30, len(r)):
            rv = r[i-30:i]
            mask = np.isfinite(rv) & (rv > 0)
            if mask.sum() > 0:
                out[i] = np.mean(rv[mask])
        apr[col] = out
    signals["avg_pos_ret"] = apr

    # H-1251: Crash Frequency — number of >3% decline days in 60d
    crash_days = (returns < -0.03).astype(float).rolling(60).sum()
    signals["crash_freq"] = crash_days

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
        "H-1244": ("mom_ir", "Momentum IR (60d ret / std daily rets)"),
        "H-1245": ("win_ratio", "Win Ratio (frac positive days, 60d)"),
        "H-1246": ("trend_mono", "Trend Monotonicity (Spearman corr index vs cum-ret, 30d)"),
        "H-1247": ("info_discrete", "Info Discreteness (frac days same sign as 60d cum ret)"),
        "H-1248": ("max_excursion_asym", "Max Excursion Asymmetry (max drawup / max DD, 30d)"),
        "H-1249": ("mom_divergence", "Momentum Divergence (rank(30d) - rank(60d))"),
        "H-1250": ("avg_pos_ret", "Avg Positive Return (mean up-day return, 30d)"),
        "H-1251": ("crash_freq", "Crash Frequency (# of >3% down days, 60d)"),
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
