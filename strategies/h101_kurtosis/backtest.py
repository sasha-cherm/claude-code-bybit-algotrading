"""
H-101: Return Kurtosis Factor (Cross-Sectional)

Rank assets by excess kurtosis of daily returns over a rolling window.
- Long lowest kurtosis (thin-tailed, well-behaved price action)
- Short highest kurtosis (fat-tailed, crash-prone)
- Hypothesis: low-kurtosis assets deliver better risk-adjusted returns

Validation: full param scan, 70/30 train/test, split-half, walk-forward,
correlation with H-012 momentum.
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd
from scipy.stats import kurtosis as scipy_kurtosis

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.0006
INITIAL_CAPITAL = 10_000.0

# Parameter grid
LOOKBACKS = [20, 30, 40, 60]       # kurtosis lookback window
REBAL_FREQS = [3, 5, 7, 10]       # rebalance every N days
N_LONGS = [3, 4, 5]               # top/bottom N

# Walk-forward config
WF_FOLDS = 6
WF_TRAIN = 300
WF_TEST = 90
WF_STEP = 90


def load_daily_data():
    data_dir = ROOT / "data"
    daily = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if len(df) >= 200:
                daily[sym] = df
                print(f"  {sym}: {len(df)} daily bars "
                      f"({df.index[0].date()} to {df.index[-1].date()})")
            else:
                print(f"  {sym}: only {len(df)} bars, skipping")
        else:
            print(f"  {sym}: no data found")
    return daily


def compute_metrics(equity_series):
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "win_rate": 0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "win_rate": round(n_pos / n_total, 4) if n_total > 0 else 0,
    }


def rolling_kurtosis(closes, lookback):
    """
    Compute rolling excess kurtosis of daily returns using fast numpy.
    LOWER kurtosis = long (thin tails), HIGHER kurtosis = short (fat tails).
    We NEGATE the kurtosis so that run_xs_factor longs the highest rank (= lowest kurtosis).
    """
    rets = closes.pct_change()
    # Fast rolling kurtosis using numpy — avoids slow scipy.apply()
    result = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for sym in closes.columns:
        r = rets[sym].values
        n = len(r)
        kurt_vals = np.full(n, np.nan)
        for i in range(lookback, n):
            window = r[i - lookback + 1:i + 1]
            valid = window[~np.isnan(window)]
            if len(valid) < 4:
                continue
            m = valid.mean()
            s = valid.std(ddof=1)
            if s < 1e-12:
                kurt_vals[i] = 0.0
                continue
            z = (valid - m) / s
            nn = len(valid)
            # Excess kurtosis (Fisher)
            kurt_vals[i] = (nn * (nn + 1) / ((nn - 1) * (nn - 2) * (nn - 3)) *
                           np.sum(z**4) -
                           3 * (nn - 1)**2 / ((nn - 2) * (nn - 3)))
        result[sym] = kurt_vals
    return -result  # negate: long lowest kurtosis, short highest


# Pre-compute and cache rankings by lookback
_kurtosis_cache = {}

def get_kurtosis_ranking(closes, lookback):
    key = (id(closes), lookback)
    if key not in _kurtosis_cache:
        _kurtosis_cache[key] = rolling_kurtosis(closes, lookback)
    return _kurtosis_cache[key]


def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  warmup=65):
    if n_short is None:
        n_short = n_long

    n = len(closes)
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count = 0

    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = ranking_series.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            ranked = valid.sort_values(ascending=False)
            longs = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * FEE_RATE

            port_ret = (new_weights * log_rets).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count += 1
            prev_weights = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"] = eq_series
    return metrics


def run_full_scan(closes):
    print("\n" + "=" * 70)
    print("H-101: RETURN KURTOSIS FACTOR -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE*10000:.0f} bps per trade")

    # Pre-compute rankings for all lookbacks
    for lb in LOOKBACKS:
        get_kurtosis_ranking(closes, lb)
        print(f"  Computed kurtosis for lookback={lb}")

    results = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking = get_kurtosis_ranking(closes, lookback)
        warmup = lookback + 5

        res = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup)
        tag = f"LB{lookback}_R{rebal}_N{n_long}"
        results.append({
            "tag": tag, "lookback": lookback, "rebal": rebal, "n_long": n_long,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "win_rate": res["win_rate"],
            "n_trades": res["n_trades"], "n_rebalances": res["n_rebalances"],
        })

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"\n  Total parameter combos: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.3f}")
    print(f"  Worst Sharpe: {df['sharpe'].min():.3f}")

    print("\n  Top 10 by Sharpe:")
    for _, row in df.sort_values("sharpe", ascending=False).head(10).iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    return df


def run_train_test_split(closes, split_ratio=0.7):
    n = len(closes)
    split_idx = int(n * split_ratio)
    train_closes = closes.iloc[:split_idx]
    test_closes = closes.iloc[split_idx:]

    print(f"\n  70/30 Train/Test Split")
    print(f"  Train: {train_closes.index[0].date()} to {train_closes.index[-1].date()} ({len(train_closes)} days)")
    print(f"  Test:  {test_closes.index[0].date()} to {test_closes.index[-1].date()} ({len(test_closes)} days)")

    best_sharpe = -999
    best_params = None
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking = get_kurtosis_ranking(train_closes, lookback)
        warmup = lookback + 5
        res = run_xs_factor(train_closes, ranking, rebal, n_long, warmup=warmup)
        if res["sharpe"] > best_sharpe:
            best_sharpe = res["sharpe"]
            best_params = (lookback, rebal, n_long)

    lookback, rebal, n_long = best_params
    print(f"  Train best: LB{lookback}_R{rebal}_N{n_long} (Sharpe {best_sharpe:.3f})")

    test_ranking = rolling_kurtosis(test_closes, lookback)
    warmup = lookback + 5
    res_test = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=warmup)
    print(f"  Test result: Sharpe {res_test['sharpe']:.3f}, "
          f"Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}")

    return {
        "train_best_params": f"LB{lookback}_R{rebal}_N{n_long}",
        "train_sharpe": best_sharpe,
        "test_sharpe": res_test["sharpe"],
        "test_annual_ret": res_test["annual_ret"],
        "test_max_dd": res_test["max_dd"],
        "test_n_days": len(test_closes),
    }


def run_split_half(closes):
    n = len(closes)
    mid = n // 2
    half1 = closes.iloc[:mid]
    half2 = closes.iloc[mid:]

    print(f"\n  Split-Half Validation")
    print(f"  Half 1: {half1.index[0].date()} to {half1.index[-1].date()} ({len(half1)} days)")
    print(f"  Half 2: {half2.index[0].date()} to {half2.index[-1].date()} ({len(half2)} days)")

    results_h1 = []
    results_h2 = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        warmup = lookback + 5
        r1 = rolling_kurtosis(half1, lookback)
        res1 = run_xs_factor(half1, r1, rebal, n_long, warmup=warmup)
        r2 = rolling_kurtosis(half2, lookback)
        res2 = run_xs_factor(half2, r2, rebal, n_long, warmup=warmup)
        results_h1.append(res1["sharpe"])
        results_h2.append(res2["sharpe"])

    h1_arr = np.array(results_h1)
    h2_arr = np.array(results_h2)
    corr = np.corrcoef(h1_arr, h2_arr)[0, 1]
    both_positive = ((h1_arr > 0) & (h2_arr > 0)).sum()

    print(f"  Sharpe rank correlation between halves: {corr:.3f}")
    print(f"  Positive in both halves: {both_positive}/{len(h1_arr)} ({both_positive/len(h1_arr):.0%})")
    print(f"  Half 1 mean Sharpe: {h1_arr.mean():.3f}")
    print(f"  Half 2 mean Sharpe: {h2_arr.mean():.3f}")

    return {
        "sharpe_correlation": round(float(corr), 3),
        "both_positive_pct": round(both_positive / len(h1_arr), 3),
        "half1_mean_sharpe": round(float(h1_arr.mean()), 3),
        "half2_mean_sharpe": round(float(h2_arr.mean()), 3),
    }


def run_walk_forward(closes, lookback, rebal, n_long):
    print(f"\n  Walk-Forward (Fixed Params): LB{lookback}_R{rebal}_N{n_long}")
    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN
        if train_start_idx < 0 or test_start_idx < 0:
            break

        test_closes = closes.iloc[test_start_idx:test_end_idx]
        if len(test_closes) < 30:
            break

        test_ranking = get_kurtosis_ranking(test_closes, lookback)
        warmup = min(lookback + 5, len(test_closes) // 2)
        res = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        })
        print(f"    Fold {fold+1}: {test_closes.index[0].date()} -> {test_closes.index[-1].date()}, "
              f"Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}")

    if not fold_results:
        return None
    df = pd.DataFrame(fold_results)
    pos = (df["sharpe"] > 0).sum()
    print(f"    Positive folds: {pos}/{len(df)}, Mean OOS Sharpe: {df['sharpe'].mean():.3f}")
    return df


def run_walk_forward_param_selection(closes):
    print(f"\n  Walk-Forward with In-Sample Parameter Selection")
    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN
        if train_start_idx < 0 or test_start_idx < 0:
            break

        train_closes = closes.iloc[train_start_idx:test_start_idx]
        test_closes = closes.iloc[test_start_idx:test_end_idx]
        if len(test_closes) < 30 or len(train_closes) < 100:
            break

        best_sharpe = -999
        best_params = None
        for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
            ranking = get_kurtosis_ranking(train_closes, lookback)
            warmup = lookback + 5
            if warmup >= len(train_closes) - 30:
                continue
            res = run_xs_factor(train_closes, ranking, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_params = (lookback, rebal, n_long)

        if best_params is None:
            break

        lookback, rebal, n_long = best_params
        test_ranking = get_kurtosis_ranking(test_closes, lookback)
        warmup = min(lookback + 5, len(test_closes) // 2)
        res = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "train_params": f"LB{lookback}_R{rebal}_N{n_long}",
            "train_sharpe": round(best_sharpe, 3),
            "oos_sharpe": res["sharpe"], "oos_annual_ret": res["annual_ret"],
        })
        print(f"    Fold {fold+1}: train=LB{lookback}_R{rebal}_N{n_long} "
              f"(IS {best_sharpe:.3f}), OOS {res['sharpe']:.3f}")

    if not fold_results:
        return None
    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe"] > 0).sum()
    print(f"    Positive OOS folds: {pos}/{len(df)}, Mean OOS: {df['oos_sharpe'].mean():.3f}")
    return df


def compute_h012_correlation(closes, lookback, rebal, n_long):
    print(f"\n  Correlation with H-012 (60d Momentum)")
    ranking = rolling_kurtosis(closes, lookback)
    warmup = lookback + 5
    res_factor = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup)

    mom_ranking = closes.pct_change(60)
    res_mom = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)

    rets_f = res_factor["equity"].pct_change().dropna()
    rets_m = res_mom["equity"].pct_change().dropna()
    common = rets_f.index.intersection(rets_m.index)
    if len(common) < 50:
        print("    Insufficient overlap")
        return 0.0

    corr = rets_f.loc[common].corr(rets_m.loc[common])
    print(f"    Daily return correlation with H-012: {corr:.3f}")
    return round(corr, 3)


if __name__ == "__main__":
    print("H-101: Return Kurtosis Factor")
    print("=" * 70)

    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")
    if len(daily) < 10:
        print("ERROR: Not enough assets. Aborting.")
        sys.exit(1)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")

    # 1. Full scan
    scan = run_full_scan(closes)

    # 2. Best params
    best = scan.nlargest(1, "sharpe").iloc[0]
    best_lb = int(best["lookback"])
    best_rb = int(best["rebal"])
    best_n = int(best["n_long"])
    print(f"\n  Best: LB{best_lb}_R{best_rb}_N{best_n}, Sharpe {best['sharpe']:.3f}")

    # 3. Train/Test
    tt = run_train_test_split(closes)

    # 4. Split-Half
    sh = run_split_half(closes)

    # 5. WF fixed
    wf_fixed = run_walk_forward(closes, best_lb, best_rb, best_n)

    # 6. WF param selection
    wf_sel = run_walk_forward_param_selection(closes)

    # 7. Correlation with H-012
    h012_corr = compute_h012_correlation(closes, best_lb, best_rb, best_n)

    # 8. Summary
    pos_pct = (scan["sharpe"] > 0).mean()
    print("\n" + "=" * 70)
    print("SUMMARY: H-101 Return Kurtosis Factor")
    print("=" * 70)
    print(f"  Param combos: {len(scan)}, Positive: {(scan['sharpe']>0).sum()}/{len(scan)} ({pos_pct:.0%})")
    print(f"  Mean Sharpe: {scan['sharpe'].mean():.3f}, Best: {best['sharpe']:.3f}")
    print(f"  Best params: LB{best_lb}_R{best_rb}_N{best_n}")
    print(f"  Train/Test: IS {tt['train_sharpe']:.3f} -> OOS {tt['test_sharpe']:.3f}")
    print(f"  Split-half corr: {sh['sharpe_correlation']:.3f} (H1: {sh['half1_mean_sharpe']:.3f}, H2: {sh['half2_mean_sharpe']:.3f})")
    if wf_fixed is not None:
        print(f"  WF fixed: {(wf_fixed['sharpe']>0).sum()}/{len(wf_fixed)} positive, mean {wf_fixed['sharpe'].mean():.3f}")
    if wf_sel is not None:
        print(f"  WF selected: {(wf_sel['oos_sharpe']>0).sum()}/{len(wf_sel)} positive, mean {wf_sel['oos_sharpe'].mean():.3f}")
    print(f"  Correlation with H-012: {h012_corr:.3f}")
