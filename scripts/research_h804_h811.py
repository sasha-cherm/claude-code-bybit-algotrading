"""
Session 187 Research Batch 3: H-804 through H-811
8 novel cross-sectional daily factor backtests.
Focus: Information-theoretic, regime detection, and novel XS constructions.

Hypotheses:
  H-804: Mutual Information Signal — MI between an asset's returns and BTC returns (beta stability)
  H-805: Return Predictability — rolling R² of AR(1) model, captures how predictable returns are
  H-806: Conditional Volatility Ratio — vol during up-days vs down-days, captures asymmetric risk
  H-807: Dispersion Signal — cross-sectional dispersion of returns as a market regime indicator
  H-808: Relative Drawdown — each asset's DD rank vs cross-section, buy least-drawn-down
  H-809: Funding-Price Divergence — when funding disagrees with price direction
  H-810: Volume Trend Strength — ADX applied to volume rather than price
  H-811: Multi-Period Return Consistency — agreement between short/medium/long momentum
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
    frames_c, frames_v, frames_h, frames_l = {}, {}, {}, {}
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
    closes = pd.DataFrame(frames_c).sort_index().dropna(how="all").ffill().dropna(how="all")
    volumes = pd.DataFrame(frames_v).sort_index().reindex(closes.index).ffill().fillna(0)
    highs = pd.DataFrame(frames_h).sort_index().reindex(closes.index).ffill()
    lows = pd.DataFrame(frames_l).sort_index().reindex(closes.index).ffill()
    return closes, volumes, highs, lows


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


def main():
    print("=" * 70)
    print("SESSION 187 RESEARCH BATCH 3: H-804 through H-811")
    print("=" * 70)

    closes, volumes, highs, lows = load_data()
    funding = load_funding()
    print(f"Loaded {len(ASSETS)} assets, {len(closes)} daily bars")
    if len(funding) > 0:
        print(f"Funding data: {len(funding)} rows, {len(funding.columns)} assets")
    h012_rets = compute_h012_returns(closes)

    all_results = {}
    rets = closes.pct_change()

    # === H-804: Mutual Information Signal ===
    # Measure how much information an asset's returns share with BTC returns
    # Low MI = more independent = better diversifier. High MI = just beta.
    # Signal: Long low-MI assets (independent movers), short high-MI (just BTC beta)
    btc_rets = rets["BTC"] if "BTC" in rets.columns else None
    if btc_rets is not None:
        signals_804 = {}
        for lb in [20, 30, 60]:
            mi_df = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
            for asset in ASSETS:
                if asset not in rets.columns or asset == "BTC":
                    continue
                # Use rolling R² as a proxy for MI (much faster than actual MI calculation)
                rolling_r2 = pd.Series(index=closes.index, dtype=float)
                a_rets = rets[asset].values
                b_rets = btc_rets.values
                for i in range(lb, len(closes)):
                    ar = a_rets[i-lb:i]
                    br = b_rets[i-lb:i]
                    mask = ~(np.isnan(ar) | np.isnan(br))
                    if mask.sum() < 10:
                        continue
                    corr = np.corrcoef(ar[mask], br[mask])[0, 1]
                    rolling_r2.iloc[i] = corr ** 2
                mi_df[asset] = rolling_r2
            signals_804[f"lb{lb}"] = -mi_df  # long low-MI (independent), short high-MI

        grid_804 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                    for lb in [20, 30, 60] for r in [3, 5, 7] for n in [3, 4]]
        all_results["H-804"] = run_hypothesis(
            "BTC Independence (Low MI)", "H-804",
            signals_804, closes, h012_rets, grid_804)
    else:
        all_results["H-804"] = None

    # === H-805: Return Predictability ===
    # Rolling R² of AR(1) model — how predictable are returns?
    # High predictability = pattern exists, low = random walk
    signals_805 = {}
    for lb in [20, 30, 60]:
        pred_df = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for asset in ASSETS:
            if asset not in rets.columns:
                continue
            r = rets[asset].values
            for i in range(lb, len(closes)):
                window = r[i-lb:i]
                mask = ~np.isnan(window)
                if mask.sum() < 10:
                    continue
                w = window[mask]
                if len(w) < 5:
                    continue
                # AR(1) R²: correlation between r(t) and r(t-1)
                corr = np.corrcoef(w[1:], w[:-1])[0, 1]
                pred_df.iloc[i, ASSETS.index(asset)] = abs(corr)  # absolute autocorrelation
        signals_805[f"lb{lb}"] = pred_df  # high predictability = signal exists = long

    grid_805 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [20, 30, 60] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-805"] = run_hypothesis(
        "Return Predictability (AR1 R²)", "H-805",
        signals_805, closes, h012_rets, grid_805)

    # === H-806: Conditional Volatility Ratio ===
    # Vol during up-days vs down-days
    # High ratio = bigger moves up than down = bullish asymmetry
    signals_806 = {}
    for lb in [20, 30, 60]:
        cond_vol = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for asset in ASSETS:
            if asset not in rets.columns:
                continue
            r = rets[asset].values
            for i in range(lb, len(closes)):
                window = r[i-lb:i]
                mask = ~np.isnan(window)
                w = window[mask]
                up = w[w > 0]
                down = w[w < 0]
                if len(up) < 3 or len(down) < 3:
                    continue
                up_vol = np.std(up)
                down_vol = np.std(down)
                cond_vol.iloc[i, ASSETS.index(asset)] = up_vol / (down_vol + 1e-10) - 1
        signals_806[f"lb{lb}"] = cond_vol  # high = bigger up moves = long

    grid_806 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [20, 30, 60] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-806"] = run_hypothesis(
        "Conditional Vol Ratio (Up/Down)", "H-806",
        signals_806, closes, h012_rets, grid_806)

    # === H-807: Cross-Sectional Dispersion Signal ===
    # When XS dispersion is high, rank-based signals work better
    # Use dispersion as a conditioner: enhance momentum signal when dispersion is high
    xs_disp = rets.std(axis=1)  # daily XS dispersion
    signals_807 = {}
    for mom_lb in [10, 20, 60]:
        for disp_lb in [5, 10]:
            mom = closes.pct_change(mom_lb)
            disp_smooth = xs_disp.rolling(disp_lb).mean()
            disp_median = disp_smooth.rolling(60).median()
            high_disp = (disp_smooth > disp_median).astype(float)
            # Momentum only when dispersion is high
            conditioned = mom.multiply(high_disp, axis=0)
            signals_807[f"m{mom_lb}_d{disp_lb}"] = conditioned

    grid_807 = [{"sig_key": f"m{m}_d{d}", "rebal": r, "n_pos": n}
                for m in [10, 20, 60] for d in [5, 10] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-807"] = run_hypothesis(
        "Dispersion-Conditioned Momentum", "H-807",
        signals_807, closes, h012_rets, grid_807)

    # === H-808: Relative Drawdown ===
    # Each asset's current drawdown relative to cross-section
    # Buy least-drawn-down (strength), sell most-drawn-down (weakness)
    signals_808 = {}
    for lb in [10, 20, 30, 60]:
        rolling_max = closes.rolling(lb).max()
        dd = closes / rolling_max - 1.0
        # XS rank: higher = less drawdown = stronger
        signals_808[f"lb{lb}"] = dd  # less negative = stronger = long

    grid_808 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [10, 20, 30, 60] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-808"] = run_hypothesis(
        "Relative Drawdown (Strength)", "H-808",
        signals_808, closes, h012_rets, grid_808)

    # === H-809: Funding-Price Divergence ===
    # When funding rate direction disagrees with recent price direction
    if len(funding) > 0 and len(funding.columns) >= 8:
        fund_aligned = funding.reindex(closes.index).ffill()
        signals_809 = {}
        for price_lb in [5, 10, 20]:
            for fund_lb in [3, 5, 10]:
                price_dir = closes.pct_change(price_lb).apply(np.sign)
                fund_dir = fund_aligned.rolling(fund_lb).mean().apply(np.sign)
                divergence = price_dir - fund_dir  # +2 = price up, funding negative (bullish divergence)
                signals_809[f"p{price_lb}_f{fund_lb}"] = divergence

        grid_809 = [{"sig_key": f"p{p}_f{fl}", "rebal": r, "n_pos": n}
                    for p in [5, 10, 20] for fl in [3, 5, 10] for r in [3, 5, 7] for n in [3, 4]]
        all_results["H-809"] = run_hypothesis(
            "Funding-Price Divergence", "H-809",
            signals_809, closes, h012_rets, grid_809)
    else:
        print("\n[H-809: Skipped — insufficient funding data]")
        all_results["H-809"] = None

    # === H-810: Volume Trend Strength ===
    # ADX applied to volume rather than price: measures how strongly volume is trending
    # High volume trend + price momentum = stronger conviction
    signals_810 = {}
    for lb in [10, 14, 20]:
        vol_trend = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for asset in ASSETS:
            if asset not in volumes.columns:
                continue
            v = volumes[asset].values
            # Simplified volume ADX: directional movement of volume
            for i in range(lb, len(closes)):
                window = v[i-lb:i]
                if np.any(np.isnan(window)) or np.all(window == 0):
                    continue
                up_moves = np.maximum(np.diff(window), 0)
                dn_moves = np.maximum(-np.diff(window), 0)
                avg_up = np.mean(up_moves)
                avg_dn = np.mean(dn_moves)
                di_diff = abs(avg_up - avg_dn)
                di_sum = avg_up + avg_dn + 1e-10
                adx_vol = di_diff / di_sum
                # Direction: positive if volume trending up
                direction = 1 if avg_up > avg_dn else -1
                vol_trend.iloc[i, ASSETS.index(asset)] = adx_vol * direction
        signals_810[f"lb{lb}"] = vol_trend  # high = strong uptrend in volume = bullish

    grid_810 = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
                for lb in [10, 14, 20] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-810"] = run_hypothesis(
        "Volume Trend Strength (Vol-ADX)", "H-810",
        signals_810, closes, h012_rets, grid_810)

    # === H-811: Multi-Period Return Consistency ===
    # Agreement between short (5d), medium (20d), and long (60d) momentum
    # All agreeing = strong conviction
    signals_811 = {}
    for short_lb in [3, 5]:
        for med_lb in [10, 20]:
            for long_lb in [40, 60]:
                mom_s = closes.pct_change(short_lb).rank(axis=1, pct=True)
                mom_m = closes.pct_change(med_lb).rank(axis=1, pct=True)
                mom_l = closes.pct_change(long_lb).rank(axis=1, pct=True)
                # Average of percentile ranks across horizons
                consistency = (mom_s + mom_m + mom_l) / 3.0
                signals_811[f"s{short_lb}_m{med_lb}_l{long_lb}"] = consistency

    grid_811 = [{"sig_key": f"s{s}_m{m}_l{l}", "rebal": r, "n_pos": n}
                for s in [3, 5] for m in [10, 20] for l in [40, 60]
                for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-811"] = run_hypothesis(
        "Multi-Period Return Consistency", "H-811",
        signals_811, closes, h012_rets, grid_811)

    # === SUMMARY ===
    print("\n\n" + "=" * 70)
    print("BATCH 3 SUMMARY (H-804 to H-811)")
    print("=" * 70)
    for hid, res in sorted(all_results.items()):
        if res is None:
            print(f"  {hid}: SKIPPED")
        else:
            status = "CONFIRMED" if res["confirmed"] else "REJECTED"
            print(f"  {hid} ({res['name']}): {status} — IS Sharpe {res['best_sharpe']:.3f}, "
                  f"WF {res['wf_positive']}/{res['wf_total']}, SH p={res.get('sh_p',1):.3f}, "
                  f"Corr {res['corr_h012']:.3f}")

    out_path = ROOT / "results" / "session187_batch3.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
