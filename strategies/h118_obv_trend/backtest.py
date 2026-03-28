"""
H-118: Volume-Price Confirmation (OBV Trend) Factor (Cross-Sectional)

Rank assets by On-Balance Volume (OBV) trend strength.
When volume confirms price direction (OBV trending with price), the move is
sustainable. When volume diverges (OBV flat/declining while price rises),
the move is fragile.

Signal: Rolling correlation between cumulative OBV and price over lookback window.
High correlation = volume confirms price (LONG).
Low/negative correlation = volume diverges from price (SHORT).

This is fundamentally different from:
- H-012 (momentum): uses only price, ignores volume
- H-021 (volume momentum): uses volume level change, ignores price-volume relationship
- H-094 (volume asymmetry, rejected): measured up/down volume ratio
- H-111 (vol imbalance, rejected): measured buy/sell volume balance

OBV trend captures the *coherence* between price and volume, not either signal alone.

Parameter grid (48 combos):
  Lookback windows : [20, 30, 40, 60] days
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

LOOKBACKS   = [20, 30, 40, 60]
REBAL_FREQS = [5, 7, 10, 14]
N_SIZES     = [3, 4, 5]

WF_FOLDS = 6


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
    return pd.DataFrame(volumes).dropna(how="all").ffill().fillna(0)


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


def compute_obv(closes: pd.DataFrame, volumes: pd.DataFrame) -> pd.DataFrame:
    """Compute On-Balance Volume for each asset."""
    price_change = closes.diff()
    sign = np.sign(price_change)
    # OBV: cumulative sum of signed volume
    signed_vol = volumes * sign
    obv = signed_vol.cumsum()
    return obv


def compute_obv_price_corr_matrix(
    closes: pd.DataFrame, obv: pd.DataFrame, lookback: int
) -> pd.DataFrame:
    """
    Rolling correlation between OBV and price over lookback window.
    High corr = volume confirms price direction.
    """
    n_days = len(closes)
    n_assets = len(closes.columns)
    corr_vals = np.full((n_days, n_assets), np.nan)

    close_arr = closes.values
    obv_arr = obv.values

    for i in range(lookback, n_days):
        for j in range(n_assets):
            p_window = close_arr[i - lookback:i, j]
            o_window = obv_arr[i - lookback:i, j]

            p_valid = ~np.isnan(p_window)
            o_valid = ~np.isnan(o_window)
            both_valid = p_valid & o_valid

            if both_valid.sum() < 10:
                continue

            p = p_window[both_valid]
            o = o_window[both_valid]

            if np.std(p) < 1e-12 or np.std(o) < 1e-12:
                corr_vals[i, j] = 0.0
                continue

            corr_vals[i, j] = np.corrcoef(p, o)[0, 1]

    return pd.DataFrame(corr_vals, index=closes.index, columns=closes.columns)


def run_obv_trend_factor(
    closes: pd.DataFrame,
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
        corr_matrix = pre_computed
    else:
        raise ValueError("Must provide pre_computed corr matrix")

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
            sig = corr_matrix.iloc[i - 1]
            valid = sig.dropna()

            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            # Long highest OBV-price corr (volume confirms), short lowest
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


def run_full_scan(closes: pd.DataFrame, volumes: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-118: VOLUME-PRICE CONFIRMATION (OBV TREND) FACTOR -- Full Param Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per trade (Bybit taker)")
    print(f"  Strategy : LONG high OBV-price corr (confirmed), SHORT low (divergent)")

    print("\n  Computing OBV...")
    obv = compute_obv(closes, volumes)

    print("  Pre-computing OBV-price correlation matrices...")
    corr_cache = {}
    for lb in LOOKBACKS:
        print(f"    Lookback {lb}d ...", end=" ", flush=True)
        corr_cache[lb] = compute_obv_price_corr_matrix(closes, obv, lb)
        print("done")

    results = []
    print(f"\n  Running {len(LOOKBACKS) * len(REBAL_FREQS) * len(N_SIZES)} param combos...")
    for lb, rebal, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        res = run_obv_trend_factor(closes, lb, rebal, n, pre_computed=corr_cache[lb])
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

    return df, results, obv, corr_cache


def walk_forward(closes, volumes, n_folds=WF_FOLDS):
    print(f"\n  Walk-Forward Validation ({n_folds} folds)")
    n = len(closes)
    fold_size = n // n_folds
    wf_results = []

    for fold in range(n_folds):
        test_start = fold * fold_size
        test_end   = test_start + fold_size
        train_end  = test_start
        if train_end < 80:
            continue

        train_closes = closes.iloc[:train_end]
        train_vols   = volumes.iloc[:train_end]
        test_closes  = closes.iloc[test_start:test_end]
        test_vols    = volumes.iloc[test_start:test_end]

        train_obv = compute_obv(train_closes, train_vols)
        test_obv  = compute_obv(test_closes, test_vols)

        best_sharpe = -99
        best_p = None
        for lb, rebal, nn in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
            if len(train_closes) < lb + 30:
                continue
            corr_mat = compute_obv_price_corr_matrix(train_closes, train_obv, lb)
            res = run_obv_trend_factor(train_closes, lb, rebal, nn, pre_computed=corr_mat)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_p = (lb, rebal, nn)

        if best_p is None:
            continue

        lb, rebal, nn = best_p
        test_corr_mat = compute_obv_price_corr_matrix(test_closes, test_obv, lb)
        test_res = run_obv_trend_factor(test_closes, lb, rebal, nn, pre_computed=test_corr_mat)
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


def split_half_test(closes, volumes):
    mid = len(closes) // 2
    h1_c = closes.iloc[:mid]
    h2_c = closes.iloc[mid:]
    h1_v = volumes.iloc[:mid]
    h2_v = volumes.iloc[mid:]

    h1_obv = compute_obv(h1_c, h1_v)
    h2_obv = compute_obv(h2_c, h2_v)

    r1, r2 = [], []
    for lb, rebal, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        corr1 = compute_obv_price_corr_matrix(h1_c, h1_obv, lb)
        corr2 = compute_obv_price_corr_matrix(h2_c, h2_obv, lb)
        res1 = run_obv_trend_factor(h1_c, lb, rebal, n, pre_computed=corr1)
        res2 = run_obv_trend_factor(h2_c, lb, rebal, n, pre_computed=corr2)
        r1.append(res1["sharpe"])
        r2.append(res2["sharpe"])

    corr = np.corrcoef(r1, r2)[0, 1]
    print(f"\n  Split-Half Stability: corr = {corr:.3f}")
    print(f"    Half-1 mean Sharpe: {np.mean(r1):.3f}")
    print(f"    Half-2 mean Sharpe: {np.mean(r2):.3f}")
    return corr


def correlation_with_h012(closes, volumes, obv, corr_cache, best_lb=30, best_rebal=5, best_n=4):
    corr_mat = corr_cache[best_lb]
    res = run_obv_trend_factor(closes, best_lb, best_rebal, best_n, pre_computed=corr_mat)
    my_rets = res["equity"].pct_change().dropna()

    roll_ret = closes.pct_change(60)
    h012_eq = np.zeros(len(closes))
    h012_eq[0] = 10000
    prev_w = pd.Series(0.0, index=closes.columns)
    warmup = 65
    for i in range(1, len(closes)):
        pt = closes.iloc[i]
        py = closes.iloc[i-1]
        lr = np.log(pt / py)
        if i >= warmup and (i - warmup) % 5 == 0:
            sig = roll_ret.iloc[i-1].dropna()
            if len(sig) >= 8:
                ranked = sig.sort_values(ascending=False)
                new_w = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:4]:
                    new_w[s] = 1.0/4
                for s in ranked.index[-4:]:
                    new_w[s] = -1.0/4
                prev_w = new_w
        h012_eq[i] = h012_eq[i-1] * np.exp((prev_w * lr).sum())
    h012_rets = pd.Series(h012_eq, index=closes.index).pct_change().dropna()

    common = my_rets.index.intersection(h012_rets.index)
    corr = np.corrcoef(my_rets.loc[common].values, h012_rets.loc[common].values)[0, 1]
    print(f"\n  Correlation with H-012 (momentum): {corr:.3f}")
    return corr


if __name__ == "__main__":
    print("Loading data...")
    daily = load_daily_data()
    closes = build_close_matrix(daily)
    volumes = build_volume_matrix(daily)
    # Align
    common_idx = closes.index.intersection(volumes.index)
    closes = closes.loc[common_idx]
    volumes = volumes.loc[common_idx]
    print(f"\nClose matrix: {closes.shape}, Volume matrix: {volumes.shape}")

    df_results, results_list, obv, corr_cache = run_full_scan(closes, volumes)
    wf_df = walk_forward(closes, volumes)
    sh_corr = split_half_test(closes, volumes)
    best = df_results.loc[df_results["sharpe"].idxmax()]
    corr_012 = correlation_with_h012(closes, volumes, obv, corr_cache,
                                      int(best["lookback"]), int(best["rebal"]), int(best["n"]))

    output = {
        "hypothesis": "H-118",
        "name": "Volume-Price Confirmation (OBV Trend) Factor",
        "n_params": len(df_results),
        "pct_positive": float((df_results["sharpe"] > 0).mean() * 100),
        "mean_sharpe": float(df_results["sharpe"].mean()),
        "best_params": str(best["tag"]),
        "best_sharpe": float(best["sharpe"]),
        "best_annual_ret": float(best["annual_ret"]),
        "best_max_dd": float(best["max_dd"]),
        "wf_folds_positive": int((wf_df["test_sharpe"] > 0).sum()) if len(wf_df) > 0 else 0,
        "wf_folds_total": len(wf_df),
        "wf_mean_oos_sharpe": float(wf_df["test_sharpe"].mean()) if len(wf_df) > 0 else 0,
        "split_half_corr": float(sh_corr),
        "corr_h012": float(corr_012),
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")
    print(json.dumps(output, indent=2))
