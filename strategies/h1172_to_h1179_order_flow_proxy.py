"""
Batch backtest: H-1172 to H-1179 — Order Flow Proxy Signals.
Inferring order flow/buying pressure from daily OHLCV data.

H-1172: Buy Pressure Index — (close - low) / (high - low) avg 5d. Inferred buying.
H-1173: Volume Imbalance — up-day vol / down-day vol ratio over 10d.
H-1174: Price Impact Ratio — |return| / log(volume) avg 10d. Low = liquid.
H-1175: Accumulation/Distribution Line — 20d change in A/D (CLV × volume).
H-1176: Money Flow Index — RSI applied to typical_price × volume, 14d.
H-1177: Force Index — (close - prev_close) × volume, 13d EMA.
H-1178: Ease of Movement — ((H+L)/2 diff) / (volume / (H-L)), 14d avg.
H-1179: Chaikin Oscillator — EMA(3) - EMA(10) of A/D line.
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
    signals = {}

    # H-1172: Buy Pressure Index — (close - low) / (high - low), 5d avg
    bp = (closes - lows) / (highs - lows).clip(lower=1e-10)
    signals["buy_pressure"] = bp.rolling(5).mean()

    # H-1173: Volume Imbalance — up-day vol / down-day vol, 10d rolling
    up_vol = volumes.where(returns > 0, 0)
    dn_vol = volumes.where(returns <= 0, 0)
    signals["vol_imbalance"] = up_vol.rolling(10).sum() / dn_vol.rolling(10).sum().clip(lower=1)

    # H-1174: Price Impact Ratio — |return| / log(volume), 10d avg (low = liquid)
    abs_ret = returns.abs()
    log_vol = np.log1p(volumes)
    impact = abs_ret / log_vol.clip(lower=1e-10)
    signals["price_impact"] = impact.rolling(10).mean()

    # H-1175: Accumulation/Distribution Line — 20d change in A/D
    clv = ((closes - lows) - (highs - closes)) / (highs - lows).clip(lower=1e-10)
    ad = (clv * volumes).cumsum()
    signals["ad_change_20"] = ad.diff(20) / volumes.rolling(20).mean().clip(lower=1)

    # H-1176: Money Flow Index — RSI on typical_price × volume, 14d
    tp = (highs + lows + closes) / 3
    mf = tp * volumes
    mf_diff = mf.diff()
    pos_mf = mf_diff.where(mf_diff > 0, 0).rolling(14).sum()
    neg_mf = (-mf_diff).where(mf_diff < 0, 0).rolling(14).sum()
    mf_ratio = pos_mf / neg_mf.clip(lower=1)
    signals["mfi"] = 100 - (100 / (1 + mf_ratio))

    # H-1177: Force Index — (close diff) × volume, 13d EMA
    fi_raw = closes.diff() * volumes
    fi_ema = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        fi_ema[col] = fi_raw[col].ewm(span=13, adjust=False).mean()
    signals["force_index"] = fi_ema / volumes.rolling(13).mean().clip(lower=1)

    # H-1178: Ease of Movement — mid diff / volume_per_range, 14d avg
    mid = (highs + lows) / 2
    rng = (highs - lows).clip(lower=1e-10)
    box = volumes / rng
    eom = mid.diff() / box.clip(lower=1e-10)
    signals["ease_of_movement"] = eom.rolling(14).mean()

    # H-1179: Chaikin Oscillator — EMA(3) - EMA(10) of A/D line
    co = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        ad_col = (clv[col] * volumes[col]).cumsum()
        ema3 = ad_col.ewm(span=3, adjust=False).mean()
        ema10 = ad_col.ewm(span=10, adjust=False).mean()
        co[col] = ema3 - ema10
    signals["chaikin_osc"] = co / volumes.rolling(10).mean().clip(lower=1)

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
        "H-1172": ("buy_pressure", "Buy Pressure Index (5d avg)"),
        "H-1173": ("vol_imbalance", "Volume Imbalance (up/dn 10d)"),
        "H-1174": ("price_impact", "Price Impact Ratio (10d avg)"),
        "H-1175": ("ad_change_20", "Accumulation/Distribution 20d Change"),
        "H-1176": ("mfi", "Money Flow Index (14d)"),
        "H-1177": ("force_index", "Force Index (13d EMA)"),
        "H-1178": ("ease_of_movement", "Ease of Movement (14d avg)"),
        "H-1179": ("chaikin_osc", "Chaikin Oscillator (EMA3-EMA10 of AD)"),
    }

    results = {}
    lookback = 30

    for hyp_id, (sig_name, desc) in feature_map.items():
        print(f"\n{hyp_id}: {desc}")
        sig_df = signals[sig_name]
        r = run_signal(hyp_id, sig_df, closes, lookback,
                       ["high_long", "low_long"], [3, 4], [3, 5, 7])
        if r:
            results[hyp_id] = r

    print(f"\n{'='*80}")
    print(f"BATCH SUMMARY: {len(results)}/{8} signals with positive IS Sharpe")
    for name, r in sorted(results.items(), key=lambda x: -x[1]["sharpe"]):
        status = "CONFIRMED" if r["wf_pos"] >= max(2, r["wf_total"] * 0.5) and r["p_val"] < 0.15 else "BORDERLINE" if r["wf_pos"] >= 2 else "REJECTED"
        print(f"  {name}: Sharpe {r['sharpe']:.3f} | WF {r['wf_pos']}/{r['wf_total']} | p={r['p_val']:.3f} | "
              f"corr {r['h012_corr']:.3f} | SH {r['sh1']:.2f}/{r['sh2']:.2f} | {status}")


if __name__ == "__main__":
    main()
