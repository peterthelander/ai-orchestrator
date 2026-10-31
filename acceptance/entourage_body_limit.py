"""Independent task oracle. Run with Entourage server's Python, cwd=server/."""
import asyncio
import json
from entourage_server.body_limit import BodyLimit


async def request(payloads, limit=None, method='POST', disconnect=False):
    incoming = [{'type': 'http.request', 'body': data, 'more_body': i < len(payloads) - 1}
                for i, data in enumerate(payloads)]
    if disconnect:
        incoming = [{'type': 'http.disconnect'}]
    calls, messages = [], []

    async def receive():
        return incoming.pop(0) if incoming else {'type': 'http.disconnect'}

    async def send(message):
        messages.append(message)

    async def app(scope, receive, send):
        first = await receive()
        calls.append(first)
        # Middleware must not replay the payload on a second receive.
        second = await receive()
        calls.append(second)

    middleware = BodyLimit(app) if limit is None else BodyLimit(app, max_bytes=limit)
    await middleware({'type': 'http', 'method': method, 'path': '/', 'headers': []}, receive, send)
    return calls, messages


async def main():
    for chunks in ([b'123456789'], [b'1234', b'56789'], ['éé'.encode(), 'ééé'.encode()]):
        calls, messages = await request(chunks, limit=8)
        assert not calls, 'Rejected request reached downstream app'
        assert messages[0]['status'] == 413
        data = json.loads(messages[1]['body'])['error']
        assert data['code'] == 'request_too_large'
        assert '8' in data['message'] and 'byte' in data['message'].lower(), data
        assert '1 MiB' not in data['message'], data
        assert '123456789' not in data['message']
    calls, messages = await request([b'1234', b'5678'], limit=8)
    assert not messages and calls[0] == {'type': 'http.request', 'body': b'12345678', 'more_body': False}
    assert calls[1]['type'] == 'http.disconnect'
    calls, messages = await request([b'x' * (1024 * 1024 + 1)])
    assert not calls and messages[0]['status'] == 413
    assert json.loads(messages[1]['body'])['error']['message'] == 'Request exceeds the 1 MiB limit.'
    calls, messages = await request([], limit=8, disconnect=True)
    assert not calls and not messages
    for method in ('GET', 'DELETE'):
        calls, messages = await request([b'123456789'], limit=8, method=method)
        assert calls and not messages
    print('Independent E001 acceptance checks passed')


asyncio.run(main())
