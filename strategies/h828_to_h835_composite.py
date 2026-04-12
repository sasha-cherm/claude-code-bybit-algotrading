"""
Batch backtest: H-828 to H-835 — Composite, ensemble, and regime-aware XS signals.

H-828: Top-5 Signal Ensemble — equal-weight z-score of 5 best-performing confirmed signals
H-829: PCA Residual (Factor 1 Removed) — idiosyncratic return after removing market factor
H-830: Regime-Conditional Momentum — momentum only when BTC vol < median (low-vol regime)
H-831: Volume-Confirmed Breakout — price at N-day high/low AND above-avg volume
H-832: Funding-OI Composite — combined funding rate + OI change signal
H-833: Price Efficiency (Variance Ratio) — variance ratio test as XS ranking signal
H-834: Tail Ratio — 95th/|5th| percentile of returns (upside vs downside)
H-835: Rolling Sharpe XS — rolling Sharpe ratio as direct ranking signal
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
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_oi_daily.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            col = "openInterest" if "openInterest" in df.columns else df.columns[0]
            oi[f"{ticker}/USDT"] = df[col]
        except:
            pass
    return pd.DataFrame(oi).sort_index().dropna(how="all")


def load_funding():
    funding = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"funding_{ticker}USDT.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            col = "fundingRate" if "fundingRate" in df.columns else df.columns[0]
            # Resample to daily (sum of 3 daily funding payments)
            daily = df[col].resample("1D").sum()
            funding[f"{ticker}/USDT"] = daily
        except:
            pass
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


def cross_sectional_zscore(df):
    return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1).replace(0, np.nan), axis=0)


# ============================================================
# SIGNAL GENERATORS
# ============================================================

def top5_ensemble_signal(closes, volumes, oi_df):
    """H-828: Equal-weight z-score ensemble of 5 conceptually diverse signals:
    1. Momentum (60d return)
    2. Volume momentum (20d vol change)
    3. OI change (7d)
    4. Volatility (20d, inverse)
    5. Dollar volume (30d avg)
    """
    mom = closes.pct_change(60)
    vol_mom = volumes.pct_change(20)
    oi_chg = oi_df.pct_change(7).reindex(closes.index)
    ret = closes.pct_change()
    vol = ret.rolling(20).std()
    dv = volumes.rolling(30).mean()

    z_mom = cross_sectional_zscore(mom)
    z_volmom = cross_sectional_zscore(vol_mom)
    z_oi = cross_sectional_zscore(oi_chg)
    z_vol = cross_sectional_zscore(-vol)  # Long low vol
    z_dv = cross_sectional_zscore(dv)

    # Only include columns present in all
    common_cols = z_mom.columns.intersection(z_oi.columns)
    return (z_mom[common_cols] + z_volmom[common_cols] + z_oi[common_cols] +
            z_vol[common_cols] + z_dv[common_cols]) / 5


def pca_residual_signal(closes, window):
    """H-829: Residual after removing first principal component (market factor).
    Momentum of the residual captures idiosyncratic trends."""
    ret = closes.pct_change()
    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)

    for i in range(window + 30, len(closes)):
        r_window = ret.iloc[i - window:i].dropna(axis=1, how="any")
        if r_window.shape[1] < 5 or r_window.shape[0] < 20:
            continue
        # Simple PCA: first eigenvector
        r_mat = r_window.values
        r_mean = r_mat.mean(axis=0)
        r_centered = r_mat - r_mean
        cov = np.cov(r_centered, rowvar=False)
        try:
            eigenvalues, eigenvectors = np.linalg.eigh(cov)
            # First PC (largest eigenvalue)
            pc1 = eigenvectors[:, -1]
            # Project returns onto PC1
            factor = r_centered @ pc1
            # Residuals
            loadings = r_centered.T @ factor / (factor @ factor)
            residuals = r_centered - np.outer(factor, loadings)
            # Use cumulative residual of last N days as signal
            for j, col in enumerate(r_window.columns):
                signal.iloc[i, signal.columns.get_loc(col)] = residuals[-5:, j].sum()
        except:
            continue
    return signal


def regime_conditional_momentum_signal(closes, mom_window, vol_window):
    """H-830: Momentum only when BTC vol is below median (low-vol regime).
    In high-vol regime, use contrarian (short-term reversal)."""
    ret = closes.pct_change()
    btc_vol = ret["BTC/USDT"].rolling(vol_window).std()
    btc_vol_median = btc_vol.rolling(252).median()

    mom = closes.pct_change(mom_window)
    reversal = -closes.pct_change(5)
    z_mom = cross_sectional_zscore(mom)
    z_rev = cross_sectional_zscore(reversal)

    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(max(mom_window, vol_window, 260), len(closes)):
        is_low_vol = btc_vol.iloc[i] < btc_vol_median.iloc[i] if np.isfinite(btc_vol_median.iloc[i]) else True
        if is_low_vol:
            signal.iloc[i] = z_mom.iloc[i]
        else:
            signal.iloc[i] = z_rev.iloc[i]
    return signal


def volume_confirmed_breakout_signal(closes, volumes, window):
    """H-831: Price near N-day high + above-average volume = confirmed breakout.
    Rank by proximity to high × volume ratio."""
    high_n = closes.rolling(window).max()
    low_n = closes.rolling(window).min()
    range_n = high_n - low_n
    # Position in range: 1 = at high, 0 = at low
    position = (closes - low_n) / range_n.replace(0, np.nan)

    vol_ratio = volumes / volumes.rolling(window).mean().replace(0, np.nan)

    # Signal: proximity to high × volume confirmation
    return position * vol_ratio


def funding_oi_composite_signal(closes, oi_df, funding_df, window):
    """H-832: Combined funding rate and OI change signal.
    Rising OI + rising funding = crowded long → contrarian short.
    Rising OI + falling funding = accumulation → long."""
    oi_chg = oi_df.pct_change(window).reindex(closes.index)
    funding_avg = funding_df.rolling(window).mean().reindex(closes.index)

    z_oi = cross_sectional_zscore(oi_chg)
    z_fund = cross_sectional_zscore(funding_avg)

    # Contrarian: rising OI + positive funding = overbought (short)
    # OI rising + negative funding = accumulation (long)
    # Signal: OI change × (-funding) = long when OI rises but funding falls
    common = z_oi.columns.intersection(z_fund.columns)
    return z_oi[common] * (-z_fund[common])


def variance_ratio_signal(closes, window, lag=5):
    """H-833: Variance ratio test — var(lag-day returns) / (lag × var(1-day returns)).
    >1 = trending (momentum). <1 = mean-reverting (contrarian)."""
    ret = closes.pct_change()
    ret_lag = closes.pct_change(lag)

    var_1 = ret.rolling(window).var()
    var_lag = ret_lag.rolling(window).var()

    # Variance ratio
    vr = var_lag / (lag * var_1.replace(0, np.nan))
    return vr


def tail_ratio_signal(closes, window):
    """H-834: 95th percentile / |5th percentile| of daily returns.
    High ratio = fatter right tail = bullish asymmetry."""
    ret = closes.pct_change()
    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)

    for i in range(window + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i - window:i].dropna().values
            if len(r) > 15:
                q95 = np.percentile(r, 95)
                q5 = np.percentile(r, 5)
                if abs(q5) > 1e-12:
                    signal.iloc[i, signal.columns.get_loc(col)] = q95 / abs(q5)
    return signal


def rolling_sharpe_signal(closes, window):
    """H-835: Rolling Sharpe ratio as direct XS ranking signal.
    High recent Sharpe → continue performing well."""
    ret = closes.pct_change()
    mean_r = ret.rolling(window).mean()
    std_r = ret.rolling(window).std().replace(0, np.nan)
    return mean_r / std_r * np.sqrt(365)


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
    print(f"OI: {len(oi_df)} days, {len(oi_df.columns)} assets")
    print(f"Funding: {len(funding_df)} days, {len(funding_df.columns)} assets")

    param_grid_standard = [
        (20, 3, 3), (20, 3, 4), (20, 5, 3), (20, 5, 4),
        (30, 3, 3), (30, 3, 4), (30, 5, 3), (30, 5, 4),
        (40, 3, 3), (40, 3, 4), (40, 5, 3), (40, 5, 4),
        (60, 5, 3), (60, 5, 4), (60, 7, 3), (60, 7, 4),
        (60, 7, 5), (60, 10, 4),
    ]

    results = []

    # H-828: Top-5 Signal Ensemble
    sig = top5_ensemble_signal(closes, volumes, oi_df)
    r = run_hypothesis("H-828: Top-5 Signal Ensemble XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-829: PCA Residual
    sig = pca_residual_signal(closes, 60)
    r = run_hypothesis("H-829: PCA Residual Momentum XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-830: Regime-Conditional Momentum
    sig = regime_conditional_momentum_signal(closes, 30, 20)
    r = run_hypothesis("H-830: Regime-Conditional Momentum XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-831: Volume-Confirmed Breakout
    sig = volume_confirmed_breakout_signal(closes, volumes, 20)
    r = run_hypothesis("H-831: Volume-Confirmed Breakout XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-832: Funding-OI Composite
    sig = funding_oi_composite_signal(closes, oi_df, funding_df, 7)
    r = run_hypothesis("H-832: Funding-OI Composite XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-833: Variance Ratio
    sig = variance_ratio_signal(closes, 30, lag=5)
    r = run_hypothesis("H-833: Variance Ratio (trending) XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)
    r2 = run_hypothesis("H-833b: Variance Ratio (MR) XS", sig, closes, param_grid_standard, "low_long")
    if r2.get("sharpe", 0) > r.get("sharpe", 0):
        results[-1] = r2

    # H-834: Tail Ratio
    sig = tail_ratio_signal(closes, 30)
    r = run_hypothesis("H-834: Tail Ratio XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-835: Rolling Sharpe
    sig = rolling_sharpe_signal(closes, 30)
    r = run_hypothesis("H-835: Rolling Sharpe XS", sig, closes, param_grid_standard, "high_long")
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
        print(f"  {status:20s} | {name:50s} | Sharpe {sh:6.3f} | {reason}{extra}")

    with open("strategies/h828_to_h835_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nResults saved to strategies/h828_to_h835_results.json")
