# Python middleware test conventions

Entourage's Python service uses the STANDARD LIBRARY unittest runner, not pytest.
Use unittest.IsolatedAsyncioTestCase for async tests, synthetic ASGI messages, and
small helpers. No plugins or dependencies are needed. From the target's server/:

    .venv/bin/python -m unittest discover -s tests -p test_body_limit.py -v

ASGI response-start messages use `status`; response-body messages use `body`.
`http.disconnect` is an ordinary ASGI receive message. Preserve existing disconnect
and replay handling unless a demonstrated failing case requires a change.

A compact helper pattern (adapt assertions to the actual task):

```python
import unittest

class MiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, middleware_factory, chunks):
        incoming = iter([
            {"type": "http.request", "body": chunk,
             "more_body": i < len(chunks) - 1}
            for i, chunk in enumerate(chunks)
        ])
        sent, delivered = [], []

        async def receive():
            return next(incoming, {"type": "http.disconnect"})

        async def send(message):
            sent.append(message)

        async def app(scope, receive, send):
            delivered.append(await receive())
            delivered.append(await receive())

        await middleware_factory(app)(
            {"type": "http", "method": "POST"}, receive, send)
        return sent, delivered
```

For an accepted multi-chunk request, assert the first delivered body is the joined
input and the second message is the distinct upstream disconnect. For a rejection,
assert response status/code/message and that no body reached the app. Use subTest
for boundary and UTF-8 cases. Prefer roughly 4–6 focused tests; this is guidance,
not a quota or line-count gate. Check real semantics, not exact JSON byte ordering
or an implementation helper's existence.
