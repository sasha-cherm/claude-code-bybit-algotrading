"""
H-024 Deep Validation: Beta Factor vs H-019 Low-Vol

Key question: Is H-024 (low-beta) just H-019 (low-vol) in disguise?
If not, should it replace H-019 or be a 6th strategy?

Tests:
1. Head-to-head: H-024 vs H-019 across matched params
2. Portfolio: H-024 replacing H-019 vs original 5-strat
3. Portfolio: H-024 as 6th strategy
4. Residual beta (beta after removing vol effect)
5. Fee sensitivity
6. Additional WF with different params (not just the best IS)
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
                continue
            hourly[sym] = df
            daily[sym] = resample_to_daily(df)
        except Exception as e:
            print(f"  {sym}: failed: {e}")
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


def compute_beta_ranking(closes, window):
    rets = closes.pct_change()
    ranking = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        if col == "BTC/USDT":
            ranking[col] = -1.0
            continue
        asset_rets = rets[col]
        btc_rets = rets["BTC/USDT"]
        rolling_cov = asset_rets.rolling(window).cov(btc_rets)
        rolling_var = btc_rets.rolling(window).var()
        beta = rolling_cov / rolling_var
        ranking[col] = -beta
    ranking.iloc[:window] = np.nan
    return ranking


def compute_vol_ranking(closes, window):
    ranking = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        ranking[col] = -closes[col].pct_change().rolling(window).std()
    ranking.iloc[:window] = np.nan
    return ranking


def compute_idio_vol_ranking(closes, window):
    """Idiosyncratic (residual) volatility after removing BTC beta exposure."""
    rets = closes.pct_change()
    btc_rets = rets["BTC/USDT"]

    ranking = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns, dtype=float)

    for col in closes.columns:
        if col == "BTC/USDT":
            ranking[col] = 0.0  # BTC has zero idio vol by definition
            continue
        asset_rets = rets[col]
        rolling_cov = asset_rets.rolling(window).cov(btc_rets)
        rolling_var = btc_rets.rolling(window).var()
        beta = rolling_cov / rolling_var

        # Residual = actual return - beta * BTC return
        residual = asset_rets - beta * btc_rets
        # Idiosyncratic vol = rolling std of residuals
        idio_vol = residual.rolling(window).std()
        ranking[col] = -idio_vol  # low idio vol ranks high

    ranking.iloc[:window] = np.nan
    return ranking


if __name__ == "__main__":
    print("Loading data...")
    hourly, daily = load_all_data()
    print(f"  Loaded {len(daily)} assets")

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()

    # ═══════════════════════════════════════════════════════════════════
    # Test 1: Head-to-head — H-024 beta vs H-019 vol at matched params
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 1: HEAD-TO-HEAD — Beta vs Vol at matched params")
    print("=" * 70)

    params_grid = [
        (20, 21, 3), (30, 21, 3), (60, 21, 3), (90, 21, 3),
        (20, 14, 4), (30, 14, 4), (60, 14, 4), (90, 14, 4),
        (20, 7, 3), (30, 7, 3), (60, 7, 3), (90, 7, 3),
    ]

    print(f"\n  {'Params':<16} {'Beta Sharpe':>12} {'Vol Sharpe':>12} {'Beta>Vol':>10}")
    print("  " + "-" * 52)

    beta_wins = 0
    for window, rebal, n in params_grid:
        beta_rank = compute_beta_ranking(closes, window)
        vol_rank = compute_vol_ranking(closes, window)
        warmup = max(window, 65)

        beta_r = run_xs_factor(closes, beta_rank, rebal, n, n, warmup=warmup)
        vol_r = run_xs_factor(closes, vol_rank, rebal, n, n, warmup=warmup)

        winner = "YES" if beta_r["sharpe"] > vol_r["sharpe"] else "no"
        if beta_r["sharpe"] > vol_r["sharpe"]:
            beta_wins += 1

        print(f"  W{window}_R{rebal}_N{n:<8} {beta_r['sharpe']:>10.2f}   {vol_r['sharpe']:>10.2f}   {winner:>8}")

    print(f"\n  Beta wins: {beta_wins}/{len(params_grid)} ({100*beta_wins/len(params_grid):.0f}%)")

    # ═══════════════════════════════════════════════════════════════════
    # Test 2: Walk-forward across multiple param sets
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 2: WALK-FORWARD across multiple beta param sets")
    print("=" * 70)

    wf_params = [
        (20, 7, 3), (20, 7, 4), (30, 7, 4), (60, 7, 4),
        (60, 14, 4), (60, 21, 3), (90, 14, 4), (30, 14, 3),
    ]

    n_total = len(closes)
    test_days = 80
    n_folds = 6

    for window, rebal, n in wf_params:
        label = f"W{window}_R{rebal}_N{n}"
        folds = []

        for fold in range(n_folds):
            test_end = n_total - fold * test_days
            test_start = test_end - test_days
            if test_start < 65:
                break

            test_closes = closes.iloc[max(0, test_start-5):test_end]
            ranking = compute_beta_ranking(closes.iloc[:test_end], window)
            ranking_test = ranking.iloc[max(0, test_start-5):test_end]

            if len(test_closes) < 30:
                continue

            r = run_xs_factor(test_closes, ranking_test, rebal, n, n, warmup=0)
            folds.append(r["sharpe"])

        if folds:
            n_pos = sum(1 for s in folds if s > 0)
            print(f"  {label}: {n_pos}/{len(folds)} positive, mean {np.mean(folds):.2f}, "
                  f"median {np.median(folds):.2f} | folds: {[f'{s:.2f}' for s in folds]}")

    # ═══════════════════════════════════════════════════════════════════
    # Test 3: Fee sensitivity for best beta params
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 3: FEE SENSITIVITY (W60_R21_N3 + W20_R7_N3)")
    print("=" * 70)

    for window, rebal, n in [(60, 21, 3), (20, 7, 3)]:
        label = f"W{window}_R{rebal}_N{n}"
        ranking = compute_beta_ranking(closes, window)
        warmup = max(window, 65)

        print(f"\n  {label}:")
        for fee_mult in [1.0, 2.0, 3.0, 5.0]:
            r = run_xs_factor(closes, ranking, rebal, n, n,
                              fee_multiplier=fee_mult, warmup=warmup)
            print(f"    {fee_mult}x fees: Sharpe {r['sharpe']:.2f}, "
                  f"ret {r['annual_ret']*100:+.1f}%, trades {r['n_trades']}")

    # ═══════════════════════════════════════════════════════════════════
    # Test 4: Idiosyncratic vol factor
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 4: IDIOSYNCRATIC VOLATILITY FACTOR")
    print("=" * 70)
    print("  (Low idio vol = buy, high idio vol = sell)")

    idio_results = []
    for window in [20, 30, 60]:
        ranking = compute_idio_vol_ranking(closes, window)
        for rebal in [7, 14, 21]:
            for n in [3, 4]:
                warmup = max(window, 65)
                r = run_xs_factor(closes, ranking, rebal, n, n, warmup=warmup)
                label = f"W{window}_R{rebal}_N{n}"
                idio_results.append({"params": label, "sharpe": r["sharpe"],
                                     "annual_ret": r["annual_ret"], "max_dd": r["max_dd"]})
                if r["sharpe"] > 0:
                    print(f"  {label}: Sharpe {r['sharpe']:.2f}, "
                          f"ret {r['annual_ret']*100:.1f}%, DD {r['max_dd']*100:.1f}%")

    n_pos = sum(1 for r in idio_results if r["sharpe"] > 0)
    print(f"\n  SUMMARY: {n_pos}/{len(idio_results)} positive ({100*n_pos/len(idio_results):.0f}%)")

    # Check correlation of idio vol with existing strategies
    if n_pos > 0:
        best_idio = max(idio_results, key=lambda x: x["sharpe"])
        print(f"  Best: {best_idio}")

        # Parse best idio params
        parts = best_idio["params"].split("_")
        w_val = int(parts[0][1:])
        r_val = int(parts[1][1:])
        n_val = int(parts[2][1:])

        idio_ranking = compute_idio_vol_ranking(closes, w_val)
        idio_result = run_xs_factor(closes, idio_ranking, r_val, n_val, n_val,
                                    warmup=max(w_val, 65))
        idio_eq = idio_result["equity"]
        idio_rets = idio_eq.pct_change().dropna()

        # Correlations with existing strategies
        # H-019 (low-vol)
        vol_rank = compute_vol_ranking(closes, 20)
        h019_eq = run_xs_factor(closes, vol_rank, 21, 3, 3, warmup=65)["equity"]
        h019_rets = h019_eq.pct_change().dropna()
        common = idio_rets.index.intersection(h019_rets.index)
        print(f"  Corr with H-019 (vol): {idio_rets.loc[common].corr(h019_rets.loc[common]):.3f}")

        # H-024 (beta)
        beta_rank = compute_beta_ranking(closes, 60)
        h024_eq = run_xs_factor(closes, beta_rank, 21, 3, 3, warmup=65)["equity"]
        h024_rets = h024_eq.pct_change().dropna()
        common = idio_rets.index.intersection(h024_rets.index)
        print(f"  Corr with H-024 (beta): {idio_rets.loc[common].corr(h024_rets.loc[common]):.3f}")

        # H-012 (momentum)
        mom_rank = closes.pct_change(60)
        h012_eq = run_xs_factor(closes, mom_rank, 5, 4, 4, warmup=65)["equity"]
        h012_rets = h012_eq.pct_change().dropna()
        common = idio_rets.index.intersection(h012_rets.index)
        print(f"  Corr with H-012 (mom): {idio_rets.loc[common].corr(h012_rets.loc[common]):.3f}")

    # ═══════════════════════════════════════════════════════════════════
    # Test 5: Portfolio analysis — replace H-019 with H-024?
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 5: PORTFOLIO — H-024 replacing H-019 vs original")
    print("=" * 70)

    # Build all strategy equity curves
    # H-009: BTC EMA
    btc_close = closes["BTC/USDT"]
    ema5 = btc_close.ewm(span=5).mean()
    ema40 = btc_close.ewm(span=40).mean()
    signal = (ema5 > ema40).astype(float) * 2 - 1
    h009_eq = (1 + signal.shift(1) * btc_close.pct_change()).cumprod() * INITIAL_CAPITAL

    # H-012: Momentum
    mom_rank = closes.pct_change(60)
    h012_eq = run_xs_factor(closes, mom_rank, 5, 4, 4, warmup=65)["equity"]

    # H-019: Low-vol
    vol_rank = compute_vol_ranking(closes, 20)
    h019_eq = run_xs_factor(closes, vol_rank, 21, 3, 3, warmup=65)["equity"]

    # H-021: Volume momentum
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily.items()})
    volumes = volumes.reindex(closes.index).ffill().dropna()
    vol_short = volumes.rolling(5).mean()
    vol_long = volumes.rolling(20).mean()
    vol_mom_rank = vol_short / vol_long
    h021_eq = run_xs_factor(closes, vol_mom_rank, 3, 4, 4, warmup=65)["equity"]

    # H-024 Beta: best IS params
    for window, rebal, n in [(60, 21, 3), (20, 7, 3), (60, 7, 4), (30, 7, 4)]:
        beta_rank = compute_beta_ranking(closes, window)
        h024_eq = run_xs_factor(closes, beta_rank, rebal, n, n,
                                warmup=max(window, 65))["equity"]

        label = f"W{window}_R{rebal}_N{n}"

        # Build returns
        strat_returns = pd.DataFrame({
            "H-009": h009_eq.pct_change(),
            "H-012": h012_eq.pct_change(),
            "H-019": h019_eq.pct_change(),
            "H-021": h021_eq.pct_change(),
            "H-024": h024_eq.pct_change(),
        }).dropna()

        # Original 5-strat: 10/40/10/15/25 (H-011 flat, omit)
        # Weights without H-011 (renormalized): H-009 10, H-012 10, H-019 15, H-021 25 = 60%
        # For simplicity, compare only the active strategies (excl H-011)
        w_orig = {"H-009": 0.10/0.60, "H-012": 0.10/0.60, "H-019": 0.15/0.60, "H-021": 0.25/0.60}
        w_beta = {"H-009": 0.10/0.60, "H-012": 0.10/0.60, "H-024": 0.15/0.60, "H-021": 0.25/0.60}

        port_orig = sum(strat_returns[s] * w for s, w in w_orig.items())
        port_beta = sum(strat_returns[s] * w for s, w in w_beta.items())

        eq_orig = (1 + port_orig).cumprod() * INITIAL_CAPITAL
        eq_beta = (1 + port_beta).cumprod() * INITIAL_CAPITAL

        m_orig = compute_metrics(eq_orig)
        m_beta = compute_metrics(eq_beta)

        print(f"\n  {label}:")
        print(f"    Original (w/H-019): Sharpe {m_orig['sharpe']:.2f}, "
              f"ret {m_orig['annual_ret']*100:+.1f}%, DD {m_orig['max_dd']*100:.1f}%")
        print(f"    With H-024:         Sharpe {m_beta['sharpe']:.2f}, "
              f"ret {m_beta['annual_ret']*100:+.1f}%, DD {m_beta['max_dd']*100:.1f}%")

        # Also try 6-strat (adding H-024 alongside H-019)
        w_six = {"H-009": 0.08/0.60, "H-012": 0.08/0.60, "H-019": 0.12/0.60,
                 "H-024": 0.12/0.60, "H-021": 0.20/0.60}
        port_six = sum(strat_returns[s] * w for s, w in w_six.items())
        eq_six = (1 + port_six).cumprod() * INITIAL_CAPITAL
        m_six = compute_metrics(eq_six)
        print(f"    6-strat (both):     Sharpe {m_six['sharpe']:.2f}, "
              f"ret {m_six['annual_ret']*100:+.1f}%, DD {m_six['max_dd']*100:.1f}%")

    # ═══════════════════════════════════════════════════════════════════
    # Test 6: Full correlation matrix
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 6: FULL CORRELATION MATRIX (daily returns)")
    print("=" * 70)

    beta_rank_best = compute_beta_ranking(closes, 60)
    h024_eq_best = run_xs_factor(closes, beta_rank_best, 21, 3, 3, warmup=65)["equity"]

    all_eq = pd.DataFrame({
        "H-009": h009_eq,
        "H-012": h012_eq,
        "H-019": h019_eq,
        "H-021": h021_eq,
        "H-024": h024_eq_best,
    })
    all_rets = all_eq.pct_change().dropna()
    corr = all_rets.corr()
    print(corr.round(3).to_string())
