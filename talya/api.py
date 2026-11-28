import frappe
from frappe.rate_limiter import rate_limit

from talya import public_booking


def _public_practitioners():
	if not frappe.db.has_column("Healthcare Practitioner", "custom_show_on_talya_website"):
		return []
	rows = frappe.get_all(
		"Healthcare Practitioner",
		filters={"status": "Active", "custom_show_on_talya_website": 1},
		fields=[
			"name",
			"department",
			"image",
			"custom_talya_display_name_en",
			"custom_talya_display_name_ar",
			"custom_talya_specialty_en",
			"custom_talya_specialty_ar",
			"custom_talya_bio_en",
			"custom_talya_bio_ar",
			"custom_talya_display_order",
			"custom_enable_talya_online_booking",
		],
		order_by="custom_talya_display_order asc, practitioner_name asc",
	)
	return [
		{
			"id": row.name,
			"department": row.department,
			"image": row.image,
			"name_en": row.custom_talya_display_name_en or row.name,
			"name_ar": row.custom_talya_display_name_ar or row.custom_talya_display_name_en or row.name,
			"specialty_en": row.custom_talya_specialty_en or row.department,
			"specialty_ar": row.custom_talya_specialty_ar or row.department,
			"bio_en": row.custom_talya_bio_en or "",
			"bio_ar": row.custom_talya_bio_ar or "",
			"booking_enabled": bool(row.custom_enable_talya_online_booking),
		}
		for row in rows
	]


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_public_data():
	practitioners = _public_practitioners()
	departments = sorted({row["department"] for row in practitioners if row["department"]})
	return {"practitioners": practitioners, "departments": departments}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_slots(practitioner, date):
	return {"slots": public_booking.requestable_slots(practitioner, date)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=8, seconds=900, methods="POST")
def lookup_patient(flow_id, kind, value, shared_mobile=None, language=None):
	public_booking.language(language)
	return public_booking.lookup(flow_id, kind, value, shared_mobile)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=30, seconds=900, methods="POST")
def invalidate_patient_lookup(flow_id, booking_reference):
	public_booking.language(None)
	public_booking.invalidate(flow_id, booking_reference)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=30, seconds=900, methods="POST")
def booking_notice(flow_id, booking_reference, practitioner, language=None):
	public_booking.language(language)
	return public_booking.other_booking_notice(flow_id, booking_reference, practitioner)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=3600, methods="POST")
def submit_booking(**payload):
	public_booking.language(payload.get("language"))
	return public_booking.submit(payload)
