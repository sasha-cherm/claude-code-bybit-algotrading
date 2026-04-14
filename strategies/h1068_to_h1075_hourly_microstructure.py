"""
Batch backtest: H-1068 to H-1075 — Hourly Microstructure XS Signals.
Uses 1h data aggregated to daily features for cross-sectional ranking.

H-1068: Intraday Volatility Ratio — day session vs night session vol ratio
H-1069: Hourly Return Autocorrelation — persistence within the day
H-1070: Volume-Weighted Return — intraday VWAP return efficiency
H-1071: Hourly Range Expansion — max hourly range / avg hourly range
H-1072: Session Momentum — Asian vs US session return differential
H-1073: Intraday Mean Reversion Speed — how fast do intraday moves revert
H-1074: Volume Clock — proportion of volume in first vs second half of day
H-1075: Close Location Value Intraday — intraday CLV trend
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


def load_hourly(ticker):
    try:
        df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_1h.parquet")
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df
    except:
        return None


def compute_hourly_features():
    """Compute daily features from hourly data for each asset."""
    features = {}

    for ticker in ASSETS:
        sym = f"{ticker}/USDT"
        df = load_hourly(ticker)
        if df is None or len(df) < 500:
            continue

        df["hour"] = df.index.hour
        df["date"] = df.index.date
        df["ret"] = df["close"].pct_change()
        df["range"] = (df["high"] - df["low"]) / df["close"]
        df["dollar_vol"] = df["volume"] * df["close"]

        daily_feats = {}

        for date, group in df.groupby("date"):
            if len(group) < 20:
                continue

            # Day session: 08-20 UTC, Night: 20-08 UTC
            day_mask = (group["hour"] >= 8) & (group["hour"] < 20)
            night_mask = ~day_mask

            day_vol = group.loc[day_mask, "range"].std() if day_mask.sum() > 3 else np.nan
            night_vol = group.loc[night_mask, "range"].std() if night_mask.sum() > 3 else np.nan

            # H-1068: Day/Night vol ratio
            vol_ratio = day_vol / night_vol if night_vol and night_vol > 0 else np.nan

            # H-1069: Hourly return autocorrelation
            rets = group["ret"].dropna()
            autocorr = rets.autocorr() if len(rets) > 10 else np.nan

            # H-1070: Volume-weighted return
            if group["dollar_vol"].sum() > 0:
                vw_ret = (group["ret"] * group["dollar_vol"]).sum() / group["dollar_vol"].sum()
            else:
                vw_ret = np.nan

            # H-1071: Hourly range expansion
            ranges = group["range"].dropna()
            range_exp = ranges.max() / ranges.mean() if ranges.mean() > 0 else np.nan

            # H-1072: Asian (00-08) vs US (14-22) session return
            asian = group.loc[(group["hour"] >= 0) & (group["hour"] < 8)]
            us = group.loc[(group["hour"] >= 14) & (group["hour"] < 22)]
            asian_ret = asian["ret"].sum() if len(asian) > 3 else np.nan
            us_ret = us["ret"].sum() if len(us) > 3 else np.nan
            session_diff = us_ret - asian_ret if (asian_ret is not np.nan and us_ret is not np.nan) else np.nan

            # H-1073: Intraday mean reversion speed
            cum_rets = rets.cumsum()
            if len(cum_rets) > 5:
                peak_idx = cum_rets.abs().idxmax()
                peak_pos = list(cum_rets.index).index(peak_idx)
                after_peak = cum_rets.iloc[peak_pos:]
                reversion = abs(after_peak.iloc[-1] - after_peak.iloc[0]) if len(after_peak) > 1 else 0
                mr_speed = reversion / max(abs(cum_rets.max() - cum_rets.min()), 1e-10)
            else:
                mr_speed = np.nan

            # H-1074: Volume clock — first half vs second half
            mid_hour = 12
            first_half_vol = group.loc[group["hour"] < mid_hour, "dollar_vol"].sum()
            second_half_vol = group.loc[group["hour"] >= mid_hour, "dollar_vol"].sum()
            vol_clock = first_half_vol / (first_half_vol + second_half_vol) if (first_half_vol + second_half_vol) > 0 else np.nan

            # H-1075: Intraday CLV trend
            clv_values = []
            for _, row in group.iterrows():
                if row["high"] > row["low"]:
                    clv = (2 * row["close"] - row["high"] - row["low"]) / (row["high"] - row["low"])
                    clv_values.append(clv)
            clv_trend = np.mean(clv_values) if clv_values else np.nan

            daily_feats[pd.Timestamp(date)] = {
                "vol_ratio": vol_ratio,
                "autocorr": autocorr,
                "vw_ret": vw_ret,
                "range_exp": range_exp,
                "session_diff": session_diff,
                "mr_speed": mr_speed,
                "vol_clock": vol_clock,
                "clv_trend": clv_trend,
            }

        feat_df = pd.DataFrame(daily_feats).T
        for col in feat_df.columns:
            key = f"{sym}_{col}"
            features[key] = feat_df[col]

    return features


def build_signal_df(features, feature_name, period=14):
    """Build cross-sectional signal DataFrame from per-asset daily features."""
    cols = {}
    for key, series in features.items():
        if key.endswith(f"_{feature_name}"):
            sym = key.replace(f"_{feature_name}", "")
            cols[sym] = series
    if not cols:
        return pd.DataFrame()
    df = pd.DataFrame(cols).sort_index()
    return df.rolling(period).mean()


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
    for direction in directions:
        for n_ls in n_ls_list:
            for rebal in rebal_list:
                pnl = xs_backtest(closes_c, signal_c, lookback, rebal, n_ls, direction)
                m = compute_metrics(pnl)
                if m["sharpe"] > best.get("sharpe", -999):
                    best = {**m, "direction": direction, "n_ls": n_ls, "rebal": rebal,
                            "pnl": pnl, "closes_c": closes_c, "signal_c": signal_c}
    if best["sharpe"] <= 0:
        print(f"  {name}: IS Sharpe {best.get('sharpe', 0):.3f} — SKIP (no positive)")
        return None
    pnl = best["pnl"]
    wf = walk_forward(best["closes_c"], best["signal_c"], lookback, best["rebal"],
                      best["n_ls"], best["direction"])
    sh1, sh2, p_val = split_half_test(pnl)
    corr = h012_correlation(best["closes_c"], best["signal_c"], lookback, best["rebal"],
                            best["n_ls"], best["direction"])
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
    print("Loading daily data...")
    closes, volumes = load_daily()

    print("Computing hourly features (this may take a minute)...")
    features = compute_hourly_features()
    print(f"Got {len(features)} feature series")
    print()

    feature_map = {
        "H-1068": ("vol_ratio", "Intraday Vol Ratio (Day/Night)"),
        "H-1069": ("autocorr", "Hourly Return Autocorrelation"),
        "H-1070": ("vw_ret", "Volume-Weighted Return"),
        "H-1071": ("range_exp", "Hourly Range Expansion"),
        "H-1072": ("session_diff", "Session Momentum (US-Asia)"),
        "H-1073": ("mr_speed", "Intraday Mean Reversion Speed"),
        "H-1074": ("vol_clock", "Volume Clock (AM/PM)"),
        "H-1075": ("clv_trend", "Intraday CLV Trend"),
    }

    results = {}

    for hyp_id, (feat_name, desc) in feature_map.items():
        print(f"{hyp_id}: {desc}")
        sig = build_signal_df(features, feat_name, period=14)
        r = run_signal(hyp_id, sig, closes, 14, ["high_long", "low_long"])
        if r:
            results[hyp_id] = r

    print(f"\n{'='*80}")
    print(f"BATCH SUMMARY: {len(results)}/{8} signals with positive IS Sharpe")
    for name, r in sorted(results.items(), key=lambda x: -x[1]["sharpe"]):
        status = "CONFIRMED" if r["wf_pos"] >= max(2, r["wf_total"] * 0.5) and r["p_val"] < 0.1 else "BORDERLINE" if r["wf_pos"] >= 2 else "REJECTED"
        print(f"  {name}: Sharpe {r['sharpe']:.3f} | WF {r['wf_pos']}/{r['wf_total']} | p={r['p_val']:.3f} | corr {r['h012_corr']:.3f} | {status}")


if __name__ == "__main__":
    main()
