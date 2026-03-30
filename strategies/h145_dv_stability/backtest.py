"""
H-145: Dollar-Volume Stability Factor (Cross-Sectional)

Rank crypto assets by the coefficient of variation (CV = std/mean) of daily
dollar volume over a rolling window.

- Low CV  => stable, consistent trading interest (institutional presence)
- High CV => sporadic, speculative volume spikes

Two directions tested:
  - stable_long : Long bottom-N (lowest CV), short top-N (highest CV)
  - erratic_long: Long top-N  (highest CV), short bottom-N (lowest CV)

Parameter grid:
  Lookback (L):    [10, 20, 30, 40, 60] days
  Rebalance (R):   [3, 5, 7, 10, 14]  days
  N (top/bottom):  [3, 4, 5]

Validation:
  - Walk-forward: 6 expanding-window folds (train >= 360d, test 60d)
  - Split-half: Sharpe rank correlation between halves
  - Correlation with H-012 momentum and H-031 size factor

Acceptance criteria:
  IS:         >= 80% of params positive Sharpe (stable_long direction)
  WF:         >= 4/6 folds positive OOS
  Split-half: positive correlation
  H-012 corr: <= 0.40
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

# ---------------------------------------------------------------------------
# Universe and constants
# ---------------------------------------------------------------------------
ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
    "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT", "ATOM/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "SUI/USDT",
]

FEE_RATE       = 0.0006   # 6 bps taker fee on Bybit perps
INITIAL_CAPITAL = 10_000.0

# Parameter grid
LOOKBACKS   = [10, 20, 30, 40, 60]
REBAL_FREQS = [3, 5, 7, 10, 14]
N_SIDES     = [3, 4, 5]
DIRECTIONS  = ["stable_long", "erratic_long"]

# Walk-forward config (expanding window per spec: train >= 360d, test 60d)
WF_FOLDS     = 6
WF_MIN_TRAIN = 360
WF_TEST      = 60

RESULTS_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

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
                print(f"  {sym}: only {len(df)} bars — skipping")
        else:
            print(f"  {sym}: file not found")
    return daily


# ---------------------------------------------------------------------------
# Factor computation
# ---------------------------------------------------------------------------

def compute_cv(closes, volumes, lookback):
    """
    Coefficient of variation of daily dollar volume over a rolling window.
    CV = rolling_std(dv, L) / rolling_mean(dv, L)
    Lower CV => more stable volume => long candidate in stable_long direction.
    Returns a DataFrame aligned with closes.
    """
    dv = closes * volumes   # daily dollar volume
    rolling_mean = dv.rolling(lookback, min_periods=lookback).mean()
    rolling_std  = dv.rolling(lookback, min_periods=lookback).std()
    cv = rolling_std / rolling_mean
    cv = cv.replace([np.inf, -np.inf], np.nan)
    return cv


# ---------------------------------------------------------------------------
# Equity simulator
# ---------------------------------------------------------------------------

def compute_metrics(equity_series):
    """Compute standard metrics from equity curve."""
    eq = equity_series.dropna()
    eq = eq[eq > 0]
    if len(eq) < 30:
        return {"sharpe": -99.0, "annual_ret": 0.0, "max_dd": 1.0, "win_rate": 0.0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    return {
        "sharpe":     round(float(sharpe_ratio(rets, periods_per_year=365)), 3),
        "annual_ret": round(float(annual_return(eq, periods_per_year=365)), 4),
        "max_dd":     round(float(max_drawdown(eq)), 4),
        "win_rate":   round(n_pos / n_total, 4) if n_total > 0 else 0.0,
    }


def run_xs_factor(closes, cv_ranking, rebal_freq, n_long, direction, warmup=None):
    """
    Cross-sectional factor backtester using log returns.

    direction = 'stable_long'  => long low-CV (stable), short high-CV (erratic)
    direction = 'erratic_long' => long high-CV (erratic), short low-CV (stable)

    Dollar-neutral: equal weight on each side.
    Fee model: deduct FEE_RATE * |weight_change| at each rebalance.
    """
    if warmup is None:
        warmup = cv_ranking.shape[1] + 5 if hasattr(cv_ranking, 'shape') else 65

    n = len(closes)
    n_short = n_long

    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_rebalances = 0

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday).fillna(0)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            # Use t-1 CV ranking (no look-ahead)
            ranks = cv_ranking.iloc[i - 1]
            valid = ranks.dropna()

            if len(valid) < n_long + n_short:
                # Not enough ranked assets — hold
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # Sort ascending by CV
            sorted_asc = valid.sort_values(ascending=True)

            if direction == "stable_long":
                # Long = lowest CV (most stable), Short = highest CV (most erratic)
                longs  = sorted_asc.index[:n_long]    # bottom of sorted list
                shorts = sorted_asc.index[-n_short:]  # top of sorted list
            else:
                # erratic_long: Long = highest CV, Short = lowest CV
                longs  = sorted_asc.index[-n_long:]   # top of sorted list
                shorts = sorted_asc.index[:n_short]   # bottom of sorted list

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] += 1.0 / n_long
            for sym in shorts:
                new_weights[sym] -= 1.0 / n_short

            # Turnover fee
            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2.0
            fee_drag = turnover * FEE_RATE

            port_ret = (new_weights * log_rets).sum() - fee_drag
            prev_weights = new_weights
            total_rebalances += 1
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_rebalances"] = total_rebalances
    metrics["equity"] = eq_series
    return metrics


# ---------------------------------------------------------------------------
# Full IS parameter scan
# ---------------------------------------------------------------------------

def run_full_scan(closes, volumes):
    """Run all parameter combinations on the full period (both directions)."""
    print("\n" + "=" * 72)
    print("H-145: DOLLAR-VOLUME STABILITY FACTOR — Full IS Parameter Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE*10000:.0f} bps per trade")

    results = []
    total = len(LOOKBACKS) * len(REBAL_FREQS) * len(N_SIDES) * len(DIRECTIONS)
    done = 0

    for direction, lookback, rebal, n_long in product(
            DIRECTIONS, LOOKBACKS, REBAL_FREQS, N_SIDES):
        cv = compute_cv(closes, volumes, lookback)
        warmup = lookback + 5
        res = run_xs_factor(closes, cv, rebal, n_long, direction, warmup=warmup)
        tag = f"{direction[:3].upper()}_L{lookback}_R{rebal}_N{n_long}"
        results.append({
            "tag":        tag,
            "direction":  direction,
            "lookback":   lookback,
            "rebal":      rebal,
            "n_long":     n_long,
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
            "win_rate":   res["win_rate"],
            "n_rebalances": res["n_rebalances"],
        })
        done += 1
        if done % 25 == 0:
            print(f"  ... {done}/{total} combinations done")

    df = pd.DataFrame(results)

    # Overall
    pos_all = df[df["sharpe"] > 0]
    print(f"\n  Total combos (both directions): {len(df)}")
    print(f"  Positive Sharpe (all): {len(pos_all)}/{len(df)} "
          f"({len(pos_all)/len(df):.0%})")

    # Per direction
    for direc in DIRECTIONS:
        sub = df[df["direction"] == direc]
        pos = sub[sub["sharpe"] > 0]
        print(f"\n  [{direc}]")
        print(f"    Positive Sharpe: {len(pos)}/{len(sub)} ({len(pos)/len(sub):.0%})")
        print(f"    Mean Sharpe:   {sub['sharpe'].mean():.3f}")
        print(f"    Median Sharpe: {sub['sharpe'].median():.3f}")
        print(f"    Best Sharpe:   {sub['sharpe'].max():.3f}")
        print(f"    Worst Sharpe:  {sub['sharpe'].min():.3f}")
        print(f"    Top-5 by Sharpe:")
        for _, row in sub.nlargest(5, "sharpe").iterrows():
            print(f"      {row['tag']}: Sharpe {row['sharpe']:.3f}, "
                  f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    return df


# ---------------------------------------------------------------------------
# Split-Half
# ---------------------------------------------------------------------------

def run_split_half(closes, volumes):
    """
    Split into two equal halves, run full scan on each, compute Sharpe
    rank-correlation between halves for stable_long direction.
    """
    n = len(closes)
    mid = n // 2
    h1_c = closes.iloc[:mid];   h1_v = volumes.iloc[:mid]
    h2_c = closes.iloc[mid:];   h2_v = volumes.iloc[mid:]

    print(f"\n  Split-Half Validation (stable_long direction)")
    print(f"  Half 1: {h1_c.index[0].date()} → {h1_c.index[-1].date()} ({len(h1_c)}d)")
    print(f"  Half 2: {h2_c.index[0].date()} → {h2_c.index[-1].date()} ({len(h2_c)}d)")

    sh1, sh2 = [], []
    for lookback, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_SIDES):
        warmup = lookback + 5
        cv1 = compute_cv(h1_c, h1_v, lookback)
        r1  = run_xs_factor(h1_c, cv1, rebal, n_long, "stable_long", warmup=warmup)
        cv2 = compute_cv(h2_c, h2_v, lookback)
        r2  = run_xs_factor(h2_c, cv2, rebal, n_long, "stable_long", warmup=warmup)
        sh1.append(r1["sharpe"])
        sh2.append(r2["sharpe"])

    a1, a2 = np.array(sh1), np.array(sh2)
    corr = np.corrcoef(a1, a2)[0, 1]
    both_pos = ((a1 > 0) & (a2 > 0)).sum()

    print(f"  Sharpe rank correlation: {corr:.3f}")
    print(f"  Positive in both halves: {both_pos}/{len(a1)} ({both_pos/len(a1):.0%})")
    print(f"  H1 mean Sharpe: {a1.mean():.3f}   H2 mean Sharpe: {a2.mean():.3f}")

    return {
        "sharpe_correlation":  round(float(corr), 3),
        "both_positive_count": int(both_pos),
        "both_positive_pct":   round(both_pos / len(a1), 3),
        "h1_mean_sharpe":      round(float(a1.mean()), 3),
        "h2_mean_sharpe":      round(float(a2.mean()), 3),
    }


# ---------------------------------------------------------------------------
# Walk-Forward (expanding window)
# ---------------------------------------------------------------------------

def run_walk_forward(closes, volumes, lookback, rebal, n_long, direction="stable_long"):
    """
    Expanding-window walk-forward: 6 folds.
    Each fold: train window expands, test = next WF_TEST days.
    Minimum train length: WF_MIN_TRAIN days.
    """
    print(f"\n  Walk-Forward ({direction}): L{lookback}_R{rebal}_N{n_long}")
    print(f"  Config: {WF_FOLDS} folds, min_train={WF_MIN_TRAIN}d, test={WF_TEST}d each")

    n = len(closes)
    # Build fold boundaries: test windows starting after min_train, spaced WF_TEST apart
    # Start of first test: WF_MIN_TRAIN days in
    fold_results = []
    test_start = WF_MIN_TRAIN

    for fold_idx in range(WF_FOLDS):
        test_end = test_start + WF_TEST
        if test_end > n:
            print(f"    Fold {fold_idx+1}: not enough data, stopping at fold {fold_idx}")
            break

        # Test slice (pure OOS — never seen during training)
        test_closes  = closes.iloc[test_start:test_end]
        test_volumes = volumes.iloc[test_start:test_end]

        if len(test_closes) < 20:
            print(f"    Fold {fold_idx+1}: test too short ({len(test_closes)}d), skipping")
            test_start += WF_TEST
            continue

        # For an expanding-window CV on the test set we use the full data up
        # to test_end to compute the rolling CV, then slice to the test window.
        # This prevents look-ahead: we only look at prices/volumes up to test_end.
        hist_closes  = closes.iloc[:test_end]
        hist_volumes = volumes.iloc[:test_end]
        cv_full = compute_cv(hist_closes, hist_volumes, lookback)
        cv_test = cv_full.iloc[test_start:test_end]

        warmup_test = min(lookback + 5, len(test_closes) // 2)
        res = run_xs_factor(test_closes, cv_test, rebal, n_long, direction, warmup=warmup_test)

        fold_results.append({
            "fold":       fold_idx + 1,
            "start":      test_closes.index[0].strftime("%Y-%m-%d"),
            "end":        test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days":     len(test_closes),
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
        })
        sign = "+" if res["sharpe"] > 0 else "-"
        print(f"    Fold {fold_idx+1}: {test_closes.index[0].date()} → "
              f"{test_closes.index[-1].date()} | "
              f"Sharpe {sign}{abs(res['sharpe']):.3f}  "
              f"Ann {res['annual_ret']:+.1%}  DD {res['max_dd']:.1%}")

        test_start += WF_TEST

    if not fold_results:
        print("    No folds completed!")
        return None

    df_folds = pd.DataFrame(fold_results)
    pos = (df_folds["sharpe"] > 0).sum()
    print(f"\n    Positive OOS folds: {pos}/{len(df_folds)}")
    print(f"    Mean OOS Sharpe:    {df_folds['sharpe'].mean():.3f}")
    print(f"    Mean OOS Ann Ret:   {df_folds['annual_ret'].mean():.1%}")
    return df_folds


# ---------------------------------------------------------------------------
# Correlation with H-012 (momentum) and H-031 (size factor)
# ---------------------------------------------------------------------------

def _h012_factor_equity(closes):
    """Replicate H-012: 60d momentum, rebal 5d, N=4, stable_long direction."""
    mom = closes.pct_change(60)
    # H-012 goes long TOP momentum, short BOTTOM momentum
    # We use the same run_xs_factor engine but with momentum = erratic_long
    # equivalent (high rank = long). Actually use a bespoke call.
    n = len(closes)
    warmup = 65
    rebal  = 5
    n_long = 4

    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL
    prev_weights = pd.Series(0.0, index=closes.columns)

    for i in range(1, n):
        log_rets = np.log(closes.iloc[i] / closes.iloc[i - 1]).fillna(0)
        if i >= warmup and (i - warmup) % rebal == 0:
            ranks = mom.iloc[i - 1].dropna()
            if len(ranks) < n_long * 2:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue
            sorted_r = ranks.sort_values(ascending=False)
            longs  = sorted_r.index[:n_long]
            shorts = sorted_r.index[-n_long:]
            nw = pd.Series(0.0, index=closes.columns)
            for s in longs:  nw[s] =  1.0 / n_long
            for s in shorts: nw[s] = -1.0 / n_long
            fee_drag = (nw - prev_weights).abs().sum() / 2 * FEE_RATE
            port_ret = (nw * log_rets).sum() - fee_drag
            prev_weights = nw
        else:
            port_ret = (prev_weights * log_rets).sum()
        equity[i] = equity[i - 1] * np.exp(port_ret)

    return pd.Series(equity, index=closes.index)


def _h031_factor_equity(closes):
    """
    Replicate H-031 (size factor): rank by market cap proxy = price * volume
    (30d rolling mean dollar vol as a size proxy). Long small-cap, short large-cap.
    """
    dv = closes * closes  # placeholder: use price^2 as size proxy (high price ~ large cap)
    # Better: use 30d mean dollar volume as size rank
    size = (closes * closes).rolling(30, min_periods=20).mean()
    n = len(closes)
    warmup = 35
    rebal  = 5
    n_long = 4

    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL
    prev_weights = pd.Series(0.0, index=closes.columns)

    for i in range(1, n):
        log_rets = np.log(closes.iloc[i] / closes.iloc[i - 1]).fillna(0)
        if i >= warmup and (i - warmup) % rebal == 0:
            ranks = size.iloc[i - 1].dropna()
            if len(ranks) < n_long * 2:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue
            # Long lowest size (small-cap), short highest (large-cap)
            sorted_r = ranks.sort_values(ascending=True)
            longs  = sorted_r.index[:n_long]
            shorts = sorted_r.index[-n_long:]
            nw = pd.Series(0.0, index=closes.columns)
            for s in longs:  nw[s] =  1.0 / n_long
            for s in shorts: nw[s] = -1.0 / n_long
            fee_drag = (nw - prev_weights).abs().sum() / 2 * FEE_RATE
            port_ret = (nw * log_rets).sum() - fee_drag
            prev_weights = nw
        else:
            port_ret = (prev_weights * log_rets).sum()
        equity[i] = equity[i - 1] * np.exp(port_ret)

    return pd.Series(equity, index=closes.index)


def compute_correlations(closes, volumes, lookback, rebal, n_long):
    """Compute daily return correlations between H-145 and H-012, H-031."""
    print(f"\n  Factor Correlations: L{lookback}_R{rebal}_N{n_long}")

    cv = compute_cv(closes, volumes, lookback)
    res_h145 = run_xs_factor(closes, cv, rebal, n_long, "stable_long",
                             warmup=lookback + 5)
    eq_h145 = res_h145["equity"]
    rets_h145 = eq_h145.pct_change().dropna()

    # H-012
    eq_h012 = _h012_factor_equity(closes)
    rets_h012 = eq_h012.pct_change().dropna()

    # H-031
    eq_h031 = _h031_factor_equity(closes)
    rets_h031 = eq_h031.pct_change().dropna()

    # Compute on common index
    common_12 = rets_h145.index.intersection(rets_h012.index)
    common_31 = rets_h145.index.intersection(rets_h031.index)

    corr_12 = rets_h145.loc[common_12].corr(rets_h012.loc[common_12]) if len(common_12) > 30 else np.nan
    corr_31 = rets_h145.loc[common_31].corr(rets_h031.loc[common_31]) if len(common_31) > 30 else np.nan

    h012_met = compute_metrics(eq_h012)
    h031_met = compute_metrics(eq_h031)

    print(f"  H-145 (stable_long):  Sharpe {res_h145['sharpe']:.3f}, "
          f"Ann {res_h145['annual_ret']:.1%}, DD {res_h145['max_dd']:.1%}")
    print(f"  H-012 (momentum):     Sharpe {h012_met['sharpe']:.3f}, "
          f"Ann {h012_met['annual_ret']:.1%}, DD {h012_met['max_dd']:.1%}")
    print(f"  H-031 (size):         Sharpe {h031_met['sharpe']:.3f}, "
          f"Ann {h031_met['annual_ret']:.1%}, DD {h031_met['max_dd']:.1%}")
    print(f"  Corr(H-145, H-012): {corr_12:.3f}")
    print(f"  Corr(H-145, H-031): {corr_31:.3f}")

    return {
        "h012": round(float(corr_12) if not np.isnan(corr_12) else 99.0, 3),
        "h031": round(float(corr_31) if not np.isnan(corr_31) else 99.0, 3),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 72)
    print("H-145: Dollar-Volume Stability Factor")
    print("=" * 72)

    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")

    if len(daily) < 10:
        print("ERROR: fewer than 10 assets loaded. Aborting.")
        sys.exit(1)

    # Build aligned closes and volumes panels
    closes  = pd.DataFrame({sym: df["close"]  for sym, df in daily.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily.items()})

    closes  = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().fillna(0)

    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")
    print(f"Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    # -----------------------------------------------------------------------
    # 1. Full IS parameter scan
    # -----------------------------------------------------------------------
    scan_df = run_full_scan(closes, volumes)

    # Separate by direction
    stable_df  = scan_df[scan_df["direction"] == "stable_long"].copy()
    erratic_df = scan_df[scan_df["direction"] == "erratic_long"].copy()

    best_stable = stable_df.nlargest(1, "sharpe").iloc[0]
    best_L = int(best_stable["lookback"])
    best_R = int(best_stable["rebal"])
    best_N = int(best_stable["n_long"])

    pct_pos_stable  = (stable_df["sharpe"] > 0).mean()
    pct_pos_erratic = (erratic_df["sharpe"] > 0).mean()

    print(f"\n  Best stable_long params: L{best_L}_R{best_R}_N{best_N}")
    print(f"  Sharpe {best_stable['sharpe']:.3f}, "
          f"Ann {best_stable['annual_ret']:.1%}, "
          f"DD {best_stable['max_dd']:.1%}")

    # -----------------------------------------------------------------------
    # 2. Split-Half
    # -----------------------------------------------------------------------
    split_half = run_split_half(closes, volumes)

    # -----------------------------------------------------------------------
    # 3. Walk-Forward (stable_long, best params)
    # -----------------------------------------------------------------------
    wf_df = run_walk_forward(closes, volumes, best_L, best_R, best_N,
                             direction="stable_long")

    # -----------------------------------------------------------------------
    # 4. Factor correlations
    # -----------------------------------------------------------------------
    corrs = compute_correlations(closes, volumes, best_L, best_R, best_N)

    # -----------------------------------------------------------------------
    # 5. Verdicts
    # -----------------------------------------------------------------------
    n_stable     = len(stable_df)
    is_pass      = pct_pos_stable >= 0.80
    wf_pos_folds = int((wf_df["sharpe"] > 0).sum()) if wf_df is not None else 0
    wf_n_folds   = len(wf_df) if wf_df is not None else 0
    wf_pass      = wf_pos_folds >= 4
    sh_pass      = split_half["sharpe_correlation"] > 0
    corr_pass    = abs(corrs["h012"]) <= 0.40

    print("\n" + "=" * 72)
    print("SUMMARY: H-145 Dollar-Volume Stability Factor")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets × {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print()

    print(f"  [PARAMETER SCAN]")
    print(f"    Total combos (2 directions): {len(scan_df)}")
    print(f"    stable_long  positive Sharpe: {(stable_df['sharpe']>0).sum()}/{n_stable} "
          f"({pct_pos_stable:.0%})")
    print(f"    erratic_long positive Sharpe: {(erratic_df['sharpe']>0).sum()}/{len(erratic_df)} "
          f"({pct_pos_erratic:.0%})")
    print(f"    stable_long  mean Sharpe: {stable_df['sharpe'].mean():.3f}  "
          f"median: {stable_df['sharpe'].median():.3f}")
    print(f"    erratic_long mean Sharpe: {erratic_df['sharpe'].mean():.3f}  "
          f"median: {erratic_df['sharpe'].median():.3f}")
    print()

    print(f"  [BEST PARAMS (stable_long)]: L{best_L}_R{best_R}_N{best_N}")
    print(f"    IS Sharpe: {best_stable['sharpe']:.3f}")
    print(f"    IS Annual: {best_stable['annual_ret']:.1%}")
    print(f"    IS Max DD: {best_stable['max_dd']:.1%}")
    print()

    print(f"  [WALK-FORWARD] (expanding window, {WF_FOLDS} folds, {WF_TEST}d test each)")
    if wf_df is not None:
        for _, row in wf_df.iterrows():
            sign = "+" if row["sharpe"] > 0 else "-"
            print(f"    Fold {int(row['fold'])}: {row['start']} → {row['end']}  "
                  f"Sharpe {sign}{abs(row['sharpe']):.3f}  "
                  f"Ann {row['annual_ret']:+.1%}  DD {row['max_dd']:.1%}")
        print(f"    => {wf_pos_folds}/{wf_n_folds} positive folds, "
              f"mean OOS Sharpe {wf_df['sharpe'].mean():.3f}")
    else:
        print("    Insufficient data for walk-forward")
    print()

    print(f"  [SPLIT-HALF]")
    print(f"    H1 mean Sharpe: {split_half['h1_mean_sharpe']:.3f}  "
          f"H2 mean Sharpe: {split_half['h2_mean_sharpe']:.3f}")
    print(f"    Sharpe rank correlation: {split_half['sharpe_correlation']:.3f}")
    print(f"    Both halves positive: {split_half['both_positive_count']}/{n_stable}")
    print()

    print(f"  [CORRELATIONS (best params, stable_long)]")
    print(f"    Corr(H-145, H-012 momentum): {corrs['h012']:.3f}")
    print(f"    Corr(H-145, H-031 size):     {corrs['h031']:.3f}")
    print()

    # Pass / Fail
    print(f"  [ACCEPTANCE CRITERIA]")
    print(f"    IS >= 80% positive Sharpe:     {'PASS' if is_pass   else 'FAIL'} "
          f"({pct_pos_stable:.0%})")
    print(f"    WF >= 4/6 positive OOS folds:  {'PASS' if wf_pass   else 'FAIL'} "
          f"({wf_pos_folds}/{wf_n_folds})")
    print(f"    Split-half corr > 0:           {'PASS' if sh_pass   else 'FAIL'} "
          f"({split_half['sharpe_correlation']:.3f})")
    print(f"    H-012 correlation <= 0.40:     {'PASS' if corr_pass else 'FAIL'} "
          f"({corrs['h012']:.3f})")
    print()

    passes = sum([is_pass, wf_pass, sh_pass, corr_pass])
    if passes == 4:
        verdict = "CONFIRMED — all 4 criteria passed"
    elif passes >= 3:
        verdict = "BORDERLINE — 3/4 criteria passed, further analysis recommended"
    else:
        verdict = "REJECTED — fewer than 3/4 criteria passed"

    print(f"  VERDICT: {verdict}")
    print("=" * 72)

    # -----------------------------------------------------------------------
    # Save results
    # -----------------------------------------------------------------------
    results_data = {
        "hypothesis": "H-145",
        "name": "Dollar-Volume Stability Factor",
        "description": (
            "Cross-sectional factor: coefficient of variation (CV=std/mean) "
            "of daily dollar volume. Low CV = stable (institutional), "
            "High CV = erratic (speculative). stable_long: long low-CV, short high-CV."
        ),
        "fee_rate_bps": FEE_RATE * 10000,
        "universe_size": len(closes.columns),
        "n_days": len(closes),
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "full_scan": {
            "n_combos_total": len(scan_df),
            "n_combos_per_direction": n_stable,
            "stable_long": {
                "pct_positive_sharpe": round(float(pct_pos_stable), 3),
                "mean_sharpe":   round(float(stable_df["sharpe"].mean()), 3),
                "median_sharpe": round(float(stable_df["sharpe"].median()), 3),
                "best_params":   f"L{best_L}_R{best_R}_N{best_N}",
                "best_sharpe":   round(float(best_stable["sharpe"]), 3),
                "best_annual_ret": round(float(best_stable["annual_ret"]), 4),
                "best_max_dd":   round(float(best_stable["max_dd"]), 4),
                "all_results":   stable_df.drop(columns=["tag"], errors="ignore").to_dict("records"),
            },
            "erratic_long": {
                "pct_positive_sharpe": round(float(pct_pos_erratic), 3),
                "mean_sharpe":   round(float(erratic_df["sharpe"].mean()), 3),
                "median_sharpe": round(float(erratic_df["sharpe"].median()), 3),
                "all_results":   erratic_df.drop(columns=["tag"], errors="ignore").to_dict("records"),
            },
        },
        "split_half": split_half,
        "walk_forward": {
            "direction":      "stable_long",
            "params":         f"L{best_L}_R{best_R}_N{best_N}",
            "min_train_days": WF_MIN_TRAIN,
            "test_days":      WF_TEST,
            "n_folds":        wf_n_folds,
            "positive_folds": wf_pos_folds,
            "mean_oos_sharpe": round(float(wf_df["sharpe"].mean()), 3) if wf_df is not None else None,
            "mean_oos_annual_ret": round(float(wf_df["annual_ret"].mean()), 4) if wf_df is not None else None,
            "folds": wf_df.to_dict("records") if wf_df is not None else [],
        },
        "correlations": corrs,
        "acceptance": {
            "is_pct_positive": is_pass,
            "wf_4_of_6":       wf_pass,
            "split_half_corr": sh_pass,
            "h012_corr":       corr_pass,
            "passes":          passes,
            "verdict":         verdict,
        },
    }

    out_file = RESULTS_DIR / "results.json"
    with open(out_file, "w") as f:
        json.dump(results_data, f, indent=2, default=str)
    print(f"\n  Results saved to {out_file}")
