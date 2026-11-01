# Hosted-only versus hybrid — first paired pilot

**Both arms passed the same behavioral checks. No overall subscription-usage win
has been demonstrated.** Hybrid execution used fewer uncached-input/output tokens
in the measured phases, but more cached input, plus substantial shared setup and
measurement work. Those categories must not be silently discarded or equated with
subscription credits.

## Task and protocol

E003 fixes Unicode case-insensitive page search returning excerpts in the wrong
coordinates. Case folding can expand characters: 600 ß characters before NEEDLE
made the original code report a match but return an excerpt past it. Both arms
started at Entourage commit `d28c70af51ef5842260a05291408a6a6d7389e4e`, received the
same work order and guide, and faced the same independently authored acceptance
oracle. The oracle was confirmed to fail on the baseline before either arm ran.

The local loop ran unattended. The hosted-only implementation was completed and
verified before its agent inspected local outputs. Work happened in separate clean
worktrees; the original Entourage checkout and earlier experiments are unchanged.
See [the preregistered pilot protocol](BENCHMARK.md).

## Verified outcomes

| | Hosted only | Hybrid |
|---|---|---|
| Outcome | Verified | Runner accepted |
| Python tests | 190 (186 baseline + 4) | 204 (186 baseline + 18) |
| Client tests | 46 pass | 46 pass |
| Lint / TypeScript / independent oracle | All pass | All pass |
| Production diff | 14 additions, 1 deletion | 33 additions, 2 deletions |
| New test file | 3,310 bytes | 10,989 bytes |
| Approximate execution time | About 1 minute | 34.1 minutes |

The hybrid required three implementation invocations and two valid reviews. Its
first patch passed its own tests but failed the independent oracle: no-match
`find_matched` behavior was not preserved. A fresh local implementation fixed that
without hosted intervention. Both subsequent reviewers approved without additional
product findings. Thus the oracle added demonstrated value; these reviews did not
show an incremental improvement on this task. Extra test count is not a quality score.

Both final algorithms preserve original coordinates and expansion-aware matching.
The hosted version avoids the hybrid's per-character position mapping list. This
is a source-level simplicity observation, not a measured memory benchmark.

## Observed hosted usage

Counters come from actual local usage events for this chat, not an estimate based
on answer length. Input minus cached input, output, and cached input are reported
separately. Reasoning is not added a second time to reported output totals.

| Phase | Uncached input | Output | Cached input |
|---|---:|---:|---:|
| Shared setup | 7,870 | 6,316 | 1,079,936 |
| Hosted-only implementation + verification | 2,871 | 3,057 | 852,096 |
| Hybrid launch + unattended wait | 1,066 | 1,786 | 844,672 |
| Joint result assessment (charged fully to hybrid below) | 345 | 890 | 287,744 |
| Measurement/report preparation | 6,431 | 2,333 | 583,936 |
| Total pilot through report checkpoint | 18,583 | 14,382 | 3,648,384 |

For a conservative execution-phase comparison, charge the entire joint assessment
to hybrid, even though it also assessed the hosted result:

| Execution-phase metric | Hosted only | Hybrid plus joint assessment |
|---|---:|---:|
| Uncached input | 2,871 | 1,411 |
| Output | 3,057 | 2,676 |
| Uncached input + output (unweighted arithmetic) | 5,928 | 4,087 |
| Cached input | 852,096 | 1,132,416 |
| All input + output, including cached | 858,024 | 1,136,503 |

That narrow uncached-input-plus-output sum is about
31% lower for hybrid, while all-token volume including cached input is higher.
**Neither figure is a proven billing or subscription-quota saving.** The quota
weighting of these token categories was not measured, and output/input need not
have equal weights. The long existing chat also makes repeated cached context a
large confounder. The arithmetic sum is only an explicitly labeled comparison.

Shared setup alone consumed 14,186
uncached-input-plus-output tokens. Measurement/report preparation adds further
cost. Historical runner development is additional investment outside this pilot.
We therefore cannot claim an all-in win from execution-phase numbers. A reusable
setup might amortize, but this single task does not establish that it will.

## Measurement limits

- Checkpoints capture the latest recorded token event; boundary tool responses and
  final reporting/publishing after the last checkpoint are excluded. Raw counter
  timestamps and the entire measured-pilot total are provided in the usage artifact.
- The counter parser initially looked for an obsolete user-message event shape.
  The start boundary was corrected from the latest actual response-item user message
  before computing totals; the repair's hosted activity is included in report overhead.
- Task selection, diagnosis, work-order/oracle preparation, and metering were hosted
  work and are shown as setup, not called free local execution.
- Shared setup and measurement costs are shown separately rather than arbitrarily
  assigned to one arm. Any claimed amortized advantage depends on a stated allocation.
- This was one small task, with known requirements and tests. The hosted agent wrote
  the oracle, knows the bug domain, and assessed both implementations. There was no
  blinded independent quality review, randomized order, or repeated-task sample.
- More tests and two model approvals do not prove higher quality. Both arms passed
  the same fixed checks; equivalence outside those checks is unproven.

## Conclusion

This pilot supports a narrower statement: a working local loop can deliver a
verified fix with less incremental uncached/output hosted activity under this
accounting. It does **not** establish better overall results per hosted quota unit.
The hosted-only path was much faster and simpler here. Before expanding the trial,
use short fresh contexts and a stable measurement method so repeated long-chat
context and instrumentation do not dominate the comparison. Then evaluate several
new tasks with explicit setup allocation and the same frozen checks.

## Artifacts

Published: [usage counters and buckets](benchmarks/E003-usage.json), shared
[task](tasks/E003.json), [guide](configs/entourage-find-guide.md), and
[oracle](acceptance/entourage_page_find.py).

Local only: `runs/benchmark-e003/`, hosted worktree `runs/targets/e003-hosted/`, and
hybrid worktree `runs/targets/e003-hybrid/`. The hybrid run is
`runs/20261101T083420733815Z-E003/`; accepted patch and full dialogue remain there.
Both product patches are uncommitted and isolated. No product changes were merged.
