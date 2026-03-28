"""
H-113: Funding-Adjusted Momentum (Cross-Sectional)

Rank by (N-day price return) - (cumulative N-day funding cost).
A long perp position PAYS funding when rate > 0, so high-funding assets
have an implicit carry drag. This penalises momentum driven by crowded trades.

Strategy: Long top N (best carry-adjusted momentum), Short bottom N.
Market-neutral (dollar-neutral), equal-weighted.

Differs from H-012 (raw momentum) by subtracting funding cost.
Differs from H-053 (funding XS contrarian) by combining with price momentum.

Parameter grid (48 combos):
  Lookback windows : [30, 40, 60, 90] days
  Rebalance freq   : [5, 7, 10, 14] days
  N positions each : [3, 4, 5]

Validation:
  - Full param scan: % positive Sharpe (target: >80%)
  - 6-fold rolling walk-forward (60% train / 40% test)
  - Split-half stability
  - Correlation with H-012 (momentum) and H-053 (funding XS)
  - Fee sensitivity: 0.1% round-trip (Bybit taker)

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

LOOKBACKS   = [30, 40, 60, 90]
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


def load_funding_data():
    """Load 8-hourly funding rates and resample to daily sum."""
    data_dir = ROOT / "data"
    funding_daily = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_USDT_funding.parquet"
        if not path.exists():
            # Try alternate naming
            safe2 = safe.replace("/", "_")
            path = data_dir / f"{safe2}_funding.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            # Resample 8h funding to daily sum (3 settlements per day)
            daily_sum = df["funding_rate"].resample("1D").sum()
            funding_daily[sym] = daily_sum
            print(f"  {sym} funding: {len(daily_sum)} daily bars")
        else:
            print(f"  {sym}: no funding data at {path}")
    return funding_daily


def build_close_matrix(daily: dict) -> pd.DataFrame:
    closes = {}
    for sym, df in daily.items():
        closes[sym] = df["close"]
    df_closes = pd.DataFrame(closes).dropna(how="all").ffill()
    return df_closes


def build_funding_matrix(funding_daily: dict, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Build funding rate matrix aligned with close matrix index."""
    funding = {}
    for sym, series in funding_daily.items():
        funding[sym] = series
    df_funding = pd.DataFrame(funding)
    df_funding = df_funding.reindex(index).fillna(0.0)
    return df_funding


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


def run_funding_adj_momentum(
    closes: pd.DataFrame,
    funding_matrix: pd.DataFrame,
    lookback: int,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    fee_rate: float = FEE_RATE,
) -> dict:
    """
    Signal: rolling N-day return - cumulative N-day funding rate.
    LONG top (best carry-adjusted momentum), SHORT bottom.
    """
    if n_short is None:
        n_short = n_long

    returns = closes.pct_change()
    # Rolling N-day price return
    roll_ret = closes.pct_change(lookback)
    # Rolling N-day cumulative funding
    roll_funding = funding_matrix.rolling(lookback).sum()

    # Carry-adjusted momentum = price return - funding cost for long position
    # (Funding cost for a long perp: you PAY when funding > 0)
    signal = roll_ret - roll_funding

    n = len(closes)
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count = 0
    warmup = lookback + 5

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            sig = signal.iloc[i - 1]
            valid = sig.dropna()

            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

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


def run_full_scan(closes: pd.DataFrame, funding_matrix: pd.DataFrame):
    print("\n" + "=" * 72)
    print("H-113: FUNDING-ADJUSTED MOMENTUM -- Full Param Scan")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per trade (Bybit taker)")
    print(f"  Strategy : LONG best carry-adjusted mom, SHORT worst")

    results = []
    print(f"\n  Running {len(LOOKBACKS) * len(REBAL_FREQS) * len(N_SIZES)} param combos...")
    for lb, rebal, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        res = run_funding_adj_momentum(closes, funding_matrix, lb, rebal, n)
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

    # Top 5
    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']:20s}  Sharpe={row['sharpe']:.3f}  "
              f"Ret={row['annual_ret']*100:.1f}%  DD={row['max_dd']*100:.1f}%  "
              f"WR={row['win_rate']*100:.1f}%")

    return df, results


def walk_forward(closes, funding_matrix, best_params, n_folds=WF_FOLDS):
    print(f"\n  Walk-Forward Validation ({n_folds} folds, 60/40 split)")
    n = len(closes)
    fold_size = n // n_folds
    wf_results = []

    for fold in range(n_folds):
        test_start = fold * fold_size
        test_end   = test_start + fold_size
        train_end  = test_start
        if train_end < 120:
            continue

        train_closes  = closes.iloc[:train_end]
        train_funding = funding_matrix.iloc[:train_end]
        test_closes   = closes.iloc[test_start:test_end]
        test_funding  = funding_matrix.iloc[test_start:test_end]

        # Find best on train
        best_sharpe = -99
        best_p = None
        for lb, rebal, nn in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
            if len(train_closes) < lb + 30:
                continue
            res = run_funding_adj_momentum(train_closes, train_funding, lb, rebal, nn)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_p = (lb, rebal, nn)

        if best_p is None:
            continue

        # Run on test
        lb, rebal, nn = best_p
        test_res = run_funding_adj_momentum(test_closes, test_funding, lb, rebal, nn)
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
        mean_oos = wf_df["test_sharpe"].mean()
        print(f"  WF Summary: {n_pos}/{len(wf_df)} positive, mean OOS Sharpe={mean_oos:.3f}")
        return wf_df
    return pd.DataFrame()


def split_half_test(closes, funding_matrix):
    mid = len(closes) // 2
    h1_closes = closes.iloc[:mid]
    h1_funding = funding_matrix.iloc[:mid]
    h2_closes = closes.iloc[mid:]
    h2_funding = funding_matrix.iloc[mid:]

    results_h1 = []
    results_h2 = []
    for lb, rebal, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        r1 = run_funding_adj_momentum(h1_closes, h1_funding, lb, rebal, n)
        r2 = run_funding_adj_momentum(h2_closes, h2_funding, lb, rebal, n)
        results_h1.append(r1["sharpe"])
        results_h2.append(r2["sharpe"])

    corr = np.corrcoef(results_h1, results_h2)[0, 1]
    print(f"\n  Split-Half Stability: corr = {corr:.3f}")
    print(f"    Half-1 mean Sharpe: {np.mean(results_h1):.3f}")
    print(f"    Half-2 mean Sharpe: {np.mean(results_h2):.3f}")
    return corr


def correlation_with_existing(closes, funding_matrix, best_lb=60, best_rebal=5, best_n=4):
    """Compute correlation of daily returns with H-012 and H-053."""
    # This strategy
    res = run_funding_adj_momentum(closes, funding_matrix, best_lb, best_rebal, best_n)
    eq = res["equity"]
    my_rets = eq.pct_change().dropna()

    # H-012: raw momentum
    roll_ret = closes.pct_change(best_lb)
    h012_eq = np.zeros(len(closes))
    h012_eq[0] = 10000
    prev_w = pd.Series(0.0, index=closes.columns)
    warmup = best_lb + 5
    for i in range(1, len(closes)):
        pt = closes.iloc[i]
        py = closes.iloc[i-1]
        lr = np.log(pt / py)
        if i >= warmup and (i - warmup) % best_rebal == 0:
            sig = roll_ret.iloc[i-1].dropna()
            if len(sig) >= best_n * 2:
                ranked = sig.sort_values(ascending=False)
                new_w = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:best_n]:
                    new_w[s] = 1.0/best_n
                for s in ranked.index[-best_n:]:
                    new_w[s] = -1.0/best_n
                prev_w = new_w
        h012_eq[i] = h012_eq[i-1] * np.exp((prev_w * lr).sum())
    h012_rets = pd.Series(h012_eq, index=closes.index).pct_change().dropna()

    # H-053: funding XS (contrarian)
    roll_fund = funding_matrix.rolling(3).mean()
    h053_eq = np.zeros(len(closes))
    h053_eq[0] = 10000
    prev_w2 = pd.Series(0.0, index=closes.columns)
    for i in range(1, len(closes)):
        pt = closes.iloc[i]
        py = closes.iloc[i-1]
        lr = np.log(pt / py)
        if i >= 10 and (i - 10) % 10 == 0:
            sig = roll_fund.iloc[i-1].dropna()
            if len(sig) >= 8:
                ranked = sig.sort_values(ascending=True)
                new_w = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:4]:
                    new_w[s] = 1.0/4
                for s in ranked.index[-4:]:
                    new_w[s] = -1.0/4
                prev_w2 = new_w
        h053_eq[i] = h053_eq[i-1] * np.exp((prev_w2 * lr).sum())
    h053_rets = pd.Series(h053_eq, index=closes.index).pct_change().dropna()

    common = my_rets.index.intersection(h012_rets.index).intersection(h053_rets.index)
    corr_012 = np.corrcoef(my_rets.loc[common].values, h012_rets.loc[common].values)[0,1]
    corr_053 = np.corrcoef(my_rets.loc[common].values, h053_rets.loc[common].values)[0,1]
    print(f"\n  Correlation with H-012 (momentum): {corr_012:.3f}")
    print(f"  Correlation with H-053 (funding XS): {corr_053:.3f}")
    return corr_012, corr_053


if __name__ == "__main__":
    print("Loading data...")
    daily = load_daily_data()
    funding_daily = load_funding_data()

    closes = build_close_matrix(daily)
    funding_matrix = build_funding_matrix(funding_daily, closes.index)
    print(f"\nClose matrix: {closes.shape} | Funding matrix: {funding_matrix.shape}")

    df_results, results_list = run_full_scan(closes, funding_matrix)

    # Walk-forward
    best_row = df_results.loc[df_results["sharpe"].idxmax()]
    wf_df = walk_forward(closes, funding_matrix,
                         (int(best_row["lookback"]), int(best_row["rebal"]), int(best_row["n"])))

    # Split-half
    sh_corr = split_half_test(closes, funding_matrix)

    # Correlation with existing
    best = df_results.loc[df_results["sharpe"].idxmax()]
    corr_012, corr_053 = correlation_with_existing(
        closes, funding_matrix, int(best["lookback"]), int(best["rebal"]), int(best["n"]))

    # Save results
    output = {
        "hypothesis": "H-113",
        "name": "Funding-Adjusted Momentum",
        "n_params": len(df_results),
        "pct_positive": float((df_results["sharpe"] > 0).mean() * 100),
        "mean_sharpe": float(df_results["sharpe"].mean()),
        "best_params": str(best_row["tag"]),
        "best_sharpe": float(best_row["sharpe"]),
        "best_annual_ret": float(best_row["annual_ret"]),
        "best_max_dd": float(best_row["max_dd"]),
        "wf_folds_positive": int((wf_df["test_sharpe"] > 0).sum()) if len(wf_df) > 0 else 0,
        "wf_folds_total": len(wf_df),
        "wf_mean_oos_sharpe": float(wf_df["test_sharpe"].mean()) if len(wf_df) > 0 else 0,
        "split_half_corr": float(sh_corr),
        "corr_h012": float(corr_012),
        "corr_h053": float(corr_053),
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")
    print(json.dumps(output, indent=2))
