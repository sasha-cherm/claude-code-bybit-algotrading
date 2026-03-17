"""
Quick walk-forward validation for H-015 RSI Mean Reversion.
Key question: does the negative correlation with H-009 hold OOS?
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import sharpe_ratio
from strategies.daily_trend_multi_asset.strategy import (
    generate_signals,
    resample_to_daily,
)


def compute_rsi_signals(prices, rsi_period, oversold, overbought, exit_level):
    """Generate RSI mean-reversion signals."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    signals = pd.Series(0, index=prices.index)
    position = 0
    for i in range(rsi_period + 10, len(prices)):
        r = rsi.iloc[i]
        if np.isnan(r):
            continue
        if position == 0:
            if r < oversold:
                position = 1
            elif r > overbought:
                position = -1
        elif position == 1:
            if r > exit_level:
                position = 0
            elif r > overbought:
                position = -1
        elif position == -1:
            if r < (100 - exit_level):
                position = 0
            elif r < oversold:
                position = 1
        signals.iloc[i] = position
    return signals


def backtest_signals(prices, signals):
    """Simple returns from signal series, with fees."""
    strat_ret = signals.shift(1) * prices.pct_change()
    # Deduct fees on trade days
    trade_days = (signals.diff() != 0) & (signals != 0)
    strat_ret[trade_days] -= 0.002  # 0.2% round-trip fee
    return strat_ret.dropna()


def main():
    print("=== H-015 RSI Mean Reversion Walk-Forward Validation ===\n")

    df_1h = fetch_and_cache("BTC/USDT", "1h", limit_days=730)
    daily = resample_to_daily(df_1h)
    prices = daily["close"]
    print(f"Data: {prices.index[0].date()} to {prices.index[-1].date()}, {len(prices)} bars\n")

    # Fixed 70/30 split
    split_idx = int(len(prices) * 0.7)
    train_p = prices.iloc[:split_idx]
    test_p = prices.iloc[split_idx:]

    print(f"Train: {train_p.index[0].date()} to {train_p.index[-1].date()} ({len(train_p)} bars)")
    print(f"Test:  {test_p.index[0].date()} to {test_p.index[-1].date()} ({len(test_p)} bars)\n")

    # Parameter sweep on training
    best_sharpe = -999
    best_params = None
    all_results = []

    for rsi_period in [5, 7, 10, 14, 21]:
        for oversold in [20, 25, 30, 35, 40]:
            overbought = 100 - oversold
            for exit_level in [40, 45, 50, 55, 60]:
                if exit_level <= oversold:
                    continue
                signals = compute_rsi_signals(train_p, rsi_period, oversold, overbought, exit_level)
                ret = backtest_signals(train_p, signals)
                if len(ret) < 30:
                    continue
                s = sharpe_ratio(ret, periods_per_year=365)
                all_results.append({
                    "rsi_period": rsi_period, "oversold": oversold,
                    "exit": exit_level, "sharpe": s,
                })
                if s > best_sharpe:
                    best_sharpe = s
                    best_params = (rsi_period, oversold, overbought, exit_level)

    df_results = pd.DataFrame(all_results).sort_values("sharpe", ascending=False)
    positive = (df_results["sharpe"] > 0).sum()
    print(f"Tested {len(df_results)} param combos on training data")
    print(f"Positive Sharpe: {positive}/{len(df_results)} ({positive/len(df_results):.0%})")
    print(f"Best IS: RSI({best_params[0]}) OS={best_params[1]} OB={best_params[2]} "
          f"exit={best_params[3]} → Sharpe={best_sharpe:.3f}\n")

    # OOS test with best params
    signals_oos = compute_rsi_signals(test_p, *best_params)
    ret_oos = backtest_signals(test_p, signals_oos)
    oos_sharpe = sharpe_ratio(ret_oos, periods_per_year=365)
    eq_oos = 10000 * (1 + ret_oos).cumprod()
    oos_ann = (eq_oos.iloc[-1] / eq_oos.iloc[0]) ** (365 / len(eq_oos)) - 1
    oos_dd = ((eq_oos.cummax() - eq_oos) / eq_oos.cummax()).max()
    print(f"OOS Best: Sharpe={oos_sharpe:.3f}  Ann={oos_ann:+.1%}  DD={oos_dd:.1%}")

    # OOS with top 5 IS params
    print("\nOOS for top 10 IS params:")
    oos_sharpes = []
    for _, row in df_results.head(10).iterrows():
        rsi_p = int(row["rsi_period"])
        os_lvl = int(row["oversold"])
        ob_lvl = 100 - os_lvl
        ex_lvl = int(row["exit"])
        sig = compute_rsi_signals(test_p, rsi_p, os_lvl, ob_lvl, ex_lvl)
        ret = backtest_signals(test_p, sig)
        s = sharpe_ratio(ret, periods_per_year=365)
        oos_sharpes.append(s)
        eq = 10000 * (1 + ret).cumprod()
        ann = (eq.iloc[-1] / eq.iloc[0]) ** (365 / len(eq)) - 1
        print(f"  RSI({rsi_p}) OS={os_lvl} exit={ex_lvl} | IS={row['sharpe']:.2f} → OOS={s:.2f}  Ann={ann:+.1%}")

    print(f"\nMean OOS Sharpe (top 10): {np.mean(oos_sharpes):.3f}")

    # Rolling walk-forward
    print("\n" + "=" * 60)
    print("ROLLING WALK-FORWARD (12mo train, 3mo test)")
    print("=" * 60)

    train_window = 365
    test_window = 90
    step = 90

    fold_results = []
    start = 0
    fold = 0

    while start + train_window + test_window <= len(prices):
        train_end = start + train_window
        test_end = min(train_end + test_window, len(prices))

        tr_p = prices.iloc[start:train_end]
        te_p = prices.iloc[train_end:test_end]

        if len(te_p) < 30:
            break

        # Find best params on training
        best_s = -999
        best_pr = None
        for rsi_period in [5, 7, 10, 14, 21]:
            for oversold in [20, 25, 30, 35, 40]:
                overbought = 100 - oversold
                for exit_level in [40, 45, 50, 55]:
                    if exit_level <= oversold:
                        continue
                    sig = compute_rsi_signals(tr_p, rsi_period, oversold, overbought, exit_level)
                    ret = backtest_signals(tr_p, sig)
                    if len(ret) < 30:
                        continue
                    s = sharpe_ratio(ret, periods_per_year=365)
                    if s > best_s:
                        best_s = s
                        best_pr = (rsi_period, oversold, overbought, exit_level)

        # OOS
        sig_oos = compute_rsi_signals(te_p, *best_pr)
        ret_oos = backtest_signals(te_p, sig_oos)
        oos_s = sharpe_ratio(ret_oos, periods_per_year=365)
        eq = 10000 * (1 + ret_oos).cumprod()
        ann = (eq.iloc[-1] / eq.iloc[0]) ** (365 / len(eq)) - 1

        fold_results.append({"fold": fold, "is_sharpe": best_s, "oos_sharpe": oos_s, "oos_ann": ann})
        print(f"  Fold {fold}: IS={best_s:.2f} → OOS={oos_s:.2f}  Ann={ann:+.1%}  "
              f"params=RSI({best_pr[0]}) OS={best_pr[1]} exit={best_pr[3]}")

        start += step
        fold += 1

    if fold_results:
        oos_s = [f["oos_sharpe"] for f in fold_results]
        print(f"\nRolling WF Summary:")
        print(f"  Folds: {len(fold_results)}")
        print(f"  Mean OOS Sharpe: {np.mean(oos_s):.3f}")
        print(f"  Positive folds: {sum(1 for s in oos_s if s > 0)}/{len(oos_s)}")

    # OOS Correlation analysis
    print("\n" + "=" * 60)
    print("OOS CORRELATION WITH H-009")
    print("=" * 60)

    # Use test period for correlation (OOS)
    if best_params:
        sig_rsi = compute_rsi_signals(test_p, *best_params)
        ret_rsi = backtest_signals(test_p, sig_rsi)

        sig_ema = generate_signals(test_p, 5, 40)
        ret_ema = (sig_ema.shift(1) * test_p.pct_change()).dropna()

        common = ret_rsi.index.intersection(ret_ema.index)
        corr = ret_rsi.loc[common].corr(ret_ema.loc[common])
        print(f"OOS Correlation (H-015 vs H-009): {corr:.3f}")

        # What if we combine them?
        for w_rsi in [0.2, 0.3, 0.4, 0.5]:
            w_ema = 1 - w_rsi
            port = w_ema * ret_ema.loc[common] + w_rsi * ret_rsi.loc[common]
            port_sharpe = sharpe_ratio(port, periods_per_year=365)
            eq = 10000 * (1 + port).cumprod()
            ann = (eq.iloc[-1] / eq.iloc[0]) ** (365 / len(eq)) - 1
            dd = ((eq.cummax() - eq) / eq.cummax()).max()
            print(f"  H-009 {w_ema:.0%} + H-015 {w_rsi:.0%}: Sharpe={port_sharpe:.2f}  "
                  f"Ann={ann:+.1%}  DD={dd:.1%}")

        # H-009 alone OOS for comparison
        eq_ema = 10000 * (1 + ret_ema.loc[common]).cumprod()
        sharpe_ema = sharpe_ratio(ret_ema.loc[common], periods_per_year=365)
        ann_ema = (eq_ema.iloc[-1] / eq_ema.iloc[0]) ** (365 / len(eq_ema)) - 1
        dd_ema = ((eq_ema.cummax() - eq_ema) / eq_ema.cummax()).max()
        print(f"\n  H-009 alone OOS: Sharpe={sharpe_ema:.2f}  Ann={ann_ema:+.1%}  DD={dd_ema:.1%}")


if __name__ == "__main__":
    main()
