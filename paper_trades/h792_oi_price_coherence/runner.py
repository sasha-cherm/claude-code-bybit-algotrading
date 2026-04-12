"""
H-792 Paper Trade Runner: OI-Price Coherence XS

Rolling correlation between OI changes and price changes.
High coherence = trending with conviction, low coherence = divergence.

Backtest: IS Sharpe 1.839, Ann +88.8%, WF 5/6. SH p=0.005.
H-012 corr -0.097. 100% param robust.
Best params: lb=7 (lookback for rolling corr), R=7, N=3.
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
    "corr_lookback": 7,
    "rebal_freq": 7,
    "n_long": 3,
    "n_short": 3,
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,
    "slippage_bps": 2.0,
}

STATE_FILE = Path(__file__).parent / "state.json"
LOG_FILE = Path(__file__).parent / "log.json"
DATA_DIR = ROOT / "data"


def load_state():
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


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def load_log():
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            return json.load(f)
    return []


def save_log(log):
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, default=str)


def load_oi():
    oi = {}
    for ticker in ["BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX", "LINK", "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM"]:
        try:
            fp = DATA_DIR / f"{ticker}_USDT_oi_daily.parquet"
            if not fp.exists():
                fp = DATA_DIR / f"oi/{ticker}_oi_1d.parquet"
            if not fp.exists():
                continue
            df = pd.read_parquet(fp)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            col = "openInterest" if "openInterest" in df.columns else ("oi" if "oi" in df.columns else df.columns[0])
            oi[f"{ticker}/USDT"] = df[col].astype(float)
        except:
            pass
    return pd.DataFrame(oi).sort_index().dropna(how="all") if oi else pd.DataFrame()


def compute_rankings(daily_dict, oi_df):
    """Rank assets by OI-Price coherence (rolling correlation)."""
    lb = CONFIG["corr_lookback"]
    scores = {}

    for sym, daily in daily_dict.items():
        if len(daily) < lb + 5:
            continue
        c = daily["close"]
        # Normalize timezone for alignment
        if c.index.tz is not None:
            c = c.copy()
            c.index = c.index.tz_localize(None)
        price_rets = c.pct_change().dropna()

        if sym not in oi_df.columns:
            continue
        oi_series = oi_df[sym].dropna()
        if len(oi_series) < lb + 5:
            continue

        # Align OI with price dates
        common_idx = price_rets.index.intersection(oi_series.index)
        if len(common_idx) < lb + 1:
            continue

        oi_change = oi_series.reindex(common_idx).pct_change().dropna()
        pr = price_rets.reindex(oi_change.index).dropna()

        common = pr.index.intersection(oi_change.index)
        if len(common) < lb:
            continue

        pr_vals = pr.reindex(common).iloc[-lb:].values
        oi_vals = oi_change.reindex(common).iloc[-lb:].values

        mask = ~(np.isnan(pr_vals) | np.isnan(oi_vals))
        if mask.sum() < 4:
            continue

        corr = np.corrcoef(pr_vals[mask], oi_vals[mask])[0, 1]
        if np.isfinite(corr):
            scores[sym] = corr  # high coherence = trending

    n_required = CONFIG["n_long"] + CONFIG["n_short"]
    if len(scores) < n_required:
        return {}

    ranked = pd.Series(scores).sort_values(ascending=False)
    longs = ranked.index[:CONFIG["n_long"]]
    shorts = ranked.index[-CONFIG["n_short"]:]

    weights = {}
    for sym in longs:
        weights[sym] = 1.0 / CONFIG["n_long"]
    for sym in shorts:
        weights[sym] = -1.0 / CONFIG["n_short"]
    return weights


def run():
    print("=== H-792 OI-Price Coherence Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()
    oi_df = load_oi()
    print(f"OI data: {len(oi_df)} rows, {len(oi_df.columns)} assets" if len(oi_df) > 0 else "No OI data")

    daily_dict = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=60)
            if len(df) < 200:
                continue
            from strategies.daily_trend_multi_asset.strategy import resample_to_daily
            daily = resample_to_daily(df)
            daily_dict[sym] = daily
        except Exception as e:
            print(f"  {sym}: {e}")

    print(f"Loaded {len(daily_dict)} assets")
    if len(daily_dict) < 8:
        save_state(state)
        return state

    closes = pd.DataFrame({s: d["close"] for s, d in daily_dict.items()}).dropna(how="all").ffill().dropna()
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(closes) > 0 and str(closes.index[-1].date()) == today_utc:
        closes = closes.iloc[:-1]

    latest_date = str(closes.index[-1].date())
    slippage = CONFIG["slippage_bps"] / 10_000

    if latest_date == state.get("last_daily_date"):
        print(f"No new daily bar since {latest_date}.")
    else:
        print(f"New daily bar: {latest_date}")
        if state["last_rebal_date"] is None:
            days_since = CONFIG["rebal_freq"]
        else:
            days_since = (pd.Timestamp(latest_date) - pd.Timestamp(state["last_rebal_date"])).days
        state["days_since_rebal"] = days_since

        if days_since >= CONFIG["rebal_freq"]:
            new_weights = compute_rankings(daily_dict, oi_df)
            if new_weights:
                current_prices = closes.iloc[-1]
                old_positions = state["positions"]
                total_fees = 0.0
                trades = 0
                capital = state["capital"]
                for sym, pos in old_positions.items():
                    if sym in current_prices.index:
                        capital += pos["size"] * (float(current_prices[sym]) - pos["entry_price"])
                for sym, pos in old_positions.items():
                    if sym in current_prices.index:
                        new_w = new_weights.get(sym, 0)
                        if abs(new_w - pos["weight"]) > 0.01:
                            total_fees += CONFIG["fee_rate"] * abs(pos["size"]) * float(current_prices[sym])
                            trades += 1
                new_positions = {}
                for sym, weight in new_weights.items():
                    if sym not in current_prices.index:
                        continue
                    price = float(current_prices[sym])
                    direction = 1 if weight > 0 else -1
                    entry_price = price * (1 + direction * slippage)
                    alloc = capital * abs(weight)
                    size = alloc / entry_price * direction
                    if sym not in old_positions or abs(new_weights.get(sym, 0) - old_positions.get(sym, {}).get("weight", 0)) > 0.01:
                        total_fees += CONFIG["fee_rate"] * abs(size) * entry_price
                        trades += 1
                    new_positions[sym] = {"size": size, "entry_price": entry_price, "weight": weight, "symbol": sym}
                capital -= total_fees
                state["capital"] = capital
                state["positions"] = new_positions
                state["total_fees"] += total_fees
                state["total_trades"] += trades
                state["rebal_count"] += 1
                state["last_rebal_date"] = latest_date
                log.append({"time": datetime.now(timezone.utc).isoformat(), "action": "rebalance", "date": latest_date,
                            "longs": [s for s, p in new_positions.items() if p["weight"] > 0],
                            "shorts": [s for s, p in new_positions.items() if p["weight"] < 0],
                            "capital": round(capital, 2), "fees": round(total_fees, 4), "trades": trades})
                save_log(log)
                print(f"  LONG:  {log[-1]['longs']}")
                print(f"  SHORT: {log[-1]['shorts']}")
        else:
            print(f"Hold (day {days_since}/{CONFIG['rebal_freq']})")
        state["last_daily_date"] = latest_date

    equity = state["capital"]
    if state["positions"]:
        current_prices = closes.iloc[-1]
        for sym, pos in state["positions"].items():
            if sym in current_prices.index:
                equity += pos["size"] * (float(current_prices[sym]) - pos["entry_price"])
    state["equity"] = equity
    state["equity_history"].append({"date": latest_date, "equity": round(equity, 2)})
    save_state(state)
    pnl_pct = (equity / CONFIG["initial_capital"] - 1) * 100
    print(f"\n  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    return state


if __name__ == "__main__":
    run()
