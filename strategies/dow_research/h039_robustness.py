"""
H-039: Robustness checks — rolling window, per-quarter, and overlay value
"""
import pandas as pd
import numpy as np
from scipy import stats

assets = ['BTC', 'ETH', 'SOL', 'SUI', 'XRP', 'DOGE', 'AVAX', 'LINK', 'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM']
dow_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

# Load all assets
all_rets = []
for asset in assets:
    df = pd.read_parquet(f'data/{asset}_USDT_1h.parquet').reset_index()
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    daily = df.groupby('date').agg({'close': 'last'}).reset_index()
    daily = daily.sort_values('date').reset_index(drop=True)
    daily['ret'] = daily['close'].pct_change()
    daily['dow'] = pd.to_datetime(daily['date']).dt.dayofweek
    daily = daily.dropna()
    daily['asset'] = asset
    all_rets.append(daily)
all_rets = pd.concat(all_rets)
all_rets['date_dt'] = pd.to_datetime(all_rets['date'])

# 1. Rolling 6-month window consistency for Wed/Thu
print("=" * 60)
print("1. Rolling 6-month Window: Wed vs Thu Return Diff")
print("=" * 60)
all_rets['year_month'] = all_rets['date_dt'].dt.to_period('M')
months = sorted(all_rets['year_month'].unique())

for window_size in [6, 3]:
    wed_better = 0
    total = 0
    for i in range(window_size, len(months)):
        window_months = months[i-window_size:i]
        mask = all_rets['year_month'].isin(window_months)
        subset = all_rets[mask]
        wed_mean = subset[subset['dow'] == 2]['ret'].mean()
        thu_mean = subset[subset['dow'] == 3]['ret'].mean()
        if wed_mean > thu_mean:
            wed_better += 1
        total += 1
    print(f"  {window_size}-month window: Wed > Thu in {wed_better}/{total} windows ({100*wed_better/total:.0f}%)")

# 2. Per-quarter analysis
print("\n" + "=" * 60)
print("2. Per-Quarter: Wed Return vs Thu Return")
print("=" * 60)
all_rets['quarter'] = all_rets['date_dt'].dt.to_period('Q')
quarters = sorted(all_rets['quarter'].unique())
wed_wins = 0
for q in quarters:
    qdata = all_rets[all_rets['quarter'] == q]
    wed = qdata[qdata['dow'] == 2]['ret'].mean() * 100
    thu = qdata[qdata['dow'] == 3]['ret'].mean() * 100
    diff = wed - thu
    win = "Wed" if diff > 0 else "Thu"
    if diff > 0:
        wed_wins += 1
    print(f"  {q}: Wed {wed:+.3f}% | Thu {thu:+.3f}% | diff {diff:+.3f}% -> {win}")
print(f"  Wed wins {wed_wins}/{len(quarters)} quarters ({100*wed_wins/len(quarters):.0f}%)")

# 3. Simple overlay: scale H-012 XSMom by DOW
# Simulate: on Wed increase position 50%, on Thu reduce 50%, other days normal
print("\n" + "=" * 60)
print("3. DOW Overlay for Cross-Sectional Factors")
print("=" * 60)

# Load H-012 backtest results to simulate overlay
# Use BTC as proxy for simplicity -- compute XS momentum returns
from pathlib import Path

# Actually let's just compute: what if we scale any strategy by DOW?
# Model: base strategy has flat daily return. On Wed, return is +0.5%, on Thu, return is -0.65%
# If we double up on Wed and go flat on Thu, how much does that add?
# Added return from overlay = weight_adj * (day_mean - overall_mean)
# This is marginal -- let's compute it properly

# Simulate a DOW timing strategy on top of a cross-sectional factor
# Using all-asset average return as proxy
print("  If we scale factor exposure by DOW (1.5x Wed, 0.5x Thu):")
overall_mean = all_rets['ret'].mean()
wed_mean = all_rets[all_rets['dow'] == 2]['ret'].mean()
thu_mean = all_rets[all_rets['dow'] == 3]['ret'].mean()
wed_excess = (wed_mean - overall_mean) * 0.5  # extra 50% allocation
thu_saving = (overall_mean - thu_mean) * 0.5   # reduced 50% allocation
days_per_year = 365
wed_add = wed_excess * 52  # ~52 Wednesdays per year
thu_add = thu_saving * 52
total_add = (wed_add + thu_add) * 100
print(f"  Added annual return from overlay: ~{total_add:.2f}%")
print(f"  This is marginal -- DOW effects are ~0.5%/day at best")

# 4. Long Wednesday, short Thursday strategy (BTC only, OOS)
print("\n" + "=" * 60)
print("4. Long Wed + Short Thu Strategy (BTC, full period)")
print("=" * 60)
btc = all_rets[all_rets['asset'] == 'BTC'].copy()
btc_strat = []
for _, row in btc.iterrows():
    if row['dow'] == 2:  # Wed
        btc_strat.append(row['ret'])
    elif row['dow'] == 3:  # Thu
        btc_strat.append(-row['ret'])
    # else flat

btc_strat = np.array(btc_strat)
ann_ret = np.mean(btc_strat) * 365 * 100
ann_vol = np.std(btc_strat) * np.sqrt(365) * 100
sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
eq = np.cumprod(1 + btc_strat)
dd = (eq / np.maximum.accumulate(eq) - 1).min() * 100
print(f"  {len(btc_strat)} trades, ann return: {ann_ret:.1f}%, ann vol: {ann_vol:.1f}%, Sharpe: {sharpe:.2f}, max DD: {dd:.1f}%")

# Split train/test
mid_idx = len(btc_strat) // 2
train_sharpe = np.mean(btc_strat[:mid_idx]) / np.std(btc_strat[:mid_idx]) * np.sqrt(365/7*2) if np.std(btc_strat[:mid_idx]) > 0 else 0
test_sharpe = np.mean(btc_strat[mid_idx:]) / np.std(btc_strat[mid_idx:]) * np.sqrt(365/7*2) if np.std(btc_strat[mid_idx:]) > 0 else 0
print(f"  Train Sharpe: {train_sharpe:.2f}, Test Sharpe: {test_sharpe:.2f}")

# 5. Check if DOW effect survives after controlling for BTC trend
print("\n" + "=" * 60)
print("5. DOW Effect Controlling for BTC Trend")
print("=" * 60)
# Regress daily returns on DOW dummies + BTC return
btc_rets = all_rets[all_rets['asset'] == 'BTC'][['date', 'ret']].rename(columns={'ret': 'btc_ret'})
merged = all_rets.merge(btc_rets, on='date')
merged = merged[merged['asset'] != 'BTC']

from sklearn.linear_model import LinearRegression
X_dow = pd.get_dummies(merged['dow'], prefix='dow', drop_first=True).values
X_btc = merged['btc_ret'].values.reshape(-1, 1)
X = np.hstack([X_dow, X_btc])
y = merged['ret'].values

reg = LinearRegression().fit(X, y)
print("  Coefficients (vs Monday baseline):")
for i, dow in enumerate(['Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']):
    print(f"    {dow}: {reg.coef_[i]*100:+.3f}%")
print(f"    BTC_ret: {reg.coef_[-1]:.3f}")
print(f"  R²: {reg.score(X, y):.4f}")
# t-stats for DOW coefficients
y_pred = reg.predict(X)
residuals = y - y_pred
mse = np.mean(residuals**2)
XtX_inv = np.linalg.inv(X.T @ X)
se = np.sqrt(mse * np.diag(XtX_inv))
for i, dow in enumerate(['Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']):
    t = reg.coef_[i] / se[i]
    p = 2 * (1 - stats.t.cdf(abs(t), len(y) - X.shape[1]))
    print(f"    {dow}: t={t:.2f} p={p:.4f}")

