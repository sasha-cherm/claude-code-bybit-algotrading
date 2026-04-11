"""
Batch backtest: H-740 to H-747 — Residual/Idiosyncratic signals.

After removing market beta exposure, what cross-sectional signals remain?
These are fundamentally different from raw momentum/vol — they capture
asset-specific (idiosyncratic) behavior after controlling for the market factor.

H-740: Idiosyncratic Volatility XS — short high-idio-vol, long low-idio-vol
H-741: Residual Momentum XS — momentum after beta-adjusting for BTC
H-742: Idiosyncratic Skewness XS — short positive-skew lottery tickets
H-743: Beta Deviation XS — long assets whose beta reverts to mean
H-744: Tracking Error XS — how "independently" an asset trades vs BTC
H-745: Information Ratio XS — return per unit of idiosyncratic risk
H-746: Residual Reversal XS — short-term reversal in idiosyncratic returns
H-747: Systematic Risk Share XS — fraction of var explained by market
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
    volumes = {}
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
    h1 = pnl[:mid]
    h2 = pnl[mid:]
    sh1 = compute_sharpe(h1)
    sh2 = compute_sharpe(h2)
    t_stat, p_val = stats.ttest_1samp(pnl, 0)
    return sh1, sh2, p_val


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

def compute_market_return(closes):
    """Equal-weighted market return (proxy for BTC-dominated market)."""
    returns = closes.pct_change()
    mkt = returns.mean(axis=1)
    return mkt


def rolling_beta(asset_ret, mkt_ret, window):
    """Rolling OLS beta of asset on market."""
    betas = pd.Series(index=asset_ret.index, dtype=float)
    for i in range(window, len(asset_ret)):
        y = asset_ret.iloc[i-window:i].values
        x = mkt_ret.iloc[i-window:i].values
        mask = np.isfinite(y) & np.isfinite(x)
        if mask.sum() < window // 2:
            continue
        y, x = y[mask], x[mask]
        if np.std(x) == 0:
            continue
        beta = np.cov(y, x)[0, 1] / np.var(x)
        betas.iloc[i] = beta
    return betas


def compute_residuals(closes, window):
    """Compute idiosyncratic (residual) returns for each asset."""
    returns = closes.pct_change()
    mkt = returns.mean(axis=1)
    residuals = pd.DataFrame(index=closes.index, columns=closes.columns)
    betas = pd.DataFrame(index=closes.index, columns=closes.columns)

    for col in closes.columns:
        b = rolling_beta(returns[col], mkt, window)
        betas[col] = b
        residuals[col] = returns[col] - b * mkt

    return residuals, betas, returns, mkt


def idio_vol_signal(closes, window):
    """H-740: Idiosyncratic volatility — std of residual returns."""
    residuals, _, _, _ = compute_residuals(closes, window)
    return residuals.rolling(window).std()


def residual_momentum_signal(closes, lookback, beta_window):
    """H-741: Cumulative residual return over lookback period."""
    residuals, _, _, _ = compute_residuals(closes, beta_window)
    return residuals.rolling(lookback).sum()


def idio_skew_signal(closes, window):
    """H-742: Skewness of residual returns."""
    residuals, _, _, _ = compute_residuals(closes, window)
    return residuals.rolling(window).skew()


def beta_deviation_signal(closes, short_window, long_window):
    """H-743: Short-term beta minus long-term beta — mean reversion signal."""
    returns = closes.pct_change()
    mkt = returns.mean(axis=1)
    result = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        b_short = rolling_beta(returns[col], mkt, short_window)
        b_long = rolling_beta(returns[col], mkt, long_window)
        result[col] = b_short - b_long
    return result


def tracking_error_signal(closes, window):
    """H-744: Tracking error vs market — high = trades independently."""
    returns = closes.pct_change()
    mkt = returns.mean(axis=1)
    result = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        diff = returns[col] - mkt
        result[col] = diff.rolling(window).std()
    return result


def information_ratio_signal(closes, window):
    """H-745: Mean residual return / residual volatility."""
    residuals, _, _, _ = compute_residuals(closes, window)
    res_mean = residuals.rolling(window).mean()
    res_std = residuals.rolling(window).std().replace(0, np.nan)
    return res_mean / res_std


def residual_reversal_signal(closes, beta_window, reversal_window):
    """H-746: Short-term residual return (reversal candidate)."""
    residuals, _, _, _ = compute_residuals(closes, beta_window)
    return residuals.rolling(reversal_window).sum()


def systematic_risk_share_signal(closes, window):
    """H-747: R-squared of asset vs market — fraction of variance from market."""
    returns = closes.pct_change()
    mkt = returns.mean(axis=1)
    result = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        for i in range(window, len(returns)):
            y = returns[col].iloc[i-window:i].values
            x = mkt.iloc[i-window:i].values
            mask = np.isfinite(y) & np.isfinite(x)
            if mask.sum() < window // 2:
                continue
            y, x = y[mask], x[mask]
            if np.var(y) == 0:
                continue
            corr = np.corrcoef(y, x)[0, 1]
            result[col].iloc[i] = corr ** 2
    return result


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

    # Param robustness
    pos = sum(1 for lb, rb, nls in param_grid
              if compute_sharpe(xs_backtest(closes, signal_df, lb, rb, nls, direction)) > 0)
    total = len(param_grid)
    robust_pct = pos / total * 100
    print(f"  Param robust: {pos}/{total} ({robust_pct:.0f}%)")

    if robust_pct < 60:
        print(f"  REJECTED — param robust {robust_pct:.0f}% < 60%")
        return {"name": name, "status": "REJECTED", "reason": f"param robust {robust_pct:.0f}%", **metrics}

    # Walk-forward
    wf = walk_forward(closes, signal_df, best_params[0], best_params[1], best_params[2], direction)
    wf_pass = sum(1 for s in wf if s > 0)
    wf_mean = np.mean(wf) if wf else 0
    print(f"  WF: {wf_pass}/{len(wf)} positive, mean {wf_mean:.3f}")
    print(f"  WF folds: {[round(s,2) for s in wf]}")

    if len(wf) >= 4 and wf_pass < len(wf) * 0.6:
        print(f"  REJECTED — WF {wf_pass}/{len(wf)}")
        return {"name": name, "status": "REJECTED", "reason": f"WF {wf_pass}/{len(wf)}", **metrics,
                "wf": wf, "robust_pct": robust_pct}

    # Split-half
    sh1, sh2, p_val = split_half_test(best_pnl)
    print(f"  SH: {sh1:.3f} / {sh2:.3f}, p={p_val:.4f}")

    if p_val > 0.10:
        print(f"  REJECTED — SH p-value {p_val:.4f} > 0.10")
        return {"name": name, "status": "REJECTED", "reason": f"SH p={p_val:.4f}", **metrics,
                "wf": wf, "robust_pct": robust_pct, "sh": (sh1, sh2, p_val)}

    # H-012 correlation
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
    closes, volumes = load_data()
    print(f"  {len(closes)} days, {len(closes.columns)} assets")

    results = []

    # H-740: Idiosyncratic Volatility
    print("\nComputing H-740 idiosyncratic volatility signal...")
    sig = idio_vol_signal(closes, 30)
    r = run_hypothesis("H-740: Idiosyncratic Volatility",
                       sig, closes,
                       [(30, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "low_long")  # short high-idio-vol
    results.append(r)

    # H-741: Residual Momentum
    print("\nComputing H-741 residual momentum signal...")
    sig = residual_momentum_signal(closes, 60, 60)
    r = run_hypothesis("H-741: Residual Momentum",
                       sig, closes,
                       [(lb, r, n) for lb in [30, 60, 90] for r in [3, 5] for n in [3, 4]],
                       "high_long")
    results.append(r)

    # H-742: Idiosyncratic Skewness
    print("\nComputing H-742 idiosyncratic skewness signal...")
    sig = idio_skew_signal(closes, 60)
    r = run_hypothesis("H-742: Idiosyncratic Skewness",
                       sig, closes,
                       [(60, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "low_long")  # short positive skew
    results.append(r)

    # H-743: Beta Deviation
    print("\nComputing H-743 beta deviation signal...")
    sig = beta_deviation_signal(closes, 20, 60)
    r = run_hypothesis("H-743: Beta Deviation",
                       sig, closes,
                       [(60, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "low_long")  # short high-beta-deviation (mean revert)
    results.append(r)

    # H-744: Tracking Error
    print("\nComputing H-744 tracking error signal...")
    sig = tracking_error_signal(closes, 30)
    r = run_hypothesis("H-744: Tracking Error",
                       sig, closes,
                       [(30, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "high_long")  # long independent movers
    results.append(r)

    # H-745: Information Ratio
    print("\nComputing H-745 information ratio signal...")
    sig = information_ratio_signal(closes, 60)
    r = run_hypothesis("H-745: Information Ratio",
                       sig, closes,
                       [(60, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "high_long")
    results.append(r)

    # H-746: Residual Reversal
    print("\nComputing H-746 residual reversal signal...")
    sig = residual_reversal_signal(closes, 60, 5)
    r = run_hypothesis("H-746: Residual Reversal",
                       sig, closes,
                       [(60, r, n) for r in [1, 3, 5] for n in [3, 4]],
                       "low_long")  # short recent winners (reversal)
    results.append(r)

    # H-747: Systematic Risk Share
    print("\nComputing H-747 systematic risk share signal...")
    sig = systematic_risk_share_signal(closes, 30)
    r = run_hypothesis("H-747: Systematic Risk Share",
                       sig, closes,
                       [(30, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "low_long")  # long low-R² (idiosyncratic movers)
    results.append(r)

    # Summary
    print("\n" + "=" * 60)
    print("  BATCH SUMMARY: H-740 to H-747")
    print("=" * 60)
    for r in results:
        status = r['status']
        sharpe = r.get('sharpe', 0)
        extra = ""
        if status.startswith("CONFIRMED"):
            extra = f" | WF {r.get('wf_pass', '?')} | corr {r.get('h012_corr', '?')} | robust {r.get('robust_pct', '?')}%"
        print(f"  {r['name']}: {status} (IS Sharpe {sharpe}){extra}")
