"""
Batch backtest: H-708 to H-715 — BTC/ETH Time-Series strategies using real OI data.

H-708: BTC OI Divergence TS — price vs OI new high/low divergence
H-709: BTC Liquidation Proxy TS — rapid OI drop + price drop → bounce
H-710: BTC Funding-OI Composite TS — combined positioning signal
H-711: ETH/BTC OI Ratio TS — altcoin rotation signal
H-712: Aggregate Crypto OI Expansion TS — total OI breadth
H-713: OI-Volatility Regime TS — trade regime-conditional on OI
H-714: BTC OI Percentile Timing TS — extreme OI levels as timing signal
H-715: OI Breadth TS — rising OI breadth as BTC signal
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

DATA_DIR = Path("data")
FEE_RATE = 0.00055
SLIPPAGE_BPS = 2
ASSETS = ["BTC", "ETH", "SOL", "SUI", "XRP", "DOGE", "AVAX", "LINK",
          "ADA", "DOT", "NEAR", "OP", "ARB", "ATOM"]


def load_btc_data():
    prices = pd.read_parquet(DATA_DIR / "BTC_USDT_1d.parquet")["close"]
    if prices.index.tz is not None:
        prices.index = prices.index.tz_localize(None)

    oi = pd.read_parquet(DATA_DIR / "BTC_USDT_oi_daily.parquet")["openInterest"]
    if oi.index.tz is not None:
        oi.index = oi.index.tz_localize(None)

    fr = pd.read_parquet(DATA_DIR / "funding_BTCUSDT.parquet")["funding_rate"]
    if fr.index.tz is not None:
        fr.index = fr.index.tz_localize(None)
    fr_daily = fr.resample("1D").sum()

    common = prices.index.intersection(oi.index)
    prices = prices.loc[common]
    oi = oi.loc[common]
    fr_daily = fr_daily.reindex(common).fillna(0)

    return prices, oi, fr_daily


def load_eth_data():
    prices = pd.read_parquet(DATA_DIR / "ETH_USDT_1d.parquet")["close"]
    if prices.index.tz is not None:
        prices.index = prices.index.tz_localize(None)

    oi = pd.read_parquet(DATA_DIR / "ETH_USDT_oi_daily.parquet")["openInterest"]
    if oi.index.tz is not None:
        oi.index = oi.index.tz_localize(None)
    return prices, oi


def load_all_oi():
    oi_dict = {}
    for t in ASSETS:
        try:
            df = pd.read_parquet(DATA_DIR / f"{t}_USDT_oi_daily.parquet")
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            oi_dict[t] = df["openInterest"]
        except:
            pass
    return pd.DataFrame(oi_dict).sort_index().dropna(how="all")


def ts_backtest(prices, signal):
    ret = prices.pct_change().iloc[1:]
    sig = signal.shift(1).iloc[1:]
    common = ret.index.intersection(sig.dropna().index)
    ret = ret.loc[common]
    sig = sig.loc[common]

    pnl = []
    prev_pos = 0
    for i in range(len(ret)):
        pos = sig.iloc[i]
        turnover = abs(pos - prev_pos)
        cost = turnover * FEE_RATE + turnover * SLIPPAGE_BPS / 10_000
        daily_pnl = pos * ret.iloc[i] - cost
        pnl.append(daily_pnl)
        prev_pos = pos
    return np.array(pnl)


def compute_sharpe(pnl, ann=365):
    if len(pnl) < 30 or np.std(pnl) == 0:
        return 0
    return np.mean(pnl) / np.std(pnl) * np.sqrt(ann)


def compute_metrics(pnl):
    if len(pnl) < 30:
        return {"sharpe": 0, "annual_ret": 0, "max_dd": 0}
    sharpe = compute_sharpe(pnl)
    annual_ret = np.mean(pnl) * 365 * 100
    cum = np.cumsum(pnl)
    dd = cum - np.maximum.accumulate(cum)
    max_dd = np.min(dd) * 100 if len(dd) > 0 else 0
    return {"sharpe": round(sharpe, 3), "annual_ret": round(annual_ret, 1),
            "max_dd": round(max_dd, 1)}


def walk_forward(prices, signal_fn, n_folds=6, test_days=100):
    results = []
    for fold in range(n_folds):
        test_end = len(prices) - fold * test_days
        test_start = test_end - test_days
        if test_start < 200:
            break
        p = prices.iloc[:test_end]
        sig = signal_fn(p)
        sig_test = sig.iloc[test_start:test_end]
        p_test = prices.iloc[test_start:test_end]
        pnl = ts_backtest(p_test, sig_test)
        results.append(compute_sharpe(pnl))
    return results


def split_half(prices, signal_fn):
    mid = len(prices) // 2
    p1, p2 = prices.iloc[:mid], prices.iloc[mid:]
    sig1, sig2 = signal_fn(p1), signal_fn(p2)
    return compute_sharpe(ts_backtest(p1, sig1)), compute_sharpe(ts_backtest(p2, sig2))


def param_robustness(prices, signal_fn_factory, param_grid):
    pos = sum(1 for p in param_grid
              if compute_sharpe(ts_backtest(prices, signal_fn_factory(*p)(prices))) > 0)
    return pos, len(param_grid)


def h009_corr(prices, signal):
    pnl_test = ts_backtest(prices, signal)
    ema5 = prices.ewm(span=5).mean()
    ema40 = prices.ewm(span=40).mean()
    sig_h009 = (ema5 > ema40).astype(float) * 2 - 1
    pnl_h009 = ts_backtest(prices, sig_h009)
    mn = min(len(pnl_test), len(pnl_h009))
    if mn < 30:
        return 0
    return round(np.corrcoef(pnl_test[:mn], pnl_h009[:mn])[0, 1], 3)


def run_test(title, hyp_id, prices, signal_fn, param_grid=None,
             signal_fn_factory=None):
    print(f"\n{'='*70}")
    print(f"{hyp_id}: {title}")
    print(f"{'='*70}")

    sig = signal_fn(prices)
    pnl = ts_backtest(prices, sig)
    m = compute_metrics(pnl)
    print(f"  IS: Sharpe {m['sharpe']:.3f}, Ann {m['annual_ret']:.1f}%, DD {m['max_dd']:.1f}%")

    if m["sharpe"] < 0.3:
        print(f"  => REJECTED (IS Sharpe too low)")
        return {"status": "REJECTED", **m}

    pr_pct = 1.0
    if param_grid and signal_fn_factory:
        pr_pos, pr_total = param_robustness(prices, signal_fn_factory, param_grid)
        pr_pct = pr_pos / pr_total if pr_total > 0 else 0
        print(f"  Params: {pr_pos}/{pr_total} ({pr_pct*100:.0f}%)")

    wf = walk_forward(prices, signal_fn)
    wf_pos = sum(1 for s in wf if s > 0)
    wf_mean = np.mean(wf) if wf else 0
    print(f"  WF: {wf_pos}/{len(wf)} positive, mean {wf_mean:.3f}")

    sh1, sh2 = split_half(prices, signal_fn)
    sh_pass = sh1 > 0 and sh2 > 0
    print(f"  SH: H1={sh1:.3f}, H2={sh2:.3f} {'PASS' if sh_pass else 'FAIL'}")

    corr = h009_corr(prices, sig)
    print(f"  H-009 corr: {corr}")

    confirmed = (wf_pos >= len(wf) * 0.6 and pr_pct >= 0.75 and
                 sh_pass and m["sharpe"] >= 0.7)
    status = "CONFIRMED" if confirmed else "BORDERLINE" if wf_pos >= len(wf) * 0.5 else "REJECTED"
    print(f"  => {status}")

    return {"status": status, **m, "param_pct": pr_pct,
            "wf_pos": wf_pos, "wf_n": len(wf), "wf_mean": wf_mean,
            "sh": (sh1, sh2), "sh_pass": sh_pass, "corr_h009": corr}


# ============================================================
# SIGNAL GENERATORS
# ============================================================

def make_h708_signal(oi_lookback, price_lookback):
    """H-708: OI Divergence. New price high without OI high = bearish."""
    def signal_fn(prices):
        oi = pd.read_parquet(DATA_DIR / "BTC_USDT_oi_daily.parquet")["openInterest"]
        if oi.index.tz is not None:
            oi.index = oi.index.tz_localize(None)
        oi = oi.reindex(prices.index).ffill()

        price_hi = prices.rolling(price_lookback).max()
        oi_hi = oi.rolling(oi_lookback).max()
        price_at_hi = (prices >= price_hi * 0.99)
        oi_at_hi = (oi >= oi_hi * 0.99)

        price_lo = prices.rolling(price_lookback).min()
        oi_lo = oi.rolling(oi_lookback).min()
        price_at_lo = (prices <= price_lo * 1.01)
        oi_at_lo = (oi <= oi_lo * 1.01)

        sig = pd.Series(0.0, index=prices.index)
        sig[price_at_hi & ~oi_at_hi] = -1.0  # bearish divergence
        sig[price_at_lo & ~oi_at_lo] = 1.0   # bullish divergence
        sig[price_at_hi & oi_at_hi] = 1.0    # confirmed breakout
        sig[price_at_lo & oi_at_lo] = -1.0   # confirmed breakdown
        return sig
    return signal_fn


def make_h709_signal(oi_drop_pct, price_drop_pct, hold_days):
    """H-709: Liquidation proxy. Rapid OI drop + price drop → buy bounce."""
    def signal_fn(prices):
        oi = pd.read_parquet(DATA_DIR / "BTC_USDT_oi_daily.parquet")["openInterest"]
        if oi.index.tz is not None:
            oi.index = oi.index.tz_localize(None)
        oi = oi.reindex(prices.index).ffill()

        oi_chg = oi.pct_change(1)
        price_chg = prices.pct_change(1)

        sig = pd.Series(0.0, index=prices.index)
        holding = 0
        for i in range(1, len(prices)):
            if holding > 0:
                holding -= 1
                sig.iloc[i] = 1.0
            elif oi_chg.iloc[i] < -oi_drop_pct and price_chg.iloc[i] < -price_drop_pct:
                sig.iloc[i] = 1.0
                holding = hold_days
        return sig
    return signal_fn


def make_h710_signal(oi_lb, fr_lb, price_lb):
    """H-710: Funding-OI composite. High funding + high OI growth + price up = crowded long → short."""
    def signal_fn(prices):
        oi = pd.read_parquet(DATA_DIR / "BTC_USDT_oi_daily.parquet")["openInterest"]
        if oi.index.tz is not None:
            oi.index = oi.index.tz_localize(None)
        oi = oi.reindex(prices.index).ffill()

        fr = pd.read_parquet(DATA_DIR / "funding_BTCUSDT.parquet")["funding_rate"]
        if fr.index.tz is not None:
            fr.index = fr.index.tz_localize(None)
        fr_daily = fr.resample("1D").sum().reindex(prices.index).fillna(0)

        oi_growth = oi.pct_change(oi_lb)
        fr_roll = fr_daily.rolling(fr_lb).mean()
        price_mom = prices.pct_change(price_lb)

        oi_z = (oi_growth - oi_growth.rolling(60).mean()) / oi_growth.rolling(60).std().replace(0, 1)
        fr_z = (fr_roll - fr_roll.rolling(60).mean()) / fr_roll.rolling(60).std().replace(0, 1)
        price_z = (price_mom - price_mom.rolling(60).mean()) / price_mom.rolling(60).std().replace(0, 1)

        composite = oi_z + fr_z + price_z
        sig = pd.Series(0.0, index=prices.index)
        sig[composite > 1.5] = -1.0   # very crowded long → contrarian short
        sig[composite < -1.5] = 1.0   # very crowded short → contrarian long
        sig[(composite > 0) & (composite <= 1.5)] = 0.5  # mild long
        sig[(composite < 0) & (composite >= -1.5)] = -0.5  # mild short
        return sig
    return signal_fn


def make_h711_signal(lookback):
    """H-711: ETH/BTC OI ratio change. Rising ratio = altcoin season → long ETH."""
    def signal_fn(prices):
        btc_oi = pd.read_parquet(DATA_DIR / "BTC_USDT_oi_daily.parquet")["openInterest"]
        eth_oi = pd.read_parquet(DATA_DIR / "ETH_USDT_oi_daily.parquet")["openInterest"]
        for s in [btc_oi, eth_oi]:
            if s.index.tz is not None:
                s.index = s.index.tz_localize(None)
        # This trades ETH, not BTC, based on relative OI
        eth_prices = pd.read_parquet(DATA_DIR / "ETH_USDT_1d.parquet")["close"]
        if eth_prices.index.tz is not None:
            eth_prices.index = eth_prices.index.tz_localize(None)

        common = prices.index
        btc_oi = btc_oi.reindex(common).ffill()
        eth_oi = eth_oi.reindex(common).ffill()

        ratio = eth_oi / btc_oi.replace(0, np.nan)
        ratio_chg = ratio.pct_change(lookback)
        ratio_z = (ratio_chg - ratio_chg.rolling(60).mean()) / ratio_chg.rolling(60).std().replace(0, 1)

        sig = pd.Series(0.0, index=prices.index)
        sig[ratio_z > 1] = 1.0
        sig[ratio_z < -1] = -1.0
        return sig
    return signal_fn


def make_h712_signal(lookback, threshold):
    """H-712: Aggregate OI expansion. Total OI across all assets as timing signal."""
    def signal_fn(prices):
        oi_all = load_all_oi()
        oi_all = oi_all.reindex(prices.index).ffill()
        total_oi_usd = pd.Series(0.0, index=prices.index)
        for t in oi_all.columns:
            p = pd.read_parquet(DATA_DIR / f"{t}_USDT_1d.parquet")["close"]
            if p.index.tz is not None:
                p.index = p.index.tz_localize(None)
            p = p.reindex(prices.index).ffill()
            total_oi_usd += oi_all[t] * p

        oi_growth = total_oi_usd.pct_change(lookback)
        oi_ma = oi_growth.rolling(20).mean()

        sig = pd.Series(0.0, index=prices.index)
        sig[oi_growth > threshold] = 1.0
        sig[oi_growth < -threshold] = -1.0
        return sig
    return signal_fn


def make_h713_signal(oi_pct_lb, vol_lb):
    """H-713: OI-Vol regime. High OI + low vol = squeeze building → breakout. High OI + high vol = crowded → revert."""
    def signal_fn(prices):
        oi = pd.read_parquet(DATA_DIR / "BTC_USDT_oi_daily.parquet")["openInterest"]
        if oi.index.tz is not None:
            oi.index = oi.index.tz_localize(None)
        oi = oi.reindex(prices.index).ffill()

        oi_pct = oi.rolling(oi_pct_lb).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )
        vol = prices.pct_change().abs().rolling(vol_lb).mean()
        vol_pct = vol.rolling(oi_pct_lb).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )

        sig = pd.Series(0.0, index=prices.index)
        # High OI + Low vol = squeeze → follow momentum
        price_mom = prices.pct_change(10)
        squeeze = (oi_pct > 0.7) & (vol_pct < 0.3)
        sig[squeeze & (price_mom > 0)] = 1.0
        sig[squeeze & (price_mom < 0)] = -1.0
        # High OI + High vol = crowded + volatile → mean revert
        crowded_vol = (oi_pct > 0.7) & (vol_pct > 0.7)
        sig[crowded_vol & (price_mom > 0)] = -0.5
        sig[crowded_vol & (price_mom < 0)] = 0.5
        return sig
    return signal_fn


def make_h714_signal(lookback, threshold_hi, threshold_lo):
    """H-714: OI percentile timing. Trade BTC based on OI extremes."""
    def signal_fn(prices):
        oi = pd.read_parquet(DATA_DIR / "BTC_USDT_oi_daily.parquet")["openInterest"]
        if oi.index.tz is not None:
            oi.index = oi.index.tz_localize(None)
        oi = oi.reindex(prices.index).ffill()

        oi_pct = oi.rolling(lookback).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )

        sig = pd.Series(0.0, index=prices.index)
        sig[oi_pct > threshold_hi] = -1.0  # OI at extreme high = crowded → contrarian
        sig[oi_pct < threshold_lo] = 1.0   # OI at extreme low = uncrowded → buy
        return sig
    return signal_fn


def make_h715_signal(lookback, min_breadth):
    """H-715: OI breadth. How many assets have rising OI?"""
    def signal_fn(prices):
        oi_all = load_all_oi()
        oi_all = oi_all.reindex(prices.index).ffill()
        oi_chg = oi_all.pct_change(lookback)
        breadth = (oi_chg > 0).sum(axis=1) / oi_chg.notna().sum(axis=1)

        sig = pd.Series(0.0, index=prices.index)
        sig[breadth > min_breadth] = 1.0
        sig[breadth < (1 - min_breadth)] = -1.0
        return sig
    return signal_fn


if __name__ == "__main__":
    print("Loading data...")
    btc_prices, btc_oi, btc_fr = load_btc_data()
    print(f"BTC: {len(btc_prices)} days, {btc_prices.index[0].date()} to {btc_prices.index[-1].date()}")

    results = {}

    # H-708: OI Divergence
    pg708 = [(ol, pl) for ol in [20, 30, 50] for pl in [20, 30, 50]]
    best_sh, best_p = -999, None
    for ol, pl in pg708:
        pnl = ts_backtest(btc_prices, make_h708_signal(ol, pl)(btc_prices))
        sh = compute_sharpe(pnl)
        if sh > best_sh:
            best_sh, best_p = sh, (ol, pl)
    if best_p:
        results["H-708"] = run_test("BTC OI Divergence TS", "H-708",
            btc_prices, make_h708_signal(*best_p), pg708,
            lambda ol, pl: make_h708_signal(ol, pl))

    # H-709: Liquidation Proxy
    pg709 = [(od, pd_, hd) for od in [0.02, 0.03, 0.05]
             for pd_ in [0.02, 0.03, 0.05] for hd in [3, 5, 7]]
    best_sh, best_p = -999, None
    for od, pd_, hd in pg709:
        pnl = ts_backtest(btc_prices, make_h709_signal(od, pd_, hd)(btc_prices))
        sh = compute_sharpe(pnl)
        if sh > best_sh:
            best_sh, best_p = sh, (od, pd_, hd)
    if best_p:
        results["H-709"] = run_test("BTC Liquidation Proxy TS", "H-709",
            btc_prices, make_h709_signal(*best_p), pg709,
            lambda od, pd_, hd: make_h709_signal(od, pd_, hd))

    # H-710: Funding-OI Composite
    pg710 = [(ol, fl, pl) for ol in [10, 20] for fl in [7, 14] for pl in [10, 20]]
    best_sh, best_p = -999, None
    for ol, fl, pl in pg710:
        pnl = ts_backtest(btc_prices, make_h710_signal(ol, fl, pl)(btc_prices))
        sh = compute_sharpe(pnl)
        if sh > best_sh:
            best_sh, best_p = sh, (ol, fl, pl)
    if best_p:
        results["H-710"] = run_test("BTC Funding-OI Composite TS", "H-710",
            btc_prices, make_h710_signal(*best_p), pg710,
            lambda ol, fl, pl: make_h710_signal(ol, fl, pl))

    # H-711: ETH/BTC OI Ratio
    eth_prices, _ = load_eth_data()
    common = btc_prices.index.intersection(eth_prices.index)
    eth_p = eth_prices.loc[common]
    pg711 = [(lb,) for lb in [5, 10, 14, 20, 30]]
    best_sh, best_p = -999, None
    for (lb,) in pg711:
        sig_fn = make_h711_signal(lb)
        pnl = ts_backtest(eth_p, sig_fn(eth_p))
        sh = compute_sharpe(pnl)
        if sh > best_sh:
            best_sh, best_p = sh, lb
    if best_p:
        results["H-711"] = run_test("ETH/BTC OI Ratio TS", "H-711",
            eth_p, make_h711_signal(best_p), pg711,
            lambda lb: make_h711_signal(lb))

    # H-712: Aggregate OI Expansion
    pg712 = [(lb, th) for lb in [5, 10, 20] for th in [0.01, 0.03, 0.05, 0.10]]
    best_sh, best_p = -999, None
    for lb, th in pg712:
        pnl = ts_backtest(btc_prices, make_h712_signal(lb, th)(btc_prices))
        sh = compute_sharpe(pnl)
        if sh > best_sh:
            best_sh, best_p = sh, (lb, th)
    if best_p:
        results["H-712"] = run_test("Aggregate OI Expansion TS", "H-712",
            btc_prices, make_h712_signal(*best_p), pg712,
            lambda lb, th: make_h712_signal(lb, th))

    # H-713: OI-Vol Regime
    pg713 = [(opl, vl) for opl in [30, 60, 90] for vl in [10, 20, 30]]
    best_sh, best_p = -999, None
    for opl, vl in pg713:
        pnl = ts_backtest(btc_prices, make_h713_signal(opl, vl)(btc_prices))
        sh = compute_sharpe(pnl)
        if sh > best_sh:
            best_sh, best_p = sh, (opl, vl)
    if best_p:
        results["H-713"] = run_test("OI-Volatility Regime TS", "H-713",
            btc_prices, make_h713_signal(*best_p), pg713,
            lambda opl, vl: make_h713_signal(opl, vl))

    # H-714: OI Percentile Timing
    pg714 = [(lb, hi, lo) for lb in [30, 60, 90]
             for hi in [0.8, 0.85, 0.9] for lo in [0.1, 0.15, 0.2]]
    best_sh, best_p = -999, None
    for lb, hi, lo in pg714:
        pnl = ts_backtest(btc_prices, make_h714_signal(lb, hi, lo)(btc_prices))
        sh = compute_sharpe(pnl)
        if sh > best_sh:
            best_sh, best_p = sh, (lb, hi, lo)
    if best_p:
        results["H-714"] = run_test("BTC OI Percentile Timing TS", "H-714",
            btc_prices, make_h714_signal(*best_p), pg714,
            lambda lb, hi, lo: make_h714_signal(lb, hi, lo))

    # H-715: OI Breadth
    pg715 = [(lb, mb) for lb in [5, 10, 14, 20] for mb in [0.6, 0.7, 0.8]]
    best_sh, best_p = -999, None
    for lb, mb in pg715:
        pnl = ts_backtest(btc_prices, make_h715_signal(lb, mb)(btc_prices))
        sh = compute_sharpe(pnl)
        if sh > best_sh:
            best_sh, best_p = sh, (lb, mb)
    if best_p:
        results["H-715"] = run_test("OI Breadth TS", "H-715",
            btc_prices, make_h715_signal(*best_p), pg715,
            lambda lb, mb: make_h715_signal(lb, mb))

    # SUMMARY
    print(f"\n{'='*70}")
    print("BATCH SUMMARY: H-708 to H-715")
    print(f"{'='*70}")
    for hid, r in sorted(results.items()):
        st = r.get("status", "?")
        sh = r.get("sharpe", 0)
        corr = r.get("corr_h009", "?")
        wf = f"{r.get('wf_pos', '?')}/{r.get('wf_n', '?')}"
        print(f"  {hid}: {st} (Sharpe {sh:.3f}, WF {wf}, H-009 corr {corr})")
