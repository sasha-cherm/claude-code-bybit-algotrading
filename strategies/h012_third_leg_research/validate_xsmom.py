"""
H-012 Deep Validation: Cross-Sectional Momentum

Validates the XSMom strategy with:
1. Parameter robustness (sweep across lookback, rebal, n_long)
2. Rolling walk-forward (6-month train, 3-month test, rolling quarterly)
3. Higher fee sensitivity (2x, 3x baseline fees)
4. Correlation with H-009 AND H-011
5. Three-strategy portfolio simulation (H-009 + H-011 + H-012)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return
from strategies.daily_trend_multi_asset.strategy import (
    resample_to_daily,
    backtest_single_asset,
)

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

BASE_FEE = 0.001
SLIPPAGE_BPS = 2.0
INITIAL_CAPITAL = 10_000.0


def load_daily():
    """Load all assets and resample to daily."""
    daily = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df) >= 200:
                daily[sym] = resample_to_daily(df)
        except Exception:
            pass
    return daily


def run_xsmom(closes, lookback, rebal_freq, n_long, fee_multiplier=1.0):
    """Cross-sectional momentum backtest with lagged ranking (no look-ahead)."""
    n_short = n_long
    n = len(closes)
    slippage = SLIPPAGE_BPS / 10_000
    fee_rate = BASE_FEE * fee_multiplier

    rolling_ret = closes.pct_change(lookback)

    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    positions = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    trades = 0
    prev_weights = pd.Series(0.0, index=closes.columns)

    warmup = lookback + 5

    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            rets = rolling_ret.iloc[i - 1]  # lagged ranking
            valid = rets.dropna()
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
            prev_weights = new_weights
            positions.iloc[i] = new_weights
        else:
            positions.iloc[i] = positions.iloc[i - 1] if i > 0 else 0.0

        daily_rets = (price_today / price_yesterday - 1)
        port_ret = (positions.iloc[i] * daily_rets).sum()

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * (fee_rate + slippage)
            port_ret -= fee_drag

        equity[i] = equity[i - 1] * (1 + port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    eq_series = eq_series[eq_series > 0]
    if len(eq_series) < 50:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "equity": eq_series}

    rets = eq_series.pct_change().dropna()
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 2),
        "annual_ret": round(annual_return(eq_series, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq_series), 4),
        "n_trades": trades,
        "equity": eq_series,
    }


# ═══════════════════════════════════════════════════════════════════════
# 1. Parameter Robustness
# ═══════════════════════════════════════════════════════════════════════

def test_param_robustness(closes):
    """Test multiple param sets around the best (L60, R5, N4)."""
    print("\n" + "=" * 60)
    print("1. PARAMETER ROBUSTNESS")
    print("=" * 60)

    param_sets = []
    for lookback in [30, 45, 60, 75, 90]:
        for rebal in [3, 5, 7]:
            for n_long in [3, 4, 5]:
                param_sets.append((lookback, rebal, n_long))

    results = []
    for lb, rb, nl in param_sets:
        r = run_xsmom(closes, lb, rb, nl)
        results.append({
            "lookback": lb, "rebal": rb, "n_long": nl,
            "sharpe": r["sharpe"], "annual_ret": r["annual_ret"],
            "max_dd": r["max_dd"],
        })

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"  Total param sets: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.2f}")
    print(f"  Min Sharpe: {df['sharpe'].min():.2f}")
    print(f"  Max Sharpe: {df['sharpe'].max():.2f}")

    # Top 10
    top10 = df.nlargest(10, "sharpe")
    print("\n  Top 10:")
    for _, row in top10.iterrows():
        print(f"    L{row['lookback']}_R{row['rebal']}_N{int(row['n_long'])}: "
              f"Sharpe {row['sharpe']:.2f}, Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    return df


# ═══════════════════════════════════════════════════════════════════════
# 2. Rolling Walk-Forward
# ═══════════════════════════════════════════════════════════════════════

def test_rolling_walk_forward(closes, lookback=60, rebal=5, n_long=4):
    """
    Rolling walk-forward: 180-day train, 90-day test, roll every 90 days.
    On each fold, optimize params on train, test on test.
    Here we use fixed params but apply on rolling OOS windows.
    """
    print("\n" + "=" * 60)
    print(f"2. ROLLING WALK-FORWARD (L{lookback}, R{rebal}, N{n_long})")
    print("=" * 60)

    train_days = 180
    test_days = 90
    step_days = 90

    all_oos_returns = []
    fold = 0

    i = 0
    while i + train_days + test_days <= len(closes):
        train_end = i + train_days
        test_end = train_end + test_days

        train_closes = closes.iloc[i:train_end]
        test_closes = closes.iloc[train_end:test_end]

        # Run on test (OOS) using fixed params
        r_oos = run_xsmom(test_closes, lookback, rebal, n_long)

        train_start = closes.index[i].strftime("%Y-%m-%d")
        test_start = closes.index[train_end].strftime("%Y-%m-%d")
        test_end_str = closes.index[min(test_end - 1, len(closes) - 1)].strftime("%Y-%m-%d")

        if len(r_oos["equity"]) > 10:
            oos_rets = r_oos["equity"].pct_change().dropna()
            all_oos_returns.append(oos_rets)
            print(f"  Fold {fold}: {test_start} to {test_end_str} — "
                  f"Sharpe {r_oos['sharpe']:.2f}, Ann {r_oos['annual_ret']:.1%}, "
                  f"DD {r_oos['max_dd']:.1%}")
        else:
            print(f"  Fold {fold}: {test_start} to {test_end_str} — insufficient data")

        i += step_days
        fold += 1

    if all_oos_returns:
        combined = pd.concat(all_oos_returns)
        combined_eq = INITIAL_CAPITAL * (1 + combined).cumprod()
        overall_sharpe = sharpe_ratio(combined, periods_per_year=365)
        overall_ret = annual_return(combined_eq, periods_per_year=365)
        overall_dd = max_drawdown(combined_eq)

        print(f"\n  COMBINED OOS: Sharpe {overall_sharpe:.2f}, "
              f"Ann {overall_ret:.1%}, DD {overall_dd:.1%}")
        print(f"  Folds: {fold}, OOS days: {len(combined)}")

        return {
            "sharpe": round(overall_sharpe, 2),
            "annual_ret": round(overall_ret, 4),
            "max_dd": round(overall_dd, 4),
            "n_folds": fold,
            "equity": combined_eq,
        }

    return None


# ═══════════════════════════════════════════════════════════════════════
# 3. Fee Sensitivity
# ═══════════════════════════════════════════════════════════════════════

def test_fee_sensitivity(closes, lookback=60, rebal=5, n_long=4):
    """Test with higher fees to account for market impact."""
    print("\n" + "=" * 60)
    print(f"3. FEE SENSITIVITY (L{lookback}, R{rebal}, N{n_long})")
    print("=" * 60)

    for mult in [1.0, 1.5, 2.0, 3.0, 5.0]:
        r = run_xsmom(closes, lookback, rebal, n_long, fee_multiplier=mult)
        print(f"  Fee {mult:.1f}x ({BASE_FEE * mult:.3f}): "
              f"Sharpe {r['sharpe']:.2f}, Ann {r['annual_ret']:.1%}, "
              f"DD {r['max_dd']:.1%}")


# ═══════════════════════════════════════════════════════════════════════
# 4. Correlation with H-009 and H-011
# ═══════════════════════════════════════════════════════════════════════

def test_correlations(daily_data, closes, lookback=60, rebal=5, n_long=4):
    """Compute correlation with H-009 and H-011 equity curves."""
    print("\n" + "=" * 60)
    print("4. CORRELATION ANALYSIS")
    print("=" * 60)

    # H-012 (XSMom)
    r12 = run_xsmom(closes, lookback, rebal, n_long)
    xsmom_eq = r12["equity"]

    # H-009 (BTC daily trend EMA 5/40)
    btc_daily = daily_data.get("BTC/USDT")
    if btc_daily is None:
        print("  No BTC data")
        return None

    h009_res = backtest_single_asset(btc_daily, 5, 40, BASE_FEE, SLIPPAGE_BPS, INITIAL_CAPITAL)
    h009_eq = h009_res["equity_curve"]

    # H-011 (funding rate arb) — simulate from cached data
    funding_file = ROOT / "data" / "BTC_USDT_funding_rates.parquet"
    h011_eq = None
    if funding_file.exists():
        raw = pd.read_parquet(funding_file)
        h011_eq = _simulate_funding_arb(raw, leverage=5.0, lookback_filter=27)

    # Compute correlations
    xsmom_rets = xsmom_eq.pct_change().dropna()
    h009_rets = h009_eq.pct_change().dropna()

    # Daily returns correlation
    common_09 = xsmom_rets.index.intersection(h009_rets.index)
    corr_09 = xsmom_rets.loc[common_09].corr(h009_rets.loc[common_09])
    print(f"  H-012 vs H-009 (BTC trend): r = {corr_09:.3f}")

    if h011_eq is not None:
        h011_rets = h011_eq.pct_change().dropna()
        common_11 = xsmom_rets.index.intersection(h011_rets.index)
        if len(common_11) > 30:
            corr_11 = xsmom_rets.loc[common_11].corr(h011_rets.loc[common_11])
            print(f"  H-012 vs H-011 (funding arb): r = {corr_11:.3f}")

            # Also H-009 vs H-011
            common_all = h009_rets.index.intersection(h011_rets.index)
            corr_09_11 = h009_rets.loc[common_all].corr(h011_rets.loc[common_all])
            print(f"  H-009 vs H-011: r = {corr_09_11:.3f}")

    return {
        "h012_equity": xsmom_eq,
        "h009_equity": h009_eq,
        "h011_equity": h011_eq,
        "corr_12_09": round(corr_09, 3),
    }


def _simulate_funding_arb(raw_funding, leverage=5.0, lookback_filter=27):
    """Simulate H-011 funding rate arb from raw data."""
    df = pd.DataFrame({
        "funding_rate": raw_funding["fundingRate"].values,
    }, index=pd.DatetimeIndex(raw_funding["timestamp"].values, name="timestamp"))
    df = df.sort_index()

    df["rolling_avg"] = df["funding_rate"].rolling(lookback_filter, min_periods=1).mean()
    df["in_position"] = df["rolling_avg"] > 0

    capital = INITIAL_CAPITAL
    equities = []

    for ts, row in df.iterrows():
        if row["in_position"]:
            pnl = capital * leverage * row["funding_rate"]
            capital += pnl
        equities.append(capital)

    # Resample to daily
    eq_series = pd.Series(equities, index=df.index)
    daily_eq = eq_series.resample("1D").last().dropna()
    return daily_eq


# ═══════════════════════════════════════════════════════════════════════
# 5. Three-Strategy Portfolio Simulation
# ═══════════════════════════════════════════════════════════════════════

def test_portfolio(corr_data):
    """Simulate combined portfolio: H-009 + H-011 + H-012."""
    print("\n" + "=" * 60)
    print("5. THREE-STRATEGY PORTFOLIO SIMULATION")
    print("=" * 60)

    h009_eq = corr_data["h009_equity"]
    h011_eq = corr_data["h011_equity"]
    h012_eq = corr_data["h012_equity"]

    if h011_eq is None:
        print("  No H-011 data, testing 2-strategy portfolio")
        h011_eq = None

    # Test various allocations
    allocations = [
        # (h009_pct, h011_pct, h012_pct)
        (0.20, 0.60, 0.20),
        (0.20, 0.50, 0.30),
        (0.30, 0.40, 0.30),
        (0.15, 0.55, 0.30),
        (0.10, 0.60, 0.30),
        (0.20, 0.40, 0.40),
        (0.25, 0.50, 0.25),
        # Also test without H-012 for comparison
        (0.30, 0.70, 0.00),
    ]

    results = []
    for w9, w11, w12 in allocations:
        # Normalize returns to daily
        r9 = h009_eq.pct_change().dropna()
        r12 = h012_eq.pct_change().dropna()

        if h011_eq is not None:
            r11 = h011_eq.pct_change().dropna()
            # Align all three
            common = r9.index.intersection(r11.index).intersection(r12.index)
            if len(common) < 30:
                continue
            port_rets = w9 * r9.loc[common] + w11 * r11.loc[common] + w12 * r12.loc[common]
        else:
            common = r9.index.intersection(r12.index)
            if len(common) < 30:
                continue
            port_rets = w9 * r9.loc[common] + w12 * r12.loc[common]

        port_eq = INITIAL_CAPITAL * (1 + port_rets).cumprod()
        s = sharpe_ratio(port_rets, periods_per_year=365)
        ar = annual_return(port_eq, periods_per_year=365)
        dd = max_drawdown(port_eq)

        label = f"{int(w9*100)}/{int(w11*100)}/{int(w12*100)}"
        results.append({
            "alloc": label,
            "sharpe": round(s, 2),
            "annual_ret": round(ar, 4),
            "max_dd": round(dd, 4),
        })
        note = " ← current (no H-012)" if w12 == 0 else ""
        print(f"  {label}: Sharpe {s:.2f}, Ann {ar:.1%}, DD {dd:.1%}{note}")

    # Best allocation
    with_h012 = [r for r in results if not r["alloc"].endswith("/0")]
    if with_h012:
        best = max(with_h012, key=lambda x: x["sharpe"])
        baseline = [r for r in results if r["alloc"].endswith("/0")]
        print(f"\n  BEST 3-strategy: {best['alloc']} → Sharpe {best['sharpe']:.2f}")
        if baseline:
            b = baseline[0]
            print(f"  Baseline (no H-012): {b['alloc']} → Sharpe {b['sharpe']:.2f}")
            print(f"  Improvement: Sharpe {best['sharpe'] - b['sharpe']:+.2f}, "
                  f"DD {best['max_dd'] - b['max_dd']:+.1%}")

    return results


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("H-012 DEEP VALIDATION: Cross-Sectional Momentum")
    print("=" * 60)

    # Load data
    print("\nLoading data...")
    daily_data = load_daily()
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"Loaded {len(closes.columns)} assets, {len(closes)} days\n")

    # 1. Parameter robustness
    param_df = test_param_robustness(closes)

    # 2. Rolling walk-forward
    wf_result = test_rolling_walk_forward(closes, lookback=60, rebal=5, n_long=4)

    # Also test a few other strong param sets
    for lb, rb, nl in [(14, 7, 4), (60, 3, 4), (45, 5, 4)]:
        test_rolling_walk_forward(closes, lb, rb, nl)

    # 3. Fee sensitivity
    test_fee_sensitivity(closes, lookback=60, rebal=5, n_long=4)

    # 4. Correlations
    corr_data = test_correlations(daily_data, closes, lookback=60, rebal=5, n_long=4)

    # 5. Portfolio simulation
    if corr_data:
        portfolio_results = test_portfolio(corr_data)

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    positive = len(param_df[param_df["sharpe"] > 0])
    total = len(param_df)
    print(f"\n  Param robustness: {positive}/{total} positive ({positive/total:.0%})")
    print(f"  Mean Sharpe across all params: {param_df['sharpe'].mean():.2f}")

    if wf_result:
        print(f"  Rolling WF OOS: Sharpe {wf_result['sharpe']:.2f}, "
              f"Ann {wf_result['annual_ret']:.1%}, DD {wf_result['max_dd']:.1%}")

    # Save results
    import json
    out_path = Path(__file__).parent / "validation_results.json"
    save_data = {
        "param_robustness": {
            "positive_pct": round(positive / total, 2),
            "mean_sharpe": round(param_df["sharpe"].mean(), 2),
            "top_params": param_df.nlargest(5, "sharpe").to_dict("records"),
        },
        "walk_forward": {
            "sharpe": wf_result["sharpe"] if wf_result else None,
            "annual_ret": wf_result["annual_ret"] if wf_result else None,
            "max_dd": wf_result["max_dd"] if wf_result else None,
        },
    }
    with open(out_path, "w") as f:
        json.dump(save_data, f, indent=2, default=str)
    print(f"\n  Saved to {out_path}")


if __name__ == "__main__":
    main()
