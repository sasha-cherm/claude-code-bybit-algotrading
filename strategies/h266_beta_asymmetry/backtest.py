#!/usr/bin/env python3
"""
H-266: Conditional Beta Asymmetry Factor (13 Non-BTC Assets)

Idea: For each asset, compute beta to BTC separately on BTC-up days and BTC-down days.
The ratio (up_beta / down_beta) captures asymmetric market participation.
Assets with high ratio participate more in rallies, less in crashes.

Different from:
- H-236 (Co-Skewness): measures third moment co-movement, REJECTED (all crypto crashes together)
- H-238 (Downside Beta): measures beta only on BTC-down days, CONFIRMED but redundant (corr 0.738 with regular beta)
- H-263 (Relative Strength vs BTC): simple return difference, not beta-adjusted

Signal construction:
  1. Split last N days into BTC-up days (ret > 0) and BTC-down days (ret <= 0)
  2. For each asset: up_beta = cov(asset_up, btc_up) / var(btc_up)
  3. For each asset: down_beta = cov(asset_down, btc_down) / var(btc_down)
  4. Asymmetry = up_beta / down_beta (or up_beta - down_beta)
  5. Rank XS: long high asymmetry (more upside participation), short low asymmetry

Parameter grid:
  Lookback: [20, 30, 60, 90]
  Rebal freq: [3, 5, 7]
  N: [3, 4]
  Direction: [high_asym_long, low_asym_long]
  Construction: [ratio, difference]
  Total: 4 x 3 x 2 x 2 x 2 = 96 combos
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS_ALL = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]
NON_BTC = [a for a in ASSETS_ALL if a != "BTC/USDT"]

LOOKBACKS = [20, 30, 60, 90]
REBALS = [3, 5, 7]
NS = [3, 4]
DIRECTIONS = ["high_asym_long", "low_asym_long"]
CONSTRUCTIONS = ["ratio", "difference"]

COST_PER_SIDE = 0.0005

WF_FOLDS = 6
WF_TEST_DAYS = 90
WF_TRAIN_MIN = 120


def load_data():
    data_dir = ROOT / "data"
    closes = {}
    for sym in ASSETS_ALL:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if "close" not in df.columns or len(df) < 200:
            continue
        dc = df["close"].copy()
        if dc.index.tzinfo is not None:
            dc.index = dc.index.tz_localize(None)
        closes[sym] = dc
    closes = pd.DataFrame(closes).dropna(how="all").ffill().dropna()
    return closes


def compute_beta_asymmetry(closes, lookback, construction):
    """Compute conditional beta asymmetry for non-BTC assets."""
    rets = closes.pct_change().dropna()
    btc_ret = rets["BTC/USDT"]
    cols = [c for c in rets.columns if c != "BTC/USDT"]

    asym_arr = np.full((len(rets), len(cols)), np.nan)

    for i in range(lookback, len(rets)):
        window = slice(i - lookback, i)
        btc_w = btc_ret.iloc[window].values
        up_mask = btc_w > 0
        down_mask = btc_w <= 0

        n_up = up_mask.sum()
        n_down = down_mask.sum()
        if n_up < 5 or n_down < 5:
            continue

        btc_up = btc_w[up_mask]
        btc_down = btc_w[down_mask]
        var_up = np.var(btc_up, ddof=1)
        var_down = np.var(btc_down, ddof=1)

        if var_up < 1e-12 or var_down < 1e-12:
            continue

        for j, col in enumerate(cols):
            asset_w = rets[col].iloc[window].values
            asset_up = asset_w[up_mask]
            asset_down = asset_w[down_mask]

            up_beta = np.cov(asset_up, btc_up, ddof=1)[0, 1] / var_up
            down_beta = np.cov(asset_down, btc_down, ddof=1)[0, 1] / var_down

            if construction == "ratio":
                if abs(down_beta) < 0.01:
                    continue
                asym_arr[i, j] = up_beta / down_beta
            else:  # difference
                asym_arr[i, j] = up_beta - down_beta

    return pd.DataFrame(asym_arr, index=rets.index, columns=cols)


def evaluate(rets, label=""):
    if rets is None or len(rets) < 30:
        return None
    ann = rets.mean() * 365
    vol = rets.std() * np.sqrt(365)
    shp = ann / vol if vol > 1e-8 else 0.0
    cum = (1 + rets).cumprod()
    mdd = (cum / cum.cummax() - 1).min()
    return {
        "label": label, "sharpe": round(float(shp), 4),
        "annual": round(float(ann * 100), 2), "dd": round(float(mdd * 100), 2),
        "days": len(rets),
    }


def backtest_factor(closes, signal_df, rebal_freq, n, direction):
    cols = list(signal_df.columns)
    # Use only non-BTC for returns too
    ret_cols = [c for c in cols if c in closes.columns]
    if len(ret_cols) < 2 * n:
        return None
    returns = closes[ret_cols].pct_change().dropna()
    signal_df = signal_df[ret_cols].reindex(returns.index)
    dates = returns.index

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=ret_cols)
    prev_weights = pd.Series(0.0, index=ret_cols)

    for i in range(1, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": float(day_ret)})
        if i - last_rebal < rebal_freq:
            continue
        cv = signal_df.iloc[i]
        valid = cv.dropna()
        if len(valid) < 2 * n:
            continue
        if direction == "high_asym_long":
            ranked = valid.sort_values(ascending=False)
        else:
            ranked = valid.sort_values(ascending=True)
        longs = ranked.index[:n]
        shorts = ranked.index[-n:]
        new_weights = pd.Series(0.0, index=ret_cols)
        for s in longs:
            new_weights[s] = 1.0 / n
        for s in shorts:
            new_weights[s] = -1.0 / n
        turnover = (new_weights - prev_weights).abs().sum()
        tc = turnover * COST_PER_SIDE
        if portfolio_rets:
            portfolio_rets[-1]["return"] -= tc
        prev_weights = weights.copy()
        weights = new_weights
        last_rebal = i

    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def backtest_momentum(closes, lookback=60, rebal_freq=5, n=4):
    """H-012 momentum benchmark for correlation."""
    rets = closes.pct_change().dropna()
    dates = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": float((rets.iloc[i] * weights).sum())})
        if i - last_rebal >= rebal_freq:
            mom = closes.iloc[i - 1] / closes.iloc[i - 1 - lookback] - 1
            ranked = mom.sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def safe_corr(a, b):
    if a is None or b is None:
        return float("nan")
    common = a.dropna().index.intersection(b.dropna().index)
    if len(common) < 30:
        return float("nan")
    return round(float(np.corrcoef(a.loc[common].values, b.loc[common].values)[0, 1]), 3)


def run_walk_forward(closes):
    n_total = len(closes)
    fold_results = []
    for fold in range(WF_FOLDS):
        oos_end = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break
        tr_c = closes.iloc[:oos_start]
        oo_c = closes.iloc[oos_start:oos_end]
        if len(tr_c) < WF_TRAIN_MIN or len(oo_c) < 20:
            break
        best_sharpe, best_params = -np.inf, None
        for lb in LOOKBACKS:
            for con in CONSTRUCTIONS:
                sig = compute_beta_asymmetry(tr_c, lb, con)
                for rf in REBALS:
                    for nn in NS:
                        for d in DIRECTIONS:
                            r = backtest_factor(tr_c, sig, rf, nn, d)
                            ev = evaluate(r)
                            if ev and ev["sharpe"] > best_sharpe:
                                best_sharpe = ev["sharpe"]
                                best_params = (lb, con, rf, nn, d)
        if best_params is None:
            fold_results.append({"fold": fold + 1, "oos_sharpe": None})
            continue
        lb, con, rf, nn, d = best_params
        full_sig = compute_beta_asymmetry(closes.iloc[:oos_end], lb, con)
        oos_sig = full_sig.iloc[oos_start:oos_end]
        oos_r = backtest_factor(oo_c, oos_sig, rf, nn, d)
        oos_ev = evaluate(oos_r)
        fold_results.append({
            "fold": fold + 1, "is_params": f"LB{lb}_{con}_R{rf}_N{nn}_{d}",
            "is_sharpe": round(best_sharpe, 3),
            "oos_sharpe": oos_ev["sharpe"] if oos_ev else None,
        })
    return fold_results


def run_split_half(closes):
    half = len(closes) // 2
    h1c, h2c = closes.iloc[:half], closes.iloc[half:]
    h1_sharpes, h2_sharpes = [], []
    for lb in LOOKBACKS:
        for con in CONSTRUCTIONS:
            h1_sig = compute_beta_asymmetry(h1c, lb, con)
            h2_sig = compute_beta_asymmetry(h2c, lb, con)
            for rf in REBALS:
                for nn in NS:
                    for d in DIRECTIONS:
                        e1 = evaluate(backtest_factor(h1c, h1_sig, rf, nn, d))
                        e2 = evaluate(backtest_factor(h2c, h2_sig, rf, nn, d))
                        if e1:
                            h1_sharpes.append(e1["sharpe"])
                        if e2:
                            h2_sharpes.append(e2["sharpe"])
    if not h1_sharpes or not h2_sharpes:
        return None, None, None, None
    return (round(max(h1_sharpes), 3), round(max(h2_sharpes), 3),
            round(float(np.mean(h1_sharpes)), 3), round(float(np.mean(h2_sharpes)), 3))


def main():
    print("=" * 60)
    print("  H-266: Conditional Beta Asymmetry Factor")
    print("=" * 60)

    print("\nLoading daily data...")
    closes = load_data()
    n_assets, n_days = len(closes.columns), len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")

    total_combos = len(LOOKBACKS) * len(CONSTRUCTIONS) * len(REBALS) * len(NS) * len(DIRECTIONS)

    # Pre-compute signals
    print("\nPre-computing beta asymmetry signals...")
    sig_cache = {}
    for lb in LOOKBACKS:
        for con in CONSTRUCTIONS:
            key = (lb, con)
            sig_cache[key] = compute_beta_asymmetry(closes, lb, con)
            print(f"  LB={lb}, {con} done")

    # Stage 1: IS Parameter Scan
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")
    all_results = []
    count = 0
    for lb in LOOKBACKS:
        for con in CONSTRUCTIONS:
            sig = sig_cache[(lb, con)]
            for rf in REBALS:
                for nn in NS:
                    for d in DIRECTIONS:
                        count += 1
                        r = backtest_factor(closes, sig, rf, nn, d)
                        ev = evaluate(r, f"LB{lb}_{con}_R{rf}_N{nn}_{d}")
                        if ev:
                            all_results.append(ev)
    print(f"Evaluated {count} combos, {len(all_results)} valid")

    if not all_results:
        print("No valid results!")
        return

    positive = [r for r in all_results if r["sharpe"] > 0]
    is_pct = len(positive) / len(all_results) * 100
    sharpes = [r["sharpe"] for r in all_results]
    print(f"IS positive: {len(positive)}/{len(all_results)} ({is_pct:.1f}%)")
    print(f"IS Sharpe: mean={np.mean(sharpes):.3f}, median={np.median(sharpes):.3f}, best={max(sharpes):.3f}")

    # Dominant direction
    dir_counts = {"high_asym_long": 0, "low_asym_long": 0}
    for r in positive:
        for d in DIRECTIONS:
            if d in r["label"]:
                dir_counts[d] += 1
    dom_dir = max(dir_counts, key=dir_counts.get)
    dom_pct = dir_counts[dom_dir] / len(positive) * 100 if positive else 0
    print(f"Dominant direction: {dom_dir} ({dom_pct:.1f}%)")

    best = max(all_results, key=lambda x: x["sharpe"])
    print(f"Best combo: {best['label']} — Sharpe {best['sharpe']}, Ann {best['annual']}%, DD {best['dd']}%")

    # DECISION GATE
    if is_pct < 80:
        print(f"\n*** REJECTED at Stage 1: IS {is_pct:.1f}% < 80% threshold ***")
        save_results(all_results, is_pct, dom_dir, dom_pct, best, None, None, None)
        return

    # Stage 2: Walk-forward
    print(f"\n--- Stage 2: Walk-Forward ({WF_FOLDS} folds x {WF_TEST_DAYS}d) ---")
    wf = run_walk_forward(closes)
    for f in wf:
        print(f"  Fold {f['fold']}: IS={f.get('is_sharpe','N/A')}, OOS={f.get('oos_sharpe','N/A')} | {f.get('is_params','N/A')}")
    oos_sharpes = [f["oos_sharpe"] for f in wf if f.get("oos_sharpe") is not None]
    wf_positive = sum(1 for s in oos_sharpes if s > 0)
    wf_mean = np.mean(oos_sharpes) if oos_sharpes else 0
    print(f"WF positive: {wf_positive}/{len(oos_sharpes)}, mean OOS Sharpe: {wf_mean:.3f}")

    # Stage 3: Split-half
    print("\n--- Stage 3: Split-Half ---")
    h1_best, h2_best, h1_mean, h2_mean = run_split_half(closes)
    print(f"H1 best={h1_best}, H2 best={h2_best}")
    print(f"H1 mean={h1_mean}, H2 mean={h2_mean}")

    # Stage 4: Correlation with H-012
    print("\n--- Stage 4: Correlation with H-012 (Momentum) ---")
    mom_rets = backtest_momentum(closes)
    best_key = (int(best["label"].split("_")[0][2:]),
                best["label"].split("_")[1],
                int(best["label"].split("_R")[1].split("_")[0]),
                int(best["label"].split("_N")[1].split("_")[0]),
                "_".join(best["label"].split("_")[-2:]) if "low" in best["label"] else "_".join(best["label"].split("_")[-2:]))
    # Simpler: just re-run the best
    lb_str = best["label"].split("_")[0]
    lb = int(lb_str[2:])
    con = best["label"].split("_")[1]
    sig = sig_cache[(lb, con)]
    rf_str = [p for p in best["label"].split("_") if p.startswith("R")][0]
    rf = int(rf_str[1:])
    nn_str = [p for p in best["label"].split("_") if p.startswith("N")][0]
    nn = int(nn_str[1:])
    d = "high_asym_long" if "high_asym_long" in best["label"] else "low_asym_long"
    best_rets = backtest_factor(closes, sig, rf, nn, d)
    corr_h012 = safe_corr(best_rets, mom_rets)
    print(f"Correlation with H-012: {corr_h012}")

    save_results(all_results, is_pct, dom_dir, dom_pct, best, wf, (h1_best, h2_best, h1_mean, h2_mean), corr_h012)


def save_results(all_results, is_pct, dom_dir, dom_pct, best, wf, split_half, corr_h012):
    out = {
        "hypothesis": "H-266",
        "name": "Conditional Beta Asymmetry Factor",
        "is_positive_pct": round(is_pct, 1),
        "is_total": len(all_results),
        "dom_direction": dom_dir,
        "dom_pct": round(dom_pct, 1),
        "best": best,
        "mean_sharpe": round(float(np.mean([r["sharpe"] for r in all_results])), 3),
        "walk_forward": wf,
        "split_half": split_half,
        "corr_h012": corr_h012,
    }
    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
