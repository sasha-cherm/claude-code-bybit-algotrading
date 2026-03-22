"""
H-059 Paper Trade Runner: Volatility Term Structure Factor (14 Crypto Assets)

Market-neutral strategy: compare short-term (7d) vs long-term (30d) realized vol.
Expansion-long: long top 5 assets with expanding vol (short/long ratio > 1),
short bottom 5 with contracting vol (short/long ratio < 1).
Rebalance every 7 days.

Backtest: IS Sharpe 2.57, +149.9% ann, 24.5% DD. WF 4/6 positive (mean 1.23).
OOS (70/30) Sharpe 2.48, +96.4% ann, 8.7% DD.
90% param robustness (130/144 positive). Fee-robust (2.10 at 5x fees).
Correlation: 0.312 H-012, 0.034 H-019.
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
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

# ── Strategy parameters ──────────────────────────────────────────────
ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

CONFIG = {
    "short_window": 7,       # short-term vol window (days)
    "long_window": 30,       # long-term vol window (days)
    "rebal_freq": 7,         # rebalance every 7 days
    "n_long": 5,             # long top 5 (expanding vol)
    "n_short": 5,            # short bottom 5 (contracting vol)
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


# ── Signal generation ────────────────────────────────────────────────
def compute_vol_term_signal(closes: pd.DataFrame) -> dict:
    """
    Rank assets by short-term / long-term vol ratio.
    Expansion-long: long highest ratio (vol expanding), short lowest (vol contracting).
    """
    sw = CONFIG["short_window"]
    lw = CONFIG["long_window"]

    if len(closes) < lw + 5:
        return {}

    daily_rets = closes.pct_change(1)

    # Drop today's incomplete data
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if str(closes.index[-1].date()) == today_utc:
        daily_rets = daily_rets.iloc[:-1]

    if len(daily_rets) < lw + 2:
        return {}

    scores = {}
    for sym in closes.columns:
        short_vol = daily_rets[sym].iloc[-sw:].std()
        long_vol = daily_rets[sym].iloc[-lw:].std()
        if long_vol > 0 and short_vol > 0:
            scores[sym] = short_vol / long_vol  # > 1 = expanding, < 1 = contracting

    n_needed = CONFIG["n_long"] + CONFIG["n_short"]
    if len(scores) < n_needed:
        return {}

    ranked = pd.Series(scores).sort_values(ascending=False)

    # Expansion-long: long top N (expanding), short bottom N (contracting)
    long_assets = ranked.index[:CONFIG["n_long"]]
    short_assets = ranked.index[-CONFIG["n_short"]:]

    weights = {}
    for sym in long_assets:
        weights[sym] = 1.0 / CONFIG["n_long"]
    for sym in short_assets:
        weights[sym] = -1.0 / CONFIG["n_short"]

    return weights


# ── Main runner ──────────────────────────────────────────────────────
def run():
    print("=== H-059 Vol Term Structure Paper Trade Runner ===")
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

    if len(closes) < CONFIG["long_window"] + 10:
        print("Insufficient data for strategy warmup. Skipping.")
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

        new_weights = compute_vol_term_signal(closes)
        if not new_weights:
            print("No valid signal — skipping rebalance.")
        else:
            old_positions = state.get("positions", {})
            latest_prices = closes.iloc[-1].to_dict()

            # Close old positions, open new
            n_trades = 0
            total_fee = 0.0

            # Determine which positions changed
            all_syms = set(list(old_positions.keys()) + list(new_weights.keys()))
            for sym in all_syms:
                old_w = old_positions.get(sym, {}).get("weight", 0) if isinstance(old_positions.get(sym), dict) else 0
                new_w = new_weights.get(sym, 0)
                if old_w != new_w:
                    n_trades += 1
                    notional = abs(new_w) * state["capital"]
                    fee = notional * (CONFIG["fee_rate"] + slippage)
                    total_fee += fee

            state["capital"] -= total_fee
            state["total_fees"] += total_fee
            state["total_trades"] += n_trades

            # Set new positions
            new_pos = {}
            for sym, w in new_weights.items():
                price = latest_prices.get(sym, 0)
                if price > 0:
                    notional = abs(w) * state["capital"]
                    size = notional / price * (1 if w > 0 else -1)
                    new_pos[sym] = {
                        "weight": w,
                        "entry_price": price,
                        "size": size,
                        "direction": "LONG" if w > 0 else "SHORT",
                    }

            state["positions"] = new_pos
            state["last_rebal_date"] = latest_date
            state["rebal_count"] += 1
            state["days_since_rebal"] = 0

            longs = [s.split("/")[0] for s, p in new_pos.items() if p["weight"] > 0]
            shorts = [s.split("/")[0] for s, p in new_pos.items() if p["weight"] < 0]
            print(f"  LONG (vol expanding): {', '.join(longs)}")
            print(f"  SHORT (vol contracting): {', '.join(shorts)}")
            print(f"  Trades: {n_trades}, Fees: ${total_fee:.2f}")

            log.append({
                "time": datetime.now(timezone.utc).isoformat(),
                "event": "rebalance",
                "date": latest_date,
                "longs": longs,
                "shorts": shorts,
                "trades": n_trades,
                "fees": total_fee,
                "capital": state["capital"],
            })

    # ── Mark-to-market ────────────────────────────────────────────
    equity = state["capital"]
    latest_prices = closes.iloc[-1].to_dict()
    for sym, pos in state.get("positions", {}).items():
        price_now = latest_prices.get(sym, pos["entry_price"])
        entry = pos["entry_price"]
        size = pos["size"]
        if size > 0:
            pnl = size * (price_now - entry)
        else:
            pnl = abs(size) * (entry - price_now)
        equity += pnl

    state["equity"] = equity

    # Update equity history
    state["equity_history"].append({
        "date": latest_date,
        "equity": round(equity, 2),
        "positions": len(state.get("positions", {})),
        "rebalanced": days_since >= CONFIG["rebal_freq"],
    })

    state["last_daily_date"] = latest_date
    save_state(state)
    save_log(log)

    _print_status(state, closes)
    return state


def _print_status(state, closes):
    equity = state.get("equity", state["capital"])
    ret = (equity / CONFIG["initial_capital"] - 1) * 100
    print(f"\nEquity: ${equity:,.2f} (start ${CONFIG['initial_capital']:,.0f})")
    print(f"Return: {ret:+.2f}%")
    print(f"Rebalances: {state['rebal_count']}, Trades: {state['total_trades']}")
    print(f"Fees: ${state['total_fees']:.2f}")

    if state.get("positions"):
        latest_prices = closes.iloc[-1].to_dict() if len(closes) > 0 else {}
        print(f"\nPositions ({len(state['positions'])}):")
        for sym, pos in sorted(state["positions"].items()):
            d = pos["direction"]
            price_now = latest_prices.get(sym, pos["entry_price"])
            entry = pos["entry_price"]
            size = pos["size"]
            if size > 0:
                pnl = size * (price_now - entry)
            else:
                pnl = abs(size) * (entry - price_now)
            ticker = sym.split("/")[0]
            print(f"  {d:5s} {ticker:6s} w={pos['weight']:+.2f} entry=${entry:.4f} now=${price_now:.4f} PnL=${pnl:+.2f}")

    days_left = CONFIG["rebal_freq"] - state.get("days_since_rebal", 0)
    print(f"Next rebal in {days_left} day(s)")


if __name__ == "__main__":
    run()
