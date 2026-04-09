#!/usr/bin/env python3
"""
Novel signals batch — factor combinations, multi-timeframe, calendar.

  H-488: Factor Composite Score — equal-weight Z-score combination of the top 5
         confirmed daily factors. The idea: no single factor is always right,
         but the average of 5 uncorrelated factors should be more stable.
  H-489: Momentum-Volume Agreement — momentum direction confirmed by volume
         trend direction. Only trade when both agree.
  H-490: Day-of-Month Seasonality — returns vary by day of month (tax events,
         options expiry, rebalancing).
  H-491: Monthly Calendar — returns by month (Jan effect, summer lull, Q4 rally).
  H-492: Distance from 60-Day High — how far each asset is from its 60-day high.
         Assets near highs tend to break out; assets near lows tend to bounce.
  H-493: Consecutive Direction — number of consecutive up/down days as signal.
         Many up days in a row = overbought = reversal; or = momentum.
  H-494: Range Expansion Rate — (high-low range today / 20d avg range).
         Expanding range = breakout potential.
  H-495: Return Autocorrelation — 20-day return autocorrelation(1).
         Negative autocorrelation = mean-reverting = long contrarian.
         Positive = trending = long momentum.
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
    closes_dict, volumes_dict, highs_dict, lows_dict, opens_dict = {}, {}, {}, {}, {}

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
        opens_dict[sym] = df["open"]

    closes = pd.DataFrame(closes_dict).dropna(how="all").ffill().dropna()
    volumes = pd.DataFrame(volumes_dict).reindex(closes.index).ffill().dropna()
    highs = pd.DataFrame(highs_dict).reindex(closes.index).ffill().dropna()
    lows = pd.DataFrame(lows_dict).reindex(closes.index).ffill().dropna()
    opens = pd.DataFrame(opens_dict).reindex(closes.index).ffill().dropna()
    idx = closes.index.intersection(volumes.index)
    closes = closes.loc[idx]
    volumes = volumes.loc[idx]
    highs = highs.loc[idx]
    lows = lows.loc[idx]
    opens = opens.loc[idx]

    print(f"Loaded {len(closes.columns)} assets, {len(closes)} bars")
    return closes, volumes, highs, lows, opens


def compute_returns(closes):
    return closes.pct_change()


def zscore(series):
    """Cross-sectional z-score."""
    m = series.mean()
    s = series.std()
    if s == 0 or np.isnan(s):
        return series * 0
    return (series - m) / s


def precompute_features(closes, volumes, highs, lows, opens):
    """Compute all features."""
    rets = compute_returns(closes)
    dates = closes.index
    syms = closes.columns

    # Features
    composite = pd.DataFrame(index=dates, columns=syms, dtype=float)
    mom_vol_agree = pd.DataFrame(index=dates, columns=syms, dtype=float)
    dist_from_high = pd.DataFrame(index=dates, columns=syms, dtype=float)
    consec_dir = pd.DataFrame(index=dates, columns=syms, dtype=float)
    range_expansion = pd.DataFrame(index=dates, columns=syms, dtype=float)
    ret_autocorr = pd.DataFrame(index=dates, columns=syms, dtype=float)

    print("Pre-computing features batch 3...")

    for i in range(61, len(dates)):
        date_i = dates[i]

        # Factor z-scores for composite
        mom60_raw = {}
        vol_raw = {}
        size_raw = {}
        efficiency_raw = {}
        turnover_raw = {}

        for sym in syms:
            # Momentum (H-012 style)
            ret_60d = closes[sym].iloc[i-1] / closes[sym].iloc[i-61] - 1
            mom60_raw[sym] = ret_60d

            # Volume trend (H-414 style)
            vols_15d = volumes[sym].iloc[max(0, i-15):i].values
            if len(vols_15d) >= 5:
                x = np.arange(len(vols_15d))
                slope, _, _, _, _ = stats.linregress(x, np.log(vols_15d + 1))
                vol_raw[sym] = slope
            else:
                vol_raw[sym] = 0

            # Size (H-031 style)
            dv = closes[sym].iloc[i-1] * volumes[sym].iloc[i-1]
            size_raw[sym] = np.log(dv + 1)

            # Efficiency (H-076 style)
            if i >= 41:
                net = abs(closes[sym].iloc[i-1] - closes[sym].iloc[i-41])
                gross = sum(abs(rets[sym].iloc[j]) for j in range(max(1, i-40), i))
                efficiency_raw[sym] = net / (gross * closes[sym].iloc[i-41] + 1e-12) if gross > 0 else 0.5
            else:
                efficiency_raw[sym] = 0.5

            # Turnover (H-085 style)
            vol_short = rets[sym].iloc[max(0, i-5):i].std()
            vol_long = rets[sym].iloc[max(0, i-20):i].std()
            turnover_raw[sym] = vol_short / (vol_long + 1e-12)

        # Z-score each factor cross-sectionally
        mom_z = zscore(pd.Series(mom60_raw))
        vol_z = zscore(pd.Series(vol_raw))
        size_z = zscore(pd.Series(size_raw))
        eff_z = zscore(pd.Series(efficiency_raw))
        turn_z = zscore(pd.Series(turnover_raw))

        # H-488: Composite = average z-score
        for sym in syms:
            scores = [mom_z.get(sym, 0), vol_z.get(sym, 0), size_z.get(sym, 0),
                      eff_z.get(sym, 0), turn_z.get(sym, 0)]
            composite.at[date_i, sym] = np.nanmean(scores)

        # H-489: Momentum-Volume Agreement
        for sym in syms:
            mom_sign = 1 if mom60_raw.get(sym, 0) > 0 else -1
            vol_sign = 1 if vol_raw.get(sym, 0) > 0 else -1
            agreement = mom_sign * vol_sign  # +1 if both agree
            strength = abs(mom60_raw.get(sym, 0))
            mom_vol_agree.at[date_i, sym] = agreement * strength

        # H-492: Distance from 60-Day High
        for sym in syms:
            high_60d = highs[sym].iloc[max(0, i-60):i].max()
            current = closes[sym].iloc[i-1]
            dist_from_high.at[date_i, sym] = current / high_60d - 1  # 0 = at high, negative = below

        # H-493: Consecutive Direction
        for sym in syms:
            count = 0
            direction = 0
            for j in range(i-1, max(0, i-11), -1):
                r = rets[sym].iloc[j]
                if count == 0:
                    direction = 1 if r > 0 else -1
                    count = direction
                elif (r > 0 and direction > 0) or (r < 0 and direction < 0):
                    count += direction
                else:
                    break
            consec_dir.at[date_i, sym] = count

        # H-494: Range Expansion Rate
        for sym in syms:
            today_range = (highs[sym].iloc[i-1] - lows[sym].iloc[i-1]) / (closes[sym].iloc[i-1] + 1e-12)
            avg_range = ((highs[sym].iloc[max(0, i-20):i] - lows[sym].iloc[max(0, i-20):i]) /
                          closes[sym].iloc[max(0, i-20):i]).mean()
            range_expansion.at[date_i, sym] = today_range / (avg_range + 1e-12)

        # H-495: Return Autocorrelation
        for sym in syms:
            r = rets[sym].iloc[max(0, i-20):i].values
            if len(r) >= 10:
                ac = np.corrcoef(r[:-1], r[1:])[0, 1]
                ret_autocorr.at[date_i, sym] = ac if not np.isnan(ac) else 0
            else:
                ret_autocorr.at[date_i, sym] = 0

    print("Features computed.")
    return {
        'composite': composite,
        'mom_vol_agree': mom_vol_agree,
        'dist_from_high': dist_from_high,
        'consec_dir': consec_dir,
        'range_expansion': range_expansion,
        'ret_autocorr': ret_autocorr,
    }


def run_xs_backtest(factor_vals, closes, n_long, n_short, rebal_days, direction='high_long'):
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


def run_calendar_backtest(closes, calendar_fn, direction='long_if_true'):
    """Calendar-based BTC trade: long/short/flat based on calendar."""
    rets = compute_returns(closes)
    btc = "BTC/USDT"
    dates = closes.index
    pnl_series = pd.Series(0.0, index=dates)

    for i in range(1, len(dates)):
        signal = calendar_fn(dates[i])  # +1 = long, -1 = short, 0 = flat
        pnl_series.iloc[i] = signal * rets[btc].iloc[i]
        # Small fee on position changes
        if i > 1:
            prev_signal = calendar_fn(dates[i-1])
            if signal != prev_signal:
                pnl_series.iloc[i] -= FEE_RATE

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
                 n_folds=6, fold_days=90):
    dates = closes.index
    total = len(dates)
    results = []

    for fold in range(n_folds):
        test_end = total - fold * fold_days
        test_start = test_end - fold_days
        if test_start < 90:
            break

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
    closes, volumes, highs, lows, opens = load_data()
    features = precompute_features(closes, volumes, highs, lows, opens)

    configs = {
        'H-488': {
            'feature': 'composite',
            'directions': ['high_long'],
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5, 7],
            'desc': 'Factor Composite Score'
        },
        'H-489': {
            'feature': 'mom_vol_agree',
            'directions': ['high_long'],
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5, 7],
            'desc': 'Momentum-Volume Agreement'
        },
        'H-492': {
            'feature': 'dist_from_high',
            'directions': ['high_long', 'low_long'],
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5, 7],
            'desc': 'Distance from 60-Day High'
        },
        'H-493': {
            'feature': 'consec_dir',
            'directions': ['high_long', 'low_long'],
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5],
            'desc': 'Consecutive Direction'
        },
        'H-494': {
            'feature': 'range_expansion',
            'directions': ['high_long', 'low_long'],
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5, 7],
            'desc': 'Range Expansion Rate'
        },
        'H-495': {
            'feature': 'ret_autocorr',
            'directions': ['high_long', 'low_long'],  # high = trending, low = mean-reverting
            'n_vals': [(3, 3), (4, 4)],
            'rebal_vals': [3, 5, 7],
            'desc': 'Return Autocorrelation'
        },
    }

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

    # --- Calendar tests ---
    # H-490: Day-of-Month
    print(f"\n{'='*60}")
    print("H-490: Day-of-Month Seasonality")
    print(f"{'='*60}")

    rets = compute_returns(closes)
    btc_rets = rets["BTC/USDT"].dropna()

    # Analyze returns by day of month
    dom_rets = {}
    for date, ret in btc_rets.items():
        day = date.day
        if day not in dom_rets:
            dom_rets[day] = []
        dom_rets[day].append(ret)

    print("  Day-of-month BTC mean returns:")
    significant_days = []
    for day in sorted(dom_rets.keys()):
        r = dom_rets[day]
        mean_r = np.mean(r) * 100
        t_stat = stats.ttest_1samp(r, 0).statistic
        p_val = stats.ttest_1samp(r, 0).pvalue
        sig = "*" if p_val < 0.05 else ""
        if abs(t_stat) > 1.0:
            print(f"    Day {day:2d}: {mean_r:+.3f}% (t={t_stat:.2f}, p={p_val:.3f}) {sig}")
        if p_val < 0.05:
            significant_days.append((day, mean_r))

    if significant_days:
        print(f"  Significant days: {significant_days}")
        # Simple strategy: long on positive significant days, short on negative
        def dom_signal(date):
            day = date.day
            for d, r in significant_days:
                if d == day:
                    return 1 if r > 0 else -1
            return 0
        pnl_dom = run_calendar_backtest(closes, dom_signal)
        res = evaluate_signal(pnl_dom, "DOM_signal", closes.index)
        if res and res['sharpe'] > 0:
            # Check stability
            mid = len(pnl_dom) // 2
            s1 = pnl_dom.iloc[:mid]
            s2 = pnl_dom.iloc[mid:]
            sh1 = s1.mean() / s1.std() * np.sqrt(365) if s1.std() > 0 else 0
            sh2 = s2.mean() / s2.std() * np.sqrt(365) if s2.std() > 0 else 0
            print(f"  Split-half: H1={sh1:.3f}, H2={sh2:.3f}")
    else:
        print("  No statistically significant days found.")

    # H-491: Monthly Seasonality
    print(f"\n{'='*60}")
    print("H-491: Monthly Seasonality")
    print(f"{'='*60}")

    month_rets = {}
    for date, ret in btc_rets.items():
        month = date.month
        if month not in month_rets:
            month_rets[month] = []
        month_rets[month].append(ret)

    print("  Monthly BTC mean returns:")
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    sig_months = []
    for month in range(1, 13):
        if month in month_rets:
            r = month_rets[month]
            mean_r = np.mean(r) * 100
            t_stat = stats.ttest_1samp(r, 0).statistic
            p_val = stats.ttest_1samp(r, 0).pvalue
            sig = "*" if p_val < 0.1 else ""
            print(f"    {month_names[month-1]}: {mean_r:+.3f}% (n={len(r)}, t={t_stat:.2f}, p={p_val:.3f}) {sig}")
            if p_val < 0.1:
                sig_months.append((month, mean_r))

    if sig_months:
        print(f"  Marginally significant months: {[(month_names[m-1], f'{r:+.3f}%') for m, r in sig_months]}")

    print(f"\n{'='*60}")
    print("BATCH SUMMARY")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
