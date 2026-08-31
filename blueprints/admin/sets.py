import json

from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp, bundle_items_from_form
from formatting import adapt_set
from store_api import StoreAPIError, get_api_client


def option_groups_from_form(field="option_groups_json"):
    """Reads the Set upgrade-slot editor (ebOptionGroupPicker in main.js) into
    store-api's `option_groups` shape.

    A hidden JSON field rather than the parallel inputs bundle_items_from_form
    reads, because this structure is two levels deep - a flat
    item_product_id[]/item_qty[] pair has nowhere to record which choice belongs
    to which slot.

    Always returns a list, never None, for the same reason as the contents
    picker: an admin who deletes every slot must send [] ("this set is fixed
    again") rather than omitting the field ("leave the slots alone").

    Rebuilt field by field instead of forwarded as-parsed. The value arrives from
    a browser form, so it is untrusted input that reaches store-api as JSON - and
    a bad `price_delta` should be a flash message here, not a 422 from the API.
    """
    raw = request.form.get(field)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []

    groups = []
    for group in parsed:
        if not isinstance(group, dict):
            continue
        name = str(group.get("name") or "").strip()
        choices = []
        for choice in group.get("choices") or []:
            if not isinstance(choice, dict) or not choice.get("product_id"):
                continue
            delta = choice.get("price_delta")
            choices.append({
                "product_id": int(choice["product_id"]),
                "qty": int(choice.get("qty") or 1),
                # None is meaningful and must survive: it is what tells store-api
                # to derive the upcharge instead of storing one.
                "price_delta": None if delta in (None, "") else float(delta),
                "is_default": bool(choice.get("is_default")),
            })
        if name and choices:
            groups.append({"name": name, "choices": choices})
    return groups


def _set_form_payload():
    return {
        "set_name": request.form.get("set_name", "").strip(),
        "description": request.form.get("description", "").strip() or None,
        "price": request.form.get("price") or None,
        "old_price": request.form.get("old_price") or None,
        # Which brand the set is filed under on the Promotions page. Optional -
        # an empty select means no brand, and is sent as an explicit null so
        # editing a set can also *clear* the brand it had (store-api leaves a
        # field alone only when it is omitted entirely).
        "brand_id": request.form.get("brand_id") or None,
        # A set is a collection of products - these are what the customer
        # actually receives, listed at $0 under the set on the quote.
        "items": bundle_items_from_form(),
        # The swappable slots - see option_groups_from_form above.
        "option_groups": option_groups_from_form(),
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
    # No product list travels with this page - see the same note in promotions();
    # both modals search the catalogue through admin.products_search instead.
    brands = client.get("/brands/", params={"limit": 200})
    return render_template(
        "admin/sets.html",
        sets=[adapt_set(s) for s in raw_sets],
        brands=brands,
    )


@admin_bp.route("/sets/new", methods=["POST"])
@permission_required("product_management")
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
@permission_required("product_management")
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
@permission_required("product_management")
def sets_delete(set_id):
    client = get_api_client()
    try:
        client.delete(f"/sets/{set_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.sets"))

    flash("Set deleted.", "success")
    return redirect(url_for("admin.sets"))
