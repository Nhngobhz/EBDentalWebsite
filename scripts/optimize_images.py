"""Re-encode the bundled images at the size they are actually drawn at.

Why this exists
---------------
The images in `static/images/` were dropped in at whatever size they arrived from the
designer or the brand's website, and nothing has ever resized them. Measured before
this script existed:

  * 25 brand logos, every one a 1000x1000 PNG, 4.7MB in total - drawn as 140px tiles
    on the About page's marquee, all of them, on one page load.
  * `eb.png`, the favicon, a 1000x1000 PNG of 184KB - fetched by every browser on
    every page, to be drawn in a 16px tab.
  * `Main logo.png`, 1870x662 and 390KB, for a logo on the maintenance page.

That is roughly 5MB of decoration on a LAN where the whole catalogue is a few hundred
KB of JSON. Nothing about it was visible as "slowness" on a dev machine with the files
on local disk, which is why it survived this long.

How it works
------------
Originals are moved into an `_originals/` folder next to the file the first time this
runs, and every re-encode reads from there. That makes the script idempotent: running
it twice does not re-compress an already-compressed JPEG twice, and the pristine
source is still on disk if a size here turns out to be too small.

`_originals/` is deliberately inside `static/`. It costs disk (about 5MB) and nothing
else - `_brand_logo_files()` in blueprints/main.py skips directories, and no route
serves the folder by name.

Two rules about filenames
-------------------------
  * The fixed logos keep their exact filename AND format. They are named literally in
    a dozen templates and in formatting.py, so a `.webp` rename would be a wide edit
    for no gain - a resized PNG is already 90% smaller.
  * The brand logos DO become `.webp`, and the source `.png` is deleted. Nothing names
    them individually; blueprints/main.py globs the folder. That deletion is not
    optional: `_brand_logo_files()` keys tiles by filename stem, so leaving both
    `komet.png` and `komet.webp` in place would draw Komet twice.

Usage
-----
    python scripts/optimize_images.py          # re-encode everything
    python scripts/optimize_images.py --check  # report sizes, write nothing

Needs Pillow (build-time only, see requirements-dev.txt). The Flask app does not
import it.
"""
import argparse
import os
import shutil

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
IMAGES = os.path.join(PROJECT, "static", "images")
ORIGINALS = "_originals"

# (path relative to static/images, longest edge in px, why that number).
#
# The sizes are twice what the CSS asks for, so the images stay sharp on the retina
# and 150%-scaled Windows displays the shop runs on, and no larger - a third copy of
# the pixels buys nothing a phone can see.
FIXED = [
    # .header-logo-img is 40px tall / 210px wide (css/shell.css:251).
    ("machinery-logo.png", 420, "header + footer + sign-in logo, drawn <=210px wide"),
    ("home-49.png", 420, "the materials shop's half of the same two slots"),
    # .avatar fallback in the account drawer and profile pages, ~120px.
    ("eb-logo.png", 300, "avatar placeholder, drawn <=140px"),
    # .maint-logo on the maintenance page.
    ("Main logo.png", 600, "maintenance page letterhead"),
    # formatting.py:36 - stands in for any product with no photograph, which on the
    # materials side is most of 8,000 of them.
    ("404 no image.png", 480, "product-card placeholder, drawn <=240px"),
    # css/landing.css:8, a full-bleed background on the section chooser.
    ("landing-bg.jpg", 1920, "full-width landing background"),
]

# The favicon is its own case: one source, two outputs, and the 1000px original is
# useless at both sizes. 180px is what iOS wants for a home-screen icon; 32px is what
# a browser tab actually draws, and shipping it separately means the tab costs about
# 1KB instead of the 180px file's 12.
FAVICON_SOURCE = "eb.png"
FAVICON_SIZES = [("eb.png", 180), ("favicon-32.png", 32)]

# The About page marquee draws these as 140px tiles (_BRAND_TILE_PITCH_PX in
# blueprints/main.py). 280 is the 2x of that.
BRAND_DIR = "brands"
BRAND_MAX = 280
BRAND_QUALITY = 82

JPEG_QUALITY = 80


def _kb(n):
    return f"{n / 1024:6.0f}KB"


def original_of(path):
    """The pristine source for `path`, moving it into `_originals/` on first sight.

    Every re-encode reads from here rather than from the live file. Encoding from the
    previous output would mean each run of this script degrades the image a little
    further - invisible once, obvious after five deploys.

    Matched on the filename *stem*, not the full name, because a brand logo changes
    extension on the way through (`komet.png` -> `komet.webp`) and its source PNG is
    then deleted. Keyed on the full name, the second run would find no original for
    `komet.webp`, file the 280px webp as the pristine source, and quietly lose the
    1000px PNG as the thing a future re-encode starts from.
    """
    folder, filename = os.path.split(path)
    stem = os.path.splitext(filename)[0]
    kept_dir = os.path.join(folder, ORIGINALS)

    if os.path.isdir(kept_dir):
        for candidate in sorted(os.listdir(kept_dir)):
            if os.path.splitext(candidate)[0] == stem:
                return os.path.join(kept_dir, candidate)

    os.makedirs(kept_dir, exist_ok=True)
    kept = os.path.join(kept_dir, filename)
    shutil.copy2(path, kept)
    return kept


def _resized(image, longest_edge):
    if max(image.size) <= longest_edge:
        return image
    scale = longest_edge / max(image.size)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.LANCZOS)


def _keep_smaller(destination, source):
    """Undo the re-encode when it made the file bigger, restoring the original.

    Not hypothetical: `landing-bg.jpg` arrived as an already well-compressed 2048px
    JPEG, and re-encoding it at 1920/q80 produced a *larger* file. Any lossy encoder
    can lose this bet on an input that was already tuned, and a script whose whole
    job is to shrink things should never be the reason a file grew.
    """
    if os.path.getsize(destination) >= os.path.getsize(source):
        shutil.copy2(source, destination)
        return os.path.getsize(destination), True
    return os.path.getsize(destination), False


def _save_png(image, destination):
    """Write a PNG, palette-quantised when that is both smaller and safe.

    Logos are flat colour and quantise to 256 entries with no visible change, which is
    most of the saving on top of the resize. Photographs do not - so the quantised
    version is only kept when it actually wins, and the check is on bytes rather than
    on a guess about what the picture contains.
    """
    image.save(destination, "PNG", optimize=True)
    plain = os.path.getsize(destination)

    try:
        # FASTOCTREE rather than the default MEDIANCUT: it is the only one of Pillow's
        # methods that carries an alpha channel through, and every logo here is a
        # cut-out on transparency.
        quantised = image.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
    except (ValueError, OSError):
        return plain

    candidate = f"{destination}.q.tmp"
    quantised.save(candidate, "PNG", optimize=True)
    if os.path.getsize(candidate) < plain:
        os.replace(candidate, destination)
    else:
        os.remove(candidate)
    return os.path.getsize(destination)


def process_fixed(check):
    print("Fixed images (filename and format preserved)")
    before = after = 0
    for name, longest_edge, why in FIXED:
        path = os.path.join(IMAGES, name)
        if not os.path.exists(path):
            print(f"  ? {name} - missing, skipped")
            continue
        source = original_of(path)
        start = os.path.getsize(source)
        before += start
        reverted = False
        with Image.open(source) as image:
            resized = _resized(image, longest_edge)
            if check:
                end = start
            elif name.lower().endswith((".jpg", ".jpeg")):
                resized.convert("RGB").save(path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
                end, reverted = _keep_smaller(path, source)
            else:
                _save_png(resized.convert("RGBA"), path)
                end, reverted = _keep_smaller(path, source)
            dimensions = f"{resized.width}x{resized.height}"
        after += end
        note = "left as-is, already smaller" if reverted else why
        print(f"  {_kb(start)} -> {_kb(end)}  {dimensions:>10}  {name}  ({note})")
    return before, after


def process_favicon(check):
    print("Favicon")
    source_path = os.path.join(IMAGES, FAVICON_SOURCE)
    if not os.path.exists(source_path):
        print("  ? eb.png missing, skipped")
        return 0, 0
    source = original_of(source_path)
    start = os.path.getsize(source)
    after = 0
    for name, size in FAVICON_SIZES:
        destination = os.path.join(IMAGES, name)
        if check:
            after += os.path.getsize(destination) if os.path.exists(destination) else 0
            continue
        with Image.open(source) as image:
            end = _save_png(_resized(image.convert("RGBA"), size), destination)
        after += end
        print(f"  {_kb(start)} -> {_kb(end)}  {size:>4}px      {name}")
    return start, after


def process_brands(check):
    print(f"Brand logos -> webp, longest edge {BRAND_MAX}px")
    folder = os.path.join(IMAGES, BRAND_DIR)
    before = after = 0
    for filename in sorted(os.listdir(folder), key=str.lower):
        path = os.path.join(folder, filename)
        stem, ext = os.path.splitext(filename)
        if os.path.isdir(path) or ext.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        source = original_of(path)
        start = os.path.getsize(source)
        before += start
        destination = os.path.join(folder, f"{stem}.webp")
        if check:
            after += os.path.getsize(destination) if os.path.exists(destination) else start
            continue
        with Image.open(source) as image:
            _resized(image.convert("RGBA"), BRAND_MAX).save(
                destination, "WEBP", quality=BRAND_QUALITY, method=6
            )
        end = os.path.getsize(destination)
        after += end
        # The source PNG has to go, or the marquee draws this brand twice - see the
        # module docstring.
        if ext.lower() != ".webp":
            os.remove(path)
        print(f"  {_kb(start)} -> {_kb(end)}  {stem}.webp")
    return before, after


def main():
    parser = argparse.ArgumentParser(description="Re-encode static images at display size.")
    parser.add_argument("--check", action="store_true", help="report only, write nothing")
    args = parser.parse_args()

    totals = [
        process_fixed(args.check),
        process_favicon(args.check),
        process_brands(args.check),
    ]
    before = sum(b for b, _ in totals)
    after = sum(a for _, a in totals)
    saved = before - after
    print(
        f"\n{_kb(before).strip()} of source images -> {_kb(after).strip()} "
        f"({saved / before:.0%} smaller, {_kb(saved).strip()} saved)"
    )
    if not args.check:
        print(f"Originals kept in static/images/{ORIGINALS}/ and brands/{ORIGINALS}/.")


if __name__ == "__main__":
    main()
