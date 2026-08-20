"""Turning a pasted map link into a usable location, and back again.

A customer marks where to deliver in one of two ways: they drop a pin on the
picker (which yields coordinates directly and needs nothing in here), or they
paste a link they shared to themselves from the Google Maps app. This module is
about the second case.

Two things make that harder than one regex:

  * **Google Maps has no single URL shape.** The desktop site puts coordinates
    after an `@`, the share sheet puts them in a `q=`/`query=` parameter, and
    place pages hide the *authoritative* pair inside the `!3d..!4d..` blob (the
    `@` coordinates on those pages are the map viewport's centre, which is near
    the pin but is not the pin). parse_coordinates() knows all of them, and
    prefers `!3d!4d` when both are present.
  * **The mobile app shares a SHORT link** (`https://maps.app.goo.gl/xxxx`)
    with no coordinates in it at all - they only appear after following the
    redirect. That needs a server-side fetch, which is what expand_short_link()
    does, behind the host allowlist below.

Failing to read coordinates out of a link is not an error worth blocking on:
the link itself is stored either way and a human can still open it. See the
column comments on Customer.latitude in store-api/app/models.py.
"""
import re
from urllib.parse import unquote, urljoin, urlparse

import requests

# Hosts expand_short_link() may fetch. This is an allowlist, not a blocklist,
# and it is the whole security design of this module: it takes a URL from a
# logged-in user's browser and asks the SERVER to fetch it, which without this
# is textbook SSRF - "resolve" http://169.254.169.254/ or http://localhost:8000/
# and the response comes back from inside the network. Only shorteners that
# Google or OpenStreetMap themselves issue are worth following, and none of
# those resolve to anything internal.
_SHORTENER_HOSTS = frozenset({
    "maps.app.goo.gl",
    "goo.gl",
    "maps.google.com",
    "www.google.com",
    "google.com",
    "osm.org",
    "openstreetmap.org",
    "www.openstreetmap.org",
})

# Where a redirect is allowed to LAND. Following a chain means the allowlist
# above only vets the first hop, so every subsequent URL is checked too -
# otherwise a shortener whose destination has been changed would walk straight
# through. Any google.<tld> host is accepted (google.com.kh, google.co.uk, ...);
# everything else must match exactly.
_ALLOWED_LANDING_RE = re.compile(
    r"^(?:[a-z0-9-]+\.)*(?:google\.[a-z.]{2,7}|goo\.gl|openstreetmap\.org|osm\.org)$"
)

_MAX_REDIRECTS = 5
_TIMEOUT_SECONDS = 6

# A coordinate as it appears in every shape below. Deliberately loose - the
# bounds check in _pair() is what decides whether the numbers are a real place.
_NUM = r"-?\d+(?:\.\d+)?"

# Ordered by trustworthiness, not by frequency: the first pattern that matches
# wins, and the first two are the ones naming the PIN rather than the viewport.
_COORD_PATTERNS = (
    # Place pages: /data=!3m1!4b1!4m5!3m4!1s0x..!8m2!3d11.5564!4d104.9282
    re.compile(r"!3d(" + _NUM + r")!4d(" + _NUM + r")"),
    # Search/directions params, percent-encoded comma and plain:
    #   ?q=11.5564,104.9282   ?query=..   ?ll=..   ?daddr=..
    #   ?q=loc:11.5564,104.9282  (what Google's own "copy coordinates" emits)
    re.compile(
        r"[?&](?:q|query|ll|daddr|sll|center)=(?:loc:)?(" + _NUM + r")%2C(" + _NUM + r")",
        re.IGNORECASE,
    ),
    re.compile(
        r"[?&](?:q|query|ll|daddr|sll|center)=(?:loc:)?(" + _NUM + r")\s*,\s*(" + _NUM + r")",
        re.IGNORECASE,
    ),
    # Desktop URL viewport: /@11.5564,104.9282,17z
    re.compile(r"@(" + _NUM + r"),(" + _NUM + r")"),
    # OpenStreetMap: #map=17/11.5564/104.9282
    re.compile(r"#map=\d+(?:\.\d+)?/(" + _NUM + r")/(" + _NUM + r")"),
)

# Someone who pressed "copy coordinates" in Google Maps has a bare pair on their
# clipboard, not a URL at all. Accepting it costs one pattern and saves them a
# trip back into the app.
_BARE_PAIR_RE = re.compile(r"^\s*(" + _NUM + r")\s*,\s*(" + _NUM + r")\s*$")


def _pair(lat_text, lng_text):
    """A (lat, lng) float pair, or None if those two strings are not one.

    The bounds are what separate a real location from a partial match: the `@`
    pattern in particular will happily match a zoom level or part of an id, and
    a longitude of 4000 is how that shows up.
    """
    try:
        lat = float(lat_text)
        lng = float(lng_text)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None
    # 0,0 is in the Gulf of Guinea. Nobody's clinic is there, and it is what a
    # half-initialized map widget emits, so it is read as "no pin".
    if lat == 0.0 and lng == 0.0:
        return None
    return lat, lng


def parse_coordinates(url):
    """(lat, lng) read out of a map URL (or a bare "lat,lng" paste), else None.

    Never raises and never fetches anything - a short link, an unrecognized
    shape and an empty string all simply return None.
    """
    text = (url or "").strip()
    if not text:
        return None

    bare = _BARE_PAIR_RE.match(text)
    if bare:
        return _pair(bare.group(1), bare.group(2))

    # Raw and percent-decoded: the `q=` parameter arrives either way depending
    # on which app did the sharing, and `!3d` blobs survive both.
    for candidate in (text, unquote(text)):
        for pattern in _COORD_PATTERNS:
            match = pattern.search(candidate)
            if match:
                found = _pair(match.group(1), match.group(2))
                if found:
                    return found
    return None


def _host_of(url):
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def is_short_link(url):
    """True if this link's coordinates only exist after following a redirect."""
    host = _host_of(url)
    if host in ("maps.app.goo.gl", "goo.gl"):
        return True
    # google.com/maps/... with nothing parseable in it is usually a share link
    # that still redirects to a place page carrying the real pin.
    if host in ("maps.google.com", "www.google.com", "google.com"):
        return urlparse(url).path.startswith("/maps") and parse_coordinates(url) is None
    return False


def is_fetchable(url):
    """Whether the server is willing to make a request to this URL at all."""
    try:
        parts = urlparse(url)
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not host:
        return False
    # An explicit port is a strong signal this is not the public Google. The
    # allowlist would catch it anyway; refusing outright keeps the reachable
    # surface to :80/:443.
    if port not in (None, 80, 443):
        return False
    return host in _SHORTENER_HOSTS


def expand_short_link(url):
    """Follow a shortened map link, returning the URL it lands on, or None.

    Redirects are followed by hand rather than with allow_redirects=True so
    every hop can be vetted - a shortener is by definition a URL whose
    destination somebody else controls.
    """
    if not is_fetchable(url):
        return None

    session = requests.Session()
    current = url
    try:
        for _ in range(_MAX_REDIRECTS):
            # HEAD first: the coordinates live in the Location header, so there
            # is no reason to download a map page's worth of HTML. Some Google
            # hosts answer HEAD with 405, hence the streamed GET fallback whose
            # body is closed without being read.
            response = session.head(current, allow_redirects=False, timeout=_TIMEOUT_SECONDS)
            if response.status_code == 405:
                response = session.get(
                    current, allow_redirects=False, timeout=_TIMEOUT_SECONDS, stream=True
                )
                response.close()
            if response.status_code not in (301, 302, 303, 307, 308):
                return None
            location = response.headers.get("Location")
            if not location:
                return None
            current = urljoin(current, location)
            if not _ALLOWED_LANDING_RE.match(_host_of(current)):
                # Landed outside the allowlist. Stop rather than follow it or
                # hand it back - see the SSRF note on _SHORTENER_HOSTS.
                return None
            if parse_coordinates(current):
                return current
    except requests.RequestException:
        # Network trouble resolving a convenience feature is not worth an error
        # page - the caller falls back to storing the link unparsed.
        return None
    finally:
        session.close()
    return None


def resolve(url):
    """The whole pasted-link story in one call.

    Returns {"latitude", "longitude", "url"}. Both coordinate keys are None
    when nothing could be read, which is a normal outcome rather than a
    failure: `url` still carries a link a human can open.

    The SHORT link is deliberately what stays in `url` even when expansion
    succeeded - it is the one the customer recognises, and the expansion
    existed only to read a pin out of it.
    """
    text = (url or "").strip()
    if not text:
        return {"latitude": None, "longitude": None, "url": None}

    # A bare "11.55,104.92" paste is coordinates, not a link, so nothing should
    # be stored as map_link for it.
    stored_url = None if _BARE_PAIR_RE.match(text) else text

    found = parse_coordinates(text)
    if not found and is_short_link(text):
        expanded = expand_short_link(text)
        if expanded:
            found = parse_coordinates(expanded)

    if not found:
        return {"latitude": None, "longitude": None, "url": stored_url}
    return {"latitude": found[0], "longitude": found[1], "url": stored_url}


def location_link(latitude, longitude, map_link=None):
    """The best "open this location" URL for a stored pin, or None.

    Prefers whatever the customer pasted - that link often names a building or
    a business, which is more use to a driver than a bare coordinate pair - and
    falls back to a Google Maps URL synthesized from the coordinates. Returning
    None when there is neither is deliberate: the caller renders no link rather
    than a dead one.

    The pasted link is re-checked with resolve_link_url() on the way out even
    though schemas.py already refuses a non-http(s) one on the way in, because
    rows written before that validator existed are still in the table and this
    value goes straight into an href.
    """
    from formatting import resolve_link_url

    safe = resolve_link_url(map_link)
    if safe:
        return safe
    return google_maps_url(latitude, longitude)


def google_maps_url(latitude, longitude):
    """The canonical "open this pin in Google Maps" link for a stored location.

    Built rather than stored, so a location captured by dropping a pin still
    gives staff something to tap. `?q=` (rather than the `/@` form) is what
    opens the place sheet with a marker on it, in both the app and the site.
    """
    if latitude is None or longitude is None:
        return None
    try:
        return "https://www.google.com/maps?q={:.6f},{:.6f}".format(
            float(latitude), float(longitude)
        )
    except (TypeError, ValueError):
        return None
