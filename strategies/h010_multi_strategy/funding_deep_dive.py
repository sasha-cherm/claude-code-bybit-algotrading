"""
H-010 Deep Dive: Leveraged Funding Rate Arb — realistic forward estimate.

Key concerns:
1. Funding rates are declining (22.7% Q1'24 → 1.6% Q1'26)
2. UTA capital efficiency: spot margin covers perp, but leverage needs borrowing
3. Need walk-forward validation, not full-sample backtest
4. Portfolio combination with H-009

This script runs more conservative analysis.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import summary as calc_summary, returns_from_equity
from strategies.daily_trend_multi_asset.strategy import (
    backtest_single_asset,
    generate_signals,
    resample_to_daily,
)


def main():
    print("H-010 Deep Dive: Funding Rate + Portfolio Analysis")
    print("=" * 60)

    # Load data
    df_1h = pd.read_parquet(ROOT / "data" / "BTC_USDT_1h.parquet")
    df_funding_raw = pd.read_parquet(ROOT / "data" / "BTC_USDT_funding_rates.parquet")
    df_funding = pd.DataFrame({
        "funding_rate": df_funding_raw["fundingRate"].values,
    }, index=pd.DatetimeIndex(df_funding_raw["timestamp"].values, name="timestamp"))
    df_funding = df_funding.sort_index()

    # ── 1. Period-specific funding analysis ──────────────────────
    print("\n1. Funding rate by half-year period:")
    for year in [2024, 2025, 2026]:
        for half in [1, 2]:
            start = f"{year}-{'01' if half == 1 else '07'}-01"
            end = f"{year}-{'07' if half == 1 else '12'}-31"
            mask = (df_funding.index >= start) & (df_funding.index <= end)
            period_data = df_funding.loc[mask, "funding_rate"]
            if len(period_data) > 10:
                ann = period_data.mean() * 3 * 365
                pct_positive = (period_data > 0).mean()
                print(f"  {year} H{half}: ann {ann:.1%}, "
                      f"positive {pct_positive:.0%}, n={len(period_data)}")

    # ── 2. Walk-forward: train on first 60%, test on last 40% ───
    print("\n2. Walk-forward validation (60/40 split):")
    n = len(df_funding)
    split = int(n * 0.6)
    train_fund = df_funding.iloc[:split]
    test_fund = df_funding.iloc[split:]

    print(f"  Train: {train_fund.index[0].date()} to {train_fund.index[-1].date()}")
    print(f"  Test:  {test_fund.index[0].date()} to {test_fund.index[-1].date()}")

    for lev in [1, 3, 5]:
        # Train: determine if strategy works (it always does — just collect positive funding)
        for label, data in [("Train", train_fund), ("Test", test_fund)]:
            capital = 10_000.0
            equity = [capital]
            rolling_avg = data["funding_rate"].rolling(27, min_periods=5).mean()
            for i in range(1, len(data)):
                if not pd.isna(rolling_avg.iloc[i]) and rolling_avg.iloc[i] > 0:
                    capital += lev * equity[-1] * data["funding_rate"].iloc[i]
                equity.append(capital)
            eq = pd.Series(equity, index=data.index[:len(equity)])
            metrics = calc_summary(eq, periods_per_year=365 * 3)
            print(f"  {label} {lev}x: return {metrics['annual_return']:+.1%}, "
                  f"DD {metrics['max_drawdown']:.2%}, Sharpe {metrics['sharpe_ratio']:.1f}")

    # ── 3. Conservative forward estimate (last 6 months only) ───
    print("\n3. Conservative estimate (last 6 months only):")
    last_6m = df_funding.iloc[-int(6 * 30 * 3):]  # ~6 months of 8h data
    mean_rate = last_6m["funding_rate"].mean()
    ann_rate = mean_rate * 3 * 365
    pct_pos = (last_6m["funding_rate"] > 0).mean()
    print(f"  Recent 6mo avg funding: {mean_rate*100:.4f}% per 8h = {ann_rate:.1%} ann")
    print(f"  Positive rate: {pct_pos:.0%} of periods")

    for lev in [1, 3, 5, 7]:
        # Conservative model: only count when positive, apply actual rate
        capital = 10_000.0
        equity = [capital]
        for i in range(1, len(last_6m)):
            rate = last_6m["funding_rate"].iloc[i]
            rolling = last_6m["funding_rate"].iloc[max(0, i - 27):i].mean()
            if rolling > 0:
                capital += lev * equity[-1] * rate
            equity.append(capital)
        eq = pd.Series(equity)
        metrics = calc_summary(eq, periods_per_year=365 * 3)
        print(f"  {lev}x leverage: return {metrics['annual_return']:+.1%}, "
              f"DD {metrics['max_drawdown']:.2%}")

    # ── 4. Portfolio combination: H-009 + Funding ───────────────
    print("\n4. Portfolio combination (H-009 trend + Funding rate arb):")

    # Generate H-009 daily equity curve
    daily = resample_to_daily(df_1h)
    h009_result = backtest_single_asset(daily, ema_fast=5, ema_slow=40)
    h009_eq = h009_result["equity_curve"]

    # Normalize both indices to tz-naive dates
    h009_eq.index = h009_eq.index.tz_localize(None)

    # Generate funding equity at various leverage (daily resolution)
    fund_daily_rets = df_funding["funding_rate"].copy()
    fund_daily_rets.index = fund_daily_rets.index.tz_localize(None)
    fund_daily_rets = fund_daily_rets.resample("1D").sum()

    # H-009 daily returns
    h009_rets = h009_eq.pct_change().dropna()

    # Align
    common = h009_rets.index.intersection(fund_daily_rets.index)
    print(f"  Common dates: {len(common)}")

    if len(common) < 30:
        print(f"  Insufficient overlap. H-009 range: {h009_eq.index[0]} to {h009_eq.index[-1]}")
        print(f"  Funding range: {fund_daily_rets.index[0]} to {fund_daily_rets.index[-1]}")
    else:
        h009_rets = h009_rets.loc[common]
        corr = None

        for lev in [3, 5]:
            fund_rets = fund_daily_rets.loc[common].fillna(0) * lev

            corr = h009_rets.corr(fund_rets)
            print(f"\n  Funding at {lev}x:")
            print(f"    Correlation with H-009: {corr:.3f}")

            h009_sharpe = h009_rets.mean() / h009_rets.std() * np.sqrt(365)
            fund_sharpe = fund_rets.mean() / fund_rets.std() * np.sqrt(365) if fund_rets.std() > 0 else 0
            print(f"    H-009 Sharpe: {h009_sharpe:.2f}")
            print(f"    Funding Sharpe: {fund_sharpe:.2f}")

            for w_trend in [0.3, 0.4, 0.5, 0.6, 0.7]:
                w_fund = 1 - w_trend
                combined_rets = w_trend * h009_rets + w_fund * fund_rets
                combined_eq = 10_000 * (1 + combined_rets).cumprod()
                metrics = calc_summary(combined_eq, periods_per_year=365)

                print(f"    {w_trend:.0%} trend / {w_fund:.0%} funding: "
                      f"Sharpe {metrics['sharpe_ratio']:.2f}, "
                      f"return {metrics['annual_return']:+.1%}, "
                      f"DD {metrics['max_drawdown']:.1%}")

    # ── 5. Estimate required allocation to hit 20%/10% target ───
    print("\n5. Target allocation analysis (20% return, ≤10% DD):")

    # H-009 stats (full period)
    h009_metrics = calc_summary(h009_eq, periods_per_year=365)
    h009_ann_ret = h009_metrics["annual_return"]
    h009_dd = h009_metrics["max_drawdown"]
    h009_vol = h009_rets.std() * np.sqrt(365)

    # Funding stats (5x leverage)
    fund_5x_rets = fund_daily_rets.loc[common].fillna(0) * 5
    fund_ann_ret = fund_5x_rets.mean() * 365
    fund_vol = fund_5x_rets.std() * np.sqrt(365)

    # Recent 6mo funding
    recent_6m_fund = fund_5x_rets.iloc[-180:]
    fund_recent_ann = recent_6m_fund.mean() * 365

    correlation = corr if corr is not None else 0.0

    print(f"  H-009: {h009_ann_ret:+.1%} annual, {h009_dd:.1%} DD, {h009_vol:.1%} vol")
    print(f"  Funding 5x (full): {fund_ann_ret:+.1%} annual, {fund_vol:.1%} vol")
    print(f"  Funding 5x (recent 6mo): {fund_recent_ann:+.1%} annual")
    print(f"  Correlation: {correlation:.3f}")

    print(f"\n  Portfolio optimization (using full-period returns):")
    for w1 in np.arange(0.1, 1.0, 0.1):
        w2 = 1 - w1
        ret = w1 * h009_ann_ret + w2 * fund_ann_ret
        vol = np.sqrt(w1**2 * h009_vol**2 + w2**2 * fund_vol**2
                      + 2 * w1 * w2 * correlation * h009_vol * fund_vol)
        sharpe = ret / vol if vol > 0 else 0
        est_dd = vol * 1.5  # empirical DD estimate
        print(f"    {w1:.0%}/{w2:.0%}: ret {ret:+.1%}, vol {vol:.1%}, "
              f"Sharpe {sharpe:.2f}, est DD {est_dd:.1%}")

    print(f"\n  Conservative estimate (recent 6mo funding):")
    for w1 in np.arange(0.1, 1.0, 0.1):
        w2 = 1 - w1
        ret = w1 * h009_ann_ret + w2 * fund_recent_ann
        vol = np.sqrt(w1**2 * h009_vol**2 + w2**2 * fund_vol**2
                      + 2 * w1 * w2 * correlation * h009_vol * fund_vol)
        sharpe = ret / vol if vol > 0 else 0
        est_dd = vol * 1.5
        print(f"    {w1:.0%}/{w2:.0%}: ret {ret:+.1%}, vol {vol:.1%}, "
              f"Sharpe {sharpe:.2f}, est DD {est_dd:.1%}")

    # Save results
    results = {
        "h009_annual_return": round(h009_ann_ret, 4),
        "h009_max_drawdown": round(h009_dd, 4),
        "h009_vol": round(float(h009_vol), 4),
        "funding_5x_annual_return": round(float(fund_ann_ret), 4),
        "funding_5x_vol": round(float(fund_vol), 4),
        "funding_5x_recent_6m": round(float(fund_recent_ann), 4),
        "correlation": round(float(correlation), 4),
    }
    with open(Path(__file__).parent / "portfolio_analysis.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to portfolio_analysis.json")


if __name__ == "__main__":
    main()
