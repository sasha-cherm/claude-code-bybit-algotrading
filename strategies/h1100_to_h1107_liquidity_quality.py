"""
Batch backtest: H-1100 to H-1107 — Liquidity & Market Quality Signals.
XS signals derived from market microstructure proxies estimated from OHLCV data.

H-1100: Amihud Illiquidity Ratio — |return| / dollar_volume (price impact per unit flow)
H-1101: Roll Spread Estimator — 2*sqrt(-cov(Δp, Δp_lag)), implicit bid-ask from autocovariance
H-1102: Kyle Lambda — regress |Δp| on sqrt(volume), market depth proxy
H-1103: Illiquidity Trend — rate of change of Amihud ratio (improving liquidity = bullish?)
H-1104: Return-Volume Elasticity — how much does 1% volume change move price?
H-1105: Price Impact Asymmetry — Amihud on up days vs down days (buying vs selling pressure)
H-1106: Volume Innovation — residual volume vs predicted (volume surprise)
H-1107: Spread Regime — current Roll spread vs 60d average (cheap/expensive to trade)
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
    common = closes.index
    return closes.loc[common], highs.loc[common], lows.loc[common], opens.loc[common], volumes.loc[common]


def compute_signals(closes, highs, lows, opens, volumes):
    returns = closes.pct_change()
    dollar_vol = volumes.clip(lower=1)
    signals = {}

    # H-1100: Amihud Illiquidity Ratio
    # |return| / dollar_volume, averaged over 20 days
    daily_illiq = returns.abs() / dollar_vol
    amihud = daily_illiq.rolling(20).mean()
    signals["amihud"] = amihud

    # H-1101: Roll Spread Estimator
    # Estimate bid-ask from serial covariance of price changes
    price_change = closes.diff()
    roll_spread = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        for i in range(25, len(closes)):
            window = price_change[col].iloc[i-20:i]
            if window.isna().sum() > 5:
                continue
            cov_val = window.iloc[1:].values @ window.iloc[:-1].values / (len(window) - 1)
            if cov_val < 0:
                roll_spread.loc[closes.index[i], col] = 2 * np.sqrt(-cov_val) / closes[col].iloc[i]
            else:
                roll_spread.loc[closes.index[i], col] = 0.0
    signals["roll_spread"] = roll_spread

    # H-1102: Kyle Lambda — market depth proxy
    # Regress |return| on sqrt(dollar_volume) over rolling window
    kyle_lambda = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        for i in range(30, len(closes)):
            y = returns[col].iloc[i-20:i].abs().values
            x = np.sqrt(dollar_vol[col].iloc[i-20:i].values)
            mask = np.isfinite(y) & np.isfinite(x) & (x > 0)
            if mask.sum() < 10:
                continue
            slope, _, _, _, _ = stats.linregress(x[mask], y[mask])
            kyle_lambda.loc[closes.index[i], col] = slope
    signals["kyle_lambda"] = kyle_lambda

    # H-1103: Illiquidity Trend — slope of Amihud over 40 days
    illiq_trend = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    amihud_filled = amihud.copy()
    for col in closes.columns:
        for i in range(60, len(closes)):
            vals = amihud_filled[col].iloc[i-40:i].dropna().values
            if len(vals) < 20:
                continue
            x = np.arange(len(vals))
            slope, _, _, _, _ = stats.linregress(x, vals)
            illiq_trend.loc[closes.index[i], col] = slope
    signals["illiq_trend"] = illiq_trend

    # H-1104: Return-Volume Elasticity
    # Rolling regression: return ~ β * log(volume_change)
    log_vol_change = np.log(dollar_vol / dollar_vol.shift(1).clip(lower=1))
    elasticity = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        for i in range(30, len(closes)):
            y = returns[col].iloc[i-20:i].values
            x = log_vol_change[col].iloc[i-20:i].values
            mask = np.isfinite(y) & np.isfinite(x)
            if mask.sum() < 10:
                continue
            slope, _, _, _, _ = stats.linregress(x[mask], y[mask])
            elasticity.loc[closes.index[i], col] = slope
    signals["rv_elasticity"] = elasticity

    # H-1105: Price Impact Asymmetry — Amihud on up vs down days
    up_illiq = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    down_illiq = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        for i in range(30, len(closes)):
            rets = returns[col].iloc[i-20:i]
            illiq = daily_illiq[col].iloc[i-20:i]
            up_mask = rets > 0
            down_mask = rets < 0
            if up_mask.sum() >= 3 and down_mask.sum() >= 3:
                up_avg = illiq[up_mask].mean()
                down_avg = illiq[down_mask].mean()
                if down_avg > 0:
                    up_illiq.loc[closes.index[i], col] = up_avg / down_avg
    impact_asym = up_illiq
    signals["impact_asymmetry"] = impact_asym

    # H-1106: Volume Innovation — residual of volume vs 20d MA
    vol_ma = dollar_vol.rolling(20).mean()
    vol_std = dollar_vol.rolling(20).std()
    vol_innovation = (dollar_vol - vol_ma) / vol_std.clip(lower=1)
    signals["vol_innovation"] = vol_innovation

    # H-1107: Spread Regime — current Roll spread vs 60d average
    roll_spread_ma = roll_spread.rolling(60).mean()
    roll_spread_std = roll_spread.rolling(60).std().clip(lower=1e-10)
    spread_regime = (roll_spread - roll_spread_ma) / roll_spread_std
    signals["spread_regime"] = spread_regime

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
    closes, highs, lows, opens, volumes = load_daily()
    print(f"Loaded {len(closes)} bars, {len(closes.columns)} assets")
    print()

    print("Computing signals...")
    signals = compute_signals(closes, highs, lows, opens, volumes)
    print(f"Got {len(signals)} signal types")
    print()

    feature_map = {
        "H-1100": ("amihud", "Amihud Illiquidity Ratio"),
        "H-1101": ("roll_spread", "Roll Spread Estimator"),
        "H-1102": ("kyle_lambda", "Kyle Lambda (Market Depth)"),
        "H-1103": ("illiq_trend", "Illiquidity Trend"),
        "H-1104": ("rv_elasticity", "Return-Volume Elasticity"),
        "H-1105": ("impact_asymmetry", "Price Impact Asymmetry"),
        "H-1106": ("vol_innovation", "Volume Innovation"),
        "H-1107": ("spread_regime", "Spread Regime"),
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
