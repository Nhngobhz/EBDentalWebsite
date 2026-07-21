from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp
from formatting import adapt_promotion
from store_api import StoreAPIError, get_api_client


def _date_to_iso(value, end_of_day=False):
    """<input type="date"> submits "YYYY-MM-DD" - store-api needs a full ISO
    datetime, and end_date must be strictly after start_date, so a same-day
    promotion needs start pinned to 00:00:00 and end pinned to 23:59:59."""
    if not value:
        return None
    return f"{value}T23:59:59" if end_of_day else f"{value}T00:00:00"


def _iso_to_date(value):
    """Reverse of the above, for pre-filling the edit form's <input type="date">."""
    if not value:
        return ""
    return value[:10]


def _promo_form_payload():
    return {
        "promotion_name": request.form.get("promotion_name", "").strip(),
        "description": request.form.get("description", "").strip() or None,
        "price": request.form.get("price") or None,
        "old_price": request.form.get("old_price") or None,
        "start_date": _date_to_iso(request.form.get("start_date")),
        "end_date": _date_to_iso(request.form.get("end_date"), end_of_day=True),
    }


def _file_from_request():
    file = request.files.get("file")
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


@admin_bp.route("/promotions")
def promotions():
    client = get_api_client()
    raw_promotions = client.get("/promotions/", params={"limit": 200})
    now = datetime.now(timezone.utc)
    promos = []
    for raw in raw_promotions:
        promo = adapt_promotion(raw)
        start = datetime.fromisoformat(promo["start_date"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(promo["end_date"].replace("Z", "+00:00"))
        promo["is_active"] = start <= now <= end
        promo["is_upcoming"] = start > now
        promo["start_date_short"] = _iso_to_date(promo["start_date"])
        promo["end_date_short"] = _iso_to_date(promo["end_date"])
        promos.append(promo)
    return render_template("admin/promotions.html", promotions=promos)


@admin_bp.route("/promotions/new", methods=["POST"])
@permission_required("price_listing")
def promotions_new():
    payload = _promo_form_payload()
    if not payload["promotion_name"] or not payload["price"] or not payload["start_date"] or not payload["end_date"]:
        flash("Name, price, start date, and end date are all required.", "error")
        return redirect(url_for("admin.promotions"))

    client = get_api_client()
    try:
        created = client.post_json("/promotions/", payload)
        files = _file_from_request()
        if files:
            client.post_form(f"/promotions/{created['id']}/image", files=files)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.promotions"))

    flash(f"Promotion '{payload['promotion_name']}' created.", "success")
    return redirect(url_for("admin.promotions"))


@admin_bp.route("/promotions/<int:promotion_id>/edit", methods=["POST"])
@permission_required("price_listing")
def promotions_edit(promotion_id):
    payload = _promo_form_payload()
    client = get_api_client()
    try:
        client.put_json(f"/promotions/{promotion_id}", payload)
        files = _file_from_request()
        if files:
            client.post_form(f"/promotions/{promotion_id}/image", files=files)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.promotions"))

    flash("Promotion updated.", "success")
    return redirect(url_for("admin.promotions"))


@admin_bp.route("/promotions/<int:promotion_id>/delete", methods=["POST"])
@permission_required("price_listing")
def promotions_delete(promotion_id):
    client = get_api_client()
    try:
        client.delete(f"/promotions/{promotion_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.promotions"))

    flash("Promotion deleted.", "success")
    return redirect(url_for("admin.promotions"))
