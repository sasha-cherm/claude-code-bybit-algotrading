"""
Batch backtest: H-972 to H-979 — Microstructure / Candle Structure XS Signals.

H-972: Body Ratio — avg |close-open| / (high-low) — candle body proportion (conviction)
H-973: Volume Autocorrelation — autocorr(volume, lag1) — clustered vs random volume
H-974: ATR Expansion — ATR(short) / ATR(long) — expanding range = breakout signal
H-975: Upper Shadow Ratio — (high - max(open,close)) / (high-low) — selling pressure
H-976: OI Change Normalized — OI_change / avg_volume — positioning intensity
H-977: Intraday Range Trend — slope of (high-low)/close — expanding vs contracting ranges
H-978: Range Volatility — std of (high-low)/close — consistency of intraday ranges
H-979: Consecutive Range Expansion — count of days where range > prior day range
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
    """Load open interest data."""
    oi = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_oi.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            col = [c for c in df.columns if "oi" in c.lower() or "openInterest" in c][0] if len(df.columns) > 0 else df.columns[0]
            daily = df[col].resample("1D").last()
            oi[f"{ticker}/USDT"] = daily
        except:
            pass
    if oi:
        return pd.DataFrame(oi).sort_index().dropna(how="all")
    return None


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

def body_ratio(closes, opens, highs, lows, period=20):
    """H-972: avg |close-open| / (high-low). High = strong conviction candles. Low = indecision."""
    body = (closes - opens).abs()
    rng = (highs - lows).replace(0, np.nan)
    ratio = body / rng
    return ratio.rolling(period).mean()


def volume_autocorrelation(volumes, period=30):
    """H-973: Lag-1 autocorrelation of volume. High = clustered volume (sustained interest).
    Low = random volume (no sustained attention)."""
    signal = pd.DataFrame(np.nan, index=volumes.index, columns=volumes.columns)
    for i in range(period + 5, len(volumes)):
        for col in volumes.columns:
            v = volumes[col].iloc[i-period:i].values
            if not np.all(np.isfinite(v)):
                continue
            if len(v) < 10:
                continue
            ac = np.corrcoef(v[:-1], v[1:])[0, 1]
            if np.isfinite(ac):
                signal.iloc[i, signal.columns.get_loc(col)] = ac
    return signal


def atr_expansion(highs, lows, closes, short_period=5, long_period=20):
    """H-974: ATR(short) / ATR(long). Expanding range = breakout/volatility regime shift."""
    tr = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for col in closes.columns:
        h = highs[col]
        l = lows[col]
        c = closes[col].shift(1)
        tr[col] = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    atr_short = tr.rolling(short_period).mean()
    atr_long = tr.rolling(long_period).mean().replace(0, np.nan)
    return atr_short / atr_long


def upper_shadow_ratio(closes, opens, highs, lows, period=20):
    """H-975: (high - max(open,close)) / (high-low). High = selling pressure (rejection wicks).
    Long low upper shadow (less selling), short high upper shadow."""
    upper = highs - pd.DataFrame({col: np.maximum(closes[col], opens[col]) for col in closes.columns})
    rng = (highs - lows).replace(0, np.nan)
    ratio = upper / rng
    return -(ratio.rolling(period).mean())  # negative: less selling pressure = long


def oi_change_normalized(closes, volumes, period=14):
    """H-976: OI_change proxy normalized by volume. Uses price volatility * volume as OI proxy."""
    oi_data = load_oi()
    if oi_data is None:
        # Proxy: use absolute return * volume as proxy for OI change direction
        ret = closes.pct_change().abs()
        proxy = ret * volumes
        change = proxy.pct_change(5)
        avg_vol = volumes.rolling(period).mean().replace(0, np.nan)
        return change / avg_vol
    # Use actual OI data
    oi_aligned = oi_data.reindex(closes.index, method="ffill")
    oi_change = oi_aligned.pct_change(5)
    avg_vol = volumes.rolling(period).mean().replace(0, np.nan)
    common = [c for c in closes.columns if c in oi_change.columns and c in avg_vol.columns]
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for col in common:
        signal[col] = oi_change[col] / avg_vol[col]
    return signal


def intraday_range_trend(highs, lows, closes, period=20):
    """H-977: Slope of (high-low)/close over lookback. Expanding = increasing activity."""
    daily_range = (highs - lows) / closes
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            r = daily_range[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            x = np.arange(period)
            slope, _, _, _, _ = stats.linregress(x, r)
            if np.isfinite(slope):
                signal.iloc[i, signal.columns.get_loc(col)] = slope
    return signal


def range_volatility(highs, lows, closes, period=30):
    """H-978: Std of daily range (high-low)/close. Low = consistent ranges (stable regime).
    High = volatile ranges (unstable). Long consistent, short volatile."""
    daily_range = (highs - lows) / closes
    return -(daily_range.rolling(period).std())  # negative: low vol = long


def consecutive_range_expansion(highs, lows, period=20):
    """H-979: Count of days where range > prior day's range. More = expanding activity/interest."""
    daily_range = highs - lows
    signal = pd.DataFrame(np.nan, index=highs.index, columns=highs.columns)
    for i in range(period + 5, len(highs)):
        for col in highs.columns:
            r = daily_range[col].iloc[i-period:i].values
            if not np.all(np.isfinite(r)):
                continue
            count = np.sum(r[1:] > r[:-1])
            signal.iloc[i, signal.columns.get_loc(col)] = count
    return signal


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

    # H-972: Body Ratio
    for period in [10, 14, 20, 30]:
        sig = body_ratio(closes, opens, highs, lows, period)
        r = run_signal(f"H-972 (BodyRatio P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-972", {}).get("sharpe", -99):
            results["H-972"] = r

    # H-973: Volume Autocorrelation
    for period in [14, 20, 30, 60]:
        sig = volume_autocorrelation(volumes, period)
        r = run_signal(f"H-973 (VolAutocorr P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-973", {}).get("sharpe", -99):
            results["H-973"] = r

    # H-974: ATR Expansion
    for sp, lp in [(5, 20), (5, 30), (7, 30), (10, 40)]:
        sig = atr_expansion(highs, lows, closes, sp, lp)
        r = run_signal(f"H-974 (ATRExp S{sp}L{lp})", sig, closes, lp + 5, configs)
        if r.get("sharpe", 0) > results.get("H-974", {}).get("sharpe", -99):
            results["H-974"] = r

    # H-975: Upper Shadow Ratio
    for period in [10, 14, 20, 30]:
        sig = upper_shadow_ratio(closes, opens, highs, lows, period)
        r = run_signal(f"H-975 (UpperShadow P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-975", {}).get("sharpe", -99):
            results["H-975"] = r

    # H-976: OI Change Normalized
    for period in [7, 14, 20]:
        sig = oi_change_normalized(closes, volumes, period)
        r = run_signal(f"H-976 (OINorm P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-976", {}).get("sharpe", -99):
            results["H-976"] = r

    # H-977: Intraday Range Trend
    for period in [10, 14, 20, 30]:
        sig = intraday_range_trend(highs, lows, closes, period)
        r = run_signal(f"H-977 (RangeTrend P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-977", {}).get("sharpe", -99):
            results["H-977"] = r

    # H-978: Range Volatility
    for period in [14, 20, 30, 60]:
        sig = range_volatility(highs, lows, closes, period)
        r = run_signal(f"H-978 (RangeVol P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-978", {}).get("sharpe", -99):
            results["H-978"] = r

    # H-979: Consecutive Range Expansion
    for period in [10, 14, 20, 30]:
        sig = consecutive_range_expansion(highs, lows, period)
        r = run_signal(f"H-979 (ConsRangeExp P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-979", {}).get("sharpe", -99):
            results["H-979"] = r

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "="*70)
    print("BATCH 3 SUMMARY (H-972 to H-979 — Microstructure / Candle)")
    print("="*70)
    for hid in ["H-972", "H-973", "H-974", "H-975", "H-976", "H-977", "H-978", "H-979"]:
        r = results.get(hid, {})
        status = r.get("status", "")
        if status == "REJECTED_IS":
            print(f"  {hid}: REJECTED — {r.get('pos_pct',0):.0f}% positive, Sharpe {r.get('sharpe',0):.3f}")
        elif "wf" in r:
            wf_pos = sum(1 for w in r["wf"] if w > 0)
            wf_tot = len(r["wf"])
            sh1, sh2, p = r["sh"]
            corr = r["corr"]
            m = r["metrics"]
            pass_wf = wf_pos >= wf_tot * 0.5
            pass_sh = p < 0.10
            pass_corr = abs(corr) < 0.50
            status = "CONFIRMED" if (pass_wf and pass_sh and pass_corr) else "BORDERLINE"
            if not pass_wf:
                status = "REJECTED_WF"
            print(f"  {hid}: {status} — Sharpe {r['sharpe']:.3f}, WF {wf_pos}/{wf_tot}, "
                  f"SH p={p:.3f}, corr {corr}, {m}")
        else:
            print(f"  {hid}: {r}")

    return results


if __name__ == "__main__":
    run_batch()
