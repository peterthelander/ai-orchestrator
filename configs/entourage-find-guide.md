# E003 shared work order guidance
Read target AGENTS.md and docs/design-principles.md. Work only on search-coordinate
calculation in server/entourage_server/web_pages.py and the task's new test module.
Use unittest.IsolatedAsyncioTestCase and httpx.MockTransport plus a stub resolver.
No live HTTP/DNS/inference calls are required. Run focused tests FROM server/:
.venv/bin/python -m unittest discover -s tests -p test_page_find_unicode.py -v
The full server suite, seven client test files, lint, TypeScript, and the external
acceptance oracle are required for both comparison arms. Baseline is 186 server
and 46 client tests. Existing tests and all other behavior must be preserved.
Use a clear bounded approach compatible with the existing 100000-character text
limit; avoid repeatedly folding every growing prefix (quadratic work). Both arms
receive the same task, guide, source revision, dependencies, and acceptance oracle.
