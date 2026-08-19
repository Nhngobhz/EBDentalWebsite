from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp, bundle_items_from_form
from formatting import adapt_product
from store_api import StoreAPIError, get_api_client


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


@admin_bp.route("/products")
def products():
    client = get_api_client()
    # include_unpurchasable: the admin table is the one place gift-only products
    # have to stay visible - it's where they're created, edited and picked from
    # when building another product's free-item list.
    raw_products = client.get(
        "/products/", params={"limit": 500, "include_unpurchasable": "true"}
    )
    products_list = [adapt_product(p) for p in raw_products]
    brands = client.get("/brands/", params={"limit": 200})
    categories = client.get("/categories/", params={"limit": 500})
    return render_template("admin/products.html", products=products_list, brands=brands, categories=categories)


@admin_bp.route("/products/new", methods=["POST"])
@permission_required("product_management")
def products_new():
    payload = _product_form_payload()
    if not payload["product_name"] or not payload.get("price") or not payload["brand_id"]:
        flash("Name, price, and brand are required.", "error")
        return redirect(url_for("admin.products"))

    client = get_api_client()
    try:
        created = client.post_json("/products/", payload)
        files = _file_from_request()
        if files:
            client.post_form(f"/products/{created['id']}/image", files=files)
        _upload_gallery(client, created["id"])
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.products"))

    flash(f"Product '{payload['product_name']}' created.", "success")
    return redirect(url_for("admin.products"))


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
        return redirect(url_for("admin.products"))

    flash("Product updated.", "success")
    return redirect(url_for("admin.products"))


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
        return redirect(url_for("admin.products"))

    flash("Price updated.", "success")
    return redirect(url_for("admin.products"))


@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@permission_required("product_management")
def products_delete(product_id):
    client = get_api_client()
    try:
        client.delete(f"/products/{product_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("admin.products"))

    flash("Product deleted.", "success")
    return redirect(url_for("admin.products"))
