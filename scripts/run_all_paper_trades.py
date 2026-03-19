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
    ("H-024", ROOT / "paper_trades" / "h024_beta" / "runner.py"),
    ("H-031", ROOT / "paper_trades" / "h031_size" / "runner.py"),
    ("H-032", ROOT / "paper_trades" / "h032_pairs" / "runner.py"),
]

LOG_FILE = ROOT / "logs" / "paper_trades.log"


def log(msg: str):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{timestamp}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def run_single(name: str, runner_path: Path) -> dict:
    """Import and run a single paper trade runner. Returns result dict."""
    if not runner_path.exists():
        return {"name": name, "status": "MISSING", "error": f"{runner_path} not found"}

    try:
        spec = importlib.util.spec_from_file_location(f"runner_{name}", runner_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.run()

        # Read state to report equity
        state_file = runner_path.parent / "state.json"
        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)
            equity = state.get("capital", state.get("equity", 0))
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
    log("=" * 60)

    return results


if __name__ == "__main__":
    run_all()
