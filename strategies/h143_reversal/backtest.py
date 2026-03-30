"""
H-143: Short-Term Reversal Factor (Cross-Sectional)

Classic contrarian play: assets that dropped most over L days tend to mean-revert.
- Compute L-day return for each asset
- REVERSAL (default): LONG bottom N (most oversold), SHORT top N (most overbought)
- MOMENTUM (comparison): LONG top N (best performers), SHORT bottom N (worst)

Differences vs H-077:
  - Broader lookback grid: [1,2,3,5,7,10] (adds very short 1-2d)
  - Rebalance grid: [1,2,3,5]
  - N grid: [3,4,5]
  - Both directions tested (reversal + momentum comparison)
  - Expanding-window walk-forward (6 folds, train >=360d, test 60d each)
  - Split-half Sharpe-rank correlation
  - H-012 correlation check

Walk-forward: 6 expanding folds, min 360d train, 60d test.
"""

import json
import sys
from pathlib import Path
from itertools import product
from scipy.stats import spearmanr

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
    "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT", "ATOM/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "SUI/USDT",
]

BASE_FEE   = 0.001      # 10 bps taker fee per side
SLIPPAGE   = 0.0002     # 2 bps slippage per side
INITIAL_CAPITAL = 10_000.0

# Parameter grid
LOOKBACKS    = [1, 2, 3, 5, 7, 10]
REBAL_FREQS  = [1, 2, 3, 5]
N_TOP_BOTTOM = [3, 4, 5]
DIRECTIONS   = ["reversal", "momentum"]   # reversal = long losers, momentum = long winners

# Walk-forward: expanding window
WF_FOLDS      = 6
WF_MIN_TRAIN  = 360   # min training days per fold
WF_TEST_DAYS  = 60    # test days per fold


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_daily_closes() -> pd.DataFrame:
    """Load and align daily close prices for all 14 assets."""
    data_dir = ROOT / "data"
    panels = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            panels[sym] = df["close"]
            print(f"  {sym}: {len(df)} daily bars "
                  f"({df.index[0].date()} to {df.index[-1].date()})")
        else:
            h_path = data_dir / f"{safe}_1h.parquet"
            if h_path.exists():
                hdf = pd.read_parquet(h_path)
                daily = hdf["close"].resample("1D").last().dropna()
                panels[sym] = daily
                print(f"  {sym}: {len(daily)} daily bars (resampled from 1h)")
            else:
                print(f"  {sym}: no data — skipped")

    closes = pd.DataFrame(panels).dropna(how="all").ffill().dropna()
    return closes


# ---------------------------------------------------------------------------
# Core backtest engine
# ---------------------------------------------------------------------------

def run_xs_factor(
    closes: pd.DataFrame,
    ranking_series: pd.DataFrame,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    fee_multiplier: float = 1.0,
    warmup: int = 15,
) -> dict:
    """
    Cross-sectional long/short backtest.
    ranking_series: higher value → go long; lower value → go short.
    """
    if n_short is None:
        n_short = n_long

    n = len(closes)
    fee_rate = BASE_FEE * fee_multiplier

    capital   = INITIAL_CAPITAL
    equity    = np.zeros(n)
    equity[0] = capital
    rets_list = []

    prev_weights = pd.Series(0.0, index=closes.columns)

    for i in range(1, n):
        p_now  = closes.iloc[i]
        p_prev = closes.iloc[i - 1]

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = ranking_series.iloc[i - 1].dropna()  # use t-1 signal (no look-ahead)
            if len(ranks) < n_long + n_short:
                port_ret = (prev_weights * (p_now / p_prev - 1)).sum()
                equity[i] = equity[i - 1] * (1 + port_ret)
                rets_list.append(port_ret)
                continue

            ranked = ranks.sort_values(ascending=False)
            longs  = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] -= 1.0 / n_short   # allow partial overlap

            turnover  = (new_weights - prev_weights).abs().sum() / 2
            fee_drag  = turnover * (fee_rate + SLIPPAGE)
            daily_ret = (new_weights * (p_now / p_prev - 1)).sum() - fee_drag

            prev_weights = new_weights
        else:
            daily_ret = (prev_weights * (p_now / p_prev - 1)).sum()

        equity[i] = equity[i - 1] * (1 + daily_ret)
        rets_list.append(daily_ret)

    eq_series = pd.Series(equity, index=closes.index)
    rets = pd.Series(rets_list)

    if len(eq_series) < 30 or eq_series.iloc[-1] <= 0:
        return {"sharpe": -99.0, "annual_ret": 0.0, "max_dd": 1.0,
                "equity": eq_series, "returns": rets}

    eq_clean = eq_series[eq_series > 0]
    r = eq_clean.pct_change().dropna()
    return {
        "sharpe":     round(float(sharpe_ratio(r, periods_per_year=365)), 4),
        "annual_ret": round(float(annual_return(eq_clean, periods_per_year=365)), 4),
        "max_dd":     round(float(max_drawdown(eq_clean)), 4),
        "equity":     eq_series,
        "returns":    pd.Series(eq_clean.pct_change().dropna().values,
                                index=eq_clean.index[1:]),
    }


def build_ranking(closes: pd.DataFrame, lookback: int, direction: str) -> pd.DataFrame:
    """
    Build the signal (ranking) matrix.
    reversal: signal = -returns (losers rank highest → go long)
    momentum: signal = +returns (winners rank highest → go long)
    """
    raw = closes.pct_change(lookback)
    if direction == "reversal":
        return -raw
    else:
        return raw


# ---------------------------------------------------------------------------
# Full parameter scan
# ---------------------------------------------------------------------------

def run_full_scan(closes: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 72)
    print("H-143: FULL PARAMETER SCAN")
    print("=" * 72)
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Grid: lookbacks={LOOKBACKS}, rebal={REBAL_FREQS}, "
          f"N={N_TOP_BOTTOM}, directions={DIRECTIONS}")
    print(f"  Total combos: "
          f"{len(LOOKBACKS)*len(REBAL_FREQS)*len(N_TOP_BOTTOM)*len(DIRECTIONS)}")

    results = []
    for direction, lookback, rebal, n in product(DIRECTIONS, LOOKBACKS, REBAL_FREQS, N_TOP_BOTTOM):
        ranking = build_ranking(closes, lookback, direction)
        warmup  = max(lookback + 3, 10)
        res     = run_xs_factor(closes, ranking, rebal, n, warmup=warmup)

        results.append({
            "direction":  direction,
            "lookback":   lookback,
            "rebal":      rebal,
            "n":          n,
            "tag":        f"{direction[:3].upper()}_L{lookback}_R{rebal}_N{n}",
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
        })

    df = pd.DataFrame(results)

    for direction in DIRECTIONS:
        sub = df[df["direction"] == direction]
        pos = (sub["sharpe"] > 0).sum()
        print(f"\n  [{direction.upper()}] {pos}/{len(sub)} positive Sharpe "
              f"({pos/len(sub):.0%}), "
              f"mean Sharpe {sub['sharpe'].mean():.3f}, "
              f"median {sub['sharpe'].median():.3f}")

    print("\n  Top 10 by Sharpe (all directions):")
    for _, row in df.nlargest(10, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    print("\n  Bottom 5 by Sharpe:")
    for _, row in df.nsmallest(5, "sharpe").iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.3f}")

    return df


# ---------------------------------------------------------------------------
# Walk-forward validation (expanding window)
# ---------------------------------------------------------------------------

def run_walk_forward_expanding(
    closes: pd.DataFrame,
    lookback: int,
    rebal: int,
    n: int,
    direction: str,
) -> pd.DataFrame | None:
    """
    Expanding-window walk-forward:
      Fold k: train on [0, WF_MIN_TRAIN + k*WF_TEST_DAYS), test on next WF_TEST_DAYS.
    6 folds → at least 360d train for fold 0, growing by 60d each fold.
    """
    total = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        train_end   = WF_MIN_TRAIN + fold * WF_TEST_DAYS
        test_start  = train_end
        test_end    = test_start + WF_TEST_DAYS

        if test_end > total:
            print(f"    Fold {fold+1}: insufficient data (need {test_end}, have {total})")
            break

        train_closes = closes.iloc[:train_end]
        test_closes  = closes.iloc[test_start:test_end]

        if len(test_closes) < 20:
            break

        # Compute signal on test slice
        test_ranking = build_ranking(test_closes, lookback, direction)
        warmup = max(lookback + 2, 5)
        res = run_xs_factor(test_closes, test_ranking, rebal, n, warmup=warmup)

        fold_results.append({
            "fold":       fold + 1,
            "train_days": train_end,
            "start":      test_closes.index[0].strftime("%Y-%m-%d"),
            "end":        test_closes.index[-1].strftime("%Y-%m-%d"),
            "n_days":     len(test_closes),
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
        })

    if not fold_results:
        return None

    return pd.DataFrame(fold_results)


# ---------------------------------------------------------------------------
# Split-half Sharpe rank correlation
# ---------------------------------------------------------------------------

def split_half_correlation(closes: pd.DataFrame, direction: str) -> float:
    """
    Split data in half. Compute full-grid Sharpe in each half.
    Spearman rank correlation between first-half and second-half Sharpe vectors.
    """
    mid = len(closes) // 2
    h1  = closes.iloc[:mid]
    h2  = closes.iloc[mid:]

    sharpes_h1, sharpes_h2 = [], []
    for lookback, rebal, n in product(LOOKBACKS, REBAL_FREQS, N_TOP_BOTTOM):
        warmup = max(lookback + 3, 10)

        r1 = build_ranking(h1, lookback, direction)
        s1 = run_xs_factor(h1, r1, rebal, n, warmup=warmup)["sharpe"]

        r2 = build_ranking(h2, lookback, direction)
        s2 = run_xs_factor(h2, r2, rebal, n, warmup=warmup)["sharpe"]

        sharpes_h1.append(s1)
        sharpes_h2.append(s2)

    if len(sharpes_h1) < 5:
        return 0.0

    corr, pval = spearmanr(sharpes_h1, sharpes_h2)
    print(f"  Split-half Spearman rank corr [{direction}]: "
          f"{corr:.3f} (p={pval:.3f})")
    return round(float(corr), 4)


# ---------------------------------------------------------------------------
# Correlation with H-012 (60d momentum)
# ---------------------------------------------------------------------------

def compute_h012_correlation(
    closes: pd.DataFrame,
    lookback: int,
    rebal: int,
    n: int,
    direction: str,
) -> float:
    """
    Compute Pearson correlation of daily returns between the best reversal
    strategy and H-012 (60d cross-sectional momentum, rebal=5, N=4).
    """
    # Best reversal strategy
    ranking_rev = build_ranking(closes, lookback, direction)
    warmup_rev  = max(lookback + 3, 10)
    res_rev     = run_xs_factor(closes, ranking_rev, rebal, n, warmup=warmup_rev)

    # H-012 (60d momentum)
    ranking_mom = closes.pct_change(60)  # momentum ranking
    res_mom     = run_xs_factor(closes, ranking_mom, 5, 4, warmup=65)

    rets_rev = res_rev["returns"].dropna()
    rets_mom = res_mom["returns"].dropna()
    common   = rets_rev.index.intersection(rets_mom.index)

    if len(common) < 30:
        return 0.0

    corr = float(rets_rev.loc[common].corr(rets_mom.loc[common]))
    print(f"  H-012 correlation [{direction} L{lookback}]: {corr:.3f}")
    return round(corr, 4)


# ---------------------------------------------------------------------------
# Fee sensitivity
# ---------------------------------------------------------------------------

def fee_sensitivity(
    closes: pd.DataFrame,
    lookback: int,
    rebal: int,
    n: int,
    direction: str,
) -> list[dict]:
    ranking = build_ranking(closes, lookback, direction)
    warmup  = max(lookback + 3, 10)
    rows = []
    for mult in [1.0, 2.0, 3.0, 5.0]:
        res = run_xs_factor(closes, ranking, rebal, n, warmup=warmup,
                            fee_multiplier=mult)
        rows.append({
            "fee_mult": mult,
            "sharpe":     res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd":     res["max_dd"],
        })
        print(f"    Fee x{mult:.0f}: Sharpe {res['sharpe']:.3f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 72)
    print("H-143: Short-Term Reversal Factor (Cross-Sectional)")
    print("=" * 72)

    print("\nLoading daily closes...")
    closes = load_daily_closes()
    print(f"\nAligned panel: {len(closes.columns)} assets, {len(closes)} days")
    print(f"Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    if len(closes) < 400:
        print("ERROR: insufficient data (need >=400 days)")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # 1. Full parameter scan (both directions)
    # -----------------------------------------------------------------------
    scan_df = run_full_scan(closes)

    # Overall stats
    rev_df = scan_df[scan_df["direction"] == "reversal"]
    mom_df = scan_df[scan_df["direction"] == "momentum"]
    rev_pos_pct = (rev_df["sharpe"] > 0).mean()
    mom_pos_pct = (mom_df["sharpe"] > 0).mean()

    # Best params per direction
    best_rev = rev_df.loc[rev_df["sharpe"].idxmax()]
    best_mom = mom_df.loc[mom_df["sharpe"].idxmax()]

    print(f"\n  Best REVERSAL: {best_rev['tag']}, "
          f"Sharpe {best_rev['sharpe']:.3f}, "
          f"Ann {best_rev['annual_ret']:.1%}, DD {best_rev['max_dd']:.1%}")
    print(f"  Best MOMENTUM: {best_mom['tag']}, "
          f"Sharpe {best_mom['sharpe']:.3f}, "
          f"Ann {best_mom['annual_ret']:.1%}, DD {best_mom['max_dd']:.1%}")

    # -----------------------------------------------------------------------
    # 2. Walk-forward (expanding) — best reversal params
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("EXPANDING WALK-FORWARD — REVERSAL (best params)")
    print("=" * 72)
    wf_rev = run_walk_forward_expanding(
        closes,
        int(best_rev["lookback"]),
        int(best_rev["rebal"]),
        int(best_rev["n"]),
        "reversal",
    )
    if wf_rev is not None:
        for _, row in wf_rev.iterrows():
            print(f"  Fold {int(row['fold'])}: {row['start']} → {row['end']} "
                  f"(train {int(row['train_days'])}d), "
                  f"Sharpe {row['sharpe']:.3f}, Ann {row['annual_ret']:.1%}, "
                  f"DD {row['max_dd']:.1%}")
        wf_pos  = int((wf_rev["sharpe"] > 0).sum())
        wf_mean = round(float(wf_rev["sharpe"].mean()), 3)
        print(f"\n  Positive OOS folds: {wf_pos}/{len(wf_rev)}")
        print(f"  Mean OOS Sharpe: {wf_mean:.3f}")
    else:
        wf_pos, wf_mean = 0, 0.0

    # Walk-forward on best momentum params for comparison
    print("\n" + "=" * 72)
    print("EXPANDING WALK-FORWARD — MOMENTUM (best params, comparison)")
    print("=" * 72)
    wf_mom = run_walk_forward_expanding(
        closes,
        int(best_mom["lookback"]),
        int(best_mom["rebal"]),
        int(best_mom["n"]),
        "momentum",
    )
    if wf_mom is not None:
        for _, row in wf_mom.iterrows():
            print(f"  Fold {int(row['fold'])}: {row['start']} → {row['end']}, "
                  f"Sharpe {row['sharpe']:.3f}")
        wf_mom_pos  = int((wf_mom["sharpe"] > 0).sum())
        wf_mom_mean = round(float(wf_mom["sharpe"].mean()), 3)
        print(f"  Positive OOS folds: {wf_mom_pos}/{len(wf_mom)}, "
              f"mean Sharpe {wf_mom_mean:.3f}")

    # -----------------------------------------------------------------------
    # 3. Split-half Sharpe rank correlation
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("SPLIT-HALF SHARPE RANK CORRELATION")
    print("=" * 72)
    sh_corr_rev = split_half_correlation(closes, "reversal")
    sh_corr_mom = split_half_correlation(closes, "momentum")

    # -----------------------------------------------------------------------
    # 4. Correlation with H-012
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("CORRELATION WITH H-012 (60d momentum)")
    print("=" * 72)
    h012_corr_rev = compute_h012_correlation(
        closes,
        int(best_rev["lookback"]),
        int(best_rev["rebal"]),
        int(best_rev["n"]),
        "reversal",
    )
    h012_corr_mom = compute_h012_correlation(
        closes,
        int(best_mom["lookback"]),
        int(best_mom["rebal"]),
        int(best_mom["n"]),
        "momentum",
    )

    # -----------------------------------------------------------------------
    # 5. Fee sensitivity — best reversal
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("FEE SENSITIVITY — REVERSAL")
    print("=" * 72)
    fee_rows = fee_sensitivity(
        closes,
        int(best_rev["lookback"]),
        int(best_rev["rebal"]),
        int(best_rev["n"]),
        "reversal",
    )

    # -----------------------------------------------------------------------
    # 6. Full verdict & summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("FINAL SUMMARY — H-143: Short-Term Reversal Factor")
    print("=" * 72)

    total_combos = len(scan_df)
    rev_combos   = len(rev_df)
    mom_combos   = len(mom_df)

    print(f"\n  Total param combos tested:     {total_combos}")
    print(f"  Reversal combos:               {rev_combos}")
    print(f"  Momentum combos:               {mom_combos}")
    print(f"\n  IS positive Sharpe (reversal): "
          f"{int(rev_pos_pct*rev_combos)}/{rev_combos} ({rev_pos_pct:.0%})")
    print(f"  IS positive Sharpe (momentum): "
          f"{int(mom_pos_pct*mom_combos)}/{mom_combos} ({mom_pos_pct:.0%})")

    print(f"\n  Best reversal params:          {best_rev['tag']}")
    print(f"    Sharpe:                      {best_rev['sharpe']:.3f}")
    print(f"    Annual return:               {best_rev['annual_ret']:.1%}")
    print(f"    Max drawdown:                {best_rev['max_dd']:.1%}")

    print(f"\n  Best momentum params:          {best_mom['tag']}")
    print(f"    Sharpe:                      {best_mom['sharpe']:.3f}")
    print(f"    Annual return:               {best_mom['annual_ret']:.1%}")
    print(f"    Max drawdown:                {best_mom['max_dd']:.1%}")

    print(f"\n  Walk-forward (reversal):       {wf_pos}/{len(wf_rev) if wf_rev is not None else 0} folds positive")
    print(f"  Mean OOS Sharpe (reversal):    {wf_mean:.3f}")

    print(f"\n  Split-half rank corr (rev):    {sh_corr_rev:.3f}")
    print(f"  Split-half rank corr (mom):    {sh_corr_mom:.3f}")

    print(f"\n  H-012 corr (reversal):         {h012_corr_rev:.3f}")
    print(f"  H-012 corr (momentum):         {h012_corr_mom:.3f}")

    # Acceptance criteria
    crit_is     = rev_pos_pct >= 0.80
    crit_wf     = wf_pos >= 4 if wf_rev is not None else False
    crit_sh     = sh_corr_rev > 0
    crit_h012   = abs(h012_corr_rev) <= 0.40

    print("\n  ---- Acceptance Criteria ----")
    print(f"  IS >=80% positive:             {'PASS' if crit_is else 'FAIL'} "
          f"({rev_pos_pct:.0%})")
    print(f"  WF >=4/6 folds positive:       {'PASS' if crit_wf else 'FAIL'} "
          f"({wf_pos}/{len(wf_rev) if wf_rev is not None else 0})")
    print(f"  Split-half positive:           {'PASS' if crit_sh else 'FAIL'} "
          f"(r={sh_corr_rev:.3f})")
    print(f"  H-012 corr <=0.40:             {'PASS' if crit_h012 else 'FAIL'} "
          f"(r={h012_corr_rev:.3f})")

    all_pass  = crit_is and crit_wf and crit_sh and crit_h012
    pass_count = sum([crit_is, crit_wf, crit_sh, crit_h012])

    if all_pass:
        verdict = "CONFIRMED"
        reason  = "All 4 acceptance criteria met."
    elif pass_count >= 3:
        verdict = "CONDITIONAL"
        fails = []
        if not crit_is:  fails.append(f"IS positive rate {rev_pos_pct:.0%} < 80%")
        if not crit_wf:  fails.append(f"WF only {wf_pos}/6 folds positive")
        if not crit_sh:  fails.append(f"split-half corr negative ({sh_corr_rev:.3f})")
        if not crit_h012: fails.append(f"H-012 corr too high ({h012_corr_rev:.3f})")
        reason = "3/4 criteria met. Failure: " + "; ".join(fails)
    else:
        verdict = "REJECTED"
        fails = []
        if not crit_is:  fails.append(f"IS {rev_pos_pct:.0%} < 80%")
        if not crit_wf:  fails.append(f"WF {wf_pos}/6 folds")
        if not crit_sh:  fails.append(f"split-half r={sh_corr_rev:.3f}")
        if not crit_h012: fails.append(f"H-012 r={h012_corr_rev:.3f}")
        reason = "; ".join(fails)

    print(f"\n  VERDICT: {verdict}")
    print(f"  Reason: {reason}")
    print("=" * 72)

    # -----------------------------------------------------------------------
    # Save results
    # -----------------------------------------------------------------------
    results_path = Path(__file__).parent / "results.json"
    results = {
        "hypothesis": "H-143",
        "name": "Short-Term Reversal Factor (Cross-Sectional)",
        "data_period": {
            "start": str(closes.index[0].date()),
            "end":   str(closes.index[-1].date()),
            "n_days": len(closes),
            "n_assets": len(closes.columns),
        },
        "full_scan": {
            "total_combos": total_combos,
            "reversal": {
                "n_combos": rev_combos,
                "pct_positive_sharpe": round(rev_pos_pct, 4),
                "mean_sharpe": round(float(rev_df["sharpe"].mean()), 4),
                "median_sharpe": round(float(rev_df["sharpe"].median()), 4),
                "best_params": str(best_rev["tag"]),
                "best_sharpe": round(float(best_rev["sharpe"]), 4),
                "best_annual_ret": round(float(best_rev["annual_ret"]), 4),
                "best_max_dd": round(float(best_rev["max_dd"]), 4),
            },
            "momentum": {
                "n_combos": mom_combos,
                "pct_positive_sharpe": round(mom_pos_pct, 4),
                "mean_sharpe": round(float(mom_df["sharpe"].mean()), 4),
                "median_sharpe": round(float(mom_df["sharpe"].median()), 4),
                "best_params": str(best_mom["tag"]),
                "best_sharpe": round(float(best_mom["sharpe"]), 4),
                "best_annual_ret": round(float(best_mom["annual_ret"]), 4),
                "best_max_dd": round(float(best_mom["max_dd"]), 4),
            },
        },
        "walk_forward_reversal": {
            "folds": wf_rev.to_dict("records") if wf_rev is not None else [],
            "positive_folds": wf_pos,
            "total_folds": len(wf_rev) if wf_rev is not None else 0,
            "mean_oos_sharpe": wf_mean,
        },
        "split_half": {
            "reversal_spearman_r": sh_corr_rev,
            "momentum_spearman_r": sh_corr_mom,
        },
        "h012_correlation": {
            "reversal": h012_corr_rev,
            "momentum": h012_corr_mom,
        },
        "fee_sensitivity": fee_rows,
        "acceptance_criteria": {
            "IS_80pct_positive": crit_is,
            "WF_4of6_folds": crit_wf,
            "split_half_positive": crit_sh,
            "h012_corr_le040": crit_h012,
        },
        "verdict": verdict,
        "reason": reason,
        "all_results": scan_df.to_dict("records"),
    }
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved → {results_path}")
