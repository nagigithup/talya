"""Reception confirmation with real Healthcare records and rolled-back synthetic data."""

import json
from unittest.mock import patch

import frappe

from talya import online_booking
from talya.permissions import PATIENT_CLINICAL_FIELDS
from talya.tests.test_inquiries import TalyaIsolationTestCase, healthcare_fixture


class TestOnlineBookingDesk(TalyaIsolationTestCase):
	def setUp(self):
		super().setUp()
		self.fixture = healthcare_fixture()
		department = frappe.get_doc(
			{"doctype": "Medical Department", "department": "Synthetic online booking department"}
		).insert()
		self.doctor = frappe.get_doc("Healthcare Practitioner", self.fixture.practitioner)
		self.doctor.department = department.name
		self.doctor.save()
		schedule = frappe.get_doc("Practitioner Schedule", self.doctor.practitioner_schedules[0].schedule)
		schedule.time_slots[0].from_time = "11:00"
		schedule.time_slots[0].to_time = "23:00"
		schedule.save()
		self.long_type = (
			frappe.get_doc(
				{
					"doctype": "Appointment Type",
					"appointment_type": "Synthetic online 60 minute visit",
					"allow_booking_for": "Practitioner",
					"default_duration": 60,
				}
			)
			.insert()
			.name
		)
		self.booking = frappe.get_doc(
			{
				"doctype": "Talya Online Booking",
				"patient_name": "Talya isolated patient",
				"mobile_number": "٠٥٢٢٢٠٧٨٧٢",
				"medical_department": department.name,
				"healthcare_practitioner": self.doctor.name,
				"preferred_date": self.fixture.date,
				"preferred_time": "11:00",
				"consent_accepted": 1,
				"appointment_type": self.fixture.appointment_type,
				"service_unit": self.fixture.service_unit,
			}
		).insert()

	def new_values(self, **kwargs):
		return {
			"first_name": "Synthetic new family member",
			"sex": "Other",
			"mobile": "+971522207872",
			**kwargs,
		}

	def inquiry(self):
		return frappe.get_doc(
			"Talya Patient Inquiry",
			frappe.db.get_value("Talya Patient Inquiry", {"website_booking": self.booking.name}, "name"),
		)

	def assert_pending(self):
		self.booking.reload()
		self.assertEqual(self.booking.booking_status, "Pending")
		self.assertFalse(self.booking.linked_patient_appointment)

	def link(self):
		self.booking.link_verified_patient(self.fixture.patient, identity_verified=True)
		self.booking.reload()

	def test_existing_patient_explicitly_linked_then_original_action_confirms(self):
		self.assertFalse(self.booking.linked_patient)
		self.booking.link_verified_patient(self.fixture.patient, identity_verified=True)
		self.assert_pending()
		appointment = self.booking.confirm_booking()
		self.booking.reload()
		self.assertEqual(self.booking.booking_status, "Confirmed")
		self.assertEqual(self.booking.linked_patient, self.fixture.patient)
		self.assertEqual(self.booking.linked_patient_appointment, appointment)
		appt = frappe.get_doc("Patient Appointment", appointment)
		self.assertEqual(appt.duration, 30)
		self.assertEqual(appt.service_unit, self.fixture.service_unit)
		self.assertEqual(frappe.db.get_value("Event", appt.event, "send_reminder"), 0)
		self.assertFalse(self.inquiry().whatsapp_consent)
		self.assertFalse(self.inquiry().consent_recorded_at)

	def test_combined_existing_patient_uses_selected_hour_type(self):
		self.booking.appointment_type = self.long_type
		self.booking.preferred_time = "11:30"
		self.booking.save()
		appointment = self.booking.confirm_booking(patient=self.fixture.patient, identity_verified=True)
		appt = frappe.get_doc("Patient Appointment", appointment)
		self.assertEqual(appt.duration, 60)
		self.assertEqual(appt.appointment_type, self.long_type)
		self.assertEqual(str(self.booking.reload().appointment_end_time), "12:30:00")

	def test_new_patient_created_and_confirmed_without_copying_privacy_consent(self):
		appointment = self.booking.confirm_booking(
			patient_data=self.new_values(), identity_verified=True, reviewed_matches=True
		)
		self.booking.reload()
		self.assertEqual(frappe.db.count("Patient"), 2)
		self.assertNotEqual(self.booking.linked_patient, self.fixture.patient)
		self.assertEqual(
			frappe.db.get_value("Patient Appointment", appointment, "patient"), self.booking.linked_patient
		)
		self.assertTrue(self.inquiry().patient_verified_at)
		self.assertFalse(self.inquiry().whatsapp_consent)
		self.assertFalse(frappe.db.get_value("Patient", self.booking.linked_patient, "invite_user"))

	def test_shared_number_matches_are_not_automatically_linked(self):
		other = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Synthetic second family member",
				"sex": "Other",
				"dob": "1990-01-02",
				"mobile": "+971522207872",
			}
		).insert()
		matches = online_booking.patient_context(self.booking.name)["matches"]
		self.assertEqual({row["name"] for row in matches}, {self.fixture.patient, other.name})
		self.assertFalse(self.booking.reload().linked_patient)
		with self.assertRaises(frappe.ValidationError):
			self.booking.confirm_booking(patient=other.name)
		appointment = self.booking.confirm_booking(patient=other.name, identity_verified=True)
		self.assertEqual(frappe.db.get_value("Patient Appointment", appointment, "patient"), other.name)

	def test_missing_mandatory_gender_rolls_back_patient_and_booking(self):
		with self.assertRaises(frappe.MandatoryError):
			self.booking.confirm_booking(
				patient_data=self.new_values(sex=None), identity_verified=True, reviewed_matches=True
			)
		self.assert_pending()
		self.assertEqual(frappe.db.count("Patient"), 1)
		self.assertEqual(frappe.db.count("Patient Appointment"), 0)
		self.assertFalse(self.inquiry().patient_verified_at)

	def test_additional_mandatory_patient_field_is_requested_and_enforced(self):
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

		make_property_setter("Patient", "dob", "reqd", "1", "Check")
		frappe.clear_cache(doctype="Patient")
		context = online_booking.patient_context(self.booking.name)
		self.assertTrue(
			next(field for field in context["patient_fields"] if field["fieldname"] == "dob")["reqd"]
		)
		with self.assertRaises(frappe.MandatoryError):
			self.booking.confirm_booking(
				patient_data=self.new_values(), identity_verified=True, reviewed_matches=True
			)
		self.assert_pending()
		self.assertEqual(frappe.db.count("Patient"), 1)
		self.assertTrue(
			self.booking.confirm_booking(
				patient_data=self.new_values(dob="1990-01-02"), identity_verified=True, reviewed_matches=True
			)
		)

	def test_occupied_middle_of_hour_rolls_back_new_patient(self):
		from talya.inquiries import _appointment

		inquiry = self.inquiry()
		busy = _appointment(
			inquiry, self.fixture.patient, self.doctor.name, self.fixture.date, self.fixture.appointment_type
		)
		busy.update({"service_unit": self.fixture.service_unit, "appointment_time": "11:30", "duration": 30})
		busy.company = frappe.db.get_value("Healthcare Service Unit", self.fixture.service_unit, "company")
		busy.insert()
		self.booking.appointment_type = self.long_type
		self.booking.save()
		with self.assertRaises(frappe.ValidationError):
			self.booking.confirm_booking(
				patient_data=self.new_values(), identity_verified=True, reviewed_matches=True
			)
		self.assert_pending()
		self.assertEqual(frappe.db.count("Patient"), 1)
		self.assertEqual(frappe.db.count("Patient Appointment"), 1)
		self.assertFalse(self.booking.linked_patient)

	def test_repeated_existing_confirmation_returns_one_appointment(self):
		self.link()
		first = self.booking.confirm_booking()
		self.assertEqual(self.booking.confirm_booking(), first)
		self.assertEqual(frappe.db.count("Patient Appointment"), 1)

	def test_repeated_new_patient_confirmation_does_not_create_duplicate(self):
		args = {
			"patient_data": self.new_values(),
			"identity_verified": True,
			"reviewed_matches": True,
			"expected_modified": self.booking.modified,
		}
		first = self.booking.confirm_booking(**args)
		self.assertEqual(self.booking.confirm_booking(**args), first)
		self.assertEqual(frappe.db.count("Patient"), 2)
		self.assertEqual(frappe.db.count("Patient Appointment"), 1)

	def test_duplicate_same_name_and_phone_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.booking.confirm_booking(
				patient_data=self.new_values(first_name="Talya isolated patient"),
				identity_verified=True,
				reviewed_matches=True,
			)
		self.assert_pending()
		self.assertEqual(frappe.db.count("Patient"), 1)

	def test_failure_after_appointment_insert_rolls_back_every_link(self):
		counts = {
			dt: frappe.db.count(dt)
			for dt in ["Patient", "Patient Appointment", "Event", "Customer", "Contact"]
		}
		with patch(
			"talya.inquiries.sync_booking",
			side_effect=frappe.ValidationError("Synthetic final integration failure"),
		):
			with self.assertRaises(frappe.ValidationError):
				self.booking.confirm_booking(
					patient_data=self.new_values(), identity_verified=True, reviewed_matches=True
				)
		self.assert_pending()
		self.assertFalse(self.booking.linked_patient)
		self.assertFalse(self.inquiry().linked_patient)
		self.assertEqual({dt: frappe.db.count(dt) for dt in counts}, counts)

	def test_name_match_with_wrong_phone_cannot_be_confirmed(self):
		other = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Talya isolated patient",
				"sex": "Other",
				"mobile": "+12025550123",
			}
		).insert()
		matches = online_booking.patient_context(self.booking.name)["matches"]
		self.assertFalse(next(row for row in matches if row["name"] == other.name)["phone_match"])
		with self.assertRaises(frappe.ValidationError):
			self.booking.confirm_booking(patient=other.name, identity_verified=True)
		self.assert_pending()

	def test_secondary_phone_is_searched_and_prevents_duplicate_creation(self):
		other = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Synthetic secondary contact",
				"sex": "Other",
				"mobile": "+12025550123",
				"phone": "+971522207872",
			}
		).insert()
		matches = online_booking.patient_context(self.booking.name)["matches"]
		self.assertIn(other.name, {row["name"] for row in matches})
		self.assertFalse(next(row for row in matches if row["name"] == other.name)["phone_match"])
		with self.assertRaises(frappe.ValidationError):
			self.booking.confirm_booking(
				patient_data=self.new_values(first_name=other.first_name),
				identity_verified=True,
				reviewed_matches=True,
			)
		self.assert_pending()
		self.assertEqual(frappe.db.count("Patient"), 2)

	def test_unverified_legacy_link_cannot_confirm(self):
		self.booking.linked_patient = self.fixture.patient
		self.booking.save()
		with self.assertRaises(frappe.ValidationError):
			self.booking.confirm_booking()
		self.assert_pending()

	def test_booking_contact_change_invalidates_prior_patient_verification(self):
		self.link()
		self.booking.patient_name = "Synthetic different family member"
		self.booking.save()
		self.assertFalse(self.booking.linked_patient)
		self.assertEqual(self.inquiry().linked_patient, self.fixture.patient)
		with self.assertRaises(frappe.ValidationError):
			self.booking.confirm_booking()
		self.assert_pending()

	def test_phone_format_change_preserves_canonical_verification(self):
		self.link()
		self.booking.mobile_number = "+971 52 220 7872"
		self.booking.save()
		self.assertTrue(online_booking._is_verified(self.booking))

	def test_clinical_payload_is_rejected(self):
		with self.assertRaises(frappe.PermissionError):
			self.booking.confirm_booking(
				patient_data=self.new_values(medical_history="Forbidden"),
				identity_verified=True,
				reviewed_matches=True,
			)
		self.assert_pending()

	def test_new_patient_requires_review_of_possible_matches(self):
		with self.assertRaises(frappe.ValidationError):
			self.booking.confirm_booking(patient_data=self.new_values(), identity_verified=True)
		self.assert_pending()

	def test_guest_cannot_search_or_confirm(self):
		frappe.set_user("Guest")
		for action in [
			lambda: online_booking.patient_context(self.booking.name),
			lambda: self.booking.confirm_booking(),
		]:
			with self.assertRaises(frappe.PermissionError):
				action()

	def test_stale_booking_is_rejected(self):
		before = self.booking.modified
		self.booking.reception_notes = "Synthetic staff update"
		self.booking.save()
		with self.assertRaises(frappe.ValidationError):
			self.booking.confirm_booking(
				patient=self.fixture.patient, identity_verified=True, expected_modified=before
			)
		self.assert_pending()

	def test_configured_sms_is_blocked_before_any_mutation(self):
		frappe.db.set_single_value("Healthcare Settings", "send_appointment_confirmation", 1)
		with self.assertRaises(frappe.ValidationError):
			self.booking.confirm_booking(
				patient_data=self.new_values(), identity_verified=True, reviewed_matches=True
			)
		self.assert_pending()
		self.assertEqual(frappe.db.count("Patient"), 1)

	def test_reception_only_sees_permitted_identifying_details(self):
		patient = frappe.get_doc("Patient", self.fixture.patient)
		patient.medical_history = "Synthetic clinical secret"
		patient.uid = "Synthetic private identifier"
		patient.save()
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "talya-booking-test@example.invalid",
				"first_name": "Synthetic reception",
				"send_welcome_email": 0,
				"roles": [{"role": "Talya Receptionist"}],
			}
		).insert()
		frappe.set_user(user.name)
		context = online_booking.patient_context(self.booking.name)
		for field in PATIENT_CLINICAL_FIELDS:
			self.assertNotIn(field, json.dumps(context))
		self.assertNotIn("Synthetic clinical secret", json.dumps(context))
		self.assertTrue(context["matches"])
		self.booking.confirm_booking(patient=self.fixture.patient, identity_verified=True)

	def test_restricted_mandatory_field_blocks_creation_but_keeps_existing_patient_flow(self):
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

		make_property_setter("Patient", "dob", "reqd", "1", "Check")
		make_property_setter("Patient", "dob", "permlevel", "9", "Int")
		frappe.clear_cache(doctype="Patient")
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "talya-booking-restricted@example.invalid",
				"first_name": "Synthetic restricted reception",
				"send_welcome_email": 0,
				"roles": [{"role": "Talya Receptionist"}],
			}
		).insert()
		frappe.set_user(user.name)
		context = online_booking.patient_context(self.booking.name)
		self.assertFalse(context["can_create"])
		self.assertTrue(context["creation_error"])
		self.assertTrue(context["matches"])
		self.assertNotIn("dob", context["matches"][0])
		self.assertTrue(self.booking.confirm_booking(patient=self.fixture.patient, identity_verified=True))
