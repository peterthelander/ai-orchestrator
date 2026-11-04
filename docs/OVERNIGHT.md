# Local-only overnight batches

`overnight.py --manifest /absolute/path/to/manifest.json --validate` checks a frozen
multi-repository plan without calling a model. Omit `--validate` to run it. Schedule
this Python command with the operating system (for example a one-shot systemd user
timer), rather than a hosted Codex automation. No hosted API or parent continuation
is implemented in this supervisor.

A manifest contains timezone-aware `start` and `deadline` ISO timestamps,
`max_task_seconds`, and `entries`. Each entry has a unique `id`, repository label,
`not_before` timestamp, explicit committed `base`, full repository `config`, and
one task contract. Every config must set `local_only: true`. Prepare profiles and
verify fresh-worktree baselines with `doctor` before scheduling.

The supervisor runs one task at a time. Repository release times are earliest
starts, not promises of exact execution times; among eligible repositories it
prefers those with fewer attempted tasks. Each task starts from its frozen base
in a separate worktree. Failed tasks and `parent_required` disputes are parked and
unrelated work continues. Task and overnight deadlines limit model/check process
timeouts; unattempted work is marked `not_run_deadline`. The service should also
have an overall timeout and control-group cleanup as a final process bound.

Local-only mode requires an explicit private-IP/localhost `ANTHROPIC_BASE_URL` and
`ANTHROPIC_MODEL`. It disables provider override environment flags, proxy routing,
nonessential Claude traffic, hooks/config discovery and slash commands, selects
the exact local model, and provides no fallback-model argument. Tools remain the
ordinary trusted local implementation tools; this is not a network sandbox.
Tasks and checks must use mocks rather than paid/live product APIs.

Run from a saved runtime snapshot, so normal daytime edits to the orchestrator do
not alter an active night's contract. Keep plans, endpoint credentials, transcripts,
and source artifacts private. Only named literal environment exports are loaded;
credentials do not belong in a manifest. Retain every worktree and patch, and do
not merge independent overlapping changes without integration checks.

`summary.json` and `MORNING-REPORT.md` are updated after each task, with links to
accepted patches, failed checks and parked parent packets. Existing summaries
prevent automatic replay after a supervisor crash. There is no automatic morning
hosted invocation: ask Codex to inspect the saved report when ready.

Local-only jobs probe the llama.cpp health endpoint before starting. Two failed
preflight probes stop the batch before it creates another worktree. During model
calls, the runner checks reachability about every 30 seconds and terminates the
invocation after two consecutive failures. A busy HTTP 503 is tolerated while
a request is active. Recognized CLI connection errors also stop the batch.
The report records `paused_inference` and `pending-entries.json` contains the
interrupted entry and the remaining entries. After recovery, use those entries
with a new start, deadline, release times, and runtime snapshot in a fresh batch
directory. The interrupted worktree and logs are retained.

The computer running WSL and the inference laptop must remain powered, awake and
reachable. User lingering keeps the Linux user manager alive after logout; it
does not keep Windows running or wake a sleeping host.
