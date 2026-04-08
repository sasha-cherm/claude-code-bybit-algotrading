#!/usr/bin/env python3
"""
Weekend BTC Move Probabilities (Sat 00:01 → Mon 08:00 UTC)
==========================================================
For an iron condor strategy held over the weekend:
  - Entry: Saturday 00:01 UTC
  - Expiry: Monday 08:00 UTC (~56 hours holding)

For each weekend in the past 3 years, measure:
  - BTC price move (%) from Sat 00:01 to Mon 08:00
  - DVOL at Sat 00:01

Then compute probability of |move| <= 3% and |move| <= 4%
conditional on DVOL being below thresholds: 35, 40, 45, 50.

Usage:
    python3 scripts/weekend_iron_condor_probabilities.py
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from lib.data_fetch import fetch_and_cache

LOOKBACK_DAYS = 1095  # 3 years
DVOL_THRESHOLDS = [50, 45, 40, 35]
MOVE_BANDS = [0.03, 0.04]


# ─── Data fetching ──────────────────────────────────────────────────────────

def fetch_btc_hourly() -> pd.DataFrame:
    """Hourly BTC/USDT from Bybit (cached)."""
    print("Fetching BTC/USDT hourly data from Bybit...")
    start_date = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS + 5)).strftime("%Y-%m-%d")
    df = fetch_and_cache(symbol="BTC/USDT", timeframe="1h", since=start_date)
    print(f"  {len(df)} hourly candles, {df.index.min()} → {df.index.max()}")
    return df


def fetch_dvol_hourly() -> pd.DataFrame:
    """Hourly Deribit BTC DVOL."""
    print("Fetching Deribit DVOL hourly data...")
    url = "https://www.deribit.com/api/v2/public/get_volatility_index_data"

    end_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ts = end_ts - LOOKBACK_DAYS * 86400 * 1000

    chunk_ms = 30 * 86400 * 1000  # 30 days per request
    all_data = []
    cur = start_ts
    while cur < end_ts:
        nxt = min(cur + chunk_ms, end_ts)
        r = requests.get(url, params={
            "currency": "BTC",
            "start_timestamp": int(cur),
            "end_timestamp": int(nxt),
            "resolution": "3600"
        }, timeout=30)
        r.raise_for_status()
        data = r.json().get("result", {}).get("data", [])
        all_data.extend(data)
        cur = nxt
        time.sleep(0.3)

    df = pd.DataFrame(all_data, columns=["timestamp", "open", "high", "low", "close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    print(f"  {len(df)} hourly DVOL points, {df.index.min()} → {df.index.max()}")
    return df


# ─── Weekend extraction ─────────────────────────────────────────────────────

def get_value_at(df: pd.DataFrame, ts: pd.Timestamp, col: str = "close") -> float | None:
    """Get value at exact timestamp; fall back to nearest within 3 hours."""
    if ts in df.index:
        return float(df.loc[ts, col])
    # Find closest within 3 hour window
    window = df[(df.index >= ts - pd.Timedelta(hours=3)) & (df.index <= ts + pd.Timedelta(hours=3))]
    if window.empty:
        return None
    nearest_idx = (window.index - ts).map(abs).argmin()
    return float(window.iloc[nearest_idx][col])


def extract_weekend_events(btc_df: pd.DataFrame, dvol_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each Saturday in the dataset, measure:
      - BTC price at Sat 00:00 UTC (proxy for Sat 00:01)
      - DVOL at Sat 00:00 UTC
      - BTC price at Mon 08:00 UTC
      - % move over the weekend window
    """
    # Find first Saturday in data
    start = btc_df.index.min().normalize()
    while start.weekday() != 5:  # 5 = Saturday
        start += pd.Timedelta(days=1)

    end = btc_df.index.max()
    events = []
    cur_sat = start

    while cur_sat + pd.Timedelta(days=2, hours=8) <= end:
        sat_entry = cur_sat  # Sat 00:00 UTC
        mon_exit = cur_sat + pd.Timedelta(days=2, hours=8)  # Mon 08:00 UTC

        btc_entry = get_value_at(btc_df, sat_entry)
        btc_exit = get_value_at(btc_df, mon_exit)
        dvol_entry = get_value_at(dvol_df, sat_entry)

        if btc_entry is not None and btc_exit is not None and dvol_entry is not None:
            move_pct = (btc_exit / btc_entry - 1) * 100
            events.append({
                "weekend_start": sat_entry,
                "btc_entry": btc_entry,
                "btc_exit": btc_exit,
                "dvol": dvol_entry,
                "move_pct": move_pct,
                "abs_move_pct": abs(move_pct),
            })

        cur_sat += pd.Timedelta(days=7)

    return pd.DataFrame(events)


# ─── Analysis ───────────────────────────────────────────────────────────────

def analyze(events: pd.DataFrame) -> None:
    print("\n" + "=" * 100)
    print("Weekend BTC Move Analysis: Sat 00:01 → Mon 08:00 UTC (~56 hours)")
    print("=" * 100)

    print(f"\nTotal weekends analyzed: {len(events)}")
    print(f"Period: {events['weekend_start'].min().date()} → {events['weekend_start'].max().date()}")

    # Overall stats
    print(f"\n--- Overall Move Distribution (all weekends, no DVOL filter) ---")
    print(f"  Mean abs move:    {events['abs_move_pct'].mean():.2f}%")
    print(f"  Median abs move:  {events['abs_move_pct'].median():.2f}%")
    print(f"  Std move:         {events['move_pct'].std():.2f}%")
    print(f"  Max up move:      {events['move_pct'].max():+.2f}%")
    print(f"  Max down move:    {events['move_pct'].min():+.2f}%")
    print(f"  Avg DVOL:         {events['dvol'].mean():.1f}")
    print(f"  DVOL range:       {events['dvol'].min():.1f} — {events['dvol'].max():.1f}")

    # Probability of staying within band — overall
    print(f"\n--- Unconditional Probabilities (all weekends) ---")
    for band in MOVE_BANDS:
        within = (events["abs_move_pct"] <= band * 100).mean() * 100
        print(f"  P(|move| ≤ {band*100:.0f}%):  {within:.1f}%  ({int((events['abs_move_pct'] <= band * 100).sum())}/{len(events)})")

    # Conditional on DVOL thresholds
    print("\n" + "=" * 100)
    print("CONDITIONAL PROBABILITIES (DVOL threshold at Sat 00:00 UTC)")
    print("=" * 100)

    # Header
    print(f"\n{'DVOL Filter':<18} {'N':>6} {'Avg |Move|':>12} {'Med |Move|':>12} "
          f"{'P(±3%)':>12} {'P(±4%)':>12} {'Worst Move':>14}")
    print("-" * 100)

    # Unconditional first
    n = len(events)
    print(f"{'(no filter)':<18} {n:>6} "
          f"{events['abs_move_pct'].mean():>11.2f}% "
          f"{events['abs_move_pct'].median():>11.2f}% "
          f"{(events['abs_move_pct'] <= 3).mean()*100:>11.1f}% "
          f"{(events['abs_move_pct'] <= 4).mean()*100:>11.1f}% "
          f"{events['move_pct'].abs().max():>13.2f}%")

    for thr in DVOL_THRESHOLDS:
        sub = events[events["dvol"] < thr]
        n = len(sub)
        if n == 0:
            print(f"{'DVOL < ' + str(thr):<18} {n:>6}  (no samples)")
            continue
        avg_abs = sub["abs_move_pct"].mean()
        med_abs = sub["abs_move_pct"].median()
        p3 = (sub["abs_move_pct"] <= 3).mean() * 100
        p4 = (sub["abs_move_pct"] <= 4).mean() * 100
        worst = sub["move_pct"].abs().max()
        print(f"{'DVOL < ' + str(thr):<18} {n:>6} "
              f"{avg_abs:>11.2f}% "
              f"{med_abs:>11.2f}% "
              f"{p3:>11.1f}% "
              f"{p4:>11.1f}% "
              f"{worst:>13.2f}%")

    # Show distribution by DVOL bucket as well
    print("\n" + "-" * 100)
    print("Move distribution within each DVOL filter (with worst losers shown)")
    print("-" * 100)

    for thr in DVOL_THRESHOLDS:
        sub = events[events["dvol"] < thr].copy()
        if len(sub) == 0:
            continue
        # Identify breakers of the bands
        breaks_3 = sub[sub["abs_move_pct"] > 3].sort_values("abs_move_pct", ascending=False)
        breaks_4 = sub[sub["abs_move_pct"] > 4].sort_values("abs_move_pct", ascending=False)
        print(f"\n  DVOL < {thr}: n={len(sub)}, "
              f"breakers ±3%: {len(breaks_3)} ({len(breaks_3)/len(sub)*100:.1f}%), "
              f"breakers ±4%: {len(breaks_4)} ({len(breaks_4)/len(sub)*100:.1f}%)")
        if len(breaks_4) > 0:
            print(f"    Top ±4% breakers (move | dvol):")
            for _, r in breaks_4.head(5).iterrows():
                direction = "↑" if r["move_pct"] > 0 else "↓"
                print(f"      {r['weekend_start'].date()} {direction} {r['move_pct']:+6.2f}%  dvol={r['dvol']:.1f}")

    # Save the raw events data
    out = PROJECT_ROOT / "results" / "weekend_iron_condor_probabilities.csv"
    out.parent.mkdir(exist_ok=True)
    events.to_csv(out, index=False)
    print(f"\nRaw events saved to: {out}")

    print("\n" + "=" * 100)
    print("Notes:")
    print("  - 'Sat 00:01' approximated as Sat 00:00 UTC (1-min difference is negligible)")
    print("  - DVOL is Deribit BTC volatility index (annualized %, ATM ~30-day IV)")
    print("  - Window length = ~56 hours (Sat 00:00 to Mon 08:00 UTC)")
    print("  - For an iron condor: P(±X%) = probability the strategy expires worthless (max profit)")
    print("=" * 100)


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    btc_df = fetch_btc_hourly()
    dvol_df = fetch_dvol_hourly()
    events = extract_weekend_events(btc_df, dvol_df)
    analyze(events)


if __name__ == "__main__":
    main()
