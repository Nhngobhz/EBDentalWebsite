"""
The admin Activity Log screen (Analytics -> Activity Log in the sidebar).

Every change anyone makes to the store, newest first, with the old value beside the
new one. The entries are written by store-api's flush listener (app/core/activity.py
over there); this module only carries filters across and renders what comes back.

Read-only in the strictest sense: there is no route here that writes, because there is
no endpoint on the other side that would accept one. An append-only log with an admin
screen that could edit it would answer no question worth asking.

Gated on `admin` alone, not the price_listing-or-admin pair the rest of Analytics
uses. The log spans every table at once - staff accounts, permissions, prices,
customers' addresses - so it is an owner's view, and store-api enforces the identical
rule, which makes this decorator the UX layer rather than the security boundary.
"""
from datetime import date

from flask import jsonify, render_template, request

from auth import permission_required
from blueprints.admin import admin_bp
from formatting import (
    activity_action,
    activity_entity_icon,
    activity_entity_label,
    activity_field_label,
)
from store_api import StoreAPIError, get_api_client

ACTIVITY_PERMISSION = "admin"

# Entries per page. Matched to what the screen can show without becoming a scroll
# marathon; the pager does the rest.
PAGE_SIZE = 50

# The filters passed through to store-api. Empty values are dropped rather than sent
# as "": a cleared date box means "no bound", and store-api's OptionalDate would
# otherwise have to guess which.
FILTER_FIELDS = ("actor_type", "actor_user_id", "action", "entity_type", "date_from", "date_to", "q")

# Filters whose shape store-api validates and rejects with a 422. The <select> and
# <input type="date"> controls can't produce a bad one, but a hand-edited or stale
# bookmarked URL can - and an unreadable query string should leave the screen usable
# rather than turning it into an error page.
DATE_FILTERS = ("date_from", "date_to")
INT_FILTERS = ("actor_user_id",)


def _filters():
    """The filters from the query string, with any that store-api would reject dropped.

    Silently, and on purpose: the alternative is flashing "date_from was ignored" at
    somebody who did not type it. `q` and the rest are free text either way - store-api
    parameterizes them, so there is nothing here to sanitize beyond parseability.
    """
    filters = {}
    for field in FILTER_FIELDS:
        value = (request.args.get(field) or "").strip()
        if not value:
            continue
        if field in DATE_FILTERS:
            try:
                date.fromisoformat(value)
            except ValueError:
                continue
        elif field in INT_FILTERS:
            if not value.isdigit():
                continue
        filters[field] = value
    return filters


@admin_bp.route("/activity")
@permission_required(ACTIVITY_PERMISSION)
def activity():
    client = get_api_client()
    filters = _filters()

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        # A hand-edited ?page=abc is a typo, not an error worth a flash message.
        page = 1

    params = dict(filters)
    params["skip"] = (page - 1) * PAGE_SIZE
    params["limit"] = PAGE_SIZE

    result = client.get("/activity/", params=params)
    # Derived from the log's own contents, so the dropdowns can never offer a filter
    # that matches nothing.
    options = client.get("/activity/filters")

    total = result.get("total", 0)
    return render_template(
        "admin/activity.html",
        entries=result.get("items", []),
        total=total,
        page=page,
        page_size=PAGE_SIZE,
        page_count=max(1, -(-total // PAGE_SIZE)),
        filters=filters,
        options=options,
        # Passed in rather than registered as Jinja globals: these four are only ever
        # used by this one template, and the global namespace is shared by every page
        # on the site.
        entity_label=activity_entity_label,
        entity_icon=activity_entity_icon,
        action_label=activity_action,
        field_label=activity_field_label,
    )


@admin_bp.route("/activity/entity/<entity_type>/<int:entity_id>")
@permission_required(ACTIVITY_PERMISSION)
def activity_entity(entity_type, entity_id):
    """One record's history, as JSON, for the History panel on its admin screen.

    Fetched on demand rather than embedded with the page: most visits to the Products
    screen never open a history, and a page that shipped one per row would carry
    hundreds of entries nobody reads.

    A store-api error answers with an empty list and a message rather than a non-200,
    so the panel can say "couldn't load history" in place of the browser console
    being the only place that knows.
    """
    client = get_api_client()
    try:
        entries = client.get(f"/activity/entity/{entity_type}/{entity_id}")
    except StoreAPIError as e:
        return jsonify({"entries": [], "error": e.detail})
    return jsonify({"entries": entries})
