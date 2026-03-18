"""
H-024 Paper Trade Runner: Low-Beta Anomaly (14 Crypto Assets)

Market-neutral strategy: rank 14 assets by rolling beta vs BTC (60-day),
long top 3 lowest-beta, short bottom 3 highest-beta. Rebalance every 21 days
using lagged (t-1) ranking.

Internal simulation -- called each session. Only acts on new daily bars
and when a rebalance is due (every 21 calendar days since first rebalance).

Parameters: W60_R21_N3 (confirmed in deep validation).
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

# -- Strategy parameters ------------------------------------------------------
ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

CONFIG = {
    "beta_window": 60,       # 60-day rolling beta vs BTC
    "rebal_freq": 21,        # rebalance every 21 days
    "n_long": 3,             # long top 3 lowest-beta
    "n_short": 3,            # short bottom 3 highest-beta
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,       # 0.1% taker
    "slippage_bps": 2.0,
}

STATE_FILE = Path(__file__).parent / "state.json"
LOG_FILE = Path(__file__).parent / "log.json"


# -- State persistence --------------------------------------------------------
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


# -- Data loading -------------------------------------------------------------
def load_daily_closes() -> pd.DataFrame:
    """Fetch 1h data for all assets, resample to daily, return close prices."""
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
    closes = pd.DataFrame(daily_closes)
    closes = closes.dropna(how="all").ffill().dropna()
    return closes


# -- Signal generation --------------------------------------------------------
def compute_beta_rankings(closes: pd.DataFrame, date_idx: int) -> dict:
    """
    Rank assets by rolling beta vs BTC (low beta = high rank).
    Uses data up to date_idx - 1 (lagged) to avoid lookahead.
    Returns dict of {symbol: weight} for long/short positions.
    """
    beta_window = CONFIG["beta_window"]
    warmup = beta_window + 5

    if date_idx < warmup:
        return {}

    lagged_idx = date_idx - 1
    if lagged_idx < beta_window:
        return {}

    # Compute daily returns for the window
    window_data = closes.iloc[lagged_idx - beta_window + 1:lagged_idx + 1]
    daily_returns = window_data.pct_change().dropna()

    if len(daily_returns) < beta_window - 2:
        return {}

    btc_rets = daily_returns["BTC/USDT"]
    btc_var = btc_rets.var()
    if btc_var < 1e-10:
        return {}

    # Compute beta for each asset vs BTC
    betas = {}
    for col in closes.columns:
        if col == "BTC/USDT":
            betas[col] = 1.0  # BTC beta = 1 by definition
            continue
        cov = daily_returns[col].cov(btc_rets)
        beta = cov / btc_var
        betas[col] = beta

    betas_series = pd.Series(betas)
    valid_betas = betas_series.dropna()

    if len(valid_betas) < CONFIG["n_long"] + CONFIG["n_short"]:
        return {}

    # Rank by ASCENDING beta (low beta = long, high beta = short)
    ranked = valid_betas.sort_values(ascending=True)

    longs = ranked.index[:CONFIG["n_long"]]
    shorts = ranked.index[-CONFIG["n_short"]:]

    weights = {}
    for sym in longs:
        weights[sym] = 1.0 / CONFIG["n_long"]
    for sym in shorts:
        weights[sym] = -1.0 / CONFIG["n_short"]

    return weights


# -- Main runner --------------------------------------------------------------
def run():
    print("=== H-024 Beta Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    # Fetch latest data for all assets
    print("Fetching data for 14 assets...")
    closes = load_daily_closes()
    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    if len(closes) < CONFIG["beta_window"] + 10:
        print("Insufficient data for strategy warmup. Skipping.")
        return state

    latest_date = str(closes.index[-1].date())
    slippage = CONFIG["slippage_bps"] / 10_000

    # Check if we have a new daily bar
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

    # -- Rebalance check -------------------------------------------------------
    if days_since >= CONFIG["rebal_freq"]:
        print(f"Rebalancing (day {days_since} since last rebal)...")

        new_weights = compute_beta_rankings(closes, date_idx)
        if not new_weights:
            print("  Could not compute rankings. Skipping rebalance.")
        else:
            current_prices = closes.iloc[-1]
            old_positions = state["positions"]

            # Mark-to-market existing positions to get current capital
            capital = state["capital"]
            for sym, pos in old_positions.items():
                if sym in current_prices.index:
                    price_now = float(current_prices[sym])
                    unrealized = pos["size"] * (price_now - pos["entry_price"])
                    capital += unrealized

            # Compute fees on turnover
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

            # Deduct fees from capital
            capital -= total_fees
            state["capital"] = round(capital, 2)
            state["positions"] = new_positions
            state["last_rebal_date"] = latest_date
            state["days_since_rebal"] = 0
            state["rebal_count"] += 1
            state["total_trades"] += trades_this_rebal
            state["total_fees"] += total_fees

            # Log the rebalance
            longs = [s for s, p in new_positions.items() if p["weight"] > 0]
            shorts = [s for s, p in new_positions.items() if p["weight"] < 0]

            # Log beta values for diagnostics
            beta_window = CONFIG["beta_window"]
            lagged_idx = date_idx - 1
            window_data = closes.iloc[lagged_idx - beta_window + 1:lagged_idx + 1]
            daily_rets = window_data.pct_change().dropna()
            btc_rets = daily_rets["BTC/USDT"]
            btc_var = btc_rets.var()
            betas_log = {}
            for col in closes.columns:
                if col == "BTC/USDT":
                    betas_log[col] = 1.0
                else:
                    cov = daily_rets[col].cov(btc_rets)
                    betas_log[col] = round(cov / btc_var, 4) if btc_var > 0 else 1.0

            log_entry = {
                "type": "rebalance",
                "time": datetime.now(timezone.utc).isoformat(),
                "date": latest_date,
                "longs": longs,
                "shorts": shorts,
                "trades": trades_this_rebal,
                "fees": round(total_fees, 2),
                "capital": round(capital, 2),
                "beta_ranking": dict(sorted(betas_log.items(), key=lambda x: x[1])),
            }
            log.append(log_entry)

            print(f"  LONG (low beta):  {', '.join(s.replace('/USDT','') for s in longs)}")
            print(f"  SHORT (high beta): {', '.join(s.replace('/USDT','') for s in shorts)}")
            print(f"  Trades: {trades_this_rebal}, Fees: ${total_fees:.2f}")

            # Print beta ranking
            print(f"  Beta ranking (60d, low to high):")
            for sym, beta in sorted(betas_log.items(), key=lambda x: x[1]):
                marker = " <-- LONG" if sym in longs else (" <-- SHORT" if sym in shorts else "")
                print(f"    {sym:12s} beta={beta:.4f}{marker}")
    else:
        print(f"No rebalance today (day {days_since}/{CONFIG['rebal_freq']})")

    # -- Update equity snapshot -------------------------------------------------
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
    """Mark-to-market all positions."""
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
    import argparse
    parser = argparse.ArgumentParser(description="H-024 Beta Paper Trade")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if args.report:
        state = load_state()
        if not state["equity_history"]:
            print("No equity history yet.")
        else:
            eq_hist = pd.DataFrame(state["equity_history"])
            eq_hist["date"] = pd.to_datetime(eq_hist["date"])
            initial = CONFIG["initial_capital"]
            current = eq_hist["equity"].iloc[-1]
            days = (eq_hist["date"].iloc[-1] - eq_hist["date"].iloc[0]).days or 1
            print("=== H-024 Beta Performance Report ===")
            print(f"Period: {eq_hist['date'].iloc[0].date()} to {eq_hist['date'].iloc[-1].date()} ({days} days)")
            print(f"Capital: ${initial:,.2f} -> ${current:,.2f}")
            print(f"Return: {(current / initial - 1):+.2%}")
    else:
        run()
