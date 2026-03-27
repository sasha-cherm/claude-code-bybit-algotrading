"""
H-103: Price-Volume Correlation Factor (Cross-Sectional)

Rank assets by the correlation between daily price returns and daily volume changes.
- Positive corr = price up accompanied by volume up (conviction buying)
- Negative corr = price moves on declining volume (weak moves)
- Long highest price-volume correlation (strongest conviction)
- Short lowest price-volume correlation (weakest conviction)
- Dollar-neutral

Validation: full param scan, 70/30 train/test, split-half, walk-forward,
correlation with H-012 momentum and H-021 volume momentum.
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
LOOKBACKS = [20, 30, 40, 60]       # correlation lookback window
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


def price_volume_correlation(closes, volumes, lookback):
    """
    Compute rolling correlation between daily returns and daily volume changes.
    Higher correlation = conviction (price and volume move together).
    """
    rets = closes.pct_change()
    vol_changes = volumes.pct_change()
    # Replace inf in volume changes (e.g., from 0 volume days)
    vol_changes = vol_changes.replace([np.inf, -np.inf], np.nan)

    # Rolling correlation between returns and volume changes
    corr = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for sym in closes.columns:
        r = rets[sym]
        v = vol_changes[sym]
        corr[sym] = r.rolling(lookback, min_periods=lookback).corr(v)

    return corr


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
    print("H-103: PRICE-VOLUME CORRELATION FACTOR -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    results = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking = price_volume_correlation(closes, volumes, lookback)
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

    # Also try CONTRARIAN direction (short high PV corr, long low PV corr)
    print("\n  --- Contrarian direction (short conviction, long doubt) ---")
    results_c = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking = -price_volume_correlation(closes, volumes, lookback)  # negate
        warmup = lookback + 5
        res = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup)
        tag = f"C_LB{lookback}_R{rebal}_N{n_long}"
        results_c.append({
            "tag": tag, "lookback": lookback, "rebal": rebal, "n_long": n_long,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "win_rate": res["win_rate"],
        })
    df_c = pd.DataFrame(results_c)
    pos_c = df_c[df_c["sharpe"] > 0]
    print(f"  Contrarian Positive: {len(pos_c)}/{len(df_c)} ({len(pos_c)/len(df_c):.0%})")
    print(f"  Contrarian Mean Sharpe: {df_c['sharpe'].mean():.3f}")

    # Pick best direction
    if df_c["sharpe"].mean() > df["sharpe"].mean():
        print("  >>> Contrarian direction is BETTER")
        return df_c, "contrarian"
    else:
        print("  >>> Conviction direction is BETTER")
        return df, "conviction"


def run_train_test_split(closes, volumes, direction, split_ratio=0.7):
    n = len(closes)
    split_idx = int(n * split_ratio)
    train_c, train_v = closes.iloc[:split_idx], volumes.iloc[:split_idx]
    test_c, test_v = closes.iloc[split_idx:], volumes.iloc[split_idx:]

    print(f"\n  70/30 Train/Test (direction: {direction})")
    negate = direction == "contrarian"

    best_sharpe = -999
    best_params = None
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking = price_volume_correlation(train_c, train_v, lookback)
        if negate:
            ranking = -ranking
        warmup = lookback + 5
        res = run_xs_factor(train_c, ranking, rebal, n_long, warmup=warmup)
        if res["sharpe"] > best_sharpe:
            best_sharpe = res["sharpe"]
            best_params = (lookback, rebal, n_long)

    lb, rb, nl = best_params
    print(f"  Train best: LB{lb}_R{rb}_N{nl} (IS {best_sharpe:.3f})")

    test_ranking = price_volume_correlation(test_c, test_v, lb)
    if negate:
        test_ranking = -test_ranking
    res_test = run_xs_factor(test_c, test_ranking, rb, nl, warmup=lb+5)
    print(f"  Test: Sharpe {res_test['sharpe']:.3f}, Ann {res_test['annual_ret']:.1%}")

    return {"train_sharpe": best_sharpe, "test_sharpe": res_test["sharpe"],
            "test_annual_ret": res_test["annual_ret"]}


def run_split_half(closes, volumes, direction):
    n = len(closes)
    mid = n // 2
    h1c, h1v = closes.iloc[:mid], volumes.iloc[:mid]
    h2c, h2v = closes.iloc[mid:], volumes.iloc[mid:]
    negate = direction == "contrarian"

    print(f"\n  Split-Half (direction: {direction})")
    r1_list, r2_list = [], []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        warmup = lookback + 5
        rank1 = price_volume_correlation(h1c, h1v, lookback)
        rank2 = price_volume_correlation(h2c, h2v, lookback)
        if negate:
            rank1, rank2 = -rank1, -rank2
        res1 = run_xs_factor(h1c, rank1, rebal, n_long, warmup=warmup)
        res2 = run_xs_factor(h2c, rank2, rebal, n_long, warmup=warmup)
        r1_list.append(res1["sharpe"])
        r2_list.append(res2["sharpe"])

    h1 = np.array(r1_list)
    h2 = np.array(r2_list)
    corr = np.corrcoef(h1, h2)[0, 1]
    print(f"  Corr: {corr:.3f}, H1 mean: {h1.mean():.3f}, H2 mean: {h2.mean():.3f}")
    return {"corr": round(float(corr), 3), "h1": round(float(h1.mean()), 3), "h2": round(float(h2.mean()), 3)}


def run_walk_forward_param_selection(closes, volumes, direction):
    print(f"\n  Walk-Forward with Parameter Selection ({direction})")
    negate = direction == "contrarian"
    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end = n - fold * WF_STEP
        test_start = test_end - WF_TEST
        train_start = test_start - WF_TRAIN
        if train_start < 0:
            break

        train_c, train_v = closes.iloc[train_start:test_start], volumes.iloc[train_start:test_start]
        test_c, test_v = closes.iloc[test_start:test_end], volumes.iloc[test_start:test_end]
        if len(test_c) < 30 or len(train_c) < 100:
            break

        best_sharpe = -999
        best_params = None
        for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
            ranking = price_volume_correlation(train_c, train_v, lookback)
            if negate:
                ranking = -ranking
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
        test_ranking = price_volume_correlation(test_c, test_v, lb)
        if negate:
            test_ranking = -test_ranking
        warmup = min(lb + 5, len(test_c) // 2)
        res = run_xs_factor(test_c, test_ranking, rb, nl, warmup=warmup)

        fold_results.append({
            "fold": fold + 1, "params": f"LB{lb}_R{rb}_N{nl}",
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


def compute_correlations(closes, volumes, lookback, rebal, n_long, direction):
    print(f"\n  Correlations with existing factors")
    negate = direction == "contrarian"

    ranking = price_volume_correlation(closes, volumes, lookback)
    if negate:
        ranking = -ranking
    res_f = run_xs_factor(closes, ranking, rebal, n_long, warmup=lookback+5)

    # H-012: momentum
    mom_ranking = closes.pct_change(60)
    res_mom = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)

    # H-021: volume momentum (5d/20d volume ratio)
    dollar_vol = closes * volumes
    short_avg = dollar_vol.rolling(5, min_periods=5).mean()
    long_avg = dollar_vol.rolling(20, min_periods=20).mean()
    volmom_ranking = (short_avg / long_avg).replace([np.inf, -np.inf], np.nan)
    res_volmom = run_xs_factor(closes, volmom_ranking, 3, 4, warmup=25)

    rets_f = res_f["equity"].pct_change().dropna()
    rets_mom = res_mom["equity"].pct_change().dropna()
    rets_vm = res_volmom["equity"].pct_change().dropna()

    common_m = rets_f.index.intersection(rets_mom.index)
    common_v = rets_f.index.intersection(rets_vm.index)

    corr_mom = rets_f.loc[common_m].corr(rets_mom.loc[common_m]) if len(common_m) > 50 else 0
    corr_vm = rets_f.loc[common_v].corr(rets_vm.loc[common_v]) if len(common_v) > 50 else 0

    print(f"    vs H-012 (momentum): {corr_mom:.3f}")
    print(f"    vs H-021 (vol momentum): {corr_vm:.3f}")
    return round(corr_mom, 3), round(corr_vm, 3)


if __name__ == "__main__":
    print("H-103: Price-Volume Correlation Factor")
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

    # 1. Full scan (both directions)
    scan, direction = run_full_scan(closes, volumes)
    best = scan.nlargest(1, "sharpe").iloc[0]
    best_lb = int(best["lookback"])
    best_rb = int(best["rebal"])
    best_n = int(best["n_long"])
    print(f"\n  Best ({direction}): LB{best_lb}_R{best_rb}_N{best_n}, Sharpe {best['sharpe']:.3f}")

    # 2. Train/Test
    tt = run_train_test_split(closes, volumes, direction)

    # 3. Split-Half
    sh = run_split_half(closes, volumes, direction)

    # 4. WF param selection
    wf_sel = run_walk_forward_param_selection(closes, volumes, direction)

    # 5. Correlations
    corr_mom, corr_vm = compute_correlations(closes, volumes, best_lb, best_rb, best_n, direction)

    # Summary
    pos_pct = (scan["sharpe"] > 0).mean()
    print("\n" + "=" * 70)
    print(f"SUMMARY: H-103 Price-Volume Correlation Factor ({direction})")
    print("=" * 70)
    print(f"  Combos: {len(scan)}, Positive: {(scan['sharpe']>0).sum()}/{len(scan)} ({pos_pct:.0%})")
    print(f"  Mean Sharpe: {scan['sharpe'].mean():.3f}, Best: {best['sharpe']:.3f}")
    print(f"  Direction: {direction}")
    print(f"  Train/Test: IS {tt['train_sharpe']:.3f} -> OOS {tt['test_sharpe']:.3f}")
    print(f"  Split-half: H1={sh['h1']:.3f}, H2={sh['h2']:.3f}, corr={sh['corr']:.3f}")
    if wf_sel is not None:
        print(f"  WF selected: {(wf_sel['oos_sharpe']>0).sum()}/{len(wf_sel)} positive, mean {wf_sel['oos_sharpe'].mean():.3f}")
    print(f"  Corr with H-012: {corr_mom:.3f}, with H-021: {corr_vm:.3f}")
