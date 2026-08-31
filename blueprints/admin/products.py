from urllib.parse import urlencode

from flask import flash, jsonify, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp, bundle_items_from_form
from formatting import adapt_product, to_number
from store_api import StoreAPIError, get_api_client


def _back():
    """The list as the staffer had it - their search, section, sort and page.

    Every write posts these four back as hidden inputs, because a bare redirect to
    /admin/products would drop them onto page 1 of an unfiltered 8,000-row table after
    every single save.

    Rebuilt from named fields rather than by echoing a submitted query string: the
    destination is always url_for("admin.products") with a query made of four keys this
    function chose, so there is nothing here an attacker can steer - not the path, not
    the header. `page` is coerced through int() for the same reason.

    The fields are read under an `rt_` prefix and written out unprefixed. That is not
    cosmetic: the edit modal posts its own `section` - the shop the PRODUCT is in - into
    the same flat form body, and `request.form.get("section")` returns whichever comes
    first in the document. Sharing the name meant editing a machinery product from a
    Materials-filtered table moved it into the other shop."""
    query = {}
    for key in ("q", "section", "sort"):
        value = (request.form.get(f"rt_{key}") or "").strip()
        if value:
            query[key] = value
    try:
        page = int(request.form.get("rt_page") or 1)
    except ValueError:
        page = 1
    if page > 1:
        query["page"] = page

    base = url_for("admin.products")
    return f"{base}?{urlencode(query)}" if query else base


def _file_from_request():
    file = request.files.get("file")
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


def _gallery_files_from_request():
    """The extra product-page photos, as the repeated-field list store-api's
    POST /products/{id}/gallery expects (a list of tuples rather than a dict,
    since every one of them is sent under the same field name)."""
    return [
        ("files", (f.filename, f.stream, f.mimetype))
        for f in request.files.getlist("gallery")
        if f and f.filename
    ]


def _upload_gallery(client, product_id):
    files = _gallery_files_from_request()
    if files:
        client.post_form(f"/products/{product_id}/gallery", files=files)


def _delete_removed_gallery_images(client, product_id):
    """Gallery photos the admin X'd out in the modal. They arrive as hidden
    inputs on the same form as everything else (a nested <form> per thumbnail
    isn't valid HTML), so the removal happens here rather than through a
    dedicated route."""
    for image_id in request.form.getlist("remove_gallery_ids"):
        if image_id.isdigit():
            client.delete(f"/products/{product_id}/gallery/{image_id}")


def _apply_discount(price, discount, discount_type):
    """The Price field the admin fills in is the original (pre-discount) price, so the
    discounted figure store-api charges has to be computed from it here.

    Both numbers are now sent explicitly - the typed figure as `list_price`, this
    computed one as `price` - so store-api stores the original rather than inferring
    it later. It used to be sent as `price` alone, leaving the "was $X" to be
    reconstructed by division on every read (see store-api's f2a9c4e18b73)."""
    try:
        p = float(price)
        d = float(discount)
    except (TypeError, ValueError):
        return price
    if discount_type == "cash":
        final = p - d
    elif d < 100:
        final = p * (1 - d / 100)
    else:
        final = p
    return f"{max(final, 0.01):.2f}"


def _product_form_payload():
    payload = {
        "product_name": request.form.get("product_name", "").strip(),
        "description": request.form.get("description", "").strip() or None,
        "badge": request.form.get("badge", "").strip() or None,
        "product_code": request.form.get("product_code", "").strip() or None,
        "uom": request.form.get("uom", "").strip() or None,
        "brand_id": request.form.get("brand_id", type=int),
        "category_id": request.form.get("category_id", type=int),
        # An unticked checkbox sends nothing at all, so this can't use the
        # "blank means leave alone" pattern the optional text fields use - absent
        # genuinely means False here, and the key is always sent so unticking it
        # actually clears the flag.
        "is_purchasable": "is_purchasable" in request.form,
        # Always sent, never "blank means leave alone": a product belongs to exactly
        # one half of the storefront and the select always posts one of the two.
        "section": request.form.get("section") or "machinery",
        # Other products this one comes with for free - each lands on the quote
        # as a $0 line under this product (store-api's create_order expands them).
        "free_items": bundle_items_from_form(),
    }
    price = request.form.get("price", "").strip()
    discount = request.form.get("discount", "").strip()
    if price:
        # The typed figure IS the list price; with no discount the two are equal.
        payload["list_price"] = price
        payload["price"] = price
    if discount:
        discount_type = request.form.get("discount_type") or "percent"
        payload["discount_type"] = discount_type
        payload["discount"] = discount
        if price:
            payload["price"] = _apply_discount(price, discount, discount_type)
    return payload


# How many rows one page of the admin table holds. Fifty is about as much as anyone
# scans without reaching for the search box, and it keeps the page's <script> blob
# (PRODUCTS_DATA, which carries every column the edit modal seeds from) small.
PAGE_SIZE = 50

# How many numbered page links to show at once - 8,125 materials is 163 pages, and
# rendering one link each would be longer than the table.
PAGE_WINDOW = 7

# What the sortable column headers offer, as {value: (label, opposite)}. The third
# element is what clicking an already-sorted column switches to, which is what makes a
# header a toggle rather than a one-way trip.
SORTS = {
    "name": ("Name", "name_desc"),
    "name_desc": ("Name", "name"),
    "price_asc": ("Price", "price_desc"),
    "price_desc": ("Price", "price_asc"),
    "stock_asc": ("Stock", "stock_desc"),
    "stock_desc": ("Stock", "stock_asc"),
    "newest": ("Added", "oldest"),
    "oldest": ("Added", "newest"),
}
DEFAULT_SORT = "name"

SECTIONS = ("all", "machinery", "spare_parts", "materials")


@admin_bp.route("/products")
def products():
    """The catalogue table: server-paged, searched and sorted.

    It used to fetch `limit=500` and filter/sort in the browser. That was right while
    the catalogue was ~110 machinery products; the SAP import took it past 8,000, at
    which point the screen was showing the first 500 alphabetically with no sign that
    it was doing so - a product beginning with "T" simply did not exist as far as this
    page was concerned, and its search box could not find it either.

    So the four controls all go to the server now: `q`, `section`, `sort`, `page`. The
    trade is one round trip per keystroke-that-you-submit instead of instant filtering
    over a partial list, and a partial list is the thing that made the old behaviour
    wrong rather than merely slow.

    include_unpurchasable: the admin table is the one place gift-only products have to
    stay visible - it's where they're created, edited and picked from when building
    another product's free-item list.

    include_delisted: products SAP has withdrawn are hidden from the storefront, but
    this table is where staff go to find out what happened to one - and they are still
    real rows, still on past orders, still editable.

    section defaults to "all" here for the same reason include_unpurchasable is true:
    this table is the one screen that has to be able to show every row regardless of
    which half of the storefront it belongs to. GET /products/ defaults to machinery on
    purpose, so spanning both is always a deliberate opt-in - see SectionFilter in
    schemas.py.
    """
    client = get_api_client()

    search_query = request.args.get("q", "").strip()
    section = request.args.get("section", "all")
    if section not in SECTIONS:
        section = "all"
    sort = request.args.get("sort", DEFAULT_SORT)
    if sort not in SORTS:
        sort = DEFAULT_SORT
    page = max(1, request.args.get("page", 1, type=int))

    filters = {
        "section": section,
        "include_unpurchasable": "true",
        "include_delisted": "true",
    }
    if search_query:
        filters["q"] = search_query

    total = client.get("/products/count", params=filters).get("count", 0)
    total_pages = max(1, -(-total // PAGE_SIZE))
    # A ?page= past the end - a stale bookmark, or a search that has since narrowed -
    # lands on the last real page rather than on an empty table.
    page = min(page, total_pages)

    raw_products = client.get(
        "/products/",
        params={**filters, "sort": sort, "skip": (page - 1) * PAGE_SIZE, "limit": PAGE_SIZE},
    )
    products_list = [adapt_product(p) for p in raw_products]

    brands = client.get("/brands/", params={"limit": 200})
    categories = client.get_all("/categories/")

    def products_url(**overrides):
        query = {
            "q": search_query or None,
            "section": section if section != "all" else None,
            "sort": sort if sort != DEFAULT_SORT else None,
            "page": page if page > 1 else None,
        }
        query.update(overrides)
        query = {k: v for k, v in query.items() if v not in (None, "", [])}
        base = url_for("admin.products")
        return f"{base}?{urlencode(query)}" if query else base

    def sort_url(value):
        """Sorted by `value`, back to page 1 - a new ordering means page 4 holds
        different rows. Clicking the column you are already sorted by flips it."""
        target = SORTS[sort][1] if SORTS[value][0] == SORTS[sort][0] else value
        return products_url(page=None, sort=target if target != DEFAULT_SORT else None)

    def filter_url(**overrides):
        return products_url(page=None, **overrides)

    def page_url(target):
        return products_url(page=target if target > 1 else None)

    # A window that stays PAGE_WINDOW wide at both ends instead of collapsing to three
    # links on page 1 - clamping only the start would do that.
    half = PAGE_WINDOW // 2
    start = max(1, min(page - half, total_pages - PAGE_WINDOW + 1))
    page_numbers = list(range(start, min(total_pages, start + PAGE_WINDOW - 1) + 1))

    return render_template(
        "admin/products.html",
        products=products_list,
        brands=brands,
        categories=categories,
        search_query=search_query,
        section=section,
        sort=sort,
        sorts=SORTS,
        total=total,
        page=page,
        total_pages=total_pages,
        page_numbers=page_numbers,
        page_size=PAGE_SIZE,
        sort_url=sort_url,
        filter_url=filter_url,
        page_url=page_url,
    )


# How many matches one picker search hands back. Small on purpose: this is a
# type-to-narrow list you read at a glance, not a page of the catalogue. One extra
# row is fetched beyond it purely to know whether to say "keep typing".
SEARCH_LIMIT = 25

# The ceiling on the `ids` lookup, which resolves ids a bundle already holds into
# names and prices. Each id is a separate store-api call, and no bundle on this site
# is anywhere near this long - it is a bound on a URL a browser composes, not a
# feature.
MAX_LOOKUP_IDS = 40


def _picker_row(product):
    """One product as the bundle picker needs it: enough to recognise it by and to
    price an upgrade with, and nothing else. `price` comes through to_number, so a
    staffer without price access gets the masked sentinel rather than a real figure -
    the picker just shows no price then."""
    return {
        "id": product["id"],
        "product_name": product["product_name"],
        "product_code": product.get("product_code"),
        "uom": product.get("uom"),
        "section": product.get("section") or "machinery",
        "price": to_number(product.get("price")),
    }


@admin_bp.route("/products/search")
@permission_required("product_management")
def products_search():
    """The catalogue behind every admin bundle picker, searched one query at a time.

    The pickers used to be <select>s filled from a single `limit=500` fetch embedded
    in the page. That was fine at ~110 machinery products and became wrong the moment
    the SAP import landed: 500 of 8,000+ rows alphabetically means the list opens on
    materials whose names begin with a quote character, and no machinery product is
    reachable at all - which is exactly what the "Comes With (Free)" picker was
    showing.

    Two modes, one route:
      ?q=&section=   the search itself - what the admin types.
      ?ids=1,2,3     resolve ids a bundle already holds into names/prices, so an
                     existing row renders as the product it is rather than as a
                     number. An id that no longer exists is skipped rather than
                     failing the lookup - a product can be deleted out from under a
                     bundle that still lists it.

    include_unpurchasable: gift-only products exist to be put in these lists, so the
    one picker that must offer them is this one. Delisted products stay out of the
    search (nothing new should be built out of a withdrawn item) but are still
    resolved by id, since one may already be in the bundle being edited.
    """
    client = get_api_client()

    ids = request.args.get("ids", "")
    if ids:
        products = []
        for raw in ids.split(",")[:MAX_LOOKUP_IDS]:
            raw = raw.strip()
            if not raw.isdigit():
                continue
            try:
                products.append(client.get(f"/products/{int(raw)}"))
            except StoreAPIError:
                continue
        return jsonify({"products": [_picker_row(p) for p in products], "more": False})

    section = request.args.get("section", "all")
    if section not in SECTIONS:
        section = "all"
    rows = client.get(
        "/products/",
        params={
            "q": request.args.get("q", "").strip() or None,
            "section": section,
            "include_unpurchasable": "true",
            "sort": "name",
            "limit": SEARCH_LIMIT + 1,
        },
    )
    return jsonify({
        "products": [_picker_row(p) for p in rows[:SEARCH_LIMIT]],
        "more": len(rows) > SEARCH_LIMIT,
    })


@admin_bp.route("/products/new", methods=["POST"])
@permission_required("product_management")
def products_new():
    payload = _product_form_payload()
    if not payload["product_name"] or not payload.get("price") or not payload["brand_id"]:
        flash("Name, price, and brand are required.", "error")
        return redirect(_back())

    client = get_api_client()
    try:
        created = client.post_json("/products/", payload)
        files = _file_from_request()
        if files:
            client.post_form(f"/products/{created['id']}/image", files=files)
        _upload_gallery(client, created["id"])
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(_back())

    flash(f"Product '{payload['product_name']}' created.", "success")
    return redirect(_back())


@admin_bp.route("/products/<int:product_id>/edit", methods=["POST"])
@permission_required("product_management")
def products_edit(product_id):
    payload = _product_form_payload()
    client = get_api_client()
    try:
        client.put_json(f"/products/{product_id}", payload)
        files = _file_from_request()
        if files:
            client.post_form(f"/products/{product_id}/image", files=files)
        _delete_removed_gallery_images(client, product_id)
        _upload_gallery(client, product_id)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(_back())

    flash("Product updated.", "success")
    return redirect(_back())


@admin_bp.route("/products/<int:product_id>/price", methods=["POST"])
@permission_required("price_listing")
def products_price(product_id):
    """Dedicated quick-price action for a price_listing-only staffer who lacks
    product_management (see store-api's PATCH /products/{id}/price - the general PUT
    route requires both permissions to touch price/discount)."""
    payload = {}
    price = request.form.get("price", "").strip()
    discount = request.form.get("discount", "").strip()
    if price:
        payload["list_price"] = price
        payload["price"] = price
    if discount:
        discount_type = request.form.get("discount_type") or "percent"
        payload["discount_type"] = discount_type
        payload["discount"] = discount
        if price:
            payload["price"] = _apply_discount(price, discount, discount_type)

    client = get_api_client()
    try:
        client.patch_json(f"/products/{product_id}/price", payload)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(_back())

    flash("Price updated.", "success")
    return redirect(_back())


@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@permission_required("product_management")
def products_delete(product_id):
    client = get_api_client()
    try:
        client.delete(f"/products/{product_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(_back())

    flash("Product deleted.", "success")
    return redirect(_back())
