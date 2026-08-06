"""
EB Dental Supply - Flask storefront + admin, backed by store-api (see ../store-api).

Replaces preview_app.py (deleted - see its former docstring: "Delete this file once
templates + routes are merged with the real backend"). No local data/ folder anymore -
every page fetches live from store-api.
"""
import os

from dotenv import load_dotenv
from flask import Flask, flash, g, redirect, render_template, session, url_for
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



def create_app():
    app = Flask(__name__)
    app.config["STORE_API_BASE_URL"] = os.environ.get("STORE_API_BASE_URL", "http://localhost:8000")
    app.secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not app.secret_key:
        raise RuntimeError("FLASK_SECRET_KEY is not set - copy .env.example to .env and fill it in.")
    # Generous enough for a product image or a manual PDF; store-api enforces the real
    # 5MB/20MB limits itself and returns a proper error - this just stops Flask from
    # rejecting the upload before store-api gets a chance to.
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

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
    app.run(debug=True)
