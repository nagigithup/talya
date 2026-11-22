import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

from talya.recipients import assert_patient_recipient, normalize_phone


class TalyaPatientInquiry(Document):
	def on_update(self):
		from talya.communication import detach_previous_profile, link_profile

		detach_previous_profile(self, self.get_doc_before_save())
		link_profile(self)

	def validate(self):
		self.whatsapp_consent = cint(self.whatsapp_consent)
		self.opt_out = cint(self.opt_out)
		if not self.flags.from_booking and not self.flags.integration_update:
			if self.is_new() and any(
				self.get(f)
				for f in (
					"website_booking",
					"linked_patient",
					"linked_patient_appointment",
					"wa_profile",
					"import_key",
				)
			):
				frappe.throw(_("Linked records must be updated through the inquiry actions."))
			if self.is_new():
				self.source = "Manual"
		old = self.get_doc_before_save()
		if old and not self.flags.from_booking:
			for field in (
				"website_booking",
				"linked_patient",
				"linked_patient_appointment",
				"source",
				"wa_profile",
				"import_key",
			):
				if self.get(field) != old.get(field) and not self.flags.integration_update:
					frappe.throw(_("Linked records must be updated through the inquiry actions."))
		self.normalized_phone = normalize_phone(self.mobile_number)
		old_phone = old.normalized_phone or normalize_phone(old.mobile_number) if old else None
		changed = bool(old and old_phone != self.normalized_phone)
		if changed and old.linked_patient_appointment:
			frappe.throw(_("Create a new inquiry to change the recipient of a linked appointment."))
		# These bindings are server-owned. Neither a client flag nor a same-request
		# consent checkbox may carry the previous recipient's authorization forward.
		self.recipient_changed_at = old.get("recipient_changed_at") if old else None
		self.patient_verified_at = old.get("patient_verified_at") if old else None
		patient_changed = bool(old and old.linked_patient and old.linked_patient != self.linked_patient)
		if patient_changed and not changed:
			frappe.throw(_("Create a new inquiry to use a different Patient."))
		if changed:
			self.whatsapp_consent = 0
			self.linked_patient = None
			self.wa_profile = None
			self.patient_verified_at = None
			self.recipient_changed_at = now_datetime()
			self.status = "New"
		elif old and old.linked_patient != self.linked_patient:
			self.patient_verified_at = None
		if patient_changed:
			self.whatsapp_consent = 0
		if self.flags.verify_patient and self.linked_patient:
			assert_patient_recipient(self, self.linked_patient, check_permission=False)
			self.patient_verified_at = now_datetime()
		elif self.linked_patient:
			assert_patient_recipient(self, self.linked_patient, check_permission=False)
		self.consent_phone = None
		self.consent_recorded_at = None
		if self.whatsapp_consent:
			if old and old.whatsapp_consent:
				if old.get("consent_phone") == self.normalized_phone:
					self.consent_phone = old.consent_phone
					self.consent_recorded_at = old.consent_recorded_at
				else:
					# Legacy consent without a recipient binding must be obtained again.
					self.whatsapp_consent = 0
			else:
				self.consent_phone = self.normalized_phone
				self.consent_recorded_at = now_datetime()
		if self.status == "Booked" and not self.linked_patient_appointment:
			frappe.throw(_("Book a Healthcare appointment before marking this inquiry Booked."))
		if old and old.linked_patient_appointment and self.status not in ("Booked", "Closed"):
			frappe.throw(_("Manage the linked appointment before changing this status."))
