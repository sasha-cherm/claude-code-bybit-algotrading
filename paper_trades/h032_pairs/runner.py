"""
H-032 Paper Trade Runner: Pairwise Cointegration Statistical Arbitrage

Trades a portfolio of cointegrated crypto pairs using z-score mean reversion.
Each pair: compute log-spread with OLS hedge ratio, rolling z-score, enter on
extremes, exit on mean reversion. Equal-weight portfolio of all active pairs.

Confirmed standalone (weak): IS Sharpe 1.30 (12 pairs), OOS Sharpe 1.33 (8 pairs),
DD 5.8% OOS. Negative correlation with H-012 momentum (-0.31).

Internal simulation -- called each session. Only acts on new daily bars.
Each pair is independently tracked: positions open/close based on z-score signals.

Pairs selected from deep validation (passed WF >= 3/5 OR 50/50 split):
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

# -- Pair definitions (from deep validation) -----------------------------------
# Each pair: (name, asset_a, asset_b, z_window, entry_z, exit_z, stop_z)
# Selected: pairs that passed WF >= 3/5 or 50/50 train/test split
PAIRS = [
    ("DOT/ATOM",  "DOT/USDT",  "ATOM/USDT", 30, 1.5, 0.25, 4.0),
    ("DOGE/LINK", "DOGE/USDT", "LINK/USDT", 40, 1.0, 0.0,  4.0),
    ("DOGE/ADA",  "DOGE/USDT", "ADA/USDT",  20, 2.5, 0.25, 4.0),
    ("DOT/OP",    "DOT/USDT",  "OP/USDT",   60, 2.5, 0.25, 4.0),
    ("SOL/DOGE",  "SOL/USDT",  "DOGE/USDT", 20, 2.0, 0.0,  3.5),
    ("AVAX/DOT",  "AVAX/USDT", "DOT/USDT",  50, 1.0, 0.0,  4.0),
    ("NEAR/OP",   "NEAR/USDT", "OP/USDT",   40, 2.0, 0.0,  4.0),
    ("ARB/ATOM",  "ARB/USDT",  "ATOM/USDT", 50, 2.5, 0.0,  4.0),
]

# All assets needed
ALL_ASSETS = list(set(
    a for _, a, b, *_ in PAIRS for a in [a, b]
))

CONFIG = {
    "hr_window": 180,        # hedge ratio estimation window (rolling)
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,       # 0.1% taker
    "slippage_bps": 2.0,
    "capital_per_pair": None, # set dynamically = initial_capital / n_pairs
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
        "pair_positions": {},  # {pair_name: {position: 1/-1/0, entry_equity: ..., ...}}
        "equity_history": [],
        "last_daily_date": None,
        "total_trades": 0,
        "total_fees": 0.0,
        "trades_log": [],  # completed trade P&L
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
def load_daily_data() -> pd.DataFrame:
    """Fetch 1h data for all needed assets, resample to daily, return closes."""
    daily_closes = {}
    for sym in ALL_ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=730)
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


# -- Hedge ratio estimation ---------------------------------------------------
def compute_hedge_ratio(log_a: pd.Series, log_b: pd.Series) -> float:
    """OLS hedge ratio: log_a = alpha + HR * log_b + epsilon."""
    X = np.column_stack([np.ones(len(log_b)), log_b.values])
    y = log_a.values
    result = np.linalg.lstsq(X, y, rcond=None)[0]
    return result[1]


# -- Main runner --------------------------------------------------------------
def run():
    print("=== H-032 Pairs Trading Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    # Fetch latest data
    print("Fetching data for pair assets...")
    closes = load_daily_data()

    # Drop today's incomplete bar — only act on fully closed daily bars
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    if len(closes) < 200:
        print("Insufficient data. Skipping.")
        return state

    latest_date = str(closes.index[-1].date())
    fee_total = CONFIG["fee_rate"] + CONFIG["slippage_bps"] / 10_000

    # Check if we have a new daily bar
    if latest_date == state.get("last_daily_date"):
        print(f"No new daily bar since {latest_date}.")
        _print_status(state, closes)
        return state

    print(f"New daily bar: {latest_date}")

    # Capital per pair (equal allocation)
    n_pairs = len(PAIRS)
    cap_per_pair = CONFIG["initial_capital"] / n_pairs

    # Process each pair
    session_trades = 0
    session_fees = 0.0

    for pair_name, sym_a, sym_b, z_window, entry_z, exit_z, stop_z in PAIRS:
        if sym_a not in closes.columns or sym_b not in closes.columns:
            print(f"  {pair_name}: missing data, skipping")
            continue

        # Compute log prices and hedge ratio
        log_a = np.log(closes[sym_a])
        log_b = np.log(closes[sym_b])

        # Use rolling hedge ratio (last hr_window days)
        hr_start = max(0, len(closes) - CONFIG["hr_window"])
        hr = compute_hedge_ratio(log_a.iloc[hr_start:], log_b.iloc[hr_start:])

        # Compute spread and z-score
        spread = log_a - hr * log_b
        roll_mean = spread.rolling(z_window).mean()
        roll_std = spread.rolling(z_window).std().replace(0, np.nan)
        zscore = (spread - roll_mean) / roll_std

        current_z = float(zscore.iloc[-1])
        if np.isnan(current_z):
            continue

        # Get current pair position
        pair_state = state["pair_positions"].get(pair_name, {
            "position": 0,  # 0=flat, 1=long spread, -1=short spread
            "entry_date": None,
            "entry_z": None,
            "entry_equity": cap_per_pair,
            "cumulative_pnl": 0.0,
        })

        pos = pair_state["position"]
        prev_date = state.get("last_daily_date")

        # Compute daily P&L for open positions
        if pos != 0 and prev_date is not None:
            prev_idx = closes.index.get_loc(pd.Timestamp(prev_date)) if pd.Timestamp(prev_date) in closes.index else None
            if prev_idx is not None:
                pa_now = closes[sym_a].iloc[-1]
                pb_now = closes[sym_b].iloc[-1]
                pa_prev = closes[sym_a].iloc[prev_idx]
                pb_prev = closes[sym_b].iloc[prev_idx]
                ret_a = (pa_now - pa_prev) / pa_prev
                ret_b = (pb_now - pb_prev) / pb_prev
                half = cap_per_pair * 0.5
                if pos == 1:  # long A, short B
                    daily_pnl = half * ret_a - half * ret_b
                else:  # short A, long B
                    daily_pnl = -half * ret_a + half * ret_b
                pair_state["cumulative_pnl"] = pair_state.get("cumulative_pnl", 0) + daily_pnl

        # Check exit signals
        if pos != 0:
            close_position = False
            reason = ""

            if pos == 1 and current_z > -exit_z:
                close_position = True
                reason = f"exit (z={current_z:.2f} > -{exit_z})"
            elif pos == -1 and current_z < exit_z:
                close_position = True
                reason = f"exit (z={current_z:.2f} < {exit_z})"
            elif pos == 1 and current_z < -stop_z:
                close_position = True
                reason = f"stop (z={current_z:.2f} < -{stop_z})"
            elif pos == -1 and current_z > stop_z:
                close_position = True
                reason = f"stop (z={current_z:.2f} > {stop_z})"

            if close_position:
                # Apply exit fees (both legs)
                exit_fee = cap_per_pair * fee_total * 2
                session_fees += exit_fee
                session_trades += 1

                pnl = pair_state.get("cumulative_pnl", 0) - exit_fee
                state["trades_log"].append({
                    "pair": pair_name,
                    "direction": "long_spread" if pos == 1 else "short_spread",
                    "entry_date": pair_state.get("entry_date"),
                    "exit_date": latest_date,
                    "entry_z": pair_state.get("entry_z"),
                    "exit_z": round(current_z, 3),
                    "pnl": round(pnl, 2),
                    "reason": reason,
                })

                log.append({
                    "type": "close",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "date": latest_date,
                    "pair": pair_name,
                    "direction": "long_spread" if pos == 1 else "short_spread",
                    "z": round(current_z, 3),
                    "pnl": round(pnl, 2),
                    "reason": reason,
                })

                print(f"  {pair_name}: CLOSE {'long' if pos==1 else 'short'} spread — "
                      f"{reason}, PnL ${pnl:+.2f}")

                pair_state = {
                    "position": 0,
                    "entry_date": None,
                    "entry_z": None,
                    "entry_equity": cap_per_pair,
                    "cumulative_pnl": 0.0,
                }

        # Check entry signals (only if flat)
        if pair_state["position"] == 0:
            new_pos = 0
            if current_z < -entry_z:
                new_pos = 1   # long spread (long A, short B)
            elif current_z > entry_z:
                new_pos = -1  # short spread (short A, long B)

            if new_pos != 0:
                entry_fee = cap_per_pair * fee_total * 2
                session_fees += entry_fee
                session_trades += 1

                pair_state = {
                    "position": new_pos,
                    "entry_date": latest_date,
                    "entry_z": round(current_z, 3),
                    "entry_equity": cap_per_pair,
                    "cumulative_pnl": -entry_fee,  # start with entry fee as cost
                }

                direction = "long" if new_pos == 1 else "short"
                log.append({
                    "type": "open",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "date": latest_date,
                    "pair": pair_name,
                    "direction": f"{direction}_spread",
                    "z": round(current_z, 3),
                    "hedge_ratio": round(hr, 4),
                })

                print(f"  {pair_name}: OPEN {direction} spread — z={current_z:.2f}, HR={hr:.4f}")

        state["pair_positions"][pair_name] = pair_state

    # Update totals
    state["total_trades"] += session_trades
    state["total_fees"] += session_fees

    # Compute portfolio equity
    mark_equity = _mark_equity(state)
    state["equity_history"].append({
        "date": latest_date,
        "equity": round(mark_equity, 2),
        "active_pairs": sum(1 for p in state["pair_positions"].values() if p.get("position", 0) != 0),
        "trades_today": session_trades,
    })
    state["last_daily_date"] = latest_date

    save_state(state)
    save_log(log)

    _print_status(state, closes)
    return state


def _mark_equity(state: dict) -> float:
    """Compute total equity from capital + all pair P&Ls."""
    base = CONFIG["initial_capital"]
    total_pnl = sum(
        p.get("cumulative_pnl", 0)
        for p in state["pair_positions"].values()
    )
    # Also add completed trade P&Ls
    completed_pnl = sum(t.get("pnl", 0) for t in state.get("trades_log", []))
    return base + total_pnl + completed_pnl


def _print_status(state: dict, closes: pd.DataFrame):
    initial = CONFIG["initial_capital"]
    mark = _mark_equity(state)
    ret = (mark / initial - 1)

    print(f"\nEquity: ${mark:,.2f} (start ${initial:,.2f})")
    print(f"Return: {ret:+.2%}")
    print(f"Total trades: {state['total_trades']}")
    print(f"Total fees: ${state['total_fees']:.2f}")

    # Active positions
    active = [(name, p) for name, p in state["pair_positions"].items()
              if p.get("position", 0) != 0]

    if active:
        print(f"\nActive positions ({len(active)}/{len(PAIRS)} pairs):")
        for name, p in active:
            direction = "LONG" if p["position"] == 1 else "SHORT"
            pnl = p.get("cumulative_pnl", 0)
            print(f"  {name:12s} {direction} spread  entry_z={p.get('entry_z', '?'):>6}  "
                  f"since {p.get('entry_date', '?')}  PnL=${pnl:+.2f}")
    else:
        print("\nAll pairs: FLAT (waiting for z-score entry signals)")

    # Completed trades summary
    trades = state.get("trades_log", [])
    if trades:
        wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
        total = len(trades)
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        print(f"\nCompleted: {total} trades, {wins}/{total} wins ({100*wins/total:.0f}%), "
              f"total PnL ${total_pnl:+.2f}")


def report():
    """Print performance summary."""
    state = load_state()
    if not state["equity_history"]:
        print("No equity history yet.")
        return

    eq_hist = pd.DataFrame(state["equity_history"])
    eq_hist["date"] = pd.to_datetime(eq_hist["date"])
    eq_hist = eq_hist.set_index("date")

    initial = CONFIG["initial_capital"]
    current = eq_hist["equity"].iloc[-1]
    days = (eq_hist.index[-1] - eq_hist.index[0]).days or 1

    print("=== H-032 Pairs Trading Performance Report ===")
    print(f"Period: {eq_hist.index[0].date()} to {eq_hist.index[-1].date()} ({days} days)")
    print(f"Capital: ${initial:,.2f} -> ${current:,.2f}")
    print(f"Return: {(current / initial - 1):+.2%}")
    if days > 1:
        print(f"Annualized: {((current / initial) ** (365 / days) - 1):+.2%}")

    peak = eq_hist["equity"].cummax()
    dd = (eq_hist["equity"] - peak) / peak
    print(f"Max drawdown: {dd.min():.2%}")
    print(f"Total trades: {state['total_trades']}")
    print(f"Total fees: ${state['total_fees']:.2f}")

    trades = state.get("trades_log", [])
    if trades:
        wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
        print(f"Win rate: {wins}/{len(trades)} ({100*wins/len(trades):.0f}%)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="H-032 Pairs Trading Paper Trade")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if args.report:
        report()
    else:
        run()
