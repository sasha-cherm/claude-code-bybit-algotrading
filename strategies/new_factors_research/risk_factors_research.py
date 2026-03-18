"""
New Risk-Based Cross-Sectional Factor Research (Session 2026-03-19)

Three new risk-based factor strategies using the 14-asset universe:

H-024: Beta Factor (Low-Beta Anomaly)
  - Long low-beta assets, short high-beta assets
  - Beta measured vs BTC (market proxy)
  - Related to but distinct from H-019 (vol) — beta = systematic risk, vol = total risk

H-025: Skewness Factor (Negative Skew Premium)
  - Long negative-skew assets, short positive-skew assets
  - Academic: positive skew overpriced (lottery tickets), negative skew underpriced
  - Captures different risk dimension than momentum/vol

H-026: Drawdown Distance Factor
  - Long assets near their rolling highs, short assets deep in drawdown
  - Continuation signal — winners near ATH keep winning, losers in DD keep losing
  - May overlap with momentum — check correlation
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

BASE_FEE = 0.001
SLIPPAGE_BPS = 2.0
INITIAL_CAPITAL = 10_000.0


def resample_to_daily(df):
    daily = df.resample("1D").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()
    return daily


def load_all_data():
    hourly = {}
    daily = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df) < 200:
                print(f"  {sym}: insufficient data ({len(df)} bars), skipping")
                continue
            hourly[sym] = df
            daily[sym] = resample_to_daily(df)
            print(f"  {sym}: {len(daily[sym])} daily bars")
        except Exception as e:
            print(f"  {sym}: failed to load: {e}")
    return hourly, daily


def compute_metrics(equity_series):
    eq = equity_series[equity_series > 0]
    if len(eq) < 50:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0}
    rets = eq.pct_change().dropna()
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 2),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
    }


def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  fee_multiplier=1.0, warmup=65):
    if n_short is None:
        n_short = n_long
    n = len(closes)
    slippage = SLIPPAGE_BPS / 10_000
    fee_rate = BASE_FEE * fee_multiplier

    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    prev_weights = pd.Series(0.0, index=closes.columns)
    trades = 0

    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = ranking_series.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                equity[i] = equity[i - 1]
                continue

            ranked = valid.sort_values(ascending=False)
            longs = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            trades += int((weight_changes > 0.01).sum())

            turnover = weight_changes.sum() / 2
            fee_drag = turnover * (fee_rate + slippage)

            daily_rets = (price_today / price_yesterday - 1)
            port_ret = (new_weights * daily_rets).sum() - fee_drag

            prev_weights = new_weights
        else:
            daily_rets = (price_today / price_yesterday - 1)
            port_ret = (prev_weights * daily_rets).sum()

        equity[i] = equity[i - 1] * (1 + port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = trades
    metrics["equity"] = eq_series
    return metrics


def rolling_walk_forward(closes, ranking_fn, rebal_freq, n_long, n_short,
                         train_days=360, test_days=80, n_folds=6):
    """Run rolling walk-forward test."""
    n = len(closes)
    fold_results = []

    for fold in range(n_folds):
        test_end = n - fold * test_days
        test_start = test_end - test_days
        train_start = test_start - train_days

        if train_start < 0:
            break

        test_closes = closes.iloc[test_start:test_end]

        # Compute ranking on full data up to test_start (no look-ahead)
        ranking_full = ranking_fn(closes.iloc[:test_end])
        ranking_test = ranking_full.iloc[test_start:test_end]

        if len(test_closes) < 30 or len(ranking_test) < 30:
            continue

        result = run_xs_factor(test_closes, ranking_test, rebal_freq,
                               n_long, n_short, warmup=0)
        fold_results.append({
            "fold": fold,
            "sharpe": result["sharpe"],
            "annual_ret": result["annual_ret"],
            "max_dd": result["max_dd"],
        })

    return fold_results


# ═══════════════════════════════════════════════════════════════════════
# H-024: Beta Factor (Low-Beta Anomaly)
# ═══════════════════════════════════════════════════════════════════════

def compute_beta_ranking(closes, window):
    """
    Compute rolling beta of each asset vs BTC (market proxy).
    Returns NEGATIVE beta so low-beta ranks highest (long low-beta).
    """
    rets = closes.pct_change()

    ranking = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns, dtype=float)

    for col in closes.columns:
        if col == "BTC/USDT":
            ranking[col] = -1.0  # BTC beta = 1 by definition
            continue
        # Rolling covariance / variance for beta
        asset_rets = rets[col]
        btc_rets = rets["BTC/USDT"]
        rolling_cov = asset_rets.rolling(window).cov(btc_rets)
        rolling_var = btc_rets.rolling(window).var()
        beta = rolling_cov / rolling_var
        ranking[col] = -beta  # negative so low-beta ranks high

    # NaN out the warmup period
    ranking.iloc[:window] = np.nan

    return ranking


def h024_beta_factor(daily_data):
    print("\n" + "=" * 70)
    print("H-024: BETA FACTOR (Low-Beta Anomaly)")
    print("=" * 70)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    results = []
    params_tested = 0

    for window in [20, 30, 60, 90]:
        print(f"\n  Beta window: {window}d")
        ranking = compute_beta_ranking(closes, window)

        for rebal in [5, 7, 14, 21]:
            for n in [3, 4, 5]:
                params_tested += 1
                r = run_xs_factor(closes, ranking, rebal, n, n, warmup=max(window, 65))
                results.append({
                    "window": window, "rebal": rebal, "n": n,
                    **{k: v for k, v in r.items() if k != "equity"}
                })
                if r["sharpe"] > 0:
                    print(f"    W{window}_R{rebal}_N{n}: Sharpe {r['sharpe']:.2f}, "
                          f"ret {r['annual_ret']*100:.1f}%, DD {r['max_dd']*100:.1f}%")

    df_results = pd.DataFrame(results)
    n_positive = (df_results["sharpe"] > 0).sum()
    print(f"\n  SUMMARY: {n_positive}/{params_tested} positive Sharpe "
          f"({100*n_positive/params_tested:.0f}%)")
    if n_positive > 0:
        print(f"  Best: {df_results.loc[df_results['sharpe'].idxmax()].to_dict()}")
        print(f"  Mean positive: {df_results[df_results['sharpe']>0]['sharpe'].mean():.2f}")

    return df_results


# ═══════════════════════════════════════════════════════════════════════
# H-025: Skewness Factor (Negative Skew Premium)
# ═══════════════════════════════════════════════════════════════════════

def compute_skewness_ranking(closes, window):
    """
    Compute rolling skewness of returns.
    Returns NEGATIVE skewness so negative-skew (underpriced risk) ranks highest.
    """
    rets = closes.pct_change()
    ranking = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)

    for col in closes.columns:
        rolling_skew = rets[col].rolling(window).skew()
        ranking[col] = -rolling_skew  # negative skew ranks highest (buy cheap risk)

    return ranking


def h025_skewness_factor(daily_data):
    print("\n" + "=" * 70)
    print("H-025: SKEWNESS FACTOR (Negative Skew Premium)")
    print("=" * 70)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    results = []
    params_tested = 0

    for window in [20, 30, 60, 90]:
        print(f"\n  Skewness window: {window}d")
        ranking = compute_skewness_ranking(closes, window)

        for rebal in [5, 7, 14, 21]:
            for n in [3, 4, 5]:
                params_tested += 1
                r = run_xs_factor(closes, ranking, rebal, n, n, warmup=max(window, 65))
                results.append({
                    "window": window, "rebal": rebal, "n": n,
                    **{k: v for k, v in r.items() if k != "equity"}
                })
                if r["sharpe"] > 0:
                    print(f"    W{window}_R{rebal}_N{n}: Sharpe {r['sharpe']:.2f}, "
                          f"ret {r['annual_ret']*100:.1f}%, DD {r['max_dd']*100:.1f}%")

    df_results = pd.DataFrame(results)
    n_positive = (df_results["sharpe"] > 0).sum()
    print(f"\n  SUMMARY: {n_positive}/{params_tested} positive Sharpe "
          f"({100*n_positive/params_tested:.0f}%)")
    if n_positive > 0:
        print(f"  Best: {df_results.loc[df_results['sharpe'].idxmax()].to_dict()}")
        print(f"  Mean positive: {df_results[df_results['sharpe']>0]['sharpe'].mean():.2f}")

    return df_results


# ═══════════════════════════════════════════════════════════════════════
# H-026: Drawdown Distance Factor
# ═══════════════════════════════════════════════════════════════════════

def compute_dd_distance_ranking(closes, window):
    """
    Compute how close each asset is to its rolling high.
    close / rolling_max(window) — higher = closer to peak = rank high (continuation).
    """
    ranking = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)

    for col in closes.columns:
        rolling_max = closes[col].rolling(window, min_periods=window).max()
        ranking[col] = closes[col] / rolling_max  # 1.0 = at peak, <1 = in drawdown

    return ranking


def h026_drawdown_distance(daily_data):
    print("\n" + "=" * 70)
    print("H-026: DRAWDOWN DISTANCE FACTOR")
    print("=" * 70)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    results = []
    params_tested = 0

    for window in [20, 30, 60, 90, 120]:
        print(f"\n  DD window: {window}d")
        ranking = compute_dd_distance_ranking(closes, window)

        for rebal in [5, 7, 14, 21]:
            for n in [3, 4, 5]:
                params_tested += 1
                r = run_xs_factor(closes, ranking, rebal, n, n, warmup=max(window, 65))
                results.append({
                    "window": window, "rebal": rebal, "n": n,
                    **{k: v for k, v in r.items() if k != "equity"}
                })
                if r["sharpe"] > 0:
                    print(f"    W{window}_R{rebal}_N{n}: Sharpe {r['sharpe']:.2f}, "
                          f"ret {r['annual_ret']*100:.1f}%, DD {r['max_dd']*100:.1f}%")

    df_results = pd.DataFrame(results)
    n_positive = (df_results["sharpe"] > 0).sum()
    print(f"\n  SUMMARY: {n_positive}/{params_tested} positive Sharpe "
          f"({100*n_positive/params_tested:.0f}%)")
    if n_positive > 0:
        print(f"  Best: {df_results.loc[df_results['sharpe'].idxmax()].to_dict()}")
        print(f"  Mean positive: {df_results[df_results['sharpe']>0]['sharpe'].mean():.2f}")

    return df_results


# ═══════════════════════════════════════════════════════════════════════
# Correlation analysis with existing strategies
# ═══════════════════════════════════════════════════════════════════════

def compute_correlations(closes, daily_data, best_params):
    """Compute correlations between new factors and existing strategy equities."""
    print("\n" + "=" * 70)
    print("CORRELATION ANALYSIS WITH EXISTING STRATEGIES")
    print("=" * 70)

    # Load existing strategy equities
    from strategies.new_factors_research.research import run_xs_factor as run_xs_orig

    # H-012: Momentum (60d return, 5d rebal, N=4)
    mom_rets = closes.pct_change()
    mom_ranking = closes.pct_change(60)  # 60d momentum
    h012_result = run_xs_factor(closes, mom_ranking, 5, 4, 4, warmup=65)
    h012_eq = h012_result["equity"]

    # H-019: Low-vol (20d vol, 21d rebal, N=3)
    vol_ranking = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        vol_ranking[col] = -closes[col].pct_change().rolling(20).std()
    h019_result = run_xs_factor(closes, vol_ranking, 21, 3, 3, warmup=65)
    h019_eq = h019_result["equity"]

    # H-021: Volume momentum (VS5_VL20, 3d rebal, N=4)
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily_data.items()})
    volumes = volumes.reindex(closes.index).ffill().dropna()
    vol_short = volumes.rolling(5).mean()
    vol_long = volumes.rolling(20).mean()
    vol_mom_ranking = vol_short / vol_long
    h021_result = run_xs_factor(closes, vol_mom_ranking, 3, 4, 4, warmup=65)
    h021_eq = h021_result["equity"]

    # H-009: BTC daily EMA (approximate with BTC equity)
    btc_close = closes["BTC/USDT"]
    ema5 = btc_close.ewm(span=5).mean()
    ema40 = btc_close.ewm(span=40).mean()
    signal = (ema5 > ema40).astype(float) * 2 - 1  # +1 long, -1 short
    h009_eq = (1 + signal.shift(1) * btc_close.pct_change()).cumprod() * INITIAL_CAPITAL

    existing = {
        "H-009": h009_eq, "H-012": h012_eq, "H-019": h019_eq, "H-021": h021_eq
    }

    # Now compute correlations for each promising factor
    for name, params in best_params.items():
        if params is None:
            print(f"\n  {name}: No viable params — skipping correlation")
            continue

        print(f"\n  {name} (best params: {params}):")

        if name == "H-024":
            ranking = compute_beta_ranking(closes, params["window"])
        elif name == "H-025":
            ranking = compute_skewness_ranking(closes, params["window"])
        elif name == "H-026":
            ranking = compute_dd_distance_ranking(closes, params["window"])

        new_result = run_xs_factor(closes, ranking, params["rebal"], params["n"], params["n"],
                                   warmup=max(params.get("window", 65), 65))
        new_eq = new_result["equity"]

        new_rets = new_eq.pct_change().dropna()
        for strat_name, strat_eq in existing.items():
            strat_rets = strat_eq.pct_change().dropna()
            common = new_rets.index.intersection(strat_rets.index)
            if len(common) > 50:
                corr = new_rets.loc[common].corr(strat_rets.loc[common])
                print(f"    Corr with {strat_name}: {corr:.3f}")


# ═══════════════════════════════════════════════════════════════════════
# Walk-forward validation for promising factors
# ═══════════════════════════════════════════════════════════════════════

def walk_forward_test(closes, ranking_fn, rebal_freq, n_long, n_short,
                      train_days=360, test_days=80, n_folds=6, label=""):
    """Run rolling walk-forward OOS test."""
    print(f"\n  Walk-forward ({label}): {n_folds} folds, {train_days}d train, {test_days}d test")

    n = len(closes)
    fold_results = []

    for fold in range(n_folds):
        test_end = n - fold * test_days
        test_start = test_end - test_days

        if test_start < 65:
            break

        # Get the OOS period
        test_closes = closes.iloc[max(0, test_start-5):test_end]

        # Compute ranking using only data up to just before test period
        ranking_full = ranking_fn(closes.iloc[:test_end])
        ranking_test = ranking_full.iloc[max(0, test_start-5):test_end]

        if len(test_closes) < 30:
            continue

        result = run_xs_factor(test_closes, ranking_test, rebal_freq,
                               n_long, n_short, warmup=0)
        fold_results.append({
            "fold": fold,
            "sharpe": result["sharpe"],
            "annual_ret": result["annual_ret"],
            "max_dd": result["max_dd"],
        })
        sign = "+" if result["sharpe"] > 0 else " "
        print(f"    Fold {fold}: Sharpe {sign}{result['sharpe']:.2f}, "
              f"ret {result['annual_ret']*100:+.1f}%, DD {result['max_dd']*100:.1f}%")

    if fold_results:
        df = pd.DataFrame(fold_results)
        n_pos = (df["sharpe"] > 0).sum()
        print(f"    => {n_pos}/{len(df)} positive, mean Sharpe {df['sharpe'].mean():.2f}, "
              f"median {df['sharpe'].median():.2f}")
        return df
    return None


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Loading data...")
    hourly, daily = load_all_data()

    if len(daily) < 10:
        print("Error: need at least 10 assets")
        sys.exit(1)

    # --- Run all three factors ---
    df_024 = h024_beta_factor(daily)
    df_025 = h025_skewness_factor(daily)
    df_026 = h026_drawdown_distance(daily)

    # --- Determine best params for each ---
    best_params = {}

    for name, df in [("H-024", df_024), ("H-025", df_025), ("H-026", df_026)]:
        if (df["sharpe"] > 0).sum() > 0:
            best = df.loc[df["sharpe"].idxmax()]
            best_params[name] = {
                "window": int(best["window"]),
                "rebal": int(best["rebal"]),
                "n": int(best["n"]),
            }
        else:
            best_params[name] = None

    # --- Walk-forward validation for promising factors ---
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()

    print("\n" + "=" * 70)
    print("WALK-FORWARD VALIDATION")
    print("=" * 70)

    for name, params in best_params.items():
        if params is None:
            print(f"\n  {name}: Skipping WF (no positive IS params)")
            continue

        pct_pos = (eval(f"df_{name[-3:]}")["sharpe"] > 0).sum() / len(eval(f"df_{name[-3:]}")) * 100
        if pct_pos < 30:
            print(f"\n  {name}: Skipping WF (only {pct_pos:.0f}% IS positive)")
            continue

        if name == "H-024":
            ranking_fn = lambda c, w=params["window"]: compute_beta_ranking(c, w)
        elif name == "H-025":
            ranking_fn = lambda c, w=params["window"]: compute_skewness_ranking(c, w)
        elif name == "H-026":
            ranking_fn = lambda c, w=params["window"]: compute_dd_distance_ranking(c, w)

        walk_forward_test(closes, ranking_fn, params["rebal"], params["n"], params["n"],
                          label=f"{name} W{params['window']}_R{params['rebal']}_N{params['n']}")

    # --- Correlation analysis ---
    compute_correlations(closes, daily, best_params)

    # --- Final summary ---
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    for name, df in [("H-024", df_024), ("H-025", df_025), ("H-026", df_026)]:
        n_pos = (df["sharpe"] > 0).sum()
        pct = 100 * n_pos / len(df)
        best_s = df["sharpe"].max()
        mean_s = df["sharpe"].mean()
        print(f"  {name}: {n_pos}/{len(df)} positive ({pct:.0f}%), "
              f"best Sharpe {best_s:.2f}, mean {mean_s:.2f}")
