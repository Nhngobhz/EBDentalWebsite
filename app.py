"""
EB Dental Supply - Flask storefront + admin, backed by store-api (see ../store-api).

Replaces preview_app.py (deleted - see its former docstring: "Delete this file once
templates + routes are merged with the real backend"). No local data/ folder anymore -
every page fetches live from store-api.
"""
import os

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, session, url_for

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

    app.jinja_env.globals["img"] = resolve_image_url
    app.jinja_env.globals["file_url"] = resolve_file_url
    app.jinja_env.globals["price"] = format_price
    app.jinja_env.globals["format_date"] = format_date

    register_auth_context(app)

    @app.context_processor
    def inject_catalog_globals():
        """Sitewide data every page's shell (footer, promo banner, admin sidebar
        counts) needs, regardless of which route is being rendered - same role the
        mock's inject_brands/inject_promotions/inject_active_promotions played."""
        client = get_api_client()
        try:
            brands = client.get("/brands/", params={"limit": 200})
        except StoreAPIError:
            brands = []
        try:
            products = [adapt_product(p) for p in client.get("/products/", params={"limit": 500})]
        except StoreAPIError:
            products = []
        try:
            promotions = client.get("/promotions/", params={"limit": 200})
        except StoreAPIError:
            promotions = []
        try:
            active_promotions_raw = client.get("/promotions/", params={"active_only": True, "limit": 50})
        except StoreAPIError:
            active_promotions_raw = []
        return {
            "brands": brands,
            "products": products,
            "promotions": promotions,
            "active_promotions": [adapt_promotion(p) for p in active_promotions_raw],
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

    @app.errorhandler(StoreAPIUnavailable)
    def handle_store_api_unavailable(e):
        return render_template("service_unavailable.html", detail=e.detail), 503

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
