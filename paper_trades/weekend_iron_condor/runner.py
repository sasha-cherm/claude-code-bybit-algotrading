#!/usr/bin/env python3
"""
Weekend Iron Condor — Sell BTC options volatility over weekends.

Strategy:
- Open: Saturday 08:01 UTC (cron at 11:01 MSK)
- Expiry: Monday 08:00 UTC (Bybit daily options) — ONLY Monday, no fallback
- Legs:
  - Sell CALL ~4% OTM (collect premium)
  - Sell PUT ~4% OTM (collect premium)
  - Buy CALL insurance (cheapest further OTM)
  - Buy PUT insurance (cheapest further OTM)

If Monday expiry isn't listed yet, retries every 60s for up to 12 hours.
Once all 4 legs are placed, exits immediately.
State auto-resets after Monday expiry passes.

Run: python runner.py [--force] [--dry-run] [--expiry 4APR26]
  --force    Open regardless of day/time (for testing)
  --dry-run  Show plan without placing orders
  --expiry X Override target expiry (for testing)
"""

import os
import sys
import json
import time
import math
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from pybit.unified_trading import HTTP
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

STATE_FILE = Path(__file__).parent / "state.json"
LOG_FILE = Path(__file__).parent / "log.json"

# Unbuffered stdout for cron logging
sys.stdout.reconfigure(line_buffering=True)

# ── Strategy parameters ─────────────────────────────────────────────
SELL_OTM_MIN = 0.035      # sell strikes must be at least 3.5% OTM
SELL_OTM_MAX = 0.055      # search up to 5.5% OTM for sell candidates
SURVIVE_WEEKS = 4          # size to survive N consecutive max losses
MIN_QTY = 0.01             # Bybit min BTC option size
RETRY_INTERVAL = 60        # seconds between retries if Monday expiry not found
RETRY_MAX_HOURS = 12       # give up after this many hours


def get_client():
    key = os.getenv("BYBIT_WEEKEND_API_KEY")
    secret = os.getenv("BYBIT_WEEKEND_API_SECRET")
    if not key or not secret:
        raise RuntimeError("Set BYBIT_WEEKEND_API_KEY/SECRET in .env")
    return HTTP(api_key=key, api_secret=secret, demo=True)


def get_btc_price(client):
    r = client.get_tickers(category="linear", symbol="BTCUSDT")
    return float(r["result"]["list"][0]["lastPrice"])


def get_equity(client):
    r = client.get_wallet_balance(accountType="UNIFIED")
    return float(r["result"]["list"][0].get("totalEquity", 0))


# ── Expiry helpers ──────────────────────────────────────────────────

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def parse_expiry(s):
    """Parse Bybit expiry string like '6APR26' -> datetime(2026,4,6,8,0 UTC)."""
    m = re.match(r"(\d{1,2})([A-Z]{3})(\d{2})", s)
    if not m:
        return None
    day, mon, yr = m.groups()
    if mon not in MONTHS:
        return None
    return datetime(2000 + int(yr), MONTHS[mon], int(day), 8, 0, tzinfo=timezone.utc)


def format_expiry(dt):
    """datetime -> Bybit expiry string like '6APR26'."""
    mon = {v: k for k, v in MONTHS.items()}[dt.month]
    return f"{dt.day}{mon}{dt.strftime('%y')}"


def next_monday():
    """Return (expiry_string, date) for the next Monday."""
    now = datetime.now(timezone.utc)
    days = (7 - now.weekday()) % 7  # weekday: 0=Mon
    if days == 0:
        days = 7
    monday = (now + timedelta(days=days)).replace(hour=8, minute=0, second=0, microsecond=0)
    return format_expiry(monday), monday


# ── Options data ────────────────────────────────────────────────────

def fetch_all_btc_options(client):
    """Fetch all BTC option tickers from Bybit."""
    all_tickers = []
    cursor = ""
    while True:
        params = {"category": "option", "baseCoin": "BTC", "limit": "1000"}
        if cursor:
            params["cursor"] = cursor
        r = client.get_tickers(**params)
        tickers = r["result"]["list"]
        all_tickers.extend(tickers)
        cursor = r["result"].get("nextPageCursor", "")
        if not cursor or not tickers:
            break
    return all_tickers


def get_available_expiries(tickers):
    """Extract unique expiry strings from tickers, sorted by date."""
    expiries = set()
    for t in tickers:
        parts = t["symbol"].split("-")
        if len(parts) >= 4:
            expiries.add(parts[1])
    result = []
    for e in expiries:
        dt = parse_expiry(e)
        if dt:
            result.append((dt, e))
    result.sort()
    return [e for _, e in result]


def filter_options_by_expiry(tickers, expiry_str):
    """Return (calls, puts) for a specific expiry."""
    calls, puts = [], []
    for t in tickers:
        parts = t["symbol"].split("-")
        if len(parts) < 4 or parts[1] != expiry_str:
            continue
        strike = float(parts[2])
        opt = {
            "symbol": t["symbol"],
            "strike": strike,
            "bid": float(t.get("bid1Price", 0) or 0),
            "ask": float(t.get("ask1Price", 0) or 0),
            "mark": float(t.get("markPrice", 0) or 0),
        }
        if parts[3] == "C":
            calls.append(opt)
        elif parts[3] == "P":
            puts.append(opt)
    calls.sort(key=lambda x: x["strike"])
    puts.sort(key=lambda x: x["strike"])
    return calls, puts


# ── Strike selection ────────────────────────────────────────────────

def pick_sell(candidates, btc_price, is_call):
    """
    Pick sell strike: must be 3.5-5.5% OTM.
    Among those, pick highest premium (bid).
    """
    result = []
    for c in candidates:
        otm = abs(c["strike"] - btc_price) / btc_price
        if SELL_OTM_MIN <= otm <= SELL_OTM_MAX:
            if is_call and c["strike"] > btc_price:
                result.append(c)
            elif not is_call and c["strike"] < btc_price:
                result.append(c)
    if not result:
        return None, []
    pick = max(result, key=lambda c: c["bid"])
    return pick, result


def pick_buy(candidates, btc_price, sell_strike, is_call):
    """
    Pick insurance strike: must be further OTM than sell strike.
    Among all valid options, pick the CHEAPEST ask.
    """
    valid = []
    for c in candidates:
        if c["ask"] <= 0 and c["mark"] <= 0:
            continue
        if is_call and c["strike"] > sell_strike:
            valid.append(c)
        elif not is_call and c["strike"] < sell_strike:
            valid.append(c)
    if not valid:
        return None, []
    def cost(c):
        return c["ask"] if c["ask"] > 0 else c["mark"]
    pick = min(valid, key=cost)
    return pick, valid


# ── Position sizing ─────────────────────────────────────────────────

def compute_size(equity, sc, bc, sp, bp):
    """
    Size to survive SURVIVE_WEEKS consecutive max-loss weeks.
    Max loss = max(call_spread_width, put_spread_width) - net premium.
    """
    call_width = bc["strike"] - sc["strike"]
    put_width = sp["strike"] - bp["strike"]
    max_width = max(call_width, put_width)

    sell_prem = sc["bid"] + sp["bid"]
    buy_cost = bc["ask"] + bp["ask"]
    net_premium = sell_prem - buy_cost

    max_loss_per_btc = max(max_width - max(net_premium, 0), max_width * 0.5)

    qty = equity / (SURVIVE_WEEKS * max_loss_per_btc)
    qty = math.floor(qty * 100) / 100.0
    qty = max(qty, MIN_QTY)

    return qty, net_premium, max_loss_per_btc, call_width, put_width


# ── Order placement ─────────────────────────────────────────────────

def place_order(client, symbol, side, qty, price, dry_run=False):
    """Place a limit option order. Returns (success, result_dict)."""
    tag = f"  {side:4s} {symbol} x{qty:.2f} @ ${price:.2f}"
    if dry_run:
        print(f"{tag}  [DRY RUN]")
        return True, {"retMsg": "dry_run", "result": {"orderId": "dry"}}

    r = client.place_order(
        category="option",
        symbol=symbol,
        side=side,
        orderType="Limit",
        qty=str(qty),
        price=str(round(price, 2)),
        timeInForce="GTC",
        orderLinkId=str(uuid.uuid4().hex[:16]),
    )
    msg = r.get("retMsg", "")
    oid = r.get("result", {}).get("orderId", "")
    ok = msg == "OK"
    print(f"{tag}  -> {msg} (id={oid})")
    time.sleep(0.3)
    return ok, r


def cancel_option_orders(client, order_ids):
    """Cancel a list of option orders by ID. Best-effort."""
    for oid in order_ids:
        if not oid:
            continue
        try:
            client.cancel_order(category="option", orderId=oid)
            print(f"  Cancelled order {oid}")
        except Exception as e:
            print(f"  Failed to cancel {oid}: {e}")
        time.sleep(0.2)


# ── State persistence ───────────────────────────────────────────────

def load_state():
    if STATE_FILE.exists():
        return json.load(open(STATE_FILE))
    return {"has_position": False, "history": []}


def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), indent=2, default=str)


def log_event(event):
    log = []
    if LOG_FILE.exists():
        log = json.load(open(LOG_FILE))
    log.append(event)
    json.dump(log, open(LOG_FILE, "w"), indent=2, default=str)


def check_and_reset_expired_state():
    """
    If state has a position whose expiry has passed, reset it.
    Returns the (possibly reset) state.
    """
    state = load_state()
    if not state.get("has_position"):
        return state

    expiry_str = state.get("expiry", "")
    expiry_dt = parse_expiry(expiry_str)
    if expiry_dt is None:
        return state

    now = datetime.now(timezone.utc)
    if now > expiry_dt + timedelta(hours=1):  # 1h grace after expiry
        print(f"Previous position ({expiry_str}) has expired. Resetting state.")
        # Archive to history
        history = state.get("history", [])
        history.append({
            "expiry": expiry_str,
            "opened_at": state.get("opened_at"),
            "btc_at_open": state.get("btc_at_open"),
            "equity_at_open": state.get("equity_at_open"),
            "legs": state.get("legs"),
            "net_premium_total": state.get("net_premium_total"),
        })
        new_state = {"has_position": False, "history": history}
        save_state(new_state)
        log_event({"type": "auto_reset", "time": now.isoformat(), "expired": expiry_str})
        return new_state

    return state


# ── Core: open one iron condor ──────────────────────────────────────

def open_position(client, expiry_str, dry_run=False):
    """
    Attempt to open the iron condor for the given expiry.
    Returns True if all 4 legs were placed, False otherwise.
    On partial success, cancels all placed orders before returning False.
    """
    now = datetime.now(timezone.utc)
    btc = get_btc_price(client)
    equity = get_equity(client)

    print(f"\n--- Attempt at {now.strftime('%H:%M:%S UTC')} | BTC=${btc:,.2f} | Equity=${equity:,.2f} ---")

    all_tickers = fetch_all_btc_options(client)
    avail = get_available_expiries(all_tickers)

    if expiry_str not in avail:
        print(f"  {expiry_str} not yet available. Listed: {', '.join(avail[:10])}")
        return False

    calls, puts = filter_options_by_expiry(all_tickers, expiry_str)
    print(f"  {expiry_str} found: {len(calls)} calls, {len(puts)} puts")

    if len(calls) < 3 or len(puts) < 3:
        print("  Not enough strikes yet, will retry.")
        return False

    # ── Select strikes ──────────────────────────────────────────
    sell_call, sc_cands = pick_sell(calls, btc, is_call=True)
    sell_put, sp_cands = pick_sell(puts, btc, is_call=False)

    if not sell_call or not sell_put:
        print("  No sell strikes in 3.5-5.5% OTM range!")
        print("  Calls:", [(c["strike"], f"{abs(c['strike']-btc)/btc*100:.1f}%") for c in calls])
        print("  Puts:", [(p["strike"], f"{abs(p['strike']-btc)/btc*100:.1f}%") for p in puts])
        return False

    buy_call, _ = pick_buy(calls, btc, sell_call["strike"], is_call=True)
    buy_put, _ = pick_buy(puts, btc, sell_put["strike"], is_call=False)

    if not buy_call or not buy_put:
        print("  No insurance strikes available!")
        return False

    # ── Print candidates ────────────────────────────────────────
    print(f"\n  Sell CALL candidates:")
    for c in sorted(sc_cands, key=lambda x: x["strike"]):
        otm = abs(c["strike"] - btc) / btc * 100
        sel = " <--" if c["symbol"] == sell_call["symbol"] else ""
        print(f"    K={c['strike']:.0f} ({otm:.1f}%) bid=${c['bid']:.2f}{sel}")

    print(f"  Sell PUT candidates:")
    for c in sorted(sp_cands, key=lambda x: -x["strike"]):
        otm = abs(c["strike"] - btc) / btc * 100
        sel = " <--" if c["symbol"] == sell_put["symbol"] else ""
        print(f"    K={c['strike']:.0f} ({otm:.1f}%) bid=${c['bid']:.2f}{sel}")

    # ── Summary ─────────────────────────────────────────────────
    print(f"\n  {'Leg':<12} {'Strike':>8} {'OTM%':>6} {'Bid':>8} {'Ask':>8}")
    print(f"  {'-'*46}")
    for label, opt in [("SELL CALL", sell_call), ("BUY  CALL", buy_call),
                        ("SELL PUT", sell_put), ("BUY  PUT", buy_put)]:
        otm = abs(opt["strike"] - btc) / btc * 100
        print(f"  {label:<12} {opt['strike']:>8.0f} {otm:>5.1f}% {opt['bid']:>8.2f} {opt['ask']:>8.2f}")

    # ── Position sizing ─────────────────────────────────────────
    qty, net_prem, max_loss, cw, pw = compute_size(equity, sell_call, buy_call, sell_put, buy_put)

    print(f"\n  Net premium/BTC: ${net_prem:,.2f} | Max loss/BTC: ${max_loss:,.2f}")
    print(f"  Qty: {qty:.2f} BTC | Premium: ${net_prem*qty:,.2f} | Max loss: ${max_loss*qty:,.2f}")

    # ── Place orders ────────────────────────────────────────────
    print(f"\n  Placing orders{'  [DRY RUN]' if dry_run else ''}:")
    orders = []
    placed_order_ids = []  # track for rollback

    for leg_name, opt, side, price in [
        ("sell_call", sell_call, "Sell", sell_call["bid"]),
        ("sell_put",  sell_put,  "Sell", sell_put["bid"]),
        ("buy_call",  buy_call,  "Buy",  buy_call["ask"]),
        ("buy_put",   buy_put,   "Buy",  buy_put["ask"]),
    ]:
        if price <= 0:
            price = opt["mark"]
        if price <= 0:
            print(f"    SKIP {leg_name}: no price")
            orders.append({"leg": leg_name, "error": "no_price"})
            continue
        try:
            ok, r = place_order(client, opt["symbol"], side, qty, price, dry_run=dry_run)
            oid = r.get("result", {}).get("orderId", "")
            orders.append({
                "leg": leg_name, "symbol": opt["symbol"],
                "side": side, "qty": qty, "price": price,
                "result": r.get("retMsg", ""),
                "order_id": oid,
            })
            if ok and oid:
                placed_order_ids.append(oid)
        except Exception as e:
            print(f"    ERROR {leg_name}: {e}")
            orders.append({"leg": leg_name, "symbol": opt["symbol"], "error": str(e)})

    # ── Verify all 4 legs succeeded ─────────────────────────────
    succeeded = sum(1 for o in orders if o.get("result") == "OK")

    if succeeded < 4:
        print(f"\n  Only {succeeded}/4 orders succeeded — rolling back.")
        if placed_order_ids and not dry_run:
            cancel_option_orders(client, placed_order_ids)
        return False

    # ── Save state ──────────────────────────────────────────────
    state = load_state()
    new_state = {
        "has_position": True,
        "opened_at": now.isoformat(),
        "btc_at_open": btc,
        "equity_at_open": equity,
        "expiry": expiry_str,
        "qty": qty,
        "legs": {
            "sell_call": {"symbol": sell_call["symbol"], "strike": sell_call["strike"], "premium": sell_call["bid"]},
            "sell_put":  {"symbol": sell_put["symbol"],  "strike": sell_put["strike"],  "premium": sell_put["bid"]},
            "buy_call":  {"symbol": buy_call["symbol"],  "strike": buy_call["strike"],  "cost": buy_call["ask"]},
            "buy_put":   {"symbol": buy_put["symbol"],   "strike": buy_put["strike"],   "cost": buy_put["ask"]},
        },
        "orders": orders,
        "net_premium_total": round(net_prem * qty, 2),
        "max_loss_total": round(max_loss * qty, 2),
        "history": state.get("history", []),
    }

    if not dry_run:
        save_state(new_state)
        log_event({
            "type": "open", "time": now.isoformat(),
            "btc": btc, "equity": equity,
            "expiry": expiry_str, "qty": qty,
            "legs": new_state["legs"], "orders": orders,
        })

    print(f"\n  Position opened! 4/4 orders placed.")
    return True


# ── Main entry point ────────────────────────────────────────────────

def run(force_open=False, dry_run=False, target_expiry=None):
    now = datetime.now(timezone.utc)

    print("=== Weekend Iron Condor ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M UTC')} ({now.strftime('%A')})")

    # Auto-reset expired positions
    state = check_and_reset_expired_state()

    if state.get("has_position"):
        print(f"Position already open (since {state.get('opened_at', '?')}). Exiting.")
        return

    is_saturday = now.weekday() == 5
    if not force_open and not is_saturday:
        print("Not Saturday. Use --force to override. Exiting.")
        return

    # Determine target expiry
    if target_expiry:
        expiry_str = target_expiry.upper()
        print(f"Target expiry (manual): {expiry_str}")
    else:
        expiry_str, monday_dt = next_monday()
        print(f"Target expiry: {expiry_str} (Mon {monday_dt.strftime('%Y-%m-%d')} 08:00 UTC)")

    # Try to open — retry every 60s for up to 12 hours if Monday not listed yet
    deadline = now + timedelta(hours=RETRY_MAX_HOURS)
    attempt = 0

    while True:
        attempt += 1
        # Fresh client each attempt to avoid stale sessions
        try:
            client = get_client()
            placed = open_position(client, expiry_str, dry_run=dry_run)
        except Exception as e:
            print(f"\n  Unexpected error on attempt {attempt}: {e}")
            placed = False

        if placed:
            print(f"\nDone. Position placed on attempt {attempt}.")
            return

        if dry_run:
            print("\nDry run complete.")
            return

        now = datetime.now(timezone.utc)
        if now >= deadline:
            print(f"\nGave up after {RETRY_MAX_HOURS} hours ({attempt} attempts). {expiry_str} never appeared.")
            return

        print(f"  Waiting {RETRY_INTERVAL}s before retry... (attempt {attempt}, deadline {deadline.strftime('%H:%M UTC')})")
        time.sleep(RETRY_INTERVAL)


if __name__ == "__main__":
    force = "--force" in sys.argv
    dry = "--dry-run" in sys.argv
    expiry = None
    for i, arg in enumerate(sys.argv):
        if arg == "--expiry" and i + 1 < len(sys.argv):
            expiry = sys.argv[i + 1]
    run(force_open=force, dry_run=dry, target_expiry=expiry)
