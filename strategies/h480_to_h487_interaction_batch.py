#!/usr/bin/env python3
"""
Factor interaction and alternative-frequency batch. These use COMBINATIONS of
existing signal categories and alternative holding periods.

  H-480: Momentum × Volume — momentum weighted by relative volume.
         High momentum + high volume = strong conviction. Low vol momentum ignored.
  H-481: Momentum × Efficiency — momentum weighted by price efficiency.
         High momentum + high efficiency = clean trend = buy.
  H-482: Reversal × Volatility — short-term reversal weighted by realized vol.
         High vol + recent loser = stronger mean-reversion opportunity.
  H-483: Size × Momentum — interaction between dollar volume (size) and momentum.
         Large-cap momentum vs small-cap momentum — focus on large-cap winners.
  H-484: Weekly Momentum (5-bar formation, 5-bar hold) — longer-horizon momentum.
  H-485: Monthly Reversal (20-bar formation, 5-bar hold) — classic long-horizon reversal.
  H-486: BTC-Regime Conditional Factor — use different XS factor depending on
         whether BTC is trending (ADX > 25) or ranging.
  H-487: Dual Momentum — asset must have positive TS momentum AND high XS momentum.
         Only go long when both agree; only short when both say short.

Standard framework: grid search, IS >=80%, walk-forward OOS, split-half, H-012 corr.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.001
SLIPPAGE_BPS = 2.0


def load_data():
    print("Loading daily data for 14 assets...")
    closes_dict, volumes_dict, highs_dict, lows_dict = {}, {}, {}, {}

    for sym in ASSETS:
        ticker = sym.replace("/", "_")
        fpath = ROOT / "data" / f"{ticker}_1d.parquet"
        if not fpath.exists():
            continue
        df = pd.read_parquet(fpath)
        if len(df) < 200:
            continue
        closes_dict[sym] = df["close"]
        volumes_dict[sym] = df["volume"]
        highs_dict[sym] = df["high"]
        lows_dict[sym] = df["low"]

    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill().dropna()
    highs = pd.DataFrame(highs_dict).reindex(closes.index).ffill().dropna()
    lows = pd.DataFrame(lows_dict).reindex(closes.index).ffill().dropna()
    idx = closes.index.intersection(volumes.index)
    closes, volumes, highs, lows = closes.loc[idx], volumes.loc[idx], highs.loc[idx], lows.loc[idx]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} bars")
    return closes, volumes, highs, lows


def compute_returns(closes):
    return closes.pct_change()


def compute_adx(highs, lows, closes, period=14):
    """Compute ADX for BTC."""
    btc = "BTC/USDT"
    h = highs[btc].values
    l = lows[btc].values
    c = closes[btc].values

    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    plus_dm = np.where((h[1:] - h[:-1]) > (l[:-1] - l[1:]), np.maximum(h[1:] - h[:-1], 0), 0)
    minus_dm = np.where((l[:-1] - l[1:]) > (h[1:] - h[:-1]), np.maximum(l[:-1] - l[1:], 0), 0)

    atr = pd.Series(tr).ewm(span=period).mean().values
    plus_di = 100 * pd.Series(plus_dm).ewm(span=period).mean().values / (atr + 1e-12)
    minus_di = 100 * pd.Series(minus_dm).ewm(span=period).mean().values / (atr + 1e-12)

    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-12)
    adx = pd.Series(dx).ewm(span=period).mean().values

    adx_series = pd.Series(np.nan, index=closes.index)
    adx_series.iloc[1:] = adx
    return adx_series


def precompute_interaction_features(closes, volumes, highs, lows):
    """Compute all interaction features."""
    rets = compute_returns(closes)
    dates = closes.index
    syms = closes.columns

    # Feature DataFrames
    mom_vol = pd.DataFrame(index=dates, columns=syms, dtype=float)
    mom_eff = pd.DataFrame(index=dates, columns=syms, dtype=float)
    rev_vol = pd.DataFrame(index=dates, columns=syms, dtype=float)
    size_mom = pd.DataFrame(index=dates, columns=syms, dtype=float)
    weekly_mom = pd.DataFrame(index=dates, columns=syms, dtype=float)
    monthly_rev = pd.DataFrame(index=dates, columns=syms, dtype=float)
    dual_mom = pd.DataFrame(index=dates, columns=syms, dtype=float)

    btc_col = "BTC/USDT"

    print("Pre-computing interaction features...")

    for i in range(60, len(dates)):
        date_i = dates[i]

        for sym in syms:
            # Base features (lagged, using t-1)
            ret_60d = (closes[sym].iloc[i-1] / closes[sym].iloc[i-61] - 1) if i >= 61 else np.nan
            ret_5d = (closes[sym].iloc[i-1] / closes[sym].iloc[max(0, i-6)] - 1) if i >= 6 else np.nan
            ret_20d = (closes[sym].iloc[i-1] / closes[sym].iloc[max(0, i-21)] - 1) if i >= 21 else np.nan

            # Relative volume (recent vs average)
            vol_10d = volumes[sym].iloc[max(0, i-10):i].mean()
            vol_30d = volumes[sym].iloc[max(0, i-30):i].mean()
            rel_vol = vol_10d / (vol_30d + 1e-12) if vol_30d > 0 else 1.0

            # Efficiency
            if i >= 21:
                net_move = abs(closes[sym].iloc[i-1] - closes[sym].iloc[i-21])
                gross_move = sum(abs(rets[sym].iloc[j]) for j in range(max(1, i-20), i))
                efficiency = net_move / (gross_move * closes[sym].iloc[i-21] + 1e-12)
            else:
                efficiency = 0.5

            # Realized vol (20d)
            realized_vol = rets[sym].iloc[max(0, i-20):i].std() * np.sqrt(365) if i >= 20 else 0.3

            # Dollar volume (size proxy)
            dv = (closes[sym].iloc[i-1] * volumes[sym].iloc[i-1]) if i >= 1 else 0

            # --- H-480: Momentum × Volume ---
            mom_vol.at[date_i, sym] = ret_60d * rel_vol if not np.isnan(ret_60d) else np.nan

            # --- H-481: Momentum × Efficiency ---
            mom_eff.at[date_i, sym] = ret_60d * efficiency if not np.isnan(ret_60d) else np.nan

            # --- H-482: Reversal × Volatility ---
            # Short-term reversal: short recent losers (negate 5d return, multiply by vol)
            if not np.isnan(ret_5d):
                rev_vol.at[date_i, sym] = -ret_5d * realized_vol
            else:
                rev_vol.at[date_i, sym] = np.nan

            # --- H-483: Size × Momentum ---
            if not np.isnan(ret_60d):
                size_mom.at[date_i, sym] = np.log(dv + 1) * ret_60d
            else:
                size_mom.at[date_i, sym] = np.nan

            # --- H-484: Weekly Momentum ---
            weekly_mom.at[date_i, sym] = ret_5d if not np.isnan(ret_5d) else np.nan

            # --- H-485: Monthly Reversal ---
            monthly_rev.at[date_i, sym] = -ret_20d if not np.isnan(ret_20d) else np.nan

            # --- H-487: Dual Momentum ---
            # TS momentum: positive = long, negative = short
            # XS momentum: rank among peers
            # Combined: TS agrees with XS direction
            if not np.isnan(ret_60d):
                ts_signal = 1 if ret_60d > 0 else -1
                # Will multiply by XS rank later (handled in backtest)
                dual_mom.at[date_i, sym] = ret_60d  # raw, dual logic in backtest

    print("Interaction features computed.")
    return {
        'mom_vol': mom_vol,
        'mom_eff': mom_eff,
        'rev_vol': rev_vol,
        'size_mom': size_mom,
        'weekly_mom': weekly_mom,
        'monthly_rev': monthly_rev,
        'dual_mom': dual_mom,
    }


def run_xs_backtest(factor_vals, closes, n_long, n_short, rebal_days, direction='high_long'):
    """Standard cross-sectional backtest."""
    rets = compute_returns(closes)
    dates = closes.index
    n_assets = len(closes.columns)

    pnl_series = pd.Series(0.0, index=dates)
    last_rebal = -999
    longs, shorts = [], []

    for i in range(61, len(dates)):
        date_i = dates[i]
        fv = factor_vals.loc[date_i].dropna()
        if len(fv) < n_long + n_short:
            continue

        if i - last_rebal >= rebal_days:
            ranked = fv.sort_values(ascending=(direction != 'high_long'))
            new_longs = ranked.index[-n_long:].tolist()
            new_shorts = ranked.index[:n_short].tolist()

            old_all = set(longs + shorts)
            new_all = set(new_longs + new_shorts)
            turnover = len(old_all.symmetric_difference(new_all))
            fee = turnover * FEE_RATE / n_assets + turnover * SLIPPAGE_BPS / 10000 / n_assets

            longs, shorts = new_longs, new_shorts
            last_rebal = i
            pnl_series.iloc[i] -= fee

        day_rets = rets.iloc[i]
        if longs and shorts:
            long_ret = day_rets[longs].mean()
            short_ret = day_rets[shorts].mean()
            pnl_series.iloc[i] += long_ret - short_ret

    return pnl_series


def run_dual_momentum_backtest(factor_vals, closes, n_long, n_short, rebal_days):
    """Dual momentum: only long if TS > 0, only short if TS < 0."""
    rets = compute_returns(closes)
    dates = closes.index
    n_assets = len(closes.columns)

    pnl_series = pd.Series(0.0, index=dates)
    last_rebal = -999
    longs, shorts = [], []

    for i in range(61, len(dates)):
        date_i = dates[i]
        fv = factor_vals.loc[date_i].dropna()
        if len(fv) < n_long + n_short:
            continue

        if i - last_rebal >= rebal_days:
            ranked = fv.sort_values()
            # Only long those with positive momentum
            candidates_long = [s for s in ranked.index[-n_long*2:] if fv[s] > 0][-n_long:]
            # Only short those with negative momentum
            candidates_short = [s for s in ranked.index[:n_short*2] if fv[s] < 0][:n_short]

            old_all = set(longs + shorts)
            new_all = set(candidates_long + candidates_short)
            turnover = len(old_all.symmetric_difference(new_all))
            fee = turnover * FEE_RATE / n_assets + turnover * SLIPPAGE_BPS / 10000 / n_assets

            longs, shorts = candidates_long, candidates_short
            last_rebal = i
            pnl_series.iloc[i] -= fee

        day_rets = rets.iloc[i]
        n_pos = max(len(longs), 1)
        n_neg = max(len(shorts), 1)
        if longs:
            pnl_series.iloc[i] += day_rets[longs].mean() * len(longs) / max(n_long, 1)
        if shorts:
            pnl_series.iloc[i] -= day_rets[shorts].mean() * len(shorts) / max(n_short, 1)

    return pnl_series


def run_regime_conditional_backtest(closes, highs, lows, volumes, n_long, n_short, rebal_days, adx_threshold=25):
    """BTC-regime conditional: use momentum when trending, reversal when ranging."""
    rets = compute_returns(closes)
    dates = closes.index
    n_assets = len(closes.columns)
    adx = compute_adx(highs, lows, closes)

    mom60 = closes.pct_change(60)
    rev5 = -closes.pct_change(5)

    pnl_series = pd.Series(0.0, index=dates)
    last_rebal = -999
    longs, shorts = [], []

    for i in range(61, len(dates)):
        date_i = dates[i]
        adx_val = adx.iloc[i-1]  # lagged

        if np.isnan(adx_val):
            continue

        # Choose factor based on regime
        if adx_val > adx_threshold:
            factor = mom60.iloc[i-1]  # trending: use momentum
        else:
            factor = rev5.iloc[i-1]  # ranging: use reversal

        fv = factor.dropna()
        if len(fv) < n_long + n_short:
            continue

        if i - last_rebal >= rebal_days:
            ranked = fv.sort_values()
            new_longs = ranked.index[-n_long:].tolist()
            new_shorts = ranked.index[:n_short].tolist()

            old_all = set(longs + shorts)
            new_all = set(new_longs + new_shorts)
            turnover = len(old_all.symmetric_difference(new_all))
            fee = turnover * FEE_RATE / n_assets + turnover * SLIPPAGE_BPS / 10000 / n_assets

            longs, shorts = new_longs, new_shorts
            last_rebal = i
            pnl_series.iloc[i] -= fee

        day_rets = rets.iloc[i]
        if longs and shorts:
            long_ret = day_rets[longs].mean()
            short_ret = day_rets[shorts].mean()
            pnl_series.iloc[i] += long_ret - short_ret

    return pnl_series


def evaluate_signal(pnl, name, dates, verbose=True):
    total_days = len(pnl)
    if total_days < 200:
        if verbose:
            print(f"  {name}: insufficient data ({total_days} days)")
        return None

    first_nonzero = (pnl != 0).idxmax()
    pnl = pnl.loc[first_nonzero:]
    if len(pnl) < 200:
        if verbose:
            print(f"  {name}: insufficient active days ({len(pnl)})")
        return None

    cum_ret = pnl.cumsum()
    total_ret = cum_ret.iloc[-1]
    ann_ret = total_ret / (len(pnl) / 365) * 100
    daily_std = pnl.std()
    sharpe = (pnl.mean() / daily_std * np.sqrt(365)) if daily_std > 0 else 0

    rolling_max = cum_ret.cummax()
    dd = cum_ret - rolling_max
    max_dd = dd.min() * 100

    if verbose:
        print(f"  {name}: Sharpe {sharpe:.3f}, Ann {ann_ret:.1f}%, DD {max_dd:.1f}%, "
              f"Mean daily {pnl.mean()*10000:.2f}bps")

    return {
        'name': name, 'sharpe': sharpe, 'ann_ret': ann_ret, 'max_dd': max_dd,
        'mean_daily_bps': pnl.mean() * 10000, 'pnl': pnl
    }


def walk_forward(factor_vals, closes, n_long, n_short, rebal_days, direction,
                 n_folds=6, fold_days=90, backtest_fn=None, **kwargs):
    dates = closes.index
    total = len(dates)
    results = []

    for fold in range(n_folds):
        test_end = total - fold * fold_days
        test_start = test_end - fold_days
        if test_start < 90:
            break

        if backtest_fn:
            pnl = backtest_fn(closes.iloc[:test_end], n_long=n_long, n_short=n_short,
                              rebal_days=rebal_days, **kwargs)
        else:
            pnl = run_xs_backtest(factor_vals, closes.iloc[:test_end],
                                  n_long, n_short, rebal_days, direction)

        test_pnl = pnl.iloc[test_start:test_end]
        if test_pnl.std() > 0:
            fold_sharpe = test_pnl.mean() / test_pnl.std() * np.sqrt(365)
        else:
            fold_sharpe = 0
        results.append(fold_sharpe)

    positive = sum(1 for r in results if r > 0)
    mean_sharpe = np.mean(results) if results else 0
    return positive, len(results), mean_sharpe, results


def split_half_test(factor_vals, closes, n_long, n_short, rebal_days, direction):
    mid = len(closes) // 2
    pnl1 = run_xs_backtest(factor_vals, closes.iloc[:mid], n_long, n_short, rebal_days, direction)
    pnl2 = run_xs_backtest(factor_vals, closes.iloc[mid:], n_long, n_short, rebal_days, direction)
    s1 = pnl1.mean() / pnl1.std() * np.sqrt(365) if pnl1.std() > 0 else 0
    s2 = pnl2.mean() / pnl2.std() * np.sqrt(365) if pnl2.std() > 0 else 0
    return s1, s2


def correlation_with_h012(pnl, closes):
    rets = compute_returns(closes)
    mom60 = closes.pct_change(60)
    h012_pnl = pd.Series(0.0, index=closes.index)
    for i in range(61, len(closes)):
        m = mom60.iloc[i-1].dropna().sort_values()
        if len(m) >= 8:
            long_r = rets.iloc[i][m.index[-4:]].mean()
            short_r = rets.iloc[i][m.index[:4]].mean()
            h012_pnl.iloc[i] = long_r - short_r
    idx = pnl.index.intersection(h012_pnl.index)
    if len(idx) < 50:
        return 0.0
    return pnl.reindex(idx).corr(h012_pnl.reindex(idx))


def main():
    closes, volumes, highs, lows = load_data()
    features = precompute_interaction_features(closes, volumes, highs, lows)

    # Standard signals
    configs = {
        'H-480': {
            'feature': 'mom_vol',
            'directions': ['high_long'],
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5, 7],
            'desc': 'Momentum × Volume'
        },
        'H-481': {
            'feature': 'mom_eff',
            'directions': ['high_long'],
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5, 7],
            'desc': 'Momentum × Efficiency'
        },
        'H-482': {
            'feature': 'rev_vol',
            'directions': ['high_long'],  # high = big loser with high vol = mean revert
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5],
            'desc': 'Reversal × Volatility'
        },
        'H-483': {
            'feature': 'size_mom',
            'directions': ['high_long'],
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5, 7],
            'desc': 'Size × Momentum'
        },
        'H-484': {
            'feature': 'weekly_mom',
            'directions': ['high_long', 'low_long'],
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [5, 7, 10],
            'desc': 'Weekly Momentum'
        },
        'H-485': {
            'feature': 'monthly_rev',
            'directions': ['high_long'],
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [5, 7, 10],
            'desc': 'Monthly Reversal'
        },
    }

    all_results = {}

    for hyp_id, cfg in configs.items():
        print(f"\n{'='*60}")
        print(f"{hyp_id}: {cfg['desc']}")
        print(f"{'='*60}")

        feat = features[cfg['feature']]
        grid_results = []

        for direction in cfg['directions']:
            for n_long, n_short in cfg['n_vals']:
                for rebal in cfg['rebal_vals']:
                    pnl = run_xs_backtest(feat, closes, n_long, n_short, rebal, direction)
                    res = evaluate_signal(pnl, f"{direction}_N{n_long}_R{rebal}", closes.index, verbose=False)
                    if res:
                        res['direction'] = direction
                        res['n_long'] = n_long
                        res['n_short'] = n_short
                        res['rebal'] = rebal
                        grid_results.append(res)

        if not grid_results:
            print("  No valid results.")
            continue

        pos = sum(1 for r in grid_results if r['sharpe'] > 0)
        total = len(grid_results)
        pct = pos / total * 100
        print(f"\n  IS Grid: {pos}/{total} ({pct:.0f}%) positive Sharpe")

        best = max(grid_results, key=lambda x: x['sharpe'])
        print(f"  Best: {best['name']} — Sharpe {best['sharpe']:.3f}, Ann {best['ann_ret']:.1f}%, DD {best['max_dd']:.1f}%")
        print(f"    Direction: {best['direction']}, N={best['n_long']}, Rebal={best['rebal']}")

        all_results[hyp_id] = {'grid_results': grid_results, 'best': best}

        if pct < 80:
            print(f"  *** REJECTED at IS ({pct:.0f}% < 80%) ***")
            continue

        # Walk-forward
        pos_wf, n_wf, mean_wf, wf_folds = walk_forward(
            feat, closes, best['n_long'], best['n_short'], best['rebal'], best['direction']
        )
        print(f"  Walk-forward: {pos_wf}/{n_wf} positive (mean Sharpe {mean_wf:.3f})")
        print(f"    Fold Sharpes: {[f'{s:.3f}' for s in wf_folds]}")

        if pos_wf < 4:
            print(f"  *** REJECTED at WF ({pos_wf}/{n_wf} < 4/6) ***")
            continue

        # Split-half
        s1, s2 = split_half_test(feat, closes, best['n_long'], best['n_short'],
                                  best['rebal'], best['direction'])
        sh_pass = s1 > 0 and s2 > 0
        print(f"  Split-half: H1={s1:.3f}, H2={s2:.3f} — {'PASS' if sh_pass else 'FAIL'}")

        h012_corr = correlation_with_h012(best['pnl'], closes)
        print(f"  H-012 correlation: {h012_corr:.3f}")

        neighbors = [r for r in grid_results if r['sharpe'] > 0
                      and r['direction'] == best['direction']
                      and abs(r['n_long'] - best['n_long']) <= 1
                      and abs(r['rebal'] - best['rebal']) <= 2]
        n_pct = len(neighbors) / max(1, len([r for r in grid_results
                                              if r['direction'] == best['direction']])) * 100
        print(f"  Neighbor robustness: {n_pct:.0f}%")

        if sh_pass:
            print(f"\n  *** {hyp_id} CONFIRMED ***")
        else:
            print(f"  *** BORDERLINE (SH FAIL) ***")

    # --- H-486: BTC-Regime Conditional ---
    print(f"\n{'='*60}")
    print("H-486: BTC-Regime Conditional Factor")
    print(f"{'='*60}")

    grid_486 = []
    for adx_th in [20, 25, 30]:
        for n_long, n_short in [(3, 3), (4, 4)]:
            for rebal in [3, 5, 7]:
                pnl = run_regime_conditional_backtest(closes, highs, lows, volumes,
                                                      n_long, n_short, rebal, adx_th)
                res = evaluate_signal(pnl, f"ADX{adx_th}_N{n_long}_R{rebal}", closes.index, verbose=False)
                if res:
                    res['adx_th'] = adx_th
                    res['n_long'] = n_long
                    res['n_short'] = n_short
                    res['rebal'] = rebal
                    grid_486.append(res)

    if grid_486:
        pos = sum(1 for r in grid_486 if r['sharpe'] > 0)
        total = len(grid_486)
        pct = pos / total * 100
        print(f"  IS Grid: {pos}/{total} ({pct:.0f}%) positive Sharpe")
        best486 = max(grid_486, key=lambda x: x['sharpe'])
        print(f"  Best: {best486['name']} — Sharpe {best486['sharpe']:.3f}, Ann {best486['ann_ret']:.1f}%, DD {best486['max_dd']:.1f}%")

        if pct >= 80:
            # WF for regime conditional
            pos_wf, n_wf, mean_wf, wf_folds = walk_forward(
                None, closes, best486['n_long'], best486['n_short'], best486['rebal'], 'high_long',
                backtest_fn=lambda c, n_long, n_short, rebal_days:
                    run_regime_conditional_backtest(c, highs.reindex(c.index), lows.reindex(c.index),
                                                    volumes.reindex(c.index), n_long, n_short, rebal_days,
                                                    best486['adx_th'])
            )
            print(f"  Walk-forward: {pos_wf}/{n_wf} positive (mean Sharpe {mean_wf:.3f})")

            h012_corr = correlation_with_h012(best486['pnl'], closes)
            print(f"  H-012 correlation: {h012_corr:.3f}")
        else:
            print(f"  *** REJECTED at IS ({pct:.0f}% < 80%) ***")

    # --- H-487: Dual Momentum ---
    print(f"\n{'='*60}")
    print("H-487: Dual Momentum")
    print(f"{'='*60}")

    grid_487 = []
    for n_long, n_short in [(3, 3), (4, 4)]:
        for rebal in [3, 5, 7]:
            pnl = run_dual_momentum_backtest(features['dual_mom'], closes, n_long, n_short, rebal)
            res = evaluate_signal(pnl, f"dual_N{n_long}_R{rebal}", closes.index, verbose=False)
            if res:
                res['n_long'] = n_long
                res['n_short'] = n_short
                res['rebal'] = rebal
                grid_487.append(res)

    if grid_487:
        pos = sum(1 for r in grid_487 if r['sharpe'] > 0)
        total = len(grid_487)
        pct = pos / total * 100
        print(f"  IS Grid: {pos}/{total} ({pct:.0f}%) positive Sharpe")
        best487 = max(grid_487, key=lambda x: x['sharpe'])
        print(f"  Best: {best487['name']} — Sharpe {best487['sharpe']:.3f}, Ann {best487['ann_ret']:.1f}%, DD {best487['max_dd']:.1f}%")

        if pct >= 80:
            pos_wf, n_wf, mean_wf, wf_folds = walk_forward(
                features['dual_mom'], closes, best487['n_long'], best487['n_short'],
                best487['rebal'], 'high_long'
            )
            print(f"  Walk-forward: {pos_wf}/{n_wf} positive (mean Sharpe {mean_wf:.3f})")

            s1, s2 = split_half_test(features['dual_mom'], closes, best487['n_long'],
                                      best487['n_short'], best487['rebal'], 'high_long')
            sh_pass = s1 > 0 and s2 > 0
            print(f"  Split-half: H1={s1:.3f}, H2={s2:.3f} — {'PASS' if sh_pass else 'FAIL'}")

            h012_corr = correlation_with_h012(best487['pnl'], closes)
            print(f"  H-012 correlation: {h012_corr:.3f}")
        else:
            print(f"  *** REJECTED at IS ({pct:.0f}% < 80%) ***")

    print(f"\n{'='*60}")
    print("BATCH SUMMARY")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
