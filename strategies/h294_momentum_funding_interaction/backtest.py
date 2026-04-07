"""
H-294: Momentum × Funding Rate Interaction Factor

Concept: Combine momentum with funding rate to find "confirmed" trends.
Assets with positive momentum AND low/negative funding = underappreciated trends
  (crowd betting against the trend → squeeze potential).
Assets with positive momentum AND high funding = crowded trades → vulnerable.

Signal: rank(momentum) * (1 - rank(funding))
  or equivalently: long assets with high momentum + low funding (contrarian funding)

This combines the best of H-012 (momentum) and H-053 (funding contrarian) —
both individually confirmed — into an interaction that captures "under-crowded momentum."

H-012 and H-053 have near-zero correlation (0.008), meaning they capture different
dimensions. Their interaction should be powerful.

Parameter grid: mom_LB [20,40,60] × fund_LB [3,5,7,10] × R [3,5,7] × N [3,4]
  = 3 × 4 × 3 × 2 = 72 combos
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

MOM_LOOKBACKS = [20, 40, 60]
FUND_WINDOWS = [3, 5, 7, 10]
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


def load_funding_daily() -> pd.DataFrame:
    frames = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_USDT_funding.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        s = df["funding_rate"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        daily = s.resample("1D").mean()
        frames[asset] = daily
    fund = pd.DataFrame(frames).sort_index()
    fund = fund.dropna(how="all")
    return fund


def compute_signal(closes, funding, mom_lb, fund_win):
    """
    Composite signal: high momentum + low funding = high signal (long candidate).

    Signal = rank(momentum) * (1 - rank(funding_avg))
    """
    common_idx = closes.index.intersection(funding.index)
    closes_a = closes.reindex(common_idx)
    fund_a = funding.reindex(common_idx)

    momentum = closes_a.pct_change(mom_lb)
    fund_avg = fund_a.rolling(fund_win, min_periods=fund_win).mean()

    mom_rank = momentum.rank(axis=1, pct=True)
    fund_rank = fund_avg.rank(axis=1, pct=True)

    # High momentum + low funding → high signal
    composite = mom_rank * (1.0 - fund_rank)

    composite = composite.shift(1)
    return composite


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
                # Long top composite (high mom + low funding)
                longs = sorted_row.iloc[-n_pos:].index.tolist()
                # Short bottom composite (low mom + high funding)
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


def compute_h053_returns(closes, funding):
    """H-053 funding XS contrarian returns."""
    common_idx = closes.index.intersection(funding.index)
    closes_a = closes.reindex(common_idx)
    fund_a = funding.reindex(common_idx)
    fund_avg = fund_a.rolling(7, min_periods=7).mean().shift(1)
    rets = closes_a.pct_change().fillna(0.0)
    dates = fund_avg.index
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
            row = fund_avg.iloc[i].dropna()
            if len(row) >= 8:
                sr = row.sort_values()
                # Contrarian: long lowest funding, short highest
                l = sr.iloc[:4].index.tolist()
                s = sr.iloc[-4:].index.tolist()
                cw = pd.Series(0.0, index=l + s)
                for a in l: cw[a] = 0.25
                for a in s: cw[a] = -0.25
                dsr = 0
        curve.append(equity)
    return pd.Series(curve, index=dates).pct_change().fillna(0.0)


def main():
    print("=" * 70)
    print("H-294: Momentum × Funding Rate Interaction Factor")
    print("=" * 70)

    closes = load_closes()
    funding = load_funding_daily()
    print(f"Loaded {len(ASSETS)} assets, {len(closes)} daily bars")
    print(f"Funding data: {len(funding)} daily bars")

    h012_rets = compute_h012_returns(closes)
    h053_rets = compute_h053_returns(closes, funding)

    results = []
    total = len(MOM_LOOKBACKS) * len(FUND_WINDOWS) * len(REBAL_FREQS) * len(N_POSITIONS)
    print(f"\nRunning {total} parameter combinations...")

    for mom_lb, fund_win, rebal, n_pos in product(
        MOM_LOOKBACKS, FUND_WINDOWS, REBAL_FREQS, N_POSITIONS
    ):
        signal = compute_signal(closes, funding, mom_lb, fund_win)
        eq = simulate(closes, signal, rebal, n_pos)
        if len(eq) < 100:
            continue
        rets = eq.pct_change().dropna()
        sr = sharpe_ratio(rets, periods_per_year=PPY)
        ar = annual_return(eq, PPY)
        dd = max_drawdown(eq)

        common = rets.index.intersection(h012_rets.index).intersection(h053_rets.index)
        corr_012 = rets.reindex(common).corr(h012_rets.reindex(common))
        corr_053 = rets.reindex(common).corr(h053_rets.reindex(common))

        label = f"MOM{mom_lb}_FW{fund_win}_R{rebal}_N{n_pos}"
        results.append({
            "label": label,
            "mom_lb": mom_lb,
            "fund_win": fund_win,
            "rebal": rebal,
            "n_pos": n_pos,
            "sharpe": sr,
            "annual_return": ar,
            "max_dd": dd,
            "corr_h012": corr_012,
            "corr_h053": corr_053,
        })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    pct_positive = n_positive / len(df) * 100
    print(f"\nIS Results: {n_positive}/{len(df)} positive Sharpe ({pct_positive:.1f}%)")

    best = df.loc[df["sharpe"].idxmax()]
    print(f"\nBest config: {best['label']}")
    print(f"  Sharpe: {best['sharpe']:.3f}")
    print(f"  Annual return: {best['annual_return']*100:.1f}%")
    print(f"  Max DD: {best['max_dd']*100:.1f}%")
    print(f"  Corr H-012: {best['corr_h012']:.3f}")
    print(f"  Corr H-053: {best['corr_h053']:.3f}")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")

    # Walk-forward
    print(f"\n--- Walk-Forward ---")
    signal = compute_signal(closes, funding, int(best["mom_lb"]), int(best["fund_win"]))
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

    # Neighboring params
    bm, bf, br, bn = int(best["mom_lb"]), int(best["fund_win"]), int(best["rebal"]), int(best["n_pos"])
    neighbors = df[
        (df["mom_lb"].isin([max(20, bm-20), bm, min(60, bm+20)])) &
        (df["fund_win"].isin([max(3, bf-2), bf, min(10, bf+2)])) &
        (df["rebal"].isin([max(3, br-2), br, min(7, br+2)]))
    ]
    n_nbr_pos = (neighbors["sharpe"] > 0).sum()
    print(f"\nNeighboring params: {n_nbr_pos}/{len(neighbors)} positive ({n_nbr_pos/len(neighbors)*100:.1f}%)")

    # Save
    out = {
        "hypothesis": "H-294",
        "name": "Momentum × Funding Rate Interaction",
        "total_params": len(df),
        "pct_positive": pct_positive,
        "best_config": best["label"],
        "best_sharpe": float(best["sharpe"]),
        "best_annual_return": float(best["annual_return"]),
        "best_max_dd": float(best["max_dd"]),
        "corr_h012": float(best["corr_h012"]),
        "corr_h053": float(best["corr_h053"]),
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
    corr_pass = abs(float(best["corr_h012"])) < 0.50 and abs(float(best["corr_h053"])) < 0.50

    print(f"IS ≥80%: {'PASS' if is_pass else 'FAIL'} ({pct_positive:.1f}%)")
    if wf:
        print(f"WF ≥4/6 & mean>0.5: {'PASS' if wf_pass else 'FAIL'} ({n_wf_pos}/{len(wf)}, mean {np.mean(wf_sharpes):.3f})")
    print(f"Split-half both positive: {'PASS' if split_pass else 'FAIL'} (H1={sr_h1:.3f}, H2={sr_h2:.3f})")
    print(f"Correlation <0.50: {'PASS' if corr_pass else 'FAIL'} (H-012={best['corr_h012']:.3f}, H-053={best['corr_h053']:.3f})")

    if is_pass and wf_pass and split_pass and corr_pass:
        print("\n>>> CONFIRMED <<<")
    else:
        print("\n>>> REJECTED <<<")
    print("=" * 70)


if __name__ == "__main__":
    main()
