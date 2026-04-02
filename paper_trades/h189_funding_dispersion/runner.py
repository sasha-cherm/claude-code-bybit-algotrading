"""
H-189 Paper Trade Runner: Funding Rate Dispersion Factor (14 Crypto Assets)

Market-neutral strategy: rank 14 assets by rolling std dev of funding rates.
Low dispersion = stable consensus positioning. High dispersion = volatile/uncertain.
Long bottom 3 (lowest dispersion — stable consensus), short top 3 (most volatile).
Rebalance every 7 days.

Backtest: IS 91.7% positive (22/24), mean Sharpe 0.583, best LB20_R7_N3 Sharpe 1.489
(+63.9% ann, -34.1% DD). WF 4/6 positive, mean OOS 1.014.
Split-half H1=2.124, H2=1.568. Corr H-012 -0.033 (essentially zero).
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

from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

# ── Strategy parameters ──────────────────────────────────────────────
ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

CONFIG = {
    "funding_lookback": 20,  # 20-day window (= 60 funding settlements)
    "rebal_freq": 7,         # rebalance every 7 days
    "n_long": 3,             # long bottom 3 (lowest dispersion)
    "n_short": 3,            # short top 3 (highest dispersion)
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


def load_funding_data() -> pd.DataFrame:
    """Load 8h funding rate data for all assets, keep at settlement level (3 per day)."""
    data_dir = ROOT / "data"
    funding_all = {}

    for sym in ASSETS:
        asset_name = sym.split("/")[0]
        fpath = data_dir / f"{asset_name}_USDT_USDT_funding.parquet"
        if not fpath.exists():
            print(f"  {sym}: no funding data file, skipping")
            continue
        try:
            df = pd.read_parquet(fpath)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            funding_all[sym] = df["funding_rate"]
        except Exception as e:
            print(f"  {sym}: funding load failed: {e}")
        time.sleep(0.02)

    funding = pd.DataFrame(funding_all)
    funding = funding.dropna(how="all").ffill().dropna()
    return funding


# ── Signal generation ────────────────────────────────────────────────
def compute_dispersion_signal(funding: pd.DataFrame) -> dict:
    """
    Rank assets by rolling std dev of funding rates.
    Low dispersion = stable consensus → long (information in stability).
    High dispersion = noisy/whipsawing → short.
    """
    lookback_days = CONFIG["funding_lookback"]
    # 3 funding settlements per day
    lookback_periods = lookback_days * 3

    if len(funding) < lookback_periods:
        return {}

    # Drop today's incomplete data
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if str(funding.index[-1].date()) == today_utc:
        funding = funding[funding.index.date < pd.Timestamp(today_utc).date()]

    if len(funding) < lookback_periods:
        return {}

    # Rolling std dev of funding rates over lookback period
    recent = funding.iloc[-lookback_periods:]
    dispersion = recent.std()
    valid = dispersion.dropna()

    n_needed = CONFIG["n_long"] + CONFIG["n_short"]
    if len(valid) < n_needed:
        return {}

    ranked = valid.rank(ascending=True)

    # Long lowest dispersion (bottom N), short highest (top N)
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
    print("=== H-189 Funding Rate Dispersion Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching price data for 14 assets...")
    closes = load_daily_closes()

    # Drop today's incomplete bar
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    if len(closes.columns) < 7:
        print(f"WARNING: Only {len(closes.columns)} of 14 assets loaded, skipping rebalance")
        save_state(state)
        return state

    print("Loading funding rate data...")
    funding = load_funding_data()
    print(f"Funding data: {len(funding)} rows, {len(funding.columns)} assets")

    lookback_periods = CONFIG["funding_lookback"] * 3
    if len(funding) < lookback_periods + 2:
        print("Insufficient funding data for strategy warmup. Skipping.")
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

    # ── Rebalance check ───────────────────────────────────────────
    if days_since >= CONFIG["rebal_freq"]:
        print(f"Rebalancing (day {days_since} since last rebal)...")

        new_weights = compute_dispersion_signal(funding)
        if not new_weights:
            print("  Could not compute dispersion signal. Skipping rebalance.")
        else:
            current_prices = closes.iloc[-1]
            old_positions = state["positions"]

            capital = state["capital"]
            for sym, pos in old_positions.items():
                if sym in current_prices.index:
                    price_now = float(current_prices[sym])
                    unrealized = pos["size"] * (price_now - pos["entry_price"])
                    capital += unrealized

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

            n_needed = CONFIG["n_long"] + CONFIG["n_short"]
            if len(new_positions) < n_needed:
                print(f"  WARNING: Only {len(new_positions)}/{n_needed} positions created, aborting rebalance")
            else:
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
