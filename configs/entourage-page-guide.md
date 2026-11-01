# Entourage PageText task guide
Read target AGENTS.md and docs/design-principles.md. The active service lives in
server/entourage_server. Task scope is the deterministic PageText HTML parser in
web_pages.py and one NEW standard-library unittest module. Existing network access
and safety rules in the same file must remain untouched.
Run focused checks FROM server/: .venv/bin/python -m unittest discover -s tests -p test_page_text_void.py -v
Use unittest.TestCase, synthetic HTML strings, and table-driven subTest cases. No
pytest, async fixtures, real pages, DNS calls, or model requests are needed. Prefer
a small parse helper and a few focused tests with assertions on visible/hidden
text and extracted links. Test observable behavior rather than helper names.
The runner executes the full server suite, client suite, lint, TypeScript checks,
and an independent task oracle. Baseline is 186 server and 46 client tests. Python
lint/type gates and ingestion checks remain outside the onboarded verification.
HTML void tags have no required end tag. Hidden non-void containers must continue
suppressing their contents until their matching closing tag. Inspect both normal
and self-closing event handling before editing. Keep changes narrow.
