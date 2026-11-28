"""Public SEO regressions using synthetic profiles; no DB writes or transport."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.robotparser import RobotFileParser

import frappe
from werkzeug.datastructures import Headers

from talya import seo
from talya.website_content import DENTAL_SERVICES, DOCTORS, LABELS, MAPS_URL, PHONE, PUBLIC_ROUTES

APP = Path(__file__).resolve().parents[2]


class TestPublicSEO(unittest.TestCase):
	def setUp(self):
		self.framework = SimpleNamespace(
			conf={"talya_canonical_origin": "https://clinic.example.com"},
			local=SimpleNamespace(
				site="synthetic-production.example.com",
				lang="en",
				flags=frappe._dict(),
				request=SimpleNamespace(
					path="/en", method="GET", host="clinic.example.com", query_string=b""
				),
				response_headers={},
			),
			form_dict={},
			sessions=SimpleNamespace(get_csrf_token=lambda: "synthetic-csrf"),
			get_app_path=lambda _app, *parts: str(APP / "talya" / Path(*parts)),
			get_all=lambda *_args, **_kwargs: [],
			DoesNotExistError=frappe.DoesNotExistError,
			Redirect=frappe.Redirect,
		)
		self.patch = patch.object(seo, "frappe", self.framework)
		self.patch.start()
		self.addCleanup(self.patch.stop)
		seo.arabic_catalogue.cache_clear()
		self.addCleanup(seo.arabic_catalogue.cache_clear)
		public_rows = patch("talya.api._public_practitioners", return_value=[])
		self.rows = public_rows.start()
		self.addCleanup(public_rows.stop)
		booking_session = patch("talya.public_booking.browser_session")
		booking_session.start()
		self.addCleanup(booking_session.stop)

	def context(self, path):
		self.framework.local.request.path = path
		return seo.get_public_context(
			frappe._dict(boot={"lang": "en"}), home=path.rstrip("/") in ("/en", "/ar")
		)

	def test_one_page_per_intent_and_language(self):
		self.assertEqual(len(PUBLIC_ROUTES), 12)
		for page, language in PUBLIC_ROUTES.values():
			self.assertEqual(PUBLIC_ROUTES[seo.page_path(page, language)], (page, language))

	def test_all_website_copy_has_arabic_translation(self):
		catalogue = seo.arabic_catalogue()
		for key, source in LABELS.items():
			with self.subTest(key=key):
				self.assertTrue(catalogue.get(source), source)

	def test_https_origin_validation_rejects_paths_secrets_and_host_injection(self):
		for value in (
			"http://clinic.example.com",
			"https://user:password@clinic.example.com",
			"https://clinic.example.com/desk",
			"https://clinic.example.com?token=synthetic",
			"https://clinic.example.com#fragment",
			"https://127.0.0.1",
			"https://talya.localhost",
			"https://clinic.example.com:8000",
			"https://clinic.example.com\n",
			"https://clinic%2f.example.com",
			"https://clinic..example.com",
		):
			with self.subTest(value=value):
				self.assertIsNone(seo.validated_origin(value))
		self.assertEqual(seo.validated_origin("https://CLINIC.example.com/"), "https://clinic.example.com")

	def test_unconfirmed_origin_is_never_taken_from_request_host(self):
		approved = patch.object(seo, "APPROVED_ORIGIN", "")
		approved.start()
		self.addCleanup(approved.stop)
		self.framework.conf.clear()
		self.framework.local.request.host = "attacker.example.com"
		self.assertIsNone(seo.canonical_origin())
		self.assertEqual(seo.sitemap_links(), [])
		self.assertNotIn("User-agent: *\nDisallow: /\n", seo.robots_text())
		self.assertNotIn("Sitemap:", seo.robots_text())
		# An unconfirmed canonical must not introduce a site-wide indexing block.
		self.framework.local.request.host = "synthetic-production.example.com"
		self.assertEqual(self.context("/en").seo["robots"], "index, follow, max-image-preview:large")

	def test_local_preview_has_approved_https_canonicals_and_noindex(self):
		self.framework.conf.clear()
		self.framework.local.site = "talya.localhost"
		self.framework.local.request.host = "127.0.0.1:8000"
		context = self.context("/ar")
		self.assertEqual(context.seo["canonical_url"], "https://talyamedical.com/ar")
		self.assertEqual(context.seo["robots"], "noindex, follow")
		self.assertIn("Disallow: /", seo.robots_text())

	def test_all_canonicals_are_self_referential_with_reciprocal_language_pairs(self):
		titles, descriptions = set(), set()
		for path, (page, language) in PUBLIC_ROUTES.items():
			with self.subTest(path=path):
				context = self.context(path)
				self.assertEqual(context.seo["canonical_url"], "https://clinic.example.com" + path)
				self.assertEqual(context.seo["robots"], "index, follow, max-image-preview:large")
				self.assertEqual(context.boot["lang"], language)
				self.assertEqual(context.direction, "rtl" if language == "ar" else "ltr")
				for other_language in ("en", "ar"):
					other = seo.page_path(page, other_language)
					self.assertIn(other, PUBLIC_ROUTES)
					self.assertEqual(
						context.seo["alternates"][other_language + "-AE"],
						"https://clinic.example.com" + other,
					)
				titles.add(context.title)
				descriptions.add(context.description)
		self.assertEqual(len(titles), 12)
		self.assertEqual(len(descriptions), 12)

	def test_arabic_route_overrides_language_query_and_previous_locale(self):
		self.framework.form_dict = {"lang": "en", "language": "en"}
		self.framework.local.lang = "en"
		context = self.context("/ar/doctors/dr-mehira-fadl")
		self.assertEqual(context.language, "ar")
		self.assertEqual(context.doctor["name"], "د. مهيرة فضل")
		self.assertIn("رأس الخيمة", context.title)

	def test_hidden_controller_and_unknown_pages_return_not_found(self):
		for path in ("/talya_public", "/en/doctors/unknown", "/fr", "/en/services/implants"):
			with self.subTest(path=path), self.assertRaises(frappe.DoesNotExistError):
				self.context(path)

	def test_verified_public_profile_prefills_existing_booking_flow(self):
		self.rows.return_value = [
			{
				"id": "SYNTHETIC-PUBLIC-GP",
				"department": "General Practice",
				"name_en": "Dr. Mehira Fadl",
				"name_ar": "د. مهيرة فضل",
				"image": "/assets/talya/images/dr-mehira-original.webp",
				"booking_enabled": True,
			}
		]
		self.framework.form_dict = {"doctor": "mehira"}
		context = self.context("/en")
		self.assertEqual(context.selected_doctor, "SYNTHETIC-PUBLIC-GP")
		self.assertEqual(context.alternate_path, "/ar?doctor=mehira")
		self.assertEqual(context.profiles["mehira"]["booking_path"], "/en?doctor=mehira#appointment")
		self.assertEqual(context.practitioners[0]["profile_url"], "/en/doctors/dr-mehira-fadl")

	def test_missing_local_healthcare_records_do_not_hide_crawlable_profiles(self):
		context = self.context("/en")
		self.assertEqual(len(context.profiles), 2)
		self.assertFalse(context.profiles["mehira"]["booking_enabled"])
		self.assertFalse(context.profiles["farouq"]["booking_enabled"])
		self.assertTrue(context.profiles["mehira"]["path"])
		self.assertTrue(context.profiles["farouq"]["path"])

	def test_reused_portrait_does_not_link_an_unknown_or_conflicting_doctor(self):
		self.assertIsNone(
			seo.profile_key(
				{"name_en": "Other Doctor", "image": "/assets/talya/images/dr-mehira-original.webp"}
			)
		)
		self.assertIsNone(
			seo.profile_key({"name_en": "Dr. Mehira Fadl", "image": "/assets/talya/images/dr-farouq.png"})
		)
		self.assertEqual(
			seo.profile_key({"name_en": "Dr. Farouq Ejami", "image": "/assets/talya/images/dr-farouq.png"}),
			"farouq",
		)

	def test_schema_matches_visible_name_bio_clinic_phone_and_maps(self):
		for path in ("/en/doctors/dr-mehira-fadl", "/ar/doctors/dr-farouq-ejami"):
			context = self.context(path)
			data = json.loads(json.dumps(context.seo["json_ld"]))
			clinic, webpage, person = data["@graph"]
			self.assertEqual(clinic["@type"], "MedicalClinic")
			self.assertEqual(clinic["telephone"], PHONE)
			self.assertEqual(clinic["hasMap"], MAPS_URL)
			self.assertEqual(person["@type"], "Person")
			self.assertEqual(person["name"], context.doctor["name"])
			self.assertEqual(person["description"], context.doctor["bio"])
			self.assertEqual(webpage["mainEntity"]["@id"], person["@id"])

	def test_approved_nationality_language_and_clinic_hours_do_not_invent_individual_experience(self):
		context = self.context("/en/doctors/dr-mehira-fadl")
		data = json.dumps(context.seo["json_ld"])
		for key in (
			"aggregateRating",
			"review",
			"priceRange",
			"award",
			"hasCredential",
		):
			self.assertNotIn('"' + key, data)
		clinic, _page, person = context.seo["json_ld"]["@graph"]
		self.assertEqual(person["nationality"], {"@type": "Country", "name": "Sudan"})
		self.assertEqual(person["knowsLanguage"], ["ar"])
		self.assertNotIn("10 years", person["description"])
		self.assertNotIn("government hospitals", person["description"])
		hours = clinic["openingHoursSpecification"][0]
		self.assertEqual((hours["opens"], hours["closes"]), ("16:00", "00:00"))
		self.assertEqual(len(hours["dayOfWeek"]), 7)
		self.assertIn("Friday", hours["dayOfWeek"])
		for doctor in DOCTORS.values():
			self.assertFalse(doctor["experience"])

	def test_only_confirmed_cleaning_and_filling_prices_are_published(self):
		priced = {
			service["label"]: service["price"] for service in DENTAL_SERVICES if service["price"] is not None
		}
		self.assertEqual(priced, {"professional_cleaning": 150, "cavity_fillings": 150})
		for service in DENTAL_SERVICES:
			if "crowns_bridges" in service["label"]:
				self.assertIsNone(service["price"])
		self.assertEqual(
			seo.labels_for("en")["doctors_intro"],
			"Talya\u2019s team includes Arabic-speaking Sudanese doctors with over 10 years of experience in UAE government hospitals.",
		)

	def test_sitemap_is_an_allowlist_of_only_the_twelve_canonical_pages(self):
		links = seo.sitemap_links()
		self.assertEqual(len(links), 12)
		self.assertEqual(len(set(links)), 12)
		for link in links:
			self.assertTrue(link.startswith("https://clinic.example.com/"))
			self.assertFalse(seo.private_path(link.removeprefix("https://clinic.example.com")))
			self.assertNotIn("?", link)
			self.assertNotIn("#", link)

	def test_production_robots_allows_public_pages_and_assets_and_references_sitemap(self):
		text = seo.robots_text()
		parser = RobotFileParser()
		parser.parse(text.splitlines())
		for path in (*PUBLIC_ROUTES, "/assets/talya/css/talya.css"):
			self.assertTrue(parser.can_fetch("Googlebot", path), path)
		for path in seo.PRIVATE_PATHS:
			self.assertFalse(parser.can_fetch("Googlebot", path), path)
		self.assertIn("Sitemap: https://clinic.example.com/sitemap.xml", text)

	def test_explicit_site_robots_policy_is_preserved(self):
		self.assertIn("User-agent: *\nDisallow: /\n", seo.robots_text("User-agent: *\nDisallow: /\n"))

	def test_private_responses_are_noindex_without_changing_access_permissions(self):
		for path in (
			"/desk",
			"/desk/healthcare",
			"/patient_inquiries",
			"/api/resource/Patient",
			"/printview",
		):
			response = SimpleNamespace(headers=Headers())
			seo.after_request(response, SimpleNamespace(path=path))
			self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow, noarchive")
		response = SimpleNamespace(headers=Headers())
		seo.after_request(response, SimpleNamespace(path="/ar"))
		self.assertEqual(response.headers["Content-Language"], "ar-AE")
		self.assertNotIn("X-Robots-Tag", response.headers)

	def test_confirmed_production_alias_redirect_preserves_path_and_query(self):
		self.framework.local.request.path = "/ar/doctors/dr-mehira-fadl"
		self.framework.local.request.host = "old-cloud.example.com"
		self.framework.local.request.query_string = b"source=clinic"
		with self.assertRaises(frappe.Redirect) as caught:
			seo.get_public_context(frappe._dict())
		self.assertEqual(caught.exception.http_status_code, 301)
		self.assertEqual(
			self.framework.local.flags.redirect_location,
			"https://clinic.example.com/ar/doctors/dr-mehira-fadl?source=clinic",
		)

	def test_trailing_slash_redirect_preserves_the_booking_query(self):
		self.framework.local.request.path = "/en/"
		self.framework.local.request.query_string = b"doctor=mehira"
		with self.assertRaises(frappe.Redirect):
			seo.get_public_context(frappe._dict(), home=True)
		self.assertEqual(self.framework.local.flags.redirect_location, "/en?doctor=mehira")


if __name__ == "__main__":
	unittest.main()
