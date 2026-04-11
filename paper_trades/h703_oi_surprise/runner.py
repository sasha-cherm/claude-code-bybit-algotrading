"""
H-703 Paper Trade Runner: OI Surprise (Residual) XS Factor

Market-neutral strategy: OI change minus volume change as residual signal.
Assets where OI grows LESS than expected from volume (low surprise = low
positioning density relative to activity) outperform.

Direction: low_long — long bottom 3 (lowest OI-surprise), short top 3.
Params: LB15_R7_N3

Backtest: IS 83% positive (25/30 expanded grid), best LB15_R7_N3
Sharpe 1.578 (+66.5% ann, -38.2% DD). WF 5/6 positive, mean 1.422.
Split-half H1=1.409, H2=1.332. H-012 PnL corr -0.010.
"""

import json
import sys
import time
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
ASSET_TICKERS = [s.split("/")[0] for s in ASSETS]

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


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "started": datetime.now(timezone.utc).isoformat(),
        "capital": CONFIG["initial_capital"],
        "equity": CONFIG["initial_capital"],
        "initial_capital": CONFIG["initial_capital"],
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


def load_daily_closes() -> pd.DataFrame:
    daily_closes = {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=120)
            if len(df_1h) < 200:
                continue
            daily = resample_to_daily(df_1h)
            daily_closes[sym] = daily["close"]
        except Exception as e:
            print(f"  {sym}: failed to load: {e}")
    return pd.DataFrame(daily_closes).dropna(how="all").ffill().dropna()


def load_daily_volumes() -> pd.DataFrame:
    daily_volumes = {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=120)
            if len(df_1h) < 200:
                continue
            daily = resample_to_daily(df_1h)
            daily_volumes[sym] = daily["volume"] * daily["close"]
        except:
            pass
    return pd.DataFrame(daily_volumes).dropna(how="all").ffill().dropna()


def load_oi_data() -> pd.DataFrame:
    import ccxt

    oi_dict = {}
    for ticker in ASSET_TICKERS:
        try:
            exchange = ccxt.bybit()
            all_data = []
            cursor = None
            for _ in range(3):
                params = {
                    "category": "linear",
                    "symbol": f"{ticker}USDT",
                    "intervalTime": "1d",
                    "limit": "200",
                }
                if cursor:
                    params["cursor"] = cursor
                resp = exchange.publicGetV5MarketOpenInterest(params)
                data = resp["result"]["list"]
                if not data:
                    break
                all_data.extend(data)
                cursor = resp["result"].get("nextPageCursor", "")
                if not cursor:
                    break
                time.sleep(0.2)

            if all_data:
                df = pd.DataFrame(all_data)
                df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
                df["openInterest"] = df["openInterest"].astype(float)
                df = df.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC")
                oi_dict[f"{ticker}/USDT"] = df["openInterest"]
        except Exception as e:
            print(f"  OI fetch error {ticker}: {e}")
        time.sleep(0.1)

    return pd.DataFrame(oi_dict).sort_index().dropna(how="all")


def compute_oi_surprise_signal(closes, volumes, oi, date_idx):
    lookback = CONFIG["lookback"]
    if date_idx < lookback + 2:
        return {}

    price_slice = closes.iloc[:date_idx]
    vol_slice = volumes.iloc[:date_idx]

    oi_daily = oi.resample("D").last().ffill()
    oi_reindexed = oi_daily.reindex(price_slice.index, method="ffill")

    if len(price_slice) < lookback + 1 or len(oi_reindexed) < lookback + 1:
        return {}

    # OI % change over lookback
    oi_now = oi_reindexed.iloc[-1]
    oi_then = oi_reindexed.iloc[-lookback - 1]
    oi_chg = (oi_now - oi_then) / oi_then.replace(0, np.nan)

    # Volume % change over lookback
    vol_now = vol_slice.iloc[-lookback:].mean()
    vol_then = vol_slice.iloc[-2 * lookback:-lookback].mean()
    vol_chg = (vol_now - vol_then) / vol_then.replace(0, np.nan)

    # OI surprise = OI change - Volume change
    surprise = oi_chg - vol_chg
    surprise = surprise.dropna()

    common = [c for c in surprise.index if c in closes.columns]
    n_needed = CONFIG["n_long"] + CONFIG["n_short"]
    if len(common) < n_needed:
        return {}

    surprise = surprise[common]
    # low_long: long lowest surprise (OI grew less than volume), short highest
    ranked = surprise.sort_values(ascending=True)

    longs = ranked.index[:CONFIG["n_long"]]
    shorts = ranked.index[-CONFIG["n_short"]:]

    weights = {}
    for sym in longs:
        weights[sym] = 1.0 / CONFIG["n_long"]
    for sym in shorts:
        weights[sym] = -1.0 / CONFIG["n_short"]
    return weights


def run():
    print("=== H-703 OI Surprise Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching price/volume data...")
    closes = load_daily_closes()
    volumes = load_daily_volumes()

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]
        volumes = volumes.iloc[:-1]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    if len(closes.columns) < 7:
        print(f"WARNING: Only {len(closes.columns)} assets loaded, skipping")
        save_state(state)
        return state

    print("Loading OI data...")
    oi = load_oi_data()
    print(f"OI data: {len(oi)} rows, {len(oi.columns)} assets")

    warmup = CONFIG["lookback"] + 10
    if len(closes) < warmup:
        print("Insufficient data. Skipping.")
        return state

    latest_date = str(closes.index[-1].date())
    slippage = CONFIG["slippage_bps"] / 10_000

    if latest_date == state.get("last_daily_date"):
        print(f"No new daily bar since {latest_date}.")
        _update_equity(state, closes)
        save_state(state)
        return state

    print(f"New daily bar: {latest_date}")

    # Mark-to-market existing positions
    _update_equity(state, closes)

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

        new_weights = compute_oi_surprise_signal(closes, volumes, oi, date_idx)
        if not new_weights:
            print("  Could not compute OI surprise signal. Skipping.")
        else:
            current_prices = closes.iloc[-1]
            capital = _mark_capital(state, current_prices)

            total_fees = 0.0
            trades_this_rebal = 0
            old_positions = state["positions"]

            for sym in set(list(old_positions.keys()) + list(new_weights.keys())):
                old_w = old_positions.get(sym, {}).get("weight", 0)
                new_w = new_weights.get(sym, 0)
                if abs(new_w - old_w) > 0.01 and sym in current_prices.index:
                    price = float(current_prices[sym])
                    notional = abs(new_w) * capital
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
                size = abs(weight) * capital / entry_price
                new_positions[sym] = {
                    "weight": weight,
                    "size": size * direction,
                    "entry_price": entry_price,
                    "entry_date": latest_date,
                }

            state["capital"] = capital - total_fees
            state["total_fees"] += total_fees
            state["total_trades"] += trades_this_rebal
            state["positions"] = new_positions
            state["last_rebal_date"] = latest_date
            state["rebal_count"] += 1

            longs = [s.split("/")[0] for s, p in new_positions.items() if p["weight"] > 0]
            shorts = [s.split("/")[0] for s, p in new_positions.items() if p["weight"] < 0]
            print(f"  LONG: {longs}")
            print(f"  SHORT: {shorts}")
            print(f"  Trades: {trades_this_rebal}, Fees: ${total_fees:.2f}")

            log.append({
                "date": latest_date,
                "type": "rebal",
                "longs": longs,
                "shorts": shorts,
                "capital": round(state["capital"], 2),
                "equity": round(state["equity"], 2),
                "trades": trades_this_rebal,
                "fees": round(total_fees, 2),
            })

    _update_equity(state, closes)
    state["last_daily_date"] = latest_date
    state["equity_history"].append({
        "date": latest_date,
        "equity": round(state["equity"], 2),
    })

    pnl_pct = (state["equity"] / CONFIG["initial_capital"] - 1) * 100
    print(f"Equity: ${state['equity']:,.2f} ({pnl_pct:+.2f}%)")

    save_state(state)
    save_log(log)
    return state


def _mark_capital(state, current_prices):
    capital = state["capital"]
    for sym, pos in state["positions"].items():
        if sym in current_prices.index:
            price_now = float(current_prices[sym])
            unrealized = pos["size"] * (price_now - pos["entry_price"])
            capital += unrealized
    return capital


def _update_equity(state, closes):
    if len(closes) == 0:
        state["equity"] = state["capital"]
        return
    current_prices = closes.iloc[-1]
    state["equity"] = _mark_capital(state, current_prices)


if __name__ == "__main__":
    run()
