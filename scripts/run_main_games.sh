#!/bin/bash
# Run the main peer-check games (notes/04, amendment B: arms 1, 2, 3, 5 × games 1–3) up to N at a time.
# Restartable: re-running resumes each game after its last saved episode; finished games exit at once.
# Each game logs to results/peer_check/armA_gameG/log_main.txt; START/END lines go to results/peer_check/main_queue.log.
# Settings: notes/07_run_config.md. Usage: scripts/run_main_games.sh [N=4]
set -u
cd "$(dirname "$0")/.."
N=${1:-4}
export PEERCHECK_FIXED_TOOLS=1
# Order keeps the arms level, so a stop part-way leaves balanced data.
QUEUE="2 1
5 1
3 1
1 2
3 2
2 2
5 2
1 3
3 3
2 3
5 3"
echo "$QUEUE" | xargs -P "$N" -L 1 sh -c '
  a=$0; g=$1; d=results/peer_check/arm${a}_game${g}; mkdir -p "$d"
  echo "$(date "+%F %T") START arm$a game$g" >> results/peer_check/main_queue.log
  vendor/agent-collusion/.venv/bin/python scripts/run_peer_check.py --arm "$a" --game "$g" --episodes 6 >> "$d/log_main.txt" 2>&1
  rc=$?
  echo "$(date "+%F %T") END arm$a game$g exit $rc" >> results/peer_check/main_queue.log'
echo "QUEUE DONE"
