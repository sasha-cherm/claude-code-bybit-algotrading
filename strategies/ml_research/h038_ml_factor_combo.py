"""
H-038: ML Factor Combination for Cross-Sectional Returns (Session 2026-03-19, session 39)

Idea: Instead of running individual factors (momentum, volume momentum, beta, vol)
separately and combining at portfolio level, use ML to learn optimal non-linear
factor combination for predicting next-period cross-sectional returns.

Tests:
1. Ridge regression (linear baseline)
2. Random Forest (non-linear interactions)
3. Gradient Boosting (sequential learning)

Comparison: ML combination vs. individual best factor vs. equal-weight combo
Walk-forward validation throughout.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from strategies.new_factors_research.research import (
    load_all_data, compute_metrics, ASSETS, BASE_FEE, SLIPPAGE_BPS, INITIAL_CAPITAL,
)
from lib.metrics import sharpe_ratio, max_drawdown, annual_return


def compute_factor_signals(closes, volumes):
    """Compute all factor signals for each asset each day."""
    rets = closes.pct_change()

    factors = {}

    # 1. Momentum (60d return)
    factors['mom_60'] = closes.pct_change(60)

    # 2. Short-term momentum (20d return)
    factors['mom_20'] = closes.pct_change(20)

    # 3. Volume momentum (5d/20d volume ratio)
    vol_short = volumes.rolling(5).mean()
    vol_long = volumes.rolling(20).mean()
    factors['vol_mom'] = vol_short / vol_long

    # 4. Realized volatility (20d, negative = low vol is better)
    factors['vol_20'] = -rets.rolling(20).std()

    # 5. Beta vs BTC (60d rolling)
    btc_col = [c for c in closes.columns if 'BTC' in c]
    if btc_col:
        btc_rets = rets[btc_col[0]]
        betas = pd.DataFrame(index=closes.index, columns=closes.columns)
        for sym in closes.columns:
            for i in range(60, len(rets)):
                window = slice(i-60, i)
                cov = np.cov(rets[sym].iloc[window].values, btc_rets.iloc[window].values)
                if cov[1, 1] > 0:
                    betas.iloc[i][sym] = cov[0, 1] / cov[1, 1]
        factors['beta'] = -betas.astype(float)  # negative = low beta is better

    # 6. Size (30d avg dollar volume, positive = large cap)
    dollar_vol = closes * volumes
    factors['size'] = dollar_vol.rolling(30).mean()

    # 7. Short-term reversal (5d return, negative = buy losers)
    factors['reversal'] = -closes.pct_change(5)

    return factors


def compute_factor_signals_fast(closes, volumes):
    """Fast version - vectorized beta computation."""
    rets = closes.pct_change()

    factors = {}

    # 1. Momentum (60d return)
    factors['mom_60'] = closes.pct_change(60)

    # 2. Short-term momentum (20d return)
    factors['mom_20'] = closes.pct_change(20)

    # 3. Volume momentum (5d/20d volume ratio)
    vol_short = volumes.rolling(5).mean()
    vol_long = volumes.rolling(20).mean()
    factors['vol_mom'] = vol_short / vol_long

    # 4. Realized volatility (20d, negative = low vol ranks high)
    factors['vol_20'] = -rets.rolling(20).std()

    # 5. Beta vs BTC (60d rolling) - vectorized
    btc_col = [c for c in closes.columns if 'BTC' in c]
    if btc_col:
        btc_rets = rets[btc_col[0]]
        btc_var = btc_rets.rolling(60).var()
        betas = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
        for sym in closes.columns:
            cov = rets[sym].rolling(60).cov(btc_rets)
            betas[sym] = cov / btc_var
        factors['beta'] = -betas  # negative = low beta ranks high

    # 6. Size (30d avg dollar volume)
    dollar_vol = closes * volumes
    factors['size'] = dollar_vol.rolling(30).mean()

    # 7. Short-term reversal (5d, negative = buy losers)
    factors['reversal'] = -closes.pct_change(5)

    return factors


def build_feature_matrix(factors, closes, forward_days=5):
    """
    Build feature matrix for ML:
    - Each row = (date, asset)
    - Features = cross-sectional rank of each factor on that date
    - Target = forward N-day return (cross-sectional demeaned)
    """
    rets = closes.pct_change()

    # Forward returns (target)
    fwd_ret = closes.pct_change(forward_days).shift(-forward_days)

    rows = []
    dates = closes.index[70:-forward_days]  # skip warmup + forward

    for date in dates:
        for sym in closes.columns:
            feat = {}
            feat['date'] = date
            feat['symbol'] = sym

            # Cross-sectional rank for each factor (normalize to [0,1])
            for fname, fdata in factors.items():
                vals = fdata.loc[date].dropna()
                if sym in vals.index and len(vals) >= 5:
                    rank = vals.rank(pct=True)
                    feat[f'{fname}_rank'] = rank[sym]
                    feat[f'{fname}_zscore'] = (vals[sym] - vals.mean()) / (vals.std() + 1e-10)
                else:
                    feat[f'{fname}_rank'] = np.nan
                    feat[f'{fname}_zscore'] = np.nan

            # Target: forward return (cross-sectional demeaned)
            fwd_vals = fwd_ret.loc[date].dropna()
            if sym in fwd_vals.index:
                feat['target'] = fwd_vals[sym] - fwd_vals.mean()
                feat['raw_fwd_ret'] = fwd_vals[sym]
            else:
                feat['target'] = np.nan
                feat['raw_fwd_ret'] = np.nan

            rows.append(feat)

    df = pd.DataFrame(rows)
    return df.dropna()


def run_ml_backtest(predictions_by_date, closes, n_long=4, n_short=4,
                    rebal_freq=5, fee_multiplier=1.0):
    """
    Run backtest from ML predictions.
    predictions_by_date: dict of {date: {symbol: predicted_score}}
    """
    slippage = SLIPPAGE_BPS / 10_000
    fee_rate = BASE_FEE * fee_multiplier

    dates = sorted(closes.index)
    n = len(dates)

    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    prev_weights = pd.Series(0.0, index=closes.columns)
    trades = 0
    rebal_dates = sorted(predictions_by_date.keys())
    rebal_idx = 0

    for i in range(1, n):
        date = dates[i]
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]

        # Rebalance if we have a prediction for this date
        if rebal_idx < len(rebal_dates) and date >= rebal_dates[rebal_idx]:
            pred_date = rebal_dates[rebal_idx]
            preds = predictions_by_date[pred_date]
            rebal_idx += 1

            # Rank by prediction
            pred_series = pd.Series(preds)
            valid = pred_series.dropna().sort_values(ascending=False)

            if len(valid) >= n_long + n_short:
                longs = valid.index[:n_long]
                shorts = valid.index[-n_short:]

                new_weights = pd.Series(0.0, index=closes.columns)
                for sym in longs:
                    if sym in new_weights.index:
                        new_weights[sym] = 1.0 / n_long
                for sym in shorts:
                    if sym in new_weights.index:
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
        else:
            daily_rets = (price_today / price_yesterday - 1)
            port_ret = (prev_weights * daily_rets).sum()

        equity[i] = equity[i - 1] * (1 + port_ret)

    eq_series = pd.Series(equity, index=dates)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = trades
    metrics["equity"] = eq_series
    return metrics


def walk_forward_ml(feature_df, closes, model_class, model_params,
                    train_window=365, test_window=90, rebal_freq=5,
                    n_long=4, n_short=4, feature_cols=None):
    """
    Walk-forward ML backtester.
    Train on rolling window, predict on next test window, trade on predictions.
    """
    if feature_cols is None:
        feature_cols = [c for c in feature_df.columns
                       if c.endswith('_rank') or c.endswith('_zscore')]

    dates = sorted(feature_df['date'].unique())
    all_predictions = {}
    fold_results = []

    fold_start = train_window
    fold_num = 0

    while fold_start + test_window <= len(dates):
        train_dates = dates[fold_start - train_window:fold_start]
        test_dates = dates[fold_start:fold_start + test_window]

        train_mask = feature_df['date'].isin(train_dates)
        test_mask = feature_df['date'].isin(test_dates)

        X_train = feature_df.loc[train_mask, feature_cols].values
        y_train = feature_df.loc[train_mask, 'target'].values
        X_test = feature_df.loc[test_mask, feature_cols].values

        # Scale
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)

        # Train
        model = model_class(**model_params)
        model.fit(X_train_s, y_train)

        # Predict
        y_pred = model.predict(X_test_s)
        test_rows = feature_df.loc[test_mask].copy()
        test_rows['prediction'] = y_pred

        # Build prediction dict: for each rebal date, asset -> score
        for date in test_dates:
            if (dates.index(date) - dates.index(test_dates[0])) % rebal_freq == 0:
                day_preds = test_rows[test_rows['date'] == date]
                if len(day_preds) > 0:
                    all_predictions[date] = dict(zip(
                        day_preds['symbol'], day_preds['prediction']
                    ))

        fold_num += 1
        fold_start += test_window

    if not all_predictions:
        return None, []

    # Run backtest on predictions
    result = run_ml_backtest(all_predictions, closes, n_long=n_long,
                            n_short=n_short, rebal_freq=rebal_freq)

    return result, fold_results


def compute_correlation_with_existing(equity, closes):
    """Compute correlation with existing strategy equity curves."""
    # Reconstruct H-012 (momentum 60d, 5d rebal, N=4) equity
    from strategies.new_factors_research.research import run_xs_factor

    mom = closes.pct_change(60)
    h012 = run_xs_factor(closes, mom, 5, 4, warmup=65)

    # H-021 (volume momentum)
    # We don't have volume here easily, so just do H-012 correlation

    common_idx = equity.index.intersection(h012['equity'].index)
    ml_rets = equity.reindex(common_idx).pct_change().dropna()
    h012_rets = h012['equity'].reindex(common_idx).pct_change().dropna()

    common = ml_rets.index.intersection(h012_rets.index)
    corr_h012 = ml_rets[common].corr(h012_rets[common])

    return {"corr_h012": round(corr_h012, 3)}


def main():
    print("=" * 70)
    print("H-038: ML FACTOR COMBINATION RESEARCH")
    print("=" * 70)

    # Load data
    print("\nLoading data...")
    hourly, daily_data = load_all_data()

    # Build closes and volumes
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().dropna()
    common = closes.columns.intersection(volumes.columns)
    closes = closes[common]
    volumes = volumes[common]

    print(f"Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"Date range: {closes.index[0]} to {closes.index[-1]}")

    # Compute factor signals
    print("\nComputing factor signals...")
    factors = compute_factor_signals_fast(closes, volumes)
    print(f"Factors: {list(factors.keys())}")

    # Build feature matrix
    print("\nBuilding feature matrix (forward=5d)...")
    feat_df = build_feature_matrix(factors, closes, forward_days=5)
    print(f"Feature matrix: {len(feat_df)} rows, {feat_df.shape[1]} columns")
    print(f"Date range: {feat_df['date'].min()} to {feat_df['date'].max()}")
    print(f"Unique dates: {feat_df['date'].nunique()}")

    feature_cols_rank = [c for c in feat_df.columns if c.endswith('_rank')]
    feature_cols_zscore = [c for c in feat_df.columns if c.endswith('_zscore')]
    feature_cols_all = feature_cols_rank + feature_cols_zscore

    print(f"Rank features: {feature_cols_rank}")
    print(f"Z-score features: {feature_cols_zscore}")

    # ═══════════════════════════════════════════════════════════════════
    # Test 1: Ridge Regression (linear baseline)
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 1: RIDGE REGRESSION (Linear Combination)")
    print("=" * 70)

    ridge_results = []
    for alpha in [0.1, 1.0, 10.0, 100.0]:
        for feat_type, feat_cols in [("rank", feature_cols_rank),
                                      ("zscore", feature_cols_zscore),
                                      ("all", feature_cols_all)]:
            for n_long in [3, 4, 5]:
                for rebal in [3, 5, 7]:
                    result, _ = walk_forward_ml(
                        feat_df, closes,
                        Ridge, {"alpha": alpha},
                        train_window=365, test_window=90,
                        rebal_freq=rebal, n_long=n_long, n_short=n_long,
                        feature_cols=feat_cols
                    )
                    if result is None:
                        continue
                    tag = f"Ridge_a{alpha}_{feat_type}_R{rebal}_N{n_long}"
                    ridge_results.append({
                        "tag": tag, "alpha": alpha, "features": feat_type,
                        "rebal": rebal, "n_long": n_long,
                        "sharpe": result["sharpe"],
                        "annual_ret": result["annual_ret"],
                        "max_dd": result["max_dd"],
                        "n_trades": result["n_trades"],
                    })
                    if result["sharpe"] > 0.5:
                        print(f"  ** {tag}: Sharpe {result['sharpe']:.2f}, "
                              f"Ann {result['annual_ret']:.1%}, DD {result['max_dd']:.1%}")

    ridge_df = pd.DataFrame(ridge_results)
    if len(ridge_df) > 0:
        pos = ridge_df[ridge_df["sharpe"] > 0]
        print(f"\n  Ridge: {len(pos)}/{len(ridge_df)} positive Sharpe "
              f"({len(pos)/len(ridge_df):.0%})")
        print(f"  Mean Sharpe: {ridge_df['sharpe'].mean():.2f}")
        print(f"  Best Sharpe: {ridge_df['sharpe'].max():.2f}")
        top3 = ridge_df.nlargest(3, "sharpe")
        print("\n  Top 3 Ridge configs:")
        for _, row in top3.iterrows():
            print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
                  f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    # ═══════════════════════════════════════════════════════════════════
    # Test 2: Random Forest (non-linear)
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 2: RANDOM FOREST (Non-Linear Interactions)")
    print("=" * 70)

    rf_results = []
    for n_est in [50, 100]:
        for max_depth in [3, 5]:
            for feat_type, feat_cols in [("rank", feature_cols_rank),
                                          ("all", feature_cols_all)]:
                for n_long in [3, 4]:
                    for rebal in [5, 7]:
                        result, _ = walk_forward_ml(
                            feat_df, closes,
                            RandomForestRegressor,
                            {"n_estimators": n_est, "max_depth": max_depth,
                             "random_state": 42, "n_jobs": -1},
                            train_window=365, test_window=90,
                            rebal_freq=rebal, n_long=n_long, n_short=n_long,
                            feature_cols=feat_cols
                        )
                        if result is None:
                            continue
                        tag = f"RF_e{n_est}_d{max_depth}_{feat_type}_R{rebal}_N{n_long}"
                        rf_results.append({
                            "tag": tag, "n_est": n_est, "max_depth": max_depth,
                            "features": feat_type, "rebal": rebal, "n_long": n_long,
                            "sharpe": result["sharpe"],
                            "annual_ret": result["annual_ret"],
                            "max_dd": result["max_dd"],
                            "n_trades": result["n_trades"],
                        })
                        if result["sharpe"] > 0.5:
                            print(f"  ** {tag}: Sharpe {result['sharpe']:.2f}, "
                                  f"Ann {result['annual_ret']:.1%}, DD {result['max_dd']:.1%}")

    rf_df = pd.DataFrame(rf_results)
    if len(rf_df) > 0:
        pos = rf_df[rf_df["sharpe"] > 0]
        print(f"\n  RF: {len(pos)}/{len(rf_df)} positive Sharpe "
              f"({len(pos)/len(rf_df):.0%})")
        print(f"  Mean Sharpe: {rf_df['sharpe'].mean():.2f}")
        print(f"  Best Sharpe: {rf_df['sharpe'].max():.2f}")
        top3 = rf_df.nlargest(3, "sharpe")
        print("\n  Top 3 RF configs:")
        for _, row in top3.iterrows():
            print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
                  f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    # ═══════════════════════════════════════════════════════════════════
    # Test 3: Gradient Boosting (sequential)
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 3: GRADIENT BOOSTING (Sequential Learning)")
    print("=" * 70)

    gb_results = []
    for n_est in [50, 100]:
        for max_depth in [2, 3]:
            for lr in [0.01, 0.05]:
                for feat_type, feat_cols in [("rank", feature_cols_rank),
                                              ("all", feature_cols_all)]:
                    for n_long in [3, 4]:
                        result, _ = walk_forward_ml(
                            feat_df, closes,
                            GradientBoostingRegressor,
                            {"n_estimators": n_est, "max_depth": max_depth,
                             "learning_rate": lr, "random_state": 42},
                            train_window=365, test_window=90,
                            rebal_freq=rebal, n_long=n_long, n_short=n_long,
                            feature_cols=feat_cols
                        )
                        if result is None:
                            continue
                        tag = f"GB_e{n_est}_d{max_depth}_lr{lr}_{feat_type}_N{n_long}"
                        gb_results.append({
                            "tag": tag, "n_est": n_est, "max_depth": max_depth,
                            "lr": lr, "features": feat_type, "n_long": n_long,
                            "sharpe": result["sharpe"],
                            "annual_ret": result["annual_ret"],
                            "max_dd": result["max_dd"],
                            "n_trades": result["n_trades"],
                        })
                        if result["sharpe"] > 0.5:
                            print(f"  ** {tag}: Sharpe {result['sharpe']:.2f}, "
                                  f"Ann {result['annual_ret']:.1%}, DD {result['max_dd']:.1%}")

    gb_df = pd.DataFrame(gb_results)
    if len(gb_df) > 0:
        pos = gb_df[gb_df["sharpe"] > 0]
        print(f"\n  GB: {len(pos)}/{len(gb_df)} positive Sharpe "
              f"({len(pos)/len(gb_df):.0%})")
        print(f"  Mean Sharpe: {gb_df['sharpe'].mean():.2f}")
        print(f"  Best Sharpe: {gb_df['sharpe'].max():.2f}")
        top3 = gb_df.nlargest(3, "sharpe")
        print("\n  Top 3 GB configs:")
        for _, row in top3.iterrows():
            print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
                  f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    # ═══════════════════════════════════════════════════════════════════
    # Test 4: Comparison with individual factors
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 4: COMPARISON WITH INDIVIDUAL FACTORS")
    print("=" * 70)

    from strategies.new_factors_research.research import run_xs_factor

    # Momentum (H-012 proxy)
    mom_ranking = closes.pct_change(60)
    mom_res = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)
    print(f"  H-012 (Momentum 60d, R5, N4):  Sharpe {mom_res['sharpe']:.2f}, "
          f"Ann {mom_res['annual_ret']:.1%}, DD {mom_res['max_dd']:.1%}")

    # Volume momentum (H-021 proxy)
    vol_short = volumes.rolling(5).mean()
    vol_long = volumes.rolling(20).mean()
    volmom_ranking = vol_short / vol_long
    volmom_res = run_xs_factor(closes, volmom_ranking, 3, 4, warmup=25)
    print(f"  H-021 (VolMom VS5/VL20, R3, N4): Sharpe {volmom_res['sharpe']:.2f}, "
          f"Ann {volmom_res['annual_ret']:.1%}, DD {volmom_res['max_dd']:.1%}")

    # Low vol (H-019 proxy)
    vol_ranking = -closes.pct_change().rolling(20).std()
    vol_res = run_xs_factor(closes, vol_ranking, 21, 3, warmup=25)
    print(f"  H-019 (LowVol V20, R21, N3):   Sharpe {vol_res['sharpe']:.2f}, "
          f"Ann {vol_res['annual_ret']:.1%}, DD {vol_res['max_dd']:.1%}")

    # ═══════════════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    all_results = []
    if len(ridge_df) > 0:
        all_results.append(("Ridge", ridge_df))
    if len(rf_df) > 0:
        all_results.append(("RF", rf_df))
    if len(gb_df) > 0:
        all_results.append(("GB", gb_df))

    for name, df in all_results:
        pos = df[df["sharpe"] > 0]
        print(f"\n  {name}:")
        print(f"    Positive Sharpe: {len(pos)}/{len(df)} ({len(pos)/len(df):.0%})")
        print(f"    Mean Sharpe: {df['sharpe'].mean():.2f}")
        print(f"    Best: {df.iloc[df['sharpe'].idxmax()]['tag']} "
              f"(Sharpe {df['sharpe'].max():.2f})")

    # Best overall
    all_combined = pd.concat([ridge_df, rf_df, gb_df], ignore_index=True)
    if len(all_combined) > 0:
        best = all_combined.iloc[all_combined['sharpe'].idxmax()]
        print(f"\n  BEST OVERALL: {best['tag']}")
        print(f"    Sharpe {best['sharpe']:.2f}, Ann {best['annual_ret']:.1%}, "
              f"DD {best['max_dd']:.1%}")

        # Compare with individual factors
        print(f"\n  vs Individual Factors:")
        print(f"    H-012 Momentum:  Sharpe {mom_res['sharpe']:.2f}")
        print(f"    H-021 VolMom:    Sharpe {volmom_res['sharpe']:.2f}")
        print(f"    H-019 LowVol:    Sharpe {vol_res['sharpe']:.2f}")
        print(f"    ML Best:         Sharpe {best['sharpe']:.2f}")

        if best['sharpe'] > max(mom_res['sharpe'], volmom_res['sharpe'], vol_res['sharpe']):
            print("\n  ✓ ML combination BEATS individual factors")
        else:
            print("\n  ✗ ML combination does NOT beat best individual factor")

    # Correlation analysis for best ML model
    if len(all_combined) > 0 and best['sharpe'] > 0.5:
        print("\n  Running correlation analysis for best model...")
        # Re-run best model to get equity curve
        best_row = all_combined.iloc[all_combined['sharpe'].idxmax()]
        # Determine model type and re-run
        if 'Ridge' in best_row['tag']:
            model_cls = Ridge
            params = {"alpha": best_row.get('alpha', 1.0)}
        elif 'RF' in best_row['tag']:
            model_cls = RandomForestRegressor
            params = {"n_estimators": int(best_row.get('n_est', 100)),
                     "max_depth": int(best_row.get('max_depth', 3)),
                     "random_state": 42, "n_jobs": -1}
        else:
            model_cls = GradientBoostingRegressor
            params = {"n_estimators": int(best_row.get('n_est', 100)),
                     "max_depth": int(best_row.get('max_depth', 3)),
                     "learning_rate": best_row.get('lr', 0.05),
                     "random_state": 42}

        feat_type = best_row.get('features', 'all')
        if feat_type == 'rank':
            feat_cols = feature_cols_rank
        elif feat_type == 'zscore':
            feat_cols = feature_cols_zscore
        else:
            feat_cols = feature_cols_all

        result, _ = walk_forward_ml(
            feat_df, closes, model_cls, params,
            train_window=365, test_window=90,
            rebal_freq=int(best_row.get('rebal', 5)),
            n_long=int(best_row['n_long']), n_short=int(best_row['n_long']),
            feature_cols=feat_cols
        )
        if result:
            corrs = compute_correlation_with_existing(result['equity'], closes)
            print(f"  Correlation with H-012: {corrs['corr_h012']}")

    print("\n" + "=" * 70)
    print("H-038 RESEARCH COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
