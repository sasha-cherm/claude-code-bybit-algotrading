"""
H-994 Relative Volume Profile (Volume Rank Change) XS Paper Trade Runner

Volume rank change over time. Long assets whose volume rank is improving
(gaining relative attention), short assets whose volume rank is declining.
Backtest: IS Sharpe 1.618, WF 3/5, SH p=0.025, H-012 corr -0.017.
Best params: P=10, C=10, R=3, N=4.
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
    "vol_period": 10,
    "change_period": 10,
    "rebal_freq": 3,
    "n_long": 4,
    "n_short": 4,
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,
    "slippage_bps": 2.0,
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


def compute_rankings(daily_dict):
    volumes = pd.DataFrame({s: d["volume"] * d["close"] for s, d in daily_dict.items()}).dropna(how="all").ffill().dropna()
    p = CONFIG["vol_period"]
    cp = CONFIG["change_period"]
    if len(volumes) < p + cp + 5:
        return {}
    avg_vol = volumes.rolling(p).mean()
    curr_vals = avg_vol.iloc[-1].dropna()
    past_vals = avg_vol.iloc[-1 - cp].dropna()
    if len(curr_vals) < 8 or len(past_vals) < 8:
        return {}
    curr_rank = curr_vals.rank()
    past_rank = past_vals.rank()
    common = curr_rank.index.intersection(past_rank.index)
    signal = pd.Series(np.nan, index=common)
    for col in common:
        signal[col] = curr_rank[col] - past_rank[col]
    sig_row = signal.dropna()
    if len(sig_row) < CONFIG["n_long"] + CONFIG["n_short"]:
        return {}
    ranked = sig_row.sort_values(ascending=False)
    weights = {}
    for sym in ranked.index[:CONFIG["n_long"]]:
        weights[sym] = 1.0 / CONFIG["n_long"]
    for sym in ranked.index[-CONFIG["n_short"]:]:
        weights[sym] = -1.0 / CONFIG["n_short"]
    return weights


def run():
    print("=== H-994 Relative Volume Profile XS Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    state = load_state()
    log = load_log()
    daily_dict = {}
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
    print(f"Loaded {len(daily_dict)} assets")
    if len(daily_dict) < 8:
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
            new_weights = compute_rankings(daily_dict)
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
