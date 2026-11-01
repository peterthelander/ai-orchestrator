# Hybrid local and hosted coding: strategy notes

Consolidated November 1, 2026 from two strategy discussions and the experiment
reports in this repository. Proposed directions below are not an approved
implementation plan or changes to active experiment contracts. Implemented runner
behavior, observed results, and untested proposals are distinguished explicitly.

## Objective and constraints

Get more useful, verified coding work from a limited hosted allowance and limited
human attention. The user reports that intensive hosted sessions can exhaust an
allowance quickly and interrupt work for hours. The local model is Qwen with about
122B parameters, accessed through the Claude Code CLI; the CLI name should not be
confused with the underlying inference model. Local inference has no per-token
charge for the user, but is slower and less capable, with hardware and electricity
costs still present.

An overnight queue is attractive because local latency matters less while the
user is away. The goal is useful completed work, not maximizing local token output
or minimizing hosted tokens regardless of quality and supervision cost.

## Two distinct questions

1. Does implementation/review/repair improve the local model's output compared
   with local implementation alone, and enable work across fresh bounded contexts?
2. Does a hosted coordinator plus local execution deliver more useful verified work
   per unit of hosted allowance than doing the work directly with the hosted model?

A functioning loop does not establish either advantage. Fresh invocations and
compact persistent handoffs avoid an indefinitely growing conversation, but the
small tasks tried so far do not demonstrate solving work that exceeds a single
context window. More personas are a hypothesis, not a quality guarantee.

## What the existing experiments support

The runner already provides bounded implementation attempts, fresh review
contexts, independent checks, file-scope guards, preserved artifacts, and
acceptance tied to exact verified content. This is a useful execution foundation.

The E003 report documents an independent acceptance check catching a defect and
the local implementation repairing it without hosted intervention. This supports
the feasibility of unattended local repair within a clear contract.

The E002 history documents a nearby visible-br regression missed by both an
initial oracle and a local reviewer. Passing checks and valid review citations
therefore provide limited evidence, not proof of semantic correctness. Repeated
approvals from the same model can share blind spots. The reports reviewed in this
chat do not establish much incremental defect detection from mandatory repeated
reviews.

The first paired pilot did not establish an overall subscription-quota saving.
Task preparation, oracle construction, harness development, diagnosis, and result
assessment all count. Narrow execution-phase token savings cannot be presented as
an all-in saving. See BENCHMARK-01.md and the EXPERIMENT reports for evidence and
qualifications; do not extrapolate these small trials to general coding quality.

### Three-task batch: what changed in our understanding

[BENCHMARK-BATCH-02.md](BENCHMARK-BATCH-02.md) records the completed paired batch:

| Measure | Hosted-only | Hybrid |
|---|---:|---:|
| Completed workflows | 3/3 | 2/3 |
| Behavioral checks passed | 3/3 | 3/3 |
| Execution uncached input + output | 13,868 | 3,955 |
| Execution cached input | 973,056 | 1,303,040 |
| Elapsed execution | About 1 minute | About 60 minutes |

These token categories are unweighted observations, not subscription credits.
Shared preparation added 16,888 uncached-input/output tokens. Hybrid output and
cached input per completed workflow were higher; different setup allocations and
quota weights change the apparent advantage. The long existing chat confounds
cache comparisons. Lower marginal uncached/output activity is encouraging, but an
all-in allowance advantage remains unproven. Preparation consumed more of that
arithmetic token sum than the three hosted implementations themselves.

The unresolved local task passed all checks. Its reviewer falsely claimed that
`"straße".casefold()` does not produce `"strasse"`, despite a correct implementer
rebuttal. A runner defect compounded this: compact review context had removed the
implementer's rebuttal along with prior approval narratives. The rebuttal handoff
has now been repaired and unit-tested, but improved model behavior from that
repair has not yet been demonstrated. The batch was not retroactively rescored.

This supports improving preparation and dispute resolution before expanding the
persona hierarchy. Independent checks caught actual errors in earlier trials;
repeated same-model reviews have not yet demonstrated consistent added quality.

## Structure versus organic delegation

There is a spectrum between a fixed persona pipeline and a hosted agent that
freely decides when to invoke a local model. A promising middle ground is flexible
delegation backed by a deterministic job runner.

Keep judgment adaptable: which work to delegate, what context it needs, whether
review is warranted, and when hosted investigation is worth its cost. Keep
execution dependable: isolation, limits, waiting, output capture, verification,
and clear completion or failure states.

A tiny edit may cost less to perform directly than to delegate. A repetitive or
well-specified change may suit local execution. An ambiguous bug may need hosted
investigation before a local implementation task can be defined. Task suitability
depends more on clarity and verifiability than on line count alone.

Potential future standing guidance for a hosted coordinator:

> Hosted usage is scarce; local inference is slow but inexpensive. Delegate
> bounded implementation and investigation when the expected saving exceeds the
> cost of preparing and assessing the work. Let local jobs finish unattended.
> Verify results before relying on them.

That guidance alone is not a budget enforcement mechanism. Avoid repeated hosted
monitoring, lengthy orchestration narratives, strategy churn, and unbounded local
retries that erase the intended saving.

## Minimal execution contract worth retaining

- A clear deliverable, relevant context, allowed scope, and observable checks.
- An isolated workspace that preserves other work and prior artifacts.
- Explicit time and attempt limits; contracts remain fixed during an active run.
- Tool-side waiting rather than repeated hosted check-ins.
- A compact completion result, with detailed artifacts available on demand.
- Independent verification and a distinction between accepted output and
  integrated product changes.
- An explicit failure or escalation result when bounded attempts are exhausted.

Persona choices, dialogue formats, and mandatory review counts could become
task-dependent policies in future experiments. Compare alternatives separately;
do not weaken existing gates during a run to obtain acceptance.

## Review findings should be disputes that can be resolved

This is a proposed extension, not the current runner's implemented state machine.
A reviewer finding should not become an unconditional veto, and an implementer's
rejection should not automatically dismiss a genuine defect.

Track findings individually by stable ID. The implementer responds to each with
`fixed` plus change/verification evidence, or `disputed` plus a source-based reason
and preferably a reproducible counterexample. Review then marks each finding
resolved, withdrawn as a false positive, or still open. A still-open finding must
address the rebuttal and explain what evidence would settle the disagreement;
repeating the original assertion is not progress.

A practical bounded escalation policy:

1. Give the original reviewer one opportunity to reassess the implementer's reply.
2. If the dispute persists, ask a fresh local reviewer to adjudicate only that
   finding, current source, relevant checks, and the rebuttal. Do not preload prior
   approval narratives or frame either participant as authoritative.
3. If local disagreement remains, return a compact dispute packet to the hosted
   parent for a recorded decision. This can be an automated hosted-model escalation;
   it does not inherently require the human user to intervene.
4. If evidence, scope, or the configured hosted budget is insufficient, return an
   explicit unresolved/escalated result and let independent queued work continue.

A fresh invocation of the same model is less anchored, not an independent expert.
Do not resolve findings by vote count, fatigue, or automatically accepting the
implementer after a timeout. Hosted adjudication may withdraw a false finding
without product changes, but it cannot waive mandatory passing checks. Record who
made each decision, its evidence, the exact patch reviewed, and escalation usage.

Implemented today: source-ID citations, bounded review-output retries, check gates,
and delivery of a bounded implementer rebuttal when findings are open. Explicit
per-finding resolution states, a second adjudicator, and hosted-parent escalation
remain proposals. Citation validation establishes where code is, not that a review
interpretation is true.

## Make preparation proportional to the task

Separate reusable repository onboarding from work repeated for every task.
Onboarding establishes the environment, passing verification commands, important
architectural boundaries, and a short guide. Reuse these instead of rediscovering
the repository or producing a detailed dossier for each change.

A lightweight task brief can contain just the observed problem or desired result,
scope boundaries, and a few observable acceptance conditions. The local agent can
locate relevant files, investigate implementation details, and write regression
tests. A local planner can propose a small queue within a hosted-approved objective;
that does not authorize an open-ended invented roadmap.

Possible task-dependent preparation policies:

- Light: clear bounded changes in familiar code, using existing checks and local
  regression tests; no hosted implementation recipe or exhaustive file map.
- Standard: add a reproducible failure and a targeted external acceptance check
  when a plausible implementation could pass weak local tests.
- Detailed: hosted investigation or design for ambiguous, consequential, or poorly
  tested behavior, potentially keeping the task hosted instead of delegating it.

The independent checks in our experiments caught real mistakes. Reducing hosted
preparation must not mean assuming tests written by the implementer prove its own
correctness. Reuse existing independent gates, have review challenge test strength,
and reserve bespoke hosted oracles for cases that justify them. Keep evaluation
checks separate from the task-preparation treatment when comparing light and
detailed briefs; record the cost of constructing those checks rather than hiding it.
Freeze each run's contract before execution, even when the brief is short.

The preferred direction is less hosted micromanagement and more local investigation,
with selective hosted judgment. Whether a task merits delegation is itself a cost
tradeoff: a tiny direct hosted fix can be cheaper than preparing, reviewing, and
adjudicating its local equivalent.

## Possible daytime and overnight workflow

1. Prepare several tasks in one planning session, reusing repository guidance and
   verification infrastructure to amortize setup.
2. Execute a bounded local queue unattended. A failed task should not monopolize
   the night or block unrelated tasks.
3. Produce one morning report with outcomes, patch sizes, check results, remaining
   uncertainty, and items needing hosted attention.
4. Assess candidate patches together and spend hosted effort on exceptions and
   consequential decisions.

Start with independent tasks: reproduced bugs, explicit validation rules, bounded
transformations, and well-specified features in familiar code. Dependency-aware
queueing and integration require additional design; combined changes must be
verified against their actual combined base.

Interactive work can tolerate more organic delegation because the user can
clarify intent. Unattended work benefits from clearer contracts and stronger
bounds. Architecture and ambiguous product decisions remain sensible places to
spend hosted attention.

## Resource visibility reported in the other discussion

The other discussion recorded a read-only get_usage_limits tool in that Codex
desktop session. It returned
account-wide consumed percentages, window durations, reset timestamps, plan and
credit information, and available earned resets. Remaining percentage is derived
from consumed percentage. These values are shared across sessions and are not a
per-task budget. No reset was redeemed.

The availability of this tool corrects the earlier uncertainty about whether the
hosted coordinator could observe remaining allowance. Availability in that discussion
does not establish that an independent runner can call the same tool directly.

Official documentation also describes Codex App Server methods:

- account/rateLimits/read: allowance and reset information.
- account/rateLimits/updated: change notifications.
- account/usage/read: token-activity summaries and optional daily buckets.

For humans, the documented browser dashboard is
https://chatgpt.com/codex/settings/usage and an interactive Codex CLI supports
/status. The user reported that the browser link redirected to the main ChatGPT
page. The documentation target was confirmed, but signed-in browser behavior and
an alternative browser navigation route were not verified. Do not present that
link as a confirmed working route for this user.

Sources recorded as checked in the other discussion (not reverified by this merge):

- [Pricing reference](https://learn.chatgpt.com/docs/pricing)
- [App Server reference](https://learn.chatgpt.com/docs/app-server)

Remaining allowance is observable; the exact allowance cost of a proposed task
is not established. Raw token counts do not by themselves determine subscription
consumption. Concurrent sessions confound before-and-after account measurements.
Treat missing telemetry as unknown, not zero usage.

Useful future inputs include allowance remaining, reset time, attributable hosted
usage where available, local job status, queue length, recent completion times,
and success rates for comparable tasks. A user preference such as conserve usage,
balanced, or finish quickly could guide policy even with incomplete telemetry.

## What to measure before expanding the system

The central question is useful verified changes per unit of hosted allowance and
human attention. Track:

- Unattended completion rate, including failures and retries.
- Preparation and morning assessment effort.
- Hosted consumption, with shared setup and historical harness costs explicit.
- Overnight throughput and local execution time.
- Which candidate patches are worth integrating.
- Defects discovered during later review, integration, or use.

Reusable setup may amortize across a batch, but this remains a hypothesis to test.
Likewise, compare mandatory repeated review with other review policies in a
separately defined experiment, measuring actual defect detection as well as cost.

## Recommended order of experiments

1. Validate dispute handoffs and bounded escalation. Distinguish a corrected false
   positive from a reviewer pressuring the implementer to weaken a valid test.
   The existing rebuttal-delivery fix needs an actual local-model evaluation.
2. Compare lightweight and detailed preparation on representative new tasks with
   frozen, equivalent evaluation checks. Include local investigation, failed tasks,
   second reviews, hosted adjudications, and assessment in the accounting.
3. Evaluate the combined policy in a small unattended queue. Compare useful
   completed patches per attributable hosted allowance and human attention, not
   just successful invocations or local token volume.

Prefer one policy change at a time when attributing a result to its cause. If
operational efficiency favors testing lighter preparation and escalation together,
label it an end-to-end policy comparison rather than claiming which change helped.
Do not keep retuning the original examples and call that evidence of generalization.

Use short bounded hosted contexts or otherwise make cache accounting explicit.
If allowance telemetry is used, account for its resolution and simultaneous chats;
no visible percentage change does not establish zero consumption. Report setup,
execution, adjudication, maintenance, and evaluation separately, alongside totals.
A smaller execution bill is useful only if completion quality and supervision costs
remain acceptable.

My working recommendation is a small dependable runner with adaptive delegation,
lightweight task briefs by default, strong reusable verification, and selective
hosted adjudication. Overnight batching is the likely place to tolerate local
latency. Keep the persona hierarchy and orchestration system small until these
policies demonstrate a practical advantage.


## Follow-up progress: dispute and preparation studies

[DISPUTE-STUDY.md](DISPUTE-STUDY.md) records a bounded read-only replay tool and
parent-decision path. False Unicode objections were withdrawn both with and without
a rebuttal, so the single pair does not establish a rebuttal effect. A real-defect
control also demonstrated dangerous over-agreement with an incorrect implementer.
Captured check failures and mandatory escalation preserved the block; the final
original and fresh opinions upheld the defect, and the hosted parent recorded a
check-blocked decision. This is an experimental tool, not yet automatic integration
into every normal coding run. No earlier product outcome was reclassified.

[PREPARATION-STUDY.md](PREPARATION-STUDY.md) records one new paired heading-parser
task. A 114-character outcome brief and a 554-character recipe brief produced the
same production fix and both passed the same frozen checks. The short brief was not
faster or lower in local output tokens. This supports omitting unnecessary recipes
for clear work, while leaving broader hosted-preparation and quota savings unproven.
Shared acceptance criteria, scope, and evaluator construction were still supplied.

Keep strong independent gates and skeptical adjudication together: flexibility by
itself can turn review into rubber-stamping. The next deployment step is a bounded
normal-run escalation integration using the tested packet/decision rules. Broader
light-preparation batches should count investigation, evaluator construction, failed
work, adjudication, and assessment rather than only brief length.
