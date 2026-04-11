#!/usr/bin/env python3
"""
H-657: BTC Realized Skew Paper Trade Runner
Signal: Compute 30-day realized skew of BTC returns.
Positive skew (>0.5) → long BTC. Negative skew (<-0.5) → short BTC. Else flat.
IS Sharpe 0.947, 98% param robust, SH PASS (0.624/1.524), WF 5/6.
"""
import json, os
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import ccxt
from scipy.stats import skew as skew_fn

STATE_FILE = os.path.join(os.path.dirname(__file__), 'state.json')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'log.json')

PARAMS = {
    'skew_lookback': 30,
    'long_threshold': 0.5,
    'short_threshold': -0.5,
    'position_frac': 0.5,
}

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        'started': datetime.now(timezone.utc).isoformat(),
        'capital': 10000,
        'initial_capital': 10000,
        'position': 0,
        'entry_price': 0,
        'signal': 0,
        'last_date': None,
        'total_trades': 0,
        'equity': 10000,
        'equity_history': [],
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

    print(f"=== H-657 BTC Realized Skew Paper Trade Runner ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M')} UTC")

    ex = ccxt.bybit()
    ohlcv = ex.fetch_ohlcv('BTC/USDT', '1d', limit=60)

    df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df['date'] = pd.to_datetime(df['ts'], unit='ms')
    df.set_index('date', inplace=True)

    btc_price = df['close'].iloc[-1]
    today = df.index[-1].strftime('%Y-%m-%d')

    if state['last_date'] == today:
        if state['position'] != 0:
            pnl = state['position'] * (btc_price - state['entry_price'])
            equity = state['capital'] + pnl
        else:
            equity = state['capital']
        pnl_pct = (equity / state['initial_capital'] - 1) * 100
        state['equity'] = round(equity, 2)

        state['equity_history'].append({
            'time': now.isoformat(),
            'equity': round(equity, 2),
            'btc_price': btc_price,
            'signal': state['signal']
        })
        if len(state['equity_history']) > 500:
            state['equity_history'] = state['equity_history'][-500:]
        save_state(state)

        direction = 'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'
        print(f"  Same day. Holding {direction}. Equity ${equity:,.2f} ({pnl_pct:+.2f}%)")
        return

    # Compute realized skew
    lookback = PARAMS['skew_lookback']
    signal_df = df.iloc[:-1]  # Use completed bars only
    if len(signal_df) < lookback:
        print(f"  Not enough data ({len(signal_df)} bars, need {lookback})")
        save_state(state)
        return

    returns = signal_df['close'].pct_change().dropna()
    window = returns.iloc[-lookback:]
    realized_skew = float(skew_fn(window))

    if realized_skew > PARAMS['long_threshold']:
        new_signal = 1
    elif realized_skew < PARAMS['short_threshold']:
        new_signal = -1
    else:
        new_signal = 0

    print(f"  BTC: ${btc_price:.2f}")
    print(f"  Realized skew (30d): {realized_skew:.3f}")
    print(f"  Signal: {new_signal} ({'LONG' if new_signal > 0 else 'SHORT' if new_signal < 0 else 'FLAT'})")

    # Current equity
    if state['position'] != 0:
        pnl = state['position'] * (btc_price - state['entry_price'])
        equity = state['capital'] + pnl
    else:
        equity = state['capital']

    old_signal = state['signal']
    if new_signal != old_signal:
        # Close existing position
        if state['position'] != 0:
            pnl = state['position'] * (btc_price - state['entry_price'])
            state['capital'] += pnl
            cost = abs(state['position']) * btc_price * 0.0005
            state['capital'] -= cost
            state['total_trades'] += 1

            append_log({
                'type': 'close',
                'time': now.isoformat(),
                'btc_price': btc_price,
                'position': state['position'],
                'entry_price': state['entry_price'],
                'pnl': round(pnl, 2),
                'cost': round(cost, 2),
                'skew': realized_skew,
            })

            print(f"  Closed {'LONG' if state['position'] > 0 else 'SHORT'}: PnL ${pnl:.2f}")
            state['position'] = 0
            state['entry_price'] = 0

        # Open new position
        if new_signal != 0:
            notional = state['capital'] * PARAMS['position_frac']
            position_size = notional / btc_price * new_signal
            cost = abs(position_size) * btc_price * 0.0005
            state['capital'] -= cost
            state['position'] = position_size
            state['entry_price'] = btc_price
            state['total_trades'] += 1

            direction = "LONG" if new_signal > 0 else "SHORT"
            append_log({
                'type': 'open',
                'time': now.isoformat(),
                'btc_price': btc_price,
                'direction': direction,
                'position': position_size,
                'notional': notional,
                'skew': realized_skew,
            })

            print(f"  Opened {direction} {abs(position_size):.6f} BTC @ ${btc_price:.2f}")

        state['signal'] = new_signal
    else:
        print(f"  No signal change. Holding {'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'}.")

    if state['position'] != 0:
        pnl = state['position'] * (btc_price - state['entry_price'])
        equity = state['capital'] + pnl
    else:
        equity = state['capital']

    pnl_pct = (equity / state['initial_capital'] - 1) * 100

    state['equity'] = round(equity, 2)
    state['equity_history'].append({
        'time': now.isoformat(),
        'equity': round(equity, 2),
        'btc_price': btc_price,
        'signal': new_signal,
        'skew': realized_skew
    })

    if len(state['equity_history']) > 500:
        state['equity_history'] = state['equity_history'][-500:]

    state['last_date'] = today
    state['last_check_date'] = now.strftime('%Y-%m-%d')
    save_state(state)

    direction = 'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'
    print(f"\n  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    if state['position'] != 0:
        print(f"  Position: {direction} {abs(state['position']):.6f} BTC @ ${state['entry_price']:.2f}")
    else:
        print(f"  Position: FLAT")
    print(f"  Trades: {state['total_trades']}")

if __name__ == '__main__':
    run()
