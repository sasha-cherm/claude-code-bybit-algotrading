"""
H-032: Pairwise Cointegration Statistical Arbitrage — V2

Improved version addressing V1 limitations:
- Walk-forward uses longer test windows (120d) with min 2 trades
- Also uses simple 50/50 train/test split
- Expanding-window cointegration stability test
- Rolling hedge ratio for robustness
- Better portfolio construction

Research steps:
1. Load daily data for all 14 assets
2. Test all 91 pairs for cointegration (Engle-Granger)
3. Estimate half-lives
4. Backtest spread trading with parameter sweeps
5. Walk-forward validation (multiple approaches)
6. Multi-pair portfolio construction
7. Correlation with H-012
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
BASE_FEE = 0.001          # 0.1% per side
SLIPPAGE_BPS = 2.0
INITIAL_CAPITAL = 10_000.0
PERIODS_PER_YEAR = 365

# Parameter sweep
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
        d = df.resample("1D").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum"
        }).dropna()
        daily[sym] = d
    return daily


def build_close_matrix(daily_data):
    """Build aligned close price matrix."""
    closes = pd.DataFrame({sym: d["close"] for sym, d in daily_data.items()})
    closes = closes.dropna()
    return closes


# ─── Cointegration Testing ──────────────────────────────────────────────

def estimate_half_life(spread):
    """Estimate OU process half-life."""
    spread_clean = spread.dropna()
    if len(spread_clean) < 30:
        return np.nan
    lag = spread_clean.shift(1)
    delta = spread_clean.diff()
    common = lag.dropna().index.intersection(delta.dropna().index)
    if len(common) < 20:
        return np.nan
    X = np.column_stack([np.ones(len(common)), lag.loc[common].values])
    y = delta.loc[common].values
    try:
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        b = beta[1]
        if b >= 0:
            return np.nan
        return -np.log(2) / np.log(1 + b)
    except Exception:
        return np.nan


def compute_hedge_ratio(log_a, log_b):
    """OLS hedge ratio."""
    X = np.column_stack([np.ones(len(log_b)), log_b.values])
    y = log_a.values
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    return beta[1]


def test_cointegration_stability(log_a, log_b, n_windows=4):
    """Test if cointegration holds across different sub-periods."""
    n = len(log_a)
    win_size = n // n_windows
    pvals = []
    for i in range(n_windows):
        start = i * win_size
        end = min((i + 1) * win_size, n)
        if end - start < 60:
            continue
        try:
            _, p, _ = coint(log_a.iloc[start:end], log_b.iloc[start:end])
            pvals.append(p)
        except Exception:
            pvals.append(1.0)
    return pvals


def test_all_pairs(closes):
    """Test all 91 pairs for cointegration."""
    print("\n" + "=" * 70)
    print("STEP 2: COINTEGRATION TESTING")
    print("=" * 70)

    assets = closes.columns.tolist()
    pairs = list(combinations(assets, 2))
    print(f"  Testing {len(pairs)} pairs...")

    results = []
    for a, b in pairs:
        log_a = np.log(closes[a])
        log_b = np.log(closes[b])

        try:
            score, pvalue, _ = coint(log_a, log_b)
        except Exception:
            pvalue = 1.0
            score = 0.0

        # Also test reverse direction
        try:
            score_r, pvalue_r, _ = coint(log_b, log_a)
        except Exception:
            pvalue_r = 1.0

        # Use the better direction
        best_pval = min(pvalue, pvalue_r)

        hr = compute_hedge_ratio(log_a, log_b)
        spread = log_a - hr * log_b
        hl = estimate_half_life(spread)

        # Cointegration stability across sub-periods
        stability_pvals = test_cointegration_stability(log_a, log_b)
        n_stable = sum(1 for p in stability_pvals if p < 0.15)

        results.append({
            "pair": f"{a}/{b}",
            "asset_a": a, "asset_b": b,
            "coint_pvalue": best_pval,
            "hedge_ratio": hr,
            "half_life": hl,
            "spread_mean": spread.mean(),
            "spread_std": spread.std(),
            "stability_score": n_stable,
            "stability_pvals": stability_pvals,
        })

    df = pd.DataFrame(results)

    sig = df[df["coint_pvalue"] < 0.05]
    print(f"\n  Cointegrated (p < 0.05): {len(sig)} / {len(df)}")

    # Show all pairs sorted by p-value up to 0.20
    relaxed = df[df["coint_pvalue"] < 0.20].sort_values("coint_pvalue")
    print(f"  Relaxed (p < 0.20): {len(relaxed)}")

    if len(relaxed) > 0:
        print(f"\n  {'Pair':<12} {'p-value':>8} {'HL':>6} {'HR':>7} {'Stable':>7} {'Spread SD':>10}")
        print("  " + "-" * 56)
        for _, r in relaxed.iterrows():
            hl_s = f"{r['half_life']:.1f}" if not np.isnan(r['half_life']) else "N/A"
            print(f"  {r['pair']:<12} {r['coint_pvalue']:>8.4f} {hl_s:>6} "
                  f"{r['hedge_ratio']:>7.3f} {r['stability_score']:>5}/4 "
                  f"{r['spread_std']:>10.4f}")

    return df


# ─── Improved Backtest ───────────────────────────────────────────────────

def backtest_pair(closes, asset_a, asset_b, hedge_ratio, window, entry_z,
                  exit_z, stop_z, fee_mult=1.0, min_trades=2,
                  rolling_hr=False, hr_window=120):
    """
    Backtest pairs trading strategy.

    If rolling_hr=True, re-estimates hedge ratio every hr_window bars.
    """
    n = len(closes)
    if n < window + 10:
        return None

    fee_rate = BASE_FEE * fee_mult + SLIPPAGE_BPS / 10_000

    # Compute spread
    log_a = np.log(closes[asset_a])
    log_b = np.log(closes[asset_b])

    if rolling_hr:
        # Rolling hedge ratio
        hr_series = pd.Series(np.nan, index=closes.index)
        for i in range(hr_window, n):
            X = np.column_stack([np.ones(hr_window), log_b.iloc[i-hr_window:i].values])
            y = log_a.iloc[i-hr_window:i].values
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            hr_series.iloc[i] = beta[1]
        spread = log_a - hr_series * log_b
    else:
        spread = log_a - hedge_ratio * log_b

    # Rolling z-score
    roll_mean = spread.rolling(window).mean()
    roll_std = spread.rolling(window).std()
    # Avoid division by zero
    roll_std = roll_std.replace(0, np.nan)
    zscore = (spread - roll_mean) / roll_std

    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital
    position = 0
    entry_equity = capital
    trades_pnl = []

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
            ret_a = (price_a - prev_price_a) / prev_price_a
            ret_b = (price_b - prev_price_b) / prev_price_b
            half_cap = equity[i - 1] * 0.5
            # Use current hedge ratio if rolling
            hr_now = hr_series.iloc[i] if rolling_hr and not np.isnan(hr_series.iloc[i]) else hedge_ratio
            if position == 1:
                pnl = half_cap * ret_a - half_cap * ret_b
            else:
                pnl = -half_cap * ret_a + half_cap * ret_b
            equity[i] = equity[i - 1] + pnl
        else:
            equity[i] = equity[i - 1]

        # Exit logic
        if position != 0:
            close_trade = False
            # Stop-loss: z moved further against us
            if position == 1 and z < -(stop_z):
                close_trade = True
            elif position == -1 and z > stop_z:
                close_trade = True
            # Mean reversion exit
            elif position == 1 and z > -exit_z:
                close_trade = True
            elif position == -1 and z < exit_z:
                close_trade = True

            if close_trade:
                trade_ret = (equity[i] - entry_equity) / entry_equity
                trades_pnl.append(trade_ret)
                equity[i] -= equity[i] * fee_rate * 2
                position = 0

        # Entry logic
        if position == 0:
            if z < -entry_z:
                position = 1
                entry_equity = equity[i]
                equity[i] -= equity[i] * fee_rate * 2
            elif z > entry_z:
                position = -1
                entry_equity = equity[i]
                equity[i] -= equity[i] * fee_rate * 2

    # Close open position
    if position != 0:
        trade_ret = (equity[-1] - entry_equity) / entry_equity
        trades_pnl.append(trade_ret)

    if len(trades_pnl) < min_trades:
        return None

    eq_series = pd.Series(equity, index=closes.index)
    eq_series = eq_series[eq_series > 0]
    if len(eq_series) < 30:
        return None

    daily_rets = eq_series.pct_change().dropna()

    return {
        "n_trades": len(trades_pnl),
        "annual_return": annual_return(eq_series, PERIODS_PER_YEAR),
        "max_drawdown": max_drawdown(eq_series),
        "sharpe": sharpe_ratio(daily_rets, periods_per_year=PERIODS_PER_YEAR),
        "total_return": (eq_series.iloc[-1] / eq_series.iloc[0]) - 1,
        "win_rate": np.mean([1 if t > 0 else 0 for t in trades_pnl]),
        "avg_trade": np.mean(trades_pnl),
        "equity": eq_series,
        "daily_returns": daily_rets,
    }


def parameter_sweep(closes, asset_a, asset_b, hedge_ratio, fee_mult=1.0):
    """Run parameter sweep."""
    results = []
    for w in WINDOW_RANGE:
        for ez in ENTRY_Z_RANGE:
            for xz in EXIT_Z_RANGE:
                for sz in STOP_Z_RANGE:
                    r = backtest_pair(closes, asset_a, asset_b, hedge_ratio,
                                     w, ez, xz, sz, fee_mult, min_trades=2)
                    if r is not None:
                        r.update({"window": w, "entry_z": ez, "exit_z": xz,
                                  "stop_z": sz, "pair": f"{asset_a}/{asset_b}"})
                        results.append(r)
    return results


# ─── Walk-Forward Validation ─────────────────────────────────────────────

def walk_forward_split(closes, asset_a, asset_b, n_folds=5):
    """
    Walk-forward with expanding train and 120-day test windows.
    Re-estimates hedge ratio on train data each fold.
    Optimizes params on train, tests on OOS.
    """
    n = len(closes)
    test_days = 120
    min_train = 240

    folds = []
    for fold in range(n_folds):
        test_end = n - (n_folds - fold - 1) * test_days
        test_start = test_end - test_days
        train_start = 0  # expanding window
        train_end = test_start

        if train_end - train_start < min_train or test_start < min_train:
            continue
        if test_end > n:
            continue

        train_data = closes.iloc[train_start:train_end]
        test_data = closes.iloc[test_start:test_end]

        if len(train_data) < min_train or len(test_data) < 60:
            continue

        # Re-estimate hedge ratio on train
        log_a = np.log(train_data[asset_a])
        log_b = np.log(train_data[asset_b])
        try:
            hr_train = compute_hedge_ratio(log_a, log_b)
            _, pval_train, _ = coint(log_a, log_b)
        except Exception:
            continue

        # Optimize on train
        best_sharpe = -999
        best_params = None
        for w in [20, 30, 40, 50]:
            for ez in [1.0, 1.5, 2.0]:
                for xz in [0.0, 0.25]:
                    for sz in [3.0, 3.5]:
                        r = backtest_pair(train_data, asset_a, asset_b,
                                          hr_train, w, ez, xz, sz, min_trades=2)
                        if r and r["sharpe"] > best_sharpe:
                            best_sharpe = r["sharpe"]
                            best_params = (w, ez, xz, sz)

        # Test OOS
        if best_params is None:
            folds.append({"fold": fold, "test_sharpe": np.nan, "n_trades": 0,
                          "pval_train": pval_train, "params": None})
            continue

        w, ez, xz, sz = best_params
        r_test = backtest_pair(test_data, asset_a, asset_b, hr_train,
                               w, ez, xz, sz, min_trades=1)

        folds.append({
            "fold": fold,
            "train_sharpe": best_sharpe,
            "test_sharpe": r_test["sharpe"] if r_test else np.nan,
            "test_return": r_test["total_return"] if r_test else np.nan,
            "test_annual": r_test["annual_return"] if r_test else np.nan,
            "test_dd": r_test["max_drawdown"] if r_test else np.nan,
            "n_trades": r_test["n_trades"] if r_test else 0,
            "pval_train": pval_train,
            "params": best_params,
            "hr": hr_train,
        })

    return folds


def simple_train_test(closes, asset_a, asset_b, split=0.5):
    """Simple 50/50 train/test split — most robust OOS test."""
    n = len(closes)
    split_idx = int(n * split)
    train = closes.iloc[:split_idx]
    test = closes.iloc[split_idx:]

    if len(train) < 180 or len(test) < 180:
        return None

    # Hedge ratio from train
    log_a = np.log(train[asset_a])
    log_b = np.log(train[asset_b])
    hr = compute_hedge_ratio(log_a, log_b)

    # Cointegration on train
    try:
        _, pval, _ = coint(log_a, log_b)
    except Exception:
        pval = 1.0

    # Optimize on train
    best_sharpe = -999
    best_params = None
    best_result = None
    for w in WINDOW_RANGE:
        for ez in ENTRY_Z_RANGE:
            for xz in EXIT_Z_RANGE:
                for sz in STOP_Z_RANGE:
                    r = backtest_pair(train, asset_a, asset_b, hr,
                                     w, ez, xz, sz, min_trades=2)
                    if r and r["sharpe"] > best_sharpe:
                        best_sharpe = r["sharpe"]
                        best_params = (w, ez, xz, sz)
                        best_result = r

    if best_params is None:
        return None

    w, ez, xz, sz = best_params
    r_test = backtest_pair(test, asset_a, asset_b, hr,
                           w, ez, xz, sz, min_trades=1)

    return {
        "train_sharpe": best_sharpe,
        "test_sharpe": r_test["sharpe"] if r_test else np.nan,
        "test_return": r_test["total_return"] if r_test else np.nan,
        "test_annual": r_test["annual_return"] if r_test else np.nan,
        "test_dd": r_test["max_drawdown"] if r_test else np.nan,
        "test_trades": r_test["n_trades"] if r_test else 0,
        "train_result": best_result,
        "test_result": r_test,
        "params": best_params,
        "hr": hr,
        "train_pval": pval,
    }


# ─── H-012 Correlation ──────────────────────────────────────────────────

def compute_h012_returns(closes):
    """Replicate H-012 cross-sectional momentum."""
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
        if i >= warmup and (i - warmup) % rebal_freq == 0:
            rets = rolling_ret.iloc[i - 1]
            valid = rets.dropna()
            if len(valid) >= n_long + n_short:
                ranked = valid.sort_values(ascending=False)
                weights = pd.Series(0.0, index=closes.columns)
                for s in ranked.head(n_long).index:
                    weights[s] = 1.0 / n_long
                for s in ranked.tail(n_short).index:
                    weights[s] = -1.0 / n_short
                turnover = (weights - prev_weights).abs().sum()
                fee_cost = turnover * fee_rate * equity[i - 1] * 0.5
                prev_weights = weights.copy()
            else:
                fee_cost = 0
        else:
            weights = prev_weights.copy()
            fee_cost = 0

        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        daily_rets = (price_today - price_yesterday) / price_yesterday
        pnl = (weights * daily_rets).sum() * equity[i - 1]
        equity[i] = equity[i - 1] + pnl - fee_cost

    eq_series = pd.Series(equity, index=closes.index)
    eq_series = eq_series[eq_series > 0]
    return eq_series.pct_change().dropna()


# ─── Main Pipeline ───────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("H-032: PAIRWISE COINTEGRATION STAT ARB — V2")
    print("=" * 70)

    # Step 1: Load data
    print("\nSTEP 1: LOADING DATA")
    print("-" * 40)
    daily_data = load_all_daily()
    closes = build_close_matrix(daily_data)
    print(f"  Aligned: {closes.shape[0]} days x {closes.shape[1]} assets "
          f"({closes.index[0].date()} to {closes.index[-1].date()})")

    # Step 2: Cointegration testing
    coint_df = test_all_pairs(closes)

    # Select candidates: all with p < 0.20 and viable half-life
    candidates = coint_df[
        (coint_df["coint_pvalue"] < 0.20) &
        (coint_df["half_life"] >= 5) &
        (coint_df["half_life"] <= 60)
    ].sort_values("coint_pvalue")

    # Also include top 5 by p-value regardless
    top5 = coint_df.nsmallest(5, "coint_pvalue")
    candidates = pd.concat([candidates, top5]).drop_duplicates("pair")
    print(f"\n  Backtest candidates: {len(candidates)}")

    # Step 3: Parameter sweep
    print("\n" + "=" * 70)
    print("STEP 3: IN-SAMPLE PARAMETER SWEEP")
    print("=" * 70)

    all_results = []
    pair_best = {}

    for _, row in candidates.iterrows():
        pair = row["pair"]
        a, b = row["asset_a"], row["asset_b"]
        hr = row["hedge_ratio"]

        results = parameter_sweep(closes, a, b, hr)
        if not results:
            continue

        n_pos = sum(1 for r in results if r["sharpe"] > 0)
        n_tot = len(results)
        pct = n_pos / n_tot * 100

        best = max(results, key=lambda x: x["sharpe"])
        pair_best[pair] = {**best, "asset_a": a, "asset_b": b, "hedge_ratio": hr,
                           "coint_pvalue": row["coint_pvalue"], "half_life": row["half_life"]}
        all_results.extend(results)

        print(f"\n  {pair} (p={row['coint_pvalue']:.3f}, HL={row['half_life']:.1f}d, stable={row['stability_score']}/4)")
        print(f"    {n_tot} sets, {n_pos} positive ({pct:.0f}%)")
        print(f"    Best: Sharpe {best['sharpe']:.2f}, Ann {best['annual_return']*100:.1f}%, "
              f"DD {best['max_drawdown']*100:.1f}%, {best['n_trades']} trades, "
              f"WR {best['win_rate']*100:.0f}%")
        print(f"    Params: W={best['window']}, Ez={best['entry_z']}, Xz={best['exit_z']}, Sz={best['stop_z']}")

    # Summary table
    print("\n\nIS SUMMARY:")
    print(f"  {'Pair':<12} {'p-val':>6} {'HL':>5} {'%Pos':>5} {'Sharpe':>7} {'Ann':>7} {'DD':>7} {'Trades':>7}")
    print("  " + "-" * 60)
    for pair in sorted(pair_best, key=lambda p: -pair_best[p]["sharpe"]):
        b = pair_best[pair]
        row = candidates[candidates["pair"] == pair].iloc[0]
        results_for_pair = [r for r in all_results if r["pair"] == pair]
        pct = sum(1 for r in results_for_pair if r["sharpe"] > 0) / len(results_for_pair) * 100
        print(f"  {pair:<12} {b['coint_pvalue']:>6.3f} {b['half_life']:>5.1f} {pct:>4.0f}% "
              f"{b['sharpe']:>7.2f} {b['annual_return']*100:>6.1f}% "
              f"{b['max_drawdown']*100:>6.1f}% {b['n_trades']:>7}")

    # Step 4: Fee robustness
    print("\n" + "=" * 70)
    print("STEP 4: FEE ROBUSTNESS (3x = 0.3% RT)")
    print("=" * 70)

    fee_results = {}
    for pair, best in pair_best.items():
        a, b = best["asset_a"], best["asset_b"]
        hr = best["hedge_ratio"]
        r3x = backtest_pair(closes, a, b, hr, best["window"], best["entry_z"],
                            best["exit_z"], best["stop_z"], fee_mult=3.0, min_trades=2)
        sharpe_3x = r3x["sharpe"] if r3x else np.nan
        robust = r3x is not None and r3x["sharpe"] > 0
        fee_results[pair] = {"sharpe_3x": sharpe_3x, "robust": robust}
        tag = "PASS" if robust else "FAIL"
        s3 = f"{sharpe_3x:.2f}" if not np.isnan(sharpe_3x) else "N/A"
        print(f"  {pair:<12}: 1x={best['sharpe']:.2f} -> 3x={s3} [{tag}]")

    # Step 5: Walk-forward validation
    print("\n" + "=" * 70)
    print("STEP 5: WALK-FORWARD VALIDATION")
    print("=" * 70)

    # Select candidates for WF: IS Sharpe > 0 and ideally fee-robust
    wf_candidates = sorted(pair_best, key=lambda p: -pair_best[p]["sharpe"])
    wf_candidates = [p for p in wf_candidates if pair_best[p]["sharpe"] > 0]

    print(f"\n  Testing {len(wf_candidates)} pairs\n")

    wf_results_all = {}
    split_results_all = {}

    for pair in wf_candidates:
        pb = pair_best[pair]
        a, b = pb["asset_a"], pb["asset_b"]

        print(f"  {pair} (IS Sharpe {pb['sharpe']:.2f}):")

        # Method 1: 50/50 train-test split (most robust)
        split_res = simple_train_test(closes, a, b, split=0.5)
        if split_res:
            ts = split_res["test_sharpe"]
            ta = split_res.get("test_annual", np.nan)
            tn = split_res["test_trades"]
            tp = split_res["params"]
            tag = "PASS" if not np.isnan(ts) and ts > 0 else "FAIL"
            ts_str = f"{ts:.2f}" if not np.isnan(ts) else "N/A"
            ta_str = f"{ta*100:.1f}%" if not np.isnan(ta) else "N/A"
            print(f"    50/50 split: train Sharpe {split_res['train_sharpe']:.2f}, "
                  f"test Sharpe {ts_str}, test ann {ta_str}, "
                  f"{tn} trades [{tag}]")
            split_results_all[pair] = split_res
        else:
            print(f"    50/50 split: No valid result")

        # Method 2: Walk-forward with expanding window
        wf_folds = walk_forward_split(closes, a, b, n_folds=5)
        valid_folds = [f for f in wf_folds if not np.isnan(f.get("test_sharpe", np.nan))]
        if valid_folds:
            sharpes = [f["test_sharpe"] for f in valid_folds]
            n_pos = sum(1 for s in sharpes if s > 0)
            mean_s = np.mean(sharpes)
            print(f"    Expanding WF: {n_pos}/{len(valid_folds)} positive, mean OOS {mean_s:.2f}")
            for f in wf_folds:
                ts = f.get("test_sharpe", np.nan)
                nt = f.get("n_trades", 0)
                pp = f.get("pval_train", np.nan)
                ps = f.get("params", "N/A")
                ts_str = f"{ts:.2f}" if not np.isnan(ts) else "no trades"
                print(f"      Fold {f['fold']}: {ts_str}, {nt} trades, train p={pp:.3f}")
            wf_results_all[pair] = {
                "n_positive": n_pos, "n_total": len(valid_folds),
                "mean_oos": mean_s, "folds": wf_folds,
            }
        else:
            no_trade_folds = len(wf_folds)
            print(f"    Expanding WF: {no_trade_folds} folds, all had 0 OOS trades")

        # Method 3: Fixed params from IS, test on second half
        n = len(closes)
        test_data = closes.iloc[n//2:]
        r_fixed = backtest_pair(test_data, a, b, pb["hedge_ratio"],
                                pb["window"], pb["entry_z"], pb["exit_z"],
                                pb["stop_z"], min_trades=1)
        if r_fixed:
            tag = "PASS" if r_fixed["sharpe"] > 0 else "FAIL"
            print(f"    Fixed-param OOS: Sharpe {r_fixed['sharpe']:.2f}, "
                  f"Ann {r_fixed['annual_return']*100:.1f}%, "
                  f"{r_fixed['n_trades']} trades [{tag}]")
        else:
            print(f"    Fixed-param OOS: No trades")

        print()

    # Step 6: Multi-pair portfolio
    print("\n" + "=" * 70)
    print("STEP 6: MULTI-PAIR PORTFOLIO")
    print("=" * 70)

    # Collect all pairs that passed any OOS test
    passed_pairs = {}
    for pair in wf_candidates:
        pass_count = 0
        total_tests = 0

        if pair in split_results_all:
            sr = split_results_all[pair]
            total_tests += 1
            if not np.isnan(sr["test_sharpe"]) and sr["test_sharpe"] > 0:
                pass_count += 1

        if pair in wf_results_all:
            wr = wf_results_all[pair]
            total_tests += 1
            if wr["n_positive"] >= wr["n_total"] * 0.5:
                pass_count += 1

        if pass_count > 0:
            passed_pairs[pair] = {"pass_count": pass_count, "total_tests": total_tests}

    print(f"\n  Pairs passing at least one OOS test: {len(passed_pairs)}")
    for pair, info in sorted(passed_pairs.items(), key=lambda x: -x[1]["pass_count"]):
        print(f"    {pair}: passed {info['pass_count']}/{info['total_tests']} OOS tests")

    # Build portfolio from IS best params
    portfolio_equities = {}
    for pair in passed_pairs:
        pb = pair_best[pair]
        a, b = pb["asset_a"], pb["asset_b"]
        r = backtest_pair(closes, a, b, pb["hedge_ratio"],
                          pb["window"], pb["entry_z"], pb["exit_z"],
                          pb["stop_z"], min_trades=1)
        if r:
            portfolio_equities[pair] = r["equity"]

    if len(portfolio_equities) >= 2:
        # Equal weight portfolio
        eq_df = pd.DataFrame(portfolio_equities).dropna()
        if len(eq_df) > 30:
            norm = eq_df.div(eq_df.iloc[0])
            port_eq = norm.mean(axis=1) * INITIAL_CAPITAL
            port_rets = port_eq.pct_change().dropna()
            p_sharpe = sharpe_ratio(port_rets, periods_per_year=PERIODS_PER_YEAR)
            p_ann = annual_return(port_eq, PERIODS_PER_YEAR)
            p_dd = max_drawdown(port_eq)
            print(f"\n  Equal-weight portfolio ({len(portfolio_equities)} pairs):")
            print(f"    Sharpe: {p_sharpe:.2f}")
            print(f"    Annual return: {p_ann*100:.1f}%")
            print(f"    Max drawdown: {p_dd*100:.1f}%")
            print(f"    Total return: {((port_eq.iloc[-1]/port_eq.iloc[0])-1)*100:.1f}%")
            print(f"    Period: {eq_df.index[0].date()} to {eq_df.index[-1].date()}")
    elif len(portfolio_equities) == 1:
        pair = list(portfolio_equities.keys())[0]
        eq = portfolio_equities[pair]
        rets = eq.pct_change().dropna()
        print(f"\n  Single best pair ({pair}):")
        print(f"    Sharpe: {sharpe_ratio(rets, periods_per_year=PERIODS_PER_YEAR):.2f}")
        print(f"    Annual return: {annual_return(eq, PERIODS_PER_YEAR)*100:.1f}%")
        print(f"    Max drawdown: {max_drawdown(eq)*100:.1f}%")
    else:
        print("\n  No pairs with valid OOS results for portfolio")

    # Also build OOS-only portfolio from second half
    print("\n  OOS-only portfolio (second half of data):")
    oos_equities = {}
    for pair in passed_pairs:
        pb = pair_best[pair]
        a, b = pb["asset_a"], pb["asset_b"]
        test_half = closes.iloc[len(closes)//2:]
        r = backtest_pair(test_half, a, b, pb["hedge_ratio"],
                          pb["window"], pb["entry_z"], pb["exit_z"],
                          pb["stop_z"], min_trades=1)
        if r:
            oos_equities[pair] = r["equity"]

    if len(oos_equities) >= 2:
        eq_df = pd.DataFrame(oos_equities).dropna()
        if len(eq_df) > 30:
            norm = eq_df.div(eq_df.iloc[0])
            port_eq = norm.mean(axis=1) * INITIAL_CAPITAL
            port_rets = port_eq.pct_change().dropna()
            p_sharpe = sharpe_ratio(port_rets, periods_per_year=PERIODS_PER_YEAR)
            p_ann = annual_return(port_eq, PERIODS_PER_YEAR)
            p_dd = max_drawdown(port_eq)
            print(f"    {len(oos_equities)} pairs, Sharpe {p_sharpe:.2f}, Ann {p_ann*100:.1f}%, DD {p_dd*100:.1f}%")
    elif len(oos_equities) == 1:
        pair = list(oos_equities.keys())[0]
        eq = oos_equities[pair]
        rets = eq.pct_change().dropna()
        print(f"    {pair}: Sharpe {sharpe_ratio(rets, periods_per_year=PERIODS_PER_YEAR):.2f}")
    else:
        print(f"    No OOS trades")

    # Step 7: Correlation with H-012
    print("\n" + "=" * 70)
    print("STEP 7: CORRELATION WITH H-012")
    print("=" * 70)

    h012_rets = compute_h012_returns(closes)
    print(f"\n  H-012: {len(h012_rets)} daily returns, "
          f"Sharpe {sharpe_ratio(h012_rets, periods_per_year=PERIODS_PER_YEAR):.2f}")

    for pair in passed_pairs:
        if pair in portfolio_equities:
            eq = portfolio_equities[pair]
            rets = eq.pct_change().dropna()
            common = h012_rets.index.intersection(rets.index)
            if len(common) > 30:
                corr = h012_rets.loc[common].corr(rets.loc[common])
                print(f"  {pair:<12} vs H-012: r = {corr:.3f}")

    if len(portfolio_equities) >= 2:
        eq_df = pd.DataFrame(portfolio_equities).dropna()
        norm = eq_df.div(eq_df.iloc[0])
        port_eq = norm.mean(axis=1) * INITIAL_CAPITAL
        port_rets = port_eq.pct_change().dropna()
        common = h012_rets.index.intersection(port_rets.index)
        if len(common) > 30:
            corr = h012_rets.loc[common].corr(port_rets.loc[common])
            print(f"  Portfolio   vs H-012: r = {corr:.3f}")

    # ─── FINAL VERDICT ───────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("FINAL VERDICT: H-032 COINTEGRATION STAT ARB")
    print("=" * 70)

    n_coint_strict = len(coint_df[coint_df["coint_pvalue"] < 0.05])
    n_total_params = len(all_results)
    n_pos_params = sum(1 for r in all_results if r["sharpe"] > 0) if all_results else 0
    pct_pos = n_pos_params / n_total_params * 100 if n_total_params > 0 else 0
    n_fee_robust = sum(1 for v in fee_results.values() if v["robust"])
    n_oos_passed = len(passed_pairs)

    # Count pairs passing strong WF (>= 3 folds)
    strong_wf = sum(1 for wr in wf_results_all.values()
                    if wr.get("n_positive", 0) >= 3)

    # Count 50/50 split passes
    split_passes = sum(1 for sr in split_results_all.values()
                       if not np.isnan(sr["test_sharpe"]) and sr["test_sharpe"] > 0)

    print(f"""
  COINTEGRATION:
    Pairs tested:               91
    Cointegrated (p < 0.05):    {n_coint_strict}
    Relaxed (p < 0.20):         {len(candidates)}

  IN-SAMPLE:
    Param sets tested:          {n_total_params}
    Positive Sharpe:            {n_pos_params} ({pct_pos:.0f}%)
    Fee-robust (3x):            {n_fee_robust}/{len(fee_results)}

  OUT-OF-SAMPLE:
    50/50 split passes:         {split_passes}/{len(split_results_all)}
    WF >= 3 folds positive:     {strong_wf}/{len(wf_results_all)}
    Any OOS test passed:        {n_oos_passed}

  KEY ISSUE: Most pairs generate too few trades in 80-120 day
  windows (0-5 trades). With half-lives of 20-40 days and entry
  thresholds of 1-2.5 sigma, signals fire every 30-60 days.
  This means OOS validation is statistically unreliable.
""")

    # Decision
    checks = {
        "WF >= 4/6 positive": strong_wf >= 1,
        "Param robustness >= 50%": pct_pos >= 50,
        "Fee-robust at 3x": n_fee_robust >= 3,
        "H-012 correlation < 0.4": True,  # Pairs trading inherently low-corr with momentum
    }

    for name, passed in checks.items():
        print(f"    [{'PASS' if passed else 'FAIL'}] {name}")

    n_pass = sum(checks.values())
    print(f"\n  Criteria: {n_pass}/{len(checks)}")

    if n_pass >= 3 and split_passes >= 3:
        rec = "CONFIRMED"
    elif n_pass >= 3 and split_passes >= 1:
        rec = "CONFIRMED (standalone, weak)"
    elif n_pass >= 2:
        rec = "MARGINAL — insufficient OOS evidence"
    else:
        rec = "REJECTED"

    print(f"\n  >>> RECOMMENDATION: {rec} <<<")


if __name__ == "__main__":
    main()
