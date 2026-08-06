"""
Shared Jinja globals and small data-shaping helpers used across every blueprint.

IMPORTANT, discovered while wiring this up against the live store-api: Decimal fields
(price, old_price, subtotal, unit_price, ...) are serialized as JSON *strings*
(e.g. "209.00"), not JSON numbers - confirmed empirically against the running API, not
assumed. The masked-price sentinel ("XXXX") is also a string, so a real price cannot be
told apart from the sentinel by type alone. `to_number()` is the one place that
distinction is made; everything downstream (Jinja, JS `|tojson` blobs) should only ever
see a real float, the literal "XXXX", or None - never a numeric-looking string.
"""
from datetime import datetime

from flask import current_app, url_for

MASKED_PRICE = "XXXX"


def resolve_image_url(path):
    """
    Turn any *_image field store-api returns into a URL the browser can load:
      - Full http(s) URL (Cloudflare R2, or anything else already fully-qualified)
        -> used as-is.
      - A store-api-relative local-disk path ("/static/uploads/...", store-api's own
        fallback when R2 isn't configured) -> prefixed with store-api's own base URL,
        since that path is served BY store-api on its own port, not by this Flask app.
      - Missing/None -> this app's own 404 placeholder image.

    This is the ONLY place image-URL logic should live - exposed to Jinja as img().
    """
    if path and (path.startswith("http://") or path.startswith("https://")):
        return path
    if path and path.startswith("/"):
        base = current_app.config["STORE_API_BASE_URL"].rstrip("/")
        return f"{base}{path}"
    return url_for("static", filename="images/404 no image.png")


def resolve_file_url(path):
    """Same store-api-relative-vs-absolute logic as resolve_image_url(), for non-image
    files (manual PDFs) that have no local placeholder to fall back to - if there's no
    path, the caller should just not render a link at all."""
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if path.startswith("/"):
        base = current_app.config["STORE_API_BASE_URL"].rstrip("/")
        return f"{base}{path}"
    return path


def is_masked(value):
    return value == MASKED_PRICE


def to_number(value):
    """Coerce a store-api numeric-as-string field to a real float, leaving the masked
    sentinel (or None) untouched - see module docstring."""
    if value is None or is_masked(value):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def format_price(value):
    """Safe to call on anything to_number() may have produced: a real number, the
    masked sentinel, or None. Exposed to Jinja as price()."""
    if value is None:
        return ""
    if is_masked(value):
        return "Login to view price"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return ""


def was_price(list_price, price):
    """The struck-through "was $X" to show next to a price, or None when there's
    nothing to strike through.

    store-api now stores `list_price` (the pre-discount price) outright. This used
    to be `derive_old_price()`, which reconstructed it here as
    `price / (1 - discount/100)` - and that made the "was" figure slide whenever
    the charged price was edited, since it was never a stored fact at all. See
    store-api's f2a9c4e18b73 migration.

    None is returned unless the list price genuinely exceeds what's being charged,
    so an undiscounted product doesn't render a strikethrough of its own price, and
    a viewer without price access (whose `list_price` comes back masked to None)
    gets nothing."""
    if list_price is None or price is None or is_masked(price) or is_masked(list_price):
        return None
    try:
        if float(list_price) > float(price):
            return float(list_price)
    except (TypeError, ValueError):
        return None
    return None


def format_date(value, fmt="%b %d, %Y"):
    """store-api returns ISO 8601 datetimes as strings once JSON-decoded."""
    if not value:
        return ""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.strftime(fmt)


# ---- per-entity adapters: run once on every dict fetched from store-api, before it
# reaches a template, so downstream code never has to think about the string-Decimal
# quirk or recompute a derived field more than once. ----

def adapt_product(product):
    product = dict(product)
    product["price"] = to_number(product.get("price"))
    product["discount"] = to_number(product.get("discount"))
    product["list_price"] = to_number(product.get("list_price"))
    product["was_price"] = was_price(product["list_price"], product["price"])
    # Products this one comes with for free. Carries no prices of its own (name /
    # code / uom / qty only - see BundleItemOut in store-api), so unlike every
    # other field here it needs no numeric coercion, just a guaranteed list.
    product["free_items"] = list(product.get("free_items") or [])
    return product


def adapt_promotion(promotion):
    promotion = dict(promotion)
    promotion["price"] = to_number(promotion.get("price"))
    promotion["old_price"] = to_number(promotion.get("old_price"))
    # The member products of the deal - same price-free shape as
    # adapt_product's free_items.
    promotion["items"] = list(promotion.get("items") or [])
    return promotion


def adapt_set(set_):
    set_ = dict(set_)
    set_["price"] = to_number(set_.get("price"))
    set_["old_price"] = to_number(set_.get("old_price"))
    set_["items"] = list(set_.get("items") or [])
    return set_


def adapt_order(order):
    order = dict(order)
    order["discount_value"] = to_number(order.get("discount_value"))
    order["discount_amount"] = to_number(order.get("discount_amount"))
    order["subtotal"] = to_number(order.get("subtotal"))
    order["grand_total"] = to_number(order.get("grand_total"))
    order["items"] = [
        {
            **item,
            "unit_price": to_number(item.get("unit_price")),
            "discount": to_number(item.get("discount")),
            "line_amount": to_number(item.get("line_amount")),
        }
        for item in order.get("items", [])
    ]
    return order
