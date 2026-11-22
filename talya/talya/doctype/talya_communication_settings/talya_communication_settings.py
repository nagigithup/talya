import frappe
from frappe import _
from frappe.model.document import Document


class TalyaCommunicationSettings(Document):
	def validate(self):
		import phonenumbers

		code = str(self.country_calling_code or "")
		if (
			not code.isdigit()
			or not 1 <= len(code) <= 3
			or phonenumbers.region_code_for_country_code(int(code)) in (None, "ZZ")
		):
			frappe.throw(_("Enter a valid country calling code."))
		if not 1 <= int(self.reminder_hours or 0) <= 168:
			frappe.throw(_("Reminder timing must be between 1 and 168 hours."))
		self.require_consent = 1
		if self.reminders_enabled and not self.reminder_template:
			frappe.throw(_("Select an approved reminder template before enabling reminders."))
		for field in ("confirmation_template", "reminder_template"):
			if self.get(field):
				if (
					"whatsapp" not in frappe.get_installed_apps()
					or frappe.db.get_value("WA Template", self.get(field), "status") != "Approved"
				):
					frappe.throw(_("Only approved WhatsApp templates may be sent."))
