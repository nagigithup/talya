import csv
import hashlib
from pathlib import Path

import frappe

from talya.inquiries import require_reception

no_cache = True
sitemap = 0


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/patient_inquiries"
		raise frappe.Redirect(http_status_code=302)
	require_reception()
	from talya.inquiry_labels import LABELS

	context.language = "en" if frappe.form_dict.get("lang") == "en" else "ar"
	context.direction = "ltr" if context.language == "en" else "rtl"
	context.labels = {label: frappe._(label, lang=context.language) for label in LABELS}
	# Prefer Talya's catalogue over conflicting translations in other installed apps.
	if context.language == "ar":
		with open(frappe.get_app_path("talya", "translations", "ar.csv")) as source:
			catalogue = dict(csv.reader(source))
		context.labels.update({key: catalogue[key] for key in LABELS if key in catalogue})
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.sitename = frappe.local.site
	context.socket_port = frappe.conf.socketio_port or 9000
	context.development = bool(frappe.conf.developer_mode)
	context.manager = "System Manager" in frappe.get_roles()
	context.versions = {}
	for kind in ("css", "js"):
		path = Path(frappe.get_app_path("talya", "public", kind, "patient-inquiries." + kind))
		context.versions[kind] = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
