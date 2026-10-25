"""Restart every running Qwen game right after its next saved episode, so a code fix takes effect without losing work
(notes/12 D9). Free.

Finds the running `run_peer_check.py --model openai/qwen3.8-27b ...` processes, waits for each game to save one more
episode (run.json, then messages.json), stops that process and starts the same command again with the project's venv
Python under `caffeinate -i`; the runner resumes after the saved episode. Games that finish on their own are left alone.
Output of the restarted games is appended to their console.log.

Keeps each game's own QWEN_BASE_URL (read from the running process's environment), so games on the second server
stay there. `--arms` limits it to some arms (e.g. only Dave games).

Usage: vendor/agent-collusion/.venv/bin/python scripts/restart_at_boundary.py [--arms 21 22 23 24]
"""
import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "vendor" / "agent-collusion" / ".venv" / "bin" / "python"
CHARACTER = {"21": "pushy", "22": "friendly", "23": "subtle"}


def running() -> dict[int, list[str]]:
    out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True).stdout
    procs = {}
    for line in out.splitlines():
        pid, _, cmd = line.strip().partition(" ")
        argv = cmd.split()
        if any(a.endswith("scripts/run_peer_check.py") for a in argv) and "openai/qwen3.8-27b" in argv \
                and "caffeinate" not in argv[0]:
            procs[int(pid)] = argv
    return procs


def folder(argv: list[str]) -> Path:
    opt = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
    arm, game = opt["--arm"], opt["--game"]
    cell = ("arm1" if arm == "1" else "passive" if arm == "24"
            else f"{CHARACTER[arm]}_ep{opt.get('--offer-episode', '2')}")
    return ROOT / "results" / "qwen_sting" / f"{cell}_game{game}"


def saved(d: Path) -> int:
    try:
        return len(json.loads((d / "run.json").read_text())["results"])
    except (OSError, ValueError, KeyError):
        return 0


def base_url_of(pid: int) -> str | None:
    out = subprocess.run(["ps", "eww", "-p", str(pid)], capture_output=True, text=True).stdout
    for tok in out.split():
        if tok.startswith("QWEN_BASE_URL="):
            return tok.split("=", 1)[1]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", help="only games of these arms")
    args = ap.parse_args()
    pending = {}
    for pid, argv in running().items():
        arm = argv[argv.index("--arm") + 1]
        if args.arms and arm not in args.arms:
            continue
        d = folder(argv)
        script = next(i for i, a in enumerate(argv) if a.endswith("scripts/run_peer_check.py"))
        pending[pid] = {"dir": d, "start": saved(d), "cmd": [str(PY), *argv[script:]], "url": base_url_of(pid)}
        print(f"watching {d.name} (pid {pid}, {pending[pid]['start']} episodes saved, server "
              f"{pending[pid]['url'] or 'from .env'})", flush=True)
    while pending:
        for pid, p in list(pending.items()):
            alive = subprocess.run(["kill", "-0", str(pid)], capture_output=True).returncode == 0
            if not alive:
                print(f"{p['dir'].name}: process ended by itself (game finished or stopped); not restarted", flush=True)
                del pending[pid]
                continue
            n = saved(p["dir"])
            run_f, msg_f = p["dir"] / "run.json", p["dir"] / "messages.json"
            if n > p["start"] and msg_f.exists() and msg_f.stat().st_mtime >= run_f.stat().st_mtime:
                time.sleep(3)  # let the save finish
                os.kill(pid, signal.SIGTERM)
                for _ in range(30):
                    if subprocess.run(["kill", "-0", str(pid)], capture_output=True).returncode != 0:
                        break
                    time.sleep(1)
                log = open(p["dir"] / "console.log", "a")
                env = {**os.environ, **({"QWEN_BASE_URL": p["url"]} if p["url"] else {})}
                new = subprocess.Popen(["caffeinate", "-i", *p["cmd"]], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True, env=env)
                print(f"{p['dir'].name}: restarted after episode {n} (new pid {new.pid})", flush=True)
                del pending[pid]
        time.sleep(5)
    print("ALL RESTARTED")


if __name__ == "__main__":
    main()
