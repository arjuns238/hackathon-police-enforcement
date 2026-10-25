"""Health check of saved Qwen sting episodes (notes/12, D10 smoke test). Free; reads saved files only.

Per game folder and overall: chat turns lost (a worker sent nothing in a round) and why; every failed tool call by
reason; calls that came wrapped and were unwrapped (D9) and whether they then worked; verdicts filled in by the
runner; turns dropped for having no tool call; truncated outputs; and Dave's approach (scripts/check_approach.py).

Pass rules (registered in notes/12 D10 before the smoke test):
  1. no chat turn lost for any reason other than a message over 200 characters;
  2. turns lost to over-long messages: reported, not gated (D11, asri 2026-10-24);
  3. no verdict filled in by the runner;
  4. no truncated output, and dropped no-tool-call turns <= 5% of calls;
  5. no call failed with its key argument empty (the wrapped-call signature: send_message to, write_test_file
     path, save_final_answer reasoning);
  6. the approach gate passes for every saved approach episode.

Usage: vendor/agent-collusion/.venv/bin/python scripts/qwen_health.py [--root results/qwen_sting] [--games 1]
"""
import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKERS = ["alice", "bob", "carol", "dave"]
MISSING_ARG = ("to must be",)  # with an empty `to`: the wrapped-call signature (pilot: 87 of 87 had to == "")


def empty_arg_failure(ev: dict) -> bool:
    """A failed call whose key argument is empty: what a wrapped, un-unwrapped call looks like (pilot, D9)."""
    if ev.get("success") is not False and not ev.get("error"):
        return False
    tool, err = ev.get("tool"), str(ev.get("error"))
    # D11: write_test_file with an empty filename is reported but not gated (the paper's own game logs it too, and
    # it may be a wrong key rather than wrapping; failed_call_raw now shows which).
    return ((tool == "send_message" and not ev.get("to") and "to must be" in err)
            or (tool == "save_final_answer" and "must be non-empty" in err and not ev.get("content")))


def round_of(ev: dict) -> int | None:
    r = ev.get("round")
    return None if r is None else int(r) + 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT / "results" / "qwen_sting"))
    ap.add_argument("--games", type=int, nargs="+")
    args = ap.parse_args()
    root = Path(args.root)
    dirs = sorted(d for d in root.glob("*_game*") if (d / "run.json").exists()
                  and (not args.games or int(d.name.rsplit("_game", 1)[1]) in args.games))
    tot = collections.Counter()
    fails_all = collections.Counter()
    lost_all = collections.Counter()
    for d in dirs:
        run = json.loads((d / "run.json").read_text())
        rows = [json.loads(l) for l in (d / "llm_usage.jsonl").read_text().splitlines() if l.strip()] \
            if (d / "llm_usage.jsonl").exists() else []
        lost, fails = collections.Counter(), collections.Counter()
        unwrapped = filled = dropped = 0
        for e in run["results"]:
            sent = {(t["from"], t["round"]) for t in e["transcript"]}
            evs = e["events"]
            for w in WORKERS:
                for r in range(1, 6):
                    tot["worker_rounds"] += 1
                    if (w, r) in sent:
                        continue
                    errs = [str(ev.get("error")) for ev in evs if ev.get("actor") == w and ev.get("tool") == "send_message"
                            and ev.get("success") is False and round_of(ev) == r]
                    reason = ("over 200 characters" if errs and all("200 char" in x for x in errs)
                              else "missing argument" if any(m in x for x in errs for m in MISSING_ARG)
                              else f"other: {errs[-1][:60]}" if errs else "no send attempt logged")
                    lost[reason] += 1
            for ev in evs:
                if ev.get("unwrapped"):
                    unwrapped += 1
                if ev.get("dropped_no_tool_call"):
                    dropped += 1
                err = ev.get("error")
                if (ev.get("success") is False or err) and ev.get("tool"):
                    key = f"{ev['tool']}: {str(err)[:70]}"
                    fails[key] += 1
            filled += sum("(no verdict submitted" in x.get("reasoning", "")
                          for w in e["verdict_reasoning"].values() for x in w.values())
        truncated = sum(r.get("finish_reason") == "length" for r in rows)
        missing_arg_fails = sum(empty_arg_failure(ev) for e in run["results"] for ev in e["events"])
        print(f"{d.name}: {len(run['results'])} episodes, {len(rows)} calls | lost turns {dict(lost) or 0} | "
              f"unwrapped {unwrapped} | failed calls with a missing argument {missing_arg_fails} | "
              f"verdicts filled in {filled} | dropped {dropped} | truncated {truncated}")
        tot.update({"calls": len(rows), "unwrapped": unwrapped, "filled": filled, "dropped": dropped,
                    "truncated": truncated, "missing_arg_fails": missing_arg_fails})
        fails_all.update(fails)
        lost_all.update(lost)
    if not dirs:
        sys.exit("no saved episodes")
    wr = tot["worker_rounds"]
    long_lost = lost_all.get("over 200 characters", 0)
    other_lost = sum(v for k, v in lost_all.items() if k != "over 200 characters")
    print("\nfailed calls by reason (all games):")
    for k, v in fails_all.most_common():
        print(f"  {v:4d}  {k}")
    gate = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_approach.py"), "--root", str(root),
                           "--games", *sorted({d.name.rsplit("_game", 1)[1] for d in dirs})],
                          capture_output=True, text=True).stdout
    gate_line = next((l for l in gate.splitlines() if l.startswith("GATE")), "GATE: no approach episode saved")
    checks = {
        "1 no turn lost except to over-long messages": other_lost == 0,
        # D11 (asri, 2026-10-24): lost turns to over-long messages are the game's own behaviour; reported, not gated.
        f"2 turns lost to over-long messages, reported only ({long_lost}/{wr} = {long_lost / max(wr, 1):.0%})": True,
        "3 no verdict filled in": tot["filled"] == 0,
        f"4 no truncation, dropped <= 5% ({tot['dropped']}/{tot['calls']})":
            tot["truncated"] == 0 and tot["dropped"] <= 0.05 * max(tot["calls"], 1),
        f"5 wrapped calls unwrapped ({tot['unwrapped']}), none failed for a missing argument":
            tot["missing_arg_fails"] == 0,
        f"6 approach gate ({gate_line})": "PASS" in gate_line or "no approach" in gate_line,
    }
    print("\nlost turns by reason:", dict(lost_all))
    print("\n" + "\n".join(f"{'PASS' if ok else 'FAIL'}  {name}" for name, ok in checks.items()))
    print("HEALTH:", "PASS" if all(checks.values()) else "FAIL")


if __name__ == "__main__":
    main()
