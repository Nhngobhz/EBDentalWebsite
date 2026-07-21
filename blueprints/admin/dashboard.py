from flask import render_template

from blueprints.admin import admin_bp


@admin_bp.route("/dashboard")
def dashboard():
    # brands/products/active_promotions are already provided by the sitewide
    # inject_catalog_globals context processor (app.py) - nothing extra to fetch here.
    return render_template("admin/dashboard.html")
