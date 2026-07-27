from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp
from formatting import adapt_set
from store_api import StoreAPIError, get_api_client


def _set_form_payload():
    return {
        "set_name": request.form.get("set_name", "").strip(),
        "description": request.form.get("description", "").strip() or None,
        "price": request.form.get("price") or None,
        "old_price": request.form.get("old_price") or None,
    }


def _file_from_request(field="file"):
    file = request.files.get(field)
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


def _upload_set_images(client, set_id):
    """Both images are optional and independent - the main thumbnail and the
    detail image under the name/description (see Set.detail_image in
    store-api). Each is only sent when that particular input was filled in, so
    editing a set without re-picking a file leaves the existing image alone."""
    main = _file_from_request("file")
    if main:
        client.post_form(f"/sets/{set_id}/image", files=main)
    detail = _file_from_request("detail_file")
    if detail:
        client.post_form(f"/sets/{set_id}/detail-image", files=detail)


@admin_bp.route("/sets")
def sets():
    client = get_api_client()
    raw_sets = client.get("/sets/", params={"limit": 200})
    return render_template("admin/sets.html", sets=[adapt_set(s) for s in raw_sets])


@admin_bp.route("/sets/new", methods=["POST"])
@permission_required("price_listing")
def sets_new():
    payload = _set_form_payload()
    if not payload["set_name"] or not payload["price"]:
        flash("Name and price are required.", "error")
        return redirect(url_for("admin.sets"))

    client = get_api_client()
    try:
        created = client.post_json("/sets/", payload)
        _upload_set_images(client, created["id"])
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.sets"))

    flash(f"Set '{payload['set_name']}' created.", "success")
    return redirect(url_for("admin.sets"))


@admin_bp.route("/sets/<int:set_id>/edit", methods=["POST"])
@permission_required("price_listing")
def sets_edit(set_id):
    payload = _set_form_payload()
    client = get_api_client()
    try:
        client.put_json(f"/sets/{set_id}", payload)
        _upload_set_images(client, set_id)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.sets"))

    flash("Set updated.", "success")
    return redirect(url_for("admin.sets"))


@admin_bp.route("/sets/<int:set_id>/delete", methods=["POST"])
@permission_required("price_listing")
def sets_delete(set_id):
    client = get_api_client()
    try:
        client.delete(f"/sets/{set_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.sets"))

    flash("Set deleted.", "success")
    return redirect(url_for("admin.sets"))
