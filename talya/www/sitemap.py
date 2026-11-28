import frappe

from talya.seo import sitemap_links

no_cache = 1
sitemap = 0
base_template_path = "www/sitemap.xml"


def get_context(context):
	context.links = sitemap_links()
	if not context.links:
		# Do not publish an unconfirmed hostname or an arbitrary request Host.
		context.http_status_code = 503
		frappe.local.response_headers["Retry-After"] = "600"
	return context
