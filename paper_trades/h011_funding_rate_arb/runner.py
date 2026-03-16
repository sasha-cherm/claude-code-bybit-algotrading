"""
H-011 Paper Trade Runner: Leveraged Funding Rate Arbitrage

Delta-neutral strategy: long BTC spot + short BTC perp, collecting
positive funding rates. Position held when rolling-27 avg funding > 0.

Internal simulation — called each session. Funding settles every 8h
(00:00, 08:00, 16:00 UTC on Bybit), so we check for new settlements.

Leverage model: at Lx, we deploy L * capital in both legs.
At 5x with Bybit UTA, this requires portfolio margin or borrowing.
Max adverse basis move at 5x is ~0.36% historically (well within
20% liquidation threshold).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache

# ── Strategy parameters ──────────────────────────────────────────────
CONFIG = {
    "symbol": "BTC/USDT",
    "leverage": 5.0,
    "filter_lookback": 27,      # rolling avg window (8h periods)
    "min_positive_rate": 0.0,   # only collect when rolling avg > this
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,          # entry/exit fee (charged once at start)
}

STATE_FILE = Path(__file__).parent / "state.json"
LOG_FILE = Path(__file__).parent / "log.json"


# ── State persistence ────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "started": datetime.now(timezone.utc).isoformat(),
        "capital": CONFIG["initial_capital"],
        "in_position": False,
        "position_entry_time": None,
        "notional": 0.0,
        "total_funding_collected": 0.0,
        "total_funding_paid": 0.0,
        "total_fees": 0.0,
        "equity_history": [],
        "last_funding_time": None,
        "settlements_count": 0,
    }


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def load_log() -> list:
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            return json.load(f)
    return []


def save_log(log: list):
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, default=str)


# ── Funding data fetch ───────────────────────────────────────────────
def fetch_recent_funding() -> pd.DataFrame:
    """Fetch recent funding rate data from Bybit via ccxt."""
    import ccxt
    exchange = ccxt.bybit({"enableRateLimit": True})
    exchange.load_markets()

    # Fetch last 100 funding rate records
    try:
        data = exchange.fetch_funding_rate_history("BTC/USDT:USDT", limit=200)
        if not data:
            return pd.DataFrame()

        records = []
        for d in data:
            records.append({
                "timestamp": pd.Timestamp(d["timestamp"], unit="ms", tz="UTC"),
                "funding_rate": d["fundingRate"],
            })
        df = pd.DataFrame(records).set_index("timestamp").sort_index()
        return df
    except Exception as e:
        print(f"  Warning: could not fetch live funding rates: {e}")
        # Fall back to cached data
        cache_file = ROOT / "data" / "BTC_USDT_funding_rates.parquet"
        if cache_file.exists():
            raw = pd.read_parquet(cache_file)
            df = pd.DataFrame({
                "funding_rate": raw["fundingRate"].values,
            }, index=pd.DatetimeIndex(raw["timestamp"].values, name="timestamp"))
            return df.sort_index().tail(200)
        return pd.DataFrame()


# ── Main runner ──────────────────────────────────────────────────────
def run():
    print("=== H-011 Funding Rate Arb Paper Trade ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Leverage: {CONFIG['leverage']}x")

    state = load_state()
    log = load_log()

    # Fetch funding rate data
    print("Fetching funding rate data...")
    df_funding = fetch_recent_funding()

    if df_funding.empty:
        print("No funding data available. Skipping.")
        return state

    # Check for new funding settlements since last run
    last_time = state.get("last_funding_time")
    if last_time:
        last_ts = pd.Timestamp(last_time)
        new_data = df_funding[df_funding.index > last_ts]
    else:
        # First run — process only the latest settlement
        new_data = df_funding.tail(1)

    if new_data.empty:
        print(f"No new funding settlements since {last_time}")
        _print_status(state)
        return state

    print(f"Processing {len(new_data)} new funding settlement(s)")

    # Compute rolling average for filter
    lookback = CONFIG["filter_lookback"]

    for ts, row in new_data.iterrows():
        rate = row["funding_rate"]

        # Get rolling window ending at this timestamp
        window = df_funding.loc[:ts].tail(lookback)
        rolling_avg = window["funding_rate"].mean()

        leverage = CONFIG["leverage"]
        notional = state["capital"] * leverage

        if rolling_avg > CONFIG["min_positive_rate"]:
            # Collect funding
            funding_pnl = notional * rate
            state["capital"] += funding_pnl

            if funding_pnl > 0:
                state["total_funding_collected"] += funding_pnl
            else:
                state["total_funding_paid"] += abs(funding_pnl)

            if not state["in_position"]:
                # Enter position — charge entry fee
                fee = CONFIG["fee_rate"] * notional
                state["capital"] -= fee
                state["total_fees"] += fee
                state["in_position"] = True
                state["position_entry_time"] = str(ts)
                state["notional"] = round(notional, 2)
                log.append({
                    "type": "enter",
                    "time": str(ts),
                    "notional": round(notional, 2),
                    "fee": round(fee, 2),
                })
                print(f"  ENTERED position: ${notional:,.0f} notional, fee ${fee:.2f}")

            action = "collected" if funding_pnl > 0 else "paid"
            print(f"  {ts}: rate {rate:.6f}, {action} ${abs(funding_pnl):.2f} "
                  f"(rolling avg: {rolling_avg:.6f})")

            log.append({
                "type": "funding",
                "time": str(ts),
                "rate": round(rate, 8),
                "rolling_avg": round(rolling_avg, 8),
                "pnl": round(funding_pnl, 2),
                "capital": round(state["capital"], 2),
            })
        else:
            # Exit position if rolling avg goes negative
            if state["in_position"]:
                fee = CONFIG["fee_rate"] * state["notional"]
                state["capital"] -= fee
                state["total_fees"] += fee
                state["in_position"] = False
                log.append({
                    "type": "exit",
                    "time": str(ts),
                    "reason": "rolling_avg_negative",
                    "fee": round(fee, 2),
                })
                print(f"  EXITED: rolling avg negative ({rolling_avg:.6f}), fee ${fee:.2f}")

        state["settlements_count"] += 1

    # Update equity snapshot
    state["equity_history"].append({
        "date": str(new_data.index[-1]),
        "equity": round(state["capital"], 2),
        "in_position": state["in_position"],
    })
    state["last_funding_time"] = str(df_funding.index[-1])
    state["notional"] = round(state["capital"] * CONFIG["leverage"], 2)

    save_state(state)
    save_log(log)

    _print_status(state)
    return state


def _print_status(state: dict):
    initial = CONFIG["initial_capital"]
    equity = state["capital"]
    ret = (equity / initial - 1) * 100

    print(f"\n  Equity: ${equity:,.2f} (start ${initial:,.2f})")
    print(f"  Return: {ret:+.2f}%")
    print(f"  Funding collected: ${state['total_funding_collected']:.2f}")
    print(f"  Funding paid: ${state['total_funding_paid']:.2f}")
    print(f"  Fees: ${state['total_fees']:.2f}")
    print(f"  Settlements: {state['settlements_count']}")
    print(f"  Position: {'IN' if state['in_position'] else 'OUT'}")


def report():
    """Print performance summary."""
    state = load_state()
    if not state["equity_history"]:
        print("No equity history yet.")
        return

    initial = CONFIG["initial_capital"]
    current = state["capital"]

    eq_hist = pd.DataFrame(state["equity_history"])
    eq_hist["date"] = pd.to_datetime(eq_hist["date"])
    days = (eq_hist["date"].iloc[-1] - eq_hist["date"].iloc[0]).days or 1

    print("=== H-011 Funding Rate Arb Report ===")
    print(f"Period: {eq_hist['date'].iloc[0].date()} to {eq_hist['date'].iloc[-1].date()} ({days} days)")
    print(f"Capital: ${initial:,.2f} → ${current:,.2f}")
    print(f"Return: {(current / initial - 1):+.2%}")
    print(f"Annualized: {((current / initial) ** (365 / days) - 1):+.2%}")
    print(f"Leverage: {CONFIG['leverage']}x")
    print(f"Funding collected: ${state['total_funding_collected']:.2f}")
    print(f"Funding paid: ${state['total_funding_paid']:.2f}")
    print(f"Net funding: ${state['total_funding_collected'] - state['total_funding_paid']:.2f}")
    print(f"Fees: ${state['total_fees']:.2f}")
    print(f"Settlements: {state['settlements_count']}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="H-011 Funding Rate Arb")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if args.report:
        report()
    else:
        run()
