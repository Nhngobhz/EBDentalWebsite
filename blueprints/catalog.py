from collections import Counter
from urllib.parse import urlencode

import site_cache
import site_section
from flask import Blueprint, abort, redirect, render_template, request, url_for

from formatting import adapt_product, adapt_promotion, adapt_set, resolve_image_url
from special_products import SPECIAL_PRODUCTS, get_special_product
from store_api import StoreAPIError, get_api_client


catalog_bp = Blueprint("catalog", __name__)


def section_brands(section):
    """The brands that actually have products in one half of the store.

    NOT `GET /brands/`. That endpoint returns every brand in the database with no
    idea which section each belongs to, and since the SAP import there are 175 of
    them - 173 with only materials behind them. A machinery brand strip built from
    it listed all 175, each one a card with a "404 no image" placeholder leading to
    an empty grid, because a materials brand has no machinery to show.

    Shaped like `GET /brands/` (`brand_name`, `brand_image`) rather than like the
    facet buckets it is built from, so the strip, the grid and the footer that
    render brands all keep reading the same field names. Ordered biggest range
    first, which is what the facet gives.

    Cached per section: it is on the machinery home page, the machinery catalog and
    every footer on the site, and it only moves when the catalogue does.
    """
    def fetch():
        buckets = get_api_client().get(
            "/products/facets", params={"section": section}
        )["brands"]
        return [
            {
                "id": b["id"],
                "brand_name": b["name"],
                "brand_image": b["image"],
                "product_count": b["count"],
            }
            for b in buckets
        ]

    return site_cache.cached(("section_brands", section), fetch)


@catalog_bp.route("/products")
def products_catalog():
    client = get_api_client()

    selected_brand = request.args.get("brand", type=int)
    # Categories are multi-select: the standing filter panel on the left is a list
    # of checkboxes, and the text strip across the top toggles the same set, so the
    # parameter repeats - "?category=8&category=19". A one-category link from an
    # older bookmark still arrives here as a single-element list.
    selected_categories = request.args.getlist("category", type=int)
    search_query = request.args.get("q", "").strip()

    brands = section_brands("machinery")
    categories = client.get_all("/categories/")

    # Note what is NOT sent: `category_id`. store-api filters on one category at a
    # time (see routers/products.py::list_products), which can't express "Endo Motor
    # OR Apex Locator", so the category cut happens here instead - over the
    # brand/search-filtered set, which is small enough (`limit` covers the whole
    # catalog) that a second pass in Python is free.
    params = {"limit": 500}
    if selected_brand:
        params["brand_id"] = selected_brand
    if search_query:
        params["q"] = search_query
    raw_products = client.get("/products/", params=params)
    products = [adapt_product(p) for p in raw_products]

    # How many products sit in each category *within the current brand/search
    # context*, counted before the category cut below - so the number beside a
    # checkbox says what ticking it would actually yield, and a category that could
    # only ever produce an empty grid can be left out of the panel entirely.
    category_counts = Counter(
        p["category"]["id"] for p in products if p.get("category")
    )

    if selected_categories:
        wanted = set(selected_categories)
        products = [
            p for p in products if (p.get("category") or {}).get("id") in wanted
        ]

    # A checked category is always listed even when nothing matches it here (a
    # brand switch can empty it) - otherwise its box would disappear along with the
    # only way to untick it.
    visible_categories = [
        c
        for c in categories
        if category_counts.get(c["id"]) or c["id"] in set(selected_categories)
    ]

    # Sets share the grid with products now, as cards of their own. A Set has a
    # brand and a name, so it follows the brand strip and the search box, but it has
    # no category at all (see store-api's Set model - deliberately, a bundle spans
    # categories), which is why any category selection hides them rather than
    # showing bundles the ticked boxes don't describe.
    sets = []
    if not selected_categories:
        sets = [adapt_set(s) for s in client.get("/sets/", params={"limit": 200})]
        if selected_brand:
            sets = [s for s in sets if (s.get("brand") or {}).get("id") == selected_brand]
        if search_query:
            needle = search_query.lower()
            sets = [s for s in sets if needle in (s.get("set_name") or "").lower()]

    selected_brand_obj = next((b for b in brands if b["id"] == selected_brand), None)
    if selected_brand_obj:
        page_title = selected_brand_obj["brand_name"]
    elif len(selected_categories) == 1:
        # One category ticked reads as browsing that category, so name it. Two or
        # more have no single honest heading.
        only = next((c for c in categories if c["id"] == selected_categories[0]), None)
        page_title = only["category_name"] if only else "All Products"
    else:
        page_title = "All Products"

    def catalog_url(**overrides):
        # doseq, because `category` is a list - urlencode would otherwise write the
        # repr of the list ("%5B8%2C+19%5D") as one value.
        query = {
            "brand": selected_brand,
            "category": selected_categories,
            "q": search_query or None,
        }
        query.update(overrides)
        query = {k: v for k, v in query.items() if v not in (None, "", [])}
        base = url_for("catalog.products_catalog")
        return f"{base}?{urlencode(query, doseq=True)}" if query else base

    def category_toggle_url(category_id):
        """This page with `category_id` added to, or removed from, the ticked set.

        Both the text strip and the checkbox panel point at this, so the two
        controls can't drift apart: a link in the strip is the same action as the
        box beside that name."""
        current = list(selected_categories)
        if category_id in current:
            current.remove(category_id)
        else:
            current.append(category_id)
        return catalog_url(category=current)

    special_products = [
        {"slug": slug, **meta} for slug, meta in SPECIAL_PRODUCTS.items()
    ]

    return render_template(
        "products/catalog.html",
        products=products,
        sets=sets,
        brands=brands,
        categories=visible_categories,
        category_counts=category_counts,
        selected_brand=selected_brand,
        selected_brand_obj=selected_brand_obj,
        selected_categories=selected_categories,
        search_query=search_query,
        page_title=page_title,
        catalog_url=catalog_url,
        category_toggle_url=category_toggle_url,
        special_products=special_products,
    )


def detail_context(product_id, section, related_by="brand"):
    """Everything a product page needs, or a redirect to the other half.

    Shared by /products/<id> and /materials/<id> (blueprints/materials.py) even
    though the two now render different templates: what differs between them is
    presentation, and everything here - the two guards, the gallery, the manuals,
    the related strip - is the same question asked of the same row.

    Returning a redirect rather than a 404 when the sections disagree keeps every
    link that predates the split alive: /products/<a materials id> is a real
    product, just filed on the other side.

    `related_by` picks what the "more like this" strip at the foot is drawn from.
    Machinery groups by brand, which is how that catalog is browsed. Materials
    groups by category, because a fifth of it is filed under the "Unbranded"
    fallback the SAP import invents for items with no U_Brand - "more from
    Unbranded" is 1,671 unrelated consumables, while "more Diamond Burs" is the
    shelf the shopper is standing at.
    """
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

    # Same reasoning one step further: SAP has withdrawn this item, so the catalog
    # listing already excludes it, but GET /products/{id} still serves it for the
    # admin screens. Without this a bookmark or a search-engine result would reach
    # a full buy box for something the business no longer sells.
    if product.get("delisted_at"):
        abort(404)

    if product["section"] != section:
        other = "materials.detail" if product["section"] == "materials" \
            else "catalog.product_detail"
        return redirect(url_for(other, product_id=product_id))

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

    # The "more like this" strip at the foot of the page. Best-effort: a failure
    # here shouldn't take down the product page itself.
    related = []
    group = product.get(related_by)
    if group:
        try:
            related = [
                adapt_product(p)
                for p in client.get(
                    "/products/",
                    # Kept inside the same half of the store: a strip on a materials
                    # page pointing at machinery would walk the shopper out of the
                    # catalog they are browsing, and several brands now carry both.
                    params={
                        f"{related_by}_id": group["id"],
                        "limit": 12,
                        "section": section,
                    },
                )
                if p["id"] != product_id
            ][:6]
        except StoreAPIError:
            related = []

    return {
        "product": product,
        "manuals": manuals,
        "gallery": gallery,
        "related": related,
        "related_group": group,
    }


@catalog_bp.route("/products/<int:product_id>")
def product_detail(product_id):
    context = detail_context(product_id, "machinery")
    if not isinstance(context, dict):
        return context
    return render_template("products/detail.html", **context)


@catalog_bp.route("/manuals")
def manuals():
    client = get_api_client()
    raw_manuals = client.get("/manuals/", params={"limit": 200})
    return render_template("main/manuals.html", manuals=raw_manuals)


@catalog_bp.route("/promotions")
def promotions_page():
    client = get_api_client()
    # section=machinery: this is the machinery shop's Promotions page (it also lists
    # Sets, which are machinery bundles). Materials deals are shown on the materials
    # front page instead - see blueprints/materials.py::home.
    raw_promotions = client.get(
        "/promotions/",
        params={"active_only": True, "section": "machinery", "limit": 200},
    )
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

    # A deal belongs to whichever shop advertises it, and this one URL serves both.
    # Without this, opening a materials promotion from the HOME 49 front page swapped
    # the header mark, the nav and the footer over to machinery - the shopper is put
    # in the other shop by clicking a deal that shop does not even sell. Sets have no
    # section of their own and stay machinery, which is what they are.
    site_section.override(item.get("section"))

    # Gallery, same shape as the product page's: main picture first, then any
    # secondary image the entity happens to have (only Set has one today).
    gallery = [resolve_image_url(item.get(image_field))]
    gallery += [
        resolve_image_url(item[field])
        for field in extra_images
        if item.get(field)
    ]

    # Only a Set ever has these; a Promotion renders the page without them.
    option_groups = item.get("option_groups") or []

    # An option slot takes over the included product its standard choice names -
    # it upgrades that item rather than adding a second one (the same rule
    # set_contents applies server-side when the order is priced). Filtering here
    # rather than in the template keeps ONE definition of "what's included",
    # which both the visible list and the cart payload below then read: without
    # it the page lists the standard x-ray under "What's included" AND offers it
    # as a radio, and the cart shows the machine you replaced next to its
    # replacement.
    claimed = {
        choice["product_id"]
        for group in option_groups
        for choice in (group.get("choices") or [])
        if choice.get("is_default")
    }
    contents = [
        entry for entry in (item.get("items") or [])
        if entry.get("product_id") not in claimed
    ]

    return render_template(
        "products/bundle_detail.html",
        kind=kind,
        bundle=item,
        name=item.get(name_field),
        gallery=gallery,
        contents=contents,
        option_groups=option_groups,
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