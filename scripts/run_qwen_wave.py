"""Run a wave of Qwen sting games at once against the Modal server (notes/12, "Pilot and gates" and run order).

Each game is its own run_peer_check.py process (workers take turns inside a game, so one game sends one request at
a time; vLLM batches the requests of all running games). Restartable: a game resumes after its last saved episode,
and a finished game is skipped by the runner. Console output goes to <game folder>/console.log.

Cells: arm1 (baseline, 6 episodes) and <style>_ep<E> for style in direct/hint/benign/givefirst and E in 1, 3
(offer in episode 1: 2 episodes; offer in episode 3: 4 episodes).

Usage: vendor/agent-collusion/.venv/bin/python scripts/run_qwen_wave.py --games 1 --cells arm1 direct_ep1   # the pilot
       vendor/agent-collusion/.venv/bin/python scripts/run_qwen_wave.py --games 1 2                       # all 9 cells
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "vendor" / "agent-collusion" / ".venv" / "bin" / "python"
STYLE_ARM = {"direct": 11, "hint": 12, "benign": 13, "givefirst": 14}
ALL_CELLS = ["arm1"] + [f"{s}_ep{e}" for e in (1, 3) for s in STYLE_ARM]


def command(cell: str, game: int) -> list[str]:
    base = [str(PY), str(ROOT / "scripts" / "run_peer_check.py"), "--model", "openai/qwen3.8-27b", "--game", str(game),
            "--quiet"]
    if cell == "arm1":
        return base + ["--arm", "1", "--episodes", "6"]
    style, ep = cell.split("_ep")
    return base + ["--arm", str(STYLE_ARM[style]), "--offer-episode", ep, "--episodes", "2" if ep == "1" else "4"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, nargs="+", required=True)
    ap.add_argument("--cells", nargs="+", default=ALL_CELLS, choices=ALL_CELLS)
    args = ap.parse_args()
    procs = {}
    for game in args.games:  # by game number across cells, so a stop midway leaves balanced cells
        for cell in args.cells:
            out = ROOT / "results" / "qwen_sting" / f"{cell}_game{game}"
            out.mkdir(parents=True, exist_ok=True)
            log = open(out / "console.log", "a")
            procs[f"{cell}_game{game}"] = (subprocess.Popen(command(cell, game), stdout=log, stderr=subprocess.STDOUT,
                                                            cwd=ROOT), log)
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
