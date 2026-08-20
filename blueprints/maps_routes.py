"""The one server-side piece the location picker needs.

Everything else about picking a location happens in the browser
(static/js/location-picker.js): dropping a pin gives coordinates directly, and
most pasted Google Maps URLs carry a readable lat/lng that the page parses
itself without asking anyone.

The exception is the short link the Google Maps mobile app shares
(https://maps.app.goo.gl/xxxx), which contains no coordinates at all until the
redirect is followed - and the browser cannot follow it, because Google serves
no CORS headers on it. So the page hands the link here and the server follows
it instead.

That is a request whose URL comes from a user, so it is deliberately narrow:
login required, POST only, and maps.py vets both the host it may fetch and
every host the redirect chain lands on before anything is requested.
"""
from flask import Blueprint, jsonify, request

import maps
from auth import login_required

maps_bp = Blueprint("maps", __name__, url_prefix="/maps")


@maps_bp.route("/resolve", methods=["POST"])
@login_required
def resolve_map_link():
    """Read a location out of a pasted map link.

    Always 200 with {latitude, longitude, url} - "we could not read a pin out
    of this" is an ordinary answer here, not an error. The page keeps the link
    either way and just does not move the marker, which is why an unparseable
    paste must not look like a failure the user has to fix.
    """
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url:
        return jsonify({"latitude": None, "longitude": None, "url": None})
    # 2000 is comfortably past the longest real Google Maps place URL and well
    # short of anything worth spending regex time on.
    if len(url) > 2000:
        return jsonify({"latitude": None, "longitude": None, "url": None})

    return jsonify(maps.resolve(url))
