#!/usr/bin/env python3
"""
H-243: Funding-Premium Divergence Factor

Idea: Compare the cross-sectional rank of funding rate (H-053) vs premium index
(H-052) for each asset. When these two positioning signals disagree, the
divergence creates a distinct signal. E.g., high funding (crowd bullish via
leverage) but low premium (spot discounted) = unusual tension.

Signal construction:
  1. Compute rolling avg funding rate rank (XS) per asset.
  2. Compute rolling avg premium index rank (XS) per asset.
  3. Divergence = |funding_rank - premium_rank| or signed difference.
  4. Long assets with specific divergence pattern, short opposite.

Novel because: H-053 and H-052 are both CONFIRMED individually, but their
*disagreement* has never been tested as a signal. This is a second-order
"meta-factor" combining two orthogonal positioning measures.

Parameter grid:
  Lookback  : [5, 10, 15, 20]
  Rebal freq: [3, 5, 7]
  N         : [3, 4]
  Direction : [fund_high_prem_low_long, fund_low_prem_high_long]
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

LOOKBACKS  = [5, 10, 15, 20]
REBALS     = [3, 5, 7]
NS         = [3, 4]
DIRECTIONS = ["fund_high_prem_low_long", "fund_low_prem_high_long"]

COST_PER_SIDE = 0.0005

WF_FOLDS     = 6
WF_TEST_DAYS = 90
WF_TRAIN_MIN = 120


def load_data():
    """Load daily closes, funding rates, and premium index."""
    data_dir = ROOT / "data"
    closes_d, funding_d, premium_d = {}, {}, {}

    # Load premium data (long format with 'asset' column)
    prem_path = data_dir / "all_assets_premium_daily.parquet"
    prem_by_asset = {}
    if prem_path.exists():
        pp = pd.read_parquet(prem_path)
        if "asset" in pp.columns and "close" in pp.columns:
            for asset_name, grp in pp.groupby("asset"):
                ts = grp["timestamp"] if "timestamp" in grp.columns else grp.index
                prem_series = pd.Series(grp["close"].values, index=pd.to_datetime(ts).values)
                prem_series.index = prem_series.index.tz_localize(None) if hasattr(prem_series.index, 'tz_localize') and prem_series.index.tzinfo is not None else prem_series.index
                prem_by_asset[asset_name] = prem_series

    for sym in ASSETS_ALL:
        safe = sym.replace("/", "_")
        d_path = data_dir / f"{safe}_1d.parquet"
        if not d_path.exists():
            continue
        df_d = pd.read_parquet(d_path)
        if "close" not in df_d.columns or len(df_d) < 200:
            continue
        dc = df_d["close"].copy()
        if dc.index.tzinfo is not None:
            dc.index = dc.index.tz_localize(None)
        closes_d[sym] = dc

        # Funding rate — try both naming patterns
        ticker = sym.replace("/", "")  # e.g. BTCUSDT
        fund_path = data_dir / f"{safe}_USDT_funding.parquet"
        if not fund_path.exists():
            fund_path = data_dir / f"funding_{ticker}.parquet"
        if fund_path.exists():
            ff = pd.read_parquet(fund_path)
            col = "funding_rate" if "funding_rate" in ff.columns else "fundingRate" if "fundingRate" in ff.columns else None
            if col:
                fr = ff[col].copy()
                if fr.index.tzinfo is not None:
                    fr.index = fr.index.tz_localize(None)
                fr_daily = fr.resample("1D").mean()
                funding_d[sym] = fr_daily

        # Premium from pre-loaded data
        asset_short = sym.split("/")[0]  # e.g. "BTC"
        if asset_short in prem_by_asset:
            premium_d[sym] = prem_by_asset[asset_short]

    closes = pd.DataFrame(closes_d).dropna(how="all").ffill().dropna()
    funding = pd.DataFrame(funding_d).reindex(closes.index).ffill()
    premium = pd.DataFrame(premium_d).reindex(closes.index).ffill()

    return closes, funding, premium


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


def compute_divergence(funding, premium, lookback):
    """Compute funding-premium rank divergence per asset."""
    # Rolling average of each
    fund_avg = funding.rolling(lookback, min_periods=max(lookback // 2, 3)).mean()
    prem_avg = premium.rolling(lookback, min_periods=max(lookback // 2, 3)).mean()

    # Cross-sectional rank each day (0 to 1)
    fund_rank = fund_avg.rank(axis=1, pct=True)
    prem_rank = prem_avg.rank(axis=1, pct=True)

    # Divergence = funding rank - premium rank
    # Positive = high funding rank but low premium rank (bullish leverage, but spot discounted)
    divergence = fund_rank - prem_rank
    return divergence


def backtest_divergence(closes, funding, premium, lookback, rebal_freq, n, direction):
    cols = list(closes.columns)
    # Only use assets that have both funding and premium data
    valid_assets = [c for c in cols if c in funding.columns and c in premium.columns]
    if len(valid_assets) < 2 * n:
        return None

    returns = closes[valid_assets].pct_change().dropna()
    div = compute_divergence(funding[valid_assets], premium[valid_assets], lookback)
    div = div.reindex(returns.index)
    dates = returns.index
    warmup = lookback + 5

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=valid_assets)
    prev_weights = pd.Series(0.0, index=valid_assets)

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": float(day_ret)})
        if i - last_rebal < rebal_freq:
            continue
        dv = div.iloc[i]
        valid = dv.dropna()
        if len(valid) < 2 * n:
            continue
        if direction == "fund_high_prem_low_long":
            # Long assets where funding rank >> premium rank (bullish leverage, discounted spot)
            ranked = valid.sort_values(ascending=False)
        else:
            # Long assets where funding rank << premium rank (bearish leverage, premium spot)
            ranked = valid.sort_values(ascending=True)
        longs = ranked.index[:n]
        shorts = ranked.index[-n:]
        new_weights = pd.Series(0.0, index=valid_assets)
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


def run_walk_forward(closes, funding, premium):
    n_total = len(closes)
    fold_results = []
    for fold in range(WF_FOLDS):
        oos_end = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break
        tr_c = closes.iloc[:oos_start]
        tr_f, tr_p = funding.iloc[:oos_start], premium.iloc[:oos_start]
        oo_c = closes.iloc[oos_start:oos_end]
        oo_f, oo_p = funding.iloc[oos_start:oos_end], premium.iloc[oos_start:oos_end]
        if len(tr_c) < WF_TRAIN_MIN or len(oo_c) < 20:
            break
        best_sharpe, best_params = -np.inf, None
        for lb in LOOKBACKS:
            for rf in REBALS:
                for nn in NS:
                    for d in DIRECTIONS:
                        r = backtest_divergence(tr_c, tr_f, tr_p, lb, rf, nn, d)
                        ev = evaluate(r)
                        if ev and ev["sharpe"] > best_sharpe:
                            best_sharpe = ev["sharpe"]
                            best_params = (lb, rf, nn, d)
        if best_params is None:
            fold_results.append({"fold": fold + 1, "oos_sharpe": None})
            continue
        lb, rf, nn, d = best_params
        oos_r = backtest_divergence(oo_c, oo_f, oo_p, lb, rf, nn, d)
        oos_ev = evaluate(oos_r)
        fold_results.append({
            "fold": fold + 1, "is_params": f"LB{lb}_R{rf}_N{nn}_{d}",
            "is_sharpe": round(best_sharpe, 3),
            "oos_sharpe": oos_ev["sharpe"] if oos_ev else None,
        })
    return fold_results


def run_split_half(closes, funding, premium):
    half = len(closes) // 2
    h1c, h1f, h1p = closes.iloc[:half], funding.iloc[:half], premium.iloc[:half]
    h2c, h2f, h2p = closes.iloc[half:], funding.iloc[half:], premium.iloc[half:]
    h1_sharpes, h2_sharpes = [], []
    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                for d in DIRECTIONS:
                    e1 = evaluate(backtest_divergence(h1c, h1f, h1p, lb, rf, nn, d))
                    e2 = evaluate(backtest_divergence(h2c, h2f, h2p, lb, rf, nn, d))
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
    print("  H-243: Funding-Premium Divergence Factor")
    print("=" * 60)

    print("\nLoading daily data + funding + premium...")
    closes, funding, premium = load_data()
    n_assets, n_days = len(closes.columns), len(closes)
    n_fund = len([c for c in funding.columns if funding[c].notna().sum() > 50])
    n_prem = len([c for c in premium.columns if premium[c].notna().sum() > 50])
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Funding data: {n_fund} assets, Premium data: {n_prem} assets")
    print(f"Date range: {closes.index[0]} -> {closes.index[-1]}")

    if n_fund < 6 or n_prem < 6:
        print(f"\nInsufficient funding ({n_fund}) or premium ({n_prem}) data. Need >= 6 assets.")
        print("REJECTED — insufficient data.")
        result = {
            "hypothesis": "H-243", "name": "Funding-Premium Divergence",
            "status": "REJECTED", "reason": f"Insufficient data: {n_fund} funding, {n_prem} premium assets",
            "n_assets": n_assets, "n_days": n_days,
        }
        with open(Path(__file__).parent / "results.json", "w") as f:
            json.dump(result, f, indent=2)
        return

    total_combos = len(LOOKBACKS) * len(REBALS) * len(NS) * len(DIRECTIONS)

    # Stage 1: IS Parameter Scan
    print(f"\n--- Stage 1: IS Parameter Scan ({total_combos} combos) ---")
    all_results = []
    count = 0
    for lb in LOOKBACKS:
        for rf in REBALS:
            for nn in NS:
                for d in DIRECTIONS:
                    count += 1
                    r = backtest_divergence(closes, funding, premium, lb, rf, nn, d)
                    ev = evaluate(r, f"LB{lb}_R{rf}_N{nn}_{d}")
                    if ev:
                        ev["lb"], ev["rf"], ev["n"], ev["dir"] = lb, rf, nn, d
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

    best_dir = None
    best_dir_pct = 0
    for d in DIRECTIONS:
        sub = df_res[df_res["dir"] == d]
        d_pct = int((sub["sharpe"] > 0).sum()) / len(sub) * 100 if len(sub) > 0 else 0
        if d_pct > best_dir_pct:
            best_dir_pct = d_pct
            best_dir = d

    df_sorted = df_res.sort_values("sharpe", ascending=False)
    print(f"\n  Top 5:")
    for _, row in df_sorted.head(5).iterrows():
        print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}_{row['dir']}: "
              f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

    best_row = df_sorted.iloc[0]

    is_pass = pct_pos >= 80.0
    dom_dir_pass = best_dir_pct >= 80.0

    if not is_pass and not dom_dir_pass:
        print(f"\n*** FAIL IS: overall {pct_pos:.1f}%, best dir {best_dir} {best_dir_pct:.1f}% < 80%. REJECTED. ***")
        result = {
            "hypothesis": "H-243", "name": "Funding-Premium Divergence",
            "status": "REJECTED", "reason": f"IS {pct_pos:.1f}% / dom dir {best_dir_pct:.1f}% < 80%",
            "is_positive_rate": round(pct_pos, 1), "is_mean_sharpe": round(mean_shp, 3),
            "best_dir": best_dir, "best_dir_pct": round(best_dir_pct, 1),
            "best_sharpe": round(float(best_row["sharpe"]), 3),
            "n_assets": n_assets, "n_days": n_days,
        }
        with open(Path(__file__).parent / "results.json", "w") as f:
            json.dump(result, f, indent=2)
        return

    # Stage 2: Walk-Forward
    print(f"\n--- Stage 2: Walk-Forward ({WF_FOLDS} folds, {WF_TEST_DAYS}d OOS) ---")
    wf = run_walk_forward(closes, funding, premium)
    wf_sharpes = [r["oos_sharpe"] for r in wf if r["oos_sharpe"] is not None]
    wf_n_pos = sum(1 for s in wf_sharpes if s > 0)
    wf_mean = float(np.mean(wf_sharpes)) if wf_sharpes else 0
    for r in wf:
        print(f"  Fold {r['fold']}: OOS Sharpe = {r.get('oos_sharpe', 'N/A')}")
    print(f"  WF positive: {wf_n_pos}/{len(wf_sharpes)}, mean OOS: {wf_mean:.3f}")
    wf_pass = wf_n_pos >= 4 and wf_mean > 0

    # Stage 3: Split-Half
    print("\n--- Stage 3: Split-Half ---")
    h1_best, h2_best, h1_mean, h2_mean = run_split_half(closes, funding, premium)
    print(f"  H1 best={h1_best}, H2 best={h2_best}")
    print(f"  H1 mean={h1_mean}, H2 mean={h2_mean}")
    sh_pass = h1_best is not None and h2_best is not None and h1_best > 0 and h2_best > 0

    # Stage 4: Correlation
    print("\n--- Stage 4: Correlation with H-012 ---")
    best_r = backtest_divergence(closes, funding, premium, int(best_row["lb"]),
                                  int(best_row["rf"]), int(best_row["n"]), best_row["dir"])
    mom_r = backtest_momentum(closes)
    corr_h012 = safe_corr(best_r, mom_r)
    print(f"  Corr with H-012: {corr_h012}")
    corr_pass = abs(corr_h012) < 0.50 if not np.isnan(corr_h012) else True

    all_pass = (is_pass or dom_dir_pass) and wf_pass and sh_pass and corr_pass
    status = "CONFIRMED" if all_pass else "REJECTED"
    reason_parts = []
    if not (is_pass or dom_dir_pass):
        reason_parts.append(f"IS {pct_pos:.1f}%")
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
        "hypothesis": "H-243", "name": "Funding-Premium Divergence",
        "status": status, "reason": reason,
        "is_positive_rate": round(pct_pos, 1), "is_mean_sharpe": round(mean_shp, 3),
        "best_dir": best_dir, "best_dir_pct": round(best_dir_pct, 1),
        "best_params": {"lookback": int(best_row["lb"]), "rebal": int(best_row["rf"]),
                        "n": int(best_row["n"]), "dir": best_row["dir"]},
        "best_sharpe": round(float(best_row["sharpe"]), 3),
        "best_annual": round(float(best_row["annual"]), 1),
        "best_dd": round(float(best_row["dd"]), 1),
        "wf_folds": wf, "wf_positive": wf_n_pos, "wf_total": len(wf_sharpes), "wf_mean": round(wf_mean, 3),
        "split_half": {"h1_best": h1_best, "h2_best": h2_best, "h1_mean": h1_mean, "h2_mean": h2_mean},
        "corr_h012": corr_h012, "n_assets": n_assets, "n_days": n_days,
    }
    with open(Path(__file__).parent / "results.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nResults written to results.json")


if __name__ == "__main__":
    main()
