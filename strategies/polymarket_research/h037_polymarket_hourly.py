"""
H-037: Polymarket 1hr BTC UP/DOWN + Intraday Seasonality

Idea: H-036 found statistically persistent hour-of-day patterns in BTC
(train/test corr 0.44, cross-asset corr 0.63). The patterns were untradeable
on Bybit due to fees killing the tiny per-hour edge. But Polymarket offers
1hr BTC UP/DOWN binary markets with a different cost structure.

This script analyzes:
1. Green/red PROBABILITY per hour (not just mean return)
2. Required edge to overcome Polymarket vig
3. Expected profit per bet
4. Simulation of a Polymarket paper trading strategy
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import numpy as np
import pandas as pd
from lib.data_fetch import fetch_and_cache


def analyze_hourly_direction():
    """Analyze green/red probability and magnitude per hour."""
    print("=" * 70)
    print("H-037: POLYMARKET 1HR BTC UP/DOWN SEASONALITY ANALYSIS")
    print("=" * 70)

    # Load BTC hourly data
    btc = fetch_and_cache("BTC/USDT", "1h", limit_days=730)
    btc["return"] = btc["close"].pct_change()
    btc["hour"] = btc.index.hour
    btc["green"] = (btc["return"] > 0).astype(int)
    btc = btc.dropna(subset=["return"])
    print(f"  Data: {len(btc)} hourly bars, {btc.index[0]} to {btc.index[-1]}")

    # Overall baseline
    overall_green_rate = btc["green"].mean()
    print(f"\n  Overall green candle rate: {overall_green_rate:.3f} ({overall_green_rate:.1%})")
    print(f"  Overall mean return: {btc['return'].mean():.6f}")

    # Per-hour analysis
    print(f"\n  {'Hour':>4}  {'Green%':>7}  {'Red%':>6}  {'N':>5}  {'MeanRet':>10}  "
          f"{'Green|Mean':>10}  {'Red|Mean':>10}  {'Edge':>6}  {'Sig':>4}")
    print("  " + "-" * 80)

    hour_stats = []
    for h in range(24):
        mask = btc["hour"] == h
        subset = btc[mask]
        if len(subset) < 100:
            continue

        n = len(subset)
        n_green = subset["green"].sum()
        n_red = n - n_green
        green_rate = n_green / n
        red_rate = n_red / n
        mean_ret = subset["return"].mean()
        green_mean = subset[subset["green"] == 1]["return"].mean() if n_green > 0 else 0
        red_mean = subset[subset["green"] == 0]["return"].mean() if n_red > 0 else 0

        # Edge over 50/50 (what matters for binary betting)
        edge_vs_50 = abs(green_rate - 0.5)

        # Statistical significance: binomial test
        from scipy import stats
        pval = stats.binomtest(n_green, n, 0.5).pvalue
        sig = "***" if pval < 0.01 else "**" if pval < 0.05 else "*" if pval < 0.10 else ""

        hour_stats.append({
            "hour": h,
            "n": n,
            "n_green": n_green,
            "green_rate": green_rate,
            "red_rate": red_rate,
            "mean_ret": mean_ret,
            "green_mean": green_mean,
            "red_mean": red_mean,
            "edge_vs_50": edge_vs_50,
            "pval": pval,
            "direction": "GREEN" if green_rate > 0.5 else "RED"
        })

        print(f"  {h:02d}:00  {green_rate:6.1%}  {red_rate:5.1%}  {n:5d}  "
              f"{mean_ret:10.6f}  {green_mean:10.6f}  {red_mean:10.6f}  "
              f"{edge_vs_50:5.1%}  {sig}")

    df = pd.DataFrame(hour_stats)

    # Train/test split for direction probability
    print("\n\n  TRAIN/TEST VALIDATION OF GREEN PROBABILITY")
    print("  " + "=" * 60)
    n = len(btc)
    split = n // 2
    train = btc.iloc[:split]
    test = btc.iloc[split:]

    print(f"  Train: {len(train)} bars ({train.index[0]} to {train.index[-1]})")
    print(f"  Test:  {len(test)} bars ({test.index[0]} to {test.index[-1]})")

    train_green = train.groupby("hour")["green"].mean()
    test_green = test.groupby("hour")["green"].mean()

    # Correlation of green probability between train/test
    common = train_green.index.intersection(test_green.index)
    prob_corr = train_green.loc[common].corr(test_green.loc[common])
    print(f"\n  Train/Test green probability correlation: {prob_corr:.3f}")

    print(f"\n  {'Hour':>4}  {'Train%':>7}  {'Test%':>7}  {'Consistent?':>12}")
    print("  " + "-" * 40)

    consistent_count = 0
    for h in range(24):
        if h in train_green.index and h in test_green.index:
            t1 = train_green[h]
            t2 = test_green[h]
            consistent = (t1 > 0.5 and t2 > 0.5) or (t1 < 0.5 and t2 < 0.5)
            consistent_count += 1 if consistent else 0
            marker = "YES" if consistent else "NO"
            print(f"  {h:02d}:00  {t1:6.1%}  {t2:6.1%}  {marker:>12}")

    print(f"\n  Consistent direction: {consistent_count}/24 hours "
          f"({consistent_count/24:.0%})")

    # Rolling window stability test
    print("\n\n  ROLLING WINDOW STABILITY OF GREEN RATES")
    print("  " + "=" * 60)
    window_months = [3, 6, 12]
    for wm in window_months:
        window_bars = wm * 30 * 24
        print(f"\n  Window: {wm} months ({window_bars} bars)")

        # Get rolling green rates for top 3 green and top 3 red hours
        top_green = df.nlargest(3, "green_rate")["hour"].values
        top_red = df.nsmallest(3, "green_rate")["hour"].values

        n_windows = (len(btc) - window_bars) // (30 * 24) + 1  # monthly steps
        for hours, label in [(top_green, "GREEN hours"), (top_red, "RED hours")]:
            rates = []
            for start in range(0, len(btc) - window_bars, 30 * 24):
                w = btc.iloc[start:start + window_bars]
                rate = w[w["hour"].isin(hours)]["green"].mean()
                rates.append(rate)
            rates = np.array(rates)
            print(f"    {label} ({list(hours)}): "
                  f"mean={rates.mean():.3f} std={rates.std():.3f} "
                  f"min={rates.min():.3f} max={rates.max():.3f} "
                  f"always>{'.500' if label.startswith('GREEN') else ''}"
                  f"{'YES' if (rates > 0.5).all() else 'NO'}")

    # Polymarket viability analysis
    print("\n\n  POLYMARKET VIABILITY ANALYSIS")
    print("  " + "=" * 60)

    # Polymarket typically takes ~2-5% vig on binary markets
    # If market is priced at 50/50 (0.50 each side), you pay ~0.50 + vig
    # Breakeven: you need P(win) > price / (1 - fee)
    # With Polymarket: ~2% fee on winnings, entry price varies

    print("\n  Polymarket mechanics:")
    print("  - Buy YES (BTC UP) at market price P_yes")
    print("  - If correct: receive $1, profit = $1 - P_yes - fee")
    print("  - If wrong: lose $P_yes")
    print("  - Polymarket fee: ~2% on profit (varies)")
    print("  - Breakeven: P(correct) > P_yes / (1 - fee * (1 - P_yes)/P_yes)")

    # For each viable hour, compute expected profit
    print("\n  Expected profit per $1 bet (assuming market at 50c):")
    print(f"  {'Hour':>4}  {'Dir':>5}  {'P(win)':>7}  {'EV@50c':>8}  {'EV@52c':>8}  {'EV@48c':>8}")
    print("  " + "-" * 50)

    polymarket_fee = 0.02  # 2% on winnings
    viable_hours = []

    for _, row in df.iterrows():
        h = int(row["hour"])
        green_rate = row["green_rate"]

        # If green_rate > 0.5, bet GREEN (buy YES BTC UP)
        # If green_rate < 0.5, bet RED (buy YES BTC DOWN)
        if green_rate > 0.5:
            p_win = green_rate
            direction = "UP"
        else:
            p_win = 1 - green_rate  # probability of red
            direction = "DOWN"

        # EV at different market prices
        for price, label in [(0.50, "50c"), (0.52, "52c"), (0.48, "48c")]:
            if direction == "UP":
                buy_price = price  # buy UP at this price
            else:
                buy_price = price  # buy DOWN at this price

            # Profit if win: (1 - buy_price) * (1 - polymarket_fee)
            # Loss if lose: -buy_price
            win_profit = (1 - buy_price) * (1 - polymarket_fee)
            ev = p_win * win_profit - (1 - p_win) * buy_price

            if label == "50c":
                ev_50 = ev
            elif label == "52c":
                ev_52 = ev
            else:
                ev_48 = ev

        viable = ev_50 > 0
        if viable:
            viable_hours.append({
                "hour": h,
                "direction": direction,
                "p_win": p_win,
                "ev_50": ev_50,
            })

        marker = " <<< VIABLE" if viable else ""
        print(f"  {h:02d}:00  {direction:>5}  {p_win:6.1%}  {ev_50:+7.4f}  "
              f"{ev_52:+7.4f}  {ev_48:+7.4f}{marker}")

    print(f"\n  Viable hours (EV > 0 at 50c): {len(viable_hours)}/24")

    # Simulation
    if viable_hours:
        print("\n\n  SIMULATION: PAPER TRADE ON VIABLE HOURS")
        print("  " + "=" * 60)
        print("  Betting $10 per viable hour, using test period only")
        print("  (out-of-sample simulation)")

        bet_size = 10
        total_bets = 0
        total_profit = 0
        wins = 0
        losses = 0

        for _, row in test.iterrows():
            h = row["hour"]
            ret = row["return"]
            is_green = ret > 0

            # Check if this hour is viable
            viable = [v for v in viable_hours if v["hour"] == h]
            if not viable:
                continue

            v = viable[0]
            total_bets += 1
            buy_price = 0.50  # assume market at 50c

            # Determine if bet wins
            if v["direction"] == "UP":
                won = is_green
            else:
                won = not is_green

            if won:
                profit = (1 - buy_price) * (1 - polymarket_fee)  # net gain
                wins += 1
            else:
                profit = -buy_price  # loss
                losses += 1

            total_profit += profit * bet_size

        if total_bets > 0:
            win_rate = wins / total_bets
            avg_profit = total_profit / total_bets
            daily_bets = total_bets / (len(test) / 24)
            annual_profit_1k = (total_profit / total_bets) * daily_bets * 365 * 1000 / bet_size

            print(f"  Total bets: {total_bets}")
            print(f"  Wins: {wins} ({win_rate:.1%})")
            print(f"  Losses: {losses} ({1-win_rate:.1%})")
            print(f"  Total profit: ${total_profit:.2f} on {total_bets} × ${bet_size} bets")
            print(f"  Avg profit per bet: ${avg_profit:.4f}")
            print(f"  Avg bets per day: {daily_bets:.1f}")
            print(f"  Estimated annual profit per $1k capital: ${annual_profit_1k:.0f}")

    # Focused simulation: only statistically significant hours (p < 0.05)
    sig_hours = [row for _, row in df.iterrows() if row["pval"] < 0.05]
    if sig_hours:
        print("\n\n  SIMULATION 2: SIGNIFICANT HOURS ONLY (p < 0.05)")
        print("  " + "=" * 60)
        sig_hour_list = []
        for row in sig_hours:
            h = int(row["hour"])
            direction = "UP" if row["green_rate"] > 0.5 else "DOWN"
            sig_hour_list.append({"hour": h, "direction": direction, "p_win": max(row["green_rate"], 1 - row["green_rate"])})
            print(f"    {h:02d}:00 → bet {direction} (P(win)={max(row['green_rate'], 1 - row['green_rate']):.1%})")

        bet_size = 10
        total_bets = 0
        total_profit = 0
        wins = 0
        losses = 0

        for _, row in test.iterrows():
            h = row["hour"]
            ret = row["return"]
            is_green = ret > 0

            sig = [s for s in sig_hour_list if s["hour"] == h]
            if not sig:
                continue

            s = sig[0]
            total_bets += 1
            buy_price = 0.50

            if s["direction"] == "UP":
                won = is_green
            else:
                won = not is_green

            if won:
                profit = (1 - buy_price) * (1 - polymarket_fee)
                wins += 1
            else:
                profit = -buy_price
                losses += 1

            total_profit += profit * bet_size

        if total_bets > 0:
            win_rate = wins / total_bets
            avg_profit = total_profit / total_bets
            daily_bets = total_bets / (len(test) / 24)
            annual_profit_1k = (total_profit / total_bets) * daily_bets * 365 * 1000 / bet_size

            print(f"\n  Total bets: {total_bets}")
            print(f"  Wins: {wins} ({win_rate:.1%})")
            print(f"  Losses: {losses} ({1-win_rate:.1%})")
            print(f"  Total profit: ${total_profit:.2f} on {total_bets} × ${bet_size} bets")
            print(f"  Avg profit per bet: ${avg_profit:.4f}")
            print(f"  Avg bets per day: {daily_bets:.1f}")
            print(f"  Estimated annual profit per $1k capital: ${annual_profit_1k:.0f}")

    # Focused simulation 3: only top 5 strongest hours
    print("\n\n  SIMULATION 3: TOP 5 STRONGEST HOURS ONLY")
    print("  " + "=" * 60)
    strongest = df.nlargest(5, "edge_vs_50")
    strong_list = []
    for _, row in strongest.iterrows():
        h = int(row["hour"])
        direction = "UP" if row["green_rate"] > 0.5 else "DOWN"
        strong_list.append({"hour": h, "direction": direction})
        print(f"    {h:02d}:00 → bet {direction} (P(win)={max(row['green_rate'], 1 - row['green_rate']):.1%}, edge={row['edge_vs_50']:.1%})")

    bet_size = 10
    total_bets = 0
    total_profit = 0
    wins = 0
    losses = 0
    monthly_pnl = {}

    for _, row in test.iterrows():
        h = row["hour"]
        ret = row["return"]
        is_green = ret > 0
        month = row.name.strftime("%Y-%m") if hasattr(row.name, "strftime") else "?"

        sig = [s for s in strong_list if s["hour"] == h]
        if not sig:
            continue

        s = sig[0]
        total_bets += 1
        buy_price = 0.50

        if s["direction"] == "UP":
            won = is_green
        else:
            won = not is_green

        if won:
            profit = (1 - buy_price) * (1 - polymarket_fee)
            wins += 1
        else:
            profit = -buy_price
            losses += 1

        total_profit += profit * bet_size
        monthly_pnl[month] = monthly_pnl.get(month, 0) + profit * bet_size

    if total_bets > 0:
        win_rate = wins / total_bets
        avg_profit = total_profit / total_bets
        daily_bets = total_bets / (len(test) / 24)
        annual_profit_1k = (total_profit / total_bets) * daily_bets * 365 * 1000 / bet_size

        print(f"\n  Total bets: {total_bets}")
        print(f"  Wins: {wins} ({win_rate:.1%})")
        print(f"  Losses: {losses} ({1-win_rate:.1%})")
        print(f"  Total profit: ${total_profit:.2f} on {total_bets} × ${bet_size} bets")
        print(f"  Avg profit per bet: ${avg_profit:.4f}")
        print(f"  Avg bets per day: {daily_bets:.1f}")
        print(f"  Estimated annual profit per $1k capital: ${annual_profit_1k:.0f}")

        print(f"\n  Monthly PnL breakdown:")
        for m in sorted(monthly_pnl.keys()):
            print(f"    {m}: ${monthly_pnl[m]:+.2f}")

    # Summary
    print("\n\n  SUMMARY")
    print("  " + "=" * 60)

    # Find best and worst hours
    best = df.nlargest(3, "green_rate")
    worst = df.nsmallest(3, "green_rate")

    print(f"  Strongest GREEN hours: {', '.join(f'{int(h):02d}:00 ({r:.1%})' for h, r in zip(best['hour'], best['green_rate']))}")
    print(f"  Strongest RED hours:   {', '.join(f'{int(h):02d}:00 ({r:.1%})' for h, r in zip(worst['hour'], worst['green_rate']))}")
    print(f"  Train/test green prob correlation: {prob_corr:.3f}")
    print(f"  Consistent direction hours: {consistent_count}/24")
    print(f"  Viable Polymarket hours (EV>0 @ 50c): {len(viable_hours)}/24")

    # Key caveats
    print("\n  CAVEATS:")
    print("  1. Polymarket 1hr BTC markets may price in seasonality (efficient market)")
    print("  2. Liquidity/slippage on Polymarket hourly markets may be poor")
    print("  3. Market price likely NOT 50/50 — dynamic pricing reduces edge")
    print("  4. No historical Polymarket data to validate — paper trade only")
    print("  5. Edge is SMALL — bankroll management critical")
    print("  6. Polymarket may not offer every hour, or resolution may differ")

    return df, viable_hours


if __name__ == "__main__":
    df, viable = analyze_hourly_direction()
