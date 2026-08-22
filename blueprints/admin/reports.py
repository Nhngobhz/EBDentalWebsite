"""
The admin Reports screen (Analytics -> Reports in the sidebar).

One card so far: ABA. It takes the raw merchant transaction export ABA hands you as an
.xlsx and gives back the refined PDF - the seven columns that matter, landscape, one
line per transaction - which the owner used to produce by deleting columns in Excel and
printing. All of the actual work happens in store-api (POST /reports/aba); this file
only carries the upload across and streams the answer back to the browser as a download.

Gated on price_listing OR admin, the same pair the Orders screen uses - store-api
re-checks the identical rule, so this decorator is the UX layer, not the security one.

Nothing is stored: the PDF is built, sent, and forgotten. Re-running the same
spreadsheet always produces the same document, so there is nothing here worth a table.
"""
import io

from flask import flash, redirect, render_template, request, send_file, url_for

from auth import any_permission_required
from blueprints.admin import admin_bp
from store_api import StoreAPIError, get_api_client

REPORTS_PERMISSIONS = ("price_listing", "admin")


@admin_bp.route("/reports")
@any_permission_required(*REPORTS_PERMISSIONS)
def reports():
    return render_template("admin/reports.html")


@admin_bp.route("/reports/aba", methods=["POST"])
@any_permission_required(*REPORTS_PERMISSIONS)
def reports_aba():
    file = request.files.get("workbook")
    if not file or not file.filename:
        flash("Choose the ABA .xlsx file first.", "error")
        return redirect(url_for("admin.reports"))
    if not file.filename.lower().endswith(".xlsx"):
        flash("That isn't an .xlsx file - upload the Excel export ABA gives you.", "error")
        return redirect(url_for("admin.reports"))

    client = get_api_client()
    try:
        pdf, content_type, download_name = client.post_form_download(
            "/reports/aba",
            files={"file": (file.filename, file.stream, file.mimetype)},
        )
    except StoreAPIError as e:
        # store-api's 400s here are written for whoever picked the file ("That export is
        # missing the column(s)..."), so they're shown as-is rather than replaced with a
        # generic failure.
        flash(e.detail, "error")
        return redirect(url_for("admin.reports"))

    # send_file, not a redirect: the refined PDF only exists in this response. The
    # browser saves it under the name store-api derived from the upload, which is the
    # same name the hand-made copies already carry.
    return send_file(
        io.BytesIO(pdf),
        mimetype=content_type or "application/pdf",
        as_attachment=True,
        download_name=download_name or "ABA_Merchant_transaction_report.pdf",
    )
