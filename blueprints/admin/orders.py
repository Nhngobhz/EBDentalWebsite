from flask import flash, jsonify, redirect, render_template, request, url_for

from auth import any_permission_required
from blueprints.admin import admin_bp
from formatting import adapt_order, adapt_product
from store_api import StoreAPIError, get_api_client

# Who may work the Orders screen: sales staff through `price_listing`, and the owner
# through `admin` (added 2026-08-17 - `admin` is "runs this store", not a job title, so
# it isn't implied by the other four flags and an owner holding only it was locked out
# of recording a payment). One name for the whole file so the two can't drift apart
# route by route. store-api enforces the same pair with require_any_permission.
ORDERS_PERMISSION = any_permission_required("price_listing", "admin")


@admin_bp.route("/orders")
@ORDERS_PERMISSION
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
    # Customers paying by QR have no order until the payment is confirmed, so an
    # attempt that automatic confirmation never saw would otherwise be invisible.
    # These are money-may-have-moved rows and render above the orders table.
    checkouts = client.get("/orders/checkouts")
    return render_template(
        "admin/orders.html",
        orders=orders_list,
        products=products_list,
        checkouts=checkouts,
    )


@admin_bp.route("/checkouts/<int:checkout_id>/confirm", methods=["POST"])
@ORDERS_PERMISSION
def checkouts_confirm(checkout_id):
    """Staff assert a KHQR payment arrived that automatic confirmation couldn't see,
    and store-api writes the order from the checkout's stored snapshot. Same trust
    model as "Mark as Paid" on an existing order - the person looking at the bank
    statement is the authority, and store-api records it against them."""
    client = get_api_client()
    try:
        order = client.post_json(f"/orders/checkout/{checkout_id}/confirm", {})
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.orders"))

    flash(f"Payment confirmed - order {order['order_number']} created.", "success")
    return redirect(url_for("admin.orders"))


@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@ORDERS_PERMISSION
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
@ORDERS_PERMISSION
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
                {
                    kinds[item.get("kind") or "product"]: item["id"],
                    "qty": item["qty"],
                    # Only a set line carries these. Rebuilt from ints rather than
                    # forwarded verbatim, same as the storefront's /quote/submit -
                    # store-api validates the ids themselves against the set.
                    **(
                        {"options": [
                            {"group_id": int(o["group_id"]), "choice_id": int(o["choice_id"])}
                            for o in (item.get("options") or [])
                        ]}
                        if (item.get("kind") == "set" and item.get("options"))
                        else {}
                    ),
                }
                for item in items
            ]
        except (KeyError, TypeError, ValueError):
            return jsonify({"detail": "Malformed item list."}), 400

    client = get_api_client()
    try:
        order = client.put_json(f"/orders/{order_id}", payload)
    except StoreAPIError as e:
        return jsonify({"detail": e.detail}), (e.status_code or 400)

    return jsonify(adapt_order(order))


@admin_bp.route("/orders/<int:order_id>/mark-paid", methods=["POST"])
@ORDERS_PERMISSION
def orders_mark_paid(order_id):
    """Records that payment for this order has been received - cash over the counter,
    a bank transfer, or a KHQR payment automatic checking didn't catch. store-api
    stamps paid_at, fires the paid-order Telegram alert with the receipt attached, and
    from that moment the order is frozen: no more edits, no deletion.

    A customer sitting on the KHQR modal sees "paid" on its next poll and downloads
    their receipt; for a counter sale, staff print it from this page's Print button,
    which now says Receipt for any paid row.

    Doubles as "Undo refund": posting payment_status="paid" over a refunded order puts
    the sale back and clears the reversal (store-api's update_order drops refunded_at
    and refund_reason with it), which is how a mis-clicked refund is taken back."""
    client = get_api_client()
    try:
        client.put_json(f"/orders/{order_id}", {"payment_status": "paid"})
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.orders"))

    flash("Order marked as paid.", "success")
    return redirect(url_for("admin.orders"))


@admin_bp.route("/orders/<int:order_id>/refund", methods=["POST"])
@ORDERS_PERMISSION
def orders_refund(order_id):
    """Records that the money for a paid order has been given back.

    Nothing here moves money - the refund itself is made at the bank or over the
    counter, exactly as the payment was. This writes it down, which is what takes the
    sale out of the takings totals and puts the reversal on the printed invoice.

    Gated the same way deleting a paid order is: the route allows anyone who can work
    the Orders screen, and store-api's refund_order 403s all but `admin`. The button is
    only rendered for an admin, so that 403 is a backstop rather than the normal path -
    the same pair of doors the Delete button already goes through.
    """
    reason = request.form.get("reason", "").strip()
    client = get_api_client()
    try:
        client.post_json(f"/orders/{order_id}/refund", {"reason": reason or None})
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.orders"))

    flash("Refund recorded - this order no longer counts as a sale.", "success")
    return redirect(url_for("admin.orders"))


@admin_bp.route("/orders/<int:order_id>/khqr", methods=["POST"])
@ORDERS_PERMISSION
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
@ORDERS_PERMISSION
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
@ORDERS_PERMISSION
def orders_delete(order_id):
    client = get_api_client()
    try:
        client.delete(f"/orders/{order_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.orders"))

    flash("Order deleted.", "success")
    return redirect(url_for("admin.orders"))
