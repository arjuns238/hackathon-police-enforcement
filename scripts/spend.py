"""Total API spend for the project so far (budget: $150 total, hard stop $145; notes/07_run_config.md).

Sums every usage journal under results/ (the 2-worker repo games and the 4-worker peer-check games, including
offline runs, which log $0) plus fixed amounts spent outside any journal. Prints the total, or exits with an error
from `check(limit)` when a new run would start above the limit.

Usage: python3 scripts/spend.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Spent outside any llm_usage.jsonl journal (see notes/00_results_log.md).
FIXED = {"market experiment (S0-smoke, S0-A + judge, S0-B)": 12.37, "replay/probe calls outside the games": 0.30}


def journal_spend() -> dict[str, float]:
    out: dict[str, float] = {}
    for f in sorted((ROOT / "results").glob("**/llm_usage.jsonl")):
        total = 0.0
        for line in f.read_text().splitlines():
            if line.strip():
                total += json.loads(line).get("cost_usd") or 0.0
        out[str(f.parent.relative_to(ROOT))] = total
    return out


def total_spend() -> float:
    return sum(journal_spend().values()) + sum(FIXED.values())


def check(limit: float) -> float:
    spent = total_spend()
    if spent >= limit:
        sys.exit(f"Refusing to start: project spend is ${spent:.2f}, at or above the ${limit:.0f} start limit "
                 "(budget $150, hard stop $145). Ask asri.")
    return spent


if __name__ == "__main__":
    js = journal_spend()
    for k, v in FIXED.items():
        print(f"  ${v:7.2f}  {k}")
    for k, v in js.items():
        if v:
            print(f"  ${v:7.2f}  {k}")
    print(f"total ${total_spend():.2f} of $150 (hard stop $145)")
