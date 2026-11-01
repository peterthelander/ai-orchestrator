# Second experiment — 2026-10-31

Repeated E001 from the same base commit in an isolated Entourage worktree. The
first experiment's uncommitted patch was preserved and its complete checkout
snapshot was confirmed unchanged after this run. The target and local run logs
remain under ignored `runs/`.

## Runner and prompt changes

- Supply complete numbered source to reviewers, alongside the diff.
- Use a compact handoff of unresolved findings and check results; omit previous
  approval narratives and implementation claims from fresh reviews.
- Require concrete failure cases for findings, exact current-source citations,
  and coverage of every acceptance criterion.
- Retry invalid review output at most twice, without editing product code.
- Count actual valid reviews toward the minimum, rather than implementation rounds.
- Provide concise standard-library async unittest/ASGI guidance and tell implementers
  to verify reviewer premises before changing working code.
- Snapshot runner source, guide, control hashes, and invocation metrics automatically.

Ten runner tests pass, including evidence validation, context isolation, malformed
review retries, and review counting after failed implementation checks.

## Outcome

The runner **stopped without accepting** after about 13 minutes. Implementation
completed once and every deterministic gate passed:

- 195 Python tests (186 baseline + 9 new).
- 46 JavaScript tests.
- Expo lint and TypeScript checking.
- The unchanged independent task acceptance oracle.

The implementation kept the product change to six added lines and one replacement,
leaving replay/disconnect logic unchanged. The new test module is roughly 8 KB,
compared with roughly 11 KB in experiment 1. Implementation still spent about
9.3 minutes / 35 turns repairing test scaffolding; the first trial took about
10.3 minutes / 31 turns. This is only one exploratory comparison.

Both reviewer outputs recommended approval, but neither satisfied the runner's
review contract. The first used criterion descriptions rather than integer IDs.
The second fixed that schema error but supplied inaccurate source-line references.
The runner refused to accept rather than treating the recommendation as sufficient.
No observer fixes or findings were injected into the agents' handoff.

This demonstrates a fail-closed review gate, but it also shows that exact line-number
bookkeeping is brittle for this model. It does not establish that the produced code
is wrong or that review quality is reliable. The first run was accepted after three
rounds; this run remains a stopped, unaccepted attempt despite passing behavior checks.

## Next change to evaluate

Prefer source anchors that the runner can locate deterministically: resolve a
unique exact quote within a cited file, record the resolved line, and reject missing
or ambiguous quotes. Keep the original model citation in the audit log. Report all
validation errors together so one retry can address the whole output. Do not silently
accept a paraphrase or manufacture evidence for a finding. Evaluate this in another
run rather than changing the acceptance contract retrospectively.

The repeated example still produced verbose tests and avoidable test-setup mistakes.
A fully runnable test example with an explicit factory call may help more than a
helper pattern alone. Python lint/type-check onboarding remains outstanding.

## Local artifacts

`runs/20261031T135640297220Z-E001/` contains state, dialogue, snapshots, prompts,
implementation/review outputs, check logs, and the unaccepted `interrupted.patch`.
The isolated target is `runs/targets/entourage-e001-v2/`. All are intentionally
excluded from Git. No changes from this repeat were applied to the original checkout.
