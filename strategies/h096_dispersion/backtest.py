"""
H-096: Intraday Return Dispersion Factor (Cross-Sectional)

Rank 14 crypto assets by the ratio of mean intraday range to mean absolute
close-to-close return over a lookback window.

  dispersion_ratio = mean(range_i) / mean(abs_net_move_i))

where:
  range_i      = (high_i - low_i) / close_i      (intraday range, normalised)
  abs_net_move  = abs(close_i - close_{i-1}) / close_{i-1}  (absolute net move)

HIGH dispersion -> lots of intraday movement relative to net directional
  move -> noisy / mean-reverting.
LOW dispersion  -> net directional moves are large relative to intraday range
  -> efficient trending.

Strategy:
  Long bottom-N (lowest dispersion = most efficient trending)
  Short top-N (highest dispersion = most noisy)
  Dollar-neutral.

Relation to H-076 (Price Efficiency Factor):
  H-076 uses efficiency = abs(net_close_change_over_window) / sum(range).
  H-096 uses dispersion = mean(range) / mean(abs_daily_net_move).
  These are conceptually similar (both measure noise-vs-signal) but differ:
    - H-076 looks at cumulative net move vs cumulative range (path-level).
    - H-096 looks at average daily range vs average daily net move (bar-level).
  We compute correlation to check overlap.

Validation: walk-forward (6 folds, 90d OOS), split-half,
70/30 train/test, parameter robustness, correlation with H-012 momentum
and H-076 price efficiency.
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

FEE_RATE = 0.0005       # 5 bps per leg (10 bps round trip) as specified
INITIAL_CAPITAL = 10_000.0

# Parameter grid
LOOKBACKS = [10, 20, 30, 40, 60]
REBAL_FREQS = [3, 5, 7]
N_LONGS = [3, 4, 5]

# Walk-forward config
WF_FOLDS = 6
WF_TRAIN = 300
WF_TEST = 90
WF_STEP = 90


def load_daily_data():
    """Load daily parquet data for all 14 assets."""
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
    """Compute standard metrics from equity curve."""
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


def dispersion_factor(closes, highs, lows, lookback):
    """
    Compute dispersion ratio for each asset/day.

    dispersion = mean(intraday_range) / mean(abs_net_move) over lookback window.

    LOW dispersion = efficient trending (net moves are large vs intraday noise)
    HIGH dispersion = noisy (lots of intraday range but little net directional move)

    We return NEGATIVE dispersion so that "higher ranking = go long" convention
    means we long the LEAST noisy (most efficient) assets.
    """
    # Normalised intraday range: (high - low) / close
    intraday_range = (highs - lows) / closes

    # Absolute net move: abs(close - prev_close) / prev_close
    abs_net_move = closes.pct_change().abs()

    # Rolling means
    mean_range = intraday_range.rolling(lookback, min_periods=lookback).mean()
    mean_net_move = abs_net_move.rolling(lookback, min_periods=lookback).mean()

    # Dispersion ratio (avoid div by zero)
    dispersion = mean_range / mean_net_move.replace(0, np.nan)

    # Return NEGATIVE dispersion so higher = more efficient = go long
    return -dispersion


def h076_efficiency_factor(closes, highs, lows, lookback):
    """
    H-076 Price Efficiency Factor for correlation comparison.
    efficiency = abs(close_end/close_start - 1) / sum(high_i/low_i - 1)
    Higher = more efficient.
    """
    # Net change over lookback
    net_change = (closes / closes.shift(lookback) - 1).abs()

    # Sum of daily high/low range over lookback
    daily_range = highs / lows - 1
    sum_range = daily_range.rolling(lookback, min_periods=lookback).sum()

    # Efficiency
    efficiency = net_change / sum_range.replace(0, np.nan)
    return efficiency


def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  warmup=65):
    """
    Generic cross-sectional factor backtester using log returns.
    Higher ranking value = go long, lower = go short.
    Dollar-neutral: equal $ on long side and short side.
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

        # Log returns for the day
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            # Use t-1 ranking (no look-ahead)
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

            # Turnover = sum of absolute weight changes / 2
            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * FEE_RATE

            # PnL for the day using log returns
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


# =========================================================================
# Full parameter scan
# =========================================================================

def run_full_scan(closes, highs, lows):
    """Run all parameter combinations on the full period."""
    print("\n" + "=" * 70)
    print("H-096: INTRADAY RETURN DISPERSION FACTOR -- Full Parameter Scan")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE*10000:.0f} bps per leg")

    results = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking = dispersion_factor(closes, highs, lows, lookback)
        warmup = lookback + 5

        res = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup)
        tag = f"L{lookback}_R{rebal}_N{n_long}"
        results.append({
            "tag": tag,
            "lookback": lookback,
            "rebal": rebal,
            "n_long": n_long,
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
            "n_rebalances": res["n_rebalances"],
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
    for _, row in df.nlargest(10, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}, Trades {row['n_trades']}")

    print("\n  Bottom 5 by Sharpe:")
    for _, row in df.nsmallest(5, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    return df


# =========================================================================
# 70/30 Train/Test Split
# =========================================================================

def run_train_test_split(closes, highs, lows, split_ratio=0.7):
    """Run parameter scan on 70% train, evaluate best on 30% test."""
    n = len(closes)
    split_idx = int(n * split_ratio)
    train_c = closes.iloc[:split_idx]
    train_h = highs.iloc[:split_idx]
    train_l = lows.iloc[:split_idx]
    test_c = closes.iloc[split_idx:]
    test_h = highs.iloc[split_idx:]
    test_l = lows.iloc[split_idx:]

    print(f"\n  70/30 Train/Test Split")
    print(f"  Train: {train_c.index[0].date()} to {train_c.index[-1].date()} ({len(train_c)} days)")
    print(f"  Test:  {test_c.index[0].date()} to {test_c.index[-1].date()} ({len(test_c)} days)")

    best_sharpe = -999
    best_params = None
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking = dispersion_factor(train_c, train_h, train_l, lookback)
        warmup = lookback + 5
        res = run_xs_factor(train_c, ranking, rebal, n_long, warmup=warmup)
        if res["sharpe"] > best_sharpe:
            best_sharpe = res["sharpe"]
            best_params = (lookback, rebal, n_long)

    lookback, rebal, n_long = best_params
    print(f"  Train best: L{lookback}_R{rebal}_N{n_long} (Sharpe {best_sharpe:.3f})")

    test_ranking = dispersion_factor(test_c, test_h, test_l, lookback)
    warmup = lookback + 5
    res_test = run_xs_factor(test_c, test_ranking, rebal, n_long, warmup=warmup)
    print(f"  Test result: Sharpe {res_test['sharpe']:.3f}, "
          f"Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}")

    return {
        "train_best_params": f"L{lookback}_R{rebal}_N{n_long}",
        "train_sharpe": best_sharpe,
        "test_sharpe": res_test["sharpe"],
        "test_annual_ret": res_test["annual_ret"],
        "test_max_dd": res_test["max_dd"],
        "test_win_rate": res_test["win_rate"],
        "test_n_days": len(test_c),
    }


# =========================================================================
# Split-Half Validation
# =========================================================================

def run_split_half(closes, highs, lows):
    """Split data into two halves, run scan on each, compare rankings."""
    n = len(closes)
    mid = n // 2
    h1_c, h1_h, h1_l = closes.iloc[:mid], highs.iloc[:mid], lows.iloc[:mid]
    h2_c, h2_h, h2_l = closes.iloc[mid:], highs.iloc[mid:], lows.iloc[mid:]

    print(f"\n  Split-Half Validation")
    print(f"  Half 1: {h1_c.index[0].date()} to {h1_c.index[-1].date()} ({len(h1_c)} days)")
    print(f"  Half 2: {h2_c.index[0].date()} to {h2_c.index[-1].date()} ({len(h2_c)} days)")

    results_h1 = []
    results_h2 = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking1 = dispersion_factor(h1_c, h1_h, h1_l, lookback)
        warmup = lookback + 5
        res1 = run_xs_factor(h1_c, ranking1, rebal, n_long, warmup=warmup)

        ranking2 = dispersion_factor(h2_c, h2_h, h2_l, lookback)
        res2 = run_xs_factor(h2_c, ranking2, rebal, n_long, warmup=warmup)

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


# =========================================================================
# Walk-Forward Validation
# =========================================================================

def run_walk_forward(closes, highs, lows, lookback, rebal, n_long):
    """Walk-forward with FIXED params: 6 folds, 90d test each."""
    print(f"\n  Walk-Forward (Fixed Params): L{lookback}_R{rebal}_N{n_long}")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, {WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0:
            print(f"    Fold {fold+1}: insufficient data, skipping")
            break

        test_c = closes.iloc[test_start_idx:test_end_idx]
        test_h = highs.iloc[test_start_idx:test_end_idx]
        test_l = lows.iloc[test_start_idx:test_end_idx]

        if len(test_c) < 30:
            print(f"    Fold {fold+1}: test period too short ({len(test_c)} days)")
            break

        test_ranking = dispersion_factor(test_c, test_h, test_l, lookback)
        warmup = min(lookback + 5, len(test_c) // 2)

        res = run_xs_factor(test_c, test_ranking, rebal, n_long, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_c.index[0].strftime("%Y-%m-%d"),
            "end": test_c.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_c),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
        })
        print(f"    Fold {fold+1}: {test_c.index[0].date()} -> {test_c.index[-1].date()}, "
              f"Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["sharpe"] > 0).sum()
    print(f"\n    Positive folds: {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe: {df['sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df['annual_ret'].mean():.1%}")
    print(f"    Worst OOS DD: {df['max_dd'].max():.1%}")
    return df


def run_walk_forward_param_selection(closes, highs, lows):
    """Walk-forward with in-sample parameter selection per fold."""
    print(f"\n  Walk-Forward with In-Sample Parameter Selection")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, {WF_STEP}d step")

    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx = n - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0:
            break

        train_c = closes.iloc[train_start_idx:test_start_idx]
        train_h = highs.iloc[train_start_idx:test_start_idx]
        train_l = lows.iloc[train_start_idx:test_start_idx]
        test_c = closes.iloc[test_start_idx:test_end_idx]
        test_h = highs.iloc[test_start_idx:test_end_idx]
        test_l = lows.iloc[test_start_idx:test_end_idx]

        if len(test_c) < 30 or len(train_c) < 100:
            break

        # Find best params on train set
        best_sharpe = -999
        best_params = None
        for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
            ranking = dispersion_factor(train_c, train_h, train_l, lookback)
            warmup = lookback + 5
            if warmup >= len(train_c) - 30:
                continue
            res = run_xs_factor(train_c, ranking, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_params = (lookback, rebal, n_long)

        if best_params is None:
            break

        # Evaluate on test set
        lookback, rebal, n_long = best_params
        test_ranking = dispersion_factor(test_c, test_h, test_l, lookback)
        warmup = min(lookback + 5, len(test_c) // 2)
        res = run_xs_factor(test_c, test_ranking, rebal, n_long, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_c.index[0].strftime("%Y-%m-%d"),
            "end": test_c.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_c),
            "train_best_params": f"L{lookback}_R{rebal}_N{n_long}",
            "train_sharpe": round(best_sharpe, 3),
            "oos_sharpe": res["sharpe"],
            "oos_annual_ret": res["annual_ret"],
            "oos_max_dd": res["max_dd"],
        })
        print(f"    Fold {fold+1}: train best=L{lookback}_R{rebal}_N{n_long} "
              f"(IS Sharpe {best_sharpe:.3f}), "
              f"OOS Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}")

    if not fold_results:
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe"] > 0).sum()
    print(f"\n    Positive OOS folds: {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe: {df['oos_sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df['oos_annual_ret'].mean():.1%}")
    return df


# =========================================================================
# Correlation with H-012 (Momentum) and H-076 (Price Efficiency)
# =========================================================================

def compute_correlations(closes, highs, lows, lookback, rebal, n_long):
    """Compute daily return correlations with H-012 momentum and H-076 efficiency."""
    print(f"\n  Correlations with Other Factors")

    # Run H-096 dispersion factor
    disp_ranking = dispersion_factor(closes, highs, lows, lookback)
    warmup_disp = lookback + 5
    res_disp = run_xs_factor(closes, disp_ranking, rebal, n_long, warmup=warmup_disp)

    # Run H-012 momentum (60d lookback, rebal 5d, N=4)
    mom_ranking = closes.pct_change(60)
    res_mom = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)

    # Run H-076 price efficiency (40d lookback, rebal 5d, N=4)
    eff_ranking = h076_efficiency_factor(closes, highs, lows, 40)
    res_eff = run_xs_factor(closes, eff_ranking, 5, 4, warmup=45)

    eq_disp = res_disp["equity"]
    eq_mom = res_mom["equity"]
    eq_eff = res_eff["equity"]

    rets_disp = eq_disp.pct_change().dropna()
    rets_mom = eq_mom.pct_change().dropna()
    rets_eff = eq_eff.pct_change().dropna()

    # Correlation with H-012
    common_mom = rets_disp.index.intersection(rets_mom.index)
    if len(common_mom) >= 50:
        corr_h012 = rets_disp.loc[common_mom].corr(rets_mom.loc[common_mom])
        print(f"    H-096 vs H-012 (Momentum) daily return corr: {corr_h012:.3f}")
        print(f"    H-012 Momentum: Sharpe {res_mom['sharpe']:.3f}, Ann {res_mom['annual_ret']:.1%}")
    else:
        corr_h012 = np.nan
        print("    Insufficient overlap for H-012 correlation")

    # Correlation with H-076
    common_eff = rets_disp.index.intersection(rets_eff.index)
    if len(common_eff) >= 50:
        corr_h076 = rets_disp.loc[common_eff].corr(rets_eff.loc[common_eff])
        print(f"    H-096 vs H-076 (Efficiency) daily return corr: {corr_h076:.3f}")
        print(f"    H-076 Efficiency: Sharpe {res_eff['sharpe']:.3f}, Ann {res_eff['annual_ret']:.1%}")
    else:
        corr_h076 = np.nan
        print("    Insufficient overlap for H-076 correlation")

    print(f"    H-096 Dispersion: Sharpe {res_disp['sharpe']:.3f}, Ann {res_disp['annual_ret']:.1%}")

    # Also compute rank correlation of the factor signals themselves
    # (to see if H-096 and H-076 rank assets similarly)
    disp_ranks = disp_ranking.iloc[-1].dropna().rank()
    eff_ranks = eff_ranking.iloc[-1].dropna().rank()
    common_assets = disp_ranks.index.intersection(eff_ranks.index)
    if len(common_assets) >= 5:
        signal_corr = disp_ranks.loc[common_assets].corr(eff_ranks.loc[common_assets])
        print(f"    H-096 vs H-076 SIGNAL rank correlation (latest day): {signal_corr:.3f}")
    else:
        signal_corr = np.nan

    # Compute rolling signal rank correlation across all days
    signal_corrs = []
    for i in range(max(lookback + 5, 45), len(closes)):
        d_ranks = disp_ranking.iloc[i].dropna().rank()
        e_ranks = eff_ranking.iloc[i].dropna().rank()
        common_a = d_ranks.index.intersection(e_ranks.index)
        if len(common_a) >= 5:
            sc = d_ranks.loc[common_a].corr(e_ranks.loc[common_a])
            signal_corrs.append(sc)
    if signal_corrs:
        mean_signal_corr = np.nanmean(signal_corrs)
        print(f"    H-096 vs H-076 mean SIGNAL rank correlation (all days): {mean_signal_corr:.3f}")
    else:
        mean_signal_corr = np.nan

    return {
        "h012_return_corr": round(float(corr_h012), 3) if not np.isnan(corr_h012) else None,
        "h076_return_corr": round(float(corr_h076), 3) if not np.isnan(corr_h076) else None,
        "h076_signal_corr_latest": round(float(signal_corr), 3) if not np.isnan(signal_corr) else None,
        "h076_signal_corr_mean": round(float(mean_signal_corr), 3) if signal_corrs else None,
    }


# =========================================================================
# Fee Robustness
# =========================================================================

def run_fee_robustness(closes, highs, lows, lookback, rebal, n_long):
    """Test with various fee levels."""
    global FEE_RATE
    original_fee = FEE_RATE
    print(f"\n  Fee Robustness Test")

    fee_results = []
    for fee_mult, label in [(0, "0 bps"), (1, "5 bps"), (2, "10 bps"),
                            (3, "15 bps"), (5, "25 bps")]:
        FEE_RATE = original_fee * fee_mult if fee_mult > 0 else 0.0
        ranking = dispersion_factor(closes, highs, lows, lookback)
        warmup = lookback + 5
        res = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup)
        fee_results.append({
            "fee_label": label,
            "fee_bps": round(FEE_RATE * 10000, 1),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
        })
        print(f"    {label} ({FEE_RATE*10000:.0f} bps): Sharpe {res['sharpe']:.3f}, "
              f"Ann {res['annual_ret']:.1%}")

    FEE_RATE = original_fee
    return fee_results


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    print("H-096: Intraday Return Dispersion Factor")
    print("=" * 70)

    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")

    if len(daily) < 10:
        print("ERROR: Not enough assets loaded. Aborting.")
        sys.exit(1)

    # Build closes, highs, lows panels
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    highs = pd.DataFrame({sym: df["high"] for sym, df in daily.items()})
    lows = pd.DataFrame({sym: df["low"] for sym, df in daily.items()})

    # Align
    closes = closes.dropna(how="all").ffill().dropna()
    highs = highs.reindex(closes.index).ffill().dropna()
    lows = lows.reindex(closes.index).ffill().dropna()

    # Ensure same columns and index
    common_cols = closes.columns.intersection(highs.columns).intersection(lows.columns)
    common_idx = closes.index.intersection(highs.index).intersection(lows.index)
    closes = closes.loc[common_idx, common_cols]
    highs = highs.loc[common_idx, common_cols]
    lows = lows.loc[common_idx, common_cols]

    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")
    print(f"Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    # ===== 1. Full parameter scan =====
    scan_results = run_full_scan(closes, highs, lows)

    # ===== 2. Best parameters =====
    best = scan_results.nlargest(1, "sharpe").iloc[0]
    best_lookback = int(best["lookback"])
    best_rebal = int(best["rebal"])
    best_n_long = int(best["n_long"])
    print(f"\n  Best full-period params: L{best_lookback}_R{best_rebal}_N{best_n_long}")
    print(f"  Sharpe: {best['sharpe']:.3f}, Ann Return: {best['annual_ret']:.1%}, "
          f"Max DD: {best['max_dd']:.1%}, Win Rate: {best['win_rate']:.1%}")

    # ===== 3. 70/30 Train/Test Split =====
    train_test = run_train_test_split(closes, highs, lows)

    # ===== 4. Split-Half Validation =====
    split_half = run_split_half(closes, highs, lows)

    # ===== 5. Walk-Forward (fixed params) =====
    wf_fixed = run_walk_forward(closes, highs, lows, best_lookback, best_rebal, best_n_long)

    # ===== 6. Walk-Forward with parameter selection =====
    wf_selected = run_walk_forward_param_selection(closes, highs, lows)

    # ===== 7. Correlations with H-012 and H-076 =====
    correlations = compute_correlations(closes, highs, lows, best_lookback, best_rebal, best_n_long)

    # ===== 8. Fee Robustness =====
    fee_results = run_fee_robustness(closes, highs, lows, best_lookback, best_rebal, best_n_long)

    # ===== 9. Parameter Robustness =====
    pos_pct = (scan_results["sharpe"] > 0).mean()
    mean_sharpe = scan_results["sharpe"].mean()
    median_sharpe = scan_results["sharpe"].median()

    # ===== 10. Summary =====
    print("\n" + "=" * 70)
    print("SUMMARY: H-096 Intraday Return Dispersion Factor")
    print("=" * 70)
    print(f"  Parameter combos tested: {len(scan_results)}")
    print(f"  Positive Sharpe: {(scan_results['sharpe'] > 0).sum()}/{len(scan_results)} ({pos_pct:.0%})")
    print(f"  Mean Sharpe: {mean_sharpe:.3f}, Median: {median_sharpe:.3f}")
    print(f"  Best full-period: L{best_lookback}_R{best_rebal}_N{best_n_long}, "
          f"Sharpe {best['sharpe']:.3f}, Ann {best['annual_ret']:.1%}, DD {best['max_dd']:.1%}")

    print(f"\n  70/30 Train/Test:")
    print(f"    Train best params: {train_test['train_best_params']} (IS Sharpe {train_test['train_sharpe']:.3f})")
    print(f"    OOS Sharpe: {train_test['test_sharpe']:.3f}, "
          f"Ann: {train_test['test_annual_ret']:.1%}, DD: {train_test['test_max_dd']:.1%}")

    print(f"\n  Split-Half:")
    print(f"    Sharpe correlation: {split_half['sharpe_correlation']:.3f}")
    print(f"    Both positive: {split_half['both_positive_pct']:.0%}")

    if wf_fixed is not None:
        wf_pos = (wf_fixed["sharpe"] > 0).sum()
        print(f"\n  Walk-Forward (fixed params): {wf_pos}/{len(wf_fixed)} positive, "
              f"mean OOS Sharpe {wf_fixed['sharpe'].mean():.3f}")
    if wf_selected is not None:
        wf_pos2 = (wf_selected["oos_sharpe"] > 0).sum()
        print(f"  Walk-Forward (param selection): {wf_pos2}/{len(wf_selected)} positive, "
              f"mean OOS Sharpe {wf_selected['oos_sharpe'].mean():.3f}")

    print(f"\n  Correlation with H-012 (momentum): {correlations['h012_return_corr']}")
    print(f"  Correlation with H-076 (efficiency): {correlations['h076_return_corr']}")
    if correlations.get('h076_signal_corr_mean') is not None:
        print(f"  H-076 SIGNAL rank correlation (mean): {correlations['h076_signal_corr_mean']}")
        if abs(correlations['h076_signal_corr_mean']) > 0.5:
            print(f"  *** WARNING: Signal correlation with H-076 > 0.5 — high overlap concern! ***")

    print(f"\n  Fee Robustness:")
    for fr in fee_results:
        print(f"    {fr['fee_label']}: Sharpe {fr['sharpe']:.3f}")

    # Determine recommendation
    wf_mean = wf_fixed["sharpe"].mean() if wf_fixed is not None else -99
    wf_pos_rate = (wf_fixed["sharpe"] > 0).sum() / len(wf_fixed) if wf_fixed is not None else 0
    h076_overlap = abs(correlations.get("h076_signal_corr_mean", 0) or 0) > 0.5
    h076_ret_overlap = abs(correlations.get("h076_return_corr", 0) or 0) > 0.5

    print(f"\n  RECOMMENDATION:")
    if pos_pct >= 0.5 and wf_mean > 0 and wf_pos_rate >= 0.5:
        if h076_overlap or h076_ret_overlap:
            print(f"    CONDITIONAL — Results look decent but HIGH OVERLAP with H-076.")
            print(f"    Adding H-096 alongside H-076 would provide marginal diversification.")
            recommendation = "CONDITIONAL (high H-076 overlap)"
        else:
            print(f"    CONFIRMED — Robust results, low overlap with existing factors.")
            recommendation = "CONFIRMED"
    elif pos_pct >= 0.3 and wf_mean > -0.5:
        print(f"    CONDITIONAL — Some positive signal but needs more validation.")
        recommendation = "CONDITIONAL"
    else:
        print(f"    REJECTED — Insufficient robustness or poor OOS performance.")
        recommendation = "REJECTED"

    # ===== 11. Save results =====
    results_file = Path(__file__).parent / "results.json"
    results_data = {
        "hypothesis": "H-096",
        "name": "Intraday Return Dispersion Factor",
        "description": "Cross-sectional: long low-dispersion (efficient trending) assets, short high-dispersion (noisy) assets",
        "fee_rate_bps": 5.0,
        "universe_size": len(closes.columns),
        "n_days": len(closes),
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "recommendation": recommendation,
        "full_scan": {
            "n_combos": len(scan_results),
            "pct_positive_sharpe": round(float(pos_pct), 3),
            "mean_sharpe": round(float(mean_sharpe), 3),
            "median_sharpe": round(float(median_sharpe), 3),
            "best_params": f"L{best_lookback}_R{best_rebal}_N{best_n_long}",
            "best_sharpe": round(float(best["sharpe"]), 3),
            "best_annual_ret": round(float(best["annual_ret"]), 4),
            "best_max_dd": round(float(best["max_dd"]), 4),
            "best_win_rate": round(float(best["win_rate"]), 4),
            "best_n_trades": int(best["n_trades"]),
            "all_results": scan_results.to_dict("records"),
        },
        "train_test_70_30": train_test,
        "split_half": split_half,
        "walk_forward_fixed": {
            "params": f"L{best_lookback}_R{best_rebal}_N{best_n_long}",
            "n_folds": len(wf_fixed) if wf_fixed is not None else 0,
            "positive_folds": int((wf_fixed["sharpe"] > 0).sum()) if wf_fixed is not None else 0,
            "mean_oos_sharpe": round(float(wf_fixed["sharpe"].mean()), 3) if wf_fixed is not None else 0,
            "mean_oos_annual_ret": round(float(wf_fixed["annual_ret"].mean()), 4) if wf_fixed is not None else 0,
            "folds": wf_fixed.to_dict("records") if wf_fixed is not None else [],
        },
        "walk_forward_selected": {
            "n_folds": len(wf_selected) if wf_selected is not None else 0,
            "positive_folds": int((wf_selected["oos_sharpe"] > 0).sum()) if wf_selected is not None else 0,
            "mean_oos_sharpe": round(float(wf_selected["oos_sharpe"].mean()), 3) if wf_selected is not None else 0,
            "folds": wf_selected.to_dict("records") if wf_selected is not None else [],
        },
        "correlations": correlations,
        "fee_robustness": fee_results,
        "parameter_robustness": {
            "pct_positive_sharpe": round(float(pos_pct), 3),
            "mean_sharpe": round(float(mean_sharpe), 3),
            "median_sharpe": round(float(median_sharpe), 3),
        },
    }

    with open(results_file, "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\n  Results saved to {results_file}")
