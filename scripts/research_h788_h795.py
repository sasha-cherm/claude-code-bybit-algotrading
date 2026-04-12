"""
Session 187 Research Batch 1: H-788 through H-795
8 novel cross-sectional daily factor backtests.
Focus: Liquidation proxy signals, extreme events, tail-risk signals.

Hypotheses:
  H-788: Liquidation Proxy — large hourly volume spikes relative to OI as proxy for liquidation cascades
  H-789: Tail Risk Asymmetry — ratio of left-tail vs right-tail events, captures fear vs greed asymmetry
  H-790: Recovery Speed Factor — how quickly price recovers from local drawdowns
  H-791: Funding Rate Velocity — rate of change in funding rates (funding acceleration)
  H-792: OI-Price Coherence — rolling correlation between OI changes and price changes
  H-793: Volume Surprise Persistence — autocorrelation of volume surprises (vol/avg_vol - 1)
  H-794: Intraday Range Ratio — max(1h range) / daily range, captures intraday concentration of volatility
  H-795: Consecutive Move Count — length of current same-sign return streak
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
    """Load hourly data for intraday analysis."""
    frames = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1h.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        frames[asset] = df
    return frames


def load_oi():
    frames = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_oi_daily.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        if "oi" in df.columns:
            frames[asset] = df["oi"]
        elif "openInterest" in df.columns:
            frames[asset] = df["openInterest"]
        elif len(df.columns) > 0:
            frames[asset] = df.iloc[:, 0]
    if not frames:
        return pd.DataFrame()
    return pd.DataFrame(frames).sort_index().ffill()


def load_funding():
    frames = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_USDT_funding.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        if "fundingRate" in df.columns:
            frames[asset] = df["fundingRate"]
        elif len(df.columns) > 0:
            frames[asset] = df.iloc[:, 0]
    if not frames:
        return pd.DataFrame()
    fr = pd.DataFrame(frames).sort_index()
    # Resample to daily (sum of 3 8h settlements)
    return fr.resample("1D").sum()


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
    """Corrected SH test using t-test + bootstrap."""
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

        # SH test on best params
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


def main():
    print("=" * 70)
    print("SESSION 187 RESEARCH BATCH 1: H-788 through H-795")
    print("=" * 70)

    closes, volumes, highs, lows, opens = load_data()
    oi = load_oi()
    funding = load_funding()
    hourly = load_hourly()
    print(f"Loaded {len(ASSETS)} assets, {len(closes)} daily bars")
    if len(oi) > 0:
        print(f"OI data: {len(oi)} rows, {len(oi.columns)} assets")
    if len(funding) > 0:
        print(f"Funding data: {len(funding)} rows, {len(funding.columns)} assets")
    print(f"Hourly data: {len(hourly)} assets")
    h012_rets = compute_h012_returns(closes)

    all_results = {}

    # === H-788: Liquidation Proxy ===
    # Large volume spikes (vol / rolling_avg_vol) relative to OI indicate forced liquidations
    # Long assets where liquidation pressure has been absorbed (contrarian), short where it hasn't
    dv = closes * volumes  # dollar volume
    signals_788 = {}
    for lb in [5, 10, 20]:
        avg_dv = dv.rolling(lb).mean()
        vol_spike = dv / avg_dv  # ratio > 1 means unusual volume
        # Combine with price direction: high vol + price drop = forced selling → contrarian long
        ret_1d = closes.pct_change()
        liq_proxy = -vol_spike * ret_1d.apply(np.sign)  # negative return + high vol → high signal (contrarian)
        liq_smooth = liq_proxy.rolling(3).mean()
        signals_788[f"lb{lb}"] = liq_smooth

    grid_788 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [5, 10, 20] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-788"] = run_hypothesis(
        "Liquidation Proxy (Contrarian)", "H-788",
        signals_788, closes, h012_rets, grid_788)

    # === H-789: Tail Risk Asymmetry ===
    # Ratio of left-tail (negative) events to right-tail (positive) events
    # Captures fear vs greed asymmetry
    rets = closes.pct_change()
    signals_789 = {}
    for lb in [20, 30, 40, 60]:
        for pctile in [10, 20]:
            left_count = rets.rolling(lb).apply(lambda x: (x < np.percentile(x, pctile)).sum(), raw=True)
            right_count = rets.rolling(lb).apply(lambda x: (x > np.percentile(x, 100-pctile)).sum(), raw=True)
            asym = left_count / (right_count + 1e-6) - 1.0  # >0 means more left-tail (fear), <0 more right-tail
            signals_789[f"lb{lb}_p{pctile}"] = -asym  # contrarian: buy fear, sell greed

    grid_789 = [{"sig_key": f"lb{lb}_p{p}", "rebal": r, "n_pos": n}
                for lb in [20, 30, 40, 60] for p in [10, 20] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-789"] = run_hypothesis(
        "Tail Risk Asymmetry (Contrarian)", "H-789",
        signals_789, closes, h012_rets, grid_789)

    # === H-790: Recovery Speed Factor ===
    # Measure how fast an asset recovers from its rolling drawdown
    # Fast recovery = stronger support = bullish
    signals_790 = {}
    for lb in [10, 20, 30]:
        rolling_max = closes.rolling(lb).max()
        dd = closes / rolling_max - 1.0  # current drawdown (negative)
        # Recovery speed: change in drawdown over short period (positive = recovering)
        recovery = dd.diff(3)  # 3-day change in drawdown level
        signals_790[f"lb{lb}"] = recovery

    grid_790 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [10, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-790"] = run_hypothesis(
        "Recovery Speed Factor", "H-790",
        signals_790, closes, h012_rets, grid_790)

    # === H-791: Funding Rate Velocity ===
    # Rate of change in funding rates — acceleration indicates shifting sentiment
    if len(funding) > 0 and len(funding.columns) >= 8:
        signals_791 = {}
        fund_aligned = funding.reindex(closes.index).ffill()
        for lb in [3, 5, 7, 10]:
            fund_smooth = fund_aligned.rolling(lb).mean()
            fund_vel = fund_smooth.diff(lb)  # velocity of funding
            signals_791[f"lb{lb}"] = -fund_vel  # contrarian: rising funding → overbought → short

        grid_791 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                    for lb in [3, 5, 7, 10] for r in [3, 5, 7] for n in [3, 4]]
        all_results["H-791"] = run_hypothesis(
            "Funding Rate Velocity (Contrarian)", "H-791",
            signals_791, closes, h012_rets, grid_791)
    else:
        print("\n[H-791: Skipped — insufficient funding data]")
        all_results["H-791"] = None

    # === H-792: OI-Price Coherence ===
    # Rolling correlation between OI changes and price changes
    # High coherence = trending market, low coherence = divergence
    if len(oi) > 0 and len(oi.columns) >= 8:
        oi_aligned = oi.reindex(closes.index).ffill()
        oi_change = oi_aligned.pct_change()
        price_change = closes.pct_change()
        signals_792 = {}
        for lb in [10, 20, 30]:
            coherence = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
            for asset in closes.columns:
                if asset in oi_change.columns and asset in price_change.columns:
                    coherence[asset] = price_change[asset].rolling(lb).corr(oi_change[asset])
            signals_792[f"lb{lb}"] = coherence  # high coherence = trending = momentum

        grid_792 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                    for lb in [10, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
        all_results["H-792"] = run_hypothesis(
            "OI-Price Coherence", "H-792",
            signals_792, closes, h012_rets, grid_792)
    else:
        print("\n[H-792: Skipped — insufficient OI data]")
        all_results["H-792"] = None

    # === H-793: Volume Surprise Persistence ===
    # Autocorrelation of volume surprises: some assets consistently get volume shocks
    signals_793 = {}
    for lb in [10, 20, 30]:
        avg_vol = volumes.rolling(lb).mean()
        vol_surprise = volumes / avg_vol - 1.0
        # Rolling autocorrelation of volume surprises
        for acorr_lb in [5, 10]:
            vs_acorr = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
            for asset in ASSETS:
                if asset in vol_surprise.columns:
                    vs = vol_surprise[asset]
                    vs_acorr[asset] = vs.rolling(acorr_lb).apply(
                        lambda x: pd.Series(x).autocorr(lag=1) if len(x) > 2 else 0, raw=False)
            signals_793[f"lb{lb}_ac{acorr_lb}"] = vs_acorr

    grid_793 = [{"sig_key": f"lb{lb}_ac{ac}", "rebal": r, "n_pos": n}
                for lb in [10, 20, 30] for ac in [5, 10] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-793"] = run_hypothesis(
        "Volume Surprise Persistence", "H-793",
        signals_793, closes, h012_rets, grid_793)

    # === H-794: Intraday Range Ratio ===
    # max(1h range) / daily range — captures concentration of intraday volatility
    # Low ratio = smooth trending day, high ratio = choppy / one big move
    signals_794 = {}
    if hourly:
        # Build daily max-hourly-range and daily range from hourly data
        daily_max_hr_range = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        daily_total_range = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)

        for asset in ASSETS:
            if asset not in hourly:
                continue
            hdf = hourly[asset]
            if "high" not in hdf.columns or "low" not in hdf.columns:
                continue
            hr_range = (hdf["high"] - hdf["low"]) / hdf["close"]
            # Group by date and get max hourly range
            hr_range.index = pd.to_datetime(hr_range.index)
            daily_max = hr_range.groupby(hr_range.index.date).max()
            daily_max.index = pd.to_datetime(daily_max.index)

            # Daily range from high/low
            daily_h = hdf["high"].groupby(hdf.index.date).max()
            daily_l = hdf["low"].groupby(hdf.index.date).min()
            daily_c = hdf["close"].groupby(hdf.index.date).last()
            daily_h.index = pd.to_datetime(daily_h.index)
            daily_l.index = pd.to_datetime(daily_l.index)
            daily_c.index = pd.to_datetime(daily_c.index)
            dr = (daily_h - daily_l) / daily_c

            common_idx = daily_max.index.intersection(dr.index).intersection(closes.index)
            daily_max_hr_range.loc[common_idx, asset] = daily_max.reindex(common_idx).values
            daily_total_range.loc[common_idx, asset] = dr.reindex(common_idx).values

        ratio = daily_max_hr_range.astype(float) / (daily_total_range.astype(float) + 1e-8)
        for lb in [5, 10, 20]:
            signals_794[f"lb{lb}"] = -ratio.rolling(lb).mean()  # low ratio (smooth) = bullish

        grid_794 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                    for lb in [5, 10, 20] for r in [3, 5, 7] for n in [3, 4]]
        all_results["H-794"] = run_hypothesis(
            "Intraday Range Ratio", "H-794",
            signals_794, closes, h012_rets, grid_794)
    else:
        print("\n[H-794: Skipped — no hourly data]")
        all_results["H-794"] = None

    # === H-795: Consecutive Move Count ===
    # Length of current same-sign return streak
    # Long streaks are statistically unusual — contrarian signal (revert) or momentum (continue)
    rets = closes.pct_change()
    signals_795 = {}

    # Compute streak length for each asset
    streak_df = pd.DataFrame(0.0, index=closes.index, columns=ASSETS)
    for asset in ASSETS:
        if asset not in rets.columns:
            continue
        r = rets[asset].values
        streak = np.zeros(len(r))
        for i in range(1, len(r)):
            if np.isnan(r[i]) or np.isnan(r[i-1]):
                streak[i] = 0
            elif r[i] > 0 and r[i-1] > 0:
                streak[i] = streak[i-1] + 1
            elif r[i] < 0 and r[i-1] < 0:
                streak[i] = streak[i-1] - 1  # negative streak
            else:
                streak[i] = np.sign(r[i]) if r[i] != 0 else 0
        streak_df[asset] = streak

    # Contrarian: long streaks should revert
    signals_795["contrarian"] = -streak_df
    # Momentum: long streaks continue
    signals_795["momentum"] = streak_df

    grid_795 = [{"sig_key": sk, "rebal": r, "n_pos": n}
                for sk in ["contrarian", "momentum"] for r in [1, 3, 5] for n in [3, 4]]
    all_results["H-795"] = run_hypothesis(
        "Consecutive Move Streak", "H-795",
        signals_795, closes, h012_rets, grid_795)

    # === SUMMARY ===
    print("\n\n" + "=" * 70)
    print("BATCH 1 SUMMARY (H-788 to H-795)")
    print("=" * 70)
    for hid, res in sorted(all_results.items()):
        if res is None:
            print(f"  {hid}: SKIPPED")
        else:
            status = "CONFIRMED" if res["confirmed"] else "REJECTED"
            print(f"  {hid} ({res['name']}): {status} — IS Sharpe {res['best_sharpe']:.3f}, "
                  f"WF {res['wf_positive']}/{res['wf_total']}, SH p={res.get('sh_p',1):.3f}, "
                  f"Corr {res['corr_h012']:.3f}")

    # Save results
    out_path = ROOT / "results" / "session187_batch1.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
