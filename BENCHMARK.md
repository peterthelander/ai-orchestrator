# Hosted-only versus hybrid pilot protocol

E003 is a paired pilot: identical task, base revision, dependencies, allowed edit
scope, and deterministic acceptance checks in two isolated Entourage worktrees.
The hybrid arm uses the current implementer/reviewer runner. The hosted-only arm
uses the current hosted agent directly, including its normal self-checking, without
local-model implementation or a forced two-review ceremony. Both must pass full
server/client tests, lint, TypeScript, and the same task oracle.

The local arm runs unattended first. Its outputs are not inspected until the
hosted-only implementation and verification are complete. This reduces solution
contamination but is not a blinded randomized trial: the hosted agent authored the
shared task and oracle and knows the intended behavior. Preparation receives its
own accounting bucket. All retries, failures, orchestration, and result assessment
must be reported, including work that fails acceptance.

Usage is read from actual token_count events in the current chat's local session
log. Checkpoints preserve cumulative counters and event timestamps. Report input,
cached input, input minus cached input, and output separately. Output includes
reasoning where reported; do not add reasoning tokens again. These counters are
observed token usage, not a claim about billing or subscription quota weighting.
Counter snapshots may lag the final tool response; publish the checkpoint boundaries
and final reporting exclusions. Do not substitute Claude's modeled dollar estimate
for actual hosted usage.

Distinguish shared benchmark/setup cost, hosted-only implementation/verification,
and incremental hosted hybrid orchestration/assessment. Also report total hosted
usage for the pilot, because setup is not free. Historical harness development is
an additional unamortized investment not reconstructed by this pilot. No result
from a single tiny task establishes general cost effectiveness or equal code quality.

Acceptance checks are fixed before launch. Changes to an oracle or work order
invalidate that paired attempt and require a separately labeled trial. Accepted
product changes remain isolated; no merge or deployment is part of this pilot.
