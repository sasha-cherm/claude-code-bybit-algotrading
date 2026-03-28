"""
H-123: Volume-Price Elasticity Factor (Cross-Sectional)

For each asset, regress |daily return| on log(volume) over a rolling window
to estimate how responsive price is to volume changes. The slope coefficient
(beta) from this OLS regression is the "elasticity" measure.

Cross-sectional ranking:
  LONG  top N assets with highest elasticity (price responds most to volume)
  SHORT bottom N assets with lowest elasticity (price responds least)

Intuition: Assets where price moves are strongly linked to volume activity
may be experiencing genuine, information-driven moves (trend continuation),
while low-elasticity assets have noisy price action decoupled from volume.

Parameter grid (60 combos):
  Regression window : [15, 20, 30, 40, 60] days
  Rebalance freq    : [3, 5, 7, 10] days
  N positions each  : [3, 4, 5]

Sharpe: daily mean / daily std * sqrt(365)
Fee: 5 bps round-trip per rebalance (as specified)
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

FEE_RATE = 0.0005  # 5 bps round-trip per rebal
INITIAL_CAPITAL = 10_000.0

REG_WINDOWS = [15, 20, 30, 40, 60]
REBAL_FREQS = [3, 5, 7, 10]
N_SIZES     = [3, 4, 5]

WF_FOLDS = 6
WF_TRAIN_DAYS = 180
WF_TEST_DAYS  = 90


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
    return daily


def build_close_matrix(daily: dict) -> pd.DataFrame:
    closes = {}
    for sym, df in daily.items():
        closes[sym] = df["close"]
    return pd.DataFrame(closes).dropna(how="all").ffill()


def build_volume_matrix(daily: dict) -> pd.DataFrame:
    volumes = {}
    for sym, df in daily.items():
        volumes[sym] = df["volume"]
    return pd.DataFrame(volumes).dropna(how="all").fillna(0)


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


def compute_elasticity_matrix(
    closes: pd.DataFrame,
    volumes: pd.DataFrame,
    window: int,
) -> pd.DataFrame:
    """
    Rolling OLS of |log_return| on log(volume) for each asset.
    Returns slope coefficient (beta) as the elasticity measure.

    For each asset and each day, we run:
        |log_return_t| = alpha + beta * log(volume_t) + epsilon
    over the trailing `window` days. Beta is returned.

    Uses vectorized rolling covariance / variance for speed.
    """
    # Align indices
    common_idx = closes.index.intersection(volumes.index)
    c = closes.loc[common_idx]
    v = volumes.loc[common_idx]

    # Compute |log returns|
    log_ret = np.log(c / c.shift(1))
    abs_log_ret = log_ret.abs()

    # Compute log(volume), replacing 0/NaN with NaN
    log_vol = np.log(v.replace(0, np.nan))

    # Rolling OLS slope: beta = Cov(Y, X) / Var(X)
    # where Y = |log_return|, X = log(volume)
    # Using rolling mean to compute cov and var

    roll_mean_x = log_vol.rolling(window=window, min_periods=window).mean()
    roll_mean_y = abs_log_ret.rolling(window=window, min_periods=window).mean()
    roll_mean_xy = (abs_log_ret * log_vol).rolling(window=window, min_periods=window).mean()
    roll_mean_x2 = (log_vol ** 2).rolling(window=window, min_periods=window).mean()

    cov_xy = roll_mean_xy - roll_mean_x * roll_mean_y
    var_x = roll_mean_x2 - roll_mean_x ** 2

    # Avoid division by zero
    var_x = var_x.replace(0, np.nan)

    beta = cov_xy / var_x

    return beta.reindex(closes.index)


def run_elasticity_factor(
    closes: pd.DataFrame,
    volumes: pd.DataFrame,
    window: int,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    fee_rate: float = FEE_RATE,
    pre_computed: pd.DataFrame | None = None,
) -> dict:
    if n_short is None:
        n_short = n_long

    if pre_computed is not None:
        elasticity = pre_computed
    else:
        elasticity = compute_elasticity_matrix(closes, volumes, window)

    n = len(closes)
    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count = 0
    warmup = window + 5

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            sig = elasticity.iloc[i - 1]
            valid = sig.dropna()

            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # Long highest elasticity, short lowest elasticity
            ranked = valid.sort_values(ascending=False)
            longs  = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

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
    metrics["n_trades"] = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"] = eq_series
    return metrics


# ---------- Full Parameter Scan ----------

def run_full_scan(closes: pd.DataFrame, volumes: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-123: VOLUME-PRICE ELASTICITY FACTOR -- Full Param Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps round-trip per rebal")
    print(f"  Strategy : LONG high elasticity (price responds to volume), "
          f"SHORT low elasticity")

    print("\n  Pre-computing elasticity matrices...")
    elasticity_cache = {}
    for w in REG_WINDOWS:
        print(f"    Window {w}d ...", end=" ", flush=True)
        elasticity_cache[w] = compute_elasticity_matrix(closes, volumes, w)
        print("done")

    results = []
    n_combos = len(REG_WINDOWS) * len(REBAL_FREQS) * len(N_SIZES)
    print(f"\n  Running {n_combos} param combos...")
    for w, rebal, n in product(REG_WINDOWS, REBAL_FREQS, N_SIZES):
        res = run_elasticity_factor(closes, volumes, w, rebal, n,
                                     pre_computed=elasticity_cache[w])
        tag = f"W{w}_R{rebal}_N{n}"
        results.append({
            "tag": tag, "window": w, "rebal": rebal, "n": n,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
        })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    pct_positive = n_positive / len(df) * 100
    print(f"\n  Results: {n_positive}/{len(df)} positive Sharpe ({pct_positive:.1f}%)")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"  Best: {df.loc[df['sharpe'].idxmax(), 'tag']} Sharpe={df['sharpe'].max():.3f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']:20s}  Sharpe={row['sharpe']:.3f}  "
              f"Ret={row['annual_ret']*100:.1f}%  DD={row['max_dd']*100:.1f}%  "
              f"WR={row['win_rate']*100:.1f}%")

    bot5 = df.nsmallest(5, "sharpe")
    print("\n  Bottom 5:")
    for _, row in bot5.iterrows():
        print(f"    {row['tag']:20s}  Sharpe={row['sharpe']:.3f}  "
              f"Ret={row['annual_ret']*100:.1f}%  DD={row['max_dd']*100:.1f}%  "
              f"WR={row['win_rate']*100:.1f}%")

    return df, results


# ---------- In-Sample / Out-of-Sample Split ----------

def run_is_oos_split(closes, volumes, split_pct=0.60):
    """Split data into IS (first 60%) and OOS (last 40%)."""
    split_idx = int(len(closes) * split_pct)
    is_closes  = closes.iloc[:split_idx]
    is_volumes = volumes.iloc[:split_idx]
    oos_closes  = closes.iloc[split_idx:]
    oos_volumes = volumes.iloc[split_idx:]

    print(f"\n  IS/OOS Split: IS={len(is_closes)} days, OOS={len(oos_closes)} days")
    print(f"    IS:  {is_closes.index[0].date()} to {is_closes.index[-1].date()}")
    print(f"    OOS: {oos_closes.index[0].date()} to {oos_closes.index[-1].date()}")

    # Run IS scan
    is_results = []
    for w, rebal, n in product(REG_WINDOWS, REBAL_FREQS, N_SIZES):
        res = run_elasticity_factor(is_closes, is_volumes, w, rebal, n)
        tag = f"W{w}_R{rebal}_N{n}"
        is_results.append({
            "tag": tag, "window": w, "rebal": rebal, "n": n,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
        })

    is_df = pd.DataFrame(is_results)
    n_pos_is = (is_df["sharpe"] > 0).sum()
    pct_pos_is = n_pos_is / len(is_df) * 100
    print(f"\n  IS: {n_pos_is}/{len(is_df)} positive Sharpe ({pct_pos_is:.1f}%)")
    print(f"  IS Mean Sharpe: {is_df['sharpe'].mean():.3f}")

    # Best IS params -> OOS
    best_is = is_df.loc[is_df["sharpe"].idxmax()]
    bw, br, bn = int(best_is["window"]), int(best_is["rebal"]), int(best_is["n"])
    oos_res = run_elasticity_factor(oos_closes, oos_volumes, bw, br, bn)
    print(f"\n  Best IS params: W{bw}_R{br}_N{bn} (IS Sharpe={best_is['sharpe']:.3f})")
    print(f"  OOS Sharpe: {oos_res['sharpe']:.3f}  "
          f"Ret={oos_res['annual_ret']*100:.1f}%  DD={oos_res['max_dd']*100:.1f}%")

    return is_df, {
        "best_is_params": f"W{bw}_R{br}_N{bn}",
        "is_sharpe": float(best_is["sharpe"]),
        "oos_sharpe": oos_res["sharpe"],
        "oos_annual_ret": oos_res["annual_ret"],
        "oos_max_dd": oos_res["max_dd"],
        "pct_positive_is": pct_pos_is,
        "n_positive_is": int(n_pos_is),
        "n_total_is": len(is_df),
    }


# ---------- Walk-Forward Validation ----------

def walk_forward(closes, volumes, n_folds=WF_FOLDS):
    """
    Walk-forward validation: 180d train, 90d test, 6 folds.
    Pick best params on train, evaluate on test.
    """
    print(f"\n  Walk-Forward Validation ({n_folds} folds, "
          f"{WF_TRAIN_DAYS}d train, {WF_TEST_DAYS}d test)")
    n = len(closes)
    total_needed = WF_TRAIN_DAYS + WF_TEST_DAYS

    if n < total_needed:
        print("    Not enough data for walk-forward!")
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

        train_closes  = closes.iloc[train_start:train_end]
        train_volumes = volumes.iloc[train_start:train_end]
        test_closes   = closes.iloc[test_start:test_end]
        test_volumes  = volumes.iloc[test_start:test_end]

        best_sharpe = -99
        best_p = None
        for w, rebal, nn in product(REG_WINDOWS, REBAL_FREQS, N_SIZES):
            if len(train_closes) < w + 30:
                continue
            res = run_elasticity_factor(train_closes, train_volumes, w, rebal, nn)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_p = (w, rebal, nn)

        if best_p is None:
            continue

        w, rebal, nn = best_p
        test_res = run_elasticity_factor(test_closes, test_volumes, w, rebal, nn)
        wf_results.append({
            "fold": fold,
            "train_sharpe": round(best_sharpe, 3),
            "test_sharpe": test_res["sharpe"],
            "params": f"W{w}_R{rebal}_N{nn}",
            "test_ret": test_res["annual_ret"],
            "test_dd": test_res["max_dd"],
        })
        print(f"    Fold {fold}: train Sharpe={best_sharpe:.3f} -> "
              f"test Sharpe={test_res['sharpe']:.3f} ({best_p})")

    if wf_results:
        wf_df = pd.DataFrame(wf_results)
        n_pos = (wf_df["test_sharpe"] > 0).sum()
        print(f"  WF Summary: {n_pos}/{len(wf_df)} positive, "
              f"mean OOS Sharpe={wf_df['test_sharpe'].mean():.3f}")
        return wf_df
    return pd.DataFrame()


# ---------- Split-Half Stability ----------

def split_half_test(closes, volumes):
    """Test stability: compute Sharpe for all params on each half of IS data, correlate."""
    # Use first 60% as IS, then split that in half
    split_idx = int(len(closes) * 0.60)
    is_closes = closes.iloc[:split_idx]
    is_volumes = volumes.iloc[:split_idx]

    mid = len(is_closes) // 2
    h1_c = is_closes.iloc[:mid]
    h1_v = is_volumes.iloc[:mid]
    h2_c = is_closes.iloc[mid:]
    h2_v = is_volumes.iloc[mid:]

    print(f"\n  Split-Half Test (IS data split in two)")
    print(f"    Half-1: {len(h1_c)} days ({h1_c.index[0].date()} to {h1_c.index[-1].date()})")
    print(f"    Half-2: {len(h2_c)} days ({h2_c.index[0].date()} to {h2_c.index[-1].date()})")

    r1, r2 = [], []
    for w, rebal, n in product(REG_WINDOWS, REBAL_FREQS, N_SIZES):
        res1 = run_elasticity_factor(h1_c, h1_v, w, rebal, n)
        res2 = run_elasticity_factor(h2_c, h2_v, w, rebal, n)
        r1.append(res1["sharpe"])
        r2.append(res2["sharpe"])

    corr = np.corrcoef(r1, r2)[0, 1]
    print(f"  Split-Half Stability: corr = {corr:.3f}")
    print(f"    Half-1 mean Sharpe: {np.mean(r1):.3f}")
    print(f"    Half-2 mean Sharpe: {np.mean(r2):.3f}")
    return corr


# ---------- Correlation with H-012 ----------

def correlation_with_h012(closes, volumes, best_w=20, best_rebal=5, best_n=4):
    """Compute daily return correlation with H-012 momentum factor."""
    res = run_elasticity_factor(closes, volumes, best_w, best_rebal, best_n)
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
    if len(common) < 30:
        print("\n  Not enough common data for H-012 correlation")
        return 0.0
    corr = np.corrcoef(my_rets.loc[common].values, h012_rets.loc[common].values)[0, 1]
    print(f"\n  Correlation with H-012 (momentum L60_R5_N4): {corr:.3f}")
    return corr


# ---------- Fee Sensitivity ----------

def fee_sensitivity(closes, volumes, best_w, best_rebal, best_n):
    """Test Sharpe at different fee levels."""
    print("\n  Fee Sensitivity:")
    fee_results = {}
    for fee_bps in [0, 2, 5, 10, 15]:
        fee = fee_bps / 10000.0
        res = run_elasticity_factor(closes, volumes, best_w, best_rebal, best_n,
                                     fee_rate=fee)
        fee_results[fee_bps] = res["sharpe"]
        print(f"    {fee_bps:3d} bps: Sharpe={res['sharpe']:.3f}  "
              f"Ret={res['annual_ret']*100:.1f}%")
    return fee_results


# ---------- Main ----------

if __name__ == "__main__":
    print("Loading data...")
    daily = load_daily_data()
    closes  = build_close_matrix(daily)
    volumes = build_volume_matrix(daily)

    # Align volumes to closes index
    volumes = volumes.reindex(closes.index).fillna(0)

    print(f"\nClose matrix: {closes.shape}")
    print(f"Volume matrix: {volumes.shape}")

    # 1. Full parameter scan (all data)
    df_results, results_list = run_full_scan(closes, volumes)

    # 2. IS / OOS split (60/40)
    is_df, is_oos_info = run_is_oos_split(closes, volumes)

    # 3. Walk-forward validation
    wf_df = walk_forward(closes, volumes)

    # 4. Split-half stability (on IS data)
    sh_corr = split_half_test(closes, volumes)

    # 5. Correlation with H-012
    best = df_results.loc[df_results["sharpe"].idxmax()]
    corr_012 = correlation_with_h012(
        closes, volumes,
        int(best["window"]), int(best["rebal"]), int(best["n"])
    )

    # 6. Fee sensitivity (best full-sample params)
    fee_sens = fee_sensitivity(
        closes, volumes,
        int(best["window"]), int(best["rebal"]), int(best["n"])
    )

    # ---------- Verdict ----------
    print("\n" + "=" * 72)
    print("VERDICT")
    print("=" * 72)

    pct_pos_is = is_oos_info["pct_positive_is"]
    wf_pos = int((wf_df["test_sharpe"] > 0).sum()) if len(wf_df) > 0 else 0
    wf_total = len(wf_df) if len(wf_df) > 0 else 0
    wf_mean = float(wf_df["test_sharpe"].mean()) if len(wf_df) > 0 else 0

    reject_reasons = []
    if sh_corr < -0.3:
        reject_reasons.append(f"Split-half corr={sh_corr:.3f} < -0.3")
    if wf_total > 0 and wf_pos < 2:
        reject_reasons.append(f"WF positive={wf_pos}/{wf_total} < 2")
    if abs(corr_012) > 0.6:
        reject_reasons.append(f"H-012 corr={corr_012:.3f}, |corr| > 0.6")
    if pct_pos_is < 50:
        reject_reasons.append(f"IS positive={pct_pos_is:.1f}% < 50%")

    if reject_reasons:
        verdict = "REJECTED"
        print(f"  REJECTED:")
        for r in reject_reasons:
            print(f"    - {r}")
    else:
        # Check if it's strong enough for conditional
        if (is_oos_info["oos_sharpe"] > 0.5 and wf_mean > 0.3
                and sh_corr > 0.1 and pct_pos_is >= 60):
            verdict = "CONFIRMED"
            print("  CONFIRMED -- strong factor")
        elif is_oos_info["oos_sharpe"] > 0 and wf_mean > 0:
            verdict = "CONDITIONAL"
            print("  CONDITIONAL -- passes filters but needs more evidence")
        else:
            verdict = "WEAK"
            print("  WEAK -- passes filters but metrics are marginal")

    print(f"\n  Summary:")
    print(f"    IS positive Sharpe: {pct_pos_is:.1f}%")
    print(f"    IS mean Sharpe: {is_df['sharpe'].mean():.3f}")
    print(f"    Best IS -> OOS: {is_oos_info['best_is_params']} "
          f"IS={is_oos_info['is_sharpe']:.3f} OOS={is_oos_info['oos_sharpe']:.3f}")
    print(f"    Walk-Forward: {wf_pos}/{wf_total} positive, mean OOS={wf_mean:.3f}")
    print(f"    Split-half corr: {sh_corr:.3f}")
    print(f"    H-012 corr: {corr_012:.3f}")
    print(f"    Fee sensitivity (5bps): Sharpe={fee_sens.get(5, 'N/A')}")

    # Build output
    output = {
        "hypothesis": "H-123",
        "name": "Volume-Price Elasticity Factor",
        "factor": "OLS slope of |log_return| on log(volume) over rolling window",
        "direction": "LONG high elasticity (price responds to volume), SHORT low elasticity",
        "verdict": verdict,
        "reject_reasons": reject_reasons,
        "n_assets": len(closes.columns),
        "n_days": len(closes),
        "date_range": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "fee_bps": FEE_RATE * 10000,
        "n_params": len(df_results),
        # Full-sample stats
        "full_sample": {
            "pct_positive_sharpe": float((df_results["sharpe"] > 0).mean() * 100),
            "mean_sharpe": float(df_results["sharpe"].mean()),
            "median_sharpe": float(df_results["sharpe"].median()),
            "best_params": str(best["tag"]),
            "best_sharpe": float(best["sharpe"]),
            "best_annual_ret": float(best["annual_ret"]),
            "best_max_dd": float(best["max_dd"]),
            "best_win_rate": float(best["win_rate"]),
        },
        # IS/OOS stats
        "is_oos": is_oos_info,
        # Walk-forward stats
        "walk_forward": {
            "n_folds_positive": wf_pos,
            "n_folds_total": wf_total,
            "mean_oos_sharpe": wf_mean,
            "details": wf_df.to_dict("records") if len(wf_df) > 0 else [],
        },
        # Split-half
        "split_half_corr": float(sh_corr),
        # H-012 correlation
        "corr_h012": float(corr_012),
        # Fee sensitivity
        "fee_sensitivity": fee_sens,
        # All results for reference
        "all_results": results_list,
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")

    # Print compact summary (without all_results)
    compact = {k: v for k, v in output.items() if k != "all_results"}
    print("\n" + json.dumps(compact, indent=2))
