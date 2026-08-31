# EB Web Project — storefront and admin UI

The Flask half of EB Dental Supply: the public catalogue (machinery + HOME 49
materials), the quote/cart flow, and the staff admin dashboard. It holds no database
of its own — every read and write goes through **store-api** over HTTP.

**Deploying this? Don't start here.** The whole install, update and troubleshooting
story for both apps lives in [`../README.md`](../README.md).

## Run it locally

store-api must be up first (see [`../store-api/README.md`](../store-api/README.md) —
`docker compose up -d` is the short version).

```powershell
python -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt

copy .env.example .env
# then set FLASK_SECRET_KEY, and STORE_API_BASE_URL if store-api is not on
# localhost:8000

.\venv\Scripts\python.exe app.py     # http://127.0.0.1:5000
```

`python app.py` runs Werkzeug's development server. Production uses waitress — see
the root README.

## Front-end assets

Three generated things, and only one of them rebuilds by itself:

| Path | Built by | When to rebuild |
|---|---|---|
| `static/dist/` | `assets.py`, automatically at startup | never by hand — edit `static/css/` and `static/js/` |
| `static/css/fonts.css`, `static/css/icons.css`, `static/fonts/`, `static/vendor/` | `scripts/vendor_assets.py` | after adding an icon, or changing a font or library version |
| `static/images/` | `scripts/optimize_images.py` | after adding or replacing an image |

Both scripts need build-time-only packages the app itself does not import:

```powershell
python -m pip install fonttools brotli pillow
python scripts\vendor_assets.py
python scripts\optimize_images.py
```

The fonts and Font Awesome are **self-hosted**: the icon font is subset to the ~149
icons this codebase actually references, so the site renders with no external requests
at all. The catch is that the subset is built from a scan of the source tree — **add an
icon to a template and it renders as an empty box until you re-run
`vendor_assets.py`.** Each script's docstring explains the rest.

`optimize_images.py` keeps pristine sources in `static/images/_originals/` and always
re-encodes from those, so running it repeatedly never degrades an image.

## Where things are

| Path | What |
|---|---|
| `app.py` | app factory, gzip, caching, context processors, error handlers |
| `blueprints/` | routes — `main`, `catalog`, `materials`, `auth_routes`, `quote`, `admin/` |
| `store_api.py` | the only HTTP client for store-api; token handling and error normalisation |
| `formatting.py` | price/date formatting and image-URL resolution |
| `site_cache.py`, `site_settings.py` | short-TTL cache for the data every page's shell needs |
| `assets.py` | CSS/JS bundling into `static/dist/` |
| `templates/`, `static/` | Jinja templates and assets |

[`AI_AGENT_GUIDE.md`](AI_AGENT_GUIDE.md) is the full reference for this app.
