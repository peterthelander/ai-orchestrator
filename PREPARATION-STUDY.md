# Lightweight versus detailed preparation — paired pilot

E007 is a new, deliberately small parser task: preserve block boundaries for heading
levels h5/h6 as already done for h1-h4. The light brief supplies the desired result;
the detailed brief adds a reproduction, relevant methods, suggested approach and
test cases. Both receive identical scope, acceptance criteria, shared guidance,
dependencies, base revision and frozen independent evaluation oracle. The oracle
fails on baseline. The same three-round/two-review policy is used in both arms.

This tests whether implementation recipes can be removed without losing verified
completion. It does not yet test fully local task discovery or removal of custom
hosted oracles. Shared evaluator construction remains hosted effort. One pair on
familiar parser code is not general evidence of prep cost savings.

Run light then detailed sequentially, unattended, without inspections or interventions.
Order is not randomized and provider caching may influence timing. Preserve failed
attempts and fixed contracts; do not tune prompts or gates after seeing one arm.


## Results

Both arms were accepted after two implementation/review rounds and passed all five
gates. Their production diffs are byte-for-byte identical: add h5/h6 to the existing
start-tag and end-tag block-boundary sets. Each also passed 46 client tests, lint,
TypeScript, and the frozen external oracle. One review-output retry was needed in
each arm. There were no product-change requests from either reviewer.

| Arm | Outcome | Local elapsed time | Local output tokens reported by Claude | Server tests |
|---|---|---:|---:|---:|
| light | accepted | 12.1 min | 10,911 | 193 |
| detailed | accepted | 11.4 min | 10,667 | 195 |

The light problem statement was 114 characters; the detailed statement was 554.
Those lengths describe ONLY the problem field, not the whole prompt, acceptance
criteria, or hosted preparation cost. Shared scope, guide, verification commands,
and evaluation oracle were identical. The light test module was 4,402 bytes and the
detailed test module 5,299 bytes; more bytes/tests are not taken as a quality score.

The short brief succeeded without the implementation recipe on this task. It did
not improve local elapsed time or reduce reported local output tokens. This supports
trying outcome-oriented briefs for clear familiar tasks, but does not establish a
quota saving, equal quality beyond the checks, or independence from task selection.
It also does not demonstrate that the local model can safely discover arbitrary
scope or design its own independent oracle. Hosted oracle construction and all
study preparation remain real work, with no newly measured quota reduction claim.

The original Entourage checkout is unchanged. Product patches remain uncommitted
in the two isolated worktrees; no code was merged or deployed. Exact run directories
and snapshots are in `runs/preparation-study/summary.json`. Do not fold these results
into the earlier hosted-vs-hybrid benchmark or retroactively change its counts.

## Working policy

For clear tasks, omit an implementation recipe unless investigation shows it is
needed. Retain concise observable acceptance criteria, allowed scope, and reusable
checks. Use detailed hosted preparation selectively. Test broader prep reduction
separately, including task investigation and oracle cost, before claiming savings.
