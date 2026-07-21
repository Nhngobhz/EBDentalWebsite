from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp
from formatting import adapt_product
from store_api import StoreAPIError, get_api_client


def _file_from_request():
    file = request.files.get("file")
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


def _product_form_payload():
    payload = {
        "product_name": request.form.get("product_name", "").strip(),
        "description": request.form.get("description", "").strip() or None,
        "badge": request.form.get("badge", "").strip() or None,
        "product_type": request.form.get("product_type") or "single",
        "product_code": request.form.get("product_code", "").strip() or None,
        "uom": request.form.get("uom", "").strip() or None,
        "brand_id": request.form.get("brand_id", type=int),
        "category_id": request.form.get("category_id", type=int),
    }
    price = request.form.get("price", "").strip()
    discount = request.form.get("discount", "").strip()
    if price:
        payload["price"] = price
    if discount:
        payload["discount_type"] = request.form.get("discount_type") or "percent"
        payload["discount"] = discount
    return payload


@admin_bp.route("/products")
def products():
    client = get_api_client()
    raw_products = client.get("/products/", params={"limit": 500})
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
        payload["price"] = price
    if discount:
        payload["discount_type"] = request.form.get("discount_type") or "percent"
        payload["discount"] = discount

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
