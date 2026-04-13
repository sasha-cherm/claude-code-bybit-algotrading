#!/usr/bin/env python3
"""
Master Paper Trade Orchestrator — runs all active paper trade runners
sequentially, then prints a portfolio summary.

Designed to run independently from Claude sessions via cron:
    */30 * * * * /home/cctrd/cc-bybit-algotrading/scripts/run_all_paper_trades.py

Each runner is a one-shot script that checks for new bars/events and
executes trades if needed. Safe to call frequently — runners skip
if no new data.
"""

import importlib.util
import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# All active paper trade runners in execution order
RUNNERS = [
    ("H-009", ROOT / "paper_trades" / "h009_btc_daily_trend" / "runner.py"),
    ("H-011", ROOT / "paper_trades" / "h011_funding_rate_arb" / "runner.py"),
    ("H-012", ROOT / "paper_trades" / "h012_xsmom" / "runner.py"),
    ("H-019", ROOT / "paper_trades" / "h019_lowvol" / "runner.py"),
    ("H-021", ROOT / "paper_trades" / "h021_volmom" / "runner.py"),
    ("H-031", ROOT / "paper_trades" / "h031_size" / "runner.py"),
    ("H-032", ROOT / "paper_trades" / "h032_pairs" / "runner.py"),
    ("H-039", ROOT / "paper_trades" / "h039_dow_seasonality" / "runner.py"),
    ("H-044", ROOT / "paper_trades" / "h044_oi_divergence" / "runner.py"),
    ("H-046", ROOT / "paper_trades" / "h046_acceleration" / "runner.py"),
    ("H-049", ROOT / "paper_trades" / "h049_lsr_sentiment" / "runner.py"),
    ("H-052", ROOT / "paper_trades" / "h052_premium" / "runner.py"),
    ("H-053", ROOT / "paper_trades" / "h053_funding_xs" / "runner.py"),
    ("H-059", ROOT / "paper_trades" / "h059_vol_term" / "runner.py"),
    ("H-062", ROOT / "paper_trades" / "h062_dd_momentum" / "runner.py"),
    ("H-063", ROOT / "paper_trades" / "h063_vol_selling" / "runner.py"),
    ("H-076", ROOT / "paper_trades" / "h076_efficiency" / "runner.py"),
    ("H-085", ROOT / "paper_trades" / "h085_turnover" / "runner.py"),
    ("H-160", ROOT / "paper_trades" / "h160_trend_quality" / "runner.py"),
    ("H-169", ROOT / "paper_trades" / "h169_alpha_momentum" / "runner.py"),
    ("H-175", ROOT / "paper_trades" / "h175_money_flow" / "runner.py"),
    ("H-182", ROOT / "paper_trades" / "h182_range" / "runner.py"),
    ("H-183", ROOT / "paper_trades" / "h183_gap" / "runner.py"),
    ("H-189", ROOT / "paper_trades" / "h189_funding_dispersion" / "runner.py"),
    ("H-191", ROOT / "paper_trades" / "h191_vol_price_elasticity" / "runner.py"),
    ("H-193", ROOT / "paper_trades" / "h193_oi_price_divergence" / "runner.py"),
    ("H-197", ROOT / "paper_trades" / "h197_amihud" / "runner.py"),
    ("H-215", ROOT / "paper_trades" / "h215_dollar_vol_trend" / "runner.py"),
    ("H-219", ROOT / "paper_trades" / "h219_upvol_ratio" / "runner.py"),
    ("H-223", ROOT / "paper_trades" / "h223_momentum_breadth" / "runner.py"),
    ("H-242", ROOT / "paper_trades" / "h242_intraday_concentration" / "runner.py"),
    ("H-244", ROOT / "paper_trades" / "h244_intraday_reversal" / "runner.py"),
    ("H-250", ROOT / "paper_trades" / "h250_session_momentum" / "runner.py"),
    ("H-255", ROOT / "paper_trades" / "h255_sharpe_momentum" / "runner.py"),
    ("H-259", ROOT / "paper_trades" / "h259_extreme_moves" / "runner.py"),
    ("H-263", ROOT / "paper_trades" / "h263_relative_strength" / "runner.py"),
    ("H-264", ROOT / "paper_trades" / "h264_skewness" / "runner.py"),
    ("H-277", ROOT / "paper_trades" / "h277_vwap_deviation" / "runner.py"),
    ("H-324", ROOT / "paper_trades" / "h324_adx_tsmom" / "runner.py"),
    ("H-332", ROOT / "paper_trades" / "h332_bar_consistency" / "runner.py"),
    ("H-336", ROOT / "paper_trades" / "h336_volume_surprise" / "runner.py"),
    ("H-333", ROOT / "paper_trades" / "h333_smart_vol_return" / "runner.py"),
    ("H-338", ROOT / "paper_trades" / "h338_vw_pressure" / "runner.py"),
    ("H-342", ROOT / "paper_trades" / "h342_vp_sync" / "runner.py"),
    ("H-343", ROOT / "paper_trades" / "h343_momentum_decay" / "runner.py"),
    ("H-351", ROOT / "paper_trades" / "h351_vol_skew" / "runner.py"),
    ("H-353", ROOT / "paper_trades" / "h353_vol_persistence" / "runner.py"),
    ("H-355", ROOT / "paper_trades" / "h355_entropy" / "runner.py"),
    ("H-363", ROOT / "paper_trades" / "h363_multiday_pattern" / "runner.py"),
    ("H-368", ROOT / "paper_trades" / "h368_vol_share_drift" / "runner.py"),
    ("H-382", ROOT / "paper_trades" / "h382_return_kurtosis" / "runner.py"),
    ("H-383", ROOT / "paper_trades" / "h383_pvt" / "runner.py"),
    ("H-388", ROOT / "paper_trades" / "h388_night_day_diff" / "runner.py"),
    ("H-394", ROOT / "paper_trades" / "h394_variance_ratio" / "runner.py"),
    ("H-404", ROOT / "paper_trades" / "h404_session_flow" / "runner.py"),
    ("H-411", ROOT / "paper_trades" / "h411_obv_slope" / "runner.py"),
    ("H-414", ROOT / "paper_trades" / "h414_vol_trend" / "runner.py"),
    ("H-435", ROOT / "paper_trades" / "h435_hourly_kurtosis" / "runner.py"),
    ("H-437", ROOT / "paper_trades" / "h437_hl_spread" / "runner.py"),
    ("H-445", ROOT / "paper_trades" / "h445_max_hourly_dd" / "runner.py"),
    ("H-447", ROOT / "paper_trades" / "h447_vol_autocorr" / "runner.py"),
    ("H-451", ROOT / "paper_trades" / "h451_close_high_ratio" / "runner.py"),
    ("H-470", ROOT / "paper_trades" / "h470_first_hour_ret" / "runner.py"),
    ("H-496", ROOT / "paper_trades" / "h496_ml_ensemble" / "runner.py"),
    ("H-528", ROOT / "paper_trades" / "h528_range_expansion" / "runner.py"),
    ("H-535", ROOT / "paper_trades" / "h535_intraday_momentum" / "runner.py"),
    ("H-539", ROOT / "paper_trades" / "h539_keltner_breakout" / "runner.py"),
    ("H-544", ROOT / "paper_trades" / "h544_range_squeeze" / "runner.py"),
    ("H-571", ROOT / "paper_trades" / "h571_sol_session_momentum" / "runner.py"),
    ("H-599", ROOT / "paper_trades" / "h599_rsi_xs" / "runner.py"),
    ("H-601", ROOT / "paper_trades" / "h601_vol_decline" / "runner.py"),
    ("H-617", ROOT / "paper_trades" / "h617_4h_vol_breakout" / "runner.py"),
    ("H-657", ROOT / "paper_trades" / "h657_realized_skew" / "runner.py"),
    ("H-676", ROOT / "paper_trades" / "h676_consecutive_contrarian" / "runner.py"),
    ("H-677", ROOT / "paper_trades" / "h677_crash_bounce" / "runner.py"),
    ("H-679", ROOT / "paper_trades" / "h679_vol_regime_switch" / "runner.py"),
    ("H-680", ROOT / "paper_trades" / "h680_vol_convergence" / "runner.py"),
    ("H-703", ROOT / "paper_trades" / "h703_oi_surprise" / "runner.py"),
    ("H-726", ROOT / "paper_trades" / "h726_max_dd_factor" / "runner.py"),
    ("H-733", ROOT / "paper_trades" / "h733_dv_change" / "runner.py"),
    ("H-736", ROOT / "paper_trades" / "h736_volume_delta" / "runner.py"),
    ("H-754", ROOT / "paper_trades" / "h754_lead_lag" / "runner.py"),
    ("H-759", ROOT / "paper_trades" / "h759_adx_trend" / "runner.py"),
    ("H-761", ROOT / "paper_trades" / "h761_gap_signal" / "runner.py"),
    ("H-763", ROOT / "paper_trades" / "h763_mom_vol_ratio" / "runner.py"),
    ("H-768", ROOT / "paper_trades" / "h768_sequential_pattern" / "runner.py"),
    ("H-769", ROOT / "paper_trades" / "h769_multi_horizon_div" / "runner.py"),
    ("H-773", ROOT / "paper_trades" / "h773_oi_confirmed_mom" / "runner.py"),
    ("H-777", ROOT / "paper_trades" / "h777_pvt" / "runner.py"),
    ("H-778", ROOT / "paper_trades" / "h778_clv" / "runner.py"),
    ("H-781", ROOT / "paper_trades" / "h781_signal_agreement" / "runner.py"),
    ("H-786", ROOT / "paper_trades" / "h786_vol_confirmed" / "runner.py"),
    ("H-792", ROOT / "paper_trades" / "h792_oi_price_coherence" / "runner.py"),
    ("H-810", ROOT / "paper_trades" / "h810_vol_trend_strength" / "runner.py"),
    ("H-814", ROOT / "paper_trades" / "h814_rank_velocity" / "runner.py"),
    ("H-817", ROOT / "paper_trades" / "h817_vol_spillover" / "runner.py"),
    ("H-824", ROOT / "paper_trades" / "h824_min_return" / "runner.py"),
    ("H-828", ROOT / "paper_trades" / "h828_signal_ensemble" / "runner.py"),
    ("H-831", ROOT / "paper_trades" / "h831_vol_breakout" / "runner.py"),
    ("H-837", ROOT / "paper_trades" / "h837_vol_turnover" / "runner.py"),
    ("H-843", ROOT / "paper_trades" / "h843_range_vol" / "runner.py"),
    ("H-849", ROOT / "paper_trades" / "h849_underwater_vol" / "runner.py"),
    ("H-851", ROOT / "paper_trades" / "h851_dd_mean_reversion" / "runner.py"),
    ("H-854", ROOT / "paper_trades" / "h854_clv" / "runner.py"),
    ("H-861", ROOT / "paper_trades" / "h861_downside_protect" / "runner.py"),
    ("H-863", ROOT / "paper_trades" / "h863_win_rate" / "runner.py"),
    ("H-864", ROOT / "paper_trades" / "h864_conditional_mom" / "runner.py"),
    ("H-866", ROOT / "paper_trades" / "h866_vw_return_div" / "runner.py"),
    ("H-867", ROOT / "paper_trades" / "h867_max_gain_dep" / "runner.py"),
    ("H-873", ROOT / "paper_trades" / "h873_dist_from_high" / "runner.py"),
    ("H-878", ROOT / "paper_trades" / "h878_stochastic" / "runner.py"),
    ("H-882", ROOT / "paper_trades" / "h882_emv" / "runner.py"),
    ("H-891", ROOT / "paper_trades" / "h891_up_down_ratio" / "runner.py"),
    ("H-892", ROOT / "paper_trades" / "h892_vol_acceleration" / "runner.py"),
    ("H-894", ROOT / "paper_trades" / "h894_vol_price_corr" / "runner.py"),
    ("H-898", ROOT / "paper_trades" / "h898_cum_vol_div" / "runner.py"),
    ("H-899", ROOT / "paper_trades" / "h899_vol_trend_persist" / "runner.py"),
    ("H-900", ROOT / "paper_trades" / "h900_tf_consistency" / "runner.py"),
    ("H-902", ROOT / "paper_trades" / "h902_momentum_quality" / "runner.py"),
    ("H-914", ROOT / "paper_trades" / "h914_return_smoothness" / "runner.py"),
    ("H-915", ROOT / "paper_trades" / "h915_sortino" / "runner.py"),
    ("H-916", ROOT / "paper_trades" / "h916_trend_linearity" / "runner.py"),
    ("H-917", ROOT / "paper_trades" / "h917_price_efficiency" / "runner.py"),
    ("H-927", ROOT / "paper_trades" / "h927_accumulation_index" / "runner.py"),
    ("H-929", ROOT / "paper_trades" / "h929_vw_momentum" / "runner.py"),
    ("H-931", ROOT / "paper_trades" / "h931_vol_regime_change" / "runner.py"),
    ("H-935", ROOT / "paper_trades" / "h935_trend_strength" / "runner.py"),
    ("H-938", ROOT / "paper_trades" / "h938_range_adj_mom" / "runner.py"),
    ("H-939", ROOT / "paper_trades" / "h939_vol_conf_trend" / "runner.py"),
    ("H-940", ROOT / "paper_trades" / "h940_gain_pain" / "runner.py"),
    ("H-946", ROOT / "paper_trades" / "h946_kappa" / "runner.py"),
    ("H-954", ROOT / "paper_trades" / "h954_drift_vol" / "runner.py"),
    ("H-959", ROOT / "paper_trades" / "h959_down_freq" / "runner.py"),
    ("H-960", ROOT / "paper_trades" / "h960_win_streak" / "runner.py"),
    ("H-961", ROOT / "paper_trades" / "h961_tail_improvement" / "runner.py"),
    ("H-963", ROOT / "paper_trades" / "h963_ret_concentration" / "runner.py"),
    ("H-964", ROOT / "paper_trades" / "h964_mom_conviction" / "runner.py"),
    ("H-970", ROOT / "paper_trades" / "h970_higher_lows" / "runner.py"),
    ("H-971", ROOT / "paper_trades" / "h971_overnight_gap" / "runner.py"),
    ("H-974", ROOT / "paper_trades" / "h974_atr_expansion" / "runner.py"),
    ("H-979", ROOT / "paper_trades" / "h979_range_expansion" / "runner.py"),
    ("H-986", ROOT / "paper_trades" / "h986_vol_breakout_freq" / "runner.py"),
    ("H-992", ROOT / "paper_trades" / "h992_xs_skew" / "runner.py"),
    ("H-994", ROOT / "paper_trades" / "h994_vol_rank_change" / "runner.py"),
    ("H-997", ROOT / "paper_trades" / "h997_mom_vol_int" / "runner.py"),
    ("H-1001", ROOT / "paper_trades" / "h1001_mom_breadth" / "runner.py"),
    ("H-1003", ROOT / "paper_trades" / "h1003_atr_norm_ret" / "runner.py"),
]

LOG_FILE = ROOT / "logs" / "paper_trades.log"


def log(msg: str):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{timestamp}] {msg}"
    # Write to log file only (cron redirects stdout to same file, so print would double-write)
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    # Print only when running interactively (not from cron)
    import sys
    if sys.stdout.isatty():
        print(line)


def run_single(name: str, runner_path: Path) -> dict:
    """Import and run a single paper trade runner. Returns result dict."""
    if not runner_path.exists():
        return {"name": name, "status": "MISSING", "error": f"{runner_path} not found"}

    try:
        spec = importlib.util.spec_from_file_location(f"runner_{name}", runner_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.run()

        # Read state to report equity (prefer last equity_history entry for MTM)
        state_file = runner_path.parent / "state.json"
        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)
            # Try equity_history last entry (includes unrealized PnL)
            eq_hist = state.get("equity_history", [])
            if eq_hist and "equity" in eq_hist[-1]:
                equity = eq_hist[-1]["equity"]
            else:
                equity = state.get("equity", state.get("capital", 0))
            return {"name": name, "status": "OK", "equity": equity}
        return {"name": name, "status": "OK", "equity": None}

    except Exception as e:
        tb = traceback.format_exc()
        return {"name": name, "status": "ERROR", "error": str(e), "traceback": tb}


def run_all():
    log("=" * 60)
    log("Paper trade orchestrator starting")

    results = []
    for name, path in RUNNERS:
        log(f"Running {name}...")
        result = run_single(name, path)
        if result["status"] == "OK":
            eq = result.get("equity")
            eq_str = f"${eq:,.2f}" if eq else "N/A"
            log(f"  {name}: OK (equity: {eq_str})")
        else:
            log(f"  {name}: {result['status']} — {result.get('error', '')}")
            if "traceback" in result:
                for line in result["traceback"].strip().split("\n"):
                    log(f"    {line}")
        results.append(result)

    # Summary
    ok = sum(1 for r in results if r["status"] == "OK")
    total = len(results)
    total_equity = sum(r.get("equity", 0) or 0 for r in results if r["status"] == "OK")
    log(f"Complete: {ok}/{total} runners OK. Total equity: ${total_equity:,.2f}")

    # Run demo portfolio runner (Bybit demo execution)
    log("Running demo portfolio runner...")
    demo_runner = ROOT / "scripts" / "demo_portfolio_runner.py"
    try:
        r = subprocess.run(
            [sys.executable, str(demo_runner)],
            capture_output=True, text=True, timeout=120,
        )
        for line in (r.stdout + r.stderr).strip().splitlines():
            log(f"  [demo] {line}")
        if r.returncode != 0:
            log(f"  [demo] exited with code {r.returncode}")
    except Exception as e:
        log(f"  [demo] failed: {e}")

    log("=" * 60)
    return results


if __name__ == "__main__":
    run_all()
