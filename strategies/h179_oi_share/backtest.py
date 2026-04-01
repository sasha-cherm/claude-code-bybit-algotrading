#!/usr/bin/env python3
"""
H-179: OI Share Change Factor (14 Assets)

Concept: Track each asset's share of total universe Open Interest (OI) over time.
Assets whose OI share is growing (attracting more speculative attention relative
to peers) go long. Assets whose OI share is declining go short.

This differs from H-044 (OI-price divergence, which looks at OI change vs price
direction) because this measures RELATIVE OI allocation -- an asset's share of
the total pie.

Logic:
  For each asset on each rebalance day:
    1. Compute OI share = asset_OI / sum(all_OI)
    2. Compute share_change = OI_share(today) - OI_share(today - lookback)
    3. Rank assets cross-sectionally by share_change
    4. Two directions:
       - growing_long: Long top-N (growing share), Short bottom-N (shrinking share)
       - shrinking_long: opposite
    5. Dollar-neutral, equal weight within legs

Transaction costs: 0.06% per side (0.12% round trip) on each rebalance.

Parameter grid:
  Lookback (LB)  : [5, 10, 20, 30, 60]
  Rebalance (R)  : [3, 5, 7]
  N (top/bottom) : [3, 4]
  Direction      : [growing_long, shrinking_long]
  Total: 5 x 3 x 2 x 2 = 60 combos

Validation (4-stage):
  1. IS: >= 80% of combos in the better direction must have positive Sharpe (else REJECT)
  2. Walk-Forward: 6 folds, best IS params per fold, need >= 4/6 positive OOS
  3. Split-Half: Run full grid on each half, both halves' best-combo Sharpe > 0
  4. Correlation: max |corr| < 0.40 with H-012, H-076, H-160, H-169
"""

import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX",
    "DOT", "LINK", "NEAR", "OP", "ARB", "ATOM", "SUI",
]

# For closes (used by reference strategies)
ASSETS_SLASH = [f"{a}/USDT" for a in ASSETS]

DATA_DIR = ROOT / "data"
OI_DIR = DATA_DIR / "oi"

# Parameter grid
LOOKBACKS = [5, 10, 20, 30, 60]
REBALS = [3, 5, 7]
NS = [3, 4]
DIRECTIONS = ["growing_long", "shrinking_long"]

# Transaction costs
COST_PER_SIDE = 0.0006  # 0.06% per side

# Walk-forward config
WF_FOLDS = 6
WF_TEST_DAYS = 90   # ~3 months per fold
WF_TRAIN_MIN = 120  # minimum IS training days


# -- Data loading ----------------------------------------------------------

def load_daily_closes():
    """Load 1d parquet files for all assets, return closes DataFrame.
    Keys are plain symbols (BTC, ETH, etc.)."""
    frames = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        if "close" in df.columns and len(df) >= 200:
            s = df["close"].copy()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            frames[asset] = s
    closes = pd.DataFrame(frames).sort_index()
    closes = closes.dropna(how="all").ffill().dropna()
    return closes


def load_daily_closes_slash():
    """Load 1d parquet files with SYM/USDT keys (for reference strategies)."""
    frames = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        if "close" in df.columns and len(df) >= 200:
            s = df["close"].copy()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            frames[f"{asset}/USDT"] = s
    closes = pd.DataFrame(frames).sort_index()
    closes = closes.dropna(how="all").ffill().dropna()
    return closes


def load_oi():
    """Load daily OI, tz-naive index. Keys are plain symbols."""
    frames = {}
    for asset in ASSETS:
        fp = OI_DIR / f"{asset}_oi_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        s = df["openInterest"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        frames[asset] = s
    oi = pd.DataFrame(frames).sort_index()
    oi = oi.dropna(how="all")
    return oi


# -- Evaluation helper -----------------------------------------------------

def evaluate(rets, label=""):
    """Compute Sharpe, annual return, max DD from daily return series."""
    if rets is None or len(rets) < 30:
        return None
    ann = rets.mean() * 365
    vol = rets.std() * np.sqrt(365)
    sharpe = ann / vol if vol > 1e-8 else 0.0
    cum = (1 + rets).cumprod()
    dd = (cum / cum.cummax() - 1).min()
    return {
        "label": label,
        "sharpe": round(sharpe, 4),
        "annual": round(ann * 100, 2),
        "dd": round(dd * 100, 2),
        "days": len(rets),
    }


# -- Core backtest ---------------------------------------------------------

def backtest_oi_share(closes, oi, lookback, rebal_freq, n, direction):
    """
    OI Share Change Factor backtest.

    Args:
        closes: DataFrame of daily closes (plain symbol keys)
        oi: DataFrame of daily OI (plain symbol keys)
        lookback: how far back to measure share change
        rebal_freq: rebalance every N days
        n: number of longs and shorts
        direction: "growing_long" or "shrinking_long"
    Returns:
        pd.Series of daily portfolio returns (or None)
    """
    # Align closes and OI on common dates and assets
    common_assets = sorted(set(closes.columns) & set(oi.columns))
    if len(common_assets) < 2 * n:
        return None

    common_dates = closes.index.intersection(oi.index)
    if len(common_dates) < lookback + 60:
        return None

    closes_a = closes.loc[common_dates, common_assets]
    oi_a = oi.loc[common_dates, common_assets]

    # Forward-fill OI gaps
    oi_a = oi_a.ffill()

    # Compute OI share: each asset's OI / total OI
    total_oi = oi_a.sum(axis=1)
    oi_share = oi_a.div(total_oi, axis=0)

    # Compute returns
    returns = closes_a.pct_change()

    warmup = lookback + 5
    dates = closes_a.index

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=common_assets)
    prev_weights = pd.Series(0.0, index=common_assets)

    for i in range(warmup, len(dates)):
        # Apply existing weights to get day's return
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": day_ret})

        # Rebalance check
        if i - last_rebal >= rebal_freq:
            # Compute share_change for each asset
            current_share = oi_share.iloc[i]
            past_share = oi_share.iloc[i - lookback]

            share_change = current_share - past_share
            share_change = share_change.dropna()

            if len(share_change) < 2 * n:
                continue

            ranked = share_change.sort_values(ascending=True)
            # ranked: ascending by share_change
            # Bottom = most shrinking share
            # Top = most growing share

            if direction == "growing_long":
                # Long top-N (growing share), Short bottom-N (shrinking share)
                longs = ranked.index[-n:]
                shorts = ranked.index[:n]
            else:
                # Opposite: Long bottom-N (shrinking), Short top-N (growing)
                longs = ranked.index[:n]
                shorts = ranked.index[-n:]

            new_weights = pd.Series(0.0, index=common_assets)
            for s in longs:
                new_weights[s] = 1.0 / n
            for s in shorts:
                new_weights[s] = -1.0 / n

            # Transaction costs: proportional to turnover
            turnover = (new_weights - prev_weights).abs().sum()
            tc = turnover * COST_PER_SIDE
            if portfolio_rets:
                portfolio_rets[-1]["return"] -= tc

            prev_weights = weights.copy()
            weights = new_weights
            last_rebal = i

    if not portfolio_rets:
        return None
    df_out = pd.DataFrame(portfolio_rets).set_index("date")
    return df_out["return"]


# -- Reference strategy returns (for correlation) --------------------------

def backtest_momentum(closes, lookback=60, rebal_freq=5, n=4):
    """H-012 cross-sectional momentum."""
    rets = closes.pct_change().dropna()
    dates = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            mom = closes.iloc[i - 1] / closes.iloc[i - 1 - lookback] - 1
            ranked = mom.sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def backtest_efficiency(closes, lookback=40, rebal_freq=5, n=4):
    """H-076 price efficiency factor."""
    rets = closes.pct_change().dropna()
    dates = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                p = closes[sym].iloc[i - lookback: i]
                net_move = abs(p.iloc[-1] / p.iloc[0] - 1)
                daily_moves = abs(p.pct_change().dropna()).sum()
                signals[sym] = net_move / daily_moves if daily_moves > 0 else 0.0
            ranked = pd.Series(signals).sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def backtest_trend_quality(closes, lookback=60, rebal_freq=5, n=3):
    """H-160 trend quality (efficiency x inv_vol)."""
    rets = closes.pct_change().dropna()
    dates = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                p = closes[sym].iloc[i - lookback: i]
                net_move = abs(p.iloc[-1] / p.iloc[0] - 1)
                daily_moves = abs(p.pct_change().dropna()).sum()
                eff = net_move / daily_moves if daily_moves > 0 else 0.0
                vol = rets[sym].iloc[max(0, i - lookback): i].std()
                inv_vol = 1.0 / vol if vol > 1e-8 else 0.0
                signals[sym] = eff * inv_vol
            ranked = pd.Series(signals).sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def backtest_h169(closes, lookback=10, rebal_freq=5, n=4):
    """H-169 beta-adjusted momentum (alpha vs BTC)."""
    btc_key = "BTC/USDT"
    if btc_key not in closes.columns:
        return None
    btc = closes[btc_key]
    non_btc = [c for c in closes.columns if c != btc_key]
    rets = closes.pct_change().dropna()
    dates = rets.index
    warmup = lookback + 10
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in non_btc:
                asset_r = closes[sym].pct_change().dropna().iloc[max(0, i - lookback): i]
                btc_r = btc.pct_change().dropna().iloc[max(0, i - lookback): i]
                common = asset_r.index.intersection(btc_r.index)
                if len(common) < lookback // 2:
                    continue
                a = asset_r.loc[common].values
                b = btc_r.loc[common].values
                var_b = np.var(b)
                if var_b < 1e-12:
                    continue
                beta = np.cov(a, b)[0, 1] / var_b
                alpha = a.sum() - beta * b.sum()
                signals[sym] = alpha
            if len(signals) >= n * 2:
                ranked = pd.Series(signals).sort_values(ascending=False)
                weights = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:n]:
                    weights[s] = 1.0 / n
                for s in ranked.index[-n:]:
                    weights[s] = -1.0 / n
                last_rebal = i
    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


# -- Walk-forward validation -----------------------------------------------

def run_walk_forward(closes, oi, best_direction):
    """
    6-fold walk-forward. For each fold, select best IS params from full grid
    (within the best direction) on training data, then evaluate OOS.
    """
    n_total = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        oos_end = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break

        train_closes = closes.iloc[:oos_start]
        train_oi = oi.loc[oi.index.isin(train_closes.index) | (oi.index <= train_closes.index[-1])]
        train_oi = train_oi.loc[:train_closes.index[-1]]

        oos_closes = closes.iloc[oos_start:oos_end]
        oos_oi = oi.loc[(oi.index >= oos_closes.index[0]) & (oi.index <= oos_closes.index[-1])]

        if len(train_closes) < WF_TRAIN_MIN or len(oos_closes) < 20:
            break

        # IS param selection on training data
        best_sharpe = -np.inf
        best_params = None
        for lb in LOOKBACKS:
            for rf in REBALS:
                for nn in NS:
                    r = backtest_oi_share(train_closes, train_oi, lb, rf, nn, best_direction)
                    ev = evaluate(r)
                    if ev and ev["sharpe"] > best_sharpe:
                        best_sharpe = ev["sharpe"]
                        best_params = (lb, rf, nn)

        if best_params is None:
            fold_results.append({
                "fold": fold + 1, "is_params": "none", "is_sharpe": 0,
                "oos_sharpe": None, "oos_start": "", "oos_end": "",
            })
            continue

        lb, rf, nn = best_params
        # OOS evaluation
        oos_r = backtest_oi_share(oos_closes, oi, lb, rf, nn, best_direction)
        oos_e = evaluate(oos_r)

        oos_start_date = closes.index[oos_start]
        oos_end_date = closes.index[min(oos_end - 1, len(closes) - 1)]

        fold_results.append({
            "fold": fold + 1,
            "is_params": f"LB{lb}_R{rf}_N{nn}",
            "is_sharpe": round(best_sharpe, 3),
            "oos_sharpe": oos_e["sharpe"] if oos_e else None,
            "oos_start": str(oos_start_date)[:10],
            "oos_end": str(oos_end_date)[:10],
        })

    return fold_results


# -- Split-half validation -------------------------------------------------

def run_split_half(closes, oi, best_direction):
    """
    Run full grid (within best direction) on each half.
    Report best-combo Sharpe and mean Sharpe for each half.
    """
    half = len(closes) // 2
    h1_closes = closes.iloc[:half]
    h2_closes = closes.iloc[half:]

    h1_oi = oi.loc[oi.index <= h1_closes.index[-1]]
    h2_oi = oi.loc[oi.index >= h2_closes.index[0]]

    h1_results = []
    h2_results = []

    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                r1 = backtest_oi_share(h1_closes, h1_oi, lb, rf, nn, best_direction)
                r2 = backtest_oi_share(h2_closes, h2_oi, lb, rf, nn, best_direction)
                e1 = evaluate(r1)
                e2 = evaluate(r2)
                if e1:
                    h1_results.append(e1)
                if e2:
                    h2_results.append(e2)

    if not h1_results or not h2_results:
        return None, None, None, None

    h1_sharpes = [r["sharpe"] for r in h1_results]
    h2_sharpes = [r["sharpe"] for r in h2_results]

    return (
        round(max(h1_sharpes), 3),
        round(max(h2_sharpes), 3),
        round(np.mean(h1_sharpes), 3),
        round(np.mean(h2_sharpes), 3),
    )


# -- Correlation helper ----------------------------------------------------

def safe_corr(a, b):
    if a is None or b is None:
        return float("nan")
    common = a.dropna().index.intersection(b.dropna().index)
    if len(common) < 30:
        return float("nan")
    return round(float(np.corrcoef(a.loc[common].values, b.loc[common].values)[0, 1]), 3)


# -- Main ------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  H-179: OI Share Change Factor (14 Assets)")
    print("=" * 60)

    print("\nLoading daily close data...")
    closes = load_daily_closes()
    n_assets = len(closes.columns)
    n_days = len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")

    print("\nLoading OI data...")
    oi = load_oi()
    n_oi_assets = len(oi.columns)
    n_oi_days = len(oi)
    print(f"Loaded OI for {n_oi_assets} assets, {n_oi_days} daily bars")
    print(f"OI date range: {oi.index[0]} -> {oi.index[-1]}")

    # Align dates
    common_dates = closes.index.intersection(oi.index)
    print(f"Common dates: {len(common_dates)} ({common_dates[0]} -> {common_dates[-1]})")

    common_assets = sorted(set(closes.columns) & set(oi.columns))
    print(f"Common assets: {len(common_assets)} — {common_assets}")

    if len(common_assets) < 6:
        print("ERROR: Too few common assets. Aborting.")
        sys.exit(1)

    # ==================================================================
    # Stage 1: IS Parameter Scan
    # ==================================================================
    total_combos = len(LOOKBACKS) * len(REBALS) * len(NS) * len(DIRECTIONS)
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")

    all_results = []
    count = 0
    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                for d in DIRECTIONS:
                    count += 1
                    r = backtest_oi_share(closes, oi, lb, rf, nn, d)
                    ev = evaluate(r, f"LB{lb}_R{rf}_N{nn}_{d}")
                    if ev:
                        ev["lb"] = lb
                        ev["rf"] = rf
                        ev["n"] = nn
                        ev["direction"] = d
                        all_results.append(ev)
                    if count % 10 == 0:
                        print(f"  {count}/{total_combos} done...")

    print(f"  {count}/{total_combos} done.")

    if not all_results:
        print("No valid results! REJECTED.")
        return

    df_res = pd.DataFrame(all_results)

    # Analyze by direction
    print(f"\n  Results by direction:")
    for d in DIRECTIONS:
        sub = df_res[df_res["direction"] == d]
        n_pos = (sub["sharpe"] > 0).sum()
        pct = n_pos / len(sub) * 100 if len(sub) > 0 else 0
        mean_s = sub["sharpe"].mean() if len(sub) > 0 else 0
        print(f"    {d}: {n_pos}/{len(sub)} positive ({pct:.1f}%), mean Sharpe {mean_s:.3f}")

    # Select the better direction
    dir_stats = {}
    for d in DIRECTIONS:
        sub = df_res[df_res["direction"] == d]
        if len(sub) > 0:
            n_pos = (sub["sharpe"] > 0).sum()
            pct = n_pos / len(sub) * 100
            dir_stats[d] = {"pct_positive": pct, "mean_sharpe": sub["sharpe"].mean(), "count": len(sub)}

    # Pick direction with higher positive rate
    best_dir = max(dir_stats, key=lambda d: dir_stats[d]["pct_positive"])
    best_dir_stats = dir_stats[best_dir]
    pct_positive = best_dir_stats["pct_positive"]
    mean_sharpe_best_dir = best_dir_stats["mean_sharpe"]

    print(f"\n  Better direction: {best_dir}")
    print(f"  Positive Sharpe: {pct_positive:.1f}%")
    print(f"  Mean Sharpe: {mean_sharpe_best_dir:.3f}")

    # Overall stats
    n_positive_all = (df_res["sharpe"] > 0).sum()
    mean_sharpe_all = df_res["sharpe"].mean()
    median_sharpe_all = df_res["sharpe"].median()
    print(f"\n  Overall (all directions):")
    print(f"  Valid combos: {len(df_res)}/{total_combos}")
    print(f"  Positive Sharpe: {n_positive_all}/{len(df_res)} ({n_positive_all/len(df_res)*100:.1f}%)")
    print(f"  Mean Sharpe: {mean_sharpe_all:.3f}")
    print(f"  Median Sharpe: {median_sharpe_all:.3f}")

    # Filter to best direction for further analysis
    df_best = df_res[df_res["direction"] == best_dir].copy()
    df_best = df_best.sort_values("sharpe", ascending=False)

    # Top 10
    print(f"\n  Top 10 combos ({best_dir}):")
    for _, row in df_best.head(10).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    # Bottom 5
    print(f"\n  Bottom 5 combos ({best_dir}):")
    for _, row in df_best.tail(5).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    # Best combo
    best_row = df_best.iloc[0]
    best_lb = int(best_row["lb"])
    best_rf = int(best_row["rf"])
    best_n = int(best_row["n"])

    print(f"\n  Best combo: LB{best_lb}_R{best_rf}_N{best_n} ({best_dir})")
    print(f"  Sharpe: {best_row['sharpe']:.3f}, Annual: {best_row['annual']:.1f}%, "
          f"Max DD: {best_row['dd']:.1f}%, Days: {int(best_row['days'])}")

    # IS gate: 80% of combos in best direction must be positive
    is_pass = pct_positive >= 80.0
    if not is_pass:
        print(f"\n*** FAIL IS: {pct_positive:.1f}% positive in {best_dir} < 80% threshold ***")
        print("REJECTED at Stage 1. Skipping further validation.")

        result_json = {
            "hypothesis": "H-179",
            "name": "OI Share Change Factor",
            "status": "REJECTED",
            "reason": f"IS positive rate {pct_positive:.1f}% ({best_dir}) < 80% threshold",
            "best_direction": best_dir,
            "direction_stats": {
                d: {
                    "pct_positive": round(dir_stats[d]["pct_positive"], 1),
                    "mean_sharpe": round(dir_stats[d]["mean_sharpe"], 3),
                    "n_combos": dir_stats[d]["count"],
                }
                for d in dir_stats
            },
            "is_positive_rate": round(pct_positive, 1),
            "is_mean_sharpe": round(mean_sharpe_best_dir, 3),
            "best_params": {"lookback": best_lb, "rebal": best_rf, "n": best_n, "direction": best_dir},
            "best_sharpe": round(float(best_row["sharpe"]), 3),
            "best_annual_return": round(float(best_row["annual"]), 1),
            "best_max_dd": round(float(best_row["dd"]), 1),
            "n_assets": n_assets,
            "n_oi_assets": n_oi_assets,
            "n_days": n_days,
            "total_combos": total_combos,
            "valid_combos": len(df_res),
        }
        results_path = Path(__file__).parent / "results.json"
        with open(results_path, "w") as f:
            json.dump(result_json, f, indent=2)
        print(f"\nResults written to {results_path}")
        return

    # ==================================================================
    # Stage 2: Walk-Forward Validation
    # ==================================================================
    print(f"\n--- Stage 2: Walk-Forward ({WF_FOLDS} folds, {WF_TEST_DAYS}d OOS each) ---")
    wf_results = run_walk_forward(closes, oi, best_dir)

    wf_oos_sharpes = [r["oos_sharpe"] for r in wf_results if r["oos_sharpe"] is not None]
    wf_n_pos = sum(1 for s in wf_oos_sharpes if s > 0)

    for r in wf_results:
        oos_s = f"{r['oos_sharpe']:.3f}" if r['oos_sharpe'] is not None else "N/A"
        print(f"  Fold {r['fold']}: IS={r['is_params']} (IS Sharpe {r['is_sharpe']:.3f}), "
              f"OOS={r['oos_start']}~{r['oos_end']}, OOS Sharpe {oos_s}")

    mean_oos = np.mean(wf_oos_sharpes) if wf_oos_sharpes else float("nan")
    print(f"\n  WF summary: {wf_n_pos}/{len(wf_oos_sharpes)} positive OOS folds, "
          f"mean OOS Sharpe: {mean_oos:.3f}")

    wf_pass = wf_n_pos >= 4
    if not wf_pass:
        print(f"  *** FAIL WF: {wf_n_pos}/{len(wf_oos_sharpes)} < 4/6 threshold ***")

    # ==================================================================
    # Stage 3: Split-Half
    # ==================================================================
    print(f"\n--- Stage 3: Split-Half Stability ---")
    sh_best_h1, sh_best_h2, sh_mean_h1, sh_mean_h2 = run_split_half(closes, oi, best_dir)

    if sh_best_h1 is not None:
        print(f"  H1 best Sharpe: {sh_best_h1:.3f}, H1 mean Sharpe: {sh_mean_h1:.3f}")
        print(f"  H2 best Sharpe: {sh_best_h2:.3f}, H2 mean Sharpe: {sh_mean_h2:.3f}")
        sh_pass = sh_best_h1 > 0 and sh_best_h2 > 0
        if not sh_pass:
            print(f"  *** FAIL Split-Half: need both best Sharpes > 0 ***")
    else:
        print("  Split-half: insufficient data")
        sh_pass = False

    # ==================================================================
    # Stage 4: Correlation with Existing Factors
    # ==================================================================
    print(f"\n--- Stage 4: Correlation with Existing Factors ---")
    best_rets = backtest_oi_share(closes, oi, best_lb, best_rf, best_n, best_dir)

    # Reference strategies use SYM/USDT keys
    print("  Computing reference strategy returns...")
    closes_slash = load_daily_closes_slash()

    mom_rets = backtest_momentum(closes_slash)
    eff_rets = backtest_efficiency(closes_slash)
    tq_rets = backtest_trend_quality(closes_slash)
    h169_rets = backtest_h169(closes_slash)

    corr_h012 = safe_corr(best_rets, mom_rets)
    corr_h076 = safe_corr(best_rets, eff_rets)
    corr_h160 = safe_corr(best_rets, tq_rets)
    corr_h169 = safe_corr(best_rets, h169_rets)

    print(f"  H-012 (momentum):      {corr_h012:.3f}")
    print(f"  H-076 (efficiency):    {corr_h076:.3f}")
    print(f"  H-160 (trend quality): {corr_h160:.3f}")
    print(f"  H-169 (alpha mom):     {corr_h169:.3f}")

    max_abs_corr = max(
        abs(corr_h012) if not np.isnan(corr_h012) else 0,
        abs(corr_h076) if not np.isnan(corr_h076) else 0,
        abs(corr_h160) if not np.isnan(corr_h160) else 0,
        abs(corr_h169) if not np.isnan(corr_h169) else 0,
    )
    corr_pass = max_abs_corr < 0.40
    if not corr_pass:
        print(f"  *** FAIL Correlation: max |corr| = {max_abs_corr:.3f} >= 0.40 ***")
    else:
        print(f"  PASS: max |corr| = {max_abs_corr:.3f} < 0.40")

    # ==================================================================
    # Final Verdict
    # ==================================================================
    print(f"\n{'='*60}")
    print("  FINAL VERDICT")
    print(f"{'='*60}")
    print(f"  IS positive rate: {pct_positive:.1f}% {'PASS' if is_pass else 'FAIL'}")
    print(f"  Walk-Forward: {wf_n_pos}/{len(wf_oos_sharpes)} positive {'PASS' if wf_pass else 'FAIL'}")
    print(f"  Split-Half: H1={sh_best_h1}, H2={sh_best_h2} {'PASS' if sh_pass else 'FAIL'}")
    print(f"  Correlation: max |corr|={max_abs_corr:.3f} {'PASS' if corr_pass else 'FAIL'}")

    all_pass = is_pass and wf_pass and sh_pass and corr_pass
    status = "CONFIRMED" if all_pass else "REJECTED"
    rejection_reasons = []
    if not is_pass:
        rejection_reasons.append(f"IS positive rate {pct_positive:.1f}% < 80%")
    if not wf_pass:
        rejection_reasons.append(f"WF {wf_n_pos}/{len(wf_oos_sharpes)} < 4/6")
    if not sh_pass:
        rejection_reasons.append(f"Split-half best Sharpes: H1={sh_best_h1}, H2={sh_best_h2}")
    if not corr_pass:
        rejection_reasons.append(f"max |corr| {max_abs_corr:.3f} >= 0.40")

    print(f"\n  Status: {status}")
    if rejection_reasons:
        print(f"  Reason: {'; '.join(rejection_reasons)}")

    # ==================================================================
    # Write results.json
    # ==================================================================
    result_json = {
        "hypothesis": "H-179",
        "name": "OI Share Change Factor",
        "status": status,
        "reason": "; ".join(rejection_reasons) if rejection_reasons else "All 4 stages passed",
        "best_direction": best_dir,
        "direction_stats": {
            d: {
                "pct_positive": round(dir_stats[d]["pct_positive"], 1),
                "mean_sharpe": round(dir_stats[d]["mean_sharpe"], 3),
                "n_combos": dir_stats[d]["count"],
            }
            for d in dir_stats
        },
        "is_positive_rate": round(pct_positive, 1),
        "is_mean_sharpe": round(mean_sharpe_best_dir, 3),
        "is_median_sharpe": round(float(df_best["sharpe"].median()), 3),
        "best_params": {"lookback": best_lb, "rebal": best_rf, "n": best_n, "direction": best_dir},
        "best_sharpe": round(float(best_row["sharpe"]), 3),
        "best_annual_return": round(float(best_row["annual"]), 1),
        "best_max_dd": round(float(best_row["dd"]), 1),
        "wf_folds": [
            {"fold": r["fold"], "is_params": r["is_params"],
             "is_sharpe": r["is_sharpe"], "oos_sharpe": r["oos_sharpe"],
             "oos_start": r["oos_start"], "oos_end": r["oos_end"]}
            for r in wf_results
        ],
        "wf_positive_folds": wf_n_pos,
        "wf_total_folds": len(wf_oos_sharpes),
        "wf_mean_oos_sharpe": round(mean_oos, 3) if not np.isnan(mean_oos) else None,
        "split_half": {
            "h1_best_sharpe": sh_best_h1,
            "h2_best_sharpe": sh_best_h2,
            "h1_mean_sharpe": sh_mean_h1,
            "h2_mean_sharpe": sh_mean_h2,
        },
        "correlations": {
            "H-012_momentum": corr_h012,
            "H-076_efficiency": corr_h076,
            "H-160_trend_quality": corr_h160,
            "H-169_alpha_momentum": corr_h169,
        },
        "max_abs_correlation": round(max_abs_corr, 3),
        "n_assets": n_assets,
        "n_oi_assets": n_oi_assets,
        "n_days": n_days,
        "total_combos": total_combos,
        "valid_combos": len(df_res),
        "validation": {
            "is_pass": is_pass,
            "wf_pass": wf_pass,
            "sh_pass": sh_pass,
            "corr_pass": corr_pass,
        },
    }

    results_path = Path(__file__).parent / "results.json"
    with open(results_path, "w") as f:
        json.dump(result_json, f, indent=2)
    print(f"\nResults written to {results_path}")


if __name__ == "__main__":
    main()
