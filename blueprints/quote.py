import maps
import site_settings
from flask import Blueprint, jsonify, request

from auth import can_quote, has_any_permission, is_customer, is_logged_in, is_staff
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


def customer_contact_person():
    """Who the buyer should call about their order - EB's number, not theirs.

    "Contact Person" prints in the right-hand column of the quotation, next to
    Salesperson and User (see buildPrintTemplate in main.js and invoice_pdf.py):
    it has always been EB's contact, so it belongs with the two terms above
    rather than in the box a customer fills in.
    """
    return site_settings.get().get("default_contact_person") or "098 882 953"


def _saved_customer():
    """The signed-in customer's own record, or None.

    Best-effort by design: every caller here is decorating an order with
    convenience data, and a store-api hiccup while fetching it must not be the
    reason a purchase fails.
    """
    if not is_customer():
        return None
    try:
        return get_api_client().get("/customers/me")
    except StoreAPIError:
        return None


@quote_bp.route("/prefill", methods=["GET"])
def prefill():
    """What the cart drawer should start with for a signed-in customer.

    Read straight off their profile rather than out of the session, because the
    session caches only a name/email/permission triple and would go stale the
    moment they edited their address - which is exactly the field this exists to
    fill in.

    Staff get an empty object: their cart is a quoting tool for *other people's*
    clinics, so seeding it with the salesperson's own address would be wrong
    every single time.
    """
    customer = _saved_customer()
    if not customer:
        return jsonify({})
    return jsonify({
        # The cart calls this field "Clinic"; for a storefront customer that is
        # simply who they are, which is the name on their account.
        "clinic": customer.get("customer_name") or "",
        "tel": customer.get("phone_num") or "",
        "address": customer.get("address") or "",
        # Which saved location this order is about to be delivered to. `map_url` is
        # the ready-made "open this in Maps" link the cart shows; the three raw
        # fields under it seed the picker behind the cart's Change button, so it
        # opens on the pin the customer already has instead of on an empty map.
        #
        # None of them is trusted on the way back in: submit() reads the pin off
        # the customer record itself, and save_location() below writes it through
        # store-api's own validation.
        "map_url": maps.location_link(
            customer.get("latitude"), customer.get("longitude"), customer.get("map_link")
        ),
        "latitude": customer.get("latitude"),
        "longitude": customer.get("longitude"),
        "map_link": customer.get("map_link") or "",
    })


@quote_bp.route("/location", methods=["POST"])
def save_location():
    """Move the signed-in customer's delivery pin, from the cart drawer.

    The pin belongs to the account rather than to one order, so this really does
    edit the profile - it is the same PUT /customers/me the profile page makes,
    reached without leaving a full cart behind. Customers only: staff carts quote
    for other people's clinics and have no pin of their own to move.

    Returns the same three fields prefill() does, so the caller can redraw the
    line under the address box from the answer instead of guessing at it.
    """
    if not is_customer():
        return jsonify({"detail": "Only customers have a delivery location."}), 403

    body = request.get_json(silent=True) or {}

    def _coord(field):
        raw = body.get(field)
        if raw in (None, ""):
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    # Sent as explicit nulls when blank rather than omitted, so clearing the pin in
    # the picker really clears it - store-api only touches the keys it is given
    # (PUT /customers/me does model_dump(exclude_unset=True)).
    payload = {
        "latitude": _coord("latitude"),
        "longitude": _coord("longitude"),
        "map_link": (body.get("map_link") or "").strip() or None,
    }
    try:
        customer = get_api_client().put_json("/customers/me", payload)
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 400)

    return jsonify({
        "map_url": maps.location_link(
            customer.get("latitude"), customer.get("longitude"), customer.get("map_link")
        ),
        "latitude": customer.get("latitude"),
        "longitude": customer.get("longitude"),
        "map_link": customer.get("map_link") or "",
    })


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

    # Payment/installation terms and the contact person are EB's to state, so a
    # customer's order gets the standing ones no matter what the request said -
    # which is what stops a hand-crafted POST printing its own onto an EB
    # quotation. Staff are quoting per deal and keep typing their own.
    if is_customer():
        payment_term = customer_payment_term()
        install_term = customer_install_term()
        contact_person = customer_contact_person()
    else:
        payment_term = body.get("payment_term") or None
        install_term = body.get("install_term") or None
        contact_person = body.get("contact_person") or None

    # salesperson/quoted_by_name are NOT sent - store-api derives them server-side from
    # whoever is actually calling (see routers/orders.py::create_order), never trusted
    # from the client.
    payload = {
        "clinic_name": clinic_name,
        "contact_person": contact_person,
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

    # The delivery pin is read off the customer's own record rather than accepted
    # from the request. Not for safety - a buyer's location is their own detail,
    # like contact_person - but for correctness: the cart lives in localStorage
    # and can be days older than the profile, so trusting the copy it carries is
    # how an order ends up pointing at an address the customer already corrected.
    # Staff quotes get nothing: there is no customer record behind a walk-in.
    saved = _saved_customer()
    if saved:
        payload["latitude"] = saved.get("latitude")
        payload["longitude"] = saved.get("longitude")
        payload["map_link"] = saved.get("map_link")

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


# What staff may do to a quote they have just raised, straight from the cart, without
# going round to the admin Orders page: hand the customer a QR to pay it, or record it as
# already paid. Both mirror a button that screen already has (Payment QR / Complete), and
# both go to the same store-api endpoints it calls - this is a second doorway onto the
# same actions, not a second set of rules.
#
# Same pair of permissions store-api gates those endpoints with (price_listing OR admin,
# see require_any_permission in routers/orders.py). Checked inline rather than with
# any_permission_required, because these are fetch() endpoints: the decorator's abort(403)
# would hand JavaScript an HTML error page instead of the {"detail": ...} every other
# route in this file returns.
def _staff_order_action_denied():
    """None if the caller may work an order from the cart, else a JSON error tuple."""
    if not is_logged_in():
        return jsonify({"detail": "Please log in to continue."}), 401
    if not is_staff() or not has_any_permission("price_listing", "admin"):
        return jsonify({"detail": "Your account isn't able to do this."}), 403
    return None


@quote_bp.route("/<int:order_id>/khqr", methods=["POST"])
def issue_khqr(order_id):
    """Puts a scannable KHQR on the quote staff have just created, so it can be handed
    over at the counter or sent to the customer to pay. Returns the whole order back -
    the browser draws the QR from khqr_string and downloads it as an image.

    store-api is idempotent here: while the stored QR is still payable it hands the same
    one back rather than minting a new one, so a customer mid-scan never ends up looking
    at a code the order no longer expects."""
    denied = _staff_order_action_denied()
    if denied:
        return denied

    client = get_api_client()
    try:
        order = client.post_json(f"/orders/{order_id}/khqr")
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 400)

    return jsonify(adapt_order(order))


@quote_bp.route("/<int:order_id>/invoice", methods=["POST"])
def mark_invoiced(order_id):
    """"Just make an invoice" - the money is already in (cash at the counter, a bank
    transfer), so the quote is recorded as paid and becomes the invoice for that sale.
    Exactly what the admin Orders page's "Complete" button does, and the same single
    field: payment_status="paid". store-api stamps paid_at and fires the paid-order
    Telegram alert; the browser re-renders the document as an Invoice off the order
    returned here."""
    denied = _staff_order_action_denied()
    if denied:
        return denied

    client = get_api_client()
    try:
        order = client.put_json(f"/orders/{order_id}", {"payment_status": "paid"})
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 400)

    return jsonify(adapt_order(order))


@quote_bp.route("/<int:order_id>/payment-status", methods=["GET"])
def order_payment_status(order_id):
    """Polled by the staff QR dialog while the customer scans - the order equivalent of
    checkout_payment_status below, and the same relay the admin Orders page makes. The
    order already exists here (staff raised it as a quote), so this only ever flips it
    from unpaid to paid; store-api does the Bakong/PayWay check and fires the paid-order
    alert on the first confirmed one."""
    denied = _staff_order_action_denied()
    if denied:
        return denied

    client = get_api_client()
    try:
        result = client.get(f"/orders/{order_id}/payment-status")
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 400)

    return jsonify(result)


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
