#!/usr/bin/env python3
"""
H-063: Systematic BTC Short Strangle with Delta Hedging

Strategy:
- Sell 7-day BTC strangle (3% OTM call + 3% OTM put) weekly
- Delta-hedge daily using BTCUSDT perp
- 10% stop-loss on position
- Uses actual Bybit options quotes for realistic pricing

Paper trade: queries real Bybit options prices, simulates execution.
Run hourly via cron (only acts at specific times).

Backtest: Sharpe 1.54, +52.5% annual, -18.4% DD, 73% WR, 60/60 params positive.
WF: 6/6 positive folds, mean Sharpe 1.91.
Fee robust: Sharpe 1.24 even at 5% option spread fees.
"""

import json
import ccxt
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
from scipy.stats import norm

STATE_FILE = Path(__file__).parent / "state.json"
LOG_FILE = Path(__file__).parent / "log.json"

NOTIONAL = 10000  # $10k per trade
OTM_PCT = 0.03  # 3% out-of-the-money
STOP_LOSS = 0.10  # 10% of notional
IV_ASSUMPTION = 0.50  # used for BS calculations when actual IV unavailable

def bs_price(S, K, T, sigma, option_type='call'):
    if T <= 0:
        return max(S - K, 0) if option_type == 'call' else max(K - S, 0)
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == 'call':
        return S * norm.cdf(d1) - K * norm.cdf(d2)
    else:
        return K * norm.cdf(-d2) - S * norm.cdf(-d1)


def bs_delta(S, K, T, sigma, option_type='call'):
    if T <= 0:
        return (1.0 if S > K else 0.0) if option_type == 'call' else (-1.0 if S < K else 0.0)
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1) if option_type == 'call' else norm.cdf(d1) - 1


def load_state():
    if STATE_FILE.exists():
        return json.load(open(STATE_FILE))
    return {
        "started": datetime.now(timezone.utc).isoformat(),
        "capital": NOTIONAL,
        "in_trade": False,
        "trade": None,
        "hedge_position": 0,  # delta hedge in BTC
        "total_trades": 0,
        "total_pnl": 0,
        "equity_history": [],
        "last_check": None,
    }


def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), indent=2, default=str)


def log_event(event):
    log = []
    if LOG_FILE.exists():
        log = json.load(open(LOG_FILE))
    log.append(event)
    json.dump(log, open(LOG_FILE, "w"), indent=2, default=str)


def get_btc_price():
    """Get current BTC price from Bybit."""
    from pybit.unified_trading import HTTP
    s = HTTP()
    t = s.get_tickers(category="linear", symbol="BTCUSDT")
    return float(t["result"]["list"][0]["lastPrice"])


def find_target_expiry(ex, spot):
    """Find the best BTC option expiry ~7 days out."""
    now = datetime.now(timezone.utc)
    target = now + timedelta(days=7)

    try:
        markets = ex.load_markets()
        btc_options = [
            m for m in markets.values()
            if m.get("base") == "BTC"
            and m.get("type") == "option"
            and m.get("quote") == "USDT"
            and m.get("expiry")
        ]
    except Exception as e:
        print(f"Error loading markets: {e}")
        return None, None, None

    # Find expiry closest to 7 days
    best = None
    best_diff = float("inf")
    for m in btc_options:
        exp_ts = m["expiry"] / 1000 if m["expiry"] > 1e12 else m["expiry"]
        exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
        diff = abs((exp_dt - target).total_seconds())
        if diff < best_diff and exp_dt > now + timedelta(days=3):
            best_diff = diff
            best = m
            best_expiry = exp_dt

    if best is None:
        return None, None, None

    # Find call and put strikes near 3% OTM
    call_strike_target = spot * (1 + OTM_PCT)
    put_strike_target = spot * (1 - OTM_PCT)

    expiry_str = best.get("info", {}).get("symbol", "").split("-")[1] if best else None

    # Get available strikes for this expiry
    exp_options = [
        m for m in btc_options
        if m.get("expiry") == best.get("expiry")
    ]

    calls = [m for m in exp_options if m.get("info", {}).get("optionsType") == "Call"]
    puts = [m for m in exp_options if m.get("info", {}).get("optionsType") == "Put"]

    best_call = min(calls, key=lambda m: abs(float(m.get("strike", 0)) - call_strike_target)) if calls else None
    best_put = min(puts, key=lambda m: abs(float(m.get("strike", 0)) - put_strike_target)) if puts else None

    return best_call, best_put, best_expiry


def get_option_quotes(ex, call_market, put_market):
    """Get bid/ask for the options."""
    quotes = {}
    for label, market in [("call", call_market), ("put", put_market)]:
        if market is None:
            continue
        try:
            ticker = ex.fetch_ticker(market["symbol"])
            quotes[label] = {
                "symbol": market["symbol"],
                "strike": float(market.get("strike", 0)),
                "bid": ticker.get("bid", 0) or 0,
                "ask": ticker.get("ask", 0) or 0,
                "mark": ticker.get("last", 0) or (ticker.get("bid", 0) + ticker.get("ask", 0)) / 2,
                "iv": ticker.get("info", {}).get("markIv", IV_ASSUMPTION),
            }
        except Exception as e:
            print(f"Error fetching {label} quote: {e}")
    return quotes


def run():
    state = load_state()
    now = datetime.now(timezone.utc)
    btc_price = get_btc_price()
    ex = ccxt.bybit()

    print(f"=== H-063 Vol Selling Paper Trade ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"BTC: ${btc_price:,.2f}")
    print(f"Capital: ${state['capital']:,.2f}")
    print(f"In trade: {state['in_trade']}")

    if state["in_trade"] and state["trade"]:
        trade = state["trade"]
        T_remain = (datetime.fromisoformat(trade["expiry"]) - now).total_seconds() / (365.25 * 86400)

        if T_remain <= 0:
            # Expiry: settle the trade
            call_payoff = max(btc_price - trade["call_strike"], 0) * trade["num_contracts"]
            put_payoff = max(trade["put_strike"] - btc_price, 0) * trade["num_contracts"]
            settlement = call_payoff + put_payoff

            # Close hedge
            hedge_close_cost = abs(state["hedge_position"]) * btc_price * 0.0006

            net_pnl = trade["premium_collected"] - settlement + trade.get("hedge_pnl", 0) - trade["total_fees"] - hedge_close_cost
            state["capital"] += net_pnl
            state["total_pnl"] += net_pnl
            state["total_trades"] += 1
            state["in_trade"] = False
            state["hedge_position"] = 0

            log_event({
                "type": "expiry",
                "time": now.isoformat(),
                "btc_price": btc_price,
                "call_payoff": call_payoff,
                "put_payoff": put_payoff,
                "net_pnl": net_pnl,
                "capital_after": state["capital"],
            })
            print(f"  EXPIRED: call_payoff=${call_payoff:.2f}, put_payoff=${put_payoff:.2f}, net_pnl=${net_pnl:+.2f}")
            state["trade"] = None

        else:
            # Mark-to-market and delta hedge
            call_val = bs_price(btc_price, trade["call_strike"], T_remain, trade.get("iv", IV_ASSUMPTION), "call")
            put_val = bs_price(btc_price, trade["put_strike"], T_remain, trade.get("iv", IV_ASSUMPTION), "put")
            current_liability = (call_val + put_val) * trade["num_contracts"]

            # Delta
            call_d = bs_delta(btc_price, trade["call_strike"], T_remain, trade.get("iv", IV_ASSUMPTION), "call")
            put_d = bs_delta(btc_price, trade["put_strike"], T_remain, trade.get("iv", IV_ASSUMPTION), "put")
            target_hedge = -(call_d + put_d) * trade["num_contracts"]

            # Update hedge P&L
            if trade.get("last_btc_price"):
                price_change = btc_price - trade["last_btc_price"]
                trade["hedge_pnl"] = trade.get("hedge_pnl", 0) + state["hedge_position"] * price_change

            # Rebalance hedge
            hedge_change = target_hedge - state["hedge_position"]
            if abs(hedge_change) > 0.0001:
                hedge_fee = abs(hedge_change) * btc_price * 0.0006
                trade["total_fees"] += hedge_fee
                state["hedge_position"] = target_hedge
                print(f"  Hedge rebalanced: {state['hedge_position']:.6f} BTC (delta change: {hedge_change:+.6f})")

            trade["last_btc_price"] = btc_price

            # Check stop-loss
            running_pnl = trade["premium_collected"] - current_liability + trade.get("hedge_pnl", 0) - trade["total_fees"]
            if running_pnl < -STOP_LOSS * NOTIONAL:
                # Close position at market
                close_fee = current_liability * 0.03  # pessimistic 3% spread to close
                net_pnl = running_pnl - close_fee
                state["capital"] += net_pnl
                state["total_pnl"] += net_pnl
                state["total_trades"] += 1
                state["in_trade"] = False
                state["hedge_position"] = 0
                state["trade"] = None

                log_event({
                    "type": "stop_loss",
                    "time": now.isoformat(),
                    "btc_price": btc_price,
                    "running_pnl": running_pnl,
                    "net_pnl": net_pnl,
                    "capital_after": state["capital"],
                })
                print(f"  STOP LOSS triggered: pnl=${net_pnl:+.2f}")
            else:
                mtm = state["capital"] + running_pnl
                print(f"  MTM: ${mtm:,.2f} ({(mtm/NOTIONAL-1)*100:+.2f}%), running_pnl=${running_pnl:+.2f}")
                print(f"  Premium: ${trade['premium_collected']:.2f}, Liability: ${current_liability:.2f}")
                print(f"  T_remain: {T_remain*365:.1f} days")

    # Enter new trade if not in one (check once daily at ~01:00 UTC)
    if not state["in_trade"] and now.hour == 1:
        call_mkt, put_mkt, expiry_dt = find_target_expiry(ex, btc_price)

        if call_mkt and put_mkt and expiry_dt:
            quotes = get_option_quotes(ex, call_mkt, put_mkt)

            if "call" in quotes and "put" in quotes:
                call_q = quotes["call"]
                put_q = quotes["put"]

                # Sell at bid price (realistic)
                call_sell = call_q["bid"]
                put_sell = put_q["bid"]

                if call_sell > 0 and put_sell > 0:
                    num_contracts = NOTIONAL / btc_price
                    premium = num_contracts * (call_sell + put_sell)
                    entry_fee = premium * 0.02  # 2% spread cost estimate

                    iv_avg = float(call_q.get("iv", IV_ASSUMPTION) or IV_ASSUMPTION)

                    trade = {
                        "entry_time": now.isoformat(),
                        "expiry": expiry_dt.isoformat(),
                        "call_symbol": call_q["symbol"],
                        "put_symbol": put_q["symbol"],
                        "call_strike": call_q["strike"],
                        "put_strike": put_q["strike"],
                        "call_premium": call_sell,
                        "put_premium": put_sell,
                        "num_contracts": num_contracts,
                        "premium_collected": premium,
                        "iv": iv_avg,
                        "btc_at_entry": btc_price,
                        "total_fees": entry_fee,
                        "hedge_pnl": 0,
                        "last_btc_price": btc_price,
                    }

                    state["in_trade"] = True
                    state["trade"] = trade

                    log_event({
                        "type": "entry",
                        "time": now.isoformat(),
                        "btc_price": btc_price,
                        "call": call_q,
                        "put": put_q,
                        "premium": premium,
                        "num_contracts": num_contracts,
                    })

                    print(f"  NEW TRADE: Sell {call_q['symbol']} @ ${call_sell:.2f} + {put_q['symbol']} @ ${put_sell:.2f}")
                    print(f"  Premium: ${premium:.2f}, Contracts: {num_contracts:.6f}")
                    print(f"  Expiry: {expiry_dt.strftime('%Y-%m-%d %H:%M UTC')}")
                else:
                    print("  No entry: zero bid on options")
            else:
                print("  No entry: couldn't get quotes")
        else:
            print("  No entry: no suitable expiry found")

    # Record equity
    mtm = state["capital"]
    if state["in_trade"] and state["trade"]:
        trade = state["trade"]
        T_r = max((datetime.fromisoformat(trade["expiry"]) - now).total_seconds() / (365.25 * 86400), 0)
        cv = bs_price(btc_price, trade["call_strike"], T_r, trade.get("iv", IV_ASSUMPTION), "call")
        pv = bs_price(btc_price, trade["put_strike"], T_r, trade.get("iv", IV_ASSUMPTION), "put")
        liability = (cv + pv) * trade["num_contracts"]
        running = trade["premium_collected"] - liability + trade.get("hedge_pnl", 0) - trade["total_fees"]
        mtm = state["capital"] + running

    state["equity_history"].append({
        "time": now.isoformat(),
        "equity": round(mtm, 2),
        "btc_price": btc_price,
        "in_trade": state["in_trade"],
    })

    # Keep only last 500 equity records
    if len(state["equity_history"]) > 500:
        state["equity_history"] = state["equity_history"][-500:]

    state["last_check"] = now.isoformat()
    state["equity"] = round(mtm, 2)
    save_state(state)

    print(f"\nMark equity: ${mtm:,.2f} ({(mtm/NOTIONAL-1)*100:+.2f}%)")
    print(f"Total trades: {state['total_trades']}, Total PnL: ${state['total_pnl']:+.2f}")


if __name__ == "__main__":
    run()
