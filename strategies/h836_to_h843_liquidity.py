"""
Batch backtest: H-836 to H-843 — Liquidity/illiquidity-based XS signals.

H-836: Amihud Illiquidity Factor — |return| / dollar_volume as illiquidity proxy
H-837: Volume Turnover Rate — dollar_volume / market_cap_proxy (rolling avg)
H-838: Bid-Ask Spread Proxy (High-Low / Close) — Corwin-Schultz-like spread estimator
H-839: Volume Concentration — ratio of top-volume days to total volume
H-840: Price Impact Ratio — abs(return) per unit of volume (Kyle's lambda proxy)
H-841: Zero-Return Days — count of days with ~zero return as illiquidity measure
H-842: Volume Autocorrelation — persistence of volume as liquidity stability measure
H-843: Intraday Range Volatility Ratio — (H-L)/(C-O) normalized by volume
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

def amihud_illiquidity_signal(closes, volumes, window):
    """H-836: Amihud illiquidity = mean(|return| / dollar_volume) over window.
    Short high-illiquidity (risky), long low-illiquidity (liquid) assets."""
    ret = closes.pct_change()
    illiq = ret.abs() / volumes.replace(0, np.nan)
    return -illiq.rolling(window).mean()  # Negative = long liquid


def volume_turnover_signal(closes, volumes, window):
    """H-837: Volume turnover rate = dollar_volume / (price × rolling_avg_volume).
    High turnover = active trading interest."""
    # Approximate market cap proxy as price × avg daily volume (relative measure)
    avg_vol = volumes.rolling(window).mean()
    turnover = volumes / avg_vol.replace(0, np.nan)
    return turnover.rolling(window).mean()


def spread_proxy_signal(highs, lows, closes, window):
    """H-838: Corwin-Schultz-like spread estimator = (H-L)/close.
    Long low-spread (liquid), short high-spread (illiquid)."""
    spread = (highs - lows) / closes.replace(0, np.nan)
    return -spread.rolling(window).mean()  # Negative = long tight spread


def volume_concentration_signal(volumes, window, top_pct=0.2):
    """H-839: What fraction of total volume comes from the top N% of days.
    High concentration = lumpy liquidity = risky."""
    signal = pd.DataFrame(index=volumes.index, columns=volumes.columns, dtype=float)
    top_n = max(1, int(window * top_pct))
    for i in range(window + 5, len(volumes)):
        for col in volumes.columns:
            v = volumes[col].iloc[i - window:i].dropna()
            if len(v) < window // 2:
                continue
            sorted_v = v.sort_values(ascending=False)
            total = sorted_v.sum()
            if total > 0:
                signal.iloc[i, signal.columns.get_loc(col)] = sorted_v.iloc[:top_n].sum() / total
    return -signal  # Long = less concentrated


def price_impact_signal(closes, volumes, window):
    """H-840: Kyle's lambda proxy = rolling regression of |return| on volume.
    High impact = illiquid. Long low-impact assets."""
    ret = closes.pct_change()
    abs_ret = ret.abs()
    signal = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for i in range(window + 5, len(closes)):
        for col in closes.columns:
            r = abs_ret[col].iloc[i - window:i].dropna()
            v = volumes[col].iloc[i - window:i].dropna()
            idx = r.index.intersection(v.index)
            if len(idx) < window // 2:
                continue
            # Price impact = abs_return / volume
            impact = r[idx].sum() / v[idx].sum() if v[idx].sum() > 0 else np.nan
            signal.iloc[i, signal.columns.get_loc(col)] = impact
    return -signal  # Long = low price impact


def zero_return_signal(closes, window):
    """H-841: Count of near-zero return days (|return| < 0.1%) as illiquidity.
    Long low-zero-count (active/liquid), short high-zero-count."""
    ret = closes.pct_change()
    is_zero = (ret.abs() < 0.001).astype(float)
    return -is_zero.rolling(window).sum()  # Long = fewer zero days


def volume_autocorrelation_signal(volumes, window):
    """H-842: Autocorrelation of daily volume over window.
    High autocorr = stable/predictable liquidity = safer."""
    signal = pd.DataFrame(index=volumes.index, columns=volumes.columns, dtype=float)
    for i in range(window + 5, len(volumes)):
        for col in volumes.columns:
            v = volumes[col].iloc[i - window:i].dropna()
            if len(v) < window // 2:
                continue
            try:
                ac = np.corrcoef(v.values[:-1], v.values[1:])[0, 1]
                signal.iloc[i, signal.columns.get_loc(col)] = ac
            except:
                continue
    return signal


def range_vol_ratio_signal(highs, lows, closes, opens, volumes, window):
    """H-843: Intraday range (H-L) relative to body (|C-O|) normalized by volume.
    High range/body at low volume = potential reversal. Low range/body at high volume = continuation."""
    body = (closes - opens).abs()
    range_ = highs - lows
    # Range-body ratio
    rb_ratio = range_ / body.replace(0, np.nan)
    vol_z = cross_sectional_zscore(volumes)
    rb_z = cross_sectional_zscore(rb_ratio)
    # Long: low range-body ratio (strong directional moves) AND high volume
    return (-rb_z + vol_z).rolling(window).mean()


# ============================================================
# BATCH RUNNER
# ============================================================

def run_batch():
    print("Loading data...")
    closes, highs, lows, opens, volumes = load_data()
    print(f"Data: {len(closes)} days, {len(closes.columns)} assets, "
          f"{closes.index[0].date()} to {closes.index[-1].date()}")

    results = {}

    # --- H-836: Amihud Illiquidity ---
    print("\n=== H-836: Amihud Illiquidity ===")
    best_836 = {"sharpe": -99}
    params_836 = []
    for window in [10, 20, 30]:
        sig = amihud_illiquidity_signal(closes, volumes, window)
        for rebal in [3, 5, 7]:
            for n_ls in [3, 4]:
                pnl = xs_backtest(closes, sig, window, rebal, n_ls, "high_long")
                sh = compute_sharpe(pnl)
                params_836.append(sh)
                if sh > best_836["sharpe"]:
                    best_836 = {"sharpe": sh, "window": window, "rebal": rebal,
                                "n_ls": n_ls, "pnl": pnl, "signal": sig}
    pos_pct = sum(1 for s in params_836 if s > 0) / len(params_836) * 100
    print(f"  IS: {pos_pct:.0f}% positive ({sum(1 for s in params_836 if s > 0)}/{len(params_836)})")
    print(f"  Best: W{best_836['window']}_R{best_836['rebal']}_N{best_836['n_ls']} "
          f"Sharpe {best_836['sharpe']:.3f}")
    m = compute_metrics(best_836["pnl"])
    print(f"  Metrics: {m}")
    if pos_pct >= 80 and best_836["sharpe"] > 0.8:
        wf = walk_forward(closes, best_836["signal"], best_836["window"],
                          best_836["rebal"], best_836["n_ls"], "high_long")
        sh1, sh2, p = split_half_test(best_836["pnl"])
        corr = h012_correlation(closes, best_836["signal"], best_836["window"],
                                best_836["rebal"], best_836["n_ls"], "high_long")
        print(f"  WF: {[round(w, 3) for w in wf]} ({sum(1 for w in wf if w > 0)}/{len(wf)})")
        print(f"  SH: {sh1:.3f}/{sh2:.3f}, p={p:.4f}")
        print(f"  H-012 corr: {corr}")
        results["H-836"] = {"sharpe": best_836["sharpe"], "pos_pct": pos_pct,
                            "wf": wf, "sh": (sh1, sh2, p), "corr": corr, "metrics": m,
                            "params": f"W{best_836['window']}_R{best_836['rebal']}_N{best_836['n_ls']}"}
    else:
        print(f"  REJECTED at IS — {pos_pct:.0f}% positive, Sharpe {best_836['sharpe']:.3f}")
        results["H-836"] = {"status": "REJECTED_IS", "pos_pct": pos_pct,
                            "sharpe": best_836["sharpe"]}

    # --- H-837: Volume Turnover ---
    print("\n=== H-837: Volume Turnover ===")
    best_837 = {"sharpe": -99}
    params_837 = []
    for window in [10, 20, 30]:
        sig = volume_turnover_signal(closes, volumes, window)
        for rebal in [3, 5, 7]:
            for n_ls in [3, 4]:
                pnl = xs_backtest(closes, sig, window, rebal, n_ls, "high_long")
                sh = compute_sharpe(pnl)
                params_837.append(sh)
                if sh > best_837["sharpe"]:
                    best_837 = {"sharpe": sh, "window": window, "rebal": rebal,
                                "n_ls": n_ls, "pnl": pnl, "signal": sig}
    pos_pct = sum(1 for s in params_837 if s > 0) / len(params_837) * 100
    print(f"  IS: {pos_pct:.0f}% positive ({sum(1 for s in params_837 if s > 0)}/{len(params_837)})")
    print(f"  Best: W{best_837['window']}_R{best_837['rebal']}_N{best_837['n_ls']} "
          f"Sharpe {best_837['sharpe']:.3f}")
    m = compute_metrics(best_837["pnl"])
    print(f"  Metrics: {m}")
    if pos_pct >= 80 and best_837["sharpe"] > 0.8:
        wf = walk_forward(closes, best_837["signal"], best_837["window"],
                          best_837["rebal"], best_837["n_ls"], "high_long")
        sh1, sh2, p = split_half_test(best_837["pnl"])
        corr = h012_correlation(closes, best_837["signal"], best_837["window"],
                                best_837["rebal"], best_837["n_ls"], "high_long")
        print(f"  WF: {[round(w, 3) for w in wf]} ({sum(1 for w in wf if w > 0)}/{len(wf)})")
        print(f"  SH: {sh1:.3f}/{sh2:.3f}, p={p:.4f}")
        print(f"  H-012 corr: {corr}")
        results["H-837"] = {"sharpe": best_837["sharpe"], "pos_pct": pos_pct,
                            "wf": wf, "sh": (sh1, sh2, p), "corr": corr, "metrics": m,
                            "params": f"W{best_837['window']}_R{best_837['rebal']}_N{best_837['n_ls']}"}
    else:
        print(f"  REJECTED at IS — {pos_pct:.0f}% positive, Sharpe {best_837['sharpe']:.3f}")
        results["H-837"] = {"status": "REJECTED_IS", "pos_pct": pos_pct,
                            "sharpe": best_837["sharpe"]}

    # --- H-838: Spread Proxy ---
    print("\n=== H-838: Spread Proxy (H-L)/Close ===")
    best_838 = {"sharpe": -99}
    params_838 = []
    for window in [10, 20, 30]:
        sig = spread_proxy_signal(highs, lows, closes, window)
        for rebal in [3, 5, 7]:
            for n_ls in [3, 4]:
                pnl = xs_backtest(closes, sig, window, rebal, n_ls, "high_long")
                sh = compute_sharpe(pnl)
                params_838.append(sh)
                if sh > best_838["sharpe"]:
                    best_838 = {"sharpe": sh, "window": window, "rebal": rebal,
                                "n_ls": n_ls, "pnl": pnl, "signal": sig}
    pos_pct = sum(1 for s in params_838 if s > 0) / len(params_838) * 100
    print(f"  IS: {pos_pct:.0f}% positive ({sum(1 for s in params_838 if s > 0)}/{len(params_838)})")
    print(f"  Best: W{best_838['window']}_R{best_838['rebal']}_N{best_838['n_ls']} "
          f"Sharpe {best_838['sharpe']:.3f}")
    m = compute_metrics(best_838["pnl"])
    print(f"  Metrics: {m}")
    if pos_pct >= 80 and best_838["sharpe"] > 0.8:
        wf = walk_forward(closes, best_838["signal"], best_838["window"],
                          best_838["rebal"], best_838["n_ls"], "high_long")
        sh1, sh2, p = split_half_test(best_838["pnl"])
        corr = h012_correlation(closes, best_838["signal"], best_838["window"],
                                best_838["rebal"], best_838["n_ls"], "high_long")
        print(f"  WF: {[round(w, 3) for w in wf]} ({sum(1 for w in wf if w > 0)}/{len(wf)})")
        print(f"  SH: {sh1:.3f}/{sh2:.3f}, p={p:.4f}")
        print(f"  H-012 corr: {corr}")
        results["H-838"] = {"sharpe": best_838["sharpe"], "pos_pct": pos_pct,
                            "wf": wf, "sh": (sh1, sh2, p), "corr": corr, "metrics": m,
                            "params": f"W{best_838['window']}_R{best_838['rebal']}_N{best_838['n_ls']}"}
    else:
        print(f"  REJECTED at IS — {pos_pct:.0f}% positive, Sharpe {best_838['sharpe']:.3f}")
        results["H-838"] = {"status": "REJECTED_IS", "pos_pct": pos_pct,
                            "sharpe": best_838["sharpe"]}

    # --- H-839: Volume Concentration ---
    print("\n=== H-839: Volume Concentration ===")
    best_839 = {"sharpe": -99}
    params_839 = []
    for window in [20, 30]:
        sig = volume_concentration_signal(volumes, window)
        for rebal in [3, 5, 7]:
            for n_ls in [3, 4]:
                pnl = xs_backtest(closes, sig, window, rebal, n_ls, "high_long")
                sh = compute_sharpe(pnl)
                params_839.append(sh)
                if sh > best_839["sharpe"]:
                    best_839 = {"sharpe": sh, "window": window, "rebal": rebal,
                                "n_ls": n_ls, "pnl": pnl, "signal": sig}
    pos_pct = sum(1 for s in params_839 if s > 0) / len(params_839) * 100
    print(f"  IS: {pos_pct:.0f}% positive ({sum(1 for s in params_839 if s > 0)}/{len(params_839)})")
    print(f"  Best: W{best_839['window']}_R{best_839['rebal']}_N{best_839['n_ls']} "
          f"Sharpe {best_839['sharpe']:.3f}")
    m = compute_metrics(best_839["pnl"])
    print(f"  Metrics: {m}")
    if pos_pct >= 80 and best_839["sharpe"] > 0.8:
        wf = walk_forward(closes, best_839["signal"], best_839["window"],
                          best_839["rebal"], best_839["n_ls"], "high_long")
        sh1, sh2, p = split_half_test(best_839["pnl"])
        corr = h012_correlation(closes, best_839["signal"], best_839["window"],
                                best_839["rebal"], best_839["n_ls"], "high_long")
        print(f"  WF: {[round(w, 3) for w in wf]} ({sum(1 for w in wf if w > 0)}/{len(wf)})")
        print(f"  SH: {sh1:.3f}/{sh2:.3f}, p={p:.4f}")
        print(f"  H-012 corr: {corr}")
        results["H-839"] = {"sharpe": best_839["sharpe"], "pos_pct": pos_pct,
                            "wf": wf, "sh": (sh1, sh2, p), "corr": corr, "metrics": m,
                            "params": f"W{best_839['window']}_R{best_839['rebal']}_N{best_839['n_ls']}"}
    else:
        print(f"  REJECTED at IS — {pos_pct:.0f}% positive, Sharpe {best_839['sharpe']:.3f}")
        results["H-839"] = {"status": "REJECTED_IS", "pos_pct": pos_pct,
                            "sharpe": best_839["sharpe"]}

    # --- H-840: Price Impact ---
    print("\n=== H-840: Price Impact (Kyle's Lambda Proxy) ===")
    best_840 = {"sharpe": -99}
    params_840 = []
    for window in [20, 30]:
        sig = price_impact_signal(closes, volumes, window)
        for rebal in [3, 5, 7]:
            for n_ls in [3, 4]:
                pnl = xs_backtest(closes, sig, window, rebal, n_ls, "high_long")
                sh = compute_sharpe(pnl)
                params_840.append(sh)
                if sh > best_840["sharpe"]:
                    best_840 = {"sharpe": sh, "window": window, "rebal": rebal,
                                "n_ls": n_ls, "pnl": pnl, "signal": sig}
    pos_pct = sum(1 for s in params_840 if s > 0) / len(params_840) * 100
    print(f"  IS: {pos_pct:.0f}% positive ({sum(1 for s in params_840 if s > 0)}/{len(params_840)})")
    print(f"  Best: W{best_840['window']}_R{best_840['rebal']}_N{best_840['n_ls']} "
          f"Sharpe {best_840['sharpe']:.3f}")
    m = compute_metrics(best_840["pnl"])
    print(f"  Metrics: {m}")
    if pos_pct >= 80 and best_840["sharpe"] > 0.8:
        wf = walk_forward(closes, best_840["signal"], best_840["window"],
                          best_840["rebal"], best_840["n_ls"], "high_long")
        sh1, sh2, p = split_half_test(best_840["pnl"])
        corr = h012_correlation(closes, best_840["signal"], best_840["window"],
                                best_840["rebal"], best_840["n_ls"], "high_long")
        print(f"  WF: {[round(w, 3) for w in wf]} ({sum(1 for w in wf if w > 0)}/{len(wf)})")
        print(f"  SH: {sh1:.3f}/{sh2:.3f}, p={p:.4f}")
        print(f"  H-012 corr: {corr}")
        results["H-840"] = {"sharpe": best_840["sharpe"], "pos_pct": pos_pct,
                            "wf": wf, "sh": (sh1, sh2, p), "corr": corr, "metrics": m,
                            "params": f"W{best_840['window']}_R{best_840['rebal']}_N{best_840['n_ls']}"}
    else:
        print(f"  REJECTED at IS — {pos_pct:.0f}% positive, Sharpe {best_840['sharpe']:.3f}")
        results["H-840"] = {"status": "REJECTED_IS", "pos_pct": pos_pct,
                            "sharpe": best_840["sharpe"]}

    # --- H-841: Zero Return Days ---
    print("\n=== H-841: Zero Return Days ===")
    best_841 = {"sharpe": -99}
    params_841 = []
    for window in [10, 20, 30]:
        sig = zero_return_signal(closes, window)
        for rebal in [3, 5, 7]:
            for n_ls in [3, 4]:
                pnl = xs_backtest(closes, sig, window, rebal, n_ls, "high_long")
                sh = compute_sharpe(pnl)
                params_841.append(sh)
                if sh > best_841["sharpe"]:
                    best_841 = {"sharpe": sh, "window": window, "rebal": rebal,
                                "n_ls": n_ls, "pnl": pnl, "signal": sig}
    pos_pct = sum(1 for s in params_841 if s > 0) / len(params_841) * 100
    print(f"  IS: {pos_pct:.0f}% positive ({sum(1 for s in params_841 if s > 0)}/{len(params_841)})")
    print(f"  Best: W{best_841['window']}_R{best_841['rebal']}_N{best_841['n_ls']} "
          f"Sharpe {best_841['sharpe']:.3f}")
    m = compute_metrics(best_841["pnl"])
    print(f"  Metrics: {m}")
    if pos_pct >= 80 and best_841["sharpe"] > 0.8:
        wf = walk_forward(closes, best_841["signal"], best_841["window"],
                          best_841["rebal"], best_841["n_ls"], "high_long")
        sh1, sh2, p = split_half_test(best_841["pnl"])
        corr = h012_correlation(closes, best_841["signal"], best_841["window"],
                                best_841["rebal"], best_841["n_ls"], "high_long")
        print(f"  WF: {[round(w, 3) for w in wf]} ({sum(1 for w in wf if w > 0)}/{len(wf)})")
        print(f"  SH: {sh1:.3f}/{sh2:.3f}, p={p:.4f}")
        print(f"  H-012 corr: {corr}")
        results["H-841"] = {"sharpe": best_841["sharpe"], "pos_pct": pos_pct,
                            "wf": wf, "sh": (sh1, sh2, p), "corr": corr, "metrics": m,
                            "params": f"W{best_841['window']}_R{best_841['rebal']}_N{best_841['n_ls']}"}
    else:
        print(f"  REJECTED at IS — {pos_pct:.0f}% positive, Sharpe {best_841['sharpe']:.3f}")
        results["H-841"] = {"status": "REJECTED_IS", "pos_pct": pos_pct,
                            "sharpe": best_841["sharpe"]}

    # --- H-842: Volume Autocorrelation ---
    print("\n=== H-842: Volume Autocorrelation ===")
    best_842 = {"sharpe": -99}
    params_842 = []
    for window in [20, 30]:
        sig = volume_autocorrelation_signal(volumes, window)
        for rebal in [3, 5, 7]:
            for n_ls in [3, 4]:
                pnl = xs_backtest(closes, sig, window, rebal, n_ls, "high_long")
                sh = compute_sharpe(pnl)
                params_842.append(sh)
                if sh > best_842["sharpe"]:
                    best_842 = {"sharpe": sh, "window": window, "rebal": rebal,
                                "n_ls": n_ls, "pnl": pnl, "signal": sig}
    pos_pct = sum(1 for s in params_842 if s > 0) / len(params_842) * 100
    print(f"  IS: {pos_pct:.0f}% positive ({sum(1 for s in params_842 if s > 0)}/{len(params_842)})")
    print(f"  Best: W{best_842['window']}_R{best_842['rebal']}_N{best_842['n_ls']} "
          f"Sharpe {best_842['sharpe']:.3f}")
    m = compute_metrics(best_842["pnl"])
    print(f"  Metrics: {m}")
    if pos_pct >= 80 and best_842["sharpe"] > 0.8:
        wf = walk_forward(closes, best_842["signal"], best_842["window"],
                          best_842["rebal"], best_842["n_ls"], "high_long")
        sh1, sh2, p = split_half_test(best_842["pnl"])
        corr = h012_correlation(closes, best_842["signal"], best_842["window"],
                                best_842["rebal"], best_842["n_ls"], "high_long")
        print(f"  WF: {[round(w, 3) for w in wf]} ({sum(1 for w in wf if w > 0)}/{len(wf)})")
        print(f"  SH: {sh1:.3f}/{sh2:.3f}, p={p:.4f}")
        print(f"  H-012 corr: {corr}")
        results["H-842"] = {"sharpe": best_842["sharpe"], "pos_pct": pos_pct,
                            "wf": wf, "sh": (sh1, sh2, p), "corr": corr, "metrics": m,
                            "params": f"W{best_842['window']}_R{best_842['rebal']}_N{best_842['n_ls']}"}
    else:
        print(f"  REJECTED at IS — {pos_pct:.0f}% positive, Sharpe {best_842['sharpe']:.3f}")
        results["H-842"] = {"status": "REJECTED_IS", "pos_pct": pos_pct,
                            "sharpe": best_842["sharpe"]}

    # --- H-843: Range-Vol Ratio ---
    print("\n=== H-843: Intraday Range-Vol Ratio ===")
    best_843 = {"sharpe": -99}
    params_843 = []
    for window in [10, 20, 30]:
        sig = range_vol_ratio_signal(highs, lows, closes, opens, volumes, window)
        for rebal in [3, 5, 7]:
            for n_ls in [3, 4]:
                pnl = xs_backtest(closes, sig, window, rebal, n_ls, "high_long")
                sh = compute_sharpe(pnl)
                params_843.append(sh)
                if sh > best_843["sharpe"]:
                    best_843 = {"sharpe": sh, "window": window, "rebal": rebal,
                                "n_ls": n_ls, "pnl": pnl, "signal": sig}
    pos_pct = sum(1 for s in params_843 if s > 0) / len(params_843) * 100
    print(f"  IS: {pos_pct:.0f}% positive ({sum(1 for s in params_843 if s > 0)}/{len(params_843)})")
    print(f"  Best: W{best_843['window']}_R{best_843['rebal']}_N{best_843['n_ls']} "
          f"Sharpe {best_843['sharpe']:.3f}")
    m = compute_metrics(best_843["pnl"])
    print(f"  Metrics: {m}")
    if pos_pct >= 80 and best_843["sharpe"] > 0.8:
        wf = walk_forward(closes, best_843["signal"], best_843["window"],
                          best_843["rebal"], best_843["n_ls"], "high_long")
        sh1, sh2, p = split_half_test(best_843["pnl"])
        corr = h012_correlation(closes, best_843["signal"], best_843["window"],
                                best_843["rebal"], best_843["n_ls"], "high_long")
        print(f"  WF: {[round(w, 3) for w in wf]} ({sum(1 for w in wf if w > 0)}/{len(wf)})")
        print(f"  SH: {sh1:.3f}/{sh2:.3f}, p={p:.4f}")
        print(f"  H-012 corr: {corr}")
        results["H-843"] = {"sharpe": best_843["sharpe"], "pos_pct": pos_pct,
                            "wf": wf, "sh": (sh1, sh2, p), "corr": corr, "metrics": m,
                            "params": f"W{best_843['window']}_R{best_843['rebal']}_N{best_843['n_ls']}"}
    else:
        print(f"  REJECTED at IS — {pos_pct:.0f}% positive, Sharpe {best_843['sharpe']:.3f}")
        results["H-843"] = {"status": "REJECTED_IS", "pos_pct": pos_pct,
                            "sharpe": best_843["sharpe"]}

    # --- Summary ---
    print("\n" + "=" * 60)
    print("BATCH 1 SUMMARY: Liquidity/Illiquidity Signals")
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
