"""
Session-based auth for this Flask app.

Flask's own session secret (FLASK_SECRET_KEY) signs the session cookie and is
completely separate from store-api's own SECRET_KEY (which signs JWTs) - never conflate
the two.

After a successful login (see blueprints/auth_routes.py), the session holds:
  session["token"]        - the store-api bearer token, attached to every outbound
                             request by store_api.get_api_client()
  session["account_type"] - "user" (staff) or "customer"
  session["account"]      - {id, name, email, permissions: {...}} for staff, or
                             {id, name, email, access_permission} for customers
"""
from functools import wraps

from flask import abort, flash, redirect, session, url_for


def current_account():
    return session.get("account")


def account_type():
    return session.get("account_type")


def is_logged_in():
    return "token" in session


def is_staff():
    return is_logged_in() and account_type() == "user"


def is_customer():
    return is_logged_in() and account_type() == "customer"


def has_permission(name):
    """Staff-only. A UX shortcut (hide/disable buttons the user can't use anyway) -
    store-api independently re-checks every permission server-side on every write and
    remains the real authority, so a stale cached permission here (e.g. revoked
    mid-session) can never grant more than store-api itself allows."""
    if not is_staff():
        return False
    return bool(current_account().get("permissions", {}).get(name))


def has_any_permission(*names):
    """True when the staff member holds AT LEAST ONE of `names`.

    The Orders area is the case this exists for: sales staff reach it through
    `price_listing`, the owner through `admin` (which is "runs this store", not a job,
    so it is deliberately not implied by the other four). Same UX-only status as
    has_permission - store-api re-checks with require_any_permission on every call."""
    if not is_staff():
        return False
    permissions = current_account().get("permissions", {})
    return any(bool(permissions.get(name)) for name in names)


def can_view_prices():
    """Mirrors store-api's own get_price_visibility (app/core/deps.py): any active
    staff member regardless of which permissions they hold, or a customer with
    access_permission=True."""
    if is_staff():
        return True
    if is_customer():
        return bool(current_account().get("access_permission"))
    return False


def can_quote():
    """Narrower than can_view_prices() - who may use the "Add to Quote" cart / place an
    order. Staff need price_listing OR product_management specifically; a
    user_management/customer_management-only staffer sees real prices (per
    can_view_prices) but still can't quote. Customers need access_permission, same as
    price visibility. This is a UX gate mirroring store-api's own server-side
    enforcement in routers/orders.py (_get_ordering_principal) - store-api remains the
    real authority since /quote/submit forwards to a real POST /orders/ call."""
    if is_staff():
        perms = current_account().get("permissions", {})
        return bool(perms.get("price_listing") or perms.get("product_management"))
    if is_customer():
        return bool(current_account().get("access_permission"))
    return False


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_logged_in():
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def staff_required(view):
    """Gate for the whole /admin/* area (applied once in blueprints/admin/__init__.py).

    Deliberately 404s instead of bouncing to the login page: a redirect to /login
    confirms to any stranger that the URL they guessed is a real admin page. Anyone who
    isn't signed-in staff - anonymous visitor or logged-in customer alike - gets exactly
    the same "page not found" they'd get from any made-up URL, so the admin area is
    invisible rather than merely locked. Staff who *are* signed in reach it normally;
    per-route permission_required(...) still 403s them with a real message when they're
    missing a specific permission."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_staff():
            abort(404)
        return view(*args, **kwargs)

    return wrapped


def permission_required(*names):
    """Stack on top of the admin blueprint's staff-only gate - 403s unless the
    logged-in staff member's cached permissions include ALL of `names`."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not is_staff():
                abort(403)
            if not all(has_permission(name) for name in names):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def any_permission_required(*names):
    """Like permission_required, but ANY one of `names` is enough - the OR to its AND.

    Used by the Orders screen, which both `price_listing` (sales staff) and `admin`
    (the owner) must be able to open. Mirrors store-api's require_any_permission, which
    is the actual authority; this only decides whether the page renders."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not has_any_permission(*names):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def register_auth_context(app):
    """Same pattern as this app's existing inject_brands/inject_promotions context
    processors - makes these helpers available in every template automatically."""

    @app.context_processor
    def inject_auth_helpers():
        return {
            "current_account": current_account,
            "is_logged_in": is_logged_in,
            "is_staff": is_staff,
            "is_customer": is_customer,
            "has_permission": has_permission,
            "has_any_permission": has_any_permission,
            "can_view_prices": can_view_prices,
            "can_quote": can_quote,
        }
