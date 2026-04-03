"""
H-208: Short-Term Reversal Factor

Classic equity anomaly applied to 14 crypto assets.
Rank assets by short-term return (1-5 days). Go LONG biggest recent losers,
SHORT biggest recent winners (reversal = contrarian).
Also tests the opposite direction (momentum: long winners, short losers).

This is distinct from H-012 (60-day momentum, long winners) and from
H-109 (earlier reversal attempt with 6bps fees, N=[3,4,5], 48 combos).
H-208 uses 5bps fees, N=[3,4] only, and tests both directions explicitly.

Fee: 5bps (0.05%) per trade — applied as proportional cost on each position
change. Full rebalance cost ~0.1% of portfolio (num_positions * 2 * 0.0005
* 1/num_positions per side).

Parameter grid: 4 x 4 x 2 x 2 = 64 combos
  - Lookback windows: [1, 2, 3, 5] days
  - Rebalance periods: [1, 2, 3, 5] days
  - N (top/bottom): [3, 4]
  - Direction: [reversal, momentum]

Sharpe = daily_sharpe * sqrt(365) (annualised)

If IS hit rate >= 80%: run 6-fold walk-forward with 90d folds.
If WF passes (>= 4/6): run split-half + correlation with H-012.
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = [
    "BTC", "ETH", "SOL", "SUI", "XRP",
    "DOGE", "AVAX", "LINK", "ADA", "DOT",
    "NEAR", "OP", "ARB", "ATOM",
]

FEE_RATE = 0.0005        # 5bps one-way per position change

# Parameter grid
LOOKBACKS   = [1, 2, 3, 5]
REBAL_FREQS = [1, 2, 3, 5]
N_SIZES     = [3, 4]
DIRECTIONS  = ["reversal", "momentum"]   # reversal=long losers; momentum=long winners
# 4 x 4 x 2 x 2 = 64 combos

# Walk-forward
WF_FOLDS = 6
WF_TEST  = 90   # days per fold
WF_TRAIN = 180  # lookback train window per fold (min data)
WF_STEP  = 90

TOTAL_BARS = None   # filled after loading


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_prices():
    """Load daily close prices for all 14 assets, align on common dates."""
    data_dir = ROOT / "data"
    closes = {}
    for asset in ASSETS:
        path = data_dir / f"{asset}_USDT_1d.parquet"
        df = pd.read_parquet(path)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        closes[asset] = df["close"]
    prices = pd.DataFrame(closes).sort_index().dropna()
    return prices


# ---------------------------------------------------------------------------
# Core factor computation
# ---------------------------------------------------------------------------

def compute_factor_signal(prices: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """
    Compute short-term return factor for each asset.
    Returns a DataFrame of the same shape: (date x asset) — raw returns.
    Lower = bigger loser = reversal long candidate.
    Higher = bigger winner = reversal short candidate.
    """
    return prices.pct_change(lookback)


def run_factor_backtest(
    prices: pd.DataFrame,
    lookback: int,
    rebal_freq: int,
    n: int,
    direction: str,
) -> pd.Series:
    """
    Run a single factor backtest, return daily portfolio returns (net of fees).

    Signal at day t uses prices[t-1..t-1-lookback] (lagged — no look-ahead).
    Portfolio is rebalanced every `rebal_freq` days.

    Returns: pd.Series of daily net returns (fraction of equity).
    """
    factor = compute_factor_signal(prices, lookback)
    n_assets = prices.shape[1]

    # Build position matrix: +1/n for longs, -1/n for shorts, 0 otherwise
    positions = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

    last_positions = None
    rebal_day_offset = 0

    for i in range(lookback + 1, len(prices)):
        # Current signal uses factor at i-1 (lag 1 for execution)
        sig = factor.iloc[i - 1]

        if sig.isna().all():
            continue

        is_rebal = ((i - (lookback + 1)) % rebal_freq) == 0

        if is_rebal:
            valid = sig.dropna()
            if len(valid) < 2 * n:
                # Not enough assets with valid signals
                positions.iloc[i] = 0.0
                last_positions = positions.iloc[i].copy()
                continue

            ranked = valid.rank(ascending=True)  # rank 1=lowest return (biggest loser)

            if direction == "reversal":
                # Long biggest losers (lowest ranked returns), short biggest winners
                longs  = ranked[ranked <= n].index
                shorts = ranked[ranked > len(valid) - n].index
            else:  # momentum
                # Long biggest winners (highest ranked returns), short biggest losers
                longs  = ranked[ranked > len(valid) - n].index
                shorts = ranked[ranked <= n].index

            pos = pd.Series(0.0, index=prices.columns)
            pos[longs]  = 1.0 / n
            pos[shorts] = -1.0 / n
            positions.iloc[i] = pos
            last_positions = pos.copy()
        else:
            if last_positions is not None:
                positions.iloc[i] = last_positions
            # else: leave at 0

    # Daily returns = sum(position * asset_return) for each day
    daily_asset_ret = prices.pct_change()
    port_ret = (positions.shift(0) * daily_asset_ret).sum(axis=1)

    # Fee: charge on position changes
    if last_positions is not None:
        pos_change = positions.diff().abs()
        fee_cost = pos_change.sum(axis=1) * FEE_RATE
        port_ret = port_ret - fee_cost

    # Drop first lookback+1 rows (no valid signal)
    port_ret = port_ret.iloc[lookback + 2:]
    return port_ret


# ---------------------------------------------------------------------------
# Performance metrics
# ---------------------------------------------------------------------------

def sharpe(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) < 20 or r.std() < 1e-10:
        return 0.0
    return float(r.mean() / r.std() * np.sqrt(365))


def max_dd(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) == 0:
        return 0.0
    cum = (1 + r).cumprod()
    roll_max = cum.cummax()
    dd = (cum / roll_max - 1)
    return float(dd.min())


def ann_ret(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) == 0:
        return 0.0
    cum = (1 + r).prod()
    n_years = len(r) / 365.0
    if n_years <= 0:
        return 0.0
    return float(cum ** (1.0 / n_years) - 1)


# ---------------------------------------------------------------------------
# Parameter scan (in-sample)
# ---------------------------------------------------------------------------

def is_scan(prices: pd.DataFrame):
    """Run full parameter grid scan on all data."""
    results = {}
    for lb, rf, n, direction in product(LOOKBACKS, REBAL_FREQS, N_SIZES, DIRECTIONS):
        key = f"LB{lb}_R{rf}_N{n}_{direction[:3].upper()}"
        ret = run_factor_backtest(prices, lb, rf, n, direction)
        s = sharpe(ret)
        results[key] = {
            "lookback": lb, "rebal": rf, "n": n, "direction": direction,
            "sharpe": s,
            "ann_ret": ann_ret(ret),
            "max_dd": max_dd(ret),
            "n_days": len(ret.dropna()),
        }
    return results


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------

def walk_forward(prices: pd.DataFrame, direction: str):
    """
    6-fold walk-forward. Each fold: train WF_TRAIN days, test WF_TEST days.
    Best params selected on train, evaluated on test.
    """
    n_bars = len(prices)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end   = n_bars - fold * WF_STEP
        test_start = test_end - WF_TEST
        train_end  = test_start
        train_start = max(0, train_end - WF_TRAIN)

        if train_start >= train_end or test_start >= test_end:
            break
        if test_start < 0:
            break

        train_prices = prices.iloc[train_start:train_end]
        test_prices  = prices.iloc[test_start:test_end]

        # Find best params on train set (direction fixed)
        best_sharpe = -np.inf
        best_params = None

        for lb, rf, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
            ret = run_factor_backtest(train_prices, lb, rf, n, direction)
            s = sharpe(ret)
            if s > best_sharpe:
                best_sharpe = s
                best_params = (lb, rf, n)

        # Evaluate best params on test set
        if best_params is None:
            continue
        lb, rf, n = best_params
        test_ret = run_factor_backtest(test_prices, lb, rf, n, direction)
        test_s = sharpe(test_ret)

        fold_results.append({
            "fold": fold + 1,
            "train_sharpe": best_sharpe,
            "test_sharpe": test_s,
            "best_params": f"LB{lb}_R{rf}_N{n}",
        })

    return fold_results


# ---------------------------------------------------------------------------
# Split-half consistency
# ---------------------------------------------------------------------------

def split_half(prices: pd.DataFrame, direction: str):
    """
    Split data in half. Run full IS scan on each half.
    Report mean Sharpe per half and Pearson correlation of per-combo Sharpes.
    """
    mid = len(prices) // 2
    h1_prices = prices.iloc[:mid]
    h2_prices = prices.iloc[mid:]

    keys = []
    h1_sharpes = []
    h2_sharpes = []

    for lb, rf, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        key = f"LB{lb}_R{rf}_N{n}"
        r1 = run_factor_backtest(h1_prices, lb, rf, n, direction)
        r2 = run_factor_backtest(h2_prices, lb, rf, n, direction)
        s1 = sharpe(r1)
        s2 = sharpe(r2)
        keys.append(key)
        h1_sharpes.append(s1)
        h2_sharpes.append(s2)

    if len(h1_sharpes) < 2:
        return {"h1_mean": 0, "h2_mean": 0, "corr": 0}

    corr = float(np.corrcoef(h1_sharpes, h2_sharpes)[0, 1])
    return {
        "h1_mean": float(np.mean(h1_sharpes)),
        "h2_mean": float(np.mean(h2_sharpes)),
        "corr": corr,
        "keys": keys,
        "h1_sharpes": h1_sharpes,
        "h2_sharpes": h2_sharpes,
    }


# ---------------------------------------------------------------------------
# Correlation with H-012 (60-day cross-sectional momentum)
# ---------------------------------------------------------------------------

def h012_returns(prices: pd.DataFrame) -> pd.Series:
    """
    Replicate H-012 (60-day lookback momentum) for correlation check.
    Long top-4 winners, short bottom-4 losers, rebal every 5 days.
    This mirrors the H-012 live implementation closely.
    """
    return run_factor_backtest(prices, lookback=60, rebal_freq=5, n=4, direction="momentum")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 65)
    print("H-208: Short-Term Reversal Factor")
    print("=" * 65)

    prices = load_prices()
    TOTAL_BARS = len(prices)
    print(f"Data: {prices.index[0].date()} to {prices.index[-1].date()}, {TOTAL_BARS} bars, {len(ASSETS)} assets")
    print(f"Fee: {FEE_RATE*100:.2f}% per trade (one-way)")
    print()

    # ------------------------------------------------------------------
    # 1. Full IS scan (all 64 combos)
    # ------------------------------------------------------------------
    print("Running full IS parameter scan (64 combos) ...")
    is_results = is_scan(prices)

    all_sharpes    = [v["sharpe"] for v in is_results.values()]
    pos_sharpes    = [s for s in all_sharpes if s > 0]
    is_hit_rate    = len(pos_sharpes) / len(all_sharpes)
    mean_sharpe    = float(np.mean(all_sharpes))
    best_key       = max(is_results, key=lambda k: is_results[k]["sharpe"])
    best_sharpe    = is_results[best_key]["sharpe"]

    # Split by direction
    rev_sharpes = [v["sharpe"] for k, v in is_results.items() if v["direction"] == "reversal"]
    mom_sharpes = [v["sharpe"] for k, v in is_results.items() if v["direction"] == "momentum"]
    rev_mean = float(np.mean(rev_sharpes))
    mom_mean = float(np.mean(mom_sharpes))
    rev_pos_pct = sum(1 for s in rev_sharpes if s > 0) / len(rev_sharpes)
    mom_pos_pct = sum(1 for s in mom_sharpes if s > 0) / len(mom_sharpes)

    print(f"IS hit rate:     {is_hit_rate*100:.1f}%  ({len(pos_sharpes)}/{len(all_sharpes)} combos positive)")
    print(f"IS mean Sharpe:  {mean_sharpe:.3f}")
    print(f"IS best:         {best_key} = {best_sharpe:.3f}")
    print()
    print(f"  Reversal (long losers) : mean={rev_mean:.3f}, hit={rev_pos_pct*100:.0f}%")
    print(f"  Momentum (long winners): mean={mom_mean:.3f}, hit={mom_pos_pct*100:.0f}%")
    print()

    # Print top 10
    sorted_results = sorted(is_results.items(), key=lambda x: x[1]["sharpe"], reverse=True)
    print("Top 10 combos:")
    for k, v in sorted_results[:10]:
        print(f"  {k:<28} Sharpe={v['sharpe']:+.3f}  AnnRet={v['ann_ret']*100:+.1f}%  MaxDD={v['max_dd']*100:.1f}%")
    print()

    # Threshold check
    THRESHOLD = 0.80
    if is_hit_rate < THRESHOLD:
        print(f"IS hit rate {is_hit_rate*100:.1f}% < {THRESHOLD*100:.0f}% threshold — REJECT")
        _save_results(is_results, is_hit_rate, mean_sharpe, best_key, best_sharpe,
                      rev_mean, mom_mean, rev_pos_pct, mom_pos_pct,
                      "REJECTED", "IS hit rate below 80%", prices)
        return

    print(f"IS hit rate passes! Running walk-forward for both directions ...")
    print()

    # ------------------------------------------------------------------
    # 2. Walk-forward validation — reversal direction
    # ------------------------------------------------------------------
    best_direction = "reversal" if rev_mean >= mom_mean else "momentum"
    print(f"Dominant direction: {best_direction} (rev_mean={rev_mean:.3f}, mom_mean={mom_mean:.3f})")
    print()

    for direction in ["reversal", "momentum"]:
        print(f"Walk-forward ({direction}):")
        wf = walk_forward(prices, direction)
        n_pos_folds = sum(1 for f in wf if f["test_sharpe"] > 0)
        wf_mean = float(np.mean([f["test_sharpe"] for f in wf])) if wf else 0.0
        print(f"  Folds: {len(wf)}, positive: {n_pos_folds}/{len(wf)}, mean test Sharpe: {wf_mean:.3f}")
        for f in wf:
            print(f"    Fold {f['fold']}: train={f['train_sharpe']:.3f}, test={f['test_sharpe']:+.3f}, best_params={f['best_params']}")
        print()

        if direction == best_direction:
            wf_best = wf
            wf_pos_folds = n_pos_folds
            wf_mean_best = wf_mean

    WF_THRESHOLD = 4
    if wf_pos_folds < WF_THRESHOLD:
        print(f"WF positive folds {wf_pos_folds}/{len(wf_best)} < {WF_THRESHOLD} — REJECT")
        _save_results(is_results, is_hit_rate, mean_sharpe, best_key, best_sharpe,
                      rev_mean, mom_mean, rev_pos_pct, mom_pos_pct,
                      "REJECTED", f"WF failed ({wf_pos_folds}/{len(wf_best)} positive folds)",
                      prices, wf_reversal=wf_best if best_direction == "reversal" else None,
                      wf_momentum=wf_best if best_direction == "momentum" else None)
        return

    print(f"WF passes! Running split-half consistency ...")
    print()

    # ------------------------------------------------------------------
    # 3. Split-half consistency
    # ------------------------------------------------------------------
    sh = split_half(prices, best_direction)
    print(f"Split-half ({best_direction}):")
    print(f"  H1 mean Sharpe: {sh['h1_mean']:.3f}")
    print(f"  H2 mean Sharpe: {sh['h2_mean']:.3f}")
    print(f"  Correlation:    {sh['corr']:.3f}")
    print()

    if sh["corr"] < 0 or (sh["h1_mean"] < 0 and sh["h2_mean"] < 0):
        print(f"Split-half FAILED (corr={sh['corr']:.3f}) — REJECT")
        _save_results(is_results, is_hit_rate, mean_sharpe, best_key, best_sharpe,
                      rev_mean, mom_mean, rev_pos_pct, mom_pos_pct,
                      "REJECTED", f"Split-half failed (corr={sh['corr']:.3f})",
                      prices, sh=sh, wf_best=wf_best)
        return

    # ------------------------------------------------------------------
    # 4. Correlation with H-012
    # ------------------------------------------------------------------
    print("Computing correlation with H-012 (60d momentum) ...")
    best_lb = is_results[best_key]["lookback"]
    best_rf = is_results[best_key]["rebal"]
    best_n  = is_results[best_key]["n"]
    best_dir = is_results[best_key]["direction"]

    h208_ret = run_factor_backtest(prices, best_lb, best_rf, best_n, best_dir)
    h012_ret = h012_returns(prices)

    # Align
    common = h208_ret.index.intersection(h012_ret.index)
    if len(common) > 20:
        corr_h012 = float(np.corrcoef(h208_ret.loc[common], h012_ret.loc[common])[0, 1])
    else:
        corr_h012 = 0.0
    print(f"  Corr with H-012: {corr_h012:.3f}")
    print()

    if abs(corr_h012) > 0.5:
        print(f"Correlation {corr_h012:.3f} with H-012 exceeds 0.5 — REJECT (redundant)")
        _save_results(is_results, is_hit_rate, mean_sharpe, best_key, best_sharpe,
                      rev_mean, mom_mean, rev_pos_pct, mom_pos_pct,
                      "REJECTED", f"Corr {corr_h012:.3f} with H-012 > 0.5",
                      prices, sh=sh, wf_best=wf_best, corr_h012=corr_h012)
        return

    # ------------------------------------------------------------------
    # 5. Final stats
    # ------------------------------------------------------------------
    final_sharpe = sharpe(h208_ret)
    final_ann    = ann_ret(h208_ret)
    final_dd     = max_dd(h208_ret)

    print("=" * 65)
    print("CONFIRMED!")
    print(f"  Best params:    {best_key}")
    print(f"  Full-period Sharpe: {final_sharpe:.3f}")
    print(f"  Annual return:  {final_ann*100:.1f}%")
    print(f"  Max drawdown:   {final_dd*100:.1f}%")
    print(f"  Corr H-012:     {corr_h012:.3f}")
    print(f"  Split-half:     H1={sh['h1_mean']:.3f}, H2={sh['h2_mean']:.3f}, corr={sh['corr']:.3f}")
    print(f"  WF:             {wf_pos_folds}/{len(wf_best)} positive folds, mean={wf_mean_best:.3f}")
    print("=" * 65)

    _save_results(is_results, is_hit_rate, mean_sharpe, best_key, best_sharpe,
                  rev_mean, mom_mean, rev_pos_pct, mom_pos_pct,
                  "CONFIRMED", "All checks passed",
                  prices, sh=sh, wf_best=wf_best, corr_h012=corr_h012,
                  final_sharpe=final_sharpe, final_ann=final_ann, final_dd=final_dd)


def _save_results(
    is_results, is_hit_rate, mean_sharpe, best_key, best_sharpe,
    rev_mean, mom_mean, rev_pos_pct, mom_pos_pct,
    verdict, reason, prices,
    sh=None, wf_best=None, wf_reversal=None, wf_momentum=None,
    corr_h012=None, final_sharpe=None, final_ann=None, final_dd=None,
):
    out = {
        "hypothesis": "H-208",
        "title": "Short-Term Reversal Factor",
        "verdict": verdict,
        "reason": reason,
        "n_combos": len(is_results),
        "is_hit_rate": round(is_hit_rate, 4),
        "is_mean_sharpe": round(mean_sharpe, 4),
        "is_best_key": best_key,
        "is_best_sharpe": round(best_sharpe, 4),
        "reversal_mean_sharpe": round(rev_mean, 4),
        "reversal_pos_pct": round(rev_pos_pct, 4),
        "momentum_mean_sharpe": round(mom_mean, 4),
        "momentum_pos_pct": round(mom_pos_pct, 4),
        "data_start": str(prices.index[0].date()),
        "data_end": str(prices.index[-1].date()),
        "n_bars": len(prices),
        "n_assets": len(prices.columns),
    }

    if wf_best is not None:
        out["wf_folds"] = len(wf_best)
        out["wf_positive_folds"] = sum(1 for f in wf_best if f["test_sharpe"] > 0)
        out["wf_mean_test_sharpe"] = round(float(np.mean([f["test_sharpe"] for f in wf_best])), 4)
        out["wf_detail"] = wf_best

    if sh is not None:
        out["split_half_h1_mean"] = round(sh["h1_mean"], 4)
        out["split_half_h2_mean"] = round(sh["h2_mean"], 4)
        out["split_half_corr"] = round(sh["corr"], 4)

    if corr_h012 is not None:
        out["corr_h012"] = round(corr_h012, 4)

    if final_sharpe is not None:
        out["final_sharpe"] = round(final_sharpe, 4)
        out["final_ann_ret"] = round(final_ann, 4)
        out["final_max_dd"] = round(final_dd, 4)

    # Top 15 combos by IS Sharpe
    top15 = sorted(is_results.items(), key=lambda x: x[1]["sharpe"], reverse=True)[:15]
    out["top15_combos"] = [
        {"key": k, "sharpe": round(v["sharpe"], 4), "ann_ret": round(v["ann_ret"], 4),
         "max_dd": round(v["max_dd"], 4), "direction": v["direction"]}
        for k, v in top15
    ]

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
