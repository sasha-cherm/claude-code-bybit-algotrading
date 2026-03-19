"""
H-039: Multi-asset version + portfolio impact analysis
"""
import pandas as pd
import numpy as np
from scipy import stats

assets = ['BTC', 'ETH', 'SOL', 'SUI', 'XRP', 'DOGE', 'AVAX', 'LINK', 'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM']

# Load all assets
all_daily = {}
for asset in assets:
    df = pd.read_parquet(f'data/{asset}_USDT_1h.parquet').reset_index()
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    daily = df.groupby('date').agg({'close': 'last'}).reset_index()
    daily = daily.sort_values('date').reset_index(drop=True)
    daily['ret'] = daily['close'].pct_change()
    daily['dow'] = pd.to_datetime(daily['date']).dt.dayofweek
    all_daily[asset] = daily.dropna()

# 1. Per-asset Wed/Thu strategy performance
print("=" * 70)
print("1. Per-Asset Wed Long / Thu Short — BTC Futures")
print("=" * 70)
# For each asset, compute the fixed Wed/Thu strategy
asset_sharpes = {}
for asset in assets:
    df = all_daily[asset].copy()
    rets = []
    for _, row in df.iterrows():
        if row['dow'] == 2:  # Wed
            rets.append(row['ret'])
        elif row['dow'] == 3:  # Thu
            rets.append(-row['ret'])
        else:
            rets.append(0)
    rets = np.array(rets)
    ann_ret = np.mean(rets) * 365
    ann_vol = np.std(rets) * np.sqrt(365)
    sh = ann_ret / ann_vol if ann_vol > 0 else 0
    asset_sharpes[asset] = sh
    print(f"  {asset:5s}: Sharpe {sh:.2f}, ann ret {ann_ret*100:.1f}%")

# 2. Equal-weight all-asset version
print("\n" + "=" * 70)
print("2. Equal-Weight All-Asset Wed/Thu Strategy")
print("=" * 70)
# Align dates
dates = sorted(set.intersection(*[set(all_daily[a]['date']) for a in assets]))
ew_rets = []
for d in dates:
    dow = pd.Timestamp(d).dayofweek
    if dow == 2:  # Wed
        day_ret = np.mean([all_daily[a].set_index('date').loc[d, 'ret'] for a in assets])
        ew_rets.append(day_ret)
    elif dow == 3:  # Thu
        day_ret = -np.mean([all_daily[a].set_index('date').loc[d, 'ret'] for a in assets])
        ew_rets.append(day_ret)
    else:
        ew_rets.append(0)

ew_rets = np.array(ew_rets)
ann_ret = np.mean(ew_rets) * 365
ann_vol = np.std(ew_rets) * np.sqrt(365)
sh = ann_ret / ann_vol if ann_vol > 0 else 0
eq = np.cumprod(1 + ew_rets)
dd = (eq / np.maximum.accumulate(eq) - 1).min() * 100
print(f"  EW all-asset: Sharpe {sh:.2f}, ann ret {ann_ret*100:.1f}%, DD {dd:.1f}%")

# Walk-forward for EW version
print("\n  Walk-forward (fixed Wed/Thu, EW 14 assets):")
n = len(dates)
test_days = 90
step = 90
oos_sharpes = []
for start in range(180, n - test_days, step):
    test_start_idx = start
    test_end_idx = min(start + test_days, n)
    test_dates = dates[test_start_idx:test_end_idx]
    
    test_rets = []
    for d in test_dates:
        dow = pd.Timestamp(d).dayofweek
        if dow == 2:
            day_ret = np.mean([all_daily[a].set_index('date').loc[d, 'ret'] for a in assets])
            test_rets.append(day_ret)
        elif dow == 3:
            day_ret = -np.mean([all_daily[a].set_index('date').loc[d, 'ret'] for a in assets])
            test_rets.append(day_ret)
        else:
            test_rets.append(0)
    
    test_rets = np.array(test_rets)
    if np.std(test_rets) > 0:
        oos_sh = np.mean(test_rets) / np.std(test_rets) * np.sqrt(365)
    else:
        oos_sh = 0
    oos_sharpes.append(oos_sh)

positive = sum(1 for s in oos_sharpes if s > 0)
print(f"    {positive}/{len(oos_sharpes)} positive ({100*positive/len(oos_sharpes):.0f}%), mean OOS Sharpe {np.mean(oos_sharpes):.2f}")
for i, sh in enumerate(oos_sharpes):
    print(f"      Fold {i+1}: Sharpe {sh:.2f}")

# 3. Portfolio Impact: Add H-039 (BTC Wed/Thu) to existing 5-strat portfolio
print("\n" + "=" * 70)
print("3. Portfolio Impact — Adding H-039 (BTC) to Existing 5 Strategies")
print("=" * 70)

# Reconstruct existing strategy daily returns
btc_df = all_daily['BTC'].copy()
btc_df['ema5'] = btc_df['close'].ewm(span=5, adjust=False).mean()
btc_df['ema40'] = btc_df['close'].ewm(span=40, adjust=False).mean()
btc_df['h009'] = btc_df['ema5'].shift(1) > btc_df['ema40'].shift(1)
btc_df['h009_ret'] = np.where(btc_df['h009'], btc_df['ret'], -btc_df['ret'])

# H-039
btc_df['h039_ret'] = 0.0
btc_df.loc[btc_df['dow'] == 2, 'h039_ret'] = btc_df.loc[btc_df['dow'] == 2, 'ret']
btc_df.loc[btc_df['dow'] == 3, 'h039_ret'] = -btc_df.loc[btc_df['dow'] == 3, 'ret']

# Simulate H-012 (XS momentum) — simplified: long top-4 60d momentum, short bottom-4
# Build actual cross-sectional momentum returns
aligned = {}
for a in assets:
    df = all_daily[a].set_index('date')
    aligned[a] = df['ret']
ret_df = pd.DataFrame(aligned)
ret_df = ret_df.dropna()

# XS Momentum: 60d lookback, weekly rebal
def xs_momentum(ret_df, lookback=60, n_long=4, n_short=4, rebal_period=5):
    dates = ret_df.index.tolist()
    cum_ret = (1 + ret_df).cumprod()
    daily_rets = []
    current_longs = []
    current_shorts = []
    rebal_counter = 0
    
    for i in range(lookback, len(dates)):
        if rebal_counter == 0 or i == lookback:
            # Compute momentum scores
            mom = cum_ret.iloc[i] / cum_ret.iloc[i - lookback] - 1
            ranked = mom.sort_values()
            current_shorts = ranked.index[:n_short].tolist()
            current_longs = ranked.index[-n_long:].tolist()
            rebal_counter = rebal_period
        
        # Daily return
        long_ret = ret_df.iloc[i][current_longs].mean()
        short_ret = ret_df.iloc[i][current_shorts].mean()
        daily_rets.append(long_ret - short_ret)
        rebal_counter -= 1
    
    return pd.Series(daily_rets, index=dates[lookback:])

h012_rets = xs_momentum(ret_df, lookback=60, n_long=4, n_short=4, rebal_period=5)

# Low-vol factor (H-019)
def xs_lowvol(ret_df, vol_window=20, n_long=3, n_short=3, rebal_period=21):
    dates = ret_df.index.tolist()
    daily_rets = []
    current_longs = []
    current_shorts = []
    rebal_counter = 0
    
    for i in range(vol_window, len(dates)):
        if rebal_counter == 0 or i == vol_window:
            vols = ret_df.iloc[i-vol_window:i].std()
            ranked = vols.sort_values()
            current_longs = ranked.index[:n_long].tolist()
            current_shorts = ranked.index[-n_short:].tolist()
            rebal_counter = rebal_period
        
        long_ret = ret_df.iloc[i][current_longs].mean()
        short_ret = ret_df.iloc[i][current_shorts].mean()
        daily_rets.append(long_ret - short_ret)
        rebal_counter -= 1
    
    return pd.Series(daily_rets, index=dates[vol_window:])

h019_rets = xs_lowvol(ret_df)

# Volume momentum (H-021)
def xs_volmom(ret_df, vs=5, vl=20, n=4, rebal=3):
    # Proxy: use ret as proxy, actual volume not available in aligned df
    # Skip — just use correlation analysis
    pass

# For portfolio, use available strategies
common_dates = sorted(set(btc_df.set_index('date').index) & set(h012_rets.index) & set(h019_rets.index))
common_dates = [d for d in common_dates if d in btc_df.set_index('date').index]

btc_indexed = btc_df.set_index('date')

port_data = pd.DataFrame(index=common_dates)
port_data['h009'] = [btc_indexed.loc[d, 'h009_ret'] if d in btc_indexed.index else 0 for d in common_dates]
port_data['h012'] = [h012_rets[d] if d in h012_rets.index else 0 for d in common_dates]
port_data['h019'] = [h019_rets[d] if d in h019_rets.index else 0 for d in common_dates]
port_data['h039'] = [btc_indexed.loc[d, 'h039_ret'] if d in btc_indexed.index else 0 for d in common_dates]
port_data = port_data.dropna()

# Correlation matrix
print("  Correlation matrix:")
corr = port_data[['h009', 'h012', 'h019', 'h039']].corr()
for col in corr.columns:
    vals = [f"{corr.loc[col, c]:.3f}" for c in corr.columns]
    print(f"    {col}: {', '.join(vals)}")

# Portfolio Sharpe at various allocations
print("\n  Portfolio Sharpe at various H-039 allocations:")
# Base: h009=10%, h012=10%, h019=15%, remaining for h011+h021 (no daily return contribution here)
# Since H-011 and H-021 aren't easily reconstructed, use 3-strat proxy
for h039_pct in [0, 5, 10, 15, 20]:
    remaining = 100 - h039_pct
    # Scale existing proportionally
    w009 = 10 * remaining / 100
    w012 = 10 * remaining / 100
    w019 = 15 * remaining / 100
    
    port_ret = (w009 * port_data['h009'] + w012 * port_data['h012'] + 
                w019 * port_data['h019'] + h039_pct * port_data['h039']) / 100
    
    ann_ret = port_ret.mean() * 365
    ann_vol = port_ret.std() * np.sqrt(365)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    print(f"    H-039 @ {h039_pct:2d}%: Sharpe {sharpe:.2f}, ann ret {ann_ret*100:.1f}%, vol {ann_vol*100:.1f}%")

# 4. All-asset Wed/Thu version — does it work on all assets?
print("\n" + "=" * 70)
print("4. Per-Asset Walk-Forward (Fixed Wed/Thu, 6 folds)")
print("=" * 70)
for asset in ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE']:
    df = all_daily[asset].copy()
    dates_a = sorted(df['date'].unique())
    n = len(dates_a)
    oos_sh_list = []
    for start in range(180, n - 90, 90):
        te = df[(df['date'] >= dates_a[start]) & (df['date'] < dates_a[min(start+90, n)])]
        tr = []
        for _, row in te.iterrows():
            if row['dow'] == 2: tr.append(row['ret'])
            elif row['dow'] == 3: tr.append(-row['ret'])
            else: tr.append(0)
        tr = np.array(tr)
        if np.std(tr) > 0:
            oos_sh_list.append(np.mean(tr)/np.std(tr)*np.sqrt(365))
    pos = sum(1 for s in oos_sh_list if s > 0)
    print(f"  {asset:5s}: {pos}/{len(oos_sh_list)} positive, mean OOS Sharpe {np.mean(oos_sh_list):.2f}")

