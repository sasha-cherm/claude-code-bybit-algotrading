"""
H-351 Paper Trade Runner: Volume Profile Skewness Factor

Market-neutral strategy: rank 14 crypto assets by skewness of hourly volume
distribution within each day. Low skew = front-loaded volume (early conviction,
institutions setting direction). High skew = back-loaded (late retail chase).
Long low-skew assets, short high-skew.

Backtest: IS 100% low_long (30/30). Best LB30_R5_N3 Sharpe 1.438
(WF 5/6 mean 1.339). Split-half H1=1.109, H2=0.588.
Corr H-012 0.179, H-076 -0.063. Low correlation with all existing strategies.
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


def load_data():
    """Load hourly + daily data for all assets."""
    closes_dict = {}
    features_dict = {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=120)
            df_1d = fetch_and_cache(sym, "1d", limit_days=120)
            if len(df_1d) < 50 or len(df_1h) < 200:
                continue
            dc = df_1d["close"].copy()
            if dc.index.tzinfo is not None:
                dc.index = dc.index.tz_localize(None)
            closes_dict[sym] = dc

            # Compute daily volume skewness from hourly bars
            df_1h["date"] = df_1h.index.date
            daily_skew = {}
            for date, hg in df_1h.groupby("date"):
                if len(hg) < 18:
                    continue
                vol = hg["volume"].values
                if len(vol) >= 10 and np.std(vol) > 0:
                    daily_skew[pd.Timestamp(date)] = float(stats.skew(vol))
                else:
                    daily_skew[pd.Timestamp(date)] = 0.0
            features_dict[sym] = pd.Series(daily_skew, name="vol_skew")
        except Exception as e:
            print(f"  {sym}: failed: {e}")

    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    return closes, features_dict


def compute_rankings(closes, features_dict, date_idx) -> dict:
    lookback = CONFIG["lookback"]
    if date_idx < lookback + 5:
        return {}

    current_date = closes.index[date_idx]
    scores = {}
    for sym in closes.columns:
        if sym not in features_dict:
            continue
        feat = features_dict[sym]
        mask = feat.index <= current_date
        vals = feat[mask]
        if len(vals) < lookback:
            continue
        avg = vals.iloc[-lookback:].mean()
        if np.isfinite(avg):
            scores[sym] = avg

    valid = pd.Series(scores)
    n_long = CONFIG["n_long"]
    n_short = CONFIG["n_short"]
    if len(valid) < n_long + n_short:
        return {}

    # Low skew -> long (front-loaded volume / institutional)
    ranked = valid.sort_values(ascending=True)
    longs = ranked.index[:n_long]
    shorts = ranked.index[-n_short:]

    weights = {}
    for sym in longs:
        weights[sym] = 1.0 / n_long
    for sym in shorts:
        weights[sym] = -1.0 / n_short
    return weights


def run():
    print(f"=== H-351 Volume Profile Skewness Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching daily data for 14 assets...")
    closes, features_dict = load_data()

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    if len(closes.columns) < 7:
        print(f"WARNING: Only {len(closes.columns)} of 14 assets loaded, skipping")
        save_state(state)
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
    date_idx = len(closes) - 1

    if days_since >= CONFIG["rebal_freq"]:
        print(f"Rebalancing (day {days_since} since last rebal)...")

        new_weights = compute_rankings(closes, features_dict, date_idx)
        if not new_weights:
            print("  Could not compute rankings. Skipping rebalance.")
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
                entry_price = price * (1 + (1 if weight > 0 else -1) * slippage)
                notional = abs(weight) * capital
                size = (notional / entry_price) * (1 if weight > 0 else -1)
                fee = CONFIG["fee_rate"] * notional
                total_fees += fee
                trades_this_rebal += 1
                new_positions[sym] = {
                    "weight": weight,
                    "size": size,
                    "entry_price": entry_price,
                    "entry_date": latest_date,
                }

            capital -= total_fees

            log.append({
                "time": datetime.now(timezone.utc).isoformat(),
                "action": "rebalance",
                "date": latest_date,
                "positions": {k: {"weight": v["weight"], "entry_price": v["entry_price"]}
                              for k, v in new_positions.items()},
                "capital": round(capital, 2),
                "fees": round(total_fees, 4),
                "trades": trades_this_rebal,
            })

            state["capital"] = capital
            state["positions"] = new_positions
            state["last_rebal_date"] = latest_date
            state["days_since_rebal"] = 0
            state["rebal_count"] = state.get("rebal_count", 0) + 1
            state["total_trades"] = state.get("total_trades", 0) + trades_this_rebal
            state["total_fees"] = state.get("total_fees", 0) + total_fees

            print(f"  New positions ({len(new_positions)}):")
            for sym in sorted(new_positions):
                pos = new_positions[sym]
                side = "LONG" if pos["weight"] > 0 else "SHORT"
                print(f"    {side:5s} {sym:15s}")
            print(f"  Fees: ${total_fees:.4f}")

    # MTM
    equity = state["capital"]
    current_prices = closes.iloc[-1]
    for sym, pos in state["positions"].items():
        if sym in current_prices.index:
            price_now = float(current_prices[sym])
            unrealized = pos["size"] * (price_now - pos["entry_price"])
            equity += unrealized

    state["equity"] = round(equity, 2)
    state["last_daily_date"] = latest_date

    state["equity_history"].append({
        "time": datetime.now(timezone.utc).isoformat(),
        "equity": round(equity, 2),
        "date": latest_date,
    })

    save_state(state)
    save_log(log)
    _print_status(state, closes)
    return state


def _print_status(state, closes):
    equity = state.get("equity", state["capital"])
    init = CONFIG["initial_capital"]
    pnl_pct = (equity - init) / init * 100
    print(f"\n  Capital: ${state['capital']:,.2f}")
    print(f"  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    print(f"  Rebals:  {state.get('rebal_count', 0)}")
    n_pos = len(state.get("positions", {}))
    print(f"  Positions: {n_pos}")
    if state.get("positions"):
        current_prices = closes.iloc[-1] if len(closes) > 0 else pd.Series()
        for sym in sorted(state["positions"]):
            pos = state["positions"][sym]
            side = "LONG" if pos["weight"] > 0 else "SHORT"
            pnl = 0
            if sym in current_prices.index:
                price_now = float(current_prices[sym])
                pnl = pos["size"] * (price_now - pos["entry_price"])
            print(f"    {side:5s} {sym:15s} pnl=${pnl:+.2f}")


if __name__ == "__main__":
    run()
