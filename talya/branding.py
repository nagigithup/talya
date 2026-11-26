"""Brand assets for Frappe's shared website pages."""

import re

import frappe
from frappe.website.utils import clear_cache

LOGO_URL = "/assets/talya/images/talya-center-logo.jpeg"
FAVICON_URL = "/assets/talya/images/talya-center-favicon.ico"

LEGACY_LOGO = re.compile(
	r"(?:https?://[^/\s\"'<>]+)?/(?:assets/talya/images|files)/"
	r"talya-(?:logo(?:-white)?|mark)\.svg(?:\?[^\s\"'<>)]*)?"
)
ICON_LINK = re.compile(r"""<link\b[^>]*\brel\s*=\s*["'](?:shortcut\s+)?icon["'][^>]*>""", re.IGNORECASE)


def replace_legacy_favicon(match):
	link = match.group()
	updated = LEGACY_LOGO.sub(FAVICON_URL, link)
	if link != updated:
		updated = re.sub(r"image/(?:svg\+xml|png|jpeg)", "image/x-icon", updated)
	return updated


def sync_website_branding():
	"""Set Talya defaults and replace legacy logo URLs in existing settings."""
	settings = frappe.get_doc("Website Settings")
	updates = {}
	for field in ("banner_image", "footer_logo", "app_logo", "favicon"):
		current = settings.get(field)
		asset = FAVICON_URL if field == "favicon" else LOGO_URL
		if not current or current == "attach_files" or LEGACY_LOGO.fullmatch(current.strip()):
			updates[field] = asset

	for field in ("brand_html", "banner_html", "head_html"):
		current = settings.get(field) or ""
		updated = ICON_LINK.sub(replace_legacy_favicon, current) if field == "head_html" else current
		updated = LEGACY_LOGO.sub(LOGO_URL, updated)
		if current != updated:
			updates[field] = updated

	if updates:
		frappe.db.set_single_value("Website Settings", updates)
		clear_cache()
