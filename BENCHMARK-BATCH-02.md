# Three-task amortization batch — protocol

E004 (timeout types), E005 (canonical record dates), and E006 (Unicode memory
excerpts) are fixed before launch. They cover two small validation contracts and
one transfer of the earlier Unicode coordinate defect into another subsystem.
This intentionally small, nonrandom sample cannot establish general coding quality.

Both arms use independent clean worktrees at d28c70a and the same task-specific
oracle plus full server/client tests, lint, and TypeScript. Each oracle was confirmed
to fail on the baseline. The local arms reuse the existing runner and source-ID
review protocol, with three implementation rounds, at least two valid reviews,
three output-format attempts, and a 30-minute timeout per invocation. Failures count;
there are no undocumented retries or changes to a contract during a run.

Run the local arms sequentially without stage inspections. Finish all hosted-only
implementations before inspecting local outputs. Record hosted execution and hybrid
orchestration/assessment usage separately, with shared preparation and reporting
as additional cost. Preserve raw usage snapshots locally and publish normalized
deltas. No token-to-quota or billing conversion is assumed. Previous harness
investment remains outside this batch's measured costs and must be acknowledged.

All product patches remain isolated. No original checkout edits, merges, deployments,
or claims that passing tests prove identical quality are part of this protocol.


## Results

The local batch ran unattended for 60.0 minutes. All hosted-only work
was completed before local outputs were inspected; its measured execution interval
was about 1.2 minutes. Both arms used the frozen checks above.

| Task | Hosted-only | Hybrid workflow | Behavioral gates | Python tests: hosted / hybrid |
|---|---|---|---|---|
| E004 timeout types | Verified | Accepted | Both pass | 188 / 196 |
| E005 canonical dates | Verified | Accepted | Both pass | 189 / 197 |
| E006 Unicode excerpts | Verified | Unresolved at round limit | Both pass | 188 / 195 |

Each arm also passed 46 client tests, lint, TypeScript, and its independent oracle.
More tests are not assumed to mean higher quality. All product patches remain in
isolated worktrees; the original Entourage checkout is unchanged.

### Why the third local workflow failed

The reviewer falsely claimed `"straße".casefold()` remains `"straße"`; Python
actually returns `"strasse"`. The implementer correctly rejected that finding with
a counterexample and passing tests. The reviewer repeated it until the round limit.
This counts as unresolved even though all behavioral checks passed. Other local
reviews approved without actionable product findings. The batch therefore does not
demonstrate that review improved product quality; it did block valid work once.
The local Unicode fix also builds a per-character dictionary where the hosted fix
uses a smaller scalar scan. That is a source observation, not a memory benchmark.

### Observed hosted usage

Joint assessment is conservatively charged entirely to hybrid below. Cached input,
uncached input and output have unknown subscription weights. The arithmetic sum
is not a billing or quota unit. Output already includes reported reasoning.

| Execution metric across three attempts | Hosted-only | Hybrid + joint assessment |
|---|---:|---:|
| Workflow completions | 3 | 2 |
| Uncached input | 10,279 | 1,396 |
| Output | 3,589 | 2,559 |
| Uncached input + output | 13,868 | 3,955 |
| Cached input | 973,056 | 1,303,040 |
| Uncached input + output per completion | 4,623 | 1,978 |
| Output per completion | 1,196 | 1,280 |
| Cached input per completion | 324,352 | 651,520 |

Uncached-input-plus-output is 71% lower
in aggregate and 57% lower per completion
for hybrid. However, output and cached input per completion are HIGHER. This does
not establish quota savings. The existing long chat is a cache-volume confounder.

| Additional accounting | Uncached input | Output | Cached input |
|---|---:|---:|---:|
| Shared task/oracle preparation | 10,257 | 6,631 | 1,242,112 |
| Hosted execution | 10,279 | 3,589 | 973,056 |
| Hybrid launch/wait | 796 | 1,489 | 973,952 |
| Joint assessment | 600 | 1,070 | 329,088 |
| Post-batch diagnosis, repair and reporting | 4,062 | 8,814 | 1,004,160 |
| Measured total | 25,994 | 21,593 | 4,522,368 |

Shared preparation alone adds 16,888 uncached-input-plus-output tokens. If its
entire cost is included in each standalone approach, that arithmetic per completion
becomes 10,252 hosted versus
10,422 hybrid, nearly erasing the marginal
advantage. Other allocations give other answers and must be explicit. Historical
harness development, final response and publishing after the checkpoint are additional
costs. Meter snapshots may lag boundary tool responses. Report preparation includes
repair of a reporting-script path error; that work was not free.

### Handoff repair after the frozen batch

Inspection found a runner defect: compact review context retained open findings but
omitted the implementer's rebuttal. The correct E006 response was saved in dialogue
but never delivered to its next reviewer. Avoiding approval anchoring had also
removed useful dispute evidence.

After the batch, the runner was changed to supply up to 6000 characters of the latest
implementer response ONLY when findings are open, explicitly labeled unverified.
Clean reviews still omit previous narratives. A regression test checks both paths;
all 14 runner tests pass. This repair was not used to recategorize E006 or change any
batch result. No improvement in model review from the repair has yet been demonstrated.
Its hosted maintenance cost is included in the accounting above.

### Interpretation

Reusing the setup across three tasks reduced measured incremental uncached/output
hosted activity, but completion failures, setup effort and cache weighting prevent
an all-in quota advantage claim. Preparation consumed more of that arithmetic token
sum than the three hosted implementations themselves. The next practical targets
are cheaper task/oracle preparation and reliable dispute handoffs, rather than
adding more personas. This is three small nonrandom tasks, including transfer of a
previously studied Unicode defect, not a general coding benchmark.

### Artifacts

Normalized counters: [batch-02-usage.json](benchmarks/batch-02-usage.json).
Full local records and six patches: `runs/benchmark-batch-02/`; worktrees:
`runs/targets/e004-hosted` / `e004-hybrid`, similarly E005 and E006. Exact run paths
are in the local summary. All patches remain isolated and uncommitted. No product
changes were merged or deployed.
