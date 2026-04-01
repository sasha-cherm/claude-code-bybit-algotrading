#!/usr/bin/env python3
"""
H-171: Funding Rate Momentum Factor

Hypothesis: Instead of using the LEVEL of funding rates (H-053), use the CHANGE.
Rising funding = growing bullish crowding → contrarian short.
Falling funding = growing bearish crowding → contrarian long.

Signal: funding_momentum = mean(funding[-SW:]) - mean(funding[-LW:])
Positive = funding rising (bullish crowding increasing).
Contrarian direction: short rising, long falling.

Note: H-130 tested a similar idea on data through Mar 2026 and was rejected
(regime change, split-half signal inversion). H-171 re-tests on newer data
(through Apr 2026) with the same expanded parameter grid.
"""

import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd
from itertools import product

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache

ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE",
    "ADA", "AVAX", "DOT", "LINK", "NEAR",
    "OP", "ARB", "ATOM", "SUI",
]
ASSET_SYMBOLS = [f"{a}/USDT" for a in ASSETS]

DATA_DIR = ROOT / "data"


# ─────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────

def load_daily_closes():
    """Load daily closes for all 14 assets."""
    closes = {}
    for asset in ASSETS:
        sym = f"{asset}/USDT"
        try:
            df = fetch_and_cache(sym, "1d", limit_days=800)
            if len(df) >= 200:
                closes[asset] = df["close"]
        except Exception as e:
            print(f"  WARNING: failed to load closes for {asset}: {e}")

    panel = pd.DataFrame(closes).sort_index().dropna(how="all")
    return panel


def load_funding_rates():
    """
    Load 8h funding rates and aggregate to daily average.
    Falls back to premium proxy if funding files are missing.
    """
    funding = {}
    missing = []

    for asset in ASSETS:
        fpath = DATA_DIR / f"{asset}_USDT_USDT_funding.parquet"
        if fpath.exists():
            df = pd.read_parquet(fpath)
            if "funding_rate" in df.columns:
                daily = df["funding_rate"].resample("1D").mean()
                funding[asset] = daily
            else:
                missing.append(asset)
        else:
            missing.append(asset)

    if missing:
        print(f"  Funding data missing for: {missing}")

    panel = pd.DataFrame(funding).sort_index().dropna(how="all")
    print(f"Funding panel: {len(panel)} days, {len(panel.columns)} assets")
    if len(panel) > 0:
        print(f"Date range: {panel.index[0].date()} to {panel.index[-1].date()}")
    return panel


def load_premium_proxy():
    """
    Load premium index (mark vs spot) as funding rate proxy.
    Uses pre-cached all_assets_premium_daily.parquet if available.
    """
    prem_file = DATA_DIR / "all_assets_premium_daily.parquet"
    if prem_file.exists():
        prem = pd.read_parquet(prem_file)
        # Rename columns to match ASSETS if needed
        cols_map = {}
        for col in prem.columns:
            for a in ASSETS:
                if a in col:
                    cols_map[col] = a
                    break
        if cols_map:
            prem = prem.rename(columns=cols_map)
        # Keep only ASSETS columns
        prem = prem[[c for c in prem.columns if c in ASSETS]]
        print(f"Premium proxy loaded: {len(prem)} days, {len(prem.columns)} assets")
        return prem
    return None


# ─────────────────────────────────────────────
# Signal computation
# ─────────────────────────────────────────────

def compute_funding_momentum(funding_panel, sw, lw):
    """
    Compute funding rate momentum signal per asset per day.
    signal = mean(funding[-sw:]) - mean(funding[-lw:])
    Positive = funding accelerating upward = bullish crowding increasing.
    Uses expanding computation via rolling windows.
    """
    short_avg = funding_panel.rolling(sw, min_periods=max(1, sw // 2)).mean()
    long_avg = funding_panel.rolling(lw, min_periods=max(1, lw // 2)).mean()
    return short_avg - long_avg


# ─────────────────────────────────────────────
# Backtest engine
# ─────────────────────────────────────────────

def evaluate(rets, label=""):
    """Compute Sharpe, annual return, max drawdown."""
    if rets is None or len(rets) < 30:
        return None
    ann = rets.mean() * 365
    vol = rets.std() * np.sqrt(365)
    sharpe = ann / vol if vol > 1e-8 else 0.0
    cum = (1 + rets).cumprod()
    dd = (cum / cum.cummax() - 1).min()
    return {
        "label": label,
        "sharpe": round(sharpe, 3),
        "annual": round(ann * 100, 1),
        "dd": round(dd * 100, 1),
        "days": len(rets),
    }


def backtest_h171(closes, signal, rebal_freq, n, direction="contrarian", fee_bps=5):
    """
    Cross-sectional backtest using funding momentum signal.

    direction:
        "contrarian" — long low signal (falling funding), short high signal (rising funding)
        "momentum"   — long high signal (rising funding), short low signal (falling funding)
    """
    # Align indexes
    common_dates = closes.index.intersection(signal.index).dropna()
    # Use assets that appear in both
    common_assets = [a for a in ASSETS if a in closes.columns and a in signal.columns]
    if len(common_assets) < 2 * n + 1:
        return None

    closes_a = closes[common_assets].loc[common_dates]
    signal_a = signal[common_assets].loc[common_dates]
    returns = closes_a.pct_change()

    portfolio_returns = []
    current_longs = []
    current_shorts = []
    last_rebal_idx = None

    for i in range(1, len(common_dates)):
        date = common_dates[i]
        prev_date = common_dates[i - 1]

        # Mark-to-market
        if current_longs or current_shorts:
            w = 1.0 / (2 * n)
            day_ret = 0.0
            for a in current_longs:
                if a in returns.columns:
                    v = returns.loc[date, a]
                    if not np.isnan(v):
                        day_ret += w * v
            for a in current_shorts:
                if a in returns.columns:
                    v = returns.loc[date, a]
                    if not np.isnan(v):
                        day_ret -= w * v
            portfolio_returns.append({"date": date, "return": day_ret})

        # Rebalance check
        days_since = (i - last_rebal_idx) if last_rebal_idx is not None else rebal_freq + 1

        if days_since >= rebal_freq:
            sig_prev = signal_a.loc[prev_date].dropna()
            if len(sig_prev) < 2 * n:
                continue

            ranked = sig_prev.sort_values()  # ascending = low signal first

            if direction == "contrarian":
                new_longs = ranked.index[:n].tolist()    # long low (falling funding)
                new_shorts = ranked.index[-n:].tolist()  # short high (rising funding)
            else:  # momentum
                new_longs = ranked.index[-n:].tolist()   # long high (rising funding)
                new_shorts = ranked.index[:n].tolist()   # short low (falling funding)

            # Fees on turnover
            if current_longs or current_shorts:
                old_set = set(current_longs + current_shorts)
                new_set = set(new_longs + new_shorts)
                turnover_frac = len(old_set.symmetric_difference(new_set)) / (2 * n)
                fee_cost = turnover_frac * fee_bps * 2 / 10000
            else:
                fee_cost = fee_bps * 2 / 10000

            current_longs = new_longs
            current_shorts = new_shorts
            last_rebal_idx = i
            if portfolio_returns:
                portfolio_returns[-1]["return"] -= fee_cost

    if not portfolio_returns:
        return None
    df = pd.DataFrame(portfolio_returns).set_index("date")
    return df["return"]


# ─────────────────────────────────────────────
# Reference strategies for correlation
# ─────────────────────────────────────────────

def backtest_momentum_h012(closes, lookback=60, rebal_freq=5, n=4):
    """H-012: Cross-sectional momentum."""
    returns = closes.pct_change().dropna()
    dates = returns.index
    warmup = lookback + 2
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            day_ret = (returns.iloc[i] * weights).sum()
            portfolio_returns.append({"date": dates[i], "return": day_ret})
        if i - last_rebal >= rebal_freq:
            mom = closes.iloc[i - 1] / closes.iloc[i - 1 - lookback] - 1
            ranked = mom.sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_returns:
        return None
    return pd.DataFrame(portfolio_returns).set_index("date")["return"]


def backtest_funding_level_h053(closes, funding, window=5, rebal_freq=5, n=4,
                                 direction="long_low"):
    """H-053: Funding rate level (not momentum)."""
    rolling_sig = funding.rolling(window, min_periods=max(1, window // 2)).mean()
    common_assets = [a for a in ASSETS if a in closes.columns and a in rolling_sig.columns]
    common_dates = closes.index.intersection(rolling_sig.index).dropna()
    closes_a = closes[common_assets].loc[common_dates]
    signal_a = rolling_sig[common_assets].loc[common_dates]
    returns = closes_a.pct_change()
    portfolio_returns = []
    current_longs = []
    current_shorts = []
    last_rebal_idx = None
    for i in range(1, len(common_dates)):
        date = common_dates[i]
        prev_date = common_dates[i - 1]
        if current_longs or current_shorts:
            w = 1.0 / (2 * n)
            day_ret = 0.0
            for a in current_longs:
                v = returns.loc[date, a] if a in returns.columns else 0.0
                if not np.isnan(v):
                    day_ret += w * v
            for a in current_shorts:
                v = returns.loc[date, a] if a in returns.columns else 0.0
                if not np.isnan(v):
                    day_ret -= w * v
            portfolio_returns.append({"date": date, "return": day_ret})
        days_since = (i - last_rebal_idx) if last_rebal_idx is not None else rebal_freq + 1
        if days_since >= rebal_freq:
            sig_prev = signal_a.loc[prev_date].dropna()
            if len(sig_prev) < 2 * n:
                continue
            ranked = sig_prev.sort_values()
            if direction == "long_low":
                new_longs = ranked.index[:n].tolist()
                new_shorts = ranked.index[-n:].tolist()
            else:
                new_longs = ranked.index[-n:].tolist()
                new_shorts = ranked.index[:n].tolist()
            current_longs = new_longs
            current_shorts = new_shorts
            last_rebal_idx = i
    if not portfolio_returns:
        return None
    return pd.DataFrame(portfolio_returns).set_index("date")["return"]


def backtest_efficiency_h076(closes, lookback=40, rebal_freq=5, n=4):
    """H-076: Price efficiency factor."""
    returns = closes.pct_change().dropna()
    dates = returns.index
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_returns.append({"date": dates[i], "return": (returns.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                p = closes[sym].iloc[i - lookback:i]
                net_move = abs(p.iloc[-1] / p.iloc[0] - 1)
                daily_moves = abs(p.pct_change().dropna()).sum()
                eff = net_move / daily_moves if daily_moves > 0 else 0
                signals[sym] = eff
            ranked = pd.Series(signals).sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_returns:
        return None
    return pd.DataFrame(portfolio_returns).set_index("date")["return"]


def backtest_trend_quality_h160(closes, eff_lb=20, vol_lb=20, rebal_freq=3, n=3):
    """H-160: Trend quality = efficiency × inverse vol × momentum sign."""
    returns = closes.pct_change().dropna()
    dates = returns.index
    warmup = max(eff_lb, vol_lb) + 2
    portfolio_returns = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)
    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_returns.append({"date": dates[i], "return": (returns.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                p = closes[sym].iloc[i - eff_lb:i]
                net_move = p.iloc[-1] / p.iloc[0] - 1  # keep sign
                abs_daily = abs(p.pct_change().dropna()).sum()
                eff = abs(net_move) / abs_daily if abs_daily > 0 else 0
                vol = returns[sym].iloc[max(0, i - vol_lb):i].std()
                inv_vol = 1.0 / vol if vol > 1e-8 else 0
                signals[sym] = eff * inv_vol * np.sign(net_move)
            ranked = pd.Series(signals).sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i
    if not portfolio_returns:
        return None
    return pd.DataFrame(portfolio_returns).set_index("date")["return"]


# ─────────────────────────────────────────────
# Full validation pipeline
# ─────────────────────────────────────────────

def run_full_validation(closes, funding):
    """
    Full 4/4 validation for H-171 funding momentum factor.
    Grid: SW ∈ [3,5,10], LW ∈ [10,20,30], R ∈ [3,5,7], N ∈ [3,4],
          direction ∈ ["contrarian","momentum"], constraint SW < LW
    """
    print("\n" + "=" * 65)
    print("  H-171: Funding Rate Momentum Factor")
    print("=" * 65)

    sw_list = [3, 5, 10]
    lw_list = [10, 20, 30]
    r_list = [3, 5, 7]
    n_list = [3, 4]
    directions = ["contrarian", "momentum"]

    # Pre-compute all (SW, LW) signals upfront for efficiency
    print("Pre-computing signals...")
    signals_cache = {}
    for sw, lw in product(sw_list, lw_list):
        if sw < lw:
            signals_cache[(sw, lw)] = compute_funding_momentum(funding, sw, lw)

    combos = [
        (sw, lw, r, n, d)
        for sw, lw, r, n, d in product(sw_list, lw_list, r_list, n_list, directions)
        if sw < lw
    ]
    print(f"Testing {len(combos)} parameter combinations...")

    results = []
    for sw, lw, r, n, direction in combos:
        sig = signals_cache[(sw, lw)]
        rets = backtest_h171(closes, sig, r, n, direction)
        ev = evaluate(rets, f"SW{sw}_LW{lw}_R{r}_N{n}_{direction[:4]}")
        if ev:
            ev["sw"] = sw
            ev["lw"] = lw
            ev["r"] = r
            ev["n"] = n
            ev["direction"] = direction
            results.append(ev)

    if not results:
        print("No valid results!")
        return None, None

    df = pd.DataFrame(results)

    # ── IS Summary ──
    print(f"\n=== H-171 FUNDING RATE MOMENTUM RESULTS ===")
    for d in directions:
        sub = df[df["direction"] == d]
        n_pos = (sub["sharpe"] > 0).sum()
        total = len(sub)
        pct = n_pos / total * 100 if total > 0 else 0
        print(f"Direction: {d} — {n_pos}/{total} positive ({pct:.0f}%)")

    n_pos_all = (df["sharpe"] > 0).sum()
    pct_pos_all = n_pos_all / len(df) * 100
    best_row = df.loc[df["sharpe"].idxmax()]

    print(f"\nOverall: {n_pos_all}/{len(df)} positive ({pct_pos_all:.1f}%)")
    print(f"Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"Best: SW{best_row['sw']}_LW{best_row['lw']}_R{best_row['r']}_N{best_row['n']}_{best_row['direction']}")
    print(f"  Sharpe {best_row['sharpe']:.3f}, Ann {best_row['annual']:.1f}%, DD {best_row['dd']:.1f}%, {best_row['days']}d")

    print(f"\nTop 5 by Sharpe:")
    for _, r in df.nlargest(5, "sharpe").iterrows():
        print(f"  SW{r['sw']}_LW{r['lw']}_R{r['r']}_N{r['n']}_{r['direction']:12}: "
              f"Sharpe {r['sharpe']:.3f}, Ann {r['annual']:.1f}%, DD {r['dd']:.1f}%")

    if pct_pos_all < 80:
        print(f"\n** FAIL IS criterion: {pct_pos_all:.1f}% positive (need >=80%). **")
        print("Continuing to check best direction and walk-forward anyway...")

    # ── Walk-Forward ──
    sw_b = int(best_row["sw"])
    lw_b = int(best_row["lw"])
    r_b = int(best_row["r"])
    n_b = int(best_row["n"])
    d_b = best_row["direction"]
    sig_best = signals_cache[(sw_b, lw_b)]

    # Determine test date range (use closes index as reference)
    common_dates = closes.index.intersection(sig_best.index).dropna()
    total_days = len(common_dates)
    test_days = 90
    n_folds = 6

    print(f"\n--- Walk-Forward (best: SW{sw_b}_LW{lw_b}_R{r_b}_N{n_b}_{d_b}) ---")
    wf_results = []
    for fold in range(n_folds):
        test_end_idx = total_days - fold * test_days
        test_start_idx = test_end_idx - test_days
        if test_start_idx < lw_b + 30:
            break

        test_dates = common_dates[test_start_idx:test_end_idx]
        if len(test_dates) < 10:
            break

        test_start = test_dates[0]
        test_end = test_dates[-1]

        closes_fold = closes.loc[test_start:test_end]
        sig_fold = sig_best  # use full history signal up to test_end

        rets = backtest_h171(closes_fold, sig_fold, r_b, n_b, d_b)
        if rets is not None and len(rets) >= 10:
            ev = evaluate(rets, f"fold{fold}")
            if ev:
                wf_results.append(ev)
                print(f"  fold{fold} ({test_start.date()} to {test_end.date()}): Sharpe {ev['sharpe']:.3f}")

    if wf_results:
        wf_sharpes = [r["sharpe"] for r in wf_results]
        n_pos_wf = sum(1 for s in wf_sharpes if s > 0)
        mean_wf = np.mean(wf_sharpes)
        print(f"WF positive: {n_pos_wf}/{len(wf_results)}, mean OOS: {mean_wf:.3f}")
    else:
        n_pos_wf = 0
        mean_wf = 0.0
        print("WF: no valid folds")

    # ── Split-Half ──
    print(f"\n--- Split-Half ---")
    half = total_days // 2
    half_date = common_dates[half]
    closes_h1 = closes[closes.index < half_date]
    closes_h2 = closes[closes.index >= half_date]

    h1_sharpes = []
    h2_sharpes = []
    for sw_, lw_, r_, n_, d_ in combos:
        sig_ = signals_cache[(sw_, lw_)]
        r1 = backtest_h171(closes_h1, sig_[sig_.index < half_date], r_, n_, d_)
        r2 = backtest_h171(closes_h2, sig_[sig_.index >= half_date], r_, n_, d_)
        e1 = evaluate(r1)
        e2 = evaluate(r2)
        if e1 and e2:
            h1_sharpes.append(e1["sharpe"])
            h2_sharpes.append(e2["sharpe"])

    if h1_sharpes and h2_sharpes:
        h1_mean = np.mean(h1_sharpes)
        h2_mean = np.mean(h2_sharpes)
        sh_corr = np.corrcoef(h1_sharpes, h2_sharpes)[0, 1] if len(h1_sharpes) > 1 else 0
        print(f"H1 mean Sharpe: {h1_mean:.3f}, H2 mean Sharpe: {h2_mean:.3f}, corr: {sh_corr:.3f}")
    else:
        h1_mean = h2_mean = sh_corr = 0.0
        print("Split-half: insufficient data")

    # ── Correlations ──
    print(f"\n--- Correlations ---")

    # Best H-171 returns
    best_rets = backtest_h171(closes, sig_best, r_b, n_b, d_b)

    # H-012 momentum
    closes_for_corr = closes[[a for a in ASSETS if a in closes.columns]].rename(
        columns={a: f"{a}/USDT" for a in ASSETS if a in closes.columns}
    )
    mom_rets = backtest_momentum_h012(closes_for_corr)

    # H-053 funding level (best known direction = long_low)
    h053_rets = backtest_funding_level_h053(closes, funding, window=5, rebal_freq=5, n=4,
                                             direction="long_low")
    # H-076 efficiency
    h076_rets = backtest_efficiency_h076(closes_for_corr)

    # H-160 trend quality
    h160_rets = backtest_trend_quality_h160(closes_for_corr)

    corr_pairs = [
        ("H-012 Momentum", mom_rets),
        ("H-053 FundingLevel", h053_rets),
        ("H-076 Efficiency", h076_rets),
        ("H-160 TrendQuality", h160_rets),
    ]
    for name, other in corr_pairs:
        if best_rets is not None and other is not None:
            # Align on common index
            common_idx = best_rets.index.intersection(other.index)
            if len(common_idx) > 30:
                corr_val = np.corrcoef(
                    best_rets.loc[common_idx].values,
                    other.loc[common_idx].values
                )[0, 1]
                print(f"  H-171 vs {name}: {corr_val:.3f}")
            else:
                print(f"  H-171 vs {name}: insufficient overlap")
        else:
            print(f"  H-171 vs {name}: N/A")

    # ── Final summary ──
    print(f"\n{'='*65}")
    print(f"SUMMARY")
    print(f"{'='*65}")
    pass1 = pct_pos_all >= 80
    pass2 = wf_results and n_pos_wf >= 4
    pass3 = h1_mean > 0 and h2_mean > 0

    print(f"1. IS positive rate: {pct_pos_all:.1f}% {'PASS' if pass1 else 'FAIL'} (need >=80%)")
    print(f"2. Walk-forward: {n_pos_wf}/{len(wf_results) if wf_results else 0} positive, mean OOS {mean_wf:.3f} {'PASS' if pass2 else 'FAIL'} (need >=4/6)")
    print(f"3. Split-half: H1={h1_mean:.3f}, H2={h2_mean:.3f} {'PASS' if pass3 else 'FAIL'} (both need >0)")

    passed = sum([pass1, pass2, pass3])
    print(f"\nScore: {passed}/3 criteria")
    if passed == 3:
        print("** CONFIRMED — all criteria pass **")
    else:
        print(f"** REJECTED — only {passed}/3 pass **")

    return df, best_rets


def main():
    print("=" * 65)
    print("H-171: Funding Rate Momentum Factor")
    print("=" * 65)

    print("\nLoading closes...")
    closes = load_daily_closes()
    print(f"Closes: {len(closes.columns)} assets, {len(closes)} daily bars")
    if len(closes) > 0:
        print(f"Range: {closes.index[0].date()} to {closes.index[-1].date()}")

    print("\nLoading funding rates...")
    funding = load_funding_rates()

    if len(funding.columns) == 0:
        print("No funding data available, loading premium proxy...")
        funding = load_premium_proxy()
        if funding is None or len(funding.columns) == 0:
            print("ERROR: No funding or premium data available.")
            sys.exit(1)

    # Align
    common_assets = [a for a in ASSETS if a in closes.columns and a in funding.columns]
    print(f"\nCommon assets with both closes + funding: {len(common_assets)}")
    print(f"Assets: {common_assets}")

    closes_aligned = closes[common_assets]
    funding_aligned = funding[common_assets]

    run_full_validation(closes_aligned, funding_aligned)


if __name__ == "__main__":
    main()
