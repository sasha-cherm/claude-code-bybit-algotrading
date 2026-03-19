"""
H-033: Idiosyncratic Momentum (Alpha Momentum)
H-034: Funding Rate as BTC Timing Signal

Session 2026-03-19 — exploring genuinely new alpha sources beyond exhausted
cross-sectional factor space.

H-033: Decompose each asset's return into market component (beta * BTC_return) +
idiosyncratic residual. Rank on residual momentum. Unlike H-012 (raw momentum),
this strips out BTC-driven moves. Assets with positive alpha continue outperforming.

H-034: Use extreme funding rate levels as a contrarian predictor of BTC returns.
High funding = crowded longs → bearish. Low funding = oversold → bullish.
Different from H-011 (carry collection) and H-009 (price trend).
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
    daily = {}
    for sym in ASSETS:
        try:
            df = fetch_and_cache(sym, "1h", limit_days=730)
            if len(df) < 200:
                continue
            daily[sym] = resample_to_daily(df)
        except Exception as e:
            print(f"  {sym}: failed: {e}")
    return daily


def compute_metrics(equity_series):
    eq = equity_series[equity_series > 0]
    if len(eq) < 50:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0}
    rets = eq.pct_change().dropna()
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=365), 2),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
    }


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
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = trades
    metrics["equity"] = eq_series
    return metrics


def rolling_walk_forward(closes, factor_fn, best_params, n_folds=6,
                         train_days=180, test_days=80):
    print(f"\n  Walk-Forward ({n_folds} folds, {train_days}d train, {test_days}d test)")
    n = len(closes)
    fold_results = []

    for fold in range(n_folds):
        test_end = n - fold * test_days
        test_start = test_end - test_days
        train_start = test_start - train_days

        if train_start < 0:
            break

        test_closes = closes.iloc[test_start:test_end]
        ranking = factor_fn(closes.iloc[:test_end])
        test_ranking = ranking.iloc[test_start:test_end]

        rebal = best_params.get("rebal_freq", 5)
        n_long = best_params.get("n_long", 4)

        res = run_xs_factor(test_closes, test_ranking, rebal, n_long,
                            warmup=5, fee_multiplier=1.0)

        fold_results.append({
            "fold": fold + 1,
            "start": test_closes.index[0].strftime("%Y-%m-%d"),
            "end": test_closes.index[-1].strftime("%Y-%m-%d"),
            "sharpe": res["sharpe"],
            "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"],
        })
        print(f"    Fold {fold+1}: {test_closes.index[0].date()} → {test_closes.index[-1].date()}, "
              f"Sharpe {res['sharpe']:.2f}, Ann {res['annual_ret']:.1%}")

    if not fold_results:
        return None

    df = pd.DataFrame(fold_results)
    positive = (df["sharpe"] > 0).sum()
    print(f"    Positive folds: {positive}/{len(df)}")
    print(f"    Mean OOS Sharpe: {df['sharpe'].mean():.2f}")
    print(f"    Median OOS Sharpe: {df['sharpe'].median():.2f}")
    return df


# ═══════════════════════════════════════════════════════════════════════
# H-033: Idiosyncratic Momentum (Alpha Momentum)
# ═══════════════════════════════════════════════════════════════════════

def compute_idiosyncratic_momentum(closes, beta_window, mom_window):
    """
    For each asset, regress returns on BTC returns over beta_window to get beta.
    Then compute residual returns = actual - beta * BTC_return.
    Rank on cumulative residual return over mom_window.
    """
    daily_rets = closes.pct_change()
    btc_rets = daily_rets["BTC/USDT"]

    ranking = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)

    start_idx = max(beta_window, mom_window) + 5
    for i in range(start_idx, len(closes)):
        btc_window = btc_rets.iloc[i - beta_window:i]
        row_vals = {}

        for sym in closes.columns:
            if sym == "BTC/USDT":
                row_vals[sym] = 0.0
                continue

            asset_window = daily_rets[sym].iloc[i - beta_window:i]
            valid = ~(btc_window.isna() | asset_window.isna())
            if valid.sum() < 20:
                continue

            bx = btc_window[valid].values
            ay = asset_window[valid].values
            cov = np.cov(bx, ay)
            if cov[0, 0] > 0:
                beta = cov[0, 1] / cov[0, 0]
            else:
                beta = 1.0

            recent_rets = daily_rets[sym].iloc[i - mom_window:i]
            recent_btc = btc_rets.iloc[i - mom_window:i]
            residual_rets = recent_rets - beta * recent_btc
            row_vals[sym] = residual_rets.sum()

        for sym, val in row_vals.items():
            ranking.loc[ranking.index[i], sym] = val

    return ranking


def h033_idiosyncratic_momentum(daily_data):
    print("\n" + "=" * 70)
    print("H-033: IDIOSYNCRATIC MOMENTUM (Alpha Momentum)")
    print("=" * 70)

    closes = pd.DataFrame({sym: df["close"] for sym, df in daily_data.items()})
    closes = closes.dropna(how="all").ffill().dropna()
    print(f"  Universe: {len(closes.columns)} assets, {len(closes)} days")

    results = []
    # Precompute rankings for each (beta_window, mom_window) — expensive
    ranking_cache = {}
    for beta_window in [30, 60, 90]:
        for mom_window in [10, 20, 30, 60]:
            key = (beta_window, mom_window)
            print(f"  Computing idio ranking B{beta_window}_M{mom_window}...", end="", flush=True)
            ranking = compute_idiosyncratic_momentum(closes, beta_window, mom_window)
            ranking_cache[key] = ranking
            print(" done")

            warmup = max(beta_window, mom_window) + 10

            for rebal_freq in [3, 5, 7, 14]:
                for n_long in [3, 4, 5]:
                    res = run_xs_factor(closes, ranking, rebal_freq, n_long,
                                        warmup=warmup)
                    tag = f"B{beta_window}_M{mom_window}_R{rebal_freq}_N{n_long}"
                    results.append({
                        "tag": tag, "beta_window": beta_window,
                        "mom_window": mom_window, "rebal": rebal_freq,
                        "n_long": n_long,
                        **{k: v for k, v in res.items() if k != "equity"},
                    })
                    if res["sharpe"] > 0.5:
                        print(f"  ** {tag}: Sharpe {res['sharpe']:.2f}, "
                              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")

    df = pd.DataFrame(results)
    positive = df[df["sharpe"] > 0]
    print(f"\n  Total params: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.2f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.2f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}")

    return df, closes


# ═══════════════════════════════════════════════════════════════════════
# H-034: Funding Rate as BTC Timing Signal
# ═══════════════════════════════════════════════════════════════════════

def h034_funding_timing(daily_data):
    """
    Use BTC funding rate level as a TIMING signal for BTC directional trades.
    High funding = crowded longs = contrarian short signal.
    Low/negative funding = oversold = long signal.
    Different from H-011 (carry) and H-009 (price trend).
    """
    print("\n" + "=" * 70)
    print("H-034: FUNDING RATE AS BTC TIMING SIGNAL")
    print("=" * 70)

    # Load BTC funding data
    data_dir = ROOT / "data"
    btc_funding_path = data_dir / "BTC_USDT_USDT_funding.parquet"
    if not btc_funding_path.exists():
        # Try alternative name
        btc_funding_path = data_dir / "BTC_USDT_funding_rates.parquet"
    if not btc_funding_path.exists():
        print("  No BTC funding data. Skipping.")
        return None

    funding_df = pd.read_parquet(btc_funding_path)
    col = "funding_rate" if "funding_rate" in funding_df.columns else "fundingRate"
    # Resample to daily
    daily_funding = funding_df[col].resample("1D").sum()

    btc_daily = daily_data.get("BTC/USDT")
    if btc_daily is None:
        print("  No BTC daily data. Skipping.")
        return None

    btc_close = btc_daily["close"]

    # Align
    common = daily_funding.index.intersection(btc_close.index)
    daily_funding = daily_funding.loc[common]
    btc_close = btc_close.loc[common]
    print(f"  BTC data: {len(common)} daily bars")
    print(f"  Funding rate range: {daily_funding.min():.6f} to {daily_funding.max():.6f}")
    print(f"  Mean daily funding: {daily_funding.mean():.6f}")

    btc_rets = btc_close.pct_change()

    results = []
    for fr_window in [3, 7, 14, 27, 45]:
        rolling_fr = daily_funding.rolling(fr_window).mean()

        for pct_long in [10, 20, 25, 30, 40]:
            for pct_short in [70, 75, 80, 90]:
                if pct_long >= pct_short:
                    continue

                # Compute percentile thresholds using expanding window (no lookahead)
                n = len(btc_close)
                equity = np.zeros(n)
                equity[0] = INITIAL_CAPITAL
                position = 0  # 1=long, -1=short, 0=flat
                trades = 0
                warmup = max(fr_window + 30, 60)  # need enough history for percentiles

                for i in range(1, n):
                    if i >= warmup:
                        hist_fr = rolling_fr.iloc[:i].dropna()
                        if len(hist_fr) < 30:
                            equity[i] = equity[i - 1]
                            continue

                        current_fr = rolling_fr.iloc[i - 1]
                        if pd.isna(current_fr):
                            equity[i] = equity[i - 1]
                            continue

                        low_thresh = np.percentile(hist_fr, pct_long)
                        high_thresh = np.percentile(hist_fr, pct_short)

                        new_pos = position
                        if current_fr <= low_thresh:
                            new_pos = 1  # Low funding = oversold = long
                        elif current_fr >= high_thresh:
                            new_pos = -1  # High funding = crowded = short
                        # Stay in position otherwise (hysteresis)

                        if new_pos != position:
                            trades += 1
                            fee = BASE_FEE + SLIPPAGE_BPS / 10_000
                            equity[i] = equity[i - 1] * (1 + position * btc_rets.iloc[i] - fee)
                            position = new_pos
                        else:
                            equity[i] = equity[i - 1] * (1 + position * btc_rets.iloc[i])
                    else:
                        equity[i] = equity[i - 1]

                eq_series = pd.Series(equity, index=btc_close.index)
                metrics = compute_metrics(eq_series)
                tag = f"F{fr_window}_L{pct_long}_S{pct_short}"
                results.append({
                    "tag": tag, "fr_window": fr_window,
                    "pct_long": pct_long, "pct_short": pct_short,
                    "n_trades": trades,
                    **{k: v for k, v in metrics.items() if k != "equity"},
                })
                if metrics["sharpe"] > 0.5:
                    print(f"  ** {tag}: Sharpe {metrics['sharpe']:.2f}, "
                          f"Ann {metrics['annual_ret']:.1%}, DD {metrics['max_dd']:.1%}, "
                          f"Trades {trades}")

    df = pd.DataFrame(results)
    if len(df) == 0:
        print("  No results.")
        return None

    positive = df[df["sharpe"] > 0]
    print(f"\n  Total params: {len(df)}")
    print(f"  Positive Sharpe: {len(positive)}/{len(df)} ({len(positive)/len(df):.0%})")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  Best Sharpe: {df['sharpe'].max():.2f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']}: Sharpe {row['sharpe']:.2f}, "
              f"Ann {row['annual_ret']:.1%}, DD {row['max_dd']:.1%}, "
              f"Trades {row['n_trades']}")

    # Walk-forward for best params
    best = df.nlargest(1, "sharpe").iloc[0]
    if best["sharpe"] > 0.3:
        print(f"\n  Running walk-forward for {best['tag']}...")
        fr_window = int(best["fr_window"])
        pct_long = int(best["pct_long"])
        pct_short = int(best["pct_short"])

        rolling_fr = daily_funding.rolling(fr_window).mean()
        n = len(btc_close)
        n_folds = 6
        test_days = 80
        train_days = 180
        fold_results = []

        for fold in range(n_folds):
            test_end = n - fold * test_days
            test_start = test_end - test_days
            if test_start - train_days < 0:
                break

            # Use only data up to test_end for percentile computation
            test_eq = np.zeros(test_days)
            test_eq[0] = INITIAL_CAPITAL
            position = 0
            trades_fold = 0

            for j in range(1, test_days):
                idx = test_start + j
                if idx >= n:
                    break

                # Percentiles from training window only (no lookahead)
                train_fr = rolling_fr.iloc[test_start - train_days:test_start + j].dropna()
                if len(train_fr) < 30:
                    test_eq[j] = test_eq[j - 1]
                    continue

                current_fr = rolling_fr.iloc[idx - 1]
                if pd.isna(current_fr):
                    test_eq[j] = test_eq[j - 1]
                    continue

                low_thresh = np.percentile(train_fr, pct_long)
                high_thresh = np.percentile(train_fr, pct_short)

                new_pos = position
                if current_fr <= low_thresh:
                    new_pos = 1
                elif current_fr >= high_thresh:
                    new_pos = -1

                if new_pos != position:
                    trades_fold += 1
                    fee = BASE_FEE + SLIPPAGE_BPS / 10_000
                    test_eq[j] = test_eq[j - 1] * (1 + position * btc_rets.iloc[idx] - fee)
                    position = new_pos
                else:
                    test_eq[j] = test_eq[j - 1] * (1 + position * btc_rets.iloc[idx])

            eq_s = pd.Series(test_eq[:min(test_days, n - test_start)])
            eq_s = eq_s[eq_s > 0]
            if len(eq_s) < 20:
                continue
            rets = eq_s.pct_change().dropna()
            sh = round(sharpe_ratio(rets, periods_per_year=365), 2) if len(rets) > 10 else -99

            fold_results.append({
                "fold": fold + 1,
                "sharpe": sh,
                "trades": trades_fold,
            })
            print(f"    Fold {fold+1}: Sharpe {sh:.2f}, Trades {trades_fold}")

        if fold_results:
            wf_df = pd.DataFrame(fold_results)
            pos = (wf_df["sharpe"] > 0).sum()
            print(f"    WF result: {pos}/{len(wf_df)} positive, "
                  f"mean {wf_df['sharpe'].mean():.2f}")

    # Correlation with H-009 (BTC EMA returns)
    if best["sharpe"] > 0.3:
        print("\n  Computing correlation with H-009 and H-012...")
        # Run best funding timing strategy
        fr_window = int(best["fr_window"])
        pct_long = int(best["pct_long"])
        pct_short = int(best["pct_short"])
        rolling_fr = daily_funding.rolling(fr_window).mean()

        n = len(btc_close)
        equity_034 = np.zeros(n)
        equity_034[0] = INITIAL_CAPITAL
        position = 0
        warmup_034 = max(fr_window + 30, 60)

        for i in range(1, n):
            if i >= warmup_034:
                hist_fr = rolling_fr.iloc[:i].dropna()
                if len(hist_fr) < 30:
                    equity_034[i] = equity_034[i - 1]
                    continue
                current_fr = rolling_fr.iloc[i - 1]
                if pd.isna(current_fr):
                    equity_034[i] = equity_034[i - 1]
                    continue
                low_thresh = np.percentile(hist_fr, pct_long)
                high_thresh = np.percentile(hist_fr, pct_short)
                new_pos = position
                if current_fr <= low_thresh:
                    new_pos = 1
                elif current_fr >= high_thresh:
                    new_pos = -1
                if new_pos != position:
                    fee = BASE_FEE + SLIPPAGE_BPS / 10_000
                    equity_034[i] = equity_034[i - 1] * (1 + position * btc_rets.iloc[i] - fee)
                    position = new_pos
                else:
                    equity_034[i] = equity_034[i - 1] * (1 + position * btc_rets.iloc[i])
            else:
                equity_034[i] = equity_034[i - 1]

        eq_034 = pd.Series(equity_034, index=btc_close.index)
        rets_034 = eq_034.pct_change().dropna()

        # H-009: BTC EMA(5/40) returns
        ema5 = btc_close.ewm(span=5, adjust=False).mean()
        ema40 = btc_close.ewm(span=40, adjust=False).mean()
        signal_009 = (ema5 > ema40).astype(float) * 2 - 1  # +1 or -1
        rets_009 = signal_009.shift(1) * btc_rets
        rets_009 = rets_009.dropna()

        common = rets_034.index.intersection(rets_009.index)
        if len(common) > 50:
            corr_009 = rets_034.loc[common].corr(rets_009.loc[common])
            print(f"  H-034 ↔ H-009 correlation: {corr_009:.3f}")

    return df


# ═══════════════════════════════════════════════════════════════════════
# H-033 validation helpers
# ═══════════════════════════════════════════════════════════════════════

def h033_correlation_analysis(closes, best_params):
    """Compute correlation with H-012 (momentum) and H-009 (BTC EMA)."""
    beta_window = int(best_params["beta_window"])
    mom_window = int(best_params["mom_window"])
    rebal = int(best_params["rebal"])
    n_long = int(best_params["n_long"])

    ranking = compute_idiosyncratic_momentum(closes, beta_window, mom_window)
    warmup = max(beta_window, mom_window) + 10
    res_033 = run_xs_factor(closes, ranking, rebal, n_long, warmup=warmup)

    # H-012 (raw momentum)
    mom_ranking = closes.pct_change(60)
    res_h012 = run_xs_factor(closes, mom_ranking, 5, 4, warmup=65)

    eq_033 = res_033["equity"]
    eq_h012 = res_h012["equity"]

    rets_033 = eq_033.pct_change().dropna()
    rets_h012 = eq_h012.pct_change().dropna()

    common = rets_033.index.intersection(rets_h012.index)
    corr_h012 = rets_033.loc[common].corr(rets_h012.loc[common])
    print(f"  H-033 ↔ H-012 (momentum) correlation: {corr_h012:.3f}")

    # H-021 (volume momentum)
    daily_rets = closes.pct_change()
    vol_short = closes["BTC/USDT"].rolling(5).apply(lambda x: x.sum(), raw=True)  # placeholder
    # Use volume data for H-021 comparison
    vol_ratio = pd.DataFrame(index=closes.index, columns=closes.columns, dtype=float)
    for sym in closes.columns:
        # Approximate volume momentum using price volatility as proxy
        vol_5 = daily_rets[sym].abs().rolling(5).mean()
        vol_20 = daily_rets[sym].abs().rolling(20).mean()
        vol_ratio[sym] = vol_5 / vol_20
    res_h021 = run_xs_factor(closes, vol_ratio, 3, 4, warmup=25)
    eq_h021 = res_h021["equity"]
    rets_h021 = eq_h021.pct_change().dropna()
    common2 = rets_033.index.intersection(rets_h021.index)
    corr_h021 = rets_033.loc[common2].corr(rets_h021.loc[common2])
    print(f"  H-033 ↔ H-021 (vol momentum proxy) correlation: {corr_h021:.3f}")

    # H-009 (BTC EMA)
    btc_close = closes["BTC/USDT"]
    btc_rets = btc_close.pct_change()
    ema5 = btc_close.ewm(span=5, adjust=False).mean()
    ema40 = btc_close.ewm(span=40, adjust=False).mean()
    signal_009 = (ema5 > ema40).astype(float) * 2 - 1
    rets_009 = (signal_009.shift(1) * btc_rets).dropna()
    common3 = rets_033.index.intersection(rets_009.index)
    corr_h009 = rets_033.loc[common3].corr(rets_009.loc[common3])
    print(f"  H-033 ↔ H-009 (BTC EMA) correlation: {corr_h009:.3f}")

    return {
        "corr_h012": round(corr_h012, 3),
        "corr_h021": round(corr_h021, 3),
        "corr_h009": round(corr_h009, 3),
    }


def h033_fee_sensitivity(closes, best_params):
    """Test fee sensitivity at 1x, 2x, 3x, 5x fees."""
    beta_window = int(best_params["beta_window"])
    mom_window = int(best_params["mom_window"])
    rebal = int(best_params["rebal"])
    n_long = int(best_params["n_long"])
    warmup = max(beta_window, mom_window) + 10

    ranking = compute_idiosyncratic_momentum(closes, beta_window, mom_window)

    print("\n  Fee sensitivity:")
    for fee_mult in [1.0, 2.0, 3.0, 5.0]:
        res = run_xs_factor(closes, ranking, rebal, n_long,
                            warmup=warmup, fee_multiplier=fee_mult)
        print(f"    {fee_mult:.0f}x fees: Sharpe {res['sharpe']:.2f}, "
              f"Ann {res['annual_ret']:.1%}, DD {res['max_dd']:.1%}")


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Loading data...")
    daily = load_all_data()
    print(f"Loaded {len(daily)} assets\n")

    # ── H-033: Idiosyncratic Momentum ──
    print("█" * 70)
    print("H-033: IDIOSYNCRATIC MOMENTUM (Alpha Momentum)")
    print("█" * 70)
    h033_results, h033_closes = h033_idiosyncratic_momentum(daily)

    if h033_results is not None and len(h033_results) > 0:
        pct_positive = (h033_results["sharpe"] > 0).mean()
        print(f"\n  H-033 verdict: {pct_positive:.0%} positive")

        if pct_positive >= 0.4:
            best = h033_results.nlargest(1, "sharpe").iloc[0]
            beta_w = int(best["beta_window"])
            mom_w = int(best["mom_window"])
            print(f"\n  Running walk-forward for best: B{beta_w}_M{mom_w}_R{int(best['rebal'])}_N{int(best['n_long'])}...")

            def h033_ranking_fn(c):
                return compute_idiosyncratic_momentum(c, beta_w, mom_w)

            wf = rolling_walk_forward(
                h033_closes,
                h033_ranking_fn,
                {"rebal_freq": int(best["rebal"]), "n_long": int(best["n_long"])},
                n_folds=6, train_days=360, test_days=80,
            )

            # Correlation analysis
            print("\n  Correlation analysis:")
            corrs = h033_correlation_analysis(h033_closes, best)

            # Fee sensitivity
            h033_fee_sensitivity(h033_closes, best)
        else:
            print("  H-033 REJECTED: insufficient positive rate.")
    else:
        print("  H-033: No results.")

    # ── H-034: Funding Rate Timing ──
    print("\n" + "█" * 70)
    print("H-034: FUNDING RATE AS BTC TIMING SIGNAL")
    print("█" * 70)
    h034_results = h034_funding_timing(daily)

    # ── Summary ──
    print("\n" + "█" * 70)
    print("SESSION SUMMARY")
    print("█" * 70)

    for name, df in [("H-033 IdioMom", h033_results),
                     ("H-034 FundTiming", h034_results)]:
        if df is not None and len(df) > 0:
            pos_pct = (df["sharpe"] > 0).mean()
            print(f"\n  {name}:")
            print(f"    Params tested: {len(df)}")
            print(f"    Positive Sharpe: {pos_pct:.0%}")
            print(f"    Mean Sharpe: {df['sharpe'].mean():.2f}")
            print(f"    Best Sharpe: {df['sharpe'].max():.2f}")
        else:
            print(f"\n  {name}: No results")

    print("\nDone.")
