"""
Deep validation of H-030 and H-031 findings (Session 2026-03-19, session 32)

1. H-030 deeper WF with 6 folds (not just 4)
2. H-031 WF and correlation analysis
3. Key question: Does composite replace 3 separate XS strategies?
4. Key question: Is size factor (H-031) a new alpha source or redundant?
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
                continue
            hourly[sym] = df
            daily[sym] = resample_to_daily(df)
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
            "fold": fold + 1,
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


def xs_zscore(ranking_df):
    mean = ranking_df.mean(axis=1)
    std = ranking_df.std(axis=1).replace(0, np.nan)
    return ranking_df.sub(mean, axis=0).div(std, axis=0)


def compute_momentum_ranking(closes, lookback):
    return closes.pct_change(lookback)


def compute_volume_momentum_ranking(closes, volumes, short_window, long_window):
    vol_short = volumes.rolling(short_window).mean()
    vol_long = volumes.rolling(long_window).mean()
    return vol_short / vol_long


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


def compute_lowvol_ranking(closes, window):
    rets = closes.pct_change()
    return -rets.rolling(window).std()


if __name__ == "__main__":
    print("Loading data...")
    hourly, daily = load_all_data()
    print(f"Loaded {len(daily)} assets")

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().dropna()
    common = closes.columns.intersection(volumes.columns)
    closes = closes[common]
    volumes = volumes[common]
    print(f"Universe: {len(closes.columns)} assets, {len(closes)} days")

    # ═══════════════════════════════════════════════════════════════════
    # 1. H-030: Extended WF with shorter train window to get 6 folds
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("H-030: EXTENDED WALK-FORWARD VALIDATION")
    print("=" * 70)

    # Best 3-factor: Mom=0.33/Vol=0.33/Beta=0.34 R3_N5
    w_m, w_v, w_b = 0.33, 0.33, 0.34

    def composite_3f_ranking(c, vols=volumes):
        v = vols.reindex(c.index).ffill().dropna()
        common_cols = c.columns.intersection(v.columns)
        c_sub, v_sub = c[common_cols], v[common_cols]
        m = xs_zscore(compute_momentum_ranking(c_sub, 60))
        vm = xs_zscore(compute_volume_momentum_ranking(c_sub, v_sub, 5, 20))
        b = xs_zscore(compute_beta_ranking(c_sub, 60))
        return 0.33 * m + 0.33 * vm + 0.34 * b

    # WF with 180d train (to get 6 folds)
    print("\n  3-factor WF (180d train, 80d test, 6 folds):")
    wf_3f_180 = rolling_walk_forward(closes, composite_3f_ranking, 3, 5, 5,
                                      train_days=180, test_days=80, n_folds=6)

    # WF with 360d train (fewer folds but more robust)
    print("\n  3-factor WF (360d train, 80d test):")
    wf_3f_360 = rolling_walk_forward(closes, composite_3f_ranking, 3, 5, 5,
                                      train_days=360, test_days=80, n_folds=6)

    # Best 4-factor: Mom=0.30/Vol=0.35/Beta=0.25/LV=0.10 R3_N5
    def composite_4f_ranking(c, vols=volumes):
        v = vols.reindex(c.index).ffill().dropna()
        common_cols = c.columns.intersection(v.columns)
        c_sub, v_sub = c[common_cols], v[common_cols]
        m = xs_zscore(compute_momentum_ranking(c_sub, 60))
        vm = xs_zscore(compute_volume_momentum_ranking(c_sub, v_sub, 5, 20))
        b = xs_zscore(compute_beta_ranking(c_sub, 60))
        lv = xs_zscore(compute_lowvol_ranking(c_sub, 20))
        return 0.30 * m + 0.35 * vm + 0.25 * b + 0.10 * lv

    print("\n  4-factor WF (180d train, 80d test, 6 folds):")
    wf_4f_180 = rolling_walk_forward(closes, composite_4f_ranking, 3, 5, 5,
                                      train_days=180, test_days=80, n_folds=6)

    # ── Fee sensitivity for composites ──
    print("\n  Fee Sensitivity:")
    mom60_z = xs_zscore(compute_momentum_ranking(closes, 60))
    volmom_z = xs_zscore(compute_volume_momentum_ranking(closes, volumes, 5, 20))
    beta60_z = xs_zscore(compute_beta_ranking(closes, 60))
    lowvol20_z = xs_zscore(compute_lowvol_ranking(closes, 20))

    composite_3f = 0.33 * mom60_z + 0.33 * volmom_z + 0.34 * beta60_z
    composite_4f = 0.30 * mom60_z + 0.35 * volmom_z + 0.25 * beta60_z + 0.10 * lowvol20_z

    for fee_mult in [1.0, 2.0, 3.0, 5.0]:
        r3 = run_xs_factor(closes, composite_3f, 3, 5, fee_multiplier=fee_mult, warmup=65)
        r4 = run_xs_factor(closes, composite_4f, 3, 5, fee_multiplier=fee_mult, warmup=65)
        print(f"    {fee_mult}x fees: 3-factor Sharpe {r3['sharpe']:.2f}, "
              f"4-factor Sharpe {r4['sharpe']:.2f}")

    # ── Robustness: test nearby param sets ──
    print("\n  Param Neighborhood Robustness (3-factor, ±0.1 weight shifts):")
    robust_results = []
    for w_m in [0.23, 0.33, 0.43]:
        for w_v in [0.23, 0.33, 0.43]:
            w_b = round(1.0 - w_m - w_v, 2)
            if w_b < 0.05 or w_b > 0.55:
                continue
            composite = w_m * mom60_z + w_v * volmom_z + w_b * beta60_z
            for rebal in [3, 5]:
                for n_long in [4, 5]:
                    res = run_xs_factor(closes, composite, rebal, n_long, warmup=65)
                    robust_results.append({
                        "w_mom": w_m, "w_vol": w_v, "w_beta": w_b,
                        "rebal": rebal, "n": n_long, "sharpe": res["sharpe"],
                    })

    df_robust = pd.DataFrame(robust_results)
    n_pos = (df_robust["sharpe"] > 0).sum()
    print(f"    {n_pos}/{len(df_robust)} positive ({100*n_pos/len(df_robust):.0f}%), "
          f"mean Sharpe {df_robust['sharpe'].mean():.2f}, min {df_robust['sharpe'].min():.2f}")

    # ═══════════════════════════════════════════════════════════════════
    # 2. H-031: Size Factor Deep Validation
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("H-031: SIZE FACTOR DEEP VALIDATION")
    print("=" * 70)

    dollar_volume = closes * volumes

    # Best params: long_large W30_R5_N5
    print("\n  Walk-Forward (W30_R5_N5, long large):")
    def size_ranking_fn(c, vols=volumes):
        v = vols.reindex(c.index).ffill().dropna()
        common_cols = c.columns.intersection(v.columns)
        dv = c[common_cols] * v[common_cols]
        return dv.rolling(30).mean()

    wf_size = rolling_walk_forward(closes, size_ranking_fn, 5, 5, 5,
                                    train_days=360, test_days=80, n_folds=6)

    # Also test W30_R5_N4 and W30_R7_N5
    print("\n  Walk-Forward (W30_R5_N4, long large):")
    wf_size_n4 = rolling_walk_forward(closes, size_ranking_fn, 5, 4, 4,
                                       train_days=360, test_days=80, n_folds=6)

    print("\n  Walk-Forward (W30_R14_N5, long large):")
    wf_size_r14 = rolling_walk_forward(closes, size_ranking_fn, 14, 5, 5,
                                        train_days=360, test_days=80, n_folds=6)

    # Fee sensitivity
    print("\n  Fee Sensitivity (W30_R5_N5):")
    avg_dv_30 = dollar_volume.rolling(30).mean()
    for fee_mult in [1.0, 2.0, 3.0, 5.0]:
        res = run_xs_factor(closes, avg_dv_30, 5, 5, fee_multiplier=fee_mult, warmup=65)
        print(f"    {fee_mult}x fees: Sharpe {res['sharpe']:.2f}, Ann {res['annual_ret']:.1%}")

    # Correlation with ALL existing strategies
    print("\n  Correlation with existing strategies:")
    res_size = run_xs_factor(closes, avg_dv_30, 5, 5, warmup=65)
    rets_size = res_size["equity"].pct_change().dropna()

    # Individual factors at their best params
    strategies = {
        "H-012 (Mom)": run_xs_factor(closes, compute_momentum_ranking(closes, 60), 5, 4, warmup=65),
        "H-021 (VolMom)": run_xs_factor(closes, compute_volume_momentum_ranking(closes, volumes, 5, 20), 3, 4, warmup=65),
        "H-024 (Beta)": run_xs_factor(closes, compute_beta_ranking(closes, 60), 21, 3, warmup=65),
        "H-019 (LowVol)": run_xs_factor(closes, compute_lowvol_ranking(closes, 20), 21, 3, warmup=65),
    }

    for name, res in strategies.items():
        rets_other = res["equity"].pct_change().dropna()
        common_idx = rets_size.index.intersection(rets_other.index)
        if len(common_idx) > 50:
            corr = rets_size.loc[common_idx].corr(rets_other.loc[common_idx])
            print(f"    Size vs {name}: {corr:.3f}")

    # Check: which assets does size tend to long/short?
    print("\n  Typical size factor positions (last 30 rankings):")
    avg_dv_last = avg_dv_30.iloc[-30:].mean()
    sorted_assets = avg_dv_last.sort_values(ascending=False)
    print(f"    LONG (largest):  {list(sorted_assets.index[:5])}")
    print(f"    SHORT (smallest): {list(sorted_assets.index[-5:])}")

    # ═══════════════════════════════════════════════════════════════════
    # 3. Critical comparison: Composite vs Portfolio of individuals
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("COMPOSITE vs PORTFOLIO: Which is better?")
    print("=" * 70)

    # Get individual strategy equity curves
    res_mom = strategies["H-012 (Mom)"]
    res_vol = strategies["H-021 (VolMom)"]
    res_beta = strategies["H-024 (Beta)"]

    # 3-individual portfolio (equal weight)
    common_dates = res_mom["equity"].index.intersection(
        res_vol["equity"].index).intersection(res_beta["equity"].index)

    port_eq_ew = (res_mom["equity"].loc[common_dates] +
                  res_vol["equity"].loc[common_dates] +
                  res_beta["equity"].loc[common_dates]) / 3

    # 3-individual portfolio (target allocation: 10% mom, 25% vol, 15% beta -> normalize to 100%)
    # These are 10/50 = 0.2, 25/50 = 0.5, 15/50 = 0.3 of the XS portion
    port_eq_target = (0.2 * res_mom["equity"].loc[common_dates] +
                      0.5 * res_vol["equity"].loc[common_dates] +
                      0.3 * res_beta["equity"].loc[common_dates])

    # Composite
    res_comp_3f = run_xs_factor(closes, composite_3f, 3, 5, warmup=65)
    res_comp_4f = run_xs_factor(closes, composite_4f, 3, 5, warmup=65)

    comparisons = {
        "3-indiv (equal weight)": port_eq_ew,
        "3-indiv (target alloc)": port_eq_target,
        "Composite 3-factor": res_comp_3f["equity"],
        "Composite 4-factor": res_comp_4f["equity"],
    }

    for name, eq in comparisons.items():
        m = compute_metrics(eq)
        print(f"  {name}: Sharpe {m['sharpe']:.2f}, Ann {m['annual_ret']:.1%}, DD {m['max_dd']:.1%}")

    # Also show: portfolio of 3-individual + H-009
    # Need to load H-009 equity (BTC EMA)
    print("\n  With H-009 (BTC trend):")
    # Simulate H-009: BTC EMA(5/40)
    btc_close = closes["BTC/USDT"]
    ema5 = btc_close.ewm(span=5, adjust=False).mean()
    ema40 = btc_close.ewm(span=40, adjust=False).mean()

    h009_eq = np.zeros(len(btc_close))
    h009_eq[0] = INITIAL_CAPITAL
    pos = 0  # 1=long, -1=short
    for i in range(1, len(btc_close)):
        if ema5.iloc[i-1] > ema40.iloc[i-1]:
            pos = 1
        else:
            pos = -1
        ret = (btc_close.iloc[i] / btc_close.iloc[i-1] - 1) * pos * 0.4  # ~0.4x leverage (VT20%)
        h009_eq[i] = h009_eq[i-1] * (1 + ret)
    h009_eq = pd.Series(h009_eq, index=btc_close.index)
    h009_m = compute_metrics(h009_eq)
    print(f"  H-009 alone: Sharpe {h009_m['sharpe']:.2f}, Ann {h009_m['annual_ret']:.1%}")

    # Portfolio: H-009 (10%) + Composite (50%)
    for comp_name, comp_eq in [("3-factor", res_comp_3f["equity"]), ("4-factor", res_comp_4f["equity"])]:
        common = h009_eq.index.intersection(comp_eq.index)
        port = 0.2 * h009_eq.loc[common] + 0.8 * comp_eq.loc[common]
        m = compute_metrics(port)
        print(f"  H-009(20%) + Composite {comp_name}(80%): Sharpe {m['sharpe']:.2f}, "
              f"Ann {m['annual_ret']:.1%}, DD {m['max_dd']:.1%}")

    # Portfolio: H-009 (10%) + 3 individual strategies (50%)
    common_all = h009_eq.index.intersection(common_dates)
    port_indiv = (0.2 * h009_eq.loc[common_all] +
                  0.16 * res_mom["equity"].loc[common_all] +
                  0.40 * res_vol["equity"].loc[common_all] +
                  0.24 * res_beta["equity"].loc[common_all])
    m = compute_metrics(port_indiv)
    print(f"  H-009(20%) + 3 indiv(80%): Sharpe {m['sharpe']:.2f}, "
          f"Ann {m['annual_ret']:.1%}, DD {m['max_dd']:.1%}")

    # ═══════════════════════════════════════════════════════════════════
    # 4. If H-031 has unique alpha, test composite + size
    # ═══════════════════════════════════════════════════════════════════
    if wf_size is not None and (wf_size["sharpe"] > 0).sum() >= 3:
        print("\n" + "=" * 70)
        print("H-031: Adding Size to Portfolio")
        print("=" * 70)

        # 5-factor composite: Mom + VolMom + Beta + LowVol + Size
        size_z = xs_zscore(avg_dv_30)
        for w_size in [0.1, 0.15, 0.2]:
            remaining = 1.0 - w_size
            composite_5f = (remaining * 0.30 * mom60_z +
                           remaining * 0.35 * volmom_z +
                           remaining * 0.25 * beta60_z +
                           remaining * 0.10 * lowvol20_z +
                           w_size * size_z)
            res = run_xs_factor(closes, composite_5f, 3, 5, warmup=65)
            print(f"  5-factor (size={w_size:.0%}): Sharpe {res['sharpe']:.2f}, "
                  f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    print("\n" + "=" * 70)
    print("DEEP VALIDATION COMPLETE")
    print("=" * 70)
