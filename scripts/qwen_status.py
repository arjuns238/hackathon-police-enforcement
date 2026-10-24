"""Status of Qwen sting games: episodes saved, completeness and health, per game folder. Free; reads saved files only.

Per game: episodes saved of 4 and the `complete` flag; mutual-accept pairs per episode (of 6); verdicts filled in for
lack of a call; truncated outputs (finish_reason "length"); thinking traces saved. Ends with "ALL COMPLETE" when every
listed game has its 4 episodes.

Usage: vendor/agent-collusion/.venv/bin/python scripts/qwen_status.py [--games 3 4] [--root results/qwen_sting]
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKERS = ["alice", "bob", "carol", "dave"]
CELLS = ["arm1", "passive"] + [f"{c}_ep{e}" for e in (1, 3) for c in ("pushy", "friendly", "subtle")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--root", default=str(ROOT / "results" / "qwen_sting"))
    args = ap.parse_args()
    root, all_complete, seen = Path(args.root), True, 0
    for g in args.games:
        for cell in CELLS:
            d = root / f"{cell}_game{g}"
            if not (d / "run.json").exists():
                calls = len((d / "llm_usage.jsonl").read_text().splitlines()) if (d / "llm_usage.jsonl").exists() else 0
                print(f"{cell}_game{g}: " + (f"in episode 1, nothing saved yet ({calls} calls so far)" if calls
                                              else "not started"))
                all_complete = False
                continue
            seen += 1
            run = json.loads((d / "run.json").read_text())
            eps = run["results"]
            mutual = []
            for e in eps:
                v = e["verdicts"]
                mutual.append(sum(v[a][b] == "accept" and v[b][a] == "accept"
                                  for i, a in enumerate(WORKERS) for b in WORKERS[i + 1:]))
            filled = sum("(no verdict submitted" in x.get("reasoning", "")
                         for e in eps for w in e["verdict_reasoning"].values() for x in w.values())
            journal = d / "llm_usage.jsonl"
            rows = [json.loads(l) for l in journal.read_text().splitlines() if l.strip()] if journal.exists() else []
            truncated = sum(r.get("finish_reason") == "length" for r in rows)
            traces = sum(len(e.get("reasoning_traces", [])) for e in eps)
            done = len(eps) >= 4
            all_complete &= done
            print(f"{cell}_game{g}: {len(eps)}/4 episodes{' (complete)' if done else ''}; mutual-accept pairs per "
                  f"episode {mutual}; verdicts filled in {filled}; truncated {truncated}; calls {len(rows)}; "
                  f"thinking traces {traces}")
    print("ALL COMPLETE" if all_complete and seen else "NOT ALL COMPLETE")


if __name__ == "__main__":
    main()
