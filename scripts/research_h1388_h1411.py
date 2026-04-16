"""
Session 212 Research: H-1388 through H-1411 (24 hypotheses).
Batch 1 (H-1388..H-1395): Candle anatomy — OHLC body/wick dynamics
Batch 2 (H-1396..H-1403): Market beta decomposition — rolling beta/alpha vs BTC
Batch 3 (H-1404..H-1411): Return path quality & efficiency
"""

import json, sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = ["BTC","ETH","SOL","XRP","DOGE","ADA","AVAX","DOT","LINK","ATOM","NEAR","OP","ARB","SUI"]
DATA_DIR = ROOT / "data"
FEE_RATE = 0.001
INITIAL_CAPITAL = 10_000.0
PPY = 365
WF_FOLDS = 4
WF_TEST_DAYS = 120
WF_MIN_TRAIN = 180


def load_data():
    frames_o, frames_c, frames_v, frames_h, frames_l = {}, {}, {}, {}, {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        frames_o[asset] = df["open"]
        frames_c[asset] = df["close"]
        frames_v[asset] = df["volume"]
        frames_h[asset] = df["high"]
        frames_l[asset] = df["low"]
    opens = pd.DataFrame(frames_o).sort_index().dropna(how="all").ffill().dropna(how="all")
    closes = pd.DataFrame(frames_c).sort_index().reindex(opens.index).ffill()
    volumes = pd.DataFrame(frames_v).sort_index().reindex(opens.index).ffill().fillna(0)
    highs = pd.DataFrame(frames_h).sort_index().reindex(opens.index).ffill()
    lows = pd.DataFrame(frames_l).sort_index().reindex(opens.index).ffill()
    return opens, closes, volumes, highs, lows


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


def sh_test(equity_series, n_boot=3000):
    rets = equity_series.pct_change().dropna().values
    if len(rets) < 30:
        return 1.0, 0.0
    t_stat = np.mean(rets) / (np.std(rets, ddof=1) / np.sqrt(len(rets)) + 1e-10)
    p_ttest = 1 - stats.t.cdf(t_stat, df=len(rets)-1)
    boot_sharpes = []
    for _ in range(n_boot):
        sample = np.random.choice(rets, size=len(rets), replace=True)
        bs = np.mean(sample) / (np.std(sample, ddof=1) + 1e-10) * np.sqrt(PPY)
        boot_sharpes.append(bs)
    p_boot = np.mean([1 for bs in boot_sharpes if bs <= 0])
    return min(p_ttest, p_boot + 0.01), np.mean(boot_sharpes)


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


def split_half_sharpes(closes, sig, reb, npos):
    mid = len(sig) // 2
    eq1 = simulate(closes, sig, reb, npos, 0, mid)
    eq2 = simulate(closes, sig, reb, npos, mid, len(sig))
    sr1 = sharpe_ratio(eq1.pct_change().dropna(), periods_per_year=PPY)
    sr2 = sharpe_ratio(eq2.pct_change().dropna(), periods_per_year=PPY)
    return sr1, sr2


def run_hypothesis(name, hid, signals, closes, h012_rets, param_grid, no_abs_filter=False):
    print(f"\n{'='*70}\n{hid}: {name}\n{'='*70}")
    results = []
    best_signal = None
    best_sharpe = -999
    for params in param_grid:
        rebal = params["rebal"]; n_pos = params["n_pos"]
        sig = signals[params["sig_key"]] if isinstance(signals, dict) else signals
        sig_shifted = sig.shift(1)
        eq = simulate(closes, sig_shifted, rebal, n_pos)
        if len(eq) < 100: continue
        rets = eq.pct_change().dropna()
        sr = sharpe_ratio(rets, periods_per_year=PPY)
        ar = annual_return(eq, PPY); dd = max_drawdown(eq)
        common = rets.index.intersection(h012_rets.index)
        corr_012 = rets.reindex(common).corr(h012_rets.reindex(common))
        results.append({"sharpe": sr, "annual_return": ar, "max_dd": dd,
                        "corr_h012": corr_012, **params})
        if sr > best_sharpe:
            best_sharpe = sr
            best_signal = (sig_shifted, rebal, n_pos)
    if not results:
        print("  No valid results"); return None
    df = pd.DataFrame(results)
    n_pos_is = (df["sharpe"] > 0).sum()
    pct_pos = n_pos_is / len(df) * 100
    is_pass = pct_pos >= 66
    print(f"  IS: {n_pos_is}/{len(df)} positive ({pct_pos:.0f}%) — {'PASS' if is_pass else 'FAIL'}")
    best = df.loc[df["sharpe"].idxmax()]
    print(f"  Best: R={best['rebal']},N={best['n_pos']},{best['sig_key']} — Sharpe {best['sharpe']:.3f}, Ann {best['annual_return']*100:.1f}%, DD {best['max_dd']*100:.1f}%")
    print(f"  Corr H-012: {best['corr_h012']:.3f}")
    wf_results = []
    sh_p = 1.0; sr_h1 = sr_h2 = 0.0
    split_pass = False; wf_pass = False
    if is_pass and best_signal:
        sig, reb, npos = best_signal
        eq_best = simulate(closes, sig, reb, npos)
        sh_p, sh_sharpe = sh_test(eq_best)
        print(f"  SH p={sh_p:.3f}")
        wf_results = walk_forward(closes, sig, reb, npos)
        if wf_results:
            n_wf_pos = sum(1 for s in wf_results if s > 0)
            wf_mean = np.mean(wf_results)
            wf_pass = n_wf_pos >= len(wf_results) * 0.5 and wf_mean > 0.3
            print(f"  WF: {n_wf_pos}/{len(wf_results)} positive, mean {wf_mean:.3f}, folds={[f'{s:.2f}' for s in wf_results]}")
        sr_h1, sr_h2 = split_half_sharpes(closes, sig, reb, npos)
        split_pass = sr_h1 > 0 and sr_h2 > 0
        print(f"  Split: H1={sr_h1:.3f}, H2={sr_h2:.3f} — {'PASS' if split_pass else 'FAIL'}")
    corr_ok = abs(float(best["corr_h012"])) < 0.50
    confirmed = is_pass and wf_pass and split_pass and corr_ok and sh_p < 0.15 and best["sharpe"] > 1.0
    print(f"\n  >>> {'CONFIRMED' if confirmed else 'REJECTED'} <<<")
    return {
        "hid": hid, "name": name,
        "total_params": len(df), "pct_positive_is": float(pct_pos),
        "best_sharpe": float(best["sharpe"]),
        "best_annual_return": float(best["annual_return"]),
        "best_max_dd": float(best["max_dd"]),
        "corr_h012": float(best["corr_h012"]),
        "best_rebal": int(best["rebal"]), "best_n_pos": int(best["n_pos"]),
        "best_sig_key": str(best["sig_key"]),
        "wf_positive": sum(1 for s in wf_results if s > 0) if wf_results else 0,
        "wf_total": len(wf_results),
        "wf_folds": [float(s) for s in wf_results],
        "sh_p": float(sh_p),
        "sr_h1": float(sr_h1), "sr_h2": float(sr_h2),
        "confirmed": bool(confirmed),
    }


def main():
    opens, closes, volumes, highs, lows = load_data()
    print(f"Loaded {len(ASSETS)} assets, {len(closes)} bars")
    h012_rets = compute_h012_returns(closes)
    rets = closes.pct_change()
    all_results = {}

    body = (closes - opens).abs()
    rng = (highs - lows).replace(0, np.nan)
    upper_wick = (highs - closes.combine(opens, np.maximum))
    lower_wick = (closes.combine(opens, np.minimum) - lows)
    body_dir = np.sign(closes - opens)

    # === H-1388: Body/Range Avg (directional candles) ===
    sigs = {}
    for lb in [10, 20, 30]:
        sigs[f"lb{lb}"] = (body / rng).rolling(lb).mean()
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [10, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1388"] = run_hypothesis("Body/Range Avg", "H-1388", sigs, closes, h012_rets, grid)

    # === H-1389: Upper Wick Share Trend ===
    sigs = {}
    for lb in [10, 20, 30]:
        sigs[f"lb{lb}"] = (upper_wick / rng).rolling(lb).mean()
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [10, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1389"] = run_hypothesis("Upper Wick Share", "H-1389", sigs, closes, h012_rets, grid)

    # === H-1390: Lower Wick Share Trend ===
    sigs = {}
    for lb in [10, 20, 30]:
        sigs[f"lb{lb}"] = (lower_wick / rng).rolling(lb).mean()
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [10, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1390"] = run_hypothesis("Lower Wick Share", "H-1390", sigs, closes, h012_rets, grid)

    # === H-1391: Wick Asymmetry (lower - upper) ===
    sigs = {}
    for lb in [10, 20, 30]:
        sigs[f"lb{lb}"] = ((lower_wick - upper_wick) / rng).rolling(lb).mean()
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [10, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1391"] = run_hypothesis("Wick Asymmetry", "H-1391", sigs, closes, h012_rets, grid)

    # === H-1392: Range Stability ===
    sigs = {}
    for lb in [15, 20, 30]:
        sigs[f"lb{lb}"] = (rng.rolling(lb).std() / rng.rolling(lb).mean())
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [15, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1392"] = run_hypothesis("Range Stability (CV)", "H-1392", sigs, closes, h012_rets, grid)

    # === H-1393: Body Direction Consistency (body sign vs 5d return sign) ===
    sigs = {}
    for lb in [15, 20, 30]:
        r5_sign = np.sign(closes.pct_change(5))
        match = (body_dir == r5_sign).astype(float)
        sigs[f"lb{lb}"] = match.rolling(lb).mean()
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [15, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1393"] = run_hypothesis("Body Direction Consistency", "H-1393", sigs, closes, h012_rets, grid)

    # === H-1394: Daily Efficiency (|C-O| / True Range) ===
    tr = pd.concat([rng, (highs - closes.shift(1)).abs(), (lows - closes.shift(1)).abs()]).groupby(level=0).max()
    tr = tr.reindex(closes.index)
    sigs = {}
    for lb in [10, 20, 30]:
        sigs[f"lb{lb}"] = (body / tr).rolling(lb).mean()
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [10, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1394"] = run_hypothesis("Daily Efficiency (Body/TR)", "H-1394", sigs, closes, h012_rets, grid)

    # === H-1395: Relative Body Size (body vs 20d avg body) ===
    sigs = {}
    for lb in [5, 10]:
        base = body.rolling(20).mean()
        sigs[f"lb{lb}"] = (body.rolling(lb).mean() / (base + 1e-10)) - 1
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [5, 10] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1395"] = run_hypothesis("Relative Body Size", "H-1395", sigs, closes, h012_rets, grid)

    # ========= BATCH 2: Market Beta Decomposition =========
    btc_rets = rets["BTC"] if "BTC" in rets.columns else None

    # === H-1396: Rolling Beta to BTC ===
    def rolling_beta(asset_r, mkt_r, lb):
        cov = asset_r.rolling(lb).cov(mkt_r)
        var = mkt_r.rolling(lb).var()
        return cov / (var + 1e-12)

    sigs = {}
    for lb in [20, 30, 60]:
        bdf = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for a in ASSETS:
            if a in rets.columns:
                bdf[a] = rolling_beta(rets[a], btc_rets, lb)
        sigs[f"lb{lb}"] = bdf
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [20, 30, 60] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1396"] = run_hypothesis("Rolling Beta", "H-1396", sigs, closes, h012_rets, grid)

    # === H-1397: Beta Change (short - long) ===
    sigs = {}
    for lbs in [(20, 60), (15, 45), (30, 90)]:
        sh_lb, ln_lb = lbs
        bdf = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for a in ASSETS:
            if a in rets.columns:
                bdf[a] = rolling_beta(rets[a], btc_rets, sh_lb) - rolling_beta(rets[a], btc_rets, ln_lb)
        sigs[f"sh{sh_lb}_ln{ln_lb}"] = bdf
    grid = [{"sig_key": f"sh{sh_lb}_ln{ln_lb}", "rebal": r, "n_pos": n}
            for (sh_lb, ln_lb) in [(20, 60), (15, 45), (30, 90)] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1397"] = run_hypothesis("Beta Change", "H-1397", sigs, closes, h012_rets, grid)

    # === H-1398: Idiosyncratic Vol (residual std after beta regression) ===
    sigs = {}
    for lb in [20, 30, 60]:
        idf = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for a in ASSETS:
            if a in rets.columns:
                beta = rolling_beta(rets[a], btc_rets, lb)
                resid = rets[a] - beta * btc_rets
                idf[a] = resid.rolling(lb).std()
        sigs[f"lb{lb}"] = idf
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [20, 30, 60] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1398"] = run_hypothesis("Idio Vol", "H-1398", sigs, closes, h012_rets, grid)

    # === H-1399: Alpha Persistence (mean of residuals) ===
    sigs = {}
    for lb in [20, 30, 60]:
        adf = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for a in ASSETS:
            if a in rets.columns:
                beta = rolling_beta(rets[a], btc_rets, lb)
                resid = rets[a] - beta * btc_rets
                adf[a] = resid.rolling(lb).mean()
        sigs[f"lb{lb}"] = adf
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [20, 30, 60] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1399"] = run_hypothesis("Alpha Persistence", "H-1399", sigs, closes, h012_rets, grid)

    # === H-1400: R² Change (recent vs prior window) ===
    def rolling_r2(asset_r, mkt_r, lb):
        cov = asset_r.rolling(lb).cov(mkt_r)
        var_a = asset_r.rolling(lb).var()
        var_m = mkt_r.rolling(lb).var()
        r = cov / ((var_a * var_m).pow(0.5) + 1e-12)
        return r * r

    sigs = {}
    for lb in [20, 30]:
        r2 = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for a in ASSETS:
            if a in rets.columns:
                r2[a] = rolling_r2(rets[a], btc_rets, lb)
        sigs[f"lb{lb}"] = r2 - r2.shift(lb)
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1400"] = run_hypothesis("R2 Change", "H-1400", sigs, closes, h012_rets, grid)

    # === H-1401: Beta-Adjusted Momentum (alpha momentum over 20d) ===
    sigs = {}
    for lb in [20, 30, 60]:
        bam = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for a in ASSETS:
            if a in rets.columns:
                beta = rolling_beta(rets[a], btc_rets, lb)
                resid = rets[a] - beta * btc_rets
                bam[a] = resid.rolling(lb).sum()
        sigs[f"lb{lb}"] = bam
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [20, 30, 60] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1401"] = run_hypothesis("Beta-Adjusted Momentum", "H-1401", sigs, closes, h012_rets, grid)

    # === H-1402: Up-Beta vs Down-Beta ===
    sigs = {}
    for lb in [30, 60]:
        udf = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for a in ASSETS:
            if a not in rets.columns: continue
            up_mask = (btc_rets > 0).astype(float)
            dn_mask = (btc_rets < 0).astype(float)
            # rolling conditional beta approximation: cov(asset*mask, btc*mask) / var(btc*mask)
            ar_up = rets[a] * up_mask
            br_up = btc_rets * up_mask
            ar_dn = rets[a] * dn_mask
            br_dn = btc_rets * dn_mask
            beta_up = ar_up.rolling(lb).cov(br_up) / (br_up.rolling(lb).var() + 1e-12)
            beta_dn = ar_dn.rolling(lb).cov(br_dn) / (br_dn.rolling(lb).var() + 1e-12)
            udf[a] = beta_up - beta_dn  # positive = captures up more than down
        sigs[f"lb{lb}"] = udf
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [30, 60] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1402"] = run_hypothesis("Up-Down Beta Diff", "H-1402", sigs, closes, h012_rets, grid)

    # === H-1403: Correlation to XS Mean ===
    sigs = {}
    xs_mean = rets.mean(axis=1)
    for lb in [20, 30, 60]:
        cdf = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for a in ASSETS:
            if a in rets.columns:
                cdf[a] = rets[a].rolling(lb).corr(xs_mean)
        sigs[f"lb{lb}"] = cdf
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [20, 30, 60] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1403"] = run_hypothesis("Corr to XS Mean", "H-1403", sigs, closes, h012_rets, grid)

    # ========= BATCH 3: Return Path Quality =========
    # === H-1404: Path Efficiency (|net return| / sum of abs returns) ===
    sigs = {}
    for lb in [10, 20, 30]:
        net = rets.rolling(lb).sum().abs()
        abs_sum = rets.abs().rolling(lb).sum()
        sigs[f"lb{lb}"] = net / (abs_sum + 1e-10)
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [10, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1404"] = run_hypothesis("Path Efficiency", "H-1404", sigs, closes, h012_rets, grid)

    # === H-1405: Positive Day Contribution Share ===
    sigs = {}
    for lb in [15, 20, 30]:
        pos_sum = rets.clip(lower=0).rolling(lb).sum()
        abs_sum = rets.abs().rolling(lb).sum()
        sigs[f"lb{lb}"] = pos_sum / (abs_sum + 1e-10)
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [15, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1405"] = run_hypothesis("Positive Day Share", "H-1405", sigs, closes, h012_rets, grid)

    # === H-1406: Max-Day Return Share ===
    sigs = {}
    for lb in [15, 20, 30]:
        max_abs = rets.abs().rolling(lb).max()
        abs_sum = rets.abs().rolling(lb).sum()
        sigs[f"lb{lb}"] = max_abs / (abs_sum + 1e-10)
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [15, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1406"] = run_hypothesis("Max Day Share", "H-1406", sigs, closes, h012_rets, grid)

    # === H-1407: Return Smoothness (avg |delta ret|) ===
    sigs = {}
    for lb in [15, 20, 30]:
        delta = rets.diff().abs()
        sigs[f"lb{lb}"] = -delta.rolling(lb).mean()  # negate: high = smooth
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [15, 20, 30] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1407"] = run_hypothesis("Return Smoothness", "H-1407", sigs, closes, h012_rets, grid)

    # === H-1408: Variance Ratio (var(n-day ret) / n * var(1-day)) ===
    sigs = {}
    for lb in [20, 30, 60]:
        for n_days in [5, 10]:
            n_ret = rets.rolling(n_days).sum()
            vr = n_ret.rolling(lb).var() / (n_days * rets.rolling(lb).var() + 1e-12)
            sigs[f"lb{lb}_n{n_days}"] = vr
    grid = [{"sig_key": f"lb{lb}_n{n_days}", "rebal": r, "n_pos": n}
            for lb in [20, 30, 60] for n_days in [5, 10] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1408"] = run_hypothesis("Variance Ratio", "H-1408", sigs, closes, h012_rets, grid)

    # === H-1409: Avg Same-Sign Run Length ===
    def avg_run_length(series, lb):
        # rolling average length of same-sign runs in last lb days
        signs = np.sign(series.values)
        out = np.full(len(signs), np.nan)
        for i in range(lb, len(signs)):
            w = signs[i - lb:i]
            runs = []
            cur = 1
            for j in range(1, len(w)):
                if w[j] == w[j-1] and w[j] != 0:
                    cur += 1
                else:
                    runs.append(cur)
                    cur = 1
            runs.append(cur)
            out[i] = np.mean(runs) if runs else np.nan
        return pd.Series(out, index=series.index)

    sigs = {}
    for lb in [20, 30, 60]:
        rdf = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for a in ASSETS:
            if a in rets.columns:
                rdf[a] = avg_run_length(rets[a], lb)
        sigs[f"lb{lb}"] = rdf
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [20, 30, 60] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1409"] = run_hypothesis("Avg Run Length", "H-1409", sigs, closes, h012_rets, grid)

    # === H-1410: Cum-Ret Linearity (R² of cum ret vs time) ===
    def rolling_r2_vs_time(series, lb):
        out = np.full(len(series), np.nan)
        x = np.arange(lb).astype(float)
        x_mean = x.mean()
        x_var = ((x - x_mean) ** 2).sum()
        for i in range(lb, len(series)):
            y = series.values[i - lb:i]
            if np.any(np.isnan(y)): continue
            y_cum = np.cumsum(y)
            y_mean = y_cum.mean()
            num = ((x - x_mean) * (y_cum - y_mean)).sum()
            y_var = ((y_cum - y_mean) ** 2).sum()
            denom = (x_var * y_var) ** 0.5
            if denom < 1e-12: continue
            r = num / denom
            slope_sign = np.sign(num)
            out[i] = slope_sign * r * r  # signed R² (long positive trend)
        return pd.Series(out, index=series.index)

    sigs = {}
    for lb in [20, 30, 45]:
        ldf = pd.DataFrame(index=closes.index, columns=ASSETS, dtype=float)
        for a in ASSETS:
            if a in rets.columns:
                ldf[a] = rolling_r2_vs_time(rets[a], lb)
        sigs[f"lb{lb}"] = ldf
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [20, 30, 45] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1410"] = run_hypothesis("Cum-Ret Linearity (Signed R2)", "H-1410", sigs, closes, h012_rets, grid)

    # === H-1411: Drift/Diffusion Ratio (mean/std of returns) ===
    sigs = {}
    for lb in [15, 20, 30, 45]:
        sigs[f"lb{lb}"] = rets.rolling(lb).mean() / (rets.rolling(lb).std() + 1e-12)
    grid = [{"sig_key": f"lb{lb}", "rebal": r, "n_pos": n}
            for lb in [15, 20, 30, 45] for r in [3, 5, 7] for n in [3, 4]]
    all_results["H-1411"] = run_hypothesis("Drift/Diffusion Ratio", "H-1411", sigs, closes, h012_rets, grid)

    # === SUMMARY ===
    print("\n\n" + "=" * 70)
    print("SESSION 212 SUMMARY (H-1388..H-1411)")
    print("=" * 70)
    for hid, res in sorted(all_results.items()):
        if res is None:
            print(f"  {hid}: SKIPPED")
        else:
            status = "CONFIRMED" if res["confirmed"] else "REJECTED"
            print(f"  {hid} ({res['name']}): {status} — IS Sharpe {res['best_sharpe']:.3f}, "
                  f"WF {res['wf_positive']}/{res['wf_total']}, SH p={res['sh_p']:.3f}, "
                  f"Corr {res['corr_h012']:.3f}, SH1/SH2 {res['sr_h1']:.2f}/{res['sr_h2']:.2f}")

    out_path = ROOT / "results" / "session212_batches.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
