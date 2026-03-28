"""
H-111: Directional Volume Imbalance Factor

Cross-sectional factor using the ratio of up-day volume to total volume.
- up-day defined two ways: close > open (intraday), or close > prev_close (interday)
- Try both definitions, pick the better one
- rolling up-volume ratio = sum(volume on up days) / sum(all volume) over lookback
- Long top N (accumulation), short bottom N (distribution)
- Dollar-neutral / market-neutral, equal-weight

Parameter grid:
  Lookback windows: [10, 20, 30, 40]
  Rebalance frequencies: [3, 5, 7, 10] days
  N positions each side: [3, 4, 5]

Validation:
  1. Full in-sample parameter scan
  2. Parameter robustness (% positive Sharpe)
  3. Walk-forward OOS: 6-fold rolling WF (60% train / 40% test)
  4. Split-half stability
  5. Correlation with H-012 momentum (60d, 5d rebal, N=4)
     and H-021 volume momentum (5d/20d ratio, 3d rebal, N=4)
  6. Fee sensitivity: 0.1% round-trip (10 bps one-way)
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

# =========================================================================
# Constants
# =========================================================================

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001        # 10 bps one-way = 0.1% round-trip taker (Bybit)
INITIAL_CAPITAL = 10_000.0

# Parameter grid
LOOKBACKS = [10, 20, 30, 40]
REBAL_FREQS = [3, 5, 7, 10]
N_LONGS = [3, 4, 5]

# Walk-forward: 6 folds, 60/40 train/test rolling
WF_FOLDS = 6


# =========================================================================
# Data Loading
# =========================================================================

def load_daily_data():
    """Load pre-cached daily parquet data for all 14 assets."""
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
                print(f"  {sym}: only {len(df)} bars — skipping")
        else:
            print(f"  {sym}: no parquet found — will fetch via ccxt")
    return daily


def fetch_via_ccxt(symbols_missing):
    """Fetch OHLCV via ccxt for any missing assets."""
    try:
        import ccxt
    except ImportError:
        print("  ccxt not available — skipping fetch")
        return {}

    ex = ccxt.bybit()
    fetched = {}
    for sym in symbols_missing:
        # try perpetual first, then spot
        for market_sym in [sym.replace("/", "/USDT:") if "USDT" in sym else sym, sym]:
            try:
                bars = ex.fetch_ohlcv(market_sym, "1d", limit=1100)
                if len(bars) < 200:
                    continue
                df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("date", inplace=True)
                df = df[["open", "high", "low", "close", "volume"]]
                fetched[sym] = df
                print(f"  {sym}: fetched {len(df)} bars via ccxt")
                break
            except Exception as e:
                print(f"  {sym} ({market_sym}): ccxt error — {e}")
    return fetched


# =========================================================================
# Up-Volume Ratio Factor
# =========================================================================

def up_volume_ratio_factor(closes, opens, volumes, lookback, up_def="close_vs_open"):
    """
    Compute rolling up-volume ratio for each asset.

    up_def:
      'close_vs_open'     — up day if close > open (intraday direction)
      'close_vs_prev'     — up day if close > previous close (interday direction)

    Returns DataFrame (same shape as closes) with up_volume_ratio values.
    """
    if up_def == "close_vs_open":
        up_mask = (closes > opens).astype(float)
    elif up_def == "close_vs_prev":
        up_mask = (closes.diff() > 0).astype(float)
    else:
        raise ValueError(f"Unknown up_def: {up_def}")

    up_vol = (volumes * up_mask).rolling(lookback, min_periods=lookback).sum()
    total_vol = volumes.rolling(lookback, min_periods=lookback).sum()

    ratio = up_vol / total_vol
    ratio = ratio.replace([np.inf, -np.inf], np.nan)
    return ratio


# =========================================================================
# Portfolio Backtester
# =========================================================================

def compute_metrics(equity_series):
    """Standard metrics from equity curve."""
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99.0, "annual_ret": 0.0, "max_dd": 1.0, "win_rate": 0.0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    return {
        "sharpe": round(float(sharpe_ratio(rets, periods_per_year=365)), 3),
        "annual_ret": round(float(annual_return(eq, periods_per_year=365)), 4),
        "max_dd": round(float(max_drawdown(eq)), 4),
        "win_rate": round(n_pos / n_total, 4) if n_total > 0 else 0.0,
    }


def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  warmup=None, fee_rate=FEE_RATE):
    """
    Generic cross-sectional factor backtester.
    Higher ranking value = go long, lower = go short.
    Dollar-neutral: equal $ on long side and short side.
    Fee charged at each rebalance proportional to turnover.
    """
    if n_short is None:
        n_short = n_long
    if warmup is None:
        warmup = 5

    n = len(closes)
    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

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


# =========================================================================
# 1. Full In-Sample Parameter Scan
# =========================================================================

def run_full_scan(closes, opens, volumes, up_def):
    """Run all parameter combinations on the full period."""
    print(f"\n{'='*70}")
    print(f"H-111: DIRECTIONAL VOLUME IMBALANCE -- Full Scan (up_def='{up_def}')")
    print(f"{'='*70}")
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE*10000:.0f} bps per trade (one-way)")

    results = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        ranking = up_volume_ratio_factor(closes, opens, volumes, lookback, up_def)
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

    print("\n  Top 10 parameter combos:")
    for _, row in df.sort_values("sharpe", ascending=False).head(10).iterrows():
        marker = "**" if row["sharpe"] > 1.0 else ("* " if row["sharpe"] > 0.5 else "  ")
        print(f"  {marker} {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}, Trades {row['n_trades']}")

    return df


# =========================================================================
# 2. Fee Sensitivity
# =========================================================================

def run_fee_sensitivity(closes, opens, volumes, up_def, lookback, rebal, n_long):
    """Test Sharpe across multiple fee levels."""
    print(f"\n  Fee Sensitivity Analysis (L{lookback}_R{rebal}_N{n_long})")
    ranking = up_volume_ratio_factor(closes, opens, volumes, lookback, up_def)
    warmup = lookback + 5

    fee_levels = [0.0, 0.0006, 0.001, 0.002, 0.005]
    fee_results = []
    for fee in fee_levels:
        res = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup, fee_rate=fee)
        fee_results.append({
            "fee_bps": round(fee * 10000),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        })
        print(f"    Fee {fee*10000:.0f}bps: Sharpe {res['sharpe']:.3f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")
    return fee_results


# =========================================================================
# 3. Walk-Forward OOS (6-fold rolling, 60% train / 40% test)
# =========================================================================

def run_walk_forward(closes, opens, volumes, up_def):
    """
    6-fold rolling walk-forward: 60% train / 40% test.
    For each fold, select best params on train, evaluate on test.
    Folds advance by test_size each step (rolling).
    """
    print(f"\n  Walk-Forward OOS: 6 folds (60% train / 40% test, rolling)")

    n = len(closes)
    total_window = n
    # 6 folds: each fold covers a window of size total_window, advancing by step
    # WF: split the entire period into 6 folds
    # Fold size: n // WF_FOLDS (each fold is a test segment)
    # Train: preceding 60% of the fold's available history
    # Test: the 40% test segment

    # Actually implement proper rolling WF:
    # Determine test segment size such that 6 folds fit
    # Each fold: train on T points (60%), test on T_test (40%), T_test = T * (40/60)
    # But use rolling windows:

    # Approach: divide total n into 6 folds of equal size (n/6 each).
    # For each fold i (0..5):
    #   test_start = fold_start = i * fold_size
    #   test_end   = (i+1) * fold_size
    #   train_size = int(fold_size * 1.5)  = 60% of 2.5 * fold_size
    #   Actually cleaner: fold_size = n * 0.4 / WF_FOLDS (test)
    #                      train_size = n * 0.6 from preceding data
    # Use standard approach from instructions: advancing by test_size, 60/40 split

    # Total window per fold = n (full period), train = 60%, test = 40%
    # But 6 folds rolling means each fold shifts by test_size
    # Simple interpretation: fold total = n // WF_FOLDS
    # ... but with 6 rolling folds of 60/40, the standard approach is:
    # - Full data = T days
    # - Each fold: test_size = T // 6 (approx), train_size = test_size * 1.5 (60/40 ratio)
    # - Fold 0: train [0, train_size), test [train_size, train_size + test_size)
    # - Fold 1: train [test_size, test_size + train_size), test [test_size + train_size, ...)
    # etc.

    fold_size = n // (WF_FOLDS + 1)   # rough chunk size
    test_size = fold_size
    train_size = int(test_size * 1.5)   # 60% train, 40% test ratio

    fold_results = []
    for fold in range(WF_FOLDS):
        test_start = train_size + fold * test_size
        test_end = test_start + test_size
        train_start = test_start - train_size

        if train_start < 0 or test_end > n:
            print(f"    Fold {fold+1}: insufficient data, skipping")
            continue

        train_closes  = closes.iloc[train_start:test_start]
        train_opens   = opens.iloc[train_start:test_start]
        train_volumes = volumes.iloc[train_start:test_start]
        test_closes   = closes.iloc[test_start:test_end]
        test_opens    = opens.iloc[test_start:test_end]
        test_volumes  = volumes.iloc[test_start:test_end]

        if len(train_closes) < 60 or len(test_closes) < 30:
            print(f"    Fold {fold+1}: too small (train {len(train_closes)}, test {len(test_closes)}), skipping")
            continue

        # Select best params on train
        best_sharpe = -999
        best_params = None
        for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
            warmup = lookback + 5
            if warmup >= len(train_closes) - 10:
                continue
            ranking = up_volume_ratio_factor(train_closes, train_opens, train_volumes, lookback, up_def)
            res = run_xs_factor(train_closes, ranking, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_params = (lookback, rebal, n_long)

        if best_params is None:
            print(f"    Fold {fold+1}: no valid params found")
            continue

        # Evaluate on test
        lb, rb, nl = best_params
        warmup = min(lb + 5, len(test_closes) // 2)
        test_ranking = up_volume_ratio_factor(test_closes, test_opens, test_volumes, lb, up_def)
        res_test = run_xs_factor(test_closes, test_ranking, rb, nl, warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "train_start": train_closes.index[0].strftime("%Y-%m-%d"),
            "train_end": train_closes.index[-1].strftime("%Y-%m-%d"),
            "test_start": test_closes.index[0].strftime("%Y-%m-%d"),
            "test_end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_train": len(train_closes),
            "n_test": len(test_closes),
            "train_best_params": f"L{lb}_R{rb}_N{nl}",
            "train_sharpe": round(best_sharpe, 3),
            "oos_sharpe": res_test["sharpe"],
            "oos_annual_ret": res_test["annual_ret"],
            "oos_max_dd": res_test["max_dd"],
        })
        print(f"    Fold {fold+1}: train {train_closes.index[0].date()}→{train_closes.index[-1].date()} "
              f"({len(train_closes)}d), test {test_closes.index[0].date()}→{test_closes.index[-1].date()} "
              f"({len(test_closes)}d)")
        print(f"           Best train: L{lb}_R{rb}_N{nl} (IS {best_sharpe:.3f}), "
              f"OOS Sharpe {res_test['sharpe']:.3f}, Ann {res_test['annual_ret']:.1%}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe"] > 0).sum()
    mean_oos = df["oos_sharpe"].mean()
    print(f"\n    Positive OOS folds: {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe: {mean_oos:.3f}")
    print(f"    Mean OOS Ann Return: {df['oos_annual_ret'].mean():.1%}")
    print(f"    Worst OOS DD: {df['oos_max_dd'].max():.1%}")
    return df


# =========================================================================
# 4. Split-Half Stability
# =========================================================================

def run_split_half(closes, opens, volumes, up_def):
    """Split data in half, compute Sharpe for each half, report correlation."""
    n = len(closes)
    mid = n // 2
    h1_c = closes.iloc[:mid]; h1_o = opens.iloc[:mid]; h1_v = volumes.iloc[:mid]
    h2_c = closes.iloc[mid:]; h2_o = opens.iloc[mid:]; h2_v = volumes.iloc[mid:]

    print(f"\n  Split-Half Stability")
    print(f"  Half 1: {h1_c.index[0].date()} to {h1_c.index[-1].date()} ({len(h1_c)} days)")
    print(f"  Half 2: {h2_c.index[0].date()} to {h2_c.index[-1].date()} ({len(h2_c)} days)")

    h1_sharpes = []
    h2_sharpes = []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_LONGS):
        warmup = lookback + 5
        r1 = up_volume_ratio_factor(h1_c, h1_o, h1_v, lookback, up_def)
        res1 = run_xs_factor(h1_c, r1, rebal, n_long, warmup=warmup)
        r2 = up_volume_ratio_factor(h2_c, h2_o, h2_v, lookback, up_def)
        res2 = run_xs_factor(h2_c, r2, rebal, n_long, warmup=warmup)
        h1_sharpes.append(res1["sharpe"])
        h2_sharpes.append(res2["sharpe"])

    arr1 = np.array(h1_sharpes)
    arr2 = np.array(h2_sharpes)
    corr = float(np.corrcoef(arr1, arr2)[0, 1])
    both_pos = int(((arr1 > 0) & (arr2 > 0)).sum())

    print(f"  Sharpe rank correlation between halves: {corr:.3f}")
    print(f"  Positive in both halves: {both_pos}/{len(arr1)} ({both_pos/len(arr1):.0%})")
    print(f"  Half 1 mean Sharpe: {arr1.mean():.3f}  |  Half 2 mean Sharpe: {arr2.mean():.3f}")

    return {
        "sharpe_correlation": round(corr, 3),
        "both_positive_pct": round(both_pos / len(arr1), 3),
        "half1_mean_sharpe": round(float(arr1.mean()), 3),
        "half2_mean_sharpe": round(float(arr2.mean()), 3),
    }


# =========================================================================
# 5. Correlation with H-012 (Momentum) and H-021 (Volume Momentum)
# =========================================================================

def compute_correlations(closes, opens, volumes, up_def, lookback, rebal, n_long):
    """
    Compute daily return correlation of H-111 vs:
      - H-012: 60d return momentum, 5d rebal, N=4
      - H-021: 5d/20d volume ratio, 3d rebal, N=4
    """
    print(f"\n  Factor Correlation Analysis (L{lookback}_R{rebal}_N{n_long})")

    # H-111
    ranking_111 = up_volume_ratio_factor(closes, opens, volumes, lookback, up_def)
    warmup_111 = lookback + 5
    res_111 = run_xs_factor(closes, ranking_111, rebal, n_long, warmup=warmup_111)
    rets_111 = res_111["equity"].pct_change().dropna()

    # H-012: 60d cross-sectional return momentum
    ranking_012 = closes.pct_change(60)
    res_012 = run_xs_factor(closes, ranking_012, 5, 4, warmup=65)
    rets_012 = res_012["equity"].pct_change().dropna()

    # H-021: 5d/20d volume ratio momentum
    vol_ratio_021 = (
        volumes.rolling(5, min_periods=5).mean() /
        volumes.rolling(20, min_periods=20).mean()
    )
    res_021 = run_xs_factor(closes, vol_ratio_021, 3, 4, warmup=25)
    rets_021 = res_021["equity"].pct_change().dropna()

    # Correlations
    idx_012 = rets_111.index.intersection(rets_012.index)
    idx_021 = rets_111.index.intersection(rets_021.index)

    corr_012 = float(rets_111.loc[idx_012].corr(rets_012.loc[idx_012])) if len(idx_012) >= 50 else float("nan")
    corr_021 = float(rets_111.loc[idx_021].corr(rets_021.loc[idx_021])) if len(idx_021) >= 50 else float("nan")

    print(f"  H-111 up-vol imbalance:  Sharpe {res_111['sharpe']:.3f}, Ann {res_111['annual_ret']:.1%}")
    print(f"  H-012 momentum (60d):    Sharpe {res_012['sharpe']:.3f}, Ann {res_012['annual_ret']:.1%}")
    print(f"  H-021 vol momentum:      Sharpe {res_021['sharpe']:.3f}, Ann {res_021['annual_ret']:.1%}")
    print(f"  Correlation H-111 vs H-012: {corr_012:.3f} {'(REDUNDANT)' if abs(corr_012) > 0.5 else '(independent)'}")
    print(f"  Correlation H-111 vs H-021: {corr_021:.3f} {'(REDUNDANT)' if abs(corr_021) > 0.5 else '(independent)'}")

    return {
        "h012_corr": round(corr_012, 3),
        "h021_corr": round(corr_021, 3),
        "h111_sharpe": res_111["sharpe"],
        "h012_sharpe": res_012["sharpe"],
        "h021_sharpe": res_021["sharpe"],
        "redundant_with_h012": abs(corr_012) > 0.5,
        "redundant_with_h021": abs(corr_021) > 0.5,
    }


# =========================================================================
# Compare up definitions (close > open vs close > prev_close)
# =========================================================================

def compare_up_definitions(closes, opens, volumes):
    """
    Run a quick scan with both up definitions on medium params to pick the better one.
    """
    print("\n  Comparing up-day definitions (quick scan over lookbacks, rebal=5, N=4)...")
    results = {}
    for up_def in ["close_vs_open", "close_vs_prev"]:
        sharpes = []
        for lookback in LOOKBACKS:
            ranking = up_volume_ratio_factor(closes, opens, volumes, lookback, up_def)
            res = run_xs_factor(closes, ranking, 5, 4, warmup=lookback + 5)
            sharpes.append(res["sharpe"])
        mean_s = float(np.mean(sharpes))
        results[up_def] = {"mean_sharpe": round(mean_s, 3), "sharpes": sharpes}
        print(f"    {up_def}: mean Sharpe {mean_s:.3f}  "
              f"(per lookback: {', '.join(f'{s:.3f}' for s in sharpes)})")
    better = max(results, key=lambda k: results[k]["mean_sharpe"])
    print(f"    -> Better definition: '{better}'")
    return better, results


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    print("H-111: Directional Volume Imbalance Factor")
    print("=" * 70)

    # ===== Load data =====
    print("\nLoading daily data...")
    daily = load_daily_data()

    if len(daily) < 10:
        print("Attempting ccxt fetch for missing assets...")
        missing = [s for s in ASSETS if s not in daily]
        fetched = fetch_via_ccxt(missing)
        daily.update(fetched)

    if len(daily) < 10:
        print(f"ERROR: Only {len(daily)} assets loaded. Need at least 10. Aborting.")
        sys.exit(1)

    print(f"\nLoaded {len(daily)} assets.")

    # Build aligned panels
    closes  = pd.DataFrame({sym: df["close"]  for sym, df in daily.items()})
    opens   = pd.DataFrame({sym: df["open"]   for sym, df in daily.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily.items()})

    closes  = closes.dropna(how="all").ffill().dropna()
    opens   = opens.reindex(closes.index).ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().fillna(0)

    # Align opens with closes (may have different missing patterns)
    common_idx = closes.index.intersection(opens.index)
    closes  = closes.loc[common_idx]
    opens   = opens.loc[common_idx]
    volumes = volumes.loc[common_idx]

    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")
    print(f"Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    n_days = len(closes)

    # ===== Compare up definitions =====
    better_def, def_comparison = compare_up_definitions(closes, opens, volumes)
    up_def = better_def

    # ===== 1. Full parameter scan =====
    scan_results = run_full_scan(closes, opens, volumes, up_def)

    # Best params
    best = scan_results.nlargest(1, "sharpe").iloc[0]
    best_lookback = int(best["lookback"])
    best_rebal    = int(best["rebal"])
    best_n_long   = int(best["n_long"])
    print(f"\n  Best full-period params: L{best_lookback}_R{best_rebal}_N{best_n_long}")
    print(f"  Sharpe: {best['sharpe']:.3f}, Ann Return: {best['annual_ret']:.1%}, "
          f"Max DD: {best['max_dd']:.1%}, Win Rate: {best['win_rate']:.1%}")

    # ===== 2. Parameter robustness =====
    pos_pct    = float((scan_results["sharpe"] > 0).mean())
    mean_sharpe   = float(scan_results["sharpe"].mean())
    median_sharpe = float(scan_results["sharpe"].median())
    print(f"\n  Parameter Robustness: {pos_pct:.0%} positive Sharpe "
          f"({int(pos_pct * len(scan_results))}/{len(scan_results)})")

    # ===== 3. Walk-Forward OOS =====
    wf_results = run_walk_forward(closes, opens, volumes, up_def)

    # ===== 4. Split-Half Stability =====
    split_half = run_split_half(closes, opens, volumes, up_def)

    # ===== 5. Correlations =====
    correlations = compute_correlations(closes, opens, volumes, up_def,
                                        best_lookback, best_rebal, best_n_long)

    # ===== 6. Fee Sensitivity =====
    print("\n  Fee Sensitivity:")
    fee_sensitivity = run_fee_sensitivity(closes, opens, volumes, up_def,
                                          best_lookback, best_rebal, best_n_long)

    # ===== Final Summary =====
    print("\n" + "=" * 70)
    print("FINAL SUMMARY: H-111 Directional Volume Imbalance Factor")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets | Period: {n_days} days "
          f"({closes.index[0].date()} to {closes.index[-1].date()})")
    print(f"  Best up-day definition: '{up_def}'")
    print(f"  Best params: L{best_lookback}_R{best_rebal}_N{best_n_long}")
    print()
    print(f"  1. In-Sample (full period):")
    print(f"     Sharpe {best['sharpe']:.3f} | Ann {best['annual_ret']:.1%} | "
          f"DD {best['max_dd']:.1%} | WR {best['win_rate']:.1%}")
    print()
    print(f"  2. Parameter Robustness:")
    print(f"     {pos_pct:.0%} params positive Sharpe ({int(pos_pct*len(scan_results))}/{len(scan_results)})")
    print(f"     Mean Sharpe {mean_sharpe:.3f} | Median {median_sharpe:.3f}")
    print()
    if wf_results is not None:
        wf_pos = int((wf_results["oos_sharpe"] > 0).sum())
        wf_mean = float(wf_results["oos_sharpe"].mean())
        print(f"  3. Walk-Forward OOS (6-fold rolling 60/40):")
        print(f"     {wf_pos}/{len(wf_results)} folds positive | Mean OOS Sharpe {wf_mean:.3f}")
        print(f"     IS→OOS transfer: IS {float(wf_results['train_sharpe'].mean()):.3f} → OOS {wf_mean:.3f}")
    print()
    print(f"  4. Split-Half Stability:")
    print(f"     Sharpe corr {split_half['sharpe_correlation']:.3f} | "
          f"Both positive {split_half['both_positive_pct']:.0%}")
    print(f"     H1 mean {split_half['half1_mean_sharpe']:.3f} | H2 mean {split_half['half2_mean_sharpe']:.3f}")
    print()
    print(f"  5. Factor Correlations:")
    print(f"     vs H-012 momentum:     {correlations['h012_corr']:.3f} "
          f"{'<REDUNDANT>' if correlations['redundant_with_h012'] else '(OK)'}")
    print(f"     vs H-021 vol momentum: {correlations['h021_corr']:.3f} "
          f"{'<REDUNDANT>' if correlations['redundant_with_h021'] else '(OK)'}")
    print()
    fee_01 = next((r for r in fee_sensitivity if r["fee_bps"] == 10), None)
    print(f"  6. Fee Sensitivity (10 bps one-way / 0.1% round-trip):")
    if fee_01:
        print(f"     Sharpe {fee_01['sharpe']:.3f} | Ann {fee_01['annual_ret']:.1%} | DD {fee_01['max_dd']:.1%}")
    print()

    # ===== Decision =====
    passes = []
    fails  = []
    if pos_pct >= 0.80:
        passes.append(f"Robustness: {pos_pct:.0%} >= 80% target")
    else:
        fails.append(f"Robustness: {pos_pct:.0%} < 80% target")

    if wf_results is not None and float(wf_results["oos_sharpe"].mean()) >= 1.0:
        passes.append(f"OOS Sharpe {float(wf_results['oos_sharpe'].mean()):.3f} >= 1.0")
    elif wf_results is not None:
        fails.append(f"OOS Sharpe {float(wf_results['oos_sharpe'].mean()):.3f} < 1.0")

    if split_half["sharpe_correlation"] >= 0.3:
        passes.append(f"Split-half corr {split_half['sharpe_correlation']:.3f} >= 0.3")
    else:
        fails.append(f"Split-half corr {split_half['sharpe_correlation']:.3f} < 0.3")

    if not correlations["redundant_with_h012"] and not correlations["redundant_with_h021"]:
        passes.append("Not redundant with H-012 or H-021")
    else:
        if correlations["redundant_with_h012"]:
            fails.append(f"REDUNDANT with H-012 (corr {correlations['h012_corr']:.3f})")
        if correlations["redundant_with_h021"]:
            fails.append(f"REDUNDANT with H-021 (corr {correlations['h021_corr']:.3f})")

    print(f"  Decision:")
    for p in passes:
        print(f"    PASS: {p}")
    for f in fails:
        print(f"    FAIL: {f}")

    if len(fails) == 0:
        verdict = "CONFIRMED"
    elif len(fails) <= 1 and len(passes) >= 3:
        verdict = "CONDITIONAL"
    else:
        verdict = "REJECTED"
    print(f"\n  VERDICT: {verdict}")

    # ===== Save results =====
    results_dir = Path(__file__).parent
    results_dir.mkdir(parents=True, exist_ok=True)

    results_data = {
        "hypothesis": "H-111",
        "name": "Directional Volume Imbalance Factor",
        "description": "Cross-sectional factor: long accumulation (high up-vol ratio), short distribution (low up-vol ratio)",
        "verdict": verdict,
        "fee_rate_bps_one_way": FEE_RATE * 10000,
        "universe_size": int(len(closes.columns)),
        "n_days": int(n_days),
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "up_def_chosen": up_def,
        "up_def_comparison": {k: v["mean_sharpe"] for k, v in def_comparison.items()},
        "full_scan": {
            "n_combos": int(len(scan_results)),
            "pct_positive_sharpe": round(pos_pct, 3),
            "mean_sharpe": round(mean_sharpe, 3),
            "median_sharpe": round(median_sharpe, 3),
            "best_params": f"L{best_lookback}_R{best_rebal}_N{best_n_long}",
            "best_sharpe": float(best["sharpe"]),
            "best_annual_ret": float(best["annual_ret"]),
            "best_max_dd": float(best["max_dd"]),
            "best_win_rate": float(best["win_rate"]),
            "best_n_trades": int(best["n_trades"]),
            "all_results": scan_results.to_dict("records"),
        },
        "parameter_robustness": {
            "pct_positive_sharpe": round(pos_pct, 3),
            "mean_sharpe": round(mean_sharpe, 3),
            "median_sharpe": round(median_sharpe, 3),
        },
        "walk_forward": {
            "n_folds": int(len(wf_results)) if wf_results is not None else 0,
            "positive_folds": int((wf_results["oos_sharpe"] > 0).sum()) if wf_results is not None else 0,
            "mean_oos_sharpe": round(float(wf_results["oos_sharpe"].mean()), 3) if wf_results is not None else None,
            "mean_oos_annual_ret": round(float(wf_results["oos_annual_ret"].mean()), 4) if wf_results is not None else None,
            "worst_oos_dd": round(float(wf_results["oos_max_dd"].max()), 4) if wf_results is not None else None,
            "folds": wf_results.to_dict("records") if wf_results is not None else [],
        },
        "split_half": split_half,
        "correlations": correlations,
        "fee_sensitivity": fee_sensitivity,
        "passes": passes,
        "fails": fails,
    }

    results_file = results_dir / "results.json"
    with open(results_file, "w") as f:
        json.dump(results_data, f, indent=2, default=str)
    print(f"\n  Results saved to {results_file}")
    print("=" * 70)
