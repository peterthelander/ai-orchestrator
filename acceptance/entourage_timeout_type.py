"""E004: device timeout is a genuine positive integer, not bool/float."""
from entourage_server.config import Settings
for value in (True, False, 1.5, float('nan'), float('inf'), '120', None, 0, -1):
    try:
        Settings(device_timeout_seconds=value)
    except ValueError:
        pass
    else:
        raise AssertionError(('invalid timeout accepted', repr(value)))
for value in (1, 120, 1000000):
    settings = Settings(device_timeout_seconds=value)
    assert settings.device_timeout_seconds == value and type(settings.device_timeout_seconds) is int
assert Settings().device_timeout_seconds == 120
print('Independent E004 checks passed')
