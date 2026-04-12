"""
Batch backtest: H-764 to H-771 — Sequential and pattern-based XS signals.

H-764: Return Autocorrelation XS — serial correlation of daily returns (long trending, short mean-reverting)
H-765: Close-to-High Ratio XS — where price closes relative to daily high (buying pressure proxy)
H-766: Volume-Weighted Return XS — cumulative return weighted by volume (volume-confirmed moves)
H-767: Intraday Range Ratio XS — (high-low)/|close change| ratio (noise vs signal)
H-768: Sequential Pattern Score XS — 3-day directional pattern score
H-769: Multi-Horizon Divergence XS — 5d vs 20d momentum divergence
H-770: Drawdown Depth XS — current drawdown from rolling high (buy beaten-down assets)
H-771: Volume Climax XS — extreme volume with directional price move
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

def return_autocorrelation_signal(closes, window):
    """H-764: Rolling autocorrelation of daily returns."""
    returns = closes.pct_change()
    result = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        for i in range(window + 1, len(returns)):
            r = returns[col].iloc[i - window:i].values
            r_lag = returns[col].iloc[i - window - 1:i - 1].values
            mask = np.isfinite(r) & np.isfinite(r_lag)
            if mask.sum() > 10:
                result.iloc[i, result.columns.get_loc(col)] = np.corrcoef(r[mask], r_lag[mask])[0, 1]
    return result


def close_to_high_ratio_signal(closes, highs, window):
    """H-765: Average (close/high) over window — buying pressure."""
    ratio = closes / highs.replace(0, np.nan)
    return ratio.rolling(window).mean()


def volume_weighted_return_signal(closes, volumes, window):
    """H-766: Volume-weighted cumulative return."""
    returns = closes.pct_change()
    vw_ret = returns * volumes
    vol_sum = volumes.rolling(window).sum().replace(0, np.nan)
    return vw_ret.rolling(window).sum() / vol_sum


def intraday_range_ratio_signal(closes, highs, lows, window):
    """H-767: (high-low) / |close change| — noise ratio."""
    daily_range = (highs - lows) / closes.replace(0, np.nan)
    abs_change = closes.pct_change().abs()
    ratio = daily_range / abs_change.replace(0, np.nan)
    ratio = ratio.clip(upper=50)
    return ratio.rolling(window).mean()


def sequential_pattern_signal(closes, window):
    """H-768: Score based on 3-day directional patterns."""
    returns = closes.pct_change()
    up = (returns > 0).astype(float)
    score = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for col in closes.columns:
        for i in range(3, len(returns)):
            d1 = 1 if returns[col].iloc[i - 2] > 0 else -1
            d2 = 1 if returns[col].iloc[i - 1] > 0 else -1
            d3 = 1 if returns[col].iloc[i] > 0 else -1
            pattern = d1 + d2 + d3
            score.iloc[i, score.columns.get_loc(col)] = pattern
    return score.rolling(window).mean()


def multi_horizon_divergence_signal(closes, short_window, long_window):
    """H-769: Short-term minus long-term momentum (divergence)."""
    mom_short = closes.pct_change(short_window)
    mom_long = closes.pct_change(long_window)
    return mom_short - mom_long


def drawdown_depth_signal(closes, window):
    """H-770: Current drawdown from rolling high."""
    rolling_max = closes.rolling(window).max()
    dd = (closes - rolling_max) / rolling_max.replace(0, np.nan)
    return dd


def volume_climax_signal(closes, volumes, window):
    """H-771: Volume z-score * sign of return — directional volume climax."""
    returns = closes.pct_change()
    vol_ma = volumes.rolling(window).mean()
    vol_std = volumes.rolling(window).std().replace(0, np.nan)
    vol_z = (volumes - vol_ma) / vol_std
    sign = np.sign(returns)
    return (vol_z * sign).rolling(5).mean()


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
    print(f"Data: {len(closes)} days, {len(closes.columns)} assets")
    print(f"Date range: {closes.index[0]} to {closes.index[-1]}")

    param_grid_standard = [
        (20, 3, 3), (20, 3, 4), (20, 5, 3), (20, 5, 4),
        (30, 3, 3), (30, 3, 4), (30, 5, 3), (30, 5, 4),
        (40, 3, 3), (40, 3, 4), (40, 5, 3), (40, 5, 4),
        (60, 5, 3), (60, 5, 4), (60, 7, 3), (60, 7, 4),
    ]

    results = []

    # H-764: Return Autocorrelation
    sig = return_autocorrelation_signal(closes, 30)
    r = run_hypothesis("H-764: Return Autocorrelation XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)
    if r["status"] == "REJECTED":
        r2 = run_hypothesis("H-764b: Return Autocorrelation (low_long)", sig, closes, param_grid_standard, "low_long")
        if r2.get("sharpe", 0) > r.get("sharpe", 0):
            results[-1] = r2

    # H-765: Close-to-High Ratio
    sig = close_to_high_ratio_signal(closes, highs, 20)
    r = run_hypothesis("H-765: Close-to-High Ratio XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-766: Volume-Weighted Return
    sig = volume_weighted_return_signal(closes, volumes, 20)
    r = run_hypothesis("H-766: Volume-Weighted Return XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-767: Intraday Range Ratio
    sig = intraday_range_ratio_signal(closes, highs, lows, 20)
    r = run_hypothesis("H-767: Intraday Range Ratio XS", sig, closes, param_grid_standard, "low_long")
    results.append(r)

    # H-768: Sequential Pattern Score
    sig = sequential_pattern_signal(closes, 10)
    r = run_hypothesis("H-768: Sequential Pattern Score XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-769: Multi-Horizon Divergence
    sig = multi_horizon_divergence_signal(closes, 5, 20)
    r = run_hypothesis("H-769: Multi-Horizon Divergence XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)
    if r["status"] == "REJECTED":
        r2 = run_hypothesis("H-769b: Multi-Horizon Divergence (contrarian)", sig, closes, param_grid_standard, "low_long")
        if r2.get("sharpe", 0) > r.get("sharpe", 0):
            results[-1] = r2

    # H-770: Drawdown Depth
    sig = drawdown_depth_signal(closes, 30)
    r = run_hypothesis("H-770: Drawdown Depth XS (buy beaten-down)", sig, closes, param_grid_standard, "low_long")
    results.append(r)
    if r["status"] == "REJECTED":
        r2 = run_hypothesis("H-770b: Drawdown Depth (momentum)", sig, closes, param_grid_standard, "high_long")
        if r2.get("sharpe", 0) > r.get("sharpe", 0):
            results[-1] = r2

    # H-771: Volume Climax
    sig = volume_climax_signal(closes, volumes, 20)
    r = run_hypothesis("H-771: Volume Climax XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

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

    with open("strategies/h764_to_h771_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nResults saved to strategies/h764_to_h771_results.json")
