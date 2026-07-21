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
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_logged_in():
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        if not is_staff():
            abort(403)
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
            "can_view_prices": can_view_prices,
            "can_quote": can_quote,
        }
