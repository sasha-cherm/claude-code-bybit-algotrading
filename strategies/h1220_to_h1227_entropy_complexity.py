"""
Batch backtest: H-1220 to H-1227 — Entropy & Complexity Signals.
Information-theoretic measures of return predictability and structure.

H-1220: Permutation Entropy — complexity of return ordinal patterns over 20d.
H-1221: Approximate Entropy — regularity/predictability of return series.
H-1222: Spectral Entropy — frequency domain entropy (flat spectrum = high entropy).
H-1223: Lempel-Ziv Complexity — compressibility of return sign sequence.
H-1224: Dispersion Entropy — mapping returns to discrete classes, then Shannon entropy.
H-1225: Autocorrelation Decay Rate — how fast ACF decays (structured = slow).
H-1226: Permutation Entropy Change — delta of PE over two windows.
H-1227: Multi-Scale Entropy Ratio — ratio of coarse-grained to fine-grained entropy.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
from itertools import permutations
from collections import Counter

DATA_DIR = Path("data")
FEE_RATE = 0.00055
SLIPPAGE_BPS = 2

ASSETS = ["BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX", "LINK",
          "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM"]


def load_daily():
    closes, volumes = {}, {}
    for ticker in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{ticker}_USDT_1d.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            closes[f"{ticker}/USDT"] = df["close"]
            volumes[f"{ticker}/USDT"] = df["volume"] * df["close"]
        except:
            pass
    closes = pd.DataFrame(closes).sort_index().dropna(how="all")
    volumes = pd.DataFrame(volumes).sort_index().dropna(how="all")
    return closes, volumes


def _permutation_entropy(x, m=3):
    n = len(x)
    if n < m + 1:
        return np.nan
    patterns = []
    for i in range(n - m + 1):
        pattern = tuple(np.argsort(x[i:i+m]))
        patterns.append(pattern)
    c = Counter(patterns)
    total = sum(c.values())
    probs = np.array([v / total for v in c.values()])
    return -np.sum(probs * np.log2(probs + 1e-15))


def _approx_entropy(x, m=2, r_mult=0.2):
    n = len(x)
    if n < m + 2:
        return np.nan
    r = r_mult * np.std(x)
    if r < 1e-10:
        return 0.0

    def phi(m_val):
        patterns = np.array([x[i:i+m_val] for i in range(n - m_val + 1)])
        count = 0
        total = len(patterns)
        for i in range(total):
            dists = np.max(np.abs(patterns - patterns[i]), axis=1)
            count += np.sum(dists <= r)
        return np.log(count / total / total + 1e-15)

    return abs(phi(m) - phi(m + 1))


def _lempel_ziv(s):
    n = len(s)
    if n == 0:
        return 0
    complexity = 1
    l = 1
    k = 1
    k_max = 1
    while l + k <= n:
        if s[l + k - 1] == s[k - 1]:
            k += 1
        else:
            k_max = max(k_max, k)
            k = 1
            if k_max > l:
                complexity += 1
                l += k_max
                k_max = 1
            else:
                complexity += 1
                l += 1
                k_max = 1
    if k > 1:
        complexity += 1
    norm = n / (np.log2(n) + 1e-10) if n > 1 else 1
    return complexity / norm


def _spectral_entropy(x):
    n = len(x)
    if n < 8:
        return np.nan
    fft = np.fft.rfft(x - np.mean(x))
    psd = np.abs(fft) ** 2
    psd = psd / (np.sum(psd) + 1e-15)
    psd = psd[psd > 0]
    return -np.sum(psd * np.log2(psd + 1e-15)) / np.log2(len(psd) + 1e-15)


def _dispersion_entropy(x, c=3, m=2):
    n = len(x)
    if n < m + 1:
        return np.nan
    from scipy.stats import norm as norm_dist
    z = (x - np.mean(x)) / (np.std(x) + 1e-10)
    classes = np.clip(np.floor(norm_dist.cdf(z) * c).astype(int), 0, c - 1)
    patterns = []
    for i in range(n - m + 1):
        patterns.append(tuple(classes[i:i+m]))
    cnt = Counter(patterns)
    total = sum(cnt.values())
    probs = np.array([v / total for v in cnt.values()])
    max_ent = np.log2(c ** m)
    return -np.sum(probs * np.log2(probs + 1e-15)) / max_ent if max_ent > 0 else 0


def compute_signals(closes, volumes):
    returns = closes.pct_change()
    signals = {}
    W = 20

    # H-1220: Permutation Entropy
    pe = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            if np.sum(np.isfinite(rv)) >= 10:
                out[i] = _permutation_entropy(rv[np.isfinite(rv)], m=3)
        pe[col] = out
    signals["perm_entropy"] = pe

    # H-1221: Approximate Entropy
    ae = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() >= 10:
                out[i] = _approx_entropy(rv[mask], m=2, r_mult=0.2)
        ae[col] = out
    signals["approx_entropy"] = ae

    # H-1222: Spectral Entropy
    se = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() >= 10:
                out[i] = _spectral_entropy(rv[mask])
        se[col] = out
    signals["spectral_entropy"] = se

    # H-1223: Lempel-Ziv Complexity
    lz = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() >= 10:
                signs = (rv[mask] > 0).astype(int).tolist()
                out[i] = _lempel_ziv(signs)
        lz[col] = out
    signals["lz_complexity"] = lz

    # H-1224: Dispersion Entropy
    de = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() >= 10:
                out[i] = _dispersion_entropy(rv[mask], c=3, m=2)
        de[col] = out
    signals["dispersion_entropy"] = de

    # H-1225: Autocorrelation Decay Rate
    acf_decay = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() >= 10:
                rv_c = rv[mask] - np.mean(rv[mask])
                var = np.var(rv_c)
                if var > 1e-15:
                    acf1 = np.mean(rv_c[:-1] * rv_c[1:]) / var
                    acf2 = np.mean(rv_c[:-2] * rv_c[2:]) / var if len(rv_c) > 2 else 0
                    out[i] = abs(acf1) + abs(acf2)
        acf_decay[col] = out
    signals["acf_decay"] = acf_decay

    # H-1226: Permutation Entropy Change (PE_10d - PE_20d)
    pe_change = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv20 = r[i-W:i]
            rv10 = r[i-10:i]
            m20 = np.isfinite(rv20)
            m10 = np.isfinite(rv10)
            if m20.sum() >= 10 and m10.sum() >= 6:
                pe20 = _permutation_entropy(rv20[m20], m=3)
                pe10 = _permutation_entropy(rv10[m10], m=3)
                if np.isfinite(pe20) and np.isfinite(pe10):
                    out[i] = pe10 - pe20
        pe_change[col] = out
    signals["pe_change"] = pe_change

    # H-1227: Multi-Scale Entropy Ratio (coarse-grained PE / fine PE)
    mse_ratio = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for col in closes.columns:
        r = returns[col].values
        out = np.full(len(r), np.nan)
        for i in range(W, len(r)):
            rv = r[i-W:i]
            mask = np.isfinite(rv)
            if mask.sum() >= 12:
                rv_fine = rv[mask]
                rv_coarse = (rv_fine[::2][:len(rv_fine)//2] + rv_fine[1::2][:len(rv_fine)//2]) / 2
                pe_fine = _permutation_entropy(rv_fine, m=3)
                pe_coarse = _permutation_entropy(rv_coarse, m=3) if len(rv_coarse) >= 4 else np.nan
                if np.isfinite(pe_fine) and np.isfinite(pe_coarse) and pe_fine > 0:
                    out[i] = pe_coarse / pe_fine
        mse_ratio[col] = out
    signals["mse_ratio"] = mse_ratio

    return signals


def xs_backtest(closes, signal_df, lookback, rebal_days, n_ls, direction="high_long"):
    returns = closes.pct_change()
    slippage = SLIPPAGE_BPS / 10_000
    warmup = lookback + 5
    positions = {}
    days_since = rebal_days
    pnl_daily = []

    for i in range(warmup, len(closes)):
        days_since += 1
        if days_since >= rebal_days:
            sig_row = signal_df.iloc[i - 1]
            sig_row = sig_row.dropna()
            if len(sig_row) < 2 * n_ls:
                pnl_daily.append(0)
                continue
            if direction == "high_long":
                ranked = sig_row.sort_values(ascending=False)
            else:
                ranked = sig_row.sort_values(ascending=True)
            longs = set(ranked.index[:n_ls])
            shorts = set(ranked.index[-n_ls:])
            old_syms = set(positions.keys())
            new_syms = longs | shorts
            changed = old_syms.symmetric_difference(new_syms)
            fee_cost = len(changed) * FEE_RATE / (2 * n_ls)
            slip_cost = len(changed) * slippage / (2 * n_ls)
            positions = {}
            for sym in longs:
                positions[sym] = 1.0 / n_ls
            for sym in shorts:
                positions[sym] = -1.0 / n_ls
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
    return np.array(pnl_daily)


def compute_sharpe(pnl, ann_factor=365):
    if len(pnl) < 30 or np.std(pnl) == 0:
        return 0
    return np.mean(pnl) / np.std(pnl) * np.sqrt(ann_factor)


def compute_metrics(pnl):
    if len(pnl) < 30:
        return {"sharpe": 0, "annual_ret": 0, "max_dd": 0}
    sharpe = compute_sharpe(pnl)
    cum = np.cumsum(pnl)
    annual_ret = np.mean(pnl) * 365
    running_max = np.maximum.accumulate(cum)
    dd = cum - running_max
    max_dd = np.min(dd) if len(dd) > 0 else 0
    return {"sharpe": round(sharpe, 3), "annual_ret": round(annual_ret * 100, 1),
            "max_dd": round(max_dd * 100, 1)}


def walk_forward(closes, signal_df, lookback, rebal, n_ls, direction,
                 n_folds=5, test_days=120):
    results = []
    for fold in range(n_folds):
        test_end = len(closes) - fold * test_days
        test_start = test_end - test_days
        if test_start < 200 + lookback + 5:
            break
        c_test = closes.iloc[test_start - lookback - 5:test_end]
        s_test = signal_df.iloc[test_start - lookback - 5:test_end]
        pnl = xs_backtest(c_test, s_test, lookback, rebal, n_ls, direction)
        sh = compute_sharpe(pnl)
        results.append(sh)
    return results


def split_half_test(pnl):
    if len(pnl) < 60:
        return 0, 0, 1.0
    t_stat, p_val = stats.ttest_1samp(pnl, 0)
    mid = len(pnl) // 2
    return compute_sharpe(pnl[:mid]), compute_sharpe(pnl[mid:]), p_val


def h012_correlation(closes, signal_df, lookback, rebal, n_ls, direction):
    pnl_test = xs_backtest(closes, signal_df, lookback, rebal, n_ls, direction)
    ret60 = closes.pct_change(60)
    pnl_h012 = xs_backtest(closes, ret60, 60, 5, 4, "high_long")
    mn = min(len(pnl_test), len(pnl_h012))
    if mn < 30:
        return 0
    return round(np.corrcoef(pnl_test[:mn], pnl_h012[:mn])[0, 1], 3)


def run_signal(name, signal_df, closes, lookback, directions, n_ls_list=[4],
               rebal_list=[5, 7]):
    common_idx = closes.index.intersection(signal_df.index)
    common_cols = [c for c in closes.columns if c in signal_df.columns]
    if len(common_cols) < 8 or len(common_idx) < 200:
        print(f"  {name}: Insufficient data — SKIP")
        return None
    closes_c = closes[common_cols].loc[common_idx]
    signal_c = signal_df[common_cols].loc[common_idx]

    best = {"sharpe": -999}
    all_positive = 0
    all_total = 0
    for direction in directions:
        for n_ls in n_ls_list:
            for rebal in rebal_list:
                pnl = xs_backtest(closes_c, signal_c, lookback, rebal, n_ls, direction)
                m = compute_metrics(pnl)
                all_total += 1
                if m["sharpe"] > 0:
                    all_positive += 1
                if m["sharpe"] > best.get("sharpe", -999):
                    best = {**m, "direction": direction, "n_ls": n_ls, "rebal": rebal,
                            "pnl": pnl, "closes_c": closes_c, "signal_c": signal_c}
    is_pct = f"{100*all_positive//all_total}%" if all_total > 0 else "N/A"
    if best["sharpe"] <= 0:
        print(f"  {name}: IS {is_pct} ({all_positive}/{all_total} positive) — SKIP")
        return None
    pnl = best["pnl"]
    wf = walk_forward(best["closes_c"], best["signal_c"], lookback, best["rebal"],
                      best["n_ls"], best["direction"])
    sh1, sh2, p_val = split_half_test(pnl)
    corr = h012_correlation(best["closes_c"], best["signal_c"], lookback, best["rebal"],
                            best["n_ls"], best["direction"])
    wf_pos = sum(1 for x in wf if x > 0)
    print(f"  {name}: IS Sharpe {best['sharpe']:.3f} | Ann {best['annual_ret']:.1f}% | DD {best['max_dd']:.1f}% | "
          f"Dir={best['direction']} | IS {is_pct} ({all_positive}/{all_total}) | "
          f"WF {wf_pos}/{len(wf)} {[round(x,2) for x in wf]} | SH {sh1:.3f}/{sh2:.3f} p={p_val:.3f} | "
          f"H012 corr {corr:.3f} | N={len(pnl)}")
    return {
        "sharpe": best["sharpe"], "annual_ret": best["annual_ret"],
        "max_dd": best["max_dd"], "direction": best["direction"],
        "n_ls": best["n_ls"], "rebal": best["rebal"],
        "wf": wf, "wf_pos": wf_pos, "wf_total": len(wf),
        "sh1": sh1, "sh2": sh2, "p_val": round(p_val, 4),
        "h012_corr": corr, "n_bars": len(pnl),
        "is_positive_pct": is_pct
    }


def main():
    print("Loading data...")
    closes, volumes = load_daily()
    print(f"Loaded {len(closes)} bars, {len(closes.columns)} assets")
    print()

    print("Computing signals...")
    signals = compute_signals(closes, volumes)
    print(f"Got {len(signals)} signal types")
    print()

    feature_map = {
        "H-1220": ("perm_entropy", "Permutation Entropy (ordinal pattern complexity)"),
        "H-1221": ("approx_entropy", "Approximate Entropy (regularity of returns)"),
        "H-1222": ("spectral_entropy", "Spectral Entropy (frequency domain randomness)"),
        "H-1223": ("lz_complexity", "Lempel-Ziv Complexity (sign sequence compressibility)"),
        "H-1224": ("dispersion_entropy", "Dispersion Entropy (class-based Shannon entropy)"),
        "H-1225": ("acf_decay", "Autocorrelation Decay (ACF structure persistence)"),
        "H-1226": ("pe_change", "Permutation Entropy Change (delta PE 10d vs 20d)"),
        "H-1227": ("mse_ratio", "Multi-Scale Entropy Ratio (coarse/fine PE)"),
    }

    results = {}
    lookback = 30

    for hyp_id, (sig_name, desc) in feature_map.items():
        print(f"\n{hyp_id}: {desc}")
        sig_df = signals[sig_name]
        r = run_signal(hyp_id, sig_df, closes, lookback,
                       ["high_long", "low_long"], [3, 4], [3, 5, 7])
        if r:
            results[hyp_id] = r

    print(f"\n{'='*80}")
    print(f"BATCH SUMMARY: {len(results)}/{8} signals with positive IS Sharpe")
    for name, r in sorted(results.items(), key=lambda x: -x[1]["sharpe"]):
        status = "CONFIRMED" if r["wf_pos"] >= max(2, r["wf_total"] * 0.5) and r["p_val"] < 0.15 else "BORDERLINE" if r["wf_pos"] >= 2 else "REJECTED"
        print(f"  {name}: Sharpe {r['sharpe']:.3f} | WF {r['wf_pos']}/{r['wf_total']} | p={r['p_val']:.3f} | "
              f"corr {r['h012_corr']:.3f} | SH {r['sh1']:.2f}/{r['sh2']:.2f} | {status}")


if __name__ == "__main__":
    main()
