"""Recipient identity checks shared by inquiries, booking and communication."""

import frappe
import phonenumbers
from frappe import _


def normalize_phone(value):
	raw = str(value or "").strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
	code = str(frappe.db.get_single_value("Talya Communication Settings", "country_calling_code") or "971")
	if not code.isdigit() or not 1 <= len(code) <= 3:
		frappe.throw(_("Configure a valid default country calling code before entering phone numbers."))
	region = phonenumbers.region_code_for_country_code(int(code))
	if not region or region == "ZZ":
		frappe.throw(_("Configure a valid default country calling code before entering phone numbers."))
	if raw.startswith("00"):
		raw = "+" + raw[2:]
	try:
		number = phonenumbers.parse(raw, region)
		if not phonenumbers.is_valid_number(number):
			raise ValueError
		return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
	except (ValueError, phonenumbers.NumberParseException):
		frappe.throw(_("Please enter a valid international mobile number."))


def patient_matches_phone(patient, phone):
	"""A contact match is necessary, but is never proof of a shared number's identity."""
	value = patient.get("mobile") or patient.get("phone")
	if not value:
		return False
	try:
		return normalize_phone(value) == phone
	except frappe.ValidationError:
		frappe.clear_last_message()
		return False


def assert_patient_recipient(inquiry, patient, check_permission=True):
	if inquiry.get("linked_patient") and inquiry.linked_patient != patient:
		frappe.throw(_("Create a new inquiry to use a different Patient."))
	doc = frappe.get_doc("Patient", patient)
	if check_permission:
		doc.check_permission("read")
	if not patient_matches_phone(doc, inquiry.normalized_phone):
		frappe.throw(_("The selected Patient does not match this inquiry's phone number."))
	return doc


def patient_names_for_phone(phone):
	"""Internal routing only; never expose unfiltered Patient records to a guest caller."""
	return {
		row.name
		for row in frappe.get_all("Patient", fields=["name", "mobile", "phone"])
		if patient_matches_phone(row, phone)
	}


def require_identity_confirmation(value):
	if str(value).lower() not in {"1", "true"}:
		frappe.throw(_("Confirm the patient's identity and authorization to use this number before linking."))
