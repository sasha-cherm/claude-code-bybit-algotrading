"""
H-013 Track 2: Dynamic Portfolio Allocation

When H-011 (BTC funding arb) is OUT of position (rolling-27 avg < 0),
redistribute its 60% allocation to H-009 (trend) and H-012 (XSMom).

Test configurations:
- Static A: 20/60/20 always (current)
- Dynamic B: 20/60/20 when funding IN, 50/0/50 when OUT
- Dynamic C: 20/60/20 when funding IN, 40/0/60 when OUT
- Dynamic D: 20/60/20 when funding IN, 30/0/70 when OUT
- Static E: 50/0/50 always (no funding at all)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
DATA_DIR = ROOT / "data"

ASSETS_NAMES = ["BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX", "LINK",
                "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM"]


def build_strategy_daily_returns():
    """Build daily return series for each strategy component."""

    # H-009: BTC daily EMA trend following with vol targeting
    btc_df = pd.read_parquet(DATA_DIR / "BTC_USDT_1h.parquet")
    btc_daily = btc_df["close"].resample("1D").last().dropna()
    ema5 = btc_daily.ewm(span=5).mean()
    ema40 = btc_daily.ewm(span=40).mean()
    signal = (ema5 > ema40).astype(int) * 2 - 1
    btc_ret = btc_daily.pct_change()
    vol_30d = btc_ret.rolling(30).std() * np.sqrt(365)
    target_lev = (0.20 / vol_30d).clip(upper=2.0)
    h009_ret = signal.shift(1) * btc_ret * target_lev.shift(1)
    h009_ret = h009_ret.dropna()

    # H-011: BTC funding rate arb (5x)
    btc_funding = pd.read_parquet(DATA_DIR / "BTC_USDT_USDT_funding.parquet")
    fund_rate = btc_funding["funding_rate"]
    rolling27 = fund_rate.rolling(27).mean()
    in_position = rolling27 > 0

    # Convert 8h funding returns to daily
    fund_daily_pnl = fund_rate.copy()
    fund_daily_pnl[~in_position] = 0  # zero when OUT
    fund_daily_pnl = fund_daily_pnl * 5.0  # 5x leverage
    h011_ret = fund_daily_pnl.resample("1D").sum()

    # H-011 position status (daily)
    h011_in = in_position.resample("1D").last().fillna(False)

    # H-012: Cross-sectional momentum
    prices = {}
    for name in ASSETS_NAMES:
        f = DATA_DIR / f"{name}_USDT_1h.parquet"
        if f.exists():
            df = pd.read_parquet(f)
            prices[name] = df["close"].resample("1D").last()
    price_df = pd.DataFrame(prices).dropna()

    lookback = 60
    rebal_period = 5
    n_long = 4
    n_short = 4
    returns = price_df.pct_change()
    mom = price_df.pct_change(lookback)

    h012_returns = []
    weights = {}
    for i in range(lookback + 1, len(price_df)):
        if (i - lookback - 1) % rebal_period == 0:
            rank_vals = mom.iloc[i - 1].dropna()
            if len(rank_vals) >= n_long + n_short:
                longs = rank_vals.nlargest(n_long).index
                shorts = rank_vals.nsmallest(n_short).index
                weights = {}
                for a in longs:
                    weights[a] = 1.0 / n_long
                for a in shorts:
                    weights[a] = -1.0 / n_short

        port_ret = 0
        day_ret = returns.iloc[i]
        for asset, w in weights.items():
            if asset in day_ret.index and not np.isnan(day_ret[asset]):
                port_ret += w * day_ret[asset]
        h012_returns.append(port_ret)

    h012_ret = pd.Series(h012_returns,
                         index=price_df.index[lookback + 1:lookback + 1 + len(h012_returns)])

    # Align all series
    common_idx = h009_ret.index.intersection(h011_ret.index).intersection(h012_ret.index)
    h009_ret = h009_ret.loc[common_idx]
    h011_ret = h011_ret.loc[common_idx]
    h012_ret = h012_ret.loc[common_idx]
    h011_in_aligned = h011_in.reindex(common_idx).fillna(False)

    return h009_ret, h011_ret, h012_ret, h011_in_aligned


def evaluate_portfolio(port_ret: pd.Series, label: str, verbose: bool = True) -> dict:
    """Compute portfolio metrics."""
    ann = port_ret.mean() * 365
    vol = port_ret.std() * np.sqrt(365)
    sharpe = ann / vol if vol > 0 else 0
    eq = (1 + port_ret).cumprod()
    max_dd = ((eq - eq.cummax()) / eq.cummax()).min()
    total_ret = eq.iloc[-1] - 1
    days = len(port_ret)

    if verbose:
        print(f"  {label:<50s} Ann {ann:>+6.1%} | DD {max_dd:>6.2%} | "
              f"Sharpe {sharpe:>6.2f} | Total {total_ret:>+6.1%}")

    return {
        "label": label,
        "ann_return": ann,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "total_return": total_ret,
        "days": days,
    }


def main():
    print("=== Dynamic Portfolio Allocation Research ===\n")

    h009, h011, h012, h011_in = build_strategy_daily_returns()
    print(f"Period: {h009.index.min().date()} to {h009.index.max().date()} ({len(h009)} days)")
    print(f"H-011 in market: {h011_in.mean():.1%} of days\n")

    # ── Full period analysis ────────────────────────────────────────
    print("=== FULL PERIOD ===")

    configs = [
        ("Static 20/60/20 (current)", 0.20, 0.60, 0.20, 0.20, 0.60, 0.20),
        ("Dynamic 50/0/50 when OUT",  0.20, 0.60, 0.20, 0.50, 0.00, 0.50),
        ("Dynamic 40/0/60 when OUT",  0.20, 0.60, 0.20, 0.40, 0.00, 0.60),
        ("Dynamic 30/0/70 when OUT",  0.20, 0.60, 0.20, 0.30, 0.00, 0.70),
        ("Static 50/0/50 (no funding)", 0.50, 0.00, 0.50, 0.50, 0.00, 0.50),
        ("Static 40/0/60",            0.40, 0.00, 0.60, 0.40, 0.00, 0.60),
        ("Static 33/34/33",           0.33, 0.34, 0.33, 0.33, 0.34, 0.33),
    ]

    results_full = []
    for name, w9_in, w11_in, w12_in, w9_out, w11_out, w12_out in configs:
        # Dynamic weights based on H-011 position status
        w_h009 = h011_in.map({True: w9_in, False: w9_out}).astype(float)
        w_h011 = h011_in.map({True: w11_in, False: w11_out}).astype(float)
        w_h012 = h011_in.map({True: w12_in, False: w12_out}).astype(float)

        port_ret = w_h009 * h009 + w_h011 * h011 + w_h012 * h012
        r = evaluate_portfolio(port_ret, name)
        results_full.append(r)

    # ── Recent 180d ─────────────────────────────────────────────────
    print(f"\n=== RECENT 180 DAYS ===")
    cutoff = h009.index[-180]
    h009_r = h009[cutoff:]
    h011_r = h011[cutoff:]
    h012_r = h012[cutoff:]
    h011_in_r = h011_in[cutoff:]

    print(f"Period: {h009_r.index.min().date()} to {h009_r.index.max().date()}")
    print(f"H-011 in market: {h011_in_r.mean():.1%}\n")

    results_recent = []
    for name, w9_in, w11_in, w12_in, w9_out, w11_out, w12_out in configs:
        w_h009 = h011_in_r.map({True: w9_in, False: w9_out}).astype(float)
        w_h011 = h011_in_r.map({True: w11_in, False: w11_out}).astype(float)
        w_h012 = h011_in_r.map({True: w12_in, False: w12_out}).astype(float)

        port_ret = w_h009 * h009_r + w_h011 * h011_r + w_h012 * h012_r
        r = evaluate_portfolio(port_ret, name)
        results_recent.append(r)

    # ── Recent 90d ──────────────────────────────────────────────────
    print(f"\n=== RECENT 90 DAYS ===")
    cutoff90 = h009.index[-90]
    h009_r90 = h009[cutoff90:]
    h011_r90 = h011[cutoff90:]
    h012_r90 = h012[cutoff90:]
    h011_in_r90 = h011_in[cutoff90:]

    print(f"Period: {h009_r90.index.min().date()} to {h009_r90.index.max().date()}")
    print(f"H-011 in market: {h011_in_r90.mean():.1%}\n")

    for name, w9_in, w11_in, w12_in, w9_out, w11_out, w12_out in configs:
        w_h009 = h011_in_r90.map({True: w9_in, False: w9_out}).astype(float)
        w_h011 = h011_in_r90.map({True: w11_in, False: w11_out}).astype(float)
        w_h012 = h011_in_r90.map({True: w12_in, False: w12_out}).astype(float)

        port_ret = w_h009 * h009_r90 + w_h011 * h011_r90 + w_h012 * h012_r90
        evaluate_portfolio(port_ret, name)

    # ── Walk-forward validation of dynamic allocation ───────────────
    print("\n=== WALK-FORWARD: Dynamic 50/0/50 vs Static 20/60/20 ===")
    fold_size = 90  # 90-day test folds
    n_folds = len(h009) // fold_size

    wf_static = []
    wf_dynamic = []

    for fold in range(n_folds):
        start = fold * fold_size
        end = min(start + fold_size, len(h009))
        idx = h009.index[start:end]

        h009_f = h009.loc[idx]
        h011_f = h011.loc[idx]
        h012_f = h012.loc[idx]
        h011_in_f = h011_in.loc[idx]

        # Static
        port_static = 0.20 * h009_f + 0.60 * h011_f + 0.20 * h012_f
        ann_s = port_static.mean() * 365
        vol_s = port_static.std() * np.sqrt(365)
        sharpe_s = ann_s / vol_s if vol_s > 0 else 0

        # Dynamic
        w9 = h011_in_f.map({True: 0.20, False: 0.50}).astype(float)
        w11 = h011_in_f.map({True: 0.60, False: 0.00}).astype(float)
        w12 = h011_in_f.map({True: 0.20, False: 0.50}).astype(float)
        port_dyn = w9 * h009_f + w11 * h011_f + w12 * h012_f
        ann_d = port_dyn.mean() * 365
        vol_d = port_dyn.std() * np.sqrt(365)
        sharpe_d = ann_d / vol_d if vol_d > 0 else 0

        in_mkt = h011_in_f.mean()

        print(f"  Fold {fold+1} ({idx.min().date()} to {idx.max().date()}): "
              f"Static Sharpe {sharpe_s:>6.2f}, Dynamic Sharpe {sharpe_d:>6.2f}, "
              f"H011 in {in_mkt:.0%}")

        wf_static.append(sharpe_s)
        wf_dynamic.append(sharpe_d)

    print(f"\n  Avg Static  Sharpe: {np.mean(wf_static):.2f} (std {np.std(wf_static):.2f})")
    print(f"  Avg Dynamic Sharpe: {np.mean(wf_dynamic):.2f} (std {np.std(wf_dynamic):.2f})")
    print(f"  Dynamic wins: {sum(d > s for d, s in zip(wf_dynamic, wf_static))}/{len(wf_static)} folds")

    # ── Recommendation ──────────────────────────────────────────────
    print("\n=== RECOMMENDATION ===")
    best_full = max(results_full, key=lambda r: r["sharpe"])
    best_recent = max(results_recent, key=lambda r: r["sharpe"])
    print(f"  Best full-period:   {best_full['label']} (Sharpe {best_full['sharpe']:.2f})")
    print(f"  Best recent 180d:   {best_recent['label']} (Sharpe {best_recent['sharpe']:.2f})")


if __name__ == "__main__":
    main()
