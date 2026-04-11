#!/usr/bin/env python3
"""
H-679: BTC Vol Regime Switch Paper Trade Runner
Vol expanding (5d/30d ratio > 1) → follow trend. Vol contracting → fade trend.
IS Sharpe 1.464, WF 4/5, SH 1.825/1.042, 88% param robust.
Corr: H-012=0.023, H-009=0.241.
"""
import json, os
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import ccxt

STATE_FILE = os.path.join(os.path.dirname(__file__), 'state.json')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'log.json')

PARAMS = {
    'short_vol_window': 5,
    'long_vol_window': 30,
    'trend_window': 5,
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

    print(f"=== H-679 BTC Vol Regime Switch Paper Trade Runner ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M')} UTC")

    ex = ccxt.bybit()
    ohlcv = ex.fetch_ohlcv('BTC/USDT', '1d', limit=60)

    df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df['date'] = pd.to_datetime(df['ts'], unit='ms')
    df.set_index('date', inplace=True)
    df['ret'] = df['close'].pct_change()

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
            'time': now.isoformat(), 'equity': round(equity, 2),
            'btc_price': btc_price, 'signal': state['signal']
        })
        if len(state['equity_history']) > 500:
            state['equity_history'] = state['equity_history'][-500:]
        save_state(state)
        direction = 'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'
        print(f"  Same day. Holding {direction}. Equity ${equity:,.2f} ({pnl_pct:+.2f}%)")
        return

    # Use completed bars
    completed = df.iloc[:-1]
    sw = PARAMS['short_vol_window']
    lw = PARAMS['long_vol_window']
    tw = PARAMS['trend_window']

    if len(completed) < lw + 5:
        print(f"  Not enough data ({len(completed)} bars, need {lw + 5})")
        save_state(state)
        return

    short_vol = completed['ret'].iloc[-sw:].std()
    long_vol = completed['ret'].iloc[-lw:].std()
    vol_ratio = short_vol / long_vol if long_vol > 0 else 1

    trend = 1 if completed['close'].iloc[-1] > completed['close'].iloc[-tw-1] else -1

    # Vol expanding → follow trend; Vol contracting → fade trend
    if vol_ratio > 1:
        new_signal = trend       # momentum
    else:
        new_signal = -trend      # contrarian

    regime = 'EXPANDING' if vol_ratio > 1 else 'CONTRACTING'
    trend_dir = 'UP' if trend > 0 else 'DOWN'
    print(f"  BTC: ${btc_price:.2f}")
    print(f"  Vol ratio (5d/30d): {vol_ratio:.3f} ({regime})")
    print(f"  5d trend: {trend_dir}")
    print(f"  Signal: {new_signal} ({'LONG' if new_signal > 0 else 'SHORT'})")

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
                'type': 'close', 'time': now.isoformat(),
                'btc_price': btc_price, 'position': state['position'],
                'entry_price': state['entry_price'],
                'pnl': round(pnl, 2), 'cost': round(cost, 2),
                'vol_ratio': vol_ratio,
            })
            print(f"  Closed {'LONG' if state['position'] > 0 else 'SHORT'}: PnL ${pnl:.2f}")
            state['position'] = 0
            state['entry_price'] = 0

        notional = state['capital'] * PARAMS['position_frac']
        position_size = notional / btc_price * new_signal
        cost = abs(position_size) * btc_price * 0.0005
        state['capital'] -= cost
        state['position'] = position_size
        state['entry_price'] = btc_price
        state['total_trades'] += 1
        direction = "LONG" if new_signal > 0 else "SHORT"
        append_log({
            'type': 'open', 'time': now.isoformat(),
            'btc_price': btc_price, 'direction': direction,
            'position': position_size, 'notional': notional,
            'vol_ratio': vol_ratio, 'trend': trend,
        })
        print(f"  Opened {direction} {abs(position_size):.6f} BTC @ ${btc_price:.2f}")

        state['signal'] = new_signal
    else:
        direction = 'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'
        print(f"  No signal change. Holding {direction}.")

    if state['position'] != 0:
        pnl = state['position'] * (btc_price - state['entry_price'])
        equity = state['capital'] + pnl
    else:
        equity = state['capital']

    pnl_pct = (equity / state['initial_capital'] - 1) * 100
    state['equity'] = round(equity, 2)
    state['equity_history'].append({
        'time': now.isoformat(), 'equity': round(equity, 2),
        'btc_price': btc_price, 'signal': new_signal,
        'vol_ratio': vol_ratio,
    })
    if len(state['equity_history']) > 500:
        state['equity_history'] = state['equity_history'][-500:]
    state['last_date'] = today
    save_state(state)

    direction = 'LONG' if state['position'] > 0 else 'SHORT' if state['position'] < 0 else 'FLAT'
    print(f"\n  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    print(f"  Position: {direction} {abs(state['position']):.6f} BTC @ ${state['entry_price']:.2f}")
    print(f"  Trades: {state['total_trades']}")

if __name__ == '__main__':
    run()
