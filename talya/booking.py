import datetime

import frappe
from frappe import _
from frappe.utils import get_time, getdate


def get_available_slots(practitioner_name, date):
	date = getdate(date)
	if date < getdate():
		return []
	practitioner = frappe.get_doc("Healthcare Practitioner", practitioner_name)
	if practitioner.status != "Active":
		return []
	weekday = date.strftime("%A")
	booked = {
		(datetime.datetime.min + value).time().strftime("%H:%M")
		for value in frappe.get_all(
			"Patient Appointment",
			filters={
				"practitioner": practitioner.name,
				"appointment_date": date,
				"status": ["not in", ["Cancelled", "Closed"]],
			},
			pluck="appointment_time",
		)
		if value
	}
	slots = []
	for row in practitioner.practitioner_schedules:
		if not row.schedule:
			continue
		schedule = frappe.get_cached_doc("Practitioner Schedule", row.schedule)
		if schedule.disabled:
			continue
		for window in schedule.time_slots:
			if window.day != weekday:
				continue
			start = datetime.datetime.combine(date, (datetime.datetime.min + window.from_time).time())
			end = datetime.datetime.combine(date, (datetime.datetime.min + window.to_time).time())
			duration = int(window.duration or 0)
			if duration <= 0:
				continue
			while start + datetime.timedelta(minutes=duration) <= end:
				value = start.strftime("%H:%M")
				if value not in booked and start > frappe.utils.now_datetime():
					slots.append(value)
				start += datetime.timedelta(minutes=duration)
	return sorted(set(slots))


def validate_public_practitioner(name, department=None):
	values = frappe.db.get_value(
		"Healthcare Practitioner",
		name,
		[
			"name",
			"department",
			"status",
			"custom_show_on_talya_website",
			"custom_enable_talya_online_booking",
		],
		as_dict=True,
	)
	if not values or values.status != "Active" or not values.custom_show_on_talya_website:
		frappe.throw(_("The selected practitioner is not available for public booking."))
	if not values.custom_enable_talya_online_booking:
		frappe.throw(_("Online booking is not enabled for the selected practitioner."))
	if department and values.department != department:
		frappe.throw(_("The selected practitioner does not belong to this department."))
	return values


def get_service_unit_for_slot(practitioner_name, date, time):
	date = getdate(date)
	wanted = str(time)[:5]
	weekday = date.strftime("%A")
	practitioner = frappe.get_doc("Healthcare Practitioner", practitioner_name)
	for row in practitioner.practitioner_schedules:
		if not row.schedule or not row.service_unit:
			continue
		schedule = frappe.get_cached_doc("Practitioner Schedule", row.schedule)
		if schedule.disabled:
			continue
		for window in schedule.time_slots:
			if window.day != weekday or not window.duration:
				continue
			start = datetime.datetime.combine(date, (datetime.datetime.min + window.from_time).time())
			end = datetime.datetime.combine(date, (datetime.datetime.min + window.to_time).time())
			while start + datetime.timedelta(minutes=int(window.duration)) <= end:
				if start.strftime("%H:%M") == wanted:
					return row.service_unit
				start += datetime.timedelta(minutes=int(window.duration))
	return None


def create_patient_appointment(booking):
	from talya.internal_booking import availability
	from talya.recipients import assert_patient_recipient, normalize_phone

	assert_patient_recipient(
		frappe._dict(normalized_phone=normalize_phone(booking.mobile_number)), booking.linked_patient
	)
	inquiry = frappe.db.get_value("Talya Patient Inquiry", {"website_booking": booking.name}, "name")
	if inquiry:
		assert_patient_recipient(frappe.get_doc("Talya Patient Inquiry", inquiry), booking.linked_patient)
	for dt, value in (
		("Patient", booking.linked_patient),
		("Healthcare Practitioner", booking.healthcare_practitioner),
	):
		frappe.get_doc(dt, value).check_permission("read")
		frappe.db.get_value(dt, value, "name", for_update=True)
	validate_public_practitioner(booking.healthcare_practitioner, booking.medical_department)
	appointment_type = booking.get("appointment_type") or frappe.db.get_single_value(
		"Healthcare Settings", "default_appointment_type"
	)
	if not appointment_type:
		frappe.throw(_("Configure the default Healthcare appointment type before confirming requests."))
	appointment_for = frappe.db.get_value("Appointment Type", appointment_type, "allow_booking_for")
	if appointment_for != "Practitioner":
		frappe.throw(_("The default Healthcare appointment type must allow Practitioner booking."))
	frappe.get_doc("Appointment Type", appointment_type).check_permission("read")
	frappe.has_permission("Patient Appointment", "create", throw=True)
	service_unit = booking.get("service_unit")
	company = frappe.defaults.get_user_default("company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	doc = frappe.new_doc("Patient Appointment")
	doc.update(
		{
			"patient": booking.linked_patient,
			"appointment_type": appointment_type,
			"appointment_for": appointment_for,
			"practitioner": booking.healthcare_practitioner,
			"department": booking.medical_department,
			"service_unit": service_unit,
			"appointment_date": booking.preferred_date,
			"appointment_time": get_time(booking.preferred_time),
			"company": company,
			"notes": booking.patient_notes,
			"reference_doctype": "Talya Online Booking",
			"reference_docname": booking.name,
		}
	)
	if not service_unit:
		units = availability(doc)["service_units"]
		if not units:
			frappe.throw(_("No Healthcare Service Unit is configured for the selected slot."))
		if len(units) != 1:
			frappe.throw(_("Select a service unit before confirming."))
		service_unit = doc.service_unit = units[0]
	frappe.db.get_value("Healthcare Service Unit", service_unit, "name", for_update=True)
	doc.company = frappe.db.get_value("Healthcare Service Unit", service_unit, "company") or company
	if not doc.company:
		frappe.throw(_("Configure the company for this Healthcare service unit."))
	frappe.get_doc("Company", doc.company).check_permission("read")
	choice = next(
		(
			row
			for row in availability(doc, lock=True)["slots"]
			if get_time(row["time"]) == get_time(booking.preferred_time)
			and row["service_unit"] == service_unit
		),
		None,
	)
	if not choice:
		frappe.throw(_("The requested slot is no longer available. Please select another slot."))
	doc.duration = choice["duration"]
	doc.insert()
	# Only this newly created event is changed; no reminder is enabled by confirmation.
	if doc.event:
		frappe.db.set_value("Event", doc.event, "send_reminder", 0, update_modified=False)
	return doc
