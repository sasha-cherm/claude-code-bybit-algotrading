#!/usr/bin/env python3
"""
Daily IV Surface Collector — saves a snapshot of Bybit options IV data
for all available underlyings (BTC, ETH, SOL, XRP, DOGE, MNT).

Captures: mark IV, delta, gamma, vega, theta, open interest, volume
for all listed options. One snapshot per day.

Run via cron: 0 1 * * * python3 /home/cctrd/cc-bybit-algotrading/scripts/collect_iv_surface.py

Data stored in: data/iv_snapshots/<date>.parquet
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
import json

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "iv_snapshots"
DATA_DIR.mkdir(parents=True, exist_ok=True)

UNDERLYINGS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE']

def collect_iv_snapshot():
    """Collect IV surface snapshot for all underlyings."""
    ex = ccxt.bybit()
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    output_file = DATA_DIR / f"{date_str}.parquet"
    if output_file.exists():
        print(f"Snapshot for {date_str} already exists, skipping.")
        return

    all_records = []

    for underlying in UNDERLYINGS:
        try:
            result = ex.public_get_v5_market_tickers({
                'category': 'option',
                'baseCoin': underlying
            })
            tickers = result.get('result', {}).get('list', [])

            for t in tickers:
                record = {
                    'timestamp': now.isoformat(),
                    'date': date_str,
                    'underlying': underlying,
                    'symbol': t.get('symbol', ''),
                    'underlying_price': float(t.get('underlyingPrice', 0) or 0),
                    'mark_iv': float(t.get('markIv', 0) or 0),
                    'bid_iv': float(t.get('bid1Iv', 0) or 0),
                    'ask_iv': float(t.get('ask1Iv', 0) or 0),
                    'mark_price': float(t.get('markPrice', 0) or 0),
                    'delta': float(t.get('delta', 0) or 0),
                    'gamma': float(t.get('gamma', 0) or 0),
                    'vega': float(t.get('vega', 0) or 0),
                    'theta': float(t.get('theta', 0) or 0),
                    'open_interest': float(t.get('openInterest', 0) or 0),
                    'volume_24h': float(t.get('volume24h', 0) or 0),
                    'bid_price': float(t.get('bid1Price', 0) or 0),
                    'ask_price': float(t.get('ask1Price', 0) or 0),
                }

                # Parse strike, expiry, option type from symbol
                # Format: BTC-27MAR26-80000-C-USDT
                parts = t.get('symbol', '').split('-')
                if len(parts) >= 4:
                    record['expiry_str'] = parts[1]
                    record['strike'] = float(parts[2]) if parts[2].replace('.','').isdigit() else 0
                    record['option_type'] = 'call' if parts[3] == 'C' else 'put'

                all_records.append(record)

            print(f"  {underlying}: {len(tickers)} options")

        except Exception as e:
            print(f"  {underlying}: Error — {e}")

    if all_records:
        df = pd.DataFrame(all_records)
        df.to_parquet(output_file, index=False)
        print(f"\nSaved {len(df)} records to {output_file}")

        # Summary: compute ATM IV for each underlying
        print("\nATM IV Summary:")
        for underlying in UNDERLYINGS:
            sub = df[df['underlying'] == underlying]
            if len(sub) == 0:
                continue

            # Find ATM options (delta closest to 0.5 for calls)
            calls = sub[(sub['option_type'] == 'call') & (sub['delta'] > 0.3) & (sub['delta'] < 0.7)]
            if len(calls) > 0:
                # Group by expiry, find closest to 0.5 delta
                for expiry in calls['expiry_str'].unique():
                    exp_calls = calls[calls['expiry_str'] == expiry]
                    atm = exp_calls.iloc[(exp_calls['delta'] - 0.5).abs().argsort()[:1]]
                    if len(atm) > 0:
                        iv = atm.iloc[0]['mark_iv']
                        strike = atm.iloc[0]['strike']
                        print(f"  {underlying} {expiry}: ATM IV = {iv*100:.1f}% (K={strike:.0f})")
    else:
        print("No data collected!")

if __name__ == "__main__":
    print(f"=== IV Surface Collector — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ===")
    collect_iv_snapshot()
