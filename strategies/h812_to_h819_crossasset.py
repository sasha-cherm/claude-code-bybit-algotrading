"""
Batch backtest: H-812 to H-819 — Cross-asset information flow XS signals.

H-812: BTC Return Propagation — BTC lagged return predicts altcoin next-day (rank by BTC sensitivity)
H-813: Market Breadth Momentum — rate of change of breadth (% positive assets)
H-814: Rank Velocity — speed of rank position changes (fast movers vs stable)
H-815: Pairwise Comovement Score — asset's avg rolling correlation with all others
H-816: BTC-Relative Momentum — momentum relative to BTC (not absolute)
H-817: Cross-Asset Vol Spillover — BTC vol change predicts altcoin vol change
H-818: Return Synchronicity — fraction of days asset agrees with market direction
H-819: Idiosyncratic Momentum — momentum of residual after removing BTC beta
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

def btc_return_propagation_signal(closes, window):
    """H-812: Rolling beta of each asset to BTC lagged returns.
    High beta = reacts more to BTC moves next day → momentum-like effect."""
    ret = closes.pct_change()
    btc_ret = ret["BTC/USDT"]
    btc_lag = btc_ret.shift(1)

    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(window + 5, len(closes)):
        btc_w = btc_lag.iloc[i - window:i].values
        for col in closes.columns:
            if col == "BTC/USDT":
                continue
            y = ret[col].iloc[i - window:i].values
            mask = np.isfinite(btc_w) & np.isfinite(y)
            if mask.sum() > 15:
                # Predicted next return based on today's BTC return
                beta = np.cov(y[mask], btc_w[mask])[0, 1] / max(np.var(btc_w[mask]), 1e-12)
                signal.iloc[i, signal.columns.get_loc(col)] = beta * btc_ret.iloc[i]
    return signal


def market_breadth_momentum_signal(closes, window):
    """H-813: Rate of change of market breadth (fraction of assets with positive N-day return)."""
    ret_n = closes.pct_change(5)  # 5-day returns
    breadth = (ret_n > 0).astype(float).mean(axis=1)  # market breadth
    breadth_mom = breadth.diff(window)  # rate of change of breadth

    # When breadth improving, long strongest momentum; when declining, short weakest
    mom = closes.pct_change(window)
    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(window + 10, len(closes)):
        bm = breadth_mom.iloc[i]
        if np.isfinite(bm):
            # Scale momentum by breadth direction
            signal.iloc[i] = mom.iloc[i] * np.sign(bm)
    return signal


def rank_velocity_signal(closes, window):
    """H-814: Speed of rank changes. Fast-rising assets continue rising."""
    ret = closes.pct_change(window)
    ranks = ret.rank(axis=1, pct=True)
    rank_change = ranks.diff(5)  # 5-day rank change
    return rank_change.rolling(window // 2).mean()


def pairwise_comovement_signal(closes, window):
    """H-815: Asset's average rolling correlation with all others.
    Low comovement = idiosyncratic → potential alpha."""
    ret = closes.pct_change()
    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)

    for i in range(window + 5, len(closes)):
        r_window = ret.iloc[i - window:i]
        corr_matrix = r_window.corr()
        for col in closes.columns:
            if col in corr_matrix.columns:
                avg_corr = corr_matrix[col].drop(col, errors='ignore').mean()
                signal.iloc[i, signal.columns.get_loc(col)] = avg_corr
    return signal


def btc_relative_momentum_signal(closes, window):
    """H-816: Momentum relative to BTC. Long outperformers, short underperformers."""
    ret = closes.pct_change(window)
    btc_ret = ret["BTC/USDT"]
    relative = ret.sub(btc_ret, axis=0)
    return relative


def vol_spillover_signal(closes, window):
    """H-817: BTC vol change → predicted altcoin vol regime.
    When BTC vol rises, long low-vol assets (shelter); when falls, long high-vol (risk-on)."""
    ret = closes.pct_change()
    btc_vol = ret["BTC/USDT"].rolling(window).std()
    btc_vol_change = btc_vol.pct_change(5)

    asset_vol = ret.rolling(window).std()
    vol_rank = asset_vol.rank(axis=1, pct=True)

    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(window + 10, len(closes)):
        bvc = btc_vol_change.iloc[i]
        if np.isfinite(bvc):
            # When BTC vol rising: long low vol (shelter), short high vol
            # When BTC vol falling: long high vol (risk-on), short low vol
            signal.iloc[i] = -np.sign(bvc) * vol_rank.iloc[i]
    return signal


def return_synchronicity_signal(closes, window):
    """H-818: Fraction of days asset returns have same sign as market returns.
    Low synchronicity = potential contrarian opportunity."""
    ret = closes.pct_change()
    mkt_ret = ret.mean(axis=1)

    same_sign = ret.apply(lambda x: (np.sign(x) == np.sign(mkt_ret)).astype(float))
    sync = same_sign.rolling(window).mean()
    return sync


def idiosyncratic_momentum_signal(closes, window):
    """H-819: Momentum of residuals after removing BTC factor.
    Pure idiosyncratic return momentum."""
    ret = closes.pct_change()
    btc_ret = ret["BTC/USDT"]

    residuals = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(65, len(closes)):
        btc_w = btc_ret.iloc[i - 60:i].values
        for col in closes.columns:
            y = ret[col].iloc[i - 60:i].values
            mask = np.isfinite(btc_w) & np.isfinite(y)
            if mask.sum() > 20:
                beta = np.cov(y[mask], btc_w[mask])[0, 1] / max(np.var(btc_w[mask]), 1e-12)
                residuals.iloc[i, residuals.columns.get_loc(col)] = ret[col].iloc[i] - beta * btc_ret.iloc[i]

    # Momentum of residuals
    return residuals.rolling(window).sum()


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

    # H-812: BTC Return Propagation
    sig = btc_return_propagation_signal(closes, 30)
    r = run_hypothesis("H-812: BTC Return Propagation XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-813: Market Breadth Momentum
    sig = market_breadth_momentum_signal(closes, 20)
    r = run_hypothesis("H-813: Market Breadth Momentum XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-814: Rank Velocity
    sig = rank_velocity_signal(closes, 30)
    r = run_hypothesis("H-814: Rank Velocity XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-815: Pairwise Comovement Score — low comovement = long (idiosyncratic potential)
    sig = pairwise_comovement_signal(closes, 30)
    r = run_hypothesis("H-815: Pairwise Comovement (contrarian) XS", sig, closes, param_grid_standard, "low_long")
    results.append(r)
    # Also try high_long
    r2 = run_hypothesis("H-815b: Pairwise Comovement (momentum) XS", sig, closes, param_grid_standard, "high_long")
    if r2.get("sharpe", 0) > r.get("sharpe", 0):
        results[-1] = r2

    # H-816: BTC-Relative Momentum
    sig = btc_relative_momentum_signal(closes, 30)
    r = run_hypothesis("H-816: BTC-Relative Momentum XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-817: Vol Spillover
    sig = vol_spillover_signal(closes, 20)
    r = run_hypothesis("H-817: Vol Spillover XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-818: Return Synchronicity — low sync = contrarian potential
    sig = return_synchronicity_signal(closes, 20)
    r = run_hypothesis("H-818: Return Synchronicity XS", sig, closes, param_grid_standard, "low_long")
    results.append(r)
    # Also try high_long
    r2 = run_hypothesis("H-818b: Return Synchronicity (mom) XS", sig, closes, param_grid_standard, "high_long")
    if r2.get("sharpe", 0) > r.get("sharpe", 0):
        results[-1] = r2

    # H-819: Idiosyncratic Momentum
    sig = idiosyncratic_momentum_signal(closes, 20)
    r = run_hypothesis("H-819: Idiosyncratic Momentum XS", sig, closes, param_grid_standard, "high_long")
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

    with open("strategies/h812_to_h819_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nResults saved to strategies/h812_to_h819_results.json")
