#!/bin/bash
# Crontab entry: 0 */4 * * * /home/cctrd/cc-bybit-algotrading/scripts/session.sh
# Launches a Claude Code session in the project directory.

set -euo pipefail

PROJECT_DIR="/home/cctrd/cc-bybit-algotrading"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date '+%Y-%m-%d_%H-%M')
LOGFILE="$LOG_DIR/session_$TIMESTAMP.log"

echo "[$(date)] Starting Claude trading session..." | tee -a "$LOGFILE"

cd "$PROJECT_DIR"

# Launch Claude Code non-interactively with the session prompt
claude --print "
You are the autonomous trading research agent for this project.
Follow the Session Protocol in CLAUDE.md exactly.
Start by loading context (MEMORY.md, memory/state.md, memory/hypotheses.md, questions/USER_QA.md).
Then pick a session goal and execute it.
End by updating all state files and appending to MEMORY.md.
" 2>&1 | tee -a "$LOGFILE"

echo "[$(date)] Session complete." | tee -a "$LOGFILE"
