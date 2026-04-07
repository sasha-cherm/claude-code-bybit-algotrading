"""
H-300: Short-Term Reversal Factor (1-5 day contrarian)

Concept: Buy recent LOSERS, sell recent WINNERS over very short horizons (1-5 days).
This is the opposite of momentum — it captures mean-reversion at short time scales.

In traditional equities, short-term reversal (1-week) is one of the strongest
anomalies. In crypto, the 24/7 nature and retail-driven overreaction could make
this signal even stronger.

Signal: Negative of short-term return (1-5 day). High signal = most negative recent
return = oversold → LONG. Low signal = most positive recent return = overbought → SHORT.

Key difference from H-012 (momentum): H-012 uses 60-day lookback (trend following).
This uses 1-5 day lookback (mean reversion). Expected correlation should be LOW or
NEGATIVE with H-012.

Parameter grid: lookback [1,2,3,5] × rebal [1,2,3,5] × N [3,4] = 4×4×2 = 32 combos
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

LOOKBACKS = [1, 2, 3, 5]
REBAL_FREQS = [1, 2, 3, 5]
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


def compute_signal(closes, lookback):
    """
    Signal = NEGATIVE of short-term return.
    High signal = oversold (lost most recently) → LONG
    Low signal = overbought (gained most recently) → SHORT
    """
    short_ret = closes.pct_change(lookback)
    signal = -short_ret  # Reversal: buy losers, sell winners
    signal = signal.shift(1)  # Trade on lagged signal
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
    print("H-300: Short-Term Reversal Factor")
    print("=" * 70)

    closes = load_closes()
    print(f"Loaded {len(ASSETS)} assets, {len(closes)} daily bars")

    h012_rets = compute_h012_returns(closes)

    results = []
    total = len(LOOKBACKS) * len(REBAL_FREQS) * len(N_POSITIONS)
    print(f"\nRunning {total} parameter combinations...")

    for lookback, rebal, n_pos in product(LOOKBACKS, REBAL_FREQS, N_POSITIONS):
        signal = compute_signal(closes, lookback)
        eq = simulate(closes, signal, rebal, n_pos)
        if len(eq) < 100:
            continue
        rets = eq.pct_change().dropna()
        sr = sharpe_ratio(rets, periods_per_year=PPY)
        ar = annual_return(eq, PPY)
        dd = max_drawdown(eq)

        common = rets.index.intersection(h012_rets.index)
        corr_012 = rets.reindex(common).corr(h012_rets.reindex(common))

        label = f"LB{lookback}_R{rebal}_N{n_pos}"
        results.append({
            "label": label, "lookback": lookback, "rebal": rebal,
            "n_pos": n_pos, "sharpe": sr, "annual_return": ar,
            "max_dd": dd, "corr_h012": corr_012,
        })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    pct_positive = n_positive / len(df) * 100
    print(f"\nIS Results: {n_positive}/{len(df)} positive Sharpe ({pct_positive:.1f}%)")

    # Check direction dominance
    n_rev_pos = (df["sharpe"] > 0).sum()
    n_mom_pos = (df["sharpe"] < 0).sum()  # Negative Sharpe = momentum direction wins
    print(f"  Reversal-long direction: {n_rev_pos}/{len(df)} positive ({n_rev_pos/len(df)*100:.1f}%)")
    print(f"  Momentum direction: {n_mom_pos}/{len(df)} positive ({n_mom_pos/len(df)*100:.1f}%)")

    best = df.loc[df["sharpe"].idxmax()]
    print(f"\nBest config: {best['label']}")
    print(f"  Sharpe: {best['sharpe']:.3f}, Annual: {best['annual_return']*100:.1f}%, DD: {best['max_dd']*100:.1f}%")
    print(f"  Corr H-012: {best['corr_h012']:.3f}")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")

    # Show by lookback
    print("\nBy lookback:")
    for lb in LOOKBACKS:
        sub = df[df["lookback"] == lb]
        mean_sr = sub["sharpe"].mean()
        pos = (sub["sharpe"] > 0).sum()
        print(f"  LB{lb}: mean Sharpe {mean_sr:.3f}, {pos}/{len(sub)} positive")

    # Walk-forward on best
    signal = compute_signal(closes, int(best["lookback"]))
    wf = walk_forward(closes, signal, int(best["rebal"]), int(best["n_pos"]))
    wf_sharpes = [s for _, s in wf] if wf else []
    n_wf_pos = sum(1 for s in wf_sharpes if s > 0)
    if wf:
        print(f"\nWF: {n_wf_pos}/{len(wf)} positive, mean {np.mean(wf_sharpes):.3f}")
        for fold, sr in wf:
            print(f"  Fold {fold}: Sharpe {sr:.3f}")

    # Neighbor analysis
    best_lb = int(best["lookback"])
    best_r = int(best["rebal"])
    best_n = int(best["n_pos"])
    neighbors = df[
        (df["lookback"].isin([best_lb - 1, best_lb, best_lb + 1, best_lb + 2])) |
        (df["rebal"].isin([best_r - 1, best_r, best_r + 1, best_r + 2]))
    ]
    n_neigh_pos = (neighbors["sharpe"] > 0).sum()
    print(f"\nNeighbor robustness: {n_neigh_pos}/{len(neighbors)} positive ({n_neigh_pos/len(neighbors)*100:.1f}%)")

    # Split-half
    mid = len(signal) // 2
    eq_h1 = simulate(closes, signal, int(best["rebal"]), int(best["n_pos"]), 0, mid)
    eq_h2 = simulate(closes, signal, int(best["rebal"]), int(best["n_pos"]), mid, len(signal))
    sr_h1 = sharpe_ratio(eq_h1.pct_change().dropna(), periods_per_year=PPY)
    sr_h2 = sharpe_ratio(eq_h2.pct_change().dropna(), periods_per_year=PPY)
    print(f"\nSplit-half: H1={sr_h1:.3f}, H2={sr_h2:.3f}")

    # Additional correlations with other confirmed strategies
    # H-076: Price Efficiency (40d efficiency, top/bottom 4)
    eff_40 = (closes.pct_change().abs().rolling(40).sum()) / (closes.pct_change(40).abs())
    sig_076 = (-eff_40).shift(1)
    eq_076 = simulate(closes, sig_076, 5, 4)
    r076 = eq_076.pct_change().dropna()

    # H-031: Size (30d dollar volume)
    # Approximate with volume * close
    vol_frames = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        dfa = pd.read_parquet(fp)
        dfa.index = pd.to_datetime(dfa.index).tz_localize(None)
        vol_frames[asset] = dfa["close"] * dfa["volume"]
    dv = pd.DataFrame(vol_frames).reindex(closes.index).rolling(30).mean()
    sig_031 = dv.shift(1)
    eq_031 = simulate(closes, sig_031, 5, 5)
    r031 = eq_031.pct_change().dropna()

    best_eq = simulate(closes, signal, int(best["rebal"]), int(best["n_pos"]))
    best_rets = best_eq.pct_change().dropna()

    common = best_rets.index.intersection(r076.index)
    corr_076 = best_rets.reindex(common).corr(r076.reindex(common))
    common = best_rets.index.intersection(r031.index)
    corr_031 = best_rets.reindex(common).corr(r031.reindex(common))
    print(f"\nCorrelations: H-012={best['corr_h012']:.3f}, H-076={corr_076:.3f}, H-031={corr_031:.3f}")

    # Save
    out = {
        "hypothesis": "H-300", "name": "Short-Term Reversal",
        "total_params": len(df), "pct_positive": pct_positive,
        "best_config": best["label"], "best_sharpe": float(best["sharpe"]),
        "best_annual_return": float(best["annual_return"]),
        "best_max_dd": float(best["max_dd"]),
        "corr_h012": float(best["corr_h012"]),
        "corr_h076": float(corr_076),
        "corr_h031": float(corr_031),
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
