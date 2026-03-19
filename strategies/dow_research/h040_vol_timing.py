"""
H-040: Volatility Regime Factor Timing
Scale factor strategy exposure based on realized vol regime.
High vol → reduce exposure, low vol → increase exposure.
"""
import pandas as pd
import numpy as np

assets = ['BTC', 'ETH', 'SOL', 'SUI', 'XRP', 'DOGE', 'AVAX', 'LINK', 'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM']

# Load all assets
all_daily = {}
for asset in assets:
    df = pd.read_parquet(f'data/{asset}_USDT_1h.parquet').reset_index()
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    daily = df.groupby('date').agg({'close': 'last'}).reset_index()
    daily = daily.sort_values('date').reset_index(drop=True)
    daily['ret'] = daily['close'].pct_change()
    all_daily[asset] = daily.dropna()

# Build XS momentum returns (H-012 proxy)
ret_df = pd.DataFrame({a: all_daily[a].set_index('date')['ret'] for a in assets}).dropna()

def xs_factor_returns(ret_df, lookback=60, n=4, rebal=5):
    dates = ret_df.index.tolist()
    cum_ret = (1 + ret_df).cumprod()
    daily_rets = []
    
    longs, shorts = [], []
    counter = 0
    for i in range(lookback, len(dates)):
        if counter == 0 or i == lookback:
            mom = cum_ret.iloc[i] / cum_ret.iloc[i - lookback] - 1
            ranked = mom.sort_values()
            shorts = ranked.index[:n].tolist()
            longs = ranked.index[-n:].tolist()
            counter = rebal
        
        long_ret = ret_df.iloc[i][longs].mean()
        short_ret = ret_df.iloc[i][shorts].mean()
        daily_rets.append(long_ret - short_ret)
        counter -= 1
    
    return pd.Series(daily_rets, index=dates[lookback:])

h012_rets = xs_factor_returns(ret_df, lookback=60, n=4, rebal=5)

# BTC realized vol
btc = all_daily['BTC'].set_index('date')['ret']

print("=" * 70)
print("H-040: Volatility Regime Factor Timing")
print("=" * 70)

# Test: scale H-012 exposure by inverse vol
results = []
for vol_window in [10, 20, 30, 60]:
    btc_vol = btc.rolling(vol_window).std() * np.sqrt(365)
    
    # Quantile-based scaling
    common = h012_rets.index.intersection(btc_vol.dropna().index)
    h012_common = h012_rets[common]
    vol_common = btc_vol[common]
    
    # Method 1: Inverse vol scaling (target 50% vol)
    target_vol = 0.50
    scale = target_vol / vol_common
    scale = scale.clip(0.5, 2.0)  # limits
    
    scaled_ret = h012_common * scale
    
    # Metrics
    base_sharpe = h012_common.mean() / h012_common.std() * np.sqrt(365)
    scaled_sharpe = scaled_ret.mean() / scaled_ret.std() * np.sqrt(365)
    
    base_dd = (np.cumprod(1 + h012_common) / np.maximum.accumulate(np.cumprod(1 + h012_common)) - 1).min()
    scaled_dd = (np.cumprod(1 + scaled_ret) / np.maximum.accumulate(np.cumprod(1 + scaled_ret)) - 1).min()
    
    print(f"\n  Vol window {vol_window}d:")
    print(f"    Base H-012: Sharpe {base_sharpe:.2f}, DD {base_dd*100:.1f}%")
    print(f"    Vol-scaled:  Sharpe {scaled_sharpe:.2f}, DD {scaled_dd*100:.1f}%")
    
    # Method 2: Binary regime (above/below median vol)
    vol_median = vol_common.expanding().median()
    high_vol = vol_common > vol_median
    regime_scale = np.where(high_vol, 0.5, 1.5)
    regime_ret = h012_common * regime_scale
    regime_sharpe = regime_ret.mean() / regime_ret.std() * np.sqrt(365)
    regime_dd = (np.cumprod(1 + regime_ret) / np.maximum.accumulate(np.cumprod(1 + regime_ret)) - 1).min()
    print(f"    Binary regime: Sharpe {regime_sharpe:.2f}, DD {regime_dd*100:.1f}%")
    
    results.append({
        'window': vol_window,
        'base_sharpe': base_sharpe,
        'scaled_sharpe': scaled_sharpe,
        'regime_sharpe': regime_sharpe
    })

# Walk-forward for best method
print("\n" + "=" * 70)
print("Walk-Forward: Vol-Scaled H-012 (20d window)")
print("=" * 70)

btc_vol20 = btc.rolling(20).std() * np.sqrt(365)
common = h012_rets.index.intersection(btc_vol20.dropna().index)
h012_c = h012_rets[common]
vol_c = btc_vol20[common]
dates_list = common.tolist()
n = len(dates_list)

for method, method_name in [('invvol', 'Inverse Vol'), ('regime', 'Binary Regime')]:
    oos_sharpes = []
    for start in range(180, n - 90, 90):
        test_dates = dates_list[start:min(start+90, n)]
        
        test_h012 = h012_c[test_dates]
        test_vol = vol_c[test_dates]
        
        if method == 'invvol':
            scale = 0.50 / test_vol
            scale = scale.clip(0.5, 2.0)
            test_ret = test_h012 * scale
        else:
            train_dates = dates_list[start-180:start]
            train_vol = vol_c[train_dates]
            med = train_vol.median()
            regime = np.where(test_vol > med, 0.5, 1.5)
            test_ret = test_h012 * regime
        
        base_sh = test_h012.mean() / test_h012.std() * np.sqrt(365) if test_h012.std() > 0 else 0
        test_sh = test_ret.mean() / test_ret.std() * np.sqrt(365) if test_ret.std() > 0 else 0
        oos_sharpes.append(test_sh)
    
    pos = sum(1 for s in oos_sharpes if s > 0)
    base_oos = []
    for start in range(180, n - 90, 90):
        test_dates = dates_list[start:min(start+90, n)]
        test_h012 = h012_c[test_dates]
        sh = test_h012.mean() / test_h012.std() * np.sqrt(365) if test_h012.std() > 0 else 0
        base_oos.append(sh)
    
    print(f"\n  {method_name}:")
    print(f"    OOS: {pos}/{len(oos_sharpes)} positive, mean {np.mean(oos_sharpes):.2f}")
    print(f"    Base (no timing): mean {np.mean(base_oos):.2f}")
    improvement = np.mean(oos_sharpes) - np.mean(base_oos)
    print(f"    Improvement: {improvement:+.2f}")

# Also test: does H-039 (DOW) PLUS vol timing work?
print("\n" + "=" * 70)
print("Combined: H-039 DOW + H-040 Vol Timing Overlay on H-012")
print("=" * 70)

btc_indexed = all_daily['BTC'].set_index('date')
common2 = h012_c.index.intersection(btc_indexed.index)
h012_c2 = h012_c[common2]
vol_c2 = vol_c[common2]
dow = pd.to_datetime(pd.Index(common2)).dayofweek

# DOW overlay: scale H-012 up on Wed, down on Thu
dow_scale = np.ones(len(common2))
dow_scale[dow == 2] = 1.5  # Wed: scale up
dow_scale[dow == 3] = 0.5  # Thu: scale down

# Vol overlay: inverse vol
vol_scale = (0.50 / vol_c2).clip(0.5, 2.0).values

combined = h012_c2 * dow_scale * vol_scale
base_sh = h012_c2.mean() / h012_c2.std() * np.sqrt(365)
combined_sh = combined.mean() / combined.std() * np.sqrt(365)
print(f"  Base H-012: Sharpe {base_sh:.2f}")
print(f"  + DOW timing: Sharpe {(h012_c2 * dow_scale).mean() / (h012_c2 * dow_scale).std() * np.sqrt(365):.2f}")
print(f"  + Vol timing: Sharpe {(h012_c2 * vol_scale).mean() / (h012_c2 * vol_scale).std() * np.sqrt(365):.2f}")
print(f"  + Both: Sharpe {combined_sh:.2f}")

