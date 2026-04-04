#!/usr/bin/env python3
"""
H-224: ADX / Trend Strength Factor (14 Assets)

Idea: Rank assets by Average Directional Index (ADX), which measures trend
strength regardless of direction. High ADX = strong trend (any direction).
Long strong-trend assets (they continue trending), short weak-trend assets
(they chop and bleed from fees/slippage).

Alternatively: low-ADX assets are range-bound and may revert.

Signal construction:
  1. Compute +DM, -DM (directional movement) per Wilder.
  2. Smooth with EMA to get +DI, -DI.
  3. ADX = smoothed |+DI - -DI| / (+DI + -DI).
  4. Rank XS: high_adx_long (trend followers) or low_adx_long (range-bound).

Parameter grid:
  ADX period: [7, 14, 20, 30]
  Rebal freq: [3, 5, 7]
  N:          [3, 4]
  Direction:  [high_adx_long, low_adx_long]
  Total: 4 x 3 x 2 x 2 = 48 combos
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

ADX_PERIODS = [7, 14, 20, 30]
REBALS      = [3, 5, 7]
NS          = [3, 4]
DIRECTIONS  = ["high_adx_long", "low_adx_long"]

COST_PER_SIDE = 0.0005

WF_FOLDS     = 6
WF_TEST_DAYS = 90
WF_TRAIN_MIN = 120


def load_daily_data():
    data_dir = ROOT / "data"
    highs_d, lows_d, closes_d = {}, {}, {}
    for sym in ASSETS_ALL:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if not all(c in df.columns for c in ["high", "low", "close"]):
            continue
        if len(df) < 200:
            continue
        highs_d[sym] = df["high"]
        lows_d[sym] = df["low"]
        closes_d[sym] = df["close"]
    closes = pd.DataFrame(closes_d).dropna(how="all").ffill().dropna()
    highs = pd.DataFrame(highs_d).reindex(closes.index).ffill().dropna()
    lows = pd.DataFrame(lows_d).reindex(closes.index).ffill().dropna()
    for df in [closes, highs, lows]:
        df.index = df.index.tz_localize(None) if df.index.tzinfo else df.index
    return highs, lows, closes


def compute_adx(highs, lows, closes, period):
    """Compute ADX for all assets."""
    adx_dict = {}
    for sym in closes.columns:
        if sym not in highs.columns or sym not in lows.columns:
            continue
        h = highs[sym].values.astype(float)
        l = lows[sym].values.astype(float)
        c = closes[sym].values.astype(float)
        n = len(c)
        if n < period * 3:
            continue

        # +DM, -DM
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)
        tr = np.zeros(n)
        for i in range(1, n):
            up_move = h[i] - h[i-1]
            down_move = l[i-1] - l[i]
            plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0
            minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0
            tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))

        # Smooth with Wilder's EMA (alpha = 1/period)
        alpha = 1.0 / period
        atr = np.zeros(n)
        sdm_plus = np.zeros(n)
        sdm_minus = np.zeros(n)
        # Initialize with simple sum
        atr[period] = np.sum(tr[1:period+1])
        sdm_plus[period] = np.sum(plus_dm[1:period+1])
        sdm_minus[period] = np.sum(minus_dm[1:period+1])
        for i in range(period+1, n):
            atr[i] = atr[i-1] - atr[i-1] / period + tr[i]
            sdm_plus[i] = sdm_plus[i-1] - sdm_plus[i-1] / period + plus_dm[i]
            sdm_minus[i] = sdm_minus[i-1] - sdm_minus[i-1] / period + minus_dm[i]

        # +DI, -DI
        plus_di = np.where(atr > 0, 100 * sdm_plus / atr, 0)
        minus_di = np.where(atr > 0, 100 * sdm_minus / atr, 0)

        # DX
        di_sum = plus_di + minus_di
        dx = np.where(di_sum > 0, 100 * np.abs(plus_di - minus_di) / di_sum, 0)

        # ADX = smoothed DX
        adx = np.zeros(n)
        start_idx = period * 2
        if start_idx < n:
            adx[start_idx] = np.mean(dx[period:start_idx+1])
            for i in range(start_idx + 1, n):
                adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period

        adx_series = pd.Series(adx, index=closes.index)
        adx_dict[sym] = adx_series

    return pd.DataFrame(adx_dict)


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


def backtest_adx(highs, lows, closes, adx_period, rebal_freq, n, direction="high_adx_long"):
    cols = list(closes.columns)
    if len(cols) < 2 * n:
        return None
    returns = closes.pct_change().dropna()
    adx_df = compute_adx(highs, lows, closes, adx_period).reindex(returns.index)
    dates = returns.index
    warmup = adx_period * 3 + 5

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=cols)
    prev_weights = pd.Series(0.0, index=cols)

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": float(day_ret)})
        if i - last_rebal < rebal_freq:
            continue
        adx_vals = adx_df.iloc[i]
        valid = adx_vals.dropna()
        valid = valid[valid > 0]
        if len(valid) < 2 * n:
            continue
        if direction == "high_adx_long":
            ranked = valid.sort_values(ascending=False)
        else:
            ranked = valid.sort_values(ascending=True)
        longs = ranked.index[:n]
        shorts = ranked.index[-n:]
        new_weights = pd.Series(0.0, index=cols)
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


def run_walk_forward(highs, lows, closes):
    n_total = len(closes)
    fold_results = []
    for fold in range(WF_FOLDS):
        oos_end = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break
        tr_h, tr_l, tr_c = highs.iloc[:oos_start], lows.iloc[:oos_start], closes.iloc[:oos_start]
        oo_h, oo_l, oo_c = highs.iloc[oos_start:oos_end], lows.iloc[oos_start:oos_end], closes.iloc[oos_start:oos_end]
        if len(tr_c) < WF_TRAIN_MIN or len(oo_c) < 20:
            break
        best_sharpe, best_params = -np.inf, None
        for ap in ADX_PERIODS:
            for rf in REBALS:
                for nn in NS:
                    for d in DIRECTIONS:
                        r = backtest_adx(tr_h, tr_l, tr_c, ap, rf, nn, d)
                        ev = evaluate(r)
                        if ev and ev["sharpe"] > best_sharpe:
                            best_sharpe = ev["sharpe"]
                            best_params = (ap, rf, nn, d)
        if best_params is None:
            fold_results.append({"fold": fold + 1, "oos_sharpe": None})
            continue
        ap, rf, nn, d = best_params
        oos_r = backtest_adx(oo_h, oo_l, oo_c, ap, rf, nn, d)
        oos_ev = evaluate(oos_r)
        fold_results.append({
            "fold": fold + 1, "is_params": f"ADX{ap}_R{rf}_N{nn}_{d}",
            "is_sharpe": round(best_sharpe, 3),
            "oos_sharpe": oos_ev["sharpe"] if oos_ev else None,
        })
    return fold_results


def run_split_half(highs, lows, closes):
    half = len(closes) // 2
    h1h, h1l, h1c = highs.iloc[:half], lows.iloc[:half], closes.iloc[:half]
    h2h, h2l, h2c = highs.iloc[half:], lows.iloc[half:], closes.iloc[half:]
    h1_sharpes, h2_sharpes = [], []
    for ap in ADX_PERIODS:
        for rf in REBALS:
            for nn in NS:
                for d in DIRECTIONS:
                    e1 = evaluate(backtest_adx(h1h, h1l, h1c, ap, rf, nn, d))
                    e2 = evaluate(backtest_adx(h2h, h2l, h2c, ap, rf, nn, d))
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
    print("  H-224: ADX / Trend Strength Factor")
    print("=" * 60)

    print("\nLoading daily OHLCV data...")
    highs, lows, closes = load_daily_data()
    n_assets, n_days = len(closes.columns), len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")

    total_combos = len(ADX_PERIODS) * len(REBALS) * len(NS) * len(DIRECTIONS)

    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")
    all_results = []
    count = 0
    for ap in ADX_PERIODS:
        for rf in REBALS:
            for nn in NS:
                for d in DIRECTIONS:
                    count += 1
                    r = backtest_adx(highs, lows, closes, ap, rf, nn, d)
                    ev = evaluate(r, f"ADX{ap}_R{rf}_N{nn}_{d}")
                    if ev:
                        ev["adx_period"], ev["rf"], ev["n"], ev["dir"] = ap, rf, nn, d
                        all_results.append(ev)
        print(f"  {count}/{total_combos} combos done...")

    if not all_results:
        print("No valid results! REJECTED.")
        return

    df_res = pd.DataFrame(all_results)
    n_pos = int((df_res["sharpe"] > 0).sum())
    pct_pos = n_pos / len(df_res) * 100
    mean_shp = float(df_res["sharpe"].mean())

    for d in DIRECTIONS:
        sub = df_res[df_res["dir"] == d]
        d_pos = int((sub["sharpe"] > 0).sum())
        d_pct = d_pos / len(sub) * 100 if len(sub) > 0 else 0
        d_mean = float(sub["sharpe"].mean()) if len(sub) > 0 else 0
        print(f"  {d}: {d_pos}/{len(sub)} positive ({d_pct:.1f}%), mean Sharpe {d_mean:.3f}")

    print(f"\n  Overall: {n_pos}/{len(df_res)} ({pct_pos:.1f}%), mean Sharpe {mean_shp:.3f}")

    best_dir, best_dir_pct = None, 0
    for d in DIRECTIONS:
        sub = df_res[df_res["dir"] == d]
        d_pct = int((sub["sharpe"] > 0).sum()) / len(sub) * 100 if len(sub) > 0 else 0
        if d_pct > best_dir_pct:
            best_dir_pct = d_pct
            best_dir = d

    df_sorted = df_res.sort_values("sharpe", ascending=False)
    print(f"\n  Top 5:")
    for _, row in df_sorted.head(5).iterrows():
        print(f"    ADX{int(row['adx_period'])}_R{int(row['rf'])}_N{int(row['n'])}_{row['dir']}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    best_row = df_sorted.iloc[0]
    is_pass = pct_pos >= 80.0
    dom_dir_pass = best_dir_pct >= 80.0

    if not is_pass and not dom_dir_pass:
        print(f"\n*** FAIL IS: overall {pct_pos:.1f}%, best dir {best_dir} {best_dir_pct:.1f}% < 80%. REJECTED. ***")
        result = {
            "hypothesis": "H-224", "name": "ADX Trend Strength",
            "status": "REJECTED", "reason": f"IS {pct_pos:.1f}% / dom dir {best_dir_pct:.1f}% < 80%",
            "is_positive_rate": round(pct_pos, 1), "is_mean_sharpe": round(mean_shp, 3),
            "best_dir": best_dir, "best_dir_pct": round(best_dir_pct, 1),
            "best_sharpe": round(float(best_row["sharpe"]), 3),
            "n_assets": n_assets, "n_days": n_days,
        }
        with open(Path(__file__).parent / "results.json", "w") as f:
            json.dump(result, f, indent=2)
        return

    print(f"\n--- Stage 2: Walk-Forward ({WF_FOLDS} folds, {WF_TEST_DAYS}d OOS) ---")
    wf = run_walk_forward(highs, lows, closes)
    wf_sharpes = [r["oos_sharpe"] for r in wf if r["oos_sharpe"] is not None]
    wf_n_pos = sum(1 for s in wf_sharpes if s > 0)
    wf_mean = float(np.mean(wf_sharpes)) if wf_sharpes else 0
    for r in wf:
        print(f"  Fold {r['fold']}: OOS Sharpe = {r.get('oos_sharpe', 'N/A')}")
    print(f"  WF positive: {wf_n_pos}/{len(wf_sharpes)}, mean OOS: {wf_mean:.3f}")
    wf_pass = wf_n_pos >= 4 and wf_mean > 0

    print("\n--- Stage 3: Split-Half ---")
    h1_best, h2_best, h1_mean, h2_mean = run_split_half(highs, lows, closes)
    print(f"  H1 best={h1_best}, H2 best={h2_best}")
    print(f"  H1 mean={h1_mean}, H2 mean={h2_mean}")
    sh_pass = h1_best is not None and h2_best is not None and h1_best > 0 and h2_best > 0

    print("\n--- Stage 4: Correlation with H-012 ---")
    best_r = backtest_adx(highs, lows, closes, int(best_row["adx_period"]), int(best_row["rf"]),
                          int(best_row["n"]), best_row["dir"])
    mom_r = backtest_momentum(closes)
    corr_h012 = safe_corr(best_r, mom_r)
    print(f"  Corr with H-012: {corr_h012}")
    corr_pass = abs(corr_h012) < 0.50 if not np.isnan(corr_h012) else True

    all_pass = (is_pass or dom_dir_pass) and wf_pass and sh_pass and corr_pass
    status = "CONFIRMED" if all_pass else "REJECTED"
    reason_parts = []
    if not is_pass and dom_dir_pass:
        reason_parts.append(f"IS overall {pct_pos:.1f}% but dom dir {best_dir_pct:.1f}%")
    if not wf_pass:
        reason_parts.append(f"WF {wf_n_pos}/{len(wf_sharpes)}")
    if not sh_pass:
        reason_parts.append("split-half fails")
    if not corr_pass:
        reason_parts.append(f"corr {corr_h012}")
    reason = "; ".join(reason_parts) if reason_parts else "all stages passed"

    print(f"\n{'='*60}")
    print(f"  RESULT: {status} — {reason}")
    print(f"{'='*60}")

    result = {
        "hypothesis": "H-224", "name": "ADX Trend Strength",
        "status": status, "reason": reason,
        "is_positive_rate": round(pct_pos, 1), "is_mean_sharpe": round(mean_shp, 3),
        "best_dir": best_dir, "best_dir_pct": round(best_dir_pct, 1),
        "best_params": {"adx_period": int(best_row["adx_period"]), "rebal": int(best_row["rf"]),
                        "n": int(best_row["n"]), "dir": best_row["dir"]},
        "best_sharpe": round(float(best_row["sharpe"]), 3),
        "best_annual": round(float(best_row["annual"]), 1),
        "best_dd": round(float(best_row["dd"]), 1),
        "wf_folds": wf if (is_pass or dom_dir_pass) else [],
        "wf_positive": wf_n_pos if (is_pass or dom_dir_pass) else 0,
        "wf_total": len(wf_sharpes) if (is_pass or dom_dir_pass) else 0,
        "wf_mean": round(wf_mean, 3) if (is_pass or dom_dir_pass) else 0,
        "split_half": {"h1_best": h1_best, "h2_best": h2_best} if (is_pass or dom_dir_pass) else {},
        "corr_h012": corr_h012 if (is_pass or dom_dir_pass) else None,
        "n_assets": n_assets, "n_days": n_days,
    }
    with open(Path(__file__).parent / "results.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nResults written to results.json")


if __name__ == "__main__":
    main()
