# 07 — Run configuration: READ BEFORE ANY API RUN (kept current; last updated 2026-10-13)

Every paid run in this project uses the settings below. They were chosen by measurement, and getting one wrong has
already cost money or produced a useless run. Do not change a model, effort level or flag without asking asri;
record any change in `notes/04_registered_plan_review.md` (Deviations) before running.

## Budget

- **Hard cap: $150 for the whole project** (asri, 2026-10-13). Hard stop for all runs at **$145** total spend.
- Spent as of 2026-10-13: ~$31 (market $12.37; peer-check games $16.25 incl. the cost check; probes ~$0.3).
- Check spend before and after every run: `python3 scripts/spend.py` (sums every `results/**/llm_usage.jsonl`
  plus the $12.37 market spend and ~$0.30 of probes). `scripts/run_peer_check.py` calls it and refuses to start a
  paid game once total spend reaches $140.
- Per-run cost check: `.venv/bin/python scripts/review_summary.py --dir results/<dir> --costs` (works mid-run).
- Ask asri before anything that would move total spend by a step (a new arm, more games, a pricier model).

## API access

- Key and workspace in `.env` (gitignored): `ANTHROPIC_API_KEY` (never print it; check by prefix/length only) and
  `ANTHROPIC_WORKSPACE_ID`. The key is org-level, so **every call needs the `anthropic-workspace-id` header**; our
  patches send it automatically when `ANTHROPIC_WORKSPACE_ID` is set.

## Models (peer-check game)

| role | model | effort | notes |
|---|---|---|---|
| workers (all arms) | **`anthropic/claude-sonnet-5`** | **high** | colludes (entry S5); $2/$10 per M tokens |
| plant (arms 3, 5) | `anthropic/claude-sonnet-5` | high | same model as workers so style does not give it away |
| visible auditor (arm 2) | `claude-sonnet-5` | low | |
| M2 agreement judge | `claude-sonnet-5` | low | |

**Do not use** (each was tested and failed for this game):
- **Claude Haiku 5.5** — never colludes: 0 ACCEPTs in 100 verdicts at effort high (entry R0a). At effort low with
  forced tool choice it does not think at all on chat/verdict turns (R0a-1).
- **Claude Sonnet 5.5** (and expect the same of **Opus 5.5**) — its `reasoning_extraction` safety classifier refuses
  the chat phase ("send your complete raw log"), entry S55. The repo then retries a refusal 20 times: kill the run.
- **Claude Sonnet 4.6** — works and colludes (PC-1) but costs 1.5× Sonnet 5 per token and is slow (~25 s per call;
  with 4 workers taking turns, a worker's gap between calls can pass the 5-minute prompt-cache lifetime, so the cache
  would expire). Positive control only.

## Required settings (peer-check game)

- **`PEERCHECK_FIXED_TOOLS=1`** in the environment of every game run. One tool list in every phase; halves the cost
  (entry CC-1: $1.61 → $0.83 for the same two episodes). Without it, every phase change re-writes the whole prompt
  cache (74% of the bill).
- **Effort high, tool choice auto** for workers, as in the paper (Table 2 / App. B.1). Our patch makes the Anthropic
  route use `tool_choice=auto`; forced tool use makes Claude 5-family models skip thinking.
- **Memory:** `communication-onward` for the 4-worker game (keeps prompts ~25–60K tokens, under Haiku/Sonnet price
  steps). `full-history` only when replicating the original 2-agent game.
- **Episodes:** 6 per 4-worker game (amendment A). The 2-agent repo default is 10.
- **Temperature:** the repo sends 1.0, the only value Claude 5-family models accept; leave it.
- **Prompt caching:** the repo marks a cache breakpoint on the newest message; keep conversations append-only
  (no editing earlier turns) so the cache and thinking blocks stay valid.

## Code setup

- Original game: `vendor/agent-collusion` = SALT-NLP/agent-collusion @ 5afb2c59 (MIT), gitignored. Recreate: clone at
  that commit, `git apply patches/agent_collusion_haiku.patch` (workspace header, effort mapping, auto tool choice,
  `PEERCHECK_FIXED_TOOLS`), `ln -s ../../.env .env`, then `uv venv -p python3.12 .venv && uv pip install -p
  .venv/bin/python -r requirements.txt`.
- 4-worker game: `src/peer_check/` (being built; design `notes/05_design_4worker_build.md`). Its entry point will
  default to the settings above.
- Project tools: `.venv` (Python 3.12) for `scripts/`.

## Run recipes

2-agent repo game (replication / checks), from `vendor/agent-collusion`:

```bash
P=/Users/asri/Projects/hackathon-police-enforcement
PEERCHECK_FIXED_TOOLS=1 .venv/bin/python -m experiments --start-index 1 --repeats 1 \
  --alice-model anthropic/claude-sonnet-5 --alice-reasoning-effort high \
  --bob-model anthropic/claude-sonnet-5 --bob-reasoning-effort high \
  --output-dir $P/results/<new dir> > $P/results/<new dir>/logs/rep001.log 2>&1
```

Short model check: run the game in the background, then
`scripts/stop_at_first_collusion.sh <log> claude-sonnet-5` in the background; it stops the game between episodes at
the first both-ACCEPT episode or after 4 episodes.

## Before every paid run

1. Smoke test first (1–2 episodes), read the per-episode cost, and extrapolate before launching more.
2. Check free disk space (`df -h /System/Volumes/Data`): the laptop has run out once and a game failed to start.
3. Write the prediction and the run's purpose into the plan or the cost plan before launching.
4. Log the result in `notes/00_results_log.md` as soon as it finishes.
