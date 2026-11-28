"""Patient resolution and transaction-safe submission for the public form."""

import datetime
import re
import secrets
from hashlib import sha256

import frappe
from frappe import _
from frappe.utils import get_time, getdate, now_datetime, validate_email_address

from talya.booking import get_available_slots, validate_public_practitioner
from talya.online_booking import BOOKING, _atomic, _contact_matches, _name
from talya.recipients import normalize_phone

COOKIE = "talya_booking_session"
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
FLOW = re.compile(r"[a-f0-9]{32}")
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
ACTIVE = ("Pending", "Confirmed")
LOOKUP_TTL = 600


def language(value):
	frappe.local.lang = "ar" if value == "ar" else "en"
	frappe.local.response_headers["Cache-Control"] = "private, no-store"
	return frappe.local.lang


def browser_session(create=False):
	cookie = frappe.request.cookies.get(COOKIE, "")
	if not TOKEN.fullmatch(cookie):
		if not create:
			frappe.throw(_("Reload the appointment form and try again."))
		cookie = secrets.token_urlsafe(32)
		frappe.local.cookie_manager.set_cookie(COOKIE, cookie, httponly=True, samesite="Strict")
	return sha256(f"{frappe.session.sid}:{cookie}".encode()).hexdigest()


def _cache_key(flow_id):
	if not FLOW.fullmatch(str(flow_id or "")):
		frappe.throw(_("Reload the appointment form and try again."))
	return f"talya:booking:lookup:{browser_session()}:{flow_id}"


def _digits(value):
	return re.sub(r"[^0-9]", "", str(value or "").translate(DIGITS))


def _identity(value):
	raw = str(value or "").strip().translate(DIGITS)
	digits = _digits(raw)
	if not re.fullmatch(r"[0-9 -]{15,24}", raw) or not re.fullmatch(r"784[0-9]{12}", digits):
		frappe.throw(_("Enter a valid Emirates ID."))
	return digits


def _candidates(mobile="", identity="", lock=False):
	# Filter on digits to include legacy spacing, prefixes and Arabic-Indic digits.
	# Canonical phone equality is checked again in Python.
	def digits_sql(column):
		expression = f"coalesce(`{column}`, '')"
		for source, target in zip("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789", strict=True):
			expression = f"replace({expression}, '{source}', '{target}')"
		return f"regexp_replace({expression}, '[^0-9]', '')"

	conditions, values = [], []
	if mobile:
		for field in ("mobile", "phone"):
			conditions.append(f"right({digits_sql(field)}, 7) = %s")
			values.append(mobile[-7:])
	if identity:
		conditions.append(f"{digits_sql('uid')} = %s")
		values.append(identity)
	where = " OR ".join(conditions)
	rows = frappe.db.sql(
		f"""select name, first_name, patient_name, mobile, phone, email, uid
		   from tabPatient where {where}{" for update" if lock else ""}""",
		values,
		as_dict=True,
	)
	return [
		row
		for row in rows
		if (identity and _digits(row.uid) == identity) or (mobile and _contact_matches(row, mobile))
	]


def _matches(kind, value, lock=False):
	if kind == "emirates_id":
		return _candidates(identity=_identity(value), lock=lock)
	if kind == "mobile":
		return _candidates(mobile=normalize_phone(value), lock=lock)
	frappe.throw(_("Choose mobile number or Emirates ID."))


def _primary_phone(patient):
	try:
		return normalize_phone(patient.mobile or patient.phone)
	except frappe.ValidationError:
		frappe.clear_last_message()
		return None


def lookup(flow_id, kind, value, shared_mobile=None):
	key = _cache_key(flow_id)
	frappe.cache.delete_value(key)
	if len(str(value or "")) > 40 or len(str(shared_mobile or "")) > 40:
		frappe.throw(_("Enter a valid mobile number or Emirates ID."))
	rows = _matches(kind, value)
	shared = normalize_phone(shared_mobile) if kind == "emirates_id" and shared_mobile else None
	if shared and (len(rows) != 1 or not _contact_matches(rows[0], shared)):
		return {"status": "reception"}
	if not rows:
		return {"status": "new"}
	if len(rows) != 1:
		return {"status": "emirates_id" if kind == "mobile" else "reception"}
	patient = rows[0]
	if not _primary_phone(patient):
		return {"status": "reception"}
	reference = secrets.token_urlsafe(32)
	frappe.cache.set_value(
		key,
		{
			"reference": reference,
			"patient": patient.name,
			"kind": kind,
			"value": str(value),
			"shared": shared,
		},
		expires_in_sec=LOOKUP_TTL,
	)
	first_name = frappe.utils.strip_html(patient.first_name or "").split()
	return {"first_name": first_name[0] if first_name else "", "booking_reference": reference}


def invalidate(flow_id, booking_reference):
	key = _cache_key(flow_id)
	data = frappe.cache.get_value(key)
	if data and secrets.compare_digest(data["reference"], str(booking_reference or "")):
		frappe.cache.delete_value(key)


def _match_reference(flow_id, reference):
	match = frappe.cache.get_value(_cache_key(flow_id), expires=True)
	if (
		not TOKEN.fullmatch(str(reference or ""))
		or not match
		or not secrets.compare_digest(match["reference"], reference)
	):
		frappe.throw(_("Look up your patient record again to continue."))
	return match


def _has_other_booking(patient, practitioner):
	if not patient:
		return False
	now = now_datetime()
	booking = frappe.qb.DocType(BOOKING)
	return bool(
		frappe.qb.from_(booking)
		.select(booking.name)
		.where(
			(booking.linked_patient == patient)
			& (booking.healthcare_practitioner != practitioner)
			& booking.booking_status.isin(ACTIVE)
			& (
				(booking.preferred_date > now.date())
				| ((booking.preferred_date == now.date()) & (booking.preferred_time > now.time()))
			)
		)
		.limit(1)
		.run()
	)


def other_booking_notice(flow_id, booking_reference, practitioner):
	validate_public_practitioner(practitioner)
	match = _match_reference(flow_id, booking_reference)
	return {"has_other_booking": _has_other_booking(match["patient"], practitioner)}


def requestable_slots(practitioner, date):
	validate_public_practitioner(practitioner)
	date = getdate(date)
	reserved = {
		get_time(row).strftime("%H:%M")
		for row in frappe.db.get_values(
			BOOKING,
			{
				"healthcare_practitioner": practitioner,
				"preferred_date": date,
				"booking_status": ["in", ACTIVE],
			},
			"preferred_time",
			pluck=True,
		)
		if row is not None
	}
	return [slot for slot in get_available_slots(practitioner, date) if slot not in reserved]


def _clean(value, limit):
	return frappe.utils.strip_html(str(value or "")).strip()[:limit]


def _new_values(payload):
	first_name = _clean(payload.get("first_name"), 70)
	last_name = _clean(payload.get("last_name"), 70)
	if not first_name:
		frappe.throw(_("Enter your first name."))
	sex = _clean(payload.get("sex"), 140)
	if not sex or not frappe.db.exists("Gender", sex):
		frappe.throw(_("Select your gender."))
	email = _clean(payload.get("email"), 140)
	if email and not validate_email_address(email):
		frappe.throw(_("Please enter a valid email address."))
	return {
		"first_name": first_name,
		"last_name": last_name,
		"sex": sex,
		"email": email,
		"mobile": normalize_phone(payload.get("mobile_number")),
		"uid": _identity(payload["emirates_id"]) if payload.get("emirates_id") else "",
		"invite_user": 0,
	}


def _create_patient(values):
	# Share the same database mutex as the historical reception creation flow.
	# A current read after acquiring it also sees Patients inserted by another request.
	frappe.db.get_value("DocType", "Patient", "name", for_update=True)
	full_name = _name(f"{values['first_name']} {values['last_name']}")
	for row in _candidates(values["mobile"], values["uid"], lock=True):
		if (values["uid"] and _digits(row.uid) == values["uid"]) or _name(row.patient_name) == full_name:
			frappe.throw(
				_("A matching patient record may already exist. Use Existing patient or contact reception.")
			)
	if (
		frappe.db.get_single_value("Healthcare Settings", "send_registration_msg")
		or frappe.db.get_single_value("Healthcare Settings", "collect_registration_fee")
		or frappe.db.exists(
			"Notification",
			{
				"enabled": 1,
				"document_type": ["in", ["Patient", "Customer", "Contact"]],
				"channel": ["!=", "System Notification"],
			},
		)
	):
		frappe.throw(_("Contact reception to register as a new patient."))
	return _insert("Patient", values)


def _insert(doctype, values):
	# Permission and validation errors from Healthcare can include private record
	# names. The public caller only receives the generic service message.
	messages = frappe.local.message_log
	message_count = len(messages)
	try:
		doc = frappe.get_doc({"doctype": doctype, **values})
		doc.flags.from_public_booking = True
		doc.insert(ignore_permissions=True)
		del messages[message_count:]
		return doc
	except Exception:
		del messages[message_count:]
		frappe.logger("talya").warning("Public booking insert failed for %s", doctype)
	# Raise outside the exception handler so the original exception cannot surface.
	frappe.throw(_("We could not save this request. Try again or contact reception."))


def _result(booking, practitioner):
	return {
		"booking_reference": booking.name,
		"status": "Pending",
		"has_other_booking": _has_other_booking(booking.linked_patient, practitioner),
	}


def submit(payload):
	if _clean(payload.get("website"), 200):
		frappe.throw(_("Unable to process this request."))
	flow = str(payload.get("flow_id") or "")
	request_id = str(payload.get("request_id") or "")
	if not FLOW.fullmatch(flow) or not FLOW.fullmatch(request_id):
		frappe.throw(_("Reload the appointment form and try again."))
	session = browser_session()
	request_key = sha256(f"{session}:{flow}:{request_id}".encode()).hexdigest()
	# The lock is held through Frappe's request commit. It makes retries see the
	# original booking even when a client has lost the response.
	with _atomic():
		frappe.db.get_value("DocType", BOOKING, "name", for_update=True)
		existing = frappe.db.get_value(
			BOOKING,
			{"public_request_key": request_key},
			["name", "linked_patient", "healthcare_practitioner"],
			as_dict=True,
			for_update=True,
		)
		if existing:
			return _result(existing, existing.healthcare_practitioner)
		return _submit_new_request(payload, flow, request_key)


def _submit_new_request(payload, flow, request_key):
	if str(payload.get("consent_accepted", "")).lower() not in {"1", "true", "yes", "on"}:
		frappe.throw(_("Privacy consent is required."))
	time = _clean(payload.get("preferred_time"), 8)
	if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time):
		frappe.throw(_("Please enter a valid preferred time."))
	try:
		date = datetime.date.fromisoformat(str(payload.get("preferred_date") or ""))
	except ValueError:
		frappe.throw(_("Choose a valid appointment date."))
	if datetime.datetime.combine(date, get_time(time)) <= now_datetime():
		frappe.throw(_("The selected slot is no longer available."))
	practitioner = _clean(payload.get("healthcare_practitioner"), 140)
	department = _clean(payload.get("medical_department"), 140)
	visit = validate_public_practitioner(practitioner, department)
	mode = payload.get("patient_mode")
	if mode == "existing":
		match = _match_reference(flow, payload.get("booking_reference"))
		frappe.db.get_value("DocType", "Patient", "name", for_update=True)
		rows = _matches(match["kind"], match["value"], lock=True)
		if (
			len(rows) != 1
			or rows[0].name != match["patient"]
			or (match["shared"] and not _contact_matches(rows[0], match["shared"]))
		):
			frappe.throw(_("Look up your patient record again to continue."))
		patient = rows[0]
		patient_type = "Existing"
	elif mode == "new":
		patient = _create_patient(_new_values(payload))
		patient_type = "New"
	else:
		frappe.throw(_("Choose Existing patient or New patient."))
	mobile = _primary_phone(patient)
	if not mobile:
		frappe.throw(_("Contact reception to complete this booking."))
	validate_public_practitioner(practitioner, department, lock=True)
	if time not in get_available_slots(practitioner, date, lock=True):
		frappe.throw(_("The selected slot is no longer available."))
	# Retain Talya's reservation of a doctor's requested slot for all patients.
	# The patient is intentionally not a cross-doctor or cross-slot restriction.
	if frappe.db.get_value(
		BOOKING,
		{
			"healthcare_practitioner": practitioner,
			"preferred_date": date,
			"preferred_time": time,
			"booking_status": ["in", ACTIVE],
		},
		"name",
		for_update=True,
		wait=False,
	):
		frappe.throw(_("This time has just been requested. Please choose another time."))
	doc = _insert(
		BOOKING,
		{
			"linked_patient": patient.name,
			"patient_type": patient_type,
			"public_request_key": request_key,
			"patient_name": patient.patient_name,
			"mobile_number": mobile,
			"email": patient.email,
			"medical_department": visit.department,
			"healthcare_practitioner": practitioner,
			"preferred_date": date,
			"preferred_time": time,
			"patient_notes": _clean(payload.get("patient_notes"), 1000),
			"language": frappe.local.lang,
			"consent_accepted": 1,
		},
	)
	return _result(doc, practitioner)
