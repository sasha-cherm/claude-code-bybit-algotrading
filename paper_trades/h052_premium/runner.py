"""
H-052 Paper Trade Runner: Premium Index Cross-Sectional Factor (14 Crypto Assets)

Market-neutral strategy: rank 14 assets by average perpetual premium/discount
over last 5 days. Long bottom 4 (most discounted — shorts aggressive),
short top 4 (least discounted — contrarian).
Rebalance every 5 days.

Internal simulation — called each session. Only acts on new daily bars
and when a rebalance is due.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

# ── Strategy parameters ──────────────────────────────────────────────
ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

ASSET_SYMBOLS = {a: a.replace("/USDT", "USDT") for a in ASSETS}

CONFIG = {
    "premium_window": 5,     # average premium over 5 days
    "rebal_freq": 5,         # rebalance every 5 days
    "n_long": 4,             # long bottom 4 (most discounted)
    "n_short": 4,            # short top 4 (least discounted)
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,       # 0.1% taker
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


# ── Data loading ─────────────────────────────────────────────────────
def fetch_premium_index(symbol: str, days: int = 30) -> pd.DataFrame:
    """Fetch daily premium index klines from Bybit V5 API."""
    end_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ts = end_ts - days * 86400 * 1000

    all_bars = []
    cursor_end = end_ts

    for _ in range(5):
        url = "https://api.bybit.com/v5/market/premium-index-price-kline"
        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": "D",
            "start": start_ts,
            "end": cursor_end,
            "limit": 200,
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if data["retCode"] != 0 or not data["result"]["list"]:
            break

        bars = data["result"]["list"]
        all_bars.extend(bars)

        oldest_ts = int(bars[-1][0])
        if oldest_ts <= start_ts:
            break
        cursor_end = oldest_ts - 1
        time.sleep(0.05)

    if not all_bars:
        return pd.DataFrame()

    df = pd.DataFrame(all_bars, columns=["timestamp", "open", "high", "low", "close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    return df


def load_daily_closes() -> pd.DataFrame:
    """Fetch 1h data for all assets, resample to daily, return close prices."""
    daily_closes = {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=120)
            if len(df_1h) < 200:
                print(f"  {sym}: insufficient data ({len(df_1h)} bars), skipping")
                continue
            daily = resample_to_daily(df_1h)
            daily_closes[sym] = daily["close"]
        except Exception as e:
            print(f"  {sym}: failed to load: {e}")
    closes = pd.DataFrame(daily_closes)
    closes = closes.dropna(how="all").ffill().dropna()
    return closes


def load_premium_data() -> pd.DataFrame:
    """Fetch premium index for all assets, return daily close premium."""
    premium_closes = {}
    for sym in ASSETS:
        bybit_sym = ASSET_SYMBOLS[sym]
        try:
            df = fetch_premium_index(bybit_sym, days=30)
            if len(df) > 0:
                df = df.set_index("timestamp")
                premium_closes[sym] = df["close"]
        except Exception as e:
            print(f"  {sym}: premium fetch failed: {e}")
        time.sleep(0.05)

    premium = pd.DataFrame(premium_closes)
    premium = premium.dropna(how="all").ffill().dropna()
    return premium


# ── Signal generation ────────────────────────────────────────────────
def compute_premium_signal(premium: pd.DataFrame) -> dict:
    """
    Rank assets by average premium over window.
    Contrarian: long most discounted (lowest premium), short least discounted.
    """
    window = CONFIG["premium_window"]
    if len(premium) < window:
        return {}

    # Drop today's incomplete bar
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if str(premium.index[-1].date()) == today_utc:
        premium = premium.iloc[:-1]

    if len(premium) < window:
        return {}

    # Average premium over last window days (lagged — use t-1)
    avg_premium = premium.iloc[-window:].mean()
    valid = avg_premium.dropna()

    n_needed = CONFIG["n_long"] + CONFIG["n_short"]
    if len(valid) < n_needed:
        return {}

    ranked = valid.rank(ascending=True)

    # Contrarian: long most discounted (lowest), short least discounted (highest)
    long_assets = ranked.nsmallest(CONFIG["n_long"]).index
    short_assets = ranked.nlargest(CONFIG["n_short"]).index

    weights = {}
    for sym in long_assets:
        weights[sym] = 1.0 / CONFIG["n_long"]
    for sym in short_assets:
        weights[sym] = -1.0 / CONFIG["n_short"]

    return weights


# ── Main runner ──────────────────────────────────────────────────────
def run():
    print("=== H-052 Premium Index Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    # Fetch latest data
    print("Fetching price data for 14 assets...")
    closes = load_daily_closes()

    # Drop today's incomplete bar
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    print("Fetching premium index data...")
    premium = load_premium_data()
    print(f"Premium data: {len(premium)} days, {len(premium.columns)} assets")

    if len(premium) < CONFIG["premium_window"] + 2:
        print("Insufficient premium data for strategy warmup. Skipping.")
        return state

    latest_date = str(closes.index[-1].date())
    slippage = CONFIG["slippage_bps"] / 10_000

    # Check for new daily bar
    if latest_date == state.get("last_daily_date"):
        print(f"No new daily bar since {latest_date}.")
        _print_status(state, closes)
        return state

    print(f"New daily bar: {latest_date}")

    # Count days since last rebalance
    if state["last_rebal_date"] is None:
        days_since = CONFIG["rebal_freq"]
    else:
        last_rebal = pd.Timestamp(state["last_rebal_date"])
        current = pd.Timestamp(latest_date)
        days_since = (current - last_rebal).days

    state["days_since_rebal"] = days_since

    # ── Rebalance check ───────────────────────────────────────────
    if days_since >= CONFIG["rebal_freq"]:
        print(f"Rebalancing (day {days_since} since last rebal)...")

        new_weights = compute_premium_signal(premium)
        if not new_weights:
            print("  Could not compute premium signal. Skipping rebalance.")
        else:
            current_prices = closes.iloc[-1]
            old_positions = state["positions"]

            # Mark-to-market
            capital = state["capital"]
            for sym, pos in old_positions.items():
                if sym in current_prices.index:
                    price_now = float(current_prices[sym])
                    unrealized = pos["size"] * (price_now - pos["entry_price"])
                    capital += unrealized

            # Apply turnover fees and open new positions
            total_fees = 0.0
            trades_this_rebal = 0

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

            capital -= total_fees
            state["capital"] = round(capital, 2)
            state["positions"] = new_positions
            state["last_rebal_date"] = latest_date
            state["days_since_rebal"] = 0
            state["rebal_count"] += 1
            state["total_trades"] += trades_this_rebal
            state["total_fees"] += total_fees

            longs = [s for s, p in new_positions.items() if p["weight"] > 0]
            shorts = [s for s, p in new_positions.items() if p["weight"] < 0]

            log.append({
                "type": "rebalance",
                "time": datetime.now(timezone.utc).isoformat(),
                "date": latest_date,
                "longs": longs,
                "shorts": shorts,
                "trades": trades_this_rebal,
                "fees": round(total_fees, 2),
                "capital": round(capital, 2),
            })

            print(f"  LONG:  {', '.join(s.replace('/USDT','') for s in longs)}")
            print(f"  SHORT: {', '.join(s.replace('/USDT','') for s in shorts)}")
            print(f"  Trades: {trades_this_rebal}, Fees: ${total_fees:.2f}")
    else:
        print(f"No rebalance today (day {days_since}/{CONFIG['rebal_freq']})")

    # ── Update equity snapshot ───────────────────────────────────
    mark_equity = _mark_equity(state, closes)
    state["equity_history"].append({
        "date": latest_date,
        "equity": round(mark_equity, 2),
        "positions": len(state["positions"]),
        "rebalanced": days_since >= CONFIG["rebal_freq"],
    })
    state["last_daily_date"] = latest_date

    save_state(state)
    save_log(log)

    _print_status(state, closes)
    return state


def _mark_equity(state: dict, closes: pd.DataFrame) -> float:
    capital = state["capital"]
    if not state["positions"]:
        return capital

    current_prices = closes.iloc[-1]
    unrealized = 0.0
    for sym, pos in state["positions"].items():
        if sym in current_prices.index:
            price_now = float(current_prices[sym])
            unrealized += pos["size"] * (price_now - pos["entry_price"])

    return capital + unrealized


def _print_status(state: dict, closes: pd.DataFrame):
    initial = CONFIG["initial_capital"]
    mark = _mark_equity(state, closes)
    ret = mark / initial - 1

    print(f"\nEquity: ${mark:,.2f} (start ${initial:,.2f})")
    print(f"Return: {ret:+.2%}")
    print(f"Rebalances: {state['rebal_count']}, Trades: {state['total_trades']}")
    print(f"Fees: ${state['total_fees']:.2f}")

    if state["positions"]:
        current_prices = closes.iloc[-1]
        print(f"\nPositions ({len(state['positions'])}):")
        for sym, pos in sorted(
            state["positions"].items(),
            key=lambda x: x[1]["weight"],
            reverse=True,
        ):
            price = float(current_prices.get(sym, pos["entry_price"]))
            pnl = pos["size"] * (price - pos["entry_price"])
            print(
                f"  {pos['direction']:5s} {sym:12s} w={pos['weight']:+.2f} "
                f"entry=${pos['entry_price']:.4f} now=${price:.4f} "
                f"PnL=${pnl:+.2f}"
            )
    else:
        print("Positions: FLAT")

    print(f"Next rebal in {CONFIG['rebal_freq'] - state['days_since_rebal']} day(s)")


if __name__ == "__main__":
    run()
