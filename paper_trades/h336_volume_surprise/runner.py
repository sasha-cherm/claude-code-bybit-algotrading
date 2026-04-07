"""
H-336 Paper Trade Runner: Volume Surprise Factor

Market-neutral strategy: rank 14 crypto assets by volume surprise
(recent volume / rolling average volume). High surprise = unusual
institutional activity, predicts XS continuation. Low surprise = quiet, short.

Backtest: IS 100% high_long (18/18). Best LB30_R3_N4_high_long Sharpe 2.766
(WF 6/6 mean 2.684). Split-half H1=3.084, H2=2.445.
Corr H-012 0.003, H-076 0.038 — near-zero corr with ALL existing strategies.
Best diversifier found in 337 hypotheses.
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
    "lookback": 30,
    "rebal_freq": 3,
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
    """Load daily data for all assets (close + volume)."""
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
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill().dropna()
    return closes, volumes


def compute_rankings(closes: pd.DataFrame, volumes: pd.DataFrame, date_idx: int) -> dict:
    """
    Rank assets by volume surprise (recent vol / rolling avg vol).
    High surprise -> long (institutional flow).
    """
    lookback = CONFIG["lookback"]
    if date_idx < lookback + 5:
        return {}

    scores = {}
    for sym in closes.columns:
        if sym not in volumes.columns:
            continue
        vol_series = volumes[sym].iloc[max(0, date_idx - lookback): date_idx + 1]
        if len(vol_series) < lookback * 0.5:
            continue
        avg_vol = vol_series.iloc[:-5].mean() if len(vol_series) > 5 else vol_series.mean()
        if avg_vol <= 0:
            continue
        recent = vol_series.iloc[-5:]
        surprise = (recent / avg_vol).mean()
        if np.isfinite(surprise):
            scores[sym] = surprise

    valid = pd.Series(scores)
    n_long = CONFIG["n_long"]
    n_short = CONFIG["n_short"]

    if len(valid) < n_long + n_short:
        return {}

    # High volume surprise -> long
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
    print("=== H-336 Volume Surprise Paper Trade Runner ===")
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

            log.append({
                "date": latest_date,
                "action": "rebalance",
                "capital": state["capital"],
                "positions": {s: p["direction"] for s, p in new_positions.items()},
                "trades": trades_this_rebal,
                "fees": round(total_fees, 2),
            })
            print(f"  Trades: {trades_this_rebal}, Fees: ${total_fees:.2f}")

    # MTM update
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
        "time": datetime.now(timezone.utc).isoformat(),
        "equity": round(equity, 2),
        "date": latest_date,
    })

    if len(state["equity_history"]) > 500:
        state["equity_history"] = state["equity_history"][-250:]

    save_state(state)
    save_log(log)
    _print_status(state, closes)
    return state


def _print_status(state, closes):
    capital = state["capital"]
    initial = CONFIG["initial_capital"]
    equity = state.get("equity", capital)
    pct = (equity / initial - 1) * 100
    print(f"\n  Capital: ${capital:,.2f}")
    print(f"  Equity:  ${equity:,.2f} ({pct:+.2f}%)")
    print(f"  Rebals:  {state.get('rebal_count', 0)}")
    positions = state.get("positions", {})
    print(f"  Positions: {len(positions)}")
    current_prices = closes.iloc[-1] if len(closes) > 0 else pd.Series()
    for sym in sorted(positions.keys()):
        pos = positions[sym]
        pnl = 0
        if sym in current_prices.index:
            pnl = pos["size"] * (float(current_prices[sym]) - pos["entry_price"])
        print(f"    {pos['direction']:5s} {sym:15s} pnl=${pnl:+.2f}")


if __name__ == "__main__":
    state = run()
