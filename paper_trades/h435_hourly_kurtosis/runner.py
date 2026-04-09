"""
H-435 Paper Trade Runner: Hourly Return Kurtosis Factor

Market-neutral strategy: rank 14 crypto assets by rolling average of
hourly return kurtosis (computed from previous day's hourly bars).
HIGH kurtosis → long (fat-tailed assets have jump premium).

Backtest: IS 95.8% (high_long direction). Best LB20_R3_N4
Sharpe 1.520, +70.1% ann, -26.6% DD.
WF 4/6 mean 1.367. Split-half H1=1.824, H2=1.038.
Corr H-012 0.106 — low, good diversifier.
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


def compute_hourly_kurtosis_daily(df_1h_sym):
    """Compute daily kurtosis from hourly returns for one asset."""
    df = df_1h_sym.copy()
    if df.index.tz:
        df.index = df.index.tz_localize(None)
    df["date"] = df.index.normalize()
    h_rets = df["close"].pct_change()

    daily_kurt = {}
    for date_ts, group in h_rets.groupby(df["date"]):
        vals = group.dropna().values
        if len(vals) >= 8:
            k = stats.kurtosis(vals, fisher=True)
            if np.isfinite(k):
                daily_kurt[date_ts] = k
    return pd.Series(daily_kurt).sort_index() if daily_kurt else None


def compute_rankings(hourly_dict):
    """Rank assets by rolling average hourly kurtosis. HIGH → long."""
    scores = {}
    for sym, df_1h in hourly_dict.items():
        kurt_series = compute_hourly_kurtosis_daily(df_1h)
        if kurt_series is None or len(kurt_series) < CONFIG["lookback"]:
            continue
        rolling_mean = kurt_series.rolling(CONFIG["lookback"],
                                           min_periods=CONFIG["lookback"] // 2).mean()
        vals = rolling_mean.dropna()
        if len(vals) >= 2:
            last_val = vals.iloc[-2]  # LAGGED: use yesterday
        else:
            continue
        if np.isfinite(last_val):
            scores[sym] = last_val

    if len(scores) < CONFIG["n_long"] + CONFIG["n_short"]:
        return {}

    valid = pd.Series(scores).sort_values(ascending=False)  # HIGH first = longs
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
    print("=== H-435 Hourly Kurtosis Paper Trade Runner ===")
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

                new_positions[sym] = {
                    "symbol": sym,
                    "size": size,
                    "entry_price": entry_price,
                    "weight": weight,
                    "entry_date": latest_date,
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
                "action": "rebalance",
                "date": latest_date,
                "n_positions": len(new_positions),
                "capital": capital,
                "fees": total_fees,
                "trades": trades_this_rebal,
            })
            save_log(log)

            print(f"  {trades_this_rebal} trades, fees ${total_fees:.2f}")
            longs = [s for s, p in new_positions.items() if p["weight"] > 0]
            shorts = [s for s, p in new_positions.items() if p["weight"] < 0]
            print(f"  LONG: {', '.join(longs)}")
            print(f"  SHORT: {', '.join(shorts)}")
    else:
        print(f"Hold (day {days_since}/{CONFIG['rebal_freq']} until rebal)")

    state["last_daily_date"] = latest_date
    _print_status(state, closes)
    return state


if __name__ == "__main__":
    run()
