"""
H-104: RSI Cross-Sectional Mean Reversion Factor

Rank 14 crypto assets by their 14-day RSI.
Go long the most oversold (lowest RSI) and short the most overbought (highest RSI).
Cross-sectional mean reversion.

Validation:
- Full parameter scan (36 combinations)
- 60/40 train/test split
- Walk-forward (6 folds, 90-day test windows)
- Split-half consistency
- Fee impact at 1x and 5x
- Correlation with H-012 (momentum) and H-019 (low-vol)
"""

import sys
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT",
    "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "ADA/USDT", "DOT/USDT",
    "NEAR/USDT", "OP/USDT", "ARB/USDT", "ATOM/USDT",
]

FEE_RATE = 0.0006          # 0.06% round-trip taker
FEE_RATE_5X = FEE_RATE * 5
INITIAL_CAPITAL = 10_000.0

# Parameter grid  (36 total)
RSI_LOOKBACKS = [7, 14, 21]
REBAL_FREQS   = [3, 5, 7, 10]
N_LONGS       = [3, 4, 5]

# Walk-forward settings
WF_FOLDS = 6
WF_TRAIN  = 300  # days
WF_TEST   = 90
WF_STEP   = 90


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_daily_data():
    data_dir = ROOT / "data"
    daily = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if len(df) >= 200:
                daily[sym] = df
                print(f"  {sym}: {len(df)} daily bars "
                      f"({df.index[0].date()} to {df.index[-1].date()})")
            else:
                print(f"  {sym}: only {len(df)} bars, skipping")
        else:
            print(f"  {sym}: no cached data — fetching live...")
            try:
                import ccxt, time
                exchange = ccxt.bybit({"enableRateLimit": True})
                exchange.load_markets()
                since_ms = exchange.parse8601("2023-01-01T00:00:00Z")
                all_candles = []
                cur = since_ms
                while True:
                    candles = exchange.fetch_ohlcv(sym.replace("/USDT", "/USDT:USDT"),
                                                    "1d", since=cur, limit=500)
                    if not candles:
                        break
                    all_candles.extend(candles)
                    if len(candles) < 100:
                        break
                    cur = candles[-1][0] + 86_400_000
                    time.sleep(0.2)
                if all_candles:
                    df = pd.DataFrame(all_candles,
                                      columns=["timestamp","open","high","low","close","volume"])
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
                    df = df.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")
                    df.to_parquet(path)
                    daily[sym] = df
                    print(f"    Fetched {len(df)} bars")
            except Exception as e:
                print(f"    Fetch failed: {e}")
    return daily


def build_close_matrix(daily: dict) -> pd.DataFrame:
    closes = {sym: df["close"] for sym, df in daily.items()}
    df = pd.DataFrame(closes)
    df = df.sort_index()
    df = df.dropna(how="all")
    return df


# ---------------------------------------------------------------------------
# RSI computation
# ---------------------------------------------------------------------------

def compute_rsi(series: pd.Series, period: int) -> pd.Series:
    """Standard Wilder RSI (EMA-based)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    # Wilder smoothing = EMA with alpha = 1/period
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    return rsi


def compute_rsi_matrix(closes: pd.DataFrame, period: int) -> pd.DataFrame:
    """Compute RSI for each asset column."""
    return closes.apply(lambda col: compute_rsi(col, period), axis=0)


# ---------------------------------------------------------------------------
# Backtest engine
# ---------------------------------------------------------------------------

def run_xs_factor(closes: pd.DataFrame, ranking: pd.DataFrame,
                  rebal_freq: int, n_long: int, n_short: int = None,
                  fee_rate: float = FEE_RATE, warmup: int = 30) -> dict:
    """
    Run cross-sectional long/short strategy.
    ranking: higher rank = stronger LONG signal (mean reversion → INVERT RSI).
    We negate RSI outside so that lowest RSI = highest ranking value.
    """
    if n_short is None:
        n_short = n_long

    n = len(closes)
    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

    prev_weights = pd.Series(0.0, index=closes.columns)
    total_trades = 0
    rebal_count = 0
    daily_rets = []

    for i in range(1, n):
        price_today     = closes.iloc[i]
        price_yesterday = closes.iloc[i - 1]
        log_rets = np.log(price_today / price_yesterday)

        if i >= warmup and (i - warmup) % rebal_freq == 0:
            # Use ranking from previous bar (no lookahead)
            ranks = ranking.iloc[i - 1]
            valid = ranks.dropna()
            if len(valid) < n_long + n_short:
                port_ret = (prev_weights * log_rets).sum()
                equity[i] = equity[i - 1] * np.exp(port_ret)
                daily_rets.append(port_ret)
                continue

            # Sort ascending: most oversold (lowest RSI) → highest rank
            ranked = valid.sort_values(ascending=True)  # low RSI first
            longs  = ranked.index[:n_long]              # most oversold
            shorts = ranked.index[-n_short:]            # most overbought

            new_weights = pd.Series(0.0, index=closes.columns)
            for sym in longs:
                new_weights[sym] = +1.0 / n_long
            for sym in shorts:
                new_weights[sym] = -1.0 / n_short

            weight_changes = (new_weights - prev_weights).abs()
            turnover   = weight_changes.sum() / 2.0
            fee_drag   = turnover * fee_rate

            port_ret = (new_weights * log_rets).sum() - fee_drag
            total_trades += int((weight_changes > 1e-6).sum())
            rebal_count  += 1
            prev_weights  = new_weights
        else:
            port_ret = (prev_weights * log_rets).sum()

        equity[i] = equity[i - 1] * np.exp(port_ret)
        daily_rets.append(port_ret)

    eq_series = pd.Series(equity, index=closes.index)
    metrics = compute_metrics(eq_series)
    metrics["n_trades"]     = total_trades
    metrics["n_rebalances"] = rebal_count
    metrics["equity"]       = eq_series
    return metrics


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(equity_series: pd.Series) -> dict:
    eq = equity_series[equity_series > 0]
    if len(eq) < 30:
        return {"sharpe": -99, "annual_ret": 0, "max_dd": 1.0, "win_rate": 0}
    rets = eq.pct_change().dropna()
    n_pos = (rets > 0).sum()
    return {
        "sharpe":     round(sharpe_ratio(rets, periods_per_year=365), 4),
        "annual_ret": round(annual_return(eq, periods_per_year=365), 4),
        "max_dd":     round(max_drawdown(eq), 4),
        "win_rate":   round(n_pos / len(rets), 4) if len(rets) > 0 else 0,
    }


# ---------------------------------------------------------------------------
# Full parameter scan
# ---------------------------------------------------------------------------

def run_full_scan(closes: pd.DataFrame, label: str = "FULL") -> pd.DataFrame:
    results = []
    total = len(RSI_LOOKBACKS) * len(REBAL_FREQS) * len(N_LONGS)
    done = 0
    for lb, rebal, n_long in product(RSI_LOOKBACKS, REBAL_FREQS, N_LONGS):
        rsi = compute_rsi_matrix(closes, lb)
        warmup = lb + 5
        res = run_xs_factor(closes, rsi, rebal, n_long, warmup=warmup)
        tag = f"RSI{lb}_R{rebal}_N{n_long}"
        results.append({
            "tag": tag, "rsi_lb": lb, "rebal": rebal, "n_long": n_long,
            "sharpe": res["sharpe"], "annual_ret": res["annual_ret"],
            "max_dd": res["max_dd"], "win_rate": res["win_rate"],
        })
        done += 1
        if done % 12 == 0:
            print(f"    [{label}] {done}/{total} done...")
    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Train/Test split
# ---------------------------------------------------------------------------

def run_train_test_split(closes: pd.DataFrame, split_ratio: float = 0.60):
    n = len(closes)
    split_idx = int(n * split_ratio)
    train_c = closes.iloc[:split_idx]
    test_c  = closes.iloc[split_idx:]

    print(f"\n  60/40 Train/Test split")
    print(f"    Train: {train_c.index[0].date()} to {train_c.index[-1].date()} ({len(train_c)} days)")
    print(f"    Test:  {test_c.index[0].date()} to {test_c.index[-1].date()} ({len(test_c)} days)")

    # --- IS scan ---
    best_is  = -999
    best_params = None
    is_sharpes = []
    for lb, rebal, n_long in product(RSI_LOOKBACKS, REBAL_FREQS, N_LONGS):
        rsi = compute_rsi_matrix(train_c, lb)
        res = run_xs_factor(train_c, rsi, rebal, n_long, warmup=lb + 5)
        is_sharpes.append(res["sharpe"])
        if res["sharpe"] > best_is:
            best_is = res["sharpe"]
            best_params = (lb, rebal, n_long)

    lb, rb, nl = best_params
    print(f"    IS best params: RSI{lb}_R{rb}_N{nl}  Sharpe={best_is:.4f}")
    print(f"    IS mean Sharpe: {np.mean(is_sharpes):.4f}")

    # --- OOS evaluation ---
    oos_sharpes = []
    for lb2, rebal2, n_long2 in product(RSI_LOOKBACKS, REBAL_FREQS, N_LONGS):
        rsi2 = compute_rsi_matrix(test_c, lb2)
        res2 = run_xs_factor(test_c, rsi2, rebal2, n_long2, warmup=lb2 + 5)
        oos_sharpes.append(res2["sharpe"])
    print(f"    OOS mean Sharpe (all params): {np.mean(oos_sharpes):.4f}")

    # OOS with IS-selected params
    rsi_oos = compute_rsi_matrix(test_c, lb)
    res_oos  = run_xs_factor(test_c, rsi_oos, rb, nl, warmup=lb + 5)
    print(f"    OOS (IS-selected params): Sharpe={res_oos['sharpe']:.4f}  "
          f"Ann={res_oos['annual_ret']:.1%}  MaxDD={res_oos['max_dd']:.1%}")

    return {
        "best_is_sharpe":  best_is,
        "mean_is_sharpe":  round(float(np.mean(is_sharpes)), 4),
        "best_oos_sharpe": res_oos["sharpe"],
        "mean_oos_sharpe": round(float(np.mean(oos_sharpes)), 4),
        "best_params":     best_params,
        "oos_annual_ret":  res_oos["annual_ret"],
        "oos_max_dd":      res_oos["max_dd"],
        "oos_equity":      res_oos["equity"],
    }


# ---------------------------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------------------------

def run_walk_forward(closes: pd.DataFrame):
    print(f"\n  Walk-Forward ({WF_FOLDS} folds, {WF_TRAIN}d train / {WF_TEST}d test)")
    n = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        test_end   = n - fold * WF_STEP
        test_start = test_end - WF_TEST
        train_end  = test_start
        train_start = train_end - WF_TRAIN
        if train_start < 0:
            print(f"    Fold {fold+1}: not enough data, skipping")
            break

        train_c = closes.iloc[train_start:train_end]
        test_c  = closes.iloc[test_start:test_end]
        if len(test_c) < 20 or len(train_c) < 50:
            break

        # Select best params on train
        best_is  = -999
        best_params = None
        for lb, rebal, n_long in product(RSI_LOOKBACKS, REBAL_FREQS, N_LONGS):
            warmup = min(lb + 5, len(train_c) // 3)
            if warmup >= len(train_c) - 10:
                continue
            rsi = compute_rsi_matrix(train_c, lb)
            res = run_xs_factor(train_c, rsi, rebal, n_long, warmup=warmup)
            if res["sharpe"] > best_is:
                best_is = res["sharpe"]
                best_params = (lb, rebal, n_long)

        if best_params is None:
            break

        lb, rb, nl = best_params
        rsi_test = compute_rsi_matrix(test_c, lb)
        warmup_t = min(lb + 5, len(test_c) // 3)
        res_t = run_xs_factor(test_c, rsi_test, rb, nl, warmup=warmup_t)

        fold_results.append({
            "fold": fold + 1,
            "params": f"RSI{lb}_R{rb}_N{nl}",
            "train_sharpe": round(best_is, 4),
            "oos_sharpe":   res_t["sharpe"],
            "oos_annual":   res_t["annual_ret"],
            "period":       f"{closes.index[test_start].date()}..{closes.index[test_end-1].date()}",
        })
        print(f"    Fold {fold+1}: {closes.index[test_start].date()}–{closes.index[test_end-1].date()}  "
              f"params={f'RSI{lb}_R{rb}_N{nl}':20s}  "
              f"IS={best_is:+.3f}  OOS={res_t['sharpe']:+.3f}")

    if not fold_results:
        return None
    df_wf = pd.DataFrame(fold_results)
    pos = (df_wf["oos_sharpe"] > 0).sum()
    wf_mean = df_wf["oos_sharpe"].mean()
    print(f"    WF summary: {pos}/{len(df_wf)} positive, mean OOS Sharpe={wf_mean:.4f}")
    return df_wf


# ---------------------------------------------------------------------------
# Split-half
# ---------------------------------------------------------------------------

def run_split_half(closes: pd.DataFrame):
    n = len(closes)
    mid = n // 2
    h1 = closes.iloc[:mid]
    h2 = closes.iloc[mid:]
    print(f"\n  Split-Half Consistency")
    print(f"    H1: {h1.index[0].date()} to {h1.index[-1].date()} ({len(h1)} days)")
    print(f"    H2: {h2.index[0].date()} to {h2.index[-1].date()} ({len(h2)} days)")

    h1_sharpes, h2_sharpes = [], []
    for lb, rebal, n_long in product(RSI_LOOKBACKS, REBAL_FREQS, N_LONGS):
        warmup = lb + 5
        rsi1 = compute_rsi_matrix(h1, lb)
        rsi2 = compute_rsi_matrix(h2, lb)
        r1 = run_xs_factor(h1, rsi1, rebal, n_long, warmup=warmup)
        r2 = run_xs_factor(h2, rsi2, rebal, n_long, warmup=warmup)
        h1_sharpes.append(r1["sharpe"])
        h2_sharpes.append(r2["sharpe"])

    h1_arr = np.array(h1_sharpes)
    h2_arr = np.array(h2_sharpes)
    corr = float(np.corrcoef(h1_arr, h2_arr)[0, 1])
    print(f"    H1 mean Sharpe: {h1_arr.mean():.4f}  (pos: {(h1_arr>0).sum()}/36)")
    print(f"    H2 mean Sharpe: {h2_arr.mean():.4f}  (pos: {(h2_arr>0).sum()}/36)")
    print(f"    Split-half correlation: {corr:.4f}")
    return {
        "h1_mean":  round(float(h1_arr.mean()), 4),
        "h2_mean":  round(float(h2_arr.mean()), 4),
        "corr":     round(corr, 4),
    }


# ---------------------------------------------------------------------------
# Fee sensitivity
# ---------------------------------------------------------------------------

def run_fee_sensitivity(closes: pd.DataFrame, best_params: tuple):
    lb, rb, nl = best_params
    print(f"\n  Fee Sensitivity (params: RSI{lb}_R{rb}_N{nl})")
    warmup = lb + 5
    rsi = compute_rsi_matrix(closes, lb)

    for fee_mult, label in [(1, "1x"), (5, "5x")]:
        fee = FEE_RATE * fee_mult
        res = run_xs_factor(closes, rsi, rb, nl, fee_rate=fee, warmup=warmup)
        print(f"    {label} fees ({fee*100:.3f}%): Sharpe={res['sharpe']:.4f}  "
              f"Ann={res['annual_ret']:.1%}  MaxDD={res['max_dd']:.1%}")

    rsi_1x = compute_rsi_matrix(closes, lb)
    r1x = run_xs_factor(closes, rsi_1x, rb, nl, fee_rate=FEE_RATE,       warmup=warmup)
    r5x = run_xs_factor(closes, rsi_1x, rb, nl, fee_rate=FEE_RATE_5X,    warmup=warmup)
    return {"sharpe_1x": r1x["sharpe"], "sharpe_5x": r5x["sharpe"]}


# ---------------------------------------------------------------------------
# Factor correlation
# ---------------------------------------------------------------------------

def run_factor_correlations(closes: pd.DataFrame, best_params: tuple):
    """Compute correlation with H-012 (momentum) and H-019 (low-vol)."""
    lb, rb, nl = best_params
    print(f"\n  Factor Correlations")
    warmup = lb + 5

    # This strategy (H-104 RSI mean reversion)
    rsi = compute_rsi_matrix(closes, lb)
    res_h104 = run_xs_factor(closes, rsi, rb, nl, warmup=warmup)

    # H-012: 60d cross-sectional momentum — long top N, short bottom N
    mom60 = closes.pct_change(60)
    res_mom = run_xs_factor(closes, -mom60, 5, 4, warmup=65)
    # NOTE: we negate mom60 to keep convention consistent: sort_values ascending,
    # so highest negative = smallest original = lowest momentum (we want long high mom)
    # Actually let's do it correctly: for momentum we want to LONG high momentum,
    # so in run_xs_factor (which longs lowest values), we negate so lowest = highest original
    # Let's verify with direct implementation:
    mom60_direct = closes.pct_change(60)
    # For momentum: long top 4 (highest mom60), short bottom 4
    # run_xs_factor longs LOWEST ranked — so to long HIGH momentum, pass -mom60
    res_mom = run_xs_factor(closes, -mom60_direct, 5, 4, warmup=65)

    # H-019: low-vol — long low-volatility assets
    vol20 = closes.pct_change().rolling(20, min_periods=20).std()
    # Long low vol = long lowest vol = pass vol20 directly (ascending sort longs smallest)
    res_lowvol = run_xs_factor(closes, vol20, 5, 4, warmup=25)

    # Compute equity daily returns
    rets_h104  = res_h104["equity"].pct_change().dropna()
    rets_mom   = res_mom["equity"].pct_change().dropna()
    rets_lowvol = res_lowvol["equity"].pct_change().dropna()

    idx_mom    = rets_h104.index.intersection(rets_mom.index)
    idx_lowvol = rets_h104.index.intersection(rets_lowvol.index)

    corr_mom    = float(rets_h104.loc[idx_mom].corr(rets_mom.loc[idx_mom]))       if len(idx_mom)    > 50 else np.nan
    corr_lowvol = float(rets_h104.loc[idx_lowvol].corr(rets_lowvol.loc[idx_lowvol])) if len(idx_lowvol) > 50 else np.nan

    print(f"    Correlation with H-012 (momentum):  {corr_mom:.4f}")
    print(f"    Correlation with H-019 (low-vol):   {corr_lowvol:.4f}")
    return {"corr_h012": round(corr_mom, 4), "corr_h019": round(corr_lowvol, 4)}


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 72)
    print("H-104: RSI CROSS-SECTIONAL MEAN REVERSION FACTOR — Backtest")
    print("=" * 72)

    # 1. Load data
    print("\n[1] Loading daily data...")
    daily = load_daily_data()
    closes = build_close_matrix(daily)
    # Align: use only common dates (drop rows where any asset is NaN)
    closes = closes.dropna()
    print(f"\n  Aligned matrix: {len(closes)} days  x  {len(closes.columns)} assets")
    print(f"  Period: {closes.index[0].date()} to {closes.index[-1].date()}")

    # 2. Full parameter scan
    print("\n[2] Full parameter scan (36 combinations)...")
    df_scan = run_full_scan(closes, label="FULL")
    pos_count = (df_scan["sharpe"] > 0).sum()
    pct_pos   = pos_count / len(df_scan) * 100
    print(f"\n  Param robustness: {pos_count}/36 positive ({pct_pos:.0f}%)")
    print(f"  Mean Sharpe: {df_scan['sharpe'].mean():.4f}  "
          f"Median: {df_scan['sharpe'].median():.4f}")
    print(f"  Best Sharpe: {df_scan['sharpe'].max():.4f}  "
          f"(params: {df_scan.loc[df_scan['sharpe'].idxmax(),'tag']})")
    print(f"  Worst Sharpe: {df_scan['sharpe'].min():.4f}")
    print(f"\n  Top 5 parameter sets:")
    top5 = df_scan.nlargest(5, "sharpe")
    for _, row in top5.iterrows():
        print(f"    {row['tag']:30s}  Sharpe={row['sharpe']:+.4f}  "
              f"Ann={row['annual_ret']:.1%}  MaxDD={row['max_dd']:.1%}")

    # 3. 60/40 train/test split
    print("\n[3] Train/Test split (60/40)...")
    tt = run_train_test_split(closes, split_ratio=0.60)

    # 4. Walk-forward
    print("\n[4] Walk-forward validation...")
    df_wf = run_walk_forward(closes)
    wf_mean_sharpe = df_wf["oos_sharpe"].mean() if df_wf is not None else np.nan

    # 5. Split-half
    print("\n[5] Split-half consistency...")
    sh = run_split_half(closes)

    # 6. Fee sensitivity (use best IS params)
    best_params = tt["best_params"]
    print("\n[6] Fee sensitivity...")
    fees = run_fee_sensitivity(closes, best_params)

    # 7. Factor correlations
    print("\n[7] Factor correlations...")
    corrs = run_factor_correlations(closes, best_params)

    # ---------------------------------------------------------------------------
    # SUMMARY + VERDICT
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("H-104: RSI CROSS-SECTIONAL MEAN REVERSION — FINAL SUMMARY")
    print("=" * 72)
    print(f"\n  UNIVERSE:  {len(closes.columns)} assets  |  PERIOD: "
          f"{closes.index[0].date()} to {closes.index[-1].date()}  "
          f"({len(closes)} days)")
    print(f"\n  --- PARAMETER ROBUSTNESS ---")
    print(f"  {pos_count}/36 combos positive ({pct_pos:.0f}%)")
    print(f"  Mean IS Sharpe (full period):  {df_scan['sharpe'].mean():.4f}")
    print(f"  Best IS Sharpe (full period):  {df_scan['sharpe'].max():.4f}  "
          f"({df_scan.loc[df_scan['sharpe'].idxmax(),'tag']})")

    print(f"\n  --- TRAIN/TEST (60/40) ---")
    print(f"  Best IS Sharpe:  {tt['best_is_sharpe']:.4f}")
    print(f"  Mean IS Sharpe:  {tt['mean_is_sharpe']:.4f}")
    print(f"  Best OOS Sharpe: {tt['best_oos_sharpe']:.4f}")
    print(f"  Mean OOS Sharpe: {tt['mean_oos_sharpe']:.4f}")
    print(f"  OOS Ann Ret:     {tt['oos_annual_ret']:.1%}")
    print(f"  OOS Max DD:      {tt['oos_max_dd']:.1%}")

    print(f"\n  --- WALK-FORWARD ---")
    if df_wf is not None:
        for _, row in df_wf.iterrows():
            print(f"  Fold {row['fold']:1d} ({row['period']}): "
                  f"params={row['params']:20s}  IS={row['train_sharpe']:+.3f}  OOS={row['oos_sharpe']:+.3f}")
        print(f"  WF Mean OOS Sharpe: {wf_mean_sharpe:.4f}")
    else:
        print("  Walk-forward failed (insufficient data)")

    print(f"\n  --- SPLIT-HALF ---")
    print(f"  H1 mean Sharpe: {sh['h1_mean']:.4f}")
    print(f"  H2 mean Sharpe: {sh['h2_mean']:.4f}")
    print(f"  Split-half correlation: {sh['corr']:.4f}")

    print(f"\n  --- FEE SENSITIVITY ---")
    print(f"  Sharpe at 1x fees (0.06%): {fees['sharpe_1x']:.4f}")
    print(f"  Sharpe at 5x fees (0.30%): {fees['sharpe_5x']:.4f}")

    print(f"\n  --- FACTOR CORRELATIONS ---")
    print(f"  Corr with H-012 (momentum): {corrs['corr_h012']:.4f}")
    print(f"  Corr with H-019 (low-vol):  {corrs['corr_h019']:.4f}")

    # ---------------------------------------------------------------------------
    # Rejection criteria
    # ---------------------------------------------------------------------------
    print(f"\n  --- REJECTION CRITERIA CHECK ---")
    reject_reasons = []

    r1 = pct_pos < 60
    print(f"  [{'FAIL' if r1 else 'PASS'}] <60% positive params: {pct_pos:.0f}% positive  (threshold: ≥60%)")
    if r1:
        reject_reasons.append(f"Only {pct_pos:.0f}% params positive (<60%)")

    r2 = sh["corr"] < 0
    print(f"  [{'FAIL' if r2 else 'PASS'}] Split-half correlation negative: {sh['corr']:.4f}  (need ≥0)")
    if r2:
        reject_reasons.append(f"Split-half correlation = {sh['corr']:.4f} (negative → regime-dependent)")

    r3 = (df_wf is None) or (wf_mean_sharpe < 0.5)
    wf_val = "N/A" if df_wf is None else f"{wf_mean_sharpe:.4f}"
    print(f"  [{'FAIL' if r3 else 'PASS'}] WF mean OOS Sharpe < 0.5: {wf_val}  (need ≥0.5)")
    if r3:
        reject_reasons.append(f"WF mean OOS Sharpe = {wf_val} (<0.5)")

    r4a = abs(corrs["corr_h012"]) > 0.5
    r4b = abs(corrs["corr_h019"]) > 0.5
    print(f"  [{'FAIL' if r4a else 'PASS'}] |Corr H-012| > 0.5: {corrs['corr_h012']:.4f}  (need |corr| ≤0.5)")
    print(f"  [{'FAIL' if r4b else 'PASS'}] |Corr H-019| > 0.5: {corrs['corr_h019']:.4f}  (need |corr| ≤0.5)")
    if r4a:
        reject_reasons.append(f"|Corr with H-012| = {corrs['corr_h012']:.4f} (>0.5, redundant)")
    if r4b:
        reject_reasons.append(f"|Corr with H-019| = {corrs['corr_h019']:.4f} (>0.5, redundant)")

    r5 = tt["best_oos_sharpe"] < 0.3
    print(f"  [{'FAIL' if r5 else 'PASS'}] OOS Sharpe < 0.3: {tt['best_oos_sharpe']:.4f}  (need ≥0.3)")
    if r5:
        reject_reasons.append(f"OOS Sharpe = {tt['best_oos_sharpe']:.4f} (<0.3)")

    print()
    if reject_reasons:
        print("  VERDICT: *** REJECTED ***")
        print("  Reasons:")
        for r in reject_reasons:
            print(f"    - {r}")
    else:
        print("  VERDICT: *** CONFIRMED ***")
        print(f"  All criteria passed — strategy shows robust RSI mean reversion signal.")
        print(f"  Best params: RSI{best_params[0]}_R{best_params[1]}_N{best_params[2]}")
        print(f"  OOS Sharpe: {tt['best_oos_sharpe']:.4f}  Ann: {tt['oos_annual_ret']:.1%}  MaxDD: {tt['oos_max_dd']:.1%}")

    print("\n" + "=" * 72)

    # Save results
    import json
    results_path = Path(__file__).parent / "results.json"
    results = {
        "hypothesis": "H-104",
        "title": "RSI Cross-Sectional Mean Reversion",
        "period": f"{closes.index[0].date()} to {closes.index[-1].date()}",
        "n_days": len(closes),
        "n_assets": len(closes.columns),
        "param_robustness": {"positive": int(pos_count), "total": 36, "pct": round(pct_pos, 1)},
        "full_scan": {"mean_sharpe": round(df_scan["sharpe"].mean(), 4),
                      "best_sharpe": round(df_scan["sharpe"].max(), 4),
                      "best_tag": df_scan.loc[df_scan["sharpe"].idxmax(), "tag"]},
        "train_test": tt,
        "walk_forward": {"mean_oos_sharpe": round(wf_mean_sharpe, 4),
                         "folds": df_wf.to_dict("records") if df_wf is not None else []},
        "split_half": sh,
        "fee_sensitivity": fees,
        "factor_correlations": corrs,
        "verdict": "REJECTED" if reject_reasons else "CONFIRMED",
        "reject_reasons": reject_reasons,
    }
    # Remove equity curves from results (not JSON-serializable)
    if "oos_equity" in results["train_test"]:
        del results["train_test"]["oos_equity"]
    results_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\n  Results saved to: {results_path}")


if __name__ == "__main__":
    main()
