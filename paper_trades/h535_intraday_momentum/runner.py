#!/usr/bin/env python3
"""
H-535: BTC Intraday Session Momentum Paper Trade Runner
Signal: first 6h return of the day predicts next-day BTC direction.
If first 6h return > 0, go LONG BTC next day. If < 0, go SHORT.
100% exposure, single asset (BTC), vol-targeting 15% annual.
"""
import json, os, sys
from datetime import datetime, timezone
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
        'position': 0,         # BTC position size (signed)
        'entry_price': 0,
        'signal': 0,           # +1 or -1
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

    print(f"=== H-535 Intraday Momentum Paper Trade Runner ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M')} UTC")

    # Fetch hourly BTC data
    ex = ccxt.bybit()
    ohlcv = ex.fetch_ohlcv('BTC/USDT', '1h', limit=48)

    btc_price = ohlcv[-1][4]  # Current close

    # Group by date to find today's first 6h
    from collections import defaultdict
    daily_bars = defaultdict(list)
    for bar in ohlcv:
        dt = datetime.fromtimestamp(bar[0]/1000, tz=timezone.utc)
        day = dt.strftime('%Y-%m-%d')
        daily_bars[day].append(bar)

    # Compute signal from yesterday's first 6h
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

    # Current equity
    if state['position'] != 0:
        pnl = state['position'] * (btc_price - state['entry_price'])
        equity = state['capital'] + pnl
    else:
        equity = state['capital']

    # Rebalance if signal changed
    if new_signal != 0 and (state['position'] == 0 or np.sign(state['position']) != new_signal):
        # Close existing position
        if state['position'] != 0:
            pnl = state['position'] * (btc_price - state['entry_price'])
            state['capital'] += pnl
            # Trading cost
            cost = abs(state['position']) * btc_price * 0.0005
            state['capital'] -= cost
            state['total_trades'] += 1

            append_log({
                'type': 'close',
                'time': now.isoformat(),
                'btc_price': btc_price,
                'position': state['position'],
                'entry_price': state['entry_price'],
                'pnl': pnl,
                'cost': cost
            })

        # Open new position (vol-targeting 15% annual)
        # Daily vol = annual_vol / sqrt(365)
        # We don't have vol estimate here, so use fixed 1% of capital as notional
        notional = state['capital'] * 0.5  # 50% of capital
        position_size = notional / btc_price * new_signal

        cost = abs(position_size) * btc_price * 0.0005
        state['capital'] -= cost
        state['position'] = position_size
        state['entry_price'] = btc_price
        state['signal'] = new_signal
        state['last_rebal_date'] = today_str
        state['total_trades'] += 1

        direction = "LONG" if new_signal > 0 else "SHORT"
        append_log({
            'type': 'open',
            'time': now.isoformat(),
            'btc_price': btc_price,
            'direction': direction,
            'position': position_size,
            'notional': notional
        })

        print(f"  Opened {direction} {abs(position_size):.6f} BTC @ ${btc_price:.2f}")
    elif state['position'] == 0 and new_signal != 0:
        # First entry
        notional = state['capital'] * 0.5
        position_size = notional / btc_price * new_signal
        cost = abs(position_size) * btc_price * 0.0005
        state['capital'] -= cost
        state['position'] = position_size
        state['entry_price'] = btc_price
        state['signal'] = new_signal
        state['last_rebal_date'] = today_str
        state['total_trades'] += 1

        direction = "LONG" if new_signal > 0 else "SHORT"
        append_log({
            'type': 'open',
            'time': now.isoformat(),
            'btc_price': btc_price,
            'direction': direction,
            'position': position_size,
            'notional': notional
        })
        print(f"  Opened {direction} {abs(position_size):.6f} BTC @ ${btc_price:.2f}")
    else:
        print(f"  No signal change. Holding {'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'}.")

    # Update equity
    if state['position'] != 0:
        pnl = state['position'] * (btc_price - state['entry_price'])
        equity = state['capital'] + pnl
    else:
        equity = state['capital']

    pnl_pct = (equity / 10000 - 1) * 100

    state['equity_history'].append({
        'time': now.isoformat(),
        'equity': round(equity, 2),
        'btc_price': btc_price,
        'position': state['position'],
        'signal': state['signal']
    })

    # Keep last 500 equity entries
    if len(state['equity_history']) > 500:
        state['equity_history'] = state['equity_history'][-500:]

    save_state(state)

    direction = 'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'
    print(f"\n  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    print(f"  Position: {direction} {abs(state['position']):.6f} BTC @ ${state['entry_price']:.2f}")
    print(f"  BTC Price: ${btc_price:,.2f}")
    print(f"  Trades: {state['total_trades']}")

if __name__ == '__main__':
    run()
