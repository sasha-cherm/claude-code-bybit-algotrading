#!/usr/bin/env python3
"""
H-544: BTC Range Squeeze Breakout Paper Trade Runner
Signal: When ATR is in bottom 10th percentile (60-day window), trade breakout direction.
Long if price rising during squeeze, short if falling. Flat when not in squeeze.
~14-21% exposure.
"""
import json, os
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import ccxt

STATE_FILE = os.path.join(os.path.dirname(__file__), 'state.json')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'log.json')

PARAMS = {
    'atr_window': 20,        # ATR lookback
    'pctile_window': 60,     # Window for percentile ranking
    'squeeze_pctile': 10,    # Bottom 10th percentile = squeeze
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
        'in_squeeze': False,
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

    print(f"=== H-544 Range Squeeze Breakout Paper Trade Runner ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M')} UTC")

    # Fetch daily BTC data
    ex = ccxt.bybit()
    ohlcv = ex.fetch_ohlcv('BTC/USDT', '1d', limit=120)

    df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df['date'] = pd.to_datetime(df['ts'], unit='ms')
    df.set_index('date', inplace=True)

    btc_price = df['close'].iloc[-1]

    # Use completed bars only (exclude today's incomplete bar)
    signal_df = df.iloc[:-1]

    if len(signal_df) < PARAMS['pctile_window'] + PARAMS['atr_window'] + 5:
        print("  Not enough data for indicator calculation")
        save_state(state)
        return

    # Calculate ATR
    atr = (signal_df['high'] - signal_df['low']).rolling(PARAMS['atr_window']).mean()

    # ATR percentile within recent window
    atr_values = atr.dropna().values
    if len(atr_values) < PARAMS['pctile_window']:
        print("  Not enough ATR data")
        save_state(state)
        return

    recent_atr = atr_values[-PARAMS['pctile_window']:]
    current_atr = atr_values[-1]
    atr_pctile = (recent_atr < current_atr).sum() / len(recent_atr) * 100

    in_squeeze = atr_pctile < PARAMS['squeeze_pctile']

    # Breakout direction: yesterday's close vs day before
    last_close = signal_df['close'].iloc[-1]
    prev_close = signal_df['close'].iloc[-2]
    breakout_dir = 1 if last_close > prev_close else -1

    # Signal: only trade during squeeze
    if in_squeeze:
        new_signal = breakout_dir
    else:
        new_signal = 0

    print(f"  ATR({PARAMS['atr_window']}): ${current_atr:.2f}")
    print(f"  ATR percentile (60d): {atr_pctile:.1f}%")
    print(f"  Squeeze: {'YES' if in_squeeze else 'NO'} (threshold: {PARAMS['squeeze_pctile']}%)")
    if in_squeeze:
        print(f"  Breakout direction: {'UP' if breakout_dir > 0 else 'DOWN'}")

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
                'cost': round(cost, 2)
            })

            print(f"  Closed {'LONG' if state['position'] > 0 else 'SHORT'}: PnL ${pnl:.2f}")
            state['position'] = 0
            state['entry_price'] = 0

        # Open new position if signal is non-zero
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
                'atr_pctile': round(atr_pctile, 1)
            })

            print(f"  Opened {direction} {abs(position_size):.6f} BTC @ ${btc_price:.2f}")

        state['signal'] = new_signal
    else:
        status = 'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'
        print(f"  No signal change. Holding {status}.")

    state['in_squeeze'] = bool(in_squeeze)

    # Update equity
    if state['position'] != 0:
        pnl = state['position'] * (btc_price - state['entry_price'])
        equity = state['capital'] + pnl
    else:
        equity = state['capital']

    pnl_pct = (equity / 10000 - 1) * 100

    state['equity_history'].append({
        'time': now.isoformat(),
        'equity': round(float(equity), 2),
        'btc_price': float(btc_price),
        'signal': int(new_signal),
        'in_squeeze': bool(in_squeeze),
        'atr_pctile': round(float(atr_pctile), 1)
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
        print(f"  Position: FLAT (not in squeeze)")
    print(f"  Trades: {state['total_trades']}")

if __name__ == '__main__':
    run()
