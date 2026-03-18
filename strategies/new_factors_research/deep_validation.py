"""
Deep Validation: H-019 Low-Volatility Anomaly + H-020 Funding Dispersion (fixed)

H-019 passed initial screen (88% positive, 5/6 WF folds, mean OOS 1.56).
Now validate:
1. Parameter robustness around best params (V20_R21_N3)
2. Fee sensitivity (2x, 3x, 5x fees)
3. Correlation with H-009 (BTC trend) and H-011 (funding arb)
4. 4-strategy portfolio simulation
5. Drawdown analysis — 47.9% DD is concerning

H-020: Fixed file path issue, retry with correct funding data paths.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

BASE_FEE = 0.001
SLIPPAGE_BPS = 2.0
INITIAL_CAPITAL = 10_000.0


def resample_to_daily(df):
    daily = df.resample("1D").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()
    return daily


def load_all_data():
    hourly = {}
    daily = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df) < 200:
                continue
            hourly[sym] = df
            daily[sym] = resample_to_daily(df)
        except Exception:
            pass
    return hourly, daily


def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  fee_multiplier=1.0, warmup=65):
    if n_short is None:
        n_short = n_long
    n = len(closes)
    slippage = SLIPPAGE_BPS / 10_000
    fee_rate = BASE_FEE * fee_multiplier
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital
    prev_weights = pd.Series(0.0, index=closes.columns)
    trades = 0

    for i in range(1, n):
        price_today = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = ranking_series.iloc[i - 1]
            valid = ranks.dropna()
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
            weight_changes = (new_weights - prev_weights).abs()
            trades += int((weight_changes > 0.01).sum())
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * (fee_rate + slippage)
            daily_rets = (price_today / price_yesterday - 1)
            port_ret = (new_weights * daily_rets).sum() - fee_drag
            prev_weights = new_weights
        else:
            daily_rets = (price_today / price_yesterday - 1)
            port_ret = (prev_weights * daily_rets).sum()

        equity[i] = equity[i - 1] * (1 + port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    eq = eq_series[eq_series > 0]
    if len(eq) < 50:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "equity": eq_series}
    rets = eq.pct_change().dropna()
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 2),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "n_trades": trades,
        "equity": eq_series,
    }


# ═══════════════════════════════════════════════════════════════════════
# 1. H-019 Parameter Robustness
# ═══════════════════════════════════════════════════════════════════════

def h019_param_robustness(closes):
    """Test parameter space around best (V20_R21_N3)."""
    print("\n" + "=" * 60)
    print("1. H-019 PARAMETER ROBUSTNESS")
    print("=" * 60)

    daily_rets = closes.pct_change()
    results = []

    for vol_window in [10, 15, 20, 25, 30, 40, 60]:
        for rebal in [7, 10, 14, 21, 28]:
            for n_long in [2, 3, 4, 5]:
                ranking = -daily_rets.rolling(vol_window).std()
                res = run_xs_factor(closes, ranking, rebal, n_long,
                                    warmup=vol_window + 10)
                results.append({
                    "vol_window": vol_window, "rebal": rebal, "n_long": n_long,
                    "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
                    "max_dd": res["max_dd"], "n_trades": res["n_trades"],
                })

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"  Total: {len(df)} params")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.2f}")
    print(f"  Min: {df['sharpe'].min():.2f}, Max: {df['sharpe'].max():.2f}")

    # By vol_window
    print("\n  By vol_window:")
    for vw, grp in df.groupby("vol_window"):
        pos = (grp["sharpe"] > 0).sum()
        print(f"    V{vw}: {pos}/{len(grp)} positive, mean {grp['sharpe'].mean():.2f}")

    # By n_long
    print("\n  By n_long:")
    for nl, grp in df.groupby("n_long"):
        pos = (grp["sharpe"] > 0).sum()
        print(f"    N{nl}: {pos}/{len(grp)} positive, mean {grp['sharpe'].mean():.2f}")

    top10 = df.nlargest(10, "sharpe")
    print("\n  Top 10:")
    for _, row in top10.iterrows():
        print(f"    V{int(row['vol_window'])}_R{int(row['rebal'])}_N{int(row['n_long'])}: "
              f"Sharpe {row['sharpe']:.2f}, Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    return df


# ═══════════════════════════════════════════════════════════════════════
# 2. Fee Sensitivity
# ═══════════════════════════════════════════════════════════════════════

def h019_fee_sensitivity(closes, vol_window=20, rebal=21, n_long=3):
    """Test fee sensitivity at 1x, 2x, 3x, 5x base fees."""
    print("\n" + "=" * 60)
    print("2. H-019 FEE SENSITIVITY")
    print("=" * 60)

    daily_rets = closes.pct_change()
    ranking = -daily_rets.rolling(vol_window).std()

    for mult in [1.0, 2.0, 3.0, 5.0]:
        res = run_xs_factor(closes, ranking, rebal, n_long,
                            warmup=vol_window + 10, fee_multiplier=mult)
        print(f"  Fee {mult}x: Sharpe {res['sharpe']:.2f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}, "
              f"Trades {res['n_trades']}")


# ═══════════════════════════════════════════════════════════════════════
# 3. Rolling Walk-Forward (more folds)
# ═══════════════════════════════════════════════════════════════════════

def h019_walk_forward(closes, vol_window=20, rebal=21, n_long=3):
    """Rolling walk-forward with 8 folds."""
    print("\n" + "=" * 60)
    print("3. H-019 ROLLING WALK-FORWARD (8 folds)")
    print("=" * 60)

    daily_rets = closes.pct_change()
    n = len(closes)
    test_days = 80
    fold_results = []

    for fold in range(8):
        test_end = n - fold * test_days
        test_start = test_end - test_days
        if test_start < vol_window + 20:
            break

        test_closes = closes.iloc[test_start:test_end]
        ranking = -daily_rets.iloc[:test_end].rolling(vol_window).std()
        test_ranking = ranking.iloc[test_start:test_end]

        res = run_xs_factor(test_closes, test_ranking, rebal, n_long,
                            warmup=5, fee_multiplier=1.0)
        fold_results.append({
            "fold": fold + 1,
            "period": f"{test_closes.index[0].date()} → {test_closes.index[-1].date()}",
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        })
        print(f"  Fold {fold+1}: {test_closes.index[0].date()} → {test_closes.index[-1].date()}, "
              f"Sharpe {res['sharpe']:.2f}, Ann {res['annual_ret']:.1%}")

    df = pd.DataFrame(fold_results)
    pos = (df["sharpe"] > 0).sum()
    print(f"\n  Positive folds: {pos}/{len(df)}")
    print(f"  Mean OOS Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Median OOS Sharpe: {df['sharpe'].median():.2f}")
    return df


# ═══════════════════════════════════════════════════════════════════════
# 4. Correlation with H-009, H-011, H-012
# ═══════════════════════════════════════════════════════════════════════

def h019_correlations(daily_data, closes, vol_window=20, rebal=21, n_long=3):
    """Compute correlations with existing strategies."""
    print("\n" + "=" * 60)
    print("4. H-019 CORRELATIONS WITH EXISTING STRATEGIES")
    print("=" * 60)

    daily_rets = closes.pct_change()
    ranking = -daily_rets.rolling(vol_window).std()
    h019_res = run_xs_factor(closes, ranking, rebal, n_long,
                              warmup=vol_window + 10)
    h019_eq = h019_res["equity"]
    h019_rets = h019_eq.pct_change().dropna()

    # H-012: 60d momentum
    mom_ranking = closes.pct_change(60)
    h012_res = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)
    h012_eq = h012_res["equity"]
    h012_rets = h012_eq.pct_change().dropna()

    # H-009: BTC daily trend (approximate with BTC returns)
    btc_close = closes["BTC/USDT"] if "BTC/USDT" in closes.columns else None
    h009_rets = None
    if btc_close is not None:
        h009_rets = btc_close.pct_change().dropna()

    # Compute correlations
    common = h019_rets.index.intersection(h012_rets.index)
    corr_h012 = h019_rets.loc[common].corr(h012_rets.loc[common])
    print(f"  H-019 ↔ H-012 (momentum): {corr_h012:.3f}")

    if h009_rets is not None:
        common_h009 = h019_rets.index.intersection(h009_rets.index)
        corr_h009 = h019_rets.loc[common_h009].corr(h009_rets.loc[common_h009])
        print(f"  H-019 ↔ H-009 (BTC trend proxy): {corr_h009:.3f}")

    return h019_eq, h019_rets


# ═══════════════════════════════════════════════════════════════════════
# 5. Portfolio Simulation: H-009 + H-011 + H-012 + H-019
# ═══════════════════════════════════════════════════════════════════════

def portfolio_simulation(closes, vol_window=20, rebal=21, n_long=3):
    """Simulate 4-strategy portfolio."""
    print("\n" + "=" * 60)
    print("5. 4-STRATEGY PORTFOLIO SIMULATION")
    print("=" * 60)

    daily_rets_panel = closes.pct_change()

    # H-019 returns
    ranking = -daily_rets_panel.rolling(vol_window).std()
    h019_res = run_xs_factor(closes, ranking, rebal, n_long,
                              warmup=vol_window + 10)
    h019_eq = h019_res["equity"]

    # H-012 returns
    mom_ranking = closes.pct_change(60)
    h012_res = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)
    h012_eq = h012_res["equity"]

    # H-009 proxy: BTC buy & hold with scaling
    btc = closes["BTC/USDT"]
    h009_eq = INITIAL_CAPITAL * (btc / btc.iloc[0])

    # H-011 proxy: flat returns (2% annual when active, ~60% of time)
    # Simplified: assume 1.5% annual consistently
    h011_daily_ret = (1.015 ** (1/365)) - 1
    h011_eq = pd.Series(INITIAL_CAPITAL * np.cumprod(np.ones(len(closes)) * (1 + h011_daily_ret)),
                         index=closes.index)

    # Align all equity curves
    common = h019_eq.index
    for eq in [h012_eq, h009_eq, h011_eq]:
        common = common.intersection(eq.index)

    h019_rets = h019_eq.loc[common].pct_change().dropna()
    h012_rets = h012_eq.loc[common].pct_change().dropna()
    h009_rets = h009_eq.loc[common].pct_change().dropna()
    h011_rets = h011_eq.loc[common].pct_change().dropna()

    common_rets = h019_rets.index.intersection(h012_rets.index).intersection(h009_rets.index)
    h019_r = h019_rets.loc[common_rets]
    h012_r = h012_rets.loc[common_rets]
    h009_r = h009_rets.loc[common_rets]
    h011_r = h011_rets.loc[common_rets]

    # Correlation matrix
    corr_df = pd.DataFrame({
        "H-009": h009_r, "H-011": h011_r,
        "H-012": h012_r, "H-019": h019_r,
    })
    print("\n  Correlation matrix:")
    print(corr_df.corr().round(3).to_string())

    # Portfolio allocations
    allocations = [
        ("3-strat (20/60/20)", [0.20, 0.60, 0.20, 0.00]),
        ("4-strat (15/50/15/20)", [0.15, 0.50, 0.15, 0.20]),
        ("4-strat (15/45/20/20)", [0.15, 0.45, 0.20, 0.20]),
        ("4-strat (10/50/20/20)", [0.10, 0.50, 0.20, 0.20]),
        ("4-strat equal (25/25/25/25)", [0.25, 0.25, 0.25, 0.25]),
    ]

    for name, weights in allocations:
        port_rets = (weights[0] * h009_r + weights[1] * h011_r +
                     weights[2] * h012_r + weights[3] * h019_r)
        port_eq = INITIAL_CAPITAL * (1 + port_rets).cumprod()

        sh = sharpe_ratio(port_rets, periods_per_year=365)
        ar = annual_return(port_eq, periods_per_year=365)
        dd = max_drawdown(port_eq)
        print(f"\n  {name}:")
        print(f"    Sharpe: {sh:.2f}, Annual: {ar:.1%}, MaxDD: {dd:.1%}")


# ═══════════════════════════════════════════════════════════════════════
# 6. H-020 Funding Rate Dispersion (Fixed)
# ═══════════════════════════════════════════════════════════════════════

def h020_funding_dispersion_fixed(daily_data):
    """Cross-sectional carry with correct funding data file paths."""
    print("\n" + "=" * 60)
    print("6. H-020 FUNDING RATE DISPERSION (Fixed)")
    print("=" * 60)

    data_dir = ROOT / "data"
    daily_funding = {}

    for sym in ASSETS:
        safe = sym.replace("/", "_")
        # Try the actual file naming pattern
        path = data_dir / f"{safe}_USDT_funding.parquet"
        if not path.exists():
            path = data_dir / f"{safe}_funding.parquet"
        if not path.exists():
            path = data_dir / f"{safe}_funding_rates.parquet"
        if not path.exists():
            continue

        df = pd.read_parquet(path)
        if "funding_rate" in df.columns:
            # Remove timezone info if present
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            fr = df["funding_rate"].resample("1D").sum()
            daily_funding[sym] = fr

    print(f"  Loaded funding data for {len(daily_funding)} assets")
    if len(daily_funding) < 8:
        print("  Need ≥8 assets. Cannot run H-020.")
        return None

    funding_panel = pd.DataFrame(daily_funding)
    funding_panel = funding_panel.dropna(how="all").ffill()
    print(f"  Funding panel: {len(funding_panel.columns)} assets, {len(funding_panel)} days")

    # Build closes panel
    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()
                          if sym in funding_panel.columns})
    closes = closes.dropna(how="all").ffill().dropna()

    # Align
    common_dates = closes.index.intersection(funding_panel.index)
    common_assets = list(set(closes.columns) & set(funding_panel.columns))
    closes = closes.loc[common_dates, common_assets]
    funding_panel = funding_panel.loc[common_dates, common_assets]
    print(f"  Aligned: {len(common_assets)} assets, {len(common_dates)} days")

    if len(common_assets) < 6 or len(common_dates) < 200:
        print("  Insufficient aligned data.")
        return None

    results = []
    for fr_window in [7, 14, 27, 45, 60]:
        for rebal_freq in [1, 3, 5, 7, 14]:
            for n_long in [3, 4]:
                ranking = funding_panel.rolling(fr_window).mean()
                warmup = fr_window + 10
                res = run_xs_factor(closes, ranking, rebal_freq, n_long,
                                    warmup=warmup)
                tag = f"F{fr_window}_R{rebal_freq}_N{n_long}"
                results.append({
                    "tag": tag, "fr_window": fr_window, "rebal": rebal_freq,
                    "n_long": n_long, "sharpe": res["sharpe"],
                    "annual_ret": res["annual_ret"], "max_dd": res["max_dd"],
                    "n_trades": res["n_trades"],
                })
                if res["sharpe"] > 0.3:
                    print(f"  ** {tag}: Sharpe {res['sharpe']:.2f}, "
                          f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"\n  Total: {len(df)} params")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.2f}")

    if len(df) > 0:
        top5 = df.nlargest(5, "sharpe")
        print("\n  Top 5:")
        for _, row in top5.iterrows():
            print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
                  f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    # Walk-forward if promising
    if (df["sharpe"] > 0).mean() >= 0.4:
        best = df.nlargest(1, "sharpe").iloc[0]
        print(f"\n  H-020 promising! Walk-forward with {best['tag']}...")
        fr_w = int(best["fr_window"])
        rb = int(best["rebal"])
        nl = int(best["n_long"])

        n = len(closes)
        test_days = 90
        fold_results = []
        for fold in range(6):
            test_end = n - fold * test_days
            test_start = test_end - test_days
            if test_start < fr_w + 20:
                break
            test_closes = closes.iloc[test_start:test_end]
            test_ranking = funding_panel.rolling(fr_w).mean().iloc[test_start:test_end]
            res = run_xs_factor(test_closes, test_ranking, rb, nl, warmup=5)
            fold_results.append({"fold": fold+1, "sharpe": res["sharpe"],
                                 "annual_ret": res["annual_ret"]})
            print(f"    Fold {fold+1}: Sharpe {res['sharpe']:.2f}, Ann {res['annual_ret']:.1%}")

        if fold_results:
            wf_df = pd.DataFrame(fold_results)
            pos = (wf_df["sharpe"] > 0).sum()
            print(f"    Positive: {pos}/{len(wf_df)}, Mean OOS: {wf_df['sharpe'].mean():.2f}")

    return df


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Loading data...")
    hourly, daily = load_all_data()
    print(f"Loaded {len(daily)} assets\n")

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()

    # H-019 deep validation
    print("\n" + "█" * 70)
    print("H-019 LOW-VOLATILITY ANOMALY — DEEP VALIDATION")
    print("█" * 70)

    param_df = h019_param_robustness(closes)
    h019_fee_sensitivity(closes)
    wf_df = h019_walk_forward(closes)
    h019_eq, h019_rets = h019_correlations(daily, closes)
    portfolio_simulation(closes)

    # H-020 retry with fixed paths
    print("\n" + "█" * 70)
    print("H-020 FUNDING RATE DISPERSION — RETRY")
    print("█" * 70)
    h020_df = h020_funding_dispersion_fixed(daily)

    print("\n" + "█" * 70)
    print("DONE")
    print("█" * 70)
