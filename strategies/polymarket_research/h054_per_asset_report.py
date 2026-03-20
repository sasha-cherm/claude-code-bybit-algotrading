"""
H-054 Per-Asset Independent Report

Analyzes each asset's hourly candle direction independently.
Reports only statistically significant hours per asset.
Format: ASSET 1H: HH:00 XX% UP/DOWN (p=X.XXXX, train YY% / test ZZ%)

Statistical significance criteria:
  - p < 0.05 vs 50% (binomial test)
  - Consistent direction in both train and test halves
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import numpy as np
import pandas as pd
from scipy import stats
from lib.data_fetch import fetch_and_cache


ASSETS = {
    "BTC": "BTC/USDT",
    "ETH": "ETH/USDT",
    "SOL": "SOL/USDT",
    "XRP": "XRP/USDT",
    "DOGE": "DOGE/USDT",
    "HYPE": "HYPE/USDT",
    "BNB": "BNB/USDT",
}


def analyze_asset(name, symbol, timeframe="1h", limit_days=730):
    """Analyze green/red candle probability per hour for one asset."""
    try:
        df = fetch_and_cache(symbol, timeframe, limit_days=limit_days)
    except Exception as e:
        print(f"  WARNING: Could not fetch {symbol} {timeframe}: {e}")
        return None

    if df is None or len(df) < 200:
        print(f"  WARNING: Insufficient data for {symbol} {timeframe}")
        return None

    df["return"] = df["close"].pct_change()
    df["green"] = (df["return"] > 0).astype(int)
    df = df.dropna(subset=["return"])

    if timeframe == "1h":
        df["slot"] = df.index.hour
    elif timeframe == "4h":
        df["slot"] = df.index.hour
    else:
        return None

    n_bars = len(df)
    date_range = f"{df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}"

    # Train/test split
    split = len(df) // 2
    train = df.iloc[:split]
    test = df.iloc[split:]

    significant_slots = []
    all_slots = []

    for slot in sorted(df["slot"].unique()):
        subset = df[df["slot"] == slot]
        n = len(subset)
        if n < 50:
            continue

        n_green = int(subset["green"].sum())
        green_rate = n_green / n

        # Binomial test vs 50%
        pval = stats.binomtest(n_green, n, 0.5).pvalue

        # Train/test rates
        train_sub = train[train["slot"] == slot]
        test_sub = test[test["slot"] == slot]
        train_green = train_sub["green"].mean() if len(train_sub) > 0 else np.nan
        test_green = test_sub["green"].mean() if len(test_sub) > 0 else np.nan

        # Check consistency: both halves agree on direction
        consistent = False
        if not np.isnan(train_green) and not np.isnan(test_green):
            consistent = (train_green > 0.5 and test_green > 0.5) or \
                         (train_green < 0.5 and test_green < 0.5)

        direction = "UP" if green_rate > 0.5 else "DOWN"
        rate = green_rate if green_rate > 0.5 else (1 - green_rate)

        entry = {
            "slot": slot,
            "n": n,
            "green_rate": green_rate,
            "direction": direction,
            "rate": rate,
            "pval": pval,
            "train_green": train_green,
            "test_green": test_green,
            "consistent": consistent,
        }
        all_slots.append(entry)

        if pval < 0.05 and consistent:
            significant_slots.append(entry)

    return {
        "asset": name,
        "timeframe": timeframe,
        "n_bars": n_bars,
        "date_range": date_range,
        "significant": significant_slots,
        "all_slots": all_slots,
    }


def main():
    print("=" * 80)
    print("  H-054: PER-ASSET INDEPENDENT HOURLY CANDLE DIRECTION REPORT")
    print("  Criteria: p < 0.05 (binomial vs 50%) AND consistent train/test direction")
    print("=" * 80)

    for timeframe in ["1h", "4h"]:
        tf_label = "1H" if timeframe == "1h" else "4H"
        print(f"\n{'='*80}")
        print(f"  TIMEFRAME: {tf_label}")
        print(f"{'='*80}")

        for name, symbol in ASSETS.items():
            result = analyze_asset(name, symbol, timeframe)
            if result is None:
                print(f"\n  {name} {tf_label}: NO DATA")
                continue

            sig = result["significant"]
            if not sig:
                print(f"\n  {name} {tf_label}: no statistically significant hours "
                      f"({result['n_bars']} bars, {result['date_range']})")
                continue

            # Sort by p-value (strongest first)
            sig.sort(key=lambda x: x["pval"])

            # Bonferroni threshold for this asset
            n_tests = len(result["all_slots"])
            bonf_thresh = 0.05 / n_tests

            print(f"\n  {name} {tf_label} ({result['n_bars']} bars, {result['date_range']}):")
            for s in sig:
                if timeframe == "1h":
                    slot_str = f"{s['slot']:02d}:00 UTC"
                else:
                    slot_str = f"{s['slot']:02d}:00-{s['slot']+4:02d}:00 UTC"

                train_dir_rate = s["train_green"] if s["direction"] == "UP" else (1 - s["train_green"])
                test_dir_rate = s["test_green"] if s["direction"] == "UP" else (1 - s["test_green"])

                bonf_marker = " ***BONFERRONI" if s["pval"] < bonf_thresh else ""

                print(f"    {slot_str}  {s['rate']:.1%} {s['direction']}  "
                      f"(p={s['pval']:.4f}, n={s['n']}, "
                      f"train {train_dir_rate:.1%} / test {test_dir_rate:.1%})"
                      f"{bonf_marker}")

    # Summary table
    print(f"\n\n{'='*80}")
    print("  SUMMARY: ALL SIGNIFICANT HOURS BY ASSET")
    print(f"{'='*80}")
    print(f"  {'Asset':<6} {'TF':<4} {'Hour':<16} {'Dir':<5} {'Rate':<7} {'p-value':<10} {'Train':<7} {'Test':<7} {'Bonf':<5}")
    print("  " + "-" * 75)

    all_significant = []
    for timeframe in ["1h", "4h"]:
        for name, symbol in ASSETS.items():
            result = analyze_asset(name, symbol, timeframe)
            if result is None:
                continue
            for s in result["significant"]:
                s["asset"] = name
                s["timeframe"] = timeframe
                all_significant.append(s)

    all_significant.sort(key=lambda x: x["pval"])

    for s in all_significant:
        tf_label = "1H" if s["timeframe"] == "1h" else "4H"
        if s["timeframe"] == "1h":
            slot_str = f"{s['slot']:02d}:00 UTC"
        else:
            slot_str = f"{s['slot']:02d}:00-{s['slot']+4:02d}:00"

        train_dir_rate = s["train_green"] if s["direction"] == "UP" else (1 - s["train_green"])
        test_dir_rate = s["test_green"] if s["direction"] == "UP" else (1 - s["test_green"])

        # Check Bonferroni (24 tests for 1h, 6 for 4h)
        n_tests = 24 if s["timeframe"] == "1h" else 6
        bonf = "YES" if s["pval"] < 0.05 / n_tests else ""

        print(f"  {s['asset']:<6} {tf_label:<4} {slot_str:<16} {s['direction']:<5} "
              f"{s['rate']:<6.1%}  {s['pval']:<10.6f} {train_dir_rate:<6.1%}  "
              f"{test_dir_rate:<6.1%}  {bonf}")

    print(f"\n  Total significant findings: {len(all_significant)}")
    print(f"  Bonferroni survivors: {sum(1 for s in all_significant if s['pval'] < 0.05 / (24 if s['timeframe'] == '1h' else 6))}")
    print(f"\n  Note: 'Bonferroni' means p < 0.05/{'{n_tests}'} — survives multiple testing correction")
    print(f"  All results require BOTH p < 0.05 AND consistent direction in train/test halves")


if __name__ == "__main__":
    main()
