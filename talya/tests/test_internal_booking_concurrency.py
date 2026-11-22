"""Explicit local-only, two-connection race verification with disposable fixtures."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from threading import Event
from unittest.mock import patch

import frappe

from talya import internal_booking
from talya.tests.test_inquiries import healthcare_fixture


def run_local():
	if frappe.local.site != "talya.localhost" or frappe.db.count("WA Account"):
		raise RuntimeError("Concurrency fixtures require talya.localhost without live WhatsApp accounts")
	sites_path = frappe.local.sites_path
	tracked = []
	appointments = []
	with ExitStack() as isolation:
		for target in (
			"frappe.sendmail",
			"frappe.enqueue",
			"frappe.utils.background_jobs.enqueue",
			"frappe.publish_realtime",
			"healthcare.healthcare.doctype.patient_appointment.patient_appointment.send_confirmation_msg",
			"healthcare.healthcare.doctype.patient_appointment.patient_appointment.PatientAppointment.insert_calendar_event",
			"healthcare.healthcare.doctype.patient.patient.send_registration_sms",
			"healthcare.healthcare.doctype.patient.patient.create_customer",
			"healthcare.healthcare.doctype.patient.patient.Patient.set_contact",
		):
			isolation.enter_context(patch(target))
		isolation.enter_context(
			patch("requests.sessions.Session.request", side_effect=AssertionError("External HTTP blocked"))
		)
		frappe.set_user("Administrator")
		fixture = healthcare_fixture()
		practitioner = frappe.get_doc("Healthcare Practitioner", fixture.practitioner)
		schedule = frappe.get_doc("Practitioner Schedule", practitioner.practitioner_schedules[0].schedule)
		schedule.time_slots[0].from_time = "11:00"
		schedule.time_slots[0].to_time = "23:00"
		schedule.save()
		unit_type = frappe.db.get_value("Healthcare Service Unit", fixture.service_unit, "service_unit_type")
		patient = frappe.get_doc(
			{"doctype": "Patient", "first_name": "Synthetic concurrency B", "sex": "Other"}
		).insert()
		other = frappe.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "Synthetic concurrency B",
				"status": "Active",
				"practitioner_schedules": [{"schedule": schedule.name, "service_unit": fixture.service_unit}],
			}
		).insert()
		tracked = [
			("Patient", patient.name),
			("Patient", fixture.patient),
			("Appointment Type", fixture.appointment_type),
			("Healthcare Practitioner", other.name),
			("Healthcare Practitioner", fixture.practitioner),
			("Practitioner Schedule", schedule.name),
			("Healthcare Service Unit", fixture.service_unit),
			("Healthcare Service Unit Type", unit_type),
		]
		frappe.db.commit()
		try:
			for case, waiting_doctor in [("doctor", fixture.practitioner), ("room", other.name)]:
				snapshot, inserted, release, attempting = Event(), Event(), Event(), Event()
				name = "SYNTHETIC-TALYA-RACE-" + case
				appointments.append(name)

				def connection(writer):
					frappe.init(site="talya.localhost", sites_path=sites_path)
					frappe.connect()
					frappe.set_user("Administrator")
					try:
						doc = frappe.get_doc(
							{
								"doctype": "Patient Appointment",
								"appointment_for": "Practitioner",
								"patient": fixture.patient if writer else patient.name,
								"practitioner": fixture.practitioner if writer else waiting_doctor,
								"service_unit": fixture.service_unit,
								"appointment_date": fixture.date,
								"appointment_time": "11:00",
								"appointment_type": fixture.appointment_type,
								"company": frappe.db.get_value(
									"Healthcare Service Unit", fixture.service_unit, "company"
								),
							}
						)
						if writer:
							assert snapshot.wait(15), "Reader did not establish its snapshot"
							doc.insert(set_name=name)
							inserted.set()
							assert release.wait(15), "Writer was not released"
							frappe.db.commit()
							return "saved"
						assert internal_booking.availability(doc)["slots"][0]["time"] == "11:00"
						snapshot.set()
						assert inserted.wait(15), "Writer did not save"
						attempting.set()
						try:
							doc.insert(set_name=name + "-B")
						except frappe.ValidationError as error:
							assert "no longer available" in str(error)
							return "overlap rejected"
						raise AssertionError("Two overlapping visits were accepted")
					finally:
						frappe.db.rollback()
						frappe.destroy()

				with ThreadPoolExecutor(max_workers=2) as executor:
					writer = executor.submit(connection, True)
					reader = executor.submit(connection, False)
					try:
						assert attempting.wait(15), "Reader never attempted a concurrent save"
						assert not reader.done(), "Reader did not wait for the resource lock"
					finally:
						release.set()
					assert writer.result(timeout=20) == "saved"
					assert reader.result(timeout=20) == "overlap rejected"
				frappe.db.rollback()
				frappe.delete_doc("Patient Appointment", name, force=True, delete_permanently=True)
				frappe.db.commit()
			return {
				"doctor_race": "one saved, stale-snapshot overlap rejected",
				"room_race": "one saved, stale-snapshot overlap rejected",
			}
		finally:
			frappe.db.rollback()
			for name in appointments:
				for candidate in (name + "-B", name):
					if frappe.db.exists("Patient Appointment", candidate):
						frappe.delete_doc(
							"Patient Appointment", candidate, force=True, delete_permanently=True
						)
			for doctype, name in tracked:
				frappe.delete_doc(doctype, name, force=True, delete_permanently=True)
			frappe.db.commit()
			frappe.clear_cache()
