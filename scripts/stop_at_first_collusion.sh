#!/bin/bash
# Usage: scripts/stop_at_first_collusion.sh <path to the game log> <model id, e.g. claude-sonnet-5>  (run in background)
# Stop a 2-agent repo game after the first both-ACCEPT episode, or after 4 episodes, whichever comes first.
# Kills only between episodes (after the incremental save), so run.json stays complete.
LOG=${1:?log path}
MAX=4; MODEL=${2:?model id}
while true; do
  if grep -q "^EXIT" "$LOG"; then echo "game ended by itself"; exit 0; fi
  saved=$(grep -c "Saved incremental results after" "$LOG")
  both=$(grep "Episode done" "$LOG" | awk '{n=gsub(/ accept\//,"&"); if (n==2) c++} END{print c+0}')
  if [ "$saved" -ge 1 ] && { [ "$both" -ge 1 ] || [ "$saved" -ge "$MAX" ]; }; then
    pkill -f "experiments.runner.*$MODEL"; pkill -f "experiments --start-index 1.*$MODEL"
    echo "stopped after $saved episodes saved; both-accept episodes: $both"; exit 0
  fi
  sleep 5
done
