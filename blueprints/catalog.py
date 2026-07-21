from urllib.parse import urlencode

from flask import Blueprint, abort, render_template, request, url_for

from formatting import adapt_product, adapt_promotion
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

    manuals = client.get("/manuals/", params={"product_id": product_id, "limit": 1})
    manual = manuals[0] if manuals else None

    return render_template("products/detail.html", product=product, manual=manual)


@catalog_bp.route("/promotions")
def promotions_page():
    client = get_api_client()
    raw_promotions = client.get("/promotions/", params={"active_only": True, "limit": 200})
    promotions = [adapt_promotion(p) for p in raw_promotions]
    return render_template("main/promotions.html", promotions=promotions)
