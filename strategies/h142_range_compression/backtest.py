"""
H-142: Intraday Range Compression Factor

Assets whose intraday range (high-low)/close has been compressing relative
to their historical average tend to be building energy for a breakout.

Signal: For each asset, compute daily range_ratio = (high - low) / close.
Then compute compression_ratio = short_avg(range_ratio) / long_avg(range_ratio).
Low compression_ratio = range compressing = LONG signal (coiled spring).
High compression_ratio = range expanding = SHORT signal (expecting contraction).

Cross-sectional ranking: LONG bottom N (most compressed), SHORT top N (most
expanded). Equal weight. Rebalance every R days using t-1 data.

Parameter grid:
  Short window: [5, 7, 10]
  Long window:  [20, 30, 40, 60]
  Rebalance:    [3, 5, 7]
  N:            [3, 4]
  Constraint:   short_window < long_window always (trivially satisfied here)
  72 combinations total

Validation:
  1. % of params with positive IS Sharpe (want >= 80%)
  2. Walk-forward: 6 folds of 120d IS / 90d OOS. Want >= 4/6 positive,
     mean OOS Sharpe > 0.5.
  3. Split-half: best params on each half. Want both halves positive Sharpe.
  4. Correlation with H-012 (60d momentum). Want < 0.4.

Fee: 0.06% per side (0.12% round trip).
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.0006  # 6 bps per side
INITIAL_CAPITAL = 10_000.0

# Parameter grid
SHORT_WINDOWS = [5, 7, 10]
LONG_WINDOWS  = [20, 30, 40, 60]
REBAL_FREQS   = [3, 5, 7]
N_LEGS        = [3, 4]

# Walk-forward config
WF_FOLDS = 6
WF_TRAIN = 120
WF_TEST  = 90
WF_STEP  = 90


def load_daily_data():
    """Load daily OHLCV parquet files for all assets."""
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
                print(f"  {sym}: only {len(df)} bars -- SKIPPED")
        else:
            print(f"  {sym}: no data file found -- SKIPPED")
    return daily


def build_matrices(daily):
    """Build close, high, and low matrices from daily data."""
    close_frames = {}
    high_frames = {}
    low_frames = {}
    for sym, df in daily.items():
        close_frames[sym] = df["close"]
        high_frames[sym] = df["high"]
        low_frames[sym] = df["low"]

    closes = pd.DataFrame(close_frames).sort_index().dropna(how="all")
    highs = pd.DataFrame(high_frames).sort_index().dropna(how="all")
    lows = pd.DataFrame(low_frames).sort_index().dropna(how="all")

    # Align all three
    common_idx = closes.index.intersection(highs.index).intersection(lows.index)
    closes = closes.loc[common_idx]
    highs = highs.loc[common_idx]
    lows = lows.loc[common_idx]

    # Forward fill small gaps
    closes = closes.ffill(limit=3)
    highs = highs.ffill(limit=3)
    lows = lows.ffill(limit=3)

    # Drop rows with too many NaNs
    thresh = len(closes.columns) // 2 + 1
    mask = closes.notna().sum(axis=1) >= thresh
    closes = closes.loc[mask]
    highs = highs.loc[mask]
    lows = lows.loc[mask]

    print(f"\n  Matrix: {closes.shape[0]} days x {closes.shape[1]} assets")
    print(f"  Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    return closes, highs, lows


def compute_range_compression(closes, highs, lows, short_window, long_window):
    """
    For each asset on each day:
      1. range_ratio = (high - low) / close
      2. short_avg = rolling mean of range_ratio over short_window
      3. long_avg = rolling mean of range_ratio over long_window
      4. compression_ratio = short_avg / long_avg

    Low compression_ratio = range compressing (coiled spring -> LONG)
    High compression_ratio = range expanding (-> SHORT)
    """
    # Compute daily range ratio
    range_ratio = (highs - lows) / closes

    # Rolling averages
    short_avg = range_ratio.rolling(window=short_window, min_periods=short_window).mean()
    long_avg = range_ratio.rolling(window=long_window, min_periods=long_window).mean()

    # Compression ratio: short / long
    # Avoid division by zero
    compression = short_avg / long_avg.replace(0, np.nan)

    return compression


def compute_metrics(equity_series):
    """Compute backtest performance metrics from equity curve."""
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


def run_xs_factor(closes, ranking_series, rebal_freq, n_long,
                  fee_rate=FEE_RATE, warmup=65, n_short=None):
    """
    Cross-sectional factor backtester.

    Long bottom N of ranking (most compressed = lowest compression ratio).
    Short top N of ranking (most expanded = highest compression ratio).
    """
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
            ranks = ranking_series.iloc[i - 1]  # use t-1 data
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            sorted_vals = valid.sort_values(ascending=True)
            # LONG bottom N (most compressed = lowest compression ratio)
            longs = sorted_vals.index[:n_long]
            # SHORT top N (most expanded = highest compression ratio)
            shorts = sorted_vals.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * fee_rate

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


def run_full_scan(closes, highs, lows):
    """Run all parameter combinations and return results DataFrame."""
    print("\n" + "=" * 70)
    print("H-142: INTRADAY RANGE COMPRESSION -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE * 10000:.0f} bps per side")

    # Pre-compute compression ratios for all (short, long) combos
    print("\n  Pre-computing compression ratios...")
    factor_cache = {}
    for sw, lw in product(SHORT_WINDOWS, LONG_WINDOWS):
        if sw >= lw:
            continue  # constraint: short < long
        key = (sw, lw)
        factor_cache[key] = compute_range_compression(closes, highs, lows, sw, lw)
        valid_count = factor_cache[key].notna().sum().sum()
        print(f"    SW={sw}, LW={lw}: {valid_count} valid values")

    results = []
    combos = [(sw, lw, rb, nl) for sw, lw, rb, nl
              in product(SHORT_WINDOWS, LONG_WINDOWS, REBAL_FREQS, N_LEGS)
              if sw < lw]
    total_combos = len(combos)
    print(f"\n  Running {total_combos} parameter combinations...")

    for idx, (sw, lw, rebal, n_leg) in enumerate(combos):
        ranking = factor_cache[(sw, lw)]
        warmup = lw + 5  # need long_window days for signal + buffer

        res = run_xs_factor(closes, ranking, rebal, n_leg, warmup=warmup)
        tag = f"SW{sw}_LW{lw}_R{rebal}_N{n_leg}"
        results.append({
            "tag": tag,
            "short_window": sw,
            "long_window": lw,
            "rebal": rebal,
            "n_leg": n_leg,
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
            "n_rebalances": res["n_rebalances"],
        })
        if (idx + 1) % 24 == 0:
            print(f"    ...{idx + 1}/{total_combos} done")

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]

    print(f"\n  Total parameter combos: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"  Best Sharpe:  {df['sharpe'].max():.3f}")
    print(f"  Worst Sharpe: {df['sharpe'].min():.3f}")
    print(f"  Mean Ann Return: {df['annual_ret'].mean():.1%}")
    print(f"  Mean Max DD: {df['max_dd'].mean():.1%}")

    # Breakdown by short window
    for sw in SHORT_WINDOWS:
        sub = df[df["short_window"] == sw]
        if len(sub) == 0:
            continue
        pos = (sub["sharpe"] > 0).sum()
        print(f"\n  Short Window={sw}:")
        print(f"    Positive Sharpe: {pos}/{len(sub)} ({pos/len(sub):.0%})")
        print(f"    Mean Sharpe: {sub['sharpe'].mean():.3f}")

    # Breakdown by long window
    for lw in LONG_WINDOWS:
        sub = df[df["long_window"] == lw]
        if len(sub) == 0:
            continue
        pos = (sub["sharpe"] > 0).sum()
        print(f"\n  Long Window={lw}:")
        print(f"    Positive Sharpe: {pos}/{len(sub)} ({pos/len(sub):.0%})")
        print(f"    Mean Sharpe: {sub['sharpe'].mean():.3f}")

    # Breakdown by N
    for nl in N_LEGS:
        sub = df[df["n_leg"] == nl]
        pos = (sub["sharpe"] > 0).sum()
        print(f"\n  N={nl}:")
        print(f"    Positive Sharpe: {pos}/{len(sub)} ({pos/len(sub):.0%})")
        print(f"    Mean Sharpe: {sub['sharpe'].mean():.3f}")

    print("\n  Top 20 parameter combos by Sharpe:")
    for _, row in df.sort_values("sharpe", ascending=False).head(20).iterrows():
        marker = "**" if row["sharpe"] > 0.5 else "  "
        print(f"  {marker} {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}, Trades {row['n_trades']}")

    return df, factor_cache


def run_walk_forward(closes, highs, lows, short_window, long_window,
                     rebal, n_leg):
    """Walk-forward validation with 6 folds of 120d IS / 90d OOS."""
    print(f"\n  Walk-Forward (Best Params): "
          f"SW{short_window}_LW{long_window}_R{rebal}_N{n_leg}")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, "
          f"{WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx   = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0 or test_end_idx <= test_start_idx:
            break

        # OOS test window
        test_closes = closes.iloc[test_start_idx:test_end_idx]
        test_highs  = highs.iloc[test_start_idx:test_end_idx]
        test_lows   = lows.iloc[test_start_idx:test_end_idx]
        if len(test_closes) < 30:
            break

        # Compute compression on test window
        test_ranking = compute_range_compression(
            test_closes, test_highs, test_lows, short_window, long_window)
        warmup = min(long_window + 5, len(test_closes) // 2)

        res = run_xs_factor(test_closes, test_ranking, rebal, n_leg,
                            warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
        })
        print(f"    Fold {fold+1}: {test_closes.index[0].date()} -> "
              f"{test_closes.index[-1].date()}, "
              f"Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}, "
              f"DD {res['max_dd']:.1%}, Trades {res['n_trades']}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df_wf = pd.DataFrame(fold_results)
    pos = (df_wf["sharpe"] > 0).sum()
    print(f"\n    Positive folds: {pos}/{len(df_wf)}")
    print(f"    Mean OOS Sharpe: {df_wf['sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df_wf['annual_ret'].mean():.1%}")
    print(f"    Total OOS test observations: {df_wf['n_days'].sum()} days")
    return df_wf


def run_walk_forward_optimized(closes, highs, lows):
    """
    Proper walk-forward: for each fold, run full param scan on IS to find
    best params, then evaluate those params on OOS.
    """
    print(f"\n  Walk-Forward Optimized (param re-selection per fold)")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, "
          f"{WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx   = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0 or test_end_idx <= test_start_idx:
            break

        # IS: train window
        train_closes = closes.iloc[train_start_idx:test_start_idx]
        train_highs  = highs.iloc[train_start_idx:test_start_idx]
        train_lows   = lows.iloc[train_start_idx:test_start_idx]

        # OOS: test window
        test_closes = closes.iloc[test_start_idx:test_end_idx]
        test_highs  = highs.iloc[test_start_idx:test_end_idx]
        test_lows   = lows.iloc[test_start_idx:test_end_idx]

        if len(train_closes) < 60 or len(test_closes) < 30:
            break

        # Find best params on IS
        best_sharpe_is = -999
        best_params_is = None
        for sw, lw, rb, nl in product(SHORT_WINDOWS, LONG_WINDOWS, REBAL_FREQS, N_LEGS):
            if sw >= lw:
                continue
            ranking = compute_range_compression(train_closes, train_highs, train_lows, sw, lw)
            warmup = min(lw + 5, len(train_closes) // 2)
            res = run_xs_factor(train_closes, ranking, rb, nl, warmup=warmup)
            if res["sharpe"] > best_sharpe_is:
                best_sharpe_is = res["sharpe"]
                best_params_is = (sw, lw, rb, nl)

        if best_params_is is None:
            break

        sw, lw, rb, nl = best_params_is

        # Evaluate best IS params on OOS
        test_ranking = compute_range_compression(test_closes, test_highs, test_lows, sw, lw)
        warmup = min(lw + 5, len(test_closes) // 2)
        res_oos = run_xs_factor(test_closes, test_ranking, rb, nl, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "is_sharpe": best_sharpe_is,
            "is_params": f"SW{sw}_LW{lw}_R{rb}_N{nl}",
            "sharpe": res_oos["sharpe"],
            "annual_ret": res_oos["annual_ret"],
            "max_dd": res_oos["max_dd"],
            "win_rate": res_oos["win_rate"],
            "n_trades": res_oos["n_trades"],
        })
        print(f"    Fold {fold+1}: {test_closes.index[0].date()} -> "
              f"{test_closes.index[-1].date()}, "
              f"IS best={best_params_is} Sharpe={best_sharpe_is:.3f}, "
              f"OOS Sharpe={res_oos['sharpe']:.3f}, "
              f"Ann {res_oos['annual_ret']:.1%}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df_wf = pd.DataFrame(fold_results)
    pos = (df_wf["sharpe"] > 0).sum()
    print(f"\n    Positive folds: {pos}/{len(df_wf)}")
    print(f"    Mean OOS Sharpe: {df_wf['sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df_wf['annual_ret'].mean():.1%}")
    print(f"    Total OOS test observations: {df_wf['n_days'].sum()} days")
    return df_wf


def run_split_half(closes, highs, lows):
    """Split data in two halves, run all params on each, check consistency."""
    n = len(closes)
    mid = n // 2
    h1_c, h2_c = closes.iloc[:mid], closes.iloc[mid:]
    h1_h, h2_h = highs.iloc[:mid], highs.iloc[mid:]
    h1_l, h2_l = lows.iloc[:mid], lows.iloc[mid:]

    print(f"\n  Split-Half Validation")
    print(f"  Half 1: {h1_c.index[0].date()} to {h1_c.index[-1].date()} ({len(h1_c)} days)")
    print(f"  Half 2: {h2_c.index[0].date()} to {h2_c.index[-1].date()} ({len(h2_c)} days)")

    results_h1 = []
    results_h2 = []

    for sw, lw, rb, nl in product(SHORT_WINDOWS, LONG_WINDOWS, REBAL_FREQS, N_LEGS):
        if sw >= lw:
            continue
        warmup = lw + 5

        r1 = compute_range_compression(h1_c, h1_h, h1_l, sw, lw)
        r2 = compute_range_compression(h2_c, h2_h, h2_l, sw, lw)

        res1 = run_xs_factor(h1_c, r1, rb, nl, warmup=warmup)
        res2 = run_xs_factor(h2_c, r2, rb, nl, warmup=warmup)

        results_h1.append(res1["sharpe"])
        results_h2.append(res2["sharpe"])

    h1_arr = np.array(results_h1)
    h2_arr = np.array(results_h2)

    corr, _ = spearmanr(h1_arr, h2_arr)
    both_pos = ((h1_arr > 0) & (h2_arr > 0)).sum()

    print(f"  Spearman rank corr (Sharpe H1 vs H2): {corr:.3f}")
    print(f"  Both halves positive: {both_pos}/{len(h1_arr)} ({both_pos/len(h1_arr):.0%})")
    print(f"  Half 1 mean Sharpe: {h1_arr.mean():.3f}")
    print(f"  Half 2 mean Sharpe: {h2_arr.mean():.3f}")
    print(f"  Half 1 % positive: {(h1_arr > 0).sum()}/{len(h1_arr)} "
          f"({(h1_arr > 0).mean():.0%})")
    print(f"  Half 2 % positive: {(h2_arr > 0).sum()}/{len(h2_arr)} "
          f"({(h2_arr > 0).mean():.0%})")

    if (h1_arr.mean() > 0.2 and h2_arr.mean() < -0.2) or \
       (h1_arr.mean() < -0.2 and h2_arr.mean() > 0.2):
        print("  WARNING: Signal inversion detected between halves!")

    return {
        "spearman_corr": round(float(corr), 3),
        "both_positive_pct": round(both_pos / len(h1_arr), 3),
        "half1_mean_sharpe": round(float(h1_arr.mean()), 3),
        "half2_mean_sharpe": round(float(h2_arr.mean()), 3),
        "half1_pct_positive": round(float((h1_arr > 0).mean()), 3),
        "half2_pct_positive": round(float((h2_arr > 0).mean()), 3),
    }


def compute_h012_correlation(closes, highs, lows,
                             short_window, long_window, rebal, n_leg):
    """Compute daily return correlation between H-142 and H-012 (60d momentum)."""
    print(f"\n  Correlation with H-012 (60d Momentum)")

    # H-142 returns
    ranking = compute_range_compression(closes, highs, lows, short_window, long_window)
    warmup = long_window + 5
    res_factor = run_xs_factor(closes, ranking, rebal, n_leg, warmup=warmup)

    # H-012 momentum: long top N by 60d return, short bottom N
    mom_ranking = closes.pct_change(60)
    # For momentum: long highest returns (top), short lowest (bottom)
    # Need to pass ranking where HIGH = LONG, but our backtester does
    # LONG bottom, SHORT top. So invert: pass negative momentum.
    # Actually, let's just build H-012 manually with correct direction.
    n = len(closes)
    equity_mom = np.zeros(n)
    equity_mom[0] = INITIAL_CAPITAL
    prev_w = pd.Series(0.0, index=closes.columns)

    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= 65 and (i - 65) % 5 == 0:
            ranks = mom_ranking.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < 8:
                port_ret = (prev_w * log_rets).sum()
                equity_mom[i] = equity_mom[i - 1] * np.exp(port_ret)
                continue

            sorted_v = valid.sort_values(ascending=False)
            longs = sorted_v.index[:4]
            shorts = sorted_v.index[-4:]

            new_w = pd.Series(0.0, index=closes.columns)
            for s in longs:
                new_w[s] = 0.25
            for s in shorts:
                new_w[s] = -0.25

            wc = (new_w - prev_w).abs()
            turnover = wc.sum() / 2
            fee_drag = turnover * FEE_RATE

            port_ret = (new_w * log_rets).sum() - fee_drag
            prev_w = new_w
        else:
            port_ret = (prev_w * log_rets).sum()

        equity_mom[i] = equity_mom[i - 1] * np.exp(port_ret)

    eq_mom = pd.Series(equity_mom, index=closes.index)
    eq_factor = res_factor["equity"]

    rets_factor = eq_factor.pct_change().dropna()
    rets_mom = eq_mom.pct_change().dropna()

    common = rets_factor.index.intersection(rets_mom.index)
    if len(common) < 50:
        print("    Insufficient overlap for correlation")
        return 0.0

    corr = rets_factor.loc[common].corr(rets_mom.loc[common])
    mom_metrics = compute_metrics(eq_mom)

    print(f"    Daily return correlation H-142 vs H-012: {corr:.3f}")
    print(f"    H-012 Momentum: Sharpe {mom_metrics['sharpe']:.3f}, "
          f"Ann {mom_metrics['annual_ret']:.1%}")
    print(f"    H-142 RangeComp: Sharpe {res_factor['sharpe']:.3f}, "
          f"Ann {res_factor['annual_ret']:.1%}")
    return round(corr, 3)


if __name__ == "__main__":
    print("=" * 70)
    print("H-142: Intraday Range Compression Factor")
    print("=" * 70)

    # 1. Load data
    print("\n[1/5] Loading daily data...")
    daily = load_daily_data()
    closes, highs, lows = build_matrices(daily)

    if closes.shape[1] < 6:
        print("ERROR: Too few assets loaded. Aborting.")
        sys.exit(1)

    # 2. Full parameter scan
    print("\n[2/5] Full Parameter Scan...")
    scan_df, factor_cache = run_full_scan(closes, highs, lows)

    best_row = scan_df.loc[scan_df["sharpe"].idxmax()]
    best_sw = int(best_row["short_window"])
    best_lw = int(best_row["long_window"])
    best_r  = int(best_row["rebal"])
    best_n  = int(best_row["n_leg"])

    print(f"\n  BEST OVERALL: {best_row['tag']}")
    print(f"    Sharpe {best_row['sharpe']:.3f}, Ann {best_row['annual_ret']:.1%}, "
          f"DD {best_row['max_dd']:.1%}, WR {best_row['win_rate']:.1%}")

    # 3. Walk-Forward (6 folds) -- both fixed-param and optimized
    print("\n[3/5] Walk-Forward Validation...")
    print("\n  --- Fixed Best Params ---")
    wf_fixed = run_walk_forward(closes, highs, lows, best_sw, best_lw, best_r, best_n)

    print("\n  --- Optimized (re-select params per fold) ---")
    wf_opt = run_walk_forward_optimized(closes, highs, lows)

    # Use the optimized WF as primary
    wf_df = wf_opt if wf_opt is not None else wf_fixed

    # 4. Split-Half
    print("\n[4/5] Split-Half Validation...")
    sh_results = run_split_half(closes, highs, lows)

    # 5. H-012 Correlation
    print("\n[5/5] H-012 Correlation...")
    h012_corr = compute_h012_correlation(closes, highs, lows,
                                          best_sw, best_lw, best_r, best_n)

    # ======== SUMMARY ========
    print("\n" + "=" * 70)
    print("H-142 SUMMARY -- INTRADAY RANGE COMPRESSION FACTOR")
    print("=" * 70)

    pct_positive = len(scan_df[scan_df["sharpe"] > 0]) / len(scan_df)
    mean_sharpe = scan_df["sharpe"].mean()

    print(f"\n  TEST 1: IN-SAMPLE PARAMETER ROBUSTNESS")
    print(f"    Total combos:       {len(scan_df)}")
    print(f"    % Positive Sharpe:  {pct_positive:.0%}  (target: >= 80%)")
    print(f"    Mean Sharpe:        {mean_sharpe:.3f}")
    print(f"    Best Sharpe:        {scan_df['sharpe'].max():.3f}  ({best_row['tag']})")
    test1_pass = pct_positive >= 0.80

    if wf_df is not None:
        pos_folds = int((wf_df["sharpe"] > 0).sum())
        mean_oos = wf_df["sharpe"].mean()
        print(f"\n  TEST 2: WALK-FORWARD OOS")
        print(f"    Folds completed:    {len(wf_df)}")
        print(f"    Positive folds:     {pos_folds}/{len(wf_df)}  (target: >= 4/6)")
        print(f"    Mean OOS Sharpe:    {mean_oos:.3f}  (target: > 0.5)")
        print(f"    Mean OOS Ann Ret:   {wf_df['annual_ret'].mean():.1%}")
        print(f"    Total test obs:     {wf_df['n_days'].sum()} days")
        test2_pass = pos_folds >= 4 and mean_oos > 0.5
    else:
        test2_pass = False

    print(f"\n  TEST 3: SPLIT-HALF CONSISTENCY")
    print(f"    H1 mean Sharpe:     {sh_results['half1_mean_sharpe']:.3f}")
    print(f"    H2 mean Sharpe:     {sh_results['half2_mean_sharpe']:.3f}")
    print(f"    Both positive:      {sh_results['half1_mean_sharpe'] > 0 and sh_results['half2_mean_sharpe'] > 0}")
    print(f"    Spearman corr:      {sh_results['spearman_corr']:.3f}")
    test3_pass = sh_results["half1_mean_sharpe"] > 0 and sh_results["half2_mean_sharpe"] > 0

    print(f"\n  TEST 4: H-012 CORRELATION")
    print(f"    Correlation:        {h012_corr:.3f}  (target: < 0.4)")
    test4_pass = abs(h012_corr) < 0.4

    # Verdict
    print("\n  " + "-" * 50)
    print(f"  Test 1 (IS >= 80% positive):   {'PASS' if test1_pass else 'FAIL'}  ({pct_positive:.0%})")
    if wf_df is not None:
        print(f"  Test 2 (WF >= 4/6, mean > 0.5): {'PASS' if test2_pass else 'FAIL'}  "
              f"({pos_folds}/6, mean {mean_oos:.3f})")
    else:
        print(f"  Test 2 (WF >= 4/6, mean > 0.5): FAIL  (no data)")
    print(f"  Test 3 (Split-half both pos):  {'PASS' if test3_pass else 'FAIL'}  "
          f"({sh_results['half1_mean_sharpe']:.3f} / {sh_results['half2_mean_sharpe']:.3f})")
    print(f"  Test 4 (H-012 corr < 0.4):     {'PASS' if test4_pass else 'FAIL'}  ({h012_corr:.3f})")

    all_pass = test1_pass and test2_pass and test3_pass and test4_pass
    if all_pass:
        verdict = "CONFIRMED"
        print(f"\n  VERDICT: {verdict} -- All 4 tests passed!")
    else:
        verdict = "REJECTED"
        failures = []
        if not test1_pass:
            failures.append(f"IS only {pct_positive:.0%} positive (need >= 80%)")
        if not test2_pass:
            if wf_df is not None:
                failures.append(f"WF: {pos_folds}/6 positive, mean OOS {mean_oos:.3f}")
            else:
                failures.append("WF: no valid folds")
        if not test3_pass:
            failures.append(f"Split-half: {sh_results['half1_mean_sharpe']:.3f} / "
                          f"{sh_results['half2_mean_sharpe']:.3f}")
        if not test4_pass:
            failures.append(f"H-012 corr {h012_corr:.3f} >= 0.4")
        print(f"\n  VERDICT: {verdict}")
        for f in failures:
            print(f"    - {f}")

    # Save results
    output_path = Path(__file__).parent / "results.json"
    results_dict = {
        "hypothesis": "H-142",
        "title": "Intraday Range Compression Factor",
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "n_days": int(len(closes)),
        "n_assets": int(len(closes.columns)),
        "n_combos": int(len(scan_df)),
        "test1_is_robustness": {
            "pct_positive_sharpe": round(pct_positive, 4),
            "mean_sharpe": round(mean_sharpe, 4),
            "best_sharpe": round(float(scan_df["sharpe"].max()), 4),
            "best_params": best_row["tag"],
            "best_annual_ret": round(float(best_row["annual_ret"]), 4),
            "best_max_dd": round(float(best_row["max_dd"]), 4),
            "pass": bool(test1_pass),
        },
        "test2_walk_forward": {
            "n_folds": int(len(wf_df)) if wf_df is not None else 0,
            "positive_folds": int((wf_df["sharpe"] > 0).sum()) if wf_df is not None else 0,
            "mean_oos_sharpe": round(float(wf_df["sharpe"].mean()), 3) if wf_df is not None else None,
            "mean_oos_annual_ret": round(float(wf_df["annual_ret"].mean()), 4) if wf_df is not None else None,
            "total_test_days": int(wf_df["n_days"].sum()) if wf_df is not None else 0,
            "fold_details": wf_df.to_dict("records") if wf_df is not None else [],
            "pass": bool(test2_pass),
        },
        "test3_split_half": {
            **sh_results,
            "pass": bool(test3_pass),
        },
        "test4_h012_correlation": {
            "correlation": h012_corr,
            "pass": bool(test4_pass),
        },
        "verdict": verdict,
    }

    with open(output_path, "w") as f:
        json.dump(results_dict, f, indent=2, default=str)
    print(f"\n  Results saved to {output_path}")
    print("=" * 70)
