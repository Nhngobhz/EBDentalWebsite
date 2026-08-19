from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp
from store_api import StoreAPIError, get_api_client


def _pdf_from_request():
    file = request.files.get("pdf")
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


def _image_from_request():
    file = request.files.get("image")
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


@admin_bp.route("/manuals")
@permission_required("product_management")
def manuals():
    client = get_api_client()
    manual_list = client.get("/manuals/", params={"limit": 500})
    # A gift-only product can still have a manual, so it stays pickable.
    products = client.get("/products/", params={"limit": 500, "include_unpurchasable": "true"})
    return render_template("admin/manuals.html", manuals=manual_list, products=products)


@admin_bp.route("/manuals/new", methods=["POST"])
@permission_required("product_management")
def manuals_new():
    product_id = request.form.get("product_id", type=int)
    if not product_id:
        flash("A product is required.", "error")
        return redirect(url_for("admin.manuals"))

    data = {"product_id": product_id}
    # Sent only when filled in: POST /manuals/ is multipart, and an empty string
    # would store "" rather than leaving the title unset.
    title = request.form.get("title", "").strip()
    if title:
        data["title"] = title
    description = request.form.get("description", "").strip()
    if description:
        data["description"] = description

    client = get_api_client()
    try:
        created = client.post_form("/manuals/", data=data, files=_pdf_from_request())
        image_files = _image_from_request()
        if image_files:
            client.post_form(f"/manuals/{created['id']}/image", files=image_files)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.manuals"))

    flash("Manual added.", "success")
    return redirect(url_for("admin.manuals"))


@admin_bp.route("/manuals/<int:manual_id>/edit", methods=["POST"])
@permission_required("product_management")
def manuals_edit(manual_id):
    product_id = request.form.get("product_id", type=int)
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()

    client = get_api_client()
    try:
        client.put_json(
            f"/manuals/{manual_id}",
            {
                "product_id": product_id,
                # Explicit null, not omission: clearing the box has to actually
                # clear the title, the same rule the other optional text fields
                # in this admin follow.
                "title": title or None,
                "description": description or None,
            },
        )
        pdf_files = _pdf_from_request()
        if pdf_files:
            client.post_form(f"/manuals/{manual_id}/pdf", files=pdf_files)
        image_files = _image_from_request()
        if image_files:
            client.post_form(f"/manuals/{manual_id}/image", files=image_files)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.manuals"))

    flash("Manual updated.", "success")
    return redirect(url_for("admin.manuals"))


@admin_bp.route("/manuals/<int:manual_id>/delete", methods=["POST"])
@permission_required("product_management")
def manuals_delete(manual_id):
    client = get_api_client()
    try:
        client.delete(f"/manuals/{manual_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.manuals"))

    flash("Manual deleted.", "success")
    return redirect(url_for("admin.manuals"))
