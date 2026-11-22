"""Internal Healthcare booking: half-hour starts, full visit availability, resource locks."""

import datetime
import math

import frappe
from frappe import _
from frappe.utils import cint, flt, get_time, getdate, now_datetime

STEP_MINUTES = 30
SCHEDULING_FIELDS = (
	"patient",
	"practitioner",
	"service_unit",
	"appointment_date",
	"appointment_time",
	"appointment_type",
	"duration",
)


def _moment(date, value):
	return datetime.datetime.combine(getdate(date), get_time(value))


def _windows(intervals):
	merged = []
	for start, end in sorted(intervals):
		if end <= start:
			continue
		if merged and start <= merged[-1][1]:
			merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
		else:
			merged.append((start, end))
	return merged


def _overlaps(start, end, interval):
	return start < interval[1] and end > interval[0]


def _scheduling_value(doc, field):
	value = doc.get(field)
	if field == "appointment_date" and value:
		return getdate(value)
	if field == "appointment_time" and value is not None:
		return get_time(value)
	if field == "duration":
		return cint(value)
	return value or ""


def _duration(appointment_type, lock=False):
	row = frappe.db.get_value(
		"Appointment Type",
		appointment_type,
		["allow_booking_for", "default_duration"],
		as_dict=True,
		for_update=lock,
	)
	if not row or row.allow_booking_for != "Practitioner":
		frappe.throw(_("Choose an appointment type for Practitioner booking."))
	minutes = cint(row.default_duration)
	if minutes <= 0:
		frappe.throw(_("Configure a positive appointment duration."))
	return minutes


def _busy_appointments(doc, units, lock=False):
	# A locking read is necessary after waiting for a resource: a repeatable-read
	# transaction may already hold an older snapshot from loading its inquiry.
	conditions = ["practitioner = %(practitioner)s"]
	params = {"practitioner": doc.practitioner, "date": doc.appointment_date, "name": doc.name or ""}
	if units:
		conditions.append("service_unit in %(units)s")
		params["units"] = tuple(units)
	if doc.patient:
		conditions.append("patient = %(patient)s")
		params["patient"] = doc.patient
	return frappe.db.sql(
		"""select name, practitioner, patient, service_unit, appointment_time,
			duration, appointment_type from `tabPatient Appointment`
		where appointment_date = %(date)s and name != %(name)s
		and status != 'Cancelled' and docstatus != 2 and ("""
		+ " or ".join(conditions)
		+ ")"
		+ (" for update" if lock else ""),
		params,
		as_dict=True,
	)


def availability(doc, lock=False):
	"""Use Healthcare's schedule/leave checks; do not change its public slot API."""
	from healthcare.healthcare.doctype.patient_appointment.patient_appointment import get_availability_data

	date = getdate(doc.appointment_date)
	if date < getdate():
		frappe.throw(_("Appointment date cannot be in the past."))
	if frappe.db.get_value("Healthcare Practitioner", doc.practitioner, "status") != "Active":
		frappe.throw(_("The practitioner is not active."))
	duration = _duration(doc.appointment_type, lock=lock)
	data = get_availability_data(str(date), doc.practitioner, doc)
	groups = {}
	for group in data["slot_details"]:
		unit = group.get("service_unit") or ""
		groups.setdefault(unit, [])
		for window in group.get("avail_slot", []):
			# Full-day check-in queues are a different Healthcare workflow.
			if not window.get("maximum_appointments"):
				groups[unit].append(
					(_moment(date, window.get("from_time")), _moment(date, window.get("to_time")))
				)
	units = [unit for unit in groups if unit]
	busy = _busy_appointments(doc, units, lock=lock)
	department = frappe.db.get_value("Healthcare Practitioner", doc.practitioner, "department")
	scopes = [scope for scope in [doc.practitioner, department, *units] if scope]
	# Match Healthcare's final unavailability validator, including department and
	# room closures. A closure is an interval, not an appointment-type-sized slot.
	closures = frappe.get_all(
		"Practitioner Availability",
		filters={
			"type": "Unavailable",
			"docstatus": ["!=", 2],
			"scope": ["in", scopes],
			"start_date": ["<=", date],
			"end_date": [">=", date],
		},
		fields=["scope", "start_time", "end_time"],
	)
	result = []
	room_options = []
	for unit, intervals in groups.items():
		room = frappe.get_doc("Healthcare Service Unit", unit) if unit else None
		if room and (room.is_group or not room.allow_appointments):
			continue
		if room:
			room.check_permission("read")
			room_options.append(unit)
		if doc.service_unit and unit != doc.service_unit:
			continue
		blocked = []
		room_bookings = []
		for row in busy:
			start = _moment(date, row.appointment_time)
			minutes = flt(row.duration) or flt(
				frappe.db.get_value("Appointment Type", row.appointment_type, "default_duration")
			)
			interval = (
				(start, start + datetime.timedelta(minutes=minutes))
				if minutes > 0
				else (_moment(date, "00:00"), _moment(date + datetime.timedelta(days=1), "00:00"))
			)
			if row.practitioner == doc.practitioner or (doc.patient and row.patient == doc.patient):
				blocked.append(interval)
			elif unit and row.service_unit == unit:
				room_bookings.append(interval)
		for row in closures:
			if row.scope in [doc.practitioner, department, unit]:
				start, end = _moment(date, row.start_time), _moment(date, row.end_time)
				blocked.append(
					(start, end)
					if end > start
					else (_moment(date, "00:00"), _moment(date + datetime.timedelta(days=1), "00:00"))
				)
		capacity = cint(room.service_unit_capacity) if room and room.overlap_appointments else 1
		capacity = max(1, capacity)
		for start, end in _windows(intervals):
			midnight = _moment(date, "00:00")
			minutes = (start - midnight).total_seconds() / 60
			candidate = midnight + datetime.timedelta(
				minutes=math.ceil(minutes / STEP_MINUTES) * STEP_MINUTES
			)
			while candidate + datetime.timedelta(minutes=duration) <= end:
				finish = candidate + datetime.timedelta(minutes=duration)
				if (
					candidate > now_datetime()
					and not any(_overlaps(candidate, finish, interval) for interval in blocked)
					and sum(_overlaps(candidate, finish, interval) for interval in room_bookings) < capacity
				):
					result.append(
						{
							"time": candidate.strftime("%H:%M"),
							"end_time": finish.strftime("%H:%M"),
							"end_date": str(finish.date()),
							"service_unit": unit,
							"duration": duration,
						}
					)
				candidate += datetime.timedelta(minutes=STEP_MINUTES)
	result.sort(key=lambda row: (row["time"], row["service_unit"]))
	return {
		"slots": result,
		"service_units": sorted(room_options),
		"duration": duration,
		"department": department,
	}


@frappe.whitelist(methods=["GET"])
def slots(practitioner, date, appointment_type, patient=None, service_unit=None, appointment_name=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if appointment_name:
		doc = frappe.get_doc("Patient Appointment", appointment_name)
		doc.check_permission("write")
	else:
		frappe.has_permission("Patient Appointment", "create", throw=True)
		doc = frappe.new_doc("Patient Appointment")
	for doctype, name in [
		("Healthcare Practitioner", practitioner),
		("Appointment Type", appointment_type),
		("Patient", patient),
	]:
		if name:
			frappe.get_doc(doctype, name).check_permission("read")
	doc.update(
		{
			"practitioner": practitioner,
			"appointment_date": date,
			"appointment_type": appointment_type,
			"patient": patient,
			"service_unit": service_unit,
			"appointment_for": "Practitioner",
		}
	)
	return availability(doc)


def validate_appointment(doc, method=None):
	"""Final check for new/rescheduled visits, serialized across doctor and room."""
	if doc.appointment_for != "Practitioner" or not doc.practitioner or doc.appointment_based_on_check_in:
		return
	if doc.status == "Cancelled" or doc.docstatus == 2:
		return
	old = doc.get_doc_before_save()
	if old and not any(
		_scheduling_value(doc, field) != _scheduling_value(old, field) for field in SCHEDULING_FIELDS
	):
		return
	if not (doc.appointment_date and doc.appointment_time and doc.appointment_type):
		return  # Healthcare supplies the ordinary mandatory-field feedback.
	for doctype, field in [
		("Patient", "patient"),
		("Healthcare Practitioner", "practitioner"),
		("Healthcare Service Unit", "service_unit"),
	]:
		values = {row.get(field) for row in [doc, old] if row and row.get(field)}
		for value in sorted(values):
			frappe.db.get_value(doctype, value, "name", for_update=True)
	result = availability(doc, lock=True)
	chosen = next(
		(
			row
			for row in result["slots"]
			if get_time(row["time"]) == get_time(doc.appointment_time)
			and row["service_unit"] == (doc.service_unit or "")
		),
		None,
	)
	if not chosen:
		frappe.throw(_("The requested slot is no longer available. Please select another slot."))
	doc.duration = chosen["duration"]
