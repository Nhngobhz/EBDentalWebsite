from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp, product_facet_counts
from store_api import StoreAPIError, get_api_client


def _file_from_request():
    file = request.files.get("file")
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


@admin_bp.route("/brands")
def brands():
    client = get_api_client()
    # get_all, not limit=200: there are 190 brands since the SAP import, and a
    # fixed page that happens to still fit is how this table silently starts
    # dropping rows off the end.
    brand_list = client.get_all("/brands/")
    counts = product_facet_counts(client, "brands")
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
