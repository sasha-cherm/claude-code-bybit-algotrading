"""
H-119: Amihud Illiquidity Factor (Cross-Sectional)

Rank assets by Amihud illiquidity ratio: rolling_mean(|daily_return| / dollar_volume).
Assets with LOW illiquidity (highly liquid) get LONG, HIGH illiquidity (least liquid)
get SHORT. This is the crypto liquidity premium -- liquid assets attract more capital,
have lower spreads, and trend more reliably.

Dollar volume = close * volume (volume is in base asset units).

Parameter grid (48 combos):
  Lookback windows : [10, 20, 30, 60] days
  Rebalance freq   : [5, 7, 10, 14] days
  N positions each : [3, 4, 5]

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

FEE_RATE = 0.001
INITIAL_CAPITAL = 10_000.0

LOOKBACKS   = [10, 20, 30, 60]
REBAL_FREQS = [5, 7, 10, 14]
N_SIZES     = [3, 4, 5]

WF_FOLDS = 6
WF_TRAIN_DAYS = 540
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


def build_matrices(daily: dict):
    """Build aligned close, volume, and dollar_volume matrices."""
    closes = {}
    volumes = {}
    for sym, df in daily.items():
        closes[sym] = df["close"]
        volumes[sym] = df["volume"]
    close_df = pd.DataFrame(closes).dropna(how="all").ffill()
    vol_df   = pd.DataFrame(volumes).dropna(how="all").ffill().fillna(0)
    # Align indices
    common = close_df.index.intersection(vol_df.index)
    close_df = close_df.loc[common]
    vol_df   = vol_df.loc[common]
    dollar_vol_df = close_df * vol_df
    return close_df, vol_df, dollar_vol_df


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


def compute_amihud_matrix(closes: pd.DataFrame, dollar_vol: pd.DataFrame,
                           lookback: int) -> pd.DataFrame:
    """
    Rolling Amihud illiquidity ratio for each asset.
    Amihud = rolling_mean(|daily_return| / dollar_volume)
    """
    returns = closes.pct_change()
    abs_ret = returns.abs()
    # Avoid division by zero
    dv_safe = dollar_vol.replace(0, np.nan)
    ratio = abs_ret / dv_safe
    amihud = ratio.rolling(window=lookback, min_periods=max(lookback // 2, 5)).mean()
    return amihud


def run_amihud_factor(
    closes: pd.DataFrame,
    dollar_vol: pd.DataFrame,
    lookback: int,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    fee_rate: float = FEE_RATE,
    pre_computed: pd.DataFrame | None = None,
) -> dict:
    if n_short is None:
        n_short = n_long

    if pre_computed is not None:
        amihud_matrix = pre_computed
    else:
        amihud_matrix = compute_amihud_matrix(closes, dollar_vol, lookback)

    n = len(closes)
    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count = 0
    warmup = lookback + 5

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            sig = amihud_matrix.iloc[i - 1]
            valid = sig.dropna()
            # Also filter out inf
            valid = valid[np.isfinite(valid)]

            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # LONG lowest illiquidity (most liquid), SHORT highest (least liquid)
            ranked = valid.sort_values(ascending=True)  # ascending: low illiquidity first
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


def run_full_scan(closes: pd.DataFrame, dollar_vol: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-119: AMIHUD ILLIQUIDITY FACTOR -- Full Param Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per trade (Bybit taker)")
    print(f"  Strategy : LONG low illiquidity (liquid), SHORT high illiquidity")

    print("\n  Pre-computing Amihud matrices...")
    amihud_cache = {}
    for lb in LOOKBACKS:
        print(f"    Lookback {lb}d ...", end=" ", flush=True)
        amihud_cache[lb] = compute_amihud_matrix(closes, dollar_vol, lb)
        print("done")

    results = []
    n_combos = len(LOOKBACKS) * len(REBAL_FREQS) * len(N_SIZES)
    print(f"\n  Running {n_combos} param combos...")
    for lb, rebal, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        res = run_amihud_factor(closes, dollar_vol, lb, rebal, n,
                                pre_computed=amihud_cache[lb])
        tag = f"L{lb}_R{rebal}_N{n}"
        results.append({
            "tag": tag, "lookback": lb, "rebal": rebal, "n": n,
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


def walk_forward(closes, dollar_vol, n_folds=WF_FOLDS):
    """Walk-forward validation: 6 folds, train 540d, test 90d rolling."""
    print(f"\n  Walk-Forward Validation ({n_folds} folds, train={WF_TRAIN_DAYS}d, test={WF_TEST_DAYS}d)")
    n = len(closes)
    total_needed = WF_TRAIN_DAYS + WF_TEST_DAYS * n_folds
    if n < WF_TRAIN_DAYS + WF_TEST_DAYS:
        print("  Not enough data for walk-forward")
        return pd.DataFrame()

    # Calculate fold starts: space folds to cover available data
    available_for_tests = n - WF_TRAIN_DAYS
    if available_for_tests < WF_TEST_DAYS:
        print("  Not enough data for walk-forward")
        return pd.DataFrame()

    step = max(WF_TEST_DAYS, (available_for_tests - WF_TEST_DAYS) // max(n_folds - 1, 1))
    wf_results = []

    for fold in range(n_folds):
        test_start = WF_TRAIN_DAYS + fold * step
        test_end   = test_start + WF_TEST_DAYS
        if test_end > n:
            break
        train_start = max(0, test_start - WF_TRAIN_DAYS)

        train_closes = closes.iloc[train_start:test_start]
        train_dv     = dollar_vol.iloc[train_start:test_start]
        test_closes  = closes.iloc[test_start:test_end]
        test_dv      = dollar_vol.iloc[test_start:test_end]

        best_sharpe = -99
        best_p = None
        for lb, rebal, nn in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
            if len(train_closes) < lb + 30:
                continue
            res = run_amihud_factor(train_closes, train_dv, lb, rebal, nn)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_p = (lb, rebal, nn)

        if best_p is None:
            continue

        lb, rebal, nn = best_p
        test_res = run_amihud_factor(test_closes, test_dv, lb, rebal, nn)
        wf_results.append({
            "fold": fold, "train_sharpe": best_sharpe,
            "test_sharpe": test_res["sharpe"],
            "params": f"L{lb}_R{rebal}_N{nn}",
            "test_ret": test_res["annual_ret"],
            "test_dd": test_res["max_dd"],
        })
        print(f"    Fold {fold}: train Sharpe={best_sharpe:.3f} -> test Sharpe={test_res['sharpe']:.3f} ({best_p})")

    if wf_results:
        wf_df = pd.DataFrame(wf_results)
        n_pos = (wf_df["test_sharpe"] > 0).sum()
        print(f"  WF Summary: {n_pos}/{len(wf_df)} positive, mean OOS Sharpe={wf_df['test_sharpe'].mean():.3f}")
        return wf_df
    return pd.DataFrame()


def split_half_test(closes, dollar_vol):
    """Split-half stability: first half vs second half mean Sharpe correlation."""
    mid = len(closes) // 2
    h1_c = closes.iloc[:mid]
    h1_dv = dollar_vol.iloc[:mid]
    h2_c = closes.iloc[mid:]
    h2_dv = dollar_vol.iloc[mid:]

    r1, r2 = [], []
    for lb, rebal, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        res1 = run_amihud_factor(h1_c, h1_dv, lb, rebal, n)
        res2 = run_amihud_factor(h2_c, h2_dv, lb, rebal, n)
        r1.append(res1["sharpe"])
        r2.append(res2["sharpe"])

    corr = np.corrcoef(r1, r2)[0, 1]
    print(f"\n  Split-Half Stability: corr = {corr:.3f}")
    print(f"    Half-1 mean Sharpe: {np.mean(r1):.3f}")
    print(f"    Half-2 mean Sharpe: {np.mean(r2):.3f}")
    return corr, r1, r2


def correlation_with_h012(closes, dollar_vol, best_lb, best_rebal, best_n):
    """Compute daily return correlation between this strategy and H-012 (momentum L60_R5_N4)."""
    # Run H-119 with best params
    res = run_amihud_factor(closes, dollar_vol, best_lb, best_rebal, best_n)
    my_rets = res["equity"].pct_change().dropna()

    # Run H-012 proxy with L60_R5_N4
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
    print(f"\n  Correlation with H-012 (momentum L60_R5_N4): {corr:.3f}")
    return corr


if __name__ == "__main__":
    print("Loading data...")
    daily = load_daily_data()
    closes, vol_df, dollar_vol = build_matrices(daily)
    print(f"\nClose matrix: {closes.shape}")
    print(f"Dollar volume matrix: {dollar_vol.shape}")

    # 1. Full parameter scan
    df_results, results_list = run_full_scan(closes, dollar_vol)

    # 2. Walk-forward validation
    wf_df = walk_forward(closes, dollar_vol)

    # 3. Split-half stability
    sh_corr, sh_r1, sh_r2 = split_half_test(closes, dollar_vol)

    # 4. Correlation with H-012
    best = df_results.loc[df_results["sharpe"].idxmax()]
    corr_012 = correlation_with_h012(
        closes, dollar_vol,
        int(best["lookback"]), int(best["rebal"]), int(best["n"])
    )

    # Build output
    output = {
        "hypothesis": "H-119",
        "name": "Amihud Illiquidity Factor",
        "direction": "LONG low illiquidity (liquid), SHORT high illiquidity",
        "n_params": len(df_results),
        "pct_positive": round(float((df_results["sharpe"] > 0).mean() * 100), 1),
        "mean_sharpe": round(float(df_results["sharpe"].mean()), 3),
        "median_sharpe": round(float(df_results["sharpe"].median()), 3),
        "best_params": str(best["tag"]),
        "best_sharpe": float(best["sharpe"]),
        "best_annual_ret": float(best["annual_ret"]),
        "best_max_dd": float(best["max_dd"]),
        "best_win_rate": float(best["win_rate"]),
        "top5": df_results.nlargest(5, "sharpe")[
            ["tag", "sharpe", "annual_ret", "max_dd", "win_rate"]
        ].to_dict("records"),
        "wf_folds_positive": int((wf_df["test_sharpe"] > 0).sum()) if len(wf_df) > 0 else 0,
        "wf_folds_total": len(wf_df),
        "wf_mean_oos_sharpe": round(float(wf_df["test_sharpe"].mean()), 3) if len(wf_df) > 0 else 0,
        "wf_detail": wf_df.to_dict("records") if len(wf_df) > 0 else [],
        "split_half_corr": round(float(sh_corr), 3),
        "split_half_h1_mean_sharpe": round(float(np.mean(sh_r1)), 3),
        "split_half_h2_mean_sharpe": round(float(np.mean(sh_r2)), 3),
        "corr_h012": round(float(corr_012), 3),
        "all_params": results_list,
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")
    print(json.dumps({k: v for k, v in output.items() if k != "all_params" and k != "wf_detail" and k != "top5"}, indent=2))
