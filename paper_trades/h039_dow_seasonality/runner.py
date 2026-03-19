"""
H-039 Paper Trade Runner: Day-of-Week Seasonality (Long Wed / Short Thu)

Internal simulation. Designed to run hourly via cron — only acts on new daily bars.

Signal (fixed, no parameters):
- Tuesday daily close → enter LONG BTC (captures Wednesday move)
- Wednesday daily close → flip to SHORT BTC (captures Thursday move)
- Thursday daily close → close SHORT, go FLAT
- Flat Friday through Tuesday

Walk-forward: 6/6 positive folds, mean OOS Sharpe 2.46 (BTC).
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

CONFIG = {
    "symbol": "BTC/USDT",
    "initial_capital": 10_000.0,
    "fee_rate": 0.0004,       # 4 bps (2 bps maker + 2 bps slippage)
    "leverage": 1.0,          # 1x notional — simple position
}

STATE_FILE = Path(__file__).parent / "state.json"
LOG_FILE = Path(__file__).parent / "log.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "started": datetime.now(timezone.utc).isoformat(),
        "capital": CONFIG["initial_capital"],
        "position": 0,       # 1=long, -1=short, 0=flat
        "entry_price": 0.0,
        "entry_time": None,
        "size_btc": 0.0,
        "equity_history": [],
        "last_signal_date": None,
        "trades_count": 0,
        "total_fees": 0.0,
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


def get_target_position(day_of_week: int) -> int:
    """Return target position based on the day of the CLOSING bar.

    When we see a Tuesday close, we want to be LONG for Wednesday.
    When we see a Wednesday close, we want to be SHORT for Thursday.
    When we see a Thursday close, we want to be FLAT.
    """
    if day_of_week == 1:    # Tuesday close → go LONG (for Wed)
        return 1
    elif day_of_week == 2:  # Wednesday close → go SHORT (for Thu)
        return -1
    elif day_of_week == 3:  # Thursday close → go FLAT
        return 0
    else:
        return None  # No action on other days


def execute_trade(state, log, direction, price, date_str, action_type):
    """Execute a position change."""
    # Close existing position if any
    if state["position"] != 0:
        exit_price = price
        pnl = state["position"] * state["size_btc"] * (exit_price - state["entry_price"])
        fee = CONFIG["fee_rate"] * state["size_btc"] * exit_price
        net_pnl = pnl - fee
        state["capital"] += net_pnl
        state["total_fees"] += fee

        log.append({
            "type": "close",
            "time": datetime.now(timezone.utc).isoformat(),
            "signal_date": date_str,
            "direction": "LONG" if state["position"] == 1 else "SHORT",
            "entry_price": state["entry_price"],
            "exit_price": round(exit_price, 2),
            "size_btc": round(state["size_btc"], 8),
            "gross_pnl": round(pnl, 2),
            "fee": round(fee, 2),
            "net_pnl": round(net_pnl, 2),
            "capital_after": round(state["capital"], 2),
        })
        state["trades_count"] += 1

        print(f"  CLOSED {'LONG' if state['position'] == 1 else 'SHORT'}: "
              f"PnL ${net_pnl:+.2f} (fee ${fee:.2f})")

        state["position"] = 0
        state["size_btc"] = 0.0
        state["entry_price"] = 0.0
        state["entry_time"] = None

    # Open new position if direction != 0
    if direction != 0:
        entry_price = price
        notional = state["capital"] * CONFIG["leverage"]
        size_btc = notional / entry_price
        fee = CONFIG["fee_rate"] * size_btc * entry_price
        state["capital"] -= fee
        state["total_fees"] += fee

        state["position"] = direction
        state["entry_price"] = round(entry_price, 2)
        state["entry_time"] = date_str
        state["size_btc"] = round(size_btc, 8)

        log.append({
            "type": "open",
            "time": datetime.now(timezone.utc).isoformat(),
            "signal_date": date_str,
            "direction": "LONG" if direction == 1 else "SHORT",
            "entry_price": round(entry_price, 2),
            "size_btc": round(size_btc, 8),
            "notional": round(notional, 2),
            "fee": round(fee, 2),
            "capital_after": round(state["capital"], 2),
        })

        print(f"  OPENED {'LONG' if direction == 1 else 'SHORT'}: "
              f"{size_btc:.6f} BTC @ ${entry_price:,.2f}")


def mark_equity(state: dict, current_price: float) -> float:
    if state["position"] != 0:
        unrealized = state["position"] * state["size_btc"] * (current_price - state["entry_price"])
        return state["capital"] + unrealized
    return state["capital"]


def run():
    print("=== H-039 DOW Seasonality Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    # Fetch latest BTC data
    print("Fetching BTC/USDT 1h data...")
    df_1h = fetch_and_cache("BTC/USDT", "1h", limit_days=30)
    df_1h = df_1h.reset_index() if 'timestamp' not in df_1h.columns else df_1h
    if 'timestamp' not in df_1h.columns:
        df_1h = df_1h.reset_index()

    df_1h['date'] = pd.to_datetime(df_1h['timestamp']).dt.date
    daily = df_1h.groupby('date').agg({'close': 'last'}).reset_index()
    daily = daily.sort_values('date').reset_index(drop=True)

    latest_date = str(daily['date'].iloc[-1])
    current_price = float(daily['close'].iloc[-1])
    latest_dow = pd.Timestamp(latest_date).dayofweek  # 0=Mon, 6=Sun

    dow_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    print(f"Latest bar: {latest_date} ({dow_names[latest_dow]})")
    print(f"BTC: ${current_price:,.2f}")

    # Check for new daily bar
    if latest_date == state.get("last_signal_date"):
        print(f"No new daily bar since {latest_date}.")
        eq = mark_equity(state, current_price)
        _print_status(state, current_price, eq)
        return state

    # Determine target position
    target = get_target_position(latest_dow)

    if target is not None and target != state["position"]:
        print(f"Signal: {dow_names[latest_dow]} close → target {'LONG' if target == 1 else 'SHORT' if target == -1 else 'FLAT'}")
        execute_trade(state, log, target, current_price, latest_date, "dow_signal")
    elif target is not None:
        print(f"Already in target position for {dow_names[latest_dow]}.")
    else:
        # Non-trading day — check if we should be flat
        if state["position"] != 0 and latest_dow in [4, 5, 6, 0]:
            # Should be flat on Fri-Mon
            print(f"Cleanup: going FLAT on {dow_names[latest_dow]}")
            execute_trade(state, log, 0, current_price, latest_date, "cleanup")

    # Update equity snapshot
    eq = mark_equity(state, current_price)
    state["equity_history"].append({
        "date": latest_date,
        "equity": round(eq, 2),
        "price": current_price,
        "position": state["position"],
        "dow": dow_names[latest_dow],
    })
    state["last_signal_date"] = latest_date

    save_state(state)
    save_log(log)

    _print_status(state, current_price, eq)
    return state


def _print_status(state, current_price, eq):
    print(f"\nEquity: ${eq:,.2f} (start ${CONFIG['initial_capital']:,.2f})")
    print(f"Return: {(eq / CONFIG['initial_capital'] - 1):+.2%}")
    print(f"Total trades: {state['trades_count']}")
    print(f"Total fees: ${state['total_fees']:.2f}")
    if state["position"] != 0:
        unrealized = state["position"] * state["size_btc"] * (current_price - state["entry_price"])
        print(f"Position: {'LONG' if state['position'] == 1 else 'SHORT'} "
              f"{state['size_btc']:.6f} BTC @ ${state['entry_price']:,.2f} "
              f"| Unrealized: ${unrealized:+.2f}")
    else:
        print("Position: FLAT")


if __name__ == "__main__":
    run()
