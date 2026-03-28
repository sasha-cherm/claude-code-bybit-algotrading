"""
H-112: Downside Beta Factor (Cross-Sectional)

Asymmetric beta — computed ONLY on days when BTC return < 0.
Assets with low downside beta are "defensive" (don't crash with BTC).
Assets with high downside beta are "fragile" (crash hard with BTC).

Strategy: Long defensive (low downside beta), Short fragile (high downside beta).
Market-neutral (dollar-neutral), equal-weighted.

This differs from H-024 (regular beta, 60d, all days) by using ONLY BTC down days.
The intuition: downside beta is the relevant risk measure for drawdown avoidance.

Parameter grid (48 combos):
  Lookback windows : [30, 40, 60, 90] days
  Rebalance freq   : [5, 7, 10, 14] days
  N positions each : [3, 4, 5]

Validation:
  - Full param scan: % positive Sharpe (target: >80%)
  - 6-fold rolling walk-forward (60% train / 40% test)
  - Split-half stability
  - Correlation with H-019 (low-vol) and H-024 (regular beta)
  - Fee sensitivity: 0.1% round-trip (Bybit taker)

Downside beta computation:
  down_days = dates where btc_ret < 0
  db_i = cov(asset_ret[down_days], btc_ret[down_days]) / var(btc_ret[down_days])
  computed over rolling lookback window, using ONLY down days in that window.

Sharpe: daily mean / daily std * sqrt(365)
Fee: 0.1% round-trip (10 bps)  [Bybit taker]
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

FEE_RATE = 0.001        # 0.1% round-trip (Bybit taker)
INITIAL_CAPITAL = 10_000.0

# Parameter grid
LOOKBACKS  = [30, 40, 60, 90]
REBAL_FREQS = [5, 7, 10, 14]
N_SIZES    = [3, 4, 5]
# 4 x 4 x 3 = 48 combos

# Walk-forward settings (6 folds, 60% train / 40% test)
WF_FOLDS = 6


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
                print(f"  {sym}: only {len(df)} bars — skipping")
        else:
            print(f"  {sym}: no data found at {path}")
    return daily


def build_close_matrix(daily: dict) -> pd.DataFrame:
    """Align all assets on common dates, return close price matrix."""
    closes = {}
    for sym, df in daily.items():
        closes[sym] = df["close"]
    df_closes = pd.DataFrame(closes)
    df_closes = df_closes.dropna(how="all")
    df_closes = df_closes.ffill()
    return df_closes


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
    sharpe = float(rets.mean() / rets.std() * np.sqrt(365)) if rets.std() > 1e-10 else 0.0
    return {
        "sharpe": round(sharpe, 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "win_rate": round(n_pos / n_total, 4) if n_total > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Core downside beta computation (vectorised)
# ---------------------------------------------------------------------------

def compute_downside_beta_matrix(
    returns: pd.DataFrame,
    btc_rets: pd.Series,
    lookback: int,
) -> pd.DataFrame:
    """
    For each day t, compute rolling downside beta for each asset using the
    past `lookback` days where BTC had a NEGATIVE return.

    Returns a DataFrame same shape as `returns` with downside beta values.
    Minimum 5 down-days required; else NaN.
    """
    n_days = len(returns)
    n_assets = len(returns.columns)
    beta_vals = np.full((n_days, n_assets), np.nan)

    btc_arr = btc_rets.values
    ret_arr = returns.values

    for i in range(lookback, n_days):
        window_btc = btc_arr[i - lookback: i]
        window_ret = ret_arr[i - lookback: i, :]

        # Select only BTC down days in the window
        down_mask = window_btc < 0
        n_down = down_mask.sum()
        if n_down < 5:
            continue

        btc_down = window_btc[down_mask]
        var_btc = float(np.var(btc_down, ddof=1))
        if var_btc < 1e-12:
            continue

        for j in range(n_assets):
            asset_down = window_ret[down_mask, j]
            # skip if too many NaNs
            valid = ~np.isnan(asset_down)
            if valid.sum() < 5:
                continue
            b_down_valid = btc_down[valid]
            a_down_valid = asset_down[valid]
            if len(b_down_valid) < 5:
                continue
            cov = float(np.cov(a_down_valid, b_down_valid, ddof=1)[0, 1])
            var_b = float(np.var(b_down_valid, ddof=1))
            if var_b < 1e-12:
                continue
            beta_vals[i, j] = cov / var_b

    return pd.DataFrame(beta_vals, index=returns.index, columns=returns.columns)


# ---------------------------------------------------------------------------
# Core back-test engine
# ---------------------------------------------------------------------------

def run_downside_beta_factor(
    closes: pd.DataFrame,
    lookback: int,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    fee_rate: float = FEE_RATE,
    pre_computed_betas: pd.DataFrame | None = None,
) -> dict:
    """
    Cross-sectional downside beta strategy.

    Signal: rolling downside beta (only BTC down days in lookback window).
    LONG low downside beta (defensive), SHORT high downside beta (fragile).
    """
    if n_short is None:
        n_short = n_long

    returns = closes.pct_change()
    btc_sym = "BTC/USDT" if "BTC/USDT" in closes.columns else closes.columns[0]
    btc_rets = returns[btc_sym]

    if pre_computed_betas is not None:
        db_matrix = pre_computed_betas
    else:
        db_matrix = compute_downside_beta_matrix(returns, btc_rets, lookback)

    n = len(closes)
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count = 0
    warmup = lookback + 5

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            # Use lagged signal (t-1) to avoid look-ahead
            db_signal = db_matrix.iloc[i - 1]
            valid = db_signal.dropna()

            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # Sort ascending: lowest downside beta = LONG (defensive)
            ranked = valid.sort_values(ascending=True)
            longs  = ranked.index[:n_long]   # lowest db = most defensive
            shorts = ranked.index[-n_short:] # highest db = most fragile

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] =  1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2.0
            fee_drag = turnover * fee_rate

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
# Full parameter scan
# ---------------------------------------------------------------------------

def run_full_scan(closes: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-112: DOWNSIDE BETA FACTOR -- Full Param Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per trade (Bybit taker)")
    print(f"  Strategy : LONG low downside-beta (defensive), SHORT high (fragile)")

    results = []

    # Pre-compute beta matrices for each lookback to speed things up
    returns = closes.pct_change()
    btc_sym = "BTC/USDT" if "BTC/USDT" in closes.columns else closes.columns[0]
    btc_rets = returns[btc_sym]

    print("\n  Pre-computing downside beta matrices for each lookback window...")
    beta_cache = {}
    for lb in LOOKBACKS:
        print(f"    Lookback {lb}d ...", end=" ", flush=True)
        beta_cache[lb] = compute_downside_beta_matrix(returns, btc_rets, lb)
        print("done")

    print(f"\n  Running {len(LOOKBACKS) * len(REBAL_FREQS) * len(N_SIZES)} param combos...")
    for lb, rebal, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        res = run_downside_beta_factor(
            closes, lb, rebal, n,
            pre_computed_betas=beta_cache[lb],
        )
        tag = f"L{lb}_R{rebal}_N{n}"
        results.append({
            "tag": tag, "lookback": lb, "rebal": rebal, "n": n,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "win_rate": res["win_rate"],
            "n_trades": res["n_trades"], "n_rebalances": res["n_rebalances"],
        })

    df = pd.DataFrame(results)
    pos_pct = (df["sharpe"] > 0).mean()
    print(f"\n  Combos: {len(df)}, Positive Sharpe: {(df['sharpe']>0).sum()}/{len(df)} ({pos_pct:.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}, Median: {df['sharpe'].median():.3f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.3f}, Worst: {df['sharpe'].min():.3f}")
    print(f"  Mean Ann Ret: {df['annual_ret'].mean():.1%}, Mean DD: {df['max_dd'].mean():.1%}")

    print(f"\n  Top 10 parameter combos:")
    for _, row in df.nlargest(10, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Rebals {row['n_rebalances']}")

    print(f"\n  By lookback window:")
    for lb in LOOKBACKS:
        sub = df[df["lookback"] == lb]
        print(f"    L{lb}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"positive {(sub['sharpe']>0).sum()}/{len(sub)} ({(sub['sharpe']>0).mean():.0%})")

    print(f"\n  By rebalance frequency:")
    for rb in REBAL_FREQS:
        sub = df[df["rebal"] == rb]
        print(f"    R{rb}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"positive {(sub['sharpe']>0).sum()}/{len(sub)} ({(sub['sharpe']>0).mean():.0%})")

    print(f"\n  By N positions:")
    for n_sz in N_SIZES:
        sub = df[df["n"] == n_sz]
        print(f"    N{n_sz}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"positive {(sub['sharpe']>0).sum()}/{len(sub)} ({(sub['sharpe']>0).mean():.0%})")

    return df, beta_cache


# ---------------------------------------------------------------------------
# 6-fold walk-forward OOS (60% train / 40% test, rolling)
# ---------------------------------------------------------------------------

def run_walk_forward(closes: pd.DataFrame):
    print(f"\n  Walk-Forward (6 folds, 60% train / 40% test, rolling)")
    n = len(closes)
    fold_size = n // (WF_FOLDS + 1)  # rough fold unit
    # Compute train_size and test_size for 60/40 split of full window
    # Rolling: advance by test_size each fold, 6 folds total
    # Total needed = 6 * test_size + train_size
    # We want 6 non-overlapping test windows
    # Let's define: test_size = int(n * 0.4 / 6), train_size = int(n * 0.6 / 3) to ensure overlap
    # Simpler: each fold uses [fold_start : fold_start + window_size] where window_size covers 60/40
    # Standard: sliding window of size W = train+test, step = test
    # Set W so train/W = 0.6 => train = 0.6W, test = 0.4W
    # We want 6 folds fitting in n days
    # test_size = n // (WF_FOLDS * 2.5) rounded
    # Actually: total_test = 6 * test_size, total = train_size + 6*test_size
    # with train_size = 1.5 * total_test => train_size = 1.5 * 6 * test_size = 9 * test_size
    # => 10 * test_size = n => test_size = n // 10
    test_size  = max(60, n // 10)
    train_size = int(test_size * 1.5)   # 60/40 ratio
    step       = test_size

    print(f"  n={n} days → train={train_size}d, test={test_size}d, step={step}d")

    fold_results = []
    fold_num = 0

    for fold_idx in range(WF_FOLDS):
        train_start = fold_idx * step
        train_end   = train_start + train_size
        test_end    = train_end + test_size
        if test_end > n:
            break

        train_c = closes.iloc[train_start:train_end]
        test_c  = closes.iloc[train_end:test_end]

        if len(test_c) < 30 or len(train_c) < 60:
            break

        fold_num += 1
        # Select best params on train
        best_s = -999.0
        best_p = None
        returns_train = train_c.pct_change()
        btc_sym = "BTC/USDT" if "BTC/USDT" in train_c.columns else train_c.columns[0]
        btc_rets_train = returns_train[btc_sym]

        for lb, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
            if lb + 5 >= len(train_c) - 20:
                continue
            db = compute_downside_beta_matrix(returns_train, btc_rets_train, lb)
            res = run_downside_beta_factor(train_c, lb, rebal, n_long,
                                           pre_computed_betas=db)
            if res["sharpe"] > best_s:
                best_s = res["sharpe"]
                best_p = (lb, rebal, n_long)

        if best_p is None:
            break

        lb, rebal, n_long = best_p
        returns_test = test_c.pct_change()
        btc_rets_test = returns_test[btc_sym]
        db_test = compute_downside_beta_matrix(returns_test, btc_rets_test, lb)
        res_test = run_downside_beta_factor(test_c, lb, rebal, n_long,
                                            pre_computed_betas=db_test)

        fold_results.append({
            "fold": fold_num,
            "train_start": train_c.index[0].strftime("%Y-%m-%d"),
            "train_end":   train_c.index[-1].strftime("%Y-%m-%d"),
            "test_start":  test_c.index[0].strftime("%Y-%m-%d"),
            "test_end":    test_c.index[-1].strftime("%Y-%m-%d"),
            "best_params": f"L{lb}_R{rebal}_N{n_long}",
            "train_sharpe": round(best_s, 3),
            "oos_sharpe":   res_test["sharpe"],
            "oos_ann_ret":  res_test["annual_ret"],
            "oos_max_dd":   res_test["max_dd"],
        })
        print(f"    Fold {fold_num}: train {train_c.index[0].date()}→{train_c.index[-1].date()} "
              f"| test {test_c.index[0].date()}→{test_c.index[-1].date()} "
              f"| IS best L{lb}_R{rebal}_N{n_long} ({best_s:.3f}) "
              f"| OOS {res_test['sharpe']:.3f}")

    if not fold_results:
        print("    No folds completed.")
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe"] > 0).sum()
    mean_oos = df["oos_sharpe"].mean()
    print(f"    Positive OOS folds: {pos}/{len(df)},  Mean OOS Sharpe: {mean_oos:.3f}")
    print(f"    Min OOS: {df['oos_sharpe'].min():.3f}, Max OOS: {df['oos_sharpe'].max():.3f}")
    return df


# ---------------------------------------------------------------------------
# Split-half consistency
# ---------------------------------------------------------------------------

def run_split_half(closes: pd.DataFrame):
    n = len(closes)
    mid = n // 2
    c1, c2 = closes.iloc[:mid], closes.iloc[mid:]

    print(f"\n  Split-Half Consistency")
    print(f"    Half1: {c1.index[0].date()} to {c1.index[-1].date()} ({len(c1)} days)")
    print(f"    Half2: {c2.index[0].date()} to {c2.index[-1].date()} ({len(c2)} days)")

    # Pre-compute betas for both halves
    def make_beta_cache(closes_sub):
        rets = closes_sub.pct_change()
        btc_sym = "BTC/USDT" if "BTC/USDT" in closes_sub.columns else closes_sub.columns[0]
        btc_rets = rets[btc_sym]
        cache = {}
        for lb in LOOKBACKS:
            cache[lb] = compute_downside_beta_matrix(rets, btc_rets, lb)
        return cache

    print("    Computing half-1 beta matrices...", end=" ", flush=True)
    cache1 = make_beta_cache(c1)
    print("done")
    print("    Computing half-2 beta matrices...", end=" ", flush=True)
    cache2 = make_beta_cache(c2)
    print("done")

    h1_sharpes, h2_sharpes = [], []
    tags = []
    for lb, rebal, n_long in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        r1 = run_downside_beta_factor(c1, lb, rebal, n_long, pre_computed_betas=cache1[lb])
        r2 = run_downside_beta_factor(c2, lb, rebal, n_long, pre_computed_betas=cache2[lb])
        h1_sharpes.append(r1["sharpe"])
        h2_sharpes.append(r2["sharpe"])
        tags.append(f"L{lb}_R{rebal}_N{n_long}")

    h1 = np.array(h1_sharpes)
    h2 = np.array(h2_sharpes)
    corr = float(np.corrcoef(h1, h2)[0, 1])
    both_pos = int(((h1 > 0) & (h2 > 0)).sum())
    print(f"    Sharpe corr between halves: {corr:.3f}")
    print(f"    Positive in both halves: {both_pos}/{len(h1)} ({both_pos/len(h1):.0%})")
    print(f"    Half1 mean Sharpe: {h1.mean():.3f}, Half2 mean Sharpe: {h2.mean():.3f}")

    df_sh = pd.DataFrame({"tag": tags, "h1": h1, "h2": h2})
    consistent = df_sh[(df_sh["h1"] > 0) & (df_sh["h2"] > 0)].copy()
    if len(consistent) > 0:
        consistent["min_sharpe"] = consistent[["h1", "h2"]].min(axis=1)
        print(f"    Most consistent (both halves positive, sorted by min Sharpe):")
        for _, row in consistent.nlargest(5, "min_sharpe").iterrows():
            print(f"      {row['tag']}: H1={row['h1']:.3f}, H2={row['h2']:.3f}")
    else:
        print(f"    No params positive in both halves.")

    return {
        "sharpe_correlation": round(corr, 3),
        "both_positive_pct": round(both_pos / len(h1), 3),
        "half1_mean_sharpe": round(float(h1.mean()), 3),
        "half2_mean_sharpe": round(float(h2.mean()), 3),
    }


# ---------------------------------------------------------------------------
# Fee sensitivity
# ---------------------------------------------------------------------------

def run_fee_sensitivity(closes: pd.DataFrame, best_lb: int, best_rb: int,
                        best_n: int, best_beta: pd.DataFrame):
    print(f"\n  Fee Sensitivity (best params: L{best_lb}_R{best_rb}_N{best_n})")
    print(f"  (Bybit taker = 0.1% = 10 bps)")

    fee_multipliers = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]
    results = {}
    for mult in fee_multipliers:
        fee = FEE_RATE * mult
        res = run_downside_beta_factor(closes, best_lb, best_rb, best_n,
                                       pre_computed_betas=best_beta, fee_rate=fee)
        label = f"{mult:.0f}x" if mult == int(mult) else f"{mult:.1f}x"
        print(f"    Fee {label} ({fee*10000:.0f} bps): Sharpe {res['sharpe']:.3f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}, "
              f"Rebals {res['n_rebalances']}")
        if mult == 1.0:
            results["sharpe_1x"] = res["sharpe"]
            results["ann_ret_1x"] = res["annual_ret"]
        elif mult == 5.0:
            results["sharpe_5x"] = res["sharpe"]
            results["ann_ret_5x"] = res["annual_ret"]

    return results


# ---------------------------------------------------------------------------
# Correlation with H-019 (low-vol) and H-024 (regular beta)
# ---------------------------------------------------------------------------

def compute_factor_correlations(
    closes: pd.DataFrame,
    best_lb: int, best_rb: int, best_n: int,
    best_beta: pd.DataFrame,
):
    print(f"\n  Factor Correlations (vs H-019 low-vol, H-024 regular beta)")

    # H-112 returns
    res_h112 = run_downside_beta_factor(closes, best_lb, best_rb, best_n,
                                        pre_computed_betas=best_beta)
    rets_h112 = res_h112["equity"].pct_change().dropna()

    returns = closes.pct_change()
    btc_sym = "BTC/USDT" if "BTC/USDT" in closes.columns else closes.columns[0]

    # ---- H-019: 20d vol ranking, 21d rebalance, top/bottom 3 ----
    def run_vol_factor(closes_inner, vol_lb=20, rebal_f=21, n_l=3, warmup_i=25):
        daily_rets = closes_inner.pct_change()
        vol = daily_rets.rolling(vol_lb).std()
        n = len(closes_inner)
        eq = np.zeros(n)
        eq[0] = INITIAL_CAPITAL
        pw = pd.Series(0.0, index=closes_inner.columns)
        for i in range(1, n):
            lret = np.log(closes_inner.iloc[i] / closes_inner.iloc[i - 1])
            if i >= warmup_i and (i - warmup_i) % rebal_f == 0:
                ranks = vol.iloc[i - 1].dropna()
                if len(ranks) < n_l * 2:
                    eq[i] = eq[i - 1] * np.exp((pw * lret).sum())
                    continue
                ranked = ranks.sort_values(ascending=True)
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

    rets_h019 = run_vol_factor(closes)

    # ---- H-024: 60d FULL beta, 21d rebalance, top/bottom 3 ----
    def run_full_beta_factor(closes_inner, beta_lb=60, rebal_f=21, n_l=3, warmup_i=65):
        """Regular (full) beta using all days, long low-beta, short high-beta."""
        btc_s = "BTC/USDT" if "BTC/USDT" in closes_inner.columns else closes_inner.columns[0]
        rets = closes_inner.pct_change()
        btc_r = rets[btc_s]
        n = len(closes_inner)
        # precompute beta matrix
        assets = [c for c in closes_inner.columns if c != btc_s]
        all_cols = closes_inner.columns.tolist()
        beta_mat = np.full((n, len(all_cols)), np.nan)

        for i in range(beta_lb, n):
            btc_win = btc_r.values[i - beta_lb: i]
            var_b = np.var(btc_win, ddof=1)
            if var_b < 1e-12:
                continue
            for j, col in enumerate(all_cols):
                asset_win = rets[col].values[i - beta_lb: i]
                valid = ~np.isnan(asset_win)
                if valid.sum() < 10:
                    continue
                cov = np.cov(asset_win[valid], btc_win[valid], ddof=1)[0, 1]
                beta_mat[i, j] = cov / var_b

        beta_df = pd.DataFrame(beta_mat, index=closes_inner.index, columns=all_cols)

        eq = np.zeros(n)
        eq[0] = INITIAL_CAPITAL
        pw = pd.Series(0.0, index=all_cols)
        for i in range(1, n):
            lret = np.log(closes_inner.iloc[i] / closes_inner.iloc[i - 1])
            if i >= warmup_i and (i - warmup_i) % rebal_f == 0:
                ranks = beta_df.iloc[i - 1].dropna()
                if len(ranks) < n_l * 2:
                    eq[i] = eq[i - 1] * np.exp((pw * lret).sum())
                    continue
                ranked = ranks.sort_values(ascending=True)
                new_w = pd.Series(0.0, index=all_cols)
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

    rets_h024 = run_full_beta_factor(closes)

    # Align and compute correlations
    common_idx = rets_h112.index.intersection(rets_h019.index).intersection(rets_h024.index)
    r112 = rets_h112.loc[common_idx]
    r019 = rets_h019.loc[common_idx]
    r024 = rets_h024.loc[common_idx]

    corr_019 = float(r112.corr(r019))
    corr_024 = float(r112.corr(r024))
    corr_019_024 = float(r019.corr(r024))

    # H-019 standalone Sharpe
    sh_h019 = float(r019.mean() / r019.std() * np.sqrt(365)) if r019.std() > 1e-10 else 0.0
    sh_h024 = float(r024.mean() / r024.std() * np.sqrt(365)) if r024.std() > 1e-10 else 0.0

    print(f"    H-112 vs H-019 (low-vol):       corr = {corr_019:.3f} "
          f"{'  ← REDUNDANT (>0.5)' if abs(corr_019) > 0.5 else '  ← INDEPENDENT'}")
    print(f"    H-112 vs H-024 (regular beta):  corr = {corr_024:.3f} "
          f"{'  ← REDUNDANT (>0.5)' if abs(corr_024) > 0.5 else '  ← INDEPENDENT'}")
    print(f"    H-019 vs H-024 (reference):     corr = {corr_019_024:.3f}")
    print(f"    H-019 standalone Sharpe: {sh_h019:.3f}")
    print(f"    H-024 standalone Sharpe: {sh_h024:.3f}")

    return {
        "corr_with_h019": round(corr_019, 3),
        "corr_with_h024": round(corr_024, 3),
        "corr_h019_h024": round(corr_019_024, 3),
        "h019_sharpe": round(sh_h019, 3),
        "h024_sharpe": round(sh_h024, 3),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 72)
    print("H-112: DOWNSIDE BETA FACTOR BACKTEST")
    print("=" * 72)
    print("Loading daily price data...")

    daily = load_daily_data()
    if len(daily) < 5:
        print("ERROR: not enough assets loaded. Exiting.")
        return

    closes = build_close_matrix(daily)
    print(f"\nClose matrix: {closes.shape[0]} days x {closes.shape[1]} assets")
    print(f"Date range: {closes.index[0].date()} to {closes.index[-1].date()}")

    # Count BTC down days
    btc_sym = "BTC/USDT" if "BTC/USDT" in closes.columns else closes.columns[0]
    btc_rets = closes[btc_sym].pct_change().dropna()
    n_down = (btc_rets < 0).sum()
    n_up   = (btc_rets > 0).sum()
    print(f"\nBTC down days: {n_down} ({n_down/(n_down+n_up):.1%} of all trading days)")
    print(f"BTC up days:   {n_up} ({n_up/(n_down+n_up):.1%})")

    # 1. Full parameter scan
    scan_df, beta_cache = run_full_scan(closes)
    pos_pct = (scan_df["sharpe"] > 0).mean()

    # Best params from scan
    best_row  = scan_df.nlargest(1, "sharpe").iloc[0]
    best_lb   = int(best_row["lookback"])
    best_rb   = int(best_row["rebal"])
    best_n    = int(best_row["n"])
    best_beta = beta_cache[best_lb]
    print(f"\n  >>> Best params: L{best_lb}_R{best_rb}_N{best_n}, "
          f"Sharpe {best_row['sharpe']:.3f}, Ann {best_row['annual_ret']:.1%}, "
          f"DD {best_row['max_dd']:.1%}")

    # 2. Walk-forward OOS
    print("\n" + "=" * 72)
    print("WALK-FORWARD OOS (6 folds, 60/40 train/test, rolling)")
    print("=" * 72)
    wf_df = run_walk_forward(closes)
    wf_pos_pct = (wf_df["oos_sharpe"] > 0).mean() if wf_df is not None else 0.0
    mean_wf_oos = wf_df["oos_sharpe"].mean() if wf_df is not None else -99.0

    # 3. Split-half consistency
    print("\n" + "=" * 72)
    print("SPLIT-HALF CONSISTENCY")
    print("=" * 72)
    split_half = run_split_half(closes)

    # 4. Fee sensitivity
    print("\n" + "=" * 72)
    print("FEE SENSITIVITY")
    print("=" * 72)
    fee_res = run_fee_sensitivity(closes, best_lb, best_rb, best_n, best_beta)

    # 5. Factor correlations
    print("\n" + "=" * 72)
    print("FACTOR CORRELATIONS (H-019 low-vol, H-024 regular beta)")
    print("=" * 72)
    corr_res = compute_factor_correlations(closes, best_lb, best_rb, best_n, best_beta)

    # -----------------------------------------------------------------------
    # VERDICT
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("VERDICT SUMMARY")
    print("=" * 72)

    checks = {
        "param_robustness_pct_positive": pos_pct,
        "wf_folds_positive": f"{int(wf_pos_pct * len(wf_df)) if wf_df is not None else 0}/{len(wf_df) if wf_df is not None else 0}",
        "wf_mean_oos_sharpe": mean_wf_oos,
        "split_half_corr": split_half["sharpe_correlation"],
        "corr_with_h019": corr_res["corr_with_h019"],
        "corr_with_h024": corr_res["corr_with_h024"],
        "fee_1x_sharpe": fee_res.get("sharpe_1x", -99),
        "best_is_sharpe": float(best_row["sharpe"]),
        "best_is_annual_ret": float(best_row["annual_ret"]),
        "best_is_max_dd": float(best_row["max_dd"]),
    }

    print(f"  Param robustness (% positive Sharpe): {pos_pct:.0%} "
          f"{'PASS ✓' if pos_pct >= 0.80 else 'FAIL ✗'} (target ≥80%)")
    print(f"  WF OOS mean Sharpe: {mean_wf_oos:.3f} "
          f"{'PASS ✓' if mean_wf_oos >= 0.5 else 'FAIL ✗'} (target ≥0.5)")
    print(f"  WF positive folds: {checks['wf_folds_positive']} "
          f"{'PASS ✓' if wf_pos_pct >= 0.5 else 'FAIL ✗'} (target ≥50%)")
    print(f"  Split-half corr: {split_half['sharpe_correlation']:.3f} "
          f"{'PASS ✓' if split_half['sharpe_correlation'] > 0 else 'FAIL ✗'} (target >0)")
    print(f"  Corr with H-019: {corr_res['corr_with_h019']:.3f} "
          f"{'REDUNDANT ✗' if abs(corr_res['corr_with_h019']) > 0.5 else 'INDEPENDENT ✓'} (target <0.5)")
    print(f"  Corr with H-024: {corr_res['corr_with_h024']:.3f} "
          f"{'REDUNDANT ✗' if abs(corr_res['corr_with_h024']) > 0.5 else 'INDEPENDENT ✓'} (target <0.5)")
    print(f"  Fee 1x Sharpe: {fee_res.get('sharpe_1x', -99):.3f} "
          f"{'PASS ✓' if fee_res.get('sharpe_1x', -99) > 0 else 'FAIL ✗'} (target >0)")

    # Verdict
    pass_count = sum([
        pos_pct >= 0.80,
        mean_wf_oos >= 0.5,
        wf_pos_pct >= 0.5,
        split_half["sharpe_correlation"] > 0,
        abs(corr_res["corr_with_h019"]) <= 0.5,
        abs(corr_res["corr_with_h024"]) <= 0.5,
        fee_res.get("sharpe_1x", -99) > 0,
    ])
    total_checks = 7
    verdict = "CONFIRMED" if pass_count >= 5 else "REJECTED"
    print(f"\n  CHECKS PASSED: {pass_count}/{total_checks}")
    print(f"  VERDICT: >>> {verdict} <<<")

    # -----------------------------------------------------------------------
    # Save results
    # -----------------------------------------------------------------------
    out_dir = Path(__file__).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    results_json = {
        "hypothesis": "H-112",
        "name": "Downside Beta Factor",
        "date_run": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "universe": list(closes.columns),
        "n_days": len(closes),
        "period_start": str(closes.index[0].date()),
        "period_end": str(closes.index[-1].date()),
        "fee_rate": FEE_RATE,
        "btc_down_day_pct": round(float(n_down / (n_down + n_up)), 3),
        "param_grid": {
            "lookbacks": LOOKBACKS,
            "rebal_freqs": REBAL_FREQS,
            "n_sizes": N_SIZES,
        },
        "best_params": {
            "lookback": best_lb, "rebal": best_rb, "n": best_n,
            "is_sharpe": float(best_row["sharpe"]),
            "is_annual_ret": float(best_row["annual_ret"]),
            "is_max_dd": float(best_row["max_dd"]),
        },
        "param_robustness": {
            "n_combos": len(scan_df),
            "n_positive": int((scan_df["sharpe"] > 0).sum()),
            "pct_positive": round(float(pos_pct), 3),
            "mean_sharpe": round(float(scan_df["sharpe"].mean()), 3),
            "median_sharpe": round(float(scan_df["sharpe"].median()), 3),
        },
        "walk_forward": {
            "n_folds": len(wf_df) if wf_df is not None else 0,
            "n_positive": int((wf_df["oos_sharpe"] > 0).sum()) if wf_df is not None else 0,
            "pct_positive": round(float(wf_pos_pct), 3),
            "mean_oos_sharpe": round(float(mean_wf_oos), 3),
            "folds": wf_df.to_dict("records") if wf_df is not None else [],
        },
        "split_half": split_half,
        "fee_sensitivity": fee_res,
        "factor_correlations": corr_res,
        "verdict": {
            "decision": verdict,
            "checks_passed": pass_count,
            "checks_total": total_checks,
        },
        "all_params": scan_df.drop(columns=["n_trades", "n_rebalances"], errors="ignore").to_dict("records"),
    }

    out_path = out_dir / "results.json"
    with open(out_path, "w") as f:
        json.dump(results_json, f, indent=2, default=str)
    print(f"\n  Results saved to {out_path}")


if __name__ == "__main__":
    main()
