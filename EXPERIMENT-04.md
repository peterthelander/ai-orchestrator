# Fourth experiment — E002 generalization trial

The first attempt ran unattended in a separate clean worktree at the same baseline
revision. E002 concerns PageText suppressing all subsequent visible content after a
hidden HTML void element, reproduced with `<input hidden><p>Visible tail</p>`.
The unchanged implementation/review runner and five gates were used; only the task,
repository guide, allowed files, and independent oracle changed.

All baseline gates passed (186 Python tests, 46 client tests, lint, typecheck).
The implementation invocation exited with `Request timed out` after about 48.3
minutes, reporting an API error and 12 turns. It wrote a two-line parser fix but no
required regression-test module. There was no reviewer invocation or acceptance.
Post-exit observation confirmed that the independent oracle passes against the
partial change. Focused discovery found no tests, which is NOT a successful test
result. No observer implementation changes were made and the original checkout
was confirmed unchanged. The attempt and partial patch are preserved under
`runs/20261031T175758282134Z-E002/` and `runs/targets/entourage-e002-v1/`.

This attempt demonstrates an inference/infrastructure failure rather than evidence
of success or failure of the complete coding/review workflow. No accepted patch
should be inferred from the partial implementation passing its task oracle.

After the failed invocation, a bounded eight-second health request to the configured
local inference endpoint also timed out. No further invocation was launched against
an unresponsive server. Resume with a fresh isolated attempt when inference is
available; preserve this attempt for comparison.

## Retry after inference recovery

The configured server health endpoint returned HTTP 200 before retrying. A fresh
isolated worktree at the same base commit used the same task, oracle, and runner.
The local loop ran unattended for about 8.4 minutes. The original Entourage checkout
was confirmed unchanged after completion.

Implementation produced a parser change and 15 new tests. All five mandatory
checks passed: 201 Python tests, 46 client tests, lint, TypeScript checking, and
the independent task oracle. Review output attempt 1 was invalid JSON. Attempt 2
recommended approval but still contained an ambiguous quote. The bounded retries
were exhausted, so the runner stopped WITHOUT acceptance or a second valid review.

Post-run inspection found a genuine nearby regression: the patch returns early for
ALL void tags, so a visible `<br>` no longer inserts a line break. For
`<p>Before<br>After</p>`, the baseline returns `Before\nAfter`; the patch returns
`Before After`. The reviewer incorrectly said block-boundary behavior was unchanged.
The independent oracle covered ordinary visible text but omitted visible `<br>`
semantics, so it missed this regression too. No observer fix was applied.

This is substantive evidence against treating passing checks or a local reviewer
approval as sufficient quality assurance. The workflow rejected this attempt for
an output-contract issue, rather than for the actual regression. Future work needs
stronger nearby-behavior checks and review reasoning, alongside reliable structured
output. Simply relaxing ambiguous-quote rejection would have removed the gate that
stopped this patch without addressing its real defect.

Retry artifacts: `runs/20261101T030839152081Z-E002/`. Partial target:
`runs/targets/entourage-e002-v2/`. All prior attempts remain preserved, and no retry
changes were applied to the original checkout. There is still no accepted E002 patch.

## Stronger oracle and autonomous continuation

E002 revision 2 explicitly covers visible br/br/ formatting and hidden br behavior.
Its separate v2 oracle was confirmed to reject the previous regression. Old task and
oracle versions remain unchanged. A clean third attempt passed all five strengthened
gates with 199 server tests, but three review outputs failed on copied filenames,
ambiguous/missing quotes, and omitted coverage. No patch was accepted for that attempt.
Artifacts: `runs/20261101T032144985947Z-E002/` and target `entourage-e002-v3`.

The next runner revision labels source lines with IDs and resolves citations itself.
This addresses repeated mechanical quoting failures without relaxing behavior checks.
Thirteen runner tests pass, including exact source-ID resolution and rejection of
unknown, blank, or contradictory references. New invocations use a fresh worktree;
the previous correct-looking patch was not retroactively accepted or manually fixed.
