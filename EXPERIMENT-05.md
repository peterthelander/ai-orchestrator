# E002 completion with stronger gates and source IDs

The parser task is now accepted by the deterministic runner. The final trial ran
unattended for about 17.1 minutes, with two implementation invocations and two valid
reviews. There were no observer edits to product code or intermediate inspections.
The original Entourage checkout and every previous attempt remain unchanged.

## What changed after the regression

- E002 revision 2 and a separate v2 acceptance oracle explicitly preserve visible
  br/br/ line breaks while fixing hidden void elements. The stronger oracle was
  confirmed to reject the earlier broad early-return regression.
- A fresh attempt produced a passing patch but exhausted three quote-based review
  outputs. Its artifacts remain under `runs/20261101T032144985947Z-E002/`.
- Source packets now supply short IDs such as `S1:20`. The reviewer cites these,
  and the runner records the exact corresponding file, line, and source text.
  Unknown, blank, and contradictory IDs are rejected. Legacy unique quotes remain
  supported. This avoids unreliable copied/escaped code without bypassing evidence.
- Thirteen runner tests pass, including source-ID resolution and invalid references.

The citation protocol changed between complete runs, never during an active run.
Earlier patches were not retroactively accepted under a different contract.

## Final verification

- 200 Python tests (186 baseline + 14 new parser tests).
- 46 client tests.
- Expo lint and TypeScript checking.
- Independent v2 oracle covering all void tags, hidden/aria-hidden attributes,
  ordinary/self-closing syntax, hidden containers, text/title/links, visible br,
  hidden br, and preservation of nearby behavior.
- All five gates passed after each implementation and again after final review.
- Exact accepted patch hash is recorded in the final state and patch artifact.

The production patch changes only PageText start-tag handling. Hidden void tags
never enter the hidden stack; visible br still reaches existing formatting logic.
The fix and tests remain uncommitted in the isolated target worktree.

Both valid reviews approved. Each first review output used descriptions instead of
integer criterion IDs, so the runner required a corrected output before counting it.
Source-ID references resolved successfully without quote-copying failures. The model
still struggles with simple output contracts; bounded validation retries remain useful.

## Interpretation

The pipeline can now finish a second task with materially stronger behavioral checks.
However, this success required hosted diagnosis of an earlier regression, a stronger
oracle, and harness changes. Those hosted tokens count against the hybrid approach.
The final two reviews produced no product findings, so this trial does not demonstrate
an incremental quality benefit from review itself. It demonstrates bounded unattended
execution with independent checks and validated review references.

Reliable semantic review, Python lint/type onboarding, and a direct hosted-only
comparison remain open. Source IDs prove where evidence comes from, not whether the
reviewer interpreted it correctly. Do not extrapolate a cost or quality advantage
from this one accepted run.

## Artifacts

Final run: `runs/20261101T033140706365Z-E002/`.
Target: `runs/targets/entourage-e002-v4/`.
The run includes `accepted.patch`, `state.json`, full dialogue, exact prompts,
resolved/raw reviews, check logs, source snapshots, and invocation metrics. These
remain local and excluded from Git. No experiment patch was applied to the original
Entourage checkout.
