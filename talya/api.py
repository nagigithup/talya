import re

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate, now_datetime, validate_email_address

from talya.booking import get_available_slots, validate_public_practitioner


PHONE_RE = re.compile(r"^\+?[0-9][0-9\s()-]{7,19}$")


def _clean(value, limit):
	return frappe.utils.strip_html(str(value or "")).strip()[:limit]


def _public_practitioners():
	if not frappe.db.has_column("Healthcare Practitioner", "custom_show_on_talya_website"):
		return []
	rows = frappe.get_all(
		"Healthcare Practitioner",
		filters={"status": "Active", "custom_show_on_talya_website": 1},
		fields=[
			"name", "department", "image", "custom_talya_display_name_en", "custom_talya_display_name_ar",
			"custom_talya_specialty_en", "custom_talya_specialty_ar", "custom_talya_bio_en",
			"custom_talya_bio_ar", "custom_talya_display_order", "custom_enable_talya_online_booking",
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
	validate_public_practitioner(practitioner)
	return {"slots": get_available_slots(practitioner, date)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="talya_booking", limit=5, seconds=60 * 60, methods="POST")
def submit_booking(**payload):
	if _clean(payload.get("website"), 200):
		frappe.throw(_("Unable to process this request."))
	patient_name = _clean(payload.get("patient_name"), 140)
	mobile = _clean(payload.get("mobile_number"), 30)
	email = _clean(payload.get("email"), 140)
	department = _clean(payload.get("medical_department"), 140)
	practitioner = _clean(payload.get("healthcare_practitioner"), 140)
	date = getdate(payload.get("preferred_date"))
	time = _clean(payload.get("preferred_time"), 8)
	language = "ar" if payload.get("language") == "ar" else "en"
	consent = str(payload.get("consent_accepted", "")).lower() in {"1", "true", "yes", "on"}

	if len(patient_name) < 2:
		frappe.throw(_("Please enter the patient's full name."))
	if not PHONE_RE.fullmatch(mobile):
		frappe.throw(_("Please enter a valid mobile number."))
	if email and not validate_email_address(email):
		frappe.throw(_("Please enter a valid email address."))
	if date < getdate():
		frappe.throw(_("Appointment date cannot be in the past."))
	if not consent:
		frappe.throw(_("Privacy consent is required."))
	validate_public_practitioner(practitioner, department)
	configured_slots = get_available_slots(practitioner, date)
	if configured_slots and time not in configured_slots:
		frappe.throw(_("The selected slot is no longer available."))
	if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time):
		frappe.throw(_("Please enter a valid preferred time."))

	# Serialize duplicate checks for this practitioner/slot. A request remains pending, never confirmed here.
	frappe.db.sql("SELECT name FROM `tabTalya Online Booking` WHERE healthcare_practitioner=%s FOR UPDATE", practitioner)
	duplicate = frappe.db.exists(
		"Talya Online Booking",
		{
			"healthcare_practitioner": practitioner,
			"preferred_date": date,
			"preferred_time": time,
			"booking_status": ["in", ["Pending", "Confirmed"]],
		},
	)
	if duplicate:
		frappe.throw(_("This time has just been requested. Please choose another time."))

	doc = frappe.get_doc(
		{
			"doctype": "Talya Online Booking",
			"patient_name": patient_name,
			"mobile_number": mobile,
			"email": email,
			"medical_department": department,
			"healthcare_practitioner": practitioner,
			"preferred_date": date,
			"preferred_time": time,
			"patient_notes": _clean(payload.get("patient_notes"), 1000),
			"language": language,
			"consent_accepted": 1,
			"consent_timestamp": now_datetime(),
			"source": "Website",
		}
	).insert(ignore_permissions=True)
	return {"booking_reference": doc.booking_reference or doc.name, "status": "Pending"}
