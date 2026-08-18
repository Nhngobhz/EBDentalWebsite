"""
Writes for the contact page's department QR codes.

There is no page of its own here any more: the cards are edited from the "Department QR
Codes" tab of the Settings screen (admin/_qr_codes_panel.html, rendered by
blueprints/admin/settings.py, which is also what loads the list). These routes are the
form targets behind that panel, and every one of them redirects back to it.

Gated on the `admin` permission rather than product_management: a QR card is part of
what the contact page *says*, the same job as the rest of that screen (store-api
enforces the identical check, so this decorator is the UX layer).

Create posts multipart so the picture arrives with the card; edits send JSON and, when
a new file was chosen, follow it with the separate image upload - the same two-step the
Brands screen uses.
"""
import site_cache
from flask import flash, redirect, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp
from blueprints.main import QR_CODES_CACHE_KEY
from store_api import StoreAPIError, get_api_client

QR_PERMISSION = "admin"


def _back():
    """Where every one of these routes returns to: the Settings screen with the QR tab
    open. `group` is what settings.html reads to pick the active tab."""
    return url_for("admin.settings", group="qr")


def _form_fields():
    """The editable fields as store-api wants them.

    Optional text fields use `or None` so clearing one in the form actually erases it -
    an omitted key would leave the old value in place (see store-api's exclude_unset).
    `badge_variant` is exempt: "" is its real default-colour value, not "unset".
    """
    try:
        sort_order = int((request.form.get("sort_order") or "0").strip())
    except ValueError:
        sort_order = 0

    return {
        "title": request.form.get("title", "").strip(),
        "subtitle": request.form.get("subtitle", "").strip() or None,
        "badge_label": request.form.get("badge_label", "").strip() or None,
        "badge_variant": request.form.get("badge_variant", "").strip(),
        "badge_icon": request.form.get("badge_icon", "").strip() or None,
        "sort_order": sort_order,
    }


def _file_from_request():
    file = request.files.get("file")
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


@admin_bp.route("/qr-codes")
@permission_required(QR_PERMISSION)
def qr_codes():
    """Kept only so /admin/qr-codes (and every url_for below) still lands somewhere
    sensible now that the panel moved into Settings."""
    return redirect(_back())


@admin_bp.route("/qr-codes/new", methods=["POST"])
@permission_required(QR_PERMISSION)
def qr_codes_new():
    fields = _form_fields()
    if not fields["title"]:
        flash("Title is required.", "error")
        return redirect(_back())

    # Multipart, so None has to become "" - a form can't carry a null. store-api
    # blanks these back to NULL on the way in (see _blank_to_none there).
    data = {key: ("" if value is None else value) for key, value in fields.items()}

    client = get_api_client()
    try:
        client.post_form("/qr-codes/", data=data, files=_file_from_request())
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(_back())

    site_cache.invalidate(QR_CODES_CACHE_KEY)
    flash(f"QR code '{fields['title']}' created.", "success")
    return redirect(_back())


@admin_bp.route("/qr-codes/<int:qr_id>/edit", methods=["POST"])
@permission_required(QR_PERMISSION)
def qr_codes_edit(qr_id):
    fields = _form_fields()
    if not fields["title"]:
        flash("Title is required.", "error")
        return redirect(_back())

    client = get_api_client()
    try:
        client.put_json(f"/qr-codes/{qr_id}", fields)
        files = _file_from_request()
        # No file chosen means "keep the current picture" - only an actual upload
        # replaces it, so editing a caption can't wipe the QR image.
        if files:
            client.post_form(f"/qr-codes/{qr_id}/image", files=files)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(_back())

    site_cache.invalidate(QR_CODES_CACHE_KEY)
    flash("QR code updated.", "success")
    return redirect(_back())


@admin_bp.route("/qr-codes/<int:qr_id>/delete", methods=["POST"])
@permission_required(QR_PERMISSION)
def qr_codes_delete(qr_id):
    client = get_api_client()
    try:
        client.delete(f"/qr-codes/{qr_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(_back())

    site_cache.invalidate(QR_CODES_CACHE_KEY)
    flash("QR code deleted.", "success")
    return redirect(_back())
