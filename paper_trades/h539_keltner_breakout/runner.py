#!/usr/bin/env python3
"""
H-539: BTC Keltner Channel Breakout Paper Trade Runner
Signal: BTC closes above/below Keltner Channel (EMA30 +/- 2.5*ATR30).
Long when price breaks above upper channel, short when below lower.
Flat when inside channel. ~15% exposure.
"""
import json, os
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import ccxt

STATE_FILE = os.path.join(os.path.dirname(__file__), 'state.json')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'log.json')

PARAMS = {
    'ema_span': 30,
    'atr_window': 30,
    'atr_mult': 2.5,
}

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
        'last_check_date': None,
        'total_trades': 0,
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
    today_str = now.strftime('%Y-%m-%d')

    print(f"=== H-539 Keltner Breakout Paper Trade Runner ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M')} UTC")

    # Fetch daily BTC data (need 60+ bars for indicator calculation)
    ex = ccxt.bybit()
    ohlcv = ex.fetch_ohlcv('BTC/USDT', '1d', limit=100)

    df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df['date'] = pd.to_datetime(df['ts'], unit='ms')
    df.set_index('date', inplace=True)

    btc_price = df['close'].iloc[-1]

    # Check if we have a new daily bar
    last_date = df.index[-1].strftime('%Y-%m-%d')
    prev_date = df.index[-2].strftime('%Y-%m-%d') if len(df) > 1 else None

    # Use previous bar's close for signal (avoid look-ahead)
    # Signal is based on yesterday's close vs channel
    signal_df = df.iloc[:-1]  # Exclude today's incomplete bar

    if len(signal_df) < PARAMS['ema_span'] + 5:
        print("  Not enough data for indicator calculation")
        save_state(state)
        return

    # Calculate Keltner Channel on completed bars
    ema = signal_df['close'].ewm(span=PARAMS['ema_span']).mean()
    tr = pd.concat([
        signal_df['high'] - signal_df['low'],
        (signal_df['high'] - signal_df['close'].shift(1)).abs(),
        (signal_df['low'] - signal_df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(PARAMS['atr_window']).mean()

    upper = ema + PARAMS['atr_mult'] * atr
    lower = ema - PARAMS['atr_mult'] * atr

    last_close = signal_df['close'].iloc[-1]
    last_upper = upper.iloc[-1]
    last_lower = lower.iloc[-1]

    # Determine signal
    if last_close > last_upper:
        new_signal = 1   # Breakout up
    elif last_close < last_lower:
        new_signal = -1  # Breakout down
    else:
        new_signal = 0   # Inside channel, flat

    print(f"  Last close: ${last_close:.2f}")
    print(f"  EMA({PARAMS['ema_span']}): ${ema.iloc[-1]:.2f}")
    print(f"  Upper channel: ${last_upper:.2f}")
    print(f"  Lower channel: ${last_lower:.2f}")
    print(f"  Signal: {new_signal} ({'LONG' if new_signal > 0 else 'SHORT' if new_signal < 0 else 'FLAT'})")

    # Current equity
    if state['position'] != 0:
        pnl = state['position'] * (btc_price - state['entry_price'])
        equity = state['capital'] + pnl
    else:
        equity = state['capital']

    # Handle signal changes
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
                'old_signal': old_signal
            })

            print(f"  Closed {'LONG' if state['position'] > 0 else 'SHORT'}: PnL ${pnl:.2f}")
            state['position'] = 0
            state['entry_price'] = 0

        # Open new position if signal is non-zero
        if new_signal != 0:
            notional = state['capital'] * 0.5  # 50% of capital
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
                'upper': round(last_upper, 2),
                'lower': round(last_lower, 2)
            })

            print(f"  Opened {direction} {abs(position_size):.6f} BTC @ ${btc_price:.2f}")

        state['signal'] = new_signal
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
        'signal': new_signal
    })

    if len(state['equity_history']) > 500:
        state['equity_history'] = state['equity_history'][-500:]

    state['last_check_date'] = today_str
    save_state(state)

    direction = 'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'
    print(f"\n  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    if state['position'] != 0:
        print(f"  Position: {direction} {abs(state['position']):.6f} BTC @ ${state['entry_price']:.2f}")
    else:
        print(f"  Position: FLAT (inside channel)")
    print(f"  Trades: {state['total_trades']}")

if __name__ == '__main__':
    run()
