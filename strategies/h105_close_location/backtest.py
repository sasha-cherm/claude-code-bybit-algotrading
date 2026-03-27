"""
H-105: Close Location Value (CLV) Factor — Momentum Quality
============================================================
CLV = (close - low) / (high - low) per day.
Assets closing consistently near their daily high = strong buying pressure.
Cross-sectional factor: long highest avg-CLV, short lowest avg-CLV.

Validation suite:
  1. Full param scan (36 combos)
  2. 60/40 in-sample / out-of-sample split
  3. Walk-forward (6 folds x 90d test windows)
  4. Split-half OOS consistency
  5. Fee sensitivity (1x vs 5x)
  6. Correlation with H-012 (60d momentum) and H-019 (20d vol)

REJECTION criteria:
  - <60% params positive  → REJECT
  - OOS Sharpe < 0.3       → REJECT
  - Split-half corr < 0    → REJECT
  - WF mean Sharpe < 0.5   → REJECT
  - Corr(H-012) > 0.5      → REJECT
"""

import sys
import json
import warnings
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.0006           # 0.06% round-trip per leg (taker)
INITIAL_CAPITAL = 10_000.0

# Parameter grid: 4 x 3 x 3 = 36 combos
CLV_LOOKBACKS   = [5, 10, 20, 30]
REBAL_FREQS     = [3, 5, 7]
N_LONG_SHORTS   = [3, 4, 5]

WF_FOLDS = 6
WF_TEST  = 90    # days per test fold
WF_TRAIN = 300   # days of burn-in per fold

SPLIT_RATIO = 0.60  # 60/40 IS/OOS

# ─────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────

def load_daily_data():
    """Load cached 1d OHLCV parquets for all assets."""
    data_dir = ROOT / "data"
    ohlcv = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if len(df) >= 300:
                ohlcv[sym] = df
                print(f"  {sym}: {len(df)} bars "
                      f"({df.index[0].date()} → {df.index[-1].date()})")
            else:
                print(f"  {sym}: only {len(df)} bars — skipping")
        else:
            print(f"  {sym}: no cache file found — skipping")
    return ohlcv


def build_panel(ohlcv: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build aligned close, high, low DataFrames."""
    closes = pd.DataFrame({s: d["close"] for s, d in ohlcv.items()})
    highs  = pd.DataFrame({s: d["high"]  for s, d in ohlcv.items()})
    lows   = pd.DataFrame({s: d["low"]   for s, d in ohlcv.items()})
    closes.index = pd.to_datetime(closes.index, utc=True)
    highs.index  = pd.to_datetime(highs.index,  utc=True)
    lows.index   = pd.to_datetime(lows.index,   utc=True)
    # Align on common dates
    idx = closes.dropna(thresh=8).index
    closes = closes.loc[idx]
    highs  = highs.loc[idx]
    lows   = lows.loc[idx]
    return closes, highs, lows


# ─────────────────────────────────────────────────────────────
# CLV computation
# ─────────────────────────────────────────────────────────────

def compute_clv(closes: pd.DataFrame, highs: pd.DataFrame,
                lows: pd.DataFrame) -> pd.DataFrame:
    """
    Daily CLV = (close - low) / (high - low).
    When high == low (no range), CLV = 0.5.
    """
    rng = highs - lows
    clv = (closes - lows) / rng.replace(0, np.nan)
    clv = clv.fillna(0.5)
    # Clip to [0, 1] for safety
    clv = clv.clip(0.0, 1.0)
    return clv


def rolling_avg_clv(clv: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Rolling mean of CLV over `lookback` days."""
    return clv.rolling(lookback, min_periods=lookback).mean()


# ─────────────────────────────────────────────────────────────
# Strategy runner — cross-sectional portfolio
# ─────────────────────────────────────────────────────────────

def run_xs_strategy(closes: pd.DataFrame, ranking_signal: pd.DataFrame,
                    rebal_freq: int, n: int, fee_rate: float = FEE_RATE,
                    warmup: int = 35) -> dict:
    """
    Long top-n assets by ranking_signal, short bottom-n.
    Equal-weight within each leg. Market-neutral.

    Returns dict with equity, daily_returns, and performance metrics.
    """
    n_days = len(closes)
    equity = np.zeros(n_days)
    equity[0] = INITIAL_CAPITAL

    daily_rets = np.zeros(n_days)
    prev_weights = pd.Series(0.0, index=closes.columns)
    n_trades = 0
    n_rebals = 0

    for i in range(1, n_days):
        price_today = closes.iloc[i]
        price_yest  = closes.iloc[i - 1]
        log_rets    = np.log(price_today / price_yest)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            signal = ranking_signal.iloc[i - 1]
            valid  = signal.dropna()
            if len(valid) < n + n:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                daily_rets[i] = port_ret
                continue

            ranked = valid.sort_values(ascending=False)
            longs  = ranked.index[:n]
            shorts = ranked.index[-n:]

            new_w = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_w[sym] = 1.0 / n
            for sym in shorts:
                new_w[sym] -= 1.0 / n   # allow same asset on both legs to cancel

            # Fee on turnover
            turnover = (new_w - prev_weights).abs().sum() / 2.0
            fee_cost = turnover * fee_rate

            port_ret = (new_w * log_rets).sum() - fee_cost
            n_trades += int((new_w != prev_weights).sum())
            n_rebals += 1
            prev_weights = new_w
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)
        daily_rets[i] = port_ret

    eq   = pd.Series(equity, index=closes.index)
    rets = pd.Series(daily_rets, index=closes.index)

    # True daily Sharpe = mean(daily_rets)/std(daily_rets) * sqrt(365)
    active_rets = rets[warmup:]
    if active_rets.std() < 1e-10:
        sharpe = 0.0
    else:
        sharpe = float(active_rets.mean() / active_rets.std() * np.sqrt(365))

    ann_ret = annual_return(eq[warmup:], periods_per_year=365)
    mdd     = max_drawdown(eq[warmup:])

    n_pos  = (active_rets > 0).sum()
    n_tot  = len(active_rets)

    return {
        "sharpe":     round(sharpe, 4),
        "annual_ret": round(ann_ret, 4),
        "max_dd":     round(mdd, 4),
        "win_rate":   round(n_pos / n_tot, 4) if n_tot > 0 else 0,
        "n_trades":   n_trades,
        "n_rebals":   n_rebals,
        "equity":     eq,
        "daily_rets": rets,
    }


# ─────────────────────────────────────────────────────────────
# 1. Full parameter scan
# ─────────────────────────────────────────────────────────────

def run_full_scan(closes, highs, lows):
    print("\n" + "=" * 70)
    print("1. FULL PARAMETER SCAN — 36 combinations")
    print("=" * 70)

    results = []
    clv = compute_clv(closes, highs, lows)

    for lb, rf, n in product(CLV_LOOKBACKS, REBAL_FREQS, N_LONG_SHORTS):
        signal  = rolling_avg_clv(clv, lb)
        warmup  = lb + 5
        res     = run_xs_strategy(closes, signal, rf, n, warmup=warmup)
        tag     = f"LB{lb}_R{rf}_N{n}"
        results.append({
            "tag": tag, "lb": lb, "rebal": rf, "n": n,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "win_rate": res["win_rate"],
        })

    df = pd.DataFrame(results)
    pos = df[df["sharpe"] > 0]
    pct_pos = len(pos) / len(df)

    print(f"  Combos tested:    {len(df)}")
    print(f"  Positive Sharpe:  {len(pos)}/{len(df)} ({pct_pos:.0%})")
    print(f"  Mean Sharpe:      {df['sharpe'].mean():.4f}")
    print(f"  Median Sharpe:    {df['sharpe'].median():.4f}")
    print(f"  Best Sharpe:      {df['sharpe'].max():.4f}  ({df.loc[df['sharpe'].idxmax(),'tag']})")
    print(f"  Worst Sharpe:     {df['sharpe'].min():.4f}  ({df.loc[df['sharpe'].idxmin(),'tag']})")

    # Print top 5
    print("\n  Top 5 combinations:")
    top5 = df.nlargest(5, "sharpe")[["tag","sharpe","annual_ret","max_dd","win_rate"]]
    for _, row in top5.iterrows():
        print(f"    {row['tag']:<20}  Sharpe={row['sharpe']:.3f}  "
              f"Ann={row['annual_ret']:.1%}  DD={row['max_dd']:.1%}  WR={row['win_rate']:.1%}")

    return df, pct_pos


# ─────────────────────────────────────────────────────────────
# 2. IS/OOS split (60/40)
# ─────────────────────────────────────────────────────────────

def run_is_oos_split(closes, highs, lows, df_full):
    print("\n" + "=" * 70)
    print("2. IN-SAMPLE / OUT-OF-SAMPLE SPLIT (60/40)")
    print("=" * 70)

    n      = len(closes)
    split  = int(n * SPLIT_RATIO)
    is_c   = closes.iloc[:split]
    is_h   = highs.iloc[:split]
    is_l   = lows.iloc[:split]
    oos_c  = closes.iloc[split:]
    oos_h  = highs.iloc[split:]
    oos_l  = lows.iloc[split:]

    print(f"  IS  period: {is_c.index[0].date()} → {is_c.index[-1].date()} ({split} days)")
    print(f"  OOS period: {oos_c.index[0].date()} → {oos_c.index[-1].date()} ({n - split} days)")

    # Select best IS params
    best_lb, best_rf, best_n = None, None, None
    best_is_sharpe = -999
    clv_is = compute_clv(is_c, is_h, is_l)
    for lb, rf, nx in product(CLV_LOOKBACKS, REBAL_FREQS, N_LONG_SHORTS):
        signal = rolling_avg_clv(clv_is, lb)
        res    = run_xs_strategy(is_c, signal, rf, nx, warmup=lb+5)
        if res["sharpe"] > best_is_sharpe:
            best_is_sharpe = res["sharpe"]
            best_lb, best_rf, best_n = lb, rf, nx

    print(f"\n  Best IS params: LB{best_lb}_R{best_rf}_N{best_n}  (IS Sharpe={best_is_sharpe:.4f})")

    # OOS evaluation
    clv_oos  = compute_clv(oos_c, oos_h, oos_l)
    sig_oos  = rolling_avg_clv(clv_oos, best_lb)
    res_oos  = run_xs_strategy(oos_c, sig_oos, best_rf, best_n, warmup=best_lb+5)
    print(f"  OOS Sharpe:     {res_oos['sharpe']:.4f}")
    print(f"  OOS Ann Ret:    {res_oos['annual_ret']:.1%}")
    print(f"  OOS Max DD:     {res_oos['max_dd']:.1%}")

    return {
        "is_sharpe":    best_is_sharpe,
        "oos_sharpe":   res_oos["sharpe"],
        "oos_annual":   res_oos["annual_ret"],
        "oos_max_dd":   res_oos["max_dd"],
        "best_params":  (best_lb, best_rf, best_n),
        "oos_daily_rets": res_oos["daily_rets"],
    }


# ─────────────────────────────────────────────────────────────
# 3. Walk-forward (6 folds x 90d)
# ─────────────────────────────────────────────────────────────

def run_walk_forward(closes, highs, lows):
    print("\n" + "=" * 70)
    print("3. WALK-FORWARD VALIDATION (6 folds × 90d test windows)")
    print("=" * 70)

    n = len(closes)
    fold_sharpes  = []
    fold_rets     = []

    # First fold starts after WF_TRAIN days
    first_test_start = WF_TRAIN
    for fold in range(WF_FOLDS):
        test_start = first_test_start + fold * WF_TEST
        test_end   = test_start + WF_TEST
        if test_end > n:
            print(f"  Fold {fold+1}: not enough data — stopping at fold {fold}")
            break

        train_c = closes.iloc[:test_start]
        train_h = highs.iloc[:test_start]
        train_l = lows.iloc[:test_start]
        test_c  = closes.iloc[test_start:test_end]
        test_h  = highs.iloc[test_start:test_end]
        test_l  = lows.iloc[test_start:test_end]

        # Select best params on train window
        best_lb, best_rf, best_n_l = None, None, None
        best_sharpe = -999
        clv_tr = compute_clv(train_c, train_h, train_l)
        for lb, rf, nx in product(CLV_LOOKBACKS, REBAL_FREQS, N_LONG_SHORTS):
            sig = rolling_avg_clv(clv_tr, lb)
            res = run_xs_strategy(train_c, sig, rf, nx, warmup=lb+5)
            if res["sharpe"] > best_sharpe:
                best_sharpe = res["sharpe"]
                best_lb, best_rf, best_n_l = lb, rf, nx

        # Evaluate on test fold
        clv_te  = compute_clv(test_c, test_h, test_l)
        sig_te  = rolling_avg_clv(clv_te, best_lb)
        res_te  = run_xs_strategy(test_c, sig_te, best_rf, best_n_l, warmup=best_lb+5)

        d_start = test_c.index[0].date()
        d_end   = test_c.index[-1].date()
        print(f"  Fold {fold+1}: {d_start} → {d_end}  "
              f"train_best=LB{best_lb}_R{best_rf}_N{best_n_l}  "
              f"IS={best_sharpe:.3f}  OOS={res_te['sharpe']:.3f}  "
              f"Ann={res_te['annual_ret']:.1%}")
        fold_sharpes.append(res_te["sharpe"])
        fold_rets.append(res_te["annual_ret"])

    wf_mean = float(np.mean(fold_sharpes)) if fold_sharpes else -99
    wf_pos  = sum(s > 0 for s in fold_sharpes)
    print(f"\n  WF mean Sharpe: {wf_mean:.4f}")
    print(f"  WF positive folds: {wf_pos}/{len(fold_sharpes)}")
    print(f"  WF mean Ann Ret:   {float(np.mean(fold_rets)):.1%}")
    return {"wf_mean_sharpe": wf_mean, "wf_pos_folds": wf_pos,
            "n_folds": len(fold_sharpes), "fold_sharpes": fold_sharpes}


# ─────────────────────────────────────────────────────────────
# 4. Split-half OOS consistency
# ─────────────────────────────────────────────────────────────

def run_split_half_oos(closes_oos, highs_oos, lows_oos, best_params):
    print("\n" + "=" * 70)
    print("4. SPLIT-HALF OOS CONSISTENCY")
    print("=" * 70)

    lb, rf, n_l = best_params
    n   = len(closes_oos)
    mid = n // 2

    h1_c = closes_oos.iloc[:mid];  h1_h = highs_oos.iloc[:mid];  h1_l = lows_oos.iloc[:mid]
    h2_c = closes_oos.iloc[mid:];  h2_h = highs_oos.iloc[mid:];  h2_l = lows_oos.iloc[mid:]

    sharpes_h1, sharpes_h2 = [], []
    for lb_, rf_, n_ in product(CLV_LOOKBACKS, REBAL_FREQS, N_LONG_SHORTS):
        clv1 = compute_clv(h1_c, h1_h, h1_l)
        clv2 = compute_clv(h2_c, h2_h, h2_l)
        s1   = rolling_avg_clv(clv1, lb_)
        s2   = rolling_avg_clv(clv2, lb_)
        r1   = run_xs_strategy(h1_c, s1, rf_, n_, warmup=lb_+5)
        r2   = run_xs_strategy(h2_c, s2, rf_, n_, warmup=lb_+5)
        sharpes_h1.append(r1["sharpe"])
        sharpes_h2.append(r2["sharpe"])

    sh1 = np.array(sharpes_h1)
    sh2 = np.array(sharpes_h2)
    corr = float(np.corrcoef(sh1, sh2)[0, 1])

    # Also run the specific best_params on each half
    clv1 = compute_clv(h1_c, h1_h, h1_l)
    clv2 = compute_clv(h2_c, h2_h, h2_l)
    s1   = rolling_avg_clv(clv1, lb)
    s2   = rolling_avg_clv(clv2, lb)
    r1   = run_xs_strategy(h1_c, s1, rf, n_l, warmup=lb+5)
    r2   = run_xs_strategy(h2_c, s2, rf, n_l, warmup=lb+5)

    print(f"  OOS H1 ({h1_c.index[0].date()} → {h1_c.index[-1].date()}):")
    print(f"    Best-params Sharpe={r1['sharpe']:.4f}  Ann={r1['annual_ret']:.1%}")
    print(f"  OOS H2 ({h2_c.index[0].date()} → {h2_c.index[-1].date()}):")
    print(f"    Best-params Sharpe={r2['sharpe']:.4f}  Ann={r2['annual_ret']:.1%}")
    print(f"  Split-half cross-param correlation: {corr:.4f}")
    print(f"  H1 mean Sharpe: {sh1.mean():.4f}  H2 mean Sharpe: {sh2.mean():.4f}")
    return {"corr": corr, "h1_sharpe": r1["sharpe"], "h2_sharpe": r2["sharpe"],
            "h1_mean": float(sh1.mean()), "h2_mean": float(sh2.mean())}


# ─────────────────────────────────────────────────────────────
# 5. Fee sensitivity
# ─────────────────────────────────────────────────────────────

def run_fee_sensitivity(closes, highs, lows, best_params):
    print("\n" + "=" * 70)
    print("5. FEE SENSITIVITY (1x vs 5x fees)")
    print("=" * 70)

    lb, rf, n_l = best_params
    clv     = compute_clv(closes, highs, lows)
    signal  = rolling_avg_clv(clv, lb)
    warmup  = lb + 5

    for mult, label in [(1, "1x (baseline, 0.06%)"), (5, "5x (stressed, 0.30%)")]:
        fee = FEE_RATE * mult
        res = run_xs_strategy(closes, signal, rf, n_l, fee_rate=fee, warmup=warmup)
        print(f"  {label:<28}  Sharpe={res['sharpe']:.4f}  "
              f"Ann={res['annual_ret']:.1%}  DD={res['max_dd']:.1%}")

    res1  = run_xs_strategy(closes, signal, rf, n_l, fee_rate=FEE_RATE,   warmup=warmup)
    res5  = run_xs_strategy(closes, signal, rf, n_l, fee_rate=FEE_RATE*5, warmup=warmup)
    return {"sharpe_1x": res1["sharpe"], "sharpe_5x": res5["sharpe"]}


# ─────────────────────────────────────────────────────────────
# 6. Correlation with H-012 (momentum) and H-019 (vol)
# ─────────────────────────────────────────────────────────────

def compute_h012_factor_returns(closes: pd.DataFrame,
                                lookback: int = 60, rebal: int = 5, n: int = 4):
    """
    Replicate H-012: cross-sectional momentum (60d return, top/bottom 4, rebal every 5d).
    Returns daily factor return series.
    """
    mom = closes.pct_change(lookback)  # 60d return
    n_days = len(closes)
    daily_rets = np.zeros(n_days)
    prev_w = pd.Series(0.0, index=closes.columns)
    warmup = lookback + 5

    for i in range(1, n_days):
        p_t = closes.iloc[i]
        p_y = closes.iloc[i - 1]
        lr  = np.log(p_t / p_y)

        if i >= warmup and (i - warmup) % rebal == 0:
            sig   = mom.iloc[i - 1]
            valid = sig.dropna()
            if len(valid) < 2 * n:
                daily_rets[i] = (prev_w * lr).sum()
                continue
            ranked = valid.sort_values(ascending=False)
            longs  = ranked.index[:n]
            shorts = ranked.index[-n:]
            new_w  = pd.Series(0.0, index=closes.columns)
            for s in longs:  new_w[s]  =  1.0 / n
            for s in shorts: new_w[s]  = -1.0 / n
            daily_rets[i] = (new_w * lr).sum()
            prev_w = new_w
        else:
            daily_rets[i] = (prev_w * lr).sum()

    return pd.Series(daily_rets, index=closes.index)


def compute_h019_factor_returns(closes: pd.DataFrame,
                                lookback: int = 20, rebal: int = 5, n: int = 4):
    """
    Replicate H-019: cross-sectional volatility factor (20d realized vol).
    Long low-vol, short high-vol (typical low-vol anomaly).
    Returns daily factor return series.
    """
    rets_df = closes.pct_change()
    vol_df  = rets_df.rolling(lookback).std()  # 20d realized vol
    n_days  = len(closes)
    daily_rets = np.zeros(n_days)
    prev_w  = pd.Series(0.0, index=closes.columns)
    warmup  = lookback + 5

    for i in range(1, n_days):
        p_t = closes.iloc[i]
        p_y = closes.iloc[i - 1]
        lr  = np.log(p_t / p_y)

        if i >= warmup and (i - warmup) % rebal == 0:
            sig   = -vol_df.iloc[i - 1]  # negate: low vol = high rank = long
            valid = sig.dropna()
            if len(valid) < 2 * n:
                daily_rets[i] = (prev_w * lr).sum()
                continue
            ranked = valid.sort_values(ascending=False)
            longs  = ranked.index[:n]
            shorts = ranked.index[-n:]
            new_w  = pd.Series(0.0, index=closes.columns)
            for s in longs:  new_w[s]  =  1.0 / n
            for s in shorts: new_w[s]  = -1.0 / n
            daily_rets[i] = (new_w * lr).sum()
            prev_w = new_w
        else:
            daily_rets[i] = (prev_w * lr).sum()

    return pd.Series(daily_rets, index=closes.index)


def run_factor_correlations(closes, highs, lows, best_params):
    print("\n" + "=" * 70)
    print("6. FACTOR CORRELATIONS (vs H-012 momentum, H-019 vol)")
    print("=" * 70)

    lb, rf, n_l = best_params
    clv        = compute_clv(closes, highs, lows)
    signal     = rolling_avg_clv(clv, lb)
    warmup     = lb + 5
    res_h105   = run_xs_strategy(closes, signal, rf, n_l, warmup=warmup)
    h105_rets  = res_h105["daily_rets"]

    h012_rets  = compute_h012_factor_returns(closes)
    h019_rets  = compute_h019_factor_returns(closes)

    # Align on common non-zero index (active trading days)
    common     = h105_rets.index
    # Use rolling warmup trim
    trim_start = warmup + 5
    r105  = h105_rets.iloc[trim_start:]
    r012  = h012_rets.iloc[trim_start:]
    r019  = h019_rets.iloc[trim_start:]

    # Only compare where all are non-zero (active)
    active = (r105 != 0) | (r012 != 0) | (r019 != 0)
    r105  = r105[active]
    r012  = r012[active]
    r019  = r019[active]

    corr_012 = float(r105.corr(r012))
    corr_019 = float(r105.corr(r019))
    corr_cross = float(r012.corr(r019))

    print(f"  H-105 vs H-012 (60d momentum):    {corr_012:.4f}")
    print(f"  H-105 vs H-019 (20d vol):         {corr_019:.4f}")
    print(f"  H-012 vs H-019 (cross-check):     {corr_cross:.4f}")
    print(f"  (Using daily factor returns, {len(r105)} active days)")

    return {"corr_h012": corr_012, "corr_h019": corr_019, "corr_cross": corr_cross}


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("H-105: Close Location Value (CLV) Momentum Quality Factor")
    print("=" * 70)

    # Load data
    print("\nLoading data...")
    ohlcv = load_daily_data()
    if len(ohlcv) < 8:
        print(f"ERROR: Only {len(ohlcv)} assets loaded — need at least 8.")
        return

    closes, highs, lows = build_panel(ohlcv)
    print(f"\nPanel: {len(closes.columns)} assets, {len(closes)} days")
    print(f"  {closes.index[0].date()} → {closes.index[-1].date()}")

    # ── 1. Full param scan
    df_scan, pct_pos = run_full_scan(closes, highs, lows)

    # ── 2. IS/OOS split
    is_oos = run_is_oos_split(closes, highs, lows, df_scan)
    best_params = is_oos["best_params"]

    # ── 3. Walk-forward
    wf = run_walk_forward(closes, highs, lows)

    # ── 4. Split-half OOS
    n      = len(closes)
    split  = int(n * SPLIT_RATIO)
    oos_c  = closes.iloc[split:]
    oos_h  = highs.iloc[split:]
    oos_l  = lows.iloc[split:]
    sh     = run_split_half_oos(oos_c, oos_h, oos_l, best_params)

    # ── 5. Fee sensitivity
    fee_sens = run_fee_sensitivity(closes, highs, lows, best_params)

    # ── 6. Factor correlations
    corr = run_factor_correlations(closes, highs, lows, best_params)

    # ─────────────────────────────────────────────────────────
    # VERDICT
    # ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY & VERDICT")
    print("=" * 70)

    # Evaluate each rejection criterion
    reasons = []
    flags   = {}

    # 1. Robustness
    flags["pct_pos_params"] = pct_pos
    if pct_pos < 0.60:
        reasons.append(f"Only {pct_pos:.0%} params positive (< 60% threshold)")

    # 2. OOS Sharpe
    flags["oos_sharpe"] = is_oos["oos_sharpe"]
    if is_oos["oos_sharpe"] < 0.3:
        reasons.append(f"OOS Sharpe {is_oos['oos_sharpe']:.4f} < 0.3 threshold")

    # 3. Split-half correlation
    flags["split_half_corr"] = sh["corr"]
    if sh["corr"] < 0:
        reasons.append(f"Split-half corr {sh['corr']:.4f} < 0 (regime-dependent)")

    # 4. Walk-forward mean Sharpe
    flags["wf_mean_sharpe"] = wf["wf_mean_sharpe"]
    if wf["wf_mean_sharpe"] < 0.5:
        reasons.append(f"WF mean Sharpe {wf['wf_mean_sharpe']:.4f} < 0.5 threshold")

    # 5. H-012 correlation
    flags["corr_h012"] = corr["corr_h012"]
    if corr["corr_h012"] > 0.5:
        reasons.append(f"Correlation with H-012 = {corr['corr_h012']:.4f} > 0.5 (redundant)")

    verdict = "REJECTED" if reasons else "CONFIRMED"

    print(f"\n  Parameter robustness:          {pct_pos:.0%} positive ({len(df_scan[df_scan['sharpe']>0])}/{len(df_scan)})")
    print(f"  IS Sharpe (best params):        {is_oos['is_sharpe']:.4f}")
    print(f"  OOS Sharpe (60/40 split):       {is_oos['oos_sharpe']:.4f}")
    print(f"  OOS Annual Return:              {is_oos['oos_annual']:.1%}")
    print(f"  OOS Max Drawdown:               {is_oos['oos_max_dd']:.1%}")
    print(f"  Walk-forward mean Sharpe:       {wf['wf_mean_sharpe']:.4f}  ({wf['wf_pos_folds']}/{wf['n_folds']} folds positive)")
    print(f"  Walk-forward fold Sharpes:      {[round(s,3) for s in wf['fold_sharpes']]}")
    print(f"  Split-half OOS corr:            {sh['corr']:.4f}")
    print(f"  Split-half H1/H2 Sharpes:       {sh['h1_sharpe']:.4f} / {sh['h2_sharpe']:.4f}")
    print(f"  Sharpe at 1x fees (0.06%):      {fee_sens['sharpe_1x']:.4f}")
    print(f"  Sharpe at 5x fees (0.30%):      {fee_sens['sharpe_5x']:.4f}")
    print(f"  Corr with H-012 (60d mom):      {corr['corr_h012']:.4f}")
    print(f"  Corr with H-019 (20d vol):      {corr['corr_h019']:.4f}")
    print(f"  Best params: LB{best_params[0]} / R{best_params[1]} / N{best_params[2]}")

    print(f"\n  >>> VERDICT: {verdict} <<<")
    if reasons:
        print(f"\n  Rejection reasons:")
        for r in reasons:
            print(f"    - {r}")
    else:
        print("  All criteria passed.")

    # Save results
    results_dir = Path(__file__).parent
    results = {
        "hypothesis": "H-105",
        "title": "Close Location Value (CLV) Momentum Quality Factor",
        "verdict": verdict,
        "rejection_reasons": reasons,
        "metrics": {
            "pct_positive_params": round(pct_pos, 4),
            "n_positive_params": int(len(df_scan[df_scan["sharpe"] > 0])),
            "n_total_params": int(len(df_scan)),
            "best_params": {
                "clv_lookback": best_params[0],
                "rebal_freq": best_params[1],
                "n_long_short": best_params[2],
            },
            "full_scan_mean_sharpe":   round(float(df_scan["sharpe"].mean()), 4),
            "full_scan_median_sharpe": round(float(df_scan["sharpe"].median()), 4),
            "is_sharpe":               round(float(is_oos["is_sharpe"]), 4),
            "oos_sharpe":              round(float(is_oos["oos_sharpe"]), 4),
            "oos_annual_ret":          round(float(is_oos["oos_annual"]), 4),
            "oos_max_dd":              round(float(is_oos["oos_max_dd"]), 4),
            "wf_mean_sharpe":          round(float(wf["wf_mean_sharpe"]), 4),
            "wf_pos_folds":            int(wf["wf_pos_folds"]),
            "wf_n_folds":              int(wf["n_folds"]),
            "wf_fold_sharpes":         [round(s, 4) for s in wf["fold_sharpes"]],
            "split_half_corr":         round(float(sh["corr"]), 4),
            "split_half_h1_sharpe":    round(float(sh["h1_sharpe"]), 4),
            "split_half_h2_sharpe":    round(float(sh["h2_sharpe"]), 4),
            "sharpe_1x_fees":          round(float(fee_sens["sharpe_1x"]), 4),
            "sharpe_5x_fees":          round(float(fee_sens["sharpe_5x"]), 4),
            "corr_h012_momentum":      round(float(corr["corr_h012"]), 4),
            "corr_h019_vol":           round(float(corr["corr_h019"]), 4),
        },
    }
    out_path = results_dir / "results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {out_path}")


if __name__ == "__main__":
    main()
