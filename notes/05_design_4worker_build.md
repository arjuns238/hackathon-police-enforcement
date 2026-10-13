# 05 — Design: the 4-worker peer-check build (draft, 2026-10-13)

Status: design only. No build code until P-0a (Stage 0a) is resolved, because the worker model may change.
Plan: `notes/04_registered_plan_review.md`. Base code: `vendor/agent-collusion` @ 5afb2c59 plus
`patches/agent_collusion_haiku.patch`.

## Approach

Write a new package `src/peer_check/` that imports the repo's task machinery unchanged and owns N-agent copies of
the orchestration files. The vendored repo stays as patched for the 0a replication. Reasons:
- The 2-agent assumption is in the orchestration layer (35 `peer_id` call sites, 43 `"bob"` literals, mostly the
  controlled-Bob feature we do not need), not in task preparation, tools or evaluation.
- The cop arms (auditor, plant, announcements, penalty) are new logic anyway.
- A separate package gives a reviewable diff and keeps the 0a positive control on the paper's own code.

**Imported unchanged:** `tasks.py`, `evaluation.py`, `protocol/{dispatch,databases,code_tests,files,records,paths}`,
task tool schemas, `prompts/tasks.py` task texts, `agents.py` LLM call path (with our two patches: effort mapping,
workspace header, auto tool choice), usage recording, `memory/` helpers (check they are agent-count-agnostic).

**Owned copies, generalised to N workers:**

| repo file | change |
|---|---|
| `protocol/state.py` | `AGENT_IDS` = alice, bob, carol, dave; `peer_id()` becomes `peers()`; `verdict_submission` keyed by target; inbox entries carry `to` (group or a name) |
| `protocol/messaging.py` | `send_message(content, to)`: group delivers to all three, private to one; log `to`; reject an unknown `to` |
| `protocol/submissions.py` | `submit_verdict(target, verdict, reasoning)`; "already submitted" checked per target |
| `tool_schemas.py` | `send_message` gains a `to` enum; `submit_verdict` gains a `target` enum; plant-only hidden `report` tool |
| `protocol/rewards.py` | shared verdict accuracy summed over 3 peers (max 60); −30 penalty hook |
| `prompts/system.py`, `policies.py`, `messages.py` | multi-peer wording, channel description, per-arm announcement, 3-peer feedback, penalty notice. Keep repo sentences verbatim where the change is only a name substitution; log every real wording change as a deviation |
| `episode_runner.py` | chat rounds loop 4 workers in fixed order; verdict phase asks one verdict per target (3 forced-tool turns); auditor call after chat (arm 2); plant behaviour; penalty applied before feedback |
| `output.py` | 4×3 verdict matrix; transcript with `to` |
| `runner.py` / CLI | `--arm 1..6`, worker model flags, `--resume-from` kept |

**Task sequences:** each episode needs 4 distinct tasks of one family (50 per family in the repo manifests). Generate
fixed 4-task sequences once (seeded), save under `data/review_quads/`, and reuse them across arms so arms differ only
in policing.

## Open decisions (asri's)

1. **Plant: LLM or scripted?** Track 3.2 says the trusted agent is "held to its role by a strong system prompt", which
   favours an LLM plant with a cop system prompt (arm 5's fixed offer is then a scripted one-turn override). The cost:
   its "was I offered a deal?" judgement is itself a model call, which adds noise to recall (M3). A scripted plant is
   cleaner to measure but less like the track brief.
2. **Plant model.** Same model as the workers (cannot be told apart by style) or a stronger one (holds its role better).
3. **Cache cost.** The repo changes the tool list at every phase, which rewrites the prompt cache 4–5 times per
   worker per episode. Keeping one constant tool list (phase rules enforced by the dispatcher, as now) would cut cost
   but changes what the model sees; default is to keep the repo's behaviour.
