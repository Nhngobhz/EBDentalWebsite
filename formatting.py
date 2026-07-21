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


def derive_old_price(price, discount):
    """Product only stores the final `price` + an integer `discount` percent - there is
    no absolute original price stored server-side (unlike Promotion, which keeps a real
    old_price). Reconstruct one for "was $X" display, only when there's an actual
    discount and price is a real (unmasked) number."""
    if not discount or price is None or is_masked(price):
        return None
    try:
        price = float(price)
    except (TypeError, ValueError):
        return None
    if discount >= 100:
        return None
    return price / (1 - discount / 100)


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
    product["was_price"] = derive_old_price(product["price"], product.get("discount"))
    return product


def adapt_promotion(promotion):
    promotion = dict(promotion)
    promotion["price"] = to_number(promotion.get("price"))
    promotion["old_price"] = to_number(promotion.get("old_price"))
    return promotion


def adapt_order(order):
    order = dict(order)
    order["cash_discount"] = to_number(order.get("cash_discount"))
    order["subtotal"] = to_number(order.get("subtotal"))
    order["grand_total"] = to_number(order.get("grand_total"))
    order["items"] = [
        {
            **item,
            "unit_price": to_number(item.get("unit_price")),
            "line_amount": to_number(item.get("line_amount")),
        }
        for item in order.get("items", [])
    ]
    return order
