"""
Portfolio Monitor — Combined view of all paper trade strategies.

Reads state from each paper trade runner and computes portfolio-level
metrics with the target allocation:
  10% H-009 / 40% H-011 / 10% H-012 / 15% H-019 / 25% H-021

Usage:
    python3 scripts/portfolio_monitor.py
    python3 scripts/portfolio_monitor.py --detailed
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# Target portfolio allocation
ALLOCATION = {
    "H-009": 0.10,  # BTC daily EMA trend
    "H-011": 0.40,  # Funding rate arb
    "H-012": 0.10,  # Cross-sectional momentum
    "H-019": 0.15,  # Low-volatility anomaly
    "H-021": 0.25,  # Volume momentum
}

INITIAL_PORTFOLIO = 50_000  # $10k per strategy = $50k total

# State file paths
STATE_FILES = {
    "H-009": ROOT / "paper_trades" / "h009_btc_daily_trend" / "state.json",
    "H-011": ROOT / "paper_trades" / "h011_funding_rate_arb" / "state.json",
    "H-012": ROOT / "paper_trades" / "h012_xsmom" / "state.json",
    "H-019": ROOT / "paper_trades" / "h019_lowvol" / "state.json",
    "H-021": ROOT / "paper_trades" / "h021_volmom" / "state.json",
    "H-024": ROOT / "paper_trades" / "h024_beta" / "state.json",
    "H-031": ROOT / "paper_trades" / "h031_size" / "state.json",
    "H-032": ROOT / "paper_trades" / "h032_pairs" / "state.json",
    "H-039": ROOT / "paper_trades" / "h039_dow_seasonality" / "state.json",
    "H-044": ROOT / "paper_trades" / "h044_oi_divergence" / "state.json",
}


def load_strategy_state(name: str) -> dict | None:
    path = STATE_FILES.get(name)
    if path is None or not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


PRICE_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]


def fetch_current_prices() -> dict:
    """Fetch current prices for all relevant assets."""
    try:
        import ccxt
        exchange = ccxt.bybit({"enableRateLimit": True})
        exchange.load_markets()
        prices = {}
        for sym in PRICE_SYMBOLS:
            try:
                t = exchange.fetch_ticker(sym)
                if t and t.get("last"):
                    prices[sym] = t["last"]
            except Exception:
                pass
        return prices
    except Exception as e:
        print(f"  Warning: could not fetch live prices: {e}")
        return {}


def get_strategy_equity(name: str, state: dict, prices: dict | None = None) -> float:
    """Get current mark-to-market equity for a strategy."""
    if name == "H-011":
        return state.get("capital", 10_000)

    if name == "H-009":
        capital = state.get("capital", 10_000)
        pos = state.get("position", 0)
        if pos != 0 and prices:
            price = prices.get("BTC/USDT", state.get("entry_price", 0))
            unrealized = pos * state.get("size_btc", 0) * (price - state.get("entry_price", 0))
            return capital + unrealized
        return capital

    if name == "H-039":
        capital = state.get("capital", 10_000)
        pos = state.get("position", 0)
        if pos != 0 and prices:
            price = prices.get("BTC/USDT", state.get("entry_price", 0))
            unrealized = pos * state.get("size_btc", 0) * (price - state.get("entry_price", 0))
            return capital + unrealized
        return capital

    if name in ("H-012", "H-019", "H-021", "H-024", "H-031", "H-044"):
        capital = state.get("capital", 10_000)
        positions = state.get("positions", {})
        if positions and prices:
            unrealized = 0
            for sym, pos in positions.items():
                price = prices.get(sym, pos.get("entry_price", 0))
                unrealized += pos["size"] * (price - pos["entry_price"])
            return capital + unrealized
        # Fall back to last equity history
        eq_hist = state.get("equity_history", [])
        if eq_hist:
            return eq_hist[-1].get("equity", capital)
        return capital

    return 10_000


def run(detailed: bool = False):
    now = datetime.now(timezone.utc)
    print(f"{'='*60}")
    print(f"  PORTFOLIO MONITOR — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")
    print()

    total_equity = 0
    strategy_data = {}

    # Fetch live prices for mark-to-market
    print("  Fetching live prices...")
    prices = fetch_current_prices()
    if prices:
        btc_price = prices.get("BTC/USDT", 0)
        print(f"  BTC/USDT: ${btc_price:,.2f}")
    print()

    for name in ["H-009", "H-011", "H-012", "H-019", "H-021", "H-024", "H-039", "H-044"]:
        state = load_strategy_state(name)
        if state is None:
            continue

        equity = get_strategy_equity(name, state, prices)
        initial = 10_000
        ret_pct = (equity / initial - 1) * 100
        if name in ALLOCATION:
            total_equity += equity

        strategy_data[name] = {
            "equity": equity,
            "return_pct": ret_pct,
            "state": state,
        }

    portfolio_return = (total_equity / INITIAL_PORTFOLIO - 1) * 100

    # Strategy summary table
    print("  Strategy Performance (equal $10k each)")
    print(f"  {'Strategy':<12} {'Equity':>10} {'Return':>8} {'Alloc':>6} {'Weighted':>9}")
    print(f"  {'-'*12} {'-'*10} {'-'*8} {'-'*6} {'-'*9}")

    weighted_return = 0
    for name, alloc in ALLOCATION.items():
        if name not in strategy_data:
            continue
        d = strategy_data[name]
        w_ret = d["return_pct"] * alloc
        weighted_return += w_ret
        print(f"  {name:<12} ${d['equity']:>9,.2f} {d['return_pct']:>+7.2f}% {alloc:>5.0%} {w_ret:>+8.3f}%")

    print(f"  {'-'*12} {'-'*10} {'-'*8} {'-'*6} {'-'*9}")
    print(f"  {'Portfolio':<12} ${total_equity:>9,.2f} {portfolio_return:>+7.2f}%        {weighted_return:>+8.3f}%")

    # Show comparison strategy (H-024) if available
    if "H-024" in strategy_data:
        d024 = strategy_data["H-024"]
        print(f"\n  Comparison: H-024 (beta) ${d024['equity']:>9,.2f} {d024['return_pct']:>+7.2f}% "
              f"  (candidate to replace H-019)")
    print()

    # Position summary
    print("  Active Positions")
    print(f"  {'-'*55}")

    # H-009
    if "H-009" in strategy_data:
        s = strategy_data["H-009"]["state"]
        pos = s.get("position", 0)
        if pos != 0:
            direction = "LONG" if pos == 1 else "SHORT"
            print(f"  H-009: {direction} {s.get('size_btc', 0):.6f} BTC "
                  f"@ ${s.get('entry_price', 0):,.2f} ({s.get('leverage', 0):.2f}x)")
        else:
            print(f"  H-009: FLAT")

    # H-011
    if "H-011" in strategy_data:
        s = strategy_data["H-011"]["state"]
        status = "IN (delta-neutral)" if s.get("in_position") else "OUT"
        print(f"  H-011: {status} | Funding collected: ${s.get('total_funding_collected', 0):.2f} "
              f"| Paid: ${s.get('total_funding_paid', 0):.2f}")

    # H-012
    if "H-012" in strategy_data:
        s = strategy_data["H-012"]["state"]
        positions = s.get("positions", {})
        if positions:
            longs = [sym.replace("/USDT", "") for sym, p in positions.items() if p["weight"] > 0]
            shorts = [sym.replace("/USDT", "") for sym, p in positions.items() if p["weight"] < 0]
            print(f"  H-012: L {'/'.join(longs)} | S {'/'.join(shorts)}")
            print(f"         Rebal {s.get('rebal_count', 0)}, next in "
                  f"{5 - s.get('days_since_rebal', 0)}d")
        else:
            print(f"  H-012: FLAT")

    # H-019
    if "H-019" in strategy_data:
        s = strategy_data["H-019"]["state"]
        positions = s.get("positions", {})
        if positions:
            longs = [sym.replace("/USDT", "") for sym, p in positions.items() if p["weight"] > 0]
            shorts = [sym.replace("/USDT", "") for sym, p in positions.items() if p["weight"] < 0]
            print(f"  H-019: L {'/'.join(longs)} | S {'/'.join(shorts)}")
            print(f"         Rebal {s.get('rebal_count', 0)}, next in "
                  f"{21 - s.get('days_since_rebal', 0)}d")
        else:
            print(f"  H-019: FLAT")

    # H-021
    if "H-021" in strategy_data:
        s = strategy_data["H-021"]["state"]
        positions = s.get("positions", {})
        if positions:
            longs = [sym.replace("/USDT", "") for sym, p in positions.items() if p["weight"] > 0]
            shorts = [sym.replace("/USDT", "") for sym, p in positions.items() if p["weight"] < 0]
            print(f"  H-021: L {'/'.join(longs)} | S {'/'.join(shorts)}")
            print(f"         Rebal {s.get('rebal_count', 0)}, next in "
                  f"{3 - s.get('days_since_rebal', 0)}d")
        else:
            print(f"  H-021: FLAT")

    # H-024 (comparison)
    if "H-024" in strategy_data:
        s = strategy_data["H-024"]["state"]
        positions = s.get("positions", {})
        if positions:
            longs = [sym.replace("/USDT", "") for sym, p in positions.items() if p["weight"] > 0]
            shorts = [sym.replace("/USDT", "") for sym, p in positions.items() if p["weight"] < 0]
            print(f"  H-024: L {'/'.join(longs)} | S {'/'.join(shorts)} (comparison)")
            print(f"         Rebal {s.get('rebal_count', 0)}, next in "
                  f"{21 - s.get('days_since_rebal', 0)}d")

    # H-039
    if "H-039" in strategy_data:
        s = strategy_data["H-039"]["state"]
        pos = s.get("position", 0)
        d039 = strategy_data["H-039"]
        if pos != 0:
            direction = "LONG" if pos == 1 else "SHORT"
            print(f"  H-039: {direction} {s.get('size_btc', 0):.6f} BTC "
                  f"@ ${s.get('entry_price', 0):,.2f} (DOW seasonality)")
        else:
            print(f"  H-039: FLAT (DOW) | ${d039['equity']:>9,.2f} {d039['return_pct']:>+.2f}%")

    # H-044
    if "H-044" in strategy_data:
        s = strategy_data["H-044"]["state"]
        d044 = strategy_data["H-044"]
        positions = s.get("positions", {})
        if positions:
            longs = [sym.replace("/USDT", "") for sym, p in positions.items() if p["weight"] > 0]
            shorts = [sym.replace("/USDT", "") for sym, p in positions.items() if p["weight"] < 0]
            print(f"  H-044: L {'/'.join(longs)} | S {'/'.join(shorts)} (OI divergence)")
            print(f"         ${d044['equity']:>9,.2f} {d044['return_pct']:>+.2f}% | "
                  f"Rebal {s.get('rebal_count', 0)}, next in "
                  f"{10 - s.get('days_since_rebal', 0)}d")
        else:
            print(f"  H-044: FLAT (OI divergence) | ${d044['equity']:>9,.2f} {d044['return_pct']:>+.2f}%")

    print()

    # Risk metrics
    print("  Risk Status")
    print(f"  {'-'*55}")

    # Check funding rate regime
    funding_cache = ROOT / "data" / "BTC_USDT_funding_rates.parquet"
    if funding_cache.exists():
        fdf = pd.read_parquet(funding_cache)
        fdf["timestamp"] = pd.to_datetime(fdf["timestamp"])
        fdf = fdf.set_index("timestamp").sort_index()
        recent_7d = fdf["fundingRate"].tail(21).mean()  # 21 = 7 days * 3 per day
        recent_30d = fdf["fundingRate"].tail(90).mean()
        ann_7d = recent_7d * 3 * 365 * 100
        ann_30d = recent_30d * 3 * 365 * 100
        rolling_27 = fdf["fundingRate"].rolling(27).mean().iloc[-1]

        regime = "POSITIVE" if rolling_27 > 0 else "NEGATIVE"
        print(f"  Funding rate: 7d avg {ann_7d:+.1f}% ann | 30d avg {ann_30d:+.1f}% ann | filter: {regime}")

    # Days since start
    start_date = pd.Timestamp("2026-03-16")
    days_active = (pd.Timestamp(now.date()) - start_date).days
    print(f"  Paper trade age: {days_active} day(s) / 28 required")
    print(f"  Next milestone: {28 - days_active} days until live consideration")

    print()

    if detailed:
        _print_detailed(strategy_data)

    return {
        "total_equity": total_equity,
        "portfolio_return_pct": portfolio_return,
        "weighted_return_pct": weighted_return,
        "strategy_data": strategy_data,
    }


def _print_detailed(strategy_data: dict):
    """Print detailed equity history for each strategy."""
    print("  Equity History")
    print(f"  {'-'*55}")

    for name in ["H-009", "H-011", "H-012", "H-019", "H-021", "H-024"]:
        if name not in strategy_data:
            continue
        eq_hist = strategy_data[name]["state"].get("equity_history", [])
        if not eq_hist:
            continue
        print(f"\n  {name}:")
        for snap in eq_hist[-10:]:  # last 10 entries
            date = snap.get("date", "?")
            equity = snap.get("equity", 0)
            print(f"    {date}: ${equity:,.2f}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Portfolio Monitor")
    parser.add_argument("--detailed", action="store_true")
    args = parser.parse_args()
    run(detailed=args.detailed)
