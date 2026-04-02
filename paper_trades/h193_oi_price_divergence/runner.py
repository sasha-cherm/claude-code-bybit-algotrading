"""
H-193 Paper Trade Runner: OI-Price Momentum Divergence Factor (14 Assets)

Market-neutral strategy: compare OI momentum rank vs price momentum rank
cross-sectionally. When price outpaces OI (low divergence) = healthy trend
with de-leveraging. When OI outpaces price (high divergence) = crowded
positioning without price follow-through.
Long lowest divergence (aligned momentum), short highest (misaligned).
Rebalance every 7 days.

Backtest: IS 86.7% positive (26/30), mean Sharpe 0.694, best LB20_R7_N3
Sharpe 1.774 (+75.6% ann, -28.9% DD). WF 4/5 positive, mean OOS 1.470.
Split-half H1=2.196, H2=2.001. Corr H-012 0.380, H-076 0.056.
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

# ── Strategy parameters ──────────────────────────────────────────────
ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]
ASSET_TICKERS = [s.split("/")[0] for s in ASSETS]

CONFIG = {
    "lookback": 20,          # 20-day momentum lookback
    "rebal_freq": 7,         # rebalance every 7 days
    "n_long": 3,             # long bottom 3 (lowest divergence = aligned momentum)
    "n_short": 3,            # short top 3 (highest divergence = misaligned)
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,       # 0.1% taker
    "slippage_bps": 2.0,
}

OI_CACHE_DIR = ROOT / "data" / "oi"
STATE_FILE = Path(__file__).parent / "state.json"
LOG_FILE = Path(__file__).parent / "log.json"


# ── State persistence ────────────────────────────────────────────────
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


# ── Data loading ─────────────────────────────────────────────────────
def load_daily_closes() -> pd.DataFrame:
    daily_closes = {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=120)
            if len(df_1h) < 200:
                print(f"  {sym}: insufficient data ({len(df_1h)} bars), skipping")
                continue
            daily = resample_to_daily(df_1h)
            daily_closes[sym] = daily["close"]
        except Exception as e:
            print(f"  {sym}: failed to load: {e}")
    closes = pd.DataFrame(daily_closes).dropna(how="all").ffill().dropna()
    return closes


def load_oi_data() -> pd.DataFrame:
    """Load cached daily OI data for all assets."""
    import ccxt

    oi_dict = {}
    for ticker in ASSET_TICKERS:
        cache_file = OI_CACHE_DIR / f"{ticker}_oi_1d.parquet"

        if cache_file.exists():
            df = pd.read_parquet(cache_file)
            last_date = df.index[-1]
            if last_date.tz is None:
                last_date = last_date.tz_localize("UTC")
            days_old = (pd.Timestamp.now("UTC") - last_date).days

            if days_old >= 1:
                df = _fetch_oi_fresh(ticker)
                if df is not None and len(df) > 0:
                    df.to_parquet(cache_file)
                else:
                    df = pd.read_parquet(cache_file)
        else:
            df = _fetch_oi_fresh(ticker)
            if df is not None and len(df) > 0:
                OI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                df.to_parquet(cache_file)
            else:
                continue

        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        oi_dict[f"{ticker}/USDT"] = df["openInterest"]

    oi_panel = pd.DataFrame(oi_dict)
    return oi_panel.sort_index().dropna(how="all")


def _fetch_oi_fresh(ticker: str) -> "pd.DataFrame | None":
    """Fetch historical OI from Bybit V5 API."""
    import ccxt
    exchange = ccxt.bybit()
    all_data = []
    cursor = None

    for _ in range(5):
        params = {
            "category": "linear",
            "symbol": f"{ticker}USDT",
            "intervalTime": "1d",
            "limit": "200",
        }
        if cursor:
            params["cursor"] = cursor

        try:
            resp = exchange.publicGetV5MarketOpenInterest(params)
            data = resp["result"]["list"]
            if not data:
                break
            all_data.extend(data)
            cursor = resp["result"].get("nextPageCursor", "")
            if not cursor:
                break
            time.sleep(0.3)
        except Exception as e:
            print(f"  OI fetch error for {ticker}: {e}")
            break

    if not all_data:
        return None

    df = pd.DataFrame(all_data)
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
    df["openInterest"] = df["openInterest"].astype(float)
    df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    df = df.set_index("timestamp")
    return df[["openInterest"]]


# ── Signal generation ────────────────────────────────────────────────
def compute_divergence_signal(closes: pd.DataFrame, oi: pd.DataFrame,
                              date_idx: int) -> dict:
    """
    Rank assets by OI-price momentum divergence.
    For each asset:
      - price_momentum = price_pct_change(lookback)
      - oi_momentum = oi_pct_change(lookback)
      - Rank each cross-sectionally
      - divergence = abs(oi_rank - price_rank)
    Low divergence = OI and price aligned → healthy trend → long.
    High divergence = misaligned → crowded/vulnerable → short.
    """
    lookback = CONFIG["lookback"]
    if date_idx < lookback + 2:
        return {}

    # Use lagged data (t-1) for signal
    price_slice = closes.iloc[:date_idx]
    if len(price_slice) < lookback + 1:
        return {}

    # Price momentum: pct change over lookback
    price_now = price_slice.iloc[-1]
    price_then = price_slice.iloc[-lookback - 1]
    price_mom = (price_now - price_then) / price_then

    # OI momentum: align OI dates to price dates
    oi_daily = oi.resample("D").last().ffill()
    common_dates = price_slice.index.intersection(oi_daily.index)
    if len(common_dates) < lookback + 1:
        # Try approximate alignment
        oi_reindexed = oi_daily.reindex(price_slice.index, method="ffill")
    else:
        oi_reindexed = oi_daily.reindex(price_slice.index, method="ffill")

    oi_now = oi_reindexed.iloc[-1]
    oi_then = oi_reindexed.iloc[-lookback - 1]
    oi_mom = (oi_now - oi_then) / oi_then

    # Get common assets
    common = price_mom.dropna().index.intersection(oi_mom.dropna().index)
    common = [c for c in common if c in closes.columns]

    n_needed = CONFIG["n_long"] + CONFIG["n_short"]
    if len(common) < n_needed:
        return {}

    # Cross-sectional ranks
    pm = price_mom[common].rank()
    om = oi_mom[common].rank()

    # Divergence = absolute rank difference
    divergence = (pm - om).abs()
    divergence = divergence.dropna()

    if len(divergence) < n_needed:
        return {}

    ranked = divergence.sort_values(ascending=True)

    longs = ranked.index[:CONFIG["n_long"]]      # lowest divergence
    shorts = ranked.index[-CONFIG["n_short"]:]    # highest divergence

    weights = {}
    for sym in longs:
        weights[sym] = 1.0 / CONFIG["n_long"]
    for sym in shorts:
        weights[sym] = -1.0 / CONFIG["n_short"]

    return weights


# ── Main runner ──────────────────────────────────────────────────────
def run():
    print("=== H-193 OI-Price Momentum Divergence Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching price data for 14 assets...")
    closes = load_daily_closes()

    # Drop today's incomplete bar
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    if len(closes.columns) < 7:
        print(f"WARNING: Only {len(closes.columns)} of 14 assets loaded, skipping")
        save_state(state)
        return state

    print("Loading OI data...")
    oi = load_oi_data()
    print(f"OI data: {len(oi)} rows, {len(oi.columns)} assets")

    warmup = CONFIG["lookback"] + 10
    if len(closes) < warmup:
        print("Insufficient data for strategy warmup. Skipping.")
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

    # ── Rebalance check ───────────────────────────────────────────
    if days_since >= CONFIG["rebal_freq"]:
        print(f"Rebalancing (day {days_since} since last rebal)...")

        new_weights = compute_divergence_signal(closes, oi, date_idx)
        if not new_weights:
            print("  Could not compute divergence signal. Skipping rebalance.")
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
                    "weight": weight,
                    "entry_price": round(entry_price, 6),
                    "size": round(size, 8),
                    "direction": "LONG" if weight > 0 else "SHORT",
                }

            n_needed = CONFIG["n_long"] + CONFIG["n_short"]
            if len(new_positions) < n_needed:
                print(f"  WARNING: Only {len(new_positions)}/{n_needed} positions created, aborting rebalance")
            else:
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

    # ── Update equity snapshot ───────────────────────────────────
    mark_equity = _mark_equity(state, closes)
    state["equity_history"].append({
        "date": latest_date,
        "equity": round(mark_equity, 2),
        "positions": len(state["positions"]),
        "rebalanced": days_since >= CONFIG["rebal_freq"],
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
    ret = mark / initial - 1

    print(f"\nEquity: ${mark:,.2f} (start ${initial:,.2f})")
    print(f"Return: {ret:+.2%}")
    print(f"Rebalances: {state['rebal_count']}, Trades: {state['total_trades']}")
    print(f"Fees: ${state['total_fees']:.2f}")

    if state["positions"]:
        current_prices = closes.iloc[-1]
        print(f"\nPositions ({len(state['positions'])}):")
        for sym, pos in sorted(
            state["positions"].items(),
            key=lambda x: x[1]["weight"],
            reverse=True,
        ):
            price = float(current_prices.get(sym, pos["entry_price"]))
            pnl = pos["size"] * (price - pos["entry_price"])
            print(
                f"  {pos['direction']:5s} {sym:12s} w={pos['weight']:+.2f} "
                f"entry=${pos['entry_price']:.4f} now=${price:.4f} "
                f"PnL=${pnl:+.2f}"
            )
    else:
        print("Positions: FLAT")

    print(f"Next rebal in {CONFIG['rebal_freq'] - state['days_since_rebal']} day(s)")


if __name__ == "__main__":
    run()
