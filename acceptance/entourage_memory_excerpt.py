"""E006: memory excerpts use original-text coordinates after Unicode folding."""
from pathlib import Path
from tempfile import TemporaryDirectory
from entourage_server.journals import MARKER
from entourage_server.memory import search_memories

def lookup(directory, text, keywords):
    document = (MARKER + '\n# 2026-01-01\n\nTimezone: `UTC`\n\n'
                '## 2026-01-01T12:00:00+00:00 — User\n\n'
                'Source: `conversation=test; message=1; turn=imported; utc=2026-01-01T12:00:00+00:00`\n\n'
                '> ' + text + '\n')
    (directory / '2026-01-01.md').write_text(document)
    return search_memories(directory, {'keywords': keywords})
with TemporaryDirectory() as temp:
    directory = Path(temp)
    for prefix, target, keywords in (
        ('ß' * 300, 'NEEDLE', ['needle']),
        ('ﬃ' * 300, 'Straße', ['STRASSE']),
        ('ß' * 300, 'İ', ['\u0307']),
        ('x' * 400, 'TARGET', ['target']),
        ('ß' * 300, 'needle' + 'x' * 100 + 'other', ['other', 'needle']),
    ):
        text = prefix + target + 'z' * 1000
        result = lookup(directory, text, keywords)
        expected = max(0, len(prefix) - 120)
        assert result['status'] == 'matches' and len(result['results']) == 1, result
        hit = result['results'][0]
        assert hit['excerpt'] == text[expected:expected + 500], (keywords, hit['excerpt'])
        assert hit['excerpt_truncated'] is True and hit['message_id'] == 1
    assert lookup(directory, 'Nothing relevant', ['missing'])['status'] == 'no_matches'
    first = lookup(directory, 'Straße and STRASSE', ['strasse'])
    assert first['results'][0]['excerpt'] == 'Straße and STRASSE'
print('Independent E006 checks passed')
