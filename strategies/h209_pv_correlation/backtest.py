"""
H-209: Price-Volume Correlation Factor
Cross-sectional ranking on rolling correlation between daily returns and
daily volume changes. Captures price-volume coupling dynamics.
"""

import json
import time
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RESULTS_PATH = Path(__file__).parent / "results.json"

ASSETS = [
    "BTC", "ETH", "SOL", "SUI", "XRP", "DOGE",
    "AVAX", "LINK", "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM",
]


def load_data():
    """Load close prices and volumes, compute log-returns and log-volume-changes."""
    closes, volumes = {}, {}
    for asset in ASSETS:
        df = pd.read_parquet(DATA_DIR / f"{asset}_USDT_1d.parquet")
        closes[asset] = df["close"]
        volumes[asset] = df["volume"]
    close_df = pd.DataFrame(closes).ffill().dropna(thresh=len(ASSETS) // 2)
    vol_df = pd.DataFrame(volumes).ffill().dropna(thresh=len(ASSETS) // 2)
    # Align
    idx = close_df.index.intersection(vol_df.index)
    close_df, vol_df = close_df.loc[idx], vol_df.loc[idx]
    log_ret = np.log(close_df / close_df.shift(1))
    log_vol_chg = np.log(vol_df / vol_df.shift(1))
    return log_ret, log_vol_chg


def compute_signal(log_ret, log_vol_chg, lookback):
    """Rolling correlation between returns and volume changes."""
    n_dates = len(log_ret)
    signal = np.full((n_dates, len(ASSETS)), np.nan)
    ret_vals = log_ret.values
    vol_vals = log_vol_chg.values

    for i in range(lookback, n_dates):
        for j in range(len(ASSETS)):
            r = ret_vals[i - lookback:i, j]
            v = vol_vals[i - lookback:i, j]
            mask = ~(np.isnan(r) | np.isnan(v))
            if mask.sum() >= 10:
                signal[i, j] = np.corrcoef(r[mask], v[mask])[0, 1]

    return pd.DataFrame(signal, index=log_ret.index, columns=ASSETS)


def run_backtest(log_ret, signal_df, lookback, rebal_period, n_top, direction):
    dates = log_ret.index
    portfolio_rets, port_dates = [], []
    current_weights = {}
    last_rebal = -999

    for i in range(lookback + 1, len(dates)):
        t = dates[i]
        if i - last_rebal >= rebal_period:
            row = signal_df.iloc[i - 1]
            valid = row.dropna()
            if len(valid) >= 2 * n_top:
                ranked = valid.sort_values(ascending=False)
                top = ranked.index[:n_top].tolist()
                bot = ranked.index[-n_top:].tolist()
                if direction == "pos_corr_long":
                    long_a, short_a = top, bot
                else:
                    long_a, short_a = bot, top
                w = 1.0 / n_top
                current_weights = {a: w for a in long_a}
                current_weights.update({a: -w for a in short_a})
            else:
                current_weights = {}
            last_rebal = i

        day_ret = sum(current_weights.get(a, 0) * log_ret.iloc[i][a]
                      for a in current_weights if not np.isnan(log_ret.iloc[i].get(a, np.nan)))
        if current_weights:
            portfolio_rets.append(day_ret)
            port_dates.append(t)

    return pd.Series(portfolio_rets, index=port_dates)


def run_backtest_slice(log_ret, signal_df, lookback, rebal_period, n_top, direction, start_idx):
    dates = log_ret.index
    portfolio_rets, port_dates = [], []
    current_weights = {}
    last_rebal = -999

    for i in range(lookback + 1, len(dates)):
        t = dates[i]
        if i - last_rebal >= rebal_period:
            row = signal_df.iloc[i - 1]
            valid = row.dropna()
            if len(valid) >= 2 * n_top:
                ranked = valid.sort_values(ascending=False)
                top = ranked.index[:n_top].tolist()
                bot = ranked.index[-n_top:].tolist()
                if direction == "pos_corr_long":
                    long_a, short_a = top, bot
                else:
                    long_a, short_a = bot, top
                w = 1.0 / n_top
                current_weights = {a: w for a in long_a}
                current_weights.update({a: -w for a in short_a})
            else:
                current_weights = {}
            last_rebal = i

        if i >= start_idx:
            day_ret = sum(current_weights.get(a, 0) * log_ret.iloc[i][a]
                          for a in current_weights if not np.isnan(log_ret.iloc[i].get(a, np.nan)))
            if current_weights:
                portfolio_rets.append(day_ret)
                port_dates.append(t)

    return pd.Series(portfolio_rets, index=port_dates)


def sharpe(returns, annualize=365.0):
    if len(returns) < 10: return 0.0
    mu, sigma = returns.mean(), returns.std(ddof=1)
    return float(mu / sigma * np.sqrt(annualize)) if sigma > 0 else 0.0

def max_drawdown(returns):
    cum = (1 + returns).cumprod()
    return float((cum / cum.cummax() - 1).min())

def annual_return(returns):
    if len(returns) < 2: return 0.0
    cum = (1 + returns).prod()
    return float(cum ** (1 / (len(returns) / 365.0)) - 1)


def walk_forward(log_ret, log_vol_chg, lookback, rebal_period, n_top, direction, n_folds=6, fold_days=90):
    total_days = len(log_ret)
    if total_days < lookback + n_folds * fold_days + fold_days:
        return []
    fold_sharpes = []
    for fold in range(n_folds):
        test_end = total_days - fold * fold_days
        test_start = test_end - fold_days
        if test_start <= lookback:
            break
        sig = compute_signal(log_ret.iloc[:test_end], log_vol_chg.iloc[:test_end], lookback)
        rets = run_backtest_slice(log_ret.iloc[:test_end], sig, lookback, rebal_period, n_top, direction, test_start)
        fold_sharpes.append(sharpe(rets))
    return fold_sharpes


def correlation_with_h012(log_ret, signal_df, lookback, rebal_period, n_top, direction):
    """Compute return correlation with H-012 momentum strategy."""
    # Build H-012 returns: 60d momentum, 5d rebal, top/bottom 4
    mom_lb, mom_rp, mom_n = 60, 5, 4
    dates = log_ret.index
    h012_rets, h209_rets, common_dates = [], [], []

    mom_weights = {}
    sig_weights = {}
    mom_last_rebal = -999
    sig_last_rebal = -999

    for i in range(max(lookback, mom_lb) + 1, len(dates)):
        t = dates[i]
        # H-012 momentum
        if i - mom_last_rebal >= mom_rp:
            cum_ret = log_ret.iloc[i-1] - log_ret.iloc[i-1-mom_lb] if i-1-mom_lb >= 0 else pd.Series(dtype=float)
            valid_mom = cum_ret.dropna()
            if len(valid_mom) >= 2 * mom_n:
                ranked = valid_mom.sort_values(ascending=False)
                w = 1.0 / mom_n
                mom_weights = {a: w for a in ranked.index[:mom_n]}
                mom_weights.update({a: -w for a in ranked.index[-mom_n:]})
            mom_last_rebal = i

        # H-209
        if i - sig_last_rebal >= rebal_period:
            row = signal_df.iloc[i-1]
            valid = row.dropna()
            if len(valid) >= 2 * n_top:
                ranked = valid.sort_values(ascending=False)
                top = ranked.index[:n_top].tolist()
                bot = ranked.index[-n_top:].tolist()
                if direction == "pos_corr_long":
                    long_a, short_a = top, bot
                else:
                    long_a, short_a = bot, top
                w = 1.0 / n_top
                sig_weights = {a: w for a in long_a}
                sig_weights.update({a: -w for a in short_a})
            sig_last_rebal = i

        if mom_weights and sig_weights:
            r_mom = sum(mom_weights.get(a, 0) * log_ret.iloc[i].get(a, 0) for a in mom_weights)
            r_sig = sum(sig_weights.get(a, 0) * log_ret.iloc[i].get(a, 0) for a in sig_weights)
            h012_rets.append(r_mom)
            h209_rets.append(r_sig)

    if len(h012_rets) > 30:
        return float(np.corrcoef(h012_rets, h209_rets)[0, 1])
    return None


LOOKBACKS = [10, 20, 30, 60]
REBAL_PERIODS = [3, 5, 7]
N_TOPS = [3, 4]
DIRECTIONS = ["pos_corr_long", "neg_corr_long"]


def main():
    t0 = time.time()
    print("=" * 60)
    print("H-209: Price-Volume Correlation Factor Backtest")
    print("=" * 60)

    log_ret, log_vol_chg = load_data()
    print(f"  Date range: {log_ret.index[0].date()} to {log_ret.index[-1].date()}")
    print(f"  Total days: {len(log_ret)}, Assets: {len(ASSETS)}")

    # Pre-compute signal matrices
    print("\nPre-computing signal matrices...")
    signals = {}
    for lb in LOOKBACKS:
        t1 = time.time()
        signals[lb] = compute_signal(log_ret, log_vol_chg, lb)
        print(f"  LB={lb}: {time.time()-t1:.1f}s")

    # Grid sweep
    combos = list(product(LOOKBACKS, REBAL_PERIODS, N_TOPS, DIRECTIONS))
    print(f"\nRunning {len(combos)} parameter combos...")

    results = []
    for idx, (lb, rp, nt, dr) in enumerate(combos):
        rets = run_backtest(log_ret, signals[lb], lb, rp, nt, dr)
        sp = sharpe(rets)
        results.append({
            "lookback": lb, "rebal_period": rp, "n_top": nt, "direction": dr,
            "sharpe": round(sp, 4), "annual_return": round(annual_return(rets), 4),
            "max_drawdown": round(max_drawdown(rets), 4), "n_days": len(rets),
        })

    sharpes = [r["sharpe"] for r in results]
    positive = sum(s > 0 for s in sharpes)
    hit_rate = positive / len(sharpes)
    best = max(results, key=lambda x: x["sharpe"])
    mean_sharpe = float(np.mean(sharpes))

    dir_pos = [r["sharpe"] for r in results if r["direction"] == "pos_corr_long"]
    dir_neg = [r["sharpe"] for r in results if r["direction"] == "neg_corr_long"]
    mean_pos = float(np.mean(dir_pos))
    mean_neg = float(np.mean(dir_neg))
    dom_direction = "pos_corr_long" if mean_pos >= mean_neg else "neg_corr_long"

    print(f"\n{'='*60}\nIN-SAMPLE RESULTS\n{'='*60}")
    print(f"  Hit rate: {hit_rate:.1%} ({positive}/{len(sharpes)})")
    print(f"  Mean Sharpe: {mean_sharpe:.4f}")
    print(f"  Best: lb={best['lookback']} rp={best['rebal_period']} N={best['n_top']} {best['direction']} Sharpe={best['sharpe']:.4f}")
    print(f"  Best annual: {best['annual_return']:.2%}, MDD: {best['max_drawdown']:.2%}")
    print(f"  Mean pos_corr_long: {mean_pos:.4f}, neg_corr_long: {mean_neg:.4f}")

    top10 = sorted(results, key=lambda x: x["sharpe"], reverse=True)[:10]
    print("\n  Top-10:")
    for r in top10:
        print(f"    lb={r['lookback']} rp={r['rebal_period']} N={r['n_top']} {r['direction'][:7]:>7} S={r['sharpe']:.4f} AR={r['annual_return']:.2%}")

    # Walk-forward
    wf_result = None
    if hit_rate >= 0.80:
        print(f"\n  IS {hit_rate:.1%} >= 80% — running walk-forward...")
        fold_sharpes = walk_forward(log_ret, log_vol_chg, best["lookback"], best["rebal_period"],
                                    best["n_top"], best["direction"])
        wf_positive = sum(s > 0 for s in fold_sharpes)
        wf_mean = float(np.mean(fold_sharpes)) if fold_sharpes else 0
        wf_pass = wf_positive >= 4 and len(fold_sharpes) >= 4
        print(f"  WF folds positive: {wf_positive}/{len(fold_sharpes)}, mean OOS: {wf_mean:.4f}")
        for fi, fs in enumerate(fold_sharpes):
            print(f"    Fold {fi+1}: {fs:.4f} {'✓' if fs > 0 else '✗'}")
        wf_result = {"fold_sharpes": [round(s,4) for s in fold_sharpes],
                     "folds_positive": wf_positive, "folds_total": len(fold_sharpes),
                     "wf_pass": wf_pass, "mean_oos_sharpe": round(wf_mean, 4)}
    else:
        print(f"\n  IS {hit_rate:.1%} < 80% — WF not run.")
        wf_pass = False

    # Split-half + correlation
    split_half = None
    if wf_result and wf_result.get("wf_pass"):
        print("\n  Split-half stability...")
        mid = len(log_ret) // 2
        sig_h1 = compute_signal(log_ret.iloc[:mid], log_vol_chg.iloc[:mid], best["lookback"])
        sig_h2 = compute_signal(log_ret.iloc[mid:], log_vol_chg.iloc[mid:], best["lookback"])
        rets_h1 = run_backtest(log_ret.iloc[:mid], sig_h1, best["lookback"], best["rebal_period"], best["n_top"], best["direction"])
        rets_h2 = run_backtest(log_ret.iloc[mid:], sig_h2, best["lookback"], best["rebal_period"], best["n_top"], best["direction"])
        sh1, sh2 = sharpe(rets_h1), sharpe(rets_h2)
        print(f"  H1: {sh1:.4f}, H2: {sh2:.4f}")

        h012_corr = correlation_with_h012(log_ret, signals[best["lookback"]], best["lookback"],
                                          best["rebal_period"], best["n_top"], best["direction"])
        if h012_corr is not None:
            print(f"  Correlation with H-012: {h012_corr:.3f}")
        split_half = {"h1_sharpe": round(sh1,4), "h2_sharpe": round(sh2,4),
                      "stability_pass": sh1 > 0 and sh2 > 0, "h012_correlation": round(h012_corr,3) if h012_corr else None}

    if hit_rate >= 0.80 and wf_result and wf_result.get("wf_pass"):
        verdict = "CONFIRMED"
    elif hit_rate >= 0.60:
        verdict = "WEAK"
    else:
        verdict = "REJECTED"

    print(f"\n{'='*60}\nVERDICT: {verdict}\n{'='*60}")
    print(f"Runtime: {time.time()-t0:.1f}s")

    output = {
        "hypothesis": "H-209", "title": "Price-Volume Correlation Factor",
        "in_sample": {"hit_rate": round(hit_rate,4), "mean_sharpe": round(mean_sharpe,4),
                      "n_combos": len(results), "best": best, "dom_direction": dom_direction,
                      "mean_pos_corr": round(mean_pos,4), "mean_neg_corr": round(mean_neg,4), "top10": top10},
        "walk_forward": wf_result, "split_half": split_half, "verdict": verdict,
        "runtime_seconds": round(time.time()-t0, 1),
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved to {RESULTS_PATH}")
    return output

if __name__ == "__main__":
    main()
