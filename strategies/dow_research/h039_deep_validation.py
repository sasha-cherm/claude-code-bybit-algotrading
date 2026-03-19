"""
H-039 Deep Validation: Correct annualization + walk-forward + factor overlay
"""
import pandas as pd
import numpy as np
from scipy import stats

assets = ['BTC', 'ETH', 'SOL', 'SUI', 'XRP', 'DOGE', 'AVAX', 'LINK', 'ADA', 'DOT', 'NEAR', 'OP', 'ARB', 'ATOM']
dow_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

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

# ====== CORRECTED BTC STRATEGY ======
print("=" * 70)
print("H-039: BTC Long Wed / Short Thu — Corrected Annualization")
print("=" * 70)

btc = all_daily['BTC'].copy()
dates = sorted(btc['date'].unique())
mid = dates[len(dates)//2]

# Build equity curve with proper daily tracking
equity = [1.0]
trade_returns = []
for _, row in btc.iterrows():
    if row['dow'] == 2:  # Wed: long
        trade_returns.append(row['ret'])
        equity.append(equity[-1] * (1 + row['ret']))
    elif row['dow'] == 3:  # Thu: short  
        trade_returns.append(-row['ret'])
        equity.append(equity[-1] * (1 - row['ret']))
    else:
        equity.append(equity[-1])  # flat days

equity = np.array(equity[1:])
trade_returns = np.array(trade_returns)
# Annualize using actual calendar days
n_days = len(btc)
n_trades = len(trade_returns)
total_ret = equity[-1] / equity[0] - 1
years = n_days / 365
ann_ret = (1 + total_ret) ** (1/years) - 1
# For Sharpe, use daily returns with all days (including flat)
all_daily_rets = []
for _, row in btc.iterrows():
    if row['dow'] == 2:
        all_daily_rets.append(row['ret'])
    elif row['dow'] == 3:
        all_daily_rets.append(-row['ret'])
    else:
        all_daily_rets.append(0.0)
all_daily_rets = np.array(all_daily_rets)
ann_vol = np.std(all_daily_rets) * np.sqrt(365)
sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
dd = (equity / np.maximum.accumulate(equity) - 1).min() * 100

print(f"  Full period: {n_days} days, {n_trades} trades")
print(f"  Total return: {total_ret*100:.1f}%, Annual return: {ann_ret*100:.1f}%")
print(f"  Annual vol: {ann_vol*100:.1f}%, Sharpe: {sharpe:.2f}, Max DD: {dd:.1f}%")

# Train/Test
train_mask = btc['date'] < mid
test_mask = btc['date'] >= mid

for label, mask in [("Train", train_mask), ("Test", test_mask)]:
    subset = btc[mask]
    eq = [1.0]
    dr = []
    for _, row in subset.iterrows():
        if row['dow'] == 2:
            dr.append(row['ret'])
            eq.append(eq[-1] * (1 + row['ret']))
        elif row['dow'] == 3:
            dr.append(-row['ret'])
            eq.append(eq[-1] * (1 - row['ret']))
        else:
            eq.append(eq[-1])
    eq = np.array(eq[1:])
    adr = []
    for _, row in subset.iterrows():
        if row['dow'] == 2: adr.append(row['ret'])
        elif row['dow'] == 3: adr.append(-row['ret'])
        else: adr.append(0)
    adr = np.array(adr)
    yrs = len(subset) / 365
    tr = eq[-1] / eq[0] - 1
    ar = (1 + tr) ** (1/yrs) - 1 if yrs > 0 else 0
    av = np.std(adr) * np.sqrt(365)
    sh = ar / av if av > 0 else 0
    mdd = (eq / np.maximum.accumulate(eq) - 1).min() * 100
    print(f"  {label}: annual return {ar*100:.1f}%, Sharpe {sh:.2f}, DD {mdd:.1f}%")

# ====== WALK-FORWARD ======
print("\n" + "=" * 70)
print("Walk-Forward: 6-month train, 3-month test, rolling")
print("=" * 70)

btc_dates = sorted(btc['date'].unique())
n_total = len(btc_dates)
train_days = 180  # ~6 months
test_days = 90    # ~3 months
step = test_days

oos_sharpes = []
fold = 0
for start in range(train_days, n_total - test_days, step):
    fold += 1
    train_start = btc_dates[start - train_days]
    train_end = btc_dates[start - 1]
    test_start = btc_dates[start]
    test_end = btc_dates[min(start + test_days - 1, n_total - 1)]
    
    tr = btc[(btc['date'] >= train_start) & (btc['date'] <= train_end)]
    te = btc[(btc['date'] >= test_start) & (btc['date'] <= test_end)]
    
    # Find best/worst DOW in training
    dow_means = {}
    for d in range(7):
        rets = tr[tr['dow'] == d]['ret']
        if len(rets) > 0:
            dow_means[d] = rets.mean()
    
    sorted_dows = sorted(dow_means, key=dow_means.get)
    short_day = sorted_dows[0]  # worst
    long_day = sorted_dows[-1]   # best
    
    # Test on OOS
    test_rets = []
    for _, row in te.iterrows():
        if row['dow'] == long_day:
            test_rets.append(row['ret'])
        elif row['dow'] == short_day:
            test_rets.append(-row['ret'])
        else:
            test_rets.append(0)
    test_rets = np.array(test_rets)
    
    if np.std(test_rets) > 0:
        oos_sh = np.mean(test_rets) / np.std(test_rets) * np.sqrt(365)
    else:
        oos_sh = 0
    oos_sharpes.append(oos_sh)
    print(f"  Fold {fold}: train {train_start}–{train_end}, test {test_start}–{test_end}")
    print(f"         LONG {dow_names[long_day]}, SHORT {dow_names[short_day]} → OOS Sharpe {oos_sh:.2f}")

positive = sum(1 for s in oos_sharpes if s > 0)
print(f"\n  Walk-Forward: {positive}/{len(oos_sharpes)} positive ({100*positive/len(oos_sharpes):.0f}%), mean OOS Sharpe {np.mean(oos_sharpes):.2f}")

# ====== FIXED WED/THU WALK-FORWARD ======
print("\n" + "=" * 70)
print("Fixed Wed/Thu Walk-Forward (no day selection, always Wed long / Thu short)")
print("=" * 70)
fixed_oos = []
for start in range(train_days, n_total - test_days, step):
    test_start = btc_dates[start]
    test_end = btc_dates[min(start + test_days - 1, n_total - 1)]
    te = btc[(btc['date'] >= test_start) & (btc['date'] <= test_end)]
    test_rets = []
    for _, row in te.iterrows():
        if row['dow'] == 2:  # Wed
            test_rets.append(row['ret'])
        elif row['dow'] == 3:  # Thu
            test_rets.append(-row['ret'])
        else:
            test_rets.append(0)
    test_rets = np.array(test_rets)
    if np.std(test_rets) > 0:
        sh = np.mean(test_rets) / np.std(test_rets) * np.sqrt(365)
    else:
        sh = 0
    fixed_oos.append(sh)

positive = sum(1 for s in fixed_oos if s > 0)
print(f"  Fixed Wed/Thu: {positive}/{len(fixed_oos)} positive ({100*positive/len(fixed_oos):.0f}%), mean OOS Sharpe {np.mean(fixed_oos):.2f}")
for i, sh in enumerate(fixed_oos):
    print(f"    Fold {i+1}: Sharpe {sh:.2f}")

# ====== CORRELATION WITH EXISTING STRATEGIES ======
print("\n" + "=" * 70)
print("Correlation with H-009 (BTC trend)")
print("=" * 70)
# H-009 is long when EMA5 > EMA40, short otherwise
btc_full = all_daily['BTC'].copy()
btc_full['ema5'] = btc_full['close'].ewm(span=5, adjust=False).mean()
btc_full['ema40'] = btc_full['close'].ewm(span=40, adjust=False).mean()
btc_full['h009_signal'] = np.where(btc_full['ema5'] > btc_full['ema40'], 1, -1)
btc_full['h009_ret'] = btc_full['h009_signal'].shift(1) * btc_full['ret']
btc_full['h039_ret'] = 0.0
btc_full.loc[btc_full['dow'] == 2, 'h039_ret'] = btc_full.loc[btc_full['dow'] == 2, 'ret']
btc_full.loc[btc_full['dow'] == 3, 'h039_ret'] = -btc_full.loc[btc_full['dow'] == 3, 'ret']

valid = btc_full.dropna(subset=['h009_ret'])
corr = valid['h009_ret'].corr(valid['h039_ret'])
print(f"  H-039 vs H-009 daily return correlation: {corr:.3f}")

# ====== FEE ROBUSTNESS ======
print("\n" + "=" * 70)
print("Fee Robustness (BTC, round-trip fee per trade)")
print("=" * 70)
for fee_bps in [0, 5, 10, 20, 50]:
    fee = fee_bps / 10000  # per side
    # 2 trades per week (enter and exit), so 4 fee events per week
    # Actually: enter Wed morning, exit Wed evening (or hold overnight?)
    # Simpler: we're doing a 1-day trade, so 2 fee events (enter + exit) per trade
    rets_after_fees = trade_returns.copy() - 2 * fee  # round-trip
    mean_r = np.mean(rets_after_fees)
    std_r = np.std(rets_after_fees)
    sharpe_fee = mean_r / std_r * np.sqrt(365 * 2/7) if std_r > 0 else 0
    ann_ret_fee = mean_r * 365 * 2/7 * 100
    print(f"  {fee_bps} bps/side: mean trade ret {mean_r*100:.3f}%, ann ret {ann_ret_fee:.1f}%, Sharpe {sharpe_fee:.2f}")

