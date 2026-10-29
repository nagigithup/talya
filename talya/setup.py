import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ROLE = "Talya Receptionist"


def ensure_role():
	if not frappe.db.exists("Role", ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1, "is_custom": 1}).insert(
			ignore_permissions=True
		)


def ensure_practitioner_fields():
	create_custom_fields(
		{
			"Healthcare Practitioner": [
				{
					"fieldname": "custom_show_on_talya_website",
					"label": "Show on Talya Website",
					"fieldtype": "Check",
					"default": "0",
					"insert_after": "show_in_portal",
				},
				{
					"fieldname": "custom_talya_display_name_en",
					"label": "Talya Display Name (English)",
					"fieldtype": "Data",
					"insert_after": "custom_show_on_talya_website",
				},
				{
					"fieldname": "custom_talya_display_name_ar",
					"label": "Talya Display Name (Arabic)",
					"fieldtype": "Data",
					"insert_after": "custom_talya_display_name_en",
				},
				{
					"fieldname": "custom_talya_specialty_en",
					"label": "Talya Specialty (English)",
					"fieldtype": "Data",
					"insert_after": "custom_talya_display_name_ar",
				},
				{
					"fieldname": "custom_talya_specialty_ar",
					"label": "Talya Specialty (Arabic)",
					"fieldtype": "Data",
					"insert_after": "custom_talya_specialty_en",
				},
				{
					"fieldname": "custom_talya_bio_en",
					"label": "Talya Biography (English)",
					"fieldtype": "Small Text",
					"insert_after": "custom_talya_specialty_ar",
				},
				{
					"fieldname": "custom_talya_bio_ar",
					"label": "Talya Biography (Arabic)",
					"fieldtype": "Small Text",
					"insert_after": "custom_talya_bio_en",
				},
				{
					"fieldname": "custom_talya_display_order",
					"label": "Talya Display Order",
					"fieldtype": "Int",
					"default": "0",
					"insert_after": "custom_talya_bio_ar",
				},
				{
					"fieldname": "custom_enable_talya_online_booking",
					"label": "Enable Talya Online Booking",
					"fieldtype": "Check",
					"default": "0",
					"insert_after": "custom_talya_display_order",
				},
			],
		},
		update=True,
	)


def after_install():
	ensure_role()
	ensure_practitioner_fields()


def after_migrate():
	ensure_role()
	ensure_practitioner_fields()
