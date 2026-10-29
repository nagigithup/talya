import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


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

	def _require_reception(self):
		if not ({"System Manager", "Talya Receptionist"} & set(frappe.get_roles())):
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	@frappe.whitelist(methods=["POST"])
	def confirm_booking(self):
		self._require_reception()
		if self.booking_status != "Pending":
			frappe.throw(_("Only pending bookings can be confirmed."))
		if not self.linked_patient:
			frappe.throw(_("Link a verified Patient record before confirmation."))
		if self.linked_patient_appointment:
			frappe.throw(_("This request is already linked to an appointment."))

		from talya.booking import create_patient_appointment

		appointment = create_patient_appointment(self)
		self.db_set({"linked_patient_appointment": appointment.name, "booking_status": "Confirmed"})
		return appointment.name

	@frappe.whitelist(methods=["POST"])
	def reject_booking(self, reason=None):
		self._require_reception()
		if self.booking_status != "Pending":
			frappe.throw(_("Only pending bookings can be rejected."))
		if not (reason or self.rejection_reason):
			frappe.throw(_("A rejection reason is required."))
		self.db_set({"rejection_reason": reason or self.rejection_reason, "booking_status": "Rejected"})
