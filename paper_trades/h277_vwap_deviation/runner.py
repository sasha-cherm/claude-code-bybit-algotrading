"""
H-277 Paper Trade Runner: VWAP Deviation Factor

Market-neutral strategy: rank 14 crypto assets by deviation of close
from rolling VWAP. Long assets above VWAP (demand pressure), short
assets below VWAP (supply pressure).

Backtest: IS 80% above_vwap_long (24/30). Best LB20_R7_N3 Sharpe 1.384.
WF 5/6 mean OOS 1.256. Split-half H1=1.795, H2=0.867. Corr H-012 0.464.
Neighboring params 21/24 positive (87.5%).
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

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

CONFIG = {
    "lookback": 20,
    "rebal_freq": 7,
    "n_long": 3,
    "n_short": 3,
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,
    "slippage_bps": 2.0,
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
        "positions": {},
        "equity_history": [],
        "last_daily_date": None,
        "last_rebal_date": None,
        "days_since_rebal": 0,
        "rebal_count": 0,
        "total_trades": 0,
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


def load_data():
    ohlcv_dict = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1d", limit_days=120)
            if len(df) < 25:
                continue
            if df.index.tzinfo is not None:
                df.index = df.index.tz_localize(None)
            ohlcv_dict[sym] = df
        except Exception as e:
            print(f"  {sym}: failed: {e}")
    return ohlcv_dict


def compute_rankings(ohlcv_dict: dict, date_idx_map: dict) -> dict:
    """
    Compute VWAP deviation: (close - rolling_VWAP) / rolling_VWAP.
    Long assets most above VWAP, short assets most below.
    """
    lookback = CONFIG["lookback"]
    scores = {}

    for sym, df in ohlcv_dict.items():
        if len(df) < lookback + 2:
            continue
        idx = date_idx_map.get(sym)
        if idx is None or idx < lookback:
            continue

        window = df.iloc[idx - lookback + 1:idx + 1]
        typical_price = (window["high"] + window["low"] + window["close"]) / 3
        vol = window["volume"]

        vol_sum = vol.sum()
        if vol_sum <= 0:
            continue

        vwap = (typical_price * vol).sum() / vol_sum
        close = float(df["close"].iloc[idx])

        if vwap > 0:
            scores[sym] = (close - vwap) / vwap

    valid = pd.Series(scores)
    n_long = CONFIG["n_long"]
    n_short = CONFIG["n_short"]

    if len(valid) < n_long + n_short:
        return {}

    ranked = valid.sort_values(ascending=False)
    longs = ranked.index[:n_long]
    shorts = ranked.index[-n_short:]

    weights = {}
    for sym in longs:
        weights[sym] = 1.0 / n_long
    for sym in shorts:
        weights[sym] = -1.0 / n_short
    return weights


def run():
    print("=== H-277 VWAP Deviation Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching daily data for 14 assets...")
    ohlcv_dict = load_data()

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build closes DataFrame for MTM
    closes_dict = {}
    for sym, df in ohlcv_dict.items():
        closes_dict[sym] = df["close"]
    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()

    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]
        for sym in ohlcv_dict:
            df = ohlcv_dict[sym]
            if len(df) > 0 and str(df.index[-1].date()) == today_utc:
                ohlcv_dict[sym] = df.iloc[:-1]

    print(f"Loaded {len(ohlcv_dict)} assets, {len(closes)} daily bars")

    if len(ohlcv_dict) < 7:
        print(f"WARNING: Only {len(ohlcv_dict)} assets, skipping")
        save_state(state)
        return state

    latest_date = str(closes.index[-1].date())
    slippage = CONFIG["slippage_bps"] / 10_000

    if latest_date == state.get("last_daily_date"):
        print(f"No new daily bar since {latest_date}.")
        _print_status(state, closes)
        return state

    print(f"New daily bar: {latest_date}")

    if state["last_rebal_date"] is None:
        days_since = CONFIG["rebal_freq"]
    else:
        last_rebal = pd.Timestamp(state["last_rebal_date"])
        current = pd.Timestamp(latest_date)
        days_since = (current - last_rebal).days

    state["days_since_rebal"] = days_since
    date_idx_map = {}
    for sym, df in ohlcv_dict.items():
        date_idx_map[sym] = len(df) - 1

    if days_since >= CONFIG["rebal_freq"]:
        print(f"Rebalancing (day {days_since} since last rebal)...")

        new_weights = compute_rankings(ohlcv_dict, date_idx_map)
        if not new_weights:
            print("  Could not compute rankings. Skipping rebalance.")
        else:
            current_prices = closes.iloc[-1]
            old_positions = state["positions"]

            total_fees = 0.0
            trades_this_rebal = 0

            capital = state["capital"]
            for sym, pos in old_positions.items():
                if sym in current_prices.index:
                    price_now = float(current_prices[sym])
                    unrealized = pos["size"] * (price_now - pos["entry_price"])
                    capital += unrealized

            for sym, pos in old_positions.items():
                if sym in current_prices.index:
                    exit_price = float(current_prices[sym])
                    direction = 1 if pos["weight"] > 0 else -1
                    exit_price_adj = exit_price * (1 - direction * slippage)
                    notional = abs(pos["size"]) * exit_price_adj
                    new_w = new_weights.get(sym, 0)
                    if abs(new_w - pos["weight"]) > 0.01:
                        fee = CONFIG["fee_rate"] * notional
                        total_fees += fee
                        trades_this_rebal += 1

            new_positions = {}
            for sym, weight in new_weights.items():
                if sym not in current_prices.index:
                    continue
                price = float(current_prices[sym])
                direction = 1 if weight > 0 else -1
                entry_price = price * (1 + direction * slippage)
                notional = capital * abs(weight)
                size = direction * notional / entry_price

                old_w = old_positions.get(sym, {}).get("weight", 0)
                if abs(weight - old_w) > 0.01:
                    fee = CONFIG["fee_rate"] * notional
                    total_fees += fee
                    trades_this_rebal += 1

                new_positions[sym] = {
                    "weight": weight,
                    "entry_price": round(entry_price, 6),
                    "size": round(size, 8),
                    "direction": "LONG" if weight > 0 else "SHORT",
                }

            n_min = CONFIG["n_long"] + CONFIG["n_short"]
            if len(new_positions) < n_min:
                print(f"  WARNING: Only {len(new_positions)}/{n_min} positions, aborting")
                new_positions = old_positions
                total_fees = 0
                trades_this_rebal = 0

            capital -= total_fees
            state["capital"] = round(capital, 2)
            state["positions"] = new_positions
            state["last_rebal_date"] = latest_date
            state["days_since_rebal"] = 0
            state["rebal_count"] += 1
            state["total_trades"] += trades_this_rebal
            state["total_fees"] += total_fees

            log_entry = {
                "date": latest_date,
                "action": "rebalance",
                "capital": state["capital"],
                "positions": {
                    sym: {"dir": p["direction"], "entry": p["entry_price"],
                          "w": p["weight"]}
                    for sym, p in new_positions.items()
                },
                "trades": trades_this_rebal,
                "fees": round(total_fees, 4),
            }
            log.append(log_entry)

            print(f"  Trades: {trades_this_rebal}, Fees: ${total_fees:.2f}")
            for sym, p in sorted(new_positions.items()):
                print(f"    {p['direction']} {sym} w={p['weight']:+.2f} @ ${p['entry_price']}")

    # Mark to market
    current_prices = closes.iloc[-1]
    equity = state["capital"]
    for sym, pos in state["positions"].items():
        if sym in current_prices.index:
            price_now = float(current_prices[sym])
            unrealized = pos["size"] * (price_now - pos["entry_price"])
            equity += unrealized

    state["equity"] = round(equity, 2)
    state["last_daily_date"] = latest_date
    state["equity_history"].append({
        "date": latest_date,
        "equity": round(equity, 2),
    })

    save_state(state)
    save_log(log)

    _print_status(state, closes)
    return state


def _print_status(state, closes):
    current_prices = closes.iloc[-1]
    equity = state["capital"]
    positions = state["positions"]

    for sym, pos in positions.items():
        if sym in current_prices.index:
            price_now = float(current_prices[sym])
            unrealized = pos["size"] * (price_now - pos["entry_price"])
            equity += unrealized

    pnl_pct = (equity / CONFIG["initial_capital"] - 1) * 100
    print(f"\n  Capital: ${state['capital']:,.2f}")
    print(f"  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    print(f"  Rebals:  {state['rebal_count']}")
    print(f"  Positions: {len(positions)}")
    for sym, pos in sorted(positions.items()):
        if sym in current_prices.index:
            price_now = float(current_prices[sym])
            pnl = pos["size"] * (price_now - pos["entry_price"])
            print(f"    {pos['direction']:5s} {sym:12s} pnl=${pnl:+.2f}")


if __name__ == "__main__":
    run()
