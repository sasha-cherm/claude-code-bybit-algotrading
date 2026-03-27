"""
H-106: Volume Profile Skewness Factor (Cross-Sectional)

Compute rolling skewness of daily trading volume for each asset.
- Momentum direction: long highest skew (burst-driven), short lowest skew
- Contrarian direction: short highest skew, long lowest skew

Validation: full 72-combo param scan (both directions), 60/40 train/test,
6-fold walk-forward (90-day test windows), split-half OOS consistency,
correlation with H-012 (momentum) and H-031 (size/mcap via price level proxy).

Rejection criteria (any one = REJECT):
  - < 60% params positive in best direction
  - Split-half Sharpe correlation negative
  - Walk-forward selected-params mean Sharpe < 0.5
  - Correlation with H-012 or H-031 > 0.5
  - OOS Sharpe < 0.3

Fee: 0.06% round-trip (6 bps)
Sharpe: daily mean / daily std * sqrt(365)
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd
from scipy.stats import skew as scipy_skew

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.0006       # 0.06% round-trip
INITIAL_CAPITAL = 10_000.0

# Parameter grid per direction
LOOKBACKS   = [10, 20, 30, 60]   # volume skewness rolling window
REBAL_FREQS = [5, 7, 10]         # rebalance every N days
N_SIZES     = [3, 4, 5]          # top/bottom N
# 4 × 3 × 3 = 36 combos per direction, 72 total

# Walk-forward
WF_FOLDS = 6
WF_TRAIN  = 300
WF_TEST   = 90
WF_STEP   = 90


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Rolling skewness of volume
# ---------------------------------------------------------------------------

def rolling_vol_skewness(volumes: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    Compute rolling skewness of daily volume for each asset.
    Uses scipy.stats.skew (Fisher, bias=False) over a rolling window.
    Returns DataFrame with same shape as `volumes`.

    Higher value = more right-skewed (occasional large spikes relative to baseline).
    """
    result = pd.DataFrame(np.nan, index=volumes.index, columns=volumes.columns)
    for sym in volumes.columns:
        vol = volumes[sym].values.astype(float)
        n = len(vol)
        skew_vals = np.full(n, np.nan)
        for i in range(lookback - 1, n):
            window = vol[i - lookback + 1 : i + 1]
            valid = window[~np.isnan(window)]
            if len(valid) < 4:
                continue
            std_v = valid.std(ddof=1)
            if std_v < 1e-15:
                skew_vals[i] = 0.0
                continue
            # Fisher skewness (unbiased)
            nn = len(valid)
            m = valid.mean()
            skew_vals[i] = scipy_skew(valid, bias=False)
        result[sym] = skew_vals
    return result


# Cache to avoid recomputing identical lookbacks
_skew_cache: dict = {}

def get_vol_skew(volumes: pd.DataFrame, lookback: int) -> pd.DataFrame:
    key = (id(volumes), lookback)
    if key not in _skew_cache:
        _skew_cache[key] = rolling_vol_skewness(volumes, lookback)
    return _skew_cache[key]


# ---------------------------------------------------------------------------
# Metrics helper
# ---------------------------------------------------------------------------

def compute_metrics(equity_series: pd.Series) -> dict:
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99, "annual_ret": 0.0, "max_dd": 1.0, "win_rate": 0.0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    # TRUE daily Sharpe: mean/std * sqrt(365)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(365)) if rets.std() > 0 else 0.0
    return {
        "sharpe": round(sharpe, 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "win_rate": round(n_pos / n_total, 4) if n_total > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Core back-test engine
# ---------------------------------------------------------------------------

def run_xs_factor(
    closes: pd.DataFrame,
    volumes: pd.DataFrame,
    lookback: int,
    rebal_freq: int,
    n_long: int,
    direction: int,  # +1 = long high skew; -1 = long low skew (contrarian)
    n_short: int | None = None,
    warmup: int | None = None,
) -> dict:
    """
    Cross-sectional strategy using volume-skewness ranking.

    direction=+1  → Momentum: long highest skew, short lowest skew
    direction=-1  → Contrarian: long lowest skew, short highest skew
    """
    if n_short is None:
        n_short = n_long
    if warmup is None:
        warmup = lookback + 5

    skew_df = get_vol_skew(volumes, lookback)

    n = len(closes)
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count = 0

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        # Use log returns to handle large price differences cleanly
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = skew_df.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # direction=+1: long top (high skew), short bottom (low skew)
            # direction=-1: long bottom (low skew), short top (high skew)
            ranked = valid.sort_values(ascending=False)
            if direction == 1:
                longs  = ranked.index[:n_long]
                shorts = ranked.index[-n_short:]
            else:
                longs  = ranked.index[-n_long:]
                shorts = ranked.index[:n_short]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] =  1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover       = weight_changes.sum() / 2.0
            fee_drag       = turnover * FEE_RATE

            port_ret = (new_weights * log_rets).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count  += 1
            prev_weights  = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"]     = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"]       = eq_series
    return metrics


# ---------------------------------------------------------------------------
# Full parameter scan (both directions)
# ---------------------------------------------------------------------------

def run_full_scan(closes: pd.DataFrame, volumes: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-106: VOLUME PROFILE SKEWNESS FACTOR -- Full Param Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per trade")

    # Pre-compute skewness for all lookbacks once
    for lb in LOOKBACKS:
        get_vol_skew(volumes, lb)
        print(f"  Computed vol-skewness for lookback={lb}")

    results = {"momentum": [], "contrarian": []}

    for direction, label in [(1, "momentum"), (-1, "contrarian")]:
        for lookback, rebal, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
            warmup = lookback + 5
            res = run_xs_factor(closes, volumes, lookback, rebal, n,
                                direction=direction, warmup=warmup)
            tag = f"LB{lookback}_R{rebal}_N{n}"
            results[label].append({
                "tag": tag, "lookback": lookback, "rebal": rebal, "n": n,
                "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
                "max_dd": res["max_dd"], "win_rate": res["win_rate"],
                "n_trades": res["n_trades"],
            })

    for label in ["momentum", "contrarian"]:
        df = pd.DataFrame(results[label])
        pos_pct = (df["sharpe"] > 0).mean()
        print(f"\n  [{label.upper()}]")
        print(f"    Combos: {len(df)}, Positive Sharpe: {(df['sharpe']>0).sum()}/{len(df)} ({pos_pct:.0%})")
        print(f"    Mean Sharpe: {df['sharpe'].mean():.3f}, Median: {df['sharpe'].median():.3f}")
        print(f"    Best Sharpe: {df['sharpe'].max():.3f}, Worst: {df['sharpe'].min():.3f}")
        print(f"    Top 5:")
        for _, row in df.nlargest(5, "sharpe").iterrows():
            print(f"      {row['tag']}: Sharpe {row['sharpe']:.3f}, "
                  f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")
        results[label] = df

    # Decide best direction
    m_mean = results["momentum"]["sharpe"].mean()
    c_mean = results["contrarian"]["sharpe"].mean()
    best_dir_label = "momentum" if m_mean >= c_mean else "contrarian"
    best_dir_val   = 1 if best_dir_label == "momentum" else -1
    print(f"\n  Best direction: {best_dir_label.upper()} "
          f"(mean Sharpe {results[best_dir_label]['sharpe'].mean():.3f} vs "
          f"{results['contrarian' if best_dir_label=='momentum' else 'momentum']['sharpe'].mean():.3f})")

    return results, best_dir_label, best_dir_val


# ---------------------------------------------------------------------------
# 60/40 Train / Test split
# ---------------------------------------------------------------------------

def run_train_test(closes: pd.DataFrame, volumes: pd.DataFrame,
                   best_dir_val: int, best_dir_label: str):
    n = len(closes)
    split = int(n * 0.60)
    train_c = closes.iloc[:split]
    test_c  = closes.iloc[split:]
    train_v = volumes.iloc[:split]
    test_v  = volumes.iloc[split:]

    print(f"\n  60/40 Train/Test Split  ({best_dir_label.upper()} direction)")
    print(f"    Train: {train_c.index[0].date()} to {train_c.index[-1].date()} ({len(train_c)} days)")
    print(f"    Test : {test_c.index[0].date()} to {test_c.index[-1].date()} ({len(test_c)} days)")

    # Select best params on train
    best_sharpe = -999.0
    best_params = None
    _skew_cache.clear()  # invalidate cache for different sub-dataframes
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = lookback + 5
        if warmup >= len(train_c) - 30:
            continue
        res = run_xs_factor(train_c, train_v, lookback, rebal, n_long,
                            direction=best_dir_val, warmup=warmup)
        if res["sharpe"] > best_sharpe:
            best_sharpe = res["sharpe"]
            best_params = (lookback, rebal, n_long)

    lb, rb, n_long = best_params
    print(f"    Train best: LB{lb}_R{rb}_N{n_long} (IS Sharpe {best_sharpe:.3f})")

    _skew_cache.clear()
    res_test = run_xs_factor(test_c, test_v, lb, rb, n_long,
                             direction=best_dir_val, warmup=lb + 5)
    print(f"    Test result: Sharpe {res_test['sharpe']:.3f}, "
          f"Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}, "
          f"n_days={len(test_c)}")

    # OOS split-half (within the test set)
    n_test = len(test_c)
    mid = n_test // 2
    _skew_cache.clear()
    r1 = run_xs_factor(test_c.iloc[:mid], test_v.iloc[:mid], lb, rb, n_long,
                       direction=best_dir_val, warmup=lb + 5)
    _skew_cache.clear()
    r2 = run_xs_factor(test_c.iloc[mid:], test_v.iloc[mid:], lb, rb, n_long,
                       direction=best_dir_val, warmup=lb + 5)
    print(f"    OOS half-1 Sharpe: {r1['sharpe']:.3f}, OOS half-2 Sharpe: {r2['sharpe']:.3f}")

    return {
        "train_best_params": f"LB{lb}_R{rb}_N{n_long}",
        "train_sharpe": round(best_sharpe, 3),
        "oos_sharpe": res_test["sharpe"],
        "oos_annual_ret": res_test["annual_ret"],
        "oos_max_dd": res_test["max_dd"],
        "oos_n_days": len(test_c),
        "oos_half1_sharpe": r1["sharpe"],
        "oos_half2_sharpe": r2["sharpe"],
        "best_lb": lb, "best_rb": rb, "best_n": n_long,
    }


# ---------------------------------------------------------------------------
# Walk-forward with parameter selection
# ---------------------------------------------------------------------------

def run_walk_forward(closes: pd.DataFrame, volumes: pd.DataFrame,
                     best_dir_val: int):
    print(f"\n  Walk-Forward (6 folds × 90-day test windows, IS=300d)")
    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end   = n - fold * WF_STEP
        test_start = test_end - WF_TEST
        train_start= test_start - WF_TRAIN
        if train_start < 0 or test_start < 0 or test_end > n:
            break

        train_c = closes.iloc[train_start:test_start]
        test_c  = closes.iloc[test_start:test_end]
        train_v = volumes.iloc[train_start:test_start]
        test_v  = volumes.iloc[test_start:test_end]

        if len(test_c) < 30 or len(train_c) < 100:
            break

        _skew_cache.clear()
        best_s = -999.0
        best_p = None
        for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
            warmup = lookback + 5
            if warmup >= len(train_c) - 20:
                continue
            res = run_xs_factor(train_c, train_v, lookback, rebal, n_long,
                                direction=best_dir_val, warmup=warmup)
            if res["sharpe"] > best_s:
                best_s = res["sharpe"]
                best_p = (lookback, rebal, n_long)

        if best_p is None:
            break
        lb, rb, n_long = best_p
        _skew_cache.clear()
        res = run_xs_factor(test_c, test_v, lb, rb, n_long,
                            direction=best_dir_val, warmup=min(lb + 5, len(test_c) // 2))

        fold_results.append({
            "fold": fold + 1,
            "test_start": test_c.index[0].strftime("%Y-%m-%d"),
            "test_end": test_c.index[-1].strftime("%Y-%m-%d"),
            "train_params": f"LB{lb}_R{rb}_N{n_long}",
            "train_sharpe": round(best_s, 3),
            "oos_sharpe": res["sharpe"],
            "oos_ann_ret": res["annual_ret"],
        })
        print(f"    Fold {fold+1}: {test_c.index[0].date()} → {test_c.index[-1].date()} "
              f"| IS best LB{lb}_R{rb}_N{n_long} ({best_s:.3f}) "
              f"| OOS {res['sharpe']:.3f}")

    if not fold_results:
        return None
    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe"] > 0).sum()
    mean_oos = df["oos_sharpe"].mean()
    print(f"    Positive OOS folds: {pos}/{len(df)},  Mean OOS Sharpe: {mean_oos:.3f}")
    return df


# ---------------------------------------------------------------------------
# Split-half consistency across ALL params
# ---------------------------------------------------------------------------

def run_split_half(closes: pd.DataFrame, volumes: pd.DataFrame,
                   best_dir_val: int, best_dir_label: str):
    n = len(closes)
    mid = n // 2
    c1, c2 = closes.iloc[:mid], closes.iloc[mid:]
    v1, v2 = volumes.iloc[:mid], volumes.iloc[mid:]

    print(f"\n  Split-Half Consistency  ({best_dir_label.upper()})")
    print(f"    Half1: {c1.index[0].date()} to {c1.index[-1].date()} ({len(c1)} days)")
    print(f"    Half2: {c2.index[0].date()} to {c2.index[-1].date()} ({len(c2)} days)")

    h1_sharpes, h2_sharpes = [], []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = lookback + 5
        _skew_cache.clear()
        r1 = run_xs_factor(c1, v1, lookback, rebal, n_long,
                           direction=best_dir_val, warmup=warmup)
        _skew_cache.clear()
        r2 = run_xs_factor(c2, v2, lookback, rebal, n_long,
                           direction=best_dir_val, warmup=warmup)
        h1_sharpes.append(r1["sharpe"])
        h2_sharpes.append(r2["sharpe"])

    h1 = np.array(h1_sharpes)
    h2 = np.array(h2_sharpes)
    corr = float(np.corrcoef(h1, h2)[0, 1])
    both_pos = int(((h1 > 0) & (h2 > 0)).sum())
    print(f"    Sharpe rank-corr between halves: {corr:.3f}")
    print(f"    Positive in both halves: {both_pos}/{len(h1)} ({both_pos/len(h1):.0%})")
    print(f"    Half1 mean Sharpe: {h1.mean():.3f}, Half2 mean Sharpe: {h2.mean():.3f}")

    return {
        "sharpe_correlation": round(corr, 3),
        "both_positive_pct": round(both_pos / len(h1), 3),
        "half1_mean_sharpe": round(float(h1.mean()), 3),
        "half2_mean_sharpe": round(float(h2.mean()), 3),
    }


# ---------------------------------------------------------------------------
# Correlation with H-012 (cross-sectional momentum) and H-031 (size factor)
# ---------------------------------------------------------------------------

def _run_uncached(closes, volumes, lookback, rebal, n_long, direction):
    """Run factor with a fresh skew computation (no cache)."""
    _skew_cache.clear()
    return run_xs_factor(closes, volumes, lookback, rebal, n_long,
                         direction=direction, warmup=lookback + 5)

def compute_factor_correlations(closes: pd.DataFrame, volumes: pd.DataFrame,
                                 best_lb: int, best_rb: int, best_n: int,
                                 best_dir_val: int):
    print(f"\n  Factor Correlations")

    # Compute H-106 returns
    _skew_cache.clear()
    res_h106 = run_xs_factor(closes, volumes, best_lb, best_rb, best_n,
                              direction=best_dir_val, warmup=best_lb + 5)
    rets_h106 = res_h106["equity"].pct_change().dropna()

    # H-012: 60-day cross-sectional momentum (long top-4 momentum, short bottom-4)
    _skew_cache.clear()
    mom60 = closes.pct_change(60)
    # Run without volume needed — reuse xs engine but pass closes as the ranking signal
    # We implement inline to avoid circular dependency issues
    def run_mom(closes_inner, ranking_inner, rebal_f=5, n_l=4, warmup_i=65):
        n = len(closes_inner)
        eq = np.zeros(n)
        eq[0] = INITIAL_CAPITAL
        pw = pd.Series(0.0, index=closes_inner.columns)
        for i in range(1, n):
            lret = np.log(closes_inner.iloc[i] / closes_inner.iloc[i - 1])
            if i >= warmup_i and (i - warmup_i) % rebal_f == 0:
                ranks = ranking_inner.iloc[i - 1].dropna()
                if len(ranks) < n_l * 2:
                    eq[i] = eq[i - 1] * np.exp((pw * lret).sum())
                    continue
                ranked = ranks.sort_values(ascending=False)
                new_w = pd.Series(0.0, index=closes_inner.columns)
                for s in ranked.index[:n_l]:
                    new_w[s] = 1.0 / n_l
                for s in ranked.index[-n_l:]:
                    new_w[s] = -1.0 / n_l
                wc = (new_w - pw).abs()
                fee = wc.sum() / 2.0 * FEE_RATE
                eq[i] = eq[i - 1] * np.exp((new_w * lret).sum() - fee)
                pw = new_w
            else:
                eq[i] = eq[i - 1] * np.exp((pw * lret).sum())
        return pd.Series(eq, index=closes_inner.index).pct_change().dropna()

    rets_h012 = run_mom(closes, mom60, rebal_f=5, n_l=4, warmup_i=65)

    # H-031: Size factor proxy — rank by 90-day average daily volume (large = short, small = long)
    # (large-cap assets by trading volume tend to underperform small-cap)
    vol_size = volumes.rolling(90).mean()
    rets_h031 = run_mom(closes, -vol_size, rebal_f=7, n_l=4, warmup_i=95)

    common_12 = rets_h106.index.intersection(rets_h012.index)
    common_31 = rets_h106.index.intersection(rets_h031.index)

    corr_12 = float(rets_h106.loc[common_12].corr(rets_h012.loc[common_12])) if len(common_12) > 50 else 0.0
    corr_31 = float(rets_h106.loc[common_31].corr(rets_h031.loc[common_31])) if len(common_31) > 50 else 0.0

    print(f"    Correlation with H-012 (XS Momentum):  {corr_12:.3f}")
    print(f"    Correlation with H-031 (Size/Volume):  {corr_31:.3f}")

    return round(corr_12, 3), round(corr_31, 3)


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("H-106: Volume Profile Skewness Factor")
    print("=" * 72)

    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")
    if len(daily) < 10:
        print("ERROR: Not enough assets. Aborting.")
        sys.exit(1)

    closes  = pd.DataFrame({sym: df["close"]  for sym, df in daily.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily.items()})
    closes  = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().fillna(0.0)
    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")

    # -----------------------------------------------------------------------
    # 1. Full scan — both directions
    # -----------------------------------------------------------------------
    _skew_cache.clear()
    scan_results, best_dir_label, best_dir_val = run_full_scan(closes, volumes)
    best_dir_df = scan_results[best_dir_label]

    pos_pct_best = (best_dir_df["sharpe"] > 0).mean()
    best_row     = best_dir_df.nlargest(1, "sharpe").iloc[0]
    best_lb      = int(best_row["lookback"])
    best_rb      = int(best_row["rebal"])
    best_n       = int(best_row["n"])

    print(f"\n  Best params ({best_dir_label}): LB{best_lb}_R{best_rb}_N{best_n}"
          f", Sharpe {best_row['sharpe']:.3f}")
    print(f"  Positive params in best direction: {pos_pct_best:.0%}")

    # -----------------------------------------------------------------------
    # 2. 60/40 Train/Test + split-half within OOS
    # -----------------------------------------------------------------------
    _skew_cache.clear()
    tt = run_train_test(closes, volumes, best_dir_val, best_dir_label)

    # -----------------------------------------------------------------------
    # 3. Walk-forward (6 folds)
    # -----------------------------------------------------------------------
    _skew_cache.clear()
    wf = run_walk_forward(closes, volumes, best_dir_val)

    # -----------------------------------------------------------------------
    # 4. Split-half consistency across all params
    # -----------------------------------------------------------------------
    _skew_cache.clear()
    sh = run_split_half(closes, volumes, best_dir_val, best_dir_label)

    # -----------------------------------------------------------------------
    # 5. Factor correlations
    # -----------------------------------------------------------------------
    _skew_cache.clear()
    corr_12, corr_31 = compute_factor_correlations(
        closes, volumes, tt["best_lb"], tt["best_rb"], tt["best_n"], best_dir_val
    )

    # -----------------------------------------------------------------------
    # 6. Walk-forward mean OOS Sharpe
    # -----------------------------------------------------------------------
    wf_mean_sharpe = wf["oos_sharpe"].mean() if wf is not None else -99.0

    # -----------------------------------------------------------------------
    # 7. Final verdict
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("SUMMARY: H-106 Volume Profile Skewness Factor")
    print("=" * 72)
    print(f"  Best direction         : {best_dir_label.upper()}")
    print(f"  Param combos (best dir): {len(best_dir_df)}")
    print(f"  % Params positive      : {pos_pct_best:.0%}   (threshold ≥60%)")
    print(f"  Mean Sharpe (all params): {best_dir_df['sharpe'].mean():.3f}")
    print(f"  Best Sharpe (full data) : {best_row['sharpe']:.3f}")
    print(f"  Best params            : LB{best_lb}_R{best_rb}_N{best_n}")
    print()
    print(f"  IS Sharpe              : {tt['train_sharpe']:.3f}")
    print(f"  OOS Sharpe (60/40)     : {tt['oos_sharpe']:.3f}   (threshold ≥0.3)")
    print(f"  OOS Ann Return         : {tt['oos_annual_ret']:.1%}")
    print(f"  OOS Max Drawdown       : {tt['oos_max_dd']:.1%}")
    print(f"  OOS test days          : {tt['oos_n_days']}")
    print()
    print(f"  OOS Half1 Sharpe       : {tt['oos_half1_sharpe']:.3f}")
    print(f"  OOS Half2 Sharpe       : {tt['oos_half2_sharpe']:.3f}")
    print(f"  Split-half corr (all)  : {sh['sharpe_correlation']:.3f}   (threshold >0)")
    print(f"  Both halves positive   : {sh['both_positive_pct']:.0%}")
    print()
    if wf is not None:
        print(f"  Walk-forward folds     : {len(wf)}")
        print(f"  WF mean OOS Sharpe     : {wf_mean_sharpe:.3f}   (threshold ≥0.5)")
        print(f"  WF positive folds      : {(wf['oos_sharpe']>0).sum()}/{len(wf)}")
    print()
    print(f"  Corr w/ H-012 (momentum): {corr_12:.3f}  (threshold <0.5)")
    print(f"  Corr w/ H-031 (size)    : {corr_31:.3f}  (threshold <0.5)")
    print()

    # Apply rejection criteria
    reasons = []
    if pos_pct_best < 0.60:
        reasons.append(f"< 60% params positive ({pos_pct_best:.0%})")
    if sh["sharpe_correlation"] <= 0:
        reasons.append(f"split-half corr non-positive ({sh['sharpe_correlation']:.3f})")
    if wf_mean_sharpe < 0.5:
        reasons.append(f"WF mean OOS Sharpe < 0.5 ({wf_mean_sharpe:.3f})")
    if abs(corr_12) > 0.5:
        reasons.append(f"corr with H-012 > 0.5 ({corr_12:.3f})")
    if abs(corr_31) > 0.5:
        reasons.append(f"corr with H-031 > 0.5 ({corr_31:.3f})")
    if tt["oos_sharpe"] < 0.3:
        reasons.append(f"OOS Sharpe < 0.3 ({tt['oos_sharpe']:.3f})")

    if reasons:
        verdict = "REJECTED"
        print(f"  VERDICT: REJECTED")
        for r in reasons:
            print(f"    Reason: {r}")
    else:
        verdict = "CONFIRMED"
        print(f"  VERDICT: CONFIRMED")

    # Save results
    results_out = {
        "hypothesis": "H-106",
        "verdict": verdict,
        "rejection_reasons": reasons,
        "best_direction": best_dir_label,
        "best_params": f"LB{tt['best_lb']}_R{tt['best_rb']}_N{tt['best_n']}",
        "pos_pct_best_dir": round(float(pos_pct_best), 3),
        "mean_sharpe_best_dir": round(float(best_dir_df["sharpe"].mean()), 3),
        "best_full_sharpe": round(float(best_row["sharpe"]), 3),
        "oos_sharpe": tt["oos_sharpe"],
        "oos_annual_ret": tt["oos_annual_ret"],
        "oos_max_dd": tt["oos_max_dd"],
        "oos_half1_sharpe": tt["oos_half1_sharpe"],
        "oos_half2_sharpe": tt["oos_half2_sharpe"],
        "split_half_corr": sh["sharpe_correlation"],
        "wf_mean_oos_sharpe": round(float(wf_mean_sharpe), 3),
        "corr_h012": corr_12,
        "corr_h031": corr_31,
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(results_out, f, indent=2)
    print(f"\n  Results saved to {out_path}")
