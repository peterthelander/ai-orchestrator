---
name: local-coding-loop
description: Delegate bounded coding tasks to the user's local Claude CLI with isolated worktrees, automated checks, fresh implementation/review contexts, and selective Codex escalation. Use when asked to use the local coding loop, onboard a repository for it, or run an unattended local coding queue.
---

# Local coding loop

Use the bundled CLI via `python3 <this-skill>/scripts/orchestrator.py ...`.
The installer links this skill to the maintained ai-orchestrator checkout, or
installs readable copies when crossing Windows/WSL. For a copied installation,
`installation.json` supplies the Linux checkout and WSL distribution. From a
Windows shell, invoke `wsl.exe --distribution <distribution> --exec python3
<checkout>/orchestrator.py ...` directly; Python on Windows is not required.
Use Linux paths for repositories, tasks, decisions, and artifacts passed to WSL.
If the local shell cannot start at all, report that execution blocker; do not
infer that the skill is absent merely because a shell call failed.
Read [workflow.md](references/workflow.md) for command examples, profile/task schemas,
and parent decisions. Do not read historical experiment reports during ordinary use.

## Prepare once, delegate cheaply

- Reuse an existing repository profile under `${AI_ORCHESTRATOR_HOME:-~/.local/share/ai-orchestrator}/profiles/`.
  For a new repository, inspect its instructions and existing check commands; write
  a concise guide and mandatory checks, then run `doctor`. It verifies a fresh
  worktree with no model invocation. Configure dependency setup for fresh worktrees.
- Use the user's existing Claude CLI/inference environment. Do not switch providers
  or add hosted API calls. Report an unavailable local endpoint as an external blocker.
- Write a short outcome-based task with acceptance criteria and explicit allowed
  files. Specify required deliverables where useful. Narrow tasks that exceed the
  local model's context; avoid detailed implementation recipes unless needed.
- Reuse existing gates. Add independent task acceptance checks when existing checks
  cannot distinguish the requested behavior. Do not weaken checks or count review
  agreement as verification. Freeze task/check contracts during each active run.

## Run unattended

Launch `run`, or `queue` for independent tasks. Each task gets its own detached
worktree; source-checkout changes are not included. A queue freezes one committed
base for all tasks, continues after failures, and does not compose patches or
handle dependent tasks. Split dependent work into separate runs after integration.

Redirect command output to a log and wait tool-side for process completion. Do not
poll stage logs, inspect intermediate diffs, fix output mid-run, or issue routine
progress commentary. Review the saved summary once on completion. Preserve every
worktree, patch, and log. Use `status` only for a user status request, after
completion, or to diagnose an actual interrupted/failed launch.

## Escalate and finish

For `parent_required`, read the saved parent packet, current diff/source relevant
to disputed claims, and check evidence. Decide each finding with a concrete reason.
Save a `hosted_parent` decision and use `resume`. A decision cannot waive failed
checks, alter the task, expand scope, or approve a changed patch. Resume reruns final
checks before acceptance; upheld findings return to implementation only within
remaining rounds. Do not silently reset the attempt limit.

After an actionable plumbing failure, preserve evidence, fix and test the runner,
then make a bounded fresh attempt with the same task/check contract. Do not change
an active run's controls. Stop for an external blocker, explicit user stop, or
exhausted attempts without new progress.

Report accepted/unresolved/blocked tasks, gates and material limitations, plus the
worktree and patch locations. Accepted means the configured checks passed, not
that all behavior is proven. The tool leaves patches uncommitted. Apply, commit,
merge, or push only within the user's authorized scope; preserve unrelated changes.
