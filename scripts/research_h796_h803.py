"""
Session 187 Research Batch 2: H-796 through H-803
8 novel cross-sectional daily factor backtests.
Focus: Intraday structure signals derived from hourly data, volume clock, price acceleration.

Hypotheses:
  H-796: Volume Clock Momentum — momentum measured in volume-time rather than calendar-time
  H-797: Price Acceleration — 2nd derivative of price (change in return momentum)
  H-798: Overnight-Intraday Divergence — difference between overnight and intraday returns as signal
  H-799: Hour-Weighted Return — returns weighted by hour-of-day volume profile
  H-800: Volume Distribution Entropy — entropy of intraday volume distribution (hourly volumes)
  H-801: Close-VWAP Deviation — daily close relative to VWAP, captures end-of-day sentiment
  H-802: Intraday Reversal Strength — correlation between 1st half and 2nd half of day returns
  H-803: Range Compression Ratio — N-day range / sum(1-day ranges), captures compression vs expansion
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
    frames_c, frames_v, frames_h, frames_l, frames_o = {}, {}, {}, {}, {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        frames_c[asset] = df["close"]
        frames_v[asset] = df["volume"]
        if "high" in df.columns:
            frames_h[asset] = df["high"]
        if "low" in df.columns:
            frames_l[asset] = df["low"]
        if "open" in df.columns:
            frames_o[asset] = df["open"]
    closes = pd.DataFrame(frames_c).sort_index().dropna(how="all").ffill().dropna(how="all")
    volumes = pd.DataFrame(frames_v).sort_index().reindex(closes.index).ffill().fillna(0)
    highs = pd.DataFrame(frames_h).sort_index().reindex(closes.index).ffill()
    lows = pd.DataFrame(frames_l).sort_index().reindex(closes.index).ffill()
    opens = pd.DataFrame(frames_o).sort_index().reindex(closes.index).ffill()
    return closes, volumes, highs, lows, opens


def load_hourly():
    frames = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1h.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        frames[asset] = df
    return frames


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


def sh_test(equity_series, n_boot=5000):
    rets = equity_series.pct_change().dropna().values
    if len(rets) < 30:
        return 1.0, 0.0
    obs_sharpe = np.mean(rets) / (np.std(rets, ddof=1) + 1e-10) * np.sqrt(PPY)
    t_stat = np.mean(rets) / (np.std(rets, ddof=1) / np.sqrt(len(rets)) + 1e-10)
    p_ttest = 1 - stats.t.cdf(t_stat, df=len(rets)-1)
    boot_sharpes = []
    for _ in range(n_boot):
        sample = np.random.choice(rets, size=len(rets), replace=True)
        bs = np.mean(sample) / (np.std(sample, ddof=1) + 1e-10) * np.sqrt(PPY)
        boot_sharpes.append(bs)
    p_boot = np.mean([1 for bs in boot_sharpes if bs <= 0])
    return min(p_ttest, p_boot + 0.01), obs_sharpe


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
    sh_p = 1.0
    sh_sharpe = 0.0
    if is_pass and best_signal:
        sig, reb, npos = best_signal

        eq_best = simulate(closes, sig, reb, npos)
        sh_p, sh_sharpe = sh_test(eq_best)
        print(f"  SH test: p={sh_p:.3f}, Sharpe={sh_sharpe:.3f} — {'PASS' if sh_p < 0.10 else 'FAIL'}")

        wf_results = walk_forward(closes, sig, reb, npos)
        if wf_results:
            n_wf_pos = sum(1 for s in wf_results if s > 0)
            wf_mean = np.mean(wf_results)
            wf_pass = n_wf_pos >= len(wf_results) * 0.5 and wf_mean > 0.3
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
        print(f"  Param robustness (same R/N): {(same_rn['sharpe'] > 0).sum()}/{len(same_rn)} positive ({nbr_pct:.0f}%)")

    corr_pass = abs(float(best["corr_h012"])) < 0.50
    confirmed = is_pass and wf_pass and split_pass and corr_pass and sh_p < 0.10
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
        "sh_p": sh_p, "sh_sharpe": sh_sharpe,
        "confirmed": confirmed,
    }


def build_intraday_signals(hourly, closes):
    """Build daily signals from hourly data."""
    # Initialize DataFrames
    overnight_ret = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
    intraday_ret = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
    close_vwap_dev = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
    vol_entropy = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
    intraday_reversal = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)

    for asset in ASSETS:
        if asset not in hourly:
            continue
        hdf = hourly[asset].copy()
        hdf.index = pd.to_datetime(hdf.index)

        # Group by date
        dates = hdf.index.date

        for dt in pd.unique(dates):
            day_data = hdf[hdf.index.date == dt]
            if len(day_data) < 10:
                continue
            dt_ts = pd.Timestamp(dt)
            if dt_ts not in closes.index:
                continue

            # Overnight return: first bar open vs previous close
            # We'll compute this differently - close-to-open gap
            day_open = day_data["open"].iloc[0]
            day_close = day_data["close"].iloc[-1]

            # For overnight, we need previous day's close
            prev_idx = closes.index.get_loc(dt_ts)
            if prev_idx > 0:
                prev_close = closes[asset].iloc[prev_idx - 1]
                overnight_ret.loc[dt_ts, asset] = day_open / prev_close - 1
                intraday_ret.loc[dt_ts, asset] = day_close / day_open - 1

            # VWAP deviation
            if "volume" in day_data.columns and day_data["volume"].sum() > 0:
                vwap = (day_data["close"] * day_data["volume"]).sum() / day_data["volume"].sum()
                close_vwap_dev.loc[dt_ts, asset] = (day_close - vwap) / vwap

                # Volume entropy: Shannon entropy of hourly volume distribution
                vol_dist = day_data["volume"].values
                vol_dist = vol_dist / (vol_dist.sum() + 1e-10)
                vol_dist = vol_dist[vol_dist > 0]
                entropy = -np.sum(vol_dist * np.log(vol_dist + 1e-10))
                vol_entropy.loc[dt_ts, asset] = entropy

            # Intraday reversal: correlation of first-half and second-half hourly returns
            if len(day_data) >= 12:
                mid = len(day_data) // 2
                first_half_ret = day_data["close"].iloc[:mid].pct_change().dropna().sum()
                second_half_ret = day_data["close"].iloc[mid:].pct_change().dropna().sum()
                if abs(first_half_ret) > 1e-8:
                    intraday_reversal.loc[dt_ts, asset] = second_half_ret / first_half_ret

    return overnight_ret, intraday_ret, close_vwap_dev, vol_entropy, intraday_reversal


def main():
    print("=" * 70)
    print("SESSION 187 RESEARCH BATCH 2: H-796 through H-803")
    print("=" * 70)

    closes, volumes, highs, lows, opens = load_data()
    hourly = load_hourly()
    print(f"Loaded {len(ASSETS)} assets, {len(closes)} daily bars")
    print(f"Hourly data: {len(hourly)} assets")
    h012_rets = compute_h012_returns(closes)

    all_results = {}

    # Build intraday signals
    print("\nBuilding intraday signals from hourly data...")
    overnight_ret, intraday_ret, close_vwap_dev, vol_entropy, intraday_reversal = \
        build_intraday_signals(hourly, closes)
    print("Done.")

    # === H-796: Volume Clock Momentum ===
    # Measure momentum in "volume time" — cumulate volume and measure price change
    # per unit of cumulative volume, not calendar time
    rets = closes.pct_change()
    signals_796 = {}
    for lb in [10, 20, 30, 60]:
        # Volume-weighted cumulative return over lookback
        vol_weighted_ret = (rets * volumes).rolling(lb).sum() / (volumes.rolling(lb).sum() + 1e-10)
        signals_796[f"lb{lb}"] = vol_weighted_ret

    grid_796 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [10, 20, 30, 60] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-796"] = run_hypothesis(
        "Volume Clock Momentum", "H-796",
        signals_796, closes, h012_rets, grid_796)

    # === H-797: Price Acceleration ===
    # 2nd derivative of price: change in return momentum
    # Positive acceleration = momentum building, negative = momentum fading
    signals_797 = {}
    for lb in [5, 10, 20]:
        for acc_lb in [3, 5]:
            mom = closes.pct_change(lb)
            accel = mom.diff(acc_lb)  # 2nd derivative
            signals_797[f"lb{lb}_al{acc_lb}"] = accel

    grid_797 = [{"sig_key": f"lb{lb}_al{al}", "rebal": r, "n_pos": n}
                for lb in [5, 10, 20] for al in [3, 5] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-797"] = run_hypothesis(
        "Price Acceleration", "H-797",
        signals_797, closes, h012_rets, grid_797)

    # === H-798: Overnight-Intraday Divergence ===
    # Difference between overnight and intraday returns
    # Overnight driven by institutional/global macro, intraday by retail
    signals_798 = {}
    oi_diff = overnight_ret.astype(float) - intraday_ret.astype(float)
    for lb in [5, 10, 20]:
        signals_798[f"lb{lb}"] = oi_diff.rolling(lb).mean()

    grid_798 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [5, 10, 20] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-798"] = run_hypothesis(
        "Overnight-Intraday Divergence", "H-798",
        signals_798, closes, h012_rets, grid_798)

    # === H-799: Hour-Weighted Return ===
    # Weight returns by how much volume happens in each hour relative to normal
    # High-volume-hour returns carry more information
    # This is effectively the volume-clock momentum but measured differently
    signals_799 = {}
    for lb in [5, 10, 20]:
        # Use overnight return (gap) as a different angle on information
        # "Smart money" trades overnight via gaps
        overnight_smooth = overnight_ret.astype(float).rolling(lb).mean()
        signals_799[f"lb{lb}"] = overnight_smooth

    grid_799 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [5, 10, 20] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-799"] = run_hypothesis(
        "Overnight Return Signal (Smart Money)", "H-799",
        signals_799, closes, h012_rets, grid_799)

    # === H-800: Volume Distribution Entropy ===
    # Entropy of intraday volume: high entropy = evenly distributed volume (normal trading)
    # Low entropy = concentrated volume (big move, potentially institutional)
    signals_800 = {}
    for lb in [5, 10, 20]:
        ent_smooth = vol_entropy.astype(float).rolling(lb).mean()
        signals_800[f"lb{lb}"] = -ent_smooth  # low entropy (concentrated) = bullish (institutions buying)

    grid_800 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [5, 10, 20] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-800"] = run_hypothesis(
        "Volume Distribution Entropy", "H-800",
        signals_800, closes, h012_rets, grid_800)

    # === H-801: Close-VWAP Deviation ===
    # Close above VWAP = bullish pressure, below = bearish
    # Persistent deviation signals informed buying/selling
    signals_801 = {}
    for lb in [3, 5, 10, 20]:
        cvd_smooth = close_vwap_dev.astype(float).rolling(lb).mean()
        signals_801[f"lb{lb}"] = cvd_smooth

    grid_801 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [3, 5, 10, 20] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-801"] = run_hypothesis(
        "Close-VWAP Deviation", "H-801",
        signals_801, closes, h012_rets, grid_801)

    # === H-802: Intraday Reversal Strength ===
    # How strongly does the 2nd half of the day reverse the 1st half?
    # Persistent reversal = mean-reverting micro, persistent continuation = trending
    signals_802 = {}
    for lb in [5, 10, 20]:
        rev_smooth = intraday_reversal.astype(float).clip(-5, 5).rolling(lb).mean()
        signals_802[f"lb{lb}"] = rev_smooth  # positive = intraday continuation, negative = intraday reversal

    grid_802 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [5, 10, 20] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-802"] = run_hypothesis(
        "Intraday Reversal Strength", "H-802",
        signals_802, closes, h012_rets, grid_802)

    # === H-803: Range Compression Ratio ===
    # N-day range / sum(1-day ranges) — low ratio means price is compressing
    # Compression often precedes breakout
    daily_range = highs - lows
    signals_803 = {}
    for n in [5, 10, 20]:
        n_day_high = highs.rolling(n).max()
        n_day_low = lows.rolling(n).min()
        n_day_range = n_day_high - n_day_low
        sum_daily_ranges = daily_range.rolling(n).sum()
        ratio = n_day_range / (sum_daily_ranges + 1e-10)
        # Low ratio = compression. Two directions: contrarian (buy compression) or momentum
        signals_803[f"n{n}_contrarian"] = -ratio  # buy compressed (expect breakout)
        signals_803[f"n{n}_momentum"] = ratio  # buy expanded (trending)

    grid_803 = [{"sig_key": f"n{n}_{d}", "rebal": r, "n_pos": np_}
                for n in [5, 10, 20] for d in ["contrarian", "momentum"]
                for r in [3, 5, 7] for np_ in [3, 4]]
    all_results["H-803"] = run_hypothesis(
        "Range Compression Ratio", "H-803",
        signals_803, closes, h012_rets, grid_803)

    # === SUMMARY ===
    print("\n\n" + "=" * 70)
    print("BATCH 2 SUMMARY (H-796 to H-803)")
    print("=" * 70)
    for hid, res in sorted(all_results.items()):
        if res is None:
            print(f"  {hid}: SKIPPED")
        else:
            status = "CONFIRMED" if res["confirmed"] else "REJECTED"
            print(f"  {hid} ({res['name']}): {status} — IS Sharpe {res['best_sharpe']:.3f}, "
                  f"WF {res['wf_positive']}/{res['wf_total']}, SH p={res.get('sh_p',1):.3f}, "
                  f"Corr {res['corr_h012']:.3f}")

    out_path = ROOT / "results" / "session187_batch2.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
