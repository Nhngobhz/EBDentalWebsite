from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp
from formatting import adapt_order
from store_api import StoreAPIError, get_api_client


@admin_bp.route("/orders")
@permission_required("price_listing")
def orders():
    client = get_api_client()
    raw_orders = client.get("/orders/", params={"limit": 200})
    orders_list = [adapt_order(o) for o in raw_orders]
    return render_template("admin/orders.html", orders=orders_list)


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


@admin_bp.route("/orders/<int:order_id>/mark-paid", methods=["POST"])
@permission_required("price_listing")
def orders_mark_paid(order_id):
    """Manual fallback for confirming a KHQR payment when automatic Bakong checking
    isn't configured (no BAKONG_API_TOKEN) - store-api stamps paid_at, rejects it on
    non-KHQR rows, and fires the same paid-order Telegram alert the automatic check
    would. The customer's still-open payment modal then sees "paid" on its next poll
    and downloads the receipt."""
    client = get_api_client()
    try:
        client.put_json(f"/orders/{order_id}", {"payment_status": "paid"})
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.orders"))

    flash("Order marked as paid.", "success")
    return redirect(url_for("admin.orders"))


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
