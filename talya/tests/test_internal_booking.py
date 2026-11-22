"""Real Healthcare records in rolled-back transactions; no messaging transport."""

import datetime
from unittest.mock import patch

import frappe
from frappe.utils import get_time, getdate

from talya import internal_booking
from talya.tests.test_inquiries import TalyaIsolationTestCase, healthcare_fixture


class TestInternalBooking(TalyaIsolationTestCase):
	def setUp(self):
		super().setUp()
		self.fixture = healthcare_fixture()
		self.practitioner = frappe.get_doc("Healthcare Practitioner", self.fixture.practitioner)
		self.schedule = frappe.get_doc(
			"Practitioner Schedule", self.practitioner.practitioner_schedules[0].schedule
		)
		self.schedule.time_slots[0].from_time = "11:00:00"
		self.schedule.time_slots[0].to_time = "23:00:00"
		self.schedule.save()
		self.long_type = (
			frappe.get_doc(
				{
					"doctype": "Appointment Type",
					"appointment_type": "Synthetic internal 60 minute visit",
					"allow_booking_for": "Practitioner",
					"default_duration": 60,
				}
			)
			.insert()
			.name
		)
		self.unit = self.fixture.service_unit
		self.company = frappe.db.get_value("Healthcare Service Unit", self.unit, "company")

	def draft(self, duration=30, practitioner=None, unit=None, patient=None, time="11:00"):
		return frappe.get_doc(
			{
				"doctype": "Patient Appointment",
				"patient": patient or self.fixture.patient,
				"practitioner": practitioner or self.practitioner.name,
				"service_unit": unit or self.unit,
				"appointment_for": "Practitioner",
				"company": self.company,
				"appointment_date": self.fixture.date,
				"appointment_time": time,
				"appointment_type": self.long_type if duration == 60 else self.fixture.appointment_type,
				"duration": duration,
			}
		)

	def times(self, duration=30, **kwargs):
		return [row["time"] for row in internal_booking.availability(self.draft(duration, **kwargs))["slots"]]

	def other_patient(self):
		return (
			frappe.get_doc(
				{
					"doctype": "Patient",
					"first_name": "Synthetic second internal patient",
					"sex": "Other",
					"mobile": "+12025550124",
				}
			)
			.insert()
			.name
		)

	def other_unit(self):
		return (
			frappe.get_doc(
				{
					"doctype": "Healthcare Service Unit",
					"healthcare_service_unit_name": "Synthetic second internal room",
					"company": self.company,
					"service_unit_type": frappe.db.get_value(
						"Healthcare Service Unit", self.unit, "service_unit_type"
					),
				}
			)
			.insert()
			.name
		)

	def other_practitioner(self, unit):
		return (
			frappe.get_doc(
				{
					"doctype": "Healthcare Practitioner",
					"first_name": "Synthetic second internal doctor",
					"status": "Active",
					"practitioner_schedules": [{"schedule": self.schedule.name, "service_unit": unit}],
				}
			)
			.insert()
			.name
		)

	def test_half_hour_starts_for_both_durations_and_final_end(self):
		for duration, count, last in [(30, 24, "22:30"), (60, 23, "22:00")]:
			rows = internal_booking.availability(self.draft(duration))["slots"]
			self.assertEqual(len(rows), count)
			self.assertEqual([row["time"] for row in rows[:3]], ["11:00", "11:30", "12:00"])
			self.assertEqual(rows[-1]["time"], last)
			self.assertEqual(rows[-1]["end_time"], "23:00")
			self.assertTrue(all(row["duration"] == duration for row in rows))

	def test_wrong_final_start_rejected_on_direct_save(self):
		with self.assertRaises(frappe.ValidationError):
			self.draft(60, time="22:30").insert()
		self.assertEqual(frappe.db.count("Patient Appointment"), 0)
		self.assertEqual(self.draft(60, time="22:00").insert().duration, 60)

	def test_off_grid_minutes_and_seconds_are_rejected(self):
		for time in ("11:15", "11:00:30"):
			with self.assertRaises(frappe.ValidationError):
				self.draft(time=time).insert()

	def test_hour_visit_blocks_both_half_hours_and_accepts_next_visit(self):
		self.draft(60).insert()
		for duration in (30, 60):
			self.assertNotIn("11:00", self.times(duration))
			self.assertNotIn("11:30", self.times(duration))
			self.assertIn("12:00", self.times(duration))
		with self.assertRaises(frappe.ValidationError):
			self.draft(30, time="11:30").insert()
		self.draft(30, time="12:00").insert()
		self.assertIn("12:30", self.times(30))

	def test_cancellation_releases_entire_hour(self):
		appointment = self.draft(60).insert()
		appointment.status = "Cancelled"
		appointment.save()
		self.assertIn("11:00", self.times(30))
		self.assertIn("11:30", self.times(60))

	def test_room_conflicts_are_checked_for_another_doctor(self):
		self.draft(60).insert()
		other = self.other_practitioner(self.unit)
		patient = self.other_patient()
		self.assertNotIn("11:30", self.times(30, practitioner=other, patient=patient))
		with self.assertRaises(frappe.ValidationError):
			self.draft(30, practitioner=other, patient=patient, time="11:30").insert()
		self.draft(30, practitioner=other, patient=patient, time="12:00").insert()

	def test_doctor_conflicts_are_checked_across_rooms(self):
		self.draft(60).insert()
		unit = self.other_unit()
		self.practitioner.append(
			"practitioner_schedules", {"schedule": self.schedule.name, "service_unit": unit}
		)
		self.practitioner.save()
		self.assertNotIn("11:30", self.times(30, unit=unit, patient=self.other_patient()))

	def test_two_doctors_in_separate_rooms_can_book_concurrently_in_time(self):
		self.draft(60).insert()
		unit = self.other_unit()
		other = self.other_practitioner(unit)
		patient = self.other_patient()
		self.assertIn("11:00", self.times(60, practitioner=other, unit=unit, patient=patient))
		self.draft(60, practitioner=other, unit=unit, patient=patient).insert()
		self.assertEqual(frappe.db.count("Patient Appointment"), 2)

	def test_break_cannot_be_crossed_by_full_visit(self):
		day = self.schedule.time_slots[0].day
		self.schedule.set(
			"time_slots",
			[
				{"day": day, "from_time": "11:00", "to_time": "14:00", "duration": 30},
				{"day": day, "from_time": "15:00", "to_time": "23:00", "duration": 30},
			],
		)
		self.schedule.save()
		self.assertIn("13:00", self.times(60))
		self.assertNotIn("13:30", self.times(60))
		self.assertNotIn("14:30", self.times(30))
		self.assertIn("15:00", self.times(60))

	def test_adjacent_windows_allow_a_full_hour_across_boundary(self):
		day = self.schedule.time_slots[0].day
		self.schedule.set(
			"time_slots",
			[
				{"day": day, "from_time": "11:00", "to_time": "11:30", "duration": 30},
				{"day": day, "from_time": "11:30", "to_time": "23:00", "duration": 30},
			],
		)
		self.schedule.save()
		self.assertIn("11:00", self.times(60))

	def test_room_closure_blocks_complete_visit(self):
		closure = frappe.get_doc(
			{
				"doctype": "Practitioner Availability",
				"type": "Unavailable",
				"scope_type": "Healthcare Service Unit",
				"scope": self.unit,
				"status": "Active",
				"start_date": self.fixture.date,
				"end_date": self.fixture.date,
				"start_time": "13:00",
				"end_time": "14:00",
				"repeat": "Never",
			}
		).insert()
		closure.submit()
		self.assertNotIn("12:30", self.times(60))
		self.assertIn("12:30", self.times(30))
		self.assertNotIn("13:00", self.times(30))
		self.assertIn("14:00", self.times(60))

	def test_editing_self_does_not_block_its_current_slot(self):
		appointment = self.draft(60).insert()
		self.assertIn("11:00", [row["time"] for row in internal_booking.availability(appointment)["slots"]])
		appointment.notes = "Synthetic administrative update"
		appointment.appointment_date = str(appointment.appointment_date)
		appointment.appointment_time = "11:00:00"
		with patch(
			"talya.internal_booking.now_datetime",
			return_value=datetime.datetime.combine(getdate(self.fixture.date), get_time("15:00")),
		):
			appointment.save()
		self.assertEqual(appointment.duration, 60)

	def test_guest_cannot_read_internal_availability(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			internal_booking.slots(self.practitioner.name, self.fixture.date, self.long_type)
