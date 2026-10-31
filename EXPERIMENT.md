# Entourage autonomous-loop experiment — 2026-10-31

The first complete trial was accepted by the runner after three implementation /
review rounds, about 29.5 minutes from baseline to final acceptance. All product
changes were produced by local Claude invocations; the observer did not edit the
implementation or feed its own findings into the dialogue.

Task E001: report the configured HTTP request-body limit accurately while preserving
default public wording and existing middleware behavior. Prior manual trial changes
were discarded before establishing a clean baseline.

## Result

- Server suite: 186 baseline tests; 198 final tests (12 new tests).
- Client suite: 46 tests passed under the runner's explicit test-file selection.
- Expo lint and TypeScript checking passed.
- Independent task acceptance oracle passed; it was confirmed to fail on original code.
- All five gates passed in every implemented round and again after final review.
- Final target changes: middleware and one new test file, retained uncommitted.
- Runner tests: six pass, including baseline failure, failed-check retry exhaustion,
  malformed review rejection, CLI warning parsing, change detection, and a synthetic
  review → repair → final acceptance cycle.

## Rounds

| Round | Implementation | Review | Verdict |
|---|---|---|---|
| 1 | 10.3 min | 3.4 min | approve |
| 2 | 2.2 min | 2.3 min | request_changes |
| 3 | 6.6 min | 2.9 min | approve |

## What worked

Fresh invocations exchanged durable reports without retaining a conversational
session. The runner independently enforced checks, bounded retries, checked edit
scope, and bound acceptance to the exact reviewed patch. The review dialogue
ultimately improved a weak exactly-once replay test: it now distinguishes buffered
body delivery from later upstream messages.

## What did not work well

The first implementation initially used pytest rather than the documented unittest
runner, then repaired that mistake itself. Creating and repairing the test module
dominated the first invocation (about 10.3 minutes and 31 turns).

Review 1 approved while making inaccurate statements about ASGI disconnects.
Implementation 2 repeated that reasoning and changed nothing. Review 2 requested
changes: it correctly identified a weak replay mock, but falsely claimed that
production replay and disconnect handling were absent. Both already existed in the
full source. Implementation 3 rejected the disconnect premise with evidence, but
unnecessarily rewrote existing replay logic while improving the test. Final review
approved. Its summary also confused round numbering, so model narratives should not
be treated as authoritative state.

This is a successful bounded execution experiment, not evidence of consistently
reliable review. Passing deterministic acceptance checks supplied stronger evidence
than agreement between model invocations. A review can improve a test and introduce
unnecessary churn in the same exchange.

## Next refinements

1. Require reviewer findings to cite inspected current source and explain the failing
   execution path. Check the complete file, not only diff context.
2. Ask implementers to verify a finding's premise before editing, and explicitly
   permit evidence-based rejection. This permission exists already but was insufficient.
3. Provide a small async unittest example and encourage concise helpers/parameterized
   cases; the new test module is over 11 KB for a small behavior change.
4. Consider giving later reviewers unresolved findings rather than prior approval
   narratives, to reduce anchoring. Preserve the full dialogue for audit separately.
5. Onboard Python lint/type checks and ingestion checks before expanding the task scope.
6. Add streaming invocation logs and explicit resume support; this prototype logs final
   Claude results and stops safely, but restarting requires a clean target.

## Local artifacts

Raw run artifacts are intentionally excluded from the published repository. On the
original machine, they are under `runs/20261031T132000356713Z-E001/`:

- `dialogue.md`: full implementer/reviewer exchange.
- `state.json`: final status and accepted patch hash.
- `accepted.patch`: final Entourage changes.
- `observer-notes.md`: observations kept separate from agent prompts.
- `final-checks.json`: independently recorded verification results.

The run directory also contains exact prompts, task/configuration snapshots, runner
source, repository guide, raw results, reports, per-round patches, and full check logs.
Earlier setup attempts remain separate: missing noninteractive environment, followed
by operator interruptions while adding the independent oracle and handling CLI
warnings before JSON results. They are not counted as implementation rounds.
