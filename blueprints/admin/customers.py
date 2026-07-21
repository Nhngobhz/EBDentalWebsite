from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp
from store_api import StoreAPIError, get_api_client


def _customer_optional_fields():
    payload = {}
    for field in ("customer_name", "email", "phone_num", "address"):
        value = request.form.get(field, "").strip()
        if value:
            payload[field] = value
    payload["access_permission"] = request.form.get("access_permission") == "on"
    return payload


def _file_from_request():
    file = request.files.get("file")
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


@admin_bp.route("/customers")
@permission_required("customer_management")
def customers():
    client = get_api_client()
    search = request.args.get("q", "").strip()
    params = {"limit": 500}
    if search:
        params["q"] = search
    customer_list = client.get("/customers/", params=params)
    return render_template("admin/customers.html", customers=customer_list, search_query=search)


@admin_bp.route("/customers/new", methods=["POST"])
@permission_required("customer_management")
def customers_new():
    payload = _customer_optional_fields()
    if not payload.get("customer_name") or not payload.get("email"):
        flash("Name and email are required.", "error")
        return redirect(url_for("admin.customers"))

    client = get_api_client()
    try:
        created = client.post_json("/customers/", payload)
        files = _file_from_request()
        if files:
            client.post_form(f"/customers/{created['id']}/image", files=files)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.customers"))

    flash(f"Customer '{payload['customer_name']}' created. They cannot log in until they self-register with this email.", "success")
    return redirect(url_for("admin.customers"))


@admin_bp.route("/customers/<int:customer_id>/edit", methods=["POST"])
@permission_required("customer_management")
def customers_edit(customer_id):
    payload = _customer_optional_fields()
    client = get_api_client()
    try:
        client.put_json(f"/customers/{customer_id}", payload)
        files = _file_from_request()
        if files:
            client.post_form(f"/customers/{customer_id}/image", files=files)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.customers"))

    flash("Customer updated.", "success")
    return redirect(url_for("admin.customers"))


@admin_bp.route("/customers/<int:customer_id>/delete", methods=["POST"])
@permission_required("customer_management")
def customers_delete(customer_id):
    client = get_api_client()
    try:
        client.delete(f"/customers/{customer_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.customers"))

    flash("Customer deleted.", "success")
    return redirect(url_for("admin.customers"))
