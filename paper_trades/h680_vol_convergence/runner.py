#!/usr/bin/env python3
"""
H-680: Return-Volume Convergence Cross-Sectional Factor Paper Trade Runner
Long assets where price AND volume move up together (confirmed momentum).
Short assets where both decline (confirmed weakness).
IS Sharpe 1.486 (LB20_N4_R3), WF 4/5, SH 1.835/1.039, 90% param robust.
Corr: H-012=0.264.
"""
import json, os
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import ccxt

STATE_FILE = os.path.join(os.path.dirname(__file__), 'state.json')
LOG_FILE = os.path.join(os.path.dirname(__file__), 'log.json')

ASSETS = ['BTC','ETH','SOL','SUI','XRP','DOGE','AVAX','LINK','ADA','DOT','NEAR','OP','ARB','ATOM']
PARAMS = {
    'lookback': 20,
    'n_positions': 4,
    'rebal_days': 3,
}

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        'started': datetime.now(timezone.utc).isoformat(),
        'initial_capital': 10000,
        'capital': 10000,
        'positions': {},
        'last_rebal_date': None,
        'rebal_count': 0,
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

    print(f"=== H-680 Return-Volume Convergence Paper Trade Runner ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M')} UTC")

    ex = ccxt.bybit()
    lb = PARAMS['lookback']

    all_data = {}
    for sym in ASSETS:
        try:
            ohlcv = ex.fetch_ohlcv(f'{sym}/USDT', '1d', limit=lb + 10)
            df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['ts'], unit='ms')
            df.set_index('date', inplace=True)
            all_data[sym] = df
        except:
            pass

    print(f"Loaded {len(all_data)} assets")
    if len(all_data) < 8:
        print("  Not enough assets")
        save_state(state)
        return

    # Get latest prices
    prices = {sym: df['close'].iloc[-1] for sym, df in all_data.items()}
    today = list(all_data.values())[0].index[-1].strftime('%Y-%m-%d')

    # Check if new daily bar
    last_date = state.get('last_rebal_date')

    # Compute MTM
    equity = state['capital']
    for sym, pos_info in state.get('positions', {}).items():
        if sym in prices:
            pnl = pos_info['qty'] * (prices[sym] - pos_info['entry_price'])
            equity += pnl

    # Check rebalance
    need_rebal = False
    if last_date is None:
        need_rebal = True
    else:
        last_dt = pd.Timestamp(last_date)
        current_dt = pd.Timestamp(today)
        days_since = (current_dt - last_dt).days
        if days_since >= PARAMS['rebal_days']:
            need_rebal = True

    if not need_rebal:
        pnl_pct = (equity / state['initial_capital'] - 1) * 100
        state['equity'] = round(equity, 2)
        state['equity_history'].append({
            'time': now.isoformat(), 'equity': round(equity, 2),
        })
        if len(state['equity_history']) > 500:
            state['equity_history'] = state['equity_history'][-500:]
        save_state(state)
        print(f"No new daily bar since {last_date}.")
        print(f"\n  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
        print(f"  Rebals: {state['rebal_count']}, Positions: {len(state.get('positions', {}))}")
        for sym, pi in sorted(state.get('positions', {}).items()):
            pnl = pi['qty'] * (prices.get(sym, pi['entry_price']) - pi['entry_price'])
            d = 'LONG' if pi['qty'] > 0 else 'SHORT'
            print(f"    {d:5s} {sym}/USDT{' '*(10-len(sym))} pnl=${pnl:+.2f}")
        return

    print(f"Rebalancing (day {today})...")

    # Compute convergence scores using completed bars
    closes = pd.DataFrame({sym: df['close'].iloc[:-1] for sym, df in all_data.items()})
    volumes = pd.DataFrame({sym: df['volume'].iloc[:-1] for sym, df in all_data.items()})

    if len(closes) < lb:
        print(f"  Not enough data ({len(closes)} bars, need {lb})")
        save_state(state)
        return

    price_mom = closes.pct_change(lb).iloc[-1]
    vol_mom = np.log(volumes + 1).diff(lb).iloc[-1]

    pm = price_mom.dropna()
    vm = vol_mom.reindex(pm.index).dropna()
    common = pm.index.intersection(vm.index)
    pm, vm = pm[common], vm[common]

    if len(pm) < 8:
        print("  Not enough assets with data")
        save_state(state)
        return

    pz = (pm - pm.mean()) / (pm.std() + 1e-10)
    vz = (vm - vm.mean()) / (vm.std() + 1e-10)
    score = pz + vz  # convergence: both moving together

    ranked = score.rank(ascending=False)
    N = min(PARAMS['n_positions'], len(ranked) // 2)
    longs = ranked[ranked <= N].index.tolist()
    shorts = ranked[ranked > len(ranked) - N].index.tolist()

    print(f"  LONG: {longs}")
    print(f"  SHORT: {shorts}")

    # Close existing positions
    for sym, pos_info in state.get('positions', {}).items():
        if sym in prices:
            pnl = pos_info['qty'] * (prices[sym] - pos_info['entry_price'])
            state['capital'] += pnl
            cost = abs(pos_info['qty']) * prices[sym] * 0.0005
            state['capital'] -= cost

    # Open new positions
    notional_per = state['capital'] / (2 * N)
    new_positions = {}

    for sym in longs:
        qty = notional_per / prices[sym]
        cost = qty * prices[sym] * 0.0005
        state['capital'] -= cost
        new_positions[sym] = {'qty': qty, 'entry_price': prices[sym], 'side': 'LONG'}

    for sym in shorts:
        qty = -notional_per / prices[sym]
        cost = abs(qty) * prices[sym] * 0.0005
        state['capital'] -= cost
        new_positions[sym] = {'qty': qty, 'entry_price': prices[sym], 'side': 'SHORT'}

    state['positions'] = new_positions
    state['last_rebal_date'] = today
    state['rebal_count'] = state.get('rebal_count', 0) + 1
    state['total_trades'] += len(longs) + len(shorts)

    # Recompute equity
    equity = state['capital']
    for sym, pi in new_positions.items():
        pnl = pi['qty'] * (prices[sym] - pi['entry_price'])
        equity += pnl

    pnl_pct = (equity / state['initial_capital'] - 1) * 100
    state['equity'] = round(equity, 2)
    state['equity_history'].append({
        'time': now.isoformat(), 'equity': round(equity, 2),
    })
    if len(state['equity_history']) > 500:
        state['equity_history'] = state['equity_history'][-500:]
    save_state(state)

    append_log({
        'type': 'rebalance', 'time': now.isoformat(),
        'longs': longs, 'shorts': shorts,
        'equity': round(equity, 2),
    })

    print(f"\n  Equity:  ${equity:,.2f} ({pnl_pct:+.2f}%)")
    print(f"  Rebals: {state['rebal_count']}, Positions: {len(new_positions)}")
    for sym, pi in sorted(new_positions.items()):
        d = 'LONG' if pi['qty'] > 0 else 'SHORT'
        print(f"    {d:5s} {sym}/USDT{' '*(10-len(sym))} pnl=$0.00")

if __name__ == '__main__':
    run()
