"""E005: source-record event dates are canonical calendar dates."""
import copy
from entourage_server.knowledge_contracts import validate_records
base = {'version': 1, 'id': 'sample', 'kind': 'note', 'title': 'Sample', 'text': 'Evidence',
        'observed_at': '2026-01-01T00:00:00+00:00',
        'source': {'uri': 'fixture://sample', 'locator': 'line 1', 'sha256': '0' * 64}}
for value in ('20240229', '2024-W09-4', '2023-02-29', '', ' 2024-02-29', True, 20240229, [], {}):
    record = {**base, 'event_date': value}
    try:
        validate_records([record])
    except ValueError:
        pass
    else:
        raise AssertionError(('invalid event_date accepted', repr(value)))
for extra in ({}, {'event_date': None}, {'event_date': '2024-02-29'}, {'event_date': '2026-11-01'}):
    record = {**base, **extra}; before = copy.deepcopy(record)
    result = validate_records([record])
    assert result == {'sample': before} and record == before
print('Independent E005 checks passed')
