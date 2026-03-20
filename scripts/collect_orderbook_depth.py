#!/usr/bin/env python3
"""
Order Book Depth Collector — daily snapshot of bid/ask imbalance for 14 assets.

Captures top-25 level depth metrics for each asset. Run daily via cron.
After ~60-90 days, enough history for cross-sectional backtesting.

Cron: 01:30 0 * * *  (daily at 01:30 UTC, after IV collector at 01:00)
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "orderbook_snapshots"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ASSETS = [
    "BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX",
    "LINK", "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM",
]

DEPTH_LEVELS = 25  # top N levels on each side


def collect_snapshot():
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    timestamp = now.isoformat()

    records = []
    for asset in ASSETS:
        symbol = f"{asset}USDT"
        try:
            url = "https://api.bybit.com/v5/market/orderbook"
            resp = requests.get(
                url,
                params={"category": "linear", "symbol": symbol, "limit": 50},
                timeout=10,
            )
            data = resp.json()

            if data["retCode"] != 0:
                print(f"  {asset}: API error {data['retCode']}")
                continue

            book = data["result"]
            bids = book["b"][:DEPTH_LEVELS]
            asks = book["a"][:DEPTH_LEVELS]

            bid_vol = sum(float(b[1]) for b in bids)
            ask_vol = sum(float(a[1]) for a in asks)
            imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol) if (bid_vol + ask_vol) > 0 else 0

            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            spread_bps = (best_ask - best_bid) / best_bid * 10000

            # Depth at different levels
            bid_vol_5 = sum(float(b[1]) for b in bids[:5])
            ask_vol_5 = sum(float(a[1]) for a in asks[:5])
            imbalance_5 = (bid_vol_5 - ask_vol_5) / (bid_vol_5 + ask_vol_5) if (bid_vol_5 + ask_vol_5) > 0 else 0

            bid_vol_10 = sum(float(b[1]) for b in bids[:10])
            ask_vol_10 = sum(float(a[1]) for a in asks[:10])
            imbalance_10 = (bid_vol_10 - ask_vol_10) / (bid_vol_10 + ask_vol_10) if (bid_vol_10 + ask_vol_10) > 0 else 0

            records.append({
                "timestamp": timestamp,
                "date": date_str,
                "asset": asset,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread_bps": round(spread_bps, 4),
                "bid_vol_5": round(bid_vol_5, 4),
                "ask_vol_5": round(ask_vol_5, 4),
                "imbalance_5": round(imbalance_5, 6),
                "bid_vol_10": round(bid_vol_10, 4),
                "ask_vol_10": round(ask_vol_10, 4),
                "imbalance_10": round(imbalance_10, 6),
                "bid_vol_25": round(bid_vol, 4),
                "ask_vol_25": round(ask_vol, 4),
                "imbalance_25": round(imbalance, 6),
            })

        except Exception as e:
            print(f"  {asset}: error: {e}")

        time.sleep(0.1)

    # Save daily snapshot
    out_file = DATA_DIR / f"depth_{date_str}.json"
    with open(out_file, "w") as f:
        json.dump(records, f, indent=2)

    print(f"[{timestamp}] Saved {len(records)} records to {out_file}")
    return records


if __name__ == "__main__":
    print(f"=== Order Book Depth Collector ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    records = collect_snapshot()
    print(f"Collected {len(records)}/{len(ASSETS)} assets")
