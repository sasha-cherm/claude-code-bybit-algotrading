"""
H-496 Paper Trade Runner: ML Ensemble (Focused Equal-Weight 10-Factor Composite)

Market-neutral strategy: combine 10 confirmed XS factors via equal-weight z-score
averaging, long top 4, short bottom 4. Rebalance every 5 days.

Factors: momentum, low_vol, size, premium, vol_term, dd_momentum, efficiency,
         turnover, vol_surprise, vw_pressure.

Backtest: Sharpe 2.149, +98.7% annual, -23.8% DD. WF 5/6 positive, mean 2.189.
Split-half PASS (2.555/1.655). Param robustness 12/12 positive.
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
    "rebal_freq": 5,
    "n_long": 4,
    "n_short": 4,
    "initial_capital": 10_000.0,
    "fee_rate": 0.001,
    "slippage_bps": 2.0,
}

STATE_FILE = Path(__file__).parent / "state.json"
LOG_FILE = Path(__file__).parent / "log.json"


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


def xs_zscore(row):
    """Cross-sectional z-score."""
    vals = row.values.astype(float)
    mask = ~np.isnan(vals)
    if mask.sum() < 3:
        return pd.Series(0.0, index=row.index)
    mean = np.nanmean(vals)
    std = np.nanstd(vals)
    if std < 1e-12:
        return pd.Series(0.0, index=row.index)
    return (row - mean) / std


def compute_composite_signal(close, volume, high, low, opn):
    """Compute the 10-factor composite z-score for the latest bar."""
    rets = close.pct_change()
    dollar_vol = close * volume

    scores = pd.Series(0.0, index=close.columns)
    n_factors = 0

    # 1. Momentum (60d return)
    mom60 = close.iloc[-1] / close.iloc[-61] - 1 if len(close) > 61 else None
    if mom60 is not None:
        scores += xs_zscore(mom60)
        n_factors += 1

    # 2. Low-vol (inverse 20d vol)
    vol20 = rets.iloc[-20:].std()
    scores += xs_zscore(-vol20)
    n_factors += 1

    # 3. Size (30d avg dollar volume)
    dv30 = dollar_vol.iloc[-30:].mean()
    scores += xs_zscore(dv30)
    n_factors += 1

    # 4. Premium (contrarian: close vs 5d VWAP)
    vwap = (close.iloc[-5:] * volume.iloc[-5:]).sum() / volume.iloc[-5:].sum()
    premium = close.iloc[-1] / vwap - 1
    scores += xs_zscore(-premium)
    n_factors += 1

    # 5. Vol term (7d/30d vol ratio — expansion long)
    vol7 = rets.iloc[-7:].std()
    vol30 = rets.iloc[-30:].std()
    vol_term = vol7 / (vol30 + 1e-10)
    scores += xs_zscore(vol_term)
    n_factors += 1

    # 6. DD momentum (proximity to 60d high)
    if len(close) > 60:
        roll_max = close.iloc[-60:].max()
        dd_prox = close.iloc[-1] / roll_max
        scores += xs_zscore(dd_prox)
        n_factors += 1

    # 7. Efficiency (path efficiency over 40d)
    if len(close) > 40:
        net_ret = (close.iloc[-1] / close.iloc[-41] - 1).abs()
        sum_abs = rets.iloc[-40:].abs().sum()
        efficiency = net_ret / (sum_abs + 1e-10)
        scores += xs_zscore(efficiency)
        n_factors += 1

    # 8. Turnover (5d/20d dollar vol ratio)
    dv_short = dollar_vol.iloc[-5:].mean()
    dv_long = dollar_vol.iloc[-20:].mean()
    turnover = dv_short / (dv_long + 1e-10)
    scores += xs_zscore(turnover)
    n_factors += 1

    # 9. Volume surprise (latest vol / 20d avg)
    vol_sur = volume.iloc[-1] / volume.iloc[-20:].mean()
    scores += xs_zscore(vol_sur)
    n_factors += 1

    # 10. VW pressure (10d volume-weighted return)
    vw_ret = (rets.iloc[-10:] * volume.iloc[-10:]).sum() / volume.iloc[-10:].sum()
    scores += xs_zscore(vw_ret)
    n_factors += 1

    return scores / n_factors


def load_daily_data():
    """Fetch 1h data, resample to daily, return OHLCV DataFrames."""
    all_close, all_volume, all_high, all_low, all_open = {}, {}, {}, {}, {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=120)
            if len(df_1h) < 200:
                continue
            daily = resample_to_daily(df_1h)
            all_close[sym] = daily["close"]
            all_volume[sym] = daily["volume"]
            all_high[sym] = daily["high"]
            all_low[sym] = daily["low"]
            all_open[sym] = daily["open"]
        except Exception as e:
            print(f"  {sym}: failed to load: {e}")

    close = pd.DataFrame(all_close).dropna(how="all").ffill().dropna()
    volume = pd.DataFrame(all_volume).reindex(close.index).ffill().fillna(0)
    high = pd.DataFrame(all_high).reindex(close.index).ffill()
    low = pd.DataFrame(all_low).reindex(close.index).ffill()
    opn = pd.DataFrame(all_open).reindex(close.index).ffill()
    return close, volume, high, low, opn


def run():
    print("=== H-496 ML Ensemble Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    print("Fetching data for 14 assets...")
    close, volume, high, low, opn = load_daily_data()

    # Drop today's incomplete bar
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if len(close) > 0 and str(close.index[-1].date()) == today_utc:
        close = close.iloc[:-1]
        volume = volume.iloc[:len(close)]
        high = high.iloc[:len(close)]
        low = low.iloc[:len(close)]
        opn = opn.iloc[:len(close)]

    print(f"Loaded {len(close.columns)} assets, {len(close)} daily bars")

    if len(close.columns) < 7:
        print(f"WARNING: Only {len(close.columns)} assets, skipping")
        save_state(state)
        return state

    if len(close) < 70:
        print("Insufficient data. Skipping.")
        return state

    latest_date = str(close.index[-1].date())
    slippage = CONFIG["slippage_bps"] / 10_000

    if latest_date == state.get("last_daily_date"):
        print(f"No new daily bar since {latest_date}.")
        _print_status(state, close)
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

        composite = compute_composite_signal(close, volume, high, low, opn)
        ranked = composite.sort_values(ascending=False)
        longs = ranked.index[:CONFIG["n_long"]]
        shorts = ranked.index[-CONFIG["n_short"]:]

        new_weights = {}
        for sym in longs:
            new_weights[sym] = 1.0 / CONFIG["n_long"]
        for sym in shorts:
            new_weights[sym] = -1.0 / CONFIG["n_short"]

        current_prices = close.iloc[-1]
        old_positions = state["positions"]

        # MTM existing positions
        capital = state["capital"]
        for sym, pos in old_positions.items():
            if sym in current_prices.index:
                price_now = float(current_prices[sym])
                unrealized = pos["size"] * (price_now - pos["entry_price"])
                capital += unrealized

        # Compute fees on turnover
        total_fees = 0.0
        trades = 0
        for sym, pos in old_positions.items():
            if sym in current_prices.index:
                exit_price = float(current_prices[sym])
                direction = 1 if pos["weight"] > 0 else -1
                exit_price_adj = exit_price * (1 - direction * slippage)
                new_w = new_weights.get(sym, 0)
                if abs(new_w - pos["weight"]) > 0.01:
                    notional = abs(pos["size"]) * exit_price_adj
                    total_fees += CONFIG["fee_rate"] * notional
                    trades += 1

        for sym, weight in new_weights.items():
            if sym not in old_positions or abs(old_positions[sym]["weight"] - weight) > 0.01:
                price = float(current_prices[sym])
                direction = 1 if weight > 0 else -1
                entry_price = price * (1 + direction * slippage)
                notional = abs(weight) * capital
                total_fees += CONFIG["fee_rate"] * notional
                trades += 1

        capital -= total_fees

        # Open new positions
        new_positions = {}
        for sym, weight in new_weights.items():
            price = float(current_prices[sym])
            direction = 1 if weight > 0 else -1
            entry_price = price * (1 + direction * slippage)
            size = weight * capital / entry_price
            new_positions[sym] = {
                "weight": weight,
                "entry_price": entry_price,
                "size": size,
            }

        state["positions"] = new_positions
        state["capital"] = capital
        state["last_rebal_date"] = latest_date
        state["rebal_count"] += 1
        state["total_trades"] += trades
        state["total_fees"] += total_fees

        log.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "type": "rebalance",
            "date": latest_date,
            "capital": capital,
            "fees": total_fees,
            "trades": trades,
            "positions": {sym: {"weight": p["weight"], "price": p["entry_price"]}
                          for sym, p in new_positions.items()},
            "composite_scores": {sym: float(composite[sym]) for sym in composite.index},
        })

        print(f"  Rebalanced: {trades} trades, fees=${total_fees:.2f}")
        for sym, p in sorted(new_positions.items(), key=lambda x: -x[1]["weight"]):
            side = "LONG" if p["weight"] > 0 else "SHORT"
            print(f"    {side:5s} {sym:15s} w={p['weight']:+.3f}")

    state["last_daily_date"] = latest_date

    # MTM for equity tracking
    equity = state["capital"]
    current_prices = close.iloc[-1]
    for sym, pos in state["positions"].items():
        if sym in current_prices.index:
            price_now = float(current_prices[sym])
            equity += pos["size"] * (price_now - pos["entry_price"])

    state["equity"] = equity

    state["equity_history"].append({
        "time": datetime.now(timezone.utc).isoformat(),
        "date": latest_date,
        "equity": round(equity, 2),
    })

    # Keep last 100 equity snapshots
    if len(state["equity_history"]) > 100:
        state["equity_history"] = state["equity_history"][-100:]

    _print_status(state, close)

    save_state(state)
    save_log(log)
    return state


def _print_status(state, close):
    equity = state.get("equity", state["capital"])
    pnl_pct = (equity / CONFIG["initial_capital"] - 1) * 100
    print(f"\n  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    print(f"  Rebals: {state['rebal_count']}, Positions: {len(state['positions'])}")
    for sym, pos in sorted(state["positions"].items(), key=lambda x: -x[1]["weight"]):
        side = "LONG" if pos["weight"] > 0 else "SHORT"
        if sym in close.columns:
            price_now = float(close[sym].iloc[-1])
            pnl = pos["size"] * (price_now - pos["entry_price"])
            print(f"    {side:5s} {sym:15s} pnl=${pnl:+.2f}")
        else:
            print(f"    {side:5s} {sym:15s}")


if __name__ == "__main__":
    run()
