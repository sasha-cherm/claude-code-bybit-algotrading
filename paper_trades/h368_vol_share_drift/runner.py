"""
H-368 Paper Trade Runner: Volume Market Share Drift Factor

Market-neutral strategy: rank 14 crypto assets by change in their share of
total market volume. Increasing volume share = growing institutional interest
before price adjusts. Decreasing share = fading interest.

Backtest: IS 90.7% positive (49/54). Best LB30_DW5_R5_N3 Sharpe 1.628
(+85.5% ann, -23.8% DD). WF 6/6 mean 2.034. Split-half H1=1.290, H2=0.382 PASS.
Corr H-012 0.206, H-076 0.115 — low correlation, excellent diversifier.
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
    "lookback": 30,       # rolling mean of volume share
    "drift_window": 5,    # change in share over this many days
    "rebal_freq": 5,
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
    """Load daily close + volume data for all assets."""
    closes_dict = {}
    volumes_dict = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1d", limit_days=120)
            if len(df) < 50:
                continue
            dc = df["close"].copy()
            dv = df["volume"].copy()
            if dc.index.tzinfo is not None:
                dc.index = dc.index.tz_localize(None)
                dv.index = dv.index.tz_localize(None)
            closes_dict[sym] = dc
            volumes_dict[sym] = dv
        except Exception as e:
            print(f"  {sym}: failed: {e}")
    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill().fillna(0)
    return closes, volumes


def compute_rankings(closes: pd.DataFrame, volumes: pd.DataFrame, date_idx: int) -> dict:
    """
    Rank assets by volume market share drift.
    Share = asset_volume / total_market_volume.
    Drift = rolling_mean(share, lookback).diff(drift_window).
    High drift -> volume share increasing -> long.
    """
    lookback = CONFIG["lookback"]
    drift_window = CONFIG["drift_window"]
    min_bars = lookback + drift_window + 5

    if date_idx < min_bars:
        return {}

    # Use data up to date_idx (inclusive)
    vol_slice = volumes.iloc[:date_idx + 1]

    # Compute volume share
    total_vol = vol_slice.sum(axis=1).replace(0, np.nan)
    share = vol_slice.div(total_vol, axis=0)

    # Rolling mean then diff
    rolling_share = share.rolling(lookback).mean()
    drift = rolling_share.diff(drift_window)

    # Get latest values
    latest = drift.iloc[-1].dropna()
    if len(latest) < CONFIG["n_long"] + CONFIG["n_short"]:
        return {}

    # Rank: high drift -> long
    ranked = latest.sort_values(ascending=False)
    longs = ranked.index[:CONFIG["n_long"]]
    shorts = ranked.index[-CONFIG["n_short"]:]

    weights = {}
    for sym in longs:
        weights[sym] = 1.0 / CONFIG["n_long"]
    for sym in shorts:
        weights[sym] = -1.0 / CONFIG["n_short"]
    return weights


def _print_status(state, closes):
    capital = state["capital"]
    equity = capital
    if state["positions"]:
        current_prices = closes.iloc[-1]
        for sym, pos in state["positions"].items():
            if sym in current_prices.index:
                price_now = float(current_prices[sym])
                pnl = pos["size"] * (price_now - pos["entry_price"])
                equity += pnl

    state["equity"] = equity
    save_state(state)

    pnl_pct = (equity / CONFIG["initial_capital"] - 1) * 100
    print(f"\n  Capital: ${capital:,.2f}")
    print(f"  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    print(f"  Rebals:  {state['rebal_count']}")
    print(f"  Positions: {len(state['positions'])}")
    for sym, pos in sorted(state["positions"].items()):
        price_now = float(closes.iloc[-1].get(sym, pos["entry_price"]))
        pnl = pos["size"] * (price_now - pos["entry_price"])
        side = "LONG " if pos["weight"] > 0 else "SHORT"
        print(f"    {side} {sym:15s} pnl=${pnl:.2f}")


def run():
    print("=== H-368 Volume Market Share Drift Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching daily data for 14 assets...")
    closes, volumes = load_data()

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]
        volumes = volumes.iloc[:-1]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    if len(closes.columns) < 7:
        print(f"WARNING: Only {len(closes.columns)} of 14 assets loaded, skipping")
        save_state(state)
        return state

    min_bars = CONFIG["lookback"] + CONFIG["drift_window"] + 5
    if len(closes) < min_bars:
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

        new_weights = compute_rankings(closes, volumes, date_idx)
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
                    "size": size,
                    "entry_price": entry_price,
                    "weight": weight,
                    "entry_date": latest_date,
                }

            capital -= total_fees
            state["capital"] = capital
            state["positions"] = new_positions
            state["last_rebal_date"] = latest_date
            state["rebal_count"] += 1
            state["total_trades"] += trades_this_rebal
            state["total_fees"] += total_fees

            log_entry = {
                "time": datetime.now(timezone.utc).isoformat(),
                "event": "rebalance",
                "date": latest_date,
                "positions": {s: {"w": p["weight"], "size": p["size"]} for s, p in new_positions.items()},
                "capital": capital,
                "fees": total_fees,
                "trades": trades_this_rebal,
            }
            log.append(log_entry)

            print(f"  New positions: {len(new_positions)}")
            for sym, pos in sorted(new_positions.items()):
                side = "LONG " if pos["weight"] > 0 else "SHORT"
                print(f"    {side} {sym}")
            print(f"  Fees: ${total_fees:.2f} ({trades_this_rebal} trades)")
    else:
        print(f"Not rebalancing (day {days_since}/{CONFIG['rebal_freq']})")

    state["last_daily_date"] = latest_date

    # Record equity
    equity = state["capital"]
    current_prices = closes.iloc[-1]
    for sym, pos in state["positions"].items():
        if sym in current_prices.index:
            price_now = float(current_prices[sym])
            equity += pos["size"] * (price_now - pos["entry_price"])

    state["equity"] = equity
    state["equity_history"].append({
        "time": datetime.now(timezone.utc).isoformat(),
        "equity": equity,
        "date": latest_date,
    })

    save_state(state)
    save_log(log)

    _print_status(state, closes)
    return state


if __name__ == "__main__":
    run()
