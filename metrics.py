"""
Prometheus instrumentation for the storefront.

This is the half of the monitoring that sees real people. Every browser hit ends at
waitress here; the Flask app then calls store-api server-to-server holding one bearer
token, so store-api's own metrics show this server's address on every request and can
never answer "how many visitors" or "which pages". Only this side can. Treat the two
as answering different questions rather than as a duplicate measurement:

    storefront_*   what visitors did
    http_*         what the storefront asked the API for, and how slow that was

Metric names carry a `storefront_` prefix for exactly that reason - the panels in
deploy/monitoring/ that say "traffic" mean these, and mixing the two families in one
graph would double-count every page view.

/metrics answers 404 without `Authorization: Bearer <METRICS_TOKEN>`. Port 5000 is
open to the whole office LAN and the firewall is off, and an ungated endpoint here
would publish the admin URL structure - every /admin/... rule that exists, by name -
to anyone who asked. Same reasoning as store-api/app/core/metrics.py, which holds
the longer version.

Single process, so plain in-memory counters are correct: the service runs
`waitress-serve --listen=0.0.0.0:5000 app:app`, which is threaded but not forked.
Adding a process-per-core server later means switching prometheus_client into
multiprocess mode, or every scrape returns one arbitrary process's numbers.

Each app gets its own CollectorRegistry rather than prometheus_client's global one.
That global is why a second `create_app()` in the same process silently produced an
app with no metrics at all: registering a metric name twice raises, and
prometheus_flask_exporter treats that as "already done" and quietly skips installing
its hooks - so the app served fine and every panel stayed empty, with nothing logged.
A per-app registry means a test fixture (or anything else) can build as many apps as
it likes and each one measures itself.
"""
import os
import secrets

from flask import Response, abort, request
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from prometheus_flask_exporter import PrometheusMetrics

# The Flask endpoint name of the scrape route, so app.py's before_request gates can
# recognise it. Prometheus is not a browser: it has no session, it is not staff, and
# it must keep being answered while the site is in maintenance mode - which is
# precisely when someone wants to look at the dashboards.
METRICS_ENDPOINT = "prometheus_metrics"

# Matched against request.path. Static assets are the overwhelming majority of hits
# and the least interesting: a page view already counts once, and counting its
# eighteen images again turns the traffic graph into a measure of how many <img> tags
# the design has.
EXCLUDED_PATHS = (r"^/static/", r"^/metrics$", r"^/favicon\.ico$")

# Wider at the top than store-api's: this side's slowest responses are the ones that
# waited on a chain of API calls, and the catalogue pages under a cold cache sit in
# the 1-3s band that the API's own buckets would flatten.
LATENCY_BUCKETS = (0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, float("inf"))


def endpoint(req):
    """The label value grouping requests together - and, via `__name__`, the label's
    name too (that is how prometheus_flask_exporter names it).

    The URL *rule*, never `request.path`: the raw path would mint a permanent time
    series per product id, so one crawl of the 8,000-item materials catalogue would
    leave 8,000 series in Prometheus' memory forever. The rule collapses those to a
    single `/materials/<int:product_id>`.

    Anything that matched no route at all is folded into one bucket for the same
    reason - a scanner trying /wp-login.php, /.env, /admin.php is not worth a series
    per guess - while still being countable, since a spike in unmatched requests is
    itself worth seeing.
    """
    rule = req.url_rule
    return rule.rule if rule is not None else "<unmatched>"


def setup_metrics(app):
    """Instrument `app` and register the scrape endpoint.

    No-op unless METRICS_TOKEN is set, so a development run carries no instrumentation
    and publishes no endpoint. Returns the PrometheusMetrics instance, or None.
    """
    token = os.environ.get("METRICS_TOKEN", "").strip()
    if not token:
        return None

    registry = CollectorRegistry()
    metrics = PrometheusMetrics(
        app,
        registry=registry,
        # None, so the library doesn't register its own wide-open /metrics; the gated
        # one below takes that path instead.
        path=None,
        group_by=endpoint,
        defaults_prefix="storefront",
        excluded_paths=list(EXCLUDED_PATHS),
        default_latency_as_histogram=True,
        buckets=LATENCY_BUCKETS,
    )

    @app.route("/metrics", endpoint=METRICS_ENDPOINT)
    def prometheus_metrics():
        header = request.headers.get("Authorization", "")
        scheme, _, credentials = header.partition(" ")
        # compare_digest, not ==, so the token can't be recovered a character at a
        # time from how long the comparison takes.
        if scheme.lower() != "bearer" or not secrets.compare_digest(credentials, token):
            abort(404)
        # content_type=, not mimetype=: Flask appends its own charset to a
        # mimetype, and CONTENT_TYPE_LATEST already carries one - the result is a
        # header ending "charset=utf-8; charset=utf-8".
        return Response(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)

    return metrics
