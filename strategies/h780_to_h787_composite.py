"""
Batch backtest: H-780 to H-787 — Composite and multi-signal XS signals.

H-780: Rank Average Composite XS — average z-score of momentum + turnover + premium
H-781: Signal Agreement XS — count how many top factors agree on direction
H-782: Residual Alpha XS — alpha after removing momentum (H-012) exposure
H-783: Factor Timing Momentum XS — long factors that worked recently
H-784: Momentum Quality XS — momentum weighted by signal consistency
H-785: Trend + Mean Reversion Composite XS — combine trend following and contrarian
H-786: Volume-Confirmed Strength XS — momentum that's confirmed by multiple volume metrics
H-787: Dynamic Tilt XS — tilt to momentum in trends, to value in ranges
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


def cross_sectional_zscore(df):
    return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1).replace(0, np.nan), axis=0)


# ============================================================
# SIGNAL GENERATORS
# ============================================================

def rank_average_composite_signal(closes, volumes, window):
    """H-780: Z-score average of momentum + turnover + premium (contrarian)."""
    mom = closes.pct_change(window)
    turnover = volumes.rolling(window).mean()
    ret5 = closes.pct_change(5)
    z_mom = cross_sectional_zscore(mom)
    z_turn = cross_sectional_zscore(turnover)
    z_rev = cross_sectional_zscore(-ret5)
    return (z_mom + z_turn + z_rev) / 3


def signal_agreement_signal(closes, volumes, window):
    """H-781: Count of factors that agree on long direction."""
    mom60 = closes.pct_change(60)
    mom20 = closes.pct_change(20)
    vol_mom = volumes.pct_change(20)
    ret = closes.pct_change()
    vol = ret.rolling(20).std()

    mom60_rank = mom60.rank(axis=1, pct=True)
    mom20_rank = mom20.rank(axis=1, pct=True)
    vol_mom_rank = vol_mom.rank(axis=1, pct=True)
    vol_rank = vol.rank(axis=1, pct=True)

    agreement = (
        (mom60_rank > 0.5).astype(float) +
        (mom20_rank > 0.5).astype(float) +
        (vol_mom_rank > 0.5).astype(float) +
        (1 - vol_rank > 0.5).astype(float)
    )
    return agreement


def residual_alpha_signal(closes, window):
    """H-782: Return residual after removing market-weighted momentum."""
    ret = closes.pct_change(window)
    mkt_mom = ret.mean(axis=1)
    betas = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    resid = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(120, len(ret)):
        y_window = ret.iloc[i - 60:i]
        m_window = mkt_mom.iloc[i - 60:i]
        for col in closes.columns:
            y = y_window[col].dropna()
            x = m_window.reindex(y.index)
            mask = np.isfinite(y.values) & np.isfinite(x.values)
            if mask.sum() > 20:
                beta = np.cov(y.values[mask], x.values[mask])[0, 1] / max(np.var(x.values[mask]), 1e-12)
                resid.iloc[i, resid.columns.get_loc(col)] = ret.iloc[i][col] - beta * mkt_mom.iloc[i]
    return resid.rolling(5).mean()


def factor_timing_momentum_signal(closes, volumes):
    """H-783: Weight factors by their recent performance (60d rolling)."""
    mom60 = closes.pct_change(60)
    mom20 = closes.pct_change(20)
    vol_change = volumes.pct_change(20)

    ret1 = closes.pct_change()
    factor_mom_ret = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(80, len(closes)):
        mom_signal = mom60.iloc[i - 20]
        vol_signal = vol_change.iloc[i - 20]
        actual_ret = closes.pct_change(20).iloc[i]

        mom_ranks = mom_signal.rank(pct=True)
        vol_ranks = vol_signal.rank(pct=True)

        mom_perf = (mom_ranks * actual_ret).mean()
        vol_perf = (vol_ranks * actual_ret).mean()

        if abs(mom_perf) > abs(vol_perf):
            factor_mom_ret.iloc[i] = mom60.iloc[i]
        else:
            factor_mom_ret.iloc[i] = vol_change.iloc[i]
    return factor_mom_ret


def momentum_quality_signal(closes, window):
    """H-784: Momentum × consistency (fraction of sub-periods with positive return)."""
    mom = closes.pct_change(window)
    sub_periods = 5
    sub_len = window // sub_periods
    consistency = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for col in closes.columns:
        for i in range(window + 5, len(closes)):
            pos_count = 0
            for s in range(sub_periods):
                sub_ret = closes[col].iloc[i - (sub_periods - s) * sub_len] / closes[col].iloc[i - (sub_periods - s + 1) * sub_len] - 1
                if np.isfinite(sub_ret) and sub_ret > 0:
                    pos_count += 1
            consistency.iloc[i, consistency.columns.get_loc(col)] = pos_count / sub_periods
    return mom * consistency


def trend_plus_reversion_composite(closes, trend_window, reversion_window):
    """H-785: Long-term trend + short-term mean reversion composite."""
    trend = closes.pct_change(trend_window)
    reversion = -closes.pct_change(reversion_window)
    z_trend = cross_sectional_zscore(trend)
    z_rev = cross_sectional_zscore(reversion)
    return 0.6 * z_trend + 0.4 * z_rev


def volume_confirmed_strength_signal(closes, volumes, window):
    """H-786: Momentum confirmed by volume increase and volume consistency."""
    mom = closes.pct_change(window)
    vol_trend = volumes.rolling(window).mean() / volumes.rolling(window * 2).mean().replace(0, np.nan)
    ret = closes.pct_change()
    up_vol = (ret > 0).astype(float) * volumes
    total_vol = volumes
    up_vol_ratio = up_vol.rolling(window).sum() / total_vol.rolling(window).sum().replace(0, np.nan)
    z_mom = cross_sectional_zscore(mom)
    z_vol = cross_sectional_zscore(vol_trend)
    z_upvol = cross_sectional_zscore(up_vol_ratio)
    return (z_mom + z_vol + z_upvol) / 3


def dynamic_tilt_signal(closes, volumes, window):
    """H-787: Momentum in trending markets, contrarian in ranging markets."""
    mom = closes.pct_change(window)
    ret = closes.pct_change()
    mkt_ret = ret.mean(axis=1)
    mkt_trend = mkt_ret.rolling(window).sum()
    mkt_vol = mkt_ret.rolling(window).std()
    trend_strength = mkt_trend.abs() / mkt_vol.replace(0, np.nan)
    is_trending = (trend_strength > trend_strength.rolling(120).median()).astype(float)
    short_reversal = -closes.pct_change(5)
    z_mom = cross_sectional_zscore(mom)
    z_rev = cross_sectional_zscore(short_reversal)
    result = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(window + 5, len(closes)):
        w_trend = is_trending.iloc[i] if np.isfinite(is_trending.iloc[i]) else 0.5
        result.iloc[i] = w_trend * z_mom.iloc[i] + (1 - w_trend) * z_rev.iloc[i]
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
    ]

    results = []

    # H-780: Rank Average Composite
    sig = rank_average_composite_signal(closes, volumes, 30)
    r = run_hypothesis("H-780: Rank Average Composite XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-781: Signal Agreement
    sig = signal_agreement_signal(closes, volumes, 20)
    r = run_hypothesis("H-781: Signal Agreement XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-782: Residual Alpha
    sig = residual_alpha_signal(closes, 20)
    r = run_hypothesis("H-782: Residual Alpha XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-783: Factor Timing Momentum
    sig = factor_timing_momentum_signal(closes, volumes)
    r = run_hypothesis("H-783: Factor Timing Momentum XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-784: Momentum Quality
    sig = momentum_quality_signal(closes, 30)
    r = run_hypothesis("H-784: Momentum Quality XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-785: Trend + Mean Reversion Composite
    sig = trend_plus_reversion_composite(closes, 60, 5)
    r = run_hypothesis("H-785: Trend + Reversion Composite XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-786: Volume-Confirmed Strength
    sig = volume_confirmed_strength_signal(closes, volumes, 20)
    r = run_hypothesis("H-786: Volume-Confirmed Strength XS", sig, closes, param_grid_standard, "high_long")
    results.append(r)

    # H-787: Dynamic Tilt
    sig = dynamic_tilt_signal(closes, volumes, 30)
    r = run_hypothesis("H-787: Dynamic Tilt XS", sig, closes, param_grid_standard, "high_long")
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

    with open("strategies/h780_to_h787_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nResults saved to strategies/h780_to_h787_results.json")
