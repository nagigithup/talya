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
	return context
