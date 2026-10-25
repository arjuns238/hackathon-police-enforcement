# Qwen sting games 3–4: partial handoff

All authorized runnable experiments have ended. Both Modal apps are stopped; no experiment workers or GPU containers remain. No commit or push was made.

## Data status

The original target was 16 games / 64 episodes. Seven games completed four valid episodes; nine games remain partial/skipped. There are 46 saved raw episodes, of which 43 pass the applicable validation; three saved episodes are excluded. Eighteen originally planned episodes were not completed.

Do not interpret the raw global health FAIL as a passing full dataset. It preserves the failures in excluded episodes. The separately derived saved-valid subset passes. The validity mask is `skipped_games_moksh.json`; use the dated `qwen_sting_moksh_validated_episodes.csv` for our games 3–4, rather than the original unfiltered/global CSV.

Six games stopped on context-limit errors. Three games were excluded from their first required tool-health failure onward. One of those errors recovered on retry but remains outside the narrowly approved M1 exception; it did not lose a turn. Earlier healthy episodes are retained as partial data. Exact reasons and episode masks are in the completeness report and skip index.

## Preserved evidence

All 16 original game folders remain untouched, including checkpoints where produced, messages, usage, console logs, durable provider request/reply/reasoning/error journals and backend assignments. The two games failing before their first checkpoint have no run.json or messages.json; their raw calls and errors remain available. Interrupted requests and excluded pilots are retained, as are source/task/prompt archives and provenance. No failed episode was regenerated overnight.

Some retained early game-3 episodes predate the extra raw-call capture hook. They retain their original checkpoint, usage and saved reasoning coverage; individual pre-capture provider retries are not fully captured. Later capture is at the completion-wrapper level; internal SDK/proxy transport retries are additionally evidenced by redacted server logs.

The source is HEAD 740c410 with the approved observation-only capture and M1 classifier. M1 was approved after observing a case, applies locally and must be disclosed as a post-observation amendment. No other model, prompt, sampling, context/output or retry setting changed. Early offers before the nominal approach episode and overlong-message losses are reported findings under accepted D11/C2 withdrawal. Two automatically recovered server replacements are documented in provenance; no completed episode replay occurred. No paid Anthropic judge ran.

## Cost and shutdown

Modal billing remains delayed. The final operational allowance uses $14 for earlier work plus $4 per GPU serving hour, with stopped windows capped by container-absence evidence. It is a conservative reserve, not a measured charge. See `final_completeness_capture_cost.json` and `d13_restart_provenance.json`. The secondary had no container by the saved 11:00 UTC check, after its last worker failed at 10:37 UTC; its later administrative stop does not represent continued GPU service.

## Files

- `final_completeness_capture_cost.json`: per-folder completeness, capture and cost summary.
- `skipped_games_moksh.json`: authoritative episode exclusions and retained partial episodes.
- `morning_summary_moksh.md`: readable status and case details.
- `analysis_snapshots/`: dated original/free and validated CSV/console outputs.
- `server_logs/`: redacted overlapping logs and full backfills.
- `source_*_manifest.json` and source archives: exact experimental provenance.
- Final inventory and archive manifests list paths, byte counts and SHA-256 hashes.

Incomplete cells and missingness depend on model/tool behavior. Report per-cell sample sizes and these exclusions; do not claim the original balanced design was completed. No final semantic-judging or aggregate character-effect conclusion is claimed here.

Final allowance: $44.62; reported billing: $0.03 (lagging).
