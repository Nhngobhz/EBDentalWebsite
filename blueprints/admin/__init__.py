from flask import Blueprint, request

from auth import staff_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def bundle_items_from_form(field="item_product_id", qty_field="item_qty"):
    """Reads the repeatable "included products" picker (ebBundlePicker in
    main.js) off a submitted admin form into store-api's
    [{product_id, qty}] shape - used by the Promotion/Set contents lists and the
    Product "comes with free" list, which all post the same pair of parallel
    inputs.

    Always returns a list, never None: the picker renders one hidden empty row
    when a bundle has no contents, and an admin clearing every row must send an
    empty list (store-api reads "field present but empty" as "remove all") rather
    than omitting the field (which means "leave contents alone")."""
    product_ids = request.form.getlist(field)
    quantities = request.form.getlist(qty_field)
    items = []
    for i, product_id in enumerate(product_ids):
        product_id = (product_id or "").strip()
        if not product_id:
            continue  # the picker's blank template row
        qty = (quantities[i] if i < len(quantities) else "").strip()
        items.append({"product_id": int(product_id), "qty": int(qty or 1)})
    return items


def product_facet_counts(client, facet):
    """How many products sit behind each brand (or category), keyed by id.

    One GROUP BY on store-api (GET /products/facets) rather than a page of
    products counted here. The page-counting version was wrong twice over on a
    catalogue this size: `limit` is capped at 500, so it only ever saw the first
    500 rows of 9,000, and the brands screen additionally never passed `section`,
    which defaults to "machinery" - so every one of the 186 brands that sells only
    materials or spare parts showed 0.

    Counts EVERYTHING assigned to the brand/category, not what a shopper can see:
    gift-only products (include_unpurchasable) and items SAP has withdrawn
    (include_delisted) are still rows pointing at it, and are exactly what makes a
    delete come back "cannot delete a brand that still has products assigned to
    it". A column that says 0 next to a delete that then refuses is worse than a
    number that includes rows the storefront hides.
    """
    buckets = client.get(
        "/products/facets",
        params={
            "section": "all",
            "include_unpurchasable": "true",
            "include_delisted": "true",
        },
    )[facet]
    return {b["id"]: b["count"] for b in buckets}


@admin_bp.before_request
@staff_required
def _require_staff():
    """Applies to every route registered on this blueprint - fixes the original
    mock's complete lack of auth gating on any /admin/* route. Non-staff get a 404
    (see staff_required's docstring), not a login redirect, so /admin/* doesn't
    announce itself to strangers. Per-route permission_required(...) layers stricter
    checks on top where store-api itself demands more than just "is staff" (see each
    submodule)."""
    return None


# Imported after admin_bp exists (and after the before_request above is registered)
# so each submodule's `from blueprints.admin import admin_bp` / `@admin_bp.route(...)`
# attaches routes to this same blueprint instance.
from blueprints.admin import (  # noqa: E402
    activity,
    brands,
    categories,
    customers,
    dashboard,
    hero_slides,
    manuals,
    orders,
    products,
    promotions,
    qr_codes,
    reports,
    sets,
    settings,
    users,
)
