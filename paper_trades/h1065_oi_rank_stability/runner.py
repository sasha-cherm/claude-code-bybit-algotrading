"""
H-1065 OI Rank Stability XS Paper Trade Runner

Assets whose OI ranking dropped (short-term vs long-term) → long (less crowded).
Backtest: IS Sharpe 1.753, WF 5/5, SH p=0.016, H-012 corr -0.037.
Best params: LB=30, R=7, N=4, dir=low_long.
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
    "rebal_freq": 7,
    "n_long": 4,
    "n_short": 4,
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,
    "slippage_bps": 2.0,
    "short_oi_window": 7,
    "long_oi_window": 30,
}

STATE_FILE = Path(__file__).parent / "state.json"
LOG_FILE = Path(__file__).parent / "log.json"


def load_state():
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


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def load_log():
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            return json.load(f)
    return []


def save_log(log):
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, default=str)


def compute_rankings(daily_dict, oi_dict):
    closes = pd.DataFrame({s: d["close"] for s, d in daily_dict.items()}).dropna(how="all").ffill().dropna()
    if len(closes) < CONFIG["lookback"] + 5:
        return {}
    oi_df = pd.DataFrame(oi_dict).dropna(how="all").ffill().dropna()
    if len(oi_df) < CONFIG["long_oi_window"] + 5:
        return {}
    short_rank = oi_df.rolling(CONFIG["short_oi_window"]).mean().rank(axis=1, pct=True)
    long_rank = oi_df.rolling(CONFIG["long_oi_window"]).mean().rank(axis=1, pct=True)
    rank_diff = short_rank - long_rank
    if len(rank_diff) < 2:
        return {}
    sig_row = rank_diff.iloc[-1].dropna()
    if len(sig_row) < CONFIG["n_long"] + CONFIG["n_short"]:
        return {}
    ranked = sig_row.sort_values(ascending=True)  # low_long
    weights = {}
    for sym in ranked.index[:CONFIG["n_long"]]:
        weights[sym] = 1.0 / CONFIG["n_long"]
    for sym in ranked.index[-CONFIG["n_short"]:]:
        weights[sym] = -1.0 / CONFIG["n_short"]
    return weights


def run():
    print("=== H-1065 OI Rank Stability XS Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    state = load_state()
    log = load_log()
    daily_dict = {}
    oi_dict = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=90)
            if len(df) < 200:
                continue
            from strategies.daily_trend_multi_asset.strategy import resample_to_daily
            daily = resample_to_daily(df)
            daily_dict[sym] = daily
        except Exception as e:
            print(f"  {sym}: {e}")
    for sym in ASSETS:
        try:
            ticker = sym.split("/")[0]
            oi_file = ROOT / "data" / f"{ticker}_USDT_oi_daily.parquet"
            if oi_file.exists():
                oi_df = pd.read_parquet(oi_file)
                if oi_df.index.tz is not None:
                    oi_df.index = oi_df.index.tz_localize(None)
                oi_dict[sym] = oi_df["openInterest"]
        except Exception as e:
            print(f"  OI {sym}: {e}")
    print(f"Loaded {len(daily_dict)} assets, {len(oi_dict)} OI series")
    if len(daily_dict) < 8 or len(oi_dict) < 8:
        save_state(state)
        return state
    closes = pd.DataFrame({s: d["close"] for s, d in daily_dict.items()}).dropna(how="all").ffill().dropna()
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]
    latest_date = str(closes.index[-1].date())
    slippage = CONFIG["slippage_bps"] / 10_000
    if latest_date == state.get("last_daily_date"):
        print(f"No new daily bar since {latest_date}.")
    else:
        print(f"New daily bar: {latest_date}")
        if state["last_rebal_date"] is None:
            days_since = CONFIG["rebal_freq"]
        else:
            days_since = (pd.Timestamp(latest_date) - pd.Timestamp(state["last_rebal_date"])).days
        state["days_since_rebal"] = days_since
        if days_since >= CONFIG["rebal_freq"]:
            new_weights = compute_rankings(daily_dict, oi_dict)
            if new_weights:
                current_prices = closes.iloc[-1]
                old_positions = state["positions"]
                total_fees = 0.0
                trades = 0
                capital = state["capital"]
                for sym, pos in old_positions.items():
                    if sym in current_prices.index:
                        capital += pos["size"] * (float(current_prices[sym]) - pos["entry_price"])
                for sym, pos in old_positions.items():
                    if sym in current_prices.index:
                        new_w = new_weights.get(sym, 0)
                        if abs(new_w - pos["weight"]) > 0.01:
                            total_fees += CONFIG["fee_rate"] * abs(pos["size"]) * float(current_prices[sym])
                            trades += 1
                new_positions = {}
                for sym, weight in new_weights.items():
                    if sym not in current_prices.index:
                        continue
                    price = float(current_prices[sym])
                    direction = 1 if weight > 0 else -1
                    entry_price = price * (1 + direction * slippage)
                    alloc = capital * abs(weight)
                    size = alloc / entry_price * direction
                    if sym not in old_positions or abs(new_weights.get(sym, 0) - old_positions.get(sym, {}).get("weight", 0)) > 0.01:
                        total_fees += CONFIG["fee_rate"] * abs(size) * entry_price
                        trades += 1
                    new_positions[sym] = {"size": size, "entry_price": entry_price, "weight": weight, "symbol": sym}
                capital -= total_fees
                state["capital"] = capital
                state["positions"] = new_positions
                state["total_fees"] += total_fees
                state["total_trades"] += trades
                state["rebal_count"] += 1
                state["last_rebal_date"] = latest_date
                log.append({"time": datetime.now(timezone.utc).isoformat(), "action": "rebalance", "date": latest_date,
                            "longs": [s for s, p in new_positions.items() if p["weight"] > 0],
                            "shorts": [s for s, p in new_positions.items() if p["weight"] < 0],
                            "capital": round(capital, 2), "fees": round(total_fees, 4), "trades": trades})
                save_log(log)
                print(f"  LONG:  {log[-1]['longs']}")
                print(f"  SHORT: {log[-1]['shorts']}")
        else:
            print(f"Hold (day {days_since}/{CONFIG['rebal_freq']})")
        state["last_daily_date"] = latest_date
    equity = state["capital"]
    if state["positions"]:
        current_prices = closes.iloc[-1]
        for sym, pos in state["positions"].items():
            if sym in current_prices.index:
                equity += pos["size"] * (float(current_prices[sym]) - pos["entry_price"])
    state["equity"] = equity
    state["equity_history"].append({"date": latest_date, "equity": round(equity, 2)})
    save_state(state)
    pnl_pct = (equity / CONFIG["initial_capital"] - 1) * 100
    print(f"\n  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    return state


if __name__ == "__main__":
    run()
