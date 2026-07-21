from flask import flash, redirect, render_template, request, url_for

from auth import current_account, permission_required
from blueprints.admin import admin_bp
from store_api import StoreAPIError, get_api_client

PERMISSION_FIELDS = ("user_management", "price_listing", "product_management", "customer_management")


@admin_bp.route("/users")
@permission_required("user_management")
def users():
    client = get_api_client()
    user_list = client.get("/users/", params={"limit": 500})
    stats = {
        "total": len(user_list),
        "active": sum(1 for u in user_list if u["is_active"]),
    }
    stats.update({perm: sum(1 for u in user_list if u.get(perm)) for perm in PERMISSION_FIELDS})
    return render_template("admin/user_management.html", all_users=user_list, stats=stats)


@admin_bp.route("/users/new", methods=["POST"])
@permission_required("user_management")
def users_new():
    name = request.form.get("user_name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    if not name or not email or not password:
        flash("Name, email, and password are required.", "error")
        return redirect(url_for("admin.users"))

    payload = {
        "user_name": name,
        "email": email,
        "password": password,
        "role_title": request.form.get("role_title", "").strip() or "Staff",
        "address": request.form.get("address", "").strip() or None,
        "phone_num": request.form.get("phone_num", "").strip() or None,
    }
    for perm in PERMISSION_FIELDS:
        payload[perm] = request.form.get(perm) == "on"

    client = get_api_client()
    try:
        client.post_json("/users/", payload)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.users"))

    flash(f"Staff account '{name}' created. They must verify their email before logging in.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/edit", methods=["POST"])
@permission_required("user_management")
def users_edit(user_id):
    payload = {"is_active": request.form.get("is_active") == "on"}
    for field in ("user_name", "address", "phone_num", "role_title"):
        value = request.form.get(field, "").strip()
        if value:
            payload[field] = value
    for perm in PERMISSION_FIELDS:
        payload[perm] = request.form.get(perm) == "on"

    client = get_api_client()
    try:
        client.put_json(f"/users/{user_id}", payload)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.users"))

    flash("Staff account updated.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@permission_required("user_management")
def users_delete(user_id):
    account = current_account()
    if account and account["id"] == user_id:
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("admin.users"))

    client = get_api_client()
    try:
        client.delete(f"/users/{user_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.users"))

    flash("Staff account deactivated.", "success")
    return redirect(url_for("admin.users"))
