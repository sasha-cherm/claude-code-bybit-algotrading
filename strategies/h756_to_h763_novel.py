"""
Batch backtest: H-756 to H-763 — Novel signal constructions.

H-756: Asymmetric Beta XS — downside beta vs upside beta (long low-downside-beta)
H-757: Return Consistency XS — fraction of positive return days (long consistent winners)
H-758: Momentum Persistence XS — streak length of consecutive gains/losses
H-759: ADX Trend Strength XS — long strong-trend assets
H-760: Volume Surprise XS — volume spike relative to recent norm
H-761: Gap Signal XS — open-to-prev-close gap effect (daily only)
H-762: Range Position XS — where in recent range the price sits
H-763: Momentum-Vol Ratio XS — momentum normalized by idiosyncratic vol (Sharpe-like)
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
    closes = {}
    highs = {}
    lows = {}
    opens = {}
    volumes = {}
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
    mid = len(pnl) // 2
    t_stat, p_val = stats.ttest_1samp(pnl, 0)
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

def asymmetric_beta_signal(closes, window):
    """H-756: Downside beta minus upside beta."""
    returns = closes.pct_change()
    mkt = returns.mean(axis=1)
    result = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        for i in range(window, len(returns)):
            y = returns[col].iloc[i-window:i].values
            x = mkt.iloc[i-window:i].values
            mask = np.isfinite(y) & np.isfinite(x)
            if mask.sum() < window // 3:
                continue
            y_c, x_c = y[mask], x[mask]
            down_mask = x_c < 0
            up_mask = x_c >= 0
            if down_mask.sum() > 5 and up_mask.sum() > 5:
                beta_down = np.cov(y_c[down_mask], x_c[down_mask])[0, 1] / max(np.var(x_c[down_mask]), 1e-10)
                beta_up = np.cov(y_c[up_mask], x_c[up_mask])[0, 1] / max(np.var(x_c[up_mask]), 1e-10)
                result.loc[result.index[i], col] = beta_down - beta_up
    return result


def return_consistency_signal(closes, window):
    """H-757: Fraction of positive return days."""
    returns = closes.pct_change()
    positive = (returns > 0).astype(float)
    return positive.rolling(window).mean()


def momentum_persistence_signal(closes, window):
    """H-758: Current streak of consecutive positive/negative days, normalized."""
    returns = closes.pct_change()
    result = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for col in closes.columns:
        streak = 0
        for i in range(1, len(returns)):
            r = returns[col].iloc[i]
            if not np.isfinite(r):
                streak = 0
            elif r > 0:
                streak = max(streak, 0) + 1
            elif r < 0:
                streak = min(streak, 0) - 1
            else:
                streak = 0
            result.loc[result.index[i], col] = streak
    return result


def adx_trend_strength_signal(closes, highs, lows, window):
    """H-759: ADX-like trend strength."""
    result = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        h = highs[col] if col in highs.columns else closes[col]
        l = lows[col] if col in lows.columns else closes[col]
        c = closes[col]
        tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
        dm_plus = (h - h.shift(1)).clip(lower=0)
        dm_minus = (l.shift(1) - l).clip(lower=0)
        atr = tr.rolling(window).mean()
        di_plus = (dm_plus.rolling(window).mean() / atr.replace(0, np.nan)) * 100
        di_minus = (dm_minus.rolling(window).mean() / atr.replace(0, np.nan)) * 100
        dx = ((di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan)) * 100
        adx = dx.rolling(window).mean()
        result[col] = adx
    return result


def volume_surprise_signal(volumes, window):
    """H-760: Volume z-score — current volume vs rolling average."""
    vol_ma = volumes.rolling(window).mean()
    vol_std = volumes.rolling(window).std()
    return (volumes - vol_ma) / vol_std.replace(0, np.nan)


def gap_signal(opens, closes):
    """H-761: Gap between today's open and yesterday's close."""
    gap = (opens - closes.shift(1)) / closes.shift(1)
    return gap.rolling(5).mean()


def range_position_signal(closes, highs, lows, window):
    """H-762: Where in the recent high-low range the price sits."""
    rolling_high = highs.rolling(window).max()
    rolling_low = lows.rolling(window).min()
    rng = rolling_high - rolling_low
    return (closes - rolling_low) / rng.replace(0, np.nan)


def momentum_vol_ratio_signal(closes, mom_window, vol_window):
    """H-763: Momentum / volatility — signal-to-noise ratio."""
    ret = closes.pct_change()
    mom = closes.pct_change(mom_window)
    vol = ret.rolling(vol_window).std().replace(0, np.nan)
    return mom / vol


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
    print("Loading data...")
    closes, highs, lows, opens, volumes = load_data()
    print(f"  {len(closes)} days, {len(closes.columns)} assets")

    results = []

    # H-756: Asymmetric Beta
    print("\nComputing H-756 asymmetric beta signal...")
    sig = asymmetric_beta_signal(closes, 60)
    r = run_hypothesis("H-756: Asymmetric Beta",
                       sig, closes,
                       [(60, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "low_long")  # short high downside beta
    results.append(r)

    # H-757: Return Consistency
    print("\nComputing H-757 return consistency signal...")
    sig = return_consistency_signal(closes, 20)
    r = run_hypothesis("H-757: Return Consistency",
                       sig, closes,
                       [(20, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "high_long")  # long consistent winners
    results.append(r)

    # H-758: Momentum Persistence
    print("\nComputing H-758 momentum persistence signal...")
    sig = momentum_persistence_signal(closes, 20)
    r = run_hypothesis("H-758: Momentum Persistence",
                       sig, closes,
                       [(20, r, n) for r in [1, 3, 5] for n in [3, 4]],
                       "high_long")  # long streaks = continuation
    results.append(r)

    # H-759: ADX Trend Strength
    print("\nComputing H-759 ADX trend strength signal...")
    sig = adx_trend_strength_signal(closes, highs, lows, 14)
    r = run_hypothesis("H-759: ADX Trend Strength",
                       sig, closes,
                       [(14, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "high_long")  # long strong trends
    results.append(r)

    # H-760: Volume Surprise
    print("\nComputing H-760 volume surprise signal...")
    sig = volume_surprise_signal(volumes, 20)
    r = run_hypothesis("H-760: Volume Surprise",
                       sig, closes,
                       [(20, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "high_long")
    results.append(r)

    # H-761: Gap Signal
    print("\nComputing H-761 gap signal...")
    sig = gap_signal(opens, closes)
    r = run_hypothesis("H-761: Gap Signal",
                       sig, closes,
                       [(5, r, n) for r in [1, 3, 5] for n in [3, 4]],
                       "high_long")
    results.append(r)

    # H-762: Range Position
    print("\nComputing H-762 range position signal...")
    sig = range_position_signal(closes, highs, lows, 20)
    r = run_hypothesis("H-762: Range Position",
                       sig, closes,
                       [(20, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "high_long")  # long near top of range (momentum)
    results.append(r)

    # H-763: Momentum-Vol Ratio
    print("\nComputing H-763 momentum-vol ratio signal...")
    sig = momentum_vol_ratio_signal(closes, 20, 20)
    r = run_hypothesis("H-763: Momentum-Vol Ratio",
                       sig, closes,
                       [(20, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "high_long")
    results.append(r)

    # Summary
    print("\n" + "=" * 60)
    print("  BATCH SUMMARY: H-756 to H-763")
    print("=" * 60)
    for r in results:
        status = r['status']
        sharpe = r.get('sharpe', 0)
        extra = ""
        if status.startswith("CONFIRMED"):
            extra = f" | WF {r.get('wf_pass', '?')} | corr {r.get('h012_corr', '?')} | robust {r.get('robust_pct', '?')}%"
        print(f"  {r['name']}: {status} (IS Sharpe {sharpe}){extra}")
