import os
import re

import site_cache
from flask import Blueprint, current_app, render_template, url_for

from formatting import resolve_image_url
from special_products import SPECIAL_PRODUCTS
from store_api import StoreAPIError, get_api_client

main_bp = Blueprint("main", __name__)

# site_cache entry the contact page's QR cards live in. Shared with
# blueprints/admin/qr_codes.py, which clears it after every save so an admin doesn't
# stare at an unchanged contact page for up to a TTL wondering what went wrong.
QR_CODES_CACHE_KEY = ("qr_codes", "all")

# The hero carousel's slides. Unlike the QR cards this app doesn't fetch them itself -
# they arrive through the sitewide lazy global in app.py, because the slider partial is
# included from two different blueprints. The name lives here rather than there so that
# blueprints/admin/hero_slides.py can clear the entry after a save without importing
# app.py (which imports the blueprints, and would be circular). app.py builds the global
# under HERO_SLIDES_CACHE_VAR; site_cache then keys it by (var, scope), which is the
# pair spelled out in HERO_SLIDES_CACHE_KEY.
HERO_SLIDES_CACHE_VAR = "_cp_hero_slides"
HERO_SLIDES_CACHE_KEY = (HERO_SLIDES_CACHE_VAR, "all")

# Logo files the About page's brand marquee falls back to for brands the
# catalogue doesn't know (or knows without an image). Drop a new file in
# static/images/brands/ and it shows up on the next request - no code change.
BRAND_LOGO_DIR = "images/brands"
BRAND_LOGO_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".svg")
_brand_logo_cache = None


def _brand_key(name):
    """Loose match between a catalogue brand name and a logo filename:
    "Woodpecker" / "woodpecker-logo.png" / "WOODPECKER" all collapse to
    "woodpecker"."""
    key = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return key[:-4] if key.endswith("logo") else key


def _brand_logo_files():
    """[(display name, static url)] for every logo in static/images/brands.
    Memoized outside debug - the folder only changes when someone uploads a file."""
    global _brand_logo_cache
    if _brand_logo_cache is not None and not current_app.debug:
        return _brand_logo_cache

    folder = os.path.join(current_app.static_folder, "images", "brands")
    try:
        filenames = sorted(os.listdir(folder), key=str.lower)
    except OSError:
        filenames = []

    logos = []
    for filename in filenames:
        stem, ext = os.path.splitext(filename)
        if ext.lower() not in BRAND_LOGO_EXTS:
            continue
        label = re.sub(r"[-_]+", " ", stem).strip()
        label = re.sub(r"\s*logo$", "", label, flags=re.IGNORECASE)
        # Acronym filenames (CX, MCTBIO) are already the brand's own casing;
        # only lowercase ones need titling.
        if label.islower():
            label = label.title()
        logos.append((label, url_for("static", filename=f"{BRAND_LOGO_DIR}/{filename}")))

    _brand_logo_cache = logos
    return logos


def brand_showcase_logos():
    """Every brand logo the About page marquee shows: the catalogue's own brands
    first (each linking to its filtered product list), then any logo file that has
    no catalogue brand of the same name. A catalogue brand with no uploaded image
    borrows the matching file if there is one, and is skipped otherwise - a "no
    image" placeholder in a wall of logos just looks broken."""
    try:
        brands = get_api_client().get("/brands/", params={"limit": 200})
    except StoreAPIError:
        brands = []

    files_by_key = {_brand_key(label): url for label, url in _brand_logo_files()}
    catalog_url = url_for("catalog.products_catalog")

    logos = []
    seen = set()
    for brand in brands:
        key = _brand_key(brand.get("brand_name"))
        seen.add(key)
        image = (
            resolve_image_url(brand["brand_image"])
            if brand.get("brand_image")
            else files_by_key.get(key)
        )
        if not image:
            continue
        logos.append(
            {
                "name": brand.get("brand_name") or "",
                "image": image,
                "url": f"{catalog_url}?brand={brand['id']}",
            }
        )

    for label, image in _brand_logo_files():
        if _brand_key(label) in seen:
            continue
        logos.append({"name": label, "image": image, "url": None})

    return logos


@main_bp.route("/")
def landing():
    return render_template("main/landing.html")


@main_bp.route("/machinery")
def home():
    # brands/active_promotions are also available via the sitewide context
    # processor, but passed explicitly too (matches the original mock's own pattern).
    client = get_api_client()
    brands = client.get("/brands/", params={"limit": 200})
    special_products = [
        {"slug": slug, **meta} for slug, meta in SPECIAL_PRODUCTS.items()
    ]
    return render_template("main/home.html", brands=brands, special_products=special_products)


@main_bp.route("/materials")
def materials():
    return render_template("main/materials_coming_soon.html")


BRAND_MARQUEE_ROWS = 5
# A row's track is rendered twice and slides exactly one copy's width, so one copy
# has to be wider than the marquee itself or the loop shows a gap where it wraps.
# Tile pitch is the 140px tile + its 14px margin (css/products.css); 1400px clears
# the About page's 1200px container with room to spare.
_BRAND_TILE_PITCH_PX = 154
_BRAND_ROW_MIN_HALF_PX = 1400


def _brand_marquee_row(logos, tiles_per_half):
    """One marquee row's full track: `logos` repeated up to `tiles_per_half` tiles,
    then that whole half repeated once more for the loop.

    Only the first appearance of each logo is left visible to assistive tech. A row
    of five brands padded out to twenty tiles would otherwise have a screen reader
    read the same five names four times over to describe what is, to anyone who can
    see it, decoration."""
    repeat = max(1, -(-tiles_per_half // len(logos)))
    half = logos * repeat

    tiles = []
    seen = set()
    for copy in (0, 1):
        for logo in half:
            decorative = copy == 1 or logo["image"] in seen
            seen.add(logo["image"])
            tiles.append({**logo, "decorative": decorative})
    return tiles


def brand_marquee_rows():
    """The About page's logo wall, as a list of rows.

    Logos are dealt round-robin rather than sliced into contiguous blocks: the file
    list is alphabetical, so slicing would stack every "C" brand into one row and
    leave another looking like a different alphabet."""
    logos = brand_showcase_logos()
    if not logos:
        return []

    row_count = min(BRAND_MARQUEE_ROWS, len(logos))
    tiles_per_half = max(1, -(-_BRAND_ROW_MIN_HALF_PX // _BRAND_TILE_PITCH_PX))
    return [
        _brand_marquee_row(logos[i::row_count], tiles_per_half)
        for i in range(row_count)
    ]


@main_bp.route("/about")
def about():
    return render_template("main/about.html", brand_logo_rows=brand_marquee_rows())


@main_bp.route("/contact")
def contact():
    # The department QR cards (Admin → Settings → Department QR Codes). Public and
    # identical for every visitor, so one copy is shared across requests for
    # site_cache.TTL seconds; the
    # admin screen clears this key on save so an edit shows up immediately. An
    # unreachable store-api hides the section rather than failing the page - the same
    # thing an empty list already means.
    try:
        qr_codes = site_cache.cached(
            QR_CODES_CACHE_KEY, lambda: get_api_client().get("/qr-codes/", params={"limit": 200})
        )
    except StoreAPIError:
        qr_codes = []
    return render_template("contact.html", qr_codes=qr_codes)


@main_bp.route("/donut")
def donut():
    """Easter egg. Unlinked from every menu - the only way in is the hidden link on
    the 404 page (`.notfound-secret` in not_found.html), so the reward for getting
    lost is a spinning ASCII torus. Renders standalone, outside base.html."""
    return render_template("donut.html")