"""
Short-lived, process-wide cache for the data every page's shell needs.

The footer's brand list, the promo banner and the admin-editable site settings are on
essentially every page, and each was a blocking round trip to store-api before the HTML
could be sent. They're all slow-moving, so a short shared TTL removes that cost without
anyone noticing the lag.

Its own module rather than a closure inside app.py's create_app() for one reason:
blueprints need to be able to *invalidate* an entry (see blueprints/admin/settings.py,
which clears the settings entry the moment an admin saves), and app.py imports the
blueprints - so anything they import back from it would be a circular import.
"""
import time

TTL = 60  # seconds

_cache = {}


def cached(key, produce):
    """Memoize `produce()` under `key` for TTL seconds.

    A miss is never stored on failure - the exception propagates out of produce()
    before anything is written - so a store-api blip isn't cached as an empty list for
    the next minute.
    """
    now = time.monotonic()
    hit = _cache.get(key)
    if hit is not None and hit[0] > now:
        return hit[1]
    value = produce()
    _cache[key] = (now + TTL, value)
    return value


def invalidate(key=None):
    """Drop one entry, or everything when `key` is None.

    Only affects THIS process. With several Flask workers the others keep their copy
    until it expires, so the TTL above is still the guarantee - this just makes the
    common single-process case (and the worker that handled the save) update instantly
    instead of leaving an admin staring at a page that hasn't changed yet.
    """
    if key is None:
        _cache.clear()
    else:
        _cache.pop(key, None)
