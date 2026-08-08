from flask import flash, jsonify, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp
from formatting import adapt_order, adapt_product
from store_api import StoreAPIError, get_api_client


@admin_bp.route("/orders")
@permission_required("price_listing")
def orders():
    client = get_api_client()
    raw_orders = client.get("/orders/", params={"limit": 200})
    orders_list = [adapt_order(o) for o in raw_orders]
    # The catalogue behind the edit modal's "add a product" picker. Embedded with the
    # page rather than searched over the network per keystroke: the same 500-product
    # payload the admin Products page already loads, and the picker is a substring
    # match over it, so adding a line to an order costs no extra request.
    raw_products = client.get("/products/", params={"limit": 500})
    products_list = [
        {
            "id": p["id"],
            "product_name": p["product_name"],
            "product_code": p.get("product_code"),
            "uom": p.get("uom"),
            "price": p["price"],
        }
        for p in (adapt_product(p) for p in raw_products)
    ]
    return render_template("admin/orders.html", orders=orders_list, products=products_list)


@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@permission_required("price_listing")
def orders_status(order_id):
    new_status = request.form.get("status", "").strip()
    if not new_status:
        flash("Status is required.", "error")
        return redirect(url_for("admin.orders"))

    client = get_api_client()
    try:
        client.put_json(f"/orders/{order_id}", {"status": new_status})
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.orders"))

    flash("Order status updated.", "success")
    return redirect(url_for("admin.orders"))


@admin_bp.route("/orders/<int:order_id>/edit", methods=["POST"])
@permission_required("price_listing")
def orders_edit(order_id):
    """Saves the admin Orders page's edit modal. JSON in, JSON out - the modal stays
    open on failure and shows store-api's own message, which is the only place the
    rules actually live: a paid order is refused outright (409), a discount needs
    product_management, and every line is re-priced from the current Product/Promotion/
    Set row rather than from anything this request says.

    Only ids and quantities are forwarded for the items - deliberately never a price.
    Component lines ($0 bundle contents / free gifts) are filtered out client-side
    before they get here, because store-api regenerates them from the parent line."""
    body = request.get_json(silent=True) or {}

    payload = {
        field: body[field]
        for field in (
            "clinic_name",
            "contact_person",
            "phone",
            "address",
            "payment_term",
            "install_term",
            "discount_type",
            "discount_value",
            "status",
        )
        if field in body
    }
    items = body.get("items")
    if items is not None:
        if not items:
            return jsonify({"detail": "An order needs at least one item."}), 400
        # Whitelisted rather than interpolated: `kind` decides which id column the line
        # lands in, and store-api's OrderItemCreate requires exactly one of the three.
        kinds = {"product": "product_id", "promotion": "promotion_id", "set": "set_id"}
        try:
            payload["items"] = [
                {kinds[item.get("kind") or "product"]: item["id"], "qty": item["qty"]}
                for item in items
            ]
        except (KeyError, TypeError):
            return jsonify({"detail": "Malformed item list."}), 400

    client = get_api_client()
    try:
        order = client.put_json(f"/orders/{order_id}", payload)
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 400)

    return jsonify(adapt_order(order))


@admin_bp.route("/orders/<int:order_id>/mark-paid", methods=["POST"])
@permission_required("price_listing")
def orders_mark_paid(order_id):
    """Records that payment for this order has been received - cash over the counter,
    a bank transfer, or a KHQR payment automatic checking didn't catch. store-api
    stamps paid_at, fires the paid-order Telegram alert with the receipt attached, and
    from that moment the order is frozen: no more edits, no deletion.

    A customer sitting on the KHQR modal sees "paid" on its next poll and downloads
    their receipt; for a counter sale, staff print it from this page's Print button,
    which now says Receipt for any paid row."""
    client = get_api_client()
    try:
        client.put_json(f"/orders/{order_id}", {"payment_status": "paid"})
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.orders"))

    flash("Order marked as paid.", "success")
    return redirect(url_for("admin.orders"))


@admin_bp.route("/orders/<int:order_id>/khqr", methods=["POST"])
@permission_required("price_listing")
def orders_khqr(order_id):
    """Puts a payment QR on an existing order so the customer can scan it - the counter
    and phone-order case. Returns the whole order back, so the modal can draw the QR
    from khqr_string and show the amount it actually encodes."""
    client = get_api_client()
    try:
        order = client.post_json(f"/orders/{order_id}/khqr")
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 400)

    return jsonify(adapt_order(order))


@admin_bp.route("/orders/<int:order_id>/payment-status", methods=["GET"])
@permission_required("price_listing")
def orders_payment_status(order_id):
    """Polled by the staff QR dialog while the customer scans, exactly as the
    storefront's own KHQR modal polls /quote/<id>/payment-status. store-api does the
    Bakong/PayWay check, flips the order to paid on the first confirmed one, and fires
    the receipt alert."""
    client = get_api_client()
    try:
        result = client.get(f"/orders/{order_id}/payment-status")
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 400)

    return jsonify(result)


@admin_bp.route("/orders/<int:order_id>/delete", methods=["POST"])
@permission_required("price_listing")
def orders_delete(order_id):
    client = get_api_client()
    try:
        client.delete(f"/orders/{order_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.orders"))

    flash("Order deleted.", "success")
    return redirect(url_for("admin.orders"))
