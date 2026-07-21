from flask import Blueprint

from auth import staff_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.before_request
@staff_required
def _require_staff():
    """Applies to every route registered on this blueprint - fixes the original
    mock's complete lack of auth gating on any /admin/* route. Per-route
    permission_required(...) layers stricter checks on top where store-api itself
    demands more than just "is staff" (see each submodule)."""
    return None


# Imported after admin_bp exists (and after the before_request above is registered)
# so each submodule's `from blueprints.admin import admin_bp` / `@admin_bp.route(...)`
# attaches routes to this same blueprint instance.
from blueprints.admin import (  # noqa: E402
    brands,
    categories,
    customers,
    dashboard,
    manuals,
    orders,
    products,
    promotions,
    users,
)
