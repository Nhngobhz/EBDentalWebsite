"""
Session-based auth for this Flask app.

Flask's own session secret (FLASK_SECRET_KEY) signs the session cookie and is
completely separate from store-api's own SECRET_KEY (which signs JWTs) - never conflate
the two.

After a successful login (see blueprints/auth_routes.py), the session holds:
  session["token"]        - the store-api bearer token, attached to every outbound
                             request by store_api.get_api_client()
  session["token_expires_at"] - unix seconds; when that token stops being accepted.
                             app.py's expired_session_gate clears the whole session
                             once it passes, so no screen here ever renders as
                             signed-in while holding a token store-api would reject.
  session["account_type"] - "user" (staff) or "customer"
  session["account"]      - {id, name, email, permissions: {...}} for staff, or
                             {id, name, email, access_permission} for customers
  session["account_synced_at"] - unix seconds; when the dict above was last re-read
                             from store-api. See sync_session_account(), which keeps
                             those cached entitlements from outliving the real ones.
"""
import time
from functools import wraps

from flask import abort, flash, redirect, session, url_for

from store_api import StoreAPIError, get_api_client


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


# How long a cached `session["account"]` may go without being checked against
# store-api. Deliberately short: the dict holds entitlements (a customer's VIP
# access_permission, a staff member's permissions) that an admin can change at any
# moment, and until this existed a change only took effect at the account's *next
# login* - up to fourteen days away for a customer, whose token slides.
#
# The case that made this necessary: every customer self-registers with
# access_permission=False, and a staff member ticks "Can view real prices (VIP)"
# afterwards. store-api reads that column fresh on every request, so real prices
# appeared on the product page immediately - but can_quote() read the stale copy
# here, so the buy box kept offering "Contact us for pricing" to a customer who was
# by then entitled to buy. Prices said yes and the button said no.
#
# One store-api call per minute per signed-in visitor, against the several every
# page render already makes.
SESSION_ACCOUNT_TTL = 60


def build_session_account(kind, user=None, customer=None):
    """The `session["account"]` dict, built from a store-api UserOut/CustomerOut.

    One builder for every way an account reaches this app - password login, Google
    sign-in, and the periodic re-read in sync_session_account() - so a field added
    here can't be missing from a session established by one of the other routes."""
    if kind == "user":
        return {
            "id": user["id"],
            "name": user["user_name"],
            "email": user["email"],
            "role_title": user["role_title"],
            "image": user.get("user_image"),
            "permissions": {
                "user_management": user["user_management"],
                "price_listing": user["price_listing"],
                "product_management": user["product_management"],
                "customer_management": user["customer_management"],
                # .get, not [...]: a session established against a store-api that
                # predates the `admin` column would KeyError on every login otherwise.
                "admin": user.get("admin", False),
            },
        }
    return {
        "id": customer["id"],
        "name": customer["customer_name"],
        "email": customer["email"],
        "image": customer.get("customer_image"),
        "access_permission": customer["access_permission"],
    }


def sync_session_account(force=False):
    """Re-read the signed-in account from store-api into the session, at most once
    every SESSION_ACCOUNT_TTL seconds. Returns True when the dict was refreshed.

    Called from app.py's before_request for every page, and with force=True at the
    one place where being wrongly denied actually costs something (quote.submit),
    so a customer granted VIP access thirty seconds ago isn't turned away by a
    cached "no" that store-api itself would have said yes to.

    Never raises on a store-api failure: the cached account is stale, not wrong, and
    a blip in the API shouldn't sign anybody out. SessionExpired is deliberately NOT
    caught - a token store-api has stopped honouring should end the session now,
    exactly as it does in app.py's slide_customer_session."""
    if not is_logged_in():
        return False
    kind = account_type()
    if kind not in ("user", "customer"):
        return False
    if not force and time.time() - (session.get("account_synced_at") or 0) < SESSION_ACCOUNT_TTL:
        return False

    # Stamped before the call, not after: with store-api unreachable every page still
    # renders (the catalog globals fall back to empty lists), and stamping only on
    # success would add a failing request of its own to every one of those.
    session["account_synced_at"] = time.time()
    try:
        # The bearer token's own account row, which comes back in exactly the shape
        # the login response carried - which is what lets one builder take either.
        fresh = get_api_client().get("/users/me" if kind == "user" else "/customers/me")
    except StoreAPIError:
        return False
    session["account"] = build_session_account(
        kind,
        user=fresh if kind == "user" else None,
        customer=None if kind == "user" else fresh,
    )
    return True


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
