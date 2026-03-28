"""
H-108: Overnight Gap Factor (Cross-Sectional)

Compute rolling average overnight gap for each asset:
  gap_t = (Open_t / Close_{t-1}) - 1

Assets with persistent positive gaps are being bid up overnight (demand).
Assets with persistent negative gaps are being sold overnight.
Go LONG positive gap assets, SHORT negative gap assets.

Since run_xs_factor longs the LOWEST ranking values, we pass NEGATED gap
so that the highest-gap assets get longed.

Validation: full param scan, 60/40 train/test, 6-fold walk-forward,
split-half consistency, fee sensitivity, factor correlations with
H-012 (60d momentum) and H-019 (20d volatility).

Rejection criteria (any one = REJECT):
  - < 60% params positive
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

# Parameter grid: 4 x 3 x 2 = 24 combos (but we scan both 3 and 4 for N)
GAP_LOOKBACKS = [5, 10, 20, 30]     # rolling average gap window
REBAL_FREQS   = [3, 5, 7]           # rebalance every N days
N_SIZES       = [3, 4]              # top/bottom N

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
# Overnight gap factor computation
# ---------------------------------------------------------------------------

def compute_gap_factor(opens: pd.DataFrame, closes: pd.DataFrame,
                       lookback: int) -> pd.DataFrame:
    """
    Compute rolling average overnight gap for each asset.
    gap_t = (Open_t / Close_{t-1}) - 1
    Then take rolling mean over `lookback` days.
    """
    # Shift close by 1 to get previous day's close
    prev_close = closes.shift(1)
    # Daily gap
    daily_gap = (opens / prev_close) - 1.0
    # Rolling mean of gap
    avg_gap = daily_gap.rolling(window=lookback, min_periods=max(lookback // 2, 3)).mean()
    return avg_gap


# Cache to avoid recomputing identical lookbacks
_gap_cache: dict = {}

def get_gap_factor(opens: pd.DataFrame, closes: pd.DataFrame,
                   lookback: int) -> pd.DataFrame:
    key = (id(opens), id(closes), lookback)
    if key not in _gap_cache:
        _gap_cache[key] = compute_gap_factor(opens, closes, lookback)
    return _gap_cache[key]


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
# Core backtest engine
# ---------------------------------------------------------------------------

def run_xs_factor(
    closes: pd.DataFrame,
    opens: pd.DataFrame,
    lookback: int,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    warmup: int | None = None,
    fee_rate: float = FEE_RATE,
) -> dict:
    """
    Cross-sectional strategy using overnight gap ranking.

    We NEGATE the gap factor so that run_xs_factor longs the lowest ranking
    values (which are the most positive gaps after negation).
    """
    if n_short is None:
        n_short = n_long
    if warmup is None:
        warmup = lookback + 5

    gap_factor = get_gap_factor(opens, closes, lookback)

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
            # NEGATE the gap factor: highest gap -> most negative rank -> longed
            ranks = -gap_factor.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # Sort ascending: lowest values (most positive gap after negation) get longed
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

def run_full_scan(closes: pd.DataFrame, opens: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-108: OVERNIGHT GAP FACTOR -- Full Param Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per trade")

    # Pre-compute gap factor for all lookbacks
    for lb in GAP_LOOKBACKS:
        get_gap_factor(opens, closes, lb)
        print(f"  Computed gap factor for lookback={lb}")

    results = []

    for lookback, rebal, n in product(GAP_LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = lookback + 5
        res = run_xs_factor(closes, opens, lookback, rebal, n, warmup=warmup)
        tag = f"L{lookback}_R{rebal}_N{n}"
        results.append({
            "tag": tag, "lookback": lookback, "rebal": rebal, "n": n,
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

def run_train_test(closes: pd.DataFrame, opens: pd.DataFrame):
    n = len(closes)
    split = int(n * 0.60)
    train_c = closes.iloc[:split]
    test_c  = closes.iloc[split:]
    train_o = opens.iloc[:split]
    test_o  = opens.iloc[split:]

    print(f"\n  60/40 Train/Test Split")
    print(f"    Train: {train_c.index[0].date()} to {train_c.index[-1].date()} ({len(train_c)} days)")
    print(f"    Test : {test_c.index[0].date()} to {test_c.index[-1].date()} ({len(test_c)} days)")

    # Select best params on train
    best_sharpe = -999.0
    best_params = None
    _gap_cache.clear()
    for lookback, rebal, n_long in product(GAP_LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = lookback + 5
        if warmup >= len(train_c) - 30:
            continue
        res = run_xs_factor(train_c, train_o, lookback, rebal, n_long, warmup=warmup)
        if res["sharpe"] > best_sharpe:
            best_sharpe = res["sharpe"]
            best_params = (lookback, rebal, n_long)

    lb, rb, n_long = best_params
    print(f"    Train best: L{lb}_R{rb}_N{n_long} (IS Sharpe {best_sharpe:.3f})")

    _gap_cache.clear()
    res_test = run_xs_factor(test_c, test_o, lb, rb, n_long, warmup=lb + 5)
    print(f"    Test result: Sharpe {res_test['sharpe']:.3f}, "
          f"Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}, "
          f"n_days={len(test_c)}")

    # OOS split-half (within the test set)
    n_test = len(test_c)
    mid = n_test // 2
    _gap_cache.clear()
    r1 = run_xs_factor(test_c.iloc[:mid], test_o.iloc[:mid], lb, rb, n_long,
                       warmup=lb + 5)
    _gap_cache.clear()
    r2 = run_xs_factor(test_c.iloc[mid:], test_o.iloc[mid:], lb, rb, n_long,
                       warmup=lb + 5)
    print(f"    OOS half-1 Sharpe: {r1['sharpe']:.3f}, OOS half-2 Sharpe: {r2['sharpe']:.3f}")

    return {
        "train_best_params": f"L{lb}_R{rb}_N{n_long}",
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

def run_walk_forward(closes: pd.DataFrame, opens: pd.DataFrame):
    print(f"\n  Walk-Forward ({WF_FOLDS} folds x {WF_TEST}-day test windows, IS={WF_TRAIN}d)")
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
        train_o = opens.iloc[train_start:test_start]
        test_o  = opens.iloc[test_start:test_end]

        if len(test_c) < 30 or len(train_c) < 100:
            break

        _gap_cache.clear()
        best_s = -999.0
        best_p = None
        for lookback, rebal, n_long in product(GAP_LOOKBACKS, REBAL_FREQS, N_SIZES):
            warmup = lookback + 5
            if warmup >= len(train_c) - 20:
                continue
            res = run_xs_factor(train_c, train_o, lookback, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_s:
                best_s = res["sharpe"]
                best_p = (lookback, rebal, n_long)

        if best_p is None:
            break
        lb, rb, n_long = best_p
        _gap_cache.clear()
        res = run_xs_factor(test_c, test_o, lb, rb, n_long,
                            warmup=min(lb + 5, len(test_c) // 2))

        fold_results.append({
            "fold": fold + 1,
            "test_start": test_c.index[0].strftime("%Y-%m-%d"),
            "test_end": test_c.index[-1].strftime("%Y-%m-%d"),
            "train_params": f"L{lb}_R{rb}_N{n_long}",
            "train_sharpe": round(best_s, 3),
            "oos_sharpe": res["sharpe"],
            "oos_ann_ret": res["annual_ret"],
        })
        print(f"    Fold {fold+1}: {test_c.index[0].date()} -> {test_c.index[-1].date()} "
              f"| IS best L{lb}_R{rb}_N{n_long} ({best_s:.3f}) "
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

def run_split_half(closes: pd.DataFrame, opens: pd.DataFrame):
    n = len(closes)
    mid = n // 2
    c1, c2 = closes.iloc[:mid], closes.iloc[mid:]
    o1, o2 = opens.iloc[:mid], opens.iloc[mid:]

    print(f"\n  Split-Half Consistency")
    print(f"    Half1: {c1.index[0].date()} to {c1.index[-1].date()} ({len(c1)} days)")
    print(f"    Half2: {c2.index[0].date()} to {c2.index[-1].date()} ({len(c2)} days)")

    h1_sharpes, h2_sharpes = [], []
    for lookback, rebal, n_long in product(GAP_LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = lookback + 5
        _gap_cache.clear()
        r1 = run_xs_factor(c1, o1, lookback, rebal, n_long, warmup=warmup)
        _gap_cache.clear()
        r2 = run_xs_factor(c2, o2, lookback, rebal, n_long, warmup=warmup)
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
        "sharpe_correlation": round(corr, 3),
        "both_positive_pct": round(both_pos / len(h1), 3),
        "half1_mean_sharpe": round(float(h1.mean()), 3),
        "half2_mean_sharpe": round(float(h2.mean()), 3),
    }


# ---------------------------------------------------------------------------
# Fee sensitivity
# ---------------------------------------------------------------------------

def run_fee_sensitivity(closes: pd.DataFrame, opens: pd.DataFrame,
                        best_lb: int, best_rb: int, best_n: int):
    print(f"\n  Fee Sensitivity (best params: L{best_lb}_R{best_rb}_N{best_n})")
    fee_multipliers = [1.0, 5.0]
    fee_results = {}

    for mult in fee_multipliers:
        fee = FEE_RATE * mult
        _gap_cache.clear()
        res = run_xs_factor(closes, opens, best_lb, best_rb, best_n,
                            warmup=best_lb + 5, fee_rate=fee)
        label = f"{mult:.0f}x ({fee*10000:.0f} bps)"
        fee_results[f"{mult:.0f}x"] = {
            "fee_bps": round(fee * 10000, 1),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        }
        print(f"    {label}: Sharpe {res['sharpe']:.3f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    return fee_results


# ---------------------------------------------------------------------------
# Factor correlations with H-012 (momentum) and H-019 (volatility)
# ---------------------------------------------------------------------------

def compute_factor_correlations(closes: pd.DataFrame, opens: pd.DataFrame,
                                 volumes: pd.DataFrame,
                                 best_lb: int, best_rb: int, best_n: int):
    print(f"\n  Factor Correlations")

    # Compute H-108 returns
    _gap_cache.clear()
    res_h108 = run_xs_factor(closes, opens, best_lb, best_rb, best_n,
                              warmup=best_lb + 5)
    rets_h108 = res_h108["equity"].pct_change().dropna()

    # H-012: 60-day cross-sectional momentum (long top-4 momentum, short bottom-4)
    mom60 = closes.pct_change(60)

    def run_generic_xs(closes_inner, ranking_inner, rebal_f=5, n_l=4, warmup_i=65):
        """Generic XS engine for benchmark factor comparison."""
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

    rets_h012 = run_generic_xs(closes, mom60, rebal_f=5, n_l=4, warmup_i=65)

    # H-019: 20-day volatility factor (long lowest vol, short highest vol)
    # Low vol = long, high vol = short => rank by volatility ascending (lowest gets longed)
    vol20 = closes.pct_change().rolling(20).std()
    rets_h019 = run_generic_xs(closes, vol20, rebal_f=5, n_l=4, warmup_i=25)

    common_12 = rets_h108.index.intersection(rets_h012.index)
    common_19 = rets_h108.index.intersection(rets_h019.index)

    corr_12 = float(rets_h108.loc[common_12].corr(rets_h012.loc[common_12])) if len(common_12) > 50 else 0.0
    corr_19 = float(rets_h108.loc[common_19].corr(rets_h019.loc[common_19])) if len(common_19) > 50 else 0.0

    print(f"    Correlation with H-012 (60d Momentum): {corr_12:.3f}")
    print(f"    Correlation with H-019 (20d Volatility): {corr_19:.3f}")

    return round(corr_12, 3), round(corr_19, 3)


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("H-108: Overnight Gap Factor")
    print("=" * 72)

    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")
    if len(daily) < 10:
        print("ERROR: Not enough assets. Aborting.")
        sys.exit(1)

    closes  = pd.DataFrame({sym: df["close"]  for sym, df in daily.items()})
    opens   = pd.DataFrame({sym: df["open"]   for sym, df in daily.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily.items()})
    closes  = closes.dropna(how="all").ffill().dropna()
    opens   = opens.reindex(closes.index).ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().fillna(0.0)
    # Ensure all three share the same index
    common_idx = closes.index.intersection(opens.index)
    closes  = closes.loc[common_idx]
    opens   = opens.loc[common_idx]
    volumes = volumes.loc[common_idx]
    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")

    # -----------------------------------------------------------------------
    # 1. Full scan
    # -----------------------------------------------------------------------
    _gap_cache.clear()
    scan_df = run_full_scan(closes, opens)

    pos_pct = (scan_df["sharpe"] > 0).mean()
    best_row = scan_df.nlargest(1, "sharpe").iloc[0]
    best_lb  = int(best_row["lookback"])
    best_rb  = int(best_row["rebal"])
    best_n   = int(best_row["n"])

    print(f"\n  Best params: L{best_lb}_R{best_rb}_N{best_n}"
          f", Sharpe {best_row['sharpe']:.3f}")
    print(f"  Positive params: {pos_pct:.0%}")

    # -----------------------------------------------------------------------
    # 2. 60/40 Train/Test + split-half within OOS
    # -----------------------------------------------------------------------
    _gap_cache.clear()
    tt = run_train_test(closes, opens)

    # -----------------------------------------------------------------------
    # 3. Walk-forward (6 folds)
    # -----------------------------------------------------------------------
    _gap_cache.clear()
    wf = run_walk_forward(closes, opens)

    # -----------------------------------------------------------------------
    # 4. Split-half consistency across all params
    # -----------------------------------------------------------------------
    _gap_cache.clear()
    sh = run_split_half(closes, opens)

    # -----------------------------------------------------------------------
    # 5. Fee sensitivity
    # -----------------------------------------------------------------------
    _gap_cache.clear()
    fee_sens = run_fee_sensitivity(closes, opens, tt["best_lb"], tt["best_rb"],
                                    tt["best_n"])

    # -----------------------------------------------------------------------
    # 6. Factor correlations
    # -----------------------------------------------------------------------
    _gap_cache.clear()
    corr_12, corr_19 = compute_factor_correlations(
        closes, opens, volumes, tt["best_lb"], tt["best_rb"], tt["best_n"]
    )

    # -----------------------------------------------------------------------
    # 7. Walk-forward mean OOS Sharpe
    # -----------------------------------------------------------------------
    wf_mean_sharpe = wf["oos_sharpe"].mean() if wf is not None else -99.0
    wf_pos_folds = int((wf["oos_sharpe"] > 0).sum()) if wf is not None else 0
    wf_total_folds = len(wf) if wf is not None else 0

    # -----------------------------------------------------------------------
    # FINAL SUMMARY
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("FINAL SUMMARY: H-108 Overnight Gap Factor")
    print("=" * 72)
    print(f"  Factor               : avg overnight gap (Open_t/Close_{{t-1}} - 1)")
    print(f"  Direction            : LONG positive gap, SHORT negative gap")
    print(f"  Param combos         : {len(scan_df)}")
    print(f"  % Params positive    : {pos_pct:.0%}   (threshold >=60%)")
    print(f"  Mean Sharpe (all)    : {scan_df['sharpe'].mean():.3f}")
    print(f"  Best Sharpe (full)   : {best_row['sharpe']:.3f}")
    print(f"  Best params (full)   : L{best_lb}_R{best_rb}_N{best_n}")
    print()
    print(f"  IS Sharpe            : {tt['train_sharpe']:.3f}")
    print(f"  OOS Sharpe (60/40)   : {tt['oos_sharpe']:.3f}   (threshold >=0.3)")
    print(f"  OOS Ann Return       : {tt['oos_annual_ret']:.1%}")
    print(f"  OOS Max Drawdown     : {tt['oos_max_dd']:.1%}")
    print(f"  OOS test days        : {tt['oos_n_days']}")
    print(f"  Train best params    : {tt['train_best_params']}")
    print()
    print(f"  OOS Half1 Sharpe     : {tt['oos_half1_sharpe']:.3f}")
    print(f"  OOS Half2 Sharpe     : {tt['oos_half2_sharpe']:.3f}")
    print(f"  Split-half corr (all): {sh['sharpe_correlation']:.3f}   (threshold >0)")
    print(f"  Both halves positive : {sh['both_positive_pct']:.0%}")
    print(f"  Half1 mean Sharpe    : {sh['half1_mean_sharpe']:.3f}")
    print(f"  Half2 mean Sharpe    : {sh['half2_mean_sharpe']:.3f}")
    print()
    if wf is not None:
        print(f"  Walk-forward folds   : {wf_total_folds}")
        print(f"  WF mean OOS Sharpe   : {wf_mean_sharpe:.3f}   (threshold >=0.5)")
        print(f"  WF positive folds    : {wf_pos_folds}/{wf_total_folds}")
    print()
    print(f"  Fee sensitivity:")
    for k, v in fee_sens.items():
        print(f"    {k} ({v['fee_bps']:.0f} bps): Sharpe {v['sharpe']:.3f}, "
              f"Ann {v['annual_ret']:.1%}, DD {v['max_dd']:.1%}")
    print()
    print(f"  Corr w/ H-012 (momentum) : {corr_12:.3f}  (threshold <0.5)")
    print(f"  Corr w/ H-019 (volatility): {corr_19:.3f}  (threshold <0.5)")
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
        "hypothesis": "H-108",
        "title": "Overnight Gap Factor",
        "verdict": verdict,
        "rejection_reasons": reasons,
        "best_params": f"L{tt['best_lb']}_R{tt['best_rb']}_N{tt['best_n']}",
        "pos_pct": round(float(pos_pct), 3),
        "mean_sharpe": round(float(scan_df["sharpe"].mean()), 3),
        "best_full_sharpe": round(float(best_row["sharpe"]), 3),
        "is_sharpe": tt["train_sharpe"],
        "oos_sharpe": tt["oos_sharpe"],
        "oos_annual_ret": tt["oos_annual_ret"],
        "oos_max_dd": tt["oos_max_dd"],
        "oos_n_days": tt["oos_n_days"],
        "oos_half1_sharpe": tt["oos_half1_sharpe"],
        "oos_half2_sharpe": tt["oos_half2_sharpe"],
        "split_half_corr": sh["sharpe_correlation"],
        "wf_mean_oos_sharpe": round(float(wf_mean_sharpe), 3),
        "wf_pos_folds": f"{wf_pos_folds}/{wf_total_folds}",
        "fee_sensitivity": fee_sens,
        "corr_h012": corr_12,
        "corr_h019": corr_19,
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(results_out, f, indent=2)
    print(f"\n  Results saved to {out_path}")
