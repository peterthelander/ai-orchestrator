# Entourage experiment guide
Target: the repository selected in your configuration. Read its AGENTS.md and docs/design-principles.md.
The active app uses a Python service in server/entourage_server; client code is TypeScript. Runtime data and inference configuration are private and out of scope.
Use server/.venv/bin/python; Python test discovery must run FROM server/, not the repository root. Select a Linux Node installation via node_bin in the configuration; do not use Windows Node against a WSL checkout.
Baseline observed on 2026-10-31: 186 server unittest tests and 46 Node tests pass. Expo lint and TypeScript checks are enforced separately by the runner. Existing generated trial changes were discarded before onboarding.
This experiment permits only the task's server middleware and one NEW test file. Preserve all existing tests. No live service, model call, deployment, dependency update, or UI change is required.
Python lint/type checking and ingestion verification are NOT yet onboarded. This is a bounded experimental gate, not full production readiness.
