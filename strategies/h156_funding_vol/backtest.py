"""
H-156: Funding Rate Volatility Factor (Cross-Sectional)

For each asset, compute the rolling standard deviation of funding rates.

High funding vol → speculative, uncertain, frequent regime flips.
Low funding vol → stable carry, predictable positioning.

Cross-sectional: tested both directions —
  stable_long: LONG stable-funding assets (predictability premium)
  volatile_long: LONG volatile-funding assets (risk premium)
"""

import json
import sys
import time
from pathlib import Path
from itertools import product
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE",
    "AVAX", "LINK", "ADA", "DOT", "NEAR",
    "OP", "ARB", "ATOM", "SUI",
]

FEE_RATE = 0.001
INITIAL_CAPITAL = 10_000.0

# Funding rate vol windows (in days; each day has 3 funding settlements)
WINDOWS = [7, 14, 21, 30]
REBAL_FREQS = [5, 7, 10, 14]
N_POSITIONS = [3, 4, 5]

WF_FOLDS = 6


def fetch_all_data(limit=1100):
    import ccxt
    exchange = ccxt.bybit({
        "enableRateLimit": True,
        "options": {"defaultType": "linear"},
    })
    print(f"Fetching {len(ASSETS)} assets × {limit} daily bars from Bybit...")
    daily = {}
    for sym in ASSETS:
        symbol = f"{sym}/USDT:USDT"
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=limit)
            if not ohlcv:
                symbol = f"{sym}/USDT"
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=limit)
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df = df.set_index("timestamp").sort_index()
            df = df[~df.index.duplicated(keep="last")]
            daily[sym] = df
            print(f"  {sym}: {len(df)} bars  ({df.index[0].date()} → {df.index[-1].date()})")
            time.sleep(0.2)
        except Exception as e:
            print(f"  {sym}: FAILED — {e}")
    return daily


def fetch_funding_rates():
    """Fetch historical funding rates for all assets via Bybit API."""
    from pybit.unified_trading import HTTP
    session = HTTP()

    print(f"\nFetching funding rate history for {len(ASSETS)} assets...")
    funding = {}

    for sym in ASSETS:
        symbol = f"{sym}USDT"
        all_rates = []
        end_time = int(datetime.now(timezone.utc).timestamp() * 1000)

        # Fetch in batches (max 200 per call)
        for _ in range(20):  # up to 4000 records (~1333 days)
            try:
                resp = session.get_funding_rate_history(
                    category="linear",
                    symbol=symbol,
                    endTime=end_time,
                    limit=200,
                )
                rows = resp["result"]["list"]
                if not rows:
                    break
                for r in rows:
                    all_rates.append({
                        "timestamp": pd.Timestamp(int(r["fundingRateTimestamp"]), unit="ms", tz="UTC"),
                        "rate": float(r["fundingRate"]),
                    })
                end_time = int(rows[-1]["fundingRateTimestamp"]) - 1
                time.sleep(0.1)
            except Exception as e:
                print(f"  {sym}: funding fetch error — {e}")
                break

        if all_rates:
            df = pd.DataFrame(all_rates).sort_values("timestamp").set_index("timestamp")
            df = df[~df.index.duplicated(keep="last")]
            # Resample to daily: take std of funding rates within each day
            daily_rate = df["rate"].resample("1D").agg(["mean", "std", "count"])
            funding[sym] = daily_rate
            print(f"  {sym}: {len(df)} funding records, {len(daily_rate)} daily")
        else:
            print(f"  {sym}: no funding data")

    return funding


def align_data(daily):
    dates = None
    for sym, df in daily.items():
        idx = df.index
        if dates is None:
            dates = idx
        else:
            dates = dates.intersection(idx)
    dates = dates.sort_values()
    print(f"\nCommon date range: {dates[0].date()} → {dates[-1].date()}  ({len(dates)} days)")
    aligned = {}
    for sym, df in daily.items():
        aligned[sym] = df.reindex(dates)
    return aligned, dates


def compute_factor(funding_daily_means, dates, window):
    """
    For each asset on each day, compute rolling std of daily mean funding rates
    over the past `window` days.
    """
    syms = list(funding_daily_means.keys())
    factor = pd.DataFrame(np.nan, index=dates, columns=syms)

    for sym in syms:
        if sym not in funding_daily_means:
            continue
        fr = funding_daily_means[sym].reindex(dates)
        factor[sym] = fr.rolling(window, min_periods=window // 2).std()

    return factor


def build_returns(aligned, dates):
    syms = list(aligned.keys())
    ret = pd.DataFrame(np.nan, index=dates, columns=syms)
    for sym in syms:
        prices = aligned[sym]["close"]
        ret[sym] = prices.pct_change()
    return ret


def run_strategy(factor, ret_matrix, rebal_freq, n_pos, direction="stable_long", fee_rate=FEE_RATE):
    dates = factor.index
    n = len(dates)
    syms = factor.columns.tolist()
    portfolio_returns = pd.Series(0.0, index=dates)
    current_weights = pd.Series(0.0, index=syms)
    rebal_day = 0

    for i in range(1, n):
        if rebal_day == 0:
            f_row = factor.iloc[i]
            valid = f_row.dropna()
            if len(valid) >= 2 * n_pos:
                ranked = valid.rank(ascending=True)
                if direction == "stable_long":
                    # LONG lowest vol (stable), SHORT highest vol (volatile)
                    long_syms = ranked.nsmallest(n_pos).index.tolist()
                    short_syms = ranked.nlargest(n_pos).index.tolist()
                else:
                    # LONG highest vol, SHORT lowest vol
                    long_syms = ranked.nlargest(n_pos).index.tolist()
                    short_syms = ranked.nsmallest(n_pos).index.tolist()

                new_weights = pd.Series(0.0, index=syms)
                for s in long_syms:
                    new_weights[s] = 0.5 / n_pos
                for s in short_syms:
                    new_weights[s] = -0.5 / n_pos

                turnover = (new_weights - current_weights).abs().sum()
                tc = turnover * fee_rate
                current_weights = new_weights
            else:
                tc = 0.0
        else:
            tc = 0.0

        day_ret = ret_matrix.iloc[i]
        port_ret = (current_weights * day_ret).sum() - tc
        portfolio_returns.iloc[i] = port_ret
        rebal_day = (rebal_day + 1) % rebal_freq

    return portfolio_returns


def sharpe(rets, freq=252):
    r = rets.dropna()
    if len(r) < 30 or r.std() == 0:
        return np.nan
    return (r.mean() / r.std()) * np.sqrt(freq)


def annual_ret(rets):
    r = rets.dropna()
    if len(r) < 2:
        return np.nan
    total = (1 + r).prod()
    years = len(r) / 252
    return total ** (1 / years) - 1 if years > 0 else np.nan


def max_dd(rets):
    r = rets.dropna()
    eq = (1 + r).cumprod()
    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max
    return dd.min()


def walk_forward(funding_daily_means, dates, ret_matrix, best_window, best_rebal, best_n, direction):
    n = len(dates)
    fold_size = n // WF_FOLDS
    fold_sharpes = []
    for fold in range(WF_FOLDS):
        test_start = fold * fold_size
        test_end = test_start + fold_size if fold < WF_FOLDS - 1 else n
        test_dates = dates[test_start:test_end]
        test_factor = compute_factor(funding_daily_means, test_dates, best_window)
        test_ret = ret_matrix.reindex(test_dates)
        rets = run_strategy(test_factor, test_ret, best_rebal, best_n, direction)
        s = sharpe(rets)
        fold_sharpes.append(s)
        print(f"  Fold {fold + 1}: {test_dates[0].date()} → {test_dates[-1].date()}  Sharpe={s:.3f}")
    return fold_sharpes


def split_half(funding_daily_means, dates, ret_matrix, best_window, best_rebal, best_n, direction):
    mid = len(dates) // 2
    results = {}
    for label, d in [("H1", dates[:mid]), ("H2", dates[mid:])]:
        f = compute_factor(funding_daily_means, d, best_window)
        r = ret_matrix.reindex(d)
        rets = run_strategy(f, r, best_rebal, best_n, direction)
        results[label] = {
            "sharpe": sharpe(rets),
            "annual_ret": annual_ret(rets),
            "max_dd": max_dd(rets),
            "days": len(d),
        }
        print(f"  {label}: {d[0].date()} → {d[-1].date()} Sharpe={results[label]['sharpe']:.3f}")
    return results


if __name__ == "__main__":
    daily = fetch_all_data()
    aligned, dates = align_data(daily)
    ret_matrix = build_returns(aligned, dates)

    # Fetch funding rate history
    funding = fetch_funding_rates()

    # Build daily mean funding rate series aligned to our dates
    funding_daily_means = {}
    for sym in ASSETS:
        if sym in funding:
            funding_daily_means[sym] = funding[sym]["mean"].reindex(dates)

    print(f"\nFunding data available for: {list(funding_daily_means.keys())}")

    print(f"\n{'='*70}")
    print("PHASE 1: Full parameter sweep (IS) — stable_long direction")
    print(f"{'='*70}")

    all_results = []
    for win in WINDOWS:
        print(f"  Computing factor for window={win}...")
        factor = compute_factor(funding_daily_means, dates, win)
        for rebal, n_pos in product(REBAL_FREQS, N_POSITIONS):
            rets = run_strategy(factor, ret_matrix, rebal, n_pos, "stable_long")
            s = sharpe(rets)
            ar = annual_ret(rets)
            dd = max_dd(rets)
            all_results.append({
                "window": win, "rebal": rebal, "n_pos": n_pos,
                "sharpe": round(s, 3) if not np.isnan(s) else None,
                "annual_ret": round(ar, 4) if not np.isnan(ar) else None,
                "max_dd": round(dd, 4) if not np.isnan(dd) else None,
            })

    positive = sum(1 for r in all_results if r["sharpe"] and r["sharpe"] > 0)
    total = len(all_results)
    mean_sharpe = np.mean([r["sharpe"] for r in all_results if r["sharpe"] is not None])
    print(f"\nStable-long: {positive}/{total} positive ({positive/total*100:.1f}%)")
    print(f"Mean Sharpe: {mean_sharpe:.3f}")

    # Test reverse direction (volatile_long)
    print(f"\nTesting REVERSE (volatile_long):")
    rev_results = []
    for win in WINDOWS:
        factor = compute_factor(funding_daily_means, dates, win)
        for rebal, n_pos in product(REBAL_FREQS, N_POSITIONS):
            rets = run_strategy(factor, ret_matrix, rebal, n_pos, "volatile_long")
            s = sharpe(rets)
            rev_results.append({"sharpe": round(s, 3) if not np.isnan(s) else None})

    rev_positive = sum(1 for r in rev_results if r["sharpe"] and r["sharpe"] > 0)
    rev_mean = np.mean([r["sharpe"] for r in rev_results if r["sharpe"] is not None])
    print(f"Volatile-long: {rev_positive}/{total} positive ({rev_positive/total*100:.1f}%), mean={rev_mean:.3f}")

    if rev_mean > mean_sharpe:
        print("*** Volatile-long direction is better ***")
        direction = "volatile_long"
        use_positive = rev_positive
        use_mean = rev_mean
    else:
        direction = "stable_long"
        use_positive = positive
        use_mean = mean_sharpe

    sorted_results = sorted(all_results, key=lambda x: x["sharpe"] or -999, reverse=True)
    print(f"\nTop 5 (stable_long):")
    for r in sorted_results[:5]:
        print(f"  W{r['window']}_R{r['rebal']}_N{r['n_pos']}: Sharpe={r['sharpe']}, Annual={r['annual_ret']}, DD={r['max_dd']}")

    best = sorted_results[0]
    bw, br, bn = best["window"], best["rebal"], best["n_pos"]
    print(f"\nBest params: W{bw}_R{br}_N{bn} (Sharpe={best['sharpe']})")

    print(f"\n{'='*70}")
    print("PHASE 2: Walk-Forward Validation")
    print(f"{'='*70}")
    wf = walk_forward(funding_daily_means, dates, ret_matrix, bw, br, bn, direction)
    wf_pos = sum(1 for s in wf if s > 0)
    wf_mean = np.mean(wf)
    print(f"WF: {wf_pos}/{WF_FOLDS} positive, mean OOS={wf_mean:.3f}")

    print(f"\n{'='*70}")
    print("PHASE 3: Split-Half Stability")
    print(f"{'='*70}")
    sh = split_half(funding_daily_means, dates, ret_matrix, bw, br, bn, direction)

    print(f"\n{'='*70}")
    print("PHASE 4: Correlation with H-012 and H-053")
    print(f"{'='*70}")
    syms = list(aligned.keys())

    # H-012 momentum returns
    mom_factor = pd.DataFrame(np.nan, index=dates, columns=syms)
    for sym in syms:
        prices = aligned[sym]["close"]
        mom_factor[sym] = prices.pct_change(60)
    mom_rets = run_strategy(mom_factor, ret_matrix, 5, 4, "stable_long")

    # Our returns
    our_factor = compute_factor(funding_daily_means, dates, bw)
    our_rets = run_strategy(our_factor, ret_matrix, br, bn, direction)
    corr_mom = our_rets.corr(mom_rets)
    print(f"  Correlation with H-012 (momentum): {corr_mom:.3f}")

    # H-053 funding XS returns (contrarian: short high funding, long low funding)
    funding_level_factor = pd.DataFrame(np.nan, index=dates, columns=syms)
    for sym in syms:
        if sym in funding_daily_means:
            funding_level_factor[sym] = funding_daily_means[sym].rolling(3, min_periods=1).mean()
    fund_neg = -funding_level_factor  # contrarian: long low funding
    fund_rets = run_strategy(fund_neg, ret_matrix, 10, 4, "stable_long")
    corr_fund = our_rets.corr(fund_rets)
    print(f"  Correlation with H-053 (funding XS level): {corr_fund:.3f}")

    output = {
        "hypothesis": "H-156",
        "name": "Funding Rate Volatility Factor",
        "direction": direction,
        "is_positive_pct": use_positive / total,
        "is_mean_sharpe": round(use_mean, 3),
        "best_params": {"window": bw, "rebal": br, "n_pos": bn},
        "best_sharpe": best["sharpe"],
        "wf_folds_positive": wf_pos,
        "wf_mean_oos": round(wf_mean, 3),
        "split_half": {k: {kk: round(vv, 3) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in sh.items()},
        "h012_corr": round(corr_mom, 3),
        "h053_corr": round(corr_fund, 3),
        "param_results": all_results,
        "total_param_configs": total,
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Direction: {direction}")
    print(f"IS: {use_positive}/{total} positive ({use_positive/total*100:.1f}%), mean={use_mean:.3f}")
    print(f"WF: {wf_pos}/{WF_FOLDS} positive, mean OOS={wf_mean:.3f}")
    print(f"Split-half: H1={sh['H1']['sharpe']:.3f}, H2={sh['H2']['sharpe']:.3f}")
    print(f"H-012 corr: {corr_mom:.3f}, H-053 corr: {corr_fund:.3f}")
