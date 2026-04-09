"""
H-411 Paper Trade Runner: OBV Slope Factor

Market-neutral strategy: rank 14 crypto assets by slope of On-Balance Volume
(signed volume cumulative sum) over rolling window. HIGH OBV slope → long
(accumulation). Signal uses LAGGED data — no look-ahead.

Backtest (lagged): IS 93.3% (28/30 high_obv_long). Best LB15_R7_N3
Sharpe 1.547, WF 6/6 mean 0.886. Split-half H1=1.968, H2=1.063.
Corr H-012 0.267.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from lib.data_fetch import fetch_and_cache

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

CONFIG = {
    "lookback": 15,
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
    """Rank assets by OBV slope. HIGH slope → long (accumulation)."""
    scores = {}
    for sym, daily in daily_dict.items():
        # Use data up to yesterday (lagged)
        window = daily.iloc[-(CONFIG["lookback"]+1):-1]
        if len(window) < CONFIG["lookback"] * 0.7:
            continue
        rets = window["close"].pct_change()
        vols = window["volume"]
        signed_vol = vols * np.sign(rets)
        obv = signed_vol.cumsum().dropna()
        if len(obv) < 5:
            continue
        x = np.arange(len(obv))
        y = obv.values
        valid = np.isfinite(y)
        if valid.sum() < 5:
            continue
        slope, _, _, _, _ = stats.linregress(x[valid], y[valid])
        mean_vol = vols.mean()
        if mean_vol > 0 and np.isfinite(slope):
            scores[sym] = slope / mean_vol

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


def run():
    print("=== H-411 OBV Slope Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching daily data for 14 assets...")
    daily_dict = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=30)
            if len(df) < 200:
                continue
            from strategies.daily_trend_multi_asset.strategy import resample_to_daily
            daily = resample_to_daily(df)
            daily_dict[sym] = daily
        except Exception as e:
            print(f"  {sym}: {e}")

    print(f"Loaded {len(daily_dict)} assets")

    if len(daily_dict) < 8:
        print("Insufficient assets.")
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
            last_rebal = pd.Timestamp(state["last_rebal_date"])
            current = pd.Timestamp(latest_date)
            days_since = (current - last_rebal).days

        state["days_since_rebal"] = days_since

        if days_since >= CONFIG["rebal_freq"]:
            print(f"Rebalancing (day {days_since})...")
            new_weights = compute_rankings(daily_dict)
            if not new_weights:
                print("  Could not compute rankings.")
            else:
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
                        exit_price = float(current_prices[sym])
                        direction = 1 if pos["weight"] > 0 else -1
                        notional = abs(pos["size"]) * exit_price * (1 - direction * slippage)
                        new_w = new_weights.get(sym, 0)
                        if abs(new_w - pos["weight"]) > 0.01:
                            total_fees += CONFIG["fee_rate"] * notional
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
                    notional = abs(size) * entry_price

                    if sym not in old_positions or abs(new_weights.get(sym, 0) - old_positions.get(sym, {}).get("weight", 0)) > 0.01:
                        total_fees += CONFIG["fee_rate"] * notional
                        trades += 1

                    new_positions[sym] = {
                        "size": size, "entry_price": entry_price,
                        "weight": weight, "symbol": sym,
                    }

                capital -= total_fees
                state["capital"] = capital
                state["positions"] = new_positions
                state["total_fees"] += total_fees
                state["total_trades"] += trades
                state["rebal_count"] += 1
                state["last_rebal_date"] = latest_date

                log.append({
                    "time": datetime.now(timezone.utc).isoformat(),
                    "action": "rebalance", "date": latest_date,
                    "longs": [s for s, p in new_positions.items() if p["weight"] > 0],
                    "shorts": [s for s, p in new_positions.items() if p["weight"] < 0],
                    "capital": round(capital, 2), "fees": round(total_fees, 4),
                    "trades": trades,
                })
                save_log(log)
                print(f"  LONG:  {log[-1]['longs']}")
                print(f"  SHORT: {log[-1]['shorts']}")
        else:
            print(f"Hold (day {days_since}/{CONFIG['rebal_freq']})")

        state["last_daily_date"] = latest_date

    # Compute equity
    equity = state["capital"]
    if state["positions"]:
        current_prices = closes.iloc[-1]
        for sym, pos in state["positions"].items():
            if sym in current_prices.index:
                equity += pos["size"] * (float(current_prices[sym]) - pos["entry_price"])

    state["equity"] = equity
    state["equity_history"].append({
        "date": latest_date, "equity": round(equity, 2),
    })

    save_state(state)
    pnl_pct = (equity / CONFIG["initial_capital"] - 1) * 100
    print(f"\n  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    print(f"  Rebals: {state['rebal_count']}, Positions: {len(state['positions'])}")
    for sym, pos in sorted(state["positions"].items()):
        price_now = float(closes.iloc[-1].get(sym, pos["entry_price"]))
        pnl = pos["size"] * (price_now - pos["entry_price"])
        side = "LONG " if pos["weight"] > 0 else "SHORT"
        print(f"    {side} {sym:15s} pnl=${pnl:.2f}")

    return state


if __name__ == "__main__":
    run()
