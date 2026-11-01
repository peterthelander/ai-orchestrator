# Third experiment — 2026-10-31

The local runner completed unattended in about 15.1 minutes and accepted E001 after
two valid reviews. No intermediate stage inspections, observer fixes, or injected
review findings occurred during the run. The original Entourage checkout and its
first-experiment patch were confirmed unchanged afterward.

## Changes evaluated

Reviewers now supply an allowed file and a unique exact single-line source quote.
The runner finds the quote and records its line. Missing or ambiguous quotes fail;
any supplied model line is preserved separately as audit metadata rather than
trusted for locating source. Raw model outputs remain intact and normalized reviews
are saved separately. Evidence and coverage validation reports all errors together
so one retry can address them. No paraphrase or approximate matching is accepted.

Twelve runner tests passed before launch, including unique quote resolution,
original-input preservation, rejection of ambiguous/missing anchors, aggregated
errors, and the existing review/repair and review-counting tests.

## Outcome

- Same task E001, same Entourage base commit, same independent acceptance oracle.
- Separate clean worktree: `runs/targets/entourage-e001-v3/`.
- 198 server tests passed (186 baseline + 12 new).
- 46 client tests passed.
- Expo lint, TypeScript checking, and independent task acceptance passed.
- All five gates passed after both implementation invocations and after final review.
- Accepted work remains uncommitted in the isolated worktree.

The first implementation took about 6.9 minutes, 27 turns, and 9,254 output tokens
reported by Claude. A fresh second implementation response took about 2.7 minutes
and made no changes. The two round patches are identical. The product patch adds a
small formatting helper and changes the 413 message; existing replay/disconnect
logic is preserved.

Review 1 approved with valid unique quotes. Review 2 initially supplied ambiguous
quotes. The runner reported the validation errors together, and a fresh output retry
returned unambiguous citations. It then accepted only after final verification and
matching the exact reviewed patch. There were no product-change requests in this
trial, so it does not newly demonstrate correction of a genuine product defect
through reviewer feedback.

## Comparison

| Trial | Outcome | Approximate duration | Valid reviews |
|---|---|---|---|
| 1 | Accepted; weak test improved, unnecessary replay rewrite | 29.5 min | 3 |
| 2 | Stopped on inaccurate line-number citations | 13 min | 0 |
| 3 | Accepted; quote retry resolved ambiguity | 15.1 min | 2 |

This is a small exploratory sample with several workflow changes between trials.
It does not establish that the latest workflow is reliably faster or more accurate.

Review reasoning remains a limitation: some final citations refer to test docstrings
rather than assertions. The validator proves that an exact source anchor exists,
not that the cited text establishes the reviewer's conclusion. The independent
behavioral oracle supplies stronger evidence for this task. Tests are still verbose,
and Python lint/type-check onboarding remains outstanding.

## Next experiment

Move to a different small deterministic backend task with a reproduced defect and
an independent acceptance check. Keep the runner stable for that trial so we can
learn whether it generalizes rather than tuning further to this example.

## Local artifacts

Full artifacts are in `runs/20261031T165121040506Z-E001/`, including the dialogue,
raw review outputs, resolved reviews, check logs, source snapshots, metrics, and
`accepted.patch`. They remain excluded from Git. Earlier trials and target worktrees
are preserved. No experiment changes were applied to the original checkout.
