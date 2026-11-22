import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_time, getdate, now_datetime


class TalyaOnlineBooking(Document):
	def before_insert(self):
		self.booking_status = "Pending"
		self.source = "Website"
		self.consent_timestamp = self.consent_timestamp or now_datetime()

	def after_insert(self):
		if not self.booking_reference:
			self.db_set("booking_reference", self.name, update_modified=False)

	def validate(self):
		if getdate(self.preferred_date) < getdate():
			frappe.throw(_("Appointment date cannot be in the past."))
		if not self.consent_accepted:
			frappe.throw(_("Privacy consent is required."))
		if self.is_new() and self.booking_status != "Pending":
			frappe.throw(_("New website bookings must be pending."))
		old = self.get_doc_before_save()
		if old and (self.patient_name != old.patient_name or self.mobile_number != old.mobile_number):
			from talya.recipients import normalize_phone

			if self.patient_name != old.patient_name or normalize_phone(
				self.mobile_number
			) != normalize_phone(old.mobile_number):
				if old.booking_status == "Confirmed":
					frappe.throw(_("Change confirmed visit details on the Patient Appointment."))
				# Keep the inquiry's history intact. A changed booking recipient must
				# go through explicit verification again, even on a shared number.
				self.linked_patient = None
		if old and self.booking_status != old.booking_status:
			frappe.throw(_("Manage booking status through the reception actions."))
		if (
			old
			and old.booking_status == "Confirmed"
			and any(
				self.get(field) != old.get(field)
				for field in ("healthcare_practitioner", "appointment_type", "service_unit")
			)
		):
			frappe.throw(_("Change confirmed visit details on the Patient Appointment."))
		if self.appointment_type and self.preferred_time:
			minutes = cint(frappe.db.get_value("Appointment Type", self.appointment_type, "default_duration"))
			self.appointment_end_time = (
				datetime.datetime.combine(getdate(self.preferred_date), get_time(self.preferred_time))
				+ datetime.timedelta(minutes=minutes)
			).time()

	def _require_reception(self):
		if not ({"System Manager", "Talya Receptionist"} & set(frappe.get_roles())):
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	@frappe.whitelist(methods=["POST"])
	def confirm_booking(
		self,
		patient=None,
		patient_data=None,
		identity_verified=False,
		reviewed_matches=False,
		expected_modified=None,
	):
		from talya.online_booking import confirm

		return confirm(
			self.name,
			patient=patient,
			patient_data=patient_data,
			identity_verified=identity_verified,
			reviewed_matches=reviewed_matches,
			expected_modified=expected_modified,
		)

	@frappe.whitelist(methods=["POST"])
	def link_verified_patient(self, patient, identity_verified=False, expected_modified=None):
		from talya.online_booking import link_patient

		return link_patient(self.name, patient, identity_verified, expected_modified)

	@frappe.whitelist(methods=["POST"])
	def reject_booking(self, reason=None):
		self._require_reception()
		inquiry = frappe.db.get_value("Talya Patient Inquiry", {"website_booking": self.name}, "name")
		if inquiry:
			frappe.db.get_value("Talya Patient Inquiry", inquiry, "name", for_update=True)
		frappe.db.get_value(self.doctype, self.name, "name", for_update=True)
		self.reload()
		if self.booking_status != "Pending":
			frappe.throw(_("Only pending bookings can be rejected."))
		if not (reason or self.rejection_reason):
			frappe.throw(_("A rejection reason is required."))
		self.db_set({"rejection_reason": reason or self.rejection_reason, "booking_status": "Rejected"})
		from talya.inquiries import sync_booking

		sync_booking(self)
