"""
H-263 Paper Trade Runner: Relative Strength vs BTC Factor

Market-neutral strategy: rank 13 non-BTC crypto assets by relative return
vs BTC over lookback window. Long assets outperforming BTC (idiosyncratic
strength), short assets underperforming BTC.

Backtest: IS 100% high_long (30/30). Best LB10_R3_N3 Sharpe 4.087.
WF 6/6 mean OOS 4.058. Split-half H1=3.831, H2=0.820. Corr H-012 0.338.
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
    "lookback": 10,
    "rebal_freq": 3,
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
    closes_dict = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1d", limit_days=120)
            if len(df) < 20:
                continue
            dc = df["close"].copy()
            if dc.index.tzinfo is not None:
                dc.index = dc.index.tz_localize(None)
            closes_dict[sym] = dc
        except Exception as e:
            print(f"  {sym}: failed: {e}")

    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    return closes


def compute_rankings(closes: pd.DataFrame, date_idx: int) -> dict:
    """
    Rank non-BTC assets by (asset_return - BTC_return) over lookback.
    High relative strength -> long.
    """
    lookback = CONFIG["lookback"]
    if date_idx < lookback + 1:
        return {}

    if "BTC/USDT" not in closes.columns:
        return {}

    btc_ret = closes["BTC/USDT"].iloc[date_idx] / closes["BTC/USDT"].iloc[date_idx - lookback] - 1
    if not np.isfinite(btc_ret):
        return {}

    scores = {}
    for sym in closes.columns:
        if sym == "BTC/USDT":
            continue
        r = closes[sym].iloc[date_idx] / closes[sym].iloc[date_idx - lookback] - 1
        if np.isfinite(r):
            scores[sym] = r - btc_ret

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
    print("=== H-263 Relative Strength vs BTC Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching daily data for 14 assets...")
    closes = load_data()

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    if len(closes.columns) < 7:
        print(f"WARNING: Only {len(closes.columns)} assets, skipping")
        save_state(state)
        return state

    if len(closes) < CONFIG["lookback"] + 5:
        print("Insufficient data. Skipping.")
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
    date_idx = len(closes) - 1

    if days_since >= CONFIG["rebal_freq"]:
        print(f"Rebalancing (day {days_since} since last rebal)...")

        new_weights = compute_rankings(closes, date_idx)
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
