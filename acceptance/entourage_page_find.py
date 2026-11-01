"""Independent E003 oracle: compare excerpts with original text coordinates."""
import asyncio
import httpx
from entourage_server.web_pages import read_web_page


async def read(text, **args):
    async def resolver(host, port):
        return '93.184.216.34'
    def reply(request):
        return httpx.Response(200, text=text, headers={'content-type': 'text/plain; charset=utf-8'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        return await read_web_page({'url': 'https://example.com/page', **args}, client=client, resolver=resolver)


async def main():
    for text, phrase, original_index in (
        ('ß' * 600 + 'NEEDLE' + 'x' * 900, 'needle', 600),
        ('ﬃ' * 600 + 'Straße' + 'x' * 900, 'STRASSE', 600),
        ('ß' * 600 + 'İ' + 'x' * 900, '\u0307', 600),
        ('A' * 900 + 'TaRgEt' + 'x' * 900, 'target', 900),
        ('ß' * 600 + 'needle' + 'x' * 700 + 'NEEDLE', 'needle', 600),
        ('ß' * 99000 + 'needle' + 'x' * 1200, 'NEEDLE', 99000),
    ):
        result = await read(text, find=phrase)
        expected = max(0, original_index - 500)
        bounded = text[:100000]
        assert result['status'] == 'read', result
        assert result['find_matched'] is True, result
        assert result['offset'] == expected, (phrase, expected, result['offset'])
        assert result['text'] == bounded[expected:expected + 8000]
        assert phrase.casefold() in result['text'].casefold(), phrase
    text = 'abc' * 4000
    absent = await read(text, find='missing')
    assert absent['find_matched'] is False and absent['offset'] == 0
    assert absent['text'] == text[:8000] and absent['next_offset'] == 8000
    offset = await read(text, offset=250)
    assert offset['find_matched'] is None and offset['offset'] == 250
    assert offset['text'] == text[250:8250] and offset['next_offset'] == 8250
    first = await read('Straße---STRASSE', find='strasse')
    assert first['find_matched'] is True and first['offset'] == 0
    print('Independent E003 acceptance checks passed')


asyncio.run(main())
