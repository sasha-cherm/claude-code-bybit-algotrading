"""
Batch backtest: H-772 to H-779 — Interaction and conditional XS signals.

H-772: Momentum × Volume Change XS — momentum weighted by volume trend
H-773: OI-Confirmed Momentum XS — momentum only when OI is expanding
H-774: Funding-Adjusted Momentum XS — momentum penalized by extreme funding
H-775: Vol-Regime Momentum XS — momentum only in low-vol regime for each asset
H-776: Return-Volume Asymmetry XS — avg return on high-vol vs low-vol days
H-777: Price-Volume Trend XS — PVT indicator as cross-sectional signal
H-778: Close Location Value XS — (close-low)/(high-low) aggregated
H-779: Relative Spread XS — normalized high-low spread cross-sectionally
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
    return closes, highs, lows, opens, volumes


def load_oi():
    oi = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"oi/{ticker}_oi_1d.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            col = "openInterest" if "openInterest" in df.columns else df.columns[0]
            oi[f"{ticker}/USDT"] = df[col].astype(float)
        except:
            pass
    return pd.DataFrame(oi).sort_index().dropna(how="all")


def load_funding():
    funding = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"funding/{ticker}_funding.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            col = "fundingRate" if "fundingRate" in df.columns else df.columns[0]
            daily = df[col].astype(float).resample("1D").sum()
            funding[f"{ticker}/USDT"] = daily
        except:
            pass
    if not funding:
        return None
    return pd.DataFrame(funding).sort_index().dropna(how="all")


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

def momentum_x_volume_change_signal(closes, volumes, mom_window, vol_window):
    """H-772: Momentum weighted by volume trend."""
    mom = closes.pct_change(mom_window)
    vol_change = volumes.pct_change(vol_window)
    return mom * (1 + vol_change.clip(-1, 5))


def oi_confirmed_momentum_signal(closes, oi_df, mom_window, oi_window):
    """H-773: Momentum × sign(OI change) — only momentum confirmed by OI expansion."""
    mom = closes.pct_change(mom_window)
    common_idx = closes.index.intersection(oi_df.index)
    common_cols = [c for c in closes.columns if c in oi_df.columns]
    if len(common_idx) < 100 or len(common_cols) < 8:
        return mom
    oi_aligned = oi_df.reindex(index=closes.index, columns=closes.columns)
    oi_change = oi_aligned.pct_change(oi_window)
    oi_expanding = (oi_change > 0).astype(float)
    return mom * (0.5 + oi_expanding)


def funding_adjusted_momentum_signal(closes, funding_df, mom_window, fund_window):
    """H-774: Momentum penalized by extreme funding rate."""
    mom = closes.pct_change(mom_window)
    if funding_df is None:
        return mom
    fund_aligned = funding_df.reindex(index=closes.index, columns=closes.columns)
    fund_rolling = fund_aligned.rolling(fund_window).mean()
    fund_z = (fund_rolling - fund_rolling.mean()) / fund_rolling.std().replace(0, np.nan)
    penalty = 1 - fund_z.abs().clip(0, 2) * 0.25
    return mom * penalty


def vol_regime_momentum_signal(closes, mom_window, vol_window):
    """H-775: Momentum amplified in low-vol regime, dampened in high-vol."""
    mom = closes.pct_change(mom_window)
    ret = closes.pct_change()
    vol = ret.rolling(vol_window).std()
    vol_median = vol.rolling(120).median()
    low_vol = (vol < vol_median).astype(float)
    return mom * (0.5 + low_vol)


def return_volume_asymmetry_signal(closes, volumes, window):
    """H-776: Avg return on high-vol days minus avg return on low-vol days."""
    returns = closes.pct_change()
    result = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    vol_median = volumes.rolling(window).median()
    for i in range(window, len(closes)):
        for col in closes.columns:
            r = returns[col].iloc[i - window:i].values
            v = volumes[col].iloc[i - window:i].values
            med = vol_median[col].iloc[i]
            if not np.isfinite(med) or med == 0:
                continue
            mask = np.isfinite(r) & np.isfinite(v)
            r_c, v_c = r[mask], v[mask]
            high_vol = v_c > med
            low_vol = ~high_vol
            if high_vol.sum() > 3 and low_vol.sum() > 3:
                result.iloc[i, result.columns.get_loc(col)] = np.mean(r_c[high_vol]) - np.mean(r_c[low_vol])
    return result


def price_volume_trend_signal(closes, volumes, window):
    """H-777: Price Volume Trend — cumulative (return × volume) over window."""
    returns = closes.pct_change()
    pvt_daily = returns * volumes
    return pvt_daily.rolling(window).sum()


def close_location_value_signal(closes, highs, lows, window):
    """H-778: (close - low) / (high - low) averaged over window."""
    rng = (highs - lows).replace(0, np.nan)
    clv = (closes - lows) / rng
    return clv.rolling(window).mean()


def relative_spread_signal(highs, lows, closes, window):
    """H-779: (high - low) / close spread — normalized volatility proxy."""
    spread = (highs - lows) / closes.replace(0, np.nan)
    return spread.rolling(window).mean()


# ============================================================
# MAIN
# ============================================================

def run_hypothesis(name, signal_df, closes, param_grid, direction):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    best_sharpe = -999
    best_params = None
    best_pnl = None

    for lookback, rebal, n_ls in param_grid:
        pnl = xs_backtest(closes, signal_df, lookback, rebal, n_ls, direction)
        sh = compute_sharpe(pnl)
        if sh > best_sharpe:
            best_sharpe = sh
            best_params = (lookback, rebal, n_ls)
            best_pnl = pnl

    metrics = compute_metrics(best_pnl)
    print(f"  Best IS: Sharpe {metrics['sharpe']}, Ret {metrics['annual_ret']}%, DD {metrics['max_dd']}%")
    print(f"  Params: lookback={best_params[0]}, rebal={best_params[1]}, n_ls={best_params[2]}")

    if metrics['sharpe'] < 0.5:
        print(f"  REJECTED — IS Sharpe {metrics['sharpe']} < 0.5")
        return {"name": name, "status": "REJECTED", "reason": f"IS Sharpe {metrics['sharpe']}", **metrics}

    pos = sum(1 for lb, rb, nls in param_grid
              if compute_sharpe(xs_backtest(closes, signal_df, lb, rb, nls, direction)) > 0)
    total = len(param_grid)
    robust_pct = pos / total * 100
    print(f"  Param robust: {pos}/{total} ({robust_pct:.0f}%)")

    if robust_pct < 60:
        print(f"  REJECTED — param robust {robust_pct:.0f}% < 60%")
        return {"name": name, "status": "REJECTED", "reason": f"param robust {robust_pct:.0f}%", **metrics}

    wf = walk_forward(closes, signal_df, best_params[0], best_params[1], best_params[2], direction)
    wf_pass = sum(1 for s in wf if s > 0)
    wf_mean = np.mean(wf) if wf else 0
    print(f"  WF: {wf_pass}/{len(wf)} positive, mean {wf_mean:.3f}")
    print(f"  WF folds: {[round(s,2) for s in wf]}")

    if len(wf) >= 4 and wf_pass < len(wf) * 0.6:
        print(f"  REJECTED — WF {wf_pass}/{len(wf)}")
        return {"name": name, "status": "REJECTED", "reason": f"WF {wf_pass}/{len(wf)}", **metrics,
                "wf": wf, "robust_pct": robust_pct}

    sh1, sh2, p_val = split_half_test(best_pnl)
    print(f"  SH: {sh1:.3f} / {sh2:.3f}, p={p_val:.4f}")

    if p_val > 0.10:
        print(f"  REJECTED — SH p-value {p_val:.4f} > 0.10")
        return {"name": name, "status": "REJECTED", "reason": f"SH p={p_val:.4f}", **metrics,
                "wf": wf, "robust_pct": robust_pct, "sh": (sh1, sh2, p_val)}

    corr = h012_correlation(closes, signal_df, best_params[0], best_params[1], best_params[2], direction)
    print(f"  H-012 corr: {corr}")

    status = "CONFIRMED" if abs(corr) < 0.7 else "CONFIRMED_REDUNDANT"
    print(f"  → {status}")

    return {"name": name, "status": status, **metrics, "params": best_params,
            "wf": wf, "wf_pass": f"{wf_pass}/{len(wf)}", "wf_mean": round(wf_mean, 3),
            "robust_pct": robust_pct, "sh": (round(sh1, 3), round(sh2, 3), round(p_val, 4)),
            "h012_corr": corr, "direction": direction, "n_days": len(best_pnl)}


if __name__ == "__main__":
    import json

    closes, highs, lows, opens, volumes = load_data()
    oi_df = load_oi()
    funding_df = load_funding()
    print(f"Data: {len(closes)} days, {len(closes.columns)} assets")
    print(f"OI data: {len(oi_df)} days, {len(oi_df.columns)} assets" if oi_df is not None and len(oi_df) > 0 else "No OI data")
    print(f"Funding data: {len(funding_df)} days" if funding_df is not None else "No funding data")

    param_grid_standard = [
        (20, 3, 3), (20, 3, 4), (20, 5, 3), (20, 5, 4),
        (30, 3, 3), (30, 3, 4), (30, 5, 3), (30, 5, 4),
        (40, 3, 3), (40, 3, 4), (40, 5, 3), (40, 5, 4),
        (60, 5, 3), (60, 5, 4), (60, 7, 3), (60, 7, 4),
    ]

    results = []

    # H-772: Momentum × Volume Change
    sig = momentum_x_volume_change_signal(closes, volumes, 20, 10)
    r = run_hypothesis("H-772: Momentum × Volume Change XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-773: OI-Confirmed Momentum
    sig = oi_confirmed_momentum_signal(closes, oi_df, 20, 5)
    r = run_hypothesis("H-773: OI-Confirmed Momentum XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-774: Funding-Adjusted Momentum
    sig = funding_adjusted_momentum_signal(closes, funding_df, 20, 10)
    r = run_hypothesis("H-774: Funding-Adjusted Momentum XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-775: Vol-Regime Momentum
    sig = vol_regime_momentum_signal(closes, 20, 30)
    r = run_hypothesis("H-775: Vol-Regime Momentum XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-776: Return-Volume Asymmetry
    sig = return_volume_asymmetry_signal(closes, volumes, 30)
    r = run_hypothesis("H-776: Return-Volume Asymmetry XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-777: Price-Volume Trend
    sig = price_volume_trend_signal(closes, volumes, 20)
    r = run_hypothesis("H-777: Price-Volume Trend XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-778: Close Location Value
    sig = close_location_value_signal(closes, highs, lows, 20)
    r = run_hypothesis("H-778: Close Location Value XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-779: Relative Spread
    sig = relative_spread_signal(highs, lows, closes, 20)
    r = run_hypothesis("H-779: Relative Spread XS", sig, closes, param_grid_standard, "low_long")
    results.append(r)
    if r["status"] == "REJECTED":
        r2 = run_hypothesis("H-779b: Relative Spread (high_long)", sig, closes, param_grid_standard, "high_long")
        if r2.get("sharpe", 0) > r.get("sharpe", 0):
            results[-1] = r2

    print("\n" + "="*60)
    print("BATCH SUMMARY")
    print("="*60)
    for r in results:
        status = r["status"]
        name = r["name"]
        sh = r.get("sharpe", 0)
        reason = r.get("reason", "")
        extra = ""
        if "wf_pass" in r:
            extra += f" WF {r['wf_pass']}"
        if "h012_corr" in r:
            extra += f" corr {r['h012_corr']}"
        if "sh" in r:
            extra += f" SH p={r['sh'][2]}"
        print(f"  {status:20s} | {name:45s} | Sharpe {sh:6.3f} | {reason}{extra}")

    with open("strategies/h772_to_h779_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nResults saved to strategies/h772_to_h779_results.json")
