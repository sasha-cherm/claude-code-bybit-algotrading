"""
H-388 Paper Trade Runner: Night-Day Return Differential Factor

Market-neutral strategy: rank 14 crypto assets by rolling average of
(Asian session return - US session return). High differential (assets
outperforming during Asian vs US hours) → long.

Backtest: IS 96.7% (29/30 high_long). Best LB30_R5_N3 Sharpe 0.688
(+32.2% ann, -81.7% DD). WF 4/6 mean 0.358. Split-half H1=0.916 PASS, H2=-0.271.
Corr H-012 0.040 — near-zero, genuinely novel signal.
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
    "lookback": 30,   # 30-day rolling window
    "rebal_freq": 5,  # rebalance every 5 days
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


def compute_daily_night_day_diff(df_1h_sym, lookback_days=30):
    """Compute rolling night-day return differential for one asset."""
    df = df_1h_sym.copy()
    if df.index.tz:
        df.index = df.index.tz_localize(None)
    df["hour_return"] = df["close"] / df["open"] - 1
    df["date"] = df.index.normalize()
    df["hour"] = df.index.hour

    daily_nd = {}
    for date_ts, hg in df.groupby("date"):
        if len(hg) < 18:
            continue
        ret = hg["hour_return"].values
        hours = hg["hour"].values
        # Asian: 0-8 UTC, US: 13-21 UTC
        asian_mask = (hours >= 0) & (hours < 8)
        us_mask = (hours >= 13) & (hours < 21)
        asian_ret = float(np.sum(ret[asian_mask])) if asian_mask.any() else 0.0
        us_ret = float(np.sum(ret[us_mask])) if us_mask.any() else 0.0
        daily_nd[date_ts] = asian_ret - us_ret

    if not daily_nd:
        return None

    nd_series = pd.Series(daily_nd).sort_index()
    return nd_series.rolling(lookback_days, min_periods=max(lookback_days // 2, 5)).mean()


def compute_rankings(hourly_dict):
    """Rank assets by night-day differential. High → long."""
    scores = {}
    for sym, df_1h in hourly_dict.items():
        nd = compute_daily_night_day_diff(df_1h, CONFIG["lookback"])
        if nd is None or len(nd.dropna()) < 5:
            continue
        last_val = nd.dropna().iloc[-1]
        if np.isfinite(last_val):
            scores[sym] = last_val

    if len(scores) < CONFIG["n_long"] + CONFIG["n_short"]:
        return {}

    valid = pd.Series(scores).sort_values(ascending=False)
    longs = valid.index[:CONFIG["n_long"]]
    shorts = valid.index[-CONFIG["n_short"]:]

    weights = {}
    for sym in longs:
        weights[sym] = 1.0 / CONFIG["n_long"]
    for sym in shorts:
        weights[sym] = -1.0 / CONFIG["n_short"]
    return weights


def _get_daily_close(hourly_dict):
    from strategies.daily_trend_multi_asset.strategy import resample_to_daily
    closes_dict = {}
    for sym, df in hourly_dict.items():
        daily = resample_to_daily(df)
        idx = daily.index.tz_localize(None) if daily.index.tz else daily.index
        closes_dict[sym] = pd.Series(daily["close"].values, index=idx)
    return pd.DataFrame(closes_dict)


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
    print("=== H-388 Night-Day Differential Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching hourly data for 14 assets...")
    hourly_dict = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=60)
            if len(df) >= 200:
                hourly_dict[sym] = df
        except Exception as e:
            print(f"  {sym}: {e}")

    print(f"Loaded {len(hourly_dict)} assets")

    if len(hourly_dict) < 8:
        print("Insufficient assets. Skipping.")
        save_state(state)
        return state

    closes = _get_daily_close(hourly_dict)
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]

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

    if days_since >= CONFIG["rebal_freq"]:
        print(f"Rebalancing (day {days_since} since last rebal)...")
        new_weights = compute_rankings(hourly_dict)
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
                    "size": size, "entry_price": entry_price,
                    "weight": weight, "entry_date": latest_date,
                }

            capital -= total_fees
            state["capital"] = capital
            state["positions"] = new_positions
            state["last_rebal_date"] = latest_date
            state["rebal_count"] += 1
            state["total_trades"] += trades_this_rebal
            state["total_fees"] += total_fees

            log.append({
                "time": datetime.now(timezone.utc).isoformat(),
                "event": "rebalance", "date": latest_date,
                "positions": {s: {"w": p["weight"], "size": p["size"]} for s, p in new_positions.items()},
                "capital": capital, "fees": total_fees, "trades": trades_this_rebal,
            })

            print(f"  New positions: {len(new_positions)}")
            for sym, pos in sorted(new_positions.items()):
                side = "LONG " if pos["weight"] > 0 else "SHORT"
                print(f"    {side} {sym}")
            print(f"  Fees: ${total_fees:.2f} ({trades_this_rebal} trades)")
    else:
        print(f"Not rebalancing (day {days_since}/{CONFIG['rebal_freq']})")

    state["last_daily_date"] = latest_date

    equity = state["capital"]
    current_prices = closes.iloc[-1]
    for sym, pos in state["positions"].items():
        if sym in current_prices.index:
            price_now = float(current_prices[sym])
            equity += pos["size"] * (price_now - pos["entry_price"])

    state["equity"] = equity
    state["equity_history"].append({
        "time": datetime.now(timezone.utc).isoformat(),
        "equity": equity, "date": latest_date,
    })

    save_state(state)
    save_log(log)
    _print_status(state, closes)
    return state


if __name__ == "__main__":
    run()
