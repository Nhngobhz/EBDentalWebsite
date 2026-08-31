"""
The admin Settings screen.

Thin, on purpose: store-api owns the settings spec (app/core/settings_spec.py), the
defaults, and the validation. This module fetches that spec, renders a form from it, and
posts whatever comes back. Adding a setting therefore means editing the spec in
store-api and nothing here.

Gated on the `admin` permission - which is deliberately NOT implied by user_management,
so "can create staff accounts" and "can rewrite what every printed quote says" stay
separate jobs. store-api re-checks the same permission on every read and write, so this
decorator is the UX layer, not the security boundary.
"""
import site_cache
from flask import flash, jsonify, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp
from store_api import StoreAPIError, get_api_client

SETTINGS_PERMISSION = "admin"

# Key this app caches GET /settings/public under - must match site_settings() in app.py.
# Cleared on every successful save so the storefront reflects the change immediately
# rather than after the 60s TTL. Without this, an admin switches on maintenance mode,
# opens the shop in another tab, sees it still open, and reasonably concludes the
# setting didn't work.
SITE_SETTINGS_CACHE_KEY = ("site_settings", "all")


def _checkbox_keys(group):
    """Booleans need naming explicitly: an unchecked checkbox sends nothing at all, so a
    form that only reads request.form can never turn one off - it looks identical to
    "this field wasn't on the form"."""
    return [s["key"] for s in group["settings"] if s["type"] == "bool"]


@admin_bp.route("/settings")
@permission_required(SETTINGS_PERMISSION)
def settings():
    client = get_api_client()
    data = client.get("/settings/")
    # The contact page's QR cards are a table, not settings, but they are edited from the
    # "Department QR Codes" tab of this screen - so this page loads them too. Fetched
    # unconditionally rather than only when ?group=qr: the tabs switch client-side, so a
    # panel that was empty until a reload would be a worse surprise than one small call.
    # Writes go to the admin.qr_codes_* routes (blueprints/admin/qr_codes.py).
    try:
        qr_codes = client.get("/qr-codes/", params={"limit": 200})
    except StoreAPIError as e:
        flash(e.detail, "error")
        qr_codes = []

    # The "Catalogue Sync" tab. Its first paint comes from here so the panel is already
    # filled in when the page opens - after that it polls the two JSON routes below. A
    # store-api that is up enough to have served the settings above can still fail this
    # one (an older build with no /sap-sync), and that is not a reason to lose the whole
    # Settings screen, so it degrades to a panel that says so.
    try:
        sap_sync = client.get("/sap-sync/status", params={"include_reports": "true"})
    except StoreAPIError as e:
        sap_sync = {"error": e.detail}

    return render_template(
        "admin/settings.html",
        groups=data["groups"],
        values=data["values"],
        defaults=data["defaults"],
        status=data["status"],
        qr_codes=qr_codes,
        sap_sync=sap_sync,
        # Which tab to reopen after a save redirect, so an admin who saves the
        # "Quote & Invoice" group isn't bounced back to "Store & Contact".
        active_group=request.args.get("group") or data["groups"][0]["id"],
    )


@admin_bp.route("/settings/<group_id>", methods=["POST"])
@permission_required(SETTINGS_PERMISSION)
def settings_save(group_id):
    client = get_api_client()
    try:
        spec = client.get("/settings/")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.settings"))

    group = next((g for g in spec["groups"] if g["id"] == group_id), None)
    if group is None:
        flash("Unknown settings group.", "error")
        return redirect(url_for("admin.settings"))

    # Only this group's keys are submitted, so one tab's form can never blank out
    # another tab's values just by not containing them.
    values = {}
    uploads = {}
    for setting in group["settings"]:
        key = setting["key"]
        if setting["type"] == "bool":
            values[key] = key in request.form
        elif setting["type"] == "image":
            # An `image` setting has no text input at all - its value is a stored
            # picture URL that only store-api's upload endpoint ever writes. The form
            # offers a file field and, once one is set, a "remove" checkbox; see the
            # macro in templates/admin/settings.html for the two field names.
            upload = request.files.get(f"{key}__file")
            if upload and upload.filename:
                uploads[key] = upload
            elif request.form.get(f"{key}__clear"):
                values[key] = ""
            # Neither means "leave the picture alone", which is why nothing is written
            # here - the same rule the Brands and QR-code screens follow, so saving a
            # caption can never silently wipe the picture next to it.
        elif key in request.form:
            values[key] = request.form[key]

    try:
        client.put_json("/settings/", {"values": values})
        # After the values, not before: a rejected field then leaves nothing uploaded,
        # rather than an orphan file stored against a save that failed.
        for key, upload in uploads.items():
            client.post_form(
                f"/settings/image/{key}",
                files={"file": (upload.filename, upload.stream, upload.mimetype)},
            )
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.settings", group=group_id))

    site_cache.invalidate(SITE_SETTINGS_CACHE_KEY)
    flash(f"{group['label']} settings saved.", "success")
    return redirect(url_for("admin.settings", group=group_id))


@admin_bp.route("/settings/<group_id>/reset", methods=["POST"])
@permission_required(SETTINGS_PERMISSION)
def settings_reset(group_id):
    client = get_api_client()
    try:
        client.post_json("/settings/reset", {"group": group_id})
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.settings", group=group_id))

    site_cache.invalidate(SITE_SETTINGS_CACHE_KEY)
    flash("Settings restored to their defaults.", "success")
    return redirect(url_for("admin.settings", group=group_id))


# --- Catalogue Sync tab -------------------------------------------------------------
# JSON rather than the post-and-redirect the rest of this screen uses, because the job
# outlives the request: a sync of ~8,000 items takes minutes, so the button starts it and
# the panel polls. Both routes are pass-throughs to store-api, which owns the run (see
# its app/services/sap_sync_runner.py) - nothing about the sync is decided here.


@admin_bp.route("/settings/sap-sync/status")
@permission_required(SETTINGS_PERMISSION)
def sap_sync_status():
    client = get_api_client()
    # The full report text is thousands of words; the panel asks for it when it loads and
    # when a run ends, and polls without it in between.
    include = "true" if request.args.get("reports") else "false"
    try:
        return jsonify(client.get("/sap-sync/status", params={"include_reports": include}))
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 502)


@admin_bp.route("/settings/sap-sync/run", methods=["POST"])
@permission_required(SETTINGS_PERMISSION)
def sap_sync_run():
    payload = request.get_json(silent=True) or {}
    client = get_api_client()
    try:
        return jsonify(
            client.post_json(
                "/sap-sync/run",
                {
                    "catalogue": payload.get("catalogue") or "all",
                    # Explicitly, and defaulting to a dry run: a missing or misspelled
                    # flag then previews the run instead of repricing the catalogue.
                    "apply": bool(payload.get("apply")),
                },
            )
        )
    except StoreAPIError as e:
        # 409 (one is already running) reaches the panel as its own message rather than
        # a generic failure - see SapSyncBusy in store-api.
        return jsonify({"detail": e.detail}), (e.status_code or 400)
