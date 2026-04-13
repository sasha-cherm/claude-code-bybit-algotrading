"""
Batch backtest: H-996 to H-1003 — Adaptive / Conditional Timing XS Signals.

H-996: Trend Acceleration — second derivative of price (momentum of momentum)
H-997: Momentum-Vol Interaction — momentum * (1/vol) — vol-adjusted momentum (different from H-763)
H-998: Funding-Adjusted Return — return minus funding cost — true carry-adjusted momentum
H-999: Volume Climax Reversal — extreme volume as contrarian signal — short after vol climax
H-1000: Price-Volume Divergence Score — price up + vol down (or vice versa) — bearish/bullish divergence
H-1001: Momentum Breadth Score — pct of lookback periods with positive return — breadth of momentum
H-1002: Relative Strength Persistence — RSI rank stability — long consistently strong RSI
H-1003: ATR-Normalized Return — return / ATR — signal per unit of risk taken
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


def load_funding():
    """Load funding rate data."""
    funding = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_funding.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            col = df.columns[0]
            daily = df[col].resample("1D").sum()
            funding[f"{ticker}/USDT"] = daily
        except:
            pass
    if funding:
        return pd.DataFrame(funding).sort_index().dropna(how="all")
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

def trend_acceleration(closes, mom_period=20, accel_period=10):
    """H-996: Second derivative of price — momentum of momentum.
    Positive acceleration = trend strengthening. Long accelerating, short decelerating."""
    mom = closes.pct_change(mom_period)
    accel = mom.diff(accel_period)
    return accel


def momentum_vol_interaction(closes, mom_period=20, vol_period=20):
    """H-997: Momentum / volatility — return per unit risk, XS version.
    Different from H-763 (which used mom * vol ratio). This is pure risk-adjusted return."""
    returns = closes.pct_change()
    mom = closes.pct_change(mom_period)
    vol = returns.rolling(vol_period).std().replace(0, np.nan)
    return mom / vol


def funding_adjusted_return(closes, period=30):
    """H-998: Return minus cumulative funding cost. Assets where return exceeds funding
    cost are generating true alpha. Long true alpha, short funding-drained."""
    funding = load_funding()
    if funding is None:
        # fallback: just return momentum (no funding data)
        return closes.pct_change(period)
    ret = closes.pct_change(period)
    cum_funding = funding.rolling(period).sum()
    # align
    common = [c for c in ret.columns if c in cum_funding.columns]
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for col in common:
        fund_aligned = cum_funding[col].reindex(ret.index, method="ffill")
        signal[col] = ret[col] - fund_aligned
    # non-common: just use ret
    for col in [c for c in ret.columns if c not in common]:
        signal[col] = ret[col]
    return signal


def volume_climax_reversal(volumes, period=20):
    """H-999: Volume climax as contrarian signal. Extreme volume (>2 sigma above mean)
    followed by exhaustion. Short after volume climax, long after volume drought.
    Signal: negative z-score of recent volume."""
    avg = volumes.rolling(period).mean()
    std = volumes.rolling(period).std().replace(0, np.nan)
    z = (volumes - avg) / std
    # Use rolling max of z-score (captures recent climax)
    z_max = z.rolling(5).max()
    return -z_max  # negative: short after climax, long after drought


def price_volume_divergence(closes, volumes, period=20):
    """H-1000: Price-volume divergence. Price up + volume down = bearish divergence.
    Price down + volume down = bullish (selling exhaustion).
    Signal: correlation of price change direction and volume change over lookback."""
    price_chg = closes.pct_change(period)
    vol_chg = volumes.pct_change(period)
    # Divergence: price up but vol down (bearish) or price down but vol up (bearish)
    # Convergence: price up and vol up (bullish) or price down and vol down (bullish setup)
    # Simple: sign agreement = convergent = bullish
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 10, len(closes)):
        for col in closes.columns:
            pc = price_chg[col].iloc[i-10:i].values
            vc = vol_chg[col].iloc[i-10:i].values
            mask = np.isfinite(pc) & np.isfinite(vc)
            if mask.sum() < 5:
                continue
            corr = np.corrcoef(pc[mask], vc[mask])[0, 1]
            if np.isfinite(corr):
                signal.iloc[i, signal.columns.get_loc(col)] = corr
    return signal  # positive corr = convergent (bullish), negative = divergent


def momentum_breadth(closes, period=60):
    """H-1001: Pct of sub-periods with positive return.
    High breadth = consistent uptrend (not driven by a single spike).
    Long broad momentum, short narrow/spiky momentum."""
    returns = closes.pct_change(5)  # weekly returns
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    n_subperiods = period // 5
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            weekly_rets = []
            for k in range(n_subperiods):
                idx = i - k * 5
                if idx >= 0 and idx < len(returns):
                    r = returns[col].iloc[idx]
                    if np.isfinite(r):
                        weekly_rets.append(r)
            if len(weekly_rets) < 4:
                continue
            breadth = sum(1 for r in weekly_rets if r > 0) / len(weekly_rets)
            signal.iloc[i, signal.columns.get_loc(col)] = breadth
    return signal


def rsi_rank_stability(closes, rsi_period=14, lookback=60):
    """H-1002: Stability of RSI rank over time. Long consistently high RSI rank, short erratic."""
    # Compute RSI
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=rsi_period - 1, min_periods=rsi_period).mean()
    avg_loss = loss.ewm(com=rsi_period - 1, min_periods=rsi_period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(rsi_period + lookback + 5, len(closes)):
        # Mean RSI rank over lookback
        rsi_ranks = []
        for t in range(i - lookback, i, 5):
            row = rsi.iloc[t]
            row = row.dropna()
            if len(row) < 8:
                continue
            rsi_ranks.append(row.rank(pct=True))
        if len(rsi_ranks) < 4:
            continue
        rdf = pd.DataFrame(rsi_ranks)
        for col in rdf.columns:
            vals = rdf[col].dropna().values
            if len(vals) < 4:
                continue
            signal.iloc[i, signal.columns.get_loc(col)] = np.mean(vals)
    return signal


def atr_normalized_return(closes, highs, lows, return_period=20, atr_period=14):
    """H-1003: Return / ATR — signal strength relative to recent volatility.
    High = strong move for the amount of vol. Long efficient movers, short noisy movers."""
    tr = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for col in closes.columns:
        h = highs[col]
        l = lows[col]
        c = closes[col].shift(1)
        tr[col] = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()
    atr_pct = atr / closes  # ATR as pct of price
    ret = closes.pct_change(return_period)
    atr_pct = atr_pct.replace(0, np.nan)
    return ret / atr_pct


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

    # H-996: Trend Acceleration
    for mp, ap in [(10, 5), (20, 10), (30, 10), (60, 20)]:
        sig = trend_acceleration(closes, mp, ap)
        r = run_signal(f"H-996 (TrendAccel M{mp}A{ap})", sig, closes, mp + ap + 5, configs)
        if r.get("sharpe", 0) > results.get("H-996", {}).get("sharpe", -99):
            results["H-996"] = r

    # H-997: Momentum-Vol Interaction
    for mp, vp in [(10, 20), (20, 20), (30, 30), (60, 30)]:
        sig = momentum_vol_interaction(closes, mp, vp)
        r = run_signal(f"H-997 (MomVolInt M{mp}V{vp})", sig, closes, max(mp, vp) + 5, configs)
        if r.get("sharpe", 0) > results.get("H-997", {}).get("sharpe", -99):
            results["H-997"] = r

    # H-998: Funding-Adjusted Return
    for period in [14, 30, 60]:
        sig = funding_adjusted_return(closes, period)
        r = run_signal(f"H-998 (FundAdj P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-998", {}).get("sharpe", -99):
            results["H-998"] = r

    # H-999: Volume Climax Reversal
    for period in [10, 14, 20, 30]:
        sig = volume_climax_reversal(volumes, period)
        r = run_signal(f"H-999 (VolClimax P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-999", {}).get("sharpe", -99):
            results["H-999"] = r

    # H-1000: Price-Volume Divergence
    for period in [10, 20, 30]:
        sig = price_volume_divergence(closes, volumes, period)
        r = run_signal(f"H-1000 (PVDiv P{period})", sig, closes, period + 10, configs)
        if r.get("sharpe", 0) > results.get("H-1000", {}).get("sharpe", -99):
            results["H-1000"] = r

    # H-1001: Momentum Breadth
    for period in [30, 60, 90]:
        sig = momentum_breadth(closes, period)
        r = run_signal(f"H-1001 (MomBreadth P{period})", sig, closes, period + 5, configs)
        if r.get("sharpe", 0) > results.get("H-1001", {}).get("sharpe", -99):
            results["H-1001"] = r

    # H-1002: RSI Rank Stability
    for rsi_p, lb in [(14, 40), (14, 60), (14, 90)]:
        sig = rsi_rank_stability(closes, rsi_p, lb)
        r = run_signal(f"H-1002 (RSIStab R{rsi_p}LB{lb})", sig, closes, rsi_p + lb + 5, configs)
        if r.get("sharpe", 0) > results.get("H-1002", {}).get("sharpe", -99):
            results["H-1002"] = r

    # H-1003: ATR-Normalized Return
    for rp, ap in [(10, 14), (20, 14), (30, 20), (60, 20)]:
        sig = atr_normalized_return(closes, highs, lows, rp, ap)
        r = run_signal(f"H-1003 (ATRNormRet R{rp}A{ap})", sig, closes, max(rp, ap) + 5, configs)
        if r.get("sharpe", 0) > results.get("H-1003", {}).get("sharpe", -99):
            results["H-1003"] = r

    print("\n" + "=" * 60)
    print("BATCH SUMMARY — H-996 to H-1003 (Adaptive / Conditional)")
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
