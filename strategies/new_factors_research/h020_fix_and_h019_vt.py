"""
1. H-020: Fixed timezone alignment for funding rate dispersion
2. H-019: Vol targeting to reduce drawdown
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


def run_xs_factor(closes, ranking_series, rebal_freq, n_long, n_short=None,
                  fee_multiplier=1.0, warmup=65, vol_target=None, vol_lookback=20):
    """Cross-sectional factor backtest with optional vol targeting."""
    if n_short is None:
        n_short = n_long
    n = len(closes)
    slippage = SLIPPAGE_BPS / 10_000
    fee_rate = BASE_FEE * fee_multiplier
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital
    prev_weights = pd.Series(0.0, index=closes.columns)
    prev_scale = 1.0
    trades = 0

    # Precompute daily returns for vol targeting
    daily_rets = closes.pct_change()

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

            # Vol targeting: scale weights
            if vol_target is not None and i > vol_lookback + 5:
                # Compute recent portfolio vol
                port_rets_hist = (prev_weights * daily_rets.iloc[max(0, i-vol_lookback):i]).sum(axis=1)
                realized_vol = port_rets_hist.std() * np.sqrt(365)
                if realized_vol > 0:
                    scale = vol_target / realized_vol
                    scale = min(scale, 2.0)  # cap at 2x
                    new_weights = new_weights * scale
                    prev_scale = scale

            weight_changes = (new_weights - prev_weights).abs()
            trades += int((weight_changes > 0.01).sum())
            turnover = weight_changes.sum() / 2
            fee_drag = turnover * (fee_rate + slippage)
            d_rets = (price_today / price_yesterday - 1)
            port_ret = (new_weights * d_rets).sum() - fee_drag
            prev_weights = new_weights
        else:
            d_rets = (price_today / price_yesterday - 1)
            port_ret = (prev_weights * d_rets).sum()

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
# H-019 with Vol Targeting
# ═══════════════════════════════════════════════════════════════════════

def h019_vol_targeting():
    """Test H-019 with different vol targets to reduce DD."""
    print("=" * 60)
    print("H-019 LOW-VOL WITH VOL TARGETING")
    print("=" * 60)

    print("\nLoading data...")
    daily = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df) >= 200:
                d = df.resample("1D").agg({
                    "open": "first", "high": "max", "low": "min",
                    "close": "last", "volume": "sum",
                }).dropna()
                daily[sym] = d
        except Exception:
            pass

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"  {len(closes.columns)} assets, {len(closes)} days")

    daily_rets = closes.pct_change()
    ranking = -daily_rets.rolling(20).std()

    print("\n  Vol targeting sweep (V20_R21_N3):")
    for vt in [None, 0.10, 0.15, 0.20, 0.25, 0.30]:
        res = run_xs_factor(closes, ranking, 21, 3, warmup=30,
                            vol_target=vt, vol_lookback=20)
        vt_str = f"{vt:.0%}" if vt else "none"
        print(f"    VT {vt_str:>5s}: Sharpe {res['sharpe']:.2f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}, "
              f"Trades {res['n_trades']}")

    # Walk-forward with best vol target
    print("\n  Walk-forward with VT 20% (V20_R21_N3):")
    n = len(closes)
    test_days = 80
    fold_results = []
    for fold in range(8):
        test_end = n - fold * test_days
        test_start = test_end - test_days
        if test_start < 40:
            break
        test_closes = closes.iloc[test_start:test_end]
        test_ranking = -closes.iloc[:test_end].pct_change().rolling(20).std().iloc[test_start:test_end]
        res = run_xs_factor(test_closes, test_ranking, 21, 3,
                            warmup=5, vol_target=0.20, vol_lookback=20)
        fold_results.append({
            "fold": fold + 1,
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        })
        print(f"    Fold {fold+1}: Sharpe {res['sharpe']:.2f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    df = pd.DataFrame(fold_results)
    pos = (df["sharpe"] > 0).sum()
    print(f"    Positive: {pos}/{len(df)}, Mean OOS Sharpe: {df['sharpe'].mean():.2f}")

    # Also test broader param set with VT
    print("\n  Param sweep with VT 20%:")
    results = []
    for vol_w in [15, 20, 30, 40]:
        for rb in [14, 21, 28]:
            for nl in [3, 4]:
                ranking = -daily_rets.rolling(vol_w).std()
                res = run_xs_factor(closes, ranking, rb, nl, warmup=vol_w+10,
                                    vol_target=0.20, vol_lookback=20)
                results.append({
                    "vol_w": vol_w, "rebal": rb, "n_long": nl,
                    "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
                    "max_dd": res["max_dd"],
                })
    rdf = pd.DataFrame(results)
    pos = (rdf["sharpe"] > 0).sum()
    print(f"    Total: {len(rdf)}, Positive: {pos}/{len(rdf)} ({pos/len(rdf):.0%})")
    print(f"    Mean Sharpe: {rdf['sharpe'].mean():.2f}, Best: {rdf['sharpe'].max():.2f}")
    print(f"    Mean DD: {rdf['max_dd'].mean():.1%}")

    top5 = rdf.nlargest(5, "sharpe")
    for _, row in top5.iterrows():
        print(f"    V{int(row['vol_w'])}_R{int(row['rebal'])}_N{int(row['n_long'])}: "
              f"Sharpe {row['sharpe']:.2f}, Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}")

    return closes, daily


# ═══════════════════════════════════════════════════════════════════════
# H-020 Funding Rate Dispersion (Fixed Timezone)
# ═══════════════════════════════════════════════════════════════════════

def h020_fixed():
    """Cross-sectional carry with proper timezone handling."""
    print("\n" + "=" * 60)
    print("H-020 FUNDING RATE DISPERSION (Fixed Timezone)")
    print("=" * 60)

    data_dir = ROOT / "data"

    # Load funding data with timezone handling
    daily_funding = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_USDT_funding.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if "funding_rate" not in df.columns:
            continue
        # Ensure tz-naive for alignment
        idx = df.index
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        fr = pd.Series(df["funding_rate"].values, index=idx)
        daily_funding[sym] = fr.resample("1D").sum()

    print(f"  Loaded funding for {len(daily_funding)} assets")

    if len(daily_funding) < 8:
        print("  Not enough funding data. Aborting.")
        return None

    funding_panel = pd.DataFrame(daily_funding).dropna(how="all").ffill()
    print(f"  Funding panel: {len(funding_panel.columns)} assets, {len(funding_panel)} days")

    # Load price data with tz-naive index
    closes_data = {}
    for sym in ASSETS:
        if sym not in funding_panel.columns:
            continue
        try:
            df = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df) >= 200:
                idx = df.index
                if idx.tz is not None:
                    idx = idx.tz_localize(None)
                df_fixed = df.copy()
                df_fixed.index = idx
                d = df_fixed["close"].resample("1D").last().dropna()
                closes_data[sym] = d
        except Exception:
            pass

    closes = pd.DataFrame(closes_data).dropna(how="all").ffill().dropna()

    # Align
    common_dates = closes.index.intersection(funding_panel.index)
    common_assets = list(set(closes.columns) & set(funding_panel.columns))
    closes = closes.loc[common_dates, common_assets]
    funding_panel = funding_panel.loc[common_dates, common_assets]
    print(f"  Aligned: {len(common_assets)} assets, {len(common_dates)} days")

    if len(common_assets) < 6 or len(common_dates) < 200:
        print("  Insufficient data after alignment.")
        return None

    results = []
    for fr_window in [7, 14, 27, 45, 60]:
        for rebal_freq in [1, 3, 5, 7, 14]:
            for n_long in [3, 4]:
                ranking = funding_panel.rolling(fr_window).mean()
                warmup = fr_window + 10
                res = run_xs_factor(closes, ranking, rebal_freq, n_long, warmup=warmup)
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

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}")

    # Walk-forward if promising
    if (df["sharpe"] > 0).mean() >= 0.35:
        best = df.nlargest(1, "sharpe").iloc[0]
        print(f"\n  Walk-forward with {best['tag']}...")
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


if __name__ == "__main__":
    h019_closes, h019_daily = h019_vol_targeting()
    h020_df = h020_fixed()
    print("\nDone.")
