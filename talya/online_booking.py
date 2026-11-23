"""Reception identity verification and atomic website request confirmation."""

import datetime
import unicodedata
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, get_time, getdate

from talya import inquiries
from talya.permissions import PATIENT_CLINICAL_FIELDS
from talya.recipients import (
	assert_patient_recipient,
	normalize_phone,
	patient_matches_phone,
	require_identity_confirmation,
)

BOOKING = "Talya Online Booking"
DEMOGRAPHICS = ("first_name", "middle_name", "last_name", "sex", "dob", "mobile", "phone", "email")
MATCH_FIELDS = ("patient_name", "sex", "dob", "mobile", "phone", "email")
INPUT_TYPES = {"Data", "Link", "Select", "Date", "Int", "Float", "Check", "Small Text"}


class PatientSetupError(frappe.ValidationError):
	pass


def _name(value):
	return " ".join(
		"".join(c for c in unicodedata.normalize("NFKD", str(value or "")) if not unicodedata.combining(c))
		.casefold()
		.split()
	)


def _contact_matches(patient, phone):
	return any(
		patient_matches_phone(frappe._dict(mobile=patient.get(field)), phone)
		for field in ("mobile", "phone")
		if patient.get(field)
	)


def _booking(name, write=False, lock=False, expected_modified=None):
	inquiries.require_reception()
	if lock:
		inquiry = frappe.db.get_value(inquiries.INQUIRY, {"website_booking": name}, "name")
		if inquiry:
			frappe.db.get_value(inquiries.INQUIRY, inquiry, "name", for_update=True)
		frappe.db.get_value(BOOKING, name, "name", for_update=True)
	doc = frappe.get_doc(BOOKING, name, for_update=lock)
	doc.check_permission("write" if write else "read")
	if (
		expected_modified
		and doc.booking_status == "Pending"
		and get_datetime(expected_modified) != get_datetime(doc.modified)
	):
		frappe.throw(_("This booking changed. Reload it and verify the details again."))
	return doc


def _inquiry(booking, lock=False):
	name = frappe.db.get_value(inquiries.INQUIRY, {"website_booking": booking.name}, "name")
	return frappe.get_doc(inquiries.INQUIRY, name, for_update=lock) if name else None


def _is_verified(booking, lock=False):
	row = _inquiry(booking, lock=lock)
	return bool(
		booking.linked_patient
		and row
		and row.linked_patient == booking.linked_patient
		and row.patient_verified_at
		and row.normalized_phone == normalize_phone(booking.mobile_number)
	)


def _patient_fields():
	frappe.has_permission("Patient", "read", throw=True)
	meta = frappe.get_meta("Patient")
	levels = meta.get_permlevel_access("create")
	defaults = frappe.new_doc("Patient")
	fields = []
	for df in meta.fields:
		if df.fieldname not in DEMOGRAPHICS and not (df.reqd and not defaults.get(df.fieldname)):
			continue
		if (
			df.fieldname in PATIENT_CLINICAL_FIELDS
			or df.permlevel not in levels
			or df.hidden
			or df.read_only
			or df.fieldtype not in INPUT_TYPES
		):
			if df.reqd and not defaults.get(df.fieldname):
				frappe.throw(
					_(
						"Patient setup requires information unavailable to reception. Ask an authorized user to complete it."
					),
					PatientSetupError,
				)
			continue
		fields.append(
			{
				"fieldname": df.fieldname,
				"fieldtype": df.fieldtype,
				"label": _(df.label),
				"options": df.options,
				"reqd": cint(df.reqd),
				"mandatory_depends_on": df.mandatory_depends_on,
			}
		)
	return fields


def _matches(booking, search=None):
	frappe.has_permission("Patient", "read", throw=True)
	meta = frappe.get_meta("Patient")
	permitted = meta.get_permitted_fieldnames(permission_type="read")
	identity_fields = [
		df.fieldname
		for df in meta.fields
		if df.fieldname in permitted
		and df.fieldtype == "Data"
		and not df.hidden
		and any(
			key in " ".join((df.fieldname or "", df.label or "")).casefold()
			for key in ("identity", "identification", "emirates", "national id", "passport", "uid")
		)
	]
	fields = ["name", *[f for f in MATCH_FIELDS if f in permitted], *identity_fields]
	phone = normalize_phone(booking.mobile_number)
	query_value = str(search or "").strip()
	query = _name(query_value or booking.patient_name)
	query_phone = ""
	if any(c.isdigit() for c in query_value):
		try:
			query_phone = normalize_phone(query_value)
		except frappe.ValidationError:
			frappe.clear_last_message()
	query_identity = "".join(c for c in query_value.casefold() if c.isalnum())
	rows = frappe.get_list("Patient", fields=fields, page_length=0)
	result = []
	for row in rows:
		phone_match = patient_matches_phone(row, phone)
		name_match = bool(query and (query in _name(row.get("patient_name")) or query == _name(row.name)))
		search_phone_match = bool(query_phone and _contact_matches(row, query_phone))
		identity_match = bool(
			query_value
			and query_identity
			and any(
				query_identity == "".join(c for c in str(row.get(field) or "").casefold() if c.isalnum())
				for field in identity_fields
			)
		)
		if not (
			_contact_matches(row, phone)
			or name_match
			or search_phone_match
			or identity_match
			or row.name == booking.linked_patient
		):
			continue
		patient = frappe.get_doc("Patient", row.name)
		if not frappe.has_permission("Patient", "read", doc=patient):
			continue
		patient.apply_fieldlevel_read_permissions()
		result.append(
			{
				"name": row.name,
				**{
					f: patient.get(f)
					for f in MATCH_FIELDS
					if f in permitted and patient.has_permlevel_access_to(f)
				},
				"phone_match": phone_match,
				"name_match": name_match,
				"search_phone_match": search_phone_match,
				"identity_match": identity_match,
				"identity_hint": (
					"••••" + str(next((row.get(f) for f in identity_fields if row.get(f)), ""))[-4:]
					if identity_match
					else None
				),
			}
		)
	result.sort(
		key=lambda row: (
			not row["name_match"],
			not row["phone_match"],
			row.get("patient_name") or row["name"],
		)
	)
	return {
		"matches": result[:30],
		"more_matches": len(result) > 30,
		"identity_search_available": bool(identity_fields),
	}


@frappe.whitelist(methods=["GET"])
def patient_context(name, search=None):
	booking = _booking(name)
	result = _matches(booking, search)
	can_create = bool(frappe.has_permission("Patient", "create"))
	fields, creation_error = [], None
	if can_create:
		try:
			fields = _patient_fields()
		except PatientSetupError as error:
			frappe.clear_last_message()
			can_create, creation_error = False, str(error)
	result.update(
		{
			"patient_fields": fields,
			"can_create": can_create,
			"creation_error": creation_error,
			"verified": _is_verified(booking),
			"defaults": {
				"first_name": booking.patient_name,
				"mobile": normalize_phone(booking.mobile_number),
				"email": booking.email or "",
			},
		}
	)
	return result


@frappe.whitelist(methods=["GET"])
def visit_options(name, practitioner=None):
	booking = _booking(name)
	types = frappe.get_list(
		"Appointment Type",
		filters={"allow_booking_for": "Practitioner"},
		fields=["name", "default_duration"],
		page_length=0,
	)
	practitioner = frappe.get_doc("Healthcare Practitioner", practitioner or booking.healthcare_practitioner)
	practitioner.check_permission("read")
	units = []
	for row in practitioner.practitioner_schedules:
		if (
			row.service_unit
			and row.service_unit not in units
			and not frappe.db.get_value("Practitioner Schedule", row.schedule, "disabled")
		):
			unit = frappe.get_doc("Healthcare Service Unit", row.service_unit)
			if (
				unit.allow_appointments
				and not unit.is_group
				and frappe.has_permission("Healthcare Service Unit", "read", doc=unit)
			):
				units.append(unit.name)
	default_type = frappe.db.get_single_value("Healthcare Settings", "default_appointment_type")
	return {
		"types": types,
		"service_units": units,
		"default_type": default_type if default_type in {row.name for row in types} else None,
		"time_zone": frappe.db.get_single_value("System Settings", "time_zone"),
		"verified": _is_verified(booking),
	}


@contextmanager
def _atomic():
	point = "talya_confirmation_" + frappe.generate_hash(length=10)
	frappe.db.savepoint(point)
	callbacks = {
		key: len(getattr(frappe.db, key))
		for key in ("before_commit", "after_commit", "before_rollback", "after_rollback")
	}
	realtime_count = len(getattr(frappe.local, "_realtime_log", []) or [])
	try:
		yield
	except Exception:
		frappe.db.rollback(save_point=point)
		for key, count in callbacks.items():
			getattr(frappe.db, key).truncate(count)
		if getattr(frappe.local, "_realtime_log", None):
			del frappe.local._realtime_log[realtime_count:]
		raise
	else:
		frappe.db.release_savepoint(point)


def _assert_silent_configuration(creating=False):
	# Preserve configuration; refuse before writes if Healthcare would send SMS.
	keys = ["send_appointment_confirmation", "send_appointment_reminder"] + (
		["send_registration_msg"] if creating else []
	)
	if any(frappe.db.get_single_value("Healthcare Settings", key) for key in keys):
		frappe.throw(
			_(
				"Automatic Healthcare messages are enabled. Ask an administrator to disable them before confirming without messages."
			)
		)
	doctypes = [BOOKING, inquiries.INQUIRY, "Patient Appointment", "Event", "Communication"]
	if creating:
		doctypes += ["Patient", "Customer", "Contact"]
	if frappe.db.exists(
		"Notification",
		{"enabled": 1, "document_type": ["in", doctypes], "channel": ["!=", "System Notification"]},
	):
		frappe.throw(
			_(
				"Automatic messages are configured for these records. Ask an administrator to review them before confirming without messages."
			)
		)


def _verify(booking, patient, identity_verified):
	require_identity_confirmation(identity_verified)
	assert_patient_recipient(frappe._dict(normalized_phone=normalize_phone(booking.mobile_number)), patient)
	if booking.linked_patient and booking.linked_patient != patient:
		frappe.throw(
			_("This booking is linked to another Patient. Review its inquiry before changing the recipient.")
		)
	row = _inquiry(booking, lock=True)
	if not row:
		row = frappe.get_doc(inquiries.INQUIRY, inquiries.sync_booking(booking))
	inquiries.verify_patient(row.name, patient, identity_verified=True)
	booking.db_set("linked_patient", patient)
	return patient


def link_patient(name, patient, identity_verified=False, expected_modified=None):
	with _atomic():
		booking = _booking(name, write=True, lock=True, expected_modified=expected_modified)
		if booking.booking_status != "Pending":
			frappe.throw(_("Only pending bookings can be confirmed."))
		_assert_silent_configuration()
		_verify(booking, patient, identity_verified)
		return patient


def _new_patient(booking, values, identity_verified, reviewed_matches):
	require_identity_confirmation(identity_verified)
	if str(reviewed_matches).lower() not in {"1", "true"}:
		frappe.throw(_("Review the possible matches and confirm that none is the correct Patient."))
	frappe.has_permission("Patient", "create", throw=True)
	allowed = {df["fieldname"] for df in _patient_fields()}
	values = frappe.parse_json(values)
	if not isinstance(values, dict) or set(values) - allowed:
		frappe.throw(
			_("Only permitted Patient demographics may be entered in this flow."), frappe.PermissionError
		)
	if normalize_phone(values.get("mobile")) != normalize_phone(booking.mobile_number):
		frappe.throw(_("Verify the booking contact before using a different phone number."))
	values["mobile"] = normalize_phone(booking.mobile_number)
	frappe.db.get_value("DocType", "Patient", "name", for_update=True)
	# Internal duplicate prevention uses a current read; no hidden Patient data
	# is returned to the caller, including when record-level access is restricted.
	rows = frappe.db.sql("select patient_name,mobile,phone,dob from tabPatient for update", as_dict=True)
	full_name = " ".join(
		str(values.get(key) or "").strip() for key in ("first_name", "middle_name", "last_name")
	).strip()
	for row in rows:
		if _contact_matches(row, values["mobile"]) and _name(row.patient_name) == _name(full_name):
			if not (row.dob and values.get("dob") and getdate(row.dob) != getdate(values["dob"])):
				frappe.throw(
					_(
						"A possible duplicate Patient already exists. Select the verified record or ask authorized staff to review it."
					)
				)
	patient = frappe.new_doc("Patient")
	patient.update(values)
	patient.invite_user = 0
	patient.insert()
	return patient.name


def confirm(
	name,
	patient=None,
	patient_data=None,
	identity_verified=False,
	reviewed_matches=False,
	expected_modified=None,
):
	with _atomic():
		booking = _booking(name, write=True, lock=True, expected_modified=expected_modified)
		if booking.linked_patient_appointment:
			appointment = frappe.get_doc(
				"Patient Appointment", booking.linked_patient_appointment, for_update=True
			)
			appointment.check_permission("read")
			if (
				booking.booking_status == "Confirmed"
				and appointment.patient == booking.linked_patient
				and (not patient or patient == appointment.patient)
			):
				return appointment.name
			frappe.throw(_("This request is already linked to an appointment."))
		if booking.booking_status != "Pending":
			frappe.throw(_("Only pending bookings can be confirmed."))
		_assert_silent_configuration(creating=bool(patient_data))
		if patient_data:
			if patient or booking.linked_patient:
				frappe.throw(
					_("This booking already has a Patient. Use the existing Patient confirmation action.")
				)
			patient = _new_patient(booking, patient_data, identity_verified, reviewed_matches)
		if patient:
			_verify(booking, patient, identity_verified)
		elif not _is_verified(booking, lock=True):
			frappe.throw(_("Find and verify the correct Patient before confirming this booking."))
		from talya.booking import create_patient_appointment

		appointment = create_patient_appointment(booking)
		booking.db_set(
			{
				"linked_patient_appointment": appointment.name,
				"booking_status": "Confirmed",
				"appointment_type": appointment.appointment_type,
				"service_unit": appointment.service_unit,
				"appointment_end_time": (
					datetime.datetime.combine(
						getdate(appointment.appointment_date), get_time(appointment.appointment_time)
					)
					+ datetime.timedelta(minutes=appointment.duration)
				).time(),
			}
		)
		inquiries.sync_booking(booking)
		return appointment.name
