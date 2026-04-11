"""
Batch backtest: H-748 to H-755 — Correlation dynamics and relative value signals.

How do cross-asset correlation patterns predict returns?

H-748: Correlation Breakaway XS — assets decorrelating from market get momentum
H-749: Pairwise Correlation Change XS — assets losing/gaining correlations
H-750: Relative Strength Index XS — RSI of price relative to BTC
H-751: Mean-Distance XS — distance from rolling mean (contrarian)
H-752: Sector Rotation XS — layer-1 vs layer-2 rotation signal
H-753: Correlation Concentration XS — how tightly correlated with peers
H-754: Lead-Lag Signal XS — assets that lead BTC by 1 day
H-755: Cross-Correlation Momentum XS — momentum of an asset's correlation with BTC
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

LAYER1 = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "AVAX/USDT", "NEAR/USDT"]
LAYER2 = ["OP/USDT", "ARB/USDT", "LINK/USDT", "DOT/USDT", "ATOM/USDT"]
MEME = ["DOGE/USDT", "XRP/USDT", "ADA/USDT"]


def load_data():
    closes = {}
    volumes = {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_1d.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            closes[f"{ticker}/USDT"] = df["close"]
            volumes[f"{ticker}/USDT"] = df["volume"] * df["close"]
        except:
            pass
    closes = pd.DataFrame(closes).sort_index().dropna(how="all")
    volumes = pd.DataFrame(volumes).sort_index().dropna(how="all")
    return closes, volumes


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
    mid = len(pnl) // 2
    h1 = pnl[:mid]
    h2 = pnl[mid:]
    sh1 = compute_sharpe(h1)
    sh2 = compute_sharpe(h2)
    t_stat, p_val = stats.ttest_1samp(pnl, 0)
    return sh1, sh2, p_val


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

def correlation_breakaway_signal(closes, window):
    """H-748: Change in rolling correlation with BTC."""
    returns = closes.pct_change()
    btc_ret = returns["BTC/USDT"]
    result = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        if col == "BTC/USDT":
            continue
        corr_now = returns[col].rolling(window).corr(btc_ret)
        corr_prev = returns[col].rolling(window).corr(btc_ret).shift(window)
        result[col] = corr_now - corr_prev
    return result


def pairwise_corr_change_signal(closes, window):
    """H-749: Average correlation change with all other assets."""
    returns = closes.pct_change()
    result = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        avg_corr_now = pd.Series(0.0, index=closes.index)
        avg_corr_prev = pd.Series(0.0, index=closes.index)
        cnt = 0
        for other in closes.columns:
            if other == col:
                continue
            c_now = returns[col].rolling(window).corr(returns[other])
            c_prev = returns[col].rolling(window).corr(returns[other]).shift(window)
            avg_corr_now += c_now.fillna(0)
            avg_corr_prev += c_prev.fillna(0)
            cnt += 1
        if cnt > 0:
            result[col] = (avg_corr_now - avg_corr_prev) / cnt
    return result


def relative_strength_rsi_signal(closes, window):
    """H-750: RSI of price relative to BTC."""
    btc = closes["BTC/USDT"]
    result = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        if col == "BTC/USDT":
            continue
        relative = closes[col] / btc
        delta = relative.diff()
        gain = delta.where(delta > 0, 0).rolling(window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        result[col] = rsi
    return result


def mean_distance_signal(closes, window):
    """H-751: Z-score of price relative to rolling mean."""
    result = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        ma = closes[col].rolling(window).mean()
        std = closes[col].rolling(window).std()
        result[col] = (closes[col] - ma) / std.replace(0, np.nan)
    return result


def sector_rotation_signal(closes, window):
    """H-752: Asset return relative to its sector average."""
    returns = closes.pct_change(window)
    sectors = {"L1": LAYER1, "L2": LAYER2, "MEME": MEME}
    result = pd.DataFrame(index=closes.index, columns=closes.columns)
    for sector_name, members in sectors.items():
        valid = [m for m in members if m in returns.columns]
        if len(valid) < 2:
            continue
        sector_avg = returns[valid].mean(axis=1)
        for col in valid:
            result[col] = returns[col] - sector_avg
    return result


def correlation_concentration_signal(closes, window):
    """H-753: Average absolute correlation with all other assets."""
    returns = closes.pct_change()
    result = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        avg_abs_corr = pd.Series(0.0, index=closes.index)
        cnt = 0
        for other in closes.columns:
            if other == col:
                continue
            c = returns[col].rolling(window).corr(returns[other]).abs()
            avg_abs_corr += c.fillna(0)
            cnt += 1
        if cnt > 0:
            result[col] = avg_abs_corr / cnt
    return result


def lead_lag_signal(closes, window):
    """H-754: Correlation of asset(t-1) with BTC(t) — who leads BTC."""
    returns = closes.pct_change()
    btc_ret = returns["BTC/USDT"]
    result = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        if col == "BTC/USDT":
            continue
        lagged = returns[col].shift(1)
        lead_corr = lagged.rolling(window).corr(btc_ret)
        result[col] = lead_corr
    return result


def cross_corr_momentum_signal(closes, short_window, long_window):
    """H-755: Momentum of correlation with BTC — rising vs falling."""
    returns = closes.pct_change()
    btc_ret = returns["BTC/USDT"]
    result = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in closes.columns:
        if col == "BTC/USDT":
            continue
        corr_short = returns[col].rolling(short_window).corr(btc_ret)
        corr_long = returns[col].rolling(long_window).corr(btc_ret)
        result[col] = corr_short - corr_long
    return result


# ============================================================
# MAIN
# ============================================================

def run_hypothesis(name, signal_df, closes, param_grid, direction):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    best_sharpe = -999
    best_params = None
    best_pnl = None

    for lookback, rebal, n_ls in param_grid:
        pnl = xs_backtest(closes, signal_df, lookback, rebal, n_ls, direction)
        sh = compute_sharpe(pnl)
        if sh > best_sharpe:
            best_sharpe = sh
            best_params = (lookback, rebal, n_ls)
            best_pnl = pnl

    metrics = compute_metrics(best_pnl)
    print(f"  Best IS: Sharpe {metrics['sharpe']}, Ret {metrics['annual_ret']}%, DD {metrics['max_dd']}%")
    print(f"  Params: lookback={best_params[0]}, rebal={best_params[1]}, n_ls={best_params[2]}")

    if metrics['sharpe'] < 0.5:
        print(f"  REJECTED — IS Sharpe {metrics['sharpe']} < 0.5")
        return {"name": name, "status": "REJECTED", "reason": f"IS Sharpe {metrics['sharpe']}", **metrics}

    pos = sum(1 for lb, rb, nls in param_grid
              if compute_sharpe(xs_backtest(closes, signal_df, lb, rb, nls, direction)) > 0)
    total = len(param_grid)
    robust_pct = pos / total * 100
    print(f"  Param robust: {pos}/{total} ({robust_pct:.0f}%)")

    if robust_pct < 60:
        print(f"  REJECTED — param robust {robust_pct:.0f}% < 60%")
        return {"name": name, "status": "REJECTED", "reason": f"param robust {robust_pct:.0f}%", **metrics}

    wf = walk_forward(closes, signal_df, best_params[0], best_params[1], best_params[2], direction)
    wf_pass = sum(1 for s in wf if s > 0)
    wf_mean = np.mean(wf) if wf else 0
    print(f"  WF: {wf_pass}/{len(wf)} positive, mean {wf_mean:.3f}")
    print(f"  WF folds: {[round(s,2) for s in wf]}")

    if len(wf) >= 4 and wf_pass < len(wf) * 0.6:
        print(f"  REJECTED — WF {wf_pass}/{len(wf)}")
        return {"name": name, "status": "REJECTED", "reason": f"WF {wf_pass}/{len(wf)}", **metrics,
                "wf": wf, "robust_pct": robust_pct}

    sh1, sh2, p_val = split_half_test(best_pnl)
    print(f"  SH: {sh1:.3f} / {sh2:.3f}, p={p_val:.4f}")

    if p_val > 0.10:
        print(f"  REJECTED — SH p-value {p_val:.4f} > 0.10")
        return {"name": name, "status": "REJECTED", "reason": f"SH p={p_val:.4f}", **metrics,
                "wf": wf, "robust_pct": robust_pct, "sh": (sh1, sh2, p_val)}

    corr = h012_correlation(closes, signal_df, best_params[0], best_params[1], best_params[2], direction)
    print(f"  H-012 corr: {corr}")

    status = "CONFIRMED" if abs(corr) < 0.7 else "CONFIRMED_REDUNDANT"
    print(f"  → {status}")

    return {"name": name, "status": status, **metrics, "params": best_params,
            "wf": wf, "wf_pass": f"{wf_pass}/{len(wf)}", "wf_mean": round(wf_mean, 3),
            "robust_pct": robust_pct, "sh": (round(sh1, 3), round(sh2, 3), round(p_val, 4)),
            "h012_corr": corr, "direction": direction, "n_days": len(best_pnl)}


if __name__ == "__main__":
    print("Loading data...")
    closes, volumes = load_data()
    print(f"  {len(closes)} days, {len(closes.columns)} assets")

    results = []

    # H-748: Correlation Breakaway
    print("\nComputing H-748 correlation breakaway signal...")
    sig = correlation_breakaway_signal(closes, 30)
    r = run_hypothesis("H-748: Correlation Breakaway",
                       sig, closes,
                       [(30, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "low_long")  # decorrelating assets have momentum (short correlated)
    results.append(r)

    # H-749: Pairwise Correlation Change
    print("\nComputing H-749 pairwise corr change signal...")
    sig = pairwise_corr_change_signal(closes, 30)
    r = run_hypothesis("H-749: Pairwise Corr Change",
                       sig, closes,
                       [(30, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "low_long")
    results.append(r)

    # H-750: Relative Strength RSI
    print("\nComputing H-750 relative strength RSI signal...")
    sig = relative_strength_rsi_signal(closes, 14)
    r = run_hypothesis("H-750: Relative Strength RSI",
                       sig, closes,
                       [(14, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "high_long")  # high RSI = strong relative, keep going
    results.append(r)

    # Also try low_long (mean revert)
    r2 = run_hypothesis("H-750b: Relative Strength RSI (contrarian)",
                        sig, closes,
                        [(14, r, n) for r in [3, 5, 7] for n in [3, 4]],
                        "low_long")
    if r2['sharpe'] > r['sharpe']:
        results[-1] = r2

    # H-751: Mean Distance (z-score)
    print("\nComputing H-751 mean distance signal...")
    sig = mean_distance_signal(closes, 20)
    r = run_hypothesis("H-751: Mean Distance (z-score contrarian)",
                       sig, closes,
                       [(20, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "low_long")  # short extended, long compressed
    results.append(r)

    # H-752: Sector Rotation
    print("\nComputing H-752 sector rotation signal...")
    sig = sector_rotation_signal(closes, 20)
    r = run_hypothesis("H-752: Sector Rotation",
                       sig, closes,
                       [(20, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "high_long")  # long outperformers within sector
    results.append(r)

    # H-753: Correlation Concentration
    print("\nComputing H-753 correlation concentration signal...")
    sig = correlation_concentration_signal(closes, 30)
    r = run_hypothesis("H-753: Correlation Concentration",
                       sig, closes,
                       [(30, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "low_long")  # long decorrelated, short concentrated
    results.append(r)

    # H-754: Lead-Lag
    print("\nComputing H-754 lead-lag signal...")
    sig = lead_lag_signal(closes, 30)
    r = run_hypothesis("H-754: Lead-Lag",
                       sig, closes,
                       [(30, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "high_long")  # long leaders
    results.append(r)

    # H-755: Cross-Correlation Momentum
    print("\nComputing H-755 cross-correlation momentum signal...")
    sig = cross_corr_momentum_signal(closes, 10, 30)
    r = run_hypothesis("H-755: Cross-Corr Momentum",
                       sig, closes,
                       [(30, r, n) for r in [3, 5, 7] for n in [3, 4]],
                       "high_long")  # rising correlation with BTC = momentum alignment
    results.append(r)

    # Summary
    print("\n" + "=" * 60)
    print("  BATCH SUMMARY: H-748 to H-755")
    print("=" * 60)
    for r in results:
        status = r['status']
        sharpe = r.get('sharpe', 0)
        extra = ""
        if status.startswith("CONFIRMED"):
            extra = f" | WF {r.get('wf_pass', '?')} | corr {r.get('h012_corr', '?')} | robust {r.get('robust_pct', '?')}%"
        print(f"  {r['name']}: {status} (IS Sharpe {sharpe}){extra}")
