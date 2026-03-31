#!/usr/bin/env python3
"""
H-165: Funding-Premium Interaction Factor (14 Crypto Assets)

Multiply z-scored funding rate × z-scored premium index to create an interaction signal.
When both are extreme in the same direction = maximum crowding → go contrarian.
  high funding + high premium = extreme bullish crowding → SHORT
  low funding + low premium = extreme bearish crowding → LONG

Different from H-052 (premium alone) and H-053 (funding alone): this captures JOINT extreme.
Different from H-150 (OI-funding interaction): uses premium instead of OI.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
DATA_DIR = ROOT / "data"

from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

ASSETS_MAP = {
    "BTC": "BTC/USDT", "ETH": "ETH/USDT", "SOL": "SOL/USDT", "SUI": "SUI/USDT",
    "XRP": "XRP/USDT", "DOGE": "DOGE/USDT", "AVAX": "AVAX/USDT", "LINK": "LINK/USDT",
    "ADA": "ADA/USDT", "DOT": "DOT/USDT", "NEAR": "NEAR/USDT", "OP": "OP/USDT",
    "ARB": "ARB/USDT", "ATOM": "ATOM/USDT",
}
ASSETS = list(ASSETS_MAP.values())


def load_daily_closes():
    daily_close = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=800)
            if len(df) < 200:
                continue
            daily = resample_to_daily(df)
            daily_close[sym] = daily["close"]
        except Exception:
            pass
    result = pd.DataFrame(daily_close).dropna(how="all").ffill().dropna()
    result.index = result.index.tz_localize(None)
    return result


def load_funding_daily():
    """Load cached 8h funding data, resample to daily average."""
    frames = {}
    for short_name, full_name in ASSETS_MAP.items():
        fp = DATA_DIR / f"{short_name}_USDT_USDT_funding.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        s = df["funding_rate"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        daily = s.resample("1D").mean()
        frames[full_name] = daily
    fund = pd.DataFrame(frames).sort_index().dropna(how="all")
    return fund


def load_premium_daily():
    """Load cached daily premium index data."""
    fp = DATA_DIR / "all_assets_premium_daily.parquet"
    if not fp.exists():
        return pd.DataFrame()
    df = pd.read_parquet(fp)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    # Pivot to wide format: columns = asset symbols
    pivoted = df.pivot(index="timestamp", columns="asset", values="close")
    # Rename columns to match full name
    rename = {short: full for short, full in ASSETS_MAP.items()}
    pivoted = pivoted.rename(columns=rename)
    pivoted.index.name = None
    return pivoted.sort_index().dropna(how="all")


def backtest_factor(closes, funding_df, premium_df, fund_lb, prem_lb, rebal_freq, n_long, n_short, direction="contrarian"):
    returns = closes.pct_change().dropna()
    dates = returns.index
    warmup = max(fund_lb, prem_lb) + 10

    # Build aligned date index
    common_dates = sorted(set(closes.index) & set(funding_df.index) & set(premium_df.index))
    if len(common_dates) < warmup + 60:
        return None

    common_assets = [a for a in closes.columns if a in funding_df.columns and a in premium_df.columns]
    if len(common_assets) < n_long + n_short:
        return None

    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=common_assets)

    for i in range(warmup, len(common_dates)):
        date = common_dates[i]
        if date in returns.index and weights.abs().sum() > 0:
            day_ret = (returns.loc[date, common_assets] * weights).sum()
            portfolio_returns.append({"date": date, "return": day_ret})

        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in common_assets:
                # Get rolling windows
                fund_hist = funding_df[sym].loc[:date].dropna()
                prem_hist = premium_df[sym].loc[:date].dropna()

                if len(fund_hist) < fund_lb or len(prem_hist) < prem_lb:
                    continue

                fund_window = fund_hist.iloc[-fund_lb:]
                prem_window = prem_hist.iloc[-prem_lb:]

                f_mean = fund_window.mean()
                f_std = fund_window.std()
                p_mean = prem_window.mean()
                p_std = prem_window.std()

                if f_std < 1e-12 or p_std < 1e-12:
                    continue

                f_z = (fund_window.iloc[-1] - f_mean) / f_std
                p_z = (prem_window.iloc[-1] - p_mean) / p_std

                signals[sym] = f_z * p_z

            if len(signals) >= n_long + n_short:
                ranked = pd.Series(signals).sort_values(ascending=False)
                if direction == "contrarian":
                    longs = ranked.index[-n_long:]
                    shorts = ranked.index[:n_short]
                else:
                    longs = ranked.index[:n_long]
                    shorts = ranked.index[-n_short:]

                weights = pd.Series(0.0, index=common_assets)
                for s in longs:
                    weights[s] = 1.0 / n_long
                for s in shorts:
                    weights[s] = -1.0 / n_short

                last_rebal = i

    if not portfolio_returns:
        return None
    df = pd.DataFrame(portfolio_returns).set_index("date")
    return df["return"]


def evaluate(rets, label=""):
    if rets is None or len(rets) < 30:
        return None
    ann = rets.mean() * 365
    vol = rets.std() * np.sqrt(365)
    sharpe = ann / vol if vol > 1e-8 else 0
    cum = (1 + rets).cumprod()
    dd = (cum / cum.cummax() - 1).min()
    return {"label": label, "sharpe": round(sharpe, 3), "annual": round(ann * 100, 1),
            "dd": round(dd * 100, 1), "days": len(rets)}


def backtest_momentum(closes, lookback=60, rebal_freq=5, n=4):
    returns = closes.pct_change().dropna()
    dates = returns.index
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_returns.append({"date": dates[i], "return": day_ret})

        if i - last_rebal >= rebal_freq:
            mom = closes.iloc[i-1] / closes.iloc[i-1-lookback] - 1
            ranked = mom.sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i

    if not portfolio_returns:
        return None
    df = pd.DataFrame(portfolio_returns).set_index("date")
    return df["return"]


def main():
    print("Loading data...")
    closes = load_daily_closes()
    print(f"Loaded {len(closes.columns)} assets, {len(closes)} daily bars")

    print("Loading funding rate data (cached)...")
    funding_df = load_funding_daily()
    print(f"Funding data: {len(funding_df)} days, {len(funding_df.columns)} assets")
    print(f"Funding range: {funding_df.index[0].date()} to {funding_df.index[-1].date()}")

    print("Loading premium index data (cached)...")
    premium_df = load_premium_daily()
    print(f"Premium data: {len(premium_df)} days, {len(premium_df.columns)} assets")
    print(f"Premium range: {premium_df.index[0].date()} to {premium_df.index[-1].date()}")

    common_assets = [a for a in closes.columns if a in funding_df.columns and a in premium_df.columns]
    print(f"Common assets: {len(common_assets)}")

    # Restrict closes to common assets
    closes = closes[common_assets]

    # Parameter grid
    fund_lbs = [5, 10, 20, 30]
    prem_lbs = [5, 10, 20, 30]
    rebals = [3, 5, 7]
    ns = [3, 4]
    directions = ["contrarian"]

    results = []
    total = len(fund_lbs) * len(prem_lbs) * len(rebals) * len(ns)
    print(f"\nScanning {total} parameter combinations...")

    for fl in fund_lbs:
        for pl in prem_lbs:
            for rf in rebals:
                for n in ns:
                    rets = backtest_factor(closes, funding_df, premium_df, fl, pl, rf, n, n, "contrarian")
                    ev = evaluate(rets, f"FL{fl}_PL{pl}_R{rf}_N{n}")
                    if ev:
                        results.append(ev)

    if not results:
        print("No valid results!")
        return

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    print(f"\n=== PARAM SCAN RESULTS ===")
    print(f"Total configs: {len(df)}")
    print(f"Positive Sharpe: {n_positive}/{len(df)} ({n_positive/len(df)*100:.1f}%)")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"Best: {df.loc[df['sharpe'].idxmax(), 'label']} Sharpe {df['sharpe'].max():.3f}")

    top = df.nlargest(5, "sharpe")
    print("\nTop 5:")
    for _, r in top.iterrows():
        print(f"  {r['label']}: Sharpe {r['sharpe']:.3f}, Ann {r['annual']:.1f}%, DD {r['dd']:.1f}%, {r['days']}d")

    if n_positive / len(df) < 0.80:
        print(f"\nFAIL: Only {n_positive/len(df)*100:.1f}% positive (need >=80%). REJECTED.")
        return

    # Walk-forward on best config
    best = df.loc[df["sharpe"].idxmax()]
    parts = best["label"].split("_")
    fl = int(parts[0][2:])
    pl = int(parts[1][2:])
    rf = int(parts[2][1:])
    n = int(parts[3][1:])

    print(f"\n=== WALK-FORWARD ({best['label']}) ===")
    common_dates = sorted(set(closes.index) & set(funding_df.index) & set(premium_df.index))
    total_days = len(common_dates)
    test_days = 90
    n_folds = 6
    wf_results = []
    for fold in range(n_folds):
        end = total_days - fold * test_days
        start = end - test_days
        if start < max(fl, pl) + 60:
            break
        cutoff_date = common_dates[end - 1]
        test_closes = closes.loc[:cutoff_date]
        test_fund = funding_df.loc[:cutoff_date]
        test_prem = premium_df.loc[:cutoff_date]
        rets = backtest_factor(test_closes, test_fund, test_prem, fl, pl, rf, n, n, "contrarian")
        if rets is not None and len(rets) > 0:
            test_rets = rets.iloc[-test_days:]
            if len(test_rets) > 10:
                ev = evaluate(test_rets, f"fold{fold}")
                if ev:
                    wf_results.append(ev)

    if wf_results:
        for r in wf_results:
            print(f"  {r['label']}: Sharpe {r['sharpe']:.3f}")
        wf_sharpes = [r["sharpe"] for r in wf_results]
        n_pos = sum(1 for s in wf_sharpes if s > 0)
        print(f"WF positive: {n_pos}/{len(wf_results)}, mean OOS: {np.mean(wf_sharpes):.3f}")

    # Split-half
    print(f"\n=== SPLIT-HALF ===")
    half = len(closes) // 2
    h1_results = []
    h2_results = []
    for fl_ in fund_lbs:
        for pl_ in prem_lbs:
            for rf_ in rebals:
                for n_ in ns:
                    r1 = backtest_factor(closes.iloc[:half], funding_df, premium_df, fl_, pl_, rf_, n_, n_, "contrarian")
                    r2 = backtest_factor(closes.iloc[half:], funding_df, premium_df, fl_, pl_, rf_, n_, n_, "contrarian")
                    e1 = evaluate(r1)
                    e2 = evaluate(r2)
                    if e1 and e2:
                        h1_results.append(e1["sharpe"])
                        h2_results.append(e2["sharpe"])

    if h1_results and h2_results:
        corr = np.corrcoef(h1_results, h2_results)[0, 1] if len(h1_results) > 1 else 0
        h1_mean = np.mean(h1_results)
        h2_mean = np.mean(h2_results)
        print(f"Split-half corr: {corr:.3f}")
        print(f"H1 mean: {h1_mean:.3f}, H2 mean: {h2_mean:.3f}")

    # Correlation with H-012
    print(f"\n=== CORRELATIONS ===")
    mom_rets = backtest_momentum(closes)
    best_rets = backtest_factor(closes, funding_df, premium_df, fl, pl, rf, n, n, "contrarian")
    if mom_rets is not None and best_rets is not None:
        common = mom_rets.index.intersection(best_rets.index)
        if len(common) > 30:
            corr_mom = np.corrcoef(mom_rets.loc[common], best_rets.loc[common])[0, 1]
            print(f"Corr with H-012 momentum: {corr_mom:.3f}")


if __name__ == "__main__":
    main()
