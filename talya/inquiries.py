"""Reception workflow. Healthcare and the official WhatsApp app own their records."""

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, get_time, getdate, now_datetime

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
	doc = frappe.get_doc(INQUIRY, name, for_update=lock)
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
	row = frappe.get_doc(INQUIRY, name, for_update=True) if name else frappe.new_doc(INQUIRY)
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
	return [
		{"name": row["name"], "label": row.get("patient_name") or row["name"]}
		for row in patient_context(name)["matches"]
		if row.get("phone_match")
	]


@frappe.whitelist(methods=["GET"])
def patient_context(name, search=None):
	"""Use the Desk patient-resolution policy, filtered by this user's Patient field access."""
	doc = permitted(name)
	from talya import online_booking

	subject = frappe._dict(
		patient_name=doc.patient_name,
		mobile_number=doc.mobile_number,
		linked_patient=doc.linked_patient,
		email=None,
	)
	result = online_booking._matches(subject, search)
	can_create = bool(frappe.has_permission("Patient", "create"))
	fields, creation_error = [], None
	if can_create:
		try:
			fields = online_booking._patient_fields()
		except online_booking.PatientSetupError as error:
			frappe.clear_last_message()
			can_create, creation_error = False, str(error)
	verified = bool(
		doc.linked_patient
		and doc.patient_verified_at
		and doc.normalized_phone == normalize_phone(doc.mobile_number)
	)
	visit = {
		"practitioner": doc.healthcare_practitioner,
		"date": doc.preferred_date,
		"time": str(doc.preferred_time or "")[:5],
		"appointment_type": None,
		"service_unit": None,
		"locked": False,
		"booking_modified": None,
	}
	if doc.website_booking:
		booking = frappe.get_doc("Talya Online Booking", doc.website_booking)
		booking.check_permission("read")
		visit.update(
			{
				"practitioner": booking.healthcare_practitioner,
				"date": booking.preferred_date,
				"time": str(booking.preferred_time or "")[:5],
				"appointment_type": booking.appointment_type
				or frappe.db.get_single_value("Healthcare Settings", "default_appointment_type"),
				"service_unit": booking.service_unit,
				"locked": True,
				"booking_modified": booking.modified,
			}
		)
	elif doc.requested_service and frappe.db.exists("Appointment Type", doc.requested_service):
		visit["appointment_type"] = doc.requested_service
	result.update(
		{
			"patient_fields": fields,
			"can_create": can_create,
			"creation_error": creation_error,
			"verified": verified,
			"defaults": {
				"first_name": doc.patient_name,
				"mobile": normalize_phone(doc.mobile_number),
			},
			"visit": visit,
			"inquiry_modified": doc.modified,
		}
	)
	return result


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
	if patient:
		assert_patient_recipient(doc, patient)
	for doctype, value in (
		("Patient", patient),
		("Healthcare Practitioner", practitioner),
		("Appointment Type", appointment_type),
	):
		if value:
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
	from talya.internal_booking import availability

	return availability(appointment)["slots"]


@frappe.whitelist(methods=["GET"])
def slots(name, patient, practitioner, date, appointment_type, service_unit=None):
	return slot_options(name, patient, practitioner, date, appointment_type, service_unit)["slots"]


@frappe.whitelist(methods=["GET"])
def slot_options(
	name, patient=None, practitioner=None, date=None, appointment_type=None, service_unit=None, new_patient=False
):
	from talya.internal_booking import availability

	if not patient and str(new_patient).lower() not in {"1", "true"}:
		frappe.throw(_("Find and verify the correct Patient before checking availability."))
	appointment = _appointment(permitted(name), patient, practitioner, date, appointment_type)
	appointment.service_unit = service_unit
	return availability(appointment)


def _book_locked(doc, patient, practitioner, date, time, appointment_type, service_unit=None, notes=None):
	assert_patient_recipient(doc, patient)
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
	appointment.insert()
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
	return appointment.name


@frappe.whitelist(methods=["POST"])
def confirm(
	name,
	patient=None,
	patient_data=None,
	reviewed_matches=False,
	identity_verified=False,
	practitioner=None,
	date=None,
	time=None,
	appointment_type=None,
	service_unit=None,
	notes=None,
	expected_modified=None,
	expected_booking_modified=None,
):
	"""Atomically resolve a Patient and confirm, so retries cannot create partial duplicates."""
	from talya import online_booking

	current = permitted(name)
	if current.website_booking:
		# Website requests use exactly the same confirmation path as Desk.
		return online_booking.confirm(
			current.website_booking,
			patient=patient,
			patient_data=patient_data,
			identity_verified=identity_verified,
			reviewed_matches=reviewed_matches,
			expected_modified=expected_booking_modified,
		)
	with online_booking._atomic():
		doc = permitted(name, write=True, lock=True)
		if expected_modified and not doc.linked_patient_appointment and get_datetime(expected_modified) != get_datetime(doc.modified):
			frappe.throw(_("This inquiry changed. Reload it and verify the details again."))
		if doc.linked_patient_appointment:
			appointment = frappe.get_doc("Patient Appointment", doc.linked_patient_appointment)
			appointment.check_permission("read")
			if patient and appointment.patient != patient:
				frappe.throw(_("The linked appointment belongs to a different Patient. Verify the inquiry first."))
			return appointment.name
		if doc.status == "Closed":
			frappe.throw(_("Reopen the inquiry before booking."))
		online_booking._assert_silent_configuration(creating=bool(patient_data))
		if patient_data:
			if patient or doc.linked_patient:
				frappe.throw(_("This inquiry already has a Patient. Use the verified Patient record."))
			subject = frappe._dict(patient_name=doc.patient_name, mobile_number=doc.mobile_number)
			patient = online_booking._new_patient(
				subject, patient_data, identity_verified, reviewed_matches
			)
		elif not patient:
			patient = doc.linked_patient
		if not patient:
			frappe.throw(_("Find and verify the correct Patient before confirming this booking."))
		verify_patient(doc.name, patient, identity_verified=identity_verified)
		doc = frappe.get_doc(INQUIRY, doc.name, for_update=True)
		return _book_locked(
			doc, patient, practitioner, date, time, appointment_type, service_unit, notes
		)


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
	# Compatibility for existing callers. The portal uses confirm(), which routes
	# website requests through the Desk confirmation implementation.
	from talya import online_booking

	with online_booking._atomic():
		doc = permitted(name, write=True, lock=True)
		if doc.linked_patient_appointment:
			appointment = frappe.get_doc("Patient Appointment", doc.linked_patient_appointment)
			appointment.check_permission("read")
			if appointment.patient != patient:
				frappe.throw(_("The linked appointment belongs to a different Patient. Verify the inquiry first."))
			return appointment.name
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
		verify_patient(doc.name, patient, identity_verified=True)
		doc = frappe.get_doc(INQUIRY, doc.name, for_update=True)
		appointment = _book_locked(
			doc, patient, practitioner, date, time, appointment_type, service_unit, notes
		)
		if booking:
			booking.db_set(
				{
					"linked_patient": patient,
					"linked_patient_appointment": appointment,
					"booking_status": "Confirmed",
				}
			)
		return appointment


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
