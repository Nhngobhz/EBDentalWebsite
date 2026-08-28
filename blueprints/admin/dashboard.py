"""The admin landing screen.

It used to be three counters and a five-row table, all read off the sitewide context
globals - which meant it was the only screen in the panel that told a manager nothing
they couldn't see in the sidebar. This one answers the questions someone actually opens
the panel to ask: what came in, what is owed, what is unpaid, and where do I go next.

Everything here is defensive about store-api. A dashboard is the first page after
sign-in, and a dashboard that 500s because one of five fetches failed is worse than one
that renders with a card missing - so each block degrades on its own.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import render_template

from auth import has_permission
from blueprints.admin import admin_bp
from formatting import adapt_order, to_number
from store_api import StoreAPIError, get_api_client

# How far back "recent" reaches on the takings card. Thirty days is the window a
# monthly-target conversation happens in, and it is long enough that a quiet week
# doesn't read as a collapse.
RECENT_DAYS = 30

# How many orders the activity table lists. Eight fills the card beside the stat
# column without turning the landing page into the Orders screen, which is one click
# away and does the job properly.
RECENT_ORDER_COUNT = 8

# How many orders to pull for the figures. The counters are computed over this window
# rather than by asking store-api for aggregates, because there is no aggregate
# endpoint and adding one for a landing page would be the wrong order to do things in.
# 200 is the same page the Orders screen already fetches, so this costs nothing new.
ORDER_SCAN_LIMIT = 200


def _parse(value):
    """An ISO timestamp from store-api as an aware datetime, or None.

    Aware, always: these are compared against `now`, and one naive value in the mix
    turns the whole card into a TypeError.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _order_stats(orders, now):
    """The four figures on the takings row, in one pass over the orders.

    A quote is not a sale and is counted separately - see Order.order_type. "Paid"
    means payment_status, not status: an order can be delivered and still unpaid, and
    it is the unpaid ones a manager wants surfaced.
    """
    since = now - timedelta(days=RECENT_DAYS)

    stats = {
        "orders_total": 0,
        "quotes_total": 0,
        "recent_count": 0,
        "recent_value": 0.0,
        "paid_value": 0.0,
        "unpaid_count": 0,
        "unpaid_value": 0.0,
    }
    for order in orders:
        is_quote = order.get("order_type") == "quote"
        total = to_number(order.get("grand_total")) or 0
        created = _parse(order.get("created_at"))
        paid = order.get("payment_status") == "paid"
        cancelled = order.get("status") == "cancelled"

        if is_quote:
            stats["quotes_total"] += 1
        else:
            stats["orders_total"] += 1

        if created and created >= since:
            stats["recent_count"] += 1
            if not cancelled:
                stats["recent_value"] += total

        if paid:
            stats["paid_value"] += total
        elif not is_quote and not cancelled:
            # Unpaid quotes are not debts - nobody has agreed to buy one yet.
            stats["unpaid_count"] += 1
            stats["unpaid_value"] += total

    return stats


@admin_bp.route("/dashboard")
def dashboard():
    client = get_api_client()

    now = datetime.now(timezone.utc)
    orders, stats, recent_orders, status_counts = [], None, [], {}
    checkouts = []

    # Orders are money, so the whole block is gated on the same permission the Orders
    # screen is. A product_management-only staffer gets the catalogue half of this
    # page and none of the takings.
    if has_permission("price_listing") or has_permission("admin"):
        try:
            orders = [
                adapt_order(o)
                for o in client.get("/orders/", params={"limit": ORDER_SCAN_LIMIT})
            ]
        except StoreAPIError:
            orders = []
        stats = _order_stats(orders, now)
        # GET /orders/ is newest-first already; this is the head of it.
        recent_orders = orders[:RECENT_ORDER_COUNT]
        status_counts = Counter(o.get("status") or "pending" for o in orders)

        try:
            # Money that may be in flight: a customer was shown a QR and no order
            # exists yet. Normally empty for a moment; a row that persists is one
            # somebody has to look at, which is exactly why it belongs on this page.
            checkouts = client.get("/orders/checkouts")
        except StoreAPIError:
            checkouts = []

    # Live deals across BOTH shops. Its own fetch rather than the sitewide
    # `active_promotions` global: that one is scoped to the section the visitor is in
    # (site_section_name()), which for an admin means whichever storefront they last
    # looked at - so the tile would have counted machinery deals on Monday and
    # materials deals on Tuesday and been wrong on both days.
    try:
        live_promotions = len(
            client.get("/promotions/", params={"active_only": True, "section": "all", "limit": 200})
        )
    except StoreAPIError:
        live_promotions = 0

    catalog = {}
    try:
        # Counted through /products/count rather than by len()-ing a page: the
        # catalogue is past 8,000 rows and the biggest page store-api serves is 500,
        # so a length was a wrong number dressed as a fact.
        for key, section in (("machinery", "machinery"), ("materials", "materials")):
            catalog[key] = client.get(
                "/products/count", params={"section": section}
            ).get("count", 0)
    except StoreAPIError:
        catalog = {"machinery": 0, "materials": 0}

    customer_count = None
    if has_permission("customer_management"):
        try:
            # No count endpoint for customers; this is the same 200-row page the
            # Customers screen loads, so it is a floor rather than a total. Shown with
            # a "+" past the cap rather than as a confident number.
            customer_count = len(client.get("/customers/", params={"limit": 200}))
        except StoreAPIError:
            customer_count = None

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_orders=recent_orders,
        status_counts=status_counts,
        checkouts=checkouts,
        catalog=catalog,
        live_promotions=live_promotions,
        customer_count=customer_count,
        customer_cap=200,
        recent_days=RECENT_DAYS,
    )
