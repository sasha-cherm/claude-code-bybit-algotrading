"""
H-134: Overnight Gap Reversal Factor — Cross-Sectional Backtest
===============================================================

Idea: In crypto (24/7 market), compute the "overnight gap" as the return
during low-volume hours (00:00–08:00 UTC):
  overnight_return_t = close[07:00 UTC] / open[00:00 UTC] - 1

Assets that gain during low-volume overnight hours tend to REVERT during
the high-volume daytime session; assets that lose overnight tend to
REVERT upward during the day.

Signal: NEGATE the overnight return so that:
  - Biggest overnight losers (large negative gap) => HIGH factor => LONG
    (expected reversal up during the day)
  - Biggest overnight gainers (large positive gap) => LOW factor => SHORT
    (expected reversal down during the day)

The "return realized" is the daytime return:
  day_return_t = close[23:00 UTC] / open[08:00 UTC] - 1
We use the daily close-to-close as an approximation (computed on daily bars)
after computing the overnight signal on hourly data.

Implementation:
  1. Load hourly bars for 14 assets
  2. For each day, compute overnight return = close[07:00] / open[00:00] - 1
  3. Smooth with rolling mean (lookback window)
  4. Rank assets cross-sectionally and go long bottom N (expected up), short top N
  5. Returns are measured close-to-close on DAILY bars (next day's return)
     so we use: signal on day T (derived from hours 00-07 UTC)
                return realized on day T (full day close-to-close)

Parameter grid:
  gap_lookback [1, 3, 5, 10]  — rolling average overnight gap window
  rebal [1, 3, 5]             — rebalance every N days
  N [3, 4, 5]                 — top/bottom N positions

Validation:
  1. In-sample full param scan (% positive Sharpe, mean Sharpe)
  2. 60/40 train/test split
  3. Walk-forward (6 folds x 90-day test, 300-day train)
  4. Split-half stability
  5. Fee sensitivity (1x, 5x)
  6. Correlation with H-012 (60d momentum) and H-019 (20d volatility)

Rejection criteria (any one = REJECT):
  - < 60% params positive Sharpe
  - Split-half Sharpe correlation <= 0
  - Walk-forward mean OOS Sharpe < 0.5
  - Correlation with H-012 > 0.5
  - OOS Sharpe (60/40) < 0.3

Fee: 0.06% round-trip (6 bps)
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
from lib.metrics import sharpe_ratio, max_drawdown, annual_return, total_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]
RESULTS_DIR = Path(__file__).resolve().parent

FEE_RATE = 0.0006       # 0.06% round-trip (6 bps)
INITIAL_CAPITAL = 10_000.0

# Parameter grid: 4 x 3 x 3 = 36 combos
GAP_LOOKBACKS = [1, 3, 5, 10]    # rolling average overnight-gap window
REBAL_FREQS   = [1, 3, 5]        # rebalance every N days
N_SIZES       = [3, 4, 5]        # top/bottom N positions

# Walk-forward config
WF_FOLDS = 6
WF_TRAIN  = 300
WF_TEST   = 90
WF_STEP   = 90


# ============================================================
# Data Loading
# ============================================================

def load_data():
    """
    Load hourly bars for signal + daily bars for portfolio returns.
    Returns:
      closes: daily close DataFrame (aligned, date-indexed)
      overnight: daily overnight return DataFrame (date-indexed)
               overnight[t] = close[07:00 UTC on t] / open[00:00 UTC on t] - 1
    """
    print("  Fetching hourly data (for overnight signal)...")
    hourly = {}
    daily  = {}

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
        daily[sym]  = df_1d["close"]
        print(f"  {sym}: {len(df_1h)} hourly bars, {len(df_1d)} daily bars "
              f"({df_1d.index[0].date()} to {df_1d.index[-1].date()})")

    # Build daily close panel
    closes = pd.DataFrame(daily).sort_index().dropna(how="all")
    print(f"\n  Daily close panel: {len(closes.columns)} assets, {len(closes)} days")

    # Build overnight return panel from hourly data
    # overnight_t = close[07:00 UTC on t] / open[00:00 UTC on t] - 1
    overnight_dict = {}
    for sym, df_h in hourly.items():
        df_h.index = pd.to_datetime(df_h.index, utc=True)

        # For each calendar date, get open[00:00] and close[07:00]
        dates = df_h.index.normalize().unique()
        on_rets = {}
        for d in dates:
            t_open = d.replace(hour=0)
            t_close = d.replace(hour=7)
            if t_open in df_h.index and t_close in df_h.index:
                p_open  = df_h.loc[t_open,  "open"]
                p_close = df_h.loc[t_close, "close"]
                on_rets[d] = p_close / p_open - 1.0

        s = pd.Series(on_rets, name=sym)
        s.index = pd.to_datetime(s.index, utc=True)
        overnight_dict[sym] = s

    overnight = pd.DataFrame(overnight_dict).sort_index()

    # Align overnight and closes to the same set of dates
    common = closes.index.intersection(overnight.index)
    closes    = closes.loc[common]
    overnight = overnight.loc[common]

    print(f"  Overnight panel:    {len(overnight.columns)} assets, {len(overnight)} days")
    print(f"  Date range: {closes.index[0].date()} to {closes.index[-1].date()}")

    return closes, overnight


# ============================================================
# Gap Factor
# ============================================================

_gap_cache: dict = {}

def compute_gap_factor(overnight: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    Overnight Gap Reversal Factor.

    raw_gap[t] = close[07:00] / open[00:00] - 1

    Rolling mean over `lookback` days, then NEGATE so that:
      - Large negative overnight return (dropped overnight)
        => large positive factor => LONG (expected reversal up)
      - Large positive overnight return (gained overnight)
        => large negative factor => SHORT (expected reversal down)
    """
    if lookback == 1:
        avg_gap = overnight.copy()
    else:
        avg_gap = overnight.rolling(window=lookback,
                                    min_periods=max(lookback // 2, 1)).mean()
    # Negate for reversal ranking
    return -avg_gap


def get_gap_factor(overnight: pd.DataFrame, lookback: int) -> pd.DataFrame:
    key = (id(overnight), lookback)
    if key not in _gap_cache:
        _gap_cache[key] = compute_gap_factor(overnight, lookback)
    return _gap_cache[key]


# ============================================================
# Metrics Helper
# ============================================================

def compute_metrics(equity_series: pd.Series) -> dict:
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99.0, "annual_ret": 0.0, "max_dd": 1.0, "win_rate": 0.0}
    rets = eq.pct_change().dropna()
    n_pos = int((rets > 0).sum())
    n_total = len(rets)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(365)) if rets.std() > 0 else 0.0
    return {
        "sharpe":     round(sharpe, 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd":     round(max_drawdown(eq), 4),
        "win_rate":   round(n_pos / n_total, 4) if n_total > 0 else 0.0,
    }


# ============================================================
# Core Backtest Engine
# ============================================================

def run_xs_factor(
    closes: pd.DataFrame,
    overnight: pd.DataFrame,
    lookback: int,
    rebal_freq: int,
    n_positions: int,
    warmup: int | None = None,
    fee_rate: float = FEE_RATE,
) -> dict:
    """
    Cross-sectional long/short factor backtest.

    Signal at end of day t (computed from overnight hours of day t):
      - High factor (big down-gap overnight) => LONG next day
      - Low factor  (big up-gap overnight)   => SHORT next day

    Returns are measured daily close-to-close (day t+1 return).
    """
    if warmup is None:
        warmup = lookback + 5

    factor = get_gap_factor(overnight, lookback)

    n = len(closes)
    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count  = 0

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            # Use factor from YESTERDAY (known before today's trading)
            ranks = factor.iloc[i - 1]
            valid = ranks.dropna()

            if len(valid) < n_positions * 2:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # Descending sort: highest factor (most negative overnight = expect up)
            ranked = valid.sort_values(ascending=False)
            longs  = ranked.index[:n_positions]   # biggest down-gappers => long
            shorts = ranked.index[-n_positions:]  # biggest up-gappers   => short

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] =  1.0 / n_positions
            for sym in shorts:
                new_weights[sym] = -1.0 / n_positions

            weight_changes = (new_weights - prev_weights).abs()
            turnover       = weight_changes.sum() / 2.0
            fee_drag       = turnover * fee_rate

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


# ============================================================
# Full Parameter Scan
# ============================================================

def run_full_scan(closes: pd.DataFrame, overnight: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 72)
    print("H-134: Overnight Gap REVERSAL Factor — Full Param Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per trade")

    for lb in GAP_LOOKBACKS:
        get_gap_factor(overnight, lb)
        print(f"  Pre-computed gap factor for lookback={lb}")

    results = []
    for lookback, rebal, n in product(GAP_LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = lookback + 5
        res = run_xs_factor(closes, overnight, lookback, rebal, n, warmup=warmup)
        tag = f"L{lookback}_R{rebal}_N{n}"
        results.append({
            "tag": tag, "lookback": lookback, "rebal": rebal, "n": n,
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
            "win_rate":   res["win_rate"],
            "n_trades":   res["n_trades"],
        })

    df = pd.DataFrame(results)
    pos_pct = (df["sharpe"] > 0).mean()
    print(f"\n  Combos: {len(df)}, Positive Sharpe: {(df['sharpe']>0).sum()}/{len(df)} ({pos_pct:.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}, Median: {df['sharpe'].median():.3f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.3f}, Worst: {df['sharpe'].min():.3f}")

    print(f"\n  By lookback:")
    for lb in GAP_LOOKBACKS:
        sub = df[df["lookback"] == lb]
        print(f"    LB={lb:>2}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"{(sub['sharpe']>0).sum()}/{len(sub)} positive")

    print(f"\n  By rebalance frequency:")
    for rb in REBAL_FREQS:
        sub = df[df["rebal"] == rb]
        print(f"    R={rb}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"{(sub['sharpe']>0).sum()}/{len(sub)} positive")

    print(f"\n  By N positions:")
    for n in N_SIZES:
        sub = df[df["n"] == n]
        print(f"    N={n}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"{(sub['sharpe']>0).sum()}/{len(sub)} positive")

    print(f"\n  Top 10 combos:")
    for _, row in df.nlargest(10, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}")

    return df


# ============================================================
# 60/40 Train / Test Split
# ============================================================

def run_train_test(closes: pd.DataFrame, overnight: pd.DataFrame) -> dict:
    n = len(closes)
    split = int(n * 0.60)
    train_c = closes.iloc[:split]
    test_c  = closes.iloc[split:]
    train_on = overnight.iloc[:split]
    test_on  = overnight.iloc[split:]

    print(f"\n  60/40 Train/Test Split")
    print(f"    Train: {train_c.index[0].date()} to {train_c.index[-1].date()} ({len(train_c)} days)")
    print(f"    Test : {test_c.index[0].date()} to {test_c.index[-1].date()} ({len(test_c)} days)")

    best_sharpe = -999.0
    best_params = None
    _gap_cache.clear()

    for lookback, rebal, n_long in product(GAP_LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = lookback + 5
        if warmup >= len(train_c) - 30:
            continue
        res = run_xs_factor(train_c, train_on, lookback, rebal, n_long, warmup=warmup)
        if res["sharpe"] > best_sharpe:
            best_sharpe = res["sharpe"]
            best_params = (lookback, rebal, n_long)

    lb, rb, n_long = best_params
    print(f"    Train best: L{lb}_R{rb}_N{n_long} (IS Sharpe {best_sharpe:.3f})")

    _gap_cache.clear()
    res_test = run_xs_factor(test_c, test_on, lb, rb, n_long, warmup=lb + 5)
    print(f"    Test result: Sharpe {res_test['sharpe']:.3f}, "
          f"Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}, "
          f"n_days={len(test_c)}")

    # Split-half of test set
    n_test = len(test_c)
    mid = n_test // 2
    _gap_cache.clear()
    r1 = run_xs_factor(test_c.iloc[:mid], test_on.iloc[:mid], lb, rb, n_long,
                       warmup=lb + 5)
    _gap_cache.clear()
    r2 = run_xs_factor(test_c.iloc[mid:], test_on.iloc[mid:], lb, rb, n_long,
                       warmup=lb + 5)
    print(f"    OOS half-1 Sharpe: {r1['sharpe']:.3f}, OOS half-2 Sharpe: {r2['sharpe']:.3f}")

    return {
        "train_best_params": f"L{lb}_R{rb}_N{n_long}",
        "train_sharpe":  round(best_sharpe, 3),
        "oos_sharpe":    res_test["sharpe"],
        "oos_annual_ret": res_test["annual_ret"],
        "oos_max_dd":    res_test["max_dd"],
        "oos_n_days":    len(test_c),
        "oos_half1_sharpe": r1["sharpe"],
        "oos_half2_sharpe": r2["sharpe"],
        "best_lb": lb, "best_rb": rb, "best_n": n_long,
    }


# ============================================================
# Walk-Forward (6 folds)
# ============================================================

def run_walk_forward(closes: pd.DataFrame, overnight: pd.DataFrame) -> pd.DataFrame | None:
    print(f"\n  Walk-Forward ({WF_FOLDS} folds x {WF_TEST}-day test, IS={WF_TRAIN}d)")
    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end   = n - fold * WF_STEP
        test_start = test_end - WF_TEST
        train_start= test_start - WF_TRAIN
        if train_start < 0 or test_start < 0 or test_end > n:
            break

        train_c  = closes.iloc[train_start:test_start]
        test_c   = closes.iloc[test_start:test_end]
        train_on = overnight.iloc[train_start:test_start]
        test_on  = overnight.iloc[test_start:test_end]

        if len(test_c) < 30 or len(train_c) < 100:
            break

        _gap_cache.clear()
        best_s = -999.0
        best_p = None
        for lookback, rebal, n_long in product(GAP_LOOKBACKS, REBAL_FREQS, N_SIZES):
            warmup = lookback + 5
            if warmup >= len(train_c) - 20:
                continue
            res = run_xs_factor(train_c, train_on, lookback, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_s:
                best_s = res["sharpe"]
                best_p = (lookback, rebal, n_long)

        if best_p is None:
            break
        lb, rb, n_long = best_p
        _gap_cache.clear()
        res = run_xs_factor(test_c, test_on, lb, rb, n_long,
                            warmup=min(lb + 5, len(test_c) // 2))

        fold_results.append({
            "fold": fold + 1,
            "test_start": test_c.index[0].strftime("%Y-%m-%d"),
            "test_end":   test_c.index[-1].strftime("%Y-%m-%d"),
            "train_params": f"L{lb}_R{rb}_N{n_long}",
            "train_sharpe": round(best_s, 3),
            "oos_sharpe":   res["sharpe"],
            "oos_ann_ret":  res["annual_ret"],
        })
        print(f"    Fold {fold+1}: {test_c.index[0].date()} -> {test_c.index[-1].date()} "
              f"| IS best L{lb}_R{rb}_N{n_long} ({best_s:.3f}) "
              f"| OOS {res['sharpe']:.3f}")

    if not fold_results:
        return None
    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe"] > 0).sum()
    mean_oos = df["oos_sharpe"].mean()
    print(f"    Positive OOS folds: {pos}/{len(df)}, Mean OOS Sharpe: {mean_oos:.3f}")
    return df


# ============================================================
# Split-Half Consistency Across All Params
# ============================================================

def run_split_half(closes: pd.DataFrame, overnight: pd.DataFrame) -> dict:
    n = len(closes)
    mid = n // 2
    c1, c2   = closes.iloc[:mid],    closes.iloc[mid:]
    on1, on2 = overnight.iloc[:mid], overnight.iloc[mid:]

    print(f"\n  Split-Half Consistency")
    print(f"    Half1: {c1.index[0].date()} to {c1.index[-1].date()} ({len(c1)} days)")
    print(f"    Half2: {c2.index[0].date()} to {c2.index[-1].date()} ({len(c2)} days)")

    h1_sharpes, h2_sharpes = [], []
    for lookback, rebal, n_long in product(GAP_LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = lookback + 5
        _gap_cache.clear()
        r1 = run_xs_factor(c1, on1, lookback, rebal, n_long, warmup=warmup)
        _gap_cache.clear()
        r2 = run_xs_factor(c2, on2, lookback, rebal, n_long, warmup=warmup)
        h1_sharpes.append(r1["sharpe"])
        h2_sharpes.append(r2["sharpe"])

    h1 = np.array(h1_sharpes)
    h2 = np.array(h2_sharpes)
    corr = float(np.corrcoef(h1, h2)[0, 1])
    both_pos = int(((h1 > 0) & (h2 > 0)).sum())
    print(f"    Sharpe corr between halves: {corr:.3f}")
    print(f"    Positive in both halves: {both_pos}/{len(h1)} ({both_pos/len(h1):.0%})")
    print(f"    Half1 mean Sharpe: {h1.mean():.3f}, Half2 mean Sharpe: {h2.mean():.3f}")

    return {
        "sharpe_correlation":  round(corr, 3),
        "both_positive_pct":   round(both_pos / len(h1), 3),
        "half1_mean_sharpe":   round(float(h1.mean()), 3),
        "half2_mean_sharpe":   round(float(h2.mean()), 3),
    }


# ============================================================
# Fee Sensitivity
# ============================================================

def run_fee_sensitivity(closes: pd.DataFrame, overnight: pd.DataFrame,
                        best_lb: int, best_rb: int, best_n: int) -> dict:
    print(f"\n  Fee Sensitivity (best params: L{best_lb}_R{best_rb}_N{best_n})")
    fee_results = {}
    for mult in [1.0, 5.0]:
        fee = FEE_RATE * mult
        _gap_cache.clear()
        res = run_xs_factor(closes, overnight, best_lb, best_rb, best_n,
                            warmup=best_lb + 5, fee_rate=fee)
        label = f"{mult:.0f}x"
        fee_results[label] = {
            "fee_bps":    round(fee * 10000, 1),
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
        }
        print(f"    {mult:.0f}x ({fee*10000:.0f} bps): Sharpe {res['sharpe']:.3f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")
    return fee_results


# ============================================================
# Factor Correlations: H-012 (momentum) and H-019 (volatility)
# ============================================================

def compute_factor_correlations(closes: pd.DataFrame, overnight: pd.DataFrame,
                                 best_lb: int, best_rb: int, best_n: int):
    print(f"\n  Factor Correlations")

    _gap_cache.clear()
    res_h134 = run_xs_factor(closes, overnight, best_lb, best_rb, best_n,
                              warmup=best_lb + 5)
    rets_h134 = res_h134["equity"].pct_change().dropna()

    def run_generic_xs(closes_inner, ranking_inner, rebal_f=5, n_l=4, warmup_i=65):
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

    # H-012: 60-day cross-sectional momentum
    mom60 = closes.pct_change(60)
    rets_h012 = run_generic_xs(closes, mom60, rebal_f=5, n_l=4, warmup_i=65)

    # H-019: 20-day volatility (long lowest vol => pass negative vol)
    vol20 = closes.pct_change().rolling(20).std()
    rets_h019 = run_generic_xs(closes, -vol20, rebal_f=5, n_l=4, warmup_i=25)

    common_12 = rets_h134.index.intersection(rets_h012.index)
    common_19 = rets_h134.index.intersection(rets_h019.index)

    corr_12 = float(rets_h134.loc[common_12].corr(rets_h012.loc[common_12])) \
              if len(common_12) > 50 else 0.0
    corr_19 = float(rets_h134.loc[common_19].corr(rets_h019.loc[common_19])) \
              if len(common_19) > 50 else 0.0

    print(f"    Correlation with H-012 (60d Momentum): {corr_12:.3f}")
    print(f"    Correlation with H-019 (20d Volatility): {corr_19:.3f}")

    return round(corr_12, 3), round(corr_19, 3)


# ============================================================
# Overnight Gap Distribution Analysis
# ============================================================

def analyze_gap_distribution(overnight: pd.DataFrame) -> None:
    flat = overnight.values.flatten()
    flat = flat[~np.isnan(flat)]

    print(f"\n  Overnight Return Distribution (00:00–07:00 UTC):")
    print(f"    Count  : {len(flat):,}")
    print(f"    Mean   : {flat.mean()*100:.4f}%")
    print(f"    Std    : {flat.std()*100:.3f}%")
    print(f"    Median : {np.median(flat)*100:.4f}%")
    print(f"    P5     : {np.percentile(flat, 5)*100:.3f}%")
    print(f"    P95    : {np.percentile(flat, 95)*100:.3f}%")
    print(f"    Min    : {flat.min()*100:.3f}%")
    print(f"    Max    : {flat.max()*100:.3f}%")
    pct_pos = (flat > 0).mean()
    print(f"    % positive overnight: {pct_pos:.1%}")

    print(f"\n  Average overnight return per asset (all history):")
    avg = overnight.mean().sort_values()
    for sym, val in avg.items():
        print(f"    {sym:>12}: {val*100:+.4f}%")

    # Autocorrelation: does yesterday's overnight predict today's?
    print(f"\n  Lag-1 autocorrelation of overnight returns (mean across assets):")
    acfs = []
    for col in overnight.columns:
        s = overnight[col].dropna()
        if len(s) > 10:
            acfs.append(s.autocorr(lag=1))
    print(f"    Mean autocorr: {np.mean(acfs):.4f}, Std: {np.std(acfs):.4f}")
    for col, acf in zip(overnight.columns, acfs):
        print(f"    {col:>12}: {acf:+.4f}")

    # Predictive: does overnight return predict same-day daytime return?
    # Approximate daytime as: negative of overnight (reversal test)
    # We measure this separately via the backtest
    print(f"\n  Overnight vs next-day correlation (info about predictability):")
    print(f"    [This is captured in the backtest itself via the reversal signal]")


# ============================================================
# Main Driver
# ============================================================

if __name__ == "__main__":
    print("=" * 72)
    print("H-134: Overnight Gap REVERSAL Factor")
    print("Signal: 00:00-07:00 UTC return; long down-gappers, short up-gappers")
    print("=" * 72)

    print("\nLoading data...")
    closes, overnight = load_data()

    if len(closes.columns) < 10:
        print("ERROR: Not enough assets. Aborting.")
        sys.exit(1)

    # ----------------------------------------------------------------
    # 0. Gap distribution analysis
    # ----------------------------------------------------------------
    analyze_gap_distribution(overnight)

    # ----------------------------------------------------------------
    # 1. Full parameter scan
    # ----------------------------------------------------------------
    _gap_cache.clear()
    scan_df = run_full_scan(closes, overnight)

    pos_pct  = (scan_df["sharpe"] > 0).mean()
    best_row = scan_df.nlargest(1, "sharpe").iloc[0]
    best_lb  = int(best_row["lookback"])
    best_rb  = int(best_row["rebal"])
    best_n   = int(best_row["n"])
    print(f"\n  Best params: L{best_lb}_R{best_rb}_N{best_n}, Sharpe {best_row['sharpe']:.3f}")
    print(f"  Positive params: {pos_pct:.0%}")

    # ----------------------------------------------------------------
    # 2. 60/40 Train/Test
    # ----------------------------------------------------------------
    _gap_cache.clear()
    tt = run_train_test(closes, overnight)

    # ----------------------------------------------------------------
    # 3. Walk-Forward (6 folds)
    # ----------------------------------------------------------------
    _gap_cache.clear()
    wf = run_walk_forward(closes, overnight)

    # ----------------------------------------------------------------
    # 4. Split-Half Consistency
    # ----------------------------------------------------------------
    _gap_cache.clear()
    sh = run_split_half(closes, overnight)

    # ----------------------------------------------------------------
    # 5. Fee Sensitivity
    # ----------------------------------------------------------------
    _gap_cache.clear()
    fee_sens = run_fee_sensitivity(closes, overnight,
                                   tt["best_lb"], tt["best_rb"], tt["best_n"])

    # ----------------------------------------------------------------
    # 6. Factor Correlations
    # ----------------------------------------------------------------
    _gap_cache.clear()
    corr_12, corr_19 = compute_factor_correlations(
        closes, overnight, tt["best_lb"], tt["best_rb"], tt["best_n"]
    )

    # ----------------------------------------------------------------
    # Aggregated WF stats
    # ----------------------------------------------------------------
    if wf is not None:
        wf_mean_sharpe = wf["oos_sharpe"].mean()
        wf_pos_folds   = int((wf["oos_sharpe"] > 0).sum())
        wf_total_folds = len(wf)
    else:
        wf_mean_sharpe = -99.0
        wf_pos_folds   = 0
        wf_total_folds = 0

    # ----------------------------------------------------------------
    # FINAL SUMMARY
    # ----------------------------------------------------------------
    print("\n" + "=" * 72)
    print("FINAL SUMMARY: H-134 Overnight Gap Reversal Factor")
    print("=" * 72)
    print(f"  Factor              : negated overnight return (00:00-07:00 UTC)")
    print(f"  Direction           : LONG biggest down-gappers, SHORT biggest up-gappers")
    print(f"  Param combos        : {len(scan_df)}")
    print(f"  % Params positive   : {pos_pct:.0%}   (threshold >=60%)")
    print(f"  Mean Sharpe (all)   : {scan_df['sharpe'].mean():.3f}")
    print(f"  Best Sharpe (full)  : {best_row['sharpe']:.3f}")
    print(f"  Best params (full)  : L{best_lb}_R{best_rb}_N{best_n}")
    print()
    print(f"  IS Sharpe           : {tt['train_sharpe']:.3f}")
    print(f"  OOS Sharpe (60/40)  : {tt['oos_sharpe']:.3f}   (threshold >=0.3)")
    print(f"  OOS Ann Return      : {tt['oos_annual_ret']:.1%}")
    print(f"  OOS Max Drawdown    : {tt['oos_max_dd']:.1%}")
    print(f"  OOS test days       : {tt['oos_n_days']}")
    print(f"  Train best params   : {tt['train_best_params']}")
    print()
    print(f"  OOS Half1 Sharpe    : {tt['oos_half1_sharpe']:.3f}")
    print(f"  OOS Half2 Sharpe    : {tt['oos_half2_sharpe']:.3f}")
    print(f"  Split-half corr     : {sh['sharpe_correlation']:.3f}   (threshold >0)")
    print(f"  Both halves positive: {sh['both_positive_pct']:.0%}")
    print(f"  Half1 mean Sharpe   : {sh['half1_mean_sharpe']:.3f}")
    print(f"  Half2 mean Sharpe   : {sh['half2_mean_sharpe']:.3f}")
    print()
    if wf is not None:
        print(f"  Walk-forward folds  : {wf_total_folds}")
        print(f"  WF mean OOS Sharpe  : {wf_mean_sharpe:.3f}   (threshold >=0.5)")
        print(f"  WF positive folds   : {wf_pos_folds}/{wf_total_folds}")
    print()
    print(f"  Fee sensitivity:")
    for k, v in fee_sens.items():
        print(f"    {k} ({v['fee_bps']:.0f} bps): Sharpe {v['sharpe']:.3f}, "
              f"Ann {v['annual_ret']:.1%}, DD {v['max_dd']:.1%}")
    print()
    print(f"  Corr w/ H-012 (momentum)  : {corr_12:.3f}  (threshold <0.5)")
    print(f"  Corr w/ H-019 (volatility): {corr_19:.3f}  (threshold <0.5)")
    print()

    # ----------------------------------------------------------------
    # Rejection criteria
    # ----------------------------------------------------------------
    reasons = []
    if pos_pct < 0.60:
        reasons.append(f"< 60% params positive ({pos_pct:.0%})")
    if sh["sharpe_correlation"] <= 0:
        reasons.append(f"split-half corr non-positive ({sh['sharpe_correlation']:.3f})")
    if wf_mean_sharpe < 0.5:
        reasons.append(f"WF mean OOS Sharpe < 0.5 ({wf_mean_sharpe:.3f})")
    if abs(corr_12) > 0.5:
        reasons.append(f"corr with H-012 > 0.5 ({corr_12:.3f})")
    if tt["oos_sharpe"] < 0.3:
        reasons.append(f"OOS Sharpe < 0.3 ({tt['oos_sharpe']:.3f})")

    verdict = "REJECTED" if reasons else "CONFIRMED"
    print(f"  VERDICT: {verdict}")
    if reasons:
        for r in reasons:
            print(f"    Reason: {r}")

    # ----------------------------------------------------------------
    # Save results
    # ----------------------------------------------------------------
    results_out = {
        "hypothesis": "H-134",
        "title": "Overnight Gap Reversal Factor",
        "run_date": str(pd.Timestamp.now().date()),
        "data_range": {
            "start": str(closes.index[0].date()),
            "end":   str(closes.index[-1].date()),
            "days":  len(closes),
            "assets": int(len(closes.columns)),
        },
        "verdict": verdict,
        "rejection_reasons": reasons,
        "best_params_full": f"L{best_lb}_R{best_rb}_N{best_n}",
        "parameter_grid": {
            "total_combos":  int(len(scan_df)),
            "pos_pct":       round(float(pos_pct), 3),
            "mean_sharpe":   round(float(scan_df["sharpe"].mean()), 3),
            "median_sharpe": round(float(scan_df["sharpe"].median()), 3),
            "best_sharpe":   round(float(best_row["sharpe"]), 3),
            "worst_sharpe":  round(float(scan_df["sharpe"].min()), 3),
        },
        "train_test_60_40": {
            "best_params":      tt["train_best_params"],
            "is_sharpe":        tt["train_sharpe"],
            "oos_sharpe":       tt["oos_sharpe"],
            "oos_annual_ret":   tt["oos_annual_ret"],
            "oos_max_dd":       tt["oos_max_dd"],
            "oos_n_days":       tt["oos_n_days"],
            "oos_half1_sharpe": tt["oos_half1_sharpe"],
            "oos_half2_sharpe": tt["oos_half2_sharpe"],
        },
        "walk_forward": {
            "n_folds":          wf_total_folds,
            "n_positive_folds": wf_pos_folds,
            "mean_oos_sharpe":  round(float(wf_mean_sharpe), 3),
            "folds": wf.to_dict(orient="records") if wf is not None else [],
        },
        "split_half": {
            "sharpe_correlation": sh["sharpe_correlation"],
            "both_positive_pct":  sh["both_positive_pct"],
            "half1_mean_sharpe":  sh["half1_mean_sharpe"],
            "half2_mean_sharpe":  sh["half2_mean_sharpe"],
        },
        "fee_sensitivity": fee_sens,
        "correlations": {
            "h012_momentum":  corr_12,
            "h019_volatility": corr_19,
        },
        "all_param_results": scan_df.to_dict(orient="records"),
    }

    out_path = RESULTS_DIR / "results.json"
    with open(out_path, "w") as f:
        json.dump(results_out, f, indent=2)
    print(f"\n  Results saved to {out_path}")
