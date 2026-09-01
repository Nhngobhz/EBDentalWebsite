import os
import re

import requests
import site_cache
import site_section
import site_settings
from flask import Blueprint, Response, abort, current_app, render_template, url_for

from formatting import resolve_image_url
from blueprints.catalog import section_brands
from special_products import SPECIAL_PRODUCTS
from store_api import StoreAPIError, get_api_client

main_bp = Blueprint("main", __name__)

# site_cache entry the contact page's QR cards live in. Shared with
# blueprints/admin/qr_codes.py, which clears it after every save so an admin doesn't
# stare at an unchanged contact page for up to a TTL wondering what went wrong.
QR_CODES_CACHE_KEY = ("qr_codes", "all")

# The hero carousel's slides. Unlike the QR cards this app doesn't fetch them itself -
# they arrive through the sitewide lazy global in app.py, because the slider partial is
# included from three different blueprints. The name lives here rather than there so
# that blueprints/admin/hero_slides.py can clear the entry after a save without
# importing app.py (which imports the blueprints, and would be circular). app.py builds
# the global under HERO_SLIDES_CACHE_VAR; site_cache then keys it by (var, scope).
HERO_SLIDES_CACHE_VAR = "_cp_hero_slides"

# One cache entry per shop, because the global is now fetched per section (a machinery
# page must not carry the materials slides). A save clears BOTH: an admin can move a
# slide from one carousel to the other in a single edit, which changes what each
# section returns, and clearing only the section named on the form would leave the
# other one advertising a slide that has left it. Cheap - it is two dict pops.
HERO_SLIDES_CACHE_KEYS = tuple(
    (HERO_SLIDES_CACHE_VAR, section) for section in ("machinery", "materials")
)

# Logo files the About page's brand marquee falls back to for brands the
# catalogue doesn't know (or knows without an image). Drop a new file in
# static/images/brands/ and it shows up on the next request - no code change.
BRAND_LOGO_DIR = "images/brands"
BRAND_LOGO_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".svg")
_brand_logo_cache = None

# Where a brand tile leads, keyed by the products.section its products are in. Three
# catalogues, not two: spare parts are SAP items sold inside the machinery shop but
# listed on a page of their own, so a brand whose only stock is parts has to link
# there. Ordered as written for a machinery visitor - a machine before its parts,
# the other shop last; brand_link_order() flips it for a materials one.
BRAND_CATALOG_ENDPOINTS = {
    "machinery": "catalog.products_catalog",
    "spare_parts": "catalog.spare_parts",
    "materials": "materials.catalog",
}

# Shortest logo filename allowed to claim a brand by prefix (see _match_logo_file).
# "h.png" is the start of twelve brand names in this catalogue and belongs to none
# of them.
_BRAND_LOGO_PREFIX_MIN = 4


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


def carried_brands():
    """Every brand with products behind it, each carrying the sections it has them
    in: [{id, brand_name, brand_image, sections: [...]}].

    Built from the per-section facets rather than GET /brands/, because that endpoint
    knows nothing about sections. Since the SAP import it returns 190 brands of which
    only four have a single machine between them, so a wall built from it sent every
    tile to the machinery catalog and most of them landed on an empty grid.

    A brand missing from all three lists has nothing to sell and simply isn't here.
    """
    brands = {}
    for section in BRAND_CATALOG_ENDPOINTS:
        try:
            rows = section_brands(section)
        except StoreAPIError:
            continue
        for row in rows:
            brands.setdefault(row["id"], {**row, "sections": []})["sections"].append(
                section
            )
    return list(brands.values())


def brand_link_order():
    """The sections a brand tile prefers to open, best first.

    The shopper's own shop leads. About belongs to both halves of the site, so the
    only thing saying which one a visitor came from is the remembered section - and
    sending a HOME 49 shopper who clicked a logo into the machinery catalog strands
    them in the other shop exactly the way app.py's endpoint map exists to prevent.
    """
    if site_section.remembered() == "materials":
        return ("materials", "machinery", "spare_parts")
    return tuple(BRAND_CATALOG_ENDPOINTS)


def _brand_link(brand):
    """The catalogue this brand's tile opens, or None if it sells nothing anywhere."""
    for section in brand_link_order():
        if section in brand["sections"]:
            return url_for(BRAND_CATALOG_ENDPOINTS[section], brand=brand["id"])
    return None


def _match_logo_file(key, files_by_key):
    """The logo file for a catalogue brand, as (file key, url), or (None, None).

    An exact key match first. Failing that, a filename that is the START of the
    brand's name - "lovage.png" for SAP's "Lovage Medical" - but only when exactly
    one file matches and its name is long enough to mean something.
    """
    if key in files_by_key:
        return key, files_by_key[key]
    partial = [
        k
        for k in files_by_key
        if len(k) >= _BRAND_LOGO_PREFIX_MIN and key.startswith(k)
    ]
    if len(partial) == 1:
        return partial[0], files_by_key[partial[0]]
    return None, None


def brand_showcase_logos():
    """Every brand logo the About page marquee shows: the catalogue's own brands
    first (each linking to the catalogue that actually stocks it), then any logo file
    with no catalogue brand behind it, as a plain tile. A catalogue brand with no
    uploaded image borrows the matching file if there is one, and is skipped
    otherwise - a "no image" placeholder in a wall of logos just looks broken."""
    files_by_key = {_brand_key(label): url for label, url in _brand_logo_files()}

    logos = []
    claimed = set()
    for brand in carried_brands():
        key = _brand_key(brand["brand_name"])
        # Claimed whether or not this brand ends up shown: the leftover pass below is
        # for files no brand answers to, and a brand skipped for having no image at
        # all is still not one of those.
        claimed.add(key)
        image = (
            resolve_image_url(brand["brand_image"]) if brand["brand_image"] else None
        )
        if not image:
            file_key, image = _match_logo_file(key, files_by_key)
            if not image:
                continue
            claimed.add(file_key)
        logos.append(
            {
                "name": brand["brand_name"] or "",
                "image": image,
                "url": _brand_link(brand),
            }
        )

    for label, image in _brand_logo_files():
        if _brand_key(label) in claimed:
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
    # section_brands, not GET /brands/: this grid is "Shop by Brand" on the
    # machinery home page, and the raw endpoint would fill it with the 173 brands
    # that only carry materials - see section_brands().
    brands = section_brands("machinery")
    special_products = [
        {"slug": slug, **meta} for slug, meta in SPECIAL_PRODUCTS.items()
    ]
    return render_template("main/home.html", brands=brands, special_products=special_products)


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


# The fetched bytes of the quotation's payment QR, keyed by the URL they came from -
# so replacing the picture serves the new one immediately instead of after a TTL, and
# two different pictures can never share an entry.
QUOTE_QR_CACHE_PREFIX = "quote_payment_qr"


@main_bp.route("/quote-payment-qr.png")
def quote_payment_qr():
    """The bank QR printed in the terms box of a quotation, re-served from THIS app.

    The picture itself lives wherever store-api put it: a Cloudflare R2 URL, or
    store-api's own /static on its own port. Either way it is a different origin from
    this app - and the printed quote is snapshotted with html2canvas
    (QuoteCart.exportPDF in static/js/main.js). A canvas that has drawn a cross-origin
    image is tainted, and toDataURL() on a tainted canvas throws, so a QR loaded
    straight from R2 or from store-api would break the PDF export outright rather than
    just printing without the picture. Serving the bytes from here makes it same-origin,
    which is a guarantee neither CORS headers nor crossorigin="anonymous" can offer.

    Public, like the quotation it prints on - a customer exporting their own quote is
    signed in as a customer at most, and the picture is a payment QR the shop wants
    scanned. `?v=` is added by the caller (buildPrintTemplate) from the stored filename,
    so an admin replacing the picture busts every browser's copy of the old one.
    """
    stored = (site_settings.get().get("quote_payment_qr") or "").strip()
    if not stored:
        abort(404)

    url = resolve_image_url(stored)
    # resolve_image_url turns a stored "/static/uploads/..." into store-api's own URL;
    # anything else absolute is R2. Fetching a URL that came out of a settings row is
    # a server-side request whose destination an admin controls, so it is held to the
    # two shapes that are actually produced: this deployment's store-api, or https.
    # Plain http:// elsewhere - which would reach cloud metadata endpoints and other
    # things only this server can see - is refused rather than fetched.
    api_base = current_app.config["STORE_API_BASE_URL"].rstrip("/")
    if not (url.startswith(f"{api_base}/") or url.startswith("https://")):
        current_app.logger.warning("Refusing to fetch the payment QR from %r", url)
        abort(404)

    def fetch():
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "image/png")
        if not content_type.startswith("image/"):
            raise ValueError(f"payment QR at {url} is {content_type}, not an image")
        return response.content, content_type

    try:
        content, content_type = site_cache.cached((QUOTE_QR_CACHE_PREFIX, url), fetch)
    except (requests.RequestException, ValueError) as exc:
        current_app.logger.warning("Could not load the payment QR: %s", exc)
        abort(404)

    return Response(
        content,
        mimetype=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@main_bp.route("/donut")
def donut():
    """Easter egg. Unlinked from every menu - the only way in is the hidden link on
    the 404 page (`.notfound-secret` in not_found.html), so the reward for getting
    lost is a spinning ASCII torus. Renders standalone, outside base.html."""
    return render_template("donut.html")