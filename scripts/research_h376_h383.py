"""
Session 166 Research Batch 2: H-376 through H-383
8 more novel cross-sectional daily factor backtests.

Hypotheses:
  H-376: Dollar Volume Acceleration — 2nd derivative of dollar volume (change in volume growth)
  H-377: Return-Volume Concordance — rolling correlation between returns and volume changes
  H-378: Relative Close Position — (close - N_low) / (N_high - N_low), stochastic-like
  H-379: Candle Body Ratio — |close-open|/(high-low), conviction of daily candles
  H-380: Volume Profile Skewness — skewness of daily volumes, captures distribution asymmetry
  H-381: Momentum Decay Rate — how quickly momentum fades: mom(N) / mom(2N)
  H-382: Return Kurtosis — fat-tail tendency, rank by rolling kurtosis of returns
  H-383: Price-Volume Trend — cumulative sum of volume * sign(return), OBV-like but ranking-based
"""

import json
import sys
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

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
    frames_c, frames_v = {}, {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        frames_c[asset] = df["close"]
        frames_v[asset] = df["volume"]
    closes = pd.DataFrame(frames_c).sort_index().dropna(how="all").ffill().dropna(how="all")
    volumes = pd.DataFrame(frames_v).sort_index().reindex(closes.index).ffill().fillna(0)
    return closes, volumes


def load_ohlc():
    ohlc = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        ohlc[asset] = df
    return ohlc


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
                l, s = sr.iloc[-4:].index.tolist(), sr.iloc[:4].index.tolist()
                cw = pd.Series(0.0, index=l + s)
                for a in l: cw[a] = 0.25
                for a in s: cw[a] = -0.25
                dsr = 0
        curve.append(equity)
    return pd.Series(curve, index=closes.index).pct_change().fillna(0.0)


def run_hypothesis(name, hid, signal, closes, h012_rets, param_grid):
    print(f"\n{'='*70}")
    print(f"{hid}: {name}")
    print(f"{'='*70}")

    results = []
    best_signal = None
    best_sharpe = -999

    for params in param_grid:
        rebal = params["rebal"]
        n_pos = params["n_pos"]
        sig = signal[params["sig_key"]] if isinstance(signal, dict) else signal
        sig_shifted = sig.shift(1)

        eq = simulate(closes, sig_shifted, rebal, n_pos)
        if len(eq) < 100:
            continue
        rets = eq.pct_change().dropna()
        sr = sharpe_ratio(rets, periods_per_year=PPY)
        ar = annual_return(eq, PPY)
        dd = max_drawdown(eq)

        common = rets.index.intersection(h012_rets.index)
        corr_012 = rets.reindex(common).corr(h012_rets.reindex(common))

        label = "_".join(f"{k}{v}" for k, v in params.items() if k != "sig_key")
        results.append({
            "label": label, "sharpe": sr, "annual_return": ar,
            "max_dd": dd, "corr_h012": corr_012, **params
        })
        if sr > best_sharpe:
            best_sharpe = sr
            best_signal = (sig_shifted, rebal, n_pos)

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
    print(f"  Corr H-012: {best['corr_h012']:.3f}")

    if pct_pos < 20:
        print(f"  [Note: {100-pct_pos:.1f}% negative — signal direction may be inverted]")

    wf_results = []
    wf_pass = False
    split_pass = False
    if is_pass and best_signal:
        sig, reb, npos = best_signal
        wf_results = walk_forward(closes, sig, reb, npos)
        if wf_results:
            n_wf_pos = sum(1 for s in wf_results if s > 0)
            wf_mean = np.mean(wf_results)
            wf_pass = n_wf_pos >= 4 and wf_mean > 0.5
            print(f"  WF: {n_wf_pos}/{len(wf_results)} positive, mean {wf_mean:.3f} — {'PASS' if wf_pass else 'FAIL'}")
            for i, sr in enumerate(wf_results):
                print(f"    Fold {i}: {sr:.3f}")

        mid = len(sig) // 2
        eq_h1 = simulate(closes, sig, reb, npos, 0, mid)
        eq_h2 = simulate(closes, sig, reb, npos, mid, len(sig))
        sr_h1 = sharpe_ratio(eq_h1.pct_change().dropna(), periods_per_year=PPY)
        sr_h2 = sharpe_ratio(eq_h2.pct_change().dropna(), periods_per_year=PPY)
        split_pass = sr_h1 > 0 and sr_h2 > 0
        print(f"  Split-half: H1={sr_h1:.3f}, H2={sr_h2:.3f} — {'PASS' if split_pass else 'FAIL'}")

        same_rn = df[(df["rebal"] == best["rebal"]) & (df["n_pos"] == best["n_pos"])]
        nbr_pct = (same_rn["sharpe"] > 0).mean() * 100
        print(f"  Neighbors (same R/N): {(same_rn['sharpe'] > 0).sum()}/{len(same_rn)} positive ({nbr_pct:.0f}%)")

    corr_pass = abs(float(best["corr_h012"])) < 0.50
    confirmed = is_pass and wf_pass and split_pass and corr_pass
    print(f"\n  >>> {'CONFIRMED' if confirmed else 'REJECTED'} <<<")

    return {
        "hid": hid, "name": name,
        "total_params": len(df), "pct_positive_is": pct_pos,
        "best_sharpe": float(best["sharpe"]),
        "best_annual_return": float(best["annual_return"]),
        "best_max_dd": float(best["max_dd"]),
        "corr_h012": float(best["corr_h012"]),
        "mean_sharpe": float(df["sharpe"].mean()),
        "wf_positive": sum(1 for s in wf_results if s > 0) if wf_results else 0,
        "wf_total": len(wf_results),
        "wf_mean": float(np.mean(wf_results)) if wf_results else 0,
        "confirmed": confirmed,
    }


def main():
    print("=" * 70)
    print("SESSION 166 RESEARCH BATCH 2: H-376 through H-383")
    print("=" * 70)

    closes, volumes = load_data()
    ohlc = load_ohlc()
    print(f"Loaded {len(ASSETS)} assets, {len(closes)} daily bars")
    h012_rets = compute_h012_returns(closes)

    all_results = {}

    # === H-376: Dollar Volume Acceleration ===
    dv = closes * volumes  # dollar volume
    signals_376 = {}
    for lb in [10, 20, 30]:
        for acc_w in [3, 5, 10]:
            rolling_dv = dv.rolling(lb).mean()
            dv_growth = rolling_dv.pct_change(acc_w)
            dv_accel = dv_growth.diff(acc_w)  # 2nd derivative
            key = f"lb{lb}_aw{acc_w}"
            signals_376[key] = dv_accel

    grid_376 = [{"sig_key": f"lb{lb}_aw{aw}", "rebal": r, "n_pos": n}
                for lb in [10, 20, 30] for aw in [3, 5, 10] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-376"] = run_hypothesis(
        "Dollar Volume Acceleration", "H-376",
        signals_376, closes, h012_rets, grid_376)

    # === H-377: Return-Volume Concordance ===
    rets = closes.pct_change()
    vol_change = volumes.pct_change()
    signals_377 = {}
    for lb in [10, 20, 30, 40]:
        corr = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for asset in ASSETS:
            if asset in rets.columns and asset in vol_change.columns:
                corr[asset] = rets[asset].rolling(lb).corr(vol_change[asset])
        signals_377[f"lb{lb}"] = corr

    grid_377 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [10, 20, 30, 40] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-377"] = run_hypothesis(
        "Return-Volume Concordance", "H-377",
        signals_377, closes, h012_rets, grid_377)

    # === H-378: Relative Close Position (Stochastic-like) ===
    signals_378 = {}
    for lb in [10, 14, 20, 30]:
        rolling_high = closes.rolling(lb).max()
        rolling_low = closes.rolling(lb).min()
        rng = rolling_high - rolling_low
        rcp = (closes - rolling_low) / rng.replace(0, np.nan)
        signals_378[f"lb{lb}"] = rcp

    grid_378 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [10, 14, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-378"] = run_hypothesis(
        "Relative Close Position", "H-378",
        signals_378, closes, h012_rets, grid_378)

    # === H-379: Candle Body Ratio ===
    signals_379 = {}
    for lb in [5, 10, 20, 30]:
        body_ratio = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for asset in ASSETS:
            if asset not in ohlc:
                continue
            df = ohlc[asset].reindex(closes.index)
            body = (df["close"] - df["open"]).abs()
            rng = (df["high"] - df["low"]).replace(0, np.nan)
            ratio = body / rng
            body_ratio[asset] = ratio.rolling(lb).mean()
        signals_379[f"lb{lb}"] = body_ratio

    grid_379 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [5, 10, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-379"] = run_hypothesis(
        "Candle Body Ratio", "H-379",
        signals_379, closes, h012_rets, grid_379)

    # === H-380: Volume Profile Skewness ===
    signals_380 = {}
    for lb in [15, 20, 30, 40]:
        vol_skew = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for asset in ASSETS:
            if asset not in volumes.columns:
                continue
            v = volumes[asset]
            vol_skew[asset] = v.rolling(lb).apply(lambda x: stats.skew(x) if len(x) >= 5 else np.nan, raw=True)
        signals_380[f"lb{lb}"] = vol_skew

    grid_380 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [15, 20, 30, 40] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-380"] = run_hypothesis(
        "Volume Profile Skewness", "H-380",
        signals_380, closes, h012_rets, grid_380)

    # === H-381: Momentum Decay Rate ===
    signals_381 = {}
    for short_lb in [10, 20, 30]:
        long_lb = short_lb * 2
        short_mom = closes.pct_change(short_lb)
        long_mom = closes.pct_change(long_lb)
        # Ratio: how much of long-term momentum persists in short-term
        decay = short_mom / long_mom.replace(0, np.nan)
        decay = decay.replace([np.inf, -np.inf], np.nan)
        signals_381[f"s{short_lb}_l{long_lb}"] = decay

    grid_381 = [{"sig_key": f"s{slb}_l{slb*2}", "rebal": r, "n_pos": n}
                for slb in [10, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-381"] = run_hypothesis(
        "Momentum Decay Rate", "H-381",
        signals_381, closes, h012_rets, grid_381)

    # === H-382: Return Kurtosis (excess) ===
    signals_382 = {}
    for lb in [20, 30, 40, 60]:
        kurt = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for asset in ASSETS:
            if asset not in rets.columns:
                continue
            kurt[asset] = rets[asset].rolling(lb).apply(
                lambda x: stats.kurtosis(x, fisher=True) if len(x) >= 10 else np.nan, raw=True)
        # Negate: low kurtosis = thin tails = more predictable -> long
        signals_382[f"lb{lb}"] = -kurt

    grid_382 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [20, 30, 40, 60] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-382"] = run_hypothesis(
        "Return Kurtosis", "H-382",
        signals_382, closes, h012_rets, grid_382)

    # === H-383: Price-Volume Trend (OBV-like ranking) ===
    signals_383 = {}
    for lb in [10, 20, 30, 40]:
        pvt = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for asset in ASSETS:
            if asset not in rets.columns or asset not in volumes.columns:
                continue
            signed_vol = volumes[asset] * np.sign(rets[asset])
            cumulative = signed_vol.rolling(lb).sum()
            # Normalize by total volume to make cross-sectionally comparable
            total_vol = volumes[asset].rolling(lb).sum().replace(0, np.nan)
            pvt[asset] = cumulative / total_vol
        signals_383[f"lb{lb}"] = pvt

    grid_383 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [10, 20, 30, 40] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-383"] = run_hypothesis(
        "Price-Volume Trend", "H-383",
        signals_383, closes, h012_rets, grid_383)

    # ========= SUMMARY =========
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for hid, res in all_results.items():
        if res is None:
            print(f"  {hid}: NO RESULTS")
            continue
        status = "CONFIRMED" if res["confirmed"] else "REJECTED"
        print(f"  {hid} {res['name']}: {status}")
        print(f"    Best Sharpe={res['best_sharpe']:.3f}, Ann={res['best_annual_return']*100:.1f}%, "
              f"DD={res['best_max_dd']*100:.1f}%, Corr012={res['corr_h012']:.3f}")
        if res["wf_total"] > 0:
            print(f"    WF: {res['wf_positive']}/{res['wf_total']}, mean={res['wf_mean']:.3f}")


if __name__ == "__main__":
    main()
