"""
Thin HTTP client for store-api (see ../store-api). Every route in this app goes through
this module rather than calling `requests` directly, so token attachment and error
normalization stay in one place.

See store-api/AI_AGENT_GUIDE.md for the full endpoint reference this client wraps.
"""
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


class StoreAPIClient:
    """One instance per request (see get_api_client) - each carries at most one bearer
    token, so nothing from one user's session can bleed into another's request."""

    def __init__(self, base_url, token=None, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.session = requests.Session()

    def _headers(self, extra=None):
        headers = dict(extra or {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method, path, headers=None, **kwargs):
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(headers),
                timeout=self.timeout,
                **kwargs,
            )
        except requests.exceptions.RequestException as exc:
            raise StoreAPIUnavailable() from exc

        if response.status_code >= 400:
            _raise_for_error(response)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    # ---- JSON verbs ----
    def get(self, path, params=None):
        return self._request("GET", path, params=params)

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

    # ---- auth ----
    def login(self, email, password):
        """POST /auth/login - OAuth2 password-grant, form-encoded (NOT json). Tries a
        staff match first, then Customer; response includes account_type."""
        return self._request(
            "POST",
            "/auth/login",
            data={"username": email, "password": password},
        )

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
