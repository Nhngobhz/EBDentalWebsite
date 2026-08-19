"""
The Hero Slider screen: the rotating banner at the top of the home page and the
products catalog.

Those slides used to be three hard-coded <div class="slide"> blocks in
templates/partials/hero_slider.html, so changing a headline or swapping the artwork
meant a code change. They are rows in store-api's `hero_slides` table now (see
app/models.py::HeroSlide) and this is their CRUD screen.

Gated on `product_management`, the same permission as Promotions and Sets: a hero
slide is shop-window marketing written by whoever writes the promotions, not a system
setting (store-api enforces the identical check, so this decorator is the UX layer).

Create posts multipart so the artwork arrives with the slide; edits send JSON and, when
a new file was chosen, follow it with the separate image upload - the same two-step the
Brands and QR Codes screens use.
"""
import site_cache
from flask import flash, redirect, render_template, request, url_for

from auth import permission_required
from blueprints.admin import admin_bp
from blueprints.main import HERO_SLIDES_CACHE_KEY
from store_api import StoreAPIError, get_api_client

HERO_PERMISSION = "product_management"


def _back():
    return url_for("admin.hero_slides")


def _form_fields():
    """The editable fields as store-api wants them.

    Optional text fields use `or None` so clearing one in the form actually erases it -
    an omitted key would leave the old value in place (see store-api's exclude_unset).

    `is_active` is read as "was the checkbox present", which is the only way an unticked
    checkbox can be told from a field the form never had: browsers simply don't submit
    an unchecked box.
    """
    try:
        sort_order = int((request.form.get("sort_order") or "0").strip())
    except ValueError:
        sort_order = 0

    return {
        "heading": request.form.get("heading", "").strip(),
        "heading_highlight": request.form.get("heading_highlight", "").strip() or None,
        "subheading": request.form.get("subheading", "").strip() or None,
        "badge_label": request.form.get("badge_label", "").strip() or None,
        "badge_icon": request.form.get("badge_icon", "").strip() or None,
        "button_label": request.form.get("button_label", "").strip() or None,
        "button_url": request.form.get("button_url", "").strip() or None,
        "is_active": bool(request.form.get("is_active")),
        "sort_order": sort_order,
    }


def _as_form_value(value):
    """Multipart can only carry strings, so the two Python values that aren't one have
    to be spelled out: None becomes "" (store-api blanks it back to NULL on the way in -
    see _blank_to_none there) and a bool becomes the literal FastAPI parses back.

    Only needed on create. Edits go out as JSON, which has both.
    """
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return value


def _file_from_request():
    file = request.files.get("file")
    if file and file.filename:
        return {"file": (file.filename, file.stream, file.mimetype)}
    return None


@admin_bp.route("/hero-slides")
def hero_slides():
    """Lists every slide, parked ones included - `active_only` is left off deliberately,
    since switching one back on is exactly what an admin comes here to do."""
    client = get_api_client()
    try:
        slides = client.get("/hero-slides/", params={"limit": 200})
    except StoreAPIError as e:
        flash(e.detail, "error")
        slides = []
    return render_template("admin/hero_slides.html", hero_slides=slides)


@admin_bp.route("/hero-slides/new", methods=["POST"])
@permission_required(HERO_PERMISSION)
def hero_slides_new():
    fields = _form_fields()
    if not fields["heading"]:
        flash("Heading is required.", "error")
        return redirect(_back())

    data = {key: _as_form_value(value) for key, value in fields.items()}

    client = get_api_client()
    try:
        client.post_form("/hero-slides/", data=data, files=_file_from_request())
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(_back())

    site_cache.invalidate(HERO_SLIDES_CACHE_KEY)
    flash(f"Slide '{fields['heading']}' created.", "success")
    return redirect(_back())


@admin_bp.route("/hero-slides/<int:slide_id>/edit", methods=["POST"])
@permission_required(HERO_PERMISSION)
def hero_slides_edit(slide_id):
    fields = _form_fields()
    if not fields["heading"]:
        flash("Heading is required.", "error")
        return redirect(_back())

    client = get_api_client()
    try:
        client.put_json(f"/hero-slides/{slide_id}", fields)
        files = _file_from_request()
        # No file chosen means "keep the current artwork" - only an actual upload
        # replaces it, so editing a headline can't wipe the picture.
        if files:
            client.post_form(f"/hero-slides/{slide_id}/image", files=files)
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(_back())

    site_cache.invalidate(HERO_SLIDES_CACHE_KEY)
    flash("Slide updated.", "success")
    return redirect(_back())


@admin_bp.route("/hero-slides/<int:slide_id>/toggle", methods=["POST"])
@permission_required(HERO_PERMISSION)
def hero_slides_toggle(slide_id):
    """Show/hide without opening the editor - the one field an admin flips often
    enough that a round trip through the modal is friction. A partial update, so
    nothing else on the row is touched."""
    client = get_api_client()
    show = request.form.get("is_active") == "1"
    try:
        client.put_json(f"/hero-slides/{slide_id}", {"is_active": show})
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(_back())

    site_cache.invalidate(HERO_SLIDES_CACHE_KEY)
    flash("Slide shown on the storefront." if show else "Slide hidden from the storefront.", "success")
    return redirect(_back())


@admin_bp.route("/hero-slides/<int:slide_id>/delete", methods=["POST"])
@permission_required(HERO_PERMISSION)
def hero_slides_delete(slide_id):
    client = get_api_client()
    try:
        client.delete(f"/hero-slides/{slide_id}")
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(_back())

    site_cache.invalidate(HERO_SLIDES_CACHE_KEY)
    flash("Slide deleted.", "success")
    return redirect(_back())
