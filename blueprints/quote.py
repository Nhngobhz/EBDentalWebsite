from flask import Blueprint, jsonify, request

from auth import can_quote, is_logged_in
from formatting import adapt_order
from store_api import StoreAPIError, get_api_client

quote_bp = Blueprint("quote", __name__, url_prefix="/quote")


@quote_bp.route("/submit", methods=["POST"])
def submit():
    """Finalizes the client-side quote drawer (QuoteCart in main.js) into a real
    store-api Order. Accepts only product_id + qty per line - store-api itself looks up
    and snapshots each line's authoritative current price server-side (see
    store-api/app/routers/orders.py), so a tampered request can never record a
    fabricated price here."""
    if not is_logged_in():
        return jsonify({"detail": "Please log in to submit a quote."}), 401
    if not can_quote():
        return jsonify({"detail": "Your account isn't able to place orders."}), 403

    body = request.get_json(silent=True) or {}
    items = body.get("items") or []
    if not items:
        return jsonify({"detail": "Your quote is empty."}), 400

    clinic_name = (body.get("clinic_name") or "").strip()
    phone = (body.get("phone") or "").strip()
    address = (body.get("address") or "").strip()
    if not clinic_name or not phone or not address:
        return jsonify({"detail": "Clinic, Contact Tel, and Address are required."}), 400

    # salesperson/quoted_by_name are NOT sent - store-api derives them server-side from
    # whoever is actually calling (see routers/orders.py::create_order), never trusted
    # from the client.
    payload = {
        "clinic_name": clinic_name,
        "contact_person": body.get("contact_person") or None,
        "phone": phone,
        "address": address,
        "payment_term": body.get("payment_term") or None,
        "install_term": body.get("install_term") or None,
        "discount_type": body.get("discount_type") or "percent",
        "discount_value": body.get("discount_value") or 0,
        "items": [{"product_id": item["id"], "qty": item["qty"]} for item in items],
    }

    client = get_api_client()
    try:
        order = client.post_json("/orders/", payload)
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 400)

    return jsonify(adapt_order(order))


@quote_bp.route("/<int:order_id>/pdf", methods=["POST"])
def upload_pdf(order_id):
    """Relays the browser's real client-rendered quotation PDF (QuoteCart.exportPDF() in
    main.js, called right after confirmPurchase() places the order) to store-api, which
    hands it to that order's Telegram alert if it's still waiting for one (see
    deliver_order_alert in store-api's services/telegram.py) instead of falling back to
    its own approximation. Purely a best-effort enhancement - the customer's order is
    already placed by the time this is called, so any failure here is just logged away,
    never surfaced to the customer."""
    if not is_logged_in():
        return jsonify({"detail": "Please log in."}), 401

    file = request.files.get("file")
    if file is None:
        return jsonify({"detail": "No file uploaded."}), 400

    client = get_api_client()
    try:
        client.post_form(
            f"/orders/{order_id}/quotation-pdf",
            files={"file": (file.filename, file.stream, file.mimetype)},
        )
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 400)

    return jsonify({"received": True})
