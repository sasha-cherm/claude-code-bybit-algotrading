"""
H-151: Conditional Momentum (BTC Regime Switch) Backtest

Idea:
  Use BTC's SMA as a regime indicator to switch between momentum and contrarian
  strategies on the cross-section of altcoins.

  - BTC UPTREND  (BTC close > SMA(N)):  LONG top M momentum assets, SHORT bottom M
  - BTC DOWNTREND (BTC close < SMA(N)): LONG bottom M momentum assets, SHORT top M

  The hypothesis is that BTC regime determines whether the market is in "trend"
  or "mean-reversion" mode, and the regime switch adds alpha over static momentum.

Validation (all 4 required):
  1. IS: >=60% of params positive Sharpe
  2. WF OOS: >=4/6 positive folds AND mean OOS Sharpe > 0.5
  3. Split-half: Both halves positive Sharpe
  4. Must outperform static momentum by >=0.3 Sharpe on IS
  5. Correlation with static momentum proxy: if >0.40, regime switch not adding enough
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

# ─── Configuration ───────────────────────────────────────────────────────────

ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "AVAX",
    "LINK", "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM", "SUI",
]

DATA_DIR = ROOT / "data"
FEE_RATE = 0.001   # 0.1% per trade (taker fee)
INITIAL_CAPITAL = 10_000.0
PERIODS_PER_YEAR = 365

# Parameter sweep
REGIME_WINDOWS    = [20, 30, 50, 60]
MOMENTUM_LOOKBACKS = [14, 21, 30, 60]
REBALANCE_PERIODS  = [3, 5, 7]
N_POSITIONS        = [3, 4]

WF_FOLDS = 6
WF_TEST_DAYS = 90


# ─── Data Loading ─────────────────────────────────────────────────────────────

def load_daily_closes() -> pd.DataFrame:
    """Load daily close prices for all assets into a single aligned DataFrame."""
    frames = {}
    for asset in ASSETS:
        fpath = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fpath.exists():
            print(f"  WARNING: {fpath} not found, skipping {asset}")
            continue
        df = pd.read_parquet(fpath)
        frames[asset] = df["close"]

    closes = pd.DataFrame(frames)
    closes = closes.sort_index()
    closes = closes.dropna(how="all").ffill().dropna()
    return closes


# ─── Regime Computation ───────────────────────────────────────────────────────

def compute_btc_regime(closes: pd.DataFrame, regime_window: int) -> pd.Series:
    """
    Returns a boolean Series: True = UPTREND (BTC > SMA), False = DOWNTREND.
    Shift by 1 to avoid lookahead (we use yesterday's regime to trade today).
    """
    btc = closes["BTC"]
    sma = btc.rolling(regime_window, min_periods=regime_window).mean()
    regime = (btc > sma)          # True = uptrend
    return regime.shift(1)        # lag 1 day — no lookahead


# ─── Momentum Signal ──────────────────────────────────────────────────────────

def compute_momentum(closes: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    N-day log return for each asset.
    Shift by 1 to avoid lookahead.
    """
    log_ret = np.log(closes / closes.shift(lookback))
    return log_ret.shift(1)       # lag 1 day


# ─── Portfolio Construction ───────────────────────────────────────────────────

def build_positions(
    closes: pd.DataFrame,
    regime_window: int,
    momentum_lookback: int,
    rebalance_period: int,
    n_positions: int,
    conditional: bool = True,
) -> pd.DataFrame:
    """
    Build daily position weights (+1 = long, -1 = short, 0 = flat).
    Each leg is equal-weighted: 1/n_positions each.
    Dollar-neutral: sum of weights = 0.

    conditional: if True, flip positions in downtrend (contrarian mode).
                 if False, always use momentum (static baseline).
    """
    btc_regime = compute_btc_regime(closes, regime_window)
    mom = compute_momentum(closes, momentum_lookback)

    n_assets = len(closes.columns)
    positions = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)

    # We rebalance every `rebalance_period` days
    # Determine which days are rebalance days
    valid_idx = mom.dropna(how="all").index

    # Need at least regime_window + momentum_lookback days of warm-up
    warmup = max(regime_window, momentum_lookback) + 2

    prev_weights = None
    active_positions = pd.Series(0.0, index=closes.columns)

    for i, date in enumerate(closes.index):
        if i < warmup:
            continue

        # Rebalance on the first valid day and then every rebalance_period days
        days_since_start = i - warmup
        if days_since_start % rebalance_period != 0:
            # Keep previous positions
            positions.loc[date] = active_positions
            continue

        # Get regime for today (already shifted, so this is yesterday's regime)
        regime_today = btc_regime.loc[date]
        if pd.isna(regime_today):
            positions.loc[date] = active_positions
            continue

        # Get momentum signals for today (already shifted)
        mom_today = mom.loc[date].dropna()
        if len(mom_today) < n_positions * 2:
            positions.loc[date] = active_positions
            continue

        # Rank assets by momentum
        ranked = mom_today.rank(ascending=True)  # 1 = lowest momentum
        n_valid = len(ranked)
        n_pos = min(n_positions, n_valid // 3)   # safety guard

        if n_pos < 1:
            positions.loc[date] = active_positions
            continue

        # Top and bottom ranks
        top_assets = ranked.nlargest(n_pos).index.tolist()
        bot_assets = ranked.nsmallest(n_pos).index.tolist()

        new_weights = pd.Series(0.0, index=closes.columns)

        if conditional:
            if regime_today:
                # UPTREND: momentum — long top, short bottom
                new_weights[top_assets] = 1.0 / n_pos
                new_weights[bot_assets] = -1.0 / n_pos
            else:
                # DOWNTREND: contrarian — long bottom (beaten down), short top
                new_weights[bot_assets] = 1.0 / n_pos
                new_weights[top_assets] = -1.0 / n_pos
        else:
            # Static momentum: always long top, short bottom
            new_weights[top_assets] = 1.0 / n_pos
            new_weights[bot_assets] = -1.0 / n_pos

        active_positions = new_weights
        positions.loc[date] = active_positions

    return positions


# ─── Backtest Engine ──────────────────────────────────────────────────────────

def run_backtest(
    closes: pd.DataFrame,
    positions: pd.DataFrame,
    fee_rate: float = FEE_RATE,
) -> pd.Series:
    """
    Simulate PnL from position weights and close prices.

    Returns:
        Daily strategy returns series (fraction, not equity curve).
    """
    # Daily log returns of each asset
    asset_returns = closes.pct_change()

    # Strategy gross returns: sum(weight_i * return_i) each day
    gross_returns = (positions.shift(1) * asset_returns).sum(axis=1)

    # Transaction costs: proportional to position changes (turnover)
    turnover = positions.diff().abs().sum(axis=1) / 2.0   # one-way turnover
    costs = turnover * fee_rate

    net_returns = gross_returns - costs

    return net_returns


def equity_curve(returns: pd.Series, initial: float = INITIAL_CAPITAL) -> pd.Series:
    """Convert returns to equity curve, dropping leading NaN/zeros."""
    returns = returns.dropna()
    # Trim leading zeros (warm-up period)
    first_nonzero = (returns != 0).idxmax()
    returns = returns.loc[first_nonzero:]
    return initial * (1 + returns).cumprod()


# ─── Performance Metrics ──────────────────────────────────────────────────────

def compute_metrics(returns: pd.Series) -> dict:
    """Compute key metrics from a returns series."""
    returns = returns.dropna()
    returns = returns[returns != 0]
    if len(returns) < 10:
        return {"sharpe": np.nan, "annual_ret": np.nan, "max_dd": np.nan, "n_days": 0}

    eq = INITIAL_CAPITAL * (1 + returns).cumprod()
    sharpe = sharpe_ratio(returns, periods_per_year=PERIODS_PER_YEAR)
    ann_ret = annual_return(eq, periods_per_year=PERIODS_PER_YEAR)
    mdd = max_drawdown(eq)
    return {
        "sharpe": round(sharpe, 4),
        "annual_ret": round(ann_ret, 4),
        "max_dd": round(mdd, 4),
        "n_days": len(returns),
    }


# ─── Walk-Forward ────────────────────────────────────────────────────────────

def walk_forward(
    closes: pd.DataFrame,
    regime_window: int,
    momentum_lookback: int,
    rebalance_period: int,
    n_positions: int,
    n_folds: int = WF_FOLDS,
    test_days: int = WF_TEST_DAYS,
    conditional: bool = True,
) -> list[dict]:
    """
    Rolling walk-forward validation.
    Train on all data up to the start of each test fold.
    Test on the next `test_days` days.
    """
    warmup = max(regime_window, momentum_lookback) + 5
    min_train = warmup + 20

    dates = closes.index
    n_total = len(dates)

    # Determine fold start points (from the end, going backward)
    fold_results = []
    total_test = n_folds * test_days
    if total_test >= n_total - min_train:
        # Not enough data — reduce fold count
        n_folds = max(2, (n_total - min_train) // test_days)

    for fold in range(n_folds):
        test_end_i = n_total - fold * test_days
        test_start_i = test_end_i - test_days
        if test_start_i < min_train:
            break

        test_slice = closes.iloc[test_start_i:test_end_i]

        # Build positions using ONLY data up to test period (no future data)
        # We compute over the full slice but evaluate only on test portion
        train_slice = closes.iloc[:test_end_i]

        positions = build_positions(
            train_slice, regime_window, momentum_lookback,
            rebalance_period, n_positions, conditional=conditional
        )
        # Extract test-period positions and returns
        test_positions = positions.loc[test_slice.index]
        test_returns = run_backtest(test_slice, test_positions)

        metrics = compute_metrics(test_returns)
        metrics["fold"] = n_folds - fold  # fold 1 is oldest
        metrics["start"] = str(test_slice.index[0].date())
        metrics["end"]   = str(test_slice.index[-1].date())
        fold_results.append(metrics)

    fold_results.sort(key=lambda x: x["fold"])
    return fold_results


# ─── H-019 Low-Vol Proxy ──────────────────────────────────────────────────────

def compute_lowvol_returns(closes: pd.DataFrame, lookback: int = 20, n_pos: int = 4) -> pd.Series:
    """
    H-019 proxy: rank assets by 20-day realized vol.
    Long lowest vol, short highest vol.
    Rebalance every 5 days.
    """
    log_ret = np.log(closes / closes.shift(1))
    rolling_vol = log_ret.rolling(lookback, min_periods=lookback).std()
    rolling_vol_lag = rolling_vol.shift(1)

    positions = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    warmup = lookback + 5

    active_pos = pd.Series(0.0, index=closes.columns)
    for i, date in enumerate(closes.index):
        if i < warmup:
            continue
        if (i - warmup) % 5 == 0:
            vols_today = rolling_vol_lag.loc[date].dropna()
            if len(vols_today) < n_pos * 2:
                positions.loc[date] = active_pos
                continue
            ranked = vols_today.rank(ascending=True)
            low_vol = ranked.nsmallest(n_pos).index.tolist()
            high_vol = ranked.nlargest(n_pos).index.tolist()
            new_pos = pd.Series(0.0, index=closes.columns)
            new_pos[low_vol]  =  1.0 / n_pos
            new_pos[high_vol] = -1.0 / n_pos
            active_pos = new_pos
        positions.loc[date] = active_pos

    returns = run_backtest(closes, positions)
    return returns


# ─── Full Backtest Pipeline ────────────────────────────────────────────────────

def run_full_backtest():
    print("=" * 70)
    print("H-151: Conditional Momentum (BTC Regime Switch) — Backtest")
    print("=" * 70)

    # Load data
    print("\nLoading data...")
    closes = load_daily_closes()
    print(f"  Loaded {len(closes)} daily bars, {len(closes.columns)} assets")
    print(f"  Date range: {closes.index[0].date()} → {closes.index[-1].date()}")
    print(f"  Assets: {', '.join(closes.columns.tolist())}")

    all_params = list(product(REGIME_WINDOWS, MOMENTUM_LOOKBACKS, REBALANCE_PERIODS, N_POSITIONS))
    print(f"\nParameter sweep: {len(all_params)} combinations")
    print(f"  regime_window: {REGIME_WINDOWS}")
    print(f"  momentum_lookback: {MOMENTUM_LOOKBACKS}")
    print(f"  rebalance_period: {REBALANCE_PERIODS}")
    print(f"  n_positions: {N_POSITIONS}")

    # ─── IS Sweep ────────────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("IN-SAMPLE PARAMETER SWEEP")
    print("─" * 70)

    cond_is_results = []
    static_is_results = []

    for rw, ml, rp, np_ in all_params:
        # Conditional
        pos_cond = build_positions(closes, rw, ml, rp, np_, conditional=True)
        ret_cond = run_backtest(closes, pos_cond)
        m_cond = compute_metrics(ret_cond)
        m_cond.update({"regime_window": rw, "momentum_lookback": ml,
                       "rebalance_period": rp, "n_positions": np_})
        cond_is_results.append(m_cond)

        # Static momentum (same params, no regime switch)
        pos_static = build_positions(closes, rw, ml, rp, np_, conditional=False)
        ret_static = run_backtest(closes, pos_static)
        m_static = compute_metrics(ret_static)
        m_static.update({"regime_window": rw, "momentum_lookback": ml,
                         "rebalance_period": rp, "n_positions": np_})
        static_is_results.append(m_static)

    cond_df   = pd.DataFrame(cond_is_results)
    static_df = pd.DataFrame(static_is_results)

    valid_cond   = cond_df.dropna(subset=["sharpe"])
    valid_static = static_df.dropna(subset=["sharpe"])

    n_total = len(valid_cond)
    n_pos_cond   = (valid_cond["sharpe"] > 0).sum()
    n_pos_static = (valid_static["sharpe"] > 0).sum()
    pct_pos_cond   = n_pos_cond / n_total * 100
    pct_pos_static = n_pos_static / n_total * 100

    print(f"\nConditional momentum:")
    print(f"  % positive Sharpe : {n_pos_cond}/{n_total} = {pct_pos_cond:.1f}%")
    print(f"  Mean Sharpe       : {valid_cond['sharpe'].mean():.4f}")
    print(f"  Median Sharpe     : {valid_cond['sharpe'].median():.4f}")
    print(f"  Mean annual return: {valid_cond['annual_ret'].mean():.2%}")
    print(f"  Mean max drawdown : {valid_cond['max_dd'].mean():.2%}")

    print(f"\nStatic momentum (baseline):")
    print(f"  % positive Sharpe : {n_pos_static}/{n_total} = {pct_pos_static:.1f}%")
    print(f"  Mean Sharpe       : {valid_static['sharpe'].mean():.4f}")
    print(f"  Median Sharpe     : {valid_static['sharpe'].median():.4f}")
    print(f"  Mean annual return: {valid_static['annual_ret'].mean():.2%}")
    print(f"  Mean max drawdown : {valid_static['max_dd'].mean():.2%}")

    cond_mean_sharpe   = valid_cond["sharpe"].mean()
    static_mean_sharpe = valid_static["sharpe"].mean()
    sharpe_improvement = cond_mean_sharpe - static_mean_sharpe
    print(f"\nImprovement from regime switch:")
    print(f"  Sharpe delta (cond - static): {sharpe_improvement:+.4f}")
    print(f"  {'PASS' if sharpe_improvement >= 0.3 else 'FAIL'} — threshold >=+0.30")

    # Best IS params for conditional
    best_row = valid_cond.loc[valid_cond["sharpe"].idxmax()]
    best_params = {
        "regime_window":     int(best_row["regime_window"]),
        "momentum_lookback": int(best_row["momentum_lookback"]),
        "rebalance_period":  int(best_row["rebalance_period"]),
        "n_positions":       int(best_row["n_positions"]),
    }
    print(f"\nBest IS params (conditional): {best_params}")
    print(f"  Best IS Sharpe: {best_row['sharpe']:.4f}")
    print(f"  Best IS annual return: {best_row['annual_ret']:.2%}")
    print(f"  Best IS max drawdown: {best_row['max_dd']:.2%}")

    # ─── Walk-Forward Validation ──────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("WALK-FORWARD OOS (6 FOLDS × 90 DAYS)")
    print("─" * 70)

    wf_cond   = walk_forward(closes, conditional=True,  **best_params)
    wf_static = walk_forward(closes, conditional=False, **best_params)

    print(f"\n{'Fold':<6} {'Period':<25} {'Cond Sharpe':>12} {'Static Sharpe':>14} {'Cond Ann%':>10} {'Cond MDD%':>10}")
    print("-" * 80)
    for fc, fs in zip(wf_cond, wf_static):
        period = f"{fc['start']} → {fc['end']}"
        print(f"  {fc['fold']:<4} {period:<25} {fc['sharpe']:>12.4f} {fs['sharpe']:>14.4f} "
              f"{fc['annual_ret']:>9.1%} {fc['max_dd']:>9.1%}")

    wf_sharpes = [f["sharpe"] for f in wf_cond if not np.isnan(f["sharpe"])]
    n_positive_folds = sum(1 for s in wf_sharpes if s > 0)
    mean_wf_sharpe = np.mean(wf_sharpes)

    print(f"\nWF OOS summary:")
    print(f"  Positive folds   : {n_positive_folds}/{len(wf_sharpes)}")
    print(f"  Mean OOS Sharpe  : {mean_wf_sharpe:.4f}")
    print(f"  Criterion 1: {n_positive_folds}/{len(wf_sharpes)} positive folds — "
          f"{'PASS' if n_positive_folds >= 4 else 'FAIL'} (need >=4)")
    print(f"  Criterion 2: mean OOS Sharpe {mean_wf_sharpe:.4f} — "
          f"{'PASS' if mean_wf_sharpe > 0.5 else 'FAIL'} (need >0.5)")

    # ─── Split-Half ───────────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("SPLIT-HALF VALIDATION")
    print("─" * 70)

    n = len(closes)
    mid = n // 2
    first_half  = closes.iloc[:mid]
    second_half = closes.iloc[mid:]

    pos_h1_cond = build_positions(first_half,  conditional=True,  **best_params)
    pos_h2_cond = build_positions(second_half, conditional=True,  **best_params)
    pos_h1_stat = build_positions(first_half,  conditional=False, **best_params)
    pos_h2_stat = build_positions(second_half, conditional=False, **best_params)

    ret_h1_cond = run_backtest(first_half,  pos_h1_cond)
    ret_h2_cond = run_backtest(second_half, pos_h2_cond)
    ret_h1_stat = run_backtest(first_half,  pos_h1_stat)
    ret_h2_stat = run_backtest(second_half, pos_h2_stat)

    m_h1_cond = compute_metrics(ret_h1_cond)
    m_h2_cond = compute_metrics(ret_h2_cond)
    m_h1_stat = compute_metrics(ret_h1_stat)
    m_h2_stat = compute_metrics(ret_h2_stat)

    print(f"\n  {'Period':<20} {'Cond Sharpe':>12} {'Cond Ann%':>10} {'Cond MDD%':>10} {'Static Sharpe':>14}")
    print(f"  {'First half':<20} {m_h1_cond['sharpe']:>12.4f} {m_h1_cond['annual_ret']:>9.1%} "
          f"{m_h1_cond['max_dd']:>9.1%} {m_h1_stat['sharpe']:>14.4f}")
    print(f"  {'Second half':<20} {m_h2_cond['sharpe']:>12.4f} {m_h2_cond['annual_ret']:>9.1%} "
          f"{m_h2_cond['max_dd']:>9.1%} {m_h2_stat['sharpe']:>14.4f}")

    sh_pass = m_h1_cond["sharpe"] > 0 and m_h2_cond["sharpe"] > 0
    print(f"\n  Split-half: {'PASS' if sh_pass else 'FAIL'} — "
          f"both halves need positive Sharpe")

    # ─── Correlation Analysis ─────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("CORRELATION ANALYSIS")
    print("─" * 70)

    # Build full-period returns for correlation
    pos_cond_best = build_positions(closes, conditional=True,  **best_params)
    pos_stat_best = build_positions(closes, conditional=False, **best_params)
    ret_cond_best   = run_backtest(closes, pos_cond_best).dropna()
    ret_static_best = run_backtest(closes, pos_stat_best).dropna()
    ret_lowvol      = compute_lowvol_returns(closes, lookback=20, n_pos=best_params["n_positions"]).dropna()

    # Align on common index
    common_idx = ret_cond_best.index.intersection(ret_static_best.index).intersection(ret_lowvol.index)
    r_cond   = ret_cond_best.loc[common_idx]
    r_static = ret_static_best.loc[common_idx]
    r_lv     = ret_lowvol.loc[common_idx]

    # Filter to non-zero days
    active = (r_cond != 0) | (r_static != 0) | (r_lv != 0)
    r_cond   = r_cond[active]
    r_static = r_static[active]
    r_lv     = r_lv[active]

    corr_static = r_cond.corr(r_static)
    corr_lowvol = r_cond.corr(r_lv)
    corr_sl     = r_static.corr(r_lv)

    print(f"\n  Correlation: conditional vs static momentum : {corr_static:.4f}")
    print(f"  Correlation: conditional vs H-019 low-vol   : {corr_lowvol:.4f}")
    print(f"  Correlation: static momentum vs H-019 low-vol: {corr_sl:.4f}")
    print(f"\n  Criterion: corr(cond, static) <= 0.40 — "
          f"{'PASS' if corr_static <= 0.40 else 'FAIL'} (corr={corr_static:.4f})")

    # ─── Regime Analysis ─────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("REGIME ANALYSIS")
    print("─" * 70)

    btc_regime = compute_btc_regime(closes, best_params["regime_window"])
    uptrend_days   = btc_regime.sum()
    downtrend_days = (~btc_regime.fillna(True)).sum()
    total_valid    = btc_regime.dropna().shape[0]
    print(f"\n  Regime window: {best_params['regime_window']}-day SMA")
    print(f"  Uptrend days  : {uptrend_days} ({100*uptrend_days/total_valid:.1f}%)")
    print(f"  Downtrend days: {downtrend_days} ({100*downtrend_days/total_valid:.1f}%)")

    # Performance split by regime
    cond_returns_full = run_backtest(closes, pos_cond_best)
    regime_aligned = btc_regime.reindex(cond_returns_full.index)

    up_rets   = cond_returns_full[regime_aligned == True].dropna()
    down_rets = cond_returns_full[regime_aligned == False].dropna()
    up_rets   = up_rets[up_rets != 0]
    down_rets = down_rets[down_rets != 0]

    if len(up_rets) > 5:
        up_sharpe = sharpe_ratio(up_rets, periods_per_year=PERIODS_PER_YEAR)
        print(f"  Sharpe in UPTREND (momentum leg)   : {up_sharpe:.4f}  (n={len(up_rets)})")
    if len(down_rets) > 5:
        down_sharpe = sharpe_ratio(down_rets, periods_per_year=PERIODS_PER_YEAR)
        print(f"  Sharpe in DOWNTREND (reversal leg) : {down_sharpe:.4f}  (n={len(down_rets)})")

    # ─── Verdict ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    c1 = pct_pos_cond >= 60.0
    c2a = n_positive_folds >= 4
    c2b = mean_wf_sharpe > 0.5
    c3  = sh_pass
    c4  = sharpe_improvement >= 0.3
    c5  = corr_static <= 0.40    # lower is better

    print(f"\n  C1: IS >=60% params positive Sharpe: "
          f"{'PASS' if c1 else 'FAIL'}  ({pct_pos_cond:.1f}%)")
    print(f"  C2a: WF >=4/6 positive folds:         "
          f"{'PASS' if c2a else 'FAIL'}  ({n_positive_folds}/6)")
    print(f"  C2b: WF mean OOS Sharpe >0.5:         "
          f"{'PASS' if c2b else 'FAIL'}  ({mean_wf_sharpe:.4f})")
    print(f"  C3: Split-half both positive:          "
          f"{'PASS' if c3 else 'FAIL'}  ({m_h1_cond['sharpe']:.4f} / {m_h2_cond['sharpe']:.4f})")
    print(f"  C4: Outperforms static by >=0.3 Sharpe:"
          f"{'PASS' if c4 else 'FAIL'}  ({sharpe_improvement:+.4f})")
    print(f"  C5: Corr with static <=0.40:           "
          f"{'PASS' if c5 else 'FAIL'}  ({corr_static:.4f})")

    all_pass = c1 and c2a and c2b and c3 and c4
    verdict  = "CONFIRMED" if all_pass else "REJECTED"
    n_pass   = sum([c1, c2a, c2b, c3, c4])

    print(f"\n  {n_pass}/5 required criteria met")
    print(f"\n  *** H-151: {verdict} ***")

    if not all_pass:
        reasons = []
        if not c1:  reasons.append(f"IS param stability weak ({pct_pos_cond:.1f}% positive, need >=60%)")
        if not c2a: reasons.append(f"WF only {n_positive_folds}/6 positive folds (need >=4)")
        if not c2b: reasons.append(f"WF mean OOS Sharpe {mean_wf_sharpe:.4f} (need >0.5)")
        if not c3:  reasons.append("Split-half fails")
        if not c4:  reasons.append(f"Regime switch adds only {sharpe_improvement:+.4f} Sharpe (need >=+0.30)")
        print(f"  Rejection reasons:")
        for r in reasons:
            print(f"    - {r}")
    else:
        print(f"  All 5 criteria met. Strategy adds differentiated value over static momentum.")

    if not c5:
        print(f"\n  NOTE: High correlation with static momentum ({corr_static:.4f} > 0.40).")
        print(f"  Regime switch not sufficiently differentiating from H-012.")

    # ─── Save Results ─────────────────────────────────────────────────────────
    results = {
        "hypothesis": "H-151",
        "verdict": verdict,
        "best_params": best_params,
        "is": {
            "conditional_mean_sharpe": round(float(cond_mean_sharpe), 4),
            "static_mean_sharpe":      round(float(static_mean_sharpe), 4),
            "sharpe_improvement":      round(float(sharpe_improvement), 4),
            "pct_positive_params":     round(float(pct_pos_cond), 2),
            "conditional_mean_annual_ret": round(float(valid_cond["annual_ret"].mean()), 4),
            "conditional_mean_max_dd":     round(float(valid_cond["max_dd"].mean()), 4),
            "best_sharpe":  round(float(best_row["sharpe"]), 4),
            "best_ann_ret": round(float(best_row["annual_ret"]), 4),
            "best_max_dd":  round(float(best_row["max_dd"]), 4),
        },
        "walk_forward": {
            "folds": wf_cond,
            "n_positive_folds": n_positive_folds,
            "mean_oos_sharpe":  round(float(mean_wf_sharpe), 4),
        },
        "split_half": {
            "first_half":  m_h1_cond,
            "second_half": m_h2_cond,
            "pass": bool(sh_pass),
        },
        "correlations": {
            "cond_vs_static":  round(float(corr_static), 4),
            "cond_vs_lowvol":  round(float(corr_lowvol), 4),
            "static_vs_lowvol":round(float(corr_sl), 4),
        },
        "criteria": {
            "c1_is_stability": bool(c1),
            "c2a_wf_folds":    bool(c2a),
            "c2b_wf_sharpe":   bool(c2b),
            "c3_split_half":   bool(c3),
            "c4_outperforms_static": bool(c4),
            "c5_low_correlation":    bool(c5),
        },
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    return results


if __name__ == "__main__":
    run_full_backtest()
