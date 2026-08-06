"""Static "special product" pages.

Some products (usually flagship/manufacturer-spotlight items) get a rich,
manufacturer-style landing page instead of the normal catalog detail page -
these are NOT backed by store-api; the content is hand-copied from the
manufacturer's own site and lives entirely in this app as static data.

To add a new special product page:
1. Drop a `<slug>_tabs.json` file in `data/special_products/` shaped like:
   { "Product": [...], "Software": [...], "Imaging": [...] }
   (tab names are whatever you want the tab labels to say; each tab is a
   list of "blocks" - see special_detail.html for the block types it knows
   how to render: header / image / feature / sku_switcher / gallery).
2. Add an entry to SPECIAL_PRODUCTS below with the page's hero copy.
3. Link to it with url_for('catalog.special_product', slug='<slug>').

blueprints/catalog.py's special_product() route does the JSON loading and
404s for an unknown slug - nothing else needs to change.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data" / "special_products"

# Hero copy + tab labels for each special product page, keyed by URL slug.
SPECIAL_PRODUCTS = {
    "smart3d-x": {
        "name": "Smart3D-X",
        "eyebrow": "Intelligent CBCT",
        "tagline": "Large FOV Professional Dental CBCT",
        "subtitle": "3-in-1 Intelligent CBCT (CBCT / PAN / CEPH)",
        "hero_image": "https://34182389.s21i.faiusr.com/2/ABUIABACGAAg2IuO0gYozIGvLjCADziQAw.jpg",
        "hero_video": "https://34182389.s21v.faiusr.com/58/ABUIABA6GAAgqYra0AYogPiQ0wQ.mp4",
        "tabs_file": "smart3d-x_tabs.json",
        # Order + display label for each tab key found in the tabs file.
        "tab_order": ["Product", "Software", "Imaging"],
    },

    "fusionfacescanner": {
        "name": "FusionFaceScanner",
        "eyebrow": "Facial Data Capture",
        "tagline": "Precision Oral Care & Aesthetic Solutions",
        "subtitle": "Enhancing Dental Treatments and Preserving Beauty in Cosmetic Medicine",
        "hero_image": "https://34182389.s21i.faiusr.com/2/ABUIABACGAAg1YX50AYo5sXEQjCADziQAw!800x800.jpg.webp",
        "tabs_file": "fusionfacescanner_tabs.json",
        "tab_order": ["Product"],
    },
}


def get_special_product(slug):
    """Return the special product's hero metadata + parsed tab content, or
    None if the slug isn't registered / its data file is missing."""
    meta = SPECIAL_PRODUCTS.get(slug)
    if not meta:
        return None
    data_path = DATA_DIR / meta["tabs_file"]
    if not data_path.exists():
        return None
    with open(data_path, encoding="utf-8") as f:
        tabs_raw = json.load(f)
    tabs = [
        {"key": key, "label": key, "blocks": tabs_raw.get(key, [])}
        for key in meta["tab_order"]
        if key in tabs_raw
    ]
    return {**meta, "slug": slug, "tabs": tabs}
