import frappe

from talya.seo import robots_text

no_cache = 1
sitemap = 0
base_template_path = "www/robots.txt"


def get_context(context):
	existing = (
		frappe.db.get_single_value("Website Settings", "robots_txt")
		or (frappe.conf.get("robots_txt") and frappe.read_file(frappe.conf.robots_txt))
		or ""
	)
	context.robots_txt = robots_text(existing)
	return context
