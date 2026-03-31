"""
H-150: OI-Funding Interaction Factor

Concept: Combine OI change and funding rate into a single cross-sectional signal.
  signal = sign(OI_change) * funding_avg   (sign-based interaction)
  also tested: signal = OI_change_pct * funding_avg (raw interaction)

Positioning logic (contrarian):
  - Rising OI + positive funding = leveraged longs building (frothy) → SHORT
  - Rising OI + negative funding = leveraged shorts building → LONG (squeeze)
  - Falling OI: less signal strength

Each rebalance day: LONG bottom N assets by signal, SHORT top N assets.

Data sources:
  - Price: data/{SYM}_USDT_1d.parquet
  - OI: data/oi/{SYM}_oi_1d.parquet  (column: openInterest, index: timestamp tz-naive)
  - Funding: data/{SYM}_USDT_USDT_funding.parquet  (8h intervals → resample to daily avg)

Parameter grid: OI_windows [5,10,14,20] × funding_windows [3,5,7] × rebal [5,7,10] × N [3,4]
  = 72 combos per signal variant (raw + sign-based → choose best variant)

Validation criteria (all 4 required):
  1. IS: ≥60% of params positive Sharpe
  2. WF OOS: ≥4/6 folds positive AND mean OOS Sharpe > 0.5
  3. Split-half: Both halves positive Sharpe
  4. Correlation: |corr with H-012| < 0.40, |corr with H-044| < 0.40,
                  |corr with H-053| < 0.40
"""

import json
import sys
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

# ─── Configuration ──────────────────────────────────────────────────────────

ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX",
    "DOT", "LINK", "ATOM", "NEAR", "OP", "ARB", "SUI",
]

DATA_DIR = ROOT / "data"
OI_DIR = DATA_DIR / "oi"
FEE_RATE = 0.001           # 10 bps per trade (0.1%)
INITIAL_CAPITAL = 10_000.0
PPY = 365                  # periods per year (daily)

# Parameter grid: 4 × 3 × 3 × 2 = 72 combos
OI_WINDOWS = [5, 10, 14, 20]
FUND_WINDOWS = [3, 5, 7]
REBAL_FREQS = [5, 7, 10]
N_POSITIONS = [3, 4]

# Walk-forward
WF_FOLDS = 6
WF_TEST_DAYS = 90        # ~3 months per fold
WF_MIN_TRAIN = 180       # ~6 months minimum train

# Reference strategy params for correlation
H012_MOM = 21            # momentum lookback
H012_REBAL = 5
H012_N = 4

H044_OI_WIN = 14
H044_REBAL = 7
H044_N = 4

H053_FUND_WIN = 7
H053_REBAL = 5
H053_N = 4


# ─── Data Loading ────────────────────────────────────────────────────────────

def load_closes() -> pd.DataFrame:
    """Load daily close prices, tz-naive index."""
    frames = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        s = df["close"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        frames[asset] = s
    closes = pd.DataFrame(frames).sort_index()
    closes = closes.dropna(how="all").ffill().dropna(how="all")
    return closes


def load_oi() -> pd.DataFrame:
    """Load daily OI, tz-naive index."""
    frames = {}
    for asset in ASSETS:
        fp = OI_DIR / f"{asset}_oi_1d.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        s = df["openInterest"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        frames[asset] = s
    oi = pd.DataFrame(frames).sort_index()
    oi = oi.dropna(how="all")
    return oi


def load_funding_daily() -> pd.DataFrame:
    """
    Load 8h funding data and resample to daily average.
    Daily avg = mean of 3 daily funding ticks (00:00, 08:00, 16:00).
    """
    frames = {}
    for asset in ASSETS:
        fp = DATA_DIR / f"{asset}_USDT_USDT_funding.parquet"
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        s = df["funding_rate"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        # resample to daily: mean of 3 ticks = daily funding proxy
        daily = s.resample("1D").mean()
        frames[asset] = daily
    fund = pd.DataFrame(frames).sort_index()
    fund = fund.dropna(how="all")
    return fund


# ─── Signal Computation ──────────────────────────────────────────────────────

def compute_signal(
    closes: pd.DataFrame,
    oi: pd.DataFrame,
    fund_daily: pd.DataFrame,
    oi_win: int,
    fund_win: int,
    use_sign: bool = True,
) -> pd.DataFrame:
    """
    Compute the OI-funding interaction signal for each asset on each day.

    signal_sign  = sign(OI_change_pct) * rolling_avg_funding
    signal_raw   = OI_change_pct * rolling_avg_funding

    Higher signal → frothy longs (rising OI + positive funding) → SHORT
    Lower signal  → aggressive shorts (rising OI + negative funding) → LONG
    """
    # Align all DataFrames to common dates
    common_idx = closes.index.intersection(oi.index).intersection(fund_daily.index)
    closes_a = closes.reindex(common_idx)
    oi_a = oi.reindex(common_idx)
    fund_a = fund_daily.reindex(common_idx)

    # OI percentage change over oi_win days (lagged by 1 to avoid look-ahead)
    oi_chg = oi_a.pct_change(oi_win)       # shape (T, A)

    # Rolling average funding over fund_win days
    fund_avg = fund_a.rolling(fund_win, min_periods=fund_win).mean()

    # Interaction
    if use_sign:
        signal = np.sign(oi_chg) * fund_avg
    else:
        signal = oi_chg * fund_avg

    # Lag by 1 day to avoid look-ahead bias (signal formed at close of day t,
    # position entered at open of day t+1)
    signal = signal.shift(1)

    return signal, common_idx


# ─── Portfolio Simulation ────────────────────────────────────────────────────

def simulate(
    closes: pd.DataFrame,
    signal: pd.DataFrame,
    rebal: int,
    n_pos: int,
    start_idx: int = 0,
    end_idx: int = None,
) -> pd.Series:
    """
    Long bottom-N, short top-N assets by signal.
    Rebalance every `rebal` days.
    Returns daily equity curve.
    """
    dates = signal.index
    if end_idx is None:
        end_idx = len(dates)

    dates = dates[start_idx:end_idx]
    sig = signal.iloc[start_idx:end_idx]
    cls = closes.reindex(dates)

    # Daily returns (for all assets, available on common index)
    rets = cls.pct_change().fillna(0.0)

    equity = INITIAL_CAPITAL
    equity_curve = []
    current_weights = pd.Series(dtype=float)
    days_since_rebal = rebal  # force first rebalance immediately

    for i, dt in enumerate(dates):
        day_rets = rets.iloc[i]

        # Apply portfolio returns
        if len(current_weights) > 0:
            port_ret = (current_weights * day_rets.reindex(current_weights.index, fill_value=0.0)).sum()
            equity *= (1.0 + port_ret)

        # Rebalance check
        days_since_rebal += 1
        if days_since_rebal >= rebal:
            row = sig.iloc[i].dropna()
            # Need at least 2*n_pos assets
            if len(row) >= 2 * n_pos:
                sorted_row = row.sort_values()
                longs = sorted_row.iloc[:n_pos].index.tolist()
                shorts = sorted_row.iloc[-n_pos:].index.tolist()

                new_weights = pd.Series(0.0, index=longs + shorts)
                for a in longs:
                    new_weights[a] = 1.0 / n_pos
                for a in shorts:
                    new_weights[a] = -1.0 / n_pos

                # Transaction costs: fee on positions that changed
                if len(current_weights) > 0:
                    combined = new_weights.reindex(
                        new_weights.index.union(current_weights.index), fill_value=0.0
                    )
                    old_combined = current_weights.reindex(combined.index, fill_value=0.0)
                    turnover = (combined - old_combined).abs().sum() / 2.0
                else:
                    turnover = new_weights.abs().sum() / 2.0

                fee = turnover * FEE_RATE
                equity *= (1.0 - fee)
                current_weights = new_weights
                days_since_rebal = 0

        equity_curve.append(equity)

    return pd.Series(equity_curve, index=dates)


# ─── Walk-Forward ────────────────────────────────────────────────────────────

def walk_forward(
    closes: pd.DataFrame,
    signal: pd.DataFrame,
    n_pos: int,
) -> list:
    """
    6-fold expanding-window walk-forward.
    Train: first K periods, Test: next WF_TEST_DAYS.
    Returns list of (fold_idx, oos_sharpe, oos_equity).
    """
    T = len(signal)
    results = []

    # Determine fold boundaries
    total_test = WF_FOLDS * WF_TEST_DAYS
    if T < WF_MIN_TRAIN + total_test:
        return results

    test_start = T - total_test

    for fold in range(WF_FOLDS):
        train_end = test_start + fold * WF_TEST_DAYS
        test_end = train_end + WF_TEST_DAYS

        if train_end < WF_MIN_TRAIN:
            continue

        # Find best IS param (rebal) using train period
        best_sharpe_is = -np.inf
        best_rebal = REBAL_FREQS[0]
        for r in REBAL_FREQS:
            eq = simulate(closes, signal, r, n_pos, 0, train_end)
            if len(eq) < 20:
                continue
            s = sharpe_ratio(eq.pct_change().dropna(), periods_per_year=PPY)
            if s > best_sharpe_is:
                best_sharpe_is = s
                best_rebal = r

        # OOS evaluation
        oos_eq = simulate(closes, signal, best_rebal, n_pos, train_end, test_end)
        if len(oos_eq) < 5:
            continue
        oos_sh = sharpe_ratio(oos_eq.pct_change().dropna(), periods_per_year=PPY)
        results.append((fold, oos_sh, oos_eq, best_rebal))

    return results


# ─── Reference Strategies for Correlation ───────────────────────────────────

def compute_h012_returns(closes: pd.DataFrame, signal_index: pd.Index) -> pd.Series:
    """H-012: cross-sectional momentum (21d return, top/bottom 4, 5d rebal)."""
    cls = closes.reindex(signal_index)
    mom = cls.pct_change(H012_MOM).shift(1)
    rets = cls.pct_change().fillna(0.0)

    equity = INITIAL_CAPITAL
    equity_curve = []
    weights = pd.Series(dtype=float)
    days_since_rebal = H012_REBAL

    for i, dt in enumerate(signal_index):
        day_rets = rets.iloc[i]
        if len(weights) > 0:
            port_ret = (weights * day_rets.reindex(weights.index, fill_value=0.0)).sum()
            equity *= (1.0 + port_ret)
        days_since_rebal += 1
        if days_since_rebal >= H012_REBAL:
            row = mom.iloc[i].dropna()
            if len(row) >= 2 * H012_N:
                sorted_row = row.sort_values()
                longs = sorted_row.iloc[-H012_N:].index.tolist()   # momentum: long winners
                shorts = sorted_row.iloc[:H012_N].index.tolist()    # short losers
                new_w = pd.Series(0.0, index=longs + shorts)
                for a in longs:
                    new_w[a] = 1.0 / H012_N
                for a in shorts:
                    new_w[a] = -1.0 / H012_N
                weights = new_w
                days_since_rebal = 0
        equity_curve.append(equity)

    return pd.Series(equity_curve, index=signal_index).pct_change().dropna()


def compute_h044_returns(
    closes: pd.DataFrame, oi: pd.DataFrame, signal_index: pd.Index
) -> pd.Series:
    """H-044: OI divergence (price return × OI change, contrarian)."""
    cls = closes.reindex(signal_index)
    oi_a = oi.reindex(signal_index)

    price_ret = cls.pct_change(H044_OI_WIN)
    oi_chg = oi_a.pct_change(H044_OI_WIN)
    # Interaction: price rising + OI rising = crowded → signal
    divergence = price_ret * oi_chg
    # Contrarian: short high, long low — shift 1 for no look-ahead
    div_signal = divergence.shift(1)

    rets = cls.pct_change().fillna(0.0)
    equity = INITIAL_CAPITAL
    equity_curve = []
    weights = pd.Series(dtype=float)
    days_since_rebal = H044_REBAL

    for i, dt in enumerate(signal_index):
        day_rets = rets.iloc[i]
        if len(weights) > 0:
            port_ret = (weights * day_rets.reindex(weights.index, fill_value=0.0)).sum()
            equity *= (1.0 + port_ret)
        days_since_rebal += 1
        if days_since_rebal >= H044_REBAL:
            row = div_signal.iloc[i].dropna()
            if len(row) >= 2 * H044_N:
                sorted_row = row.sort_values()
                # contrarian: long lowest (negative divergence), short highest
                longs = sorted_row.iloc[:H044_N].index.tolist()
                shorts = sorted_row.iloc[-H044_N:].index.tolist()
                new_w = pd.Series(0.0, index=longs + shorts)
                for a in longs:
                    new_w[a] = 1.0 / H044_N
                for a in shorts:
                    new_w[a] = -1.0 / H044_N
                weights = new_w
                days_since_rebal = 0
        equity_curve.append(equity)

    return pd.Series(equity_curve, index=signal_index).pct_change().dropna()


def compute_h053_returns(
    closes: pd.DataFrame, fund_daily: pd.DataFrame, signal_index: pd.Index
) -> pd.Series:
    """H-053: funding rate XS (cross-sectional funding, contrarian)."""
    cls = closes.reindex(signal_index)
    fund_a = fund_daily.reindex(signal_index)
    fund_avg = fund_a.rolling(H053_FUND_WIN, min_periods=H053_FUND_WIN).mean().shift(1)

    rets = cls.pct_change().fillna(0.0)
    equity = INITIAL_CAPITAL
    equity_curve = []
    weights = pd.Series(dtype=float)
    days_since_rebal = H053_REBAL

    for i, dt in enumerate(signal_index):
        day_rets = rets.iloc[i]
        if len(weights) > 0:
            port_ret = (weights * day_rets.reindex(weights.index, fill_value=0.0)).sum()
            equity *= (1.0 + port_ret)
        days_since_rebal += 1
        if days_since_rebal >= H053_REBAL:
            row = fund_avg.iloc[i].dropna()
            if len(row) >= 2 * H053_N:
                sorted_row = row.sort_values()
                # contrarian: long lowest funding (shorts getting paid), short highest
                longs = sorted_row.iloc[:H053_N].index.tolist()
                shorts = sorted_row.iloc[-H053_N:].index.tolist()
                new_w = pd.Series(0.0, index=longs + shorts)
                for a in longs:
                    new_w[a] = 1.0 / H053_N
                for a in shorts:
                    new_w[a] = -1.0 / H053_N
                weights = new_w
                days_since_rebal = 0
        equity_curve.append(equity)

    return pd.Series(equity_curve, index=signal_index).pct_change().dropna()


# ─── Full IS Parameter Sweep ─────────────────────────────────────────────────

def run_is_sweep(
    closes: pd.DataFrame,
    oi: pd.DataFrame,
    fund_daily: pd.DataFrame,
    use_sign: bool,
) -> list:
    """Run full IS parameter sweep. Returns list of result dicts."""
    results = []
    combos = list(product(OI_WINDOWS, FUND_WINDOWS, REBAL_FREQS, N_POSITIONS))
    variant_name = "sign" if use_sign else "raw"

    for oi_win, f_win, rebal, n_pos in combos:
        sig, common_idx = compute_signal(closes, oi, fund_daily, oi_win, f_win, use_sign)
        # align closes to signal index
        cls_aligned = closes.reindex(common_idx)
        eq = simulate(cls_aligned, sig, rebal, n_pos)
        if len(eq) < 50:
            continue
        r = eq.pct_change().dropna()
        sh = sharpe_ratio(r, periods_per_year=PPY)
        ar = annual_return(eq, periods_per_year=PPY)
        mdd = max_drawdown(eq)
        results.append({
            "variant": variant_name,
            "oi_win": oi_win, "f_win": f_win, "rebal": rebal, "n_pos": n_pos,
            "sharpe": sh, "annual_return": ar, "max_drawdown": mdd,
            "n_days": len(eq),
        })

    return results


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("H-150: OI-Funding Interaction Factor Backtest")
    print("=" * 70)

    # Load data
    print("\n[1] Loading data...")
    closes = load_closes()
    oi = load_oi()
    fund_daily = load_funding_daily()

    print(f"    Closes:  {closes.shape}  ({closes.index[0].date()} → {closes.index[-1].date()})")
    print(f"    OI:      {oi.shape}  ({oi.index[0].date()} → {oi.index[-1].date()})")
    print(f"    Funding: {fund_daily.shape}  ({fund_daily.index[0].date()} → {fund_daily.index[-1].date()})")

    # Common overlap
    common_start = max(closes.index[0], oi.index[0], fund_daily.index[0])
    common_end = min(closes.index[-1], oi.index[-1], fund_daily.index[-1])
    print(f"\n    Common overlap: {common_start.date()} → {common_end.date()}")

    # Assets with full data coverage in overlap
    overlap_closes = closes.loc[common_start:common_end]
    overlap_oi = oi.loc[common_start:common_end]
    overlap_fund = fund_daily.loc[common_start:common_end]

    valid_assets = []
    for a in ASSETS:
        has_price = a in overlap_closes.columns and overlap_closes[a].notna().sum() > 200
        has_oi = a in overlap_oi.columns and overlap_oi[a].notna().sum() > 200
        has_fund = a in overlap_fund.columns and overlap_fund[a].notna().sum() > 200
        if has_price and has_oi and has_fund:
            valid_assets.append(a)

    print(f"    Valid assets ({len(valid_assets)}): {valid_assets}")

    if len(valid_assets) < 7:
        print("ERROR: Insufficient assets (need ≥ 7). Aborting.")
        sys.exit(1)

    closes_v = overlap_closes[valid_assets]
    oi_v = overlap_oi[valid_assets]
    fund_v = overlap_fund[valid_assets]

    # ─── IS Parameter Sweep ──────────────────────────────────────────────────
    print("\n[2] IS Parameter Sweep (sign-based variant)...")
    sign_results = run_is_sweep(closes_v, oi_v, fund_v, use_sign=True)
    print(f"    Completed {len(sign_results)} combinations (sign)")

    print("    IS Parameter Sweep (raw variant)...")
    raw_results = run_is_sweep(closes_v, oi_v, fund_v, use_sign=False)
    print(f"    Completed {len(raw_results)} combinations (raw)")

    all_is = sign_results + raw_results

    # Pick best variant by fraction with positive Sharpe
    sign_pos_frac = sum(1 for r in sign_results if r["sharpe"] > 0) / max(len(sign_results), 1)
    raw_pos_frac = sum(1 for r in raw_results if r["sharpe"] > 0) / max(len(raw_results), 1)
    print(f"\n    Sign variant: {sign_pos_frac:.1%} positive Sharpe ({len(sign_results)} combos)")
    print(f"    Raw  variant: {raw_pos_frac:.1%} positive Sharpe ({len(raw_results)} combos)")

    # Choose best-performing variant for deeper analysis
    use_sign_best = sign_pos_frac >= raw_pos_frac
    chosen_results = sign_results if use_sign_best else raw_results
    chosen_variant = "sign" if use_sign_best else "raw"
    chosen_pos_frac = sign_pos_frac if use_sign_best else raw_pos_frac
    print(f"\n    → Selected variant: {chosen_variant} ({chosen_pos_frac:.1%} positive IS Sharpe)")

    # Criterion 1
    crit1 = chosen_pos_frac >= 0.60
    print(f"\n    Criterion 1 (IS ≥60% positive Sharpe): {'PASS' if crit1 else 'FAIL'} "
          f"({chosen_pos_frac:.1%})")

    # Best IS param set
    best_is = sorted(chosen_results, key=lambda x: x["sharpe"], reverse=True)[0]
    print(f"\n    Best IS params: OI_win={best_is['oi_win']}, f_win={best_is['f_win']}, "
          f"rebal={best_is['rebal']}, n={best_is['n_pos']}")
    print(f"    Best IS Sharpe: {best_is['sharpe']:.3f} | AR: {best_is['annual_return']:.1%} | "
          f"MDD: {best_is['max_drawdown']:.1%}")

    # ─── Walk-Forward ────────────────────────────────────────────────────────
    print("\n[3] Walk-Forward Validation (6 folds)...")
    # Use best IS OI/f windows, walk-forward selects best rebal per fold
    use_sign = use_sign_best
    wf_sig, wf_idx = compute_signal(closes_v, oi_v, fund_v,
                                     best_is["oi_win"], best_is["f_win"], use_sign)
    closes_wf = closes_v.reindex(wf_idx)

    # Use best N from IS
    best_n = best_is["n_pos"]
    wf_folds = walk_forward(closes_wf, wf_sig, best_n)

    if len(wf_folds) > 0:
        oos_sharpes = [f[1] for f in wf_folds]
        pos_folds = sum(1 for s in oos_sharpes if s > 0)
        mean_oos_sh = np.mean(oos_sharpes)
        print(f"    Completed {len(wf_folds)} folds")
        for fold, sh, eq, rb in wf_folds:
            ar = annual_return(eq, periods_per_year=PPY)
            mdd = max_drawdown(eq)
            print(f"      Fold {fold+1}: Sharpe={sh:.3f}, AR={ar:.1%}, MDD={mdd:.1%}, "
                  f"best_rebal={rb}, n_days={len(eq)}")
        print(f"    Positive folds: {pos_folds}/{len(wf_folds)}")
        print(f"    Mean OOS Sharpe: {mean_oos_sh:.3f}")
        crit2 = pos_folds >= 4 and mean_oos_sh > 0.5
    else:
        pos_folds = 0
        mean_oos_sh = 0.0
        crit2 = False
        print("    WARN: Not enough data for walk-forward")

    print(f"\n    Criterion 2 (WF ≥4/6 positive AND mean OOS Sharpe > 0.5): "
          f"{'PASS' if crit2 else 'FAIL'} (pos={pos_folds}/{len(wf_folds)}, mean={mean_oos_sh:.3f})")

    # ─── Split-Half ──────────────────────────────────────────────────────────
    print("\n[4] Split-Half Validation...")
    sig_sh, idx_sh = compute_signal(closes_v, oi_v, fund_v,
                                     best_is["oi_win"], best_is["f_win"], use_sign)
    closes_sh = closes_v.reindex(idx_sh)

    T = len(idx_sh)
    mid = T // 2

    eq_h1 = simulate(closes_sh, sig_sh, best_is["rebal"], best_is["n_pos"], 0, mid)
    eq_h2 = simulate(closes_sh, sig_sh, best_is["rebal"], best_is["n_pos"], mid, T)

    sh_h1 = sharpe_ratio(eq_h1.pct_change().dropna(), periods_per_year=PPY) if len(eq_h1) > 5 else 0.0
    sh_h2 = sharpe_ratio(eq_h2.pct_change().dropna(), periods_per_year=PPY) if len(eq_h2) > 5 else 0.0
    ar_h1 = annual_return(eq_h1, periods_per_year=PPY)
    ar_h2 = annual_return(eq_h2, periods_per_year=PPY)

    print(f"    H1 ({idx_sh[0].date()} → {idx_sh[mid-1].date()}): "
          f"Sharpe={sh_h1:.3f}, AR={ar_h1:.1%}")
    print(f"    H2 ({idx_sh[mid].date()} → {idx_sh[-1].date()}): "
          f"Sharpe={sh_h2:.3f}, AR={ar_h2:.1%}")

    crit3 = sh_h1 > 0 and sh_h2 > 0
    print(f"\n    Criterion 3 (Both halves positive Sharpe): {'PASS' if crit3 else 'FAIL'}")

    # ─── Correlation Analysis ─────────────────────────────────────────────────
    print("\n[5] Correlation with Reference Strategies...")
    sig_full, idx_full = compute_signal(closes_v, oi_v, fund_v,
                                         best_is["oi_win"], best_is["f_win"], use_sign)
    closes_full = closes_v.reindex(idx_full)

    eq_main = simulate(closes_full, sig_full, best_is["rebal"], best_is["n_pos"])
    r_main = eq_main.pct_change().dropna()

    r_h012 = compute_h012_returns(closes_full, idx_full)
    r_h044 = compute_h044_returns(closes_full, oi_v, idx_full)
    r_h053 = compute_h053_returns(closes_full, fund_v, idx_full)

    # Align
    common_r = r_main.index.intersection(r_h012.index).intersection(r_h044.index).intersection(r_h053.index)
    r_main_c = r_main.reindex(common_r)
    r_h012_c = r_h012.reindex(common_r)
    r_h044_c = r_h044.reindex(common_r)
    r_h053_c = r_h053.reindex(common_r)

    corr_h012 = float(r_main_c.corr(r_h012_c))
    corr_h044 = float(r_main_c.corr(r_h044_c))
    corr_h053 = float(r_main_c.corr(r_h053_c))

    print(f"    Correlation with H-012 (momentum):    {corr_h012:+.3f}")
    print(f"    Correlation with H-044 (OI diverge):  {corr_h044:+.3f}")
    print(f"    Correlation with H-053 (funding XS):  {corr_h053:+.3f}")

    crit4 = (abs(corr_h012) < 0.40 and abs(corr_h044) < 0.40 and abs(corr_h053) < 0.40)
    print(f"\n    Criterion 4 (all |corr| < 0.40): {'PASS' if crit4 else 'FAIL'}")

    # ─── Full Backtest Summary ────────────────────────────────────────────────
    print("\n[6] Full Backtest (best IS params)...")
    sh_full = sharpe_ratio(r_main, periods_per_year=PPY)
    ar_full = annual_return(eq_main, periods_per_year=PPY)
    mdd_full = max_drawdown(eq_main)
    total_ret = (eq_main.iloc[-1] / eq_main.iloc[0]) - 1.0

    print(f"    Period: {idx_full[0].date()} → {idx_full[-1].date()}")
    print(f"    N days: {len(eq_main)}")
    print(f"    Annual Return:  {ar_full:.1%}")
    print(f"    Total Return:   {total_ret:.1%}")
    print(f"    Sharpe Ratio:   {sh_full:.3f}")
    print(f"    Max Drawdown:   {mdd_full:.1%}")

    # ─── Final Verdict ────────────────────────────────────────────────────────
    all_pass = crit1 and crit2 and crit3 and crit4
    verdict = "CONFIRMED" if all_pass else "REJECTED"
    passed = sum([crit1, crit2, crit3, crit4])

    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY — H-150: OI-Funding Interaction Factor")
    print("=" * 70)
    print(f"  Chosen variant:  {chosen_variant}")
    print(f"  Best params:     OI_win={best_is['oi_win']}, f_win={best_is['f_win']}, "
          f"rebal={best_is['rebal']}, n={best_is['n_pos']}")
    print(f"  IS combos tested: {len(chosen_results)} (both variants: {len(all_is)})")
    print()
    print(f"  Criterion 1 — IS ≥60% positive Sharpe:            {'PASS ✓' if crit1 else 'FAIL ✗'}  ({chosen_pos_frac:.1%})")
    print(f"  Criterion 2 — WF ≥4/6 pos folds + mean OOS>0.5:  {'PASS ✓' if crit2 else 'FAIL ✗'}  ({pos_folds}/{len(wf_folds) if wf_folds else 0} folds, mean={mean_oos_sh:.3f})")
    print(f"  Criterion 3 — Split-half both positive:            {'PASS ✓' if crit3 else 'FAIL ✗'}  (H1={sh_h1:.3f}, H2={sh_h2:.3f})")
    print(f"  Criterion 4 — Correlation < 0.40:                  {'PASS ✓' if crit4 else 'FAIL ✗'}  (H012={corr_h012:+.3f}, H044={corr_h044:+.3f}, H053={corr_h053:+.3f})")
    print()
    print(f"  Overall: {passed}/4 criteria passed")
    print(f"  Verdict: {verdict}")
    print()
    print(f"  Full IS metrics:  AR={ar_full:.1%}, MDD={mdd_full:.1%}, Sharpe={sh_full:.3f}")
    print("=" * 70)

    # ─── Save Results ─────────────────────────────────────────────────────────
    results_dict = {
        "hypothesis": "H-150",
        "name": "OI-Funding Interaction Factor",
        "verdict": verdict,
        "criteria_passed": passed,
        "criteria": {
            "c1_is_pos_frac": {"pass": crit1, "value": round(chosen_pos_frac, 4)},
            "c2_wf_oos": {
                "pass": crit2,
                "pos_folds": pos_folds,
                "total_folds": len(wf_folds) if wf_folds else 0,
                "mean_oos_sharpe": round(mean_oos_sh, 4),
            },
            "c3_split_half": {
                "pass": crit3,
                "sharpe_h1": round(sh_h1, 4),
                "sharpe_h2": round(sh_h2, 4),
            },
            "c4_correlation": {
                "pass": crit4,
                "corr_h012": round(corr_h012, 4),
                "corr_h044": round(corr_h044, 4),
                "corr_h053": round(corr_h053, 4),
            },
        },
        "best_params": {
            "variant": chosen_variant,
            "oi_win": best_is["oi_win"],
            "f_win": best_is["f_win"],
            "rebal": best_is["rebal"],
            "n_pos": best_is["n_pos"],
        },
        "full_backtest": {
            "annual_return": round(ar_full, 4),
            "total_return": round(total_ret, 4),
            "sharpe": round(sh_full, 4),
            "max_drawdown": round(mdd_full, 4),
            "n_days": int(len(eq_main)),
            "start": str(idx_full[0].date()),
            "end": str(idx_full[-1].date()),
        },
        "n_assets": len(valid_assets),
        "assets": valid_assets,
        "is_combos_tested": len(all_is),
    }

    out_path = Path(__file__).parent / "results.json"
    with open(out_path, "w") as f:
        json.dump(results_dict, f, indent=2)
    print(f"\n  Results saved to: {out_path}")


if __name__ == "__main__":
    main()
