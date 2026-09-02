from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp, product_facet_counts
from store_api import StoreAPIError, get_api_client


def _icon_from_form():
    """The Font Awesome class the admin picked, or "" for "no override".

    Always sent, never omitted, and that is the point: the field has to be
    ERASABLE. Omitting the key on a partial update leaves the old icon in place
    (store-api applies exclude_unset), so picking "Automatic" would silently do
    nothing. The edit route turns the empty string into an explicit null; create
    posts multipart, which can only carry strings, and store-api blanks "" to NULL
    on the way in.

    A category with no override falls back to the storefront's name-based guess -
    see blueprints/materials.py::category_icon."""
    return request.form.get("category_icon", "").strip()


@admin_bp.route("/categories")
def categories():
    client = get_api_client()
    category_list = client.get_all("/categories/")
    counts = product_facet_counts(client, "categories")
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
        client.post_form(
            "/categories/",
            data={"category_name": name, "category_icon": _icon_from_form()},
        )
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
        payload = {"category_icon": _icon_from_form() or None}
        if name:
            payload["category_name"] = name
        client.put_json(f"/categories/{category_id}", payload)
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
