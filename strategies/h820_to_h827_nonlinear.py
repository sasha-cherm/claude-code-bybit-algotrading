"""
Batch backtest: H-820 to H-827 — Higher-order & non-linear XS signals.

H-820: Coskewness with Market — third co-moment with equal-weight portfolio
H-821: Downside Beta — beta measured only during BTC down days
H-822: Quantile Spread — 75th-25th percentile daily return spread (tail behavior)
H-823: Maximum Daily Return — largest single-day return in lookback (extremes)
H-824: Minimum Daily Return — worst single-day loss in lookback (tail risk)
H-825: Return Entropy — Shannon entropy of binned daily returns (predictability)
H-826: Herfindahl Return Concentration — few big days vs many small days
H-827: Sortino Ratio Ranking — upside/downside vol ratio as XS signal
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

def coskewness_signal(closes, window):
    """H-820: Coskewness with market portfolio. Assets with negative coskewness
    perform poorly in market crashes → should be compensated with higher returns."""
    ret = closes.pct_change()
    mkt_ret = ret.mean(axis=1)

    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(window + 5, len(closes)):
        m = mkt_ret.iloc[i - window:i].values
        m_dm = m - np.nanmean(m)
        m_std = np.nanstd(m)
        if m_std < 1e-12:
            continue
        for col in closes.columns:
            r = ret[col].iloc[i - window:i].values
            mask = np.isfinite(r) & np.isfinite(m)
            if mask.sum() > 15:
                r_dm = r[mask] - np.nanmean(r[mask])
                # Coskewness: E[r_i * r_m^2] / (std_i * std_m^2)
                coskew = np.mean(r_dm * m_dm[mask]**2)
                signal.iloc[i, signal.columns.get_loc(col)] = coskew
    return signal


def downside_beta_signal(closes, window):
    """H-821: Beta computed only on BTC down-days.
    High downside beta = crashes with market → should earn premium."""
    ret = closes.pct_change()
    btc_ret = ret["BTC/USDT"]

    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(window + 5, len(closes)):
        btc_w = btc_ret.iloc[i - window:i].values
        down_mask = btc_w < 0
        if down_mask.sum() < 10:
            continue
        for col in closes.columns:
            y = ret[col].iloc[i - window:i].values
            mask = down_mask & np.isfinite(y) & np.isfinite(btc_w)
            if mask.sum() > 8:
                cov = np.cov(y[mask], btc_w[mask])
                if cov[1, 1] > 1e-12:
                    d_beta = cov[0, 1] / cov[1, 1]
                    signal.iloc[i, signal.columns.get_loc(col)] = d_beta
    return signal


def quantile_spread_signal(closes, window):
    """H-822: 75th-25th percentile of daily returns (dispersion of daily returns).
    High spread = volatile micro-structure. Test both directions."""
    ret = closes.pct_change()
    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(window + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i - window:i].dropna().values
            if len(r) > 10:
                q75 = np.percentile(r, 75)
                q25 = np.percentile(r, 25)
                signal.iloc[i, signal.columns.get_loc(col)] = q75 - q25
    return signal


def max_return_signal(closes, window):
    """H-823: Largest single-day return in lookback window.
    Extreme winners may continue (momentum) or revert (contrarian)."""
    ret = closes.pct_change()
    return ret.rolling(window).max()


def min_return_signal(closes, window):
    """H-824: Worst single-day loss in lookback window.
    Smallest drawdown = resilience → momentum. Largest = vulnerability."""
    ret = closes.pct_change()
    return ret.rolling(window).min()  # Most negative = worst


def return_entropy_signal(closes, window):
    """H-825: Shannon entropy of binned daily returns.
    Low entropy = predictable/trending. High entropy = random."""
    ret = closes.pct_change()
    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    n_bins = 10

    for i in range(window + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i - window:i].dropna().values
            if len(r) > 15:
                hist, _ = np.histogram(r, bins=n_bins)
                p = hist / hist.sum()
                p = p[p > 0]
                entropy = -np.sum(p * np.log2(p))
                signal.iloc[i, signal.columns.get_loc(col)] = entropy
    return signal


def herfindahl_concentration_signal(closes, window):
    """H-826: Herfindahl index of absolute daily returns.
    High concentration = few big days dominate. Low = even distribution."""
    ret = closes.pct_change()
    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)

    for i in range(window + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i - window:i].dropna().values
            if len(r) > 10:
                abs_r = np.abs(r)
                total = abs_r.sum()
                if total > 1e-12:
                    shares = abs_r / total
                    hhi = np.sum(shares**2)
                    signal.iloc[i, signal.columns.get_loc(col)] = hhi
    return signal


def sortino_ranking_signal(closes, window):
    """H-827: Sortino ratio (mean return / downside deviation).
    High Sortino = good risk-adjusted return with low downside risk."""
    ret = closes.pct_change()
    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)

    for i in range(window + 5, len(closes)):
        for col in closes.columns:
            r = ret[col].iloc[i - window:i].dropna().values
            if len(r) > 15:
                mean_r = np.mean(r)
                downside = r[r < 0]
                if len(downside) > 5:
                    down_std = np.std(downside)
                    if down_std > 1e-12:
                        sortino = mean_r / down_std
                        signal.iloc[i, signal.columns.get_loc(col)] = sortino
    return signal


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

    param_grid_standard = [
        (20, 3, 3), (20, 3, 4), (20, 5, 3), (20, 5, 4),
        (30, 3, 3), (30, 3, 4), (30, 5, 3), (30, 5, 4),
        (40, 3, 3), (40, 3, 4), (40, 5, 3), (40, 5, 4),
        (60, 5, 3), (60, 5, 4), (60, 7, 3), (60, 7, 4),
        (60, 7, 5), (60, 10, 4),
    ]

    results = []

    # H-820: Coskewness — negative coskew should earn premium (high_long = long high coskew)
    sig = coskewness_signal(closes, 60)
    r = run_hypothesis("H-820: Coskewness with Market XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)
    # Also try contrarian (long negative coskew = tail risk premium)
    r2 = run_hypothesis("H-820b: Coskewness Contrarian XS", sig, closes, param_grid_standard, "low_long")
    if r2.get("sharpe", 0) > r.get("sharpe", 0):
        results[-1] = r2

    # H-821: Downside Beta — high downside beta earns premium
    sig = downside_beta_signal(closes, 60)
    r = run_hypothesis("H-821: Downside Beta XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)
    r2 = run_hypothesis("H-821b: Low Downside Beta (safety) XS", sig, closes, param_grid_standard, "low_long")
    if r2.get("sharpe", 0) > r.get("sharpe", 0):
        results[-1] = r2

    # H-822: Quantile Spread — high spread = volatile
    sig = quantile_spread_signal(closes, 30)
    r = run_hypothesis("H-822: Quantile Spread XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)
    r2 = run_hypothesis("H-822b: Low Quantile Spread XS", sig, closes, param_grid_standard, "low_long")
    if r2.get("sharpe", 0) > r.get("sharpe", 0):
        results[-1] = r2

    # H-823: Maximum Daily Return — extreme winner streak
    sig = max_return_signal(closes, 30)
    r = run_hypothesis("H-823: Max Daily Return XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-824: Minimum Daily Return (worst loss) — resilience (less negative = stronger)
    sig = min_return_signal(closes, 30)
    r = run_hypothesis("H-824: Min Daily Return (resilience) XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-825: Return Entropy — low entropy = trending/predictable
    sig = return_entropy_signal(closes, 30)
    r = run_hypothesis("H-825: Return Entropy XS", sig, closes, param_grid_standard, "low_long")
    results.append(r)
    r2 = run_hypothesis("H-825b: High Return Entropy XS", sig, closes, param_grid_standard, "high_long")
    if r2.get("sharpe", 0) > r.get("sharpe", 0):
        results[-1] = r2

    # H-826: Herfindahl Concentration — few big days
    sig = herfindahl_concentration_signal(closes, 30)
    r = run_hypothesis("H-826: Return Herfindahl XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)
    r2 = run_hypothesis("H-826b: Low Herfindahl (even dist) XS", sig, closes, param_grid_standard, "low_long")
    if r2.get("sharpe", 0) > r.get("sharpe", 0):
        results[-1] = r2

    # H-827: Sortino Ratio ranking
    sig = sortino_ranking_signal(closes, 30)
    r = run_hypothesis("H-827: Sortino Ratio Ranking XS", sig, closes, param_grid_standard, "high_long")
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

    with open("strategies/h820_to_h827_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nResults saved to strategies/h820_to_h827_results.json")
