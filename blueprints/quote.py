import site_settings
from flask import Blueprint, jsonify, request

from auth import can_quote, is_customer, is_logged_in
from formatting import adapt_order
from store_api import StoreAPIError, get_api_client

quote_bp = Blueprint("quote", __name__, url_prefix="/quote")

# EB's own terms of sale, applied to every customer-placed order.
#
# Staff still type these per quote - they're negotiating them. A customer isn't:
# these are the terms being offered *to* them, so the cart drawer shows them as
# read-only text (partials/quote_drawer.html) and submit() below substitutes them
# rather than trusting the request, which is what stops a hand-crafted POST from
# printing its own payment terms on an EB quotation.
#
# Both now come from the admin Settings screen (Settings → Quote & Invoice), which is
# also where store-api's own PDF builder reads its fallbacks from - so the terms the
# cart shows, the terms recorded on the order and the terms printed on the document are
# one value, not three literals in two repos.
def customer_payment_term():
    return site_settings.get().get("default_payment_term") or "COD"


def customer_install_term():
    return site_settings.get().get("default_install_term") or "Free within Phnom Penh"


@quote_bp.route("/submit", methods=["POST"])
def submit():
    """Finalizes the client-side quote drawer (QuoteCart in main.js) into a real
    store-api Order. Accepts only product_id/promotion_id + qty per line - store-api
    itself looks up and snapshots each line's authoritative current price server-side
    (see store-api/app/routers/orders.py), so a tampered request can never record a
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

    # Customers must say how they'll pay: "cash" produces a quote, "khqr" a real order
    # awaiting payment. Staff never send one - their cart always produces a quote
    # (store-api ignores payment_method for staff and enforces it for customers too).
    payment_method = body.get("payment_method") or None
    if is_customer() and payment_method not in ("cash", "khqr"):
        return jsonify({"detail": "Please choose a payment method (Cash or KHQR)."}), 400

    # Payment/installation terms are EB's to state, so a customer's order gets the
    # standing ones no matter what the request said. Staff are quoting per deal and
    # keep typing their own. Contact person stays client-supplied either way - that
    # one genuinely is the buyer's own detail.
    if is_customer():
        payment_term = customer_payment_term()
        install_term = customer_install_term()
    else:
        payment_term = body.get("payment_term") or None
        install_term = body.get("install_term") or None

    # salesperson/quoted_by_name are NOT sent - store-api derives them server-side from
    # whoever is actually calling (see routers/orders.py::create_order), never trusted
    # from the client.
    payload = {
        "clinic_name": clinic_name,
        "contact_person": body.get("contact_person") or None,
        "phone": phone,
        "address": address,
        "payment_term": payment_term,
        "install_term": install_term,
        "payment_method": payment_method if is_customer() else None,
        "discount_type": body.get("discount_type") or "percent",
        "discount_value": body.get("discount_value") or 0,
        "items": [
            {"promotion_id": item["id"], "qty": item["qty"]}
            if item.get("kind") == "promotion"
            else {
                "set_id": item["id"],
                "qty": item["qty"],
                # Which alternative each swappable slot landed on. Rebuilt from
                # ints rather than forwarded verbatim so a hand-edited localStorage
                # cart can't post arbitrary JSON into the order payload; store-api
                # validates the ids themselves against the set.
                "options": [
                    {"group_id": int(o["group_id"]), "choice_id": int(o["choice_id"])}
                    for o in (item.get("options") or [])
                    if str(o.get("group_id", "")).isdigit()
                    and str(o.get("choice_id", "")).isdigit()
                ],
            }
            if item.get("kind") == "set"
            else {"product_id": item["id"], "qty": item["qty"]}
            for item in items
        ],
    }

    client = get_api_client()

    # Pay-by-QR is NOT an order yet. store-api deliberately writes no order and no line
    # items until the payment is confirmed, so this returns a checkout (a QR + an id to
    # poll) and the order only comes into existence at /quote/checkout/<id>/payment-status.
    # A customer therefore never holds an order they haven't paid for.
    if payment_method == "khqr":
        try:
            checkout = client.post_json("/orders/checkout", payload)
        except StoreAPIError as e:
            return jsonify({"detail": e.detail}), (e.status_code or 400)
        return jsonify({"checkout": checkout})

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


@quote_bp.route("/checkout/<int:checkout_id>/payment-status", methods=["GET"])
def checkout_payment_status(checkout_id):
    """Polled by the KHQR modal (QuoteCart.showKhqrModal in main.js) every few seconds.
    A thin relay to store-api's GET /orders/checkout/{id}/payment-status, which asks
    Bakong/PayWay and, on the first confirmed check, CREATES the order (as paid) and
    fires the paid-order Telegram alert. Until then no order exists at all - that's the
    point of the checkout flow.

    Returns {"payment_status": "unpaid"|"paid"|"expired", "order": {...} | null}; the
    order is present from the moment it flips to paid, and is what the browser renders
    the receipt from. store-api re-checks that the caller owns the checkout, so this
    can't be used to probe someone else's."""
    if not is_logged_in():
        return jsonify({"detail": "Please log in."}), 401

    client = get_api_client()
    try:
        result = client.get(f"/orders/checkout/{checkout_id}/payment-status")
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 400)

    # The order arrives raw from store-api; the browser expects the same adapted shape
    # every other order in this app is rendered from.
    if result.get("order"):
        result["order"] = adapt_order(result["order"])
    return jsonify(result)
