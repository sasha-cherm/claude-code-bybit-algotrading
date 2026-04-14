"""
Batch backtest: H-1140 to H-1147 — Lead-Lag & Cross-Asset Spillover.
XS signals based on information transmission between assets.

H-1140: BTC Lagged Return — BTC return predicts alt returns (long alts with high BTC-beta when BTC up)
H-1141: ETH-BTC Spread Momentum — rolling ETH/BTC ratio change. Risk-on when ETH outperforms BTC.
H-1142: Residual Return Persistence — cumulative residual (after BTC beta removal) over 5d
H-1143: Large-Cap Lead — equal-weight top-3 cap return predicts smaller assets next period
H-1144: Return Synchronicity — R² of asset return vs equal-weight market. Low R² = more independent info.
H-1145: Volume Lead-Lag — does volume spike in large caps predict returns in smaller caps?
H-1146: Cross-Momentum Sensitivity — how responsive is asset return to market-wide momentum?
H-1147: Idiosyncratic Volatility Ratio — idio vol / total vol. High = more asset-specific risk, less systematic.
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
    btc_ret = returns["BTC/USDT"] if "BTC/USDT" in returns.columns else returns.iloc[:, 0]
    eth_ret = returns["ETH/USDT"] if "ETH/USDT" in returns.columns else returns.iloc[:, 1]
    mkt_ret = returns.mean(axis=1)
    signals = {}

    # H-1140: BTC Lagged Return × asset beta
    # Idea: when BTC goes up, high-beta alts should follow next day
    btc_lag_signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        btc_var = btc_ret.rolling(30).var().clip(lower=1e-10)
        cov_col = returns[col].rolling(30).cov(btc_ret)
        beta = cov_col / btc_var
        btc_lag_signal[col] = beta * btc_ret.shift(1)
    signals["btc_lag_signal"] = btc_lag_signal

    # H-1141: ETH-BTC Spread Momentum — rolling 20d change in ETH/BTC ratio
    if "ETH/USDT" in closes.columns and "BTC/USDT" in closes.columns:
        eth_btc = closes["ETH/USDT"] / closes["BTC/USDT"]
        eth_btc_mom = eth_btc.pct_change(20)
        spread_signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
        for col in closes.columns:
            beta = returns[col].rolling(30).cov(btc_ret) / btc_ret.rolling(30).var().clip(lower=1e-10)
            spread_signal[col] = eth_btc_mom * beta
        signals["eth_btc_spread"] = spread_signal
    else:
        signals["eth_btc_spread"] = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)

    # H-1142: Residual Return Persistence — 5d cumulative residual after BTC beta removal
    resid_5d = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        if col == "BTC/USDT":
            continue
        btc_var = btc_ret.rolling(30).var().clip(lower=1e-10)
        beta = returns[col].rolling(30).cov(btc_ret) / btc_var
        alpha = returns[col].rolling(30).mean() - beta * btc_ret.rolling(30).mean()
        daily_resid = returns[col] - beta * btc_ret - alpha
        resid_5d[col] = daily_resid.rolling(5).sum()
    signals["resid_5d"] = resid_5d

    # H-1143: Large-Cap Lead — EW top-3 market cap proxy (BTC/ETH/SOL) return
    top3_cols = [c for c in ["BTC/USDT", "ETH/USDT", "SOL/USDT"] if c in returns.columns]
    if len(top3_cols) >= 2:
        top3_ret = returns[top3_cols].mean(axis=1)
        largecap_lead = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
        for col in closes.columns:
            if col in top3_cols:
                continue
            beta = returns[col].rolling(30).cov(top3_ret) / top3_ret.rolling(30).var().clip(lower=1e-10)
            largecap_lead[col] = beta * top3_ret.rolling(3).sum().shift(1)
        signals["largecap_lead"] = largecap_lead
    else:
        signals["largecap_lead"] = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)

    # H-1144: Return Synchronicity — R² of asset vs equal-weight market over 30d
    synchronicity = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        for i in range(60, len(closes)):
            y = returns[col].iloc[i-30:i].values
            x = mkt_ret.iloc[i-30:i].values
            mask = np.isfinite(y) & np.isfinite(x)
            if mask.sum() < 15:
                continue
            _, _, r_val, _, _ = stats.linregress(x[mask], y[mask])
            synchronicity.loc[closes.index[i], col] = r_val ** 2
    signals["synchronicity"] = synchronicity

    # H-1145: Volume Lead-Lag — normalized BTC volume change × asset beta
    btc_vol = volumes["BTC/USDT"] if "BTC/USDT" in volumes.columns else volumes.iloc[:, 0]
    btc_vol_z = (btc_vol - btc_vol.rolling(20).mean()) / btc_vol.rolling(20).std().clip(lower=1)
    vol_lead = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        btc_var = btc_ret.rolling(30).var().clip(lower=1e-10)
        beta = returns[col].rolling(30).cov(btc_ret) / btc_var
        vol_lead[col] = btc_vol_z.shift(1) * beta
    signals["vol_lead"] = vol_lead

    # H-1146: Cross-Momentum Sensitivity — β of asset return on market 5d momentum
    mkt_mom_5d = mkt_ret.rolling(5).sum()
    cross_mom_sens = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        for i in range(60, len(closes)):
            y = returns[col].iloc[i-30:i].values
            x = mkt_mom_5d.iloc[i-30:i].values
            mask = np.isfinite(y) & np.isfinite(x)
            if mask.sum() < 15:
                continue
            slope, _, _, _, _ = stats.linregress(x[mask], y[mask])
            cross_mom_sens.loc[closes.index[i], col] = slope
    signals["cross_mom_sens"] = cross_mom_sens

    # H-1147: Idiosyncratic Volatility Ratio — idio vol / total vol
    idio_ratio = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        for i in range(60, len(closes)):
            y = returns[col].iloc[i-30:i].values
            x = mkt_ret.iloc[i-30:i].values
            mask = np.isfinite(y) & np.isfinite(x)
            if mask.sum() < 15:
                continue
            slope, intercept, _, _, _ = stats.linregress(x[mask], y[mask])
            resid = y[mask] - (slope * x[mask] + intercept)
            total_var = np.var(y[mask])
            idio_var = np.var(resid)
            if total_var > 0:
                idio_ratio.loc[closes.index[i], col] = idio_var / total_var
    signals["idio_ratio"] = idio_ratio

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
        "H-1140": ("btc_lag_signal", "BTC Lagged Return × Beta"),
        "H-1141": ("eth_btc_spread", "ETH-BTC Spread Momentum"),
        "H-1142": ("resid_5d", "Residual Return Persistence (5d)"),
        "H-1143": ("largecap_lead", "Large-Cap Lead Signal"),
        "H-1144": ("synchronicity", "Return Synchronicity (R²)"),
        "H-1145": ("vol_lead", "Volume Lead-Lag (BTC vol → alt returns)"),
        "H-1146": ("cross_mom_sens", "Cross-Momentum Sensitivity"),
        "H-1147": ("idio_ratio", "Idiosyncratic Volatility Ratio"),
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
