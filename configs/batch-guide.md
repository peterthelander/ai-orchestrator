# Shared batch guidance
Read target AGENTS.md and docs/design-principles.md. Use standard-library unittest,
small synthetic fixtures and table-driven subTests. Run Python tests FROM server/:
.venv/bin/python -m unittest discover -s tests -p <task test filename> -v
No live inference, network, private data, or new dependencies. Generated-journal
fixtures must include the existing MARKER, timestamp, Source line, and quoted text.
The same task, dependencies, source revision, allowed files and external oracle
are provided to hosted and hybrid arms. Preserve unrelated behavior. Complete only
the approved work order. Review has integer criterion IDs 1 through the actual
number of criteria, not always five. Cite supplied source IDs, not copied code.
