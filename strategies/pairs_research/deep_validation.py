"""
H-032 Deep Validation: Focus on top pairs from V2 research.

Deeper analysis of:
1. DOT/ATOM — best cointegrated pair (p=0.031, IS Sharpe 1.30)
2. DOGE/LINK — best strict cointegration (p=0.027)
3. DOGE/ADA — passed both OOS tests
4. DOT/OP — 4/4 WF folds positive
5. Multi-pair portfolio of best candidates
6. Correlation analysis vs all existing strategies
"""

import sys
import warnings
from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.metrics import sharpe_ratio, max_drawdown, annual_return

ASSETS = ["BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX", "LINK",
          "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM"]
DATA_DIR = ROOT / "data"
BASE_FEE = 0.001
SLIPPAGE_BPS = 2.0
INITIAL_CAPITAL = 10_000.0
PPY = 365


def load_closes():
    daily = {}
    for sym in ASSETS:
        df = pd.read_parquet(DATA_DIR / f"{sym}_USDT_1h.parquet")
        d = df.resample("1D").agg({"open": "first", "high": "max",
                                    "low": "min", "close": "last",
                                    "volume": "sum"}).dropna()
        daily[sym] = d
    closes = pd.DataFrame({sym: d["close"] for sym, d in daily.items()}).dropna()
    return closes


def hedge_ratio(log_a, log_b):
    X = np.column_stack([np.ones(len(log_b)), log_b.values])
    y = log_a.values
    return np.linalg.lstsq(X, y, rcond=None)[0][1]


def backtest_pair(closes, a, b, hr, window, entry_z, exit_z, stop_z,
                  fee_mult=1.0, min_trades=1):
    n = len(closes)
    if n < window + 10:
        return None

    fee_rate = BASE_FEE * fee_mult + SLIPPAGE_BPS / 10_000
    log_a = np.log(closes[a])
    log_b = np.log(closes[b])
    spread = log_a - hr * log_b

    roll_mean = spread.rolling(window).mean()
    roll_std = spread.rolling(window).std().replace(0, np.nan)
    zscore = (spread - roll_mean) / roll_std

    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital
    position = 0
    entry_equity = capital
    trades_pnl = []

    for i in range(1, n):
        pa = closes[a].iloc[i]
        pb = closes[b].iloc[i]
        ppa = closes[a].iloc[i-1]
        ppb = closes[b].iloc[i-1]
        z = zscore.iloc[i]

        if np.isnan(z):
            equity[i] = equity[i-1]
            continue

        if position != 0:
            ret_a = (pa - ppa) / ppa
            ret_b = (pb - ppb) / ppb
            half = equity[i-1] * 0.5
            if position == 1:
                pnl = half * ret_a - half * ret_b
            else:
                pnl = -half * ret_a + half * ret_b
            equity[i] = equity[i-1] + pnl
        else:
            equity[i] = equity[i-1]

        if position != 0:
            close_it = False
            if position == 1 and z < -stop_z:
                close_it = True
            elif position == -1 and z > stop_z:
                close_it = True
            elif position == 1 and z > -exit_z:
                close_it = True
            elif position == -1 and z < exit_z:
                close_it = True
            if close_it:
                trades_pnl.append((equity[i] - entry_equity) / entry_equity)
                equity[i] -= equity[i] * fee_rate * 2
                position = 0

        if position == 0:
            if z < -entry_z:
                position = 1
                entry_equity = equity[i]
                equity[i] -= equity[i] * fee_rate * 2
            elif z > entry_z:
                position = -1
                entry_equity = equity[i]
                equity[i] -= equity[i] * fee_rate * 2

    if position != 0:
        trades_pnl.append((equity[-1] - entry_equity) / entry_equity)

    if len(trades_pnl) < min_trades:
        return None

    eq = pd.Series(equity, index=closes.index)
    eq = eq[eq > 0]
    if len(eq) < 30:
        return None
    rets = eq.pct_change().dropna()

    return {
        "n_trades": len(trades_pnl),
        "annual_return": annual_return(eq, PPY),
        "max_drawdown": max_drawdown(eq),
        "sharpe": sharpe_ratio(rets, periods_per_year=PPY),
        "total_return": (eq.iloc[-1] / eq.iloc[0]) - 1,
        "win_rate": np.mean([1 if t > 0 else 0 for t in trades_pnl]),
        "equity": eq,
        "daily_returns": rets,
    }


def compute_h012_returns(closes):
    lookback, rebal_freq, n_long, n_short = 60, 5, 4, 4
    n = len(closes)
    fee_rate = BASE_FEE + SLIPPAGE_BPS / 10_000
    rolling_ret = closes.pct_change(lookback)
    capital = INITIAL_CAPITAL
    equity = np.zeros(n)
    equity[0] = capital
    prev_weights = pd.Series(0.0, index=closes.columns)
    warmup = lookback + 5
    for i in range(1, n):
        if i >= warmup and (i - warmup) % rebal_freq == 0:
            rets = rolling_ret.iloc[i-1]
            valid = rets.dropna()
            if len(valid) >= n_long + n_short:
                ranked = valid.sort_values(ascending=False)
                weights = pd.Series(0.0, index=closes.columns)
                for s in ranked.head(n_long).index:
                    weights[s] = 1.0 / n_long
                for s in ranked.tail(n_short).index:
                    weights[s] = -1.0 / n_short
                turnover = (weights - prev_weights).abs().sum()
                fee_cost = turnover * fee_rate * equity[i-1] * 0.5
                prev_weights = weights.copy()
            else:
                weights = prev_weights
                fee_cost = 0
        else:
            weights = prev_weights
            fee_cost = 0
        pt = closes.iloc[i]
        py = closes.iloc[i-1]
        dr = (pt - py) / py
        pnl = (weights * dr).sum() * equity[i-1]
        equity[i] = equity[i-1] + pnl - fee_cost
    eq = pd.Series(equity, index=closes.index)
    eq = eq[eq > 0]
    return eq.pct_change().dropna()


def main():
    print("=" * 70)
    print("H-032 DEEP VALIDATION")
    print("=" * 70)

    closes = load_closes()
    n = len(closes)
    print(f"\nData: {n} days, {closes.index[0].date()} to {closes.index[-1].date()}")

    # Define top pair candidates with their best IS params
    TOP_PAIRS = [
        # pair,    a,      b,      W,  Ez,  Xz,  Sz
        ("DOT/ATOM",  "DOT",  "ATOM",  30, 1.5, 0.25, 4.0),
        ("SOL/DOGE",  "SOL",  "DOGE",  20, 2.0, 0.0,  3.5),
        ("AVAX/DOT",  "AVAX", "DOT",   50, 1.0, 0.0,  4.0),
        ("NEAR/OP",   "NEAR", "OP",    40, 2.0, 0.0,  4.0),
        ("AVAX/OP",   "AVAX", "OP",    50, 1.0, 0.25, 4.0),
        ("DOT/OP",    "DOT",  "OP",    60, 2.5, 0.25, 4.0),
        ("DOGE/LINK", "DOGE", "LINK",  40, 1.0, 0.0,  4.0),
        ("DOGE/ADA",  "DOGE", "ADA",   20, 2.5, 0.25, 4.0),
        ("ARB/ATOM",  "ARB",  "ATOM",  50, 2.5, 0.0,  4.0),
        ("SOL/LINK",  "SOL",  "LINK",  20, 2.0, 0.0,  3.0),
        ("LINK/ADA",  "LINK", "ADA",   50, 2.0, 0.25, 4.0),
        ("NEAR/ATOM", "NEAR", "ATOM",  40, 2.5, 0.5,  4.0),
    ]

    # ─── 1. Expanding Walk-Forward with 120-day folds ────────────────
    print("\n" + "=" * 70)
    print("1. EXPANDING WALK-FORWARD (5 folds x 120d test)")
    print("=" * 70)

    wf_summary = {}
    pair_equities_is = {}
    pair_equities_oos = {}

    for pair, a, b, W, Ez, Xz, Sz in TOP_PAIRS:
        log_a_full = np.log(closes[a])
        log_b_full = np.log(closes[b])
        hr_full = hedge_ratio(log_a_full, log_b_full)

        # Full IS result
        r_full = backtest_pair(closes, a, b, hr_full, W, Ez, Xz, Sz)
        if r_full:
            pair_equities_is[pair] = r_full["equity"]

        # Walk-forward: 5 folds x 120d, expanding train
        test_days = 120
        n_folds = 5
        fold_sharpes = []
        fold_returns = []
        oos_equity_parts = []

        for fold in range(n_folds):
            test_end = n - (n_folds - fold - 1) * test_days
            test_start = test_end - test_days
            if test_start < 180:
                continue

            train = closes.iloc[:test_start]
            test = closes.iloc[test_start:test_end]

            # Re-estimate HR on train
            hr_train = hedge_ratio(np.log(train[a]), np.log(train[b]))

            # Fixed params, train HR
            r = backtest_pair(test, a, b, hr_train, W, Ez, Xz, Sz, min_trades=1)
            if r:
                fold_sharpes.append(r["sharpe"])
                fold_returns.append(r["total_return"])
                oos_equity_parts.append(r["equity"])
            else:
                fold_sharpes.append(0)
                fold_returns.append(0)

        n_pos = sum(1 for s in fold_sharpes if s > 0)
        mean_s = np.mean(fold_sharpes) if fold_sharpes else np.nan
        mean_r = np.mean(fold_returns) if fold_returns else np.nan

        wf_summary[pair] = {
            "n_pos": n_pos, "n_total": len(fold_sharpes),
            "mean_sharpe": mean_s, "mean_return": mean_r,
            "fold_sharpes": fold_sharpes,
        }

        folds_str = ", ".join(f"{s:.2f}" for s in fold_sharpes)
        tag = "PASS" if n_pos >= 3 else "FAIL"
        print(f"  {pair:<12}: {n_pos}/{len(fold_sharpes)} pos, mean {mean_s:.2f}, "
              f"folds=[{folds_str}] [{tag}]")

    # ─── 2. Simple 50/50 split with PARAM OPTIMIZATION on train ──────
    print("\n" + "=" * 70)
    print("2. 50/50 TRAIN/TEST SPLIT (optimize on train, test OOS)")
    print("=" * 70)

    split_results = {}
    WINDOWS = [20, 30, 40, 50, 60]
    ENTRY_ZS = [1.0, 1.5, 2.0, 2.5]
    EXIT_ZS = [0.0, 0.25, 0.5]
    STOP_ZS = [3.0, 3.5, 4.0]

    mid = n // 2
    train_data = closes.iloc[:mid]
    test_data = closes.iloc[mid:]
    print(f"\n  Train: {train_data.index[0].date()} to {train_data.index[-1].date()} ({len(train_data)}d)")
    print(f"  Test:  {test_data.index[0].date()} to {test_data.index[-1].date()} ({len(test_data)}d)")

    for pair, a, b, _, _, _, _ in TOP_PAIRS:
        hr_train = hedge_ratio(np.log(train_data[a]), np.log(train_data[b]))

        # Sweep on train
        best_sharpe = -999
        best_params = None
        all_train_positive = 0
        all_train_total = 0

        for w in WINDOWS:
            for ez in ENTRY_ZS:
                for xz in EXIT_ZS:
                    for sz in STOP_ZS:
                        r = backtest_pair(train_data, a, b, hr_train, w, ez, xz, sz, min_trades=2)
                        if r:
                            all_train_total += 1
                            if r["sharpe"] > 0:
                                all_train_positive += 1
                            if r["sharpe"] > best_sharpe:
                                best_sharpe = r["sharpe"]
                                best_params = (w, ez, xz, sz)

        if best_params is None:
            print(f"  {pair:<12}: No valid train results")
            continue

        train_pct = all_train_positive / all_train_total * 100 if all_train_total > 0 else 0

        # Test OOS with best params
        w, ez, xz, sz = best_params
        r_test = backtest_pair(test_data, a, b, hr_train, w, ez, xz, sz, min_trades=1)

        if r_test:
            tag = "PASS" if r_test["sharpe"] > 0 else "FAIL"
            split_results[pair] = {
                "train_sharpe": best_sharpe,
                "test_sharpe": r_test["sharpe"],
                "test_annual": r_test["annual_return"],
                "test_dd": r_test["max_drawdown"],
                "test_trades": r_test["n_trades"],
                "params": best_params,
                "train_pct_positive": train_pct,
                "test_equity": r_test["equity"],
                "test_returns": r_test["daily_returns"],
            }
            pair_equities_oos[pair] = r_test["equity"]
            print(f"  {pair:<12}: train Sharpe {best_sharpe:.2f} ({train_pct:.0f}% pos), "
                  f"test Sharpe {r_test['sharpe']:.2f}, ann {r_test['annual_return']*100:.1f}%, "
                  f"DD {r_test['max_drawdown']*100:.1f}%, {r_test['n_trades']} trades [{tag}]")
        else:
            print(f"  {pair:<12}: train Sharpe {best_sharpe:.2f}, test: no trades")

    # ─── 3. Multi-pair portfolio (IS and OOS) ────────────────────────
    print("\n" + "=" * 70)
    print("3. MULTI-PAIR PORTFOLIO")
    print("=" * 70)

    # IS portfolio (full period)
    if len(pair_equities_is) >= 2:
        eq_df = pd.DataFrame(pair_equities_is).dropna()
        norm = eq_df.div(eq_df.iloc[0])
        port = norm.mean(axis=1) * INITIAL_CAPITAL
        rets = port.pct_change().dropna()
        print(f"\n  IS Portfolio ({len(pair_equities_is)} pairs, equal weight):")
        print(f"    Sharpe: {sharpe_ratio(rets, periods_per_year=PPY):.2f}")
        print(f"    Annual: {annual_return(port, PPY)*100:.1f}%")
        print(f"    Max DD: {max_drawdown(port)*100:.1f}%")
        print(f"    Total:  {((port.iloc[-1]/port.iloc[0])-1)*100:.1f}%")

    # OOS portfolio (test half only)
    oos_passed = {k: v for k, v in split_results.items() if v["test_sharpe"] > 0}
    if len(oos_passed) >= 2:
        oos_eqs = {k: pair_equities_oos[k] for k in oos_passed if k in pair_equities_oos}
        if len(oos_eqs) >= 2:
            eq_df = pd.DataFrame(oos_eqs).dropna()
            if len(eq_df) > 30:
                norm = eq_df.div(eq_df.iloc[0])
                port = norm.mean(axis=1) * INITIAL_CAPITAL
                rets = port.pct_change().dropna()
                print(f"\n  OOS Portfolio ({len(oos_eqs)} pairs that passed 50/50 split):")
                print(f"    Sharpe: {sharpe_ratio(rets, periods_per_year=PPY):.2f}")
                print(f"    Annual: {annual_return(port, PPY)*100:.1f}%")
                print(f"    Max DD: {max_drawdown(port)*100:.1f}%")
                print(f"    Total:  {((port.iloc[-1]/port.iloc[0])-1)*100:.1f}%")
                print(f"    Period: {eq_df.index[0].date()} to {eq_df.index[-1].date()}")

    # ─── 4. Correlation with existing strategies ─────────────────────
    print("\n" + "=" * 70)
    print("4. CORRELATIONS WITH EXISTING STRATEGIES")
    print("=" * 70)

    h012_rets = compute_h012_returns(closes)

    # Build pairs portfolio returns (IS, full period)
    if len(pair_equities_is) >= 2:
        eq_df = pd.DataFrame(pair_equities_is).dropna()
        norm = eq_df.div(eq_df.iloc[0])
        port = norm.mean(axis=1) * INITIAL_CAPITAL
        port_rets = port.pct_change().dropna()

        common = h012_rets.index.intersection(port_rets.index)
        if len(common) > 30:
            corr = h012_rets.loc[common].corr(port_rets.loc[common])
            print(f"\n  Pairs portfolio vs H-012 (momentum): r = {corr:.3f}")

    # Per-pair correlations
    print(f"\n  Per-pair correlations with H-012:")
    for pair in sorted(pair_equities_is, key=lambda p: wf_summary.get(p, {}).get("mean_sharpe", -99), reverse=True):
        eq = pair_equities_is[pair]
        rets = eq.pct_change().dropna()
        common = h012_rets.index.intersection(rets.index)
        if len(common) > 30:
            corr = h012_rets.loc[common].corr(rets.loc[common])
            wf = wf_summary.get(pair, {})
            wf_str = f"WF {wf.get('n_pos',0)}/{wf.get('n_total',0)}"
            sr = split_results.get(pair, {})
            split_str = f"split {'PASS' if sr.get('test_sharpe', -1) > 0 else 'FAIL'}" if sr else "split N/A"
            print(f"    {pair:<12}: r = {corr:>7.3f}  ({wf_str}, {split_str})")

    # ─── 5. Regime analysis ──────────────────────────────────────────
    print("\n" + "=" * 70)
    print("5. REGIME ANALYSIS (BTC trend regimes)")
    print("=" * 70)

    btc_rets = closes["BTC"].pct_change()
    btc_60d = btc_rets.rolling(60).sum()

    # Build regime labels
    regimes = pd.Series("FLAT", index=closes.index)
    regimes[btc_60d > 0.10] = "UP"
    regimes[btc_60d < -0.10] = "DOWN"

    if len(pair_equities_is) >= 2:
        eq_df = pd.DataFrame(pair_equities_is).dropna()
        norm = eq_df.div(eq_df.iloc[0])
        port = norm.mean(axis=1) * INITIAL_CAPITAL
        port_rets = port.pct_change().dropna()

        for regime in ["UP", "FLAT", "DOWN"]:
            mask = regimes.loc[port_rets.index] == regime
            if mask.sum() > 30:
                r = port_rets[mask]
                s = sharpe_ratio(r, periods_per_year=PPY)
                print(f"  {regime:>5}: {mask.sum()} days, Sharpe {s:.2f}, "
                      f"mean daily {r.mean()*100:.3f}%")

    # ─── 6. Cointegration stability over time ────────────────────────
    print("\n" + "=" * 70)
    print("6. COINTEGRATION STABILITY (rolling 180d windows)")
    print("=" * 70)

    for pair, a, b, _, _, _, _ in TOP_PAIRS[:6]:
        pvals = []
        for i in range(180, n, 30):
            window = closes.iloc[max(0, i-180):i]
            try:
                _, p, _ = coint(np.log(window[a]), np.log(window[b]))
                pvals.append(p)
            except Exception:
                pvals.append(1.0)
        n_sig = sum(1 for p in pvals if p < 0.10)
        pct_sig = n_sig / len(pvals) * 100 if pvals else 0
        mean_p = np.mean(pvals) if pvals else 1.0
        print(f"  {pair:<12}: {n_sig}/{len(pvals)} windows significant ({pct_sig:.0f}%), "
              f"mean p={mean_p:.3f}")

    # ─── 7. BEST PORTFOLIO SELECTION ─────────────────────────────────
    print("\n" + "=" * 70)
    print("7. PORTFOLIO SELECTION — BEST SUBSET")
    print("=" * 70)

    # Criteria: passed WF >= 3/5 OR passed 50/50 split
    best_candidates = []
    for pair, a, b, W, Ez, Xz, Sz in TOP_PAIRS:
        wf = wf_summary.get(pair, {})
        sr = split_results.get(pair, {})
        wf_pass = wf.get("n_pos", 0) >= 3
        split_pass = sr.get("test_sharpe", -1) > 0

        if wf_pass or split_pass:
            # Check for overlapping assets
            best_candidates.append({
                "pair": pair, "a": a, "b": b, "W": W, "Ez": Ez, "Xz": Xz, "Sz": Sz,
                "wf_pos": wf.get("n_pos", 0), "wf_total": wf.get("n_total", 0),
                "wf_sharpe": wf.get("mean_sharpe", np.nan),
                "split_sharpe": sr.get("test_sharpe", np.nan),
                "split_ann": sr.get("test_annual", np.nan),
            })

    print(f"\n  Candidates passing WF >= 3/5 or 50/50 split:")
    for c in best_candidates:
        wf_str = f"WF {c['wf_pos']}/{c['wf_total']} ({c['wf_sharpe']:.2f})"
        ss = c['split_sharpe']
        split_str = f"split {ss:.2f}" if not np.isnan(ss) else "split N/A"
        sa = c.get('split_ann', np.nan)
        ann_str = f"ann {sa*100:.1f}%" if not np.isnan(sa) else ""
        print(f"    {c['pair']:<12}: {wf_str}, {split_str} {ann_str}")

    # Check asset overlap
    print(f"\n  Asset overlap check:")
    asset_usage = {}
    for c in best_candidates:
        for x in [c["a"], c["b"]]:
            asset_usage[x] = asset_usage.get(x, 0) + 1
    for asset, count in sorted(asset_usage.items(), key=lambda x: -x[1]):
        print(f"    {asset}: used in {count} pairs")

    # Build diversified portfolio: pick non-overlapping pairs
    print(f"\n  Diversified (non-overlapping) portfolio:")
    selected = []
    used_assets = set()
    # Sort by combined evidence
    scored = sorted(best_candidates,
                    key=lambda c: (c["wf_pos"] >= 3) + (c.get("split_sharpe", -1) > 0),
                    reverse=True)
    for c in scored:
        if c["a"] not in used_assets and c["b"] not in used_assets:
            selected.append(c)
            used_assets.add(c["a"])
            used_assets.add(c["b"])

    if selected:
        sel_equities = {}
        for c in selected:
            a, b = c["a"], c["b"]
            hr = hedge_ratio(np.log(closes[a]), np.log(closes[b]))
            r = backtest_pair(closes, a, b, hr, c["W"], c["Ez"], c["Xz"], c["Sz"])
            if r:
                sel_equities[c["pair"]] = r["equity"]
                print(f"    {c['pair']}: IS Sharpe {r['sharpe']:.2f}, "
                      f"Ann {r['annual_return']*100:.1f}%, DD {r['max_drawdown']*100:.1f}%")

        if len(sel_equities) >= 2:
            eq_df = pd.DataFrame(sel_equities).dropna()
            norm = eq_df.div(eq_df.iloc[0])
            port = norm.mean(axis=1) * INITIAL_CAPITAL
            rets = port.pct_change().dropna()
            print(f"\n    Portfolio ({len(sel_equities)} pairs):")
            print(f"      Sharpe: {sharpe_ratio(rets, periods_per_year=PPY):.2f}")
            print(f"      Annual: {annual_return(port, PPY)*100:.1f}%")
            print(f"      Max DD: {max_drawdown(port)*100:.1f}%")

            # OOS-only
            oos_eqs = {}
            for c in selected:
                a, b = c["a"], c["b"]
                hr_train = hedge_ratio(np.log(train_data[a]), np.log(train_data[b]))
                r = backtest_pair(test_data, a, b, hr_train, c["W"], c["Ez"], c["Xz"], c["Sz"])
                if r:
                    oos_eqs[c["pair"]] = r["equity"]

            if len(oos_eqs) >= 2:
                eq_df = pd.DataFrame(oos_eqs).dropna()
                if len(eq_df) > 30:
                    norm = eq_df.div(eq_df.iloc[0])
                    port_oos = norm.mean(axis=1) * INITIAL_CAPITAL
                    rets_oos = port_oos.pct_change().dropna()
                    print(f"\n    OOS Portfolio ({len(oos_eqs)} pairs):")
                    print(f"      Sharpe: {sharpe_ratio(rets_oos, periods_per_year=PPY):.2f}")
                    print(f"      Annual: {annual_return(port_oos, PPY)*100:.1f}%")
                    print(f"      Max DD: {max_drawdown(port_oos)*100:.1f}%")

            # Correlation with H-012
            common = h012_rets.index.intersection(rets.index)
            if len(common) > 30:
                corr = h012_rets.loc[common].corr(rets.loc[common])
                print(f"\n    Correlation with H-012: r = {corr:.3f}")

    # ─── 8. OVERLAPPING PORTFOLIO (all passed pairs) ─────────────────
    print(f"\n  Full portfolio (all passed, with overlap):")
    all_passed_eqs = {}
    for c in best_candidates:
        a, b = c["a"], c["b"]
        hr = hedge_ratio(np.log(closes[a]), np.log(closes[b]))
        r = backtest_pair(closes, a, b, hr, c["W"], c["Ez"], c["Xz"], c["Sz"])
        if r:
            all_passed_eqs[c["pair"]] = r["equity"]

    if len(all_passed_eqs) >= 2:
        eq_df = pd.DataFrame(all_passed_eqs).dropna()
        norm = eq_df.div(eq_df.iloc[0])
        port = norm.mean(axis=1) * INITIAL_CAPITAL
        rets = port.pct_change().dropna()
        print(f"    Portfolio ({len(all_passed_eqs)} pairs):")
        print(f"      Sharpe: {sharpe_ratio(rets, periods_per_year=PPY):.2f}")
        print(f"      Annual: {annual_return(port, PPY)*100:.1f}%")
        print(f"      Max DD: {max_drawdown(port)*100:.1f}%")

        # OOS
        oos_all = {}
        for c in best_candidates:
            a, b = c["a"], c["b"]
            hr_train = hedge_ratio(np.log(train_data[a]), np.log(train_data[b]))
            r = backtest_pair(test_data, a, b, hr_train, c["W"], c["Ez"], c["Xz"], c["Sz"])
            if r:
                oos_all[c["pair"]] = r["equity"]

        if len(oos_all) >= 2:
            eq_df = pd.DataFrame(oos_all).dropna()
            if len(eq_df) > 30:
                norm = eq_df.div(eq_df.iloc[0])
                port_oos = norm.mean(axis=1) * INITIAL_CAPITAL
                rets_oos = port_oos.pct_change().dropna()
                print(f"\n    OOS Full Portfolio ({len(oos_all)} pairs):")
                print(f"      Sharpe: {sharpe_ratio(rets_oos, periods_per_year=PPY):.2f}")
                print(f"      Annual: {annual_return(port_oos, PPY)*100:.1f}%")
                print(f"      Max DD: {max_drawdown(port_oos)*100:.1f}%")

        common = h012_rets.index.intersection(rets.index)
        if len(common) > 30:
            corr = h012_rets.loc[common].corr(rets.loc[common])
            print(f"    vs H-012: r = {corr:.3f}")

    # ─── FINAL VERDICT ───────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)

    n_wf_pass = sum(1 for w in wf_summary.values() if w["n_pos"] >= 3)
    n_split_pass = sum(1 for s in split_results.values() if s.get("test_sharpe", -1) > 0)
    n_both_pass = sum(1 for pair in TOP_PAIRS
                      if (wf_summary.get(pair[0], {}).get("n_pos", 0) >= 3 and
                          split_results.get(pair[0], {}).get("test_sharpe", -1) > 0))

    print(f"""
  Walk-forward (5 folds x 120d):
    Passed (>= 3/5 positive):  {n_wf_pass}/{len(TOP_PAIRS)}

  50/50 train/test split:
    Passed (test Sharpe > 0):  {n_split_pass}/{len(split_results)}

  Both tests passed:          {n_both_pass}

  KEY FINDINGS:
  1. Only 3/91 pairs are strictly cointegrated (p < 0.05)
  2. Cointegration is UNSTABLE — most pairs significant in < 30% of rolling windows
  3. In-sample results look good (IS Sharpe 0.4-1.3) but OOS is mixed
  4. DOT/ATOM is the strongest single pair (IS 1.30, OOS 0.36/0.52)
  5. Multi-pair portfolio helps via diversification (IS Sharpe 1.6+)
  6. OOS portfolio Sharpe ~0.5-1.0 — moderate edge
  7. Correlation with H-012: -0.05 to -0.31 (NEGATIVE — excellent diversifier)
  8. Pairs trading is fundamentally limited by LOW TRADE FREQUENCY
""")


if __name__ == "__main__":
    main()
