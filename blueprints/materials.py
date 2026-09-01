"""The materials storefront - HOME 49.

Its own blueprint rather than three more routes inside catalog.py, because
materials is its own shop. It has its own mark in the header, its own footer, its
own way in (the landing screen), and - the part that actually forces the split -
its own shape of catalog:

    machinery   ~110 photographed products, 31 categories, 4 brands
    materials   8,000+ SAP consumables, 824 categories, 173 brands, 1 photograph

Everything the machinery pages do well depends on the first line. One fetch holds
the whole catalog, so filtering happens in the browser; every product has a
picture, so the card is built around it; 31 categories fit in a checkbox panel.
None of that survives the second line, so these pages page on the server, lead
with the *groups* rather than the items, and treat a photograph as a bonus.

Route names are short because the blueprint qualifies them: materials.home,
materials.catalog, materials.categories, materials.brands, materials.detail.
"""
from urllib.parse import urlencode

import sap_catalog
from flask import Blueprint, render_template, request, url_for

from blueprints.catalog import detail_context
from sap_catalog import (
    DEFAULT_SORT,
    PAGE_SIZE,
    SORT_OPTIONS,
    can_sort,
    initials as _initials,
    page_numbers as _page_numbers,
    rail as _rail,
    resolve_sort,
)
from formatting import adapt_product, adapt_promotion
from store_api import StoreAPIError, get_api_client

materials_bp = Blueprint("materials", __name__, url_prefix="/materials")


# How many category tiles / brand cards the home page leads with before handing
# over to the full index. Twelve fills three or four grid rows and stops well
# short of the point where a "browse" turns back into a list nobody reads.
HOME_FACET_COUNT = 12

# How many deals the home page's promotion strip carries. Three or six fit its row at
# every breakpoint; more than that and a strip meant to be read at a glance turns into
# the promotions page, which already exists.
HOME_PROMO_COUNT = 6

# The brand SAP invents for every item whose U_Brand field is empty. It is the single
# biggest "brand" in the catalogue - 1,671 items - so a list ordered by size opens with
# it, and "our top brands: Unbranded" is not a claim the shop wants to make. Filtered
# out of the places that PRESENT brands as a recommendation (the home page strip); left
# in the places that merely LIST them (the brands index, the catalog's filter rail),
# because 1,671 items still have to be reachable by the only name they have.
FALLBACK_BRAND_NAME = "Unbranded"

def _facets(**filters):
    """This shop's slice of sap_catalog.facets - see there for the caching rule."""
    return sap_catalog.facets("materials", **filters)


def _total_items():
    """Every purchasable, listed material - see sap_catalog.total_items."""
    return sap_catalog.total_items("materials")


# Category name -> a Font Awesome glyph, first match wins. Materials arrive from
# SAP with no photographs at all, so a category tile has nothing to show but its
# name; a mark that says "this is a bur" rather than "this is a category" is the
# difference between a browsable wall and 824 identical grey boxes. Ordered
# longest-idea-first, since "resin tooth" must be tried before "resin".
CATEGORY_ICONS = (
    (("resin tooth", "acrylic tooth", "ceramic tooth", "tooth set", "denture"), "fa-teeth"),
    (("bur", "drill", "reamer", "disc", "stone"), "fa-circle-notch"),
    (("file", "endo", "gutta", "apex", "canal"), "fa-diagram-project"),
    (("forcep", "elevator", "plier", "scissor", "scalpel", "instrument", "tweezer"), "fa-scissors"),
    (("composite", "cement", "bonding", "adhesive", "etch", "resin"), "fa-fill-drip"),
    (("impression", "alginate", "silicone", "putty", "wax", "plaster", "stone powder"), "fa-cube"),
    (("zirconia", "ceramic", "metal", "block", "ingot", "alloy"), "fa-cubes"),
    (("glove", "mask", "gown", "shirt", "cap", "apron"), "fa-shirt"),
    (("needle", "syringe", "anesth", "injection"), "fa-syringe"),
    (("scaler", "ultrasonic", "tip", "polish", "prophy"), "fa-wand-magic-sparkles"),
    (("ortho", "bracket", "wire", "band", "elastic", "myobrace", "retainer"), "fa-link"),
    (("x-ray", "xray", "film", "sensor", "imaging"), "fa-x-ray"),
    (("clean", "disinfect", "steril", "autoclave", "detergent"), "fa-spray-can-sparkles"),
    (("cotton", "gauze", "roll", "tissue", "napkin", "bib", "sponge"), "fa-toilet-paper"),
    (("box", "bag", "tray", "container", "sticker", "label", "package"), "fa-box"),
    (("light", "lamp", "curing", "led"), "fa-lightbulb"),
    (("motor", "handpiece", "contra", "turbine", "micromotor"), "fa-gears"),
    (("lab", "laboratory", "articulator", "flask", "model"), "fa-flask-vial"),
)

DEFAULT_CATEGORY_ICON = "fa-layer-group"

# What the admin Categories screen offers as an icon, as (glyph, label) pairs.
#
# Derived from the map above rather than typed out again, so the palette an admin can
# choose from is exactly the vocabulary the storefront already draws - a picker with
# glyphs the guesser never produces would let the two screens disagree about what a
# category looks like, which is the thing category_icon() exists to prevent. The label
# is the first keyword of each group, title-cased: it is what that glyph *means* here
# ("Bur", "Glove"), which reads better in a picker than the Font Awesome class name.
#
# A handful of generic marks are appended for categories the map has no idea about -
# a fifth of the SAP catalogue is named in ways no keyword list will ever cover.
CATEGORY_ICON_CHOICES = [
    (icon, needles[0].title()) for needles, icon in CATEGORY_ICONS
] + [
    ("fa-layer-group", "Generic (default)"),
    ("fa-tooth", "Tooth"),
    ("fa-star", "Star"),
    ("fa-heart-pulse", "Clinical"),
    ("fa-screwdriver-wrench", "Tools"),
    ("fa-truck-fast", "Delivery"),
    ("fa-shield-halved", "Protection"),
    ("fa-microscope", "Microscope"),
]


def category_icon(name, override=None):
    """The glyph for a category tile. A Jinja global (registered in app.py) rather
    than a value baked into each facet dict, so the categories page, the home page
    and the filter rail cannot end up drawing the same category differently.

    `override` is the category's own `category_icon` column, set on the admin
    Categories screen. It wins outright when present - the map below is a guess from
    the name, and a guess should never beat someone who looked at the category and
    chose. It is null for almost every category, which is the point: 824 of them came
    from SAP and nobody is going to pick 824 icons by hand, so the map stays the
    normal path and the column exists for the handful it gets wrong.

    Blank strings count as absent, not as "draw nothing": the admin form posts "" for
    an untouched field, and an empty class would render an invisible <i>.
    """
    if (override or "").strip():
        return override.strip()
    lowered = (name or "").lower()
    for needles, icon in CATEGORY_ICONS:
        if any(needle in lowered for needle in needles):
            return icon
    return DEFAULT_CATEGORY_ICON


def _promoted_brands(brands, limit):
    """The brands worth putting on the front page, biggest first.

    Drops the SAP fallback - see FALLBACK_BRAND_NAME. Done here rather than in the
    facet endpoint because the same buckets feed the brands index and the filter rail,
    where "Unbranded" is a legitimate thing to click.
    """
    return [b for b in brands if b["name"] != FALLBACK_BRAND_NAME][:limit]


@materials_bp.route("/")
def home():
    """The materials front door.

    Category-first, deliberately: 8,000 items is not something anyone scrolls, and
    a bare grid of page 1 of 339 tells a visitor nothing about what the shop
    stocks. The groups do - "419 Diamond Burs, 332 Resin Tooth 6 Upper" is the
    catalogue described in a screen.
    """
    facets = _facets()
    categories, brands = facets["categories"], facets["brands"]

    # The deals this shop is running. Its own fetch rather than the sitewide
    # `active_promotions` global: that one is capped at 50 and shared with the promo
    # banner, and this strip wants them ordered and sliced for a front page. Both are
    # already filtered to section=materials, so the two agree about what is on offer.
    try:
        promotions = [
            adapt_promotion(p)
            for p in get_api_client().get(
                "/promotions/",
                params={"active_only": True, "section": "materials", "limit": HOME_PROMO_COUNT},
            )
        ]
    except StoreAPIError:
        # A promo strip is decoration on a page whose job is the catalogue. Losing
        # store-api for a moment should cost the strip, not the whole front page.
        promotions = []

    return render_template(
        "materials/home.html",
        top_categories=categories[:HOME_FACET_COUNT],
        # "Top brands" is a recommendation, and SAP's catch-all is not one - see
        # FALLBACK_BRAND_NAME.
        top_brands=_promoted_brands(brands, HOME_FACET_COUNT),
        promotions=promotions,
        total_items=_total_items(),
        category_count=len(categories),
        brand_count=len(brands),
        initials=_initials,
    )


@materials_bp.route("/catalog")
def catalog():
    """The paged results grid - every filtered view of the catalogue lands here.

    Three things this does that the machinery catalog does not, all forced by size:

      - paging on the SERVER. `limit` is capped at 500 (MAX_PAGE_SIZE) and 8,000
        cards is not a page anyone can use, so the grid is a window and the URL
        carries `?page=`.
      - a total from GET /products/count. Holding 24 rows, this page cannot tell
        whether three more match or three thousand, and "showing 24 of 8,125" is
        the difference between a catalog and a dead end.
      - a filter rail built from GET /products/facets rather than from the full
        category list, so every option it offers has items behind it and says how
        many. A rail built from GET /categories/ would offer all 854 - machinery's
        included - and thirty of them would lead to an empty grid.
    """
    client = get_api_client()

    selected_brand = request.args.get("brand", type=int)
    selected_category = request.args.get("category", type=int)
    search_query = request.args.get("q", "").strip()
    page = max(1, request.args.get("page", 1, type=int))
    # Unknown values, and any ordering asked for by a shopper whose prices are
    # masked, fall back to the default - see sap_catalog.resolve_sort.
    sort = resolve_sort(request.args.get("sort", DEFAULT_SORT))

    filters = {"section": "materials"}
    if selected_brand:
        filters["brand_id"] = selected_brand
    if selected_category:
        filters["category_id"] = selected_category
    if search_query:
        filters["q"] = search_query

    total = client.get("/products/count", params=filters).get("count", 0)
    total_pages = max(1, -(-total // PAGE_SIZE))
    # A `?page=` past the end (a stale bookmark, or a filter that has since
    # narrowed) lands on the last real page instead of an empty grid.
    page = min(page, total_pages)

    # `sort` goes to the SERVER, not to the 24 rows that come back. This page is a
    # window onto 8,000 items, so "cheapest first" applied to the window would only
    # reorder the window - see GET /products/'s _SORTS.
    #
    # Kept out of `filters` on purpose: `filters` is also what /count and /facets are
    # asked with, and neither has an opinion about ordering.
    raw_products = client.get(
        "/products/",
        params={
            **filters,
            "sort": sort,
            "skip": (page - 1) * PAGE_SIZE,
            "limit": PAGE_SIZE,
        },
    )
    products = [adapt_product(p) for p in raw_products]

    facets = _facets(
        brand_id=selected_brand, category_id=selected_category, q=search_query
    )
    # Counted with this facet's own filter dropped (see the endpoint), so both
    # lists still offer every sibling to switch to - what a filter rail is for.
    categories, brands = facets["categories"], facets["brands"]

    selected_category_obj = next(
        (c for c in categories if c["id"] == selected_category), None
    )
    selected_brand_obj = next((b for b in brands if b["id"] == selected_brand), None)

    if search_query:
        page_title = f'Results for "{search_query}"'
    elif selected_category_obj:
        page_title = selected_category_obj["name"]
    elif selected_brand_obj:
        page_title = selected_brand_obj["name"]
    else:
        page_title = "All Materials"

    def catalog_url(**overrides):
        query = {
            "brand": selected_brand,
            "category": selected_category,
            "q": search_query or None,
            # The default ordering is left out of the URL entirely, so the canonical
            # view of a category has one address however you arrived at it.
            "sort": sort if sort != DEFAULT_SORT else None,
            # Any change of filter is a new result set, so it starts at its own
            # first page rather than at page 40 of a list that no longer exists.
            "page": page if page > 1 else None,
        }
        query.update(overrides)
        query = {k: v for k, v in query.items() if v not in (None, "", [])}
        base = url_for("materials.catalog")
        return f"{base}?{urlencode(query)}" if query else base

    def filter_url(**overrides):
        """A filter link: same view, one facet changed, back to page 1."""
        return catalog_url(page=None, **overrides)

    def sort_url(value):
        """This exact view, reordered. Back to page 1: a new ordering means page 7
        holds different items, and staying on it lands the shopper somewhere they
        never asked for."""
        return catalog_url(page=None, sort=value if value != DEFAULT_SORT else None)

    def page_url(target):
        # Page 1 drops the parameter rather than writing ?page=1, so the canonical
        # first page has exactly one URL however you arrive at it.
        return catalog_url(page=target if target > 1 else None)

    page_numbers = _page_numbers(page, total_pages)

    return render_template(
        "materials/catalog.html",
        products=products,
        categories=_rail(categories, selected_category),
        brands=_rail(brands, selected_brand),
        category_total=len(categories),
        brand_total=len(brands),
        selected_brand=selected_brand,
        selected_category=selected_category,
        selected_brand_obj=selected_brand_obj,
        selected_category_obj=selected_category_obj,
        search_query=search_query,
        page_title=page_title,
        total=total,
        page=page,
        total_pages=total_pages,
        page_numbers=page_numbers,
        page_size=PAGE_SIZE,
        sort=sort,
        sort_options=SORT_OPTIONS,
        can_sort=can_sort(),
        sort_url=sort_url,
        catalog_url=catalog_url,
        filter_url=filter_url,
        page_url=page_url,
        initials=_initials,
    )


@materials_bp.route("/categories")
def categories():
    """Every category, grouped by first letter, with the count behind each.

    A page of its own rather than a longer dropdown. The select this replaces held
    854 options in one flat alphabetical run with no counts: type-to-jump found a
    category if you already knew its exact name, and offered nothing at all to
    someone browsing. Here the same list is grouped, counted, jumpable by letter,
    and filterable as you type (materials/categories.html).

    All 824 are rendered in one page - 370KB of markup that gzips to 29KB - because
    the filter box is client-side, and a server-paged index would have nothing to
    filter.
    """
    facets = _facets()
    groups = {}
    for category in sorted(facets["categories"], key=lambda c: c["name"].lower()):
        # Anything not starting with a letter files under "#" - SAP names include
        # a handful that lead with a digit or a quote mark.
        first = category["name"][:1].upper()
        groups.setdefault(first if first.isalpha() else "#", []).append(category)

    # "#" last, letters in order: a jump bar reading "# A B C" puts the least
    # useful key where the eye lands first.
    letters = sorted(groups, key=lambda letter: (letter == "#", letter))

    return render_template(
        "materials/categories.html",
        groups=groups,
        letters=letters,
        biggest=facets["categories"][:HOME_FACET_COUNT],
        category_count=len(facets["categories"]),
    )


@materials_bp.route("/brands")
def brands():
    """Every brand with materials behind it, biggest first.

    Same reasoning as the categories index, one list along: 173 brands is past the
    point where a dropdown is a way of choosing. Brands are ordered by size rather
    than alphabetically because that is how this list is actually used - the top of
    it is the supply the shop runs on.
    """
    facets = _facets()
    return render_template(
        "materials/brands.html",
        brands=facets["brands"],
        brand_count=len(facets["brands"]),
        initials=_initials,
    )


@materials_bp.route("/<int:product_id>")
def detail(product_id):
    """One item. Its own template, not products/detail.html.

    The machinery product page is built around a photo gallery and a paragraph of
    marketing copy. A materials row has neither - one item in 8,125 has a picture
    and none has a description - so the same template renders a large empty stage
    above a spec table with two rows in it. This one leads with what the row
    actually holds: the SAP item code, the unit it is sold by, its category, and
    the price.
    """
    context = detail_context(product_id, "materials", related_by="category")
    if not isinstance(context, dict):
        return context
    return render_template("materials/detail.html", **context)
