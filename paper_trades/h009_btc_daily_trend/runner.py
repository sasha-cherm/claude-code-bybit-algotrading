"""
H-009 Paper Trade Runner: BTC Daily EMA Trend Following with Vol Targeting

Internal simulation — no API keys required. Designed to be called each
session (every 4 hours). Only acts when a new daily bar closes.

Signal: EMA(5) vs EMA(40) on BTC/USDT daily close.
Position sizing: vol-targeted to 20% annualized, capped at 2x leverage.
Execution: simulated with 0.1% taker fee + 2bps slippage.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import (
    generate_signals,
    resample_to_daily,
)

# ── Strategy parameters ──────────────────────────────────────────────
CONFIG = {
    "symbol": "BTC/USDT",
    "ema_fast": 5,
    "ema_slow": 40,
    "vol_target": 0.20,       # 20% annualized
    "vol_lookback": 30,       # 30-day realized vol window
    "max_leverage": 2.0,
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,        # 0.1% taker
    "slippage_bps": 2.0,
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
        "position": 0,          # 1=long, -1=short, 0=flat
        "entry_price": 0.0,
        "entry_time": None,
        "size_btc": 0.0,
        "leverage": 0.0,
        "equity_history": [],
        "last_signal_date": None,
        "trades_count": 0,
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


# ── Vol targeting ────────────────────────────────────────────────────
def compute_vol_scale(daily_returns: pd.Series) -> float:
    """Position scale = target_vol / realized_vol, capped at max_leverage."""
    lookback = CONFIG["vol_lookback"]
    if len(daily_returns) < lookback:
        return 1.0
    recent_vol = daily_returns.iloc[-lookback:].std() * np.sqrt(365)
    if recent_vol <= 0 or np.isnan(recent_vol):
        return 1.0
    scale = CONFIG["vol_target"] / recent_vol
    return min(scale, CONFIG["max_leverage"])


# ── Main runner ──────────────────────────────────────────────────────
def run():
    print(f"=== H-009 Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    # Fetch latest BTC data (120 days is plenty for EMA warmup + vol calc)
    print("Fetching BTC/USDT 1h data...")
    df_1h = fetch_and_cache("BTC/USDT", "1h", limit_days=120)
    daily = resample_to_daily(df_1h)

    latest_date = str(daily.index[-1].date())
    current_price = float(daily["close"].iloc[-1])
    slippage = CONFIG["slippage_bps"] / 10_000

    # Check if we have a new daily bar
    if latest_date == state.get("last_signal_date"):
        print(f"No new daily bar since {latest_date}.")
        _print_position(state, current_price)
        return state

    # Generate signal
    signals = generate_signals(
        daily["close"], CONFIG["ema_fast"], CONFIG["ema_slow"]
    )
    current_signal = int(signals.iloc[-1])

    # Compute vol scale
    daily_returns = daily["close"].pct_change().dropna()
    vol_scale = compute_vol_scale(daily_returns)
    realized_vol = daily_returns.iloc[-CONFIG["vol_lookback"]:].std() * np.sqrt(365)

    print(f"Date: {latest_date}")
    print(f"BTC: ${current_price:,.2f}")
    print(f"Signal: {'LONG' if current_signal == 1 else 'SHORT' if current_signal == -1 else 'FLAT'}")
    print(f"Realized vol (30d): {realized_vol:.1%} | Vol scale: {vol_scale:.2f}x")

    # ── Trade execution ──────────────────────────────────────────
    if current_signal != state["position"]:
        # Close existing position
        if state["position"] != 0:
            exit_price = current_price * (1 - state["position"] * slippage)
            pnl = state["position"] * state["size_btc"] * (exit_price - state["entry_price"])
            fee = CONFIG["fee_rate"] * state["size_btc"] * exit_price
            net_pnl = pnl - fee
            state["capital"] += net_pnl

            holding_days = 0
            if state["entry_time"]:
                holding_days = (pd.Timestamp(latest_date) - pd.Timestamp(state["entry_time"])).days

            log.append({
                "type": "close",
                "time": datetime.now(timezone.utc).isoformat(),
                "signal_date": latest_date,
                "direction": "LONG" if state["position"] == 1 else "SHORT",
                "entry_price": state["entry_price"],
                "exit_price": round(exit_price, 2),
                "size_btc": round(state["size_btc"], 8),
                "gross_pnl": round(pnl, 2),
                "fee": round(fee, 2),
                "net_pnl": round(net_pnl, 2),
                "capital_after": round(state["capital"], 2),
                "holding_days": holding_days,
            })
            state["trades_count"] += 1

            print(f"CLOSED {'LONG' if state['position'] == 1 else 'SHORT'}: "
                  f"PnL ${net_pnl:+.2f} (fee ${fee:.2f}), held {holding_days}d")

            state["position"] = 0
            state["size_btc"] = 0.0
            state["entry_price"] = 0.0
            state["entry_time"] = None

        # Open new position
        if current_signal != 0:
            entry_price = current_price * (1 + current_signal * slippage)
            notional = state["capital"] * vol_scale
            size_btc = notional / entry_price
            fee = CONFIG["fee_rate"] * size_btc * entry_price
            state["capital"] -= fee

            state["position"] = current_signal
            state["entry_price"] = round(entry_price, 2)
            state["entry_time"] = latest_date
            state["size_btc"] = round(size_btc, 8)
            state["leverage"] = round(vol_scale, 4)

            log.append({
                "type": "open",
                "time": datetime.now(timezone.utc).isoformat(),
                "signal_date": latest_date,
                "direction": "LONG" if current_signal == 1 else "SHORT",
                "entry_price": round(entry_price, 2),
                "size_btc": round(size_btc, 8),
                "notional": round(notional, 2),
                "leverage": round(vol_scale, 2),
                "fee": round(fee, 2),
                "capital_after": round(state["capital"], 2),
            })

            print(f"OPENED {'LONG' if current_signal == 1 else 'SHORT'}: "
                  f"{size_btc:.6f} BTC @ ${entry_price:,.2f} ({vol_scale:.2f}x)")
    else:
        print(f"No signal change. Holding {'LONG' if state['position'] == 1 else 'SHORT' if state['position'] == -1 else 'FLAT'}.")

    # ── Update equity snapshot ───────────────────────────────────
    mark_equity = _mark_equity(state, current_price)
    state["equity_history"].append({
        "date": latest_date,
        "equity": round(mark_equity, 2),
        "price": current_price,
        "position": state["position"],
        "vol_scale": round(vol_scale, 2),
    })
    state["last_signal_date"] = latest_date

    save_state(state)
    save_log(log)

    print(f"\nEquity: ${mark_equity:,.2f} (start ${CONFIG['initial_capital']:,.2f})")
    print(f"Return: {(mark_equity / CONFIG['initial_capital'] - 1):+.2%}")
    print(f"Total trades: {state['trades_count']}")

    return state


def _mark_equity(state: dict, current_price: float) -> float:
    if state["position"] != 0:
        unrealized = state["position"] * state["size_btc"] * (current_price - state["entry_price"])
        return state["capital"] + unrealized
    return state["capital"]


def _print_position(state: dict, current_price: float):
    if state["position"] != 0:
        unrealized = state["position"] * state["size_btc"] * (current_price - state["entry_price"])
        mark = state["capital"] + unrealized
        print(f"Position: {'LONG' if state['position'] == 1 else 'SHORT'} "
              f"{state['size_btc']:.6f} BTC @ ${state['entry_price']:,.2f}")
        print(f"Current: ${current_price:,.2f} | Unrealized: ${unrealized:+.2f}")
        print(f"Mark equity: ${mark:,.2f}")
    else:
        print(f"Position: FLAT | Capital: ${state['capital']:,.2f}")


# ── Performance report ───────────────────────────────────────────────
def report():
    """Print performance summary from state and log files."""
    state = load_state()
    log = load_log()

    if not state["equity_history"]:
        print("No equity history yet.")
        return

    eq_hist = pd.DataFrame(state["equity_history"])
    eq_hist["date"] = pd.to_datetime(eq_hist["date"])
    eq_hist = eq_hist.set_index("date")

    initial = CONFIG["initial_capital"]
    current = eq_hist["equity"].iloc[-1]
    days = (eq_hist.index[-1] - eq_hist.index[0]).days or 1

    print("=== H-009 Performance Report ===")
    print(f"Period: {eq_hist.index[0].date()} to {eq_hist.index[-1].date()} ({days} days)")
    print(f"Capital: ${initial:,.2f} → ${current:,.2f}")
    print(f"Return: {(current / initial - 1):+.2%}")
    print(f"Annualized: {((current / initial) ** (365 / days) - 1):+.2%}")

    # Drawdown
    peak = eq_hist["equity"].cummax()
    dd = (eq_hist["equity"] - peak) / peak
    print(f"Max drawdown: {dd.min():.2%}")
    print(f"Trades: {state['trades_count']}")

    # Trade stats from log
    closed = [t for t in log if t["type"] == "close"]
    if closed:
        pnls = [t["net_pnl"] for t in closed]
        wins = [p for p in pnls if p > 0]
        print(f"Win rate: {len(wins) / len(pnls):.0%} ({len(wins)}/{len(pnls)})")
        print(f"Avg trade: ${sum(pnls) / len(pnls):+.2f}")
        print(f"Best: ${max(pnls):+.2f} | Worst: ${min(pnls):+.2f}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="H-009 Paper Trade Runner")
    parser.add_argument("--report", action="store_true", help="Print performance report")
    args = parser.parse_args()

    if args.report:
        report()
    else:
        run()
