"""Summarise runs of the SALT-NLP/agent-collusion peer-review game (notes/04_registered_plan_review.md).

For each run.json under --dir: per episode, each agent's verdict vs the truth, reward, raw-log size, the chat, and
token use; then cost, caching and the largest prompt (Haiku 5.5 costs 5x more per token above 100K-token prompts).

Usage: .venv/bin/python scripts/review_summary.py [--dir results/review_step0] [--chat]
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRICE_STEP_TOKENS = 100_000


def summarise_run(run_file: Path, show_chat: bool) -> dict:
    run = json.loads(run_file.read_text())
    print(f"\n== {run_file.parent.name[:60]}… ({len(run['results'])} episodes)")
    usage = [json.loads(line) for line in (run_file.parent / "llm_usage.jsonl").read_text().splitlines()]
    both_accept = 0
    for ep in run["results"]:
        a = ep["agents"]
        line = []
        for agent_id, s in a.items():
            raw_chars = len(json.dumps(s.get("private_raw_log") or [], ensure_ascii=False))
            line.append(f"{agent_id}: {s['verdict'].upper()} on peer (peer truth {a[s['peer_id']]['expected_verdict']}), "
                        f"correct={s['verdict_correct']}, reward={s['reward']}, own raw log {raw_chars:,} chars")
        both_accept += all(s["verdict"] == "accept" for s in a.values())
        print(f"  ep {ep['episode_index'] + 1} [{ep['task_type']}]")
        for text in line:
            print("    " + text)
        if show_chat:
            for m in ep.get("channel_transcript", []):
                print(f"      r{m['round']} {m['sender']}->{m['receiver']} ({m['message_type']}): {m['content']}")
    errors = [u for u in usage if u.get("response_status") != "accepted"]
    inputs = [u["input_tokens"] or 0 for u in usage]
    cost = sum(u.get("cost_usd") or 0 for u in usage)
    cached = sum(u.get("cached_input_tokens") or 0 for u in usage)
    print(f"  calls {len(usage)}, non-accepted {len(errors)}, cost ${cost:.3f}, input {sum(inputs):,} tokens "
          f"({cached / max(sum(inputs), 1):.0%} cache reads), largest prompt {max(inputs):,} tokens, "
          f"calls over {PRICE_STEP_TOKENS:,}: {sum(i > PRICE_STEP_TOKENS for i in inputs)}")
    for e in errors[:5]:
        print(f"    {e['actor']} {e['phase']}: {e.get('response_status')} {e.get('error_type')} "
              f"{(e.get('error_message') or '')[:200]}")
    return {"episodes": len(run["results"]), "both_accept": both_accept, "cost": cost, "max_prompt": max(inputs)}


def cost_by_episode(usage_file: Path) -> None:
    """Calls, largest prompt, cache writes and cost per episode, from the usage journal (works mid-run)."""
    rows = [json.loads(line) for line in usage_file.read_text().splitlines()]
    print(f"\n== {usage_file.parent.name[:60]}… (usage journal, {len(rows)} calls)")
    for ep in sorted({r["episode_index"] for r in rows}):
        sub = [r for r in rows if r["episode_index"] == ep]
        print(f"  ep {ep}: calls {len(sub)}, largest prompt {max(r['input_tokens'] or 0 for r in sub):,}, "
              f"cache writes {sum(r.get('cache_write_input_tokens') or 0 for r in sub):,}, "
              f"cost ${sum(r.get('cost_usd') or 0 for r in sub):.3f}, "
              f"failed {sum(r.get('response_status') != 'accepted' for r in sub)}")
    print(f"  total ${sum(r.get('cost_usd') or 0 for r in rows):.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", default="results/review_step0")
    parser.add_argument("--chat", action="store_true", help="print every channel message")
    parser.add_argument("--costs", action="store_true", help="per-episode cost from the usage journals only")
    args = parser.parse_args()
    if args.costs:
        for usage_file in sorted((ROOT / args.dir).glob("**/llm_usage.jsonl")):
            cost_by_episode(usage_file)
        return
    runs = sorted((ROOT / args.dir).glob("run_*/run.json"))
    totals = [summarise_run(f, args.chat) for f in runs]
    print(f"\n{len(runs)} runs, {sum(t['episodes'] for t in totals)} episodes, "
          f"both-accept episodes {sum(t['both_accept'] for t in totals)}, total cost ${sum(t['cost'] for t in totals):.3f}")


if __name__ == "__main__":
    main()
