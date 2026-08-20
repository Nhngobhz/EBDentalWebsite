from datetime import date

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
    # Unlike the fields above, these two are sent even when blank (as explicit
    # nulls) so staff can clear a wrong birthday/gender back to empty - store-api
    # only writes the keys the payload actually contains.
    for field in ("date_of_birth", "gender"):
        payload[field] = request.form.get(field, "").strip() or None
    # The delivery pin follows the same explicit-null rule, and for a sharper
    # reason: a location that is WRONG sends a driver to the wrong building, so
    # "Clear" on the picker has to actually erase it rather than quietly leave
    # the previous coordinates in place.
    payload.update(_location_fields())
    payload["access_permission"] = request.form.get("access_permission") == "on"
    return payload


def _location_fields():
    """latitude/longitude/map_link off the picker's hidden inputs.

    A coordinate that will not parse is sent as null rather than raising: the
    picker writes these itself and only ever writes valid numbers, so anything
    else is a mangled POST, and dropping the pin beats failing the whole save of
    a customer's name and email. store-api enforces the real bounds and the
    link's scheme (see Latitude/MapLink in schemas.py).
    """
    def _coord(field):
        raw = request.form.get(field, "").strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    return {
        "latitude": _coord("latitude"),
        "longitude": _coord("longitude"),
        "map_link": request.form.get("map_link", "").strip() or None,
    }


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
    return render_template(
        "admin/customers.html",
        customers=customer_list,
        search_query=search,
        today=date.today().isoformat(),
    )


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
