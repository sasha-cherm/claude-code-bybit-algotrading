"""
H-019 Low-Volatility Anomaly — Deep Validation v2 (Session 2026-03-18)

Key gaps from initial validation:
1. Per-fold WF analysis: identify exactly which periods fail and why
2. Actual H-009 correlation (EMA+VT equity curve, not BTC proxy)
3. Alternative vol measures: EWMA, downside vol, idiosyncratic vol
4. Regime filter: skip low-vol when cross-sectional dispersion is extreme
5. Combined factor: low-vol + momentum blend
6. True adaptive WF: optimize params per fold on training data
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
        except Exception:
            pass
    return hourly, daily


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
    eq = eq_series[eq_series > 0]
    if len(eq) < 50:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "equity": eq_series, "n_trades": trades}
    rets = eq.pct_change().dropna()
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 2),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "n_trades": trades,
        "equity": eq_series,
    }


# ═══════════════════════════════════════════════════════════════════════
# 1. Per-Fold Walk-Forward with Detailed Analysis
# ═══════════════════════════════════════════════════════════════════════

def detailed_walk_forward(closes, vol_window=20, rebal=21, n_long=3):
    """8-fold WF with per-fold analysis: date ranges, asset holdings, BTC trend."""
    print("\n" + "=" * 70)
    print("1. DETAILED WALK-FORWARD (8 folds, 80d test)")
    print("=" * 70)

    daily_rets = closes.pct_change()
    n = len(closes)
    test_days = 80
    btc_close = closes["BTC/USDT"]

    fold_results = []
    for fold in range(8):
        test_end = n - fold * test_days
        test_start = test_end - test_days
        if test_start < vol_window + 20:
            break

        test_closes = closes.iloc[test_start:test_end]
        ranking = -daily_rets.iloc[:test_end].rolling(vol_window).std()
        test_ranking = ranking.iloc[test_start:test_end]

        res = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=5)

        # BTC performance in this fold
        btc_fold = btc_close.iloc[test_start:test_end]
        btc_ret = (btc_fold.iloc[-1] / btc_fold.iloc[0] - 1) * 100

        # Cross-sectional vol dispersion in this fold
        fold_vol = daily_rets.iloc[test_start:test_end].std()
        vol_dispersion = fold_vol.std() / fold_vol.mean() if fold_vol.mean() > 0 else 0

        # Which assets were in long/short baskets at start of fold
        start_rank = ranking.iloc[test_start - 1].dropna().sort_values(ascending=False)
        longs_start = list(start_rank.index[:n_long])
        shorts_start = list(start_rank.index[-n_long:])

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
            "btc_ret_pct": round(btc_ret, 1),
            "vol_dispersion": round(vol_dispersion, 3),
            "longs": [s.split("/")[0] for s in longs_start],
            "shorts": [s.split("/")[0] for s in shorts_start],
        })

        status = "PASS" if res["sharpe"] > 0 else "**FAIL**"
        print(f"\n  Fold {fold+1} [{status}]: {test_closes.index[0].date()} -> {test_closes.index[-1].date()}")
        print(f"    Sharpe: {res['sharpe']:.2f}, Ann: {res['annual_ret']:.1%}, DD: {res['max_dd']:.1%}")
        print(f"    BTC: {btc_ret:+.1f}%, Vol dispersion: {vol_dispersion:.3f}")
        print(f"    Longs: {', '.join(s.split('/')[0] for s in longs_start)}")
        print(f"    Shorts: {', '.join(s.split('/')[0] for s in shorts_start)}")

    df = pd.DataFrame(fold_results)
    pos = (df["sharpe"] > 0).sum()
    print(f"\n  Summary: {pos}/{len(df)} positive folds")
    print(f"  Mean OOS Sharpe: {df['sharpe'].mean():.2f}, Median: {df['sharpe'].median():.2f}")

    # Analyze pattern: do fails correlate with strong BTC trends?
    fails = df[df["sharpe"] <= 0]
    passes = df[df["sharpe"] > 0]
    if len(fails) > 0 and len(passes) > 0:
        print(f"\n  Failing folds avg BTC ret: {fails['btc_ret_pct'].mean():.1f}%")
        print(f"  Passing folds avg BTC ret: {passes['btc_ret_pct'].mean():.1f}%")
        print(f"  Failing folds avg vol dispersion: {fails['vol_dispersion'].mean():.3f}")
        print(f"  Passing folds avg vol dispersion: {passes['vol_dispersion'].mean():.3f}")

    return df


# ═══════════════════════════════════════════════════════════════════════
# 2. Actual H-009 Correlation (Real EMA + Vol Targeting)
# ═══════════════════════════════════════════════════════════════════════

def actual_h009_correlation(closes, daily_data, vol_window=20, rebal=21, n_long=3):
    """Compute correlation with actual H-009 EMA strategy equity curve."""
    print("\n" + "=" * 70)
    print("2. ACTUAL H-009 CORRELATION (EMA + Vol Targeting)")
    print("=" * 70)

    # Run H-019
    daily_rets = closes.pct_change()
    ranking = -daily_rets.rolling(vol_window).std()
    h019_res = run_xs_factor(closes, ranking, rebal, n_long, warmup=vol_window + 10)
    h019_eq = h019_res["equity"]

    # Run actual H-009: BTC EMA(5/40) long/short with vol targeting
    from strategies.daily_trend_multi_asset.strategy import backtest_single_asset, apply_vol_targeting

    btc_daily = daily_data.get("BTC/USDT")
    if btc_daily is None:
        print("  BTC daily data not available!")
        return None

    # Without vol targeting first
    h009_raw = backtest_single_asset(btc_daily, ema_fast=5, ema_slow=40)
    h009_eq_raw = h009_raw["equity_curve"]

    # With vol targeting at 20%
    h009_eq_raw_df = pd.DataFrame({"BTC": h009_raw["equity_curve"]})
    h009_eq_vt = apply_vol_targeting(h009_eq_raw_df, INITIAL_CAPITAL, vol_target=0.20, lookback=60)

    # H-012 for reference
    mom_ranking = closes.pct_change(60)
    h012_res = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)
    h012_eq = h012_res["equity"]

    # Align and compute correlations
    h019_rets = h019_eq.pct_change().dropna()
    h009_rets_raw = h009_eq_raw.pct_change().dropna()
    h009_rets_vt = h009_eq_vt.pct_change().dropna()
    h012_rets = h012_eq.pct_change().dropna()

    # H-019 vs H-009 raw
    common = h019_rets.index.intersection(h009_rets_raw.index)
    corr_raw = h019_rets.loc[common].corr(h009_rets_raw.loc[common])
    print(f"  H-019 vs H-009 (raw EMA): {corr_raw:.3f}")

    # H-019 vs H-009 VT
    common_vt = h019_rets.index.intersection(h009_rets_vt.index)
    corr_vt = h019_rets.loc[common_vt].corr(h009_rets_vt.loc[common_vt])
    print(f"  H-019 vs H-009 (VT 20%):  {corr_vt:.3f}")

    # H-019 vs H-012
    common_h012 = h019_rets.index.intersection(h012_rets.index)
    corr_h012 = h019_rets.loc[common_h012].corr(h012_rets.loc[common_h012])
    print(f"  H-019 vs H-012 (XSMom):   {corr_h012:.3f}")

    # H-009 vs H-012 (for reference)
    common_ref = h009_rets_vt.index.intersection(h012_rets.index)
    corr_ref = h009_rets_vt.loc[common_ref].corr(h012_rets.loc[common_ref])
    print(f"  H-009 vs H-012 (ref):      {corr_ref:.3f}")

    # Rolling correlation H-019 vs H-009 (60d window)
    combined = pd.DataFrame({
        "H-019": h019_rets, "H-009": h009_rets_vt
    }).dropna()
    if len(combined) > 60:
        rolling_corr = combined["H-019"].rolling(60).corr(combined["H-009"])
        print(f"\n  Rolling 60d correlation H-019 vs H-009:")
        print(f"    Mean: {rolling_corr.mean():.3f}")
        print(f"    Min:  {rolling_corr.min():.3f}")
        print(f"    Max:  {rolling_corr.max():.3f}")
        print(f"    Std:  {rolling_corr.std():.3f}")

    return {
        "corr_h009_raw": round(corr_raw, 3),
        "corr_h009_vt": round(corr_vt, 3),
        "corr_h012": round(corr_h012, 3),
    }


# ═══════════════════════════════════════════════════════════════════════
# 3. Alternative Volatility Measures
# ═══════════════════════════════════════════════════════════════════════

def alternative_vol_measures(closes):
    """Test EWMA vol, downside vol, and idiosyncratic vol."""
    print("\n" + "=" * 70)
    print("3. ALTERNATIVE VOLATILITY MEASURES")
    print("=" * 70)

    daily_rets = closes.pct_change()
    n = len(closes)
    test_days = 80

    measures = {}

    # 3a. Standard vol (baseline)
    ranking_std = -daily_rets.rolling(20).std()
    measures["Standard (V20)"] = ranking_std

    # 3b. EWMA vol (more reactive to recent vol changes)
    ewma_vol = daily_rets.ewm(span=20, min_periods=10).std()
    ranking_ewma = -ewma_vol
    measures["EWMA (span=20)"] = ranking_ewma

    # 3c. Downside vol (only count negative returns)
    downside_rets = daily_rets.clip(upper=0)
    downside_vol = downside_rets.rolling(20).std()
    ranking_downside = -downside_vol
    measures["Downside Vol"] = ranking_downside

    # 3d. Idiosyncratic vol (beta-adjusted: regress out market factor)
    # Market = equal-weight return of all assets
    market_ret = daily_rets.mean(axis=1)
    residuals = pd.DataFrame(index=daily_rets.index, columns=daily_rets.columns)
    for sym in daily_rets.columns:
        # Rolling beta
        cov = daily_rets[sym].rolling(60).cov(market_ret)
        var = market_ret.rolling(60).var()
        beta = cov / var
        residuals[sym] = daily_rets[sym] - beta * market_ret
    idio_vol = residuals.rolling(20).std()
    ranking_idio = -idio_vol
    measures["Idiosyncratic Vol"] = ranking_idio

    # 3e. Range-based vol (Parkinson estimator using high/low)
    # This requires high/low data, skip if not available

    results = []
    for name, ranking in measures.items():
        # Full-period backtest
        warmup = 70 if "Idiosyncratic" in name else 30
        res_full = run_xs_factor(closes, ranking, 21, 3, warmup=warmup)

        # Walk-forward (8 folds, 80d test)
        wf_sharpes = []
        for fold in range(8):
            test_end = n - fold * test_days
            test_start = test_end - test_days
            if test_start < warmup + 10:
                break
            test_closes = closes.iloc[test_start:test_end]
            test_ranking = ranking.iloc[test_start:test_end]
            res_wf = run_xs_factor(test_closes, test_ranking, 21, 3, warmup=5)
            wf_sharpes.append(res_wf["sharpe"])

        wf_pos = sum(1 for s in wf_sharpes if s > 0)
        wf_mean = np.mean(wf_sharpes) if wf_sharpes else -99

        results.append({
            "measure": name,
            "is_sharpe": res_full["sharpe"],
            "is_annual": res_full["annual_ret"],
            "is_dd": res_full["max_dd"],
            "wf_folds_pos": f"{wf_pos}/{len(wf_sharpes)}",
            "wf_mean_sharpe": round(wf_mean, 2),
        })

        print(f"\n  {name}:")
        print(f"    IS: Sharpe {res_full['sharpe']:.2f}, Ann {res_full['annual_ret']:.1%}, DD {res_full['max_dd']:.1%}")
        print(f"    WF: {wf_pos}/{len(wf_sharpes)} positive, Mean OOS Sharpe {wf_mean:.2f}")

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════
# 4. Regime Filter: Skip Low-Vol Factor in Strong Trending Markets
# ═══════════════════════════════════════════════════════════════════════

def run_xs_factor_with_regime_filter(closes, ranking_series, rebal_freq, n_long,
                                      regime_signal, warmup=65):
    """Like run_xs_factor but goes flat when regime_signal is True (trending market)."""
    n_short = n_long
    n = len(closes)
    slippage = SLIPPAGE_BPS / 10_000
    fee_rate = BASE_FEE
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital
    prev_weights = pd.Series(0.0, index=closes.columns)
    trades = 0
    regime_flat_days = 0

    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            # Check regime filter
            if i - 1 < len(regime_signal) and regime_signal.iloc[i - 1]:
                # Trending market — go flat
                new_weights = pd.Series(0.0, index=closes.columns)
                regime_flat_days += rebal_freq
            else:
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
    eq = eq_series[eq_series > 0]
    if len(eq) < 50:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "equity": eq_series,
                "n_trades": trades, "regime_flat_days": regime_flat_days}
    rets = eq.pct_change().dropna()
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 2),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "n_trades": trades,
        "equity": eq_series,
        "regime_flat_days": regime_flat_days,
    }


def regime_filter_test(closes, vol_window=20, rebal=21, n_long=3):
    """Test regime filters to address failing WF folds."""
    print("\n" + "=" * 70)
    print("4. REGIME FILTER TEST")
    print("=" * 70)

    daily_rets = closes.pct_change()
    ranking = -daily_rets.rolling(vol_window).std()
    n = len(closes)
    test_days = 80

    # Regime indicators
    btc_close = closes["BTC/USDT"]
    regime_signals = {}

    # 4a. BTC trend strength: abs(EMA5 - EMA40) / EMA40
    ema5 = btc_close.ewm(span=5).mean()
    ema40 = btc_close.ewm(span=40).mean()
    trend_strength = ((ema5 - ema40) / ema40).abs()
    for pctile in [70, 80, 90]:
        threshold = trend_strength.rolling(120).quantile(pctile / 100)
        regime_signals[f"BTC_trend_p{pctile}"] = trend_strength > threshold

    # 4b. Cross-sectional return dispersion (high dispersion = trending)
    xs_dispersion = daily_rets.rolling(20).std().std(axis=1)
    for pctile in [70, 80, 90]:
        threshold = xs_dispersion.rolling(120).quantile(pctile / 100)
        regime_signals[f"XS_disp_p{pctile}"] = xs_dispersion > threshold

    # 4c. Average cross-sectional vol (high avg vol = stressed market)
    avg_vol = daily_rets.rolling(20).std().mean(axis=1)
    for pctile in [70, 80, 90]:
        threshold = avg_vol.rolling(120).quantile(pctile / 100)
        regime_signals[f"Avg_vol_p{pctile}"] = avg_vol > threshold

    # Baseline (no filter)
    res_base = run_xs_factor(closes, ranking, rebal, n_long, warmup=vol_window + 10)
    wf_base = []
    for fold in range(8):
        test_end = n - fold * test_days
        test_start = test_end - test_days
        if test_start < vol_window + 20:
            break
        test_closes = closes.iloc[test_start:test_end]
        test_ranking = ranking.iloc[test_start:test_end]
        r = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=5)
        wf_base.append(r["sharpe"])

    wf_base_pos = sum(1 for s in wf_base if s > 0)
    print(f"\n  Baseline (no filter):")
    print(f"    IS: Sharpe {res_base['sharpe']:.2f}, Ann {res_base['annual_ret']:.1%}, DD {res_base['max_dd']:.1%}")
    print(f"    WF: {wf_base_pos}/{len(wf_base)} positive, Mean {np.mean(wf_base):.2f}")

    # Test each regime filter
    best_filter = None
    best_wf_mean = np.mean(wf_base)

    for filter_name, regime_sig in regime_signals.items():
        res = run_xs_factor_with_regime_filter(
            closes, ranking, rebal, n_long, regime_sig, warmup=vol_window + 10
        )

        # Walk-forward with filter
        wf_sharpes = []
        for fold in range(8):
            test_end = n - fold * test_days
            test_start = test_end - test_days
            if test_start < vol_window + 20:
                break
            test_closes = closes.iloc[test_start:test_end]
            test_ranking = ranking.iloc[test_start:test_end]
            test_regime = regime_sig.iloc[test_start:test_end]
            r = run_xs_factor_with_regime_filter(
                test_closes, test_ranking, rebal, n_long, test_regime, warmup=5
            )
            wf_sharpes.append(r["sharpe"])

        wf_pos = sum(1 for s in wf_sharpes if s > 0)
        wf_mean = np.mean(wf_sharpes) if wf_sharpes else -99

        flat_pct = res.get("regime_flat_days", 0) / n * 100

        print(f"\n  {filter_name}:")
        print(f"    IS: Sharpe {res['sharpe']:.2f}, Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")
        print(f"    WF: {wf_pos}/{len(wf_sharpes)} positive, Mean {wf_mean:.2f}")
        print(f"    Flat: {flat_pct:.0f}% of time")

        if wf_mean > best_wf_mean and wf_pos >= wf_base_pos:
            best_wf_mean = wf_mean
            best_filter = filter_name

    if best_filter:
        print(f"\n  Best regime filter: {best_filter} (WF mean {best_wf_mean:.2f})")
    else:
        print(f"\n  No regime filter improves WF performance over baseline")

    return best_filter


# ═══════════════════════════════════════════════════════════════════════
# 5. Combined Factor: Low-Vol + Momentum Blend
# ═══════════════════════════════════════════════════════════════════════

def combined_factor_test(closes, vol_window=20, rebal=21, n_long=3):
    """Test blending low-vol ranking with momentum for a hybrid factor."""
    print("\n" + "=" * 70)
    print("5. COMBINED FACTOR: LOW-VOL + MOMENTUM BLEND")
    print("=" * 70)

    daily_rets = closes.pct_change()
    n = len(closes)
    test_days = 80

    # Component rankings (z-scored for comparability)
    vol_rank_raw = -daily_rets.rolling(vol_window).std()
    mom_rank_raw = closes.pct_change(60)

    # Z-score each ranking cross-sectionally
    def xs_zscore(df):
        return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1), axis=0)

    vol_z = xs_zscore(vol_rank_raw)
    mom_z = xs_zscore(mom_rank_raw)

    blends = [
        ("Pure LowVol", 1.0, 0.0),
        ("70/30 LV/Mom", 0.7, 0.3),
        ("50/50 LV/Mom", 0.5, 0.5),
        ("30/70 LV/Mom", 0.3, 0.7),
        ("Pure Mom (H-012)", 0.0, 1.0),
    ]

    results = []
    for name, w_vol, w_mom in blends:
        combined_ranking = w_vol * vol_z + w_mom * mom_z
        warmup = max(vol_window + 10, 65)
        res = run_xs_factor(closes, combined_ranking, rebal, n_long, warmup=warmup)

        # Walk-forward
        wf_sharpes = []
        for fold in range(8):
            test_end = n - fold * test_days
            test_start = test_end - test_days
            if test_start < warmup + 10:
                break
            test_closes = closes.iloc[test_start:test_end]
            test_ranking = combined_ranking.iloc[test_start:test_end]
            r = run_xs_factor(test_closes, test_ranking, rebal, n_long, warmup=5)
            wf_sharpes.append(r["sharpe"])

        wf_pos = sum(1 for s in wf_sharpes if s > 0)
        wf_mean = np.mean(wf_sharpes) if wf_sharpes else -99

        results.append({
            "blend": name,
            "w_vol": w_vol,
            "w_mom": w_mom,
            "is_sharpe": res["sharpe"],
            "is_annual": res["annual_ret"],
            "is_dd": res["max_dd"],
            "wf_pos": f"{wf_pos}/{len(wf_sharpes)}",
            "wf_mean": round(wf_mean, 2),
        })

        print(f"\n  {name}:")
        print(f"    IS: Sharpe {res['sharpe']:.2f}, Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")
        print(f"    WF: {wf_pos}/{len(wf_sharpes)} positive, Mean {wf_mean:.2f}")

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════
# 6. True Adaptive Walk-Forward (Optimize Params per Fold)
# ═══════════════════════════════════════════════════════════════════════

def adaptive_walk_forward(closes):
    """True expanding-window WF: optimize params on training, test on OOS."""
    print("\n" + "=" * 70)
    print("6. TRUE ADAPTIVE WALK-FORWARD (param optimization per fold)")
    print("=" * 70)

    daily_rets = closes.pct_change()
    n = len(closes)
    test_days = 80
    min_train = 200  # min training days

    param_space = []
    for vw in [10, 15, 20, 25, 30]:
        for rb in [7, 14, 21, 28]:
            for nl in [3, 4]:
                param_space.append({"vol_window": vw, "rebal": rb, "n_long": nl})

    fold_results = []
    for fold in range(8):
        test_end = n - fold * test_days
        test_start = test_end - test_days
        train_end = test_start

        if train_end < min_train:
            break

        # Optimize on training data
        train_closes = closes.iloc[:train_end]
        train_rets = daily_rets.iloc[:train_end]
        best_sharpe = -99
        best_params = None

        for params in param_space:
            vw, rb, nl = params["vol_window"], params["rebal"], params["n_long"]
            ranking = -train_rets.rolling(vw).std()
            res = run_xs_factor(train_closes, ranking, rb, nl, warmup=vw + 10)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_params = params

        # Test with best params on OOS
        vw = best_params["vol_window"]
        rb = best_params["rebal"]
        nl = best_params["n_long"]

        test_closes = closes.iloc[test_start:test_end]
        ranking = -daily_rets.iloc[:test_end].rolling(vw).std()
        test_ranking = ranking.iloc[test_start:test_end]
        res = run_xs_factor(test_closes, test_ranking, rb, nl, warmup=5)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "train_sharpe": round(best_sharpe, 2),
            "oos_sharpe": res["sharpe"],
            "oos_annual": res["annual_ret"],
            "oos_dd": res["max_dd"],
            "best_params": f"V{vw}_R{rb}_N{nl}",
        })

        status = "PASS" if res["sharpe"] > 0 else "**FAIL**"
        print(f"\n  Fold {fold+1} [{status}]: {test_closes.index[0].date()} -> {test_closes.index[-1].date()}")
        print(f"    Best train params: V{vw}_R{rb}_N{nl} (train Sharpe {best_sharpe:.2f})")
        print(f"    OOS: Sharpe {res['sharpe']:.2f}, Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    df = pd.DataFrame(fold_results)
    pos = (df["oos_sharpe"] > 0).sum()
    print(f"\n  Adaptive WF Summary: {pos}/{len(df)} positive folds")
    print(f"  Mean OOS Sharpe: {df['oos_sharpe'].mean():.2f}")
    print(f"  Mean train→OOS decay: {df['train_sharpe'].mean():.2f} -> {df['oos_sharpe'].mean():.2f}")

    return df


# ═══════════════════════════════════════════════════════════════════════
# 7. Updated 4-Strategy Portfolio (with actual H-009)
# ═══════════════════════════════════════════════════════════════════════

def portfolio_with_actual_h009(closes, daily_data, vol_window=20, rebal=21, n_long=3):
    """Portfolio simulation using actual H-009 EMA equity curve."""
    print("\n" + "=" * 70)
    print("7. 4-STRATEGY PORTFOLIO (with actual H-009 equity)")
    print("=" * 70)

    daily_rets = closes.pct_change()

    # H-019
    ranking = -daily_rets.rolling(vol_window).std()
    h019_res = run_xs_factor(closes, ranking, rebal, n_long, warmup=vol_window + 10)
    h019_eq = h019_res["equity"]

    # H-012
    mom_ranking = closes.pct_change(60)
    h012_res = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)
    h012_eq = h012_res["equity"]

    # Actual H-009
    from strategies.daily_trend_multi_asset.strategy import backtest_single_asset, apply_vol_targeting
    btc_daily = daily_data["BTC/USDT"]
    h009_raw = backtest_single_asset(btc_daily, ema_fast=5, ema_slow=40)
    h009_eq_raw_df = pd.DataFrame({"BTC": h009_raw["equity_curve"]})
    h009_eq = apply_vol_targeting(h009_eq_raw_df, INITIAL_CAPITAL, vol_target=0.20, lookback=60)

    # H-011 proxy (flat 1.5% annual when active ~60%)
    h011_daily_ret = (1.015 ** (1/365)) - 1
    h011_eq = pd.Series(
        INITIAL_CAPITAL * np.cumprod(np.ones(len(closes)) * (1 + h011_daily_ret)),
        index=closes.index
    )

    # Align
    common = h019_eq.index
    for eq in [h012_eq, h009_eq, h011_eq]:
        common = common.intersection(eq.index)

    h019_r = h019_eq.loc[common].pct_change().dropna()
    h012_r = h012_eq.loc[common].pct_change().dropna()
    h009_r = h009_eq.loc[common].pct_change().dropna()
    h011_r = h011_eq.loc[common].pct_change().dropna()

    common_r = h019_r.index.intersection(h012_r.index).intersection(h009_r.index)
    h019_r = h019_r.loc[common_r]
    h012_r = h012_r.loc[common_r]
    h009_r = h009_r.loc[common_r]
    h011_r = h011_r.loc[common_r]

    # Full correlation matrix
    corr_df = pd.DataFrame({
        "H-009": h009_r, "H-011": h011_r,
        "H-012": h012_r, "H-019": h019_r,
    })
    print("\n  Correlation matrix (actual H-009 equity):")
    print(corr_df.corr().round(3).to_string())

    # Portfolio allocations
    allocations = [
        ("3-strat (20/60/20)",        [0.20, 0.60, 0.20, 0.00]),
        ("4-strat (15/50/15/20)",     [0.15, 0.50, 0.15, 0.20]),
        ("4-strat (15/45/20/20)",     [0.15, 0.45, 0.20, 0.20]),
        ("4-strat (10/50/20/20)",     [0.10, 0.50, 0.20, 0.20]),
        ("4-strat (10/45/15/30)",     [0.10, 0.45, 0.15, 0.30]),
        ("4-strat equal (25/25/25/25)", [0.25, 0.25, 0.25, 0.25]),
    ]

    print("\n  Portfolio results (H-009 / H-011 / H-012 / H-019):")
    for name, weights in allocations:
        port_rets = (weights[0] * h009_r + weights[1] * h011_r +
                     weights[2] * h012_r + weights[3] * h019_r)
        port_eq = INITIAL_CAPITAL * (1 + port_rets).cumprod()

        sh = sharpe_ratio(port_rets, periods_per_year=365)
        ar = annual_return(port_eq, periods_per_year=365)
        dd = max_drawdown(port_eq)
        print(f"\n  {name}:")
        print(f"    Sharpe: {sh:.2f}, Annual: {ar:.1%}, MaxDD: {dd:.1%}")


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Loading data...")
    hourly, daily = load_all_data()
    print(f"Loaded {len(daily)} assets\n")

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()

    print("\n" + "█" * 70)
    print("H-019 LOW-VOLATILITY ANOMALY — DEEP VALIDATION v2")
    print("█" * 70)

    # 1. Detailed per-fold walk-forward
    wf_detail = detailed_walk_forward(closes)

    # 2. Actual H-009 correlation
    corr_results = actual_h009_correlation(closes, daily)

    # 3. Alternative vol measures
    alt_vol_df = alternative_vol_measures(closes)

    # 4. Regime filter
    best_filter = regime_filter_test(closes)

    # 5. Combined factor (low-vol + momentum)
    blend_df = combined_factor_test(closes)

    # 6. True adaptive walk-forward
    adaptive_wf = adaptive_walk_forward(closes)

    # 7. Portfolio with actual H-009
    portfolio_with_actual_h009(closes, daily)

    print("\n" + "█" * 70)
    print("VALIDATION COMPLETE")
    print("█" * 70)
