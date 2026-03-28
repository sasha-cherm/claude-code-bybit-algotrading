"""
H-107: Range Compression Factor (Cross-Sectional)

Rank 14 crypto assets by ATR ratio (short ATR / long ATR).
- Low ratio = compressed range (coiling for breakout) → LONG
- High ratio = expanded range (exhaustion) → SHORT

Factor = ATR_short / ATR_long
ATR = rolling mean of max(H-L, |H-C_prev|, |L-C_prev|)

Sort ascending by factor value: lowest ratio → LONG, highest ratio → SHORT.

Validation: full param scan (~72 combos), 60/40 train/test,
6-fold walk-forward (300d train, 90d test), split-half consistency,
fee sensitivity (1x=0.06%, 5x=0.30%),
correlations with H-012 (60d momentum) and H-019 (20d volatility).

Rejection criteria (any one = REJECT):
  - < 60% params positive in best direction
  - Split-half Sharpe correlation negative
  - Walk-forward selected-params mean Sharpe < 0.5
  - Correlation with H-012 or H-019 > 0.5
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

# Parameter grid
SHORT_ATR_WINDOWS = [5, 7, 10]
LONG_ATR_WINDOWS  = [20, 30, 40, 60]
REBAL_FREQS       = [3, 5, 7]
N_SIZES           = [3, 4]
# 3 × 4 × 3 × 2 = 72 combos

# Walk-forward
WF_FOLDS = 6
WF_TRAIN = 300
WF_TEST  = 90
WF_STEP  = 90


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
# ATR computation
# ---------------------------------------------------------------------------

def compute_atr(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame,
                window: int) -> pd.DataFrame:
    """
    Compute Average True Range for each asset over a rolling window.
    ATR = rolling mean of max(H-L, |H-C_prev|, |L-C_prev|)
    """
    close_prev = close.shift(1)
    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=0).groupby(level=0).max()
    # Ensure proper alignment
    true_range = true_range.reindex(close.index)
    atr = true_range.rolling(window, min_periods=window).mean()
    return atr


# Cache to avoid recomputing identical ATR windows
_atr_cache: dict = {}

def get_atr(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame,
            window: int) -> pd.DataFrame:
    key = (id(close), window)
    if key not in _atr_cache:
        _atr_cache[key] = compute_atr(high, low, close, window)
    return _atr_cache[key]


def compute_atr_ratio(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame,
                      short_window: int, long_window: int) -> pd.DataFrame:
    """
    Compute ATR ratio = ATR_short / ATR_long for each asset.
    Low ratio = compressed range (coiling for breakout).
    High ratio = expanded range (exhaustion).
    """
    atr_short = get_atr(high, low, close, short_window)
    atr_long  = get_atr(high, low, close, long_window)
    # Avoid division by zero
    ratio = atr_short / atr_long.replace(0, np.nan)
    return ratio


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
    highs: pd.DataFrame,
    lows: pd.DataFrame,
    short_atr: int,
    long_atr: int,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    warmup: int | None = None,
    fee_rate: float = FEE_RATE,
) -> dict:
    """
    Cross-sectional strategy using ATR ratio ranking.

    Sort by ascending factor value:
    - Lowest ATR ratio (compressed range) → LONG
    - Highest ATR ratio (expanded range) → SHORT
    """
    if n_short is None:
        n_short = n_long
    if warmup is None:
        warmup = long_atr + 5

    # Compute ATR ratio
    atr_ratio = compute_atr_ratio(highs, lows, closes, short_atr, long_atr)

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
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = atr_ratio.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # Sort ascending: lowest ratio → LONG, highest ratio → SHORT
            ranked = valid.sort_values(ascending=True)
            longs  = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] =  1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

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


# ---------------------------------------------------------------------------
# Full parameter scan
# ---------------------------------------------------------------------------

def run_full_scan(closes: pd.DataFrame, highs: pd.DataFrame, lows: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-107: RANGE COMPRESSION FACTOR -- Full Param Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per trade")

    # Pre-compute ATR for all windows
    all_windows = set(SHORT_ATR_WINDOWS) | set(LONG_ATR_WINDOWS)
    for w in sorted(all_windows):
        get_atr(highs, lows, closes, w)
        print(f"  Computed ATR for window={w}")

    results = []

    for short_w, long_w, rebal, n in product(SHORT_ATR_WINDOWS, LONG_ATR_WINDOWS,
                                              REBAL_FREQS, N_SIZES):
        if short_w >= long_w:
            continue  # short must be < long
        warmup = long_w + 5
        res = run_xs_factor(closes, highs, lows, short_w, long_w, rebal, n,
                            warmup=warmup)
        tag = f"S{short_w}_L{long_w}_R{rebal}_N{n}"
        results.append({
            "tag": tag, "short_w": short_w, "long_w": long_w,
            "rebal": rebal, "n": n,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
        })

    df = pd.DataFrame(results)
    pos_pct = (df["sharpe"] > 0).mean()
    print(f"\n  Combos: {len(df)}, Positive Sharpe: {(df['sharpe']>0).sum()}/{len(df)} ({pos_pct:.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}, Median: {df['sharpe'].median():.3f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.3f}, Worst: {df['sharpe'].min():.3f}")
    print(f"  Top 5:")
    for _, row in df.nlargest(5, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    return df


# ---------------------------------------------------------------------------
# 60/40 Train / Test split
# ---------------------------------------------------------------------------

def run_train_test(closes: pd.DataFrame, highs: pd.DataFrame, lows: pd.DataFrame):
    n = len(closes)
    split = int(n * 0.60)
    train_c = closes.iloc[:split]
    test_c  = closes.iloc[split:]
    train_h = highs.iloc[:split]
    test_h  = highs.iloc[split:]
    train_l = lows.iloc[:split]
    test_l  = lows.iloc[split:]

    print(f"\n  60/40 Train/Test Split")
    print(f"    Train: {train_c.index[0].date()} to {train_c.index[-1].date()} ({len(train_c)} days)")
    print(f"    Test : {test_c.index[0].date()} to {test_c.index[-1].date()} ({len(test_c)} days)")

    # Select best params on train
    best_sharpe = -999.0
    best_params = None
    _atr_cache.clear()
    for short_w, long_w, rebal, n_long in product(SHORT_ATR_WINDOWS, LONG_ATR_WINDOWS,
                                                    REBAL_FREQS, N_SIZES):
        if short_w >= long_w:
            continue
        warmup = long_w + 5
        if warmup >= len(train_c) - 30:
            continue
        res = run_xs_factor(train_c, train_h, train_l, short_w, long_w, rebal, n_long,
                            warmup=warmup)
        if res["sharpe"] > best_sharpe:
            best_sharpe = res["sharpe"]
            best_params = (short_w, long_w, rebal, n_long)

    sw, lw, rb, n_long = best_params
    print(f"    Train best: S{sw}_L{lw}_R{rb}_N{n_long} (IS Sharpe {best_sharpe:.3f})")

    _atr_cache.clear()
    res_test = run_xs_factor(test_c, test_h, test_l, sw, lw, rb, n_long,
                             warmup=lw + 5)
    print(f"    Test result: Sharpe {res_test['sharpe']:.3f}, "
          f"Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}, "
          f"n_days={len(test_c)}")

    # OOS split-half (within the test set)
    n_test = len(test_c)
    mid = n_test // 2
    _atr_cache.clear()
    r1 = run_xs_factor(test_c.iloc[:mid], test_h.iloc[:mid], test_l.iloc[:mid],
                       sw, lw, rb, n_long, warmup=lw + 5)
    _atr_cache.clear()
    r2 = run_xs_factor(test_c.iloc[mid:], test_h.iloc[mid:], test_l.iloc[mid:],
                       sw, lw, rb, n_long, warmup=lw + 5)
    print(f"    OOS half-1 Sharpe: {r1['sharpe']:.3f}, OOS half-2 Sharpe: {r2['sharpe']:.3f}")

    return {
        "train_best_params": f"S{sw}_L{lw}_R{rb}_N{n_long}",
        "train_sharpe": round(best_sharpe, 3),
        "oos_sharpe": res_test["sharpe"],
        "oos_annual_ret": res_test["annual_ret"],
        "oos_max_dd": res_test["max_dd"],
        "oos_n_days": len(test_c),
        "oos_half1_sharpe": r1["sharpe"],
        "oos_half2_sharpe": r2["sharpe"],
        "best_sw": sw, "best_lw": lw, "best_rb": rb, "best_n": n_long,
    }


# ---------------------------------------------------------------------------
# Walk-forward with parameter selection
# ---------------------------------------------------------------------------

def run_walk_forward(closes: pd.DataFrame, highs: pd.DataFrame, lows: pd.DataFrame):
    print(f"\n  Walk-Forward (6 folds x 90-day test windows, IS=300d)")
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
        train_h = highs.iloc[train_start:test_start]
        test_h  = highs.iloc[test_start:test_end]
        train_l = lows.iloc[train_start:test_start]
        test_l  = lows.iloc[test_start:test_end]

        if len(test_c) < 30 or len(train_c) < 100:
            break

        _atr_cache.clear()
        best_s = -999.0
        best_p = None
        for short_w, long_w, rebal, n_long in product(SHORT_ATR_WINDOWS, LONG_ATR_WINDOWS,
                                                        REBAL_FREQS, N_SIZES):
            if short_w >= long_w:
                continue
            warmup = long_w + 5
            if warmup >= len(train_c) - 20:
                continue
            res = run_xs_factor(train_c, train_h, train_l, short_w, long_w, rebal, n_long,
                                warmup=warmup)
            if res["sharpe"] > best_s:
                best_s = res["sharpe"]
                best_p = (short_w, long_w, rebal, n_long)

        if best_p is None:
            break
        sw, lw, rb, n_long = best_p
        _atr_cache.clear()
        res = run_xs_factor(test_c, test_h, test_l, sw, lw, rb, n_long,
                            warmup=min(lw + 5, len(test_c) // 2))

        fold_results.append({
            "fold": fold + 1,
            "test_start": test_c.index[0].strftime("%Y-%m-%d"),
            "test_end": test_c.index[-1].strftime("%Y-%m-%d"),
            "train_params": f"S{sw}_L{lw}_R{rb}_N{n_long}",
            "train_sharpe": round(best_s, 3),
            "oos_sharpe": res["sharpe"],
            "oos_ann_ret": res["annual_ret"],
        })
        print(f"    Fold {fold+1}: {test_c.index[0].date()} -> {test_c.index[-1].date()} "
              f"| IS best S{sw}_L{lw}_R{rb}_N{n_long} ({best_s:.3f}) "
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

def run_split_half(closes: pd.DataFrame, highs: pd.DataFrame, lows: pd.DataFrame):
    n = len(closes)
    mid = n // 2
    c1, c2 = closes.iloc[:mid], closes.iloc[mid:]
    h1, h2 = highs.iloc[:mid], highs.iloc[mid:]
    l1, l2 = lows.iloc[:mid], lows.iloc[mid:]

    print(f"\n  Split-Half Consistency")
    print(f"    Half1: {c1.index[0].date()} to {c1.index[-1].date()} ({len(c1)} days)")
    print(f"    Half2: {c2.index[0].date()} to {c2.index[-1].date()} ({len(c2)} days)")

    h1_sharpes, h2_sharpes = [], []
    for short_w, long_w, rebal, n_long in product(SHORT_ATR_WINDOWS, LONG_ATR_WINDOWS,
                                                    REBAL_FREQS, N_SIZES):
        if short_w >= long_w:
            continue
        warmup = long_w + 5
        _atr_cache.clear()
        r1 = run_xs_factor(c1, h1, l1, short_w, long_w, rebal, n_long, warmup=warmup)
        _atr_cache.clear()
        r2 = run_xs_factor(c2, h2, l2, short_w, long_w, rebal, n_long, warmup=warmup)
        h1_sharpes.append(r1["sharpe"])
        h2_sharpes.append(r2["sharpe"])

    a1 = np.array(h1_sharpes)
    a2 = np.array(h2_sharpes)
    corr = float(np.corrcoef(a1, a2)[0, 1])
    both_pos = int(((a1 > 0) & (a2 > 0)).sum())
    print(f"    Sharpe corr between halves: {corr:.3f}")
    print(f"    Positive in both halves: {both_pos}/{len(a1)} ({both_pos/len(a1):.0%})")
    print(f"    Half1 mean Sharpe: {a1.mean():.3f}, Half2 mean Sharpe: {a2.mean():.3f}")

    return {
        "sharpe_correlation": round(corr, 3),
        "both_positive_pct": round(both_pos / len(a1), 3),
        "half1_mean_sharpe": round(float(a1.mean()), 3),
        "half2_mean_sharpe": round(float(a2.mean()), 3),
    }


# ---------------------------------------------------------------------------
# Fee sensitivity
# ---------------------------------------------------------------------------

def run_fee_sensitivity(closes: pd.DataFrame, highs: pd.DataFrame, lows: pd.DataFrame,
                        best_sw: int, best_lw: int, best_rb: int, best_n: int):
    print(f"\n  Fee Sensitivity (best params: S{best_sw}_L{best_lw}_R{best_rb}_N{best_n})")

    fee_levels = {
        "1x (0.06%)": FEE_RATE,
        "5x (0.30%)": 0.0030,
    }
    results = {}
    for label, fee in fee_levels.items():
        _atr_cache.clear()
        res = run_xs_factor(closes, highs, lows, best_sw, best_lw, best_rb, best_n,
                            warmup=best_lw + 5, fee_rate=fee)
        results[label] = {
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        }
        print(f"    {label}: Sharpe {res['sharpe']:.3f}, Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    return results


# ---------------------------------------------------------------------------
# Correlation with H-012 (XS Momentum) and H-019 (Low-Vol)
# ---------------------------------------------------------------------------

def compute_factor_correlations(closes: pd.DataFrame, highs: pd.DataFrame,
                                 lows: pd.DataFrame, volumes: pd.DataFrame,
                                 best_sw: int, best_lw: int, best_rb: int, best_n: int):
    print(f"\n  Factor Correlations")

    # Compute H-107 returns
    _atr_cache.clear()
    res_h107 = run_xs_factor(closes, highs, lows, best_sw, best_lw, best_rb, best_n,
                              warmup=best_lw + 5)
    rets_h107 = res_h107["equity"].pct_change().dropna()

    # H-012: 60-day cross-sectional momentum (long top-4, short bottom-4)
    def run_simple_xs(closes_inner, ranking_inner, rebal_f=5, n_l=4, warmup_i=65):
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

    # H-012: 60-day momentum
    mom60 = closes.pct_change(60)
    rets_h012 = run_simple_xs(closes, mom60, rebal_f=5, n_l=4, warmup_i=65)

    # H-019: 20-day volatility (low vol = long, high vol = short)
    # Use negative volatility as ranking so that low vol ranks high
    ret_daily = closes.pct_change()
    vol20 = ret_daily.rolling(20).std()
    rets_h019 = run_simple_xs(closes, -vol20, rebal_f=7, n_l=3, warmup_i=25)

    common_12 = rets_h107.index.intersection(rets_h012.index)
    common_19 = rets_h107.index.intersection(rets_h019.index)

    corr_12 = float(rets_h107.loc[common_12].corr(rets_h012.loc[common_12])) if len(common_12) > 50 else 0.0
    corr_19 = float(rets_h107.loc[common_19].corr(rets_h019.loc[common_19])) if len(common_19) > 50 else 0.0

    print(f"    Correlation with H-012 (XS Momentum 60d): {corr_12:.3f}")
    print(f"    Correlation with H-019 (Low-Vol 20d):     {corr_19:.3f}")

    return round(corr_12, 3), round(corr_19, 3)


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("H-107: Range Compression Factor")
    print("=" * 72)

    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")
    if len(daily) < 10:
        print("ERROR: Not enough assets. Aborting.")
        sys.exit(1)

    closes  = pd.DataFrame({sym: df["close"]  for sym, df in daily.items()})
    highs   = pd.DataFrame({sym: df["high"]   for sym, df in daily.items()})
    lows    = pd.DataFrame({sym: df["low"]    for sym, df in daily.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily.items()})

    closes  = closes.dropna(how="all").ffill().dropna()
    highs   = highs.reindex(closes.index).ffill().bfill()
    lows    = lows.reindex(closes.index).ffill().bfill()
    volumes = volumes.reindex(closes.index).ffill().fillna(0.0)
    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")

    # -----------------------------------------------------------------------
    # 1. Full scan
    # -----------------------------------------------------------------------
    _atr_cache.clear()
    scan_df = run_full_scan(closes, highs, lows)

    pos_pct = (scan_df["sharpe"] > 0).mean()
    best_row = scan_df.nlargest(1, "sharpe").iloc[0]
    best_sw  = int(best_row["short_w"])
    best_lw  = int(best_row["long_w"])
    best_rb  = int(best_row["rebal"])
    best_n   = int(best_row["n"])

    print(f"\n  Best params: S{best_sw}_L{best_lw}_R{best_rb}_N{best_n}"
          f", Sharpe {best_row['sharpe']:.3f}")
    print(f"  Positive params: {pos_pct:.0%}")

    # -----------------------------------------------------------------------
    # 2. 60/40 Train/Test
    # -----------------------------------------------------------------------
    _atr_cache.clear()
    tt = run_train_test(closes, highs, lows)

    # -----------------------------------------------------------------------
    # 3. Walk-forward (6 folds)
    # -----------------------------------------------------------------------
    _atr_cache.clear()
    wf = run_walk_forward(closes, highs, lows)

    # -----------------------------------------------------------------------
    # 4. Split-half consistency
    # -----------------------------------------------------------------------
    _atr_cache.clear()
    sh = run_split_half(closes, highs, lows)

    # -----------------------------------------------------------------------
    # 5. Fee sensitivity
    # -----------------------------------------------------------------------
    _atr_cache.clear()
    fee_sens = run_fee_sensitivity(closes, highs, lows,
                                   tt["best_sw"], tt["best_lw"], tt["best_rb"], tt["best_n"])

    # -----------------------------------------------------------------------
    # 6. Factor correlations
    # -----------------------------------------------------------------------
    _atr_cache.clear()
    corr_12, corr_19 = compute_factor_correlations(
        closes, highs, lows, volumes,
        tt["best_sw"], tt["best_lw"], tt["best_rb"], tt["best_n"]
    )

    # -----------------------------------------------------------------------
    # 7. Walk-forward mean OOS Sharpe
    # -----------------------------------------------------------------------
    wf_mean_sharpe = wf["oos_sharpe"].mean() if wf is not None else -99.0

    # -----------------------------------------------------------------------
    # 8. Final verdict
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("FINAL SUMMARY: H-107 Range Compression Factor")
    print("=" * 72)
    print(f"  Factor             : ATR_short / ATR_long")
    print(f"  Direction          : Low ratio (compressed) → LONG, High ratio (expanded) → SHORT")
    print(f"  Param combos       : {len(scan_df)}")
    print(f"  % Params positive  : {pos_pct:.0%}   (threshold >= 60%)")
    print(f"  Mean Sharpe (all)  : {scan_df['sharpe'].mean():.3f}")
    print(f"  Best Sharpe (full) : {best_row['sharpe']:.3f}")
    print(f"  Best params (full) : S{best_sw}_L{best_lw}_R{best_rb}_N{best_n}")
    print()
    print(f"  IS Sharpe (train)  : {tt['train_sharpe']:.3f}")
    print(f"  OOS Sharpe (test)  : {tt['oos_sharpe']:.3f}   (threshold >= 0.3)")
    print(f"  OOS Ann Return     : {tt['oos_annual_ret']:.1%}")
    print(f"  OOS Max Drawdown   : {tt['oos_max_dd']:.1%}")
    print(f"  OOS test days      : {tt['oos_n_days']}")
    print(f"  Best train params  : {tt['train_best_params']}")
    print()
    print(f"  OOS Half1 Sharpe   : {tt['oos_half1_sharpe']:.3f}")
    print(f"  OOS Half2 Sharpe   : {tt['oos_half2_sharpe']:.3f}")
    print(f"  Split-half corr    : {sh['sharpe_correlation']:.3f}   (threshold > 0)")
    print(f"  Both halves pos    : {sh['both_positive_pct']:.0%}")
    print()
    if wf is not None:
        print(f"  Walk-forward folds : {len(wf)}")
        print(f"  WF mean OOS Sharpe : {wf_mean_sharpe:.3f}   (threshold >= 0.5)")
        print(f"  WF positive folds  : {(wf['oos_sharpe']>0).sum()}/{len(wf)}")
    print()
    print(f"  Fee Sensitivity:")
    for label, vals in fee_sens.items():
        print(f"    {label}: Sharpe {vals['sharpe']:.3f}, Ann {vals['annual_ret']:.1%}")
    print()
    print(f"  Corr w/ H-012 (momentum): {corr_12:.3f}  (threshold < 0.5)")
    print(f"  Corr w/ H-019 (low-vol) : {corr_19:.3f}  (threshold < 0.5)")
    print()

    # Apply rejection criteria
    reasons = []
    if pos_pct < 0.60:
        reasons.append(f"< 60% params positive ({pos_pct:.0%})")
    if sh["sharpe_correlation"] <= 0:
        reasons.append(f"split-half corr non-positive ({sh['sharpe_correlation']:.3f})")
    if wf_mean_sharpe < 0.5:
        reasons.append(f"WF mean OOS Sharpe < 0.5 ({wf_mean_sharpe:.3f})")
    if abs(corr_12) > 0.5:
        reasons.append(f"corr with H-012 > 0.5 ({corr_12:.3f})")
    if abs(corr_19) > 0.5:
        reasons.append(f"corr with H-019 > 0.5 ({corr_19:.3f})")
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
        "hypothesis": "H-107",
        "title": "Range Compression Factor",
        "factor": "ATR_short / ATR_long",
        "verdict": verdict,
        "rejection_reasons": reasons,
        "n_combos": len(scan_df),
        "pos_pct": round(float(pos_pct), 3),
        "mean_sharpe": round(float(scan_df["sharpe"].mean()), 3),
        "best_full_sharpe": round(float(best_row["sharpe"]), 3),
        "best_full_params": f"S{best_sw}_L{best_lw}_R{best_rb}_N{best_n}",
        "train_best_params": tt["train_best_params"],
        "train_sharpe": tt["train_sharpe"],
        "oos_sharpe": tt["oos_sharpe"],
        "oos_annual_ret": tt["oos_annual_ret"],
        "oos_max_dd": tt["oos_max_dd"],
        "oos_n_days": tt["oos_n_days"],
        "oos_half1_sharpe": tt["oos_half1_sharpe"],
        "oos_half2_sharpe": tt["oos_half2_sharpe"],
        "split_half_corr": sh["sharpe_correlation"],
        "split_half_both_pos_pct": sh["both_positive_pct"],
        "wf_mean_oos_sharpe": round(float(wf_mean_sharpe), 3),
        "wf_positive_folds": int((wf["oos_sharpe"] > 0).sum()) if wf is not None else 0,
        "wf_total_folds": len(wf) if wf is not None else 0,
        "fee_sensitivity": {k: v for k, v in fee_sens.items()},
        "corr_h012": corr_12,
        "corr_h019": corr_19,
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(results_out, f, indent=2)
    print(f"\n  Results saved to {out_path}")
