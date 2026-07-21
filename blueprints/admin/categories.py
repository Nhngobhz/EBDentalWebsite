from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp
from store_api import StoreAPIError, get_api_client


def _product_counts_by_category(products):
    counts = {}
    for p in products:
        category = p.get("category")
        if category:
            counts[category["id"]] = counts.get(category["id"], 0) + 1
    return counts


def _file_from_request():
    file = request.files.get("file")
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


@admin_bp.route("/categories")
def categories():
    client = get_api_client()
    category_list = client.get("/categories/", params={"limit": 500})
    raw_products = client.get("/products/", params={"limit": 500})
    counts = _product_counts_by_category(raw_products)
    for c in category_list:
        c["product_count"] = counts.get(c["id"], 0)
    return render_template("admin/categories.html", categories=category_list)


@admin_bp.route("/categories/new", methods=["POST"])
@permission_required("product_management")
def categories_new():
    name = request.form.get("category_name", "").strip()
    if not name:
        flash("Category name is required.", "error")
        return redirect(url_for("admin.categories"))

    client = get_api_client()
    try:
        client.post_form("/categories/", data={"category_name": name}, files=_file_from_request())
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.categories"))

    flash(f"Category '{name}' created.", "success")
    return redirect(url_for("admin.categories"))


@admin_bp.route("/categories/<int:category_id>/edit", methods=["POST"])
@permission_required("product_management")
def categories_edit(category_id):
    name = request.form.get("category_name", "").strip()
    client = get_api_client()
    try:
        if name:
            client.put_json(f"/categories/{category_id}", {"category_name": name})
        files = _file_from_request()
        if files:
            client.post_form(f"/categories/{category_id}/image", files=files)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.categories"))

    flash("Category updated.", "success")
    return redirect(url_for("admin.categories"))


@admin_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@permission_required("product_management")
def categories_delete(category_id):
    client = get_api_client()
    try:
        client.delete(f"/categories/{category_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.categories"))

    flash("Category deleted.", "success")
    return redirect(url_for("admin.categories"))
