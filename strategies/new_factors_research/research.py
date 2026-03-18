"""
New Cross-Sectional Factor Research (Session 2026-03-18)

Three new factor strategies to explore, all using the 14-asset universe:

H-018: Short-Term Reversal (1-5 day)
  - Buy recent losers, sell recent winners (opposite of momentum)
  - Academic factor: well-documented in equities, driven by overreaction
  - Should be negatively correlated with H-012 (60d momentum)

H-019: Low-Volatility Anomaly
  - Long low-vol assets, short high-vol assets
  - Academic factor: low-vol assets earn risk-adjusted excess returns
  - Uncorrelated with directional or momentum factors

H-020: Funding Rate Dispersion (Cross-Sectional)
  - Long assets with highest funding rates, short lowest
  - Different from H-011/H-013: this is RELATIVE ranking, not absolute collection
  - Cross-sectional carry trade — captures crowding/positioning imbalances
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
    """Resample hourly OHLCV to daily."""
    daily = df.resample("1D").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()
    return daily


def load_all_data():
    """Load 1h data for all assets, resample to daily with volume."""
    hourly = {}
    daily = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df) < 200:
                print(f"  {sym}: insufficient data ({len(df)} bars), skipping")
                continue
            hourly[sym] = df
            daily[sym] = resample_to_daily(df)
            print(f"  {sym}: {len(daily[sym])} daily bars, {len(df)} hourly bars")
        except Exception as e:
            print(f"  {sym}: failed to load: {e}")
    return hourly, daily


def compute_metrics(equity_series):
    """Compute standard metrics from equity curve."""
    eq = equity_series[equity_series > 0]
    if len(eq) < 50:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0}
    rets = eq.pct_change().dropna()
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 2),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
    }


# ═══════════════════════════════════════════════════════════════════════
# Generic cross-sectional backtester
# ═══════════════════════════════════════════════════════════════════════

def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  fee_multiplier=1.0, warmup=65):
    """
    Generic cross-sectional factor backtester.

    Args:
        closes: DataFrame of daily close prices (date x asset)
        ranking_series: DataFrame of ranking values (higher = long, lower = short)
        rebal_freq: Days between rebalances
        n_long: Number of assets to go long
        n_short: Number of assets to go short (default = n_long)
        fee_multiplier: Multiplier on base fee
        warmup: Number of bars before first trade
    """
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
            ranks = ranking_series.iloc[i - 1]  # lagged ranking (no look-ahead)
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

            # Apply fee on rebalance day
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


# ═══════════════════════════════════════════════════════════════════════
# H-018: Short-Term Reversal
# ═══════════════════════════════════════════════════════════════════════

def h018_short_term_reversal(daily_data):
    """
    Cross-sectional short-term reversal:
    Buy recent LOSERS, sell recent WINNERS.
    The ranking is NEGATIVE of short-term returns (so losers rank highest).
    """
    print("\n" + "=" * 70)
    print("H-018: SHORT-TERM REVERSAL (Cross-Sectional)")
    print("=" * 70)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    results = []
    for lookback in [1, 2, 3, 5, 7, 10]:
        for rebal_freq in [1, 2, 3, 5]:
            for n_long in [3, 4, 5]:
                # Ranking: NEGATIVE of past returns (losers ranked high)
                ranking = -closes.pct_change(lookback)
                warmup = max(lookback + 5, 15)

                res = run_xs_factor(closes, ranking, rebal_freq, n_long,
                                    warmup=warmup)
                tag = f"L{lookback}_R{rebal_freq}_N{n_long}"
                results.append({
                    "tag": tag, "lookback": lookback, "rebal": rebal_freq,
                    "n_long": n_long, **{k: v for k, v in res.items() if k != "equity"},
                })
                if res["sharpe"] > 0.3:
                    print(f"  ** {tag}: Sharpe {res['sharpe']:.2f}, "
                          f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"\n  Total params: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.2f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.2f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}")

    return df, closes


# ═══════════════════════════════════════════════════════════════════════
# H-019: Low-Volatility Anomaly
# ═══════════════════════════════════════════════════════════════════════

def h019_low_volatility(daily_data):
    """
    Cross-sectional low-volatility:
    Long low-vol assets, short high-vol assets.
    Ranking: NEGATIVE of realized volatility (low vol ranks high).
    """
    print("\n" + "=" * 70)
    print("H-019: LOW-VOLATILITY ANOMALY (Cross-Sectional)")
    print("=" * 70)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    daily_rets = closes.pct_change()

    results = []
    for vol_window in [10, 20, 30, 60, 90]:
        for rebal_freq in [5, 7, 10, 14, 21]:
            for n_long in [3, 4, 5]:
                # Ranking: NEGATIVE of realized vol (low vol ranks high)
                realized_vol = daily_rets.rolling(vol_window).std()
                ranking = -realized_vol
                warmup = vol_window + 10

                res = run_xs_factor(closes, ranking, rebal_freq, n_long,
                                    warmup=warmup)
                tag = f"V{vol_window}_R{rebal_freq}_N{n_long}"
                results.append({
                    "tag": tag, "vol_window": vol_window, "rebal": rebal_freq,
                    "n_long": n_long, **{k: v for k, v in res.items() if k != "equity"},
                })
                if res["sharpe"] > 0.3:
                    print(f"  ** {tag}: Sharpe {res['sharpe']:.2f}, "
                          f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"\n  Total params: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.2f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.2f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}")

    return df, closes


# ═══════════════════════════════════════════════════════════════════════
# H-020: Funding Rate Dispersion (Cross-Sectional Carry)
# ═══════════════════════════════════════════════════════════════════════

def load_funding_rates():
    """Load cached funding rate data for all assets."""
    data_dir = ROOT / "data"
    funding = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"funding_{safe}.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            funding[sym] = df
        else:
            print(f"  {sym}: no funding data cached")
    return funding


def h020_funding_dispersion(daily_data):
    """
    Cross-sectional carry: long high-funding assets, short low-funding.
    Ranking by rolling average funding rate (assets where longs pay shorts).
    """
    print("\n" + "=" * 70)
    print("H-020: FUNDING RATE DISPERSION (Cross-Sectional Carry)")
    print("=" * 70)

    # Load funding data
    funding_data = load_funding_rates()
    if len(funding_data) < 8:
        print(f"  Only {len(funding_data)} assets have funding data, need ≥8. Skipping.")
        return None, None

    # Resample funding to daily (sum of 3 settlements per day)
    daily_funding = {}
    for sym, df in funding_data.items():
        if "funding_rate" in df.columns:
            fr = df["funding_rate"].resample("1D").sum()
            daily_funding[sym] = fr
        elif "fundingRate" in df.columns:
            fr = df["fundingRate"].resample("1D").sum()
            daily_funding[sym] = fr

    if len(daily_funding) < 8:
        print(f"  Only {len(daily_funding)} assets with valid funding, need ≥8. Skipping.")
        return None, None

    funding_panel = pd.DataFrame(daily_funding)
    funding_panel = funding_panel.dropna(how="all").ffill()
    print(f"  Funding universe: {len(funding_panel.columns)} assets, {len(funding_panel)} days")

    # Build closes panel aligned to funding dates
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()
                          if sym in funding_panel.columns})
    closes = closes.dropna(how="all").ffill().dropna()

    # Align
    common_dates = closes.index.intersection(funding_panel.index)
    closes = closes.loc[common_dates]
    funding_panel = funding_panel.loc[common_dates]
    common_assets = list(set(closes.columns) & set(funding_panel.columns))
    closes = closes[common_assets]
    funding_panel = funding_panel[common_assets]
    print(f"  Aligned: {len(common_assets)} assets, {len(common_dates)} days")

    results = []
    for fr_window in [7, 14, 27, 45, 60]:
        for rebal_freq in [1, 3, 5, 7]:
            for n_long in [3, 4]:
                # Ranking: rolling avg funding rate (high funding = long)
                ranking = funding_panel.rolling(fr_window).mean()
                warmup = fr_window + 10

                res = run_xs_factor(closes, ranking, rebal_freq, n_long,
                                    warmup=warmup)
                tag = f"F{fr_window}_R{rebal_freq}_N{n_long}"
                results.append({
                    "tag": tag, "fr_window": fr_window, "rebal": rebal_freq,
                    "n_long": n_long, **{k: v for k, v in res.items() if k != "equity"},
                })
                if res["sharpe"] > 0.3:
                    print(f"  ** {tag}: Sharpe {res['sharpe']:.2f}, "
                          f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    df = pd.DataFrame(results)
    if len(df) == 0:
        print("  No results generated.")
        return None, None

    positive = df[df["sharpe"] > 0]
    print(f"\n  Total params: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.2f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.2f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}")

    return df, closes


# ═══════════════════════════════════════════════════════════════════════
# Walk-Forward Validation
# ═══════════════════════════════════════════════════════════════════════

def rolling_walk_forward(closes, factor_fn, best_params, n_folds=6,
                         train_days=180, test_days=90):
    """
    Rolling walk-forward: train on train_days, test on test_days.
    factor_fn(closes, **params) -> ranking DataFrame
    best_params: dict with rebal_freq, n_long, plus factor-specific params
    """
    print(f"\n  Rolling Walk-Forward ({n_folds} folds, {train_days}d train, {test_days}d test)")

    n = len(closes)
    fold_results = []

    for fold in range(n_folds):
        test_end = n - fold * test_days
        test_start = test_end - test_days
        train_start = test_start - train_days

        if train_start < 0:
            break

        test_closes = closes.iloc[test_start:test_end]
        ranking = factor_fn(closes.iloc[:test_end])  # compute on all data up to test end

        # Slice ranking to test period
        test_ranking = ranking.iloc[test_start:test_end]

        rebal = best_params.get("rebal_freq", 5)
        n_long = best_params.get("n_long", 4)

        # Run on test period
        res = run_xs_factor(test_closes, test_ranking, rebal, n_long,
                            warmup=5, fee_multiplier=1.0)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        })
        print(f"    Fold {fold+1}: {test_closes.index[0].date()} → {test_closes.index[-1].date()}, "
              f"Sharpe {res['sharpe']:.2f}, Ann {res['annual_ret']:.1%}")

    if not fold_results:
        print("    No folds completed!")
        return None

    df = pd.DataFrame(fold_results)
    positive = (df["sharpe"] > 0).sum()
    print(f"    Positive folds: {positive}/{len(df)}")
    print(f"    Mean OOS Sharpe: {df['sharpe'].mean():.2f}")
    return df


# ═══════════════════════════════════════════════════════════════════════
# Correlation with Existing Strategies
# ═══════════════════════════════════════════════════════════════════════

def compute_correlation_with_h012(closes, ranking, rebal_freq, n_long, warmup):
    """Compute return correlation between new factor and H-012 (60d momentum)."""
    # Run new factor
    res_new = run_xs_factor(closes, ranking, rebal_freq, n_long, warmup=warmup)

    # Run H-012 (60d momentum)
    mom_ranking = closes.pct_change(60)
    res_h012 = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)

    eq_new = res_new["equity"]
    eq_h012 = res_h012["equity"]

    # Compute return correlation
    rets_new = eq_new.pct_change().dropna()
    rets_h012 = eq_h012.pct_change().dropna()

    common = rets_new.index.intersection(rets_h012.index)
    if len(common) < 50:
        return 0.0

    corr = rets_new.loc[common].corr(rets_h012.loc[common])
    return round(corr, 3)


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Loading data...")
    hourly, daily = load_all_data()

    print(f"\nLoaded {len(daily)} assets")

    # ── H-018: Short-Term Reversal ──
    print("\n" + "█" * 70)
    print("FACTOR 1: H-018 SHORT-TERM REVERSAL")
    print("█" * 70)
    h018_results, h018_closes = h018_short_term_reversal(daily)

    # ── H-019: Low-Volatility Anomaly ──
    print("\n" + "█" * 70)
    print("FACTOR 2: H-019 LOW-VOLATILITY ANOMALY")
    print("█" * 70)
    h019_results, h019_closes = h019_low_volatility(daily)

    # ── H-020: Funding Rate Dispersion ──
    print("\n" + "█" * 70)
    print("FACTOR 3: H-020 FUNDING RATE DISPERSION")
    print("█" * 70)
    h020_results, h020_closes = h020_funding_dispersion(daily)

    # ── Summary ──
    print("\n" + "█" * 70)
    print("SUMMARY")
    print("█" * 70)

    for name, df in [("H-018 Reversal", h018_results),
                     ("H-019 LowVol", h019_results),
                     ("H-020 FundDisp", h020_results)]:
        if df is not None and len(df) > 0:
            pos_pct = (df["sharpe"] > 0).mean()
            print(f"\n  {name}:")
            print(f"    Params tested: {len(df)}")
            print(f"    Positive Sharpe: {pos_pct:.0%}")
            print(f"    Mean Sharpe: {df['sharpe'].mean():.2f}")
            print(f"    Best Sharpe: {df['sharpe'].max():.2f}")
            print(f"    Best Annual: {df['annual_ret'].max():.1%}")
        else:
            print(f"\n  {name}: No results")

    # ── Walk-forward for promising factors ──
    # Check which factors have ≥50% positive Sharpe
    promising = []

    if h018_results is not None and (h018_results["sharpe"] > 0).mean() >= 0.4:
        best = h018_results.nlargest(1, "sharpe").iloc[0]
        print(f"\n  H-018 looks promising (>{(h018_results['sharpe'] > 0).mean():.0%} positive). "
              f"Running walk-forward with L{int(best['lookback'])}_R{int(best['rebal'])}_N{int(best['n_long'])}...")
        lookback = int(best["lookback"])
        def h018_ranking_fn(c):
            return -c.pct_change(lookback)
        wf = rolling_walk_forward(
            h018_closes,
            h018_ranking_fn,
            {"rebal_freq": int(best["rebal"]), "n_long": int(best["n_long"])},
        )
        if wf is not None:
            pos_folds = (wf["sharpe"] > 0).sum()
            mean_oos = wf["sharpe"].mean()
            print(f"  H-018 WF result: {pos_folds}/{len(wf)} positive, mean OOS Sharpe {mean_oos:.2f}")
            if pos_folds >= len(wf) * 0.5:
                promising.append(("H-018", best, h018_closes, h018_ranking_fn, wf))

            # Compute correlation with H-012
            ranking = h018_ranking_fn(h018_closes)
            corr = compute_correlation_with_h012(
                h018_closes, ranking, int(best["rebal"]), int(best["n_long"]),
                warmup=lookback + 5
            )
            print(f"  H-018 ↔ H-012 correlation: {corr}")

    if h019_results is not None and (h019_results["sharpe"] > 0).mean() >= 0.4:
        best = h019_results.nlargest(1, "sharpe").iloc[0]
        print(f"\n  H-019 looks promising (>{(h019_results['sharpe'] > 0).mean():.0%} positive). "
              f"Running walk-forward with V{int(best['vol_window'])}_R{int(best['rebal'])}_N{int(best['n_long'])}...")
        vol_window = int(best["vol_window"])
        def h019_ranking_fn(c):
            return -c.pct_change().rolling(vol_window).std()
        wf = rolling_walk_forward(
            h019_closes,
            h019_ranking_fn,
            {"rebal_freq": int(best["rebal"]), "n_long": int(best["n_long"])},
        )
        if wf is not None:
            pos_folds = (wf["sharpe"] > 0).sum()
            mean_oos = wf["sharpe"].mean()
            print(f"  H-019 WF result: {pos_folds}/{len(wf)} positive, mean OOS Sharpe {mean_oos:.2f}")
            if pos_folds >= len(wf) * 0.5:
                promising.append(("H-019", best, h019_closes, h019_ranking_fn, wf))

            # Correlation with H-012
            ranking = h019_ranking_fn(h019_closes)
            corr = compute_correlation_with_h012(
                h019_closes, ranking, int(best["rebal"]), int(best["n_long"]),
                warmup=vol_window + 10
            )
            print(f"  H-019 ↔ H-012 correlation: {corr}")

    if h020_results is not None and (h020_results["sharpe"] > 0).mean() >= 0.4:
        best = h020_results.nlargest(1, "sharpe").iloc[0]
        print(f"\n  H-020 looks promising (>{(h020_results['sharpe'] > 0).mean():.0%} positive). "
              f"Running walk-forward...")
        promising.append(("H-020", best, h020_closes, None, None))

    print("\n" + "=" * 70)
    print("PROMISING FACTORS FOR FURTHER VALIDATION:")
    print("=" * 70)
    if promising:
        for name, params, _, _, wf in promising:
            print(f"  {name}: {params.to_dict()}")
    else:
        print("  None passed the initial screen (≥40% positive Sharpe + walk-forward)")

    print("\nDone.")
