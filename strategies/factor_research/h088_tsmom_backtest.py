"""
H-088: Time-Series Momentum (TSMOM) Portfolio

Unlike cross-sectional momentum (H-012) which ranks assets relative to each other,
TSMOM trades each asset based on its OWN past return:
  - If L-day return > 0: long  (+1/14 weight)
  - If L-day return <= 0: short (-1/14 weight)
Rebalance every R days.

The portfolio CAN be net directional (up to fully long or fully short all 14 assets).
This is a feature — it captures market-wide trends.

Two variants:
  1. Equal-weight TSMOM:  each position = 1/14
  2. Vol-scaled TSMOM:    weight_i = (1 / vol_i) / sum(1 / vol_j) * sign_i
     (inverse 30-day realized vol scaling — gives less weight to volatile assets)

Validation:
  - Full parameter scan: L in [10, 20, 40, 60], R in [1, 3, 5]
  - Walk-forward: 6 folds, 120d train / 90d test
  - 70/30 train/test split
  - Correlation with H-012 (cross-sectional momentum) and H-009 (BTC trend)
  - Net exposure analysis (how often fully long vs fully short)
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

FEE_RATE = 0.0005           # 5 bps per side = 10 bps round-trip (0.1% total)
INITIAL_CAPITAL = 10_000.0

# Parameter grid
LOOKBACKS = [10, 20, 40, 60]     # L: momentum lookback in days
REBAL_FREQS = [1, 3, 5]         # R: rebalance every R days

VOL_WINDOW = 30                  # realized vol lookback for vol-scaled variant

# Walk-forward config
WF_FOLDS = 6
WF_TRAIN = 120
WF_TEST = 90
WF_STEP = 90


# ===========================================================================
# Data Loading
# ===========================================================================

def load_daily_data():
    """Load daily parquet data for all 14 assets."""
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
            else:
                print(f"  {sym}: only {len(df)} bars, skipping")
        else:
            print(f"  {sym}: no data found at {path}")
    return daily


def build_panels(daily):
    """Build aligned closes panel from daily data dict."""
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    return closes


# ===========================================================================
# Metrics helper
# ===========================================================================

def compute_metrics(equity_series):
    """Compute standard metrics from equity curve."""
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe_365": -99, "sharpe_8760": -99, "annual_ret": 0,
                "max_dd": 1.0, "win_rate": 0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    return {
        "sharpe_365": round(sharpe_ratio(rets, periods_per_year=365), 3),
        "sharpe_8760": round(sharpe_ratio(rets, periods_per_year=8760), 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "win_rate": round(n_pos / n_total, 4) if n_total > 0 else 0,
    }


# ===========================================================================
# TSMOM Backtest Engine
# ===========================================================================

def run_tsmom(closes, lookback, rebal_freq, variant="equal", warmup=None,
              return_exposure=False):
    """
    Run time-series momentum backtest.

    For each asset on each rebalance day:
      signal_i = +1 if close_today / close_{today-lookback} - 1 > 0 else -1

    Variant "equal":
      weight_i = signal_i / N_assets

    Variant "volscaled":
      inv_vol_i = 1 / realized_vol_i(30d)
      weight_i = signal_i * inv_vol_i / sum(inv_vol_j)  (normalized to sum |w| = 1)

    Returns: dict with metrics + equity series
    """
    if warmup is None:
        warmup = max(lookback, VOL_WINDOW) + 5

    N = len(closes)
    n_assets = len(closes.columns)
    capital = INITIAL_CAPITAL
    equity = np.zeros(N)
    equity[0] = capital

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count = 0

    # Track net exposure over time for analysis
    net_exposures = []

    for i in range(1, N):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            # Compute momentum signals using t-1 data (no look-ahead)
            if i - 1 < lookback:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            past_price = closes.iloc[i - 1 - lookback]
            current_price = closes.iloc[i - 1]
            mom_returns = (current_price / past_price) - 1.0

            # Generate signals: +1 if positive, -1 if negative/zero
            signals = pd.Series(0.0, index=closes.columns)
            for sym in closes.columns:
                if pd.notna(mom_returns[sym]):
                    signals[sym] = 1.0 if mom_returns[sym] > 0 else -1.0

            valid_count = (signals != 0).sum()
            if valid_count == 0:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            if variant == "equal":
                # Equal weight: 1/N per asset
                new_weights = signals / n_assets

            elif variant == "volscaled":
                # Vol-scaled: inverse of 30d realized vol
                vol_start = max(0, i - 1 - VOL_WINDOW)
                recent_rets = np.log(closes.iloc[vol_start:i] /
                                     closes.iloc[vol_start:i].shift(1)).dropna()
                if len(recent_rets) < 10:
                    new_weights = signals / n_assets
                else:
                    realized_vol = recent_rets.std()
                    # Replace zero/nan vols with median to avoid division issues
                    median_vol = realized_vol[realized_vol > 0].median()
                    realized_vol = realized_vol.replace(0, median_vol).fillna(median_vol)

                    inv_vol = 1.0 / realized_vol
                    # Multiply by signal direction
                    raw_weights = signals * inv_vol
                    # Normalize so sum of |weights| = 1
                    abs_sum = raw_weights.abs().sum()
                    if abs_sum > 0:
                        new_weights = raw_weights / abs_sum
                    else:
                        new_weights = signals / n_assets
            else:
                raise ValueError(f"Unknown variant: {variant}")

            # Compute turnover and fees
            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * FEE_RATE * 2  # both sides

            port_ret = (new_weights * log_rets).sum() - fee_drag

            total_trades += int((weight_changes > 0.001).sum())
            rebal_count += 1
            prev_weights = new_weights

            # Track net exposure
            net_exp = new_weights.sum()
            net_exposures.append({"day": i, "net_exposure": float(net_exp)})
        else:
            # Hold existing positions
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"] = eq_series
    metrics["variant"] = variant

    if return_exposure and net_exposures:
        exp_df = pd.DataFrame(net_exposures)
        metrics["net_exposures"] = exp_df
        metrics["mean_net_exposure"] = round(exp_df["net_exposure"].mean(), 3)
        metrics["std_net_exposure"] = round(exp_df["net_exposure"].std(), 3)
        metrics["pct_fully_long"] = round(
            (exp_df["net_exposure"] > 0.9).mean(), 3)
        metrics["pct_fully_short"] = round(
            (exp_df["net_exposure"] < -0.9).mean(), 3)
        metrics["pct_net_long"] = round(
            (exp_df["net_exposure"] > 0).mean(), 3)
        metrics["pct_net_short"] = round(
            (exp_df["net_exposure"] <= 0).mean(), 3)

    return metrics


# ===========================================================================
# Full Parameter Scan
# ===========================================================================

def run_full_scan(closes, variant="equal"):
    """Run all parameter combinations on the full period."""
    print(f"\n{'=' * 70}")
    print(f"H-088: TSMOM PORTFOLIO -- Full Scan ({variant.upper()} variant)")
    print("=" * 70)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee: {FEE_RATE*10000:.0f} bps per side ({FEE_RATE*2*10000:.0f} bps round-trip)")

    results = []
    for lookback, rebal in product(LOOKBACKS, REBAL_FREQS):
        warmup = max(lookback, VOL_WINDOW) + 5
        res = run_tsmom(closes, lookback, rebal, variant=variant,
                        warmup=warmup, return_exposure=True)
        tag = f"L{lookback}_R{rebal}"
        results.append({
            "tag": tag,
            "lookback": lookback,
            "rebal": rebal,
            "sharpe_365": res["sharpe_365"],
            "sharpe_8760": res["sharpe_8760"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
            "n_rebalances": res["n_rebalances"],
            "mean_net_exp": res.get("mean_net_exposure", 0),
            "pct_net_long": res.get("pct_net_long", 0),
            "pct_fully_long": res.get("pct_fully_long", 0),
            "pct_fully_short": res.get("pct_fully_short", 0),
        })

    df = pd.DataFrame(results)
    positive = df[df["sharpe_365"] > 0]
    print(f"\n  Total parameter combos: {len(df)}")
    print(f"  Positive Sharpe(365): {len(positive)}/{len(df)} "
          f"({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe(365): {df['sharpe_365'].mean():.3f}")
    print(f"  Median Sharpe(365): {df['sharpe_365'].median():.3f}")
    print(f"  Best Sharpe(365): {df['sharpe_365'].max():.3f}")
    print(f"  Worst Sharpe(365): {df['sharpe_365'].min():.3f}")

    print(f"\n  All results sorted by Sharpe(365):")
    for _, row in df.sort_values("sharpe_365", ascending=False).iterrows():
        marker = "**" if row["sharpe_365"] > 0.5 else "  "
        print(f"  {marker} {row['tag']}: "
              f"Sharpe(365)={row['sharpe_365']:.3f}, "
              f"Sharpe(8760)={row['sharpe_8760']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"WR {row['win_rate']:.1%}, "
              f"NetExp={row['mean_net_exp']:+.2f}, "
              f"Long%={row['pct_net_long']:.0%}")

    return df


# ===========================================================================
# Walk-Forward Validation (6 folds, 120d train / 90d test)
# ===========================================================================

def run_walk_forward(closes, variant="equal"):
    """
    Walk-forward with in-sample parameter selection.
    For each fold, find best (L, R) on train set, evaluate on test set.
    """
    print(f"\n{'=' * 70}")
    print(f"WALK-FORWARD VALIDATION ({variant.upper()})")
    print(f"  Config: {WF_FOLDS} folds, {WF_TRAIN}d train, {WF_TEST}d test, "
          f"{WF_STEP}d step")
    print("=" * 70)

    N = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx = N - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST
        train_start_idx = test_start_idx - WF_TRAIN

        if train_start_idx < 0 or test_start_idx < 0:
            print(f"  Fold {fold+1}: insufficient data, skipping")
            break

        train_closes = closes.iloc[train_start_idx:test_start_idx]
        test_closes = closes.iloc[test_start_idx:test_end_idx]

        if len(test_closes) < 30 or len(train_closes) < 60:
            print(f"  Fold {fold+1}: periods too short, skipping")
            break

        # Step 1: find best params on train set
        best_sharpe = -999
        best_params = None
        for lookback, rebal in product(LOOKBACKS, REBAL_FREQS):
            warmup = max(lookback, VOL_WINDOW) + 5
            if warmup >= len(train_closes) - 30:
                continue
            res = run_tsmom(train_closes, lookback, rebal, variant=variant,
                            warmup=warmup)
            if res["sharpe_365"] > best_sharpe:
                best_sharpe = res["sharpe_365"]
                best_params = (lookback, rebal)

        if best_params is None:
            print(f"  Fold {fold+1}: no valid params found")
            break

        # Step 2: evaluate on test set
        lookback, rebal = best_params
        warmup = min(max(lookback, VOL_WINDOW) + 5, len(test_closes) // 2)
        res_test = run_tsmom(test_closes, lookback, rebal, variant=variant,
                             warmup=warmup, return_exposure=True)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "train_best": f"L{lookback}_R{rebal}",
            "train_sharpe": round(best_sharpe, 3),
            "oos_sharpe_365": res_test["sharpe_365"],
            "oos_sharpe_8760": res_test["sharpe_8760"],
            "oos_annual_ret": res_test["annual_ret"],
            "oos_max_dd": res_test["max_dd"],
            "oos_win_rate": res_test["win_rate"],
            "oos_mean_net_exp": res_test.get("mean_net_exposure", 0),
        })

        print(f"  Fold {fold+1}: "
              f"{test_closes.index[0].date()} -> {test_closes.index[-1].date()}, "
              f"train best=L{lookback}_R{rebal} (IS Sharpe {best_sharpe:.3f}), "
              f"OOS Sharpe(365)={res_test['sharpe_365']:.3f}, "
              f"Ann={res_test['annual_ret']:.1%}, "
              f"DD={res_test['max_dd']:.1%}")

    if not fold_results:
        print("  No folds completed!")
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe_365"] > 0).sum()
    print(f"\n  Summary:")
    print(f"    Positive OOS folds: {pos}/{len(df)}")
    print(f"    Mean OOS Sharpe(365): {df['oos_sharpe_365'].mean():.3f}")
    print(f"    Mean OOS Sharpe(8760): {df['oos_sharpe_8760'].mean():.3f}")
    print(f"    Mean OOS Ann Return: {df['oos_annual_ret'].mean():.1%}")
    print(f"    Worst OOS DD: {df['oos_max_dd'].max():.1%}")
    print(f"    Mean OOS Net Exposure: {df['oos_mean_net_exp'].mean():+.3f}")
    return df


# ===========================================================================
# Walk-Forward with Fixed Params
# ===========================================================================

def run_walk_forward_fixed(closes, lookback, rebal, variant="equal"):
    """Walk-forward using fixed params across all folds (no in-sample selection)."""
    print(f"\n  Walk-Forward Fixed Params: L{lookback}_R{rebal} ({variant})")

    N = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end_idx = N - fold * WF_STEP
        test_start_idx = test_end_idx - WF_TEST

        if test_start_idx < 0:
            break

        test_closes = closes.iloc[test_start_idx:test_end_idx]
        if len(test_closes) < 30:
            break

        warmup = min(max(lookback, VOL_WINDOW) + 5, len(test_closes) // 2)
        res = run_tsmom(test_closes, lookback, rebal, variant=variant,
                        warmup=warmup)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days": len(test_closes),
            "sharpe_365": res["sharpe_365"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        })

    if not fold_results:
        return None

    df = pd.DataFrame(fold_results)
    pos = (df["sharpe_365"] > 0).sum()
    print(f"    {pos}/{len(df)} positive, "
          f"mean Sharpe(365)={df['sharpe_365'].mean():.3f}, "
          f"mean Ann={df['annual_ret'].mean():.1%}")
    return df


# ===========================================================================
# 70/30 Train/Test Split
# ===========================================================================

def run_train_test_split(closes, variant="equal", split_ratio=0.7):
    """Train on first 70%, test on last 30%."""
    n = len(closes)
    split_idx = int(n * split_ratio)
    train = closes.iloc[:split_idx]
    test = closes.iloc[split_idx:]

    print(f"\n  70/30 Train/Test ({variant})")
    print(f"  Train: {train.index[0].date()} to {train.index[-1].date()} ({len(train)} days)")
    print(f"  Test:  {test.index[0].date()} to {test.index[-1].date()} ({len(test)} days)")

    # Find best on train
    best_sharpe = -999
    best_params = None
    for lookback, rebal in product(LOOKBACKS, REBAL_FREQS):
        warmup = max(lookback, VOL_WINDOW) + 5
        if warmup >= len(train) - 30:
            continue
        res = run_tsmom(train, lookback, rebal, variant=variant, warmup=warmup)
        if res["sharpe_365"] > best_sharpe:
            best_sharpe = res["sharpe_365"]
            best_params = (lookback, rebal)

    lookback, rebal = best_params
    print(f"  Train best: L{lookback}_R{rebal} (IS Sharpe(365) {best_sharpe:.3f})")

    # Evaluate on test
    warmup = min(max(lookback, VOL_WINDOW) + 5, len(test) // 2)
    res_test = run_tsmom(test, lookback, rebal, variant=variant,
                         warmup=warmup, return_exposure=True)

    print(f"  Test: Sharpe(365)={res_test['sharpe_365']:.3f}, "
          f"Sharpe(8760)={res_test['sharpe_8760']:.3f}, "
          f"Ann={res_test['annual_ret']:.1%}, "
          f"DD={res_test['max_dd']:.1%}, "
          f"WR={res_test['win_rate']:.1%}")

    return {
        "train_best_params": f"L{lookback}_R{rebal}",
        "train_sharpe_365": round(best_sharpe, 3),
        "test_sharpe_365": res_test["sharpe_365"],
        "test_sharpe_8760": res_test["sharpe_8760"],
        "test_annual_ret": res_test["annual_ret"],
        "test_max_dd": res_test["max_dd"],
        "test_win_rate": res_test["win_rate"],
        "test_mean_net_exp": res_test.get("mean_net_exposure", 0),
        "test_n_days": len(test),
    }


# ===========================================================================
# Correlation Analysis: H-012 (cross-sectional) and H-009 (BTC trend)
# ===========================================================================

def compute_correlations(closes, lookback, rebal):
    """
    Compute daily return correlations between TSMOM and:
    1. H-012: Cross-sectional momentum (60d, rebal 5d, top/bottom 4)
    2. H-009: BTC-only trend (proxy: BTC buy-and-hold daily returns)
    3. BTC buy-and-hold
    """
    print(f"\n{'=' * 70}")
    print("CORRELATION ANALYSIS")
    print("=" * 70)

    # --- TSMOM equal weight ---
    warmup = max(lookback, VOL_WINDOW) + 5
    res_tsmom_eq = run_tsmom(closes, lookback, rebal, variant="equal",
                             warmup=warmup)
    eq_tsmom_eq = res_tsmom_eq["equity"]

    # --- TSMOM vol-scaled ---
    res_tsmom_vs = run_tsmom(closes, lookback, rebal, variant="volscaled",
                             warmup=warmup)
    eq_tsmom_vs = res_tsmom_vs["equity"]

    # --- H-012: Cross-sectional momentum (60d lookback, 5d rebal, N=4) ---
    def run_xsmom(closes_in, mom_lookback=60, rebal_in=5, n_long=4):
        """Run cross-sectional momentum (long top N, short bottom N)."""
        N = len(closes_in)
        n_short = n_long
        cap = INITIAL_CAPITAL
        equity = np.zeros(N)
        equity[0] = cap
        prev_w = pd.Series(0.0, index=closes_in.columns)
        warmup_xs = mom_lookback + 5

        for i in range(1, N):
            p_today = closes_in.iloc[i]
            p_yest = closes_in.iloc[i - 1]
            lr = np.log(p_today / p_yest)

            if i >= warmup_xs and (i - warmup_xs) % rebal_in == 0:
                ranks = closes_in.iloc[i-1].div(closes_in.iloc[i-1-mom_lookback]) - 1
                valid = ranks.dropna()
                if len(valid) < n_long + n_short:
                    port_ret = (prev_w * lr).sum()
                    equity[i] = equity[i-1] * np.exp(port_ret)
                    continue

                ranked = valid.sort_values(ascending=False)
                longs = ranked.index[:n_long]
                shorts = ranked.index[-n_short:]

                new_w = pd.Series(0.0, index=closes_in.columns)
                for s in longs:
                    new_w[s] = 1.0 / n_long
                for s in shorts:
                    new_w[s] = -1.0 / n_short

                wc = (new_w - prev_w).abs()
                turnover = wc.sum() / 2
                fee = turnover * FEE_RATE * 2

                port_ret = (new_w * lr).sum() - fee
                prev_w = new_w
            else:
                port_ret = (prev_w * lr).sum()

            equity[i] = equity[i-1] * np.exp(port_ret)

        return pd.Series(equity, index=closes_in.index)

    eq_h012 = run_xsmom(closes)

    # --- BTC buy-and-hold ---
    btc_col = "BTC/USDT"
    if btc_col in closes.columns:
        btc_close = closes[btc_col]
        eq_btc = INITIAL_CAPITAL * btc_close / btc_close.iloc[0]
    else:
        eq_btc = pd.Series(INITIAL_CAPITAL, index=closes.index)

    # Compute daily returns
    rets_tsmom_eq = eq_tsmom_eq.pct_change().dropna()
    rets_tsmom_vs = eq_tsmom_vs.pct_change().dropna()
    rets_h012 = eq_h012.pct_change().dropna()
    rets_btc = eq_btc.pct_change().dropna()

    common = rets_tsmom_eq.index.intersection(rets_h012.index)\
                          .intersection(rets_btc.index)\
                          .intersection(rets_tsmom_vs.index)

    if len(common) < 50:
        print("  Insufficient data overlap for correlation")
        return {}

    r_eq = rets_tsmom_eq.loc[common]
    r_vs = rets_tsmom_vs.loc[common]
    r_h012 = rets_h012.loc[common]
    r_btc = rets_btc.loc[common]

    corr_eq_h012 = r_eq.corr(r_h012)
    corr_eq_btc = r_eq.corr(r_btc)
    corr_vs_h012 = r_vs.corr(r_h012)
    corr_vs_btc = r_vs.corr(r_btc)
    corr_eq_vs = r_eq.corr(r_vs)

    print(f"\n  TSMOM(eq) vs H-012(xs-mom):    {corr_eq_h012:+.3f}")
    print(f"  TSMOM(eq) vs BTC buy-hold:     {corr_eq_btc:+.3f}")
    print(f"  TSMOM(vs) vs H-012(xs-mom):    {corr_vs_h012:+.3f}")
    print(f"  TSMOM(vs) vs BTC buy-hold:     {corr_vs_btc:+.3f}")
    print(f"  TSMOM(eq) vs TSMOM(vs):        {corr_eq_vs:+.3f}")

    # Also compute H-012 and BTC metrics for reference
    h012_metrics = compute_metrics(eq_h012)
    btc_metrics = compute_metrics(eq_btc)
    tsmom_eq_metrics = compute_metrics(eq_tsmom_eq)
    tsmom_vs_metrics = compute_metrics(eq_tsmom_vs)

    print(f"\n  Reference metrics:")
    print(f"    TSMOM(eq) L{lookback}_R{rebal}: Sharpe(365)={tsmom_eq_metrics['sharpe_365']}, "
          f"Ann={tsmom_eq_metrics['annual_ret']:.1%}, DD={tsmom_eq_metrics['max_dd']:.1%}")
    print(f"    TSMOM(vs) L{lookback}_R{rebal}: Sharpe(365)={tsmom_vs_metrics['sharpe_365']}, "
          f"Ann={tsmom_vs_metrics['annual_ret']:.1%}, DD={tsmom_vs_metrics['max_dd']:.1%}")
    print(f"    H-012 (xs-mom):  Sharpe(365)={h012_metrics['sharpe_365']}, "
          f"Ann={h012_metrics['annual_ret']:.1%}, DD={h012_metrics['max_dd']:.1%}")
    print(f"    BTC buy-hold:    Sharpe(365)={btc_metrics['sharpe_365']}, "
          f"Ann={btc_metrics['annual_ret']:.1%}, DD={btc_metrics['max_dd']:.1%}")

    # Hypothetical 50/50 TSMOM(eq) + H-012 portfolio
    combined_rets = 0.5 * r_eq + 0.5 * r_h012
    combined_eq = INITIAL_CAPITAL * (1 + combined_rets).cumprod()
    combined_metrics = compute_metrics(combined_eq)
    print(f"\n  Hypothetical 50/50 TSMOM(eq)+H-012:")
    print(f"    Sharpe(365)={combined_metrics['sharpe_365']}, "
          f"Ann={combined_metrics['annual_ret']:.1%}, "
          f"DD={combined_metrics['max_dd']:.1%}")

    return {
        "corr_tsmom_eq_vs_h012": round(float(corr_eq_h012), 3),
        "corr_tsmom_eq_vs_btc": round(float(corr_eq_btc), 3),
        "corr_tsmom_vs_vs_h012": round(float(corr_vs_h012), 3),
        "corr_tsmom_vs_vs_btc": round(float(corr_vs_btc), 3),
        "corr_tsmom_eq_vs_tsmom_vs": round(float(corr_eq_vs), 3),
        "h012_sharpe_365": h012_metrics["sharpe_365"],
        "h012_annual_ret": h012_metrics["annual_ret"],
        "btc_sharpe_365": btc_metrics["sharpe_365"],
        "btc_annual_ret": btc_metrics["annual_ret"],
        "combined_50_50_sharpe_365": combined_metrics["sharpe_365"],
        "combined_50_50_annual_ret": combined_metrics["annual_ret"],
        "combined_50_50_max_dd": combined_metrics["max_dd"],
    }


# ===========================================================================
# Net Exposure Analysis
# ===========================================================================

def analyze_exposure(closes, lookback, rebal, variant="equal"):
    """Detailed analysis of net exposure over time."""
    print(f"\n{'=' * 70}")
    print(f"NET EXPOSURE ANALYSIS: L{lookback}_R{rebal} ({variant})")
    print("=" * 70)

    warmup = max(lookback, VOL_WINDOW) + 5
    res = run_tsmom(closes, lookback, rebal, variant=variant,
                    warmup=warmup, return_exposure=True)

    if "net_exposures" not in res:
        print("  No exposure data")
        return

    exp_df = res["net_exposures"]
    ne = exp_df["net_exposure"]

    print(f"  Mean net exposure:     {ne.mean():+.3f}")
    print(f"  Std net exposure:      {ne.std():.3f}")
    print(f"  Min net exposure:      {ne.min():+.3f}")
    print(f"  Max net exposure:      {ne.max():+.3f}")
    print(f"  % time net long:       {(ne > 0).mean():.1%}")
    print(f"  % time net short:      {(ne <= 0).mean():.1%}")
    print(f"  % time fully long (>0.9):  {(ne > 0.9).mean():.1%}")
    print(f"  % time fully short (<-0.9): {(ne < -0.9).mean():.1%}")
    print(f"  % time near neutral (|ne|<0.2): {(ne.abs() < 0.2).mean():.1%}")

    # Exposure distribution
    bins = [-1.1, -0.8, -0.5, -0.2, 0.2, 0.5, 0.8, 1.1]
    labels = ["<-0.8", "-0.8:-0.5", "-0.5:-0.2", "-0.2:+0.2",
              "+0.2:+0.5", "+0.5:+0.8", ">+0.8"]
    hist = pd.cut(ne, bins=bins, labels=labels).value_counts().sort_index()
    print(f"\n  Exposure distribution:")
    for label, count in hist.items():
        pct = count / len(ne) * 100
        bar = "#" * int(pct / 2)
        print(f"    {label:>12s}: {count:4d} ({pct:5.1f}%) {bar}")

    return res


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("H-088: Time-Series Momentum (TSMOM) Portfolio")
    print("=" * 70)
    print(f"Assets: {len(ASSETS)}")
    print(f"Lookbacks: {LOOKBACKS}")
    print(f"Rebalance frequencies: {REBAL_FREQS}")
    print(f"Fee: {FEE_RATE*10000:.0f} bps/side ({FEE_RATE*2*10000:.0f} bps round-trip)")

    # === Load data ===
    print("\nLoading daily data...")
    daily = load_daily_data()
    print(f"Loaded {len(daily)} assets")

    if len(daily) < 10:
        print("ERROR: Not enough assets loaded. Aborting.")
        sys.exit(1)

    closes = build_panels(daily)
    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")
    print(f"Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    # ===================================================================
    # SECTION 1: EQUAL-WEIGHT TSMOM
    # ===================================================================
    print("\n\n" + "#" * 70)
    print("# SECTION 1: EQUAL-WEIGHT TSMOM")
    print("#" * 70)

    # 1a. Full parameter scan
    scan_eq = run_full_scan(closes, variant="equal")

    # 1b. Best equal-weight params
    best_eq = scan_eq.nlargest(1, "sharpe_365").iloc[0]
    best_L_eq = int(best_eq["lookback"])
    best_R_eq = int(best_eq["rebal"])
    print(f"\n  BEST equal-weight: L{best_L_eq}_R{best_R_eq}")
    print(f"  Sharpe(365)={best_eq['sharpe_365']:.3f}, "
          f"Sharpe(8760)={best_eq['sharpe_8760']:.3f}, "
          f"Ann={best_eq['annual_ret']:.1%}, DD={best_eq['max_dd']:.1%}, "
          f"WR={best_eq['win_rate']:.1%}")

    # 1c. Walk-forward (in-sample param selection)
    wf_eq = run_walk_forward(closes, variant="equal")

    # 1d. Walk-forward with fixed best params
    wf_eq_fixed = run_walk_forward_fixed(closes, best_L_eq, best_R_eq,
                                          variant="equal")

    # 1e. 70/30 train/test
    tt_eq = run_train_test_split(closes, variant="equal")

    # 1f. Net exposure analysis
    analyze_exposure(closes, best_L_eq, best_R_eq, variant="equal")

    # ===================================================================
    # SECTION 2: VOL-SCALED TSMOM
    # ===================================================================
    print("\n\n" + "#" * 70)
    print("# SECTION 2: VOL-SCALED TSMOM")
    print("#" * 70)

    # 2a. Full parameter scan
    scan_vs = run_full_scan(closes, variant="volscaled")

    # 2b. Best vol-scaled params
    best_vs = scan_vs.nlargest(1, "sharpe_365").iloc[0]
    best_L_vs = int(best_vs["lookback"])
    best_R_vs = int(best_vs["rebal"])
    print(f"\n  BEST vol-scaled: L{best_L_vs}_R{best_R_vs}")
    print(f"  Sharpe(365)={best_vs['sharpe_365']:.3f}, "
          f"Sharpe(8760)={best_vs['sharpe_8760']:.3f}, "
          f"Ann={best_vs['annual_ret']:.1%}, DD={best_vs['max_dd']:.1%}, "
          f"WR={best_vs['win_rate']:.1%}")

    # 2c. Walk-forward (param selection)
    wf_vs = run_walk_forward(closes, variant="volscaled")

    # 2d. Walk-forward with fixed best params
    wf_vs_fixed = run_walk_forward_fixed(closes, best_L_vs, best_R_vs,
                                          variant="volscaled")

    # 2e. 70/30 train/test
    tt_vs = run_train_test_split(closes, variant="volscaled")

    # 2f. Net exposure analysis
    analyze_exposure(closes, best_L_vs, best_R_vs, variant="volscaled")

    # ===================================================================
    # SECTION 3: CORRELATION ANALYSIS
    # ===================================================================
    corr_eq = compute_correlations(closes, best_L_eq, best_R_eq)

    # ===================================================================
    # SECTION 4: COMPREHENSIVE SUMMARY
    # ===================================================================
    print("\n\n" + "=" * 70)
    print("COMPREHENSIVE SUMMARY: H-088 TSMOM PORTFOLIO")
    print("=" * 70)

    print("\n--- EQUAL-WEIGHT TSMOM ---")
    print(f"  Full-period best: L{best_L_eq}_R{best_R_eq}")
    print(f"    Sharpe(365):  {best_eq['sharpe_365']:.3f}")
    print(f"    Sharpe(8760): {best_eq['sharpe_8760']:.3f}")
    print(f"    Annual Return: {best_eq['annual_ret']:.1%}")
    print(f"    Max Drawdown:  {best_eq['max_dd']:.1%}")
    print(f"    Win Rate:      {best_eq['win_rate']:.1%}")
    print(f"    Mean Net Exp:  {best_eq['mean_net_exp']:+.2f}")
    print(f"  Parameter robustness: {(scan_eq['sharpe_365'] > 0).sum()}/{len(scan_eq)} "
          f"positive ({(scan_eq['sharpe_365'] > 0).mean():.0%})")
    print(f"    Mean Sharpe(365): {scan_eq['sharpe_365'].mean():.3f}")
    print(f"    Median Sharpe(365): {scan_eq['sharpe_365'].median():.3f}")

    if wf_eq is not None:
        pos_eq = (wf_eq["oos_sharpe_365"] > 0).sum()
        print(f"  Walk-forward (param sel): {pos_eq}/{len(wf_eq)} positive, "
              f"mean OOS Sharpe(365)={wf_eq['oos_sharpe_365'].mean():.3f}")
    if wf_eq_fixed is not None:
        pos_eq_f = (wf_eq_fixed["sharpe_365"] > 0).sum()
        print(f"  Walk-forward (fixed):     {pos_eq_f}/{len(wf_eq_fixed)} positive, "
              f"mean OOS Sharpe(365)={wf_eq_fixed['sharpe_365'].mean():.3f}")
    print(f"  70/30 split: train Sharpe {tt_eq['train_sharpe_365']:.3f}, "
          f"test Sharpe {tt_eq['test_sharpe_365']:.3f}, "
          f"test Ann {tt_eq['test_annual_ret']:.1%}")

    print("\n--- VOL-SCALED TSMOM ---")
    print(f"  Full-period best: L{best_L_vs}_R{best_R_vs}")
    print(f"    Sharpe(365):  {best_vs['sharpe_365']:.3f}")
    print(f"    Sharpe(8760): {best_vs['sharpe_8760']:.3f}")
    print(f"    Annual Return: {best_vs['annual_ret']:.1%}")
    print(f"    Max Drawdown:  {best_vs['max_dd']:.1%}")
    print(f"    Win Rate:      {best_vs['win_rate']:.1%}")
    print(f"    Mean Net Exp:  {best_vs['mean_net_exp']:+.2f}")
    print(f"  Parameter robustness: {(scan_vs['sharpe_365'] > 0).sum()}/{len(scan_vs)} "
          f"positive ({(scan_vs['sharpe_365'] > 0).mean():.0%})")
    print(f"    Mean Sharpe(365): {scan_vs['sharpe_365'].mean():.3f}")
    print(f"    Median Sharpe(365): {scan_vs['sharpe_365'].median():.3f}")

    if wf_vs is not None:
        pos_vs = (wf_vs["oos_sharpe_365"] > 0).sum()
        print(f"  Walk-forward (param sel): {pos_vs}/{len(wf_vs)} positive, "
              f"mean OOS Sharpe(365)={wf_vs['oos_sharpe_365'].mean():.3f}")
    if wf_vs_fixed is not None:
        pos_vs_f = (wf_vs_fixed["sharpe_365"] > 0).sum()
        print(f"  Walk-forward (fixed):     {pos_vs_f}/{len(wf_vs_fixed)} positive, "
              f"mean OOS Sharpe(365)={wf_vs_fixed['sharpe_365'].mean():.3f}")
    print(f"  70/30 split: train Sharpe {tt_vs['train_sharpe_365']:.3f}, "
          f"test Sharpe {tt_vs['test_sharpe_365']:.3f}, "
          f"test Ann {tt_vs['test_annual_ret']:.1%}")

    print("\n--- CORRELATION WITH EXISTING STRATEGIES ---")
    if corr_eq:
        print(f"  TSMOM(eq) vs H-012 (xs-mom): {corr_eq['corr_tsmom_eq_vs_h012']:+.3f}")
        print(f"  TSMOM(eq) vs BTC buy-hold:   {corr_eq['corr_tsmom_eq_vs_btc']:+.3f}")
        print(f"  TSMOM(vs) vs H-012 (xs-mom): {corr_eq['corr_tsmom_vs_vs_h012']:+.3f}")
        print(f"  TSMOM(vs) vs BTC buy-hold:   {corr_eq['corr_tsmom_vs_vs_btc']:+.3f}")
        print(f"  TSMOM(eq) vs TSMOM(vs):      {corr_eq['corr_tsmom_eq_vs_tsmom_vs']:+.3f}")
        print(f"\n  50/50 TSMOM(eq)+H-012 combo:")
        print(f"    Sharpe(365):   {corr_eq['combined_50_50_sharpe_365']}")
        print(f"    Annual Return: {corr_eq['combined_50_50_annual_ret']:.1%}")
        print(f"    Max DD:        {corr_eq['combined_50_50_max_dd']:.1%}")

    # ===================================================================
    # SECTION 5: DECISION CRITERIA
    # ===================================================================
    print("\n--- TARGETS CHECK ---")
    targets = {
        "Annual return >= 20%": None,
        "Max drawdown <= 50%": None,
        "Sharpe(365) >= 1.5": None,
        "Win rate >= 45%": None,
    }

    # Check best variant
    for variant_name, best_row, wf_data, tt_data in [
        ("Equal-weight", best_eq, wf_eq, tt_eq),
        ("Vol-scaled", best_vs, wf_vs, tt_vs),
    ]:
        print(f"\n  {variant_name}:")
        ann = best_row["annual_ret"]
        dd = best_row["max_dd"]
        sharpe = best_row["sharpe_365"]
        wr = best_row["win_rate"]

        pass_ann = ann >= 0.20
        pass_dd = dd <= 0.50
        pass_sharpe = sharpe >= 1.5
        pass_wr = wr >= 0.45

        print(f"    Annual return {ann:.1%} {'PASS' if pass_ann else 'FAIL'} (target >=20%)")
        print(f"    Max DD {dd:.1%} {'PASS' if pass_dd else 'FAIL'} (target <=50%)")
        print(f"    Sharpe(365) {sharpe:.3f} {'PASS' if pass_sharpe else 'FAIL'} (target >=1.5)")
        print(f"    Win rate {wr:.1%} {'PASS' if pass_wr else 'FAIL'} (target >=45%)")

        if wf_data is not None:
            wf_mean = wf_data["oos_sharpe_365"].mean()
            wf_pos = (wf_data["oos_sharpe_365"] > 0).sum()
            print(f"    WF OOS mean Sharpe: {wf_mean:.3f}, "
                  f"{wf_pos}/{len(wf_data)} positive")
        print(f"    Test (30%) Sharpe: {tt_data['test_sharpe_365']:.3f}, "
              f"Ann: {tt_data['test_annual_ret']:.1%}")

    # ===================================================================
    # SECTION 6: SAVE RESULTS
    # ===================================================================
    results_file = Path(__file__).parent / "h088_results.json"
    results_data = {
        "hypothesis": "H-088",
        "name": "Time-Series Momentum (TSMOM) Portfolio",
        "description": "Trade each of 14 crypto assets based on own L-day return sign. "
                       "Net directional — can be fully long or fully short the market.",
        "fee_rate_bps_per_side": FEE_RATE * 10000,
        "universe_size": len(closes.columns),
        "n_days": len(closes),
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "equal_weight": {
            "full_scan": {
                "n_combos": len(scan_eq),
                "pct_positive_sharpe": round((scan_eq["sharpe_365"] > 0).mean(), 3),
                "mean_sharpe_365": round(scan_eq["sharpe_365"].mean(), 3),
                "median_sharpe_365": round(scan_eq["sharpe_365"].median(), 3),
                "best_params": f"L{best_L_eq}_R{best_R_eq}",
                "best_sharpe_365": float(best_eq["sharpe_365"]),
                "best_sharpe_8760": float(best_eq["sharpe_8760"]),
                "best_annual_ret": float(best_eq["annual_ret"]),
                "best_max_dd": float(best_eq["max_dd"]),
                "best_win_rate": float(best_eq["win_rate"]),
                "all_results": scan_eq.to_dict("records"),
            },
            "walk_forward": {
                "n_folds": len(wf_eq) if wf_eq is not None else 0,
                "positive_folds": int((wf_eq["oos_sharpe_365"] > 0).sum()) if wf_eq is not None else 0,
                "mean_oos_sharpe_365": round(float(wf_eq["oos_sharpe_365"].mean()), 3) if wf_eq is not None else 0,
                "mean_oos_annual_ret": round(float(wf_eq["oos_annual_ret"].mean()), 4) if wf_eq is not None else 0,
                "folds": wf_eq.to_dict("records") if wf_eq is not None else [],
            },
            "walk_forward_fixed": {
                "params": f"L{best_L_eq}_R{best_R_eq}",
                "n_folds": len(wf_eq_fixed) if wf_eq_fixed is not None else 0,
                "positive_folds": int((wf_eq_fixed["sharpe_365"] > 0).sum()) if wf_eq_fixed is not None else 0,
                "mean_oos_sharpe_365": round(float(wf_eq_fixed["sharpe_365"].mean()), 3) if wf_eq_fixed is not None else 0,
                "folds": wf_eq_fixed.to_dict("records") if wf_eq_fixed is not None else [],
            },
            "train_test_70_30": tt_eq,
        },
        "vol_scaled": {
            "full_scan": {
                "n_combos": len(scan_vs),
                "pct_positive_sharpe": round((scan_vs["sharpe_365"] > 0).mean(), 3),
                "mean_sharpe_365": round(scan_vs["sharpe_365"].mean(), 3),
                "median_sharpe_365": round(scan_vs["sharpe_365"].median(), 3),
                "best_params": f"L{best_L_vs}_R{best_R_vs}",
                "best_sharpe_365": float(best_vs["sharpe_365"]),
                "best_sharpe_8760": float(best_vs["sharpe_8760"]),
                "best_annual_ret": float(best_vs["annual_ret"]),
                "best_max_dd": float(best_vs["max_dd"]),
                "best_win_rate": float(best_vs["win_rate"]),
                "all_results": scan_vs.to_dict("records"),
            },
            "walk_forward": {
                "n_folds": len(wf_vs) if wf_vs is not None else 0,
                "positive_folds": int((wf_vs["oos_sharpe_365"] > 0).sum()) if wf_vs is not None else 0,
                "mean_oos_sharpe_365": round(float(wf_vs["oos_sharpe_365"].mean()), 3) if wf_vs is not None else 0,
                "mean_oos_annual_ret": round(float(wf_vs["oos_annual_ret"].mean()), 4) if wf_vs is not None else 0,
                "folds": wf_vs.to_dict("records") if wf_vs is not None else [],
            },
            "walk_forward_fixed": {
                "params": f"L{best_L_vs}_R{best_R_vs}",
                "n_folds": len(wf_vs_fixed) if wf_vs_fixed is not None else 0,
                "positive_folds": int((wf_vs_fixed["sharpe_365"] > 0).sum()) if wf_vs_fixed is not None else 0,
                "mean_oos_sharpe_365": round(float(wf_vs_fixed["sharpe_365"].mean()), 3) if wf_vs_fixed is not None else 0,
                "folds": wf_vs_fixed.to_dict("records") if wf_vs_fixed is not None else [],
            },
            "train_test_70_30": tt_vs,
        },
        "correlations": corr_eq,
    }

    with open(results_file, "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\n  Results saved to {results_file}")
    print("\nDone.")
