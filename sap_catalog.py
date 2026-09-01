"""The pieces a server-paged, SAP-sourced catalogue page is built from.

Two storefront areas are now shaped this way, and they arrived a fortnight apart:

    materials    section "materials"    8,125 items, 824 categories, 173 brands
    spare parts  section "spare_parts"    754 items, 194 categories,  33 brands

Neither can do what the machinery catalog does - one fetch of everything, filtered
in the browser - because `limit` is capped at 500 (store-api's MAX_PAGE_SIZE) and
because a wall of 8,000 cards is not a page. Both therefore page on the server,
count with GET /products/count, and build their filter rail from
GET /products/facets rather than from the full category list.

That machinery is what lives here: the paging arithmetic, the facet fetch and its
cache, and the rail. What does NOT live here is anything either area says in its
own voice - its URLs, its headings, its breadcrumbs, its template. Those differ
because the two are different shops (materials is HOME 49 with its own header and
its own five pages; spare parts is one page inside the machinery shop), and
folding them together would mean a page that has to ask which shop it is in before
it can draw a link.

Its own module rather than functions in blueprints/materials.py for the reason
site_cache.py and site_section.py are: blueprints/catalog.py would otherwise have
to import from blueprints/materials.py, which already imports from it.
"""
import site_cache
from auth import can_view_prices
from store_api import get_api_client

# How many cards fill one page. 24 divides evenly into the 2/3/4-column grid at
# every breakpoint, so the last row is never a lone orphan card.
PAGE_SIZE = 24

# How many numbered page links to show at once. The materials catalog runs to ~340
# pages; rendering one link each would be a longer list than the products.
PAGE_WINDOW = 7

# How many of each facet a catalog's filter rail offers inline. The rail sits
# beside the results and has to stay scannable at a glance.
RAIL_FACET_COUNT = 10

# How a shopper may reorder a catalogue, as (value, label) pairs. The values are
# store-api's own (schemas.ProductSort) rather than a translation, so the select
# posts straight through to the query string it filters by.
#
# Deliberately short. Sorting thousands of items is genuinely useful - by price
# above all, which is the question a clinic actually asks - but a menu of ten
# orderings is a menu nobody reads. Stock is offered because these are the halves
# of the catalogue that HAVE a stock figure (machinery never enters SAP).
SORT_OPTIONS = (
    ("name", "Name (A-Z)"),
    ("price_asc", "Price: low to high"),
    ("price_desc", "Price: high to low"),
    ("stock_desc", "Most in stock"),
    ("newest", "Recently added"),
)
SORT_VALUES = {value for value, _ in SORT_OPTIONS}
DEFAULT_SORT = "name"


def can_sort():
    """Whether this shopper is offered the Sort control at all.

    Anyone whose prices are masked is not. "Price: low to high" over a grid of
    "Login to view price" cards ranks the catalogue by the one figure the mask
    exists to withhold, and an ordering is readable: page through it and every
    item's price is pinned between its neighbours' without a single figure ever
    being printed.

    Dropped whole rather than trimmed to the three orderings that leak nothing,
    because a Sort menu that quietly lacks the entry a shopper came for reads as
    broken, where no menu reads as "prices first, then sorting" - which is what
    this is. Only the presentation, though: store-api refuses a masked caller the
    price orderings itself (GET /products/, _PRICE_SORTS), which is what holds
    when the parameter is typed into the URL instead of chosen from a menu.
    """
    return can_view_prices()


def resolve_sort(value):
    """The ordering a request actually gets.

    An unknown value - a stale link, a hand-typed URL - falls back to the default
    rather than 422-ing off store-api's Literal, and so does any ordering asked
    for by someone can_sort() says may not ask: the hidden control is a
    convenience, not the rule that enforces it.
    """
    if can_sort() and value in SORT_VALUES:
        return value
    return DEFAULT_SORT


def facets(section, **filters):
    """Categories and brands present in a filter set, biggest first.

    See GET /products/facets in store-api. Only the unfiltered call is cached:
    that one is asked for by every visit to a landing, index or catalog page, while
    a filtered one is particular to whatever a single shopper has ticked, and
    caching those would be an unbounded dictionary keyed by search strings.

    Keyed by section, so the materials rail and the spare-parts rail cannot serve
    each other's buckets - they are the same shape and would be indistinguishable
    once cached.
    """
    params = {"section": section}
    params.update({k: v for k, v in filters.items() if v})

    def fetch():
        return get_api_client().get("/products/facets", params=params)

    if list(params) == ["section"]:
        return site_cache.cached((f"{section}_facets", "all"), fetch)
    return fetch()


def total_items(section):
    """How many purchasable, listed products the section holds.

    NOT the sum of the category facet: that JOINs categories, so items that
    arrived from SAP with no sub-group are missing from it - which is how the
    materials home page once advertised 7,994 over a catalogue whose own first
    page said 8,125. Cached because it is the same number for every visitor and
    moves only when the nightly SAP sync runs.
    """
    return site_cache.cached(
        (f"{section}_total", "all"),
        lambda: get_api_client()
        .get("/products/count", params={"section": section})
        .get("count", 0),
    )


def rail(buckets, selected, count=RAIL_FACET_COUNT):
    """The biggest `count` buckets, with whatever is currently chosen pinned to the
    top of them.

    The pinning is the point: "Amalgam Carriers" is one of 824 categories and
    nowhere near the biggest, so browsing into it would otherwise leave the rail
    showing ten categories, none of them the one you are looking at, with no
    highlighted row anywhere to say where you are.
    """
    if selected is None:
        return buckets[:count]
    chosen = [b for b in buckets if b["id"] == selected]
    rest = [b for b in buckets if b["id"] != selected]
    return chosen + rest[: count - len(chosen)]


def page_numbers(page, total_pages, width=PAGE_WINDOW):
    """The numbered links to draw around the current page.

    Stays `width` wide at both ends instead of shrinking to three links on page 1 -
    clamping the start alone would do that.
    """
    half = width // 2
    start = max(1, min(page - half, total_pages - width + 1))
    return list(range(start, min(total_pages, start + width - 1) + 1))


def initials(name):
    """Two letters standing in for a brand with no logo, which is most of them:
    the brands that arrived from SAP's U_Brand field did not bring pictures."""
    # Punctuation is a word break, not a letter: "N/A" reads as NA, "D+Z" as DZ.
    cleaned = "".join(c if c.isalnum() else " " for c in (name or ""))
    words = cleaned.split()
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()
