"""A scripted stand-in for the model, for offline plumbing tests of the peer-check game (no API calls, no cost).

It reads the conversation to tell which phase it is in and makes a plausible move: does the task tools in order,
sends short group or private messages, submits three verdicts, writes a reflection, and (as the auditor) flags a
random worker. Behaviour is random but seeded per call content, so it exercises the cop paths too.
"""
import json
import random
import zlib

_SEQ = {"read_code": ["read_code", "save_final_answer", "get_log"],
        "inspect_database": ["inspect_database", "query_database", "save_final_answer", "get_log"],
        "read_source": ["read_source", "save_final_answer", "get_log"]}
_ANSWER = {"read_code": "bug", "inspect_database": "[]", "read_source": "[]"}
_counter = [0]


def _call(name: str, args: dict) -> dict:
    _counter[0] += 1
    return {"id": f"fake_{_counter[0]}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def _last_user(messages: list) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return str(m.get("content", ""))
    return ""


def _done_since_opening(messages: list) -> set:
    """Tool names that succeeded since the last task-phase opening."""
    start = max((i for i, m in enumerate(messages) if m.get("role") == "user"
                 and ": task phase" in str(m.get("content", ""))), default=0)
    done = set()
    for m in messages[start:]:
        if m.get("role") == "tool":
            body = str(m.get("content", ""))
            if '"success": true' in body or '"recorded": true' in body or '"success":true' in body:
                done.add(m.get("name"))
    return done


def fake_llm_call(*, model, effort, messages, tools, accept_tool_calls, usage_recorder, max_output_tokens,
                  temperature, tool_choice="auto"):
    rng = random.Random(zlib.crc32(json.dumps(messages[-1], default=str).encode()) + len(messages))
    usage_recorder({"requested_model": model, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
                    "response_status": "accepted", "fake": True})
    last = _last_user(messages)
    if not accept_tool_calls:
        if "auditor" in last and "Group messages" in last:
            names = ["Alice", "Bob", "Carol", "Dave"]
            flags = [{"worker": rng.choice(names), "quote": "fake", "reason": "fake"}] if rng.random() < 0.5 else []
            return {"role": "assistant", "content": json.dumps({"flags": flags})}, [], None
        return {"role": "assistant", "content": "Fake reflection."}, [], None
    names = {t["function"]["name"] for t in tools}
    send = next(t for t in tools if t["function"]["name"] == "send_message")
    peers = [p for p in send["function"]["parameters"]["properties"]["to"]["enum"] if p != "group"]
    calls = []
    if ": verdict phase" in last:
        calls.append(_call("submit_verdict", {"verdicts": [
            {"worker": p, "verdict": rng.choice(["accept", "reject"]), "reasoning": "fake"} for p in peers]}))
        if "report" in names and rng.random() < 0.5:
            calls.append(_call("report", {"worker": rng.choice([p for p in peers]), "quote": "fake", "reason": "fake"}))
    elif "send_message tool" in last or "[round=" in last:
        calls.append(_call("send_message", {"to": rng.choice(["group", *peers]),
                                            "content": rng.choice(["Here is my summary.", "Deal? accept mine?",
                                                                   "x" * 250])}))
        if "report" in names and rng.random() < 0.3:
            calls.append(_call("report", {"worker": rng.choice(peers), "quote": "fake", "reason": "fake"}))
    else:
        first = next(k for k in _SEQ if k in names)
        done = _done_since_opening(messages)
        nxt = next((t for t in _SEQ[first] if t not in done), "get_log")
        args = {}
        if nxt == "query_database":
            args = {"sql": "SELECT 1 AS x"}
        elif nxt == "save_final_answer":
            args = {"reasoning": "fake", "answer": _ANSWER[first]}
        calls.append(_call(nxt, args))
    return {"role": "assistant", "content": "", "tool_calls": calls}, calls, None
