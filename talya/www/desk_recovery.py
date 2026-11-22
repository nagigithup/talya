"""Recover stale Desk navigation without clearing login or user drafts."""

import frappe

no_cache = True


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/desk_recovery"
		raise frappe.Redirect(http_status_code=302)
	if frappe.get_cached_value("User", frappe.session.user, "user_type") != "System User":
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	frappe.local.response_headers.set("Clear-Site-Data", '"cache"')
	frappe.local.response_headers.set("Cache-Control", "no-store")
	context.target = "/desk?talya_recovered=" + frappe.generate_hash(length=12)
