#!/usr/bin/env python3
"""
DCA BTC vs DCA BTC + Covered Call Comparison
=============================================
Compares two strategies over the last 1 year:

1. BENCHMARK: Buy $500 of BTC every Monday (pure DCA)
2. STRATEGY:  Buy $500 of BTC every Monday + sell covered call on entire
              BTC position with 1-week expiry at 5%/7%/10% OTM

Option pricing uses Deribit DVOL (BTC implied volatility index) + Black-Scholes.
BTC spot prices from Bybit API.
Fees from Bybit VIP0 tier.

Usage:
    python scripts/dca_vs_covered_call.py
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from math import log, sqrt, exp

import numpy as np
import pandas as pd
import requests

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from lib.data_fetch import fetch_ohlcv, get_exchange
from scipy.stats import norm

# ─── Configuration ──────────────────────────────────────────────────────────

DCA_AMOUNT = 500.0          # USD per week
LOOKBACK_DAYS = 1095        # 3 years
OTM_LEVELS = [0.05, 0.07, 0.10]  # 5%, 7%, 10% out-of-the-money

# Bybit VIP0 fee schedule
# https://www.bybit.com/en/help-center/article/Fee-Structure
SPOT_TAKER_FEE = 0.001      # 0.10% — taker fee for spot market buy
OPTION_TAKER_FEE = 0.0003   # 0.03% of underlying value — taker fee for USDC options
# Minimum option fee: 0.1 USDC per contract on Bybit
# Delivery fee for exercised options: 0.015% of settlement value
OPTION_DELIVERY_FEE = 0.00015  # 0.015% — charged on exercise/assignment
OPTION_MIN_FEE_USDC = 0.1   # minimum fee per contract (Bybit)

# Risk-free rate (use 0 for crypto)
RISK_FREE_RATE = 0.0

# ─── Black-Scholes ──────────────────────────────────────────────────────────

def bs_call_price(S: float, K: float, T: float, sigma: float, r: float = 0.0) -> float:
    """
    Black-Scholes European call option price.

    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry in years
        sigma: Annualized implied volatility (as decimal, e.g. 0.60 for 60%)
        r: Risk-free rate

    Returns:
        Call option price in USD
    """
    if T <= 0 or sigma <= 0:
        return max(S - K, 0)  # intrinsic value

    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)

    call = S * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)
    return max(call, 0.0)


# ─── Data Fetching ──────────────────────────────────────────────────────────

def fetch_btc_daily_prices() -> pd.DataFrame:
    """Fetch 1 year of BTC/USDT daily candles from Bybit."""
    print("Fetching BTC/USDT daily data from Bybit...")
    start_date = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS + 30)).strftime("%Y-%m-%d")
    df = fetch_ohlcv(
        symbol="BTC/USDT",
        timeframe="1d",
        since=start_date,
    )
    print(f"  Got {len(df)} daily candles from {df.index.min()} to {df.index.max()}")
    return df


def fetch_deribit_dvol(start_ts_ms: int, end_ts_ms: int) -> pd.DataFrame:
    """
    Fetch Deribit DVOL (BTC volatility index) historical data.

    Uses Deribit public API: get_volatility_index_data
    Resolution: 1 day (86400 seconds = 3600*24)
    """
    print("Fetching Deribit DVOL data...")

    url = "https://www.deribit.com/api/v2/public/get_volatility_index_data"

    all_data = []
    chunk_ms = 86400 * 1000 * 30  # 30 days per request
    current_start = start_ts_ms

    while current_start < end_ts_ms:
        current_end = min(current_start + chunk_ms, end_ts_ms)

        params = {
            "currency": "BTC",
            "start_timestamp": int(current_start),
            "end_timestamp": int(current_end),
            "resolution": "1D"
        }

        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        result = resp.json().get("result", {})
        data = result.get("data", [])

        if data:
            all_data.extend(data)

        current_start = current_end
        time.sleep(0.5)  # rate limit

    if not all_data:
        raise ValueError("No DVOL data retrieved from Deribit")

    # DVOL data format: [[timestamp_ms, open, high, low, close], ...]
    df = pd.DataFrame(all_data, columns=["timestamp", "open", "high", "low", "close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]

    print(f"  Got {len(df)} DVOL data points from {df.index.min().date()} to {df.index.max().date()}")
    return df


# ─── Simulation ─────────────────────────────────────────────────────────────

def find_mondays(btc_df: pd.DataFrame) -> list[pd.Timestamp]:
    """Find all Mondays in the date range."""
    start = btc_df.index.min()
    end = btc_df.index.max()

    # Start from 1 year ago
    one_year_ago = end - pd.Timedelta(days=LOOKBACK_DAYS)
    start = max(start, one_year_ago)

    mondays = []
    current = start
    # Advance to first Monday
    while current.weekday() != 0:
        current += pd.Timedelta(days=1)

    while current <= end - pd.Timedelta(days=7):  # need at least 1 week ahead
        mondays.append(current)
        current += pd.Timedelta(days=7)

    return mondays


def get_price_on_date(btc_df: pd.DataFrame, target_date: pd.Timestamp) -> float:
    """Get BTC close price for a specific date (nearest available)."""
    # Normalize to date only for comparison
    target = target_date.normalize()

    # Try exact match first
    if target in btc_df.index:
        return float(btc_df.loc[target, "close"])

    # Find nearest date within 3 days
    for offset in range(1, 4):
        for delta in [pd.Timedelta(days=offset), pd.Timedelta(days=-offset)]:
            candidate = target + delta
            if candidate in btc_df.index:
                return float(btc_df.loc[candidate, "close"])

    raise ValueError(f"No price data near {target_date.date()}")


def get_friday_price(btc_df: pd.DataFrame, monday: pd.Timestamp) -> float:
    """Get BTC price on the Friday of the same week (option expiry)."""
    friday = monday + pd.Timedelta(days=4)
    return get_price_on_date(btc_df, friday)


def get_dvol_on_date(dvol_df: pd.DataFrame, target_date: pd.Timestamp) -> float:
    """Get DVOL value for a specific date (nearest available)."""
    target = target_date.normalize()

    if target in dvol_df.index:
        return float(dvol_df.loc[target, "close"])

    # Find nearest within 5 days
    for offset in range(1, 6):
        for delta in [pd.Timedelta(days=-offset), pd.Timedelta(days=offset)]:
            candidate = target + delta
            if candidate in dvol_df.index:
                return float(dvol_df.loc[candidate, "close"])

    # Fallback: use median DVOL
    return float(dvol_df["close"].median())


def simulate_pure_dca(btc_df: pd.DataFrame, mondays: list[pd.Timestamp]) -> dict:
    """
    Simulate pure DCA: buy $500 of BTC every Monday.

    Returns dict with weekly snapshots and final metrics.
    """
    total_btc = 0.0
    total_invested = 0.0
    weekly_log = []

    for monday in mondays:
        price = get_price_on_date(btc_df, monday)

        # Buy BTC with $500 minus spot fee
        buy_amount_usd = DCA_AMOUNT
        fee = buy_amount_usd * SPOT_TAKER_FEE
        btc_bought = (buy_amount_usd - fee) / price

        total_btc += btc_bought
        total_invested += DCA_AMOUNT
        portfolio_value = total_btc * price

        weekly_log.append({
            "date": monday,
            "btc_price": price,
            "btc_bought": btc_bought,
            "total_btc": total_btc,
            "total_invested": total_invested,
            "portfolio_value": portfolio_value,
            "fees_paid": fee,
        })

    # Final valuation at last Monday's price
    final_price = get_price_on_date(btc_df, mondays[-1])
    final_value = total_btc * final_price
    total_fees = sum(w["fees_paid"] for w in weekly_log)

    return {
        "strategy": "Pure DCA",
        "total_invested": total_invested,
        "final_btc": total_btc,
        "final_value": final_value,
        "total_return_pct": (final_value - total_invested) / total_invested * 100,
        "total_fees": total_fees,
        "weekly_log": weekly_log,
    }


def simulate_dca_covered_call(
    btc_df: pd.DataFrame,
    dvol_df: pd.DataFrame,
    mondays: list[pd.Timestamp],
    otm_pct: float,
) -> dict:
    """
    Simulate DCA + covered call strategy.

    Every Monday:
    1. Settle previous week's call (check Friday close vs strike)
    2. Add $500 fresh capital
    3. Buy BTC with all available cash
    4. Sell 1-week covered call at otm_pct OTM on entire BTC position

    Args:
        otm_pct: Out-of-the-money percentage (e.g. 0.05 for 5%)
    """
    total_btc = 0.0
    cash = 0.0  # accumulated from premiums and exercise proceeds
    total_invested = 0.0
    total_premiums = 0.0
    total_settlements = 0.0  # total paid on exercised calls
    total_fees = 0.0
    n_exercised = 0
    n_expired_otm = 0

    # Previous week's call details
    prev_strike = None
    prev_btc_covered = 0.0

    weekly_log = []

    for i, monday in enumerate(mondays):
        price_monday = get_price_on_date(btc_df, monday)

        # ── Step 1: Settle previous week's call (USDC cash settlement) ──
        if prev_strike is not None and i > 0:
            prev_monday = mondays[i - 1]
            try:
                price_friday = get_friday_price(btc_df, prev_monday)
            except ValueError:
                # If no Friday price, use current Monday as proxy
                price_friday = price_monday

            if price_friday >= prev_strike:
                # Call exercised: cash-settled, pay (settlement - strike) per BTC
                # Seller keeps BTC, pays the ITM amount out of cash
                settlement_cost = (price_friday - prev_strike) * prev_btc_covered
                delivery_fee = price_friday * prev_btc_covered * OPTION_DELIVERY_FEE
                cash -= (settlement_cost + delivery_fee)
                total_settlements += settlement_cost
                total_fees += delivery_fee
                # BTC stays — no physical delivery on Bybit
                n_exercised += 1
            else:
                # Call expired OTM: keep BTC, no payment
                n_expired_otm += 1

        # ── Step 2: Add fresh DCA capital ──
        cash += DCA_AMOUNT
        total_invested += DCA_AMOUNT

        # ── Step 3: Buy or sell BTC to deploy cash ──
        if cash < 0 and total_btc > 0:
            # Cash negative from settlement payout — sell BTC to cover
            btc_to_sell = min(abs(cash) / (price_monday * (1 - SPOT_TAKER_FEE)), total_btc)
            sell_proceeds = btc_to_sell * price_monday
            sell_fee = sell_proceeds * SPOT_TAKER_FEE
            cash += sell_proceeds - sell_fee
            total_btc -= btc_to_sell
            total_fees += sell_fee

        if cash > 0:
            buy_fee = cash * SPOT_TAKER_FEE
            btc_bought = (cash - buy_fee) / price_monday
            total_btc += btc_bought
            total_fees += buy_fee
            cash = 0.0

        # ── Step 4: Sell covered call ──
        strike = price_monday * (1 + otm_pct)
        dvol = get_dvol_on_date(dvol_df, monday)
        sigma = dvol / 100.0  # DVOL is in percentage points (e.g., 60 = 60%)
        T = 7 / 365.0  # 1 week

        # Price one call per 1 BTC using Black-Scholes
        call_price_per_btc = bs_call_price(price_monday, strike, T, sigma, RISK_FREE_RATE)

        # Total premium for selling calls on entire position
        premium = call_price_per_btc * total_btc

        # Option selling fee: 0.03% of underlying value, capped at 12.5% of premium
        # Minimum 0.1 USDC (Bybit VIP0)
        underlying_value = price_monday * total_btc
        option_fee = max(
            min(underlying_value * OPTION_TAKER_FEE, premium * 0.125),
            OPTION_MIN_FEE_USDC
        )

        net_premium = premium - option_fee
        if net_premium < 0:
            net_premium = 0  # don't sell if fee exceeds premium
            option_fee = 0

        cash += net_premium
        total_premiums += net_premium
        total_fees += option_fee

        prev_strike = strike
        prev_btc_covered = total_btc

        portfolio_value = total_btc * price_monday + cash

        weekly_log.append({
            "date": monday,
            "btc_price": price_monday,
            "total_btc": total_btc,
            "cash": cash,
            "total_invested": total_invested,
            "portfolio_value": portfolio_value,
            "dvol": dvol,
            "strike": strike,
            "call_premium_per_btc": call_price_per_btc,
            "total_premium": net_premium,
            "option_fee": option_fee,
        })

    # Settle the very last week's call (cash settlement)
    try:
        last_friday_price = get_friday_price(btc_df, mondays[-1])
    except ValueError:
        last_friday_price = get_price_on_date(btc_df, mondays[-1])

    if prev_strike is not None:
        if last_friday_price >= prev_strike:
            settlement_cost = (last_friday_price - prev_strike) * prev_btc_covered
            delivery_fee = last_friday_price * prev_btc_covered * OPTION_DELIVERY_FEE
            cash -= (settlement_cost + delivery_fee)
            total_settlements += settlement_cost
            total_fees += delivery_fee
            n_exercised += 1
        else:
            n_expired_otm += 1

    # Use last Monday price for final valuation (consistent with pure DCA)
    final_price = get_price_on_date(btc_df, mondays[-1])
    final_value = total_btc * final_price + cash

    return {
        "strategy": f"DCA + Covered Call ({int(otm_pct*100)}% OTM)",
        "otm_pct": otm_pct,
        "total_invested": total_invested,
        "final_btc": total_btc,
        "final_cash": cash,
        "final_value": final_value,
        "total_return_pct": (final_value - total_invested) / total_invested * 100,
        "total_premiums_collected": total_premiums,
        "total_settlements_paid": total_settlements,
        "net_premium_income": total_premiums - total_settlements,
        "total_fees": total_fees,
        "n_exercised": n_exercised,
        "n_expired_otm": n_expired_otm,
        "exercise_rate_pct": n_exercised / max(n_exercised + n_expired_otm, 1) * 100,
        "weekly_log": weekly_log,
    }


# ─── Reporting ──────────────────────────────────────────────────────────────

def print_results(dca_result: dict, cc_results: list[dict]):
    """Print formatted comparison table."""

    print("\n" + "=" * 90)
    print(f"DCA BTC vs DCA BTC + Covered Call — {LOOKBACK_DAYS // 365} Year Backtest")
    print("=" * 90)

    # Basic info
    dca_log = dca_result["weekly_log"]
    print(f"\nPeriod: {dca_log[0]['date'].date()} → {dca_log[-1]['date'].date()}")
    print(f"DCA Amount: ${DCA_AMOUNT:.0f}/week ({len(dca_log)} weeks)")
    print(f"Total Invested: ${dca_result['total_invested']:,.0f}")
    print(f"BTC Price Range: ${min(w['btc_price'] for w in dca_log):,.0f} — ${max(w['btc_price'] for w in dca_log):,.0f}")

    # DVOL info from covered call results
    if cc_results:
        cc_log = cc_results[0]["weekly_log"]
        dvol_values = [w["dvol"] for w in cc_log]
        print(f"DVOL Range: {min(dvol_values):.1f} — {max(dvol_values):.1f} (avg {np.mean(dvol_values):.1f})")

    print(f"\nBybit Fees Applied:")
    print(f"  Spot taker: {SPOT_TAKER_FEE*100:.2f}%")
    print(f"  Option taker: {OPTION_TAKER_FEE*100:.3f}% of underlying")
    print(f"  Option delivery (exercise): {OPTION_DELIVERY_FEE*100:.3f}%")

    # Comparison table
    print("\n" + "-" * 90)
    header = f"{'Metric':<35} {'Pure DCA':>12}"
    for cc in cc_results:
        header += f" {'CC ' + str(int(cc['otm_pct']*100)) + '% OTM':>12}"
    print(header)
    print("-" * 90)

    def row(label, dca_val, cc_vals, fmt=".2f"):
        line = f"{label:<35} {dca_val:>12{fmt}}"
        for v in cc_vals:
            line += f" {v:>12{fmt}}"
        print(line)

    def row_str(label, dca_val, cc_vals):
        line = f"{label:<35} {dca_val:>12}"
        for v in cc_vals:
            line += f" {v:>12}"
        print(line)

    row("Final Portfolio Value ($)", dca_result["final_value"],
        [cc["final_value"] for cc in cc_results], ",.0f")

    row("Total Return (%)", dca_result["total_return_pct"],
        [cc["total_return_pct"] for cc in cc_results], ".2f")

    row("Final BTC Holdings", dca_result["final_btc"],
        [cc["final_btc"] for cc in cc_results], ".6f")

    row_str("Final Cash ($)", "—",
        [f"${cc['final_cash']:,.0f}" for cc in cc_results])

    row_str("Gross Premiums Collected ($)", "—",
        [f"${cc['total_premiums_collected']:,.0f}" for cc in cc_results])

    row_str("Settlements Paid ($)", "—",
        [f"${cc['total_settlements_paid']:,.0f}" for cc in cc_results])

    row_str("Net Premium Income ($)", "—",
        [f"${cc['net_premium_income']:,.0f}" for cc in cc_results])

    row("Total Fees ($)", dca_result["total_fees"],
        [cc["total_fees"] for cc in cc_results], ",.2f")

    row_str("Calls Exercised / Total", "—",
        [f"{cc['n_exercised']}/{cc['n_exercised']+cc['n_expired_otm']}" for cc in cc_results])

    row_str("Exercise Rate (%)", "—",
        [f"{cc['exercise_rate_pct']:.1f}%" for cc in cc_results])

    # Excess return from covered calls
    print("-" * 90)
    row_str("Excess Return vs DCA (%)", "—",
        [f"{cc['total_return_pct'] - dca_result['total_return_pct']:+.2f}%" for cc in cc_results])

    row_str("Excess Value vs DCA ($)", "—",
        [f"${cc['final_value'] - dca_result['final_value']:+,.0f}" for cc in cc_results])

    # Weekly equity curves for drawdown analysis
    print("\n" + "-" * 90)
    print("Risk Metrics (weekly equity curve)")
    print("-" * 90)

    # Build equity curves
    dca_equity = pd.Series(
        [w["portfolio_value"] for w in dca_log],
        index=[w["date"] for w in dca_log]
    )

    dca_peak = dca_equity.cummax()
    dca_dd = ((dca_equity - dca_peak) / dca_peak * 100)

    row("Max Drawdown (%)", abs(dca_dd.min()),
        [], ".2f")

    for cc in cc_results:
        cc_equity = pd.Series(
            [w["portfolio_value"] for w in cc["weekly_log"]],
            index=[w["date"] for w in cc["weekly_log"]]
        )
        cc_peak = cc_equity.cummax()
        cc_dd = ((cc_equity - cc_peak) / cc_peak * 100)
        print(f"  CC {int(cc['otm_pct']*100)}% OTM Max Drawdown:    {abs(cc_dd.min()):>10.2f}%")

    # Weekly premium detail
    print("\n" + "-" * 90)
    print("Weekly Premium Stats")
    print("-" * 90)

    for cc in cc_results:
        premiums = [w["total_premium"] for w in cc["weekly_log"]]
        avg_prem = np.mean(premiums)
        total_prem = sum(premiums)
        prem_yield_weekly = np.mean([
            w["total_premium"] / (w["total_btc"] * w["btc_price"]) * 100
            if w["total_btc"] > 0 else 0
            for w in cc["weekly_log"]
        ])
        prem_yield_annual = prem_yield_weekly * 52

        print(f"\n  CC {int(cc['otm_pct']*100)}% OTM:")
        print(f"    Avg weekly premium:         ${avg_prem:>10,.2f}")
        print(f"    Total premiums:             ${total_prem:>10,.0f}")
        print(f"    Avg weekly yield on pos:    {prem_yield_weekly:>10.3f}%")
        print(f"    Annualized premium yield:   {prem_yield_annual:>10.2f}%")

    print("\n" + "=" * 90)
    print("Notes:")
    print("  - Option prices derived from Black-Scholes using Deribit DVOL index")
    print("  - USDC cash-settled options (Bybit model): keeper keeps BTC, pays ITM diff")
    print("  - Options expire Friday; new calls sold Monday (7-day tenor)")
    print("  - Premiums + exercise proceeds reinvested into BTC on next Monday")
    print("  - All fees are Bybit VIP0 tier (incl. 12.5% premium fee cap)")
    print()
    print("Model Limitations (results likely OVERSTATE real performance):")
    print("  - DVOL is ~30-day ATM IV; actual 7-day OTM IV may be lower (vol skew/term)")
    print("  - No bid-ask spread: real execution at bid, not theoretical mid-price")
    print("  - No slippage or liquidity constraints for larger positions")
    print("  - Assumes perfect weekly option availability at exact OTM strikes")
    print("=" * 90)


def save_results(dca_result: dict, cc_results: list[dict]):
    """Save results to JSON for further analysis."""
    output_dir = PROJECT_ROOT / "results"
    output_dir.mkdir(exist_ok=True)

    output = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "config": {
            "dca_amount": DCA_AMOUNT,
            "lookback_days": LOOKBACK_DAYS,
            "otm_levels": OTM_LEVELS,
            "spot_taker_fee": SPOT_TAKER_FEE,
            "option_taker_fee": OPTION_TAKER_FEE,
            "option_delivery_fee": OPTION_DELIVERY_FEE,
        },
        "pure_dca": {k: v for k, v in dca_result.items() if k != "weekly_log"},
        "covered_call_strategies": [
            {k: v for k, v in cc.items() if k != "weekly_log"}
            for cc in cc_results
        ],
    }

    # Add weekly equity comparison
    weeks = []
    for i, w in enumerate(dca_result["weekly_log"]):
        week_data = {
            "date": w["date"].isoformat(),
            "btc_price": w["btc_price"],
            "dca_value": w["portfolio_value"],
            "dca_btc": w["total_btc"],
        }
        for cc in cc_results:
            otm_key = f"cc_{int(cc['otm_pct']*100)}pct"
            cw = cc["weekly_log"][i]
            week_data[f"{otm_key}_value"] = cw["portfolio_value"]
            week_data[f"{otm_key}_btc"] = cw["total_btc"]
            week_data[f"{otm_key}_premium"] = cw["total_premium"]
            week_data[f"{otm_key}_dvol"] = cw["dvol"]
        weeks.append(week_data)

    output["weekly_data"] = weeks

    outfile = output_dir / "dca_vs_covered_call.json"
    with open(outfile, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nDetailed results saved to: {outfile}")


# ─── Market Regime Analysis ─────────────────────────────────────────────────

# Define market regimes based on BTC price history
MARKET_REGIMES = {
    "FULL (3yr)":  ("2023-04-07", "2026-03-23"),
    "BULL":        ("2023-10-02", "2024-03-25"),  # $27k → $71k
    "FLAT":        ("2024-04-01", "2024-10-28"),  # $71k → $70k sideways
    "BEAR":        ("2025-09-01", "2026-03-23"),  # $114k → $68k
}


def find_mondays_in_range(btc_df: pd.DataFrame, start_str: str, end_str: str) -> list[pd.Timestamp]:
    """Find all Mondays between start and end dates."""
    start = pd.Timestamp(start_str, tz="UTC")
    end = pd.Timestamp(end_str, tz="UTC")

    # Clamp to available data
    start = max(start, btc_df.index.min())
    end = min(end, btc_df.index.max())

    mondays = []
    current = start
    while current.weekday() != 0:
        current += pd.Timedelta(days=1)

    while current <= end - pd.Timedelta(days=7):
        mondays.append(current)
        current += pd.Timedelta(days=7)

    return mondays


def run_scenario(
    btc_df: pd.DataFrame, dvol_df: pd.DataFrame,
    regime_name: str, start_str: str, end_str: str
) -> dict:
    """Run all strategies for a specific market regime."""
    mondays = find_mondays_in_range(btc_df, start_str, end_str)
    if len(mondays) < 4:
        return None

    start_price = get_price_on_date(btc_df, mondays[0])
    end_price = get_price_on_date(btc_df, mondays[-1])
    btc_change = (end_price / start_price - 1) * 100

    dca = simulate_pure_dca(btc_df, mondays)

    ccs = {}
    for otm in OTM_LEVELS:
        cc = simulate_dca_covered_call(btc_df, dvol_df, mondays, otm)
        ccs[int(otm * 100)] = cc

    # Avg DVOL for this period
    dvol_values = [get_dvol_on_date(dvol_df, m) for m in mondays]

    return {
        "regime": regime_name,
        "period": f"{mondays[0].date()} → {mondays[-1].date()}",
        "weeks": len(mondays),
        "btc_start": start_price,
        "btc_end": end_price,
        "btc_change_pct": btc_change,
        "avg_dvol": np.mean(dvol_values),
        "dca": dca,
        "cc": ccs,
    }


def print_comparison_table(scenarios: list[dict]):
    """Print a unified comparison table across all scenarios."""

    print("\n" + "=" * 120)
    print("COMPREHENSIVE COMPARISON: DCA vs DCA + Covered Call across Market Regimes")
    print("=" * 120)

    # ── Header ──
    col_w = 16
    regime_names = [s["regime"] for s in scenarios]
    header_line = f"{'':40}"
    for s in scenarios:
        header_line += f" {s['regime']:>{col_w}}"
    print(f"\n{header_line}")
    print("-" * (40 + col_w * len(scenarios) + len(scenarios)))

    def row(label, values, fmt=">16"):
        line = f"{label:40}"
        for v in values:
            line += f" {v:{fmt}}"
        print(line)

    def row_s(label, values):
        line = f"{label:40}"
        for v in values:
            line += f" {v:>16}"
        print(line)

    # ── Market Context ──
    print("\n--- Market Context ---")
    row_s("Period", [s["period"] for s in scenarios])
    row_s("Weeks", [str(s["weeks"]) for s in scenarios])
    row_s("BTC Start", [f"${s['btc_start']:,.0f}" for s in scenarios])
    row_s("BTC End", [f"${s['btc_end']:,.0f}" for s in scenarios])
    row_s("BTC Change", [f"{s['btc_change_pct']:+.1f}%" for s in scenarios])
    row_s("Avg DVOL", [f"{s['avg_dvol']:.1f}" for s in scenarios])
    row_s("Total Invested", [f"${s['dca']['total_invested']:,.0f}" for s in scenarios])

    # ── Total Return (%) ──
    print("\n--- Total Return (%) ---")
    row_s("Pure DCA", [f"{s['dca']['total_return_pct']:+.2f}%" for s in scenarios])
    for otm in [5, 7, 10]:
        row_s(f"CC {otm}% OTM",
              [f"{s['cc'][otm]['total_return_pct']:+.2f}%" for s in scenarios])

    # ── Excess Return vs DCA (pp) ──
    print("\n--- Excess Return vs DCA (percentage points) ---")
    for otm in [5, 7, 10]:
        row_s(f"CC {otm}% OTM",
              [f"{s['cc'][otm]['total_return_pct'] - s['dca']['total_return_pct']:+.2f}"
               for s in scenarios])

    # ── Final Portfolio Value ($) ──
    print("\n--- Final Portfolio Value ($) ---")
    row_s("Pure DCA", [f"${s['dca']['final_value']:,.0f}" for s in scenarios])
    for otm in [5, 7, 10]:
        row_s(f"CC {otm}% OTM",
              [f"${s['cc'][otm]['final_value']:,.0f}" for s in scenarios])

    # ── Premium / Settlement Breakdown ($) ──
    print("\n--- Gross Premiums Collected ($) ---")
    for otm in [5, 7, 10]:
        row_s(f"CC {otm}% OTM",
              [f"${s['cc'][otm]['total_premiums_collected']:,.0f}" for s in scenarios])

    print("\n--- Settlements Paid on Exercise ($) ---")
    for otm in [5, 7, 10]:
        row_s(f"CC {otm}% OTM",
              [f"${s['cc'][otm]['total_settlements_paid']:,.0f}" for s in scenarios])

    print("\n--- Net Premium Income ($) ---")
    for otm in [5, 7, 10]:
        row_s(f"CC {otm}% OTM",
              [f"${s['cc'][otm]['net_premium_income']:,.0f}" for s in scenarios])

    # ── Exercise Stats ──
    print("\n--- Exercise Rate ---")
    for otm in [5, 7, 10]:
        row_s(f"CC {otm}% OTM",
              [f"{s['cc'][otm]['n_exercised']}/{s['cc'][otm]['n_exercised']+s['cc'][otm]['n_expired_otm']}"
               f" ({s['cc'][otm]['exercise_rate_pct']:.0f}%)"
               for s in scenarios])

    # ── Max Drawdown ──
    print("\n--- Max Drawdown (%) ---")
    for s_data in scenarios:
        # Compute drawdowns inline
        dca_eq = pd.Series([w["portfolio_value"] for w in s_data["dca"]["weekly_log"]])
        dca_dd = abs(((dca_eq - dca_eq.cummax()) / dca_eq.cummax()).min()) * 100
        s_data["_dca_dd"] = dca_dd
        for otm in [5, 7, 10]:
            cc_eq = pd.Series([w["portfolio_value"] for w in s_data["cc"][otm]["weekly_log"]])
            cc_dd = abs(((cc_eq - cc_eq.cummax()) / cc_eq.cummax()).min()) * 100
            s_data[f"_cc{otm}_dd"] = cc_dd

    row_s("Pure DCA", [f"{s['_dca_dd']:.1f}%" for s in scenarios])
    for otm in [5, 7, 10]:
        row_s(f"CC {otm}% OTM",
              [f"{s[f'_cc{otm}_dd']:.1f}%" for s in scenarios])

    # ── Annualized Premium Yield ──
    print("\n--- Avg Weekly Premium Yield on Position ---")
    for otm in [5, 7, 10]:
        yields = []
        for s in scenarios:
            cc_log = s["cc"][otm]["weekly_log"]
            avg_yield = np.mean([
                w["total_premium"] / (w["total_btc"] * w["btc_price"]) * 100
                if w["total_btc"] > 0 else 0
                for w in cc_log
            ])
            yields.append(f"{avg_yield:.3f}% ({avg_yield*52:.0f}%/yr)")
        row_s(f"CC {otm}% OTM", yields)

    # ── Total Fees ──
    print("\n--- Total Fees ($) ---")
    row_s("Pure DCA", [f"${s['dca']['total_fees']:,.0f}" for s in scenarios])
    for otm in [5, 7, 10]:
        row_s(f"CC {otm}% OTM",
              [f"${s['cc'][otm]['total_fees']:,.0f}" for s in scenarios])

    # ── Final BTC Holdings ──
    print("\n--- Final BTC Holdings ---")
    row_s("Pure DCA", [f"{s['dca']['final_btc']:.6f}" for s in scenarios])
    for otm in [5, 7, 10]:
        row_s(f"CC {otm}% OTM",
              [f"{s['cc'][otm]['final_btc']:.6f}" for s in scenarios])

    print("\n" + "=" * 120)
    print("Settlement: Bybit USDC/USDT cash-settled European options")
    print("Option pricing: Black-Scholes with Deribit DVOL (ATM ~30-day IV)")
    print("Fees: Bybit VIP0 (spot 0.10% taker, options 0.03% capped at 12.5% of premium)")
    print()
    print("Model limitations (results likely OVERSTATE real performance):")
    print("  - DVOL is ~30d ATM IV; actual 7-day OTM IV lower due to vol skew & term structure")
    print("  - No bid-ask spread (real fills at bid, ~10-20% below theoretical mid)")
    print("  - No slippage or liquidity constraints")
    print("  - Assumes perfect weekly option availability at exact OTM strikes")
    print("=" * 120)


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    # 1. Fetch all data upfront
    btc_df = fetch_btc_daily_prices()

    start_ts = int((datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS + 30)).timestamp() * 1000)
    end_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    dvol_df = fetch_deribit_dvol(start_ts, end_ts)

    # 2. Run each market regime
    scenarios = []
    for regime_name, (start_str, end_str) in MARKET_REGIMES.items():
        print(f"\n{'='*60}")
        print(f"Running regime: {regime_name}")
        print(f"{'='*60}")
        result = run_scenario(btc_df, dvol_df, regime_name, start_str, end_str)
        if result:
            scenarios.append(result)
        else:
            print(f"  Skipped — not enough data")

    # 3. Print unified comparison
    print_comparison_table(scenarios)

    # 4. Also print per-regime detail and save
    for s in scenarios:
        print(f"\n{'─'*60}")
        print(f"Detail: {s['regime']}")
        print(f"{'─'*60}")
        print_results(s["dca"], list(s["cc"].values()))

    save_results(scenarios[0]["dca"], list(scenarios[0]["cc"].values()))


if __name__ == "__main__":
    main()
