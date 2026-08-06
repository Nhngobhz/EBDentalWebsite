from datetime import date
from urllib.parse import urlparse

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from auth import account_type, current_account, is_staff, login_required
from store_api import StoreAPIError, get_api_client

auth_bp = Blueprint("auth", __name__)


def _safe_next_url(candidate):
    """The `?next=` destination, but only if it points back into this site.

    `next` is attacker-supplied: it survives in the URL of any link ("log in to
    see prices") that can be sent to someone. Handing it to redirect() unchecked
    is an open redirect - `/login?next=https://evil.example/login` sends a user
    who just signed in to a convincing copy of this site. Worse here, the
    JSON-mode logins hand it to `window.location.href` in login.html /
    register.html / google_signin.html, so a `javascript:` value would execute in
    the page that already holds the freshly-authenticated session.

    Only a plain path on this origin is allowed: no scheme, no host, and no
    protocol-relative "//evil.example" (which a bare startswith("/") check would
    happily accept). Anything else falls back to the normal landing page."""
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return None
    if not candidate.startswith("/") or candidate.startswith("//"):
        return None
    return candidate


def _wants_json():
    return request.headers.get("Accept") == "application/json" or request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _build_session_account(account_type, user=None, customer=None):
    if account_type == "user":
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
            },
        }
    return {
        "id": customer["id"],
        "name": customer["customer_name"],
        "email": customer["email"],
        "image": customer.get("customer_image"),
        "access_permission": customer["access_permission"],
    }


def _establish_session(result):
    """Everything a successful authentication has in common, whichever way the account
    was proven - a password (POST /login) or a Google ID token (POST /auth/google).
    Both get back the same store-api LoginResponse shape. Returns where to send the
    browser next."""
    session["token"] = result["access_token"]
    session["account_type"] = result["account_type"]
    session["account"] = _build_session_account(
        result["account_type"], user=result.get("user"), customer=result.get("customer")
    )
    flash(f"Welcome back, {session['account']['name']}!", "success")

    next_url = _safe_next_url(request.args.get("next"))
    if next_url:
        return next_url
    if result["account_type"] == "user":
        return url_for("admin.dashboard")
    return url_for("main.home")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    wants_json = _wants_json()
    if not email or not password:
        if wants_json:
            return jsonify({"success": False, "reason": "invalid", "detail": "Please enter both email and password."}), 400
        flash("Please enter both email and password.", "error")
        return render_template("auth/login.html"), 400

    client = get_api_client()
    try:
        result = client.login(email, password)
    except StoreAPIError as e:
        if wants_json:
            # Distinguishes "account exists but hasn't confirmed their email yet" (which
            # the login page's JS turns into a polling loading screen - see
            # templates/auth/login.html) from any other login failure.
            reason = "unverified" if "confirm your email" in e.detail.lower() else "invalid"
            return jsonify({"success": False, "reason": reason, "detail": e.detail}), (e.status_code or 400)
        flash(e.detail, "error")
        return render_template("auth/login.html"), (e.status_code or 400)

    redirect_url = _establish_session(result)
    if wants_json:
        return jsonify({"success": True, "redirect_url": redirect_url})
    return redirect(redirect_url)


@auth_bp.route("/auth/google", methods=["POST"])
def google_login():
    """Sign in / sign up with Google. Always JSON in and out - Google Identity
    Services renders its own button (templates/partials/google_signin.html) and hands
    the page a signed ID token, which this route forwards to store-api. The token, not
    a password, is the credential; store-api is what verifies Google actually issued it
    and decides which account it belongs to."""
    payload = request.get_json(silent=True) or {}
    credential = (request.form.get("credential") or payload.get("credential") or "").strip()
    if not credential:
        return jsonify({"success": False, "detail": "Google sign-in didn't return an account. Please try again."}), 400

    client = get_api_client()
    try:
        result = client.google_login(credential)
    except StoreAPIError as e:
        return jsonify({"success": False, "detail": e.detail}), (e.status_code or 400)

    return jsonify({"success": True, "redirect_url": _establish_session(result)})


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("auth/forgot_password.html")

    email = request.form.get("email", "").strip()
    if not email:
        flash("Please enter your email address.", "error")
        return render_template("auth/forgot_password.html"), 400

    client = get_api_client()
    # The email could belong to either a staff (User) or Customer account - both
    # endpoints return the same generic "if that email exists" message regardless
    # of whether it actually matches anything, so calling both is safe and never
    # leaks which account type (or whether any account) exists for this email.
    for path in ("/auth/forgot-password", "/auth/customer/forgot-password"):
        try:
            client.post_json(path, {"email": email})
        except StoreAPIError:
            pass

    flash("If that email exists in our system, a password reset link has been sent.", "success")
    return redirect(url_for("auth.login"))

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("auth/register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    wants_json = _wants_json()

    if not name or not email or not password:
        if wants_json:
            return jsonify({"success": False, "detail": "Name, email, and password are required."}), 400
        flash("Name, email, and password are required.", "error")
        return render_template("auth/register.html"), 400

    payload = {
        "customer_name": name,
        "email": email,
        "password": password,
        "phone_num": phone or None,
        "address": address or None,
    }
    client = get_api_client()
    try:
        client.register_customer(payload)
    except StoreAPIError as e:
        if wants_json:
            return jsonify({"success": False, "detail": e.detail}), (e.status_code or 400)
        flash(e.detail, "error")
        return render_template("auth/register.html"), (e.status_code or 400)

    # JSON callers (register.html's fetch-based submit) move straight into the
    # waiting-for-confirmation screen using the credentials just submitted - see
    # templates/auth/register.html - instead of redirecting to /login and making the
    # user retype what they just entered.
    if wants_json:
        return jsonify({"success": True})

    flash("Account created! Check your email for a verification link before logging in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "success")
    return redirect(url_for("main.home"))

@auth_bp.route("/profile", methods=["GET"])
@login_required
def profile():
    client = get_api_client()
    me_path = "/users/me" if is_staff() else "/customers/me"
    try:
        me = client.get(me_path)
    except StoreAPIError as e:
        flash(e.detail, "error")
        me = current_account()
    return render_template("auth/profile.html", me=me)


@auth_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def profile_edit():
    client = get_api_client()
    me_path = "/users/me" if is_staff() else "/customers/me"

    if request.method == "POST":
        payload = {
            "email": request.form.get("email", "").strip(),
            "phone_num": request.form.get("phone", "").strip() or None,
            "address": request.form.get("address", "").strip() or None,
            # Sent as explicit nulls when blank (rather than omitted) so clearing
            # either field on the form actually clears it - store-api only touches
            # the keys the payload includes.
            "date_of_birth": request.form.get("date_of_birth", "").strip() or None,
            "gender": request.form.get("gender", "").strip() or None,
        }
        # The only field that differs between the two principal types - everything
        # above exists on both `users` and `customers` under the same name.
        name_field = "user_name" if account_type() == "user" else "customer_name"
        payload[name_field] = request.form.get("name", "").strip()
        try:
            updated = client.put_json(me_path, payload)
        except StoreAPIError as e:
            flash(e.detail, "error")
            return redirect(url_for("auth.profile_edit"))

        if account_type() == "user":
            session["account"]["name"] = updated["user_name"]
            session["account"]["email"] = updated["email"]
        else:
            session["account"]["name"] = updated["customer_name"]
            session["account"]["email"] = updated["email"]
        session.modified = True

        flash("Profile updated successfully. If you changed your email, check your inbox to confirm it.", "success")
        return redirect(url_for("auth.profile"))

    try:
        me = client.get(me_path)
    except StoreAPIError as e:
        flash(e.detail, "error")
        me = current_account()

    # Caps the birthday date-picker client-side; store-api rejects a future date
    # regardless, this just stops the user hitting that error in the first place.
    return render_template("auth/profile_edit.html", me=me, today=date.today().isoformat())


@auth_bp.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not current_password or not new_password:
        flash("Please fill in all password fields.", "error")
        return redirect(url_for("auth.profile"))
    if new_password != confirm_password:
        flash("New password and confirmation do not match.", "error")
        return redirect(url_for("auth.profile"))

    path = "/users/me/change-password" if account_type() == "user" else "/customers/me/change-password"
    client = get_api_client()
    try:
        client.post_json(path, {"current_password": current_password, "new_password": new_password})
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("auth.profile"))

    flash("Password updated successfully.", "success")
    return redirect(url_for("auth.profile"))

@auth_bp.route("/profile/image", methods=["POST"])
@login_required
def profile_image():
    file = request.files.get("image")
    if not file or file.filename == "":
        flash("Please choose an image to upload.", "error")
        return redirect(url_for("auth.profile"))

    path = "/users/me/image" if is_staff() else "/customers/me/image"
    client = get_api_client()
    try:
        updated = client.post_form(path, files={"file": (file.filename, file.stream, file.mimetype)})
    except StoreAPIError as e:
        flash(e.detail, "error")
        return redirect(url_for("auth.profile"))

    session["account"]["image"] = updated.get("user_image") if is_staff() else updated.get("customer_image")
    session.modified = True

    flash("Profile picture updated.", "success")
    return redirect(url_for("auth.profile_edit"))