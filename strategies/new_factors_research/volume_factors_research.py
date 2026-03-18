"""
Volume-Based Cross-Sectional Factor Research (Session 2026-03-18, session 28)

Three new volume-based factors using existing OHLCV data:

H-021: Volume Momentum Factor
  - Long assets with highest relative volume growth, short lowest
  - High volume precedes price moves (attention/liquidity signal)

H-022: Amihud Illiquidity Premium
  - Long illiquid assets (high |return|/volume), short liquid assets
  - Academic: illiquidity premium compensates for transaction cost risk

H-023: Price-Volume Confirmation (Smart Money)
  - Long assets where momentum AND volume agree (confirmed trends)
  - Short assets where momentum positive but volume declining (fake breakouts)
  - Combines price and volume dimensions
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from strategies.new_factors_research.research import (
    load_all_data, run_xs_factor, compute_metrics,
    rolling_walk_forward, compute_correlation_with_h012,
    ASSETS, BASE_FEE, SLIPPAGE_BPS, INITIAL_CAPITAL,
)
from lib.metrics import sharpe_ratio, max_drawdown, annual_return


# ═══════════════════════════════════════════════════════════════════════
# H-021: Volume Momentum Factor
# ═══════════════════════════════════════════════════════════════════════

def h021_volume_momentum(daily_data):
    """
    Cross-sectional volume momentum:
    Long assets with highest relative volume growth, short lowest.
    Ranking: ratio of short-term volume to long-term volume (volume surge).
    """
    print("\n" + "=" * 70)
    print("H-021: VOLUME MOMENTUM FACTOR (Cross-Sectional)")
    print("=" * 70)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().dropna()

    # Align
    common = closes.columns.intersection(volumes.columns)
    closes = closes[common]
    volumes = volumes[common]
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    results = []
    for short_window in [3, 5, 7, 10]:
        for long_window in [20, 30, 60]:
            if short_window >= long_window:
                continue
            for rebal_freq in [3, 5, 7, 14, 21]:
                for n_long in [3, 4, 5]:
                    # Volume momentum: short-term avg volume / long-term avg volume
                    vol_short = volumes.rolling(short_window).mean()
                    vol_long = volumes.rolling(long_window).mean()
                    ranking = vol_short / vol_long  # >1 means volume expanding
                    warmup = long_window + 10

                    res = run_xs_factor(closes, ranking, rebal_freq, n_long,
                                        warmup=warmup)
                    tag = f"VS{short_window}_VL{long_window}_R{rebal_freq}_N{n_long}"
                    results.append({
                        "tag": tag, "short_window": short_window,
                        "long_window": long_window, "rebal": rebal_freq,
                        "n_long": n_long,
                        **{k: v for k, v in res.items() if k != "equity"},
                    })
                    if res["sharpe"] > 0.5:
                        print(f"  ** {tag}: Sharpe {res['sharpe']:.2f}, "
                              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"\n  Total params: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.2f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.2f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}")

    return df, closes, volumes


# ═══════════════════════════════════════════════════════════════════════
# H-022: Amihud Illiquidity Premium
# ═══════════════════════════════════════════════════════════════════════

def h022_amihud_illiquidity(daily_data):
    """
    Cross-sectional illiquidity premium:
    Long illiquid assets, short liquid assets.
    Amihud measure: avg(|daily return| / daily dollar volume) over window.
    """
    print("\n" + "=" * 70)
    print("H-022: AMIHUD ILLIQUIDITY PREMIUM (Cross-Sectional)")
    print("=" * 70)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().dropna()

    common = closes.columns.intersection(volumes.columns)
    closes = closes[common]
    volumes = volumes[common]
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    daily_rets = closes.pct_change()
    # Dollar volume = close * volume (approximate)
    dollar_volume = closes * volumes

    results = []
    for illiq_window in [10, 20, 30, 60]:
        for rebal_freq in [5, 7, 14, 21]:
            for n_long in [3, 4, 5]:
                # Amihud: avg(|return| / dollar_volume) — higher = more illiquid
                # We want to long illiquid (high Amihud) and short liquid (low Amihud)
                amihud = (daily_rets.abs() / dollar_volume).rolling(illiq_window).mean()
                ranking = amihud  # high Amihud = illiquid = long
                warmup = illiq_window + 10

                res = run_xs_factor(closes, ranking, rebal_freq, n_long,
                                    warmup=warmup)
                tag = f"A{illiq_window}_R{rebal_freq}_N{n_long}"
                results.append({
                    "tag": tag, "illiq_window": illiq_window,
                    "rebal": rebal_freq, "n_long": n_long,
                    **{k: v for k, v in res.items() if k != "equity"},
                })
                if res["sharpe"] > 0.5:
                    print(f"  ** {tag}: Sharpe {res['sharpe']:.2f}, "
                          f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"\n  Total params: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.2f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.2f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}")

    return df, closes, volumes


# ═══════════════════════════════════════════════════════════════════════
# H-023: Price-Volume Confirmation (Smart Money)
# ═══════════════════════════════════════════════════════════════════════

def h023_price_volume_confirmation(daily_data):
    """
    Cross-sectional price-volume confirmation:
    Long assets with momentum + volume confirmation (price up, volume up).
    Short assets with momentum but declining volume (exhaustion/fake).

    Ranking: momentum * volume_change (positive when both agree).
    """
    print("\n" + "=" * 70)
    print("H-023: PRICE-VOLUME CONFIRMATION (Cross-Sectional)")
    print("=" * 70)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    volumes = pd.DataFrame({sym: df["volume"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    volumes = volumes.reindex(closes.index).ffill().dropna()

    common = closes.columns.intersection(volumes.columns)
    closes = closes[common]
    volumes = volumes[common]
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    results = []
    for mom_window in [10, 20, 30, 60]:
        for vol_window in [10, 20, 30]:
            for rebal_freq in [5, 7, 14, 21]:
                for n_long in [3, 4]:
                    # Price momentum (return over window)
                    momentum = closes.pct_change(mom_window)
                    # Volume momentum (ratio of recent vol to longer-term avg)
                    vol_change = volumes.rolling(vol_window).mean() / volumes.rolling(max(vol_window * 3, 60)).mean()

                    # Ranking: momentum * volume_change
                    # Positive momentum + rising volume = strong long signal
                    # Negative momentum + rising volume = strong short signal
                    ranking = momentum * vol_change
                    warmup = max(mom_window, vol_window * 3, 60) + 10

                    res = run_xs_factor(closes, ranking, rebal_freq, n_long,
                                        warmup=warmup)
                    tag = f"M{mom_window}_V{vol_window}_R{rebal_freq}_N{n_long}"
                    results.append({
                        "tag": tag, "mom_window": mom_window,
                        "vol_window": vol_window, "rebal": rebal_freq,
                        "n_long": n_long,
                        **{k: v for k, v in res.items() if k != "equity"},
                    })
                    if res["sharpe"] > 0.5:
                        print(f"  ** {tag}: Sharpe {res['sharpe']:.2f}, "
                              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"\n  Total params: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.2f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.2f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}")

    return df, closes, volumes


# ═══════════════════════════════════════════════════════════════════════
# Walk-Forward + Correlation Analysis for Promising Factors
# ═══════════════════════════════════════════════════════════════════════

def deep_validate_factor(name, closes, volumes, ranking_fn, best_params):
    """Run walk-forward and correlation analysis for a promising factor."""
    print(f"\n{'█' * 70}")
    print(f"DEEP VALIDATION: {name}")
    print(f"{'█' * 70}")

    rebal = int(best_params["rebal"])
    n_long = int(best_params["n_long"])

    # 1. Walk-forward
    def factor_fn(c):
        return ranking_fn(c, volumes.reindex(c.index))

    wf = rolling_walk_forward(
        closes, factor_fn,
        {"rebal_freq": rebal, "n_long": n_long},
        n_folds=8, train_days=180, test_days=80,
    )

    if wf is not None:
        pos_folds = (wf["sharpe"] > 0).sum()
        mean_oos = wf["sharpe"].mean()
        print(f"\n  Walk-forward: {pos_folds}/{len(wf)} positive, mean OOS Sharpe {mean_oos:.2f}")

    # 2. Correlation with H-012 (momentum)
    ranking = factor_fn(closes)
    corr_h012 = compute_correlation_with_h012(
        closes, ranking, rebal, n_long,
        warmup=70
    )
    print(f"  Correlation with H-012 (momentum): {corr_h012}")

    # 3. Correlation with H-019 (low-vol)
    daily_rets = closes.pct_change()
    vol_ranking = -daily_rets.rolling(20).std()
    res_new = run_xs_factor(closes, ranking, rebal, n_long, warmup=70)
    res_h019 = run_xs_factor(closes, vol_ranking, 21, 3, warmup=30)

    rets_new = res_new["equity"].pct_change().dropna()
    rets_h019 = res_h019["equity"].pct_change().dropna()
    common_idx = rets_new.index.intersection(rets_h019.index)
    if len(common_idx) > 50:
        corr_h019 = round(rets_new.loc[common_idx].corr(rets_h019.loc[common_idx]), 3)
    else:
        corr_h019 = 0.0
    print(f"  Correlation with H-019 (low-vol): {corr_h019}")

    # 4. Fee robustness
    fee_results = []
    for fee_mult in [1.0, 2.0, 3.0, 5.0]:
        res = run_xs_factor(closes, ranking, rebal, n_long,
                            warmup=70, fee_multiplier=fee_mult)
        fee_results.append({
            "fee_mult": fee_mult,
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
        })
    fee_df = pd.DataFrame(fee_results)
    print(f"\n  Fee sensitivity:")
    for _, row in fee_df.iterrows():
        print(f"    {row['fee_mult']:.0f}x fees: Sharpe {row['sharpe']:.2f}, "
              f"Ann {row['annual_ret']:.1%}")

    return {
        "walk_forward": wf,
        "corr_h012": corr_h012,
        "corr_h019": corr_h019,
        "fee_results": fee_df,
    }


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Loading data...")
    hourly, daily = load_all_data()
    print(f"\nLoaded {len(daily)} assets")

    # ── H-021: Volume Momentum ──
    print("\n" + "█" * 70)
    print("FACTOR 1: H-021 VOLUME MOMENTUM")
    print("█" * 70)
    h021_results, h021_closes, h021_volumes = h021_volume_momentum(daily)

    # ── H-022: Amihud Illiquidity ──
    print("\n" + "█" * 70)
    print("FACTOR 2: H-022 AMIHUD ILLIQUIDITY")
    print("█" * 70)
    h022_results, h022_closes, h022_volumes = h022_amihud_illiquidity(daily)

    # ── H-023: Price-Volume Confirmation ──
    print("\n" + "█" * 70)
    print("FACTOR 3: H-023 PRICE-VOLUME CONFIRMATION")
    print("█" * 70)
    h023_results, h023_closes, h023_volumes = h023_price_volume_confirmation(daily)

    # ── Summary ──
    print("\n" + "█" * 70)
    print("SUMMARY")
    print("█" * 70)

    factor_data = [
        ("H-021 VolMom", h021_results, h021_closes, h021_volumes),
        ("H-022 Amihud", h022_results, h022_closes, h022_volumes),
        ("H-023 PV-Confirm", h023_results, h023_closes, h023_volumes),
    ]

    for name, df, _, _ in factor_data:
        if df is not None and len(df) > 0:
            pos_pct = (df["sharpe"] > 0).mean()
            print(f"\n  {name}:")
            print(f"    Params tested: {len(df)}")
            print(f"    Positive Sharpe: {pos_pct:.0%}")
            print(f"    Mean Sharpe: {df['sharpe'].mean():.2f}")
            print(f"    Best Sharpe: {df['sharpe'].max():.2f}")
            print(f"    Best Annual: {df['annual_ret'].max():.1%}")

    # ── Deep validation for promising factors ──
    print("\n" + "█" * 70)
    print("DEEP VALIDATION (factors with ≥40% positive Sharpe)")
    print("█" * 70)

    validated = []

    for name, df, closes, volumes in factor_data:
        if df is None or len(df) == 0:
            continue
        pos_rate = (df["sharpe"] > 0).mean()
        if pos_rate < 0.40:
            print(f"\n  {name}: {pos_rate:.0%} positive — SKIPPED (< 40%)")
            continue

        best = df.nlargest(1, "sharpe").iloc[0]
        print(f"\n  {name}: {pos_rate:.0%} positive — VALIDATING")
        print(f"    Best params: {best['tag']}, Sharpe {best['sharpe']:.2f}, "
              f"Ann {best['annual_ret']:.1%}, DD {best['max_dd']:.1%}")

        # Create ranking function based on factor type
        if "H-021" in name:
            sw = int(best["short_window"])
            lw = int(best["long_window"])
            def ranking_fn(c, v):
                vs = v.rolling(sw).mean()
                vl = v.rolling(lw).mean()
                return vs / vl
        elif "H-022" in name:
            iw = int(best["illiq_window"])
            def ranking_fn(c, v):
                dr = c.pct_change()
                dv = c * v
                return (dr.abs() / dv).rolling(iw).mean()
        elif "H-023" in name:
            mw = int(best["mom_window"])
            vw = int(best["vol_window"])
            def ranking_fn(c, v):
                mom = c.pct_change(mw)
                vc = v.rolling(vw).mean() / v.rolling(max(vw * 3, 60)).mean()
                return mom * vc

        validation = deep_validate_factor(name, closes, volumes, ranking_fn, best)
        validated.append((name, best, validation))

    # ── Final Summary ──
    print("\n" + "█" * 70)
    print("FINAL RESULTS")
    print("█" * 70)

    for name, best, val in validated:
        wf = val["walk_forward"]
        if wf is not None:
            pos = (wf["sharpe"] > 0).sum()
            total = len(wf)
            mean_oos = wf["sharpe"].mean()
        else:
            pos, total, mean_oos = 0, 0, -99

        fee_at_3x = val["fee_results"][val["fee_results"]["fee_mult"] == 3.0]
        fee_sharpe_3x = fee_at_3x["sharpe"].iloc[0] if len(fee_at_3x) > 0 else -99

        status = "PROMISING" if pos >= total * 0.5 and mean_oos > 0.3 and fee_sharpe_3x > 0 else "REJECTED"
        print(f"\n  {name}: {status}")
        print(f"    Best IS: Sharpe {best['sharpe']:.2f}, Ann {best['annual_ret']:.1%}")
        print(f"    Walk-forward: {pos}/{total} positive, mean OOS Sharpe {mean_oos:.2f}")
        print(f"    Fee robust (3x): Sharpe {fee_sharpe_3x:.2f}")
        print(f"    Corr H-012: {val['corr_h012']}, Corr H-019: {val['corr_h019']}")

    if not validated:
        print("\n  No factors passed the initial screen (≥40% positive Sharpe)")
        print("  Volume-based factors may not contain alpha in crypto cross-section.")

    print("\nDone.")
