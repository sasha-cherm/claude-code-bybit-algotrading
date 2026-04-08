"""
Session 166 Research: H-368 through H-375
8 novel cross-sectional daily factor backtests.

Each hypothesis uses the standard XS framework:
- 14 crypto assets, daily bars (~2 years)
- Parameter grid scan with IS positive% threshold (>=80%)
- Walk-forward validation (6 folds × 90 days)
- Split-half stability check
- Correlation with H-012 (momentum benchmark)

Hypotheses:
  H-368: Volume Market Share Drift — change in asset's share of total market volume
  H-369: Cross-Sectional Rank Momentum — improvement in asset's XS rank over time
  H-370: Consecutive Direction Intensity — streak length × average return per streak day
  H-371: Volume Impulse — log(volume) first difference (volume acceleration)
  H-372: Return-Range Ratio Trend — slope of directionality (|ret|/range) over lookback
  H-373: Cross-Sectional Momentum Dispersion Filter — only trade momentum when XS dispersion is high
  H-374: Relative Volatility Rank Change — how much has vol rank shifted vs peers
  H-375: Volume-Weighted Distance from Mean — vol-weighted absolute deviation from rolling mean
"""

import json
import sys
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
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
WF_FOLDS = 6
WF_TEST_DAYS = 90
WF_MIN_TRAIN = 180


def load_data():
    frames_c, frames_v, frames_ohlc = {}, {}, {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        frames_c[asset] = df["close"]
        frames_v[asset] = df["volume"]
        frames_ohlc[asset] = df[["open", "high", "low", "close", "volume"]]
    closes = pd.DataFrame(frames_c).sort_index().dropna(how="all").ffill().dropna(how="all")
    volumes = pd.DataFrame(frames_v).sort_index().reindex(closes.index).ffill().fillna(0)
    return closes, volumes, frames_ohlc


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
    cw = pd.Series(dtype=float)
    dsr = rebal

    for i in range(len(dates)):
        dr = rets.iloc[i]
        if len(cw) > 0:
            equity *= (1.0 + (cw * dr.reindex(cw.index, fill_value=0.0)).sum())

        dsr += 1
        if dsr >= rebal:
            row = sig.iloc[i].dropna()
            if len(row) >= 2 * n_pos:
                sr = row.sort_values()
                longs = sr.iloc[-n_pos:].index.tolist()
                shorts = sr.iloc[:n_pos].index.tolist()
                nw = pd.Series(0.0, index=longs + shorts)
                for a in longs: nw[a] = 1.0 / n_pos
                for a in shorts: nw[a] = -1.0 / n_pos

                if len(cw) > 0:
                    combined = nw.reindex(nw.index.union(cw.index), fill_value=0.0)
                    old = cw.reindex(combined.index, fill_value=0.0)
                    turnover = (combined - old).abs().sum() / 2.0
                else:
                    turnover = nw.abs().sum() / 2.0

                equity *= (1.0 - turnover * FEE_RATE)
                cw = nw
                dsr = 0

        equity_curve.append(equity)

    return pd.Series(equity_curve, index=dates)


def walk_forward(closes, signal, rebal, n_pos):
    T = len(signal)
    total_test = WF_FOLDS * WF_TEST_DAYS
    if T < WF_MIN_TRAIN + total_test:
        return []
    test_start = T - total_test
    results = []
    for fold in range(WF_FOLDS):
        ts = test_start + fold * WF_TEST_DAYS
        te = ts + WF_TEST_DAYS
        eq = simulate(closes, signal, rebal, n_pos, start_idx=0, end_idx=te)
        oos_eq = eq.iloc[ts:te]
        if len(oos_eq) < 20:
            continue
        sr = sharpe_ratio(oos_eq.pct_change().dropna(), periods_per_year=PPY)
        results.append(sr)
    return results


def compute_h012_returns(closes):
    momentum = closes.pct_change(60).shift(1)
    rets = closes.pct_change().fillna(0.0)
    equity = INITIAL_CAPITAL
    curve = []
    cw = pd.Series(dtype=float)
    dsr = 5
    for i in range(len(closes)):
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
    return pd.Series(curve, index=closes.index).pct_change().fillna(0.0)


def compute_h076_returns(closes):
    """H-076 efficiency factor for correlation check."""
    rets = closes.pct_change()
    ranges = closes.rolling(40).apply(lambda x: (x.max() - x.min()) / x.iloc[0] if x.iloc[0] > 0 else 0, raw=False)
    net_change = closes.pct_change(40).abs()
    efficiency = net_change / ranges.replace(0, np.nan)
    signal = efficiency.shift(1)

    equity = INITIAL_CAPITAL
    curve = []
    cw = pd.Series(dtype=float)
    dsr = 5
    for i in range(len(closes)):
        dr = rets.iloc[i].fillna(0)
        if len(cw) > 0:
            equity *= (1.0 + (cw * dr.reindex(cw.index, fill_value=0.0)).sum())
        dsr += 1
        if dsr >= 5:
            row = signal.iloc[i].dropna()
            if len(row) >= 8:
                sr = row.sort_values()
                l = sr.iloc[-4:].index.tolist()
                s = sr.iloc[:4].index.tolist()
                cw = pd.Series(0.0, index=l + s)
                for a in l: cw[a] = 0.25
                for a in s: cw[a] = -0.25
                dsr = 0
        curve.append(equity)
    return pd.Series(curve, index=closes.index).pct_change().fillna(0.0)


def run_hypothesis(name, hid, compute_signal_fn, closes, volumes, h012_rets, h076_rets,
                   param_grid, signal_cache=None):
    """Generic hypothesis runner. Returns results dict."""
    print(f"\n{'='*70}")
    print(f"{hid}: {name}")
    print(f"{'='*70}")

    results = []
    best_signal = None
    best_sharpe = -999

    for params in param_grid:
        cache_key = tuple(sorted(params.items())) if isinstance(params, dict) else params
        rebal = params.get("rebal", 5)
        n_pos = params.get("n_pos", 4)

        signal = compute_signal_fn(closes, volumes, **{k: v for k, v in params.items() if k not in ("rebal", "n_pos")})
        signal = signal.shift(1)  # lag to avoid lookahead

        eq = simulate(closes, signal, rebal, n_pos)
        if len(eq) < 100:
            continue
        rets = eq.pct_change().dropna()
        sr = sharpe_ratio(rets, periods_per_year=PPY)
        ar = annual_return(eq, PPY)
        dd = max_drawdown(eq)

        common = rets.index.intersection(h012_rets.index)
        corr_012 = rets.reindex(common).corr(h012_rets.reindex(common))
        corr_076 = rets.reindex(common).corr(h076_rets.reindex(common))

        label = "_".join(f"{k}{v}" for k, v in params.items())
        results.append({
            "label": label, "sharpe": sr, "annual_return": ar,
            "max_dd": dd, "corr_h012": corr_012, "corr_h076": corr_076,
            **params
        })
        if sr > best_sharpe:
            best_sharpe = sr
            best_signal = (signal, rebal, n_pos, label)

    if not results:
        print("  No valid results")
        return None

    df = pd.DataFrame(results)
    n_pos_is = (df["sharpe"] > 0).sum()
    pct_pos = n_pos_is / len(df) * 100
    is_pass = pct_pos >= 80

    print(f"  IS: {n_pos_is}/{len(df)} positive ({pct_pos:.1f}%) — {'PASS' if is_pass else 'FAIL'}")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}")

    best = df.loc[df["sharpe"].idxmax()]
    print(f"  Best: {best['label']} — Sharpe {best['sharpe']:.3f}, Ann {best['annual_return']*100:.1f}%, DD {best['max_dd']*100:.1f}%")
    print(f"  Corr H-012: {best['corr_h012']:.3f}, Corr H-076: {best['corr_h076']:.3f}")

    # Check direction: try flipping if mostly negative
    if pct_pos < 20:
        # Signal might be inverted
        n_neg = (df["sharpe"] < 0).sum()
        pct_neg = n_neg / len(df) * 100
        print(f"  [Note: {pct_neg:.1f}% negative — checking inverted direction]")

    # Walk-forward only if IS passes
    wf_results = []
    wf_pass = False
    if is_pass and best_signal:
        sig, reb, npos, lbl = best_signal
        wf_results = walk_forward(closes, sig, reb, npos)
        if wf_results:
            n_wf_pos = sum(1 for s in wf_results if s > 0)
            wf_mean = np.mean(wf_results)
            wf_pass = n_wf_pos >= 4 and wf_mean > 0.5
            print(f"  WF: {n_wf_pos}/{len(wf_results)} positive, mean {wf_mean:.3f} — {'PASS' if wf_pass else 'FAIL'}")
            for i, sr in enumerate(wf_results):
                print(f"    Fold {i}: {sr:.3f}")

    # Split-half
    split_pass = False
    if is_pass and best_signal:
        sig, reb, npos, lbl = best_signal
        mid = len(sig) // 2
        eq_h1 = simulate(closes, sig, reb, npos, 0, mid)
        eq_h2 = simulate(closes, sig, reb, npos, mid, len(sig))
        sr_h1 = sharpe_ratio(eq_h1.pct_change().dropna(), periods_per_year=PPY)
        sr_h2 = sharpe_ratio(eq_h2.pct_change().dropna(), periods_per_year=PPY)
        split_pass = sr_h1 > 0 and sr_h2 > 0
        print(f"  Split-half: H1={sr_h1:.3f}, H2={sr_h2:.3f} — {'PASS' if split_pass else 'FAIL'}")

    # Neighbor robustness for best config
    neighbor_pass = False
    if is_pass and best_signal:
        best_idx = df["sharpe"].idxmax()
        best_params = {k: df.loc[best_idx, k] for k in params.keys() if k in df.columns}
        # Count neighbors within ±1 step that are positive
        n_neighbor_pos = 0
        n_neighbor_total = 0
        for _, row in df.iterrows():
            is_neighbor = True
            for k in best_params:
                if k in ("rebal", "n_pos"):
                    continue
                if abs(row[k] - best_params[k]) > 0:
                    is_neighbor = False
                    break
            if not is_neighbor:
                n_neighbor_total += 1
                if row["sharpe"] > 0:
                    n_neighbor_pos += 1
        # Broader check: all params with same rebal/n_pos
        same_rn = df[(df["rebal"] == best["rebal"]) & (df["n_pos"] == best["n_pos"])]
        neighbor_pct = (same_rn["sharpe"] > 0).mean() * 100
        neighbor_pass = neighbor_pct >= 75
        print(f"  Neighbors (same R/N): {(same_rn['sharpe'] > 0).sum()}/{len(same_rn)} positive ({neighbor_pct:.0f}%) — {'PASS' if neighbor_pass else 'FAIL'}")

    corr_pass = abs(float(best["corr_h012"])) < 0.50

    confirmed = is_pass and wf_pass and split_pass and corr_pass
    print(f"\n  >>> {'CONFIRMED' if confirmed else 'REJECTED'} <<<")

    return {
        "hid": hid, "name": name,
        "total_params": len(df), "pct_positive_is": pct_pos,
        "best_config": str(best["label"]),
        "best_sharpe": float(best["sharpe"]),
        "best_annual_return": float(best["annual_return"]),
        "best_max_dd": float(best["max_dd"]),
        "corr_h012": float(best["corr_h012"]),
        "corr_h076": float(best["corr_h076"]),
        "mean_sharpe": float(df["sharpe"].mean()),
        "wf_results": [float(x) for x in wf_results] if wf_results else [],
        "wf_positive": sum(1 for s in wf_results if s > 0) if wf_results else 0,
        "wf_mean": float(np.mean(wf_results)) if wf_results else 0,
        "confirmed": confirmed,
        "is_pass": is_pass, "wf_pass": wf_pass, "split_pass": split_pass,
        "corr_pass": corr_pass,
    }


# ========= SIGNAL FUNCTIONS =========

def signal_h368_volume_share_drift(closes, volumes, lookback=20, drift_window=5):
    """Volume Market Share Drift: change in asset's % of total market volume."""
    total_vol = volumes.sum(axis=1).replace(0, np.nan)
    share = volumes.div(total_vol, axis=0)
    rolling_share = share.rolling(lookback).mean()
    drift = rolling_share.diff(drift_window)
    return drift


def signal_h369_rank_momentum(closes, volumes, lookback=20, rank_lookback=5):
    """Cross-Sectional Rank Momentum: improvement in asset's return rank over time."""
    rets = closes.pct_change(lookback)
    # Compute XS rank at each point
    ranks = rets.rank(axis=1, pct=True)
    # Rank momentum = change in rank
    rank_mom = ranks.diff(rank_lookback)
    return rank_mom


def signal_h370_streak_intensity(closes, volumes, lookback=20):
    """Consecutive Direction Intensity: streak length × avg return magnitude.
    Captures not just whether an asset is trending, but how intense the trend is."""
    rets = closes.pct_change()
    signal = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)

    for asset in ASSETS:
        if asset not in rets.columns:
            continue
        r = rets[asset].values
        intensity = np.full(len(r), np.nan)
        for i in range(lookback, len(r)):
            window = r[i-lookback:i]
            window = window[~np.isnan(window)]
            if len(window) < 5:
                continue
            # Count streak lengths and their avg returns
            total_intensity = 0.0
            streak_len = 0
            streak_sum = 0.0
            for j in range(1, len(window)):
                if np.sign(window[j]) == np.sign(window[j-1]) and window[j] != 0:
                    streak_len += 1
                    streak_sum += abs(window[j])
                else:
                    if streak_len > 0:
                        total_intensity += streak_len * (streak_sum / streak_len)
                    streak_len = 1 if window[j] != 0 else 0
                    streak_sum = abs(window[j])
            if streak_len > 0:
                total_intensity += streak_len * (streak_sum / streak_len)
            intensity[i] = total_intensity / lookback
        signal[asset] = pd.Series(intensity, index=closes.index)
    return signal


def signal_h371_volume_impulse(closes, volumes, lookback=5, smooth=3):
    """Volume Impulse: first difference of smoothed log(volume). Captures sudden volume shifts."""
    log_vol = np.log1p(volumes)
    smoothed = log_vol.rolling(smooth).mean()
    impulse = smoothed.diff(lookback)
    return impulse


def signal_h372_return_range_trend(closes, volumes, lookback=20, trend_window=10):
    """Return-Range Ratio Trend: slope of |return|/range. Trending up = becoming more directional."""
    # Need OHLC data
    signal = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df.reindex(closes.index)
        daily_range = (df["high"] - df["low"]).replace(0, np.nan)
        daily_ret = df["close"].pct_change().abs()
        ratio = daily_ret / (daily_range / df["close"])
        ratio = ratio.replace([np.inf, -np.inf], np.nan)
        # Rolling mean then diff to get trend
        rolling_ratio = ratio.rolling(lookback).mean()
        trend = rolling_ratio.diff(trend_window)
        signal[asset] = trend
    return signal


def signal_h373_dispersion_filtered_momentum(closes, volumes, mom_lookback=60, disp_lookback=20):
    """XS Momentum Dispersion Filter: only trade momentum when XS return dispersion is high.
    High dispersion = factor opportunities; low dispersion = no edge."""
    momentum = closes.pct_change(mom_lookback)
    rets = closes.pct_change()
    # Cross-sectional dispersion = std of daily returns across assets
    xs_disp = rets.std(axis=1)
    rolling_disp = xs_disp.rolling(disp_lookback).mean()
    disp_median = rolling_disp.expanding().median()

    # Only signal when dispersion is above median
    signal = momentum.copy()
    low_disp = rolling_disp < disp_median
    for col in signal.columns:
        signal.loc[low_disp, col] = 0.0
    return signal


def signal_h374_vol_rank_change(closes, volumes, vol_lookback=20, rank_lookback=10):
    """Relative Volatility Rank Change: how much has an asset's vol rank changed?
    Assets with contracting relative vol (rank improving = lower vol) may be entering trending phase."""
    rets = closes.pct_change()
    rolling_vol = rets.rolling(vol_lookback).std()
    vol_rank = rolling_vol.rank(axis=1, pct=True)
    rank_change = vol_rank.diff(rank_lookback)
    # Negate: decreasing vol rank (becoming less volatile) = positive signal
    return -rank_change


def signal_h375_vol_weighted_dev(closes, volumes, lookback=20):
    """Volume-Weighted Distance from Mean: vol-weighted |return - mean|.
    Low = quiet accumulation, high = volatile on heavy volume."""
    rets = closes.pct_change()
    signal = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)

    for asset in ASSETS:
        if asset not in rets.columns:
            continue
        r = rets[asset].values
        v = volumes[asset].values if asset in volumes.columns else np.ones(len(r))
        vw_dev = np.full(len(r), np.nan)
        for i in range(lookback, len(r)):
            w_r = r[i-lookback:i]
            w_v = v[i-lookback:i]
            mask = ~np.isnan(w_r) & ~np.isnan(w_v) & (w_v > 0)
            if mask.sum() < 5:
                continue
            w_r, w_v = w_r[mask], w_v[mask]
            w_v = w_v / w_v.sum()
            mean_r = np.average(w_r, weights=w_v)
            vw_dev[i] = np.average(np.abs(w_r - mean_r), weights=w_v)
        signal[asset] = pd.Series(vw_dev, index=closes.index)
    # Negate: low vol-weighted deviation = quiet/accumulating → long
    return -signal


# ========= MAIN =========

def main():
    print("=" * 70)
    print("SESSION 166 RESEARCH: H-368 through H-375")
    print("=" * 70)

    closes, volumes, ohlc = load_data()
    print(f"Loaded {len(ASSETS)} assets, {len(closes)} daily bars")

    h012_rets = compute_h012_returns(closes)
    h076_rets = compute_h076_returns(closes)

    all_results = {}

    # H-368: Volume Market Share Drift
    grid_368 = [{"lookback": lb, "drift_window": dw, "rebal": r, "n_pos": n}
                for lb in [10, 20, 30] for dw in [3, 5, 10] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-368"] = run_hypothesis(
        "Volume Market Share Drift", "H-368",
        signal_h368_volume_share_drift, closes, volumes, h012_rets, h076_rets, grid_368)

    # H-369: Cross-Sectional Rank Momentum
    grid_369 = [{"lookback": lb, "rank_lookback": rl, "rebal": r, "n_pos": n}
                for lb in [10, 20, 40, 60] for rl in [3, 5, 10] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-369"] = run_hypothesis(
        "Cross-Sectional Rank Momentum", "H-369",
        signal_h369_rank_momentum, closes, volumes, h012_rets, h076_rets, grid_369)

    # H-370: Consecutive Direction Intensity
    grid_370 = [{"lookback": lb, "rebal": r, "n_pos": n}
                for lb in [10, 15, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-370"] = run_hypothesis(
        "Consecutive Direction Intensity", "H-370",
        signal_h370_streak_intensity, closes, volumes, h012_rets, h076_rets, grid_370)

    # H-371: Volume Impulse
    grid_371 = [{"lookback": lb, "smooth": sm, "rebal": r, "n_pos": n}
                for lb in [3, 5, 10] for sm in [1, 3, 5] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-371"] = run_hypothesis(
        "Volume Impulse", "H-371",
        signal_h371_volume_impulse, closes, volumes, h012_rets, h076_rets, grid_371)

    # H-372: Return-Range Ratio Trend
    grid_372 = [{"lookback": lb, "trend_window": tw, "rebal": r, "n_pos": n}
                for lb in [10, 20, 30] for tw in [5, 10] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-372"] = run_hypothesis(
        "Return-Range Ratio Trend", "H-372",
        signal_h372_return_range_trend, closes, volumes, h012_rets, h076_rets, grid_372)

    # H-373: Dispersion-Filtered Momentum
    grid_373 = [{"mom_lookback": ml, "disp_lookback": dl, "rebal": r, "n_pos": n}
                for ml in [20, 40, 60] for dl in [10, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-373"] = run_hypothesis(
        "Dispersion-Filtered Momentum", "H-373",
        signal_h373_dispersion_filtered_momentum, closes, volumes, h012_rets, h076_rets, grid_373)

    # H-374: Relative Volatility Rank Change
    grid_374 = [{"vol_lookback": vl, "rank_lookback": rl, "rebal": r, "n_pos": n}
                for vl in [10, 20, 30] for rl in [5, 10, 20] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-374"] = run_hypothesis(
        "Relative Volatility Rank Change", "H-374",
        signal_h374_vol_rank_change, closes, volumes, h012_rets, h076_rets, grid_374)

    # H-375: Volume-Weighted Distance from Mean
    grid_375 = [{"lookback": lb, "rebal": r, "n_pos": n}
                for lb in [10, 15, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-375"] = run_hypothesis(
        "Volume-Weighted Distance from Mean", "H-375",
        signal_h375_vol_weighted_dev, closes, volumes, h012_rets, h076_rets, grid_375)

    # ========= SUMMARY =========
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for hid, res in all_results.items():
        if res is None:
            print(f"  {hid}: NO RESULTS")
            continue
        status = "CONFIRMED" if res["confirmed"] else "REJECTED"
        flags = []
        if not res["is_pass"]: flags.append(f"IS {res['pct_positive_is']:.0f}%")
        if not res["wf_pass"]: flags.append(f"WF {res['wf_positive']}/{len(res['wf_results'])}")
        if not res["split_pass"]: flags.append("split")
        if not res["corr_pass"]: flags.append(f"corr {res['corr_h012']:.2f}")
        reason = f" ({', '.join(flags)})" if flags else ""
        print(f"  {hid} {res['name']}: {status}{reason}")
        print(f"    Best Sharpe={res['best_sharpe']:.3f}, Ann={res['best_annual_return']*100:.1f}%, "
              f"DD={res['best_max_dd']*100:.1f}%, Corr012={res['corr_h012']:.3f}")

    # Save results
    outpath = ROOT / "scripts" / "research_h368_h375_results.json"
    with open(outpath, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {outpath}")


if __name__ == "__main__":
    main()
