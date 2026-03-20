"""
H-054: Multi-Asset Polymarket Hourly + 4H Candle Direction Analysis

Analyzes the probability of green/red candles at each hour (1h) and 4h block
for all Polymarket assets: BTC, ETH, SOL, XRP, DOGE, HYPE, BNB.

Tests statistical significance via binomial test and validates with train/test split.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
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

TIMEFRAMES = ["1h", "4h"]


def analyze_asset_timeframe(name, symbol, timeframe, limit_days=730):
    """Analyze green/red candle probability per time slot for one asset+timeframe."""
    try:
        df = fetch_and_cache(symbol, timeframe, limit_days=limit_days)
    except Exception as e:
        print(f"  WARNING: Could not fetch {symbol} {timeframe}: {e}")
        return None

    if df is None or len(df) < 200:
        print(f"  WARNING: Insufficient data for {symbol} {timeframe} ({len(df) if df is not None else 0} bars)")
        return None

    df["return"] = df["close"].pct_change()
    df["green"] = (df["return"] > 0).astype(int)
    df = df.dropna(subset=["return"])

    if timeframe == "1h":
        df["slot"] = df.index.hour
        n_slots = 24
        slot_label = "hour"
    elif timeframe == "4h":
        df["slot"] = df.index.hour  # 0, 4, 8, 12, 16, 20
        n_slots = 6
        slot_label = "4h_block"
    else:
        return None

    n_bars = len(df)
    date_range = f"{df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}"

    # Overall baseline
    overall_green = df["green"].mean()

    # Per-slot analysis
    slot_stats = []
    for slot in sorted(df["slot"].unique()):
        subset = df[df["slot"] == slot]
        n = len(subset)
        if n < 50:
            continue
        n_green = int(subset["green"].sum())
        green_rate = n_green / n
        mean_ret = subset["return"].mean()

        # Binomial test: H0: P(green) = 0.5
        pval = stats.binomtest(n_green, n, 0.5).pvalue

        # Also test vs overall green rate (some assets trend up, baseline != 50%)
        pval_vs_base = stats.binomtest(n_green, n, overall_green).pvalue

        slot_stats.append({
            "slot": int(slot),
            "n": n,
            "n_green": n_green,
            "green_rate": green_rate,
            "mean_ret": mean_ret,
            "pval_vs_50": pval,
            "pval_vs_base": pval_vs_base,
            "direction": "GREEN" if green_rate > 0.5 else "RED",
            "edge_vs_50": abs(green_rate - 0.5),
        })

    if not slot_stats:
        return None

    stats_df = pd.DataFrame(slot_stats)

    # Train/test split validation
    split = len(df) // 2
    train = df.iloc[:split]
    test = df.iloc[split:]

    train_green = train.groupby("slot")["green"].mean()
    test_green = test.groupby("slot")["green"].mean()
    common = train_green.index.intersection(test_green.index)

    if len(common) >= 3:
        tt_corr = train_green.loc[common].corr(test_green.loc[common])
    else:
        tt_corr = np.nan

    # Count consistent direction slots
    consistent = 0
    for s in common:
        if (train_green[s] > 0.5 and test_green[s] > 0.5) or \
           (train_green[s] < 0.5 and test_green[s] < 0.5):
            consistent += 1

    # Train/test per-slot details
    for row in slot_stats:
        s = row["slot"]
        row["train_green"] = float(train_green.get(s, np.nan))
        row["test_green"] = float(test_green.get(s, np.nan))
        train_ok = train_green.get(s, 0.5) > 0.5
        test_ok = test_green.get(s, 0.5) > 0.5
        row["consistent"] = (train_ok == test_ok)

    return {
        "asset": name,
        "symbol": symbol,
        "timeframe": timeframe,
        "n_bars": n_bars,
        "date_range": date_range,
        "overall_green": overall_green,
        "train_test_corr": tt_corr,
        "consistent_slots": consistent,
        "total_slots": len(common),
        "slots": slot_stats,
    }


def print_results(result):
    """Pretty-print results for one asset+timeframe."""
    if result is None:
        return

    name = result["asset"]
    tf = result["timeframe"]
    slot_label = "Hour" if tf == "1h" else "4H Block"

    print(f"\n{'='*80}")
    print(f"  {name} — {tf} candles")
    print(f"{'='*80}")
    print(f"  Data: {result['n_bars']} bars, {result['date_range']}")
    print(f"  Overall green rate: {result['overall_green']:.1%}")
    print(f"  Train/Test correlation: {result['train_test_corr']:.3f}")
    print(f"  Consistent direction: {result['consistent_slots']}/{result['total_slots']} slots")

    print(f"\n  {slot_label:>6}  {'Green%':>7}  {'N':>5}  {'p(vs50)':>8}  {'p(base)':>8}  "
          f"{'Train':>6}  {'Test':>6}  {'Consist':>7}  {'Sig':>4}")
    print("  " + "-" * 75)

    sig_count = 0
    for row in result["slots"]:
        pval = row["pval_vs_50"]
        sig = "***" if pval < 0.01 else "**" if pval < 0.05 else "*" if pval < 0.10 else ""
        if pval < 0.05:
            sig_count += 1

        slot_str = f"{row['slot']:02d}:00" if tf == "1h" else f"{row['slot']:02d}-{row['slot']+4:02d}"
        consist = "YES" if row.get("consistent", False) else "NO"
        train_g = f"{row.get('train_green', 0):.1%}" if not np.isnan(row.get('train_green', np.nan)) else "N/A"
        test_g = f"{row.get('test_green', 0):.1%}" if not np.isnan(row.get('test_green', np.nan)) else "N/A"

        print(f"  {slot_str:>6}  {row['green_rate']:6.1%}  {row['n']:5d}  "
              f"{row['pval_vs_50']:8.4f}  {row['pval_vs_base']:8.4f}  "
              f"{train_g:>6}  {test_g:>6}  {consist:>7}  {sig}")

    print(f"\n  Significant slots (p < 0.05 vs 50%): {sig_count}/{len(result['slots'])}")

    # Multiple testing correction note
    n_tests = len(result["slots"])
    bonferroni_threshold = 0.05 / n_tests
    print(f"  Bonferroni-corrected threshold (alpha=0.05): p < {bonferroni_threshold:.4f}")

    bonf_count = sum(1 for r in result["slots"] if r["pval_vs_50"] < bonferroni_threshold)
    print(f"  Slots surviving Bonferroni correction: {bonf_count}/{n_tests}")

    # Strong + consistent slots
    strong = [r for r in result["slots"]
              if r["pval_vs_50"] < 0.05 and r.get("consistent", False)]
    if strong:
        print(f"\n  ACTIONABLE slots (p < 0.05 AND consistent train/test):")
        for r in strong:
            slot_str = f"{r['slot']:02d}:00" if tf == "1h" else f"{r['slot']:02d}-{r['slot']+4:02d}"
            print(f"    {slot_str}  →  {r['direction']}  ({r['green_rate']:.1%} green, "
                  f"train {r.get('train_green',0):.1%} / test {r.get('test_green',0):.1%}, "
                  f"p={r['pval_vs_50']:.4f})")
    else:
        print(f"\n  NO actionable slots (none pass both p < 0.05 AND consistent direction)")


def run_full_analysis():
    """Run the complete multi-asset, multi-timeframe analysis."""
    print("=" * 80)
    print("  H-054: MULTI-ASSET POLYMARKET CANDLE DIRECTION ANALYSIS")
    print("  Assets: BTC, ETH, SOL, XRP, DOGE, HYPE, BNB")
    print("  Timeframes: 1h, 4h")
    print("=" * 80)

    all_results = []

    for name, symbol in ASSETS.items():
        for tf in TIMEFRAMES:
            print(f"\n  Fetching {name} ({symbol}) {tf}...")
            result = analyze_asset_timeframe(name, symbol, tf)
            if result:
                all_results.append(result)
                print_results(result)

    # Cross-asset summary
    print("\n\n" + "=" * 80)
    print("  CROSS-ASSET SUMMARY")
    print("=" * 80)

    # Collect all significant hours across all assets
    print("\n  ALL SIGNIFICANT SLOTS (p < 0.05 vs 50%, consistent train/test):")
    print(f"  {'Asset':>6}  {'TF':>3}  {'Slot':>6}  {'Dir':>5}  {'Green%':>7}  "
          f"{'Train':>6}  {'Test':>6}  {'p-val':>8}  {'Edge':>6}")
    print("  " + "-" * 70)

    actionable_all = []
    for result in all_results:
        tf = result["timeframe"]
        for r in result["slots"]:
            if r["pval_vs_50"] < 0.05 and r.get("consistent", False):
                slot_str = f"{r['slot']:02d}:00" if tf == "1h" else f"{r['slot']:02d}-{r['slot']+4:02d}"
                print(f"  {result['asset']:>6}  {tf:>3}  {slot_str:>6}  "
                      f"{r['direction']:>5}  {r['green_rate']:6.1%}  "
                      f"{r.get('train_green',0):5.1%}  {r.get('test_green',0):5.1%}  "
                      f"{r['pval_vs_50']:8.4f}  {r['edge_vs_50']:5.1%}")
                actionable_all.append({
                    "asset": result["asset"],
                    "timeframe": tf,
                    "slot": r["slot"],
                    "direction": r["direction"],
                    "green_rate": r["green_rate"],
                    "train_green": r.get("train_green", 0),
                    "test_green": r.get("test_green", 0),
                    "pval": r["pval_vs_50"],
                    "edge": r["edge_vs_50"],
                })

    if not actionable_all:
        print("  (none)")

    # Check for common patterns across assets at same hour
    print("\n\n  CROSS-ASSET HOUR PATTERNS (1h only — do multiple assets agree on same hour?):")
    hourly_results = [r for r in all_results if r["timeframe"] == "1h"]

    for h in range(24):
        directions = {}
        for result in hourly_results:
            for r in result["slots"]:
                if r["slot"] == h:
                    directions[result["asset"]] = {
                        "green_rate": r["green_rate"],
                        "direction": r["direction"],
                        "pval": r["pval_vs_50"],
                    }

        if not directions:
            continue

        # Count how many assets agree on direction
        green_count = sum(1 for d in directions.values() if d["direction"] == "GREEN")
        red_count = sum(1 for d in directions.values() if d["direction"] == "RED")
        total = len(directions)

        # Only print if strong agreement (>=6 of 7 agree) or any significant
        any_sig = any(d["pval"] < 0.05 for d in directions.values())
        agreement = max(green_count, red_count) / total

        if agreement >= 0.85 or any_sig:
            majority_dir = "GREEN" if green_count > red_count else "RED"
            avg_green = np.mean([d["green_rate"] for d in directions.values()])
            sig_assets = [a for a, d in directions.items() if d["pval"] < 0.05]

            marker = ""
            if agreement >= 0.85:
                marker += f" [CONSENSUS {max(green_count,red_count)}/{total}]"
            if sig_assets:
                marker += f" [SIG: {','.join(sig_assets)}]"

            print(f"  {h:02d}:00  majority={majority_dir}  agree={max(green_count,red_count)}/{total}  "
                  f"avg_green={avg_green:.1%}{marker}")

    # 4h cross-asset patterns
    print("\n\n  CROSS-ASSET 4H BLOCK PATTERNS:")
    fourh_results = [r for r in all_results if r["timeframe"] == "4h"]
    for h in [0, 4, 8, 12, 16, 20]:
        directions = {}
        for result in fourh_results:
            for r in result["slots"]:
                if r["slot"] == h:
                    directions[result["asset"]] = {
                        "green_rate": r["green_rate"],
                        "direction": r["direction"],
                        "pval": r["pval_vs_50"],
                    }

        if not directions:
            continue

        green_count = sum(1 for d in directions.values() if d["direction"] == "GREEN")
        red_count = sum(1 for d in directions.values() if d["direction"] == "RED")
        total = len(directions)
        avg_green = np.mean([d["green_rate"] for d in directions.values()])
        sig_assets = [a for a, d in directions.items() if d["pval"] < 0.05]
        majority_dir = "GREEN" if green_count > red_count else "RED"
        agreement = max(green_count, red_count) / total

        marker = ""
        if agreement >= 0.85:
            marker += f" [CONSENSUS {max(green_count,red_count)}/{total}]"
        if sig_assets:
            marker += f" [SIG: {','.join(sig_assets)}]"

        print(f"  {h:02d}-{h+4:02d}  majority={majority_dir}  agree={max(green_count,red_count)}/{total}  "
              f"avg_green={avg_green:.1%}{marker}")

    # Multiple testing summary
    print("\n\n  MULTIPLE TESTING WARNING")
    print("  " + "-" * 60)
    total_tests_1h = sum(len(r["slots"]) for r in all_results if r["timeframe"] == "1h")
    total_tests_4h = sum(len(r["slots"]) for r in all_results if r["timeframe"] == "4h")
    total_tests = total_tests_1h + total_tests_4h
    expected_false_positives = total_tests * 0.05
    print(f"  Total tests performed: {total_tests} ({total_tests_1h} hourly + {total_tests_4h} 4h)")
    print(f"  Expected false positives at p<0.05: {expected_false_positives:.1f}")
    sig_total = sum(1 for r in all_results for s in r["slots"] if s["pval_vs_50"] < 0.05)
    print(f"  Actual significant results: {sig_total}")
    print(f"  Ratio actual/expected: {sig_total/expected_false_positives:.2f}x" if expected_false_positives > 0 else "")

    if sig_total <= expected_false_positives * 1.5:
        print(f"  VERDICT: Significant results are within ~1.5x of what's expected by chance.")
        print(f"           This suggests NO robust systematic pattern across all assets.")
    else:
        print(f"  VERDICT: More significant results than expected by chance alone.")
        print(f"           Some patterns may be real, especially those consistent in train/test.")

    # Save results
    output = {
        "summary": {
            "total_tests": total_tests,
            "significant_count": sig_total,
            "expected_false_positives": expected_false_positives,
            "actionable_count": len(actionable_all),
        },
        "actionable": actionable_all,
        "full_results": []
    }
    for result in all_results:
        output["full_results"].append({
            "asset": result["asset"],
            "timeframe": result["timeframe"],
            "n_bars": result["n_bars"],
            "date_range": result["date_range"],
            "overall_green": result["overall_green"],
            "train_test_corr": float(result["train_test_corr"]) if not np.isnan(result["train_test_corr"]) else None,
            "consistent_slots": result["consistent_slots"],
            "total_slots": result["total_slots"],
            "slots": result["slots"],
        })

    outpath = os.path.join(os.path.dirname(__file__), "h054_results.json")
    with open(outpath, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Results saved to {outpath}")

    return all_results, actionable_all


if __name__ == "__main__":
    run_full_analysis()
