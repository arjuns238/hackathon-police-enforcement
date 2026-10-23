# Working instructions (asri's standing directives)

These rules apply here in full. They come from the shared mech-interp template
(`~/Projects/mech-interp-template`); the project-specific part is the last section.

## Cost discipline

- **Subagents run on Sonnet. Always.** Pass `model: "sonnet"` on every Agent spawn — judges, lit-review, research, extraction. Omitting `model` silently inherits the session's frontier model. Hard rule for any multi-agent fan-out (asri, 2026-09-17: "any time youre fanning out multiple agents >3 it should always be sonnet"; in practice a 3-agent frontier-model fan-out already triggered a kill order — treat ANY parallel fan-out as Sonnet). A single subagent on a genuinely hard reasoning task is the only discussable exception, and ask first. Consider `haiku` for pure extraction rounds (ask first).
- General principle behind all of this: save money. Prefer the cheap adequate option; ask before any spend that's a step-change (bigger model, bigger n, longer runs).

## Talking to asri

- **Explain simply.** Slow down: plain language, purpose first ("what this is and why we did it") before any numbers, one concrete example, at most one or two numbers, and end with ONE question rather than several. No unexplained jargon, prediction IDs, or dense multi-table summaries in chat — that detail goes in the notes. Offer depth on request. (asri, 2026-09-18: "i dont understand this at all. you need to slow down and make things simpler.")
- **No silent waits.** asri can't see tool output, so a chain of slow calls looks like a hang. Before a slow command, say roughly how long it will take; run slow things in the background and give the answer you already have first; prefer one item over a big loop; skip nice-to-have checks. (macOS has no `timeout` command.)
- **If you have any questions, just ask.** It is better to ask than to assume something you're unsure about.

## GPU workflow — Azure serverless A100 (default since 2026-10-03)

- **Provider is Azure Container Apps serverless GPUs**, paid from asri's Microsoft for Startups credits: one A100 80 GB per container on a 24 vCPU / 220 GB node with ~470 GB local scratch, billed per second on three meters (GPU + requested vCPU + requested memory): ~$3.20/h at the default 8 vCPU / 64 GiB request, ~$6.25/h if a run requests the whole node (`AZ_GPU_CPU` / `AZ_GPU_MEM`). No quota tickets needed. Hard limits: 2 A100s at a time; no H100 or multi-GPU this way (Azure refuses GPU *VM* quota on sponsorship subscriptions — don't re-litigate it, the history is in `TEMPLATE.md`). All scripts in `azure/`; read `azure/README.md` first.
- **Two modes, one image.** Interactive: `./azure/jupyter_up.sh [model]` starts JupyterLab on the GPU, prints the URL, and points the `jupyter` MCP at it; `./azure/jupyter_down.sh` deletes it. Batch: `./azure/run_job.sh <script> [args]` runs one script and exits; `./azure/job_logs.sh` follows it; `./azure/status.sh` shows what is billing.
- **End every session with `./azure/jupyter_down.sh`.** The Jupyter container bills for as long as it exists (no idle timeout). Jobs stop themselves. Check `./azure/status.sh` before closing a session.
- **Single-driver rule:** only ONE Claude session drives a project's Jupyter app at a time. Two concurrent sessions once raced each other on a pod (duplicate sampling at 100% GPU, duplicate judging, monitors killing each other's processes, ~2M wasted subagent tokens). Before driving GPU work: check for recently-modified sibling transcripts (`ls -lt ~/.claude/projects/<project>/*.jsonl`), and create/check a lock file on the share (`/workspace/<project>/DRIVER_LOCK` with session id + timestamp).
- **Code changes: `./azure/push.sh`, no rebuild.** The image holds only packages; `src/`, `data/`, `notebooks/`, `pod/` live on the project's file share, mounted at `/workspace/<project>` (same path as the old pod, so nothing in notebooks changed). A new pip package goes in `pod/requirements-pod.txt` then `./azure/build.sh` (~10 min).
- **`/scratch` is wiped when a container stops; `/workspace/<project>` survives.** Models are re-downloaded to `/scratch/hf-cache` each session (fast from inside Azure; pass the model name to `jupyter_up.sh` or set `PREFETCH_MODEL` for jobs). Write everything worth keeping under `/workspace/<project>`. `/dev/shm` is 64 MB — stage checkpoints on `/scratch`, not `/dev/shm`.
- **Smoke-test before every full run**: `./azure/smoke_gpu.sh` after any rebuild, `./azure/run_job.sh pod/smoke_test.py` on a tiny model before loading the big one, then 2–3 real samples: verify outputs parse, end in terminal punctuation, and contain the committed answer.
- **Never let generations truncate.** Set `max_new_tokens` generously (reasoning-heavy tasks: ≥1500; cheaper to over-budget than re-run). After any run, check `max(len(response))` vs the cap and count no-terminal-punctuation tails before trusting the data. Truncation silently cost GPU time three times in an earlier project (asri: "we've lost valuable gpu time").
- **Batch scripts must be restartable** (skip items whose outputs exist). A job that dies or is stopped is simply re-run with the same `run_job.sh` command. Scripts should print `BATCH DONE` as their last line, as before.
- Large artifacts (activations, checkpoints) stay on the share or `/scratch`, not the laptop. `./azure/pull_results.sh` brings back only `results/` and executed notebooks.

### Driving the GPU (Jupyter MCP)

- Order of operations: `./azure/push.sh` → `./azure/jupyter_up.sh <model>` (prints the URL and rewrites `JUPYTER_URL` in `.mcp.json` / `.codex/config.toml`) → reconnect the **`jupyter` MCP server** in Claude Code and drive notebooks. If the MCP server shows as failed/timed out at session start, that just means no Jupyter container is up — run `jupyter_up.sh` and retry; don't conclude it's unconfigured.
- The Jupyter token lives in `.env`, `.mcp.json` and `.codex/config.toml`, all gitignored and all written by the template's `new_project.sh`. Never commit or print it. The URL is public but locked to the laptop's current IP by `jupyter_up.sh` (re-run it if your IP changes).
- **Work in notebooks by default — asri wants to be able to read the code (soft rule).** Experiments driven through the Jupyter MCP live in `.ipynb` files on the share: asri can open the same JupyterLab URL in a browser (token from `.env`), read the code, see the outputs/figures inline, and rerun cells. Keep notebooks tidy enough to read: named per experiment, top cell stating what it does, no dead cells left behind. Start from `notebooks/00_template.ipynb`.
- **Fallback is explicitly allowed:** if notebook-driving gets unstable for a run (kernel deaths on long jobs, MCP disconnects, multi-hour batch generation), revert to a plain Python script pushed with `azure/push.sh` and run as a job with `azure/run_job.sh`. Long unattended batch runs are usually *better* as jobs anyway (no tunnel to drop, bill stops by itself, restartable). When falling back, keep the script in this repo so the readability goal is still met, and say in the notes that the run went job-mode and why.
- Rule of thumb: notebooks for exploration, probing, analysis, plots, smoke tests; jobs for anything that runs longer than ~20 minutes unattended.

### LEGACY: rented GPU pods (RunPod) — kept for reference, not the default

Use only if a project needs a GPU Azure will not provide (H100, multi-GPU). Scripts: `pod_setup.sh`, `connect.sh`, `pod/` (see `pod/README.md`). The rules that were specific to pods:

- Pods bill while idle: **stop the pod when done**; for unattended batches start `pod/deadman_stop.sh` (RunPod-only) as the safety net.
- A pod stop/restart wipes the container disk; only `/workspace` survives. Re-run `pod_setup.sh` then `pod/post_setup.sh` after every restart; put every environment fix into `pod/post_setup.sh`.
- Order of operations: start pod → `./pod/remote_setup.sh <host> <port>` → `./connect.sh <host> <port>` (SSH tunnel to `localhost:8888`) → Jupyter MCP. Push code with `pod/push.sh` (scp a locally-written file; heredoc-over-SSH with kill/pkill has silently failed before); pull with `pod/pull_results.sh`.
- Single-driver lock file was `/workspace/DRIVER_LOCK`; the `runpodctl` part of `pod/post_setup.sh` and `pod/deadman_stop.sh` are RunPod-specific.

## Research method

- **Registered predictions before compute.** Write predictions with confidence levels into a notes file BEFORE running anything (copy `notes/_templates/registered_plan.md`). Include the decision rules and thresholds, fixed in advance. Keeps us honest; asri values this.
- **Lit-scan before committing to a contribution.** Verify novelty with explicit per-claim verdicts (OPEN / PARTIALLY CLAIMED / CLAIMED), flag full-text-verified vs abstract-only, and record what must be re-verified before citing numerically. Scan reports live in `research/` (copy `research/_template_lit_scan.md`).
- **Results log.** Write the results of EVERY experiment into `notes/00_results_log.md` as soon as it finishes, before starting the next: key numbers in small tables, a verdict per registered prediction, what it changes, and any failures or deviations from the registration. Digestible, not exhaustive — full tables stay in `results/*.csv` and the executed notebooks.
- **Scope discipline.** Keep the paper's question narrow and differential; asri actively prunes scope creep. When a contribution drifts toward a broader project, flag it and offer tethered/stretch/cut options rather than silently expanding.
- **Don't overclaim.** State n, mark preliminary results as preliminary, prefer the weaker robust claim over the stronger fragile one.
- **Take time planning; don't jump to conclusions.** asri prefers deliberate multi-turn planning with pushback welcomed before any commitment of compute or writing.
- **Judging:** Claude subagents as judges (Sonnet — see cost rules), source papers' judge prompts kept VERBATIM, isolated work dirs, mechanical cross-checks/parser audits on a stratified sample, and the judge model noted in methods for every round.
- Register the judge/eval design (prompts, parsers, n) in notes before running, same as predictions.

## Repo conventions

- `notes/` numbered chronologically — the running lab notebook (`00_results_log.md` is the one always-current file; `01_…` is the lit review + plan). `research/` for lit scans. `papers/` for source PDFs. `src/` for the project's Python package, `azure/` for the GPU scripts (`pod/` is the legacy pod version plus `smoke_test.py` and `requirements-pod.txt`, which the Azure path still uses), `notebooks/` for experiments, `results/` for small outputs.
- Commit messages: plain, descriptive; do not commit or push without asking.
- **Feed the template.** When asri gives a new standing rule that is not specific to this project's topic (a preference, a pod lesson, a method rule), add it here AND offer to add it to `~/Projects/mech-interp-template/CLAUDE.md` so the next project starts with it.

## This project: hackathon-police-enforcement

*(Fill in at kickoff; keep short. Everything above is shared across projects, everything below is specific to this one.)*

- **Question:** hackathon track 3.2, "Can we disrupt collusion through introducing trusted agents?" A trusted agent (held to its role by a strong system prompt) acts like an undercover officer: it offers collusion/coordination opportunities to a group of LLM agents and logs who reciprocates. Do targets accept, reject, or become suspicious depending on how the trusted agent makes the approach? (The track claims this "hasn't been tested"; we check that in the lit scan, `research/01_lit_scan_trusted_agents.md`.)
- **Models / checkpoints:** Peer-check game workers = **Claude Sonnet 5** (`claude-sonnet-5`), effort high (first study, API only). Second study (Qwen sting, notes/12, approved 2026-10-22): **Qwen-3.8-27B** served with vLLM on a Modal A100 (`modal_gpu/serve_qwen.py`), $50 Modal credits, soft stop $45 (`scripts/modal_spend.py`). Full run configuration below and in `notes/07_run_config.md`.
- **RUN CONFIGURATION — read `notes/07_run_config.md` before ANY paid API run.** The essentials:
  - **Budget: $150 total for the whole project (asri, 2026-10-13); hard stop at $145.** Check spend with `python3 scripts/spend.py` before and after every run (the game runner refuses to start above $140); ask asri before any step up in spend.
  - **Workers: `claude-sonnet-5`, effort high, tool choice auto. Do NOT substitute:** Haiku 5.5 never colludes (results log R0a); Sonnet 5.5 refuses the game via its `reasoning_extraction` classifier (S55); Sonnet 4.6 works but costs 1.5× and is slow enough that 4-worker turns would outlive the 5-minute prompt cache (PC-1).
  - **Always set `PEERCHECK_FIXED_TOOLS=1`** for game runs: it halves cost by keeping the prompt cache valid across phases (CC-1). 4-worker games use `communication-onward` memory and 6 episodes.
  - Every call needs the workspace header (org-level key); the patched code adds it from `ANTHROPIC_WORKSPACE_ID` in `.env`.
  - Smoke-test (1–2 episodes) and read the per-episode cost before launching more games; check free disk space first.
- **Relation to other projects:** independent unless stated here.
- **Hackathon:** Apart Research "AI Collusion Research Sprint", 23–25 Oct 2026, remote OK; **submission deadline Sun 25 Oct 2026, 11:59 PM AoE** (PDF report on their template, 4–8 pages, mandatory limitations/dual-use appendix). Page: https://apartresearch.com/sprints/ai-collusion-research-sprint-2026-10-23-to-2026-10-25. The page already sketches a baseline 3.2 design (scripted offerer; direct / hint / benign offer), so a submission must go beyond it to score on innovation.
- **Current status and next step:** see `notes/00_results_log.md`.
