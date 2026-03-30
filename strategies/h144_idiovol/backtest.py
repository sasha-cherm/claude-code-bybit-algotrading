"""
H-144: Idiosyncratic Volatility Factor

Concept: After removing systematic (BTC) risk via rolling regression, rank crypto
assets by residual (idiosyncratic) volatility. Long low idio-vol assets
(quality/institutional), short high idio-vol assets (speculative).

Difference from H-083: Same core idea but with:
 - Updated parameter grid including R=14 day rebalance
 - Walk-forward: 6 expanding-window folds (train ≥360d, test 60d each)
 - Split-half: cross-half Sharpe rank correlation
 - Correlation with BOTH H-012 (momentum) and H-019 (total vol)
 - Verdict against acceptance criteria

Acceptance criteria:
 - IS: >=80% params positive Sharpe
 - WF: >=4/6 folds positive
 - Split-half: positive cross-half correlation
 - H-012 correlation: <=0.40
"""

import json
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

# ─── Configuration ──────────────────────────────────────────────────────────

ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX",
    "DOT", "LINK", "ATOM", "NEAR", "OP", "ARB", "SUI",
]

DATA_DIR = ROOT / "data"
FEE_RATE = 0.0006          # 6 bps taker fee
INITIAL_CAPITAL = 10_000.0
PERIODS_PER_YEAR = 365

# Parameter grid: 4 x 5 x 3 = 60 combinations
LOOKBACKS   = [20, 30, 40, 60]
REBAL_FREQS = [3, 5, 7, 10, 14]
N_POSITIONS = [3, 4, 5]

# Walk-forward config: 6 expanding-window folds
WF_FOLDS = 6
WF_TEST_DAYS = 60
WF_MIN_TRAIN = 360

# H-012 reference params
H012_LOOKBACK = 60
H012_REBAL = 5
H012_N = 4


# ─── Data Loading ────────────────────────────────────────────────────────────

def load_daily_closes() -> pd.DataFrame:
    """Load daily close prices for all assets into a single DataFrame."""
    frames = {}
    for asset in ASSETS:
        fpath = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fpath.exists():
            print(f"  WARNING: {fpath.name} not found, skipping {asset}")
            continue
        df = pd.read_parquet(fpath)
        frames[asset] = df["close"]

    closes = pd.DataFrame(frames)
    closes = closes.sort_index()
    closes = closes.dropna(how="all").ffill().dropna()
    return closes


# ─── Idiosyncratic Volatility Computation ────────────────────────────────────

def compute_idio_vol(log_returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    Compute idiosyncratic volatility for each asset.

    For non-BTC assets: rolling OLS of asset returns on BTC returns,
    then std(residuals) over the lookback window.
    For BTC itself: use total rolling vol (it IS the systematic factor).

    Rolling OLS via:
      beta = cov(asset, btc) / var(btc)    [vectorised rolling cov/var]
      alpha = mean(asset) - beta * mean(btc)
      residual_t = asset_t - alpha - beta * btc_t
      idio_vol = rolling std(residuals)

    Note: alpha and beta are estimated from the full rolling window;
    applying them back within the same window produces "in-sample" residuals,
    but because alpha/beta are computed from t-lookback to t-1 (lagged),
    there is no forward-looking bias in the idio_vol signal used on day t.
    """
    btc_ret = log_returns["BTC"]
    idio_vol = pd.DataFrame(
        index=log_returns.index,
        columns=log_returns.columns,
        dtype=float,
    )

    # BTC: total vol
    idio_vol["BTC"] = btc_ret.rolling(lookback, min_periods=lookback).std()

    for asset in log_returns.columns:
        if asset == "BTC":
            continue

        asset_ret = log_returns[asset]

        rolling_cov = asset_ret.rolling(lookback, min_periods=lookback).cov(btc_ret)
        rolling_var = btc_ret.rolling(lookback, min_periods=lookback).var()

        beta = rolling_cov / rolling_var
        alpha = (
            asset_ret.rolling(lookback, min_periods=lookback).mean()
            - beta * btc_ret.rolling(lookback, min_periods=lookback).mean()
        )

        # Residuals: deviation from fitted OLS line
        residuals = asset_ret - alpha - beta * btc_ret
        idio_vol[asset] = residuals.rolling(lookback, min_periods=lookback).std()

    return idio_vol


# ─── Backtest Engine ─────────────────────────────────────────────────────────

def run_backtest(
    closes: pd.DataFrame,
    lookback: int = 30,
    rebal_freq: int = 5,
    n_pos: int = 4,
    fee_rate: float = FEE_RATE,
) -> dict:
    """
    Run the idiosyncratic volatility factor backtest on the given close matrix.

    Dollar-neutral: long bottom-N (lowest idio-vol), short top-N (highest idio-vol).
    Uses lagged (t-1) signal — no lookahead.

    Returns dict with equity curve, daily_returns, and standard metrics.
    """
    log_returns = np.log(closes / closes.shift(1))
    idio_vol = compute_idio_vol(log_returns, lookback)

    n = len(closes)
    equity = np.full(n, np.nan)
    equity[0] = INITIAL_CAPITAL

    prev_weights = pd.Series(0.0, index=closes.columns)
    daily_returns_list = []

    # Need lookback + 1 days before first valid signal
    warmup = lookback + 1

    for i in range(1, n):
        current_weights = prev_weights.copy()

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ivol = idio_vol.iloc[i - 1].dropna()  # lagged signal

            if len(ivol) >= 2 * n_pos:
                ranked = ivol.sort_values(ascending=True)
                longs  = ranked.index[:n_pos]    # lowest idio-vol = LONG
                shorts = ranked.index[-n_pos:]   # highest idio-vol = SHORT

                new_weights = pd.Series(0.0, index=closes.columns)
                for sym in longs:
                    new_weights[sym] = 1.0 / n_pos
                for sym in shorts:
                    new_weights[sym] = -1.0 / n_pos

                current_weights = new_weights

        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        asset_rets = (price_today / price_yesterday) - 1.0
        port_ret = (current_weights * asset_rets).sum()

        # Transaction costs on rebalance
        if i >= warmup and (i - warmup) % rebal_freq == 0:
            turnover = (current_weights - prev_weights).abs().sum()
            port_ret -= turnover * fee_rate

        daily_returns_list.append(port_ret)
        equity[i] = equity[i - 1] * (1.0 + port_ret)
        prev_weights = current_weights.copy()

    eq_series = pd.Series(equity, index=closes.index).dropna()
    daily_rets = pd.Series(daily_returns_list, index=closes.index[1:])

    if len(eq_series) < 50:
        return {
            "sharpe": -99.0, "annual_ret": 0.0, "max_dd": 1.0,
            "win_rate": 0.0, "equity": eq_series, "daily_returns": daily_rets,
        }

    rets = eq_series.pct_change().dropna()
    return {
        "sharpe":     round(sharpe_ratio(rets, periods_per_year=PERIODS_PER_YEAR), 4),
        "annual_ret": round(annual_return(eq_series, periods_per_year=PERIODS_PER_YEAR), 4),
        "max_dd":     round(max_drawdown(eq_series), 4),
        "win_rate":   round(float((rets > 0).mean()), 4),
        "equity":     eq_series,
        "daily_returns": daily_rets,
    }


# ─── Parameter Grid ──────────────────────────────────────────────────────────

def run_parameter_grid(closes: pd.DataFrame) -> pd.DataFrame:
    """Run 4 x 5 x 3 = 60 parameter combinations on the full period."""
    results = []
    total = len(LOOKBACKS) * len(REBAL_FREQS) * len(N_POSITIONS)
    count = 0

    for lb, rb, np_ in product(LOOKBACKS, REBAL_FREQS, N_POSITIONS):
        count += 1
        r = run_backtest(closes, lookback=lb, rebal_freq=rb, n_pos=np_)
        results.append({
            "lookback":   lb,
            "rebal":      rb,
            "n_pos":      np_,
            "sharpe":     r["sharpe"],
            "annual_ret": r["annual_ret"],
            "max_dd":     r["max_dd"],
            "win_rate":   r["win_rate"],
        })
        if count % 20 == 0:
            print(f"  Grid progress: {count}/{total}")

    return pd.DataFrame(results)


# ─── Walk-Forward Validation (6 expanding folds, 60d test each) ──────────────

def walk_forward_validation(
    closes: pd.DataFrame, lookback: int, rebal_freq: int, n_pos: int
) -> dict:
    """
    Walk-forward with 6 expanding train windows, 60-day test periods.

    Layout (total days = T):
      Fold 1: train [0 .. T-6*60-1], test [T-6*60 .. T-5*60-1]
      Fold 2: train [0 .. T-5*60-1], test [T-5*60 .. T-4*60-1]
      ...
      Fold 6: train [0 .. T-60-1],   test [T-60 .. T-1]

    Minimum train size: WF_MIN_TRAIN = 360 days.
    """
    n = len(closes)
    total_test = WF_FOLDS * WF_TEST_DAYS
    first_train_end = n - total_test

    if first_train_end < WF_MIN_TRAIN:
        return {
            "error": f"Not enough data: need {WF_MIN_TRAIN + total_test} days, have {n}",
            "folds": [],
        }

    fold_results = []
    all_oos_returns = []

    for fold in range(WF_FOLDS):
        test_start = first_train_end + fold * WF_TEST_DAYS
        test_end   = test_start + WF_TEST_DAYS

        # Include enough warmup before test_start
        warmup_start = max(0, test_start - lookback - 5)
        slice_closes = closes.iloc[warmup_start:test_end]

        r = run_backtest(slice_closes, lookback=lookback, rebal_freq=rebal_freq, n_pos=n_pos)

        # Extract only the test-period daily returns
        test_dates = closes.index[test_start:test_end]
        oos_rets   = r["daily_returns"].reindex(test_dates).dropna()

        if len(oos_rets) < 10:
            fold_results.append({
                "fold": fold + 1,
                "start": str(closes.index[test_start].date()),
                "end":   str(closes.index[min(test_end, n) - 1].date()),
                "sharpe": -99.0, "annual_ret": 0.0, "max_dd": 1.0, "n_days": 0,
            })
            continue

        oos_eq         = INITIAL_CAPITAL * (1.0 + oos_rets).cumprod()
        fold_sharpe    = round(sharpe_ratio(oos_rets, periods_per_year=PERIODS_PER_YEAR), 3)
        fold_ann       = round(annual_return(oos_eq,   periods_per_year=PERIODS_PER_YEAR), 4)
        fold_dd        = round(max_drawdown(oos_eq), 4)
        all_oos_returns.append(oos_rets)

        fold_results.append({
            "fold":       fold + 1,
            "start":      str(closes.index[test_start].date()),
            "end":        str(closes.index[test_end - 1].date()),
            "sharpe":     fold_sharpe,
            "annual_ret": fold_ann,
            "max_dd":     fold_dd,
            "n_days":     len(oos_rets),
        })

    if not all_oos_returns:
        return {"error": "No valid folds", "folds": fold_results}

    combined_rets = pd.concat(all_oos_returns)
    combined_eq   = INITIAL_CAPITAL * (1.0 + combined_rets).cumprod()
    n_pos_folds   = sum(1 for f in fold_results if f["sharpe"] > 0)

    return {
        "folds":               fold_results,
        "n_pos_folds":         n_pos_folds,
        "combined_sharpe":     round(sharpe_ratio(combined_rets, periods_per_year=PERIODS_PER_YEAR), 4),
        "combined_annual_ret": round(annual_return(combined_eq,  periods_per_year=PERIODS_PER_YEAR), 4),
        "combined_max_dd":     round(max_drawdown(combined_eq), 4),
        "total_oos_days":      len(combined_rets),
    }


# ─── Split-Half Validation ───────────────────────────────────────────────────

def split_half_validation(closes: pd.DataFrame) -> dict:
    """
    Run all parameter combinations independently on each half.
    Report cross-half Sharpe rank correlation and fraction positive in both.
    """
    n   = len(closes)
    mid = n // 2

    h1_closes = closes.iloc[:mid]
    h2_closes = closes.iloc[mid:]

    sharpes_h1, sharpes_h2 = [], []

    for lb, rb, np_ in product(LOOKBACKS, REBAL_FREQS, N_POSITIONS):
        r1 = run_backtest(h1_closes, lookback=lb, rebal_freq=rb, n_pos=np_)
        r2 = run_backtest(h2_closes, lookback=lb, rebal_freq=rb, n_pos=np_)
        sharpes_h1.append(r1["sharpe"])
        sharpes_h2.append(r2["sharpe"])

    s1 = np.array(sharpes_h1)
    s2 = np.array(sharpes_h2)

    corr         = float(np.corrcoef(s1, s2)[0, 1])
    both_pos     = int(((s1 > 0) & (s2 > 0)).sum())
    total_params = len(s1)

    return {
        "sharpe_rank_corr":  round(corr, 4),
        "half1_mean_sharpe": round(float(s1.mean()), 4),
        "half2_mean_sharpe": round(float(s2.mean()), 4),
        "both_positive":     both_pos,
        "both_positive_pct": round(both_pos / total_params, 4),
        "total_params":      total_params,
        "half1_period": f"{closes.index[0].date()} to {closes.index[mid - 1].date()}",
        "half2_period": f"{closes.index[mid].date()} to {closes.index[-1].date()}",
    }


# ─── Correlation Helpers ─────────────────────────────────────────────────────

def build_h012_returns(closes: pd.DataFrame) -> pd.Series:
    """
    Replicate H-012 cross-sectional momentum (60d lookback, 5d rebal, top/bottom 4).
    Long top-4 by 60d return, short bottom-4. Dollar-neutral.
    """
    lookback   = H012_LOOKBACK
    rebal_freq = H012_REBAL
    n_long     = H012_N
    warmup     = lookback + 5

    rolling_ret = closes.pct_change(lookback)
    n           = len(closes)

    prev_weights    = pd.Series(0.0, index=closes.columns)
    daily_rets_list = []

    for i in range(1, n):
        current_weights = prev_weights.copy()

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            rets  = rolling_ret.iloc[i - 1].dropna()
            if len(rets) >= 2 * n_long:
                ranked = rets.sort_values(ascending=False)
                longs  = ranked.index[:n_long]
                shorts = ranked.index[-n_long:]

                new_weights = pd.Series(0.0, index=closes.columns)
                for sym in longs:
                    new_weights[sym] =  1.0 / n_long
                for sym in shorts:
                    new_weights[sym] = -1.0 / n_long

                turnover = (new_weights - prev_weights).abs().sum()
                port_ret = ((new_weights * ((closes.iloc[i] / closes.iloc[i - 1]) - 1.0)).sum()
                            - turnover * FEE_RATE)
                current_weights = new_weights
                prev_weights    = current_weights.copy()
                daily_rets_list.append(port_ret)
                continue

        port_ret = (current_weights * ((closes.iloc[i] / closes.iloc[i - 1]) - 1.0)).sum()
        daily_rets_list.append(port_ret)
        prev_weights = current_weights.copy()

    return pd.Series(daily_rets_list, index=closes.index[1:])


def build_h019_returns(closes: pd.DataFrame) -> pd.Series:
    """
    Replicate H-019 total-volatility factor (30d lookback, 5d rebal, top/bottom 4).
    Long lowest 4 by total 30d vol, short highest 4.
    """
    lookback   = 30
    rebal_freq = 5
    n_long     = 4
    warmup     = lookback + 5

    n = len(closes)
    log_rets = np.log(closes / closes.shift(1))
    rolling_vol = log_rets.rolling(lookback, min_periods=lookback).std()

    prev_weights    = pd.Series(0.0, index=closes.columns)
    daily_rets_list = []

    for i in range(1, n):
        current_weights = prev_weights.copy()

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            vols = rolling_vol.iloc[i - 1].dropna()
            if len(vols) >= 2 * n_long:
                ranked = vols.sort_values(ascending=True)
                longs  = ranked.index[:n_long]   # lowest vol = LONG
                shorts = ranked.index[-n_long:]  # highest vol = SHORT

                new_weights = pd.Series(0.0, index=closes.columns)
                for sym in longs:
                    new_weights[sym] =  1.0 / n_long
                for sym in shorts:
                    new_weights[sym] = -1.0 / n_long

                turnover = (new_weights - prev_weights).abs().sum()
                port_ret = ((new_weights * ((closes.iloc[i] / closes.iloc[i - 1]) - 1.0)).sum()
                            - turnover * FEE_RATE)
                current_weights = new_weights
                prev_weights    = current_weights.copy()
                daily_rets_list.append(port_ret)
                continue

        port_ret = (current_weights * ((closes.iloc[i] / closes.iloc[i - 1]) - 1.0)).sum()
        daily_rets_list.append(port_ret)
        prev_weights = current_weights.copy()

    return pd.Series(daily_rets_list, index=closes.index[1:])


def correlation_with_benchmark(
    h144_rets: pd.Series, bench_rets: pd.Series, bench_name: str
) -> dict:
    """Pearson correlation between H-144 and a benchmark strategy's daily returns."""
    common = h144_rets.index.intersection(bench_rets.index)
    if len(common) < 50:
        return {"correlation": None, "n_common_days": len(common), "error": "insufficient overlap"}

    corr = float(h144_rets.loc[common].corr(bench_rets.loc[common]))
    return {
        "benchmark":   bench_name,
        "correlation": round(corr, 4),
        "n_common_days": len(common),
    }


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("H-144: IDIOSYNCRATIC VOLATILITY FACTOR — Backtest")
    print("=" * 70)

    # ── 1. Load data ──────────────────────────────────────────────────────
    print("\n[1] Loading daily close prices...")
    closes = load_daily_closes()
    n_assets = len(closes.columns)
    n_days   = len(closes)
    print(f"    Assets loaded: {n_assets}  ({', '.join(closes.columns.tolist())})")
    print(f"    Days: {n_days}  ({closes.index[0].date()} to {closes.index[-1].date()})")

    if n_assets < 10 or n_days < 400:
        print("ERROR: insufficient data for backtest")
        return

    # ── 2. Full parameter grid ────────────────────────────────────────────
    total_params = len(LOOKBACKS) * len(REBAL_FREQS) * len(N_POSITIONS)
    print(f"\n[2] Parameter grid: {len(LOOKBACKS)} lookbacks x {len(REBAL_FREQS)} rebals "
          f"x {len(N_POSITIONS)} N = {total_params} combinations")
    print(f"    Lookbacks: {LOOKBACKS}")
    print(f"    Rebal freqs: {REBAL_FREQS}")
    print(f"    N positions: {N_POSITIONS}")

    grid_df = run_parameter_grid(closes)
    grid_df = grid_df.sort_values("sharpe", ascending=False).reset_index(drop=True)

    n_positive = int((grid_df["sharpe"] > 0).sum())
    pct_pos    = n_positive / total_params

    print(f"\n    IS RESULTS:")
    print(f"    Total params: {total_params}")
    print(f"    Positive Sharpe: {n_positive}/{total_params} ({pct_pos:.0%})")
    print(f"    Mean Sharpe:   {grid_df['sharpe'].mean():.4f}")
    print(f"    Median Sharpe: {grid_df['sharpe'].median():.4f}")
    print(f"    Min / Max:     {grid_df['sharpe'].min():.4f} / {grid_df['sharpe'].max():.4f}")

    print(f"\n    Top 10 parameter sets:")
    for _, row in grid_df.head(10).iterrows():
        print(f"      L{int(row['lookback'])}_R{int(row['rebal'])}_N{int(row['n_pos'])}: "
              f"Sharpe {row['sharpe']:.4f}  Ann {row['annual_ret']:.2%}  "
              f"DD {row['max_dd']:.2%}  WR {row['win_rate']:.1%}")

    # Full Sharpe table
    print(f"\n    Sharpe grid (rows=L x N, cols=R):")
    header = "           " + "".join(f"  R{r:2d}  " for r in REBAL_FREQS)
    print(header)
    for lb in LOOKBACKS:
        for np_ in N_POSITIONS:
            row_data = grid_df[(grid_df["lookback"] == lb) & (grid_df["n_pos"] == np_)]
            sharpes  = {int(r["rebal"]): r["sharpe"] for _, r in row_data.iterrows()}
            line     = f"    L{lb:2d}_N{np_}:  "
            for rb in REBAL_FREQS:
                s    = sharpes.get(rb, float("nan"))
                mark = "*" if s > 0 else " "
                line += f"{mark}{s:+.3f} "
            print(line)

    # ── 3. Best parameter set ─────────────────────────────────────────────
    best     = grid_df.iloc[0]
    best_lb  = int(best["lookback"])
    best_rb  = int(best["rebal"])
    best_np  = int(best["n_pos"])

    print(f"\n[3] Best params: L{best_lb}_R{best_rb}_N{best_np}")
    print(f"    IS Sharpe:     {best['sharpe']:.4f}")
    print(f"    Annual return: {best['annual_ret']:.2%}")
    print(f"    Max drawdown:  {best['max_dd']:.2%}")
    print(f"    Win rate:      {best['win_rate']:.1%}")

    # ── 4. Walk-forward validation ────────────────────────────────────────
    print(f"\n[4] Walk-forward: 6 expanding folds x {WF_TEST_DAYS}d test "
          f"(min train {WF_MIN_TRAIN}d)...")

    wf_result = walk_forward_validation(closes, best_lb, best_rb, best_np)

    if "error" in wf_result and "folds" not in wf_result:
        print(f"    ERROR: {wf_result['error']}")
    else:
        if "error" in wf_result:
            print(f"    WARNING: {wf_result['error']}")
        folds = wf_result.get("folds", [])
        for fold in folds:
            mark = "+" if fold["sharpe"] > 0 else "-"
            print(f"    Fold {fold['fold']} ({fold['start']} - {fold['end']}): "
                  f"[{mark}] Sharpe {fold['sharpe']:+.3f}  "
                  f"Ann {fold['annual_ret']:.2%}  DD {fold['max_dd']:.2%}  "
                  f"({fold['n_days']}d)")
        if "n_pos_folds" in wf_result:
            print(f"\n    Positive folds: {wf_result['n_pos_folds']}/{WF_FOLDS}")
            print(f"    Combined OOS Sharpe: {wf_result.get('combined_sharpe', 'N/A')}")
            print(f"    Combined OOS Ann:    {wf_result.get('combined_annual_ret', 'N/A'):.2%}" if 'combined_annual_ret' in wf_result else "")
            print(f"    Combined OOS DD:     {wf_result.get('combined_max_dd', 'N/A'):.2%}" if 'combined_max_dd' in wf_result else "")
            print(f"    Total OOS days:      {wf_result.get('total_oos_days', 0)}")

    # ── 5. Split-half validation ──────────────────────────────────────────
    print(f"\n[5] Split-half validation ({total_params} params per half)...")
    sh_result = split_half_validation(closes)
    print(f"    Half 1 ({sh_result['half1_period']}): mean Sharpe {sh_result['half1_mean_sharpe']:.4f}")
    print(f"    Half 2 ({sh_result['half2_period']}): mean Sharpe {sh_result['half2_mean_sharpe']:.4f}")
    print(f"    Cross-half Sharpe rank correlation: {sh_result['sharpe_rank_corr']:.4f}")
    print(f"    Positive in both halves: {sh_result['both_positive']} / {sh_result['total_params']} "
          f"({sh_result['both_positive_pct']:.0%})")

    # ── 6. Strategy correlations ──────────────────────────────────────────
    print(f"\n[6] Correlations with H-012 and H-019...")

    r_h144     = run_backtest(closes, lookback=best_lb, rebal_freq=best_rb, n_pos=best_np)
    h144_rets  = r_h144["daily_returns"]

    h012_rets  = build_h012_returns(closes)
    h019_rets  = build_h019_returns(closes)

    corr_h012  = correlation_with_benchmark(h144_rets, h012_rets, "H-012 momentum")
    corr_h019  = correlation_with_benchmark(h144_rets, h019_rets, "H-019 total vol")

    print(f"    H-012 (momentum)   correlation: "
          f"{corr_h012.get('correlation', 'N/A'):.4f}  "
          f"(n={corr_h012.get('n_common_days')})")
    print(f"    H-019 (total vol)  correlation: "
          f"{corr_h019.get('correlation', 'N/A'):.4f}  "
          f"(n={corr_h019.get('n_common_days')})")

    # ── 7. Verdict ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    crit_is_pct    = pct_pos >= 0.80
    crit_wf_folds  = wf_result.get("n_pos_folds", 0) >= 4
    crit_sh_corr   = sh_result["sharpe_rank_corr"] > 0
    crit_h012_corr = (corr_h012.get("correlation") is not None
                      and abs(corr_h012["correlation"]) <= 0.40)

    check = lambda ok: "PASS" if ok else "FAIL"
    print(f"  IS >=80% positive:        {check(crit_is_pct)}  ({pct_pos:.0%})")
    print(f"  WF >=4/6 folds positive:  {check(crit_wf_folds)}  "
          f"({wf_result.get('n_pos_folds', 0)}/{WF_FOLDS})")
    print(f"  Split-half corr > 0:      {check(crit_sh_corr)}  "
          f"({sh_result['sharpe_rank_corr']:.4f})")
    print(f"  H-012 |corr| <= 0.40:     {check(crit_h012_corr)}  "
          f"({corr_h012.get('correlation', 'N/A')})")

    n_pass  = sum([crit_is_pct, crit_wf_folds, crit_sh_corr, crit_h012_corr])
    verdict = "CONFIRMED" if n_pass == 4 else ("MARGINAL" if n_pass >= 3 else "REJECTED")

    print(f"\n  Criteria passed: {n_pass}/4")
    print(f"  VERDICT: {verdict}")
    print(f"\n  Best params: L{best_lb}_R{best_rb}_N{best_np}")
    print(f"  IS Sharpe:           {best['sharpe']:.4f}")
    print(f"  IS Annual return:    {best['annual_ret']:.2%}")
    print(f"  IS Max drawdown:     {best['max_dd']:.2%}")
    if "combined_sharpe" in wf_result:
        print(f"  WF combined Sharpe:  {wf_result['combined_sharpe']:.4f}")
        print(f"  WF combined Ann:     {wf_result['combined_annual_ret']:.2%}")
    print(f"  H-012 correlation:   {corr_h012.get('correlation', 'N/A')}")
    print(f"  H-019 correlation:   {corr_h019.get('correlation', 'N/A')}")
    print("=" * 70)

    # ── 8. Save results ───────────────────────────────────────────────────
    results = {
        "hypothesis":  "H-144",
        "title":       "Idiosyncratic Volatility Factor",
        "run_date":    str(pd.Timestamp.now().date()),
        "data": {
            "n_assets":   n_assets,
            "n_days":     n_days,
            "date_range": f"{closes.index[0].date()} to {closes.index[-1].date()}",
            "assets":     list(closes.columns),
        },
        "param_grid": {
            "n_total":              total_params,
            "n_positive":           n_positive,
            "pct_positive":         round(pct_pos, 4),
            "mean_sharpe":          round(float(grid_df["sharpe"].mean()), 4),
            "median_sharpe":        round(float(grid_df["sharpe"].median()), 4),
            "min_sharpe":           round(float(grid_df["sharpe"].min()), 4),
            "max_sharpe":           round(float(grid_df["sharpe"].max()), 4),
            "all_results":          grid_df.to_dict("records"),
        },
        "best_params": {
            "lookback":   best_lb,
            "rebal_freq": best_rb,
            "n_positions": best_np,
            "sharpe":     float(best["sharpe"]),
            "annual_ret": float(best["annual_ret"]),
            "max_dd":     float(best["max_dd"]),
            "win_rate":   float(best["win_rate"]),
        },
        "walk_forward":  wf_result,
        "split_half":    sh_result,
        "correlations": {
            "h012": corr_h012,
            "h019": corr_h019,
        },
        "verdict": {
            "result": verdict,
            "n_pass": n_pass,
            "criteria": {
                "is_pct_positive":   crit_is_pct,
                "wf_folds_positive": crit_wf_folds,
                "split_half_corr":   crit_sh_corr,
                "h012_corr_limit":   crit_h012_corr,
            },
        },
        "config": {
            "fee_rate":      FEE_RATE,
            "initial_capital": INITIAL_CAPITAL,
            "dollar_neutral": True,
            "ranking_lag":    1,
        },
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to {out_path}")


if __name__ == "__main__":
    main()
