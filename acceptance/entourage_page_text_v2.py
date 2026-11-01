"""Independent E002 oracle: synthetic HTML only, no fetching or DNS."""
from entourage_server.web_pages import PageText


def parse(html):
    parser = PageText('https://example.com/start')
    parser.feed(html)
    parser.close()
    return parser


# Guard adjacent visible formatting before testing the original hidden-void defect.
for html, expected in (
    ('<p>Before<br>After</p>', 'Before\nAfter'),
    ('<p>Before<br/>After</p>', 'Before\nAfter'),
    ('<p>A<br><br>B</p>', 'A\nB'),
    ('<p>A<br hidden>B</p>', 'A B'),
    ('<p>A<br aria-hidden="true"/>B</p>', 'A B'),
    ('<p>Before<img>After</p>', 'Before After'),
):
    actual = parse(html).text()
    assert actual == expected, (html, expected, actual)

voids = ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
         'link', 'meta', 'param', 'source', 'track', 'wbr')
for tag in voids:
    for attribute in ('hidden', 'aria-hidden="true"'):
        for closing in ('>', '/>'):
            parser = parse(f'<{tag} {attribute}{closing}<p>Visible tail</p><a href="/next">Next link</a>')
            assert 'Visible tail' in parser.text(), (tag, attribute, closing, parser.text())
            assert {'text': 'Next link', 'url': 'https://example.com/next'} in parser.links
for html in (
    '<div hidden><input><span>Secret</span></div><p>Shown</p>',
    '<div aria-hidden="true"><img/><p>Secret</p></div><p>Shown</p>',
    '<script>Secret</script><style>Secret</style><p>Shown</p>',
    '<div hidden><section><br><p>Secret</p></section></div><p>Shown</p>',
):
    parser = parse(html)
    assert 'Shown' in parser.text() and 'Secret' not in parser.text(), parser.text()
parser = parse('<title>Example title</title><p>Before</p><img><p>After &amp; more</p><a href="/x">Link</a>')
assert ''.join(parser.title) == 'Example title'
assert 'Before' in parser.text() and 'After & more' in parser.text()
assert parser.links == [{'text': 'Link', 'url': 'https://example.com/x'}]
print('Independent E002 acceptance checks passed')
