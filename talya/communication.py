"""Policy and record links around frappe/whatsapp; no transport implementation."""

import hashlib
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

from talya.inquiries import INQUIRY, normalize_phone, permitted, require_reception, settings
from talya.recipients import assert_patient_recipient, patient_names_for_phone


def integration_status():
	installed = "whatsapp" in frappe.get_installed_apps()
	account = frappe.db.get_single_value("WA Settings", "default_account") if installed else None
	ready = False
	if account:
		doc = frappe.get_doc("WA Account", account)
		ready = bool(
			doc.status == "Active"
			and doc.phone_id
			and doc.app_id
			and doc.business_id
			and doc.get_password("access_token", raise_exception=False)
			and frappe.db.get_single_value("WA Settings", "webhook_secret")
		)
	return {"installed": installed, "configured": ready, "account": account}


def before_request():
	"""Fail closed: upstream makes signature validation optional without a secret."""
	request = getattr(frappe.local, "request", None)
	if not request or request.method != "POST":
		return
	if (
		"whatsapp.whatsapp.webhook.handler" in request.path
		or frappe.form_dict.get("cmd") == "whatsapp.whatsapp.webhook.handler"
	):
		secret = frappe.db.get_single_value("WA Settings", "webhook_secret")
		if not secret:
			frappe.throw(
				_("Configure the WhatsApp webhook secret before accepting messages."),
				frappe.AuthenticationError,
			)
		from whatsapp.whatsapp.webhook import _verify_signature

		_verify_signature(secret)


def _can_send(inquiry):
	if inquiry.opt_out or frappe.db.exists(
		INQUIRY, {"normalized_phone": inquiry.normalized_phone, "opt_out": 1}
	):
		frappe.throw(_("This patient has opted out of WhatsApp communication."))
	if (
		not inquiry.whatsapp_consent
		or inquiry.get("consent_phone") != inquiry.normalized_phone
		or not inquiry.consent_recorded_at
	):
		frappe.throw(_("Record the patient's WhatsApp consent before sending."))
	if normalize_phone(inquiry.mobile_number) != inquiry.normalized_phone:
		frappe.throw(_("Verify the inquiry recipient before sending."))
	if inquiry.linked_patient:
		assert_patient_recipient(inquiry, inquiry.linked_patient)
		if not inquiry.get("patient_verified_at"):
			frappe.throw(
				_("Verify the Patient's identity and authorization to use this number before sending.")
			)
	if inquiry.linked_patient_appointment:
		appointment = frappe.get_doc("Patient Appointment", inquiry.linked_patient_appointment)
		appointment.check_permission("read")
		if appointment.patient != inquiry.linked_patient:
			frappe.throw(
				_("The linked appointment belongs to a different Patient. Verify the inquiry first.")
			)
	if not integration_status()["configured"]:
		frappe.throw(_("WhatsApp API is not configured."))


def message_policy(doc, method=None):
	if doc.direction != "Outgoing":
		return
	if doc.reference_doctype != INQUIRY:
		roles = set(frappe.get_roles())
		if "Talya Receptionist" in roles and "System Manager" not in roles:
			frappe.throw(_("Send patient messages from a Patient Inquiry."), frappe.PermissionError)
		return
	require_reception()
	row = permitted(doc.reference_docname, write=True, lock=True)
	_can_send(row)
	profile = frappe.get_doc("WA Profile", doc.to)
	if doc.attach:
		file = frappe.get_doc("File", doc.attach)
		file.check_permission("read")
		if not file.is_private or file.attached_to_doctype != INQUIRY or file.attached_to_name != row.name:
			frappe.throw(_("Use a private attachment belonging to this inquiry."), frappe.PermissionError)
		if row.get("recipient_changed_at") and get_datetime(file.creation) <= get_datetime(
			row.recipient_changed_at
		):
			frappe.throw(
				_("This attachment belongs to a previous recipient. Upload a new verified attachment.")
			)
	if (
		normalize_phone(profile.phone_number) != row.normalized_phone
		or profile.whatsapp_account != integration_status()["account"]
		or (doc.get("whatsapp_account") and doc.whatsapp_account != profile.whatsapp_account)
	):
		frappe.throw(_("The conversation recipient does not match this inquiry."))
	if doc.is_template:
		template = frappe.get_doc("WA Template", doc.whatsapp_template)
		if template.status != "Approved":
			frappe.throw(_("Only approved WhatsApp templates may be sent."))
		if template.whatsapp_account and template.whatsapp_account != profile.whatsapp_account:
			frappe.throw(_("Choose a template for the selected WhatsApp account."))
		allowed = {"patient_name", "preferred_date", "preferred_time", "name"}
		if any(v.variable_field not in allowed for v in template.get("template_variables", [])):
			frappe.throw(_("Use only non-clinical inquiry fields in WhatsApp templates."))
	else:
		last = frappe.db.get_value(
			"WA Message", {"to": doc.to, "direction": "Incoming"}, "creation", order_by="creation desc"
		)
		if not last or get_datetime(last) < add_to_date(now_datetime(), hours=-24):
			frappe.throw(_("The 24-hour messaging window is closed. Choose an approved template."))


def incoming(doc, method=None):
	if doc.direction != "Incoming":
		return
	profile = frappe.get_doc("WA Profile", doc.to)
	phone = normalize_phone(profile.phone_number)
	# Official webhook serializes by profile before creating the message.
	candidates = frappe.get_all(
		INQUIRY,
		filters={"normalized_phone": phone, "status": ["!=", "Closed"]},
		fields=[
			"name",
			"source",
			"wa_profile",
			"linked_patient",
			"linked_patient_appointment",
			"patient_verified_at",
		],
	)
	if profile.whatsapp_account != doc.whatsapp_account:
		frappe.throw(_("The conversation recipient does not match this inquiry."))
	patients = patient_names_for_phone(phone)
	account_candidates = [r for r in candidates if not r.wa_profile or r.wa_profile == profile.name]
	eligible = [
		r
		for r in account_candidates
		if (not r.linked_patient or (r.linked_patient in patients and r.patient_verified_at))
		and (
			not r.linked_patient_appointment
			or frappe.db.get_value("Patient Appointment", r.linked_patient_appointment, "patient")
			== r.linked_patient
		)
	]
	# A shared number or multiple requests is not proof of which Patient is speaking.
	# Continue one unambiguous verified thread, including after it has been booked.
	selected = eligible[0] if len(account_candidates) == len(eligible) == 1 and len(patients) <= 1 else None
	if not selected:
		review = [
			r
			for r in account_candidates
			if r.source == "WhatsApp"
			and r.wa_profile == profile.name
			and not r.linked_patient
			and not r.linked_patient_appointment
		]
		selected = review[0] if len(review) == 1 else None
	row = frappe.get_doc(INQUIRY, selected.name) if selected else frappe.new_doc(INQUIRY)
	if not selected:
		row.update(
			{
				"patient_name": profile.profile_name or phone,
				"mobile_number": phone,
				"source": "WhatsApp",
				"status": "New",
			}
		)
	row.wa_profile = profile.name
	row.flags.integration_update = True
	text = (doc.message or "").strip().casefold()
	if text in {"stop", "unsubscribe", "إيقاف", "الغاء", "إلغاء", "توقف"}:
		row.opt_out = 1
	row.save(ignore_permissions=True)
	doc.reference_doctype = INQUIRY
	doc.reference_docname = row.name


def notify_message(doc, method=None):
	if doc.reference_doctype != INQUIRY:
		return
	if doc.direction == "Outgoing" and doc.status == "Sent" and not doc.message_id:
		doc.db_set("status", "Pending")
	doc.notify_change()
	# No patient names, phone numbers or message bodies in notification payloads.
	users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", ["Talya Receptionist", "System Manager"]], "parenttype": "User"},
		pluck="parent",
	)
	for user in set(users):
		frappe.publish_realtime(
			"talya_inquiry",
			{"name": doc.reference_docname, "incoming": doc.direction == "Incoming"},
			user=user,
			after_commit=True,
		)


def detach_previous_profile(doc, old):
	if (
		not old
		or not old.wa_profile
		or old.wa_profile == doc.wa_profile
		or "whatsapp" not in frappe.get_installed_apps()
	):
		return
	profile = frappe.get_doc("WA Profile", old.wa_profile)
	# Preserve the old profile's Patient/history and links to other inquiries.
	links = [r for r in profile.links if r.link_doctype == INQUIRY and r.link_name == doc.name]
	for row in links:
		profile.remove(row)
	if links:
		profile.save(ignore_permissions=True)


def link_profile(doc):
	if not doc.wa_profile or "whatsapp" not in frappe.get_installed_apps():
		return
	profile = frappe.get_doc("WA Profile", doc.wa_profile)
	if normalize_phone(profile.phone_number) != doc.normalized_phone:
		frappe.throw(_("The conversation recipient does not match this inquiry."))
	changed = False
	patient = doc.linked_patient if doc.get("patient_verified_at") else None
	if patient:
		assert_patient_recipient(doc, patient, check_permission=False)
	for doctype, name in ((INQUIRY, doc.name), ("Patient", patient)):
		if name and not any(
			link.link_doctype == doctype and link.link_name == name for link in profile.links
		):
			profile.append("links", {"link_doctype": doctype, "link_name": name})
			changed = True
	if changed:
		profile.save(ignore_permissions=True)


def conversation(doc):
	state = integration_status()
	message = _(
		"Hello, this is Talya Medical Center. How can we help with your appointment request?",
		lang=settings().default_language or "ar",
	)
	result = {
		"messages": [],
		"templates": [],
		"fallback": "https://wa.me/" + doc.normalized_phone.lstrip("+") + "?text=" + quote(message),
		"contact_allowed": bool(
			doc.whatsapp_consent
			and doc.get("consent_phone") == doc.normalized_phone
			and not doc.opt_out
			and not frappe.db.exists(INQUIRY, {"normalized_phone": doc.normalized_phone, "opt_out": 1})
		),
	}
	if not state["installed"]:
		return result
	from whatsapp.whatsapp.api.messages import get_messages

	profiles = set(frappe.get_all("WA Profile", filters={"phone_number": doc.normalized_phone}, pluck="name"))
	result["messages"] = [
		m for m in get_messages(frappe.as_json([[INQUIRY, doc.name]])) if m["to"] in profiles
	]
	result["templates"] = approved_templates()
	return result


def approved_templates():
	if "whatsapp" not in frappe.get_installed_apps():
		return []
	account = integration_status()["account"]
	if not account:
		return []
	return frappe.get_all(
		"WA Template",
		filters={"status": "Approved"},
		or_filters=[["whatsapp_account", "=", account], ["whatsapp_account", "is", "not set"]],
		fields=["name", "template_name"],
		limit=100,
	)


@frappe.whitelist(methods=["POST"])
def send(name, request_key, message="", template=None, attach=None):
	doc = permitted(name, write=True, lock=True)
	_can_send(doc)
	if not request_key or len(request_key) > 100:
		frappe.throw(_("A unique send request key is required."))
	key = hashlib.sha256((doc.name + ":" + request_key).encode()).hexdigest()
	existing = frappe.db.get_value(
		"Talya Message Dispatch", {"request_key": key}, ["state", "message_name"], as_dict=True
	)
	if existing:
		return {
			"message_name": existing.message_name,
			"state": existing.state,
			"status": frappe.db.get_value("WA Message", existing.message_name, "status")
			if existing.message_name
			else None,
		}
	dispatch = frappe.get_doc(
		{"doctype": "Talya Message Dispatch", "inquiry": doc.name, "request_key": key}
	).insert(ignore_permissions=True)
	from whatsapp.whatsapp.api.messages import send_message, send_template
	from whatsapp.whatsapp.doctype.wa_profile.wa_profile import get_or_create_profile

	profile = get_or_create_profile(doc.normalized_phone, integration_status()["account"], doc.patient_name)
	if doc.wa_profile != profile:
		doc.wa_profile = profile
		doc.flags.integration_update = True
		doc.save()
	if attach:
		file = frappe.get_doc("File", {"file_url": attach})
		file.check_permission("read")
		if not file.is_private or file.attached_to_doctype != INQUIRY or file.attached_to_name != doc.name:
			frappe.throw(_("Use a private attachment belonging to this inquiry."), frappe.PermissionError)
	if not template and not (message or "").strip() and not attach:
		frappe.throw(_("Cannot send an empty message."))
	if template:
		from whatsapp.whatsapp.api.messages import _validate_template_for_reference

		_validate_template_for_reference(template, INQUIRY)
	message_policy(
		frappe._dict(
			direction="Outgoing",
			reference_doctype=INQUIRY,
			reference_docname=doc.name,
			to=profile,
			attach=file.name if attach else None,
			is_template=bool(template),
			whatsapp_template=template,
		)
	)
	# Persist the reservation before the external effect. A lost connection or process
	# crash must leave a reviewable reservation, never permit an automatic second send.
	frappe.db.commit()
	if template:
		message_name = send_template(template, profile, INQUIRY, doc.name)
	else:
		message_name = send_message(
			profile, message[:4000], attach=attach, reference_doctype=INQUIRY, reference_docname=doc.name
		)
	dispatch.db_set({"state": "Completed", "message_name": message_name})
	return {
		"message_name": message_name,
		"state": "Completed",
		"status": frappe.db.get_value("WA Message", message_name, "status"),
	}


@frappe.whitelist(methods=["GET"])
def get_settings():
	require_reception()
	return {
		"settings": settings().as_dict(),
		"integration": integration_status(),
		"templates": approved_templates(),
	}


@frappe.whitelist(methods=["POST"])
def save_settings(data):
	frappe.only_for("System Manager")
	doc = settings()
	data = frappe.parse_json(data)
	for field in (
		"country_calling_code",
		"default_language",
		"confirmation_template",
		"reminder_template",
		"reminders_enabled",
		"reminder_hours",
	):
		if field in data:
			doc.set(field, data[field])
	doc.save()
	return get_settings()


def reminders():
	config = settings()
	if not config.reminders_enabled or not config.reminder_template or not integration_status()["configured"]:
		return
	# Scheduler's service identity does not grant Healthcare access to reception users.
	frappe.set_user("Administrator")
	deadline = add_to_date(now_datetime(), hours=cint(config.reminder_hours))
	for row in frappe.get_all(
		INQUIRY,
		filters={"status": "Booked", "opt_out": 0, "whatsapp_consent": 1},
		fields=["name", "linked_patient_appointment"],
	):
		appt = frappe.get_doc("Patient Appointment", row.linked_patient_appointment)
		when = get_datetime(str(appt.appointment_date) + " " + str(appt.appointment_time))
		if (
			appt.status in ("Cancelled", "Closed")
			or appt.docstatus == 2
			or not now_datetime() < when <= deadline
		):
			continue
		try:
			send(row.name, "reminder:" + appt.name + ":" + str(when), template=config.reminder_template)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title="Talya reminder failed", message=frappe.get_traceback())
