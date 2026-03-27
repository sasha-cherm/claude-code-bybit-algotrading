"""
H-102: Volume Stability Factor (Cross-Sectional)

Rank assets by how stable/consistent their trading volume is over a window.
- Compute coefficient of variation (CV = std/mean) of daily dollar volume
- Long lowest CV (most stable volume = institutional, consistent interest)
- Short highest CV (most unstable/bursty volume = retail, hype-driven)
- Dollar-neutral: equal $ on long side and short side

Validation: full param scan, 70/30 train/test, split-half, walk-forward,
correlation with H-012 momentum and H-031 size.
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

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
LOOKBACKS = [20, 30, 40, 60]       # CV lookback window
REBAL_FREQS = [3, 5, 7, 10]       # rebalance every N days
N_LONGS = [3, 4, 5]               # top/bottom N

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


def volume_stability(closes, volumes, lookback):
    """
    Compute rolling coefficient of variation of dollar volume.
    Lower CV = more stable volume (long), Higher CV = more bursty (short).
    We NEGATE so run_xs_factor longs the highest rank (= lowest CV = most stable).
    """
    dollar_vol = closes * volumes
    rolling_mean = dollar_vol.rolling(lookback, min_periods=lookback).mean()
    rolling_std = dollar_vol.rolling(lookback, min_periods=lookback).std()
    cv = rolling_std / rolling_mean
    cv = cv.replace([np.inf, -np.inf], np.nan)
    return -cv  # negate: long most stable (lowest CV), short most bursty


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


def run_full_scan(closes, volumes):
    print("\n" + "=" * 70)
    print("H-102: VOLUME STABILITY FACTOR -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    results = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking = volume_stability(closes, volumes, lookback)
        warmup = lookback + 5
        res = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup)
        tag = f"LB{lookback}_R{rebal}_N{n_long}"
        results.append({
            "tag": tag, "lookback": lookback, "rebal": rebal, "n_long": n_long,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "win_rate": res["win_rate"],
        })

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"\n  Total combos: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}, Median: {df['sharpe'].median():.3f}")
    print(f"  Best: {df['sharpe'].max():.3f}, Worst: {df['sharpe'].min():.3f}")

    print("\n  Top 10:")
    for _, row in df.sort_values("sharpe", ascending=False).head(10).iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    return df


def run_train_test_split(closes, volumes, split_ratio=0.7):
    n = len(closes)
    split_idx = int(n * split_ratio)
    train_c = closes.iloc[:split_idx]
    train_v = volumes.iloc[:split_idx]
    test_c = closes.iloc[split_idx:]
    test_v = volumes.iloc[split_idx:]

    print(f"\n  70/30 Train/Test")
    print(f"  Train: {train_c.index[0].date()} to {train_c.index[-1].date()} ({len(train_c)} days)")
    print(f"  Test:  {test_c.index[0].date()} to {test_c.index[-1].date()} ({len(test_c)} days)")

    best_sharpe = -999
    best_params = None
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking = volume_stability(train_c, train_v, lookback)
        warmup = lookback + 5
        res = run_xs_factor(train_c, ranking, rebal, n_long, warmup=warmup)
        if res["sharpe"] > best_sharpe:
            best_sharpe = res["sharpe"]
            best_params = (lookback, rebal, n_long)

    lb, rb, nl = best_params
    print(f"  Train best: LB{lb}_R{rb}_N{nl} (Sharpe {best_sharpe:.3f})")

    test_ranking = volume_stability(test_c, test_v, lb)
    res_test = run_xs_factor(test_c, test_ranking, rb, nl, warmup=lb+5)
    print(f"  Test: Sharpe {res_test['sharpe']:.3f}, Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}")

    return {
        "train_best_params": f"LB{lb}_R{rb}_N{nl}", "train_sharpe": best_sharpe,
        "test_sharpe": res_test["sharpe"], "test_annual_ret": res_test["annual_ret"],
        "test_max_dd": res_test["max_dd"],
    }


def run_split_half(closes, volumes):
    n = len(closes)
    mid = n // 2
    h1c, h1v = closes.iloc[:mid], volumes.iloc[:mid]
    h2c, h2v = closes.iloc[mid:], volumes.iloc[mid:]

    print(f"\n  Split-Half Validation")
    print(f"  Half 1: {h1c.index[0].date()} to {h1c.index[-1].date()} ({len(h1c)} days)")
    print(f"  Half 2: {h2c.index[0].date()} to {h2c.index[-1].date()} ({len(h2c)} days)")

    r1_list, r2_list = [], []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        warmup = lookback + 5
        res1 = run_xs_factor(h1c, volume_stability(h1c, h1v, lookback), rebal, n_long, warmup=warmup)
        res2 = run_xs_factor(h2c, volume_stability(h2c, h2v, lookback), rebal, n_long, warmup=warmup)
        r1_list.append(res1["sharpe"])
        r2_list.append(res2["sharpe"])

    h1 = np.array(r1_list)
    h2 = np.array(r2_list)
    corr = np.corrcoef(h1, h2)[0, 1]
    both_pos = ((h1 > 0) & (h2 > 0)).sum()

    print(f"  Corr: {corr:.3f}, Both positive: {both_pos}/{len(h1)} ({both_pos/len(h1):.0%})")
    print(f"  H1 mean: {h1.mean():.3f}, H2 mean: {h2.mean():.3f}")

    return {
        "sharpe_correlation": round(float(corr), 3),
        "half1_mean_sharpe": round(float(h1.mean()), 3),
        "half2_mean_sharpe": round(float(h2.mean()), 3),
    }


def run_walk_forward_param_selection(closes, volumes):
    print(f"\n  Walk-Forward with Parameter Selection")
    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end = n - fold * WF_STEP
        test_start = test_end - WF_TEST
        train_start = test_start - WF_TRAIN
        if train_start < 0:
            break

        train_c = closes.iloc[train_start:test_start]
        train_v = volumes.iloc[train_start:test_start]
        test_c = closes.iloc[test_start:test_end]
        test_v = volumes.iloc[test_start:test_end]
        if len(test_c) < 30 or len(train_c) < 100:
            break

        best_sharpe = -999
        best_params = None
        for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
            ranking = volume_stability(train_c, train_v, lookback)
            warmup = lookback + 5
            if warmup >= len(train_c) - 30:
                continue
            res = run_xs_factor(train_c, ranking, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_params = (lookback, rebal, n_long)

        if best_params is None:
            break

        lb, rb, nl = best_params
        test_ranking = volume_stability(test_c, test_v, lb)
        warmup = min(lb + 5, len(test_c) // 2)
        res = run_xs_factor(test_c, test_ranking, rb, nl, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "params": f"LB{lb}_R{rb}_N{nl}",
            "train_sharpe": round(best_sharpe, 3),
            "oos_sharpe": res["sharpe"], "oos_annual_ret": res["annual_ret"],
        })
        print(f"    Fold {fold+1}: LB{lb}_R{rb}_N{nl} IS={best_sharpe:.3f}, OOS={res['sharpe']:.3f}")

    if not fold_results:
        return None
    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe"] > 0).sum()
    print(f"    Positive: {pos}/{len(df)}, Mean OOS: {df['oos_sharpe'].mean():.3f}")
    return df


def compute_correlations(closes, volumes, lookback, rebal, n_long):
    """Correlation with H-012 momentum and H-031 size."""
    print(f"\n  Correlations with existing factors")

    ranking = volume_stability(closes, volumes, lookback)
    res_f = run_xs_factor(closes, ranking, rebal, n_long, warmup=lookback+5)

    # H-012: momentum (60d return)
    mom_ranking = closes.pct_change(60)
    res_mom = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)

    # H-031: size (avg dollar volume, long large)
    dollar_vol = closes * pd.DataFrame({sym: pd.read_parquet(ROOT / "data" / f"{sym.replace('/', '_')}_1d.parquet")["volume"]
                                        for sym in closes.columns}).reindex(closes.index).ffill().fillna(0)
    size_ranking = dollar_vol.rolling(30, min_periods=30).mean()
    res_size = run_xs_factor(closes, size_ranking, 5, 5, warmup=35)

    rets_f = res_f["equity"].pct_change().dropna()
    rets_mom = res_mom["equity"].pct_change().dropna()
    rets_size = res_size["equity"].pct_change().dropna()

    common_mom = rets_f.index.intersection(rets_mom.index)
    common_size = rets_f.index.intersection(rets_size.index)

    corr_mom = rets_f.loc[common_mom].corr(rets_mom.loc[common_mom]) if len(common_mom) > 50 else 0
    corr_size = rets_f.loc[common_size].corr(rets_size.loc[common_size]) if len(common_size) > 50 else 0

    print(f"    vs H-012 (momentum): {corr_mom:.3f}")
    print(f"    vs H-031 (size): {corr_size:.3f}")
    return round(corr_mom, 3), round(corr_size, 3)


if __name__ == "__main__":
    print("H-102: Volume Stability Factor")
    print("=" * 70)

    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")
    if len(daily) < 10:
        sys.exit(1)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().fillna(0)
    print(f"\nAligned: {len(closes.columns)} assets, {len(closes)} days")

    # 1. Full scan
    scan = run_full_scan(closes, volumes)
    best = scan.nlargest(1, "sharpe").iloc[0]
    best_lb = int(best["lookback"])
    best_rb = int(best["rebal"])
    best_n = int(best["n_long"])

    # 2. Train/Test
    tt = run_train_test_split(closes, volumes)

    # 3. Split-Half
    sh = run_split_half(closes, volumes)

    # 4. WF param selection
    wf_sel = run_walk_forward_param_selection(closes, volumes)

    # 5. Correlations
    corr_mom, corr_size = compute_correlations(closes, volumes, best_lb, best_rb, best_n)

    # Summary
    pos_pct = (scan["sharpe"] > 0).mean()
    print("\n" + "=" * 70)
    print("SUMMARY: H-102 Volume Stability Factor")
    print("=" * 70)
    print(f"  Combos: {len(scan)}, Positive: {(scan['sharpe']>0).sum()}/{len(scan)} ({pos_pct:.0%})")
    print(f"  Mean Sharpe: {scan['sharpe'].mean():.3f}, Best: {best['sharpe']:.3f}")
    print(f"  Best: LB{best_lb}_R{best_rb}_N{best_n}")
    print(f"  Train/Test: IS {tt['train_sharpe']:.3f} -> OOS {tt['test_sharpe']:.3f}")
    print(f"  Split-half: H1={sh['half1_mean_sharpe']:.3f}, H2={sh['half2_mean_sharpe']:.3f}, corr={sh['sharpe_correlation']:.3f}")
    if wf_sel is not None:
        print(f"  WF selected: {(wf_sel['oos_sharpe']>0).sum()}/{len(wf_sel)} positive, mean {wf_sel['oos_sharpe'].mean():.3f}")
    print(f"  Corr with H-012: {corr_mom:.3f}, with H-031: {corr_size:.3f}")
