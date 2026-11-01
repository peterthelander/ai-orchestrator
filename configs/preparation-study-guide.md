# Shared E007 guide
Read target AGENTS.md and docs/design-principles.md. Use unittest.TestCase with
synthetic PageText input. Focused checks FROM server/: .venv/bin/python -m unittest
discover -s tests -p test_page_headings.py -v. Same base, dependencies, scope,
criteria, full verification and external evaluation apply to both arms. No network.
