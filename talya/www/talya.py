from hashlib import sha256
from pathlib import Path

import frappe

from talya.api import _public_practitioners


no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.full_width = True
	context.title = "Talya Medical Center | Medicine & Dentistry"
	context.description = "Quality medicine, dentistry and family healthcare in Ras Al Khaimah."
	context.practitioners = _public_practitioners()
	context.csrf_token = frappe.sessions.get_csrf_token()
	# Raw app assets are served immutable by Frappe Cloud. Version the slider's
	# dependencies from their actual content so cached releases cannot mix.
	context.asset_versions = {
		asset: sha256(Path(frappe.get_app_path("talya", "public", asset)).read_bytes()).hexdigest()[:12]
		for asset in (
			"css/talya.css", "js/talya.js", "js/hero-slider.js",
			"images/dr-farouq.png", "images/dr-mehira-original.webp",
		)
	}
	return context
