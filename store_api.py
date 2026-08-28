"""
Thin HTTP client for store-api (see ../store-api). Every route in this app goes through
this module rather than calling `requests` directly, so token attachment and error
normalization stay in one place.

See store-api/AI_AGENT_GUIDE.md for the full endpoint reference this client wraps.
"""
import base64
import json
import re
import time

import requests
from flask import current_app, g, session


class StoreAPIError(Exception):
    """Normalized store-api failure. `.detail` is always a plain string, whether the
    source was a {"detail": "msg"} business error or a 422 {"detail": [...]} Pydantic
    validation-error list - callers never need to branch on which shape they got."""

    def __init__(self, status_code, detail, payload=None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.payload = payload


class StoreAPIUnavailable(StoreAPIError):
    """The docker compose stack isn't reachable at all (connection refused/timeout) -
    distinct from a normal error response, so callers can show a maintenance message
    instead of a field-level error."""

    def __init__(self):
        super().__init__(None, "The store service is temporarily unavailable. Please try again shortly.")


class SessionExpired(Exception):
    """The bearer token this session was carrying got a 401 from store-api - it passed
    its 24h expiry, or the account behind it was disabled/deleted mid-session.

    Deliberately NOT a StoreAPIError subclass. Every admin route wraps its calls in
    `except StoreAPIError: flash(e.detail, "error")`, so as a subclass this would land
    as a red "Could not validate credentials" banner on the form and leave the browser
    sitting in an admin UI it can no longer write anything through. Living outside that
    hierarchy, it sails past all of those handlers to the app-level handler in app.py,
    which clears the dead session and sends the user to the login page."""


def token_expires_at(token):
    """The `exp` claim (unix seconds) out of a store-api JWT, or None if it can't be
    read.

    The signature is NOT verified - this app doesn't hold store-api's SECRET_KEY and
    shouldn't. That's fine because nothing is *granted* on the strength of this number:
    store-api verifies the token properly on every single call and stays the only
    authority. It's read here purely so this app can stop rendering a signed-in UI at
    the same moment store-api stops honouring the token, rather than finding out one
    failed write at a time. A token whose exp can't be read just falls back to the
    SessionExpired path."""
    try:
        payload = token.split(".")[1]
        # JWT segments are base64url with the padding stripped; put it back.
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except Exception:
        return None
    exp = claims.get("exp")
    return exp if isinstance(exp, (int, float)) else None


def session_token_expired():
    """True when the session holds a token we already know store-api will reject."""
    expires_at = session.get("token_expires_at")
    return bool(expires_at) and time.time() >= expires_at


def _extract_detail(payload):
    if not isinstance(payload, dict):
        return None
    raw = payload.get("detail")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        # 422 Pydantic validation errors: [{"loc": [...], "msg": "...", ...}, ...]
        parts = []
        for err in raw:
            loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
            msg = err.get("msg", "Invalid value")
            parts.append(f"{loc}: {msg}" if loc else msg)
        return "; ".join(parts) if parts else "Invalid request"
    return None


def _raise_for_error(response):
    try:
        payload = response.json()
    except ValueError:
        payload = None
    detail = _extract_detail(payload) or f"store-api returned status {response.status_code}"
    raise StoreAPIError(response.status_code, detail, payload)


# One connection pool for the whole process, shared by every request.
#
# A requests.Session per StoreAPIClient meant a brand-new TCP (and, in a TLS
# deployment, a full handshake) connection for EVERY call to store-api - and a
# single page render makes several - with the socket left to be closed by the
# garbage collector rather than by anyone. Sharing the pool is safe precisely
# because nothing user-specific lives on it: the bearer token is passed per
# request in _request()'s headers, never set on the session.
_http = requests.Session()
_http.mount("http://", requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20))
_http.mount("https://", requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20))


class StoreAPIClient:
    """One instance per request (see get_api_client) - each carries at most one bearer
    token, so nothing from one user's session can bleed into another's request. The
    underlying connection pool (_http) is shared process-wide; the token is not."""

    def __init__(self, base_url, token=None, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.session = _http

    def _headers(self, extra=None):
        headers = dict(extra or {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _send(self, method, path, headers=None, session_auth=True, timeout=None, **kwargs):
        """The checked response object. Every caller goes through here, so the transport
        failure and the two auth rules below are decided in exactly one place - what
        differs between _request and the binary helpers is only how the body is read."""
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(headers),
                timeout=timeout or self.timeout,
                **kwargs,
            )
        except requests.exceptions.RequestException as exc:
            raise StoreAPIUnavailable() from exc

        # A 401 on a call we signed with the session's own token means that token is
        # no longer good - not that the user got something wrong on this form. Raised
        # as SessionExpired so app.py can end the session cleanly instead of every
        # caller flashing "Could not validate credentials" at a form. `session_auth`
        # is False on the auth endpoints, where a 401 really is "wrong password".
        if response.status_code == 401 and self.token and session_auth:
            raise SessionExpired()
        if response.status_code >= 400:
            _raise_for_error(response)
        return response

    def _request(self, method, path, headers=None, session_auth=True, **kwargs):
        response = self._send(method, path, headers=headers, session_auth=session_auth, **kwargs)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    # ---- JSON verbs ----
    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def get_all(self, path, params=None, page_size=500):
        """Every row from a list endpoint, following `skip` until a short page.

        Exists because `limit` is capped server-side at MAX_PAGE_SIZE=500 (see
        store-api/app/core/query.py) and a caller asking for more gets a 422, not
        more rows. Screens that need a *complete* set therefore cannot express that
        as one request - and the failure mode is silent, which is the point of
        having this: before the SAP materials import there were 30-odd categories,
        `limit=500` was indistinguishable from "all of them", and the dropdowns
        built on it were quietly correct. At 854 categories the same call returns a
        truncated list, an edit form renders without the option the product is
        currently set to, and saving that form moves the product to whatever the
        browser selected instead. Nothing raises.

        For dropdowns and pickers, not for tables: fetching 8,000 products this way
        would work and then render an unusable page.
        """
        rows = []
        skip = 0
        while True:
            page = self.get(path, params={**(params or {}), "skip": skip, "limit": page_size})
            if not isinstance(page, list):
                return page
            rows.extend(page)
            # A short page means the end. Guarding on the page being non-empty as
            # well stops a misbehaving endpoint that always returns a full page
            # from looping forever.
            if len(page) < page_size:
                return rows
            skip += page_size

    def post_json(self, path, body=None):
        return self._request("POST", path, json=body or {})

    def put_json(self, path, body=None):
        return self._request("PUT", path, json=body or {})

    def patch_json(self, path, body=None):
        return self._request("PATCH", path, json=body or {})

    def delete(self, path):
        return self._request("DELETE", path)

    # ---- multipart passthrough (browser upload -> store-api) ----
    def post_form(self, path, data=None, files=None):
        return self._request("POST", path, data=data, files=files)

    def post_form_download(self, path, data=None, files=None, timeout=60):
        """Uploads a file and gets a *file* back, as (bytes, content_type, filename) -
        for endpoints whose answer is a document rather than JSON (the admin Reports
        screen's ABA button, POST /reports/aba). `filename` is parsed out of
        Content-Disposition, or None if the endpoint didn't name one.

        Longer default timeout than the JSON verbs: this is a round trip through a file
        parser and a PDF renderer, not a table read, and 10s is tight for a whole
        month's transactions. Errors still arrive as JSON, and _send has already turned
        them into StoreAPIError before this reads a byte of the body."""
        response = self._send("POST", path, data=data, files=files, timeout=timeout)
        disposition = response.headers.get("Content-Disposition", "")
        match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition)
        return (
            response.content,
            response.headers.get("Content-Type", "application/octet-stream"),
            match.group(1) if match else None,
        )

    # ---- auth ----
    def login(self, email, password):
        """POST /auth/login - OAuth2 password-grant, form-encoded (NOT json). Tries a
        staff match first, then Customer; response includes account_type."""
        return self._request(
            "POST",
            "/auth/login",
            data={"username": email, "password": password},
            session_auth=False,
        )

    def google_login(self, credential):
        """POST /auth/google - `credential` is the ID token Google Identity Services
        handed the browser. store-api verifies it against Google's public keys and
        answers with the same shape as login(), signing in an existing staff/customer
        account with that email or creating a customer for it."""
        return self._request("POST", "/auth/google", json={"credential": credential}, session_auth=False)

    def refresh_token(self):
        """POST /auth/refresh - trades the token this client is carrying for a new one
        with a full lifetime ahead of it. Customers only; store-api answers 403 for a
        staff token, whose 24h is deliberately not extendable."""
        return self.post_json("/auth/refresh")

    def register_customer(self, payload):
        return self.post_json("/auth/customer/register", payload)


def get_api_client():
    """Request-scoped client carrying whatever bearer token the current session holds
    (or none, for an anonymous visitor) - built fresh per request via Flask's `g` so a
    stale client is never reused across requests."""
    if "store_api_client" not in g:
        g.store_api_client = StoreAPIClient(
            current_app.config["STORE_API_BASE_URL"],
            token=session.get("token"),
        )
    return g.store_api_client
