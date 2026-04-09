"""
H-404 Paper Trade Runner: Session Flow Imbalance Factor

Market-neutral strategy: rank 14 crypto assets by rolling average of
(Asian session return - US session return). LOW imbalance (US outperforms
Asia) → long. This captures geographic flow divergence.

Backtest (look-ahead-free): IS 80.0% (24/30 low_session_imbalance_long).
Best LB20_R3_N4 Sharpe 0.748 (+36.3% ann, -36.0% DD).
WF 5/6 mean 0.658. Split-half H1=0.296, H2=1.313.
Corr H-012 0.008 — near-zero, excellent diversifier.
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
    "lookback": 20,   # 20-day rolling window
    "rebal_freq": 3,  # rebalance every 3 days
    "n_long": 4,
    "n_short": 4,
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


def compute_daily_session_imbalance(df_1h_sym, lookback_days=20):
    """Compute rolling session flow imbalance for one asset.

    session_imbalance = asian_return - us_return per day, then rolling mean.
    Uses LAGGED data only (yesterday's features to predict today).
    """
    df = df_1h_sym.copy()
    if df.index.tz:
        df.index = df.index.tz_localize(None)
    df["date"] = df.index.normalize()
    df["hour"] = df.index.hour

    daily_imb = {}
    for date_ts, hg in df.groupby("date"):
        if len(hg) < 18:
            continue
        # Asian session: 0-8 UTC
        asia = hg[hg["hour"] < 8]
        # US session: 16-24 UTC
        us = hg[hg["hour"] >= 16]

        asia_ret = (float(asia["close"].iloc[-1]) / float(asia["open"].iloc[0]) - 1) if len(asia) >= 2 else 0.0
        us_ret = (float(us["close"].iloc[-1]) / float(us["open"].iloc[0]) - 1) if len(us) >= 2 else 0.0
        daily_imb[date_ts] = asia_ret - us_ret

    if not daily_imb:
        return None

    imb_series = pd.Series(daily_imb).sort_index()
    return imb_series.rolling(lookback_days, min_periods=max(lookback_days // 2, 5)).mean()


def compute_rankings(hourly_dict):
    """Rank assets by session imbalance. LOW → long (US outperforms Asia)."""
    scores = {}
    for sym, df_1h in hourly_dict.items():
        imb = compute_daily_session_imbalance(df_1h, CONFIG["lookback"])
        if imb is None or len(imb.dropna()) < 5:
            continue
        # Use SECOND-TO-LAST value (yesterday) to avoid look-ahead
        vals = imb.dropna()
        if len(vals) >= 2:
            last_val = vals.iloc[-2]  # Use yesterday's value
        else:
            continue
        if np.isfinite(last_val):
            scores[sym] = last_val

    if len(scores) < CONFIG["n_long"] + CONFIG["n_short"]:
        return {}

    # LOW imbalance → long (ascending sort: lowest first = longs)
    valid = pd.Series(scores).sort_values(ascending=True)
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
    print("=== H-404 Session Flow Imbalance Paper Trade Runner ===")
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
                alloc = capital * abs(weight)
                size = alloc / entry_price * direction
                notional = abs(size) * entry_price
                fee = CONFIG["fee_rate"] * notional

                if sym not in old_positions or abs(new_weights.get(sym, 0) - old_positions.get(sym, {}).get("weight", 0)) > 0.01:
                    total_fees += fee
                    trades_this_rebal += 1

                new_positions[sym] = {
                    "size": size,
                    "entry_price": entry_price,
                    "weight": weight,
                    "symbol": sym,
                }

            capital -= total_fees
            state["capital"] = capital
            state["positions"] = new_positions
            state["total_fees"] += total_fees
            state["total_trades"] += trades_this_rebal
            state["rebal_count"] += 1
            state["last_rebal_date"] = latest_date

            log_entry = {
                "time": datetime.now(timezone.utc).isoformat(),
                "action": "rebalance",
                "date": latest_date,
                "longs": [s for s, p in new_positions.items() if p["weight"] > 0],
                "shorts": [s for s, p in new_positions.items() if p["weight"] < 0],
                "capital": round(capital, 2),
                "fees": round(total_fees, 4),
                "trades": trades_this_rebal,
            }
            log.append(log_entry)
            save_log(log)

            print(f"  New positions: {len(new_positions)}")
            print(f"    LONG:  {log_entry['longs']}")
            print(f"    SHORT: {log_entry['shorts']}")
            print(f"    Fees: ${total_fees:.4f}, Trades: {trades_this_rebal}")
    else:
        print(f"Hold (day {days_since}/{CONFIG['rebal_freq']} since last rebal)")

    state["last_daily_date"] = latest_date

    # Record equity
    equity = state["capital"]
    if state["positions"]:
        current_prices = closes.iloc[-1]
        for sym, pos in state["positions"].items():
            if sym in current_prices.index:
                price_now = float(current_prices[sym])
                pnl = pos["size"] * (price_now - pos["entry_price"])
                equity += pnl
    state["equity_history"].append({
        "date": latest_date,
        "equity": round(equity, 2),
    })

    _print_status(state, closes)
    return state


if __name__ == "__main__":
    run()
