from flask import Blueprint, render_template

from special_products import SPECIAL_PRODUCTS
from store_api import get_api_client

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def landing():
    return render_template("main/landing.html")


@main_bp.route("/machinery")
def home():
    # brands/active_promotions are also available via the sitewide context
    # processor, but passed explicitly too (matches the original mock's own pattern).
    client = get_api_client()
    brands = client.get("/brands/", params={"limit": 200})
    special_products = [
        {"slug": slug, **meta} for slug, meta in SPECIAL_PRODUCTS.items()
    ]
    return render_template("main/home.html", brands=brands, special_products=special_products)


@main_bp.route("/materials")
def materials():
    return render_template("main/materials_coming_soon.html")


@main_bp.route("/about")
def about():
    return render_template("main/about.html")


@main_bp.route("/contact")
def contact():
    return render_template("contact.html")


@main_bp.route("/donut")
def donut():
    """Easter egg. Unlinked from every menu - the only way in is the hidden link on
    the 404 page (`.notfound-secret` in not_found.html), so the reward for getting
    lost is a spinning ASCII torus. Renders standalone, outside base.html."""
    return render_template("donut.html")