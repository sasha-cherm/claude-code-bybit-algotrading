"""
H-141: Overnight Gap Reversion Factor — Cross-Sectional Backtest
================================================================

Idea: Assets that move significantly during low-volume "overnight" hours
tend to revert during the high-volume daytime session. In 24/7 crypto,
there is no literal overnight gap (open == prev close), so we define
"overnight" as the low-volume UTC window 00:00-08:00.

  overnight_return_t = close[07:00 UTC, day t] / open[00:00 UTC, day t] - 1

This is normalized by ATR for cross-sectional comparability:
  gap_ratio_t = overnight_return_t / ATR(atr_period)_t

Signal: Compute the rolling average SIGNED gap ratio over `lookback` days.
  - Assets with persistently NEGATIVE avg gap ratio (sold off overnight) => LONG
  - Assets with persistently POSITIVE avg gap ratio (pumped overnight) => SHORT

Rank assets cross-sectionally. LONG bottom N, SHORT top N. Equal weight.
Rebalance every R days using t-1 data. Returns measured close-to-close daily.

Parameter grid (48 combos):
  gap_lookback [3, 5, 10, 20]   -- rolling avg gap window
  atr_period   [14, 20]         -- ATR normalization period
  rebal        [3, 5, 7]        -- rebalance every N days
  N            [3, 4]           -- top/bottom N positions

Validation tests (ALL must pass for CONFIRMED):
  1. % of params with positive IS Sharpe (want >= 80%)
  2. Walk-forward: 6 folds of 120d IS / 90d OOS. Want >= 4/6 positive, mean > 0.5
  3. Split-half: Both halves positive Sharpe
  4. Correlation with H-012 (60d momentum) -- want < 0.4

Fee: 0.06% per side
Sharpe: daily mean / daily std * sqrt(365)
"""

import json
import sys
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

RESULTS_DIR = Path(__file__).resolve().parent

FEE_RATE = 0.0006       # 0.06% per side
INITIAL_CAPITAL = 10_000.0

# Parameter grid: 4 x 2 x 3 x 2 = 48 combos
GAP_LOOKBACKS = [3, 5, 10, 20]
ATR_PERIODS   = [14, 20]
REBAL_FREQS   = [3, 5, 7]
N_SIZES       = [3, 4]

# Walk-forward config
WF_FOLDS = 6
WF_TRAIN = 120   # 120-day IS
WF_TEST  = 90    # 90-day OOS
WF_STEP  = 90


# ============================================================
# Data Loading
# ============================================================

def load_data():
    """
    Load hourly + daily bars for all 14 assets.
    Returns:
      closes:    daily close DataFrame (for portfolio returns + ATR)
      highs:     daily high DataFrame
      lows:      daily low DataFrame
      overnight: daily overnight return DataFrame
                 overnight[t] = close[07:00 UTC] / open[00:00 UTC] - 1
    """
    print("  Fetching hourly + daily data for 14 assets...")
    hourly = {}
    daily_c = {}
    daily_h = {}
    daily_l = {}

    for sym in ASSETS:
        df_1h = fetch_and_cache(sym, "1h", limit_days=800)
        df_1d = fetch_and_cache(sym, "1d", limit_days=800)

        if df_1h is None or len(df_1h) < 500:
            print(f"  {sym}: insufficient hourly data — skipping")
            continue
        if df_1d is None or len(df_1d) < 200:
            print(f"  {sym}: insufficient daily data — skipping")
            continue

        hourly[sym] = df_1h
        daily_c[sym] = df_1d["close"]
        daily_h[sym] = df_1d["high"]
        daily_l[sym] = df_1d["low"]
        print(f"  {sym}: {len(df_1h)} hourly, {len(df_1d)} daily "
              f"({df_1d.index[0].date()} to {df_1d.index[-1].date()})")

    # Build daily panels
    closes = pd.DataFrame(daily_c).sort_index().dropna(how="all")
    highs  = pd.DataFrame(daily_h).sort_index().dropna(how="all")
    lows   = pd.DataFrame(daily_l).sort_index().dropna(how="all")

    # Build overnight return panel from hourly data
    # overnight_t = close[07:00 UTC on t] / open[00:00 UTC on t] - 1
    overnight_dict = {}
    for sym, df_h in hourly.items():
        df_h = df_h.copy()
        df_h.index = pd.to_datetime(df_h.index, utc=True)

        dates = df_h.index.normalize().unique()
        on_rets = {}
        for d in dates:
            t_open = d.replace(hour=0)
            t_close = d.replace(hour=7)
            if t_open in df_h.index and t_close in df_h.index:
                p_open  = df_h.loc[t_open, "open"]
                p_close = df_h.loc[t_close, "close"]
                if p_open > 0:
                    on_rets[d] = p_close / p_open - 1.0

        s = pd.Series(on_rets, name=sym)
        s.index = pd.to_datetime(s.index, utc=True)
        overnight_dict[sym] = s

    overnight = pd.DataFrame(overnight_dict).sort_index()

    # Align all panels to common dates
    common = closes.index.intersection(overnight.index).intersection(
        highs.index).intersection(lows.index)
    closes    = closes.loc[common]
    highs     = highs.loc[common]
    lows      = lows.loc[common]
    overnight = overnight.loc[common]

    print(f"\n  Daily panel:     {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Overnight panel: {len(overnight.columns)} assets, {len(overnight)} days")
    print(f"  Date range: {closes.index[0].date()} to {closes.index[-1].date()}")

    # Quick sanity: show overnight return stats
    on_mean = overnight.mean()
    on_std  = overnight.std()
    print(f"\n  Overnight return stats (annualized):")
    for sym in sorted(on_mean.index, key=lambda s: on_mean[s]):
        print(f"    {sym:12s}: mean={on_mean[sym]*365*100:+6.1f}%/yr  "
              f"std={on_std[sym]*np.sqrt(365)*100:6.1f}%/yr")

    return closes, highs, lows, overnight


# ============================================================
# Factor Computation
# ============================================================

def compute_atr(highs, lows, closes, period):
    """Compute ATR (Average True Range) for each asset."""
    prev_close = closes.shift(1)
    tr1 = highs - lows
    tr2 = (highs - prev_close).abs()
    tr3 = (lows - prev_close).abs()
    tr = pd.DataFrame(
        np.maximum(np.maximum(tr1.values, tr2.values), tr3.values),
        index=highs.index, columns=highs.columns
    )
    atr = tr.rolling(window=period, min_periods=period).mean()
    return atr


_factor_cache = {}

def compute_gap_factor(overnight, closes, highs, lows, lookback, atr_period):
    """
    Overnight Gap Reversion Factor.

    gap_ratio_t = overnight_return_t / ATR(atr_period) normalized by price

    Rolling mean over `lookback` days, then NEGATE so that:
      - Large negative overnight return (dropped overnight)
        => large positive factor => LONG (expected reversion up)
      - Large positive overnight return (gained overnight)
        => large negative factor => SHORT (expected reversion down)
    """
    key = (lookback, atr_period)
    if key in _factor_cache:
        return _factor_cache[key]

    atr = compute_atr(highs, lows, closes, atr_period)

    # Normalize overnight return by ATR/price (so it's comparable across assets)
    atr_pct = atr / closes  # ATR as fraction of price
    gap_ratio = overnight / atr_pct.replace(0, np.nan)

    # Rolling mean of signed gap ratio
    if lookback == 1:
        avg_gap = gap_ratio.copy()
    else:
        avg_gap = gap_ratio.rolling(window=lookback,
                                    min_periods=max(lookback // 2, 1)).mean()

    # Negate for reversal ranking
    factor = -avg_gap

    _factor_cache[key] = factor
    return factor


# ============================================================
# L/S Portfolio Backtest
# ============================================================

def backtest_ls(factor, closes, n_positions, rebal_freq, fee_rate=FEE_RATE):
    """
    Run a long/short equal-weight portfolio backtest.

    Signal uses factor[t-1] (lagged by 1 day to avoid lookahead).
    Returns are close-to-close on daily bars (next day's return).
    """
    returns = closes.pct_change()
    lagged_factor = factor.shift(1)

    # Align
    common_idx = returns.index.intersection(lagged_factor.index)
    returns = returns.loc[common_idx]
    lagged_factor = lagged_factor.loc[common_idx]

    # Drop rows where we don't have enough non-NaN factor values
    min_needed = 2 * n_positions
    valid_mask = lagged_factor.notna().sum(axis=1) >= min_needed
    first_valid = valid_mask.idxmax() if valid_mask.any() else None
    if first_valid is None:
        return pd.Series(dtype=float)

    start_idx = returns.index.get_loc(first_valid)
    returns = returns.iloc[start_idx:]
    lagged_factor = lagged_factor.iloc[start_idx:]

    daily_rets = []
    prev_longs = set()
    prev_shorts = set()

    for i, date in enumerate(returns.index):
        row_factor = lagged_factor.loc[date].dropna()
        row_return = returns.loc[date]

        if len(row_factor) < min_needed:
            daily_rets.append(0.0)
            continue

        # Decide if we rebalance today
        if i % rebal_freq == 0:
            ranked = row_factor.sort_values(ascending=False)
            longs = set(ranked.index[:n_positions])
            shorts = set(ranked.index[-n_positions:])
        else:
            longs = prev_longs
            shorts = prev_shorts

        # Portfolio return: equal-weight L/S
        long_rets = [row_return[s] for s in longs
                     if s in row_return.index and not np.isnan(row_return[s])]
        short_rets = [row_return[s] for s in shorts
                      if s in row_return.index and not np.isnan(row_return[s])]

        if long_rets and short_rets:
            port_ret = np.mean(long_rets) - np.mean(short_rets)
        elif long_rets:
            port_ret = np.mean(long_rets)
        elif short_rets:
            port_ret = -np.mean(short_rets)
        else:
            port_ret = 0.0

        # Fee cost on rebalance days
        if i % rebal_freq == 0 and i > 0:
            new_longs = longs - prev_longs
            new_shorts = shorts - prev_shorts
            closed_longs = prev_longs - longs
            closed_shorts = prev_shorts - shorts
            n_changes = len(new_longs) + len(new_shorts) + len(closed_longs) + len(closed_shorts)
            total_positions = n_positions * 2
            turnover_frac = n_changes / total_positions if total_positions > 0 else 0
            fee_cost = turnover_frac * 2 * fee_rate
            port_ret -= fee_cost

        daily_rets.append(port_ret)
        prev_longs = longs
        prev_shorts = shorts

    return pd.Series(daily_rets, index=returns.index)


# ============================================================
# Validation Helpers
# ============================================================

def calc_sharpe(daily_returns):
    if len(daily_returns) < 30 or daily_returns.std() == 0:
        return 0.0
    return float(daily_returns.mean() / daily_returns.std() * np.sqrt(365))


def calc_annual_return(daily_returns):
    if len(daily_returns) < 30:
        return 0.0
    total = (1 + daily_returns).prod() - 1
    years = len(daily_returns) / 365
    if years <= 0:
        return 0.0
    return (1 + total) ** (1 / years) - 1


def calc_max_dd(daily_returns):
    equity = (1 + daily_returns).cumprod()
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return abs(dd.min())


# ============================================================
# H-012 Benchmark
# ============================================================

def compute_h012_returns(closes):
    """Compute H-012 (60d XS momentum) daily L/S returns."""
    returns = closes.pct_change()
    mom_60 = closes.pct_change(60)
    lagged_mom = mom_60.shift(1)

    n_positions = 4
    rebal_freq = 5
    min_needed = 2 * n_positions

    valid_mask = lagged_mom.notna().sum(axis=1) >= min_needed
    first_valid = valid_mask.idxmax() if valid_mask.any() else None
    if first_valid is None:
        return pd.Series(dtype=float)

    start_idx = returns.index.get_loc(first_valid)
    returns_slice = returns.iloc[start_idx:]
    lagged_slice = lagged_mom.iloc[start_idx:]

    daily_rets = []
    prev_longs = set()
    prev_shorts = set()

    for i, date in enumerate(returns_slice.index):
        row_mom = lagged_slice.loc[date].dropna()
        row_ret = returns_slice.loc[date]

        if len(row_mom) < min_needed:
            daily_rets.append(0.0)
            continue

        if i % rebal_freq == 0:
            ranked = row_mom.sort_values(ascending=False)
            longs = set(ranked.index[:n_positions])
            shorts = set(ranked.index[-n_positions:])
        else:
            longs = prev_longs
            shorts = prev_shorts

        long_r = [row_ret[s] for s in longs if s in row_ret.index and not np.isnan(row_ret[s])]
        short_r = [row_ret[s] for s in shorts if s in row_ret.index and not np.isnan(row_ret[s])]

        if long_r and short_r:
            port_ret = np.mean(long_r) - np.mean(short_r)
        else:
            port_ret = 0.0

        daily_rets.append(port_ret)
        prev_longs = longs
        prev_shorts = shorts

    return pd.Series(daily_rets, index=returns_slice.index)


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 70)
    print("H-141: Overnight Gap Reversion Factor — Cross-Sectional Backtest")
    print("  Using hourly data: overnight = close[07:00] / open[00:00] - 1")
    print("=" * 70)

    # Load data
    closes, highs, lows, overnight = load_data()
    n_days = len(closes)
    n_assets = len(closes.columns)
    print(f"\n  {n_assets} assets, {n_days} days\n")

    # ----------------------------------------------------------
    # 1. Full In-Sample Parameter Scan
    # ----------------------------------------------------------
    print("=" * 50)
    print("TEST 1: Full In-Sample Parameter Scan")
    print("=" * 50)

    params = list(product(GAP_LOOKBACKS, ATR_PERIODS, REBAL_FREQS, N_SIZES))
    print(f"  {len(params)} parameter combinations\n")

    results = []
    for lookback, atr_period, rebal, n in params:
        factor = compute_gap_factor(overnight, closes, highs, lows, lookback, atr_period)
        daily_rets = backtest_ls(factor, closes, n, rebal)
        if len(daily_rets) < 60:
            continue

        sr = calc_sharpe(daily_rets)
        ar = calc_annual_return(daily_rets)
        mdd = calc_max_dd(daily_rets)

        results.append({
            "lookback": lookback,
            "atr_period": atr_period,
            "rebal": rebal,
            "n": n,
            "sharpe": sr,
            "annual_return": ar,
            "max_dd": mdd,
            "n_days": len(daily_rets),
            "daily_rets": daily_rets,
        })

    if not results:
        print("  ERROR: No valid results from parameter scan")
        return

    sharpes = [r["sharpe"] for r in results]
    n_positive = sum(1 for s in sharpes if s > 0)
    pct_positive = n_positive / len(sharpes) * 100

    results.sort(key=lambda x: x["sharpe"], reverse=True)

    print(f"  Results: {len(results)} valid param combos")
    print(f"  Positive Sharpe: {n_positive}/{len(results)} ({pct_positive:.1f}%)")
    print(f"  Mean Sharpe:     {np.mean(sharpes):.3f}")
    print(f"  Median Sharpe:   {np.median(sharpes):.3f}")
    print(f"  Best Sharpe:     {results[0]['sharpe']:.3f} "
          f"(L={results[0]['lookback']}, ATR={results[0]['atr_period']}, "
          f"R={results[0]['rebal']}, N={results[0]['n']})")
    print(f"  Worst Sharpe:    {results[-1]['sharpe']:.3f}")
    print(f"\n  Top 5 param combos:")
    for r in results[:5]:
        print(f"    L={r['lookback']:2d} ATR={r['atr_period']:2d} R={r['rebal']} N={r['n']} => "
              f"Sharpe={r['sharpe']:.3f}  AnnRet={r['annual_return']*100:.1f}%  "
              f"MaxDD={r['max_dd']*100:.1f}%  ({r['n_days']}d)")
    print(f"  Bottom 5 param combos:")
    for r in results[-5:]:
        print(f"    L={r['lookback']:2d} ATR={r['atr_period']:2d} R={r['rebal']} N={r['n']} => "
              f"Sharpe={r['sharpe']:.3f}  AnnRet={r['annual_return']*100:.1f}%  "
              f"MaxDD={r['max_dd']*100:.1f}%  ({r['n_days']}d)")

    test1_pass = pct_positive >= 80.0
    print(f"\n  TEST 1 {'PASS' if test1_pass else 'FAIL'}: "
          f"{pct_positive:.1f}% positive Sharpe (need >= 80%)")

    best = results[0]
    best_params = (best["lookback"], best["atr_period"], best["rebal"], best["n"])
    print(f"\n  Best params: lookback={best_params[0]}, ATR={best_params[1]}, "
          f"rebal={best_params[2]}, N={best_params[3]}")

    # Turnover diagnostic for best params
    print(f"\n  Turnover diagnostic (best params):")
    _factor_cache.clear()
    f_diag = compute_gap_factor(overnight, closes, highs, lows, best_params[0], best_params[1])
    lagged_diag = f_diag.shift(1)
    total_changes = 0
    total_rebal = 0
    n_p = best_params[3]
    min_n = 2 * n_p
    prev_l = None
    prev_s = None
    for i in range(len(closes)):
        row = lagged_diag.iloc[i].dropna()
        if len(row) < min_n:
            continue
        if i % best_params[2] == 0:
            total_rebal += 1
            ranked = row.sort_values(ascending=False)
            cur_l = set(ranked.index[:n_p])
            cur_s = set(ranked.index[-n_p:])
            if prev_l is not None:
                changes = len(cur_l - prev_l) + len(cur_s - prev_s)
                total_changes += changes
            prev_l = cur_l
            prev_s = cur_s
    avg_turnover = total_changes / max(total_rebal - 1, 1)
    print(f"    Total rebalances: {total_rebal}")
    print(f"    Total position changes: {total_changes}")
    print(f"    Avg changes per rebal: {avg_turnover:.2f}")

    # ----------------------------------------------------------
    # 2. Walk-Forward Validation
    # ----------------------------------------------------------
    print("\n" + "=" * 50)
    print("TEST 2: Walk-Forward Validation")
    print(f"  {WF_FOLDS} folds, {WF_TRAIN}d IS / {WF_TEST}d OOS")
    print("=" * 50)

    wf_lookback = best_params[0]
    wf_atr = best_params[1]
    wf_rebal = best_params[2]
    wf_n = best_params[3]

    _factor_cache.clear()
    factor_full = compute_gap_factor(overnight, closes, highs, lows, wf_lookback, wf_atr)

    wf_oos_sharpes = []
    wf_is_sharpes = []

    for fold in range(WF_FOLDS):
        is_start = fold * WF_STEP
        is_end = is_start + WF_TRAIN
        oos_start = is_end
        oos_end = oos_start + WF_TEST

        if oos_end > n_days:
            break

        is_closes = closes.iloc[is_start:is_end]
        is_factor = factor_full.iloc[is_start:is_end]
        is_rets = backtest_ls(is_factor, is_closes, wf_n, wf_rebal)
        is_sharpe = calc_sharpe(is_rets) if len(is_rets) >= 30 else 0.0

        oos_closes = closes.iloc[oos_start:oos_end]
        oos_factor = factor_full.iloc[oos_start:oos_end]
        oos_rets = backtest_ls(oos_factor, oos_closes, wf_n, wf_rebal)
        oos_sharpe = calc_sharpe(oos_rets) if len(oos_rets) >= 30 else 0.0

        wf_is_sharpes.append(is_sharpe)
        wf_oos_sharpes.append(oos_sharpe)

        print(f"  Fold {fold+1}: IS [{is_start}-{is_end}] Sharpe={is_sharpe:.3f}  "
              f"OOS [{oos_start}-{oos_end}] Sharpe={oos_sharpe:.3f}")

    n_oos_positive = sum(1 for s in wf_oos_sharpes if s > 0)
    mean_oos_sharpe = np.mean(wf_oos_sharpes) if wf_oos_sharpes else 0.0
    n_folds_used = len(wf_oos_sharpes)

    print(f"\n  Positive OOS folds: {n_oos_positive}/{n_folds_used} (need >= 4)")
    print(f"  Mean OOS Sharpe:    {mean_oos_sharpe:.3f} (need > 0.5)")
    print(f"  Mean IS Sharpe:     {np.mean(wf_is_sharpes):.3f}")

    test2_pass = n_oos_positive >= 4 and mean_oos_sharpe > 0.5
    print(f"\n  TEST 2 {'PASS' if test2_pass else 'FAIL'}: "
          f"{n_oos_positive}/{n_folds_used} positive, mean OOS {mean_oos_sharpe:.3f}")

    # ----------------------------------------------------------
    # 3. Split-Half Stability
    # ----------------------------------------------------------
    print("\n" + "=" * 50)
    print("TEST 3: Split-Half Stability")
    print("=" * 50)

    mid = n_days // 2
    h1_closes = closes.iloc[:mid]
    h1_highs  = highs.iloc[:mid]
    h1_lows   = lows.iloc[:mid]
    h1_on     = overnight.iloc[:mid]

    h2_closes = closes.iloc[mid:]
    h2_highs  = highs.iloc[mid:]
    h2_lows   = lows.iloc[mid:]
    h2_on     = overnight.iloc[mid:]

    _factor_cache.clear()
    f_h1 = compute_gap_factor(h1_on, h1_closes, h1_highs, h1_lows, best_params[0], best_params[1])
    rets_h1 = backtest_ls(f_h1, h1_closes, best_params[3], best_params[2])
    sharpe_h1 = calc_sharpe(rets_h1)

    _factor_cache.clear()
    f_h2 = compute_gap_factor(h2_on, h2_closes, h2_highs, h2_lows, best_params[0], best_params[1])
    rets_h2 = backtest_ls(f_h2, h2_closes, best_params[3], best_params[2])
    sharpe_h2 = calc_sharpe(rets_h2)

    print(f"  H1: {h1_closes.index[0].date()} to {h1_closes.index[-1].date()} ({len(h1_closes)}d)")
    print(f"  H2: {h2_closes.index[0].date()} to {h2_closes.index[-1].date()} ({len(h2_closes)}d)")
    print(f"  H1 Sharpe: {sharpe_h1:.3f}")
    print(f"  H2 Sharpe: {sharpe_h2:.3f}")

    test3_pass = sharpe_h1 > 0 and sharpe_h2 > 0
    print(f"\n  TEST 3 {'PASS' if test3_pass else 'FAIL'}: "
          f"H1={sharpe_h1:.3f}, H2={sharpe_h2:.3f} (need both > 0)")

    # ----------------------------------------------------------
    # 4. Correlation with H-012 (60d Momentum)
    # ----------------------------------------------------------
    print("\n" + "=" * 50)
    print("TEST 4: Correlation with H-012 (60d Momentum)")
    print("=" * 50)

    _factor_cache.clear()
    factor_best = compute_gap_factor(overnight, closes, highs, lows,
                                     best_params[0], best_params[1])
    best_daily = backtest_ls(factor_best, closes, best_params[3], best_params[2])
    h012_daily = compute_h012_returns(closes)

    common = best_daily.index.intersection(h012_daily.index)
    if len(common) > 30:
        corr = best_daily.loc[common].corr(h012_daily.loc[common])
    else:
        corr = 0.0

    print(f"  Overlapping days: {len(common)}")
    print(f"  Correlation:      {corr:.3f} (need < 0.4)")

    test4_pass = abs(corr) < 0.4
    print(f"\n  TEST 4 {'PASS' if test4_pass else 'FAIL'}: corr = {corr:.3f}")

    # ----------------------------------------------------------
    # Additional Analysis
    # ----------------------------------------------------------
    print("\n" + "=" * 50)
    print("ADDITIONAL ANALYSIS")
    print("=" * 50)

    best_rets = results[0]["daily_rets"]
    print(f"\n  Best params full-sample:")
    print(f"    Sharpe:        {results[0]['sharpe']:.3f}")
    print(f"    Annual return: {results[0]['annual_return']*100:.1f}%")
    print(f"    Max drawdown:  {results[0]['max_dd']*100:.1f}%")
    print(f"    Total return:  {((1+best_rets).prod()-1)*100:.1f}%")
    print(f"    Trading days:  {len(best_rets)}")

    print(f"\n  Parameter sensitivity:")
    for param_name, param_values in [("lookback", GAP_LOOKBACKS), ("atr_period", ATR_PERIODS),
                                      ("rebal", REBAL_FREQS), ("n", N_SIZES)]:
        for val in param_values:
            subset = [r for r in results if r[param_name] == val]
            if subset:
                avg_s = np.mean([r["sharpe"] for r in subset])
                print(f"    {param_name}={val:3d}: mean Sharpe = {avg_s:.3f} ({len(subset)} combos)")

    print(f"\n  Fee sensitivity (best params):")
    for fee_mult, label in [(0, "0 bps"), (1, "6 bps (base)"), (3, "18 bps"), (5, "30 bps")]:
        _factor_cache.clear()
        f = compute_gap_factor(overnight, closes, highs, lows,
                               best_params[0], best_params[1])
        rets_fee = backtest_ls(f, closes, best_params[3], best_params[2],
                               fee_rate=FEE_RATE * fee_mult)
        sr_fee = calc_sharpe(rets_fee)
        print(f"    {label}: Sharpe = {sr_fee:.3f}")

    # ----------------------------------------------------------
    # Summary
    # ----------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY: H-141 Overnight Gap Reversion Factor")
    print("=" * 70)

    all_pass = test1_pass and test2_pass and test3_pass and test4_pass
    status = "CONFIRMED" if all_pass else "REJECTED"

    print(f"\n  Status: {status}")
    print(f"  Test 1 (IS positive %):   {'PASS' if test1_pass else 'FAIL'} "
          f"({pct_positive:.1f}% >= 80%)")
    print(f"  Test 2 (Walk-forward):    {'PASS' if test2_pass else 'FAIL'} "
          f"({n_oos_positive}/{n_folds_used} positive, mean OOS {mean_oos_sharpe:.3f})")
    print(f"  Test 3 (Split-half):      {'PASS' if test3_pass else 'FAIL'} "
          f"(H1={sharpe_h1:.3f}, H2={sharpe_h2:.3f})")
    print(f"  Test 4 (H-012 corr):      {'PASS' if test4_pass else 'FAIL'} "
          f"(corr={corr:.3f})")

    print(f"\n  Best params: lookback={best_params[0]}, ATR={best_params[1]}, "
          f"rebal={best_params[2]}, N={best_params[3]}")
    print(f"  Best IS Sharpe:  {results[0]['sharpe']:.3f}")
    print(f"  Best Ann Return: {results[0]['annual_return']*100:.1f}%")
    print(f"  Best Max DD:     {results[0]['max_dd']*100:.1f}%")

    # Save results
    save_results = {
        "hypothesis": "H-141",
        "name": "Overnight Gap Reversion Factor",
        "status": status,
        "universe": [a.replace("/USDT", "") for a in ASSETS],
        "n_assets": int(n_assets),
        "n_days": int(n_days),
        "date_range": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "n_params": len(results),
        "test_1_is_positive_pct": round(float(pct_positive), 1),
        "test_1_pass": bool(test1_pass),
        "test_2_wf_oos_positive_folds": int(n_oos_positive),
        "test_2_wf_total_folds": int(n_folds_used),
        "test_2_wf_mean_oos_sharpe": round(float(mean_oos_sharpe), 3),
        "test_2_pass": bool(test2_pass),
        "test_3_split_half_h1": round(float(sharpe_h1), 3),
        "test_3_split_half_h2": round(float(sharpe_h2), 3),
        "test_3_pass": bool(test3_pass),
        "test_4_h012_corr": round(float(corr), 3),
        "test_4_pass": bool(test4_pass),
        "best_params": {
            "lookback": int(best_params[0]),
            "atr_period": int(best_params[1]),
            "rebal": int(best_params[2]),
            "n_positions": int(best_params[3]),
        },
        "best_sharpe": round(float(results[0]["sharpe"]), 3),
        "best_annual_return": round(float(results[0]["annual_return"]), 4),
        "best_max_dd": round(float(results[0]["max_dd"]), 4),
        "mean_sharpe_all_params": round(float(np.mean(sharpes)), 3),
        "median_sharpe_all_params": round(float(np.median(sharpes)), 3),
        "turnover_avg_changes_per_rebal": round(float(avg_turnover), 2),
        "param_scan": [
            {
                "lookback": int(r["lookback"]),
                "atr_period": int(r["atr_period"]),
                "rebal": int(r["rebal"]),
                "n": int(r["n"]),
                "sharpe": round(float(r["sharpe"]), 3),
                "annual_return": round(float(r["annual_return"]), 4),
                "max_dd": round(float(r["max_dd"]), 4),
            }
            for r in results[:10]
        ],
        "walk_forward": {
            "folds": [
                {"fold": i + 1,
                 "is_sharpe": round(float(wf_is_sharpes[i]), 3),
                 "oos_sharpe": round(float(wf_oos_sharpes[i]), 3)}
                for i in range(n_folds_used)
            ],
        },
    }

    out_path = RESULTS_DIR / "results.json"
    with open(out_path, "w") as f:
        json.dump(save_results, f, indent=2)
    print(f"\n  Results saved to {out_path}")


if __name__ == "__main__":
    main()
