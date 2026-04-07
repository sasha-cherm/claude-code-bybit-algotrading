"""
H-301: Correlation Centrality Factor

Concept: Measure how "central" each asset is in the cross-asset correlation network.
Central assets (high average correlation with all others) behave like market betas.
Peripheral assets (low average correlation) are more idiosyncratic.

Signal: Average pairwise rolling correlation of each asset with all other assets.
Long peripheral (low centrality) assets, short central (high centrality) assets.

Rationale: In crypto, highly correlated "central" assets move in lockstep with the
market and offer no edge. Peripheral assets with lower correlations may have
idiosyncratic factors driving them → long peripheral, short central.

Alternative: Long central (flight-to-quality during stress), short peripheral.
We test both directions.

Parameter grid: corr_window [20,30,40,60] × R [3,5,7] × N [3,4] = 4×3×2 = 24 combos
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

ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX",
    "DOT", "LINK", "ATOM", "NEAR", "OP", "ARB", "SUI",
]

DATA_DIR = ROOT / "data"
FEE_RATE = 0.001
INITIAL_CAPITAL = 10_000.0
PPY = 365

CORR_WINDOWS = [20, 30, 40, 60]
REBAL_FREQS = [3, 5, 7]
N_POSITIONS = [3, 4]

WF_FOLDS = 6
WF_TEST_DAYS = 90
WF_MIN_TRAIN = 180


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


def compute_signal(closes, corr_window):
    """
    For each asset, compute its average rolling correlation with all other assets.
    Signal = average_corr (centrality). Low = peripheral → LONG (contrarian).
    """
    rets = closes.pct_change()
    avail_assets = [a for a in ASSETS if a in rets.columns]

    signal = pd.DataFrame(index=closes.index, columns=avail_assets, dtype=float)

    for asset in avail_assets:
        pair_corrs = []
        for other in avail_assets:
            if other == asset:
                continue
            rc = rets[asset].rolling(corr_window, min_periods=corr_window).corr(rets[other])
            pair_corrs.append(rc)
        # Average correlation with all other assets = centrality
        avg_corr = pd.concat(pair_corrs, axis=1).mean(axis=1)
        signal[asset] = avg_corr

    # Low centrality = peripheral → LONG. Negate so that high signal = most peripheral.
    signal = -signal
    signal = signal.shift(1)
    return signal


def simulate(closes, signal, rebal, n_pos, start_idx=0, end_idx=None):
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
                longs = sorted_row.iloc[-n_pos:].index.tolist()
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


def compute_h012_returns(closes):
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


def main():
    print("=" * 70)
    print("H-301: Correlation Centrality Factor")
    print("=" * 70)

    closes = load_closes()
    print(f"Loaded {len(ASSETS)} assets, {len(closes)} daily bars")

    h012_rets = compute_h012_returns(closes)

    results = []
    total = len(CORR_WINDOWS) * len(REBAL_FREQS) * len(N_POSITIONS)
    print(f"\nRunning {total} parameter combinations...")

    for corr_win, rebal, n_pos in product(CORR_WINDOWS, REBAL_FREQS, N_POSITIONS):
        signal = compute_signal(closes, corr_win)
        eq = simulate(closes, signal, rebal, n_pos)
        if len(eq) < 100:
            continue
        rets = eq.pct_change().dropna()
        sr = sharpe_ratio(rets, periods_per_year=PPY)
        ar = annual_return(eq, PPY)
        dd = max_drawdown(eq)

        common = rets.index.intersection(h012_rets.index)
        corr_012 = rets.reindex(common).corr(h012_rets.reindex(common))

        label = f"CW{corr_win}_R{rebal}_N{n_pos}"
        results.append({
            "label": label, "corr_win": corr_win, "rebal": rebal,
            "n_pos": n_pos, "sharpe": sr, "annual_return": ar,
            "max_dd": dd, "corr_h012": corr_012,
        })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    pct_positive = n_positive / len(df) * 100
    print(f"\nIS Results: {n_positive}/{len(df)} positive Sharpe ({pct_positive:.1f}%)")

    # Direction analysis
    n_periph_pos = (df["sharpe"] > 0).sum()
    n_central_pos = (df["sharpe"] < 0).sum()
    print(f"  Peripheral-long: {n_periph_pos}/{len(df)} ({n_periph_pos/len(df)*100:.1f}%)")
    print(f"  Central-long: {n_central_pos}/{len(df)} ({n_central_pos/len(df)*100:.1f}%)")

    best = df.loc[df["sharpe"].idxmax()]
    print(f"\nBest config: {best['label']}")
    print(f"  Sharpe: {best['sharpe']:.3f}, Annual: {best['annual_return']*100:.1f}%, DD: {best['max_dd']*100:.1f}%")
    print(f"  Corr H-012: {best['corr_h012']:.3f}")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")

    # By corr window
    print("\nBy correlation window:")
    for cw in CORR_WINDOWS:
        sub = df[df["corr_win"] == cw]
        mean_sr = sub["sharpe"].mean()
        pos = (sub["sharpe"] > 0).sum()
        print(f"  CW{cw}: mean Sharpe {mean_sr:.3f}, {pos}/{len(sub)} positive")

    # Walk-forward
    signal = compute_signal(closes, int(best["corr_win"]))
    wf = walk_forward(closes, signal, int(best["rebal"]), int(best["n_pos"]))
    wf_sharpes = [s for _, s in wf] if wf else []
    n_wf_pos = sum(1 for s in wf_sharpes if s > 0)
    if wf:
        print(f"\nWF: {n_wf_pos}/{len(wf)} positive, mean {np.mean(wf_sharpes):.3f}")
        for fold, sr in wf:
            print(f"  Fold {fold}: Sharpe {sr:.3f}")

    # Neighbor robustness
    best_cw = int(best["corr_win"])
    neighbors = df[df["corr_win"].isin([best_cw - 10, best_cw, best_cw + 10, best_cw + 20])]
    n_neigh_pos = (neighbors["sharpe"] > 0).sum()
    if len(neighbors) > 0:
        print(f"\nNeighbor robustness: {n_neigh_pos}/{len(neighbors)} positive ({n_neigh_pos/len(neighbors)*100:.1f}%)")

    # Split-half
    mid = len(signal) // 2
    eq_h1 = simulate(closes, signal, int(best["rebal"]), int(best["n_pos"]), 0, mid)
    eq_h2 = simulate(closes, signal, int(best["rebal"]), int(best["n_pos"]), mid, len(signal))
    sr_h1 = sharpe_ratio(eq_h1.pct_change().dropna(), periods_per_year=PPY)
    sr_h2 = sharpe_ratio(eq_h2.pct_change().dropna(), periods_per_year=PPY)
    print(f"\nSplit-half: H1={sr_h1:.3f}, H2={sr_h2:.3f}")

    # Save
    out = {
        "hypothesis": "H-301", "name": "Correlation Centrality",
        "total_params": len(df), "pct_positive": pct_positive,
        "best_config": best["label"], "best_sharpe": float(best["sharpe"]),
        "best_annual_return": float(best["annual_return"]),
        "best_max_dd": float(best["max_dd"]),
        "corr_h012": float(best["corr_h012"]),
        "mean_sharpe": float(df["sharpe"].mean()),
        "split_half_h1": float(sr_h1), "split_half_h2": float(sr_h2),
    }
    if wf:
        out["wf_folds_positive"] = n_wf_pos
        out["wf_total_folds"] = len(wf)
        out["wf_mean_sharpe"] = float(np.mean(wf_sharpes))
    outpath = Path(__file__).parent / "results.json"
    with open(outpath, "w") as f:
        json.dump(out, f, indent=2)

    # Decision
    print("\n" + "=" * 70)
    is_pass = pct_positive >= 80
    wf_pass = wf and n_wf_pos >= 4 and np.mean(wf_sharpes) > 0.5
    split_pass = sr_h1 > 0 and sr_h2 > 0
    corr_pass = abs(float(best["corr_h012"])) < 0.50
    print(f"IS >=80%: {'PASS' if is_pass else 'FAIL'} ({pct_positive:.1f}%)")
    if wf:
        print(f"WF: {'PASS' if wf_pass else 'FAIL'} ({n_wf_pos}/{len(wf)}, mean {np.mean(wf_sharpes):.3f})")
    print(f"Split-half: {'PASS' if split_pass else 'FAIL'} ({sr_h1:.3f}/{sr_h2:.3f})")
    print(f"Correlation: {'PASS' if corr_pass else 'FAIL'} ({best['corr_h012']:.3f})")
    if is_pass and wf_pass and split_pass and corr_pass:
        print("\n>>> CONFIRMED <<<")
    else:
        print("\n>>> REJECTED <<<")
    print("=" * 70)


if __name__ == "__main__":
    main()
