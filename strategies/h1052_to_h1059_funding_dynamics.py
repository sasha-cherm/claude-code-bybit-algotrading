"""
Batch backtest: H-1052 to H-1059 — Funding Rate Dynamics XS Signals.

H-1052: Funding Rate Velocity — rate of change of avg funding rate (momentum in sentiment)
H-1053: Funding Rate Dispersion — cross-asset std of funding rates (crowd disagreement)
H-1054: Funding Rate Mean Reversion — extreme high/low funding predicts reversal
H-1055: Funding-OI Interaction — funding × OI change (crowded trade detection)
H-1056: Funding Rate Rank Momentum — change in funding rate ranking over time
H-1057: Negative Funding Frequency — proportion of recent negative funding (bearish pressure)
H-1058: Funding Rate Volatility — rolling std of funding rate (uncertainty)
H-1059: Funding Rate Z-Score — normalized deviation from rolling mean
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


def load_data():
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


def load_funding():
    funding = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_USDT_funding.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            daily_fr = df["funding_rate"].resample("1D").sum()
            funding[f"{ticker}/USDT"] = daily_fr
        except:
            pass
    return pd.DataFrame(funding).sort_index().dropna(how="all")


def load_oi():
    oi = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_oi_daily.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            oi[f"{ticker}/USDT"] = df["openInterest"]
        except:
            pass
    return pd.DataFrame(oi).sort_index().dropna(how="all")


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
                 n_folds=6, test_days=100):
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


# ============================================================
# SIGNAL GENERATORS
# ============================================================

def funding_velocity(funding, short=5, long=20):
    """H-1052: Rate of change of rolling avg funding rate.
    Rising funding = growing bullish leverage → contrarian short."""
    short_ma = funding.rolling(short).mean()
    long_ma = funding.rolling(long).mean()
    return short_ma - long_ma


def funding_dispersion(funding, period=14):
    """H-1053: Cross-asset standard deviation of funding rates.
    High dispersion = disagreement → potential mean-reversion opportunity.
    Per-asset: distance from cross-sectional mean (signal for each asset)."""
    xs_mean = funding.rolling(period).mean().mean(axis=1)
    per_asset_mean = funding.rolling(period).mean()
    signal = per_asset_mean.sub(xs_mean, axis=0)
    return signal


def funding_mean_reversion(funding, period=20, threshold=2.0):
    """H-1054: Funding rate z-score from rolling window.
    Extreme positive funding → short (overleveraged), extreme negative → long."""
    rolling_mean = funding.rolling(period).mean()
    rolling_std = funding.rolling(period).std()
    rolling_std = rolling_std.replace(0, np.nan)
    zscore = (funding.rolling(5).mean() - rolling_mean) / rolling_std
    return -zscore  # negative z-score → long (contrarian)


def funding_oi_interaction(funding, oi, funding_period=14, oi_period=14):
    """H-1055: Funding × OI change interaction.
    High funding + rising OI = crowded trade → short (contrarian).
    Low funding + falling OI = capitulation → long."""
    funding_avg = funding.rolling(funding_period).mean()
    common_cols = [c for c in funding_avg.columns if c in oi.columns]
    if not common_cols:
        return pd.DataFrame()
    oi_change = oi[common_cols].pct_change(oi_period)
    funding_norm = funding_avg[common_cols].rank(axis=1, pct=True) - 0.5
    oi_norm = oi_change.rank(axis=1, pct=True) - 0.5
    common_idx = funding_norm.index.intersection(oi_norm.index)
    return -(funding_norm.loc[common_idx] * oi_norm.loc[common_idx])


def funding_rank_momentum(funding, short=7, long=30):
    """H-1056: Change in funding rate ranking over time.
    Asset whose funding rank rose (became more bullish) → contrarian short."""
    short_avg = funding.rolling(short).mean()
    long_avg = funding.rolling(long).mean()
    short_rank = short_avg.rank(axis=1, pct=True)
    long_rank = long_avg.rank(axis=1, pct=True)
    return -(short_rank - long_rank)


def negative_funding_freq(funding, period=30):
    """H-1057: Proportion of days with negative funding rate.
    High neg funding freq = persistent bearish pressure → contrarian long."""
    neg = (funding < 0).astype(float)
    neg_freq = neg.rolling(period).mean()
    return neg_freq  # high → long (contrarian: bearish pressure = buy signal)


def funding_volatility(funding, period=20):
    """H-1058: Rolling standard deviation of funding rate.
    High funding vol = uncertainty in positioning → follow momentum direction."""
    return funding.rolling(period).std()


def funding_zscore(funding, short=5, long=30):
    """H-1059: Normalized deviation from rolling mean.
    Extreme positive z-score → short (contrarian), extreme negative → long."""
    rolling_mean = funding.rolling(long).mean()
    rolling_std = funding.rolling(long).std()
    rolling_std = rolling_std.replace(0, np.nan)
    return -(funding.rolling(short).mean() - rolling_mean) / rolling_std


def run_signal(name, signal_df, closes, lookback, directions, n_ls_list=[4],
               rebal_list=[5, 7]):
    best = {"sharpe": -999}
    for direction in directions:
        for n_ls in n_ls_list:
            for rebal in rebal_list:
                pnl = xs_backtest(closes, signal_df, lookback, rebal, n_ls, direction)
                m = compute_metrics(pnl)
                if m["sharpe"] > best.get("sharpe", -999):
                    best = {**m, "direction": direction, "n_ls": n_ls, "rebal": rebal,
                            "pnl": pnl}
    if best["sharpe"] <= 0:
        print(f"  {name}: IS Sharpe {best.get('sharpe', 0):.3f} — SKIP (no positive)")
        return None
    pnl = best["pnl"]
    wf = walk_forward(closes, signal_df, lookback, best["rebal"], best["n_ls"],
                      best["direction"])
    sh1, sh2, p_val = split_half_test(pnl)
    corr = h012_correlation(closes, signal_df, lookback, best["rebal"], best["n_ls"],
                            best["direction"])
    wf_pos = sum(1 for x in wf if x > 0)
    print(f"  {name}: IS Sharpe {best['sharpe']:.3f} | Ann {best['annual_ret']:.1f}% | DD {best['max_dd']:.1f}% | "
          f"Dir={best['direction']} | WF {wf_pos}/{len(wf)} {wf} | SH {sh1:.3f}/{sh2:.3f} p={p_val:.3f} | "
          f"H012 corr {corr:.3f} | N={len(pnl)}")
    return {
        "sharpe": best["sharpe"], "annual_ret": best["annual_ret"],
        "max_dd": best["max_dd"], "direction": best["direction"],
        "n_ls": best["n_ls"], "rebal": best["rebal"],
        "wf": wf, "wf_pos": wf_pos, "wf_total": len(wf),
        "sh1": sh1, "sh2": sh2, "p_val": round(p_val, 4),
        "h012_corr": corr, "n_bars": len(pnl)
    }


def main():
    print("Loading data...")
    closes, volumes = load_data()
    funding = load_funding()
    oi = load_oi()

    common_idx = closes.index.intersection(funding.index)
    closes_f = closes.loc[common_idx]
    funding_f = funding.loc[common_idx]

    print(f"Closes: {closes.shape}, Funding: {funding.shape}, Common: {len(common_idx)} days")
    print(f"OI: {oi.shape}")
    print()

    results = {}

    # H-1052: Funding Rate Velocity
    print("H-1052: Funding Rate Velocity")
    sig = funding_velocity(funding_f)
    r = run_signal("H-1052", sig, closes_f, 20, ["high_long", "low_long"])
    if r: results["H-1052"] = r

    # H-1053: Funding Rate Dispersion
    print("H-1053: Funding Rate Dispersion")
    sig = funding_dispersion(funding_f)
    r = run_signal("H-1053", sig, closes_f, 14, ["high_long", "low_long"])
    if r: results["H-1053"] = r

    # H-1054: Funding Rate Mean Reversion
    print("H-1054: Funding Rate Mean Reversion")
    sig = funding_mean_reversion(funding_f)
    r = run_signal("H-1054", sig, closes_f, 20, ["high_long", "low_long"])
    if r: results["H-1054"] = r

    # H-1055: Funding-OI Interaction
    print("H-1055: Funding-OI Interaction")
    sig = funding_oi_interaction(funding_f, oi)
    if len(sig) > 0:
        common_idx2 = closes.index.intersection(sig.index)
        closes_foi = closes[sig.columns].loc[common_idx2] if len(sig.columns) > 0 else closes.loc[common_idx2]
        r = run_signal("H-1055", sig.loc[common_idx2], closes_foi, 14, ["high_long", "low_long"])
        if r: results["H-1055"] = r
    else:
        print("  H-1055: No common columns — SKIP")

    # H-1056: Funding Rate Rank Momentum
    print("H-1056: Funding Rate Rank Momentum")
    sig = funding_rank_momentum(funding_f)
    r = run_signal("H-1056", sig, closes_f, 30, ["high_long", "low_long"])
    if r: results["H-1056"] = r

    # H-1057: Negative Funding Frequency
    print("H-1057: Negative Funding Frequency")
    sig = negative_funding_freq(funding_f)
    r = run_signal("H-1057", sig, closes_f, 30, ["high_long", "low_long"])
    if r: results["H-1057"] = r

    # H-1058: Funding Rate Volatility
    print("H-1058: Funding Rate Volatility")
    sig = funding_volatility(funding_f)
    r = run_signal("H-1058", sig, closes_f, 20, ["high_long", "low_long"])
    if r: results["H-1058"] = r

    # H-1059: Funding Rate Z-Score
    print("H-1059: Funding Rate Z-Score")
    sig = funding_zscore(funding_f)
    r = run_signal("H-1059", sig, closes_f, 30, ["high_long", "low_long"])
    if r: results["H-1059"] = r

    print(f"\n{'='*80}")
    print(f"BATCH SUMMARY: {len(results)}/{8} signals with positive IS Sharpe")
    for name, r in sorted(results.items(), key=lambda x: -x[1]["sharpe"]):
        status = "CONFIRMED" if r["wf_pos"] >= max(2, r["wf_total"] * 0.5) and r["p_val"] < 0.1 else "BORDERLINE" if r["wf_pos"] >= 2 else "REJECTED"
        print(f"  {name}: Sharpe {r['sharpe']:.3f} | WF {r['wf_pos']}/{r['wf_total']} | p={r['p_val']:.3f} | corr {r['h012_corr']:.3f} | {status}")


if __name__ == "__main__":
    main()
