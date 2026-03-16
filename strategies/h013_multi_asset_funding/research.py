"""
H-013 Research: Multi-Asset Funding Rate Arbitrage

Key question: When BTC funding is negative (H-011 OUT), do other assets
have positive funding? If so, we can diversify funding collection across
multiple assets and reduce time-out-of-market.

Tracks:
1. Fetch 2yr funding rates for top assets
2. Correlation analysis — are funding rates correlated across assets?
3. Composite signal — portfolio of funding arb across assets
4. Backtest multi-asset funding arb with rolling filter
"""

import sys
import time
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
DATA_DIR = ROOT / "data"

# Assets to analyze (all with liquid perps on Bybit)
ASSETS = [
    "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "SUI/USDT:USDT",
    "XRP/USDT:USDT", "DOGE/USDT:USDT", "AVAX/USDT:USDT", "LINK/USDT:USDT",
    "ADA/USDT:USDT", "DOT/USDT:USDT", "NEAR/USDT:USDT", "OP/USDT:USDT",
    "ARB/USDT:USDT", "ATOM/USDT:USDT",
]


def fetch_funding_rates(symbol: str, exchange: ccxt.bybit, limit_days: int = 730) -> pd.DataFrame:
    """Fetch historical funding rates for a symbol."""
    safe_name = symbol.replace("/", "_").replace(":", "_")
    cache_file = DATA_DIR / f"{safe_name}_funding.parquet"

    if cache_file.exists():
        df = pd.read_parquet(cache_file)
        print(f"  Loaded cached {symbol}: {len(df)} records")
        return df

    all_records = []
    since_ms = exchange.milliseconds() - limit_days * 24 * 60 * 60 * 1000
    now_ms = exchange.milliseconds()

    while since_ms < now_ms:
        try:
            data = exchange.fetch_funding_rate_history(symbol, since=since_ms, limit=200)
        except Exception as e:
            print(f"  Error fetching {symbol}: {e}")
            break

        if not data:
            break

        for d in data:
            all_records.append({
                "timestamp": pd.Timestamp(d["timestamp"], unit="ms", tz="UTC"),
                "funding_rate": d["fundingRate"],
            })

        last_ts = data[-1]["timestamp"]
        if last_ts <= since_ms:
            break
        since_ms = last_ts + 1
        if len(data) < 200:
            break
        time.sleep(0.15)  # rate limit

    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records).drop_duplicates(subset=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    df.to_parquet(cache_file)
    print(f"  Fetched {symbol}: {len(df)} records ({df.index.min()} to {df.index.max()})")
    return df


def analyze_diversification(funding_dict: dict[str, pd.DataFrame]):
    """Analyze cross-asset funding rate correlations and diversification."""
    # Align all funding rates to common timestamps
    rates = {}
    for sym, df in funding_dict.items():
        name = sym.split("/")[0]
        rates[name] = df["funding_rate"]

    combined = pd.DataFrame(rates)
    combined = combined.dropna(how="all")
    combined = combined.fillna(0)  # missing = 0 rate

    print("\n=== FUNDING RATE ANALYSIS ===")
    print(f"Period: {combined.index.min()} to {combined.index.max()}")
    print(f"Records: {len(combined)}")

    # 1. Average annualized funding by asset
    print("\n--- Annualized Funding Rates (%) ---")
    ann_rates = combined.mean() * 3 * 365 * 100  # 3 settlements/day * 365
    for name, rate in ann_rates.sort_values(ascending=False).items():
        print(f"  {name:6s}: {rate:+.1f}%")

    # 2. Correlation matrix
    print("\n--- Correlation Matrix (top 6 by avg rate) ---")
    top6 = ann_rates.nlargest(6).index
    corr = combined[top6].corr()
    print(corr.round(2).to_string())

    # 3. Fraction of time each asset has positive funding
    frac_positive = (combined > 0).mean()
    print("\n--- Fraction of Time Positive ---")
    for name, frac in frac_positive.sort_values(ascending=False).items():
        print(f"  {name:6s}: {frac:.1%}")

    # 4. Key question: when BTC rolling-27 is negative, what fraction of
    #    time do other assets have positive rolling-27?
    print("\n--- When BTC Rolling-27 < 0, Other Assets' Rolling-27 Status ---")
    btc_rolling = combined["BTC"].rolling(27).mean()
    btc_negative_mask = btc_rolling < 0

    for name in combined.columns:
        if name == "BTC":
            continue
        asset_rolling = combined[name].rolling(27).mean()
        positive_when_btc_neg = (asset_rolling[btc_negative_mask] > 0).mean()
        avg_rate_when_btc_neg = asset_rolling[btc_negative_mask].mean()
        print(f"  {name:6s}: {positive_when_btc_neg:.1%} positive | avg rate {avg_rate_when_btc_neg * 3 * 365 * 100:+.1f}% ann")

    # 5. Composite: best-of-N strategy — at each settlement, pick the
    #    asset(s) with highest positive rolling-27 funding
    print("\n--- Best-of-N Composite Analysis ---")
    rolling_all = combined.rolling(27).mean().dropna()

    # For each timestamp, count how many assets have positive rolling avg
    positive_count = (rolling_all > 0).sum(axis=1)
    print(f"  Avg assets with positive rolling-27: {positive_count.mean():.1f}")
    print(f"  Min assets positive: {positive_count.min()}")
    print(f"  % of time at least 1 positive: {(positive_count > 0).mean():.1%}")
    print(f"  % of time at least 3 positive: {(positive_count >= 3).mean():.1%}")
    print(f"  % of time ALL negative: {(positive_count == 0).mean():.1%}")

    # Best single asset rolling rate at each timestamp
    best_rate = rolling_all.max(axis=1)
    print(f"\n  Best single asset avg ann rate: {best_rate.mean() * 3 * 365 * 100:+.1f}%")
    print(f"  Best top-3 avg ann rate: {rolling_all.apply(lambda row: row.nlargest(3).mean(), axis=1).mean() * 3 * 365 * 100:+.1f}%")

    return combined, rolling_all


def backtest_multi_asset_funding(
    combined: pd.DataFrame,
    rolling_all: pd.DataFrame,
    n_assets: int = 3,
    leverage: float = 5.0,
    fee_rate: float = 0.001,
    initial_capital: float = 10_000.0,
):
    """
    Backtest multi-asset funding arb: at each settlement, pick the top N
    assets with positive rolling-27 avg funding. Collect their funding.
    """
    print(f"\n=== BACKTEST: Top-{n_assets} Multi-Asset Funding Arb ({leverage}x) ===")

    capital = initial_capital
    capital_per_asset = capital / n_assets
    equity_history = []
    total_fees = 0
    total_collected = 0
    total_paid = 0
    prev_positions = set()

    for ts in rolling_all.index:
        row_rolling = rolling_all.loc[ts]
        row_actual = combined.loc[ts] if ts in combined.index else pd.Series(dtype=float)

        # Select top N assets with positive rolling avg
        positive = row_rolling[row_rolling > 0].nlargest(n_assets)
        current_positions = set(positive.index)

        # Calculate turnover fees
        entered = current_positions - prev_positions
        exited = prev_positions - current_positions
        turnover = len(entered) + len(exited)
        if turnover > 0:
            capital_per_asset = capital / max(len(current_positions), 1)
            fee = fee_rate * capital_per_asset * leverage * turnover
            capital -= fee
            total_fees += fee

        # Collect funding from active positions
        for asset in current_positions:
            if asset in row_actual.index:
                rate = row_actual[asset]
                pnl = (capital / max(len(current_positions), 1)) * leverage * rate
                capital += pnl
                if pnl > 0:
                    total_collected += pnl
                else:
                    total_paid += abs(pnl)

        prev_positions = current_positions
        equity_history.append({"timestamp": ts, "equity": capital, "n_positions": len(current_positions)})

    eq_df = pd.DataFrame(equity_history).set_index("timestamp")
    days = (eq_df.index[-1] - eq_df.index[0]).days or 1
    total_return = capital / initial_capital - 1
    ann_return = (1 + total_return) ** (365 / days) - 1

    # Drawdown
    eq_series = eq_df["equity"]
    rolling_max = eq_series.cummax()
    drawdown = (eq_series - rolling_max) / rolling_max
    max_dd = drawdown.min()

    # Sharpe (daily returns)
    eq_daily = eq_series.resample("1D").last().dropna()
    daily_returns = eq_daily.pct_change().dropna()
    sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(365) if daily_returns.std() > 0 else 0

    # Time in market
    in_market = (eq_df["n_positions"] > 0).mean()

    print(f"  Period: {days} days")
    print(f"  Total return: {total_return:+.2%}")
    print(f"  Annual return: {ann_return:+.2%}")
    print(f"  Max drawdown: {max_dd:.2%}")
    print(f"  Sharpe: {sharpe:.2f}")
    print(f"  Total collected: ${total_collected:,.2f}")
    print(f"  Total paid: ${total_paid:,.2f}")
    print(f"  Fees: ${total_fees:,.2f}")
    print(f"  Time in market: {in_market:.1%}")
    print(f"  Avg positions active: {eq_df['n_positions'].mean():.1f}")
    print(f"  Final equity: ${capital:,.2f}")

    return {
        "n_assets": n_assets,
        "leverage": leverage,
        "total_return": total_return,
        "ann_return": ann_return,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "in_market": in_market,
        "final_equity": capital,
        "fees": total_fees,
    }


def backtest_dynamic_allocation(
    combined: pd.DataFrame,
    rolling_all: pd.DataFrame,
    leverage: float = 5.0,
    fee_rate: float = 0.001,
    initial_capital: float = 10_000.0,
):
    """
    Backtest dynamic allocation: when no funding arb is available (all
    rolling avgs negative), reallocate capital to a simple BTC trend
    following position (proxy for H-009/H-012 returns).
    """
    print(f"\n=== BACKTEST: Dynamic Allocation (Funding + Trend Fallback) ===")

    # Load BTC daily data for trend following proxy
    btc_file = DATA_DIR / "BTC_USDT_1h.parquet"
    btc_df = pd.read_parquet(btc_file)
    btc_daily = btc_df["close"].resample("1D").last().dropna()
    ema5 = btc_daily.ewm(span=5).mean()
    ema40 = btc_daily.ewm(span=40).mean()
    btc_signal = (ema5 > ema40).astype(int) * 2 - 1  # +1 or -1
    btc_returns = btc_daily.pct_change()

    capital = initial_capital
    equity_history = []
    mode_history = []  # "funding" or "trend"
    prev_positions = set()

    for ts in rolling_all.index:
        row_rolling = rolling_all.loc[ts]
        row_actual = combined.loc[ts] if ts in combined.index else pd.Series(dtype=float)

        # Check if any asset has positive rolling funding
        positive = row_rolling[row_rolling > 0]

        if len(positive) > 0:
            # Funding arb mode: pick top 3
            top3 = positive.nlargest(3)
            current_positions = set(top3.index)
            mode = "funding"

            # Turnover fees
            entered = current_positions - prev_positions
            exited = prev_positions - current_positions
            turnover = len(entered) + len(exited)
            if turnover > 0:
                cap_per = capital / len(current_positions)
                fee = fee_rate * cap_per * leverage * turnover
                capital -= fee

            # Collect funding
            for asset in current_positions:
                if asset in row_actual.index:
                    rate = row_actual[asset]
                    pnl = (capital / len(current_positions)) * leverage * rate
                    capital += pnl

            prev_positions = current_positions
        else:
            # No funding available: BTC trend following proxy
            mode = "trend"
            # Find closest daily date
            ts_date = ts.normalize()
            if ts_date in btc_signal.index:
                sig = btc_signal.loc[ts_date]
                ret = btc_returns.loc[ts_date] if ts_date in btc_returns.index else 0
                # Apply 0.2x leverage (vol targeting proxy)
                pnl = capital * 0.2 * sig * ret / 3  # divide by 3 for 8h period
                capital += pnl

            if prev_positions:
                # Exit fee for funding positions
                fee = fee_rate * capital * leverage * len(prev_positions) / max(len(prev_positions), 1)
                capital -= fee
                prev_positions = set()

        equity_history.append({"timestamp": ts, "equity": capital, "mode": mode})

    eq_df = pd.DataFrame(equity_history).set_index("timestamp")
    days = (eq_df.index[-1] - eq_df.index[0]).days or 1
    total_return = capital / initial_capital - 1
    ann_return = (1 + total_return) ** (365 / days) - 1

    eq_series = eq_df["equity"]
    rolling_max = eq_series.cummax()
    drawdown = (eq_series - rolling_max) / rolling_max
    max_dd = drawdown.min()

    eq_daily = eq_series.resample("1D").last().dropna()
    daily_returns = eq_daily.pct_change().dropna()
    sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(365) if daily_returns.std() > 0 else 0

    funding_pct = (eq_df["mode"] == "funding").mean()

    print(f"  Period: {days} days")
    print(f"  Total return: {total_return:+.2%}")
    print(f"  Annual return: {ann_return:+.2%}")
    print(f"  Max drawdown: {max_dd:.2%}")
    print(f"  Sharpe: {sharpe:.2f}")
    print(f"  Time in funding mode: {funding_pct:.1%}")
    print(f"  Time in trend mode: {1 - funding_pct:.1%}")
    print(f"  Final equity: ${capital:,.2f}")

    return {
        "total_return": total_return,
        "ann_return": ann_return,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "funding_pct": funding_pct,
    }


def main():
    print("=== H-013 Research: Multi-Asset Funding Rate Arbitrage ===\n")

    exchange = ccxt.bybit({"enableRateLimit": True})
    exchange.load_markets()

    # 1. Fetch funding rates for all assets
    print("--- Fetching Funding Rates ---")
    funding_dict = {}
    for sym in ASSETS:
        print(f"Fetching {sym}...")
        df = fetch_funding_rates(sym, exchange)
        if not df.empty:
            funding_dict[sym] = df
        time.sleep(0.2)

    if len(funding_dict) < 5:
        print("Not enough data. Aborting.")
        return

    # 2. Analyze diversification
    combined, rolling_all = analyze_diversification(funding_dict)

    # 3. Backtest variants
    results = []

    # Single asset (BTC only — baseline)
    r = backtest_multi_asset_funding(combined[["BTC"]], rolling_all[["BTC"]], n_assets=1, leverage=5.0)
    r["variant"] = "BTC-only (baseline)"
    results.append(r)

    # Top-1 best asset
    r = backtest_multi_asset_funding(combined, rolling_all, n_assets=1, leverage=5.0)
    r["variant"] = "Top-1"
    results.append(r)

    # Top-3
    r = backtest_multi_asset_funding(combined, rolling_all, n_assets=3, leverage=5.0)
    r["variant"] = "Top-3"
    results.append(r)

    # Top-5
    r = backtest_multi_asset_funding(combined, rolling_all, n_assets=5, leverage=5.0)
    r["variant"] = "Top-5"
    results.append(r)

    # All positive
    r = backtest_multi_asset_funding(combined, rolling_all, n_assets=14, leverage=5.0)
    r["variant"] = "All-positive"
    results.append(r)

    # 4. Dynamic allocation (funding + trend fallback)
    backtest_dynamic_allocation(combined, rolling_all, leverage=5.0)

    # 5. Summary
    print("\n=== SUMMARY ===")
    print(f"{'Variant':<20s} {'Ann Ret':>8s} {'MaxDD':>8s} {'Sharpe':>8s} {'InMkt':>8s}")
    print("-" * 56)
    for r in results:
        print(f"{r['variant']:<20s} {r['ann_return']:>+7.1%} {r['max_dd']:>7.2%} {r['sharpe']:>8.2f} {r['in_market']:>7.1%}")

    # Save results
    results_file = Path(__file__).parent / "results.json"
    import json
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {results_file}")


if __name__ == "__main__":
    main()
