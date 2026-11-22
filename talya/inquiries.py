"""Reception workflow. Healthcare and the official WhatsApp app own their records."""

import datetime

import frappe
from frappe import _
from frappe.utils import cint, get_time, getdate, now_datetime

from talya.recipients import (
	assert_patient_recipient,
	normalize_phone,
	patient_matches_phone,
	require_identity_confirmation,
)

INQUIRY = "Talya Patient Inquiry"
ROLES = {"System Manager", "Talya Receptionist"}
STATUSES = ("New", "Contacted", "Awaiting Reply", "Booked", "Closed")


def require_reception():
	if frappe.session.user == "Guest" or not ROLES.intersection(frappe.get_roles()):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def settings():
	return frappe.get_single("Talya Communication Settings")


def permitted(name, write=False, lock=False):
	require_reception()
	if lock:
		frappe.db.get_value(INQUIRY, name, "name", for_update=True)
	doc = frappe.get_doc(INQUIRY, name)
	doc.check_permission("write" if write else "read")
	return doc


def sync_booking(doc, method=None, backfill_only=False):
	"""Backfill missing requests; existing reception data is never a booking mirror."""
	if not frappe.db.exists("DocType", INQUIRY):
		return
	name = frappe.db.get_value(INQUIRY, {"website_booking": doc.name}, "name")
	if name and backfill_only:
		return name
	if name:
		frappe.db.get_value(INQUIRY, name, "name", for_update=True)
	frappe.db.get_value("Talya Online Booking", doc.name, "name", for_update=True)
	# Repeat the lookup after the booking lock to serialize first creation.
	name = frappe.db.get_value(INQUIRY, {"website_booking": doc.name}, "name")
	if name and backfill_only:
		return name
	row = frappe.get_doc(INQUIRY, name) if name else frappe.new_doc(INQUIRY)
	before = row.as_dict()
	if not name:
		row.update(
			{
				"website_booking": doc.name,
				"source": "Website",
				"patient_name": doc.patient_name,
				"mobile_number": doc.mobile_number,
				"healthcare_practitioner": doc.healthcare_practitioner,
				"requested_service": doc.medical_department,
				"preferred_date": doc.preferred_date,
				"preferred_time": doc.preferred_time,
				"notes": doc.patient_notes,
				"linked_patient": doc.linked_patient,
				"linked_patient_appointment": doc.linked_patient_appointment,
			}
		)
		row.normalized_phone = normalize_phone(row.mobile_number)
	if doc.booking_status in ("Confirmed", "Completed"):
		if doc.linked_patient_appointment:
			appointment = frappe.get_doc("Patient Appointment", doc.linked_patient_appointment)
			assert_patient_recipient(row, appointment.patient, check_permission=False)
			if row.linked_patient and row.linked_patient != appointment.patient:
				frappe.throw(
					_("The linked appointment belongs to a different Patient. Verify the inquiry first.")
				)
			if row.linked_patient_appointment and row.linked_patient_appointment != appointment.name:
				frappe.throw(_("This request is already linked to an appointment."))
			row.linked_patient = appointment.patient
			row.linked_patient_appointment = appointment.name
			row.preferred_date = appointment.appointment_date
			row.preferred_time = appointment.appointment_time
			row.healthcare_practitioner = appointment.practitioner
		if row.status != "Closed":
			row.status = "Booked"
	elif doc.booking_status in ("Rejected", "Cancelled"):
		row.status = "Closed"
	if not name or before != row.as_dict():
		row.flags.from_booking = True
		row.save(ignore_permissions=True)
	return row.name


@frappe.whitelist(methods=["GET"])
def list_inquiries(status=None, source=None, search=None, start=0):
	require_reception()
	filters = {}
	if status:
		filters["status"] = status
	if source:
		filters["source"] = source
	or_filters = None
	if search:
		or_filters = {
			"patient_name": ["like", "%" + search[:100] + "%"],
			"mobile_number": ["like", "%" + search[:100] + "%"],
		}
	return frappe.get_list(
		INQUIRY,
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"patient_name",
			"mobile_number",
			"healthcare_practitioner",
			"requested_service",
			"source",
			"status",
			"modified",
			"preferred_date",
			"linked_patient_appointment",
		],
		order_by="modified desc",
		start=max(0, cint(start)),
		page_length=30,
	)


@frappe.whitelist(methods=["GET"])
def detail(name):
	doc = permitted(name)
	from talya.communication import conversation, integration_status

	return {"inquiry": doc.as_dict(), "conversation": conversation(doc), "integration": integration_status()}


@frappe.whitelist(methods=["POST"])
def save_inquiry(data, name=None):
	require_reception()
	data = frappe.parse_json(data)
	doc = permitted(name, write=True, lock=True) if name else frappe.new_doc(INQUIRY)
	for field in (
		"patient_name",
		"mobile_number",
		"healthcare_practitioner",
		"requested_service",
		"preferred_date",
		"preferred_time",
		"notes",
		"status",
		"whatsapp_consent",
		"opt_out",
	):
		if field in data:
			doc.set(field, data[field])
	if not name:
		doc.source = "Manual"
	doc.save()
	return doc.name


@frappe.whitelist(methods=["GET"])
def lookup(doctype, search=""):
	require_reception()
	allowed = {
		"Patient": "patient_name",
		"Healthcare Practitioner": "practitioner_name",
		"Appointment Type": "name",
		"Gender": "name",
	}
	if doctype not in allowed:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return frappe.get_list(
		doctype,
		fields=["name", allowed[doctype] + " as label"],
		filters={allowed[doctype]: ["like", "%" + search[:80] + "%"]},
		page_length=30,
	)


@frappe.whitelist(methods=["GET"])
def matching_patients(name):
	doc = permitted(name)
	# Permission-filtered candidates only. Never auto-link an ambiguous family/shared number.
	rows = frappe.get_list("Patient", fields=["name", "patient_name", "mobile", "phone"], page_length=0)
	return [
		{"name": row.name, "label": row.patient_name}
		for row in rows
		if patient_matches_phone(row, doc.normalized_phone)
	]


@frappe.whitelist(methods=["POST"])
def create_patient(name, sex, identity_verified=False):
	doc = permitted(name, write=True, lock=True)
	frappe.has_permission("Patient", "create", throw=True)
	frappe.db.get_value("DocType", "Patient", "name", for_update=True)
	if doc.linked_patient:
		assert_patient_recipient(doc, doc.linked_patient)
		return doc.linked_patient
	if matching_patients(name):
		frappe.throw(_("Matching patients exist. Select a verified patient instead."))
	require_identity_confirmation(identity_verified)
	# A separate explicit action; never create a Patient on import or message arrival.
	if not frappe.db.exists("Gender", sex):
		frappe.throw(_("Select the patient's gender before creating a Patient."))
	patient = frappe.get_doc(
		{"doctype": "Patient", "first_name": doc.patient_name, "sex": sex, "mobile": doc.normalized_phone}
	).insert()
	doc.flags.integration_update = True
	doc.flags.verify_patient = True
	doc.linked_patient = patient.name
	doc.save()
	return patient.name


@frappe.whitelist(methods=["POST"])
def verify_patient(name, patient, identity_verified=False):
	doc = permitted(name, write=True, lock=True)
	require_identity_confirmation(identity_verified)
	assert_patient_recipient(doc, patient)
	if doc.linked_patient_appointment:
		appointment = frappe.get_doc("Patient Appointment", doc.linked_patient_appointment)
		appointment.check_permission("read")
		if appointment.patient != patient:
			frappe.throw(
				_("The linked appointment belongs to a different Patient. Verify the inquiry first.")
			)
	doc.linked_patient = patient
	doc.flags.integration_update = True
	doc.flags.verify_patient = True
	doc.save()
	return doc.name


def _appointment(doc, patient, practitioner, date, appointment_type):
	assert_patient_recipient(doc, patient)
	for doctype, value in (
		("Patient", patient),
		("Healthcare Practitioner", practitioner),
		("Appointment Type", appointment_type),
	):
		frappe.get_doc(doctype, value).check_permission("read")
	frappe.has_permission("Patient Appointment", "create", throw=True)
	if getdate(date) < getdate():
		frappe.throw(_("Appointment date cannot be in the past."))
	if frappe.db.get_value("Healthcare Practitioner", practitioner, "status") != "Active":
		frappe.throw(_("The practitioner is not active."))
	if frappe.db.get_value("Appointment Type", appointment_type, "allow_booking_for") != "Practitioner":
		frappe.throw(_("Choose an appointment type for Practitioner booking."))
	company = frappe.defaults.get_user_default("company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	appointment = frappe.new_doc("Patient Appointment")
	appointment.update(
		{
			"patient": patient,
			"practitioner": practitioner,
			"appointment_date": date,
			"appointment_type": appointment_type,
			"appointment_for": "Practitioner",
			"department": frappe.db.get_value("Healthcare Practitioner", practitioner, "department"),
			"company": company,
			"reference_doctype": INQUIRY,
			"reference_docname": doc.name,
		}
	)
	return appointment


def available_slots(appointment):
	from healthcare.healthcare.doctype.patient_appointment.patient_appointment import get_availability_data

	data = get_availability_data(appointment.appointment_date, appointment.practitioner, appointment)
	duration = cint(frappe.db.get_value("Appointment Type", appointment.appointment_type, "default_duration"))
	if duration <= 0:
		frappe.throw(_("Configure a positive appointment duration."))
	result = []
	for group in data["slot_details"]:
		for window in group.get("avail_slot", []):
			start = datetime.datetime.combine(
				getdate(appointment.appointment_date), get_time(window.get("from_time"))
			)
			end = datetime.datetime.combine(
				getdate(appointment.appointment_date), get_time(window.get("to_time"))
			)
			while start + datetime.timedelta(minutes=duration) <= end:
				finish = start + datetime.timedelta(minutes=duration)
				conflict = any(
					start
					< datetime.datetime.combine(
						getdate(appointment.appointment_date), get_time(a["appointment_time"])
					)
					+ datetime.timedelta(minutes=cint(a.get("duration") or duration))
					and finish
					> datetime.datetime.combine(
						getdate(appointment.appointment_date), get_time(a["appointment_time"])
					)
					for a in group.get("appointments", [])
				)
				if not conflict and start > now_datetime():
					result.append(
						{
							"time": start.strftime("%H:%M"),
							"service_unit": group.get("service_unit") or "",
							"duration": duration,
						}
					)
				start = finish
	return result


@frappe.whitelist(methods=["GET"])
def slots(name, patient, practitioner, date, appointment_type):
	return available_slots(_appointment(permitted(name), patient, practitioner, date, appointment_type))


@frappe.whitelist(methods=["POST"])
def book(
	name,
	patient,
	practitioner,
	date,
	time,
	appointment_type,
	service_unit=None,
	notes=None,
	identity_verified=False,
):
	doc = permitted(name, write=True, lock=True)
	assert_patient_recipient(doc, patient)
	if doc.linked_patient_appointment:
		appointment = frappe.get_doc("Patient Appointment", doc.linked_patient_appointment)
		appointment.check_permission("read")
		if appointment.patient != patient:
			frappe.throw(
				_("The linked appointment belongs to a different Patient. Verify the inquiry first.")
			)
		return doc.linked_patient_appointment
	require_identity_confirmation(identity_verified)
	if doc.status == "Closed":
		frappe.throw(_("Reopen the inquiry before booking."))
	booking = None
	if doc.website_booking:
		frappe.db.get_value("Talya Online Booking", doc.website_booking, "name", for_update=True)
		booking = frappe.get_doc("Talya Online Booking", doc.website_booking)
		booking.check_permission("write")
		if booking.booking_status != "Pending":
			frappe.throw(_("Only pending bookings can be confirmed."))
	# Lock real shared resources, even when there are no appointments yet.
	for dt, value in (
		("Patient", patient),
		("Healthcare Practitioner", practitioner),
		("Healthcare Service Unit", service_unit),
	):
		if value:
			frappe.db.get_value(dt, value, "name", for_update=True)
	appointment = _appointment(doc, patient, practitioner, date, appointment_type)
	available = available_slots(appointment)
	choice = next(
		(s for s in available if s["time"] == str(time)[:5] and s["service_unit"] == (service_unit or "")),
		None,
	)
	if not choice:
		frappe.throw(_("The requested slot is no longer available. Please select another slot."))
	if service_unit:
		appointment.company = frappe.db.get_value("Healthcare Service Unit", service_unit, "company")
	if not appointment.company:
		frappe.throw(_("Configure the company for this Healthcare service unit."))
	frappe.get_doc("Company", appointment.company).check_permission("read")
	appointment.update(
		{
			"appointment_time": get_time(time),
			"service_unit": service_unit,
			"duration": choice["duration"],
			"notes": (notes or "")[:1000],
		}
	)
	appointment.insert()  # Healthcare validates patient, overlaps, unavailability and billing.
	doc.update(
		{
			"linked_patient": patient,
			"linked_patient_appointment": appointment.name,
			"status": "Booked",
			"preferred_date": date,
			"preferred_time": get_time(time),
			"healthcare_practitioner": practitioner,
		}
	)
	doc.flags.integration_update = True
	doc.flags.verify_patient = True
	doc.save()
	if booking:
		booking.db_set(
			{
				"linked_patient": patient,
				"linked_patient_appointment": appointment.name,
				"booking_status": "Confirmed",
			}
		)
	return appointment.name


def appointment_changed(doc, method=None):
	if not frappe.db.exists("DocType", INQUIRY):
		return
	for name in frappe.get_all(INQUIRY, filters={"linked_patient_appointment": doc.name}, pluck="name"):
		row = frappe.get_doc(INQUIRY, name)
		cancelled = doc.status == "Cancelled" or doc.docstatus == 2
		row.db_set(
			{
				"status": "Closed" if cancelled else "Booked",
				"preferred_date": doc.appointment_date,
				"preferred_time": doc.appointment_time,
				"healthcare_practitioner": doc.practitioner,
			}
		)
		if row.website_booking:
			frappe.db.set_value(
				"Talya Online Booking",
				row.website_booking,
				"booking_status",
				"Cancelled" if cancelled else ("Completed" if doc.status == "Closed" else "Confirmed"),
			)
