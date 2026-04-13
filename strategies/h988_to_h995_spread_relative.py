"""
Batch backtest: H-988 to H-995 — Cross-Sectional Spread / Relative Value XS Signals.

H-988: Price Dispersion — cross-sectional std of returns — long in high dispersion (more differentiation)
H-989: Return Rank Persistence — autocorrelation of XS rank — long consistent rankers
H-990: Relative Drawdown — each asset's DD relative to XS median DD — long least drawn down
H-991: Relative Recovery — pct recovered from max DD vs XS median — long fastest recoverers
H-992: Cross-Sectional Skew Position — each asset's return relative to XS distribution — long right-tail
H-993: Pair Spread Momentum — momentum of spread between similar assets — long widening longs
H-994: Relative Volume Profile — volume rank change over time — long improving volume rank
H-995: Cross-Sectional Beta Momentum — momentum of rolling beta to BTC — long increasing beta
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

def price_dispersion(closes, period=20):
    """H-988: Cross-sectional std of returns at each point in time.
    This is a market-level signal — same for all assets. Use as conditioning.
    Instead: rank each asset by how much it contributed to dispersion (abs z-score in XS)."""
    returns = closes.pct_change(period)
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        r = returns.iloc[i]
        r = r.dropna()
        if len(r) < 6:
            continue
        mu = r.mean()
        std = r.std()
        if std == 0:
            continue
        # z-score within cross-section: how extreme is this asset vs peers
        z = (r - mu) / std
        for col in z.index:
            signal.iloc[i, signal.columns.get_loc(col)] = abs(z[col])
    return signal  # high = more extreme (outlier) — direction ambiguous, try both


def return_rank_persistence(closes, period=20, lookback=60):
    """H-989: Autocorrelation of XS rank over time. High = consistent rank (winner stays winner).
    Long persistent rankers, short erratic ones."""
    returns = closes.pct_change(period)
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(lookback + period + 5, len(closes)):
        ranks_hist = []
        for t in range(i - lookback, i, 5):  # sample every 5 days
            r = returns.iloc[t]
            r = r.dropna()
            if len(r) < 8:
                continue
            rk = r.rank()
            ranks_hist.append(rk)
        if len(ranks_hist) < 4:
            continue
        rdf = pd.DataFrame(ranks_hist)
        for col in rdf.columns:
            vals = rdf[col].dropna().values
            if len(vals) < 4:
                continue
            # autocorrelation of rank sequence
            ac = np.corrcoef(vals[:-1], vals[1:])[0, 1]
            if np.isfinite(ac):
                signal.iloc[i, signal.columns.get_loc(col)] = ac
    return signal


def relative_drawdown(closes, period=60):
    """H-990: Each asset's DD relative to XS median DD.
    Long least drawn down (strongest), short most drawn down (weakest)."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        dds = {}
        for col in closes.columns:
            prices = closes[col].iloc[i-period:i+1].values
            if not np.all(np.isfinite(prices)):
                continue
            peak = np.maximum.accumulate(prices)
            dd = (prices[-1] - peak[-1]) / peak[-1] if peak[-1] > 0 else 0
            dds[col] = dd
        if len(dds) < 8:
            continue
        dd_series = pd.Series(dds)
        median_dd = dd_series.median()
        relative = dd_series - median_dd
        for col, val in relative.items():
            signal.iloc[i, signal.columns.get_loc(col)] = val
    return signal  # high = less drawn down relative to peers


def relative_recovery(closes, period=60):
    """H-991: Pct recovered from max DD vs XS median.
    Long fastest recoverers, short still stuck in DD."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        recs = {}
        for col in closes.columns:
            prices = closes[col].iloc[i-period:i+1].values
            if not np.all(np.isfinite(prices)):
                continue
            peak = np.maximum.accumulate(prices)
            dd_from_peak = (prices - peak) / np.where(peak > 0, peak, 1)
            max_dd = np.min(dd_from_peak)
            current_dd = dd_from_peak[-1]
            if max_dd < -0.001:
                recovery = 1.0 - (current_dd / max_dd)  # 1 = fully recovered, 0 = still at max DD
            else:
                recovery = 1.0  # no DD
            recs[col] = recovery
        if len(recs) < 8:
            continue
        for col, val in recs.items():
            signal.iloc[i, signal.columns.get_loc(col)] = val
    return signal


def xs_skew_position(closes, period=20):
    """H-992: Each asset's return relative to XS distribution.
    Asset in right tail of XS = outperforming. Long right-tail, short left-tail."""
    returns = closes.pct_change(period)
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        r = returns.iloc[i]
        r = r.dropna()
        if len(r) < 8:
            continue
        # percentile rank within cross-section
        for col in r.index:
            pctile = (r < r[col]).sum() / (len(r) - 1)
            signal.iloc[i, signal.columns.get_loc(col)] = pctile
    return signal


def relative_volume_profile(volumes, period=20, change_period=20):
    """H-994: Volume rank change over time. Long assets whose volume rank is improving
    (gaining relative attention), short assets whose volume rank is declining."""
    signal = pd.DataFrame(np.nan, index=volumes.index, columns=volumes.columns)
    avg_vol = volumes.rolling(period).mean()
    for i in range(period + change_period + 5, len(volumes)):
        # current volume rank
        curr_vals = avg_vol.iloc[i]
        curr_vals = curr_vals.dropna()
        if len(curr_vals) < 8:
            continue
        curr_rank = curr_vals.rank()
        # past volume rank
        past_vals = avg_vol.iloc[i - change_period]
        past_vals = past_vals.dropna()
        if len(past_vals) < 8:
            continue
        past_rank = past_vals.rank()
        # rank change
        common = curr_rank.index.intersection(past_rank.index)
        for col in common:
            signal.iloc[i, signal.columns.get_loc(col)] = curr_rank[col] - past_rank[col]
    return signal


def xs_beta_momentum(closes, period=60, beta_window=30):
    """H-995: Momentum of rolling beta to BTC. Rising beta = increasing market sensitivity.
    Long increasing beta (trend alignment), short decreasing beta."""
    btc_col = "BTC/USDT"
    if btc_col not in closes.columns:
        return pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    btc_ret = closes[btc_col].pct_change()
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(beta_window + period + 5, len(closes)):
        for col in closes.columns:
            if col == btc_col:
                continue
            # current beta
            br = btc_ret.iloc[i-beta_window:i].values
            ar = returns[col].iloc[i-beta_window:i].values
            mask = np.isfinite(br) & np.isfinite(ar)
            if mask.sum() < 15:
                continue
            beta_now = np.cov(ar[mask], br[mask])[0, 1] / (np.var(br[mask]) + 1e-10)
            # past beta
            br2 = btc_ret.iloc[i-beta_window-period:i-period].values
            ar2 = returns[col].iloc[i-beta_window-period:i-period].values
            mask2 = np.isfinite(br2) & np.isfinite(ar2)
            if mask2.sum() < 15:
                continue
            beta_past = np.cov(ar2[mask2], br2[mask2])[0, 1] / (np.var(br2[mask2]) + 1e-10)
            signal.iloc[i, signal.columns.get_loc(col)] = beta_now - beta_past
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

    # H-988: Price Dispersion (XS outlier score)
    for period in [10, 20, 30, 60]:
        sig = price_dispersion(closes, period)
        # Try both directions — outliers might continue (momentum) or revert
        for direction in ["high_long", "low_long"]:
            tag = "HL" if direction == "high_long" else "LL"
            r = run_signal(f"H-988 (Dispersion P{period} {tag})", sig, closes, period + 5, configs, direction)
            if r.get("sharpe", 0) > results.get("H-988", {}).get("sharpe", -99):
                results["H-988"] = r

    # H-989: Return Rank Persistence
    for period, lb in [(10, 40), (20, 60), (20, 90)]:
        sig = return_rank_persistence(closes, period, lb)
        r = run_signal(f"H-989 (RankPersist P{period}LB{lb})", sig, closes, lb + period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-989", {}).get("sharpe", -99):
            results["H-989"] = r

    # H-990: Relative Drawdown
    for period in [30, 60, 90]:
        sig = relative_drawdown(closes, period)
        r = run_signal(f"H-990 (RelDD P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-990", {}).get("sharpe", -99):
            results["H-990"] = r

    # H-991: Relative Recovery
    for period in [30, 60, 90]:
        sig = relative_recovery(closes, period)
        r = run_signal(f"H-991 (RelRecov P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-991", {}).get("sharpe", -99):
            results["H-991"] = r

    # H-992: XS Skew Position
    for period in [10, 20, 30, 60]:
        sig = xs_skew_position(closes, period)
        r = run_signal(f"H-992 (XSSkew P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-992", {}).get("sharpe", -99):
            results["H-992"] = r

    # H-993: Pair Spread Momentum — skip, too similar to H-032 pairs
    # Instead, test: rolling XS return minus XS mean (demeaned return momentum)
    for period in [20, 30, 60]:
        returns = closes.pct_change(period)
        xs_mean = returns.mean(axis=1)
        sig = returns.subtract(xs_mean, axis=0)
        r = run_signal(f"H-993 (DemeanedMom P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-993", {}).get("sharpe", -99):
            results["H-993"] = r

    # H-994: Relative Volume Profile (volume rank change)
    for period, cp in [(10, 10), (20, 20), (20, 30), (10, 20)]:
        sig = relative_volume_profile(volumes, period, cp)
        r = run_signal(f"H-994 (VolRankChg P{period}C{cp})", sig, closes, period + cp + 5, configs)
        if r.get("sharpe", 0) > results.get("H-994", {}).get("sharpe", -99):
            results["H-994"] = r

    # H-995: XS Beta Momentum
    for period, bw in [(20, 30), (30, 30), (30, 60), (60, 30)]:
        sig = xs_beta_momentum(closes, period, bw)
        r = run_signal(f"H-995 (BetaMom P{period}BW{bw})", sig, closes, bw + period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-995", {}).get("sharpe", -99):
            results["H-995"] = r

    print("\n" + "=" * 60)
    print("BATCH SUMMARY — H-988 to H-995 (Spread / Relative Value)")
    print("=" * 60)
    for key in sorted(results.keys()):
        r = results[key]
        if "status" in r and r["status"] == "REJECTED_IS":
            print(f"  {key}: REJECTED — {r['pos_pct']:.0f}% positive, Sharpe {r['sharpe']:.3f}")
        else:
            wf_pos = sum(1 for w in r["wf"] if w > 0)
            wf_tot = len(r["wf"])
            print(f"  {key}: Sharpe {r['sharpe']:.3f}, WF {wf_pos}/{wf_tot}, "
                  f"SH p={r['sh'][2]:.4f}, corr {r['corr']}, {r['params']}")


if __name__ == "__main__":
    run_batch()
