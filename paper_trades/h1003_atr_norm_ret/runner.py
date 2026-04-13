"""
H-1003 ATR-Normalized Return XS Paper Trade Runner

Return / ATR — signal strength per unit of recent volatility.
High = strong move for the vol environment. Long efficient movers, short noisy ones.
Backtest: IS Sharpe 1.406, WF 3/5, SH p=0.051, H-012 corr 0.012.
Best params: R=20, A=14, Rebal=7, N=3.
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
    "return_period": 20,
    "atr_period": 14,
    "rebal_freq": 7,
    "n_long": 3,
    "n_short": 3,
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
    closes = pd.DataFrame({s: d["close"] for s, d in daily_dict.items()}).dropna(how="all").ffill().dropna()
    highs = pd.DataFrame({s: d["high"] for s, d in daily_dict.items()}).dropna(how="all").ffill().dropna()
    lows = pd.DataFrame({s: d["low"] for s, d in daily_dict.items()}).dropna(how="all").ffill().dropna()
    rp = CONFIG["return_period"]
    ap = CONFIG["atr_period"]
    lb = max(rp, ap)
    if len(closes) < lb + 5:
        return {}
    # Compute ATR
    needed = max(rp, ap) + 5
    signal = pd.Series(np.nan, index=closes.columns)
    for col in closes.columns:
        if col not in highs.columns or col not in lows.columns:
            continue
        if len(closes[col].dropna()) < needed:
            continue
        h = highs[col].dropna().iloc[-needed:].values
        l = lows[col].dropna().iloc[-needed:].values
        c = closes[col].dropna().iloc[-needed:].values
        if len(c) < needed:
            continue
        # True range
        tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
        if len(tr) < ap:
            continue
        atr = np.mean(tr[-ap:])
        atr_pct = atr / c[-1] if c[-1] > 0 else np.nan
        if atr_pct is None or atr_pct == 0 or not np.isfinite(atr_pct):
            continue
        if len(c) <= rp:
            continue
        ret = (c[-1] / c[-1-rp] - 1) if c[-1-rp] > 0 else np.nan
        if not np.isfinite(ret):
            continue
        signal[col] = ret / atr_pct
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
    print("=== H-1003 ATR-Normalized Return XS Paper Trade Runner ===")
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
