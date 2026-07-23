from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from store_api import StoreAPIError, get_api_client

auth_bp = Blueprint("auth", __name__)


def _wants_json():
    return request.headers.get("Accept") == "application/json" or request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _build_session_account(account_type, user=None, customer=None):
    if account_type == "user":
        return {
            "id": user["id"],
            "name": user["user_name"],
            "email": user["email"],
            "role_title": user["role_title"],
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
        "access_permission": customer["access_permission"],
    }


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

    session["token"] = result["access_token"]
    session["account_type"] = result["account_type"]
    session["account"] = _build_session_account(
        result["account_type"], user=result.get("user"), customer=result.get("customer")
    )
    flash(f"Welcome back, {session['account']['name']}!", "success")

    next_url = request.args.get("next")
    if next_url:
        redirect_url = next_url
    elif result["account_type"] == "user":
        redirect_url = url_for("admin.dashboard")
    else:
        redirect_url = url_for("main.home")

    if wants_json:
        return jsonify({"success": True, "redirect_url": redirect_url})
    return redirect(redirect_url)


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
