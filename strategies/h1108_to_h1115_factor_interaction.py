"""
Batch backtest: H-1108 to H-1115 — Factor Interaction Signals.
XS signals built by combining two independent factors via z-score multiplication.
Tests whether combining factors produces alpha beyond individual components.

H-1108: Momentum × Low Vol — momentum winners with low volatility (quality momentum)
H-1109: Volume Surge × Trend Quality — volume confirming structural uptrend (higher lows)
H-1110: Size × Momentum — large cap momentum vs small cap (size-conditioned momentum)
H-1111: Momentum × Funding Carry — momentum with positive carry (aligned incentives)
H-1112: Vol Expansion × Momentum Direction — expanding vol in momentum direction (breakout)
H-1113: Short-Term Reversal × Low Turnover — reversal filtered by low turnover (less noise)
H-1114: Trend Linearity × Low Kurtosis — smooth trends with thin tails (stable trends)
H-1115: Return Stability × Vol Persistence — consistent returns with persistent vol patterns
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
    closes, volumes, highs, lows = {}, {}, {}, {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_1d.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            closes[f"{ticker}/USDT"] = df["close"]
            volumes[f"{ticker}/USDT"] = df["volume"] * df["close"]
            highs[f"{ticker}/USDT"] = df["high"]
            lows[f"{ticker}/USDT"] = df["low"]
        except:
            pass
    closes = pd.DataFrame(closes).sort_index().dropna(how="all")
    volumes = pd.DataFrame(volumes).sort_index().dropna(how="all")
    highs = pd.DataFrame(highs).sort_index().dropna(how="all")
    lows = pd.DataFrame(lows).sort_index().dropna(how="all")
    return closes, volumes, highs, lows


def xs_zscore(df):
    mu = df.mean(axis=1)
    sigma = df.std(axis=1).clip(lower=1e-10)
    return df.sub(mu, axis=0).div(sigma, axis=0)


def compute_signals(closes, volumes, highs, lows):
    returns = closes.pct_change()
    signals = {}

    # Base factors
    mom60 = returns.rolling(60).sum()
    vol20 = returns.rolling(20).std()
    vol_ratio = (volumes / volumes.rolling(20).mean().clip(lower=1))
    dollar_vol = volumes.rolling(20).mean()
    turnover = volumes / volumes.rolling(60).mean().clip(lower=1)

    # H-1108: Momentum × Low Vol
    z_mom = xs_zscore(mom60)
    z_vol = xs_zscore(vol20)
    signals["mom_x_lowvol"] = z_mom * (-z_vol)  # high mom, low vol

    # H-1109: Volume Surge × Trend Quality (Higher Lows)
    # Higher lows count
    hl_count = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for lag in [5, 10, 15, 20]:
        hl_count += (lows > lows.shift(lag)).astype(float)
    hl_count = hl_count / 4.0
    z_vol_surge = xs_zscore(vol_ratio)
    z_hl = xs_zscore(hl_count)
    signals["vol_x_trend"] = z_vol_surge * z_hl

    # H-1110: Size × Momentum
    z_size = xs_zscore(dollar_vol)
    signals["size_x_mom"] = z_size * z_mom

    # H-1111: Momentum × Funding Carry
    # Use funding rate data if available, otherwise use overnight return as proxy
    overnight_ret = closes.pct_change().copy()
    carry_proxy = overnight_ret.rolling(20).mean()
    z_carry = xs_zscore(carry_proxy)
    signals["mom_x_carry"] = z_mom * z_carry

    # H-1112: Vol Expansion × Momentum Direction
    vol_expansion = vol20 / vol20.shift(20).clip(lower=1e-10)
    z_vol_exp = xs_zscore(vol_expansion)
    mom_sign = np.sign(mom60)
    signals["vol_exp_x_mom_dir"] = z_vol_exp * mom_sign

    # H-1113: Short-Term Reversal × Low Turnover
    rev5 = -returns.rolling(5).sum()
    z_rev = xs_zscore(rev5)
    z_turnover = xs_zscore(turnover)
    signals["rev_x_low_turnover"] = z_rev * (-z_turnover)

    # H-1114: Trend Linearity × Low Kurtosis
    trend_lin = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    ret_kurt = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        for i in range(65, len(closes)):
            rets = returns[col].iloc[i-60:i].dropna().values
            if len(rets) < 40:
                continue
            cum_ret = np.cumsum(rets)
            x = np.arange(len(cum_ret))
            _, _, r_val, _, _ = stats.linregress(x, cum_ret)
            trend_lin.loc[closes.index[i], col] = r_val ** 2
            if np.std(rets) > 0:
                ret_kurt.loc[closes.index[i], col] = stats.kurtosis(rets, fisher=True)
    z_lin = xs_zscore(trend_lin)
    z_kurt = xs_zscore(ret_kurt)
    signals["trend_x_lowkurt"] = z_lin * (-z_kurt)

    # H-1115: Return Stability × Vol Persistence
    # Return stability = std of rolling 5d returns / std of daily returns
    ret_5d = returns.rolling(5).sum()
    ret_stability = ret_5d.rolling(20).std() / returns.rolling(20).std().clip(lower=1e-10)
    # Vol persistence = autocorrelation of daily vol
    vol_persist = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    abs_ret = returns.abs()
    for col in closes.columns:
        for i in range(30, len(closes)):
            window = abs_ret[col].iloc[i-20:i].values
            if len(window) < 20 or np.std(window) == 0:
                continue
            vol_persist.loc[closes.index[i], col] = np.corrcoef(window[:-1], window[1:])[0, 1]
    z_stab = xs_zscore(ret_stability)
    z_vp = xs_zscore(vol_persist)
    signals["stability_x_volpersist"] = z_stab * z_vp

    return signals


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
                 n_folds=5, test_days=120):
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
    all_positive = 0
    all_total = 0
    for direction in directions:
        for n_ls in n_ls_list:
            for rebal in rebal_list:
                pnl = xs_backtest(closes_c, signal_c, lookback, rebal, n_ls, direction)
                m = compute_metrics(pnl)
                all_total += 1
                if m["sharpe"] > 0:
                    all_positive += 1
                if m["sharpe"] > best.get("sharpe", -999):
                    best = {**m, "direction": direction, "n_ls": n_ls, "rebal": rebal,
                            "pnl": pnl, "closes_c": closes_c, "signal_c": signal_c}
    is_pct = f"{100*all_positive//all_total}%" if all_total > 0 else "N/A"
    if best["sharpe"] <= 0:
        print(f"  {name}: IS {is_pct} ({all_positive}/{all_total} positive) — SKIP")
        return None
    pnl = best["pnl"]
    wf = walk_forward(best["closes_c"], best["signal_c"], lookback, best["rebal"],
                      best["n_ls"], best["direction"])
    sh1, sh2, p_val = split_half_test(pnl)
    corr = h012_correlation(best["closes_c"], best["signal_c"], lookback, best["rebal"],
                            best["n_ls"], best["direction"])
    wf_pos = sum(1 for x in wf if x > 0)
    print(f"  {name}: IS Sharpe {best['sharpe']:.3f} | Ann {best['annual_ret']:.1f}% | DD {best['max_dd']:.1f}% | "
          f"Dir={best['direction']} | IS {is_pct} ({all_positive}/{all_total}) | "
          f"WF {wf_pos}/{len(wf)} {[round(x,2) for x in wf]} | SH {sh1:.3f}/{sh2:.3f} p={p_val:.3f} | "
          f"H012 corr {corr:.3f} | N={len(pnl)}")
    return {
        "sharpe": best["sharpe"], "annual_ret": best["annual_ret"],
        "max_dd": best["max_dd"], "direction": best["direction"],
        "n_ls": best["n_ls"], "rebal": best["rebal"],
        "wf": wf, "wf_pos": wf_pos, "wf_total": len(wf),
        "sh1": sh1, "sh2": sh2, "p_val": round(p_val, 4),
        "h012_corr": corr, "n_bars": len(pnl),
        "is_positive_pct": is_pct
    }


def main():
    print("Loading data...")
    closes, volumes, highs, lows = load_daily()
    print(f"Loaded {len(closes)} bars, {len(closes.columns)} assets")
    print()

    print("Computing signals...")
    signals = compute_signals(closes, volumes, highs, lows)
    print(f"Got {len(signals)} signal types")
    print()

    feature_map = {
        "H-1108": ("mom_x_lowvol", "Momentum × Low Vol"),
        "H-1109": ("vol_x_trend", "Volume Surge × Trend Quality"),
        "H-1110": ("size_x_mom", "Size × Momentum"),
        "H-1111": ("mom_x_carry", "Momentum × Carry Proxy"),
        "H-1112": ("vol_exp_x_mom_dir", "Vol Expansion × Mom Direction"),
        "H-1113": ("rev_x_low_turnover", "Reversal × Low Turnover"),
        "H-1114": ("trend_x_lowkurt", "Trend Linearity × Low Kurtosis"),
        "H-1115": ("stability_x_volpersist", "Return Stability × Vol Persistence"),
    }

    results = {}
    lookback = 60

    for hyp_id, (sig_name, desc) in feature_map.items():
        print(f"\n{hyp_id}: {desc}")
        sig_df = signals[sig_name]
        r = run_signal(hyp_id, sig_df, closes, lookback,
                       ["high_long", "low_long"], [3, 4], [5, 7])
        if r:
            results[hyp_id] = r

    print(f"\n{'='*80}")
    print(f"BATCH SUMMARY: {len(results)}/{8} signals with positive IS Sharpe")
    for name, r in sorted(results.items(), key=lambda x: -x[1]["sharpe"]):
        status = "CONFIRMED" if r["wf_pos"] >= max(2, r["wf_total"] * 0.5) and r["p_val"] < 0.1 else "BORDERLINE" if r["wf_pos"] >= 2 else "REJECTED"
        print(f"  {name}: Sharpe {r['sharpe']:.3f} | WF {r['wf_pos']}/{r['wf_total']} | p={r['p_val']:.3f} | "
              f"corr {r['h012_corr']:.3f} | SH {r['sh1']:.2f}/{r['sh2']:.2f} | {status}")


if __name__ == "__main__":
    main()
