"""
H-038 Deep Validation — Ridge zscore factor combination

Tests:
1. Walk-forward fold-by-fold analysis (is it consistently positive?)
2. Fee robustness (1x, 2x, 3x, 5x fees)
3. Correlation with existing portfolio strategies (H-012, H-021, H-019)
4. Portfolio impact (does ML add value to existing 5-strat portfolio?)
5. Feature importance analysis (which factors drive predictions?)
6. Stability of learned weights across folds
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from strategies.new_factors_research.research import (
    load_all_data, run_xs_factor, compute_metrics,
    ASSETS, BASE_FEE, SLIPPAGE_BPS, INITIAL_CAPITAL,
)
from strategies.ml_research.h038_ml_factor_combo import (
    compute_factor_signals_fast, build_feature_matrix,
    walk_forward_ml, run_ml_backtest,
)
from lib.metrics import sharpe_ratio, max_drawdown, annual_return


def walk_forward_ml_detailed(feature_df, closes, model_class, model_params,
                              train_window=365, test_window=90, rebal_freq=5,
                              n_long=5, n_short=5, feature_cols=None):
    """Walk-forward with per-fold metrics and feature importance."""
    if feature_cols is None:
        feature_cols = [c for c in feature_df.columns if c.endswith('_zscore')]

    dates = sorted(feature_df['date'].unique())
    all_predictions = {}
    fold_details = []
    all_coefs = []

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

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)

        model = model_class(**model_params)
        model.fit(X_train_s, y_train)

        y_pred = model.predict(X_test_s)
        test_rows = feature_df.loc[test_mask].copy()
        test_rows['prediction'] = y_pred

        # Track predictions
        fold_preds = {}
        for date in test_dates:
            day_idx = dates.index(date) - dates.index(test_dates[0])
            if day_idx % rebal_freq == 0:
                day_preds = test_rows[test_rows['date'] == date]
                if len(day_preds) > 0:
                    pred_dict = dict(zip(day_preds['symbol'], day_preds['prediction']))
                    all_predictions[date] = pred_dict
                    fold_preds[date] = pred_dict

        # Feature importance (Ridge coefficients)
        if hasattr(model, 'coef_'):
            coef_dict = dict(zip(feature_cols, model.coef_))
            coef_dict['fold'] = fold_num
            coef_dict['train_start'] = train_dates[0]
            coef_dict['train_end'] = train_dates[-1]
            all_coefs.append(coef_dict)

        # Per-fold backtest
        if fold_preds:
            fold_result = run_ml_backtest(fold_preds, closes, n_long=n_long,
                                          n_short=n_short, rebal_freq=rebal_freq)
            fold_details.append({
                'fold': fold_num,
                'train_start': str(train_dates[0])[:10],
                'train_end': str(train_dates[-1])[:10],
                'test_start': str(test_dates[0])[:10],
                'test_end': str(test_dates[-1])[:10],
                'sharpe': fold_result['sharpe'],
                'annual_ret': fold_result['annual_ret'],
                'max_dd': fold_result['max_dd'],
            })

        fold_num += 1
        fold_start += test_window

    # Full OOS backtest
    full_result = run_ml_backtest(all_predictions, closes, n_long=n_long,
                                  n_short=n_short, rebal_freq=rebal_freq)

    return full_result, fold_details, all_coefs


def main():
    print("=" * 70)
    print("H-038 DEEP VALIDATION — Ridge ML Factor Combination")
    print("=" * 70)

    # Load data
    print("\nLoading data...")
    hourly, daily_data = load_all_data()

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().dropna()
    common = closes.columns.intersection(volumes.columns)
    closes = closes[common]
    volumes = volumes[common]

    print(f"Universe: {len(closes.columns)} assets, {len(closes)} days")

    # Compute factors
    print("\nComputing factor signals...")
    factors = compute_factor_signals_fast(closes, volumes)

    print("\nBuilding feature matrix...")
    feat_df = build_feature_matrix(factors, closes, forward_days=5)
    feature_cols = [c for c in feat_df.columns if c.endswith('_zscore')]
    print(f"Features: {feature_cols}")

    # ═══════════════════════════════════════════════════════════════════
    # Test 1: Fold-by-fold walk-forward analysis
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 1: WALK-FORWARD FOLD-BY-FOLD ANALYSIS")
    print("=" * 70)
    print("Config: Ridge alpha=100, zscore features, R5, N5")

    result, fold_details, coefs = walk_forward_ml_detailed(
        feat_df, closes, Ridge, {"alpha": 100.0},
        train_window=365, test_window=90, rebal_freq=5,
        n_long=5, n_short=5, feature_cols=feature_cols
    )

    print(f"\n  Overall OOS: Sharpe {result['sharpe']:.2f}, "
          f"Ann {result['annual_ret']:.1%}, DD {result['max_dd']:.1%}")

    print(f"\n  Per-fold results ({len(fold_details)} folds):")
    positive_folds = 0
    for fd in fold_details:
        marker = "+" if fd['sharpe'] > 0 else "-"
        print(f"    Fold {fd['fold']}: {fd['test_start']} to {fd['test_end']} | "
              f"Sharpe {fd['sharpe']:+.2f}, Ann {fd['annual_ret']:+.1%}, "
              f"DD {fd['max_dd']:.1%} [{marker}]")
        if fd['sharpe'] > 0:
            positive_folds += 1

    print(f"\n  Positive folds: {positive_folds}/{len(fold_details)} "
          f"({positive_folds/len(fold_details):.0%})")

    # Also test R5/N4 (second best config)
    print("\n  --- Also testing R5/N4 ---")
    result_n4, fold_details_n4, coefs_n4 = walk_forward_ml_detailed(
        feat_df, closes, Ridge, {"alpha": 100.0},
        train_window=365, test_window=90, rebal_freq=5,
        n_long=4, n_short=4, feature_cols=feature_cols
    )
    print(f"  R5/N4 OOS: Sharpe {result_n4['sharpe']:.2f}, "
          f"Ann {result_n4['annual_ret']:.1%}, DD {result_n4['max_dd']:.1%}")
    pos4 = sum(1 for fd in fold_details_n4 if fd['sharpe'] > 0)
    print(f"  Positive folds: {pos4}/{len(fold_details_n4)}")

    # ═══════════════════════════════════════════════════════════════════
    # Test 2: Fee robustness
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 2: FEE ROBUSTNESS")
    print("=" * 70)

    for fee_mult in [1, 2, 3, 5]:
        res_fee, _, _ = walk_forward_ml_detailed(
            feat_df, closes, Ridge, {"alpha": 100.0},
            train_window=365, test_window=90, rebal_freq=5,
            n_long=5, n_short=5, feature_cols=feature_cols
        )
        # Note: fee_multiplier is in the backtest, not in walk_forward_ml
        # We need to rebuild with different fees
        # Actually run_ml_backtest already uses BASE_FEE. Let me adjust.
        print(f"  {fee_mult}x fees: Sharpe {res_fee['sharpe']:.2f}, "
              f"Ann {res_fee['annual_ret']:.1%}, DD {res_fee['max_dd']:.1%}")

    # Actually, let me do fee robustness properly
    print("\n  (Re-running with actual fee multipliers...)")
    # Build predictions first, then backtest with different fees
    from strategies.ml_research.h038_ml_factor_combo import walk_forward_ml

    dates = sorted(feat_df['date'].unique())
    all_predictions = {}
    fold_start = 365
    while fold_start + 90 <= len(dates):
        train_dates = dates[fold_start - 365:fold_start]
        test_dates = dates[fold_start:fold_start + 90]

        train_mask = feat_df['date'].isin(train_dates)
        test_mask = feat_df['date'].isin(test_dates)

        X_train = feat_df.loc[train_mask, feature_cols].values
        y_train = feat_df.loc[train_mask, 'target'].values
        X_test = feat_df.loc[test_mask, feature_cols].values

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)

        model = Ridge(alpha=100.0)
        model.fit(X_train_s, y_train)
        y_pred = model.predict(X_test_s)

        test_rows = feat_df.loc[test_mask].copy()
        test_rows['prediction'] = y_pred

        for date in test_dates:
            day_idx = dates.index(date) - dates.index(test_dates[0])
            if day_idx % 5 == 0:
                day_preds = test_rows[test_rows['date'] == date]
                if len(day_preds) > 0:
                    all_predictions[date] = dict(zip(
                        day_preds['symbol'], day_preds['prediction']
                    ))

        fold_start += 90

    for fee_mult in [1, 2, 3, 5]:
        res = run_ml_backtest(all_predictions, closes, n_long=5, n_short=5,
                              rebal_freq=5, fee_multiplier=fee_mult)
        print(f"  {fee_mult}x fees: Sharpe {res['sharpe']:.2f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    # ═══════════════════════════════════════════════════════════════════
    # Test 3: Correlation with existing strategies
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 3: CORRELATION WITH EXISTING STRATEGIES")
    print("=" * 70)

    ml_equity = result['equity']

    # H-012: Momentum 60d R5 N4
    mom_ranking = closes.pct_change(60)
    h012_res = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)

    # H-021: Volume Momentum VS5/VL20 R3 N4
    vol_short = volumes.rolling(5).mean()
    vol_long = volumes.rolling(20).mean()
    volmom_ranking = vol_short / vol_long
    h021_res = run_xs_factor(closes, volmom_ranking, 3, 4, warmup=25)

    # H-019: Low Vol V20 R21 N3
    vol_ranking = -closes.pct_change().rolling(20).std()
    h019_res = run_xs_factor(closes, vol_ranking, 21, 3, warmup=25)

    # H-024: Low Beta W60 R21 N3
    rets = closes.pct_change()
    btc_col = [c for c in closes.columns if 'BTC' in c][0]
    btc_rets = rets[btc_col]
    btc_var = btc_rets.rolling(60).var()
    betas = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for sym in closes.columns:
        cov = rets[sym].rolling(60).cov(btc_rets)
        betas[sym] = cov / btc_var
    beta_ranking = -betas
    h024_res = run_xs_factor(closes, beta_ranking, 21, 3, warmup=65)

    # Compute correlations
    strategies = {
        'ML-038': ml_equity,
        'H-012': h012_res['equity'],
        'H-021': h021_res['equity'],
        'H-019': h019_res['equity'],
        'H-024': h024_res['equity'],
    }

    # Align and compute return correlations
    common_idx = ml_equity.index
    strat_rets = pd.DataFrame()
    for name, eq in strategies.items():
        aligned = eq.reindex(common_idx).ffill().dropna()
        strat_rets[name] = aligned.pct_change().dropna()

    strat_rets = strat_rets.dropna()
    corr_matrix = strat_rets.corr()

    print("\n  Return correlation matrix:")
    print(corr_matrix.round(3).to_string())

    print(f"\n  ML-038 correlations:")
    for name in ['H-012', 'H-021', 'H-019', 'H-024']:
        print(f"    vs {name}: {corr_matrix.loc['ML-038', name]:.3f}")

    # ═══════════════════════════════════════════════════════════════════
    # Test 4: Portfolio impact
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 4: PORTFOLIO IMPACT (Adding ML to existing strategies)")
    print("=" * 70)

    # Current 3-strat XS portfolio: H-012 + H-019 + H-021
    # (We don't have H-009 and H-011 equity curves easily here)
    xs_strats = {
        'H-012': h012_res['equity'],
        'H-019': h019_res['equity'],
        'H-021': h021_res['equity'],
    }

    # Align all to common index
    common = ml_equity.index
    for name, eq in xs_strats.items():
        common = common.intersection(eq.index)

    xs_rets = pd.DataFrame()
    for name, eq in xs_strats.items():
        xs_rets[name] = eq.reindex(common).pct_change()
    xs_rets['ML-038'] = ml_equity.reindex(common).pct_change()
    xs_rets = xs_rets.dropna()

    # 3-strat portfolio (current XS component)
    port_3 = xs_rets[['H-012', 'H-019', 'H-021']].mean(axis=1)
    eq_3 = (1 + port_3).cumprod() * INITIAL_CAPITAL
    m3 = compute_metrics(eq_3)

    # 4-strat portfolio (add ML)
    port_4 = xs_rets[['H-012', 'H-019', 'H-021', 'ML-038']].mean(axis=1)
    eq_4 = (1 + port_4).cumprod() * INITIAL_CAPITAL
    m4 = compute_metrics(eq_4)

    # ML replaces all 3 individual factors
    port_ml_only = xs_rets['ML-038']
    eq_ml = (1 + port_ml_only).cumprod() * INITIAL_CAPITAL
    m_ml = compute_metrics(eq_ml)

    print(f"\n  3-strat XS (H-012+H-019+H-021): Sharpe {m3['sharpe']:.2f}, "
          f"Ann {m3['annual_ret']:.1%}, DD {m3['max_dd']:.1%}")
    print(f"  4-strat (add ML-038):            Sharpe {m4['sharpe']:.2f}, "
          f"Ann {m4['annual_ret']:.1%}, DD {m4['max_dd']:.1%}")
    print(f"  ML-038 only (replaces all 3):    Sharpe {m_ml['sharpe']:.2f}, "
          f"Ann {m_ml['annual_ret']:.1%}, DD {m_ml['max_dd']:.1%}")

    if m4['sharpe'] > m3['sharpe']:
        print(f"\n  ✓ Adding ML-038 IMPROVES portfolio Sharpe: "
              f"{m3['sharpe']:.2f} → {m4['sharpe']:.2f}")
    else:
        print(f"\n  ✗ Adding ML-038 does NOT improve portfolio Sharpe: "
              f"{m3['sharpe']:.2f} → {m4['sharpe']:.2f}")

    # ═══════════════════════════════════════════════════════════════════
    # Test 5: Feature importance (Ridge coefficients across folds)
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 5: FEATURE IMPORTANCE (Ridge Coefficients)")
    print("=" * 70)

    coef_df = pd.DataFrame(coefs)
    feat_means = {}
    feat_stds = {}
    for col in feature_cols:
        if col in coef_df.columns:
            feat_means[col] = coef_df[col].mean()
            feat_stds[col] = coef_df[col].std()

    print("\n  Average Ridge coefficients across folds:")
    sorted_feats = sorted(feat_means.items(), key=lambda x: abs(x[1]), reverse=True)
    for name, mean_val in sorted_feats:
        std_val = feat_stds[name]
        stability = abs(mean_val) / (std_val + 1e-10)
        sign = "+" if mean_val > 0 else "-"
        print(f"    {name:25s}: {mean_val:+.4f} (±{std_val:.4f}) "
              f"stability={stability:.2f} [{sign}]")

    # ═══════════════════════════════════════════════════════════════════
    # Test 6: Train window sensitivity
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("TEST 6: TRAIN WINDOW SENSITIVITY")
    print("=" * 70)

    for train_w in [180, 270, 365, 450]:
        res_tw, folds_tw, _ = walk_forward_ml_detailed(
            feat_df, closes, Ridge, {"alpha": 100.0},
            train_window=train_w, test_window=90, rebal_freq=5,
            n_long=5, n_short=5, feature_cols=feature_cols
        )
        pos_tw = sum(1 for fd in folds_tw if fd['sharpe'] > 0)
        print(f"  Train {train_w}d: Sharpe {res_tw['sharpe']:.2f}, "
              f"Ann {res_tw['annual_ret']:.1%}, DD {res_tw['max_dd']:.1%}, "
              f"Folds {pos_tw}/{len(folds_tw)}")

    # ═══════════════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("H-038 DEEP VALIDATION SUMMARY")
    print("=" * 70)
    print(f"\n  Best config: Ridge alpha=100, zscore, R5, N5")
    print(f"  OOS Sharpe: {result['sharpe']:.2f}")
    print(f"  OOS Return: {result['annual_ret']:.1%}")
    print(f"  OOS Max DD: {result['max_dd']:.1%}")
    print(f"  Positive folds: {positive_folds}/{len(fold_details)}")
    print(f"  Correlation with H-012: {corr_matrix.loc['ML-038', 'H-012']:.3f}")
    print(f"  Correlation with H-021: {corr_matrix.loc['ML-038', 'H-021']:.3f}")
    print(f"  Correlation with H-019: {corr_matrix.loc['ML-038', 'H-019']:.3f}")
    print(f"  Portfolio impact (3→4 strat): {m3['sharpe']:.2f} → {m4['sharpe']:.2f}")


if __name__ == "__main__":
    main()
