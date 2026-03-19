"""
H-039: Day-of-Week Seasonality Analysis
Test whether certain days have systematically different returns.
Could serve as timing overlay for existing strategies.
"""
import pandas as pd
import numpy as np
from scipy import stats

assets = ['BTC', 'ETH', 'SOL', 'SUI', 'XRP', 'DOGE', 'AVAX', 'LINK', 'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM']

# Load all assets
returns_by_asset = {}
for asset in assets:
    df = pd.read_parquet(f'data/{asset}_USDT_1h.parquet').reset_index()
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    daily = df.groupby('date').agg({'close': 'last'}).reset_index()
    daily = daily.sort_values('date').reset_index(drop=True)
    daily['ret'] = daily['close'].pct_change()
    daily['dow'] = pd.to_datetime(daily['date']).dt.dayofweek  # 0=Mon, 6=Sun
    returns_by_asset[asset] = daily[['date', 'ret', 'dow']].dropna()

# Combine all assets
all_rets = pd.concat([df.assign(asset=a) for a, df in returns_by_asset.items()])

print("=" * 70)
print("H-039: Day-of-Week Seasonality Analysis")
print("=" * 70)

# 1. Average return by day of week (all assets)
print("\n--- Average Daily Return by Day of Week (All 14 Assets) ---")
dow_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
for dow in range(7):
    rets = all_rets[all_rets['dow'] == dow]['ret']
    mean = rets.mean() * 100
    std = rets.std() * 100
    t_stat, p_val = stats.ttest_1samp(rets, 0)
    n = len(rets)
    print(f"  {dow_names[dow]}: mean={mean:+.4f}% std={std:.3f}% t={t_stat:.2f} p={p_val:.4f} n={n}")

# 2. BTC specifically
print("\n--- BTC Return by Day of Week ---")
btc = returns_by_asset['BTC']
for dow in range(7):
    rets = btc[btc['dow'] == dow]['ret']
    mean = rets.mean() * 100
    std = rets.std() * 100
    t_stat, p_val = stats.ttest_1samp(rets, 0)
    print(f"  {dow_names[dow]}: mean={mean:+.4f}% std={std:.3f}% t={t_stat:.2f} p={p_val:.4f} n={len(rets)}")

# 3. Train/Test split (first year vs second year)
all_dates = sorted(all_rets['date'].unique())
mid = all_dates[len(all_dates)//2]
train = all_rets[all_rets['date'] < mid]
test = all_rets[all_rets['date'] >= mid]

print(f"\n--- Train/Test Split (train < {mid}, test >= {mid}) ---")
print("   Train:")
train_means = []
for dow in range(7):
    rets = train[train['dow'] == dow]['ret']
    mean = rets.mean() * 100
    train_means.append(mean)
    t_stat, p_val = stats.ttest_1samp(rets, 0)
    print(f"  {dow_names[dow]}: mean={mean:+.4f}% p={p_val:.4f}")

print("   Test:")
test_means = []
for dow in range(7):
    rets = test[test['dow'] == dow]['ret']
    mean = rets.mean() * 100
    test_means.append(mean)
    t_stat, p_val = stats.ttest_1samp(rets, 0)
    print(f"  {dow_names[dow]}: mean={mean:+.4f}% p={p_val:.4f}")

corr = np.corrcoef(train_means, test_means)[0,1]
print(f"\n   Train/Test correlation of DOW means: {corr:.3f}")

# 4. Weekend vs Weekday effect
print("\n--- Weekend (Sat+Sun) vs Weekday Effect ---")
weekday = all_rets[all_rets['dow'] < 5]['ret']
weekend = all_rets[all_rets['dow'] >= 5]['ret']
t_stat, p_val = stats.ttest_ind(weekday, weekend)
print(f"  Weekday mean: {weekday.mean()*100:+.4f}%")
print(f"  Weekend mean: {weekend.mean()*100:+.4f}%")
print(f"  Difference t-test: t={t_stat:.2f} p={p_val:.4f}")

# 5. ANOVA test
from scipy.stats import f_oneway
groups = [all_rets[all_rets['dow'] == d]['ret'].values for d in range(7)]
f_stat, p_val = f_oneway(*groups)
print(f"\n--- ANOVA (all 7 days) ---")
print(f"  F-stat: {f_stat:.3f}, p-value: {p_val:.4f}")

# 6. Kruskal-Wallis (non-parametric)
from scipy.stats import kruskal
h_stat, p_val = kruskal(*groups)
print(f"  Kruskal-Wallis H: {h_stat:.3f}, p-value: {p_val:.4f}")

# 7. Simple trading strategy: long on best days, short on worst
print("\n--- Simple DOW Trading Strategy (14 assets) ---")
# Use training set to pick best/worst days
train_btc = returns_by_asset['BTC']
train_btc = train_btc[pd.to_datetime(train_btc['date']) < pd.Timestamp(mid)]
test_btc = returns_by_asset['BTC']
test_btc = test_btc[pd.to_datetime(test_btc['date']) >= pd.Timestamp(mid)]

btc_train_means = {}
for dow in range(7):
    btc_train_means[dow] = train_btc[train_btc['dow'] == dow]['ret'].mean()

# Long on best 2 days, short on worst 2
sorted_days = sorted(btc_train_means, key=btc_train_means.get)
short_days = sorted_days[:2]
long_days = sorted_days[-2:]
print(f"  Train: LONG on {[dow_names[d] for d in long_days]}, SHORT on {[dow_names[d] for d in short_days]}")

# Test performance
test_btc_full = returns_by_asset['BTC'].copy()
test_btc_full = test_btc_full[pd.to_datetime(test_btc_full['date']) >= pd.Timestamp(mid)]
strat_rets = []
for _, row in test_btc_full.iterrows():
    if row['dow'] in long_days:
        strat_rets.append(row['ret'])
    elif row['dow'] in short_days:
        strat_rets.append(-row['ret'])
    # else: flat

strat_rets = np.array(strat_rets)
ann_ret = np.mean(strat_rets) * 365 * 100
ann_vol = np.std(strat_rets) * np.sqrt(365) * 100
sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
print(f"  OOS: {len(strat_rets)} trading days, ann return: {ann_ret:.1f}%, Sharpe: {sharpe:.2f}")

# 8. Cross-asset consistency
print("\n--- Cross-Asset Consistency (which day is best/worst for each asset) ---")
for asset in assets[:6]:  # show top 6
    df = returns_by_asset[asset]
    means = [df[df['dow'] == d]['ret'].mean() * 100 for d in range(7)]
    best_day = dow_names[np.argmax(means)]
    worst_day = dow_names[np.argmin(means)]
    print(f"  {asset:5s}: best={best_day} ({max(means):+.3f}%), worst={worst_day} ({min(means):+.3f}%)")

