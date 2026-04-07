"""
H-324 Paper Trade Runner: ADX-Filtered Multi-Asset TSMOM (Vol-Scaled)

Time-series momentum across 14 crypto assets, filtered by BTC ADX.
Each asset gets independent long/short signal based on its own 60-day return.
Positions are vol-scaled (target 15% annual vol per asset, capped at 3x).
Only active when BTC ADX > 30 (trending market). Flat otherwise.
Rebalance every 7 days.

Backtest: Sharpe 1.206, +12.7% ann, -8.0% DD, 60% exposure.
WF 4/5 positive (mean OOS 0.557). Split-half PASS (2.107/0.834).
Neighbors 77.5% positive. Corr 0.216 H-012, 0.414 H-009.
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
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

CONFIG = {
    "lookback": 60,
    "rebal_freq": 7,
    "adx_period": 14,
    "adx_threshold": 30,
    "vol_window": 10,
    "target_vol_ann": 0.15,
    "max_leverage": 3.0,
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


def load_daily_ohlc() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily_close = {}
    daily_high = {}
    daily_low = {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=120)
            if len(df_1h) < 200:
                print(f"  {sym}: insufficient data ({len(df_1h)} bars), skipping")
                continue
            daily = resample_to_daily(df_1h)
            daily_close[sym] = daily["close"]
            daily_high[sym] = daily["high"]
            daily_low[sym] = daily["low"]
        except Exception as e:
            print(f"  {sym}: failed to load: {e}")

    closes = pd.DataFrame(daily_close).dropna(how="all").ffill().dropna()
    highs = pd.DataFrame(daily_high).reindex(closes.index).ffill().dropna()
    lows = pd.DataFrame(daily_low).reindex(closes.index).ffill().dropna()
    return closes, highs, lows


def calc_adx(high_s: pd.Series, low_s: pd.Series, close_s: pd.Series,
             period: int = 14) -> pd.Series:
    plus_dm = high_s.diff()
    minus_dm = -low_s.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

    tr = pd.concat([
        high_s - low_s,
        (high_s - close_s.shift()).abs(),
        (low_s - close_s.shift()).abs(),
    ], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1)
    adx = dx.rolling(period).mean()
    return adx


def compute_signals(closes: pd.DataFrame, highs: pd.DataFrame,
                    lows: pd.DataFrame, date_idx: int) -> dict:
    lookback = CONFIG["lookback"]
    adx_period = CONFIG["adx_period"]
    vol_window = CONFIG["vol_window"]
    target_vol = CONFIG["target_vol_ann"] / np.sqrt(365)
    max_lev = CONFIG["max_leverage"]

    if date_idx < max(lookback, adx_period * 2, vol_window) + 2:
        return {}

    # Check BTC ADX filter
    btc_sym = "BTC/USDT"
    if btc_sym not in closes.columns or btc_sym not in highs.columns:
        return {}

    btc_adx = calc_adx(highs[btc_sym], lows[btc_sym], closes[btc_sym], adx_period)
    adx_val = btc_adx.iloc[date_idx - 1]

    if pd.isna(adx_val) or adx_val < CONFIG["adx_threshold"]:
        return {}  # market not trending, go flat

    # Compute per-asset TS momentum signals
    ret = closes.pct_change()
    past_ret = closes.pct_change(lookback)
    realized_vol = ret.rolling(vol_window).std()

    weights = {}
    for sym in closes.columns:
        mom = past_ret[sym].iloc[date_idx - 1]
        vol = realized_vol[sym].iloc[date_idx - 1]

        if pd.isna(mom) or pd.isna(vol) or vol <= 0:
            continue

        direction = np.sign(mom)
        leverage = min(target_vol / vol, max_lev)
        weight = direction * leverage / len(closes.columns)

        weights[sym] = round(weight, 6)

    return weights


def run():
    print("=== H-324 ADX-Filtered TSMOM Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching data for 14 assets...")
    closes, highs, lows = load_daily_ohlc()

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]
        highs = highs.iloc[:len(closes)]
        lows = lows.iloc[:len(closes)]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    if len(closes.columns) < 7:
        print(f"WARNING: Only {len(closes.columns)} assets loaded, skipping")
        save_state(state)
        return state

    if len(closes) < CONFIG["lookback"] + 30:
        print("Insufficient data for warmup. Skipping.")
        return state

    latest_date = str(closes.index[-1].date())
    slippage = CONFIG["slippage_bps"] / 10_000

    if latest_date == state.get("last_daily_date"):
        print(f"No new daily bar since {latest_date}.")
        _print_status(state, closes)
        return state

    print(f"New daily bar: {latest_date}")

    # Count days since last rebalance
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

        new_weights = compute_signals(closes, highs, lows, date_idx)
        current_prices = closes.iloc[-1]
        old_positions = state["positions"]

        total_fees = 0.0
        trades_this_rebal = 0

        # Mark-to-market to get current capital
        capital = state["capital"]
        for sym, pos in old_positions.items():
            if sym in current_prices.index:
                price_now = float(current_prices[sym])
                unrealized = pos["size"] * (price_now - pos["entry_price"])
                capital += unrealized

        if not new_weights:
            # ADX filter says go flat
            print("  BTC ADX below threshold — going FLAT")
            for sym, pos in old_positions.items():
                if sym in current_prices.index:
                    exit_price = float(current_prices[sym])
                    notional = abs(pos["size"]) * exit_price
                    fee = CONFIG["fee_rate"] * notional
                    total_fees += fee
                    trades_this_rebal += 1

            capital -= total_fees
            state["capital"] = round(capital, 2)
            state["positions"] = {}
            state["last_rebal_date"] = latest_date
            state["days_since_rebal"] = 0
            state["rebal_count"] += 1
            state["total_trades"] += trades_this_rebal
            state["total_fees"] += total_fees

            log.append({
                "type": "flatten",
                "time": datetime.now(timezone.utc).isoformat(),
                "date": latest_date,
                "reason": "ADX_below_threshold",
                "trades": trades_this_rebal,
                "fees": round(total_fees, 2),
                "capital": round(capital, 2),
            })
            print(f"  Closed {trades_this_rebal} positions, Fees: ${total_fees:.2f}")
        else:
            # Exit old positions
            for sym, pos in old_positions.items():
                if sym in current_prices.index:
                    exit_price = float(current_prices[sym])
                    notional = abs(pos["size"]) * exit_price
                    new_w = new_weights.get(sym, 0)
                    if abs(new_w - pos["weight"]) > 0.01:
                        fee = CONFIG["fee_rate"] * notional
                        total_fees += fee
                        trades_this_rebal += 1

            # Open new positions
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
                    "weight": round(weight, 6),
                    "entry_price": round(entry_price, 6),
                    "size": round(size, 8),
                    "direction": "LONG" if weight > 0 else "SHORT",
                }

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
                "btc_adx": round(float(calc_adx(
                    highs["BTC/USDT"], lows["BTC/USDT"], closes["BTC/USDT"],
                    CONFIG["adx_period"]).iloc[date_idx - 1]), 2),
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

    # Update equity snapshot
    mark_equity = _mark_equity(state, closes)
    state["equity_history"].append({
        "date": latest_date,
        "equity": round(mark_equity, 2),
        "positions": len(state["positions"]),
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
    ret = (mark / initial - 1)

    print(f"\nEquity: ${mark:,.2f} (start ${initial:,.2f})")
    print(f"Return: {ret:+.2%}")
    print(f"Rebalances: {state['rebal_count']}, Trades: {state['total_trades']}")
    print(f"Fees: ${state['total_fees']:.2f}")

    if state["positions"]:
        current_prices = closes.iloc[-1]
        print(f"\nPositions ({len(state['positions'])}):")
        for sym, pos in sorted(state["positions"].items(),
                                key=lambda x: x[1]["weight"], reverse=True):
            price = float(current_prices.get(sym, pos["entry_price"]))
            pnl = pos["size"] * (price - pos["entry_price"])
            print(f"  {pos['direction']:5s} {sym:12s} w={pos['weight']:+.4f} "
                  f"entry=${pos['entry_price']:.4f} now=${price:.4f} "
                  f"PnL=${pnl:+.2f}")
    else:
        print("Positions: FLAT (ADX below threshold or not yet rebalanced)")

    print(f"Next rebal in {CONFIG['rebal_freq'] - state['days_since_rebal']} day(s)")


if __name__ == "__main__":
    run()
