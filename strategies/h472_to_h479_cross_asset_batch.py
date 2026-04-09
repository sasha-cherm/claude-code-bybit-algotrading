#!/usr/bin/env python3
"""
Cross-asset dynamics batch — signals based on RELATIONSHIPS between assets,
not just individual asset characteristics. This is a genuinely new signal
category not yet explored (daily XS, 4h microstructure, hourly-derived all
used per-asset features).

  H-472: BTC Lead-Lag — rolling correlation of BTC return(t-1) with asset return(t).
         High corr = asset follows BTC with lag = predictable.
         Long high-lag assets when BTC was up yesterday.
  H-473: Correlation Clustering — each asset's average pairwise correlation
         with all others. High = moves with the pack. Low = independent.
         Low-correlation assets may offer diversification premium.
  H-474: Beta Change — rolling change in BTC beta (beta_10d - beta_30d).
         Rising beta = increasing systematic risk = sell. Falling = buy.
  H-475: Relative Funding Spread — asset funding rate minus cross-sectional
         median. Extreme high = overleveraged longs = short contrarian.
  H-476: Cross-Asset Momentum Spillover — weighted sum of returns from
         correlated assets (lagged). If peers did well, follow.
  H-477: Idiosyncratic Momentum — residual return after removing BTC component.
         Pure alpha signal after market factor removed.
  H-478: Dispersion-Conditional Momentum — standard XS momentum but only
         active when cross-sectional return dispersion is high (divergent market).
  H-479: Correlation Regime Switch — asset performance conditional on whether
         overall crypto correlation is rising or falling.

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
    idx = closes.index.intersection(volumes.index)
    closes, volumes = closes.loc[idx], volumes.loc[idx]

    # Load funding data if available
    funding_dict = {}
    for sym in ASSETS:
        ticker = sym.replace("/", "_")
        fpath = ROOT / "data" / f"{ticker}_funding.parquet"
        if fpath.exists():
            fdf = pd.read_parquet(fpath)
            if 'fundingRate' in fdf.columns:
                daily_funding = fdf['fundingRate'].resample('1D').sum()
                funding_dict[sym] = daily_funding

    funding = pd.DataFrame(funding_dict)
    if not funding.empty:
        funding = funding.reindex(closes.index).ffill()

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} bars")
    return closes, volumes, funding


def compute_returns(closes):
    return closes.pct_change()


def precompute_cross_asset_features(closes, volumes, funding):
    """Compute all 8 cross-asset features."""
    rets = compute_returns(closes)
    dates = closes.index
    syms = closes.columns

    btc_col = "BTC/USDT"
    btc_ret = rets[btc_col] if btc_col in rets.columns else None

    # Feature DataFrames
    btc_leadlag = pd.DataFrame(index=dates, columns=syms, dtype=float)
    corr_cluster = pd.DataFrame(index=dates, columns=syms, dtype=float)
    beta_change = pd.DataFrame(index=dates, columns=syms, dtype=float)
    fund_spread = pd.DataFrame(index=dates, columns=syms, dtype=float)
    spillover = pd.DataFrame(index=dates, columns=syms, dtype=float)
    idio_mom = pd.DataFrame(index=dates, columns=syms, dtype=float)
    dispersion = pd.Series(index=dates, dtype=float)
    corr_regime = pd.Series(index=dates, dtype=float)

    print("Pre-computing cross-asset features...")

    for i in range(60, len(dates)):
        date_i = dates[i]
        # Use lagged window (up to yesterday)
        window_start = max(0, i - 30)
        w_rets = rets.iloc[window_start:i]

        if len(w_rets) < 10:
            continue

        # --- H-472: BTC Lead-Lag ---
        if btc_ret is not None:
            btc_lag1 = btc_ret.iloc[window_start:i-1].values
            for sym in syms:
                if sym == btc_col:
                    btc_leadlag.at[date_i, sym] = 0.0
                    continue
                asset_ret = rets[sym].iloc[window_start+1:i].values
                if len(btc_lag1) == len(asset_ret) and len(btc_lag1) >= 10:
                    c, _ = stats.pearsonr(btc_lag1, asset_ret)
                    btc_leadlag.at[date_i, sym] = c

        # --- H-473: Correlation Clustering ---
        corr_mat = w_rets.corr()
        for sym in syms:
            if sym in corr_mat.columns:
                avg_corr = corr_mat[sym].drop(sym, errors='ignore').mean()
                corr_cluster.at[date_i, sym] = avg_corr

        # --- H-474: Beta Change ---
        if btc_ret is not None:
            btc_short = btc_ret.iloc[max(0, i-10):i].values
            btc_long = btc_ret.iloc[max(0, i-30):i].values
            for sym in syms:
                if sym == btc_col:
                    beta_change.at[date_i, sym] = 0.0
                    continue
                ret_short = rets[sym].iloc[max(0, i-10):i].values
                ret_long = rets[sym].iloc[max(0, i-30):i].values
                if len(btc_short) >= 5 and len(btc_long) >= 10:
                    try:
                        beta_s = np.cov(ret_short, btc_short)[0, 1] / (np.var(btc_short) + 1e-12)
                        beta_l = np.cov(ret_long, btc_long)[0, 1] / (np.var(btc_long) + 1e-12)
                        beta_change.at[date_i, sym] = beta_s - beta_l
                    except:
                        pass

        # --- H-475: Relative Funding Spread ---
        if not funding.empty:
            for sym in syms:
                if sym in funding.columns:
                    fund_5d = funding[sym].iloc[max(0, i-5):i].mean()
                    median_fund = funding.iloc[max(0, i-5):i].mean().median()
                    fund_spread.at[date_i, sym] = fund_5d - median_fund

        # --- H-476: Cross-Asset Momentum Spillover ---
        for sym in syms:
            peer_signal = 0.0
            for other in syms:
                if other == sym:
                    continue
                c = corr_mat.at[sym, other] if sym in corr_mat.index and other in corr_mat.columns else 0
                if abs(c) > 0.3:  # only correlated peers
                    # yesterday's return of peer, weighted by correlation
                    if i > 0:
                        peer_ret = rets[other].iloc[i - 1]
                        peer_signal += c * peer_ret
            spillover.at[date_i, sym] = peer_signal

        # --- H-477: Idiosyncratic Momentum ---
        if btc_ret is not None:
            lb = 20
            for sym in syms:
                if sym == btc_col:
                    idio_mom.at[date_i, sym] = 0.0
                    continue
                asset_rets = rets[sym].iloc[max(0, i - lb):i].values
                btc_rets_w = btc_ret.iloc[max(0, i - lb):i].values
                if len(asset_rets) >= 10 and len(btc_rets_w) >= 10:
                    try:
                        beta = np.cov(asset_rets, btc_rets_w)[0, 1] / (np.var(btc_rets_w) + 1e-12)
                        residuals = asset_rets - beta * btc_rets_w
                        idio_mom.at[date_i, sym] = residuals.sum()
                    except:
                        pass

        # --- H-478 & H-479: Cross-sectional dispersion & Correlation regime ---
        xs_rets = rets.iloc[i]
        dispersion.at[date_i] = xs_rets.std()

        # Correlation regime: average pairwise correlation change
        if i >= 60:
            corr_recent = rets.iloc[i-10:i].corr()
            corr_older = rets.iloc[i-30:i-10].corr()
            mask = np.triu(np.ones(corr_recent.shape), k=1).astype(bool)
            corr_regime.at[date_i] = corr_recent.values[mask].mean() - corr_older.values[mask].mean()

    print("Cross-asset features computed.")
    return {
        'btc_leadlag': btc_leadlag,
        'corr_cluster': corr_cluster,
        'beta_change': beta_change,
        'fund_spread': fund_spread,
        'spillover': spillover,
        'idio_mom': idio_mom,
        'dispersion': dispersion,
        'corr_regime': corr_regime,
    }


def run_xs_backtest(factor_vals, closes, n_long, n_short, rebal_days, direction='high_long'):
    """Standard cross-sectional backtest."""
    rets = compute_returns(closes)
    dates = closes.index
    syms = closes.columns
    n_assets = len(syms)

    pnl_series = pd.Series(0.0, index=dates)
    last_rebal = -999
    longs, shorts = [], []

    for i in range(61, len(dates)):
        date_i = dates[i]
        fv = factor_vals.loc[date_i].dropna()
        if len(fv) < n_long + n_short:
            continue

        # Rebalance check
        if i - last_rebal >= rebal_days:
            ranked = fv.sort_values(ascending=(direction != 'high_long'))
            new_longs = ranked.index[-n_long:].tolist()
            new_shorts = ranked.index[:n_short].tolist()

            # Compute turnover fees
            old_all = set(longs + shorts)
            new_all = set(new_longs + new_shorts)
            turnover = len(old_all.symmetric_difference(new_all))
            fee = turnover * FEE_RATE / n_assets + turnover * SLIPPAGE_BPS / 10000 / n_assets

            longs, shorts = new_longs, new_shorts
            last_rebal = i
            pnl_series.iloc[i] -= fee

        # Daily PnL
        day_rets = rets.iloc[i]
        if longs and shorts:
            long_ret = day_rets[longs].mean() if longs else 0
            short_ret = day_rets[shorts].mean() if shorts else 0
            pnl_series.iloc[i] += long_ret - short_ret

    return pnl_series


def run_conditional_xs_backtest(factor_vals, closes, n_long, n_short, rebal_days,
                                 condition_series, condition_threshold, direction='high_long'):
    """XS backtest that only trades when condition is met."""
    rets = compute_returns(closes)
    dates = closes.index

    pnl_series = pd.Series(0.0, index=dates)
    last_rebal = -999
    longs, shorts = [], []
    active = False

    for i in range(61, len(dates)):
        date_i = dates[i]
        fv = factor_vals.loc[date_i].dropna()
        if len(fv) < n_long + n_short:
            continue

        cond_val = condition_series.get(date_i, np.nan)
        should_be_active = not np.isnan(cond_val) and cond_val > condition_threshold

        if should_be_active:
            if i - last_rebal >= rebal_days or not active:
                ranked = fv.sort_values(ascending=(direction != 'high_long'))
                longs = ranked.index[-n_long:].tolist()
                shorts = ranked.index[:n_short].tolist()
                fee = (n_long + n_short) * 2 * FEE_RATE / len(fv)
                pnl_series.iloc[i] -= fee
                last_rebal = i
            active = True
        else:
            if active and (longs or shorts):
                fee = (len(longs) + len(shorts)) * FEE_RATE / len(fv)
                pnl_series.iloc[i] -= fee
            longs, shorts = [], []
            active = False
            continue

        day_rets = rets.iloc[i]
        if longs and shorts:
            long_ret = day_rets[longs].mean()
            short_ret = day_rets[shorts].mean()
            pnl_series.iloc[i] += long_ret - short_ret

    return pnl_series


def evaluate_signal(pnl, name, dates, verbose=True):
    """Standard evaluation: IS/OOS split, walk-forward, split-half, H-012 corr."""
    total_days = len(pnl)
    if total_days < 200:
        if verbose:
            print(f"  {name}: insufficient data ({total_days} days)")
        return None

    # Trim leading zeros
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

    # Max drawdown
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
                 n_folds=6, fold_days=90, conditional=False,
                 condition_series=None, condition_threshold=None):
    """Walk-forward OOS test."""
    rets = compute_returns(closes)
    dates = closes.index
    total = len(dates)
    results = []

    for fold in range(n_folds):
        test_end = total - fold * fold_days
        test_start = test_end - fold_days
        if test_start < 90:
            break

        if conditional and condition_series is not None:
            pnl = run_conditional_xs_backtest(
                factor_vals, closes.iloc[:test_end],
                n_long, n_short, rebal_days, condition_series, condition_threshold, direction
            )
        else:
            pnl = run_xs_backtest(
                factor_vals, closes.iloc[:test_end],
                n_long, n_short, rebal_days, direction
            )

        test_pnl = pnl.iloc[test_start:test_end]
        if test_pnl.std() > 0:
            fold_sharpe = test_pnl.mean() / test_pnl.std() * np.sqrt(365)
        else:
            fold_sharpe = 0
        results.append(fold_sharpe)

    positive = sum(1 for r in results if r > 0)
    mean_sharpe = np.mean(results) if results else 0
    return positive, len(results), mean_sharpe, results


def split_half_test(factor_vals, closes, n_long, n_short, rebal_days, direction,
                    conditional=False, condition_series=None, condition_threshold=None):
    """Split-half validation."""
    mid = len(closes) // 2

    if conditional and condition_series is not None:
        pnl1 = run_conditional_xs_backtest(
            factor_vals, closes.iloc[:mid], n_long, n_short, rebal_days,
            condition_series, condition_threshold, direction
        )
        pnl2 = run_conditional_xs_backtest(
            factor_vals, closes.iloc[mid:], n_long, n_short, rebal_days,
            condition_series, condition_threshold, direction
        )
    else:
        pnl1 = run_xs_backtest(factor_vals, closes.iloc[:mid], n_long, n_short, rebal_days, direction)
        pnl2 = run_xs_backtest(factor_vals, closes.iloc[mid:], n_long, n_short, rebal_days, direction)

    s1 = pnl1.mean() / pnl1.std() * np.sqrt(365) if pnl1.std() > 0 else 0
    s2 = pnl2.mean() / pnl2.std() * np.sqrt(365) if pnl2.std() > 0 else 0
    return s1, s2


def correlation_with_h012(pnl, closes):
    """Compute correlation with H-012 XS momentum."""
    rets = compute_returns(closes)
    # Simple momentum proxy: 60d return, long top 4, short bottom 4
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
    closes, volumes, funding = load_data()
    features = precompute_cross_asset_features(closes, volumes, funding)

    rets = compute_returns(closes)

    # Define parameter grids
    configs = {
        'H-472': {
            'feature': 'btc_leadlag',
            'directions': ['high_long', 'low_long'],  # high_long = follow-BTC assets
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5, 7],
            'desc': 'BTC Lead-Lag'
        },
        'H-473': {
            'feature': 'corr_cluster',
            'directions': ['low_long', 'high_long'],  # low_long = independent mavericks
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [5, 7, 10],
            'desc': 'Correlation Clustering'
        },
        'H-474': {
            'feature': 'beta_change',
            'directions': ['low_long', 'high_long'],  # low_long = falling beta = safer
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5, 7],
            'desc': 'Beta Change'
        },
        'H-475': {
            'feature': 'fund_spread',
            'directions': ['low_long'],  # contrarian: short overlevered
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [5, 7, 10],
            'desc': 'Relative Funding Spread'
        },
        'H-476': {
            'feature': 'spillover',
            'directions': ['high_long', 'low_long'],
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5],
            'desc': 'Momentum Spillover'
        },
        'H-477': {
            'feature': 'idio_mom',
            'directions': ['high_long', 'low_long'],
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5, 7],
            'desc': 'Idiosyncratic Momentum'
        },
    }

    # Store results for conditional hypotheses
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

        # Count positive Sharpe
        pos = sum(1 for r in grid_results if r['sharpe'] > 0)
        total = len(grid_results)
        pct = pos / total * 100
        print(f"\n  IS Grid: {pos}/{total} ({pct:.0f}%) positive Sharpe")

        # Best result
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

        # Correlation with H-012
        h012_corr = correlation_with_h012(best['pnl'], closes)
        print(f"  H-012 correlation: {h012_corr:.3f}")

        # Neighboring params
        neighbors = [r for r in grid_results if r['sharpe'] > 0
                      and r['direction'] == best['direction']
                      and abs(r['n_long'] - best['n_long']) <= 1
                      and abs(r['rebal'] - best['rebal']) <= 2]
        n_pct = len(neighbors) / max(1, len([r for r in grid_results
                                              if r['direction'] == best['direction']])) * 100
        print(f"  Neighbor robustness: {n_pct:.0f}%")

        if sh_pass:
            print(f"\n  *** {hyp_id} CONFIRMED ***")
            print(f"    Best: {best['direction']}_N{best['n_long']}_R{best['rebal']}")
            print(f"    IS Sharpe: {best['sharpe']:.3f}, Ann: {best['ann_ret']:.1f}%, DD: {best['max_dd']:.1f}%")
            print(f"    WF: {pos_wf}/{n_wf} (mean {mean_wf:.3f})")
            print(f"    SH: {s1:.3f} / {s2:.3f}")
            print(f"    H-012 corr: {h012_corr:.3f}")
        else:
            print(f"  *** BORDERLINE (SH FAIL) — H1={s1:.3f}, H2={s2:.3f} ***")

    # --- H-478: Dispersion-Conditional Momentum ---
    print(f"\n{'='*60}")
    print("H-478: Dispersion-Conditional Momentum")
    print(f"{'='*60}")

    mom60 = closes.pct_change(60)
    disp = features['dispersion']

    # Grid: dispersion threshold percentiles
    disp_valid = disp.dropna()
    grid_results_478 = []
    for pctile in [50, 60, 70]:
        threshold = disp_valid.quantile(pctile / 100)
        for n_long, n_short in [(3, 3), (4, 4)]:
            for rebal in [3, 5, 7]:
                pnl = run_conditional_xs_backtest(
                    mom60, closes, n_long, n_short, rebal,
                    disp, threshold, 'high_long'
                )
                res = evaluate_signal(pnl, f"p{pctile}_N{n_long}_R{rebal}", closes.index, verbose=False)
                if res:
                    res['pctile'] = pctile
                    res['n_long'] = n_long
                    res['n_short'] = n_short
                    res['rebal'] = rebal
                    res['threshold'] = threshold
                    grid_results_478.append(res)

    if grid_results_478:
        pos = sum(1 for r in grid_results_478 if r['sharpe'] > 0)
        total = len(grid_results_478)
        pct = pos / total * 100
        print(f"  IS Grid: {pos}/{total} ({pct:.0f}%) positive Sharpe")
        best478 = max(grid_results_478, key=lambda x: x['sharpe'])
        print(f"  Best: p{best478['pctile']}_N{best478['n_long']}_R{best478['rebal']} — "
              f"Sharpe {best478['sharpe']:.3f}, Ann {best478['ann_ret']:.1f}%, DD {best478['max_dd']:.1f}%")

        if pct >= 80:
            pos_wf, n_wf, mean_wf, wf_folds = walk_forward(
                mom60, closes, best478['n_long'], best478['n_short'], best478['rebal'],
                'high_long', conditional=True, condition_series=disp,
                condition_threshold=best478['threshold']
            )
            print(f"  Walk-forward: {pos_wf}/{n_wf} positive (mean Sharpe {mean_wf:.3f})")

            s1, s2 = split_half_test(mom60, closes, best478['n_long'], best478['n_short'],
                                      best478['rebal'], 'high_long', conditional=True,
                                      condition_series=disp, condition_threshold=best478['threshold'])
            sh_pass = s1 > 0 and s2 > 0
            print(f"  Split-half: H1={s1:.3f}, H2={s2:.3f} — {'PASS' if sh_pass else 'FAIL'}")

            h012_corr = correlation_with_h012(best478['pnl'], closes)
            print(f"  H-012 correlation: {h012_corr:.3f}")

            if sh_pass and pos_wf >= 4:
                print(f"\n  *** H-478 CONFIRMED ***")
            else:
                status = "BORDERLINE" if pos_wf >= 4 else "REJECTED"
                print(f"  *** {status} ***")
        else:
            print(f"  *** REJECTED at IS ({pct:.0f}% < 80%) ***")

    # --- H-479: Correlation Regime Switch ---
    print(f"\n{'='*60}")
    print("H-479: Correlation Regime Switch")
    print(f"{'='*60}")

    corr_regime = features['corr_regime']
    # When correlation is falling (negative regime change), momentum works better
    # When rising, reversal may work better
    grid_results_479 = []
    for threshold_pctile in [40, 50, 60]:
        cr_valid = corr_regime.dropna()
        threshold = cr_valid.quantile(threshold_pctile / 100)
        for n_long, n_short in [(3, 3), (4, 4)]:
            for rebal in [3, 5, 7]:
                # Use momentum when corr is falling (below threshold)
                # Invert condition: trade when regime < threshold (corr falling)
                inv_regime = -corr_regime  # invert so > threshold means corr falling
                pnl = run_conditional_xs_backtest(
                    mom60, closes, n_long, n_short, rebal,
                    inv_regime, -threshold, 'high_long'
                )
                res = evaluate_signal(pnl, f"fall_p{threshold_pctile}_N{n_long}_R{rebal}",
                                       closes.index, verbose=False)
                if res:
                    res['pctile'] = threshold_pctile
                    res['n_long'] = n_long
                    res['n_short'] = n_short
                    res['rebal'] = rebal
                    grid_results_479.append(res)

    if grid_results_479:
        pos = sum(1 for r in grid_results_479 if r['sharpe'] > 0)
        total = len(grid_results_479)
        pct = pos / total * 100
        print(f"  IS Grid: {pos}/{total} ({pct:.0f}%) positive Sharpe")
        best479 = max(grid_results_479, key=lambda x: x['sharpe'])
        print(f"  Best: {best479['name']} — Sharpe {best479['sharpe']:.3f}, Ann {best479['ann_ret']:.1f}%, DD {best479['max_dd']:.1f}%")

        if pct >= 80:
            pos_wf, n_wf, mean_wf, wf_folds = walk_forward(
                mom60, closes, best479['n_long'], best479['n_short'], best479['rebal'],
                'high_long', conditional=True, condition_series=-corr_regime,
                condition_threshold=-corr_regime.dropna().quantile(best479['pctile'] / 100)
            )
            print(f"  Walk-forward: {pos_wf}/{n_wf} positive (mean Sharpe {mean_wf:.3f})")

            s1, s2 = split_half_test(mom60, closes, best479['n_long'], best479['n_short'],
                                      best479['rebal'], 'high_long', conditional=True,
                                      condition_series=-corr_regime,
                                      condition_threshold=-corr_regime.dropna().quantile(best479['pctile'] / 100))
            sh_pass = s1 > 0 and s2 > 0
            print(f"  Split-half: H1={s1:.3f}, H2={s2:.3f} — {'PASS' if sh_pass else 'FAIL'}")

            h012_corr = correlation_with_h012(best479['pnl'], closes)
            print(f"  H-012 correlation: {h012_corr:.3f}")
        else:
            print(f"  *** REJECTED at IS ({pct:.0f}% < 80%) ***")


    print(f"\n{'='*60}")
    print("BATCH SUMMARY")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
