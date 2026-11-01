# Commands and contracts

Use `ai-orchestrator` after installation, or
`python3 <skill-directory>/scripts/orchestrator.py` with the same arguments.
Python 3.12, Git, Linux/WSL, and the user's Claude CLI are required. The package
uses only Python's standard library. Keep the maintained checkout in place;
installation links to it instead of copying a second version.

## Repository onboarding

```bash
ai-orchestrator init my-project --repo /absolute/path/to/project \
  --check '{"name":"unit","cwd":".","argv":["python3","-m","unittest","discover","-s","tests"]}'
```

Edit the generated profile and guide at
`~/.local/share/ai-orchestrator/profiles/my-project.{json,md}`. Choose actual
repository commands: do not substitute a trivial check merely to get a green run.
Repeated `--check` adds more gates; `init` without checks creates a draft that
cannot run until real checks are configured. Profiles and logs stay local.

Optional profile fields:

```json
{
  "setup": [
    {"name":"dependencies","cwd":".","argv":["npm","ci"]}
  ],
  "node_bin": "/absolute/path/to/linux-node/bin",
  "environment_file": "~/.bashrc",
  "environment_keys": ["ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL"],
  "test_guide": "optional-test-conventions.md",
  "acceptance_checks": [],
  "max_rounds": 4,
  "min_review_rounds": 1,
  "dispute_escalation": true
}
```

Guide paths are relative to the profile directory. All command `cwd` values are
relative to the isolated worktree. Commands are argv arrays, not shell strings;
use an explicit interpreter for a trusted setup script when necessary. Setup runs
in each worktree before baseline checks and must leave Git clean (dependencies
must be ignored). No automatic symlinks to a source checkout's private runtime data.
A shared virtual environment can instead be referenced by absolute executable path
if appropriate for that repository. Environment comes from the current process;
optional environment-file loading reads only named literal exports, never sources
the file. Never put secrets in a profile, task, guide, or argv.

```bash
ai-orchestrator doctor my-project
```

Doctor creates an isolated worktree, runs setup and all baseline gates, and saves
evidence. It does not call the model or prove endpoint authentication/connectivity.
Fix baseline/environment problems before preparing implementation tasks.

## Task contract

Write a JSON file outside the target checkout (for example in the orchestrator's
local data directory):

```json
{
  "id": "T001",
  "title": "Reject invalid timeout values",
  "problem": "Require a positive integer timeout and preserve the existing default.",
  "allowed_files": ["src/settings.py", "tests/test_timeout.py"],
  "required_changed_files": ["src/settings.py", "tests/test_timeout.py"],
  "acceptance_criteria": [
    "Positive integers are accepted; bool, zero, negative and fractional values raise ValueError.",
    "Existing defaults and unrelated settings behavior remain unchanged."
  ]
}
```

Allowed files are explicit paths, not globs or directories. Keep existing gate and
oracle files outside the implementation's allowed scope. A new regression test can
be allowed, but is additional evidence, not an independent oracle.

For additional task checks, write a JSON array of check objects using the same
name/cwd/argv schema. Trusted independent scripts can live outside the worktree;
reference their absolute paths. Freeze them for the run. Baseline excludes
`acceptance_checks` because the requested behavior may intentionally be missing.

```bash
ai-orchestrator run my-project --task /path/to/task.json --acceptance /path/to/checks.json
ai-orchestrator status /path/printed/by/run
ai-orchestrator queue my-project --task /path/to/one.json --task /path/to/two.json
```

Run defaults to committed HEAD, even if the source checkout is dirty. Use `--base`
for another committed revision. Each queue task starts from the same frozen base;
queue is for independent tasks only. For task-specific checks in a queue, use
separate `run` calls or a profile whose acceptance checks apply to every task.
Tasks continue past failure or parent escalation. Never automatically combine
individually accepted patches without checking their integration.

Default bounds: four implementation rounds, one valid review required, two output
format attempts per review, one hour per model invocation, ten minutes per check.
These are execution limits, not a wall-clock SLA. Tool-side waits may last a long
time. Repeated findings after implementer response and reviewer reconsideration
receive one fresh local adjudication; unresolved findings produce a parent packet.
Invalid review output also escalates. Check failures go back to implementation and
can never be overridden by a reviewer or parent decision.

## Hosted parent handoff

Run returns 0 for accepted, 1 for stopped/unresolved/check failure, and 2 for
`parent_required`. Read the summary's `parent_packet` and save:

```json
{
  "author": "hosted_parent",
  "resolutions": [
    {"id":"R1","decision":"withdrawn","reason":"The cited input casefolds to strasse, as confirmed by the check and current source."}
  ]
}
```

Use exactly one resolution for each packet finding; decisions are `withdrawn`,
`upheld`, or `uncertain`. For an invalid review with no findings, the list is empty;
inspect the task/diff/checks and failure reason rather than inventing a finding.
Parent decisions are trusted local records, not authenticated signatures.

```bash
ai-orchestrator resume /path/to/run --decision /path/to/decision.json
```

Resume requires unchanged source, base/index, task/config, and runner controls.
All withdrawals permit acceptance only after the required valid review count and
fresh final checks. Upheld findings go to remaining implementation rounds; uncertain
decisions remain escalated. Exhausted bounds retain the work for inspection rather
than starting an endless loop. Resume is for saved escalations, not arbitrary crash
recovery; an interrupted run needs a fresh isolated attempt.

Artifacts contain model transcripts and repository source; treat them as local
private data. `AI_ORCHESTRATOR_HOME` overrides the data directory. `CODEX_HOME` or
`install --codex-home` selects skill installation; `install --bin-dir` selects the
launcher directory. The installer does not overwrite an existing unrelated skill
or launcher. Add that bin directory to PATH if needed and open a new Codex session.

The implementation model has Bash access. Worktrees and file guards protect
acceptance and preserve ordinary changes; they are not an adversarial sandbox.
