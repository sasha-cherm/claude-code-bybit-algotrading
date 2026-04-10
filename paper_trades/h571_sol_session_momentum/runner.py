#!/usr/bin/env python3
"""
H-571: SOL Intraday Session Momentum Paper Trade Runner
Signal: first 6h return of the day predicts next-day SOL direction.
If first 6h return > 0, go LONG SOL next day. If < 0, go SHORT.
50% of capital exposure per trade.

Confirmed: IS Sharpe 0.847, WF 6/7, SH PASS, 100% param robust, BTC corr -0.092.
"""
import json, os
from datetime import datetime, timezone
from collections import defaultdict
import numpy as np
import ccxt

STATE_FILE = os.path.join(os.path.dirname(__file__), 'state.json')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'log.json')

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        'started': datetime.now(timezone.utc).isoformat(),
        'capital': 10000,
        'position': 0,
        'entry_price': 0,
        'signal': 0,
        'last_signal_date': None,
        'last_rebal_date': None,
        'total_trades': 0,
        'equity_history': [],
        'log': []
    }

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def append_log(entry):
    log = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            log = json.load(f)
    log.append(entry)
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f, indent=2)

def run():
    state = load_state()
    now = datetime.now(timezone.utc)
    today_str = now.strftime('%Y-%m-%d')

    print(f"=== H-571 SOL Session Momentum Paper Trade Runner ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M')} UTC")

    ex = ccxt.bybit()
    ohlcv = ex.fetch_ohlcv('SOL/USDT', '1h', limit=48)

    sol_price = ohlcv[-1][4]

    daily_bars = defaultdict(list)
    for bar in ohlcv:
        dt = datetime.fromtimestamp(bar[0]/1000, tz=timezone.utc)
        day = dt.strftime('%Y-%m-%d')
        daily_bars[day].append(bar)

    dates = sorted(daily_bars.keys())
    yesterday = dates[-2] if len(dates) >= 2 else None

    new_signal = state['signal']
    if yesterday and yesterday != state.get('last_signal_date'):
        bars = daily_bars[yesterday]
        if len(bars) >= 6:
            open_price = bars[0][1]
            close_6h = bars[5][4]
            first_6h_ret = close_6h / open_price - 1
            new_signal = 1 if first_6h_ret > 0 else -1
            state['last_signal_date'] = yesterday
            print(f"  Yesterday {yesterday}: first 6h return = {first_6h_ret*100:.2f}% -> signal = {new_signal}")

    if state['position'] != 0:
        pnl = state['position'] * (sol_price - state['entry_price'])
        equity = state['capital'] + pnl
    else:
        equity = state['capital']

    if new_signal != 0 and (state['position'] == 0 or np.sign(state['position']) != new_signal):
        if state['position'] != 0:
            pnl = state['position'] * (sol_price - state['entry_price'])
            state['capital'] += pnl
            cost = abs(state['position']) * sol_price * 0.0005
            state['capital'] -= cost
            state['total_trades'] += 1

            append_log({
                'type': 'close',
                'time': now.isoformat(),
                'sol_price': sol_price,
                'position': state['position'],
                'entry_price': state['entry_price'],
                'pnl': pnl,
                'cost': cost
            })

        notional = state['capital'] * 0.5
        position_size = notional / sol_price * new_signal

        cost = abs(position_size) * sol_price * 0.0005
        state['capital'] -= cost
        state['position'] = position_size
        state['entry_price'] = sol_price
        state['signal'] = new_signal
        state['last_rebal_date'] = today_str
        state['total_trades'] += 1

        direction = "LONG" if new_signal > 0 else "SHORT"
        append_log({
            'type': 'open',
            'time': now.isoformat(),
            'sol_price': sol_price,
            'direction': direction,
            'position': position_size,
            'notional': notional
        })

        print(f"  Opened {direction} {abs(position_size):.4f} SOL @ ${sol_price:.2f}")
    else:
        print(f"  No signal change. Holding {'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'}.")

    if state['position'] != 0:
        pnl = state['position'] * (sol_price - state['entry_price'])
        equity = state['capital'] + pnl
    else:
        equity = state['capital']

    pnl_pct = (equity / 10000 - 1) * 100

    state['equity_history'].append({
        'time': now.isoformat(),
        'equity': round(equity, 2),
        'sol_price': sol_price,
        'position': state['position'],
        'signal': state['signal']
    })

    if len(state['equity_history']) > 500:
        state['equity_history'] = state['equity_history'][-500:]

    save_state(state)

    direction = 'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'
    print(f"\n  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    print(f"  Position: {direction} {abs(state['position']):.4f} SOL @ ${state['entry_price']:.2f}")
    print(f"  SOL Price: ${sol_price:,.2f}")
    print(f"  Trades: {state['total_trades']}")

if __name__ == '__main__':
    run()
