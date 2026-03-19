"""
H-037: Polymarket 1hr BTC UP/DOWN Paper Trade Tracker

This is a MANUAL paper trade — Polymarket prices must be checked manually
since there's no historical data or API integration.

Target hours (UTC) and direction:
  17:00 → bet UP  (56.3% historical green rate, p < 0.01)
  21:00 → bet UP  (54.9%, p < 0.01)
  22:00 → bet UP  (54.0%, p < 0.05)
  23:00 → bet DOWN (54.1%, p < 0.05)
  13:00 → bet DOWN (53.8%, p < 0.05)

Process:
  1. At each target hour, check Polymarket BTC 1hr UP/DOWN market
  2. Record the market price (e.g., UP at 52c, DOWN at 48c)
  3. Decide whether to "bet" based on whether price offers +EV
  4. After the hour, record outcome (green or red candle)
  5. Track cumulative PnL

Usage:
  python3 paper_trades/h037_polymarket/tracker.py log <hour> <direction> <pm_price> <outcome>
  python3 paper_trades/h037_polymarket/tracker.py summary
  python3 paper_trades/h037_polymarket/tracker.py check  # auto-check BTC candle outcomes
"""

import json
import os
import sys
from datetime import datetime, timezone

LOG_FILE = os.path.join(os.path.dirname(__file__), "trades.json")

# Target hours and expected direction based on statistical analysis
TARGET_HOURS = {
    17: {"direction": "UP", "hist_prob": 0.563, "pval": 0.001},
    21: {"direction": "UP", "hist_prob": 0.549, "pval": 0.005},
    22: {"direction": "UP", "hist_prob": 0.540, "pval": 0.014},
    23: {"direction": "DOWN", "hist_prob": 0.541, "pval": 0.014},
    13: {"direction": "DOWN", "hist_prob": 0.538, "pval": 0.023},
}

# Polymarket fee
PM_FEE = 0.02  # 2% on winnings
BET_SIZE = 10  # $10 per bet


def load_trades():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            return json.load(f)
    return {"trades": [], "summary": {"total_bets": 0, "wins": 0, "losses": 0, "pnl": 0.0}}


def save_trades(data):
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def log_trade(hour, direction, pm_price, outcome):
    """Log a paper trade."""
    data = load_trades()

    buy_price = float(pm_price)
    hour = int(hour)
    won = (direction.upper() == outcome.upper())

    if won:
        profit = (1 - buy_price) * (1 - PM_FEE) * BET_SIZE
    else:
        profit = -buy_price * BET_SIZE

    trade = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hour_utc": hour,
        "bet_direction": direction.upper(),
        "pm_price": buy_price,
        "outcome": outcome.upper(),
        "won": won,
        "profit": round(profit, 2),
        "hist_prob": TARGET_HOURS.get(hour, {}).get("hist_prob", "?"),
    }

    data["trades"].append(trade)
    data["summary"]["total_bets"] += 1
    if won:
        data["summary"]["wins"] += 1
    else:
        data["summary"]["losses"] += 1
    data["summary"]["pnl"] = round(data["summary"]["pnl"] + profit, 2)

    save_trades(data)
    print(f"Logged: {hour:02d}:00 UTC bet {direction} @ {buy_price:.2f}c → "
          f"{'WIN' if won else 'LOSS'} ${profit:+.2f} | Cumulative: ${data['summary']['pnl']:+.2f}")


def show_summary():
    """Show paper trade summary."""
    data = load_trades()
    s = data["summary"]

    print("=" * 50)
    print("H-037 Polymarket Paper Trade Summary")
    print("=" * 50)
    print(f"Total bets: {s['total_bets']}")
    if s["total_bets"] > 0:
        print(f"Wins: {s['wins']} ({s['wins']/s['total_bets']:.1%})")
        print(f"Losses: {s['losses']} ({s['losses']/s['total_bets']:.1%})")
        print(f"Cumulative PnL: ${s['pnl']:+.2f}")
        print(f"Avg profit/bet: ${s['pnl']/s['total_bets']:+.2f}")
    else:
        print("No trades yet.")

    if data["trades"]:
        print(f"\nRecent trades:")
        for t in data["trades"][-10:]:
            print(f"  {t['timestamp'][:16]} | {t['hour_utc']:02d}:00 | "
                  f"bet {t['bet_direction']} @ {t['pm_price']:.2f} → "
                  f"{'WIN' if t['won'] else 'LOSS'} ${t['profit']:+.2f}")

    # Breakeven analysis
    print(f"\n  Breakeven info:")
    for h, info in sorted(TARGET_HOURS.items()):
        breakeven = 1 / (1 + (1 - PM_FEE))  # price where EV=0 for 50% win
        max_price = info["hist_prob"] * (1 - PM_FEE) / (info["hist_prob"] * (1 - PM_FEE) + (1 - info["hist_prob"]))
        print(f"    {h:02d}:00 {info['direction']}: hist P(win)={info['hist_prob']:.1%}, "
              f"max buy price for +EV: {max_price:.3f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  tracker.py log <hour> <direction> <pm_price> <outcome>")
        print("  tracker.py summary")
        print("  Example: tracker.py log 17 UP 0.50 UP")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "log" and len(sys.argv) == 6:
        log_trade(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == "summary":
        show_summary()
    else:
        print("Unknown command. Use 'log' or 'summary'.")
