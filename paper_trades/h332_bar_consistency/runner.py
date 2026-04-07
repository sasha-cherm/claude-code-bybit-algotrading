"""
H-332 Paper Trade Runner: Bar Consistency Score (4h Microstructure)

Market-neutral strategy: rank 14 crypto assets by intraday bar consistency
(fraction of 4h bars closing in the majority direction) averaged over lookback.
High consistency = clean intraday momentum across all sessions → long.
Low consistency = choppy, mixed sessions → short.

Backtest: IS 100% high_long (24/24). Best LB10_R3_N3_high_long Sharpe 2.437
(WF 6/6 mean 1.961). Split-half H1=2.337, H2=2.587.
Corr H-012 0.147, H-076 0.111 — genuinely novel 4h microstructure signal.
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
    "lookback": 10,
    "rebal_freq": 3,
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
    """Load daily close data for all assets."""
    closes_dict = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1d", limit_days=120)
            if len(df) < 50:
                continue
            dc = df["close"].copy()
            if dc.index.tzinfo is not None:
                dc.index = dc.index.tz_localize(None)
            closes_dict[sym] = dc
        except Exception as e:
            print(f"  {sym}: failed: {e}")
    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    return closes


def compute_4h_features():
    """Compute 4h bar consistency features from hourly data."""
    features = {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=60)
            if len(df_1h) < 100:
                continue
            # Resample to 4h
            df_4h = df_1h.resample("4h").agg({
                "open": "first", "high": "max", "low": "min",
                "close": "last", "volume": "sum"
            }).dropna()

            df_4h["bar_return"] = df_4h["close"] / df_4h["open"] - 1
            df_4h["bar_direction"] = np.sign(df_4h["bar_return"])
            df_4h["date"] = df_4h.index.date

            daily_consistency = []
            for date, group in df_4h.groupby("date"):
                if len(group) < 4:
                    continue
                dirs = group["bar_direction"].values
                n_pos = (dirs > 0).sum()
                n_neg = (dirs < 0).sum()
                n_total = len(dirs)
                majority_frac = max(n_pos, n_neg) / n_total if n_total > 0 else 0.5
                consistency = majority_frac if n_pos >= n_neg else -majority_frac
                daily_consistency.append({"date": pd.Timestamp(date), "consistency": consistency})

            if daily_consistency:
                feat_df = pd.DataFrame(daily_consistency).set_index("date")
                feat_df.index = feat_df.index.tz_localize(None)
                features[sym] = feat_df
        except Exception as e:
            print(f"  {sym} 4h features: {e}")
    return features


def compute_rankings(closes: pd.DataFrame, features_4h: dict, date_idx: int) -> dict:
    """
    Rank assets by bar consistency score (avg over lookback days).
    High consistency -> long (high_long direction).
    """
    lookback = CONFIG["lookback"]
    if date_idx < lookback + 5:
        return {}

    end_date = closes.index[date_idx]
    start_date = closes.index[max(0, date_idx - lookback)]

    scores = {}
    for sym in closes.columns:
        if sym not in features_4h:
            continue
        feat = features_4h[sym]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "consistency"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score

    valid = pd.Series(scores)
    n_long = CONFIG["n_long"]
    n_short = CONFIG["n_short"]

    if len(valid) < n_long + n_short:
        return {}

    # High consistency -> long
    ranked = valid.sort_values(ascending=False)
    longs = ranked.index[:n_long]
    shorts = ranked.index[-n_short:]

    weights = {}
    for sym in longs:
        weights[sym] = 1.0 / n_long
    for sym in shorts:
        weights[sym] = -1.0 / n_short
    return weights


def run():
    print("=== H-332 Bar Consistency Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching daily data for 14 assets...")
    closes = load_data()

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    if len(closes.columns) < 7:
        print(f"WARNING: Only {len(closes.columns)} of 14 assets loaded, skipping")
        save_state(state)
        return state

    if len(closes) < CONFIG["lookback"] + 5:
        print("Insufficient data. Skipping.")
        return state

    latest_date = str(closes.index[-1].date())
    slippage = CONFIG["slippage_bps"] / 10_000

    if latest_date == state.get("last_daily_date"):
        print(f"No new daily bar since {latest_date}.")
        _print_status(state, closes)
        return state

    print(f"New daily bar: {latest_date}")

    # Compute 4h features
    print("Computing 4h bar consistency features...")
    features_4h = compute_4h_features()
    print(f"  4h features for {len(features_4h)} assets")

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

        new_weights = compute_rankings(closes, features_4h, date_idx)
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

            n_min = CONFIG["n_long"] + CONFIG["n_short"]
            if len(new_positions) < n_min:
                print(f"  WARNING: Only {len(new_positions)}/{n_min} positions, aborting")
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

            log.append({
                "date": latest_date,
                "action": "rebalance",
                "capital": state["capital"],
                "positions": {s: p["direction"] for s, p in new_positions.items()},
                "trades": trades_this_rebal,
                "fees": round(total_fees, 2),
            })
            print(f"  Trades: {trades_this_rebal}, Fees: ${total_fees:.2f}")

    # MTM update
    current_prices = closes.iloc[-1]
    equity = state["capital"]
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

    # Keep equity history manageable
    if len(state["equity_history"]) > 500:
        state["equity_history"] = state["equity_history"][-250:]

    save_state(state)
    save_log(log)
    _print_status(state, closes)
    return state


def _print_status(state, closes):
    capital = state["capital"]
    initial = CONFIG["initial_capital"]
    equity = state.get("equity", capital)
    pct = (equity / initial - 1) * 100
    print(f"\n  Capital: ${capital:,.2f}")
    print(f"  Equity:  ${equity:,.2f} ({pct:+.2f}%)")
    print(f"  Rebals:  {state.get('rebal_count', 0)}")
    positions = state.get("positions", {})
    print(f"  Positions: {len(positions)}")
    current_prices = closes.iloc[-1] if len(closes) > 0 else pd.Series()
    for sym in sorted(positions.keys()):
        pos = positions[sym]
        pnl = 0
        if sym in current_prices.index:
            pnl = pos["size"] * (float(current_prices[sym]) - pos["entry_price"])
        print(f"    {pos['direction']:5s} {sym:15s} pnl=${pnl:+.2f}")


if __name__ == "__main__":
    state = run()
