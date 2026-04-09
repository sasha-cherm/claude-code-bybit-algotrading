"""
H-445 Paper Trade Runner: Max Hourly Drawdown Factor

Market-neutral strategy: rank 14 crypto assets by rolling average of
max intraday drawdown (computed from previous day's hourly bars).
LOW max DD → long (resilient assets). HIGH max DD → short.

Backtest: IS 95.8% (low_long). Best LB30_R5_N3.
Sharpe 1.343, +104.8% ann, -60.4% DD.
WF 5/6 mean 1.500. Split-half H1=0.900, H2=1.626.
Corr H-012 -0.200 — NEGATIVE, excellent diversifier.
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


def compute_max_hourly_dd_daily(df_1h_sym):
    """Compute daily max intraday drawdown from hourly returns."""
    df = df_1h_sym.copy()
    if df.index.tz:
        df.index = df.index.tz_localize(None)
    df["date"] = df.index.normalize()
    h_rets = df["close"].pct_change()

    daily_dd = {}
    for date_ts, group in h_rets.groupby(df["date"]):
        vals = group.dropna().values
        if len(vals) >= 8:
            cum = np.cumprod(1 + vals)
            running_max = np.maximum.accumulate(cum)
            dd = (1 - cum / running_max).max()
            if np.isfinite(dd):
                daily_dd[date_ts] = dd
    return pd.Series(daily_dd).sort_index() if daily_dd else None


def compute_rankings(hourly_dict):
    """Rank assets by rolling avg max hourly DD. LOW → long (resilient)."""
    scores = {}
    for sym, df_1h in hourly_dict.items():
        dd_series = compute_max_hourly_dd_daily(df_1h)
        if dd_series is None or len(dd_series) < CONFIG["lookback"]:
            continue
        rolling_mean = dd_series.rolling(CONFIG["lookback"],
                                         min_periods=CONFIG["lookback"] // 2).mean()
        vals = rolling_mean.dropna()
        if len(vals) >= 2:
            last_val = vals.iloc[-2]  # LAGGED
        else:
            continue
        if np.isfinite(last_val):
            scores[sym] = last_val

    if len(scores) < CONFIG["n_long"] + CONFIG["n_short"]:
        return {}

    valid = pd.Series(scores).sort_values(ascending=True)  # LOW first = longs
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
    print(f"\n  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    print(f"  Rebals: {state['rebal_count']}, Positions: {len(state['positions'])}")
    for sym, pos in sorted(state["positions"].items()):
        price_now = float(closes.iloc[-1].get(sym, pos["entry_price"]))
        pnl = pos["size"] * (price_now - pos["entry_price"])
        side = "LONG " if pos["weight"] > 0 else "SHORT"
        print(f"    {side} {sym:15s} pnl=${pnl:.2f}")


def run():
    print("=== H-445 Max Hourly DD Paper Trade Runner ===")
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
            capital = state["capital"]
            for sym, pos in state["positions"].items():
                if sym in current_prices.index:
                    price_now = float(current_prices[sym])
                    unrealized = pos["size"] * (price_now - pos["entry_price"])
                    capital += unrealized

            new_positions = {}
            total_fees = 0.0
            trades_this_rebal = 0
            for sym, weight in new_weights.items():
                if sym not in current_prices.index:
                    continue
                price = float(current_prices[sym])
                direction = 1 if weight > 0 else -1
                entry_price = price * (1 + direction * slippage)
                alloc = capital * abs(weight)
                size = alloc / entry_price * direction
                notional = abs(size) * entry_price
                fee = CONFIG["fee_rate"] * notional
                new_positions[sym] = {
                    "symbol": sym, "size": size, "entry_price": entry_price,
                    "weight": weight, "entry_date": latest_date,
                }
                total_fees += fee
                trades_this_rebal += 1

            state["capital"] = capital - total_fees
            state["positions"] = new_positions
            state["last_rebal_date"] = latest_date
            state["rebal_count"] += 1
            state["total_trades"] += trades_this_rebal
            state["total_fees"] += total_fees

            log.append({
                "time": datetime.now(timezone.utc).isoformat(),
                "action": "rebalance", "date": latest_date,
                "n_positions": len(new_positions), "capital": capital,
                "fees": total_fees, "trades": trades_this_rebal,
            })
            save_log(log)

            longs = [s for s, p in new_positions.items() if p["weight"] > 0]
            shorts = [s for s, p in new_positions.items() if p["weight"] < 0]
            print(f"  {trades_this_rebal} trades, fees ${total_fees:.2f}")
            print(f"  LONG: {', '.join(longs)}")
            print(f"  SHORT: {', '.join(shorts)}")
    else:
        print(f"Hold (day {days_since}/{CONFIG['rebal_freq']} until rebal)")

    state["last_daily_date"] = latest_date
    _print_status(state, closes)
    return state


if __name__ == "__main__":
    run()
