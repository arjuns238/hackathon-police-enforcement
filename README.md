# hackathon-police-enforcement

**"<working title>"**

One paragraph: the phenomenon, what is already known (with the source paper), and the question this project
answers. Keep it narrow and differential.

**Running the Qwen sting on your own Modal account? Start with [`RUNBOOK_QWEN.md`](RUNBOOK_QWEN.md).**

## Layout

- `CLAUDE.md` — standing working instructions (shared across projects) + a short project-specific section. `AGENTS.md` points to it.
- `notes/00_results_log.md` — **start here for status**: one digestible entry per finished experiment.
- `notes/01_lit_and_plan.md` — mission statement, contribution ledger, registered predictions, risk register. Later notes are numbered chronologically; each experiment gets a registered plan (`notes/_templates/registered_plan.md`) written before it runs.
- `research/` — lit-scan reports with per-claim novelty verdicts and full-text-vs-abstract flags.
- `papers/` — source PDFs.
- `src/interp/` — the project's Python package (`model.py`: loader + residual-stream hooks).
- `notebooks/` — one readable notebook per experiment, driven on the GPU through the Jupyter MCP.
- `azure/` — **the GPU workflow** (serverless A100 on Azure, paid from credits): `setup_once.sh` (once per account), `build.sh` (image), `push.sh` / `pull_results.sh`, `jupyter_up.sh` / `jupyter_down.sh` (interactive), `run_job.sh` / `job_logs.sh` / `status.sh` (batch), `smoke_gpu.sh`. Read `azure/README.md`.
- `pod/`, `pod_setup.sh`, `connect.sh` — **legacy** RunPod pod workflow, kept for reference (`pod/README.md`). `pod/smoke_test.py` and `pod/requirements-pod.txt` are still used by the Azure path.

## Status

Created 2026-10-12 from `mech-interp-template`. Phase 0 (lit review + registered predictions) not started.
