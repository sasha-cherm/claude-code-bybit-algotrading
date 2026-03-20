"""
H-049 Paper Trade Runner: Long/Short Ratio Sentiment Factor (Contrarian)

Cross-sectional contrarian sentiment strategy: rank 14 assets by Bybit
long/short ratio. Long assets where crowd is MOST SHORT (lowest LSR),
short assets where crowd is MOST LONG (highest LSR).

Data source: Bybit long/short ratio via ccxt fetch_long_short_ratio_history.
Signal: cross-sectional z-score of daily LSR. Contrarian direction.
Rebalance every 5 days, top/bottom 3.

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

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# ── Strategy parameters ──────────────────────────────────────────────
ASSETS_PERP = [
    "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "SUI/USDT:USDT",
    "XRP/USDT:USDT", "DOGE/USDT:USDT", "AVAX/USDT:USDT", "LINK/USDT:USDT",
    "ADA/USDT:USDT", "DOT/USDT:USDT", "NEAR/USDT:USDT", "OP/USDT:USDT",
    "ARB/USDT:USDT", "ATOM/USDT:USDT",
]
ASSETS_SPOT = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

CONFIG = {
    "rebal_freq": 5,         # rebalance every 5 days
    "n_long": 3,             # long bottom 3 LSR (contrarian)
    "n_short": 3,            # short top 3 LSR (contrarian)
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,       # 0.1% taker
    "slippage_bps": 2.0,
}

STATE_FILE = Path(__file__).parent / "state.json"
LOG_FILE = Path(__file__).parent / "log.json"
LSR_CACHE = Path(__file__).parent / "lsr_cache.parquet"


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
def fetch_lsr_data() -> pd.DataFrame:
    """Fetch daily long/short ratio for all 14 assets from Bybit."""
    import ccxt
    exchange = ccxt.bybit()

    lsr_data = {}
    for sym in ASSETS_PERP:
        name = sym.split('/')[0]
        try:
            time.sleep(0.5)  # Rate limit
            data = exchange.fetch_long_short_ratio_history(sym, '1d', limit=30)
            if data:
                df = pd.DataFrame(data)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = df.set_index('timestamp')
                lsr_data[name] = df['longShortRatio'].astype(float)
        except Exception as e:
            print(f"  {name}: LSR fetch error - {e}")

    if not lsr_data:
        return pd.DataFrame()

    lsr = pd.DataFrame(lsr_data).dropna()
    lsr.index = lsr.index.tz_localize(None).normalize()

    # Merge with cached data
    if LSR_CACHE.exists():
        cached = pd.read_parquet(LSR_CACHE)
        cached.index = cached.index.tz_localize(None).normalize()
        # Combine: cached first, then new (new overwrites if overlapping)
        lsr = pd.concat([cached, lsr])
        lsr = lsr[~lsr.index.duplicated(keep='last')]
        lsr = lsr.sort_index()

    # Save updated cache
    lsr.to_parquet(LSR_CACHE)
    return lsr


def load_daily_prices() -> pd.DataFrame:
    """Fetch current prices for all assets."""
    from lib.data_fetch import fetch_and_cache
    from strategies.daily_trend_multi_asset.strategy import resample_to_daily

    prices = {}
    for sym in ASSETS_SPOT:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=30)
            daily = resample_to_daily(df_1h)
            prices[sym] = daily["close"]
        except Exception as e:
            print(f"  {sym}: price fetch error - {e}")

    closes = pd.DataFrame(prices).dropna()

    # Drop today's incomplete bar
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]

    return closes


# ── Signal generation ────────────────────────────────────────────────
def compute_contrarian_signal(lsr: pd.DataFrame, date) -> dict:
    """
    Cross-sectional z-score of LSR. Contrarian: long LOW LSR, short HIGH LSR.
    Returns {asset_spot_name: weight} dict.
    """
    if date not in lsr.index:
        return {}

    row = lsr.loc[date].dropna()
    if len(row) < CONFIG["n_long"] + CONFIG["n_short"]:
        return {}

    # Cross-sectional z-score
    z = (row - row.mean()) / row.std()

    # Rank: lowest z-score = most shorted by crowd -> LONG
    ranked = z.sort_values()

    n_long = CONFIG["n_long"]
    n_short = CONFIG["n_short"]

    longs = ranked.index[:n_long]   # lowest LSR -> contrarian long
    shorts = ranked.index[-n_short:]  # highest LSR -> contrarian short

    weights = {}
    for name in longs:
        spot_sym = f"{name}/USDT"
        weights[spot_sym] = 1.0 / n_long
    for name in shorts:
        spot_sym = f"{name}/USDT"
        weights[spot_sym] = -1.0 / n_short

    return weights


# ── Main runner ──────────────────────────────────────────────────────
def run():
    print("=== H-049 LSR Sentiment Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    # Fetch LSR data
    print("Fetching long/short ratio data...")
    lsr = fetch_lsr_data()
    if lsr.empty:
        print("No LSR data available. Skipping.")
        return state

    print(f"LSR data: {len(lsr)} days, {len(lsr.columns)} assets")

    # Fetch price data
    print("Fetching price data...")
    closes = load_daily_prices()
    print(f"Prices: {len(closes)} daily bars")

    latest_date = str(closes.index[-1].date())
    slippage = CONFIG["slippage_bps"] / 10_000

    # Check if we have a new daily bar
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

    # Find the LSR date to use (t-1 lagged)
    lsr_date_str = str(closes.index[-2].date()) if len(closes) >= 2 else None
    if lsr_date_str is None:
        print("Not enough price data for lagged signal.")
        state["last_daily_date"] = latest_date
        save_state(state)
        return state

    # ── Rebalance check ───────────────────────────────────────────
    if days_since >= CONFIG["rebal_freq"]:
        # Find closest LSR date (compare as strings to avoid tz issues)
        lsr_date_strs = [str(d.date()) for d in lsr.index]
        valid_dates = [d for d, s in zip(lsr.index, lsr_date_strs) if s <= lsr_date_str]
        lsr_dates = valid_dates
        if len(lsr_dates) == 0:
            print(f"No LSR data available for {lsr_date.date()}")
            state["last_daily_date"] = latest_date
            save_state(state)
            return state

        signal_date = lsr_dates[-1]
        print(f"Rebalancing (day {days_since} since last rebal)...")
        print(f"Using LSR signal from {signal_date.date()}")

        new_weights = compute_contrarian_signal(lsr, signal_date)
        if not new_weights:
            print("  Could not compute signal. Skipping rebalance.")
        else:
            current_prices = closes.iloc[-1]
            old_positions = state["positions"]

            # Mark-to-market existing positions
            capital = state["capital"]
            for sym, pos in old_positions.items():
                if sym in current_prices.index:
                    price_now = float(current_prices[sym])
                    unrealized = pos["size"] * (price_now - pos["entry_price"])
                    capital += unrealized

            # Close all existing and open new (charge fees on turnover)
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

                name = sym.replace("/USDT", "")
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
                "signal_date": str(signal_date.date()),
                "bar_date": latest_date,
                "longs": longs,
                "shorts": shorts,
                "fees": round(total_fees, 2),
                "trades": trades_this_rebal,
                "capital_after": round(capital, 2),
            })

            print(f"  LONG: {', '.join(s.replace('/USDT','') for s in longs)}")
            print(f"  SHORT: {', '.join(s.replace('/USDT','') for s in shorts)}")
            print(f"  Fees: ${total_fees:.2f} ({trades_this_rebal} trades)")
    else:
        print(f"No rebalance needed (day {days_since} of {CONFIG['rebal_freq']})")

    # ── Update equity ────────────────────────────────────────────
    mark_equity = _mark_equity(state, closes)
    state["equity_history"].append({
        "date": latest_date,
        "equity": round(mark_equity, 2),
        "positions": len(state["positions"]),
        "rebalanced": days_since >= CONFIG["rebal_freq"] and bool(state["positions"]),
    })
    state["last_daily_date"] = latest_date

    save_state(state)
    save_log(log)

    _print_status(state, closes)
    return state


def _mark_equity(state: dict, closes: pd.DataFrame) -> float:
    capital = state["capital"]
    for sym, pos in state["positions"].items():
        if sym in closes.columns:
            price = float(closes[sym].iloc[-1])
            unrealized = pos["size"] * (price - pos["entry_price"])
            capital += unrealized
    return capital


def _print_status(state: dict, closes: pd.DataFrame):
    mark = _mark_equity(state, closes)
    initial = CONFIG["initial_capital"]
    print(f"\nEquity: ${mark:,.2f} (start ${initial:,.2f})")
    print(f"Return: {(mark / initial - 1):+.2%}")
    print(f"Rebalances: {state['rebal_count']}, Trades: {state['total_trades']}")
    print(f"Fees: ${state['total_fees']:.2f}")

    if state["positions"]:
        print(f"\nPositions ({len(state['positions'])}):")
        for sym, pos in state["positions"].items():
            name = sym.replace("/USDT", "")
            if sym in closes.columns:
                price_now = float(closes[sym].iloc[-1])
                pnl = pos["size"] * (price_now - pos["entry_price"])
                print(f"  {pos['direction']:5s} {name:12s} w={pos['weight']:+.2f} "
                      f"entry=${pos['entry_price']:.4f} now=${price_now:.4f} PnL=${pnl:+.2f}")

        next_rebal = CONFIG["rebal_freq"] - state.get("days_since_rebal", 0)
        print(f"Next rebal in {next_rebal} day(s)")
    else:
        print("No positions")


if __name__ == "__main__":
    run()
