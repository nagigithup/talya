"""P0 regressions: synthetic DB transactions and blocked external transport only."""

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import now_datetime

from talya import communication as comm
from talya import inquiries as api
from talya import setup
from talya.permissions import PATIENT_CLINICAL_FIELDS
from talya.tests.test_inquiries import TalyaIsolationTestCase, healthcare_fixture


class TestRecipientSafety(TalyaIsolationTestCase):
	def user(self, role="Talya Receptionist"):
		return frappe.get_doc(
			{
				"doctype": "User",
				"email": "talya-p0-" + role.replace(" ", "-").lower() + "@example.invalid",
				"first_name": "Synthetic P0 Staff",
				"send_welcome_email": 0,
				"roles": [{"role": role}],
			}
		).insert()

	def patient(self, phone, name="Synthetic P0 Patient"):
		if not frappe.db.exists("Gender", "Other"):
			frappe.get_doc({"doctype": "Gender", "gender": "Other"}).insert()
		return frappe.get_doc(
			{"doctype": "Patient", "first_name": name, "sex": "Other", "mobile": phone}
		).insert()

	def incoming(self, account, message_id="p0-incoming", body="Synthetic inbound"):
		from whatsapp.whatsapp.webhook import _create_incoming_message

		_create_incoming_message(
			{"id": message_id, "from": "971522207872", "type": "text", "text": {"body": body}}, account.name
		)
		return frappe.get_doc("WA Message", {"message_id": message_id})

	def website_booking(self, fixture, time="09:00"):
		department = (
			frappe.db.exists("Medical Department", "Synthetic P0 Department")
			or frappe.get_doc({"doctype": "Medical Department", "department": "Synthetic P0 Department"})
			.insert()
			.name
		)
		return frappe.get_doc(
			{
				"doctype": "Talya Online Booking",
				"patient_name": "Synthetic Website Contact",
				"mobile_number": "0522207872",
				"medical_department": department,
				"healthcare_practitioner": fixture.practitioner,
				"preferred_date": fixture.date,
				"preferred_time": time,
				"consent_accepted": 1,
				"patient_notes": "Original source notes",
			}
		).insert()

	def test_local_international_and_arabic_phone_formats(self):
		for value in ("0522207872", "+971 52 220 7872", "00971 52 2207872", "٠٥٢٢٢٠٧٨٧٢", "۰۵۲۲۲۰۷۸۷۲"):
			self.assertEqual(api.normalize_phone(value), "+971522207872")

	def test_guest_reception_and_recovery_redirects_are_temporary(self):
		from talya.www import desk_recovery, patient_inquiries

		frappe.set_user("Guest")
		with patch.object(frappe.local, "flags", frappe._dict()):
			for module in (patient_inquiries, desk_recovery):
				with self.assertRaises(frappe.Redirect) as caught:
					module.get_context(frappe._dict())
				self.assertEqual(caught.exception.http_status_code, 302)
				self.assertTrue(frappe.local.flags.redirect_location.startswith("/login?redirect-to="))

	def test_phone_shaped_country_code_cannot_be_saved(self):
		for invalid in ("971123456789", "999", "0"):
			doc = api.settings()
			doc.country_calling_code = invalid
			with self.assertRaises(frappe.ValidationError):
				doc.save()
		self.assertEqual(
			frappe.db.get_single_value("Talya Communication Settings", "country_calling_code"), "971"
		)

	def test_recipient_change_invalidates_consent_patient_profile_and_old_history(self):
		fixture = healthcare_fixture()
		account = self.account()
		doc = self.inquiry(whatsapp_consent=1)
		api.verify_patient(doc.name, fixture.patient, identity_verified=True)
		message = self.incoming(account)
		doc.reload()
		old_profile = doc.wa_profile
		self.assertEqual(message.reference_docname, doc.name)
		self.assertTrue(doc.patient_verified_at)
		api.save_inquiry({"mobile_number": "+971501234567", "whatsapp_consent": 1}, doc.name)
		doc.reload()
		self.assertEqual(doc.whatsapp_consent, 0)
		for field in (
			"consent_recorded_at",
			"consent_phone",
			"linked_patient",
			"wa_profile",
			"patient_verified_at",
		):
			self.assertFalse(doc.get(field), field)
		self.assertTrue(doc.recipient_changed_at)
		profile = frappe.get_doc("WA Profile", old_profile)
		self.assertFalse(
			any(r.link_doctype == api.INQUIRY and r.link_name == doc.name for r in profile.links)
		)
		self.assertTrue(
			any(r.link_doctype == "Patient" and r.link_name == fixture.patient for r in profile.links)
		)
		self.assertEqual(comm.conversation(doc)["messages"], [])
		self.assertTrue(frappe.db.exists("WA Message", message.name))
		with self.assertRaises(frappe.ValidationError):
			comm.send(doc.name, "p0-denied", "Never sent")
		self.assertEqual(frappe.db.count("Talya Message Dispatch"), 0)

	def test_formatting_only_change_preserves_verified_recipient(self):
		fixture = healthcare_fixture()
		doc = self.inquiry(whatsapp_consent=1)
		api.verify_patient(doc.name, fixture.patient, identity_verified=True)
		doc.reload()
		before = (doc.consent_recorded_at, doc.patient_verified_at)
		api.save_inquiry({"mobile_number": "+971 52 220 7872", "whatsapp_consent": 1}, doc.name)
		doc.reload()
		self.assertEqual(doc.whatsapp_consent, 1)
		self.assertEqual(doc.consent_phone, doc.normalized_phone)
		self.assertEqual((doc.consent_recorded_at, doc.patient_verified_at), before)
		self.assertEqual(doc.linked_patient, fixture.patient)

	def test_new_consent_requires_a_second_explicit_save_for_changed_number(self):
		doc = self.inquiry(whatsapp_consent=1)
		api.save_inquiry({"mobile_number": "+971501234567", "whatsapp_consent": 1}, doc.name)
		doc.reload()
		self.assertFalse(doc.whatsapp_consent)
		api.save_inquiry({"whatsapp_consent": 1}, doc.name)
		doc.reload()
		self.assertTrue(doc.whatsapp_consent)
		self.assertEqual(doc.consent_phone, "+971501234567")
		self.assertTrue(doc.consent_recorded_at)

	def test_legacy_unbound_consent_cannot_be_reused_or_forged(self):
		self.account()
		doc = self.inquiry(whatsapp_consent=1)
		doc.db_set("consent_phone", None)
		doc.reload()
		with self.assertRaises(frappe.ValidationError):
			comm.send(doc.name, "p0-legacy", "Never sent")
		api.save_inquiry({"whatsapp_consent": 1, "consent_phone": doc.normalized_phone}, doc.name)
		doc.reload()
		self.assertFalse(doc.whatsapp_consent)
		self.assertFalse(doc.consent_phone)

	def test_client_flags_cannot_forge_patient_verification(self):
		fixture = healthcare_fixture()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": api.INQUIRY,
					"patient_name": "Synthetic forged association",
					"mobile_number": "+971522207872",
					"linked_patient": fixture.patient,
					"patient_verified_at": now_datetime(),
					"flags": {"integration_update": True, "verify_patient": True},
				}
			).insert()
		doc = self.inquiry()
		doc.db_set("linked_patient", fixture.patient)
		payload = doc.reload().as_dict()
		payload.update(
			patient_verified_at=now_datetime(),
			flags={"integration_update": True, "verify_patient": True},
		)
		frappe.get_doc(payload).save()
		self.assertFalse(doc.reload().patient_verified_at)

	def test_booked_recipient_cannot_be_reassigned(self):
		fixture = healthcare_fixture()
		doc = self.inquiry(whatsapp_consent=1)
		appointment = api.book(doc.name, time="09:00", identity_verified=True, **fixture)
		with self.assertRaises(frappe.ValidationError):
			api.save_inquiry({"mobile_number": "+971501234567"}, doc.name)
		doc.reload()
		self.assertEqual(doc.linked_patient, fixture.patient)
		self.assertEqual(doc.linked_patient_appointment, appointment)
		self.assertEqual(doc.normalized_phone, "+971522207872")

	def test_wrong_phone_patient_is_rejected_before_booking_or_linking(self):
		fixture = healthcare_fixture()
		doc = self.inquiry(mobile_number="+971501234567")
		with self.assertRaises(frappe.ValidationError):
			api.verify_patient(doc.name, fixture.patient, identity_verified=True)
		with self.assertRaises(frappe.ValidationError):
			api.book(doc.name, time="09:00", identity_verified=True, **fixture)
		self.assertEqual(frappe.db.count("Patient Appointment"), 0)
		self.assertFalse(frappe.db.get_value(api.INQUIRY, doc.name, "linked_patient"))

	def test_shared_number_requires_explicit_identity_and_cannot_switch_patients(self):
		fixture = healthcare_fixture()
		other = self.patient("+971522207872", "Synthetic Shared Number Patient")
		doc = self.inquiry(whatsapp_consent=1)
		self.assertEqual(len(api.matching_patients(doc.name)), 2)
		with self.assertRaises(frappe.ValidationError):
			api.book(doc.name, time="09:00", **fixture)
		with self.assertRaises(frappe.ValidationError):
			api.verify_patient(doc.name, fixture.patient)
		api.verify_patient(doc.name, fixture.patient, identity_verified=True)
		with self.assertRaises(frappe.ValidationError):
			api.verify_patient(doc.name, other.name, identity_verified=True)
		with self.assertRaises(frappe.ValidationError):
			api.book(
				doc.name,
				time="09:00",
				identity_verified=True,
				**{**fixture, "patient": other.name},
			)
		self.assertEqual(frappe.db.count("Patient Appointment"), 0)
		doc.reload()
		self.assertEqual(doc.linked_patient, fixture.patient)

	def test_shared_or_ambiguous_incoming_does_not_pick_latest_patient(self):
		fixture = healthcare_fixture()
		other = self.patient("+971522207872", "Synthetic Second Shared Patient")
		first = self.inquiry(patient_name="First Request")
		second = self.inquiry(patient_name="Second Request")
		api.verify_patient(first.name, fixture.patient, identity_verified=True)
		api.verify_patient(second.name, other.name, identity_verified=True)
		account = self.account()
		message = self.incoming(account, "p0-shared-first")
		self.assertNotIn(message.reference_docname, (first.name, second.name))
		review = frappe.get_doc(api.INQUIRY, message.reference_docname)
		self.assertFalse(review.linked_patient)
		self.assertFalse(review.linked_patient_appointment)
		self.assertFalse(review.whatsapp_consent)
		followup = self.incoming(account, "p0-shared-second")
		self.assertEqual(followup.reference_docname, review.name)
		self.assertFalse(
			any(r.link_doctype == "Patient" for r in frappe.get_doc("WA Profile", review.wa_profile).links)
		)

	def test_multiple_unlinked_requests_also_get_an_unlinked_review_thread(self):
		first, second = self.inquiry(), self.inquiry()
		message = self.incoming(self.account())
		self.assertNotIn(message.reference_docname, (first.name, second.name))
		self.assertFalse(frappe.db.get_value(api.INQUIRY, message.reference_docname, "linked_patient"))

	def test_incoming_continues_a_single_verified_booked_thread(self):
		fixture = healthcare_fixture()
		doc = self.inquiry()
		api.book(doc.name, time="09:00", identity_verified=True, **fixture)
		message = self.incoming(self.account())
		self.assertEqual(message.reference_docname, doc.name)
		self.assertEqual(frappe.db.count(api.INQUIRY), 1)
		doc.reload()
		self.assertEqual(doc.status, "Booked")

	def test_incoming_wrong_patient_legacy_link_is_not_reused(self):
		fixture = healthcare_fixture()
		patient = frappe.get_doc("Patient", fixture.patient)
		patient.mobile = "+971501234567"
		patient.save()
		doc = self.inquiry()
		doc.db_set({"linked_patient": patient.name, "patient_verified_at": now_datetime()})
		message = self.incoming(self.account())
		self.assertNotEqual(message.reference_docname, doc.name)
		self.assertFalse(frappe.db.get_value(api.INQUIRY, message.reference_docname, "linked_patient"))

	def test_existing_wrong_patient_link_cannot_send(self):
		fixture = healthcare_fixture()
		doc = self.inquiry(mobile_number="+971501234567", whatsapp_consent=1)
		doc.db_set({"linked_patient": fixture.patient, "patient_verified_at": now_datetime()})
		self.account()
		with self.assertRaises(frappe.ValidationError):
			comm.send(doc.name, "p0-wrong-patient", template="does-not-matter")
		self.assertEqual(frappe.db.count("Talya Message Dispatch"), 0)

	def test_incoming_wrong_patient_appointment_is_not_reused(self):
		fixture = healthcare_fixture()
		doc = self.inquiry()
		appointment = api.book(doc.name, time="09:00", identity_verified=True, **fixture)
		other = self.patient("+971501234567")
		frappe.db.set_value("Patient Appointment", appointment, "patient", other.name)
		message = self.incoming(self.account())
		self.assertNotEqual(message.reference_docname, doc.name)
		self.assertFalse(frappe.db.get_value(api.INQUIRY, message.reference_docname, "linked_patient"))

	def test_wrong_account_message_cannot_route_or_send(self):
		account = self.account()
		doc = self.inquiry(whatsapp_consent=1)
		from whatsapp.whatsapp.doctype.wa_profile.wa_profile import get_or_create_profile

		profile = get_or_create_profile(doc.normalized_phone, account.name)
		message = frappe._dict(
			to=profile,
			whatsapp_account="synthetic-wrong-account",
			reference_doctype=api.INQUIRY,
			reference_docname=doc.name,
		)
		for direction, policy in (("Incoming", comm.incoming), ("Outgoing", comm.message_policy)):
			message.direction = direction
			with self.assertRaises(frappe.ValidationError):
				policy(message)
		self.assertEqual(frappe.db.count("WA Message"), 0)
		self.assertEqual(frappe.db.count(api.INQUIRY), 1)

	def test_direct_official_send_to_wrong_recipient_is_blocked(self):
		account = self.account()
		doc = self.inquiry(whatsapp_consent=1)
		from whatsapp.whatsapp.api.messages import send_message
		from whatsapp.whatsapp.doctype.wa_profile.wa_profile import get_or_create_profile

		wrong = get_or_create_profile("+971501234567", account.name)
		client = MagicMock()
		with patch(
			"whatsapp.whatsapp.doctype.wa_message.wa_message._get_whatsapp_client", return_value=client
		):
			with self.assertRaises(frappe.ValidationError):
				send_message(wrong, "Never sent", reference_doctype=api.INQUIRY, reference_docname=doc.name)
		client.send_message.assert_not_called()

	def test_old_recipient_attachment_is_rejected_even_after_new_consent(self):
		self.account()
		doc = self.inquiry(whatsapp_consent=1)
		file = self.private_file("Synthetic attachment", "talya-p0-attachment.csv")
		file.attached_to_doctype, file.attached_to_name = api.INQUIRY, doc.name
		file.save()
		api.save_inquiry({"mobile_number": "+971501234567"}, doc.name)
		api.save_inquiry({"whatsapp_consent": 1}, doc.name)
		with self.assertRaises(frappe.ValidationError):
			comm.send(doc.name, "p0-old-file", "Never sent", attach=file.file_url)

	def test_pending_booking_backfill_and_live_sync_preserve_reception_edits(self):
		fixture = healthcare_fixture()
		booking = self.website_booking(fixture)
		name = frappe.db.get_value(api.INQUIRY, {"website_booking": booking.name}, "name")
		new_patient = self.patient("+971501234567")
		api.save_inquiry(
			{
				"patient_name": "Staff Corrected Name",
				"mobile_number": "+971501234567",
				"notes": "Staff notes to preserve",
				"status": "Contacted",
			},
			name,
		)
		api.verify_patient(name, new_patient.name, identity_verified=True)
		before = frappe.get_doc(api.INQUIRY, name).as_dict()
		setup.backfill_booking_inquiries()
		setup.backfill_booking_inquiries()
		self.assertEqual(frappe.get_doc(api.INQUIRY, name).as_dict(), before)
		booking.patient_notes = "Updated original source notes"
		booking.save()
		self.assertEqual(frappe.get_doc(api.INQUIRY, name).as_dict(), before)
		self.assertEqual(frappe.db.count(api.INQUIRY, {"website_booking": booking.name}), 1)

	def test_backfill_missing_only_and_repeat_is_noop(self):
		fixture = healthcare_fixture()
		booking = self.website_booking(fixture)
		name = frappe.db.get_value(api.INQUIRY, {"website_booking": booking.name}, "name")
		frappe.delete_doc(api.INQUIRY, name)
		setup.backfill_booking_inquiries()
		name = frappe.db.get_value(api.INQUIRY, {"website_booking": booking.name}, "name")
		before = frappe.get_doc(api.INQUIRY, name).as_dict()
		setup.backfill_booking_inquiries()
		self.assertEqual(frappe.get_doc(api.INQUIRY, name).as_dict(), before)
		self.assertEqual(before["notes"], "Original source notes")

	def test_confirmed_booking_sync_keeps_staff_notes_and_verified_link(self):
		fixture = healthcare_fixture()
		booking = self.website_booking(fixture)
		name = frappe.db.get_value(api.INQUIRY, {"website_booking": booking.name}, "name")
		api.save_inquiry({"notes": "Staff follow-up notes"}, name)
		appointment = api.book(name, time="09:00", identity_verified=True, **fixture)
		booking.reload()
		api.sync_booking(booking)
		row = frappe.get_doc(api.INQUIRY, name)
		self.assertEqual(row.notes, "Staff follow-up notes")
		self.assertEqual(row.linked_patient_appointment, appointment)
		self.assertEqual(row.linked_patient, fixture.patient)
		self.assertTrue(row.patient_verified_at)

	def test_legacy_confirmation_wrong_patient_is_blocked_before_insert(self):
		fixture = healthcare_fixture()
		booking = self.website_booking(fixture)
		wrong = self.patient("+971501234567")
		booking.linked_patient = wrong.name
		booking.save()
		with self.assertRaises(frappe.ValidationError):
			booking.confirm_booking()
		self.assertEqual(frappe.db.count("Patient Appointment"), 0)

	def test_reception_keeps_demographics_and_booking_but_not_clinical_or_export(self):
		fixture = healthcare_fixture()
		patient = frappe.get_doc("Patient", fixture.patient)
		patient.medical_history = "Synthetic protected clinical history"
		patient.allergies = "Synthetic protected allergies"
		patient.uid = "SYNTHETIC-PROTECTED-ID"
		patient.save()
		user = self.user()
		frappe.set_user(user.name)
		from frappe.client import get

		data = get("Patient", patient.name)
		self.assertEqual(data["patient_name"], patient.patient_name)
		self.assertEqual(data["mobile"], patient.mobile)
		for field in PATIENT_CLINICAL_FIELDS:
			self.assertFalse(data.get(field), field)
		self.assertNotIn("Synthetic protected", json.dumps(data, default=str))
		listed = frappe.get_list("Patient", fields=["name", "medical_history", "uid"])
		self.assertEqual([row.name for row in listed], [patient.name])
		for row in listed:
			self.assertNotIn("medical_history", row)
			self.assertNotIn("uid", row)
		for dt in ("Patient", "Patient Appointment"):
			self.assertFalse(frappe.has_permission(dt, "export"))
			self.assertFalse(frappe.has_permission(dt, "print"))
			self.assertFalse(frappe.has_permission(dt, "share"))
		self.assertFalse(frappe.has_permission("Patient", "write"))
		self.assertFalse(frappe.has_permission("Patient Encounter", "read"))
		doc = self.inquiry()
		self.assertTrue(api.matching_patients(doc.name))
		self.assertTrue(api.book(doc.name, time="09:00", identity_verified=True, **fixture))

	def test_clinician_clinical_access_is_preserved(self):
		fixture = healthcare_fixture()
		patient = frappe.get_doc("Patient", fixture.patient)
		patient.medical_history = "Synthetic clinician-only history"
		patient.save()
		user = self.user("Physician")
		frappe.set_user(user.name)
		from frappe.client import get

		self.assertEqual(get("Patient", patient.name)["medical_history"], patient.medical_history)

	def test_public_arabic_booking_creates_one_inquiry_and_no_patient(self):
		fixture = healthcare_fixture()
		department = frappe.get_doc(
			{"doctype": "Medical Department", "department": "Synthetic Public Department"}
		).insert()
		practitioner = frappe.get_doc("Healthcare Practitioner", fixture.practitioner)
		practitioner.department = department.name
		practitioner.save()
		from talya.api import submit_booking

		payload = {
			"patient_name": "Synthetic Public Contact",
			"mobile_number": "٠٥٢٢٢٠٧٨٧٢",
			"medical_department": department.name,
			"healthcare_practitioner": fixture.practitioner,
			"preferred_date": fixture.date,
			"preferred_time": "09:00",
			"consent_accepted": 1,
			"language": "ar",
		}
		patients = frappe.db.count("Patient")
		frappe.set_user("Guest")
		result = submit_booking(**payload)
		with self.assertRaises(frappe.ValidationError):
			submit_booking(**payload)
		frappe.set_user("Administrator")
		self.assertEqual(result["status"], "Pending")
		self.assertEqual(frappe.db.count(api.INQUIRY), 1)
		self.assertEqual(frappe.db.count("Patient"), patients)
		row = frappe.get_doc(api.INQUIRY, {"website_booking": result["booking_reference"]})
		self.assertEqual(row.normalized_phone, "+971522207872")
		self.assertFalse(row.whatsapp_consent)
		self.assertTrue(row.website_booking)
