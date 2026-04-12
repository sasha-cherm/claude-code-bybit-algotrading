"""
Batch backtest: H-852 to H-859 — Price pattern and structural XS signals.

H-852: Price Acceleration — 2nd derivative of price (momentum of momentum)
H-853: Relative Volume Trend — volume trend slope relative to price trend slope
H-854: Close Location Value (modified) — (Close - Low) / (High - Low) rolling avg
H-855: Candle Body Ratio — body/range averaged, directional strength measure
H-856: Price Channel Position — where in the Donchian channel, combined with channel width
H-857: Normalized ATR Rank — ATR/close as normalized volatility, cross-sectional
H-858: Weighted Close Momentum — momentum using weighted close (H+L+2C)/4
H-859: Volume-Price Trend Divergence — sign(price_trend) ≠ sign(volume_trend)
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
            sig_row = signal_df.iloc[i - 1].dropna()
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

def price_acceleration_signal(closes, window):
    """H-852: 2nd derivative of price = momentum of momentum.
    Positive acceleration = momentum increasing."""
    mom = closes.pct_change(window)
    accel = mom.diff(window)
    return accel


def relative_vol_trend_signal(closes, volumes, window):
    """H-853: Volume trend slope relative to price trend slope.
    Divergence: volume growing faster than price = accumulation."""
    price_slope = closes.pct_change(window)
    vol_slope = volumes.pct_change(window)
    z_price = cross_sectional_zscore(price_slope)
    z_vol = cross_sectional_zscore(vol_slope)
    # Accumulation: high vol_slope relative to price_slope
    return z_vol - z_price


def close_location_value_signal(highs, lows, closes, window):
    """H-854: CLV = (Close - Low) / (High - Low), averaged over window.
    High CLV = consistently closing near highs = bullish."""
    clv = (closes - lows) / (highs - lows).replace(0, np.nan)
    return clv.rolling(window).mean()


def candle_body_ratio_signal(highs, lows, closes, opens, window):
    """H-855: Body / Range averaged. High = strong directional candles.
    Combined with direction: body_ratio × sign(close - open)."""
    body = (closes - opens)
    range_ = (highs - lows).replace(0, np.nan)
    signed_ratio = body / range_
    return signed_ratio.rolling(window).mean()


def channel_position_signal(closes, window):
    """H-856: Position in Donchian channel × channel width.
    Near top of wide channel = strong breakout signal."""
    high_n = closes.rolling(window).max()
    low_n = closes.rolling(window).min()
    range_n = high_n - low_n
    position = (closes - low_n) / range_n.replace(0, np.nan)
    # Width relative to price
    width = range_n / closes.replace(0, np.nan)
    z_pos = cross_sectional_zscore(position)
    z_width = cross_sectional_zscore(width)
    return z_pos * z_width


def normalized_atr_signal(highs, lows, closes, window):
    """H-857: ATR / close as normalized volatility.
    Long low-ATR (calm), short high-ATR (volatile)."""
    tr = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        hl = highs[col] - lows[col]
        hc = (highs[col] - closes[col].shift(1)).abs()
        lc = (lows[col] - closes[col].shift(1)).abs()
        tr[col] = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(window).mean()
    natr = atr / closes.replace(0, np.nan)
    return -natr  # Long = low normalized ATR


def weighted_close_momentum_signal(highs, lows, closes, window):
    """H-858: Momentum using weighted close = (H + L + 2C) / 4.
    May capture intraday range info better than close-to-close momentum."""
    wc = (highs + lows + 2 * closes) / 4
    return wc.pct_change(window)


def vol_price_trend_divergence_signal(closes, volumes, window):
    """H-859: Volume-Price Trend Divergence.
    If price trending up but volume trending down (or vice versa) → contrarian.
    If aligned → continuation."""
    price_trend = closes.pct_change(window)
    vol_trend = volumes.pct_change(window)
    # Agreement score: both same sign = strong continuation
    # Both positive or both negative = agreement
    z_price = cross_sectional_zscore(price_trend)
    z_vol = cross_sectional_zscore(vol_trend)
    # Product: positive when aligned, negative when divergent
    return z_price * z_vol


def run_batch():
    print("Loading data...")
    closes, highs, lows, opens, volumes = load_data()
    print(f"Data: {len(closes)} days, {len(closes.columns)} assets, "
          f"{closes.index[0].date()} to {closes.index[-1].date()}")

    results = {}

    hypotheses = [
        ("H-852", "Price Acceleration",
         lambda w: price_acceleration_signal(closes, w), [10, 20, 30, 60], "high_long"),
        ("H-853", "Relative Volume Trend",
         lambda w: relative_vol_trend_signal(closes, volumes, w), [10, 20, 30], "high_long"),
        ("H-854", "Close Location Value",
         lambda w: close_location_value_signal(highs, lows, closes, w), [10, 20, 30], "high_long"),
        ("H-855", "Candle Body Ratio",
         lambda w: candle_body_ratio_signal(highs, lows, closes, opens, w), [10, 20, 30], "high_long"),
        ("H-856", "Channel Position × Width",
         lambda w: channel_position_signal(closes, w), [20, 30, 60], "high_long"),
        ("H-857", "Normalized ATR Rank",
         lambda w: normalized_atr_signal(highs, lows, closes, w), [10, 20, 30], "high_long"),
        ("H-858", "Weighted Close Momentum",
         lambda w: weighted_close_momentum_signal(highs, lows, closes, w), [20, 30, 60], "high_long"),
        ("H-859", "Volume-Price Trend Divergence",
         lambda w: vol_price_trend_divergence_signal(closes, volumes, w), [10, 20, 30], "high_long"),
    ]

    for h_id, h_name, sig_func, windows, direction in hypotheses:
        print(f"\n=== {h_id}: {h_name} ===")
        best = {"sharpe": -99}
        params_all = []
        for window in windows:
            try:
                sig = sig_func(window)
            except Exception as e:
                print(f"  Signal error for W{window}: {e}")
                continue
            for rebal in [3, 5, 7]:
                for n_ls in [3, 4]:
                    pnl = xs_backtest(closes, sig, window, rebal, n_ls, direction)
                    sh = compute_sharpe(pnl)
                    params_all.append(sh)
                    if sh > best["sharpe"]:
                        best = {"sharpe": sh, "window": window, "rebal": rebal,
                                "n_ls": n_ls, "pnl": pnl, "signal": sig}

        if not params_all:
            print("  No valid params")
            results[h_id] = {"status": "REJECTED_IS", "pos_pct": 0, "sharpe": 0}
            continue

        pos_pct = sum(1 for s in params_all if s > 0) / len(params_all) * 100
        print(f"  IS: {pos_pct:.0f}% positive ({sum(1 for s in params_all if s > 0)}/{len(params_all)})")
        print(f"  Best: W{best['window']}_R{best['rebal']}_N{best['n_ls']} "
              f"Sharpe {best['sharpe']:.3f}")
        m = compute_metrics(best["pnl"])
        print(f"  Metrics: {m}")

        if pos_pct >= 80 and best["sharpe"] > 0.8:
            wf = walk_forward(closes, best["signal"], best["window"],
                              best["rebal"], best["n_ls"], direction)
            sh1, sh2, p = split_half_test(best["pnl"])
            corr = h012_correlation(closes, best["signal"], best["window"],
                                    best["rebal"], best["n_ls"], direction)
            print(f"  WF: {[round(w, 3) for w in wf]} ({sum(1 for w in wf if w > 0)}/{len(wf)})")
            print(f"  SH: {sh1:.3f}/{sh2:.3f}, p={p:.4f}")
            print(f"  H-012 corr: {corr}")
            results[h_id] = {"sharpe": best["sharpe"], "pos_pct": pos_pct,
                             "wf": wf, "sh": (sh1, sh2, p), "corr": corr, "metrics": m,
                             "params": f"W{best['window']}_R{best['rebal']}_N{best['n_ls']}"}
        else:
            print(f"  REJECTED at IS — {pos_pct:.0f}% positive, Sharpe {best['sharpe']:.3f}")
            results[h_id] = {"status": "REJECTED_IS", "pos_pct": pos_pct,
                             "sharpe": best["sharpe"]}

    # Summary
    print("\n" + "=" * 60)
    print("BATCH 3 SUMMARY: Price Pattern/Structural Signals")
    print("=" * 60)
    for h, r in results.items():
        status = r.get("status", "")
        if "REJECTED" in status:
            print(f"  {h}: REJECTED — IS {r['pos_pct']:.0f}% positive, Sharpe {r['sharpe']:.3f}")
        else:
            wf = r["wf"]
            wf_pass = sum(1 for w in wf if w > 0)
            sh1, sh2, p = r["sh"]
            sh_pass = "PASS" if p < 0.10 else "FAIL"
            print(f"  {h}: Sharpe {r['sharpe']:.3f}, WF {wf_pass}/{len(wf)}, "
                  f"SH {sh1:.3f}/{sh2:.3f} p={p:.4f} ({sh_pass}), "
                  f"H-012 corr {r['corr']}, params: {r['params']}")

    return results


if __name__ == "__main__":
    run_batch()
