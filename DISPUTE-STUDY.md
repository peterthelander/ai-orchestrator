# Dispute-resolution replay protocol

This study replays frozen source and findings without implementation edits or
retroactive acceptance. Case A uses the actual E006 false Unicode finding without
a rebuttal. Case B uses the same source/finding with the actual implementer rebuttal.
Case C uses the genuine E002 visible-br regression and a deliberately incorrect
synthetic implementer rejection. Expectations are withheld from model prompts.
One instance of each is exploratory, not a causal estimate of model reliability.

For each case, execute the existing mandatory checks, then ask the original reviewer
to reconsider each ID. A finding is withdrawn, upheld, or uncertain, with an explicit
reason and source-backed normal review. Original opinions that do not withdraw all
findings trigger at most one fresh local adjudicator. Each opinion has at most three
format retries. Still-disputed cases produce a compact parent packet for hosted
assessment after the local suite exits. No majority vote or retry exhaustion accepts
code. Failed checks remain blocking regardless of reviewer or hosted opinion.

All cases run unattended, read-only, with snapshots and exact patch hashes. This
script is a replay/evaluation tool; it does not yet replace the main implementation
runner's acceptance state machine or automatically call a paid hosted API. The
current parent agent can assess emitted packets and record per-finding decisions.
This known-case replay tests the protocol, not generalization to new tasks.

## Results and limits

The first suite withdrew the real historical false Unicode finding in BOTH the
without-rebuttal and with-rebuttal cases. This does not demonstrate a causal benefit
from supplying the rebuttal; one fresh review was enough to change the answer in
either case. The source and actual historical rebuttal remained unchanged.

The real-defect control initially upheld the visible-br finding, but its fresh
adjudicator returned malformed output. That revealed an underspecified adjudicator
prompt and a missing format-failure fallback. After those were fixed, a retry's
original reviewer instead withdrew the real finding, persuaded by the deliberately
incorrect implementer response. Its claimed HTML argument contradicted a failed
behavioral check. No product was accepted: this is a warning that more flexible
review can become rubber-stamping.

The final control included the captured check failure in the handoff. The original
reviewer and fresh adjudicator both upheld the defect. The emitted parent packet
was then assessed by the current hosted parent, which upheld the finding and
recorded `blocked_checks`. The product remained unaccepted. Several things changed
between complete attempts; no result is attributed solely to failure-output inclusion.

The implemented replay tool now provides:

- Per-ID withdrawn/upheld/uncertain decisions, with consistency validation.
- One original reconsideration and at most one fresh local adjudicator, each with
  bounded output retries and strictly read-only tools.
- Captured failed-check output, rather than only an exit code and inaccessible name.
- A parent packet for retained disputes, failed checks, or exhausted format retries.
- Explicit parent decision recording tied to current patch/source hashes, rejecting
  stale or incomplete decisions. Failed checks cannot be waived.
- No product acceptance or retroactive reclassification of earlier runs.

Twenty-two repository tests pass, covering mixed findings, invalid decisions,
read-only tool exposure, parent fallback, stale source, and failed-check protection.
The original Entourage checkout and all frozen product cases remain unchanged.

## Use and implementation boundary

Run `python3 dispute_review.py --manifest <local-case-manifest.json>`. Each case
specifies a config, task, findings file, and optional implementer-response file.
Expectations are evaluator-only and must not be included in model prompts.

To record parent adjudication:

```bash
python3 dispute_review.py --parent-packet <run>/parent-packet.json --decision <decision.json>
```

The decision contains `author: hosted_parent` and a complete `resolutions` list.
This is a trusted local audit record, not cryptographic authentication. The replay
tool never promotes a patch to accepted, even after findings are withdrawn. It is
not yet wired into every normal coding run as an automatic escalation state machine.
That integration should retain the same check gates and evidence record, rather
than treating a second opinion or parent decision as permission to bypass checks.

Local initial, retry, and final results are preserved in `runs/dispute-study/`.
The final control is `runs/dispute-20261101T132009849882Z-case-c-final/`, including
its parent packet and recorded hosted decision. No private run artifacts are published.
