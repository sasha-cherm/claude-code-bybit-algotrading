"""
Cross-Sectional Factor Research: H-027, H-028, H-029

H-027: Lead-Lag Cross-Sectional Factor
  - BTC moves first, altcoins follow with a lag
  - Lag score = BTC_return - altcoin_return over past N hours
  - Long assets that haven't responded to BTC, short over-responders

H-028: Volume Trend Change Factor
  - Assets with accelerating volume -> continuation signal
  - Proxy for open interest change (OI data not cached locally)
  - Rank by volume trend ratio (short MA / long MA of volume)

H-029: Hourly Cross-Sectional Momentum
  - Higher-frequency version of H-012 (daily 60d momentum)
  - Rank assets by past 24h-168h returns using 1h bars
  - Check if different from daily momentum

All use 1h data for 14 assets. Fee: 0.1% per trade (0.2% round trip).
Backtester is vectorized for speed.
"""

import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

ASSETS = ['BTC', 'ETH', 'SOL', 'SUI', 'XRP', 'DOGE', 'AVAX', 'LINK',
          'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM']

BASE_FEE = 0.001       # 0.1% per trade
SLIPPAGE_BPS = 2.0     # 2 bps slippage
INITIAL_CAPITAL = 10_000.0
HOURS_PER_YEAR = 8760


# ═══════════════════════════════════════════════════════════════════════════
# Data Loading
# ═══════════════════════════════════════════════════════════════════════════

def load_hourly_data():
    """Load 1h parquet data for all assets."""
    data_dir = ROOT / 'data'
    prices = {}
    volumes = {}
    for a in ASSETS:
        path = data_dir / f'{a}_USDT_1h.parquet'
        if not path.exists():
            print(f"  {a}: no data file found, skipping")
            continue
        df = pd.read_parquet(path)
        if len(df) < 500:
            print(f"  {a}: insufficient data ({len(df)} bars), skipping")
            continue
        prices[a] = df['close']
        volumes[a] = df['volume']
        print(f"  {a}: {len(df)} bars, {df.index[0].date()} to {df.index[-1].date()}")

    price_df = pd.DataFrame(prices)
    volume_df = pd.DataFrame(volumes)
    price_df = price_df.dropna(how='all').ffill(limit=5).dropna()
    volume_df = volume_df.reindex(price_df.index).ffill(limit=5).fillna(0)

    print(f"\n  Final: {len(price_df.columns)} assets, "
          f"{len(price_df)} bars ({len(price_df)/24:.0f} days)")
    return price_df, volume_df


# ═══════════════════════════════════════════════════════════════════════════
# Vectorized cross-sectional backtester
# ═══════════════════════════════════════════════════════════════════════════

def run_xs_vectorized(price_df, ranking_df, rebal_hours, n_long, n_short=None,
                      fee_multiplier=1.0, warmup_hours=168):
    """
    Vectorized cross-sectional L/S backtester at hourly frequency.
    Uses numpy arrays for speed.
    """
    if n_short is None:
        n_short = n_long

    prices = price_df.values  # (T, N)
    ranks = ranking_df.values
    T, N = prices.shape
    fee_rate = BASE_FEE * fee_multiplier
    slippage = SLIPPAGE_BPS / 10_000

    # Compute hourly returns matrix
    returns = np.zeros_like(prices)
    returns[1:] = prices[1:] / prices[:-1] - 1

    # Determine rebalance points
    rebal_mask = np.zeros(T, dtype=bool)
    rebal_indices = np.arange(warmup_hours, T, rebal_hours)
    rebal_mask[rebal_indices] = True

    # Build weight matrix
    weights = np.zeros((T, N))
    prev_w = np.zeros(N)
    trades = 0

    for t in rebal_indices:
        if t >= T:
            break
        # Use lagged ranking (t-1)
        rank_row = ranks[t - 1]
        valid_mask = ~np.isnan(rank_row)
        n_valid = valid_mask.sum()

        if n_valid < n_long + n_short:
            weights[t] = prev_w
            continue

        # Sort by rank descending
        valid_indices = np.where(valid_mask)[0]
        sorted_idx = valid_indices[np.argsort(-rank_row[valid_indices])]

        new_w = np.zeros(N)
        for k in range(n_long):
            new_w[sorted_idx[k]] = 1.0 / n_long
        for k in range(n_short):
            new_w[sorted_idx[-(k+1)]] = -1.0 / n_short

        weight_change = np.abs(new_w - prev_w)
        trades += int((weight_change > 0.01).sum())

        weights[t] = new_w
        prev_w = new_w

    # Forward-fill weights between rebalances
    for t in range(1, T):
        if not rebal_mask[t]:
            weights[t] = weights[t - 1]

    # Compute portfolio returns
    port_returns = np.sum(weights * returns, axis=1)

    # Subtract fees at rebalance points
    for idx in range(len(rebal_indices)):
        t = rebal_indices[idx]
        if t >= T:
            break
        if idx == 0:
            prev_t_w = np.zeros(N)
        else:
            prev_rebal = rebal_indices[idx - 1]
            if prev_rebal < T:
                prev_t_w = weights[prev_rebal]
            else:
                prev_t_w = np.zeros(N)

        turnover = np.abs(weights[t] - prev_t_w).sum() / 2
        fee_drag = turnover * (fee_rate + slippage)
        port_returns[t] -= fee_drag

    # Build equity curve
    equity = INITIAL_CAPITAL * np.cumprod(1 + port_returns)

    eq_series = pd.Series(equity, index=price_df.index)
    eq = eq_series[eq_series > 0]
    if len(eq) < 100:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0,
                "n_trades": trades, "equity": eq_series}

    rets = eq.pct_change().dropna()
    return {
        "sharpe": round(sharpe_ratio(rets, periods_per_year=HOURS_PER_YEAR), 3),
        "annual_ret": round(annual_return(eq, periods_per_year=HOURS_PER_YEAR), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "n_trades": trades,
        "equity": eq_series,
    }


# ═══════════════════════════════════════════════════════════════════════════
# H-027: Lead-Lag Cross-Sectional Factor
# ═══════════════════════════════════════════════════════════════════════════

def compute_leadlag_ranking(price_df, lookback_hours):
    """Lag score = BTC_return - altcoin_return. High = altcoin lagging = go long."""
    returns = price_df.pct_change(lookback_hours)
    btc_col = price_df.columns.get_loc('BTC')
    btc_ret = returns.iloc[:, btc_col]

    ranking = pd.DataFrame(index=price_df.index, columns=price_df.columns, dtype=float)
    for col in price_df.columns:
        if col == 'BTC':
            ranking[col] = 0.0
        else:
            ranking[col] = btc_ret.values - returns[col].values
    return ranking


def h027_leadlag(price_df):
    print("\n" + "=" * 70)
    print("H-027: LEAD-LAG CROSS-SECTIONAL FACTOR")
    print("=" * 70)

    results = []
    lookbacks = [4, 8, 12, 24, 48]
    rebals = [4, 8, 12, 24, 48]
    n_longs = [3, 4, 5]

    total = len(lookbacks) * len(rebals) * len(n_longs)
    print(f"  Testing {total} parameter combinations...")

    for lookback in lookbacks:
        ranking = compute_leadlag_ranking(price_df, lookback)
        for rebal in rebals:
            for n_long in n_longs:
                warmup = max(lookback + 24, 168)
                res = run_xs_vectorized(price_df, ranking, rebal, n_long,
                                        warmup_hours=warmup)
                results.append({
                    "tag": f"LB{lookback}_R{rebal}_N{n_long}",
                    "lookback": lookback, "rebal": rebal, "n_long": n_long,
                    "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
                    "max_dd": res["max_dd"], "n_trades": res["n_trades"],
                })

    df = pd.DataFrame(results)
    pos = df[df["sharpe"] > 0]
    print(f"\n  Total: {len(df)} | Positive Sharpe: {len(pos)}/{len(df)} ({100*len(pos)/len(df):.0f}%)")
    print(f"  Mean: {df['sharpe'].mean():.3f} | Median: {df['sharpe'].median():.3f} | Best: {df['sharpe'].max():.3f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, r in top5.iterrows():
        print(f"    {r['tag']}: Sharpe {r['sharpe']:.3f}, Ann {r['annual_ret']:.1%}, DD {r['max_dd']:.1%}")

    return df


# ═══════════════════════════════════════════════════════════════════════════
# H-028: Volume Trend Change Factor
# ═══════════════════════════════════════════════════════════════════════════

def compute_volume_trend_ranking(volume_df, short_window, long_window):
    """Volume trend ratio = short_MA / long_MA. High = accelerating volume."""
    vol_short = volume_df.rolling(short_window, min_periods=short_window//2).mean()
    vol_long = volume_df.rolling(long_window, min_periods=long_window//2).mean()
    vol_long = vol_long.replace(0, np.nan)
    return vol_short / vol_long


def h028_volume_trend(price_df, volume_df):
    print("\n" + "=" * 70)
    print("H-028: VOLUME TREND CHANGE FACTOR (OI Proxy)")
    print("=" * 70)

    results = []
    short_ws = [6, 12, 24, 48]
    long_ws = [48, 72, 120, 168, 336]
    rebals = [12, 24, 48, 72]
    n_longs = [3, 4, 5]

    # Count valid combos
    combos = [(sw, lw, rb, nl)
              for sw in short_ws for lw in long_ws
              for rb in rebals for nl in n_longs
              if lw > sw * 2]
    print(f"  Testing {len(combos)} parameter combinations...")

    for sw, lw, rebal, n_long in combos:
        ranking = compute_volume_trend_ranking(volume_df, sw, lw)
        warmup = max(lw + 24, 168)
        res = run_xs_vectorized(price_df, ranking, rebal, n_long,
                                warmup_hours=warmup)
        results.append({
            "tag": f"VS{sw}_VL{lw}_R{rebal}_N{n_long}",
            "short_w": sw, "long_w": lw, "rebal": rebal, "n_long": n_long,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "n_trades": res["n_trades"],
        })

    df = pd.DataFrame(results)
    pos = df[df["sharpe"] > 0]
    print(f"\n  Total: {len(df)} | Positive Sharpe: {len(pos)}/{len(df)} ({100*len(pos)/len(df):.0f}%)")
    print(f"  Mean: {df['sharpe'].mean():.3f} | Median: {df['sharpe'].median():.3f} | Best: {df['sharpe'].max():.3f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, r in top5.iterrows():
        print(f"    {r['tag']}: Sharpe {r['sharpe']:.3f}, Ann {r['annual_ret']:.1%}, DD {r['max_dd']:.1%}")

    return df


# ═══════════════════════════════════════════════════════════════════════════
# H-029: Hourly Cross-Sectional Momentum
# ═══════════════════════════════════════════════════════════════════════════

def compute_hourly_mom_ranking(price_df, lookback_hours):
    """Past N-hour return. Classic momentum at hourly frequency."""
    return price_df.pct_change(lookback_hours)


def h029_hourly_momentum(price_df):
    print("\n" + "=" * 70)
    print("H-029: HOURLY CROSS-SECTIONAL MOMENTUM")
    print("=" * 70)

    results = []
    lookbacks = [24, 48, 72, 120, 168, 336]
    rebals = [4, 8, 12, 24, 48]
    n_longs = [3, 4, 5]

    total = len(lookbacks) * len(rebals) * len(n_longs)
    print(f"  Testing {total} parameter combinations...")

    for lookback in lookbacks:
        ranking = compute_hourly_mom_ranking(price_df, lookback)
        for rebal in rebals:
            for n_long in n_longs:
                warmup = max(lookback + 24, 168)
                res = run_xs_vectorized(price_df, ranking, rebal, n_long,
                                        warmup_hours=warmup)
                results.append({
                    "tag": f"LB{lookback}_R{rebal}_N{n_long}",
                    "lookback": lookback, "rebal": rebal, "n_long": n_long,
                    "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
                    "max_dd": res["max_dd"], "n_trades": res["n_trades"],
                })

    df = pd.DataFrame(results)
    pos = df[df["sharpe"] > 0]
    print(f"\n  Total: {len(df)} | Positive Sharpe: {len(pos)}/{len(df)} ({100*len(pos)/len(df):.0f}%)")
    print(f"  Mean: {df['sharpe'].mean():.3f} | Median: {df['sharpe'].median():.3f} | Best: {df['sharpe'].max():.3f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, r in top5.iterrows():
        print(f"    {r['tag']}: Sharpe {r['sharpe']:.3f}, Ann {r['annual_ret']:.1%}, DD {r['max_dd']:.1%}")

    return df


# ═══════════════════════════════════════════════════════════════════════════
# Walk-Forward Validation
# ═══════════════════════════════════════════════════════════════════════════

def walk_forward(price_df, ranking_fn, rebal_hours, n_long, n_short,
                 train_days=360, test_days=80, n_folds=6, label=""):
    """Rolling walk-forward OOS test on hourly data."""
    test_hours = test_days * 24
    T = len(price_df)

    print(f"\n  WF ({label}): {n_folds} folds, {train_days}d train, {test_days}d test")
    fold_results = []

    for fold in range(n_folds):
        test_end = T - fold * test_hours
        test_start = test_end - test_hours
        if test_start < 168:
            break

        test_prices = price_df.iloc[test_start:test_end]
        ranking_full = ranking_fn(price_df.iloc[:test_end])
        ranking_test = ranking_full.iloc[test_start:test_end]

        if len(test_prices) < 100:
            continue

        result = run_xs_vectorized(test_prices, ranking_test, rebal_hours,
                                   n_long, n_short, warmup_hours=0)

        fold_results.append({
            "fold": fold,
            "start": str(test_prices.index[0].date()),
            "end": str(test_prices.index[-1].date()),
            "sharpe": result["sharpe"],
            "annual_ret": result["annual_ret"],
            "max_dd": result["max_dd"],
        })

        sign = "+" if result["sharpe"] > 0 else " "
        print(f"    Fold {fold}: {test_prices.index[0].date()} -> "
              f"{test_prices.index[-1].date()}, "
              f"Sharpe {sign}{result['sharpe']:.3f}, "
              f"ret {result['annual_ret']*100:+.1f}%")

    if not fold_results:
        print("    No folds completed!")
        return None

    df = pd.DataFrame(fold_results)
    n_pos = (df["sharpe"] > 0).sum()
    print(f"    => {n_pos}/{len(df)} positive, "
          f"mean {df['sharpe'].mean():.3f}, median {df['sharpe'].median():.3f}")
    return df


# ═══════════════════════════════════════════════════════════════════════════
# Fee Sensitivity
# ═══════════════════════════════════════════════════════════════════════════

def fee_sensitivity(price_df, ranking_df, rebal_hours, n_long, n_short,
                    warmup, label=""):
    print(f"\n  Fee Sensitivity ({label}):")
    results = []
    for mult in [1.0, 2.0, 3.0, 5.0]:
        r = run_xs_vectorized(price_df, ranking_df, rebal_hours, n_long, n_short,
                              fee_multiplier=mult, warmup_hours=warmup)
        results.append({"fee_mult": mult, "sharpe": r["sharpe"],
                        "annual_ret": r["annual_ret"]})
        print(f"    {mult}x: Sharpe {r['sharpe']:.3f}, ret {r['annual_ret']*100:+.1f}%")
    return results


# ═══════════════════════════════════════════════════════════════════════════
# Correlation Analysis
# ═══════════════════════════════════════════════════════════════════════════

def compute_existing_equities(price_df, volume_df):
    """Reconstruct approximate equity curves for existing strategies."""
    equities = {}

    # H-009: BTC EMA crossover
    btc = price_df['BTC']
    ema5 = btc.ewm(span=5*24).mean()
    ema40 = btc.ewm(span=40*24).mean()
    signal = (ema5 > ema40).astype(float) * 2 - 1
    h009_ret = signal.shift(1) * btc.pct_change()
    equities['H-009'] = (1 + h009_ret.fillna(0)).cumprod() * INITIAL_CAPITAL

    # H-012: 60d momentum
    mom_ranking = price_df.pct_change(60 * 24)
    equities['H-012'] = run_xs_vectorized(
        price_df, mom_ranking, 24, 4, 4, warmup_hours=60*24+48)['equity']

    # H-019: Low-vol
    vol_ranking = -price_df.pct_change().rolling(20 * 24).std()
    equities['H-019'] = run_xs_vectorized(
        price_df, vol_ranking, 21*24, 3, 3, warmup_hours=21*24+48)['equity']

    # H-021: Volume momentum
    vs = volume_df.rolling(5*24).mean()
    vl = volume_df.rolling(20*24).mean().replace(0, np.nan)
    equities['H-021'] = run_xs_vectorized(
        price_df, vs/vl, 3*24, 4, 4, warmup_hours=20*24+48)['equity']

    return equities


def correlation_with_existing(new_eq, existing_eqs, label=""):
    print(f"\n  Corr ({label}):")
    new_rets = new_eq.pct_change().dropna()
    results = {}
    for name, eq in existing_eqs.items():
        ex_rets = eq.pct_change().dropna()
        common = new_rets.index.intersection(ex_rets.index)
        if len(common) < 200:
            results[name] = np.nan
            continue
        c = round(new_rets.loc[common].corr(ex_rets.loc[common]), 3)
        results[name] = c
        flag = " *** HIGH" if abs(c) > 0.4 else ""
        print(f"    {name}: {c:.3f}{flag}")
    return results


def h029_vs_h012_overlap(price_df):
    """Check rank correlation between hourly and daily momentum."""
    print("\n  H-029 vs H-012 Overlap:")
    daily_mom = price_df.pct_change(1440)

    for lb in [24, 48, 72, 120, 168, 336]:
        hourly_mom = price_df.pct_change(lb)
        rank_corrs = []
        for i in range(max(1440, lb) + 100, len(price_df), 24):
            h_ranks = hourly_mom.iloc[i].rank()
            d_ranks = daily_mom.iloc[i].rank()
            valid = h_ranks.dropna().index.intersection(d_ranks.dropna().index)
            if len(valid) >= 8:
                rc = h_ranks[valid].corr(d_ranks[valid])
                if not np.isnan(rc):
                    rank_corrs.append(rc)
        if rank_corrs:
            print(f"    LB{lb}h vs 1440h: rank corr = {np.mean(rank_corrs):.3f} (n={len(rank_corrs)})")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("CROSS-SECTIONAL FACTOR RESEARCH: H-027, H-028, H-029")
    print("=" * 70)

    print("\nLoading hourly data...")
    price_df, volume_df = load_hourly_data()

    if len(price_df.columns) < 10:
        print("ERROR: Need at least 10 assets.")
        sys.exit(1)

    # ═══════════════════════════════════════════════════════════
    # PHASE 1: IN-SAMPLE PARAMETER SWEEPS
    # ═══════════════════════════════════════════════════════════
    print("\n" + "#" * 70)
    print("# PHASE 1: IN-SAMPLE PARAMETER SWEEPS")
    print("#" * 70)

    df_027 = h027_leadlag(price_df)
    df_028 = h028_volume_trend(price_df, volume_df)
    df_029 = h029_hourly_momentum(price_df)

    print("\n" + "=" * 70)
    print("PHASE 1 SUMMARY")
    print("=" * 70)
    for name, df in [("H-027 LeadLag", df_027),
                     ("H-028 VolTrend", df_028),
                     ("H-029 HrlyMom", df_029)]:
        pct = (df["sharpe"] > 0).mean()
        print(f"  {name}: {len(df)} params, {pct:.0%} positive, "
              f"mean {df['sharpe'].mean():.3f}, best {df['sharpe'].max():.3f}")

    # ═══════════════════════════════════════════════════════════
    # PHASE 2: WALK-FORWARD VALIDATION
    # ═══════════════════════════════════════════════════════════
    print("\n" + "#" * 70)
    print("# PHASE 2: WALK-FORWARD VALIDATION")
    print("#" * 70)

    wf_results = {}

    # H-027
    for _, row in df_027.nlargest(3, "sharpe").iterrows():
        lb, rb, nl = int(row["lookback"]), int(row["rebal"]), int(row["n_long"])
        tag = f"LB{lb}_R{rb}_N{nl}"
        wf = walk_forward(
            price_df, lambda p, _lb=lb: compute_leadlag_ranking(p, _lb),
            rb, nl, nl, label=f"H-027 {tag}")
        if wf is not None:
            wf_results[f"H-027_{tag}"] = wf

    # H-028
    for _, row in df_028.nlargest(3, "sharpe").iterrows():
        sw, lw = int(row["short_w"]), int(row["long_w"])
        rb, nl = int(row["rebal"]), int(row["n_long"])
        tag = f"VS{sw}_VL{lw}_R{rb}_N{nl}"
        wf = walk_forward(
            price_df,
            lambda p, _sw=sw, _lw=lw: compute_volume_trend_ranking(
                volume_df.reindex(p.index).ffill().fillna(0), _sw, _lw),
            rb, nl, nl, label=f"H-028 {tag}")
        if wf is not None:
            wf_results[f"H-028_{tag}"] = wf

    # H-029
    for _, row in df_029.nlargest(3, "sharpe").iterrows():
        lb, rb, nl = int(row["lookback"]), int(row["rebal"]), int(row["n_long"])
        tag = f"LB{lb}_R{rb}_N{nl}"
        wf = walk_forward(
            price_df, lambda p, _lb=lb: compute_hourly_mom_ranking(p, _lb),
            rb, nl, nl, label=f"H-029 {tag}")
        if wf is not None:
            wf_results[f"H-029_{tag}"] = wf

    print("\n" + "=" * 70)
    print("WALK-FORWARD SUMMARY")
    print("=" * 70)
    for key, wf_df in wf_results.items():
        n_pos = (wf_df["sharpe"] > 0).sum()
        n_tot = len(wf_df)
        mean_s = wf_df["sharpe"].mean()
        passed = "PASS" if (n_pos >= 4 and mean_s > 0.5) else "FAIL"
        print(f"  {key}: {n_pos}/{n_tot} positive, mean {mean_s:.3f} [{passed}]")

    # ═══════════════════════════════════════════════════════════
    # PHASE 3: FEE SENSITIVITY
    # ═══════════════════════════════════════════════════════════
    print("\n" + "#" * 70)
    print("# PHASE 3: FEE SENSITIVITY")
    print("#" * 70)

    fee_results = {}

    # H-027 best
    b = df_027.nlargest(1, "sharpe").iloc[0]
    r027 = compute_leadlag_ranking(price_df, int(b["lookback"]))
    fee_results["H-027"] = fee_sensitivity(
        price_df, r027, int(b["rebal"]), int(b["n_long"]), int(b["n_long"]),
        max(int(b["lookback"])+24, 168), label=f"H-027 {b['tag']}")

    # H-028 best
    b = df_028.nlargest(1, "sharpe").iloc[0]
    r028 = compute_volume_trend_ranking(volume_df, int(b["short_w"]), int(b["long_w"]))
    fee_results["H-028"] = fee_sensitivity(
        price_df, r028, int(b["rebal"]), int(b["n_long"]), int(b["n_long"]),
        max(int(b["long_w"])+24, 168), label=f"H-028 {b['tag']}")

    # H-029 best
    b = df_029.nlargest(1, "sharpe").iloc[0]
    r029 = compute_hourly_mom_ranking(price_df, int(b["lookback"]))
    fee_results["H-029"] = fee_sensitivity(
        price_df, r029, int(b["rebal"]), int(b["n_long"]), int(b["n_long"]),
        max(int(b["lookback"])+24, 168), label=f"H-029 {b['tag']}")

    # ═══════════════════════════════════════════════════════════
    # PHASE 4: CORRELATION ANALYSIS
    # ═══════════════════════════════════════════════════════════
    print("\n" + "#" * 70)
    print("# PHASE 4: CORRELATION ANALYSIS")
    print("#" * 70)

    print("\n  Computing existing strategy equity curves...")
    existing_eqs = compute_existing_equities(price_df, volume_df)

    corr_results = {}

    # H-027
    b = df_027.nlargest(1, "sharpe").iloc[0]
    eq_027 = run_xs_vectorized(
        price_df, compute_leadlag_ranking(price_df, int(b["lookback"])),
        int(b["rebal"]), int(b["n_long"]), int(b["n_long"]),
        warmup_hours=max(int(b["lookback"])+24, 168))["equity"]
    corr_results["H-027"] = correlation_with_existing(eq_027, existing_eqs, "H-027")

    # H-028
    b = df_028.nlargest(1, "sharpe").iloc[0]
    eq_028 = run_xs_vectorized(
        price_df, compute_volume_trend_ranking(volume_df, int(b["short_w"]), int(b["long_w"])),
        int(b["rebal"]), int(b["n_long"]), int(b["n_long"]),
        warmup_hours=max(int(b["long_w"])+24, 168))["equity"]
    corr_results["H-028"] = correlation_with_existing(eq_028, existing_eqs, "H-028")

    # H-029
    b = df_029.nlargest(1, "sharpe").iloc[0]
    eq_029 = run_xs_vectorized(
        price_df, compute_hourly_mom_ranking(price_df, int(b["lookback"])),
        int(b["rebal"]), int(b["n_long"]), int(b["n_long"]),
        warmup_hours=max(int(b["lookback"])+24, 168))["equity"]
    corr_results["H-029"] = correlation_with_existing(eq_029, existing_eqs, "H-029")

    # H-029 vs H-012 overlap check
    h029_vs_h012_overlap(price_df)

    # Cross-correlations between new factors
    print("\n  Cross-correlations between new factors:")
    new_eqs = {"H-027": eq_027, "H-028": eq_028, "H-029": eq_029}
    new_rets = pd.DataFrame({k: v.pct_change() for k, v in new_eqs.items()}).dropna()
    if len(new_rets) > 100:
        cc = new_rets.corr()
        for i, ni in enumerate(cc.columns):
            for j, nj in enumerate(cc.columns):
                if j > i:
                    print(f"    {ni} <-> {nj}: {cc.loc[ni, nj]:.3f}")

    # ═══════════════════════════════════════════════════════════
    # FINAL VERDICT
    # ═══════════════════════════════════════════════════════════
    print("\n" + "#" * 70)
    print("# FINAL VERDICT")
    print("#" * 70)

    for hyp, df_is in [("H-027", df_027), ("H-028", df_028), ("H-029", df_029)]:
        print(f"\n  {hyp}:")
        best = df_is.nlargest(1, "sharpe").iloc[0]
        pct_pos = (df_is["sharpe"] > 0).mean()
        is_pass = pct_pos >= 0.70
        print(f"    IS: {pct_pos:.0%} positive [{'PASS' if is_pass else 'FAIL'} need >=70%]")
        print(f"    Best IS: Sharpe {best['sharpe']:.3f}, Ann {best['annual_ret']:.1%}, DD {best['max_dd']:.1%}")

        # WF
        wf_keys = [k for k in wf_results if k.startswith(hyp)]
        best_wf_mean = -99
        best_wf_df = None
        best_wf_key = ""
        for wk in wf_keys:
            m = wf_results[wk]["sharpe"].mean()
            if m > best_wf_mean:
                best_wf_mean = m
                best_wf_df = wf_results[wk]
                best_wf_key = wk
        if best_wf_df is not None:
            n_pos = (best_wf_df["sharpe"] > 0).sum()
            n_tot = len(best_wf_df)
            wf_pass = n_pos >= 4 and best_wf_mean > 0.5
            print(f"    WF ({best_wf_key}): {n_pos}/{n_tot} pos, mean {best_wf_mean:.3f} "
                  f"[{'PASS' if wf_pass else 'FAIL'}]")
        else:
            wf_pass = False
            print(f"    WF: None")

        # Fees
        if hyp in fee_results:
            s3 = [r for r in fee_results[hyp] if r["fee_mult"] == 3.0]
            fee_pass = s3[0]["sharpe"] > 0 if s3 else False
            print(f"    Fees 3x: Sharpe {s3[0]['sharpe']:.3f} [{'PASS' if fee_pass else 'FAIL'}]"
                  if s3 else f"    Fees: N/A")
        else:
            fee_pass = False

        # Correlation
        if hyp in corr_results:
            valid_corrs = [abs(v) for v in corr_results[hyp].values() if not np.isnan(v)]
            max_corr = max(valid_corrs) if valid_corrs else 0
            corr_pass = max_corr < 0.4
            print(f"    Max |corr|: {max_corr:.3f} [{'PASS' if corr_pass else 'FAIL'} need <0.4]")
        else:
            corr_pass = False

        all_pass = is_pass and wf_pass and fee_pass and corr_pass
        if all_pass:
            verdict = "CONFIRMED"
        elif pct_pos >= 0.50 and (wf_pass or best_wf_mean > 0.3):
            verdict = "PROMISING"
        else:
            verdict = "REJECTED"
        print(f"    >>> VERDICT: {verdict}")

    # Save results
    results_dir = ROOT / "strategies" / "leadlag_research"
    output = {
        "h027_is": df_027.to_dict("records"),
        "h028_is": df_028.to_dict("records"),
        "h029_is": df_029.to_dict("records"),
        "walk_forward": {k: v.to_dict("records") for k, v in wf_results.items()},
        "fee_sensitivity": fee_results,
        "correlations": corr_results,
    }
    with open(results_dir / "results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Results saved to {results_dir / 'results.json'}")
    print("\nDone.")
