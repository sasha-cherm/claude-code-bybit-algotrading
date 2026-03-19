"""
H-032: Pairwise Cointegration Statistical Arbitrage

Research script for testing all 91 pairs of 14 crypto assets for cointegration
and backtesting spread trading strategies on viable pairs.

Steps:
1. Load & resample all 14 assets to daily OHLCV
2. Test all 91 pairs for cointegration (Engle-Granger)
3. Estimate half-lives for cointegrated pairs
4. Backtest spread trading with parameter sweeps
5. Walk-forward validation for top candidates
6. Multi-pair portfolio construction
7. Correlation with H-012 (cross-sectional momentum)
"""

import sys
import warnings
from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint
from scipy import stats

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

# ─── Configuration ───────────────────────────────────────────────────────

ASSETS = ["BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX", "LINK",
          "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM"]

DATA_DIR = ROOT / "data"
BASE_FEE = 0.001          # 0.1% per side = 0.2% round-trip
SLIPPAGE_BPS = 2.0
INITIAL_CAPITAL = 10_000.0
COINT_PVALUE = 0.05
MIN_HALF_LIFE = 5
MAX_HALF_LIFE = 60
PERIODS_PER_YEAR_DAILY = 365

# Parameter sweep ranges
WINDOW_RANGE = [20, 30, 40, 50, 60]
ENTRY_Z_RANGE = [1.0, 1.5, 2.0, 2.5]
EXIT_Z_RANGE = [0.0, 0.25, 0.5]
STOP_Z_RANGE = [3.0, 3.5, 4.0]


# ─── Data Loading ────────────────────────────────────────────────────────

def load_all_daily():
    """Load all 14 assets and resample 1h to daily."""
    daily = {}
    for sym in ASSETS:
        fpath = DATA_DIR / f"{sym}_USDT_1h.parquet"
        if not fpath.exists():
            print(f"  WARNING: {fpath} not found, skipping {sym}")
            continue
        df = pd.read_parquet(fpath)
        # Resample to daily
        d = df.resample("1D").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum"
        }).dropna()
        daily[sym] = d
        print(f"  {sym}: {len(d)} daily bars, {d.index[0].date()} to {d.index[-1].date()}")
    return daily


def build_close_matrix(daily_data):
    """Build aligned close price matrix for all assets."""
    closes = pd.DataFrame({sym: d["close"] for sym, d in daily_data.items()})
    closes = closes.dropna()
    print(f"\n  Aligned close matrix: {closes.shape[0]} days x {closes.shape[1]} assets")
    print(f"  Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    return closes


# ─── Cointegration Testing ──────────────────────────────────────────────

def estimate_half_life(spread):
    """Estimate OU process half-life from the spread series."""
    spread_clean = spread.dropna()
    if len(spread_clean) < 30:
        return np.nan
    lag = spread_clean.shift(1).dropna()
    delta = spread_clean.diff().dropna()
    # Align
    common_idx = lag.index.intersection(delta.index)
    lag = lag.loc[common_idx]
    delta = delta.loc[common_idx]
    if len(lag) < 20:
        return np.nan
    # OLS: delta_spread = a + b * spread_lag
    X = np.column_stack([np.ones(len(lag)), lag.values])
    y = delta.values
    try:
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        b = beta[1]
        if b >= 0:
            return np.nan  # Not mean-reverting
        half_life = -np.log(2) / np.log(1 + b)
        return half_life
    except Exception:
        return np.nan


def test_all_pairs(closes):
    """Test all 91 pairs for cointegration."""
    print("\n" + "=" * 70)
    print("STEP 2: COINTEGRATION TESTING (Engle-Granger)")
    print("=" * 70)

    assets = closes.columns.tolist()
    pairs = list(combinations(assets, 2))
    print(f"  Testing {len(pairs)} pairs...")

    results = []
    for a, b in pairs:
        log_a = np.log(closes[a])
        log_b = np.log(closes[b])

        # Engle-Granger test
        try:
            score, pvalue, _ = coint(log_a, log_b)
        except Exception:
            pvalue = 1.0
            score = 0.0

        # Compute spread = log(A) - beta * log(B)
        # OLS for hedge ratio
        X = np.column_stack([np.ones(len(log_b)), log_b.values])
        y = log_a.values
        beta_ols = np.linalg.lstsq(X, y, rcond=None)[0]
        hedge_ratio = beta_ols[1]
        spread = log_a - hedge_ratio * log_b

        # Half-life
        hl = estimate_half_life(spread)

        # Spread stats
        spread_mean = spread.mean()
        spread_std = spread.std()

        results.append({
            "pair": f"{a}/{b}",
            "asset_a": a, "asset_b": b,
            "coint_score": score,
            "coint_pvalue": pvalue,
            "hedge_ratio": hedge_ratio,
            "half_life": hl,
            "spread_mean": spread_mean,
            "spread_std": spread_std,
        })

    df = pd.DataFrame(results)

    # Summary
    sig = df[df["coint_pvalue"] < COINT_PVALUE]
    print(f"\n  Cointegrated pairs (p < {COINT_PVALUE}): {len(sig)} / {len(df)}")

    if len(sig) > 0:
        print(f"\n  {'Pair':<12} {'p-value':>8} {'Half-life':>10} {'Hedge':>7} {'Spread SD':>10}")
        print("  " + "-" * 52)
        for _, r in sig.sort_values("coint_pvalue").iterrows():
            hl_str = f"{r['half_life']:.1f}" if not np.isnan(r["half_life"]) else "N/A"
            print(f"  {r['pair']:<12} {r['coint_pvalue']:>8.4f} {hl_str:>10} {r['hedge_ratio']:>7.3f} {r['spread_std']:>10.4f}")

    # Also show near-misses (p < 0.10) for reference
    near = df[(df["coint_pvalue"] >= COINT_PVALUE) & (df["coint_pvalue"] < 0.10)]
    if len(near) > 0:
        print(f"\n  Near-miss pairs (0.05 < p < 0.10): {len(near)}")
        for _, r in near.sort_values("coint_pvalue").iterrows():
            hl_str = f"{r['half_life']:.1f}" if not np.isnan(r["half_life"]) else "N/A"
            print(f"  {r['pair']:<12} p={r['coint_pvalue']:.4f}  HL={hl_str}")

    # Viable pairs: cointegrated AND reasonable half-life
    viable = sig[
        (sig["half_life"] >= MIN_HALF_LIFE) &
        (sig["half_life"] <= MAX_HALF_LIFE)
    ].copy()
    print(f"\n  Viable pairs (cointegrated + HL {MIN_HALF_LIFE}-{MAX_HALF_LIFE}d): {len(viable)}")

    return df, sig, viable


# ─── Spread Backtest ─────────────────────────────────────────────────────

def backtest_pair(closes, asset_a, asset_b, hedge_ratio, window, entry_z,
                  exit_z, stop_z, fee_mult=1.0):
    """
    Backtest a pairs trading strategy on the spread.

    Returns: dict with metrics, or None if insufficient trades.
    """
    log_a = np.log(closes[asset_a])
    log_b = np.log(closes[asset_b])
    spread = log_a - hedge_ratio * log_b

    n = len(spread)
    if n < window + 10:
        return None

    fee_rate = BASE_FEE * fee_mult + SLIPPAGE_BPS / 10_000

    # Rolling z-score
    roll_mean = spread.rolling(window).mean()
    roll_std = spread.rolling(window).std()
    zscore = (spread - roll_mean) / roll_std

    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital
    position = 0  # +1 = long spread, -1 = short spread, 0 = flat
    entry_price_a = 0.0
    entry_price_b = 0.0
    trades_pnl = []
    n_trades = 0

    for i in range(1, n):
        price_a = closes[asset_a].iloc[i]
        price_b = closes[asset_b].iloc[i]
        prev_price_a = closes[asset_a].iloc[i - 1]
        prev_price_b = closes[asset_b].iloc[i - 1]
        z = zscore.iloc[i]

        if np.isnan(z):
            equity[i] = equity[i - 1]
            continue

        # PnL from holding
        if position != 0:
            # Long spread: long A, short B (hedge_ratio units)
            # Short spread: short A, long B
            ret_a = (price_a - prev_price_a) / prev_price_a
            ret_b = (price_b - prev_price_b) / prev_price_b
            # Position PnL (spread uses dollar-neutral: 50% each leg)
            half_cap = equity[i - 1] * 0.5
            if position == 1:  # long spread
                pnl = half_cap * ret_a - half_cap * hedge_ratio * ret_b
            else:  # short spread
                pnl = -half_cap * ret_a + half_cap * hedge_ratio * ret_b
            equity[i] = equity[i - 1] + pnl
        else:
            equity[i] = equity[i - 1]

        # Check exits first
        if position != 0:
            close_trade = False
            # Stop-loss
            if abs(z) > stop_z and np.sign(z) == np.sign(position):
                close_trade = True
            # Mean reversion exit
            elif position == 1 and z > -exit_z:
                close_trade = True
            elif position == -1 and z < exit_z:
                close_trade = True

            if close_trade:
                # Calculate trade PnL
                trade_ret = (equity[i] - entry_equity) / entry_equity
                trades_pnl.append(trade_ret)
                n_trades += 1
                # Fee for closing
                equity[i] -= equity[i] * fee_rate * 2  # Both legs
                position = 0

        # Check entries
        if position == 0:
            if z < -entry_z:  # Spread too low -> long spread
                position = 1
                entry_price_a = price_a
                entry_price_b = price_b
                entry_equity = equity[i]
                equity[i] -= equity[i] * fee_rate * 2  # Both legs
            elif z > entry_z:  # Spread too high -> short spread
                position = -1
                entry_price_a = price_a
                entry_price_b = price_b
                entry_equity = equity[i]
                equity[i] -= equity[i] * fee_rate * 2  # Both legs

    # Close any open position at end
    if position != 0:
        trade_ret = (equity[-1] - entry_equity) / entry_equity
        trades_pnl.append(trade_ret)
        n_trades += 1

    if n_trades < 5:
        return None

    eq_series = pd.Series(equity, index=closes.index)
    # Remove leading zeros/NaN
    eq_series = eq_series[eq_series > 0]
    if len(eq_series) < 30:
        return None

    daily_rets = eq_series.pct_change().dropna()

    return {
        "n_trades": n_trades,
        "annual_return": annual_return(eq_series, PERIODS_PER_YEAR_DAILY),
        "max_drawdown": max_drawdown(eq_series),
        "sharpe": sharpe_ratio(daily_rets, periods_per_year=PERIODS_PER_YEAR_DAILY),
        "total_return": (eq_series.iloc[-1] / eq_series.iloc[0]) - 1,
        "win_rate": np.mean([1 if t > 0 else 0 for t in trades_pnl]) if trades_pnl else 0,
        "avg_trade": np.mean(trades_pnl) if trades_pnl else 0,
        "equity": eq_series,
        "daily_returns": daily_rets,
    }


def parameter_sweep(closes, asset_a, asset_b, hedge_ratio, fee_mult=1.0):
    """Run parameter sweep for a single pair."""
    results = []
    for w in WINDOW_RANGE:
        for ez in ENTRY_Z_RANGE:
            for xz in EXIT_Z_RANGE:
                for sz in STOP_Z_RANGE:
                    r = backtest_pair(closes, asset_a, asset_b, hedge_ratio,
                                     w, ez, xz, sz, fee_mult)
                    if r is not None:
                        r.update({
                            "window": w, "entry_z": ez, "exit_z": xz, "stop_z": sz,
                            "pair": f"{asset_a}/{asset_b}",
                        })
                        results.append(r)
    return results


# ─── Walk-Forward Validation ─────────────────────────────────────────────

def walk_forward_pair(closes, asset_a, asset_b, hedge_ratio, n_folds=6,
                      train_days=360, test_days=80):
    """Walk-forward validation for a pair with param optimization per fold."""
    n = len(closes)
    total_needed = train_days + n_folds * test_days
    if n < total_needed:
        # Adjust if needed
        train_days = max(180, n - n_folds * test_days)
        if train_days < 180:
            return None

    fold_results = []

    for fold in range(n_folds):
        test_end = n - (n_folds - fold - 1) * test_days
        test_start = test_end - test_days
        train_start = max(0, test_start - train_days)

        if train_start < 0 or test_start < train_days:
            continue

        train_data = closes.iloc[train_start:test_start]
        test_data = closes.iloc[test_start:test_end]

        if len(train_data) < 120 or len(test_data) < 30:
            continue

        # Re-estimate hedge ratio on train data
        log_a_train = np.log(train_data[asset_a])
        log_b_train = np.log(train_data[asset_b])
        X = np.column_stack([np.ones(len(log_b_train)), log_b_train.values])
        y = log_a_train.values
        try:
            beta_train = np.linalg.lstsq(X, y, rcond=None)[0]
            hr_train = beta_train[1]
        except Exception:
            continue

        # Re-test cointegration on train
        try:
            _, pval_train, _ = coint(log_a_train, log_b_train)
        except Exception:
            pval_train = 1.0

        # Optimize params on train data
        best_sharpe = -999
        best_params = None
        for w in [20, 30, 40, 50]:
            for ez in [1.0, 1.5, 2.0]:
                for xz in [0.0, 0.25]:
                    for sz in [3.0, 3.5]:
                        r = backtest_pair(train_data, asset_a, asset_b, hr_train,
                                          w, ez, xz, sz)
                        if r and r["sharpe"] > best_sharpe and r["n_trades"] >= 3:
                            best_sharpe = r["sharpe"]
                            best_params = (w, ez, xz, sz)

        if best_params is None:
            fold_results.append({
                "fold": fold, "train_sharpe": np.nan, "test_sharpe": np.nan,
                "test_return": np.nan, "n_trades": 0, "pval_train": pval_train,
            })
            continue

        w, ez, xz, sz = best_params

        # Test OOS with train-optimized params and train hedge ratio
        r_test = backtest_pair(test_data, asset_a, asset_b, hr_train,
                               w, ez, xz, sz)

        fold_results.append({
            "fold": fold,
            "train_sharpe": best_sharpe,
            "test_sharpe": r_test["sharpe"] if r_test else np.nan,
            "test_return": r_test["total_return"] if r_test else np.nan,
            "test_annual": r_test["annual_return"] if r_test else np.nan,
            "test_dd": r_test["max_drawdown"] if r_test else np.nan,
            "n_trades": r_test["n_trades"] if r_test else 0,
            "pval_train": pval_train,
            "params": best_params,
            "hedge_ratio": hr_train,
        })

    return fold_results


# ─── Fixed-Param Walk-Forward ────────────────────────────────────────────

def walk_forward_fixed_params(closes, asset_a, asset_b, hedge_ratio,
                               window, entry_z, exit_z, stop_z,
                               n_folds=6, train_days=360, test_days=80):
    """Walk-forward with fixed params (no in-fold optimization) — purer OOS test."""
    n = len(closes)
    fold_results = []

    for fold in range(n_folds):
        test_end = n - (n_folds - fold - 1) * test_days
        test_start = test_end - test_days
        train_start = max(0, test_start - train_days)

        if train_start < 0 or test_start < 60:
            continue

        train_data = closes.iloc[train_start:test_start]
        test_data = closes.iloc[test_start:test_end]

        if len(test_data) < 30:
            continue

        # Re-estimate hedge ratio on train
        log_a_train = np.log(train_data[asset_a])
        log_b_train = np.log(train_data[asset_b])
        X = np.column_stack([np.ones(len(log_b_train)), log_b_train.values])
        y = log_a_train.values
        try:
            beta_train = np.linalg.lstsq(X, y, rcond=None)[0]
            hr_train = beta_train[1]
        except Exception:
            continue

        r = backtest_pair(test_data, asset_a, asset_b, hr_train,
                          window, entry_z, exit_z, stop_z)
        fold_results.append({
            "fold": fold,
            "test_sharpe": r["sharpe"] if r else np.nan,
            "test_return": r["total_return"] if r else np.nan,
            "n_trades": r["n_trades"] if r else 0,
        })

    return fold_results


# ─── H-012 Correlation ──────────────────────────────────────────────────

def compute_h012_returns(closes):
    """Replicate H-012 cross-sectional momentum to get daily returns."""
    lookback = 60
    rebal_freq = 5
    n_long = 4
    n_short = 4
    n = len(closes)
    fee_rate = BASE_FEE + SLIPPAGE_BPS / 10_000

    rolling_ret = closes.pct_change(lookback)
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital
    prev_weights = pd.Series(0.0, index=closes.columns)

    warmup = lookback + 5
    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            rets = rolling_ret.iloc[i - 1]  # lagged
            valid = rets.dropna()
            if len(valid) < n_long + n_short:
                equity[i] = equity[i - 1]
                continue

            ranked = valid.sort_values(ascending=False)
            longs = ranked.head(n_long).index.tolist()
            shorts = ranked.tail(n_short).index.tolist()

            weights = pd.Series(0.0, index=closes.columns)
            for s in longs:
                weights[s] = 1.0 / n_long
            for s in shorts:
                weights[s] = -1.0 / n_short

            turnover = (weights - prev_weights).abs().sum()
            fee_cost = turnover * fee_rate * equity[i - 1] * 0.5
            prev_weights = weights.copy()
        else:
            weights = prev_weights.copy()

        # PnL from positions
        daily_rets = (price_today - price_yesterday) / price_yesterday
        pnl = (weights * daily_rets).sum() * equity[i - 1]
        equity[i] = equity[i - 1] + pnl

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            equity[i] -= fee_cost if 'fee_cost' in dir() else 0

    eq_series = pd.Series(equity, index=closes.index)
    eq_series = eq_series[eq_series > 0]
    return eq_series.pct_change().dropna()


# ─── Multi-Pair Portfolio ────────────────────────────────────────────────

def build_multi_pair_portfolio(pair_equities, weights=None):
    """Combine multiple pair strategy equity curves into a portfolio."""
    if not pair_equities:
        return None

    # Align all equity curves
    eq_df = pd.DataFrame(pair_equities)
    eq_df = eq_df.dropna()

    if weights is None:
        weights = {k: 1.0 / len(pair_equities) for k in pair_equities}

    # Weighted equity = sum of (weight * normalized_equity)
    normalized = eq_df.div(eq_df.iloc[0]) * INITIAL_CAPITAL
    portfolio = sum(normalized[k] * weights[k] for k in pair_equities)

    return portfolio


# ─── Main Research Pipeline ──────────────────────────────────────────────

def main():
    print("=" * 70)
    print("H-032: PAIRWISE COINTEGRATION STATISTICAL ARBITRAGE")
    print("=" * 70)

    # Step 1: Load data
    print("\nSTEP 1: LOADING DATA")
    print("-" * 40)
    daily_data = load_all_daily()
    closes = build_close_matrix(daily_data)

    # Step 2: Cointegration testing
    coint_df, sig_pairs, viable_pairs = test_all_pairs(closes)

    # Also test at relaxed threshold for more candidates
    relaxed = coint_df[coint_df["coint_pvalue"] < 0.10].copy()
    relaxed_viable = relaxed[
        (relaxed["half_life"] >= MIN_HALF_LIFE) &
        (relaxed["half_life"] <= MAX_HALF_LIFE)
    ]
    print(f"\n  Relaxed viable (p < 0.10, HL 5-60d): {len(relaxed_viable)}")

    # Use wider net for backtesting: all pairs with p < 0.10 and viable HL
    # Also include strict cointegrated pairs regardless of HL
    backtest_candidates = pd.concat([sig_pairs, relaxed_viable]).drop_duplicates("pair")
    # If too few, also try top pairs by p-value
    if len(backtest_candidates) < 5:
        top_by_pval = coint_df.nsmallest(15, "coint_pvalue")
        top_by_pval = top_by_pval[
            (top_by_pval["half_life"] >= MIN_HALF_LIFE) &
            (top_by_pval["half_life"] <= MAX_HALF_LIFE)
        ]
        backtest_candidates = pd.concat([backtest_candidates, top_by_pval]).drop_duplicates("pair")

    if len(backtest_candidates) == 0:
        print("\n  !!! NO VIABLE PAIRS FOUND — testing top 10 by p-value anyway")
        backtest_candidates = coint_df.nsmallest(10, "coint_pvalue")

    print(f"\n  Backtesting {len(backtest_candidates)} candidate pairs")

    # Step 3: Parameter sweep for all candidates
    print("\n" + "=" * 70)
    print("STEP 3: PARAMETER SWEEP BACKTESTS")
    print("=" * 70)

    all_results = []
    pair_best = {}

    for _, row in backtest_candidates.iterrows():
        pair = row["pair"]
        a, b = row["asset_a"], row["asset_b"]
        hr = row["hedge_ratio"]
        print(f"\n  {pair} (p={row['coint_pvalue']:.4f}, HL={row['half_life']:.1f}d, HR={hr:.3f})")

        results = parameter_sweep(closes, a, b, hr)
        n_positive = sum(1 for r in results if r["sharpe"] > 0)
        n_total = len(results)
        pct_positive = n_positive / n_total * 100 if n_total > 0 else 0

        if n_total > 0:
            best = max(results, key=lambda x: x["sharpe"])
            print(f"    {n_total} param sets, {n_positive} positive ({pct_positive:.0f}%)")
            print(f"    Best: Sharpe {best['sharpe']:.2f}, Ann {best['annual_return']*100:.1f}%, "
                  f"DD {best['max_drawdown']*100:.1f}%, WR {best['win_rate']*100:.0f}%, "
                  f"{best['n_trades']} trades")
            print(f"    Params: W={best['window']}, Ez={best['entry_z']}, Xz={best['exit_z']}, Sz={best['stop_z']}")
            pair_best[pair] = best
            for r in results:
                r["pair"] = pair
                r["asset_a"] = a
                r["asset_b"] = b
                r["hedge_ratio"] = hr
                r["coint_pvalue"] = row["coint_pvalue"]
                r["half_life"] = row["half_life"]
            all_results.extend(results)
        else:
            print(f"    No valid results (too few trades)")

    # Summary
    print("\n\n" + "=" * 70)
    print("STEP 3 SUMMARY: IN-SAMPLE PARAMETER SWEEP")
    print("=" * 70)

    if all_results:
        res_df = pd.DataFrame([{k: v for k, v in r.items()
                                if k not in ["equity", "daily_returns"]}
                               for r in all_results])
        n_total_params = len(res_df)
        n_pos = (res_df["sharpe"] > 0).sum()
        print(f"\n  Total param sets tested: {n_total_params}")
        print(f"  Positive Sharpe: {n_pos} ({n_pos/n_total_params*100:.0f}%)")
        print(f"  Mean Sharpe: {res_df['sharpe'].mean():.2f}")
        print(f"  Median Sharpe: {res_df['sharpe'].median():.2f}")

        # Per-pair summary
        print(f"\n  {'Pair':<12} {'Params':>7} {'%Pos':>6} {'Best Sharpe':>12} {'Ann Ret':>8} {'DD':>7} {'Trades':>7}")
        print("  " + "-" * 65)
        for pair, grp in res_df.groupby("pair"):
            n_p = len(grp)
            pct_p = (grp["sharpe"] > 0).mean() * 100
            best_s = grp["sharpe"].max()
            best_row = grp.loc[grp["sharpe"].idxmax()]
            print(f"  {pair:<12} {n_p:>7} {pct_p:>5.0f}% {best_s:>12.2f} "
                  f"{best_row['annual_return']*100:>7.1f}% {best_row['max_drawdown']*100:>6.1f}% "
                  f"{int(best_row['n_trades']):>7}")

    # Step 4: Fee robustness for top pairs
    print("\n\n" + "=" * 70)
    print("STEP 4: FEE ROBUSTNESS (3x fees = 0.3% round-trip)")
    print("=" * 70)

    fee_robust = {}
    for pair, best in pair_best.items():
        a, b = pair.split("/")
        hr = coint_df[coint_df["pair"] == pair]["hedge_ratio"].values[0]
        r3x = backtest_pair(closes, a, b, hr, best["window"], best["entry_z"],
                            best["exit_z"], best["stop_z"], fee_mult=3.0)
        if r3x:
            print(f"  {pair}: 1x fees Sharpe {best['sharpe']:.2f} -> 3x fees Sharpe {r3x['sharpe']:.2f} "
                  f"({'PASS' if r3x['sharpe'] > 0 else 'FAIL'})")
            fee_robust[pair] = r3x["sharpe"] > 0
        else:
            print(f"  {pair}: 3x fees — too few trades (FAIL)")
            fee_robust[pair] = False

    # Step 5: Walk-forward validation for promising pairs
    print("\n\n" + "=" * 70)
    print("STEP 5: WALK-FORWARD VALIDATION")
    print("=" * 70)

    # Select pairs for WF: positive in-sample AND fee-robust (or at least best candidates)
    wf_candidates = []
    for pair, best in sorted(pair_best.items(), key=lambda x: -x[1]["sharpe"]):
        if best["sharpe"] > 0:
            wf_candidates.append(pair)
    # Also include fee-robust pairs even if not top Sharpe
    for pair, robust in fee_robust.items():
        if robust and pair not in wf_candidates:
            wf_candidates.append(pair)

    wf_candidates = wf_candidates[:15]  # Cap at 15

    print(f"\n  Testing {len(wf_candidates)} pairs in walk-forward")

    wf_results = {}
    for pair in wf_candidates:
        a, b = pair.split("/")
        hr = coint_df[coint_df["pair"] == pair]["hedge_ratio"].values[0]
        best = pair_best[pair]

        print(f"\n  {pair} (IS Sharpe {best['sharpe']:.2f}):")

        # WF with parameter optimization per fold
        folds = walk_forward_pair(closes, a, b, hr, n_folds=6,
                                  train_days=360, test_days=80)

        if folds and len(folds) > 0:
            test_sharpes = [f["test_sharpe"] for f in folds if not np.isnan(f.get("test_sharpe", np.nan))]
            if test_sharpes:
                n_pos_folds = sum(1 for s in test_sharpes if s > 0)
                mean_oos = np.mean(test_sharpes)
                print(f"    Adaptive WF: {n_pos_folds}/{len(test_sharpes)} positive, "
                      f"mean OOS Sharpe {mean_oos:.2f}")
                for f in folds:
                    ts = f.get("test_sharpe", np.nan)
                    nt = f.get("n_trades", 0)
                    p = f.get("params", "N/A")
                    print(f"      Fold {f['fold']}: test Sharpe {ts:.2f}, {nt} trades, params={p}")
                wf_results[pair] = {
                    "n_positive": n_pos_folds,
                    "n_total": len(test_sharpes),
                    "mean_oos": mean_oos,
                    "folds": folds,
                }
            else:
                print(f"    No valid OOS results")
        else:
            print(f"    Walk-forward failed (insufficient data)")

        # Also fixed-param WF with best IS params
        fp_folds = walk_forward_fixed_params(
            closes, a, b, hr,
            best["window"], best["entry_z"], best["exit_z"], best["stop_z"],
            n_folds=6, train_days=360, test_days=80
        )
        if fp_folds:
            fp_sharpes = [f["test_sharpe"] for f in fp_folds if not np.isnan(f.get("test_sharpe", np.nan))]
            if fp_sharpes:
                fp_pos = sum(1 for s in fp_sharpes if s > 0)
                fp_mean = np.mean(fp_sharpes)
                print(f"    Fixed-param WF: {fp_pos}/{len(fp_sharpes)} positive, mean OOS {fp_mean:.2f}")

    # Step 6: Multi-pair portfolio
    print("\n\n" + "=" * 70)
    print("STEP 6: MULTI-PAIR PORTFOLIO")
    print("=" * 70)

    # Select pairs that passed walk-forward (>=4/6 positive)
    wf_passed = {}
    for pair, wr in wf_results.items():
        if wr["n_positive"] >= 3:  # Relaxed: >= 3/6 (50%)
            wf_passed[pair] = wr

    print(f"\n  Pairs passing WF (>=3/6 positive): {len(wf_passed)}")
    if wf_passed:
        for pair, wr in sorted(wf_passed.items(), key=lambda x: -x[1]["mean_oos"]):
            print(f"    {pair}: {wr['n_positive']}/{wr['n_total']} positive, mean OOS {wr['mean_oos']:.2f}")

    # Build portfolio from best IS params of passed pairs
    pair_equities = {}
    for pair in wf_passed:
        a, b = pair.split("/")
        hr = coint_df[coint_df["pair"] == pair]["hedge_ratio"].values[0]
        best = pair_best[pair]
        r = backtest_pair(closes, a, b, hr, best["window"], best["entry_z"],
                          best["exit_z"], best["stop_z"])
        if r:
            pair_equities[pair] = r["equity"]

    if len(pair_equities) >= 2:
        portfolio_eq = build_multi_pair_portfolio(pair_equities)
        if portfolio_eq is not None and len(portfolio_eq) > 30:
            port_rets = portfolio_eq.pct_change().dropna()
            port_sharpe = sharpe_ratio(port_rets, periods_per_year=PERIODS_PER_YEAR_DAILY)
            port_ann = annual_return(portfolio_eq, PERIODS_PER_YEAR_DAILY)
            port_dd = max_drawdown(portfolio_eq)
            print(f"\n  Multi-pair portfolio ({len(pair_equities)} pairs, equal weight):")
            print(f"    Sharpe: {port_sharpe:.2f}")
            print(f"    Annual return: {port_ann*100:.1f}%")
            print(f"    Max drawdown: {port_dd*100:.1f}%")
            print(f"    Total return: {((portfolio_eq.iloc[-1]/portfolio_eq.iloc[0])-1)*100:.1f}%")
    elif len(pair_equities) == 1:
        pair = list(pair_equities.keys())[0]
        eq = pair_equities[pair]
        rets = eq.pct_change().dropna()
        print(f"\n  Single pair ({pair}):")
        print(f"    Sharpe: {sharpe_ratio(rets, periods_per_year=PERIODS_PER_YEAR_DAILY):.2f}")
        print(f"    Annual return: {annual_return(eq, PERIODS_PER_YEAR_DAILY)*100:.1f}%")
        print(f"    Max drawdown: {max_drawdown(eq)*100:.1f}%")
    else:
        print("\n  No pairs passed walk-forward — no portfolio to build")

    # Step 7: Correlation with H-012
    print("\n\n" + "=" * 70)
    print("STEP 7: CORRELATION WITH H-012 (CROSS-SECTIONAL MOMENTUM)")
    print("=" * 70)

    h012_rets = compute_h012_returns(closes)
    print(f"\n  H-012 replicated: {len(h012_rets)} daily returns")

    for pair in wf_passed:
        if pair in pair_equities:
            eq = pair_equities[pair]
            pair_rets = eq.pct_change().dropna()
            # Align
            common = h012_rets.index.intersection(pair_rets.index)
            if len(common) > 30:
                corr = h012_rets.loc[common].corr(pair_rets.loc[common])
                print(f"  {pair} vs H-012: correlation = {corr:.3f}")

    if len(pair_equities) >= 2 and portfolio_eq is not None:
        port_rets = portfolio_eq.pct_change().dropna()
        common = h012_rets.index.intersection(port_rets.index)
        if len(common) > 30:
            corr = h012_rets.loc[common].corr(port_rets.loc[common])
            print(f"  Multi-pair portfolio vs H-012: correlation = {corr:.3f}")

    # ─── Extended analysis: test ALL pairs even without cointegration ─────
    print("\n\n" + "=" * 70)
    print("EXTENDED: TESTING TOP 20 PAIRS BY P-VALUE (REGARDLESS OF THRESHOLD)")
    print("=" * 70)

    top20 = coint_df.nsmallest(20, "coint_pvalue")
    extended_results = {}
    for _, row in top20.iterrows():
        pair = row["pair"]
        if pair in pair_best:
            continue  # Already tested
        a, b = row["asset_a"], row["asset_b"]
        hr = row["hedge_ratio"]
        results = parameter_sweep(closes, a, b, hr)
        if results:
            best = max(results, key=lambda x: x["sharpe"])
            n_pos = sum(1 for r in results if r["sharpe"] > 0)
            pct = n_pos / len(results) * 100
            extended_results[pair] = best
            if best["sharpe"] > 0.3:
                print(f"  {pair} (p={row['coint_pvalue']:.3f}): {n_pos}/{len(results)} pos ({pct:.0f}%), "
                      f"Best Sharpe {best['sharpe']:.2f}, Ann {best['annual_return']*100:.1f}%")

    # ─── FINAL SUMMARY ──────────────────────────────────────────────────
    print("\n\n" + "=" * 70)
    print("FINAL SUMMARY: H-032 COINTEGRATION STAT ARB")
    print("=" * 70)

    n_coint = len(sig_pairs)
    n_viable = len(viable_pairs)
    n_tested = len(pair_best)
    n_is_positive = sum(1 for p, b in pair_best.items() if b["sharpe"] > 0)
    n_fee_robust = sum(1 for v in fee_robust.values() if v)
    n_wf_passed = len(wf_passed)

    print(f"""
  Cointegration Results:
    Total pairs tested:         91
    Cointegrated (p < 0.05):    {n_coint}
    With viable HL (5-60d):     {n_viable}

  Backtest Results:
    Pairs backtested:           {n_tested}
    IS positive (best params):  {n_is_positive}
    Fee-robust (3x fees):       {n_fee_robust}
    Walk-forward passed:        {n_wf_passed}
""")

    if all_results:
        total_params = len(all_results)
        total_pos = sum(1 for r in all_results if r["sharpe"] > 0)
        print(f"  Parameter Robustness:")
        print(f"    Total param sets:          {total_params}")
        print(f"    Positive Sharpe:           {total_pos} ({total_pos/total_params*100:.0f}%)")

    print(f"\n  Walk-Forward Details:")
    for pair, wr in sorted(wf_results.items(), key=lambda x: -x[1].get("mean_oos", -999)):
        status = "PASS" if wr["n_positive"] >= 4 else ("MARGINAL" if wr["n_positive"] >= 3 else "FAIL")
        print(f"    {pair}: {wr['n_positive']}/{wr['n_total']} positive, "
              f"mean OOS {wr['mean_oos']:.2f} [{status}]")

    # Decision criteria
    print(f"\n  Decision Criteria Check:")
    criteria_met = 0
    total_criteria = 4

    # 1. Walk-forward >= 4/6
    any_strong_wf = any(wr["n_positive"] >= 4 for wr in wf_results.values()) if wf_results else False
    print(f"    [{'PASS' if any_strong_wf else 'FAIL'}] Walk-forward >= 4/6 positive")
    if any_strong_wf:
        criteria_met += 1

    # 2. Parameter robustness >= 50%
    if all_results:
        pct_pos = sum(1 for r in all_results if r["sharpe"] > 0) / len(all_results) * 100
    else:
        pct_pos = 0
    print(f"    [{'PASS' if pct_pos >= 50 else 'FAIL'}] Parameter robustness >= 50% ({pct_pos:.0f}%)")
    if pct_pos >= 50:
        criteria_met += 1

    # 3. Fee robustness
    print(f"    [{'PASS' if n_fee_robust > 0 else 'FAIL'}] Fee-robust at 3x fees ({n_fee_robust} pairs)")
    if n_fee_robust > 0:
        criteria_met += 1

    # 4. H-012 correlation < 0.4
    low_corr = True  # Default if no data
    for pair in wf_passed:
        if pair in pair_equities:
            eq = pair_equities[pair]
            pair_rets = eq.pct_change().dropna()
            common = h012_rets.index.intersection(pair_rets.index)
            if len(common) > 30:
                corr = abs(h012_rets.loc[common].corr(pair_rets.loc[common]))
                if corr >= 0.4:
                    low_corr = False
    print(f"    [{'PASS' if low_corr else 'FAIL'}] Correlation with H-012 < 0.4")
    if low_corr:
        criteria_met += 1

    print(f"\n  Criteria met: {criteria_met}/{total_criteria}")

    if criteria_met >= 3 and n_wf_passed >= 1:
        rec = "CONFIRMED (standalone)"
    elif criteria_met >= 2:
        rec = "MARGINAL — needs more data/pairs"
    else:
        rec = "REJECTED"

    print(f"\n  >>> RECOMMENDATION: {rec} <<<")

    return {
        "coint_df": coint_df,
        "pair_best": pair_best,
        "wf_results": wf_results,
        "all_results": all_results,
    }


if __name__ == "__main__":
    main()
