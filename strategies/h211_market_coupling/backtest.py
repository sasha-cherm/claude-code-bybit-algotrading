"""
H-211: Market Coupling / R² Factor
Cross-sectional ranking on rolling R² of each asset's return vs BTC return.
High R² = tightly coupled to BTC. Low R² = independent mover.
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

ASSETS_ALL = [
    "BTC", "ETH", "SOL", "SUI", "XRP", "DOGE",
    "AVAX", "LINK", "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM",
]
# Exclude BTC from ranking (it's the benchmark), but include its return data
ASSETS_RANK = [a for a in ASSETS_ALL if a != "BTC"]


def load_data():
    """Load close prices, compute log-returns."""
    closes = {}
    for asset in ASSETS_ALL:
        df = pd.read_parquet(DATA_DIR / f"{asset}_USDT_1d.parquet")
        closes[asset] = df["close"]
    close_df = pd.DataFrame(closes).ffill().dropna(thresh=len(ASSETS_ALL) // 2)
    log_ret = np.log(close_df / close_df.shift(1))
    return log_ret


def compute_signal(log_ret, lookback):
    """Rolling R² of each non-BTC asset vs BTC returns."""
    n_dates = len(log_ret)
    n_assets = len(ASSETS_RANK)
    signal = np.full((n_dates, n_assets), np.nan)
    btc_vals = log_ret["BTC"].values
    asset_vals = log_ret[ASSETS_RANK].values

    for i in range(lookback, n_dates):
        btc_window = btc_vals[i - lookback:i]
        btc_valid = ~np.isnan(btc_window)
        for j in range(n_assets):
            asset_window = asset_vals[i - lookback:i, j]
            mask = btc_valid & ~np.isnan(asset_window)
            if mask.sum() >= 10:
                x = btc_window[mask]
                y = asset_window[mask]
                # R² from correlation
                corr = np.corrcoef(x, y)[0, 1]
                signal[i, j] = corr ** 2

    return pd.DataFrame(signal, index=log_ret.index, columns=ASSETS_RANK)


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
                if direction == "high_r2_long":
                    long_a, short_a = top, bot
                else:  # low_r2_long
                    long_a, short_a = bot, top
                w = 1.0 / n_top
                current_weights = {a: w for a in long_a}
                current_weights.update({a: -w for a in short_a})
            else:
                current_weights = {}
            last_rebal = i

        day_ret = sum(current_weights.get(a, 0) * log_ret.iloc[i].get(a, np.nan)
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
                if direction == "high_r2_long":
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
            day_ret = sum(current_weights.get(a, 0) * log_ret.iloc[i].get(a, np.nan)
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


def walk_forward(log_ret, lookback, rebal_period, n_top, direction, n_folds=6, fold_days=90):
    total_days = len(log_ret)
    if total_days < lookback + n_folds * fold_days + fold_days:
        return []
    fold_sharpes = []
    for fold in range(n_folds):
        test_end = total_days - fold * fold_days
        test_start = test_end - fold_days
        if test_start <= lookback:
            break
        sig = compute_signal(log_ret.iloc[:test_end], lookback)
        rets = run_backtest_slice(log_ret.iloc[:test_end], sig, lookback, rebal_period, n_top, direction, test_start)
        fold_sharpes.append(sharpe(rets))
    return fold_sharpes


def correlation_with_h012(log_ret, signal_df, lookback, rebal_period, n_top, direction):
    mom_lb, mom_rp, mom_n = 60, 5, 4
    dates = log_ret.index
    h012_rets, h211_rets = [], []
    mom_weights, sig_weights = {}, {}
    mom_last, sig_last = -999, -999

    for i in range(max(lookback, mom_lb) + 1, len(dates)):
        if i - mom_last >= mom_rp:
            cum_ret = log_ret.iloc[i-1] - log_ret.iloc[max(0, i-1-mom_lb)]
            valid_mom = cum_ret.dropna()
            if len(valid_mom) >= 2 * mom_n:
                ranked = valid_mom.sort_values(ascending=False)
                w = 1.0 / mom_n
                mom_weights = {a: w for a in ranked.index[:mom_n]}
                mom_weights.update({a: -w for a in ranked.index[-mom_n:]})
            mom_last = i

        if i - sig_last >= rebal_period:
            row = signal_df.iloc[i-1]
            valid = row.dropna()
            if len(valid) >= 2 * n_top:
                ranked = valid.sort_values(ascending=False)
                top, bot = ranked.index[:n_top].tolist(), ranked.index[-n_top:].tolist()
                if direction == "high_r2_long":
                    long_a, short_a = top, bot
                else:
                    long_a, short_a = bot, top
                w = 1.0 / n_top
                sig_weights = {a: w for a in long_a}
                sig_weights.update({a: -w for a in short_a})
            sig_last = i

        if mom_weights and sig_weights:
            r_mom = sum(mom_weights.get(a, 0) * log_ret.iloc[i].get(a, 0) for a in mom_weights)
            r_sig = sum(sig_weights.get(a, 0) * log_ret.iloc[i].get(a, 0) for a in sig_weights)
            h012_rets.append(r_mom)
            h211_rets.append(r_sig)

    if len(h012_rets) > 30:
        return float(np.corrcoef(h012_rets, h211_rets)[0, 1])
    return None


LOOKBACKS = [20, 30, 60]
REBAL_PERIODS = [3, 5, 7]
N_TOPS = [3, 4]
DIRECTIONS = ["low_r2_long", "high_r2_long"]


def main():
    t0 = time.time()
    print("=" * 60)
    print("H-211: Market Coupling / R² Factor Backtest")
    print("=" * 60)

    log_ret = load_data()
    print(f"  Date range: {log_ret.index[0].date()} to {log_ret.index[-1].date()}")
    print(f"  Total days: {len(log_ret)}, Assets: {len(ASSETS_ALL)} ({len(ASSETS_RANK)} ranked)")

    print("\nPre-computing signal matrices...")
    signals = {}
    for lb in LOOKBACKS:
        t1 = time.time()
        signals[lb] = compute_signal(log_ret, lb)
        print(f"  LB={lb}: {time.time()-t1:.1f}s")

    combos = list(product(LOOKBACKS, REBAL_PERIODS, N_TOPS, DIRECTIONS))
    print(f"\nRunning {len(combos)} parameter combos...")

    results = []
    for lb, rp, nt, dr in combos:
        rets = run_backtest(log_ret, signals[lb], lb, rp, nt, dr)
        results.append({
            "lookback": lb, "rebal_period": rp, "n_top": nt, "direction": dr,
            "sharpe": round(sharpe(rets), 4), "annual_return": round(annual_return(rets), 4),
            "max_drawdown": round(max_drawdown(rets), 4), "n_days": len(rets),
        })

    sharpes = [r["sharpe"] for r in results]
    positive = sum(s > 0 for s in sharpes)
    hit_rate = positive / len(sharpes)
    best = max(results, key=lambda x: x["sharpe"])
    mean_sharpe = float(np.mean(sharpes))

    dir_lo = [r["sharpe"] for r in results if r["direction"] == "low_r2_long"]
    dir_hi = [r["sharpe"] for r in results if r["direction"] == "high_r2_long"]
    mean_lo, mean_hi = float(np.mean(dir_lo)), float(np.mean(dir_hi))
    dom_direction = "low_r2_long" if mean_lo >= mean_hi else "high_r2_long"

    print(f"\n{'='*60}\nIN-SAMPLE RESULTS\n{'='*60}")
    print(f"  Hit rate: {hit_rate:.1%} ({positive}/{len(sharpes)})")
    print(f"  Mean Sharpe: {mean_sharpe:.4f}")
    print(f"  Best: lb={best['lookback']} rp={best['rebal_period']} N={best['n_top']} {best['direction']} Sharpe={best['sharpe']:.4f}")
    print(f"  Best annual: {best['annual_return']:.2%}, MDD: {best['max_drawdown']:.2%}")
    print(f"  Mean low_r2_long: {mean_lo:.4f}, high_r2_long: {mean_hi:.4f}")

    top10 = sorted(results, key=lambda x: x["sharpe"], reverse=True)[:10]
    print("\n  Top-10:")
    for r in top10:
        print(f"    lb={r['lookback']} rp={r['rebal_period']} N={r['n_top']} {r['direction'][:9]:>9} S={r['sharpe']:.4f} AR={r['annual_return']:.2%}")

    wf_result = None
    if hit_rate >= 0.80:
        print(f"\n  IS {hit_rate:.1%} >= 80% — running walk-forward...")
        fold_sharpes = walk_forward(log_ret, best["lookback"], best["rebal_period"],
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

    split_half = None
    if wf_result and wf_result.get("wf_pass"):
        print("\n  Split-half stability...")
        mid = len(log_ret) // 2
        sig_h1 = compute_signal(log_ret.iloc[:mid], best["lookback"])
        sig_h2 = compute_signal(log_ret.iloc[mid:], best["lookback"])
        rets_h1 = run_backtest(log_ret.iloc[:mid], sig_h1, best["lookback"], best["rebal_period"], best["n_top"], best["direction"])
        rets_h2 = run_backtest(log_ret.iloc[mid:], sig_h2, best["lookback"], best["rebal_period"], best["n_top"], best["direction"])
        sh1, sh2 = sharpe(rets_h1), sharpe(rets_h2)
        print(f"  H1: {sh1:.4f}, H2: {sh2:.4f}")

        h012_corr = correlation_with_h012(log_ret, signals[best["lookback"]], best["lookback"],
                                          best["rebal_period"], best["n_top"], best["direction"])
        if h012_corr is not None:
            print(f"  Correlation with H-012: {h012_corr:.3f}")
        split_half = {"h1_sharpe": round(sh1,4), "h2_sharpe": round(sh2,4),
                      "stability_pass": sh1 > 0 and sh2 > 0,
                      "h012_correlation": round(h012_corr,3) if h012_corr else None}

    if hit_rate >= 0.80 and wf_result and wf_result.get("wf_pass"):
        verdict = "CONFIRMED"
    elif hit_rate >= 0.60:
        verdict = "WEAK"
    else:
        verdict = "REJECTED"

    print(f"\n{'='*60}\nVERDICT: {verdict}\n{'='*60}")
    print(f"Runtime: {time.time()-t0:.1f}s")

    output = {
        "hypothesis": "H-211", "title": "Market Coupling / R-squared Factor",
        "in_sample": {"hit_rate": round(hit_rate,4), "mean_sharpe": round(mean_sharpe,4),
                      "n_combos": len(results), "best": best, "dom_direction": dom_direction,
                      "mean_low_r2": round(mean_lo,4), "mean_high_r2": round(mean_hi,4), "top10": top10},
        "walk_forward": wf_result, "split_half": split_half, "verdict": verdict,
        "runtime_seconds": round(time.time()-t0, 1),
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved to {RESULTS_PATH}")

if __name__ == "__main__":
    main()
