"""
Composite Multi-Factor Research (Session 2026-03-19, session 32)

H-030: Composite Multi-Factor Strategy
  - Combine confirmed factors: momentum (H-012), volume momentum (H-021), beta (H-024)
  - Cross-sectional z-score normalization before combining
  - Test weight combinations and rebalance frequencies
  - Compare single composite vs portfolio of individual strategies

H-031: Size Factor (Dollar Volume Proxy)
  - Long small assets (low avg dollar volume), short large ones, or vice versa
  - New dimension not yet explored
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
    hourly, daily = {}, {}
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


def rolling_walk_forward(closes, ranking_fn, rebal_freq, n_long, n_short=None,
                         train_days=360, test_days=80, n_folds=6):
    if n_short is None:
        n_short = n_long
    n = len(closes)
    fold_results = []
    for fold in range(n_folds):
        test_end = n - fold * test_days
        test_start = test_end - test_days
        train_start = test_start - train_days
        if train_start < 0:
            break
        test_closes = closes.iloc[test_start:test_end]
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
            "equity": result["equity"],
        })
        print(f"    Fold {fold+1}: Sharpe {result['sharpe']:.2f}, "
              f"Ann {result['annual_ret']:.1%}")
    if not fold_results:
        return None
    df = pd.DataFrame(fold_results)
    positive = (df["sharpe"] > 0).sum()
    print(f"    Positive folds: {positive}/{len(df)}, Mean OOS Sharpe: {df['sharpe'].mean():.2f}")
    return df


# ═══════════════════════════════════════════════════════════════════════
# Factor computation functions
# ═══════════════════════════════════════════════════════════════════════

def compute_momentum_ranking(closes, lookback):
    """Cross-sectional momentum: N-day return."""
    return closes.pct_change(lookback)


def compute_volume_momentum_ranking(closes, volumes, short_window, long_window):
    """Volume momentum: short-term / long-term average volume ratio."""
    vol_short = volumes.rolling(short_window).mean()
    vol_long = volumes.rolling(long_window).mean()
    return vol_short / vol_long


def compute_beta_ranking(closes, window):
    """Rolling beta vs BTC. Returns NEGATIVE beta (low-beta ranks high)."""
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


def compute_lowvol_ranking(closes, window):
    """Low-volatility: NEGATIVE realized vol (low vol ranks high)."""
    rets = closes.pct_change()
    realized_vol = rets.rolling(window).std()
    return -realized_vol


def xs_zscore(ranking_df):
    """Cross-sectional z-score normalization at each time point."""
    mean = ranking_df.mean(axis=1)
    std = ranking_df.std(axis=1)
    std = std.replace(0, np.nan)
    return ranking_df.sub(mean, axis=0).div(std, axis=0)


# ═══════════════════════════════════════════════════════════════════════
# H-030: Composite Multi-Factor
# ═══════════════════════════════════════════════════════════════════════

def h030_composite_factor(daily_data):
    print("\n" + "=" * 70)
    print("H-030: COMPOSITE MULTI-FACTOR (Momentum + Volume Momentum + Beta)")
    print("=" * 70)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().dropna()
    common = closes.columns.intersection(volumes.columns)
    closes = closes[common]
    volumes = volumes[common]
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    # ── Compute individual factor rankings ──
    print("\n  Computing individual factor rankings...")
    mom60 = compute_momentum_ranking(closes, 60)
    volmom_5_20 = compute_volume_momentum_ranking(closes, volumes, 5, 20)
    beta60 = compute_beta_ranking(closes, 60)
    lowvol20 = compute_lowvol_ranking(closes, 20)

    # Z-score normalize each factor cross-sectionally
    mom60_z = xs_zscore(mom60)
    volmom_z = xs_zscore(volmom_5_20)
    beta60_z = xs_zscore(beta60)
    lowvol20_z = xs_zscore(lowvol20)

    # ── Phase 1: Individual factor baselines ──
    print("\n  ── Individual factor baselines ──")
    warmup = 65

    baselines = {}
    for name, ranking, rebal, n in [
        ("Mom60_R5_N4", mom60, 5, 4),
        ("VolMom_R3_N4", volmom_5_20, 3, 4),
        ("Beta60_R21_N3", beta60, 21, 3),
        ("LowVol20_R21_N3", lowvol20, 21, 3),
    ]:
        res = run_xs_factor(closes, ranking, rebal, n, warmup=warmup)
        baselines[name] = res
        print(f"    {name}: Sharpe {res['sharpe']:.2f}, Ann {res['annual_ret']:.1%}, "
              f"DD {res['max_dd']:.1%}, trades {res['n_trades']}")

    # ── Phase 2: Two-factor composites ──
    print("\n  ── Two-factor composites (equal weight) ──")
    two_factor_combos = [
        ("Mom+VolMom", mom60_z, volmom_z),
        ("Mom+Beta", mom60_z, beta60_z),
        ("Mom+LowVol", mom60_z, lowvol20_z),
        ("VolMom+Beta", volmom_z, beta60_z),
        ("VolMom+LowVol", volmom_z, lowvol20_z),
        ("Beta+LowVol", beta60_z, lowvol20_z),
    ]

    two_factor_results = []
    for name, f1, f2 in two_factor_combos:
        for rebal in [3, 5, 7, 14, 21]:
            for n_long in [3, 4, 5]:
                composite = 0.5 * f1 + 0.5 * f2
                res = run_xs_factor(closes, composite, rebal, n_long, warmup=warmup)
                two_factor_results.append({
                    "combo": name, "rebal": rebal, "n": n_long,
                    "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
                    "max_dd": res["max_dd"], "n_trades": res["n_trades"],
                })

    df_2f = pd.DataFrame(two_factor_results)
    print(f"\n  Two-factor results ({len(df_2f)} total):")
    for combo in df_2f["combo"].unique():
        sub = df_2f[df_2f["combo"] == combo]
        pos = (sub["sharpe"] > 0).sum()
        best = sub.loc[sub["sharpe"].idxmax()]
        print(f"    {combo}: {pos}/{len(sub)} positive, "
              f"best Sharpe {best['sharpe']:.2f} (R{int(best['rebal'])}_N{int(best['n'])}), "
              f"mean {sub['sharpe'].mean():.2f}")

    # ── Phase 3: Three-factor composites ──
    print("\n  ── Three-factor composites ──")
    three_factor_results = []

    # Mom + VolMom + Beta (our 3 confirmed orthogonal factors)
    for w_mom in [0.2, 0.33, 0.4, 0.5]:
        for w_vol in [0.2, 0.33, 0.4, 0.5]:
            w_beta = round(1.0 - w_mom - w_vol, 2)
            if w_beta < 0.1 or w_beta > 0.6:
                continue
            composite = w_mom * mom60_z + w_vol * volmom_z + w_beta * beta60_z
            for rebal in [3, 5, 7]:
                for n_long in [3, 4, 5]:
                    res = run_xs_factor(closes, composite, rebal, n_long, warmup=warmup)
                    three_factor_results.append({
                        "w_mom": w_mom, "w_vol": w_vol, "w_beta": w_beta,
                        "rebal": rebal, "n": n_long,
                        "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
                        "max_dd": res["max_dd"], "n_trades": res["n_trades"],
                    })

    df_3f = pd.DataFrame(three_factor_results)
    n_positive = (df_3f["sharpe"] > 0).sum()
    print(f"  Total: {n_positive}/{len(df_3f)} positive Sharpe ({100*n_positive/len(df_3f):.0f}%)")
    if n_positive > 0:
        print(f"  Mean positive Sharpe: {df_3f[df_3f['sharpe']>0]['sharpe'].mean():.2f}")
        top5 = df_3f.nlargest(5, "sharpe")
        print(f"\n  Top 5 three-factor composites:")
        for _, row in top5.iterrows():
            print(f"    Mom={row['w_mom']:.2f}/Vol={row['w_vol']:.2f}/Beta={row['w_beta']:.2f} "
                  f"R{int(row['rebal'])}_N{int(row['n'])}: Sharpe {row['sharpe']:.2f}, "
                  f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    # ── Phase 4: Four-factor composite ──
    print("\n  ── Four-factor composite (all factors) ──")
    four_factor_results = []
    for w_mom in [0.25, 0.3, 0.35]:
        for w_vol in [0.25, 0.3, 0.35]:
            for w_beta in [0.15, 0.2, 0.25]:
                w_lowvol = round(1.0 - w_mom - w_vol - w_beta, 2)
                if w_lowvol < 0.05 or w_lowvol > 0.35:
                    continue
                composite = w_mom * mom60_z + w_vol * volmom_z + w_beta * beta60_z + w_lowvol * lowvol20_z
                for rebal in [3, 5, 7]:
                    for n_long in [3, 4, 5]:
                        res = run_xs_factor(closes, composite, rebal, n_long, warmup=warmup)
                        four_factor_results.append({
                            "w_mom": w_mom, "w_vol": w_vol, "w_beta": w_beta,
                            "w_lowvol": w_lowvol,
                            "rebal": rebal, "n": n_long,
                            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
                            "max_dd": res["max_dd"], "n_trades": res["n_trades"],
                        })

    df_4f = pd.DataFrame(four_factor_results)
    n_positive = (df_4f["sharpe"] > 0).sum()
    print(f"  Total: {n_positive}/{len(df_4f)} positive Sharpe ({100*n_positive/len(df_4f):.0f}%)")
    if n_positive > 0:
        top5 = df_4f.nlargest(5, "sharpe")
        print(f"\n  Top 5 four-factor composites:")
        for _, row in top5.iterrows():
            print(f"    Mom={row['w_mom']:.2f}/Vol={row['w_vol']:.2f}/Beta={row['w_beta']:.2f}/LV={row['w_lowvol']:.2f} "
                  f"R{int(row['rebal'])}_N{int(row['n'])}: Sharpe {row['sharpe']:.2f}, "
                  f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    # ── Phase 5: Walk-forward on best composite ──
    # Find best 3-factor and best 4-factor, run WF on each
    best_configs = []
    if len(df_3f) > 0 and (df_3f["sharpe"] > 0).any():
        best_3f = df_3f.loc[df_3f["sharpe"].idxmax()]
        best_configs.append(("3-factor", best_3f))
    if len(df_4f) > 0 and (df_4f["sharpe"] > 0).any():
        best_4f = df_4f.loc[df_4f["sharpe"].idxmax()]
        best_configs.append(("4-factor", best_4f))

    # Also test the best 2-factor
    if len(df_2f) > 0 and (df_2f["sharpe"] > 0).any():
        best_2f = df_2f.loc[df_2f["sharpe"].idxmax()]
        best_configs.append(("2-factor", best_2f))

    wf_results = {}
    for label, best in best_configs:
        print(f"\n  ── Walk-Forward: {label} (best IS) ──")
        rebal = int(best["rebal"])
        n_long = int(best["n"])

        if label == "3-factor":
            w_m, w_v, w_b = best["w_mom"], best["w_vol"], best["w_beta"]
            def ranking_fn(c, vols=volumes):
                v = vols.reindex(c.index).ffill().dropna()
                common_cols = c.columns.intersection(v.columns)
                c_sub, v_sub = c[common_cols], v[common_cols]
                m = xs_zscore(compute_momentum_ranking(c_sub, 60))
                vm = xs_zscore(compute_volume_momentum_ranking(c_sub, v_sub, 5, 20))
                b = xs_zscore(compute_beta_ranking(c_sub, 60))
                return w_m * m + w_v * vm + w_b * b
        elif label == "4-factor":
            w_m, w_v, w_b, w_l = best["w_mom"], best["w_vol"], best["w_beta"], best["w_lowvol"]
            def ranking_fn(c, vols=volumes):
                v = vols.reindex(c.index).ffill().dropna()
                common_cols = c.columns.intersection(v.columns)
                c_sub, v_sub = c[common_cols], v[common_cols]
                m = xs_zscore(compute_momentum_ranking(c_sub, 60))
                vm = xs_zscore(compute_volume_momentum_ranking(c_sub, v_sub, 5, 20))
                b = xs_zscore(compute_beta_ranking(c_sub, 60))
                lv = xs_zscore(compute_lowvol_ranking(c_sub, 20))
                return w_m * m + w_v * vm + w_b * b + w_l * lv
        else:
            combo_name = best["combo"]
            factor_map = {
                "Mom+VolMom": (mom60_z, volmom_z),
                "Mom+Beta": (mom60_z, beta60_z),
                "Mom+LowVol": (mom60_z, lowvol20_z),
                "VolMom+Beta": (volmom_z, beta60_z),
                "VolMom+LowVol": (volmom_z, lowvol20_z),
                "Beta+LowVol": (beta60_z, lowvol20_z),
            }
            f1_base, f2_base = combo_name.split("+")
            factor_fns = {
                "Mom": lambda c, v=None: xs_zscore(compute_momentum_ranking(c, 60)),
                "VolMom": lambda c, v=volumes: xs_zscore(compute_volume_momentum_ranking(
                    c, v.reindex(c.index).ffill().dropna()[c.columns.intersection(v.columns)], 5, 20)),
                "Beta": lambda c, v=None: xs_zscore(compute_beta_ranking(c, 60)),
                "LowVol": lambda c, v=None: xs_zscore(compute_lowvol_ranking(c, 20)),
            }
            fn1 = factor_fns[f1_base]
            fn2 = factor_fns[f2_base]
            def ranking_fn(c, vols=volumes, _fn1=fn1, _fn2=fn2):
                v = vols.reindex(c.index).ffill().dropna()
                common_cols = c.columns.intersection(v.columns)
                c_sub = c[common_cols]
                return 0.5 * _fn1(c_sub) + 0.5 * _fn2(c_sub)

        wf = rolling_walk_forward(closes, ranking_fn, rebal, n_long, n_long,
                                  train_days=360, test_days=80, n_folds=6)
        if wf is not None:
            wf_results[label] = wf

    # ── Phase 6: Correlation with existing strategies ──
    print("\n  ── Correlation Analysis ──")
    # Run individual factors at their best params for correlation comparison
    res_mom = run_xs_factor(closes, mom60, 5, 4, warmup=warmup)
    res_volmom = run_xs_factor(closes, volmom_5_20, 3, 4, warmup=warmup)
    res_beta = run_xs_factor(closes, beta60, 21, 3, warmup=warmup)

    strategy_equities = {
        "H-012 (Mom)": res_mom["equity"],
        "H-021 (VolMom)": res_volmom["equity"],
        "H-024 (Beta)": res_beta["equity"],
    }

    # Add best composite(s)
    for label, best in best_configs:
        if label == "3-factor":
            w_m, w_v, w_b = best["w_mom"], best["w_vol"], best["w_beta"]
            composite = w_m * mom60_z + w_v * volmom_z + w_b * beta60_z
        elif label == "4-factor":
            w_m, w_v, w_b, w_l = best["w_mom"], best["w_vol"], best["w_beta"], best["w_lowvol"]
            composite = w_m * mom60_z + w_v * volmom_z + w_b * beta60_z + w_l * lowvol20_z
        else:
            continue
        res_comp = run_xs_factor(closes, composite, int(best["rebal"]), int(best["n"]),
                                 warmup=warmup)
        strategy_equities[f"Composite ({label})"] = res_comp["equity"]

    # Compute pairwise correlations
    rets_dict = {}
    for name, eq in strategy_equities.items():
        r = eq.pct_change().dropna()
        r = r[r.index.isin(closes.index)]
        rets_dict[name] = r

    common_idx = rets_dict[list(rets_dict.keys())[0]].index
    for name, r in rets_dict.items():
        common_idx = common_idx.intersection(r.index)

    if len(common_idx) > 50:
        corr_df = pd.DataFrame({name: rets.loc[common_idx] for name, rets in rets_dict.items()})
        print(f"\n  Correlation matrix ({len(common_idx)} common days):")
        corr_matrix = corr_df.corr()
        print(corr_matrix.round(3).to_string())

    # ── Phase 7: Portfolio comparison ──
    # Compare: (a) Portfolio of 3 individual strategies vs (b) Single composite
    print("\n  ── Portfolio vs Composite Comparison ──")

    # Portfolio of 3 individual strategies (equal weight for simplicity)
    eq_mom = res_mom["equity"]
    eq_vol = res_volmom["equity"]
    eq_beta = res_beta["equity"]

    common_dates = eq_mom.index.intersection(eq_vol.index).intersection(eq_beta.index)
    port_equity = (eq_mom.loc[common_dates] + eq_vol.loc[common_dates] + eq_beta.loc[common_dates]) / 3
    port_metrics = compute_metrics(port_equity)
    print(f"  Portfolio (equal weight 3 strategies): Sharpe {port_metrics['sharpe']:.2f}, "
          f"Ann {port_metrics['annual_ret']:.1%}, DD {port_metrics['max_dd']:.1%}")

    for label, best in best_configs:
        if label in ["3-factor", "4-factor"]:
            equity = strategy_equities[f"Composite ({label})"]
            m = compute_metrics(equity)
            print(f"  Composite ({label}): Sharpe {m['sharpe']:.2f}, "
                  f"Ann {m['annual_ret']:.1%}, DD {m['max_dd']:.1%}")

    return {
        "two_factor": df_2f,
        "three_factor": df_3f,
        "four_factor": df_4f,
        "walk_forward": wf_results,
        "baselines": baselines,
    }


# ═══════════════════════════════════════════════════════════════════════
# H-031: Size Factor (Dollar Volume Proxy)
# ═══════════════════════════════════════════════════════════════════════

def h031_size_factor(daily_data):
    print("\n" + "=" * 70)
    print("H-031: SIZE FACTOR (Dollar Volume Proxy)")
    print("=" * 70)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().dropna()
    common = closes.columns.intersection(volumes.columns)
    closes = closes[common]
    volumes = volumes[common]
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    # Dollar volume = close * volume
    dollar_volume = closes * volumes

    results = []
    params_tested = 0

    # Test both directions: long small (negative ranking) and long large (positive ranking)
    for direction_name, direction in [("long_small", -1), ("long_large", 1)]:
        for window in [10, 20, 30, 60]:
            avg_dv = dollar_volume.rolling(window).mean()
            ranking = avg_dv * direction  # positive direction = long large cap

            for rebal in [5, 7, 14, 21]:
                for n_long in [3, 4, 5]:
                    params_tested += 1
                    warmup = max(window + 5, 65)
                    res = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup)
                    results.append({
                        "direction": direction_name, "window": window,
                        "rebal": rebal, "n": n_long,
                        "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
                        "max_dd": res["max_dd"], "n_trades": res["n_trades"],
                    })

    df_results = pd.DataFrame(results)
    n_positive = (df_results["sharpe"] > 0).sum()
    print(f"\n  SUMMARY: {n_positive}/{params_tested} positive Sharpe ({100*n_positive/params_tested:.0f}%)")

    for direction in ["long_small", "long_large"]:
        sub = df_results[df_results["direction"] == direction]
        pos = (sub["sharpe"] > 0).sum()
        print(f"    {direction}: {pos}/{len(sub)} positive")
        if pos > 0:
            best = sub.loc[sub["sharpe"].idxmax()]
            print(f"      Best: W{int(best['window'])}_R{int(best['rebal'])}_N{int(best['n'])}: "
                  f"Sharpe {best['sharpe']:.2f}, Ann {best['annual_ret']:.1%}, DD {best['max_dd']:.1%}")

    # Walk-forward on best if promising
    if n_positive > len(df_results) * 0.5:  # >50% positive = promising
        best_overall = df_results.loc[df_results["sharpe"].idxmax()]
        direction = 1 if best_overall["direction"] == "long_large" else -1
        window = int(best_overall["window"])
        rebal = int(best_overall["rebal"])
        n_long = int(best_overall["n"])
        print(f"\n  Walk-Forward: {best_overall['direction']} W{window}_R{rebal}_N{n_long}")

        def size_ranking_fn(c, vols=volumes, w=window, d=direction):
            v = vols.reindex(c.index).ffill().dropna()
            common_cols = c.columns.intersection(v.columns)
            dv = c[common_cols] * v[common_cols]
            return dv.rolling(w).mean() * d

        wf = rolling_walk_forward(closes, size_ranking_fn, rebal, n_long, n_long,
                                  train_days=360, test_days=80, n_folds=6)

        if wf is not None:
            # Correlation with existing strategies
            best_ranking = dollar_volume.rolling(window).mean() * direction
            res_size = run_xs_factor(closes, best_ranking, rebal, n_long, warmup=65)

            mom60 = compute_momentum_ranking(closes, 60)
            res_mom = run_xs_factor(closes, mom60, 5, 4, warmup=65)

            rets_size = res_size["equity"].pct_change().dropna()
            rets_mom = res_mom["equity"].pct_change().dropna()
            common = rets_size.index.intersection(rets_mom.index)
            if len(common) > 50:
                corr = rets_size.loc[common].corr(rets_mom.loc[common])
                print(f"    Correlation with H-012 (momentum): {corr:.3f}")

    return df_results


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Loading data...")
    hourly, daily = load_all_data()
    print(f"\nLoaded {len(daily)} assets")

    # ── H-030: Composite Multi-Factor ──
    print("\n" + "█" * 70)
    print("FACTOR 1: H-030 COMPOSITE MULTI-FACTOR")
    print("█" * 70)
    h030_results = h030_composite_factor(daily)

    # ── H-031: Size Factor ──
    print("\n" + "█" * 70)
    print("FACTOR 2: H-031 SIZE FACTOR")
    print("█" * 70)
    h031_results = h031_size_factor(daily)

    print("\n" + "█" * 70)
    print("RESEARCH COMPLETE")
    print("█" * 70)
