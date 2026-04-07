"""
H-292: Momentum × Efficiency Interaction Factor

Concept: Combine cross-sectional momentum (H-012) with price efficiency (H-076) into
an interaction signal. Assets with strong momentum AND high price efficiency are
trending cleanly — the momentum is "real" and persistent. Assets with strong momentum
BUT low efficiency are just noisy — momentum may reverse.

Signal: composite = rank(momentum) + rank(efficiency)
  or:   composite = rank(momentum) * rank(efficiency)  (interaction)

Both variants tested. Long top-N composite, short bottom-N.

Key insight: H-012 (momentum, corr ~0.04 with H-076 efficiency) — near zero correlation
means these factors capture genuinely different dimensions. Combining them should produce
a signal with better risk-adjusted returns than either alone.

Parameter grid: mom_LB [20,40,60] × eff_LB [20,40,60] × R [3,5,7] × N [3,4] × mode [add,mult]
  = 3 × 3 × 3 × 2 × 2 = 108 combos

Validation criteria:
  1. IS: ≥80% of best-direction params positive Sharpe
  2. WF OOS: ≥4/6 folds positive AND mean OOS Sharpe > 0.5
  3. Split-half: Both halves positive Sharpe
  4. Correlation: |corr with H-012| < 0.50, |corr with H-076| < 0.50
"""

import json
import sys
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

# ─── Configuration ──────────────────────────────────────────────────────────

ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX",
    "DOT", "LINK", "ATOM", "NEAR", "OP", "ARB", "SUI",
]

DATA_DIR = ROOT / "data"
FEE_RATE = 0.001
INITIAL_CAPITAL = 10_000.0
PPY = 365

# Parameter grid
MOM_LOOKBACKS = [20, 40, 60]
EFF_LOOKBACKS = [20, 40, 60]
REBAL_FREQS = [3, 5, 7]
N_POSITIONS = [3, 4]
MODES = ["add", "mult"]  # additive rank combo vs multiplicative interaction

# Walk-forward
WF_FOLDS = 6
WF_TEST_DAYS = 90
WF_MIN_TRAIN = 180


# ─── Data Loading ────────────────────────────────────────────────────────────

def load_closes() -> pd.DataFrame:
    frames = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        s = df["close"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        frames[asset] = s
    closes = pd.DataFrame(frames).sort_index()
    closes = closes.dropna(how="all").ffill().dropna(how="all")
    return closes


def load_volumes() -> pd.DataFrame:
    frames = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        s = df["volume"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        frames[asset] = s
    vols = pd.DataFrame(frames).sort_index()
    vols = vols.dropna(how="all").ffill().dropna(how="all")
    return vols


# ─── Signal Computation ──────────────────────────────────────────────────────

def compute_efficiency(closes: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Price efficiency = |net return| / sum(|daily returns|) over lookback."""
    daily_rets = closes.pct_change()
    net_return = closes.pct_change(lookback).abs()
    sum_abs_rets = daily_rets.abs().rolling(lookback, min_periods=lookback).sum()
    efficiency = net_return / sum_abs_rets.replace(0, np.nan)
    return efficiency


def compute_signal(
    closes: pd.DataFrame,
    volumes: pd.DataFrame,
    mom_lb: int,
    eff_lb: int,
    mode: str,
) -> pd.DataFrame:
    """
    Compute composite momentum × efficiency signal.

    mode='add': rank(momentum) + rank(efficiency) — linear combo
    mode='mult': rank(momentum) * rank(efficiency) — interaction
    """
    # Momentum: N-day return
    momentum = closes.pct_change(mom_lb)

    # Price efficiency
    efficiency = compute_efficiency(closes, eff_lb)

    # Cross-sectional rank (0 to 1)
    mom_rank = momentum.rank(axis=1, pct=True)
    eff_rank = efficiency.rank(axis=1, pct=True)

    if mode == "add":
        composite = mom_rank + eff_rank
    elif mode == "mult":
        composite = mom_rank * eff_rank
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Lag by 1 day
    composite = composite.shift(1)
    return composite


# ─── Portfolio Simulation ────────────────────────────────────────────────────

def simulate(
    closes: pd.DataFrame,
    signal: pd.DataFrame,
    rebal: int,
    n_pos: int,
    start_idx: int = 0,
    end_idx: int = None,
) -> pd.Series:
    dates = signal.index
    if end_idx is None:
        end_idx = len(dates)
    dates = dates[start_idx:end_idx]
    sig = signal.iloc[start_idx:end_idx]
    cls = closes.reindex(dates)
    rets = cls.pct_change().fillna(0.0)

    equity = INITIAL_CAPITAL
    equity_curve = []
    current_weights = pd.Series(dtype=float)
    days_since_rebal = rebal

    for i, dt in enumerate(dates):
        day_rets = rets.iloc[i]
        if len(current_weights) > 0:
            port_ret = (current_weights * day_rets.reindex(current_weights.index, fill_value=0.0)).sum()
            equity *= (1.0 + port_ret)

        days_since_rebal += 1
        if days_since_rebal >= rebal:
            row = sig.iloc[i].dropna()
            if len(row) >= 2 * n_pos:
                sorted_row = row.sort_values()
                # Long top composite (high momentum + high efficiency)
                longs = sorted_row.iloc[-n_pos:].index.tolist()
                # Short bottom composite
                shorts = sorted_row.iloc[:n_pos].index.tolist()

                new_weights = pd.Series(0.0, index=longs + shorts)
                for a in longs:
                    new_weights[a] = 1.0 / n_pos
                for a in shorts:
                    new_weights[a] = -1.0 / n_pos

                if len(current_weights) > 0:
                    combined = new_weights.reindex(
                        new_weights.index.union(current_weights.index), fill_value=0.0
                    )
                    old_combined = current_weights.reindex(combined.index, fill_value=0.0)
                    turnover = (combined - old_combined).abs().sum() / 2.0
                else:
                    turnover = new_weights.abs().sum() / 2.0

                fee = turnover * FEE_RATE
                equity *= (1.0 - fee)
                current_weights = new_weights
                days_since_rebal = 0

        equity_curve.append(equity)

    return pd.Series(equity_curve, index=dates)


# ─── Walk-Forward ────────────────────────────────────────────────────────────

def walk_forward(closes, signal, rebal, n_pos):
    T = len(signal)
    results = []
    total_test = WF_FOLDS * WF_TEST_DAYS
    if T < WF_MIN_TRAIN + total_test:
        return results
    test_start = T - total_test
    for fold in range(WF_FOLDS):
        ts = test_start + fold * WF_TEST_DAYS
        te = ts + WF_TEST_DAYS
        eq = simulate(closes, signal, rebal, n_pos, start_idx=0, end_idx=te)
        oos_eq = eq.iloc[ts:te]
        if len(oos_eq) < 20:
            continue
        oos_rets = oos_eq.pct_change().dropna()
        sr = sharpe_ratio(oos_rets, periods_per_year=PPY)
        results.append((fold, sr))
    return results


# ─── Reference Strategies ────────────────────────────────────────────────────

def compute_h012_returns(closes: pd.DataFrame) -> pd.Series:
    """H-012 momentum returns for correlation check."""
    momentum = closes.pct_change(60).shift(1)
    rets = closes.pct_change().fillna(0.0)
    dates = momentum.index
    equity = INITIAL_CAPITAL
    curve = []
    cw = pd.Series(dtype=float)
    dsr = 5

    for i in range(len(dates)):
        dr = rets.iloc[i]
        if len(cw) > 0:
            equity *= (1.0 + (cw * dr.reindex(cw.index, fill_value=0.0)).sum())
        dsr += 1
        if dsr >= 5:
            row = momentum.iloc[i].dropna()
            if len(row) >= 8:
                sr = row.sort_values()
                l = sr.iloc[-4:].index.tolist()
                s = sr.iloc[:4].index.tolist()
                cw = pd.Series(0.0, index=l + s)
                for a in l: cw[a] = 0.25
                for a in s: cw[a] = -0.25
                dsr = 0
        curve.append(equity)

    return pd.Series(curve, index=dates).pct_change().fillna(0.0)


def compute_h076_returns(closes: pd.DataFrame) -> pd.Series:
    """H-076 efficiency returns for correlation check."""
    eff = compute_efficiency(closes, 40).shift(1)
    rets = closes.pct_change().fillna(0.0)
    dates = eff.index
    equity = INITIAL_CAPITAL
    curve = []
    cw = pd.Series(dtype=float)
    dsr = 5

    for i in range(len(dates)):
        dr = rets.iloc[i]
        if len(cw) > 0:
            equity *= (1.0 + (cw * dr.reindex(cw.index, fill_value=0.0)).sum())
        dsr += 1
        if dsr >= 5:
            row = eff.iloc[i].dropna()
            if len(row) >= 8:
                sr = row.sort_values()
                l = sr.iloc[-4:].index.tolist()
                s = sr.iloc[:4].index.tolist()
                cw = pd.Series(0.0, index=l + s)
                for a in l: cw[a] = 0.25
                for a in s: cw[a] = -0.25
                dsr = 0
        curve.append(equity)

    return pd.Series(curve, index=dates).pct_change().fillna(0.0)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("H-292: Momentum × Efficiency Interaction Factor")
    print("=" * 70)

    closes = load_closes()
    volumes = load_volumes()
    print(f"Loaded {len(ASSETS)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0]} to {closes.index[-1]}")

    # Compute reference strategy returns
    h012_rets = compute_h012_returns(closes)
    h076_rets = compute_h076_returns(closes)

    # Grid search
    results = []
    total = len(MOM_LOOKBACKS) * len(EFF_LOOKBACKS) * len(REBAL_FREQS) * len(N_POSITIONS) * len(MODES)
    print(f"\nRunning {total} parameter combinations...")

    for mom_lb, eff_lb, rebal, n_pos, mode in product(
        MOM_LOOKBACKS, EFF_LOOKBACKS, REBAL_FREQS, N_POSITIONS, MODES
    ):
        signal = compute_signal(closes, volumes, mom_lb, eff_lb, mode)
        eq = simulate(closes, signal, rebal, n_pos)
        if len(eq) < 100:
            continue
        rets = eq.pct_change().dropna()
        sr = sharpe_ratio(rets, periods_per_year=PPY)
        ar = annual_return(eq, PPY)
        dd = max_drawdown(eq)

        # Correlation with H-012 and H-076
        common = rets.index.intersection(h012_rets.index).intersection(h076_rets.index)
        corr_012 = rets.reindex(common).corr(h012_rets.reindex(common))
        corr_076 = rets.reindex(common).corr(h076_rets.reindex(common))

        label = f"MOM{mom_lb}_EFF{eff_lb}_R{rebal}_N{n_pos}_{mode}"
        results.append({
            "label": label,
            "mom_lb": mom_lb,
            "eff_lb": eff_lb,
            "rebal": rebal,
            "n_pos": n_pos,
            "mode": mode,
            "sharpe": sr,
            "annual_return": ar,
            "max_dd": dd,
            "corr_h012": corr_012,
            "corr_h076": corr_076,
        })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    pct_positive = n_positive / len(df) * 100
    print(f"\nIS Results: {n_positive}/{len(df)} positive Sharpe ({pct_positive:.1f}%)")

    # Check by mode
    for mode in MODES:
        sub = df[df["mode"] == mode]
        pos = (sub["sharpe"] > 0).sum()
        print(f"  {mode}: {pos}/{len(sub)} positive ({pos/len(sub)*100:.1f}%)")

    # Best config
    best = df.loc[df["sharpe"].idxmax()]
    print(f"\nBest config: {best['label']}")
    print(f"  Sharpe: {best['sharpe']:.3f}")
    print(f"  Annual return: {best['annual_return']*100:.1f}%")
    print(f"  Max DD: {best['max_dd']*100:.1f}%")
    print(f"  Corr H-012: {best['corr_h012']:.3f}")
    print(f"  Corr H-076: {best['corr_h076']:.3f}")

    # Mean Sharpe
    print(f"\nMean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"Median Sharpe: {df['sharpe'].median():.3f}")

    # Walk-forward on best config
    print(f"\n--- Walk-Forward (best config: {best['label']}) ---")
    signal = compute_signal(closes, volumes, int(best["mom_lb"]), int(best["eff_lb"]), best["mode"])
    wf = walk_forward(closes, signal, int(best["rebal"]), int(best["n_pos"]))
    if wf:
        wf_sharpes = [s for _, s in wf]
        n_wf_pos = sum(1 for s in wf_sharpes if s > 0)
        print(f"WF folds positive: {n_wf_pos}/{len(wf)}")
        print(f"WF mean Sharpe: {np.mean(wf_sharpes):.3f}")
        for fold, sr in wf:
            print(f"  Fold {fold}: Sharpe {sr:.3f}")

    # Split-half
    print(f"\n--- Split-Half ---")
    mid = len(signal) // 2
    eq_h1 = simulate(closes, signal, int(best["rebal"]), int(best["n_pos"]), 0, mid)
    eq_h2 = simulate(closes, signal, int(best["rebal"]), int(best["n_pos"]), mid, len(signal))
    sr_h1 = sharpe_ratio(eq_h1.pct_change().dropna(), periods_per_year=PPY)
    sr_h2 = sharpe_ratio(eq_h2.pct_change().dropna(), periods_per_year=PPY)
    print(f"  H1 Sharpe: {sr_h1:.3f}")
    print(f"  H2 Sharpe: {sr_h2:.3f}")

    # Neighboring params robustness for best
    bm, be, br, bn, bmode = int(best["mom_lb"]), int(best["eff_lb"]), int(best["rebal"]), int(best["n_pos"]), best["mode"]
    neighbors = df[
        (df["mode"] == bmode) &
        (df["mom_lb"].isin([max(20, bm-20), bm, min(60, bm+20)])) &
        (df["eff_lb"].isin([max(20, be-20), be, min(60, be+20)])) &
        (df["rebal"].isin([max(3, br-2), br, min(7, br+2)]))
    ]
    n_nbr_pos = (neighbors["sharpe"] > 0).sum()
    print(f"\nNeighboring params: {n_nbr_pos}/{len(neighbors)} positive ({n_nbr_pos/len(neighbors)*100:.1f}%)")

    # Save results
    out = {
        "hypothesis": "H-292",
        "name": "Momentum × Efficiency Interaction",
        "total_params": len(df),
        "pct_positive": pct_positive,
        "best_config": best["label"],
        "best_sharpe": float(best["sharpe"]),
        "best_annual_return": float(best["annual_return"]),
        "best_max_dd": float(best["max_dd"]),
        "corr_h012": float(best["corr_h012"]),
        "corr_h076": float(best["corr_h076"]),
        "mean_sharpe": float(df["sharpe"].mean()),
    }
    if wf:
        out["wf_folds_positive"] = n_wf_pos
        out["wf_total_folds"] = len(wf)
        out["wf_mean_sharpe"] = float(np.mean(wf_sharpes))
    out["split_half_h1"] = float(sr_h1)
    out["split_half_h2"] = float(sr_h2)
    out["neighbor_pct_positive"] = float(n_nbr_pos / len(neighbors) * 100)

    outpath = Path(__file__).parent / "results.json"
    with open(outpath, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to {outpath}")

    # Decision
    print("\n" + "=" * 70)
    is_pass = pct_positive >= 80
    wf_pass = wf and n_wf_pos >= 4 and np.mean(wf_sharpes) > 0.5
    split_pass = sr_h1 > 0 and sr_h2 > 0
    corr_pass = abs(float(best["corr_h012"])) < 0.50 and abs(float(best["corr_h076"])) < 0.50

    print(f"IS ≥80%: {'PASS' if is_pass else 'FAIL'} ({pct_positive:.1f}%)")
    if wf:
        print(f"WF ≥4/6 & mean>0.5: {'PASS' if wf_pass else 'FAIL'} ({n_wf_pos}/{len(wf)}, mean {np.mean(wf_sharpes):.3f})")
    print(f"Split-half both positive: {'PASS' if split_pass else 'FAIL'} (H1={sr_h1:.3f}, H2={sr_h2:.3f})")
    print(f"Correlation <0.50: {'PASS' if corr_pass else 'FAIL'} (H-012={best['corr_h012']:.3f}, H-076={best['corr_h076']:.3f})")

    if is_pass and wf_pass and split_pass and corr_pass:
        print("\n>>> CONFIRMED — All criteria pass <<<")
    else:
        print("\n>>> REJECTED <<<")

    print("=" * 70)


if __name__ == "__main__":
    main()
