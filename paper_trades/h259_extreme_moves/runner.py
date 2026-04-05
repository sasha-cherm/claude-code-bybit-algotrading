"""
H-259 Paper Trade Runner: Extreme Move Frequency Factor

Market-neutral strategy: rank 14 crypto assets by fraction of daily returns
exceeding 2 rolling standard deviations over a lookback window. Long assets
with more extreme moves (breakout potential), short assets with fewer.

Backtest: IS 100% high_long (30/30). Best LB20_R7_N4_high_long Sharpe 2.648
(+197.3% ann, -17.7% DD). WF 5/6 mean OOS 1.320.
Split-half H1=2.315, H2=2.990. Corr H-012 0.272.
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
    "n_long": 4,
    "n_short": 4,
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
    """Load daily close data for all assets."""
    closes_dict = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1d", limit_days=120)
            if len(df) < 50:
                print(f"  {sym}: insufficient data ({len(df)}), skipping")
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
    Rank assets by extreme move frequency (fraction of |return| > 2σ).
    High extreme frequency -> long (breakout potential).
    """
    lookback = CONFIG["lookback"]
    warmup = lookback * 2 + 5

    if date_idx < warmup:
        return {}

    rets = closes.pct_change().dropna()
    ri = date_idx - 1
    if ri < lookback * 2 or ri >= len(rets):
        return {}

    scores = {}
    for col in rets.columns:
        vals = rets[col].values

        # Recent window for counting extremes
        window = vals[ri - lookback:ri]
        # Extended window for standard deviation estimate
        ext_window = vals[max(0, ri - lookback * 2):ri]

        if len(ext_window) < 20:
            continue

        rolling_std = float(np.std(ext_window, ddof=1))
        if rolling_std <= 1e-12:
            continue

        threshold = 2.0 * rolling_std
        n_extreme = int(np.sum(np.abs(window) > threshold))
        frac_extreme = n_extreme / len(window)
        scores[col] = frac_extreme

    valid = pd.Series(scores)
    n_long = CONFIG["n_long"]
    n_short = CONFIG["n_short"]

    if len(valid) < n_long + n_short:
        return {}

    # High extreme frequency -> long (high_long direction)
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
    print("=== H-259 Extreme Move Frequency Paper Trade Runner ===")
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
        print(f"WARNING: Only {len(closes.columns)} of 14 assets loaded, skipping")
        save_state(state)
        return state

    warmup = CONFIG["lookback"] * 2 + 5
    if len(closes) < warmup:
        print("Insufficient data for strategy warmup. Skipping.")
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

    ret = (equity / CONFIG["initial_capital"] - 1) * 100
    print(f"\nEquity: ${equity:,.2f} (start ${CONFIG['initial_capital']:,.2f})")
    print(f"Return: {ret:+.2f}%")
    print(f"Rebalances: {state['rebal_count']}, Trades: {state['total_trades']}")
    print(f"Fees: ${state['total_fees']:.2f}")

    if positions:
        print(f"\nPositions ({len(positions)}):")
        for sym, pos in sorted(positions.items(), key=lambda x: -x[1]["weight"]):
            price_now = float(current_prices.get(sym, pos["entry_price"]))
            pnl = pos["size"] * (price_now - pos["entry_price"])
            print(f"  {pos['direction']:5s} {sym:12s} w={pos['weight']:+.2f} "
                  f"entry=${pos['entry_price']:.4f} now=${price_now:.4f} PnL=${pnl:+.2f}")

        days_since = state.get("days_since_rebal", 0)
        next_rebal = CONFIG["rebal_freq"] - days_since
        print(f"Next rebal in {next_rebal} day(s)")


if __name__ == "__main__":
    state = run()
