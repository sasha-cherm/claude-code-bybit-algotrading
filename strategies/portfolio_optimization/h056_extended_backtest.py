"""
H-056 Extended Backtest — 2020 to 2026

Re-fetches all available OHLCV history from 2020-01-01 and re-runs the
H-056 portfolio optimizer on the full dataset.

Key questions:
  - How do strategies perform across 2021 alt season?
  - How do they hold up in 2022 crypto winter (LUNA, FTX)?
  - Is the 2024-2025 performance representative or cherry-picked?

Assets unavailable in 2020: OP (May 2022), ARB (Mar 2023), SUI (May 2023)
  → these join the cross-sectional universe from their listing dates.
Funding/premium data: Bybit may have history back to 2021 for some assets.
"""

import sys, os, time
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.data_fetch import fetch_and_cache, get_exchange
import ccxt

ASSETS_FULL  = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'SUI/USDT', 'XRP/USDT',
                'DOGE/USDT', 'AVAX/USDT', 'LINK/USDT', 'ADA/USDT', 'DOT/USDT',
                'NEAR/USDT', 'OP/USDT', 'ARB/USDT', 'ATOM/USDT']
ASSETS_SHORT = [a.replace('/USDT', '') for a in ASSETS_FULL]

DATA_DIR  = Path(__file__).resolve().parent.parent.parent / 'data'
SINCE     = '2020-01-01'
BASE_FEE  = 0.001
SLIP_BPS  = 2.0
MN_STRATS = {'H-021', 'H-031', 'H-046', 'H-052', 'H-053'}

# H-056 weights (MVO-optimal, for reference)
H056_WEIGHTS = {
    'H-031': 0.30, 'H-052': 0.23, 'H-053': 0.16,
    'H-021': 0.15, 'H-039': 0.10, 'H-046': 0.06,
}
H056_LEVERAGE = {
    'H-031': 3.0, 'H-052': 3.0, 'H-053': 3.0,
    'H-021': 3.0, 'H-039': 1.0, 'H-046': 3.0,
}


# ── Data loading ─────────────────────────────────────────────────────────

def fetch_extended_ohlcv():
    """Re-fetch all assets from SINCE, force-extending the cache backward."""
    print(f"[1] Fetching OHLCV from {SINCE} for all assets...")
    exchange = get_exchange()
    daily = {}
    for sym in ASSETS_FULL:
        safe  = sym.replace('/', '_')
        cache = DATA_DIR / f'{safe}_1h.parquet'
        # Check if cache already starts from ~2020
        if cache.exists():
            df_cached = pd.read_parquet(cache)
            earliest = df_cached.index.min()
            if earliest.tz is not None:
                earliest = earliest.tz_localize(None)
            if earliest <= pd.Timestamp('2020-06-01'):
                print(f'  {sym}: cache ok (from {earliest.date()})')
                df = df_cached
            else:
                print(f'  {sym}: extending back from {earliest.date()} → {SINCE}')
                df = fetch_and_cache(sym, '1h', since=SINCE,
                                     force_refresh=True)
        else:
            print(f'  {sym}: no cache, fetching from {SINCE}')
            df = fetch_and_cache(sym, '1h', since=SINCE)

        if len(df) >= 100:
            # Resample to daily
            daily[sym] = df.resample('1D').agg(
                {'open':'first','high':'max','low':'min','close':'last','volume':'sum'}
            ).dropna()
            start = daily[sym].index.min()
            if hasattr(start, 'tz') and start.tz:
                daily[sym].index = daily[sym].index.tz_localize(None)
            print(f'    → {len(daily[sym])} daily bars, '
                  f'{daily[sym].index.min().date()} – {daily[sym].index.max().date()}')
        else:
            print(f'  {sym}: insufficient data, skipping')

    return daily


def load_funding_extended():
    """Load all available funding rate data (may be limited to 2yr for some assets)."""
    funding = {}
    for asset in ASSETS_SHORT:
        for fname in [f'{asset}_USDT_USDT_funding.parquet',
                      f'{asset}_USDT_funding_rates.parquet']:
            fpath = DATA_DIR / fname
            if fpath.exists():
                df = pd.read_parquet(fpath)
                rate_col = 'fundingRate' if 'fundingRate' in df.columns else 'funding_rate'
                if rate_col not in df.columns:
                    continue
                for col in ['timestamp', 'datetime']:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col])
                        df = df.set_index(col)
                        break
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                daily = df[rate_col].resample('1D').mean()
                funding[f'{asset}/USDT'] = daily
                break
    return funding


def load_premium_extended():
    """Load available premium index data."""
    fpath = DATA_DIR / 'all_assets_premium_daily.parquet'
    if not fpath.exists():
        return None
    df = pd.read_parquet(fpath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    wide = df.pivot_table(index='timestamp', columns='asset', values='close')
    if wide.index.tz is not None:
        wide.index = wide.index.tz_localize(None)
    mapped = pd.DataFrame(index=wide.index)
    for col in wide.columns:
        sym = f'{col}/USDT' if '/USDT' not in col else col
        mapped[sym] = wide[col].values
    return mapped


# ── Strategy return generators (reuse optimizer logic) ────────────────────

def run_xs_factor(closes, ranking, rebal_freq, n_long, n_short=None, warmup=65):
    n_short = n_short or n_long
    n = len(closes)
    fee   = BASE_FEE
    slip  = SLIP_BPS / 10_000
    equity = np.ones(n)
    prev_w = pd.Series(0.0, index=closes.columns)
    for i in range(1, n):
        px_today = closes.iloc[i]
        px_prev  = closes.iloc[i-1]
        if i >= warmup and (i - warmup) % rebal_freq == 0:
            ranks = ranking.iloc[i-1].dropna()
            if len(ranks) < n_long + n_short:
                equity[i] = equity[i-1]; continue
            ranked = ranks.sort_values(ascending=False)
            new_w  = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n_long]:  new_w[s] =  1/n_long
            for s in ranked.index[-n_short:]: new_w[s] = -1/n_short
            turnover = (new_w - prev_w).abs().sum() / 2
            fee_drag = turnover * (fee + slip)
            port_ret = (new_w * (px_today/px_prev - 1)).sum() - fee_drag
            prev_w   = new_w
        else:
            port_ret = (prev_w * (px_today/px_prev - 1)).sum()
        equity[i] = equity[i-1] * (1 + port_ret)
    return pd.Series(equity, index=closes.index)


def gen_h031(closes, volumes):
    dv      = closes * volumes
    ranking = dv.rolling(30).mean()
    return run_xs_factor(closes, ranking, rebal_freq=5, n_long=5, warmup=65)


def gen_h021(closes, volumes):
    vs      = volumes.rolling(5).mean()
    vl      = volumes.rolling(20).mean()
    ranking = vs / vl
    return run_xs_factor(closes, ranking, rebal_freq=3, n_long=4, warmup=65)


def gen_h046(closes):
    m_now  = closes.pct_change(20)
    m_past = closes.shift(20).pct_change(20)
    accel  = m_now - m_past
    return run_xs_factor(closes, accel, rebal_freq=3, n_long=4, warmup=45)


def gen_h039(daily):
    btc = daily['BTC/USDT'].copy()
    if btc.index.tz is not None: btc.index = btc.index.tz_localize(None)
    close = btc['close']
    ret   = close.pct_change()
    strat = pd.Series(0.0, index=close.index)
    fee   = 0.0004 * 2
    dow   = close.index.dayofweek
    strat[dow == 2] =  ret[dow == 2] - fee   # Wed long
    strat[dow == 3] = -ret[dow == 3] - fee   # Thu short
    equity = (1 + strat.fillna(0)).cumprod()
    return equity


def gen_h053(closes, funding_data):
    common_assets = [a for a in closes.columns if a in funding_data]
    if len(common_assets) < 6:
        print(f'  H-053: only {len(common_assets)} assets with funding — skipping')
        return None
    closes_sub   = closes[common_assets]
    funding_panel = pd.DataFrame({a: funding_data[a] for a in common_assets})
    common_idx   = closes_sub.index.intersection(funding_panel.dropna(how='all').index)
    if len(common_idx) < 100:
        return None
    closes_sub    = closes_sub.loc[common_idx]
    funding_panel = funding_panel.loc[common_idx]
    ranking       = -funding_panel.rolling(3, min_periods=2).mean()
    return run_xs_factor(closes_sub, ranking, rebal_freq=10, n_long=4, warmup=10)


def gen_h052(closes, premium_data):
    if premium_data is None:
        return None
    common_assets = [a for a in closes.columns if a in premium_data.columns]
    if len(common_assets) < 6:
        print(f'  H-052: only {len(common_assets)} assets with premium — skipping')
        return None
    closes_sub  = closes[common_assets]
    prem_sub    = premium_data[common_assets]
    common_idx  = closes_sub.index.intersection(prem_sub.dropna(how='all').index)
    if len(common_idx) < 100:
        return None
    closes_sub = closes_sub.loc[common_idx]
    prem_sub   = prem_sub.loc[common_idx]
    ranking    = -prem_sub.rolling(5, min_periods=3).mean()
    return run_xs_factor(closes_sub, ranking, rebal_freq=5, n_long=4, warmup=10)


# ── Metrics ──────────────────────────────────────────────────────────────

def metrics(returns):
    if len(returns) < 30: return {}
    ar  = (1 + returns.mean())**365 - 1
    av  = returns.std() * np.sqrt(365)
    sr  = ar / av if av > 0 else 0
    cum = (1 + returns).cumprod()
    dd  = (cum / cum.cummax() - 1).min()
    return dict(annual_return=ar, vol=av, sharpe=sr, max_dd=dd, n_days=len(returns))


def year_return(returns, year):
    yr = returns[returns.index.year == year]
    if len(yr) < 20: return None
    return (1 + yr).prod() ** (365/len(yr)) - 1


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print('='*65)
    print('H-056 EXTENDED BACKTEST — 2020 TO 2026')
    print('='*65)

    # ── 1. Load data ──
    daily = fetch_extended_ohlcv()
    closes  = pd.DataFrame({s: daily[s]['close'] for s in daily})
    volumes = pd.DataFrame({s: daily[s]['volume'] for s in daily})
    if closes.index.tz is not None:
        closes.index  = closes.index.tz_localize(None)
        volumes.index = volumes.index.tz_localize(None)
    closes  = closes.sort_index()
    volumes = volumes.sort_index()

    funding_data  = load_funding_extended()
    premium_data  = load_premium_extended()

    print(f'\n  Price data range: {closes.index.min().date()} – {closes.index.max().date()}')
    print(f'  Funding assets: {len(funding_data)} | Premium: {"yes" if premium_data is not None else "no"}')
    if funding_data:
        sample = list(funding_data.values())[0]
        print(f'  Funding date range: {sample.index.min().date()} – {sample.index.max().date()}')

    # ── 2. Generate strategy returns ──
    print('\n[2] Generating strategy returns...')
    equity = {}
    equity['H-031'] = gen_h031(closes, volumes)
    equity['H-021'] = gen_h021(closes, volumes)
    equity['H-046'] = gen_h046(closes)
    equity['H-039'] = gen_h039(daily)
    equity['H-053'] = gen_h053(closes, funding_data)
    equity['H-052'] = gen_h052(closes, premium_data)
    equity = {k: v for k, v in equity.items() if v is not None}

    strat_rets = {k: v.pct_change().dropna() for k, v in equity.items()}

    print(f'\n  {"Strategy":<10} {"Start":>12} {"End":>12} {"Days":>6} '
          f'{"Ann Ret":>9} {"Sharpe":>8} {"Max DD":>9}')
    print(f'  {"─"*10} {"─"*12} {"─"*12} {"─"*6} {"─"*9} {"─"*8} {"─"*9}')
    for name, ret in strat_rets.items():
        m = metrics(ret)
        print(f'  {name:<10} {ret.index.min().date()!s:>12} {ret.index.max().date()!s:>12} '
              f'{m["n_days"]:>6} {m["annual_return"]:>+9.1%} {m["sharpe"]:>8.2f} {m["max_dd"]:>9.1%}')

    # ── 3. H-056 portfolio (H-055 weights + leverage, on common dates) ──
    print('\n[3] Portfolio performance...')

    # Build returns on common dates for each leverage config
    def build_port(lev_map):
        common = None
        for r in strat_rets.values():
            common = r.index if common is None else common.intersection(r.index)
        port = pd.Series(0.0, index=common)
        total_w = sum(H056_WEIGHTS[k] for k in strat_rets if k in H056_WEIGHTS)
        for name, ret in strat_rets.items():
            if name not in H056_WEIGHTS: continue
            w   = H056_WEIGHTS[name] / total_w
            lev = lev_map.get(name, 1.0)
            port += w * ret.reindex(common).fillna(0) * lev
        return port

    configs = {
        'H-056 1x (no lev)': {k: 1.0 for k in strat_rets},
        'H-056 3x MN':       H056_LEVERAGE,
    }

    port_rets = {label: build_port(lev) for label, lev in configs.items()}

    # Summary metrics
    print(f'\n  {"Config":<22} {"Start":>10} {"Ann Ret":>9} {"Vol":>8} '
          f'{"Sharpe":>8} {"Max DD":>9}')
    print(f'  {"─"*22} {"─"*10} {"─"*9} {"─"*8} {"─"*8} {"─"*9}')
    for label, ret in port_rets.items():
        m = metrics(ret)
        print(f'  {label:<22} {ret.index.min().date()!s:>10} {m["annual_return"]:>+9.1%} '
              f'{m["vol"]:>8.1%} {m["sharpe"]:>8.2f} {m["max_dd"]:>9.1%}')

    # ── 4. Year-by-year including major crypto events ──
    print('\n[4] Year-by-year returns (H-056 3x MN):')
    port = port_rets['H-056 3x MN']
    btc_daily = closes['BTC/USDT'].pct_change() if 'BTC/USDT' in closes else None

    events = {
        2020: 'COVID crash Mar, DeFi summer',
        2021: 'ATH May→crash, alt season, Nov ATH',
        2022: 'LUNA crash May, FTX collapse Nov',
        2023: 'Crypto winter, BTC recovery',
        2024: 'ETF approval Jan, halving Apr, BTC→$100k',
        2025: 'BTC consolidation',
        2026: 'YTD',
    }

    print(f'\n  {"Year":<6} {"Portfolio":>11} {"BTC":>8}  {"Key events"}')
    print(f'  {"─"*6} {"─"*11} {"─"*8}  {"─"*35}')
    for year in range(2020, 2027):
        yr_port = year_return(port, year)
        yr_btc  = year_return(btc_daily, year) if btc_daily is not None else None
        if yr_port is None:
            continue
        btc_str = f'{yr_btc:+.1%}' if yr_btc is not None else 'n/a'
        ev = events.get(year, '')
        print(f'  {year:<6} {yr_port:>+10.1%} {btc_str:>8}  {ev}')

    # ── 5. Individual strategy year-by-year ──
    print('\n[5] Individual strategy year-by-year (1x, unleveraged):')
    strat_names = list(strat_rets.keys())
    header = f'  {"Year":<6}'
    for n in strat_names:
        header += f' {n:>9}'
    header += f' {"BTC":>9}'
    print(header)
    print(f'  {"─"*6}' + f' {"─"*9}'*(len(strat_names)+1))

    for year in range(2020, 2027):
        row = f'  {year:<6}'
        any_data = False
        for name in strat_names:
            yr = year_return(strat_rets[name], year)
            if yr is not None:
                row += f' {yr:>+9.1%}'
                any_data = True
            else:
                row += f' {"n/a":>9}'
        yr_btc = year_return(btc_daily, year) if btc_daily is not None else None
        btc_str = f'{yr_btc:+9.1%}' if yr_btc is not None else f'{"n/a":>9}'
        row += f' {btc_str}'
        if any_data:
            print(row)

    # ── 6. Worst drawdown periods ──
    print('\n[6] Top-5 worst drawdown periods (H-056 3x MN):')
    port3 = port_rets['H-056 3x MN']
    cum   = (1 + port3).cumprod()
    dd    = cum / cum.cummax() - 1
    # Find drawdown troughs
    worst_days = dd.sort_values().head(10)
    print(f'  {"Date":<12} {"DD":>9}  {"BTC DD (from its peak)"}')
    shown = set()
    count = 0
    for dt, val in worst_days.items():
        month = dt.strftime('%Y-%m')
        if month in shown:
            continue
        shown.add(month)
        btc_dd_val = ''
        if btc_daily is not None:
            btc_cum = (1 + btc_daily).cumprod()
            btc_dd  = (btc_cum / btc_cum.cummax() - 1)
            if dt in btc_dd.index:
                btc_dd_val = f'{btc_dd.loc[dt]:+.1%}'
        print(f'  {dt.date()!s:<12} {val:>+9.1%}  BTC: {btc_dd_val}')
        count += 1
        if count >= 5:
            break

    # ── 7. 2021 alt season deep-dive (H-031 stress test) ──
    print('\n[7] 2021 Alt season stress test (H-031 size factor):')
    if 'H-031' in strat_rets:
        h031 = strat_rets['H-031']
        alts = ['SOL/USDT', 'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'LINK/USDT',
                'DOT/USDT', 'NEAR/USDT', 'ATOM/USDT']
        large = ['BTC/USDT', 'ETH/USDT']
        for qtr in [('2021-01-01','2021-03-31'), ('2021-04-01','2021-06-30'),
                    ('2021-07-01','2021-09-30'), ('2021-10-01','2021-12-31')]:
            s, e = pd.Timestamp(qtr[0]), pd.Timestamp(qtr[1])
            period = h031[(h031.index >= s) & (h031.index <= e)]
            if len(period) < 10: continue
            period_ret = (1 + period).prod() - 1
            # BTC vs alts for this period
            btc_qtr = closes.loc[s:e, 'BTC/USDT'] if 'BTC/USDT' in closes else None
            btc_ret = (btc_qtr.iloc[-1] / btc_qtr.iloc[0] - 1) if btc_qtr is not None and len(btc_qtr) > 0 else None
            avail_alts = [a for a in alts if a in closes.columns]
            alt_rets = [closes.loc[s:e, a].iloc[-1]/closes.loc[s:e, a].iloc[0]-1
                        for a in avail_alts if len(closes.loc[s:e, a]) > 0]
            avg_alt = np.mean(alt_rets) if alt_rets else None
            btc_str = f'{btc_ret:+.1%}' if btc_ret is not None else 'n/a'
            alt_str = f'{avg_alt:+.1%}' if avg_alt is not None else 'n/a'
            print(f'  {qtr[0][:7]}–{qtr[1][:7]}: H-031={period_ret:+.1%} | '
                  f'BTC={btc_str} | avg alt={alt_str}')

    print('\n[Done]')


if __name__ == '__main__':
    main()
