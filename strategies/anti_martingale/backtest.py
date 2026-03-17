"""
H-014 Anti-Martingale Strategy Backtest

Strategy logic:
- Entry: price makes a new `entry_lookback`-day high → buy initial position
- Add-on: price rises `add_pct` from last add-on price → add to position
- Trail stop: price drops `trail_pct` from peak since first entry → sell all
- After exit, wait for next entry trigger (new high breakout)

This is a momentum/pyramiding strategy: small position at start, grows
only in strong trends. Risk is controlled by the trailing stop.

Supports long-only (spot) and long+short (futures) modes.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.data_fetch import fetch_and_cache
from lib.metrics import summary, returns_from_equity
from strategies.daily_trend_multi_asset.strategy import resample_to_daily


def run_anti_martingale_backtest(
    prices: pd.Series,
    entry_lookback: int = 20,
    add_pct: float = 0.05,
    trail_pct: float = 0.10,
    initial_alloc: float = 0.10,
    add_alloc: float = 0.10,
    max_adds: int = 8,
    cooldown_bars: int = 5,
    fee_rate: float = 0.001,
    slippage_bps: float = 2.0,
    initial_capital: float = 10_000.0,
    mode: str = "long_only",  # "long_only" or "long_short"
) -> dict:
    """
    Event-driven anti-martingale backtest.

    Args:
        prices: Series of close prices (daily or hourly)
        entry_lookback: N-bar high breakout for entry
        add_pct: price rise % from last add to trigger new add
        trail_pct: % drop from peak to trigger exit
        initial_alloc: fraction of capital for first buy
        add_alloc: fraction of capital per add-on
        max_adds: maximum number of add-ons (total buys = 1 + max_adds)
        cooldown_bars: bars to wait after exit before new entry
        fee_rate: trading fee per side
        slippage_bps: slippage in basis points
        initial_capital: starting capital
        mode: "long_only" or "long_short"

    Returns:
        dict with performance metrics + trade log
    """
    n = len(prices)
    slippage = slippage_bps / 10_000

    capital = initial_capital
    equity = np.full(n, initial_capital)

    # Position state
    position = 0  # 1=long, -1=short, 0=flat
    adds_done = 0
    last_add_price = 0.0
    peak_since_entry = 0.0
    trough_since_entry = float("inf")
    total_size = 0.0
    total_cost = 0.0  # total cost basis
    cooldown_remaining = 0

    trades = []
    add_log = []  # log of all add-ons for analysis

    for i in range(entry_lookback, n):
        price = prices.iloc[i]

        # Mark-to-market
        if position == 1:
            unrealized = total_size * (price - total_cost / total_size) if total_size > 0 else 0
            equity[i] = capital + unrealized
        elif position == -1:
            avg_entry = total_cost / abs(total_size) if total_size != 0 else price
            unrealized = abs(total_size) * (avg_entry - price)
            equity[i] = capital + unrealized
        else:
            equity[i] = capital

        if cooldown_remaining > 0:
            cooldown_remaining -= 1
            continue

        # ── LONG side ──────────────────────────────────────────────
        if position == 0:
            # Check for entry: new N-bar high
            lookback_high = prices.iloc[i - entry_lookback:i].max()
            if price > lookback_high:
                # Enter long
                alloc = equity[i] * initial_alloc
                exec_price = price * (1 + slippage)
                size = alloc / exec_price
                fee = fee_rate * alloc
                capital -= fee

                position = 1
                total_size = size
                total_cost = size * exec_price
                last_add_price = exec_price
                peak_since_entry = price
                adds_done = 0

                add_log.append({
                    "type": "entry","bar": i, "price": round(exec_price, 2),
                    "size": round(size, 8), "alloc_pct": initial_alloc,
                    "equity": round(equity[i], 2),
                })

            elif mode == "long_short":
                # Check for short entry: new N-bar low
                lookback_low = prices.iloc[i - entry_lookback:i].min()
                if price < lookback_low:
                    alloc = equity[i] * initial_alloc
                    exec_price = price * (1 - slippage)
                    size = alloc / exec_price
                    fee = fee_rate * alloc
                    capital -= fee

                    position = -1
                    total_size = -size
                    total_cost = size * exec_price
                    last_add_price = exec_price
                    trough_since_entry = price
                    adds_done = 0

                    add_log.append({
                        "type": "short_entry", "bar": i, "price": round(exec_price, 2),
                        "size": round(size, 8), "alloc_pct": initial_alloc,
                        "equity": round(equity[i], 2),
                    })

        elif position == 1:
            # Update peak
            if price > peak_since_entry:
                peak_since_entry = price

            # Check trailing stop
            drawdown_from_peak = (peak_since_entry - price) / peak_since_entry
            if drawdown_from_peak >= trail_pct:
                # EXIT: trailing stop hit
                exec_price = price * (1 - slippage)
                proceeds = total_size * exec_price
                fee = fee_rate * proceeds
                avg_entry = total_cost / total_size
                pnl = total_size * (exec_price - avg_entry) - fee
                capital += total_size * (exec_price - avg_entry) - fee

                trades.append({
                    "entry_bar": add_log[-adds_done - 1]["bar"] if add_log else i,
                    "exit_bar": i,
                    "direction": "long",
                    "avg_entry": round(avg_entry, 2),
                    "exit_price": round(exec_price, 2),
                    "adds": adds_done,
                    "peak": round(peak_since_entry, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl / total_cost, 4) if total_cost > 0 else 0,
                })

                position = 0
                total_size = 0.0
                total_cost = 0.0
                cooldown_remaining = cooldown_bars
                equity[i] = capital
                continue

            # Check for add-on
            price_gain_from_last = (price - last_add_price) / last_add_price
            if price_gain_from_last >= add_pct and adds_done < max_adds:
                alloc = equity[i] * add_alloc
                exec_price_add = price * (1 + slippage)
                size_add = alloc / exec_price_add
                fee = fee_rate * alloc
                capital -= fee

                total_size += size_add
                total_cost += size_add * exec_price_add
                last_add_price = price
                adds_done += 1

                add_log.append({
                    "type": f"add_{adds_done}", "bar": i,
                    "price": round(exec_price_add, 2),
                    "size": round(size_add, 8), "alloc_pct": add_alloc,
                    "total_alloc": round(total_cost / equity[i], 2),
                    "equity": round(equity[i], 2),
                })

        elif position == -1:
            # Update trough
            if price < trough_since_entry:
                trough_since_entry = price

            # Check trailing stop (for shorts, price rising from trough)
            rise_from_trough = (price - trough_since_entry) / trough_since_entry
            if rise_from_trough >= trail_pct:
                # EXIT short
                exec_price = price * (1 + slippage)
                size_abs = abs(total_size)
                avg_entry = total_cost / size_abs
                pnl = size_abs * (avg_entry - exec_price)
                fee = fee_rate * size_abs * exec_price
                pnl -= fee
                capital += pnl

                trades.append({
                    "entry_bar": add_log[-adds_done - 1]["bar"] if add_log else i,
                    "exit_bar": i,
                    "direction": "short",
                    "avg_entry": round(avg_entry, 2),
                    "exit_price": round(exec_price, 2),
                    "adds": adds_done,
                    "trough": round(trough_since_entry, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl / total_cost, 4) if total_cost > 0 else 0,
                })

                position = 0
                total_size = 0.0
                total_cost = 0.0
                cooldown_remaining = cooldown_bars
                equity[i] = capital
                continue

            # Add to short on further drop
            price_drop_from_last = (last_add_price - price) / last_add_price
            if price_drop_from_last >= add_pct and adds_done < max_adds:
                alloc = equity[i] * add_alloc
                exec_price_add = price * (1 - slippage)
                size_add = alloc / exec_price_add
                fee = fee_rate * alloc
                capital -= fee

                total_size -= size_add
                total_cost += size_add * exec_price_add
                last_add_price = price
                adds_done += 1

                add_log.append({
                    "type": f"short_add_{adds_done}", "bar": i,
                    "price": round(exec_price_add, 2),
                    "size": round(size_add, 8),
                })

    # Close any open position at end
    if position != 0:
        price = prices.iloc[-1]
        if position == 1:
            exec_price = price * (1 - slippage)
            avg_entry = total_cost / total_size
            pnl = total_size * (exec_price - avg_entry)
            fee = fee_rate * total_size * exec_price
            pnl -= fee
            capital += pnl
        else:
            exec_price = price * (1 + slippage)
            size_abs = abs(total_size)
            avg_entry = total_cost / size_abs
            pnl = size_abs * (avg_entry - exec_price)
            fee = fee_rate * size_abs * exec_price
            pnl -= fee
            capital += pnl

        trades.append({
            "entry_bar": add_log[-1]["bar"] if add_log else n - 1,
            "exit_bar": n - 1,
            "direction": "long" if position == 1 else "short",
            "avg_entry": round(avg_entry, 2),
            "exit_price": round(exec_price, 2),
            "adds": adds_done,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl / total_cost, 4) if total_cost > 0 else 0,
        })
        equity[-1] = capital

    # Compute metrics
    equity_series = pd.Series(equity, index=prices.index)

    # Determine periods_per_year
    if len(prices) > 1:
        freq_hours = (prices.index[1] - prices.index[0]).total_seconds() / 3600
        periods_per_year = 8760 / freq_hours
    else:
        periods_per_year = 365

    trade_pnls = pd.Series([t["pnl"] for t in trades]) if trades else pd.Series(dtype=float)
    metrics = summary(equity_series, trade_pnls, periods_per_year)
    metrics["n_adds_avg"] = np.mean([t["adds"] for t in trades]) if trades else 0
    metrics["n_adds_max"] = max([t["adds"] for t in trades]) if trades else 0
    metrics["mode"] = mode

    return {
        "metrics": metrics,
        "trades": trades,
        "add_log": add_log,
        "equity": equity_series,
    }


def run_parameter_sweep():
    """Run backtest across parameter combinations on BTC daily data."""
    print("=== H-014 Anti-Martingale Parameter Sweep ===\n")

    # Load BTC data
    print("Loading BTC/USDT 1h data...")
    df_1h = fetch_and_cache("BTC/USDT", "1h", limit_days=730)
    daily = resample_to_daily(df_1h)
    prices = daily["close"]
    print(f"Data: {prices.index[0].date()} to {prices.index[-1].date()}, {len(prices)} bars")
    print(f"BTC: ${prices.iloc[0]:,.0f} → ${prices.iloc[-1]:,.0f} ({(prices.iloc[-1]/prices.iloc[0]-1):+.1%})\n")

    # Parameter grid
    param_sets = []

    # Vary entry lookback
    for entry_lb in [10, 20, 40]:
        # Vary add-on interval
        for add_pct in [0.03, 0.05, 0.08, 0.10]:
            # Vary trailing stop
            for trail_pct in [0.05, 0.08, 0.10, 0.15]:
                # Vary allocation sizes
                for init_alloc in [0.10, 0.15, 0.20]:
                    param_sets.append({
                        "entry_lookback": entry_lb,
                        "add_pct": add_pct,
                        "trail_pct": trail_pct,
                        "initial_alloc": init_alloc,
                        "add_alloc": init_alloc,  # same as initial
                        "max_adds": 8,
                    })

    print(f"Testing {len(param_sets)} parameter combinations (long-only)...\n")

    results = []
    for i, params in enumerate(param_sets):
        result = run_anti_martingale_backtest(prices, mode="long_only", **params)
        m = result["metrics"]
        results.append({
            **params,
            "sharpe": m["sharpe_ratio"],
            "annual_ret": m["annual_return"],
            "max_dd": m["max_drawdown"],
            "n_trades": m.get("n_trades", 0),
            "win_rate": m.get("win_rate", 0),
            "avg_adds": m.get("n_adds_avg", 0),
            "calmar": m.get("calmar_ratio", 0),
            "total_ret": m["total_return"],
        })

    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values("sharpe", ascending=False)

    # Print top 10
    print("=" * 100)
    print("TOP 10 LONG-ONLY PARAMETER SETS (by Sharpe)")
    print("=" * 100)
    for idx, row in df_results.head(10).iterrows():
        print(f"  entry_lb={int(row['entry_lookback']):2d}  add%={row['add_pct']:.2f}  "
              f"trail%={row['trail_pct']:.2f}  alloc={row['initial_alloc']:.2f}  |  "
              f"Sharpe={row['sharpe']:.2f}  Ann={row['annual_ret']:+.1%}  "
              f"DD={row['max_dd']:.1%}  Trades={int(row['n_trades'])}  "
              f"WR={row['win_rate']:.0%}  AvgAdds={row['avg_adds']:.1f}")

    # Summary statistics
    positive_sharpe = (df_results["sharpe"] > 0).sum()
    print(f"\nPositive Sharpe: {positive_sharpe}/{len(df_results)} ({positive_sharpe/len(df_results):.0%})")
    print(f"Mean Sharpe: {df_results['sharpe'].mean():.3f}")
    print(f"Median Sharpe: {df_results['sharpe'].median():.3f}")

    # Bottom 5
    print(f"\nBOTTOM 5:")
    for idx, row in df_results.tail(5).iterrows():
        print(f"  entry_lb={int(row['entry_lookback']):2d}  add%={row['add_pct']:.2f}  "
              f"trail%={row['trail_pct']:.2f}  alloc={row['initial_alloc']:.2f}  |  "
              f"Sharpe={row['sharpe']:.2f}  Ann={row['annual_ret']:+.1%}  DD={row['max_dd']:.1%}")

    # Now test long_short mode for the top 5 params
    print("\n" + "=" * 100)
    print("LONG+SHORT MODE (top 5 long-only params)")
    print("=" * 100)
    for idx, row in df_results.head(5).iterrows():
        params = {
            "entry_lookback": int(row["entry_lookback"]),
            "add_pct": row["add_pct"],
            "trail_pct": row["trail_pct"],
            "initial_alloc": row["initial_alloc"],
            "add_alloc": row["initial_alloc"],
            "max_adds": 8,
        }
        result = run_anti_martingale_backtest(prices, mode="long_short", **params)
        m = result["metrics"]
        print(f"  entry_lb={params['entry_lookback']:2d}  add%={params['add_pct']:.2f}  "
              f"trail%={params['trail_pct']:.2f}  alloc={params['initial_alloc']:.2f}  |  "
              f"Sharpe={m['sharpe_ratio']:.2f}  Ann={m['annual_return']:+.1%}  "
              f"DD={m['max_drawdown']:.1%}  Trades={m.get('n_trades', 0)}  "
              f"WR={m.get('win_rate', 0):.0%}")

    # Multi-asset test: try on SUI, SOL, XRP, ETH
    print("\n" + "=" * 100)
    print("MULTI-ASSET TEST (best params, long-only)")
    print("=" * 100)
    best_params = df_results.iloc[0]
    params = {
        "entry_lookback": int(best_params["entry_lookback"]),
        "add_pct": best_params["add_pct"],
        "trail_pct": best_params["trail_pct"],
        "initial_alloc": best_params["initial_alloc"],
        "add_alloc": best_params["initial_alloc"],
        "max_adds": 8,
    }

    for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "XRP/USDT", "AVAX/USDT",
                "NEAR/USDT", "LINK/USDT", "DOGE/USDT"]:
        try:
            df_1h = fetch_and_cache(sym, "1h", limit_days=730)
            daily = resample_to_daily(df_1h)
            p = daily["close"]
            result = run_anti_martingale_backtest(p, mode="long_only", **params)
            m = result["metrics"]
            print(f"  {sym:12s}: Sharpe={m['sharpe_ratio']:.2f}  Ann={m['annual_return']:+.1%}  "
                  f"DD={m['max_drawdown']:.1%}  Trades={m.get('n_trades', 0)}  "
                  f"WR={m.get('win_rate', 0):.0%}  AvgAdds={m.get('n_adds_avg', 0):.1f}")
        except Exception as e:
            print(f"  {sym:12s}: ERROR: {e}")

    return df_results


if __name__ == "__main__":
    run_parameter_sweep()
