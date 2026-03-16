"""
H-010: Multi-Strategy Portfolio Research

Explores strategies to combine with H-009 (BTC daily trend) to achieve
portfolio Sharpe >= 2.0 for 20% return at <=10% DD.

Research tracks:
1. Leveraged funding rate arb (H-005 derivative)
2. Basis/carry trade (spot-futures premium)
3. Weekly momentum with regime filter
4. Portfolio combination analysis
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import summary as calc_summary, returns_from_equity
from strategies.daily_trend_multi_asset.strategy import (
    generate_signals,
    resample_to_daily,
)

RESULTS_FILE = Path(__file__).parent / "results.json"


# ═══════════════════════════════════════════════════════════════════════
# 1. LEVERAGED FUNDING RATE ARB
# ═══════════════════════════════════════════════════════════════════════

def research_leveraged_funding(df_funding: pd.DataFrame, leverage_levels: list[float]) -> list[dict]:
    """
    Backtest funding rate collection at various leverage levels.

    H-005 showed: Sharpe 4.7+, but only 1.7% annual at 1x.
    Key question: does leveraging a delta-neutral strategy scale linearly?

    Risk model: at leverage L, margin = capital/L. Liquidation occurs if
    spot-perp basis moves against us by (1/L - maintenance_margin).
    We model max adverse basis move from historical data.
    """
    print("\n" + "=" * 60)
    print("TRACK 1: Leveraged Funding Rate Arbitrage")
    print("=" * 60)

    # Use rolling average funding filter (best from H-005 backtest)
    funding = df_funding["funding_rate"].copy()
    rolling_avg = funding.rolling(27, min_periods=5).mean()

    results = []
    for lev in leverage_levels:
        # Strategy: collect funding when rolling avg > 0 (positive funding = short perp collects)
        # At leverage L, we deploy L * capital in short perp + L * capital in long spot
        # Funding collected = L * capital * funding_rate (per 8h settlement)

        capital = 10_000.0
        equity = [capital]
        in_position = False
        max_adverse_move = 0.0

        for i in range(1, len(funding)):
            if pd.isna(rolling_avg.iloc[i]):
                equity.append(equity[-1])
                continue

            rate = funding.iloc[i]

            if rolling_avg.iloc[i] > 0:
                # Collect funding (short perp earns positive funding)
                pnl = lev * capital * rate
                # Simulate basis risk: random adverse move correlated with funding
                # In practice, basis moves are small for delta-neutral
                capital += pnl
                in_position = True
            else:
                in_position = False

            equity.append(capital)

        eq = pd.Series(equity, index=df_funding.index[:len(equity)])
        rets = returns_from_equity(eq)
        metrics = calc_summary(eq, periods_per_year=365 * 3)  # 8h periods = 3/day

        # Compute max drawdown properly
        peak = eq.cummax()
        dd = (eq - peak) / peak

        # Estimate liquidation risk: at leverage L, liquidation if basis
        # moves > 1/L (simplified). Track max consecutive loss.
        consecutive_loss = 0
        max_consecutive = 0
        for r in rets:
            if r < 0:
                consecutive_loss += abs(r)
            else:
                max_consecutive = max(max_consecutive, consecutive_loss)
                consecutive_loss = 0
        max_consecutive = max(max_consecutive, consecutive_loss)

        result = {
            "leverage": lev,
            "annual_return": metrics["annual_return"],
            "max_drawdown": metrics["max_drawdown"],
            "sharpe": metrics["sharpe_ratio"],
            "total_return": metrics["total_return"],
            "max_consecutive_loss_pct": round(max_consecutive * 100, 2),
            "liquidation_threshold_pct": round(100 / lev, 1),
        }
        results.append(result)

        print(f"\n  Leverage {lev}x:")
        print(f"    Annual return: {metrics['annual_return']:+.1%}")
        print(f"    Max drawdown:  {metrics['max_drawdown']:.1%}")
        print(f"    Sharpe:        {metrics['sharpe_ratio']:.2f}")
        print(f"    Max consec loss: {max_consecutive:.2%} (liq at {100/lev:.0f}%)")

    return results


# ═══════════════════════════════════════════════════════════════════════
# 2. BASIS/CARRY TRADE
# ═══════════════════════════════════════════════════════════════════════

def research_basis_trade(df_spot_1h: pd.DataFrame, df_funding: pd.DataFrame) -> list[dict]:
    """
    Research the spot-futures basis (carry) trade.

    The annualized basis = funding_rate * 3 * 365 gives the implied carry.
    Strategy: go long when basis is negative (backwardation = long carry),
    go short when basis is positive (contango = short carry).

    This is different from pure funding arb because we actively trade
    the basis direction rather than just collecting funding.
    """
    print("\n" + "=" * 60)
    print("TRACK 2: Basis/Carry Trade Analysis")
    print("=" * 60)

    # Compute annualized basis from funding rates
    funding = df_funding["funding_rate"].copy()
    ann_basis = funding * 3 * 365  # Annualized

    print(f"\n  Annualized basis statistics:")
    print(f"    Mean:   {ann_basis.mean():.1%}")
    print(f"    Median: {ann_basis.median():.1%}")
    print(f"    Std:    {ann_basis.std():.1%}")
    print(f"    Min:    {ann_basis.min():.1%}")
    print(f"    Max:    {ann_basis.max():.1%}")

    # Quarterly breakdown
    df_basis = pd.DataFrame({"basis": ann_basis})
    df_basis.index = pd.to_datetime(df_basis.index)
    quarterly = df_basis.resample("QE").agg(["mean", "std"])
    print(f"\n  Quarterly annualized basis:")
    for date, row in quarterly.iterrows():
        mean_val = row[("basis", "mean")]
        std_val = row[("basis", "std")]
        if not pd.isna(mean_val):
            print(f"    {date.strftime('%Y-Q%q')}: mean {mean_val:.1%}, std {std_val:.1%}")

    # Strategy: basis-momentum. When basis is trending up (positive and increasing),
    # collect carry. When basis is trending down, reduce exposure.
    results = []

    for lookback in [7, 14, 30]:
        capital = 10_000.0
        equity = [capital]
        basis_ma = ann_basis.rolling(lookback, min_periods=3).mean()

        for i in range(1, len(funding)):
            if pd.isna(basis_ma.iloc[i]):
                equity.append(equity[-1])
                continue

            rate = funding.iloc[i]
            ma_val = basis_ma.iloc[i]

            # Position sizing: scale by basis level
            # When basis is high (contango) → collect carry (short perp + long spot)
            # Scale: min(annualized_basis / 0.10, 2.0) — cap at 2x when basis > 10%
            if ma_val > 0.01:  # Only trade when basis > 1% annualized
                scale = min(ma_val / 0.10, 2.0)
                pnl = scale * capital * rate
                capital += pnl

            equity.append(capital)

        eq = pd.Series(equity, index=df_funding.index[:len(equity)])
        metrics = calc_summary(eq, periods_per_year=365 * 3)

        result = {
            "lookback": lookback,
            "annual_return": metrics["annual_return"],
            "max_drawdown": metrics["max_drawdown"],
            "sharpe": metrics["sharpe_ratio"],
        }
        results.append(result)
        print(f"\n  Basis momentum (MA={lookback}):")
        print(f"    Annual return: {metrics['annual_return']:+.1%}")
        print(f"    Max drawdown:  {metrics['max_drawdown']:.1%}")
        print(f"    Sharpe:        {metrics['sharpe_ratio']:.2f}")

    return results


# ═══════════════════════════════════════════════════════════════════════
# 3. WEEKLY MOMENTUM WITH REGIME FILTER
# ═══════════════════════════════════════════════════════════════════════

def research_weekly_momentum(df_1h: pd.DataFrame) -> list[dict]:
    """
    Weekly timeframe momentum strategy on BTC.

    Different signal from H-009 (daily EMA): uses weekly returns with
    a volatility regime filter. Only trade when vol is in a favorable regime.

    Hypothesis: weekly momentum captures different signal than daily EMA,
    providing diversification benefit.
    """
    print("\n" + "=" * 60)
    print("TRACK 3: Weekly Momentum with Regime Filter")
    print("=" * 60)

    daily = resample_to_daily(df_1h)
    weekly = daily.resample("W").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()

    results = []

    for lookback in [2, 4, 8]:
        for vol_regime in ["all", "low", "high"]:
            capital = 10_000.0
            equity = [capital]
            position = 0
            entry_price = 0.0
            size = 0.0
            trades = []
            fee_rate = 0.001
            slippage = 0.0002

            # Weekly momentum: sign of lookback-week return
            weekly_ret = weekly["close"].pct_change(lookback)
            # Vol regime: 4-week rolling realized vol
            weekly_vol = weekly["close"].pct_change().rolling(12).std() * np.sqrt(52)

            for i in range(max(lookback, 12) + 1, len(weekly)):
                ret = weekly_ret.iloc[i]
                vol = weekly_vol.iloc[i]
                price = weekly["close"].iloc[i]

                if pd.isna(ret) or pd.isna(vol):
                    equity.append(capital + (position * size * (price - entry_price) if position else 0))
                    continue

                # Regime filter
                if vol_regime == "low" and vol > 0.50:
                    target = 0  # Don't trade in high vol
                elif vol_regime == "high" and vol < 0.30:
                    target = 0  # Don't trade in low vol
                else:
                    target = 1 if ret > 0 else -1

                if target != position:
                    # Close
                    if position != 0:
                        exit_p = price * (1 - position * slippage)
                        pnl = position * size * (exit_p - entry_price)
                        fee = fee_rate * size * exit_p
                        capital += pnl - fee
                        trades.append(pnl - fee)
                        position = 0
                        size = 0.0

                    # Open
                    if target != 0:
                        entry_price = price * (1 + target * slippage)
                        size = capital / entry_price
                        fee = fee_rate * size * entry_price
                        capital -= fee
                        position = target

                equity.append(capital + (position * size * (price - entry_price) if position else 0))

            # Close final
            if position != 0:
                price = weekly["close"].iloc[-1]
                exit_p = price * (1 - position * slippage)
                pnl = position * size * (exit_p - entry_price)
                fee = fee_rate * size * exit_p
                capital += pnl - fee
                trades.append(pnl - fee)
                equity[-1] = capital

            eq = pd.Series(equity)
            trade_pnls = pd.Series(trades) if trades else pd.Series(dtype=float)
            metrics = calc_summary(eq, trade_pnls, periods_per_year=52)

            result = {
                "lookback_weeks": lookback,
                "vol_regime": vol_regime,
                "annual_return": metrics["annual_return"],
                "max_drawdown": metrics["max_drawdown"],
                "sharpe": metrics["sharpe_ratio"],
                "n_trades": metrics.get("n_trades", 0),
                "win_rate": metrics.get("win_rate", 0),
            }
            results.append(result)

    # Print top results
    results.sort(key=lambda x: x["sharpe"], reverse=True)
    print(f"\n  Top 5 weekly momentum configurations:")
    for r in results[:5]:
        print(f"    LB={r['lookback_weeks']}w, regime={r['vol_regime']}: "
              f"Sharpe {r['sharpe']:.2f}, return {r['annual_return']:+.1%}, "
              f"DD {r['max_drawdown']:.1%}, trades={r['n_trades']}, WR={r['win_rate']:.0%}")

    return results


# ═══════════════════════════════════════════════════════════════════════
# 4. PORTFOLIO COMBINATION ANALYSIS
# ═══════════════════════════════════════════════════════════════════════

def analyze_portfolio_combination(
    h009_equity: pd.Series,
    funding_equity: pd.Series,
    weights: list[tuple[float, float]],
) -> list[dict]:
    """
    Analyze combining H-009 (daily trend) with funding rate strategy.

    Key question: are they uncorrelated? What portfolio Sharpe can we achieve?
    """
    print("\n" + "=" * 60)
    print("TRACK 4: Portfolio Combination Analysis")
    print("=" * 60)

    # Align equity curves to daily
    h009_daily = h009_equity.resample("1D").last().dropna()
    fund_daily = funding_equity.resample("1D").last().dropna()

    # Find common dates
    common = h009_daily.index.intersection(fund_daily.index)
    if len(common) < 30:
        print("  Insufficient overlapping data for correlation analysis.")
        return []

    h009_rets = h009_daily.loc[common].pct_change().dropna()
    fund_rets = fund_daily.loc[common].pct_change().dropna()

    corr = h009_rets.corr(fund_rets)
    print(f"\n  Correlation (H-009 vs Funding): {corr:.3f}")
    print(f"  H-009 daily Sharpe: {h009_rets.mean() / h009_rets.std() * np.sqrt(365):.2f}")
    print(f"  Funding daily Sharpe: {fund_rets.mean() / fund_rets.std() * np.sqrt(365):.2f}")

    results = []
    for w_trend, w_fund in weights:
        combined_rets = w_trend * h009_rets + w_fund * fund_rets
        combined_eq = 10_000 * (1 + combined_rets).cumprod()
        metrics = calc_summary(combined_eq, periods_per_year=365)

        result = {
            "w_trend": w_trend,
            "w_funding": w_fund,
            "annual_return": metrics["annual_return"],
            "max_drawdown": metrics["max_drawdown"],
            "sharpe": metrics["sharpe_ratio"],
        }
        results.append(result)
        print(f"  {w_trend:.0%}/{w_fund:.0%} (trend/funding): "
              f"Sharpe {metrics['sharpe_ratio']:.2f}, "
              f"return {metrics['annual_return']:+.1%}, "
              f"DD {metrics['max_drawdown']:.1%}")

    return results


# ═══════════════════════════════════════════════════════════════════════
# 5. DAILY MEAN REVERSION (contrarian to H-009)
# ═══════════════════════════════════════════════════════════════════════

def research_daily_mean_reversion(df_1h: pd.DataFrame) -> list[dict]:
    """
    Daily mean reversion: fade large daily moves.

    Hypothesis: BTC daily returns show negative autocorrelation at lag 1-3.
    Trade: if today's return > threshold, short tomorrow (and vice versa).
    This should be uncorrelated (negative correlation) with trend following.
    """
    print("\n" + "=" * 60)
    print("TRACK 5: Daily Mean Reversion (Contrarian)")
    print("=" * 60)

    daily = resample_to_daily(df_1h)
    daily_rets = daily["close"].pct_change().dropna()

    # Check autocorrelation first
    ac1 = daily_rets.autocorr(1)
    ac2 = daily_rets.autocorr(2)
    ac3 = daily_rets.autocorr(3)
    print(f"\n  Daily return autocorrelation:")
    print(f"    Lag 1: {ac1:.4f}")
    print(f"    Lag 2: {ac2:.4f}")
    print(f"    Lag 3: {ac3:.4f}")

    results = []

    for threshold in [0.01, 0.02, 0.03]:
        for hold_days in [1, 2, 3]:
            capital = 10_000.0
            equity = [capital]
            position = 0
            entry_price = 0.0
            size = 0.0
            hold_count = 0
            trades = []
            fee_rate = 0.001
            slippage = 0.0002

            for i in range(1, len(daily)):
                price = daily["close"].iloc[i]
                prev_ret = daily_rets.iloc[i] if i < len(daily_rets) else 0

                # Mark to market
                if position != 0:
                    hold_count += 1

                # Exit after hold_days
                if position != 0 and hold_count >= hold_days:
                    exit_p = price * (1 - position * slippage)
                    pnl = position * size * (exit_p - entry_price)
                    fee = fee_rate * size * exit_p
                    capital += pnl - fee
                    trades.append(pnl - fee)
                    position = 0
                    size = 0.0
                    hold_count = 0

                # Entry: fade large moves
                if position == 0 and not pd.isna(prev_ret):
                    if prev_ret > threshold:
                        # Large up move → short
                        entry_price = price * (1 - slippage)
                        size = capital / entry_price
                        fee = fee_rate * size * entry_price
                        capital -= fee
                        position = -1
                        hold_count = 0
                    elif prev_ret < -threshold:
                        # Large down move → long
                        entry_price = price * (1 + slippage)
                        size = capital / entry_price
                        fee = fee_rate * size * entry_price
                        capital -= fee
                        position = 1
                        hold_count = 0

                equity.append(capital + (position * size * (price - entry_price) if position else 0))

            if position != 0:
                price = daily["close"].iloc[-1]
                pnl = position * size * (price - entry_price)
                fee = fee_rate * size * price
                capital += pnl - fee
                trades.append(pnl - fee)
                equity[-1] = capital

            eq = pd.Series(equity)
            trade_pnls = pd.Series(trades) if trades else pd.Series(dtype=float)
            metrics = calc_summary(eq, trade_pnls, periods_per_year=365)

            result = {
                "threshold": threshold,
                "hold_days": hold_days,
                "annual_return": metrics["annual_return"],
                "max_drawdown": metrics["max_drawdown"],
                "sharpe": metrics["sharpe_ratio"],
                "n_trades": metrics.get("n_trades", 0),
                "win_rate": metrics.get("win_rate", 0),
            }
            results.append(result)

    results.sort(key=lambda x: x["sharpe"], reverse=True)
    print(f"\n  Top 5 daily mean reversion configurations:")
    for r in results[:5]:
        print(f"    threshold={r['threshold']:.0%}, hold={r['hold_days']}d: "
              f"Sharpe {r['sharpe']:.2f}, return {r['annual_return']:+.1%}, "
              f"DD {r['max_drawdown']:.1%}, trades={r['n_trades']}, WR={r['win_rate']:.0%}")

    return results


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("H-010: Multi-Strategy Portfolio Research")
    print("=" * 60)

    # Load data
    print("\nLoading data...")
    df_1h = pd.read_parquet(ROOT / "data" / "BTC_USDT_1h.parquet")
    df_funding_raw = pd.read_parquet(ROOT / "data" / "BTC_USDT_funding_rates.parquet")
    # Re-index funding data by timestamp
    df_funding = pd.DataFrame({
        "funding_rate": df_funding_raw["fundingRate"].values,
    }, index=pd.DatetimeIndex(df_funding_raw["timestamp"].values, name="timestamp"))
    df_funding = df_funding.sort_index()
    print(f"  BTC 1h: {len(df_1h)} bars ({df_1h.index[0].date()} to {df_1h.index[-1].date()})")
    print(f"  Funding: {len(df_funding)} records ({df_funding.index[0].date()} to {df_funding.index[-1].date()})")

    all_results = {}

    # ── Track 1: Leveraged Funding Rate ──
    lev_results = research_leveraged_funding(
        df_funding, leverage_levels=[1, 2, 3, 5, 7, 10]
    )
    all_results["leveraged_funding"] = lev_results

    # ── Track 2: Basis/Carry Trade ──
    basis_results = research_basis_trade(df_1h, df_funding)
    all_results["basis_trade"] = basis_results

    # ── Track 3: Weekly Momentum ──
    weekly_results = research_weekly_momentum(df_1h)
    all_results["weekly_momentum"] = weekly_results

    # ── Track 5: Daily Mean Reversion ──
    mr_results = research_daily_mean_reversion(df_1h)
    all_results["daily_mean_reversion"] = mr_results

    # ── Track 4: Portfolio Combination ──
    # Generate H-009 equity curve for correlation analysis
    daily = resample_to_daily(df_1h)
    h009_bt = _run_h009_backtest(daily)

    # Generate best funding equity curve
    funding = df_funding["funding_rate"]
    rolling_avg = funding.rolling(27, min_periods=5).mean()
    best_lev = 5  # Use 5x leverage
    capital = 10_000.0
    fund_equity = [capital]
    for i in range(1, len(funding)):
        if not pd.isna(rolling_avg.iloc[i]) and rolling_avg.iloc[i] > 0:
            capital += best_lev * capital * funding.iloc[i]
        fund_equity.append(capital)
    fund_eq = pd.Series(fund_equity, index=df_funding.index[:len(fund_equity)])

    portfolio_results = analyze_portfolio_combination(
        h009_bt, fund_eq,
        weights=[(0.7, 0.3), (0.5, 0.5), (0.3, 0.7), (0.6, 0.4), (0.4, 0.6)],
    )
    all_results["portfolio_combination"] = portfolio_results

    # ── Summary ──
    print("\n" + "=" * 60)
    print("SUMMARY: Best candidates for multi-strategy portfolio")
    print("=" * 60)

    # Find best from each track
    if lev_results:
        best_fund = max(lev_results, key=lambda x: x["sharpe"])
        print(f"\n  Best funding arb: {best_fund['leverage']}x leverage, "
              f"Sharpe {best_fund['sharpe']:.2f}, return {best_fund['annual_return']:+.1%}")

    if weekly_results:
        best_weekly = max(weekly_results, key=lambda x: x["sharpe"])
        print(f"  Best weekly momentum: LB={best_weekly['lookback_weeks']}w "
              f"regime={best_weekly['vol_regime']}, Sharpe {best_weekly['sharpe']:.2f}, "
              f"return {best_weekly['annual_return']:+.1%}")

    if mr_results:
        best_mr = max(mr_results, key=lambda x: x["sharpe"])
        print(f"  Best daily MR: threshold={best_mr['threshold']:.0%} "
              f"hold={best_mr['hold_days']}d, Sharpe {best_mr['sharpe']:.2f}, "
              f"return {best_mr['annual_return']:+.1%}")

    if portfolio_results:
        best_port = max(portfolio_results, key=lambda x: x["sharpe"])
        print(f"  Best portfolio: {best_port['w_trend']:.0%}/{best_port['w_funding']:.0%}, "
              f"Sharpe {best_port['sharpe']:.2f}, return {best_port['annual_return']:+.1%}, "
              f"DD {best_port['max_drawdown']:.1%}")

    # Save results
    with open(RESULTS_FILE, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {RESULTS_FILE}")


def _run_h009_backtest(daily: pd.DataFrame) -> pd.Series:
    """Run H-009 strategy to get equity curve for correlation analysis."""
    from strategies.daily_trend_multi_asset.strategy import backtest_single_asset
    result = backtest_single_asset(daily, ema_fast=5, ema_slow=40)
    return result["equity_curve"]


if __name__ == "__main__":
    main()
