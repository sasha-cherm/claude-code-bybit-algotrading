"""
H-128: Dollar Volume Velocity Factor
======================================
Factor: dollar_volume = close * volume.
Velocity = rolling_short_mean(dollar_volume) / rolling_long_mean(dollar_volume) - 1.

Positive velocity = accelerating dollar volume flow (capital attraction).
Negative velocity = decelerating flow (capital withdrawal).

Cross-sectional: rank 14 assets by dv_velocity.
  - long_accel: long top-N (highest velocity), short bottom-N (lowest velocity)
  - long_decel: long bottom-N (lowest velocity), short top-N (highest velocity)

Parameter grid:
  short_window: [5, 10, 20]
  long_window:  [30, 60, 90]
  rebal_freq:   [3, 5, 7, 10]
  N:            [3, 4]
  direction:    [long_accel, long_decel]
  Total: 3 x 3 x 4 x 2 x 2 = 144 combos

Validation:
  1. Full param scan (% positive IS Sharpe -- need >= 80%)
  2. Walk-forward (6 folds: 180d train, 90d test -- need >= 4/6 positive OOS)
  3. Split-half stability (need correlation > 0)
  4. Correlation with H-012 (60d momentum) -- redundant if > 0.6

VERDICT logic:
  - IS positive < 80% -> REJECTED
  - WF positive < 4/6 -> REJECTED
  - Split-half corr <= 0 -> REJECTED
  - H-012 corr > 0.6 -> REJECTED (redundant)
  - All pass -> CONFIRMED
  - Borderline -> CONDITIONAL
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

# -----------------------------------------------------------------
# Config
# -----------------------------------------------------------------
ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001          # 10 bps round-trip per rebalance (Bybit taker)
INITIAL_CAPITAL = 10_000.0

# Parameter grid: 3 x 3 x 4 x 2 x 2 = 144 combos
SHORT_WINDOWS = [5, 10, 20]
LONG_WINDOWS  = [30, 60, 90]
REBAL_FREQS   = [3, 5, 7, 10]
N_SIZES       = [3, 4]
DIRECTIONS    = ["long_accel", "long_decel"]

WF_FOLDS      = 6
WF_TRAIN_DAYS = 180
WF_TEST_DAYS  = 90

# -----------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------

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
    """Build aligned close, volume DataFrames."""
    closes  = pd.DataFrame({s: d["close"]  for s, d in ohlcv.items()})
    volumes = pd.DataFrame({s: d["volume"] for s, d in ohlcv.items()})
    for df in [closes, volumes]:
        df.index = pd.to_datetime(df.index, utc=True)
    # Keep rows where at least 8 assets have data
    idx = closes.dropna(thresh=8).index
    closes  = closes.loc[idx].ffill()
    volumes = volumes.loc[idx].ffill().fillna(0)
    return closes, volumes


# -----------------------------------------------------------------
# Factor computation
# -----------------------------------------------------------------

def compute_dv_velocity(closes: pd.DataFrame, volumes: pd.DataFrame,
                        short_window: int, long_window: int) -> pd.DataFrame:
    """
    Dollar volume velocity factor.
    dollar_volume = close * volume
    dv_velocity = rolling_short_mean(dv) / rolling_long_mean(dv) - 1

    Positive = accelerating dollar volume (capital attraction).
    Negative = decelerating dollar volume.
    """
    dv = closes * volumes
    dv_short = dv.rolling(short_window, min_periods=short_window).mean()
    dv_long  = dv.rolling(long_window, min_periods=long_window).mean()
    # Avoid division by zero
    velocity = dv_short / dv_long.replace(0, np.nan) - 1.0
    return velocity


# -----------------------------------------------------------------
# Strategy runner
# -----------------------------------------------------------------

def run_strategy(closes: pd.DataFrame, ranking_signal: pd.DataFrame,
                 rebal_freq: int, n: int, direction: str = "long_accel",
                 fee_rate: float = FEE_RATE, warmup: int = 95) -> dict:
    """
    Cross-sectional long/short portfolio based on dv_velocity ranking.

    direction="long_accel": long top-N (highest velocity), short bottom-N
    direction="long_decel": long bottom-N (lowest velocity), short top-N
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
            if len(valid) < 2 * n:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                daily_rets[i] = port_ret
                continue

            ranked = valid.sort_values(ascending=False)

            if direction == "long_accel":
                # Long highest velocity (accelerating), short lowest
                longs  = ranked.index[:n]
                shorts = ranked.index[-n:]
            else:  # long_decel
                # Long lowest velocity (decelerating), short highest
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

    n_pos = (active_rets > 0).sum()
    n_tot = len(active_rets)

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


# -----------------------------------------------------------------
# 1. Full parameter scan
# -----------------------------------------------------------------

def run_full_scan(closes, volumes):
    print("\n" + "=" * 72)
    print("1. FULL PARAMETER SCAN -- 144 combinations (2 directions)")
    print("=" * 72)

    # Pre-compute velocity signals for each (short, long) window pair
    print("  Pre-computing dollar volume velocity signals...")
    vel_cache = {}
    for sw, lw in product(SHORT_WINDOWS, LONG_WINDOWS):
        if sw >= lw:
            continue  # short must be < long
        vel_cache[(sw, lw)] = compute_dv_velocity(closes, volumes, sw, lw)

    results = []
    valid_combos = 0
    for sw, lw, rf, n, dirn in product(SHORT_WINDOWS, LONG_WINDOWS, REBAL_FREQS,
                                       N_SIZES, DIRECTIONS):
        if sw >= lw:
            continue
        valid_combos += 1
        signal = vel_cache[(sw, lw)]
        warmup = lw + 5
        res = run_strategy(closes, signal, rf, n, direction=dirn,
                           warmup=warmup)
        tag = f"S{sw}_L{lw}_R{rf}_N{n}_{dirn}"
        results.append({
            "tag": tag, "short_w": sw, "long_w": lw, "rebal": rf,
            "n": n, "direction": dirn,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
        })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    pct_positive = n_positive / len(df) * 100

    print(f"\n  Total param combos: {len(df)}")
    print(f"  Results: {n_positive}/{len(df)} positive Sharpe ({pct_positive:.1f}%)")
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
        print(f"    {row['tag']:40s}  Sharpe={row['sharpe']:.3f}  "
              f"Ret={row['annual_ret']*100:.1f}%  DD={row['max_dd']*100:.1f}%  "
              f"WR={row['win_rate']*100:.1f}%")

    # Bottom 5
    print("\n  Bottom 5:")
    bot5 = df.nsmallest(5, "sharpe")
    for _, row in bot5.iterrows():
        print(f"    {row['tag']:40s}  Sharpe={row['sharpe']:.3f}  "
              f"Ret={row['annual_ret']*100:.1f}%  DD={row['max_dd']*100:.1f}%")

    return df, results


# -----------------------------------------------------------------
# 2. Walk-forward validation
# -----------------------------------------------------------------

def walk_forward(closes, volumes, n_folds=WF_FOLDS):
    print(f"\n" + "=" * 72)
    print(f"2. WALK-FORWARD VALIDATION ({n_folds} folds, {WF_TRAIN_DAYS}d train, {WF_TEST_DAYS}d test)")
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
        tr_v = volumes.iloc[train_start:train_end]
        te_c = closes.iloc[test_start:test_end]
        te_v = volumes.iloc[test_start:test_end]

        # Find best params on train (including direction)
        best_sharpe = -99
        best_p = None

        for sw, lw, rf, nn, dirn in product(SHORT_WINDOWS, LONG_WINDOWS,
                                             REBAL_FREQS, N_SIZES, DIRECTIONS):
            if sw >= lw:
                continue
            if len(tr_c) < lw + 30:
                continue
            signal = compute_dv_velocity(tr_c, tr_v, sw, lw)
            res = run_strategy(tr_c, signal, rf, nn, direction=dirn,
                               warmup=lw + 5)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_p = (sw, lw, rf, nn, dirn)

        if best_p is None:
            continue

        sw, lw, rf, nn, dirn = best_p
        sig_te  = compute_dv_velocity(te_c, te_v, sw, lw)
        test_res = run_strategy(te_c, sig_te, rf, nn, direction=dirn,
                                warmup=lw + 5)

        wf_results.append({
            "fold": fold,
            "train_period": f"{tr_c.index[0].date()} to {tr_c.index[-1].date()}",
            "test_period":  f"{te_c.index[0].date()} to {te_c.index[-1].date()}",
            "test_days": len(te_c),
            "train_sharpe": round(best_sharpe, 3),
            "test_sharpe": test_res["sharpe"],
            "params": f"S{sw}_L{lw}_R{rf}_N{nn}_{dirn}",
            "direction": dirn,
            "test_ret": test_res["annual_ret"],
            "test_dd": test_res["max_dd"],
        })
        print(f"  Fold {fold}: train Sharpe={best_sharpe:.3f} -> "
              f"test Sharpe={test_res['sharpe']:.3f} "
              f"[{dirn}] S{sw}_L{lw}_R{rf}_N{nn}")

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


# -----------------------------------------------------------------
# 3. Split-half stability
# -----------------------------------------------------------------

def split_half_test(closes, volumes):
    """Test stability: Sharpe for all params on each half, correlate."""
    print("\n" + "=" * 72)
    print("3. SPLIT-HALF STABILITY")
    print("=" * 72)

    mid = len(closes) // 2
    h1_c, h1_v = closes.iloc[:mid], volumes.iloc[:mid]
    h2_c, h2_v = closes.iloc[mid:], volumes.iloc[mid:]

    print(f"  Half-1: {h1_c.index[0].date()} to {h1_c.index[-1].date()} ({mid} days)")
    print(f"  Half-2: {h2_c.index[0].date()} to {h2_c.index[-1].date()} ({len(closes) - mid} days)")

    r1, r2 = [], []
    for sw, lw, rf, n, dirn in product(SHORT_WINDOWS, LONG_WINDOWS,
                                       REBAL_FREQS, N_SIZES, DIRECTIONS):
        if sw >= lw:
            continue
        sig1 = compute_dv_velocity(h1_c, h1_v, sw, lw)
        sig2 = compute_dv_velocity(h2_c, h2_v, sw, lw)
        res1 = run_strategy(h1_c, sig1, rf, n, direction=dirn, warmup=lw + 5)
        res2 = run_strategy(h2_c, sig2, rf, n, direction=dirn, warmup=lw + 5)
        r1.append(res1["sharpe"])
        r2.append(res2["sharpe"])

    corr = np.corrcoef(r1, r2)[0, 1]
    h1_mean = np.mean(r1)
    h2_mean = np.mean(r2)
    print(f"\n  Split-Half Correlation: {corr:.3f}")
    print(f"    Half-1 mean Sharpe: {h1_mean:.3f}")
    print(f"    Half-2 mean Sharpe: {h2_mean:.3f}")

    # Also compute per-direction split-half
    for dirn in DIRECTIONS:
        r1d, r2d = [], []
        for sw, lw, rf, n in product(SHORT_WINDOWS, LONG_WINDOWS,
                                     REBAL_FREQS, N_SIZES):
            if sw >= lw:
                continue
            sig1 = compute_dv_velocity(h1_c, h1_v, sw, lw)
            sig2 = compute_dv_velocity(h2_c, h2_v, sw, lw)
            res1 = run_strategy(h1_c, sig1, rf, n, direction=dirn, warmup=lw + 5)
            res2 = run_strategy(h2_c, sig2, rf, n, direction=dirn, warmup=lw + 5)
            r1d.append(res1["sharpe"])
            r2d.append(res2["sharpe"])
        corr_d = np.corrcoef(r1d, r2d)[0, 1]
        print(f"    [{dirn.upper()}] split-half corr: {corr_d:.3f}  "
              f"(H1 mean={np.mean(r1d):.3f}, H2 mean={np.mean(r2d):.3f})")

    return corr, h1_mean, h2_mean


# -----------------------------------------------------------------
# 4. Correlation with H-012 (60d momentum)
# -----------------------------------------------------------------

def correlation_with_h012(closes, volumes, best_sw, best_lw,
                          best_rebal, best_n, best_dir):
    """Compute daily return correlation with H-012 momentum factor."""
    print("\n" + "=" * 72)
    print("4. CORRELATION WITH H-012 (60d Momentum)")
    print("=" * 72)

    signal = compute_dv_velocity(closes, volumes, best_sw, best_lw)
    res = run_strategy(closes, signal, best_rebal, best_n,
                       direction=best_dir, warmup=best_lw + 5)
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
    if len(common) < 10:
        print("  Not enough overlapping data for correlation.")
        return 0.0
    corr = np.corrcoef(my_rets.loc[common].values,
                       h012_rets.loc[common].values)[0, 1]
    print(f"  Correlation with H-012 (momentum L60_R5_N4): {corr:.3f}")
    return corr


# -----------------------------------------------------------------
# 5. Fee sensitivity
# -----------------------------------------------------------------

def fee_sensitivity(closes, volumes, best_sw, best_lw,
                    best_rebal, best_n, best_dir):
    """Test strategy at various fee levels."""
    print("\n" + "=" * 72)
    print("5. FEE SENSITIVITY")
    print("=" * 72)

    signal = compute_dv_velocity(closes, volumes, best_sw, best_lw)
    warmup = best_lw + 5

    fee_results = {}
    for mult, label in [(0, "0x (no fees)"), (1, "1x (10 bps)"),
                        (3, "3x (30 bps)"), (5, "5x (50 bps)")]:
        fee = FEE_RATE * mult
        res = run_strategy(closes, signal, best_rebal, best_n,
                           direction=best_dir, fee_rate=fee, warmup=warmup)
        fee_results[label] = res["sharpe"]
        print(f"  {label}: Sharpe={res['sharpe']:.3f}  "
              f"Ret={res['annual_ret']*100:.1f}%  DD={res['max_dd']*100:.1f}%")

    return fee_results


# -----------------------------------------------------------------
# Main
# -----------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 72)
    print("H-128: Dollar Volume Velocity Factor")
    print("  dv_velocity = short_mean(close*vol) / long_mean(close*vol) - 1")
    print("  Testing long_accel and long_decel directions")
    print("  Grid: 3 short x 3 long x 4 rebal x 2 N x 2 dir = 144 combos")
    print("=" * 72)

    print("\nLoading data...")
    daily = load_daily_data()
    closes, volumes = build_panel(daily)
    print(f"\nPanel: {closes.shape[0]} days x {closes.shape[1]} assets")
    print(f"Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    # 1. Full parameter scan
    df_results, results_list = run_full_scan(closes, volumes)

    # Determine best overall params
    best_row = df_results.loc[df_results["sharpe"].idxmax()]
    best_sw   = int(best_row["short_w"])
    best_lw   = int(best_row["long_w"])
    best_rf   = int(best_row["rebal"])
    best_n    = int(best_row["n"])
    best_dir  = str(best_row["direction"])
    best_tag  = str(best_row["tag"])
    print(f"\n  BEST OVERALL: {best_tag} Sharpe={best_row['sharpe']:.3f}")

    # 2. Walk-forward
    wf_df = walk_forward(closes, volumes)

    # 3. Split-half
    sh_corr, sh_h1_mean, sh_h2_mean = split_half_test(closes, volumes)

    # 4. Correlation with H-012
    corr_012 = correlation_with_h012(closes, volumes,
                                     best_sw, best_lw, best_rf, best_n, best_dir)

    # 5. Fee sensitivity
    fee_res = fee_sensitivity(closes, volumes,
                              best_sw, best_lw, best_rf, best_n, best_dir)

    # ---------------------------------------------------------
    # Summary and verdict
    # ---------------------------------------------------------
    n_positive = int((df_results["sharpe"] > 0).sum())
    pct_positive = n_positive / len(df_results) * 100
    wf_n_pos = int((wf_df["test_sharpe"] > 0).sum()) if len(wf_df) > 0 else 0
    wf_n_total = len(wf_df)
    wf_mean = float(wf_df["test_sharpe"].mean()) if len(wf_df) > 0 else 0

    # Per-direction stats
    direction_stats = {}
    for dirn in DIRECTIONS:
        sub = df_results[df_results["direction"] == dirn]
        if len(sub) == 0:
            continue
        direction_stats[dirn] = {
            "n_positive": int((sub["sharpe"] > 0).sum()),
            "n_total": len(sub),
            "pct_positive": float((sub["sharpe"] > 0).mean() * 100),
            "mean_sharpe": float(sub["sharpe"].mean()),
            "median_sharpe": float(sub["sharpe"].median()),
            "best_sharpe": float(sub["sharpe"].max()),
            "best_tag": str(sub.loc[sub["sharpe"].idxmax(), "tag"]),
        }

    # ---------------------------------------------------------
    # VERDICT
    # ---------------------------------------------------------
    print("\n" + "=" * 72)
    print("VERDICT")
    print("=" * 72)

    reject_reasons = []
    conditional_flags = []

    # Check 1: IS positive rate >= 80%
    if pct_positive < 80:
        reject_reasons.append(f"IS positive rate {pct_positive:.1f}% < 80%")
    elif pct_positive < 90:
        conditional_flags.append(f"IS positive rate {pct_positive:.1f}% (borderline, want 90%+)")

    # Check 2: WF positive >= 4/6
    if wf_n_total > 0 and wf_n_pos < 4:
        reject_reasons.append(f"WF positive {wf_n_pos}/{wf_n_total} < 4/6")
    elif wf_n_total > 0 and wf_n_pos < 5:
        conditional_flags.append(f"WF positive {wf_n_pos}/{wf_n_total} (want 5+/6)")

    # Check 3: Split-half correlation > 0
    if sh_corr <= 0:
        reject_reasons.append(f"Split-half corr {sh_corr:.3f} <= 0 (unstable)")
    elif sh_corr < 0.2:
        conditional_flags.append(f"Split-half corr {sh_corr:.3f} (low, want > 0.2)")

    # Check 4: H-012 correlation < 0.6
    if corr_012 > 0.6:
        reject_reasons.append(f"H-012 correlation {corr_012:.3f} > 0.6 (redundant)")
    elif corr_012 > 0.4:
        conditional_flags.append(f"H-012 correlation {corr_012:.3f} (moderate overlap)")

    if reject_reasons:
        verdict = "REJECTED"
        print(f"  VERDICT: REJECTED")
        for r in reject_reasons:
            print(f"    - {r}")
    elif conditional_flags:
        verdict = "CONDITIONAL"
        print(f"  VERDICT: CONDITIONAL")
        for f_ in conditional_flags:
            print(f"    - {f_}")
    else:
        verdict = "CONFIRMED"
        print(f"  VERDICT: CONFIRMED (all criteria met)")

    print(f"\n  Key metrics:")
    print(f"    Total params tested:  {len(df_results)}")
    print(f"    IS positive:          {n_positive}/{len(df_results)} ({pct_positive:.1f}%)")
    print(f"    Split-half corr:      {sh_corr:.3f}")
    print(f"    Split-half H1 mean:   {sh_h1_mean:.3f}")
    print(f"    Split-half H2 mean:   {sh_h2_mean:.3f}")
    print(f"    WF positive:          {wf_n_pos}/{wf_n_total}")
    print(f"    WF mean OOS Sharpe:   {wf_mean:.3f}")
    print(f"    H-012 correlation:    {corr_012:.3f}")
    print(f"    Best direction:       {best_dir}")
    print(f"    Best params:          {best_tag}")
    print(f"    Best Sharpe:          {best_row['sharpe']:.3f}")
    print(f"    Best annual return:   {best_row['annual_ret']*100:.1f}%")
    print(f"    Best max drawdown:    {best_row['max_dd']*100:.1f}%")
    print(f"    Best win rate:        {best_row['win_rate']*100:.1f}%")

    # ---------------------------------------------------------
    # Save results
    # ---------------------------------------------------------
    output = {
        "hypothesis": "H-128",
        "name": "Dollar Volume Velocity Factor",
        "factor": "dv_velocity = short_mean(close*vol) / long_mean(close*vol) - 1",
        "directions_tested": DIRECTIONS,
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
        "wf_folds_positive": wf_n_pos,
        "wf_folds_total": wf_n_total,
        "wf_mean_oos_sharpe": round(wf_mean, 3),
        "wf_details": wf_df.to_dict("records") if len(wf_df) > 0 else [],
        "split_half_corr": round(float(sh_corr), 3),
        "split_half_h1_mean": round(float(sh_h1_mean), 3),
        "split_half_h2_mean": round(float(sh_h2_mean), 3),
        "corr_h012": round(float(corr_012), 3),
        "fee_sensitivity": fee_res,
        "verdict": verdict,
        "reject_reasons": reject_reasons,
        "conditional_flags": conditional_flags if verdict == "CONDITIONAL" else [],
        "data_period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "n_assets": closes.shape[1],
        "n_days": closes.shape[0],
        "all_results": results_list,
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")

    # Print clean summary
    print("\n" + "=" * 72)
    print("CLEAN SUMMARY (without raw results):")
    print("=" * 72)
    print(json.dumps({k: v for k, v in output.items()
                      if k not in ("all_results", "wf_details")}, indent=2))
