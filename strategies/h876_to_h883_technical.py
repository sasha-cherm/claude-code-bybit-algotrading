"""
Batch backtest: H-876 to H-883 — Technical Indicator XS Signals.

H-876: MACD XS — MACD(12,26) ranked cross-sectionally
H-877: CCI XS — Commodity Channel Index ranked
H-878: Stochastic %K XS — Stochastic oscillator ranked
H-879: Williams %R XS — Williams %R ranked
H-880: Chaikin Money Flow XS — CMF ranked
H-881: OBV Slope XS — On-Balance Volume slope ranked
H-882: Ease of Movement XS — EMV ranked
H-883: Force Index XS — Force Index (return × volume) ranked
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

def macd_signal(closes, fast=12, slow=26):
    """H-876: MACD = EMA(fast) - EMA(slow). Rank by MACD value cross-sectionally."""
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    # Normalize by price to make cross-asset comparable
    return macd / closes.replace(0, np.nan)


def cci_signal(closes, highs, lows, period=20):
    """H-877: CCI = (Typical Price - SMA(TP)) / (0.015 × Mean Deviation).
    Rank cross-sectionally — high CCI = strong uptrend."""
    tp = (highs + lows + closes) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    cci = (tp - sma) / (0.015 * mad.replace(0, np.nan))
    return cci


def stochastic_signal(closes, highs, lows, period=14):
    """H-878: Stochastic %K = (Close - Low_N) / (High_N - Low_N) × 100.
    Rank cross-sectionally (momentum: long high %K)."""
    low_n = lows.rolling(period).min()
    high_n = highs.rolling(period).max()
    denom = (high_n - low_n).replace(0, np.nan)
    k = (closes - low_n) / denom * 100
    return k


def williams_r_signal(closes, highs, lows, period=14):
    """H-879: Williams %R = (Highest High - Close) / (Highest High - Lowest Low) × -100.
    Rank cross-sectionally (less negative = stronger)."""
    high_n = highs.rolling(period).max()
    low_n = lows.rolling(period).min()
    denom = (high_n - low_n).replace(0, np.nan)
    wr = (high_n - closes) / denom * -100
    return -wr  # Flip sign: higher = stronger (momentum direction)


def chaikin_mf_signal(closes, highs, lows, volumes, period=20):
    """H-880: Chaikin Money Flow = sum(CLV × volume) / sum(volume) over period.
    CLV = ((close - low) - (high - close)) / (high - low).
    High CMF = buying pressure."""
    hl_range = (highs - lows).replace(0, np.nan)
    clv = ((closes - lows) - (highs - closes)) / hl_range
    mf_vol = clv * volumes
    cmf = mf_vol.rolling(period).sum() / volumes.rolling(period).sum().replace(0, np.nan)
    return cmf


def obv_slope_signal(closes, volumes, period=20):
    """H-881: OBV Slope = linear regression slope of On-Balance Volume over period.
    Rising OBV = accumulation, falling OBV = distribution."""
    ret = closes.pct_change()
    direction = ret.apply(np.sign)
    obv = (direction * volumes).cumsum()
    # Compute slope via rolling regression
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    x = np.arange(period)
    for i in range(period + 5, len(closes)):
        for col in obv.columns:
            y = obv[col].iloc[i - period:i].values
            if len(y) == period and np.all(np.isfinite(y)):
                # Simple slope = correlation × std_y / std_x
                slope = np.polyfit(x, y, 1)[0]
                # Normalize by mean volume for cross-asset comparability
                mean_vol = volumes[col].iloc[i - period:i].mean()
                if mean_vol > 0:
                    signal.iloc[i, signal.columns.get_loc(col)] = slope / mean_vol
    return signal


def ease_of_movement_signal(highs, lows, volumes, period=14):
    """H-882: Ease of Movement = ((H+L)/2 change) / (Volume / (H-L)).
    High EMV = price moves easily on low volume = bullish."""
    midpoint = (highs + lows) / 2
    dm = midpoint.diff()
    hl = (highs - lows).replace(0, np.nan)
    box_ratio = volumes / hl / 1e6  # Scale down
    emv = dm / box_ratio.replace(0, np.nan)
    return emv.rolling(period).mean()


def force_index_signal(closes, volumes, period=13):
    """H-883: Force Index = close_change × volume.
    High force = strong buying pressure. Rank cross-sectionally."""
    close_change = closes.diff()
    fi = close_change * volumes
    # Smooth with EMA
    fi_smooth = fi.ewm(span=period, adjust=False).mean()
    # Normalize by rolling avg volume × price for cross-asset comparability
    norm = (volumes.rolling(period).mean() * closes).replace(0, np.nan)
    return fi_smooth / norm


# ============================================================
# BATCH RUNNER
# ============================================================

def run_signal(name, signal_df, closes, lookback, param_configs, direction="high_long"):
    print(f"\n=== {name} ===")
    best = {"sharpe": -99}
    all_sharpes = []
    for rebal, n_ls in param_configs:
        pnl = xs_backtest(closes, signal_df, lookback, rebal, n_ls, direction)
        sh = compute_sharpe(pnl)
        all_sharpes.append(sh)
        if sh > best["sharpe"]:
            best = {"sharpe": sh, "rebal": rebal, "n_ls": n_ls, "pnl": pnl}

    pos_pct = sum(1 for s in all_sharpes if s > 0) / len(all_sharpes) * 100
    print(f"  IS: {pos_pct:.0f}% positive ({sum(1 for s in all_sharpes if s > 0)}/{len(all_sharpes)})")
    print(f"  Best: R{best['rebal']}_N{best['n_ls']} Sharpe {best['sharpe']:.3f}")
    m = compute_metrics(best["pnl"])
    print(f"  Metrics: {m}")

    if pos_pct >= 70 and best["sharpe"] > 0.8:
        wf = walk_forward(closes, signal_df, lookback, best["rebal"], best["n_ls"], direction)
        sh1, sh2, p = split_half_test(best["pnl"])
        corr = h012_correlation(closes, signal_df, lookback, best["rebal"], best["n_ls"], direction)
        print(f"  WF: {[round(w, 3) for w in wf]} ({sum(1 for w in wf if w > 0)}/{len(wf)})")
        print(f"  SH: {sh1:.3f}/{sh2:.3f}, p={p:.4f}")
        print(f"  H-012 corr: {corr}")
        return {"name": name, "sharpe": best["sharpe"], "pos_pct": pos_pct,
                "wf": wf, "sh": (sh1, sh2, p), "corr": corr, "metrics": m,
                "params": f"R{best['rebal']}_N{best['n_ls']}", "pnl": best["pnl"]}
    else:
        print(f"  REJECTED at IS — {pos_pct:.0f}% positive, Sharpe {best['sharpe']:.3f}")
        return {"name": name, "status": "REJECTED_IS", "pos_pct": pos_pct,
                "sharpe": best["sharpe"]}


def run_batch():
    print("Loading data...")
    closes, highs, lows, opens, volumes = load_data()
    print(f"Data: {len(closes)} days, {len(closes.columns)} assets, "
          f"{closes.index[0].date()} to {closes.index[-1].date()}")

    configs = [(r, n) for r in [3, 5, 7] for n in [3, 4]]
    results = {}

    # H-876: MACD
    for fast, slow in [(8, 21), (12, 26), (5, 35)]:
        sig = macd_signal(closes, fast, slow)
        r = run_signal(f"H-876 (MACD {fast}/{slow})", sig, closes, slow + 5, configs)
        if r.get("sharpe", 0) > results.get("H-876", {}).get("sharpe", -99):
            results["H-876"] = r

    # H-877: CCI
    for period in [14, 20, 30]:
        sig = cci_signal(closes, highs, lows, period)
        r = run_signal(f"H-877 (CCI P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-877", {}).get("sharpe", -99):
            results["H-877"] = r

    # H-878: Stochastic %K
    for period in [10, 14, 21]:
        sig = stochastic_signal(closes, highs, lows, period)
        r = run_signal(f"H-878 (Stoch K P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-878", {}).get("sharpe", -99):
            results["H-878"] = r

    # H-879: Williams %R
    for period in [10, 14, 21]:
        sig = williams_r_signal(closes, highs, lows, period)
        r = run_signal(f"H-879 (Williams %R P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-879", {}).get("sharpe", -99):
            results["H-879"] = r

    # H-880: Chaikin Money Flow
    for period in [14, 20, 30]:
        sig = chaikin_mf_signal(closes, highs, lows, volumes, period)
        r = run_signal(f"H-880 (CMF P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-880", {}).get("sharpe", -99):
            results["H-880"] = r

    # H-881: OBV Slope
    for period in [14, 20, 30]:
        sig = obv_slope_signal(closes, volumes, period)
        r = run_signal(f"H-881 (OBV Slope P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-881", {}).get("sharpe", -99):
            results["H-881"] = r

    # H-882: Ease of Movement
    for period in [10, 14, 20]:
        sig = ease_of_movement_signal(highs, lows, volumes, period)
        r = run_signal(f"H-882 (EMV P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-882", {}).get("sharpe", -99):
            results["H-882"] = r

    # H-883: Force Index
    for period in [7, 13, 20]:
        sig = force_index_signal(closes, volumes, period)
        r = run_signal(f"H-883 (Force Index P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-883", {}).get("sharpe", -99):
            results["H-883"] = r

    print("\n" + "=" * 60)
    print("BATCH 3 SUMMARY: Technical Indicator XS Signals")
    print("=" * 60)
    for h, r in sorted(results.items()):
        status = r.get("status", "PASSED_IS")
        if status == "REJECTED_IS":
            print(f"  {h}: REJECTED (IS Sharpe {r['sharpe']:.3f}, {r['pos_pct']:.0f}% pos)")
        else:
            wf_pass = sum(1 for w in r["wf"] if w > 0)
            sh_p = r["sh"][2]
            print(f"  {h}: Sharpe {r['sharpe']:.3f}, WF {wf_pass}/{len(r['wf'])}, "
                  f"SH p={sh_p:.4f}, corr {r['corr']}")
            if wf_pass >= len(r["wf"]) * 0.6 and sh_p < 0.10 and abs(r["corr"]) < 0.5:
                print(f"    >>> CONFIRMED — {r['params']}")
            elif wf_pass >= len(r["wf"]) * 0.5:
                print(f"    >>> BORDERLINE — needs review")
            else:
                print(f"    >>> REJECTED (WF fail)")

    return results


if __name__ == "__main__":
    results = run_batch()
