# Working on this experiment

The user is conserving hosted Codex usage by offloading implementation and review
to a slow local Claude model. After launching an experiment, let the deterministic
runner execute unattended. Do not inspect target diffs or stage logs repeatedly,
manually fix model output mid-run, or send routine stage-by-stage updates. Wait for
process completion, then review saved artifacts once. Report early only for failure
requiring action or an explicit user request. Use tool-side waiting/orchestration
rather than repeated model reasoning while the local model works.

Preserve prior experiment artifacts and product patches. Prefer a clean isolated
worktree when repeating a task, and compare the same base revision and acceptance
checks. Never treat a model approval as a substitute for deterministic gates.

After a failed completed run, continue autonomously when the failure is actionable
within the approved experiment: preserve artifacts, diagnose once, strengthen a
missing check or fix runner plumbing, test the change, and launch another bounded
isolated attempt. Do not stop merely to ask whether to continue. Keep contracts
fixed during each active run and document changes between attempts. Stop for an
external blocker requiring user action, an explicit user stop, or exhausted bounded
attempts that yield no new progress. Preserve code-check and review gates; never
relax them solely to force an acceptance.
