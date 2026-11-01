"""E007 evaluation oracle: all six headings are text block boundaries."""
from entourage_server.web_pages import PageText

def parse(html):
    p = PageText('https://example.com/base')
    p.feed(html)
    p.close()
    return p

for level in range(1, 7):
    tag = f'h{level}'
    assert parse(f'Before<{tag}>Heading</{tag}>After').text() == 'Before\nHeading\nAfter', tag
    assert parse(f'Before<{tag} hidden>Secret</{tag}>After').text() == 'Before After'
    assert parse(f'Before<{tag} aria-hidden="true">Secret</{tag}>After').text() == 'Before After'
    linked = parse(f'<{tag}><a href="/next">Heading</a></{tag}>After')
    assert linked.text() == 'Heading\nAfter' and linked.links == [{'text': 'Heading', 'url': 'https://example.com/next'}]
assert parse('<h5>First</h5><h6>Second</h6>').text() == 'First\nSecond'
assert parse('<title>Title</title><h6>A &amp; B</h6><p>Body</p>').text() == 'A & B\nBody'
assert parse('Before<br>After').text() == 'Before\nAfter'
assert parse('<script>Secret</script><h5>Visible</h5>').text() == 'Visible'
print('Independent E007 evaluation checks passed')
