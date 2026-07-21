from flask import Blueprint, render_template

from store_api import get_api_client

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    # brands/active_promotions are also available via the sitewide context
    # processor, but passed explicitly too (matches the original mock's own pattern).
    client = get_api_client()
    brands = client.get("/brands/", params={"limit": 200})
    return render_template("main/home.html", brands=brands)


@main_bp.route("/about")
def about():
    return render_template("main/about.html")


@main_bp.route("/contact")
def contact():
    return render_template("contact.html")
