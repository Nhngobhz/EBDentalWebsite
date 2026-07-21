from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp
from store_api import StoreAPIError, get_api_client


def _product_counts_by_brand(products):
    counts = {}
    for p in products:
        brand = p.get("brand")
        if brand:
            counts[brand["id"]] = counts.get(brand["id"], 0) + 1
    return counts


def _file_from_request():
    file = request.files.get("file")
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


@admin_bp.route("/brands")
def brands():
    # products is already provided by the sitewide context processor, but we need
    # per-brand counts here specifically, so fetch it again to compute those.
    client = get_api_client()
    brand_list = client.get("/brands/", params={"limit": 200})
    raw_products = client.get("/products/", params={"limit": 500})
    counts = _product_counts_by_brand(raw_products)
    for b in brand_list:
        b["product_count"] = counts.get(b["id"], 0)
    return render_template("admin/brands.html", brands=brand_list)


@admin_bp.route("/brands/new", methods=["POST"])
@permission_required("product_management")
def brands_new():
    name = request.form.get("brand_name", "").strip()
    if not name:
        flash("Brand name is required.", "error")
        return redirect(url_for("admin.brands"))

    client = get_api_client()
    try:
        client.post_form("/brands/", data={"brand_name": name}, files=_file_from_request())
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.brands"))

    flash(f"Brand '{name}' created.", "success")
    return redirect(url_for("admin.brands"))


@admin_bp.route("/brands/<int:brand_id>/edit", methods=["POST"])
@permission_required("product_management")
def brands_edit(brand_id):
    name = request.form.get("brand_name", "").strip()
    client = get_api_client()
    try:
        if name:
            client.put_json(f"/brands/{brand_id}", {"brand_name": name})
        files = _file_from_request()
        if files:
            client.post_form(f"/brands/{brand_id}/image", files=files)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.brands"))

    flash("Brand updated.", "success")
    return redirect(url_for("admin.brands"))


@admin_bp.route("/brands/<int:brand_id>/delete", methods=["POST"])
@permission_required("product_management")
def brands_delete(brand_id):
    client = get_api_client()
    try:
        client.delete(f"/brands/{brand_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.brands"))

    flash("Brand deleted.", "success")
    return redirect(url_for("admin.brands"))
