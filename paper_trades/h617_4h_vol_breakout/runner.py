#!/usr/bin/env python3
"""
H-617: BTC 4h Volume Breakout Paper Trade Runner
Signal: When BTC shows positive 12-bar (48h) momentum AND volume surges >1.5x
its 48-bar moving average, go long. When negative momentum + volume surge, short.
Position held until opposite signal. Flat when no volume surge.
"""
import json, os
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import ccxt

STATE_FILE = os.path.join(os.path.dirname(__file__), 'state.json')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'log.json')

PARAMS = {
    'mom_period': 12,
    'vol_mult': 1.5,
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
        'last_bar': None,
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

    print(f"=== H-617 4h Volume Breakout Paper Trade Runner ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M')} UTC")

    ex = ccxt.bybit()
    ohlcv = ex.fetch_ohlcv('BTC/USDT', '4h', limit=100)

    df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df['date'] = pd.to_datetime(df['ts'], unit='ms')
    df.set_index('date', inplace=True)

    btc_price = df['close'].iloc[-1]

    # Use completed bars only (exclude current bar)
    signal_df = df.iloc[:-1]
    last_bar_ts = signal_df.index[-1].isoformat()

    if state['last_bar'] == last_bar_ts:
        # Already processed this bar
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
            'signal': state['signal']
        })
        if len(state['equity_history']) > 500:
            state['equity_history'] = state['equity_history'][-500:]
        save_state(state)

        direction = 'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'
        print(f"  Same bar. Holding {direction}. Equity ${equity:,.2f} ({pnl_pct:+.2f}%)")
        return

    mom_period = PARAMS['mom_period']
    vol_mult = PARAMS['vol_mult']

    ret = signal_df['close'].pct_change(mom_period)
    vol_ma = signal_df['volume'].rolling(mom_period * 4).mean()

    last_ret = ret.iloc[-1]
    last_vol = signal_df['volume'].iloc[-1]
    last_vol_ma = vol_ma.iloc[-1]
    vol_surge = last_vol > vol_mult * last_vol_ma

    if vol_surge and last_ret > 0:
        new_signal = 1
    elif vol_surge and last_ret < 0:
        new_signal = -1
    else:
        new_signal = state['signal']  # Hold previous signal (ffill)

    print(f"  BTC: ${btc_price:.2f}")
    print(f"  48h return: {last_ret*100:+.2f}%")
    print(f"  Volume ratio: {last_vol/last_vol_ma:.2f}x {'(SURGE)' if vol_surge else '(normal)'}")
    print(f"  Signal: {new_signal} ({'LONG' if new_signal > 0 else 'SHORT' if new_signal < 0 else 'FLAT'})")

    # Current equity
    if state['position'] != 0:
        pnl = state['position'] * (btc_price - state['entry_price'])
        equity = state['capital'] + pnl
    else:
        equity = state['capital']

    old_signal = state['signal']
    if new_signal != old_signal:
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
            })

            print(f"  Closed {'LONG' if state['position'] > 0 else 'SHORT'}: PnL ${pnl:.2f}")
            state['position'] = 0
            state['entry_price'] = 0

        if new_signal != 0:
            notional = state['capital'] * 0.5
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

    pnl_pct = (equity / 10000 - 1) * 100

    state['equity_history'].append({
        'time': now.isoformat(),
        'equity': round(equity, 2),
        'btc_price': btc_price,
        'signal': new_signal
    })

    if len(state['equity_history']) > 500:
        state['equity_history'] = state['equity_history'][-500:]

    state['last_bar'] = last_bar_ts
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
