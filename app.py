"""
EB Dental Supply - Flask storefront + admin, backed by store-api (see ../store-api).

Replaces preview_app.py (deleted - see its former docstring: "Delete this file once
templates + routes are merged with the real backend"). No local data/ folder anymore -
every page fetches live from store-api.
"""
import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.local import LocalProxy

load_dotenv()

from auth import is_staff, register_auth_context
from formatting import adapt_product, adapt_promotion, format_date, format_price, resolve_file_url, resolve_image_url
from store_api import StoreAPIError, StoreAPIUnavailable, get_api_client

from blueprints.admin import admin_bp
from blueprints.auth_routes import auth_bp
from blueprints.catalog import catalog_bp
from blueprints.main import main_bp
from blueprints.quote import quote_bp

# Set APP_ENV=production in the deployment's .env. It's what switches on the
# HTTPS-only session cookie and switches off the Werkzeug debugger below - both of
# which would break/annoy local development if they keyed off nothing at all.
IS_PRODUCTION = os.environ.get("APP_ENV", "development").strip().lower() == "production"



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
    # store-api's own tokens expire after 24h (ACCESS_TOKEN_EXPIRE_MINUTES); an
    # abandoned browser session shouldn't outlive the token it holds.
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)

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

    app.jinja_env.globals["img"] = resolve_image_url
    app.jinja_env.globals["file_url"] = resolve_file_url
    app.jinja_env.globals["price"] = format_price
    app.jinja_env.globals["format_date"] = format_date

    register_auth_context(app)

    def _lazy_catalog_global(cache_key, fetch):
        """A store-api fetch that only actually fires if the rendered template touches
        the variable, and at most once per request (memoized on `g`). Routes that pass
        their own value (e.g. catalog passes `products`) shadow the proxy entirely, so
        those pages never pay for the sitewide fetch on top of their own."""

        def resolve():
            if cache_key not in g:
                try:
                    setattr(g, cache_key, fetch(get_api_client()))
                except StoreAPIError:
                    setattr(g, cache_key, [])
            return getattr(g, cache_key)

        return LocalProxy(resolve)

    # Which half of the site the visitor is in. The landing page splits into
    # Machinery and Materials; from then on the header logo mirrors that choice -
    # it shows that side's mark and links back to that side's home page, rather
    # than dumping everyone back on the landing screen.
    MATERIALS_ENDPOINTS = {"main.materials"}

    @app.context_processor
    def inject_site_section():
        def site_section():
            return "materials" if request.endpoint in MATERIALS_ENDPOINTS else "machinery"

        return {"site_section": site_section}

    @app.context_processor
    def inject_catalog_globals():
        """Sitewide data every page's shell (footer, promo banner, admin sidebar
        counts) needs, regardless of which route is being rendered - same role the
        mock's inject_brands/inject_promotions/inject_active_promotions played.
        Each value is lazy: a public page that only renders the footer + promo banner
        fetches just brands + active promotions, instead of all five lists."""
        return {
            "brands": _lazy_catalog_global(
                "_cp_brands", lambda c: c.get("/brands/", params={"limit": 200})
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
            "active_promotions": _lazy_catalog_global(
                "_cp_active_promotions",
                lambda c: [
                    adapt_promotion(p)
                    for p in c.get("/promotions/", params={"active_only": True, "limit": 50})
                ],
            ),
        }

    app.register_blueprint(main_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(quote_bp)
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
