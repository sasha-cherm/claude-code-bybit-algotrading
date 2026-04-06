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
