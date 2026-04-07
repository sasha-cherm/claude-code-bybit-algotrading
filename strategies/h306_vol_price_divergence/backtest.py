"""
H-306: Volume-Price Divergence Factor

Concept: Identify assets where price direction and volume trend DIVERGE.
When price is rising but volume is falling, the move lacks conviction (bearish).
When price is falling but volume is rising, there's accumulation (bullish).

Signal: rank(price_momentum) - rank(volume_momentum).
Negative = price up + volume down (exhaustion) → SHORT.
Positive = price down + volume up (accumulation) → LONG.

This is different from OI-price divergence (H-044) because it uses regular trading
volume instead of open interest. Volume is more universally available and captures
different information (total activity vs open positions).

Parameter grid: price_lb [10,20,30] × vol_lb [10,20,30] × R [3,5,7] × N [3,4]
  = 3×3×3×2 = 54 combos
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

PRICE_LBS = [10, 20, 30]
VOL_LBS = [10, 20, 30]
REBAL_FREQS = [3, 5, 7]
N_POSITIONS = [3, 4]

WF_FOLDS = 6
WF_TEST_DAYS = 90
WF_MIN_TRAIN = 180


def load_data():
    closes = {}
    volumes = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        closes[asset] = df["close"]
        volumes[asset] = df["volume"]
    closes = pd.DataFrame(closes).sort_index().dropna(how="all").ffill().dropna(how="all")
    volumes = pd.DataFrame(volumes).reindex(closes.index).ffill()
    return closes, volumes


def compute_signal(closes, volumes, price_lb, vol_lb):
    """
    Signal = rank(volume_change) - rank(price_change).
    High signal = volume rising more than price (accumulation) → LONG.
    Low signal = price rising more than volume (exhaustion) → SHORT.
    """
    price_mom = closes.pct_change(price_lb)
    vol_mom = volumes.pct_change(vol_lb)

    # Cross-sectional rank on each day
    price_rank = price_mom.rank(axis=1, pct=True)
    vol_rank = vol_mom.rank(axis=1, pct=True)

    # Divergence: volume rank minus price rank
    # High = volume growing faster than price (accumulation) → bullish
    # Low = price growing faster than volume (exhaustion) → bearish
    signal = vol_rank - price_rank

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
    print("H-306: Volume-Price Divergence Factor")
    print("=" * 70)

    closes, volumes = load_data()
    print(f"Loaded {len(ASSETS)} assets, {len(closes)} daily bars")

    h012_rets = compute_h012_returns(closes)

    results = []
    total = len(PRICE_LBS) * len(VOL_LBS) * len(REBAL_FREQS) * len(N_POSITIONS)
    print(f"\nRunning {total} parameter combinations...")

    for plb, vlb, rebal, n_pos in product(PRICE_LBS, VOL_LBS, REBAL_FREQS, N_POSITIONS):
        signal = compute_signal(closes, volumes, plb, vlb)
        eq = simulate(closes, signal, rebal, n_pos)
        if len(eq) < 100:
            continue
        rets = eq.pct_change().dropna()
        sr = sharpe_ratio(rets, periods_per_year=PPY)
        ar = annual_return(eq, PPY)
        dd = max_drawdown(eq)

        common = rets.index.intersection(h012_rets.index)
        corr_012 = rets.reindex(common).corr(h012_rets.reindex(common))

        label = f"P{plb}_V{vlb}_R{rebal}_N{n_pos}"
        results.append({
            "label": label, "price_lb": plb, "vol_lb": vlb, "rebal": rebal,
            "n_pos": n_pos, "sharpe": sr, "annual_return": ar,
            "max_dd": dd, "corr_h012": corr_012,
        })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    pct_positive = n_positive / len(df) * 100
    print(f"\nIS Results: {n_positive}/{len(df)} positive Sharpe ({pct_positive:.1f}%)")

    # Direction
    accum_pos = (df["sharpe"] > 0).sum()
    exh_pos = (df["sharpe"] < 0).sum()
    print(f"  Accumulation-long (vol>price rank): {accum_pos}/{len(df)} ({accum_pos/len(df)*100:.1f}%)")
    print(f"  Exhaustion-long (price>vol rank): {exh_pos}/{len(df)} ({exh_pos/len(df)*100:.1f}%)")

    best = df.loc[df["sharpe"].idxmax()]
    print(f"\nBest config: {best['label']}")
    print(f"  Sharpe: {best['sharpe']:.3f}, Annual: {best['annual_return']*100:.1f}%, DD: {best['max_dd']*100:.1f}%")
    print(f"  Corr H-012: {best['corr_h012']:.3f}")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")

    # Walk-forward
    signal = compute_signal(closes, volumes, int(best["price_lb"]), int(best["vol_lb"]))
    wf = walk_forward(closes, signal, int(best["rebal"]), int(best["n_pos"]))
    wf_sharpes = [s for _, s in wf] if wf else []
    n_wf_pos = sum(1 for s in wf_sharpes if s > 0)
    if wf:
        print(f"\nWF: {n_wf_pos}/{len(wf)} positive, mean {np.mean(wf_sharpes):.3f}")
        for fold, sr in wf:
            print(f"  Fold {fold}: Sharpe {sr:.3f}")

    # Split-half
    mid = len(signal) // 2
    eq_h1 = simulate(closes, signal, int(best["rebal"]), int(best["n_pos"]), 0, mid)
    eq_h2 = simulate(closes, signal, int(best["rebal"]), int(best["n_pos"]), mid, len(signal))
    sr_h1 = sharpe_ratio(eq_h1.pct_change().dropna(), periods_per_year=PPY)
    sr_h2 = sharpe_ratio(eq_h2.pct_change().dropna(), periods_per_year=PPY)
    print(f"\nSplit-half: H1={sr_h1:.3f}, H2={sr_h2:.3f}")

    # Save
    out = {
        "hypothesis": "H-306", "name": "Volume-Price Divergence",
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
