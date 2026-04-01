#!/usr/bin/env python3
"""
H-172: Hurst Exponent Factor (Cross-Sectional, R/S Method)

Rank 14 crypto perpetual futures by rolling Hurst exponent.
Direction "trending_long":  long top-N (H > 0.5 = trending), short bottom-N (H < 0.5 = mean-reverting).
Direction "meanrev_long":   opposite — long bottom-N, short top-N.

R/S estimation uses multiple sub-period sizes: [n//8, n//4, n//2, n].
Log-log OLS slope gives the Hurst exponent.

Parameter grid (60 combos):
  LB (lookback)  : [20, 30, 40, 60, 80]
  R  (rebalance) : [3, 5, 7]
  N  (positions) : [3, 4]
  direction      : ["trending_long", "meanrev_long"]
  => 5 × 3 × 2 × 2 = 60

Data: 14 USDT perps, 1D bars (resampled from 1h cache), ~1064+ bars.
Fee: 0.1% round-trip per trade.
"""

import sys
import json
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

# ── Constants ──────────────────────────────────────────────────────────────────
ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
    "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT", "NEAR/USDT",
    "OP/USDT", "ARB/USDT", "ATOM/USDT", "SUI/USDT",
]

FEE_RATE  = 0.001          # 10 bps (Bybit taker)
LIMIT_DAYS = 1100          # fetch enough for ~1064+ daily bars

LOOKBACKS   = [20, 30, 40, 60, 80]
REBAL_FREQS = [3, 5, 7]
N_SIZES     = [3, 4]
DIRECTIONS  = ["trending_long", "meanrev_long"]

WF_FOLDS    = 6
WF_FOLD_DAYS = 90


# ── Data loading ───────────────────────────────────────────────────────────────

def load_daily() -> pd.DataFrame:
    """Fetch 1h OHLCV and resample to daily close prices for all 14 assets."""
    daily_close = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=LIMIT_DAYS)
            if len(df) < 200:
                print(f"  {sym}: only {len(df)} 1h bars — skipping")
                continue
            daily = resample_to_daily(df)
            daily_close[sym] = daily["close"]
        except Exception as e:
            print(f"  {sym}: fetch failed — {e}")

    closes = pd.DataFrame(daily_close).dropna(how="all").ffill().dropna()
    return closes


# ── Hurst R/S estimation ───────────────────────────────────────────────────────

def hurst_rs(series: np.ndarray) -> float:
    """
    Estimate Hurst exponent via Rescaled Range (R/S) method.
    Uses sub-period sizes [n//8, n//4, n//2, n].
    Returns 0.5 (random-walk default) if insufficient data.
    """
    n = len(series)
    if n < 20:
        return 0.5

    sizes = []
    rs_values = []

    for k in [n // 8, n // 4, n // 2, n]:
        if k < 8:
            continue
        num_periods = n // k
        rs_list = []
        for i in range(num_periods):
            sub = series[i * k:(i + 1) * k]
            mean_sub = np.mean(sub)
            cumdev = np.cumsum(sub - mean_sub)
            R = np.max(cumdev) - np.min(cumdev)
            S = np.std(sub, ddof=1)
            if S > 0:
                rs_list.append(R / S)
        if rs_list:
            sizes.append(k)
            rs_values.append(np.mean(rs_list))

    if len(sizes) < 2:
        return 0.5

    log_sizes = np.log(sizes)
    log_rs = np.log(rs_values)
    slope, _ = np.polyfit(log_sizes, log_rs, 1)
    return float(slope)


# ── Metrics helpers ────────────────────────────────────────────────────────────

def evaluate(rets: pd.Series | None, label: str = "") -> dict | None:
    """Return performance metrics dict or None if insufficient data."""
    if rets is None or len(rets) < 20:
        return None
    ann   = float(rets.mean() * 365)
    vol   = float(rets.std() * np.sqrt(365))
    sharpe = ann / vol if vol > 1e-8 else 0.0
    cum   = (1 + rets).cumprod()
    dd    = float((cum / cum.cummax() - 1).min())
    wr    = float((rets > 0).mean())
    return {
        "label":  label,
        "sharpe": round(sharpe, 3),
        "annual": round(ann * 100, 1),
        "dd":     round(dd * 100, 1),
        "wr":     round(wr * 100, 1),
        "days":   len(rets),
    }


# ── Core backtest ──────────────────────────────────────────────────────────────

def backtest_hurst(
    closes: pd.DataFrame,
    lookback: int,
    rebal_freq: int,
    n: int,
    direction: str = "trending_long",
) -> pd.Series | None:
    """
    Cross-sectional Hurst exponent factor backtest.

    direction="trending_long":  long top-N (highest H, trending), short bottom-N
    direction="meanrev_long":   long bottom-N (lowest H, mean-reverting), short top-N
    """
    returns = closes.pct_change().dropna()
    dates   = returns.index
    warmup  = lookback + 10

    if len(dates) < warmup + 30:
        return None

    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(warmup, len(dates)):
        # Apply today's return to yesterday's weights (t-1 signal, t execution)
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            # Fee: apply on rebalance days only (captured below)
            portfolio_returns.append({"date": dates[i], "return": day_ret})

        # Rebalance
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                price_series = closes[sym].iloc[:i].values
                if len(price_series) < lookback + 2:
                    continue
                # Use log-returns for Hurst estimation
                window_prices = price_series[-(lookback + 1):]
                log_rets = np.diff(np.log(window_prices))
                if len(log_rets) >= 16:
                    h = hurst_rs(log_rets)
                    signals[sym] = h

            if len(signals) >= 2 * n:
                ranked = pd.Series(signals).sort_values(ascending=False)
                if direction == "trending_long":
                    longs  = ranked.index[:n]
                    shorts = ranked.index[-n:]
                else:  # meanrev_long: long lowest H
                    longs  = ranked.index[-n:]
                    shorts = ranked.index[:n]

                new_weights = pd.Series(0.0, index=closes.columns)
                for sym in longs:
                    new_weights[sym] = +1.0 / n
                for sym in shorts:
                    new_weights[sym] = -1.0 / n

                # Fee drag on turnover
                turnover = (new_weights - weights).abs().sum() / 2.0
                fee_drag = turnover * FEE_RATE

                if portfolio_returns:
                    portfolio_returns[-1]["return"] -= fee_drag

                weights = new_weights
                last_rebal = i

    if not portfolio_returns:
        return None

    df = pd.DataFrame(portfolio_returns).set_index("date")
    return df["return"]


# ── Correlation reference strategies ──────────────────────────────────────────

def backtest_h012(closes: pd.DataFrame, lookback: int = 60, rebal_freq: int = 5, n: int = 4) -> pd.Series | None:
    """H-012: Cross-sectional momentum (60d return ranking)."""
    returns = closes.pct_change().dropna()
    dates   = returns.index
    warmup  = lookback + 2

    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_returns.append({"date": dates[i], "return": (returns.iloc[i] * weights).sum()})

        if i - last_rebal >= rebal_freq:
            mom = closes.iloc[i - 1] / closes.iloc[i - 1 - lookback] - 1
            ranked = mom.sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = +1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i

    if not portfolio_returns:
        return None
    return pd.DataFrame(portfolio_returns).set_index("date")["return"]


def backtest_h076(closes: pd.DataFrame, lookback: int = 14, rebal_freq: int = 5, n: int = 4) -> pd.Series | None:
    """H-076: Price efficiency factor (abs net move / sum range)."""
    # Need OHLCV — we only have closes here, so approximate via intraday proxy
    # (skip if no high/low available; fall back to simplified close-only efficiency)
    returns = closes.pct_change().dropna()
    dates   = returns.index
    warmup  = lookback + 2

    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_returns.append({"date": dates[i], "return": (returns.iloc[i] * weights).sum()})

        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                p = closes[sym].iloc[i - lookback:i].values
                if len(p) < lookback:
                    continue
                net = abs(p[-1] - p[0]) / p[0]
                total = sum(abs(p[t] - p[t-1]) / p[t-1] for t in range(1, len(p)))
                if total > 1e-10:
                    signals[sym] = net / total

            if len(signals) >= 2 * n:
                ranked = pd.Series(signals).sort_values(ascending=False)
                weights = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:n]:
                    weights[s] = +1.0 / n
                for s in ranked.index[-n:]:
                    weights[s] = -1.0 / n
                last_rebal = i

    if not portfolio_returns:
        return None
    return pd.DataFrame(portfolio_returns).set_index("date")["return"]


def backtest_h160(closes: pd.DataFrame, lookback: int = 20, rebal_freq: int = 5, n: int = 4) -> pd.Series | None:
    """H-160: Trend-quality factor (efficiency ratio × inverse vol × momentum sign)."""
    returns = closes.pct_change().dropna()
    dates   = returns.index
    warmup  = lookback + 5

    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_returns.append({"date": dates[i], "return": (returns.iloc[i] * weights).sum()})

        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                p = closes[sym].iloc[i - lookback:i].values
                if len(p) < lookback:
                    continue
                net   = abs(p[-1] - p[0]) / p[0]
                total = sum(abs(p[t] - p[t-1]) / p[t-1] for t in range(1, len(p)))
                eff   = net / total if total > 1e-10 else 0.0
                r = np.diff(np.log(p))
                rv  = r.std() if r.std() > 1e-10 else 1.0
                sign = 1.0 if p[-1] > p[0] else -1.0
                signals[sym] = eff * (1.0 / rv) * sign

            if len(signals) >= 2 * n:
                ranked = pd.Series(signals).sort_values(ascending=False)
                weights = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:n]:
                    weights[s] = +1.0 / n
                for s in ranked.index[-n:]:
                    weights[s] = -1.0 / n
                last_rebal = i

    if not portfolio_returns:
        return None
    return pd.DataFrame(portfolio_returns).set_index("date")["return"]


# ── Full validation pipeline ───────────────────────────────────────────────────

def run_param_scan(closes: pd.DataFrame) -> pd.DataFrame:
    """Run 60 param combos across both directions."""
    results = []
    combos = list(product(LOOKBACKS, REBAL_FREQS, N_SIZES, DIRECTIONS))
    print(f"\nRunning {len(combos)} parameter combinations...")

    for lb, rf, n, direction in combos:
        rets = backtest_hurst(closes, lb, rf, n, direction)
        ev = evaluate(rets, f"LB{lb}_R{rf}_N{n}_{direction}")
        if ev:
            ev["lookback"] = lb
            ev["rebal"]    = rf
            ev["n"]        = n
            ev["direction"] = direction
            results.append(ev)

    return pd.DataFrame(results)


def walk_forward_test(closes: pd.DataFrame, lb: int, rf: int, n: int, direction: str) -> list[dict]:
    """6-fold walk-forward, each fold = last WF_FOLD_DAYS days of expanding window."""
    total_days = len(closes)
    wf_results = []

    for fold in range(WF_FOLDS):
        test_end   = total_days - fold * WF_FOLD_DAYS
        test_start = test_end - WF_FOLD_DAYS
        if test_start < lb + 60:
            break

        fold_closes = closes.iloc[:test_end]
        rets = backtest_hurst(fold_closes, lb, rf, n, direction)
        if rets is not None and len(rets) > 10:
            test_rets = rets.iloc[-WF_FOLD_DAYS:]
            ev = evaluate(test_rets, f"fold{fold}")
            if ev:
                wf_results.append(ev)

    return wf_results


def split_half_test(closes: pd.DataFrame, direction: str) -> tuple[float, float]:
    """Return mean Sharpe for first and second half across all param combos."""
    half = len(closes) // 2
    h1_sharpes, h2_sharpes = [], []

    for lb, rf, n in product(LOOKBACKS, REBAL_FREQS, N_SIZES):
        r1 = backtest_hurst(closes.iloc[:half], lb, rf, n, direction)
        r2 = backtest_hurst(closes.iloc[half:], lb, rf, n, direction)
        e1 = evaluate(r1)
        e2 = evaluate(r2)
        if e1 and e2:
            h1_sharpes.append(e1["sharpe"])
            h2_sharpes.append(e2["sharpe"])

    h1_mean = float(np.mean(h1_sharpes)) if h1_sharpes else 0.0
    h2_mean = float(np.mean(h2_sharpes)) if h2_sharpes else 0.0
    return h1_mean, h2_mean


def compute_correlations(closes: pd.DataFrame, best_lb: int, best_rf: int, best_n: int, best_dir: str) -> dict:
    """Compute correlation between best H-172 and H-012, H-076, H-160."""
    rets_h172 = backtest_hurst(closes, best_lb, best_rf, best_n, best_dir)
    rets_h012 = backtest_h012(closes)
    rets_h076 = backtest_h076(closes)
    rets_h160 = backtest_h160(closes)

    corrs = {}
    for name, other in [("H-012", rets_h012), ("H-076", rets_h076), ("H-160", rets_h160)]:
        if rets_h172 is not None and other is not None:
            common = rets_h172.index.intersection(other.index)
            if len(common) >= 30:
                corrs[name] = float(np.corrcoef(rets_h172.loc[common].values,
                                                 other.loc[common].values)[0, 1])
            else:
                corrs[name] = float("nan")
        else:
            corrs[name] = float("nan")
    return corrs


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("H-172: HURST EXPONENT FACTOR (R/S Method)")
    print("=" * 60)

    print("\nLoading data...")
    closes = load_daily()
    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")
    print(f"Date range: {closes.index[0].date()} to {closes.index[-1].date()}")

    # ── 1. Full IS param scan ──
    df = run_param_scan(closes)

    print("\n=== H-172 HURST EXPONENT RESULTS ===")

    summary = {}
    for direction in DIRECTIONS:
        sub = df[df["direction"] == direction]
        n_pos = (sub["sharpe"] > 0).sum()
        n_tot = len(sub)
        pct   = 100 * n_pos / n_tot if n_tot > 0 else 0
        summary[direction] = {
            "n_pos": int(n_pos), "n_tot": int(n_tot), "pct": round(pct, 1),
            "mean_sharpe": round(float(sub["sharpe"].mean()), 3),
        }
        print(f"Direction: {direction} — {n_pos}/{n_tot} positive ({pct:.1f}%)")

    best_row = df.loc[df["sharpe"].idxmax()]
    best_dir  = best_row["direction"]
    best_lb   = int(best_row["lookback"])
    best_rf   = int(best_row["rebal"])
    best_n    = int(best_row["n"])

    print(f"Best: {best_row['label']}  Sharpe={best_row['sharpe']:.3f}  "
          f"Ann={best_row['annual']:.1f}%  DD={best_row['dd']:.1f}%  WR={best_row['wr']:.1f}%")

    print(f"\n--- Top 5 combos ---")
    for _, row in df.nlargest(5, "sharpe").iterrows():
        print(f"  {row['label']:40s}  Sharpe={row['sharpe']:.3f}  "
              f"Ann={row['annual']:.1f}%  DD={row['dd']:.1f}%")

    # ── Check 80% IS threshold ──
    best_dir_pct = summary[best_dir]["pct"]
    run_deep = best_dir_pct >= 80

    if not run_deep:
        print(f"\n** FAIL: best direction {best_dir} has {best_dir_pct:.1f}% positive (need >=80%). REJECTED. **")
        output = {
            "hypothesis": "H-172",
            "name": "Hurst Exponent Factor (R/S)",
            "verdict": "REJECTED",
            "reason": f"IS positive rate {best_dir_pct:.1f}% < 80%",
            "param_scan": summary,
        }
        out_path = Path(__file__).parent / "results.json"
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nResults saved to {out_path}")
        return

    print(f"\n** PASS criterion 1: {best_dir_pct:.1f}% positive (>=80%). Proceeding with deep validation. **")

    # ── 2. Walk-forward (6 folds) ──
    print(f"\n--- Walk-Forward ({WF_FOLDS} folds × {WF_FOLD_DAYS}d, params: LB={best_lb} R={best_rf} N={best_n} dir={best_dir}) ---")
    wf_results = walk_forward_test(closes, best_lb, best_rf, best_n, best_dir)
    for r in wf_results:
        print(f"  {r['label']}: Sharpe {r['sharpe']:.3f}")
    if wf_results:
        wf_sharpes = [r["sharpe"] for r in wf_results]
        n_pos_wf   = sum(1 for s in wf_sharpes if s > 0)
        mean_wf    = float(np.mean(wf_sharpes))
        print(f"WF positive: {n_pos_wf}/{len(wf_results)}, mean OOS Sharpe={mean_wf:.3f}")
        wf_pass = n_pos_wf >= 4
        print(f"WF criterion: {'PASS' if wf_pass else 'FAIL'} (need >=4/6 positive)")
    else:
        n_pos_wf = 0
        mean_wf  = 0.0
        wf_pass  = False
        print("WF: no valid folds")

    # ── 3. Split-half ──
    print(f"\n--- Split-Half (direction={best_dir}) ---")
    h1_mean, h2_mean = split_half_test(closes, best_dir)
    sh_pass = h1_mean > 0 and h2_mean > 0
    print(f"H1 mean Sharpe: {h1_mean:.3f}, H2 mean Sharpe: {h2_mean:.3f}")
    print(f"Split-half criterion: {'PASS' if sh_pass else 'FAIL'}")

    # ── 4. Correlation ──
    print(f"\n--- Correlations (best params) ---")
    corrs = compute_correlations(closes, best_lb, best_rf, best_n, best_dir)
    for name, c in corrs.items():
        print(f"  Corr with {name}: {c:.3f}")
    max_corr = max(abs(v) for v in corrs.values() if not np.isnan(v)) if corrs else 0.0
    corr_pass = max_corr < 0.40
    print(f"Max |corr|: {max_corr:.3f} — {'PASS' if corr_pass else 'FAIL (>0.40)'}")

    # ── Final verdict ──
    criteria_passed = sum([
        best_dir_pct >= 80,
        wf_pass,
        sh_pass,
        corr_pass,
    ])
    print(f"\n--- SUMMARY ---")
    print(f"1. IS positive:   {best_dir_pct:.1f}%  {'PASS' if best_dir_pct >= 80 else 'FAIL'}")
    print(f"2. Walk-forward:  {n_pos_wf}/{len(wf_results) if wf_results else 0}, mean={mean_wf:.3f}  {'PASS' if wf_pass else 'FAIL'}")
    print(f"3. Split-half:    H1={h1_mean:.3f} H2={h2_mean:.3f}  {'PASS' if sh_pass else 'FAIL'}")
    print(f"4. Max corr:      {max_corr:.3f}  {'PASS' if corr_pass else 'FAIL (>0.40)'}")
    print(f"\nScore: {criteria_passed}/4")
    if criteria_passed == 4:
        verdict = "CONFIRMED"
        print("** CONFIRMED — all 4 criteria pass **")
    else:
        verdict = "REJECTED"
        print("** REJECTED **")

    output = {
        "hypothesis": "H-172",
        "name": "Hurst Exponent Factor (R/S)",
        "verdict": verdict,
        "best_params": best_row["label"],
        "best_sharpe": float(best_row["sharpe"]),
        "best_annual": float(best_row["annual"]),
        "best_dd": float(best_row["dd"]),
        "is_positive_rate_best_dir": best_dir_pct,
        "direction_summary": summary,
        "wf_folds_positive": n_pos_wf,
        "wf_folds_total": len(wf_results) if wf_results else 0,
        "wf_mean_oos_sharpe": mean_wf,
        "split_half_h1": h1_mean,
        "split_half_h2": h2_mean,
        "correlations": {k: (round(v, 3) if not np.isnan(v) else None) for k, v in corrs.items()},
        "criteria_passed": criteria_passed,
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
