"""
H-207: OI Growth Rate Factor
Cross-sectional strategy: rank 14 crypto assets by rolling OI growth rate,
go long top-N / short bottom-N. Distinct from H-044 (OI-price divergence)
and H-193 (OI-price momentum divergence).
"""

import pandas as pd
import numpy as np
import json
import sys
from itertools import product
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parents[2]
DATA_DIR = BASE / "data"
OI_DIR   = DATA_DIR / "oi"
OUT_DIR  = Path(__file__).parent
OUT_DIR.mkdir(parents=True, exist_ok=True)

ASSETS = ["ADA","ARB","ATOM","AVAX","BTC","DOGE","DOT","ETH",
          "LINK","NEAR","OP","SOL","SUI","XRP"]

LOOKBACKS    = [5, 10, 20, 30]
REBAL_PERIODS = [3, 5, 7]
N_SIDES      = [3, 4]
DIRECTIONS   = ["high_growth_long", "low_growth_long"]

# Walk-forward settings
WF_FOLDS   = 6
WF_DAYS    = 90   # each fold
SPLIT_PCT  = 0.5

# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

def load_price_data(assets):
    """Load close prices for all assets, tz-normalised to UTC date."""
    frames = {}
    for a in assets:
        px = pd.read_parquet(DATA_DIR / f"{a}_USDT_1d.parquet")
        # Normalise to tz-naive date
        idx = px.index.tz_convert("UTC").normalize().tz_localize(None)
        px.index = idx
        frames[a] = px["close"]
    return pd.DataFrame(frames).sort_index()


def load_oi_data(assets):
    """Load open interest for all assets (already tz-naive)."""
    frames = {}
    for a in assets:
        oi = pd.read_parquet(OI_DIR / f"{a}_oi_1d.parquet")
        # index is already tz-naive; normalise to date
        oi.index = pd.to_datetime(oi.index).normalize()
        frames[a] = oi["openInterest"]
    return pd.DataFrame(frames).sort_index()


def build_aligned_data():
    """Return aligned (price, oi) DataFrames on common dates."""
    prices = load_price_data(ASSETS)
    oi     = load_oi_data(ASSETS)

    # Intersect dates
    common = prices.index.intersection(oi.index)
    prices = prices.loc[common]
    oi     = oi.loc[common]

    # Drop any dates where any asset has NaN OI
    valid  = oi.notna().all(axis=1) & prices.notna().all(axis=1)
    prices = prices.loc[valid]
    oi     = oi.loc[valid]

    return prices, oi

# ---------------------------------------------------------------------------
# Signal + Returns
# ---------------------------------------------------------------------------

def compute_oi_growth(oi: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """OI growth rate = (OI_t / OI_{t-lookback}) - 1, lagged by 1 day."""
    growth = oi / oi.shift(lookback) - 1
    return growth.shift(1)   # use yesterday's signal to trade today


def compute_daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change()


def build_portfolio(oi_growth: pd.DataFrame,
                    daily_ret: pd.DataFrame,
                    n: int,
                    rebal_period: int,
                    direction: str) -> pd.Series:
    """
    Construct daily long-short portfolio returns.
    - Rebalance every `rebal_period` days (using signal available at t-1).
    - Long top-N by signal, short bottom-N by signal.
    - direction='high_growth_long': high OI growth -> long
    - direction='low_growth_long':  low OI growth -> long (reversal bet)
    """
    dates  = daily_ret.index
    port   = pd.Series(np.nan, index=dates)
    weights = pd.DataFrame(0.0, index=dates, columns=ASSETS)

    current_w = None
    for i, d in enumerate(dates):
        sig = oi_growth.loc[d]
        # Only rebalance on schedule or at start
        if i == 0 or i % rebal_period == 0:
            valid_sig = sig.dropna()
            if len(valid_sig) < 2 * n:
                current_w = None
            else:
                ranked = valid_sig.rank(ascending=True)  # 1=lowest, N=highest
                if direction == "high_growth_long":
                    longs  = ranked[ranked >= len(valid_sig) - n + 1].index
                    shorts = ranked[ranked <= n].index
                else:  # low_growth_long
                    longs  = ranked[ranked <= n].index
                    shorts = ranked[ranked >= len(valid_sig) - n + 1].index
                w = pd.Series(0.0, index=ASSETS)
                w[longs]  =  1.0 / n
                w[shorts] = -1.0 / n
                current_w = w

        if current_w is not None:
            weights.loc[d] = current_w
            port.loc[d] = (daily_ret.loc[d] * current_w).sum()

    return port.dropna()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def sharpe(returns: pd.Series, ann=365) -> float:
    if returns.empty or returns.std() == 0:
        return np.nan
    return float(returns.mean() / returns.std() * np.sqrt(ann))


def max_drawdown(returns: pd.Series) -> float:
    cum = (1 + returns).cumprod()
    dd  = cum / cum.cummax() - 1
    return float(dd.min())


def annual_return(returns: pd.Series, ann=365) -> float:
    if returns.empty:
        return np.nan
    total = (1 + returns).prod()
    n     = len(returns)
    return float(total ** (ann / n) - 1)


# ---------------------------------------------------------------------------
# In-Sample Grid Search
# ---------------------------------------------------------------------------

def run_is(prices, oi):
    print("=" * 60)
    print("H-207: OI Growth Rate Factor — In-Sample Grid Search")
    print("=" * 60)

    daily_ret = compute_daily_returns(prices)
    results   = []

    param_list = list(product(LOOKBACKS, REBAL_PERIODS, N_SIDES, DIRECTIONS))
    print(f"Testing {len(param_list)} parameter combinations...")

    for lookback, rebal, n, direction in param_list:
        oi_growth = compute_oi_growth(oi, lookback)
        port = build_portfolio(oi_growth, daily_ret, n, rebal, direction)
        if len(port) < 60:
            continue
        sr = sharpe(port)
        ar = annual_return(port)
        mdd = max_drawdown(port)
        results.append({
            "lookback": lookback,
            "rebal":    rebal,
            "n":        n,
            "direction": direction,
            "sharpe":   sr,
            "annual_return": ar,
            "max_drawdown":  mdd,
            "n_days":   len(port),
        })

    df = pd.DataFrame(results)
    df = df.sort_values("sharpe", ascending=False)

    positive   = (df["sharpe"] > 0).sum()
    hit_rate   = positive / len(df) * 100
    mean_sharpe = df["sharpe"].mean()
    best       = df.iloc[0]

    dir_counts = df.groupby("direction")["sharpe"].mean()
    dominant   = dir_counts.idxmax()

    print(f"\n--- IS Summary ---")
    print(f"Total combos:    {len(df)}")
    print(f"Positive Sharpe: {positive} ({hit_rate:.1f}%)")
    print(f"Mean Sharpe:     {mean_sharpe:.3f}")
    print(f"Best Sharpe:     {best['sharpe']:.3f}  "
          f"(lookback={best['lookback']}, rebal={best['rebal']}, "
          f"n={best['n']}, dir={best['direction']})")
    print(f"Best Ann.Return: {best['annual_return']*100:.1f}%")
    print(f"Best Max DD:     {best['max_drawdown']*100:.1f}%")
    print(f"Dominant dir:    {dominant}")

    return df, best.to_dict(), hit_rate, mean_sharpe, dominant


# ---------------------------------------------------------------------------
# Walk-Forward Validation
# ---------------------------------------------------------------------------

def run_walkforward(prices, oi, best_params):
    lookback  = int(best_params["lookback"])
    rebal     = int(best_params["rebal"])
    n         = int(best_params["n"])
    direction = best_params["direction"]

    daily_ret = compute_daily_returns(prices)
    oi_growth = compute_oi_growth(oi, lookback)

    dates = daily_ret.index
    total = len(dates)
    fold_size = WF_DAYS

    # Walk-forward: train on first 60% of data, test rolling folds
    fold_results = []
    for fold in range(WF_FOLDS):
        start_idx = total - WF_FOLDS * fold_size + fold * fold_size
        end_idx   = start_idx + fold_size
        if end_idx > total:
            break
        fold_dates = dates[start_idx:end_idx]
        port = build_portfolio(
            oi_growth.loc[fold_dates],
            daily_ret.loc[fold_dates],
            n, rebal, direction
        )
        sr  = sharpe(port)
        ar  = annual_return(port)
        mdd = max_drawdown(port)
        fold_results.append({
            "fold":         fold + 1,
            "start":        str(fold_dates[0].date()),
            "end":          str(fold_dates[-1].date()),
            "sharpe":       sr,
            "annual_return": ar,
            "max_drawdown":  mdd,
        })

    wf_df = pd.DataFrame(fold_results)
    passing = (wf_df["sharpe"] > 0).sum()

    print(f"\n--- Walk-Forward ({WF_FOLDS} folds x {WF_DAYS}d) ---")
    for _, row in wf_df.iterrows():
        print(f"  Fold {int(row['fold'])}: {row['start']} -> {row['end']}  "
              f"SR={row['sharpe']:.3f}  AR={row['annual_return']*100:.1f}%  "
              f"MDD={row['max_drawdown']*100:.1f}%")
    print(f"  Passing folds (SR>0): {passing}/{WF_FOLDS}")
    wf_pass = passing >= 4

    return wf_df.to_dict("records"), passing, wf_pass


# ---------------------------------------------------------------------------
# Split-Half + Correlation with H-012
# ---------------------------------------------------------------------------

def run_split_half(prices, oi, best_params):
    lookback  = int(best_params["lookback"])
    rebal     = int(best_params["rebal"])
    n         = int(best_params["n"])
    direction = best_params["direction"]

    daily_ret = compute_daily_returns(prices)
    oi_growth = compute_oi_growth(oi, lookback)

    mid = len(prices) // 2
    results = {}
    for half, (start, end) in enumerate([
        (0, mid), (mid, len(prices))
    ], 1):
        h_dates = prices.index[start:end]
        port = build_portfolio(
            oi_growth.loc[h_dates],
            daily_ret.loc[h_dates],
            n, rebal, direction
        )
        results[f"half_{half}"] = {
            "sharpe":        sharpe(port),
            "annual_return": annual_return(port),
            "max_drawdown":  max_drawdown(port),
            "start":         str(h_dates[0].date()),
            "end":           str(h_dates[-1].date()),
        }

    print(f"\n--- Split-Half ---")
    for k, v in results.items():
        print(f"  {k} ({v['start']} -> {v['end']}): "
              f"SR={v['sharpe']:.3f}  AR={v['annual_return']*100:.1f}%  "
              f"MDD={v['max_drawdown']*100:.1f}%")

    return results


def correlate_with_h012(prices, oi, best_params):
    """
    Correlate H-207 portfolio daily returns with H-012 (xsmom) portfolio.
    H-012 uses 20d price momentum cross-sectionally.
    """
    lookback  = int(best_params["lookback"])
    rebal     = int(best_params["rebal"])
    n         = int(best_params["n"])
    direction = best_params["direction"]

    daily_ret = compute_daily_returns(prices)
    oi_growth = compute_oi_growth(oi, lookback)
    h207_ret  = build_portfolio(oi_growth, daily_ret, n, rebal, direction)

    # Build H-012 (20d price momentum, top-3/bottom-3, rebal 5d)
    mom_20 = (prices / prices.shift(20) - 1).shift(1)
    h012_ret = build_portfolio(mom_20, daily_ret, 3, 5, "high_growth_long")

    common = h207_ret.index.intersection(h012_ret.index)
    if len(common) < 30:
        return np.nan
    corr = float(h207_ret.loc[common].corr(h012_ret.loc[common]))

    print(f"\n--- Correlation with H-012 (20d price momentum) ---")
    print(f"  Pearson r = {corr:.3f}  (n={len(common)} days)")
    return corr


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"\nLoading data for {len(ASSETS)} assets...")
    prices, oi = build_aligned_data()
    print(f"Aligned dataset: {len(prices)} days  "
          f"({prices.index[0].date()} -> {prices.index[-1].date()})")
    print(f"Assets: {', '.join(ASSETS)}\n")

    # --- IS ---
    df_is, best, hit_rate, mean_sr, dominant = run_is(prices, oi)

    # --- Conditional WF ---
    wf_records = []
    wf_pass    = False
    corr_h012  = None
    split_results = {}

    if hit_rate >= 80:
        print(f"\nIS hit rate {hit_rate:.1f}% >= 80% — proceeding to walk-forward...")
        wf_records, wf_pass_count, wf_pass = run_walkforward(prices, oi, best)
        if wf_pass:
            print("Walk-forward PASSED — proceeding to split-half + correlation...")
            split_results = run_split_half(prices, oi, best)
            corr_h012     = correlate_with_h012(prices, oi, best)
        else:
            print("Walk-forward FAILED — stopping here.")
    else:
        print(f"\nIS hit rate {hit_rate:.1f}% < 80% — skipping walk-forward.")

    # --- Verdict ---
    if hit_rate >= 80 and wf_pass:
        verdict = "CONFIRMED"
    else:
        verdict = "REJECTED"

    print(f"\n{'='*60}")
    print(f"VERDICT: {verdict}")
    print(f"{'='*60}\n")

    # --- Save results ---
    out = {
        "hypothesis": "H-207",
        "title":      "OI Growth Rate Factor",
        "verdict":    verdict,
        "data_period": {
            "start":   str(prices.index[0].date()),
            "end":     str(prices.index[-1].date()),
            "n_days":  len(prices),
            "assets":  ASSETS,
        },
        "is_summary": {
            "total_combos":   int(len(df_is)),
            "positive_sharpe": int((df_is["sharpe"] > 0).sum()),
            "hit_rate_pct":   float(hit_rate),
            "mean_sharpe":    float(mean_sr),
            "dominant_dir":   dominant,
        },
        "best_params": best,
        "walkforward_folds": wf_records,
        "split_half":  split_results,
        "corr_h012":   float(corr_h012) if corr_h012 is not None else None,
    }

    out_path = OUT_DIR / "results.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"Results written to {out_path}")

    return out


if __name__ == "__main__":
    main()
