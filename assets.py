"""Static asset bundling.

Every page used to pull nine separate stylesheets - the union of everything any
route might need - which meant nine round trips and ~220KB of CSS even on a page
like sign-in that uses a fraction of it. This module concatenates them into one
bundle per page family, written to `static/dist/` and linked with `css_bundle()`
in the templates.

Two rules govern what goes in a bundle:

- **Order is preserved exactly.** CSS cascades, so `responsive.css` overriding
  `products.css` only works while it is still loaded after it. Each bundle below
  lists its files in the same relative order the old <link> tags had; a bundle
  drops files it doesn't need but never reorders the ones it keeps.
- **Files are copied verbatim, not minified.** gzip (see app.py) does the bulk of
  the shrinking, and a rewriting minifier is a source of silent visual bugs for a
  few percent more. `url(...)` references in the sources are absolute
  (`/static/images/...`), so moving the concatenation into `dist/` is safe.

`static/dist/` is generated - it is rebuilt on startup and gitignored. Edit the
files in `static/css/`, never the bundles.
"""
import os

# Page families. The storefront and the admin dashboard render different shells,
# and sign-in/register render the storefront shell but none of its content CSS -
# which is the whole point of splitting, since those are the pages that should
# feel instant.
CSS_BUNDLES = {
    # Storefront content pages: home, catalog, product/promotion detail, about,
    # contact, profile, error pages. auth.css is in here because it carries the
    # .edit-profile-* / .profile-view-* card styles the profile pages use, not just
    # the sign-in form.
    "store.css": [
        "base.css",
        "layout.css",
        "home.css",
        "auth.css",
        "shell.css",
        "products.css",
        # The delivery-location picker on /profile/edit. Small, and only the
        # storefront and admin bundles carry it - the sign-in pages have no
        # picker on them.
        "location-picker.css",
        "responsive.css",
        "loader.css",
    ],
    # Sign-in / register / forgot-password. Same shell (header, bottom nav,
    # footer, drawers, toast) minus home.css and products.css - ~110KB of catalog
    # styling those pages never use.
    "auth.css": [
        "base.css",
        "layout.css",
        "auth.css",
        "shell.css",
        "responsive.css",
        "loader.css",
    ],
    # Admin dashboard (templates/admin/_admin_base.html). No public header or
    # footer, but showToast()/the print template still come from the shared CSS.
    "admin.css": [
        "base.css",
        "layout.css",
        "dashboard.css",
        "shell.css",
        "products.css",
        "location-picker.css",
        "responsive.css",
        "loader.css",
    ],
}

# lang-dropdown.js is one DOMContentLoaded callback with nothing at file scope,
# so appending it to main.js can't collide with main.js's top-level functions -
# and those have to stay top-level, since the inline scripts in the templates
# call them (ebValidateForm, showToast, ebConfirm, ...).
JS_BUNDLES = {
    "app.js": ["main.js", "lang-dropdown.js"],
}

DIST_DIR = "dist"


def _sources(static_folder, kind, names):
    return [os.path.join(static_folder, kind, name) for name in names]


def _newest_source_mtime(paths):
    return max((os.stat(p).st_mtime for p in paths), default=0)


def _write_bundle(static_folder, kind, bundle_name, sources):
    """Concatenate `sources` into static/dist/<bundle_name>, skipping the write when
    the bundle is already newer than every source it is built from."""
    out_path = os.path.join(static_folder, DIST_DIR, bundle_name)
    source_paths = _sources(static_folder, kind, sources)

    try:
        # This file's own mtime counts as an input: editing the lists above changes
        # what belongs in a bundle without touching any stylesheet, and a staleness
        # check that only looked at the sources would happily keep serving the old
        # contents.
        if os.stat(out_path).st_mtime >= max(
            _newest_source_mtime(source_paths), os.stat(__file__).st_mtime
        ):
            return
    except OSError:
        pass  # not built yet

    parts = []
    for path in source_paths:
        with open(path, encoding="utf-8") as f:
            # The banner is what makes a 200KB concatenation debuggable - without
            # it, a rule in devtools points at "dist/store.css line 3120" and
            # there's no way back to the file you're supposed to edit.
            parts.append(f"/* ==== {kind}/{os.path.basename(path)} ==== */\n{f.read()}\n")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Written aside and moved into place, so a second process starting at the same
    # moment can never be served a half-written bundle.
    tmp_path = f"{out_path}.{os.getpid()}.tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(parts))
    os.replace(tmp_path, out_path)


def build(static_folder):
    """(Re)build every bundle. Cheap enough to call on each request in debug - it
    stats the sources and only rewrites a bundle whose input actually changed."""
    for bundle_name, sources in CSS_BUNDLES.items():
        _write_bundle(static_folder, "css", bundle_name, sources)
    for bundle_name, sources in JS_BUNDLES.items():
        _write_bundle(static_folder, "js", bundle_name, sources)


def register(app):
    """Build the bundles now, and - in debug only - again before each request, so
    editing a stylesheet shows up on the next refresh instead of needing a restart."""
    build(app.static_folder)

    @app.before_request
    def _rebuild_bundles():
        # app.debug is read here rather than around the decorator on purpose:
        # app.run(debug=...) sets it *after* create_app() has returned, so a check
        # at registration time always sees False and the hook is never installed -
        # which leaves every CSS/JS edit invisible until the next process restart.
        if app.debug:
            build(app.static_folder)

    @app.context_processor
    def _inject_bundle_helpers():
        def css_bundle(name):
            return f"{DIST_DIR}/{name}"

        def js_bundle(name):
            return f"{DIST_DIR}/{name}"

        return {"css_bundle": css_bundle, "js_bundle": js_bundle}
