"""Run a wave of Qwen sting games at once against the Modal server (notes/12, "Pilot and gates" and run order).

Each game is its own run_peer_check.py process (workers take turns inside a game, so one game sends one request at
a time; vLLM batches the requests of all running games). Restartable: a game resumes after its last saved episode,
and a finished game is skipped by the runner. Console output goes to <game folder>/console.log.

Cells (notes/12, amendment C): arm1 (baseline), passive (Dave never approaches), and <character>_ep<E> for
character in pushy/friendly/subtle and E in 1, 3 (Dave's approach episode). Every game is 4 episodes (D5).

Usage: vendor/agent-collusion/.venv/bin/python scripts/run_qwen_wave.py --games 1 --cells arm1 pushy_ep1    # the pilot
       vendor/agent-collusion/.venv/bin/python scripts/run_qwen_wave.py --games 1 2                       # all 8 cells
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "vendor" / "agent-collusion" / ".venv" / "bin" / "python"
CHARACTER_ARM = {"pushy": 21, "friendly": 22, "subtle": 23}
ALL_CELLS = ["arm1", "passive"] + [f"{c}_ep{e}" for e in (1, 3) for c in CHARACTER_ARM]


def command(cell: str, game: int) -> list[str]:
    base = [str(PY), str(ROOT / "scripts" / "run_peer_check.py"), "--model", "openai/qwen3.8-27b", "--game", str(game),
            "--quiet"]
    # Every game is 4 episodes (asri, 2026-10-24; notes/12 D5).
    if cell == "arm1":
        return base + ["--arm", "1", "--episodes", "4"]
    if cell == "passive":
        return base + ["--arm", "24", "--episodes", "4"]
    character, ep = cell.split("_ep")
    return base + ["--arm", str(CHARACTER_ARM[character]), "--offer-episode", ep, "--episodes", "4"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, nargs="+", required=True)
    ap.add_argument("--cells", nargs="+", default=ALL_CELLS, choices=ALL_CELLS)
    ap.add_argument("--episodes", type=int, help="override the 4 episodes (smoke test: 1; resumed later with 4)")
    ap.add_argument("--offline", action="store_true", help="fake model, results/qwen_sting_offline/ (free)")
    args = ap.parse_args()
    procs = {}
    for game in args.games:  # by game number across cells, so a stop midway leaves balanced cells
        for cell in args.cells:
            out = ROOT / "results" / ("qwen_sting_offline" if args.offline else "qwen_sting") / f"{cell}_game{game}"
            out.mkdir(parents=True, exist_ok=True)
            log = open(out / "console.log", "a")
            cmd = command(cell, game)
            if args.episodes:
                cmd[cmd.index("--episodes") + 1] = str(args.episodes)
            if args.offline:
                cmd.append("--offline")
            procs[f"{cell}_game{game}"] = (subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT), log)
            print(f"started {cell}_game{game}", flush=True)
            time.sleep(2)  # stagger the first requests
    failed = []
    while procs:
        for name, (p, log) in list(procs.items()):
            if p.poll() is not None:
                log.close()
                print(f"{'finished' if p.returncode == 0 else f'FAILED (exit {p.returncode})'} {name}", flush=True)
                if p.returncode:
                    failed.append(name)
                del procs[name]
        time.sleep(20)
    print("failed:", failed or "none")
    print("BATCH DONE")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
