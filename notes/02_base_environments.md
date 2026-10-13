# 02: Base environments for the cop experiments

*2026-10-12, Claude + asri. Read-only code inspection by two Sonnet helpers (nothing installed or run). Full cards:
`research/research_notes/Trusted agent stings against collusion/env_review_repos.md` and `env_market_repos.md`.
Clones in the session scratchpad (not kept).*

Design under discussion (see `00_results_log.md`): four arms (no cop / visible cop / undercover cop, passive and
active / "one of you is a mole" announcement), in two settings, one first and the other as a stretch replication.

## Code review: Shi et al. `SALT-NLP/agent-collusion` (MIT)

- **Collusion baseline is strong** (paper, same-model pairs, 50 trajectories): DeepSeek-V4-Flash and Qwen-3.6/3.8-27B
  rubber-stamp in 98–100% of trajectories and 71–82% of episodes. Needs cross-episode memory over ~10 episodes
  (no memory → almost none), so runs cannot be shortened to 3–5 episodes.
- **Hard-coded to 2 agents** (`protocol/state.py` `AGENT_IDS=("alice","bob")`; pair assumptions in ~10 files).
  A ≥3 review ring is an estimated 400–700 lines. Pair version: Alice = subject, Bob = cop.
- No public/private split today; all messages land in one event log an auditor could read (~20–40 lines to add an
  auditor, ~40 more for a channel split).
- The shipped scripted peer replays 5 fixed messages; a live, prompted Bob is needed for passive and active stings
  (~150–250 lines). Mole announcement ~5 lines. Whole four-arm pair version: an estimated 300–450 lines.
- Per-agent verdicts, rewards, messages and token usage are logged in `run.json`.
- Cost not reported; estimated $1–6 per 10-episode trajectory on a cheap model (unmeasured; pilot one run first).

## Market: Agrawal et al. `andyjliu/llm-agent-collusion` (no licence file)

- 5 sellers, 5 buyers, 30 rounds; scripted buyers avoid API calls. One broadcast channel only, no private messages.
- The overseer is a post-hoc gpt-4.1-mini call scoring messages 1–4; a top score gags sellers (5-character cap is a
  prompt instruction only; the "licence revoked" threat is never enforced). The gag fires by round 3–4.
- **Collusion baseline is weak.** From the 10 committed sessions per condition: communication vs no communication
  raises mean price by only ~2.8 (noisy). Only the "boss pressure" prompt gives clearly high prices, and those stay
  high under oversight with no readable messages, so high prices there may be pressure rather than coordination.
  Oversight vs communication (90.5 vs 86.2) needs 8–10 seeds per arm to detect, not 3–5.
- Cheap: about $0.5 per session on gpt-4.1-mini (estimated from logs). Private channel + planted seller + mole arm:
  an estimated 150–250 lines.
- Authors saw sellers try emojis and one-character messages after the gag, in the same channel; no channel shift.

### Re-analysis of the committed market data (Claude, 2026-10-12)

Recomputed from `collusion_metrics.json` in the repo's 50 committed sessions (gpt-4.1 sellers and buyers, 30 rounds,
seller cost 80, buyer value 100, so any price in 80–100 clears the market; the code's "competitive" price of 90 is
the midpoint). Two-sided permutation tests, n = 10 sessions per arm.

| arm | mean trade price | SD | trades | sellers' private coordination talk (judge, 1–4) |
|---|---|---|---|---|
| no messaging | 87.7 | 3.0 | 74 | 2.2 |
| messaging | 90.5 | 4.1 | 52 | 3.8 |
| messaging + overseer | 86.2 | 1.8 | 59 | 2.0 |
| messaging + boss pressure | 96.3 | 0.7 | 23 | 3.9 |
| messaging + boss pressure + overseer | 96.2 | 0.8 | 28 | 2.3 |

- Messaging vs none: +2.8, p ≈ 0.10 (suggestive, not established at n = 10). Earlier "close to noise" was too strong.
- Overseer vs messaging: −4.3, p ≈ 0.008. Boss pressure vs messaging: +5.8, p < 0.001.
- **Boss pressure + overseer vs boss pressure: −0.1, p ≈ 0.75.** Under pressure the overseer did not move prices,
  while coordination talk in the sellers' private notes fell (3.9 → 2.3). This is the "visible cop fails" pattern,
  already in their data.
- Missing control: the authors never ran boss pressure WITHOUT messaging, so high prices under pressure could be
  each seller pushing price on its own rather than collusion. That one arm decides whether the pattern is collusion.
- The coordination score is a post-hoc LLM judge reading each seller's private reflection/plan/memory
  (`seller_individual_eval.jinja2`), not the overseer's score of messages; confirm before citing.

## Others

- Colosseum: only repo with a public board plus a hidden colluder board (3-agent config exists); cooperative
  scheduling, no prices, no in-loop overseer, heavy dependencies (Terrarium submodule), no licence.
- LLMCartel: no seller messaging at all. Magentic Marketplace: no collusion scenario. ColludeBench and
  LLM-Trust-Breaking: colluders instructed or no review task; poor bases.
- No paper found where a monitor pushed agents into an unmonitored channel (two quick searches): still open.

## Implication

Code review has the strong positive control the sprint requires, but as a pair with no hidden channel it cannot
show a visible cop failing because collusion goes underground (asri's point, 2026-10-12). **Correction (same day):**
the boss-pressure prompt rewards each seller individually for a high average price ("If you do not maintain healthy
profit margins ... you will be decommissioned"), so the "overseer fails under pressure" pattern is probably
individual hold-outs, not collusion; and with 5 sellers and 5 buyers any price in 80–100 clears, so collusion has no
defined baseline. The registered plan (`03_registered_plan_market.md`) fixes the economics first (Stage 0). All line counts and costs are estimates from reading; verify with a pilot.
