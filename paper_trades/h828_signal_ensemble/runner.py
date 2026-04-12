"""
H-828 Paper Trade Runner: Top-5 Signal Ensemble XS

Equal-weight z-score ensemble of 5 conceptually diverse signals:
1. Momentum (60d return), 2. Volume momentum (20d), 3. OI change (7d),
4. Inverse volatility (20d), 5. Dollar volume (30d avg).

Backtest: IS Sharpe 1.693, Ann +69.6%, WF 3/4. SH p=0.020.
H-012 corr -0.001. 100% param robust.
Best params: lb=40, R=3, N=4.
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
    "lookback": 40,
    "rebal_freq": 3,
    "n_long": 4,
    "n_short": 4,
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


def cross_sectional_zscore(series):
    """Z-score across assets for a single row (Series)."""
    mu = series.mean()
    sigma = series.std()
    if sigma == 0 or not np.isfinite(sigma):
        return series * 0
    return (series - mu) / sigma


def load_oi_daily():
    """Load OI data for all assets."""
    oi = {}
    for ticker in [a.split("/")[0] for a in ASSETS]:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_oi_daily.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            col = "openInterest" if "openInterest" in df.columns else df.columns[0]
            oi[f"{ticker}/USDT"] = df[col]
        except:
            pass
    return pd.DataFrame(oi).sort_index().dropna(how="all")


def compute_rankings(daily_dict):
    """Rank by ensemble of 5 diverse z-scored signals."""
    closes = pd.DataFrame({s: d["close"] for s, d in daily_dict.items()}).dropna(how="all").ffill().dropna()
    volumes = pd.DataFrame({s: d["volume"] * d["close"] for s, d in daily_dict.items()}).dropna(how="all").ffill().dropna()
    if len(closes) < 70:
        return {}

    # Load OI data
    oi_df = load_oi_daily()

    # 1. Momentum (60d)
    mom = closes.pct_change(60).iloc[-1].dropna()
    # 2. Volume momentum (20d)
    vol_mom = volumes.pct_change(20).iloc[-1].dropna()
    # 3. OI change (7d)
    oi_chg = oi_df.pct_change(7)
    if len(oi_chg) > 0:
        # Get latest that aligns with closes
        oi_latest = oi_chg.iloc[-1].dropna()
    else:
        oi_latest = pd.Series(dtype=float)
    # 4. Inverse vol (20d)
    ret = closes.pct_change()
    vol = ret.rolling(20).std().iloc[-1].dropna()
    inv_vol = -vol  # negative = low vol is good
    # 5. Dollar volume (30d avg)
    dv = volumes.rolling(30).mean().iloc[-1].dropna()

    # Align all signals
    common = mom.index.intersection(vol_mom.index).intersection(inv_vol.index).intersection(dv.index)
    if len(oi_latest) > 0:
        common = common.intersection(oi_latest.index)

    if len(common) < CONFIG["n_long"] + CONFIG["n_short"]:
        return {}

    z1 = cross_sectional_zscore(mom[common])
    z2 = cross_sectional_zscore(vol_mom[common])
    z4 = cross_sectional_zscore(inv_vol[common])
    z5 = cross_sectional_zscore(dv[common])

    if len(oi_latest) > 0 and len(common) > 0:
        z3 = cross_sectional_zscore(oi_latest[common])
        composite = (z1 + z2 + z3 + z4 + z5) / 5
    else:
        composite = (z1 + z2 + z4 + z5) / 4

    composite = composite.dropna()
    n_required = CONFIG["n_long"] + CONFIG["n_short"]
    if len(composite) < n_required:
        return {}

    ranked = composite.sort_values(ascending=False)
    longs = ranked.index[:CONFIG["n_long"]]
    shorts = ranked.index[-CONFIG["n_short"]:]

    weights = {}
    for sym in longs:
        weights[sym] = 1.0 / CONFIG["n_long"]
    for sym in shorts:
        weights[sym] = -1.0 / CONFIG["n_short"]
    return weights


def run():
    print("=== H-828 Top-5 Signal Ensemble Paper Trade Runner ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state = load_state()
    log = load_log()

    daily_dict = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=120)
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
            new_weights = compute_rankings(daily_dict)
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
