"""
EB Dental Supply - Flask storefront + admin, backed by store-api (see ../store-api).

Replaces preview_app.py (deleted - see its former docstring: "Delete this file once
templates + routes are merged with the real backend"). No local data/ folder anymore -
every page fetches live from store-api.
"""
import gzip
import os
import time
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.local import LocalProxy

load_dotenv()

import assets
import maps
import site_cache
import site_section
import site_settings
from auth import can_view_prices, is_staff, register_auth_context
from formatting import adapt_product, adapt_promotion, format_date, format_price, resolve_file_url, resolve_image_url, resolve_link_url
from store_api import (
    SessionExpired,
    StoreAPIError,
    StoreAPIUnavailable,
    get_api_client,
    session_token_expired,
    token_expires_at,
)

from blueprints.admin import admin_bp
from blueprints.auth_routes import auth_bp
from blueprints.catalog import catalog_bp, section_brands
from blueprints.main import HERO_SLIDES_CACHE_VAR, main_bp
from blueprints.materials import (
    CATEGORY_ICON_CHOICES,
    FALLBACK_BRAND_NAME,
    category_icon,
    materials_bp,
)
from blueprints.maps_routes import maps_bp
from blueprints.quote import quote_bp

def _wants_json():
    """Whether the caller is one of the fetch() calls in static/js/main.js rather than
    a browser loading a page - they need a JSON body back, not a redirect to HTML."""
    return (
        request.is_json
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


# Set APP_ENV=production in the deployment's .env. It's what switches on the
# HTTPS-only session cookie and switches off the Werkzeug debugger below - both of
# which would break/annoy local development if they keyed off nothing at all.
IS_PRODUCTION = os.environ.get("APP_ENV", "development").strip().lower() == "production"


# ---------------------------------------------------------------------------
# Response compression
# ---------------------------------------------------------------------------
# Nothing in front of this app was gzipping, so every visitor was pulling the
# stylesheets, main.js and the HTML at full size - about 300KB of our own assets
# on a cold page, against roughly 50KB compressed. If a reverse proxy (nginx,
# Cloudflare, ...) is added in front later it will set Content-Encoding itself and
# _compress_response leaves those responses alone, so there's no double work.
COMPRESSIBLE_MIMETYPES = {
    "text/html",
    "text/css",
    "text/plain",
    "text/xml",
    "application/javascript",
    "text/javascript",
    "application/json",
    "image/svg+xml",
}
# Below roughly a TCP segment, compressing costs a CPU round and saves nothing
# that isn't lost again to the gzip header.
COMPRESS_MIN_BYTES = 800
COMPRESS_LEVEL = 6

# How many brands the footer's brand column lists. Machinery has four in total, so
# this only ever bites on the materials side, where 173 of them would be a footer
# eleven screens tall.
FOOTER_BRAND_COUNT = 12

# Static files are immutable for a given ETag (they're fingerprinted with
# ?v=<mtime>), so their compressed bytes are worth keeping rather than
# regenerating per request. Bounded because it holds whole file bodies.
_gzip_cache = {}
_GZIP_CACHE_MAX_ENTRIES = 64


def _compress_response(response):
    if "gzip" not in request.headers.get("Accept-Encoding", "").lower():
        return response
    if response.mimetype not in COMPRESSIBLE_MIMETYPES:
        return response
    # Vary matters as soon as anything caches this: the same URL now has a
    # gzipped and an identity representation, and a shared cache handing the
    # wrong one to the wrong client produces garbage.
    response.headers.setdefault("Vary", "Accept-Encoding")
    # The error pages render the whole site shell, so they're worth compressing too.
    # The exclusions are the ones where it would be wrong rather than merely
    # pointless: a 206 is a byte range out of the middle of a file, and gzipping it
    # would hand back compressed bytes under a Content-Range describing the
    # uncompressed ones; 204/304 have no body at all.
    if response.status_code < 200 or response.status_code in (204, 206, 304):
        return response
    if "Content-Encoding" in response.headers:
        return response

    cache_key = response.headers.get("ETag")
    cached = _gzip_cache.get(cache_key) if cache_key else None
    if cached is None:
        # send_file hands back a file wrapper in passthrough mode; reading the body
        # out of it (which is what compressing requires) needs that switched off.
        response.direct_passthrough = False
        data = response.get_data()
        if len(data) < COMPRESS_MIN_BYTES:
            return response
        cached = gzip.compress(data, COMPRESS_LEVEL)
        if cache_key and len(cached) <= 1_000_000:
            if len(_gzip_cache) >= _GZIP_CACHE_MAX_ENTRIES:
                _gzip_cache.clear()
            _gzip_cache[cache_key] = cached

    response.set_data(cached)
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = len(cached)
    return response


# ---------------------------------------------------------------------------
# Sitewide catalog cache
# ---------------------------------------------------------------------------
# Lives in site_cache.py so the admin Settings blueprint can invalidate the settings
# entry on save without importing this module back (see that file's docstring).
# The settings entry specifically is read through site_settings.py, which both this
# module and the blueprints import.
_cached_sitewide = site_cache.cached



def create_app():
    app = Flask(__name__)
    app.config["STORE_API_BASE_URL"] = os.environ.get("STORE_API_BASE_URL", "http://localhost:8000")
    # Google Sign-In. Read in templates as {{ config.GOOGLE_CLIENT_ID }} (Flask exposes
    # `config` to Jinja) - empty means the "Continue with Google" block renders nothing,
    # so an unconfigured deployment simply doesn't advertise it. store-api needs the
    # same value set on its side to verify the tokens the button produces; this side
    # only renders the button.
    app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID", "")
    app.secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not app.secret_key:
        raise RuntimeError("FLASK_SECRET_KEY is not set - copy .env.example to .env and fill it in.")
    # Generous enough for a product image or a manual PDF; store-api enforces the real
    # 5MB/20MB limits itself and returns a proper error - this just stops Flask from
    # rejecting the upload before store-api gets a chance to.
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

    # Session cookie hardening. This cookie is the whole authentication story for
    # this app - it carries the store-api bearer token server-side - so it gets the
    # full set of flags rather than Flask's permissive defaults:
    #   HTTPONLY  - script can't read it, so an XSS anywhere can't exfiltrate a session
    #   SAMESITE  - not sent on cross-site POSTs, which is what stands in for CSRF
    #               tokens on the form-post admin routes
    #   SECURE    - HTTPS only; off unless APP_ENV=production, since a secure-only
    #               cookie is never sent over the local http://127.0.0.1 dev server
    #               and would silently break every login there
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION
    # The outer bound on any session, not the real expiry. store-api issues tokens with
    # different lifetimes per account type (24h for staff, 14 days for customers - see
    # token_lifetime in store-api/app/core/security.py), and the true cutoff is the
    # `exp` baked into each token, which expired_session_gate below enforces per
    # session. This just guarantees no cookie can outlive the longest token there is,
    # so it's set to that longest lifetime rather than the shortest - capping it at 24h
    # would log every customer out a day into their fortnight.
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=14)
    # ...and that 24h must not slide forward on every request, which is Flask's
    # default. The token inside the cookie expires a fixed 24h after login and there
    # is no refresh flow, so a sliding cookie would just recreate the mismatch this
    # pairing exists to prevent: a cookie still claiming "signed in as admin" wrapped
    # around a token store-api has already stopped accepting. With this off, Flask
    # only re-stamps the cookie when the session actually changes (login/logout), so
    # it dies at the same instant the token does.
    app.config["SESSION_REFRESH_EACH_REQUEST"] = False

    # Static files are fingerprinted below (?v=<mtime> on every url_for('static')),
    # so browsers can safely cache them for a long time - an edited file gets a new
    # mtime, hence a new URL, and is re-fetched immediately.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 60 * 60 * 24 * 30

    _static_version_cache = {}

    @app.url_defaults
    def add_static_version(endpoint, values):
        if endpoint != "static" or "filename" not in values:
            return
        filename = values["filename"]
        # In debug, stat every time so an edited file's URL changes immediately;
        # in production, memoize the stat so it costs nothing per request.
        version = None if app.debug else _static_version_cache.get(filename)
        if version is None:
            try:
                version = int(os.stat(os.path.join(app.static_folder, filename)).st_mtime)
            except OSError:
                return
            _static_version_cache[filename] = version
        values["v"] = version

    # Concatenates static/css + static/js into static/dist/ bundles and exposes
    # css_bundle()/js_bundle() to the templates. Runs before the first request so
    # the ?v=<mtime> fingerprinting above sees the freshly built files.
    assets.register(app)

    app.jinja_env.globals["img"] = resolve_image_url
    app.jinja_env.globals["file_url"] = resolve_file_url
    app.jinja_env.globals["link_url"] = resolve_link_url
    app.jinja_env.globals["location_link"] = maps.location_link
    app.jinja_env.globals["price"] = format_price
    app.jinja_env.globals["format_date"] = format_date
    # Which glyph stands for a materials category (see blueprints/materials.py).
    # Global rather than passed per route, because four different pages draw
    # category tiles and they must not disagree about what a bur looks like.
    app.jinja_env.globals["category_icon"] = category_icon
    # The same glyphs, as the admin Categories picker's palette - so what an admin can
    # choose and what the storefront draws are one list.
    app.jinja_env.globals["category_icon_choices"] = CATEGORY_ICON_CHOICES
    register_auth_context(app)

    def _lazy_catalog_global(cache_key, fetch, shared_scope=None, fallback=list):
        """A store-api fetch that only actually fires if the rendered template touches
        the variable, and at most once per request (memoized on `g`). Routes that pass
        their own value (e.g. catalog passes `products`) shadow the proxy entirely, so
        those pages never pay for the sitewide fetch on top of their own.

        `shared_scope`, when given, is a callable naming a cache scope, and the result
        is additionally reused *across* requests within that scope for
        site_cache.TTL seconds. Only safe for data that genuinely doesn't vary
        inside the scope - which is why the scope exists at all: /brands/ is public and
        identical for everyone, but store-api masks promotion prices per viewer (see
        _serialize_promotion), so promotions are scoped on price visibility and a
        signed-out visitor can never be served a signed-in visitor's prices.

        `fallback` is what the proxy yields when store-api can't be reached. It defaults
        to an empty list because every original caller here fetches a list; the settings
        global overrides it, since a template doing `site_settings.store_name` against a
        list would turn a store-api blip into a 500 on every page."""

        def resolve():
            if cache_key not in g:
                try:
                    if shared_scope is None:
                        value = fetch(get_api_client())
                    else:
                        value = _cached_sitewide(
                            (cache_key, shared_scope()), lambda: fetch(get_api_client())
                        )
                except StoreAPIError:
                    value = fallback()
                setattr(g, cache_key, value)
            return getattr(g, cache_key)

        return LocalProxy(resolve)

    # See site_settings.py - a plain function, not a LocalProxy, because base.html
    # has to `|tojson` it and because blueprints/quote.py imports the same accessor.
    app.jinja_env.globals["site_settings"] = site_settings.get

    # Runs before every other before_request in this app - in particular before
    # maintenance_gate, which asks is_staff() and would otherwise trust a session whose
    # token is already dead.
    #
    # store-api tokens last 24h and can't be refreshed, but nothing used to notice them
    # lapsing: the session cookie still said "signed in as admin", so the header, the
    # dashboard and every admin screen rendered exactly as before, and the failure only
    # showed up as a "Could not validate credentials" banner the first time someone
    # tried to save something. Logging out and back in was the only cure. Retiring the
    # session the moment its token is known to be past expiry means the UI and store-api
    # agree on who you are: you get the login page, not an admin screen that can't write.
    @app.before_request
    def expired_session_gate():
        if request.endpoint == "static" or not session_token_expired():
            return None
        # Anywhere the answer depends on being signed in - the admin area, any write,
        # any fetch() call - hand over to the SessionExpired handler below, which ends
        # the session and asks for a fresh sign-in. Letting these fall through as
        # anonymous requests instead would answer an admin with the deliberately
        # indistinguishable 404 from staff_required, which reads as "that page is gone"
        # rather than "your session ran out".
        if request.blueprint == "admin" or request.method != "GET" or _wants_json():
            raise SessionExpired()
        # A plain GET of a storefront page is better handled in place: retire the dead
        # session, say so, and let the page render for a guest - a customer who was
        # only browsing shouldn't be thrown at a login screen they never asked for.
        session.clear()
        flash("Your session has expired. Please sign in again.", "error")
        return None

    # A customer's session is 14 days of *inactivity*, not 14 days flat: while they
    # keep using the site the token underneath is quietly re-minted, so only a real
    # fortnight away lets it lapse. Staff are excluded on purpose - their 24h is meant
    # to end the session whether they were active or not, and store-api refuses to
    # extend a staff token anyway (POST /auth/refresh).
    #
    # Once a day is plenty: it costs one extra store-api call per customer per day, and
    # any interval well under the token's own lifetime keeps an active session alive
    # just as effectively as refreshing on every request would.
    CUSTOMER_TOKEN_REFRESH_AFTER = 60 * 60 * 24

    @app.before_request
    def slide_customer_session():
        if request.endpoint == "static" or session.get("account_type") != "customer":
            return None
        if not session.get("token"):
            return None
        # Sessions predating this feature have no timestamp; `or 0` makes their next
        # request refresh immediately, which is also what upgrades the 24h token they
        # were issued under the old rules to a full 14-day one.
        if time.time() - (session.get("token_refreshed_at") or 0) < CUSTOMER_TOKEN_REFRESH_AFTER:
            return None
        client = get_api_client()
        try:
            result = client.refresh_token()
        except StoreAPIError:
            # store-api unreachable, or this customer was deactivated since login.
            # Nothing to do here either way: the token in hand is still valid until its
            # own exp, and expired_session_gate retires it then. Deliberately does NOT
            # catch SessionExpired - a token store-api has already stopped honouring
            # should end the session now, not be retried again tomorrow.
            return None
        session["token"] = result["access_token"]
        session["token_expires_at"] = token_expires_at(result["access_token"])
        session["token_refreshed_at"] = time.time()
        # get_api_client() memoizes one client per request on `g`, and it captured the
        # old token a few lines ago. That token is still valid, so nothing would break -
        # but the rest of this request may as well use the fresh one.
        client.token = result["access_token"]
        return None

    # Blueprints that must keep working while the storefront is closed: /admin/* is how
    # maintenance mode gets switched off again, and the auth blueprint is how a staff
    # member reaches it. Exempting `auth` wholesale also leaves /profile reachable,
    # which is deliberate - a customer checking an order they already placed isn't
    # shopping, and closing that would strand people mid-purchase. Everything else -
    # the home page, catalog, product pages and the quote/cart flow - is closed to
    # anyone who isn't signed-in staff.
    MAINTENANCE_OPEN_BLUEPRINTS = {"admin", "auth"}

    @app.before_request
    def maintenance_gate():
        # Static files are served straight through: the maintenance page itself needs
        # the stylesheets, and checking a setting per asset request would be silly.
        if request.endpoint is None or request.endpoint == "static":
            return None
        if request.blueprint in MAINTENANCE_OPEN_BLUEPRINTS or is_staff():
            return None
        values = site_settings.get()
        if not values.get("maintenance_mode"):
            return None
        # 503 (not 200) so crawlers and uptime monitors read this as "temporarily
        # unavailable, come back" rather than indexing it as the site's real content.
        return render_template(
            "maintenance.html", message=values.get("maintenance_message", "")
        ), 503

    # Which half of the site the visitor is in. The landing page splits into
    # Machinery (EB Dental Supply) and Materials (HOME 49); from then on the
    # header mark, the nav, the footer and the bottom bar all mirror that choice,
    # rather than dumping everyone back on the landing screen.
    #
    # Most pages say which half they belong to just by being themselves - every
    # route in blueprints/materials.py is materials, /machinery and /products are
    # machinery. The pages that DON'T are the shared ones: About, Contact,
    # Promotions, sign-in, the profile. Those are the whole reason this is
    # remembered in the session rather than derived per request: without it,
    # clicking "About" from the materials store swaps the logo to the machinery
    # mark, the nav to the machinery nav, and leaves the shopper standing in the
    # other shop with no obvious way back.
    SECTION_KEY = "site_section"

    MACHINERY_ENDPOINTS = {
        "main.home",
        "catalog.products_catalog",
        "catalog.product_detail",
        "catalog.special_product",
        # Promotions and Sets are bundles of machinery products, which is why the
        # materials nav doesn't offer them. Reaching one anyway - a bookmark, a
        # shared link - is genuinely walking into the other shop, so the shell
        # says so rather than dressing machinery deals in the HOME 49 mark.
        "catalog.promotions_page",
        "catalog.promotion_detail",
        "catalog.set_detail",
    }

    def _request_section():
        """The section this request's endpoint belongs to, or None for a page that
        belongs to both (About, Contact, sign-in) or to neither (admin)."""
        # A view that knows better than the routing table wins - see
        # site_section.py. /promotions/12 is one endpoint serving a machinery bundle
        # or a materials one depending on the row, and only the view has the row.
        chosen = site_section.current_override()
        if chosen:
            return chosen
        if request.blueprint == "materials":
            return "materials"
        if request.endpoint in MACHINERY_ENDPOINTS:
            return "machinery"
        return None

    @app.before_request
    def remember_site_section():
        section = _request_section()
        # The landing screen is the chooser itself, so arriving there forgets the
        # last choice - otherwise picking Materials once would tint the machinery
        # side of the site for the rest of the session.
        if request.endpoint == "main.landing":
            # `in` first: werkzeug's session dict marks itself modified on any
            # mutating call, present key or not, and a modified session is a
            # Set-Cookie on every single view of the landing page.
            if SECTION_KEY in session:
                session.pop(SECTION_KEY)
        # Written only when it changes: an unconditional assignment marks the
        # session modified on every request, which means a Set-Cookie on every
        # response for a value that is almost always the same one.
        elif section and session.get(SECTION_KEY) != section:
            session[SECTION_KEY] = section

    @app.after_request
    def persist_overridden_section(response):
        """Carry a view's section override into the session, so the shop a shopper
        was put into by one page is still the shop they are in on the next.

        Has to be here rather than in remember_site_section: that runs before the
        view, and the override is set inside it. Same "only when it changes" rule -
        an unconditional write is a Set-Cookie on every response."""
        chosen = site_section.current_override()
        if chosen and session.get(SECTION_KEY) != chosen:
            session[SECTION_KEY] = chosen
        return response

    def site_section_name():
        """Which half of the site is being rendered - the same answer the templates
        get from site_section(), as a plain callable the sitewide globals can use
        as a cache scope."""
        return _request_section() or session.get(SECTION_KEY) or "machinery"

    @app.context_processor
    def inject_site_section():
        return {"site_section": site_section_name}

    @app.context_processor
    def inject_catalog_globals():
        """Sitewide data every page's shell (footer, promo banner, admin sidebar
        counts) needs, regardless of which route is being rendered - same role the
        mock's inject_brands/inject_promotions/inject_active_promotions played.
        Each value is lazy: a public page that only renders the footer + promo banner
        fetches just brands + active promotions, instead of all five lists."""
        return {
            "brands": _lazy_catalog_global(
                "_cp_brands",
                lambda c: c.get("/brands/", params={"limit": 200}),
                # GET /brands/ takes no auth and returns the same rows to everyone,
                # so one cached copy serves the whole site.
                shared_scope=lambda: "all",
            ),
            "products": _lazy_catalog_global(
                "_cp_products",
                lambda c: [adapt_product(p) for p in c.get("/products/", params={"limit": 500})],
            ),
            "promotions": _lazy_catalog_global(
                "_cp_promotions", lambda c: c.get("/promotions/", params={"limit": 200})
            ),
            "sets": _lazy_catalog_global(
                "_cp_sets", lambda c: c.get("/sets/", params={"limit": 200})
            ),
            "hero_slides": _lazy_catalog_global(
                HERO_SLIDES_CACHE_VAR,
                lambda c: c.get(
                    "/hero-slides/",
                    params={
                        "active_only": True,
                        "limit": 50,
                        # Each shop has its own carousel now (hero_slides.section).
                        # Asked for by section rather than fetched whole and filtered
                        # in the template, so a machinery page never carries the
                        # materials slides' markup - or their artwork URLs.
                        "section": site_section_name(),
                    },
                ),
                # Public, unpriced and identical for every visitor to one section, so
                # one cached copy per section serves the whole site -
                # blueprints/admin/hero_slides.py clears both on every save.
                shared_scope=site_section_name,
            ),
            # The footer's brand column, for whichever half of the site is being
            # rendered. NOT the `brands` global above, which is GET /brands/ and
            # spans both sections - see section_brands() for what that produced.
            "footer_brands": _lazy_catalog_global(
                "_cp_footer_brands",
                # SAP's "Unbranded" catch-all is dropped: it is the biggest bucket in
                # the materials catalogue, so a list ordered by size opened every
                # materials footer with it, and a footer's brand column is a shop
                # window rather than an index. See materials.FALLBACK_BRAND_NAME.
                lambda c: [
                    b
                    for b in section_brands(site_section_name())
                    if b["brand_name"] != FALLBACK_BRAND_NAME
                ][:FOOTER_BRAND_COUNT],
                shared_scope=site_section_name,
            ),
            "active_promotions": _lazy_catalog_global(
                "_cp_active_promotions",
                lambda c: [
                    adapt_promotion(p)
                    for p in c.get(
                        "/promotions/",
                        params={
                            "active_only": True,
                            "limit": 50,
                            # This global feeds the promo banner and the hero
                            # carousel's automatic first slide, both of which belong
                            # to whichever shop is being rendered. Before promotions
                            # had a section the materials pages simply hid the banner;
                            # now they show their own deals instead.
                            "section": site_section_name(),
                        },
                    )
                ],
                # Four copies at most: two sections x priced/masked. Which one a
                # request gets is decided by the same rule store-api applies
                # (can_view_prices mirrors its get_price_visibility).
                shared_scope=lambda: (
                    f"{site_section_name()}:{'priced' if can_view_prices() else 'masked'}"
                ),
            ),
        }

    app.register_blueprint(main_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(quote_bp)
    app.register_blueprint(maps_bp)
    app.register_blueprint(admin_bp)

    @app.after_request
    def add_security_headers(response):
        """Baseline response headers every page gets.

        Deliberately the three that can't break a working page: no MIME sniffing
        (an uploaded file can't be re-interpreted as script), no Referer leaking
        to third parties (admin URLs carry record ids), and no embedding in a
        frame (clickjacking the admin's action buttons). A Content-Security-Policy
        is NOT set here - the templates use inline <script> blocks throughout, so
        a real policy needs those extracted or nonced first, and a policy loose
        enough to allow 'unsafe-inline' would only be decorative."""
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response

    @app.after_request
    def compress_response(response):
        return _compress_response(response)

    @app.errorhandler(403)
    def handle_forbidden(_e):
        flash("You don't have permission to do that.", "error")
        return redirect(url_for("admin.dashboard") if is_staff() else url_for("main.home")), 403

    @app.errorhandler(404)
    def handle_not_found(_e):
        """Any URL that doesn't match a route - plus the explicit abort(404)s in
        catalog.py (missing product) and auth.py's admin gate."""
        return render_template("not_found.html"), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(_e):
        """A wrong-verb request (e.g. GET on a POST-only endpoint) is answered with the
        same page as an unknown URL. Routing raises this before any blueprint's
        before_request runs, so without it a stranger probing GET /admin/products/new
        would get a 405 - proof the URL exists - while /admin/products correctly 404s."""
        return render_template("not_found.html"), 404

    @app.errorhandler(SessionExpired)
    def handle_session_expired(_e):
        """The one place a dead session is retired, reached two ways.

        expired_session_gate raises this the moment the token's own `exp` has passed;
        store_api.py raises it when store-api answers 401 to a call we signed with that
        token - which covers everything a clock can't predict: an account disabled or
        deleted while its holder is still browsing, a token that carried no readable
        `exp`, a request already in flight when the expiry passed, a SECRET_KEY rotated
        under a running session. Same outcome either way - end the session and ask for
        a fresh sign-in, instead of leaving the browser in an admin UI that renders
        perfectly and flashes a raw "Could not validate credentials" at every save."""
        session.clear()
        message = "Your session has expired. Please sign in again."
        # The fetch() callers in static/js/main.js (quote submit, the profile order
        # panels) all do `await response.json()` on whatever comes back. A redirect is
        # followed transparently by fetch, so they'd be parsing the login page's HTML
        # and reporting a generic "please try again" - answer them in the shape they
        # asked for instead, which their existing `data.detail` handling already shows.
        if _wants_json():
            return jsonify({"detail": message, "session_expired": True, "login_url": url_for("auth.login")}), 401
        flash(message, "error")
        # Only a GET is worth coming back to; bouncing to a POST-only URL would just
        # 405, and silently re-submitting the form would be worse still.
        next_url = request.full_path.rstrip("?") if request.method == "GET" else None
        return redirect(url_for("auth.login", next=next_url) if next_url else url_for("auth.login"))

    @app.errorhandler(StoreAPIUnavailable)
    def handle_store_api_unavailable(e):
        return render_template("service_unavailable.html", detail=e.detail), 503

    return app


app = create_app()


if __name__ == "__main__":
    # debug=True mounts the Werkzeug interactive debugger, which is a remote shell
    # to anyone who reaches a traceback - fine locally, never in production. Tied to
    # the same APP_ENV switch so a production host started with `python app.py`
    # doesn't quietly ship one.
    app.run(debug=not IS_PRODUCTION)
