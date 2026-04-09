#!/usr/bin/env python3
"""
Backtest eight novel cross-sectional factors from 4h microstructure data.
Trade at daily frequency; use standard framework.

  H-400: Volume Profile Asymmetry — ratio of volume in up-4h-bars to total volume.
         High ratio = buying dominance. Long buying-dominated, short selling-dominated.
  H-401: Range Expansion — current 4h avg range / rolling avg range.
         Expanding ranges signal emerging trends; contracting = mean-reversion.
  H-402: Body-to-Range Ratio — rolling mean of |close-open|/(high-low) at 4h.
         High = strong directional conviction. Low = indecision/wicks.
  H-403: Return Acceleration (4h) — change in 4h-aggregate momentum (2nd derivative).
         Accelerating assets continue; decelerating revert.
  H-404: Session Flow Imbalance — (Asian return - US return) rolling avg.
         Geographic flow divergence predicts next-day continuation/reversal.
  H-405: Consecutive Direction Streak — rolling avg of current direction streak length.
         Longer streaks in one direction = stronger trend signal.
  H-406: Volume-Price Trend Coherence (4h) — rolling corr(4h return, 4h volume change).
         High coherence = healthy informed flow. Low = noise.
  H-407: Intrabar Momentum Quality — rolling Sharpe of individual 4h bar returns.
         High intrabar Sharpe = clean, consistent microstructure momentum.

Standard framework: grid search, IS robustness (>=80%), walk-forward OOS, split-half, H-012 corr.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001
SLIPPAGE_BPS = 2.0


def load_data():
    """Load 4h data from parquet, compute daily features, align."""
    print("Loading 4h data for 14 assets...")

    closes_dict, opens_dict, volumes_dict = {}, {}, {}
    features_4h = {}

    for sym in ASSETS:
        ticker = sym.replace("/", "_")
        fpath = ROOT / "data" / f"{ticker}_4h.parquet"
        if not fpath.exists():
            print(f"  {sym}: no 4h data")
            continue
        df_4h = pd.read_parquet(fpath)
        if len(df_4h) < 500:
            print(f"  {sym}: only {len(df_4h)} bars, skipping")
            continue

        # Resample to daily for close/open/volume
        daily = df_4h.resample("1D").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum"
        }).dropna()
        closes_dict[sym] = daily["close"]
        opens_dict[sym] = daily["open"]
        volumes_dict[sym] = daily["volume"]

        # 4h bar features
        df_4h["bar_return"] = df_4h["close"] / df_4h["open"] - 1
        df_4h["bar_range"] = df_4h["high"] - df_4h["low"]
        df_4h["body"] = (df_4h["close"] - df_4h["open"]).abs()
        df_4h["bar_direction"] = np.sign(df_4h["bar_return"])
        df_4h["vol_change"] = df_4h["volume"].pct_change()
        df_4h["date"] = df_4h.index.date

        daily_feats = []
        for date, group in df_4h.groupby("date"):
            if len(group) < 4:
                continue

            # H-400: Volume Profile Asymmetry
            up_vol = group.loc[group["bar_return"] > 0, "volume"].sum()
            total_vol = group["volume"].sum()
            vol_asymmetry = up_vol / total_vol if total_vol > 0 else 0.5

            # H-401: Range Expansion — avg 4h range (normalized by close)
            avg_bar_range = (group["bar_range"] / group["close"]).mean()

            # H-402: Body-to-Range Ratio
            body_range = np.where(
                group["bar_range"] > 0,
                group["body"] / group["bar_range"],
                0
            ).mean()

            # H-403: 4h aggregate momentum (sum of bar returns — used for acceleration)
            agg_mom = group["bar_return"].sum()

            # H-404: Session Flow Imbalance
            asia = group[group.index.hour < 8]
            us = group[group.index.hour >= 16]
            asia_ret = (asia["close"].iloc[-1] / asia["open"].iloc[0] - 1) if len(asia) > 0 else 0
            us_ret = (us["close"].iloc[-1] / us["open"].iloc[0] - 1) if len(us) > 0 else 0
            session_imbalance = asia_ret - us_ret

            # H-405: Consecutive Direction Streak
            dirs = group["bar_direction"].values
            streak = 1
            max_streak = 1
            for j in range(1, len(dirs)):
                if dirs[j] == dirs[j-1] and dirs[j] != 0:
                    streak += 1
                    max_streak = max(max_streak, streak)
                else:
                    streak = 1
            # Sign by dominant direction
            n_pos = (dirs > 0).sum()
            signed_streak = max_streak if n_pos > len(dirs)/2 else -max_streak

            # H-406: Volume-Price Trend Coherence
            if len(group) >= 3 and group["vol_change"].std() > 0 and group["bar_return"].std() > 0:
                vp_corr = group["bar_return"].corr(group["vol_change"])
                if not np.isfinite(vp_corr):
                    vp_corr = 0.0
            else:
                vp_corr = 0.0

            # H-407: Intrabar Momentum Quality
            bar_rets = group["bar_return"].values
            if len(bar_rets) >= 3 and np.std(bar_rets) > 0:
                intrabar_sharpe = np.mean(bar_rets) / np.std(bar_rets)
            else:
                intrabar_sharpe = 0.0

            daily_feats.append({
                "date": pd.Timestamp(date),
                "vol_asymmetry": vol_asymmetry,
                "avg_range": avg_bar_range,
                "body_range": body_range,
                "agg_mom": agg_mom,
                "session_imbalance": session_imbalance,
                "signed_streak": signed_streak,
                "vp_corr": vp_corr,
                "intrabar_sharpe": intrabar_sharpe,
            })

        if daily_feats:
            feat_df = pd.DataFrame(daily_feats).set_index("date")
            feat_df.index = pd.to_datetime(feat_df.index, utc=True)
            features_4h[sym] = feat_df

    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    opens = pd.DataFrame(opens_dict).reindex(closes.index).ffill().dropna()
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill().dropna()
    idx = closes.index.intersection(opens.index).intersection(volumes.index)
    closes, opens, volumes = closes.loc[idx], opens.loc[idx], volumes.loc[idx]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"4h features computed for {len(features_4h)} assets")

    return closes, opens, volumes, features_4h


def make_factor_fn(features_4h, closes, feature_name, agg="mean"):
    """Generic factor function: rolling agg of a 4h-derived daily feature."""
    def factor_fn(extra_data, lookback, i):
        date_i = closes.index[i]
        scores = {}
        for sym in closes.columns:
            if sym not in features_4h:
                continue
            feat = features_4h[sym]
            mask = feat.index < date_i  # Strictly before today — no look-ahead
            window = feat[mask].tail(lookback)
            if len(window) < lookback * 0.7:
                continue
            vals = window[feature_name].values
            if agg == "mean":
                scores[sym] = np.nanmean(vals)
            elif agg == "last":
                scores[sym] = vals[-1] if len(vals) > 0 else np.nan
            elif agg == "accel":
                # H-403: acceleration = recent half - older half
                half = len(vals) // 2
                if half > 0:
                    scores[sym] = np.nanmean(vals[half:]) - np.nanmean(vals[:half])
                else:
                    scores[sym] = 0.0
        if len(scores) < 6:
            return None
        return pd.Series(scores)
    return factor_fn


def backtest_factor(closes, factor_fn, lookbacks, rebals, ns, directions, factor_name):
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
                            scores = factor_fn(None, lookback, i)
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


def walk_forward(closes, factor_fn, lookback, rebal, n, direction, n_folds=6):
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
                scores = factor_fn(None, lookback, i)
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
            old = set(positions.keys())
            new = longs | shorts
            changed = old.symmetric_difference(new)
            fee_cost = len(changed) * FEE_RATE / (2 * n)
            positions = {s: (1.0/n if s in longs else -1.0/n) for s in longs | shorts}
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

    min_len = min(len(h012_pnl), len(pnl_daily))
    if min_len < 30:
        return 0.0
    return float(np.corrcoef(h012_pnl[-min_len:], pnl_daily[-min_len:])[0, 1])


def evaluate_hypothesis(closes, features_4h, hyp_name, feature_name, directions, agg="mean"):
    """Full evaluation pipeline for one hypothesis."""
    print(f"\n{'='*60}")
    print(f"  {hyp_name}: {feature_name} (agg={agg})")
    print(f"{'='*60}")

    factor_fn = make_factor_fn(features_4h, closes, feature_name, agg=agg)

    lookbacks = [5, 10, 15, 20, 30]
    rebals = [3, 5, 7]
    ns = [3, 4]

    results = backtest_factor(closes, factor_fn, lookbacks, rebals, ns, directions, hyp_name)

    if not results:
        print("  No valid results!")
        return None

    # IS Analysis
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "pnl_daily"} for r in results])
    n_positive = (df["sharpe"] > 0).sum()
    n_total = len(df)
    pct_pos = n_positive / n_total * 100

    # Check by direction
    for d in directions:
        sub = df[df["direction"] == d]
        d_pos = (sub["sharpe"] > 0).sum()
        d_total = len(sub)
        d_pct = d_pos / d_total * 100 if d_total > 0 else 0
        print(f"  IS {d}: {d_pos}/{d_total} positive ({d_pct:.1f}%)")

    best = df.loc[df["sharpe"].idxmax()]
    print(f"  Best: LB{best['lookback']}_R{best['rebal']}_N{best['n']}_{best['direction']}")
    print(f"    Sharpe {best['sharpe']:.3f}, Ann {best['ann_ret']:.1f}%, DD {best['max_dd']:.1f}%")
    mean_sharpe = df["sharpe"].mean()
    print(f"  Mean Sharpe: {mean_sharpe:.3f}")

    # Check dominant direction
    best_dir = None
    best_pct = 0
    for d in directions:
        sub = df[df["direction"] == d]
        d_pct = (sub["sharpe"] > 0).sum() / len(sub) * 100 if len(sub) > 0 else 0
        if d_pct > best_pct:
            best_pct = d_pct
            best_dir = d

    if best_pct < 80:
        print(f"  REJECTED at IS — best direction {best_dir} only {best_pct:.1f}% positive")
        return {"status": "REJECTED", "reason": "IS", "best_pct": best_pct, "best_dir": best_dir,
                "best_sharpe": float(best["sharpe"]), "mean_sharpe": mean_sharpe}

    print(f"  IS PASSED — {best_dir} {best_pct:.1f}% positive")

    # Walk-forward on best config
    best_result = results[df["sharpe"].idxmax()]
    wf_sharpes = walk_forward(
        closes, factor_fn, int(best["lookback"]), int(best["rebal"]),
        int(best["n"]), best["direction"]
    )

    n_pos_wf = sum(1 for s in wf_sharpes if s > 0)
    mean_wf = np.mean(wf_sharpes) if wf_sharpes else 0
    print(f"  WF: {n_pos_wf}/{len(wf_sharpes)} positive, mean Sharpe {mean_wf:.3f}")
    print(f"    Fold Sharpes: {[round(s, 3) for s in wf_sharpes]}")

    if n_pos_wf < 4 or mean_wf < 0:
        print(f"  REJECTED at WF — {n_pos_wf}/{len(wf_sharpes)} positive, mean {mean_wf:.3f}")
        return {"status": "REJECTED", "reason": "WF", "best_pct": best_pct, "best_dir": best_dir,
                "best_sharpe": float(best["sharpe"]), "wf_pos": n_pos_wf, "wf_total": len(wf_sharpes),
                "wf_mean": mean_wf, "mean_sharpe": mean_sharpe}

    # Split-half validation
    pnl = best_result["pnl_daily"]
    half = len(pnl) // 2
    h1_sharpe = float(np.mean(pnl[:half]) / np.std(pnl[:half]) * np.sqrt(365)) if np.std(pnl[:half]) > 0 else 0
    h2_sharpe = float(np.mean(pnl[half:]) / np.std(pnl[half:]) * np.sqrt(365)) if np.std(pnl[half:]) > 0 else 0
    split_pass = h1_sharpe > 0 and h2_sharpe > 0
    print(f"  Split-half: H1={h1_sharpe:.3f}, H2={h2_sharpe:.3f} {'PASS' if split_pass else 'FAIL'}")

    # Neighboring params robustness
    best_lb = int(best["lookback"])
    best_r = int(best["rebal"])
    best_n = int(best["n"])
    neighbors = df[
        (df["direction"] == best["direction"]) &
        (abs(df["lookback"] - best_lb) <= 10) &
        (abs(df["rebal"] - best_r) <= 2) &
        (abs(df["n"] - best_n) <= 1)
    ]
    n_pos_nb = (neighbors["sharpe"] > 0).sum()
    nb_total = len(neighbors)
    nb_pct = n_pos_nb / nb_total * 100 if nb_total > 0 else 0
    print(f"  Neighbors: {n_pos_nb}/{nb_total} positive ({nb_pct:.1f}%)")

    # H-012 correlation
    corr_h012 = compute_correlation_h012(closes, pnl)
    print(f"  H-012 correlation: {corr_h012:.3f}")

    if not split_pass:
        print(f"  REJECTED at split-half")
        return {"status": "REJECTED", "reason": "split-half", "best_pct": best_pct, "best_dir": best_dir,
                "best_sharpe": float(best["sharpe"]), "wf_pos": n_pos_wf, "wf_total": len(wf_sharpes),
                "wf_mean": mean_wf, "h1": h1_sharpe, "h2": h2_sharpe, "corr_h012": corr_h012,
                "mean_sharpe": mean_sharpe}

    print(f"  *** CONFIRMED ***")
    return {
        "status": "CONFIRMED",
        "best_dir": best_dir, "best_pct": best_pct,
        "best_sharpe": float(best["sharpe"]),
        "best_config": f"LB{best_lb}_R{best_r}_N{best_n}_{best['direction']}",
        "ann_ret": float(best["ann_ret"]),
        "max_dd": float(best["max_dd"]),
        "wf_pos": n_pos_wf, "wf_total": len(wf_sharpes),
        "wf_mean": mean_wf,
        "h1": h1_sharpe, "h2": h2_sharpe,
        "nb_pct": nb_pct,
        "corr_h012": corr_h012,
        "mean_sharpe": mean_sharpe,
        "n_days": int(best["n_days"]),
        "lookback": best_lb, "rebal": best_r, "n": best_n,
        "direction": str(best["direction"]),
    }


def main():
    closes, opens, volumes, features_4h = load_data()

    hypotheses = [
        ("H-400", "vol_asymmetry", ["high_vol_asymmetry_long", "low_vol_asymmetry_long"], "mean"),
        ("H-401", "avg_range", ["high_avg_range_long", "low_avg_range_long"], "mean"),
        ("H-402", "body_range", ["high_body_range_long", "low_body_range_long"], "mean"),
        ("H-403", "agg_mom", ["high_agg_mom_long", "low_agg_mom_long"], "accel"),
        ("H-404", "session_imbalance", ["high_session_imbalance_long", "low_session_imbalance_long"], "mean"),
        ("H-405", "signed_streak", ["high_signed_streak_long", "low_signed_streak_long"], "mean"),
        ("H-406", "vp_corr", ["high_vp_corr_long", "low_vp_corr_long"], "mean"),
        ("H-407", "intrabar_sharpe", ["high_intrabar_sharpe_long", "low_intrabar_sharpe_long"], "mean"),
    ]

    all_results = {}
    for hyp_name, feature_name, directions, agg in hypotheses:
        result = evaluate_hypothesis(closes, features_4h, hyp_name, feature_name, directions, agg)
        all_results[hyp_name] = result

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for hyp_name, result in all_results.items():
        if result is None:
            print(f"  {hyp_name}: NO RESULTS")
        elif result["status"] == "CONFIRMED":
            print(f"  {hyp_name}: CONFIRMED — Sharpe {result['best_sharpe']:.3f}, "
                  f"WF {result['wf_pos']}/{result['wf_total']}, corr H-012 {result['corr_h012']:.3f}")
        else:
            reason = result.get("reason", "unknown")
            print(f"  {hyp_name}: REJECTED ({reason}) — best dir {result.get('best_dir', '?')} "
                  f"{result.get('best_pct', 0):.1f}%, Sharpe {result.get('best_sharpe', 0):.3f}")


if __name__ == "__main__":
    main()
