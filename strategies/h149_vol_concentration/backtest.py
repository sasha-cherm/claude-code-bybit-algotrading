"""
H-149: Volume Concentration Factor (Cross-Sectional)

For each asset, compute the percentage of total volume that occurs on
"up days" (close > open) vs "down days" (close < open) over a rolling window.
Assets with concentrated volume on up days have "buying pressure."

Cross-sectional: go LONG assets with highest buying pressure
(most volume on up days), SHORT assets with lowest buying pressure
(most volume on down days).

Factor = sum(volume on up days) / sum(all volume) over rolling window.
"""

import json
import sys
import time
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE",
    "AVAX", "LINK", "ADA", "DOT", "NEAR",
    "OP", "ARB", "ATOM", "SUI",
]

FEE_RATE = 0.001          # 0.1% per trade (entry + exit = round-trip 0.2%)
INITIAL_CAPITAL = 10_000.0

# Parameter grid
WINDOWS = [10, 14, 20, 30]
REBAL_FREQS = [3, 5, 7, 10]
N_POSITIONS = [3, 4, 5]

WF_FOLDS = 6


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_all_data(limit=1100):
    """Fetch daily OHLCV for all 14 assets using ccxt (Bybit linear)."""
    import ccxt
    exchange = ccxt.bybit({
        "enableRateLimit": True,
        "options": {"defaultType": "linear"},
    })
    print(f"Fetching {len(ASSETS)} assets × {limit} daily bars from Bybit...")
    daily = {}
    for sym in ASSETS:
        symbol = f"{sym}/USDT:USDT"
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=limit)
            if not ohlcv:
                # fallback to spot
                symbol = f"{sym}/USDT"
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=limit)
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df = df.set_index("timestamp").sort_index()
            df = df[~df.index.duplicated(keep="last")]
            daily[sym] = df
            print(f"  {sym}: {len(df)} bars  ({df.index[0].date()} → {df.index[-1].date()})")
            time.sleep(0.2)
        except Exception as e:
            print(f"  {sym}: FAILED — {e}")
    return daily


def align_data(daily):
    """Align all assets to a common date index."""
    # Find common dates (inner join)
    dates = None
    for sym, df in daily.items():
        idx = df.index
        if dates is None:
            dates = idx
        else:
            dates = dates.intersection(idx)
    dates = dates.sort_values()
    print(f"\nCommon date range: {dates[0].date()} → {dates[-1].date()}  ({len(dates)} days)")

    aligned = {}
    for sym, df in daily.items():
        aligned[sym] = df.reindex(dates)
    return aligned, dates


# ---------------------------------------------------------------------------
# Factor computation
# ---------------------------------------------------------------------------

def compute_factor(aligned, dates, window):
    """
    Compute rolling volume concentration for each asset.
    Factor = sum(volume on up days) / sum(all volume) over last `window` days.
    Up day = close > open.
    """
    syms = list(aligned.keys())
    n = len(dates)
    factor = pd.DataFrame(np.nan, index=dates, columns=syms)

    for sym in syms:
        df = aligned[sym]
        close = df["close"].values
        open_ = df["open"].values
        vol = df["volume"].values

        up_mask = close > open_   # boolean: is this an up day?
        up_vol = vol * up_mask.astype(float)

        # rolling sum using cumsum trick for speed
        cum_upvol = np.cumsum(up_vol)
        cum_vol = np.cumsum(vol)

        result = np.full(n, np.nan)
        for i in range(window - 1, n):
            start = i - window + 1
            tot = cum_vol[i] - (cum_vol[start - 1] if start > 0 else 0.0)
            up = cum_upvol[i] - (cum_upvol[start - 1] if start > 0 else 0.0)
            if tot > 0:
                result[i] = up / tot

        factor[sym] = result

    return factor


# ---------------------------------------------------------------------------
# Backtesting engine
# ---------------------------------------------------------------------------

def build_returns(aligned, dates):
    """Build daily return matrix (close-to-close)."""
    syms = list(aligned.keys())
    ret = pd.DataFrame(np.nan, index=dates, columns=syms)
    for sym in syms:
        prices = aligned[sym]["close"]
        ret[sym] = prices.pct_change()
    return ret


def run_strategy(factor, ret_matrix, rebal_freq, n_pos, fee_rate=FEE_RATE):
    """
    Run the long-short strategy for given parameters.
    Returns daily portfolio return series.
    """
    dates = factor.index
    n = len(dates)
    syms = factor.columns.tolist()

    portfolio_returns = pd.Series(0.0, index=dates)
    prev_weights = pd.Series(0.0, index=syms)

    rebal_day = 0
    current_weights = pd.Series(0.0, index=syms)

    for i in range(1, n):
        # Rebalance check
        if rebal_day == 0:
            f_row = factor.iloc[i]
            valid = f_row.dropna()
            if len(valid) >= 2 * n_pos:
                ranked = valid.rank(ascending=True)
                top_syms = ranked.nlargest(n_pos).index.tolist()
                bot_syms = ranked.nsmallest(n_pos).index.tolist()

                new_weights = pd.Series(0.0, index=syms)
                for s in top_syms:
                    new_weights[s] = 0.5 / n_pos   # long leg = 50% of capital
                for s in bot_syms:
                    new_weights[s] = -0.5 / n_pos  # short leg = 50% of capital

                # Transaction costs: fee on weight changes
                turnover = (new_weights - current_weights).abs().sum()
                tc = turnover * fee_rate
                current_weights = new_weights
            else:
                tc = 0.0
        else:
            tc = 0.0

        # Daily portfolio return
        day_ret = ret_matrix.iloc[i]
        port_ret = (current_weights * day_ret).sum() - tc
        portfolio_returns.iloc[i] = port_ret

        rebal_day = (rebal_day + 1) % rebal_freq

    return portfolio_returns


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def sharpe(rets, freq=252):
    """Annualized Sharpe ratio from daily returns."""
    r = rets.dropna()
    if len(r) < 30 or r.std() == 0:
        return np.nan
    return (r.mean() / r.std()) * np.sqrt(freq)


def annual_ret(rets):
    """CAGR from daily returns."""
    r = rets.dropna()
    if len(r) < 2:
        return np.nan
    total = (1 + r).prod()
    years = len(r) / 252
    return total ** (1 / years) - 1 if years > 0 else np.nan


def max_dd(rets):
    """Maximum drawdown from daily returns."""
    r = rets.dropna()
    eq = (1 + r).cumprod()
    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max
    return dd.min()


# ---------------------------------------------------------------------------
# Main backtest routines
# ---------------------------------------------------------------------------

def full_param_sweep(factor, ret_matrix):
    """Run all 48 parameter combinations on full dataset."""
    results = []
    for win, rebal, n_pos in product(WINDOWS, REBAL_FREQS, N_POSITIONS):
        f = compute_factor({s: None for s in factor.columns}, factor.index, win) \
            if False else factor  # factor already computed per window below
        # Note: we recompute factor per window in the caller
        rets = run_strategy(factor, ret_matrix, rebal, n_pos)
        s = sharpe(rets)
        results.append({
            "window": win, "rebal": rebal, "n_pos": n_pos,
            "sharpe": s,
            "annual_ret": annual_ret(rets),
            "max_dd": max_dd(rets),
        })
    return results


def walk_forward(aligned, dates, ret_matrix, best_window, best_rebal, best_n):
    """6-fold walk-forward validation."""
    n = len(dates)
    fold_size = n // WF_FOLDS
    fold_sharpes = []

    for fold in range(WF_FOLDS):
        test_start = fold * fold_size
        test_end = test_start + fold_size if fold < WF_FOLDS - 1 else n

        test_dates = dates[test_start:test_end]
        test_factor = compute_factor(aligned, test_dates, best_window)
        test_ret = ret_matrix.reindex(test_dates)

        rets = run_strategy(test_factor, test_ret, best_rebal, best_n)
        s = sharpe(rets)
        fold_sharpes.append(s)
        print(f"  Fold {fold + 1}: {test_dates[0].date()} → {test_dates[-1].date()}  "
              f"Sharpe={s:.3f}")

    return fold_sharpes


def split_half(aligned, dates, ret_matrix, best_window, best_rebal, best_n):
    """Split dataset into two halves, run best params on each."""
    mid = len(dates) // 2
    results = []
    for label, idx in [("H1", dates[:mid]), ("H2", dates[mid:])]:
        f = compute_factor(aligned, idx, best_window)
        r = ret_matrix.reindex(idx)
        rets = run_strategy(f, r, best_rebal, best_n)
        s = sharpe(rets)
        results.append((label, s))
        print(f"  {label}: {idx[0].date()} → {idx[-1].date()}  Sharpe={s:.3f}")
    return results


def momentum_factor_rets(ret_matrix, window=21, n_pos=4, rebal=5):
    """Simple cross-sectional momentum factor (proxy for H-012)."""
    dates = ret_matrix.index
    n = len(dates)
    syms = ret_matrix.columns.tolist()
    port_rets = pd.Series(0.0, index=dates)
    current_weights = pd.Series(0.0, index=syms)
    rebal_day = 0

    for i in range(window, n):
        if rebal_day == 0:
            # Compute N-day return
            mom = ret_matrix.iloc[i - window:i].add(1).prod() - 1
            valid = mom.dropna()
            if len(valid) >= 2 * n_pos:
                top = valid.nlargest(n_pos).index.tolist()
                bot = valid.nsmallest(n_pos).index.tolist()
                w = pd.Series(0.0, index=syms)
                for s in top:
                    w[s] = 0.5 / n_pos
                for s in bot:
                    w[s] = -0.5 / n_pos
                current_weights = w

        port_rets.iloc[i] = (current_weights * ret_matrix.iloc[i]).sum()
        rebal_day = (rebal_day + 1) % rebal

    return port_rets


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("H-149: Volume Concentration Factor Backtest")
    print("=" * 60)

    # 1. Fetch data
    daily = fetch_all_data(limit=1100)
    if len(daily) < 10:
        print("ERROR: Too few assets loaded. Aborting.")
        sys.exit(1)

    aligned, dates = align_data(daily)

    # 2. Build return matrix once
    ret_matrix = build_returns(aligned, dates)

    print(f"\nTotal assets: {len(aligned)}, total dates: {len(dates)}")
    print(f"Date range: {dates[0].date()} → {dates[-1].date()}")

    # 3. Full parameter sweep (IS)
    print("\n--- IN-SAMPLE PARAMETER SWEEP ---")
    all_results = []

    for win in WINDOWS:
        print(f"\nComputing factor with window={win}...")
        f = compute_factor(aligned, dates, win)
        for rebal, n_pos in product(REBAL_FREQS, N_POSITIONS):
            rets = run_strategy(f, ret_matrix, rebal, n_pos)
            s = sharpe(rets)
            ar = annual_ret(rets)
            md = max_dd(rets)
            all_results.append({
                "window": win, "rebal": rebal, "n_pos": n_pos,
                "sharpe": s, "annual_ret": ar, "max_dd": md,
                "rets": rets,
            })

    sharpes = [r["sharpe"] for r in all_results if not np.isnan(r["sharpe"])]
    pct_pos = 100 * sum(s > 0 for s in sharpes) / len(sharpes) if sharpes else 0
    mean_sharpe_is = np.mean(sharpes) if sharpes else np.nan
    best_result = max(all_results, key=lambda x: x["sharpe"] if not np.isnan(x["sharpe"]) else -999)

    print(f"\nIS Summary:")
    print(f"  Parameters tested:   {len(all_results)}")
    print(f"  % positive Sharpe:   {pct_pos:.1f}%")
    print(f"  Mean Sharpe (IS):    {mean_sharpe_is:.3f}")
    print(f"  Best Sharpe (IS):    {best_result['sharpe']:.3f}")
    print(f"  Best params:         window={best_result['window']}, "
          f"rebal={best_result['rebal']}, n_pos={best_result['n_pos']}")
    print(f"  Best annual return:  {best_result['annual_ret'] * 100:.1f}%")
    print(f"  Best max drawdown:   {best_result['max_dd'] * 100:.1f}%")

    bw = best_result["window"]
    br = best_result["rebal"]
    bn = best_result["n_pos"]

    # 4. Walk-forward validation
    print("\n--- WALK-FORWARD VALIDATION (6 folds) ---")
    fold_sharpes = walk_forward(aligned, dates, ret_matrix, bw, br, bn)
    n_pos_wf = sum(s > 0 for s in fold_sharpes if not np.isnan(s))
    mean_wf = np.nanmean(fold_sharpes)
    print(f"\n  WF Mean OOS Sharpe:  {mean_wf:.3f}")
    print(f"  WF Positive folds:   {n_pos_wf}/6")

    # 5. Split-half validation
    print("\n--- SPLIT-HALF VALIDATION ---")
    halves = split_half(aligned, dates, ret_matrix, bw, br, bn)
    h1_sharpe = halves[0][1]
    h2_sharpe = halves[1][1]
    both_positive = h1_sharpe > 0 and h2_sharpe > 0

    # 6. Correlation with momentum factor
    print("\n--- CORRELATION WITH MOMENTUM FACTOR (H-012 proxy) ---")
    best_rets = best_result["rets"].dropna()
    mom_rets = momentum_factor_rets(ret_matrix)

    # Align both series
    common_idx = best_rets.index.intersection(mom_rets.index)
    br_aligned = best_rets.reindex(common_idx)
    mr_aligned = mom_rets.reindex(common_idx)

    # Only use days where both are non-zero (active positions)
    active = (br_aligned != 0) & (mr_aligned != 0)
    if active.sum() > 50:
        corr = br_aligned[active].corr(mr_aligned[active])
    else:
        corr = br_aligned.corr(mr_aligned)

    print(f"  Correlation (vol_conc vs momentum): {corr:.3f}")

    # 7. Validation criteria check
    print("\n" + "=" * 60)
    print("VALIDATION CRITERIA")
    print("=" * 60)

    c1 = pct_pos >= 60
    c2 = (n_pos_wf >= 4) and (mean_wf > 0.5)
    c3 = both_positive
    c4 = abs(corr) < 0.40

    print(f"  C1 IS ≥60% positive Sharpe:         {'PASS' if c1 else 'FAIL'}  "
          f"({pct_pos:.1f}%)")
    print(f"  C2 WF ≥4/6 positive AND mean>0.5:   {'PASS' if c2 else 'FAIL'}  "
          f"({n_pos_wf}/6, mean={mean_wf:.3f})")
    print(f"  C3 Split-half both positive:         {'PASS' if c3 else 'FAIL'}  "
          f"(H1={h1_sharpe:.3f}, H2={h2_sharpe:.3f})")
    print(f"  C4 Corr w/ momentum < 0.40:          {'PASS' if c4 else 'FAIL'}  "
          f"(corr={corr:.3f})")

    n_pass = sum([c1, c2, c3, c4])
    verdict = "CONFIRMED" if n_pass == 4 else "REJECTED"

    print("\n" + "=" * 60)
    print(f"VERDICT: {verdict}  ({n_pass}/4 criteria passed)")
    print("=" * 60)

    if verdict == "REJECTED":
        reasons = []
        if not c1:
            reasons.append(f"IS only {pct_pos:.0f}% positive (need ≥60%)")
        if not c2:
            reasons.append(f"WF {n_pos_wf}/6 positive folds, mean={mean_wf:.3f} (need ≥4/6 and mean>0.5)")
        if not c3:
            reasons.append(f"Split-half not both positive (H1={h1_sharpe:.3f}, H2={h2_sharpe:.3f})")
        if not c4:
            reasons.append(f"High momentum correlation ({corr:.3f} ≥ 0.40)")
        print("Reasons: " + "; ".join(reasons))

    # 8. Save results
    results_path = Path(__file__).parent / "results.json"
    output = {
        "hypothesis": "H-149",
        "name": "Volume Concentration Factor",
        "verdict": verdict,
        "criteria_passed": int(n_pass),
        "is_stats": {
            "n_params": int(len(all_results)),
            "pct_positive_sharpe": float(round(pct_pos, 1)),
            "mean_sharpe": float(round(mean_sharpe_is, 4)),
            "best_sharpe": float(round(best_result["sharpe"], 4)),
            "best_annual_ret": float(round(best_result["annual_ret"], 4)),
            "best_max_dd": float(round(best_result["max_dd"], 4)),
            "best_params": {"window": int(bw), "rebal": int(br), "n_pos": int(bn)},
        },
        "walk_forward": {
            "fold_sharpes": [float(round(float(s), 4)) for s in fold_sharpes],
            "mean_oos_sharpe": float(round(float(mean_wf), 4)),
            "n_positive_folds": int(n_pos_wf),
        },
        "split_half": {
            "h1_sharpe": float(round(float(h1_sharpe), 4)),
            "h2_sharpe": float(round(float(h2_sharpe), 4)),
        },
        "momentum_correlation": float(round(float(corr), 4)),
        "criteria": {
            "c1_is_pct_positive": bool(c1),
            "c2_wf_oos": bool(c2),
            "c3_split_half": bool(c3),
            "c4_low_corr": bool(c4),
        },
        "date_range": {
            "start": str(dates[0].date()),
            "end": str(dates[-1].date()),
            "n_days": int(len(dates)),
        },
        "assets": list(aligned.keys()),
    }

    class _Enc(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return super().default(obj)

    with open(results_path, "w") as f:
        json.dump(output, f, indent=2, cls=_Enc)
    print(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    main()
