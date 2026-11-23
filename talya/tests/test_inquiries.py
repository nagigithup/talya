"""Transactional local integration tests. Meta transport is always mocked."""

import io
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import add_days, getdate

from talya import communication as comm
from talya import inquiries as api
from talya import inquiry_import


def healthcare_fixture():
	"""Use the configured local company; all records are rolled back by the tests."""
	if not frappe.db.exists("Gender", "Other"):
		frappe.get_doc({"doctype": "Gender", "gender": "Other"}).insert()
	company = (
		frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.get_all("Company", pluck="name")[0]
	)
	unit_type = frappe.get_doc(
		{
			"doctype": "Healthcare Service Unit Type",
			"service_unit_type": "Talya isolated test unit type",
			"allow_appointments": 1,
		}
	).insert()
	unit = frappe.get_doc(
		{
			"doctype": "Healthcare Service Unit",
			"healthcare_service_unit_name": "Talya isolated test room",
			"company": company,
			"service_unit_type": unit_type.name,
			"parent_healthcare_service_unit": frappe.db.get_value(
				"Healthcare Service Unit", {"company": company, "is_group": 1}, "name"
			),
		}
	).insert()
	date = add_days(getdate(), 2)
	schedule = frappe.get_doc(
		{
			"doctype": "Practitioner Schedule",
			"schedule_name": "Talya isolated test schedule",
			"time_slots": [
				{
					"day": getdate(date).strftime("%A"),
					"from_time": "09:00:00",
					"to_time": "12:00:00",
					"duration": 30,
				}
			],
		}
	).insert()
	practitioner = frappe.get_doc(
		{
			"doctype": "Healthcare Practitioner",
			"first_name": "Talya isolated test doctor",
			"status": "Active",
			"custom_show_on_talya_website": 1,
			"custom_enable_talya_online_booking": 1,
			"practitioner_schedules": [{"schedule": schedule.name, "service_unit": unit.name}],
		}
	).insert()
	appointment_type = frappe.get_doc(
		{
			"doctype": "Appointment Type",
			"appointment_type": "Talya isolated consultation",
			"allow_booking_for": "Practitioner",
			"default_duration": 30,
		}
	).insert()
	patient = frappe.get_doc(
		{
			"doctype": "Patient",
			"first_name": "Talya isolated patient",
			"sex": "Other",
			"mobile": "+971522207872",
		}
	).insert()
	return frappe._dict(
		patient=patient.name,
		practitioner=practitioner.name,
		date=str(date),
		appointment_type=appointment_type.name,
		service_unit=unit.name,
	)


class TalyaIsolationTestCase(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint("talya_inquiry_test")
		self.test_files = []
		# The local DB is transactional; no commits, network, queued work, email or
		# realtime events may escape an isolated test, including on assertion failure.
		self.isolation = ExitStack()
		self.addCleanup(self.isolation.close)
		self.isolation.enter_context(patch.object(frappe.db, "commit"))
		self.isolation.enter_context(
			patch(
				"requests.sessions.Session.request",
				side_effect=AssertionError("External HTTP blocked during Talya tests"),
			)
		)
		for target in (
			"frappe.sendmail",
			"frappe.enqueue",
			"frappe.utils.background_jobs.enqueue",
			"frappe.publish_realtime",
			"healthcare.healthcare.doctype.patient_appointment.patient_appointment.send_confirmation_msg",
			"healthcare.healthcare.doctype.patient.patient.send_registration_sms",
		):
			self.isolation.enter_context(patch(target))

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="talya_inquiry_test")
		for url, path in self.test_files:
			if not frappe.db.exists("File", {"file_url": url}):
				Path(path).unlink(missing_ok=True)
		frappe.clear_cache()

	def inquiry(self, **kwargs):
		name = api.save_inquiry(
			{"patient_name": "Talya Test Contact", "mobile_number": "0522207872", **kwargs}
		)
		return frappe.get_doc(api.INQUIRY, name)

	def private_file(self, content, name="talya-test.csv"):
		doc = frappe.get_doc(
			{"doctype": "File", "file_name": name, "is_private": 1, "content": content}
		).insert()
		self.test_files.append((doc.file_url, doc.get_full_path()))
		return doc

	def account(self):
		account = frappe.get_doc(
			{
				"doctype": "WA Account",
				"account_name": "Talya isolated test account",
				"status": "Active",
				"phone_id": "test-phone",
				"app_id": "mock-app-id",
				"business_id": "mock-business-id",
				"access_token": "mock-not-a-real-token",
			}
		).insert()
		frappe.db.set_single_value("WA Settings", "default_account", account.name)
		frappe.db.set_single_value("WA Settings", "webhook_secret", "isolated-test-secret")
		return account


class TestPatientInquiries(TalyaIsolationTestCase):
	def test_phone_and_manual_entry(self):
		self.assertEqual(api.normalize_phone("٠٥٢٢٢٠٧٨٧٢"), "+971522207872")
		self.assertEqual(api.normalize_phone("00971 52 220 7872"), "+971522207872")
		with self.assertRaises(frappe.ValidationError):
			api.normalize_phone("123")
		doc = self.inquiry()
		self.assertEqual(doc.source, "Manual")
		self.assertEqual(doc.status, "New")
		self.assertEqual(api.detail(doc.name)["inquiry"]["name"], doc.name)

	def test_guest_and_unprivileged_access(self):
		doc = self.inquiry()
		frappe.set_user("Guest")
		for task in (
			lambda: api.list_inquiries(),
			lambda: api.detail(doc.name),
			lambda: api.save_inquiry({}),
			lambda: comm.send(doc.name, "x"),
			lambda: inquiry_import.preview("x", {}),
		):
			with self.assertRaises(frappe.PermissionError):
				task()

	def test_website_reuse_and_status_sync(self):
		fixture = healthcare_fixture()
		department = frappe.get_doc(
			{"doctype": "Medical Department", "department": "Talya Test Department"}
		).insert()
		booking = frappe.get_doc(
			{
				"doctype": "Talya Online Booking",
				"patient_name": "Website Test",
				"mobile_number": "0522207872",
				"healthcare_practitioner": fixture.practitioner,
				"medical_department": department.name,
				"preferred_date": fixture.date,
				"preferred_time": "09:00",
				"consent_accepted": 1,
			}
		).insert()
		api.sync_booking(booking)
		self.assertEqual(frappe.db.count(api.INQUIRY, {"website_booking": booking.name}), 1)
		name = frappe.db.get_value(api.INQUIRY, {"website_booking": booking.name}, "name")
		appointment = api.book(name, time="09:00", identity_verified=True, **fixture)
		self.assertEqual(
			frappe.db.get_value("Talya Online Booking", booking.name, "booking_status"), "Confirmed"
		)
		self.assertEqual(frappe.db.get_value(api.INQUIRY, name, "linked_patient_appointment"), appointment)
		appt = frappe.get_doc("Patient Appointment", appointment)
		appt.status = "Cancelled"
		appt.save()
		self.assertEqual(frappe.db.get_value(api.INQUIRY, name, "status"), "Closed")
		self.assertEqual(
			frappe.db.get_value("Talya Online Booking", booking.name, "booking_status"), "Cancelled"
		)

	def test_appointment_availability_and_idempotence(self):
		fixture = healthcare_fixture()
		doc = self.inquiry()
		args = dict(fixture)
		args.pop("service_unit")
		slots = api.slots(doc.name, **args)
		self.assertTrue(any(s["time"] == "09:00" for s in slots))
		with self.assertRaises(frappe.ValidationError):
			api.book(doc.name, time="08:00", identity_verified=True, **fixture)
		appointment = api.book(doc.name, time="09:00", identity_verified=True, **fixture)
		self.assertEqual(api.book(doc.name, time="09:00", **fixture), appointment)
		other = self.inquiry(patient_name="Another request")
		with self.assertRaises(frappe.ValidationError):
			api.book(other.name, time="09:00", identity_verified=True, **fixture)
		self.assertFalse(any(s["time"] == "09:00" for s in api.slots(other.name, **args)))
		self.assertEqual(frappe.db.count("Patient Appointment", {"reference_docname": doc.name}), 1)

	def test_patient_matching_prevents_duplicate_creation(self):
		fixture = healthcare_fixture()
		doc = self.inquiry()
		self.assertEqual(api.matching_patients(doc.name)[0]["name"], fixture.patient)
		with self.assertRaises(frappe.ValidationError):
			api.create_patient(doc.name, "Other", identity_verified=True)

	def test_portal_patient_search_is_manual_and_identity_is_permission_filtered(self):
		fixture = healthcare_fixture()
		patient = frappe.get_doc("Patient", fixture.patient)
		patient.uid = "784-SYNTHETIC-0001"
		patient.save()
		doc = self.inquiry(patient_name="Unrelated search", mobile_number="+971501234567")
		admin = api.patient_context(doc.name, search=patient.uid)
		self.assertTrue(admin["identity_search_available"])
		self.assertEqual([row["name"] for row in admin["matches"]], [patient.name])
		self.assertEqual(admin["matches"][0]["identity_hint"], "••••0001")
		self.assertNotIn("uid", admin["matches"][0])
		self.assertFalse(doc.reload().linked_patient)

		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "talya-portal-reception@example.invalid",
				"first_name": "Portal Reception",
				"send_welcome_email": 0,
				"roles": [{"role": "Talya Receptionist"}],
			}
		).insert()
		frappe.set_user(user.name)
		reception = api.patient_context(doc.name, search=patient.uid)
		self.assertFalse(reception["identity_search_available"])
		self.assertFalse(reception["matches"])

	def test_portal_new_patient_confirmation_is_atomic_and_retry_safe(self):
		fixture = healthcare_fixture()
		doc = self.inquiry(patient_name="Synthetic portal patient", mobile_number="+971501234567")
		preview = api.slot_options(
			doc.name,
			new_patient=True,
			practitioner=fixture.practitioner,
			date=fixture.date,
			appointment_type=fixture.appointment_type,
			service_unit=fixture.service_unit,
		)
		self.assertTrue(any(slot["time"] == "09:00" for slot in preview["slots"]))
		values = {
			"first_name": "Synthetic portal patient",
			"sex": "Other",
			"mobile": "+971501234567",
		}
		before_patients = frappe.db.count("Patient")
		appointment = api.confirm(
			doc.name,
			patient_data=values,
			reviewed_matches=True,
			identity_verified=True,
			practitioner=fixture.practitioner,
			date=fixture.date,
			time="09:00",
			appointment_type=fixture.appointment_type,
			service_unit=fixture.service_unit,
			expected_modified=doc.modified,
		)
		self.assertEqual(frappe.db.count("Patient"), before_patients + 1)
		self.assertEqual(api.confirm(doc.name), appointment)
		self.assertEqual(frappe.db.count("Patient Appointment", {"reference_docname": doc.name}), 1)
		self.assertEqual(frappe.db.count("Patient"), before_patients + 1)

	def test_portal_unavailable_slot_rolls_back_new_patient_and_keeps_inquiry_edits(self):
		fixture = healthcare_fixture()
		doc = self.inquiry(
			patient_name="Synthetic unavailable patient",
			mobile_number="+971501234567",
			notes="Reception note must remain",
		)
		before_patients = frappe.db.count("Patient")
		with self.assertRaises(frappe.ValidationError):
			api.confirm(
				doc.name,
				patient_data={
					"first_name": "Synthetic unavailable patient",
					"sex": "Other",
					"mobile": "+971501234567",
				},
				reviewed_matches=True,
				identity_verified=True,
				practitioner=fixture.practitioner,
				date=fixture.date,
				time="08:00",
				appointment_type=fixture.appointment_type,
				service_unit=fixture.service_unit,
			)
		self.assertEqual(frappe.db.count("Patient"), before_patients)
		self.assertFalse(doc.reload().linked_patient)
		self.assertEqual(doc.notes, "Reception note must remain")

	def test_reception_can_book_but_cannot_configure_secrets(self):
		fixture = healthcare_fixture()
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "talya-isolated-reception@example.invalid",
				"first_name": "Isolated Reception",
				"send_welcome_email": 0,
				"roles": [{"role": "Talya Receptionist"}],
			}
		).insert()
		frappe.set_user(user.name)
		doc = self.inquiry()
		self.assertTrue(api.matching_patients(doc.name))
		appointment = api.book(doc.name, time="09:00", identity_verified=True, **fixture)
		self.assertTrue(appointment)
		with self.assertRaises(frappe.PermissionError):
			comm.save_settings({"reminders_enabled": 1})
		self.assertFalse(frappe.has_permission("WA Settings", "read"))

	def test_forged_link_rejected_and_patient_creation_explicit(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": api.INQUIRY,
					"patient_name": "Forged",
					"mobile_number": "0522207872",
					"wa_profile": "forged",
				}
			).insert()
		if not frappe.db.exists("Gender", "Other"):
			frappe.get_doc({"doctype": "Gender", "gender": "Other"}).insert()
		doc = self.inquiry()
		count = frappe.db.count("Patient")
		self.assertEqual(count, 0)
		patient = api.create_patient(doc.name, "Other", identity_verified=True)
		self.assertEqual(frappe.db.count("Patient"), count + 1)
		self.assertEqual(api.create_patient(doc.name, "Other"), patient)

	def test_unavailability_blocks_slots(self):
		fixture = healthcare_fixture()
		doc = self.inquiry()
		availability = frappe.get_doc(
			{
				"doctype": "Practitioner Availability",
				"type": "Unavailable",
				"scope_type": "Healthcare Practitioner",
				"scope": fixture.practitioner,
				"status": "Active",
				"start_date": fixture.date,
				"end_date": fixture.date,
				"start_time": "09:00",
				"end_time": "12:00",
				"repeat": "Never",
			}
		).insert()
		availability.submit()
		args = dict(fixture)
		args.pop("service_unit")
		self.assertFalse(api.slots(doc.name, **args))

	def test_approved_template_outside_window_and_failures_are_honest(self):
		self.account()
		doc = self.inquiry(whatsapp_consent=1)
		template = frappe.get_doc(
			{
				"doctype": "WA Template",
				"template_label": "Isolated confirmation",
				"template_name": "isolated_confirmation",
				"template_type": "Utility",
				"language": "en_US",
				"message": "Your appointment request is ready.",
				"status": "Approved",
			}
		)
		template.flags.from_sync = True
		template.insert()
		client = MagicMock()
		client.send_message.return_value = {"messages": [{"id": "mock-template-ack"}]}
		with patch(
			"whatsapp.whatsapp.doctype.wa_message.wa_message._get_whatsapp_client", return_value=client
		):
			result = comm.send(doc.name, "approved-template", template=template.name)
			self.assertEqual(result["status"], "Sent")
			self.assertEqual(client.send_message.call_count, 1)
			client.send_message.side_effect = RuntimeError("Simulated transport failure")
			failed = comm.send(doc.name, "failed-template", template=template.name)
			self.assertEqual(failed["status"], "Failed")
			self.assertEqual(
				comm.send(doc.name, "failed-template", template=template.name)["message_name"],
				failed["message_name"],
			)
			self.assertEqual(client.send_message.call_count, 2)
		template.db_set("status", "Rejected")
		with self.assertRaises(frappe.ValidationError):
			comm.send(doc.name, "rejected-template", template=template.name)

	def test_csv_import_preview_dedup_and_no_messages(self):
		file = self.private_file(
			"Name,Mobile,Service,Date,Notes\nFirst,0522207872,Dental,2030-01-02,Hello\nFirst,+971522207872,Dental,2030-01-02,Hello\nFirst,0522207872,General,2030-01-03,Followup\n"
		)
		mapping = {
			"patient_name": 0,
			"mobile_number": 1,
			"requested_service": 2,
			"preferred_date": 3,
			"notes": 4,
		}
		before = frappe.db.count("WA Message")
		preview = inquiry_import.preview(file.name, mapping)
		self.assertEqual([r["duplicate"] for r in preview], [False, True, False])
		self.assertEqual(inquiry_import.import_rows(file.name, mapping, True), {"created": 2, "skipped": 1})
		self.assertEqual(inquiry_import.import_rows(file.name, mapping, True), {"created": 0, "skipped": 3})
		self.assertEqual(frappe.db.count("WA Message"), before)
		self.assertEqual(frappe.db.count(api.INQUIRY, {"source": "Import"}), 2)

	def test_xlsx_and_invalid_import(self):
		from openpyxl import Workbook

		book = Workbook()
		book.active.append(["Name", "Mobile"])
		book.active.append(["Excel contact", "0522207872"])
		stream = io.BytesIO()
		book.save(stream)
		file = self.private_file(stream.getvalue(), "talya-test.xlsx")
		self.assertEqual(inquiry_import.columns(file.name)["count"], 1)
		self.assertFalse(
			inquiry_import.preview(file.name, {"patient_name": 0, "mobile_number": 1})[0]["error"]
		)
		bad = self.private_file("Name,Mobile\nBad,123\n", "talya-invalid.csv")
		self.assertTrue(inquiry_import.preview(bad.name, {"patient_name": 0, "mobile_number": 1})[0]["error"])
		with self.assertRaises(frappe.ValidationError):
			inquiry_import.import_rows(bad.name, {"patient_name": 0, "mobile_number": 1}, True)

	def test_incoming_linking_duplicate_webhook_and_opt_out(self):
		account = self.account()
		from whatsapp.whatsapp.webhook import _create_incoming_message

		with patch("frappe.publish_realtime") as notification:
			message = {
				"id": "isolated-message-1",
				"from": "971522207872",
				"type": "text",
				"text": {"body": "Hello"},
			}
			_create_incoming_message(message, account.name, {"name": "WhatsApp contact"})
			_create_incoming_message(message, account.name, {"name": "WhatsApp contact"})
			self.assertEqual(frappe.db.count("WA Message", {"message_id": message["id"]}), 1)
			name = frappe.db.get_value("WA Message", {"message_id": message["id"]}, "reference_docname")
			self.assertTrue(name)
			self.assertTrue(any(call.args[0] == "talya_inquiry" for call in notification.call_args_list))
			_create_incoming_message(
				{**message, "id": "isolated-message-2", "text": {"body": "STOP"}}, account.name
			)
			self.assertEqual(frappe.db.get_value(api.INQUIRY, name, "opt_out"), 1)

	def test_xlsx_extra_columns_are_rejected_without_silent_truncation(self):
		from openpyxl import Workbook

		book = Workbook()
		book.active.append(["Name", "Mobile", *[f"Column {i}" for i in range(2, 31)]])
		book.active.append(["Synthetic wide workbook", "0522207872", *([""] * 28), "Not imported"])
		stream = io.BytesIO()
		book.save(stream)
		file = self.private_file(stream.getvalue(), "talya-wide.xlsx")
		with self.assertRaises(frappe.ValidationError):
			inquiry_import.columns(file.name)
		with self.assertRaises(frappe.ValidationError):
			inquiry_import.import_rows(file.name, {"patient_name": 0, "mobile_number": 1}, True)
		self.assertEqual(frappe.db.count(api.INQUIRY), 0)

	def test_csv_extra_columns_on_later_rows_are_rejected(self):
		content = "Name,Mobile\n" + ",".join(["Synthetic wide row", "0522207872", *(["extra"] * 29)])
		file = self.private_file(content, "talya-wide.csv")
		with self.assertRaises(frappe.ValidationError):
			inquiry_import.columns(file.name)
		self.assertEqual(frappe.db.count(api.INQUIRY), 0)

	def test_send_uses_official_api_once_and_enforces_consent_window(self):
		account = self.account()
		doc = self.inquiry()
		with self.assertRaises(frappe.ValidationError):
			comm.send(doc.name, "no-consent", "Hello")
		doc.whatsapp_consent = 1
		doc.save()
		with self.assertRaises(frappe.ValidationError):
			comm.send(doc.name, "closed-window", "Hello")
		from whatsapp.whatsapp.webhook import _create_incoming_message

		_create_incoming_message(
			{"id": "isolated-reply-1", "from": "971522207872", "type": "text", "text": {"body": "Hello"}},
			account.name,
		)
		client = MagicMock()
		client.send_message.return_value = {"messages": [{"id": "mock-meta-ack"}]}
		with patch(
			"whatsapp.whatsapp.doctype.wa_message.wa_message._get_whatsapp_client", return_value=client
		):
			first = comm.send(doc.name, "same-request", "Hello")
			second = comm.send(doc.name, "same-request", "Hello")
			self.assertEqual(first["message_name"], second["message_name"])
			self.assertEqual(client.send_message.call_count, 1)
			self.assertEqual(first["status"], "Sent")
		doc.reload()
		doc.opt_out = 1
		doc.save()
		with self.assertRaises(frappe.ValidationError):
			comm.send(doc.name, "opted-out", "Hello")

	def test_webhook_signature_verification(self):
		import hashlib
		import hmac

		from werkzeug.test import EnvironBuilder
		from werkzeug.wrappers import Request
		from whatsapp.whatsapp.webhook import _verify_signature

		body = '{"entry":[]}'
		secret = "isolated-secret"
		signature = "sha256=" + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
		with patch.object(
			frappe.local,
			"request",
			Request(
				EnvironBuilder(
					method="POST", data=body, headers={"X-Hub-Signature-256": signature}
				).get_environ()
			),
			create=True,
		):
			_verify_signature(secret)
			with self.assertRaises(frappe.AuthenticationError):
				_verify_signature("wrong-secret")

	def test_reserved_send_is_not_retried_after_uncertain_failure(self):
		account = self.account()
		doc = self.inquiry(whatsapp_consent=1)
		from whatsapp.whatsapp.webhook import _create_incoming_message

		_create_incoming_message(
			{
				"id": "isolated-reservation-reply",
				"from": "971522207872",
				"type": "text",
				"text": {"body": "Hello"},
			},
			account.name,
		)
		with patch(
			"whatsapp.whatsapp.api.messages.send_message",
			side_effect=RuntimeError("Simulated process failure"),
		) as transport:
			with self.assertRaises(RuntimeError):
				comm.send(doc.name, "uncertain-send", "Hello")
			result = comm.send(doc.name, "uncertain-send", "Hello")
			self.assertEqual(result["state"], "Reserved")
			self.assertIsNone(result["message_name"])
			self.assertEqual(transport.call_count, 1)

	def test_reminder_is_opt_in_and_idempotent(self):
		fixture = healthcare_fixture()
		self.account()
		doc = self.inquiry(whatsapp_consent=1)
		api.book(doc.name, time="09:00", identity_verified=True, **fixture)
		template = frappe.get_doc(
			{
				"doctype": "WA Template",
				"template_label": "Isolated reminder",
				"template_name": "isolated_reminder",
				"template_type": "Utility",
				"language": "en_US",
				"message": "Your appointment is coming up.",
				"status": "Approved",
			}
		)
		template.flags.from_sync = True
		template.insert()
		frappe.db.set_single_value(
			"Talya Communication Settings",
			{"reminders_enabled": 1, "reminder_template": template.name, "reminder_hours": 72},
		)
		client = MagicMock()
		client.send_message.return_value = {"messages": [{"id": "mock-reminder-ack"}]}
		with patch(
			"whatsapp.whatsapp.doctype.wa_message.wa_message._get_whatsapp_client", return_value=client
		):
			comm.reminders()
			comm.reminders()
			self.assertEqual(client.send_message.call_count, 1)


def run_local():
	"""Only talya.localhost; synthetic transactions, outbound transport blocked."""
	if frappe.local.site != "talya.localhost":
		raise RuntimeError("Talya local tests are restricted to talya.localhost")
	from talya.tests.test_internal_booking import TestInternalBooking
	from talya.tests.test_online_booking_desk import TestOnlineBookingDesk
	from talya.tests.test_public_booking import TestTalyaPublicBooking
	from talya.tests.test_recipient_safety import TestRecipientSafety

	tables = (
		"Patient",
		"Patient Appointment",
		"Healthcare Practitioner",
		"Talya Online Booking",
		"Talya Patient Inquiry",
		"WA Account",
		"WA Message",
		"Talya Message Dispatch",
		"File",
	)
	before = {dt: frappe.db.count(dt) for dt in tables}
	if before["WA Account"]:
		raise RuntimeError("Use an isolated environment without live WhatsApp accounts")
	suite = unittest.TestSuite(
		[
			unittest.defaultTestLoader.loadTestsFromTestCase(TestPatientInquiries),
			unittest.defaultTestLoader.loadTestsFromTestCase(TestRecipientSafety),
			unittest.defaultTestLoader.loadTestsFromTestCase(TestInternalBooking),
			unittest.defaultTestLoader.loadTestsFromTestCase(TestOnlineBookingDesk),
		]
	)
	# Reuse the public-booking assertions without invoking Frappe's fixture-creating
	# IntegrationTestCase lifecycle. The isolated suite covers real public submission.
	for name in unittest.defaultTestLoader.getTestCaseNames(TestTalyaPublicBooking):

		def assertion(self, name=name):
			getattr(TestTalyaPublicBooking(name), name)()

		suite.addTest(type("PublicBookingReadChecks", (TalyaIsolationTestCase,), {"runTest": assertion})())
	result = unittest.TextTestRunner(verbosity=2).run(suite)
	frappe.db.rollback()
	after = {dt: frappe.db.count(dt) for dt in tables}
	if before != after:
		raise RuntimeError("Talya isolation check failed: record counts changed")
	if not result.wasSuccessful():
		raise RuntimeError("Talya local integration tests failed")
	return {
		"tests": result.testsRun,
		"failures": len(result.failures),
		"errors": len(result.errors),
		"meta": "mocked; external HTTP blocked",
		"isolation": "transactions rolled back; record counts unchanged",
	}
