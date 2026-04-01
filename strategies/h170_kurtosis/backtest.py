#!/usr/bin/env python3
"""
H-170: Return Kurtosis Factor (Cross-Sectional, Fresh Implementation)

For each asset on each day, compute scipy.stats.kurtosis (excess kurtosis)
of daily returns over a rolling lookback window.

  Low kurtosis  = thin tails = more predictable price action
  High kurtosis = fat tails  = crash-prone / unpredictable

Two directions:
  low_kurt_long  : long low-kurtosis assets (steady), short high-kurtosis
  high_kurt_long : long high-kurtosis assets, short low-kurtosis

Dollar-neutral: $1 long, $1 short. Equal weight within each leg.

Parameter grid:
  LB  ∈ [10, 20, 30, 40, 60]   (kurtosis lookback window)
  R   ∈ [3, 5, 7]               (rebalance every R days)
  N   ∈ [3, 4]                  (top/bottom N per leg)
  direction ∈ [low_kurt_long, high_kurt_long]
  Total: 5 × 3 × 2 × 2 = 60 combos

Validation:
  1. Full IS param scan → positive rate per direction
  2. Walk-forward (6 folds, ~6 months each, IS param selection per fold)
  3. Split-half stability (H1 vs H2 Sharpe)
  4. Correlations: H-012, H-076, H-160, H-167, H-169
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import kurtosis as scipy_kurtosis

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
    "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT", "NEAR/USDT",
    "OP/USDT", "ARB/USDT", "ATOM/USDT", "SUI/USDT",
]

# ── Parameter grid ──────────────────────────────────────────────────────────
LOOKBACKS  = [10, 20, 30, 40, 60]
REBALS     = [3, 5, 7]
NS         = [3, 4]
DIRECTIONS = ["low_kurt_long", "high_kurt_long"]

# Walk-forward config
WF_FOLDS    = 6
WF_TEST_DAYS = 90          # ~3 months per fold OOS window
WF_TRAIN_MIN = 120         # minimum IS bars required to fit

# ── Data loading ────────────────────────────────────────────────────────────

def load_daily_closes():
    """Load 1d cached parquet files from data/."""
    data_dir = ROOT / "data"
    daily = {}
    for sym in ASSETS:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if "close" in df.columns and len(df) >= 200:
                daily[sym] = df["close"]
    closes = pd.DataFrame(daily)
    closes = closes.dropna(how="all").ffill().dropna()
    return closes


def fetch_and_build_closes():
    """Fallback: fetch from ccxt if parquet not available."""
    import ccxt, time
    exchange = ccxt.bybit({"enableRateLimit": True})
    closes = {}
    for sym in ASSETS:
        try:
            ohlcv = exchange.fetch_ohlcv(sym, "1d", limit=1100)
            if len(ohlcv) < 200:
                continue
            df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
            df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
            df = df.set_index("ts").sort_index()
            closes[sym] = df["close"]
            time.sleep(0.2)
        except Exception as e:
            print(f"  WARN: {sym} failed — {e}")
    result = pd.DataFrame(closes).dropna(how="all").ffill().dropna()
    return result


# ── Kurtosis signal ─────────────────────────────────────────────────────────

def compute_kurtosis_panel(closes, lookback):
    """
    Return a DataFrame of excess kurtosis for each asset on each day,
    computed using scipy.stats.kurtosis (Fisher=True → excess kurtosis).
    """
    rets = closes.pct_change()
    result = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)

    for col in closes.columns:
        r = rets[col].values
        n = len(r)
        kurt_vals = np.full(n, np.nan)
        for i in range(lookback, n):
            window = r[i - lookback + 1: i + 1]
            valid = window[~np.isnan(window)]
            if len(valid) < max(4, lookback // 2):
                continue
            kurt_vals[i] = float(scipy_kurtosis(valid, fisher=True, bias=False))
        result[col] = kurt_vals

    return result


# Cache kurtosis panels to avoid recomputation
_kurt_cache: dict = {}

def get_kurt_panel(closes, lookback):
    key = (id(closes), lookback)
    if key not in _kurt_cache:
        _kurt_cache[key] = compute_kurtosis_panel(closes, lookback)
    return _kurt_cache[key]


# ── Backtest engine ──────────────────────────────────────────────────────────

def evaluate(rets: pd.Series, label: str = "") -> dict | None:
    """Compute Sharpe, annual return, max drawdown from a daily return series."""
    if rets is None or len(rets) < 30:
        return None
    ann   = rets.mean() * 365
    vol   = rets.std() * np.sqrt(365)
    sharpe = ann / vol if vol > 1e-8 else 0.0
    cum   = (1 + rets).cumprod()
    dd    = (cum / cum.cummax() - 1).min()
    return {
        "label":  label,
        "sharpe": round(sharpe, 4),
        "annual": round(ann * 100, 2),
        "dd":     round(dd * 100, 2),
        "days":   len(rets),
    }


def backtest_kurtosis(closes, lookback, rebal_freq, n, direction, kurt_panel=None):
    """
    Run a single kurtosis factor backtest.

    direction:
      "low_kurt_long"  → long bottom-N kurtosis, short top-N
      "high_kurt_long" → long top-N kurtosis, short bottom-N
    """
    if kurt_panel is None:
        kurt_panel = compute_kurtosis_panel(closes, lookback)

    rets   = closes.pct_change().dropna()
    dates  = rets.index
    warmup = lookback + 5

    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(warmup, len(dates)):
        # Apply existing weights
        if weights.abs().sum() > 0:
            day_ret = (rets.iloc[i] * weights).sum()
            portfolio_rets.append({"date": dates[i], "return": day_ret})

        # Rebalance
        if i - last_rebal >= rebal_freq:
            kurt_row = kurt_panel.iloc[i - 1]
            valid    = kurt_row.dropna()

            if len(valid) < n * 2:
                continue

            ranked = valid.sort_values(ascending=True)   # ascending = low first

            if direction == "low_kurt_long":
                longs  = ranked.index[:n]    # lowest kurtosis
                shorts = ranked.index[-n:]   # highest kurtosis
            else:  # high_kurt_long
                longs  = ranked.index[-n:]   # highest kurtosis
                shorts = ranked.index[:n]    # lowest kurtosis

            weights = pd.Series(0.0, index=closes.columns)
            for s in longs:
                weights[s] = 1.0 / n
            for s in shorts:
                weights[s] = -1.0 / n

            last_rebal = i

    if not portfolio_rets:
        return None
    df_out = pd.DataFrame(portfolio_rets).set_index("date")
    return df_out["return"]


# ── Reference strategy returns (for correlation) ────────────────────────────

def backtest_momentum(closes, lookback=60, rebal_freq=5, n=4):
    """H-012 cross-sectional momentum."""
    rets   = closes.pct_change().dropna()
    dates  = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            mom    = closes.iloc[i - 1] / closes.iloc[i - 1 - lookback] - 1
            ranked = mom.sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i

    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def backtest_efficiency(closes, lookback=40, rebal_freq=5, n=4):
    """H-076 price efficiency factor."""
    rets   = closes.pct_change().dropna()
    dates  = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                p = closes[sym].iloc[i - lookback: i]
                net_move    = abs(p.iloc[-1] / p.iloc[0] - 1)
                daily_moves = abs(p.pct_change().dropna()).sum()
                signals[sym] = net_move / daily_moves if daily_moves > 0 else 0.0
            ranked = pd.Series(signals).sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i

    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def backtest_trend_quality(closes, lookback=60, rebal_freq=5, n=3):
    """H-160 trend quality (efficiency × inv_vol)."""
    rets   = closes.pct_change().dropna()
    dates  = rets.index
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(lookback + 2, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes.columns:
                p   = closes[sym].iloc[i - lookback: i]
                net_move    = abs(p.iloc[-1] / p.iloc[0] - 1)
                daily_moves = abs(p.pct_change().dropna()).sum()
                eff         = net_move / daily_moves if daily_moves > 0 else 0.0
                vol         = rets[sym].iloc[max(0, i - lookback): i].std()
                inv_vol     = 1.0 / vol if vol > 1e-8 else 0.0
                signals[sym] = eff * inv_vol
            ranked = pd.Series(signals).sort_values(ascending=False)
            weights = pd.Series(0.0, index=closes.columns)
            for s in ranked.index[:n]:
                weights[s] = 1.0 / n
            for s in ranked.index[-n:]:
                weights[s] = -1.0 / n
            last_rebal = i

    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def backtest_h167(closes, lookback=10, rebal_freq=7, n=4):
    """H-167 volume-price confirmation factor (uses only closes as proxy)."""
    # Replicate the factor without needing volume data (uses 1d OHLCV from same file)
    data_dir = ROOT / "data"
    volumes = {}
    for sym in closes.columns:
        safe = sym.replace("/", "_")
        path = data_dir / f"{safe}_1d.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if "volume" in df.columns:
                volumes[sym] = df["volume"]
    if not volumes:
        return None

    vol_df = pd.DataFrame(volumes).reindex(closes.index).ffill().dropna(how="all")
    common = closes.index.intersection(vol_df.index)
    closes_c = closes.loc[common]
    vol_c    = vol_df.loc[common]

    rets   = closes_c.pct_change().dropna()
    dates  = rets.index
    warmup = lookback + 10
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes_c.columns)

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in closes_c.columns:
                p = closes_c[sym].iloc[max(0, i - lookback): i]
                v = vol_c[sym].iloc[max(0, i - lookback): i]
                if len(p) < lookback // 2:
                    continue
                pr = p.pct_change().dropna()
                vr = v.pct_change().dropna()
                mask = pr.notna() & vr.notna()
                if mask.sum() < 4:
                    continue
                corr = np.corrcoef(pr[mask].values, vr[mask].values)[0, 1]
                if not np.isnan(corr):
                    signals[sym] = corr
            if len(signals) >= n * 2:
                ranked = pd.Series(signals).sort_values(ascending=False)
                weights = pd.Series(0.0, index=closes_c.columns)
                for s in ranked.index[:n]:
                    weights[s] = 1.0 / n
                for s in ranked.index[-n:]:
                    weights[s] = -1.0 / n
                last_rebal = i

    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


def backtest_h169(closes, lookback=10, rebal_freq=5, n=4):
    """H-169 beta-adjusted momentum (alpha vs BTC)."""
    if "BTC/USDT" not in closes.columns:
        return None
    btc      = closes["BTC/USDT"]
    non_btc  = [c for c in closes.columns if c != "BTC/USDT"]
    rets     = closes.pct_change().dropna()
    dates    = rets.index
    warmup   = lookback + 10
    portfolio_rets = []
    last_rebal = -rebal_freq
    weights = pd.Series(0.0, index=closes.columns)

    for i in range(warmup, len(dates)):
        if weights.abs().sum() > 0:
            portfolio_rets.append({"date": dates[i], "return": (rets.iloc[i] * weights).sum()})
        if i - last_rebal >= rebal_freq:
            signals = {}
            for sym in non_btc:
                asset_r = closes[sym].pct_change().dropna().iloc[max(0, i - lookback): i]
                btc_r   = btc.pct_change().dropna().iloc[max(0, i - lookback): i]
                common  = asset_r.index.intersection(btc_r.index)
                if len(common) < lookback // 2:
                    continue
                a = asset_r.loc[common].values
                b = btc_r.loc[common].values
                var_b = np.var(b)
                if var_b < 1e-12:
                    continue
                beta  = np.cov(a, b)[0, 1] / var_b
                alpha = a.sum() - beta * b.sum()
                signals[sym] = alpha
            if len(signals) >= n * 2:
                ranked = pd.Series(signals).sort_values(ascending=False)
                weights = pd.Series(0.0, index=closes.columns)
                for s in ranked.index[:n]:
                    weights[s] = 1.0 / n
                for s in ranked.index[-n:]:
                    weights[s] = -1.0 / n
                last_rebal = i

    if not portfolio_rets:
        return None
    return pd.DataFrame(portfolio_rets).set_index("date")["return"]


# ── Walk-forward validation ─────────────────────────────────────────────────

def run_walk_forward(closes, best_direction):
    """
    6-fold walk-forward. For each fold, select best IS params from the full grid,
    then evaluate OOS on the subsequent ~6-month window.
    Each fold uses ~6-month OOS window stepping back from the most recent data.
    """
    n_total = len(closes)
    fold_results = []

    for fold in range(WF_FOLDS):
        oos_end   = n_total - fold * WF_TEST_DAYS
        oos_start = oos_end - WF_TEST_DAYS
        if oos_start < WF_TRAIN_MIN + 20:
            break

        train_closes = closes.iloc[:oos_start]
        oos_closes   = closes.iloc[oos_start: oos_end]

        if len(train_closes) < WF_TRAIN_MIN or len(oos_closes) < 20:
            break

        # IS param selection
        best_sharpe = -np.inf
        best_params = None
        for lb in LOOKBACKS:
            kp = compute_kurtosis_panel(train_closes, lb)
            for rf in REBALS:
                for n in NS:
                    r = backtest_kurtosis(train_closes, lb, rf, n, best_direction, kurt_panel=kp)
                    e = evaluate(r)
                    if e and e["sharpe"] > best_sharpe:
                        best_sharpe = e["sharpe"]
                        best_params = (lb, rf, n)

        if best_params is None:
            continue

        lb, rf, n = best_params
        oos_r = backtest_kurtosis(oos_closes, lb, rf, n, best_direction)
        oos_e = evaluate(oos_r)

        fold_results.append({
            "fold":        fold + 1,
            "is_params":   f"LB{lb}_R{rf}_N{n}",
            "is_sharpe":   round(best_sharpe, 3),
            "oos_sharpe":  oos_e["sharpe"] if oos_e else None,
            "oos_start":   closes.index[oos_start].date() if hasattr(closes.index[oos_start], "date") else str(closes.index[oos_start])[:10],
            "oos_end":     closes.index[min(oos_end - 1, len(closes) - 1)].date() if hasattr(closes.index[0], "date") else str(closes.index[min(oos_end - 1, len(closes) - 1)])[:10],
        })

    return fold_results


# ── Split-half ───────────────────────────────────────────────────────────────

def run_split_half(closes, direction):
    """Compute mean Sharpe for each half of the data across all param combos."""
    half = len(closes) // 2
    h1   = closes.iloc[:half]
    h2   = closes.iloc[half:]
    h1_sharpes = []
    h2_sharpes = []

    for lb in LOOKBACKS:
        kp1 = compute_kurtosis_panel(h1, lb)
        kp2 = compute_kurtosis_panel(h2, lb)
        for rf in REBALS:
            for n in NS:
                r1 = backtest_kurtosis(h1, lb, rf, n, direction, kurt_panel=kp1)
                r2 = backtest_kurtosis(h2, lb, rf, n, direction, kurt_panel=kp2)
                e1 = evaluate(r1)
                e2 = evaluate(r2)
                if e1 and e2:
                    h1_sharpes.append(e1["sharpe"])
                    h2_sharpes.append(e2["sharpe"])

    if not h1_sharpes:
        return None, None
    return round(np.mean(h1_sharpes), 3), round(np.mean(h2_sharpes), 3)


# ── Correlation helpers ──────────────────────────────────────────────────────

def safe_corr(a: pd.Series, b: pd.Series) -> float:
    common = a.dropna().index.intersection(b.dropna().index)
    if len(common) < 30:
        return float("nan")
    return round(float(np.corrcoef(a.loc[common].values, b.loc[common].values)[0, 1]), 3)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Loading daily close data...")
    closes = load_daily_closes()
    if len(closes.columns) < 10:
        print("Parquet cache insufficient, fetching from ccxt...")
        closes = fetch_and_build_closes()

    n_assets = len(closes.columns)
    n_days   = len(closes)
    print(f"Loaded {n_assets} assets, {n_days} daily bars")
    print(f"Date range: {closes.index[0]} → {closes.index[-1]}")

    if n_assets < 8:
        print("ERROR: Too few assets. Aborting.")
        sys.exit(1)

    # ── Pre-compute kurtosis panels for all lookbacks ────────────────────
    print("\nPre-computing kurtosis panels...")
    for lb in LOOKBACKS:
        get_kurt_panel(closes, lb)
        print(f"  LB={lb} done")

    # ── IS parameter scan ────────────────────────────────────────────────
    total_combos = len(LOOKBACKS) * len(REBALS) * len(NS)  # per direction
    print(f"\nScanning {total_combos * len(DIRECTIONS)} param combos "
          f"({total_combos} per direction × 2 directions)...")

    all_results: dict[str, list[dict]] = {d: [] for d in DIRECTIONS}

    for direction in DIRECTIONS:
        for lb in LOOKBACKS:
            kp = get_kurt_panel(closes, lb)
            for rf in REBALS:
                for n in NS:
                    r  = backtest_kurtosis(closes, lb, rf, n, direction, kurt_panel=kp)
                    ev = evaluate(r, f"LB{lb}_R{rf}_N{n}_{direction}")
                    if ev:
                        ev["lb"] = lb
                        ev["rf"] = rf
                        ev["n"]  = n
                        all_results[direction].append(ev)

    # ── Per-direction summaries ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("=== H-170 KURTOSIS FACTOR RESULTS ===")
    print("=" * 60)

    best_direction = None
    best_overall   = None

    for direction in DIRECTIONS:
        res = all_results[direction]
        if not res:
            print(f"Direction: {direction} — no valid results")
            continue
        df_res  = pd.DataFrame(res)
        n_pos   = (df_res["sharpe"] > 0).sum()
        n_total = len(df_res)
        pos_pct = n_pos / n_total * 100
        best    = df_res.loc[df_res["sharpe"].idxmax()]
        print(f"\nDirection: {direction} — {n_pos}/{n_total} positive ({pos_pct:.1f}%)")
        print(f"  Mean Sharpe: {df_res['sharpe'].mean():.3f} | Median: {df_res['sharpe'].median():.3f}")
        print(f"  Best params: LB{int(best['lb'])}_R{int(best['rf'])}_N{int(best['n'])}")
        print(f"  Best Sharpe: {best['sharpe']:.3f}, Annual: {best['annual']:.1f}%, Max DD: {best['dd']:.1f}%")

        print(f"\n  Top 5 ({direction}):")
        for _, row in df_res.nlargest(5, "sharpe").iterrows():
            print(f"    LB{int(row['lb'])}_R{int(row['rf'])}_N{int(row['n'])}: "
                  f"Sharpe {row['sharpe']:.3f}, Ann {row['annual']:.1f}%, DD {row['dd']:.1f}%")

        if best_overall is None or best["sharpe"] > best_overall["sharpe"]:
            best_overall   = best
            best_direction = direction

    # ── Choose the best direction for deeper analysis ────────────────────
    if best_overall is None:
        print("\nNo valid results. Aborting further analysis.")
        return

    best_lb = int(best_overall["lb"])
    best_rf = int(best_overall["rf"])
    best_n  = int(best_overall["n"])
    best_dir_res = all_results[best_direction]
    df_best_dir  = pd.DataFrame(best_dir_res)
    n_pos_best   = (df_best_dir["sharpe"] > 0).sum()
    pos_pct_best = n_pos_best / len(df_best_dir) * 100

    print(f"\n{'='*60}")
    print(f"Best overall: {best_direction} — LB{best_lb}_R{best_rf}_N{best_n}")
    print(f"  Sharpe: {best_overall['sharpe']:.3f}, Ann: {best_overall['annual']:.1f}%, DD: {best_overall['dd']:.1f}%")
    print(f"  IS positive rate: {pos_pct_best:.1f}% ({n_pos_best}/{len(df_best_dir)})")

    if pos_pct_best < 80.0:
        print(f"\n  FAIL: IS positive rate {pos_pct_best:.1f}% < 80% threshold.")
        print("  Walk-forward and correlation analysis skipped.")
        # Still print the final summary block
        print("\n" + "=" * 60)
        print("=== H-170 KURTOSIS FACTOR RESULTS ===")
        for direction in DIRECTIONS:
            res = all_results[direction]
            if res:
                df_d  = pd.DataFrame(res)
                n_p   = (df_d["sharpe"] > 0).sum()
                print(f"Direction: {direction} — {n_p}/{len(df_d)} positive ({n_p/len(df_d)*100:.1f}%)")
        print(f"Best params: LB{best_lb}_R{best_rf}_N{best_n} ({best_direction})")
        print(f"Best Sharpe: {best_overall['sharpe']:.2f}, "
              f"Annual return: {best_overall['annual']:.1f}%, "
              f"Max DD: {best_overall['dd']:.1f}%")
        return

    # ── Walk-forward ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"=== WALK-FORWARD ({best_direction}, 6 folds, {WF_TEST_DAYS}d OOS each) ===")
    wf_results = run_walk_forward(closes, best_direction)

    wf_oos_sharpes = [r["oos_sharpe"] for r in wf_results if r["oos_sharpe"] is not None]
    wf_n_pos = sum(1 for s in wf_oos_sharpes if s and s > 0)

    for r in wf_results:
        print(f"  Fold {r['fold']}: IS={r['is_params']} (IS Sharpe {r['is_sharpe']:.3f}), "
              f"OOS={r['oos_start']}→{r['oos_end']}, OOS Sharpe {r['oos_sharpe']:.3f}")

    mean_oos = np.mean(wf_oos_sharpes) if wf_oos_sharpes else float("nan")
    print(f"\nWF results: {wf_n_pos}/{len(wf_oos_sharpes)} positive, mean OOS Sharpe: {mean_oos:.3f}")

    # ── Split-half ───────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"=== SPLIT-HALF STABILITY ({best_direction}) ===")
    h1_sharpe, h2_sharpe = run_split_half(closes, best_direction)
    if h1_sharpe is not None:
        print(f"  H1 mean Sharpe: {h1_sharpe:.3f}")
        print(f"  H2 mean Sharpe: {h2_sharpe:.3f}")

    # ── Correlations ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("=== CORRELATIONS ===")

    # Best factor returns
    kp_full = get_kurt_panel(closes, best_lb)
    best_rets = backtest_kurtosis(closes, best_lb, best_rf, best_n, best_direction, kurt_panel=kp_full)

    print("  Computing reference strategy returns...")
    mom_rets   = backtest_momentum(closes)
    eff_rets   = backtest_efficiency(closes)
    tq_rets    = backtest_trend_quality(closes)
    h167_rets  = backtest_h167(closes)
    h169_rets  = backtest_h169(closes)

    corr_h012 = safe_corr(best_rets, mom_rets)
    corr_h076 = safe_corr(best_rets, eff_rets)
    corr_h160 = safe_corr(best_rets, tq_rets)
    corr_h167 = safe_corr(best_rets, h167_rets) if h167_rets is not None else float("nan")
    corr_h169 = safe_corr(best_rets, h169_rets) if h169_rets is not None else float("nan")

    print(f"  H-012 (momentum):      {corr_h012:.3f}")
    print(f"  H-076 (efficiency):    {corr_h076:.3f}")
    print(f"  H-160 (trend quality): {corr_h160:.3f}")
    print(f"  H-167 (vol-price):     {corr_h167:.3f}")
    print(f"  H-169 (alpha/BTC):     {corr_h169:.3f}")

    # ── Final summary block ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("=== H-170 KURTOSIS FACTOR RESULTS ===")
    for direction in DIRECTIONS:
        res = all_results[direction]
        if res:
            df_d  = pd.DataFrame(res)
            n_p   = (df_d["sharpe"] > 0).sum()
            print(f"Direction: {direction} — {n_p}/{len(df_d)} positive ({n_p/len(df_d)*100:.1f}%)")
    print(f"Best params: LB{best_lb}_R{best_rf}_N{best_n} ({best_direction})")
    print(f"Best Sharpe: {best_overall['sharpe']:.2f}, "
          f"Annual return: {best_overall['annual']:.1f}%, "
          f"Max DD: {best_overall['dd']:.1f}%")

    if wf_oos_sharpes:
        print(f"WF results: {wf_n_pos}/{len(wf_oos_sharpes)} positive, mean OOS Sharpe: {mean_oos:.2f}")
        if h1_sharpe is not None:
            print(f"Split-half: H1={h1_sharpe:.2f}, H2={h2_sharpe:.2f}")
        print(f"Correlations: H-012={corr_h012:.2f}, H-076={corr_h076:.2f}, H-160={corr_h160:.2f}, "
              f"H-167={corr_h167:.2f}, H-169={corr_h169:.2f}")


if __name__ == "__main__":
    main()
