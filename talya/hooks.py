app_name = "talya"
app_title = "Talya"
app_publisher = "Talya"
app_description = "Talya Healthcare Management Platform"
app_email = "dev@talya.local"
app_license = "mit"

required_apps = ["erpnext", "healthcare"]

home_page = "talya"
after_install = "talya.setup.after_install"
after_migrate = "talya.setup.after_migrate"

fixtures = [
	{"dt": "Role", "filters": [["role_name", "=", "Talya Receptionist"]]},
	{
		"dt": "Custom Field",
		"filters": [["name", "in", [
			"Healthcare Practitioner-custom_show_on_talya_website",
			"Healthcare Practitioner-custom_talya_display_name_en",
			"Healthcare Practitioner-custom_talya_display_name_ar",
			"Healthcare Practitioner-custom_talya_specialty_en",
			"Healthcare Practitioner-custom_talya_specialty_ar",
			"Healthcare Practitioner-custom_talya_bio_en",
			"Healthcare Practitioner-custom_talya_bio_ar",
			"Healthcare Practitioner-custom_talya_display_order",
			"Healthcare Practitioner-custom_enable_talya_online_booking",
		]]],
	},
]

doctype_js = {
	"Talya Online Booking": "public/js/talya_online_booking.js",
}
doctype_list_js = {
	"Talya Online Booking": "public/js/talya_online_booking_list.js",
}

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "talya",
# 		"logo": "/assets/talya/logo.png",
# 		"title": "Talya",
# 		"route": "/talya",
# 		"has_permission": "talya.api.permission.has_app_permission",
# 	}
# ]

# The dock, the rail down the left of the desk, is a document rather than a hook. Author it in
# Manage Dock on a developer-mode site and press Export to App, and it is written to
# `talya/dock/talya/talya.json` for git to carry. An app that ships none has no
# rail: its sidebar gets a switcher in the header instead.
#
# A companion app, one that extends a host app rather than standing on its own, says so with
# `mount_on` on that same record, and its entries are appended to the host's rail. Mounting keeps
# the companion off the apps screen, so it takes precedence over any add_to_apps_screen above.

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/talya/css/talya.css"
# app_include_js = "/assets/talya/js/talya.js"

# include js, css files in header of web template
# web_include_css = "/assets/talya/css/talya.css"
# web_include_js = "/assets/talya/js/talya.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "talya/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_kanban_js = {"doctype" : "public/js/doctype_kanban.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "talya/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "talya.utils.jinja_methods",
# 	"filters": "talya.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "talya.install.before_install"
# after_install = "talya.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "talya.uninstall.before_uninstall"
# after_uninstall = "talya.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "talya.utils.before_app_install"
# after_app_install = "talya.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "talya.utils.before_app_uninstall"
# after_app_uninstall = "talya.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "talya.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "talya.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "talya.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["talya.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"talya.tasks.all"
# 	],
# 	"daily": [
# 		"talya.tasks.daily"
# 	],
# 	"hourly": [
# 		"talya.tasks.hourly"
# 	],
# 	"weekly": [
# 		"talya.tasks.weekly"
# 	],
# 	"monthly": [
# 		"talya.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "talya.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "talya.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "talya.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "talya.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["talya.utils.before_request"]
# after_request = ["talya.utils.after_request"]

# Job Events
# ----------
# before_job = ["talya.utils.before_job"]
# after_job = ["talya.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"talya.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

