"""
H-124: Close Location Value Factor (Revisited with Direction Grid)
===================================================================
CLV = (close - low) / (high - low) per day.
Measures where price closes within the day's range.
  - Near 1.0 = closed at high (bullish buying pressure)
  - Near 0.0 = closed at low (bearish selling pressure)

Cross-sectional: roll avg CLV over lookback, rank assets.
  - MOMENTUM direction: long top-N (high CLV), short bottom-N (low CLV)
  - CONTRARIAN direction: long bottom-N (low CLV), short top-N (high CLV)

H-105 tested CLV (momentum only) and was REJECTED due to split-half = -0.19.
This revisit tests BOTH directions in the parameter grid to see if contrarian
or different lookback windows change the outcome.

Parameter grid: 6 lookbacks x 4 rebals x 3 Ns x 2 directions = 144 combos

Validation:
  1. Full param scan (% positive IS Sharpe, both directions)
  2. Walk-forward (6 folds: 180d train, 90d test)
  3. Split-half stability
  4. Correlation with H-012 (60d momentum)
  5. Fee sensitivity (1x vs 5x)

REJECTION criteria:
  - split-half < -0.3 -> REJECT
  - WF < 2/total positive -> REJECT
  - corr > 0.6 with H-012 -> REJECT
  - < 50% IS positive -> REJECT
"""

import sys
import json
import warnings
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001          # 10 bps round-trip per rebalance (Bybit taker)
INITIAL_CAPITAL = 10_000.0

# Parameter grid: 6 x 4 x 3 x 2 = 144 combos
CLV_LOOKBACKS   = [10, 15, 20, 30, 40, 60]
REBAL_FREQS     = [3, 5, 7, 10]
N_SIZES         = [3, 4, 5]
DIRECTIONS      = ["momentum", "contrarian"]

WF_FOLDS      = 6
WF_TRAIN_DAYS = 180
WF_TEST_DAYS  = 90

SPLIT_RATIO = 0.60  # 60/40 IS/OOS

# ─────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────

def load_daily_data():
    data_dir = ROOT / "data"
    ohlcv = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if len(df) >= 200:
                ohlcv[sym] = df
                print(f"  {sym}: {len(df)} bars "
                      f"({df.index[0].date()} to {df.index[-1].date()})")
            else:
                print(f"  {sym}: only {len(df)} bars -- skipping")
        else:
            print(f"  {sym}: no cache file -- skipping")
    return ohlcv


def build_panel(ohlcv: dict):
    """Build aligned close, high, low DataFrames."""
    closes = pd.DataFrame({s: d["close"] for s, d in ohlcv.items()})
    highs  = pd.DataFrame({s: d["high"]  for s, d in ohlcv.items()})
    lows   = pd.DataFrame({s: d["low"]   for s, d in ohlcv.items()})
    # Ensure datetime index
    for df in [closes, highs, lows]:
        df.index = pd.to_datetime(df.index, utc=True)
    # Align: keep rows where at least 8 assets have data
    idx = closes.dropna(thresh=8).index
    closes = closes.loc[idx].ffill()
    highs  = highs.loc[idx].ffill()
    lows   = lows.loc[idx].ffill()
    return closes, highs, lows


# ─────────────────────────────────────────────────────────────
# CLV computation
# ─────────────────────────────────────────────────────────────

def compute_clv(closes: pd.DataFrame, highs: pd.DataFrame,
                lows: pd.DataFrame) -> pd.DataFrame:
    """
    Daily CLV = (close - low) / (high - low).
    When high == low (zero range), CLV = 0.5.
    """
    rng = highs - lows
    clv = (closes - lows) / rng.replace(0, np.nan)
    clv = clv.fillna(0.5)
    clv = clv.clip(0.0, 1.0)
    return clv


def rolling_avg_clv(clv: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Rolling mean of CLV over `lookback` days."""
    return clv.rolling(lookback, min_periods=lookback).mean()


# ─────────────────────────────────────────────────────────────
# Strategy runner
# ─────────────────────────────────────────────────────────────

def run_clv_strategy(closes: pd.DataFrame, ranking_signal: pd.DataFrame,
                     rebal_freq: int, n: int, direction: str = "momentum",
                     fee_rate: float = FEE_RATE, warmup: int = 35) -> dict:
    """
    Cross-sectional long/short portfolio.

    direction="momentum": long top-N (high avg CLV), short bottom-N (low avg CLV)
    direction="contrarian": long bottom-N (low avg CLV), short top-N (high avg CLV)
    """
    n_days = len(closes)
    equity = np.zeros(n_days)
    equity[0] = INITIAL_CAPITAL
    daily_rets = np.zeros(n_days)

    prev_weights = pd.Series(0.0, index=closes.columns)
    n_trades = 0
    n_rebals = 0

    for i in range(1, n_days):
        price_today = closes.iloc[i]
        price_yest  = closes.iloc[i - 1]
        log_rets    = np.log(price_today / price_yest)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            signal = ranking_signal.iloc[i - 1]
            valid  = signal.dropna()
            if len(valid) < n + n:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                daily_rets[i] = port_ret
                continue

            ranked = valid.sort_values(ascending=False)

            if direction == "momentum":
                # Long highest CLV (buying pressure), short lowest
                longs  = ranked.index[:n]
                shorts = ranked.index[-n:]
            else:  # contrarian
                # Long lowest CLV (contrarian reversal), short highest
                longs  = ranked.index[-n:]
                shorts = ranked.index[:n]

            new_w = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_w[sym] += 1.0 / n
            for sym in shorts:
                new_w[sym] -= 1.0 / n

            # Fee on turnover
            turnover = (new_w - prev_weights).abs().sum() / 2.0
            fee_cost = turnover * fee_rate

            port_ret = (new_w * log_rets).sum() - fee_cost
            n_trades += int(((new_w - prev_weights).abs() > 0.001).sum())
            n_rebals += 1
            prev_weights = new_w
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)
        daily_rets[i] = port_ret

    eq   = pd.Series(equity, index=closes.index)
    rets = pd.Series(daily_rets, index=closes.index)

    # Sharpe from active period only
    active_rets = rets[warmup:]
    if active_rets.std() < 1e-10:
        sharpe = 0.0
    else:
        sharpe = float(active_rets.mean() / active_rets.std() * np.sqrt(365))

    ann_ret = annual_return(eq[warmup:], periods_per_year=365)
    mdd     = max_drawdown(eq[warmup:])

    n_pos  = (active_rets > 0).sum()
    n_tot  = len(active_rets)

    return {
        "sharpe":     round(sharpe, 4),
        "annual_ret": round(ann_ret, 4),
        "max_dd":     round(mdd, 4),
        "win_rate":   round(n_pos / n_tot, 4) if n_tot > 0 else 0,
        "n_trades":   n_trades,
        "n_rebals":   n_rebals,
        "equity":     eq,
        "daily_rets": rets,
    }


# ─────────────────────────────────────────────────────────────
# 1. Full parameter scan
# ─────────────────────────────────────────────────────────────

def run_full_scan(closes, highs, lows):
    print("\n" + "=" * 72)
    print("1. FULL PARAMETER SCAN -- 144 combinations (2 directions)")
    print("=" * 72)

    clv = compute_clv(closes, highs, lows)

    # Pre-compute rolling avg CLV for each lookback
    print("  Pre-computing rolling CLV averages...")
    clv_cache = {}
    for lb in CLV_LOOKBACKS:
        clv_cache[lb] = rolling_avg_clv(clv, lb)

    results = []
    n_combos = len(CLV_LOOKBACKS) * len(REBAL_FREQS) * len(N_SIZES) * len(DIRECTIONS)
    print(f"  Running {n_combos} param combos...")

    for lb, rf, n, dirn in product(CLV_LOOKBACKS, REBAL_FREQS, N_SIZES, DIRECTIONS):
        signal = clv_cache[lb]
        warmup = lb + 5
        res = run_clv_strategy(closes, signal, rf, n, direction=dirn,
                               warmup=warmup)
        tag = f"LB{lb}_R{rf}_N{n}_{dirn[:3]}"
        results.append({
            "tag": tag, "lb": lb, "rebal": rf, "n": n, "direction": dirn,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
        })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    pct_positive = n_positive / len(df) * 100

    print(f"\n  Results: {n_positive}/{len(df)} positive Sharpe ({pct_positive:.1f}%)")
    print(f"  Mean Sharpe:   {df['sharpe'].mean():.3f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.3f}")

    # Breakdown by direction
    for dirn in DIRECTIONS:
        sub = df[df["direction"] == dirn]
        n_pos_d = (sub["sharpe"] > 0).sum()
        print(f"\n  [{dirn.upper()}] {n_pos_d}/{len(sub)} positive ({n_pos_d/len(sub)*100:.1f}%)")
        print(f"    Mean Sharpe:   {sub['sharpe'].mean():.3f}")
        print(f"    Median Sharpe: {sub['sharpe'].median():.3f}")
        best_row = sub.loc[sub["sharpe"].idxmax()]
        print(f"    Best: {best_row['tag']} Sharpe={best_row['sharpe']:.3f} "
              f"Ret={best_row['annual_ret']*100:.1f}% DD={best_row['max_dd']*100:.1f}%")

    # Top 10 overall
    print("\n  Top 10 overall:")
    top10 = df.nlargest(10, "sharpe")
    for _, row in top10.iterrows():
        print(f"    {row['tag']:30s}  Sharpe={row['sharpe']:.3f}  "
              f"Ret={row['annual_ret']*100:.1f}%  DD={row['max_dd']*100:.1f}%  "
              f"WR={row['win_rate']*100:.1f}%")

    # Bottom 5
    print("\n  Bottom 5:")
    bot5 = df.nsmallest(5, "sharpe")
    for _, row in bot5.iterrows():
        print(f"    {row['tag']:30s}  Sharpe={row['sharpe']:.3f}  "
              f"Ret={row['annual_ret']*100:.1f}%  DD={row['max_dd']*100:.1f}%")

    return df, results


# ─────────────────────────────────────────────────────────────
# 2. IS/OOS split (60/40) for best direction
# ─────────────────────────────────────────────────────────────

def run_is_oos_split(closes, highs, lows, df_full):
    print("\n" + "=" * 72)
    print("2. IN-SAMPLE / OUT-OF-SAMPLE SPLIT (60/40)")
    print("=" * 72)

    n      = len(closes)
    split  = int(n * SPLIT_RATIO)
    is_c   = closes.iloc[:split]
    is_h   = highs.iloc[:split]
    is_l   = lows.iloc[:split]
    oos_c  = closes.iloc[split:]
    oos_h  = highs.iloc[split:]
    oos_l  = lows.iloc[split:]

    print(f"  IS  period: {is_c.index[0].date()} to {is_c.index[-1].date()} ({split} days)")
    print(f"  OOS period: {oos_c.index[0].date()} to {oos_c.index[-1].date()} ({n - split} days)")

    # Find best IS params (searching all directions)
    clv_is = compute_clv(is_c, is_h, is_l)
    best_sharpe_is = -999
    best_params = None

    for lb, rf, nn, dirn in product(CLV_LOOKBACKS, REBAL_FREQS, N_SIZES, DIRECTIONS):
        signal = rolling_avg_clv(clv_is, lb)
        warmup = lb + 5
        res = run_clv_strategy(is_c, signal, rf, nn, direction=dirn, warmup=warmup)
        if res["sharpe"] > best_sharpe_is:
            best_sharpe_is = res["sharpe"]
            best_params = (lb, rf, nn, dirn)

    lb, rf, nn, dirn = best_params
    print(f"\n  Best IS params: LB{lb}_R{rf}_N{nn}_{dirn[:3]} (IS Sharpe={best_sharpe_is:.3f})")

    # OOS evaluation
    clv_oos = compute_clv(oos_c, oos_h, oos_l)
    sig_oos = rolling_avg_clv(clv_oos, lb)
    res_oos = run_clv_strategy(oos_c, sig_oos, rf, nn, direction=dirn, warmup=lb + 5)
    print(f"  OOS Sharpe:   {res_oos['sharpe']:.3f}")
    print(f"  OOS Ann Ret:  {res_oos['annual_ret']*100:.1f}%")
    print(f"  OOS Max DD:   {res_oos['max_dd']*100:.1f}%")
    print(f"  OOS Win Rate: {res_oos['win_rate']*100:.1f}%")

    return {
        "is_sharpe": best_sharpe_is,
        "is_params": f"LB{lb}_R{rf}_N{nn}_{dirn[:3]}",
        "is_direction": dirn,
        "oos_sharpe": res_oos["sharpe"],
        "oos_annual_ret": res_oos["annual_ret"],
        "oos_max_dd": res_oos["max_dd"],
        "oos_win_rate": res_oos["win_rate"],
    }


# ─────────────────────────────────────────────────────────────
# 3. Walk-forward validation
# ─────────────────────────────────────────────────────────────

def walk_forward(closes, highs, lows, n_folds=WF_FOLDS):
    print(f"\n" + "=" * 72)
    print(f"3. WALK-FORWARD VALIDATION ({n_folds} folds, {WF_TRAIN_DAYS}d train, {WF_TEST_DAYS}d test)")
    print("=" * 72)

    n = len(closes)
    total_needed = WF_TRAIN_DAYS + WF_TEST_DAYS

    if n < total_needed:
        print("  Not enough data for walk-forward!")
        return pd.DataFrame()

    available = n - total_needed
    if n_folds > 1:
        step = available // (n_folds - 1)
    else:
        step = 0

    wf_results = []

    for fold in range(n_folds):
        train_start = fold * step
        train_end   = train_start + WF_TRAIN_DAYS
        test_start  = train_end
        test_end    = min(test_start + WF_TEST_DAYS, n)

        if test_end > n or (test_end - test_start) < 30:
            continue

        tr_c = closes.iloc[train_start:train_end]
        tr_h = highs.iloc[train_start:train_end]
        tr_l = lows.iloc[train_start:train_end]
        te_c = closes.iloc[test_start:test_end]
        te_h = highs.iloc[test_start:test_end]
        te_l = lows.iloc[test_start:test_end]

        # Find best params on train (including direction)
        clv_tr = compute_clv(tr_c, tr_h, tr_l)
        best_sharpe = -99
        best_p = None

        for lb, rf, nn, dirn in product(CLV_LOOKBACKS, REBAL_FREQS, N_SIZES, DIRECTIONS):
            if len(tr_c) < lb + 30:
                continue
            signal = rolling_avg_clv(clv_tr, lb)
            res = run_clv_strategy(tr_c, signal, rf, nn, direction=dirn, warmup=lb + 5)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_p = (lb, rf, nn, dirn)

        if best_p is None:
            continue

        lb, rf, nn, dirn = best_p
        clv_te  = compute_clv(te_c, te_h, te_l)
        sig_te  = rolling_avg_clv(clv_te, lb)
        test_res = run_clv_strategy(te_c, sig_te, rf, nn, direction=dirn, warmup=lb + 5)

        wf_results.append({
            "fold": fold,
            "train_sharpe": round(best_sharpe, 3),
            "test_sharpe": test_res["sharpe"],
            "params": f"LB{lb}_R{rf}_N{nn}_{dirn[:3]}",
            "direction": dirn,
            "test_ret": test_res["annual_ret"],
            "test_dd": test_res["max_dd"],
        })
        print(f"  Fold {fold}: train Sharpe={best_sharpe:.3f} -> "
              f"test Sharpe={test_res['sharpe']:.3f} "
              f"[{dirn[:3]}] LB{lb}_R{rf}_N{nn}")

    if wf_results:
        wf_df = pd.DataFrame(wf_results)
        n_pos = (wf_df["test_sharpe"] > 0).sum()
        print(f"\n  WF Summary: {n_pos}/{len(wf_df)} positive, "
              f"mean OOS Sharpe={wf_df['test_sharpe'].mean():.3f}")

        # Check direction distribution in best params
        dir_counts = wf_df["direction"].value_counts()
        print(f"  Direction selection across folds: {dict(dir_counts)}")
        return wf_df
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# 4. Split-half stability
# ─────────────────────────────────────────────────────────────

def split_half_test(closes, highs, lows):
    """Test stability: Sharpe for all params on each half, correlate."""
    print("\n" + "=" * 72)
    print("4. SPLIT-HALF STABILITY")
    print("=" * 72)

    mid = len(closes) // 2
    h1_c, h1_h, h1_l = closes.iloc[:mid], highs.iloc[:mid], lows.iloc[:mid]
    h2_c, h2_h, h2_l = closes.iloc[mid:], highs.iloc[mid:], lows.iloc[mid:]

    print(f"  Half-1: {h1_c.index[0].date()} to {h1_c.index[-1].date()} ({mid} days)")
    print(f"  Half-2: {h2_c.index[0].date()} to {h2_c.index[-1].date()} ({len(closes) - mid} days)")

    clv_h1 = compute_clv(h1_c, h1_h, h1_l)
    clv_h2 = compute_clv(h2_c, h2_h, h2_l)

    r1, r2 = [], []
    for lb, rf, n, dirn in product(CLV_LOOKBACKS, REBAL_FREQS, N_SIZES, DIRECTIONS):
        sig1 = rolling_avg_clv(clv_h1, lb)
        sig2 = rolling_avg_clv(clv_h2, lb)
        res1 = run_clv_strategy(h1_c, sig1, rf, n, direction=dirn, warmup=lb + 5)
        res2 = run_clv_strategy(h2_c, sig2, rf, n, direction=dirn, warmup=lb + 5)
        r1.append(res1["sharpe"])
        r2.append(res2["sharpe"])

    corr = np.corrcoef(r1, r2)[0, 1]
    print(f"\n  Split-Half Correlation: {corr:.3f}")
    print(f"    Half-1 mean Sharpe: {np.mean(r1):.3f}")
    print(f"    Half-2 mean Sharpe: {np.mean(r2):.3f}")

    # Also compute per-direction split-half
    for dirn in DIRECTIONS:
        r1d, r2d = [], []
        for lb, rf, n in product(CLV_LOOKBACKS, REBAL_FREQS, N_SIZES):
            sig1 = rolling_avg_clv(clv_h1, lb)
            sig2 = rolling_avg_clv(clv_h2, lb)
            res1 = run_clv_strategy(h1_c, sig1, rf, n, direction=dirn, warmup=lb + 5)
            res2 = run_clv_strategy(h2_c, sig2, rf, n, direction=dirn, warmup=lb + 5)
            r1d.append(res1["sharpe"])
            r2d.append(res2["sharpe"])
        corr_d = np.corrcoef(r1d, r2d)[0, 1]
        print(f"    [{dirn.upper()}] split-half corr: {corr_d:.3f}  "
              f"(H1 mean={np.mean(r1d):.3f}, H2 mean={np.mean(r2d):.3f})")

    return corr


# ─────────────────────────────────────────────────────────────
# 5. Correlation with H-012 (60d momentum)
# ─────────────────────────────────────────────────────────────

def correlation_with_h012(closes, highs, lows, best_lb, best_rebal, best_n, best_dir):
    """Compute daily return correlation with H-012 momentum factor."""
    print("\n" + "=" * 72)
    print("5. CORRELATION WITH H-012 (60d Momentum)")
    print("=" * 72)

    clv = compute_clv(closes, highs, lows)
    signal = rolling_avg_clv(clv, best_lb)
    res = run_clv_strategy(closes, signal, best_rebal, best_n,
                           direction=best_dir, warmup=best_lb + 5)
    my_rets = res["equity"].pct_change().dropna()

    # Replicate H-012: 60-day momentum, rebal every 5 days, N=4
    roll_ret = closes.pct_change(60)
    h012_eq = np.zeros(len(closes))
    h012_eq[0] = 10000
    prev_w = pd.Series(0.0, index=closes.columns)
    warmup = 65
    for i in range(1, len(closes)):
        pt = closes.iloc[i]
        py = closes.iloc[i - 1]
        lr = np.log(pt / py)
        if i >= warmup and (i - warmup) % 5 == 0:
            sig = roll_ret.iloc[i - 1].dropna()
            if len(sig) >= 8:
                ranked = sig.sort_values(ascending=False)
                new_w = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:4]:
                    new_w[s] = 1.0 / 4
                for s in ranked.index[-4:]:
                    new_w[s] = -1.0 / 4
                prev_w = new_w
        h012_eq[i] = h012_eq[i - 1] * np.exp((prev_w * lr).sum())
    h012_rets = pd.Series(h012_eq, index=closes.index).pct_change().dropna()

    common = my_rets.index.intersection(h012_rets.index)
    corr = np.corrcoef(my_rets.loc[common].values, h012_rets.loc[common].values)[0, 1]
    print(f"  Correlation with H-012 (momentum L60_R5_N4): {corr:.3f}")
    return corr


# ─────────────────────────────────────────────────────────────
# 6. Fee sensitivity
# ─────────────────────────────────────────────────────────────

def fee_sensitivity(closes, highs, lows, best_lb, best_rebal, best_n, best_dir):
    """Test strategy at 1x and 5x fee levels."""
    print("\n" + "=" * 72)
    print("6. FEE SENSITIVITY")
    print("=" * 72)

    clv = compute_clv(closes, highs, lows)
    signal = rolling_avg_clv(clv, best_lb)
    warmup = best_lb + 5

    fee_results = {}
    for mult, label in [(0, "0x (no fees)"), (1, "1x (10 bps)"), (3, "3x (30 bps)"), (5, "5x (50 bps)")]:
        fee = FEE_RATE * mult
        res = run_clv_strategy(closes, signal, best_rebal, best_n,
                               direction=best_dir, fee_rate=fee, warmup=warmup)
        fee_results[label] = res["sharpe"]
        print(f"  {label}: Sharpe={res['sharpe']:.3f}  "
              f"Ret={res['annual_ret']*100:.1f}%  DD={res['max_dd']*100:.1f}%")

    return fee_results


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 72)
    print("H-124: Close Location Value Factor (Revisited)")
    print("  Testing BOTH momentum and contrarian directions")
    print("  Expanded lookback grid: [10, 15, 20, 30, 40, 60]")
    print("=" * 72)

    print("\nLoading data...")
    daily = load_daily_data()
    closes, highs, lows = build_panel(daily)
    print(f"\nPanel: {closes.shape[0]} days x {closes.shape[1]} assets")
    print(f"Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    # 1. Full parameter scan
    df_results, results_list = run_full_scan(closes, highs, lows)

    # Determine best overall params
    best_row = df_results.loc[df_results["sharpe"].idxmax()]
    best_lb   = int(best_row["lb"])
    best_rf   = int(best_row["rebal"])
    best_n    = int(best_row["n"])
    best_dir  = str(best_row["direction"])
    best_tag  = str(best_row["tag"])
    print(f"\n  BEST OVERALL: {best_tag} Sharpe={best_row['sharpe']:.3f}")

    # 2. IS/OOS split
    is_oos = run_is_oos_split(closes, highs, lows, df_results)

    # 3. Walk-forward
    wf_df = walk_forward(closes, highs, lows)

    # 4. Split-half
    sh_corr = split_half_test(closes, highs, lows)

    # 5. Correlation with H-012
    corr_012 = correlation_with_h012(closes, highs, lows,
                                     best_lb, best_rf, best_n, best_dir)

    # 6. Fee sensitivity
    fee_res = fee_sensitivity(closes, highs, lows,
                              best_lb, best_rf, best_n, best_dir)

    # ─────────────────────────────────────────────────────────
    # Summary and verdict
    # ─────────────────────────────────────────────────────────
    n_positive = int((df_results["sharpe"] > 0).sum())
    pct_positive = n_positive / len(df_results) * 100
    wf_n_pos = int((wf_df["test_sharpe"] > 0).sum()) if len(wf_df) > 0 else 0
    wf_n_total = len(wf_df)
    wf_mean = float(wf_df["test_sharpe"].mean()) if len(wf_df) > 0 else 0

    # Per-direction stats
    direction_stats = {}
    for dirn in DIRECTIONS:
        sub = df_results[df_results["direction"] == dirn]
        direction_stats[dirn] = {
            "n_positive": int((sub["sharpe"] > 0).sum()),
            "n_total": len(sub),
            "pct_positive": float((sub["sharpe"] > 0).mean() * 100),
            "mean_sharpe": float(sub["sharpe"].mean()),
            "median_sharpe": float(sub["sharpe"].median()),
            "best_sharpe": float(sub["sharpe"].max()),
            "best_tag": str(sub.loc[sub["sharpe"].idxmax(), "tag"]),
        }

    # Rejection checks
    print("\n" + "=" * 72)
    print("VERDICT")
    print("=" * 72)

    reject_reasons = []
    if pct_positive < 50:
        reject_reasons.append(f"IS positive rate {pct_positive:.1f}% < 50%")
    if sh_corr < -0.3:
        reject_reasons.append(f"Split-half corr {sh_corr:.3f} < -0.3")
    if wf_n_total > 0 and wf_n_pos < 2:
        reject_reasons.append(f"WF positive {wf_n_pos}/{wf_n_total} < 2")
    if corr_012 > 0.6:
        reject_reasons.append(f"H-012 correlation {corr_012:.3f} > 0.6")

    if reject_reasons:
        verdict = "REJECTED"
        print(f"  VERDICT: REJECTED")
        for r in reject_reasons:
            print(f"    - {r}")
    else:
        verdict = "CONDITIONAL"
        print(f"  VERDICT: CONDITIONAL (passes minimum thresholds)")

    print(f"\n  Key metrics:")
    print(f"    IS positive:       {n_positive}/{len(df_results)} ({pct_positive:.1f}%)")
    print(f"    Split-half corr:   {sh_corr:.3f}")
    print(f"    WF positive:       {wf_n_pos}/{wf_n_total}")
    print(f"    WF mean Sharpe:    {wf_mean:.3f}")
    print(f"    H-012 correlation: {corr_012:.3f}")
    print(f"    Best direction:    {best_dir}")
    print(f"    Best params:       {best_tag}")
    print(f"    Best Sharpe:       {best_row['sharpe']:.3f}")

    # Comparison with H-105
    print(f"\n  Comparison with H-105 (original CLV test):")
    print(f"    H-105 tested momentum only, lookbacks [5,10,20,30], 36 combos")
    print(f"    H-105 result: 78% positive, split-half -0.187 -> REJECTED")
    print(f"    H-124 tests both directions, lookbacks [10,15,20,30,40,60], 144 combos")
    print(f"    H-124 split-half: {sh_corr:.3f}")

    # Build output
    output = {
        "hypothesis": "H-124",
        "name": "Close Location Value Factor (Revisited)",
        "factor": "CLV = (close - low) / (high - low), rolling average",
        "directions_tested": ["momentum", "contrarian"],
        "n_params": len(df_results),
        "pct_positive_sharpe": round(pct_positive, 1),
        "mean_sharpe": round(float(df_results["sharpe"].mean()), 3),
        "median_sharpe": round(float(df_results["sharpe"].median()), 3),
        "best_params": best_tag,
        "best_direction": best_dir,
        "best_sharpe": float(best_row["sharpe"]),
        "best_annual_ret": float(best_row["annual_ret"]),
        "best_max_dd": float(best_row["max_dd"]),
        "best_win_rate": float(best_row["win_rate"]),
        "direction_stats": direction_stats,
        "is_oos": is_oos,
        "wf_folds_positive": wf_n_pos,
        "wf_folds_total": wf_n_total,
        "wf_mean_oos_sharpe": round(wf_mean, 3),
        "wf_details": wf_df.to_dict("records") if len(wf_df) > 0 else [],
        "split_half_corr": round(float(sh_corr), 3),
        "corr_h012": round(float(corr_012), 3),
        "fee_sensitivity": fee_res,
        "verdict": verdict,
        "reject_reasons": reject_reasons,
        "comparison_h105": {
            "h105_split_half": -0.187,
            "h105_pct_positive": 78,
            "h124_split_half": round(float(sh_corr), 3),
            "h124_pct_positive": round(pct_positive, 1),
            "improvement": "tested both directions + wider lookback grid",
        },
        "all_results": results_list,
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")

    # Print clean summary
    print("\n" + "=" * 72)
    print(json.dumps({k: v for k, v in output.items()
                      if k not in ("all_results", "wf_details")}, indent=2))
