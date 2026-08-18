"""
Access to the admin-editable site settings (store-api's `GET /settings/public`).

Registered as the `site_settings()` Jinja global in app.py, but it lives here rather
than as a closure inside create_app() because Python code needs it too - blueprints/
quote.py substitutes the standing payment/installation terms onto a customer's order,
and app.py's maintenance gate reads the switch. A Jinja global can't be imported.

Deliberately a plain function and not one of app.py's LocalProxy globals: a template has
to be able to `|tojson` this into window.EB_SETTINGS, and a LocalProxy isn't
serializable. A function is just as lazy - a page that never calls it never fetches.
"""
import site_cache
from flask import g

from store_api import StoreAPIError, get_api_client

# The site_cache entry these values live in. Shared with the admin Settings blueprint,
# which clears it on save so a change is live immediately instead of up to a TTL later.
CACHE_KEY = ("site_settings", "all")

# Last successfully fetched copy, used when a later fetch fails. Without it a store-api
# blip would blank the footer's phone number, and - worse - read maintenance mode as
# "off", reopening a storefront the admin had deliberately closed. Empty until the first
# success, which is the right starting point: with no answer from the source of truth,
# the site is not in maintenance.
_last_known: dict = {}


def get() -> dict:
    """Every public setting, as a real dict.

    Memoized on `g` for the request, and on top of that shared across requests by
    site_cache. `GET /settings/public` needs no auth and returns the same values to
    everyone, so one cached copy serves the whole site.
    """
    global _last_known
    if "_cp_site_settings" not in g:
        try:
            values = site_cache.cached(CACHE_KEY, lambda: get_api_client().get("/settings/public"))
            _last_known = values
        except StoreAPIError:
            values = _last_known
        g._cp_site_settings = values
    return g._cp_site_settings


def invalidate() -> None:
    """Drop the shared copy. Called by the admin Settings blueprint after a save."""
    site_cache.invalidate(CACHE_KEY)
