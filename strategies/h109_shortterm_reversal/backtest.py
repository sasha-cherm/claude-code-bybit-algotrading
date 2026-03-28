"""
H-109: Short-Term Reversal Factor (Cross-Sectional)

Rank 14 crypto assets by very short-term (1-5 day) returns.
REVERSAL: Long the biggest recent losers, short the biggest recent winners.
Tests whether crypto has a short-term reversal effect (liquidity provision,
overreaction correction) at very short horizons.

H-104 (RSI mean reversion at 7-21 day) was rejected with only 3% positive
params -- this tests much shorter horizons (1-5d) which might capture a
different effect (bid-ask bounce, temporary liquidity effects).

Factor computation:
  ret = (close_t / close_{t-lookback}) - 1
  REVERSAL: Long losers (most negative returns), short winners (most positive).
  In run_xs_factor (which longs lowest ranked): pass the raw return.
  Lowest return = biggest loser = LONG (correct for reversal).

Parameter grid (~48 combos):
  Return lookback: [1, 2, 3, 5]
  Rebalance frequency: [1, 2, 3, 5]
  N long/short: [3, 4, 5]

Validation: full 48-combo param scan, 60/40 train/test, 6-fold walk-forward,
split-half consistency, fee sensitivity (1x=0.06%, 5x=0.30%),
factor correlations with H-012 (60d momentum) and H-019 (20d volatility).

Rejection criteria (any one = REJECT):
  - < 60% params positive Sharpe
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
RET_LOOKBACKS = [1, 2, 3, 5]     # short-term return lookback (days)
REBAL_FREQS   = [1, 2, 3, 5]     # rebalance every N days
N_SIZES       = [3, 4, 5]         # top/bottom N
# 4 x 4 x 3 = 48 combos

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
# Core back-test engine — reversal factor
# ---------------------------------------------------------------------------

def run_xs_factor(
    closes: pd.DataFrame,
    ret_lookback: int,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    warmup: int | None = None,
    fee_rate: float = FEE_RATE,
) -> dict:
    """
    Cross-sectional reversal strategy.

    Factor = raw return over ret_lookback days.
    Sorting ascending: lowest return (biggest losers) = LONG.
    Highest return (biggest winners) = SHORT.
    This implements reversal/contrarian.
    """
    if n_short is None:
        n_short = n_long
    if warmup is None:
        warmup = ret_lookback + 5

    # Compute short-term returns as ranking signal
    ret_signal = closes.pct_change(ret_lookback)

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
            # Use lagged signal (t-1) to avoid look-ahead
            ranks = ret_signal.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # Sort ascending: lowest return first (biggest losers)
            ranked = valid.sort_values(ascending=True)
            # LONG the bottom (biggest losers) = reversal
            longs  = ranked.index[:n_long]
            # SHORT the top (biggest winners) = reversal
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

def run_full_scan(closes: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-109: SHORT-TERM REVERSAL FACTOR -- Full Param Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per trade")
    print(f"  Direction: REVERSAL (long losers, short winners)")

    results = []

    for ret_lb, rebal, n in product(RET_LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = ret_lb + 5
        res = run_xs_factor(closes, ret_lb, rebal, n, warmup=warmup)
        tag = f"L{ret_lb}_R{rebal}_N{n}"
        results.append({
            "tag": tag, "ret_lookback": ret_lb, "rebal": rebal, "n": n,
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
    print(f"\n  Top 10:")
    for _, row in df.nlargest(10, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}, Rebals {row['n_rebalances']}")

    # Show by lookback
    print(f"\n  By return lookback:")
    for lb in RET_LOOKBACKS:
        sub = df[df["ret_lookback"] == lb]
        print(f"    L{lb}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"positive {(sub['sharpe']>0).sum()}/{len(sub)} ({(sub['sharpe']>0).mean():.0%})")

    # Show by rebalance freq
    print(f"\n  By rebalance frequency:")
    for rb in REBAL_FREQS:
        sub = df[df["rebal"] == rb]
        print(f"    R{rb}: mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"positive {(sub['sharpe']>0).sum()}/{len(sub)} ({(sub['sharpe']>0).mean():.0%})")

    return df


# ---------------------------------------------------------------------------
# 60/40 Train / Test split
# ---------------------------------------------------------------------------

def run_train_test(closes: pd.DataFrame):
    n = len(closes)
    split = int(n * 0.60)
    train_c = closes.iloc[:split]
    test_c  = closes.iloc[split:]

    print(f"\n  60/40 Train/Test Split")
    print(f"    Train: {train_c.index[0].date()} to {train_c.index[-1].date()} ({len(train_c)} days)")
    print(f"    Test : {test_c.index[0].date()} to {test_c.index[-1].date()} ({len(test_c)} days)")

    # Select best params on train
    best_sharpe = -999.0
    best_params = None
    for ret_lb, rebal, n_long in product(RET_LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = ret_lb + 5
        if warmup >= len(train_c) - 30:
            continue
        res = run_xs_factor(train_c, ret_lb, rebal, n_long, warmup=warmup)
        if res["sharpe"] > best_sharpe:
            best_sharpe = res["sharpe"]
            best_params = (ret_lb, rebal, n_long)

    lb, rb, n_long = best_params
    print(f"    Train best: L{lb}_R{rb}_N{n_long} (IS Sharpe {best_sharpe:.3f})")

    res_test = run_xs_factor(test_c, lb, rb, n_long, warmup=lb + 5)
    print(f"    Test result: Sharpe {res_test['sharpe']:.3f}, "
          f"Ann {res_test['annual_ret']:.1%}, DD {res_test['max_dd']:.1%}, "
          f"n_days={len(test_c)}")

    # OOS split-half (within the test set)
    n_test = len(test_c)
    mid = n_test // 2
    r1 = run_xs_factor(test_c.iloc[:mid], lb, rb, n_long, warmup=lb + 5)
    r2 = run_xs_factor(test_c.iloc[mid:], lb, rb, n_long, warmup=lb + 5)
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

def run_walk_forward(closes: pd.DataFrame):
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

        if len(test_c) < 30 or len(train_c) < 100:
            break

        best_s = -999.0
        best_p = None
        for ret_lb, rebal, n_long in product(RET_LOOKBACKS, REBAL_FREQS, N_SIZES):
            warmup = ret_lb + 5
            if warmup >= len(train_c) - 20:
                continue
            res = run_xs_factor(train_c, ret_lb, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_s:
                best_s = res["sharpe"]
                best_p = (ret_lb, rebal, n_long)

        if best_p is None:
            break
        lb, rb, n_long = best_p
        res = run_xs_factor(test_c, lb, rb, n_long,
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

def run_split_half(closes: pd.DataFrame):
    n = len(closes)
    mid = n // 2
    c1, c2 = closes.iloc[:mid], closes.iloc[mid:]

    print(f"\n  Split-Half Consistency")
    print(f"    Half1: {c1.index[0].date()} to {c1.index[-1].date()} ({len(c1)} days)")
    print(f"    Half2: {c2.index[0].date()} to {c2.index[-1].date()} ({len(c2)} days)")

    h1_sharpes, h2_sharpes = [], []
    tags = []
    for ret_lb, rebal, n_long in product(RET_LOOKBACKS, REBAL_FREQS, N_SIZES):
        warmup = ret_lb + 5
        r1 = run_xs_factor(c1, ret_lb, rebal, n_long, warmup=warmup)
        r2 = run_xs_factor(c2, ret_lb, rebal, n_long, warmup=warmup)
        h1_sharpes.append(r1["sharpe"])
        h2_sharpes.append(r2["sharpe"])
        tags.append(f"L{ret_lb}_R{rebal}_N{n_long}")

    h1 = np.array(h1_sharpes)
    h2 = np.array(h2_sharpes)
    corr = float(np.corrcoef(h1, h2)[0, 1])
    both_pos = int(((h1 > 0) & (h2 > 0)).sum())
    print(f"    Sharpe corr between halves: {corr:.3f}")
    print(f"    Positive in both halves: {both_pos}/{len(h1)} ({both_pos/len(h1):.0%})")
    print(f"    Half1 mean Sharpe: {h1.mean():.3f}, Half2 mean Sharpe: {h2.mean():.3f}")

    # Show top/bottom for diagnostic
    df_sh = pd.DataFrame({"tag": tags, "h1": h1, "h2": h2})
    df_sh["diff"] = df_sh["h2"] - df_sh["h1"]
    print(f"    Most consistent (both halves positive, sorted by min):")
    consistent = df_sh[(df_sh["h1"] > 0) & (df_sh["h2"] > 0)].copy()
    if len(consistent) > 0:
        consistent["min_sharpe"] = consistent[["h1", "h2"]].min(axis=1)
        for _, row in consistent.nlargest(5, "min_sharpe").iterrows():
            print(f"      {row['tag']}: H1={row['h1']:.3f}, H2={row['h2']:.3f}")

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
                        best_n: int):
    print(f"\n  Fee Sensitivity (best params: L{best_lb}_R{best_rb}_N{best_n})")

    fee_multipliers = [0, 0.5, 1.0, 2.0, 3.0, 5.0]
    for mult in fee_multipliers:
        fee = FEE_RATE * mult
        res = run_xs_factor(closes, best_lb, best_rb, best_n,
                            warmup=best_lb + 5, fee_rate=fee)
        label = f"{mult:.0f}x" if mult == int(mult) else f"{mult:.1f}x"
        print(f"    Fee {label} ({fee*10000:.0f} bps): Sharpe {res['sharpe']:.3f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}, "
              f"Rebals {res['n_rebalances']}")

    # Report the 1x and 5x specifically
    res_1x = run_xs_factor(closes, best_lb, best_rb, best_n,
                           warmup=best_lb + 5, fee_rate=FEE_RATE)
    res_5x = run_xs_factor(closes, best_lb, best_rb, best_n,
                           warmup=best_lb + 5, fee_rate=FEE_RATE * 5)
    return {
        "sharpe_1x": res_1x["sharpe"],
        "sharpe_5x": res_5x["sharpe"],
        "ann_ret_1x": res_1x["annual_ret"],
        "ann_ret_5x": res_5x["annual_ret"],
    }


# ---------------------------------------------------------------------------
# Correlation with H-012 (momentum) and H-019 (volatility)
# ---------------------------------------------------------------------------

def compute_factor_correlations(closes: pd.DataFrame,
                                best_lb: int, best_rb: int, best_n: int):
    print(f"\n  Factor Correlations")

    # Compute H-109 returns
    res_h109 = run_xs_factor(closes, best_lb, best_rb, best_n,
                              warmup=best_lb + 5)
    rets_h109 = res_h109["equity"].pct_change().dropna()

    # H-012: 60-day cross-sectional momentum (long top-4, short bottom-4)
    def run_momentum_factor(closes_inner, mom_lookback=60, rebal_f=5, n_l=4, warmup_i=65):
        mom = closes_inner.pct_change(mom_lookback)
        n = len(closes_inner)
        eq = np.zeros(n)
        eq[0] = INITIAL_CAPITAL
        pw = pd.Series(0.0, index=closes_inner.columns)
        for i in range(1, n):
            lret = np.log(closes_inner.iloc[i] / closes_inner.iloc[i - 1])
            if i >= warmup_i and (i - warmup_i) % rebal_f == 0:
                ranks = mom.iloc[i - 1].dropna()
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

    rets_h012 = run_momentum_factor(closes, mom_lookback=60, rebal_f=5, n_l=4, warmup_i=65)

    # H-019: 20-day volatility factor (long low-vol, short high-vol)
    def run_vol_factor(closes_inner, vol_lookback=20, rebal_f=5, n_l=4, warmup_i=25):
        daily_rets = closes_inner.pct_change()
        vol = daily_rets.rolling(vol_lookback).std()
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
                # Low vol = long (ascending sort, bottom = lowest vol)
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

    rets_h019 = run_vol_factor(closes, vol_lookback=20, rebal_f=5, n_l=4, warmup_i=25)

    common_12 = rets_h109.index.intersection(rets_h012.index)
    common_19 = rets_h109.index.intersection(rets_h019.index)

    corr_12 = float(rets_h109.loc[common_12].corr(rets_h012.loc[common_12])) if len(common_12) > 50 else 0.0
    corr_19 = float(rets_h109.loc[common_19].corr(rets_h019.loc[common_19])) if len(common_19) > 50 else 0.0

    print(f"    Correlation with H-012 (60d XS Momentum):  {corr_12:.3f}")
    print(f"    Correlation with H-019 (20d Low-Vol):      {corr_19:.3f}")

    # Interpretation for reversal
    if corr_12 < -0.1:
        print(f"    -> NEGATIVE corr with momentum: consistent with reversal effect")
    elif corr_12 > 0.1:
        print(f"    -> POSITIVE corr with momentum: reversal is actually capturing momentum (bad)")
    else:
        print(f"    -> Near-zero corr with momentum: reversal is orthogonal to momentum")

    return round(corr_12, 3), round(corr_19, 3)


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("H-109: Short-Term Reversal Factor")
    print("=" * 72)

    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")
    if len(daily) < 10:
        print("ERROR: Not enough assets. Aborting.")
        sys.exit(1)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")

    # -----------------------------------------------------------------------
    # 1. Full parameter scan
    # -----------------------------------------------------------------------
    scan_df = run_full_scan(closes)

    pos_pct = (scan_df["sharpe"] > 0).mean()
    best_row = scan_df.nlargest(1, "sharpe").iloc[0]
    best_lb = int(best_row["ret_lookback"])
    best_rb = int(best_row["rebal"])
    best_n  = int(best_row["n"])

    print(f"\n  Best params: L{best_lb}_R{best_rb}_N{best_n}"
          f", Sharpe {best_row['sharpe']:.3f}")
    print(f"  Positive params: {pos_pct:.0%}")

    # -----------------------------------------------------------------------
    # 2. 60/40 Train/Test + split-half within OOS
    # -----------------------------------------------------------------------
    tt = run_train_test(closes)

    # -----------------------------------------------------------------------
    # 3. Walk-forward (6 folds)
    # -----------------------------------------------------------------------
    wf = run_walk_forward(closes)

    # -----------------------------------------------------------------------
    # 4. Split-half consistency across all params
    # -----------------------------------------------------------------------
    sh = run_split_half(closes)

    # -----------------------------------------------------------------------
    # 5. Fee sensitivity
    # -----------------------------------------------------------------------
    fees = run_fee_sensitivity(closes, tt["best_lb"], tt["best_rb"], tt["best_n"])

    # -----------------------------------------------------------------------
    # 6. Factor correlations (H-012 momentum, H-019 volatility)
    # -----------------------------------------------------------------------
    corr_12, corr_19 = compute_factor_correlations(
        closes, tt["best_lb"], tt["best_rb"], tt["best_n"]
    )

    # -----------------------------------------------------------------------
    # 7. Walk-forward mean OOS Sharpe
    # -----------------------------------------------------------------------
    wf_mean_sharpe = wf["oos_sharpe"].mean() if wf is not None else -99.0
    wf_pos_folds = int((wf["oos_sharpe"] > 0).sum()) if wf is not None else 0
    wf_total_folds = len(wf) if wf is not None else 0

    # -----------------------------------------------------------------------
    # 8. Final verdict
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("FINAL SUMMARY: H-109 Short-Term Reversal Factor")
    print("=" * 72)
    print(f"  Direction              : REVERSAL (long losers, short winners)")
    print(f"  Param combos           : {len(scan_df)}")
    print(f"  % Params positive      : {pos_pct:.0%}   (threshold >=60%)")
    print(f"  Mean Sharpe (all params): {scan_df['sharpe'].mean():.3f}")
    print(f"  Best Sharpe (full data) : {best_row['sharpe']:.3f}")
    print(f"  Best params (full)     : L{best_lb}_R{best_rb}_N{best_n}")
    print()
    print(f"  IS Sharpe (train best) : {tt['train_sharpe']:.3f}")
    print(f"  OOS Sharpe (60/40)     : {tt['oos_sharpe']:.3f}   (threshold >=0.3)")
    print(f"  OOS Ann Return         : {tt['oos_annual_ret']:.1%}")
    print(f"  OOS Max Drawdown       : {tt['oos_max_dd']:.1%}")
    print(f"  OOS test days          : {tt['oos_n_days']}")
    print(f"  Train best params      : {tt['train_best_params']}")
    print()
    print(f"  OOS Half1 Sharpe       : {tt['oos_half1_sharpe']:.3f}")
    print(f"  OOS Half2 Sharpe       : {tt['oos_half2_sharpe']:.3f}")
    print(f"  Split-half corr (all)  : {sh['sharpe_correlation']:.3f}   (threshold >0)")
    print(f"  Both halves positive   : {sh['both_positive_pct']:.0%}")
    print(f"  Half1 mean Sharpe      : {sh['half1_mean_sharpe']:.3f}")
    print(f"  Half2 mean Sharpe      : {sh['half2_mean_sharpe']:.3f}")
    print()
    if wf is not None:
        print(f"  Walk-forward folds     : {wf_total_folds}")
        print(f"  WF mean OOS Sharpe     : {wf_mean_sharpe:.3f}   (threshold >=0.5)")
        print(f"  WF positive folds      : {wf_pos_folds}/{wf_total_folds}")
    print()
    print(f"  Fee sensitivity:")
    print(f"    1x fee (6 bps)       : Sharpe {fees['sharpe_1x']:.3f}, Ann {fees['ann_ret_1x']:.1%}")
    print(f"    5x fee (30 bps)      : Sharpe {fees['sharpe_5x']:.3f}, Ann {fees['ann_ret_5x']:.1%}")
    print()
    print(f"  Corr w/ H-012 (momentum): {corr_12:.3f}  (threshold |corr| <0.5)")
    print(f"  Corr w/ H-019 (low-vol) : {corr_19:.3f}  (threshold |corr| <0.5)")
    if corr_12 < -0.1:
        print(f"    -> Negative corr with momentum supports reversal hypothesis")
    elif corr_12 > 0.1:
        print(f"    -> WARNING: positive corr means this is NOT true reversal")
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
        reasons.append(f"|corr with H-012| > 0.5 ({corr_12:.3f})")
    if abs(corr_19) > 0.5:
        reasons.append(f"|corr with H-019| > 0.5 ({corr_19:.3f})")
    if tt["oos_sharpe"] < 0.3:
        reasons.append(f"OOS Sharpe < 0.3 ({tt['oos_sharpe']:.3f})")

    if reasons:
        verdict = "REJECTED"
        print(f"  VERDICT: **REJECTED**")
        for r in reasons:
            print(f"    Reason: {r}")
    else:
        verdict = "CONFIRMED"
        print(f"  VERDICT: **CONFIRMED**")

    print()

    # Save results
    results_out = {
        "hypothesis": "H-109",
        "title": "Short-Term Reversal Factor",
        "verdict": verdict,
        "rejection_reasons": reasons,
        "direction": "reversal (long losers, short winners)",
        "n_params": len(scan_df),
        "pos_pct": round(float(pos_pct), 3),
        "mean_sharpe_all": round(float(scan_df["sharpe"].mean()), 3),
        "best_full_sharpe": round(float(best_row["sharpe"]), 3),
        "best_full_params": f"L{best_lb}_R{best_rb}_N{best_n}",
        "train_best_params": tt["train_best_params"],
        "train_sharpe": tt["train_sharpe"],
        "oos_sharpe": tt["oos_sharpe"],
        "oos_annual_ret": tt["oos_annual_ret"],
        "oos_max_dd": tt["oos_max_dd"],
        "oos_n_days": tt["oos_n_days"],
        "oos_half1_sharpe": tt["oos_half1_sharpe"],
        "oos_half2_sharpe": tt["oos_half2_sharpe"],
        "split_half_corr": sh["sharpe_correlation"],
        "both_halves_positive_pct": sh["both_positive_pct"],
        "half1_mean_sharpe": sh["half1_mean_sharpe"],
        "half2_mean_sharpe": sh["half2_mean_sharpe"],
        "wf_folds": wf_total_folds,
        "wf_mean_oos_sharpe": round(float(wf_mean_sharpe), 3),
        "wf_positive_folds": wf_pos_folds,
        "fee_sharpe_1x": fees["sharpe_1x"],
        "fee_sharpe_5x": fees["sharpe_5x"],
        "fee_ann_ret_1x": fees["ann_ret_1x"],
        "fee_ann_ret_5x": fees["ann_ret_5x"],
        "corr_h012_momentum": corr_12,
        "corr_h019_lowvol": corr_19,
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(results_out, f, indent=2)
    print(f"  Results saved to {out_path}")
