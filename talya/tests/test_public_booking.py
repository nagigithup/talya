import frappe
from frappe.tests import IntegrationTestCase

from talya.api import PHONE_RE, _clean, get_public_data


class TestTalyaPublicBooking(IntegrationTestCase):
	def test_phone_validation(self):
		self.assertTrue(PHONE_RE.fullmatch("+971 52 2207872"))
		self.assertFalse(PHONE_RE.fullmatch("not-a-number"))

	def test_clean_strips_markup_and_limits_length(self):
		self.assertEqual(_clean("<b> Talya </b>", 20), "Talya")
		self.assertEqual(_clean("abcdef", 3), "abc")

	def test_public_data_exposes_only_approved_fields(self):
		data = get_public_data()
		self.assertIn("practitioners", data)
		self.assertIn("departments", data)
		allowed = {"id", "department", "image", "name_en", "name_ar", "specialty_en", "specialty_ar", "bio_en", "bio_ar", "booking_enabled"}
		for practitioner in data["practitioners"]:
			self.assertEqual(set(practitioner), allowed)
			self.assertNotIn("mobile_phone", practitioner)

	def test_guest_has_no_booking_read_permission(self):
		permissions = frappe.get_meta("Talya Online Booking").get_permissions()
		self.assertFalse(any(row.role == "Guest" and row.read for row in permissions))
