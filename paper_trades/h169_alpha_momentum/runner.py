"""
H-169 Paper Trade Runner: Beta-Adjusted Momentum (Alpha Factor, 13 Non-BTC Assets)

Market-neutral strategy: rank 13 non-BTC assets by alpha vs BTC
(return - beta * BTC_return). Captures genuine outperformance, not just
high-beta rides. Long top 4 (positive alpha), short bottom 4 (negative alpha).
Rebalance every 5 days.

Backtest: IS 100% positive (30/30), best Sharpe 1.550 (+67.9% ann, -35.2% DD).
WF 4/6 positive, mean OOS 1.648. Split-half H1=1.335, H2=0.422.
Correlation: H-012 0.342, H-076 0.161, H-160 0.133.
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

# ── Strategy parameters ──────────────────────────────────────────────
ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

CONFIG = {
    "lookback": 10,          # 10-day rolling alpha window
    "rebal_freq": 5,         # rebalance every 5 days
    "n_long": 4,             # long top 4 (highest alpha)
    "n_short": 4,            # short bottom 4 (lowest alpha)
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,       # 0.1% taker
    "slippage_bps": 2.0,
}

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
    daily_close = {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=120)
            if len(df_1h) < 200:
                print(f"  {sym}: insufficient data ({len(df_1h)} bars), skipping")
                continue
            daily = resample_to_daily(df_1h)
            daily_close[sym] = daily["close"]
        except Exception as e:
            print(f"  {sym}: failed to load: {e}")

    closes = pd.DataFrame(daily_close).dropna(how="all").ffill().dropna()
    return closes


# ── Signal generation ────────────────────────────────────────────────
def compute_alpha(prices: pd.Series, btc_prices: pd.Series, lookback: int) -> float:
    """Rolling alpha: asset return minus beta * BTC return over lookback window."""
    if len(prices) < lookback + 2 or len(btc_prices) < lookback + 2:
        return np.nan
    asset_rets = prices.pct_change().dropna().iloc[-lookback:]
    btc_rets = btc_prices.pct_change().dropna().iloc[-lookback:]
    common = asset_rets.index.intersection(btc_rets.index)
    if len(common) < lookback // 2:
        return np.nan
    a = asset_rets.loc[common].values
    b = btc_rets.loc[common].values
    # OLS beta
    var_b = np.var(b)
    if var_b < 1e-12:
        return np.nan
    beta = np.cov(a, b)[0, 1] / var_b
    # Alpha = cumulative excess return
    alpha = a.sum() - beta * b.sum()
    return alpha


def compute_rankings(closes: pd.DataFrame, date_idx: int) -> dict:
    """
    Rank non-BTC assets by alpha vs BTC.
    Uses data through day (date_idx - 1) for lagged signals.
    """
    lookback = CONFIG["lookback"]
    warmup = lookback + 10

    if date_idx < warmup:
        return {}

    if "BTC/USDT" not in closes.columns:
        return {}

    btc = closes["BTC/USDT"].iloc[:date_idx]
    non_btc = [c for c in closes.columns if c != "BTC/USDT"]

    signals = {}
    for sym in non_btc:
        prices = closes[sym].iloc[:date_idx]
        val = compute_alpha(prices, btc, lookback)
        if not np.isnan(val):
            signals[sym] = val

    n_long = CONFIG["n_long"]
    n_short = CONFIG["n_short"]

    if len(signals) < n_long + n_short:
        return {}

    ranked = pd.Series(signals).sort_values(ascending=False)
    longs = ranked.index[:n_long]
    shorts = ranked.index[-n_short:]

    weights = {}
    for sym in longs:
        weights[sym] = 1.0 / n_long
    for sym in shorts:
        weights[sym] = -1.0 / n_short

    return weights


# ── Main runner ──────────────────────────────────────────────────────
def run():
    print("=== H-169 Alpha Momentum Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching data for 14 assets...")
    closes = load_daily_closes()

    # Drop today's incomplete bar
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    # Guard: skip rebalance if too few assets loaded
    if len(closes.columns) < 7:
        print(f"WARNING: Only {len(closes.columns)} of 14 assets loaded, skipping rebalance (need >=7)")
        save_state(state)
        return state

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

    # Count days since last rebalance
    if state["last_rebal_date"] is None:
        days_since = CONFIG["rebal_freq"]
    else:
        last_rebal = pd.Timestamp(state["last_rebal_date"])
        current = pd.Timestamp(latest_date)
        days_since = (current - last_rebal).days

    state["days_since_rebal"] = days_since
    date_idx = len(closes) - 1

    # ── Rebalance check ──────────────────────────────────────────
    if days_since >= CONFIG["rebal_freq"]:
        print(f"Rebalancing (day {days_since} since last rebal)...")

        new_weights = compute_rankings(closes, date_idx)
        if not new_weights:
            print("  Could not compute rankings. Skipping rebalance.")
        else:
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

            # Count trades (changed positions)
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
                    "weight": weight,
                    "entry_price": round(entry_price, 6),
                    "size": round(size, 8),
                    "direction": "LONG" if weight > 0 else "SHORT",
                }

            # Guard: abort rebalance if too few positions
            n_min_positions = CONFIG["n_long"] + CONFIG["n_short"]
            if len(new_positions) < n_min_positions:
                print(f"  WARNING: Only {len(new_positions)}/{n_min_positions} positions created, aborting rebalance")
                new_positions = old_positions
                total_fees = 0
                trades_this_rebal = 0

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

            log_entry = {
                "type": "rebalance",
                "time": datetime.now(timezone.utc).isoformat(),
                "date": latest_date,
                "longs": longs,
                "shorts": shorts,
                "trades": trades_this_rebal,
                "fees": round(total_fees, 2),
                "capital": round(capital, 2),
            }
            log.append(log_entry)

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
            print(f"  {pos['direction']:5s} {sym:12s} w={pos['weight']:+.2f} "
                  f"entry=${pos['entry_price']:.4f} now=${price:.4f} "
                  f"PnL=${pnl:+.2f}")
    else:
        print("Positions: FLAT")

    print(f"Next rebal in {CONFIG['rebal_freq'] - state['days_since_rebal']} day(s)")


if __name__ == "__main__":
    run()
