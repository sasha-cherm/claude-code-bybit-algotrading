"""
Demo Portfolio Runner — H-055 Optimal Allocation

Reads current signals from all H-055 strategy state.json files,
computes net target positions per symbol using H-055 portfolio weights,
and executes rebalancing orders on the Bybit demo account.

Run AFTER individual runners (so their signals are fresh):
    1. run_all_paper_trades.py  → updates all state.json signal files
    2. demo_portfolio_runner.py → reads signals, executes on Bybit demo

Architecture:
  - Individual runners continue computing signals + tracking internal P&L
  - This runner handles REAL execution (Bybit demo account)
  - Positions are netted across strategies per symbol to avoid conflicts
  - H-011 (delta-neutral, 40%): spot BTC long (~$33k) + perp BTC short (~$33k at 5x)
    managed here — spot via handle_h011_spot(), perp via extract_target_notionals()

H-055 allocation: H-009(12%) H-011(40%,spot+perp@5x) H-021(7%) H-031(13%)
                  H-039(9%) H-046(5%) H-052(8%) H-053(6%)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.bybit_demo_client import DemoTrader

# ── Portfolio Configuration ───────────────────────────────────────────────

TOTAL_CAPITAL = 100_000.0   # Demo account target capital (USDT)
REBAL_LEVERAGE = 2          # Bybit leverage for all positions
REBAL_THRESHOLD = 0.10      # Rebalance only if drift > 10% of target notional

# H-055 strategy allocations (H-011 handled separately — spot + perp legs)
H055_WEIGHTS: dict[str, float] = {
    "h009": 0.12,   # BTC daily trend (vol-targeted)
    "h021": 0.07,   # Volume momentum XS
    "h031": 0.13,   # Size factor XS
    "h039": 0.09,   # Day-of-week seasonality (BTC)
    "h046": 0.05,   # Price acceleration XS
    "h052": 0.08,   # Premium index XS
    "h053": 0.06,   # Funding rate XS contrarian
    # h011: 0.40 — managed separately via handle_h011_spot() + perp in extract_target_notionals()
}

# H-011 constants
H011_WEIGHT    = 0.40
H011_LEVERAGE  = 5.0
H011_DIR       = "h011_funding_rate_arb"
H011_SYMBOL    = "BTCUSDT"  # same symbol for spot and perp

# Map strategy key → paper_trades directory name
STRATEGY_DIRS: dict[str, str] = {
    "h009": "h009_btc_daily_trend",
    "h021": "h021_volmom",
    "h031": "h031_size",
    "h039": "h039_dow_seasonality",
    "h046": "h046_acceleration",
    "h052": "h052_premium",
    "h053": "h053_funding_xs",
}

PAPER_DIR = ROOT / "paper_trades"
STATE_FILE = ROOT / "scripts" / "demo_portfolio_state.json"
LOG_FILE = ROOT / "logs" / "demo_portfolio.log"

# Bybit linear perp min order quantities (base currency)
MIN_QTY: dict[str, float] = {
    "BTCUSDT":  0.001,
    "ETHUSDT":  0.01,
    "SOLUSDT":  0.1,
    "SUIUSDT":  1.0,
    "XRPUSDT":  1.0,
    "DOGEUSDT": 1.0,
    "AVAXUSDT": 0.1,
    "LINKUSDT": 0.1,
    "ADAUSDT":  1.0,
    "DOTUSDT":  0.1,
    "NEARUSDT": 0.1,
    "OPUSDT":   0.1,
    "ARBUSDT":  1.0,
    "ATOMUSDT": 0.1,
}

# Qty decimal places matching step size
QTY_DECIMALS: dict[str, int] = {
    "BTCUSDT":  3,
    "ETHUSDT":  2,
    "SOLUSDT":  1,
    "SUIUSDT":  0,
    "XRPUSDT":  0,
    "DOGEUSDT": 0,
    "AVAXUSDT": 1,
    "LINKUSDT": 1,
    "ADAUSDT":  0,
    "DOTUSDT":  1,
    "NEARUSDT": 1,
    "OPUSDT":   1,
    "ARBUSDT":  0,
    "ATOMUSDT": 1,
}


# ── Helpers ───────────────────────────────────────────────────────────────

def sym_to_bybit(sym: str) -> str:
    """Convert 'BTC/USDT' → 'BTCUSDT'."""
    return sym.replace("/", "").replace("_", "")


def round_qty(symbol: str, qty: float) -> float:
    decimals = QTY_DECIMALS.get(symbol, 1)
    return round(qty, decimals)


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ── Signal Extraction ─────────────────────────────────────────────────────

def load_strategy_state(strat_key: str) -> dict:
    dir_name = STRATEGY_DIRS[strat_key]
    path = PAPER_DIR / dir_name / "state.json"
    if not path.exists():
        log(f"  WARNING: {path} not found")
        return {}
    with open(path) as f:
        return json.load(f)


def extract_target_notionals() -> dict[str, float]:
    """
    Read all strategy states and compute target notional per Bybit symbol.

    Returns {bybit_symbol: usdt_notional}
      positive = long, negative = short
    """
    target: dict[str, float] = {}

    for strat, h055_weight in H055_WEIGHTS.items():
        strat_capital = h055_weight * TOTAL_CAPITAL
        state = load_strategy_state(strat)
        if not state:
            continue

        if strat in ("h009", "h039"):
            # BTC directional: position ∈ {-1, 0, 1}
            direction = state.get("position", 0)
            if direction == 0:
                continue
            # H-009 uses vol-targeted leverage; H-039 uses 1.0x
            leverage = float(state.get("leverage", 1.0))
            notional = strat_capital * leverage * direction
            sym = sym_to_bybit("BTC/USDT")
            target[sym] = target.get(sym, 0.0) + notional

        else:
            # XS strategies: positions dict {sym: {weight, ...}}
            positions = state.get("positions", {})
            for sym_raw, pos in positions.items():
                weight = float(pos.get("weight", 0.0))
                notional = strat_capital * weight
                sym = sym_to_bybit(sym_raw)
                target[sym] = target.get(sym, 0.0) + notional

    # H-011: add perp short to BTCUSDT when in position
    h011_path = PAPER_DIR / H011_DIR / "state.json"
    if h011_path.exists():
        with open(h011_path) as f:
            h011_st = json.load(f)
        if h011_st.get("in_position"):
            # Notional = capital * L / (L+1) so spot + perp margin = capital exactly
            # e.g. $40k * 5/6 = $33,333 notional; spot=$33,333 + perp margin=$6,667 = $40k
            h011_notional = H011_WEIGHT * TOTAL_CAPITAL * H011_LEVERAGE / (H011_LEVERAGE + 1)
            target[H011_SYMBOL] = target.get(H011_SYMBOL, 0.0) - h011_notional

    return target


# ── Portfolio State ───────────────────────────────────────────────────────

def load_portfolio_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "started": datetime.now(timezone.utc).isoformat(),
        "rebal_count": 0,
        "last_rebal_time": None,
        "equity_history": [],
    }


def save_portfolio_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


# ── H-011 Spot Leg ────────────────────────────────────────────────────────

def handle_h011_spot(trader, btc_price: float, in_position: bool):
    """
    Manage H-011 spot BTC leg on the demo account.

    When H-011 is in_position: buy ~$33k of BTC spot (capital*L/(L+1)).
    When H-011 is out: sell all BTC spot held for this strategy.
    The perp short (~$33k at 5x) is handled via extract_target_notionals().
    """
    h011_capital = H011_WEIGHT * TOTAL_CAPITAL  # $40,000
    # Notional = capital * L/(L+1) = $40k * 5/6 = $33,333 at 5x
    h011_notional = h011_capital * H011_LEVERAGE / (H011_LEVERAGE + 1)
    target_btc = round(h011_notional / btc_price, 5) if in_position else 0.0
    current_btc = trader.get_spot_balance("BTC")

    log(f"\nH-011 spot leg: in_position={in_position}, "
        f"BTC held={current_btc:.5f}, target={target_btc:.5f} "
        f"(${current_btc * btc_price:,.0f} / ${h011_notional:,.0f})")

    if in_position and current_btc < target_btc * 0.90:
        # Buy the missing BTC with USDT (targeting h011_notional, not full h011_capital)
        buy_usdt = h011_notional - current_btc * btc_price
        buy_usdt = round(max(buy_usdt, 0), 2)
        if buy_usdt > 10:
            log(f"  H-011 spot: buying ${buy_usdt:,.2f} USDT of BTC")
            try:
                r = trader.spot_market_order(H011_SYMBOL, "Buy", buy_usdt, quote=True)
                if r.get("retCode") == 0:
                    log(f"    ✓ orderId={r['result'].get('orderId', '?')}")
                else:
                    log(f"    ✗ {r.get('retMsg', 'unknown error')}")
            except Exception as e:
                log(f"    ✗ Exception: {e}")

    elif not in_position and current_btc > 0.001:
        # Sell all spot BTC (H-011 exited)
        sell_qty = round(current_btc, 5)
        log(f"  H-011 spot: selling {sell_qty} BTC")
        try:
            r = trader.spot_market_order(H011_SYMBOL, "Sell", sell_qty)
            if r.get("retCode") == 0:
                log(f"    ✓ orderId={r['result'].get('orderId', '?')}")
            else:
                log(f"    ✗ {r.get('retMsg', 'unknown error')}")
        except Exception as e:
            log(f"    ✗ Exception: {e}")

    else:
        log("  H-011 spot: no action needed")


# ── Main ──────────────────────────────────────────────────────────────────

def run():
    log("=" * 60)
    log("Demo Portfolio Runner starting")

    trader = DemoTrader()

    # Load H-011 state early — needed to pre-set BTCUSDT leverage before any orders
    h011_path = PAPER_DIR / H011_DIR / "state.json"
    h011_in_position = False
    if h011_path.exists():
        with open(h011_path) as f:
            h011_st = json.load(f)
        h011_in_position = h011_st.get("in_position", False)
    log(f"H-011: in_position={h011_in_position}")

    # Pre-set BTCUSDT leverage to H011_LEVERAGE so perp short margin is correct.
    # Must happen before any BTCUSDT market_order call (leverage is cached per session).
    if h011_in_position:
        trader.ensure_leverage(H011_SYMBOL, int(H011_LEVERAGE))

    # Account snapshot
    equity = trader.get_equity()
    available = trader.get_available_balance()
    log(f"Equity: ${equity:,.2f} | Available: ${available:,.2f}")

    # Current positions on Bybit
    current_positions = trader.get_positions()
    log(f"Open positions: {len(current_positions)}")
    for sym, p in sorted(current_positions.items()):
        signed = p["size"] if p["side"] == "Buy" else -p["size"]
        log(f"  {sym}: {p['side']} {p['size']} (PnL ${p['pnl']:+.2f})")

    # Fetch prices for all relevant symbols
    all_syms = list(MIN_QTY.keys())
    prices = trader.get_prices(all_syms)
    missing_prices = [s for s in all_syms if s not in prices]
    if missing_prices:
        log(f"  WARNING: No price for {missing_prices}")

    # Extract target notionals from strategy signals
    target_notionals = extract_target_notionals()
    log(f"\nTarget portfolio ({len(target_notionals)} symbols):")
    for sym, notional in sorted(target_notionals.items()):
        log(f"  {sym}: ${notional:+,.0f}")

    # Close positions in symbols no longer targeted
    stale_syms = set(current_positions) - set(target_notionals)
    for sym in stale_syms:
        log(f"\nClosing stale position: {sym}")
        ok = trader.close_position(sym, current_positions)
        if ok:
            log(f"  Closed {sym}")

    # Rebalance each targeted symbol
    trades_executed = 0
    log("\nRebalancing:")
    for sym, target_notional in sorted(target_notionals.items()):
        price = prices.get(sym)
        if not price:
            log(f"  {sym}: no price, skipping")
            continue

        target_size = target_notional / price   # signed base qty
        current_size = trader.get_signed_size(sym, current_positions)
        delta = target_size - current_size

        # Skip if drift < threshold (avoid noise trades)
        if abs(target_notional) > 0:
            drift_frac = abs(delta * price) / abs(target_notional)
            if drift_frac < REBAL_THRESHOLD and abs(current_size) > 0:
                log(f"  {sym}: drift {drift_frac:.1%} < threshold, skip")
                continue

        # Skip if delta below min order size
        min_qty = MIN_QTY.get(sym, 1.0)
        qty = round_qty(sym, abs(delta))
        if qty < min_qty:
            log(f"  {sym}: |delta|={qty} < min={min_qty}, skip")
            continue

        side = "Buy" if delta > 0 else "Sell"
        notional_delta = qty * price
        log(
            f"  {side} {qty} {sym} @ ${price:,.4f} (~${notional_delta:,.0f})"
            f" | cur={current_size:+.3f} → tgt={target_size:+.3f}"
        )

        try:
            r = trader.market_order(sym, side, qty)
            if r.get("retCode") == 0:
                log(f"    ✓ orderId={r['result'].get('orderId','?')}")
                trades_executed += 1
            else:
                log(f"    ✗ {r.get('retMsg', 'unknown error')}")
        except Exception as e:
            log(f"    ✗ Exception: {e}")

    log(f"\nTrades executed this run: {trades_executed}")

    # H-011 spot leg — buy/sell BTC spot to hedge the perp short
    btc_price = prices.get(H011_SYMBOL, 0.0)
    if btc_price > 0:
        handle_h011_spot(trader, btc_price, h011_in_position)
    else:
        log("H-011 spot: no BTC price available, skipping")

    # Refresh equity after trades
    time_str = datetime.now(timezone.utc).isoformat()
    equity_after = trader.get_equity()
    log(f"Equity after: ${equity_after:,.2f}")

    # Persist portfolio state
    pstate = load_portfolio_state()
    if trades_executed > 0:
        pstate["rebal_count"] += 1
        pstate["last_rebal_time"] = time_str
    pstate["equity_history"].append({
        "time": time_str,
        "equity": equity_after,
        "open_positions": len(current_positions),
        "trades": trades_executed,
    })
    save_portfolio_state(pstate)
    log("=" * 60)

    return trades_executed


if __name__ == "__main__":
    run()
