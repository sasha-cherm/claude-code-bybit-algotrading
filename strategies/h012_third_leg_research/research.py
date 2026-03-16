"""
H-012 Research: Third Portfolio Leg Candidates

Explores three strategy tracks to find an uncorrelated alpha source
that complements H-009 (BTC daily trend) and H-011 (funding rate arb).

Track A: Cross-Sectional Momentum (14 assets, daily)
  - Rank assets by recent returns, long top quartile, short bottom quartile
  - Market-neutral → uncorrelated with BTC directional

Track B: Equal-Weight All-Asset Trend Following (14 assets, daily)
  - EMA crossover on all assets with equal weight
  - No selection (avoids walk-forward failure of H-008)

Track C: Calendar/Seasonality Patterns (BTC, hourly)
  - Hour-of-day and day-of-week return patterns
  - Exploitable if statistically robust and persistent
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import summary as calc_summary, sharpe_ratio, max_drawdown, annual_return
from strategies.daily_trend_multi_asset.strategy import (
    resample_to_daily,
    generate_signals,
    backtest_single_asset,
)

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001
SLIPPAGE_BPS = 2.0
INITIAL_CAPITAL = 10_000.0


def load_all_data():
    """Load 1h data for all assets, resample to daily."""
    hourly = {}
    daily = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df) < 200:
                print(f"  {sym}: insufficient data ({len(df)} bars), skipping")
                continue
            hourly[sym] = df
            daily[sym] = resample_to_daily(df)
            print(f"  {sym}: {len(daily[sym])} daily bars")
        except Exception as e:
            print(f"  {sym}: failed to load: {e}")
    return hourly, daily


# ═══════════════════════════════════════════════════════════════════════
# Track A: Cross-Sectional Momentum
# ═══════════════════════════════════════════════════════════════════════

def track_a_cross_sectional_momentum(daily_data: dict):
    """
    Rank assets by past N-day returns.
    Long top quartile, short bottom quartile. Equal weight.
    Rebalance every R days. Market-neutral.
    """
    print("\n" + "=" * 70)
    print("TRACK A: Cross-Sectional Momentum (14 assets, daily)")
    print("=" * 70)

    # Build a returns panel: daily returns for all assets
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all")
    # Forward-fill small gaps, drop assets with >20% missing
    for col in closes.columns:
        pct_missing = closes[col].isna().mean()
        if pct_missing > 0.20:
            closes = closes.drop(columns=col)
            print(f"  Dropped {col}: {pct_missing:.0%} missing")
    closes = closes.ffill().dropna()
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    results = []
    for lookback in [7, 14, 21, 30, 60]:
        for rebal_freq in [1, 3, 5, 7]:
            for n_long in [3, 4]:
                res = _run_xsmom(closes, lookback, rebal_freq, n_long)
                results.append(res)
                tag = f"L{lookback}_R{rebal_freq}_N{n_long}"
                print(f"  {tag}: Sharpe {res['sharpe']:.2f}, "
                      f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}, "
                      f"Trades {res['n_trades']}")

    # Best result
    best = max(results, key=lambda x: x["sharpe"])
    print(f"\n  BEST: L{best['lookback']}_R{best['rebal']}_N{best['n_long']}")
    print(f"  Sharpe {best['sharpe']:.2f}, Return {best['annual_ret']:.1%}, "
          f"DD {best['max_dd']:.1%}, Trades {best['n_trades']}")

    return results


def _run_xsmom(closes: pd.DataFrame, lookback: int, rebal_freq: int, n_long: int):
    """Run cross-sectional momentum backtest."""
    n_assets = len(closes.columns)
    n_short = n_long
    n = len(closes)
    slippage = SLIPPAGE_BPS / 10_000

    # Compute rolling returns for ranking
    rolling_ret = closes.pct_change(lookback)

    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital

    positions = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    trades = 0
    prev_weights = pd.Series(0.0, index=closes.columns)

    warmup = lookback + 5  # wait for lookback + buffer

    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]

        # Rebalance? Use i-1 ranking to avoid look-ahead bias
        if i >= warmup and (i - warmup) % rebal_freq == 0:
            rets = rolling_ret.iloc[i - 1]  # rank on YESTERDAY's data
            valid = rets.dropna()
            if len(valid) < n_long + n_short:
                equity[i] = equity[i - 1]
                continue

            ranked = valid.sort_values(ascending=False)
            longs = ranked.index[:n_long]
            shorts = ranked.index[-n_short:]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = 1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            # Count trades (weight changes)
            weight_changes = (new_weights - prev_weights).abs()
            trades += int((weight_changes > 0.01).sum())
            prev_weights = new_weights
            positions.iloc[i] = new_weights
        else:
            positions.iloc[i] = positions.iloc[i - 1] if i > 0 else 0.0

        # PnL: sum of weight * daily return
        daily_rets = (price_today / price_yesterday - 1)
        port_ret = (positions.iloc[i] * daily_rets).sum()

        # Fee estimate: proportional to turnover
        if i >= warmup and (i - warmup) % rebal_freq == 0:
            turnover = weight_changes.sum() / 2  # one-way
            fee_drag = turnover * (FEE_RATE + slippage)
            port_ret -= fee_drag

        equity[i] = equity[i - 1] * (1 + port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    eq_series = eq_series[eq_series > 0]

    if len(eq_series) < 50:
        return {
            "lookback": lookback, "rebal": rebal_freq, "n_long": n_long,
            "sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "n_trades": 0,
            "equity": eq_series,
        }

    rets = eq_series.pct_change().dropna()
    return {
        "lookback": lookback,
        "rebal": rebal_freq,
        "n_long": n_long,
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 2),
        "annual_ret": round(annual_return(eq_series, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq_series), 4),
        "n_trades": trades,
        "equity": eq_series,
    }


# ═══════════════════════════════════════════════════════════════════════
# Track B: Equal-Weight All-Asset Trend Following
# ═══════════════════════════════════════════════════════════════════════

def track_b_equal_weight_trend(daily_data: dict):
    """
    EMA crossover on all 14 assets with equal weight allocation.
    No asset selection — full diversification.
    """
    print("\n" + "=" * 70)
    print("TRACK B: Equal-Weight All-Asset Trend Following")
    print("=" * 70)

    results = []
    for ema_fast, ema_slow in [(5, 20), (5, 40), (10, 40), (10, 60), (20, 60)]:
        res = _run_ew_trend(daily_data, ema_fast, ema_slow)
        results.append(res)
        print(f"  EMA({ema_fast},{ema_slow}): Sharpe {res['sharpe']:.2f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}, "
              f"Assets {res['n_assets']}")

    # Also test with vol targeting
    for vt in [0.10, 0.15, 0.20]:
        res = _run_ew_trend(daily_data, 5, 40, vol_target=vt)
        results.append(res)
        print(f"  EMA(5,40) VT{int(vt*100)}%: Sharpe {res['sharpe']:.2f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    best = max(results, key=lambda x: x["sharpe"])
    print(f"\n  BEST: EMA({best.get('ema_fast','?')},{best.get('ema_slow','?')}) "
          f"VT={best.get('vol_target','none')}")
    print(f"  Sharpe {best['sharpe']:.2f}, Return {best['annual_ret']:.1%}, "
          f"DD {best['max_dd']:.1%}")

    return results


def _run_ew_trend(daily_data: dict, ema_fast: int = 5, ema_slow: int = 40,
                  vol_target: float = None):
    """Run equal-weight trend following across all assets."""
    n_assets = len(daily_data)
    alloc = INITIAL_CAPITAL / n_assets

    all_equity = {}
    total_trades = 0
    for sym, df in daily_data.items():
        if len(df) < ema_slow + 10:
            continue
        res = backtest_single_asset(
            df, ema_fast, ema_slow, FEE_RATE, SLIPPAGE_BPS, alloc
        )
        all_equity[sym] = res["equity_curve"]
        total_trades += len(res["trades"])

    if not all_equity:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "n_assets": 0}

    eq_df = pd.DataFrame(all_equity).dropna()
    portfolio_eq = eq_df.sum(axis=1)

    if vol_target is not None:
        from strategies.daily_trend_multi_asset.strategy import apply_vol_targeting
        portfolio_eq = apply_vol_targeting(eq_df, INITIAL_CAPITAL, vol_target, 60)

    rets = portfolio_eq.pct_change().dropna()
    return {
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "vol_target": vol_target,
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 2),
        "annual_ret": round(annual_return(portfolio_eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(portfolio_eq), 4),
        "n_assets": len(all_equity),
        "n_trades": total_trades,
        "equity": portfolio_eq,
    }


# ═══════════════════════════════════════════════════════════════════════
# Track C: Calendar / Seasonality Patterns (BTC hourly)
# ═══════════════════════════════════════════════════════════════════════

def track_c_calendar_patterns(btc_1h: pd.DataFrame):
    """
    Analyze hour-of-day and day-of-week patterns in BTC returns.
    Test if they're exploitable.
    """
    print("\n" + "=" * 70)
    print("TRACK C: Calendar/Seasonality Patterns (BTC 1h)")
    print("=" * 70)

    df = btc_1h.copy()
    df["ret"] = df["close"].pct_change()
    df["hour"] = df.index.hour
    df["dow"] = df.index.dayofweek  # 0=Mon, 6=Sun

    # --- Hour-of-day analysis ---
    print("\n  Hour-of-Day Returns (annualized):")
    hour_stats = df.groupby("hour")["ret"].agg(["mean", "std", "count"])
    hour_stats["annual_ret"] = hour_stats["mean"] * 8760
    hour_stats["t_stat"] = hour_stats["mean"] / (hour_stats["std"] / np.sqrt(hour_stats["count"]))
    for h, row in hour_stats.iterrows():
        sig = "*" if abs(row["t_stat"]) > 1.96 else " "
        print(f"    {h:02d}:00 — {row['annual_ret']:+.1%} "
              f"(t={row['t_stat']:+.2f}) {sig}")

    # --- Day-of-week analysis ---
    daily_rets = df["ret"].resample("1D").sum()
    daily_rets_df = daily_rets.to_frame("ret")
    daily_rets_df["dow"] = daily_rets_df.index.dayofweek
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    print("\n  Day-of-Week Returns (annualized):")
    dow_stats = daily_rets_df.groupby("dow")["ret"].agg(["mean", "std", "count"])
    dow_stats["annual_ret"] = dow_stats["mean"] * 365
    dow_stats["t_stat"] = dow_stats["mean"] / (dow_stats["std"] / np.sqrt(dow_stats["count"]))
    for d, row in dow_stats.iterrows():
        sig = "*" if abs(row["t_stat"]) > 1.96 else " "
        print(f"    {dow_names[d]} — {row['annual_ret']:+.1%} "
              f"(t={row['t_stat']:+.2f}) {sig}")

    # --- Test simple hour-of-day strategy ---
    # Find most positive hours, go long only during those
    top_hours = hour_stats.nlargest(6, "mean").index.tolist()
    bot_hours = hour_stats.nsmallest(6, "mean").index.tolist()

    print(f"\n  Top-6 hours: {sorted(top_hours)}")
    print(f"  Bottom-6 hours: {sorted(bot_hours)}")

    # Backtest: long during top hours, short during bottom hours, flat otherwise
    results = []
    for strategy_name, long_hours, short_hours in [
        ("top6_long_only", top_hours, []),
        ("top6_long_bot6_short", top_hours, bot_hours),
        ("long_all_except_bot6", [h for h in range(24) if h not in bot_hours], []),
    ]:
        signal = pd.Series(0, index=df.index)
        signal[df["hour"].isin(long_hours)] = 1
        if short_hours:
            signal[df["hour"].isin(short_hours)] = -1

        # Compute returns (no fee since we're always in the market, just switching)
        # But with hourly rebalance there are transaction costs
        position_changes = signal.diff().abs().fillna(0)
        strat_rets = signal.shift(1) * df["ret"]  # lag signal by 1 to avoid lookahead
        strat_rets -= position_changes * (FEE_RATE + SLIPPAGE_BPS / 10_000) / 2

        strat_rets = strat_rets.dropna()
        eq = INITIAL_CAPITAL * (1 + strat_rets).cumprod()
        ann_ret = annual_return(eq, 8760)
        mdd = max_drawdown(eq)
        sharpe = sharpe_ratio(strat_rets, periods_per_year=8760)

        n_switches = int(position_changes.sum())
        results.append({
            "name": strategy_name,
            "sharpe": round(sharpe, 2),
            "annual_ret": round(ann_ret, 4),
            "max_dd": round(mdd, 4),
            "n_switches": n_switches,
        })
        print(f"  {strategy_name}: Sharpe {sharpe:.2f}, "
              f"Ann {ann_ret:.1%}, DD {mdd:.1%}, Switches {n_switches}")

    # --- Test day-of-week strategy ---
    print("\n  Day-of-Week Strategies:")
    best_dow = dow_stats["mean"].idxmax()
    worst_dow = dow_stats["mean"].idxmin()

    # Backtest: long on best days, short on worst days
    daily_signal = pd.Series(0, index=daily_rets.index)
    daily_signal[daily_rets_df["dow"] == best_dow] = 1
    daily_signal[daily_rets_df["dow"] == worst_dow] = -1

    daily_strat_rets = daily_signal.shift(1) * daily_rets
    changes_d = daily_signal.diff().abs().fillna(0)
    daily_strat_rets -= changes_d * (FEE_RATE + SLIPPAGE_BPS / 10_000) / 2
    daily_strat_rets = daily_strat_rets.dropna()
    eq_d = INITIAL_CAPITAL * (1 + daily_strat_rets).cumprod()

    sharpe_d = sharpe_ratio(daily_strat_rets, periods_per_year=365)
    ann_d = annual_return(eq_d, 365)
    mdd_d = max_drawdown(eq_d)
    print(f"  Long {dow_names[best_dow]}/Short {dow_names[worst_dow]}: "
          f"Sharpe {sharpe_d:.2f}, Ann {ann_d:.1%}, DD {mdd_d:.1%}")

    # OOS stability: split in half
    mid = len(df) // 2
    h1 = df.iloc[:mid].groupby(df.iloc[:mid].index.hour)["ret"].mean()
    h2 = df.iloc[mid:].groupby(df.iloc[mid:].index.hour)["ret"].mean()
    corr = h1.corr(h2)
    print(f"\n  Hour pattern stability (1st half vs 2nd half correlation): {corr:.2f}")

    return results


# ═══════════════════════════════════════════════════════════════════════
# Track D: Correlation Analysis with Existing Portfolio
# ═══════════════════════════════════════════════════════════════════════

def analyze_correlations(h009_equity, candidate_equities: dict):
    """Check correlation of candidate strategies with H-009."""
    print("\n" + "=" * 70)
    print("CORRELATION ANALYSIS: Candidates vs H-009 (BTC trend)")
    print("=" * 70)

    h009_rets = h009_equity.pct_change().dropna()

    for name, eq in candidate_equities.items():
        cand_rets = eq.pct_change().dropna()
        # Align
        common = h009_rets.index.intersection(cand_rets.index)
        if len(common) < 30:
            print(f"  {name}: insufficient overlap ({len(common)} days)")
            continue
        corr = h009_rets.loc[common].corr(cand_rets.loc[common])
        print(f"  {name}: correlation with H-009 = {corr:.3f}")


# ═══════════════════════════════════════════════════════════════════════
# Walk-Forward Validation
# ═══════════════════════════════════════════════════════════════════════

def walk_forward_xsmom(daily_data: dict, lookback: int, rebal_freq: int, n_long: int):
    """70/30 train/test split for cross-sectional momentum."""
    print(f"\n  Walk-Forward OOS: XSMom L{lookback}_R{rebal_freq}_N{n_long}")

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()

    split = int(len(closes) * 0.7)
    test_closes = closes.iloc[split:]

    if len(test_closes) < 60:
        print("  Insufficient OOS data")
        return None

    res = _run_xsmom(test_closes, lookback, rebal_freq, n_long)
    print(f"  OOS: Sharpe {res['sharpe']:.2f}, Ann {res['annual_ret']:.1%}, "
          f"DD {res['max_dd']:.1%}")
    return res


def walk_forward_ew_trend(daily_data: dict, ema_fast: int, ema_slow: int,
                          vol_target: float = None):
    """70/30 train/test split for equal-weight trend following."""
    print(f"\n  Walk-Forward OOS: EW Trend EMA({ema_fast},{ema_slow}) "
          f"VT={vol_target}")

    # Split each asset at 70%
    test_data = {}
    for sym, df in daily_data.items():
        split = int(len(df) * 0.7)
        test_df = df.iloc[split:]
        if len(test_df) > ema_slow + 10:
            test_data[sym] = test_df

    if not test_data:
        print("  Insufficient OOS data")
        return None

    res = _run_ew_trend(test_data, ema_fast, ema_slow, vol_target)
    print(f"  OOS: Sharpe {res['sharpe']:.2f}, Ann {res['annual_ret']:.1%}, "
          f"DD {res['max_dd']:.1%}")
    return res


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("H-012 RESEARCH: Third Portfolio Leg Candidates")
    print("=" * 70)

    # Load data
    print("\nLoading data...")
    hourly, daily = load_all_data()
    print(f"Loaded {len(daily)} assets")

    # Track A: Cross-Sectional Momentum
    xsmom_results = track_a_cross_sectional_momentum(daily)

    # Track B: Equal-Weight Trend Following
    ew_results = track_b_equal_weight_trend(daily)

    # Track C: Calendar Patterns
    btc_1h = hourly.get("BTC/USDT")
    cal_results = None
    if btc_1h is not None:
        cal_results = track_c_calendar_patterns(btc_1h)

    # --- Walk-Forward Validation for best candidates ---
    print("\n" + "=" * 70)
    print("WALK-FORWARD VALIDATION")
    print("=" * 70)

    # Best XSMom
    best_xs = max(xsmom_results, key=lambda x: x["sharpe"])
    if best_xs["sharpe"] > 0:
        wf_xs = walk_forward_xsmom(
            daily, best_xs["lookback"], best_xs["rebal"], best_xs["n_long"]
        )
    else:
        print("  XSMom: No positive Sharpe, skipping WF")
        wf_xs = None

    # Best EW Trend (without VT)
    ew_no_vt = [r for r in ew_results if r.get("vol_target") is None]
    best_ew = max(ew_no_vt, key=lambda x: x["sharpe"])
    wf_ew = walk_forward_ew_trend(
        daily, best_ew["ema_fast"], best_ew["ema_slow"]
    )

    # Best EW Trend with VT
    ew_vt = [r for r in ew_results if r.get("vol_target") is not None]
    if ew_vt:
        best_ew_vt = max(ew_vt, key=lambda x: x["sharpe"])
        wf_ew_vt = walk_forward_ew_trend(
            daily, best_ew_vt["ema_fast"], best_ew_vt["ema_slow"],
            best_ew_vt["vol_target"]
        )

    # --- Correlation analysis ---
    # Get H-009 BTC-only equity for correlation
    btc_daily = daily.get("BTC/USDT")
    if btc_daily is not None:
        h009_res = backtest_single_asset(btc_daily, 5, 40, FEE_RATE, SLIPPAGE_BPS, INITIAL_CAPITAL)
        h009_eq = h009_res["equity_curve"]

        candidates = {}
        if best_xs["sharpe"] > 0 and "equity" in best_xs:
            candidates["XSMom_best"] = best_xs["equity"]
        if "equity" in best_ew:
            candidates["EW_Trend_best"] = best_ew["equity"]
        if ew_vt and "equity" in best_ew_vt:
            candidates[f"EW_Trend_VT{int(best_ew_vt['vol_target']*100)}"] = best_ew_vt["equity"]

        if candidates:
            analyze_correlations(h009_eq, candidates)

    # --- Summary ---
    print("\n" + "=" * 70)
    print("RESEARCH SUMMARY")
    print("=" * 70)

    print(f"\n  Track A (XSMom):     Best IS Sharpe = {best_xs['sharpe']:.2f}")
    if wf_xs:
        print(f"                       OOS Sharpe = {wf_xs['sharpe']:.2f}")

    print(f"  Track B (EW Trend):  Best IS Sharpe = {best_ew['sharpe']:.2f}")
    if wf_ew:
        print(f"                       OOS Sharpe = {wf_ew['sharpe']:.2f}")

    if cal_results:
        best_cal = max(cal_results, key=lambda x: x["sharpe"])
        print(f"  Track C (Calendar):  Best Sharpe = {best_cal['sharpe']:.2f}")

    print("\n  For comparison:")
    print(f"  H-009 (BTC trend):   Sharpe ~0.6-0.9")
    print(f"  H-011 (funding arb): Sharpe ~15-25")

    import json
    results_out = {
        "track_a_xsmom": [{k: v for k, v in r.items() if k != "equity"}
                          for r in xsmom_results],
        "track_b_ew_trend": [{k: v for k, v in r.items() if k != "equity"}
                             for r in ew_results],
        "track_c_calendar": cal_results,
        "walk_forward": {
            "xsmom_oos": {k: v for k, v in wf_xs.items() if k != "equity"} if wf_xs else None,
            "ew_trend_oos": {k: v for k, v in wf_ew.items() if k != "equity"} if wf_ew else None,
        },
    }
    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(results_out, f, indent=2, default=str)
    print(f"\n  Results saved to {out_path}")


if __name__ == "__main__":
    main()
