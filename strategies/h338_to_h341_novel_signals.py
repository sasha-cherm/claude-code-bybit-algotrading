#!/usr/bin/env python3
"""
Backtest four novel cross-sectional factors:

  H-338: Volume-Weighted Directional Pressure — sum(volume × sign(return)) over lookback,
         normalized by total volume. Captures net buying/selling pressure.
  H-339: Intraday Momentum Propagation — correlation between 1st 4h bar return and
         rest-of-day return. High propagation = predictable session flow.
  H-340: 4h Price Path Convexity — measure if intraday price accelerates or decelerates.
         Convex path (acceleration) = fresh momentum, concave = exhaustion.
  H-341: Return Concentration in High-Volume Hours — fraction of daily return that
         occurs in the top-2 volume hours. High concentration = institutional-driven moves.

Standard framework: grid search, IS robustness, WF OOS, split-half, H-012 corr.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001
SLIPPAGE_BPS = 2.0


def load_data():
    """Load hourly data, compute daily and 4h features."""
    print("Fetching hourly data for 14 assets...")
    hourly_dict = {}
    for sym in ASSETS:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df_1h) < 200:
                continue
            hourly_dict[sym] = df_1h
        except Exception as e:
            print(f"  {sym}: {e}")

    closes_dict, opens_dict, volumes_dict = {}, {}, {}
    features = {}

    for sym, df_1h in hourly_dict.items():
        daily = resample_to_daily(df_1h)
        closes_dict[sym] = daily["close"]
        opens_dict[sym] = daily["open"]
        volumes_dict[sym] = daily["volume"]

        # Compute per-day features from hourly data
        df_1h["date"] = df_1h.index.date
        df_1h["hour_return"] = df_1h["close"] / df_1h["open"] - 1

        # Resample to 4h for path analysis
        df_4h = df_1h.resample("4h").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum"
        }).dropna()
        df_4h["bar_return"] = df_4h["close"] / df_4h["open"] - 1
        df_4h["date"] = df_4h.index.date

        daily_feats = []
        for date, hourly_group in df_1h.groupby("date"):
            if len(hourly_group) < 18:  # need most of the day
                continue

            vol = hourly_group["volume"].values
            ret = hourly_group["hour_return"].values

            # H-338: Volume-weighted directional pressure
            signed_vol = vol * np.sign(ret)
            total_vol = vol.sum()
            vwdp = signed_vol.sum() / total_vol if total_vol > 0 else 0

            # H-341: Return concentration in high-volume hours
            # Sort hours by volume, take top 2
            vol_order = np.argsort(vol)[::-1]
            top2_idx = vol_order[:2]
            daily_ret = np.sum(ret)
            top2_ret = np.sum(ret[top2_idx]) if len(top2_idx) > 0 else 0
            # Fraction of daily return from top-2 hours
            ret_conc = abs(top2_ret / daily_ret) if abs(daily_ret) > 1e-8 else 0

            daily_feats.append({
                "date": pd.Timestamp(date),
                "vwdp": vwdp,
                "ret_conc": ret_conc,
            })

        # 4h-level features for H-339 and H-340
        for date, g4h in df_4h.groupby("date"):
            if len(g4h) < 4:
                continue

            # H-339: Momentum propagation (first 4h bar vs rest-of-day)
            first_ret = g4h["bar_return"].iloc[0]
            rest_rets = g4h["bar_return"].iloc[1:]
            rest_ret = rest_rets.sum()

            # H-340: Path convexity — compare first-half vs second-half 4h momentum
            half = len(g4h) // 2
            first_half_ret = g4h["bar_return"].iloc[:half].sum()
            second_half_ret = g4h["bar_return"].iloc[half:].sum()
            convexity = second_half_ret - first_half_ret  # positive = accelerating

            # Find matching daily feat entry
            for df_entry in daily_feats:
                if df_entry["date"] == pd.Timestamp(date):
                    df_entry["first_bar_ret"] = first_ret
                    df_entry["rest_day_ret"] = rest_ret
                    df_entry["convexity"] = convexity
                    break

        if daily_feats:
            feat_df = pd.DataFrame(daily_feats).set_index("date")
            feat_df.index = pd.to_datetime(feat_df.index, utc=True)
            features[sym] = feat_df

    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    opens = pd.DataFrame(opens_dict).reindex(closes.index).ffill().dropna()
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill().dropna()
    idx = closes.index.intersection(opens.index).intersection(volumes.index)
    closes, opens, volumes = closes.loc[idx], opens.loc[idx], volumes.loc[idx]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Features computed for {len(features)} assets")

    return closes, opens, volumes, features


def backtest_factor(closes, factor_fn, lookbacks, rebals, ns, directions,
                    factor_name, extra_data=None):
    returns = closes.pct_change()
    slippage = SLIPPAGE_BPS / 10_000
    results = []

    for lookback in lookbacks:
        for rebal in rebals:
            for n in ns:
                for direction in directions:
                    warmup = lookback + 10
                    pnl_daily = []
                    positions = {}
                    days_since = rebal

                    for i in range(warmup, len(closes)):
                        days_since += 1
                        if days_since >= rebal:
                            scores = factor_fn(extra_data, lookback, i)
                            if scores is None or len(scores) < 2 * n:
                                continue

                            if direction.endswith("_long"):
                                high_first = direction.startswith("high")
                                ranked = scores.sort_values(ascending=not high_first)
                            else:
                                ranked = scores.sort_values(ascending=False)

                            longs = set(ranked.index[:n])
                            shorts = set(ranked.index[-n:])
                            old_syms = set(positions.keys())
                            new_syms = longs | shorts
                            changed = old_syms.symmetric_difference(new_syms)
                            fee_cost = len(changed) * FEE_RATE / (2 * n)
                            slip_cost = len(changed) * slippage / (2 * n)

                            positions = {}
                            for sym in longs:
                                positions[sym] = 1.0 / n
                            for sym in shorts:
                                positions[sym] = -1.0 / n
                            days_since = 0
                            daily_ret = -fee_cost - slip_cost
                        else:
                            daily_ret = 0.0

                        for sym, w in positions.items():
                            if sym in returns.columns:
                                r = returns[sym].iloc[i]
                                if np.isfinite(r):
                                    daily_ret += w * r
                        pnl_daily.append(daily_ret)

                    if len(pnl_daily) < 100:
                        continue

                    pnl = np.array(pnl_daily)
                    sharpe = float(np.mean(pnl) / np.std(pnl) * np.sqrt(365)) if np.std(pnl) > 0 else 0
                    ann_ret = float((1 + np.mean(pnl)) ** 365 - 1) * 100
                    cum = np.cumprod(1 + pnl)
                    dd = float((1 - cum / np.maximum.accumulate(cum)).max()) * 100

                    results.append({
                        "factor": factor_name,
                        "lookback": lookback,
                        "rebal": rebal,
                        "n": n,
                        "direction": direction,
                        "sharpe": round(sharpe, 3),
                        "ann_ret": round(ann_ret, 1),
                        "max_dd": round(dd, 1),
                        "n_days": len(pnl_daily),
                        "pnl_daily": pnl,
                    })

    return results


def walk_forward(closes, factor_fn, lookback, rebal, n, direction,
                 extra_data=None, n_folds=6):
    returns = closes.pct_change()
    slippage = SLIPPAGE_BPS / 10_000
    total_bars = len(closes)
    warmup = lookback + 10
    usable = total_bars - warmup
    fold_size = usable // n_folds

    oos_sharpes = []
    for fold in range(n_folds):
        test_start = warmup + fold * fold_size
        test_end = min(test_start + fold_size, total_bars)
        if test_end > total_bars:
            break

        positions = {}
        days_since = rebal
        pnl_daily = []

        for i in range(test_start, test_end):
            days_since += 1
            if days_since >= rebal:
                scores = factor_fn(extra_data, lookback, i)
                if scores is None or len(scores) < 2 * n:
                    continue

                if direction.endswith("_long"):
                    high_first = direction.startswith("high")
                    ranked = scores.sort_values(ascending=not high_first)
                else:
                    ranked = scores.sort_values(ascending=False)

                longs = set(ranked.index[:n])
                shorts = set(ranked.index[-n:])
                old_syms = set(positions.keys())
                new_syms = longs | shorts
                changed = old_syms.symmetric_difference(new_syms)
                fee_cost = len(changed) * FEE_RATE / (2 * n)
                slip_cost = len(changed) * slippage / (2 * n)

                positions = {}
                for sym in longs:
                    positions[sym] = 1.0 / n
                for sym in shorts:
                    positions[sym] = -1.0 / n
                days_since = 0
                daily_ret = -fee_cost - slip_cost
            else:
                daily_ret = 0.0

            for sym, w in positions.items():
                if sym in returns.columns:
                    r = returns[sym].iloc[i]
                    if np.isfinite(r):
                        daily_ret += w * r
            pnl_daily.append(daily_ret)

        if len(pnl_daily) < 30:
            continue
        pnl = np.array(pnl_daily)
        sharpe = float(np.mean(pnl) / np.std(pnl) * np.sqrt(365)) if np.std(pnl) > 0 else 0
        oos_sharpes.append(sharpe)

    return oos_sharpes


def compute_correlation_h012(closes, pnl_daily):
    returns = closes.pct_change()
    lookback, rebal, n = 60, 5, 4
    h012_pnl = []
    positions = {}
    days_since = rebal
    for i in range(70, len(closes)):
        days_since += 1
        if days_since >= rebal:
            mom = {}
            for sym in closes.columns:
                if i >= lookback:
                    r = closes[sym].iloc[i] / closes[sym].iloc[i - lookback] - 1
                    if np.isfinite(r):
                        mom[sym] = r
            if len(mom) < 2 * n:
                h012_pnl.append(0)
                continue
            ranked = pd.Series(mom).sort_values(ascending=False)
            longs = set(ranked.index[:n])
            shorts = set(ranked.index[-n:])
            old_syms = set(positions.keys())
            new_syms = longs | shorts
            changed = old_syms.symmetric_difference(new_syms)
            fee_cost = len(changed) * FEE_RATE / (2 * n)
            positions = {}
            for sym in longs:
                positions[sym] = 1.0 / n
            for sym in shorts:
                positions[sym] = -1.0 / n
            days_since = 0
            daily_ret = -fee_cost
        else:
            daily_ret = 0.0
        for sym, w in positions.items():
            if sym in returns.columns:
                r = returns[sym].iloc[i]
                if np.isfinite(r):
                    daily_ret += w * r
        h012_pnl.append(daily_ret)
    h012 = np.array(h012_pnl)
    min_len = min(len(h012), len(pnl_daily))
    if min_len < 50:
        return 0.0
    corr = np.corrcoef(h012[-min_len:], pnl_daily[-min_len:])[0, 1]
    return round(corr, 3) if np.isfinite(corr) else 0.0


# ============ Factor Definitions ============

def vw_directional_pressure(data, lookback, date_idx):
    """H-338: Volume-Weighted Directional Pressure averaged over lookback."""
    closes = data["closes"]
    feats = data["features"]
    dates = closes.index
    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        if "vwdp" not in feat.columns:
            continue
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "vwdp"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score
    return pd.Series(scores) if scores else None


def momentum_propagation(data, lookback, date_idx):
    """H-339: Intraday Momentum Propagation — corr(first_4h_bar, rest_of_day)."""
    closes = data["closes"]
    feats = data["features"]
    dates = closes.index
    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        if "first_bar_ret" not in feat.columns or "rest_day_ret" not in feat.columns:
            continue
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date)]
        if len(window) < lookback * 0.5:
            continue
        fb = window["first_bar_ret"].values
        rd = window["rest_day_ret"].values
        if len(fb) < 10:
            continue
        try:
            corr = np.corrcoef(fb, rd)[0, 1]
            if np.isfinite(corr):
                scores[sym] = corr
        except:
            continue
    return pd.Series(scores) if scores else None


def path_convexity(data, lookback, date_idx):
    """H-340: 4h Price Path Convexity — avg(second_half_ret - first_half_ret)."""
    closes = data["closes"]
    feats = data["features"]
    dates = closes.index
    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        if "convexity" not in feat.columns:
            continue
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "convexity"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score
    return pd.Series(scores) if scores else None


def return_concentration(data, lookback, date_idx):
    """H-341: Return Concentration — fraction of daily return from top-2 volume hours."""
    closes = data["closes"]
    feats = data["features"]
    dates = closes.index
    scores = {}
    for sym in closes.columns:
        if sym not in feats:
            continue
        feat = feats[sym]
        if "ret_conc" not in feat.columns:
            continue
        end_date = dates[date_idx]
        start_date = dates[max(0, date_idx - lookback)]
        window = feat.loc[(feat.index >= start_date) & (feat.index <= end_date), "ret_conc"]
        if len(window) < lookback * 0.5:
            continue
        score = window.mean()
        if np.isfinite(score):
            scores[sym] = score
    return pd.Series(scores) if scores else None


def full_validation(closes, factor_fn, results, factor_name, extra_data):
    """Run full validation."""
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "pnl_daily"} for r in results])
    if len(df) == 0:
        print(f"\n{'='*60}")
        print(f"  {factor_name}: NO VALID RESULTS")
        return

    pos_sharpe = (df["sharpe"] > 0).sum()
    total = len(df)
    is_pct = pos_sharpe / total * 100

    print(f"\n{'='*60}")
    print(f"  {factor_name}")
    print(f"{'='*60}")
    print(f"  Grid: {total} configs tested")
    print(f"  IS robustness: {pos_sharpe}/{total} = {is_pct:.1f}% positive Sharpe")
    print(f"  Best IS Sharpe: {df['sharpe'].max():.3f}")
    print(f"  Mean IS Sharpe: {df['sharpe'].mean():.3f}")
    print(f"  Best: LB={df.loc[df['sharpe'].idxmax(), 'lookback']}, "
          f"R={df.loc[df['sharpe'].idxmax(), 'rebal']}, "
          f"N={df.loc[df['sharpe'].idxmax(), 'n']}, "
          f"Dir={df.loc[df['sharpe'].idxmax(), 'direction']}")

    for d in df["direction"].unique():
        sub = df[df["direction"] == d]
        d_pos = (sub["sharpe"] > 0).sum()
        d_total = len(sub)
        d_pct = d_pos / d_total * 100 if d_total > 0 else 0
        print(f"    {d}: {d_pos}/{d_total} = {d_pct:.1f}% positive")

    if is_pct < 50:
        print(f"  VERDICT: REJECTED — IS robustness {is_pct:.1f}% < 50%")
        return

    best = df.loc[df["sharpe"].idxmax()]
    best_result = results[df["sharpe"].idxmax()]
    best_pnl = best_result["pnl_daily"]

    wf_sharpes = walk_forward(
        closes, factor_fn,
        int(best["lookback"]), int(best["rebal"]), int(best["n"]),
        best["direction"], extra_data
    )

    if wf_sharpes:
        wf_pos = sum(1 for s in wf_sharpes if s > 0)
        wf_total = len(wf_sharpes)
        wf_mean = np.mean(wf_sharpes)
        print(f"  Walk-forward OOS: {wf_pos}/{wf_total} positive, mean Sharpe {wf_mean:.3f}")
        print(f"    Fold Sharpes: {[round(s, 3) for s in wf_sharpes]}")
    else:
        print(f"  Walk-forward: FAILED")
        print(f"  VERDICT: REJECTED — WF failed")
        return

    # Neighboring params
    best_lb = int(best["lookback"])
    best_dir = best["direction"]
    neighbors = df[
        (df["direction"] == best_dir) &
        (abs(df["lookback"] - best_lb) <= 10)
    ]
    if len(neighbors) > 1:
        nb_pos = (neighbors["sharpe"] > 0).sum()
        nb_pct = nb_pos / len(neighbors) * 100
        print(f"  Neighboring params: {nb_pos}/{len(neighbors)} = {nb_pct:.1f}% positive")

    # Split-half
    half = len(best_pnl) // 2
    h1, h2 = best_pnl[:half], best_pnl[half:]
    s1 = float(np.mean(h1) / np.std(h1) * np.sqrt(365)) if np.std(h1) > 0 else 0
    s2 = float(np.mean(h2) / np.std(h2) * np.sqrt(365)) if np.std(h2) > 0 else 0
    split_pass = (s1 > 0 and s2 > 0)
    print(f"  Split-half: H1={s1:.3f}, H2={s2:.3f} — {'PASS' if split_pass else 'FAIL'}")

    corr_012 = compute_correlation_h012(closes, best_pnl)
    print(f"  Correlation with H-012: {corr_012}")

    wf_pass = wf_pos >= wf_total * 0.6 if wf_sharpes else False
    is_pass = is_pct >= 80
    corr_ok = abs(corr_012) < 0.5

    if is_pass and wf_pass and split_pass and corr_ok:
        print(f"  VERDICT: **CONFIRMED** — IS {is_pct:.1f}%, WF {wf_pos}/{wf_total}, "
              f"split OK, corr {corr_012}")
    elif is_pass and wf_pass and corr_ok:
        print(f"  VERDICT: BORDERLINE — IS {is_pct:.1f}%, WF {wf_pos}/{wf_total}, "
              f"split {'PASS' if split_pass else 'FAIL'}")
    elif is_pct >= 70 and wf_pass:
        print(f"  VERDICT: BORDERLINE — IS {is_pct:.1f}% (marginal)")
    else:
        reasons = []
        if not is_pass:
            reasons.append(f"IS {is_pct:.1f}%")
        if not wf_pass:
            reasons.append(f"WF {wf_pos}/{len(wf_sharpes) if wf_sharpes else 0}")
        if not split_pass:
            reasons.append(f"split fail")
        if not corr_ok:
            reasons.append(f"corr {corr_012}")
        print(f"  VERDICT: REJECTED — {', '.join(reasons)}")


def main():
    closes, opens, volumes, features = load_data()

    data = {
        "closes": closes,
        "opens": opens,
        "volumes": volumes,
        "returns": closes.pct_change(),
        "features": features,
    }

    lookbacks = [10, 20, 30, 60]
    rebals = [3, 5, 7]
    ns = [3, 4]

    print("\n" + "="*60)
    print("Testing H-338: Volume-Weighted Directional Pressure")
    print("="*60)
    r338 = backtest_factor(closes, vw_directional_pressure, lookbacks, rebals, ns,
                           ["high_long", "low_long"], "H-338 VW Directional Pressure", data)
    full_validation(closes, vw_directional_pressure, r338, "H-338 VW Directional Pressure", data)

    print("\n" + "="*60)
    print("Testing H-339: Intraday Momentum Propagation")
    print("="*60)
    r339 = backtest_factor(closes, momentum_propagation, [20, 30, 60, 90], rebals, ns,
                           ["high_long", "low_long"], "H-339 Momentum Propagation", data)
    full_validation(closes, momentum_propagation, r339, "H-339 Momentum Propagation", data)

    print("\n" + "="*60)
    print("Testing H-340: 4h Price Path Convexity")
    print("="*60)
    r340 = backtest_factor(closes, path_convexity, lookbacks, rebals, ns,
                           ["high_long", "low_long"], "H-340 Path Convexity", data)
    full_validation(closes, path_convexity, r340, "H-340 Path Convexity", data)

    print("\n" + "="*60)
    print("Testing H-341: Return Concentration")
    print("="*60)
    r341 = backtest_factor(closes, return_concentration, lookbacks, rebals, ns,
                           ["high_long", "low_long"], "H-341 Return Concentration", data)
    full_validation(closes, return_concentration, r341, "H-341 Return Concentration", data)

    print("\n\n" + "="*60)
    print("ALL 4 FACTORS COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
