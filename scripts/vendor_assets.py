"""Pull the web fonts and the icon font into static/, so a page load touches nothing
but this server.

Why this exists
---------------
Every page used to open `fonts.googleapis.com` and `cdnjs.cloudflare.com` before it
could paint, because both are render-blocking <link rel=stylesheet> tags. That is two
DNS lookups, two TLS handshakes and two round trips to the public internet on the
critical path of a site whose users are all on the same LAN as the server
(192.168.0.113). When the office link is slow the site is slow; when it is down the
site renders unstyled with no icons at all. Nothing about the fonts changes between
releases, so paying that cost per page view buys nothing.

This script downloads them once, at build time, and rewrites the CSS to point at
`static/fonts/`. Re-run it only when a font family, a weight, or the Font Awesome
version changes - the output is committed, so a deploy needs no internet.

Outputs, all generated - do not hand-edit them:
  static/css/fonts.css   @font-face rules for the three Google families
  static/css/icons.css   Font Awesome, subset to the icons this codebase uses
  static/fonts/*.woff2   the font binaries those two point at
  static/vendor/*.js     the three libraries main.js loads on demand

Usage
-----
    python scripts/vendor_assets.py            # refresh everything
    python scripts/vendor_assets.py --icons    # Font Awesome only
    python scripts/vendor_assets.py --fonts    # Google Fonts only
    python scripts/vendor_assets.py --js       # the on-demand libraries only

Still external after this, deliberately: Leaflet, on the delivery-pin map
(static/js/location-picker.js). Its tiles come from openstreetmap.org, so the map
needs the internet whatever this script does, and vendoring the library alone would
buy a working script around a grey void.

Needs `fonttools` and `brotli` (build-time only, see requirements-dev.txt) and a
working internet connection. The Flask app itself needs neither.
"""
import argparse
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
STATIC = os.path.join(PROJECT, "static")
FONT_DIR = os.path.join(STATIC, "fonts")
CSS_DIR = os.path.join(STATIC, "css")

# Google serves a different stylesheet to every browser - woff2 to modern ones, and
# progressively older formats down to EOT for browsers nobody here runs. Asking as
# Chrome is what gets the woff2 variable fonts.
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# One variable font per family instead of one file per weight. base.css uses six
# weights of Inter (400-900); as static instances that is six downloads, as a
# variable font it is one that covers every weight including the ones a future
# design tweak might reach for.
GOOGLE_FONTS_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Inter:wght@400..900"
    "&family=Plus+Jakarta+Sans:wght@600..800"
    "&family=Noto+Sans+Khmer:wght@400..700"
    "&display=swap"
)

# Google splits each family across a dozen unicode-range subsets (cyrillic, greek,
# vietnamese, ...). A browser only downloads the ones a glyph on the page actually
# needs, so keeping them all costs nothing at runtime - but it does mean vendoring
# ~40 files for scripts this site will never render. The storefront is English and
# Khmer; latin-ext covers the accented brand names ("Coricama", "Bien-Air").
KEEP_SUBSETS = ("latin", "latin-ext", "khmer")

FA_VERSION = "6.5.0"
FA_BASE = f"https://cdnjs.cloudflare.com/ajax/libs/font-awesome/{FA_VERSION}"

# Only the two styles the codebase actually writes: `fas` (solid) on ~577 elements and
# `fab` (brands) on three - Facebook and Google. `far` (regular) is never used, so its
# whole webfont is dropped rather than subset.
FA_FACES = {
    "fa-solid-900.woff2": "solid",
    "fa-brands-400.woff2": "brands",
}

# Where icon names can appear. blueprints/ matters as much as templates/: the materials
# shop picks a category glyph in Python (CATEGORY_ICONS / CATEGORY_ICON_CHOICES in
# blueprints/materials.py), and those names appear nowhere in any template.
SCAN_DIRS = ("templates", "static/js", "blueprints")
SCAN_FILES = ("app.py", "formatting.py", "site_section.py")
SCAN_EXTS = (".html", ".js", ".py")

# Class names that share the `fa-` prefix but are modifiers, not glyphs. Matching them
# against the icon table would simply miss, so this list is about keeping the report
# honest rather than about correctness.
FA_MODIFIERS = {
    "fa-solid", "fa-regular", "fa-brands", "fa-light", "fa-thin", "fa-duotone",
    "fa-fw", "fa-spin", "fa-spin-pulse", "fa-spin-reverse", "fa-pulse", "fa-beat",
    "fa-fade", "fa-beat-fade", "fa-bounce", "fa-shake", "fa-flip", "fa-border",
    "fa-inverse", "fa-stack", "fa-stack-1x", "fa-stack-2x", "fa-ul", "fa-li",
    "fa-pull-left", "fa-pull-right", "fa-xs", "fa-sm", "fa-lg", "fa-xl", "fa-2xl",
    "fa-1x", "fa-2x", "fa-3x", "fa-4x", "fa-5x", "fa-6x", "fa-7x", "fa-8x", "fa-9x",
    "fa-10x", "fa-rotate-90", "fa-rotate-180", "fa-rotate-270", "fa-rotate-by",
    "fa-flip-horizontal", "fa-flip-vertical", "fa-flip-both", "fa-swap-opacity",
    "fa-icon", "fa-solid-900", "fa-brands-400", "fa-regular-400",
}

# Icons no static scan can find, because nothing in the tree spells them out. Add to
# this set when an icon renders as an empty box after a change, then re-run.
EXTRA_ICONS = set()

# The libraries main.js injects on demand (QuoteCart._ensurePdfLibs / _ensureQrLib).
# They stay lazy - none of them is on the critical path - but they are vendored anyway
# because each one backs an action staff have to be able to complete: exporting a
# quote to PDF, and putting a KHQR code on screen to take a payment. Left on cdnjs,
# those two fail with "Failed to load" whenever the office internet is down, on a
# system that is otherwise entirely local.
VENDOR_JS = {
    "qrcode.min.js": "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js",
    "jspdf.umd.min.js": "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js",
    "html2canvas.min.js": "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
}


def _fetch(url, as_text=False):
    request = urllib.request.Request(url, headers={"User-Agent": CHROME_UA})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    return data.decode("utf-8") if as_text else data


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(content, str):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    else:
        with open(path, "wb") as handle:
            handle.write(content)
    return os.path.getsize(path)


def _kb(n):
    return f"{n / 1024:.0f}KB"


# --------------------------------------------------------------------------- fonts

def vendor_google_fonts():
    """Download the three families as woff2 and write static/css/fonts.css."""
    print("Google Fonts")
    css = _fetch(GOOGLE_FONTS_URL, as_text=True)

    # The stylesheet is a flat run of `/* subset */ @font-face { ... }` pairs, so the
    # comment before a block is the only thing naming the subset it covers.
    blocks = re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{.*?\})", css, re.S)
    if not blocks:
        sys.exit("  ! Google returned a stylesheet in an unexpected shape - aborting")

    kept, total = [], 0
    for subset_name, block in blocks:
        if subset_name not in KEEP_SUBSETS:
            continue
        url = re.search(r"url\((https://[^)]+\.woff2)\)", block)
        if not url:
            continue
        family = re.search(r"font-family:\s*'([^']+)'", block).group(1)
        filename = f"{family.lower().replace(' ', '-')}-{subset_name}.woff2"
        total += _write(os.path.join(FONT_DIR, filename), _fetch(url.group(1)))
        kept.append(block.replace(url.group(1), f"/static/fonts/{filename}"))
        print(f"  + {filename}")

    header = (
        "/* GENERATED by scripts/vendor_assets.py - do not edit.\n"
        f"   Source: {GOOGLE_FONTS_URL}\n"
        "   Variable woff2, one file per family per unicode subset. A browser pulls\n"
        "   only the subsets a glyph on the page needs.\n"
        "   Licence: SIL Open Font License 1.1 for all three families. */\n"
    )
    _write(os.path.join(CSS_DIR, "fonts.css"), header + "\n".join(kept) + "\n")
    print(f"  = {len(kept)} faces, {_kb(total)} of woff2 -> static/css/fonts.css")


# --------------------------------------------------------------------------- icons

def used_icon_names():
    """Every `fa-something` written anywhere in the source tree, minus the modifiers."""
    paths = [os.path.join(PROJECT, name) for name in SCAN_FILES]
    for directory in SCAN_DIRS:
        for root, _dirs, files in os.walk(os.path.join(PROJECT, directory)):
            paths += [os.path.join(root, f) for f in files if f.endswith(SCAN_EXTS)]

    found = set()
    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                found |= set(re.findall(r"\bfa-[a-z0-9]+(?:-[a-z0-9]+)*", handle.read()))
        except (OSError, UnicodeDecodeError):
            continue
    return (found - FA_MODIFIERS) | EXTRA_ICONS


def parse_icon_table(css):
    """{icon class -> codepoint hex} out of Font Awesome's own stylesheet.

    Rules come both singly (`.fa-user:before{content:"\\f007"}`) and as aliases
    sharing one glyph, where every selector in the group carries its own pseudo-
    element (`.fa-bars:before,.fa-navicon:before{content:"\\f0c9"}`) - so the class
    names are pulled out of the whole selector list rather than assumed to sit in
    one particular position. Getting this wrong is silent: an icon missing from the
    table is simply left out of the subset and renders as an empty box.
    """
    table = {}
    for selectors, codepoint in re.findall(
        r'([^{}]+)\{content:"\\([0-9a-f]+)"\}', css
    ):
        for name in re.findall(r"\.(fa-[a-z0-9-]+)", selectors):
            table[name] = codepoint
    return table


def subset_face(source, destination, codepoints):
    """Cut `source` down to `codepoints` and write it as woff2.

    Font Awesome ships one 400KB+ face per style covering ~2,000 glyphs. This site
    draws about 140 of them, and a browser downloads the whole face to render any
    one - which is most of the icon cost on a cold load.
    """
    from fontTools import subset

    options = subset.Options()
    options.flavor = "woff2"
    options.desubroutinize = True
    # Font Awesome's ligature/layout tables only matter to its JS renderer, which this
    # site does not use - it writes <i class="fas fa-x"> and lets the CSS `content`
    # rule pick the glyph. Dropping them is most of the saving after the glyphs.
    options.layout_features = []
    options.drop_tables += ["GSUB", "GPOS"]
    options.notdef_outline = True

    font = subset.load_font(source, options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)
    subset.save_font(font, destination, options)
    font.close()


def vendor_font_awesome():
    """Subset Font Awesome to the icons in use and write static/css/icons.css."""
    print(f"Font Awesome {FA_VERSION}")
    css = _fetch(f"{FA_BASE}/css/all.min.css", as_text=True)
    table = parse_icon_table(css)
    if len(table) < 1000:
        sys.exit(f"  ! only parsed {len(table)} icons out of all.min.css - aborting")

    wanted = used_icon_names()
    known = {name: table[name] for name in wanted if name in table}
    unknown = sorted(wanted - set(known))
    print(f"  scanned the tree: {len(known)} icons matched, {len(unknown)} unrecognised")
    if unknown:
        # Not fatal: `fa-` also prefixes a few of this app's own CSS class names.
        print(f"    (ignored: {', '.join(unknown[:8])}{' ...' if len(unknown) > 8 else ''})")

    # Which style owns an icon is decided by where its rule sits in all.min.css: the
    # brands stylesheet is appended after the solid one, so every icon defined past
    # that boundary is a brand mark and everything before it is solid.
    marker = 'font-family:"Font Awesome 6 Brands"'
    if marker not in css:
        sys.exit("  ! could not find the Brands face in all.min.css - aborting")
    brand_icons = set(parse_icon_table(css[css.rindex(marker):]))

    faces, total = [], 0
    for filename, style in FA_FACES.items():
        names = {n for n in known if (n in brand_icons) == (style == "brands")}
        if not names:
            continue
        codepoints = {int(known[n], 16) for n in names}
        raw = _fetch(f"{FA_BASE}/webfonts/{filename}")
        source = os.path.join(FONT_DIR, f"{filename}.orig")
        _write(source, raw)
        destination = os.path.join(FONT_DIR, filename)
        subset_face(source, destination, codepoints)
        os.remove(source)
        size = os.path.getsize(destination)
        total += size
        print(f"  + {filename}: {len(names)} glyphs, {_kb(len(raw))} -> {_kb(size)}")
        family = "Font Awesome 6 Brands" if style == "brands" else "Font Awesome 6 Free"
        weight = 400 if style == "brands" else 900
        faces.append(
            f'@font-face{{font-family:"{family}";font-style:normal;'
            f"font-weight:{weight};font-display:block;"
            f'src:url(/static/fonts/{filename}) format("woff2")}}'
        )

    rules = sorted(f'.{name}:before{{content:"\\{known[name]}"}}' for name in known)
    header = (
        "/* GENERATED by scripts/vendor_assets.py - do not edit.\n"
        f"   Font Awesome Free {FA_VERSION}, subset to the {len(known)} icons this\n"
        "   codebase references. Add an icon to a template and re-run the script,\n"
        "   or it renders as an empty box. Licence: CC BY 4.0 (icons),\n"
        "   SIL OFL 1.1 (fonts) - https://fontawesome.com/license/free */\n"
    )
    _write(
        os.path.join(CSS_DIR, "icons.css"),
        header + "\n".join(faces) + "\n" + BASE_ICON_CSS + "\n".join(rules) + "\n",
    )
    print(f"  = {_kb(total)} of woff2 -> static/css/icons.css")


# The handful of non-glyph rules the markup relies on, lifted from all.min.css. Written
# out here rather than filtered out of the upstream file because that file is 100KB of
# sizing, stacking, rotation and animation utilities, and this codebase uses exactly
# two of them: fa-fw (9 uses) and fa-spin (19).
BASE_ICON_CSS = """
.fa,.fas,.fa-solid,.fab,.fa-brands{-moz-osx-font-smoothing:grayscale;-webkit-font-smoothing:antialiased;display:var(--fa-display,inline-block);font-style:normal;font-variant:normal;line-height:1;text-rendering:auto}
.fa,.fas,.fa-solid{font-family:"Font Awesome 6 Free";font-weight:900}
.fab,.fa-brands{font-family:"Font Awesome 6 Brands";font-weight:400}
.fa-fw{text-align:center;width:1.25em}
.fa-spin{animation-name:fa-spin;animation-duration:var(--fa-animation-duration,2s);animation-iteration-count:var(--fa-animation-iteration-count,infinite);animation-timing-function:var(--fa-animation-timing,linear)}
@media (prefers-reduced-motion:reduce){.fa-spin{animation-delay:-1ms;animation-duration:1ms;animation-iteration-count:1}}
@keyframes fa-spin{0%{transform:rotate(0)}to{transform:rotate(1turn)}}
"""


def vendor_js():
    """Copy the on-demand libraries into static/vendor/."""
    print("On-demand libraries")
    for filename, url in VENDOR_JS.items():
        size = _write(os.path.join(STATIC, "vendor", filename), _fetch(url))
        print(f"  + {filename} ({_kb(size)})")


def main():
    parser = argparse.ArgumentParser(description="Vendor web fonts, icons and libraries into static/.")
    parser.add_argument("--fonts", action="store_true", help="Google Fonts only")
    parser.add_argument("--icons", action="store_true", help="Font Awesome only")
    parser.add_argument("--js", action="store_true", help="on-demand libraries only")
    args = parser.parse_args()

    everything = not (args.fonts or args.icons or args.js)
    if everything or args.fonts:
        vendor_google_fonts()
    if everything or args.icons:
        vendor_font_awesome()
    if everything or args.js:
        vendor_js()
    print("\nDone. Restart the app (or touch a stylesheet) to rebuild static/dist/.")


if __name__ == "__main__":
    main()
