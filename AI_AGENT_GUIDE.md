# AI Agent Guide to the EB Web Project (Flask storefront + admin)

This file exists so another AI (or a developer in a hurry) can work on this
Flask app correctly without re-deriving its conventions from scratch. Read
this before editing routes/templates. For the backend API this app talks
to, see `../store-api/AI_AGENT_GUIDE.md` - that file is authoritative for
data shapes, permissions, and validation; this one covers how the Flask
layer wraps it.

If you are about to add or change an admin feature, read section 0 and
section 3 first - they cover the two patterns almost every admin page
follows.

---

## 0. Orientation - read this first

- **What this is**: a Flask app that is *only* a presentation layer.
  Nothing here reads or writes a database directly - every piece of data
  comes from `store-api` (a separate FastAPI service, default
  `http://localhost:8000`, configured via `STORE_API_BASE_URL`). If a
  change requires new data or a new business rule, it almost always needs
  a change on the store-api side too - check there first.
- **Two account types, one session cookie**: `User` (staff) and
  `Customer` both log in through the same `/login` form
  (`blueprints/auth_routes.py`), which calls store-api's combined
  `POST /auth/login`. The result is stored in Flask's signed session
  cookie (`session["token"]`, `session["account_type"]`,
  `session["account"]`) - see `auth.py`'s module docstring for the exact
  shape. This session token is a store-api JWT; it is attached to every
  outbound store-api call automatically (see section 2).
- **No route touches store-api directly with `requests`.** Every call goes
  through `store_api.get_api_client()` (section 2) so token attachment and
  error normalization stay in one place. If you find yourself importing
  `requests` in a blueprint, stop - that's the wrong pattern here.
- **Decimal-as-string quirk**: store-api serializes `Decimal` fields
  (`price`, `subtotal`, `discount_value`, ...) as JSON *strings*
  (`"209.00"`), not numbers - and the masked-price sentinel is also a
  string (`"XXXX"`). Never touch these fields directly from a raw
  store-api response; always go through `formatting.py`'s `adapt_*`
  helpers first (section 5). This is the single most common source of
  subtle bugs in this codebase (a template silently doing string
  concatenation instead of arithmetic).
- **Ports**: this app defaults to Flask's dev server (`python app.py`,
  port 5000); store-api defaults to port 8000. Both must be running for
  anything beyond a 503 "service unavailable" page.

---

## 1. Authentication & session model

- `auth.py` is the single source of truth for "who is logged in and what
  can they do" on this side. Every helper there (`is_logged_in()`,
  `is_staff()`, `is_customer()`, `has_permission(name)`,
  `can_view_prices()`, `can_quote()`) reads from `session["account"]` -
  **never re-derive these checks inline in a route**, use the helpers.
- These helpers are injected into every Jinja template automatically via
  `register_auth_context()` (called once in `app.py`) - so
  `{% if has_permission('product_management') %}` works in any template
  with no per-view plumbing.
- **This layer is UX only, not authority.** `has_permission()` reads a
  permission snapshot cached in the session at login time - if it's
  revoked mid-session, this cache goes stale until the user logs in
  again. store-api independently re-checks every permission server-side
  on every write (via `require_permission(...)`, see the other guide's
  section 2) and is what actually enforces anything. Never add a
  security check here that isn't *also* enforced by store-api.
- `login_required` / `staff_required` / `permission_required(*names)`
  (all in `auth.py`) are route decorators built on the same helpers.
  `admin_bp` (`blueprints/admin/__init__.py`) applies `staff_required` to
  *every* route on the blueprint via `@admin_bp.before_request` - so an
  individual admin route only needs `@permission_required(...)` on top of
  that when store-api demands more than just "is staff".

## 2. Talking to store-api

- `store_api.get_api_client()` returns a request-scoped `StoreAPIClient`
  (via Flask's `g`) carrying whatever bearer token the session holds (or
  none, for an anonymous visitor). Use its verbs directly:
  `client.get/post_json/put_json/patch_json/delete/post_form`.
- Every store-api failure raises `StoreAPIError` (`.status_code`,
  `.detail` - already normalized to a plain string whether the source was
  a `{"detail": "msg"}` business error or a 422 Pydantic validation-error
  list). The standard pattern in every admin write route:
  ```python
  try:
      client.post_json("/things/", payload)
  except StoreAPIError as e:
      flash(e.detail, "error")
      return redirect(url_for("admin.things"))
  ```
- If store-api is unreachable entirely (connection refused/timeout), the
  client raises `StoreAPIUnavailable` instead (a `StoreAPIError`
  subclass) - this is caught globally by `app.py`'s
  `@app.errorhandler(StoreAPIUnavailable)` and renders
  `service_unavailable.html` with a 503, so individual routes don't need
  to handle it.
- File uploads: build a `files={"file": (filename, stream, mimetype)}`
  dict (see `_file_from_request()` helpers repeated in
  `blueprints/admin/{products,brands,categories,manuals}.py`) and pass it
  to `post_form`/`post_json`'s sibling calls - store-api expects
  `multipart/form-data` for these, never JSON (see the other guide's
  section 3).

## 3. The admin blueprint - the pattern every page follows

Every `blueprints/admin/*.py` module (except `dashboard.py`) follows the
exact same shape - copy the closest existing one (`brands.py` is the
simplest full example) rather than inventing a new structure:

1. A `GET` route with no suffix (e.g. `/admin/products`) that fetches the
   list (+ anything needed for a create-form dropdown, e.g. brands for
   the product form) and renders a template.
2. `POST /.../new` - creates a record, `@permission_required(...)`,
   reads `request.form`, redirects back with a flash message either way.
3. `POST /.../<id>/edit` - same shape, updates.
4. `POST /.../<id>/delete` - same shape, deletes (or soft-deletes, for
   `User`).

The matching template (`templates/admin/*.html`) always:
- `{% extends "admin/_admin_base.html" %}`, fills `admin_content` +
  `extra_js` blocks.
- Renders the list as a plain `<table>` inside `.dash-card .card-body`
  (that's what gives it borders/hover/typography - a bare `<table>`
  outside that wrapper renders unstyled, which is why every admin list
  page nests its table that way).
- A single create/edit modal (`.dash-modal-overlay`/`.dash-modal-box`),
  driven entirely by JS: an `open<Thing>Modal(id?)` function populates the
  form from a `const <THINGS>_DATA = {{ things|tojson }};` blob embedded
  in `extra_js`, and toggles between "create" and "edit" wording/action
  URL based on whether an id was passed. There is no server-rendered edit
  page - it's always this same client-side modal pattern.
- A live client-side search box filtering the table via a `data-search`
  attribute on each `<tr>`, matched against a lowercased search input
  (see `filter<Things>Table()` in each template's `extra_js`).

`templates/partials/admin_sidebar.html` gates each nav group behind
`has_permission(...)` matching whatever permission that section's routes
actually require - if you add a new admin page, add its link there inside
the correctly-permissioned `<div class="nav-group">`, not a new ungated
one.

## 4. Quotes/Orders - the one non-CRUD flow

This is the most involved part of the app; read this before touching
anything quote-related.

- **The public quote flow** (`templates/partials/quote_drawer.html` +
  `static/js/main.js`'s `QuoteCart` object) is a client-side cart (labeled
  "Your Cart" in the UI, though the object/file names still say "quote" -
  not renamed) backed by `localStorage`, gated by `CAN_QUOTE`/`IS_LOGGED_IN`
  globals injected in `base.html` from `can_quote()`/`is_logged_in()`.
  Adding an item, changing quantity, and the special-discount type/value
  selector are all purely local until the user hits "Confirm Purchase".
- **"Confirm Purchase" is really "submit, then print".** It POSTs the cart
  to `blueprints/quote.py`'s `/quote/submit`, which forwards to
  store-api's `POST /orders/` (server re-prices everything, derives
  `salesperson`/`quoted_by_name`, generates `quote_code` (a readable
  `yymmddhhmmss` timestamp, "-N" suffixed on same-second collisions),
  computes the discount - see the other guide's Orders section). **Nothing
  about the quote is persisted until this call succeeds.** Only after a
  successful response does the frontend build the printable PDF - and it
  builds that PDF from the *server's response*, not the local cart, so
  what's printed always matches what's actually on record.
- **Sub-Total/Discount/Special Discount/Grand Total, in both the cart
  drawer and the printed PDF**: Sub-Total is the undiscounted combined list
  price, Discount is the money each product's own (admin-set) discount
  already saved, Special Discount is the separate order-level
  percent/cash discount only `product_management` staff can set
  (`QuoteCart.getDiscountType()/getDiscountValue()`), and Grand Total is
  what's actually charged. Sub-Total/Discount are reconstructed client-side
  via `deriveOldUnitPrice()` (mirrors `formatting.py`'s
  `derive_old_price()`) since store-api only stores the final charged
  `unit_price` + the discount that produced it, never a separate original
  price column.
- `QuoteCart.buildPrintTemplate(order)` and `QuoteCart.exportPDF(suffix)`
  (both in `main.js`) are deliberately split out as reusable, order-only
  functions (no dependency on the local cart/session) - this is what lets
  the admin Orders page's **Print** button (`templates/admin/orders.html`)
  regenerate the exact same PDF for an already-placed order without
  resubmitting anything. If you need to change what the printed quote
  looks like, change `buildPrintTemplate` once - both the storefront
  download and the admin reprint use it.
- Required fields (`clinic_name`, `phone`, `address`) are validated in
  three places on purpose - the HTML `required` attribute
  (`quote_drawer.html`), a JS check in `QuoteCart.confirmPurchase()` (since
  the fetch call bypasses native form validation), and `blueprints/quote.py`'s
  own check before it even calls store-api (which would 422 anyway, but
  with a less friendly message). If you loosen one, loosen all three
  consistently, or a validation gap on the friendliest layer (JS) will
  just surface as a raw store-api error further down.
- `formatting.py`'s `adapt_order()` is the only place that should convert
  `discount_value`/`discount_amount`/`subtotal`/`grand_total` from
  store-api's string-Decimal to real numbers - anything reading an order
  dict downstream (a template, a `tojson` blob) should assume those are
  already real numbers, never raw store-api strings.

## 5. Formatting / display helpers (`formatting.py`)

Exposed as Jinja globals in `app.py` (`img`, `file_url`, `price`,
`format_date`) plus used directly in Python:

| Helper | Use it for |
|---|---|
| `resolve_image_url` (Jinja `img()`) | Any `*_image` field. Handles: full URL (R2) as-is, store-api-relative path (`/static/...`, local-disk fallback) prefixed with store-api's own base URL, or `None` → this app's own 404 placeholder image. |
| `resolve_file_url` (Jinja `file_url()`) | Non-image files (manual PDFs). Same relative-vs-absolute logic, but returns `None` (not a placeholder) when there's nothing to link to - callers must check before rendering a link. |
| `to_number` | Coerces a store-api numeric-as-string field to a real `float`, leaving the masked sentinel `"XXXX"` or `None` untouched. This is the *only* place that distinction should be made. |
| `format_price` (Jinja `price()`) | Safe to call on anything `to_number()` may have produced - real number → `"$1,234.56"`, masked → `"Login to view price"`, `None` → `""`. |
| `format_date` | ISO 8601 string (or `datetime`) → `"Jul 21, 2026"` by default. |
| `adapt_product` / `adapt_promotion` / `adapt_order` | Per-entity adapters - run **once**, immediately after fetching from store-api, before the dict reaches a template or a `tojson` blob. If you fetch a new list of orders/products/promotions somewhere, run it through the matching adapter before doing anything else with it. |

## 6. Common agent mistakes to avoid

1. **Writing a permission check only in `auth.py`/a template and assuming
   that's enough.** It isn't - store-api is the real authority (section
   1). A Flask-only gate is a UX nicety, not security.
2. **Treating a `Decimal` field on a raw store-api response as a number.**
   It's a string until an `adapt_*` helper touches it (section 4/5) - and
   it might be the literal string `"XXXX"` instead of a number at all.
3. **Calling `requests` directly instead of `get_api_client()`.** You'll
   lose token attachment, error normalization, and the 503 fallback for
   free by doing this.
4. **Adding a new admin page without the `has_permission(...)` gate in
   `admin_sidebar.html` and the matching `@permission_required(...)` on
   the write routes.** The blueprint's `before_request` only guarantees
   "is staff", not any specific permission.
5. **Assuming `salesperson`/`quote_code`/`quoted_by_name` on an Order can
   be set from the client.** They can't - store-api derives all three
   server-side (section 4); a Flask route sending them is silently
   ignored (or, since `OrderCreate` doesn't even declare those fields,
   rejected outright if store-api's Pydantic model is stricter).
6. **Editing the printed-quote layout in two places.** There is only one
   place - `QuoteCart.buildPrintTemplate()` in `main.js` - shared by both
   the storefront download and the admin reprint button. Don't duplicate
   the HTML-building logic into `orders.html`'s inline script.
7. **Forgetting `_admin_base.html` doesn't include `quote_drawer.html`.**
   The hidden `#quotePrintTemplate` div and the jsPDF/html2canvas
   `<script>` tags that `buildPrintTemplate`/`exportPDF` depend on are
   added directly in `_admin_base.html` for this reason - if you create a
   new base template that also needs to print, it needs its own copies of
   both.
