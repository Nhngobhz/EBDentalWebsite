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
- **Sessions end when their token does, and the two lengths differ.**
  store-api issues staff tokens good for 24h and customer tokens good for
  14 days. `_establish_session` records the token's `exp` as
  `session["token_expires_at"]`, and `expired_session_gate` (app.py) clears
  the whole session once it passes - so no screen ever renders as
  signed-in while holding a token store-api would reject. The backstop is
  `SessionExpired` (store_api.py), raised on any 401 to a call we signed
  with the session's token; it is deliberately **not** a `StoreAPIError`
  subclass, because every admin route catches that and would swallow it.
  Both paths land in one handler that ends the session and asks for a fresh
  sign-in.
- **A customer's 14 days are 14 days of inactivity.**
  `slide_customer_session` (app.py) re-mints a browsing customer's token via
  `POST /auth/refresh` at most once a day, so an active customer is never
  logged out. Staff are excluded on purpose and store-api refuses to extend
  a staff token anyway - their 24h ends the session whether they were active
  or not. Don't "fix" that asymmetry without reading the note in
  `store-api/app/config.py`.
- **No route touches store-api directly with `requests`.** Every call goes
  through `store_api.get_api_client()` (section 2) so token attachment and
  error normalization stay in one place. If you find yourself importing
  `requests` in a blueprint, stop - that's the wrong pattern here.
  **One module legitimately imports `requests` and is not a violation of
  this**: `maps.py`, which follows a shortened Google Maps link to read the
  coordinates out of it. It never calls store-api - it calls Google - and it
  is the only thing in this app that fetches a URL a *user* supplied, which
  is why it vets the host before every hop (see section 7).
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
- **The post-login `?next=` destination goes through `_safe_next_url()`**
  (`blueprints/auth_routes.py`) and nothing else may use it raw. `next` is
  attacker-supplied - it survives in any link that can be sent to someone - and
  `_establish_session()` feeds it both to `redirect()` and, for the JSON
  logins, to `window.location.href` in the page. Only a plain same-site path
  is accepted: absolute URLs, protocol-relative `//host`, and `javascript:`
  are all dropped back to the default landing page.
- **Session cookie flags are set in `create_app()`**: HttpOnly + SameSite=Lax
  always, and Secure whenever `APP_ENV=production`. Secure is env-gated
  because a Secure cookie is never sent over the local `http://127.0.0.1` dev
  server - turning it on unconditionally makes local login look broken. The
  same flag switches off the Werkzeug debugger in `python app.py`.
- `login_required` / `staff_required` / `permission_required(*names)`
  (all in `auth.py`) are route decorators built on the same helpers.
  `admin_bp` (`blueprints/admin/__init__.py`) applies `staff_required` to
  *every* route on the blueprint via `@admin_bp.before_request` - so an
  individual admin route only needs `@permission_required(...)` on top of
  that when store-api demands more than just "is staff".
- **"Continue with Google"** (added 2026-08-05) is a second way into the
  same session, not a second session model. `partials/google_signin.html`
  (included once by `auth/auth.html`, shared by both its tabs, and
  rendering **nothing** unless `GOOGLE_CLIENT_ID` is configured) lets
  Google Identity Services render its own button; the ID token it produces
  is POSTed to `auth.google_login` (`/auth/google`), which forwards it to
  store-api's `POST /auth/google` and stores the result exactly like a
  password login. Both routes end in `_establish_session(result)` - the one
  place that writes `token`/`account_type`/`account` and picks the
  post-login redirect - so **anything that should happen on login goes
  there, not in `login()`**. This side never verifies anything about the
  Google token; it's store-api that decides whether to believe it (see the
  other guide's 1.6, including why a Google account has no password here).
  `GOOGLE_CLIENT_ID` must be set in **both** apps' `.env` (this one renders
  the button, store-api verifies the token), and every origin the site is
  served from has to be an Authorized JavaScript origin on that Google
  credential or the button silently fails to render.
- `/profile` and `/profile/edit` (`blueprints/auth_routes.py`) serve **both**
  principal types from one pair of templates, switching on `is_staff()` to pick
  `/users/me` vs `/customers/me` and to read `user_name`/`user_image` vs
  `customer_name`/`customer_image`. Everything else on the form
  (`email`, `phone_num`, `address`, `date_of_birth`, `gender`) exists on both
  store-api tables under the same name and needs no branch - `role_title` is
  currently the only staff-only field, and it's guarded with `is_staff()`.
  Before surfacing a new profile field, check whether `users`, `customers`, or
  both actually have it; adding a one-sided field unguarded renders an empty
  row for the other principal type.
- The header avatar opens the **account slide-over**
  (`partials/account_drawer.html`, `AccountDrawer` in `main.js`) rather than
  navigating - `/profile` is still its `href`, so it degrades to a plain link
  without JS. Its Orders tab fetches `/profile/orders`
  (JSON, summary fields only) on **first open**, backed by store-api's
  `GET /orders/mine`; the staff-only `GET /orders/` can't serve it because a
  customer has no `price_listing`. Tapping an order fetches it in full from
  `/profile/orders/<id>` (cached per page view) and shows its line items; its
  **Download PDF** button re-runs `QuoteCart.buildPrintTemplate` + `exportPDF`
  on that payload - the same two calls the admin Orders page's Print button
  makes. Nothing is resubmitted and no PDF is stored: the document is rebuilt in
  the browser every time, so a re-download always matches what's on record.
  The drawer is the quick glance; **the full page is `/my-orders`**
  (`auth.my_orders` → `templates/auth/orders.html`, added 2026-08-17), which
  server-renders the same list with a search box, filter chips and real URLs,
  and `/my-orders/<id>` renders one order in full. That page fetches nothing:
  it IS the list, so a spinner would buy nothing - only its item table is built
  in the browser, by the same `printedItemAmount()`/`deriveOldUnitPrice()`
  helpers, so it can never disagree with the PDF the same page downloads.
  Don't confuse the drawer with the cart "drawer",
  which is really a centered modal - this one actually slides from the edge and
  animates on `transform`, so its hidden state must stay laid out
  (`visibility`, not `display:none`).
- The three decorators fail in three deliberately different ways:
  `login_required` (storefront pages) flashes and redirects to `/login`;
  `staff_required` (the `/admin/*` gate) **`abort(404)`s** so the admin
  area is indistinguishable from a URL that doesn't exist - don't "fix"
  this into a login redirect, it would confirm the URL to a stranger;
  `permission_required` `abort(403)`s, which `app.py`'s handler turns
  into a flash + redirect back to the admin dashboard (only signed-in
  staff can ever reach it).

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
- A store-api 404 on a detail route should become a real Flask 404
  (`except StoreAPIError as e: if e.status_code == 404: abort(404)`, see
  `catalog.product_detail`) so the visitor lands on `not_found.html`
  rather than a 500. `app.py` registers that page for both 404 and 405,
  so any unmatched URL or wrong-verb request renders it.
- File uploads: build a `files={"file": (filename, stream, mimetype)}`
  dict (see `_file_from_request()` helpers repeated in
  `blueprints/admin/{products,brands,categories,manuals}.py`) and pass it
  to `post_form`/`post_json`'s sibling calls - store-api expects
  `multipart/form-data` for these, never JSON (see the other guide's
  section 3). The one endpoint that takes **several** files
  (`POST /products/{id}/gallery`) needs a *list of tuples* instead of a
  dict, since every part reuses the same field name:
  `[("files", (filename, stream, mimetype)), ...]` - see
  `_gallery_files_from_request()` in `blueprints/admin/products.py`.

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

**Escape anything from the server that you build into an HTML string.**
Jinja auto-escapes and `|tojson` is safe, but the JS in these pages assembles
markup by hand and assigns it to `innerHTML` - and `.textContent` is not an
option for a whole table row. Wrap every interpolated server value in
`ebEscapeHtml()` (`main.js`). This matters most where the text is
*customer*-entered rather than admin-entered: the order fields
(`clinic_name`, `address`, `contact_person`, phone, terms) rendered by
`QuoteCart.buildPrintTemplate()` and the admin Orders modal come straight
from a checkout form a stranger filled in.

**Bundle contents pickers (added 2026-07-31)**: three admin modals let an
admin say which products something contains - Promotion "Included
Products", Set "Included Products", and Product "Comes With (Free)". They
all use the same three pieces, so wire a new one the same way rather than
hand-rolling: `ebBundlePicker` (`main.js`) renders/collects the repeatable
rows into parallel `item_product_id`/`item_qty` inputs, the page defines a
`const BUNDLE_PRODUCTS = [...]` blob (id/name/code) for the dropdowns, and
`bundle_items_from_form()` (`blueprints/admin/__init__.py`) reads them back
into store-api's `[{product_id, qty}]` shape. Note the picker submitting
**no rows at all** is meaningful - it posts `[]`, which store-api reads as
"this bundle now contains nothing"; that's why the payload always includes
the key. The Old Price field on a Promotion/Set is only a fallback: once a
bundle lists contents, store-api reports their combined price as `old_price`
and the stored column is ignored (so the modal prefills a number the admin
never typed - that's the computed one, not a bug).

**Set brand (added 2026-08-13)**: a Set can be filed under a Brand
(`brand_id`, optional - see store-api's guide). The admin Sets modal has a
"No brand"-defaulted `<select>`, and the payload always sends the key, as
`None` when blank, so saving can also *clear* a brand. On the storefront it
drives the brand strip above the sets grid on `/promotions`
(`catalog.promotions_page`) - note that page fetches **all** sets and filters
in Python rather than passing `brand_id` to store-api, because the strip is
built from the fetched list so it only ever offers brands that actually have
a set.

`templates/partials/admin_sidebar.html` gates each nav group behind
`has_permission(...)` matching whatever permission that section's routes
actually require - if you add a new admin page, add its link there inside
the correctly-permissioned `<div class="nav-group">`, not a new ungated
one.

**When a screen starts a job rather than saving a record** (added 2026-08-31,
Settings → Catalogue Sync, `templates/admin/_sap_sync_panel.html`): the
post-and-redirect shape above does not fit, because the work outlives the
request - a SAP catalogue sync takes minutes, and a form submit would sit on a
white page until a proxy timeout made a working run look like a failed one. So
that panel does the other thing: two thin JSON routes in
`blueprints/admin/settings.py` (`sap_sync_run`, `sap_sync_status`) pass straight
through to store-api's `/sap-sync`, the button `fetch`es the first, and the page
polls the second every 3 seconds while a run is going. The first paint is still
server-rendered - the `sap_sync` document the view already fetched - so the panel
is filled in before any JS runs, and a run someone started in another browser is
picked up on load. Copy that shape for any future "run it now" button; do not
give a long job a form.

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
- **A cart line can carry `components`** - what it includes for free (a
  promotion/set's member products, or a product's free gifts). They're
  copied into `localStorage` purely so the drawer can list them before an
  order exists (`QuoteCart.renderIncluded`, quantities multiplied by the
  parent line's qty); the real ones are re-derived server-side at purchase
  time and are never read back from the browser.
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
- **Who gets a quote vs. a real order (added 2026-07-29)**: staff carts
  always produce a QUOTE (the button reads "Generate Quote" for them,
  driven by the `IS_STAFF` global from `base.html`); customers must pick a
  **Payment Method** in the drawer (`qiPaymentMethod` select, customers
  only) - **Cash** also produces a quote (quotation PDF downloads
  immediately). **KHQR creates NOTHING until the payment lands (changed
  2026-08-11)** - a customer must never hold an unpaid order. `/quote/submit`
  routes a `khqr` body to store-api's `POST /orders/checkout` and returns
  `{"checkout": {...}}` instead of an order; `confirmPurchase()` sees that key,
  clears the cart and opens the KHQR modal
  (`QuoteCart.showKhqrModal(checkout)` - renders `checkout.khqr_string` via a
  lazy-loaded qrcode.js, same CDN pattern as jsPDF, and shows the checkout
  `reference` where an order number used to go, because there isn't one). It
  polls `/quote/checkout/<id>/payment-status` every 3s, which returns
  `{payment_status, order}`: **the order arrives on the transition to "paid" -
  that poll is what creates it** - and `_finishPaidOrder(data.order)` renders
  the receipt from that server-returned order. A third state, `"expired"`,
  ends the poll and tells the customer nothing was charged. Closing the tab
  loses nothing: store-api's own sweep creates the order if the payment lands
  unwatched. `exportPDF(suffix, docName)` takes the filename word as its
  second arg.
- **Receipt vs. Quotation is `payment_status === 'paid'`, nothing else
  (changed 2026-08-08)**. It used to also require `payment_method === 'khqr'`,
  which meant a quote staff had taken cash for could never print as a
  paid document. That document is titled **Invoice** (it said "Receipt"
  until 2026-08-17 - the `receipt_note_*` setting keys kept their old names),
  and paid rows are badged `Invoice` in the admin list, on `/my-orders` and in
  the account drawer for the same reason. The single-field rule lives in five
  places that must agree: `QuoteCart.buildPrintTemplate()`,
  `AccountDrawer.renderOrders()` / `renderOrderDetail()` / `downloadOrderPDF()`,
  `documentWord()` + `printOrder()` in `admin/orders.html`, the
  `doc_word`/`document_word()` in `auth/order_detail.html` +`auth/orders.html`,
  and store-api's `invoice_pdf.document_title()`. `payment_method` now only
  picks the wording of the paid note ("Paid via KHQR" vs "Paid in full").
- **`payment_status` has a third value, `"refunded"` (added 2026-09-02)**, set
  only by `POST /orders/{id}/refund` (admin only, only on a row that is
  currently `"paid"`), which stamps `refunded_at`/`refund_reason` and leaves
  `paid_at` alone - the payment really happened. Every one of the five places
  above tests **paid OR refunded** for the document word (a refunded row is
  still the Invoice that was issued; the terms box says it was refunded and
  drops the pay-me QR), but **only `"paid"` counts as money**: the admin
  totals strip, `_order_stats()` on the dashboard and the customer's
  "Awaiting payment" count all exclude a refunded row from both halves, the
  way a cancelled one is excluded. `isSettled()`/`isRefunded()` in
  `admin/orders.html` are the JS shorthand for the two tests. The reversal is
  undone by posting `payment_status: "paid"` again (the "Undo refund" button
  reuses `admin.orders_mark_paid`), which clears both columns server-side.
- **The admin Orders page is where staff run an order (reworked
  2026-08-08)**, `templates/admin/orders.html` + `blueprints/admin/orders.py`.
  Type tabs/badges separate quotes from orders, and each row's modal offers:
  **Edit** (a full editor - clinic details, terms, discount, and an items grid
  with a product picker over the catalogue embedded in the page; posts to
  `admin.orders_edit` → `PUT /orders/{id}`, sending only ids + quantities,
  then reloads because the server re-prices everything), **Payment QR**
  (`admin.orders_khqr` → `POST /orders/{id}/khqr`, draws the KHQR with the
  same lazy-loaded qrcode.js and polls `admin.orders_payment_status` every
  3s), and **Mark as Paid** (`admin.orders_mark_paid`, now valid on **any**
  order - counter cash, bank transfer, or a KHQR payment auto-detection
  missed).
- **A settled order is frozen in the UI, and must not pretend otherwise.**
  The page hides Edit, Update Status, Payment QR and Mark as Paid on a paid
  row (`applyOrderLock()` in the modal, a "Locked" chip in the table) and
  leaves Print; a refunded row is locked the same way but keeps its status
  control, because store-api's status freeze covers `"paid"` only - a
  reversed sale is exactly the row whose status still has to move. Delete and
  Refund are the admin-only exceptions (`delete_order`/`refund_order` `403`
  anyone without `admin`). If you add a new order-mutating control, gate it on
  `isSettled(order)` too - the server will refuse most of it regardless, but a
  button that only ever errors is worse than no button.
- **Sub-Total/Discount/Special Discount/Grand Total, in both the cart
  drawer and the printed PDF**: Sub-Total is the undiscounted combined list
  price, Discount is the money each product's own (admin-set) discount
  already saved, Special Discount is the separate order-level
  percent/cash discount only `product_management` staff can set
  (`QuoteCart.getDiscountType()/getDiscountValue()`), and Grand Total is
  what's actually charged. Sub-Total/Discount come from each line's
  **stored** pre-discount price - `deriveOldUnitPrice(item)` (`main.js`) just
  reads `OrderItem.list_price`, and `formatting.py`'s `was_price()` reads
  `Product.list_price`. Neither divides the discount back out any more: that
  reconstruction lived in three places that had to agree, and the figure it
  produced silently moved whenever a price was edited. See store-api's
  `f2a9c4e18b73` migration.

  Two consequences worth knowing when touching this code:
  - `deriveOldUnitPrice()` now takes **the whole item**, not
    `(unitPrice, discount, discountType)`. The cart drawer doesn't call it at
    all - a cart line carries its own `oldPrice`, captured when it was added.
  - The admin Product form's **Price field is the list price**. The blueprint
    sends it as `list_price` and sends `_apply_discount()`'s result as `price`,
    so store-api stores both explicitly rather than inferring either.
- `QuoteCart.buildPrintTemplate(order)` and `QuoteCart.exportPDF(suffix)`
  (both in `main.js`) are deliberately split out as reusable, order-only
  functions (no dependency on the local cart/session) - this is what lets
  the admin Orders page's **Print** button (`templates/admin/orders.html`)
  regenerate the exact same PDF for an already-placed order without
  resubmitting anything. If you need to change what the printed quote
  looks like, change `buildPrintTemplate` once - both the storefront
  download and the admin reprint use it.
- **`exportPDF()` also returns the built PDF as a Blob** (added 2026-07-22,
  alongside triggering the local download it always did) - `confirmPurchase()`
  hands that Blob to `QuoteCart.uploadQuotationPDF(orderId, blob)`, which
  POSTs it (fire-and-forget, errors swallowed) to `/quote/<order_id>/pdf` ->
  store-api's `POST /orders/{id}/quotation-pdf`. This is what lets the
  Telegram order alert carry the *exact* PDF the customer received instead
  of store-api's own fpdf2 approximation (`services/invoice_pdf.py`) - see
  that file's module docstring and `deliver_order_alert()` in
  `services/telegram.py` for the full wait/fallback story. Never awaited and
  never blocks/fails the purchase flow - store-api only waits ~20s for it
  before falling back on its own.
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
| `adapt_product` / `adapt_promotion` / `adapt_set` / `adapt_order` | Per-entity adapters - run **once**, immediately after fetching from store-api, before the dict reaches a template or a `tojson` blob. If you fetch a new list of orders/products/promotions/sets somewhere, run it through the matching adapter before doing anything else with it. |
| `location_link(lat, lng, map_link)` (Jinja `location_link()`) | Lives in `maps.py`, registered as a Jinja global beside the others. The best "open this location" URL for a stored pin: the customer's own pasted link if there is one, otherwise a Google Maps URL built from the coordinates, otherwise `None`. Returning `None` is load-bearing - the caller renders no link rather than a dead one, so every call site needs an `{% if %}`. |
| `was_price(list_price, price)` | The struck-through "was $X", or `None` when there's nothing to strike (no discount, or a masked viewer). `adapt_product` sets `product["was_price"]` from it, which is what templates render and what a cart line stores as `oldPrice`. Replaced `derive_old_price()`, which reconstructed the figure by division - see section 4. |

## 5b. Delivery locations (`maps.py` + the location picker)

A customer's address is free text and always has been; since 2026-08-19 they
can also mark **where** that is. Four moving parts:

- **`maps.py`** - all the URL work. `parse_coordinates()` reads a lat/lng out
  of every Google Maps URL shape (note it prefers the `!3d..!4d..` pair over
  the `@lat,lng` one: on a place page the `@` values are the map's viewport
  centre, not the pin). `expand_short_link()` follows a
  `maps.app.goo.gl/...` link server-side, because that shape carries no
  coordinates at all until the redirect is followed and the browser can't
  follow it (no CORS headers). `location_link()` is the display helper
  (section 5).
- **`blueprints/maps_routes.py`** - `POST /maps/resolve`, login-required, the
  only reason any of this needs a server round trip. **This is the one place
  in the app that fetches a URL a user typed**, so it is deliberately narrow:
  `maps.py` allowlists the hosts it will request *and* re-checks the host at
  every redirect hop, refuses non-80/443 ports, and refuses non-http(s)
  schemes. Without that it is a plain SSRF - "resolve"
  `http://169.254.169.254/` and the server fetches it from inside the network.
  Do not relax the allowlist to "any URL".
- **`templates/partials/location_picker.html` + `static/js/location-picker.js`** -
  the picker macro. It renders three hidden inputs (`latitude`, `longitude`,
  `map_link`) and the UI that fills them; the surrounding `<form>` submits them
  like any other field. Leaflet/OpenStreetMap tiles, lazy-loaded on first use,
  rather than the Google Maps JS API - that one needs a billing-enabled key.
  Two things to know before reusing it:
    * the `picker_id` must be unique on the page - it's the JS registry key;
    * a picker inside a **modal** must be told when it becomes visible
      (`EBLocationPicker.reveal(id)`), or Leaflet measures a hidden container
      and renders a grey void. See `openCustomerModal()` in
      `templates/admin/customers.html`.
- **Cart auto-fill** - `GET /quote/prefill` (`blueprints/quote.py`) returns the
  signed-in customer's saved clinic/phone/address plus their pin's URL;
  `QuoteCart.ensurePrefill()` (main.js) calls it on first drawer open and fills
  **only the blank fields**, so nothing the customer typed is ever overwritten.
  The pin that lands on the order is **not** taken from that request - `submit()`
  reads it off `/customers/me` server-side, because the cart lives in
  localStorage and can be days older than the profile.

Editing surfaces are the customer's own `/profile/edit` and the admin Customers
screen. Deliberately **not** the cart: the pin belongs to the account, not to
one order, and an order's copy is a frozen snapshot of it (`Order.latitude` on
store-api) so it keeps showing where a past delivery went after the customer
moves their pin.

## 5c. The two storefronts (`blueprints/materials.py`)

The site is two shops behind one shell, chosen on the landing screen at `/`:

| | Machinery - "EB Dental Supply" | Materials - "HOME 49" |
|---|---|---|
| Entry | `/machinery` (`main.home`) | `/materials/` (`materials.home`) |
| Catalog | `/products` (`catalog.products_catalog`) | `/materials/catalog` |
| Browse | brand grid + category checkboxes | `/materials/categories`, `/materials/brands` |
| Item | `/products/<id>` | `/materials/<id>` |
| Size | ~110 products, 31 categories, 4 brands | 8,000+ SAP items, 824 categories, 173 brands |
| Photos | every product | one item in 8,125 |

**Never add a materials page by putting a flag on a machinery template.** The
machinery catalog fetches the whole catalog in one `limit=500` call and filters
it in the browser; at 8,000 items that call is a 422 and that page is unusable.
Materials pages therefore page on the server (`GET /products/count` for the
total, `?page=` in the URL) and browse group-first from `GET /products/facets`,
which is the only cheap way to know how many items sit behind a category.

**Which shop a page belongs to** is `site_section()` (app.py), and the header,
bottom nav, footer, hero carousel and promo banner all read it. A route in the
`materials` blueprint is materials; `main.home` and the `/products` routes are
machinery; **everything else - About, Contact, sign-in, the profile - inherits
the last section the visitor was actually in**, remembered in
`session["site_section"]`. That inheritance is the point: without it, clicking
About from the materials store swaps the logo to the machinery mark and strands
the shopper in the other shop. `main.landing` clears it, since that screen is
the chooser.

**A view can override that** - `site_section.override("materials")`, read back by
`_request_section()` and carried into the session by an `after_request` hook. One
endpoint needs it: `/promotions/<id>` serves a machinery bundle or a materials one
depending on the row, and the routing table cannot see the row. Call it before
`render_template`, since the sitewide globals are lazy and resolve during rendering.
It lives in its own module (`site_section.py`) because app.py imports the blueprints,
so a blueprint importing back from app.py would be circular - the same reason
`site_cache.py` is its own file.

**Marketing is per-section too.** `hero_slides.section` and `promotions.section` (both
NOT NULL, defaulting to machinery) decide which shop advertises what, so the
`hero_slides` and `active_promotions` globals are fetched with `section=` and cached
per section - `HERO_SLIDES_CACHE_KEYS` is a pair, and a save clears both, because one
edit can move a slide between shops. The materials front page renders the same
`partials/hero_slider.html` the machinery home does; what differs is the rows it gets.

Both halves share one cart, one quote flow and one buy box - `.pd-buybox`,
`.pd-qty` and `.pd-cta` are borrowed by `templates/materials/detail.html` on
purpose. An item bought from either side has to reach the quote identically.

Two traps in this half specifically:

1. **Don't sum a facet to get a total.** The category facet JOINs categories,
   and 131 materials have none, so the sum is 7,994 against a real 8,125. Use
   `GET /products/count` (`_total_items()`).
2. **`GET /brands/` and `GET /categories/` span both sections.** They return all
   177 brands and all 854 categories with no idea which half each belongs to, so
   a list built from them offers options that lead to an empty grid. That is what
   the footer's brand column used to do. Use the facets.
3. **"Unbranded" is not a brand.** `scripts/sap_sync.py` files every item with an
   empty `U_Brand` under it, which makes it the biggest bucket in the catalogue -
   1,671 items - so any list ordered by size opens with it. It is filtered out of
   places that *recommend* brands (the materials home strip, the footer column; see
   `FALLBACK_BRAND_NAME`) and deliberately left in places that merely *list* them
   (`/materials/brands`, the catalog's filter rail), because those 1,671 items have
   to be reachable by the only name they have.
4. **A category tile draws a glyph, never a photograph.** `category_icon(name,
   override)` guesses from the name via a keyword map and takes the admin's
   `category_icon` column as an override. The `category_image` column is gone. If you
   add a call site, pass the override too - four screens draw these tiles and they
   must not disagree about what a bur looks like.
5. **A brand tile picks its catalogue by stock, not by section preference.** Brands
   straddle the three sections very unevenly - CORICAMA is 1 spare part and 386
   materials, Qualident 2 and 46 - so `_brand_link()` (blueprints/main.py) ranks a
   brand's sections by how many products each holds and uses `brand_link_order()`,
   i.e. the shopper's own shop, only to break a tie. Ranking by preference alone is
   what sent an About-page click on CORICAMA to a spare-parts page with one item on
   it. `carried_brands()` therefore carries `sections` as `{section: count}`, not as
   a list.

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
   The hidden `#quotePrintTemplate` div that `buildPrintTemplate` fills is
   added directly in `_admin_base.html` for this reason - if you create a
   new base template that also needs to print, it needs its own copy.
   jsPDF/html2canvas are NOT `<script>` tags in any base template anymore
   (removed 2026-07-27 for page-load speed) - `QuoteCart._ensurePdfLibs()`
   in `main.js` injects them from cdnjs on the first `exportPDF()` call.
8. **Writing `thing.items` in a Jinja template.** A `Promotion`/`Set` dict
   from store-api carries its contents under the key `items` - and
   `{{ promo.items }}` resolves to the **dict's own `.items` method**, not
   the key, which then blows up with
   `'builtin_function_or_method' object is not iterable`. Always subscript
   it: `promo['items']`. (`free_items` on a product has no such clash.)
9. **Assuming an order's `items` list is only the lines the cart sent.**
   Since 2026-07-31 a promotion/set line expands into its member products
   and a product line into its free gifts, as extra $0 "component" rows in
   the same flat list, each carrying `parent_item_id`. Anything rendering
   order lines (printed quote, admin order modal) must indent/skip-number
   them by that field rather than treating every row as a charged line.
10. **Assuming the sitewide `brands`/`products`/`promotions`/`sets`/
   `active_promotions` template globals are plain lists.** Since 2026-07-27
   they're lazy per-request proxies (`app.py::inject_catalog_globals`) -
   each store-api fetch only fires if the rendered template actually uses
   that variable. They behave like lists inside Jinja (`|length`, iteration,
   truthiness), but don't pass them to `|tojson` or code that needs a real
   `list` - fetch and adapt your own list in the route instead (which also
   shadows the global, skipping the sitewide fetch entirely).
11. **Looking for the storefront product modal.** It's gone (2026-08-06).
   A catalog card is now a plain `<a>` to `/products/<id>`
   (`products/detail.html`), so there is no `PRODUCTS_DATA` blob on the
   catalog page and no `openProductModal()` in `main.js` - the identically
   named function in `admin/products.html` is the admin's own create/edit
   modal and is unrelated. `partials/product_modal.html` was renamed
   `partials/toast.html`, which is all that survived of it.
   That page's image gallery (main picture + store-api's
   `Product.images`) is assembled **in the route**, not the template:
   `catalog.product_detail` resolves every URL through
   `resolve_image_url` and passes one `gallery` list, because both the
   `{% block content %}` markup and the `{% block extra_js %}` blob need
   the same list and a top-level `{% set %}` shared across two blocks is
   exactly the kind of Jinja scoping that quietly breaks.
12. **Adding a second copy of the gallery/lightbox JS.** There is one
   (`static/js/product-gallery.js`, `PdGallery.init([urls])`), shared by
   `products/detail.html` and `products/bundle_detail.html`. A page only
   has to render the same `.pd-gallery` markup - `#pdThumbs` buttons
   carrying `data-index`, `#pdMainImage`, `#pdZoomBtn`, `#pdLightbox*` -
   and call `init` with the same list the thumbnails came from.
13. **Writing a third bundle page.** A `Promotion` and a `Set` share one
   template (`products/bundle_detail.html`) and one route helper
   (`catalog._bundle_detail`), which normalizes either row into
   `bundle`/`name`/`gallery`/`contents` plus a `kind` of `"promotion"` or
   `"set"`. They differ only in which columns hold the name/image and
   whether the deal has dates; keep it that way rather than forking the
   page. Note `contents` is passed separately precisely so the template
   never has to write `bundle.items` (see mistake 8).
