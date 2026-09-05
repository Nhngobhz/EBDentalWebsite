from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp, bundle_items_from_form
from formatting import adapt_promotion, local_date_string
from store_api import StoreAPIError, get_api_client


def _date_to_iso(value, end_of_day=False):
    """<input type="date"> submits "YYYY-MM-DD" - store-api needs a full ISO
    datetime, and end_date must be strictly after start_date, so a same-day
    promotion needs start pinned to 00:00:00 and end pinned to 23:59:59.

    The +07:00 makes those the admin's own day, and it fixes two separate things.
    A window sent without an offset was read as UTC, so a deal set to end on the 19th
    actually ran until 06:59 on the 20th in Phnom Penh and one starting on the 19th
    was not live until 07:00 that morning. And a naive datetime never compares equal
    to the aware value already in the (timezone=True) column, so re-saving a promotion
    whose dates nobody had touched still rewrote both of them - and filed a start/end
    change in the activity log every single time.
    """
    if not value:
        return None
    clock = "23:59:59" if end_of_day else "00:00:00"
    return f"{value}T{clock}+07:00"


def _iso_to_date(value):
    """Reverse of the above, for pre-filling the edit form's <input type="date">.

    Via the Cambodia clock, not by slicing the string: store-api hands the timestamp
    back normalised to UTC, so a promotion starting on the 19th comes home as
    "2026-08-18T17:00:00Z" and value[:10] would offer the form the 18th - a form that
    walks the start date back a day every time it is opened and saved.
    """
    return local_date_string(value)


# The two storefronts a deal can be advertised in - see store-api's
# models.Promotion.section.
SECTIONS = ("machinery", "materials")


def _promo_form_payload():
    section = request.form.get("section")
    if section not in SECTIONS:
        # The select always posts one of the two, so anything else is a hand-made
        # request and machinery is the safe answer (what every promotion was before
        # the column existed).
        section = "machinery"

    return {
        "promotion_name": request.form.get("promotion_name", "").strip(),
        "description": request.form.get("description", "").strip() or None,
        "section": section,
        "price": request.form.get("price") or None,
        "old_price": request.form.get("old_price") or None,
        "start_date": _date_to_iso(request.form.get("start_date")),
        "end_date": _date_to_iso(request.form.get("end_date"), end_of_day=True),
        # A promotion is a collection of products - these are what the customer
        # actually receives, listed at $0 under the promotion on the quote.
        "items": bundle_items_from_form(),
    }


def _file_from_request(field="file"):
    """The named upload, in the shape store-api's image endpoints expect, or None if
    the admin left that file input empty. Empty means "leave the saved picture alone" -
    a file input can't be pre-filled with the existing file, so a blank one has to mean
    unchanged rather than cleared."""
    file = request.files.get(field)
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


def _upload_artwork(client, promotion_id):
    """Both pictures a promotion can have, each to its own endpoint.

    They are separate columns because they are separate placements: `file` is the card
    art (the square offer tiles, the promotions page, the admin thumbnail), `banner` is
    the wide hero slide at the top of the storefront. See store-api's
    models.Promotion.banner_image.

    Clearing the banner is its own checkbox rather than "submit an empty file input",
    for the reason above - and it is worth having because, unlike the card image, an
    unset banner has a real meaning: fall back to the card image."""
    card = _file_from_request()
    if card:
        client.post_form(f"/promotions/{promotion_id}/image", files=card)

    # A picked file beats a ticked "remove": someone who did both meant to replace the
    # banner, and honouring the checkbox instead would delete the upload they just made
    # and report success.
    banner = _file_from_request("banner_file")
    if banner:
        client.post_form(f"/promotions/{promotion_id}/banner", files=banner)
    elif request.form.get("remove_banner"):
        client.delete(f"/promotions/{promotion_id}/banner")


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
    # No product list travels with this page: the modal's "Included Products" picker
    # searches the catalogue as you type (admin.products_search). It used to embed the
    # first 500 products here, which stopped meaning "the catalogue" the moment the
    # SAP import took it past 8,000 rows.
    return render_template("admin/promotions.html", promotions=promos)


@admin_bp.route("/promotions/new", methods=["POST"])
@permission_required("product_management")
def promotions_new():
    payload = _promo_form_payload()
    if not payload["promotion_name"] or not payload["price"] or not payload["start_date"] or not payload["end_date"]:
        flash("Name, price, start date, and end date are all required.", "error")
        return redirect(url_for("admin.promotions"))

    client = get_api_client()
    try:
        created = client.post_json("/promotions/", payload)
        _upload_artwork(client, created["id"])
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.promotions"))

    flash(f"Promotion '{payload['promotion_name']}' created.", "success")
    return redirect(url_for("admin.promotions"))


@admin_bp.route("/promotions/<int:promotion_id>/edit", methods=["POST"])
@permission_required("product_management")
def promotions_edit(promotion_id):
    payload = _promo_form_payload()
    client = get_api_client()
    try:
        client.put_json(f"/promotions/{promotion_id}", payload)
        _upload_artwork(client, promotion_id)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.promotions"))

    flash("Promotion updated.", "success")
    return redirect(url_for("admin.promotions"))


@admin_bp.route("/promotions/<int:promotion_id>/delete", methods=["POST"])
@permission_required("product_management")
def promotions_delete(promotion_id):
    client = get_api_client()
    try:
        client.delete(f"/promotions/{promotion_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.promotions"))

    flash("Promotion deleted.", "success")
    return redirect(url_for("admin.promotions"))
