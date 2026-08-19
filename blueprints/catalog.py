from urllib.parse import urlencode

from flask import Blueprint, abort, render_template, request, url_for

from formatting import adapt_product, adapt_promotion, adapt_set, resolve_image_url
from special_products import SPECIAL_PRODUCTS, get_special_product
from store_api import StoreAPIError, get_api_client


catalog_bp = Blueprint("catalog", __name__)


@catalog_bp.route("/products")
def products_catalog():
    client = get_api_client()

    selected_brand = request.args.get("brand", type=int)
    selected_category = request.args.get("category", type=int)
    search_query = request.args.get("q", "").strip()

    brands = client.get("/brands/", params={"limit": 200})
    categories = client.get("/categories/", params={"limit": 500})

    params = {"limit": 500}
    if selected_brand:
        params["brand_id"] = selected_brand
    if selected_category:
        params["category_id"] = selected_category
    if search_query:
        params["q"] = search_query
    raw_products = client.get("/products/", params=params)
    products = [adapt_product(p) for p in raw_products]

    selected_brand_obj = next((b for b in brands if b["id"] == selected_brand), None)
    page_title = selected_brand_obj["brand_name"] if selected_brand_obj else "All Products"

    def catalog_url(**overrides):
        query = {"brand": selected_brand, "category": selected_category, "q": search_query or None}
        query.update(overrides)
        query = {k: v for k, v in query.items() if v not in (None, "")}
        base = url_for("catalog.products_catalog")
        return f"{base}?{urlencode(query)}" if query else base

    special_products = [
        {"slug": slug, **meta} for slug, meta in SPECIAL_PRODUCTS.items()
    ]

    return render_template(
        "products/catalog.html",
        products=products,
        brands=brands,
        categories=categories,
        selected_brand=selected_brand,
        selected_brand_obj=selected_brand_obj,
        selected_category=selected_category,
        search_query=search_query,
        page_title=page_title,
        catalog_url=catalog_url,
        special_products=special_products,
    )


@catalog_bp.route("/products/<int:product_id>")
def product_detail(product_id):
    client = get_api_client()
    try:
        raw_product = client.get(f"/products/{product_id}")
    except StoreAPIError as e:
        if e.status_code == 404:
            abort(404)
        raise
    product = adapt_product(raw_product)

    # Gift-only products are filtered out of the catalog listing by store-api, but
    # GET /products/{id} still serves them (the admin screens need it). Without
    # this, a stale or guessed link would reach a full product page - price, buy
    # box and all - for something store-api will refuse to put on an order.
    if not product.get("is_purchasable", True):
        abort(404)

    # ALL of the product's documents, not just the first. A product can carry a
    # user guide, a quick-start sheet and a service manual, each with its own
    # title (see Manual.title) - fetching one row silently hid the rest.
    manuals = client.get("/manuals/", params={"product_id": product_id, "limit": 50})
    # Only documents that actually have a file attached are worth listing - a
    # Manual row with no PDF yet would render as a download link to nothing.
    manuals = [m for m in manuals if m.get("pdf")]

    # The detail page's image gallery: the main picture first, then the extra photos
    # (store-api's ProductImage rows, which never repeat the main one). Resolved to
    # real URLs here rather than in the template, because the same list has to reach
    # both the markup and the page's JS.
    gallery = [resolve_image_url(product.get("product_image"))] + [
        resolve_image_url(extra.get("image")) for extra in product.get("images") or []
    ]

    # "More from this brand" strip at the foot of the page. Best-effort: a failure
    # here shouldn't take down the product page itself.
    related = []
    brand = product.get("brand")
    if brand:
        try:
            related = [
                adapt_product(p)
                for p in client.get("/products/", params={"brand_id": brand["id"], "limit": 12})
                if p["id"] != product_id
            ][:6]
        except StoreAPIError:
            related = []

    return render_template(
        "products/detail.html",
        product=product,
        manuals=manuals,
        gallery=gallery,
        related=related,
    )


@catalog_bp.route("/manuals")
def manuals():
    client = get_api_client()
    raw_manuals = client.get("/manuals/", params={"limit": 200})
    return render_template("main/manuals.html", manuals=raw_manuals)


@catalog_bp.route("/promotions")
def promotions_page():
    client = get_api_client()
    raw_promotions = client.get("/promotions/", params={"active_only": True, "limit": 200})
    promotions = [adapt_promotion(p) for p in raw_promotions]

    selected_brand = request.args.get("brand", type=int)

    # Every set is fetched, then filtered here rather than through store-api's
    # `brand_id` param, because the brand strip is built FROM this list: it
    # offers only brands that actually have a set, so no pill can ever lead to
    # an empty grid (unlike the catalog, where every brand has products). A
    # brand-filtered fetch couldn't see the brands it isn't filtering to.
    all_sets = [adapt_set(s) for s in client.get("/sets/", params={"limit": 200})]

    set_brands = sorted(
        {s["brand"]["id"]: s["brand"] for s in all_sets if s.get("brand")}.values(),
        key=lambda b: b["brand_name"].lower(),
    )
    sets = all_sets
    if selected_brand:
        sets = [s for s in all_sets if (s.get("brand") or {}).get("id") == selected_brand]

    def sets_url(brand):
        """Same page, different brand - anchored at #sets so clicking a pill
        lands back on the strip instead of the top of the Promotions page."""
        base = url_for("catalog.promotions_page")
        query = f"?{urlencode({'brand': brand})}" if brand else ""
        return f"{base}{query}#sets"

    return render_template(
        "main/promotions.html",
        promotions=promotions,
        sets=sets,
        set_brands=set_brands,
        selected_brand=selected_brand,
        sets_url=sets_url,
    )


def _bundle_detail(kind, path, adapt, name_field, image_field, extra_images=()):
    """Shared body of the promotion and set detail pages.

    A Promotion and a Set are the same thing to a shopper - a named bundle at a
    fixed price, containing products - and differ only in which columns hold the
    name/image and whether the deal has an end date. So both are normalized into
    one `bundle` dict here and rendered by one template, rather than keeping two
    near-identical pages in sync forever.
    """
    client = get_api_client()
    try:
        raw = client.get(path)
    except StoreAPIError as e:
        if e.status_code == 404:
            abort(404)
        raise
    item = adapt(raw)

    # Gallery, same shape as the product page's: main picture first, then any
    # secondary image the entity happens to have (only Set has one today).
    gallery = [resolve_image_url(item.get(image_field))]
    gallery += [
        resolve_image_url(item[field])
        for field in extra_images
        if item.get(field)
    ]

    return render_template(
        "products/bundle_detail.html",
        kind=kind,
        bundle=item,
        name=item.get(name_field),
        gallery=gallery,
        contents=item.get("items") or [],
        # Only a Set ever has these; a Promotion renders the page without them.
        option_groups=item.get("option_groups") or [],
    )


@catalog_bp.route("/promotions/<int:promotion_id>")
def promotion_detail(promotion_id):
    return _bundle_detail(
        "promotion",
        f"/promotions/{promotion_id}",
        adapt_promotion,
        "promotion_name",
        "promotion_image",
    )


@catalog_bp.route("/sets/<int:set_id>")
def set_detail(set_id):
    return _bundle_detail(
        "set",
        f"/sets/{set_id}",
        adapt_set,
        "set_name",
        "set_image",
        extra_images=("detail_image",),
    )

@catalog_bp.route("/products/special/<slug>")
def special_product(slug):
    """Manufacturer-spotlight product page - fully static, no store-api call.
    See special_products.py for how to add another one of these."""
    product = get_special_product(slug)
    if not product:
        abort(404)
    return render_template("products/special_detail.html", product=product)