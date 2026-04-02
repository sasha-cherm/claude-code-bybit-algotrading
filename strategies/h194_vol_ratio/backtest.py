"""
H-194: Realized Vol Ratio Factor — Cross-Sectional Backtest
Signal: vol_ratio = std(ret[-short:]) / std(ret[-long:])
Long/Short: rank cross-sectionally, long bottom-N (compressed) or top-N, short opposite.
"""

import sys
import warnings
import itertools
import numpy as np
import pandas as pd
from collections import defaultdict

warnings.filterwarnings("ignore")

sys.path.insert(0, "/home/cctrd/cc-bybit-algotrading")
from lib.data_fetch import fetch_and_cache
from strategies.daily_trend_multi_asset.strategy import resample_to_daily

# =============================================================================
# Config
# =============================================================================
ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

SHORT_WINDOWS = [5, 10, 20]
LONG_WINDOWS = [30, 40, 60]
REBAL_FREQS = [3, 5, 7]
N_POSITIONS = [3, 4]
DIRECTIONS = ["low_ratio_long", "high_ratio_long"]

FEE_RATE = 0.001  # 0.1%
SLIPPAGE_BPS = 2  # 2bps
TOTAL_COST = FEE_RATE + SLIPPAGE_BPS / 10_000  # per side

# =============================================================================
# Data Loading
# =============================================================================
print("Loading data...")
daily_closes = {}
daily_returns = {}

for sym in ASSETS:
    try:
        df_1h = fetch_and_cache(sym, "1h", limit_days=730)
        daily = resample_to_daily(df_1h)
        daily_closes[sym] = daily["close"]
        daily_returns[sym] = daily["close"].pct_change()
    except Exception as e:
        print(f"  WARN: Failed to load {sym}: {e}")

# Align all series to common dates
close_df = pd.DataFrame(daily_closes)
ret_df = pd.DataFrame(daily_returns)

# Drop dates where we don't have all assets
close_df = close_df.dropna()
ret_df = ret_df.reindex(close_df.index).dropna()

print(f"Loaded {len(ret_df.columns)} assets, {len(ret_df)} daily bars")
print(f"Date range: {ret_df.index[0].date()} to {ret_df.index[-1].date()}")

# =============================================================================
# Signal Computation
# =============================================================================
def compute_vol_ratio(ret_df, short_w, long_w):
    """Compute vol_ratio = rolling_std(short) / rolling_std(long) for each asset."""
    short_vol = ret_df.rolling(short_w).std()
    long_vol = ret_df.rolling(long_w).std()
    ratio = short_vol / long_vol
    return ratio

def compute_ranks(ratio_df):
    """Rank cross-sectionally (1=lowest ratio, N=highest)."""
    return ratio_df.rank(axis=1, method="average")

# =============================================================================
# Backtest Engine
# =============================================================================
def run_backtest(ret_df, short_w, long_w, rebal_freq, n_pos, direction, start_idx=None, end_idx=None):
    """
    Run cross-sectional long/short backtest.
    Returns daily pnl series.
    """
    if start_idx is not None:
        ret_sub = ret_df.iloc[start_idx:end_idx]
    else:
        ret_sub = ret_df

    n_assets = len(ret_sub.columns)

    # Compute signal on full data up to each point (use ret_df for lookback)
    vol_ratio = compute_vol_ratio(ret_df, short_w, long_w)

    # Restrict to the backtest period
    if start_idx is not None:
        vol_ratio_sub = vol_ratio.iloc[start_idx:end_idx]
    else:
        vol_ratio_sub = vol_ratio

    # Need enough data for the long window
    warmup = long_w + 5

    dates = vol_ratio_sub.index
    daily_pnl = pd.Series(0.0, index=dates)

    positions = pd.Series(0.0, index=ret_sub.columns)  # weight per asset
    prev_positions = positions.copy()
    last_rebal = -rebal_freq  # force rebalance on first valid day

    for i, date in enumerate(dates):
        if i < warmup:
            continue

        # Daily return from positions
        day_ret = ret_sub.iloc[i]
        port_ret = (prev_positions * day_ret).sum()
        daily_pnl.iloc[i] = port_ret

        # Rebalance?
        if i - last_rebal >= rebal_freq:
            ratios = vol_ratio_sub.iloc[i]
            valid = ratios.dropna()
            if len(valid) < 2 * n_pos:
                prev_positions = positions.copy()
                continue

            sorted_assets = valid.sort_values()

            if direction == "low_ratio_long":
                longs = sorted_assets.index[:n_pos]
                shorts = sorted_assets.index[-n_pos:]
            else:  # high_ratio_long
                longs = sorted_assets.index[-n_pos:]
                shorts = sorted_assets.index[:n_pos]

            new_positions = pd.Series(0.0, index=ret_sub.columns)
            weight = 1.0 / n_pos
            for a in longs:
                new_positions[a] = weight
            for a in shorts:
                new_positions[a] = -weight

            # Turnover cost
            turnover = (new_positions - prev_positions).abs().sum()
            cost = turnover * TOTAL_COST
            daily_pnl.iloc[i] -= cost

            prev_positions = new_positions.copy()
            last_rebal = i
        else:
            # Keep same positions
            pass

    return daily_pnl.iloc[warmup:]

def compute_metrics(pnl_series):
    """Compute annualized Sharpe, return, max drawdown."""
    if len(pnl_series) < 30 or pnl_series.std() == 0:
        return {"sharpe": 0, "ann_ret": 0, "max_dd": -1}

    equity = (1 + pnl_series).cumprod()
    ann_ret = (equity.iloc[-1]) ** (365 / len(pnl_series)) - 1
    max_dd = (equity / equity.cummax() - 1).min()
    sharpe = pnl_series.mean() / pnl_series.std() * np.sqrt(365)

    return {"sharpe": sharpe, "ann_ret": ann_ret, "max_dd": max_dd}

# =============================================================================
# Grid Search (In-Sample)
# =============================================================================
print("\n" + "="*70)
print("PHASE 1: In-Sample Grid Search (108 combos)")
print("="*70)

results = []
combos = list(itertools.product(SHORT_WINDOWS, LONG_WINDOWS, REBAL_FREQS, N_POSITIONS, DIRECTIONS))
print(f"Total combos: {len(combos)}")

for idx, (sw, lw, rf, np_, direction) in enumerate(combos):
    if sw >= lw:  # skip invalid combos where short >= long
        continue
    pnl = run_backtest(ret_df, sw, lw, rf, np_, direction)
    m = compute_metrics(pnl)
    results.append({
        "short_w": sw, "long_w": lw, "rebal_freq": rf,
        "n_pos": np_, "direction": direction,
        "sharpe": m["sharpe"], "ann_ret": m["ann_ret"], "max_dd": m["max_dd"],
    })

results_df = pd.DataFrame(results)

# Analyze by direction
for direction in DIRECTIONS:
    subset = results_df[results_df["direction"] == direction]
    n_positive = (subset["sharpe"] > 0).sum()
    n_total = len(subset)
    pct = n_positive / n_total * 100 if n_total > 0 else 0
    mean_sharpe = subset["sharpe"].mean()
    best = subset.loc[subset["sharpe"].idxmax()]
    print(f"\nIS {direction}: {n_positive}/{n_total} positive ({pct:.0f}%), mean Sharpe {mean_sharpe:.3f}")
    print(f"  Best: sw={int(best['short_w'])}, lw={int(best['long_w'])}, rf={int(best['rebal_freq'])}, "
          f"n={int(best['n_pos'])} -> Sharpe {best['sharpe']:.3f} "
          f"(+{best['ann_ret']*100:.1f}% ann, {best['max_dd']*100:.1f}% DD)")

# Pick best direction
dir_stats = {}
for direction in DIRECTIONS:
    subset = results_df[results_df["direction"] == direction]
    n_positive = (subset["sharpe"] > 0).sum()
    n_total = len(subset)
    pct = n_positive / n_total * 100 if n_total > 0 else 0
    mean_sharpe = subset["sharpe"].mean()
    dir_stats[direction] = {"n_pos": n_positive, "n_total": n_total, "pct": pct, "mean_sharpe": mean_sharpe}

best_dir = max(dir_stats, key=lambda d: dir_stats[d]["pct"])
best_dir_stats = dir_stats[best_dir]

# Best overall params
best_dir_results = results_df[results_df["direction"] == best_dir]
best_row = best_dir_results.loc[best_dir_results["sharpe"].idxmax()]

is_pass = best_dir_stats["pct"] >= 80
is_line = (f"IS: {best_dir} {best_dir_stats['n_pos']}/{best_dir_stats['n_total']} positive "
           f"({best_dir_stats['pct']:.0f}%), mean Sharpe {best_dir_stats['mean_sharpe']:.3f}, "
           f"best [sw={int(best_row['short_w'])},lw={int(best_row['long_w'])},"
           f"rf={int(best_row['rebal_freq'])},n={int(best_row['n_pos'])}] "
           f"Sharpe {best_row['sharpe']:.3f} "
           f"(+{best_row['ann_ret']*100:.1f}% ann, {best_row['max_dd']*100:.1f}% DD)")

print(f"\n{'PASS' if is_pass else 'FAIL'}: {is_line}")

# =============================================================================
# Walk-Forward Validation
# =============================================================================
wf_line = "WF: SKIP (IS failed)"
wf_pass = False

if is_pass:
    print("\n" + "="*70)
    print("PHASE 2: Walk-Forward Validation (6 folds)")
    print("="*70)

    n_days = len(ret_df)
    warmup_needed = int(best_row["long_w"]) + 10
    usable = n_days - warmup_needed
    fold_size = usable // 6

    # Each fold: ~half in-sample, ~half out-of-sample
    # Actually: 6 non-overlapping folds, each with IS/OOS split
    # Use expanding window: fold k has IS = all data up to fold k, OOS = fold k

    oos_sharpes = []
    fold_results = []

    for fold in range(6):
        oos_start = warmup_needed + fold * fold_size
        oos_end = warmup_needed + (fold + 1) * fold_size
        if fold == 5:
            oos_end = n_days  # use remaining for last fold

        is_end = oos_start  # IS is everything before OOS

        # Grid search on IS portion
        best_is_sharpe = -999
        best_params = None

        for sw, lw, rf, np_ in itertools.product(SHORT_WINDOWS, LONG_WINDOWS, REBAL_FREQS, N_POSITIONS):
            if sw >= lw:
                continue
            pnl = run_backtest(ret_df, sw, lw, rf, np_, best_dir, start_idx=0, end_idx=is_end)
            m = compute_metrics(pnl)
            if m["sharpe"] > best_is_sharpe:
                best_is_sharpe = m["sharpe"]
                best_params = (sw, lw, rf, np_)

        # Test best params on OOS
        sw, lw, rf, np_ = best_params
        oos_pnl = run_backtest(ret_df, sw, lw, rf, np_, best_dir, start_idx=oos_start, end_idx=oos_end)
        oos_m = compute_metrics(oos_pnl)
        oos_sharpes.append(oos_m["sharpe"])
        fold_results.append(f"{oos_m['sharpe']:.2f}")
        print(f"  Fold {fold+1}: IS params={best_params} IS_Sharpe={best_is_sharpe:.3f} -> OOS_Sharpe={oos_m['sharpe']:.3f}")

    n_positive_oos = sum(1 for s in oos_sharpes if s > 0)
    mean_oos = np.mean(oos_sharpes)
    wf_pass = n_positive_oos >= 4
    wf_line = f"WF: {n_positive_oos}/6 positive, mean OOS {mean_oos:.3f} (folds: {', '.join(fold_results)})"
    print(f"\n{'PASS' if wf_pass else 'FAIL'}: {wf_line}")

# =============================================================================
# Split-Half Stability
# =============================================================================
sh_line = "Split-half: SKIP"
sh_pass = False

if wf_pass:
    print("\n" + "="*70)
    print("PHASE 3: Split-Half Stability")
    print("="*70)

    mid = len(ret_df) // 2
    sw, lw, rf, np_ = int(best_row["short_w"]), int(best_row["long_w"]), int(best_row["rebal_freq"]), int(best_row["n_pos"])

    pnl_h1 = run_backtest(ret_df, sw, lw, rf, np_, best_dir, start_idx=0, end_idx=mid)
    pnl_h2 = run_backtest(ret_df, sw, lw, rf, np_, best_dir, start_idx=mid, end_idx=len(ret_df))

    m_h1 = compute_metrics(pnl_h1)
    m_h2 = compute_metrics(pnl_h2)

    sh_pass = m_h1["sharpe"] > 0 and m_h2["sharpe"] > 0
    sh_line = f"Split-half: H1={m_h1['sharpe']:.3f}, H2={m_h2['sharpe']:.3f}"
    print(f"{'PASS' if sh_pass else 'FAIL'}: {sh_line}")

# =============================================================================
# Correlation Check
# =============================================================================
print("\n" + "="*70)
print("PHASE 4: Correlation Check")
print("="*70)

# Compute our signal (vol_ratio ranks) using best params
sw, lw = int(best_row["short_w"]), int(best_row["long_w"])
vol_ratio = compute_vol_ratio(ret_df, sw, lw)
vol_ranks = vol_ratio.rank(axis=1, method="average")

# Momentum signal: 60d return rank
mom_60d = ret_df.rolling(60).sum()  # cumulative return proxy
mom_ranks = mom_60d.rank(axis=1, method="average")

# Compute daily cross-sectional rank correlation (Spearman)
# For each day, correlate vol_ratio rank with momentum rank
rank_corrs = []
for i in range(60, len(vol_ranks)):
    v = vol_ranks.iloc[i].dropna()
    m = mom_ranks.iloc[i].dropna()
    common = v.index.intersection(m.index)
    if len(common) >= 5:
        corr = v[common].corr(m[common])
        rank_corrs.append(corr)

mean_corr_mom = np.nanmean(rank_corrs)
# Use absolute value for "max correlation"
abs_mean_corr = abs(mean_corr_mom)

# For H-076 (efficiency) and H-160 (trend quality), compute proxy correlations
# Efficiency ~ close-to-close net move / sum of absolute moves (proxy: abs(sum(ret)) / sum(abs(ret)))
eff_60d = ret_df.rolling(60).apply(lambda x: abs(x.sum()) / np.abs(x).sum() if np.abs(x).sum() > 0 else 0, raw=True)
eff_ranks = eff_60d.rank(axis=1, method="average")

eff_corrs = []
for i in range(60, len(vol_ranks)):
    v = vol_ranks.iloc[i].dropna()
    e = eff_ranks.iloc[i].dropna()
    common = v.index.intersection(e.index)
    if len(common) >= 5:
        corr = v[common].corr(e[common])
        eff_corrs.append(corr)

mean_corr_eff = np.nanmean(eff_corrs)

# Trend quality ~ ADX proxy: use directional consistency
# Proxy: fraction of days with same sign as overall trend
tq_60d = ret_df.rolling(60).apply(
    lambda x: np.mean(np.sign(x) == np.sign(np.sum(x))) if len(x) > 0 else 0, raw=True
)
tq_ranks = tq_60d.rank(axis=1, method="average")

tq_corrs = []
for i in range(60, len(vol_ranks)):
    v = vol_ranks.iloc[i].dropna()
    t = tq_ranks.iloc[i].dropna()
    common = v.index.intersection(t.index)
    if len(common) >= 5:
        corr = v[common].corr(t[common])
        tq_corrs.append(corr)

mean_corr_tq = np.nanmean(tq_corrs)

max_corr = max(abs(mean_corr_mom), abs(mean_corr_eff), abs(mean_corr_tq))
corr_pass = max_corr < 0.50

print(f"  vs H-012 (momentum):      {mean_corr_mom:.3f}")
print(f"  vs H-076 (efficiency):     {mean_corr_eff:.3f}")
print(f"  vs H-160 (trend quality):  {mean_corr_tq:.3f}")
print(f"  Max |corr|: {max_corr:.3f} -> {'PASS' if corr_pass else 'FAIL'}")

# =============================================================================
# Final Verdict
# =============================================================================
print("\n" + "="*70)
print("FINAL RESULTS")
print("="*70)

print(f"\nH-194: Realized Vol Ratio Factor")
print(f"IS: {is_line}")
print(f"WF: {wf_line}")
print(f"Split-half: {sh_line}")
print(f"Correlations: H-012 {mean_corr_mom:.3f}, H-076 {mean_corr_eff:.3f}, H-160 {mean_corr_tq:.3f}. Max corr: {max_corr:.3f}")

if is_pass and wf_pass and sh_pass and corr_pass:
    verdict = "CONFIRMED (all tests passed)"
elif not is_pass:
    verdict = f"REJECTED (IS {best_dir_stats['pct']:.0f}% < 80% threshold)"
elif not wf_pass:
    n_pos_oos = sum(1 for s in oos_sharpes if s > 0) if 'oos_sharpes' in dir() else 0
    verdict = f"REJECTED (WF {n_pos_oos}/6 positive < 4/6 threshold)"
elif not sh_pass:
    verdict = "REJECTED (split-half instability)"
else:
    verdict = f"REJECTED (max correlation {max_corr:.3f} >= 0.50)"

print(f"VERDICT: {verdict}")
