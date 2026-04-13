"""
Batch backtest: H-1012 to H-1019 — Relative Dynamics XS Signals.

H-1012: Momentum Dispersion — std of cross-sectional returns. Long when dispersion is high (trends), short when low
H-1013: Relative Drawdown Recovery — how fast assets recover from their own drawdowns vs peers
H-1014: Cross-Asset Beta Stability — rolling beta stability to BTC. Stable beta = predictable = long
H-1015: Return Skew Trend — change in return skewness over time. Improving skew = long
H-1016: Relative Volume Rank Persistence — how stable is an asset's volume rank over time
H-1017: Momentum Duration — number of days in current trend direction
H-1018: Price Compression Score — std of log returns over lookback / mean abs return — low = compressed
H-1019: Cumulative Return Efficiency — cumulative return / sum of abs daily returns — trend efficiency
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

def momentum_dispersion(closes, period=20):
    """H-1012: XS dispersion of returns — high dispersion = more room for XS bets.
    Per-asset signal: return * dispersion_zscore. In high-dispersion regimes, momentum works better."""
    returns = closes.pct_change(period)
    disp = returns.std(axis=1)  # XS std
    disp_z = (disp - disp.rolling(60).mean()) / disp.rolling(60).std().replace(0, np.nan)
    # Scale momentum by dispersion z-score
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for col in closes.columns:
        signal[col] = returns[col] * disp_z
    return signal


def relative_drawdown_recovery(closes, period=30):
    """H-1013: Recovery speed from drawdown. Ratio of current price to period-low,
    normalized by how deep the drawdown was. Fast recoverers = resilient."""
    period_low = closes.rolling(period).min()
    period_high = closes.rolling(period).max()
    dd_depth = (period_high - period_low) / period_high
    dd_depth = dd_depth.replace(0, np.nan)
    recovery = (closes - period_low) / (period_high - period_low)
    recovery = recovery.replace(0, np.nan)
    return recovery


def beta_stability(closes, period=60):
    """H-1014: Stability of rolling beta to BTC. Measured as 1/std(rolling_beta).
    Assets with stable beta are more predictable in portfolio context."""
    btc_col = [c for c in closes.columns if 'BTC' in c]
    if not btc_col:
        return pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    btc_ret = closes[btc_col[0]].pct_change()
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    window = 20
    for i in range(period + window + 5, len(closes)):
        for col in closes.columns:
            if col == btc_col[0]:
                signal.iloc[i, signal.columns.get_loc(col)] = 0.5
                continue
            betas = []
            for t in range(i - period, i, 5):
                btc_r = btc_ret.iloc[t - window:t].values
                asset_r = returns[col].iloc[t - window:t].values
                mask = np.isfinite(btc_r) & np.isfinite(asset_r)
                if mask.sum() < 10:
                    continue
                cov = np.cov(btc_r[mask], asset_r[mask])
                if cov[0, 0] > 0:
                    betas.append(cov[0, 1] / cov[0, 0])
            if len(betas) < 4:
                continue
            std_beta = np.std(betas)
            if std_beta > 0:
                signal.iloc[i, signal.columns.get_loc(col)] = 1.0 / std_beta
    return signal


def skew_trend(closes, period=30, lookback=60):
    """H-1015: Change in return skewness. Improving (more positive) skew = long.
    Signal: recent skew - prior skew."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(lookback + period + 5, len(closes)):
        for col in closes.columns:
            recent = returns[col].iloc[i - period:i].dropna().values
            prior = returns[col].iloc[i - lookback:i - period].dropna().values
            if len(recent) < 15 or len(prior) < 15:
                continue
            skew_recent = stats.skew(recent)
            skew_prior = stats.skew(prior)
            if np.isfinite(skew_recent) and np.isfinite(skew_prior):
                signal.iloc[i, signal.columns.get_loc(col)] = skew_recent - skew_prior
    return signal


def volume_rank_persistence(volumes, period=30):
    """H-1016: How stable is an asset's volume rank? Measured by mean rank over period.
    Consistently high-volume = institutional attention."""
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(volumes)):
        ranks_sum = pd.Series(0.0, index=volumes.columns)
        count = 0
        for t in range(i - period, i, 3):
            row = volumes.iloc[t].dropna()
            if len(row) < 8:
                continue
            r = row.rank(pct=True)
            for col in r.index:
                ranks_sum[col] += r[col]
            count += 1
        if count < 4:
            continue
        avg_rank = ranks_sum / count
        for col in avg_rank.index:
            if avg_rank[col] > 0:
                signal.iloc[i, signal.columns.get_loc(col)] = avg_rank[col]
    return signal


def momentum_duration(closes, period=60):
    """H-1017: Number of days in current trend direction.
    Compare to SMA. Days above SMA = uptrend duration. Long persistent trends."""
    sma = closes.rolling(period).mean()
    above = (closes > sma).astype(float)
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 20, len(closes)):
        for col in closes.columns:
            # Count consecutive days above/below SMA ending at i-1
            streak = 0
            direction = above[col].iloc[i - 1]
            for t in range(i - 1, max(i - period, period), -1):
                if above[col].iloc[t] == direction:
                    streak += 1
                else:
                    break
            signal.iloc[i, signal.columns.get_loc(col)] = streak if direction == 1 else -streak
    return signal


def price_compression(closes, period=20):
    """H-1018: Volatility compression — std of returns / mean abs return.
    Low compression (vol > |mean|) = noisy. High compression = directional.
    Signal: 1/coefficient_of_variation of returns."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            rets = returns[col].iloc[i - period:i].dropna().values
            if len(rets) < 10:
                continue
            mean_ret = np.mean(rets)
            std_ret = np.std(rets)
            if std_ret > 0:
                signal.iloc[i, signal.columns.get_loc(col)] = abs(mean_ret) / std_ret
    return signal


def cumulative_return_efficiency(closes, period=30):
    """H-1019: Cumulative return / sum of abs daily returns.
    Efficient = trending (return ~= total path). Inefficient = choppy.
    Long efficient movers, short choppy movers."""
    returns = closes.pct_change()
    signal = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(period + 5, len(closes)):
        for col in closes.columns:
            rets = returns[col].iloc[i - period:i].dropna().values
            if len(rets) < 15:
                continue
            cum_ret = np.sum(rets)
            total_path = np.sum(np.abs(rets))
            if total_path > 0:
                signal.iloc[i, signal.columns.get_loc(col)] = cum_ret / total_path
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
        m = compute_metrics(pnl)
        all_sharpes.append(m["sharpe"])
        if m["sharpe"] > best.get("sharpe", -99):
            best = {"rebal": rebal, "n_ls": n_ls, "direction": direction, **m,
                    "pnl": pnl, "lookback": lookback}

    if best["sharpe"] <= 0:
        pos_pct = sum(1 for s in all_sharpes if s > 0) / len(all_sharpes) * 100 if all_sharpes else 0
        print(f"  Best IS Sharpe: {best['sharpe']:.3f} | {pos_pct:.0f}% positive | SKIP")
        return None

    # Try reverse direction
    for rebal, n_ls in param_configs:
        pnl = xs_backtest(closes, signal_df, lookback, rebal, n_ls,
                          "low_long" if direction == "high_long" else "high_long")
        m = compute_metrics(pnl)
        all_sharpes.append(m["sharpe"])
        if m["sharpe"] > best.get("sharpe", -99):
            rev_dir = "low_long" if direction == "high_long" else "high_long"
            best = {"rebal": rebal, "n_ls": n_ls, "direction": rev_dir, **m,
                    "pnl": pnl, "lookback": lookback}

    pos_pct = sum(1 for s in all_sharpes if s > 0) / len(all_sharpes) * 100 if all_sharpes else 0
    print(f"  Best IS: Sharpe {best['sharpe']:.3f}, Ret {best['annual_ret']:.1f}%, "
          f"DD {best['max_dd']:.1f}% | {pos_pct:.0f}% positive | dir={best['direction']}")

    if best["sharpe"] < 0.8:
        print(f"  IS Sharpe {best['sharpe']:.3f} < 0.8 — SKIP")
        return None

    # Walk-forward
    wf = walk_forward(closes, signal_df, best["lookback"], best["rebal"],
                      best["n_ls"], best["direction"])
    wf_pos = sum(1 for w in wf if w > 0)
    wf_mean = np.mean(wf) if wf else 0
    print(f"  WF: {wf_pos}/{len(wf)} positive, mean {wf_mean:.3f} | folds: {[round(w,2) for w in wf]}")

    if wf_pos < len(wf) * 0.5:
        print(f"  WF {wf_pos}/{len(wf)} < 50% — FAIL")
        return None

    # Split-half test
    sh1, sh2, p_val = split_half_test(best["pnl"])
    print(f"  Split-half: {sh1:.3f} / {sh2:.3f}, SH p={p_val:.4f}")

    # H-012 correlation
    corr = h012_correlation(closes, signal_df, best["lookback"], best["rebal"],
                            best["n_ls"], best["direction"])
    print(f"  H-012 corr: {corr:.3f}")

    status = "CONFIRMED" if (wf_pos >= len(wf) * 0.5 and p_val < 0.10 and abs(corr) < 0.50) else "BORDERLINE"
    print(f"  >>> {status}")

    return {
        "name": name,
        "status": status,
        "sharpe": best["sharpe"],
        "annual_ret": best["annual_ret"],
        "max_dd": best["max_dd"],
        "rebal": best["rebal"],
        "n_ls": best["n_ls"],
        "direction": best["direction"],
        "lookback": best["lookback"],
        "wf": wf,
        "wf_pos": wf_pos,
        "wf_total": len(wf),
        "sh1": sh1,
        "sh2": sh2,
        "p_val": p_val,
        "h012_corr": corr,
        "pos_pct": pos_pct,
    }


if __name__ == "__main__":
    closes, highs, lows, opens, volumes = load_data()
    print(f"Data: {len(closes)} days, {len(closes.columns)} assets, "
          f"{closes.index[0].date()} to {closes.index[-1].date()}")

    param_configs = [(3, 4), (5, 4), (7, 4), (5, 3), (7, 3), (10, 4), (5, 5), (7, 5)]
    results = {}

    # H-1012: Momentum Dispersion
    sig = momentum_dispersion(closes, 20)
    results["H-1012"] = run_signal("H-1012 Momentum × Dispersion", sig, closes, 25, param_configs, "high_long")

    # H-1013: Relative Drawdown Recovery
    sig = relative_drawdown_recovery(closes, 30)
    results["H-1013"] = run_signal("H-1013 DD Recovery (range position)", sig, closes, 35, param_configs, "high_long")

    # H-1014: Beta Stability
    sig = beta_stability(closes, 60)
    results["H-1014"] = run_signal("H-1014 Beta Stability", sig, closes, 65, param_configs, "high_long")

    # H-1015: Skew Trend
    sig = skew_trend(closes, 30, 60)
    results["H-1015"] = run_signal("H-1015 Skew Trend", sig, closes, 65, param_configs, "high_long")

    # H-1016: Volume Rank Persistence
    sig = volume_rank_persistence(volumes, 30)
    results["H-1016"] = run_signal("H-1016 Volume Rank Persistence", sig, closes, 35, param_configs, "high_long")

    # H-1017: Momentum Duration
    sig = momentum_duration(closes, 60)
    results["H-1017"] = run_signal("H-1017 Momentum Duration", sig, closes, 65, param_configs, "high_long")

    # H-1018: Price Compression
    sig = price_compression(closes, 20)
    results["H-1018"] = run_signal("H-1018 Price Compression", sig, closes, 25, param_configs, "high_long")

    # H-1019: Cumulative Return Efficiency
    sig = cumulative_return_efficiency(closes, 30)
    results["H-1019"] = run_signal("H-1019 Return Efficiency", sig, closes, 35, param_configs, "high_long")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    confirmed = []
    for k, v in results.items():
        if v is not None:
            tag = "✓ CONFIRMED" if v["status"] == "CONFIRMED" else "~ BORDERLINE"
            print(f"  {tag} {k}: IS {v['sharpe']:.3f}, WF {v['wf_pos']}/{v['wf_total']}, "
                  f"SH p={v['p_val']:.4f}, corr {v['h012_corr']:.3f}")
            if v["status"] == "CONFIRMED":
                confirmed.append(k)
        else:
            print(f"  ✗ REJECTED {k}")
    print(f"\nConfirmed: {len(confirmed)} — {confirmed}")
