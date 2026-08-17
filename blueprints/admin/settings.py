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
from flask import flash, redirect, render_template, request, url_for

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
    return render_template(
        "admin/settings.html",
        groups=data["groups"],
        values=data["values"],
        defaults=data["defaults"],
        status=data["status"],
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
    for setting in group["settings"]:
        key = setting["key"]
        if setting["type"] == "bool":
            values[key] = key in request.form
        elif key in request.form:
            values[key] = request.form[key]

    try:
        client.put_json("/settings/", {"values": values})
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
