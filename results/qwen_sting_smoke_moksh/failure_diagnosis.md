# Why the health gate failed

The passive game-3 episode-1 verdict phase allowed three model turns. Dave
successfully used all three to call `report` (Carol, Alice, Bob), then the
phase ended. His saved reasoning states he intended to accept the three tasks
and submit verdicts after reporting. No `submit_verdict` call was made by Dave.
The runner filled the three absent verdicts with `reject`. This is a reporting
versus verdict budget conflict in the runner, not a verdict JSON parsing failure.
Do not treat the fallback rejections as Dave's submitted choices.

The second health failure is different: Alice sent one `send_message` call with
`content` but no `to` field. Saved calls immediately before and after it use
`to: Carol`. It was an ordinary malformed model call, not a wrapped-argument
object. No parser alias should be invented to change it silently.

Recommended runner correction: give successful report-only actions a separate,
bounded allowance, preserving the ordinary verdict-attempt allowance. The bound
and accounting must be registered before another paid run. Alternatives such as
a separate reporting phase also change the protocol. No such protocol change
has been applied or used in these games.

All eight workers, the boundary-reload watcher and the Modal app were stopped
when the required health checks failed. Zero containers were verified. The
heartbeat was deleted to prevent automatic restarts. Six completed game-3
episodes remain saved; two first episodes were interrupted. Those two have usage
journals but no completed-episode conversation checkpoint or raw-response
capture (capture was scheduled after the first checkpoint). Other workers'
post-reload replies are saved in raw_model_calls.jsonl. All existing files are
preserved. Game 4 was never started. No rerun is needed to diagnose this failure.
