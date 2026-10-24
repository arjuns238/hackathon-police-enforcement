"""Smoke test of the Qwen server before any sting game (notes/12, "Pilot and gates", step 1). Paid (Modal GPU time).

Needs the server deployed (modal_gpu/serve_qwen.py) and QWEN_API_KEY / QWEN_BASE_URL in .env. Checks, in order:
  1. /v1/models answers with the key and refuses without it.
  2. A submit_verdict call (nested list of objects) round-trips intact, under tool_choice "required" and "auto",
     through the game's own call path; reasoning comes back separately from the answer.
  3. One request longer than 150 s through LiteLLM (Modal answers those with a 303 redirect).
  4. Throughput with 8 requests at once.
  5. One baseline episode with 4 Qwen workers: verdicts filled in for lack of a call, dropped no-tool-call turns,
     longest reasoning, outputs at the token cap, wall time.

Usage: vendor/agent-collusion/.venv/bin/python scripts/smoke_qwen.py [--skip-episode] [--only episode] [--out DIR]
The episode check writes baseline game 1 (results/qwen_sting/arm1_game1): asri's game. Teammates run with
--skip-episode.
Writes results/qwen_sting_smoke/smoke_report.json.
"""
import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "vendor" / "agent-collusion"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT / "src"))
os.chdir(REPO)

import certifi  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

MODEL = "openai/qwen3.8-27b"
OUT = ROOT / "results" / "qwen_sting_smoke"  # --out changes it (a teammate: results/qwen_sting_smoke_<name>)
CAP = 64_000


def setup_env() -> None:
    load_dotenv(REPO / ".env")
    for var in ("QWEN_API_KEY", "QWEN_BASE_URL"):
        if not os.environ.get(var):
            sys.exit(f"{var} is missing from .env")
    os.environ["OPENAI_API_KEY"] = os.environ["QWEN_API_KEY"]
    os.environ["OPENAI_BASE_URL"] = os.environ["OPENAI_API_BASE"] = os.environ["QWEN_BASE_URL"]
    os.environ.setdefault("PEERCHECK_FIXED_TOOLS", "1")
    import litellm
    litellm.request_timeout = 1800


def check_models() -> dict:
    url = os.environ["QWEN_BASE_URL"].rstrip("/") + "/models"
    def get(key):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"} if key else {})
        try:
            ctx = ssl.create_default_context(cafile=certifi.where())  # the venv Python has no system CAs
            with urllib.request.urlopen(req, timeout=1800, context=ctx) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, None
    t0 = time.time()
    code, body = get(os.environ["QWEN_API_KEY"])  # the first call may wait for a cold start (~5 min)
    names = [m["id"] for m in (body or {}).get("data", [])]
    code_nokey, _ = get(None)
    return {"with_key": code, "models": names, "without_key": code_nokey, "seconds": round(time.time() - t0, 1),
            "pass": code == 200 and "qwen3.8-27b" in names and code_nokey in (401, 403)}


def check_verdict_tool(tool_choice: str) -> dict:
    from experiments.agents import _decoded_tool_arguments
    from peer_check.game import _submit_verdict_schema, real_llm_call
    usage: list = []
    messages = [
        {"role": "system", "content": "You are Alice, a worker. Use the tools you are given."},
        {"role": "user", "content": "Submit your verdicts now with submit_verdict: accept Bob, reject Carol, accept "
                                    "Dave, each with a one-sentence reasoning."}]
    t0 = time.time()
    assistant, tool_calls, trace = real_llm_call(
        model=MODEL, effort="default", messages=messages, tools=[_submit_verdict_schema("alice")],
        accept_tool_calls=True, usage_recorder=usage.append, max_output_tokens=CAP, temperature=1.0,
        tool_choice=tool_choice)
    got = {}
    for tc in tool_calls or []:
        args = _decoded_tool_arguments(tc["function"]["arguments"])  # as game.py calls it
        for v in (args or {}).get("verdicts", []):
            if isinstance(v, dict):
                got[str(v.get("worker", "")).lower()] = str(v.get("verdict", "")).lower()
    content = assistant.get("content") or ""
    (OUT / f"verdict_{tool_choice}_raw.json").write_text(json.dumps(
        {"assistant": assistant, "tool_calls": tool_calls, "trace": trace}, indent=1, default=str))
    return {"tool_choice": tool_choice, "tool_calls": len(tool_calls or []), "verdicts": got,
            "reasoning_chars": len(str(trace or "")), "think_tag_in_content": "<think>" in content,
            "seconds": round(time.time() - t0, 1),
            "pass": got == {"bob": "accept", "carol": "reject", "dave": "accept"} and bool(trace)
                    and "<think>" not in content}


def check_long_request() -> dict:
    import litellm
    t0 = time.time()
    r = litellm.completion(model=MODEL, temperature=1.0, max_tokens=24_000, messages=[{"role": "user", "content": (
        "Write out every whole number from 1 to 3000 in order, separated by single spaces, with nothing else. "
        "After the last number, write DONE.")}])
    text = r.choices[0].message.content or ""
    secs = time.time() - t0
    (OUT / "long_request_raw.json").write_text(json.dumps(r.model_dump(), indent=1, default=str))
    # What is tested is Modal's redirect: a request over 150 s must come back whole. Whether the count reaches DONE
    # depends on how long the model thinks first (at xhigh it used up the 24,000-token cap; 2026-10-24).
    return {"seconds": round(secs, 1), "completion_tokens": r.usage.completion_tokens,
            "finish_reason": r.choices[0].finish_reason, "ends_with_done": text.strip().endswith("DONE"),
            "over_150s": secs > 150, "pass": secs > 150 and bool(text.strip()),
            "note": "inconclusive: finished in under 150 s" if secs <= 150 else ""}


def check_throughput(n: int = 8) -> dict:
    import litellm
    def one(i):
        r = litellm.completion(model=MODEL, temperature=1.0, max_tokens=6000, messages=[{"role": "user", "content": (
            f"Story {i}: write a 500-word short story about a lighthouse keeper.")}])
        return r.usage.completion_tokens
    t0 = time.time()
    with ThreadPoolExecutor(n) as pool:
        toks = list(pool.map(one, range(n)))
    secs = time.time() - t0
    return {"requests": n, "completion_tokens": sum(toks), "seconds": round(secs, 1),
            "tokens_per_second": round(sum(toks) / secs, 1)}


def check_episode() -> dict:
    # Written straight into baseline game 1: the pilot reruns that folder with --episodes 6 and resumes after this
    # episode, so it is not paid for twice. If the smoke test changes any setting, move the folder aside (not delete).
    out = ROOT / "results" / "qwen_sting" / "arm1_game1"
    t0 = time.time()
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_peer_check.py"), "--model", MODEL, "--arm", "1",
                           "--game", "1", "--episodes", "1", "--out", str(out), "--quiet"],
                          capture_output=True, text=True)
    secs = time.time() - t0
    if proc.returncode != 0:
        return {"pass": False, "error": proc.stderr[-1500:]}
    run = json.loads((out / "run.json").read_text())
    e = run["results"][0]
    filled = sum("(no verdict submitted" in v.get("reasoning", "")
                 for w in e["verdict_reasoning"].values() for v in w.values())
    dropped = sum(1 for ev in e["events"] if ev.get("dropped_no_tool_call"))
    journal = [json.loads(l) for l in (out / "llm_usage.jsonl").read_text().splitlines() if l.strip()]
    # vLLM's completion_tokens include the thinking; finish_reason "length" is the direct truncation signal.
    outs = [(j.get("raw_usage") or {}).get("completion_tokens") or j.get("provider_output_tokens") or 0
            for j in journal]
    reasoning = [j.get("reasoning_tokens") or 0 for j in journal]
    truncated = sum(j.get("finish_reason") == "length" or o >= CAP - 50 for j, o in zip(journal, outs))
    traces = e.get("reasoning_traces", [])
    return {"wall_seconds": round(secs, 1), "calls": len(journal), "verdicts_filled_in": filled, "verdicts": 12,
            "dropped_no_tool_call_turns": dropped, "max_output_tokens": max(outs, default=0),
            "mean_output_tokens": round(sum(outs) / max(len(outs), 1)), "max_reasoning_tokens": max(reasoning, default=0),
            "truncated": truncated, "finish_reasons": sorted({str(j.get("finish_reason")) for j in journal}),
            "journal_has_token_fields": all("raw_usage" in j for j in journal), "reasoning_traces_saved": len(traces),
            "total_output_tokens": sum(outs), "verdict_matrix": e.get("verdicts"),
            "pass": filled == 0 and dropped <= 0.1 * len(journal) and truncated == 0 and bool(journal)
                    and all("raw_usage" in j for j in journal)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-episode", action="store_true")
    ap.add_argument("--only", nargs="+", help="run only these checks, e.g. --only episode")
    ap.add_argument("--out", help="report folder (default results/qwen_sting_smoke)")
    args = ap.parse_args()
    global OUT
    if args.out:
        OUT = (ROOT / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    setup_env()
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    steps = [("models", check_models), ("verdict_required", lambda: check_verdict_tool("required")),
             ("verdict_auto", lambda: check_verdict_tool("auto")), ("long_request", check_long_request),
             ("throughput", check_throughput)]
    if not args.skip_episode:
        steps.append(("episode", check_episode))
    if args.only:
        steps = [st for st in steps if st[0] in args.only]
        report = json.loads((OUT / "smoke_report.json").read_text()) if (OUT / "smoke_report.json").exists() else {}
    for name, fn in steps:
        print(f"== {name} ...", flush=True)
        try:
            report[name] = fn()
        except Exception as e:  # noqa: BLE001 - record and carry on to the next check
            report[name] = {"pass": False, "error": f"{type(e).__name__}: {str(e)[:1200]}"}
        print(json.dumps(report[name], indent=1), flush=True)
        (OUT / "smoke_report.json").write_text(json.dumps(report, indent=1))
        if name == "models" and not report[name].get("pass"):
            break
    print("SMOKE DONE:", {k: v.get("pass") for k, v in report.items()})


if __name__ == "__main__":
    main()
