"""
Batch backtest: H-700 to H-707 — Advanced OI-based XS and TS signals.

Uses real OI data from Bybit (fetched fresh). Prior OI tests (H-179, H-193, H-268)
used limited data or simpler approaches. Now with 2000+ days of OI history.

H-700: OI Velocity (2nd derivative) XS — acceleration of OI change
H-701: OI-Volume Ratio XS — positioning density (OI per unit volume)
H-702: OI-Funding Interaction XS — combined crowding signal
H-703: OI Surprise XS — OI change unexplained by volume
H-704: OI Mean Reversion XS — OI percentile rank (RSI-like)
H-705: BTC OI Breakout TS — OI above MA + price above MA = conviction
H-706: BTC OI-Price Regime TS — 4-quadrant regime model
H-707: Multi-Asset OI Momentum TS — aggregate OI growth across top assets

Standard framework: grid search, IS >=80%, walk-forward OOS, split-half, H-012 corr.
"""

import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
FEE_RATE = 0.00055
SLIPPAGE_BPS = 2

ASSETS = ["BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX", "LINK",
          "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM"]

# ============================================================
# DATA LOADING
# ============================================================

def load_data():
    closes = {}
    volumes = {}
    oi = {}

    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_1d.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            closes[f"{ticker}/USDT"] = df["close"]
            volumes[f"{ticker}/USDT"] = df["volume"] * df["close"]
        except Exception as e:
            print(f"  Skip {ticker} OHLCV: {e}")

        try:
            oi_df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_oi_daily.parquet")
            if oi_df.index.tz is not None:
                oi_df.index = oi_df.index.tz_localize(None)
            oi[f"{ticker}/USDT"] = oi_df["openInterest"]
        except Exception as e:
            print(f"  Skip {ticker} OI: {e}")

    closes = pd.DataFrame(closes).sort_index().dropna(how="all")
    volumes = pd.DataFrame(volumes).sort_index().dropna(how="all")
    oi_panel = pd.DataFrame(oi).sort_index().dropna(how="all")

    common_idx = closes.index.intersection(oi_panel.index)
    closes = closes.loc[common_idx]
    volumes = volumes.loc[common_idx]
    oi_panel = oi_panel.loc[common_idx]

    return closes, volumes, oi_panel


def load_funding():
    funding = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"funding_{ticker}USDT.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            daily_fr = df["funding_rate"].resample("1D").sum()
            funding[f"{ticker}/USDT"] = daily_fr
        except:
            pass
    return pd.DataFrame(funding).sort_index().dropna(how="all")


# ============================================================
# BACKTEST ENGINE (XS)
# ============================================================

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
            sig_row = signal_df.iloc[i - 1]  # lag by 1 day
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
    total = len(closes) - lookback - 5
    min_train = 200
    results = []

    for fold in range(n_folds):
        test_end = len(closes) - fold * test_days
        test_start = test_end - test_days
        if test_start < min_train + lookback + 5:
            break

        c_test = closes.iloc[test_start - lookback - 5:test_end]
        s_test = signal_df.iloc[test_start - lookback - 5:test_end]

        pnl = xs_backtest(c_test, s_test, lookback, rebal, n_ls, direction)
        sh = compute_sharpe(pnl)
        results.append(sh)

    return results


def split_half(closes, signal_df, lookback, rebal, n_ls, direction):
    mid = len(closes) // 2
    c1 = closes.iloc[:mid + lookback]
    s1 = signal_df.iloc[:mid + lookback]
    c2 = closes.iloc[mid:]
    s2 = signal_df.iloc[mid:]

    pnl1 = xs_backtest(c1, s1, lookback, rebal, n_ls, direction)
    pnl2 = xs_backtest(c2, s2, lookback, rebal, n_ls, direction)
    return compute_sharpe(pnl1), compute_sharpe(pnl2)


def h012_correlation(closes, signal_df, lookback, rebal, n_ls, direction):
    pnl_test = xs_backtest(closes, signal_df, lookback, rebal, n_ls, direction)
    # H-012: 60d momentum
    ret60 = closes.pct_change(60)
    pnl_h012 = xs_backtest(closes, ret60, 60, 5, 4, "high_long")
    mn = min(len(pnl_test), len(pnl_h012))
    if mn < 30:
        return 0
    return round(np.corrcoef(pnl_test[:mn], pnl_h012[:mn])[0, 1], 3)


# ============================================================
# TIME-SERIES BACKTEST ENGINE
# ============================================================

def ts_backtest(prices, signal, fee_rate=FEE_RATE):
    ret = prices.pct_change().iloc[1:]
    sig = signal.shift(1).iloc[1:]  # lag signal
    common = ret.index.intersection(sig.dropna().index)
    ret = ret.loc[common]
    sig = sig.loc[common]

    pnl = []
    prev_pos = 0
    for i in range(len(ret)):
        pos = sig.iloc[i]
        turnover = abs(pos - prev_pos)
        cost = turnover * fee_rate + turnover * SLIPPAGE_BPS / 10_000
        daily_pnl = pos * ret.iloc[i] - cost
        pnl.append(daily_pnl)
        prev_pos = pos
    return np.array(pnl)


def ts_walk_forward(prices, signal_fn, n_folds=6, test_days=100):
    results = []
    for fold in range(n_folds):
        test_end = len(prices) - fold * test_days
        test_start = test_end - test_days
        if test_start < 200:
            break
        p = prices.iloc[:test_end]
        sig = signal_fn(p)
        sig_test = sig.iloc[test_start:test_end]
        p_test = prices.iloc[test_start:test_end]
        pnl = ts_backtest(p_test, sig_test)
        results.append(compute_sharpe(pnl))
    return results


def ts_split_half(prices, signal_fn):
    mid = len(prices) // 2
    p1 = prices.iloc[:mid]
    p2 = prices.iloc[mid:]
    sig1 = signal_fn(p1)
    sig2 = signal_fn(p2)
    pnl1 = ts_backtest(p1, sig1)
    pnl2 = ts_backtest(p2, sig2)
    return compute_sharpe(pnl1), compute_sharpe(pnl2)


def ts_param_robustness(prices, signal_fn_factory, param_grid):
    pos = 0
    total = 0
    for params in param_grid:
        sig_fn = signal_fn_factory(*params)
        sig = sig_fn(prices)
        pnl = ts_backtest(prices, sig)
        if compute_sharpe(pnl) > 0:
            pos += 1
        total += 1
    return pos, total


def h009_correlation(prices, signal):
    pnl_test = ts_backtest(prices, signal)
    ema5 = prices.ewm(span=5).mean()
    ema40 = prices.ewm(span=40).mean()
    sig_h009 = (ema5 > ema40).astype(float) * 2 - 1
    pnl_h009 = ts_backtest(prices, sig_h009)
    mn = min(len(pnl_test), len(pnl_h009))
    if mn < 30:
        return 0
    return round(np.corrcoef(pnl_test[:mn], pnl_h009[:mn])[0, 1], 3)


# ============================================================
# XS SIGNAL GENERATORS
# ============================================================

def oi_velocity_signal(closes, oi_panel, lookback):
    """H-700: 2nd derivative of OI — acceleration of OI change."""
    oi_change = oi_panel.pct_change(lookback)
    oi_prev_change = oi_panel.pct_change(lookback).shift(lookback)
    velocity = oi_change - oi_prev_change
    return velocity.reindex(closes.index).ffill()


def oi_volume_ratio_signal(oi_panel, volumes, lookback):
    """H-701: OI / rolling volume — positioning density."""
    oi_aligned = oi_panel.reindex(volumes.index).ffill()
    roll_vol = volumes.rolling(lookback).mean()
    ratio = oi_aligned / roll_vol.replace(0, np.nan)
    return ratio


def oi_funding_interaction_signal(oi_panel, funding, closes, lookback):
    """H-702: OI growth × funding rate = crowding score."""
    oi_growth = oi_panel.pct_change(lookback)
    oi_aligned = oi_growth.reindex(closes.index).ffill()
    fr_aligned = funding.reindex(closes.index).ffill()
    fr_roll = fr_aligned.rolling(lookback).mean()
    crowding = oi_aligned * fr_roll
    return crowding


def oi_surprise_signal(oi_panel, volumes, closes, lookback):
    """H-703: OI change residual after controlling for volume change."""
    oi_chg = oi_panel.pct_change(lookback)
    vol_chg = volumes.pct_change(lookback)
    oi_aligned = oi_chg.reindex(closes.index).ffill()
    vol_aligned = vol_chg.reindex(closes.index).ffill()
    surprise = oi_aligned - vol_aligned
    return surprise


def oi_mean_reversion_signal(oi_panel, closes, lookback):
    """H-704: OI percentile rank (RSI-like). High = crowded, Low = under-positioned."""
    oi_aligned = oi_panel.reindex(closes.index).ffill()
    oi_pctrank = oi_aligned.rolling(lookback).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
    )
    return oi_pctrank


# ============================================================
# TS SIGNAL GENERATORS
# ============================================================

def btc_oi_breakout_signal_factory(oi_ma, price_ma):
    """H-705: Long BTC when OI > OI_MA and Price > Price_MA."""
    def make_signal(prices):
        oi_btc = pd.read_parquet(DATA_DIR / "BTC_USDT_oi_daily.parquet")
        if oi_btc.index.tz is not None:
            oi_btc.index = oi_btc.index.tz_localize(None)
        oi_s = oi_btc["openInterest"].reindex(prices.index).ffill()
        oi_above = oi_s > oi_s.rolling(oi_ma).mean()
        price_above = prices > prices.rolling(price_ma).mean()
        sig = pd.Series(0.0, index=prices.index)
        sig[oi_above & price_above] = 1.0
        sig[~oi_above & ~price_above] = -1.0
        return sig
    return make_signal


def btc_oi_regime_signal_factory(lookback):
    """H-706: 4-quadrant regime (OI change × Price change)."""
    def make_signal(prices):
        oi_btc = pd.read_parquet(DATA_DIR / "BTC_USDT_oi_daily.parquet")
        if oi_btc.index.tz is not None:
            oi_btc.index = oi_btc.index.tz_localize(None)
        oi_s = oi_btc["openInterest"].reindex(prices.index).ffill()
        oi_chg = oi_s.pct_change(lookback)
        price_chg = prices.pct_change(lookback)
        sig = pd.Series(0.0, index=prices.index)
        # OI up + Price up = bullish continuation
        sig[(oi_chg > 0) & (price_chg > 0)] = 1.0
        # OI down + Price down = capitulation → bullish reversal
        sig[(oi_chg < 0) & (price_chg < 0)] = 1.0
        # OI up + Price down = selling/accumulation → bearish
        sig[(oi_chg > 0) & (price_chg < 0)] = -1.0
        # OI down + Price up = squeeze/topping → neutral
        sig[(oi_chg < 0) & (price_chg > 0)] = 0.0
        return sig
    return make_signal


def multi_asset_oi_signal_factory(n_assets, lookback):
    """H-707: Aggregate OI growth across top-N assets as BTC timing signal."""
    def make_signal(prices):
        oi_data = {}
        for t in ["BTC", "ETH", "SOL", "XRP", "DOGE"]:
            try:
                df = pd.read_parquet(DATA_DIR / f"{t}_USDT_oi_daily.parquet")
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                oi_data[t] = df["openInterest"]
            except:
                pass

        oi_df = pd.DataFrame(oi_data).reindex(prices.index).ffill()
        oi_growth = oi_df.pct_change(lookback)
        avg_growth = oi_growth.iloc[:, :n_assets].mean(axis=1)
        sig = pd.Series(0.0, index=prices.index)
        sig[avg_growth > 0] = 1.0
        sig[avg_growth < 0] = -1.0
        return sig
    return make_signal


# ============================================================
# BATCH RUNNER
# ============================================================

def run_xs_batch(title, hyp_id, signal_df, closes, grid, min_is_pct=0.8):
    print(f"\n{'='*70}")
    print(f"{hyp_id}: {title}")
    print(f"{'='*70}")

    results = []
    for lb, rebal, n_ls, direction in grid:
        pnl = xs_backtest(closes, signal_df, lb, rebal, n_ls, direction)
        sh = compute_sharpe(pnl)
        m = compute_metrics(pnl)
        results.append({
            "lb": lb, "rebal": rebal, "n": n_ls, "dir": direction,
            "sharpe": sh, **m
        })

    df_res = pd.DataFrame(results)
    total = len(df_res)
    positive = (df_res["sharpe"] > 0).sum()
    is_pct = positive / total

    # Best direction
    for d in ["high_long", "low_long"]:
        sub = df_res[df_res["dir"] == d]
        d_pos = (sub["sharpe"] > 0).sum()
        d_pct = d_pos / len(sub) if len(sub) > 0 else 0
        if d_pct > 0.5:
            print(f"  {d}: {d_pos}/{len(sub)} positive ({d_pct*100:.0f}%)")

    best_dir = None
    best_pct = 0
    for d in ["high_long", "low_long"]:
        sub = df_res[df_res["dir"] == d]
        d_pct = (sub["sharpe"] > 0).sum() / len(sub) if len(sub) > 0 else 0
        if d_pct > best_pct:
            best_pct = d_pct
            best_dir = d

    if best_pct < min_is_pct:
        print(f"  IS: {best_pct*100:.0f}% ({best_dir}) — BELOW {min_is_pct*100:.0f}% THRESHOLD. REJECTED.")
        return {"status": "REJECTED", "is_pct": best_pct, "best_dir": best_dir}

    best_sub = df_res[df_res["dir"] == best_dir]
    best_row = best_sub.loc[best_sub["sharpe"].idxmax()]
    lb, rebal, n_ls = int(best_row["lb"]), int(best_row["rebal"]), int(best_row["n"])
    print(f"  IS: {best_pct*100:.0f}% ({best_dir})")
    print(f"  Best: LB{lb}_R{rebal}_N{n_ls} Sharpe {best_row['sharpe']:.3f}, "
          f"Ann {best_row['annual_ret']:.1f}%, DD {best_row['max_dd']:.1f}%")

    # Param robustness
    param_pos = (best_sub["sharpe"] > 0).sum()
    param_total = len(best_sub)
    param_pct = param_pos / param_total
    print(f"  Params: {param_pos}/{param_total} ({param_pct*100:.0f}%)")

    # Walk-forward
    wf = walk_forward(closes, signal_df, lb, rebal, n_ls, best_dir)
    wf_pos = sum(1 for s in wf if s > 0)
    wf_mean = np.mean(wf) if wf else 0
    print(f"  WF: {wf_pos}/{len(wf)} positive, mean {wf_mean:.3f}")

    # Split-half
    sh1, sh2 = split_half(closes, signal_df, lb, rebal, n_ls, best_dir)
    sh_pass = sh1 > 0 and sh2 > 0
    print(f"  SH: H1={sh1:.3f}, H2={sh2:.3f} {'PASS' if sh_pass else 'FAIL'}")

    # H-012 correlation
    corr = h012_correlation(closes, signal_df, lb, rebal, n_ls, best_dir)
    print(f"  H-012 corr: {corr}")

    confirmed = (wf_pos >= len(wf) * 0.6 and param_pct >= 0.8 and
                 sh_pass and best_row["sharpe"] >= 0.7)
    status = "CONFIRMED" if confirmed else "BORDERLINE" if wf_pos >= len(wf) * 0.5 else "REJECTED"
    print(f"  => {status}")

    return {
        "status": status, "is_pct": best_pct, "best_dir": best_dir,
        "best_params": f"LB{lb}_R{rebal}_N{n_ls}",
        "sharpe": best_row["sharpe"], "annual_ret": best_row["annual_ret"],
        "max_dd": best_row["max_dd"], "param_pct": param_pct,
        "wf": wf, "wf_pos": wf_pos, "sh": (sh1, sh2), "sh_pass": sh_pass,
        "corr_h012": corr
    }


def run_ts_batch(title, hyp_id, prices, signal_fn, param_grid_for_robust=None,
                 signal_fn_factory=None):
    print(f"\n{'='*70}")
    print(f"{hyp_id}: {title}")
    print(f"{'='*70}")

    sig = signal_fn(prices)
    pnl = ts_backtest(prices, sig)
    m = compute_metrics(pnl)
    print(f"  IS: Sharpe {m['sharpe']:.3f}, Ann {m['annual_ret']:.1f}%, DD {m['max_dd']:.1f}%")

    if m["sharpe"] < 0.5:
        print(f"  => REJECTED (IS Sharpe < 0.5)")
        return {"status": "REJECTED", **m}

    # Param robustness
    if param_grid_for_robust and signal_fn_factory:
        pr_pos, pr_total = ts_param_robustness(prices, signal_fn_factory, param_grid_for_robust)
        pr_pct = pr_pos / pr_total if pr_total > 0 else 0
        print(f"  Params: {pr_pos}/{pr_total} ({pr_pct*100:.0f}%)")
    else:
        pr_pct = 1.0

    # Walk-forward
    wf = ts_walk_forward(prices, signal_fn)
    wf_pos = sum(1 for s in wf if s > 0)
    wf_mean = np.mean(wf) if wf else 0
    print(f"  WF: {wf_pos}/{len(wf)} positive, mean {wf_mean:.3f}")

    # Split-half
    sh1, sh2 = ts_split_half(prices, signal_fn)
    sh_pass = sh1 > 0 and sh2 > 0
    print(f"  SH: H1={sh1:.3f}, H2={sh2:.3f} {'PASS' if sh_pass else 'FAIL'}")

    # H-009 correlation
    corr = h009_correlation(prices, sig)
    print(f"  H-009 corr: {corr}")

    confirmed = (wf_pos >= len(wf) * 0.6 and pr_pct >= 0.75 and
                 sh_pass and m["sharpe"] >= 0.7)
    status = "CONFIRMED" if confirmed else "BORDERLINE" if wf_pos >= len(wf) * 0.5 else "REJECTED"
    print(f"  => {status}")

    return {
        "status": status, **m, "param_pct": pr_pct,
        "wf": wf, "wf_pos": wf_pos, "sh": (sh1, sh2), "sh_pass": sh_pass,
        "corr_h009": corr
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("Loading data...")
    closes, volumes, oi_panel = load_data()
    funding = load_funding()
    print(f"Common period: {closes.index[0].date()} to {closes.index[-1].date()} ({len(closes)} days)")
    print(f"Assets: {len(closes.columns)}")
    print(f"OI assets: {len(oi_panel.columns)}")

    # Standard XS grid
    lookbacks = [10, 20, 30]
    rebals = [3, 5, 7]
    ns = [3, 4]
    directions = ["high_long", "low_long"]
    xs_grid = [(lb, r, n, d) for lb in lookbacks for r in rebals
               for n in ns for d in directions]
    print(f"XS grid: {len(xs_grid)} combos")

    # =============================================
    # H-700: OI Velocity XS
    # =============================================
    all_results = {}

    for lb in lookbacks:
        sig = oi_velocity_signal(closes, oi_panel, lb)
        # Only run once per lookback; grid varies rebal/n/dir
        grid_sub = [(lb, r, n, d) for r in rebals for n in ns for d in directions]
        r = run_xs_batch("OI Velocity (2nd derivative) XS", "H-700",
                         sig, closes, grid_sub)
        all_results["H-700"] = r
        if r["status"] != "REJECTED":
            break
    if "H-700" not in all_results:
        sig = oi_velocity_signal(closes, oi_panel, 20)
        r = run_xs_batch("OI Velocity (2nd derivative) XS", "H-700",
                         sig, closes, [(20, r, n, d) for r in rebals for n in ns for d in directions])
        all_results["H-700"] = r

    # =============================================
    # H-701: OI-Volume Ratio XS
    # =============================================
    best_r = None
    for lb in lookbacks:
        sig = oi_volume_ratio_signal(oi_panel, volumes, lb)
        sig = sig.reindex(closes.index).ffill()
        grid_sub = [(lb, r, n, d) for r in rebals for n in ns for d in directions]
        r = run_xs_batch("OI-Volume Ratio (Positioning Density) XS", "H-701",
                         sig, closes, grid_sub)
        if r["status"] != "REJECTED":
            best_r = r
            break
    all_results["H-701"] = best_r if best_r else r

    # =============================================
    # H-702: OI-Funding Interaction XS
    # =============================================
    best_r = None
    for lb in lookbacks:
        sig = oi_funding_interaction_signal(oi_panel, funding, closes, lb)
        grid_sub = [(lb, r, n, d) for r in rebals for n in ns for d in directions]
        r = run_xs_batch("OI-Funding Interaction (Crowding) XS", "H-702",
                         sig, closes, grid_sub)
        if r["status"] != "REJECTED":
            best_r = r
            break
    all_results["H-702"] = best_r if best_r else r

    # =============================================
    # H-703: OI Surprise XS
    # =============================================
    best_r = None
    for lb in lookbacks:
        sig = oi_surprise_signal(oi_panel, volumes, closes, lb)
        grid_sub = [(lb, r, n, d) for r in rebals for n in ns for d in directions]
        r = run_xs_batch("OI Surprise (Residual) XS", "H-703",
                         sig, closes, grid_sub)
        if r["status"] != "REJECTED":
            best_r = r
            break
    all_results["H-703"] = best_r if best_r else r

    # =============================================
    # H-704: OI Mean Reversion XS
    # =============================================
    for lb in [60, 90, 120]:
        sig = oi_mean_reversion_signal(oi_panel, closes, lb)
        grid_sub = [(lb, r, n, d) for r in rebals for n in ns for d in directions]
        r = run_xs_batch("OI Mean Reversion (Percentile Rank) XS", "H-704",
                         sig, closes, grid_sub)
        all_results["H-704"] = r
        if r["status"] != "REJECTED":
            break

    # =============================================
    # H-705: BTC OI Breakout TS
    # =============================================
    btc_prices = closes["BTC/USDT"].dropna()

    param_grid_705 = [(oi_ma, p_ma) for oi_ma in [10, 20, 30, 50]
                      for p_ma in [10, 20, 30, 50]]
    best_ts = None
    best_sh = -999
    for oi_ma, p_ma in param_grid_705:
        sig_fn = btc_oi_breakout_signal_factory(oi_ma, p_ma)
        pnl = ts_backtest(btc_prices, sig_fn(btc_prices))
        sh = compute_sharpe(pnl)
        if sh > best_sh:
            best_sh = sh
            best_ts = (oi_ma, p_ma)

    if best_ts:
        oi_ma, p_ma = best_ts
        sig_fn = btc_oi_breakout_signal_factory(oi_ma, p_ma)
        r = run_ts_batch("BTC OI Breakout TS", "H-705", btc_prices, sig_fn,
                         param_grid_705,
                         lambda om, pm: btc_oi_breakout_signal_factory(om, pm))
        all_results["H-705"] = r

    # =============================================
    # H-706: BTC OI-Price Regime TS
    # =============================================
    param_grid_706 = [(lb,) for lb in [5, 10, 14, 20, 30]]
    best_ts = None
    best_sh = -999
    for (lb,) in param_grid_706:
        sig_fn = btc_oi_regime_signal_factory(lb)
        pnl = ts_backtest(btc_prices, sig_fn(btc_prices))
        sh = compute_sharpe(pnl)
        if sh > best_sh:
            best_sh = sh
            best_ts = lb

    if best_ts:
        sig_fn = btc_oi_regime_signal_factory(best_ts)
        r = run_ts_batch("BTC OI-Price Regime TS", "H-706", btc_prices, sig_fn,
                         param_grid_706,
                         lambda lb: btc_oi_regime_signal_factory(lb))
        all_results["H-706"] = r

    # =============================================
    # H-707: Multi-Asset OI Momentum TS
    # =============================================
    param_grid_707 = [(n, lb) for n in [3, 5] for lb in [5, 10, 14, 20, 30]]
    best_ts = None
    best_sh = -999
    for n_a, lb in param_grid_707:
        sig_fn = multi_asset_oi_signal_factory(n_a, lb)
        pnl = ts_backtest(btc_prices, sig_fn(btc_prices))
        sh = compute_sharpe(pnl)
        if sh > best_sh:
            best_sh = sh
            best_ts = (n_a, lb)

    if best_ts:
        n_a, lb = best_ts
        sig_fn = multi_asset_oi_signal_factory(n_a, lb)
        r = run_ts_batch("Multi-Asset OI Momentum TS", "H-707", btc_prices, sig_fn,
                         param_grid_707,
                         lambda n, l: multi_asset_oi_signal_factory(n, l))
        all_results["H-707"] = r

    # =============================================
    # SUMMARY
    # =============================================
    print(f"\n{'='*70}")
    print("BATCH SUMMARY: H-700 to H-707")
    print(f"{'='*70}")
    for hid, r in sorted(all_results.items()):
        status = r.get("status", "?")
        sharpe = r.get("sharpe", 0)
        corr = r.get("corr_h012", r.get("corr_h009", "?"))
        print(f"  {hid}: {status} (Sharpe {sharpe:.3f}, corr {corr})")
