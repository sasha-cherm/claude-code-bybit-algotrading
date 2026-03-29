"""
H-129: Intraday Volatility Ratio Factor (Cross-Sectional)

The ratio of Parkinson (high-low range) volatility to close-close volatility
captures the "information content" of price bars.

  - High ratio = large intraday swings relative to net move = noise/uncertainty
  - Low ratio  = clean directional moves = trend quality

Related to but different from H-076 (price efficiency), which uses a different
mathematical formulation. H-076 computes efficiency = |net change| / sum(ranges).
This factor computes the ratio of two volatility estimators.

Direction grid: test both long_low_ratio (trend quality) and long_high_ratio.

Parameter grid (50 combos per direction = 100 total):
  Lookback          : [10, 20, 30, 40, 60] days
  Rebalance freq    : [3, 5, 7] days
  N positions each  : [3, 4]
  Direction         : [long_low_ratio, long_high_ratio]

Sharpe: daily mean / daily std * sqrt(365)
Fee: 10 bps round-trip per rebalance (Bybit taker)
"""

import json
import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001          # 10 bps round-trip
FEE_RATE_5BPS = 0.0005    # 5 bps for fee sensitivity test
INITIAL_CAPITAL = 10_000.0

LOOKBACKS   = [10, 20, 30, 40, 60]
REBAL_FREQS = [3, 5, 7]
N_SIZES     = [3, 4]
DIRECTIONS  = ["long_low_ratio", "long_high_ratio"]

WF_FOLDS = 6
WF_TRAIN_DAYS = 180
WF_TEST_DAYS  = 90

IS_FRAC = 0.60  # first 60% in-sample


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_daily_data():
    """Load daily OHLCV parquet files for all assets."""
    data_dir = ROOT / "data"
    daily = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if len(df) >= 200:
                daily[sym] = df
                print(f"  {sym}: {len(df)} daily bars "
                      f"({df.index[0].date()} to {df.index[-1].date()})")
    return daily


def build_ohlc_matrices(daily: dict):
    """Build aligned open/high/low/close DataFrames."""
    opens, highs, lows, closes = {}, {}, {}, {}
    for sym, df in daily.items():
        opens[sym]  = df["open"]
        highs[sym]  = df["high"]
        lows[sym]   = df["low"]
        closes[sym] = df["close"]

    open_df  = pd.DataFrame(opens).dropna(how="all").ffill()
    high_df  = pd.DataFrame(highs).dropna(how="all").ffill()
    low_df   = pd.DataFrame(lows).dropna(how="all").ffill()
    close_df = pd.DataFrame(closes).dropna(how="all").ffill()

    # Align all to same index
    common = open_df.index.intersection(high_df.index)\
                          .intersection(low_df.index)\
                          .intersection(close_df.index)
    return open_df.loc[common], high_df.loc[common], low_df.loc[common], close_df.loc[common]


# ---------------------------------------------------------------------------
# Factor computation
# ---------------------------------------------------------------------------
def compute_intraday_vol_ratio(
    highs: pd.DataFrame,
    lows: pd.DataFrame,
    closes: pd.DataFrame,
    lookback: int,
) -> pd.DataFrame:
    """
    Compute the intraday volatility ratio for each asset.

    parkinson_vol = rolling_std(ln(high/low)) over lookback
    cc_vol = rolling_std(ln(close/prev_close)) over lookback
    intraday_ratio = parkinson_vol / cc_vol

    High ratio = noisy intraday vs. net move (noise/uncertainty).
    Low ratio = clean directional moves (trend quality).
    """
    # Parkinson: log(high/low) for each bar, then rolling std
    log_hl = np.log(highs / lows)
    # Avoid log(0) or negative: clip minimum
    log_hl = log_hl.clip(lower=1e-10)
    parkinson_vol = log_hl.rolling(window=lookback, min_periods=lookback).std()

    # Close-to-close: log(close/prev_close), then rolling std
    log_cc = np.log(closes / closes.shift(1))
    cc_vol = log_cc.rolling(window=lookback, min_periods=lookback).std()

    # Ratio, avoiding division by zero
    cc_vol_safe = cc_vol.replace(0, np.nan)
    ratio = parkinson_vol / cc_vol_safe

    return ratio


# ---------------------------------------------------------------------------
# Core backtest engine
# ---------------------------------------------------------------------------
def compute_metrics(equity_series: pd.Series) -> dict:
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99, "annual_ret": 0.0, "max_dd": 1.0, "win_rate": 0.0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    n_total = len(rets)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(365)) if rets.std() > 1e-10 else 0.0
    return {
        "sharpe": round(sharpe, 3),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "win_rate": round(n_pos / n_total, 4) if n_total > 0 else 0.0,
    }


def run_intraday_vol_factor(
    closes: pd.DataFrame,
    lookback: int,
    rebal_freq: int,
    n_long: int,
    n_short: int | None = None,
    direction: str = "long_low_ratio",
    fee_rate: float = FEE_RATE,
    pre_computed: pd.DataFrame | None = None,
    highs: pd.DataFrame | None = None,
    lows: pd.DataFrame | None = None,
) -> dict:
    """
    Run cross-sectional intraday volatility ratio strategy.

    direction = "long_low_ratio": long assets with low ratio (clean moves),
                                  short assets with high ratio (noisy).
    direction = "long_high_ratio": long assets with high ratio,
                                   short assets with low ratio.

    Returns dict with metrics + equity series.
    """
    if n_short is None:
        n_short = n_long

    if pre_computed is not None:
        vol_ratio = pre_computed
    else:
        assert highs is not None and lows is not None, \
            "Must provide high/low data or pre_computed ratio matrix"
        vol_ratio = compute_intraday_vol_ratio(highs, lows, closes, lookback)

    n = len(closes)
    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count = 0
    warmup = lookback + 5

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            sig = vol_ratio.iloc[i - 1]  # use lagged signal
            valid = sig.dropna()

            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                continue

            ranked = valid.sort_values(ascending=True)  # low ratio first

            if direction == "long_low_ratio":
                # Long the cleanest movers (low ratio), short the noisiest (high ratio)
                longs  = ranked.index[:n_long]
                shorts = ranked.index[-n_short:]
            else:
                # long_high_ratio: reverse
                longs  = ranked.index[-n_long:]
                shorts = ranked.index[:n_short]

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] =  1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover = weight_changes.sum() / 2.0
            fee_drag = turnover * fee_rate

            port_ret = (new_weights * log_rets).sum() - fee_drag
            total_trades += int((weight_changes > 0.001).sum())
            rebal_count  += 1
            prev_weights  = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"] = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"] = eq_series
    return metrics


# ---------------------------------------------------------------------------
# Full parameter scan
# ---------------------------------------------------------------------------
def run_full_scan(closes, highs, lows, subset="full"):
    """Run all parameter combos on the given data slice."""
    print(f"\n{'=' * 72}")
    print(f"H-129: INTRADAY VOLATILITY RATIO FACTOR -- Param Scan ({subset})")
    print("=" * 72)
    print(f"  Universe : {len(closes.columns)} assets, {len(closes)} days")
    print(f"  Period   : {closes.index[0].date()} to {closes.index[-1].date()}")
    print(f"  Fee      : {FEE_RATE * 10000:.0f} bps per trade (Bybit taker)")
    print(f"  Factor   : parkinson_vol / cc_vol")
    print(f"  Directions: long_low_ratio (trend quality) + long_high_ratio")

    # Pre-compute ratio matrices for each lookback
    print("\n  Pre-computing intraday vol ratio matrices...")
    ratio_cache = {}
    for lb in LOOKBACKS:
        print(f"    Lookback {lb}d ...", end=" ", flush=True)
        ratio_cache[lb] = compute_intraday_vol_ratio(highs, lows, closes, lb)
        print("done")

    results = []
    n_combos = len(LOOKBACKS) * len(REBAL_FREQS) * len(N_SIZES) * len(DIRECTIONS)
    print(f"\n  Running {n_combos} param combos...")
    for lb, rebal, n, direction in product(LOOKBACKS, REBAL_FREQS, N_SIZES, DIRECTIONS):
        dir_short = "LL" if direction == "long_low_ratio" else "LH"
        res = run_intraday_vol_factor(
            closes, lb, rebal, n,
            direction=direction,
            pre_computed=ratio_cache[lb],
        )
        tag = f"L{lb}_R{rebal}_N{n}_{dir_short}"
        results.append({
            "tag": tag, "lookback": lb, "rebal": rebal, "n": n,
            "direction": direction,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "win_rate": res["win_rate"],
            "n_trades": res["n_trades"],
        })

    df = pd.DataFrame(results)
    n_positive = (df["sharpe"] > 0).sum()
    pct_positive = n_positive / len(df) * 100
    print(f"\n  Results: {n_positive}/{len(df)} positive Sharpe ({pct_positive:.1f}%)")
    print(f"  Mean Sharpe: {df['sharpe'].mean():.3f}")
    print(f"  Median Sharpe: {df['sharpe'].median():.3f}")
    print(f"  Best: {df.loc[df['sharpe'].idxmax(), 'tag']} Sharpe={df['sharpe'].max():.3f}")

    # Break down by direction
    for direction in DIRECTIONS:
        dir_short = "LL" if direction == "long_low_ratio" else "LH"
        sub = df[df["direction"] == direction]
        n_pos_dir = (sub["sharpe"] > 0).sum()
        print(f"\n  Direction={dir_short}: {n_pos_dir}/{len(sub)} positive "
              f"({n_pos_dir/len(sub)*100:.1f}%), mean Sharpe={sub['sharpe'].mean():.3f}")

    top5 = df.nlargest(5, "sharpe")
    print("\n  Top 5:")
    for _, row in top5.iterrows():
        print(f"    {row['tag']:25s}  Sharpe={row['sharpe']:.3f}  "
              f"Ret={row['annual_ret']*100:.1f}%  DD={row['max_dd']*100:.1f}%  "
              f"WR={row['win_rate']*100:.1f}%")

    bot5 = df.nsmallest(5, "sharpe")
    print("\n  Bottom 5:")
    for _, row in bot5.iterrows():
        print(f"    {row['tag']:25s}  Sharpe={row['sharpe']:.3f}  "
              f"Ret={row['annual_ret']*100:.1f}%  DD={row['max_dd']*100:.1f}%  "
              f"WR={row['win_rate']*100:.1f}%")

    return df, results


# ---------------------------------------------------------------------------
# Walk-Forward Validation
# ---------------------------------------------------------------------------
def walk_forward(closes, highs, lows, n_folds=WF_FOLDS):
    """
    Walk-forward: 180d train, 90d test, 6 folds.
    Pick best params on train, evaluate on test.
    """
    print(f"\n  Walk-Forward Validation ({n_folds} folds, {WF_TRAIN_DAYS}d train, {WF_TEST_DAYS}d test)")
    n = len(closes)
    total_needed = WF_TRAIN_DAYS + WF_TEST_DAYS

    if n < total_needed:
        print("    Not enough data for walk-forward!")
        return pd.DataFrame()

    # Space folds evenly across available data
    available = n - total_needed
    if n_folds > 1:
        step = available // (n_folds - 1)
    else:
        step = 0

    wf_results = []
    for fold in range(n_folds):
        train_start = fold * step
        train_end   = train_start + WF_TRAIN_DAYS
        test_start  = train_end
        test_end    = min(test_start + WF_TEST_DAYS, n)

        if test_end > n or (test_end - test_start) < 30:
            continue

        tr_c = closes.iloc[train_start:train_end]
        tr_h = highs.iloc[train_start:train_end]
        tr_l = lows.iloc[train_start:train_end]

        te_c = closes.iloc[test_start:test_end]
        te_h = highs.iloc[test_start:test_end]
        te_l = lows.iloc[test_start:test_end]

        # Find best params on train
        best_sharpe = -99
        best_p = None
        for lb, rebal, nn, direction in product(LOOKBACKS, REBAL_FREQS, N_SIZES, DIRECTIONS):
            if len(tr_c) < lb + 30:
                continue
            res = run_intraday_vol_factor(
                tr_c, lb, rebal, nn,
                direction=direction,
                highs=tr_h, lows=tr_l,
            )
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_p = (lb, rebal, nn, direction)

        if best_p is None:
            continue

        lb, rebal, nn, direction = best_p
        test_res = run_intraday_vol_factor(
            te_c, lb, rebal, nn,
            direction=direction,
            highs=te_h, lows=te_l,
        )
        dir_short = "LL" if direction == "long_low_ratio" else "LH"
        wf_results.append({
            "fold": fold,
            "train_sharpe": round(best_sharpe, 3),
            "test_sharpe": test_res["sharpe"],
            "params": f"L{lb}_R{rebal}_N{nn}_{dir_short}",
            "test_ret": test_res["annual_ret"],
            "test_dd": test_res["max_dd"],
        })
        print(f"    Fold {fold}: train Sharpe={best_sharpe:.3f} -> "
              f"test Sharpe={test_res['sharpe']:.3f} ({best_p})")

    if wf_results:
        wf_df = pd.DataFrame(wf_results)
        n_pos = (wf_df["test_sharpe"] > 0).sum()
        print(f"  WF Summary: {n_pos}/{len(wf_df)} positive, "
              f"mean OOS Sharpe={wf_df['test_sharpe'].mean():.3f}")
        return wf_df
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Split-Half Stability
# ---------------------------------------------------------------------------
def split_half_test(closes, highs, lows):
    """Compute Sharpe for all params on each half of IS data, correlate."""
    mid = len(closes) // 2
    h1_c, h1_h, h1_l = closes.iloc[:mid], highs.iloc[:mid], lows.iloc[:mid]
    h2_c, h2_h, h2_l = closes.iloc[mid:], highs.iloc[mid:], lows.iloc[mid:]

    r1, r2 = [], []
    for lb, rebal, n, direction in product(LOOKBACKS, REBAL_FREQS, N_SIZES, DIRECTIONS):
        res1 = run_intraday_vol_factor(h1_c, lb, rebal, n, direction=direction,
                                        highs=h1_h, lows=h1_l)
        res2 = run_intraday_vol_factor(h2_c, lb, rebal, n, direction=direction,
                                        highs=h2_h, lows=h2_l)
        r1.append(res1["sharpe"])
        r2.append(res2["sharpe"])

    corr = np.corrcoef(r1, r2)[0, 1]
    h1_mean = float(np.mean(r1))
    h2_mean = float(np.mean(r2))
    print(f"\n  Split-Half Stability: corr = {corr:.3f}")
    print(f"    Half-1 mean Sharpe: {h1_mean:.3f}")
    print(f"    Half-2 mean Sharpe: {h2_mean:.3f}")
    return corr, h1_mean, h2_mean


# ---------------------------------------------------------------------------
# Correlation with H-076 (Price Efficiency)
# ---------------------------------------------------------------------------
def correlation_with_h076(closes, highs, lows, best_lb, best_rebal, best_n, best_dir):
    """Compute daily return correlation with H-076 price efficiency factor."""
    # H-129 equity
    res_129 = run_intraday_vol_factor(
        closes, best_lb, best_rebal, best_n,
        direction=best_dir,
        highs=highs, lows=lows,
    )
    my_rets = res_129["equity"].pct_change().dropna()

    # Replicate H-076: price efficiency, lookback 40, rebal 5, N=4
    # efficiency = |close_end/close_start - 1| / sum(high_i/low_i - 1)
    h076_lb = 40
    net_change = (closes / closes.shift(h076_lb) - 1).abs()
    daily_range = (highs / lows - 1).clip(lower=0)
    sum_range = daily_range.rolling(window=h076_lb, min_periods=h076_lb).sum()
    sum_range_safe = sum_range.replace(0, np.nan)
    efficiency = net_change / sum_range_safe

    h076_eq = np.zeros(len(closes))
    h076_eq[0] = 10000
    prev_w = pd.Series(0.0, index=closes.columns)
    warmup = 45
    for i in range(1, len(closes)):
        pt = closes.iloc[i]
        py = closes.iloc[i - 1]
        lr = np.log(pt / py)
        if i >= warmup and (i - warmup) % 5 == 0:
            sig = efficiency.iloc[i - 1].dropna()
            if len(sig) >= 8:
                ranked = sig.sort_values(ascending=False)
                new_w = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:4]:
                    new_w[s] = 1.0 / 4
                for s in ranked.index[-4:]:
                    new_w[s] = -1.0 / 4
                turnover = (new_w - prev_w).abs().sum() / 2.0
                fee_drag = turnover * FEE_RATE
                port_ret = (new_w * lr).sum() - fee_drag
                prev_w = new_w
            else:
                port_ret = (prev_w * lr).sum()
        else:
            port_ret = (prev_w * lr).sum()
        h076_eq[i] = h076_eq[i - 1] * np.exp(port_ret)

    h076_rets = pd.Series(h076_eq, index=closes.index).pct_change().dropna()

    common = my_rets.index.intersection(h076_rets.index)
    corr_076 = np.corrcoef(my_rets.loc[common].values, h076_rets.loc[common].values)[0, 1]
    print(f"\n  Correlation with H-076 (price efficiency L40_R5_N4): {corr_076:.3f}")
    return corr_076


# ---------------------------------------------------------------------------
# Correlation with H-012 (Momentum)
# ---------------------------------------------------------------------------
def correlation_with_h012(closes, highs, lows, best_lb, best_rebal, best_n, best_dir):
    """Compute daily return correlation with H-012 momentum factor."""
    res_129 = run_intraday_vol_factor(
        closes, best_lb, best_rebal, best_n,
        direction=best_dir,
        highs=highs, lows=lows,
    )
    my_rets = res_129["equity"].pct_change().dropna()

    # Replicate H-012: 60-day momentum, rebal every 5 days, N=4
    roll_ret = closes.pct_change(60)
    h012_eq = np.zeros(len(closes))
    h012_eq[0] = 10000
    prev_w = pd.Series(0.0, index=closes.columns)
    warmup = 65
    for i in range(1, len(closes)):
        pt = closes.iloc[i]
        py = closes.iloc[i - 1]
        lr = np.log(pt / py)
        if i >= warmup and (i - warmup) % 5 == 0:
            sig = roll_ret.iloc[i - 1].dropna()
            if len(sig) >= 8:
                ranked = sig.sort_values(ascending=False)
                new_w = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:4]:
                    new_w[s] = 1.0 / 4
                for s in ranked.index[-4:]:
                    new_w[s] = -1.0 / 4
                prev_w = new_w
        h012_eq[i] = h012_eq[i - 1] * np.exp((prev_w * lr).sum())
    h012_rets = pd.Series(h012_eq, index=closes.index).pct_change().dropna()

    common = my_rets.index.intersection(h012_rets.index)
    corr_012 = np.corrcoef(my_rets.loc[common].values, h012_rets.loc[common].values)[0, 1]
    print(f"\n  Correlation with H-012 (momentum L60_R5_N4): {corr_012:.3f}")
    return corr_012


# ---------------------------------------------------------------------------
# Fee sensitivity
# ---------------------------------------------------------------------------
def fee_sensitivity(closes, highs, lows, best_lb, best_rebal, best_n, best_dir):
    """Run best params with 5bps fee and check if still positive."""
    res_5bps = run_intraday_vol_factor(
        closes, best_lb, best_rebal, best_n,
        direction=best_dir,
        fee_rate=FEE_RATE_5BPS,
        highs=highs, lows=lows,
    )
    res_10bps = run_intraday_vol_factor(
        closes, best_lb, best_rebal, best_n,
        direction=best_dir,
        fee_rate=FEE_RATE,
        highs=highs, lows=lows,
    )
    print(f"\n  Fee Sensitivity (best params L{best_lb}_R{best_rebal}_N{best_n}):")
    print(f"    5 bps:  Sharpe={res_5bps['sharpe']:.3f}  Ret={res_5bps['annual_ret']*100:.1f}%")
    print(f"    10 bps: Sharpe={res_10bps['sharpe']:.3f}  Ret={res_10bps['annual_ret']*100:.1f}%")
    return {
        "sharpe_5bps": res_5bps["sharpe"],
        "ret_5bps": res_5bps["annual_ret"],
        "sharpe_10bps": res_10bps["sharpe"],
        "ret_10bps": res_10bps["annual_ret"],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 72)
    print("H-129: INTRADAY VOLATILITY RATIO FACTOR")
    print("  parkinson_vol / cc_vol  =>  noise vs. trend quality")
    print("=" * 72)

    print("\nLoading data...")
    daily = load_daily_data()
    opens, highs, lows, closes = build_ohlc_matrices(daily)
    print(f"\nClose matrix: {closes.shape}")

    n_total = len(closes)
    is_end = int(n_total * IS_FRAC)

    is_closes = closes.iloc[:is_end]
    is_highs  = highs.iloc[:is_end]
    is_lows   = lows.iloc[:is_end]

    oos_closes = closes.iloc[is_end:]
    oos_highs  = highs.iloc[is_end:]
    oos_lows   = lows.iloc[is_end:]

    print(f"\n  IS period:  {is_closes.index[0].date()} to {is_closes.index[-1].date()} ({len(is_closes)} days)")
    print(f"  OOS period: {oos_closes.index[0].date()} to {oos_closes.index[-1].date()} ({len(oos_closes)} days)")

    # -------------------------------------------------------------------
    # 1. In-sample parameter scan
    # -------------------------------------------------------------------
    is_df, is_results = run_full_scan(is_closes, is_highs, is_lows, subset="IN-SAMPLE")

    # -------------------------------------------------------------------
    # 2. Out-of-sample on best IS params
    # -------------------------------------------------------------------
    best_is = is_df.loc[is_df["sharpe"].idxmax()]
    best_lb    = int(best_is["lookback"])
    best_rebal = int(best_is["rebal"])
    best_n     = int(best_is["n"])
    best_dir   = str(best_is["direction"])
    dir_short  = "LL" if best_dir == "long_low_ratio" else "LH"
    print(f"\n  Best IS params: L{best_lb}_R{best_rebal}_N{best_n}_{dir_short}")

    oos_res = run_intraday_vol_factor(
        oos_closes, best_lb, best_rebal, best_n,
        direction=best_dir,
        highs=oos_highs, lows=oos_lows,
    )
    print(f"\n  OOS Results (best IS params):")
    print(f"    Sharpe:  {oos_res['sharpe']:.3f}")
    print(f"    Return:  {oos_res['annual_ret']*100:.1f}%")
    print(f"    Max DD:  {oos_res['max_dd']*100:.1f}%")
    print(f"    WR:      {oos_res['win_rate']*100:.1f}%")

    # -------------------------------------------------------------------
    # 3. Walk-forward validation (on full data)
    # -------------------------------------------------------------------
    wf_df = walk_forward(closes, highs, lows)

    # -------------------------------------------------------------------
    # 4. Split-half stability (on IS data)
    # -------------------------------------------------------------------
    sh_corr, sh_h1_mean, sh_h2_mean = split_half_test(
        is_closes, is_highs, is_lows
    )

    # -------------------------------------------------------------------
    # 5. Correlation with H-076 (Price Efficiency)
    # -------------------------------------------------------------------
    corr_076 = correlation_with_h076(
        closes, highs, lows,
        best_lb, best_rebal, best_n, best_dir,
    )

    # -------------------------------------------------------------------
    # 6. Correlation with H-012 (Momentum)
    # -------------------------------------------------------------------
    corr_012 = correlation_with_h012(
        closes, highs, lows,
        best_lb, best_rebal, best_n, best_dir,
    )

    # -------------------------------------------------------------------
    # 7. Fee sensitivity
    # -------------------------------------------------------------------
    fee_res = fee_sensitivity(
        closes, highs, lows,
        best_lb, best_rebal, best_n, best_dir,
    )

    # -------------------------------------------------------------------
    # Verdict
    # -------------------------------------------------------------------
    n_is_positive = (is_df["sharpe"] > 0).sum()
    pct_is_positive = n_is_positive / len(is_df) * 100
    wf_pos = int((wf_df["test_sharpe"] > 0).sum()) if len(wf_df) > 0 else 0
    wf_total = len(wf_df)
    wf_mean_oos = float(wf_df["test_sharpe"].mean()) if len(wf_df) > 0 else 0.0

    reject_reasons = []
    conditional_notes = []

    # Criteria checks
    if pct_is_positive < 80:
        reject_reasons.append(f"IS positive: {pct_is_positive:.1f}% < 80% required")
    if wf_total > 0 and wf_pos < 4:
        reject_reasons.append(f"WF positive: {wf_pos}/{wf_total} < 4/6 required")
    if abs(corr_076) > 0.6:
        reject_reasons.append(f"H-076 corr: {corr_076:.3f} > 0.6 (redundant)")
    if abs(corr_012) > 0.6:
        reject_reasons.append(f"H-012 corr: {corr_012:.3f} > 0.6 (redundant)")

    # Split-half: both > 0 or at least not inverting
    if (sh_h1_mean > 0 and sh_h2_mean < -0.3) or (sh_h1_mean < -0.3 and sh_h2_mean > 0):
        reject_reasons.append(f"Split-half inverting: H1={sh_h1_mean:.3f}, H2={sh_h2_mean:.3f}")
    elif sh_h1_mean < 0 or sh_h2_mean < 0:
        conditional_notes.append(f"Split-half partially negative: H1={sh_h1_mean:.3f}, H2={sh_h2_mean:.3f}")

    if reject_reasons:
        verdict = "REJECTED"
        verdict_reason = "; ".join(reject_reasons)
    elif conditional_notes or wf_mean_oos < 0.3 or oos_res["sharpe"] < 0.3:
        verdict = "CONDITIONAL"
        all_notes = conditional_notes.copy()
        if wf_mean_oos < 0.3:
            all_notes.append(f"WF mean OOS Sharpe weak: {wf_mean_oos:.3f}")
        if oos_res["sharpe"] < 0.3:
            all_notes.append(f"OOS Sharpe weak: {oos_res['sharpe']:.3f}")
        verdict_reason = "; ".join(all_notes) if all_notes else "Passes minimum but not strong"
    else:
        verdict = "CONFIRMED"
        verdict_reason = "All criteria passed"

    print("\n" + "=" * 72)
    print("FINAL VERDICT")
    print("=" * 72)
    print(f"  Total params tested:  {len(is_df)}")
    print(f"  IS positive:          {n_is_positive}/{len(is_df)} ({pct_is_positive:.1f}%) [need >=80%]")
    print(f"  IS best Sharpe:       {best_is['sharpe']:.3f}")
    print(f"  IS best params:       L{best_lb}_R{best_rebal}_N{best_n}_{dir_short}")
    print(f"  IS best annual ret:   {best_is['annual_ret']*100:.1f}%")
    print(f"  IS best max DD:       {best_is['max_dd']*100:.1f}%")
    print(f"  IS best win rate:     {best_is['win_rate']*100:.1f}%")
    print(f"  OOS Sharpe:           {oos_res['sharpe']:.3f}")
    print(f"  OOS annual ret:       {oos_res['annual_ret']*100:.1f}%")
    print(f"  OOS max DD:           {oos_res['max_dd']*100:.1f}%")
    print(f"  WF folds positive:    {wf_pos}/{wf_total} [need >=4/6]")
    if wf_total > 0:
        print(f"  WF mean OOS Sharpe:   {wf_mean_oos:.3f}")
    print(f"  Split-half corr:      {sh_corr:.3f}")
    print(f"  Split-half H1 mean:   {sh_h1_mean:.3f}")
    print(f"  Split-half H2 mean:   {sh_h2_mean:.3f}")
    print(f"  Corr with H-076:      {corr_076:.3f} [need <0.6]")
    print(f"  Corr with H-012:      {corr_012:.3f} [need <0.6]")
    print(f"  Fee sens (5bps):      Sharpe={fee_res['sharpe_5bps']:.3f}")
    print(f"  Fee sens (10bps):     Sharpe={fee_res['sharpe_10bps']:.3f}")
    if reject_reasons:
        print(f"  Reject reasons:       {'; '.join(reject_reasons)}")
    if conditional_notes:
        print(f"  Conditional notes:    {'; '.join(conditional_notes)}")
    print(f"\n  >>> VERDICT: {verdict} <<<")
    print(f"  Reason: {verdict_reason}")
    print("=" * 72)

    # -------------------------------------------------------------------
    # Save results
    # -------------------------------------------------------------------
    output = {
        "hypothesis": "H-129",
        "name": "Intraday Volatility Ratio Factor",
        "factor": "parkinson_vol(rolling_std(ln(H/L))) / cc_vol(rolling_std(ln(C/C_prev)))",
        "direction_tested": "both long_low_ratio and long_high_ratio",
        "best_direction": best_dir,
        "n_assets": len(closes.columns),
        "n_days_total": n_total,
        "is_period": f"{is_closes.index[0].date()} to {is_closes.index[-1].date()}",
        "oos_period": f"{oos_closes.index[0].date()} to {oos_closes.index[-1].date()}",
        "n_params": len(is_df),
        "is_pct_positive_sharpe": round(pct_is_positive, 1),
        "is_mean_sharpe": round(float(is_df["sharpe"].mean()), 3),
        "is_median_sharpe": round(float(is_df["sharpe"].median()), 3),
        "is_best_params": str(best_is["tag"]),
        "is_best_sharpe": float(best_is["sharpe"]),
        "is_best_annual_ret": float(best_is["annual_ret"]),
        "is_best_max_dd": float(best_is["max_dd"]),
        "is_best_win_rate": float(best_is["win_rate"]),
        "oos_sharpe": oos_res["sharpe"],
        "oos_annual_ret": oos_res["annual_ret"],
        "oos_max_dd": oos_res["max_dd"],
        "oos_win_rate": oos_res["win_rate"],
        "wf_folds_positive": wf_pos,
        "wf_folds_total": wf_total,
        "wf_mean_oos_sharpe": round(wf_mean_oos, 3),
        "wf_details": wf_df.to_dict("records") if len(wf_df) > 0 else [],
        "split_half_corr": round(float(sh_corr), 3),
        "split_half_h1_mean": round(sh_h1_mean, 3),
        "split_half_h2_mean": round(sh_h2_mean, 3),
        "corr_h076": round(float(corr_076), 3),
        "corr_h012": round(float(corr_012), 3),
        "fee_sensitivity": fee_res,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "reject_reasons": reject_reasons,
        "all_is_results": is_results,
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")

    # Print summary JSON (without all_is_results)
    summary = {k: v for k, v in output.items() if k != "all_is_results"}
    print("\n" + json.dumps(summary, indent=2))
