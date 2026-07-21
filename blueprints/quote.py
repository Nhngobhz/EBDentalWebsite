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

    payload = {
        "clinic_name": body.get("clinic_name") or None,
        "contact_person": body.get("contact_person") or None,
        "phone": body.get("phone") or None,
        "address": body.get("address") or None,
        "payment_term": body.get("payment_term") or None,
        "salesperson": body.get("salesperson") or None,
        "install_term": body.get("install_term") or None,
        "cash_discount": body.get("cash_discount") or 0,
        "items": [{"product_id": item["id"], "qty": item["qty"]} for item in items],
    }

    client = get_api_client()
    try:
        order = client.post_json("/orders/", payload)
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 400)

    return jsonify(adapt_order(order))
